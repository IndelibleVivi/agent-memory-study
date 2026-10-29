"""Explicitly pin owned successful native jobs to canonical scientific records.

The job lifecycle remains JobManager's responsibility. No new run is executed,
no interpretation is inferred, and historical inspection is never a Run.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from .records import record, command, ref
from .repository import RepositoryError, encoded, now

class ExperimentViewService:
    def __init__(self, repo, project, jobs):
        self.repo, self.project, self.jobs = repo, Path(project).resolve(), jobs

    def history_snapshot(self, job_id):
        """Pin a real historical inspection receipt without inventing an execution."""
        job=self.jobs.get(job_id,include_result=False)
        if job['state']!='succeeded' or job['plan']['study'] not in ('c2c-cache-retraction-study','decision-learning-study') or job['plan']['operation'] not in ('inspect','check-saved-results'):
            raise ValueError('only a successful registered historical inspection can be pinned here')
        identifier='artifact:history-'+job_id
        try:artifact=self.repo.load('artifact',identifier)
        except RepositoryError as exc:
            if exc.code!='not-found':raise
        else:
            self.repo.read_blob(artifact['artifact_digest'])
            return {'kind':'historical-inspection','artifact':artifact,'artifact_ref':ref(artifact),'basis_refs':[ref(artifact)],'run_ref':None,'new_execution':False,'interpretation':{'state':'not-recorded'}}
        job=self.jobs.get(job_id);evidence=self.jobs.evidence(job_id)
        missing='Only originally saved bytes are present. '+('Early full tensors remain unavailable; no reconstruction from summary.' if job['plan']['study']=='c2c-cache-retraction-study' else 'Classifier results are historical; this inspection does not execute new training or establish unrecorded raw evidence.')
        raw=encoded({'kind':'historical-inspection','job_id':job_id,'plan':job['plan'],'result':job['result'],'evidence':evidence,'new_execution':False,'missing_raw':missing}).encode()
        with self.repo.transaction():
            try:artifact=self.repo.load('artifact',identifier)
            except RepositoryError as exc:
                if exc.code!='not-found':raise
                digest=self.repo.put_blob(raw)
                artifact=record('artifact',{'media_type':'application/json','byte_length':len(raw),'artifact_digest':digest,'storage':{'kind':'blob','locator':digest},'role':'receipt','visibility':'private','obtained_at':now()},id=identifier)
                self.repo._apply(command(artifact))
            self.repo.read_blob(artifact['artifact_digest'])
        return {'kind':'historical-inspection','artifact':artifact,'artifact_ref':ref(artifact),'basis_refs':[ref(artifact)],'run_ref':None,'new_execution':False,'interpretation':{'state':'not-recorded'}}

    def _saved(self, run):
        for pointer in [run['protocol_ref'],run['code_ref'],run['config_ref'],run['rubric_ref'],*run['dataset_refs'],*run.get('result_artifact_refs',[])]:
            artifact=self.repo.load(pointer['kind'],pointer['id'],pointer['revision'])
            self.repo.read_blob(artifact['artifact_digest'])
        analyses=[a for a in self.repo.list('analysis') if ref(run) in a['run_refs']]
        return {'run':run,'analysis':analyses[0] if analyses else None,'run_ref':ref(run),
                'analysis_ref':ref(analyses[0]) if analyses else None,'interpretation':{'state':'not-recorded'},
                'new_execution':False,'raw_revalidation':'not-performed; reopening fixed canonical bytes, not a fresh native replay'}

    def snapshot(self, job_id):
        job = self.jobs.get(job_id, include_result=False)
        if job['state'] != 'succeeded' or job['plan']['operation'] != 'run':
            raise ValueError('only a successful actual run can be pinned; prepare/inspect/history are not new runs')
        attempt = job['attempts'][-1]
        run_id = 'run:job-' + job_id + '-attempt-' + str(attempt['number'])
        # Reopen the original immutable snapshot, even after source subsequently changes.
        try:
            existing = self.repo.load('run', run_id)
        except RepositoryError as exc:
            if exc.code != 'not-found': raise
        else:
            return self._saved(existing)
        job = self.jobs.get(job_id)
        evidence = self.jobs.evidence(job_id)  # Native replay/integrity check, including source identity.
        result = job['result']
        from .studies import OWNERS
        study = job['plan']['study']
        if study not in OWNERS: raise ValueError('unknown native owner')
        root = self.project / 'research' / study
        sources = {}
        for name, expected in result['source_bindings'].items():
            if name not in ('study.py','protocol.md','corpus.py','corpus.json','fixtures.json','adapter.py'):
                raise ValueError('undeclared source binding')
            raw = (root/name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected: raise ValueError('source binding changed during snapshot')
            sources[name] = raw
        if 'study.py' not in sources: raise ValueError('native scoring/code source not recorded')
        with self.repo.transaction():
            # Concurrent explicit pin requests share exactly one canonical Run.
            try: existing = self.repo.load('run',run_id)
            except RepositoryError as exc:
                if exc.code != 'not-found': raise
            else:
                return self._saved(existing)
            def artifact(raw, role, media):
                digest = self.repo.put_blob(raw)
                value = record('artifact',{'media_type':media,'byte_length':len(raw),'artifact_digest':digest,
                    'storage':{'kind':'blob','locator':digest},'role':role,'visibility':'private','obtained_at':now()})
                self.repo._apply(command(value));return value
            fixed = {name:artifact(raw,'code' if name.endswith('.py') else 'dataset' if name.endswith('.json') else 'other','text/plain; charset=utf-8') for name,raw in sources.items()}
            config = artifact(encoded({'plan':job['plan'],'native_manifest':result['run'].get('native_manifest'),
                'completion':result['run'].get('completion'),'job_id':job_id,'attempt':attempt['number'],
                'executor':result['evidence_kind'],'used':'unknown',
                'protocol_binding':'protocol.md' if 'protocol.md' in sources else 'native executable study.py; no separate protocol document bound at execution'}).encode(),'config','application/json')
            output = artifact(encoded(result).encode(),'receipt','application/json')
            inspection = artifact(encoded(evidence).encode(),'receipt','application/json')
            code = fixed['study.py']
            run = record('run',{'protocol_ref':ref(fixed.get('protocol.md',code)),
                'code_ref':ref(code),'config_ref':ref(config),'dataset_refs':[ref(v) for k,v in fixed.items() if k in ('corpus.py','corpus.json','fixtures.json')],
                'rubric_ref':ref(code),'executor':result['evidence_kind'],
                'started_at':attempt.get('started_at') or job['created_at'],'status':'complete',
                'result_artifact_refs':[ref(output),ref(inspection)]},id=run_id)
            self.repo._apply(command(run))
            analysis = None
            if result['analysis']['state'] == 'raw-validated':
                analysis = record('analysis',{'run_refs':[ref(run)],'method':'native-owner raw replay; execution rubric preserved',
                    'scope':f"Owned job {job_id}, attempt {attempt['number']}; completion and bounds remain in config/result Artifacts.",
                    'result':encoded(result['analysis']),'observation_refs':[]})
                self.repo._apply(command(analysis))
        return {'run':run,'analysis':analysis,'run_ref':ref(run),'analysis_ref':ref(analysis) if analysis else None,
                'result_artifact_ref':ref(output),'inspection_artifact_ref':ref(inspection),
                'interpretation':{'state':'not-recorded'},'new_execution':False}
