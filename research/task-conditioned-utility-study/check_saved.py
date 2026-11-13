#!/usr/bin/env python3
"""Offline contract check of compact saved outputs, not replay of upstream rows.

No NumPy, network, upstream checkout, model, or retrieval service is used. Hashes
detect changed artifacts against this receipt; they do not authenticate authors,
prove an upstream execution history, or protect a jointly edited receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from figure_data import derive

UPSTREAM_COMMIT = "386ac65a8b5fc46414abdd2755375f2a52d4d3b8"
HF_REVISION = "332cd047e9093a948606c4251bf5b294b0664762"
UPSTREAM_INPUTS = {
    "primary": "7433b7806e5d9373ef4fe5c6653f284e82a7114114dca41b4f8520796c3aa951",
    "gptoss": "e7d6307404f6881ea6e5cac0120a0ae96ab5c8e711e978f9fa2ec6a9192e1cb9",
    "gemma": "f3223aee68d9ba673f8461fedfba9d5f9b5f5fed6c2585cf2d262824e5d3407e",
}
FIXED_INPUT = "d7a7309044ffb02aed7ddb786359939c51de12bf910a5825f3a6933ef651b033"
REQUIRED = {
    "README.md", "research-note.md", "source-notes.md", "reanalyze.py",
    "fetch_fixed_context.py", "check_saved.py", "figure_data.py", "test_saved.py",
    "plot_results.py", "results.json", "official_fixed_context.json",
    "official-headline-output.txt", "official-fixed-context-output.txt", "figure-data.json",
    "utility-opportunities.svg", "utility-opportunities.png",
}


class ContractError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ContractError(message)


def read_json(path):
    return json.loads(path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ContractError(f"Invalid JSON number: {value}")))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a, b, label):
    require(isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isfinite(a) and math.isfinite(b) and abs(a-b) < 1e-10, label)


def check_interval(value, low=-1, high=1):
    require(isinstance(value, list) and len(value) == 2, "Malformed interval")
    require(all(isinstance(x, (int, float)) and math.isfinite(x) for x in value), "Nonfinite interval")
    require(low <= value[0] <= value[1] <= high, "Invalid interval bounds")


def check_transitions(value):
    names = ["baseline_wrong_stays_wrong", "helped", "baseline_correct_stays_correct", "harmed"]
    require(all(type(value[key]) is int and value[key] >= 0 for key in names), "Invalid transition count")
    n = value["n_cells"]
    require(type(n) is int and n > 0 and sum(value[key] for key in names) == n, "Transition total mismatch")
    wrong = value[names[0]] + value["helped"]
    correct = value[names[2]] + value["harmed"]
    require(wrong == value["help_opportunities"] and correct == value["harm_opportunities"], "Opportunity denominator mismatch")
    require(wrong > 0 and correct > 0, "This saved study requires both opportunity types")
    p, h, e = correct/n, value["helped"]/wrong, value["harmed"]/correct
    close(value["baseline_correctness_p"], p, "Incorrect baseline correctness")
    close(value["with_memory_accuracy"], (value[names[2]]+value["helped"])/n, "Incorrect with-memory correctness")
    close(value["help_given_wrong_h"], h, "Incorrect conditional help")
    close(value["harm_given_correct_e"], e, "Incorrect conditional harm")
    close(value["mean_delta"], (value["helped"]-value["harmed"])/n, "Incorrect paired change")
    close(value["identity_reconstruction"], (1-p)*h-p*e, "Opportunity identity mismatch")
    close(value["hypothetical_zero_cost_threshold_p"], h/(h+e), "Hypothetical threshold mismatch")
    for q, effect in value["hypothetical_standardised_delta_at_p"].items():
        close(effect, (1-float(q))*h-float(q)*e, "Hypothetical standardisation mismatch")
    for interval in value.get("conditional_harm_uncertainty", []):
        check_interval(interval["percentile_95"], 0, 1)
        require(0 < interval["defined_resamples"] <= interval["resamples"], "Undefined bootstrap draws silently counted")


def check(root):
    root = root.resolve()
    receipt = read_json(root/"receipt.json")
    require(receipt["schema"] == "ams-task-conditioned-utility-receipt/1", "Unknown receipt schema")
    require(receipt["evidence_kind"] == "secondary_analysis_of_archived_model_outputs", "Incorrect evidence kind")
    require(receipt["new_model_inference"] is False, "Cannot label saved analysis as new inference")
    require(receipt["offline_check"]["upstream_row_replay"] is False, "Offline contract check must not claim upstream replay")
    require(receipt["offline_check"]["confidence_intervals_recomputed"] is False, "Saved check does not recompute confidence intervals")
    require(receipt["upstream_repository"]["commit"] == UPSTREAM_COMMIT, "Upstream version drift")
    require(receipt["fixed_context_input"]["revision"] == HF_REVISION and receipt["fixed_context_input"]["sha256"] == FIXED_INPUT, "Fixed-context source drift")
    bound = receipt["artifacts"]
    require(set(bound) == REQUIRED, "Receipt must bind exactly the documented public artifact set")
    for relative, digest in bound.items():
        path = (root/relative).resolve()
        require(path.parent == root and path.is_file(), "Missing or escaping artifact")
        require(sha(path) == digest, f"Artifact changed: {relative}")
    results = read_json(root/"results.json")
    require(results["schema"] == "ams-task-conditioned-utility-results/1", "Unknown results schema")
    require(results["new_model_inference"] is False and results["new_empirical_natural_world_sampling"] is False, "Evidence promotion")
    require(results["upstream_commit"] == UPSTREAM_COMMIT, "Results from another upstream version")
    require(results["analysis_script_sha256"] == sha(root/"reanalyze.py"), "Analysis source/result identity mismatch")
    inputs = {row["name"]: row["sha256"] for row in results["inputs"]}
    require(inputs == UPSTREAM_INPUTS, "Public input identity mismatch")
    require(inputs == receipt["upstream_input_sha256"], "Receipt/result input identities differ")
    integrity = results["integrity"]["primary"]
    require((integrity["rows"], integrity["unique_cells"], integrity["excluded_missing_rows"]) == (2599, 1157, 0), "Primary archive counts differ")
    require(sum(int(k)*v for k, v in integrity["replicates_per_cell"].items()) == integrity["rows"], "Replicate-row accounting mismatch")
    require(sum(integrity["replicates_per_cell"].values()) == integrity["unique_cells"], "Replicate-cell accounting mismatch")
    require(set(results["strata"]) == {"BEARING", "MATCHED_CONTROL", "RANDOM"}, "Unexpected design strata")
    for value in results["strata"].values():
        check_transitions(value)
    require(sum(v["n_cells"] for v in results["strata"].values()) == 1157, "Stratum count mismatch")
    contrasts = results["memory_contrasts"]
    require(len(contrasts) == len({x["memory"] for x in contrasts}) == 60, "Memory contrast identities differ")
    require(len({x["episode"] for x in contrasts}) == 35, "Episode count mismatch")
    close(sum(x["value"] for x in contrasts)/len(contrasts), results["headline"]["memory_weighted_bearing_minus_control"], "Headline mean differs from compact per-memory estimates")
    for interval in results["headline"]["confidence_intervals"]:
        check_interval(interval["percentile_95"])
    transfer = results["reader_transfer"]
    require(transfer["paired_cells"] == transfer["gptoss"]["n_cells"] == transfer["gemma"]["n_cells"] == 275, "Reader sample pairing differs")
    check_transitions(transfer["gptoss"])
    check_transitions(transfer["gemma"])
    close(transfer["mean_gemma_minus_gptoss_delta"], transfer["gemma"]["mean_delta"]-transfer["gptoss"]["mean_delta"], "Reader contrast mismatch")
    check_interval(transfer["task_clustered_interval"]["percentile_95"])
    graph = results["additivity_diagnostic"]
    require(graph["design_rank"] == graph["memories"]+graph["tasks"]-graph["components"], "Graph rank identity mismatch")
    require(graph["cycle_space_dimension"] == graph["edges"]-graph["design_rank"], "Graph dimension identity mismatch")
    require(sum(graph["four_cycle_sums"].values()) == graph["four_cycles_total"], "Cycle accounting mismatch")
    require(graph["four_cycles_total"]-graph["four_cycle_sums"]["0.0"] == graph["four_cycles_nonzero"], "Nonzero-cycle accounting mismatch")
    witness = graph["witness"]
    require(len(witness["cells"]) == 4, "Cycle witness must have four cells")
    for cell in witness["cells"]:
        close(cell["delta"], cell["with"]-cell["baseline"], "Witness transition mismatch")
    close(witness["alternating_sum"], sum(sign*cell["delta"] for sign, cell in zip([1,-1,-1,1], witness["cells"])), "Cycle witness mismatch")
    fixed = read_json(root/"official_fixed_context.json")
    require(fixed["n_cells_total"] == 277 and fixed["n_exposed_pairs"] == 63, "Fixed-context counts differ")
    for name, n in (("excluding_exposed", 77), ("including_exposed", 135)):
        section = fixed[name]
        require(section["n_bearing_cells"] == n, "Fixed-context exclusion count differs")
        for estimate in list(section["arms"].values())+list(section["contrasts"].values()):
            require(estimate["n"] == n, "Unpaired fixed-context estimate")
            check_interval(estimate["ci95"])
        for arm in ("summary", "structured", "trunc_last_matched"):
            close(section["contrasts"][arm+"_minus_raw"]["mean"], section["arms"][arm]["mean"]-section["arms"]["raw"]["mean"], "Fixed-context paired contrast mismatch")
    require(read_json(root/"figure-data.json") == derive(results, fixed), "Figure data no longer agrees with compact summaries")
    require("VERDICT: REPRODUCED" in (root/"official-headline-output.txt").read_text(), "Official headline output lacks success verdict")
    require("VERDICT: COUNTS_MATCH_PAPER" in (root/"official-fixed-context-output.txt").read_text(), "Fixed-context output lacks counts verdict")
    require(all(run["exit_code"] == 0 for run in receipt["executed_analyses"]), "An analysis did not complete")
    return {"status": "passed", "scope": "saved_artifact_identity_and_algebra",
            "upstream_rows_replayed": False, "new_model_inference": False,
            "confidence_intervals_recomputed": False, "figures_rerendered": False,
            "artifacts_checked": len(bound), "cells_described": 1157,
            "warning": "This offline gate validates the saved public package; rerun reanalyze.py with the pinned upstream checkout to recompute archived outcome statistics."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        result = check(args.root)
    except (KeyError, ValueError, OSError, TypeError) as error:
        raise SystemExit(f"Saved artifact check failed: {error}")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
