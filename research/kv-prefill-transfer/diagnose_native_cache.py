#!/usr/bin/env python3
"""Separate disk reconstruction from BF16 chunk-shape effects on one validation doc."""
import argparse
import platform
import resource
import time
from pathlib import Path

import torch
import runner


def prefix_from_output(output, length, upstream):
    layers = upstream.huggingface._legacy_layers(output.past_key_values)
    return upstream.cache.KVCache(
        [key[:, :, :length].clone() for key, _ in layers],
        [value[:, :, :length].clone() for _, value in layers],
        keys_are_content=False,
    )


def compare_cache(left, right):
    """Exact element comparisons plus per-layer absolute deltas; no tolerance tuning."""
    report = {}
    for kind in ('keys', 'values'):
        rows = []
        for layer, (a, b) in enumerate(zip(getattr(left, kind), getattr(right, kind), strict=True)):
            assert a.shape == b.shape and a.dtype == b.dtype
            rows.append({'layer': layer, 'different_elements': int((a != b).sum()),
                         'elements': a.numel(), 'max_abs_delta': float((a.float()-b.float()).abs().max())})
        report[kind] = {'all_equal': all(row['different_elements'] == 0 for row in rows),
                        'max_abs_delta': max(row['max_abs_delta'] for row in rows),
                        'first_differing_layer': next((row['layer'] for row in rows if row['different_elements']), None),
                        'per_layer': rows}
    return report


def logit_delta(left, right):
    assert left.shape == right.shape
    return {'bitwise_equal': torch.equal(left, right),
            'max_abs_delta': float((left.float()-right.float()).abs().max()),
            'top1_agreement': float((left.argmax(-1) == right.argmax(-1)).float().mean())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--probe-output', required=True, type=Path)
    parser.add_argument('--upstream', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    dest = args.out.expanduser().resolve()
    if dest.is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error('Keep runtime evidence outside the Git checkout.')
    if dest.exists():
        parser.error('Preserve prior diagnostics; choose a new output file.')
    upstream = runner.load_upstream(args.upstream, runner.PINNED_UPSTREAM_COMMIT)
    run = runner.RunDir.open(args.run)
    config = run.config()
    runner.configure_threads(config)
    documents, token_map = runner.load_prepared(run)
    prior = runner.read_json(args.probe_output / 'receipt.json')
    if prior['dataset_fingerprint'] != run.dataset_fingerprint():
        raise runner.IdentityError('Probe and prepared run refer to different inputs.')
    document = next(doc for doc in documents if doc.index == prior['doc_index'])
    assert document.split == 'validation'
    tokens = token_map[document.index]
    past_ids, stride, past_positions = runner.capture_plan('validation', tokens, config)
    prefix, length = len(past_ids), int(config['seq_len'])
    fresh_ids, labels = tokens[prefix:length-1], tokens[prefix+1:length]
    fresh_positions = torch.arange(prefix, length-1)
    started = time.perf_counter()
    model, _ = runner.load_role_model(config, 'target')
    tokenizer_hash, tokenizer_kind = runner.resolve_tokenizer_identity(config['target'])
    identity = runner.describe_model(model, 'target', config['target'], tokenizer_hash,
                                     tokenizer_kind, config['dtype'])
    if identity.fingerprint != prior['model']['fingerprint']:
        raise runner.IdentityError('Diagnostic model differs from the original probe.')
    expected = runner.capture_identity('target', 'validation', document.index, past_ids,
                                      past_positions, stride, run.dataset_fingerprint(), identity.fingerprint)
    stored = runner.load_shard(runner.RunDir(args.probe_output), 'target', 'validation',
                               document.index, expected).native_cache(upstream)
    with torch.inference_mode():
        content, direct, _ = runner.capture_kv(model, past_ids, upstream)
        del content
        disk_vs_fresh = compare_cache(stored, direct)
        print('Captured fresh prefix and compared with saved raw cache.', flush=True)
        outputs = runner.run_branch(model, direct, fresh_ids, fresh_positions, length-1,
                                     upstream, with_queries=False)
        direct_logits = outputs['logits']
        del outputs, direct
        outputs = runner.run_branch(model, stored, fresh_ids, fresh_positions, length-1,
                                     upstream, with_queries=False)
        disk_logits = outputs['logits']
        del outputs
        same_split = logit_delta(direct_logits, disk_logits)
        disk_metrics = runner.continuation_metrics(disk_logits, disk_logits, labels, upstream,
                                                   first_label_index=prefix+1)
        del direct_logits
        print('Compared same-shape direct and disk continuation logits.', flush=True)
        full_ids = tokens[:length-1]
        full_positions = torch.arange(length-1).unsqueeze(0)
        full_mask = torch.ones((1, length-1), dtype=torch.long)
        outputs = model(input_ids=full_ids.unsqueeze(0), attention_mask=full_mask,
                        position_ids=full_positions, use_cache=True, return_dict=True)
        full_logits = outputs.logits[:, prefix:length-1].clone()
        full_prefix = prefix_from_output(outputs, prefix, upstream)
        del outputs
        prefix_shape = compare_cache(stored, full_prefix)
        full_vs_split = logit_delta(full_logits, disk_logits)
        full_nll = runner.log_softmax_nll(full_logits, labels)
        del full_logits
        print('Compared standalone-prefix and full-length prefix K/V.', flush=True)
        # Keep shape and the first 191 tokens; perturb only positions 191..254.
        perturbed = full_ids.clone()
        changed_tail = torch.roll(perturbed[prefix:], 1)
        if torch.equal(changed_tail, perturbed[prefix:]):
            changed_tail = (changed_tail + 1) % model.config.vocab_size
        perturbed[prefix:] = changed_tail
        assert torch.equal(perturbed[:prefix], full_ids[:prefix])
        assert not torch.equal(perturbed[prefix:], full_ids[prefix:])
        outputs = model(input_ids=perturbed.unsqueeze(0), attention_mask=full_mask,
                        position_ids=full_positions, use_cache=True, return_dict=True)
        future_prefix = prefix_from_output(outputs, prefix, upstream)
        del outputs
        prefix_future = compare_cache(full_prefix, future_prefix)
        # Use the full-prefill-derived prefix with the same 64-token suffix shape.
        outputs = runner.run_branch(model, full_prefix, fresh_ids, fresh_positions, length-1,
                                     upstream, with_queries=False)
        full_prefix_split = logit_delta(outputs['logits'], disk_logits)
        full_prefix_split_nll = runner.log_softmax_nll(outputs['logits'], labels)
        del outputs
    report = {
        'status': 'complete-measured', 'evidence_kind': 'native-cache-chunk-diagnostic',
        'run_evidence_kind': config['evidence_kind'], 'model': identity.to_dict(),
        'runner_code_sha256': runner.RUNNER_CODE_SHA256, 'runtime_versions': runner.RUNTIME_VERSIONS,
        'dataset_fingerprint': run.dataset_fingerprint(), 'doc_index': document.index,
        'split': 'validation', 'cached_tokens': prefix, 'fresh_tokens': len(fresh_ids),
        'disk_vs_fresh_capture': disk_vs_fresh, 'direct_vs_disk_same_split': same_split,
        'full255_vs_standalone191_prefix': prefix_shape,
        'full255_same_shape_future_prefix': prefix_future,
        'full_vs_disk_split_logits': full_vs_split,
        'full_prefix_split_vs_standalone_prefix_split_logits': full_prefix_split,
        'nll': {'disk_split': disk_metrics['nll'], 'full': full_nll,
                'full_prefix_split': full_prefix_split_nll},
        'disk_first_token': disk_metrics['first_token'],
        'elapsed_seconds': time.perf_counter()-started,
        'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                                 (1 if platform.system() == 'Darwin' else 1024),
        'scope': 'One document and fixed pretrained/random model as labelled. Discriminates disk reconstruction from different chunk-shape executions; does not identify a specific arithmetic kernel or measure transfer quality.',
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    runner.write_json_atomic(dest, report)
    print(runner.canonical_json(report))


if __name__ == '__main__':
    main()
