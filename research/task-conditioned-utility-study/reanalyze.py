#!/usr/bin/env python3
"""Reanalyse public paired outcomes. No model, retriever, or paid API is called.

All empirical numbers refer to the archived upstream execution. The opportunity
standardisation and additive-cycle calculation are new analyses of those records.
They are descriptive, conditional on the constructed design, and cannot establish
a population harm rate or a semantic cause of an observed interaction.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np


UPSTREAM_SHA = "386ac65a8b5fc46414abdd2755375f2a52d4d3b8"
INPUTS = {
    "primary": ("results/ledgers/repro/screened_cells_slim.jsonl", "7433b7806e5d9373ef4fe5c6653f284e82a7114114dca41b4f8520796c3aa951"),
    "gptoss": ("results/ledgers/repro/raw_session_matched/raw_gptoss_slim.jsonl", "e7d6307404f6881ea6e5cac0120a0ae96ab5c8e711e978f9fa2ec6a9192e1cb9"),
    "gemma": ("results/ledgers/repro/raw_session_matched/raw_gemma_slim.jsonl", "f3223aee68d9ba673f8461fedfba9d5f9b5f5fed6c2585cf2d262824e5d3407e"),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def valid_binary(x):
    return isinstance(x, (int, float)) and math.isfinite(x) and x in (0.0, 1.0)


def aggregate(rows):
    """Deduplicate replicates before analysis; reject inconsistent binary pairs.

    The present archive is deterministic within its original session. Refusing to
    collapse non-identical replicates keeps the transition analysis honest if a
    future archive changes that property. Missing pairs are excluded, not zeroed.
    """
    grouped = collections.defaultdict(list)
    excluded = 0
    for r in rows:
        w, b = r.get("reward_with_memory"), r.get("reward_without_memory")
        if w is None or b is None or (isinstance(w, float) and math.isnan(w)) or (isinstance(b, float) and math.isnan(b)):
            excluded += 1
            continue
        if not valid_binary(w) or not valid_binary(b):
            raise ValueError("Transition analysis requires finite binary rewards")
        key = r["memory_id"], r["future_task_id"]
        grouped[key].append(r)
    cells = []
    for (m, t), group in sorted(grouped.items()):
        transitions = {(r["reward_without_memory"], r["reward_with_memory"]) for r in group}
        if len(transitions) != 1:
            raise ValueError(f"Non-identical within-cell outcomes: {(m, t)}; extend the estimand before reuse")
        strata = {r.get("stratum", "unspecified") for r in group}
        if len(strata) != 1:
            raise ValueError("Conflicting design strata")
        b, w = next(iter(transitions))
        cells.append({"memory": m, "task": t, "episode": m.split("-")[1],
                      "stratum": next(iter(strata)), "baseline": int(b), "with": int(w),
                      "delta": float(w - b), "replicates": len(group)})
    return cells, {"rows": len(rows), "excluded_missing_rows": excluded,
                   "unique_cells": len(cells),
                   "replicates_per_cell": dict(sorted(collections.Counter(x["replicates"] for x in cells).items()))}


def transitions(cells):
    n = len(cells)
    counts = collections.Counter((c["baseline"], c["with"]) for c in cells)
    help_n = counts[(0, 1)]
    harm_n = counts[(1, 0)]
    wrong = counts[(0, 0)] + help_n
    correct = counts[(1, 1)] + harm_n
    h = help_n / wrong if wrong else None
    e = harm_n / correct if correct else None
    p = correct / n if n else None
    mean = (help_n - harm_n) / n if n else None
    recon = ((1 - p) * h - p * e) if h is not None and e is not None else None
    if recon is not None and abs(recon - mean) > 1e-12:
        raise AssertionError("Opportunity identity failed")
    return {
        "n_cells": n, "baseline_wrong_stays_wrong": counts[(0, 0)],
        "helped": help_n, "baseline_correct_stays_correct": counts[(1, 1)], "harmed": harm_n,
        "baseline_correctness_p": p, "with_memory_accuracy": sum(c["with"] for c in cells) / n,
        "help_opportunities": wrong, "harm_opportunities": correct,
        "help_given_wrong_h": h, "harm_given_correct_e": e,
        "mean_delta": mean, "identity_reconstruction": recon,
        "hypothetical_zero_cost_threshold_p": h / (h + e) if h is not None and e is not None and h + e else None,
        "hypothetical_standardised_delta_at_p": {
            str(q): (1 - q) * h - q * e for q in (0.1, 0.5, 0.8, 0.95)
        } if h is not None and e is not None else None,
    }


def cluster_interval(cells, statistic, cluster_key, n_boot, seed):
    groups = collections.defaultdict(list)
    for c in cells:
        groups[c[cluster_key]].append(c)
    keys = sorted(groups)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n_boot):
        draw = rng.integers(0, len(keys), size=len(keys))
        sample = [c for i in draw for c in groups[keys[i]]]
        v = statistic(sample)
        if v is not None and math.isfinite(v):
            values.append(v)
    interval = list(map(float, np.percentile(values, [2.5, 97.5]))) if values else None
    return {"cluster": cluster_key, "clusters": len(keys), "resamples": n_boot,
            "defined_resamples": len(values), "seed": seed, "percentile_95": interval}


def memory_contrasts(cells):
    acc = collections.defaultdict(lambda: collections.defaultdict(list))
    for c in cells:
        acc[c["memory"]][c["stratum"]].append(c["delta"])
    return [{"memory": m, "episode": m.split("-")[1],
             "value": float(np.mean(d["BEARING"]) - np.mean(d["MATCHED_CONTROL"]))}
            for m, d in sorted(acc.items()) if d["BEARING"] and d["MATCHED_CONTROL"]]


def additive_cycles(cells):
    """Exact algebraic diagnostic, not a statistical semantic-interaction test.

    On the observed memory-task bipartite graph, an edge function can be written
    as a_m+b_t iff every alternating cycle sum vanishes. Four-cycles alone can
    refute this claim but need not characterise graphs with longer cycles.
    """
    memory_ids = sorted({c["memory"] for c in cells})
    task_ids = sorted({c["task"] for c in cells})
    mi = {m: i for i, m in enumerate(memory_ids)}
    ti = {t: i for i, t in enumerate(task_ids)}
    X = np.zeros((len(cells), len(memory_ids) + len(task_ids)))
    y = np.array([c["delta"] for c in cells])
    adjacency = collections.defaultdict(set)
    by_memory = collections.defaultdict(dict)
    for i, c in enumerate(cells):
        X[i, mi[c["memory"]]] = 1
        X[i, len(memory_ids) + ti[c["task"]]] = 1
        a, b = "m:" + c["memory"], "t:" + c["task"]
        adjacency[a].add(b)
        adjacency[b].add(a)
        by_memory[c["memory"]][c["task"]] = c
    unvisited = set(adjacency)
    components = 0
    while unvisited:
        components += 1
        stack = [unvisited.pop()]
        while stack:
            for v in adjacency[stack.pop()]:
                if v in unvisited:
                    unvisited.remove(v)
                    stack.append(v)
    coef, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    error = y - X @ coef
    rank_expected = len(adjacency) - components
    if rank != rank_expected:
        raise AssertionError("Bipartite incidence rank identity failed")
    count = collections.Counter()
    witness = None
    for a, b in itertools.combinations(memory_ids, 2):
        shared = sorted(set(by_memory[a]) & set(by_memory[b]))
        for t, u in itertools.combinations(shared, 2):
            four = [by_memory[a][t], by_memory[a][u], by_memory[b][t], by_memory[b][u]]
            z = four[0]["delta"] - four[1]["delta"] - four[2]["delta"] + four[3]["delta"]
            count[float(z)] += 1
            if z and witness is None:
                witness = {"alternating_sum": float(z), "cells": four}
    return {"memories": len(memory_ids), "tasks": len(task_ids), "edges": len(cells),
            "components": components, "design_rank": int(rank),
            "cycle_space_dimension": len(cells) - int(rank),
            "residual_sum_squares": float(error @ error),
            "total_sum_squares": float(((y - y.mean()) ** 2).sum()),
            "four_cycle_sums": {str(k): count[k] for k in sorted(count)},
            "four_cycles_total": sum(count.values()), "four_cycles_nonzero": sum(v for k, v in count.items() if k != 0),
            "witness": witness,
            "interpretation": "The archived condition-specific edge values violate the exact additive restriction. This does not identify semantic interaction, a random-effects variance share, or population prevalence. Position and baseline opportunity remain possible contributors. Overlapping cycles are not independent observations."}


def self_checks():
    # A sign flip can occur under a fully additive function; cycles must stay zero.
    additive = [{"memory": m, "task": t, "delta": a + b} for m, a in (("m1", -0.2), ("m2", 0.2)) for t, b in (("t1", -0.5), ("t2", 0.5))]
    out = additive_cycles(additive)
    assert out["four_cycles_nonzero"] == 0
    assert out["residual_sum_squares"] < 1e-20
    # An arbitrary edge perturbation, including a hypothetical position effect,
    # violates additivity without establishing any semantic memory effect.
    changed = [dict(c) for c in additive]
    changed[0]["delta"] += 0.4
    assert additive_cycles(changed)["four_cycles_nonzero"] == 1
    # More archived copies of a call do not create new memory-task cells.
    row = {"memory_id": "mem-episode-unit", "future_task_id": "t", "stratum": "RANDOM", "reward_without_memory": 0, "reward_with_memory": 1}
    assert aggregate([row])[0][0]["delta"] == aggregate([row, row, row])[0][0]["delta"]
    assert aggregate([dict(row, reward_with_memory=None)])[1]["excluded_missing_rows"] == 1
    try:
        aggregate([row, dict(row, reward_with_memory=0)])
    except ValueError:
        pass
    else:
        raise AssertionError("Inconsistent replicates must not be hidden")
    return {"additive_sign_flip_negative_control": "passed", "edge_perturbation_positive_control": "passed", "replicate_deduplication": "passed", "missingness_exclusion": "passed", "inconsistent_replicate_rejection": "passed"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--upstream", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--bootstrap", type=int, default=10000)
    p.add_argument("--seed", type=int, default=20261113)
    a = p.parse_args()
    if a.bootstrap < 100:
        raise SystemExit("Use at least 100 resamples")
    root = a.upstream.resolve()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if head != UPSTREAM_SHA:
        raise SystemExit(f"Expected pinned upstream {UPSTREAM_SHA}, found {head}")
    provenance = []
    all_cells = {}
    audits = {}
    for name, (rel, expected) in INPUTS.items():
        path = root / rel
        got = digest(path)
        if got != expected:
            raise SystemExit(f"Input changed: {rel}")
        all_cells[name], audits[name] = aggregate(read_rows(path))
        provenance.append({"name": name, "upstream_path": rel, "sha256": got, "bytes": path.stat().st_size})
    primary = all_cells["primary"]
    contrasts = memory_contrasts(primary)
    headline = float(np.mean([v["value"] for v in contrasts]))
    if abs(headline - 0.3348611111111111) > 1e-12:
        raise AssertionError("Headline mismatch")
    summaries = {}
    for s in ("BEARING", "MATCHED_CONTROL", "RANDOM"):
        sub = [c for c in primary if c["stratum"] == s]
        result = transitions(sub)
        result["conditional_harm_uncertainty"] = [
            cluster_interval(sub, lambda x: transitions(x)["harm_given_correct_e"], key, a.bootstrap, a.seed)
            for key in ("task", "memory", "episode")
        ]
        summaries[s] = result
    keys = [{(c["memory"], c["task"]) for c in all_cells[k]} for k in ("gptoss", "gemma")]
    common = keys[0] & keys[1]
    pair = {name: [c for c in all_cells[name] if (c["memory"], c["task"]) in common] for name in ("gptoss", "gemma")}
    reader_difference = [{"task": c["task"], "memory": c["memory"], "episode": c["episode"], "value": b["delta"] - c["delta"]} for c, b in zip(pair["gptoss"], pair["gemma"], strict=True)]
    output = {
        "schema": "ams-task-conditioned-utility-results/1",
        "kind": "secondary_analysis_of_archived_model_outcomes",
        "new_model_inference": False,
        "new_empirical_natural_world_sampling": False,
        "upstream_repository": "https://github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory",
        "upstream_commit": head,
        "analysis_script_sha256": digest(__file__),
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "inputs": provenance, "integrity": audits, "method_self_checks": self_checks(),
        "headline": {"memory_weighted_bearing_minus_control": headline, "memory_count": len(contrasts),
                     "confidence_intervals": [cluster_interval(contrasts, lambda x: float(np.mean([r["value"] for r in x])), key, a.bootstrap, a.seed) for key in ("memory", "episode")]},
        "memory_contrasts": contrasts,
        "strata": summaries,
        "reader_transfer": {"paired_cells": len(common), "gptoss": transitions(pair["gptoss"]), "gemma": transitions(pair["gemma"]),
                            "mean_gemma_minus_gptoss_delta": float(np.mean([r["value"] for r in reader_difference])),
                            "task_clustered_interval": cluster_interval(reader_difference, lambda x: float(np.mean([r["value"] for r in x])), "task", a.bootstrap, a.seed)},
        "additivity_diagnostic": additive_cycles(primary),
        "limitations": ["The task population was constructed and answer-bearing memories oversampled.",
                        "Hypothetical standardisation holds help and harm rates fixed and is not a forecast of stronger models.",
                        "No primary placebo arm isolates semantic content from insertion/position perturbations.",
                        "Cluster bootstrap intervals describe sensitivity under each chosen clustering, not a natural deployment population.",
                        "The additive diagnostic is algebraic and conditioned on archived placement; no causal variance share is estimated."]
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"out": str(a.out), "headline": headline, "cells": len(primary), "reader_paired_cells": len(common), "four_cycles_nonzero": output["additivity_diagnostic"]["four_cycles_nonzero"], "method_self_checks": output["method_self_checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
