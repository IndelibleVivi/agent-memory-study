"""Guard evidence ownership, without treating a schema check as fact checking."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from tools import build


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((build.ROOT / 'data/materials.json').read_text())

    def validate(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'materials.json'
            path.write_text(json.dumps(data, ensure_ascii=False))
            return build.load_and_validate(path)

    def test_four_audits_have_independent_ownership(self):
        expected = {'statefuse-conflict-preserving-memory': 1,
                    'fluctlightdb-observation-binding': 4,
                    'memprobe-hidden-user-state-recovery': 2,
                    'useful-memories-become-faulty': 3}
        for mid, count in expected.items():
            m = next(m for m in self.data['materials'] if m['id'] == mid)
            self.assertEqual(len(m['amsEvidence']['findings']), count)
            self.assertTrue(m['reportedFindings'])
            self.assertTrue(m['amsEvidence']['methods'])
        self.validate(self.data)

    def test_worked_requires_executed_public_test(self):
        data = copy.deepcopy(self.data)
        m = next(m for m in data['materials'] if m['id'] == 'a-tma-state-aware-memory')
        m['noteDepth'] = 'worked'
        with self.assertRaisesRegex(ValueError, 'worked requires'):
            self.validate(data)

    def test_audit_artifact_must_exist_and_match_attribution(self):
        for path in ['../README.md', '/tmp/result.json', 'research/missing.json', 'research/correction-scope-study/README.md']:
            data = copy.deepcopy(self.data)
            m = next(m for m in data['materials'] if 'amsEvidence' in m)
            m['amsEvidence']['artifactUrl'] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.validate(data)
        data = copy.deepcopy(self.data)
        m = next(m for m in data['materials'] if 'amsEvidence' in m)
        m['amsEvidence']['byline'] = 'Unattributed test'
        with self.assertRaisesRegex(ValueError, 'attributed public-test'):
            self.validate(data)

    def test_audit_results_cannot_also_live_under_paper_label(self):
        for field, source in [('reportedFindings', 'findings'), ('keyPoints', 'observations')]:
            data = copy.deepcopy(self.data)
            m = next(m for m in data['materials'] if 'amsEvidence' in m)
            m[field].append(m['amsEvidence'][source][0])
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'duplicates'):
                self.validate(data)

    def test_audit_duplicates_reject_wrapping_and_whitespace_variants(self):
        variants = [
            lambda text: f'Paper prefix: {text}',
            lambda text: f'{text} Paper suffix.',
            lambda text: f'  {text.replace(" ", "  \n", 1)}  ',
        ]
        for variant in variants:
            data = copy.deepcopy(self.data)
            m = next(m for m in data['materials'] if 'amsEvidence' in m)
            m['reportedFindings'].append(variant(m['amsEvidence']['findings'][0]))
            with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, 'duplicates'):
                self.validate(data)

    def test_distinct_paper_and_audit_statements_remain_valid(self):
        data = copy.deepcopy(self.data)
        m = next(m for m in data['materials'] if 'amsEvidence' in m)
        m['reportedFindings'].append(
            'The paper reports a separate benchmark result with its own source locator.'
        )
        self.validate(data)

    def test_empty_or_untyped_audit_fails(self):
        for field in ['observations', 'reasoning', 'methods', 'findings']:
            data = copy.deepcopy(self.data)
            m = next(m for m in data['materials'] if 'amsEvidence' in m)
            m['amsEvidence'][field] = 'unstructured'
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(data)

    def test_recuris_reach_cannot_be_read_as_task_success(self):
        m = next(m for m in self.data['materials'] if m['id'] == 'recuris-memory-evolution')
        t = next(t['observation'] for t in m['sourceTensions'] if '0/86' in t['observation'])
        self.assertIn('memory reach 为 0/86', t)
        self.assertIn('57.85%', t)
        self.assertIn('Table 5', t)

    def test_early_why_read_and_later_transfer_keep_stable_ids(self):
        html = (build.ROOT / 'index.html').read_text()
        self.assertLess(html.index('id="why-read-block"'), html.index('id="paper-problem"'))
        self.assertGreater(html.index('id="paper-transfer"'), html.index('id="paper-findings"'))
        self.assertIn('AMS audit · 本站复核与实验', html)
        self.assertIn('Paper-reported findings', html)


if __name__ == '__main__':
    unittest.main()
