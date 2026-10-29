"""Actual local workers, repository-owned migration and lifecycle failure checks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from services.local.repository import Repository, RepositoryError, restore
from services.local.jobs import JobManager,TERMINAL

PROJECT=Path(__file__).resolve().parents[2]
P8={'study':'observation-contract-study','operation':'run','parameters':{'operation':'search-pair','model':'score-weighted','left':'revision','right':'scope'}}
P9={'study':'conditional-contribution-study','operation':'run','parameters':{'limit':2}}

class JobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'data'
        self.repo=Repository(self.root,PROJECT,lambda command:None)
        self.manager=JobManager(self.repo,PROJECT)
    def tearDown(self):
        self.manager.close();self.repo.close();self.tmp.cleanup()
    def wait(self,jid):
        end=time.monotonic()+15
        while time.monotonic()<end:
            j=self.manager.get(jid,False)
            if j['state'] in TERMINAL:return self.manager.get(jid)
            time.sleep(.02)
        self.fail('worker did not finish')
    def test_real_p8_duplicate_and_conflicting_submit(self):
        j=self.manager.submit(P8,idempotency_key='one')
        same=self.manager.submit(P8,idempotency_key='one');self.assertEqual(j['id'],same['id'])
        with self.assertRaises(ValueError):self.manager.submit(P9,idempotency_key='one')
        done=self.wait(j['id']);self.assertEqual(done['state'],'succeeded')
        self.assertEqual(done['result']['result']['result']['word'],['prepare','inspect'])
        self.assertEqual(len(done['attempts']),1)
    def test_real_p9_and_owned_replay(self):
        j=self.wait(self.manager.submit(P9,idempotency_key='run')['id']);self.assertEqual(j['state'],'succeeded')
        e=self.manager.evidence(j['id']);self.assertEqual(len(e['stages']),2)
        p={'study':'conditional-contribution-study','operation':'replay','source_job':j['id']}
        checked=self.wait(self.manager.submit(p,idempotency_key='replay')['id']);self.assertEqual(checked['state'],'succeeded')
        with self.assertRaises(ValueError):self.manager.submit({**p,'source_job':'/etc/passwd'},idempotency_key='bad')
    def test_backup_restores_native_bytes_and_replays_from_new_root(self):
        j=self.wait(self.manager.submit(P9,idempotency_key='backup-run')['id'])
        expected=self.manager.evidence(j['id'])
        backup=Path(self.tmp.name)/'backup';destination=Path(self.tmp.name)/'restored'
        manifest=self.repo.backup(backup)
        self.assertEqual(manifest['schema'],'ams-backup/2')
        self.assertTrue(any('/native/' in item['path'] for item in manifest['job_files']))
        self.assertFalse(any('.owner.lock' in item['path'] for item in manifest['job_files']))
        self.assertTrue(restore(backup,destination,PROJECT,lambda c:None)['ok'])
        restored=Repository(destination,PROJECT,lambda c:None);manager=JobManager(restored,PROJECT)
        try:
            self.assertEqual(manager.evidence(j['id']),expected)
            replay=manager.submit({'study':'conditional-contribution-study','operation':'replay','source_job':j['id']},idempotency_key='restored-replay')
            self.assertEqual(manager.wait(replay['id'])['state'],'succeeded')
        finally:
            manager.close();restored.close()
        raw=next(item for item in manifest['job_files'] if '/native/' in item['path'])
        (backup/raw['path']).write_bytes(b'corrupted original')
        with self.assertRaisesRegex(RepositoryError,'损坏'):
            restore(backup,Path(self.tmp.name)/'corrupt-restore',PROJECT,lambda c:None)
        self.assertFalse((Path(self.tmp.name)/'corrupt-restore').exists())
        manifest['schema']='ams-backup/1';manifest.pop('job_files')
        (backup/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(RepositoryError,'旧格式'):
            restore(backup,Path(self.tmp.name)/'legacy-restore',PROJECT,lambda c:None)
    def test_backup_refuses_live_attempt_and_path_escape(self):
        # Hold the worker lock so this is deterministically a pending attempt.
        with self.manager.cv:
            j=self.manager.submit(P8,idempotency_key='pending-backup')
            with self.assertRaises(RepositoryError) as error:self.repo.backup(Path(self.tmp.name)/'live-backup')
            self.assertEqual(error.exception.code,'backup-active-jobs')
        self.wait(j['id'])
        backup=Path(self.tmp.name)/'safe-backup';manifest=self.repo.backup(backup)
        manifest['job_files'][0]['path']=f"jobs/{j['id']}/attempt-1/../../outside"
        (backup/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(RepositoryError):restore(backup,Path(self.tmp.name)/'escaped',PROJECT,lambda c:None)
        self.assertFalse((Path(self.tmp.name)/'escaped').exists())
    def test_cancel_and_explicit_idempotent_retry(self):
        j=self.manager.submit({'study':'conditional-contribution-study','operation':'run'},idempotency_key='cancel')
        self.manager.cancel(j['id']);done=self.wait(j['id']);self.assertEqual(done['state'],'cancelled')
        self.manager.retry(j['id'],idempotency_key='retry')
        self.manager.retry(j['id'],idempotency_key='retry')
        done=self.wait(j['id']);self.assertEqual(done['state'],'succeeded');self.assertEqual(len(done['attempts']),2)
        self.assertEqual(done['attempts'][0]['state'],'cancelled')
    def test_close_waits_and_preserves_partial(self):
        j=self.manager.submit({'study':'conditional-contribution-study','operation':'run'},idempotency_key='shutdown')
        self.manager.close();done=self.manager.get(j['id'],False)
        self.assertEqual(done['state'],'interrupted');self.assertFalse(self.manager.thread.is_alive())
        self.manager=JobManager(self.repo,PROJECT)
        self.assertEqual(self.manager.get(j['id'],False)['state'],'interrupted')
    def test_exclusive_manager_and_no_private_logs(self):
        with self.assertRaisesRegex(ValueError,'owns'):JobManager(self.repo,PROJECT)
        j=self.wait(self.manager.submit(P8,idempotency_key='log')['id'])
        log=self.root/'jobs'/j['id']/'attempt-1/status.log'
        self.assertLess(log.stat().st_size,100)
        self.assertNotIn('messages',log.read_text())
    def test_unknown_submission_never_automatically_retries(self):
        j=self.wait(self.manager.submit(P8,idempotency_key='unknown')['id'])
        with self.repo.transaction():self.manager._state(j['id'],1,'indeterminate',error='Synthetic unknown provider submission; not a live call.')
        with self.assertRaises(ValueError):self.manager.retry(j['id'],idempotency_key='forbidden')
        self.assertEqual(len(self.manager.get(j['id'],False)['attempts']),1)
    def test_result_and_native_receipt_corruption_rejected(self):
        j=self.wait(self.manager.submit(P9,idempotency_key='native-corrupt')['id']);work=self.root/'jobs'/j['id']/'attempt-1'
        rp=next((work/'native/attempts').glob('*/*/receipt.json'));value=json.loads(rp.read_text());value['raw_response']='tampered';rp.write_text(json.dumps(value))
        with self.assertRaises(ValueError):self.manager.evidence(j['id'])
        (work/'result.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'corrupted'):self.manager.get(j['id'])
    def test_timeout_not_success(self):
        self.manager.close();self.manager=JobManager(self.repo,PROJECT,timeout=0)
        j=self.wait(self.manager.submit(P9,idempotency_key='timeout')['id']);self.assertEqual(j['state'],'interrupted')
    def test_killed_previous_owner_recovery(self):
        # Real abrupt parent exit; child process identity must be reconciled.
        self.manager.close();self.repo.close()
        script='''import os,sys,time
from services.local.repository import Repository
from services.local.jobs import JobManager
r=Repository(sys.argv[1],sys.argv[2],lambda c:None);m=JobManager(r,sys.argv[2])
j=m.submit({'study':'conditional-contribution-study','operation':'run'},idempotency_key='killed')
while m.get(j['id'],False)['state'] not in ('running','succeeded','failed'):time.sleep(.01)
print(j['id'],flush=True);os._exit(0)
'''
        proc=subprocess.run([sys.executable,'-B','-c',script,str(self.root),str(PROJECT)],cwd=PROJECT,capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr);jid=proc.stdout.strip()
        self.repo=Repository(self.root,PROJECT,lambda c:None);self.manager=JobManager(self.repo,PROJECT)
        self.assertEqual(self.manager.get(jid,False)['state'],'interrupted')
        self.assertEqual(len(self.manager.get(jid,False)['attempts']),1)

if __name__=='__main__':unittest.main()
