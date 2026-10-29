"""Explicit local acquisition, immutable bytes and separately declared reading."""
from __future__ import annotations
from io import BytesIO
import json
from pathlib import Path
import socket
import urllib.error
import urllib.request
from urllib.parse import urlsplit,urljoin
from schemas.validate import content_digest,validate_entity
from .arguments import ArgumentService
from .intake import remember,details,set_details
from .records import ACTOR,command,record,ref,identity
from .repository import encoded,now

ACQUISITION_MIGRATION_SQL=(
 'CREATE TABLE acquisition_plans (id TEXT PRIMARY KEY,capture_id TEXT NOT NULL,plan TEXT NOT NULL)',
 'CREATE TABLE acquisition_attempts (id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,receipt TEXT NOT NULL)',
 'CREATE TABLE extraction_attempts (id TEXT PRIMARY KEY,receipt TEXT NOT NULL)',
)
DEFAULT_LIMIT=8*1024*1024
MAX_LIMIT=32*1024*1024

def approved_url(url,hosts):
    u=urlsplit(url)
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:raise ValueError('plain selected HTTP(S) URL required')
    if u.hostname.lower() not in {h.lower() for h in hosts}:raise ValueError('host not explicitly permitted')
    return url

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def http_get(url,limit):
    """No cookies/auth/upload. Redirects are data and rechecked by caller."""
    opener=urllib.request.build_opener(NoRedirect())
    request=urllib.request.Request(url,method='GET',headers={'User-Agent':'AMS-Local-Research/1'})
    try:
        with opener.open(request,timeout=15) as r:return {'status':r.status,'headers':dict(r.headers),'body':r.read(limit+1),'final_url':r.geturl()}
    except urllib.error.HTTPError as exc:
        return {'status':exc.code,'headers':dict(exc.headers),'body':exc.read(limit+1),'final_url':exc.geturl()}

class AcquisitionService:
    def __init__(self,repo,public_records=(),*,fetch=None):
        public_records=list(public_records);repo.cache_public_records(public_records)
        self.repo=repo;self.resolver=ArgumentService(repo,public_records);self.fetch=fetch or http_get
    def _plan(self,capture_id,kind,selection,limit,key):
        self.repo.load('capture',capture_id)
        if type(limit) is not int or not 1<=limit<=MAX_LIMIT:raise ValueError('explicit bounded byte budget required')
        payload={'kind':kind,'capture_id':capture_id,'selection':selection,'max_bytes':limit}
        def apply():
            p={'id':identity('acquisition'),**payload,'created_at':now(),'network_default':False,'status':'planned-not-executed'}
            self.repo.db.execute('INSERT INTO acquisition_plans VALUES (?,?,?)',(p['id'],capture_id,encoded(p)));d=details(self.repo,capture_id);d['acquisition_state']='queued';set_details(self.repo,capture_id,d);return p
        return remember(self.repo,key,payload,apply)
    def plan_url(self,capture_id,url,*,idempotency_key,max_bytes=DEFAULT_LIMIT):
        u=urlsplit(url)
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:raise ValueError('selected HTTP(S) URL only')
        return self._plan(capture_id,'url',{'url':url},max_bytes,idempotency_key)
    def plan_file(self,capture_id,*,filename,media_type='application/octet-stream',idempotency_key,max_bytes=DEFAULT_LIMIT):
        if not isinstance(filename,str) or not filename.strip():raise ValueError('selected filename required')
        # Metadata only, never opened as a server filesystem path.
        return self._plan(capture_id,'file',{'filename':filename,'media_type':media_type},max_bytes,idempotency_key)
    def _load(self,id):
        with self.repo.lock:r=self.repo.db.execute('SELECT plan FROM acquisition_plans WHERE id=?',(id,)).fetchone()
        if r is None:raise ValueError('unknown acquisition plan')
        return json.loads(r[0])
    def inspect(self,capture_id):
        self.repo.load('capture',capture_id)
        with self.repo.lock:
            plans=[json.loads(r[0]) for r in self.repo.db.execute('SELECT plan FROM acquisition_plans WHERE capture_id=?',(capture_id,))]
            attempts=[json.loads(r[0]) for r in self.repo.db.execute('SELECT a.receipt FROM acquisition_attempts a JOIN acquisition_plans p ON p.id=a.plan_id WHERE p.capture_id=?',(capture_id,))]
            artifacts={encoded(r['artifact_ref']) for r in attempts if r.get('artifact_ref')}
            extractions=[json.loads(r[0]) for r in self.repo.db.execute('SELECT receipt FROM extraction_attempts')]
        return {'capture_id':capture_id,'plans':plans,'attempts':attempts,'extractions':[r for r in extractions if encoded(r['input_artifact_ref']) in artifacts]}
    def cancel(self,plan_id,*,idempotency_key):
        def apply():
            plan=self._load(plan_id);plan['status']='cancelled';plan['cancelled_at']=now()
            self.repo.db.execute('UPDATE acquisition_plans SET plan=? WHERE id=?',(encoded(plan),plan_id))
            d=details(self.repo,plan['capture_id']);d['acquisition_state']='cancelled';set_details(self.repo,plan['capture_id'],d)
            return {'plan_id':plan_id,'status':'cancelled','existing_artifacts_preserved':True,'inflight_transport':'current GET may complete or timeout before cancellation is observed','retry':'create a new explicit plan and execution key'}
        return remember(self.repo,idempotency_key,{'operation':'cancel-acquisition','plan':plan_id},apply)
    def _artifact(self,raw,media_type,*,role='source-manifestation',source_revision_ref=None,representation_of=None):
        digest=self.repo.put_blob(raw)
        fields={'media_type':media_type,'byte_length':len(raw),'artifact_digest':digest,'storage':{'kind':'blob','locator':digest},'role':role,'visibility':'private','obtained_at':now()}
        if source_revision_ref:fields['source_revision_ref']=source_revision_ref
        if representation_of:fields['representation_of']=representation_of
        value=record('artifact',fields);self.repo._apply(command(value));return value
    def _accept(self,plan,raw,media_type,*,status,requested_url=None,final_url=None,response_status=None,error=None,redirects=(),content_range=None):
        received_length=len(raw) if raw is not None else 0
        d=details(self.repo,plan['capture_id']);source=d.get('source_revision_ref');artifact=None
        if raw is not None:
            raw=raw[:plan['max_bytes']]
            old_source=self.resolver.resolve(source) if source else None
            if old_source and old_source['identity']['mode']=='observed-snapshot':
                digest=self.repo.put_blob(raw);prior_artifact=old_source['identity'].get('artifact_ref')
                same=prior_artifact and self.resolver.resolve(prior_artifact)['artifact_digest']==digest
                if not same:
                    fields={'media_type':media_type,'byte_length':len(raw),'artifact_digest':digest,'storage':{'kind':'blob','locator':digest},'role':'source-manifestation','visibility':'private','obtained_at':now()}
                    provisional=record('artifact',fields)
                    revision=record('source_revision',{'work_ref':old_source['work_ref'],'predecessor_ref':source,'identity':{'mode':'observed-snapshot','observed_at':now(),'source_locator':requested_url or plan['selection'].get('filename','selected file'),'observation_basis':'actual bounded acquired bytes; not a publisher edition or semantic-change judgment','publisher_version_known':False,'snapshot_captured':True,'artifact_ref':ref(provisional)}},id=old_source['id'])
                    artifact=record('artifact',{**fields,'source_revision_ref':ref(revision)},id=provisional['id'])
                    # Allocate both exact refs before publishing either; neither provisional record was stored.
                    revision['identity']['artifact_ref']=ref(artifact);revision['content_digest']=content_digest(revision);validate_entity(revision)
                    self.repo._apply(command(artifact));self.repo._apply(command(revision,previous=old_source));source=ref(revision);d['source_revision_ref']=source
                else:artifact=self._artifact(raw,media_type,source_revision_ref=source,representation_of=None if source else ref(self.repo.load('capture',plan['capture_id'])))
            else:artifact=self._artifact(raw,media_type,source_revision_ref=source,representation_of=None if source else ref(self.repo.load('capture',plan['capture_id'])))
        receipt={'id':identity('acquisition_attempt'),'plan_id':plan['id'],'capture_id':plan['capture_id'],'recorded_at':now(),'status':status,'artifact_ref':ref(artifact) if artifact else None,'stored_byte_digest':artifact['artifact_digest'] if artifact else None,'requested_url':requested_url,'final_url':final_url,'response_status':response_status,'redirects':list(redirects),'media_type':media_type,'byte_length':len(raw) if raw is not None else 0,'received_byte_length':received_length,'obtained_range':content_range or ('bounded-prefix' if received_length>plan['max_bytes'] else 'selected-response-or-file' if artifact else 'none'),'original_complete':bool(artifact and received_length<=plan['max_bytes'] and response_status!=206),'error':error,'distribution':'private-original; no redistribution permission inferred','read_scope':'not-read','source_revision_ref':source}
        self.repo.db.execute('INSERT INTO acquisition_attempts VALUES (?,?,?)',(receipt['id'],plan['id'],encoded(receipt)))
        d['acquisition_state']=status;d.setdefault('acquisition_refs',[]).append(receipt['id'])
        if artifact:d.setdefault('artifact_refs',[]).append(ref(artifact))
        set_details(self.repo,plan['capture_id'],d);return receipt
    def execute_file(self,plan_id,selected_bytes,*,idempotency_key):
        plan=self._load(plan_id)
        if plan['kind']!='file' or not isinstance(selected_bytes,bytes):raise ValueError('selected file bytes required')
        from .repository import byte_digest
        payload={'operation':'execute-file','plan':plan_id,'selected_digest':byte_digest(selected_bytes),'selected_length':len(selected_bytes)}
        def apply():
            if self._load(plan_id)['status']=='cancelled':raise ValueError('cancelled plan; create a new explicit plan to retry')
            return self._accept(plan,selected_bytes,plan['selection']['media_type'],status='partial' if len(selected_bytes)>plan['max_bytes'] else 'available',error='byte-limit-exceeded; bounded original prefix retained' if len(selected_bytes)>plan['max_bytes'] else None)
        return remember(self.repo,idempotency_key,payload,apply)
    def execute_url(self,plan_id,*,allowed_hosts=(),idempotency_key):
        plan=self._load(plan_id)
        if plan['kind']!='url':raise ValueError('URL plan required')
        payload={'operation':'execute-url','plan':plan_id,'allowed_hosts':sorted(allowed_hosts)}
        # A durable start precedes transport. Re-entering an unresolved key never fetches again.
        with self.repo.lock:
            old=self.repo.db.execute('SELECT payload,receipt FROM intake_operations WHERE idempotency_key=?',(idempotency_key,)).fetchone()
            if old:
                if old['payload']!=encoded(payload):raise ValueError('idempotency payload conflict')
                return json.loads(old['receipt'])
            prior=self.repo.db.execute('SELECT payload,receipt FROM intake_operations WHERE idempotency_key=?',(idempotency_key+':started',)).fetchone()
            if prior:
                if prior['payload']!=encoded(payload):raise ValueError('idempotency payload conflict')
                return {'status':'indeterminate','started_attempt':json.loads(prior['receipt']),'automatic_retry':False,'next':'Inspect prior attempt; explicit new key required for another GET.'}
            if self._load(plan_id)['status']=='cancelled':raise ValueError('cancelled plan; create a new explicit plan to retry')
            start=remember(self.repo,idempotency_key+':started',payload,lambda:self._accept(plan,None,'unknown',status='working',requested_url=plan['selection']['url']))
        requested=plan['selection']['url'];current=requested;redirects=[]
        outcome=None
        try:
            for _ in range(6):
                if self._load(plan_id)['status']=='cancelled':
                    outcome={'raw':None,'media_type':'unknown','status':'cancelled','requested_url':requested,'final_url':current,'redirects':redirects,'error':'explicit cancellation before GET'};break
                approved_url(current,allowed_hosts);response=self.fetch(current,plan['max_bytes']);final=response.get('final_url',current);approved_url(final,allowed_hosts)
                if response['status'] in (301,302,303,307,308):
                    location=next((v for k,v in response['headers'].items() if k.lower()=='location'),None)
                    if not location:raise ValueError('redirect missing Location')
                    target=urljoin(current,location);approved_url(target,allowed_hosts);redirects.append({'from':current,'to':target});current=target;continue
                media=next((v for k,v in response['headers'].items() if k.lower()=='content-type'),'application/octet-stream')
                raw=response['body'];good=200<=response['status']<300;over_limit=len(raw)>plan['max_bytes'];partial=over_limit or response['status']==206
                content_range=next((v for k,v in response['headers'].items() if k.lower()=='content-range'),None)
                outcome={'raw':raw if good else None,'media_type':media,'status':'partial' if good and partial else 'available' if good else 'blocked','requested_url':requested,'final_url':final,'response_status':response['status'],'redirects':redirects,'content_range':content_range,'error':'byte-limit-exceeded' if over_limit else 'HTTP partial content' if response['status']==206 else None if good else 'HTTP source unavailable'}
                break
            if outcome is None:raise ValueError('redirect limit exceeded')
        except (ValueError,OSError,urllib.error.URLError) as exc:
            outcome={'raw':None,'media_type':'unknown','status':'blocked','requested_url':requested,'final_url':current,'redirects':redirects,'error':type(exc).__name__+': '+str(exc)}
        def complete():
            if self._load(plan_id)['status']=='cancelled':
                outcome['status']='cancelled';outcome['error']='explicit cancellation; any bytes already returned are retained within original budget'
            result=self._accept(plan,**outcome);result['started_attempt_ref']=start['id']
            self.repo.db.execute('UPDATE acquisition_attempts SET receipt=? WHERE id=?',(encoded(result),result['id']))
            return result
        return remember(self.repo,idempotency_key,payload,complete)
    def extract(self,artifact_ref,*,source_revision_ref=None,parser='text-utf8',coverage='unknown',idempotency_key):
        original=self.resolver.resolve(artifact_ref)
        if original['kind']!='artifact' or original.get('role')!='source-manifestation':raise ValueError('original source-manifestation Artifact required')
        if source_revision_ref and self.resolver.resolve(source_revision_ref)['kind']!='source_revision':raise ValueError('fixed SourceRevision required')
        if original.get('source_revision_ref') and source_revision_ref!=original['source_revision_ref']:raise ValueError('extractor cannot change source edition')
        if parser not in ('text-utf8','text-utf8-lines','pdf-pypdf'):raise ValueError('unknown parser')
        if coverage not in ('fulltext','abstract-only','partial','unknown'):raise ValueError('explicit extraction coverage required')
        if coverage=='fulltext':
            with self.repo.lock:receipts=[json.loads(r[0]) for r in self.repo.db.execute('SELECT receipt FROM acquisition_attempts')]
            if any(r.get('artifact_ref')==artifact_ref and (r['status']=='partial' or r.get('original_complete') is False) for r in receipts):raise ValueError('partial original cannot be labelled fulltext')
        payload={'operation':'extract','artifact_ref':artifact_ref,'source_revision_ref':source_revision_ref,'parser':parser,'coverage':coverage}
        def apply():
            raw=self.repo.read_blob(original['artifact_digest']);text=None;version='1';error=None
            try:
                if parser=='pdf-pypdf':
                    from importlib.metadata import version as package_version
                    from pypdf import PdfReader
                    version=package_version('pypdf');text='\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(raw)).pages)
                    if not text.strip():raise ValueError('image-only/scanned PDF; OCR is not installed by this service')
                else:
                    text=raw.decode('utf-8')
                    if parser=='text-utf8-lines':text='\n'.join(text.splitlines())
            except Exception as exc:error=type(exc).__name__+': '+str(exc)[:1000]
            output=None;extraction=None
            if text is not None and error is None:
                output=self._artifact(text.encode(),'text/plain; charset=utf-8',role='extracted-text',source_revision_ref=source_revision_ref,representation_of=original.get('representation_of'))
                if source_revision_ref:
                    cfg={'encoding':'utf-8','parser':parser}
                    extraction=record('extraction',{'input_artifact_ref':artifact_ref,'source_revision_ref':source_revision_ref,'output_artifact_ref':ref(output),'extractor':parser,'extractor_version':version,'config_digest':content_digest(cfg,['encoding','parser']),'coverage':coverage});self.repo._apply(command(extraction))
            receipt={'id':identity('extraction_attempt'),'input_artifact_ref':artifact_ref,'output_artifact_ref':ref(output) if output else None,'extraction_ref':ref(extraction) if extraction else None,'parser':parser,'parser_version':version,'coverage':coverage if output else 'unknown','status':'available' if extraction else 'available-unbound' if output else 'blocked','error':error,'source_revision_ref':source_revision_ref,'read_scope':'not-read','original_retained':True}
            self.repo.db.execute('INSERT INTO extraction_attempts VALUES (?,?)',(receipt['id'],encoded(receipt)));return receipt
        return remember(self.repo,idempotency_key,payload,apply)
    def read_activity(self,target_ref,representation_ref,extent,*,method='human-selected',receipt_ref=None,actor=ACTOR,idempotency_key):
        target=self.resolver.resolve(target_ref);representation=self.resolver.resolve(representation_ref)
        if representation['kind']!='artifact' or not isinstance(extent,list) or not extent or any(not isinstance(x,str) or not x.strip() for x in extent):raise ValueError('explicit nonempty read extent required')
        if method not in ('human-selected','manual-declaration','agent-delivered'):raise ValueError('page open/scroll does not establish reading')
        if method=='human-selected' and actor.get('kind')!='human':raise ValueError('human selection needs human actor')
        if actor.get('kind')=='agent' and method!='agent-delivered':raise ValueError('agent reading must bind actual delivery receipt')
        if method=='agent-delivered' and actor.get('kind')!='agent':raise ValueError('agent-delivered method requires agent actor')
        if method=='agent-delivered' and not receipt_ref:raise ValueError('agent delivery requires a receipt Artifact')
        if target['kind']=='source_revision' and representation.get('source_revision_ref')!=target_ref:raise ValueError('reading representation targets another edition')
        if target['kind']!='source_revision' and representation.get('representation_of')!=target_ref:raise ValueError('reading representation is not bound to this target snapshot')
        if receipt_ref and self.resolver.resolve(receipt_ref).get('role')!='receipt':raise ValueError('delivery receipt Artifact required')
        if method=='agent-delivered':
            receipt=self.resolver.resolve(receipt_ref)
            delivered=json.loads(self.repo.read_blob(receipt['artifact_digest']))
            if delivered.get('target_ref')!=target_ref or delivered.get('representation_ref')!=representation_ref or delivered.get('extent')!=extent:raise ValueError('agent input receipt does not bind actual reading')
            actual=self.repo.read_blob(representation['artifact_digest']).decode('utf-8')
            if any(x not in delivered.get('delivered_text','') or x not in actual for x in extent):raise ValueError('extent was not actually delivered from this representation')
        if method=='human-selected':
            text=self.repo.read_blob(representation['artifact_digest']).decode('utf-8')
            if any(x not in text for x in extent):raise ValueError('selected quote absent from actual representation')
        payload={'operation':'read','target_ref':target_ref,'representation_ref':representation_ref,'extent':extent,'method':method,'receipt_ref':receipt_ref,'actor':actor}
        def apply():
            f={'actor':actor,'target_ref':target_ref,'representation_ref':representation_ref,'extent':extent,'method':method,'occurred_at':now()}
            if receipt_ref:f['receipt_ref']=receipt_ref
            value=record('read_activity',f);self.repo._apply(command(value,actor=actor));return value
        return remember(self.repo,idempotency_key,payload,apply)
    def compare(self,old_artifact_ref,new_artifact_ref):
        import difflib
        before=self.resolver.resolve(old_artifact_ref);after=self.resolver.resolve(new_artifact_ref)
        if before['kind']!='artifact' or after['kind']!='artifact':raise ValueError('two explicit Artifact snapshots required')
        same_bytes=before['artifact_digest']==after['artifact_digest']
        old_source=before.get('source_revision_ref');new_source=after.get('source_revision_ref')
        result={'old_artifact_ref':old_artifact_ref,'new_artifact_ref':new_artifact_ref,'same_bytes':same_bytes,'old_source_revision_ref':old_source,'new_source_revision_ref':new_source,'source_identity_changed':old_source!=new_source,'semantic_conclusion':'not-determined','automatic_revision':False}
        try:
            left=self.repo.read_blob(before['artifact_digest']).decode('utf-8');right=self.repo.read_blob(after['artifact_digest']).decode('utf-8')
            diff=''.join(difflib.unified_diff(left.splitlines(True),right.splitlines(True),fromfile='old exact Artifact',tofile='new exact Artifact'))
            result.update(text_diff=diff[:20000],diff_truncated=len(diff)>20000,scope='stored UTF-8 representations; parser/version and meaning still require review')
        except UnicodeError:result.update(text_diff=None,scope='binary bytes only; no invented text comparison')
        return result

    def reanchor(self,excerpt_ref,new_representation_ref):
        old=self.resolver.resolve(excerpt_ref);new=self.resolver.resolve(new_representation_ref)
        if old['kind']!='excerpt' or new['kind']!='artifact':raise ValueError('known excerpt and representation required')
        next_target=new.get('source_revision_ref') or new.get('representation_of')
        if not next_target or (old['target_ref']['kind'],old['target_ref']['id'])!=(next_target['kind'],next_target['id']):raise ValueError('reanchor candidate must remain on the same object identity')
        text=self.repo.read_blob(new['artifact_digest']).decode('utf-8');quote=old['selector'];count=text.count(quote)
        return {'excerpt_ref':excerpt_ref,'old_target_ref':old['target_ref'],'new_representation_ref':new_representation_ref,'status':'exact' if count==1 else 'ambiguous' if count>1 else 'missing','occurrences':count,'proposal_only':True,'old_excerpt_modified':False}
