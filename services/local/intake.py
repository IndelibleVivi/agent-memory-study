"""Capture first, private operational links, and bounded candidate context."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import subprocess
from .records import ACTOR,command,record,ref,revise
from .repository import encoded,now

INTAKE_MIGRATION_SQL=(
 'CREATE TABLE intake_operations (idempotency_key TEXT PRIMARY KEY,payload TEXT NOT NULL,receipt TEXT NOT NULL)',
 'CREATE TABLE intake_links (capture_id TEXT PRIMARY KEY,details TEXT NOT NULL)',
)
MAX_CAPTURE_BYTES=8*1024*1024

def remember(repo,key,payload,action):
    if not isinstance(key,str) or not 1<=len(key)<=200:raise ValueError('explicit bounded idempotency key required')
    with repo.transaction():
        old=repo.db.execute('SELECT payload,receipt FROM intake_operations WHERE idempotency_key=?',(key,)).fetchone()
        if old:
            if old['payload']!=encoded(payload):raise ValueError('idempotency payload conflict')
            return json.loads(old['receipt'])
        value=action()
        repo.db.execute('INSERT INTO intake_operations VALUES (?,?,?)',(key,encoded(payload),encoded(value)))
    return value

def details(repo,capture_id):
    repo.load('capture',capture_id)
    with repo.lock:row=repo.db.execute('SELECT details FROM intake_links WHERE capture_id=?',(capture_id,)).fetchone()
    return json.loads(row[0]) if row else {}

def set_details(repo,capture_id,value):
    repo.db.execute('INSERT INTO intake_links VALUES (?,?) ON CONFLICT(capture_id) DO UPDATE SET details=excluded.details',(capture_id,encoded(value)))

class CaptureService:
    def __init__(self,repo,project,public_records=()):
        self.repo=repo;self.project=Path(project).resolve();self.public=list(public_records)
        repo.cache_public_records(self.public)
    def capture(self,text,*,channel='manual',why_now='',context_refs=(),idempotency_key,actor=ACTOR):
        if not isinstance(text,str) or not text.strip() or len(text.encode())>MAX_CAPTURE_BYTES:raise ValueError('nonempty bounded input required')
        from schemas.validate import exact_ref
        from .arguments import ArgumentService
        resolver=ArgumentService(self.repo,self.public)
        for r in context_refs:exact_ref(r);resolver.resolve(r)
        payload={'input':text,'channel':channel,'why_now':why_now,'context_refs':list(context_refs),'actor':actor}
        def apply():
            value=record('capture',{'captured_at':now(),'actor':actor,'channel':channel,'input':text,'why_now':why_now,'attention':'resting','visibility':'private'})
            ack=self.repo._apply(command(value,actor=actor));set_details(self.repo,value['id'],{'context_refs':list(context_refs),'identity_state':'unresolved','acquisition_state':'not-requested','return_when':''})
            return {'capture':value,'ack':ack,'saved':'committed-local'}
        return remember(self.repo,idempotency_key,payload,apply)
    def capture_bytes(self,text,raw,*,media_type='application/octet-stream',idempotency_key,channel='manual',why_now=''):
        if not isinstance(raw,bytes):raise ValueError('selected bytes required, not a filesystem path')
        # Preserve a Capture even if bytes are rejected. The separate receipt is retryable.
        captured=self.capture(text,channel=channel,why_now=why_now,idempotency_key=idempotency_key+':capture')
        from .acquisition import AcquisitionService
        acq=AcquisitionService(self.repo,self.public)
        plan=acq.plan_file(captured['capture']['id'],filename=text,media_type=media_type,idempotency_key=idempotency_key+':plan')
        result=acq.execute_file(plan['id'],raw,idempotency_key=idempotency_key+':bytes')
        return {**captured,'acquisition':result}
    def capture_connector(self,receipt,*,idempotency_key):
        connector=receipt.get('connector')
        if connector=='zotero-readonly/1':rows=receipt['records'];channel='zotero'
        elif connector=='github-readonly/1':rows=[receipt];channel='github'
        else:raise ValueError('known read-only connector receipt required')
        if len(rows)>100:raise ValueError('bounded explicitly selected records required')
        saved=[]
        for n,row in enumerate(rows):
            if channel=='github':
                text='https://github.com/'+row['repository_locator']+'/commit/'+row['commit'];suggested=row['identifiers']
            else:
                text=('https://doi.org/'+row['doi']) if row.get('doi') else row.get('url') or row.get('title') or row['item_key']
                suggested=[{'namespace':'doi','value':row['doi'].lower()}] if row.get('doi') else []
            base=self.capture(text,channel=channel,idempotency_key=f'{idempotency_key}:{n}:capture')
            def link():
                d=details(self.repo,base['capture']['id']);d['connector_metadata']=row;d['connector_library_record_version']=receipt.get('library_record_version');d['suggested_identifiers']=suggested;d['connector_response_digest']=receipt['response_digest'];set_details(self.repo,base['capture']['id'],d)
                return {'capture_ref':ref(base['capture']),'metadata_only':True,'suggested_identifiers':suggested,'identity_accepted':False}
            saved.append(remember(self.repo,f'{idempotency_key}:{n}:metadata',{'connector':connector,'record':row,'response_digest':receipt['response_digest']},link))
        return saved

    def get(self,id):return {'capture':self.repo.load('capture',id),'details':details(self.repo,id)}
    def list(self):return [self.get(c['id']) for c in self.repo.list('capture')]
    def attention(self,id,attention,*,expected_revision,return_when='',idempotency_key):
        payload={'capture_id':id,'attention':attention,'expected_revision':expected_revision,'return_when':return_when}
        def apply():
            old=self.repo.load('capture',id)
            if old['revision']!=expected_revision:raise ValueError('stale capture attention')
            new=revise(old,attention=attention);ack=self.repo._apply(command(new,previous=old));d=details(self.repo,id);d['return_when']=return_when;set_details(self.repo,id,d)
            return {'capture':new,'ack':ack}
        return remember(self.repo,idempotency_key,payload,apply)
    def batch(self,inputs,*,batch_key):
        if not isinstance(inputs,list) or len(inputs)>100:raise ValueError('bounded explicit batch required')
        out=[]
        for n,text in enumerate(inputs):
            try:out.append({'index':n,'status':'saved','result':self.capture(text,idempotency_key=f'{batch_key}:{n}')})
            except (ValueError,TypeError) as exc:out.append({'index':n,'status':'rejected','reason':str(exc)})
        return out
    def context_links(self,id,*,changed_public=None):
        capture=self.repo.load('capture',id);text=capture['input'].lower()
        def tokens(value):
            latin=set(re.findall(r'[a-z0-9]{3,}',value.lower()));chinese=re.findall(r'[\u4e00-\u9fff]+',value)
            return latin|{part[i:i+2] for part in chinese for i in range(len(part)-1)}
        query=tokens(text);candidates=[]
        for obj in self.public:
            fields=' '.join(str(obj.get(k,'')) for k in ('title','intro','claim'))
            matched=sorted(query&tokens(fields))
            if matched:candidates.append({'object_ref':ref(obj),'locator':'public:title/intro/claim','source_fragment':fields[:600],'matched':matched[:12],'method':'lexical-token-overlap/1','status':'proposal','rationale':'词项交集仅作为阅读切口，不认证支持或理论等价'})
        candidates.sort(key=lambda c:(-len(c['matched']),c['object_ref']['id']))
        explicit=None;formal=None
        if changed_public:
            if set(changed_public)!={'kind','id'} or changed_public['kind'] not in ('material','study','question','finding'):raise ValueError('known public object required')
            manifest=self.project/'data/public-corpus.manifest.json'
            request={'command':'impact','dataFile':str(manifest),'kind':changed_public['kind'],'id':changed_public['id']}
            # Fixed local bridge consumes compiler manifest / shared ResearchMap only.
            result=subprocess.run(['node',str(self.project/'tools/research_context.cjs')],cwd=self.project,input=encoded(request),capture_output=True,text=True,timeout=20)
            if result.returncode:explicit={'status':'unavailable','reason':'shared reference bridge rejected request'}
            else:explicit=json.loads(result.stdout).get('result')
        from .arguments import ArgumentService
        d=details(self.repo,id);review_refs=list(d.get('context_refs',[]));version_change=None
        if d.get('source_revision_ref'):
            source=ArgumentService(self.repo,self.public).resolve(d['source_revision_ref'])
            if source.get('predecessor_ref'):
                review_refs.append(source['predecessor_ref']);version_change={'old_ref':source['predecessor_ref'],'new_ref':ref(source),'status':'structural-review-candidate','semantic_conflict':False}
        seen=set()
        for r in review_refs:
            key=(r['kind'],r['id'],r['revision'])
            if key in seen:continue
            seen.add(key)
            candidate=ArgumentService(self.repo,self.public).impact(r)
            if formal is None:formal=[]
            formal.append(candidate)
        return {'capture_ref':ref(capture),'candidates':candidates[:8],'explicit_review_scope':explicit,'formal_review_scope':formal,'automatic_acceptance':False,'source_version_change':version_change}
