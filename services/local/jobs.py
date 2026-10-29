"""Durable local job ownership. Repository alone owns SQL migration/versioning."""
from __future__ import annotations
from collections import deque
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import uuid
from . import studies
from .repository import encoded, now

JOBS_MIGRATION_SQL = (
 'CREATE TABLE execution_jobs (id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)',
 'CREATE TABLE execution_attempts (job_id TEXT NOT NULL REFERENCES execution_jobs(id), number INTEGER NOT NULL, owner TEXT NOT NULL, state TEXT NOT NULL, started_at TEXT, ended_at TEXT, error TEXT, result_digest TEXT, PRIMARY KEY(job_id,number))',
 'CREATE TABLE execution_retries (idempotency_key TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES execution_jobs(id), number INTEGER NOT NULL)',
)
TERMINAL={'succeeded','failed','cancelled','interrupted','indeterminate','blocked'}

class JobManager:
    def __init__(self,repo,project,*,timeout=300):
        self.repo=repo;self.project=Path(project).resolve();self.root=repo.root/'jobs'
        if self.root.resolve().is_relative_to(self.project):raise ValueError('jobs require private data root')
        self.root.mkdir(exist_ok=True,mode=0o700);self.owner=str(uuid.uuid4());self.timeout=timeout
        self._lease=(self.root/'.owner.lock').open('a')
        try:fcntl.flock(self._lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self._lease.close();raise ValueError('another JobManager owns this data root') from None
        self.cv=threading.Condition();self.queue=deque();self.closed=False;self.process=None;self.active=None;self.cancelled=set()
        try:
            # Verify migration exists; never CREATE or set user_version here.
            with repo.transaction():
                rows=repo.db.execute("SELECT job_id,number,state FROM execution_attempts WHERE state NOT IN ('succeeded','failed','cancelled','interrupted','indeterminate','blocked')").fetchall()
                for row in rows:
                    self._recover_process(self._attempt_path(row['job_id'],row['number']))
                    self._state(row['job_id'],row['number'],'interrupted',error='Previous owner exited; explicit retry required.')
            self.thread=threading.Thread(target=self._loop,name='ams-local-jobs',daemon=True);self.thread.start()
        except BaseException:
            fcntl.flock(self._lease,fcntl.LOCK_UN);self._lease.close();raise

    @staticmethod
    def _recover_process(work):
        path=work/'process.json'
        if not path.exists():return
        data=json.loads(path.read_text());pid=data['pid']
        if type(pid) is not int or pid<=1:return
        def same():
            info=subprocess.run(['ps','-p',str(pid),'-o','lstart='],capture_output=True,text=True)
            return info.returncode==0 and info.stdout.strip()==data['birth']
        if same():
            try:os.killpg(pid,signal.SIGTERM)
            except ProcessLookupError:return
            deadline=time.monotonic()+1
            while same() and time.monotonic()<deadline:time.sleep(.02)
            if same():
                try:os.killpg(pid,signal.SIGKILL)
                except ProcessLookupError:pass

    def registry(self):return studies.registry()
    def _state(self,jid,n,state,error=None,result_digest=None):
        self.repo.db.execute('UPDATE execution_attempts SET state=?,ended_at=?,error=?,result_digest=? WHERE job_id=? AND number=?',
                             (state,now() if state in TERMINAL else None,error,result_digest,jid,n))
        self.repo.db.execute('UPDATE execution_jobs SET state=?,updated_at=? WHERE id=?',(state,now(),jid))
    def _attempt_path(self,jid,n):
        return self.root/jid/f'attempt-{n}'
    def submit(self,plan,*,idempotency_key):
        plan=studies.validate_plan(self.project,plan)
        if not isinstance(idempotency_key,str) or not 1<=len(idempotency_key)<=200:raise ValueError('invalid idempotency key')
        payload=encoded(plan)
        with self.cv:
            if self.closed:raise ValueError('JobManager closed')
            with self.repo.transaction():
                old=self.repo.db.execute('SELECT id,payload FROM execution_jobs WHERE idempotency_key=?',(idempotency_key,)).fetchone()
                if old:
                    if old['payload']!=payload:raise ValueError('idempotency payload conflict')
                    return self.get(old['id'])
                if plan['operation']=='replay':self._source(plan)
                jid=str(uuid.uuid4());stamp=now()
                self.repo.db.execute('INSERT INTO execution_jobs VALUES (?,?,?,?,?,?)',(jid,idempotency_key,payload,'queued',stamp,stamp))
                self.repo.db.execute('INSERT INTO execution_attempts VALUES (?,?,?,?,?,?,?,?)',(jid,1,self.owner,'queued',None,None,None,None))
            self.queue.append((jid,1));self.cv.notify()
        return self.get(jid)
    def _source(self,plan):
        source=self.get(plan['source_job'],include_result=False)
        if source['state']!='succeeded' or source['plan']['study']!=plan['study'] or source['plan']['operation']!='run':raise ValueError('replay requires successful same-owner study run')
        return self._attempt_path(source['id'],source['attempts'][-1]['number'])/'native'
    def list(self):
        with self.repo.lock:
            return [dict(r) for r in self.repo.db.execute('SELECT id,state,created_at,updated_at FROM execution_jobs ORDER BY created_at DESC')]
    def get(self,jid,include_result=True):
        with self.repo.lock:
            row=self.repo.db.execute('SELECT * FROM execution_jobs WHERE id=?',(jid,)).fetchone()
            if row is None:raise ValueError('unknown job')
            result=dict(row);result['plan']=json.loads(result.pop('payload'));result.pop('idempotency_key')
            result['attempts']=[dict(r) for r in self.repo.db.execute('SELECT * FROM execution_attempts WHERE job_id=? ORDER BY number',(jid,))]
        if include_result and result['attempts'] and result['state']=='succeeded':
            last=result['attempts'][-1];p=self._attempt_path(jid,last['number'])/'result.json'
            raw=p.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=last['result_digest']:raise ValueError('job result corrupted')
            result['result']=json.loads(raw)
        return result
    def cancel(self,jid):
        with self.cv:
            job=self.get(jid,False);n=job['attempts'][-1]['number']
            if job['state'] in TERMINAL:return job
            self.cancelled.add((jid,n))
            with self.repo.transaction():self._state(jid,n,'cancel-requested')
            if self.active==(jid,n) and self.process:self._terminate(self.process)
            self.cv.notify()
        return self.get(jid)
    def retry(self,jid,*,idempotency_key):
        if not isinstance(idempotency_key,str) or not 1<=len(idempotency_key)<=200:raise ValueError('invalid retry key')
        with self.cv:
            if self.closed:raise ValueError('JobManager closed')
            with self.repo.transaction():
                old=self.repo.db.execute('SELECT job_id,number FROM execution_retries WHERE idempotency_key=?',(idempotency_key,)).fetchone()
                if old:
                    if old['job_id']!=jid:raise ValueError('retry key conflict')
                    return self.get(jid)
                job=self.get(jid,False)
                if job['state'] not in {'failed','cancelled','interrupted','blocked'}:raise ValueError('job not explicitly retryable; indeterminate requires reconciliation')
                n=job['attempts'][-1]['number']+1
                self.repo.db.execute('INSERT INTO execution_attempts VALUES (?,?,?,?,?,?,?,?)',(jid,n,self.owner,'queued',None,None,None,None))
                self.repo.db.execute('INSERT INTO execution_retries VALUES (?,?,?)',(idempotency_key,jid,n))
                self.repo.db.execute('UPDATE execution_jobs SET state=?,updated_at=? WHERE id=?',('queued',now(),jid))
            self.queue.append((jid,n));self.cv.notify()
        return self.get(jid)
    @staticmethod
    def _terminate(process):
        if process.poll() is None:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
    def _loop(self):
        while True:
            with self.cv:
                while not self.queue and not self.closed:self.cv.wait()
                if self.closed:return
                jid,n=self.queue.popleft();self.active=(jid,n)
            try:self._execute(jid,n)
            except BaseException as exc:
                with self.repo.transaction():self._state(jid,n,'failed',error=type(exc).__name__+': worker boundary failure')
            finally:
                with self.cv:self.active=None;self.process=None;self.cv.notify_all()
    def _execute(self,jid,n):
        with self.cv:
            if (jid,n) in self.cancelled or self.closed:
                with self.repo.transaction():self._state(jid,n,'cancelled' if not self.closed else 'interrupted')
                return
            with self.repo.transaction():
                self._state(jid,n,'preparing')
                self.repo.db.execute('UPDATE execution_attempts SET started_at=? WHERE job_id=? AND number=?',(now(),jid,n))
            job=self.get(jid,False);plan=job['plan'];work=self._attempt_path(jid,n);work.mkdir(parents=True,mode=0o700)
            source=self._source(plan) if plan['operation']=='replay' else None
            (work/'plan.json').write_text(encoded(plan));(work/'status.log').write_text('preparing\n')
            argv=[sys.executable,'-B','-m','services.local.studies','--project',str(self.project),'--work',str(work),'--plan',str(work/'plan.json')]
            if source:argv+=['--source',str(source)]
            # Keep the parent's selected runtime libraries (not provider credentials).
            # Otherwise Linux workers can silently load a different SQLite build.
            env={key:os.environ[key] for key in ('LD_LIBRARY_PATH','DYLD_LIBRARY_PATH','DYLD_FALLBACK_LIBRARY_PATH') if key in os.environ}
            env.update({'PATH':os.defpath,'PYTHONPATH':str(self.project),'PYTHONIOENCODING':'utf-8'})
            self.process=subprocess.Popen(argv,cwd=self.project,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            process=self.process
            deadline=time.monotonic()+3
            while not (work/'process.json').exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.01)
            if (work/'process.json').exists():(work/'launch.json').write_text('{}')
            else:self._terminate(process)
            with self.repo.transaction():self._state(jid,n,'running')
        started=time.monotonic();timed_out=False
        while process.poll() is None:
            with self.cv:stop=self.closed or (jid,n) in self.cancelled
            if stop or time.monotonic()-started>self.timeout:
                timed_out=not stop;self._terminate(process)
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait()
                break
            time.sleep(.02)
        code=process.wait()
        with self.cv:
            if self.closed:state='interrupted';error='Owner shutdown; partial artifacts retained.'
            elif (jid,n) in self.cancelled:state='cancelled';error='Process group terminated.'
            elif timed_out:state='interrupted';error='Local execution timeout; explicit retry required.'
            elif code:
                failure=json.loads((work/'failure.json').read_text()) if (work/'failure.json').exists() else {}
                state='blocked' if failure.get('state')=='blocked' else 'failed'
                error=f"Native worker exit {code}; {failure.get('code','worker-exit')}; {failure.get('error_type','unknown')}; partial artifacts retained."
            else:
                try:
                    raw=(work/'result.json').read_bytes();result=json.loads(raw)
                    if result.get('schema')!='ams-local-study-result/1' or result['study']!=plan['study'] or result['operation']!=plan['operation']:raise ValueError('invalid envelope')
                    state='succeeded';error=None
                except (OSError,ValueError,KeyError):state='failed';error='Successful process lacks valid bound result.'
            identity=hashlib.sha256(raw).hexdigest() if state=='succeeded' else None
            # Terminal DB state makes the attempt eligible for a consistent backup.
            # Finish its last write before exposing that state to another connection.
            with (work/'status.log').open('a') as log:
                log.write(state+'\n');log.flush();os.fsync(log.fileno())
            with self.repo.transaction():self._state(jid,n,state,error,identity)
    def evidence(self,jid):
        job=self.get(jid)
        if job['state']!='succeeded':return {'state':job['state'],'stages':[],'missing_raw':True,'interpretation':{'state':'not-recorded'}}
        work=self._attempt_path(jid,job['attempts'][-1]['number'])
        if job['result']['source_bindings']!=studies.bindings(self.project,job['plan']['study']):raise ValueError('research source drift; keep old result but cannot revalidate as current')
        if job['result']['run']['native_artifacts']:
            observed=studies.validate_artifacts(self.project,job['plan']['study'],work/'native')
            saved=job['result']['result']
            if job['plan']['study']=='conditional-contribution-study':saved=saved['result']
            if observed!=saved:raise ValueError('native evidence no longer matches the completed result; preserve history and restore missing raw artifacts')
        return studies.evidence(work,job['result'])
    def wait(self,jid):
        """CLI owns the worker until a durable terminal state, without busy polling."""
        with self.cv:
            while True:
                job=self.get(jid)
                if job['state'] not in ('queued','preparing','running'):return job
                if self.closed:raise ValueError('execution owner closed before job completed')
                self.cv.wait()
    def close(self):
        with self.cv:
            if self.closed:return
            self.closed=True
            if self.process:self._terminate(self.process)
            queued=list(self.queue);self.queue.clear()
            for jid,n in queued:
                with self.repo.transaction():self._state(jid,n,'interrupted',error='Owner shutdown before execution.')
            self.cv.notify_all()
        self.thread.join()
        fcntl.flock(self._lease,fcntl.LOCK_UN);self._lease.close()
