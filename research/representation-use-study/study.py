#!/usr/bin/env python3
"""Offline scripted/oracle controls; no provider, network, or model inference."""
import argparse
import hashlib
import json
import os
import platform
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from corpus import canonical, corpus, digest, evidence, truth, writer

ROOT=Path(__file__).resolve().parent
SCORER='ams-exact-set-scorer/2'
PARSER='ams-structured-response/1'
TOKENIZER={'identity':'utf8-exact-diagnostic/1','unit':'UTF-8 bytes','provider_budget_verified':False}
BACKENDS=('scripted','latest','abstain','oracle')
ARMS=('raw','summary','coexistence')
ORDERS=('forward','reverse','rotate')
STATUSES=('successful','failed','timeout','refusal','parse_failure','interrupted')


def byte_count(s): return len(s.encode('utf-8'))


def freeze(path, value, raw=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Same-directory staging + hard link publishes complete bytes without replacing a target.
    # Keep staging on interruption, including the narrow post-link/pre-unlink window.
    staged=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.pending')
    payload=(value if raw else canonical(value)+'\n').encode('utf-8')
    with staged.open('xb') as f:
        f.write(payload)
        f.flush(); os.fsync(f.fileno())
    os.link(staged,path)
    staged.unlink()


def load(path): return json.loads(path.read_text(encoding='utf-8'))


def source_identity():
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ('corpus.py','study.py','protocol.md')}


def settings(modes=('full','equal'), orders=('forward','reverse','rotate'), backends=BACKENDS, budget=900):
    if budget<0: raise ValueError('budget must be nonnegative')
    for values,allowed in ((modes,('full','equal')),(orders,ORDERS),(backends,BACKENDS)):
        if not values or len(values)!=len(set(values)) or not set(values)<=set(allowed):
            raise ValueError('settings need distinct supported modes/orders/backends')
    return dict(modes=list(modes),orders=list(orders),backends=list(backends),memory_budget=budget,
                selector='all-candidates-stable-prefix/1',fail_once=False)


def plan(config):
    jobs=[]
    for case in corpus()['cases']:
        for q in case['questions']:
            for mode in config['modes']:
                for order in config['orders']:
                    for arm in ARMS:
                        for backend in config['backends']:
                            key=[case['id'],q['id'],mode,order,arm,backend]
                            jobs.append(dict(id=digest(key)[:24],case=case['id'],question=q['id'],
                                             mode=mode,order=order,arm=arm,backend=backend))
    return jobs


def prepare(case,q,job,config):
    materials=writer(case['events'],job['arm']); candidates=[m['id'] for m in materials]
    if job['order']=='reverse': materials=list(reversed(materials))
    elif job['order']=='rotate': materials=materials[1:]+materials[:1]
    selected=[m['id'] for m in materials]
    budget=None if job['mode']=='full' else config['memory_budget']
    chunks=[]; delivered=[]; remaining=budget
    for m in materials:
        full=canonical(m['record'])+'\n'
        fragment=full if remaining is None else full.encode()[:remaining].decode('utf-8',errors='ignore')
        if fragment:
            chunks.append(dict(id=m['id'],text=fragment,full_bytes=byte_count(full),
                               delivered_bytes=byte_count(fragment),complete=fragment==full))
            if fragment==full: delivered.append(m)
        if remaining is not None:
            remaining-=byte_count(fragment)
            if fragment!=full: break
    memory=''.join(c['text'] for c in chunks)
    request={'schema':'ams-offline-request/1','backend':job['backend'],
        'system':'Read only delivered JSONL memory. Return {action: answer|clarify|abstain, value: string, citations: [record id]}. Missing evidence permits abstain:insufficient. No external knowledge.',
        'question':q,'memory':memory,'generation':{'deterministic':True,'network':False}}
    if job['backend']=='oracle': request['oracle_extra_information']=truth(case['events'],q)
    audit=dict(candidate_ids=candidates,selected_ids=selected,delivered=chunks,order=job['order'],
               memory_bytes=byte_count(memory),memory_budget=budget,request_bytes=byte_count(canonical(request)),
               tokenizer=TOKENIZER,availability=evidence(case,q,delivered),used='unknown')
    return request,audit


def parse(raw):
    r=json.loads(raw)
    if not isinstance(r,dict) or set(r)!={'action','value','citations'}: raise ValueError('response schema')
    if r['action'] not in ('answer','clarify','abstain') or not isinstance(r['value'],str): raise ValueError('response action/value')
    if not isinstance(r['citations'],list) or not all(isinstance(x,str) for x in r['citations']): raise ValueError('citations')
    return r


def response(label,citations=()):
    action,value=label.split(':',1)
    return canonical(dict(action=action,value=value,citations=list(citations)))


def scripted(request, naive=False):
    """Independent consumer of visible records; deliberately no latent/gold parameter."""
    records=[]
    for line in request['memory'].splitlines():
        try:
            r=json.loads(line)
            if isinstance(r,dict) and 'id' in r: records.append(r)
        except ValueError: pass
    # Coexistence has duplicate logical events. Raw detail takes precedence.
    by_id={}
    for r in records:
        if r['id'] not in by_id or r['representation']=='raw': by_id[r['id']]=r
    records=list(by_id.values()); q=request['question']; kind=q['kind']
    if not records: return response('abstain:insufficient')
    if kind=='decision':
        pool=[r for r in records if r['kind']=='decision' and (naive or
              (r['authority'] and r['accepted'] and r['scope']==q['scope'] and r['time']<=q['at']))]
        if not pool: return response('abstain:unknown')
        t=max(r['time'] for r in pool); latest=[r for r in pool if r['time']==t]
        values={r['value'] for r in latest}
        if len(values)>1 and not naive: return response('clarify:conflict',[r['id'] for r in latest])
        return response('answer:'+latest[-1]['value'],[latest[-1]['id']])
    if kind=='agreement':
        value='yes' if any(r['kind']=='decision' and r['value']=='red' and r['authority']
                          and r['accepted'] and r['time']<=5 for r in records) else 'no'
    elif kind in ('wording','provenance'):
        # First original event ID uses e1, not current position.
        r=next((r for r in records if r['id'].endswith(':e1')),None)
        if not r or 'actor' not in r: return response('abstain:insufficient')
        value=r['wording'] if kind=='wording' else f"{r['actor']}@{r['time']}"
    else:
        pairs={tuple(sorted(r['pair'])) for r in records if r['kind']=='relation'}
        yes=('A','C') in pairs if kind=='direct' else {('A','B'),('B','C')} <= pairs
        value='yes' if yes else 'no'
    return response('answer:'+value,[r['id'] for r in records])


def backend(request):
    name=request['backend']
    if name=='oracle': return response(request['oracle_extra_information']['accepted'][0])
    if name=='abstain': return response('abstain:insufficient')
    return scripted(request,naive=name=='latest')


def score(case,q,audit,raw):
    r=parse(raw); label=r['action']+':'+r['value']; gold=truth(case['events'],q)
    task_correct=label in gold['accepted']
    insufficient=audit['availability']=='insufficient'
    calibrated=(label in ('abstain:insufficient','clarify:missing-evidence','abstain:unknown','clarify:scope') and insufficient)
    known_ids=set()
    for chunk in audit['delivered']:
        if chunk['complete']: known_ids.add(json.loads(chunk['text'])['id'])
    return dict(task_correct=task_correct,acceptable=task_correct or calibrated,
        unsupported_answer=r['action']=='answer' and (insufficient or not task_correct),
        over_abstain=(r['action'] in ('abstain','clarify') and audit['availability']=='sufficient'
                      and any(label.startswith('answer:') for label in gold['accepted'])),
        appropriate_defer=calibrated or (task_correct and r['action']!='answer'),
        citations_valid=all(x in known_ids for x in r['citations']),used='unknown')


def manifest(config):
    data=corpus(); jobs=plan(config)
    return dict(schema='ams-offline-run/1',evidence_kind='scripted-oracle-controls-only',settings=config,
        dataset_digest=digest(data),source=source_identity(),scorer=SCORER,parser=PARSER,tokenizer=TOKENIZER,
        backend_version='stdlib-controls/1',python=platform.python_version(),jobs_digest=digest(jobs),
        planned_requests=len(jobs),family_count=len(data['families']))


def index():
    return {c['id']:c for c in corpus()['cases']}


def safe_ref(root,ref):
    p=Path(ref)
    if p.is_absolute() or '..' in p.parts or not p.parts: raise ValueError('unsafe artifact reference')
    result=root/p
    if result.resolve().is_relative_to(root.resolve()) is False: raise ValueError('artifact escapes root')
    return result


def binding(root,path):
    return dict(path=path.relative_to(root).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def read_bound(root,ref,raw=False):
    path=safe_ref(root,ref['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']: raise ValueError('corrupt artifact: '+ref['path'])
    return path.read_bytes() if raw else path.read_text(encoding='utf-8')


def check_run(root,expected=None):
    m=load(root/'manifest.json')
    if expected is None:
        expected=manifest(m['settings'])
        expected['python']=m['python']  # Replay validates source, not the current interpreter patch.
    if {k:v for k,v in m.items() if k!='run_id'}!=expected: raise ValueError('foreign/stale manifest: source, dataset, settings or scorer changed')
    jobs=plan(m['settings']); mapping={j['id']:j for j in jobs}; cases=index(); receipts=[]; pending=[]
    attempt_root=root/'attempts'
    if attempt_root.exists():
        for job_dir in sorted(attempt_root.iterdir()):
            if job_dir.name not in mapping or not job_dir.is_dir(): raise ValueError('foreign job directory')
            job=mapping[job_dir.name]; case=cases[job['case']]; q=next(q for q in case['questions'] if q['id']==job['question'])
            request,audit=prepare(case,q,job,m['settings'])
            previous=None; successful=False
            for number,ad in enumerate(sorted(job_dir.iterdir()),1):
                if ad.name!=f'{number:04d}' or successful: raise ValueError('invalid attempt sequence')
                expected_start={'job':job,'attempt':number,'retry_of':previous,'request_digest':digest(request),'audit':audit,'run_id':m['run_id']}
                started=load(ad/'started.json') if (ad/'started.json').exists() else expected_start
                if started!=expected_start:
                    raise ValueError('foreign/stale attempt')
                request_exists=(ad/'request.json').exists()
                started_exists=(ad/'started.json').exists()
                if (ad/'response.txt').exists() and not started_exists:
                    raise ValueError('missing published started before response')
                if request_exists:
                    if load(ad/'request.json')!=request: raise ValueError('request drift')
                elif started_exists or (ad/'response.txt').exists():
                    raise ValueError('missing published request before started/response')
                rp=ad/'receipt.json'
                if not rp.exists():
                    pending.append((job,ad,started)); previous=f'{job_dir.name}/{ad.name}'; continue
                r=load(rp)
                if r['run_id']!=m['run_id'] or r['job']!=job or r['attempt']!=number or r['retry_of']!=previous or r['audit']!=audit:
                    raise ValueError('receipt binding mismatch')
                if request_exists:
                    if r['request'] is None or json.loads(read_bound(root,r['request']))!=request:
                        raise ValueError('receipt request mismatch')
                elif r['status']!='interrupted' or r['request'] is not None:
                    raise ValueError('missing request allowed only for interrupted pre-publication attempt')
                if r['status']=='successful' and not started_exists: raise ValueError('missing published started artifact')
                for artifact in r['incomplete_artifacts']: read_bound(root,artifact,raw=True)
                raw=read_bound(root,r['response']) if r['response'] else None
                if r['status'] not in STATUSES: raise ValueError('unknown attempt status')
                if r['status']=='successful':
                    if r['score']!=score(case,q,audit,raw): raise ValueError('score drift')
                    successful=True
                elif r['score'] is not None: raise ValueError('failed attempt scored')
                if r['status']=='parse_failure':
                    try: parse(raw)
                    except (ValueError,TypeError): pass
                    else: raise ValueError('parse failure receipt contains a valid response')
                if r['status']=='refusal' and (raw is None or json.loads(raw).get('action')!='refusal'):
                    raise ValueError('refusal receipt mismatch')
                if r['parser']!=PARSER or r['scorer']!=SCORER: raise ValueError('version drift')
                receipts.append(r); previous=f'{job_dir.name}/{ad.name}'
    return m,receipts,pending


def make_receipt(root,ad,started,status,raw=None,error=None):
    response_path=ad/'response.txt'
    if raw is not None: freeze(response_path,raw,raw=True)
    case=index()[started['job']['case']]; q=next(q for q in case['questions'] if q['id']==started['job']['question'])
    result=dict(run_id=started['run_id'],job=started['job'],attempt=started['attempt'],retry_of=started['retry_of'],
        status=status,audit=started['audit'],request=binding(root,ad/'request.json') if (ad/'request.json').exists() else None,
        incomplete_artifacts=[binding(root,p) for p in sorted(ad.glob('.*.pending'))],
        response=binding(root,response_path) if response_path.exists() else None,error=error,
        parser=PARSER,scorer=SCORER,score=score(case,q,started['audit'],raw) if status=='successful' else None)
    freeze(ad/'receipt.json',result)
    return result


def run(root,config,resume=False,limit=None):
    if limit is not None and limit<0: raise ValueError('limit must be nonnegative')
    root=Path(root); wanted=manifest(config)
    if root.exists() and (root/'manifest.json').exists():
        if not resume: raise ValueError('run exists; use --resume')
        _,receipts,pending=check_run(root,wanted)
        for job,ad,start in pending:
            receipts.append(make_receipt(root,ad,start,'interrupted',error='Outcome unknown after interruption; may have executed.'))
    else:
        if root.exists() and any(root.iterdir()):
            raise ValueError('nonempty output without complete published manifest; preserve staging and use a new output')
        freeze(root/'manifest.json',dict(wanted,run_id=str(uuid.uuid4()))); receipts=[]
    completed={r['job']['id'] for r in receipts if r['status']=='successful'}
    counts=Counter(r['job']['id'] for r in receipts); cases=index(); executed=0
    for job in plan(config):
        if job['id'] in completed: continue
        if limit is not None and executed>=limit: break
        case=cases[job['case']]; q=next(q for q in case['questions'] if q['id']==job['question'])
        request,audit=prepare(case,q,job,config); n=counts[job['id']]+1
        ad=root/'attempts'/job['id']/f'{n:04d}'
        start=dict(run_id=load(root/'manifest.json')['run_id'],job=job,attempt=n,retry_of=f"{job['id']}/{n-1:04d}" if n>1 else None,
                   request_digest=digest(request),audit=audit)
        freeze(ad/'request.json',request); freeze(ad/'started.json',start)
        try:
            if config['fail_once'] and not receipts and executed==0 and n==1: raise RuntimeError('intentional first-attempt failure')
            raw=backend(request)
            try:
                if json.loads(raw).get('action')=='refusal': status='refusal'
                else: parse(raw); status='successful'
            except (ValueError,TypeError,AttributeError): status='parse_failure'
            receipts.append(make_receipt(root,ad,start,status,raw))
        except TimeoutError as exc:
            receipts.append(make_receipt(root,ad,start,'timeout',error=str(exc)))
        except Exception as exc:
            receipts.append(make_receipt(root,ad,start,'failed',error=str(exc)))
        executed+=1
    return report(root)


def portable_identity(m):
    return digest({k:v for k,v in m.items() if k not in ('run_id','python')})


def report(root):
    m,receipts,pending=check_run(Path(root)); latest={}
    for r in receipts: latest[r['job']['id']]=r
    pending_ids={j['id'] for j,_,_ in pending}
    attempted=set(latest)|pending_ids
    jobs=plan(m['settings']); cases=index()
    def cell(j): return tuple(j[k] for k in ('case','question','mode','order','backend'))
    def question(j): return next(q for q in cases[j['case']]['questions'] if q['id']==j['question'])
    # Evidence subset is fixed from all planned contexts, never conditioned on successful responses.
    certificates={}
    sufficient_arms=defaultdict(set)
    for j in jobs:
        key=tuple(j[k] for k in ('case','question','mode','order','arm'))
        if key not in certificates:
            certificates[key]=prepare(cases[j['case']],question(j),j,m['settings'])[1]['availability']
        if certificates[key]=='sufficient': sufficient_arms[cell(j)].add(j['arm'])
    eligible={k for k,v in sufficient_arms.items() if v==set(ARMS)}
    def status(j):
        if j['id'] in pending_ids: return 'pending_interrupted'
        return latest[j['id']]['status'] if j['id'] in latest else 'unexecuted'
    def scored(js):
        return [latest[j['id']] for j in js if status(j)=='successful']
    def counts(js):
        rs=scored(js)
        return dict(planned_jobs=len(js),executed_jobs=sum(j['id'] in attempted for j in js),
                    scored_responses=len(rs),task_correct=sum(r['score']['task_correct'] for r in rs))
    result={}
    for subset in ('full_task_set','all_arms_sufficient'):
        buckets=defaultdict(list)
        for j in jobs:
            if subset=='all_arms_sufficient' and cell(j) not in eligible: continue
            buckets['/'.join(j[k] for k in ('mode','order','arm','backend'))].append(j)
        result[subset]={}
        for key,js in sorted(buckets.items()):
            rs=scored(js)
            family_groups=sorted({cases[j['case']]['group'] for j in js})
            metrics={field:sum(r['score'][field] for r in rs) for field in
                     ('task_correct','acceptable','unsupported_answer','over_abstain','appropriate_defer')}
            result[subset][key]=dict(**counts(js),families=len(family_groups),metrics=metrics,
                outcome_statuses=dict(Counter(status(j) for j in js)),
                planned_availability=dict(Counter(certificates[tuple(j[k] for k in ('case','question','mode','order','arm'))] for j in js)),
                by_family={f:counts([j for j in js if cases[j['case']]['group']==f]) for f in family_groups},
                by_question={qid:dict(**counts([j for j in js if j['question']==qid]),
                    task_role='common' if qid in ('current','boundary') else 'added')
                    for qid in sorted({j['question'] for j in js})},
                by_task_set={task:counts([j for j in js if cases[j['case']]['task']==task])
                             for task in ('current','expanded')})
    pairs=defaultdict(dict)
    for r in latest.values():
        j=r['job']; c=cases[j['case']]
        key=(c['group'],c['task'],c['variant'],j['question'],j['mode'],j['order'],j['arm'],j['backend'])
        pairs[key][c['history']]=r
    transitions=defaultdict(Counter)
    for key,pair in pairs.items():
        if set(pair)!={'fixed','updated'}: continue
        old,new=pair['fixed'],pair['updated']; c0=cases[old['job']['case']]; c1=cases[new['job']['case']]
        q=question(old['job']); changed=truth(c0['events'],q)!=truth(c1['events'],q)
        scopes=['changed' if changed else 'preserved']
        if not changed and q['id']=='boundary': scopes.append('boundary')
        bucket='/'.join(key[-4:])
        for scope in scopes:
            transitions[bucket][scope+':attempted_pairs']+=1
            if status(old['job'])=='successful' and status(new['job'])=='successful':
                transitions[bucket][scope+':scored_pairs']+=1
                transitions[bucket][scope+':'+str(int(old['score']['task_correct']))+'->'+str(int(new['score']['task_correct']))]+=1
    return dict(schema='ams-offline-report/1',evidence_kind=m['evidence_kind'],portable_experiment_digest=portable_identity(m),
        planned_requests=m['planned_requests'],attempts=len(receipts),pending_interrupted=len(pending),
        states=dict(Counter(r['status'] for r in receipts)),successful_jobs=sum(status(j)=='successful' for j in jobs),
        unexecuted=m['planned_requests']-len(attempted),results=result,
        history_transitions={k:dict(v) for k,v in sorted(transitions.items())},
        corpus=dict(cases=len(corpus()['cases']),questions_per_case={'current':2,'expanded':8},
                    question_rows=sum(len(c['questions']) for c in corpus()['cases']),families=8,independent_unit='event family',
                    design='fixed/updated history x current/expanded task sets; two wording variants; common questions paired, added uses separate',blinded=False),
        limits=['Development/diagnostic fixture; no blinded confirmation.','Oracle sees extra information; not a fair winner.',
                'UTF-8 bytes are not model tokens.','Citation does not prove causal use; used remains unknown.',
                'Added task questions change task distribution; compare overlapping common questions separately.'])


def check_saved_sample(path=ROOT/'sample-results.json'):
    """Bounded no-backend check for reader integration; full replay needs external raw run."""
    r=load(path); config=settings(orders=('forward',))
    if r['portable_experiment_digest']!=portable_identity(manifest(config)):
        raise ValueError('saved control sample identity drift')
    if r['planned_requests']!=len(plan(config)) or r['successful_jobs']!=r['planned_requests'] or r['unexecuted']:
        raise ValueError('saved sample incomplete')
    for subset,buckets in r['results'].items():
        for key,b in buckets.items():
            if b['executed_jobs']!=b['planned_jobs'] or b['scored_responses']!=b['planned_jobs']:
                raise ValueError('sample denominators differ')
            for field in ('planned_jobs','executed_jobs','scored_responses','task_correct'):
                if sum(f[field] for f in b['by_family'].values())!=b[field]: raise ValueError('family accounting')
                if sum(f[field] for f in b['by_question'].values())!=b[field]: raise ValueError('question accounting')
                if sum(f[field] for f in b['by_task_set'].values())!=b[field]: raise ValueError('task-set accounting')
    full=r['results']['full_task_set']
    n=sum(len(c['questions']) for c in corpus()['cases'])
    for arm in ARMS:
        if full[f'full/forward/{arm}/oracle']['task_correct']!=n: raise ValueError('oracle control')
    if full['full/forward/raw/scripted']['task_correct']!=n: raise ValueError('positive reader control')
    if full['full/forward/raw/latest']['task_correct']>=n: raise ValueError('latest counterexample lost')
    answerable=sum(any(label.startswith('answer:') for label in truth(c['events'],q)['accepted'])
                   for c in corpus()['cases'] for q in c['questions'])
    if full['full/forward/raw/abstain']['metrics']['over_abstain']!=answerable:
        raise ValueError('answerable-only abstain counterexample count drift')
    if full['full/forward/summary/scripted']['task_correct']>=n: raise ValueError('summary loss control')
    return dict(status='checked-saved-control-summary-not-raw-replay',families=8,planned_requests=r['planned_requests'])


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('command',choices=('dry-run','run','verify','replay','check-sample'))
    p.add_argument('--out',type=Path); p.add_argument('--resume',action='store_true'); p.add_argument('--budget',type=int,default=900)
    p.add_argument('--modes',nargs='+',choices=('full','equal'),default=['full','equal'])
    p.add_argument('--orders',nargs='+',choices=ORDERS,default=list(ORDERS)); p.add_argument('--backends',nargs='+',choices=BACKENDS,default=list(BACKENDS))
    p.add_argument('--check-report',type=Path); p.add_argument('--limit',type=int); p.add_argument('--fail-once',action='store_true'); p.add_argument('--report',type=Path)
    args=p.parse_args(); config=settings(args.modes,args.orders,args.backends,args.budget); config['fail_once']=args.fail_once
    try:
        if args.command=='check-sample': result=check_saved_sample()
        elif args.command=='dry-run': result=dict(manifest=manifest(config),jobs=plan(config),model_requests=0)
        else:
            if not args.out: p.error('--out required')
            result=run(args.out,config,args.resume,args.limit) if args.command=='run' else report(args.out)
        if args.check_report:
            if result!=load(args.check_report): raise ValueError('sample report differs')
            print('Frozen report matches recomputed receipts.')
        elif args.report: freeze(args.report,result)
        else: print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        p.exit(1,f'{type(exc).__name__}: {exc}\n')


if __name__=='__main__': main()
