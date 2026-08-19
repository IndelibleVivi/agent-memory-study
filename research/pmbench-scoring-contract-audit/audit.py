#!/usr/bin/env python3
"""Reproduce the PM-Bench scorer-contract probes and released-log audit.

This standard-library-only runner is locked to one official source revision.
It executes three deterministic scorer probes, validates and rescores the 64
released primary trajectories, checks step identity, and rebuilds the official
comparison report. CPython tracing exposes revision-locked scorer locals without
modifying the official checkout. It makes no model or network call.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import importlib.util
import json
import platform
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True


EXPECTED_COMMIT = "e1093c470c8981daf522d4ef047a7c3a71e077d7"
EXPECTED_PM_BENCH_SHA256 = "d8ec27d8dcf4679d7a789c52fc305286df460844d47e9f116b81f2400ac254d8"
EXPECTED_SCENARIO_SHA256 = "94a45937da1363be19ccfdc2c188d132f23093041e30abd3ec22d64d70da8f24"
EXPECTED_REPORT_SHA256 = "ee61a8e26685458531df5847ef7485b83c91ec0e26b0ce085d0fc2d63ddf60df"
EXPECTED_REPORT_BUILDER_SHA256 = "02a0e6c4dbfba41c749b764c4391a4c4fd3b11c8230c3ed3403697db63004e1f"
EXPECTED_REBUILT_REPORT_SHA256 = "3b263f8cdda2c37975ce7d4df6e59615193f0b59dcc422595659c927fceefa7f"
EXPECTED_MODELS = {
    "gpt-53-codex",
    "gpt-54",
    "llama-33-70b-instruct",
    "mistral-large-2512",
    "mistral-small-32-24b-instruct",
    "qwen3-14b",
    "qwen3-32b",
    "qwen3-8b",
}
EXPECTED_SETUPS = {
    "single-baseline",
    "single-todo-ledger",
    "heartbeat-proactive",
    "heartbeat-auto-60m",
    "heartbeat-auto-30m",
    "hier-union-query",
    "hier-majority-vote",
    "hier-unanimous-vote",
}
REPLAY_SETUPS = {"hier-majority-vote", "hier-unanimous-vote"}
EXPECTED_TABLE_2 = {
    "heartbeat-auto-30m": (57.8, 51.5),
    "heartbeat-auto-60m": (56.6, 52.2),
    "heartbeat-proactive": (65.1, 65.0),
    "hier-majority-vote": (37.2, 38.3),
    "hier-unanimous-vote": (35.3, 39.6),
    "hier-union-query": (45.2, 45.9),
    "single-baseline": (60.0, 59.4),
    "single-todo-ledger": (62.8, 62.8),
}
UPDATED_OFF_DUE_LINE = 2518
CANCELED_SELECTION_LINE = 2461
GENERATED_FILES = {
    "RESULTS.txt",
    "raw/decision.json",
    "raw/environment.txt",
    "raw/hidden_channel_findings.jsonl",
    "raw/official_probes.json",
    "raw/report_comparison.json",
    "raw/run_scores.jsonl",
    "raw/source_manifest.json",
    "raw/update_violation_findings.jsonl",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout.strip()


def load_official_module(source_repo: Path):
    source_file = source_repo / "sim" / "pm_bench.py"
    spec = importlib.util.spec_from_file_location("pmbench_release_audit", source_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {source_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, source_file


def setup_from_run_dir(run_dir: Path, model: str) -> str:
    marker = f"-{model}-v9-"
    if marker not in run_dir.name:
        raise ValueError(f"cannot parse setup from {run_dir.name}")
    return run_dir.name.split(marker, 1)[0]


def primary_logs(results_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in results_dir.rglob("*.jsonl")
        if not path.name.endswith(".ledger.jsonl")
        and not path.name.endswith(".debug.jsonl")
    )


def expected_step_pairs(scenario: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (day["name"], step["id"])
        for day in scenario["days"]
        for step in day["steps"]
    ]


def identity_audit(
    entries: list[dict[str, Any]], scenario: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
    expected = expected_step_pairs(scenario)
    expected_set = set(expected)
    day_order = [day["name"] for day in scenario["days"]]
    expected_by_day = {
        day["name"]: [step["id"] for step in day["steps"]]
        for day in scenario["days"]
    }
    step_days: dict[str, set[str]] = defaultdict(set)
    for day, step_id in expected:
        step_days[step_id].add(day)

    observed_valid: list[tuple[str, str]] = []
    missing_day_rows: list[int] = []
    missing_step_id_rows: list[int] = []
    unknown_day_rows: list[dict[str, Any]] = []
    unknown_step_rows: list[dict[str, Any]] = []
    cross_day_rows: list[dict[str, Any]] = []
    pair_to_rows: dict[tuple[str, str], list[int]] = defaultdict(list)

    for row_index, entry in enumerate(entries):
        day = entry.get("day")
        step_id = entry.get("step_id")
        if not isinstance(day, str):
            missing_day_rows.append(row_index)
            continue
        if not isinstance(step_id, str):
            missing_step_id_rows.append(row_index)
            continue
        if day not in expected_by_day:
            unknown_day_rows.append({"row": row_index, "day": day, "step_id": step_id})
            continue
        if step_id not in step_days:
            unknown_step_rows.append({"row": row_index, "day": day, "step_id": step_id})
            continue
        if (day, step_id) not in expected_set:
            cross_day_rows.append(
                {
                    "row": row_index,
                    "declared_day": day,
                    "step_id": step_id,
                    "scenario_days": sorted(step_days[step_id]),
                }
            )
            continue
        pair = (day, step_id)
        observed_valid.append(pair)
        pair_to_rows[pair].append(row_index)

    duplicates = {
        f"{day}::{step_id}": rows
        for (day, step_id), rows in sorted(pair_to_rows.items())
        if len(rows) > 1
    }
    missing_pairs = [
        {"day": day, "step_id": step_id}
        for day, step_id in expected
        if (day, step_id) not in pair_to_rows
    ]

    within_day_out_of_order: dict[str, dict[str, Any]] = {}
    for day in day_order:
        actual = [step_id for entry_day, step_id in observed_valid if entry_day == day]
        wanted = expected_by_day[day]
        if actual != wanted:
            within_day_out_of_order[day] = {
                "actual": actual,
                "expected": wanted,
                "rows_not_at_expected_position": sum(
                    left != right for left, right in zip(actual, wanted)
                )
                + abs(len(actual) - len(wanted)),
            }

    actual_day_sequence = [entry.get("day") for entry in entries]
    expected_day_sequence = [day for day, _ in expected]
    global_row_order_matches = actual_day_sequence == expected_day_sequence
    exact_sequence_matches = observed_valid == expected
    valid = not any(
        (
            missing_day_rows,
            missing_step_id_rows,
            unknown_day_rows,
            unknown_step_rows,
            cross_day_rows,
            duplicates,
            missing_pairs,
        )
    ) and len(entries) == len(expected)

    aligned = None
    if valid:
        entry_by_pair = {
            (entry["day"], entry["step_id"]): entry for entry in entries
        }
        aligned = [entry_by_pair[pair] for pair in expected]

    return (
        {
            "entry_count": len(entries),
            "expected_entry_count": len(expected),
            "identity_valid": valid,
            "missing_day_rows": missing_day_rows,
            "missing_step_id_rows": missing_step_id_rows,
            "unknown_day_rows": unknown_day_rows,
            "unknown_step_rows": unknown_step_rows,
            "cross_day_rows": cross_day_rows,
            "duplicate_pairs": duplicates,
            "missing_pairs": missing_pairs,
            "within_day_out_of_order": within_day_out_of_order,
            "global_day_row_order_matches": global_row_order_matches,
            "exact_pair_sequence_matches": exact_sequence_matches,
        },
        aligned,
    )


def traced_score_day(
    pm,
    day: dict[str, Any],
    actions: list[dict[str, Any]],
    pre_updates: list[dict[str, Any]],
    updates_by_step: dict[str, list[dict[str, Any]]],
    state_visibility: dict[str, bool],
):
    captured: dict[str, Any] = {}
    violations: list[dict[str, Any]] = []
    code = pm.score_day.__code__

    def tracer(frame, event, arg):
        if frame.f_code is not code:
            return None
        if event == "line" and frame.f_lineno in {
            UPDATED_OFF_DUE_LINE,
            CANCELED_SELECTION_LINE,
        }:
            state = frame.f_locals.get("state", {})
            step = frame.f_locals.get("step", {})
            violations.append(
                {
                    "kind": (
                        "updated_off_due"
                        if frame.f_lineno == UPDATED_OFF_DUE_LINE
                        else "canceled_selection"
                    ),
                    "line": frame.f_lineno,
                    "day": day["name"],
                    "step_id": step.get("id"),
                    "task_id": frame.f_locals.get("task_id"),
                    "task_result_after_selection": state.get("result"),
                    "state_updated": bool(state.get("updated")),
                    "has_update": bool(state.get("has_update")),
                    "current": copy.deepcopy(state.get("current")),
                }
            )
        elif event == "return":
            captured["task_states"] = copy.deepcopy(frame.f_locals["task_states"])
            captured["metrics"] = copy.deepcopy(frame.f_locals["metrics"])
        return tracer

    old_trace = sys.gettrace()
    sys.settrace(tracer)
    try:
        result = pm.score_day(
            day,
            actions,
            pre_updates,
            updates_by_step,
            state_visibility,
        )
    finally:
        sys.settrace(old_trace)

    if sum(1 for event in violations) != result[0]["update_violation"]:
        raise AssertionError(
            f"trace mismatch in {day['name']}: {len(violations)} events vs "
            f"{result[0]['update_violation']} scorer increments"
        )
    return result, captured["task_states"], violations


def due_window_start_index(pm, day: dict[str, Any], state: dict[str, Any]) -> int | None:
    current = state["current"]
    task_type = current.get("type")
    if task_type in {"event", "time"}:
        return state.get("cue_step_idx")
    if task_type == "time_check":
        day_start = pm.build_day_start_minutes(day)
        for index, step in enumerate(day["steps"]):
            step_minutes = pm.time_to_minutes(step["time"])
            if pm.timecheck_status(current, step_minutes, day_start) == "on_time":
                return index
    return None


def set_f1(summary: dict[str, int]) -> float | None:
    denom = 2 * summary["set_tp"] + summary["set_fp"] + summary["set_fn"]
    if denom == 0:
        return None
    return 2 * summary["set_tp"] / denom


def compact_summary(summary: dict[str, Any]) -> dict[str, int]:
    keys = [
        "hit",
        "late",
        "miss",
        "set_tp",
        "set_fp",
        "set_fn",
        "state_query_calls",
        "check_time_calls",
        "update_total",
        "update_hit",
        "update_late",
        "update_miss",
        "update_violation",
    ]
    return {key: int(summary[key]) for key in keys}


def probe_event_day() -> dict[str, Any]:
    return {
        "name": "Monday",
        "steps": [
            {
                "id": "s1",
                "time": "09:00",
                "cues": [],
                "state_events": {
                    "email": [{"id": "email-arrived", "text": "A hidden email arrived."}]
                },
            }
        ],
        "tasks": [
            {
                "id": "t-email",
                "type": "event",
                "encoding": "start",
                "regular": False,
                "cue_id": "email-arrived",
                "cue_channel": "email",
                "label": "Reply to the email",
                "action_text": "Reply to the email",
            }
        ],
    }


def probe_event_actions(email_queries: int) -> list[dict[str, Any]]:
    return [
        {
            "day": "Monday",
            "step_id": "s1",
            "task_ids": ["t-email"],
            "state_queries": ({"email": email_queries} if email_queries else {}),
        }
    ]


def probe_update_day(initial_target: str) -> dict[str, Any]:
    return {
        "name": "Tuesday",
        "steps": [
            {"id": "u1", "time": "10:00", "cues": [], "state_events": {}},
            {"id": "u2", "time": "11:00", "cues": [], "state_events": {}},
            {"id": "u3", "time": "12:00", "cues": [], "state_events": {}},
        ],
        "tasks": [
            {
                "id": "t-time",
                "type": "time",
                "encoding": "start",
                "regular": False,
                "target_time": initial_target,
                "label": "Current scheduled action",
                "action_text": "Perform current scheduled action",
            }
        ],
    }


def probe_update_actions() -> list[dict[str, Any]]:
    return [
        {"day": "Tuesday", "step_id": "u1", "task_ids": [], "state_queries": {}},
        {"day": "Tuesday", "step_id": "u2", "task_ids": [], "state_queries": {}},
        {"day": "Tuesday", "step_id": "u3", "task_ids": ["t-time"], "state_queries": {}},
    ]


def probe_order_day() -> dict[str, Any]:
    return {
        "name": "Wednesday",
        "steps": [
            {"id": "o1", "time": "09:00", "cues": ["cue-1"], "state_events": {}},
            {"id": "o2", "time": "10:00", "cues": [], "state_events": {}},
        ],
        "tasks": [
            {
                "id": "t-order",
                "type": "event",
                "encoding": "start",
                "regular": False,
                "cue_id": "cue-1",
                "cue_channel": "narrative",
                "label": "Do ordered task",
                "action_text": "Do ordered task",
            }
        ],
    }


def score_probe_day(pm, day, actions, *, updates=None):
    return pm.score_day(
        day,
        actions,
        pre_updates=[],
        updates_by_step=(updates or {}),
        state_visibility={"clock": False, "email": False},
    )


def run_official_probes(pm) -> dict[str, Any]:
    metrics_no, _, _, monitoring_no, channels_no = score_probe_day(
        pm, probe_event_day(), probe_event_actions(0)
    )
    metrics_yes, _, _, monitoring_yes, channels_yes = score_probe_day(
        pm, probe_event_day(), probe_event_actions(1)
    )
    assert metrics_no["hit"] == metrics_yes["hit"] == 1
    assert metrics_no["set_tp"] == metrics_yes["set_tp"] == 1
    assert monitoring_no["proactive_monitoring_required"]["hit"] == 1
    assert monitoring_yes["proactive_monitoring_required"]["hit"] == 1
    assert channels_no["email"]["hit"] == channels_yes["email"]["hit"] == 1
    assert metrics_no["state_query_calls"] == 0
    assert metrics_yes["state_query_calls"] == 1

    updated_metrics, *_ = score_probe_day(
        pm,
        probe_update_day("10:00"),
        probe_update_actions(),
        updates={
            "u1": [
                {
                    "task_id": "t-time",
                    "action": "reschedule",
                    "new_target_time": "11:00",
                }
            ]
        },
    )
    control_metrics, *_ = score_probe_day(
        pm, probe_update_day("11:00"), probe_update_actions()
    )
    assert updated_metrics["late"] == updated_metrics["update_late"] == 1
    assert updated_metrics["update_violation"] == 1
    assert control_metrics["late"] == 1
    assert control_metrics["update_violation"] == 0

    chronological = [
        {"day": "Wednesday", "step_id": "o1", "task_ids": ["t-order"], "state_queries": {}},
        {"day": "Wednesday", "step_id": "o2", "task_ids": [], "state_queries": {}},
    ]
    scenario = {"state_visibility": {"clock": False}, "days": [probe_order_day()]}
    ordered_summary, _, _ = pm.score_log(scenario, chronological)
    reversed_summary, _, _ = pm.score_log(scenario, list(reversed(chronological)))
    assert ordered_summary["hit"] == ordered_summary["set_tp"] == 1
    assert ordered_summary["set_fp"] == ordered_summary["set_fn"] == 0
    assert reversed_summary["hit"] == reversed_summary["set_tp"] == 0
    assert reversed_summary["late"] == 1
    assert reversed_summary["set_fp"] == reversed_summary["set_fn"] == 1

    return {
        "artifact": "PM-Bench exact-official-checkout scorer-contract probes",
        "status": "PASS",
        "fixture_boundary": (
            "Direct scorer-function fixtures, not complete scenario-validator fixtures. "
            "The released-corpus lane separately validates the full official scenario."
        ),
        "probes": {
            "hidden_channel_no_query": {
                "metrics": compact_summary(metrics_no),
                "monitoring": monitoring_no["proactive_monitoring_required"],
                "email_channel": channels_no["email"],
            },
            "hidden_channel_with_query": {
                "metrics": compact_summary(metrics_yes),
                "monitoring": monitoring_yes["proactive_monitoring_required"],
                "email_channel": channels_yes["email"],
            },
            "updated_current_version_late": compact_summary(updated_metrics),
            "no_update_late_control": compact_summary(control_metrics),
            "chronological_rows": compact_summary(ordered_summary),
            "reversed_rows_same_declared_step_ids": compact_summary(reversed_summary),
        },
    }


def rebuild_and_compare_report(source_repo: Path) -> dict[str, Any]:
    results_dir = source_repo / "runs" / "all_results_v9"
    builder = results_dir / "build_experiment_output_comparison_report.py"
    checked = results_dir / "experiment_output_comparison_report.md"
    scenario = source_repo / "data" / "synthetic_week_v9.json"
    if sha256(builder) != EXPECTED_REPORT_BUILDER_SHA256:
        raise SystemExit("official report builder hash mismatch")
    if sha256(checked) != EXPECTED_REPORT_SHA256:
        raise SystemExit("official checked report hash mismatch")
    with tempfile.TemporaryDirectory(prefix="pmbench-report-") as temp_dir:
        rebuilt = Path(temp_dir) / "report.md"
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(builder),
                "--results-dir",
                str(results_dir),
                "--scenario",
                str(scenario),
                "--out",
                str(rebuilt),
            ],
            cwd=source_repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        checked_text = checked.read_text(encoding="utf-8")
        rebuilt_text = rebuilt.read_text(encoding="utf-8")
        expected_rebuilt = checked_text.replace(
            "runs/March_ALL_results_v9", "runs/all_results_v9"
        )
        if expected_rebuilt != rebuilt_text:
            diff = "".join(
                difflib.unified_diff(
                    checked_text.splitlines(keepends=True),
                    rebuilt_text.splitlines(keepends=True),
                    fromfile="checked",
                    tofile="rebuilt",
                )
            )
            raise AssertionError(f"unexpected official report difference:\n{diff[:4000]}")
        if sha256(rebuilt) != EXPECTED_REBUILT_REPORT_SHA256:
            raise AssertionError("rebuilt report hash mismatch")
        return {
            "status": "PASS",
            "checked_report_sha256": sha256(checked),
            "rebuilt_report_sha256": sha256(rebuilt),
            "builder_sha256": sha256(builder),
            "builder_stdout_normalized": "Wrote report: <temporary-output>/report.md",
            "stderr": proc.stderr,
            "byte_identical": checked_text == rebuilt_text,
            "semantic_content_identical_after_single_path_repair": True,
            "only_difference": {
                "checked": "runs/March_ALL_results_v9",
                "rebuilt": "runs/all_results_v9",
            },
        }


def run_released_audit(
    source_repo: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    source_repo = source_repo.expanduser().resolve()
    head = git(source_repo, "rev-parse", "HEAD")
    dirty = git(source_repo, "status", "--porcelain")
    if head != EXPECTED_COMMIT:
        raise SystemExit(f"wrong source commit: {head}")
    if dirty:
        raise SystemExit("official checkout is dirty")

    pm, source_file = load_official_module(source_repo)
    scenario_path = source_repo / "data" / "synthetic_week_v9.json"
    results_dir = source_repo / "runs" / "all_results_v9"
    if sha256(source_file) != EXPECTED_PM_BENCH_SHA256:
        raise SystemExit("official scorer hash mismatch")
    if sha256(scenario_path) != EXPECTED_SCENARIO_SHA256:
        raise SystemExit("official scenario hash mismatch")
    source_lines = source_file.read_text(encoding="utf-8").splitlines()
    if "metrics[\"update_violation\"] += 1" not in source_lines[UPDATED_OFF_DUE_LINE - 1]:
        raise SystemExit("updated-off-due trace line no longer matches lock")
    if "metrics[\"update_violation\"] += 1" not in source_lines[CANCELED_SELECTION_LINE - 1]:
        raise SystemExit("canceled-selection trace line no longer matches lock")

    scenario = pm.load_scenario(str(scenario_path))
    validation_errors, validation_warnings = pm.validate_scenario(scenario)
    if validation_errors:
        raise SystemExit(f"scenario invalid: {validation_errors}")
    logs = primary_logs(results_dir)
    if len(logs) != 64:
        raise SystemExit(f"expected 64 primary logs, found {len(logs)}")

    run_results: list[dict[str, Any]] = []
    raw_hidden_findings: list[dict[str, Any]] = []
    raw_update_findings: list[dict[str, Any]] = []
    entry_key_union: set[str] = set()
    version_like_entry_keys: set[str] = set()
    all_run_metadata_modes: Counter[str] = Counter()
    model_setup_cells: Counter[tuple[str, str]] = Counter()

    state_visibility = pm.normalize_state_visibility(scenario)
    updates_by_day = pm.build_updates_by_day(scenario)
    scenario_days = {day["name"]: day for day in scenario["days"]}

    for log_path in logs:
        relative = log_path.relative_to(results_dir).as_posix()
        model = log_path.relative_to(results_dir).parts[0]
        setup = setup_from_run_dir(log_path.parent, model)
        model_setup_cells[(model, setup)] += 1
        entries, metadata = pm.read_log_with_metadata(str(log_path))
        if metadata:
            all_run_metadata_modes[str(metadata.get("mode"))] += 1
        for entry in entries:
            entry_key_union.update(entry.keys())
            version_like_entry_keys.update(
                key
                for key in entry.keys()
                if "version" in key.lower() or "target" in key.lower()
            )

        identity, aligned_entries = identity_audit(entries, scenario)
        official_summary, _, _ = pm.score_log(scenario, entries)
        aligned_summary = None
        score_changed_after_alignment = None
        if aligned_entries is not None:
            aligned_summary, _, _ = pm.score_log(scenario, aligned_entries)
            score_changed_after_alignment = official_summary != aligned_summary

        actions_by_day = {day["name"]: [] for day in scenario["days"]}
        for entry in entries:
            if entry.get("day") in actions_by_day:
                actions_by_day[entry["day"]].append(entry)

        traced_violation_count = 0
        accepted_late_violation_count = 0
        for day_name, day in scenario_days.items():
            day_updates = updates_by_day.get(day_name, {"pre": [], "by_step": {}})
            actions = actions_by_day[day_name]
            (_, task_states, violations) = traced_score_day(
                pm,
                day,
                actions,
                day_updates.get("pre", []),
                day_updates.get("by_step", {}),
                state_visibility,
            )
            traced_violation_count += len(violations)
            for violation in violations:
                finding = {
                    "run": relative,
                    "model": model,
                    "setup": setup,
                    **violation,
                }
                finding["accepted_late_current_state_by_scorer"] = bool(
                    violation["kind"] == "updated_off_due"
                    and violation["task_result_after_selection"] == "late"
                    and violation["state_updated"]
                )
                if finding["accepted_late_current_state_by_scorer"]:
                    accepted_late_violation_count += 1
                raw_update_findings.append(finding)

            step_index = {step["id"]: index for index, step in enumerate(day["steps"])}
            for task_id, state in task_states.items():
                if not state.get("completed") or state.get("result") not in {"hit", "late"}:
                    continue
                current = state["current"]
                if not pm.requires_state_monitoring(current, state_visibility):
                    continue
                channel = pm.required_monitor_channel(current)
                if channel is None:
                    continue
                completion_step_id = state.get("completed_at")
                completion_index = step_index[completion_step_id]
                completion_action = actions[completion_index]
                completion_query_count = pm.get_action_channel_query_count(
                    completion_action, channel
                )
                start_index = due_window_start_index(pm, day, state)
                if start_index is None:
                    start_index = completion_index
                opportunity_query_count = sum(
                    pm.get_action_channel_query_count(action, channel)
                    for action in actions[start_index : completion_index + 1]
                )
                raw_hidden_findings.append(
                    {
                        "run": relative,
                        "model": model,
                        "setup": setup,
                        "day": day_name,
                        "task_id": task_id,
                        "channel": channel,
                        "result": state["result"],
                        "completion_step_id": completion_step_id,
                        "due_window_start_step_id": day["steps"][start_index]["id"],
                        "completion_row_required_query_count": completion_query_count,
                        "due_to_completion_required_query_count": opportunity_query_count,
                        "official_completion_had_required_query": bool(
                            state.get("completion_had_required_query")
                        ),
                    }
                )

        if traced_violation_count != official_summary["update_violation"]:
            raise AssertionError(f"run trace mismatch: {relative}")

        inferred_type = (
            "replay"
            if (metadata and str(metadata.get("mode", "")).startswith("replay-"))
            else "live"
        )
        expected_type = "replay" if setup in REPLAY_SETUPS else "live"
        run_results.append(
            {
                "run": relative,
                "model": model,
                "setup": setup,
                "expected_run_type": expected_type,
                "metadata_run_type": inferred_type,
                "metadata_mode": metadata.get("mode") if metadata else None,
                "duration_seconds": metadata.get("duration_seconds") if metadata else None,
                "identity": identity,
                "official_summary": compact_summary(official_summary),
                "aligned_summary": (
                    compact_summary(aligned_summary) if aligned_summary is not None else None
                ),
                "score_changed_after_identity_alignment": score_changed_after_alignment,
                "accepted_late_update_violation_count": accepted_late_violation_count,
            }
        )

    if set(model for model, _ in model_setup_cells) != EXPECTED_MODELS:
        raise AssertionError("model inventory mismatch")
    if set(setup for _, setup in model_setup_cells) != EXPECTED_SETUPS:
        raise AssertionError("setup inventory mismatch")
    if any(count != 1 for count in model_setup_cells.values()):
        raise AssertionError("model/setup grid is not one run per cell")
    if len(model_setup_cells) != 64:
        raise AssertionError("model/setup grid is incomplete")

    hidden_without_completion_query = [
        finding
        for finding in raw_hidden_findings
        if finding["completion_row_required_query_count"] == 0
    ]
    hidden_without_opportunity_query = [
        finding
        for finding in raw_hidden_findings
        if finding["due_to_completion_required_query_count"] == 0
    ]

    def grouped_hidden(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: Counter[tuple[str, str, str, str]] = Counter(
            (
                finding["model"],
                finding["setup"],
                finding["channel"],
                finding["result"],
            )
            for finding in findings
        )
        return [
            {
                "model": model,
                "setup": setup,
                "channel": channel,
                "result": result,
                "count": count,
            }
            for (model, setup, channel, result), count in sorted(counts.items())
        ]

    identity_problem_runs = [
        run for run in run_results if not run["identity"]["identity_valid"]
    ]
    within_day_order_problem_runs = [
        run
        for run in run_results
        if run["identity"]["within_day_out_of_order"]
    ]
    global_order_problem_runs = [
        run
        for run in run_results
        if not run["identity"]["global_day_row_order_matches"]
    ]
    changed_after_alignment = [
        run
        for run in run_results
        if run["score_changed_after_identity_alignment"] is True
    ]

    aggregate_by_setup: list[dict[str, Any]] = []
    for setup in sorted(EXPECTED_SETUPS):
        subset = [run for run in run_results if run["setup"] == setup]
        tp = sum(run["official_summary"]["set_tp"] for run in subset)
        fp = sum(run["official_summary"]["set_fp"] for run in subset)
        fn = sum(run["official_summary"]["set_fn"] for run in subset)
        f1_values = [set_f1(run["official_summary"]) for run in subset]
        macro_f1 = statistics.mean(value for value in f1_values if value is not None)
        aggregate_by_setup.append(
            {
                "setup": setup,
                "run_type": "replay" if setup in REPLAY_SETUPS else "live",
                "run_count": len(subset),
                "set_tp": tp,
                "set_fp": fp,
                "set_fn": fn,
                "macro_set_f1": macro_f1,
                "micro_set_f1": (2 * tp / (2 * tp + fp + fn)),
                "state_query_calls": sum(
                    run["official_summary"]["state_query_calls"] for run in subset
                ),
                "duration_seconds_sum": sum(
                    float(run["duration_seconds"] or 0.0) for run in subset
                ),
            }
        )
    for row in aggregate_by_setup:
        expected_macro, expected_micro = EXPECTED_TABLE_2[row["setup"]]
        observed = (
            round(row["macro_set_f1"] * 100, 1),
            round(row["micro_set_f1"] * 100, 1),
        )
        if observed != (expected_macro, expected_micro):
            raise AssertionError(
                f"Table 2 mismatch for {row['setup']}: {observed} != "
                f"{(expected_macro, expected_micro)}"
            )

    accepted_late_update_violations = [
        finding
        for finding in raw_update_findings
        if finding["accepted_late_current_state_by_scorer"]
    ]
    run_type_mismatches = [
        run
        for run in run_results
        if run["expected_run_type"] != run["metadata_run_type"]
    ]

    result = {
        "artifact": "PM-Bench released trajectory scorer-contract audit",
        "status": "PASS",
        "source": {
            "repository": "genglinliu/PMBench",
            "commit": head,
            "dirty": bool(dirty),
            "pm_bench_py_sha256": sha256(source_file),
            "synthetic_week_v9_sha256": sha256(scenario_path),
        },
        "scenario": {
            "validation_errors": validation_errors,
            "validation_warnings": validation_warnings,
            "days": len(scenario["days"]),
            "steps": len(expected_step_pairs(scenario)),
            "tasks": sum(len(day["tasks"]) for day in scenario["days"]),
        },
        "inventory": {
            "primary_run_count": len(logs),
            "model_count": len(EXPECTED_MODELS),
            "setup_count": len(EXPECTED_SETUPS),
            "model_setup_cells": len(model_setup_cells),
            "live_run_count": sum(
                run["expected_run_type"] == "live" for run in run_results
            ),
            "replay_run_count": sum(
                run["expected_run_type"] == "replay" for run in run_results
            ),
            "metadata_modes": dict(sorted(all_run_metadata_modes.items())),
            "run_type_mismatch_count": len(run_type_mismatches),
        },
        "step_identity": {
            "identity_problem_run_count": len(identity_problem_runs),
            "within_day_out_of_order_run_count": len(within_day_order_problem_runs),
            "global_day_row_order_problem_run_count": len(global_order_problem_runs),
            "score_changed_after_identity_alignment_run_count": len(changed_after_alignment),
            "rejected_alignment_run_count": len(identity_problem_runs),
            "identity_problem_runs": identity_problem_runs,
            "within_day_order_problem_runs": within_day_order_problem_runs,
            "global_order_problem_runs": global_order_problem_runs,
            "changed_after_alignment": changed_after_alignment,
        },
        "hidden_channel_attribution": {
            "completed_proactive_required_task_count": len(raw_hidden_findings),
            "without_required_query_on_completion_row_count": len(
                hidden_without_completion_query
            ),
            "without_required_query_from_due_through_completion_count": len(
                hidden_without_opportunity_query
            ),
            "grouped_without_completion_row_query": grouped_hidden(
                hidden_without_completion_query
            ),
            "grouped_without_due_to_completion_query": grouped_hidden(
                hidden_without_opportunity_query
            ),
        },
        "update_violation": {
            "total_increment_count": len(raw_update_findings),
            "accepted_late_current_state_by_scorer_count": len(
                accepted_late_update_violations
            ),
            "machine_readable_selection_fields": sorted(entry_key_union),
            "version_or_target_named_selection_fields": sorted(version_like_entry_keys),
            "semantic_retired_vs_current_intention_reconstructable": False,
            "semantic_current_version_lower_bound": 0,
            "semantic_current_version_upper_bound": len(
                accepted_late_update_violations
            ),
            "boundary": (
                "The scorer applies every selected task_id to the mutable current task state. "
                "Released action rows do not bind a selection to an intention version or target. "
                "The exact scorer-level co-occurrence is measurable; the agent's retired-versus-current "
                "intention is not reconstructable, so its semantic count is bounded from zero to the "
                "scorer-level co-occurrence count."
            ),
        },
        "aggregates_by_setup": aggregate_by_setup,
        "duration_treatment": {
            "live_duration_missing_count": sum(
                run["expected_run_type"] == "live" and run["duration_seconds"] is None
                for run in run_results
            ),
            "replay_duration_missing_count": sum(
                run["expected_run_type"] == "replay" and run["duration_seconds"] is None
                for run in run_results
            ),
            "replay_zero_duration_count": sum(
                run["expected_run_type"] == "replay"
                and float(run["duration_seconds"] or 0.0) == 0.0
                for run in run_results
            ),
            "boundary": (
                "Replay metadata duration is deterministic replay time, not fresh model inference time; "
                "zero must not be compared as agent runtime against live configurations."
            ),
        },
        "grand_totals": {
            "set_tp": sum(run["official_summary"]["set_tp"] for run in run_results),
            "set_fp": sum(run["official_summary"]["set_fp"] for run in run_results),
            "set_fn": sum(run["official_summary"]["set_fn"] for run in run_results),
            "state_query_calls": sum(
                run["official_summary"]["state_query_calls"] for run in run_results
            ),
            "update_violation": sum(
                run["official_summary"]["update_violation"] for run in run_results
            ),
            "update_late": sum(
                run["official_summary"]["update_late"] for run in run_results
            ),
        },
        "boundary": (
            "Read-only audit of released scorer inputs at the locked commit. No model calls, "
            "new benchmark run, population estimate, or causal attribution."
        ),
    }
    return result, run_results, raw_hidden_findings, raw_update_findings


def render_results(decision: dict[str, Any]) -> str:
    hidden = decision["hidden_channel_attribution"]
    update = decision["update_violation"]
    identity = decision["step_identity"]
    totals = decision["grand_totals"]
    optional = next(
        row
        for row in decision["aggregates_by_setup"]
        if row["setup"] == "heartbeat-proactive"
    )
    return "\n".join(
        [
            "PM-Bench scorer-contract and released-log audit",
            f"official source revision {EXPECTED_COMMIT}",
            "status: PASS",
            "official scorer probes: PASS (A hidden-channel attribution; B update violation; C row identity)",
            "official scenario validation: PASS",
            "released primary logs: 64 (8 models x 8 setups; 48 live, 16 replay-derived)",
            (
                "proactive-required successful completions: "
                f"{hidden['completed_proactive_required_task_count']}"
            ),
            (
                "without required-channel query on completion row: "
                f"{hidden['without_required_query_on_completion_row_count']}"
            ),
            (
                "without required-channel query from due/cue through completion: "
                f"{hidden['without_required_query_from_due_through_completion_count']}"
            ),
            f"update_violation scorer increments: {update['total_increment_count']}",
            (
                "accepted-late current-mutable-state co-occurrences: "
                f"{update['accepted_late_current_state_by_scorer_count']}"
            ),
            "semantic current-version count reconstructable: no (bounded 0..27)",
            f"released logs with invalid (day, step_id) identity: {identity['identity_problem_run_count']}",
            (
                "released logs whose score changed after identity alignment: "
                f"{identity['score_changed_after_identity_alignment_run_count']}"
            ),
            (
                "optional-heartbeat across-model macro Set-F1: "
                f"{optional['macro_set_f1'] * 100:.1f}%"
            ),
            (
                "grand totals: "
                f"TP={totals['set_tp']} FP={totals['set_fp']} FN={totals['set_fn']} "
                f"state_queries={totals['state_query_calls']}"
            ),
            "official report rebuild: metric/text equality after repairing one stale results-directory path",
            "headline Set-F1 changed by this audit: no",
            (
                "boundary: deterministic scorer-contract and released-input audit; no model calls, "
                "new benchmark run, causal attribution, or population estimate"
            ),
            "",
        ]
    )


def source_manifest(source_repo: Path) -> dict[str, Any]:
    results_dir = source_repo / "runs" / "all_results_v9"
    log_hashes = {
        path.relative_to(results_dir).as_posix(): sha256(path)
        for path in primary_logs(results_dir)
    }
    return {
        "repository": "https://github.com/genglinliu/PMBench",
        "commit": EXPECTED_COMMIT,
        "checkout_requirement": "exact commit and clean worktree",
        "files": {
            "sim/pm_bench.py": EXPECTED_PM_BENCH_SHA256,
            "data/synthetic_week_v9.json": EXPECTED_SCENARIO_SHA256,
            "runs/all_results_v9/build_experiment_output_comparison_report.py": (
                EXPECTED_REPORT_BUILDER_SHA256
            ),
            "runs/all_results_v9/experiment_output_comparison_report.md": (
                EXPECTED_REPORT_SHA256
            ),
        },
        "released_primary_log_sha256": log_hashes,
        "source_locators_at_locked_commit": {
            "requires_state_monitoring": "sim/pm_bench.py:2206-2214",
            "required_monitor_channel": "sim/pm_bench.py:2217-2226",
            "monitoring_and_channel_buckets": "sim/pm_bench.py:2522-2581",
            "updated_off_due_violation": "sim/pm_bench.py:2517-2518",
            "row_order_grouping": "sim/pm_bench.py:2586-2589",
            "positional_action_consumption": "sim/pm_bench.py:2350-2367",
        },
    }


def environment_text() -> str:
    return "\n".join(
        [
            f"OS: {platform.system()} {platform.release()}",
            f"Architecture: {platform.machine()}",
            f"Python: {platform.python_version()}",
            "Dependencies: Python standard library plus Git CLI; official source imports its bundled scorer",
            "Network: no network call",
            "Models/APIs: not invoked",
            "Official source mutation: none; clean status required before and after execution",
            "",
        ]
    )


def write_checksum_manifest(root: Path) -> None:
    missing = sorted(name for name in GENERATED_FILES if not (root / name).is_file())
    if missing:
        raise AssertionError(f"cannot write manifest; missing generated files: {missing}")
    manifest = "".join(
        f"{sha256(root / name)}  {name}\n" for name in sorted(GENERATED_FILES)
    )
    (root / "checksums.sha256").write_text(manifest, encoding="utf-8")


def read_checksum_manifest(root: Path) -> dict[str, str]:
    path = root / "checksums.sha256"
    if not path.is_file():
        raise SystemExit(f"missing checksum manifest: {path}")
    observed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if relative in observed:
            raise SystemExit(f"duplicate checksum entry: {relative}")
        observed[relative] = digest
    if set(observed) != GENERATED_FILES:
        raise SystemExit(
            f"checksum file set mismatch: {sorted(observed)} != {sorted(GENERATED_FILES)}"
        )
    return observed


def verify_checked(root: Path) -> None:
    manifest = read_checksum_manifest(root)
    for relative, expected in manifest.items():
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"missing checked file: {relative}")
        observed = sha256(path)
        if observed != expected:
            raise SystemExit(
                f"checksum mismatch for {relative}: {observed} != {expected}"
            )


def compare_checked(checked: Path, rebuilt: Path) -> None:
    checked_manifest = read_checksum_manifest(checked)
    rebuilt_manifest = read_checksum_manifest(rebuilt)
    if checked_manifest != rebuilt_manifest:
        raise SystemExit("rebuilt checksum manifest differs from checked publication")
    for relative in sorted(GENERATED_FILES | {"checksums.sha256"}):
        if (checked / relative).read_bytes() != (rebuilt / relative).read_bytes():
            raise SystemExit(f"rebuilt bytes differ: {relative}")


def generate(source_repo: Path, output_dir: Path) -> None:
    source_repo = source_repo.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    collisions = sorted(
        name
        for name in GENERATED_FILES | {"checksums.sha256"}
        if (output_dir / name).exists()
    )
    if collisions:
        raise SystemExit(
            "refusing to overwrite generated output; choose a new --output-dir: "
            + ", ".join(collisions)
        )

    probes_pm, _ = load_official_module(source_repo)
    probes = run_official_probes(probes_pm)
    decision, runs, hidden_findings, update_findings = run_released_audit(source_repo)
    report = rebuild_and_compare_report(source_repo)
    if git(source_repo, "status", "--porcelain"):
        raise SystemExit("official checkout became dirty during audit")

    raw = output_dir / "raw"
    write_json(raw / "official_probes.json", probes)
    write_json(raw / "decision.json", decision)
    write_json(raw / "report_comparison.json", report)
    write_json(raw / "source_manifest.json", source_manifest(source_repo))
    write_jsonl(raw / "run_scores.jsonl", runs)
    write_jsonl(raw / "hidden_channel_findings.jsonl", hidden_findings)
    write_jsonl(raw / "update_violation_findings.jsonl", update_findings)
    (raw / "environment.txt").write_text(environment_text(), encoding="utf-8")
    (output_dir / "RESULTS.txt").write_text(render_results(decision), encoding="utf-8")
    write_checksum_manifest(output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--verify-checked", action="store_true")
    parser.add_argument("--compare-checked", action="store_true")
    args = parser.parse_args()
    artifact_root = Path(__file__).resolve().parent

    if args.verify_checked:
        verify_checked(artifact_root)
        print("checked artifact: PASS")
        if not args.source_repo and not args.compare_checked:
            return 0

    if args.source_repo:
        if args.output_dir is None:
            parser.error("--output-dir is required with --source-repo")
        generate(args.source_repo, args.output_dir)
        print(f"rebuilt artifact: {args.output_dir.resolve()}")

    if args.compare_checked:
        if args.output_dir is None:
            parser.error("--output-dir is required with --compare-checked")
        compare_checked(artifact_root, args.output_dir.resolve())
        print("checked versus rebuilt bytes: PASS")

    if not (args.verify_checked or args.source_repo or args.compare_checked):
        parser.error("choose --verify-checked and/or provide --source-repo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
