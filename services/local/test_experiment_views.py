"""Actual native jobs -> fixed typed records, no network/provider."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from schemas.validate import validate_command
from services.local.jobs import JobManager,TERMINAL
from services.local.repository import Repository
from services.local.experiment_views import ExperimentViewService

PROJECT=Path(__file__).resolve().parents[2]
P8={'study':'observation-contract-study','operation':'run','parameters':{'operation':'search-pair','model':'score-weighted','left':'revision','right':'scope'}}
P9={'study':'conditional-contribution-study','operation':'run','parameters':{'limit':2}}
class ExperimentViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('AMS_LAB_TEST_ROOT'));self.root=Path(self.tmp.name)/'data'
        self.repo=Repository(self.root,PROJECT,validate_command);self.manager=JobManager(self.repo,PROJECT)
        self.views=ExperimentViewService(self.repo,PROJECT,self.manager)
    def tearDown(self):self.manager.close();self.repo.close();self.tmp.cleanup()
    def execute(self,plan):
        jid=self.manager.submit(plan,idempotency_key='test-'+str(len(self.manager.list())))['id'];end=time.monotonic()+15
        while time.monotonic()<end:
            job=self.manager.get(jid)
            if job['state'] in TERMINAL:
                self.assertEqual(job['state'],'succeeded');return job
            time.sleep(.02)
        self.fail('native worker timeout')
    def test_p8_actual_sources_pinned_and_idempotent(self):
        job=self.execute(P8);a=self.views.snapshot(job['id']);b=self.views.snapshot(job['id'])
        self.assertEqual(a['run_ref'],b['run_ref']);self.assertEqual(len(self.repo.list('run')),1)
        self.assertEqual(a['run']['executor'],'finite-exact');self.assertIsNone(a['analysis'])
        artifact=self.repo.load(**{k:a['run']['code_ref'][k] for k in ('kind','id','revision')})
        self.assertEqual(self.repo.read_blob(artifact['artifact_digest']),(PROJECT/'research/observation-contract-study/study.py').read_bytes())
        self.assertEqual(a['interpretation']['state'],'not-recorded')
    def test_p9_analysis_separate_restart_and_native_missing(self):
        job=self.execute(P9);a=self.views.snapshot(job['id']);self.assertNotEqual(a['run_ref'],a['analysis_ref'])
        self.manager.close();self.repo.close()
        native=self.root/'jobs'/job['id']/'attempt-1/native'
        receipt=next((native/'attempts').glob('*/*/receipt.json'));receipt.rename(receipt.with_suffix('.missing'))
        self.repo=Repository(self.root,PROJECT,validate_command);self.manager=JobManager(self.repo,PROJECT);self.views=ExperimentViewService(self.repo,PROJECT,self.manager)
        b=self.views.snapshot(job['id']);self.assertEqual(a['run_ref'],b['run_ref']);self.assertIn('not-performed',b['raw_revalidation'])
        with self.assertRaises(ValueError):self.manager.evidence(job['id'])
    def test_corrupt_native_before_pin_rejected_no_partial_records(self):
        job=self.execute(P9);native=self.root/'jobs'/job['id']/'attempt-1/native'
        receipt=next((native/'attempts').glob('*/*/receipt.json'));r=json.loads(receipt.read_text());r['raw_response']='tampered';receipt.write_text(json.dumps(r))
        with self.assertRaises(ValueError):self.views.snapshot(job['id'])
        self.assertEqual(self.repo.list('run'),[]);self.assertEqual(self.repo.list('artifact'),[])
    def test_corrupt_fixed_blob_rejected_on_reopen(self):
        job=self.execute(P8);snapshot=self.views.snapshot(job['id']);r=snapshot['run']['config_ref'];a=self.repo.load(r['kind'],r['id'],r['revision'])
        path=self.repo.blob_path(a['artifact_digest']) if hasattr(self.repo,'blob_path') else None
        # Locate only the owned test blob using Repository's actual CAS layout.
        if path is None:
            matches=[p for p in self.repo.blob_root.rglob('*') if p.is_file() and p.read_bytes()==self.repo.read_blob(a['artifact_digest'])]
            self.assertEqual(len(matches),1);path=matches[0]
        path.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.views.snapshot(job['id'])
    def test_prepare_and_history_cannot_become_new_run(self):
        for plan in ({'study':'conditional-contribution-study','operation':'prepare'},{'study':'c2c-cache-retraction-study','operation':'inspect'}):
            job=self.execute(plan)
            with self.assertRaises(ValueError):self.views.snapshot(job['id'])
        self.assertEqual(self.repo.list('run'),[])
    def test_historical_receipt_pin_is_exact_reusable_and_never_a_run(self):
        job=self.execute({'study':'c2c-cache-retraction-study','operation':'inspect'})
        first=self.views.history_snapshot(job['id']);again=self.views.history_snapshot(job['id'])
        self.assertEqual(first['artifact_ref'],again['artifact_ref']);self.assertEqual(first['kind'],'historical-inspection');self.assertIsNone(first['run_ref'])
        self.assertEqual(self.repo.list('run'),[]);self.assertEqual(self.repo.list('analysis'),[])
        artifact=first['artifact'];raw=json.loads(self.repo.read_blob(artifact['artifact_digest']))
        self.assertFalse(raw['new_execution']);self.assertIn('Early full tensors',raw['missing_raw'])
        self.assertFalse(raw['result']['result']['execution_history']['reviewed_float32']['summary']['causal_query_controls_pass'])
        with self.assertRaises(ValueError):self.views.history_snapshot(self.execute(P8)['id'])
    def test_finite_runner_without_protocol_document_binds_actual_executable(self):
        job=self.execute({'study':'task-relative-sufficiency','operation':'run'})
        saved=self.views.snapshot(job['id']);self.assertEqual(saved['run']['protocol_ref'],saved['run']['code_ref'])
        config=saved['run']['config_ref'];a=self.repo.load(config['kind'],config['id'],config['revision'])
        self.assertIn('no separate protocol document',json.loads(self.repo.read_blob(a['artifact_digest']))['protocol_binding'])

if __name__=='__main__':unittest.main()
