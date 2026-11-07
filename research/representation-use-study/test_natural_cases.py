"""Corpus contracts and independent, explicitly authored semantic gold checks.

These tests do not infer natural-language truth or certify every annotation. The
named checks lock difficult adjudications so a future mechanical reshuffle cannot
silently replace the scope/time interpretation. No model or provider is called.
"""
import collections
from datetime import datetime
import difflib
import json
from pathlib import Path
import unittest


CORPUS = Path(__file__).with_name('natural-cases.json')


class NaturalCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(CORPUS.read_text(encoding='utf-8'))
        cls.cases = {case['id']: case for case in cls.data['cases']}

    def chosen(self, cid, qid):
        question = next(q for q in self.cases[cid]['questions'] if q['id'] == f'{cid}:{qid}')
        return next(o['text'] for o in question['options'] if o['id'] == question['gold'])

    def event(self, cid, number):
        return next(e['text'] for e in self.cases[cid]['events'] if e['id'] == f'{cid}:e{number:02}')

    def test_original_diagnostic_shape_and_no_latent_event_fields(self):
        self.assertEqual(self.data['schema'], 'ams-natural-scope-cases/1')
        self.assertEqual(self.data['status'], 'original-authored-exploratory-diagnostic')
        self.assertEqual(len(self.data['cases']), 12)
        self.assertEqual(len(self.cases), 12)
        ids = []
        for case in self.cases.values():
            with self.subTest(case=case['id']):
                self.assertEqual(set(case), {'id', 'mechanism', 'title', 'events', 'questions'})
                self.assertTrue(12 <= len(case['events']) <= 18)
                self.assertEqual(len(case['questions']), 6)
                times = []
                for event in case['events']:
                    self.assertEqual(set(event), {'id', 'at', 'speaker', 'text'})
                    self.assertTrue(event['text'].strip())
                    self.assertTrue(event['speaker'].strip())
                    times.append(datetime.fromisoformat(event['at']))
                    ids.append(event['id'])
                self.assertEqual(times, sorted(times))
                self.assertEqual(len(times), len(set(times)))
                chars = sum(len(e['text']) for e in case['events'])
                self.assertGreaterEqual(chars, 1200)
                self.assertLessEqual(chars, 2400)
                support_ids = {e['id'] for e in case['events']}
                for q in case['questions']:
                    ids.append(q['id'])
                    self.assertEqual(set(q), {'id', 'kind', 'text', 'options', 'gold',
                                              'support', 'rationale', 'misconception'})
                    self.assertEqual([o['id'] for o in q['options']], list('ABCD'))
                    self.assertEqual(len({o['text'] for o in q['options']}), 4)
                    for o in q['options']:
                        self.assertEqual(set(o), {'id', 'text'})
                        self.assertTrue(o['text'].strip())
                    self.assertIn(q['gold'], 'ABCD')
                    self.assertTrue(q['support'])
                    self.assertEqual(len(q['support']), len(set(q['support'])))
                    self.assertTrue(set(q['support']) <= support_ids)
                    for field in ('text', 'rationale', 'misconception'):
                        self.assertTrue(q[field].strip())
        self.assertEqual(len(ids), len(set(ids)))

    def test_answer_positions_and_question_roles_are_balanced(self):
        counts = collections.Counter(q['gold'] for c in self.cases.values() for q in c['questions'])
        self.assertEqual(counts, {letter: 18 for letter in 'ABCD'})
        expected = {'current-action', 'preserved-boundary', 'historical-action',
                    'conjunction-boundary', 'targeted-clarification', 'ordinary-action'}
        for c in self.cases.values():
            self.assertEqual({q['kind'] for q in c['questions']}, expected)
            per_case = collections.Counter(q['gold'] for q in c['questions'])
            self.assertEqual(sorted(per_case.values()), [1, 1, 2, 2])

    def test_histories_are_distinct_authored_work_not_renamed_templates(self):
        cases = list(self.cases.values())
        self.assertEqual(len({c['title'] for c in cases}), 12)
        self.assertEqual(len({c['mechanism'] for c in cases}), 12)
        texts = ['\n'.join(e['text'] for e in c['events']) for c in cases]
        self.assertEqual(len(set(texts)), 12)
        # Detect near-verbatim copied narrative skeletons, not scientific independence.
        for i, a in enumerate(texts):
            for j in range(i):
                ratio = difflib.SequenceMatcher(None, a, texts[j], autojunk=False).ratio()
                self.assertLess(ratio, 0.55, (cases[i]['id'], cases[j]['id'], ratio))
        controls = [c for c in cases if c['mechanism'].startswith('stable-control-')]
        self.assertEqual(len(controls), 2)

    def test_manual_use_beats_dual_recipient_identity(self):
        self.assertIn('按他这次参加选品会的用途发两章', self.event('field-notes', 7))
        self.assertEqual(self.chosen('field-notes', 'q4'), '两章选品版本')
        self.assertEqual(self.chosen('field-notes', 'q2'), '仍提供整本校样用于挑错')
        self.assertEqual(self.chosen('field-notes', 'q3'), '整本校样')

    def test_manual_effective_date_uses_confirmation_not_collection(self):
        self.assertIn('切换依据是确认时间', self.event('dispatch-date', 6))
        self.assertEqual(self.chosen('dispatch-date', 'q4'), '前台，按原确认单完成交接与归还')
        self.assertEqual(self.chosen('dispatch-date', 'q1'), '领取与归还均走柜机')
        self.assertEqual(self.chosen('dispatch-date', 'q3'), '按前台纸本流程')

    def test_manual_individual_reinstatement_does_not_restore_whole_batch(self):
        self.assertIn('批准时间线第二张恢复', self.event('poster-set', 7))
        self.assertIn('第三张继续暂停', self.event('poster-set', 7))
        self.assertEqual(self.chosen('poster-set', 'q1'), '十一张，排除时间线第三张')
        self.assertEqual(self.chosen('poster-set', 'q3'), '十张，第二第三仍待各自恢复批准')
        self.assertEqual(self.chosen('poster-set', 'q6'), '可按恢复批准提供印刷PDF')

    def test_manual_equal_authority_conflict_has_no_latest_wins_rule(self):
        self.assertIn('没有约定谁最后发言就覆盖另一人', self.event('joint-release', 1))
        self.assertIn('没有同意文字版', self.event('joint-release', 6))
        self.assertEqual(self.chosen('joint-release', 'q1'), '暂停封面生产，请两位负责人共同对齐选择')
        self.assertEqual(self.chosen('joint-release', 'q6'), '可发送规格单，不附候选封面')

    def test_manual_prerequisites_do_not_imply_new_authorization(self):
        self.assertIn('不是自动生效信号', self.event('pilot-guide', 11))
        self.assertEqual(self.chosen('pilot-guide', 'q4'), '仍不能，须负责人明确接受改线')
        self.assertEqual(self.chosen('pilot-guide', 'q6'), '可按保留的带队训练安排并记录条件')

    def test_manual_expiry_reinstates_baseline_not_just_specific_item_ban(self):
        self.assertIn('到期自动恢复仅登记快递', self.event('fair-delivery', 3))
        self.assertEqual(self.chosen('fair-delivery', 'q1'), '不可以，回到登记快递流程')
        self.assertEqual(self.chosen('fair-delivery', 'q6'), '按常规签收后入样品柜')

    def test_manual_stable_controls_require_no_invented_revision(self):
        self.assertEqual(self.chosen('micro-grants', 'q4'), '符合不超过八百，可进入评审但不保证资助')
        self.assertEqual(self.chosen('micro-grants', 'q6'), '按批准付六百五十并保留原申请预算')
        self.assertEqual(self.chosen('support-routing', 'q2'), '直接由编辑队按使用问题处理')
        self.assertEqual(self.chosen('support-routing', 'q6'), '分别建编辑单和技术单并互链')


if __name__ == '__main__':
    unittest.main()
