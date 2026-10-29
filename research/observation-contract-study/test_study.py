"""Discriminatory finite-contract checks; no provider or browser."""
import copy
from fractions import Fraction
import importlib.util
from itertools import combinations, product
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('observation_study', ROOT / 'study.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
MODELS = {m['id']: m for m in json.loads((ROOT / 'fixtures.json').read_text())['models']}


class ContractTests(unittest.TestCase):
    def plant(self, name):
        return copy.deepcopy(MODELS[name]['plant'])

    def test_fixture_validity(self):
        for m in MODELS.values():
            s.validate_model(m)

    def test_future_collision_is_not_a_sequence(self):
        r = s.analyze(MODELS['future-denied-permitted'])
        self.assertEqual(r['observation_class_count'], 2)
        self.assertTrue(all(c['questions']['current']['compatible'] for c in r['classes']))
        self.assertTrue(all(not c['questions']['future']['compatible'] for c in r['classes']))
        self.assertEqual(s.search_pair(self.plant('future-denied-permitted'), 'w00', 'w01')['status'],
                         'indistinguishable-in-declared-model')

    def test_five_access_gates_individually_deny(self):
        for gate in s.GATES:
            p = self.plant('future-denied-' + gate)
            self.assertEqual(s.search_pair(p, 'w00', 'w01')['word'], None)
            with self.assertRaisesRegex(ValueError, 'inaccessible'):
                s.trace_word(p, 'w00', 'w01', ['revisit'])

    def test_revisit_visible_version_target(self):
        r = s.search_pair(self.plant('future-access'), 'w00', 'w01')
        self.assertEqual(r['word'], ['revisit'])
        self.assertEqual(r['trace'][1]['left'], {'source_version': 'v1', 'target': 'y', 'y': 0})
        self.assertEqual(r['trace'][1]['right']['y'], 1)

    def test_side_information_refines_compatibility(self):
        plain = s.analyze(MODELS['future-denied-permitted'])
        side = s.analyze(MODELS['future-side-information'])
        self.assertEqual(len(plain['classes']), 2)
        self.assertEqual(len(side['classes']), 4)
        for c in side['classes']:
            self.assertTrue(c['questions']['future']['compatible'])
        self.assertEqual(s.search_pair(self.plant('future-side-information'), 'w00', 'w01')['steps'], 0)

    def test_three_sets_need_global_check(self):
        m = MODELS['nonpairwise-control']
        a = m['evaluator']['answers']['route']
        self.assertTrue(all(s.compatibility(list(pair), a)['compatible'] for pair in combinations(a, 2)))
        r = s.compatibility(list(a), a)
        self.assertFalse(r['compatible'])
        self.assertEqual(r['minimal_conflict'], ['a', 'b', 'c'])

    def test_delayed_writeback_witness_and_bound(self):
        p = self.plant('writeback-active')
        self.assertEqual(s.search_pair(p, 'live', 'cached')['word'], ['withdraw', 'read'])
        r = s.search_pair(p, 'live', 'cached', max_steps=1)
        self.assertEqual(r['status'], 'not-distinguished-within-bound')
        self.assertEqual(r['bounds']['max_steps'], 1)

    def test_forbidden_and_true_equivalence(self):
        for name, pair in [('writeback-forbidden', ('live', 'cached')),
                           ('equivalent-control', ('a', 'b'))]:
            r = s.search_pair(self.plant(name), *pair)
            self.assertEqual(r['certificate'], 'reachable-product-closure')
            self.assertEqual(r['status'], 'indistinguishable-in-declared-model')

    def test_weighted_minimum_not_first_generated_edge(self):
        p = self.plant('score-weighted')
        r = s.search_pair(p, 'revision', 'scope')
        self.assertEqual((r['word'], r['cost']), (['prepare', 'inspect'], '1'))
        bounded = s.search_pair(p, 'revision', 'scope', max_steps=1)
        self.assertEqual((bounded['word'], bounded['cost']), (['expensive-probe'], '3'))
        self.assertEqual(bounded['scope'], 'minimum-within-declared-bounds')

    def test_uniform_cost_minimizes_steps(self):
        r = s.search_pair(self.plant('score-unit-cost'), 'revision', 'scope')
        self.assertEqual((r['word'], r['cost'], r['steps']), (['expensive-probe'], '1', 1))

    def test_zero_cycle_terminates_and_cost_bound(self):
        p = self.plant('score-weighted')
        r = s.search_pair(p, 'revision', 'scope', max_cost='1/2')
        self.assertEqual(r['status'], 'not-distinguished-within-bound')
        self.assertLessEqual(len(r['expanded']), 4)
        self.assertEqual(s.search_pair(p, 'revision', 'scope', max_cost=1)['cost'], '1')

    def test_negative_float_random_and_nontotal_rejected(self):
        for value in [-1, '-1/2', 0.5, True, '1/0']:
            with self.assertRaises(ValueError):
                s.cost(value)
        m = copy.deepcopy(MODELS['writeback-active'])
        m['plant']['states']['live']['transitions'].pop('read')
        with self.assertRaisesRegex(ValueError, 'total'):
            s.validate_model(m)
        m = copy.deepcopy(MODELS['writeback-active'])
        m['plant']['states']['live']['transitions']['read']['probability'] = 0.5
        with self.assertRaises(ValueError):
            s.validate_model(m)

    def test_evaluator_isolation(self):
        m = copy.deepcopy(MODELS['score-weighted'])
        before = s.search_pair(m['plant'], 'revision', 'scope')
        m['evaluator']['targets'] = {k: 'unrelated' for k in m['evaluator']['targets']}
        for answers in m['evaluator']['answers'].values():
            for k in answers:
                answers[k] = ['different-gold']
        self.assertEqual(before, s.search_pair(m['plant'], 'revision', 'scope'))
        self.assertFalse(any(c['target_collisions'] for c in s.analyze(m)['classes']))

    def test_renaming_handles_and_order_do_not_create_signal(self):
        p = self.plant('score-weighted')
        before = s.search_pair(p, 'revision', 'scope')
        mapping = {k: 'opaque-' + str(i) for i, k in enumerate(reversed(p['states']))}
        p['states'] = {mapping[k]: v for k, v in reversed(list(p['states'].items()))}
        for st in p['states'].values():
            for t in st['transitions'].values():
                t['next'] = mapping[t['next']]
        p['actions'] = dict(reversed(list(p['actions'].items())))
        after = s.search_pair(p, mapping['revision'], mapping['scope'])
        for key in ['word', 'cost', 'steps', 'trace', 'status']:
            self.assertEqual(before[key], after[key])

    def test_action_deletion_and_observation_mutation(self):
        p = self.plant('writeback-active')
        for state in p['states'].values():
            state['transitions'].pop('withdraw')
        p['actions'].pop('withdraw')
        self.assertIsNone(s.search_pair(p, 'live', 'cached')['word'])
        p['states']['live']['observation']['new-visible-flag'] = True
        self.assertEqual(s.search_pair(p, 'live', 'cached')['word'], [])

    def test_task_extension_not_change_plant(self):
        m = copy.deepcopy(MODELS['future-denied-permitted'])
        before = s.search_pair(m['plant'], 'w00', 'w01')
        m['evaluator']['answers']['harder'] = {k: [k] for k in m['plant']['states']}
        m['evaluator']['question_descriptions']['harder'] = '精确世界'
        after = s.analyze(m)
        self.assertEqual(before, s.search_pair(m['plant'], 'w00', 'w01'))
        self.assertTrue(all(not c['questions']['harder']['compatible'] for c in after['classes']))

    def test_more_actions_never_worsen_unbounded_minimum(self):
        p = self.plant('score-weighted')
        original = s.search_pair(p, 'revision', 'scope')
        p['actions']['inspect']['gates'] = {'permitted': False}
        restricted = s.search_pair(p, 'revision', 'scope')
        self.assertLessEqual(s.cost(original['cost']), s.cost(restricted['cost']))

    def test_step_bound_keeps_costlier_shorter_prefix(self):
        # Cheap long route to m must not suppress costly short route at step bound.
        states = {}
        actions = {'cheap': {'cost': 0, 'gates': {}, 'meaning': 'cheap'},
                   'short': {'cost': 2, 'gates': {}, 'meaning': 'short'},
                   'probe': {'cost': 0, 'gates': {}, 'meaning': 'probe'}}
        for arm in ['L', 'R']:
            for phase in ['s', 'p', 'm']:
                k = arm + phase
                nxt = 'p' if phase == 's' else 'm'
                states[k] = {'observation': 0, 'side_information': {}, 'transitions': {
                    'cheap': {'next': arm + nxt, 'output': 0},
                    'short': {'next': arm + 'm', 'output': 0},
                    'probe': {'next': k, 'output': arm if phase == 'm' else 0}}}
        p = {'states': states, 'actions': actions, 'side_information_description': ''}
        r = s.search_pair(p, 'Ls', 'Rs', max_steps=2)
        self.assertEqual((r['word'], r['cost']), (['short', 'probe'], '2'))
        self.assertEqual(s.search_pair(p, 'Ls', 'Rs')['cost'], '0')

    def test_exhaustive_independent_two_state_systems(self):
        # All 256 assignments of next-state/output bits for two states × two actions.
        for bits in product((0, 1), repeat=8):
            states = {}
            for i in range(2):
                transitions = {}
                for j, action in enumerate(['a', 'b']):
                    at = 4 * i + 2 * j
                    transitions[action] = {'next': str(bits[at]), 'output': bits[at + 1]}
                states[str(i)] = {'observation': 0, 'side_information': {}, 'transitions': transitions}
            p = {'states': states, 'actions': {'a': {'cost': 0, 'gates': {}, 'meaning': ''},
                 'b': {'cost': '1/2', 'gates': {}, 'meaning': ''}}, 'side_information_description': ''}
            fast = s.search_pair(p, '0', '1', max_steps=4)
            slow = s.naive_pair(p, '0', '1', 4)
            actual = None if fast['word'] is None else (s.cost(fast['cost']), fast['steps'], tuple(fast['word']))
            self.assertEqual(actual, slow)

    def test_adapter_matches_native_and_rejects_extra_fields(self):
        spec = importlib.util.spec_from_file_location('observation_adapter', ROOT / 'adapter.py')
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        plan = {'operation': 'search-pair', 'model': 'score-weighted', 'left': 'revision', 'right': 'scope'}
        self.assertEqual(adapter.execute(plan)['result'], s.search_pair(self.plant('score-weighted'), 'revision', 'scope'))
        with self.assertRaises(ValueError):
            adapter.execute({**plan, 'gold': 'secret'})
        self.assertFalse(adapter.describe_capabilities()['provider'])
        self.assertEqual(adapter.describe_capabilities()['operations'], ['analyze-model', 'search-pair'])
        with self.assertRaises(ValueError):
            adapter.validate_plan({'operation': 'check-saved-results'})

    def test_invalid_bounds(self):
        p = self.plant('equivalent-control')
        for n in [-1, True, 1.5]:
            with self.assertRaises(ValueError):
                s.search_pair(p, 'a', 'b', max_steps=n)


if __name__ == '__main__':
    unittest.main()
