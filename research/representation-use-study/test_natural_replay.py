"""Bound malformed provider bodies must not abort an otherwise useful raw replay."""
import contextlib
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import natural as n
import natural_api as api
import natural_facts as facts
import natural_probe as probe
from test_natural import data, receipt


def priced(value, model):
    result = receipt(value)
    body = json.loads(result['raw_body'])
    body.update(model=model, usage={'input_tokens': 100, 'output_tokens': 2,
        'input_tokens_details': {'cached_tokens': 0},
        'output_tokens_details': {'reasoning_tokens': 1}})
    result['raw_body'] = json.dumps(body)
    return result


def sample(root, bad_body):
    """Original synthetic transport sample; no provider calls, retained on request."""
    def good(endpoint, payload):
        if endpoint.endswith('input_tokens'):
            return {'http_status': 200, 'raw_body': '{"input_tokens":100}'}
        name = payload['text']['format']['name']
        value = ({'memory': '公开版获准。[e1]'} if name == 'scope_memory' else
                 {'answer': 1, 'sources': [], 'basis': ''} if name == 'factual_answer' else
                 {'choice': 'A', 'sources': [], 'basis': ''})
        return priced(value, payload['model'])

    def run_with_bad(directory, phase, plan):
        calls = 0
        def transport(endpoint, payload):
            nonlocal calls
            if endpoint == '/responses':
                calls += 1
                if calls == 1:
                    return {'http_status': 200, 'raw_body': bad_body}
            return good(endpoint, payload)
        with patch.object(api, 'post', side_effect=transport):
            api.run_phase(directory, phase, plan)

    primary, control, factual = (root/name for name in ('primary', 'control', 'factual'))
    with patch.object(n, 'corpus', return_value=data()), patch.object(api, 'post', side_effect=good):
        n.prepare(primary)
        api.write(primary)
    memories = n.load(primary/'memories.json')
    run_with_bad(primary, 'readers', n.reader_jobs(data(), memories))
    for directory in (control, factual):
        directory.mkdir()
        n.freeze(directory/'corpus.json', data())
    n.freeze(control/'manifest.json', {'source_identity': probe.identity(), 'corpus_digest': n.digest(data())})
    run_with_bad(control, 'question-only', probe.jobs(data()))
    tasks = {'questions': [{'id': 'c:f1', 'case': 'c', 'kind': 'scope', 'text': '计数？',
                           'answer_schema': {'type': ['integer', 'null']}, 'gold': 1}]}
    n.freeze(factual/'memories.json', memories)
    n.freeze(factual/'tasks.json', tasks)
    n.freeze(factual/'manifest.json', {'source_identity': facts.identity(), 'corpus_digest': n.digest(data()),
             'memories_digest': n.digest(memories), 'tasks_digest': n.digest(tasks)})
    run_with_bad(factual, 'facts', facts.jobs(data(), memories, tasks))
    with patch.object(api, 'post', side_effect=AssertionError('replay must be offline')):
        results = [api.replay(primary), probe.replay(control), facts.replay(factual)]
    for directory, result in zip((primary, control, factual), results):
        n.freeze(directory/'replay.json', result)
    return results


class ReplayTests(unittest.TestCase):
    def test_bound_bad_json_body_retains_failures_and_other_calls_in_all_replays(self):
        for raw in ('[]', 'null', '{broken'):
            with self.subTest(body=raw), tempfile.TemporaryDirectory() as tmp, \
                    contextlib.redirect_stdout(None):
                primary, control, factual = sample(Path(tmp), raw)
                self.assertEqual(primary['reader_receipts'], 12)
                self.assertEqual(sum(g['valid'] for g in primary['groups']), 11)
                self.assertEqual(sum(e['status'] == 'parse_error' for g in primary['groups'] for e in g['errors']), 1)
                reader_usage = [u for u in primary['usage'] if u['phase'] == 'readers']
                self.assertEqual(sum(u['usage_receipts'] for u in reader_usage), 11)
                self.assertEqual(sum(u['input_tokens'] for u in reader_usage), 1100)
                self.assertEqual(control['receipts'], 4)
                self.assertEqual(sum(g['valid'] for g in control['groups']), 3)
                self.assertEqual(sum(g['usage_receipts'] for g in control['groups']), 3)
                self.assertEqual(factual['receipts'], 8)
                self.assertEqual(sum(r['outcome'] == 'technical-failure' for r in factual['rows']), 1)
                self.assertEqual(sum(g['usage_receipts'] for g in factual['groups']), 7)
                self.assertEqual(sum(g['input_tokens'] for g in factual['groups']), 700)

    def test_archived_execution_is_explicit_offline_and_still_request_bound(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(None):
            root = Path(tmp)
            sample(root, '[]')
            archive = root/'source'; archive.mkdir()
            sources = n.identity() | probe.identity() | facts.identity()
            for name in sources:
                body = (n.ROOT/name).read_bytes()
                if name == 'natural_api.py': body += b'\n# synthetic earlier execution source\n'
                (archive/name).write_bytes(body)
            for name, module in (('primary', api), ('control', probe), ('factual', facts)):
                run = root/name
                manifest = n.load(run/'manifest.json')
                manifest['source_identity'] = {filename: hashlib.sha256((archive/filename).read_bytes()).hexdigest()
                                               for filename in manifest['source_identity']}
                (run/'manifest.json').write_text(n.canonical(manifest))
                with self.assertRaisesRegex(ValueError, 'new run required'):
                    module.replay(run)
                with patch.object(api, 'post', side_effect=AssertionError('network')):
                    result = module.replay(run, archive)
                self.assertEqual(result['source_identity'], manifest['source_identity'])
                self.assertNotEqual(result['replay_source_identity'], result['source_identity'])
                n.check_saved_source(result, result['replay_source_identity'])
            with patch.object(api, 'post', side_effect=AssertionError('network')):
                with self.assertRaisesRegex(ValueError, 'new run required'):
                    api.read(root/'primary')
            request = next((root/'primary'/'readers').glob('*.request.json'))
            changed = n.load(request); changed['input'][1]['content'] = 'changed actual input'
            request.write_text(n.canonical(changed))
            with self.assertRaisesRegex(ValueError, 'actual request'):
                api.replay(root/'primary', archive)
            (archive/'natural_api.py').write_text('corrupt archive')
            with self.assertRaisesRegex(ValueError, 'archive mismatch'):
                probe.replay(root/'control', archive)

    def test_valid_answers_survive_unavailable_usage(self):
        value = priced({'choice': 'A', 'sources': [], 'basis': ''}, n.MODELS[0])
        body = json.loads(value['raw_body']); body['usage'] = []
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(None):
            primary, control, _ = sample(Path(tmp), json.dumps(body))
            self.assertEqual(sum(g['valid'] for g in primary['groups']), 12)
            self.assertEqual(sum(g['valid'] for g in control['groups']), 4)
            self.assertEqual(sum(g['usage_unavailable'] for g in control['groups']), 1)

    def test_usage_validation_is_independent_of_answer_scoring(self):
        good = priced({'choice': 'Z', 'sources': [], 'basis': ''}, n.MODELS[0])
        self.assertEqual(n.parse(good)['status'], 'parse_error')
        self.assertEqual(api.usage_metadata(good)['input_tokens'], 100)
        for usage in (None, [], {}, {'input_tokens': True, 'output_tokens': 1},
                      {'input_tokens': 10, 'output_tokens': -1},
                      {'input_tokens': 10, 'output_tokens': 1, 'input_tokens_details': []},
                      {'input_tokens': 10, 'output_tokens': 1, 'output_tokens_details': {'reasoning_tokens': 'one'}}):
            with self.subTest(usage=usage):
                value = priced({'choice': 'A', 'sources': [], 'basis': ''}, n.MODELS[0])
                body = json.loads(value['raw_body']); body['usage'] = usage
                value['raw_body'] = json.dumps(body)
                self.assertEqual(n.parse(value)['status'], 'valid')
                self.assertIsNone(api.usage_metadata(value))
        body = json.loads(good['raw_body']); body.pop('model')
        good['raw_body'] = json.dumps(body)
        self.assertEqual(api.usage_metadata(good)['output_tokens'], 2)


if __name__ == '__main__':
    unittest.main()
