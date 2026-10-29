#!/usr/bin/env python3
"""Finite observation contracts; stdlib only, no provider or private inputs."""
from __future__ import annotations
import argparse
from fractions import Fraction
import hashlib
import heapq
from itertools import combinations, product
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA = 'ams-observation-contract-results/1'
GATES = ('permitted', 'available', 'correct_revision', 'target_bound', 'adequate_coverage')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def cost(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError('cost must be a nonnegative integer or exact rational string')
    try:
        c = Fraction(value)
    except (ValueError, ZeroDivisionError):
        raise ValueError('invalid rational cost') from None
    if c < 0:
        raise ValueError('negative cost')
    return c


def validate_model(model):
    if set(model) != {'id', 'family', 'description', 'plant', 'evaluator'}:
        raise ValueError('model fields differ from contract')
    p, e = model['plant'], model['evaluator']
    if set(p) != {'states', 'actions', 'side_information_description'}:
        raise ValueError('plant fields differ from contract')
    states, actions = p['states'], p['actions']
    if not states or not isinstance(states, dict) or not isinstance(actions, dict):
        raise ValueError('finite states/actions required')
    for a, spec in actions.items():
        if set(spec) != {'cost', 'gates', 'meaning'} or not isinstance(spec['gates'], dict):
            raise ValueError('invalid action')
        cost(spec['cost'])
        if set(spec['gates']) - set(GATES) or any(type(v) is not bool for v in spec['gates'].values()):
            raise ValueError('invalid access gates')
    for name, s in states.items():
        if set(s) != {'observation', 'side_information', 'transitions'}:
            raise ValueError('state may contain only observable data and transitions')
        if set(s['transitions']) != set(actions):
            raise ValueError('deterministic transition must be total')
        for a, t in s['transitions'].items():
            if set(t) != {'next', 'output'} or t['next'] not in states:
                raise ValueError('invalid deterministic transition')
        encoded(s['observation']); encoded(s['side_information'])
    if set(e) != {'targets', 'answers', 'question_descriptions'} or set(e['targets']) != set(states):
        raise ValueError('evaluator states differ')
    if set(e['answers']) != set(e['question_descriptions']):
        raise ValueError('question mismatch')
    for answers in e['answers'].values():
        if set(answers) != set(states) or any(not isinstance(v, list) or not v or
            any(not isinstance(a, str) for a in v) or len(v) != len(set(v)) for v in answers.values()):
            raise ValueError('nonempty finite answer sets required for every state')
    return model


def initial(plant, state):
    s = plant['states'][state]
    return {'observation': s['observation'], 'side_information': s['side_information']}


def allowed_actions(plant):
    return sorted(a for a, spec in plant['actions'].items() if all(spec['gates'].values()))


def partition(plant):
    groups = {}
    for state in sorted(plant['states']):
        groups.setdefault(encoded(initial(plant, state)), []).append(state)
    return [{'observation': json.loads(key), 'members': members} for key, members in sorted(groups.items())]


def compatibility(members, answers):
    common = set.intersection(*(set(answers[s]) for s in members))
    witness = None
    if not common:
        for n in range(1, len(members) + 1):
            witness = next((list(c) for c in combinations(sorted(members), n)
                            if not set.intersection(*(set(answers[s]) for s in c))), None)
            if witness:
                break
    return {'compatible': bool(common), 'common_answers': sorted(common), 'minimal_conflict': witness}


def trace_word(plant, left, right, word):
    """Execute public transitions only; evaluator never enters this function."""
    trace = [{'step': 0, 'left': initial(plant, left), 'right': initial(plant, right)}]
    for step, action in enumerate(word, 1):
        if action not in allowed_actions(plant):
            raise ValueError('action inaccessible under declared gates')
        lt, rt = (plant['states'][s]['transitions'][action] for s in (left, right))
        trace.append({'step': step, 'action': action, 'left': lt['output'], 'right': rt['output']})
        left, right = lt['next'], rt['next']
    return trace


def search_pair(plant, left, right, max_steps=None, max_cost=None):
    """Dijkstra on pairs. Input contains no target labels or answer contracts."""
    if left not in plant['states'] or right not in plant['states']:
        raise ValueError('unknown state')
    if max_steps is not None and (type(max_steps) is not int or max_steps < 0):
        raise ValueError('max_steps must be a nonnegative integer')
    budget = None if max_cost is None else cost(max_cost)
    bounded = max_steps is not None or budget is not None
    actions = allowed_actions(plant)
    rejected = sorted(set(plant['actions']) - set(actions))
    base = {'pair': [left, right], 'bounds': {'max_steps': max_steps, 'max_cost': None if budget is None else str(budget)},
            'allowed_actions': actions, 'inaccessible_actions': rejected,
            'optimization': 'cost-then-steps-then-lexicographic-word',
            'scope': 'minimum-within-declared-bounds' if bounded else 'global-minimum'}
    if initial(plant, left) != initial(plant, right):
        return {**base, 'status': 'distinguished', 'word': [], 'cost': '0', 'steps': 0,
                'trace': trace_word(plant, left, right, []), 'expanded': [], 'pruned_by_bound': 0}
    # Pending distinguishing edges also enter the heap: returning upon edge
    # generation would incorrectly prefer an expensive one-step observation.
    queue = [(Fraction(0), 0, (), left, right, False)]
    best, expanded, pruned = {}, [], 0
    while queue:
        total, steps, word, ls, rs, found = heapq.heappop(queue)
        if found:
            return {**base, 'status': 'distinguished', 'word': list(word), 'cost': str(total),
                    'steps': steps, 'trace': trace_word(plant, left, right, word),
                    'expanded': expanded, 'pruned_by_bound': pruned}
        key = (ls, rs, steps) if max_steps is not None else (ls, rs)
        rank = total, steps, word
        if key in best and best[key] <= rank:
            continue
        best[key] = rank
        expanded.append({'pair': [ls, rs], 'cost': str(total), 'steps': steps, 'word': list(word)})
        for action in actions:
            nc, ns = total + cost(plant['actions'][action]['cost']), steps + 1
            if (max_steps is not None and ns > max_steps) or (budget is not None and nc > budget):
                pruned += 1
                continue
            lt, rt = (plant['states'][s]['transitions'][action] for s in (ls, rs))
            heapq.heappush(queue, (nc, ns, word + (action,), lt['next'], rt['next'], lt['output'] != rt['output']))
    return {**base, 'status': 'not-distinguished-within-bound' if bounded else 'indistinguishable-in-declared-model',
            'word': None, 'cost': None, 'steps': None, 'trace': [], 'expanded': expanded,
            'pruned_by_bound': pruned, 'certificate': 'reachable-product-closure' if not bounded else 'bounded-search-exhausted'}


def naive_pair(plant, left, right, max_steps, max_cost=None):
    """Independent exhaustive word enumerator for small-domain validation."""
    candidates = []
    budget = None if max_cost is None else cost(max_cost)
    # Deliberately no product-state memo, heap, or optimized search call.
    actions = sorted(a for a, s in plant['actions'].items() if all(s['gates'].values()))
    for n in range(max_steps + 1):
        for word in product(actions, repeat=n):
            total = sum((cost(plant['actions'][a]['cost']) for a in word), Fraction(0))
            if budget is not None and total > budget:
                continue
            ls, rs = left, right
            different = initial(plant, ls) != initial(plant, rs)
            for action in word:
                lt = plant['states'][ls]['transitions'][action]
                rt = plant['states'][rs]['transitions'][action]
                different |= lt['output'] != rt['output']
                ls, rs = lt['next'], rt['next']
            if different:
                candidates.append((total, n, word))
    return min(candidates) if candidates else None


def analyze(model):
    validate_model(model)
    p, e = model['plant'], model['evaluator']
    classes = partition(p)
    for c in classes:
        c['questions'] = {q: compatibility(c['members'], a) for q, a in sorted(e['answers'].items())}
        c['target_collisions'] = [list(pair) for pair in combinations(c['members'], 2)
                                  if e['targets'][pair[0]] != e['targets'][pair[1]]]
    pairs = []
    for left, right in combinations(sorted(p['states']), 2):
        pair = {'states': [left, right], 'unbounded': search_pair(p, left, right),
                'step_bound_1': search_pair(p, left, right, max_steps=1)}
        fast = search_pair(p, left, right, max_steps=5)
        slow = naive_pair(p, left, right, 5)
        observed = None if fast['word'] is None else (cost(fast['cost']), fast['steps'], tuple(fast['word']))
        if observed != slow:
            raise ValueError('independent enumeration disagrees')
        pair['independent_check'] = {'method': 'all-action-words-through-length-5', 'passed': True,
                                     'minimum': None if slow is None else {'cost': str(slow[0]), 'steps': slow[1], 'word': list(slow[2])}}
        pairs.append(pair)
    return {'id': model['id'], 'family': model['family'], 'description': model['description'],
            'state_count': len(p['states']), 'observation_class_count': len(classes),
            'question_descriptions': e['question_descriptions'], 'classes': classes, 'pairs': pairs}


def source_bindings():
    return {name: 'sha256:' + hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ('study.py', 'protocol.md', 'fixtures.json')}


def run():
    fixtures = json.loads((ROOT / 'fixtures.json').read_text())
    models = fixtures['models']
    if len({m['id'] for m in models}) != len(models):
        raise ValueError('duplicate model ID')
    bindings = source_bindings()
    return {'schema': SCHEMA, 'method': 'exact-finite-deterministic-observation-and-action-study',
            'byline': 'Agent Memory Study editors', 'date': '2026-10-29',
            'empirical_sample_count': 0, 'bindings': bindings, 'model_count': len(models),
            'family_count': len({m['family'] for m in models}),
            'models': [analyze(m) for m in models],
            'limits': ['Constructed models; no human/model/provider observations.',
                       'Minimality covers declared actions, transitions, costs and bounds only.',
                       'Pairwise open-loop search is not a multi-hypothesis adaptive policy.',
                       'Target/evaluator labels never enter search or visible output.']}


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--packet', action='store_true', help='portable input + result JSON; no executable content')
    parser.add_argument('--search', nargs=3, metavar=('MODEL', 'LEFT', 'RIGHT'))
    parser.add_argument('--max-steps', type=int)
    parser.add_argument('--max-cost')
    args = parser.parse_args()
    if args.check and (args.output or args.packet or args.search):
        parser.error('--check is exclusive')
    if args.packet and args.search:
        parser.error('--packet exports a complete study, not an isolated search')
    if args.search:
        model_id, left, right = args.search
        data = json.loads((ROOT / 'fixtures.json').read_text())
        matches = [m for m in data['models'] if m['id'] == model_id]
        if not matches:
            parser.error('unknown model')
        validate_model(matches[0])
        result = search_pair(matches[0]['plant'], left, right, args.max_steps, args.max_cost)
    else:
        if args.max_steps is not None or args.max_cost is not None:
            parser.error('bounds apply only to --search')
        result = run()
    if args.check:
        if result != json.loads((ROOT / 'results.json').read_text()):
            raise ValueError('saved results drift: regenerate intentionally to a fresh output path')
        print('PASS observation contracts: exact recomputation and independent enumeration; empirical samples=0')
        return
    if args.packet:
        result = {'schema': 'ams-observation-contract-packet/1',
                  'fixtures': json.loads((ROOT / 'fixtures.json').read_text()), 'results': result}
    if args.output:
        write_new(args.output, result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, FileExistsError) as exc:
        raise SystemExit(str(exc))
