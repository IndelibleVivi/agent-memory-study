"""Read-only selected-record decoders. No account discovery or live transport."""
from __future__ import annotations
import hashlib
import re
from .repository import encoded

CONNECTORS_MIGRATION_SQL=(
 'CREATE TABLE connector_observations (idempotency_key TEXT PRIMARY KEY,connector TEXT NOT NULL,selection TEXT NOT NULL,receipt TEXT NOT NULL)',
)

def digest(v):return hashlib.sha256(encoded(v).encode()).hexdigest()

class ZoteroConnector:
    id='zotero-readonly/1'
    def decode(self,response,selected_keys,*,attachments=False,annotations=False):
        if not selected_keys or len(selected_keys)>100 or len(set(selected_keys))!=len(selected_keys):raise ValueError('explicit bounded distinct Zotero selection required')
        if any(not re.fullmatch('[A-Z0-9]{8}',k) for k in selected_keys):raise ValueError('Zotero item keys are not citation keys')
        if not isinstance(response,dict) or set(response)-{'headers','data'}:raise ValueError('recorded response envelope required')
        version=response['headers'].get('Last-Modified-Version')
        if not str(version).isdigit():raise ValueError('actual Zotero library version required')
        selected=[]
        for key in selected_keys:
            matches=[r for r in response['data'] if r.get('key')==key]
            if len(matches)!=1:raise ValueError('missing/duplicate selected Zotero item')
            r=matches[0];data=r['data']
            if type(r.get('version')) is not int or r['version']<0:raise ValueError('actual Zotero item version required')
            kind=data.get('itemType')
            if kind=='attachment' and not attachments:raise ValueError('attachment selection requires separate explicit permission')
            if kind=='annotation' and not annotations:raise ValueError('annotation selection requires separate explicit permission')
            value={'item_key':key,'record_version':r['version'],'item_type':kind,'title':data.get('title',''),'doi':data.get('DOI'),'url':data.get('url'),'authors':[c.get('lastName','') for c in data.get('creators',[]) if c.get('creatorType')=='author'],
                   'content_revision':'not-inferred-from-Zotero-version','status':'metadata-only'}
            if kind in ('attachment','annotation'):value['parent_item_key']=data.get('parentItem')
            if kind=='annotation':value['selected_annotation_text']=data.get('annotationText','')
            # Never expose local attachment path, tags, private notes or auth fields.
            selected.append(value)
        return {'connector':self.id,'library_record_version':int(version),'records':selected,'response_digest':digest(response),'writeback':False,'live_verified':False}

class GitHubConnector:
    id='github-readonly/1'
    def decode(self,repository,commit,*,requested_ref,observed_at):
        if type(repository.get('id')) is not int or repository['id']<1:raise ValueError('actual GitHub repository id required')
        sha=commit.get('sha','')
        if not re.fullmatch('[0-9a-f]{40}',sha):raise ValueError('GitHub ref must resolve to full fixed commit')
        if not requested_ref or not observed_at:raise ValueError('observed named pointer and time required')
        files=[]
        for f in commit.get('files',[]):
            if not re.fullmatch('[0-9a-f]{40}',f.get('sha','')):raise ValueError('each blob must have exact sha')
            files.append({'path':f['filename'],'blob_sha':f['sha'],'status':f['status'],'patch':f.get('patch'),'patch_scope':'API returned excerpt; complete diff not implied'})
        return {'connector':self.id,'repository_identity':str(repository['id']),'repository_locator':repository['full_name'],'requested_ref':requested_ref,'commit':sha,'observed_at':observed_at,'files':files,
                'identifiers':[{'namespace':'github-repository','value':str(repository['id'])}],
                'response_digest':digest({'repository':repository,'commit':commit}),'writeback':False,'live_verified':False}

def record_observation(repo,connector,selection,receipt,*,idempotency_key):
    from .intake import remember
    payload={'connector':connector,'selection':selection,'receipt':receipt}
    def apply():
        repo.db.execute('INSERT INTO connector_observations VALUES (?,?,?,?)',(idempotency_key,connector,encoded(selection),encoded(receipt)));return receipt
    return remember(repo,idempotency_key,payload,apply)
