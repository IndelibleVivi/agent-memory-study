#!/usr/bin/env python3
"""Offline fixed released-artifact audit for MEMPROBE.

This runner intentionally uses only the Python standard library.  It never
imports upstream code, never executes a model or retriever, and never emits
upstream free text.  Its public receipts contain identifiers, locators,
counts, enumerated states, fixed numeric scores, and cryptographic digests.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import locale
import math
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable


sys.dont_write_bytecode = True

SOURCE_COMMIT = "19bb83644b082489b4e181e59f1cded1a00d0529"
PAPER_SHA256 = "e5b3699c00a0731cc00e165f12efb755c57886058e311c01e5643df6e56897b5"
SCHEMA_VERSION = 1

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

RUNS: dict[str, dict[str, str]] = {
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
BASE_RUNS = tuple(sorted({spec["base"] for spec in RUNS.values()}))
RETRIEVE_RUNS = tuple(run for run, spec in RUNS.items() if spec["mode"] == "retrieve")
QUARTER_SCORES = {Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1)}

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


class AuditFailure(RuntimeError):
    """A contract failure with a reader-meaningful message."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(source: Path, *args: str) -> str:
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(source), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def strict_equal(left: Any, right: Any) -> bool:
    """Recursive JSON equality that never equates different scalar types."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(strict_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(strict_equal(a, b) for a, b in zip(left, right))
    return left == right


def typed_form(value: Any) -> Any:
    """Canonical, type-tagged form used only for equality-preserving digests."""
    if value is None:
        return {"type": "null"}
    if type(value) is bool:
        return {"type": "boolean", "value": value}
    if type(value) is int:
        return {"type": "integer", "value": str(value)}
    if type(value) is Decimal:
        return {"type": "decimal", "value": str(value)}
    if type(value) is float:
        return {"type": "binary64", "value": value.hex()}
    if type(value) is str:
        return {"type": "string", "value": value}
    if isinstance(value, list):
        return {"type": "array", "value": [typed_form(item) for item in value]}
    if isinstance(value, tuple):
        return {"type": "tuple", "value": [typed_form(item) for item in value]}
    if isinstance(value, dict):
        return {
            "type": "object",
            "value": [[key, typed_form(value[key])] for key in sorted(value)],
        }
    raise TypeError(f"unsupported value in typed digest: {type(value).__name__}")


def typed_digest(value: Any) -> str:
    payload = json.dumps(typed_form(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return sha256_bytes(payload.encode("utf-8"))


def load_json_bytes(payload: bytes, label: str) -> Any:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AuditFailure(f"duplicate JSON object key in {label}: {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise AuditFailure(f"nonstandard JSON numeric constant in {label}: {value}")

    try:
        return json.loads(
            payload.decode("utf-8"),
            parse_float=Decimal,
            parse_int=int,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditFailure(f"unreadable JSON: {label}: {exc}") from exc


def dump_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(dump_json_bytes(value))


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def fraction_of(value: Any) -> Fraction:
    if type(value) is int:
        return Fraction(value)
    if type(value) is Decimal:
        return Fraction(value)
    raise AuditFailure(f"score is not a JSON integer/decimal: {type(value).__name__}")


def fraction_record(value: Fraction) -> dict[str, Any]:
    return {
        "denominator": value.denominator,
        "float": float(value),
        "numerator": value.numerator,
    }


def numeric_record(value: Any) -> dict[str, Any]:
    fraction = fraction_of(value)
    return {
        "json_type": "integer" if type(value) is int else "decimal",
        "literal": str(value),
        **fraction_record(fraction),
    }


def numeric_close(exact: Fraction, stored: Any, tolerance: float = 1e-12) -> bool:
    if type(stored) not in (int, Decimal):
        return False
    return abs(float(exact) - float(stored)) <= tolerance


def classify_string_field(container: dict[str, Any], key: str) -> dict[str, Any]:
    if key not in container:
        return {"state": "FIELD_ABSENT"}
    value = container[key]
    if value is None:
        return {"state": "NULL"}
    if type(value) is not str:
        return {"state": "WRONG_TYPE", "json_type": type(value).__name__}
    if value == "":
        state = "EMPTY_STRING"
    elif value.strip() == "":
        state = "WHITESPACE_ONLY"
    else:
        state = "NONEMPTY_STRING"
    return {
        "state": state,
        "sha256": typed_digest(value),
        "exact_literal_unknown": value == "unknown",
    }


def classify_score(container: dict[str, Any], key: str = "score") -> dict[str, Any]:
    if key not in container:
        return {"state": "MISSING"}
    value = container[key]
    if value is None:
        return {"state": "NULL"}
    if type(value) not in (int, Decimal):
        return {"state": "WRONG_TYPE", "json_type": type(value).__name__}
    fraction = fraction_of(value)
    return {
        "state": "VALID_QUARTER_STEP" if fraction in QUARTER_SCORES else "OUT_OF_RUBRIC",
        "value": numeric_record(value),
    }


def public_score(value: Any) -> float:
    return float(fraction_of(value))


def safe_relative(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise AuditFailure(f"input escaped source root: {path}") from exc
    if relative.startswith("../") or relative.startswith("/"):
        raise AuditFailure(f"unsafe relative input path: {relative}")
    return relative


class EvidenceReader:
    """Reads registered evidence while retaining a complete hash manifest."""

    def __init__(self, source: Path, paper_pdf: Path):
        self.source = source
        self.paper_pdf = paper_pdf
        self.records: dict[str, dict[str, Any]] = {}
        self.cache: dict[str, Any] = {}
        self.denied_strings: set[str] = set()
        self.denied_eight_token_spans: set[str] = set()

    def _record(self, key: str, payload: bytes, scope: str, locator: str) -> None:
        record = {
            "input_scope": scope,
            "locator": locator,
            "sha256": sha256_bytes(payload),
            "size_bytes": len(payload),
        }
        prior = self.records.get(key)
        if prior is not None and prior != record:
            raise AuditFailure(f"input changed during read: {key}")
        self.records[key] = record

    def read_source_bytes(self, relative: str) -> bytes:
        key = f"source:{relative}"
        path = self.source / relative
        if not path.is_file():
            raise AuditFailure(f"required source file absent: {relative}")
        payload = path.read_bytes()
        self._record(key, payload, "official_source", relative)
        return payload

    def read_source_json(self, relative: str) -> Any:
        key = f"source:{relative}"
        if key not in self.cache:
            self.cache[key] = load_json_bytes(self.read_source_bytes(relative), relative)
        return self.cache[key]

    def read_paper(self) -> bytes:
        key = "paper:arxiv-2606.24595v1.pdf"
        if not self.paper_pdf.is_file():
            raise AuditFailure("paper PDF is absent")
        payload = self.paper_pdf.read_bytes()
        self._record(key, payload, "paper", "arxiv-2606.24595v1.pdf")
        return payload

    def mark_denied(self, value: Any) -> None:
        if type(value) is str:
            if value:
                self.denied_strings.add(value)
                tokens = re.findall(r"[^\W_]+(?:['’-][^\W_]+)*", value.casefold(), flags=re.UNICODE)
                for index in range(max(0, len(tokens) - 7)):
                    self.denied_eight_token_spans.add(" ".join(tokens[index:index + 8]))
            return
        if isinstance(value, list):
            for item in value:
                self.mark_denied(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                self.mark_denied(item)

    def manifest(self) -> list[dict[str, Any]]:
        return [self.records[key] for key in sorted(self.records)]

    def verify_unchanged(self) -> bool:
        for key, expected in self.records.items():
            if key.startswith("source:"):
                path = self.source / expected["locator"]
            else:
                path = self.paper_pdf
            if not path.is_file() or path.stat().st_size != expected["size_bytes"] or sha256_file(path) != expected["sha256"]:
                return False
        return True


class NetworkGuard:
    """Process-local DNS/socket denial with a deterministic attempt receipt."""

    def __init__(self) -> None:
        self.attempts: list[str] = []
        self.originals: list[tuple[Any, str, Any]] = []

    def _deny(self, surface: str) -> Callable[..., Any]:
        def denied(*_args: Any, **_kwargs: Any) -> Any:
            self.attempts.append(surface)
            raise RuntimeError(f"network access blocked by audit guard: {surface}")
        return denied

    def install(self) -> None:
        targets = (
            (socket, "create_connection"),
            (socket, "getaddrinfo"),
            (socket, "gethostbyname"),
            (socket, "gethostbyname_ex"),
            (socket.socket, "connect"),
            (socket.socket, "connect_ex"),
        )
        for owner, name in targets:
            self.originals.append((owner, name, getattr(owner, name)))
            setattr(owner, name, self._deny(f"{owner.__name__}.{name}"))

    def restore(self) -> None:
        for owner, name, value in reversed(self.originals):
            setattr(owner, name, value)
        self.originals.clear()


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuditFailure(f"expected object: {label}")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AuditFailure(f"expected list: {label}")
    return value


def require_exact_names(actual: Iterable[str], expected: Iterable[str], label: str) -> None:
    actual_set, expected_set = set(actual), set(expected)
    if actual_set != expected_set:
        raise AuditFailure(
            f"{label} mismatch: missing={sorted(expected_set-actual_set)} extra={sorted(actual_set-expected_set)}"
        )


def validate_source_identity(source: Path) -> None:
    if run_git(source, "rev-parse", "HEAD") != SOURCE_COMMIT:
        raise AuditFailure("official checkout is not at the frozen revision")
    if run_git(source, "status", "--porcelain=v1", "--untracked-files=all"):
        raise AuditFailure("official checkout is dirty")


def deny_bank_and_tasks(reader: EvidenceReader, bank: dict[str, Any], tasks_by_user: dict[str, dict[str, Any]]) -> None:
    for user in bank["users"]:
        reader.mark_denied(user.get("base_profile", {}))
        for entries in user["memory_bank"].values():
            for entry in entries:
                reader.mark_denied(entry.get("short"))
                reader.mark_denied(entry.get("explanation"))
    for task_file in tasks_by_user.values():
        for task in task_file["tasks"]:
            for key in ("task", "rationale", "target_short", "pipeline_note"):
                reader.mark_denied(task.get(key))


def load_bank_and_tasks(reader: EvidenceReader) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[tuple[str, str], dict[str, Any]]]]:
    bank_relative = "Deeppersona/data/user_memory_banks_pooled_final.json"
    bank = require_object(reader.read_source_json(bank_relative), bank_relative)
    if set(bank) != {"generated_at", "source", "num_users", "users"}:
        raise AuditFailure("hidden bank root schema mismatch")
    if type(bank.get("generated_at")) is not str or type(bank.get("source")) is not str or type(bank.get("num_users")) is not int or bank.get("num_users") != 50:
        raise AuditFailure("hidden bank num_users is not 50")
    users_list = require_list(bank.get("users"), "hidden bank users")
    if [item.get("user_id") for item in users_list] != list(USERS):
        raise AuditFailure("hidden bank user registry/order mismatch")

    tasks_dir = reader.source / "benchmark_data/CustomTasksPooledFinal"
    require_exact_names((path.name for path in tasks_dir.glob("user_*.json")), (f"{user}.json" for user in USERS), "task files")
    tasks_by_user: dict[str, dict[str, Any]] = {}
    bank_index: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for user_record in users_list:
        user_id = user_record["user_id"]
        if type(user_id) is not str or not isinstance(user_record.get("base_profile"), dict):
            raise AuditFailure(f"hidden user schema/type mismatch: {user_id!r}")
        memory_bank = require_object(user_record.get("memory_bank"), f"memory bank {user_id}")
        require_exact_names(memory_bank, CATEGORIES, f"categories {user_id}")
        indexed: dict[tuple[str, str], dict[str, Any]] = {}
        for category in CATEGORIES:
            entries = require_list(memory_bank[category], f"{user_id}/{category}")
            if len(entries) != CATEGORY_COUNTS[category]:
                raise AuditFailure(f"category cardinality mismatch: {user_id}/{category}")
            dimensions: set[str] = set()
            for entry in entries:
                if set(entry) != {"dimension", "short", "explanation"}:
                    raise AuditFailure(f"hidden entry schema mismatch: {user_id}/{category}")
                dimension = entry["dimension"]
                if (
                    type(dimension) is not str
                    or type(entry["short"]) is not str
                    or type(entry["explanation"]) is not str
                    or dimension in dimensions
                ):
                    raise AuditFailure(f"hidden dimension duplicate/type mismatch: {user_id}/{category}")
                dimensions.add(dimension)
                indexed[(category, dimension)] = entry
        bank_index[user_id] = indexed

        relative = f"benchmark_data/CustomTasksPooledFinal/{user_id}.json"
        task_file = require_object(reader.read_source_json(relative), relative)
        if set(task_file) != {"user_id", "generated_at", "n_tasks", "tasks"} or type(task_file.get("generated_at")) is not str:
            raise AuditFailure(f"task root schema mismatch: {user_id}")
        if task_file.get("user_id") != user_id or type(task_file.get("n_tasks")) is not int or task_file.get("n_tasks") != 31:
            raise AuditFailure(f"task header mismatch: {user_id}")
        tasks = require_list(task_file.get("tasks"), f"tasks {user_id}")
        if len(tasks) != 31:
            raise AuditFailure(f"task count mismatch: {user_id}")
        task_keys = [(task.get("target_category"), task.get("target_dimension")) for task in tasks]
        if len(set(task_keys)) != 31 or set(task_keys) != set(indexed):
            raise AuditFailure(f"task target set mismatch: {user_id}")
        for task in tasks:
            if set(task) != {"task", "rationale", "target_category", "target_dimension", "target_short", "pipeline_note"}:
                raise AuditFailure(f"task item schema mismatch: {user_id}")
            if any(type(task[key]) is not str for key in task):
                raise AuditFailure(f"task item type mismatch: {user_id}")
            bank_entry = indexed[(task["target_category"], task["target_dimension"])]
            if not strict_equal(task.get("target_short"), bank_entry["short"]):
                raise AuditFailure(f"task target value drift: {user_id}/{task['target_dimension']}")
        tasks_by_user[user_id] = task_file
    deny_bank_and_tasks(reader, bank, tasks_by_user)
    return bank, tasks_by_user, bank_index


def read_histories(
    reader: EvidenceReader,
    tasks_by_user: dict[str, dict[str, Any]],
) -> tuple[dict[tuple[str, str, int], dict[str, Any]], dict[str, Any]]:
    history_root = reader.source / "history"
    require_exact_names((path.name for path in history_root.iterdir() if path.is_dir()), BASE_RUNS, "history run directories")
    episodes: dict[tuple[str, str, int], dict[str, Any]] = {}
    turn_state_counts: Counter[str] = Counter()
    for base_run in BASE_RUNS:
        run_dir = history_root / base_run
        require_exact_names((path.name for path in run_dir.iterdir() if path.is_dir()), USERS, f"history users {base_run}")
        for user_id in USERS:
            user_dir = run_dir / user_id
            require_exact_names(
                (path.name for path in user_dir.glob("episode_*.json")),
                (f"episode_{index}.json" for index in range(1, 32)),
                f"history episodes {base_run}/{user_id}",
            )
            for index, task in enumerate(tasks_by_user[user_id]["tasks"], 1):
                relative = f"history/{base_run}/{user_id}/episode_{index}.json"
                episode = require_object(reader.read_source_json(relative), relative)
                reader.mark_denied(episode.get("task"))
                reader.mark_denied(episode.get("ground_truth"))
                turns = require_list(episode.get("turns"), f"turns {relative}")
                has_agent = False
                has_user = False
                for turn in turns:
                    agent_value = turn.get("agent_response")
                    user_value = (turn.get("user_simulator") or {}).get("text") if isinstance(turn.get("user_simulator"), dict) else None
                    reader.mark_denied(agent_value)
                    reader.mark_denied(user_value)
                    has_agent = has_agent or (type(agent_value) is str and bool(agent_value.strip()))
                    has_user = has_user or (type(user_value) is str and bool(user_value.strip()))
                state = "BOTH_NONEMPTY" if has_agent and has_user else "INCOMPLETE_OR_EMPTY"
                turn_state_counts[state] += 1
                if episode.get("user_id") != user_id or not strict_equal(episode.get("task"), task.get("task")):
                    raise AuditFailure(f"episode identity/task mismatch: {relative}")
                episodes[(base_run, user_id, index)] = episode
    return episodes, {
        "episode_count": len(episodes),
        "turn_content_states": dict(sorted(turn_state_counts.items())),
    }


def read_store_census(reader: EvidenceReader) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, Any]]:
    memory_root = reader.source / "memory"
    require_exact_names((path.name for path in memory_root.iterdir() if path.is_dir()), BASE_RUNS, "memory run directories")
    stores: dict[tuple[str, str], list[dict[str, Any]]] = {}
    run_rows: list[dict[str, Any]] = []
    for run in BASE_RUNS:
        run_dir = memory_root / run
        require_exact_names((path.name for path in run_dir.iterdir() if path.is_dir()), USERS, f"memory users {run}")
        counts: list[int] = []
        declared_ok = True
        native_raw_dirs = 0
        for user_id in USERS:
            relative = f"memory/{run}/{user_id}/memories.json"
            payload = require_object(reader.read_source_json(relative), relative)
            if set(payload) != {"num_memories", "memories"} or type(payload.get("num_memories")) is not int:
                raise AuditFailure(f"memory store root schema mismatch: {relative}")
            memories = require_list(payload.get("memories"), f"memories {relative}")
            declared_ok = declared_ok and type(payload.get("num_memories")) is int and payload["num_memories"] == len(memories)
            counts.append(len(memories))
            stores[(run, user_id)] = memories
            for item in memories:
                if not isinstance(item, dict):
                    raise AuditFailure(f"memory item is not an object: {relative}")
                for key, value in item.items():
                    if key not in {"id", "category", "timestamp", "task_index", "turn"}:
                        reader.mark_denied(value)
            if (reader.source / f"memory/{run}/{user_id}/raw").exists():
                native_raw_dirs += 1
        run_rows.append({
            "declared_counts_reconcile": declared_ok,
            "maximum_items_per_user": max(counts),
            "minimum_items_per_user": min(counts),
            "native_raw_directories": native_raw_dirs,
            "run_id": run,
            "total_items": sum(counts),
            "users": len(counts),
        })
    result = {
        "schema": f"memprobe-store-census/{SCHEMA_VERSION}",
        "runs": run_rows,
        "all_declared_counts_reconcile": all(row["declared_counts_reconcile"] for row in run_rows),
    }
    return stores, result


def validate_packet_item(system: str, packet: dict[str, Any], store: list[dict[str, Any]]) -> tuple[bool, list[int]]:
    """Frozen system adapters from PROTOCOL.md; no runtime inference."""
    if system == "amem":
        expected = {"id", "content", "keywords", "context", "tags", "category", "score"}
        schema_ok = set(packet) == expected
        schema_ok = schema_ok and all(type(packet[key]) is str for key in ("id", "content", "context", "category"))
        schema_ok = schema_ok and all(
            isinstance(packet[key], list) and all(type(value) is str for value in packet[key])
            for key in ("keywords", "tags")
        )
        schema_ok = schema_ok and type(packet["score"]) in (int, Decimal)
        if not schema_ok:
            return False, []
        matches = [
            index for index, item in enumerate(store)
            if isinstance(item, dict)
            and strict_equal(item.get("id"), packet["id"])
            and strict_equal(item.get("content"), packet["content"])
        ]
        return True, matches
    if system == "longctx_full":
        allowed = (
            {"content", "category", "task_index", "score"},
            {"content", "category", "task_index", "turn", "score"},
        )
        if (
            set(packet) not in allowed
            or type(packet.get("score")) not in (int, Decimal)
            or type(packet.get("content")) is not str
            or type(packet.get("category")) is not str
            or type(packet.get("task_index")) is not int
            or ("turn" in packet and type(packet.get("turn")) is not int)
        ):
            return False, []
        candidate = {key: value for key, value in packet.items() if key != "score"}
        matches = [index for index, item in enumerate(store) if strict_equal(item, candidate)]
        return True, matches
    if system == "mem0":
        expected = {"id", "content", "category", "metadata", "timestamp"}
        schema_ok = set(packet) == expected
        schema_ok = schema_ok and all(type(packet[key]) is str for key in ("id", "content", "category", "timestamp"))
        schema_ok = schema_ok and packet.get("metadata") is None
        if not schema_ok:
            return False, []
        matches = [index for index, item in enumerate(store) if strict_equal(item, packet)]
        return True, matches
    if system == "memt":
        expected = {"id", "content", "category", "score", "timestamp"}
        schema_ok = set(packet) == expected and packet.get("score") is None
        schema_ok = schema_ok and all(type(packet[key]) is str for key in ("id", "content", "category", "timestamp"))
        if not schema_ok:
            return False, []
        matches = []
        for index, item in enumerate(store):
            metadata = item.get("metadata") if isinstance(item, dict) else None
            if not isinstance(metadata, dict):
                continue
            if (
                strict_equal(item.get("id"), packet["id"])
                and strict_equal(metadata.get("memory_content"), packet["content"])
                and strict_equal(item.get("category"), packet["category"])
                and strict_equal(item.get("timestamp"), packet["timestamp"])
            ):
                matches.append(index)
        return True, matches
    raise AuditFailure(f"unregistered adapter system: {system}")


def legal_attribution_reduction(
    score: Any,
    attribution: dict[str, Any],
    expected_episode_index: int | None = None,
) -> tuple[bool, str | None, list[dict[str, Any]]]:
    score_fraction = fraction_of(score)
    stages = attribution.get("stages")
    if not isinstance(stages, list):
        return False, None, []
    expected_root_keys = {"category", "score", "stages"} if score_fraction >= Fraction(3, 4) else {"category", "ep_index", "score", "stages"}
    if set(attribution) != expected_root_keys:
        return False, None, []
    if not strict_equal(attribution.get("score"), score):
        return False, None, []
    if score_fraction < Fraction(3, 4):
        if type(attribution.get("ep_index")) is not int:
            return False, None, []
        if expected_episode_index is not None and attribution["ep_index"] != expected_episode_index:
            return False, None, []
    public_stages: list[dict[str, Any]] = []

    def stage_ok(stage: Any, name: str, required: dict[str, Any], optional: set[str]) -> bool:
        if not isinstance(stage, dict) or stage.get("stage") != name:
            return False
        expected_keys = {"stage", *required, *optional}
        if not set(stage).issubset(expected_keys) or not {"stage", *required}.issubset(stage):
            return False
        for key, expected in required.items():
            if type(stage[key]) is not type(expected) or stage[key] != expected:
                return False
        for key in optional:
            if key in stage and type(stage[key]) is not str:
                return False
        public_stages.append({
            "name": name,
            "required_values": required,
            "optional_fields_present": sorted(set(stage) & optional),
        })
        return True

    if score_fraction >= Fraction(3, 4):
        expected = "ok" if stages == [] else None
    elif len(stages) == 1 and stage_ok(stages[0], "oracle", {"can_invite": False}, {"reason"}):
        expected = "task_design_failure"
    elif (
        len(stages) == 2
        and stage_ok(stages[0], "oracle", {"can_invite": True}, {"reason"})
        and stage_ok(stages[1], "disclosure", {"disclosed": True}, {"reason", "evidence"})
    ):
        expected = "memory_failure"
    elif (
        len(stages) == 3
        and stage_ok(stages[0], "oracle", {"can_invite": True}, {"reason"})
        and stage_ok(stages[1], "disclosure", {"disclosed": False}, {"reason", "evidence"})
        and isinstance(stages[2], dict)
        and stages[2].get("category") in {"A", "B", "?"}
        and stage_ok(stages[2], "disclosure_subclass", {"category": stages[2]["category"]}, {"reason", "evidence"})
    ):
        expected = {
            "A": "agent_elicitation_failure",
            "B": "simulator_too_strict",
            "?": "unclassified",
        }[stages[2]["category"]]
    else:
        expected = None
    return expected is not None and attribution.get("category") == expected, expected, public_stages


def audit_outputs(
    reader: EvidenceReader,
    bank_index: dict[str, dict[tuple[str, str], dict[str, Any]]],
    tasks_by_user: dict[str, dict[str, Any]],
    episodes: dict[tuple[str, str, int], dict[str, Any]],
    stores: dict[tuple[str, str], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, dict[str, Any]]]:
    output_root = reader.source / "output"
    actual_output_dirs = {path.name for path in output_root.iterdir() if path.is_dir()}
    require_exact_names(actual_output_dirs, set(RUNS) | {"_task_design_oracle"}, "output directories")

    target_rows: list[dict[str, Any]] = []
    attribution_rows: list[dict[str, Any]] = []
    packet_rows: list[dict[str, Any]] = []
    packet_items: list[dict[str, Any]] = []
    per_user_computed: dict[str, dict[str, Any]] = {}
    observability: dict[str, Any] = {run: {field: Counter() for field in ("predicted", "slot_fill_reason", "judge_reason", "score")} for run in RUNS}

    for run_id, spec in RUNS.items():
        recon_dir = output_root / run_id / "recon_judge"
        attr_dir = output_root / run_id / "attribution"
        require_exact_names((path.name for path in recon_dir.glob("user_*.json")), (f"{user}.json" for user in USERS), f"reconstruction users {run_id}")
        require_exact_names((path.name for path in attr_dir.glob("user_*.json")), (f"{user}.json" for user in USERS), f"attribution users {run_id}")
        run_computed: dict[str, Any] = {}
        for user_id in USERS:
            recon_rel = f"output/{run_id}/recon_judge/{user_id}.json"
            attr_rel = f"output/{run_id}/attribution/{user_id}.json"
            recon = require_object(reader.read_source_json(recon_rel), recon_rel)
            attribution_file = require_object(reader.read_source_json(attr_rel), attr_rel)
            if set(recon) != {"user_id", "per_category", "overall", "details"}:
                raise AuditFailure(f"reconstruction root schema mismatch: {recon_rel}")
            if not isinstance(recon.get("per_category"), dict) or set(recon["per_category"]) != set(CATEGORIES):
                raise AuditFailure(f"reconstruction category summary schema mismatch: {recon_rel}")
            if any(type(recon["per_category"][category]) not in (int, Decimal) for category in CATEGORIES) or type(recon.get("overall")) not in (int, Decimal):
                raise AuditFailure(f"reconstruction summary type mismatch: {recon_rel}")
            if set(attribution_file) != {"user_id", "tasks_dir", "counts", "details"}:
                raise AuditFailure(f"attribution root schema mismatch: {attr_rel}")
            if attribution_file.get("tasks_dir") != "CustomTasksPooledFinal" or not isinstance(attribution_file.get("counts"), dict):
                raise AuditFailure(f"attribution root value mismatch: {attr_rel}")
            if any(type(key) is not str or type(value) is not int for key, value in attribution_file["counts"].items()):
                raise AuditFailure(f"attribution counts type mismatch: {attr_rel}")
            if recon.get("user_id") != user_id or attribution_file.get("user_id") != user_id:
                raise AuditFailure(f"output user_id mismatch: {run_id}/{user_id}")
            details = require_list(recon.get("details"), f"details {recon_rel}")
            attr_details = require_list(attribution_file.get("details"), f"details {attr_rel}")
            if len(details) != 31 or len(attr_details) != 31:
                raise AuditFailure(f"output detail cardinality mismatch: {run_id}/{user_id}")
            task_by_key = {
                (task["target_category"], task["target_dimension"]): (index, task)
                for index, task in enumerate(tasks_by_user[user_id]["tasks"], 1)
            }
            seen_keys: set[tuple[str, str]] = set()
            category_scores: dict[str, list[Fraction]] = defaultdict(list)
            computed_attr_counts: Counter[str] = Counter()
            for detail_index, (detail, attr_detail) in enumerate(zip(details, attr_details)):
                detail = require_object(detail, f"detail {recon_rel}#{detail_index}")
                attr_detail = require_object(attr_detail, f"detail {attr_rel}#{detail_index}")
                required_detail_keys = {
                    "category", "dimension", "explanation", "ground_truth", "score", "scoring_mode",
                } | ({"retrieved_memories"} if spec["mode"] == "retrieve" else set())
                optional_observability_keys = {"predicted", "slot_fill_reason", "judge_reason"}
                allowed_detail_keys = required_detail_keys | optional_observability_keys
                if not required_detail_keys.issubset(detail) or not set(detail).issubset(allowed_detail_keys):
                    raise AuditFailure(f"reconstruction detail schema mismatch: {recon_rel}#{detail_index}")
                if set(attr_detail) != set(detail) | {"attribution"}:
                    raise AuditFailure(f"attribution detail schema mismatch: {attr_rel}#{detail_index}")
                if any(type(detail[field]) is not str for field in (
                    "category", "dimension", "explanation", "ground_truth", "scoring_mode",
                )):
                    raise AuditFailure(f"reconstruction detail type mismatch: {recon_rel}#{detail_index}")
                category, dimension = detail.get("category"), detail.get("dimension")
                key = (category, dimension)
                if key not in bank_index[user_id] or key in seen_keys:
                    raise AuditFailure(f"unknown/duplicate reconstruction key: {run_id}/{user_id}/{key}")
                seen_keys.add(key)
                bank_entry = bank_index[user_id][key]
                task_index, task = task_by_key[key]
                score_state = classify_score(detail)
                if score_state["state"] != "VALID_QUARTER_STEP":
                    raise AuditFailure(f"invalid score: {run_id}/{user_id}/{dimension}: {score_state['state']}")
                score = detail["score"]
                category_scores[category].append(fraction_of(score))
                expected_mode = spec["mode"]
                join_flags = {
                    "attribution_copy_exact": strict_equal(
                        {k: v for k, v in attr_detail.items() if k != "attribution"}, detail
                    ),
                    "benchmark_explanation_exact": strict_equal(detail.get("explanation"), bank_entry["explanation"]),
                    "benchmark_target_exact": strict_equal(detail.get("ground_truth"), bank_entry["short"]),
                    "category_exact": category == task["target_category"],
                    "dimension_exact": dimension == task["target_dimension"],
                    "scoring_mode_exact": detail.get("scoring_mode") == expected_mode,
                    "task_target_exact": strict_equal(task.get("target_short"), bank_entry["short"]),
                    "user_id_exact": True,
                }
                if not all(join_flags.values()):
                    raise AuditFailure(f"target/copy join failed: {run_id}/{user_id}/{category}/{dimension}: {join_flags}")

                episode_rel = f"history/{spec['base']}/{user_id}/episode_{task_index}.json"
                episode = episodes[(spec["base"], user_id, task_index)]
                turns = episode["turns"]
                has_agent = any(type(turn.get("agent_response")) is str and bool(turn["agent_response"].strip()) for turn in turns)
                has_user = any(
                    isinstance(turn.get("user_simulator"), dict)
                    and type(turn["user_simulator"].get("text")) is str
                    and bool(turn["user_simulator"]["text"].strip())
                    for turn in turns
                )

                for field in ("explanation", "ground_truth", "predicted", "slot_fill_reason", "judge_reason"):
                    reader.mark_denied(detail.get(field))
                if isinstance(detail.get("retrieved_memories"), list):
                    for item in detail["retrieved_memories"]:
                        if isinstance(item, dict):
                            for field, value in item.items():
                                if field not in {"id", "category", "timestamp", "task_index", "turn", "score"}:
                                    reader.mark_denied(value)

                output_states: dict[str, Any] = {}
                for field in ("predicted", "slot_fill_reason", "judge_reason"):
                    state = classify_string_field(detail, field)
                    output_states[field] = state
                    observability[run_id][field][state["state"]] += 1
                    if state.get("exact_literal_unknown"):
                        observability[run_id][field]["EXACT_LITERAL_UNKNOWN"] += 1
                observability[run_id]["score"][score_state["state"]] += 1

                attribution = require_object(attr_detail.get("attribution"), f"attribution {attr_rel}#{detail_index}")
                if not strict_equal(attribution.get("score"), score):
                    raise AuditFailure(f"attribution score copy mismatch: {run_id}/{user_id}/{dimension}")
                reduction_ok, expected_label, public_stages = legal_attribution_reduction(score, attribution, task_index)
                if not reduction_ok:
                    raise AuditFailure(f"attribution reduction mismatch: {run_id}/{user_id}/{dimension}")
                computed_attr_counts[attribution["category"]] += 1
                for stage in attribution.get("stages", []):
                    for field in ("reason", "evidence"):
                        reader.mark_denied(stage.get(field))

                row_key = {
                    "category": category,
                    "dimension": dimension,
                    "run_id": run_id,
                    "scoring_mode": spec["mode"],
                    "system": spec["system"],
                    "user_id": user_id,
                }
                target_rows.append({
                    **row_key,
                    "attribution_locator": f"{attr_rel}#/details/{detail_index}",
                    "benchmark_explanation_sha256": typed_digest(bank_entry["explanation"]),
                    "benchmark_target_sha256": typed_digest(bank_entry["short"]),
                    "episode_locator": episode_rel,
                    "episode_sha256": reader.records[f"source:{episode_rel}"]["sha256"],
                    "join": join_flags,
                    "output_states": output_states,
                    "reconstruction_locator": f"{recon_rel}#/details/{detail_index}",
                    "score": numeric_record(score),
                    "stored_attribution_label": attribution["category"],
                    "task_index": task_index,
                    "task_locator": f"benchmark_data/CustomTasksPooledFinal/{user_id}.json#/tasks/{task_index-1}",
                    "task_text_sha256": typed_digest(task["task"]),
                })
                attr_observations = []
                for stage_index, stage in enumerate(attribution["stages"]):
                    attr_observations.append({
                        "index": stage_index,
                        "name": stage["stage"],
                        "reason_observation": classify_string_field(stage, "reason"),
                        "evidence_observation": classify_string_field(stage, "evidence"),
                    })
                attribution_rows.append({
                    **row_key,
                    "episode_exists": True,
                    "episode_locator": episode_rel,
                    "episode_sha256": reader.records[f"source:{episode_rel}"]["sha256"],
                    "exact_released_prompt_or_input_hash": False,
                    "historical_input_observability": "HISTORICAL_INPUT_UNVERIFIED",
                    "input_binding": "PARTIALLY_BOUND",
                    "reduction": "REDUCTION_CONSISTENT",
                    "score": numeric_record(score),
                    "stage_field_observations": attr_observations,
                    "stage_shape": public_stages,
                    "stored_attribution_label": attribution["category"],
                    "stored_task_design_verdict": next((stage.get("can_invite") for stage in attribution["stages"] if stage.get("stage") == "oracle"), None),
                    "stored_disclosure_verdict": next((stage.get("disclosed") for stage in attribution["stages"] if stage.get("stage") == "disclosure"), None),
                    "task_index": task_index,
                    "task_text_exact": strict_equal(episode.get("task"), task["task"]),
                    "transcript_has_nonempty_agent_and_user": has_agent and has_user,
                })

                if spec["mode"] == "retrieve":
                    packet = detail.get("retrieved_memories")
                    if not isinstance(packet, list) or len(packet) > 5:
                        raise AuditFailure(f"retrieve packet cardinality/type mismatch: {run_id}/{user_id}/{dimension}")
                    packet_row_index = len(packet_rows)
                    packet_rows.append({
                        **row_key,
                        "cardinality": len(packet),
                        "packet_locator": f"{recon_rel}#/details/{detail_index}/retrieved_memories",
                        "packet_schema": "PASS",
                        "packet_sha256": typed_digest(packet),
                    })
                    store = stores[(spec["base"], user_id)]
                    store_rel = f"memory/{spec['base']}/{user_id}/memories.json"
                    for item_index, item in enumerate(packet):
                        if not isinstance(item, dict):
                            raise AuditFailure(f"packet item is not an object: {run_id}/{user_id}/{dimension}/{item_index}")
                        schema_ok, matches = validate_packet_item(spec["system"], item, store)
                        if not schema_ok:
                            raise AuditFailure(f"packet adapter schema mismatch: {run_id}/{user_id}/{dimension}/{item_index}")
                        item_id = item.get("id") if type(item.get("id")) is str else None
                        packet_items.append({
                            **row_key,
                            "candidate_store_pointers": [f"{store_rel}#/memories/{index}" for index in matches],
                            "adapter_schema": "PASS",
                            "match_count": len(matches),
                            "membership_result": "NO_MATCH" if not matches else "EXACT_MEMBER" if len(matches) == 1 else "AMBIGUOUS_MEMBER",
                            "packet_index": item_index,
                            "packet_item_id": item_id,
                            "packet_item_sha256": typed_digest(item),
                            "packet_row_index": packet_row_index,
                            "store_locator": f"{store_rel}#/memories",
                        })

            if seen_keys != set(bank_index[user_id]):
                raise AuditFailure(f"reconstruction key population mismatch: {run_id}/{user_id}")
            if set(category_scores) != set(CATEGORIES):
                raise AuditFailure(f"reconstruction category population mismatch: {run_id}/{user_id}")
            category_means: dict[str, Fraction] = {}
            category_checks: dict[str, bool] = {}
            for category in CATEGORIES:
                if len(category_scores[category]) != CATEGORY_COUNTS[category]:
                    raise AuditFailure(f"category score count mismatch: {run_id}/{user_id}/{category}")
                mean = sum(category_scores[category], Fraction()) / len(category_scores[category])
                category_means[category] = mean
                category_checks[category] = numeric_close(mean, recon.get("per_category", {}).get(category))
            overall = sum(category_means.values(), Fraction()) / len(CATEGORIES)
            overall_ok = numeric_close(overall, recon.get("overall"))
            if not all(category_checks.values()) or not overall_ok:
                raise AuditFailure(f"stored reconstruction arithmetic mismatch: {run_id}/{user_id}")
            if not strict_equal(attribution_file.get("counts"), dict(computed_attr_counts)):
                raise AuditFailure(f"stored attribution counts mismatch: {run_id}/{user_id}")
            run_computed[user_id] = {
                "categories": category_means,
                "overall": overall,
                "stored_reconstruction": {
                    **recon["per_category"],
                    "overall": recon["overall"],
                },
                "stored_category_checks": category_checks,
                "stored_overall_check": overall_ok,
            }
        per_user_computed[run_id] = run_computed

    if len(target_rows) != 9 * 50 * 31 or len(attribution_rows) != 9 * 50 * 31:
        raise AuditFailure("exhaustive output population cardinality mismatch")
    expected_packets = 4 * 50 * 31
    if len(packet_rows) != expected_packets:
        raise AuditFailure("retrieve packet population cardinality mismatch")
    observability_receipt = {
        "schema": f"memprobe-output-observability/{SCHEMA_VERSION}",
        "runs": {
            run: {field: dict(sorted(counts.items())) for field, counts in fields.items()}
            for run, fields in observability.items()
        },
        "historical_payload_binding": {
            "judge_request_response": "UNVERIFIABLE_FROM_RELEASE",
            "slot_fill_payload": "UNVERIFIABLE_FROM_RELEASE",
            "slot_fill_response": "UNVERIFIABLE_FROM_RELEASE",
        },
    }
    return target_rows, attribution_rows, packet_rows, packet_items, observability_receipt, per_user_computed


def exact_sample_stats(values: list[Fraction]) -> tuple[Fraction, Fraction, float]:
    if len(values) < 2:
        raise AuditFailure("sample standard deviation requires at least two values")
    mean = sum(values, Fraction()) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, variance, math.sqrt(float(variance))


def build_paired_deltas(target_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    full = {
        (row["system"], row["user_id"], row["category"], row["dimension"]): row
        for row in target_rows
        if row["scoring_mode"] == "dump_all" and row["system"] != "nomem"
    }
    retrieve = {
        (row["system"], row["user_id"], row["category"], row["dimension"]): row
        for row in target_rows
        if row["scoring_mode"] == "retrieve"
    }
    if set(full) != set(retrieve) or len(full) != 4 * 50 * 31:
        raise AuditFailure("paired historical artifact population mismatch")
    rows: list[dict[str, Any]] = []
    for key in sorted(full):
        full_row, retrieve_row = full[key], retrieve[key]
        full_score = Fraction(full_row["score"]["numerator"], full_row["score"]["denominator"])
        retrieve_score = Fraction(retrieve_row["score"]["numerator"], retrieve_row["score"]["denominator"])
        delta = retrieve_score - full_score
        field_deltas = {}
        for field in ("predicted", "slot_fill_reason", "judge_reason"):
            left, right = full_row["output_states"][field], retrieve_row["output_states"][field]
            field_deltas[field] = {
                "state_changed": left.get("state") != right.get("state"),
                "typed_value_digest_changed": left.get("sha256") != right.get("sha256"),
            }
        rows.append({
            "category": key[2],
            "delta_scope": "paired historical artifact delta",
            "dimension": key[3],
            "field_deltas": field_deltas,
            "full_run_id": full_row["run_id"],
            "full_score": full_row["score"],
            "noncausal_boundary": "not_a_retrieval_effect_or_failure_estimate",
            "retrieve_minus_full_score": fraction_record(delta),
            "retrieve_run_id": retrieve_row["run_id"],
            "retrieve_score": retrieve_row["score"],
            "schema": f"memprobe-paired-historical-artifact-delta/{SCHEMA_VERSION}",
            "system": key[0],
            "user_id": key[1],
        })
    return rows


def report_reconstruction_matches(report: dict[str, Any], computed: dict[str, Any]) -> bool:
    per_user = report.get("per_user")
    if not isinstance(per_user, list) or len(per_user) != 50 or report.get("num_users") != 50:
        return False
    rows = {row.get("user_id"): row for row in per_user if isinstance(row, dict)}
    if set(rows) != set(USERS):
        return False
    for user_id in USERS:
        reconstruction = rows[user_id].get("reconstruction")
        if not isinstance(reconstruction, dict):
            return False
        expected = computed[user_id]["stored_reconstruction"]
        if not strict_equal(reconstruction, expected):
            return False
    return True


def audit_arithmetic(reader: EvidenceReader, computed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    runs_receipt: list[dict[str, Any]] = []
    all_report_gates = True
    for run_id in RUNS:
        fields = (*CATEGORIES, "overall")
        stats: dict[str, Any] = {}
        for field in fields:
            values = [
                computed[run_id][user_id]["overall"] if field == "overall" else computed[run_id][user_id]["categories"][field]
                for user_id in USERS
            ]
            mean, variance, std = exact_sample_stats(values)
            stats[field] = {
                "mean": fraction_record(mean),
                "sample_variance": fraction_record(variance),
                "sample_standard_deviation": std,
            }

        per_user_receipts = []
        for user_id in USERS:
            per_user_receipts.append({
                "categories": {
                    category: fraction_record(computed[run_id][user_id]["categories"][category])
                    for category in CATEGORIES
                },
                "overall": fraction_record(computed[run_id][user_id]["overall"]),
                "user_id": user_id,
            })

        report_files = sorted((reader.source / "output" / run_id).glob("*.json"))
        candidates: list[dict[str, Any]] = []
        partials: list[dict[str, Any]] = []
        for report_path in report_files:
            relative = safe_relative(report_path, reader.source)
            report = require_object(reader.read_source_json(relative), relative)
            row = {
                "locator": relative,
                "num_users": report.get("num_users") if type(report.get("num_users")) is int else None,
                "sha256": reader.records[f"source:{relative}"]["sha256"],
            }
            if not report_reconstruction_matches(report, computed[run_id]):
                row["status"] = "PARTIAL_OR_EMBEDDED_RECONSTRUCTION_MISMATCH"
                partials.append(row)
                continue
            aggregate = report.get("aggregate", {}).get("B_reconstruction", {})
            means = aggregate.get("mean") if isinstance(aggregate, dict) else None
            stds = aggregate.get("std") if isinstance(aggregate, dict) else None
            match_fields: dict[str, bool] = {}
            if isinstance(means, dict) and isinstance(stds, dict):
                for field in fields:
                    match_fields[field] = numeric_close(Fraction(stats[field]["mean"]["numerator"], stats[field]["mean"]["denominator"]), means.get(field)) and abs(stats[field]["sample_standard_deviation"] - float(stds.get(field, Decimal("NaN")))) <= 1e-12
            row["field_matches"] = match_fields
            row["status"] = "RELEASED_AGGREGATE_MATCH" if match_fields and all(match_fields.values()) else "RELEASED_AGGREGATE_MISMATCH"
            candidates.append(row)
        report_gate = bool(candidates) and all(row["status"] == "RELEASED_AGGREGATE_MATCH" for row in candidates)
        all_report_gates = all_report_gates and report_gate
        runs_receipt.append({
            "candidate_50_user_reports": candidates,
            "fixed_arithmetic": stats,
            "partial_or_nonmatching_reports": partials,
            "per_user_fixed_arithmetic": per_user_receipts,
            "recalculation_status": "INDEPENDENT_RECALCULATION_SUCCEEDED",
            "report_gate": report_gate,
            "run_id": run_id,
            "stored_user_arithmetic_checks_pass": all(
                all(computed[run_id][user]["stored_category_checks"].values()) and computed[run_id][user]["stored_overall_check"]
                for user in USERS
            ),
        })

    paper_table_2 = {
        "nomem_pooled_50": (0.000, 0.000),
        "amem_pooled_50": (0.611, 0.062),
        "amem_pooled_50_retrieve": (0.540, 0.062),
        "longctx_full_pooled_50": (0.624, 0.067),
        "longctx_full_pooled_50_retrieve": (0.503, 0.075),
        "mem0_pooled_50": (0.613, 0.060),
        "mem0_pooled_50_retrieve": (0.473, 0.079),
        "memt_memonly_pooled_50": (0.130, 0.251),
        "memt_memonly_pooled_50_retrieve": (0.465, 0.057),
    }
    display_checks = []
    by_run = {row["run_id"]: row for row in runs_receipt}
    for run_id, (shown_mean, shown_std) in paper_table_2.items():
        actual = by_run[run_id]["fixed_arithmetic"]["overall"]
        display_checks.append({
            "cell": "Table 2 / Reconstruction B / mean plus-minus sample std",
            "displayed_mean": shown_mean,
            "displayed_std": shown_std,
            "mean_matches_three_decimal_rounding": round(actual["mean"]["float"] + 0.0, 3) == shown_mean,
            "run_id": run_id,
            "std_matches_three_decimal_rounding": round(actual["sample_standard_deviation"] + 0.0, 3) == shown_std,
        })
    return {
        "schema": f"memprobe-fixed-arithmetic/{SCHEMA_VERSION}",
        "aggregate_report_gate": all_report_gates,
        "paper_display_cross_checks": display_checks,
        "runs": runs_receipt,
        "score_semantics": "historical_LLM_judge_outputs_only",
    }


def replay_inventory(reader: EvidenceReader) -> dict[str, Any]:
    inspected_source_files = [
        "README.md",
        "scorer.py",
        "failure_attribution.py",
        "runner.py",
        "agents/agent.py",
        "agents/agent_longctx.py",
        "agents/agent_mem0.py",
        "agents/agent_memt.py",
    ]
    source_hashes = []
    for relative in inspected_source_files:
        reader.read_source_bytes(relative)
        source_hashes.append({"locator": relative, "sha256": reader.records[f"source:{relative}"]["sha256"]})

    retrieve_history_dirs = [f"history/{run}" for run in RETRIEVE_RUNS]
    native_dirs = [f"memory/{run}/{user}/raw" for run in BASE_RUNS for user in USERS]
    rendered_prompt_fields = {"prompt", "rendered_prompt", "slot_fill_prompt", "judge_prompt"}
    observed_prompt_fields = set()
    for run in RUNS:
        for user in USERS:
            recon = reader.read_source_json(f"output/{run}/recon_judge/{user}.json")
            for detail in recon["details"]:
                observed_prompt_fields.update(set(detail) & rendered_prompt_fields)
    materials = [
        {
            "locator": "merge_50u_reports.py",
            "material": "Appendix C named merge script",
            "status": "NAMED_SOURCE_PATH_ABSENT" if not (reader.source / "merge_50u_reports.py").exists() else "PRESENT",
        },
        {
            "locator": "output/*/recon_judge/*.json#/details/*",
            "material": "rendered slot-fill or judge prompt fields",
            "observed_field_names": sorted(observed_prompt_fields),
            "status": "RELEASED_INPUT_ABSENT" if not observed_prompt_fields else "PRESENT",
        },
        {
            "locators": retrieve_history_dirs,
            "material": "retrieve-run histories addressed by current failure_attribution.py",
            "present_count": sum((reader.source / relative).is_dir() for relative in retrieve_history_dirs),
            "status": "RELEASED_INPUT_ABSENT" if not any((reader.source / relative).is_dir() for relative in retrieve_history_dirs) else "PARTIAL",
        },
        {
            "locator_pattern": "memory/<base-run>/<user>/raw",
            "material": "native retriever state",
            "present_count": sum((reader.source / relative).is_dir() for relative in native_dirs),
            "registered_count": len(native_dirs),
            "status": "RELEASED_INPUT_ABSENT" if not any((reader.source / relative).is_dir() for relative in native_dirs) else "PARTIAL",
        },
    ]
    provenance_fields = [
        "exact_model_snapshot",
        "endpoint",
        "runtime_receipt",
        "sampling_values_receipt",
        "request_ids",
        "raw_requests",
        "raw_responses",
        "rendered_prompt_hashes",
        "retry_receipt",
        "dependency_receipt",
        "usage_receipt",
    ]
    return {
        "schema": f"memprobe-replay-inventory/{SCHEMA_VERSION}",
        "historical_execution_replay": "NOT_ATTEMPTED",
        "historical_provenance": {field: "ABSENT" for field in provenance_fields},
        "materials": materials,
        "source_files_inspected": source_hashes,
        "source_replay_material_status": "BLOCKED",
    }


def run_mutation_controls() -> dict[str, Any]:
    adapter_fixtures = {
        "amem": {
            "packet": {"id": "a1", "content": "fixture_alpha", "keywords": [], "context": "fixture_context", "tags": [], "category": "fact", "score": Decimal("0.8")},
            "store": [{"id": "a1", "content": "fixture_alpha", "keywords": [], "context": "fixture_context", "tags": [], "category": "other", "timestamp": "t1"}],
        },
        "longctx_full": {
            "packet": {"content": "fixture_beta", "category": "assistant", "task_index": 2, "turn": 1, "score": Decimal("0.4")},
            "store": [{"content": "fixture_beta", "category": "assistant", "task_index": 2, "turn": 1}],
        },
        "mem0": {
            "packet": {"id": "m0", "content": "fixture_gamma", "category": "fact", "metadata": None, "timestamp": "t2"},
            "store": [{"id": "m0", "content": "fixture_gamma", "category": "fact", "metadata": None, "timestamp": "t2"}],
        },
        "memt": {
            "packet": {"id": "mt", "content": "fixture_delta", "category": "fact", "score": None, "timestamp": "t3"},
            "store": [{"id": "mt", "content": "ignored_projection", "category": "fact", "metadata": {"memory_content": "fixture_delta"}, "timestamp": "t3"}],
        },
    }
    join = {"run": "r", "user": "u", "category": "c", "dimension": "d", "target": "t", "explanation": "e", "mode": "retrieve"}
    attribution = {
        "category": "memory_failure",
        "ep_index": 1,
        "score": Decimal("0.5"),
        "stages": [
            {"stage": "oracle", "can_invite": True},
            {"stage": "disclosure", "disclosed": True},
        ],
    }
    context = {
        "adapters": adapter_fixtures,
        "arithmetic_stored": {
            "category_mean": Decimal("0.5"),
            "overall_mean": Decimal("0.5"),
            "across_user_mean": Decimal("0.5"),
            "sample_standard_deviation": math.sqrt(Decimal("0.625") / Decimal(4)),
        },
        "attribution": attribution,
        "attribution_expected_episode": 1,
        "attribution_score": Decimal("0.5"),
        "join_candidate": copy.deepcopy(join),
        "join_expected": copy.deepcopy(join),
        "join_rows": [copy.deepcopy(join)],
        "score_expected_state": "VALID_QUARTER_STEP",
        "score_fixture": {"score": Decimal("0.75")},
    }
    original_context_sha256 = typed_digest(context)

    def evaluate(candidate: dict[str, Any]) -> dict[str, bool]:
        gates: dict[str, bool] = {}
        for system, fixture in candidate["adapters"].items():
            schema_ok, matches = validate_packet_item(system, fixture["packet"], fixture["store"])
            gates[f"packet_schema:{system}"] = schema_ok
            gates[f"packet_membership:{system}"] = schema_ok and len(matches) >= 1
            gates[f"packet_unique_binding:{system}"] = schema_ok and len(matches) == 1
        gates["target_identity"] = strict_equal(candidate["join_candidate"], candidate["join_expected"])
        gates["target_uniqueness"] = len({typed_digest(row) for row in candidate["join_rows"]}) == len(candidate["join_rows"])
        gates["run_identity"] = candidate["join_candidate"]["run"] == candidate["join_expected"]["run"]
        gates["attribution_reduction"] = legal_attribution_reduction(
            candidate["attribution_score"],
            candidate["attribution"],
            candidate["attribution_expected_episode"],
        )[0]
        arithmetic_values = [Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1)]
        exact_mean, _, exact_std = exact_sample_stats(arithmetic_values)
        gates["category_mean"] = numeric_close(exact_mean, candidate["arithmetic_stored"]["category_mean"])
        gates["overall_mean"] = numeric_close(exact_mean, candidate["arithmetic_stored"]["overall_mean"])
        gates["across_user_mean"] = numeric_close(exact_mean, candidate["arithmetic_stored"]["across_user_mean"])
        gates["sample_standard_deviation"] = abs(exact_std - candidate["arithmetic_stored"]["sample_standard_deviation"]) <= 1e-12
        gates["score_classification"] = classify_score(candidate["score_fixture"])["state"] == candidate["score_expected_state"]
        gates["boolean_number_distinct"] = not strict_equal(True, 1)
        gates["integer_decimal_distinct"] = not strict_equal(1, Decimal("1"))
        return gates

    baseline = evaluate(context)
    if not all(baseline.values()):
        raise AuditFailure(f"synthetic control baseline is invalid: {baseline}")
    rows: list[dict[str, Any]] = []

    def record(
        name: str,
        expected_gate: str,
        mutator: Callable[[dict[str, Any]], None] | None = None,
        *,
        expected_value: bool,
        allowed_changed_gates: set[str],
    ) -> None:
        candidate = copy.deepcopy(context)
        if mutator is not None:
            mutator(candidate)
        after = evaluate(candidate)
        changed = {gate for gate in baseline if baseline[gate] != after[gate]}
        caught = after.get(expected_gate) is expected_value
        unrelated_stable = changed.issubset(allowed_changed_gates)
        rows.append({
            "actual_changed_gates": sorted(changed),
            "after_gate_snapshot_sha256": typed_digest(after),
            "allowed_changed_gates": sorted(allowed_changed_gates),
            "before_gate_snapshot_sha256": typed_digest(baseline),
            "caught_expected_gate": caught,
            "control": name,
            "expected_gate": expected_gate,
            "expected_gate_value_after": expected_value,
            "isolated_deep_copy": True,
            "mutated_context_sha256": typed_digest(candidate),
            "original_hash_unchanged": typed_digest(context) == original_context_sha256,
            "unrelated_gates_stable": unrelated_stable,
        })

    for system in adapter_fixtures:
        schema_gate = f"packet_schema:{system}"
        membership_gate = f"packet_membership:{system}"
        unique_gate = f"packet_unique_binding:{system}"
        record(f"{system}_baseline_exact_member", membership_gate, expected_value=True, allowed_changed_gates=set())

        def remove_candidate(value: dict[str, Any], system: str = system) -> None:
            value["adapters"][system]["store"] = []
        record(f"{system}_absent_packet_item", membership_gate, remove_candidate, expected_value=False, allowed_changed_gates={membership_gate, unique_gate})

        def duplicate_candidate(value: dict[str, Any], system: str = system) -> None:
            value["adapters"][system]["store"] += copy.deepcopy(value["adapters"][system]["store"])
        record(f"{system}_duplicate_exact_item", unique_gate, duplicate_candidate, expected_value=False, allowed_changed_gates={unique_gate})

        required_field = next(iter(adapter_fixtures[system]["packet"]))
        def omit_field(value: dict[str, Any], system: str = system, field: str = required_field) -> None:
            value["adapters"][system]["packet"].pop(field)
        record(f"{system}_omitted_required_packet_field", schema_gate, omit_field, expected_value=False, allowed_changed_gates={schema_gate, membership_gate, unique_gate})

        def add_field(value: dict[str, Any], system: str = system) -> None:
            value["adapters"][system]["packet"]["forbidden_extra"] = "fixture"
        record(f"{system}_forbidden_extra_packet_field", schema_gate, add_field, expected_value=False, allowed_changed_gates={schema_gate, membership_gate, unique_gate})

    def change_amem_content(value: dict[str, Any]) -> None:
        value["adapters"]["amem"]["packet"]["content"] = "fixture_changed"
    record("same_id_changed_immutable_content", "packet_membership:amem", change_amem_content, expected_value=False, allowed_changed_gates={"packet_membership:amem", "packet_unique_binding:amem"})

    def change_amem_id(value: dict[str, Any]) -> None:
        value["adapters"]["amem"]["packet"]["id"] = "a2"
    record("changed_id_same_content", "packet_membership:amem", change_amem_id, expected_value=False, allowed_changed_gates={"packet_membership:amem", "packet_unique_binding:amem"})

    def wrong_store(value: dict[str, Any]) -> None:
        value["adapters"]["amem"]["store"] = copy.deepcopy(value["adapters"]["longctx_full"]["store"])
    record("wrong_retrieve_to_store_mapping", "packet_membership:amem", wrong_store, expected_value=False, allowed_changed_gates={"packet_membership:amem", "packet_unique_binding:amem"})

    def change_retrieval_score(value: dict[str, Any]) -> None:
        value["adapters"]["longctx_full"]["packet"]["score"] = Decimal("0.9")
    record("allowed_retrieval_only_score_difference", "packet_membership:longctx_full", change_retrieval_score, expected_value=True, allowed_changed_gates=set())
    record("boolean_number_strict_inequality", "boolean_number_distinct", expected_value=True, allowed_changed_gates=set())
    record("integer_decimal_strict_inequality", "integer_decimal_distinct", expected_value=True, allowed_changed_gates=set())

    for field in join:
        def change_join(value: dict[str, Any], field: str = field) -> None:
            value["join_candidate"][field] += "_changed"
        allowed = {"target_identity"} | ({"run_identity"} if field == "run" else set())
        record(f"changed_join_{field}", "target_identity", change_join, expected_value=False, allowed_changed_gates=allowed)

    def duplicate_join(value: dict[str, Any]) -> None:
        value["join_rows"].append(copy.deepcopy(value["join_rows"][0]))
    record("duplicated_reconstruction_row", "target_uniqueness", duplicate_join, expected_value=False, allowed_changed_gates={"target_uniqueness"})

    def cross_run(value: dict[str, Any]) -> None:
        value["join_candidate"]["run"] = "other_run"
    record("cross_run_swapped_reconstruction_row", "run_identity", cross_run, expected_value=False, allowed_changed_gates={"target_identity", "run_identity"})

    legal = [
        (Decimal("0.75"), {"category": "ok", "score": Decimal("0.75"), "stages": []}, None),
        (Decimal("0.5"), {"category": "task_design_failure", "ep_index": 1, "score": Decimal("0.5"), "stages": [{"stage": "oracle", "can_invite": False, "reason": "fixture"}]}, 1),
        (Decimal("0.5"), copy.deepcopy(attribution), 1),
        (Decimal("0.5"), {"category": "agent_elicitation_failure", "ep_index": 1, "score": Decimal("0.5"), "stages": [{"stage": "oracle", "can_invite": True}, {"stage": "disclosure", "disclosed": False}, {"stage": "disclosure_subclass", "category": "A"}]}, 1),
        (Decimal("0.5"), {"category": "simulator_too_strict", "ep_index": 1, "score": Decimal("0.5"), "stages": [{"stage": "oracle", "can_invite": True}, {"stage": "disclosure", "disclosed": False}, {"stage": "disclosure_subclass", "category": "B"}]}, 1),
        (Decimal("0.5"), {"category": "unclassified", "ep_index": 1, "score": Decimal("0.5"), "stages": [{"stage": "oracle", "can_invite": True}, {"stage": "disclosure", "disclosed": False}, {"stage": "disclosure_subclass", "category": "?"}]}, 1),
    ]
    for index, (score, value, episode) in enumerate(legal):
        def set_legal(candidate: dict[str, Any], score: Decimal = score, value: dict[str, Any] = value, episode: int | None = episode) -> None:
            candidate["attribution_score"] = score
            candidate["attribution"] = copy.deepcopy(value)
            candidate["attribution_expected_episode"] = episode
        record(f"legal_attribution_branch_{index}", "attribution_reduction", set_legal, expected_value=True, allowed_changed_gates=set())

    def set_below(candidate: dict[str, Any]) -> None:
        score = Decimal("0.749999")
        candidate["attribution_score"] = score
        candidate["attribution"]["score"] = score
    record("immediately_below_threshold", "attribution_reduction", set_below, expected_value=True, allowed_changed_gates=set())

    def set_exact(candidate: dict[str, Any]) -> None:
        candidate["attribution_score"] = Decimal("0.75")
        candidate["attribution"] = {"category": "ok", "score": Decimal("0.75"), "stages": []}
        candidate["attribution_expected_episode"] = None
    record("exact_threshold", "attribution_reduction", set_exact, expected_value=True, allowed_changed_gates=set())

    invalid_attribution_mutators: list[tuple[str, Callable[[dict[str, Any]], None]]] = []
    def malformed_boolean(value: dict[str, Any]) -> None: value["attribution"]["stages"][0]["can_invite"] = 1
    invalid_attribution_mutators.append(("malformed_boolean", malformed_boolean))
    def wrong_order(value: dict[str, Any]) -> None: value["attribution"]["stages"].reverse()
    invalid_attribution_mutators.append(("wrong_stage_order", wrong_order))
    def unknown_stage(value: dict[str, Any]) -> None: value["attribution"]["stages"][1]["stage"] = "unknown"
    invalid_attribution_mutators.append(("unknown_stage", unknown_stage))
    def trailing_stage(value: dict[str, Any]) -> None: value["attribution"]["stages"].append({"stage": "disclosure", "disclosed": True})
    invalid_attribution_mutators.append(("extra_trailing_stage", trailing_stage))
    def wrong_episode(value: dict[str, Any]) -> None: value["attribution"]["ep_index"] = 2
    invalid_attribution_mutators.append(("wrong_episode_index", wrong_episode))
    def extra_payload(value: dict[str, Any]) -> None:
        value["attribution_score"] = Decimal("0.75")
        value["attribution"] = {"category": "ok", "score": Decimal("0.75"), "stages": [], "later_payload": {}}
        value["attribution_expected_episode"] = None
    invalid_attribution_mutators.append(("ok_extra_later_payload", extra_payload))
    for name, mutator in invalid_attribution_mutators:
        record(name, "attribution_reduction", mutator, expected_value=False, allowed_changed_gates={"attribution_reduction"})

    arithmetic_mutations = {
        "changed_category_mean": ("category_mean", Decimal("0.51")),
        "changed_overall_mean": ("overall_mean", Decimal("0.49")),
        "changed_across_user_mean": ("across_user_mean", Decimal("0.5001")),
        "changed_sample_standard_deviation": ("sample_standard_deviation", context["arithmetic_stored"]["sample_standard_deviation"] + 0.01),
    }
    for name, (gate, value) in arithmetic_mutations.items():
        def mutate_arithmetic(candidate: dict[str, Any], gate: str = gate, value: Any = value) -> None:
            candidate["arithmetic_stored"][gate] = value
        record(name, gate, mutate_arithmetic, expected_value=False, allowed_changed_gates={gate})

    score_controls = [({}, "MISSING"), ({"score": None}, "NULL"), ({"score": "0.5"}, "WRONG_TYPE"), ({"score": Decimal("0.3")}, "OUT_OF_RUBRIC")]
    for fixture, expected in score_controls:
        def set_score_case(candidate: dict[str, Any], fixture: dict[str, Any] = fixture, expected: str = expected) -> None:
            candidate["score_fixture"] = copy.deepcopy(fixture)
            candidate["score_expected_state"] = expected
        record(f"score_state_{expected.lower()}", "score_classification", set_score_case, expected_value=True, allowed_changed_gates=set())

    if typed_digest(context) != original_context_sha256:
        raise AuditFailure("mutation controls changed their original composite fixture")
    if not all(row["caught_expected_gate"] and row["unrelated_gates_stable"] and row["original_hash_unchanged"] for row in rows):
        failures = [row["control"] for row in rows if not (row["caught_expected_gate"] and row["unrelated_gates_stable"] and row["original_hash_unchanged"])]
        raise AuditFailure(f"one or more mutation controls failed: {failures}")
    return {
        "schema": f"memprobe-mutation-controls/{SCHEMA_VERSION}",
        "all_controls_pass": True,
        "composite_fixture_pre_sha256": original_context_sha256,
        "composite_fixture_post_sha256": typed_digest(context),
        "control_count": len(rows),
        "controls": rows,
        "unrelated_gate_evaluation": "full_composite_snapshot_per_isolated_mutation",
    }


def build_cases(
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
        (project(row, "KNOWN_PAPER_OR_RECONNAISSANCE_CASE") for row in target_rows if row["user_id"] == "user_022" and row["dimension"] == "pushback_tolerance"),
        key=lambda row: row["run_id"],
    )
    known_2 = sorted(
        (project(row, "KNOWN_PAPER_OR_RECONNAISSANCE_CASE") for row in target_rows if row["user_id"] == "user_005" and row["dimension"] == "geographic_knowledge" and row["system"] == "amem"),
        key=lambda row: row["run_id"],
    )
    full_lookup = {
        (row["system"], row["user_id"], row["category"], row["dimension"]): row
        for row in target_rows if row["scoring_mode"] == "dump_all" and row["system"] != "nomem"
    }
    retrieve_lookup = {
        (row["system"], row["user_id"], row["category"], row["dimension"]): row
        for row in target_rows if row["scoring_mode"] == "retrieve"
    }
    rule_candidates = [
        key for key in sorted(set(full_lookup) & set(retrieve_lookup))
        if full_lookup[key]["score"]["float"] >= 0.75 and retrieve_lookup[key]["score"]["float"] < 0.75
    ]
    rule_selected = []
    if rule_candidates:
        key = rule_candidates[0]
        rule_selected = [
            project(full_lookup[key], "RULE_SELECTED_ILLUSTRATION"),
            project(retrieve_lookup[key], "RULE_SELECTED_ILLUSTRATION"),
        ]
    return {
        "schema": f"memprobe-public-cases/{SCHEMA_VERSION}",
        "source_commit": SOURCE_COMMIT,
        "strata": [
            {"case": "user_022_pushback_tolerance", "rows": known_1},
            {"case": "user_005_geographic_knowledge_amem", "rows": known_2},
            {"case": "lexicographic_full_ge_075_retrieve_lt_075", "rows": rule_selected},
        ],
    }


def build_microfixture() -> dict[str, Any]:
    return {
        "schema": f"memprobe-ams-microfixture/{SCHEMA_VERSION}",
        "fixture_origin": "AMS-authored synthetic fixture",
        "not_a_memprobe_record": True,
        "not_for_benchmark_score_reproduction": True,
        "packet": {
            "id": "fixture-item-1",
            "content": "fixture_alpha",
            "keywords": ["fixture_key"],
            "context": "fixture_context",
            "tags": ["fixture_tag"],
            "category": "fixture_category",
            "score": 0.5,
        },
        "designated_store_projection": {
            "id": "fixture-item-1",
            "content": "fixture_alpha",
        },
        "expected_transition": "EXACT_MEMBER",
    }


def build_target_registry(tasks_by_user: dict[str, dict[str, Any]]) -> dict[str, Any]:
    targets = []
    for user_id in USERS:
        for task_index, task in enumerate(tasks_by_user[user_id]["tasks"], 1):
            targets.append({
                "category": task["target_category"],
                "dimension": task["target_dimension"],
                "task_index": task_index,
                "user_id": user_id,
            })
    return {
        "schema": f"memprobe-target-registry/{SCHEMA_VERSION}",
        "categories": CATEGORY_COUNTS,
        "run_registry": RUNS,
        "targets": targets,
        "users": list(USERS),
    }


def scan_public_safety(primary: Path, reader: EvidenceReader) -> dict[str, Any]:
    path_patterns = [
        re.compile("/" + "Users/"),
        re.compile("/" + "Volumes/"),
        re.compile("/" + "private/(?:tmp|var)/"),
    ]
    secret_patterns = [
        re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
        re.compile(r"(?i)(?:OPENAI|ANTHROPIC|OPENROUTER|GOOGLE)_API_KEY\s*[=:]\s*\S+"),
        re.compile(r"(?i)\b(?:" + "local" + r"host|[A-Za-z0-9-]+\.local)\b"),
    ]

    def string_leaves(value: Any, pointer: str = "#") -> Iterable[tuple[str, str]]:
        if type(value) is str:
            yield pointer, value
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from string_leaves(item, f"{pointer}/{index}")
        elif isinstance(value, dict):
            for key, item in value.items():
                escaped = key.replace("~", "~0").replace("/", "~1")
                yield from string_leaves(item, f"{pointer}/{escaped}")

    def pointer_tokens(pointer: str) -> list[str]:
        if pointer == "#":
            return []
        return [token.replace("~1", "/").replace("~0", "~") for token in pointer[2:].split("/")]

    def source_relative_locator(value: str) -> bool:
        path_part = value.split("#", 1)[0]
        return (
            bool(value)
            and not value.startswith("/")
            and ".." not in Path(path_part).parts
            and re.fullmatch(r"[A-Za-z0-9_.*#/<>{}-]+", value) is not None
        )

    def packet_identifier(value: str) -> bool:
        return re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}", value) is not None

    def absolute_local_path(value: str) -> bool:
        return (
            value.startswith("/")
            or re.match(r"^[A-Za-z]:[\\/]", value) is not None
            or value.startswith("\\\\")
        )

    exact_enum_fields: dict[str, set[str]] = {
        "adapter_schema": {"PASS"},
        "attribution_input_observability": {"PARTIAL"},
        "case": {
            "user_022_pushback_tolerance",
            "user_005_geographic_knowledge_amem",
            "lexicographic_full_ge_075_retrieve_lt_075",
        },
        "dependency_receipt": {"ABSENT"},
        "endpoint": {"ABSENT"},
        "exact_model_snapshot": {"ABSENT"},
        "expected_transition": {"EXACT_MEMBER"},
        "historical_execution_replay": {"NOT_ATTEMPTED"},
        "historical_input_observability": {"HISTORICAL_INPUT_UNVERIFIED"},
        "input_binding": {"PARTIALLY_BOUND"},
        "input_scope": {"official_source", "paper"},
        "json_type": {"integer", "decimal", "str", "list", "dict", "bool", "null"},
        "judge_request_response": {"UNVERIFIABLE_FROM_RELEASE"},
        "label": {"KNOWN_PAPER_OR_RECONNAISSANCE_CASE", "RULE_SELECTED_ILLUSTRATION"},
        "membership_result": {"EXACT_MEMBER", "NO_MATCH", "AMBIGUOUS_MEMBER"},
        "mode": {"dump_all", "retrieve"},
        "name": {"oracle", "disclosure", "disclosure_subclass"},
        "packet_schema": {"PASS"},
        "packet_unique_binding": {"PASS", "FAIL"},
        "raw_requests": {"ABSENT"},
        "raw_responses": {"ABSENT"},
        "recalculation_status": {"INDEPENDENT_RECALCULATION_SUCCEEDED"},
        "reduction": {"REDUCTION_CONSISTENT"},
        "rendered_prompt_hashes": {"ABSENT"},
        "request_ids": {"ABSENT"},
        "retry_receipt": {"ABSENT"},
        "runtime_receipt": {"ABSENT"},
        "sampling_values_receipt": {"ABSENT"},
        "scoring_mode": {"dump_all", "retrieve"},
        "slot_fill_payload": {"UNVERIFIABLE_FROM_RELEASE"},
        "slot_fill_response": {"UNVERIFIABLE_FROM_RELEASE"},
        "source_replay_material_status": {"COMPLETE", "PARTIAL", "BLOCKED"},
        "state": {"FIELD_ABSENT", "NULL", "EMPTY_STRING", "WHITESPACE_ONLY", "NONEMPTY_STRING", "WRONG_TYPE"},
        "status": {
            "NAMED_SOURCE_PATH_ABSENT",
            "RELEASED_INPUT_ABSENT",
            "RELEASED_AGGREGATE_ABSENT",
            "RELEASED_AGGREGATE_MATCH",
            "RELEASED_AGGREGATE_MISMATCH",
            "PARTIAL_OR_EMBEDDED_RECONSTRUCTION_MISMATCH",
        },
        "stored_attribution_label": {
            "ok", "task_design_failure", "memory_failure", "agent_elicitation_failure",
            "simulator_too_strict", "unclassified",
        },
        "stored_output_observability": {"COMPLETE_TYPED_INVENTORY"},
        "system": {spec["system"] for spec in RUNS.values()},
        "usage_receipt": {"ABSENT"},
        "worked_fixed_artifact_audit": {"SINGLE_RUN_PASS_PENDING_REPEATABILITY_AND_SOURCE_BOUND_REVALIDATION"},
    }
    locator_fields = {
        "attribution_locator", "candidate_store_pointers", "episode_locator", "locator", "locator_pattern",
        "locators", "packet_locator", "reconstruction_locator", "store_locator", "task_locator",
    }
    identifier_fields = {"control", "expected_gate"}
    identifier_array_fields = {"actual_changed_gates", "allowed_changed_gates"}

    def exact_denial_exempt(receipt_name: str, pointer: str, value: str) -> bool:
        tokens = pointer_tokens(pointer)
        field = tokens[-1] if tokens else ""
        parent = tokens[-2] if len(tokens) >= 2 else ""
        if field == "schema":
            return re.fullmatch(r"memprobe-[a-z0-9-]+/1", value) is not None
        if field == "source_commit":
            return value == SOURCE_COMMIT
        if field == "sha256" or field.endswith("_sha256"):
            return re.fullmatch(r"[0-9a-f]{64}", value) is not None
        if field in locator_fields or parent in locator_fields:
            return source_relative_locator(value)
        if field == "packet_item_id" or parent == "packet_item_ids":
            return packet_identifier(value)
        if field == "user_id" or parent == "users":
            return value in USERS
        if field in {"run_id", "full_run_id", "retrieve_run_id"}:
            return value in RUNS
        if field == "base":
            return value in BASE_RUNS
        if field == "category":
            return value in {*CATEGORIES, "A", "B", "?", "fixture_category"}
        if field == "dimension":
            return re.fullmatch(r"[a-z][a-z0-9_]*", value) is not None
        if field == "literal":
            return re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value) is not None
        if field == "id" and receipt_name == "microfixture.json":
            return value == "fixture-item-1"
        if field in identifier_fields or parent in identifier_array_fields:
            return re.fullmatch(r"[a-z][a-z0-9_:.-]*", value) is not None
        if (
            receipt_name == "attribution_rows.jsonl"
            and len(tokens) == 4
            and tokens[0] == "stage_shape"
            and tokens[1].isdigit()
            and tokens[2] == "optional_fields_present"
            and tokens[3].isdigit()
        ):
            return value in {"reason", "evidence"}
        allowed = exact_enum_fields.get(field)
        return allowed is not None and value in allowed

    scanned = 0
    for path in sorted(primary.iterdir()):
        if not path.is_file() or path.name == "public_safety.json":
            continue
        text = path.read_text(encoding="utf-8")
        scanned += 1
        for pattern in (*path_patterns, *secret_patterns):
            if pattern.search(text):
                raise AuditFailure(f"public safety pattern found in {path.name}: {pattern.pattern}")
        if path.suffix == ".jsonl":
            values = [load_json_bytes(line.encode("utf-8"), f"{path.name}:{index}") for index, line in enumerate(text.splitlines(), 1) if line]
        else:
            values = [load_json_bytes(text.encode("utf-8"), path.name)]
        for value_index, value in enumerate(values):
            for pointer, leaf in string_leaves(value):
                receipt_pointer = f"line:{value_index + 1}{pointer}" if path.suffix == ".jsonl" else pointer
                if absolute_local_path(leaf):
                    raise AuditFailure(
                        "absolute path value copied into public receipt: "
                        f"receipt={path.name} pointer={receipt_pointer} value_sha256={typed_digest(leaf)}"
                    )
                denial_exempt = exact_denial_exempt(path.name, pointer, leaf)
                if leaf in reader.denied_strings and not denial_exempt:
                    raise AuditFailure(
                        "upstream denied free-text value copied: "
                        f"receipt={path.name} pointer={receipt_pointer} "
                        f"value_sha256={typed_digest(leaf)} value_length={len(leaf)}"
                    )
                if denial_exempt:
                    continue
                tokens = re.findall(r"[^\W_]+(?:['’-][^\W_]+)*", leaf.casefold(), flags=re.UNICODE)
                for index in range(max(0, len(tokens) - 7)):
                    if " ".join(tokens[index:index + 8]) in reader.denied_eight_token_spans:
                        span_digest = sha256_bytes(" ".join(tokens[index:index + 8]).encode("utf-8"))
                        raise AuditFailure(
                            "upstream eight-token free-text span copied: "
                            f"receipt={path.name} pointer={receipt_pointer} span_sha256={span_digest}"
                        )
    return {
        "schema": f"memprobe-public-safety/{SCHEMA_VERSION}",
        "absolute_local_path_matches": 0,
        "api_secret_pattern_matches": 0,
        "files_scanned_excluding_self": scanned,
        "upstream_continuous_eight_token_span_matches": 0,
        "upstream_free_text_copied": False,
    }


def primary_manifest(primary: Path) -> dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(primary.iterdir()) if path.is_file()}


def parsed_object_manifest_digest(cache: dict[str, Any]) -> str:
    rows = [[key, typed_digest(cache[key])] for key in sorted(cache)]
    return typed_digest(rows)


def run_audit(source: Path, paper_pdf: Path, output: Path) -> None:
    if output == source or output.is_relative_to(source):
        raise AuditFailure("output must be outside the immutable official checkout")
    if output == paper_pdf:
        raise AuditFailure("output must not alias the paper PDF")
    if output.exists():
        raise AuditFailure(f"output path already exists: {output}")
    validate_source_identity(source)
    if sha256_file(paper_pdf) != PAPER_SHA256:
        raise AuditFailure("paper PDF hash mismatch")
    output.mkdir(parents=True)
    primary = output / "primary"
    primary.mkdir()
    guard = NetworkGuard()
    guard.install()
    try:
        reader = EvidenceReader(source, paper_pdf)
        reader.read_paper()
        bank, tasks_by_user, bank_index = load_bank_and_tasks(reader)
        del bank
        episodes, history_census = read_histories(reader, tasks_by_user)
        stores, store_census = read_store_census(reader)
        store_census["history_census"] = history_census
        target_rows, attribution_rows, packet_rows, packet_items, observability, computed = audit_outputs(
            reader, bank_index, tasks_by_user, episodes, stores
        )
        paired_deltas = build_paired_deltas(target_rows)
        arithmetic = audit_arithmetic(reader, computed)
        replay = replay_inventory(reader)
        parsed_objects_pre = parsed_object_manifest_digest(reader.cache)
        registered_inputs_pre = typed_digest(reader.manifest())
        controls = run_mutation_controls()
        parsed_objects_post = parsed_object_manifest_digest(reader.cache)
        registered_inputs_post = typed_digest(reader.manifest())
        if parsed_objects_pre != parsed_objects_post or registered_inputs_pre != registered_inputs_post:
            raise AuditFailure("mutation controls changed original parsed evidence or its registered manifest")
        controls.update({
            "official_parsed_objects_pre_sha256": parsed_objects_pre,
            "official_parsed_objects_post_sha256": parsed_objects_post,
            "official_parsed_objects_unchanged": True,
            "registered_input_manifest_pre_sha256": registered_inputs_pre,
            "registered_input_manifest_post_sha256": registered_inputs_post,
        })
        cases = build_cases(target_rows, packet_rows, packet_items)
        microfixture = build_microfixture()
        target_registry = build_target_registry(tasks_by_user)
        checkout_unchanged = reader.verify_unchanged()
        git_still_clean = run_git(source, "rev-parse", "HEAD") == SOURCE_COMMIT and not run_git(source, "status", "--porcelain=v1", "--untracked-files=all")
        controls["official_checkout_disk_bytes_unchanged"] = checkout_unchanged

        write_json(primary / "arithmetic.json", arithmetic)
        write_jsonl(primary / "attribution_rows.jsonl", attribution_rows)
        write_json(primary / "cases.json", cases)
        write_json(primary / "input_manifest.json", {
            "schema": f"memprobe-input-manifest/{SCHEMA_VERSION}",
            "paper_sha256": PAPER_SHA256,
            "source_commit": SOURCE_COMMIT,
            "inputs": reader.manifest(),
        })
        write_json(primary / "microfixture.json", microfixture)
        write_json(primary / "mutation_controls.json", controls)
        write_json(primary / "observability.json", observability)
        write_jsonl(primary / "packet_items.jsonl", packet_items)
        write_jsonl(primary / "packet_rows.jsonl", packet_rows)
        write_jsonl(primary / "paired_deltas.jsonl", paired_deltas)
        write_json(primary / "replay_inventory.json", replay)
        write_json(primary / "store_census.json", store_census)
        write_json(primary / "target_registry.json", target_registry)
        write_jsonl(primary / "target_joins.jsonl", target_rows)

        fixed_gates = {
            "aggregate_reports": arithmetic["aggregate_report_gate"],
            "attribution_input_linkage": all(row["input_binding"] == "PARTIALLY_BOUND" and row["task_text_exact"] for row in attribution_rows),
            "attribution_reduction": all(row["reduction"] == "REDUCTION_CONSISTENT" for row in attribution_rows),
            "checkout_immutable": checkout_unchanged and git_still_clean,
            "fixed_score_arithmetic": all(row["stored_user_arithmetic_checks_pass"] for row in arithmetic["runs"]),
            "mutation_controls": controls["all_controls_pass"],
            "network_guard": not guard.attempts,
            "packet_membership_complete": all(row["match_count"] >= 1 for row in packet_items),
            "packet_schema": (
                len(packet_rows) == 6200
                and all(row["packet_schema"] == "PASS" for row in packet_rows)
                and all(row["adapter_schema"] == "PASS" for row in packet_items)
            ),
            "public_population": len(target_rows) == 13950 and len(attribution_rows) == 13950,
            "target_identity": all(all(row["join"].values()) for row in target_rows),
        }
        packet_unique = all(row["match_count"] == 1 for row in packet_items)
        if not all(fixed_gates.values()):
            raise AuditFailure(f"one or more fixed-artifact gates failed: {fixed_gates}")
        decision = {
            "schema": f"memprobe-fixed-artifact-decision/{SCHEMA_VERSION}",
            "attribution_input_observability": "PARTIAL",
            "fixed_artifact_gates": fixed_gates,
            "historical_execution_replay": "NOT_ATTEMPTED",
            "packet_unique_binding": "PASS" if packet_unique else "FAIL",
            "primary_receipt_cardinalities": {
                "attribution_rows": len(attribution_rows),
                "packet_items": len(packet_items),
                "packet_rows": len(packet_rows),
                "paired_historical_artifact_deltas": len(paired_deltas),
                "target_join_rows": len(target_rows),
                "registered_targets": len(target_registry["targets"]),
            },
            "source_commit": SOURCE_COMMIT,
            "source_replay_material_status": replay["source_replay_material_status"],
            "stored_output_observability": "COMPLETE_TYPED_INVENTORY",
            "worked_fixed_artifact_audit": "SINGLE_RUN_PASS_PENDING_REPEATABILITY_AND_SOURCE_BOUND_REVALIDATION",
        }
        write_json(primary / "decision.json", decision)
        safety = scan_public_safety(primary, reader)
        write_json(primary / "public_safety.json", safety)
        # The final scan covers decision and the safety receipt too.
        scan_public_safety(primary, reader)
        require_exact_names((path.name for path in primary.iterdir() if path.is_file()), PRIMARY_FILES, "primary receipt files")
        manifest = primary_manifest(primary)
        write_json(output / "environment.json", {
            "schema": f"memprobe-audit-environment/{SCHEMA_VERSION}",
            "architecture": platform.machine(),
            "input_manifest_sha256": manifest["input_manifest.json"],
            "locale": locale.setlocale(locale.LC_ALL, None),
            "network_attempt_count": len(guard.attempts),
            "network_guard": "PASS" if not guard.attempts else "FAIL",
            "operating_system": platform.system(),
            "primary_manifest": manifest,
            "primary_manifest_digest": typed_digest(manifest),
            "python_hash_seed": os.environ.get("PYTHONHASHSEED", "UNSET"),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "runner_sha256": sha256_file(Path(__file__)),
            "timezone": os.environ.get("TZ", "UNSET"),
        })
    finally:
        guard.restore()


def comparison_evidence(run_a: Path, run_b: Path) -> dict[str, Any]:
    for run in (run_a, run_b):
        require_exact_names((path.name for path in (run / "primary").iterdir() if path.is_file()), PRIMARY_FILES, f"primary files {run.name}")
        require_exact_names((path.name for path in run.iterdir() if path.is_file()), {"environment.json"}, f"run envelope files {run.name}")
    manifest_a = primary_manifest(run_a / "primary")
    manifest_b = primary_manifest(run_b / "primary")
    equal = manifest_a == manifest_b
    differing = sorted(name for name in set(manifest_a) | set(manifest_b) if manifest_a.get(name) != manifest_b.get(name))
    env_a = load_json_bytes((run_a / "environment.json").read_bytes(), "run A environment")
    env_b = load_json_bytes((run_b / "environment.json").read_bytes(), "run B environment")
    expected_environment_keys = {
        "schema", "architecture", "input_manifest_sha256", "locale", "network_attempt_count",
        "network_guard", "operating_system", "primary_manifest", "primary_manifest_digest",
        "python_hash_seed", "python_implementation", "python_version", "runner_sha256", "timezone",
    }
    environment_shapes = (
        isinstance(env_a, dict)
        and isinstance(env_b, dict)
        and set(env_a) == set(env_b) == expected_environment_keys
        and env_a.get("schema") == env_b.get("schema") == f"memprobe-audit-environment/{SCHEMA_VERSION}"
        and all(type(env_a.get(key)) is str and type(env_b.get(key)) is str for key in (
            "architecture", "input_manifest_sha256", "locale", "network_guard", "operating_system",
            "primary_manifest_digest", "python_hash_seed", "python_implementation", "python_version",
            "runner_sha256", "timezone",
        ))
        and type(env_a.get("network_attempt_count")) is int
        and type(env_b.get("network_attempt_count")) is int
        and isinstance(env_a.get("primary_manifest"), dict)
        and isinstance(env_b.get("primary_manifest"), dict)
    )
    distinct_seeds = env_a.get("python_hash_seed") != env_b.get("python_hash_seed")
    explicit_frozen_envelopes = (
        env_a.get("python_hash_seed") != "UNSET"
        and env_b.get("python_hash_seed") != "UNSET"
        and env_a.get("locale") == env_b.get("locale") == "C"
        and env_a.get("timezone") == env_b.get("timezone") == "UTC"
        and all(env_a.get(key) == env_b.get(key) for key in (
            "architecture", "operating_system", "python_implementation", "python_version",
        ))
    )
    environment_bindings = (
        environment_shapes
        and explicit_frozen_envelopes
        and env_a.get("primary_manifest") == manifest_a
        and env_b.get("primary_manifest") == manifest_b
        and env_a.get("primary_manifest_digest") == typed_digest(manifest_a)
        and env_b.get("primary_manifest_digest") == typed_digest(manifest_b)
        and env_a.get("runner_sha256") == env_b.get("runner_sha256")
        and env_a.get("runner_sha256") == sha256_file(Path(__file__))
        and env_a.get("input_manifest_sha256") == manifest_a.get("input_manifest.json")
        and env_b.get("input_manifest_sha256") == manifest_b.get("input_manifest.json")
        and env_a.get("network_guard") == env_b.get("network_guard") == "PASS"
        and env_a.get("network_attempt_count") == env_b.get("network_attempt_count") == 0
    )
    input_a = load_json_bytes((run_a / "primary/input_manifest.json").read_bytes(), "run A input manifest")
    input_b = load_json_bytes((run_b / "primary/input_manifest.json").read_bytes(), "run B input manifest")
    source_bindings = (
        input_a.get("source_commit") == input_b.get("source_commit") == SOURCE_COMMIT
        and input_a.get("paper_sha256") == input_b.get("paper_sha256") == PAPER_SHA256
        and strict_equal(input_a, input_b)
    )
    if not equal or not distinct_seeds or not environment_bindings or not source_bindings:
        raise AuditFailure(
            "repeatability comparison failed: "
            f"differing={differing}, distinct_seeds={distinct_seeds}, "
            f"environment_bindings={environment_bindings}, source_bindings={source_bindings}"
        )
    return {
        "schema": f"memprobe-run-comparison/{SCHEMA_VERSION}",
        "combined_primary_manifest_digest": typed_digest(manifest_a),
        "differing_primary_files": differing,
        "environment_bindings": "PASS",
        "primary_file_count": len(manifest_a),
        "primary_receipts_byte_identical": equal,
        "run_a_primary_manifest": manifest_a,
        "run_a_environment_sha256": sha256_file(run_a / "environment.json"),
        "run_b_primary_manifest": manifest_b,
        "run_b_environment_sha256": sha256_file(run_b / "environment.json"),
        "runner_repeatability": "PASS",
        "seeds_distinct": distinct_seeds,
        "source_and_input_identity": "PASS",
    }


def compare_runs(run_a: Path, run_b: Path, output: Path) -> None:
    if output.exists():
        raise AuditFailure(f"comparison output already exists: {output}")
    evidence = comparison_evidence(run_a, run_b)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, evidence)


def install_checked(run_a: Path, run_b: Path, comparison: Path, artifact_root: Path) -> None:
    raw = artifact_root / "raw"
    if raw.exists():
        raise AuditFailure(f"checked raw directory already exists: {raw}")
    comparison_value = require_object(load_json_bytes(comparison.read_bytes(), "comparison"), "comparison")
    expected_comparison = comparison_evidence(run_a, run_b)
    if not strict_equal(comparison_value, expected_comparison):
        raise AuditFailure("comparison receipt does not bind the supplied run envelopes")
    raw.mkdir()
    for path in sorted((run_a / "primary").iterdir()):
        shutil.copyfile(path, raw / path.name)
    shutil.copyfile(run_a / "environment.json", raw / "environment_run_a.json")
    shutil.copyfile(run_b / "environment.json", raw / "environment_run_b.json")
    shutil.copyfile(comparison, raw / "comparison.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="execute one source-bound fixed-artifact audit")
    run_parser.add_argument("--source", required=True, type=Path)
    run_parser.add_argument("--paper-pdf", required=True, type=Path)
    run_parser.add_argument("--output", required=True, type=Path)
    compare_parser = sub.add_parser("compare", help="compare two fresh run envelopes")
    compare_parser.add_argument("--run-a", required=True, type=Path)
    compare_parser.add_argument("--run-b", required=True, type=Path)
    compare_parser.add_argument("--output", required=True, type=Path)
    install_parser = sub.add_parser("install", help="install one byte-checked primary set into this artifact")
    install_parser.add_argument("--run-a", required=True, type=Path)
    install_parser.add_argument("--run-b", required=True, type=Path)
    install_parser.add_argument("--comparison", required=True, type=Path)
    install_parser.add_argument("--artifact-root", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "run":
            run_audit(args.source.resolve(), args.paper_pdf.resolve(), args.output.resolve())
        elif args.command == "compare":
            compare_runs(args.run_a.resolve(), args.run_b.resolve(), args.output.resolve())
        else:
            install_checked(args.run_a.resolve(), args.run_b.resolve(), args.comparison.resolve(), args.artifact_root.resolve())
    except (AuditFailure, AssertionError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
