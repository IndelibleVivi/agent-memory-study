"""Explicit official API execution and offline raw replay. Never invoked by CI."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

import natural as n

BASE = 'https://api.openai.com/v1'


def now():
    return datetime.now(timezone.utc).isoformat()


def post(endpoint, payload):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise ValueError('operator must supply OPENAI_API_KEY in the runtime environment')
    req = urllib.request.Request(BASE + endpoint, n.canonical(payload).encode(),
                                 {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    started, clock = now(), time.monotonic()
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=60) as response:
            body, status, request_id = response.read(), response.status, response.headers.get('x-request-id')
    except urllib.error.HTTPError as exc:
        body, status, request_id = exc.read(), exc.code, exc.headers.get('x-request-id')
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {'http_status': None, 'raw_body': None, 'transport_error': type(exc).__name__,
                'started_at': started, 'finished_at': now(), 'elapsed_seconds': time.monotonic()-clock}
    return {'http_status': status, 'raw_body': body.decode('utf-8', errors='replace'),
            'invalid_utf8_hex': body.hex() if body.decode('utf-8', errors='replace').encode() != body else None,
            'request_id': request_id, 'started_at': started, 'finished_at': now(),
            'elapsed_seconds': time.monotonic()-clock}


@contextmanager
def locked(root):
    path = root / '.execution.lock'
    with path.open('x') as stream:
        stream.write(str(os.getpid()))
    try:
        yield
    finally:
        path.unlink()


def canary_jobs():
    return [{'id': model, 'payload': n.payload(model, n.READER_SYSTEM,
            '接口格式检查，无研究题目。请返回choice=A、sources=[]、basis=格式正常。')}
            for model in n.MODELS]


def responses(root, phase, jobs):
    folder = root / phase
    known = {j['id'] for j in jobs}
    if {p.name[:-len('.response.json')] for p in folder.glob('*.response.json')} - known:
        raise ValueError('foreign response artifact')
    output = {}
    for job in jobs:
        req_path = folder / (job['id'] + '.request.json')
        response_path = folder / (job['id'] + '.response.json')
        if req_path.exists() and n.load(req_path) != job['payload']:
            raise ValueError('actual request does not match frozen job')
        if response_path.exists():
            receipt = n.load(response_path)
            started = n.load(folder / (job['id'] + '.started.json'))
            if (not req_path.exists() or receipt['request_digest'] != n.digest(job['payload'])
                    or started['request_digest'] != receipt['request_digest'] or receipt['job'] != job['id']):
                raise ValueError('response/input binding failure')
            output[job['id']] = receipt
    return output


def run_phase(root, phase, jobs):
    """No retry: an existing request without a receipt remains outcome-unknown."""
    folder = root / phase
    folder.mkdir(exist_ok=True)
    plan_path = root / (phase + '-plan.json')
    if plan_path.exists():
        if n.load(plan_path) != jobs:
            raise ValueError('phase plan changed')
    else:
        n.freeze(plan_path, jobs)
    existing = responses(root, phase, jobs)
    preflight_path = root / (phase + '-preflight.json')
    if not preflight_path.exists():
        def count(job):
            p = job['payload']
            if p is None:
                return job['id'], 0
            request = {k: p[k] for k in ('model', 'input', 'reasoning', 'text')}
            cp = folder / (job['id'] + '.count-request.json')
            rp = folder / (job['id'] + '.count-response.json')
            if cp.exists():
                if n.load(cp) != request or not rp.exists():
                    raise ValueError('interrupted count; preserve this run and investigate')
                result = n.load(rp)
            else:
                n.freeze(cp, request)
                result = post('/responses/input_tokens', request)
                n.freeze(rp, result)
            if result['http_status'] != 200:
                raise ValueError('token count failed; inspect retained receipt, no generation in this phase')
            value = json.loads(result['raw_body'])['input_tokens']
            if type(value) is not int or value <= 0:
                raise ValueError('invalid input token count')
            return job['id'], value
        with ThreadPoolExecutor(max_workers=4) as pool:
            counts = dict(pool.map(count, jobs))
        upper = sum((counts[j['id']] * n.PRICES[j['payload']['model']][1]
                    + j['payload']['max_output_tokens'] * n.PRICES[j['payload']['model']][2]) / 1e6
                    for j in jobs if j['payload'])
        reserved = sum(n.load(p)['upper_usd'] for p in root.glob('*-preflight.json'))
        if upper + reserved > n.BUDGET:
            raise ValueError(f'budget would exceed ${n.BUDGET}: {upper + reserved:.4f}; no generation')
        n.freeze(preflight_path, {'counts': counts, 'upper_usd': upper,
                                 'cumulative_reserved_usd': upper+reserved, 'plan_digest': n.digest(jobs)})
    pre = n.load(preflight_path)
    if pre['plan_digest'] != n.digest(jobs) or pre['cumulative_reserved_usd'] > n.BUDGET:
        raise ValueError('preflight binding or budget failure')

    def call(job):
        if not job['payload'] or job['id'] in existing:
            return
        request_path = folder / (job['id'] + '.request.json')
        if request_path.exists():
            return  # Possibly charged, outcome unknown; never repeat automatically.
        n.freeze(request_path, job['payload'])
        n.freeze(folder / (job['id'] + '.started.json'), {'at': now(), 'request_digest': n.digest(job['payload'])})
        receipt = post('/responses', job['payload'])
        n.freeze(folder / (job['id'] + '.response.json'),
                 receipt | {'job': job['id'], 'request_digest': n.digest(job['payload'])})
    print(f'{phase}: {len(jobs)} planned, upper reserve ${pre["cumulative_reserved_usd"]:.4f}', flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(call, jobs))
    result = responses(root, phase, jobs)
    completion = {'phase': phase, 'planned': len(jobs), 'receipts': len(result), 'at': now()}
    if not (root / (phase + '-completion.json')).exists():
        n.freeze(root / (phase + '-completion.json'), completion)
    print(n.canonical(completion), flush=True)
    return result


def write(root):
    root, _, data = n.checked(root)
    with locked(root):
        canaries = run_phase(root, 'canaries', canary_jobs())
        if any(n.parse(canaries.get(j['id'])).get('choice') != 'A' for j in canary_jobs()):
            raise ValueError('canary failed; no research calls')
        jobs = n.writer_jobs(data)
        result = run_phase(root, 'writers', jobs)
        memories = {j['id']: n.parse(result.get(j['id']), True) for j in jobs}
        for name, value in (('memories.json', memories), ('reader-jobs.json', n.reader_jobs(data, memories))):
            if (root / name).exists():
                if n.load(root / name) != value:
                    raise ValueError('generated memory/reader plan changed')
            else:
                n.freeze(root / name, value)
    print(n.canonical({'memory_statuses': {j: m['status'] for j, m in memories.items()}}), flush=True)


def frozen_readers(root, data):
    origin = root / 'writer-origin.json'
    if origin.exists():
        for name, expected in n.load(origin)['artifact_digests'].items():
            ref = Path(name)
            if ref.is_absolute() or '..' in ref.parts or n.digest(n.load(root / ref)) != expected:
                raise ValueError('inherited writer artifact changed')
    wr = responses(root, 'writers', n.writer_jobs(data))
    memories = {j['id']: n.parse(wr.get(j['id']), True) for j in n.writer_jobs(data)}
    if n.load(root / 'memories.json') != memories:
        raise ValueError('memory does not match actual writer response')
    jobs = n.reader_jobs(data, memories)
    if n.load(root / 'reader-jobs.json') != jobs:
        raise ValueError('reader input does not match actual generated memory')
    return memories, jobs


def inherit_writers(origin, output):
    """Carry every unchanged writer request/receipt into an explicitly amended run."""
    origin = n.safe_root(origin)
    data = n.load(origin / 'corpus.json')
    old_manifest = n.load(origin / 'manifest.json')
    if data != n.corpus() or old_manifest['corpus_digest'] != n.digest(data):
        raise ValueError('writer corpus differs; cannot inherit')
    if any((origin / 'readers').glob('*.request.json')):
        raise ValueError('this amendment requires zero previous reader calls')
    plans = [('canaries', canary_jobs()), ('writers', n.writer_jobs(data))]
    for phase, jobs in plans:
        if n.load(origin / (phase+'-plan.json')) != jobs:
            raise ValueError('writer/canary request changed; cannot inherit')
        if len(responses(origin, phase, jobs)) != len(jobs):
            raise ValueError('inherit every completed writer; no outcome selection')
    n.prepare(output)
    root = n.safe_root(output)
    copied = {}
    for phase, jobs in plans:
        names = [phase+'-'+suffix+'.json' for suffix in ('plan', 'preflight', 'completion')]
        names += [phase+'/'+j['id']+'.'+suffix+'.json' for j in jobs
                  for suffix in ('request', 'started', 'response', 'count-request', 'count-response')]
        for name in names:
            value = n.load(origin / name)
            n.freeze(root / name, value)
            copied[name] = n.digest(value)
    n.freeze(root / 'writer-origin.json', {'schema': 'ams-natural-writer-inheritance/1',
             'origin_manifest': old_manifest, 'artifact_digests': copied,
             'reason': 'before-reader length-policy amendment; all writer inputs and outputs unchanged'})
    wr = responses(root, 'writers', n.writer_jobs(data))
    memories = {j['id']: n.parse(wr[j['id']], True) for j in n.writer_jobs(data)}
    n.freeze(root / 'memories.json', memories)
    n.freeze(root / 'reader-jobs.json', n.reader_jobs(data, memories))
    frozen_readers(root, data)


def read(root):
    root, _, data = n.checked(root)
    with locked(root):
        _, jobs = frozen_readers(root, data)
        run_phase(root, 'readers', jobs)


def usage_metadata(receipt):
    """Optional provider accounting must not invalidate independently scored evidence."""
    if not receipt or receipt.get('http_status') != 200:
        return None
    try:
        body = json.loads(receipt['raw_body'])
        if not isinstance(body, dict) or not isinstance(body.get('usage'), dict):
            return None
        usage = body['usage']
        totals = {k: usage[k] for k in ('input_tokens', 'output_tokens')}
        for detail, name in (('input_tokens_details', 'cached_tokens'),
                             ('output_tokens_details', 'reasoning_tokens')):
            details = usage.get(detail, {})
            if not isinstance(details, dict):
                return None
            totals[name] = details.get(name, 0)
        if any(type(v) is not int or v < 0 for v in totals.values()):
            return None
        return totals | {'model': body.get('model') if isinstance(body.get('model'), str) else None}
    except (ValueError, TypeError, KeyError):
        return None


def replay(root, recorded_source=None):
    root, manifest, data = n.checked(root, recorded_source)
    memories, jobs = frozen_readers(root, data)
    rr = responses(root, 'readers', jobs)
    summary = n.aggregate(data, jobs, rr)
    usage = []
    receipt_binding = {}
    for phase, plan in (('canaries', canary_jobs()), ('writers', n.writer_jobs(data)), ('readers', jobs)):
        receipts = responses(root, phase, plan)
        if n.load(root / (phase + '-plan.json')) != plan:
            raise ValueError('replay plan mismatch')
        pre = n.load(root / (phase + '-preflight.json'))
        if pre['plan_digest'] != n.digest(plan):
            raise ValueError('preflight plan mismatch')
        for j in plan:
            if not j['payload']:
                continue
            count_request = n.load(root / phase / (j['id'] + '.count-request.json'))
            if count_request != {k: j['payload'][k] for k in ('model', 'input', 'reasoning', 'text')}:
                raise ValueError('token count request mismatch')
            count_receipt = n.load(root / phase / (j['id'] + '.count-response.json'))
            if json.loads(count_receipt['raw_body'])['input_tokens'] != pre['counts'][j['id']]:
                raise ValueError('token count receipt mismatch')
        for model in n.MODELS:
            selected = [j for j in plan if j['payload'] and j['payload']['model'] == model]
            if not selected:
                continue
            totals = {'input_tokens': 0, 'output_tokens': 0, 'cached_tokens': 0, 'reasoning_tokens': 0}
            matched, models, complete = True, set(), 0
            for j in selected:
                r = receipts.get(j['id'])
                receipt_binding[phase + ':' + j['id']] = n.digest(r)
                u = usage_metadata(r)
                if u is None:
                    continue
                complete += 1
                if u['model'] is not None:
                    models.add(u['model'])
                matched &= u['input_tokens'] == pre['counts'][j['id']]
                for k in totals:
                    totals[k] += u[k]
            rate = n.PRICES[model]
            # No cache discount claimed: upper estimate from returned usage, not an invoice.
            estimate = (totals['input_tokens'] * rate[0] + totals['output_tokens'] * rate[2]) / 1e6
            usage.append({'phase': phase, 'model': model, 'planned': len(selected), 'usage_receipts': complete,
                          'usage_unavailable': len(selected)-complete,
                          'returned_models': sorted(models), 'input_counts_match': matched if complete else None,
                          **totals, 'undiscounted_usage_estimate_usd': round(estimate, 6)})
    return {'schema': 'ams-natural-scope-results/1', 'status': 'executed-exploratory-model-diagnostic',
            'date': '2026-11-07', 'source_identity': manifest['source_identity'],
            'replay_source_identity': n.identity(),
            'raw_receipts_digest': n.digest(receipt_binding), 'independent_histories': len(data['cases']),
            'questions_per_history': 6, 'planned_reader_calls': len(jobs), 'reader_receipts': len(rr),
            'writer_model': n.WRITER_MODEL, 'memory_limit_characters': n.MEMORY_LIMIT,
            'memories': {k: {'status': v['status'], 'characters': len(v.get('memory', '')),
                            'within_requested_budget': v.get('within_requested_budget', False)} for k, v in memories.items()},
            'writer_inherited_without_regeneration': (root / 'writer-origin.json').exists(),
            'usage': usage, 'undiscounted_usage_estimate_usd': round(sum(u['undiscounted_usage_estimate_usd'] for u in usage), 6),
            'reserved_upper_usd': round(sum(n.load(p)['upper_usd'] for p in root.glob('*-preflight.json')), 6),
            **summary}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=('writers', 'readers', 'replay', 'inherit-writers'))
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--output', type=Path, help='exclusive replay output; does not call API')
    ap.add_argument('--recorded-source', type=Path, help='replay only: verified execution-source archive')
    a = ap.parse_args()
    if a.recorded_source and a.command != 'replay':
        ap.error('--recorded-source is only allowed for offline replay')
    if a.command == 'inherit-writers':
        if not a.output:
            ap.error('inherit-writers requires --output for a new run')
        inherit_writers(a.run, a.output)
        print('Inherited all identical writer/canary requests and responses; no API called.')
    elif a.command == 'writers':
        write(a.run)
    elif a.command == 'readers':
        read(a.run)
    else:
        result = replay(a.run, a.recorded_source)
        if a.output:
            n.freeze(a.output, result)
        print(n.canonical(result))
