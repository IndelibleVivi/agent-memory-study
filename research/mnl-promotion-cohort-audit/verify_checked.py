#!/usr/bin/env python3
"""Verify the checked MNL audit receipts, optionally against exact source."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
COMMIT = "dc7de755522ad58864c62b74ab8e9959c01b7f23"
PAPER_SHA256 = "39137385c4e96bd83bfc0dfc4363733d0c91107a605999e074e5681065335c9c"
PRIMARY = (
    "cases.json", "run_results.jsonl", "decision.json",
    "source_manifest.json", "mutation_controls.json", "public_safety.json",
)
RAW_SET = set(PRIMARY) | {"comparison.json", "environment_run_a.json", "environment_run_b.json"}
ROOT_SET = {"README.md", "PROTOCOL.md", "audit.py", "verify_checked.py", "checksums.sha256", "raw"}
SOURCE_HASHES = {
    "mnl/trainer.py": "398ef9fc98ef418454cc3c243c762a65ee733cf687b94c16e80b92a6b4ce6033",
    "mnl/evaluator.py": "47d429f2962b0423ce2a48dfaf3910d5ce2efcaacc9e69018912b3a963a90347",
    "mnl/knowledge_base.py": "c4a62fd6b47b8ca4bd6a8265b1d218fedd3e67f5cdd52a27668ef89fd64116c5",
}
SOURCE_BLOBS = {
    "mnl/trainer.py": "2a39b9d8921760476b3f2ae2f2d1397fcadb163a",
    "mnl/evaluator.py": "be97b6e6da5157e1e7c3501961b6fad4b7d2a542",
    "mnl/knowledge_base.py": "50483b9a18d97ef743993644f657f982a95a3d59",
}


def frozen_item(item_id: str, outcome: str, *, group: str = "all", prompt: str = "nonempty", updated: str = "value") -> dict[str, str]:
    return {
        "group": group,
        "id": item_id,
        "observed_outcome_if_evaluated": outcome,
        "updated_prompt": prompt,
        "updated_response": updated,
    }


def frozen_cases() -> dict[str, Any]:
    batches = [
        {
            "id": "complete_positive_accept", "expected_source_acceptance": True,
            "items": [
                frozen_item("cpa-01", "win"), frozen_item("cpa-02", "win"),
                frozen_item("cpa-03", "win"), frozen_item("cpa-04", "loss"),
            ],
        },
        {
            "id": "complete_balanced_reject", "expected_source_acceptance": False,
            "items": [
                frozen_item("cbr-01", "win"), frozen_item("cbr-02", "win"),
                frozen_item("cbr-03", "loss"), frozen_item("cbr-04", "loss"),
            ],
        },
        {
            "id": "complete_all_ties_reject", "expected_source_acceptance": False,
            "items": [
                frozen_item("ctr-01", "tie"), frozen_item("ctr-02", "tie"),
                frozen_item("ctr-03", "tie"),
            ],
        },
        {
            "id": "partial_updated_none_survivor_accept", "expected_source_acceptance": True,
            "items": [
                frozen_item("pun-01", "win"), frozen_item("pun-02", "win"),
                frozen_item("pun-03", "unavailable", updated="none"),
                frozen_item("pun-04", "unavailable", updated="none"),
            ],
        },
        {
            "id": "partial_empty_prompt_survivor_accept", "expected_source_acceptance": True,
            "items": [
                frozen_item("pep-01", "win"), frozen_item("pep-02", "win"),
                frozen_item("pep-03", "unavailable", prompt="empty", updated="not_called"),
                frozen_item("pep-04", "unavailable", prompt="empty", updated="not_called"),
            ],
        },
        {
            "id": "all_updated_prompts_empty_rollback", "expected_source_acceptance": False,
            "items": [
                frozen_item("ape-01", "unavailable", prompt="empty", updated="not_called"),
                frozen_item("ape-02", "unavailable", prompt="empty", updated="not_called"),
                frozen_item("ape-03", "unavailable", prompt="empty", updated="not_called"),
            ],
        },
        {
            "id": "all_updated_responses_none_rollback", "expected_source_acceptance": False,
            "items": [
                frozen_item("arn-01", "unavailable", updated="none"),
                frozen_item("arn-02", "unavailable", updated="none"),
                frozen_item("arn-03", "unavailable", updated="none"),
            ],
        },
        {
            "id": "net_accept_with_group_loss", "expected_source_acceptance": True,
            "items": [
                frozen_item("ngl-01", "win", group="A"),
                frozen_item("ngl-02", "win", group="A"),
                frozen_item("ngl-03", "win", group="A"),
                frozen_item("ngl-04", "loss", group="B"),
            ],
        },
    ]
    return {
        "batch_cases": batches,
        "probes": [
            {
                "expected": "append_two_entries_old_entry_top1",
                "id": "exact_subject_equal_embedding_top1",
                "kind": "knowledge_base",
            },
            {
                "expected": "source_accuracy_1_enrolled_coverage_half",
                "id": "all_failed_question_denominator",
                "kind": "evaluation_coverage",
            },
            {
                "expected": "zero_attempts",
                "id": "socket_network_guard",
                "kind": "runtime_guard",
            },
        ],
        "schema": "mnl-promotion-cases/1",
    }


class VerificationFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected JSON object: {path.name}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        require(bool(line), f"blank JSONL row: {index}")
        value = json.loads(line)
        require(isinstance(value, dict), f"expected JSONL object: {index}")
        rows.append(value)
    return rows


def verify_checksums() -> None:
    expected = sorted(
        ["README.md", "PROTOCOL.md", "audit.py", "verify_checked.py"]
        + [f"raw/{name}" for name in sorted(RAW_SET)]
    )
    observed: dict[str, str] = {}
    for line in (ROOT / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        require(bool(separator) and len(digest) == 64, "malformed checksum row")
        require(relative not in observed, f"duplicate checksum row: {relative}")
        observed[relative] = digest
    require(sorted(observed) == expected, "checksum file inventory changed")
    for relative, digest in observed.items():
        require(sha256(ROOT / relative) == digest, f"checksum mismatch: {relative}")


def index_results(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed = {}
    for row in rows:
        key = (row.get("kind"), row.get("case_id", row.get("id")))
        require(key not in indexed, f"duplicate result: {key}")
        indexed[key] = row
    return indexed


def verify_batch(spec: dict[str, Any], row: dict[str, Any]) -> None:
    original = [item["id"] for item in spec["items"]]
    prompt_valid = [item["id"] for item in spec["items"] if item["updated_prompt"] == "nonempty"]
    response_valid = [
        item["id"] for item in spec["items"]
        if item["updated_prompt"] == "nonempty" and item["updated_response"] != "none"
    ]
    dispositions = {}
    for item in spec["items"]:
        if item["id"] in response_valid:
            dispositions[item["id"]] = f"observed_{item['observed_outcome_if_evaluated']}"
        elif item["updated_prompt"] == "empty":
            dispositions[item["id"]] = "filtered_empty_updated_prompt"
        else:
            dispositions[item["id"]] = "updated_response_unavailable"
    ledger = row["identity_ledger"]
    require(ledger["original_ids"] == original, f"original cohort drift: {spec['id']}")
    require(ledger["baseline_valid_ids"] == original, f"baseline cohort drift: {spec['id']}")
    require(ledger["updated_prompt_nonempty_ids"] == prompt_valid, f"prompt cohort drift: {spec['id']}")
    require(ledger["updated_generation_ids"] == prompt_valid, f"generation cohort drift: {spec['id']}")
    require(ledger["updated_response_valid_ids"] == response_valid, f"response cohort drift: {spec['id']}")
    require(ledger["evaluated_ids"] == response_valid, f"evaluated cohort drift: {spec['id']}")
    require(ledger["dispositions"] == dispositions, f"disposition drift: {spec['id']}")

    outcomes = [
        item["observed_outcome_if_evaluated"] for item in spec["items"] if item["id"] in response_valid
    ]
    wins, losses, ties = outcomes.count("win"), outcomes.count("loss"), outcomes.count("tie")
    missing = len(original) - len(response_valid)
    admission = row["admission"]
    require(admission["source_observed_wins"] == wins, f"win count drift: {spec['id']}")
    require(admission["source_observed_losses"] == losses, f"loss count drift: {spec['id']}")
    require(admission["source_observed_ties"] == ties, f"tie count drift: {spec['id']}")
    require(admission["source_observed_delta"] == wins - losses, f"delta drift: {spec['id']}")
    require(admission["source_accepted"] is spec["expected_source_acceptance"], f"admission drift: {spec['id']}")
    expected_full = ("ACCEPT" if wins - losses > 0 else "REJECT") if missing == 0 else "UNDEFINED_FROM_OBSERVED_RESULTS"
    require(admission["full_enrolled_decision"] == expected_full, f"full decision drift: {spec['id']}")
    sensitivity = row["missing_as_failure_sensitivity"]
    require(sensitivity["missing_count"] == missing, f"missing count drift: {spec['id']}")
    require(sensitivity["counterfactual_delta"] == wins - losses - missing, f"sensitivity drift: {spec['id']}")
    require(sensitivity["not_observed_source_outcomes"] is True, f"sensitivity label drift: {spec['id']}")

    kb = row["kb_state"]
    if spec["expected_source_acceptance"]:
        require(row["source_return"] == "METRICS", f"accepted return drift: {spec['id']}")
        require(kb["in_memory_delta"] == 1 and kb["accepted_entry_exact"], f"accepted KB delta drift: {spec['id']}")
        require(kb["in_memory_post_sha256"] != kb["in_memory_pre_sha256"], f"accepted memory unchanged: {spec['id']}")
        require(kb["serialized_post_sha256"] != kb["serialized_pre_sha256"], f"accepted serialization unchanged: {spec['id']}")
    else:
        require(row["source_return"] == "NONE", f"rejected return drift: {spec['id']}")
        require(kb["in_memory_delta"] == 0, f"rejected KB delta drift: {spec['id']}")
        require(kb["in_memory_post_sha256"] == kb["in_memory_pre_sha256"], f"rejected memory drift: {spec['id']}")
        require(kb["serialized_post_sha256"] == kb["serialized_pre_sha256"], f"rejected serialization drift: {spec['id']}")
    require(kb["serialized_matches_in_memory"] is True, f"memory/serialization split: {spec['id']}")


def verify_kb_probe(row: dict[str, Any]) -> None:
    require(row["entry_count_before"] == 1 and row["entry_count_after"] == 2, "exact-subject append count changed")
    require(row["exact_subject_count_after"] == 2, "same-subject count changed")
    require(row["top1_guidance"] == "older-guidance" and row["top1_similarity"] == 1.0, "stable top-1 result changed")
    require(row["serialized_matches_in_memory"] is True, "KB probe serialization changed")


def verify_eval_probe(row: dict[str, Any]) -> None:
    require(row["enrolled_count"] == 2 and row["surviving_question_count"] == 1, "eval counts changed")
    require(row["source_reported_accuracy"] == 1.0, "source accuracy changed")
    require(row["enrolled_coverage"] == 0.5, "enrolled coverage changed")
    require(row["all_failed_question_omitted_from_denominator"] is True, "eval omission label changed")


def independent_mutation_detection(cases: dict[str, Any], rows: list[dict[str, Any]]) -> set[str]:
    specs = {spec["id"]: spec for spec in cases["batch_cases"]}
    detected: set[str] = set()

    def batch_mutation(control_id: str, case_id: str, mutate: Any) -> None:
        altered = copy.deepcopy(rows)
        indexed = index_results(altered)
        mutate(indexed[("batch_promotion", case_id)])
        try:
            verify_batch(specs[case_id], indexed[("batch_promotion", case_id)])
        except VerificationFailure:
            detected.add(control_id)

    batch_mutation(
        "delete_original_identity",
        "complete_positive_accept",
        lambda row: row["identity_ledger"]["original_ids"].pop(),
    )
    batch_mutation(
        "flip_source_admission",
        "complete_positive_accept",
        lambda row: row["admission"].update(source_accepted=False),
    )
    batch_mutation(
        "relabel_unavailable_as_observed_loss",
        "partial_updated_none_survivor_accept",
        lambda row: row["identity_ledger"]["dispositions"].update({"pun-03": "observed_loss"}),
    )
    batch_mutation(
        "alter_rejected_serialized_poststate",
        "complete_balanced_reject",
        lambda row: row["kb_state"].update(serialized_post_sha256="0" * 64),
    )

    altered_eval = copy.deepcopy(rows)
    eval_row = index_results(altered_eval)[("evaluation_coverage", "all_failed_question_denominator")]
    eval_row["enrolled_count"] = 1
    try:
        verify_eval_probe(eval_row)
    except VerificationFailure:
        detected.add("change_eval_enrolled_denominator")

    altered_kb = copy.deepcopy(rows)
    kb_row = index_results(altered_kb)[("knowledge_base", "exact_subject_equal_embedding_top1")]
    kb_row["top1_guidance"] = "newer-guidance"
    try:
        verify_kb_probe(kb_row)
    except VerificationFailure:
        detected.add("replace_stable_top1_with_new_entry")
    return detected


def independently_derived_decision(indexed: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    incomplete = [
        case_id for case_id in (
            "complete_positive_accept",
            "complete_balanced_reject",
            "complete_all_ties_reject",
            "partial_updated_none_survivor_accept",
            "partial_empty_prompt_survivor_accept",
            "all_updated_prompts_empty_rollback",
            "all_updated_responses_none_rollback",
            "net_accept_with_group_loss",
        )
        if indexed[("batch_promotion", case_id)]["admission"]["source_accepted"]
        and indexed[("batch_promotion", case_id)]["admission"]["full_enrolled_decision"]
        == "UNDEFINED_FROM_OBSERVED_RESULTS"
    ]
    evaluation = indexed[("evaluation_coverage", "all_failed_question_denominator")]
    return {
        "batch_case_count": 8,
        "canonical_ams_status": {"public_note_depth": "not_assessed_by_evidence_artifact"},
        "complete_cohort_controls": "PASS",
        "evaluation_denominator_probe": {
            "enrolled_coverage": evaluation["enrolled_coverage"],
            "source_reported_accuracy": evaluation["source_reported_accuracy"],
        },
        "evidence_artifact_readiness": "PASS",
        "exact_subject_top1_probe": "OLDER_ENTRY_RETURNED_AFTER_APPEND",
        "full_cohort_status_for_filtered_admissions": "UNDEFINED_FROM_OBSERVED_RESULTS",
        "incomplete_survivor_admissions": incomplete,
        "model_or_api_calls": 0,
        "paper_or_benchmark_experiment_reproduction": "NOT_ATTEMPTED",
        "schema": "mnl-promotion-decision/1",
        "source_commit": COMMIT,
        "source_to_paper_revision_binding": "NOT_ESTABLISHED",
        "subgroup_non_regression_guarantee": "NOT_ESTABLISHED_BY_NET_BATCH_ACCEPTANCE",
    }


def verify_receipts() -> None:
    root_entries = {path.name for path in ROOT.iterdir() if path.name != "__pycache__"}
    require(root_entries == ROOT_SET, "artifact root inventory changed")
    require({path.name for path in (ROOT / "raw").iterdir()} == RAW_SET, "raw receipt inventory changed")
    verify_checksums()

    cases = load_json(ROOT / "raw/cases.json")
    rows = load_jsonl(ROOT / "raw/run_results.jsonl")
    require(cases == frozen_cases(), "frozen case payload changed")
    indexed = index_results(rows)
    require(len(rows) == 11, "result row count changed")
    for spec in cases["batch_cases"]:
        verify_batch(spec, indexed[("batch_promotion", spec["id"])])

    kb = indexed[("knowledge_base", "exact_subject_equal_embedding_top1")]
    verify_kb_probe(kb)
    evaluation = indexed[("evaluation_coverage", "all_failed_question_denominator")]
    verify_eval_probe(evaluation)
    require(indexed[("runtime_guard", "socket_network_guard")]["attempts"] == 0, "network attempt recorded")

    manifest = load_json(ROOT / "raw/source_manifest.json")
    require(
        set(manifest) == {"checkout_observations", "paper", "schema", "source", "source_methods_executed", "synthetic_adapters"},
        "source manifest field set changed",
    )
    require(
        set(manifest["source"]) == {
            "commit", "paper_production_revision_binding", "read_access_instrumented",
            "runner_declared_source_code_read_allowlist", "upstream_source_copied_into_artifact",
        },
        "source manifest source field set changed",
    )
    require(manifest["source"]["commit"] == COMMIT, "source commit changed")
    require(
        manifest["paper"] == {
            "acl_anthology_id": "2026.findings-acl.719",
            "physical_page_count_reviewed": 17,
            "sha256": PAPER_SHA256,
            "size_bytes": 5_855_586,
        },
        "paper identity changed",
    )
    require(manifest["schema"] == "mnl-source-manifest/2", "source manifest schema changed")
    allowlist = manifest["source"]["runner_declared_source_code_read_allowlist"]
    expected_allowlist = [
        {"git_blob": SOURCE_BLOBS[path], "path": path, "sha256": SOURCE_HASHES[path]}
        for path in ("mnl/trainer.py", "mnl/evaluator.py", "mnl/knowledge_base.py")
    ]
    require(allowlist == expected_allowlist, "source allowlist changed")
    require(manifest["source"]["read_access_instrumented"] is False, "source read instrumentation boundary changed")
    require(manifest["source"]["paper_production_revision_binding"] == "NOT_ESTABLISHED", "source/paper binding changed")
    require(manifest["source"]["upstream_source_copied_into_artifact"] is False, "upstream source copy boundary changed")
    observations = manifest["checkout_observations"]
    require(
        observations == {
            "allowlisted_bytes_match_lock_after": True,
            "allowlisted_bytes_match_lock_before": True,
            "git_status_clean_after": True,
            "git_status_clean_before": True,
            "transient_or_ignored_writes_instrumented": False,
        },
        "checkout endpoint observations changed",
    )
    require(
        manifest["source_methods_executed"] == [
            "PromptTuner._process_batch",
            "PromptTuner._evaluate_on_eval_set",
            "Evaluator.evaluate_batch",
            "Evaluator.evaluate_single",
            "KnowledgeBase.update_entry",
            "KnowledgeBase._save_entries",
            "KnowledgeBase.retrieve_by_subject",
        ],
        "executed-method declaration changed",
    )
    require(
        manifest["synthetic_adapters"] == [
            "classification_and_generation",
            "embedding_and_reward",
            "jsonl_load_save",
            "batch_splitter",
            "minimal_vector_operations",
            "optional_import_modules",
        ],
        "synthetic adapter declaration changed",
    )

    controls = load_json(ROOT / "raw/mutation_controls.json")
    expected_control_codes = [
        ("delete_original_identity", "BATCH_ORIGINAL_IDS"),
        ("flip_source_admission", "BATCH_ACCEPTANCE"),
        ("relabel_unavailable_as_observed_loss", "BATCH_DISPOSITIONS"),
        ("alter_rejected_serialized_poststate", "KB_REJECTED_SERIALIZED"),
        ("change_eval_enrolled_denominator", "EVAL_ENROLLED"),
        ("replace_stable_top1_with_new_entry", "KB_TOP1"),
    ]
    expected_controls_payload = {
        "all_detected": True,
        "controls": [
            {
                "detected": True,
                "expected_error_code": code,
                "id": control_id,
                "observed_error_code": code,
            }
            for control_id, code in expected_control_codes
        ],
        "schema": "mnl-mutation-controls/1",
    }
    require(controls == expected_controls_payload, "mutation receipt changed")
    expected_controls = {control_id for control_id, _code in expected_control_codes}
    require(independent_mutation_detection(cases, rows) == expected_controls, "independent mutation detection changed")

    decision = load_json(ROOT / "raw/decision.json")
    require(decision == independently_derived_decision(indexed), "independent decision rederivation changed")

    safety = load_json(ROOT / "raw/public_safety.json")
    require(safety["no_local_paths_credentials_or_upstream_source"] is True, "public safety gate changed")
    require(safety["denied_content_hits"] == [] and safety["copied_upstream_source"] is False, "public receipt leak detected")
    slash = b"/"
    denied = (
        slash + b"Users" + slash,
        slash + b"Volumes" + slash,
        slash + b"home" + slash,
        b"file" + b"://",
        b"BEGIN " + b"PRIVATE KEY",
        b"api" + b"_key",
        b"access" + b"_token",
        b"refresh" + b"_token",
    )
    safety_scope = ("cases.json", "run_results.jsonl", "decision.json", "source_manifest.json", "mutation_controls.json")
    require(safety["scan_scope"] == sorted(safety_scope), "public safety scope changed")
    for name in safety_scope:
        payload = (ROOT / "raw" / name).read_bytes().lower()
        require(not any(marker.lower() in payload for marker in denied), f"independent public scan failed: {name}")
    comparison = load_json(ROOT / "raw/comparison.json")
    require(comparison["byte_identical"] is True and comparison["primary_file_count"] == 6, "comparison gate changed")
    require(comparison["run_a_hash_seed"] == "313" and comparison["run_b_hash_seed"] == "727", "comparison seeds changed")
    for name in PRIMARY:
        digest = sha256(ROOT / "raw" / name)
        require(comparison["primary_files"][name]["run_a_sha256"] == digest, f"run A binding changed: {name}")
        require(comparison["primary_files"][name]["run_b_sha256"] == digest, f"run B binding changed: {name}")
    require(load_json(ROOT / "raw/environment_run_a.json")["hash_seed"] == "313", "environment A seed changed")
    require(load_json(ROOT / "raw/environment_run_b.json")["hash_seed"] == "727", "environment B seed changed")


def git_output(source: Path, *args: str) -> str:
    return subprocess.run(
        ["/usr/bin/git", "-C", str(source), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def source_bound(source: Path, paper_pdf: Path, work_root: Path) -> None:
    require(source.is_dir(), "source checkout missing")
    require(paper_pdf.is_file(), "paper PDF missing")
    require(not work_root.exists(), "work root must not already exist")
    require(not is_within(work_root, source), "work root must be outside the source checkout")
    require(not is_within(source, work_root), "work root must not contain the source checkout")
    require(git_output(source, "rev-parse", "HEAD") == COMMIT, "source HEAD mismatch")
    require(git_output(source, "status", "--porcelain") == "", "source checkout dirty")
    require(sha256(paper_pdf) == PAPER_SHA256, "paper PDF mismatch")
    work_root.mkdir(parents=True)
    run_a, run_b = work_root / "run-a", work_root / "run-b"
    for label, seed, output in (("A", "313", run_a), ("B", "727", run_b)):
        env = os.environ.copy()
        env.update({
            "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": seed, "TZ": "UTC",
        })
        subprocess.run(
            [
                sys.executable, str(ROOT / "audit.py"), "run",
                "--source", str(source), "--paper-pdf", str(paper_pdf),
                "--output", str(output), "--run-label", label,
            ],
            check=True,
            env=env,
        )
    comparison = work_root / "comparison.json"
    subprocess.run(
        [
            sys.executable, str(ROOT / "audit.py"), "compare",
            "--run-a", str(run_a), "--run-b", str(run_b), "--output", str(comparison),
        ],
        check=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    for name in PRIMARY:
        expected = (ROOT / "raw" / name).read_bytes()
        require((run_a / "raw" / name).read_bytes() == expected, f"fresh run A differs: {name}")
        require((run_b / "raw" / name).read_bytes() == expected, f"fresh run B differs: {name}")
    require(git_output(source, "status", "--porcelain") == "", "post-run source checkout is not Git-clean")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("receipt-only", "source-bound"), default="receipt-only")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--paper-pdf", type=Path)
    parser.add_argument("--work-root", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    verify_receipts()
    if args.mode == "source-bound":
        require(args.source is not None and args.paper_pdf is not None and args.work_root is not None, "source-bound mode requires --source, --paper-pdf, and --work-root")
        source_bound(args.source.resolve(), args.paper_pdf.resolve(), args.work_root.resolve())
        print("Verified checked receipts and fresh exact-source A/B byte identity.")
    else:
        print("Verified checked receipt inventory, hashes, derivations, controls, and claim boundary.")


if __name__ == "__main__":
    main()
