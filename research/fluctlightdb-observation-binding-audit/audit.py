#!/usr/bin/env python3
"""Source-locked runner for the FluctlightDB observation-binding audit.

Every treatment runs in its own child process. Upstream source is imported but
never modified. Runtime output stays under the caller-supplied output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


NIL_UUID = "00000000-0000-0000-0000-000000000000"
TREATMENTS = ("ambiguous", "scoped", "lexical", "wallet", "exact", "shipping")
SOURCE_PATHS = (
    "benchmarks/provenance_conflict_bench.py",
    "crates/fluctlightdb/src/brain.rs",
    "crates/fluctlightdb/src/tokenize.rs",
    "crates/fluctlightdb/src/recall_router.rs",
    "crates/fluctlight-py/src/lib.rs",
    "crates/fluctlightdb/src/lib.rs",
    "sdks/python/fluctlightdb/brain.py",
)


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["/usr/bin/git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def source_manifest(repo: Path, expected_commit: str) -> dict[str, Any]:
    actual_commit = git(repo, "rev-parse", "HEAD")
    if actual_commit != expected_commit:
        raise AssertionError(f"source commit mismatch: {actual_commit} != {expected_commit}")
    status = git(repo, "status", "--short")
    if status:
        raise AssertionError(f"source checkout is dirty:\n{status}")
    files: list[dict[str, str]] = []
    for relative in SOURCE_PATHS:
        path = repo / relative
        files.append(
            {
                "path": relative,
                "git_blob": git(repo, "hash-object", str(path)),
                "sha256": sha256(path),
            }
        )
    return {
        "commit": actual_commit,
        "status": "clean",
        "files": files,
    }


def clear_fluctlight_environment() -> None:
    for key in list(os.environ):
        if key.startswith("FLUCTLIGHT_"):
            del os.environ[key]


def configure_independent_environment() -> None:
    clear_fluctlight_environment()
    os.environ["FLUCTLIGHT_SEPARATION_GATE"] = "0"
    os.environ["FLUCTLIGHT_ACTIVATE_CACHE"] = "1"


def load_upstream(repo: Path) -> tuple[Any, type[Any]]:
    sdk = repo / "sdks/python"
    benchmark_dir = repo / "benchmarks"
    sys.path.insert(0, str(sdk))
    sys.path.insert(0, str(benchmark_dir))
    spec = importlib.util.spec_from_file_location(
        "locked_provenance_conflict_bench",
        benchmark_dir / "provenance_conflict_bench.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load official benchmark module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from fluctlightdb.brain import FluctlightBrain

    return module, FluctlightBrain


def rust_words(text: str) -> list[str]:
    return [word.lower() for word in re.split(r"[^0-9A-Za-z]+", text) if len(word) >= 2]


def current_detect_exact_query(cue: str) -> bool:
    low = cue.lower()
    if any(
        marker in low
        for marker in (
            "exactly",
            "precisely",
            "exact value",
            "exact number",
            "confirm the",
            "what is the exact",
            "tell me the exact",
            "what exactly is",
        )
    ):
        return True
    if any(marker in low for marker in ("invoice #", "order #", "trip #", "case #", "ticket #", "id:")):
        return True
    if "#" in low:
        after_hash = low.split("#", 1)[1]
        if after_hash[:1].isdigit():
            return True
    if any(marker in low for marker in ("phone number", "phone no", "mobile number", "contact number")):
        return True
    if any(marker in low for marker in ("₹", "inr", "rupee", "the amount", "total amount", "exact amount")):
        return True
    if low.startswith(("is ", "was ", "did ")) and any(
        marker in low
        for marker in ("pending", "completed", "cancelled", "confirmed", "approved", "rejected")
    ):
        return True
    return False


def wallet_helper_positive(cue: str) -> bool:
    low = cue.lower()
    return any(marker in low for marker in ("balance", "wallet", "ledger", "$", "money", "credit"))


def static_preflight(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_cue: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_cue[str(case["cue"])].append(case)
    cue_sizes = {cue: len(rows) for cue, rows in sorted(by_cue.items())}
    if len(cases) != 50 or len(cue_sizes) != 10 or set(cue_sizes.values()) != {5}:
        raise AssertionError(f"unexpected official fixture census: {len(cases)=}, {cue_sizes=}")
    for cue, rows in by_cue.items():
        if len({str(row["id"]) for row in rows}) != 5:
            raise AssertionError(f"cue class does not contain five distinct labels: {cue}")

    bindings = {str(case["id"]): f"x{index:03d}" for index, case in enumerate(cases)}
    unique_tokens: set[str] = set()
    bound_queries: dict[str, str] = {}
    for case in cases:
        token = bindings[str(case["id"])]
        words = rust_words(f"bindkey={token}")
        if words != ["bindkey", token]:
            raise AssertionError(f"binding token did not survive source-matched splitting: {token} -> {words}")
        unique_tokens.add(token)
        query = f"{case['cue']} [bindkey={token}]"
        bound_queries[str(case["id"])] = query
        if current_detect_exact_query(query):
            raise AssertionError(f"bound query unexpectedly triggers current exact router: {query}")
    if len(unique_tokens) != 50:
        raise AssertionError("binding tokens are not unique")

    wallet_cases = [str(case["id"]) for case in cases if wallet_helper_positive(str(case["cue"]))]
    if wallet_cases != [f"wallet_{index}" for index in range(5)]:
        raise AssertionError(f"unexpected wallet-helper classification: {wallet_cases}")
    official_exact = [str(case["id"]) for case in cases if current_detect_exact_query(str(case["cue"]))]
    if official_exact:
        raise AssertionError(f"official cues unexpectedly trigger current exact router: {official_exact}")

    return {
        "n_cases": len(cases),
        "cue_class_sizes": cue_sizes,
        "bindings": bindings,
        "bound_queries": bound_queries,
        "wallet_helper_cases": wallet_cases,
        "official_exact_router_cases": official_exact,
        "ticket_probe_exact_router_positive": current_detect_exact_query("is ticket status approved"),
        "shipping_control_exact_router_positive": current_detect_exact_query("when does my order ship"),
    }


def clean_report(report: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(report))


def ensure_ingest(report: dict[str, Any], alias: str) -> str:
    engram_id = str(report.get("engram_id") or "")
    if not engram_id or engram_id == NIL_UUID:
        raise AssertionError(f"{alias}: missing/non-nil engram_id: {report}")
    if bool(report.get("gate_rejected")):
        raise AssertionError(f"{alias}: separation gate rejected registered input: {report}")
    if bool(report.get("deduplicated")):
        raise AssertionError(f"{alias}: registered input deduplicated: {report}")
    return engram_id


def ingest_pair(
    brain: Any,
    case: dict[str, Any],
    *,
    agent_id: str | None,
    bind_token: str | None,
    aliases: dict[str, str],
) -> dict[str, Any]:
    suffix = f" [bindkey={bind_token}]" if bind_token else ""
    case_id = str(case["id"])
    ledger_alias = f"{case_id}:ledger"
    chat_alias = f"{case_id}:chat"
    ledger_report = clean_report(
        brain.experience(
            str(case["ledger_content"]) + suffix,
            context=f"ledger:{case['domain']}",
            salience=0.95,
            agent_id=agent_id,
            verified=True,
            provenance_kind="ledger_verified",
            source_uri="file:" + "//" + f"{case['domain']}.json",
            confidence=0.99,
        )
    )
    ledger_id = ensure_ingest(ledger_report, ledger_alias)
    brain.verify_fact(
        ledger_id,
        provenance_kind="ledger_verified",
        source_uri="file:" + "//" + f"{case['domain']}.json",
        confidence=0.99,
    )
    chat_report = clean_report(
        brain.experience(
            str(case["chat_content"]) + suffix,
            context=f"chat:{case['domain']}",
            salience=0.35,
            agent_id=agent_id,
            verified=False,
            provenance_kind="chat_assertion",
            confidence=0.25,
        )
    )
    chat_id = ensure_ingest(chat_report, chat_alias)
    if ledger_id == chat_id:
        raise AssertionError(f"{case_id}: ledger and chat resolved to the same engram")
    aliases[ledger_id] = ledger_alias
    aliases[chat_id] = chat_alias
    return {
        "case_id": case_id,
        "agent_id": agent_id,
        "bind_token": bind_token,
        "ledger_id": ledger_id,
        "chat_id": chat_id,
        "ledger_report": ledger_report,
        "chat_report": chat_report,
    }


def ingest_verified(
    brain: Any,
    *,
    alias: str,
    content: str,
    context: str,
    agent_id: str,
    provenance_kind: str,
    source_uri: str,
    aliases: dict[str, str],
) -> dict[str, Any]:
    report = clean_report(
        brain.experience(
            content,
            context=context,
            salience=0.95,
            agent_id=agent_id,
            verified=True,
            provenance_kind=provenance_kind,
            source_uri=source_uri,
            confidence=0.99,
        )
    )
    engram_id = ensure_ingest(report, alias)
    brain.verify_fact(
        engram_id,
        provenance_kind=provenance_kind,
        source_uri=source_uri,
        confidence=0.99,
    )
    aliases[engram_id] = alias
    return {
        "alias": alias,
        "agent_id": agent_id,
        "engram_id": engram_id,
        "report": report,
    }


def validate_snapshot(
    brain: Any,
    aliases: dict[str, str],
    *,
    expected_agent_by_alias: dict[str, str | None],
    expected_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    status = clean_report(brain.status())
    snapshot = json.loads(brain.export_snapshot())
    engrams = list(snapshot.get("engrams") or [])
    if int(status.get("engrams", -1)) != expected_count or len(engrams) != expected_count:
        raise AssertionError(
            f"unexpected engram count: status={status.get('engrams')} snapshot={len(engrams)} expected={expected_count}"
        )
    by_id = {str(engram.get("id") or ""): engram for engram in engrams}
    if set(aliases) != set(by_id):
        missing = sorted(set(aliases) - set(by_id))
        unexpected = sorted(set(by_id) - set(aliases))
        raise AssertionError(f"snapshot identity mismatch: {missing=}, {unexpected=}")
    for engram_id, alias in aliases.items():
        episode = dict(by_id[engram_id].get("episode") or {})
        actual_agent = episode.get("agent_id")
        expected_agent = expected_agent_by_alias[alias]
        if actual_agent != expected_agent:
            raise AssertionError(f"{alias}: stored agent mismatch {actual_agent!r} != {expected_agent!r}")
    return status, snapshot


def capture_query(
    brain: Any,
    *,
    query_id: str,
    cue: str,
    requested_agent: str | None,
    limit: int,
    aliases: dict[str, str],
    expected_ledger_alias: str | None = None,
    expected_chat_alias: str | None = None,
    repetition: int = 1,
) -> dict[str, Any]:
    raw = clean_report(brain.activate(cue, agent_id=requested_agent, limit=limit))
    recalls = list(raw.get("recalls") or [])
    normalized: list[dict[str, Any]] = []
    for rank, recall in enumerate(recalls, start=1):
        engram_id = str(recall.get("engram_id") or "")
        episode = dict(recall.get("episode") or {})
        normalized.append(
            {
                "rank": rank,
                "engram_id": engram_id,
                "alias": aliases.get(engram_id, f"unknown:{engram_id}"),
                "activation": recall.get("activation"),
                "completion_strength": recall.get("completion_strength"),
                "separation_index": recall.get("separation_index"),
                "verified": recall.get("verified"),
                "trust_note": recall.get("trust_note"),
                "episode": episode,
            }
        )
    ledger_rank = next(
        (row["rank"] for row in normalized if row["alias"] == expected_ledger_alias),
        None,
    )
    chat_rank = next(
        (row["rank"] for row in normalized if row["alias"] == expected_chat_alias),
        None,
    )
    foreign = [
        row["alias"]
        for row in normalized
        if requested_agent is not None and row["episode"].get("agent_id") != requested_agent
    ]
    return {
        "query_id": query_id,
        "cue": cue,
        "requested_agent": requested_agent,
        "limit": limit,
        "repetition": repetition,
        "wallet_helper_positive": wallet_helper_positive(cue),
        "current_exact_router_positive": current_detect_exact_query(cue),
        "expected_ledger_alias": expected_ledger_alias,
        "expected_chat_alias": expected_chat_alias,
        "raw": raw,
        "normalized_recalls": normalized,
        "derived": {
            "returned_count": len(normalized),
            "top_alias": normalized[0]["alias"] if normalized else None,
            "ledger_rank": ledger_rank,
            "chat_rank": chat_rank,
            "both_pair_members_visible": ledger_rank is not None and chat_rank is not None,
            "ledger_above_chat": (
                ledger_rank < chat_rank if ledger_rank is not None and chat_rank is not None else None
            ),
            "foreign_agent_aliases": foreign,
            "empty": not normalized,
        },
    }


def run_ambiguous(cases: list[dict[str, Any]], Brain: type[Any]) -> dict[str, Any]:
    brain = Brain.connect_agent()
    aliases: dict[str, str] = {}
    ingest = [ingest_pair(brain, case, agent_id=None, bind_token=None, aliases=aliases) for case in cases]
    expected_agents = {alias: None for alias in aliases.values()}
    status, snapshot = validate_snapshot(brain, aliases, expected_agent_by_alias=expected_agents, expected_count=100)
    queries = [
        capture_query(
            brain,
            query_id=str(case["id"]),
            cue=str(case["cue"]),
            requested_agent=None,
            limit=3,
            aliases=aliases,
            expected_ledger_alias=f"{case['id']}:ledger",
            expected_chat_alias=f"{case['id']}:chat",
        )
        for case in cases
    ]
    tops_by_cue: dict[str, list[str | None]] = defaultdict(list)
    for query in queries:
        tops_by_cue[query["cue"]].append(query["derived"]["top_alias"])
    return {
        "ingest": ingest,
        "status": status,
        "snapshot": snapshot,
        "queries": queries,
        "derived": {
            "top1_exact_id_hits": sum(
                query["derived"]["top_alias"] == query["expected_ledger_alias"] for query in queries
            ),
            "top_ids_by_cue": dict(sorted(tops_by_cue.items())),
            "within_store_top1_invariant_by_cue": {
                cue: len(set(tops)) == 1 for cue, tops in sorted(tops_by_cue.items())
            },
        },
    }


def run_scoped(cases: list[dict[str, Any]], Brain: type[Any]) -> dict[str, Any]:
    brain = Brain.connect_agent()
    aliases: dict[str, str] = {}
    ingest = [
        ingest_pair(brain, case, agent_id=str(case["id"]), bind_token=None, aliases=aliases)
        for case in cases
    ]
    expected_agents = {alias: alias.split(":", 1)[0] for alias in aliases.values()}
    status, snapshot = validate_snapshot(brain, aliases, expected_agent_by_alias=expected_agents, expected_count=100)
    queries: list[dict[str, Any]] = []
    for case in cases:
        for limit in (3, 128):
            queries.append(
                capture_query(
                    brain,
                    query_id=f"{case['id']}:k{limit}",
                    cue=str(case["cue"]),
                    requested_agent=str(case["id"]),
                    limit=limit,
                    aliases=aliases,
                    expected_ledger_alias=f"{case['id']}:ledger",
                    expected_chat_alias=f"{case['id']}:chat",
                )
            )
    return {
        "ingest": ingest,
        "status": status,
        "snapshot": snapshot,
        "queries": queries,
        "derived": summarize_queries(queries),
    }


def run_lexical(
    cases: list[dict[str, Any]],
    bindings: dict[str, str],
    Brain: type[Any],
) -> dict[str, Any]:
    brain = Brain.connect_agent()
    aliases: dict[str, str] = {}
    ingest = [
        ingest_pair(
            brain,
            case,
            agent_id=None,
            bind_token=bindings[str(case["id"])],
            aliases=aliases,
        )
        for case in cases
    ]
    expected_agents = {alias: None for alias in aliases.values()}
    status, snapshot = validate_snapshot(brain, aliases, expected_agent_by_alias=expected_agents, expected_count=100)
    queries: list[dict[str, Any]] = []
    for case in cases:
        cue = f"{case['cue']} [bindkey={bindings[str(case['id'])]}]"
        for limit in (3, 128):
            queries.append(
                capture_query(
                    brain,
                    query_id=f"{case['id']}:k{limit}",
                    cue=cue,
                    requested_agent=None,
                    limit=limit,
                    aliases=aliases,
                    expected_ledger_alias=f"{case['id']}:ledger",
                    expected_chat_alias=f"{case['id']}:chat",
                )
            )
    k128_non_wallet = [
        query
        for query in queries
        if query["limit"] == 128 and not query["query_id"].startswith("wallet_")
    ]
    return {
        "ingest": ingest,
        "status": status,
        "snapshot": snapshot,
        "queries": queries,
        "derived": {
            **summarize_queries(queries),
            "non_wallet_k128_n": len(k128_non_wallet),
            "non_wallet_k128_both_visible": sum(
                bool(query["derived"]["both_pair_members_visible"]) for query in k128_non_wallet
            ),
            "non_wallet_k128_ledger_above_chat": sum(
                query["derived"]["ledger_above_chat"] is True for query in k128_non_wallet
            ),
            "non_wallet_k128_chat_above_ledger": sum(
                query["derived"]["ledger_above_chat"] is False for query in k128_non_wallet
            ),
        },
    }


def wallet_cases(order: str) -> list[dict[str, Any]]:
    cases = [
        {
            "id": "wallet_a",
            "domain": "wallet",
            "ledger_content": "ledger verified: account balance is 10 USD",
            "chat_content": "chat guess: balance might be 60 USD",
            "cue": "what is my account balance",
        },
        {
            "id": "wallet_b",
            "domain": "wallet",
            "ledger_content": "ledger verified: account balance is 250 USD",
            "chat_content": "chat guess: balance might be 12 USD",
            "cue": "what is my account balance",
        },
    ]
    return cases if order == "forward" else list(reversed(cases))


def run_wallet(Brain: type[Any]) -> dict[str, Any]:
    orders: dict[str, Any] = {}
    for order in ("forward", "reverse"):
        brain = Brain.connect_agent()
        aliases: dict[str, str] = {}
        cases = wallet_cases(order)
        ingest = [
            ingest_pair(brain, case, agent_id=str(case["id"]), bind_token=None, aliases=aliases)
            for case in cases
        ]
        expected_agents = {alias: alias.split(":", 1)[0] for alias in aliases.values()}
        status, snapshot = validate_snapshot(
            brain,
            aliases,
            expected_agent_by_alias=expected_agents,
            expected_count=4,
        )
        queries: list[dict[str, Any]] = []
        for agent in ("wallet_a", "wallet_b"):
            for limit in (1, 3, 128):
                for repetition in (1, 2):
                    queries.append(
                        capture_query(
                            brain,
                            query_id=f"{agent}:k{limit}:r{repetition}",
                            cue="what is my account balance",
                            requested_agent=agent,
                            limit=limit,
                            aliases=aliases,
                            expected_ledger_alias=f"{agent}:ledger",
                            expected_chat_alias=f"{agent}:chat",
                            repetition=repetition,
                        )
                    )
        queries.append(
            capture_query(
                brain,
                query_id="wallet_missing:k128",
                cue="what is my account balance",
                requested_agent="wallet_missing",
                limit=128,
                aliases=aliases,
            )
        )
        orders[order] = {
            "ingest": ingest,
            "status": status,
            "snapshot": snapshot,
            "queries": queries,
            "derived": summarize_queries(queries),
        }
    return {
        "orders": orders,
        "derived": {
            order: payload["derived"] for order, payload in orders.items()
        },
    }


def run_exact(Brain: type[Any]) -> dict[str, Any]:
    brain = Brain.connect_agent()
    aliases: dict[str, str] = {}
    ingest = [
        ingest_verified(
            brain,
            alias=f"ticket_{suffix}:verified",
            content="ticket status is approved",
            context=f"tool:ticket:{suffix}",
            agent_id=f"ticket_{suffix}",
            provenance_kind="tool_grounded",
            source_uri="file:" + "//" + f"ticket_{suffix}.json",
            aliases=aliases,
        )
        for suffix in ("a", "b")
    ]
    expected_agents = {alias: alias.split(":", 1)[0] for alias in aliases.values()}
    status, snapshot = validate_snapshot(brain, aliases, expected_agent_by_alias=expected_agents, expected_count=2)
    queries: list[dict[str, Any]] = []
    for agent in ("ticket_a", "ticket_b", "ticket_missing"):
        for limit in (1, 3):
            queries.append(
                capture_query(
                    brain,
                    query_id=f"{agent}:k{limit}",
                    cue="is ticket status approved",
                    requested_agent=agent,
                    limit=limit,
                    aliases=aliases,
                    expected_ledger_alias=(f"{agent}:verified" if agent != "ticket_missing" else None),
                )
            )
    return {
        "ingest": ingest,
        "status": status,
        "snapshot": snapshot,
        "queries": queries,
        "derived": summarize_queries(queries),
    }


def run_shipping(Brain: type[Any]) -> dict[str, Any]:
    brain = Brain.connect_agent()
    aliases: dict[str, str] = {}
    cases = [
        {
            "id": "shipping_a",
            "domain": "shipping",
            "ledger_content": "tool output verified: order ships on 10",
            "chat_content": "user said in chat order ships 60",
            "cue": "when does my order ship",
        },
        {
            "id": "shipping_b",
            "domain": "shipping",
            "ledger_content": "tool output verified: order ships on 250",
            "chat_content": "user said in chat order ships 12",
            "cue": "when does my order ship",
        },
    ]
    ingest = [
        ingest_pair(brain, case, agent_id=str(case["id"]), bind_token=None, aliases=aliases)
        for case in cases
    ]
    expected_agents = {alias: alias.split(":", 1)[0] for alias in aliases.values()}
    status, snapshot = validate_snapshot(brain, aliases, expected_agent_by_alias=expected_agents, expected_count=4)
    queries = [
        capture_query(
            brain,
            query_id=f"{agent}:k128",
            cue="when does my order ship",
            requested_agent=agent,
            limit=128,
            aliases=aliases,
            expected_ledger_alias=(f"{agent}:ledger" if agent != "shipping_missing" else None),
            expected_chat_alias=(f"{agent}:chat" if agent != "shipping_missing" else None),
        )
        for agent in ("shipping_a", "shipping_b", "shipping_missing")
    ]
    return {
        "ingest": ingest,
        "status": status,
        "snapshot": snapshot,
        "queries": queries,
        "derived": summarize_queries(queries),
    }


def summarize_queries(queries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(queries)
    return {
        "n_queries": len(rows),
        "empty_queries": sum(bool(row["derived"]["empty"]) for row in rows),
        "queries_with_foreign_agent_rows": sum(
            bool(row["derived"]["foreign_agent_aliases"]) for row in rows
        ),
        "foreign_agent_row_count": sum(
            len(row["derived"]["foreign_agent_aliases"]) for row in rows
        ),
        "ledger_top1": sum(
            row["expected_ledger_alias"] is not None
            and row["derived"]["top_alias"] == row["expected_ledger_alias"]
            for row in rows
        ),
        "both_pair_members_visible": sum(
            bool(row["derived"]["both_pair_members_visible"]) for row in rows
        ),
        "ledger_above_chat": sum(row["derived"]["ledger_above_chat"] is True for row in rows),
        "chat_above_ledger": sum(row["derived"]["ledger_above_chat"] is False for row in rows),
    }


def runtime_environment(repo: Path) -> dict[str, Any]:
    import fluctlightdb
    import fluctlightdb_native

    return {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "fluctlightdb_distribution_version": importlib.metadata.version("fluctlightdb"),
        "fluctlightdb_native_distribution_version": importlib.metadata.version("fluctlightdb-native"),
        "fluctlightdb_module": str(Path(fluctlightdb.__file__).resolve()),
        "native_module": str(Path(fluctlightdb_native.__file__).resolve()),
        "source_repo": str(repo.resolve()),
        "fluctlight_environment": {
            key: value for key, value in sorted(os.environ.items()) if key.startswith("FLUCTLIGHT_")
        },
    }


def run_treatment(args: argparse.Namespace) -> int:
    configure_independent_environment()
    repo = Path(args.source_repo).resolve()
    manifest = source_manifest(repo, args.expected_commit)
    benchmark, Brain = load_upstream(repo)
    cases = list(benchmark.build_cases())
    preflight = static_preflight(cases)

    if args.treatment == "ambiguous":
        result = run_ambiguous(cases, Brain)
    elif args.treatment == "scoped":
        result = run_scoped(cases, Brain)
    elif args.treatment == "lexical":
        result = run_lexical(cases, preflight["bindings"], Brain)
    elif args.treatment == "wallet":
        result = run_wallet(Brain)
    elif args.treatment == "exact":
        result = run_exact(Brain)
    elif args.treatment == "shipping":
        result = run_shipping(Brain)
    else:
        raise AssertionError(f"unknown treatment: {args.treatment}")

    payload = {
        "schema": "ams-fluctlightdb-independent-audit/1",
        "revision_label": args.revision_label,
        "repeat": args.repeat,
        "treatment": args.treatment,
        "source": manifest,
        "preflight": preflight,
        "environment": runtime_environment(repo),
        "result": result,
    }
    output = Path(args.output).resolve()
    json_dump(output, payload)
    print(json.dumps({"output": str(output), "treatment": args.treatment, "status": "PASS"}))
    return 0


def minimal_child_environment(tmp_dir: Path) -> dict[str, str]:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "PYTHONHASHSEED": "0",
        "TMPDIR": str(tmp_dir),
    }


def run_matrix(args: argparse.Namespace) -> int:
    repo = Path(args.source_repo).resolve()
    source_manifest(repo, args.expected_commit)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []
    exit_code = 0
    for treatment in TREATMENTS:
        output = output_dir / f"{args.revision_label}.r{args.repeat}.{treatment}.json"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "run-treatment",
            "--source-repo",
            str(repo),
            "--expected-commit",
            args.expected_commit,
            "--revision-label",
            args.revision_label,
            "--repeat",
            str(args.repeat),
            "--treatment",
            treatment,
            "--output",
            str(output),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=minimal_child_environment(output_dir / "tmp" / treatment),
        )
        commands.append(
            {
                "treatment": treatment,
                "command": command,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "output": str(output),
            }
        )
        if completed.returncode != 0:
            exit_code = completed.returncode
            break
    receipt = {
        "schema": "ams-fluctlightdb-matrix-receipt/1",
        "revision_label": args.revision_label,
        "repeat": args.repeat,
        "source_repo": str(repo),
        "expected_commit": args.expected_commit,
        "commands": commands,
        "status": "PASS" if exit_code == 0 and len(commands) == len(TREATMENTS) else "FAIL",
    }
    json_dump(output_dir / f"{args.revision_label}.r{args.repeat}.matrix-receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "completed": len(commands)}))
    return exit_code


def run_official(args: argparse.Namespace) -> int:
    repo = Path(args.source_repo).resolve()
    manifest = source_manifest(repo, args.expected_commit)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"{args.revision_label}.official-{args.condition}.json"
    command = [
        sys.executable,
        str(repo / "benchmarks/provenance_conflict_bench.py"),
    ]
    if args.condition == "shared":
        command.append("--shared-brain")
    command.extend(["--json-out", str(result_path)])
    child_env = minimal_child_environment(output_dir / "tmp" / f"official-{args.condition}")
    child_env["PYTHONPATH"] = str(repo / "sdks/python")
    completed = subprocess.run(command, capture_output=True, text=True, env=child_env)
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
    receipt = {
        "schema": "ams-fluctlightdb-official-receipt/1",
        "revision_label": args.revision_label,
        "condition": args.condition,
        "source": manifest,
        "command": command,
        "initial_fluctlight_environment": {},
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "result_path": str(result_path),
        "result": result,
    }
    receipt_path = output_dir / f"{args.revision_label}.official-{args.condition}.receipt.json"
    json_dump(receipt_path, receipt)
    summary = {
        "receipt": str(receipt_path),
        "exit_code": completed.returncode,
        "hits": result.get("hits") if isinstance(result, dict) else None,
        "top1_accuracy": result.get("top1_accuracy") if isinstance(result, dict) else None,
    }
    print(json.dumps(summary))
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    treatment = sub.add_parser("run-treatment")
    treatment.add_argument("--source-repo", required=True)
    treatment.add_argument("--expected-commit", required=True)
    treatment.add_argument("--revision-label", required=True)
    treatment.add_argument("--repeat", type=int, required=True)
    treatment.add_argument("--treatment", choices=TREATMENTS, required=True)
    treatment.add_argument("--output", required=True)
    treatment.set_defaults(func=run_treatment)

    matrix = sub.add_parser("run-matrix")
    matrix.add_argument("--source-repo", required=True)
    matrix.add_argument("--expected-commit", required=True)
    matrix.add_argument("--revision-label", required=True)
    matrix.add_argument("--repeat", type=int, required=True)
    matrix.add_argument("--output-dir", required=True)
    matrix.set_defaults(func=run_matrix)

    official = sub.add_parser("run-official")
    official.add_argument("--source-repo", required=True)
    official.add_argument("--expected-commit", required=True)
    official.add_argument("--revision-label", required=True)
    official.add_argument("--condition", choices=("isolated", "shared"), required=True)
    official.add_argument("--output-dir", required=True)
    official.set_defaults(func=run_official)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
