#!/usr/bin/env python3
"""Verify the checked Memora audit artifact and its exact external evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

CURRENT_COMMIT = "a6493188efc836d6511ed5e4163fe3ba87da30ff"
PARENT_COMMIT = "e19ebbd1089465876dca11b09e70256977f9755f"
PAPER_SHA256 = "683a21a6b6fa09f1a6ad270832b3d891e41ecff6e6893298d8efe0df702566b2"

RAW_FILES = {
    "aggregator.json",
    "census.json",
    "decision.json",
    "environment.json",
    "fama.json",
    "judge_binding.json",
    "official_pytest.txt",
    "official_tests.json",
    "paper_locator.json",
    "release_boundary.json",
    "reproduction.json",
    "source_manifest.json",
}
ROOT_FILES = {
    "PREREGISTRATION.md",
    "README.md",
    "audit.py",
    "checksums.sha256",
    "verify_checked.py",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(source: Path, *args: str, text: bool = True) -> Any:
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(source), *args],
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout.strip() if text else result.stdout


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path.name}")
    return value


def verify_tree(root: Path) -> None:
    root_entries = {path.name for path in root.iterdir() if path.name != "__pycache__"}
    if root_entries != ROOT_FILES | {"raw"}:
        raise AssertionError(f"artifact root file set mismatch: {sorted(root_entries)}")
    raw_entries = {path.name for path in (root / "raw").iterdir()}
    if raw_entries != RAW_FILES:
        raise AssertionError(f"raw file set mismatch: {sorted(raw_entries)}")
    junk = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo", ".tmp", ".log"}
    ]
    if junk:
        raise AssertionError(f"generated junk in checked artifact: {junk}")
    symlinks = [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_symlink()]
    if symlinks:
        raise AssertionError(f"symlinks are not allowed in checked artifact: {symlinks}")


def verify_checksums(root: Path) -> None:
    manifest = root / "checksums.sha256"
    seen: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_./-]+)", line)
        if not match:
            raise AssertionError(f"invalid checksum line: {line!r}")
        digest, relative = match.groups()
        if relative in seen or relative == "checksums.sha256" or relative.startswith("/") or ".." in Path(relative).parts:
            raise AssertionError(f"invalid/duplicate checksum path: {relative}")
        path = root / relative
        if not path.is_file():
            raise AssertionError(f"checksummed file missing: {relative}")
        actual = sha256_file(path)
        if actual != digest:
            raise AssertionError(f"checksum mismatch: {relative}: {actual} != {digest}")
        seen[relative] = digest
    expected = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest
    }
    if set(seen) != expected:
        raise AssertionError(f"checksum coverage mismatch: missing={sorted(expected-set(seen))}, extra={sorted(set(seen)-expected)}")


def verify_public_safety(root: Path) -> None:
    forbidden = (
        re.compile("/" + "Users/"),
        re.compile("/" + "Volumes/"),
        re.compile(r"/private/(?:var|tmp)/"),
        re.compile(r"(?i)(?:OPENAI|OPENROUTER|OPEN_ROUTER|ANTHROPIC|GOOGLE)_API_KEY\s*=\s*\S+"),
        re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    )
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            if pattern.search(text):
                raise AssertionError(f"public-safety pattern {pattern.pattern!r} found in {path.relative_to(root)}")


def verify_source(root: Path, source: Path) -> None:
    head = run_git(source, "rev-parse", "HEAD")
    parent = run_git(source, "rev-parse", "HEAD^")
    status = run_git(source, "status", "--porcelain=v1", "--untracked-files=all")
    if (head, parent, status) != (CURRENT_COMMIT, PARENT_COMMIT, ""):
        raise AssertionError(f"source gate failed: head={head}, parent={parent}, status={status!r}")
    manifest = load_json(root / "raw/source_manifest.json")
    if manifest["head"] != head or manifest["direct_parent"] != parent or manifest["worktree_status"] != "clean":
        raise AssertionError("source manifest identity/status mismatch")
    for row in manifest["inspected_files"]:
        relative = row["path"]
        blob = run_git(source, "show", f"{CURRENT_COMMIT}:{relative}", text=False)
        if hashlib.sha256(blob).hexdigest() != row["sha256"]:
            raise AssertionError(f"current source hash mismatch: {relative}")
        if run_git(source, "rev-parse", f"{CURRENT_COMMIT}:{relative}") != row["git_blob"]:
            raise AssertionError(f"current Git blob mismatch: {relative}")
        historical = row.get("historical_direct_parent")
        if historical:
            old_blob = run_git(source, "show", f"{PARENT_COMMIT}:{relative}", text=False)
            if hashlib.sha256(old_blob).hexdigest() != historical["sha256"]:
                raise AssertionError(f"historical source hash mismatch: {relative}")
    census = load_json(root / "raw/census.json")
    for row in census["files"]:
        path = source / row["path"]
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            raise AssertionError(f"question-file identity mismatch: {row['path']}")


def verify_logic(root: Path, paper_pdf: Path) -> None:
    if sha256_file(paper_pdf) != PAPER_SHA256:
        raise AssertionError("paper PDF hash mismatch")
    decision = load_json(root / "raw/decision.json")
    if decision.get("schema") != "memora-forgetting-contract-audit-decision/3" or decision.get("verdict") != "PASS":
        raise AssertionError("decision schema/verdict mismatch")
    if (
        decision.get("decision_scope") != "single_run_completeness"
        or decision.get("package_acceptance_status") != "not_evaluated_within_single_run"
        or len(decision.get("package_acceptance_requirements", [])) != 3
    ):
        raise AssertionError("single-run decision/package-acceptance scope mismatch")
    if not decision.get("gates") or not all(decision["gates"].values()):
        raise AssertionError(f"decision gate failure: {decision.get('gates')}")
    protocol = decision.get("protocol_provenance", {})
    if (
        protocol.get("public_protocol_file") != "PREREGISTRATION.md"
        or protocol.get("public_record_timing") != "post_execution"
        or protocol.get("private_pretest_freeze_date") != "2026-08-29"
        or protocol.get("private_pretest_source_published") is not False
        or protocol.get("same_day_clock_times_asserted") is not False
        or len(protocol.get("post_execution_amendments", [])) != 5
        or not protocol.get("pretest_aggregation_hypothesis_status", "").startswith(
            "not_supported_as_exact_source_contract"
        )
    ):
        raise AssertionError(f"protocol provenance mismatch: {protocol}")
    public_protocol = (root / "PREREGISTRATION.md").read_text(encoding="utf-8")
    required_protocol_markers = (
        "post-execution public-safe protocol record",
        "not itself a contemporaneously public preregistration",
        "private source is not published",
        "not supported as the exact executable aggregation contract",
        "invalid direct-function probe",
    )
    normalized_protocol = " ".join(public_protocol.lower().split())
    if any(marker not in normalized_protocol for marker in required_protocol_markers):
        raise AssertionError("public protocol chronology/amendment markers incomplete")

    tests = load_json(root / "raw/official_tests.json")
    if tests.get("passed") != 5 or tests.get("status") != "passed" or not tests.get("complete"):
        raise AssertionError("official five-test receipt missing")
    if any(tests.get(key) for key in ("created_paths", "deleted_paths", "modified_paths", "cache_paths_after")):
        raise AssertionError("official test export was not write/cache clean")

    judges = load_json(root / "raw/judge_binding.json")
    if judges["historical_track2"]["use_multi_judge_after_import_error"] is not False:
        raise AssertionError("historical Track-2 fallback observation mismatch")
    t2_matrix = judges["current_track2_initialization_matrix"]
    t1_matrix = judges["current_track1_initialization_matrix"]
    if len(t2_matrix) != 8 or len(t1_matrix) != 4:
        raise AssertionError("judge initialization matrix incomplete")
    origin = judges["current_track2_fresh_import_origin"]
    if (
        origin["fresh_process_api_client_initially_cached"]
        or not origin["both_origins_match_expected"]
        or origin["api_client_module_file"] != "evals/model_eval/api_client.py"
        or origin["openrouter_client_source_file"] != "evals/model_eval/api_client.py"
    ):
        raise AssertionError(f"current Track-2 import origin mismatch: {origin}")
    mechanics = judges["current_track2_import_mechanics"]
    if (
        mechanics["path_mutation"] != "sys.path.append"
        or mechanics["import_form"] != "from api_client import OpenRouterClient"
        or not mechanics["pre_cached_api_client_can_shadow_expected_module"]
        or not mechanics["earlier_sys_path_api_client_can_shadow_expected_module"]
        or not mechanics["official_test_asserts_class_name_only"]
        or mechanics["official_test_asserts_source_origin"]
    ):
        raise AssertionError(f"current Track-2 import mechanics mismatch: {mechanics}")
    boundary = judges["execution_boundary"]
    if boundary["real_client_or_model_constructed"] or not boundary["synthetic_fake_constructor_calls_recorded"]:
        raise AssertionError("judge matrix execution boundary mismatch")
    for row in t2_matrix:
        n, strict = row["requested_successful_clients"], row["strict"]
        if row["accepted"] != (n == 3 or not strict):
            raise AssertionError(f"Track-2 initialization outcome mismatch: {row}")
    if [row["accepted"] for row in t1_matrix] != [False, True, True, True]:
        raise AssertionError("Track-1 initialization outcomes mismatch")
    t1_runtime = judges["runtime_valid_judge_quorum"]["track1"]
    t2_runtime = judges["runtime_valid_judge_quorum"]["track2"]
    if [row["consensus"] for row in t1_runtime] != ["error", "yes", "tie", "yes"]:
        raise AssertionError("Track-1 runtime quorum outcomes mismatch")
    if [row["consensus"] for row in t2_runtime] != ["error", "yes", "no", "yes"]:
        raise AssertionError("Track-2 runtime quorum outcomes mismatch")
    if [row["is_correct"] for row in t1_runtime] != [False, True, False, True]:
        raise AssertionError("strict-majority correctness mismatch")

    fama = load_json(root / "raw/fama.json")
    if fama.get("schema") != "memora-fama-audit/2":
        raise AssertionError("FAMA schema mismatch")
    matrix = fama["bounded_valid_matrix"]
    paper_domain = matrix["paper_equation_domain"]
    source_extensions = matrix["source_zero_bucket_extensions"]
    if (
        matrix["source_valid_counter_fixtures"] != 784
        or matrix["source_valid_function_comparisons"] != 1568
        or paper_domain["fixtures"] != 729
        or paper_domain["function_comparisons"] != 1458
        or source_extensions["fixtures"] != 55
        or source_extensions["function_comparisons"] != 110
        or paper_domain["oracle_zero_division_defined"]
        or source_extensions["paper_defined"]
        or paper_domain["fixtures"] + source_extensions["fixtures"]
        != matrix["source_valid_counter_fixtures"]
    ):
        raise AssertionError("FAMA evidence-domain partition mismatch")
    if matrix["bounds_failures"] or matrix["monotonicity_failures"] or matrix["maximum_absolute_error"] > 1e-12:
        raise AssertionError("FAMA valid-domain gate failed")
    probe = fama["out_of_domain_direct_function_probe"]
    if (probe["track1"], probe["track2"]) != (1.5, 1.5):
        raise AssertionError("FAMA out-of-domain probe mismatch")
    if fama["released_counter_pair_corners"]["distinct_pairs"] != 156:
        raise AssertionError("released counter-pair corner coverage mismatch")

    census = load_json(root / "raw/census.json")
    if census["totals"] != {
        "files": 30,
        "questions": 600,
        "criteria": 6415,
        "memory_presence": 2947,
        "forgetting_absence": 3468,
        "zero_forgetting": 204,
        "zero_presence": 0,
    }:
        raise AssertionError(f"release census mismatch: {census['totals']}")
    qcoll = census["identity"]["bare_question_id_collisions"]
    ccoll = census["identity"]["bare_criterion_id_collisions"]
    if (qcoll["groups"], qcoll["payload_different_groups"]) != (38, 38):
        raise AssertionError("question bare-ID collision geometry mismatch")
    if (ccoll["groups"], ccoll["payload_different_groups"], ccoll["payload_identical_groups"]) != (178, 175, 3):
        raise AssertionError("criterion bare-ID collision geometry mismatch")
    if len(census["identity"]["three_identical_criterion_payload_path_pair_loci"]) != 3:
        raise AssertionError("identical criterion payload loci incomplete")

    aggregator = load_json(root / "raw/aggregator.json")
    fixture = aggregator["synthetic_fixtures"]["unweighted_report_macro"]
    if (fixture["source_aggregate"], fixture["question_weighted_control"]) != (0.5, 0.9):
        raise AssertionError("aggregator macro fixture mismatch")
    if not aggregator["synthetic_fixtures"]["duplicate_report_rows_retained"]:
        raise AssertionError("aggregator duplicate-row fixture missing")

    boundary = load_json(root / "raw/release_boundary.json")
    if (
        any(boundary["tracked_inventory"].values())
        or any(boundary["reader_checkout_inventory"].values())
        or boundary["derived_boundary"]["table3_reconstructable_model_free_from_locked_release"]
    ):
        raise AssertionError("release boundary mismatch")
    paper = load_json(root / "raw/paper_locator.json")
    if paper["paper"]["pdf_sha256"] != PAPER_SHA256 or paper["appendix_d2_example"]["physical_pages"] != [23, 24]:
        raise AssertionError("paper locator mismatch")

    reproduction = load_json(root / "raw/reproduction.json")
    if reproduction.get("verdict") != "REPRODUCIBLE" or reproduction.get("stable_files_compared") != 11:
        raise AssertionError("reproduction receipt mismatch")
    for row in reproduction["files"]:
        if sha256_file(root / "raw" / row["path"]) != row["sha256"]:
            raise AssertionError(f"reproduction hash mismatch: {row['path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--paper-pdf", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.artifact.resolve()
    verify_tree(root)
    verify_checksums(root)
    verify_public_safety(root)
    verify_source(root, args.source.resolve())
    verify_logic(root, args.paper_pdf.resolve())
    print("PASS: checked Memora audit artifact, exact source, paper identity, hashes, and logic verified")


if __name__ == "__main__":
    main()
