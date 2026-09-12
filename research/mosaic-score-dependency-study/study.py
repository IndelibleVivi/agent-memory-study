#!/usr/bin/env python3
"""Exact synthetic score-cache comparisons motivated by MOSAIC Eq. (1)."""

from __future__ import annotations

import argparse
import json
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICIES = ("full", "graph-dirty", "dependency-aware")


def frontier(graph, state):
    """Recompute eligibility in every treatment; never test stale eligibility."""
    return sorted(v for v, node in state["nodes"].items()
                  if not node["resolved"] and all(
                      state["nodes"][u]["resolved"]
                      for u, target in graph["prerequisites"] if target == v))


def context(state, eligible):
    return (max(F(state["nodes"][v]["importance"]) for v in eligible),
            state["nodes"][state["previous"]]["community"])


def score_terms(state, v, eligible, weights):
    denominator, previous_community = context(state, eligible)
    node = state["nodes"][v]
    return {
        "importance": F(weights["alpha"]) * F(node["importance"]) / denominator,
        "centrality": F(weights["beta"]) * F(node["centrality"]),
        "continuity": F(weights["gamma"]) * (node["community"] == previous_community),
    }


def score(state, v, eligible, weights):
    return sum(score_terms(state, v, eligible, weights).values(), F(0))


def graph_dirty(graph, before, after):
    """U = changed nodes plus consumers of their directed graph edges."""
    changed = {v for v in before["nodes"] if before["nodes"][v] != after["nodes"][v]}
    edges = graph["association_edges"] + graph["prerequisites"]
    dirty = changed | {v for u, v in edges if u in changed}
    return changed, dirty


def rank(scores):
    return sorted(scores, key=lambda v: (-scores[v], v))


def evaluate(graph, weights, case):
    before, after = case["before"], case["after"]
    old_frontier, new_frontier = frontier(graph, before), frontier(graph, after)
    old_scores = {v: score(before, v, old_frontier, weights) for v in old_frontier}
    changed, dirty = graph_dirty(graph, before, after)
    global_change = context(before, old_frontier) != context(after, new_frontier)
    fresh = {v: score(after, v, new_frontier, weights) for v in new_frontier}
    outputs = {}
    for policy in POLICIES:
        if policy == "full" or (policy == "dependency-aware" and global_change):
            rescore = set(new_frontier)
        else:
            rescore = (dirty & set(new_frontier)) | (set(new_frontier) - set(old_scores))
        cached = {v: score(after, v, new_frontier, weights) if v in rescore else old_scores[v]
                  for v in new_frontier}
        order = rank(cached)
        outputs[policy] = {
            "rescored": sorted(rescore),
            "reused": sorted(set(new_frontier) - rescore),
            "scores": {v: str(cached[v]) for v in new_frontier},
            "ranking": order,
            "selected": order[0],
            "stale_nodes": [v for v in new_frontier if cached[v] != fresh[v]],
            "matches_full_scores": cached == fresh,
            "matches_full_choice": order[0] == rank(fresh)[0],
        }
    return {
        "id": case["id"],
        "changed_nodes": sorted(changed),
        "graph_dirty_nodes": sorted(dirty),
        "before_frontier": old_frontier,
        "after_frontier": new_frontier,
        "before_context": [str(x) for x in context(before, old_frontier)],
        "after_context": [str(x) for x in context(after, new_frontier)],
        "global_context_changed": global_change,
        "before_scores": {v: str(s) for v, s in old_scores.items()},
        "fresh_terms": {v: {k: str(s) for k, s in score_terms(after, v, new_frontier, weights).items()}
                        for v in new_frontier},
        "treatments": outputs,
    }


def run(data):
    rows = [evaluate(case.get("graph", data["graph"]), data["weights"], case)
            for case in data["cases"]]
    return {
        "schema": "ams-mosaic-score-study-v1",
        "source": data["source"],
        "scope": "AMS synthetic equation/cache study; no official implementation or benchmark execution",
        "inputs": data,
        "cases": rows,
        "summary": {
            "cases": len(rows),
            "after_state_treatments": len(rows) * len(POLICIES),
            "graph_dirty_score_mismatches": [r["id"] for r in rows if not r["treatments"]["graph-dirty"]["matches_full_scores"]],
            "graph_dirty_choice_mismatches": [r["id"] for r in rows if not r["treatments"]["graph-dirty"]["matches_full_choice"]],
            "dependency_aware_matches_all": all(r["treatments"]["dependency-aware"]["matches_full_scores"] for r in rows),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Rerun and compare all inputs, terms, scores and choices")
    parser.add_argument("--output", type=Path, default=ROOT / "results.json")
    args = parser.parse_args()
    result = run(json.loads((ROOT / "fixtures.json").read_text()))
    if args.check:
        if result != json.loads(args.output.read_text()):
            raise SystemExit("Results differ from fresh execution")
        print("Fresh execution matches all checked results")
    else:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
