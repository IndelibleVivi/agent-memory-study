import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from services.local.test_arguments import P6Base
from services.local.records import record,ref,ACTOR
from services.local.repository import now
from services.local.publication import PublicationService,scan_public
from services.local.revisions import git

class PublicationTests(P6Base):
    def setUp(self):
        super().setUp();self.project=Path(self.temp.name)/'synthetic';self.project.mkdir()
        git(self.project,'init','-b','main');git(self.project,'config','user.name','AMS Synthetic Test');git(self.project,'config','user.email','ams-test@example.invalid')
        (self.project/'seed.txt').write_text('synthetic baseline');git(self.project,'add','seed.txt');git(self.project,'commit','-m','create synthetic baseline')
        self.base=git(self.project,'rev-parse','HEAD');self.pub=PublicationService(self.repo,self.project)
    def fixture(self,text='public original text',path='study/entries/test.md',visibility='public-candidate'):
        blob=self.repo.put_blob(text.encode());raw=text.encode();digest='sha256:'+hashlib.sha256(raw).hexdigest()
        a=self.save(record('artifact',{'media_type':'text/markdown','byte_length':len(raw),'artifact_digest':digest,'storage':{'kind':'blob','locator':digest},'role':'authored','visibility':visibility,'obtained_at':now()}))
        e=self.save(record('entry',{'entry_type':'research-essay','title':'Synthetic original','byline':'AMS tests','date':'2026-10-29','intro':'bounded','body_file':path.removeprefix('study/'),'payload':{'private_note':'MUST NOT SPREAD'}}))
        item={'entity_ref':ref(e),'artifact_ref':ref(a),'public_path':path,'rights':{'basis':'own-work','license_or_permission':'original synthetic fixture explicitly selected for this test','attribution':'AMS tests'},'reviewed_digest':digest,'release_review':{'actor':ACTOR,'at':now(),'rationale':'reviewed these exact public bytes'}}
        return e,a,item
    def prepare(self,text='public original text'):
        e,a,item=self.fixture(text);m=self.pub.prepare([ref(e)],[item],base_commit=self.base);return m,e,a,item
    def test_explicit_allowlist_no_private_manifest_or_payload(self):
        m,e,a,item=self.prepare();projection=self.pub.public_projection(ref(m));raw=json.dumps(projection)
        self.assertNotIn('MUST NOT SPREAD',raw);self.assertNotIn(m['id'],raw);self.assertNotIn('prepared_by',raw)
        self.assertEqual(self.pub.preview(ref(m))['status'],'reviewable-not-published')
    def test_private_artifact_bad_digest_and_canary_rejected(self):
        e,a,item=self.fixture(visibility='private')
        with self.assertRaises(ValueError):self.pub.prepare([ref(e)],[item],base_commit=self.base)
        e,a,item=self.fixture('PRIVATE-CANARY')
        with self.assertRaises(ValueError):self.pub.prepare([ref(e)],[item],base_commit=self.base,canaries=['PRIVATE-CANARY'])
        item['reviewed_digest']='sha256:'+'0'*64
        with self.assertRaises(ValueError):self.pub.prepare([ref(e)],[item],base_commit=self.base)
    def test_canary_every_output_format_and_attachment(self):
        for extension in ['html','js','json','md','rdf','xml','pdf']:
            with self.assertRaises(ValueError):scan_public({'result.'+extension:b'prefix canary suffix'},['canary'])
    def test_dependency_closure_and_path_escape(self):
        e,a,item=self.fixture();other=self.claim()
        from services.local.records import revise,command
        newer=revise(e,references=[ref(other)]);self.repo.apply(command(newer,previous=e));item['entity_ref']=ref(newer)
        with self.assertRaisesRegex(ValueError,'closure'):self.pub.prepare([ref(newer)],[item],base_commit=self.base)
        item['entity_ref']=ref(e);item['public_path']='study/../../escape.md'
        with self.assertRaises(ValueError):self.pub.prepare([ref(e)],[item],base_commit=self.base)
    def test_gate_required_and_base_conflict(self):
        m,*_=self.prepare()
        with self.assertRaisesRegex(ValueError,'gate'):self.pub.execute_selection(ref(m),message='not authorized')
        self.pub.execution_gate=lambda p:True
        (self.project/'new.txt').write_text('another accepted commit');git(self.project,'add','new.txt');git(self.project,'commit','-m','move synthetic base')
        with self.assertRaisesRegex(ValueError,'base moved'):self.pub.execute_selection(ref(m),message='do not overwrite')
    def test_push_visible_build_failed_keeps_previous_site(self):
        m,*_=self.prepare();self.pub.execution_gate=lambda p:True
        remote=Path(self.temp.name)/'remote.git';subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
        git(self.project,'remote','add','synthetic',str(remote))
        result=self.pub.execute_selection(ref(m),message='publish synthetic selected original',remote='synthetic')
        self.assertTrue(result['repository_visible']);commit=result['commit']
        self.assertEqual(git(remote,'rev-parse','refs/heads/main'),commit)
        active={'repository':{'state':'visible','commit':commit,'url':'https://example.invalid/repo','observed_at':now()},'build':{'state':'succeeded','source_commit':commit,'artifact_digest':'sha256:'+'a'*64},'site':{'state':'active','source_commit':commit,'artifact_digest':'sha256:'+'a'*64,'deployment_id':'synthetic-one','url':'https://example.invalid/','verified_at':now()}}
        self.pub.record_delivery(ref(m),active)
        failed={'repository':active['repository'],'build':{'state':'failed','source_commit':commit},'site':{'state':'failed'}}
        self.pub.record_delivery(ref(m),failed)
        self.assertEqual(self.pub.current_site()['delivery']['site']['deployment_id'],'synthetic-one')
        self.assertEqual(self.pub.deliveries(ref(m))[-1]['delivery']['repository']['state'],'visible')
    def test_push_failure_preserves_commit_and_explicit_resume(self):
        m,*_=self.prepare();self.pub.execution_gate=lambda p:True
        with self.assertRaises(subprocess.CalledProcessError):self.pub.execute_selection(ref(m),message='commit before push failure',remote='missing')
        commit=git(self.project,'rev-parse','HEAD');self.assertNotEqual(commit,self.base)
        remote=Path(self.temp.name)/'retry.git';subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True);git(self.project,'remote','add','synthetic',str(remote))
        r=self.pub.execute_selection(ref(m),message='resume existing commit',remote='synthetic')
        self.assertEqual(r['commit'],commit);self.assertTrue(r['repository_visible'])
    def test_checked_unchanged_creates_no_commit(self):
        path=self.project/'study/entries/test.md';path.parent.mkdir(parents=True);path.write_text('same')
        git(self.project,'add','study/entries/test.md');git(self.project,'commit','-m','existing public text');self.base=git(self.project,'rev-parse','HEAD')
        m,*_=self.prepare('same');self.pub.execution_gate=lambda p:True
        r=self.pub.execute_selection(ref(m),message='should not be a commit')
        self.assertEqual(r['state'],'checked-unchanged');self.assertEqual(git(self.project,'rev-parse','HEAD'),self.base)
    def test_precommit_partial_write_recovery_and_commit_ack_reconcile(self):
        m,*_=self.prepare();self.pub.execution_gate=lambda p:True
        original=Path.write_bytes
        first=[True]
        def interrupt(path,raw):
            result=original(path,raw)
            if path.name=='test.md' and first[0]:first[0]=False;raise RuntimeError('synthetic interrupted after selected file write')
            return result
        with patch.object(Path,'write_bytes',interrupt):
            with self.assertRaises(RuntimeError):self.pub.execute_selection(ref(m),message='selected only')
        self.assertEqual(git(self.project,'rev-parse','HEAD'),self.base)
        result=self.pub.execute_selection(ref(m),message='resume reviewed bytes');commit=result['commit']
        with self.repo.transaction():self.repo.db.execute('UPDATE publication_executions SET receipt=? WHERE manifest_revision=?',(json.dumps({'state':'preparing'}),m['revision']))
        reconciled=self.pub.reconcile_commit(ref(m),commit)
        self.assertTrue(reconciled['reconciled_after_ack_loss']);self.assertEqual(git(self.project,'rev-parse','HEAD'),commit)

    def test_site_active_requires_exact_successful_build(self):
        m,*_=self.prepare()
        with self.assertRaises(ValueError):self.pub.record_delivery(ref(m),{'repository':{'state':'not-pushed'},'build':{'state':'failed'},'site':{'state':'active'}})

    def test_root_relative_body_and_delivery_idempotence_are_validated(self):
        e,a,item=self.fixture();from services.local.records import revise,command
        root_relative=revise(e,body_file='study/entries/test.md');self.repo.apply(command(root_relative,previous=e));item['entity_ref']=ref(root_relative)
        manifest=self.pub.prepare([ref(root_relative)],[item],base_commit=self.base)
        value={'repository':{'state':'not-pushed'},'build':{'state':'not-built'},'site':{'state':'not-requested'}}
        one=self.pub.record_delivery(ref(manifest),value,idempotency_key='delivery');self.assertEqual(one,self.pub.record_delivery(ref(manifest),value,idempotency_key='delivery'))
        self.assertEqual(len(self.pub.deliveries(ref(manifest))),1);self.assertEqual(one['schema'],'ams-publication-delivery/1')
        with self.assertRaises(ValueError):self.pub.record_delivery(ref(manifest),{**value,'observed_at':'not-an-ISO-time'})
    def test_prepare_delegation_does_not_grant_git_execution(self):
        e,a,item=self.fixture();grant=self.save(record('thread',{'title':'Synthetic host release review delegation','byline':'AMS tests','status':'open','payload':{'artifact_ref':ref(a)}}));agent={'kind':'agent','id':'actor:release-review'}
        item['release_review']={**item['release_review'],'actor':agent,'delegation_ref':ref(grant)}
        def trusted(actor,operation,target,requested):
            if actor!=agent or operation not in ('publication.release','publication.prepare') or target not in (ref(a),ref(e)):raise ValueError('out of delegation scope')
            return ref(grant)
        service=PublicationService(self.repo,self.project,review_authorizer=trusted)
        m=service.prepare([ref(e)],[item],base_commit=self.base,actor=agent,delegation_ref=ref(grant))
        _,selection=service._selection(ref(m));self.assertEqual(selection['items'][0]['release_review']['delegation_ref'],ref(grant))
        with self.assertRaisesRegex(ValueError,'gate'):service.execute_selection(ref(m),message='review is not publish permission')

if __name__=='__main__':unittest.main()
