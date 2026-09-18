"""Checks the saved-evidence contract, without rerunning a model."""
import copy
import json
from pathlib import Path
import unittest
import study


class ReceiptContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads((Path(__file__).parent / 'results.json').read_text())

    def test_checked_receipt_is_complete_and_bound(self):
        self.assertEqual(study.verify_receipt(self.receipt)['rollouts'], 200)

    def test_omitted_pair_cannot_be_vacuous_success(self):
        bad = copy.deepcopy(self.receipt)
        bad['comparisons'] = []
        bad['summary'] = study.derive(bad['rows'], [])
        with self.assertRaises(AssertionError):
            study.verify_receipt(bad)

    def test_prompt_change_is_detected(self):
        bad = copy.deepcopy(self.receipt)
        bad['rows'][0]['query_text'] = 'Which answer do you prefer?'
        with self.assertRaises(AssertionError):
            study.verify_receipt(bad)

    def test_physical_index_cannot_masquerade_as_rope_position(self):
        bad = copy.deepcopy(self.receipt)
        row = next(r for r in bad['rows'] if r['treatment'] == 'trim')
        row['query_position_start'] = row['query_cache_position_start']
        with self.assertRaises(AssertionError):
            study.verify_receipt(bad)

    def test_answer_score_uses_every_token(self):
        bad = copy.deepcopy(self.receipt)
        first = next(iter(bad['rows'][0]['candidate_scores'].values()))
        first['sequence_log_probability'] += 0.5
        with self.assertRaises(AssertionError):
            study.verify_receipt(bad)

    def test_failed_negative_control_remains_failed(self):
        bad = copy.deepcopy(self.receipt)
        row = next(r for r in bad['rows'] if r['treatment'] == 'masked_trim')
        row['masked_vs_recompute']['max_abs_logit_delta'] = 0.1
        self.assertFalse(study.derive(bad['rows'], bad['comparisons'])['masked_controls_pass'])

    def test_directional_margin_is_bound_to_candidate_scores(self):
        bad = copy.deepcopy(self.receipt)
        bad['comparisons'][0]['exploratory_source_value_margin_contrast']['trim'] *= -1
        with self.assertRaises(AssertionError):
            study.verify_receipt(bad)

    def test_full_eligibility_cannot_be_promoted(self):
        bad = copy.deepcopy(self.receipt)
        comparison = next(c for c in bad['comparisons'] if not c['full_candidate_eligible_both'])
        comparison['full_candidate_eligible_both'] = True
        with self.assertRaises(AssertionError):
            study.verify_receipt(bad)


if __name__ == '__main__':
    unittest.main()
