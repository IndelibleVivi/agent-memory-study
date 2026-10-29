#!/usr/bin/env python3
"""Native SQLite FTS5 conditional-contribution controls; no network transports."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import uuid

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT.parent / 'experience-reuse-retrieval-study' / 'study.py'
_spec = importlib.util.spec_from_file_location('ams_native_fts5', NATIVE)
retriever = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retriever)
SCHEMA = 'ams-conditional-contribution-results/1'
SCORER = 'conditional-exact-world/1'
ARMS = ('empty', 'B', 'S', 'BS', 'duplicate', 'sham')
SYSTEM = ('Use only the supplied JSONL memory. Return JSON {"action":"answer|abstain",'
          '"value":"string","citations":["record id"]}. Do not use external knowledge. '
          'Missing required evidence permits abstain with value insufficient.')


def canonical(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(v):
    return hashlib.sha256(canonical(v).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sources():
    return {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in
            [('study.py', ROOT/'study.py'), ('corpus.json', ROOT/'corpus.json'),
             ('protocol.md', ROOT/'protocol.md'), ('provider.py', ROOT/'provider.py'), ('native-retriever', NATIVE)]}


def config():
    return {'schema': 'ams-conditional-settings/1', 'budget_bytes': 200, 'top_k': 3,
            'representations': ['raw', 'compact'], 'modes': ['full', 'equal'],
            'policies': ['top-k', 'unique-key'], 'backends': ['scripted', 'oracle'],
            'tokenizer': {'id': 'utf8-bytes/1', 'provider_tokens': False}, 'scorer': SCORER}


def corpus():
    return load(ROOT/'corpus.json')


def writer(records, representation):
    """No question/world/evaluator argument. Compact deletes prose only."""
    if representation not in ('raw', 'compact'):
        raise ValueError('unknown representation')
    result = copy.deepcopy(records)
    if representation == 'compact':
        for r in result:
            r['value'].pop('prose', None)
    return result


def line(record):
    return canonical(record) + '\n'


def sham_like(record):
    sham = {'id': record['id'], 'key': record['key'], 'value': {'kind': 'noise', 'padding': ''}}
    missing = len(line(record).encode()) - len(line(sham).encode())
    if missing < 0:
        raise ValueError('template too short for exact length sham')
    sham['value']['padding'] = 'z' * missing
    assert len(line(sham).encode()) == len(line(record).encode())
    return sham


def materials(case, arm, representation):
    b, s = writer(case['B'], representation), writer(case['S'], representation)
    if arm == 'empty': return []
    if arm == 'B': return b
    if arm == 'S': return s
    if arm == 'BS': return b+s
    if arm == 'duplicate':
        other = copy.deepcopy(b)
        for r in other: r['id'] += '-copy'
        return b+other
    if arm == 'sham': return b+[sham_like(r) for r in s]
    raise ValueError('unknown arm')


def gold(case):
    """World evaluator is separate from retrieval and consumer."""
    w = case['world']
    return str(w['x'] ^ w['y']) if case['family'] == 'complement' else w['value']


def jobs(settings=None):
    settings = config() if settings is None else settings
    result = []
    for c in corpus()['cases']:
        for arm in ARMS:
            for rep in settings['representations']:
                for mode in settings['modes']:
                    for policy in settings['policies']:
                        for backend in settings['backends']:
                            j = {'case': c['id'], 'family': c['family'], 'split': c['split'],
                                 'arm': arm, 'representation': rep, 'mode': mode, 'policy': policy, 'backend': backend}
                            result.append({'id': digest(j)[:24], **j})
    return result


def parsed_memory(memory):
    records = []
    for text in memory.splitlines():
        try:
            r = json.loads(text)
            if isinstance(r, dict) and set(r) == {'id', 'key', 'value'}:
                records.append(r)
        except ValueError:
            pass
    return records


def prepare(case, job, settings=None):
    settings = config() if settings is None else settings
    pool = materials(case, job['arm'], job['representation'])
    ranked = retriever.rank(pool, case['question']['query'])
    chosen = retriever.select(ranked, settings['top_k'], job['policy'])
    by_id = {r['id']: r for r in pool}
    full = ''.join(line(by_id[i]) for i in chosen)
    budget = None if job['mode'] == 'full' else settings['budget_bytes']
    actual = full if budget is None else full.encode()[:budget].decode('utf-8', errors='ignore')
    records = parsed_memory(actual)
    user = canonical({'question': case['question'], 'memory': actual})
    request = {'schema': 'ams-conditional-request/1', 'backend': job['backend'],
               'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
               'generation': {'deterministic': True, 'network': False},
               'tokenizer': settings['tokenizer']}
    if job['backend'] == 'oracle': request['oracle_extra_information'] = {'accepted': gold(case)}
    audit = {'writer': {'id': 'field-preserving-'+job['representation']+'/1',
                       'input_digest': digest({'B': case['B'], 'S': case['S']}), 'output_digest': digest(pool)},
             'candidate_pool': [{'id': r['id'], 'key': r['key'], 'content_digest': digest(r)} for r in pool],
             'ranking': [{'id': r['id'], 'score': r['score'], 'rank': n+1} for n, r in enumerate(ranked)],
             'selected_ids': chosen, 'top_k': settings['top_k'], 'selection_policy': job['policy'],
             'memory_budget_bytes': budget, 'planned_memory_bytes': len(full.encode()),
             'delivered_memory_bytes': len(actual.encode()), 'request_bytes': len(canonical(request).encode()),
             'delivery_digest': digest(actual), 'complete_record_ids': [r['id'] for r in records],
             'truncated': actual != full, 'used': 'unknown'}
    return request, audit


def response(action, value, citations=()):
    return canonical({'action': action, 'value': str(value), 'citations': list(citations)})


def scripted(request):
    """Reads fixed actual messages only; no case/gold/family input."""
    data = json.loads(request['messages'][1]['content'])
    q, records = data['question'], parsed_memory(data['memory'])
    values = [(r['id'], r['value']) for r in records]
    selected = []
    if q['kind'] == 'xor':
        bits = {v.get('name'): (i, v.get('value')) for i, v in values if v.get('kind') == 'bit'}
        if {'x', 'y'} <= bits.keys():
            selected = [bits['x'][0], bits['y'][0]]
            return response('answer', int(bits['x'][1]) ^ int(bits['y'][1]), selected)
    elif q['kind'] == 'fact':
        selected = [(i, v) for i, v in values if v.get('kind') == 'fact']
    elif q['kind'] == 'revision':
        selected = sorted(((i, v) for i, v in values if v.get('kind') == 'revision' and v['at'] <= q['at']),
                          key=lambda item: item[1]['at'])
    elif q['kind'] == 'method':
        selected = [(i, v) for i, v in values if v.get('kind') == 'method' and v.get('condition') == q['condition']]
    if selected:
        i, v = selected[-1]
        return response('answer', v['value'], [i])
    return response('abstain', 'insufficient')


def consume(request):
    if request['backend'] == 'oracle': return response('answer', request['oracle_extra_information']['accepted'])
    if request['backend'] != 'scripted': raise ValueError('no network/provider backend in local runner')
    return scripted(request)


def parse(raw):
    r = json.loads(raw)
    if not isinstance(r, dict) or set(r) != {'action', 'value', 'citations'} or r['action'] not in ('answer', 'abstain'):
        raise ValueError('invalid response schema')
    if not isinstance(r['value'], str) or not isinstance(r['citations'], list) or any(not isinstance(i, str) for i in r['citations']):
        raise ValueError('invalid response types')
    return r


def score(case, audit, raw):
    r = parse(raw)
    correct = r['action'] == 'answer' and r['value'] == gold(case)
    return {'scorer': SCORER, 'task_correct': correct, 'response_status': r['action'],
            'unsupported_answer': r['action'] == 'answer' and not correct,
            'citations_valid': set(r['citations']) <= set(audit['complete_record_ids']),
            'used': 'unknown'}


def freeze(path, value):
    """Atomic complete publication with no overwrite; pending survives interruption."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.pending')
    with tmp.open('xb') as f:
        f.write((canonical(value)+'\n').encode()); f.flush(); os.fsync(f.fileno())
    os.link(tmp, path)
    tmp.unlink()


def manifest(settings):
    return {'schema': 'ams-conditional-run/1', 'sources': sources(), 'settings': settings,
            'job_digest': digest(jobs(settings)), 'sqlite_version': sqlite3.sqlite_version,
            'planned': len(jobs(settings))}


def check_raw(root, settings=None):
    root = Path(root); m = load(root/'manifest.json')
    expected = manifest(m['settings'] if settings is None else settings)
    if {k:v for k,v in m.items() if k != 'run_id'} != expected:
        raise ValueError('manifest source/settings/runtime drift')
    mapping = {j['id']: j for j in jobs(m['settings'])}
    cases = {c['id']: c for c in corpus()['cases']}
    receipts, pending = [], []
    for jd in sorted((root/'attempts').glob('*')) if (root/'attempts').exists() else []:
        if jd.name not in mapping or not jd.is_dir(): raise ValueError('foreign job')
        job = mapping[jd.name]; request, audit = prepare(cases[job['case']], job, m['settings'])
        previous = None; successful = False
        for n, ad in enumerate(sorted(jd.iterdir()), 1):
            if ad.name != f'{n:04d}' or successful: raise ValueError('invalid attempt order')
            sp, rp = ad/'started.json', ad/'receipt.json'
            # A pre-start interruption preserves pending bytes but has no execution claim.
            start = load(sp) if sp.exists() else None
            expected_start = {'run_id': m['run_id'], 'job': job, 'attempt': n, 'retry_of': previous,
                              'request': request, 'audit': audit, 'request_digest': digest(request)}
            if start is not None and start != expected_start: raise ValueError('started binding drift')
            if not rp.exists():
                pending.append((ad, expected_start, start is not None)); previous = f'{job["id"]}/{n:04d}'; continue
            r = load(rp)
            if r['start'] != expected_start or r['start_digest'] != digest(expected_start): raise ValueError('receipt start mismatch')
            if start is None and r['status'] != 'interrupted-before-start': raise ValueError('missing started artifact')
            if r['status'] not in ('successful','failed','parse_failure','indeterminate','interrupted-before-start'):
                raise ValueError('unknown receipt status')
            if r['response_digest'] != digest(r['raw_response']): raise ValueError('raw response binding drift')
            if r['status'] == 'successful':
                if r['score'] != score(cases[job['case']], audit, r['raw_response']): raise ValueError('score/rubric drift')
                successful = True
            elif r['score'] is not None: raise ValueError('failed attempt has score')
            if r['status'] == 'parse_failure':
                try: parse(r['raw_response'])
                except (ValueError, TypeError): pass
                else: raise ValueError('parse_failure has valid response')
            receipts.append(r); previous = f'{job["id"]}/{n:04d}'
    return m, receipts, pending


def receipt(start, status, raw=None, error=None, case=None):
    return {'start': start, 'start_digest': digest(start), 'status': status, 'raw_response': raw,
            'response_digest': digest(raw), 'score': score(case, start['audit'], raw) if status == 'successful' else None,
            'error': error}


@contextmanager
def single_writer(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root/'.writer.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('run already has a writer') from None
        try: yield
        finally: fcntl.flock(lock, fcntl.LOCK_UN)


def run(root, settings=None, resume=False, limit=None, backend=consume):
    root = Path(root); settings = config() if settings is None else settings
    if root.resolve().is_relative_to(ROOT.parent.parent.resolve()): raise ValueError('raw run must stay outside repository')
    if limit is not None and (type(limit) is not int or limit < 0): raise ValueError('invalid limit')
    with single_writer(root):
        if (root/'manifest.json').exists():
            if not resume: raise ValueError('run exists: explicit resume required')
            m, receipts, pending = check_raw(root, settings)
            for ad, start, started in pending:
                r = receipt(start, 'indeterminate' if started else 'interrupted-before-start', error='Interrupted; prior attempt retained.')
                freeze(ad/'receipt.json', r); receipts.append(r)
        else:
            if any(p.name != '.writer.lock' for p in root.iterdir()): raise ValueError('nonempty run without manifest')
            m = {**manifest(settings), 'run_id': str(uuid.uuid4())}; freeze(root/'manifest.json', m); receipts = []
        done = {r['start']['job']['id'] for r in receipts if r['status'] == 'successful'}
        counts = Counter(r['start']['job']['id'] for r in receipts)
        cases = {c['id']: c for c in corpus()['cases']}; count = 0
        for job in jobs(settings):
            if job['id'] in done: continue
            if limit is not None and count >= limit: break
            case = cases[job['case']]; request, audit = prepare(case, job, settings)
            n = counts[job['id']]+1; ad = root/'attempts'/job['id']/f'{n:04d}'
            start = {'run_id': m['run_id'], 'job': job, 'attempt': n,
                     'retry_of': f'{job["id"]}/{n-1:04d}' if n>1 else None,
                     'request': request, 'audit': audit, 'request_digest': digest(request)}
            freeze(ad/'started.json', start)
            try:
                raw = backend(request)
                try: parse(raw); status = 'successful'
                except (ValueError, TypeError): status = 'parse_failure'
                r = receipt(start, status, raw, case=case)
            except Exception as exc:
                r = receipt(start, 'failed', error=type(exc).__name__+': '+str(exc))
            freeze(ad/'receipt.json', r); count += 1
    return replay(root)


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        j = row['job']; groups['/'.join(j[k] for k in ('family','representation','mode','policy','backend','arm'))].append(row)
    aggregates = [{'cell': key, 'planned': len(value), 'successful': sum(x['status']=='successful' for x in value),
                   'task_correct': sum(bool(x['score'] and x['score']['task_correct']) for x in value),
                   'abstain': sum(bool(x['score'] and x['score']['response_status']=='abstain') for x in value)}
                  for key,value in sorted(groups.items())]
    cells = defaultdict(dict)
    for row in rows:
        j=row['job']; key=tuple(j[k] for k in ('case','representation','mode','policy','backend'))
        if row['status']=='successful': cells[key][j['arm']]=int(row['score']['task_correct'])
    contrasts=[]
    for key,arms in sorted(cells.items()):
        if {'empty','B','S','BS'}<=arms.keys():
            contrasts.append({'case':key[0],'representation':key[1],'mode':key[2],'policy':key[3],'backend':key[4],
                              'increment_S_given_B':arms['BS']-arms['B'],
                              'interaction':arms['BS']-arms['B']-arms['S']+arms['empty']})
    return aggregates, contrasts


def replay(root):
    m, receipts, pending = check_raw(root)
    by_job = defaultdict(list)
    for r in receipts: by_job[r['start']['job']['id']].append(r)
    rows=[]
    for j in jobs(m['settings']):
        attempts=by_job[j['id']]; last=attempts[-1] if attempts else None
        rows.append({'job':j,'status':last['status'] if last else 'unexecuted',
                     'score':last['score'] if last else None,
                     'audit':last['start']['audit'] if last else None,
                     'response':parse(last['raw_response']) if last and last['status']=='successful' else None})
    aggregates,contrasts=summarize(rows)
    return {'schema':SCHEMA,'sources':m['sources'],'settings':m['settings'],'sqlite_version':m['sqlite_version'],
            'family_count':4,'case_count':len(corpus()['cases']),'empirical_sample_count':0,
            'planned_jobs':m['planned'],'attempt_count':len(receipts),'pending_attempts':len(pending),
            'rows':rows,'aggregates':aggregates,'contrasts':contrasts,
            'limits':['FTS5 is native; scripted/oracle are finite controls, not model performance.',
                      'Four constructed families, all exposed; no held-out inference or confidence interval.',
                      'Diagnostic UTF-8 bytes are not provider token budgets; used is unknown.']}


def local_report(settings=None):
    settings=config() if settings is None else settings
    cases={c['id']:c for c in corpus()['cases']}; rows=[]
    for j in jobs(settings):
        c=cases[j['case']]; req,audit=prepare(c,j,settings);raw=consume(req)
        rows.append({'job':j,'status':'successful','score':score(c,audit,raw),'audit':audit,'response':parse(raw)})
    a,c=summarize(rows)
    return {'schema':SCHEMA,'sources':sources(),'settings':settings,'sqlite_version':sqlite3.sqlite_version,
            'family_count':4,'case_count':len(cases),'empirical_sample_count':0,'planned_jobs':len(rows),
            'attempt_count':len(rows),'pending_attempts':0,'rows':rows,'aggregates':a,'contrasts':c,
            'limits':['FTS5 is native; scripted/oracle are finite controls, not model performance.',
                      'Four constructed families, all exposed; no held-out inference or confidence interval.',
                      'Diagnostic UTF-8 bytes are not provider token budgets; used is unknown.']}


def provider_plan():
    cases={c['id']:c for c in corpus()['cases']}; cells=[]
    for j in jobs():
        if j['backend']!='scripted': continue
        req,audit=prepare(cases[j['case']],j)
        cells.append({'job':j,'messages':req['messages'],'request_bytes':audit['request_bytes'],
                      'delivery_digest':audit['delivery_digest'],'max_output_tokens':96})
    return {'schema':'ams-conditional-provider-plan/1','status':'awaiting-provider-binding-and-authorization',
            'sources':sources(),'cells':cells,'cell_count':len(cells),'material_scope':'corpus.json original synthetic only',
            'provider':None,'model_revision':None,'tokenizer':None,'authorized':False,
            'input_token_count':None,'fee_cap':None,'output_token_cap':len(cells)*96,
            'selection_gate':'Bind exact provider/model/tokenizer; count actual inputs and fee cap; explicit authorization before transport.',
            'request_contract':'injected-json-transport/1; real-provider wire mapping requires its documented adapter'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',nargs='?',default='report',choices=['run','replay','report','check','packet','provider-plan'])
    p.add_argument('--check',action='store_true',help='recompute local results; alias for check')
    p.add_argument('--out',type=Path);p.add_argument('--output',type=Path);p.add_argument('--resume',action='store_true');p.add_argument('--limit',type=int)
    a=p.parse_args()
    if a.check:
        if a.command not in ('report','check'):p.error('--check cannot combine with this command')
        a.command='check'
    if a.command in ('run','replay') and a.out is None: p.error('--out required')
    if a.command=='run': result=run(a.out,resume=a.resume,limit=a.limit)
    elif a.command=='replay': result=replay(a.out)
    elif a.command=='provider-plan': result=provider_plan()
    elif a.command=='packet':result={'schema':'ams-conditional-packet/1','corpus':corpus(),'protocol':(ROOT/'protocol.md').read_text(),'results':load(ROOT/'sample-results.json'),'provider_plan':provider_plan()}
    else:
        result=local_report()
        if a.command=='check':
            if result!=load(ROOT/'sample-results.json'):raise ValueError('saved local results drift')
            result={'status':'passed-local-recomputation-not-raw-replay','jobs':result['planned_jobs'],'family_count':4,'empirical_sample_count':0}
    if a.output:freeze(a.output,result)
    else:print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,FileExistsError) as exc:raise SystemExit(str(exc))
