"""Post-result question-only diagnostic; separate identity, no new writer calls."""
import argparse
import hashlib
from pathlib import Path

import natural as n
import natural_api as api


def identity():
    return n.identity() | {name: hashlib.sha256((n.ROOT/name).read_bytes()).hexdigest()
                           for name in ('natural_probe.py', 'natural-question-only.md')}


def jobs(data):
    return [{'id': f"{c['id']}--{q['id']}--none--{model}", 'model': model,
             'case': c['id'], 'question': q['id'], 'kind': q['kind'],
             'payload': n.payload(model, n.READER_SYSTEM, n.canonical(
                 {'memory': '', 'task': {'question': q['text'], 'options': q['options']}}))}
            for c in data['cases'] for q in c['questions'] for model in n.MODELS]


def prepare(parent, output):
    parent, manifest, data = n.checked(parent)
    if len(api.responses(parent, 'readers', n.load(parent/'reader-jobs.json'))) != 432:
        raise ValueError('diagnostic follows completed primary run')
    root = n.safe_root(output); root.mkdir(parents=True, exist_ok=False)
    n.freeze(root/'manifest.json', {'schema': 'ams-question-only-run/1', 'source_identity': identity(),
             'parent_manifest': manifest, 'corpus_digest': n.digest(data), 'budget_usd_total': n.BUDGET})
    n.freeze(root/'corpus.json', data)
    for phase in ('canaries', 'writers', 'readers'):
        n.freeze(root/('prior-'+phase+'-preflight.json'), n.load(parent/(phase+'-preflight.json')))


def checked(root, recorded_source=None):
    root = n.safe_root(root)
    m, data = n.load(root/'manifest.json'), n.load(root/'corpus.json')
    n.check_source(m['source_identity'], identity(), recorded_source)
    if m['corpus_digest'] != n.digest(data):
        raise ValueError('diagnostic source/corpus changed')
    return root, data


def replay(root, recorded_source=None):
    root, data = checked(root, recorded_source)
    plan = jobs(data)
    if n.load(root/'question-only-plan.json') != plan:
        raise ValueError('question-only request plan changed')
    rr = api.responses(root, 'question-only', plan)
    truth = {(c['id'], q['id']): q for c in data['cases'] for q in c['questions']}
    groups = []
    for model in n.MODELS:
        rows = []
        usage = {'input_tokens': 0, 'output_tokens': 0, 'cached_tokens': 0, 'reasoning_tokens': 0}
        complete = 0
        for j in plan:
            if j['model'] != model:
                continue
            parsed = n.parse(rr.get(j['id']))
            q = truth[j['case'], j['question']]
            rows.append({'case': j['case'], 'question': j['question'], 'kind': q['kind'], 'gold': q['gold'],
                         'choice': parsed.get('choice'), 'status': parsed['status'],
                         'correct': parsed.get('choice') == q['gold'] if parsed['status'] == 'valid' else False})
            u = api.usage_metadata(rr.get(j['id']))
            if u is not None:
                complete += 1
                for k in usage: usage[k] += u[k]
        groups.append({'model': model, 'correct': sum(r['correct'] for r in rows), 'total': len(rows),
                       'valid': sum(r['status'] == 'valid' for r in rows), 'rows': rows, 'usage': usage,
                       'usage_receipts': complete, 'usage_unavailable': len(rows)-complete,
                       'usage_estimate_usd': round((usage['input_tokens']*n.PRICES[model][0]
                                                   + usage['output_tokens']*n.PRICES[model][2])/1e6, 6)})
    return {'schema': 'ams-question-only-results/1', 'status': 'post-result-diagnostic',
            'source_identity': n.load(root/'manifest.json')['source_identity'], 'replay_source_identity': identity(),
            'date': '2026-11-07', 'planned_calls': len(plan), 'receipts': len(rr), 'groups': groups,
            'raw_receipts_digest': n.digest(rr), 'total_reserved_usd_including_primary':
            sum(n.load(p)['upper_usd'] for p in root.glob('*-preflight.json'))}


def check_saved():
    s = n.load(n.ROOT/'natural-question-only-results.json')
    n.check_saved_source(s, identity())
    if s['planned_calls'] != 144 or s['receipts'] != 144:
        raise ValueError('saved question-only identity/count mismatch')
    truth = {(c['id'], q['id']): q for c in n.corpus()['cases'] for q in c['questions']}
    if [g['model'] for g in s['groups']] != list(n.MODELS): raise ValueError('model mismatch')
    for g in s['groups']:
        rows = g['rows']
        if len(rows) != 72 or {(r['case'], r['question']) for r in rows} != set(truth):
            raise ValueError('question identity mismatch')
        for r in rows:
            q = truth[r['case'], r['question']]
            if r['gold'] != q['gold'] or r['kind'] != q['kind'] or r['correct'] != (r['status']=='valid' and r['choice']==q['gold']):
                raise ValueError('score mismatch')
        if g['correct'] != sum(r['correct'] for r in rows) or g['valid'] != sum(r['status']=='valid' for r in rows):
            raise ValueError('summary mismatch')
    return {'calls': 144, 'groups': len(s['groups'])}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('prepare', 'run', 'replay', 'check-saved'))
    p.add_argument('--run', type=Path); p.add_argument('--parent', type=Path); p.add_argument('--output', type=Path)
    p.add_argument('--recorded-source', type=Path, help='replay only: verified execution-source archive')
    a = p.parse_args()
    if a.recorded_source and a.command != 'replay':
        p.error('--recorded-source is only allowed for offline replay')
    if a.command == 'prepare':
        if not a.parent or not a.output: p.error('prepare requires --parent and --output')
        prepare(a.parent, a.output)
    elif a.command == 'check-saved': print(n.canonical(check_saved()))
    else:
        if not a.run: p.error('--run required')
        if a.command == 'run':
            root, data = checked(a.run)
            with api.locked(root): api.run_phase(root, 'question-only', jobs(data))
        else:
            result = replay(a.run, a.recorded_source)
            if a.output: n.freeze(a.output, result)
            print(n.canonical(result))
