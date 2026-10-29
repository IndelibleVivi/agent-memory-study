"""Conservative identifier parsing and reversible current-identity decisions."""
from __future__ import annotations
import json
import re
from urllib.parse import urlsplit,urlunsplit,unquote
from .intake import remember,details,set_details
from .records import ACTOR,command,record,ref,revise,identity
from .repository import encoded,now
from .arguments import ArgumentService,human

IDENTITY_MIGRATION_SQL=(
 'CREATE TABLE identity_aliases (namespace TEXT NOT NULL,value TEXT NOT NULL,work_id TEXT NOT NULL,PRIMARY KEY(namespace,value,work_id))',
 'CREATE TABLE identity_redirects (work_id TEXT PRIMARY KEY,target_id TEXT NOT NULL)',
 'CREATE TABLE identity_decisions (id TEXT PRIMARY KEY,decision TEXT NOT NULL)',
)

def checked_identifier(value):
    if not isinstance(value,dict) or set(value)!={'namespace','value'} or not isinstance(value['value'],str):raise ValueError('explicit identifier namespace/value only')
    namespace,text=value['namespace'],value['value']
    if namespace=='doi' and re.fullmatch(r'10\.\d{4,9}/\S+',text,re.I):text=text.lower()
    elif namespace=='arxiv' and re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})',text,re.I):text=text.lower()
    elif namespace=='github-repository' and re.fullmatch(r'[1-9]\d*',text):pass
    elif namespace=='url':
        parsed=parse_identifier(text)
        if not parsed['locator']:raise ValueError('explicit URL identifier required')
        text=parsed['locator']
    else:raise ValueError('identifier must satisfy the DOI/arXiv family/GitHub repository/URL allowlist')
    return {'namespace':namespace,'value':text}

def parse_identifier(raw):
    value=raw.strip();out={'input':raw,'identifiers':[],'publisher_version':None,'locator':None,'confidence':'unresolved'}
    if re.fullmatch(r'10\.\d{4,9}/\S+',value,re.I):out['identifiers']=[{'namespace':'doi','value':value.lower()}];out['confidence']='exact-namespace';return out
    match=re.fullmatch(r'(?:arxiv:)?((?:\d{4}\.\d{4,5}|[a-z-]+/\d{7}))(v\d+)?',value,re.I)
    if match:
        out.update(identifiers=[{'namespace':'arxiv','value':match[1].lower()}],publisher_version=match[1].lower()+(match[2] or '') if match[2] else None,confidence='exact-namespace');return out
    u=urlsplit(value)
    if u.scheme.lower() not in ('http','https') or not u.hostname:return out
    if u.username or u.password:raise ValueError('credential-bearing URL rejected')
    host=u.hostname.lower();netloc=host+((':'+str(u.port)) if u.port else '')
    out['locator']=urlunsplit((u.scheme.lower(),netloc,u.path,u.query,u.fragment))
    out['identifiers']=[{'namespace':'url','value':out['locator']}]
    if host in ('doi.org','dx.doi.org'):
        doi=unquote(u.path.lstrip('/'))
        if re.fullmatch(r'10\.\d{4,9}/\S+',doi,re.I):out['identifiers'].append({'namespace':'doi','value':doi.lower()});out['confidence']='exact-namespace'
    elif host=='arxiv.org':
        m=re.fullmatch(r'/(?:abs|pdf)/((?:\d{4}\.\d{4,5}|[a-z-]+/\d{7}))(v\d+)?(?:\.pdf)?',u.path,re.I)
        if m:out['identifiers'].append({'namespace':'arxiv','value':m[1].lower()});out['publisher_version']=m[1].lower()+(m[2] or '') if m[2] else None;out['confidence']='exact-namespace'
    elif host=='github.com':
        m=re.fullmatch(r'/([^/]+)/([^/]+)/(?:commit|blob)/([0-9a-fA-F]{40})(?:/.*)?',u.path)
        if m:out.update(github_repository_locator=m[1]+'/'+m[2],publisher_version=m[3].lower(),confidence='fixed-commit-needs-repository-id')
    return out

class IdentityService:
    def __init__(self,repo,public_records=()):
        self.repo=repo;self.public=list(public_records);repo.cache_public_records(self.public)
        self.resolver=ArgumentService(repo,self.public)
    def _current_id(self,id):
        seen=set()
        while True:
            if id in seen:raise ValueError('identity redirect cycle')
            seen.add(id)
            row=self.repo.db.execute('SELECT target_id FROM identity_redirects WHERE work_id=?',(id,)).fetchone()
            if row is None:return id
            id=row[0]
    def resolve(self,capture_id):
        capture=self.repo.load('capture',capture_id);parsed=parse_identifier(capture['input']);ids=set()
        works=self.repo.list('source_work')+[v for v in self.public if v['kind']=='source_work']
        with self.repo.lock:
            for identifier in parsed['identifiers']:
                for row in self.repo.db.execute('SELECT work_id FROM identity_aliases WHERE namespace=? AND value=?',(identifier['namespace'],identifier['value'])):ids.add(self._current_id(row[0]))
                for work in works:
                    if any(i['namespace']==identifier['namespace'] and i['value']==identifier['value'] and i['status']=='confirmed' for i in work['identifiers']):ids.add(self._current_id(work['id']))
        candidates=[]
        for wid in sorted(ids):
            found=next((w for w in works if w['id']==wid),None)
            if found:candidates.append({'work_ref':ref(found),'reason':'confirmed namespace alias; source authenticity not established'})
        state='conflicted' if len(ids)>1 else 'candidates' if candidates else 'unresolved'
        with self.repo.transaction():d=details(self.repo,capture_id);d.update(identity_state=state,identity_candidates=candidates,parsed_identity=parsed);set_details(self.repo,capture_id,d)
        return {'capture_ref':ref(capture),'state':state,'candidates':candidates,'parsed':parsed,'automatic_merge':False}
    def confirm(self,capture_id,*,title,expected_revision,idempotency_key,work_ref=None,identifiers=(),publisher_version=None,new_work=False,actor=ACTOR):
        human(actor);capture=self.repo.load('capture',capture_id);parsed=parse_identifier(capture['input'])
        payload={'operation':'confirm','capture_id':capture_id,'title':title,'expected_revision':expected_revision,'work_ref':work_ref,'identifiers':list(identifiers),'publisher_version':publisher_version,'new_work':new_work,'actor':actor}
        def apply():
            current=self.repo.load('capture',capture_id)
            if current['revision']!=expected_revision:raise ValueError('stale capture confirmation')
            if not title.strip():raise ValueError('source title required only at explicit identity confirmation')
            all_ids=parsed['identifiers']+details(self.repo,capture_id).get('suggested_identifiers',[])+list(identifiers)
            normalized=[]
            for i in all_ids:
                i=checked_identifier(i)
                v={'namespace':i['namespace'],'value':i['value'],'status':'confirmed','role':'source-locator' if i['namespace']=='url' else 'work-identity'}
                if v not in normalized:normalized.append(v)
            if type(new_work) is not bool:raise ValueError('new_work must be an explicit boolean')
            chosen=work_ref
            works=self.repo.list('source_work')+[v for v in self.public if v['kind']=='source_work']
            if chosen is None and not new_work:
                matches=set()
                for i in normalized:
                    matches.update(self._current_id(row[0]) for row in self.repo.db.execute('SELECT work_id FROM identity_aliases WHERE namespace=? AND value=?',(i['namespace'],i['value'])))
                    matches.update(self._current_id(w['id']) for w in works if any(a['namespace']==i['namespace'] and a['value']==i['value'] and a['status']=='confirmed' for a in w['identifiers']))
                if len(matches)>1:raise ValueError('multiple exact aliases conflict; choose a fixed Work or explicitly keep separate')
                if matches:
                    wid=next(iter(matches));match=next((w for w in works if w['id']==wid),None)
                    if match:chosen=ref(match)
            if chosen:
                work=self.resolver.resolve(chosen)
                if work['kind']!='source_work':raise ValueError('expected SourceWork')
            else:
                work=record('source_work',{'title':title,'work_type':'code' if parsed.get('github_repository_locator') else 'other','authors':[],'year':None,'identifiers':normalized,'manifestations':[],'aliases':[],'visibility':'private'})
                self.repo._apply(command(work,actor=actor))
            for i in normalized:self.repo.db.execute('INSERT OR IGNORE INTO identity_aliases VALUES (?,?,?)',(i['namespace'],i['value'],work['id']))
            version=publisher_version or parsed['publisher_version']
            if version is not None and not isinstance(version,(str,dict)):raise ValueError('explicit fixed publisher edition required')
            if isinstance(version,dict) and (version.get('mode')!='publisher-version' or not isinstance(version.get('value'),str)):raise ValueError('publisher_version cannot fabricate an acquired observation snapshot')
            if parsed.get('github_repository_locator') and not work_ref and not any(i['namespace']=='github-repository' and i['value'].isdigit() for i in normalized):raise ValueError('GitHub identity requires recorded repository ID, not mutable name alone')
            if isinstance(version,str):
                if parsed.get('github_repository_locator') and not re.fullmatch('[0-9a-f]{40}',version):raise ValueError('fixed full commit required')
                if not parsed.get('github_repository_locator') and not re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})v\d+',version):raise ValueError('explicit namespace-bound publisher edition required')
            identity_version=version.get('value') if isinstance(version,dict) else version
            if identity_version:
                namespace=version.get('namespace') if isinstance(version,dict) else 'git' if parsed.get('github_repository_locator') else 'arxiv'
                if namespace=='git':
                    if not parsed.get('github_repository_locator') or not re.fullmatch('[0-9a-f]{40}',identity_version) or parsed['publisher_version']!=identity_version:raise ValueError('Git edition must bind the selected fixed commit locator')
                elif namespace=='arxiv':
                    m=re.fullmatch(r'((?:\d{4}\.\d{4,5}|[a-z-]+/\d{7}))v([1-9]\d*)',identity_version)
                    if not m or not any(i['namespace']=='arxiv' and i['value']==m[1] for i in normalized):raise ValueError('arXiv edition must bind the confirmed family')
                else:raise ValueError('publisher edition namespace not in the supported allowlist')
            locator=parsed['locator'] or capture['input']
            identity_fields={'mode':'publisher-version','namespace':'git' if parsed.get('github_repository_locator') else 'arxiv','value':version,'source_locator':locator,'identity_basis':'explicit human confirmation of fixed identifier; not authenticity certification'} if version else {'mode':'observed-snapshot','observed_at':now(),'source_locator':locator,'observation_basis':'metadata identity only; content not yet acquired','publisher_version_known':False,'snapshot_captured':False}
            if publisher_version and isinstance(publisher_version,dict):identity_fields=publisher_version
            # Same publisher edition reuses its exact content identity; metadata-only does not create a content edition.
            previous=[r for r in self.repo.list('source_revision') if r['id']==work['id']]
            history=self.repo.history('source_revision',work['id'])
            same=next((r for r in history if version and r['identity'].get('value')==identity_fields.get('value') and r['identity'].get('namespace')==identity_fields.get('namespace')),None)
            if not version and previous:same=previous[0]  # metadata alone does not establish a new content snapshot
            if same:revision=same
            else:
                fields={'work_ref':ref(work),'identity':identity_fields}
                if previous:fields['predecessor_ref']=ref(previous[0])
                revision=record('source_revision',fields,id=work['id']);self.repo._apply(command(revision,previous=previous[0] if previous else None,actor=actor))
            decision={'id':identity('decision'),'operation':'confirm','capture_ref':ref(capture),'work_ref':ref(work),'source_revision_ref':ref(revision),'actor':actor,'recorded_at':now(),'historical_refs_rewritten':False}
            self.repo.db.execute('INSERT INTO identity_decisions VALUES (?,?)',(decision['id'],encoded(decision)))
            d=details(self.repo,capture_id);d.update(identity_state='confirmed',identity_decision_id=decision['id'],work_ref=ref(work),source_revision_ref=ref(revision));set_details(self.repo,capture_id,d)
            return decision
        return remember(self.repo,idempotency_key,payload,apply)
    def merge(self,work_refs,target_ref,*,reason,idempotency_key,actor=ACTOR):
        human(actor);payload={'operation':'merge','input_refs':work_refs,'target_ref':target_ref,'reason':reason,'actor':actor}
        def apply():
            values=[self.resolver.resolve(r) for r in work_refs];target=self.resolver.resolve(target_ref)
            if len({v['id'] for v in values})<2 or target['kind']!='source_work' or not reason.strip():raise ValueError('explicit distinct works and reason required')
            if target['id'] not in {v['id'] for v in values}:raise ValueError('merge target must be an input work')
            for value in values:
                if value['kind']!='source_work':raise ValueError('work refs only')
                if value['id']!=target['id']:self.repo.db.execute('INSERT INTO identity_redirects VALUES (?,?) ON CONFLICT(work_id) DO UPDATE SET target_id=excluded.target_id',(value['id'],target['id']))
            for value in values:self._current_id(value['id'])
            d={'id':identity('decision'),**payload,'recorded_at':now(),'historical_refs_rewritten':False};self.repo.db.execute('INSERT INTO identity_decisions VALUES (?,?)',(d['id'],encoded(d)));return d
        return remember(self.repo,idempotency_key,payload,apply)
    def split(self,work_refs,*,reason,idempotency_key,actor=ACTOR):
        human(actor);payload={'operation':'split','work_refs':work_refs,'reason':reason,'actor':actor}
        def apply():
            values=[self.resolver.resolve(r) for r in work_refs]
            if len({v['id'] for v in values})<2 or not reason.strip():raise ValueError('split requires explicit identities and reason')
            for v in values:
                if v['kind']!='source_work':raise ValueError('work refs required')
                self.repo.db.execute('DELETE FROM identity_redirects WHERE work_id=?',(v['id'],))
            d={'id':identity('decision'),**payload,'recorded_at':now(),'historical_refs_rewritten':False};self.repo.db.execute('INSERT INTO identity_decisions VALUES (?,?)',(d['id'],encoded(d)));return d
        return remember(self.repo,idempotency_key,payload,apply)
