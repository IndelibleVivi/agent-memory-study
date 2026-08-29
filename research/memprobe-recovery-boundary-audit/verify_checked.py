#!/usr/bin/env python3
"""Verify the checked MEMPROBE fixed released-artifact audit package.

``receipt-only`` verifies package hashes and independently recomputes the
deterministic reductions exposed by public receipts.  It does not reopen the
original evidence.  ``source-bound`` additionally reopens an exact clean
checkout and paper PDF, verifies every registered input, executes a fresh
offline audit, and requires byte identity with every installed primary
receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import runpy
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


sys.dont_write_bytecode = True

SOURCE_COMMIT = "19bb83644b082489b4e181e59f1cded1a00d0529"
PAPER_SHA256 = "e5b3699c00a0731cc00e165f12efb755c57886058e311c01e5643df6e56897b5"
CATEGORIES = (
    "skill_memory",
    "knowledge_memory",
    "episodic_memory",
    "self_model",
    "assistance_preference",
)
CATEGORY_COUNTS = {
    "skill_memory": 7,
    "knowledge_memory": 7,
    "episodic_memory": 7,
    "self_model": 5,
    "assistance_preference": 5,
}
USERS = tuple(f"user_{index:03d}" for index in range(1, 51))
RUN_REGISTRY: dict[str, dict[str, str]] = {
    "nomem_pooled_50": {"system": "nomem", "mode": "dump_all", "base": "nomem_pooled_50"},
    "amem_pooled_50": {"system": "amem", "mode": "dump_all", "base": "amem_pooled_50"},
    "amem_pooled_50_retrieve": {"system": "amem", "mode": "retrieve", "base": "amem_pooled_50"},
    "longctx_full_pooled_50": {"system": "longctx_full", "mode": "dump_all", "base": "longctx_full_pooled_50"},
    "longctx_full_pooled_50_retrieve": {"system": "longctx_full", "mode": "retrieve", "base": "longctx_full_pooled_50"},
    "mem0_pooled_50": {"system": "mem0", "mode": "dump_all", "base": "mem0_pooled_50"},
    "mem0_pooled_50_retrieve": {"system": "mem0", "mode": "retrieve", "base": "mem0_pooled_50"},
    "memt_memonly_pooled_50": {"system": "memt", "mode": "dump_all", "base": "memt_memonly_pooled_50"},
    "memt_memonly_pooled_50_retrieve": {"system": "memt", "mode": "retrieve", "base": "memt_memonly_pooled_50"},
}
RUN_IDS = set(RUN_REGISTRY)
PRIMARY_FILES = {
    "arithmetic.json",
    "attribution_rows.jsonl",
    "cases.json",
    "decision.json",
    "input_manifest.json",
    "microfixture.json",
    "mutation_controls.json",
    "observability.json",
    "packet_items.jsonl",
    "packet_rows.jsonl",
    "paired_deltas.jsonl",
    "public_safety.json",
    "replay_inventory.json",
    "store_census.json",
    "target_registry.json",
    "target_joins.jsonl",
}
RAW_FILES = PRIMARY_FILES | {"comparison.json", "environment_run_a.json", "environment_run_b.json"}
ROOT_FILES = {
    "NOTICE.md",
    "PROTOCOL.md",
    "README.md",
    "audit.py",
    "checksums.sha256",
    "verify_checked.py",
}
DECISION_FIELDS = {
    "attribution_input_observability",
    "fixed_artifact_gates",
    "historical_execution_replay",
    "packet_unique_binding",
    "primary_receipt_cardinalities",
    "schema",
    "source_commit",
    "source_replay_material_status",
    "stored_output_observability",
    "worked_fixed_artifact_audit",
}
FIXED_GATE_NAMES = {
    "aggregate_reports",
    "attribution_input_linkage",
    "attribution_reduction",
    "checkout_immutable",
    "fixed_score_arithmetic",
    "mutation_controls",
    "network_guard",
    "packet_membership_complete",
    "packet_schema",
    "public_population",
    "target_identity",
}
CASE_NAMES = (
    "user_022_pushback_tolerance",
    "user_005_geographic_knowledge_amem",
    "lexicographic_full_ge_075_retrieve_lt_075",
)
QUARTER_SCORES = {Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1)}


class VerificationFailure(RuntimeError):
    pass


def verify_decision_header(decision: dict[str, Any]) -> None:
    gates = decision.get("fixed_artifact_gates")
    if set(decision) != DECISION_FIELDS:
        raise VerificationFailure("decision outer schema mismatch")
    if not isinstance(gates, dict) or set(gates) != FIXED_GATE_NAMES or any(value is not True for value in gates.values()):
        raise VerificationFailure("decision fixed-artifact gate schema/value mismatch")
    if decision.get("schema") != "memprobe-fixed-artifact-decision/1":
        raise VerificationFailure("decision schema mismatch")
    if decision.get("source_commit") != SOURCE_COMMIT:
        raise VerificationFailure("decision source revision mismatch")
    if (
        decision.get("packet_unique_binding") != "PASS"
        or decision.get("stored_output_observability") != "COMPLETE_TYPED_INVENTORY"
        or decision.get("attribution_input_observability") != "PARTIAL"
        or decision.get("source_replay_material_status") != "BLOCKED"
        or decision.get("historical_execution_replay") != "NOT_ATTEMPTED"
        or decision.get("worked_fixed_artifact_audit") != "SINGLE_RUN_PASS_PENDING_REPEATABILITY_AND_SOURCE_BOUND_REVALIDATION"
    ):
        raise VerificationFailure("decision boundary/status mismatch")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(strict_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(strict_equal(a, b) for a, b in zip(left, right))
    return left == right


def typed_form(value: Any) -> Any:
    if value is None:
        return {"type": "null"}
    if type(value) is bool:
        return {"type": "boolean", "value": value}
    if type(value) is int:
        return {"type": "integer", "value": str(value)}
    if type(value) is Decimal:
        return {"type": "decimal", "value": str(value)}
    if type(value) is str:
        return {"type": "string", "value": value}
    if isinstance(value, list):
        return {"type": "array", "value": [typed_form(item) for item in value]}
    if isinstance(value, dict):
        return {"type": "object", "value": [[key, typed_form(value[key])] for key in sorted(value)]}
    raise VerificationFailure(f"unsupported typed digest value: {type(value).__name__}")


def typed_digest(value: Any) -> str:
    payload = json.dumps(typed_form(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json_bytes(payload: bytes, label: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise VerificationFailure(f"duplicate JSON key in {label}: {key!r}")
            value[key] = item
        return value

    def constant(value: str) -> Any:
        raise VerificationFailure(f"nonstandard JSON constant in {label}: {value}")

    try:
        return json.loads(
            payload.decode("utf-8"),
            parse_float=Decimal,
            parse_int=int,
            parse_constant=constant,
            object_pairs_hook=object_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationFailure(f"invalid JSON in {label}: {exc}") from exc


def load_json(path: Path) -> dict[str, Any]:
    value = load_json_bytes(path.read_bytes(), path.name)
    if not isinstance(value, dict):
        raise VerificationFailure(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for index, line in enumerate(path.read_bytes().splitlines(), 1):
        if not line:
            raise VerificationFailure(f"blank JSONL row: {path.name}:{index}")
        value = load_json_bytes(line, f"{path.name}:{index}")
        if not isinstance(value, dict):
            raise VerificationFailure(f"expected JSONL object: {path.name}:{index}")
        rows.append(value)
    return rows


def fraction_record_value(record: dict[str, Any]) -> Fraction:
    if not {"numerator", "denominator", "float"}.issubset(record):
        raise VerificationFailure("fraction record is incomplete")
    numerator, denominator = record["numerator"], record["denominator"]
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        raise VerificationFailure("fraction record integer/type boundary failed")
    value = Fraction(numerator, denominator)
    if type(record["float"]) not in (int, Decimal) or abs(float(value) - float(record["float"])) > 1e-15:
        raise VerificationFailure("fraction record binary64 projection mismatch")
    return value


def score_value(record: dict[str, Any]) -> Fraction:
    value = fraction_record_value(record)
    if value not in QUARTER_SCORES:
        raise VerificationFailure(f"out-of-rubric fixed score: {value}")
    json_type, literal = record.get("json_type"), record.get("literal")
    if json_type not in {"integer", "decimal"} or type(literal) is not str:
        raise VerificationFailure("score type/literal receipt mismatch")
    if json_type == "integer":
        if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)", literal):
            raise VerificationFailure("noncanonical integer score literal")
        literal_value = Fraction(int(literal))
    else:
        if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)\.[0-9]+", literal):
            raise VerificationFailure("noncanonical decimal score literal")
        literal_value = Fraction(Decimal(literal))
    if literal_value != value:
        raise VerificationFailure("score literal/json_type does not bind the rational value")
    return value


def valid_packet_identifier(value: Any) -> bool:
    return value is None or (
        type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}", value) is not None
    )


def absolute_local_path(value: str) -> bool:
    return (
        value.startswith("/")
        or re.match(r"^[A-Za-z]:[\\/]", value) is not None
        or value.startswith("\\\\")
    )


def exact_sample_stats(values: list[Fraction]) -> tuple[Fraction, Fraction, float]:
    mean = sum(values, Fraction()) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, variance, math.sqrt(float(variance))


def run_git(source: Path, *args: str) -> str:
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(source), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def verify_tree(root: Path) -> None:
    root_entries = {path.name for path in root.iterdir() if path.name != "__pycache__"}
    if root_entries != ROOT_FILES | {"raw"}:
        raise VerificationFailure(f"artifact root file set mismatch: {sorted(root_entries)}")
    raw_entries = {path.name for path in (root / "raw").iterdir()}
    if raw_entries != RAW_FILES:
        raise VerificationFailure(f"raw file set mismatch: {sorted(raw_entries)}")
    prohibited = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_symlink() or path.name == "__pycache__" or path.suffix in {".pyc", ".pyo", ".tmp", ".log"}
    ]
    if prohibited:
        raise VerificationFailure(f"prohibited generated/symlink paths: {prohibited}")


def verify_checksums(root: Path) -> None:
    manifest = root / "checksums.sha256"
    seen: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_./-]+)", line)
        if not match:
            raise VerificationFailure(f"invalid checksum line: {line!r}")
        digest, relative = match.groups()
        if relative in seen or relative == "checksums.sha256" or relative.startswith("/") or ".." in Path(relative).parts:
            raise VerificationFailure(f"unsafe/duplicate checksum path: {relative}")
        path = root / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise VerificationFailure(f"checksum mismatch: {relative}")
        seen[relative] = digest
    expected = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest
    }
    if set(seen) != expected:
        raise VerificationFailure(f"checksum coverage mismatch: missing={sorted(expected-set(seen))}, extra={sorted(set(seen)-expected)}")


def verify_public_package(root: Path) -> None:
    text_patterns = [
        re.compile("/" + "Users/"),
        re.compile("/" + "Volumes/"),
        re.compile("/" + "private/(?:tmp|var)/"),
        re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
        re.compile(r"(?i)(?:OPENAI|ANTHROPIC|OPENROUTER|GOOGLE)_API_KEY\s*[=:]\s*\S+"),
        re.compile(r"(?i)\b(?:" + "local" + r"host|[A-Za-z0-9-]+\.local)\b"),
    ]
    denied_receipt_keys = {
        "agent_response", "content", "context", "evidence", "explanation", "ground_truth",
        "judge_reason", "persona", "predicted", "prompt", "rationale", "reason",
        "slot_fill_reason", "target_short", "task", "transcript",
    }

    def key_pointers(value: Any, pointer: str = "#") -> Iterable[tuple[str, str]]:
        if isinstance(value, dict):
            for key, item in value.items():
                escaped = key.replace("~", "~0").replace("/", "~1")
                key_pointer = f"{pointer}/{escaped}"
                yield key_pointer, key
                yield from key_pointers(item, key_pointer)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from key_pointers(item, f"{pointer}/{index}")

    structural_output_fields = {"predicted", "slot_fill_reason", "judge_reason"}

    def structural_key_exempt(filename: str, pointer: str, key: str) -> bool:
        if key not in structural_output_fields:
            return False
        if filename == "observability.json":
            match = re.fullmatch(r"#/runs/([^/]+)/(predicted|slot_fill_reason|judge_reason)", pointer)
            return match is not None and match.group(1) in RUN_IDS and match.group(2) == key
        if filename == "target_joins.jsonl":
            return pointer == f"#/output_states/{key}"
        if filename == "paired_deltas.jsonl":
            return pointer == f"#/field_deltas/{key}"
        return False

    def string_values(value: Any) -> Iterable[str]:
        if type(value) is str:
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from string_values(item)
        elif isinstance(value, list):
            for item in value:
                yield from string_values(item)

    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        text = path.read_text(encoding="utf-8")
        for pattern in text_patterns:
            if pattern.search(text):
                raise VerificationFailure(f"public-safety pattern in {path.relative_to(root)}: {pattern.pattern}")
        if path.parent.name != "raw" or path.name == "microfixture.json" or path.suffix not in {".json", ".jsonl"}:
            continue
        values = load_jsonl(path) if path.suffix == ".jsonl" else [load_json(path)]
        denied_key_pointers = []
        for value in values:
            for pointer, key in key_pointers(value):
                if key in denied_receipt_keys and not structural_key_exempt(path.name, pointer, key):
                    denied_key_pointers.append(pointer)
            for string in string_values(value):
                if absolute_local_path(string) or re.search(r"(?i)\b(?:" + "local" + r"host|[A-Za-z0-9-]+\.local)\b", string):
                    raise VerificationFailure(f"local absolute path/hostname value in {path.name}")
        if denied_key_pointers:
            raise VerificationFailure(
                f"denied upstream free-text key pointers in {path.name}: {sorted(set(denied_key_pointers))}"
            )


def expected_attribution_label(row: dict[str, Any]) -> str:
    score = score_value(row["score"])
    stages = row.get("stage_shape")
    if not isinstance(stages, list):
        raise VerificationFailure("attribution stage_shape is not a list")
    if score >= Fraction(3, 4):
        if stages:
            raise VerificationFailure("recovered attribution row has later stages")
        return "ok"
    names = [stage.get("name") for stage in stages if isinstance(stage, dict)]
    required = [stage.get("required_values") for stage in stages]
    if names == ["oracle"] and required == [{"can_invite": False}]:
        return "task_design_failure"
    if names == ["oracle", "disclosure"] and required == [{"can_invite": True}, {"disclosed": True}]:
        return "memory_failure"
    if names == ["oracle", "disclosure", "disclosure_subclass"] and required[:2] == [{"can_invite": True}, {"disclosed": False}]:
        category = required[2].get("category") if isinstance(required[2], dict) else None
        mapping = {"A": "agent_elicitation_failure", "B": "simulator_too_strict", "?": "unclassified"}
        if category in mapping:
            return mapping[category]
    raise VerificationFailure(f"illegal attribution stage shape: {names}/{required}")


def verify_string_observation(value: Any, label: str) -> None:
    if not isinstance(value, dict) or value.get("state") not in {
        "FIELD_ABSENT", "NULL", "EMPTY_STRING", "WHITESPACE_ONLY", "NONEMPTY_STRING", "WRONG_TYPE",
    }:
        raise VerificationFailure(f"invalid string observation state: {label}")
    state = value["state"]
    if state in {"EMPTY_STRING", "WHITESPACE_ONLY", "NONEMPTY_STRING"}:
        if set(value) != {"state", "sha256", "exact_literal_unknown"} or not re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256"))) or type(value.get("exact_literal_unknown")) is not bool:
            raise VerificationFailure(f"invalid present-string observation: {label}")
    elif state == "WRONG_TYPE":
        if set(value) != {"state", "json_type"} or type(value.get("json_type")) is not str:
            raise VerificationFailure(f"invalid wrong-type observation: {label}")
    elif set(value) != {"state"}:
        raise VerificationFailure(f"invalid absent/null observation: {label}")


def expected_cases_receipt(
    target_rows: list[dict[str, Any]],
    packet_rows: list[dict[str, Any]],
    packet_items: list[dict[str, Any]],
) -> dict[str, Any]:
    packets_by_key = {
        (row["run_id"], row["user_id"], row["category"], row["dimension"]): row
        for row in packet_rows
    }
    item_ids_by_key: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for row in packet_items:
        key = (row["run_id"], row["user_id"], row["category"], row["dimension"])
        if row.get("packet_item_id") is not None:
            item_ids_by_key[key].append(row["packet_item_id"])

    def project(row: dict[str, Any], label: str) -> dict[str, Any]:
        key = (row["run_id"], row["user_id"], row["category"], row["dimension"])
        packet = packets_by_key.get(key)
        return {
            "category": row["category"],
            "dimension": row["dimension"],
            "fixed_numeric_score": row["score"]["float"],
            "label": label,
            "packet_cardinality": packet["cardinality"] if packet else None,
            "packet_item_ids": item_ids_by_key.get(key, []),
            "reconstruction_locator": row["reconstruction_locator"],
            "run_id": row["run_id"],
            "scoring_mode": row["scoring_mode"],
            "stored_attribution_label": row["stored_attribution_label"],
            "system": row["system"],
            "user_id": row["user_id"],
        }

    known_1 = sorted(
        (
            project(row, "KNOWN_PAPER_OR_RECONNAISSANCE_CASE")
            for row in target_rows
            if row["user_id"] == "user_022" and row["dimension"] == "pushback_tolerance"
        ),
        key=lambda row: row["run_id"],
    )
    known_2 = sorted(
        (
            project(row, "KNOWN_PAPER_OR_RECONNAISSANCE_CASE")
            for row in target_rows
            if row["user_id"] == "user_005"
            and row["dimension"] == "geographic_knowledge"
            and row["system"] == "amem"
        ),
        key=lambda row: row["run_id"],
    )
    full_lookup = {
        (row["system"], row["user_id"], row["category"], row["dimension"]): row
        for row in target_rows
        if row["scoring_mode"] == "dump_all" and row["system"] != "nomem"
    }
    retrieve_lookup = {
        (row["system"], row["user_id"], row["category"], row["dimension"]): row
        for row in target_rows
        if row["scoring_mode"] == "retrieve"
    }
    rule_candidates = [
        key
        for key in sorted(set(full_lookup) & set(retrieve_lookup))
        if score_value(full_lookup[key]["score"]) >= Fraction(3, 4)
        and score_value(retrieve_lookup[key]["score"]) < Fraction(3, 4)
    ]
    rule_selected: list[dict[str, Any]] = []
    if rule_candidates:
        key = rule_candidates[0]
        rule_selected = [
            project(full_lookup[key], "RULE_SELECTED_ILLUSTRATION"),
            project(retrieve_lookup[key], "RULE_SELECTED_ILLUSTRATION"),
        ]
    return {
        "schema": "memprobe-public-cases/1",
        "source_commit": SOURCE_COMMIT,
        "strata": [
            {"case": CASE_NAMES[0], "rows": known_1},
            {"case": CASE_NAMES[1], "rows": known_2},
            {"case": CASE_NAMES[2], "rows": rule_selected},
        ],
    }


def verify_cases_receipt(
    cases: dict[str, Any],
    target_rows: list[dict[str, Any]],
    packet_rows: list[dict[str, Any]],
    packet_items: list[dict[str, Any]],
) -> None:
    if not strict_equal(cases, expected_cases_receipt(target_rows, packet_rows, packet_items)):
        raise VerificationFailure("cases receipt schema/labels/projection mismatch")


def verify_receipt_logic(root: Path) -> dict[str, Any]:
    raw = root / "raw"
    decision = load_json(raw / "decision.json")
    verify_decision_header(decision)

    target_rows = load_jsonl(raw / "target_joins.jsonl")
    attr_rows = load_jsonl(raw / "attribution_rows.jsonl")
    packet_rows = load_jsonl(raw / "packet_rows.jsonl")
    packet_items = load_jsonl(raw / "packet_items.jsonl")
    paired_rows = load_jsonl(raw / "paired_deltas.jsonl")
    cardinalities = decision["primary_receipt_cardinalities"]
    observed_cardinalities = {
        "attribution_rows": len(attr_rows),
        "packet_items": len(packet_items),
        "packet_rows": len(packet_rows),
        "paired_historical_artifact_deltas": len(paired_rows),
        "registered_targets": 1550,
        "target_join_rows": len(target_rows),
    }
    if not strict_equal(cardinalities, observed_cardinalities):
        raise VerificationFailure(f"decision cardinalities mismatch: {cardinalities} != {observed_cardinalities}")
    if len(target_rows) != 13950 or len(attr_rows) != 13950 or len(packet_rows) != 6200 or len(paired_rows) != 6200 or len(packet_items) != 30379:
        raise VerificationFailure("registered exhaustive population cardinality mismatch")

    public_safety = load_json(raw / "public_safety.json")
    if not strict_equal(public_safety, {
        "absolute_local_path_matches": 0,
        "api_secret_pattern_matches": 0,
        "files_scanned_excluding_self": 15,
        "schema": "memprobe-public-safety/1",
        "upstream_continuous_eight_token_span_matches": 0,
        "upstream_free_text_copied": False,
    }):
        raise VerificationFailure("public-safety receipt mismatch")

    microfixture = load_json(raw / "microfixture.json")
    if not strict_equal(microfixture, {
        "designated_store_projection": {"content": "fixture_alpha", "id": "fixture-item-1"},
        "expected_transition": "EXACT_MEMBER",
        "fixture_origin": "AMS-authored synthetic fixture",
        "not_a_memprobe_record": True,
        "not_for_benchmark_score_reproduction": True,
        "packet": {
            "category": "fixture_category",
            "content": "fixture_alpha",
            "context": "fixture_context",
            "id": "fixture-item-1",
            "keywords": ["fixture_key"],
            "score": Decimal("0.5"),
            "tags": ["fixture_tag"],
        },
        "schema": "memprobe-ams-microfixture/1",
    }):
        raise VerificationFailure("AMS microfixture schema/value mismatch")

    registry = load_json(raw / "target_registry.json")
    if (
        registry.get("schema") != "memprobe-target-registry/1"
        or not strict_equal(registry.get("categories"), CATEGORY_COUNTS)
        or not strict_equal(registry.get("run_registry"), RUN_REGISTRY)
        or registry.get("users") != list(USERS)
        or not isinstance(registry.get("targets"), list)
        or len(registry["targets"]) != 1550
    ):
        raise VerificationFailure("target registry header mismatch")
    registered_targets: dict[tuple[str, str, str], int] = {}
    user_category_counts: Counter[tuple[str, str]] = Counter()
    user_task_indices: dict[str, set[int]] = defaultdict(set)
    for row in registry["targets"]:
        if set(row) != {"category", "dimension", "task_index", "user_id"}:
            raise VerificationFailure("target registry row schema mismatch")
        key = (row["user_id"], row["category"], row["dimension"])
        if (
            key in registered_targets
            or row["user_id"] not in USERS
            or row["category"] not in CATEGORIES
            or type(row["dimension"]) is not str
            or type(row["task_index"]) is not int
            or not 1 <= row["task_index"] <= 31
        ):
            raise VerificationFailure(f"invalid/duplicate target registry row: {row}")
        registered_targets[key] = row["task_index"]
        user_category_counts[(row["user_id"], row["category"])] += 1
        user_task_indices[row["user_id"]].add(row["task_index"])
    if any(user_category_counts[(user, category)] != CATEGORY_COUNTS[category] for user in USERS for category in CATEGORIES):
        raise VerificationFailure("target registry category geometry mismatch")
    if any(user_task_indices[user] != set(range(1, 32)) for user in USERS):
        raise VerificationFailure("target registry task-index geometry mismatch")
    expected_target_keys = {
        (run_id, user_id, category, dimension, spec["mode"])
        for run_id, spec in RUN_REGISTRY.items()
        for user_id, category, dimension in registered_targets
    }

    target_keys: set[tuple[str, str, str, str, str]] = set()
    scores_by_user_category: dict[tuple[str, str, str], list[Fraction]] = defaultdict(list)
    output_counts: dict[str, dict[str, Counter[str]]] = {
        run: {field: Counter() for field in ("predicted", "slot_fill_reason", "judge_reason", "score")}
        for run in RUN_IDS
    }
    target_by_mode: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in target_rows:
        expected_target_row_fields = {
            "attribution_locator", "benchmark_explanation_sha256", "benchmark_target_sha256",
            "category", "dimension", "episode_locator", "episode_sha256", "join", "output_states",
            "reconstruction_locator", "run_id", "score", "scoring_mode", "stored_attribution_label",
            "system", "task_index", "task_locator", "task_text_sha256", "user_id",
        }
        if set(row) != expected_target_row_fields:
            raise VerificationFailure("target receipt row schema mismatch")
        key = (row["run_id"], row["user_id"], row["category"], row["dimension"], row["scoring_mode"])
        if key in target_keys or key not in expected_target_keys:
            raise VerificationFailure(f"invalid/duplicate target key: {key}")
        spec = RUN_REGISTRY[row["run_id"]]
        if row.get("system") != spec["system"] or row.get("scoring_mode") != spec["mode"]:
            raise VerificationFailure(f"run/system/mode mismatch: {key}")
        if row.get("task_index") != registered_targets[(row["user_id"], row["category"], row["dimension"])]:
            raise VerificationFailure(f"target task index mismatch: {key}")
        target_keys.add(key)
        expected_join_fields = {
            "attribution_copy_exact", "benchmark_explanation_exact", "benchmark_target_exact",
            "category_exact", "dimension_exact", "scoring_mode_exact", "task_target_exact", "user_id_exact",
        }
        if set(row.get("join", {})) != expected_join_fields or not all(value is True for value in row["join"].values()):
            raise VerificationFailure(f"target join row is not verified: {key}")
        if set(row.get("output_states", {})) != {"predicted", "slot_fill_reason", "judge_reason"}:
            raise VerificationFailure(f"target output-state schema mismatch: {key}")
        for field in ("predicted", "slot_fill_reason", "judge_reason"):
            verify_string_observation(row["output_states"][field], f"{key}/{field}")
        for hash_field in ("benchmark_explanation_sha256", "benchmark_target_sha256", "episode_sha256", "task_text_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(row.get(hash_field))):
                raise VerificationFailure(f"invalid target digest: {key}/{hash_field}")
        score = score_value(row["score"])
        scores_by_user_category[(row["run_id"], row["user_id"], row["category"])].append(score)
        target_by_mode[(row["system"], row["user_id"], row["category"], row["dimension"], row["scoring_mode"])] = row
        for field in ("predicted", "slot_fill_reason", "judge_reason"):
            state = row["output_states"][field]
            output_counts[row["run_id"]][field][state["state"]] += 1
            if state.get("exact_literal_unknown") is True:
                output_counts[row["run_id"]][field]["EXACT_LITERAL_UNKNOWN"] += 1
        output_counts[row["run_id"]]["score"]["VALID_QUARTER_STEP"] += 1
    if target_keys != expected_target_keys:
        raise VerificationFailure("target rows do not form the exact registered Cartesian population")

    arithmetic = load_json(raw / "arithmetic.json")
    arithmetic_runs = {row["run_id"]: row for row in arithmetic.get("runs", [])}
    if set(arithmetic_runs) != RUN_IDS or arithmetic.get("aggregate_report_gate") is not True:
        raise VerificationFailure("arithmetic run registry/report gate mismatch")
    for run_id in RUN_IDS:
        run_receipt = arithmetic_runs[run_id]
        per_user_rows = {row["user_id"]: row for row in run_receipt["per_user_fixed_arithmetic"]}
        if set(per_user_rows) != set(USERS):
            raise VerificationFailure(f"per-user arithmetic population mismatch: {run_id}")
        per_user_values: dict[str, list[Fraction]] = {field: [] for field in (*CATEGORIES, "overall")}
        for user_id, receipt in per_user_rows.items():
            category_means: dict[str, Fraction] = {}
            for category in CATEGORIES:
                scores = scores_by_user_category[(run_id, user_id, category)]
                if len(scores) != CATEGORY_COUNTS[category]:
                    raise VerificationFailure(f"category score count mismatch: {run_id}/{user_id}/{category}")
                mean = sum(scores, Fraction()) / len(scores)
                if fraction_record_value(receipt["categories"][category]) != mean:
                    raise VerificationFailure(f"per-user category mean mismatch: {run_id}/{user_id}/{category}")
                category_means[category] = mean
                per_user_values[category].append(mean)
            overall = sum(category_means.values(), Fraction()) / len(CATEGORIES)
            if fraction_record_value(receipt["overall"]) != overall:
                raise VerificationFailure(f"per-user overall mismatch: {run_id}/{user_id}")
            per_user_values["overall"].append(overall)
        for field, values in per_user_values.items():
            mean, variance, std = exact_sample_stats(values)
            stored = run_receipt["fixed_arithmetic"][field]
            if (
                fraction_record_value(stored["mean"]) != mean
                or fraction_record_value(stored["sample_variance"]) != variance
                or abs(float(stored["sample_standard_deviation"]) - std) > 1e-12
            ):
                raise VerificationFailure(f"across-user arithmetic mismatch: {run_id}/{field}")
        candidates = run_receipt["candidate_50_user_reports"]
        if not candidates or any(row.get("status") != "RELEASED_AGGREGATE_MATCH" or not all(row.get("field_matches", {}).values()) for row in candidates):
            raise VerificationFailure(f"aggregate candidate mismatch: {run_id}")

    attr_keys: set[tuple[str, str, str, str, str]] = set()
    for row in attr_rows:
        expected_attr_fields = {
            "category", "dimension", "episode_exists", "episode_locator", "episode_sha256",
            "exact_released_prompt_or_input_hash", "historical_input_observability", "input_binding",
            "reduction", "run_id", "score", "scoring_mode", "stage_field_observations", "stage_shape",
            "stored_attribution_label", "stored_disclosure_verdict", "stored_task_design_verdict",
            "system", "task_index", "task_text_exact", "transcript_has_nonempty_agent_and_user", "user_id",
        }
        if set(row) != expected_attr_fields:
            raise VerificationFailure("attribution receipt row schema mismatch")
        key = (row["run_id"], row["user_id"], row["category"], row["dimension"], row["scoring_mode"])
        if key in attr_keys or key not in expected_target_keys:
            raise VerificationFailure(f"duplicate attribution key: {key}")
        attr_keys.add(key)
        spec = RUN_REGISTRY[row["run_id"]]
        registered_task_index = registered_targets[(row["user_id"], row["category"], row["dimension"])]
        if row.get("system") != spec["system"] or row.get("scoring_mode") != spec["mode"] or row.get("task_index") != registered_task_index:
            raise VerificationFailure(f"attribution run/system/mode/task mismatch: {key}")
        expected_episode = f"history/{spec['base']}/{row['user_id']}/episode_{registered_task_index}.json"
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("episode_sha256"))):
            raise VerificationFailure(f"invalid attribution episode digest: {key}")
        if type(row.get("stored_task_design_verdict")) not in (bool, type(None)) or type(row.get("stored_disclosure_verdict")) not in (bool, type(None)):
            raise VerificationFailure(f"invalid stored attribution verdict type: {key}")
        if not isinstance(row.get("stage_field_observations"), list) or not isinstance(row.get("stage_shape"), list):
            raise VerificationFailure(f"invalid attribution stage receipt type: {key}")
        for index, observation in enumerate(row["stage_field_observations"]):
            if set(observation) != {"index", "name", "reason_observation", "evidence_observation"} or observation.get("index") != index or type(observation.get("name")) is not str:
                raise VerificationFailure(f"invalid attribution stage observation schema: {key}/{index}")
            verify_string_observation(observation["reason_observation"], f"{key}/stage/{index}/reason")
            verify_string_observation(observation["evidence_observation"], f"{key}/stage/{index}/evidence")
        for stage in row["stage_shape"]:
            if set(stage) != {"name", "required_values", "optional_fields_present"} or type(stage.get("name")) is not str or not isinstance(stage.get("required_values"), dict) or not isinstance(stage.get("optional_fields_present"), list):
                raise VerificationFailure(f"invalid attribution stage shape schema: {key}")
            optional_fields = stage["optional_fields_present"]
            if len(optional_fields) != len(set(optional_fields)) or any(
                type(field) is not str or field not in {"reason", "evidence"} for field in optional_fields
            ):
                raise VerificationFailure(f"invalid attribution optional-field enum: {key}")
        expected = expected_attribution_label(row)
        if (
            row.get("stored_attribution_label") != expected
            or row.get("reduction") != "REDUCTION_CONSISTENT"
            or row.get("input_binding") != "PARTIALLY_BOUND"
            or row.get("historical_input_observability") != "HISTORICAL_INPUT_UNVERIFIED"
            or row.get("exact_released_prompt_or_input_hash") is not False
            or row.get("episode_exists") is not True
            or row.get("episode_locator") != expected_episode
            or row.get("task_text_exact") is not True
        ):
            raise VerificationFailure(f"attribution row reduction/input mismatch: {key}")
    if attr_keys != target_keys:
        raise VerificationFailure("target/attribution key set mismatch")

    expected_packet_keys = {
        (run_id, user_id, category, dimension)
        for run_id, spec in RUN_REGISTRY.items() if spec["mode"] == "retrieve"
        for user_id, category, dimension in registered_targets
    }
    observed_packet_keys: set[tuple[str, str, str, str]] = set()
    for row_index, row in enumerate(packet_rows):
        if set(row) != {
            "cardinality", "category", "dimension", "packet_locator", "packet_schema", "packet_sha256",
            "run_id", "scoring_mode", "system", "user_id",
        }:
            raise VerificationFailure("packet row schema mismatch")
        key = (row["run_id"], row["user_id"], row["category"], row["dimension"])
        if key in observed_packet_keys or key not in expected_packet_keys:
            raise VerificationFailure(f"invalid/duplicate packet row key: {key}")
        observed_packet_keys.add(key)
        spec = RUN_REGISTRY[row["run_id"]]
        target = target_by_mode[(row["system"], row["user_id"], row["category"], row["dimension"], "retrieve")]
        if row.get("packet_schema") != "PASS" or type(row.get("cardinality")) is not int or not 0 <= row["cardinality"] <= 5:
            raise VerificationFailure("packet-row schema/cardinality mismatch")
        if (
            row.get("system") != spec["system"]
            or row.get("scoring_mode") != "retrieve"
            or row.get("packet_locator") != target["reconstruction_locator"] + "/retrieved_memories"
            or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("packet_sha256")))
        ):
            raise VerificationFailure(f"packet row linkage mismatch: {row_index}/{key}")
    if observed_packet_keys != expected_packet_keys:
        raise VerificationFailure("packet rows do not form the exact registered retrieve population")

    items_by_row: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in packet_items:
        if set(row) != {
            "adapter_schema", "candidate_store_pointers", "category", "dimension", "match_count",
            "membership_result", "packet_index", "packet_item_id", "packet_item_sha256",
            "packet_row_index", "run_id", "scoring_mode", "store_locator", "system", "user_id",
        }:
            raise VerificationFailure("packet item schema mismatch")
        count = row.get("match_count")
        expected_result = "NO_MATCH" if count == 0 else "EXACT_MEMBER" if count == 1 else "AMBIGUOUS_MEMBER"
        packet_row_index = row.get("packet_row_index")
        if type(packet_row_index) is not int or not 0 <= packet_row_index < len(packet_rows):
            raise VerificationFailure("packet item row index is out of range")
        packet_row = packet_rows[packet_row_index]
        item_key = (row["run_id"], row["user_id"], row["category"], row["dimension"])
        packet_key = (packet_row["run_id"], packet_row["user_id"], packet_row["category"], packet_row["dimension"])
        spec = RUN_REGISTRY[row["run_id"]]
        expected_store = f"memory/{spec['base']}/{row['user_id']}/memories.json#/memories"
        candidates = row.get("candidate_store_pointers", [])
        if (
            row.get("adapter_schema") != "PASS"
            or type(count) is not int
            or count != len(candidates)
            or row.get("membership_result") != expected_result
            or count != 1
            or item_key != packet_key
            or row.get("system") != packet_row.get("system")
            or row.get("system") != spec["system"]
            or row.get("scoring_mode") != packet_row.get("scoring_mode")
            or row.get("scoring_mode") != "retrieve"
            or row.get("store_locator") != expected_store
            or any(not re.fullmatch(re.escape(expected_store) + r"/[0-9]+", str(pointer)) for pointer in candidates)
            or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("packet_item_sha256")))
            or not valid_packet_identifier(row.get("packet_item_id"))
            or type(row.get("packet_index")) is not int
        ):
            raise VerificationFailure("packet item binding mismatch")
        items_by_row[packet_row_index].append(row)
    for index, row in enumerate(packet_rows):
        items = items_by_row[index]
        if len(items) != row["cardinality"] or {item.get("packet_index") for item in items} != set(range(row["cardinality"])):
            raise VerificationFailure(f"packet item/cardinality mismatch: {index}")

    cases = load_json(raw / "cases.json")
    verify_cases_receipt(cases, target_rows, packet_rows, packet_items)

    paired_keys = set()
    for row in paired_rows:
        if set(row) != {
            "category", "delta_scope", "dimension", "field_deltas", "full_run_id", "full_score",
            "noncausal_boundary", "retrieve_minus_full_score", "retrieve_run_id", "retrieve_score",
            "schema", "system", "user_id",
        } or row.get("schema") != "memprobe-paired-historical-artifact-delta/1":
            raise VerificationFailure("paired delta row schema mismatch")
        key = (row["system"], row["user_id"], row["category"], row["dimension"])
        if key in paired_keys or row.get("delta_scope") != "paired historical artifact delta" or row.get("noncausal_boundary") != "not_a_retrieval_effect_or_failure_estimate":
            raise VerificationFailure(f"paired delta scope/key mismatch: {key}")
        paired_keys.add(key)
        full_row = target_by_mode[(*key, "dump_all")]
        retrieve_row = target_by_mode[(*key, "retrieve")]
        full_score, retrieve_score = score_value(full_row["score"]), score_value(retrieve_row["score"])
        if score_value(row["full_score"]) != full_score or score_value(row["retrieve_score"]) != retrieve_score:
            raise VerificationFailure(f"paired score copy mismatch: {key}")
        if row.get("full_run_id") != full_row["run_id"] or row.get("retrieve_run_id") != retrieve_row["run_id"]:
            raise VerificationFailure(f"paired run identity mismatch: {key}")
        if fraction_record_value(row["retrieve_minus_full_score"]) != retrieve_score - full_score:
            raise VerificationFailure(f"paired score delta mismatch: {key}")
        expected_field_deltas = {}
        for field in ("predicted", "slot_fill_reason", "judge_reason"):
            left, right = full_row["output_states"][field], retrieve_row["output_states"][field]
            expected_field_deltas[field] = {
                "state_changed": left.get("state") != right.get("state"),
                "typed_value_digest_changed": left.get("sha256") != right.get("sha256"),
            }
        if not strict_equal(row.get("field_deltas"), expected_field_deltas):
            raise VerificationFailure(f"paired output-state delta mismatch: {key}")
    expected_paired_keys = {
        (spec["system"], user_id, category, dimension)
        for run_id, spec in RUN_REGISTRY.items() if spec["mode"] == "retrieve"
        for user_id, category, dimension in registered_targets
    }
    if paired_keys != expected_paired_keys:
        raise VerificationFailure("paired deltas do not form the exact registered full/retrieve population")

    observability = load_json(raw / "observability.json")
    for run_id, fields in output_counts.items():
        for field, counts in fields.items():
            if not strict_equal(observability["runs"][run_id][field], dict(sorted(counts.items()))):
                raise VerificationFailure(f"observability reduction mismatch: {run_id}/{field}")
    controls = load_json(raw / "mutation_controls.json")
    if controls.get("all_controls_pass") is not True or controls.get("control_count") != len(controls.get("controls", [])):
        raise VerificationFailure("mutation control summary mismatch")
    for row in controls["controls"]:
        if row.get("caught_expected_gate") is not True or row.get("original_hash_unchanged") is not True or row.get("unrelated_gates_stable") is not True:
            raise VerificationFailure(f"mutation control failed: {row.get('control')}")
    if (
        controls.get("official_parsed_objects_unchanged") is not True
        or controls.get("official_checkout_disk_bytes_unchanged") is not True
        or controls.get("official_parsed_objects_pre_sha256") != controls.get("official_parsed_objects_post_sha256")
        or controls.get("registered_input_manifest_pre_sha256") != controls.get("registered_input_manifest_post_sha256")
        or controls.get("composite_fixture_pre_sha256") != controls.get("composite_fixture_post_sha256")
        or controls.get("unrelated_gate_evaluation") != "full_composite_snapshot_per_isolated_mutation"
    ):
        raise VerificationFailure("mutation immutability/full-context receipt mismatch")
    checked_runner = runpy.run_path(str(root / "audit.py"))
    rerun_controls = checked_runner["run_mutation_controls"]()
    installed_control_core = {
        key: controls[key]
        for key in (
            "schema", "all_controls_pass", "composite_fixture_pre_sha256",
            "composite_fixture_post_sha256", "control_count", "controls",
            "unrelated_gate_evaluation",
        )
    }
    if not strict_equal(rerun_controls, installed_control_core):
        raise VerificationFailure("independent receipt-only synthetic control rerun mismatch")

    manifest = load_json(raw / "input_manifest.json")
    if (
        set(manifest) != {"inputs", "paper_sha256", "schema", "source_commit"}
        or manifest.get("schema") != "memprobe-input-manifest/1"
        or manifest.get("source_commit") != SOURCE_COMMIT
        or manifest.get("paper_sha256") != PAPER_SHA256
    ):
        raise VerificationFailure("input manifest authority mismatch")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise VerificationFailure("input manifest is empty")
    identities = set()
    for row in inputs:
        if not isinstance(row, dict) or set(row) != {"input_scope", "locator", "sha256", "size_bytes"}:
            raise VerificationFailure("input manifest row schema mismatch")
        identity = (row.get("input_scope"), row.get("locator"))
        if identity in identities or row.get("input_scope") not in {"official_source", "paper"}:
            raise VerificationFailure(f"invalid/duplicate input manifest row: {identity}")
        identities.add(identity)
        locator = row.get("locator")
        if type(locator) is not str or locator.startswith("/") or ".." in Path(locator).parts or not re.fullmatch(r"[A-Za-z0-9_. /-]+", locator):
            raise VerificationFailure(f"unsafe input locator: {locator!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256"))) or type(row.get("size_bytes")) is not int or row["size_bytes"] < 0:
            raise VerificationFailure(f"invalid input digest/size: {identity}")
    if controls.get("registered_input_manifest_pre_sha256") != typed_digest(inputs):
        raise VerificationFailure("mutation-control input-manifest digest is not bound to installed inputs")

    comparison = load_json(raw / "comparison.json")
    env_a = load_json(raw / "environment_run_a.json")
    env_b = load_json(raw / "environment_run_b.json")
    expected_environment_keys = {
        "schema", "architecture", "input_manifest_sha256", "locale", "network_attempt_count",
        "network_guard", "operating_system", "primary_manifest", "primary_manifest_digest",
        "python_hash_seed", "python_implementation", "python_version", "runner_sha256", "timezone",
    }
    if (
        set(env_a) != expected_environment_keys
        or set(env_b) != expected_environment_keys
        or env_a.get("schema") != "memprobe-audit-environment/1"
        or env_b.get("schema") != "memprobe-audit-environment/1"
        or any(type(env_a.get(key)) is not str or type(env_b.get(key)) is not str for key in (
            "architecture", "input_manifest_sha256", "locale", "network_guard", "operating_system",
            "primary_manifest_digest", "python_hash_seed", "python_implementation", "python_version",
            "runner_sha256", "timezone",
        ))
        or type(env_a.get("network_attempt_count")) is not int
        or type(env_b.get("network_attempt_count")) is not int
        or not isinstance(env_a.get("primary_manifest"), dict)
        or not isinstance(env_b.get("primary_manifest"), dict)
    ):
        raise VerificationFailure("environment receipt schema/type mismatch")
    installed_manifest = {name: sha256_file(raw / name) for name in sorted(PRIMARY_FILES)}
    if (
        comparison.get("runner_repeatability") != "PASS"
        or comparison.get("primary_receipts_byte_identical") is not True
        or comparison.get("seeds_distinct") is not True
        or comparison.get("environment_bindings") != "PASS"
        or comparison.get("source_and_input_identity") != "PASS"
        or comparison.get("differing_primary_files") != []
        or not strict_equal(comparison.get("run_a_primary_manifest"), installed_manifest)
        or not strict_equal(comparison.get("run_b_primary_manifest"), installed_manifest)
        or not strict_equal(env_a.get("primary_manifest"), installed_manifest)
        or not strict_equal(env_b.get("primary_manifest"), installed_manifest)
        or env_a.get("primary_manifest_digest") != typed_digest(installed_manifest)
        or env_b.get("primary_manifest_digest") != typed_digest(installed_manifest)
        or comparison.get("combined_primary_manifest_digest") != typed_digest(installed_manifest)
        or comparison.get("primary_file_count") != len(PRIMARY_FILES)
        or comparison.get("run_a_environment_sha256") != sha256_file(raw / "environment_run_a.json")
        or comparison.get("run_b_environment_sha256") != sha256_file(raw / "environment_run_b.json")
        or env_a.get("network_guard") != "PASS"
        or env_b.get("network_guard") != "PASS"
        or env_a.get("network_attempt_count") != 0
        or env_b.get("network_attempt_count") != 0
        or env_a.get("locale") != "C"
        or env_b.get("locale") != "C"
        or env_a.get("timezone") != "UTC"
        or env_b.get("timezone") != "UTC"
        or env_a.get("python_hash_seed") == "UNSET"
        or env_b.get("python_hash_seed") == "UNSET"
        or env_a.get("python_hash_seed") == env_b.get("python_hash_seed")
        or any(env_a.get(key) != env_b.get(key) for key in (
            "architecture", "operating_system", "python_implementation", "python_version",
        ))
        or env_a.get("runner_sha256") != sha256_file(root / "audit.py")
        or env_b.get("runner_sha256") != sha256_file(root / "audit.py")
        or env_a.get("input_manifest_sha256") != installed_manifest["input_manifest.json"]
        or env_b.get("input_manifest_sha256") != installed_manifest["input_manifest.json"]
    ):
        raise VerificationFailure("repeatability/environment binding mismatch")

    recomputed_fixed_gates = {
        "aggregate_reports": arithmetic.get("aggregate_report_gate") is True,
        "attribution_input_linkage": (
            len(attr_rows) == 13950
            and all(
                row.get("input_binding") == "PARTIALLY_BOUND" and row.get("task_text_exact") is True
                for row in attr_rows
            )
        ),
        "attribution_reduction": (
            len(attr_rows) == 13950
            and all(row.get("reduction") == "REDUCTION_CONSISTENT" for row in attr_rows)
        ),
        "checkout_immutable": (
            controls.get("official_checkout_disk_bytes_unchanged") is True
            and controls.get("official_parsed_objects_unchanged") is True
            and controls.get("official_parsed_objects_pre_sha256") == controls.get("official_parsed_objects_post_sha256")
            and controls.get("registered_input_manifest_pre_sha256") == controls.get("registered_input_manifest_post_sha256")
        ),
        "fixed_score_arithmetic": (
            set(arithmetic_runs) == RUN_IDS
            and all(row.get("stored_user_arithmetic_checks_pass") is True for row in arithmetic_runs.values())
        ),
        "mutation_controls": (
            controls.get("all_controls_pass") is True
            and controls.get("control_count") == len(controls.get("controls", []))
            and all(
                row.get("caught_expected_gate") is True
                and row.get("original_hash_unchanged") is True
                and row.get("unrelated_gates_stable") is True
                for row in controls.get("controls", [])
            )
        ),
        "network_guard": (
            env_a.get("network_guard") == env_b.get("network_guard") == "PASS"
            and env_a.get("network_attempt_count") == env_b.get("network_attempt_count") == 0
        ),
        "packet_membership_complete": (
            len(packet_items) == 30379
            and all(type(row.get("match_count")) is int and row["match_count"] >= 1 for row in packet_items)
        ),
        "packet_schema": (
            len(packet_rows) == 6200
            and all(row.get("packet_schema") == "PASS" for row in packet_rows)
            and all(row.get("adapter_schema") == "PASS" for row in packet_items)
        ),
        "public_population": len(target_rows) == len(attr_rows) == 13950,
        "target_identity": (
            len(target_rows) == 13950
            and all(all(value is True for value in row["join"].values()) for row in target_rows)
        ),
    }
    if not strict_equal(decision["fixed_artifact_gates"], recomputed_fixed_gates) or any(
        value is not True for value in recomputed_fixed_gates.values()
    ):
        raise VerificationFailure("decision fixed-artifact gates are not bound to exhaustive receipt/environment evidence")
    return {
        "input_count": len(inputs),
        "packet_item_count": len(packet_items),
        "primary_manifest": installed_manifest,
        "target_count": len(target_rows),
    }


def verify_source_bound(root: Path, source: Path, paper_pdf: Path, receipt_summary: dict[str, Any]) -> None:
    if run_git(source, "rev-parse", "HEAD") != SOURCE_COMMIT:
        raise VerificationFailure("reader source checkout is at the wrong revision")
    if run_git(source, "status", "--porcelain=v1", "--untracked-files=all"):
        raise VerificationFailure("reader source checkout is dirty")
    if not paper_pdf.is_file() or sha256_file(paper_pdf) != PAPER_SHA256:
        raise VerificationFailure("reader paper PDF hash mismatch")
    manifest = load_json(root / "raw/input_manifest.json")
    for row in manifest["inputs"]:
        path = paper_pdf if row["input_scope"] == "paper" else source / row["locator"]
        if not path.is_file() or path.stat().st_size != row["size_bytes"] or sha256_file(path) != row["sha256"]:
            raise VerificationFailure(f"source-bound input mismatch: {row['input_scope']}:{row['locator']}")

    with tempfile.TemporaryDirectory(prefix="memprobe-source-bound-") as temp_dir:
        output = Path(temp_dir) / "run"
        env = os.environ.copy()
        env.update({"LC_ALL": "C", "TZ": "UTC", "PYTHONHASHSEED": "909", "PYTHONDONTWRITEBYTECODE": "1"})
        result = subprocess.run(
            [
                sys.executable,
                str(root / "audit.py"),
                "run",
                "--source", str(source),
                "--paper-pdf", str(paper_pdf),
                "--output", str(output),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            raise VerificationFailure(f"fresh source-bound audit failed: {result.stderr.strip() or result.stdout.strip()}")
        fresh_manifest = {name: sha256_file(output / "primary" / name) for name in sorted(PRIMARY_FILES)}
        if not strict_equal(fresh_manifest, receipt_summary["primary_manifest"]):
            differences = sorted(name for name in PRIMARY_FILES if fresh_manifest.get(name) != receipt_summary["primary_manifest"].get(name))
            raise VerificationFailure(f"fresh source-bound receipt mismatch: {differences}")
    if run_git(source, "status", "--porcelain=v1", "--untracked-files=all"):
        raise VerificationFailure("source-bound verifier changed the official checkout")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("receipt-only", "source-bound"), default="receipt-only")
    parser.add_argument("--artifact-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--paper-pdf", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.artifact_root.resolve()
    try:
        verify_tree(root)
        verify_checksums(root)
        verify_public_package(root)
        summary = verify_receipt_logic(root)
        if args.mode == "source-bound":
            if args.source is None or args.paper_pdf is None:
                raise VerificationFailure("source-bound mode requires --source and --paper-pdf")
            verify_source_bound(root, args.source.resolve(), args.paper_pdf.resolve(), summary)
            print("PASS: source-bound revalidation; worked_fixed_artifact_audit=PASS")
        else:
            print("PASS: receipt-only integrity; original evidence not revalidated")
    except (VerificationFailure, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
