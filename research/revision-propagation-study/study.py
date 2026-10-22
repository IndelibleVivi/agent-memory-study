#!/usr/bin/env python3
"""WP4/E2 offline longitudinal revision controls; stdlib, no models/providers."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from collections import Counter,defaultdict
from fixtures import canonical,identity,fixtures,query,probes,gold

ROOT=Path(__file__).resolve().parent
POLICIES=('append-latest','versions','dependencies','source-reread')
LAYERS=('store','index','summary','delivered')
BRANCHES=('natural',)+tuple('stale-'+l for l in LAYERS)+tuple('repair-'+l for l in LAYERS)+('oracle-extraction','oracle-retrieval','oracle-context')
SCORER='ams-revision-scorer/1'


def extract(events,q,policy):
    """Domain implementation, independent of gold. Returns recommendation and source IDs."""
    if policy=='append-latest':
        candidates=[e for e in events if e['key']==q['key'] and e['kind'] in ('assert','rule','revoke','commitment','scope-update')]
        if not candidates: return dict(label='abstain:unknown',support=[])
        e=max(enumerate(candidates),key=lambda p:(p[1]['observed_time'],p[0]))[1]
        return dict(label='abstain:unknown' if e['kind']=='revoke' else 'answer:'+e['value'],support=[e['id']])
    candidates=[]
    for e in events:
        if e['authority']!='owner' or e['kind']=='notice': continue
        if (e['key'],e['project'])!=(q['key'],q['project']) or q['scope'] not in e['scopes']: continue
        if e['observed_time']>q['observed_time'] or e['valid_from']>q['valid_time']: continue
        if e['valid_to'] is not None and e['valid_to']<=q['valid_time']: continue
        candidates.append(e)
    killed=set()
    for e in candidates: killed.update(e['supersedes'])
    live=[e for e in candidates if e['id'] not in killed and e['kind']!='revoke'
          and (e['kind']!='scope-update' or q['scope'] in e['allowed_scopes'])]
    labels=set(); support=[]
    for e in live:
        value=e['value']; support.append(e['id'])
        if e['kind']=='rule' and policy in ('dependencies','source-reread'):
            dep=extract(events,dict(q,key=e['dependency']),policy)
            support.extend(dep['support'])
            if not dep['label'].startswith('answer:'): return dict(label='clarify:conflict',support=sorted(set(support)))
            value=e['mapping'][dep['label'].split(':',1)[1]]
        labels.add('answer:'+value)
    label='abstain:unknown' if not labels else ('clarify:conflict' if len(labels)>1 else labels.pop())
    return dict(label=label,support=sorted(set(support)))


def make_store(family,retention,updated=True):
    events=copy.deepcopy(family['initial']+(family['revision'] if updated else [])); source_identity=identity(events); tombstones=[]
    if updated:
        for rev in family['revision']:
            if rev['authority']=='owner': tombstones.extend(dict(target=x,revision=rev['id'],scopes=rev['scopes'],valid_from=rev['valid_from']) for x in rev['supersedes'])
        if retention=='delete': events=[e for e in events if e['id'] not in {x['target'] for x in tombstones}]
    return dict(events=events,tombstones=tombstones,retention=retention,identity=source_identity,content_identity=identity(events))


def materialize(store,qs,policy,step,oracle=None):
    rows={}
    for name,q in qs.items():
        if oracle is None: result=extract(store['events'],q,policy)
        else:
            g=gold(oracle,q); result=dict(label=g['accepted'][0],support=g['support'])
        # Expiry metadata is operational evidence, not a model-token/latency claim.
        activations=[e['valid_from'] for e in store['events'] if e['key']==q['key'] and e['project']==q['project']
                     and q['scope'] in e['scopes'] and e['authority']=='owner'
                     and e['observed_time']<=q['observed_time'] and e['valid_from']>q['valid_time']]
        expiries=activations+[e['valid_to'] for e in store['events'] if e['id'] in result['support'] and e['valid_to'] is not None]
        rows[name]=dict(**result,source_identity=store['identity'],evaluated_query=q,
                        expires=min(expiries) if expiries else None,origin='oracle-extra-information' if oracle else 'scripted-extraction')
    return dict(version=step,source_identity=store['identity'],rows=rows)


def answerer(delivery):
    """Only sees actual delivered recommendation; cannot access fixture/gold/store."""
    if delivery.get('oracle_extra_information'):
        row=delivery['oracle_extra_information']
    else: row=delivery['records'][-1] if delivery['records'] else dict(label='abstain:missing',support=[])
    return dict(label=row['label'],citations=list(row['support']),used='unknown')


def score(events,q,delivery,action):
    g=gold(events,q); row=(delivery.get('oracle_extra_information') or delivery['records'][-1])
    # Version-stale is an observable provenance mismatch/expiry; it is separate from wrong action.
    stale=row['source_identity']!=identity(events) or (row['expires'] is not None and row['expires']<=q['valid_time'])
    return dict(correct=action['label'] in g['accepted'],version_stale_delivered=stale,
                error_given_stale=stale and action['label'] not in g['accepted'],used='unknown')


def checkpoint(family,policy,retention):
    store=make_store(family,retention,False)
    qs=probes(1)
    # Shared state is materialized at valid_time=1, before observation of revision at 2.
    qs={k:dict(q,valid_time=1,observed_time=1) if k in ('main','preserved','boundary') else q for k,q in qs.items()}
    index=materialize(store,qs,'dependencies',0)
    return dict(store=store,index=index,summary=copy.deepcopy(index),writes=[],delivered=None)


def jobs(settings=None):
    settings=settings or dict(delays=[0,1,3],retentions=['tombstone','delete'],policies=list(POLICIES),branches=list(BRANCHES))
    supported=dict(delays=(0,1,3),retentions=('tombstone','delete'),policies=POLICIES,branches=BRANCHES)
    if set(settings)-set(supported)-{'tasks'} or settings.get('tasks',10)!=10: raise ValueError('unsupported task/configuration')
    for key,allowed in supported.items():
        values=settings[key]
        if not values or len(values)!=len(set(values)) or not set(values)<=set(allowed): raise ValueError('unsupported/duplicate '+key)
    return [dict(id=identity([f['id'],p,d,r,b])[:24],family=f['id'],policy=p,delay=d,retention=r,branch=b)
            for f in fixtures()['families'] for p in settings['policies'] for d in settings['delays']
            for r in settings['retentions'] for b in settings['branches']]


def episode(family,job,disable_writes=False):
    policy=job['policy']; official=family['initial']+family['revision']
    pre=checkpoint(family,policy,job['retention']); state=copy.deepcopy(pre)
    state['store']=make_store(family,job['retention']); snapshots=[]; recomputations=0; diagnostic_recomputations=0
    branch=job['branch']; fault=branch.split('-',1)[1] if branch.startswith(('stale-','repair-')) else ('summary' if branch.startswith('oracle-') else None)
    pinned_delivery=False; last_index_version=state['summary']['version']; synced_at=None
    for step in range(1,11):
        qs=probes(step); before=copy.deepcopy(state); updates=[]; intervention=None; fault_injection=None
        if step==1 and fault=='store':
            direct_before=copy.deepcopy(state); state['store']=copy.deepcopy(pre['store'])
            fault_injection=dict(layer='store',before=direct_before,after=copy.deepcopy(state)); updates.append('inject:store')
        due=step==job['delay']+1
        dependency_dirty=policy=='dependencies' and (state['index']['source_identity']!=state['store']['identity'] or
            any(row['expires'] is not None and row['expires']<=qs[k]['valid_time'] for k,row in state['index']['rows'].items() if k in ('main','boundary','preserved')))
        if due or dependency_dirty:
            extra=official if branch=='oracle-extraction' else None
            state['index']=materialize(state['store'],qs,policy,step,extra)
            recomputations+=1; updates.append('extract')
            if synced_at is None: synced_at=step
        if step==1 and fault=='index':
            direct_before=copy.deepcopy(state)
            state['index']=copy.deepcopy(pre['index']); state['index']['version']=step
            fault_injection=dict(layer='index',before=direct_before,after=copy.deepcopy(state)); updates.append('inject:index')
        if state['index']['version']!=last_index_version:
            state['summary']=copy.deepcopy(state['index']); last_index_version=state['index']['version']; updates.append('summarize')
        if step==1 and fault=='summary':
            direct_before=copy.deepcopy(state)
            state['summary']=copy.deepcopy(pre['summary']); state['summary']['version']=state['index']['version']
            fault_injection=dict(layer='summary',before=direct_before,after=copy.deepcopy(state)); updates.append('inject:summary')
        if step==1 and fault=='delivered': pinned_delivery=True
        if step==2 and branch.startswith('repair-'):
            # Exactly one layer is replaced. Descendants and earlier output/write remain branch-specific.
            direct_before=copy.deepcopy(state)
            if fault=='store': state['store']=make_store(family,job['retention'])
            elif fault in ('index','summary'):
                state[fault]=materialize(make_store(family,job['retention']),qs,policy,100+step)
            if fault!='delivered':
                intervention=dict(layer=fault,before=direct_before,after=copy.deepcopy(state))
            updates.append('repair:'+fault)
        diagnostics={}
        for name,q in qs.items():
            row=copy.deepcopy(state['summary']['rows'][name]); retrieval='summary'
            if policy=='source-reread':
                row=materialize(state['store'],{name:q},policy,step)['rows'][name]; retrieval='source-reread'
                if name=='main': recomputations+=1
                else: diagnostic_recomputations+=1
            if name=='main' and step in (5,8) and state['writes'] and policy!='source-reread':
                echo=state['writes'][0]['memory']
                valid_echo=echo['source_identity']==state['store']['identity'] and (echo['expires'] is None or echo['expires']>q['valid_time'])
                if policy!='dependencies' or valid_echo:
                    row=copy.deepcopy(echo); retrieval='lagged-first-output-write'
            if branch=='oracle-retrieval':
                row=materialize(make_store(family,'tombstone'),{name:q},policy,step,official)['rows'][name]; retrieval='oracle-retrieval'
            before_pin=dict(query=q,records=[copy.deepcopy(row)],retrieval=retrieval,used='unknown')
            if pinned_delivery:
                row=copy.deepcopy(pre['summary']['rows'][name]); retrieval='pinned-stale-delivery'
            delivery_before_repair=None
            if step==2 and branch=='repair-delivered':
                delivery_before_repair=dict(query=q,records=[copy.deepcopy(row)],retrieval=retrieval,used='unknown')
                row=materialize(make_store(family,job['retention']),{name:q},policy,step)['rows'][name]; retrieval='single-layer-repair'
            delivery=dict(query=q,records=[row],retrieval=retrieval,used='unknown')
            if branch=='oracle-context':
                delivery['oracle_extra_information']=materialize(make_store(family,'tombstone'),{name:q},policy,step,official)['rows'][name]
            if name=='main' and step==1 and fault=='delivered':
                direct_before=copy.deepcopy(state); direct_before['delivered']=before_pin
                direct_after=copy.deepcopy(direct_before); direct_after['delivered']=copy.deepcopy(delivery)
                fault_injection=dict(layer='delivered',before=direct_before,after=direct_after)
            if name=='main' and delivery_before_repair is not None:
                direct_before=copy.deepcopy(state); direct_before['delivered']=delivery_before_repair
                direct_after=copy.deepcopy(direct_before); direct_after['delivered']=copy.deepcopy(delivery)
                intervention=dict(layer='delivered',before=direct_before,after=direct_after)
            action=answerer(delivery); scored=score(official,q,delivery,action)
            old=gold(family['initial'],q if name.startswith('historical') else dict(q,valid_time=1,observed_time=1))
            new=gold(official,q)
            group='changed' if old['accepted']!=new['accepted'] else 'preserved'
            diagnostics[name]=dict(delivery=delivery,action=action,score=scored,scope=group,
                boundary=name=='boundary' and group=='preserved',historical=name.startswith('historical'))
        if step==2 and branch=='repair-delivered': pinned_delivery=False
        main=diagnostics['main']; state['delivered']=copy.deepcopy(main['delivery'])
        write=None
        if not disable_writes:
            source_row=main['delivery'].get('oracle_extra_information') or main['delivery']['records'][-1]
            write=dict(id=f'write:{step}',producer='main-action-only',action_identity=identity(main['action']),
                memory=dict(label=main['action']['label'],support=main['action']['citations'],
                            source_identity=source_row['source_identity'],evaluated_query=qs['main'],
                            expires=source_row['expires'],origin='own-output-write'))
            state['writes'].append(write)
        snapshots.append(dict(step=step,before=before,updates=updates,after=copy.deepcopy(state),
            probes=diagnostics,write=write,intervention=intervention,fault_injection=fault_injection,recomputations_so_far=recomputations))
    return dict(schema='ams-revision-episode/1',job=job,checkpoint=pre,checkpoint_identity=identity(pre),
                snapshots=snapshots,recomputations=recomputations,diagnostic_recomputations=diagnostic_recomputations,scheduled_delay_tasks=job['delay'],
                first_refresh_task=synced_at,output_feedback='disabled-diagnostic' if disable_writes else 'main-action-write')


def source_identity():
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('fixtures.py','study.py','protocol.md')}


def settings(): return dict(delays=[0,1,3],retentions=['tombstone','delete'],policies=list(POLICIES),branches=list(BRANCHES),tasks=10)


def manifest(config):
    return dict(schema='ams-revision-run/1',evidence_kind='scripted-oracle-controls-only',settings=config,
                fixture_identity=identity(fixtures()),source=source_identity(),scorer=SCORER,jobs_identity=identity(jobs(config)))


def freeze(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        f.write(canonical(value)+'\n'); f.flush(); os.fsync(f.fileno())


def load(path): return json.loads(path.read_text())


def bound(root,path): return dict(path=path.relative_to(root).as_posix(),identity=hashlib.sha256(path.read_bytes()).hexdigest())


def read_bound(root,ref):
    path=root/ref['path']
    if Path(ref['path']).is_absolute() or not path.resolve().is_relative_to(root.resolve()): raise ValueError('unsafe reference')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['identity']: raise ValueError('corrupt episode')
    return load(path)


def focused_contrast():
    f=fixtures()['families'][0]
    j=dict(id='focused-writeback-contrast',family=f['id'],policy='versions',delay=1,retention='tombstone',branch='natural')
    return dict(with_writeback=episode(f,j),without_writeback=episode(f,j,True),
                interpretation='Preset synthetic revisit pressure at tasks 5/8; not a natural reappearance rate.')


def execute(root,config=None,limit=None):
    config=config or settings(); root=Path(root)
    if limit is not None and limit<0: raise ValueError('limit must be nonnegative')
    # Whole-episode atomic completion: partial dirs are preserved and rejected, never overwritten.
    if root.exists() and any(root.iterdir()): raise ValueError('output must be empty/new; partial or old run is preserved')
    freeze(root/'manifest.json',manifest(config)); families={f['id']:f for f in fixtures()['families']}
    receipts=[]
    for j in jobs(config)[:limit]:
        ep=root/'episodes'/j['id']
        freeze(ep/'started.json',dict(job=j,manifest_identity=identity(manifest(config))))
        result=episode(families[j['family']],j)
        freeze(ep/'episode.json',result)
        receipt=dict(job=j,episode=bound(root,ep/'episode.json'),scorer=SCORER,status='successful')
        freeze(ep/'receipt.json',receipt); receipts.append(receipt)
    freeze(root/'focused.json',focused_contrast())
    freeze(root/'completion.json',dict(episode_count=len(receipts),planned=len(jobs(config)),receipts=receipts,focused=bound(root,root/'focused.json')))
    return verify(root)


def validate_episode(family,ep):
    """Replay deterministic transitions, then separately recompute scores from actual receipts."""
    if ep['output_feedback'] not in ('disabled-diagnostic','main-action-write'): raise ValueError('unknown feedback mode')
    expected=episode(family,ep['job'],disable_writes=ep['output_feedback']=='disabled-diagnostic')
    if ep!=expected: raise ValueError('episode transition/action/write/score mismatch')
    for snapshot in ep['snapshots']:
        for name,probe in snapshot['probes'].items():
            if probe['score']!=score(family['initial']+family['revision'],probe['delivery']['query'],probe['delivery'],probe['action']):
                raise ValueError('score mismatch')


def verify(root):
    root=Path(root); m=load(root/'manifest.json')
    if m!=manifest(m['settings']): raise ValueError('foreign/config/source identity mismatch')
    completion=load(root/'completion.json') if (root/'completion.json').exists() else None
    if completion is None: raise ValueError('partial run; no completion receipt; use a new output')
    planned=jobs(m['settings']); expected_ids={j['id'] for j in planned}
    actual_dirs={p.name for p in (root/'episodes').iterdir()} if (root/'episodes').exists() else set()
    if actual_dirs!={r['job']['id'] for r in completion['receipts']}: raise ValueError('partial/foreign episode directories')
    if completion['episode_count']!=len(completion['receipts']) or completion['planned']!=len(planned): raise ValueError('completion accounting')
    families={f['id']:f for f in fixtures()['families']}; results=[]; seen=set()
    for receipt in completion['receipts']:
        j=receipt['job']
        if j['id'] not in expected_ids or j not in planned or j['id'] in seen: raise ValueError('foreign/duplicate job')
        seen.add(j['id']); epdir=root/'episodes'/j['id']
        if load(epdir/'started.json')!=dict(job=j,manifest_identity=identity(m)): raise ValueError('foreign started receipt')
        if load(epdir/'receipt.json')!=receipt or receipt['status']!='successful' or receipt['scorer']!=SCORER: raise ValueError('receipt mismatch')
        ep=read_bound(root,receipt['episode'])
        if ep['job']!=j: raise ValueError('episode job mismatch')
        validate_episode(families[j['family']],ep); results.append(ep)
    focused=read_bound(root,completion['focused'])
    if focused!=focused_contrast(): raise ValueError('focused contrast mismatch')
    report=summarize(m,results)
    report['feedback_contrast']={mode:dict(main_labels=[s['probes']['main']['action']['label'] for s in ep['snapshots']],
        main_correct=[s['probes']['main']['score']['correct'] for s in ep['snapshots']],
        writes=len(ep['snapshots'][-1]['after']['writes'])) for mode,ep in focused.items() if isinstance(ep,dict)}
    return report


def recurrence_metrics(ep,family):
    """Match wrong→repaired→wrong within the same expected-answer phase and query identity.

    Old influence additionally requires the prerevision recommendation and support/version;
    arbitrary later errors and legitimate valid-time phase transitions do not qualify.
    """
    official=family['initial']+family['revision']; phases={}; old_recur=False; any_recur=False; events=[]
    old_gold=gold(family['initial'],query(valid_time=1,observed_time=1))
    old_support=set(old_gold['support']); old_source=ep['checkpoint']['store']['identity']
    for s in ep['snapshots']:
        p=s['probes']['main']; d=p['delivery']; q=d['query']; expected=gold(official,q)['accepted']
        phase=(q['project'],q['key'],q['scope'],tuple(expected))
        seen_error,repaired=phases.get(phase,(False,False)); ok=p['action']['label'] in expected
        if not ok:
            row=d.get('oracle_extra_information') or d['records'][-1]
            old_bound=(p['action']['label'] in old_gold['accepted'] and p['action']['label'] not in expected and
                       (row['source_identity']==old_source or bool(set(row['support']) & old_support)))
            if repaired:
                any_recur=True; old_recur|=old_bound
                events.append(dict(step=s['step'],old_bound=old_bound,
                                   phase=[phase[0],phase[1],phase[2],list(phase[3])]))
            seen_error=True
        elif seen_error: repaired=True
        phases[phase]=(seen_error,repaired)
    return dict(old_influence_reappearance=old_recur,any_error_after_repair=any_recur,events=events)


def summarize(m,episodes):
    buckets=defaultdict(list)
    for j in jobs(m['settings']):
        buckets['/'.join(str(j[k]) for k in ('policy','delay','retention','branch'))]
    for ep in episodes:
        j=ep['job']; key='/'.join(str(j[k]) for k in ('policy','delay','retention','branch'))
        buckets[key].append(ep)
    output={}
    for key,eps in sorted(buckets.items()):
        checkpoints={}
        for horizon in (1,3,10):
            rows=[p for ep in eps for s in ep['snapshots'][:horizon] for p in s['probes'].values()]
            breakdown={}
            for group in ('changed','preserved','boundary','historical'):
                rs=[p for p in rows if (p['scope']==group if group in ('changed','preserved') else p[group])]
                stale=sum(p['score']['version_stale_delivered'] for p in rs)
                errors=sum(p['score']['error_given_stale'] for p in rs)
                breakdown[group]=dict(scored=len(rs),correct=sum(p['score']['correct'] for p in rs),
                    stale_delivered=stale,errors_given_stale=errors,conditional_error_denominator=stale)
            checkpoints[str(horizon)]=dict(scored=len(rows),correct=sum(p['score']['correct'] for p in rows),breakdown=breakdown)
        reappear=0; sustained=0; any_recur=0; traces=[]
        for ep in eps:
            correct=[s['probes']['main']['score']['correct'] for s in ep['snapshots']]
            family=next(f for f in fixtures()['families'] if f['id']==ep['job']['family'])
            recurrence=recurrence_metrics(ep,family)
            reappear+=recurrence['old_influence_reappearance']; any_recur+=recurrence['any_error_after_repair']
            sustained+=not any(correct)
            traces.append(dict(family=ep['job']['family'],main_correct=correct,
                main_labels=[s['probes']['main']['action']['label'] for s in ep['snapshots']],
                recomputations=ep['recomputations'],diagnostic_recomputations=ep['diagnostic_recomputations'],
                first_refresh_task=ep['first_refresh_task'],recurrence=recurrence))
        output[key]=dict(planned_episodes=len(fixtures()['families']),executed_episodes=len(eps),scored_episodes=len(eps),
            families=len({ep['job']['family'] for ep in eps}),checkpoints=checkpoints,
            old_influence_reappearance=reappear,any_error_after_repair=any_recur,persistent_error_episodes=sustained,
            recomputations=sum(ep['recomputations'] for ep in eps),traces=traces)
    return dict(schema='ams-revision-results/1',evidence_kind=m['evidence_kind'],experiment_identity=identity(m),
        planned_episodes=len(jobs(m['settings'])),executed_episodes=len(episodes),scored_episodes=len(episodes),
        unexecuted_episodes=len(jobs(m['settings']))-len(episodes),execution_state='complete' if len(episodes)==len(jobs(m['settings'])) else 'partial-planned',
        outcome_statuses=dict(successful=len(episodes),unexecuted=len(jobs(m['settings']))-len(episodes)),families=len(fixtures()['families']),
        tasks_per_episode=10,probes_per_task=7,results=output,
        limits=['Original public development controls, not LLM/human results or a blinded evaluation.',
                'Task/recomputation counts are not wall latency or model tokens.','used=unknown; citations do not establish causal use.',
                'Delete is a retention ablation, not privacy erasure.','Boundary is a preserved subset; do not sum overlapping groups.'])


def check_saved():
    """Fast identity/conservation checks only; not raw transition replay."""
    saved=load(ROOT/'results.json'); m=manifest(settings()); planned=jobs(); families={f['id'] for f in fixtures()['families']}
    expected_keys={'/'.join(str(j[k]) for k in ('policy','delay','retention','branch')) for j in planned}
    def require(condition,message):
        if not condition: raise ValueError(message)
    def bounded(n,upper,message):
        require(type(n) is int and 0<=n<=upper,message)
    require(saved['experiment_identity']==identity(m),'saved identity drift')
    require(saved['planned_episodes']==len(planned) and saved['executed_episodes']==len(planned)
        and saved['scored_episodes']==len(planned) and saved['unexecuted_episodes']==0,'episode accounting')
    require(saved['outcome_statuses']=={'successful':len(planned),'unexecuted':0} and saved['execution_state']=='complete','outcome accounting')
    require(saved['families']==len(families) and saved['tasks_per_episode']==10 and saved['probes_per_task']==7,'corpus accounting')
    require(set(saved['results'])==expected_keys,'missing/foreign bucket')
    for key,b in saved['results'].items():
        require(b['planned_episodes']==b['executed_episodes']==b['scored_episodes']==len(families),'bucket denominator')
        traces=b['traces']
        require(len(traces)==len(families) and {t['family'] for t in traces}==families and b['families']==len(families),'family traces')
        require(set(b['checkpoints'])=={'1','3','10'},'horizon set')
        for horizon,c in b['checkpoints'].items():
            n=int(horizon); total=len(families)*n*7
            require(c['scored']==total,'scored denominator')
            bounded(c['correct'],total,'invalid correct')
            require(set(c['breakdown'])=={'changed','preserved','boundary','historical'},'breakdown set')
            for group,r in c['breakdown'].items():
                bounded(r['scored'],total,'scope denominator')
                bounded(r['correct'],r['scored'],'scope correct')
                bounded(r['stale_delivered'],r['scored'],'stale denominator')
                bounded(r['errors_given_stale'],r['stale_delivered'],'conditional stale errors')
                require(r['conditional_error_denominator']==r['stale_delivered'],'conditional denominator')
                require(r['errors_given_stale']<=r['scored']-r['correct'],'error conservation')
            changed=c['breakdown']['changed']; preserved=c['breakdown']['preserved']
            require(changed['scored']+preserved['scored']==total and changed['correct']+preserved['correct']==c['correct'],'changed/preserved conservation')
            for field in ('scored','correct','stale_delivered','errors_given_stale'):
                require(c['breakdown']['boundary'][field]<=preserved[field],'boundary subset')
            require(c['breakdown']['historical']['scored']==len(families)*n*4,'history denominator')
        for trace in traces:
            require(len(trace['main_correct'])==10 and all(type(x) is bool for x in trace['main_correct']),'main trace')
            require(len(trace['main_labels'])==10 and all(isinstance(x,str) for x in trace['main_labels']),'label trace')
            recurrence=trace['recurrence']
            require(recurrence['any_error_after_repair']==bool(recurrence['events']),'recurrence events')
            require(recurrence['old_influence_reappearance']==any(e['old_bound'] for e in recurrence['events']),'old influence events')
            for n in (1,3,10):
                main_correct=sum(t['main_correct'][i] for t in traces for i in range(n))
                require(main_correct<=b['checkpoints'][str(n)]['correct']<=main_correct+len(families)*n*6,'main score conservation')
        require(b['recomputations']==sum(t['recomputations'] for t in traces),'recomputation conservation')
        require(b['old_influence_reappearance']==sum(t['recurrence']['old_influence_reappearance'] for t in traces),'reappearance conservation')
        require(b['any_error_after_repair']==sum(t['recurrence']['any_error_after_repair'] for t in traces),'new error conservation')
        require(b['persistent_error_episodes']==sum(not any(t['main_correct']) for t in traces),'persistent error conservation')
    require(sum(b['executed_episodes'] for b in saved['results'].values())==saved['executed_episodes'],'global executed conservation')
    focused=saved['feedback_contrast']
    require(focused['with_writeback']['writes']==10 and focused['without_writeback']['writes']==0,'focused writes')
    require(not focused['with_writeback']['main_correct'][4] and focused['without_writeback']['main_correct'][4],'focused feedback control')
    return dict(status='checked-saved-summary-not-raw-replay',episodes=saved['executed_episodes'],families=9)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('command',choices=('dry-run','run','verify','replay','check-sample'))
    parser.add_argument('--out',type=Path); parser.add_argument('--report',type=Path); parser.add_argument('--check-report',type=Path); parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    try:
        if args.command=='dry-run': result=dict(manifest=manifest(settings()),jobs=jobs(),model_requests=0)
        elif args.command=='check-sample': result=check_saved()
        elif args.out is None: parser.error('--out required')
        elif args.command=='run': result=execute(args.out,limit=args.limit)
        else: result=verify(args.out)
        if args.check_report:
            if result!=load(args.check_report): raise ValueError('saved result differs')
            print('Frozen longitudinal results match verified receipts.')
        elif args.report: freeze(args.report,result)
        else: print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as exc: parser.exit(1,f'{type(exc).__name__}: {exc}\n')


if __name__=='__main__': main()
