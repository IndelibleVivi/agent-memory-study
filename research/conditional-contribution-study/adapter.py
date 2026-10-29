"""Native P9 instrument boundary; platform registry/jobs remain external owners."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('ams_conditional_native',ROOT/'study.py')
s=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s)
OPERATIONS=['report-local','run-local','replay','check-sample','provider-plan','packet']


def describe_capabilities():
    return {'id':'conditional-contribution-study','version':'1','operations':OPERATIONS,
            'native_retriever':'SQLite FTS5/BM25 via experience-reuse rank/select',
            'local_backends':['scripted','oracle'],'live_provider':False,'empirical_sample_count':0}


def validate_plan(plan):
    if not isinstance(plan,dict) or plan.get('operation') not in OPERATIONS:raise ValueError('unknown operation')
    op=plan['operation'];allowed={'operation','out','resume','limit'} if op=='run-local' else {'operation','out'} if op=='replay' else {'operation'}
    if set(plan)-allowed:raise ValueError('unknown fields')
    if op in ('run-local','replay') and not isinstance(plan.get('out'),str):raise ValueError('out required')
    if 'resume' in plan and type(plan['resume']) is not bool:raise ValueError('resume must be boolean')
    if 'limit' in plan and (type(plan['limit']) is not int or plan['limit']<0):raise ValueError('invalid limit')
    return plan


def execute(plan):
    validate_plan(plan);op=plan['operation']
    if op=='run-local':result=s.run(plan['out'],resume=plan.get('resume',False),limit=plan.get('limit'))
    elif op=='replay':result=s.replay(plan['out'])
    elif op=='provider-plan':result=s.provider_plan()
    elif op=='packet':result={'schema':'ams-conditional-packet/1','corpus':s.corpus(),'protocol':(ROOT/'protocol.md').read_text(),'results':s.load(ROOT/'sample-results.json'),'provider_plan':s.provider_plan()}
    else:
        result=s.local_report()
        if op=='check-sample':
            if result!=s.load(ROOT/'sample-results.json'):raise ValueError('sample drift')
            result={'status':'passed-local-recomputation-not-raw-replay','jobs':result['planned_jobs']}
    return {'schema':'ams-conditional-instrument/1','plan':dict(plan),'sources':s.sources(),'result':result}
