"""Offline contract checks for the linked, post-diagnostic factual redesign.

The source histories remain canonical in natural-cases.json. Named gold checks
state independent acceptance expectations; the small schema checker validates
only the deliberately limited JSON Schema subset used by these tasks.
"""
import collections
from datetime import date
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parent


def conforms(value, schema):
    """Check the actual supported answer shapes without third-party packages."""
    types = schema['type']
    types = [types] if isinstance(types, str) else types
    if value is None:
        kind = 'null'
    elif type(value) is int:
        kind = 'integer'
    elif isinstance(value, str):
        kind = 'string'
    elif isinstance(value, list):
        kind = 'array'
    else:
        return False
    if kind not in types:
        return False
    if 'enum' in schema and value not in schema['enum']:
        return False
    if kind == 'string' and 'pattern' in schema:
        if not re.fullmatch(schema['pattern'], value):
            return False
    if kind == 'array':
        if not all(conforms(item, schema['items']) for item in value):
            return False
        if schema.get('uniqueItems') and len(value) != len(set(value)):
            return False
    return True


class NaturalFactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / 'natural-facts.json').read_text(encoding='utf-8'))
        cls.questions = {q['id']: q for q in cls.data['questions']}
        cls.cases = {c['id']: c for c in json.loads(
            (ROOT / 'natural-cases.json').read_text(encoding='utf-8'))['cases']}

    def gold(self, cid, number):
        return self.questions[f'{cid}:f{number}']['gold']

    def event(self, cid, number):
        return next(e for e in self.cases[cid]['events'] if e['id'] == f'{cid}:e{number:02}')

    def test_exactly_two_linked_tasks_per_frozen_history(self):
        self.assertEqual(self.data['schema'], 'ams-scope-factual-tasks/1')
        self.assertEqual(self.data['status'], 'exploratory-redesign-after-option-cue-diagnostic')
        self.assertEqual(len(self.data['questions']), 24)
        self.assertEqual(len(self.questions), 24)
        self.assertEqual(collections.Counter(q['case'] for q in self.questions.values()),
                         {cid: 2 for cid in self.cases})
        for cid in self.cases:
            self.assertEqual({q['id'] for q in self.questions.values() if q['case'] == cid},
                             {f'{cid}:f1', f'{cid}:f2'})
            self.assertEqual(self.questions[f'{cid}:f1']['kind'], 'scope-application')

    def test_shape_source_support_and_no_multiple_choice_or_gold_examples(self):
        for q in self.questions.values():
            with self.subTest(question=q['id']):
                self.assertEqual(set(q), {'id', 'case', 'kind', 'text', 'answer_schema',
                                          'gold', 'support', 'rationale'})
                self.assertRegex(q['text'], r'2026年11月\d+日')
                self.assertNotIn('options', q)
                self.assertNotIn('examples', q['answer_schema'])
                self.assertNotIn('default', q['answer_schema'])
                self.assertNotIn('const', q['answer_schema'])
                self.assertTrue(q['rationale'].strip())
                events = {e['id'] for e in self.cases[q['case']]['events']}
                self.assertTrue(q['support'])
                self.assertEqual(len(q['support']), len(set(q['support'])))
                self.assertTrue(set(q['support']) <= events)

    def test_gold_and_unknown_conform_to_each_answer_schema(self):
        for q in self.questions.values():
            with self.subTest(question=q['id']):
                self.assertTrue(conforms(q['gold'], q['answer_schema']))
                self.assertTrue(conforms(None, q['answer_schema']))
                self.assertFalse(conforms({'explanation': q['gold']}, q['answer_schema']))
                if isinstance(q['gold'], list):
                    self.assertEqual(q['gold'], sorted(set(q['gold'])))
                    self.assertTrue(q['answer_schema']['uniqueItems'])
                    self.assertTrue(conforms(list(reversed(q['gold'])), q['answer_schema']))
                if 'pattern' in q['answer_schema'] and q['gold'] is not None:
                    date.fromisoformat(q['gold'])
                    # No answer date is supplied in the task or an example.
                    gold_date = date.fromisoformat(q['gold'])
                    self.assertNotIn(f'{gold_date.year}年{gold_date.month}月{gold_date.day}日', q['text'])

    def test_closed_labels_are_operational_values_not_justifications(self):
        approved = {'路线', '访谈练习', '插画', '普通预约', '快通', '南门', '北门',
                    '前台', '柜机', '收货台', '临时台', '展位', '规格单', '文字版封面',
                    '图文版封面', '独自训练', '培训员带队训练', '技术队', '编辑队'}
        for q in self.questions.values():
            schema = q['answer_schema']
            enums = schema.get('enum', schema.get('items', {}).get('enum', []))
            for value in enums:
                if isinstance(value, str):
                    self.assertIn(value, approved)
                    self.assertNotIn('因为', value)
                    self.assertNotIn('批准', value)

    def test_two_actual_unspecified_dates_are_the_only_null_gold(self):
        unknown = {q['id'] for q in self.questions.values() if q['gold'] is None}
        self.assertEqual(unknown, {'field-notes:f2', 'joint-release:f2'})
        self.assertIn('不提前宣布定稿', self.event('field-notes', 12)['text'])
        self.assertIn('仍没有共同接受同一个封面或公开日期',
                      self.event('joint-release', 12)['text'])

    def test_manual_recipient_and_calendar_application(self):
        self.assertEqual(self.gold('field-notes', 1), ['插画', '路线'])
        self.assertIn('选品会的用途发两章', self.event('field-notes', 7)['text'])
        self.assertEqual(date(2026, 11, 28).weekday(), 5)
        self.assertEqual((date(2026, 12, 1) - date(2026, 11, 28)).days, 3)
        self.assertEqual(self.gold('studio-room', 1), '快通')
        self.assertEqual(self.gold('studio-room', 2), 2)

    def test_manual_actual_change_date_and_confirmation_field(self):
        self.assertEqual(self.gold('water-counts', 1), ['北门'])
        self.assertEqual(self.gold('water-counts', 2), '2026-11-07')
        self.assertEqual(self.event('water-counts', 7)['at'][:10], '2026-11-07')
        self.assertIn('提前到今天完成', self.event('water-counts', 7)['text'])
        self.assertEqual(self.gold('dispatch-date', 1), '前台')
        self.assertEqual(self.gold('dispatch-date', 2), '2026-11-15')
        self.assertIn('旧单保留前台直到归还核验完', self.event('dispatch-date', 12)['text'])

    def test_manual_scope_bound_durations_and_historical_delay(self):
        self.assertEqual(self.gold('audio-edition', 1), 30)
        self.assertEqual(self.gold('audio-edition', 2), 60)
        self.assertIn('仅第四期', self.event('audio-edition', 4)['text'])
        self.assertEqual(self.gold('search-branch', 1), 500)
        self.assertEqual(self.gold('search-branch', 2), 300)
        self.assertIn('三百毫秒', self.event('search-branch', 2)['text'])
        self.assertIn('五百毫秒', self.event('search-branch', 4)['text'])

    def test_manual_single_day_location_and_partial_reinstatement(self):
        self.assertEqual(self.gold('fair-delivery', 1), '收货台')
        self.assertEqual(self.gold('fair-delivery', 2), '2026-11-08')
        self.assertIn('只有那一天改地点', self.event('fair-delivery', 6)['text'])
        self.assertEqual(self.gold('poster-set', 1), [1, 4])
        self.assertEqual(self.gold('poster-set', 2), 11)
        self.assertEqual(self.event('poster-set', 7)['at'][:10], '2026-11-07')
        self.assertIn('批准时间线第二张恢复', self.event('poster-set', 7)['text'])

    def test_manual_joint_scope_and_employee_modes(self):
        self.assertEqual(self.gold('joint-release', 1), ['规格单'])
        self.assertIn('同意内页核定稿和只发规格询价', self.event('joint-release', 3)['text'])
        self.assertEqual(self.gold('pilot-guide', 1), ['培训员带队训练'])
        self.assertEqual(self.gold('pilot-guide', 2), '2026-11-08')
        self.assertEqual(self.event('pilot-guide', 8)['at'][:10], '2026-11-08')
        self.assertIn('只保留培训员带队训练', self.event('pilot-guide', 8)['text'])

    def test_manual_budget_arithmetic_and_actual_mixed_workflow(self):
        self.assertEqual(self.gold('micro-grants', 1), 875 - 800)
        self.assertEqual(self.gold('micro-grants', 2), 650)
        self.assertIn('批准六百五十', self.event('micro-grants', 8)['text'])
        self.assertEqual(self.gold('support-routing', 1), ['技术队', '编辑队'])
        self.assertEqual(self.gold('support-routing', 2), 2)
        self.assertIn('回信列了两个编号', self.event('support-routing', 7)['text'])


if __name__ == '__main__':
    unittest.main()
