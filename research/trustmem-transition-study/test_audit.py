from copy import deepcopy
from fractions import Fraction
import unittest

from audit import evaluate, execute, load_cases, pair, report


class TransitionStudyTests(unittest.TestCase):
    def setUp(self):
        self.cases = {c['id']: c for c in load_cases()}

    def test_explicit_correction_is_not_loss_of_valid_prior(self):
        good = evaluate(self.cases['legitimate-correction'])
        bad = evaluate(self.cases['drops-valid-condition'])
        self.assertEqual(good['score'], '1')
        self.assertTrue(good['preservation_ok'])
        self.assertEqual(bad['lost_prior'], ['timezone'])
        self.assertTrue(bad['coverage_ok'])
        self.assertFalse(bad['preservation_ok'])

    def test_unsupported_addition_and_retraction(self):
        self.assertEqual(evaluate(self.cases['unsupported-addition'])['unsupported'], ['room'])
        self.assertEqual(evaluate(self.cases['legitimate-prune'])['score'], '1')
        self.assertFalse(evaluate(self.cases['keeps-retracted'])['faithfulness_ok'])

    def test_noop_depends_on_prior_state_and_wrong_group_is_degenerate(self):
        group = [self.cases['already-stored'], self.cases['missing-noop']]
        self.assertEqual(evaluate(group[0])['score'], '1')
        self.assertEqual(evaluate(group[1])['score'], '2/3')
        bad = pair(group, require_same_prompt=False)
        self.assertEqual(bad['status'], 'paired')
        self.assertTrue(bad['same_actions'])
        self.assertFalse(bad['same_prompt'])
        self.assertEqual(pair(group)['status'], 'incomparable-prompt')

    def test_shared_state_control_produces_a_real_action_comparison(self):
        group = [self.cases['write-new'], self.cases['missing-noop']]
        result = pair(group)
        self.assertEqual(result['preferred'], 'write-new')
        self.assertFalse(result['same_actions'])
        self.assertTrue(result['same_prompt'])
        self.assertEqual(pair(list(reversed(group))), result)

    def test_equal_scores_and_strict_margin_do_not_form_pairs(self):
        self.assertEqual(pair([self.cases['legitimate-correction'], self.cases['equivalent-correction']])['status'], 'insufficient-gap')
        group = [self.cases['write-new'], self.cases['missing-noop']]
        self.assertEqual(pair(group, margin=Fraction(1, 3))['status'], 'insufficient-gap')
        self.assertEqual(pair(group, margin=Fraction(1, 3)-Fraction(1, 1000))['status'], 'paired')

    def test_chunk_or_contract_changes_are_not_a_shared_prompt(self):
        for field, value in [('chunk', {'facts': {'deadline': 'Monday'}, 'withdraw': []}),
                             ('contract', 'different-executor')]:
            a, b = deepcopy(self.cases['write-new']), deepcopy(self.cases['missing-noop'])
            b['prompt'][field] = value
            self.assertEqual(pair([a, b])['status'], 'incomparable-prompt')

    def test_invalid_action_is_atomic_and_does_not_change_fixture(self):
        case = self.cases['invalid-revise']
        before = deepcopy(case)
        result = evaluate(case)
        self.assertFalse(result['executable'])
        self.assertEqual(result['post'], case['prompt']['pre'])
        self.assertEqual(result['score'], '0')
        self.assertEqual(case, before)
        self.assertEqual(execute({}, [{'op': 'write', 'key': 'x', 'value': '1'},
                                      {'op': 'revise', 'key': 'missing', 'value': '2'}]), ({}, False))

    def test_paper_arithmetic_keeps_relative_and_absolute_separate(self):
        result = report()['paper_arithmetic']
        self.assertEqual(Fraction(result['headline_differences']['halumem_extraction_f1']), Fraction('12.14'))
        self.assertEqual(result['figure_2']['hallucination']['relative_reduction_percent'], 50)
        self.assertEqual(Fraction(result['figure_2']['hallucination']['absolute_percentage_point_drop']), Fraction('0.01'))


if __name__ == '__main__':
    unittest.main()
