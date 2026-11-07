"""Reject leakage, misleading scores and duplicate/incorrectly bound paid calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import natural as n
import natural_api as api
import natural_probe as probe


def data():
    return {'cases': [{'id': 'c', 'title': '合成项目', 'mechanism': 'SECRET-MECHANISM',
                      'events': [{'id': 'e1', 'at': 'day1', 'speaker': '负责人', 'text': '允许公开版。'}],
                      'questions': [{'id': 'q1', 'kind': 'current', 'text': '公开版怎样处理？',
                                     'options': [{'id': x, 'text': x+'方案'} for x in 'ABCD'],
                                     'gold': 'B', 'support': ['e1'], 'rationale': 'SECRET-GOLD',
                                     'misconception': 'SECRET-ERROR'},
                                    {'id': 'q2', 'kind': 'boundary', 'text': 'SECOND-QUESTION',
                                     'options': [{'id': x, 'text': x+'其他'} for x in 'ABCD'],
                                     'gold': 'C', 'support': ['e1'], 'rationale': 'SECRET-GOLD',
                                     'misconception': 'SECRET-ERROR'}]}]}


def receipt(value, status='completed'):
    return {'http_status': 200, 'raw_body': json.dumps({'status': status,
        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]})}


class InputTests(unittest.TestCase):
    def test_question_blind_writer_and_reader_projection(self):
        d = data()
        writer = n.canonical(n.writer_jobs(d))
        for hidden in ('SECRET', '公开版怎样处理', 'SECOND-QUESTION'):
            self.assertNotIn(hidden, writer)
        jobs = n.reader_jobs(d, {'c--prose': {'status': 'valid', 'memory': 'PROSE'},
                                'c--ledger': {'status': 'valid', 'memory': 'LEDGER'}})
        for j in jobs:
            body = n.canonical(j['payload'])
            self.assertNotIn('SECRET', body)
            if j['question'] == 'q1':
                self.assertNotIn('SECOND-QUESTION', body)
            if j['arm'] == 'prose':
                self.assertIn('PROSE', body)
                self.assertNotIn('LEDGER', body)
            self.assertFalse(j['payload']['store'])
            self.assertEqual(j['payload']['service_tier'], 'default')

    def test_writer_failure_not_replaced_by_raw(self):
        jobs = n.reader_jobs(data(), {'c--prose': {'status': 'over_budget', 'memory': 'x'},
                                     'c--ledger': {'status': 'missing'}})
        self.assertTrue(all(j['payload'] is None for j in jobs if j['arm'] != 'raw'))
        result = n.aggregate(data(), jobs, {})
        self.assertTrue(all(g['correct'] == 0 and g['total'] == 2 for g in result['groups']))

    def test_schedule_is_fixed_and_each_task_is_separate(self):
        m = {'c--'+arm: {'status': 'valid', 'memory': arm} for arm in ('prose', 'ledger')}
        a, b = n.reader_jobs(data(), m), n.reader_jobs(data(), m)
        self.assertEqual(a, b)
        self.assertEqual(len({j['id'] for j in a}), 12)

    def test_question_only_probe_changes_only_memory(self):
        full = n.reader_jobs(data(), {'c--'+a: {'status': 'valid', 'memory': a} for a in ('prose', 'ledger')})
        original = {(j['case'],j['question'],j['model']):j['payload'] for j in full if j['arm']=='raw'}
        for j in probe.jobs(data()):
            p = copy.deepcopy(original[j['case'],j['question'],j['model']])
            user = json.loads(p['input'][1]['content']); user['memory']=''
            p['input'][1]['content']=n.canonical(user)
            self.assertEqual(j['payload'],p)
            self.assertNotIn('SECRET',n.canonical(j['payload']))


class ScoreTests(unittest.TestCase):
    def test_invalid_and_incomplete_do_not_receive_credit(self):
        self.assertEqual(n.parse(receipt({'choice': 'B', 'sources': [], 'basis': 'x'}, 'incomplete'))['status'], 'incomplete')
        for value in ({'choice': 'B'}, {'choice': 'Z', 'sources': [], 'basis': ''}, [], None):
            self.assertEqual(n.parse(receipt(value))['status'], 'parse_error')
        self.assertEqual(n.parse({'http_status': 429})['status'], 'http_error')

    def test_memory_length_is_reported_without_truncation_or_selection(self):
        for length, within in ((450, True), (451, False)):
            p = n.parse(receipt({'memory': '甲'*length}), True)
            self.assertEqual(p['status'], 'valid')
            self.assertEqual(p['within_requested_budget'], within)
            self.assertEqual(len(p['memory']), length)

    def test_paired_gains_and_losses_have_full_denominator(self):
        jobs = n.reader_jobs(data(), {'c--'+arm: {'status': 'valid', 'memory': arm} for arm in ('prose', 'ledger')})
        rr = {}
        for j in jobs:
            # Ledger gets q1 right but q2 wrong; prose opposite; raw both correct.
            gold = 'B' if j['question'] == 'q1' else 'C'
            correct = j['arm'] == 'raw' or (j['arm'] == 'ledger') == (j['question'] == 'q1')
            rr[j['id']] = receipt({'choice': gold if correct else 'A', 'sources': [], 'basis': ''})
        s = n.aggregate(data(), jobs, rr)
        pair = next(p for p in s['paired'] if p['baseline'] == 'prose')
        self.assertEqual((pair['ledger_only'], pair['baseline_only'], pair['both_correct']), (1, 1, 0))
        del rr[jobs[0]['id']]
        s = n.aggregate(data(), jobs, rr)
        self.assertEqual(sum(g['total'] for g in s['groups']), 12)
        self.assertEqual(sum(g['valid'] for g in s['groups']), 11)
        with self.assertRaises(ValueError):
            n.aggregate(data(), jobs, {'foreign': {}})


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.job = {'id': 'j', 'payload': n.payload('gpt-6-luna', 'system', 'user')}

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def fake_post(endpoint, payload):
        if endpoint.endswith('input_tokens'):
            return {'http_status': 200, 'raw_body': '{"input_tokens":100}'}
        return receipt({'choice': 'A', 'sources': [], 'basis': ''})

    def test_exclusive_complete_publication(self):
        p = self.root / 'a.json'
        n.freeze(p, {'a': 1})
        with self.assertRaises(FileExistsError):
            n.freeze(p, {'a': 2})
        self.assertEqual(n.load(p), {'a': 1})

    def test_no_network_on_offline_scoring(self):
        with patch.object(api, 'post', side_effect=AssertionError('network')):
            n.parse(receipt({'choice': 'A', 'sources': [], 'basis': ''}))
            n.aggregate(data(), n.reader_jobs(data(), {'c--'+a: {'status': 'missing'} for a in ('prose', 'ledger')}), {})

    def test_success_and_unknown_are_not_retried(self):
        with patch.object(api, 'post', side_effect=self.fake_post) as network:
            api.run_phase(self.root, 'test', [self.job])
            self.assertEqual(network.call_count, 2)
            api.run_phase(self.root, 'test', [self.job])
            self.assertEqual(network.call_count, 2)
        # Independent interrupted run with persisted request, no receipt.
        other = self.root / 'other'; other.mkdir()
        n.freeze(other / 'test' / 'j.request.json', self.job['payload'])
        with patch.object(api, 'post', side_effect=self.fake_post) as network:
            api.run_phase(other, 'test', [self.job])
            self.assertEqual(network.call_count, 1)  # token counting only
        self.assertEqual(api.responses(other, 'test', [self.job]), {})

    def test_request_and_response_binding_rejects_corruption(self):
        with patch.object(api, 'post', side_effect=self.fake_post):
            api.run_phase(self.root, 'test', [self.job])
        p = self.root / 'test' / 'j.request.json'
        value = n.load(p); value['input'][1]['content'] = 'changed'
        p.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'request'):
            api.responses(self.root, 'test', [self.job])

    def test_budget_gate_precedes_generation(self):
        with patch.object(api, 'post', return_value={'http_status': 200, 'raw_body': '{"input_tokens":1000000000}'}) as network:
            with self.assertRaisesRegex(ValueError, 'budget'):
                api.run_phase(self.root, 'test', [self.job])
            self.assertEqual(network.call_count, 1)
        self.assertFalse((self.root / 'test' / 'j.request.json').exists())

    def test_no_raw_runs_inside_repo_and_exclusive_writer(self):
        with self.assertRaises(ValueError):
            n.safe_root(n.REPO / 'untracked-run')
        with api.locked(self.root):
            with self.assertRaises(FileExistsError):
                with api.locked(self.root):
                    pass

    def test_amendment_inherits_every_writer_without_a_new_call(self):
        old, new = self.root / 'old', self.root / 'new'
        def fake(endpoint, payload):
            if endpoint.endswith('input_tokens'):
                return self.fake_post(endpoint, payload)
            if payload['text']['format']['name'] == 'scope_memory':
                return receipt({'memory': '甲'*451})
            return self.fake_post(endpoint, payload)
        with patch.object(n, 'corpus', return_value=data()), patch.object(n, 'identity', return_value={}), \
                patch.object(api, 'post', side_effect=fake) as network:
            n.prepare(old)
            api.run_phase(old, 'canaries', api.canary_jobs())
            api.run_phase(old, 'writers', n.writer_jobs(data()))
            before = network.call_count
            api.inherit_writers(old, new)
            self.assertEqual(network.call_count, before)
            memories, jobs = api.frozen_readers(new, data())
            self.assertTrue(all(not m['within_requested_budget'] for m in memories.values()))
            self.assertTrue(all(j['payload'] is not None for j in jobs))
            self.assertEqual(n.load(old/'writers'/'c--prose.response.json'), n.load(new/'writers'/'c--prose.response.json'))
            n.freeze(old/'readers'/'started.request.json', {})
            with self.assertRaisesRegex(ValueError, 'zero previous'):
                api.inherit_writers(old, self.root/'forbidden')


if __name__ == '__main__':
    unittest.main()
