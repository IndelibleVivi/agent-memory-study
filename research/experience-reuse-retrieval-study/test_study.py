import copy
import unittest

import study


class RetrievalStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = study.load_fixtures()
        cls.result = study.report(cls.fixture)

    def observation(self, name, added, policy, budget=3):
        case = next(c for c in self.result['cases'] if c['id'] == name)
        stage = next(s for s in case['stages'] if s['added'] == added)
        return next(o for o in stage['observations']
                    if o['policy'] == policy and o['budget_entries'] == budget)

    def test_duplicate_growth_excludes_retained_target(self):
        self.assertTrue(self.observation('exact-duplicates', 0, 'top-k')['hit'])
        self.assertFalse(self.observation('exact-duplicates', 2, 'top-k')['hit'])
        self.assertTrue(self.observation('exact-duplicates', 2, 'top-k', 5)['hit'])
        self.assertFalse(self.observation('exact-duplicates', 4, 'top-k', 5)['hit'])
        for policy in ('unique-key', 'unique-key-value'):
            self.assertTrue(self.observation('exact-duplicates', 4, policy)['hit'])

    def test_same_size_unrelated_growth_is_not_crowding(self):
        for added in self.fixture['growth']:
            self.assertTrue(self.observation('unrelated-growth', added, 'top-k')['hit'])

    def test_key_collapse_loses_distinct_useful_value(self):
        self.assertTrue(self.observation('different-values-same-key', 0, 'top-k')['hit'])
        self.assertFalse(self.observation('different-values-same-key', 0, 'unique-key')['hit'])
        self.assertTrue(self.observation('different-values-same-key', 4, 'unique-key-value')['hit'])

    def test_exact_dedup_does_not_solve_paraphrase_competition(self):
        self.assertFalse(self.observation('same-key-paraphrases', 2, 'unique-key-value')['hit'])
        self.assertTrue(self.observation('same-key-paraphrases', 2, 'unique-key')['hit'])

    def test_no_store_loss_or_old_rank_reversal_in_these_fixtures(self):
        for case in self.result['cases']:
            for stage in case['stages']:
                self.assertEqual(stage['old_items_retained'], stage['old_item_count'])
                self.assertTrue(stage['old_matching_order_preserved'])
                for o in stage['observations']:
                    self.assertLessEqual(len(o['selected_ids']), o['budget_entries'])

    def test_labels_do_not_select_and_values_do_not_score(self):
        case = copy.deepcopy(self.fixture['cases'][0])
        pool = case['base'] + case['additions']
        before = study.rank(pool, case['query'])
        for item in pool:
            item['value'] = 'clean bowl kitchen ' * 100
        after = study.rank(pool, case['query'])
        self.assertEqual([(i['id'], i['score']) for i in before], [(i['id'], i['score']) for i in after])
        altered = copy.deepcopy(self.fixture)
        for c in altered['cases']:
            c['relevant_ids'] = []
        unlabelled = study.report(altered)
        for original, changed in zip(self.result['cases'], unlabelled['cases']):
            for a, b in zip(original['stages'], changed['stages']):
                self.assertEqual(a['ranking'], b['ranking'])
                self.assertEqual([o['selected_ids'] for o in a['observations']],
                                 [o['selected_ids'] for o in b['observations']])

    def test_same_key_tie_depends_on_order_without_semantic_resolution(self):
        case = self.fixture['cases'][-1]
        reversed_pool = list(reversed(case['base']))
        self.assertNotIn('old-locked-room', study.select(study.rank(case['base'], case['query']), 3, 'unique-key'))
        self.assertIn('old-locked-room', study.select(study.rank(reversed_pool, case['query']), 3, 'unique-key'))

    def test_execution_preserves_original_fixtures(self):
        source = copy.deepcopy(self.fixture)
        study.report(source)
        self.assertEqual(source, self.fixture)


if __name__ == '__main__':
    unittest.main()
