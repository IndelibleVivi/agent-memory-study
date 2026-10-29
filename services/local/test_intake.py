from pathlib import Path
import os
import tempfile
import unittest
from schemas.validate import validate_command
from services.local.repository import Repository
from services.local.intake import CaptureService
from services.local.identity import IdentityService
from services.local.acquisition import AcquisitionService
from services.local.records import record,command,ref

PROJECT=Path(__file__).resolve().parents[2]
EVIDENCE=Path(os.environ.get('AMS_P4_TEST_ROOT',tempfile.gettempdir()))
class P4Base(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='test-',dir=EVIDENCE);self.addCleanup(self.temp.cleanup)
        self.repo=Repository(Path(self.temp.name)/'data',PROJECT,validate_command);self.addCleanup(self.repo.close)
        self.capture=CaptureService(self.repo,PROJECT);self.identity=IdentityService(self.repo);self.acq=AcquisitionService(self.repo)
    def saved(self,text,key='capture'):
        return self.capture.capture(text,idempotency_key=key)['capture']
    def confirmed(self,text='https://arxiv.org/abs/2607.12345v2',key='capture'):
        c=self.saved(text,key);d=self.identity.confirm(c['id'],title='Original synthetic metadata',expected_revision=c['revision'],idempotency_key=key+':confirm');return c,d

class IntakeTests(P4Base):
    def test_half_thought_committed_no_title(self):
        c=self.saved('为什么单独没用的材料放一起会有用？');self.assertEqual(c['attention'],'resting');self.assertEqual(self.capture.get(c['id'])['details']['identity_state'],'unresolved')
        self.assertEqual(self.capture.capture(c['input'],idempotency_key='capture')['capture'],c)
        with self.assertRaises(ValueError):self.capture.capture('changed',idempotency_key='capture')
    def test_multiple_encounters_keep_reasons(self):
        a=self.capture.capture('arxiv:2607.12345v2',why_now='先比较定义',idempotency_key='a')
        b=self.capture.capture('arxiv:2607.12345v2',why_now='后来出现反例',idempotency_key='b')
        self.assertNotEqual(a['capture']['id'],b['capture']['id']);self.assertEqual(len(self.capture.list()),2)
    def test_attention_stale_and_restart_durable(self):
        c=self.saved('暂留概念');r=self.capture.attention(c['id'],'waiting',expected_revision=c['revision'],return_when='出现第二个真实消费者',idempotency_key='attention')
        with self.assertRaises(ValueError):self.capture.attention(c['id'],'active',expected_revision=c['revision'],idempotency_key='stale')
        # Close and reopen the actual database, not merely its page/service state.
        root=self.repo.root;self.repo.close()
        reopened=Repository(root,PROJECT,validate_command);self.addCleanup(reopened.close)
        self.assertEqual(CaptureService(reopened,PROJECT).get(c['id'])['details']['return_when'],'出现第二个真实消费者')
        self.assertEqual(r['capture']['attention'],'waiting')
    def test_batch_partial_failure_retains_successes(self):
        r=self.capture.batch(['概念一','','概念二'],batch_key='batch')
        self.assertEqual([v['status'] for v in r],['saved','rejected','saved']);self.assertEqual(len(self.capture.list()),2)
    def test_unknown_file_durable_and_context_candidate_not_support(self):
        r=self.capture.capture_bytes('unknown.bin',b'original opaque bytes',idempotency_key='bytes')
        self.assertEqual(r['acquisition']['status'],'available');self.assertTrue(r['acquisition']['artifact_ref'])
        obj=record('claim_revision',{'title':'未来任务','byline':'AMS synthetic','claim':'未来任务需要单独限定','scope':'finite','scope_binding':'finite','payload':{}})
        service=CaptureService(self.repo,PROJECT,[obj]);c=service.capture('未来任务与信息',context_refs=[ref(obj)],idempotency_key='public-context')['capture'];links=service.context_links(c['id'])
        self.assertEqual(self.repo.load(obj['kind'],obj['id'],obj['revision']),obj)
        self.assertTrue(links['candidates']);self.assertFalse(links['automatic_acceptance']);self.assertEqual(self.repo.list('evidence_relation'),[])
    def test_source_version_formal_review_scope_only(self):
        from services.local.arguments import ArgumentService
        c,d=self.confirmed();arg=ArgumentService(self.repo)
        claim=record('claim_revision',{'title':'限定旧判断','byline':'AMS tests','claim':'仅固定任务范围','scope':'finite','scope_binding':'finite','payload':{}});self.repo.apply(command(claim))
        proposal=arg.propose({'from_ref':d['source_revision_ref'],'to_ref':ref(claim),'relation':'supports','scope':'finite','scope_binding':'finite','locator':'synthetic source section','rationale':'explicit fixed scope','generated_by':{'kind':'agent','id':'actor:test'},'method_version':'synthetic/1'})
        arg.accept(ref(proposal),'human scoped review')
        newer=self.saved('arxiv:2607.12345v3','new')
        self.identity.confirm(newer['id'],title='new version',work_ref=d['work_ref'],expected_revision=newer['revision'],idempotency_key='new-confirm')
        links=self.capture.context_links(newer['id']);self.assertFalse(links['source_version_change']['semantic_conflict'])
        self.assertEqual(links['formal_review_scope'][0]['review_paths'][0]['to_ref'],ref(claim))

    def test_shared_reference_bridge_uses_public_manifest(self):
        c=self.saved('未来问题');r=self.capture.context_links(c['id'],changed_public={'kind':'study','id':'future-questions-and-memory'})
        self.assertNotEqual(r['explicit_review_scope'].get('status'),'unavailable')
        self.assertIn('references',r['explicit_review_scope'])

if __name__=='__main__':unittest.main()
