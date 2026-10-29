"""Native owner integration; no network, model or historical receipt changes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from services.local import studies

PROJECT=Path(__file__).resolve().parents[2]
class StudyTests(unittest.TestCase):
    def execute(self,study,operation,parameters=None):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        plan={'study':study,'operation':operation}
        if parameters is not None:plan['parameters']=parameters
        return studies.execute(PROJECT,plan,Path(self.temp.name)/'attempt')
    def test_registry_readonly_boundaries(self):
        reg={r['id']:r for r in studies.registry()}
        self.assertNotIn('run',reg['c2c-cache-retraction-study']['operations'])
        self.assertNotIn('check-saved-results',reg['decision-learning-study']['operations'])
        self.assertEqual(len(reg),7)
        for r in reg.values():self.assertFalse(r['network']);self.assertFalse(r['provider'])
    def test_arbitrary_command_path_url_rejected(self):
        for plan in [dict(study='unknown',operation='run'),dict(study='conditional-contribution-study',operation='run',parameters={'out':'/etc'}),dict(study='observation-contract-study',operation='run',argv=['sh']),dict(study='conditional-contribution-study',operation='replay',source_job='x',parameters={'url':'https://example.org'})]:
            with self.assertRaises(ValueError):studies.validate_plan(PROJECT,plan)
    def test_p8_native_adapter_and_saved_check(self):
        r=self.execute('observation-contract-study','run',{'operation':'search-pair','model':'score-weighted','left':'revision','right':'scope'})
        self.assertEqual(r['result']['result']['word'],['prepare','inspect'])
        self.assertEqual(r['interpretation']['state'],'not-recorded')
        self.assertEqual(studies.evidence(Path(self.temp.name)/'attempt',r)['stages'][0]['word'],['prepare','inspect'])
        self.assertEqual(self.execute('observation-contract-study','check-saved-results')['result']['status'],'checked-finite-recomputation')
    def test_p9_real_native_run_replay_and_evidence(self):
        r=self.execute('conditional-contribution-study','run',{'limit':2})
        self.assertEqual(r['result']['result'],r['native_validation']['result'])
        work=Path(self.temp.name)/'attempt';e=studies.evidence(work,r)
        self.assertEqual(len(e['stages']),2);self.assertIn('messages',e['stages'][0]['request'])
        self.assertEqual(e['used'],'unknown')
        self.assertEqual(studies.validate_artifacts(PROJECT,r['study'],work/'native')['attempt_count'],2)
    def test_representation_native_small_run(self):
        r=self.execute('representation-use-study','run',{'limit':2})
        self.assertEqual(r['result'],r['native_validation'])
        e=studies.evidence(Path(self.temp.name)/'attempt',r)
        self.assertEqual(len(e['stages']),2);self.assertIsNotNone(e['stages'][0]['response'])
    def test_revision_native_small_run(self):
        r=self.execute('revision-propagation-study','run',{'limit':2})
        self.assertEqual(r['result'],r['native_validation'])
        self.assertEqual(len(studies.evidence(Path(self.temp.name)/'attempt',r)['stages']),2)
    def test_finite_enum_and_historical_inspection(self):
        r=self.execute('task-relative-sufficiency','check-saved-results');self.assertEqual(r['evidence_kind'],'finite-exact')
        for name in ['c2c-cache-retraction-study','decision-learning-study']:
            r=self.execute(name,'inspect');e=studies.evidence(Path(self.temp.name)/'attempt',r)
            self.assertTrue(e['missing_raw']);self.assertEqual(r['run']['state'],'not-new-execution')
    def test_c2c_actual_saved_arithmetic_no_inference(self):
        r=self.execute('c2c-cache-retraction-study','check-saved-results');self.assertIsInstance(r['result'],dict)
    def test_all_advertised_saved_checks_and_prepare(self):
        for name in ('conditional-contribution-study','representation-use-study','revision-propagation-study'):
            self.assertIsInstance(self.execute(name,'check-saved-results')['result'],dict)
        for name in ('representation-use-study','revision-propagation-study'):
            r=self.execute(name,'prepare');self.assertIn('native_plan',r['result'])
            self.assertEqual(r['run']['state'],'not-new-execution')

    def test_native_validation_failure_not_success(self):
        adapter=studies.load_module(PROJECT/'research/conditional-contribution-study/adapter.py')
        native=adapter.execute
        def bad(plan):
            value=native(plan)
            if plan['operation']=='replay':value['result']['attempt_count']=-1
            return value
        with patch.object(adapter,'execute',side_effect=bad),patch.object(studies,'load_module',return_value=adapter):
            with self.assertRaisesRegex(ValueError,'mismatch'):self.execute('conditional-contribution-study','run',{'limit':1})
    def test_saved_corruption_rejected(self):
        original=studies.read
        def corrupt(path):
            if Path(path).name=='results.json':return {'corrupt':True}
            return original(path)
        with patch.object(studies,'read',side_effect=corrupt):
            with self.assertRaises(ValueError):self.execute('observation-contract-study','check-saved-results')

if __name__=='__main__':unittest.main()
