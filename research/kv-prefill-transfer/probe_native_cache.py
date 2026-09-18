#!/usr/bin/env python3
"""Measure one validation document's native disk/cache path before mapper fitting."""
import argparse
import math
from pathlib import Path
import platform
import resource
import time

import torch
import runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--run', type=Path)
    mode.add_argument('--random', action='store_true',
                      help='Build a tiny random BF16 Qwen fixture at the exact 191/64 cut.')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--upstream', required=True)
    args = parser.parse_args()
    output = args.out.expanduser().resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error('Use an output directory outside the Git checkout.')
    if output.exists() and any(output.iterdir()):
        parser.error('Use an empty output directory; preserve prior evidence.')
    upstream = runner.load_upstream(args.upstream, runner.PINNED_UPSTREAM_COMMIT)
    if args.random:
        fixture = output / 'fixture'
        models = runner.build_random_pair(fixture / 'models')
        config = runner.resolve_config({
            'evidence_kind': 'random-model-smoke',
            'source': models['source'], 'target': models['target'], 'dtype': 'bfloat16',
            'seq_len': 256, 'prefix_len': 192, 'stride': 4,
            'splits': {'train': 2, 'validation': 1, 'test': 1},
            'data': {'kind': 'synthetic', 'num_documents': 4, 'vocab_size': 128,
                     'min_tokens': 256, 'max_tokens': 256},
        })
        runner.phase_prepare(config, fixture / 'run', upstream)
        run_path = fixture / 'run'
    else:
        run_path = args.run
    prepared = runner.RunDir.open(run_path)
    config = prepared.config()
    runner.configure_threads(config)
    documents, token_map = runner.load_prepared(prepared)
    # Use validation, never consume the frozen test split for this implementation check.
    document = next(doc for doc in documents if doc.split == 'validation')
    tokens = token_map[document.index]
    prefix_len, seq_len = int(config['prefix_len']), int(config['seq_len'])
    capture_ids, stride, positions = runner.capture_plan('validation', tokens, config)
    fresh = tokens[prefix_len - 1:seq_len - 1]
    labels = tokens[prefix_len:seq_len]
    fresh_positions = torch.arange(prefix_len - 1, seq_len - 1)
    tokenizer = runner.read_json(prepared.path('prepare', 'receipt.json'))['tokenizer_identity']['target']
    tokenizer_hash, tokenizer_kind = runner.resolve_tokenizer_identity(config['target'])
    if (tokenizer_hash, tokenizer_kind) != (tokenizer['hash'], tokenizer['kind']):
        raise runner.IdentityError('Target tokenizer differs from the prepared input.')
    started = time.perf_counter()
    model, low_memory = runner.load_role_model(config, 'target')
    load_seconds = time.perf_counter() - started
    identity = runner.describe_model(model, 'target', config['target'], tokenizer_hash,
                                     tokenizer_kind, config['dtype'])
    expected = runner.capture_identity('target', 'validation', document.index, capture_ids,
                                      positions, stride, prepared.dataset_fingerprint(),
                                      identity.fingerprint)
    probe = runner.RunDir(output)
    shard, shard_receipt = runner.shard_paths(probe, 'target', 'validation', document.index)
    with torch.inference_mode():
        started = time.perf_counter()
        content, raw, roundtrip_diagnostics = runner.capture_kv(model, capture_ids, upstream)
        capture_seconds = time.perf_counter() - started
        runner.save_shard(shard, content, raw, capture_ids, positions, expected)
    runner.write_json_atomic(shard_receipt, {
        'status': 'complete', 'capture_dtype': config['dtype'],
        'shard_sha256': runner.sha256_file(shard), **expected,
    })
    del content, raw
    loaded = runner.load_shard(probe, 'target', 'validation', document.index, expected)
    with torch.inference_mode():
        started = time.perf_counter()
        native = runner.run_branch(model, loaded.native_cache(upstream), fresh,
                                   fresh_positions, seq_len - 1, upstream, with_queries=False)
        native_seconds = time.perf_counter() - started
        full = model(input_ids=tokens[:seq_len - 1].unsqueeze(0),
                     attention_mask=torch.ones((1, seq_len - 1), dtype=torch.long),
                     position_ids=torch.arange(seq_len - 1).unsqueeze(0),
                     use_cache=False, return_dict=True).logits[:, prefix_len - 1:seq_len - 1]
        factors = upstream.huggingface.capture_rotary_factors(model, positions.unsqueeze(0))
        roundtrip = runner.run_branch(model, loaded.content_rotated(upstream, factors), fresh,
                                      fresh_positions, seq_len - 1, upstream, with_queries=False)
        future_delta = runner.first_logit_future_invariance(
            model, loaded.native_cache(upstream), fresh, fresh_positions,
            native['logits'], upstream)
    assert native['logits'].shape == full.shape
    assert full.shape[1] == labels.numel() == seq_len - prefix_len
    native_metrics = runner.continuation_metrics(native['logits'], native['logits'], labels,
                                                 upstream, first_label_index=prefix_len)
    full_metrics = runner.continuation_metrics(full, native['logits'], labels, upstream,
                                               first_label_index=prefix_len)
    roundtrip_metrics = runner.continuation_metrics(roundtrip['logits'], native['logits'], labels,
                                                    upstream, first_label_index=prefix_len)
    max_delta = float((native['logits'].float() - full.float()).abs().max())
    assert math.isfinite(max_delta)
    report = {
        'status': 'complete-measured', 'evidence_kind': 'native-disk-cache-control',
        'run_evidence_kind': config['evidence_kind'],
        'model_origin': config['target']['origin'], 'model': identity.to_dict(),
        'upstream_commit': upstream.commit, 'dataset_fingerprint': prepared.dataset_fingerprint(),
        'doc_index': document.index, 'split': 'validation', 'seq_len': seq_len,
        'cached_tokens': len(capture_ids), 'fresh_tokens': len(fresh), 'labels': len(labels),
        'torch': torch.__version__, 'low_cpu_mem_usage': low_memory,
        'attention_backend': model.config._attn_implementation,
        'native_prefix_kind': 'raw-post-rope',
        'native_vs_full': {'max_abs_logit_delta': max_delta,
                           'nll_delta': native_metrics['nll'] - full_metrics['nll']},
        'first_logit_future_invariance': future_delta,
        'native': native_metrics, 'full': full_metrics, 'content_roundtrip': roundtrip_metrics,
        'capture_roundtrip_diagnostics': roundtrip_diagnostics,
        'load_seconds': load_seconds, 'capture_seconds': capture_seconds,
        'native_suffix_seconds': native_seconds,
        'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                                 (1 if platform.system() == 'Darwin' else 1024),
        'limitation': 'One target-native document; no source model, mapper fit, transfer-quality claim or speedup. Numerical deltas require inspection before a calibration run.',
    }
    runner.write_json_atomic(output / 'receipt.json', report)
    print(runner.canonical_json(report))


if __name__ == '__main__':
    main()
