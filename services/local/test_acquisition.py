import json
import unittest
from services.local.test_intake import P4Base
from services.local.acquisition import AcquisitionService
from services.local.records import ref,record,command

class AcquisitionTests(P4Base):
    def acquired(self,text='original text',parser_source=True):
        c,d=self.confirmed() if parser_source else (self.saved('selected file'),None)
        p=self.acq.plan_file(c['id'],filename='selected.txt',media_type='text/plain',idempotency_key='file-plan')
        r=self.acq.execute_file(p['id'],text.encode(),idempotency_key='file-execute');return c,d,r
    def test_original_extraction_read_are_distinct(self):
        c,d,r=self.acquired();self.assertEqual(self.repo.list('read_activity'),[])
        one=self.acq.extract(r['artifact_ref'],source_revision_ref=r['source_revision_ref'],parser='text-utf8',coverage='fulltext',idempotency_key='extract1')
        two=self.acq.extract(r['artifact_ref'],source_revision_ref=r['source_revision_ref'],parser='text-utf8-lines',coverage='fulltext',idempotency_key='extract2')
        self.assertNotEqual(one['extraction_ref'],two['extraction_ref']);self.assertEqual(one['source_revision_ref'],two['source_revision_ref']);self.assertEqual(len(self.repo.list('source_revision')),1)
        read=self.acq.read_activity(r['source_revision_ref'],one['output_artifact_ref'],['original text'],idempotency_key='read')
        self.assertEqual(read['method'],'human-selected')
        diff=self.acq.compare(one['output_artifact_ref'],two['output_artifact_ref']);self.assertTrue(diff['same_bytes']);self.assertFalse(diff['source_identity_changed']);self.assertEqual(diff['semantic_conclusion'],'not-determined')
        with self.assertRaises(ValueError):self.acq.read_activity(r['source_revision_ref'],one['output_artifact_ref'],['not there'],idempotency_key='bad-read')
        with self.assertRaises(ValueError):self.acq.extract(one['output_artifact_ref'],source_revision_ref=r['source_revision_ref'],coverage='fulltext',idempotency_key='scope-escalation')
    def test_non_source_lineage_and_agent_receipt_binding(self):
        c,d,r=self.acquired(parser_source=False)
        extracted=self.acq.extract(r['artifact_ref'],idempotency_key='unbound')
        self.assertEqual(extracted['status'],'available-unbound')
        read=self.acq.read_activity(ref(c),extracted['output_artifact_ref'],['original text'],idempotency_key='non-source-read');self.assertEqual(read['target_ref'],ref(c))
        other=self.saved('other target','other')
        with self.assertRaises(ValueError):self.acq.read_activity(ref(other),extracted['output_artifact_ref'],['original text'],idempotency_key='wrong-target')
        payload={'target_ref':ref(c),'representation_ref':extracted['output_artifact_ref'],'extent':['original text'],'delivered_text':'original text'}
        with self.repo.transaction():receipt=self.acq._artifact(json.dumps(payload).encode(),'application/json',role='receipt')
        agent=self.acq.read_activity(ref(c),extracted['output_artifact_ref'],['original text'],method='agent-delivered',receipt_ref=ref(receipt),actor={'kind':'agent','id':'actor:input-reader'},idempotency_key='agent');self.assertEqual(agent['method'],'agent-delivered')
        with self.assertRaises(ValueError):self.acq.read_activity(ref(c),extracted['output_artifact_ref'],['original text'],method='scroll',idempotency_key='scroll')
    def test_new_web_bytes_observed_snapshot_not_parser_edition(self):
        c,d=self.confirmed('https://example.org/unversioned')
        p=self.acq.plan_file(c['id'],filename='page.txt',idempotency_key='p')
        r1=self.acq.execute_file(p['id'],b'version old',idempotency_key='r1')
        same=self.acq.execute_file(p['id'],b'version old',idempotency_key='same')
        newer=self.acq.execute_file(p['id'],b'version new',idempotency_key='new')
        self.assertEqual(same['source_revision_ref'],r1['source_revision_ref']);self.assertNotEqual(newer['source_revision_ref'],r1['source_revision_ref'])
        old=self.repo.load('source_revision',r1['source_revision_ref']['id'],r1['source_revision_ref']['revision']);self.assertTrue(old['identity']['snapshot_captured']);self.assertFalse(old['identity']['publisher_version_known'])
    def test_original_bytes_remain_after_bad_text_or_pdf_parser(self):
        c,d,r=self.acquired();original=self.repo.load('artifact',r['artifact_ref']['id'])
        blocked=self.acq.extract(r['artifact_ref'],source_revision_ref=r['source_revision_ref'],parser='pdf-pypdf',idempotency_key='pdf')
        self.assertEqual(blocked['status'],'blocked');self.assertTrue(blocked['original_retained']);self.assertEqual(self.repo.read_blob(original['artifact_digest']),b'original text')
    def test_size_limit_partial_and_no_false_fulltext(self):
        c=self.saved('large file');p=self.acq.plan_file(c['id'],filename='large.bin',max_bytes=4,idempotency_key='p')
        r=self.acq.execute_file(p['id'],b'0123456789',idempotency_key='r');self.assertEqual(r['status'],'partial')
        a=self.repo.load('artifact',r['artifact_ref']['id']);self.assertEqual(self.repo.read_blob(a['artifact_digest']),b'0123')
        with self.assertRaises(ValueError):self.acq.extract(r['artifact_ref'],coverage='fulltext',idempotency_key='overclaim')
        self.assertEqual(len(self.capture.list()),1)
    def test_url_host_permission_query_and_failed_retry(self):
        c=self.saved('https://example.org/page?q=keep&v=2');calls=[]
        def fetch(url,limit):calls.append(url);return {'status':200,'headers':{'Content-Type':'text/plain'},'body':b'original','final_url':url}
        acq=AcquisitionService(self.repo,fetch=fetch);p=acq.plan_url(c['id'],c['input'],idempotency_key='url-plan')
        denied=acq.execute_url(p['id'],idempotency_key='denied');self.assertEqual(denied['status'],'blocked');self.assertFalse(calls)
        result=acq.execute_url(p['id'],allowed_hosts=['example.org'],idempotency_key='approved');self.assertEqual(result['status'],'available');self.assertEqual(calls,[c['input']])
        self.assertEqual(acq.execute_url(p['id'],allowed_hosts=['example.org'],idempotency_key='approved'),result);self.assertEqual(len(calls),1)
    def test_redirect_cross_host_and_network_failure_preserve_capture(self):
        c=self.saved('https://example.org/a')
        def redirect(url,limit):return {'status':302,'headers':{'Location':'https://private.invalid/secret'},'body':b'','final_url':url}
        a=AcquisitionService(self.repo,fetch=redirect);p=a.plan_url(c['id'],c['input'],idempotency_key='p')
        self.assertEqual(a.execute_url(p['id'],allowed_hosts=['example.org'],idempotency_key='redirect')['status'],'blocked')
        def fail(url,limit):raise OSError('synthetic offline')
        a.fetch=fail;r=a.execute_url(p['id'],allowed_hosts=['example.org'],idempotency_key='network-fail');self.assertEqual(r['status'],'blocked');self.assertIsNone(r['artifact_ref']);self.assertEqual(self.capture.get(c['id'])['capture']['id'],c['id'])
    def test_http_partial_response_keeps_range_not_fulltext(self):
        c=self.saved('https://example.org/partial')
        def fetch(url,limit):return {'status':206,'headers':{'Content-Range':'bytes 0-3/100'},'body':b'part','final_url':url}
        a=AcquisitionService(self.repo,fetch=fetch);p=a.plan_url(c['id'],c['input'],idempotency_key='p')
        r=a.execute_url(p['id'],allowed_hosts=['example.org'],idempotency_key='r')
        self.assertEqual(r['status'],'partial');self.assertFalse(r['original_complete']);self.assertEqual(r['obtained_range'],'bytes 0-3/100')
        self.assertEqual(r['stored_byte_digest'],self.repo.load('artifact',r['artifact_ref']['id'])['artifact_digest'])
        with self.assertRaises(ValueError):a.extract(r['artifact_ref'],coverage='fulltext',idempotency_key='false-fulltext')
    def test_interrupted_transport_no_automatic_reentry(self):
        c=self.saved('https://example.org/a');calls=[]
        def interrupted(url,limit):calls.append(url);raise KeyboardInterrupt()
        a=AcquisitionService(self.repo,fetch=interrupted);p=a.plan_url(c['id'],c['input'],idempotency_key='p')
        with self.assertRaises(KeyboardInterrupt):a.execute_url(p['id'],allowed_hosts=['example.org'],idempotency_key='exec')
        state=a.execute_url(p['id'],allowed_hosts=['example.org'],idempotency_key='exec');self.assertEqual(state['status'],'indeterminate');self.assertFalse(state['automatic_retry']);self.assertEqual(len(calls),1)
    def test_cancel_preserves_receipts_and_explicit_new_plan_retry(self):
        c=self.saved('selected file');p=self.acq.plan_file(c['id'],filename='a.txt',idempotency_key='p')
        first=self.acq.execute_file(p['id'],b'original',idempotency_key='first')
        self.acq.cancel(p['id'],idempotency_key='cancel')
        self.assertEqual(self.acq.execute_file(p['id'],b'original',idempotency_key='first'),first)
        with self.assertRaises(ValueError):self.acq.execute_file(p['id'],b'new',idempotency_key='after-cancel')
        next_plan=self.acq.plan_file(c['id'],filename='a.txt',idempotency_key='new-plan')
        self.assertEqual(self.acq.execute_file(next_plan['id'],b'new',idempotency_key='new-attempt')['status'],'available')
        state=self.acq.inspect(c['id']);self.assertEqual(len(state['attempts']),2)
        self.assertEqual(self.repo.read_blob(self.repo.load('artifact',first['artifact_ref']['id'])['artifact_digest']),b'original')
    def test_cancellation_during_transport_retains_returned_bytes(self):
        c=self.saved('https://example.org/a');a=AcquisitionService(self.repo)
        p=a.plan_url(c['id'],c['input'],idempotency_key='p')
        def fetch(url,limit):
            a.cancel(p['id'],idempotency_key='cancel-inflight')
            return {'status':200,'headers':{},'body':b'returned original','final_url':url}
        a.fetch=fetch;r=a.execute_url(p['id'],allowed_hosts=['example.org'],idempotency_key='exec')
        self.assertEqual(r['status'],'cancelled');self.assertIsNotNone(r['artifact_ref']);self.assertEqual(len(a.inspect(c['id'])['attempts']),2)
    def test_old_excerpt_reanchor_is_only_proposal(self):
        c,d,r=self.acquired();a=self.repo.load('artifact',r['artifact_ref']['id'])
        excerpt=record('excerpt',{'target_ref':r['source_revision_ref'],'representation_ref':ref(a),'selector':'original','comment':'old quote'});self.repo.apply(command(excerpt))
        with self.repo.transaction():new=self.acq._artifact(b'original and original','text/plain',source_revision_ref=r['source_revision_ref'])
        result=self.acq.reanchor(ref(excerpt),ref(new));self.assertEqual(result['status'],'ambiguous');self.assertFalse(result['old_excerpt_modified'])
        self.assertEqual(self.repo.load('excerpt',excerpt['id'])['representation_ref'],ref(a))

if __name__=='__main__':unittest.main()
