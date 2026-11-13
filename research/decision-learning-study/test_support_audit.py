"""Behavioral tests for finite-domain and confounding claims, no model calls."""
import os
from pathlib import Path
import unittest

import support_audit


class SupportAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(os.environ.get('AMS_REPO_PATH', Path(__file__).resolve().parents[2]))
        cls.result = support_audit.report(repo)
        cls.cases = {tuple(c['vector']): c for c in cls.result['cases']}

    def test_enumeration_covers_unseen_negatives_but_no_unseen_positives(self):
        self.assertEqual(len(self.cases), 1024)
        self.assertEqual(self.result['support']['unique_train_vectors'], 36)
        self.assertEqual(self.result['support']['unseen'], 988)
        self.assertEqual(self.result['support']['useful_v1_unseen'], 0)
        self.assertEqual(self.result['support']['useful_v2_unseen'], 0)

    def test_verification_can_reverse_selection_without_resolving_expiry(self):
        unverified = self.cases[(1, 1, 1, 1, 1, 0, 1, 0, 0, 0)]
        verified = self.cases[(1, 1, 1, 1, 1, 0, 1, 0, 1, 0)]
        self.assertEqual(unverified['label_v1'], 'harmful')
        self.assertEqual(verified['label_v1'], 'harmful')
        self.assertEqual(unverified['predictions_v1']['scorer'], 'harmful')
        self.assertEqual(verified['predictions_v1']['scorer'], 'useful')
        self.assertNotEqual(verified['nuisance_control_v1']['scorer_without_v1_nuisance'], 'useful')

    def test_original_scores_cannot_identify_label_priority(self):
        p = self.result['competing_priorities']
        for split in p['original_split_agreement'].values():
            self.assertEqual(split['agree'], split['n'])
        self.assertEqual(p['enumerated_label_disagreement'], 7 * 15 * 2 ** 3)
        self.assertEqual(p['enumerated_selection_disagreement'], 0)

    def test_case_order_supplies_unidentified_priority(self):
        p = self.result['competing_priorities']
        self.assertEqual(p['eight_feature_original_order_matches_scope_first'], 1024)
        self.assertEqual(p['eight_feature_reverse_order_matches_hazard_first'], 1024)
        m = self.result['post_observation_nuisance_control']['metrics']
        self.assertEqual(m['episodic_without_v1_nuisance']['all']['selection_correct'], 1024)
        self.assertEqual(m['episodic_without_v1_nuisance_reversed']['all']['selection_correct'], 1024)


if __name__ == '__main__':
    unittest.main()
