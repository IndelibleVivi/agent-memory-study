#!/usr/bin/env python3
"""Exact, authored set-utility witnesses; no models, network, or retrieved corpora.

All candidate costs are one slot. The observation lower bound is about an
interface exposing only utilities for sets of size <= 2, not graph topology.
"""
import argparse
from fractions import Fraction
from itertools import combinations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def subsets(items, maximum=None):
    items = tuple(items)
    for k in range(len(items) + 1 if maximum is None else min(maximum, len(items)) + 1):
        for s in combinations(items, k):
            yield frozenset(s)


def enc(x):
    if isinstance(x, Fraction):
        return str(x)
    if isinstance(x, (set, frozenset)):
        return sorted(x)
    raise TypeError(type(x).__name__)


def choose(n, k):
    return len(list(combinations(range(n), k))) if 0 <= k <= n else 0


def hidden_support_study(n, budget):
    items = tuple(range(n))
    supports = tuple(subsets(items, 3))
    supports = tuple(t for t in supports if len(t) == 3)
    low_sets = tuple(subsets(items, 2))
    transcripts = {tuple(int(t <= s) for s in low_sets) for t in supports}
    assert len(transcripts) == 1 and set(next(iter(transcripts))) == {0}
    policies = tuple(s for s in subsets(items, budget) if len(s) == budget)
    successes = [sum(t <= s for t in supports) for s in policies]
    expected_count = choose(budget, 3)
    assert all(k == expected_count for k in successes)
    smaller_policy_best = max(
        Fraction(sum(t <= s for t in supports), len(supports))
        for s in subsets(items, budget)
    )
    bound = Fraction(choose(budget, 3), choose(n, 3))
    assert smaller_policy_best == bound
    oracle = Fraction(int(budget >= 3))
    return {
        'n': n, 'budget_slots': budget, 'support_size': 3,
        'hidden_supports': len(supports), 'low_order_queries_per_world': len(low_sets),
        'distinct_low_order_transcripts': len(transcripts),
        'final_size_b_slates': len(policies),
        'successful_worlds_per_size_b_slate': expected_count,
        'uniform_hidden_support_success': bound,
        'support_aware_oracle_success': oracle,
        'interpretation': 'Exhaustive states of one authored utility family, not independent tasks.'
    }


def package_greedy(items, budget, utility, lookahead):
    selected = frozenset()
    trace = []
    while len(selected) < budget:
        remaining = sorted(set(items) - selected)
        packages = list(subsets(remaining, min(lookahead, budget - len(selected))))
        packages = [p for p in packages if p]
        if not packages:
            break
        # Deterministic: descending gain/cost, then gain; lexical tie break.
        ranked = sorted(packages, key=lambda p: (
            -(utility(selected | p) - utility(selected)) / len(p),
            -(utility(selected | p) - utility(selected)), tuple(sorted(p))))
        package = ranked[0]
        gain = utility(selected | package) - utility(selected)
        trace.append({'before': selected, 'package': package, 'gain': gain,
                      'gain_per_slot': gain / len(package)})
        selected |= package
    return {'selected': selected, 'value': utility(selected), 'trace': trace}


def decoy_study(epsilon):
    support = frozenset(['s1', 's2', 's3'])
    decoys = frozenset(['d1', 'd2', 'd3'])
    items = sorted(support | decoys)
    def utility(s):
        return max(Fraction(int(support <= s)), epsilon * len(s & decoys))
    table = [{'set': s, 'value': utility(s)} for s in subsets(items)]
    assert len(table) == 64
    assert all(utility(a) <= utility(b) for a in subsets(items)
               for b in subsets(items) if a <= b)
    a, b, e = frozenset(), frozenset(['s1', 's2']), 's3'
    small = utility(a | {e}) - utility(a)
    large = utility(b | {e}) - utility(b)
    assert small == 0 and large == 1  # Violates diminishing returns.
    third_difference = sum(((-1) ** (3 - len(u))) * utility(u) for u in subsets(support))
    assert third_difference == 1
    policies = {str(k): package_greedy(items, 3, utility, k) for k in [1, 2, 3]}
    assert policies['1']['selected'] == decoys
    assert policies['2']['selected'] == decoys
    assert policies['1']['value'] == policies['2']['value'] == 3 * epsilon
    assert policies['3']['selected'] == support and policies['3']['value'] == 1
    optimum = max(utility(s) for s in subsets(items, 3))
    assert optimum == 1
    return {'epsilon': epsilon, 'budget_slots': 3, 'support': support,
            'decoys': decoys, 'optimum': optimum, 'policies_by_package_lookahead': policies,
            'submodularity_counterexample': {'A': a, 'B': b, 'element': e,
                'marginal_at_A': small, 'marginal_at_B': large},
            'third_finite_difference_at_empty': third_difference,
            'all_subset_utilities': table}


def positive_control():
    weights = {'a': Fraction(6, 20), 'b': Fraction(5, 20), 'c': Fraction(4, 20),
               'd': Fraction(3, 20), 'e': Fraction(2, 20)}
    def utility(s):
        return sum((weights[i] for i in s), Fraction())
    result = package_greedy(sorted(weights), 3, utility, 1)
    optimum = max(utility(s) for s in subsets(weights, 3))
    assert result['value'] == optimum == Fraction(3, 4)
    assert all(utility(a | {e}) - utility(a) == utility(b | {e}) - utility(b)
               for a in subsets(weights) for b in subsets(weights) if a <= b
               for e in weights if e not in b)
    return {'kind': 'additive utility, unit costs', 'weights': weights,
            'greedy': result, 'optimum': optimum}


def alternative_supports():
    universe = frozenset('abcde')
    supports = [frozenset('abc'), frozenset('de')]
    def complete(s):
        return any(t <= s for t in supports)
    def observe(name, pool, selected, budget):
        pool, selected = frozenset(pool), frozenset(selected)
        assert selected <= pool and len(selected) <= budget
        feasible = any(t <= pool and len(t) <= budget for t in supports)
        return {'name': name, 'pool': pool, 'selected': selected, 'budget_slots': budget,
                'pool_has_support': complete(pool), 'pool_has_budget_feasible_support': feasible,
                'selected_has_support': complete(selected),
                'recall_against_nominal_abc': Fraction(len(selected & supports[0]), 3),
                'recall_against_union_abcde': Fraction(len(selected), 5)}
    rows = [
        observe('alternate_path_valid', universe, 'de', 3),
        observe('three_of_five_incomplete', universe, 'abd', 3),
        observe('nominal_path_valid', universe, 'abc', 3),
        observe('lost_nominal_path_but_alternative_survives', 'bcde', 'de', 3),
        observe('candidate_pool_missing_every_support', 'abd', 'abd', 3),
        observe('support_exposed_but_too_expensive', 'abc', 'ab', 2),
        observe('budget_feasible_but_selector_misses', universe, 'ab', 2),
    ]
    assert rows[0]['selected_has_support'] and rows[0]['recall_against_nominal_abc'] == 0
    assert not rows[1]['selected_has_support'] and rows[1]['recall_against_union_abcde'] == Fraction(3, 5)
    exhaustive = 0
    for pool in subsets(sorted(universe)):
        for budget in range(0, 6):
            feasible = any(t <= pool and len(t) <= budget for t in supports)
            for selected in subsets(sorted(pool), budget):
                assert not complete(selected) or feasible
                assert not feasible or complete(pool)
                exhaustive += 1
    # This authored perfect decoder returns success iff a complete support is selected.
    # Ratios below describe this selected finite casebook, not a causal decomposition.
    count = len(rows)
    pool_count = sum(r['pool_has_support'] for r in rows)
    feasible_count = sum(r['pool_has_budget_feasible_support'] for r in rows)
    selected_count = sum(r['selected_has_support'] for r in rows)
    product = Fraction(pool_count, count) * Fraction(feasible_count, pool_count) * Fraction(selected_count, feasible_count)
    assert product == Fraction(selected_count, count)
    return {'minimal_supports': supports, 'rows': rows,
            'exhaustive_pool_budget_slate_combinations_checked': exhaustive,
            'authored_casebook_factorization': {
                'pool_complete_rate': Fraction(pool_count, count),
                'budget_feasible_given_pool_complete': Fraction(feasible_count, pool_count),
                'selected_complete_given_budget_feasible': Fraction(selected_count, feasible_count),
                'perfect_decoder_success_rate': product,
                'warning': 'Exact descriptive identity on seven authored rows, not causal stage attribution.'}}


def compute():
    return {
        'format': 'ams-exact-complementarity-witness-v1',
        'authored_date': '2026-11-05',
        'evidence_class': 'Executed exact finite synthetic utility analysis',
        'model_calls': 0, 'provider_calls': 0, 'independent_empirical_task_count': 0,
        'cost_contract': 'One candidate = one slot. No token-budget result.',
        'low_order_interface_contract': 'Only set utility observations for |S| <= 2; all other visible features are identical across hidden-support worlds. Pairwise graph structure alone does not imply this contract.',
        'hidden_support_lower_bound': [hidden_support_study(n, b) for n, b in [(6,2),(6,3),(6,4),(8,3),(8,4)]],
        'decoy_complementarity': [decoy_study(Fraction(1, d)) for d in [20,10,4]],
        'additive_positive_control': positive_control(),
        'alternative_supports': alternative_supports(),
        'unexecuted': ['LLM reader study', 'learned ranker comparison', 'SG2RAG reproduction', 'OptiSet reproduction', 'InMind rejudging'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--write', action='store_true')
    group.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = json.loads(json.dumps(compute(), default=enc))
    path = ROOT / 'results.json'
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.write:
        path.write_text(serialized, encoding='utf-8')
        print('WROTE exact complementarity witnesses:', path)
    else:
        assert json.loads(path.read_text(encoding='utf-8')) == result, 'Saved results differ from exact computation'
        print('PASS: exact hidden-support bound; decoy policies; additive control; alternative-support and budget nesting. No model calls.')


if __name__ == '__main__':
    main()
