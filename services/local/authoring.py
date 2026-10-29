"""Private manuscript/review orchestration over the existing canonical owners.

No source scanning, provider calls, production Git writes or publication gate.
"""
from __future__ import annotations
import base64
import json
from pathlib import Path
import re
import subprocess
import tempfile
from schemas.validate import exact_ref,walk_exact_refs
from .arguments import ArgumentService
from .intake import remember
from .records import ACTOR,record,command,ref,revise
from .repository import now
from .revisions import RevisionService,git,path_inside,entry_body_path
from .publication import PublicationService

DECISIONS=('maintain','narrow','rewrite','needs-experiment','defer')
PUBLIC_METADATA=('id','title','subtitle','kind','date','byline','intro','domains','directionIds','readings','externalReadings','boundary','materialIds')
MAX_TEXT=2*1024*1024

def bounded(text,name,required=False):
    if not isinstance(text,str) or len(text.encode())>MAX_TEXT or (required and not text.strip()):raise ValueError(name+' must be explicit bounded text')
    return text

class ReviewAuthoringService:
    def __init__(self,repo,project,public_records=(),*,review_authorizer=None):
        public_records=list(public_records);self.repo=repo;self.project=Path(project).resolve()
        self.arguments=ArgumentService(repo,public_records,review_authorizer=review_authorizer)
        self.revisions=RevisionService(repo,project,public_records,review_authorizer=review_authorizer)
        self.publication=PublicationService(repo,project,public_records,review_authorizer=review_authorizer)
    def catalogue(self):
        private=self.repo.list();public=list(self.arguments.public.values());seen=set();rows=[]
        values=[*private,*public];known={exact_ref(ref(v)) for v in values}
        # Explicit saved references, including an old excerpt's basis, remain
        # selectable. Do not replace them with the current head or list every
        # unreferenced historical revision.
        for value in values:
            for pointer in walk_exact_refs(value):
                key=exact_ref(pointer)
                if key not in known:
                    known.add(key);values.append(self.arguments.resolve(pointer))
        for value in values:
            key=tuple(ref(value).values())
            if key in seen or value['kind'] in ('session','capture','read_activity','extraction','changeset','publication_manifest'):continue
            seen.add(key);rows.append({'ref':ref(value),'title':value.get('title') or value.get('statement') or value.get('claim') or value.get('method') or value['id'],'scope':value.get('scope',''),'public':value in public,'editable':value['kind'] in ('entry','claim_revision','thread')})
        try:base=git(self.project,'rev-parse','HEAD')
        except (subprocess.CalledProcessError,FileNotFoundError):base=None
        return {'records':rows,'base_commit':base,'decisions':list(DECISIONS),'git_execution':False}
    def open(self,target_ref):
        value=self.arguments.resolve(target_ref);payload=value.get('payload',{})
        body=payload.get('bodyMarkdown',payload.get('body',payload.get('note',value.get('claim',value.get('statement',value.get('body',value.get('result','')))))))
        if value['kind']=='excerpt':body=value['selector']
        if value['kind']=='artifact' and value['storage']['kind']=='blob':
            try:body=self.repo.read_blob(value['artifact_digest']).decode('utf-8')
            except UnicodeError:body=''
        if not isinstance(body,str):body=''
        public=exact_ref(target_ref) in self.arguments.public
        try:current=self.repo.load(value['kind'],value['id'])
        except ValueError:current=value
        with self.repo.lock:
            withdrawn={r[0] for r in self.repo.db.execute('SELECT relation_revision FROM argument_withdrawals')}
            decisions={r['proposal_revision']:{'decision':r['decision'],'rationale':r['rationale'],'authorization':json.loads(r['actor'])} for r in self.repo.db.execute('SELECT * FROM argument_decisions')}
        return {'record':value,'body':body,'body_status':'snapshot-bound' if body else 'not-recorded-or-empty','public':public,'withdrawn_relations':list(withdrawn),'proposal_decisions':decisions,
                'current_ref':ref(current),'scope':value.get('scope',payload.get('scope','')),'open_question':payload.get('open_question',''),
                'relations':[r for r in self.repo.list('evidence_relation') if target_ref in (r['from_ref'],r['to_ref'])],
                'proposals':[r for r in self.repo.list('relation_proposal') if target_ref in (r['from_ref'],r['to_ref'])],
                'bundles':[r for r in self.repo.list('support_bundle') if r['conclusion_ref']==target_ref],
                'impact':self.arguments.impact(target_ref)}
    def create(self,*,kind='entry',title,body,byline,intro='',scope='',open_question='',entry_type='learning-note',basis_ref=None,idempotency_key,actor=ACTOR):
        for name,value in [('title',title),('body',body),('byline',byline),('intro',intro),('scope',scope),('open_question',open_question)]:bounded(value,name,name in ('title','byline'))
        if entry_type not in ('learning-note','research-essay'):raise ValueError('lightweight authored entry type required')
        if kind not in ('entry','claim_revision','thread'):raise ValueError('supported private authored kind required')
        if basis_ref is not None:self.arguments.resolve(basis_ref)
        fields={'kind':kind,'title':title,'body':body,'byline':byline,'intro':intro,'scope':scope,'open_question':open_question,'entry_type':entry_type,'basis_ref':basis_ref,'actor':actor}
        def apply():
            payload={'bodyMarkdown':body,'open_question':open_question,'scope':scope,'authored_private':True,**({'source_basis_ref':basis_ref} if basis_ref else {})}
            if kind=='entry':
                if not intro.strip():raise ValueError('short manuscript introduction required')
                value=record('entry',{'entry_type':entry_type,'title':title,'byline':byline,'date':now()[:10],'intro':intro,'body_file':'study/entries/private-'+__import__('uuid').uuid4().hex+'.md','payload':payload,'references':[]})
            elif kind=='claim_revision':
                if not scope.strip() or not body.strip():raise ValueError('claim statement and bounded scope required')
                value=record(kind,{'title':title,'byline':byline,'claim':body,'scope':scope,'scope_binding':scope,'payload':payload})
            else:value=record(kind,{'title':title,'byline':byline,'status':'open','payload':payload})
            self.repo._apply(command(value,actor=actor));return {'record':value,'private':True,'public_files_written':False}
        return remember(self.repo,idempotency_key,{'operation':'authoring.create',**fields},apply)
    def propose(self,*,base_ref,decision,explanation,body=None,scope=None,open_question='',metadata=None,idempotency_key,actor=ACTOR):
        if metadata is not None and (not isinstance(metadata,dict) or set(metadata)-{'title','intro','byline','entry_type','date'}):raise ValueError('explicit author metadata allowlist required')
        if decision not in DECISIONS:raise ValueError('explicit supported review decision required')
        bounded(explanation,'review explanation',True);bounded(open_question,'open question')
        if body is not None:bounded(body,'body')
        if scope is not None:bounded(scope,'scope')
        opened=self.open(base_ref);base=opened['record']
        request={'operation':'authoring.propose','base_ref':base_ref,'decision':decision,'explanation':explanation,'body':body,'scope':scope,'open_question':open_question,'metadata':metadata,'actor':actor}
        def apply():
            working=base
            if (opened['public'] or base['kind'] not in ('entry','claim_revision','thread')) and decision!='maintain':
                if base['kind']=='entry':
                    payload={'bodyMarkdown':opened['body'],'open_question':opened['open_question'],'source_basis_ref':base_ref,'public_metadata':{k:base['payload'][k] for k in PUBLIC_METADATA if k in base['payload']},'authored_private':True}
                    working=record('entry',{k:base[k] for k in ('entry_type','title','byline','date','intro','body_file')}|{'payload':payload,'references':base.get('references',[])})
                elif base['kind']=='claim_revision':working=record('claim_revision',{k:base[k] for k in ('title','byline','claim','scope','scope_binding')}|{'payload':{'source_basis_ref':base_ref,'authored_private':True}})
                else:working=record('thread',{'title':'Review: '+base.get('title',base['id']),'byline':'Local researcher','status':'open','payload':{'note':opened['body'],'source_basis_ref':base_ref}})
                self.repo._apply(command(working,actor=actor))
            if decision=='maintain':change={'mode':'no-change','reason':explanation}
            else:
                payload={**working.get('payload',{}),'open_question':open_question,'review_explanation':explanation,'review_basis_ref':base_ref,'review_decision':decision}
                new_body=opened['body'] if body is None else body
                payload['bodyMarkdown']=new_body
                fields={'payload':payload,**(metadata or {})}
                if working['kind']=='claim_revision':
                    fields['claim']=new_body
                    if scope is not None:
                        if not scope.strip():raise ValueError('claim scope cannot be empty')
                        fields.update(scope=scope,scope_binding=scope)
                elif scope is not None:payload['scope']=scope
                if decision=='needs-experiment':
                    if not open_question.strip():raise ValueError('an unexecuted design needs an open diagnostic question')
                    design=record('design',{'title':working.get('title','Review')+' — diagnostic proposal','body':explanation+'\n\nUnresolved question: '+open_question+'\n\nBasis: '+json.dumps(base_ref,ensure_ascii=False),'status':'proposed-not-run'})
                    self.repo._apply(command(design,actor=actor));payload['design_ref']=ref(design)
                change={'mode':'replace-fields','fields':fields}
            target='public-corpus' if opened['public'] and working is base else 'canonical-draft' if working['kind'] in ('entry','claim_revision') else 'private-thread'
            changeset=self.revisions._create([{'id':'review','target':target,'base_ref':ref(working),'change':change}],actor)
            return {'changeset':changeset,'working_ref':ref(working),'source_base_ref':base_ref,'decision':decision,'public_files_written':False}
        return remember(self.repo,idempotency_key,request,apply)
    def publication_plan(self,*,entry_ref,public_id,base_commit,rights,idempotency_key,include_metadata=True,include_text=True,attachments=(),actor=ACTOR):
        entry=self.arguments.resolve(entry_ref)
        if entry['kind']!='entry' or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',public_id):raise ValueError('selected Entry and portable public id required')
        opened=self.open(entry_ref)
        if not opened['body'].strip():raise ValueError('finish explicit manuscript text before publication selection')
        if type(include_metadata) is not bool or type(include_text) is not bool or len(attachments)>24:raise ValueError('bounded explicit release selection required')
        request={'operation':'authoring.publication','entry_ref':entry_ref,'public_id':public_id,'base_commit':base_commit,'rights':rights,'include_metadata':include_metadata,'include_text':include_text,'attachments':list(attachments),'actor':actor}
        def apply():
            body_path='study/entries/'+public_id+'.md';items=[];selected=[entry_ref]
            def artifact(raw,role):
                blob=self.repo.put_blob(raw);value=record('artifact',{'media_type':'application/json' if role=='dataset' else 'text/markdown; charset=utf-8','byte_length':len(raw),'artifact_digest':blob,'storage':{'kind':'blob','locator':blob},'role':role,'visibility':'public-candidate','obtained_at':now()})
                self.repo._apply(command(value,actor=actor));return value
            def item(entity,a,path,item_rights):return {'entity_ref':entity,'artifact_ref':ref(a),'public_path':path,'rights':item_rights,'reviewed_digest':a['artifact_digest'],'release_review':{'actor':actor,'at':now(),'rationale':'Explicit selection of these exact bytes and declared rights; preparation only.'}}
            if include_text:
                a=artifact(opened['body'].encode(),'authored');items.append(item(entry_ref,a,body_path,rights))
            if include_metadata:
                supplied=entry['payload'].get('public_metadata',{})
                metadata={**{k:supplied[k] for k in PUBLIC_METADATA if k in supplied},'id':public_id,'kind':entry['entry_type'],'title':entry['title'],'byline':entry['byline'],'date':entry['date'],'intro':entry['intro'],'bodyFile':'entries/'+public_id+'.md'}
                a=artifact((json.dumps(metadata,ensure_ascii=False,indent=2)+'\n').encode(),'dataset');items.append(item(entry_ref,a,'study/entries/'+public_id+'.json',rights))
            for selection in attachments:
                if set(selection)!={'artifact_ref','public_path','rights'}:raise ValueError('attachment needs explicit exact ref, public path and its own rights')
                a=self.arguments.resolve(selection['artifact_ref'])
                if a['kind']!='artifact' or a['visibility'] not in ('public-candidate','public'):raise ValueError('attachment must already be explicitly reviewed public candidate')
                selected.append(ref(a));items.append(item(ref(a),a,selection['public_path'],selection['rights']))
            # A draft may retain its original path; the release Entry is a new immutable
            # explicitly selected identity bound to the chosen public body path.
            release=record('entry',{k:entry[k] for k in ('entry_type','title','byline','date','intro','references') if k in entry}|{'body_file':body_path,'payload':{**entry['payload'],'release_of':entry_ref}})
            self.repo._apply(command(release,actor=actor));selected[0]=ref(release)
            for value in items:
                if value['entity_ref']==entry_ref:value['entity_ref']=ref(release)
            manifest=self.publication._prepare(selected,items,base_commit=base_commit,actor=actor)
            for changeset in self.repo.list('changeset'):
                if any(i['application_state'] in ('applied','checked-unchanged') and i.get('result_ref',i['base_ref'])==entry_ref for i in changeset['items']):
                    updated=revise(changeset,publication_refs=[*changeset['publication_refs'],ref(manifest)])
                    self.repo._apply(command(updated,previous=changeset,actor=actor))
            result={'manifest':manifest,'preview':self.publication.preview(ref(manifest)),'draft_ref':entry_ref,'git_execution':False}
            return result
        return remember(self.repo,idempotency_key,request,apply)
    def patch(self,manifest_ref):
        preview=self.publication.preview(manifest_ref);base=preview['base_commit']
        git(self.project,'rev-parse',base+'^{commit}')
        output=[]
        for item in preview['files']:
            path=item['path'];path_inside(self.project,path)
            before=subprocess.run(['git','show',base+':'+path],cwd=self.project,capture_output=True)
            old=before.stdout if before.returncode==0 else b''
            after=base64.b64decode(item['content_base64'])
            if old==after and before.returncode==0:continue
            with tempfile.TemporaryDirectory(prefix='review-patch-',dir=self.repo.root) as temp:
                temporary=Path(temp);(temporary/'before').write_bytes(old);(temporary/'after').write_bytes(after)
                result=subprocess.run(['git','diff','--no-index','--binary','--src-prefix=a/','--dst-prefix=b/','--','before' if before.returncode==0 else '/dev/null','after'],cwd=temporary,capture_output=True)
                if result.returncode not in (0,1):raise ValueError('selected patch encoding failed')
                for line in result.stdout.decode().splitlines(True):
                    if line.startswith('diff --git '):line='diff --git '+json.dumps('a/'+path,ensure_ascii=False)+' '+json.dumps('b/'+path,ensure_ascii=False)+'\n'
                    elif line.startswith('--- '):line='--- '+('/dev/null' if before.returncode else json.dumps('a/'+path,ensure_ascii=False))+'\n'
                    elif line.startswith('+++ '):line='+++ '+json.dumps('b/'+path,ensure_ascii=False)+'\n'
                    output.append(line)
        return {'manifest_ref':manifest_ref,'base_commit':base,'patch':''.join(output),'status':'reviewable-not-applied','empty':not output,'git_execution':False}
