import copy
import json
import unittest
from pathlib import Path
import fixture_build as fixtures
import study

ROOT=Path(__file__).parent

class DecisionLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((ROOT/'fixtures.json').read_text())
        cls.results=json.loads((ROOT/'results.json').read_text())
        cls.train=study.rows_for(cls.fixture,'train')
        cls.test=study.rows_for(cls.fixture,'test')

    def test_frozen_inputs_match_public_generator(self):
        self.assertEqual(self.fixture,fixtures.generate())

    def test_groups_and_variants_do_not_cross_splits(self):
        groups=[{e['group'] for e in es} for es in self.fixture['splits'].values()]
        for i,a in enumerate(groups):
            for b in groups[i+1:]:self.assertFalse(a&b)
        ids=[e['id'] for es in self.fixture['splits'].values() for e in es]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(self.results['support']['test_rows_with_seen_vector'],len(self.test))

    def test_inference_ignores_labels_ids_and_positions(self):
        changed=copy.deepcopy(self.test)
        for row in changed:row.update(expected='wrong-label',id='noise',index=-1,group='noise')
        model=self.results['models']['original'];tree=self.results['models']['rules']
        self.assertEqual(study.all_predictions(self.train,self.test,model,tree),
                         study.all_predictions(self.train,changed,model,tree))

    def test_observation_vector_has_no_contradictory_labels_in_either_version(self):
        for version in (1,2):
            seen={}
            for split in self.fixture['splits']:
                for row in study.rows_for(self.fixture,split,version):
                    key=tuple(study.vector(row))
                    self.assertEqual(seen.setdefault(key,row['expected']),row['expected'])

    def test_context_candidate_and_known_counterfactuals(self):
        row=self.test[0];context=copy.deepcopy(row['context']);candidate=row['candidate']
        self.assertEqual(fixtures.label(context,candidate),'useful')
        context['known'].append(candidate['fact'])
        self.assertEqual(fixtures.label(context,candidate),'redundant')
        self.assertEqual(fixtures.label(row['context'],dict(candidate,expired=True)),'harmful')
        self.assertEqual(fixtures.label(row['context'],dict(candidate,goal='other')),'irrelevant')

    def test_correction_predicate_preserves_scope_boundaries(self):
        row=self.test[0];m=row['candidate'];c=dict(row['context'],sensitive=True)
        self.assertEqual(fixtures.label(c,m,1),'useful')
        self.assertEqual(fixtures.label(c,m,2),'harmful')
        self.assertEqual(fixtures.label(dict(c,sensitive=False),m,2),'useful')
        self.assertEqual(fixtures.label(c,dict(m,verified=True),2),'useful')

    def test_fitting_and_incremental_warm_start_are_real_and_do_not_mutate_original(self):
        models=self.results['models'];old=copy.deepcopy(models['original'])
        self.assertNotEqual(old['initial'],old['weights'])
        self.assertEqual(models['incremental']['initial'],old['weights'])
        self.assertNotEqual(models['incremental']['weights'],old['weights'])
        sample=copy.deepcopy(self.train[:12]);study.fit(sample,initial=old['weights'],steps=2)
        self.assertEqual(old,models['original'])
        correction_ids=self.results['after']['correction_row_ids']
        self.assertTrue(set(correction_ids).isdisjoint(r['id'] for r in self.test))
        self.assertLess(len(correction_ids),len(self.train))

    def test_saved_predictions_follow_saved_weights_and_tree(self):
        for key,phase in [('original','frozen'),('refit','refit'),('incremental','incremental')]:
            self.assertEqual(study.scorer(self.results['models'][key],self.test),self.results['after']['predictions'][phase])
        self.assertEqual(study.rule_predict(self.results['models']['rules'],self.test),self.results['before']['predictions']['rules'])

    def test_scope_metrics_and_transitions_match_per_case_results(self):
        cases=self.results['cases'];after=self.results['after'];predictions=after['predictions']
        for name,preds in predictions.items():
            for scope,metrics in after['metrics'][name].items():
                indices=[i for i,c in enumerate(cases) if c['scope']==scope or (scope=='preserved' and c['scope']=='boundary')]
                self.assertEqual(metrics['n'],len(indices))
                self.assertEqual(metrics['correct'],sum(preds[i]==cases[i]['expected_v2'] for i in indices))
                self.assertEqual(sum(after['transitions'][name][scope].values()),len(indices))
        self.assertEqual(predictions['frozen'],self.results['before']['predictions']['scorer'])

    def test_empty_selection_is_actually_exercised_and_counts_are_honest(self):
        metric=self.results['before']['metrics']['scorer']
        self.assertGreater(metric['empty_events'],0)
        wrong=['useful']*len(self.test)
        self.assertEqual(study.metrics(self.test,wrong)['correct_empty'],0)
        self.assertGreater(study.metrics(self.test,wrong)['harmful_selected'],0)
        self.assertTrue(self.results['controls']['identity-invariance'])

if __name__=='__main__':unittest.main()
