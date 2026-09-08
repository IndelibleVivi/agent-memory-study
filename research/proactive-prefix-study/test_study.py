from copy import deepcopy
from fractions import Fraction
import unittest

import study


class PrefixStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = study.load_fixtures()
        cls.result = {case['id']: case for case in study.report(cls.fixture)['cases']}

    def test_future_reaches_current_through_shared_file_without_backward_edges(self):
        runs = self.result['shared-file']['runs']['drop-backward-only']
        for run in runs.values():
            self.assertFalse(any(edge[2] == 'backward' for edge in run['edges']))
        self.assertEqual(runs['zero']['layer_states'][1]['event:2'], runs['one']['layer_states'][1]['event:2'])
        self.assertNotEqual(runs['zero']['layer_states'][2]['event:2'], runs['one']['layer_states'][2]['event:2'])

    def test_future_reaches_current_through_type_without_sharing_file(self):
        case = self.result['shared-type']
        self.assertFalse(case['comparisons']['drop-backward-only']['changing_future_signal_preserves_readout'])
        edges = case['runs']['drop-backward-only']['one']['edges']
        self.assertIn(['event:3', 'type:writing', 'has_entity'], edges)
        self.assertNotIn(['event:3', 'file:reading.md', 'has_entity'], edges)

    def test_zeroing_every_future_state_still_changes_neighborhood_mean(self):
        case = self.result['shared-file']
        masked = case['runs']['zero-future-states']['one']
        for layer in masked['layer_states']:
            for node in masked['masked_nodes']:
                self.assertEqual(layer[node], '0')
        baseline = case['runs']['zero-future-states']['prefix']
        self.assertEqual(baseline['layer_states'][1]['file:reading.md'], '1/3')
        self.assertEqual(masked['layer_states'][1]['file:reading.md'], '1/4')
        self.assertFalse(case['comparisons']['zero-future-states']['zero_suffix_matches_prefix'])
        self.assertTrue(case['comparisons']['zero-future-states']['changing_future_signal_preserves_readout'])

    def test_disconnected_suffix_is_negative_control_for_past_readouts(self):
        for comparison in self.result['unrelated-future']['comparisons'].values():
            self.assertTrue(all(comparison.values()))

    def test_prefix_rebuild_preserves_all_known_readouts(self):
        for case in self.result.values():
            self.assertTrue(all(case['comparisons']['prefix-graph'].values()))
            for run in case['runs']['prefix-graph'].values():
                self.assertNotIn('event:3', run['nodes'])
                self.assertNotIn('file:tomorrow.md', run['nodes'])

    def test_valid_past_signal_changes_outputs(self):
        for case in self.result.values():
            self.assertTrue(case['past_change_changes_readout'])

    def test_each_layer_is_synchronous_and_bounded(self):
        for case in self.result.values():
            for runs in case['runs'].values():
                for run in runs.values():
                    for layer in run['layer_states']:
                        self.assertTrue(all(0 <= Fraction(value) <= 1 for value in layer.values()))
        states = self.result['shared-file']['runs']['prefix-graph']['prefix']['layer_states']
        self.assertEqual(states[1]['event:1'], '1/2')
        self.assertEqual(states[1]['event:2'], '1/3')
        self.assertEqual(states[2]['event:2'], '7/18')

    def test_input_fixtures_are_not_rewritten(self):
        original = deepcopy(self.fixture)
        study.report(self.fixture)
        self.assertEqual(self.fixture, original)


if __name__ == '__main__':
    unittest.main()
