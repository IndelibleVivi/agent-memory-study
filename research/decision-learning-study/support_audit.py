#!/usr/bin/env python3
"""Replay the unchanged AMS structured policy on its full Boolean domain."""
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys


def load_module(path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location('ams_original_decision', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def direct_label(x, version=1, hazard_first=False):
    scope = all(x[:3])
    hazard = not x[3] or not x[4] or x[6] or x[7]
    if hazard_first and hazard:
        return 'harmful'
    if not scope:
        return 'irrelevant'
    if hazard:
        return 'harmful'
    if x[5]:
        return 'redundant'
    if version == 2 and x[9] and not x[8]:
        return 'harmful'
    return 'useful'


def construct(x, idx, original):
    known = []
    if x[3]:
        known.append('precondition')
    if x[5]:
        known.append('target-fact')
    context = {'family': 'family-a', 'goal': 'goal-a', 'param': 'param-a',
               'known': known, 'tools': ['tool-a'] if x[4] else [],
               'sensitive': bool(x[9])}
    candidate = {'family': 'family-a' if x[0] else 'family-b',
                 'goal': 'goal-a' if x[1] else 'goal-b',
                 'param': 'param-a' if x[2] else 'param-b',
                 'requires': ['precondition'], 'fact': 'target-fact',
                 'tool': 'tool-a', 'expired': bool(x[6]),
                 'side_effect': bool(x[7]), 'verified': bool(x[8])}
    row = {'id': f'boolean-{idx:04d}', 'event': f'boolean-{idx:04d}',
           'group': 'exhaustive-boolean', 'context': context,
           'candidate': candidate, 'index': 0,
           'expected': original.label(context, candidate)}
    assert original.vector(row) == list(x), ('roundtrip', x)
    for version in (1, 2):
        assert original.label(context, candidate, version) == direct_label(x, version)
    return row


def counts(rows, labels, prediction, indices):
    ys = [labels[i] for i in indices]
    ps = [prediction[i] for i in indices]
    return {'n': len(indices),
            'class_correct': sum(y == p for y, p in zip(ys, ps)),
            'selection_correct': sum((y == 'useful') == (p == 'useful') for y, p in zip(ys, ps)),
            'useful_cases': ys.count('useful'),
            'useful_missed': sum(y == 'useful' and p != 'useful' for y, p in zip(ys, ps)),
            'harmful_selected': sum(y == 'harmful' and p == 'useful' for y, p in zip(ys, ps)),
            'other_unnecessary_selected': sum(y in ('irrelevant', 'redundant') and p == 'useful' for y, p in zip(ys, ps))}


def report(repo):
    directory = repo / 'research/decision-learning-study'
    original = load_module(directory / 'study.py')
    fixture = json.loads((directory / 'fixtures.json').read_text())
    saved = json.loads((directory / 'results.json').read_text())
    train = original.rows_for(fixture, 'train')
    test = original.rows_for(fixture, 'test')
    source_vectors = {tuple(original.vector(r)) for r in train}
    baseline = original.all_predictions(train, test, saved['models']['original'], saved['models']['rules'])
    assert baseline == saved['before']['predictions'], 'saved baseline replay mismatch'

    vectors = list(itertools.product((0, 1), repeat=10))
    rows = [construct(x, i, original) for i, x in enumerate(vectors)]
    original_labels = [r['expected'] for r in rows]
    corrected_labels = [direct_label(x, 2) for x in vectors]
    alternate_labels = [direct_label(x, hazard_first=True) for x in vectors]
    predictions = original.all_predictions(train, rows, saved['models']['original'], saved['models']['rules'])
    nuisance_free = original.fit(train, active=list(range(8)))
    train_vectors = [original.vector(r)[:8] for r in train]
    nuisance_predictions = {
        'scorer_without_v1_nuisance': original.scorer(nuisance_free, rows),
        'episodic_without_v1_nuisance': [train[min(range(len(train)), key=lambda j:
            sum(a != b for a, b in zip(train_vectors[j], x[:8])))]['expected'] for x in vectors]}
    reversed_train = list(reversed(train))
    reversed_vectors = [original.vector(r)[:8] for r in reversed_train]
    nuisance_predictions['episodic_without_v1_nuisance_reversed'] = [
        reversed_train[min(range(len(reversed_train)), key=lambda j:
            sum(a != b for a, b in zip(reversed_vectors[j], x[:8])))]['expected'] for x in vectors]
    corrected_predictions = {
        'frozen': predictions['scorer'],
        'refit': original.scorer(saved['models']['refit'], rows),
        'incremental': original.scorer(saved['models']['incremental'], rows),
        'guard': [('harmful' if p == 'useful' and original.in_scope(r['context'], r['candidate']) else p)
                  for p, r in zip(predictions['scorer'], rows)]}
    seen = [i for i, x in enumerate(vectors) if x in source_vectors]
    unseen = [i for i, x in enumerate(vectors) if x not in source_vectors]
    conflict = [i for i, (a, b) in enumerate(zip(original_labels, alternate_labels)) if a != b]
    groups = {'all': list(range(len(rows))), 'seen': seen, 'unseen': unseen,
              'scope_and_hazard_conflict': conflict,
              'in_scope': [i for i, x in enumerate(vectors) if all(x[:3])],
              'out_of_scope': [i for i, x in enumerate(vectors) if not all(x[:3])]}
    hypothesis_agreement = {}
    for split in ('train', 'validation', 'test'):
        split_rows = original.rows_for(fixture, split)
        hypothesis_agreement[split] = {
            'n': len(split_rows),
            'agree': sum(r['expected'] == direct_label(original.vector(r), hazard_first=True) for r in split_rows)}
    witnesses = []
    for x in [(0, 1, 1, 1, 1, 0, 1, 0, 0, 0),
              (1, 1, 1, 1, 1, 0, 0, 0, 1, 1),
              (1, 1, 1, 1, 1, 0, 1, 0, 0, 0),
              (1, 1, 1, 1, 1, 0, 1, 0, 1, 0),
              (0, 0, 0, 0, 0, 1, 1, 1, 0, 1)]:
        i = vectors.index(x)
        witnesses.append({'vector': list(x), 'seen': i in seen,
                          'scope_first': original_labels[i],
                          'hazard_first': alternate_labels[i],
                          'predictions': {k: v[i] for k, v in predictions.items()}})
    index_by_vector = {x: i for i, x in enumerate(vectors)}
    invariant_flips = {}
    for feature in (8, 9):
        pairs = []
        for i, x in enumerate(vectors):
            if x[feature]:
                continue
            y = list(x)
            y[feature] = 1
            j = index_by_vector[tuple(y)]
            assert original_labels[i] == original_labels[j]
            pairs.append((i, j))
        invariant_flips[original.FEATURES[feature]] = {
            'pairs': len(pairs), 'oracle_label_changes': 0,
            'methods': {m: {'class_changes': sum(p[i] != p[j] for i, j in pairs),
                            'selection_changes': sum((p[i] == 'useful') != (p[j] == 'useful') for i, j in pairs)}
                        for m, p in {**predictions, **nuisance_predictions}.items()}}
    return {'schema': 'ams-structured-support-audit/1',
            'baseline_commit': '196880924ae501dd8103bdcb4c03e5c27c7df8ed',
            'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'evidence_kind': 'exhaustive synthetic Boolean-domain probe with saved-model replay',
            'source_sha256': {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [directory / n for n in ('fixture_build.py', 'study.py', 'fixtures.json', 'results.json')]},
            'features': list(original.FEATURES),
            'support': {'unique_train_vectors': len(source_vectors),
                        'total_constructible_vectors': len(vectors),
                        'seen': len(seen), 'unseen': len(unseen),
                        'useful_v1_total': original_labels.count('useful'),
                        'useful_v1_unseen': sum(original_labels[i] == 'useful' for i in unseen),
                        'useful_v2_total': corrected_labels.count('useful'),
                        'useful_v2_unseen': sum(corrected_labels[i] == 'useful' for i in unseen)},
            'v1_metrics': {m: {g: counts(rows, original_labels, p, ids) for g, ids in groups.items()}
                           for m, p in predictions.items()},
            'v2_metrics': {m: {g: counts(rows, corrected_labels, p, ids) for g, ids in groups.items()}
                           for m, p in corrected_predictions.items()},
            'post_observation_nuisance_control': {
                'note': 'Designer-known v1 nuisance features omitted; no claim of automatic feature discovery or v2 suitability.',
                'model': original.rounded(nuisance_free),
                'metrics': {m: {g: counts(rows, original_labels, p, ids) for g, ids in groups.items()}
                            for m, p in nuisance_predictions.items()},
                'invariance_flips': invariant_flips},
            'competing_priorities': {'original_split_agreement': hypothesis_agreement,
                                     'enumerated_label_disagreement': len(conflict),
                                     'enumerated_selection_disagreement': sum((a == 'useful') != (b == 'useful')
                                                                              for a, b in zip(original_labels, alternate_labels)),
                                     'eight_feature_original_order_matches_scope_first': sum(
                                         p == y for p, y in zip(nuisance_predictions['episodic_without_v1_nuisance'], original_labels)),
                                     'eight_feature_reverse_order_matches_hazard_first': sum(
                                         p == y for p, y in zip(nuisance_predictions['episodic_without_v1_nuisance_reversed'], alternate_labels))},
            'witnesses': witnesses,
            'cases': [{'vector': list(x), 'seen': x in source_vectors,
                       'label_v1': original_labels[i], 'label_v2': corrected_labels[i],
                       'label_hazard_first': alternate_labels[i],
                       'predictions_v1': {m: p[i] for m, p in predictions.items()},
                       'nuisance_control_v1': {m: p[i] for m, p in nuisance_predictions.items()},
                       'predictions_v2': {m: p[i] for m, p in corrected_predictions.items()}}
                      for i, x in enumerate(vectors)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('support-results.json'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = report(args.repo.resolve())
    if args.check:
        assert json.loads(args.output.read_text()) == result, 'deterministic receipt mismatch'
        print('PASS: full Boolean support, saved predictions, rule priorities and source bindings recomputed')
    else:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k not in ('cases', 'source_sha256')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
