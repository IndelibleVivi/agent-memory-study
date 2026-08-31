#!/usr/bin/env python3
"""Deterministic, model-free audit of the exact current Memory-Collapse release.

The audit checks released arm/row membership, denominator observability,
official-verifier scope, selected AppWorld schedule fixtures, registered curve
descriptions, mutation sensitivity, and two-root repeatability. It does not run
models, agent environments, or paper experiments.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable


EXPECTED_COMMIT = "adf347f67a81a19fc71d2529d09108c71a1f9712"
EXPECTED_TREE = "5b79bbfbc93e6cc681aaf0fe1dcb916abab0aa2c"
EXPECTED_PAPER_SHA256 = (
    "16613d73b3dfe8de8dd73d42c4fb7b2e803b84a78d7ecf748c9e23a7e3b4aa92"
)
EXPECTED_SOURCE_INPUTS_SHA256 = (
    "7cd1838ab9fa23a4f960cd0534a9dc8e98b7e8a69a551f98eb872bff075eb2fd"
)
EXPECTED_SOURCE_LOCK_RECEIPT_SHA256 = (
    "47b1b4dfe89fb13701d6f467d6cd6b32febad1f69c87c6c8901c179158063118"
)
EXPECTED_ASSERTION_MANIFEST_SHA256 = (
    "9500315457cf400bf31acf5906f2830988a065bf572c55fa0b6f66ff2d4cf287"
)
EXPECTED_MEMBERSHIP_RECEIPT_SHA256 = (
    "121bb526fafdd1c5a9e1ca966caa1de3d7886af498cf14a2fcade02f57dccad1"
)
EXPECTED_DENOMINATOR_RECEIPT_SHA256 = (
    "e1d1a8753a709da7189d60ef199b80a879f0da0b29065038773f75504a9484da"
)
EXPECTED_OFFICIAL_RECEIPT_SHA256 = (
    "e809455d2880b9ad92b9097213b5de83de6c6905ea85c1d2ee6eabf96c24c1f5"
)
EXPECTED_SCHEDULE_RECEIPT_SHA256 = (
    "f905143957e819aecbf29299fb30374514ce49ffffe034687011b9ffbc09b249"
)
EXPECTED_CURVES_RECEIPT_SHA256 = (
    "1b48e1934b61caf305e9d8642fd074775b8ee6bdc30ca7f8dd8947d2c184fb4f"
)
EXPECTED_CONTROL_RECEIPT_SHA256 = (
    "e21bd044ab9cb668e0c60870acc6e0e533d85fb3c3f5965694c06bcffca4bb4d"
)
EXPECTED_AUDIT_RECEIPT_SHA256 = (
    "607519d925a4c292ee544318d296dc264244610f2bf95dc18800db34d45f7c44"
)

INTERACTIVE_HEADER = [
    "arm",
    "archive_cell",
    "method",
    "variant",
    "checkpoint_n",
    "condition",
    "backbone",
    "n_tasks",
    "n_valid",
    "n_success",
]
ARC_HEADER = [
    "arm",
    "archive_cell",
    "line",
    "method",
    "variant",
    "memory_arm",
    "checkpoint_n",
    "pool",
    "epoch",
    "caliber",
    "backbone",
    "n_samples",
    "n_tasks",
    "n_rows",
    "n_success",
]

EXPERIMENTS: dict[str, dict[str, Any]] = {
    "alfworld_examine-rulebook-escape-hatch": {
        "label": "ALFWorld",
        "kind": "interactive",
        "identity": "idx",
        "valid_marker": "task_name",
        "arms": 48,
        "rows": 4_320,
        "valid": 4_309,
        "invalid": 11,
        "affected_arms": 9,
    },
    "sciworld_cross-family-shortcut-contamination": {
        "label": "ScienceWorld",
        "kind": "interactive",
        "identity": "idx",
        "valid_marker": "task_name",
        "arms": 30,
        "rows": 1_500,
        "valid": 1_212,
        "invalid": 288,
        "affected_arms": 30,
    },
    "webshop_retrieval-hijack": {
        "label": "WebShop",
        "kind": "interactive",
        "identity": "idx",
        "valid_marker": "task_name",
        "arms": 391,
        "rows": 19_550,
        "valid": 19_545,
        "invalid": 5,
        "affected_arms": 1,
    },
    "appworld_feed-order-same-pool": {
        "label": "AppWorld",
        "kind": "interactive",
        "identity": "task_id",
        "valid_marker": "task_id",
        "arms": 212,
        "rows": 10_365,
        "valid": 10_365,
        "invalid": 0,
        "affected_arms": 0,
    },
    "arc_stream-self-eval": {
        "label": "ARC stream/self-eval",
        "kind": "arc",
        "arms": 48,
        "rows": 2_840,
    },
    "arc_200task-stream": {
        "label": "ARC 200-task stream",
        "kind": "arc",
        "arms": 33,
        "rows": 16_500,
    },
}

INTERACTIVE_META = (
    "archive_cell",
    "method",
    "variant",
    "checkpoint_n",
    "condition",
    "backbone",
)
ARC_META = (
    "archive_cell",
    "line",
    "method",
    "variant",
    "memory_arm",
    "checkpoint_n",
    "pool",
    "epoch",
    "caliber",
    "backbone",
)

MAPPED_TABLES = (
    "results/sciworld_cross-family-shortcut-contamination/numbers/trend_8methods.csv",
    "results/sciworld_cross-family-shortcut-contamination/numbers/eval_8methods_success_and_rawscore.csv",
    "results/alfworld_examine-rulebook-escape-hatch/numbers/总体_25臂_vsN.csv",
    "results/alfworld_examine-rulebook-escape-hatch/numbers/长程x2_second_loop_8方法.csv",
    "results/appworld_feed-order-same-pool/numbers/当前混序_全框架_成功率.csv",
    "results/appworld_feed-order-same-pool/numbers/chain对照_adversarial_vs_normal.csv",
    "results/appworld_feed-order-same-pool/numbers/检索vs注入_混序.csv",
    "results/appworld_feed-order-same-pool/numbers/ACE重排_排序对N-grid.csv",
    "results/appworld_feed-order-same-pool/numbers/全stream_TGC与构成.csv",
    "results/webshop_retrieval-hijack/numbers/results_retrieval_hijack.csv",
    "results/webshop_retrieval-hijack/numbers/n400_longhorizon_gpt.csv",
    "results/arc_stream-self-eval/numbers/cells.csv",
    "results/arc_200task-stream/numbers/cells.csv",
)

SELECTED_POOLS = {
    "natural": "results/appworld_feed-order-same-pool/pools/stream_pool_v2.jsonl",
    "A": "results/appworld_feed-order-same-pool/pools/pool_A.jsonl",
    "B": "results/appworld_feed-order-same-pool/pools/pool_B.jsonl",
    "succdrop": "results/appworld_feed-order-same-pool/pools/pool_succdrop.jsonl",
}
EXCEPTION_POOLS = {
    "content_intervention_D": "results/appworld_feed-order-same-pool/pools/pool_D.jsonl",
    "drop50_subset": "results/appworld_feed-order-same-pool/pools/pool_drop50.jsonl",
    "replay2_duplication": "results/appworld_feed-order-same-pool/pools/pool_replay2.jsonl",
}

SCIENCE_CURVE_REGISTRY = (
    ("langmem", "langmem"),
    ("mem0", "mem0"),
    ("reasoningbank", "rb"),
    ("letta", "letta"),
    ("ACE", "ace"),
    ("AWM", "awm"),
    ("proplay", "proplay"),
)
SCIENCE_CURVE_CHECKPOINTS = (100, 200, 300, 400)
APP_CURVE_REGISTRY = (
    ("当前混序", "ace", ("N25", "N50", "N100", "N150", "N200")),
    ("A难度升序", "aceA", ("N25", "N50", "N100", "N150", "N200")),
    ("B成功降序", "aceB", ("N25", "N50", "N85", "N100", "N150", "N200")),
    (
        "C成功率平滑下降(succdrop)",
        "acesuccdrop",
        ("N25", "N50", "N100", "N150", "N200"),
    ),
)

EXPECTED_FALLBACKS = {
    (
        "runs/mix6_rulebook_gpt/eval/dc_x2_n300",
        "runs/mix6_rulebook_gpt/eval/dc_n300",
    ),
    (
        "runs/mix6_rulebook_gpt/eval/awm_x2_n300",
        "runs/mix6_rulebook_gpt/eval/awm_n300",
    ),
}

EXPECTED_PACKAGE_FILES = {
    "PROTOCOL.md",
    "REVIEW-AMENDMENT.md",
    "REVIEW-AMENDMENT-2.md",
    "README.md",
    "audit.py",
    "verify_checked.py",
    "raw/audit.json",
    "raw/environment_run_a.json",
    "raw/environment_run_b.json",
    "raw/mutation-controls.json",
    "raw/repeatability.json",
}
STABLE_RUN_FILES = ("audit.json", "mutation-controls.json")

NEGATIVE_CONTROL_CODES = (
    ("duplicate_interactive_row_identity", "ROW_IDENTITY_UNIQUE"),
    ("delete_mapped_failure_row_with_success_count_unchanged", "AGGREGATE_MATCH"),
    ("delete_invalid_refusal_row", "AGGREGATE_MATCH"),
    ("delete_unasserted_arm_and_matching_arms_row", "PINNED_TOTALS"),
    ("change_arms_csv_denominator", "AGGREGATE_MATCH"),
    ("string_false_success", "SUCCESS_BOOL"),
    ("delete_arc_sample_task_cell", "ARC_RECTANGULAR_GRID"),
    ("shrink_mapped_tables_to_headers", "OFFICIAL_ASSERTION_COUNT"),
    ("unexpected_generic_fallback", "OFFICIAL_FALLBACK_ALLOWLIST"),
    ("pool_content_tamper_with_ids_preserved", "POOL_CONTENT_MULTISET_EQUAL"),
    ("pool_delete_one_duplicate_another", "POOL_TASK_ID_UNIQUE"),
    ("relabel_assertion_count_as_unique_arm_count", "COVERAGE_UNIT_DISTINCT"),
    ("relabel_missing_outcome_as_observed_failure", "MISSINGNESS_LABEL"),
    ("duplicate_one_drop_one_science_curve_method", "CURVE_REGISTRY_UNIQUE"),
    ("duplicate_one_drop_one_app_curve_checkpoint", "CURVE_REGISTRY_UNIQUE"),
    ("clear_selected_pool_task_id", "POOL_TASK_ID_PRESENT"),
    ("remove_invalid_interactive_success_field", "SUCCESS_BOOL"),
)
POSITIVE_CONTROL_CASES = (
    "appworld_null_task_name_remains_valid_by_task_id",
    "curve_csv_row_order_invariant",
)


class AuditFailure(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise AuditFailure(code, detail)


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_bytes(value))


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, "JSON_DUPLICATE_KEY", key)
        value[key] = item
    return value


def read_json_object(path: Path) -> dict[str, Any]:
    require(path.is_file(), "JSON_FILE", path.name)
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditFailure("JSON_PARSE", f"{path.name}: {exc}") from exc
    require(isinstance(value, dict), "JSON_OBJECT", path.name)
    require(raw == canonical_bytes(value), "JSON_CANONICAL_BYTES", path.name)
    return value


def exact_json_equal(observed: Any, expected: Any) -> bool:
    if type(observed) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(observed) == set(expected) and all(
            exact_json_equal(observed[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(observed) == len(expected) and all(
            exact_json_equal(left, right)
            for left, right in zip(observed, expected, strict=True)
        )
    return observed == expected


def require_exact_json_equal(
    observed: Any, expected: Any, code: str, detail: str
) -> None:
    require(exact_json_equal(observed, expected), code, detail)


def require_exact_keys(
    value: dict[str, Any], expected: Iterable[str], code: str, detail: str
) -> None:
    expected_set = set(expected)
    require(
        set(value) == expected_set,
        code,
        f"{detail}: got={sorted(value)} expected={sorted(expected_set)}",
    )


def require_sha256(value: Any, code: str, detail: str) -> None:
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        code,
        detail,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def git_output(source: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(source), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    require(
        result.returncode == 0,
        "GIT_COMMAND",
        f"git {' '.join(args)} failed: {result.stderr.strip()}",
    )
    return result.stdout.strip()


def normalized(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def int_field(row: dict[str, Any], field: str, context: str) -> int:
    raw = row.get(field)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise AuditFailure("INTEGER_FIELD", f"{context}.{field}={raw!r}") from exc
    require(not isinstance(raw, bool), "INTEGER_FIELD", f"{context}.{field} is bool")
    return value


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AuditFailure(
                    "JSONL_PARSE", f"{path.name}:{line_number}: {exc.msg}"
                ) from exc
            require(isinstance(row, dict), "JSONL_OBJECT", f"{path.name}:{line_number}")
            rows.append(row)
    return rows


def is_valid_interactive(config: dict[str, Any], row: dict[str, Any]) -> bool:
    marker = config["valid_marker"]
    return bool(row.get(marker)) and not row.get("error") and not row.get("skipped")


def identity_value(config: dict[str, Any], row: dict[str, Any]) -> tuple[Any, ...]:
    if config["kind"] == "arc":
        return (row.get("arm"), row.get("sample"), row.get("task_id"))
    return (row.get("arm"), row.get(config["identity"]))


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def decimal_text(value: Fraction, places: int = 6) -> str:
    rendered = f"{float(value):.{places}f}".rstrip("0").rstrip(".")
    return rendered or "0"


def rate_payload(success: int, denominator: int) -> dict[str, Any]:
    require(denominator > 0, "ZERO_DENOMINATOR", f"success={success}")
    rate = Fraction(success, denominator)
    return {
        "numerator": success,
        "denominator": denominator,
        "fraction": fraction_text(rate),
        "percent": decimal_text(rate * 100),
    }


def schema_counts(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(tuple(sorted(row)) for row in rows)
    return [
        {"fields": list(fields), "rows": count}
        for fields, count in sorted(counts.items())
    ]


def _metadata_match(
    config: dict[str, Any], arm_row: dict[str, Any], row: dict[str, Any], context: str
) -> None:
    fields = ARC_META if config["kind"] == "arc" else INTERACTIVE_META
    for field in fields:
        require(
            normalized(row.get(field)) == normalized(arm_row.get(field)),
            "ARM_METADATA_MATCH",
            f"{context}.{field}: row={row.get(field)!r} arms={arm_row.get(field)!r}",
        )


def validate_experiment(
    experiment: str,
    config: dict[str, Any],
    arms_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    enforce_expected: bool,
) -> dict[str, Any]:
    arm_ids = [row.get("arm") for row in arms_rows]
    require(all(isinstance(arm, str) and arm for arm in arm_ids), "ARM_ID", experiment)
    require(len(arm_ids) == len(set(arm_ids)), "ARM_ID_UNIQUE", experiment)
    arms = {str(row["arm"]): row for row in arms_rows}

    row_arm_ids = {row.get("arm") for row in rows}
    require(
        row_arm_ids == set(arms),
        "ARM_ROW_SET_EQUAL",
        f"{experiment}: csv_only={sorted(set(arms) - row_arm_ids)} "
        f"rows_only={sorted(row_arm_ids - set(arms))}",
    )

    identities: list[tuple[Any, ...]] = []
    rows_by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows):
        arm = row.get("arm")
        require(isinstance(arm, str) and arm in arms, "ROW_ARM", f"{experiment}:{index}")
        identity = identity_value(config, row)
        require(
            all(value is not None and value != "" for value in identity),
            "ROW_IDENTITY_PRESENT",
            f"{experiment}:{index}:{identity!r}",
        )
        identities.append(identity)
        success = row.get("success")
        require(
            "success" in row and type(success) is bool,
            "SUCCESS_BOOL",
            f"{experiment}:{identity!r}",
        )
        rows_by_arm[arm].append(row)

    require(
        len(identities) == len(set(identities)),
        "ROW_IDENTITY_UNIQUE",
        experiment,
    )

    stats: dict[str, dict[str, Any]] = {}
    invalid_reasons = Counter()
    for arm in sorted(arms):
        arm_rows = rows_by_arm[arm]
        for row in arm_rows:
            _metadata_match(config, arms[arm], row, f"{experiment}:{arm}")

        all_identity_keys = {
            json.dumps(identity_value(config, row)[1:], ensure_ascii=False, separators=(",", ":"))
            for row in arm_rows
        }
        if config["kind"] == "interactive":
            valid_rows = [row for row in arm_rows if is_valid_interactive(config, row)]
            for row in arm_rows:
                if row in valid_rows:
                    require(
                        type(row.get("success")) is bool,
                        "SUCCESS_BOOL",
                        f"{experiment}:{arm}",
                    )
                    continue
                reasons = []
                if not row.get(config["valid_marker"]):
                    reasons.append("missing_marker")
                if row.get("error"):
                    reasons.append("error")
                if row.get("skipped"):
                    reasons.append("skipped")
                require(reasons, "INVALID_REASON", f"{experiment}:{identity_value(config, row)!r}")
                require(row.get("success") is not True, "INVALID_TRUE_SUCCESS", f"{experiment}:{arm}")
                invalid_reasons["+".join(reasons)] += 1

            n_tasks = len(arm_rows)
            n_valid = len(valid_rows)
            n_success = sum(row.get("success") is True for row in valid_rows)
            require(
                n_tasks == int_field(arms[arm], "n_tasks", f"{experiment}:{arm}"),
                "AGGREGATE_MATCH",
                f"{experiment}:{arm}:n_tasks",
            )
            require(
                n_valid == int_field(arms[arm], "n_valid", f"{experiment}:{arm}"),
                "AGGREGATE_MATCH",
                f"{experiment}:{arm}:n_valid",
            )
            require(
                n_success == int_field(arms[arm], "n_success", f"{experiment}:{arm}"),
                "AGGREGATE_MATCH",
                f"{experiment}:{arm}:n_success",
            )
            score_total = Fraction(0, 1)
            for row in valid_rows:
                raw_score = row.get("final_score")
                if raw_score is None:
                    raw_score = row.get("pass_percentage", 0)
                score_total += Fraction(str(raw_score or 0))
            valid_identity_keys = {
                json.dumps(identity_value(config, row)[1:], ensure_ascii=False, separators=(",", ":"))
                for row in valid_rows
            }
            stats[arm] = {
                "n_tasks": n_tasks,
                "n_valid": n_valid,
                "n_success": n_success,
                "mean_score": score_total / n_valid,
                "all_identity_keys": all_identity_keys,
                "valid_identity_keys": valid_identity_keys,
            }
        else:
            for row in arm_rows:
                require(type(row.get("success")) is bool, "SUCCESS_BOOL", f"{experiment}:{arm}")
            samples: dict[Any, set[Any]] = defaultdict(set)
            sample_success: dict[Any, int] = defaultdict(int)
            for row in arm_rows:
                sample = row["sample"]
                task_id = row["task_id"]
                require(task_id not in samples[sample], "ROW_IDENTITY_UNIQUE", f"{experiment}:{arm}")
                samples[sample].add(task_id)
                sample_success[sample] += row["success"] is True
            ordered_samples = sorted(samples, key=lambda value: (str(type(value)), str(value)))
            first_tasks = samples[ordered_samples[0]]
            require(
                all(samples[sample] == first_tasks for sample in ordered_samples),
                "ARC_RECTANGULAR_GRID",
                f"{experiment}:{arm}:task sets differ",
            )
            n_samples = len(samples)
            n_tasks = len(first_tasks)
            n_rows = len(arm_rows)
            n_success = sum(sample_success.values())
            require(
                n_rows == n_samples * n_tasks,
                "ARC_RECTANGULAR_GRID",
                f"{experiment}:{arm}:{n_rows}!={n_samples}*{n_tasks}",
            )
            for field, got in (
                ("n_samples", n_samples),
                ("n_tasks", n_tasks),
                ("n_rows", n_rows),
                ("n_success", n_success),
            ):
                require(
                    got == int_field(arms[arm], field, f"{experiment}:{arm}"),
                    "AGGREGATE_MATCH",
                    f"{experiment}:{arm}:{field}",
                )
            rates = [Fraction(sample_success[sample], n_tasks) for sample in ordered_samples]
            stats[arm] = {
                "n_samples": n_samples,
                "n_tasks": n_tasks,
                "n_rows": n_rows,
                "n_success": n_success,
                "sample_rates": rates,
                "all_identity_keys": all_identity_keys,
                "valid_identity_keys": all_identity_keys,
            }

    if enforce_expected:
        require(len(arms) == config["arms"], "PINNED_TOTALS", f"{experiment}:arms")
        require(len(rows) == config["rows"], "PINNED_TOTALS", f"{experiment}:rows")
        if config["kind"] == "interactive":
            total_valid = sum(stat["n_valid"] for stat in stats.values())
            require(total_valid == config["valid"], "PINNED_TOTALS", f"{experiment}:valid")

    arm_ledger = []
    for arm, stat in sorted(stats.items()):
        if config["kind"] == "interactive":
            row = {
                "arm": arm,
                "n_tasks": stat["n_tasks"],
                "n_valid": stat["n_valid"],
                "n_success": stat["n_success"],
            }
        else:
            row = {
                "arm": arm,
                "n_samples": stat["n_samples"],
                "n_tasks": stat["n_tasks"],
                "n_rows": stat["n_rows"],
                "n_success": stat["n_success"],
            }
        arm_ledger.append(row)

    return {
        "arms": arms,
        "arms_rows": arms_rows,
        "rows": rows,
        "rows_by_arm": rows_by_arm,
        "stats": stats,
        "public": {
            "experiment": experiment,
            "label": config["label"],
            "kind": config["kind"],
            "arm_count": len(arms),
            "row_count": len(rows),
            "valid_row_count": (
                sum(stat["n_valid"] for stat in stats.values())
                if config["kind"] == "interactive"
                else len(rows)
            ),
            "invalid_row_count": (
                len(rows) - sum(stat["n_valid"] for stat in stats.values())
                if config["kind"] == "interactive"
                else 0
            ),
            "invalid_reason_counts": dict(sorted(invalid_reasons.items())),
            "schema_variants": schema_counts(rows),
            "arm_ledger_sha256": digest_value(arm_ledger),
            "row_identity_ledger_sha256": digest_value(
                sorted(
                    [list(identity) for identity in identities],
                    key=lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True),
                )
            ),
            "metadata_mismatches": 0,
            "duplicate_row_identities": 0,
        },
    }


def selected_input_paths() -> list[str]:
    paths = [
        "Makefile",
        "results/README.md",
        "results/verify_numbers.py",
        "results/appworld_feed-order-same-pool/README.md",
    ]
    for experiment in EXPERIMENTS:
        paths.extend(
            [
                f"results/{experiment}/arms.csv",
                f"results/{experiment}/per-task-results.jsonl",
            ]
        )
    paths.extend(MAPPED_TABLES)
    paths.extend(SELECTED_POOLS.values())
    paths.extend(EXCEPTION_POOLS.values())
    return sorted(set(paths))


def normalize_repository_origin(raw: str) -> str:
    value = raw.strip().removesuffix(".git").removesuffix("/")
    prefixes = (
        "https://github.com/",
        "http://github.com/",
        "ssh://git@github.com/",
        "git@github.com:",
    )
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    require(value == "DylanZSZ/Memory-Collapse-Eval", "SOURCE_ORIGIN", raw)
    return value


def source_manifest_pre(source: Path, paper_pdf: Path) -> dict[str, Any]:
    require(source.is_dir(), "SOURCE_DIRECTORY", source.name)
    require(paper_pdf.is_file(), "PAPER_FILE", paper_pdf.name)
    commit = git_output(source, "rev-parse", "HEAD")
    require(commit == EXPECTED_COMMIT, "SOURCE_COMMIT", commit)
    tree = git_output(source, "rev-parse", "HEAD^{tree}")
    require(tree == EXPECTED_TREE, "SOURCE_TREE", tree)
    status = git_output(source, "status", "--porcelain=v1", "--untracked-files=all")
    require(not status, "SOURCE_DIRTY", status)
    tags = sorted(filter(None, git_output(source, "tag", "--list").splitlines()))
    require(tags == [], "SOURCE_TAGS", repr(tags))
    origin = normalize_repository_origin(git_output(source, "remote", "get-url", "origin"))
    discovered_experiments = sorted(
        path.parent.name for path in source.glob("results/*/arms.csv")
    )
    require(
        discovered_experiments == sorted(EXPERIMENTS),
        "EXPERIMENT_DISCOVERY",
        repr(discovered_experiments),
    )
    paper_digest = sha256_file(paper_pdf)
    require(paper_digest == EXPECTED_PAPER_SHA256, "PAPER_DIGEST", paper_digest)

    inputs = []
    for rel in selected_input_paths():
        path = source / rel
        require(path.is_file(), "SOURCE_INPUT_MISSING", rel)
        inputs.append(
            {
                "path": rel,
                "git_blob_oid": git_output(source, "rev-parse", f"HEAD:{rel}"),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    require(
        digest_value(inputs) == EXPECTED_SOURCE_INPUTS_SHA256,
        "SOURCE_INPUT_MANIFEST",
        digest_value(inputs),
    )

    return {
        "paper": {
            "identity": "arXiv:2605.12978v1",
            "sha256": paper_digest,
            "bytes": paper_pdf.stat().st_size,
            "pages": 69,
        },
        "source": {
            "repository": origin,
            "origin_verified": True,
            "commit": commit,
            "tree": tree,
            "commit_count": int(git_output(source, "rev-list", "--count", "HEAD")),
            "commit_date": git_output(source, "show", "-s", "--format=%cI", "HEAD"),
            "local_tags": tags,
            "discovered_experiments": discovered_experiments,
            "tracked_status_pre": "clean",
            "paper_production_binding": "NOT_ESTABLISHED",
            "audit_target": "exact_current_public_release",
            "inputs": inputs,
        },
    }


def source_manifest_post(source: Path, manifest: dict[str, Any]) -> None:
    status = git_output(source, "status", "--porcelain=v1", "--untracked-files=all")
    require(not status, "SOURCE_DIRTY_POST", status)
    require(git_output(source, "rev-parse", "HEAD") == EXPECTED_COMMIT, "SOURCE_COMMIT_POST", "changed")
    require(git_output(source, "rev-parse", "HEAD^{tree}") == EXPECTED_TREE, "SOURCE_TREE", "changed")
    require(not git_output(source, "tag", "--list"), "SOURCE_TAGS", "changed")
    normalize_repository_origin(git_output(source, "remote", "get-url", "origin"))
    for item in manifest["source"]["inputs"]:
        require(
            sha256_file(source / item["path"]) == item["sha256"],
            "SOURCE_INPUT_CHANGED",
            item["path"],
        )
    manifest["source"]["tracked_status_post"] = "clean"
    manifest["source"]["input_bytes_unchanged"] = True


def load_release(source: Path, traversal_seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    state: dict[str, Any] = {}
    public_experiments = []
    for offset, experiment in enumerate(sorted(EXPERIMENTS)):
        config = EXPERIMENTS[experiment]
        root = source / "results" / experiment
        header, arms_rows = read_csv(root / "arms.csv")
        expected_header = ARC_HEADER if config["kind"] == "arc" else INTERACTIVE_HEADER
        require(header == expected_header, "ARMS_HEADER", experiment)
        rows = read_jsonl(root / "per-task-results.jsonl")
        shuffled = list(rows)
        random.Random(f"{traversal_seed}:{offset}:{experiment}").shuffle(shuffled)
        result = validate_experiment(
            experiment,
            config,
            arms_rows,
            shuffled,
            enforce_expected=True,
        )
        # Preserve source order only for mutation fixture selection. All stable
        # derivations are canonicalized by explicit keys.
        result["source_order_rows"] = rows
        state[experiment] = result
        public_experiments.append(result["public"])

    totals = {
        "experiments": len(state),
        "arms": sum(item["public"]["arm_count"] for item in state.values()),
        "rows": sum(item["public"]["row_count"] for item in state.values()),
        "valid_rows": sum(item["public"]["valid_row_count"] for item in state.values()),
        "invalid_rows": sum(item["public"]["invalid_row_count"] for item in state.values()),
    }
    require(totals == {
        "experiments": 6,
        "arms": 762,
        "rows": 55_075,
        "valid_rows": 54_771,
        "invalid_rows": 304,
    }, "PINNED_TOTALS", repr(totals))
    return state, {
        "status": "PASS",
        "identity_rules": {
            "ALFWorld/ScienceWorld/WebShop": ["arm", "idx"],
            "AppWorld": ["arm", "task_id"],
            "ARC": ["arm", "sample", "task_id"],
        },
        "totals": totals,
        "experiments": sorted(public_experiments, key=lambda item: item["experiment"]),
    }


def denominator_receipt(state: dict[str, Any]) -> dict[str, Any]:
    affected = []
    invalid_by_experiment: dict[str, int] = {}
    affected_by_experiment: dict[str, int] = {}
    max_delta = Fraction(-1, 1)
    max_identity = None
    for experiment, config in EXPERIMENTS.items():
        if config["kind"] != "interactive":
            continue
        experiment_state = state[experiment]
        invalid = sum(
            stat["n_tasks"] - stat["n_valid"]
            for stat in experiment_state["stats"].values()
        )
        invalid_by_experiment[experiment] = invalid
        count = 0
        for arm, stat in sorted(experiment_state["stats"].items()):
            if stat["n_tasks"] == stat["n_valid"]:
                continue
            count += 1
            task_rate = Fraction(stat["n_success"], stat["n_tasks"])
            valid_rate = Fraction(stat["n_success"], stat["n_valid"])
            delta = (valid_rate - task_rate) * 100
            if delta > max_delta:
                max_delta = delta
                max_identity = (experiment, arm)
            affected.append(
                {
                    "experiment": experiment,
                    "arm": arm,
                    "invalid_rows": stat["n_tasks"] - stat["n_valid"],
                    "task_denominator": rate_payload(stat["n_success"], stat["n_tasks"]),
                    "valid_denominator": rate_payload(stat["n_success"], stat["n_valid"]),
                    "delta_pp": decimal_text(delta),
                }
            )
        affected_by_experiment[experiment] = count
        require(invalid == config["invalid"], "DENOMINATOR_TOTAL", experiment)
        require(count == config["affected_arms"], "DENOMINATOR_ARMS", experiment)

    require(len(affected) == 40, "DENOMINATOR_ARMS", str(len(affected)))
    require(sum(invalid_by_experiment.values()) == 304, "DENOMINATOR_TOTAL", "global")
    require(max_delta == Fraction(81, 4), "DENOMINATOR_MAX", fraction_text(max_delta))
    require(
        max_identity
        == ("sciworld_cross-family-shortcut-contamination", "eval/letta_N400"),
        "DENOMINATOR_MAX",
        repr(max_identity),
    )
    receipt = {
        "status": "PASS",
        "invalid_rows": 304,
        "affected_arms": 40,
        "invalid_rows_by_experiment": dict(sorted(invalid_by_experiment.items())),
        "affected_arms_by_experiment": dict(sorted(affected_by_experiment.items())),
        "max_delta": {
            "experiment": max_identity[0],
            "arm": max_identity[1],
            "delta_pp": decimal_text(max_delta),
        },
        "missingness_semantics": "observed_missing_outcome_not_relabelled_as_failure",
        "arms": affected,
    }
    validate_denominator_receipt(receipt)
    return receipt


def validate_denominator_receipt(receipt: dict[str, Any]) -> None:
    require(receipt.get("status") == "PASS", "DENOMINATOR_RECEIPT", "status")
    require(
        receipt.get("missingness_semantics")
        == "observed_missing_outcome_not_relabelled_as_failure",
        "MISSINGNESS_LABEL",
        str(receipt.get("missingness_semantics")),
    )
    arms = receipt.get("arms")
    require(isinstance(arms, list), "DENOMINATOR_RECEIPT", "arms")
    identities: set[tuple[str, str]] = set()
    invalid_by_experiment: Counter[str] = Counter()
    affected_by_experiment: Counter[str] = Counter()
    observed_max: tuple[Fraction, str, str] | None = None
    for item in arms:
        require(isinstance(item, dict), "DENOMINATOR_RECEIPT", "arm entry")
        experiment = item.get("experiment")
        arm = item.get("arm")
        require(
            isinstance(experiment, str) and isinstance(arm, str),
            "DENOMINATOR_RECEIPT",
            "arm identity",
        )
        identity = (experiment, arm)
        require(identity not in identities, "DENOMINATOR_RECEIPT", f"duplicate {identity!r}")
        identities.add(identity)
        task = item.get("task_denominator")
        valid = item.get("valid_denominator")
        require(
            isinstance(task, dict) and isinstance(valid, dict),
            "DENOMINATOR_RECEIPT",
            f"{identity!r}: rates",
        )
        numerator = task.get("numerator")
        n_tasks = task.get("denominator")
        n_valid = valid.get("denominator")
        require(
            type(numerator) is int
            and type(n_tasks) is int
            and type(n_valid) is int
            and 0 <= numerator <= n_valid < n_tasks,
            "DENOMINATOR_RECEIPT",
            f"{identity!r}: counts",
        )
        require(valid.get("numerator") == numerator, "DENOMINATOR_RECEIPT", f"{identity!r}: numerator")
        require(task == rate_payload(numerator, n_tasks), "DENOMINATOR_RECEIPT", f"{identity!r}: task rate")
        require(valid == rate_payload(numerator, n_valid), "DENOMINATOR_RECEIPT", f"{identity!r}: valid rate")
        missing = n_tasks - n_valid
        require(item.get("invalid_rows") == missing, "DENOMINATOR_RECEIPT", f"{identity!r}: missing")
        delta = (Fraction(numerator, n_valid) - Fraction(numerator, n_tasks)) * 100
        require(item.get("delta_pp") == decimal_text(delta), "DENOMINATOR_RECEIPT", f"{identity!r}: delta")
        invalid_by_experiment[experiment] += missing
        affected_by_experiment[experiment] += 1
        candidate = (delta, experiment, arm)
        if observed_max is None or candidate[0] > observed_max[0]:
            observed_max = candidate

    require(len(arms) == 40, "DENOMINATOR_ARMS", str(len(arms)))
    require(sum(invalid_by_experiment.values()) == 304, "DENOMINATOR_TOTAL", "receipt")
    require(receipt.get("invalid_rows") == 304, "DENOMINATOR_TOTAL", "top-level")
    require(receipt.get("affected_arms") == 40, "DENOMINATOR_ARMS", "top-level")
    interactive_experiments = sorted(
        experiment
        for experiment, config in EXPERIMENTS.items()
        if config["kind"] == "interactive"
    )
    expected_invalid_by_experiment = {
        experiment: invalid_by_experiment[experiment]
        for experiment in interactive_experiments
    }
    expected_affected_by_experiment = {
        experiment: affected_by_experiment[experiment]
        for experiment in interactive_experiments
    }
    require(
        receipt.get("invalid_rows_by_experiment") == expected_invalid_by_experiment,
        "DENOMINATOR_RECEIPT",
        "invalid rows by experiment",
    )
    require(
        receipt.get("affected_arms_by_experiment") == expected_affected_by_experiment,
        "DENOMINATOR_RECEIPT",
        "affected arms by experiment",
    )
    require(observed_max is not None, "DENOMINATOR_MAX", "missing")
    expected_max = {
        "experiment": observed_max[1],
        "arm": observed_max[2],
        "delta_pp": decimal_text(observed_max[0]),
    }
    require(receipt.get("max_delta") == expected_max, "DENOMINATOR_MAX", repr(receipt.get("max_delta")))
    require(
        digest_value(receipt) == EXPECTED_DENOMINATOR_RECEIPT_SHA256,
        "DENOMINATOR_RECEIPT_DIGEST",
        digest_value(receipt),
    )


def load_official_module(source: Path):
    path = source / "results" / "verify_numbers.py"
    module_name = f"memory_collapse_verify_{EXPECTED_COMMIT[:12]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(spec is not None and spec.loader is not None, "OFFICIAL_IMPORT", str(path.name))
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _csv_data_rows(path: Path) -> int:
    _, rows = read_csv(path)
    return len(rows)


def validate_fallback(requested: str, fallback: str) -> None:
    require(
        (requested, fallback) in EXPECTED_FALLBACKS,
        "OFFICIAL_FALLBACK_ALLOWLIST",
        f"{requested} -> {fallback}",
    )


def collect_official_assertions(
    checks_by_experiment: dict[str, Any],
    state: dict[str, Any],
    rows_by_table: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    assertions = []
    table_rows: dict[str, int] = {}
    table_assertions = Counter()
    resolved_by_experiment: dict[str, list[str]] = defaultdict(list)
    fallback_pairs = set()
    configured_paths = []

    for experiment, checks in checks_by_experiment.items():
        require(experiment in state, "OFFICIAL_EXPERIMENT", experiment)
        arm_presence = {arm: True for arm in state[experiment]["arms"]}
        for rel, mapper in checks:
            project_rel = f"results/{experiment}/{rel}"
            configured_paths.append(project_rel)
            require(project_rel in rows_by_table, "OFFICIAL_TABLE_SET", project_rel)
            rows = rows_by_table[project_rel]
            table_rows[project_rel] = len(rows)
            for row_index, row in enumerate(rows, 1):
                for check in mapper(row, arm_presence):
                    label, requested, expected, metric = check[:4]
                    fallback = check[4] if len(check) > 4 else None
                    if requested in arm_presence:
                        actual = requested
                        used_fallback = None
                    else:
                        require(
                            fallback is not None and fallback in arm_presence,
                            "OFFICIAL_ARM",
                            requested,
                        )
                        validate_fallback(requested, fallback)
                        actual = fallback
                        used_fallback = fallback
                        fallback_pairs.add((requested, fallback))
                    assertions.append(
                        {
                            "experiment": experiment,
                            "table": project_rel,
                            "csv_row": row_index,
                            "label": label,
                            "requested_arm": requested,
                            "actual_arm": actual,
                            "fallback": used_fallback,
                            "metric": metric,
                            "expected": expected,
                        }
                    )
                    table_assertions[project_rel] += 1
                    resolved_by_experiment[experiment].append(actual)

    require(tuple(configured_paths) == MAPPED_TABLES, "OFFICIAL_TABLE_SET", repr(configured_paths))
    # Assertion shrinkage is the primary failure for a header-only mutation;
    # row-count shrinkage is checked immediately afterwards.
    require(len(assertions) == 675, "OFFICIAL_ASSERTION_COUNT", str(len(assertions)))
    require(sum(table_rows.values()) == 259, "OFFICIAL_TABLE_ROW_COUNT", str(sum(table_rows.values())))
    require(fallback_pairs == EXPECTED_FALLBACKS, "OFFICIAL_FALLBACK_ALLOWLIST", repr(fallback_pairs))
    return {
        "assertions": assertions,
        "configured_paths": configured_paths,
        "table_rows": table_rows,
        "table_assertions": table_assertions,
        "resolved_by_experiment": resolved_by_experiment,
        "fallback_pairs": fallback_pairs,
    }


def official_verifier_receipt(
    source: Path, state: dict[str, Any], traversal_seed: int
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update(
        {
            "LC_ALL": "C.UTF-8",
            "TZ": "UTC",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": str(traversal_seed),
        }
    )
    execution = subprocess.run(
        [sys.executable, "results/verify_numbers.py"],
        cwd=source,
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    summary_match = re.search(
        r"reproduced (\d+) cells, (\d+) mismatched, (\d+) with no rows",
        execution.stdout,
    )
    require(execution.returncode == 0, "OFFICIAL_VERIFIER_EXECUTION", execution.stderr.strip())
    require(summary_match is not None, "OFFICIAL_VERIFIER_SUMMARY", execution.stdout[-500:])
    reported = tuple(int(value) for value in summary_match.groups())
    require(reported == (675, 0, 0), "OFFICIAL_VERIFIER_SUMMARY", repr(reported))

    module = load_official_module(source)
    rows_by_table = {path: read_csv(source / path)[1] for path in MAPPED_TABLES}
    mapping = collect_official_assertions(module.CHECKS, state, rows_by_table)
    assertions = mapping["assertions"]
    configured_paths = mapping["configured_paths"]
    table_rows = mapping["table_rows"]
    table_assertions = mapping["table_assertions"]
    resolved_by_experiment = mapping["resolved_by_experiment"]
    fallback_pairs = mapping["fallback_pairs"]

    all_number_tables = sorted(
        path.relative_to(source).as_posix()
        for path in source.glob("results/*/numbers/*.csv")
    )
    unmapped = sorted(set(all_number_tables) - set(configured_paths))
    unmapped_rows = {path: _csv_data_rows(source / path) for path in unmapped}
    require(len(all_number_tables) == 40, "NUMBER_TABLE_COUNT", str(len(all_number_tables)))
    require(len(unmapped) == 27, "UNMAPPED_TABLE_COUNT", str(len(unmapped)))
    require(sum(unmapped_rows.values()) == 511, "UNMAPPED_TABLE_ROW_COUNT", str(sum(unmapped_rows.values())))

    coverage = []
    global_arms: set[tuple[str, str]] = set()
    covered_raw = covered_valid = 0
    for experiment in module.CHECKS:
        actual_arms = sorted(set(resolved_by_experiment[experiment]))
        global_arms.update((experiment, arm) for arm in actual_arms)
        raw_rows = 0
        valid_rows = 0
        for arm in actual_arms:
            stat = state[experiment]["stats"][arm]
            if EXPERIMENTS[experiment]["kind"] == "arc":
                raw_rows += stat["n_rows"]
                valid_rows += stat["n_rows"]
            else:
                raw_rows += stat["n_tasks"]
                valid_rows += stat["n_valid"]
        covered_raw += raw_rows
        covered_valid += valid_rows
        coverage.append(
            {
                "experiment": experiment,
                "assertions": len(resolved_by_experiment[experiment]),
                "unique_covered_arms": len(actual_arms),
                "total_arms": len(state[experiment]["arms"]),
                "covered_raw_rows": raw_rows,
                "total_raw_rows": state[experiment]["public"]["row_count"],
                "covered_valid_rows": valid_rows,
                "total_valid_rows": state[experiment]["public"]["valid_row_count"],
                "uncovered_arms": sorted(set(state[experiment]["arms"]) - set(actual_arms)),
            }
        )

    require(len(global_arms) == 335, "OFFICIAL_UNIQUE_ARM_COUNT", str(len(global_arms)))
    require(covered_raw == 33_956, "OFFICIAL_COVERED_ROWS", str(covered_raw))
    require(covered_valid == 33_658, "OFFICIAL_COVERED_VALID_ROWS", str(covered_valid))

    tables = []
    for path in configured_paths:
        actual = {
            item["actual_arm"] for item in assertions if item["table"] == path
        }
        tables.append(
            {
                "path": path,
                "data_rows": table_rows[path],
                "assertions": table_assertions[path],
                "unique_actual_arms": len(actual),
            }
        )

    receipt = {
        "execution": "PASS",
        "return_code": execution.returncode,
        "reported_assertions": reported[0],
        "reported_mismatches": reported[1],
        "reported_no_rows": reported[2],
        "stdout": execution.stdout.strip().splitlines(),
        "stderr": execution.stderr.strip(),
        "mapped_tables": 13,
        "mapped_csv_data_rows": 259,
        "assertion_manifest_sha256": digest_value(assertions),
        "tables": tables,
        "requested_arm_ids": len({item["requested_arm"] for item in assertions}),
        "unique_covered_arms": len(global_arms),
        "total_arms": 762,
        "covered_raw_rows": covered_raw,
        "total_raw_rows": 55_075,
        "covered_valid_rows": covered_valid,
        "total_valid_rows": 54_771,
        "coverage_complete": False,
        "coverage": coverage,
        "fallback_pairs": [
            {"requested": requested, "actual": actual}
            for requested, actual in sorted(fallback_pairs)
        ],
        "all_number_tables": 40,
        "unmapped_tables": [
            {"path": path, "data_rows": unmapped_rows[path]} for path in unmapped
        ],
        "scope_statement": (
            "675 official numeric assertions over 13 selected tables; not 675 arms, "
            "not all 762 arms, and not all 40 numbers tables"
        ),
    }
    validate_official_receipt(receipt)
    return receipt


def validate_official_receipt(receipt: dict[str, Any]) -> None:
    require(receipt.get("execution") == "PASS", "OFFICIAL_RECEIPT", "execution")
    require(receipt.get("return_code") == 0, "OFFICIAL_RECEIPT", "return code")
    require(receipt.get("reported_mismatches") == 0, "OFFICIAL_RECEIPT", "mismatches")
    require(receipt.get("reported_no_rows") == 0, "OFFICIAL_RECEIPT", "no rows")
    tables = receipt.get("tables")
    coverage = receipt.get("coverage")
    unmapped = receipt.get("unmapped_tables")
    require(
        isinstance(tables, list) and isinstance(coverage, list) and isinstance(unmapped, list),
        "OFFICIAL_RECEIPT",
        "collection fields",
    )
    table_paths = [item.get("path") for item in tables if isinstance(item, dict)]
    require(tuple(table_paths) == MAPPED_TABLES, "OFFICIAL_TABLE_SET", repr(table_paths))
    assertion_total = sum(
        item.get("assertions", -1) for item in tables if isinstance(item, dict)
    )
    table_row_total = sum(
        item.get("data_rows", -1) for item in tables if isinstance(item, dict)
    )
    require(assertion_total == 675, "OFFICIAL_ASSERTION_COUNT", str(assertion_total))
    require(receipt.get("reported_assertions") == assertion_total, "OFFICIAL_ASSERTION_COUNT", "receipt")
    require(table_row_total == 259, "OFFICIAL_TABLE_ROW_COUNT", str(table_row_total))
    require(receipt.get("mapped_tables") == 13, "OFFICIAL_TABLE_SET", "mapped count")
    require(receipt.get("mapped_csv_data_rows") == table_row_total, "OFFICIAL_TABLE_ROW_COUNT", "receipt")

    require(len(coverage) == len(EXPERIMENTS), "OFFICIAL_COVERAGE", "experiment count")
    coverage_experiments = [item.get("experiment") for item in coverage if isinstance(item, dict)]
    require(
        len(coverage_experiments) == len(set(coverage_experiments))
        and set(coverage_experiments) == set(EXPERIMENTS),
        "OFFICIAL_COVERAGE",
        repr(coverage_experiments),
    )
    coverage_assertions = sum(item.get("assertions", -1) for item in coverage)
    distinct_arms = sum(item.get("unique_covered_arms", -1) for item in coverage)
    require(coverage_assertions == assertion_total, "OFFICIAL_ASSERTION_COUNT", "coverage")
    require(
        receipt.get("unique_covered_arms") == distinct_arms == 335,
        "COVERAGE_UNIT_DISTINCT",
        f"reported={receipt.get('unique_covered_arms')} recomputed={distinct_arms}",
    )
    total_arms = sum(item.get("total_arms", -1) for item in coverage)
    covered_raw = sum(item.get("covered_raw_rows", -1) for item in coverage)
    total_raw = sum(item.get("total_raw_rows", -1) for item in coverage)
    covered_valid = sum(item.get("covered_valid_rows", -1) for item in coverage)
    total_valid = sum(item.get("total_valid_rows", -1) for item in coverage)
    require(receipt.get("total_arms") == total_arms == 762, "OFFICIAL_COVERAGE", "arms")
    require(receipt.get("covered_raw_rows") == covered_raw == 33_956, "OFFICIAL_COVERAGE", "raw")
    require(receipt.get("total_raw_rows") == total_raw == 55_075, "OFFICIAL_COVERAGE", "total raw")
    require(receipt.get("covered_valid_rows") == covered_valid == 33_658, "OFFICIAL_COVERAGE", "valid")
    require(receipt.get("total_valid_rows") == total_valid == 54_771, "OFFICIAL_COVERAGE", "total valid")
    require(receipt.get("coverage_complete") is False, "OFFICIAL_COVERAGE", "ceiling")
    require(receipt.get("all_number_tables") == 40, "NUMBER_TABLE_COUNT", "receipt")
    require(len(unmapped) == 27, "UNMAPPED_TABLE_COUNT", str(len(unmapped)))
    require(
        sum(item.get("data_rows", -1) for item in unmapped) == 511,
        "UNMAPPED_TABLE_ROW_COUNT",
        "receipt",
    )
    fallback_pairs = {
        (item.get("requested"), item.get("actual"))
        for item in receipt.get("fallback_pairs", [])
        if isinstance(item, dict)
    }
    require(fallback_pairs == EXPECTED_FALLBACKS, "OFFICIAL_FALLBACK_ALLOWLIST", repr(fallback_pairs))
    require(
        receipt.get("requested_arm_ids") == 337,
        "OFFICIAL_COVERAGE",
        "requested arm IDs",
    )
    require(
        receipt.get("assertion_manifest_sha256") == EXPECTED_ASSERTION_MANIFEST_SHA256,
        "OFFICIAL_ASSERTION_MANIFEST",
        str(receipt.get("assertion_manifest_sha256")),
    )
    require(
        receipt.get("scope_statement")
        == "675 official numeric assertions over 13 selected tables; not 675 arms, "
        "not all 762 arms, and not all 40 numbers tables",
        "OFFICIAL_COVERAGE",
        "scope statement",
    )
    require(
        digest_value(receipt) == EXPECTED_OFFICIAL_RECEIPT_SHA256,
        "OFFICIAL_RECEIPT_DIGEST",
        digest_value(receipt),
    )


def canonical_row_hash(row: dict[str, Any]) -> str:
    encoded = json.dumps(
        row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(encoded)


def validate_pool_task_ids(
    rows: list[dict[str, Any]], label: str, expected_rows: int
) -> list[str]:
    require(len(rows) == expected_rows, "POOL_ROW_COUNT", label)
    task_ids = [row.get("task_id") for row in rows]
    require(
        all(isinstance(task_id, str) and task_id for task_id in task_ids),
        "POOL_TASK_ID_PRESENT",
        label,
    )
    require(len(set(task_ids)) == expected_rows, "POOL_TASK_ID_UNIQUE", label)
    return task_ids  # type: ignore[return-value]


def validate_pure_reorder(
    reference: list[dict[str, Any]], variant: list[dict[str, Any]], label: str
) -> dict[str, Any]:
    reference_ids = validate_pool_task_ids(reference, "natural", 200)
    variant_ids = validate_pool_task_ids(variant, label, 200)
    require(Counter(variant_ids) == Counter(reference_ids), "POOL_ID_MULTISET_EQUAL", label)
    reference_hashes = [canonical_row_hash(row) for row in reference]
    variant_hashes = [canonical_row_hash(row) for row in variant]
    require(
        Counter(variant_hashes) == Counter(reference_hashes),
        "POOL_CONTENT_MULTISET_EQUAL",
        label,
    )
    require(variant_ids != reference_ids, "POOL_ORDER_CHANGED", label)
    reference_rank = {task_id: index for index, task_id in enumerate(reference_ids)}
    distances = [abs(index - reference_rank[task_id]) for index, task_id in enumerate(variant_ids)]
    return {
        "label": label,
        "rows": len(variant),
        "unique_task_ids": len(set(variant_ids)),
        "full_content_multiset_equal": True,
        "task_id_multiset_equal": True,
        "order_changed": True,
        "moved_positions": sum(left != right for left, right in zip(reference_ids, variant_ids)),
        "mean_absolute_rank_move": decimal_text(Fraction(sum(distances), len(distances)), 3),
        "max_rank_move": max(distances),
        "ordered_task_ids_sha256": digest_value(variant_ids),
        "content_multiset_sha256": digest_value(sorted(variant_hashes)),
    }


def schedule_receipt(source: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    pools = {
        label: read_jsonl(source / rel)
        for label, rel in {**SELECTED_POOLS, **EXCEPTION_POOLS}.items()
    }
    reference = pools["natural"]
    reference_ids = validate_pool_task_ids(reference, "natural", 200)
    require(
        all(row.get("taskName") == row.get("task_id") for row in reference),
        "POOL_TASK_NAME_ID",
        "natural",
    )
    variants = [
        validate_pure_reorder(reference, pools[label], label)
        for label in ("A", "B", "succdrop")
    ]

    reference_hashes = [canonical_row_hash(row) for row in reference]
    reference_by_id = {row["task_id"]: row for row in reference}

    pool_d = pools["content_intervention_D"]
    require(len(pool_d) == 200, "POOL_EXCEPTION_CONTRACT", "D rows")
    require([row["task_id"] for row in pool_d] == reference_ids, "POOL_EXCEPTION_CONTRACT", "D order")
    d_changed_descriptions = 0
    d_other_field_changes = 0
    for row in pool_d:
        baseline = reference_by_id[row["task_id"]]
        require(set(row) == set(baseline), "POOL_EXCEPTION_CONTRACT", "D key set")
        if row.get("taskDescription") != baseline.get("taskDescription"):
            d_changed_descriptions += 1
        row_without_description = {
            field: value for field, value in row.items() if field != "taskDescription"
        }
        baseline_without_description = {
            field: value for field, value in baseline.items() if field != "taskDescription"
        }
        if canonical_bytes(row_without_description) != canonical_bytes(
            baseline_without_description
        ):
            d_other_field_changes += 1
    require(
        d_changed_descriptions == 200 and d_other_field_changes == 0,
        "POOL_EXCEPTION_CONTRACT",
        f"D descriptions={d_changed_descriptions} other={d_other_field_changes}",
    )

    drop50 = pools["drop50_subset"]
    drop_hashes = [canonical_row_hash(row) for row in drop50]
    require(len(drop50) == 150, "POOL_EXCEPTION_CONTRACT", "drop50 rows")
    require(
        Counter(drop_hashes) == (Counter(drop_hashes) & Counter(reference_hashes)),
        "POOL_EXCEPTION_CONTRACT",
        "drop50 subset",
    )

    replay = pools["replay2_duplication"]
    replay_hashes = [canonical_row_hash(row) for row in replay]
    require(len(replay) == 400, "POOL_EXCEPTION_CONTRACT", "replay rows")
    require(
        Counter(replay_hashes) == Counter(reference_hashes) + Counter(reference_hashes),
        "POOL_EXCEPTION_CONTRACT",
        "replay multiset",
    )
    require(
        replay_hashes == reference_hashes + reference_hashes,
        "POOL_EXCEPTION_CONTRACT",
        "replay order",
    )

    return {
        "status": "PASS",
        "scope": "selected_GPT_AppWorld_current_A_B_succdrop_fixtures",
        "reference": {
            "label": "natural",
            "rows": 200,
            "unique_task_ids": 200,
            "ordered_task_ids_sha256": digest_value(reference_ids),
            "content_multiset_sha256": digest_value(sorted(reference_hashes)),
        },
        "pure_reorder_variants": variants,
        "registered_exceptions": [
            {
                "label": "pool_D",
                "classification": "content_intervention_not_permutation",
                "rows": 200,
                "same_task_ids_and_order": True,
                "changed_task_descriptions": 200,
                "other_field_changes": 0,
            },
            {
                "label": "pool_drop50",
                "classification": "150_row_subset",
                "rows": 150,
                "exact_content_subset": True,
            },
            {
                "label": "pool_replay2",
                "classification": "natural_pool_repeated_twice",
                "rows": 400,
                "unique_task_ids": 200,
                "exact_reference_twice": True,
            },
        ],
        "result_to_pool_lineage": "naming_and_code_evidence_only",
        "cryptographic_run_link": False,
        "causal_schedule_effect_established": False,
    }, pools


def identity_set_digest(values: set[str]) -> str:
    return digest_value(sorted(values))


def curve_point(
    experiment: str,
    arm: str,
    checkpoint: str,
    stat: dict[str, Any],
    reported: dict[str, Any],
) -> dict[str, Any]:
    return {
        "experiment": experiment,
        "arm": arm,
        "checkpoint": checkpoint,
        "n_tasks": stat["n_tasks"],
        "n_valid": stat["n_valid"],
        "n_success": stat["n_success"],
        "task_denominator": rate_payload(stat["n_success"], stat["n_tasks"]),
        "valid_denominator": rate_payload(stat["n_success"], stat["n_valid"]),
        "full_eval_identity_set_sha256": identity_set_digest(stat["all_identity_keys"]),
        "valid_eval_identity_set_sha256": identity_set_digest(stat["valid_identity_keys"]),
        "reported_table_value": reported,
    }


def direction(left: Fraction, right: Fraction) -> str:
    if right > left:
        return "up"
    if right < left:
        return "down"
    return "flat"


def monotonic_label(values: list[Fraction]) -> str:
    directions = [direction(left, right) for left, right in zip(values, values[1:])]
    active = {item for item in directions if item != "flat"}
    if not active:
        return "constant"
    if active == {"up"}:
        return "nondecreasing"
    if active == {"down"}:
        return "nonincreasing"
    return "non_monotonic"


def curve_summary(name: str, points: list[dict[str, Any]]) -> dict[str, Any]:
    task_rates = [
        Fraction(point["n_success"], point["n_tasks"]) for point in points
    ]
    valid_rates = [
        Fraction(point["n_success"], point["n_valid"]) for point in points
    ]
    task_directions = [
        direction(left, right) for left, right in zip(task_rates, task_rates[1:])
    ]
    valid_directions = [
        direction(left, right) for left, right in zip(valid_rates, valid_rates[1:])
    ]
    full_digests = {point["full_eval_identity_set_sha256"] for point in points}
    valid_digests = {point["valid_eval_identity_set_sha256"] for point in points}
    return {
        "name": name,
        "points": points,
        "task_denominator_shape": {
            "adjacent_directions": task_directions,
            "classification": monotonic_label(task_rates),
            "first_to_last_delta_pp": decimal_text((task_rates[-1] - task_rates[0]) * 100),
            "peak_to_final_delta_pp": decimal_text((task_rates[-1] - max(task_rates)) * 100),
        },
        "valid_denominator_shape": {
            "adjacent_directions": valid_directions,
            "classification": monotonic_label(valid_rates),
            "first_to_last_delta_pp": decimal_text((valid_rates[-1] - valid_rates[0]) * 100),
            "peak_to_final_delta_pp": decimal_text((valid_rates[-1] - max(valid_rates)) * 100),
        },
        "denominator_direction_agreement": task_directions == valid_directions,
        "full_eval_identity_sets_equal": len(full_digests) == 1,
        "valid_eval_identity_sets_equal": len(valid_digests) == 1,
        "fully_paired": len(full_digests) == 1 and len(valid_digests) == 1,
        "interpretation": "released_row_descriptive_only",
    }


def cross_schedule_pairing(curves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    app_curves = {
        curve["name"].removeprefix("AppWorld:ACE:"): curve
        for curve in curves
        if curve["name"].startswith("AppWorld:ACE:")
    }
    schedules = [schedule for schedule, _, _ in APP_CURVE_REGISTRY]
    require(set(app_curves) == set(schedules), "CURVE_REGISTRY_SET", "AppWorld pairing")
    common_checkpoints = set.intersection(
        *(
            {point["checkpoint"] for point in app_curves[schedule]["points"]}
            for schedule in schedules
        )
    )
    checkpoint_order = [
        checkpoint for checkpoint in APP_CURVE_REGISTRY[0][2] if checkpoint in common_checkpoints
    ]
    pairing = []
    for checkpoint in checkpoint_order:
        rows = []
        for schedule in schedules:
            point = next(
                item
                for item in app_curves[schedule]["points"]
                if item["checkpoint"] == checkpoint
            )
            rows.append(
                {
                    "schedule": schedule,
                    "arm": point["arm"],
                    "n_tasks": point["n_tasks"],
                    "n_valid": point["n_valid"],
                    "full_eval_identity_set_sha256": point[
                        "full_eval_identity_set_sha256"
                    ],
                    "valid_eval_identity_set_sha256": point[
                        "valid_eval_identity_set_sha256"
                    ],
                }
            )
        baseline = rows[0]
        unpaired = [
            row["schedule"]
            for row in rows[1:]
            if (
                row["full_eval_identity_set_sha256"]
                != baseline["full_eval_identity_set_sha256"]
                or row["valid_eval_identity_set_sha256"]
                != baseline["valid_eval_identity_set_sha256"]
            )
        ]
        pairing.append(
            {
                "checkpoint": checkpoint,
                "schedules": rows,
                "all_full_eval_identity_sets_equal": len(
                    {row["full_eval_identity_set_sha256"] for row in rows}
                )
                == 1,
                "all_valid_eval_identity_sets_equal": len(
                    {row["valid_eval_identity_set_sha256"] for row in rows}
                )
                == 1,
                "unpaired_from_current": unpaired,
                "interpretation": "released_row_identity_pairing_only",
            }
        )
    return pairing


def build_registered_curves(
    science_rows: list[dict[str, str]],
    app_rows: list[dict[str, str]],
    state: dict[str, Any],
) -> dict[str, Any]:
    science_labels = [row.get("方法") for row in science_rows]
    require(
        len(science_labels) == len(set(science_labels)),
        "CURVE_REGISTRY_UNIQUE",
        "ScienceWorld methods",
    )
    expected_science_labels = {label for label, _ in SCIENCE_CURVE_REGISTRY}
    require(
        set(science_labels) == expected_science_labels,
        "CURVE_REGISTRY_SET",
        repr(science_labels),
    )
    science_by_label = {row["方法"]: row for row in science_rows}
    curves = []
    science_state = state["sciworld_cross-family-shortcut-contamination"]
    for label, method in SCIENCE_CURVE_REGISTRY:
        row = science_by_label[label]
        points = []
        for checkpoint in SCIENCE_CURVE_CHECKPOINTS:
            arm = f"eval/{method}_N{checkpoint}"
            stat = science_state["stats"][arm]
            reported_success = int(row[f"win_N{checkpoint}"])
            require(
                stat["n_success"] == reported_success,
                "CURVE_TABLE_MATCH",
                f"ScienceWorld:{arm}",
            )
            points.append(
                curve_point(
                    "sciworld_cross-family-shortcut-contamination",
                    arm,
                    f"N{checkpoint}",
                    stat,
                    {"success_count": reported_success},
                )
            )
        curves.append(curve_summary(f"ScienceWorld:{method}", points))

    app_keys = [(row.get("排序"), row.get("ckpt")) for row in app_rows]
    require(
        len(app_keys) == len(set(app_keys)),
        "CURVE_REGISTRY_UNIQUE",
        "AppWorld schedule/checkpoint",
    )
    expected_app_keys = {
        (schedule, checkpoint)
        for schedule, _, checkpoints in APP_CURVE_REGISTRY
        for checkpoint in checkpoints
    }
    require(set(app_keys) == expected_app_keys, "CURVE_REGISTRY_SET", repr(app_keys))
    app_by_key = {(row["排序"], row["ckpt"]): row for row in app_rows}
    app_state = state["appworld_feed-order-same-pool"]
    for schedule, prefix, checkpoints in APP_CURVE_REGISTRY:
        points = []
        for checkpoint in checkpoints:
            row = app_by_key[(schedule, checkpoint)]
            arm = f"runs/eval/{prefix}_{checkpoint}"
            stat = app_state["stats"][arm]
            reported_n = int(row["题数"])
            reported_percent = int(row["成功率TGC"])
            require(
                stat["n_valid"] == reported_n,
                "CURVE_TABLE_MATCH",
                f"AppWorld:{arm}:n",
            )
            require(
                round(100 * stat["n_success"] / stat["n_valid"])
                == reported_percent,
                "CURVE_TABLE_MATCH",
                f"AppWorld:{arm}:rate",
            )
            points.append(
                curve_point(
                    "appworld_feed-order-same-pool",
                    arm,
                    checkpoint,
                    stat,
                    {"n": reported_n, "whole_percent": reported_percent},
                )
            )
        curves.append(curve_summary(f"AppWorld:ACE:{schedule}", points))

    b_curve = next(curve for curve in curves if curve["name"] == "AppWorld:ACE:B成功降序")
    require(not b_curve["fully_paired"], "CURVE_PAIRING_FALSIFIER", "aceB unexpectedly paired")
    n25 = next(point for point in b_curve["points"] if point["checkpoint"] == "N25")
    require(n25["n_tasks"] == 49, "CURVE_PAIRING_FALSIFIER", "aceB_N25 != 49")

    receipt = {
        "status": "PASS",
        "registered_before_corrected_formal_execution": True,
        "curve_count": len(curves),
        "scienceworld_curves": len(SCIENCE_CURVE_REGISTRY),
        "appworld_schedule_curves": len(APP_CURVE_REGISTRY),
        "curves": curves,
        "pairing_by_checkpoint": cross_schedule_pairing(curves),
        "claim_ceiling": (
            "descriptive shapes over released rows; no significance, causal schedule effect, "
            "paper-run identity, or independent-repeat estimate"
        ),
    }
    validate_registered_curves_receipt(receipt)
    return receipt


def registered_curves(source: Path, state: dict[str, Any]) -> dict[str, Any]:
    science_path = (
        source
        / "results/sciworld_cross-family-shortcut-contamination/numbers/trend_8methods.csv"
    )
    app_path = (
        source
        / "results/appworld_feed-order-same-pool/numbers/ACE重排_排序对N-grid.csv"
    )
    science_header, science_rows = read_csv(science_path)
    app_header, app_rows = read_csv(app_path)
    require(
        science_header
        == [
            "方法",
            "存储粒度",
            "win_N100",
            "win_N200",
            "win_N300",
            "win_N400",
            "CA趋势z",
            "CA_p",
            "raw斜率per100",
            "判定",
        ],
        "CURVE_TABLE_HEADER",
        "ScienceWorld",
    )
    require(app_header == ["排序", "ckpt", "题数", "成功率TGC"], "CURVE_TABLE_HEADER", "AppWorld")
    return build_registered_curves(science_rows, app_rows, state)


def validate_registered_curves_receipt(receipt: dict[str, Any]) -> None:
    require(receipt.get("status") == "PASS", "CURVE_RECEIPT", "status")
    require(
        receipt.get("registered_before_corrected_formal_execution") is True,
        "CURVE_RECEIPT",
        "registration",
    )
    curves = receipt.get("curves")
    require(isinstance(curves, list), "CURVE_RECEIPT", "curves")
    expected_names = [f"ScienceWorld:{method}" for _, method in SCIENCE_CURVE_REGISTRY] + [
        f"AppWorld:ACE:{schedule}" for schedule, _, _ in APP_CURVE_REGISTRY
    ]
    require([curve.get("name") for curve in curves] == expected_names, "CURVE_REGISTRY_SET", "receipt")
    require(receipt.get("curve_count") == len(curves) == 11, "CURVE_RECEIPT", "count")
    require(receipt.get("scienceworld_curves") == 7, "CURVE_RECEIPT", "Science count")
    require(receipt.get("appworld_schedule_curves") == 4, "CURVE_RECEIPT", "App count")
    for curve in curves:
        points = curve.get("points")
        require(isinstance(points, list), "CURVE_RECEIPT", f"{curve.get('name')}: points")
        name = curve["name"]
        if name.startswith("ScienceWorld:"):
            expected_checkpoints = [f"N{value}" for value in SCIENCE_CURVE_CHECKPOINTS]
        else:
            schedule = name.removeprefix("AppWorld:ACE:")
            expected_checkpoints = list(
                next(checkpoints for label, _, checkpoints in APP_CURVE_REGISTRY if label == schedule)
            )
        require(
            [point.get("checkpoint") for point in points] == expected_checkpoints,
            "CURVE_REGISTRY_SET",
            name,
        )
        for point in points:
            n_tasks = point.get("n_tasks")
            n_valid = point.get("n_valid")
            n_success = point.get("n_success")
            require(
                type(n_tasks) is int
                and type(n_valid) is int
                and type(n_success) is int
                and 0 <= n_success <= n_valid <= n_tasks,
                "CURVE_RECEIPT",
                f"{name}: counts",
            )
            require(
                point.get("task_denominator") == rate_payload(n_success, n_tasks),
                "CURVE_RECEIPT",
                f"{name}: task rate",
            )
            require(
                point.get("valid_denominator") == rate_payload(n_success, n_valid),
                "CURVE_RECEIPT",
                f"{name}: valid rate",
            )
            require_sha256(point.get("full_eval_identity_set_sha256"), "CURVE_RECEIPT", name)
            require_sha256(point.get("valid_eval_identity_set_sha256"), "CURVE_RECEIPT", name)
            reported = point.get("reported_table_value")
            require(isinstance(reported, dict), "CURVE_RECEIPT", f"{name}: reported")
            if name.startswith("ScienceWorld:"):
                require(reported == {"success_count": n_success}, "CURVE_RECEIPT", f"{name}: table")
            else:
                require(
                    reported
                    == {
                        "n": n_valid,
                        "whole_percent": round(100 * n_success / n_valid),
                    },
                    "CURVE_RECEIPT",
                    f"{name}: table",
                )
        require(curve == curve_summary(name, points), "CURVE_RECEIPT", f"{name}: summary")
    expected_pairing = cross_schedule_pairing(curves)
    require(
        receipt.get("pairing_by_checkpoint") == expected_pairing,
        "CURVE_PAIRING_RECEIPT",
        "cross-schedule",
    )
    n25 = expected_pairing[0]
    require(
        n25["checkpoint"] == "N25" and n25["unpaired_from_current"] == ["B成功降序"],
        "CURVE_PAIRING_FALSIFIER",
        repr(n25["unpaired_from_current"]),
    )
    require(
        all(not item["unpaired_from_current"] for item in expected_pairing[1:]),
        "CURVE_PAIRING_FALSIFIER",
        "post-N25 pairing",
    )
    require(
        receipt.get("claim_ceiling")
        == "descriptive shapes over released rows; no significance, causal schedule effect, "
        "paper-run identity, or independent-repeat estimate",
        "CURVE_RECEIPT",
        "claim ceiling",
    )
    require(
        digest_value(receipt) == EXPECTED_CURVES_RECEIPT_SHA256,
        "CURVE_RECEIPT_DIGEST",
        digest_value(receipt),
    )


def expect_failure(
    case: str, expected_code: str, action: Callable[[], Any]
) -> dict[str, Any]:
    try:
        action()
    except AuditFailure as exc:
        require(
            exc.code == expected_code,
            "MUTATION_WRONG_GATE",
            f"{case}: expected {expected_code}, observed {exc.code}",
        )
        return {
            "case": case,
            "expected_failure_code": expected_code,
            "observed_failure_code": exc.code,
            "detected": True,
        }
    raise AuditFailure("MUTATION_NOT_DETECTED", case)


def mutation_controls(
    source: Path,
    state: dict[str, Any],
    pools: dict[str, list[dict[str, Any]]],
    denominators: dict[str, Any],
    official: dict[str, Any],
    curves: dict[str, Any],
) -> dict[str, Any]:
    negative_controls = []
    positive_controls = []
    science_name = "sciworld_cross-family-shortcut-contamination"
    science_config = EXPERIMENTS[science_name]
    science = state[science_name]

    duplicate_rows = copy.deepcopy(science["source_order_rows"])
    duplicate_rows.append(copy.deepcopy(duplicate_rows[0]))
    negative_controls.append(
        expect_failure(
            "duplicate_interactive_row_identity",
            "ROW_IDENTITY_UNIQUE",
            lambda: validate_experiment(
                science_name,
                science_config,
                copy.deepcopy(science["arms_rows"]),
                duplicate_rows,
                enforce_expected=False,
            ),
        )
    )

    false_rows = copy.deepcopy(science["source_order_rows"])
    false_index = next(
        index
        for index, row in enumerate(false_rows)
        if row.get("arm") == "eval/langmem_N100"
        and is_valid_interactive(science_config, row)
        and row.get("success") is False
    )
    del false_rows[false_index]
    negative_controls.append(
        expect_failure(
            "delete_mapped_failure_row_with_success_count_unchanged",
            "AGGREGATE_MATCH",
            lambda: validate_experiment(
                science_name,
                science_config,
                copy.deepcopy(science["arms_rows"]),
                false_rows,
                enforce_expected=False,
            ),
        )
    )

    invalid_rows = copy.deepcopy(science["source_order_rows"])
    invalid_index = next(
        index
        for index, row in enumerate(invalid_rows)
        if not is_valid_interactive(science_config, row)
    )
    del invalid_rows[invalid_index]
    negative_controls.append(
        expect_failure(
            "delete_invalid_refusal_row",
            "AGGREGATE_MATCH",
            lambda: validate_experiment(
                science_name,
                science_config,
                copy.deepcopy(science["arms_rows"]),
                invalid_rows,
                enforce_expected=False,
            ),
        )
    )

    unasserted_rows = [
        copy.deepcopy(row)
        for row in science["source_order_rows"]
        if row.get("arm") != "eval/raw_k16"
    ]
    unasserted_arms = [
        copy.deepcopy(row)
        for row in science["arms_rows"]
        if row.get("arm") != "eval/raw_k16"
    ]
    negative_controls.append(
        expect_failure(
            "delete_unasserted_arm_and_matching_arms_row",
            "PINNED_TOTALS",
            lambda: validate_experiment(
                science_name,
                science_config,
                unasserted_arms,
                unasserted_rows,
                enforce_expected=True,
            ),
        )
    )

    altered_arms = copy.deepcopy(science["arms_rows"])
    altered_arms[0]["n_valid"] = str(int(altered_arms[0]["n_valid"]) + 1)
    negative_controls.append(
        expect_failure(
            "change_arms_csv_denominator",
            "AGGREGATE_MATCH",
            lambda: validate_experiment(
                science_name,
                science_config,
                altered_arms,
                copy.deepcopy(science["source_order_rows"]),
                enforce_expected=False,
            ),
        )
    )

    string_success_rows = copy.deepcopy(science["source_order_rows"])
    valid_index = next(
        index
        for index, row in enumerate(string_success_rows)
        if is_valid_interactive(science_config, row)
    )
    string_success_rows[valid_index]["success"] = "false"
    negative_controls.append(
        expect_failure(
            "string_false_success",
            "SUCCESS_BOOL",
            lambda: validate_experiment(
                science_name,
                science_config,
                copy.deepcopy(science["arms_rows"]),
                string_success_rows,
                enforce_expected=False,
            ),
        )
    )

    app_name = "appworld_feed-order-same-pool"
    app_rows_with_null_task_name = copy.deepcopy(state[app_name]["source_order_rows"])
    app_rows_with_null_task_name[0]["task_name"] = None
    validate_experiment(
        app_name,
        EXPERIMENTS[app_name],
        copy.deepcopy(state[app_name]["arms_rows"]),
        app_rows_with_null_task_name,
        enforce_expected=False,
    )
    positive_controls.append(
        {
            "case": "appworld_null_task_name_remains_valid_by_task_id",
            "expected_outcome": "PASS",
            "observed_outcome": "PASS",
            "passed": True,
        }
    )

    arc_name = "arc_stream-self-eval"
    arc = state[arc_name]
    arc_rows = copy.deepcopy(arc["source_order_rows"])
    target_arm = arc_rows[0]["arm"]
    target_sample = arc_rows[0]["sample"]
    delete_index = next(
        index
        for index, row in enumerate(arc_rows)
        if row["arm"] == target_arm and row["sample"] == target_sample
    )
    del arc_rows[delete_index]
    negative_controls.append(
        expect_failure(
            "delete_arc_sample_task_cell",
            "ARC_RECTANGULAR_GRID",
            lambda: validate_experiment(
                arc_name,
                EXPERIMENTS[arc_name],
                copy.deepcopy(arc["arms_rows"]),
                arc_rows,
                enforce_expected=False,
            ),
        )
    )

    module = load_official_module(source)
    header_only_tables = {path: [] for path in MAPPED_TABLES}
    negative_controls.append(
        expect_failure(
            "shrink_mapped_tables_to_headers",
            "OFFICIAL_ASSERTION_COUNT",
            lambda: collect_official_assertions(
                module.CHECKS,
                state,
                header_only_tables,
            ),
        )
    )
    negative_controls.append(
        expect_failure(
            "unexpected_generic_fallback",
            "OFFICIAL_FALLBACK_ALLOWLIST",
            lambda: validate_fallback("missing/requested", "unregistered/fallback"),
        )
    )

    tampered_pool = copy.deepcopy(pools["A"])
    tampered_pool[0]["taskDescription"] = str(tampered_pool[0]["taskDescription"]) + " [tampered]"
    negative_controls.append(
        expect_failure(
            "pool_content_tamper_with_ids_preserved",
            "POOL_CONTENT_MULTISET_EQUAL",
            lambda: validate_pure_reorder(pools["natural"], tampered_pool, "tampered"),
        )
    )

    duplicate_pool = copy.deepcopy(pools["A"])
    duplicate_pool[1] = copy.deepcopy(duplicate_pool[0])
    negative_controls.append(
        expect_failure(
            "pool_delete_one_duplicate_another",
            "POOL_TASK_ID_UNIQUE",
            lambda: validate_pure_reorder(pools["natural"], duplicate_pool, "duplicate"),
        )
    )

    relabelled_coverage = copy.deepcopy(official)
    relabelled_coverage["unique_covered_arms"] = relabelled_coverage[
        "reported_assertions"
    ]
    negative_controls.append(
        expect_failure(
            "relabel_assertion_count_as_unique_arm_count",
            "COVERAGE_UNIT_DISTINCT",
            lambda: validate_official_receipt(relabelled_coverage),
        )
    )

    relabelled_missingness = copy.deepcopy(denominators)
    relabelled_missingness["missingness_semantics"] = "observed_failure"
    negative_controls.append(
        expect_failure(
            "relabel_missing_outcome_as_observed_failure",
            "MISSINGNESS_LABEL",
            lambda: validate_denominator_receipt(relabelled_missingness),
        )
    )

    science_curve_path = (
        source
        / "results/sciworld_cross-family-shortcut-contamination/numbers/trend_8methods.csv"
    )
    app_curve_path = (
        source
        / "results/appworld_feed-order-same-pool/numbers/ACE重排_排序对N-grid.csv"
    )
    _, science_curve_rows = read_csv(science_curve_path)
    _, app_curve_rows = read_csv(app_curve_path)
    science_duplicate = copy.deepcopy(science_curve_rows)
    science_duplicate[-1] = copy.deepcopy(science_duplicate[0])
    negative_controls.append(
        expect_failure(
            "duplicate_one_drop_one_science_curve_method",
            "CURVE_REGISTRY_UNIQUE",
            lambda: build_registered_curves(
                science_duplicate,
                copy.deepcopy(app_curve_rows),
                state,
            ),
        )
    )
    app_duplicate = copy.deepcopy(app_curve_rows)
    app_duplicate[-1] = copy.deepcopy(app_duplicate[0])
    negative_controls.append(
        expect_failure(
            "duplicate_one_drop_one_app_curve_checkpoint",
            "CURVE_REGISTRY_UNIQUE",
            lambda: build_registered_curves(
                copy.deepcopy(science_curve_rows),
                app_duplicate,
                state,
            ),
        )
    )

    cleared_pool_id = copy.deepcopy(pools["A"])
    cleared_pool_id[0]["task_id"] = ""
    cleared_pool_id[0]["taskName"] = ""
    negative_controls.append(
        expect_failure(
            "clear_selected_pool_task_id",
            "POOL_TASK_ID_PRESENT",
            lambda: validate_pure_reorder(pools["natural"], cleared_pool_id, "cleared"),
        )
    )

    invalid_success_rows = copy.deepcopy(science["source_order_rows"])
    invalid_success_index = next(
        index
        for index, row in enumerate(invalid_success_rows)
        if not is_valid_interactive(science_config, row)
    )
    del invalid_success_rows[invalid_success_index]["success"]
    negative_controls.append(
        expect_failure(
            "remove_invalid_interactive_success_field",
            "SUCCESS_BOOL",
            lambda: validate_experiment(
                science_name,
                science_config,
                copy.deepcopy(science["arms_rows"]),
                invalid_success_rows,
                enforce_expected=False,
            ),
        )
    )

    reversed_curves = build_registered_curves(
        list(reversed(copy.deepcopy(science_curve_rows))),
        list(reversed(copy.deepcopy(app_curve_rows))),
        state,
    )
    require(
        canonical_bytes(reversed_curves) == canonical_bytes(curves),
        "CURVE_ORDER_INVARIANCE",
        "reversed CSV row order changed receipt",
    )
    positive_controls.append(
        {
            "case": "curve_csv_row_order_invariant",
            "expected_outcome": "PASS",
            "observed_outcome": "PASS",
            "passed": True,
        }
    )

    receipt = {
        "schema_version": 2,
        "status": "PASS",
        "all_controls_passed": True,
        "negative_controls_registered": len(negative_controls),
        "negative_controls_detected": len(negative_controls),
        "positive_controls_registered": len(positive_controls),
        "positive_controls_passed": len(positive_controls),
        "negative_controls": negative_controls,
        "positive_controls": positive_controls,
        "boundary": "checker-sensitivity controls, not upstream experiment results",
    }
    validate_mutation_receipt(receipt)
    return receipt


def validate_mutation_receipt(receipt: dict[str, Any]) -> None:
    require(
        type(receipt.get("schema_version")) is int
        and receipt["schema_version"] == 2,
        "CONTROL_RECEIPT",
        "schema",
    )
    require(receipt.get("status") == "PASS", "CONTROL_RECEIPT", "status")
    require(receipt.get("all_controls_passed") is True, "CONTROL_RECEIPT", "summary")
    negative = receipt.get("negative_controls")
    positive = receipt.get("positive_controls")
    require(
        isinstance(negative, list) and isinstance(positive, list),
        "CONTROL_RECEIPT",
        "control lists",
    )
    observed_negative = []
    for item in negative:
        require(isinstance(item, dict), "CONTROL_RECEIPT", "negative entry")
        require(item.get("detected") is True, "CONTROL_RECEIPT", str(item.get("case")))
        require(
            item.get("expected_failure_code") == item.get("observed_failure_code"),
            "CONTROL_RECEIPT",
            str(item.get("case")),
        )
        observed_negative.append(
            (item.get("case"), item.get("expected_failure_code"))
        )
    require(tuple(observed_negative) == NEGATIVE_CONTROL_CODES, "CONTROL_RECEIPT", "negative registry")
    observed_positive = []
    for item in positive:
        require(isinstance(item, dict), "CONTROL_RECEIPT", "positive entry")
        require(item.get("passed") is True, "CONTROL_RECEIPT", str(item.get("case")))
        require(
            item.get("expected_outcome") == item.get("observed_outcome") == "PASS",
            "CONTROL_RECEIPT",
            str(item.get("case")),
        )
        observed_positive.append(item.get("case"))
    require(tuple(observed_positive) == POSITIVE_CONTROL_CASES, "CONTROL_RECEIPT", "positive registry")
    require(
        type(receipt.get("negative_controls_registered")) is int
        and type(receipt.get("negative_controls_detected")) is int
        and receipt["negative_controls_registered"]
        == receipt["negative_controls_detected"]
        == len(NEGATIVE_CONTROL_CODES),
        "CONTROL_RECEIPT",
        "negative counts",
    )
    require(
        type(receipt.get("positive_controls_registered")) is int
        and type(receipt.get("positive_controls_passed")) is int
        and receipt["positive_controls_registered"]
        == receipt["positive_controls_passed"]
        == len(POSITIVE_CONTROL_CASES),
        "CONTROL_RECEIPT",
        "positive counts",
    )
    require(
        receipt.get("boundary")
        == "checker-sensitivity controls, not upstream experiment results",
        "CONTROL_RECEIPT",
        "boundary",
    )
    require(
        digest_value(receipt) == EXPECTED_CONTROL_RECEIPT_SHA256,
        "CONTROL_RECEIPT_DIGEST",
        digest_value(receipt),
    )


def public_safety_patterns() -> dict[str, str]:
    return {
        "local_user_path": "/" + "Users/",
        "local_volume_path": "/" + "Volumes/",
        "openai_key": "s" + r"k-[A-Za-z0-9_-]{16,}",
        "github_token": r"gh[pousr]_[A-Za-z0-9]{20,}",
        "aws_key": "A" + r"KIA[0-9A-Z]{16}",
    }


def count_upstream_payload_keys(value: Any) -> int:
    banned = {
        "task_description",
        "taskDescription",
        "instruction",
        "raw_instruction",
        "memory_snapshot",
        "trajectory",
        "messages",
        "observation",
        "memory_text",
    }
    if isinstance(value, dict):
        return sum(key in banned for key in value) + sum(
            count_upstream_payload_keys(item) for item in value.values()
        )
    if isinstance(value, list):
        return sum(count_upstream_payload_keys(item) for item in value)
    return 0


def public_safety_scan(values: Iterable[Any]) -> dict[str, Any]:
    scanned = list(values)
    payload = b"\n".join(canonical_bytes(value) for value in scanned).decode("utf-8")
    hits = {
        name: len(re.findall(pattern, payload))
        for name, pattern in public_safety_patterns().items()
    }
    payload_key_hits = sum(count_upstream_payload_keys(value) for value in scanned)
    require(not any(hits.values()), "PUBLIC_SAFETY", repr(hits))
    require(payload_key_hits == 0, "PUBLIC_PAYLOAD_KEYS", str(payload_key_hits))
    return {
        "status": "PASS",
        "scanned_receipts": len(scanned),
        "local_path_hits": hits["local_user_path"] + hits["local_volume_path"],
        "credential_pattern_hits": sum(
            count
            for name, count in hits.items()
            if name not in {"local_user_path", "local_volume_path"}
        ),
        "upstream_row_payload_key_hits": payload_key_hits,
    }


def scan_public_package_files(package_root: Path, relative_paths: Iterable[str]) -> None:
    paths = sorted(set(relative_paths))
    combined = []
    for rel in paths:
        path = package_root / rel
        require(path.is_file(), "PUBLIC_PACKAGE_FILE", rel)
        try:
            combined.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError as exc:
            raise AuditFailure("PUBLIC_PACKAGE_TEXT", rel) from exc
    payload = "\n".join(combined)
    hits = {
        name: len(re.findall(pattern, payload))
        for name, pattern in public_safety_patterns().items()
    }
    require(not any(hits.values()), "PUBLIC_PACKAGE_SAFETY", repr(hits))


def expected_claim_dispositions() -> list[dict[str, str]]:
    return [
        {
            "claim": "all released arm summaries match released rows",
            "disposition": "PASS_AT_EXACT_CURRENT_RELEASE",
            "ceiling": "membership and aggregate consistency, not semantic outcome truth",
        },
        {
            "claim": "official verifier covers the complete release",
            "disposition": "NOT_SUPPORTED",
            "evidence": "675 assertions resolve to 335 of 762 arms and 13 of 40 number tables",
        },
        {
            "claim": "interactive success level has one release-wide denominator",
            "disposition": "NOT_SUPPORTED",
            "evidence": "304 missing outcomes affect 40 arms; task and valid rates differ by up to 20.25 pp",
        },
        {
            "claim": "registered current/A/B/succdrop fixtures differ only by order",
            "disposition": "PASS_FOR_SELECTED_SHIPPED_POOL_BYTES",
            "ceiling": "result-to-pool run lineage is not cryptographically sealed",
        },
        {
            "claim": "registered curve shapes identify causal memory-collapse effects",
            "disposition": "NOT_SUPPORTED",
            "evidence": "released-row descriptions only; some task sets are unpaired and repeats are sparse",
        },
        {
            "claim": "current public source is the paper-production revision",
            "disposition": "NOT_ESTABLISHED",
            "evidence": "May paper v1 and later one-commit public release have no production binding receipt",
        },
    ]


def validate_source_lock_receipt(source_lock: dict[str, Any]) -> None:
    paper = source_lock.get("paper")
    source = source_lock.get("source")
    require(isinstance(paper, dict) and isinstance(source, dict), "SOURCE_RECEIPT", "sections")
    require(
        paper.get("identity") == "arXiv:2605.12978v1"
        and paper.get("sha256") == EXPECTED_PAPER_SHA256
        and paper.get("pages") == 69
        and type(paper.get("bytes")) is int
        and paper["bytes"] > 0,
        "SOURCE_RECEIPT",
        "paper",
    )
    require(source.get("repository") == "DylanZSZ/Memory-Collapse-Eval", "SOURCE_RECEIPT", "repository")
    require(source.get("origin_verified") is True, "SOURCE_RECEIPT", "origin")
    require(source.get("commit") == EXPECTED_COMMIT, "SOURCE_RECEIPT", "commit")
    require(source.get("tree") == EXPECTED_TREE, "SOURCE_RECEIPT", "tree")
    require(
        type(source.get("commit_count")) is int and source["commit_count"] == 1,
        "SOURCE_RECEIPT",
        "commit count",
    )
    require(source.get("local_tags") == [], "SOURCE_RECEIPT", "tags")
    require(
        source.get("discovered_experiments") == sorted(EXPERIMENTS),
        "SOURCE_RECEIPT",
        "experiment discovery",
    )
    require(
        source.get("tracked_status_pre") == source.get("tracked_status_post") == "clean",
        "SOURCE_RECEIPT",
        "tracked status",
    )
    require(source.get("input_bytes_unchanged") is True, "SOURCE_RECEIPT", "input postcheck")
    require(source.get("paper_production_binding") == "NOT_ESTABLISHED", "SOURCE_RECEIPT", "binding")
    require(source.get("audit_target") == "exact_current_public_release", "SOURCE_RECEIPT", "target")
    inputs = source.get("inputs")
    require(isinstance(inputs, list), "SOURCE_RECEIPT", "inputs")
    require(
        digest_value(inputs) == EXPECTED_SOURCE_INPUTS_SHA256,
        "SOURCE_INPUT_MANIFEST",
        digest_value(inputs),
    )
    for item in inputs:
        require(isinstance(item, dict), "SOURCE_RECEIPT", "input entry")
        require_sha256(item.get("sha256"), "SOURCE_RECEIPT", str(item.get("path")))
        require(
            isinstance(item.get("git_blob_oid"), str)
            and re.fullmatch(r"[0-9a-f]{40}", item["git_blob_oid"]) is not None,
            "SOURCE_RECEIPT",
            str(item.get("path")),
        )
    require(
        digest_value(source_lock) == EXPECTED_SOURCE_LOCK_RECEIPT_SHA256,
        "SOURCE_RECEIPT_DIGEST",
        digest_value(source_lock),
    )


def validate_audit_receipt(audit: dict[str, Any], mutations: dict[str, Any]) -> None:
    require_exact_keys(
        audit,
        {
            "schema_version",
            "execution_status",
            "source_lock",
            "scope",
            "membership",
            "denominators",
            "official_verifier",
            "schedule_conservation",
            "registered_curves",
            "mutation_controls",
            "claim_dispositions",
            "hard_failures",
            "public_safety",
        },
        "AUDIT_RECEIPT",
        "top-level",
    )
    require(
        type(audit.get("schema_version")) is int and audit["schema_version"] == 2,
        "AUDIT_RECEIPT",
        "schema",
    )
    require(audit.get("execution_status") == "PASS", "AUDIT_RECEIPT", "status")
    require(audit.get("hard_failures") == [], "AUDIT_RECEIPT", "hard failures")
    source_lock = audit.get("source_lock")
    membership = audit.get("membership")
    denominators = audit.get("denominators")
    official = audit.get("official_verifier")
    schedules = audit.get("schedule_conservation")
    curves = audit.get("registered_curves")
    require(
        all(
            isinstance(value, dict)
            for value in (source_lock, membership, denominators, official, schedules, curves)
        ),
        "AUDIT_RECEIPT",
        "decision sections",
    )
    validate_source_lock_receipt(source_lock)
    require(
        digest_value(membership) == EXPECTED_MEMBERSHIP_RECEIPT_SHA256,
        "MEMBERSHIP_RECEIPT_DIGEST",
        digest_value(membership),
    )
    require(membership.get("status") == "PASS", "MEMBERSHIP_RECEIPT", "status")
    require_exact_json_equal(
        membership.get("totals"),
        {
            "experiments": 6,
            "arms": 762,
            "rows": 55_075,
            "valid_rows": 54_771,
            "invalid_rows": 304,
        },
        "MEMBERSHIP_RECEIPT",
        "totals",
    )
    validate_denominator_receipt(denominators)
    validate_official_receipt(official)
    require(
        digest_value(schedules) == EXPECTED_SCHEDULE_RECEIPT_SHA256,
        "SCHEDULE_RECEIPT_DIGEST",
        digest_value(schedules),
    )
    require(
        schedules.get("status") == "PASS"
        and schedules.get("cryptographic_run_link") is False
        and schedules.get("causal_schedule_effect_established") is False,
        "SCHEDULE_RECEIPT",
        "status or ceiling",
    )
    validate_registered_curves_receipt(curves)
    validate_mutation_receipt(mutations)
    expected_mutation_summary = {
        "status": "PASS",
        "all_controls_passed": True,
        "negative_controls_registered": len(NEGATIVE_CONTROL_CODES),
        "negative_controls_detected": len(NEGATIVE_CONTROL_CODES),
        "positive_controls_registered": len(POSITIVE_CONTROL_CASES),
        "positive_controls_passed": len(POSITIVE_CONTROL_CASES),
    }
    require_exact_json_equal(
        audit.get("mutation_controls"),
        expected_mutation_summary,
        "AUDIT_RECEIPT",
        "control summary",
    )
    require_exact_json_equal(
        audit.get("scope"),
        {
            "target": "exact_current_public_release_consistency",
            "model_calls": 0,
            "api_calls": 0,
            "agent_environment_runs": 0,
            "paper_experiment_replays": 0,
            "network_instrumentation": "not_performed",
            "file_read_instrumentation": "not_performed",
        },
        "AUDIT_RECEIPT",
        "scope",
    )
    require_exact_json_equal(
        audit.get("claim_dispositions"),
        expected_claim_dispositions(),
        "AUDIT_RECEIPT",
        "claim dispositions",
    )
    safety_input = copy.deepcopy(audit)
    observed_safety = safety_input.pop("public_safety")
    require_exact_json_equal(
        observed_safety,
        public_safety_scan([safety_input, mutations]),
        "PUBLIC_SAFETY",
        "receipt mismatch",
    )
    require(
        digest_value(audit) == EXPECTED_AUDIT_RECEIPT_SHA256,
        "AUDIT_RECEIPT_DIGEST",
        digest_value(audit),
    )


def run_audit(
    source: Path,
    paper_pdf: Path,
    output: Path,
    run_label: str,
    traversal_seed: int,
) -> None:
    require(not output.exists(), "FRESH_OUTPUT_ROOT", output.name)
    expected_hash_seed = str(traversal_seed)
    require(
        os.environ.get("PYTHONHASHSEED") == expected_hash_seed,
        "HASH_SEED_BINDING",
        f"expected PYTHONHASHSEED={expected_hash_seed}",
    )
    output.mkdir(parents=True)
    manifest = source_manifest_pre(source, paper_pdf)
    state, membership = load_release(source, traversal_seed)
    denominators = denominator_receipt(state)
    official = official_verifier_receipt(source, state, traversal_seed)
    schedules, pools = schedule_receipt(source)
    curves = registered_curves(source, state)
    mutations = mutation_controls(
        source,
        state,
        pools,
        denominators,
        official,
        curves,
    )
    source_manifest_post(source, manifest)

    audit = {
        "schema_version": 2,
        "execution_status": "PASS",
        "source_lock": manifest,
        "scope": {
            "target": "exact_current_public_release_consistency",
            "model_calls": 0,
            "api_calls": 0,
            "agent_environment_runs": 0,
            "paper_experiment_replays": 0,
            "network_instrumentation": "not_performed",
            "file_read_instrumentation": "not_performed",
        },
        "membership": membership,
        "denominators": denominators,
        "official_verifier": official,
        "schedule_conservation": schedules,
        "registered_curves": curves,
        "mutation_controls": {
            "status": mutations["status"],
            "all_controls_passed": mutations["all_controls_passed"],
            "negative_controls_registered": mutations[
                "negative_controls_registered"
            ],
            "negative_controls_detected": mutations[
                "negative_controls_detected"
            ],
            "positive_controls_registered": mutations[
                "positive_controls_registered"
            ],
            "positive_controls_passed": mutations["positive_controls_passed"],
        },
        "claim_dispositions": expected_claim_dispositions(),
        "hard_failures": [],
    }
    audit["public_safety"] = public_safety_scan([audit, mutations])
    validate_audit_receipt(audit, mutations)
    write_json(output / "audit.json", audit)
    write_json(output / "mutation-controls.json", mutations)
    stable_receipts = [
        {
            "path": rel,
            "bytes": (output / rel).stat().st_size,
            "sha256": sha256_file(output / rel),
        }
        for rel in STABLE_RUN_FILES
    ]
    write_json(
        output / "run.json",
        {
            "schema_version": 2,
            "run_label": run_label,
            "python_hash_seed": traversal_seed,
            "traversal_seed": traversal_seed,
            "traversal_randomized": True,
            "schedule_order_preserved": True,
            "checker_sha256": sha256_file(Path(__file__).resolve()),
            "source_commit": manifest["source"]["commit"],
            "source_tree": manifest["source"]["tree"],
            "paper_sha256": manifest["paper"]["sha256"],
            "audit_execution_status": audit["execution_status"],
            "all_controls_passed": mutations["all_controls_passed"],
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "stable_receipts": stable_receipts,
            "status": "PASS",
        },
    )
    print(
        f"PASS: {membership['totals']['arms']} arms, {membership['totals']['rows']} rows, "
        f"{mutations['negative_controls_detected']}/"
        f"{mutations['negative_controls_registered']} negative controls detected, "
        f"{mutations['positive_controls_passed']}/"
        f"{mutations['positive_controls_registered']} positive controls passed"
    )


def stable_receipt_records(audit_path: Path, mutations_path: Path) -> list[dict[str, Any]]:
    paths = {"audit.json": audit_path, "mutation-controls.json": mutations_path}
    return [
        {
            "path": rel,
            "bytes": paths[rel].stat().st_size,
            "sha256": sha256_file(paths[rel]),
        }
        for rel in STABLE_RUN_FILES
    ]


def validate_environment_receipt(
    environment: dict[str, Any],
    stable_records: list[dict[str, Any]],
    *,
    expected_label: str,
    expected_seed: int,
    checker_path: Path,
) -> None:
    require_exact_keys(
        environment,
        {
            "schema_version",
            "run_label",
            "python_hash_seed",
            "traversal_seed",
            "traversal_randomized",
            "schedule_order_preserved",
            "checker_sha256",
            "source_commit",
            "source_tree",
            "paper_sha256",
            "audit_execution_status",
            "all_controls_passed",
            "python",
            "python_implementation",
            "platform_system",
            "platform_machine",
            "stable_receipts",
            "status",
        },
        "RUN_RECEIPT",
        expected_label,
    )
    require(
        type(environment.get("schema_version")) is int
        and environment["schema_version"] == 2,
        "RUN_RECEIPT",
        "schema",
    )
    require(environment.get("status") == "PASS", "RUN_STATUS", expected_label)
    require(environment.get("run_label") == expected_label, "RUN_LABEL", str(environment.get("run_label")))
    require(
        type(environment.get("python_hash_seed")) is int
        and type(environment.get("traversal_seed")) is int
        and environment["python_hash_seed"]
        == environment["traversal_seed"]
        == expected_seed,
        "RUN_SEEDS",
        expected_label,
    )
    require(environment.get("traversal_randomized") is True, "TRAVERSAL_RANDOMIZATION", expected_label)
    require(environment.get("schedule_order_preserved") is True, "RUN_RECEIPT", "schedule order")
    require(environment.get("source_commit") == EXPECTED_COMMIT, "RUN_RECEIPT", "source commit")
    require(environment.get("source_tree") == EXPECTED_TREE, "RUN_RECEIPT", "source tree")
    require(environment.get("paper_sha256") == EXPECTED_PAPER_SHA256, "RUN_RECEIPT", "paper")
    require(environment.get("audit_execution_status") == "PASS", "RUN_RECEIPT", "audit status")
    require(environment.get("all_controls_passed") is True, "RUN_RECEIPT", "controls")
    require(
        environment.get("checker_sha256") == sha256_file(checker_path),
        "CHECKER_BINDING",
        expected_label,
    )
    require_exact_json_equal(
        environment.get("stable_receipts"),
        stable_records,
        "RUN_STABLE_BINDING",
        expected_label,
    )
    for field in (
        "python",
        "python_implementation",
        "platform_system",
        "platform_machine",
    ):
        require(
            isinstance(environment.get(field), str) and environment[field],
            "RUN_RECEIPT",
            f"{expected_label}:{field}",
        )


def validate_receipt_bundle(
    audit_path: Path,
    mutations_path: Path,
    environment_path: Path,
    *,
    expected_label: str,
    expected_seed: int,
    checker_path: Path,
) -> dict[str, Any]:
    audit = read_json_object(audit_path)
    mutations = read_json_object(mutations_path)
    environment = read_json_object(environment_path)
    validate_audit_receipt(audit, mutations)
    stable_records = stable_receipt_records(audit_path, mutations_path)
    validate_environment_receipt(
        environment,
        stable_records,
        expected_label=expected_label,
        expected_seed=expected_seed,
        checker_path=checker_path,
    )
    return {
        "audit": audit,
        "mutations": mutations,
        "environment": environment,
        "environment_path": environment_path,
        "stable_records": stable_records,
        "stable_paths": {
            "audit.json": audit_path,
            "mutation-controls.json": mutations_path,
        },
    }


def validate_run_root(run_root: Path, expected_label: str, expected_seed: int) -> dict[str, Any]:
    require(run_root.is_dir(), "RUN_ROOT", run_root.name)
    actual_files = strict_regular_files(
        run_root,
        excluded=set(),
        code="RUN_FILE_SET",
    )
    require(
        actual_files == {"audit.json", "mutation-controls.json", "run.json"},
        "RUN_FILE_SET",
        repr(sorted(actual_files)),
    )
    return validate_receipt_bundle(
        run_root / "audit.json",
        run_root / "mutation-controls.json",
        run_root / "run.json",
        expected_label=expected_label,
        expected_seed=expected_seed,
        checker_path=Path(__file__).resolve(),
    )


def build_comparison_receipt(
    bundle_a: dict[str, Any], bundle_b: dict[str, Any]
) -> dict[str, Any]:
    env_a = bundle_a["environment"]
    env_b = bundle_b["environment"]
    for field in (
        "checker_sha256",
        "source_commit",
        "source_tree",
        "paper_sha256",
        "python",
        "python_implementation",
        "platform_system",
        "platform_machine",
    ):
        require(env_a[field] == env_b[field], "RUN_ENVIRONMENT_MATCH", field)
    files = []
    for rel in STABLE_RUN_FILES:
        path_a = bundle_a["stable_paths"][rel]
        path_b = bundle_b["stable_paths"][rel]
        digest_a = sha256_file(path_a)
        digest_b = sha256_file(path_b)
        bytes_a = path_a.stat().st_size
        bytes_b = path_b.stat().st_size
        require(digest_a == digest_b, "REPEATABILITY_BYTES", rel)
        require(bytes_a == bytes_b, "REPEATABILITY_BYTES", rel)
        require(path_a.read_bytes() == path_b.read_bytes(), "REPEATABILITY_BYTES", rel)
        files.append(
            {
                "path": rel,
                "bytes_a": bytes_a,
                "bytes_b": bytes_b,
                "sha256_a": digest_a,
                "sha256_b": digest_b,
                "equal": True,
            }
        )
    return {
        "schema_version": 2,
        "status": "PASS",
        "run_a": {
            "label": env_a["run_label"],
            "python_hash_seed": env_a["python_hash_seed"],
            "traversal_seed": env_a["traversal_seed"],
            "environment_receipt_sha256": sha256_file(
                bundle_a["environment_path"]
            ),
            "checker_sha256": env_a["checker_sha256"],
        },
        "run_b": {
            "label": env_b["run_label"],
            "python_hash_seed": env_b["python_hash_seed"],
            "traversal_seed": env_b["traversal_seed"],
            "environment_receipt_sha256": sha256_file(
                bundle_b["environment_path"]
            ),
            "checker_sha256": env_b["checker_sha256"],
        },
        "stable_receipts": files,
        "all_stable_receipts_byte_identical": True,
        "fresh_process_identity": "PROCEDURAL_NOT_RECEIPT_PROVEN",
        "boundary": (
            "producer-recorded same-machine byte comparison; historical execution "
            "identity not receipt-proven"
        ),
    }


def compare_runs(run_a: Path, run_b: Path, output: Path) -> None:
    require(output.parent.is_dir(), "COMPARISON_PARENT", output.parent.name)
    require(not output.exists(), "COMPARISON_OUTPUT", output.name)
    bundle_a = validate_run_root(run_a, "A", 313)
    bundle_b = validate_run_root(run_b, "B", 727)
    receipt = build_comparison_receipt(bundle_a, bundle_b)
    write_json(output, receipt)
    print(
        f"PASS: {len(receipt['stable_receipts'])} stable receipts are byte-identical; "
        "environment bindings recorded, execution identity not receipt-proven"
    )


def install_receipts(run_a: Path, run_b: Path, comparison: Path, package_root: Path) -> None:
    require(package_root.is_dir(), "PACKAGE_ROOT", package_root.name)
    require(comparison.is_file(), "COMPARISON_RECEIPT", comparison.name)
    bundle_a = validate_run_root(run_a, "A", 313)
    bundle_b = validate_run_root(run_b, "B", 727)
    expected_comparison = build_comparison_receipt(bundle_a, bundle_b)
    comparison_value = read_json_object(comparison)
    require(
        comparison.read_bytes() == canonical_bytes(expected_comparison)
        and exact_json_equal(comparison_value, expected_comparison),
        "COMPARISON_BINDING",
        comparison.name,
    )
    raw = package_root / "raw"
    require(not raw.exists(), "INSTALL_TARGET", "raw already exists")
    raw.mkdir(parents=True)
    for rel in STABLE_RUN_FILES:
        shutil.copyfile(run_a / rel, raw / rel)
    shutil.copyfile(run_a / "run.json", raw / "environment_run_a.json")
    shutil.copyfile(run_b / "run.json", raw / "environment_run_b.json")
    shutil.copyfile(comparison, raw / "repeatability.json")
    validate_installed_receipt_bundle(package_root)
    print(
        "PASS: installed internally bound checked receipts; historical execution "
        "identity remains procedural"
    )


def strict_regular_files(
    root: Path, *, excluded: set[str], code: str
) -> set[str]:
    files = set()
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        require(not path.is_symlink(), code, f"symlink: {rel}")
        if path.is_dir():
            continue
        require(path.is_file(), code, f"non-regular entry: {rel}")
        if rel in excluded:
            continue
        files.add(rel)
    return files


def package_files(package_root: Path) -> set[str]:
    return strict_regular_files(
        package_root,
        excluded={"checksums.sha256"},
        code="PACKAGE_FILE_SET",
    )


def write_checksums(package_root: Path) -> None:
    actual = package_files(package_root)
    require(actual == EXPECTED_PACKAGE_FILES, "PACKAGE_FILE_SET", repr(sorted(actual)))
    validate_installed_receipt_bundle(package_root)
    scan_public_package_files(package_root, actual)
    checksum_path = package_root / "checksums.sha256"
    require(not checksum_path.exists(), "CHECKSUM_MANIFEST", "already exists")
    lines = [f"{sha256_file(package_root / rel)}  {rel}" for rel in sorted(actual)]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PASS: wrote checksums for {len(lines)} package files")


def validate_installed_receipt_bundle(package_root: Path) -> None:
    raw = package_root / "raw"
    bundle_a = validate_receipt_bundle(
        raw / "audit.json",
        raw / "mutation-controls.json",
        raw / "environment_run_a.json",
        expected_label="A",
        expected_seed=313,
        checker_path=package_root / "audit.py",
    )
    bundle_b = validate_receipt_bundle(
        raw / "audit.json",
        raw / "mutation-controls.json",
        raw / "environment_run_b.json",
        expected_label="B",
        expected_seed=727,
        checker_path=package_root / "audit.py",
    )
    expected_comparison = build_comparison_receipt(bundle_a, bundle_b)
    installed_comparison = read_json_object(raw / "repeatability.json")
    require(
        (raw / "repeatability.json").read_bytes()
        == canonical_bytes(expected_comparison)
        and exact_json_equal(installed_comparison, expected_comparison),
        "COMPARISON_BINDING",
        "installed",
    )


def verify_installed(package_root: Path) -> None:
    checksum_path = package_root / "checksums.sha256"
    require(checksum_path.is_file(), "CHECKSUM_MANIFEST", "missing")
    listed: dict[str, str] = {}
    for line_number, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, "CHECKSUM_MANIFEST", f"line {line_number}")
        digest, rel = match.groups()
        require(rel not in listed, "CHECKSUM_MANIFEST", f"duplicate {rel}")
        listed[rel] = digest
    require(set(listed) == EXPECTED_PACKAGE_FILES, "PACKAGE_FILE_SET", repr(sorted(listed)))
    require(package_files(package_root) == EXPECTED_PACKAGE_FILES, "PACKAGE_FILE_SET", "disk mismatch")
    for rel, expected in sorted(listed.items()):
        require(sha256_file(package_root / rel) == expected, "CHECKSUM_MISMATCH", rel)
    validate_installed_receipt_bundle(package_root)
    scan_public_package_files(
        package_root,
        set(listed) | {"checksums.sha256"},
    )
    print(
        "PASS: package integrity and internal receipt consistency; "
        "source and paper were not reopened"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="execute one fresh source-bound audit")
    run.add_argument("--source", type=Path, required=True)
    run.add_argument("--paper-pdf", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--run-label", required=True)
    run.add_argument("--traversal-seed", type=int, required=True)

    compare = subparsers.add_parser("compare", help="compare two fresh run roots")
    compare.add_argument("--run-a", type=Path, required=True)
    compare.add_argument("--run-b", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)

    install = subparsers.add_parser("install", help="install already-compared receipts")
    install.add_argument("--run-a", type=Path, required=True)
    install.add_argument("--run-b", type=Path, required=True)
    install.add_argument("--comparison", type=Path, required=True)
    install.add_argument("--package-root", type=Path, required=True)

    checksums = subparsers.add_parser("checksums", help="write exact package checksums")
    checksums.add_argument("--package-root", type=Path, required=True)

    verify = subparsers.add_parser("verify-installed", help="verify installed receipts")
    verify.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parent)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            run_audit(
                args.source.resolve(),
                args.paper_pdf.resolve(),
                args.output.resolve(),
                args.run_label,
                args.traversal_seed,
            )
        elif args.command == "compare":
            compare_runs(args.run_a.resolve(), args.run_b.resolve(), args.output.resolve())
        elif args.command == "install":
            install_receipts(
                args.run_a.resolve(),
                args.run_b.resolve(),
                args.comparison.resolve(),
                args.package_root.resolve(),
            )
        elif args.command == "checksums":
            write_checksums(args.package_root.resolve())
        elif args.command == "verify-installed":
            verify_installed(args.package_root.resolve())
        else:  # pragma: no cover - argparse makes this unreachable
            raise AssertionError(args.command)
    except AuditFailure as exc:
        print(f"FAIL [{exc.code}]: {exc.detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
