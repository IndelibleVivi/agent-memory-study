#!/usr/bin/env python3
"""Tensor-only 1024-wide ridge probe; no model or transfer-quality evidence."""
import argparse
import json
import platform
import resource
import time
from pathlib import Path
import torch
from runner import load_upstream, PINNED_UPSTREAM_COMMIT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    upstream = load_upstream(args.upstream, PINNED_UPSTREAM_COMMIT)
    generator = torch.Generator().manual_seed(260803893)
    acc = upstream.RidgeAccumulator(1024, 1024, dtype=torch.float64)
    started = time.perf_counter()
    row_counts, shapes = [], []
    for _ in range(4):
        x = torch.randn(64, 1024, dtype=torch.float64, generator=generator)
        y = .5 * x.roll(1, dims=1) + .1
        acc.update(x, y)
        row_counts.append(acc.count)
        shapes.append({name: list(value.shape) for name,value in vars(acc).items()
                       if isinstance(value, torch.Tensor)})
    del x, y
    assert all(shape == shapes[0] for shape in shapes)
    accumulation_seconds = time.perf_counter() - started
    solution = acc.solve(.01)
    assert solution.observations == 256
    assert solution.weight.shape == (1024,1024)
    assert bool(torch.isfinite(solution.weight).all())
    report = dict(evidence_kind='tensor-only-memory-probe', upstream_commit=upstream.commit,
                  torch=torch.__version__, threads=1, accumulation_dtype='float64',
                  feature_width=1024, output_width=1024, batch_rows=64,
                  observation_counts=row_counts, persistent_tensor_shapes=shapes[0],
                  persistent_shapes_unchanged=True, accumulation_seconds=accumulation_seconds,
                  total_seconds=time.perf_counter()-started,
                  peak_process_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                    (1 if platform.system()=='Darwin' else 1024),
                  limitation='One K or V accumulator/solve at k=1; not full runner/model RSS, quality, or VPS timing.')
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
