#!/usr/bin/env python3
"""Exact-rational prefix invariance witnesses, not TGL or GATv2 inference."""
import argparse
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
POLICIES = ('drop-backward-only', 'zero-future-states', 'prefix-graph')


def graph(events):
    """Original toy topology: event/entity links, temporal links, and self loops."""
    nodes, edges = {}, []
    for position, event in enumerate(events):
        event_id = event['id']
        nodes[event_id] = {'born': position, 'signal': event['signal']}
        if position:
            previous = events[position - 1]['id']
            edges.extend([(previous, event_id, 'forward'), (event_id, previous, 'backward')])
        for entity in event['entities']:
            nodes.setdefault(entity, {'born': position, 'signal': '0'})
            edges.extend([(event_id, entity, 'has_entity'), (entity, event_id, 'belongs_to')])
    edges.extend((node, node, 'self') for node in nodes)
    return nodes, edges


def execute(events, prefix_length, policy, layers=3):
    """Synchronous mean aggregation with exact fractions, no trained weights.

    zero-future-states zeros future nodes at input AND after every layer. It
    intentionally leaves their incident edges in neighborhood denominators.
    All policies drop backward time edges; only prefix-graph removes the suffix
    before graph construction. Observation positions define availability.
    """
    if policy not in POLICIES:
        raise ValueError(policy)
    available = events[:prefix_length]
    nodes, edges = graph(available if policy == 'prefix-graph' else events)
    edges = [edge for edge in edges if edge[2] != 'backward']
    future = {node for node, data in nodes.items() if data['born'] >= prefix_length}
    masked = future if policy == 'zero-future-states' else set()
    incoming = {node: [] for node in nodes}
    for source, target, _ in edges:
        incoming[target].append(source)
    state = {node: Fraction(0) if node in masked else Fraction(data['signal'])
             for node, data in nodes.items()}
    trace = [state]
    for _ in range(layers):
        state = {
            node: Fraction(0) if node in masked else
            sum((state[source] for source in neighbors), Fraction(0)) / len(neighbors)
            for node, neighbors in incoming.items()
        }
        trace.append(state)
    current = available[-1]['id']
    known_entities = sorted({entity for event in available for entity in event['entities']})
    readout_ids = [current, *known_entities]
    return {
        'policy': policy, 'current_event': current,
        'nodes': nodes, 'edges': [list(edge) for edge in edges],
        'masked_nodes': sorted(masked),
        'layer_states': [{node: str(value) for node, value in layer.items()} for layer in trace],
        'readout': {node: str(state[node]) for node in readout_ids},
    }


def load_fixtures():
    return json.loads((ROOT / 'fixtures.json').read_text(encoding='utf-8'))


def report(fixture=None):
    fixture = load_fixtures() if fixture is None else fixture
    cases = []
    for case in fixture['cases']:
        prefix, layers = case['prefix'], fixture['layers']
        runs, comparisons = {}, {}
        for policy in POLICIES:
            runs[policy] = {'prefix': execute(prefix, len(prefix), policy, layers)}
            for name, suffix in case['suffix_variants'].items():
                runs[policy][name] = execute(prefix + suffix, len(prefix), policy, layers)
            baseline = runs[policy]['prefix']['readout']
            comparisons[policy] = {
                'zero_suffix_matches_prefix': runs[policy]['zero']['readout'] == baseline,
                'one_suffix_matches_prefix': runs[policy]['one']['readout'] == baseline,
                'changing_future_signal_preserves_readout': runs[policy]['zero']['readout'] == runs[policy]['one']['readout'],
            }
        changed = deepcopy(prefix)
        changed[0]['signal'] = '0'
        past_control = execute(changed, len(changed), 'prefix-graph', layers)
        cases.append({
            'id': case['id'], 'runs': runs, 'comparisons': comparisons,
            'past_change_control': past_control,
            'past_change_changes_readout': past_control['readout'] != runs['prefix-graph']['prefix']['readout'],
        })
    return {
        'study': 'proactive-prefix-study',
        'boundary': 'AMS exact-rational mean propagation on original synthetic graphs; not learned TGL, attention, trigger probability, or an official implementation audit.',
        'layers': fixture['layers'], 'propagation_runs': len(cases) * (len(POLICIES) * 3 + 1),
        'cases': cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='execute and compare with saved public results')
    args = parser.parse_args()
    result = report()
    if args.check:
        checked = json.loads((ROOT / 'results.json').read_text(encoding='utf-8'))
        if result != checked:
            raise SystemExit('FAIL: fresh topology, layer states or comparisons differ')
        print(f'PASS: {len(result["cases"])} graph scenarios, {result["propagation_runs"]} propagation runs match')
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
