#!/usr/bin/env python3
"""Original local causal-LM probe. Not a C2C model or benchmark reproduction."""
import argparse
import hashlib
import json
import platform
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = 'HuggingFaceTB/SmolLM2-135M-Instruct'
REVISION = '12fd25f77366fa6b3b4b768ec3050bf629380bac'
TOLERANCE = 1e-4
TREATMENTS = ('full', 'trim', 'recompute', 'neutral_trim', 'masked_trim')


def fixtures():
    return json.loads((HERE / 'fixtures.json').read_text())


def prompts(pair, value, spec):
    fields = dict(pair, value=value)
    return (spec['prefix_template'].format(**fields),
            spec['retained_template'].format(**fields),
            {key: text.format(**fields) for key, text in spec['queries'].items()})


def derive(rows, comparisons):
    return {
        'rollouts': len(rows),
        'source_pairs_by_query': len(comparisons),
        'trim_pair_logit_differences_above_tolerance': sum(
            c['trim_pair']['max_abs_logit_delta'] > TOLERANCE for c in comparisons),
        'recompute_pair_controls_pass': all(
            c['recompute_pair']['max_abs_logit_delta'] <= TOLERANCE for c in comparisons),
        'masked_controls_pass': all(r['masked_vs_recompute']['max_abs_logit_delta'] <= TOLERANCE
                                    for r in rows if r['treatment'] == 'masked_trim'),
        'full_split_controls_pass': all(r['split_vs_full']['max_abs_logit_delta'] <= TOLERANCE
                                        for r in rows if r['treatment'] == 'full'),
        'shifted_split_and_repack_controls_pass': all(
            r['shifted_split_max_abs'] <= TOLERANCE and r['repack_max_abs'] <= TOLERANCE
            and max(max(s['k_max_abs'], s['v_max_abs']) for s in r['repack_cache_delta']) <= TOLERANCE
            for r in rows if r['treatment'] == 'recompute'),
        'causal_query_controls_pass': all(r['query_prefix_invariance_max_abs'] <= TOLERANCE
                                         and r['same_shape_future_change_max_abs'] <= TOLERANCE for r in rows),
        'masked_attention_and_state_controls_pass': all(
            r['masked_source_attention_max'] == 0
            and max(max(s['k_max_abs'], s['v_max_abs']) for s in r['suffix_cache_vs_recompute']) <= TOLERANCE
            for r in rows if r['treatment'] == 'masked_trim'),
        'masked_source_pair_controls_pass': all(
            max(max(s['k_max_abs'], s['v_max_abs']) for s in c['masked_suffix_cache_pair']) <= TOLERANCE
            for c in comparisons),
        'first_layer_content_controls_pass': all(c['suffix_cache_pair'][0]['k_max_abs'] <= TOLERANCE
                                                and c['suffix_cache_pair'][0]['v_max_abs'] <= TOLERANCE
                                                for c in comparisons),
        'greedy_top1_changes_after_source_swap': sum(c['trim_pair']['argmax_changed'] for c in comparisons),
        'scope': 'one fixed small model, four synthetic source pairs, five query roles; no accuracy benchmark'
    }


def verify_receipt(receipt):
    """Offline structural/arithmetic checks only; never asserts fresh model execution."""
    spec = fixtures()
    assert receipt['fixtures'] == spec, 'fixture binding changed'
    assert receipt['model']['id'] == MODEL and receipt['model']['revision'] == REVISION
    assert receipt['model']['verified_files'] == json.loads((HERE / 'model-files.json').read_text())['files']
    rows = receipt['rows']
    expected = {(p['id'], v, q, t) for p in spec['pairs'] for v in p['values']
                for q in spec['queries'] for t in TREATMENTS}
    actual = [(r['pair'], r['source_value'], r['query_role'], r['treatment']) for r in rows]
    assert len(actual) == len(set(actual)) and set(actual) == expected
    for row in rows:
        pair = next(p for p in spec['pairs'] if p['id'] == row['pair'])
        prefix, retained, queries = prompts(pair, row['source_value'], spec)
        assert row['source_text'] == prefix and row['retained_text'] == retained
        assert row['query_text'] == queries[row['query_role']]
        assert row['question_semantics'] == spec['question_semantics'][row['query_role']]
        n, r, q = [len(row[k]) for k in ('source_ids', 'retained_ids', 'query_ids')]
        assert len(row['neutral_ids']) == n
        assert row['retained_position_start'] == n and row['query_position_start'] == n+r
        physical = n+r if row['treatment'] == 'full' else r
        assert row['query_cache_position_start'] == physical
        assert row['query_attention_mask_length'] == physical+q
        assert set(row['candidate_scores']) == set(pair['values'] + [pair['updated']])
        for score in row['candidate_scores'].values():
            assert len(score['token_ids']) == len(score['token_log_probabilities'])
            assert abs(sum(score['token_log_probabilities']) - score['sequence_log_probability']) < 1e-10
    comparison_keys = [(c['pair'], c['query_role']) for c in receipt['comparisons']]
    assert len(comparison_keys) == len(set(comparison_keys))
    assert set(comparison_keys) == {(p['id'], q) for p in spec['pairs'] for q in spec['queries']}
    assert all(len(c['suffix_cache_pair']) == receipt['model']['layers'] for c in receipt['comparisons'])
    indexed = {(r['pair'], r['source_value'], r['query_role'], r['treatment']): r for r in rows}
    for comparison in receipt['comparisons']:
        pair = next(p for p in spec['pairs'] if p['id'] == comparison['pair'])
        a, b = pair['values']
        role = comparison['query_role']
        def scores(source, treatment):
            return {answer: score['sequence_log_probability'] for answer, score in
                    indexed[(pair['id'], source, role, treatment)]['candidate_scores'].items()}
        for treatment in TREATMENTS:
            sa, sb = scores(a, treatment), scores(b, treatment)
            contrast = (sa[a] - sa[b] - (sb[a] - sb[b])) / 2
            assert abs(comparison['exploratory_source_value_margin_contrast'][treatment] - contrast) < 1e-10
        eligible = []
        for source in (a, b):
            target = source if spec['question_semantics'][role]['target'] == 'source_value' else pair['updated']
            s = scores(source, 'full')
            eligible.append(s[target] > max(value for answer, value in s.items() if answer != target))
        assert comparison['full_candidate_eligible_both'] == all(eligible)
    assert receipt['summary'] == derive(rows, receipt['comparisons']), 'derived summary changed'
    return receipt['summary']


def run(model_dir, raw_path, dtype_name):
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, DynamicCache
    identity = json.loads((HERE / 'model-files.json').read_text())
    for filename, expected in identity['files'].items():
        with (model_dir / filename).open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected, f'model identity: {filename}'
    torch.set_num_threads(4)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    dtype = getattr(torch, dtype_name)
    tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True,
                                                trust_remote_code=False, torch_dtype=dtype,
                                                attn_implementation='eager').eval().cpu()
    spec = fixtures()
    rows, comparisons, raw = [], [], {}

    def encode(text):
        return tok.encode(text, add_special_tokens=False)

    def clone_cache(cache, start=0):
        result = DynamicCache()
        for layer, (k, v) in enumerate(cache):
            result.update(k[:, :, start:, :].clone(), v[:, :, start:, :].clone(), layer)
        return result

    def forward(ids, position, cache=None, prefix_mask=0):
        past = 0 if cache is None else cache.get_seq_length()
        mask = torch.ones((1, past+len(ids)), dtype=torch.long)
        if prefix_mask:
            assert past == 0
            # C rows remain causal; only R queries lose access to C keys.
            mask = torch.full((1, 1, len(ids), len(ids)), torch.finfo(dtype).min, dtype=dtype)
            for i in range(len(ids)):
                mask[0, 0, i, :i+1] = 0
            mask[0, 0, prefix_mask:, :prefix_mask] = torch.finfo(dtype).min
        return model(input_ids=torch.tensor([ids]), past_key_values=cache,
                     attention_mask=mask, position_ids=torch.arange(position, position+len(ids))[None, :],
                     cache_position=torch.arange(past, past+len(ids)), use_cache=True,
                     output_attentions=bool(prefix_mask))

    def delta(a, b):
        pa, pb = a.double().softmax(-1), b.double().softmax(-1)
        return {'max_abs_logit_delta': float((a-b).abs().max()),
                'total_variation': float((pa-pb).abs().sum()/2),
                'argmax_changed': int(a.argmax()) != int(b.argmax())}

    def cache_delta(a, b):
        return [{'layer': i, 'k_max_abs': float((ka-kb).abs().max()),
                 'v_max_abs': float((va-vb).abs().max())}
                for i, ((ka, va), (kb, vb)) in enumerate(zip(a, b))]

    def describe(out, query_end, answers):
        logits = out.logits[0, -1].clone()
        logp = logits.double().log_softmax(-1)
        scores = {}
        for answer in answers:
            ids = encode(' '+answer)
            terms = [float(logp[ids[0]])]
            if len(ids) > 1:
                more = forward(ids[:-1], query_end, clone_cache(out.past_key_values))
                logs = more.logits[0].double().log_softmax(-1)
                terms += [float(logs[i, token]) for i, token in enumerate(ids[1:])]
            scores[answer] = {'token_ids': ids, 'token_log_probabilities': terms,
                              'sequence_log_probability': sum(terms)}
        values, indices = logp.exp().topk(5)
        top = [{'id': int(i), 'text': tok.decode([i]), 'probability': float(p)}
               for i, p in zip(indices.tolist(), values.tolist())]
        generated = []
        gen_cache = clone_cache(out.past_key_values)
        next_logits = logits
        for step in range(8):
            token = int(next_logits.argmax())
            generated.append(token)
            if token == tok.eos_token_id:
                break
            next_logits = forward([token], query_end+step, gen_cache).logits[0, -1]
        return logits, scores, top, generated

    with torch.inference_mode():
        for pair in spec['pairs']:
            by_source, caches_by_source, masked_by_source, scores_by_source = {}, {}, {}, {}
            lengths = []
            for value in pair['values']:
                ctext, rtext, queries = prompts(pair, value, spec)
                c, r = encode(ctext), encode(rtext)
                n = len(c)
                lengths.append(n)
                neutral_token = encode(' note')
                assert len(neutral_token) == 1, 'neutral token must be a single fixed token'
                neutral = neutral_token*n
                full = forward(c+r, 0).past_key_values
                masked = forward(c+r, 0, prefix_mask=n)
                masked_source_attention = max(float(a[:, :, n:, :n].abs().max()) for a in masked.attentions)
                caches = {'full': full, 'trim': clone_cache(full, n),
                          'recompute': forward(r, n).past_key_values,
                          'neutral_trim': clone_cache(forward(neutral+r, 0).past_key_values, n),
                          'masked_trim': clone_cache(masked.past_key_values, n)}
                assert caches['trim'].get_seq_length() == len(r)
                assert all(torch.equal(k, fk[:, :, n:, :]) and torch.equal(v, fv[:, :, n:, :])
                           for (k, v), (fk, fv) in zip(caches['trim'], full))
                caches_by_source[value] = caches['trim']
                masked_by_source[value] = caches['masked_trim']
                by_source[value] = {}
                scores_by_source[value] = {}
                for role, qtext in queries.items():
                    q = encode(qtext)
                    outs = {t: forward(q, n+len(r), clone_cache(cache)) for t, cache in caches.items()}
                    by_source[value][role] = {t: out.logits[0, -1].clone() for t, out in outs.items()}
                    scores_by_source[value][role] = {}
                    for treatment, out in outs.items():
                        logits, scores, top, generated = describe(out, n+len(r)+len(q), pair['values']+[pair['updated']])
                        scores_by_source[value][role][treatment] = scores
                        for candidate in scores.values():
                            assert len(candidate['token_ids']) == 1, 'fixed fixtures use one-token candidate continuations'
                        assert all(encode(qtext+' '+a) == q+encode(' '+a) for a in scores), 'continuation boundary'
                        cut = len(q)//2
                        short = forward(q[:cut], n+len(r), clone_cache(caches[treatment]))
                        future_changed = forward(q[:cut]+list(reversed(q[cut:])), n+len(r), clone_cache(caches[treatment]))
                        raw['|'.join((pair['id'], value, role, treatment))] = logits
                        row = {'pair': pair['id'], 'source_value': value, 'query_role': role, 'treatment': treatment,
                               'source_text': ctext, 'retained_text': rtext, 'query_text': qtext,
                               'question_semantics': spec['question_semantics'][role],
                               'source_ids': c, 'retained_ids': r, 'query_ids': q, 'neutral_ids': neutral,
                               'retained_position_start': n, 'query_position_start': n+len(r),
                               'query_cache_position_start': caches[treatment].get_seq_length(),
                               'query_attention_mask_length': caches[treatment].get_seq_length()+len(q),
                               'prefill_prefix_masked': treatment == 'masked_trim',
                               'candidate_scores': scores, 'top5': top, 'greedy_ids': generated,
                               'greedy_text': tok.decode(generated),
                               'query_prefix_invariance_max_abs': float((short.logits-out.logits[:, :cut]).abs().max()),
                               'same_shape_future_change_max_abs': float((future_changed.logits[:, :cut]-out.logits[:, :cut]).abs().max()),
                               'vs_recompute': delta(logits, outs['recompute'].logits[0, -1]),
                               'suffix_cache_vs_recompute': cache_delta(clone_cache(caches[treatment], n if treatment == 'full' else 0), caches['recompute'])}
                        if treatment == 'full':
                            joined = forward(c+r+q, 0)
                            row['split_vs_full'] = {'max_abs_logit_delta': float((out.logits-joined.logits[:, -len(q):]).abs().max())}
                        if treatment == 'recompute':
                            joined = forward(r+q, n)
                            native = forward(q, n+len(r), forward(r, n).past_key_values)
                            row['shifted_split_max_abs'] = float((out.logits-joined.logits[:, -len(q):]).abs().max())
                            row['repack_max_abs'] = float((out.logits-native.logits).abs().max())
                            row['repack_cache_delta'] = cache_delta(out.past_key_values, native.past_key_values)
                        if treatment == 'masked_trim':
                            row['masked_vs_recompute'] = row['vs_recompute']
                            row['masked_source_attention_max'] = masked_source_attention
                        rows.append(row)
                print('completed', pair['id'], value, flush=True)
            assert lengths[0] == lengths[1], 'paired source lengths must match'
            a, b = pair['values']
            for role in spec['queries']:
                def margin(source, treatment):
                    s = scores_by_source[source][role][treatment]
                    return s[a]['sequence_log_probability'] - s[b]['sequence_log_probability']
                eligible = []
                for source in (a, b):
                    target = source if spec['question_semantics'][role]['target'] == 'source_value' else pair['updated']
                    s = scores_by_source[source][role]['full']
                    eligible.append(s[target]['sequence_log_probability'] > max(
                        score['sequence_log_probability'] for answer, score in s.items() if answer != target))
                comparisons.append({'pair': pair['id'], 'query_role': role,
                                    'trim_pair': delta(by_source[a][role]['trim'], by_source[b][role]['trim']),
                                    'recompute_pair': delta(by_source[a][role]['recompute'], by_source[b][role]['recompute']),
                                    'suffix_cache_pair': cache_delta(caches_by_source[a], caches_by_source[b]),
                                    'masked_suffix_cache_pair': cache_delta(masked_by_source[a], masked_by_source[b]),
                                    'exploratory_source_value_margin_contrast': {
                                        t: (margin(a,t)-margin(b,t))/2 for t in TREATMENTS},
                                    'full_candidate_eligible_both': all(eligible)})
    torch.save(raw, raw_path)
    result = {'schema': 'ams-c2c-retraction-results-v2', 'date': '2026-09-18',
              'phase': 'fresh run after review and numerical-control amendments; earlier outputs were inspected',
              'byline': 'Agent Memory Study editors', 'fixtures': spec,
              'model': {'id': MODEL, 'revision': REVISION, 'parameters': sum(p.numel() for p in model.parameters()),
                        'layers': model.config.num_hidden_layers, 'verified_files': identity['files']},
              'environment': {'python': platform.python_version(), 'torch': torch.__version__,
                              'transformers': transformers.__version__, 'device': 'cpu', 'dtype': dtype_name,
                              'upstream_precision_note': 'Llama RoPE frequency computation and eager softmax use float32 internally',
                              'attention': 'eager', 'threads': 4, 'greedy_max_new_tokens': 8},
              'rows': rows, 'comparisons': comparisons, 'summary': derive(rows, comparisons),
              'limits': ['Original single-model experiment, not C2C fusion or paper benchmark reproduction.',
                         'Compact receipts are not proof of fresh inference; use pinned weights and runner.',
                         'Token sequence likelihoods are not calibrated correctness probabilities.',
                         'Synthetic cloze prompts do not establish real-world correction reliability.']}
    verify_receipt(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--raw-logits', type=Path)
    parser.add_argument('--dtype', choices=('float32', 'float64'), default='float64')
    parser.add_argument('--verify-checked', action='store_true')
    args = parser.parse_args()
    if args.verify_checked:
        result = json.loads((HERE / 'results.json').read_text())
        print(json.dumps(verify_receipt(result), ensure_ascii=False, indent=2))
        print('PASS: saved receipt structure and derived arithmetic only; no fresh inference')
    else:
        if not all((args.model_dir, args.output, args.raw_logits)):
            parser.error('fresh inference requires --model-dir, --output and --raw-logits')
        result = run(args.model_dir, args.raw_logits, args.dtype)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(result['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
