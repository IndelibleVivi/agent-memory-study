"""Fixed native research registry; executed in a disposable local worker process."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path
import sys

OWNERS = {
 'observation-contract-study': {'saved':'results.json','operations':['inspect','prepare','run','check-saved-results','packet'],'kind':'finite-exact'},
 'conditional-contribution-study': {'saved':'sample-results.json','operations':['inspect','prepare','run','replay','check-saved-results','packet'],'kind':'native-fts5-scripted-oracle'},
 'representation-use-study': {'saved':'sample-results.json','operations':['inspect','prepare','run','replay','check-saved-results','packet'],'kind':'scripted-oracle-control'},
 'revision-propagation-study': {'saved':'results.json','operations':['inspect','prepare','run','replay','check-saved-results','packet'],'kind':'typed-longitudinal-control'},
 'task-relative-sufficiency': {'saved':'results.json','operations':['inspect','prepare','run','check-saved-results','packet'],'kind':'finite-exact'},
 'c2c-cache-retraction-study': {'saved':'results.json','operations':['inspect','check-saved-results','packet'],'kind':'historical-single-model-receipt'},
 'decision-learning-study': {'saved':'results.json','operations':['inspect','packet'],'kind':'historical-classifier-receipt'},
}

def encoded(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def read(p):return json.loads(Path(p).read_text())
def digest(v):return hashlib.sha256(encoded(v).encode()).hexdigest()
def registry():return [{'id':k,'operations':v['operations'],'evidence_kind':v['kind'],'provider':False,'network':False} for k,v in OWNERS.items()]

def validate_plan(project, plan):
    if not isinstance(plan,dict) or set(plan)-{'study','operation','parameters','source_job'}:raise ValueError('unknown study plan fields')
    study,op=plan.get('study'),plan.get('operation')
    if study not in OWNERS or op not in OWNERS[study]['operations']:raise ValueError('unsupported study operation')
    params=plan.get('parameters',{})
    if not isinstance(params,dict):raise ValueError('parameters must be object')
    if op=='replay':
        if set(plan)!= {'study','operation','source_job'} or not isinstance(plan['source_job'],str):raise ValueError('replay requires owned source job ID only')
    elif 'source_job' in plan:raise ValueError('source job only for replay')
    if study=='observation-contract-study' and op=='run':
        mod=load_module(Path(project)/'research'/study/'adapter.py');mod.validate_plan(params)
        if params.get('max_steps',0) is not None and params.get('max_steps',0)>100:raise ValueError('step bound too large')
    elif op=='run':
        if set(params)-{'limit'}:raise ValueError('only bounded local limit is accepted')
        if 'limit' in params and (type(params['limit']) is not int or not 1<=params['limit']<=100):raise ValueError('limit must be 1..100')
        if study=='task-relative-sufficiency' and params:raise ValueError('finite enumeration has no run parameters')
    elif params:raise ValueError('operation takes no parameters')
    return {'study':study,'operation':op,**({'source_job':plan['source_job']} if op=='replay' else {'parameters':params})}

def load_module(path):
    spec=importlib.util.spec_from_file_location('ams_native_'+path.parent.name.replace('-','_')+'_'+path.stem,path)
    m=importlib.util.module_from_spec(spec)
    # Existing P1/P2 use native sibling imports. Worker is one owner per process.
    sys.path.insert(0,str(path.parent))
    try:spec.loader.exec_module(m)
    finally:sys.path.pop(0)
    return m

def bindings(project,study):
    root=Path(project)/'research'/study
    names=['study.py','protocol.md','corpus.py','corpus.json','fixtures.json','adapter.py']
    return {n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names if (root/n).is_file()}

def execute(project,plan,work,source=None):
    project,work=Path(project).resolve(),Path(work).resolve();plan=validate_plan(project,plan)
    if work.is_relative_to(project):raise ValueError('work must be outside repository')
    work.mkdir(parents=True,exist_ok=True)
    study,op=plan['study'],plan['operation'];root=project/'research'/study;spec=OWNERS[study]
    result=None;validation=None;native=work/'native'
    if op in ('inspect','packet'):
        result=read(root/spec['saved'])
        if study=='c2c-cache-retraction-study':result={'results':result,'execution_history':read(root/'execution-history.json'),'early_full_tensors':'not-published; not-replayable-from-summary'}
        if op=='packet':result={'owner':study,'saved':result,'protocol':(root/'protocol.md').read_text() if (root/'protocol.md').exists() else None,'capabilities':registry()[list(OWNERS).index(study)]}
    elif op=='prepare':
        result={'study':study,'source_bindings':bindings(project,study),'network':False,'provider':False,
                'operations':spec['operations'],'default_run_limit':4 if study in ('representation-use-study','revision-propagation-study') else None,
                'note':'Plan only; no research run or scientific finding.'}
        if study in ('representation-use-study','revision-propagation-study'):
            mod=load_module(root/'study.py')
            cfg=mod.settings(modes=('full',),orders=('forward',),backends=('scripted',)) if study=='representation-use-study' else mod.settings()
            result['native_plan']=mod.manifest(cfg)
        if study=='conditional-contribution-study':result['provider_plan']=load_module(root/'adapter.py').execute({'operation':'provider-plan'})['result']
    elif study=='observation-contract-study':
        adapter=load_module(root/'adapter.py')
        if op=='run':result=adapter.execute(plan['parameters'])
        else:
            mod=load_module(root/'study.py');computed=mod.run()
            if computed!=read(root/spec['saved']):raise ValueError('P8 saved result drift')
            result={'status':'checked-finite-recomputation','empirical_sample_count':0}
    elif study=='conditional-contribution-study':
        adapter=load_module(root/'adapter.py')
        if op=='run':
            params={'operation':'run-local','out':str(native)}
            if 'limit' in plan['parameters']:params['limit']=plan['parameters']['limit']
            result=adapter.execute(params)
            validation=adapter.execute({'operation':'replay','out':str(native)})
            if result['result']!=validation['result']:raise ValueError('P9 raw replay mismatch')
        elif op=='replay':result=adapter.execute({'operation':'replay','out':str(source)})
        else:result=adapter.execute({'operation':'check-sample'})
    elif study in ('representation-use-study','revision-propagation-study'):
        mod=load_module(root/'study.py')
        if op=='check-saved-results':result=mod.check_saved_sample() if study=='representation-use-study' else mod.check_saved()
        elif op=='replay':result=mod.report(Path(source)) if study=='representation-use-study' else mod.verify(Path(source))
        else:
            limit=plan['parameters'].get('limit',4)
            if study=='representation-use-study':
                cfg=mod.settings(modes=('full',),orders=('forward',),backends=('scripted',))
                result=mod.run(native,cfg,limit=limit);validation=mod.report(native)
            else:result=mod.execute(native,limit=limit);validation=mod.verify(native)
            if result!=validation:raise ValueError('native raw validation mismatch')
    elif study=='task-relative-sufficiency':
        mod=load_module(root/'study.py');result=mod.run(mod.load_fixtures())
        if op=='check-saved-results' and result!=read(root/spec['saved']):raise ValueError('finite saved results differ')
    elif study=='c2c-cache-retraction-study':result=load_module(root/'study.py').verify_receipt(read(root/spec['saved']))
    original_manifest=read(Path(source)/'manifest.json') if source and (Path(source)/'manifest.json').exists() else None
    native_manifest=read(native/'manifest.json') if (native/'manifest.json').exists() else None
    scientific=result.get('result',result) if isinstance(result,dict) else {}
    completion={k:scientific[k] for k in ('planned_requests','successful_jobs','unexecuted','planned_episodes','executed_episodes','unexecuted_episodes','execution_state','planned_jobs','attempt_count','pending_attempts') if k in scientific}
    envelope={'schema':'ams-local-study-result/1','study':study,'operation':op,'evidence_kind':spec['kind'],
              'source_bindings':bindings(project,study),'result':result,'native_validation':validation,
              'run':{'state':'executed-local' if op=='run' else 'not-new-execution','native_artifacts':native.exists(),'id':work.parent.name+'/'+work.name,'plan_digest':digest(plan),'source_bindings':bindings(project,study),'native_manifest':native_manifest,'completion':completion},
              'analysis':{'state':'raw-validated' if validation is not None or op=='replay' else 'not-recorded','input_run_ref':plan.get('source_job') if op=='replay' else (work.parent.name+'/'+work.name if op=='run' else None),'original_manifest':original_manifest,'scorer_policy':'native owner; execution rubric not rewritten'},
              'interpretation':{'state':'not-recorded'},'used':'unknown'}
    return envelope

def validate_artifacts(project,study,native):
    root=Path(project)/'research'/study
    mod=load_module(root/'study.py')
    if study=='conditional-contribution-study':return mod.replay(native)
    if study=='representation-use-study':return mod.report(native)
    if study=='revision-propagation-study':return mod.verify(native)
    return None

def evidence(work,result):
    """Unify only stage labels; retain native values, no synthesized gold or use."""
    work=Path(work);items=[]
    for rp in sorted((work/'native'/'attempts').glob('*/*/receipt.json')):
        r=read(rp)
        if 'start' in r: # P9 native embedded request/response.
            items.append({'locator':rp.relative_to(work).as_posix(),'request':r['start'].get('request'),
                          'delivered':r['start'].get('audit'),'response':r.get('raw_response'),'score':r.get('score'),'status':r.get('status')})
        else: # P1 bound artifacts, after owner replay validated them.
            native=work/'native'
            def bound(ref):
                if ref is None:return None
                p=(native/ref['path']).resolve()
                if not p.is_relative_to(native.resolve()):raise ValueError('native ref escape')
                return p.read_text()
            items.append({'locator':rp.relative_to(work).as_posix(),'request':bound(r.get('request')),
                          'delivered':r.get('audit'),'response':bound(r.get('response')),'score':r.get('score'),'status':r.get('status')})
    if result['study']=='observation-contract-study' and result['operation']=='run':
        native=result['result']['result']
        if 'trace' in native:items.append({'kind':'finite-observation-trace','trace':native['trace'],'word':native['word'],'cost':native['cost'],'bounds':native['bounds'],'status':native['status']})
        elif 'pairs' in native:items.extend({'kind':'finite-pair-search','states':p['states'],'search':p['unbounded']} for p in native['pairs'])
    if result['study']=='revision-propagation-study':
        for ep in sorted((work/'native'/'episodes').glob('*/episode.json')):
            items.append({'locator':ep.relative_to(work).as_posix(),'native_episode':read(ep),'request':'not-recorded-as-provider-request','response':'native-episode','score':'native-episode'})
    return {'run':result['run'],'analysis':result['analysis'],'interpretation':result['interpretation'],
            'stages':items,'missing_raw':not bool(items),'used':'unknown','native_result':result['result']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--source',type=Path)
    a=p.parse_args()
    a.work.mkdir(parents=True,exist_ok=True)
    birth=subprocess.check_output(['ps','-p',str(os.getpid()),'-o','lstart='],text=True).strip()
    (a.work/'process.json').write_text(encoded({'pid':os.getpid(),'birth':birth}))
    deadline=time.monotonic()+5
    while not (a.work/'launch.json').exists():
        if time.monotonic()>deadline:raise SystemExit('owner launch acknowledgment missing')
        time.sleep(.01)
    try:result=execute(a.project,read(a.plan),a.work,a.source)
    except Exception as exc:
        dependency=isinstance(exc,(ImportError,FileNotFoundError))
        (a.work/'failure.json').write_text(encoded({'state':'blocked' if dependency else 'failed','error_type':type(exc).__name__,'code':'native-dependency-unavailable' if dependency else 'native-execution-or-validation-failed'}))
        raise
    with (a.work/'result.json').open('x') as f:f.write(encoded(result))

if __name__=='__main__':main()
