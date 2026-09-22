"""Offline receipt checks. Fresh upstream execution uses the documented CLI."""
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('jev_contract_study', HERE/'study.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads((HERE/'results.json').read_text())
        self.fixtures = json.loads((HERE/'fixtures.json').read_text())

    def verify(self):
        return study.verify_checked(self.receipt, self.fixtures)

    def test_saved_receipt_and_controls(self):
        self.assertEqual(self.verify()['cases'], 10)
        cases={c['id']:c for c in self.receipt['cases']}
        merged=cases['merge-with-summarizer-creates-derived-representation']
        self.assertEqual(merged['before']['stored_ids'], ['n1','n2'])
        self.assertEqual(merged['after']['stored_ids'], ['n1','n2','n3'])
        self.assertEqual(merged['observations']['nodes']['n3']['source_memory_ids'], ['n2','n1'])

    def test_changed_fixture_is_not_the_same_execution(self):
        self.fixtures['cases'][0]['sequence'][0]['text']='Different observation'
        with self.assertRaisesRegex(SystemExit,'fixture binding'): self.verify()

    def test_wrong_source_pin(self):
        self.receipt['source']['commit']='0'*40
        with self.assertRaisesRegex(SystemExit,'commit pin'): self.verify()

    def test_case_order_mismatch(self):
        self.receipt['cases'].reverse()
        with self.assertRaisesRegex(SystemExit,'case ids/order'): self.verify()

    def test_magma_branch_cannot_pass_as_jev(self):
        self.receipt['cases'][0]['observations']['build_outcomes'][0]['has_jev_mem']=False
        with self.assertRaisesRegex(SystemExit,'recomputed checks'): self.verify()

    def test_recorded_obsolete_must_match_given_value(self):
        self.receipt['cases'][3]['observations']['consolidation_decisions'][0][0]['obsolete']=0.05
        with self.assertRaisesRegex(SystemExit,'recomputed checks'): self.verify()

    def test_deleted_node_cannot_keep_passed_flags(self):
        self.receipt['cases'][3]['after']['stored_ids'].remove('n1')
        with self.assertRaisesRegex(SystemExit,'recomputed checks'): self.verify()

    def test_summary_must_preserve_both_sources(self):
        case=next(c for c in self.receipt['cases'] if c['after']['summary_ids'])
        case['observations']['nodes']['n3']['source_memory_ids']=['n2']
        with self.assertRaisesRegex(SystemExit,'recomputed checks'): self.verify()

    def test_rejection_cannot_leave_vector(self):
        self.receipt['cases'][1]['after']['vector_ids']=['n1']
        with self.assertRaisesRegex(SystemExit,'recomputed checks'): self.verify()

    def test_summary_arithmetic_is_recomputed(self):
        self.receipt['summary']['cases']=11
        with self.assertRaisesRegex(SystemExit,'summary consistency'): self.verify()

    def test_original_content_cannot_silently_change(self):
        self.receipt['cases'][3]['observations']['nodes']['n1']['content']='Rewritten'
        with self.assertRaisesRegex(SystemExit,'recomputed checks'): self.verify()

    def test_effective_write_configuration_is_bound(self):
        self.receipt['cases'][0]['input']['config']['write_enabled']=False
        with self.assertRaisesRegex(SystemExit,'effective config'): self.verify()


if __name__ == '__main__': unittest.main()
