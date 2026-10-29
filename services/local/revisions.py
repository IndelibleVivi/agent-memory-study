"""Canonical ChangeSets plus recoverable per-owner operational apply units."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
import subprocess
import uuid
from schemas.validate import check_structure
from .arguments import ArgumentService,human
from .records import ACTOR,command,record,ref,revise
from .repository import encoded,now

REVISIONS_MIGRATION_SQL=(
 'CREATE TABLE revision_reviews (changeset_revision TEXT NOT NULL,item_id TEXT NOT NULL,actor TEXT NOT NULL,rationale TEXT NOT NULL,decided_at TEXT NOT NULL,PRIMARY KEY(changeset_revision,item_id))',
 'CREATE TABLE revision_units (id TEXT PRIMARY KEY,idempotency_key TEXT NOT NULL UNIQUE,payload TEXT NOT NULL,receipt TEXT NOT NULL)',
)

def git(project,*args):
    return subprocess.run(['git',*args],cwd=project,check=True,capture_output=True,text=True).stdout.strip()
def path_inside(root,path):
    if not isinstance(path,str) or any(ord(c)<32 or c=='\\' for c in path):raise ValueError('invalid portable public path')
    p=Path(path)
    if p.is_absolute() or any(x in ('','..','.') for x in p.parts) or not p.parts:raise ValueError('normalized relative path required')
    if p.as_posix()!=path:raise ValueError('path is not normalized')
    full=(Path(root)/p).resolve()
    if not full.is_relative_to(Path(root).resolve()):raise ValueError('path escapes project')
    return full

def entry_body_path(root,body_file):
    path=body_file if body_file.startswith('study/') else 'study/'+body_file
    full=path_inside(root,path)
    if not path.startswith('study/') or full.suffix!='.md':raise ValueError('entry body must be selected study Markdown')
    return path

def application_state(items):
    states={i['application_state'] for i in items if i['review_state']=='accepted'}
    if 'conflict' in states:return 'conflict'
    if not states or 'not-applied' in states:return 'not-applied'
    if states=={'checked-unchanged'}:return 'checked-unchanged'
    return 'applied'
def review_state(items):
    states={i['review_state'] for i in items}
    if states<= {'accepted','rejected'}:return 'accepted' if 'accepted' in states else 'rejected'
    return 'reviewing' if states!={'proposed'} else 'proposed'

class RevisionService:
    def __init__(self,repo,project,public_records=(),*,review_authorizer=None):
        self.repo=repo;self.project=Path(project).resolve();self.arguments=ArgumentService(repo,public_records,review_authorizer=review_authorizer)
    def _create(self,items,actor=ACTOR):
        if not items or len({i['id'] for i in items})!=len(items):raise ValueError('nonempty unique items required')
        accepted=[]
        for i in items:
            self.arguments.resolve(i['base_ref'])
            accepted.append({'id':i['id'],'target':i['target'],'base_ref':i['base_ref'],'change':i['change'],'review_state':'proposed','application_state':'not-applied'})
        value=record('changeset',{'review_state':'proposed','application_state':'not-applied','items':accepted,'publication_refs':[]})
        self.repo._apply(command(value,actor=actor));return value
    def create(self,items,*,actor=ACTOR,idempotency_key=None):
        if idempotency_key:
            from .intake import remember
            return remember(self.repo,idempotency_key,{'operation':'revision.create','items':items,'actor':actor},lambda:self._create(items,actor))
        with self.repo.transaction():return self._create(items,actor)
    def review(self,id,item_id,decision,rationale,*,expected_revision,actor=ACTOR,delegation_ref=None,idempotency_key=None):
        payload={'operation':'revision.review','id':id,'item_id':item_id,'decision':decision,'rationale':rationale,'expected_revision':expected_revision,'actor':actor,**({'delegation_ref':delegation_ref} if delegation_ref else {})}
        def apply():
            if decision not in ('accepted','rejected','paused') or not rationale.strip():raise ValueError('explicit item review and reason required')
            old=self.repo.load('changeset',id)
            if old['revision']!=expected_revision:raise ValueError('stale changeset review')
            authorization=self.arguments.authorize(actor,'revision.review',ref(old),rationale,delegation_ref)
            items=json.loads(encoded(old['items']));found=False
            for i in items:
                if i['id']==item_id:
                    if i['application_state'] in ('applied','checked-unchanged'):raise ValueError('applied history cannot be re-reviewed in place; create a new changeset')
                    i['review_state']=decision;found=True
            if not found:raise ValueError('unknown item')
            new=revise(old,items=items,review_state=review_state(items),application_state=application_state(items))
            self.repo._apply(command(new,previous=old,actor=actor))
            self.repo.db.execute('INSERT INTO revision_reviews VALUES (?,?,?,?,?)',(new['revision'],item_id,encoded(authorization),rationale,now()))
            return new
        if idempotency_key:
            from .intake import remember
            return remember(self.repo,idempotency_key,payload,apply)
        with self.repo.transaction():return apply()
    def pause(self,id,*,expected_revision,actor=ACTOR,delegation_ref=None):
        old=self.repo.load('changeset',id)
        if old['revision']!=expected_revision:raise ValueError('stale changeset')
        authorization=self.arguments.authorize(actor,'revision.pause',ref(old),'Pause only; accepted item decisions retained.',delegation_ref)
        new=revise(old,review_state='paused')
        with self.repo.transaction():
            self.repo._apply(command(new,previous=old,actor=actor));self.repo.db.execute('INSERT INTO revision_reviews VALUES (?,?,?,?,?)',(new['revision'],'*',encoded(authorization),authorization['rationale'],now()))
        return new
    def _unit_previous(self,key,payload):
        old=self.repo.db.execute('SELECT payload,receipt FROM revision_units WHERE idempotency_key=?',(key,)).fetchone()
        if old:
            saved=json.loads(old['payload'])
            if encoded(saved.get('request',saved))!=encoded(payload):raise ValueError('unit idempotency conflict')
            if saved.get('schema'):check_structure(saved,'OperationalApplyUnit')
            return json.loads(old['receipt'])
    def _store(self,key,payload,base,selected,result,authorization):
        unit={'schema':'ams-operational-apply-unit/1','id':result['id'],'idempotency_key':key,'request':payload,'changeset_ref':ref(base),'base_refs':[i['base_ref'] for i in selected],'created_at':now()}
        result.update(schema='ams-operational-apply-receipt/1',authorization=authorization,recorded_at=now(),item_results=[{'item_id':i['id'],'state':i['application_state'],**({'result_ref':i['result_ref']} if 'result_ref' in i else {})} for i in selected])
        check_structure(unit,'OperationalApplyUnit');check_structure(result,'OperationalApplyReceipt')
        self.repo.db.execute('INSERT INTO revision_units VALUES (?,?,?,?)',(result['id'],key,encoded(unit),encoded(result)))
    def units(self,changeset_id):
        with self.repo.lock:
            rows=list(self.repo.db.execute('SELECT payload,receipt FROM revision_units'))
        values=[]
        for row in rows:
            unit,result=json.loads(row['payload']),json.loads(row['receipt'])
            if result['changeset_id']!=changeset_id:continue
            if unit.get('schema'):check_structure(unit,'OperationalApplyUnit')
            if result.get('schema'):check_structure(result,'OperationalApplyReceipt')
            elif result.get('receipt',{}):check_structure(result['receipt'],'OperationalApplyReceipt')
            values.append(result)
        return values
    def apply_db(self,id,item_ids,*,expected_revision,idempotency_key,actor=ACTOR,delegation_ref=None):
        if not isinstance(idempotency_key,str) or not 1<=len(idempotency_key)<=200:raise ValueError('invalid unit idempotency key')
        authorization=self.arguments.authorize(actor,'revision.apply',{'kind':'changeset','id':id,'revision':expected_revision},'Apply explicitly accepted selected items under one database owner.',delegation_ref)
        payload={'changeset_id':id,'item_ids':item_ids,'expected_revision':expected_revision,'owner':'db','actor':actor,**({'delegation_ref':authorization['delegation_ref']} if 'delegation_ref' in authorization else {})}
        if not item_ids or len(set(item_ids))!=len(item_ids):raise ValueError('unique selected items required')
        with self.repo.transaction():
            prior=self._unit_previous(idempotency_key,payload)
            if prior:return prior
            old=self.repo.load('changeset',id)
            if old['revision']!=expected_revision:raise ValueError('stale changeset apply')
            if old['review_state']=='paused':raise ValueError('paused changeset must resume review before apply')
            items=json.loads(encoded(old['items']));selected=[i for i in items if i['id'] in item_ids]
            if len(selected)!=len(item_ids):raise ValueError('unknown selected item')
            prepared=[];conflicts=[];targets=set()
            for i in selected:
                if i['review_state']!='accepted' or i['application_state']!='not-applied':raise ValueError('item not accepted/unapplied')
                if i['target']=='public-corpus':
                    if isinstance(i['change'],dict) and i['change'].get('mode')=='no-change':
                        self.arguments.resolve(i['base_ref']);continue
                    raise ValueError('public corpus has Git owner; use prepared patch')
                base=i['base_ref'];address=(base['kind'],base['id'])
                if address in targets:raise ValueError('two selected items modify same target')
                targets.add(address);current=self.repo.load(*address)
                if current['revision']!=base['revision']:conflicts.append(i['id']);continue
                change=i['change']
                if not isinstance(change,dict):raise ValueError('structured accepted change required for apply')
                if change['mode']=='no-change':continue
                if change['mode']!='replace-fields':raise ValueError('unsupported database change')
                fields=change['fields']
                if not fields or set(fields)&{'schema','kind','id','revision','state_revision','content_digest'}:raise ValueError('invalid replacement fields')
                if current['kind']=='excerpt' and set(fields)&{'target_ref','representation_ref','selector'}:raise ValueError('old excerpt basis must not be rebound')
                if all(k in current and current[k]==v for k,v in fields.items()):
                    i['change']={'mode':'no-change','reason':'Accepted replacement exactly equals fixed base; original fields remain in the apply unit changeset_ref.'}
                    continue
                new=revise(current,**fields);prepared.append((i,current,new))
            if conflicts:
                for i in selected:
                    if i['id'] in conflicts:i['application_state']='conflict'
                new=revise(old,items=items,application_state=application_state(items));self.repo._apply(command(new,previous=old,actor=actor))
                result={'id':'unit:'+uuid.uuid4().hex,'changeset_id':id,'owner':'db','state':'conflict','conflicts':conflicts,'applied_refs':[],'changeset_ref':ref(new)}
            else:
                applied={i['id']:new for i,previous,new in prepared}
                for i,previous,new in prepared:self.repo._apply(command(new,previous=previous,actor=actor))
                for i in selected:
                    if i['id'] in applied:i.update(application_state='applied',result_ref=ref(applied[i['id']]))
                    else:i['application_state']='checked-unchanged'
                updated=revise(old,items=items,application_state=application_state(items));self.repo._apply(command(updated,previous=old,actor=actor))
                result={'id':'unit:'+uuid.uuid4().hex,'changeset_id':id,'owner':'db','state':application_state(selected),'conflicts':[],'applied_refs':[ref(v) for v in applied.values()],'changeset_ref':ref(updated)}
            self._store(idempotency_key,payload,old,selected,result,authorization)
        return result
    def prepare_git(self,id,item_ids,files,*,base_commit,expected_revision,idempotency_key,actor=ACTOR,delegation_ref=None):
        """Create private byte-bound patch plan; never mutate production Git."""
        if not re.fullmatch('[0-9a-f]{40}',base_commit):raise ValueError('exact Git base required')
        base=self.arguments.resolve({'kind':'changeset','id':id,'revision':expected_revision})
        authorization=self.arguments.authorize(actor,'revision.prepare-git',ref(base),'Prepare explicitly selected byte-bound public patch; no Git execution.',delegation_ref)
        with self.repo.lock:prior=self.repo.db.execute('SELECT payload,receipt FROM revision_units WHERE idempotency_key=?',(idempotency_key,)).fetchone()
        if prior:
            unit=json.loads(prior['payload']);check_structure(unit,'OperationalApplyUnit');request=unit['request']
            if (request['changeset_id'],request['item_ids'],request['base_commit'],request['expected_revision'],request['actor'],request.get('delegation_ref'),{p['path']:p['after'] for p in request['patches']})!=(id,item_ids,base_commit,expected_revision,actor,authorization.get('delegation_ref'),files):raise ValueError('unit idempotency conflict')
            return json.loads(prior['receipt'])
        old=self.repo.load('changeset',id)
        if old['revision']!=expected_revision:raise ValueError('stale changeset')
        selected=[i for i in old['items'] if i['id'] in item_ids]
        if not selected or len(selected)!=len(set(item_ids)):raise ValueError('invalid selected items')
        if any(i['target']!='public-corpus' or i['review_state']!='accepted' or i['application_state']!='not-applied' for i in selected):raise ValueError('accepted unapplied Git-owner items required')
        if all(isinstance(i['change'],dict) and i['change']['mode']=='no-change' for i in selected):
            if files:raise ValueError('unchanged review cannot create patch')
        elif not files:raise ValueError('modified Git unit needs explicit files')
        patches=[]
        for path,text in files.items():
            full=path_inside(self.project,path)
            if not path.startswith(('study/','research/','docs/')) or not isinstance(text,str):raise ValueError('unsupported public patch path')
            try:before=git(self.project,'show',base_commit+':'+path)+'\n'
            except subprocess.CalledProcessError:raise ValueError('base path missing; creation needs separate operation') from None
            # git helper strips terminal LF; preserve exact base via byte stdout below.
            before=subprocess.run(['git','show',base_commit+':'+path],cwd=self.project,check=True,capture_output=True).stdout.decode()
            patches.append({'path':path,'before':before,'after':text,'before_digest':hashlib.sha256(before.encode()).hexdigest(),'after_digest':hashlib.sha256(text.encode()).hexdigest()})
        payload={'changeset_id':id,'owner':'git','changeset_ref':ref(old),'item_ids':item_ids,'base_commit':base_commit,'patches':patches,'expected_revision':expected_revision,'actor':actor,**({'delegation_ref':authorization['delegation_ref']} if 'delegation_ref' in authorization else {})}
        with self.repo.transaction():
            prior=self._unit_previous(idempotency_key,payload)
            if prior:return prior
            result={**payload,'id':'unit:'+uuid.uuid4().hex,'state':'prepared','application_state':'not-applied','receipt':None}
            unit={'schema':'ams-operational-apply-unit/1','id':result['id'],'idempotency_key':idempotency_key,'request':payload,'changeset_ref':ref(old),'base_refs':[i['base_ref'] for i in selected],'created_at':now()}
            check_structure(unit,'OperationalApplyUnit');result['plan']=unit
            self.repo.db.execute('INSERT INTO revision_units VALUES (?,?,?,?)',(result['id'],idempotency_key,encoded(unit),encoded(result)))
        return result
    def record_git_unit(self,unit_id,receipt,*,actor=ACTOR,delegation_ref=None):
        with self.repo.transaction():
            row=self.repo.db.execute('SELECT payload,receipt FROM revision_units WHERE id=?',(unit_id,)).fetchone()
            if row is None:raise ValueError('unknown unit')
            unit=json.loads(row['payload']);plan=unit.get('request',unit);saved=json.loads(row['receipt'])
            if unit.get('schema'):check_structure(unit,'OperationalApplyUnit')
            authorization=self.arguments.authorize(actor,'revision.record-git',plan['changeset_ref'],'Record concrete owner result without executing Git.',delegation_ref)
            if plan['owner']!='git':raise ValueError('wrong unit owner')
            if saved.get('receipt') is not None:
                if saved.get('owner_result',saved['receipt'])!=receipt:raise ValueError('unit receipt immutable')
                return saved
            if receipt.get('base_commit')!=plan['base_commit'] or receipt.get('state') not in ('applied','conflict','checked-unchanged'):raise ValueError('invalid owner receipt')
            if receipt['state']=='applied':
                if not receipt.get('commit'):raise ValueError('Git apply needs concrete commit receipt')
                git(self.project,'merge-base','--is-ancestor',plan['base_commit'],receipt['commit'])
                for patch in plan['patches']:
                    actual=subprocess.run(['git','show',receipt['commit']+':'+patch['path']],cwd=self.project,check=True,capture_output=True).stdout
                    if hashlib.sha256(actual).hexdigest()!=patch['after_digest']:raise ValueError('Git receipt bytes differ from reviewed patch')
            old=self.repo.load('changeset',plan['changeset_id']);items=json.loads(encoded(old['items']))
            original=self.arguments.resolve(plan['changeset_ref']);original_items={i['id']:i for i in original['items']}
            for i in items:
                if i['id'] in plan['item_ids']:
                    if any(i[k]!=original_items[i['id']][k] for k in ('base_ref','change','review_state')):raise ValueError('selected item changed after Git plan; reconcile before receipt')
                    if receipt['state']=='checked-unchanged' and (not isinstance(i['change'],dict) or i['change'].get('mode')!='no-change'):raise ValueError('unchanged receipt requires accepted no-change intent')
                    if i['review_state']!='accepted':raise ValueError('accepted decision moved; reconcile unit')
                    if receipt['state']=='applied':
                        results=receipt.get('result_refs',{})
                        if i['id'] not in results:raise ValueError('applied public item needs exact result_ref')
                        before,after=i['base_ref'],results[i['id']]
                        if (before['kind'],before['id'])!=(after['kind'],after['id']) or before['revision']==after['revision']:raise ValueError('invalid applied result identity')
                        self.arguments.resolve(after)
                        i['result_ref']=after
                    i['application_state']=receipt['state']
            new=revise(old,items=items,application_state=application_state(items));self.repo._apply(command(new,previous=old,actor=actor))
            selected=[i for i in items if i['id'] in plan['item_ids']]
            operational={'schema':'ams-operational-apply-receipt/1','id':unit_id,'changeset_id':old['id'],'owner':'git','state':receipt['state'],'conflicts':[i['id'] for i in selected if i['application_state']=='conflict'],'applied_refs':[i['result_ref'] for i in selected if i.get('result_ref')],
                'changeset_ref':ref(new),'item_results':[{'item_id':i['id'],'state':i['application_state'],**({'result_ref':i['result_ref']} if i.get('result_ref') else {})} for i in selected],'authorization':authorization,'recorded_at':now(),'base_commit':plan['base_commit'],**({k:receipt[k] for k in ('commit','result_refs') if k in receipt})}
            check_structure(operational,'OperationalApplyReceipt')
            saved.update(state=receipt['state'],application_state=receipt['state'],receipt=operational,owner_result=receipt,result_changeset_ref=ref(new))
            self.repo.db.execute('UPDATE revision_units SET receipt=? WHERE id=?',(encoded(saved),unit_id))
        return saved
