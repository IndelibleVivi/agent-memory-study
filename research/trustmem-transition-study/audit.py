#!/usr/bin/env python3
"""Original, finite transition witnesses inspired by TRUSTMEM, not its verifier."""
import argparse
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def execute(pre, actions):
    """An atomic exact-key toy executor; no NLP, retrieval, or authority inference."""
    post = deepcopy(pre)
    for action in actions:
        op, key = action['op'], action['key']
        if op == 'write' and key not in post:
            post[key] = action['value']
        elif op == 'revise' and key in post:
            post[key] = action['value']
        elif op == 'prune' and key in post:
            del post[key]
        else:
            return deepcopy(pre), False
    return post, True


def evaluate(case):
    """Score explicit obligations, not natural-language factual reliability.

    A chunk supplies new facts and explicit retractions. Every surviving prior
    fact is designated important. Coverage is not a substring/copying test.
    """
    pre, chunk = case['prompt']['pre'], case['prompt']['chunk']
    post, executable = execute(pre, case['actions'])
    withdrawn = set(chunk['withdraw'])
    valid_prior = {k: v for k, v in pre.items()
                   if k not in withdrawn and k not in chunk['facts']}
    supported = valid_prior | chunk['facts']
    missing_new = [k for k, v in chunk['facts'].items() if post.get(k) != v]
    lost_prior = [k for k, v in valid_prior.items() if post.get(k) != v]
    unsupported = [k for k, v in post.items() if k not in supported or supported[k] != v]
    diagnostics = {
        'coverage_ok': not missing_new,
        'preservation_ok': not lost_prior,
        'faithfulness_ok': not unsupported,
    }
    score = Fraction(sum(diagnostics.values()), 3) if executable else Fraction(0)
    return {
        'id': case['id'], 'post': post, 'executable': executable,
        **diagnostics, 'missing_new': missing_new, 'lost_prior': lost_prior,
        'unsupported': unsupported, 'score': str(score),
    }


def pair(candidates, margin=Fraction(15, 100), require_same_prompt=True):
    """Top/bottom pair for one proposed group; reject a mismatched group.

    The unguarded mode is an intentionally invalid comparison control.
    A real trainer should group/resample by all actual conditioning inputs;
    equality here covers only the explicitly declared toy prompt.
    """
    if len(candidates) < 2:
        return {'status': 'insufficient-candidates'}
    if require_same_prompt and any(c['prompt'] != candidates[0]['prompt'] for c in candidates[1:]):
        return {'status': 'incomparable-prompt'}
    ordered = sorted(candidates, key=lambda c: Fraction(evaluate(c)['score']))
    low, high = ordered[0], ordered[-1]
    gap = Fraction(evaluate(high)['score']) - Fraction(evaluate(low)['score'])
    if gap <= margin:
        return {'status': 'insufficient-gap', 'gap': str(gap)}
    return {
        'status': 'paired', 'preferred': high['id'], 'rejected': low['id'],
        'gap': str(gap), 'same_prompt': high['prompt'] == low['prompt'],
        'same_actions': high['actions'] == low['actions'],
    }


def load_cases():
    return json.loads((ROOT / 'fixtures.json').read_text(encoding='utf-8'))['cases']


def report():
    cases = load_cases()
    by_id = {c['id']: c for c in cases}
    groups = {
        'different-prior-same-noop': ['already-stored', 'missing-noop'],
        'shared-prior-write-vs-noop': ['write-new', 'missing-noop'],
        'shared-prior-correction-vs-omission': ['legitimate-correction', 'drops-valid-condition'],
        'shared-prior-tie': ['legitimate-correction', 'equivalent-correction'],
    }
    pairing = {}
    for name, ids in groups.items():
        group = [by_id[i] for i in ids]
        pairing[name] = {
            'candidate_ids': ids,
            'chunk_only_control': pair(group, require_same_prompt=False),
            'same_prompt': pair(group),
        }
    numbers = json.loads((ROOT / 'paper-values.json').read_text(encoding='utf-8'))
    arithmetic = {}
    for key, values in numbers['headline_differences'].items():
        arithmetic[key] = str(Fraction(values['trustmem']) - Fraction(values['comparator']))
    reductions = {}
    for key, values in numbers['figure_2'].items():
        baseline, current = Fraction(values['baseline']), Fraction(values['trustmem'])
        reductions[key] = {'relative_reduction_percent': round(float((baseline-current)/baseline*100), 3),
                           'absolute_percentage_point_drop': str(baseline-current)}
    return {
        'study': 'trustmem-transition-study',
        'boundary': 'Original deterministic fixtures and arithmetic on rounded paper values; no official code, LLM judge, training, or benchmark reproduction.',
        'transitions': [evaluate(c) for c in cases], 'pairing': pairing,
        'paper_arithmetic': {'headline_differences': arithmetic, 'figure_2': reductions},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='compare with the checked public result')
    args = parser.parse_args()
    result = report()
    if args.check:
        checked = json.loads((ROOT / 'results.json').read_text(encoding='utf-8'))
        if checked != result:
            raise SystemExit('FAIL: checked result differs from fresh execution')
        print(f"PASS: {len(result['transitions'])} transitions and {len(result['pairing'])} pairing groups match checked results")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
