"""Private release selection, explicit public projection and independent delivery."""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
from schemas.validate import content_digest,content_fields,validate_entity,walk_exact_refs,exact_ref,check_structure
from .arguments import ArgumentService,human
from .records import ACTOR,command,identity,ref
from .repository import encoded,now
from .revisions import git,path_inside,entry_body_path

PUBLICATION_MIGRATION_SQL=(
 'CREATE TABLE publication_selections (manifest_revision TEXT PRIMARY KEY,selection TEXT NOT NULL)',
 'CREATE TABLE publication_deliveries (seq INTEGER PRIMARY KEY AUTOINCREMENT,manifest_revision TEXT NOT NULL,delivery TEXT NOT NULL)',
 'CREATE TABLE publication_executions (manifest_revision TEXT PRIMARY KEY,receipt TEXT NOT NULL)',
)
FIELDS={
 'entry':['kind','id','revision','entry_type','title','byline','date','intro','body_file','references'],
 'claim_revision':['kind','id','revision','title','byline','claim','scope','scope_binding'],
 'source_work':['kind','id','revision','title','work_type','authors','year','identifiers'],
 'source_revision':['kind','id','revision','work_ref','identity','predecessor_ref'],
 'artifact':['kind','id','revision','media_type','byte_length','artifact_digest','role'],
 'analysis':['kind','id','revision','run_refs','method','scope','result','observation_refs'],
 'observation':['kind','id','revision','run_ref','scope','statement','basis_refs'],
}

def scan_public(files,canaries=()):
    hits=[]
    needles=[(c.encode() if isinstance(c,str) else c) for c in canaries]
    for path,raw in files.items():
        for needle in needles:
            if needle and needle in raw:hits.append({'path':path,'reason':'private-canary'})
        if any(v in raw for v in (b'file://',b'/Users/',b'/home/',b'/Volumes/',b'/private/')):hits.append({'path':path,'reason':'local-private-path'})
    if hits:raise ValueError('public output contains private marker/path: '+encoded(hits))
    return {'files_checked':len(files),'status':'passed'}

class PublicationService:
    def __init__(self,repo,project,public_records=(),*,execution_gate=None,review_authorizer=None):
        self.repo=repo;self.project=Path(project).resolve();self.arguments=ArgumentService(repo,public_records,review_authorizer=review_authorizer);self.execution_gate=execution_gate
    def prepare(self,selected_refs,items,*,base_commit,actor=ACTOR,canaries=(),delegation_ref=None):
        with self.repo.transaction():return self._prepare(selected_refs,items,base_commit=base_commit,actor=actor,canaries=canaries,delegation_ref=delegation_ref)
    def _prepare(self,selected_refs,items,*,base_commit,actor=ACTOR,canaries=(),delegation_ref=None):
        if not re.fullmatch('[0-9a-f]{40}',base_commit):raise ValueError('exact base commit required')
        if not selected_refs or len({exact_ref(r) for r in selected_refs})!=len(selected_refs):raise ValueError('unique selected refs required')
        authorization=self.arguments.authorize(actor,'publication.prepare',selected_refs[0],'Prepare only the explicitly selected reviewed public bytes; no execution authority.',delegation_ref)
        selected={exact_ref(r):self.arguments.resolve(r) for r in selected_refs}
        if any(v['kind'] not in FIELDS or v.get('visibility')=='private' for v in selected.values()):raise ValueError('private/unpublished kind cannot enter public projection')
        public_keys=set(self.arguments.public)
        projections=[]
        for value in selected.values():
            projection={k:value[k] for k in FIELDS[value['kind']] if k in value}
            for dependency in walk_exact_refs(projection):
                if exact_ref(dependency) not in selected and exact_ref(dependency) not in public_keys:raise ValueError('selected public dependency closure is incomplete')
            projections.append(projection)
        paths=set();files={};reviews=[]
        for item in items:
            if set(item)!={'entity_ref','artifact_ref','public_path','rights','reviewed_digest','release_review'}:raise ValueError('explicit reviewed publication item fields required')
            if exact_ref(item['entity_ref']) not in selected:raise ValueError('publication entity not selected')
            artifact=self.arguments.resolve(item['artifact_ref'])
            if artifact['kind']!='artifact' or artifact['visibility'] not in ('public-candidate','public'):raise ValueError('artifact is not reviewed public candidate')
            check_structure(item['release_review'],'Review')
            authorized_review=self.arguments.authorize(item['release_review']['actor'],'publication.release',item['artifact_ref'],item['release_review']['rationale'],item['release_review'].get('delegation_ref'))
            if not item['release_review'].get('rationale','').strip() or not item['rights'].get('basis','').strip() or not item['rights'].get('attribution','').strip() or not item['rights'].get('license_or_permission','').strip():raise ValueError('rights and release review rationale required')
            if item['reviewed_digest']!=artifact['artifact_digest']:raise ValueError('release review binds different bytes')
            path=item['public_path'];path_inside(self.project,path)
            if not path.startswith(('study/','research/','docs/','assets/')) or path.startswith('assets/materials-data'):raise ValueError('unsupported publication output path')
            if path in paths or any(part.startswith('.') for part in Path(path).parts):raise ValueError('duplicate or hidden public path')
            raw=self.repo.read_blob(artifact['artifact_digest'])
            if len(raw)!=artifact['byte_length']:raise ValueError('artifact bytes differ')
            files[path]=raw;paths.add(path);reviews.append({**item,'release_review':authorized_review})
        if not files:raise ValueError('explicit public bytes required')
        for value in selected.values():
            if value['kind']=='entry' and value['body_file']:
                body=entry_body_path(self.project,value['body_file'])
                if body not in files and not (self.project/body).is_file():raise ValueError('entry body dependency missing')
        canaries=(*canaries,str(self.repo.root))
        scan_public({**files,'selection.json':encoded({'objects':projections,'rights':[i['rights'] for i in items]}).encode()},canaries)
        rev=identity('rev');manifest={'schema':'ams-publication-manifest/1','kind':'publication_manifest','id':identity('publication_manifest'),'revision':rev,'state_revision':rev,
                  'base_git_commit':base_commit,'selected_refs':selected_refs,'visibility':'private','prepared_by':actor}
        manifest['content_digest']=content_digest(manifest,content_fields(manifest));validate_entity(manifest)
        selection={'items':reviews,'public_objects':projections,'canaries':list(canaries),'prepared_at':now(),'authorization':authorization}
        self.repo._apply(command(manifest,actor=actor))
        self.repo.db.execute('INSERT INTO publication_selections VALUES (?,?)',(rev,encoded(selection)))
        return manifest
    def _selection(self,manifest_ref):
        m=self.arguments.resolve(manifest_ref)
        if m['kind']!='publication_manifest':raise ValueError('expected private PublicationManifest')
        with self.repo.lock:row=self.repo.db.execute('SELECT selection FROM publication_selections WHERE manifest_revision=?',(m['revision'],)).fetchone()
        if row is None:raise ValueError('selection not available')
        return m,json.loads(row[0])
    def preview(self,manifest_ref):
        m,s=self._selection(manifest_ref);files={}
        for item in s['items']:
            a=self.arguments.resolve(item['artifact_ref']);files[item['public_path']]=self.repo.read_blob(a['artifact_digest'])
        scan_public({**files,'public-objects.json':encoded({'objects':s['public_objects'],'rights':[i['rights'] for i in s['items']]}).encode()},s['canaries'])
        return {'manifest_ref':manifest_ref,'base_commit':m['base_git_commit'],'files':[{'path':p,'byte_length':len(v),'digest':'sha256:'+hashlib.sha256(v).hexdigest(),'content_base64':base64.b64encode(v).decode()} for p,v in sorted(files.items())],
                'public_objects':s['public_objects'],'status':'reviewable-not-published','rights':[[i['public_path'],i['rights']] for i in s['items']]}
    def public_projection(self,manifest_ref):
        preview=self.preview(manifest_ref)
        return {'schema':'ams-public-selection/1','objects':preview['public_objects'],'files':preview['files'],'attributions':[{'path':path,'attribution':rights['attribution'],'license_or_permission':rights['license_or_permission']} for path,rights in preview['rights']],'scope':'reviewed public selection; compiler remains PublicCorpusManifest owner'}
    def record_delivery(self,manifest_ref,delivery,*,actor=ACTOR,delegation_ref=None,idempotency_key=None):
        self._selection(manifest_ref)
        authorization=self.arguments.authorize(actor,'publication.record-delivery',manifest_ref,'Record supplied repository/build/site observation; not a network verification.',delegation_ref)
        if set(delivery)-{'local_commit','repository','build','site','receipt','observed_at'}:raise ValueError('unknown delivery fields')
        repo,build,site=(delivery[k] for k in ('repository','build','site'))
        if repo['state'] not in ('not-pushed','visible') or build['state'] not in ('not-built','failed','succeeded') or site['state'] not in ('not-requested','pending','failed','active'):raise ValueError('invalid delivery state')
        if repo['state']=='visible' and (not re.fullmatch('[0-9a-f]{40}',repo.get('commit','')) or not repo.get('url') or not repo.get('observed_at')):raise ValueError('repository visibility needs concrete observation')
        if site['state']=='active':
            if build['state']!='succeeded' or repo['state']!='visible':raise ValueError('active site requires matching visible successful build')
            if any(site.get(k)!=build.get(k) or site.get(k) is None for k in ('source_commit','artifact_digest')) or repo['commit']!=site['source_commit']:raise ValueError('site source/build mismatch')
            if not all(site.get(k) for k in ('deployment_id','url','verified_at')):raise ValueError('active site requires observed receipt')
        def apply():
            receipt={'schema':'ams-publication-delivery/1','id':identity('delivery'),'manifest_ref':manifest_ref,'delivery':delivery,'recorded_at':now(),'authorization':authorization,'evidence_status':'operator-supplied-observation; not independently network-verified'}
            check_structure(receipt,'PublicationDelivery')
            self.repo.db.execute('INSERT INTO publication_deliveries(manifest_revision,delivery) VALUES (?,?)',(manifest_ref['revision'],encoded(receipt)));return receipt
        if idempotency_key:
            from .intake import remember
            return remember(self.repo,idempotency_key,{'operation':'publication.record-delivery','manifest_ref':manifest_ref,'delivery':delivery,'actor':actor,**({'delegation_ref':delegation_ref} if delegation_ref else {})},apply)
        with self.repo.transaction():return apply()
    def deliveries(self,manifest_ref):
        self._selection(manifest_ref)
        with self.repo.lock:values=[json.loads(r[0]) for r in self.repo.db.execute('SELECT delivery FROM publication_deliveries WHERE manifest_revision=? ORDER BY seq',(manifest_ref['revision'],))]
        for value in values:
            if value.get('schema'):check_structure(value,'PublicationDelivery')
        return values
    def current_site(self):
        with self.repo.lock:
            for row in self.repo.db.execute('SELECT delivery FROM publication_deliveries ORDER BY seq DESC'):
                receipt=json.loads(row[0])
                if receipt.get('schema'):check_structure(receipt,'PublicationDelivery')
                if receipt['delivery']['site']['state']=='active':return receipt
        return None
    def reconcile_commit(self,manifest_ref,commit):
        """Read-only Git observation after commit ack loss; no new Git mutation."""
        preview=self.preview(manifest_ref)
        if git(self.project,'rev-parse',commit+'^')!=preview['base_commit']:raise ValueError('observed commit parent differs from reviewed base')
        allowed={f['path'] for f in preview['files']}
        if set(git(self.project,'diff-tree','--no-commit-id','--name-only','-r',commit).splitlines())-allowed:raise ValueError('observed commit contains unselected files')
        for f in preview['files']:
            raw=subprocess.run(['git','show',commit+':'+f['path']],cwd=self.project,check=True,capture_output=True).stdout
            if 'sha256:'+hashlib.sha256(raw).hexdigest()!=f['digest']:raise ValueError('observed commit differs from reviewed bytes')
        result={'state':'committed','base_commit':preview['base_commit'],'commit':commit,'branch':git(self.project,'symbolic-ref','--short','HEAD'),'repository_visible':False,'site_active':False,'reconciled_after_ack_loss':True}
        with self.repo.transaction():
            old=self.repo.db.execute('SELECT receipt FROM publication_executions WHERE manifest_revision=?',(manifest_ref['revision'],)).fetchone()
            if old is None or json.loads(old[0])['state']!='preparing':raise ValueError('only an unresolved prepared execution can be reconciled')
            self.repo.db.execute('UPDATE publication_executions SET receipt=? WHERE manifest_revision=?',(encoded(result),manifest_ref['revision']))
        return result

    def execute_selection(self,manifest_ref,*,message,remote=None):
        """Disabled without trusted host gate. Production execution belongs to main."""
        preview=self.preview(manifest_ref)
        if not message.strip():raise ValueError('commit message required')
        if remote is not None and not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]*',remote):raise ValueError('remote must be a configured name, not URL/path/option')
        plan={'manifest_ref':manifest_ref,'project':str(self.project),'base_commit':preview['base_commit'],'files':[{k:f[k] for k in ('path','digest')} for f in preview['files']],'operation':'commit-and-push' if remote else 'local-commit','remote':remote}
        if self.execution_gate is None or self.execution_gate(plan) is not True:raise ValueError('host execution gate did not authorize this concrete Git plan')
        with self.repo.lock:
            old=self.repo.db.execute('SELECT receipt FROM publication_executions WHERE manifest_revision=?',(manifest_ref['revision'],)).fetchone()
        previous=json.loads(old[0]) if old else None
        if previous and previous['state']!='preparing':
            if remote and not previous['repository_visible']:
                git(self.project,'push',remote,previous['commit']+':refs/heads/'+previous['branch'])
                previous.update(state='pushed',repository_visible=True)
                with self.repo.transaction():self.repo.db.execute('UPDATE publication_executions SET receipt=? WHERE manifest_revision=?',(encoded(previous),manifest_ref['revision']))
            return previous
        if git(self.project,'rev-parse','HEAD')!=preview['base_commit']:raise ValueError('Git base moved; preserve selection for re-review')
        if previous:
            allowed={f['path'] for f in preview['files']}
            dirty=set(git(self.project,'diff','--name-only').splitlines())|set(git(self.project,'diff','--cached','--name-only').splitlines())|set(git(self.project,'ls-files','--others','--exclude-standard').splitlines())
            if dirty-allowed:raise ValueError('recovery found unrelated changes')
            for f in preview['files']:
                target=path_inside(self.project,f['path'])
                old_bytes=subprocess.run(['git','show',preview['base_commit']+':'+f['path']],cwd=self.project,capture_output=True).stdout
                current=target.read_bytes() if target.exists() else b''
                if current not in (old_bytes,base64.b64decode(f['content_base64'])):raise ValueError('recovery bytes differ from base and reviewed output')
        else:
            if git(self.project,'status','--porcelain'):raise ValueError('Git worktree contains unrelated changes')
            preparing={'state':'preparing','base_commit':preview['base_commit'],'branch':git(self.project,'symbolic-ref','--short','HEAD'),'repository_visible':False,'site_active':False}
            with self.repo.transaction():self.repo.db.execute('INSERT INTO publication_executions VALUES (?,?)',(manifest_ref['revision'],encoded(preparing)))
        files=[]
        for f in preview['files']:
            path=path_inside(self.project,f['path']);path.parent.mkdir(parents=True,exist_ok=True);raw=base64.b64decode(f['content_base64']);path.write_bytes(raw);files.append(f['path'])
        changed=git(self.project,'status','--porcelain')
        if not changed:
            unchanged={'state':'checked-unchanged','commit':preview['base_commit'],'branch':git(self.project,'symbolic-ref','--short','HEAD'),'repository_visible':False,'site_active':False,'empty_commit_created':False}
            with self.repo.transaction():self.repo.db.execute('UPDATE publication_executions SET receipt=? WHERE manifest_revision=?',(encoded(unchanged),manifest_ref['revision']))
            return unchanged
        git(self.project,'add','--',*files)
        subprocess.run(['git','commit','-F','-'],cwd=self.project,input=message,text=True,check=True,capture_output=True)
        commit=git(self.project,'rev-parse','HEAD');result={'state':'committed','base_commit':preview['base_commit'],'commit':commit,'branch':git(self.project,'symbolic-ref','--short','HEAD'),'repository_visible':False,'site_active':False}
        # Commit is durable before any remote action; persist partial success first.
        with self.repo.transaction():self.repo.db.execute('UPDATE publication_executions SET receipt=? WHERE manifest_revision=?',(encoded(result),manifest_ref['revision']))
        if remote:
            git(self.project,'push',remote,'HEAD')
            result.update(state='pushed',repository_visible=True)
            with self.repo.transaction():self.repo.db.execute('UPDATE publication_executions SET receipt=? WHERE manifest_revision=?',(encoded(result),manifest_ref['revision']))
        return result
