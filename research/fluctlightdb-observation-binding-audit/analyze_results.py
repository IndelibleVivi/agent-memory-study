#!/usr/bin/env python3
"""Reduce raw FluctlightDB audit receipts to public-safe logical observables."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REVISIONS = ("paper-time", "repair-descendant")
REPEATS = (1, 2)
TREATMENTS = ("ambiguous", "scoped", "lexical", "wallet", "exact", "shipping")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def public_safe_provenance(value: Any) -> Any:
    """Preserve synthetic provenance fields without publishing a local-file URI."""
    if not isinstance(value, dict):
        return value
    normalized = dict(value)
    source_uri = normalized.get("source_uri")
    local_prefix = "file:" + "//"
    if isinstance(source_uri, str) and source_uri.startswith(local_prefix):
        normalized["source_uri"] = "synthetic-source:" + source_uri.removeprefix(local_prefix)
    return normalized


def official_summary(data: dict[str, Any]) -> dict[str, Any]:
    cases = list(data["cases"])
    ledger_alias = {
        str(row["ledger_engram_id"]): f"{row['id']}:ledger"
        for row in cases
    }
    tops_by_domain: dict[str, list[str]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    for row in cases:
        domain = str(row["id"]).rsplit("_", 1)[0]
        top_id = str(row.get("top_engram_id") or "")
        top_alias = ledger_alias.get(top_id)
        if top_alias is None:
            preview = str(row.get("top_content_preview") or "")
            top_alias = "unmapped-chat-or-other:" + preview
        tops_by_domain[domain].append(top_alias)
        rows.append(
            {
                "case_id": row["id"],
                "hit": bool(row["hit"]),
                "top_alias": top_alias,
                "expected_alias": f"{row['id']}:ledger",
                "top_content_preview": row.get("top_content_preview"),
            }
        )
    invariant = {domain: len(set(tops)) == 1 for domain, tops in sorted(tops_by_domain.items())}
    return {
        "condition": data["condition"],
        "n_cases": data["n_cases"],
        "hits": data["hits"],
        "top1_accuracy": data["top1_accuracy"],
        "rows": rows,
        "top_aliases_by_domain": dict(sorted(tops_by_domain.items())),
        "within_store_top1_invariant_by_domain": invariant,
        "all_domains_invariant": all(invariant.values()),
    }


def iter_queries(result: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    if "queries" in result:
        for query in result["queries"]:
            yield "single", query
    for order, payload in result.get("orders", {}).items():
        for query in payload["queries"]:
            yield order, query


def compact_query(
    revision: str,
    repeat: int,
    treatment: str,
    group: str,
    query: dict[str, Any],
) -> dict[str, Any]:
    return {
        "revision": revision,
        "repeat": repeat,
        "treatment": treatment,
        "group": group,
        "query_id": query["query_id"],
        "cue": query["cue"],
        "requested_agent": query["requested_agent"],
        "limit": query["limit"],
        "repetition": query["repetition"],
        "wallet_helper_positive": query["wallet_helper_positive"],
        "current_exact_router_positive": query["current_exact_router_positive"],
        "expected_ledger_alias": query["expected_ledger_alias"],
        "expected_chat_alias": query["expected_chat_alias"],
        "derived": query["derived"],
        "recalls": [
            {
                "rank": recall["rank"],
                "alias": recall["alias"],
                "activation": recall["activation"],
                "verified": recall["verified"],
                "trust_note": recall["trust_note"],
                "agent_id": recall["episode"].get("agent_id"),
                "tenant_id": recall["episode"].get("tenant_id"),
                "content": recall["episode"].get("content"),
                "context": recall["episode"].get("context"),
                "provenance": public_safe_provenance(recall["episode"].get("provenance")),
            }
            for recall in query["normalized_recalls"]
        ],
    }


def select_rows(
    rows: list[dict[str, Any]],
    *,
    revision: str,
    repeat: int,
    treatment: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row["revision"] == revision
        and row["repeat"] == repeat
        and row["treatment"] == treatment
    ]


def alias_signature(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "limit": row["limit"],
        "group": row["group"],
        "requested_agent": row["requested_agent"],
        "top_alias": row["derived"]["top_alias"],
        "empty": row["derived"]["empty"],
        "ledger_rank": row["derived"]["ledger_rank"],
        "chat_rank": row["derived"]["chat_rank"],
        "foreign_agent_aliases": row["derived"]["foreign_agent_aliases"],
        "recall_aliases": [recall["alias"] for recall in row["recalls"]],
        "recall_agents": [recall["agent_id"] for recall in row["recalls"]],
    }


def lexical_primary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    primary = [
        row
        for row in rows
        if row["limit"] == 128 and not row["query_id"].startswith("wallet_")
    ]
    return {
        "n": len(primary),
        "both_pair_members_visible": sum(
            bool(row["derived"]["both_pair_members_visible"]) for row in primary
        ),
        "ledger_above_chat": sum(row["derived"]["ledger_above_chat"] is True for row in primary),
        "chat_above_ledger": sum(row["derived"]["ledger_above_chat"] is False for row in primary),
        "foreign_agent_rows": sum(len(row["derived"]["foreign_agent_aliases"]) for row in primary),
    }


def scoped_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    wallet = [row for row in rows if row["query_id"].startswith("wallet_")]
    non_wallet = [row for row in rows if not row["query_id"].startswith("wallet_")]
    by_case: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for row in non_wallet:
        case = row["query_id"].rsplit(":k", 1)[0]
        by_case[case][int(row["limit"])] = row
    rescued: list[str] = []
    for case, pair in sorted(by_case.items()):
        low = pair[3]
        high = pair[128]
        if (
            low["derived"]["ledger_rank"] is None
            and high["derived"]["ledger_rank"] is not None
            and not low["derived"]["foreign_agent_aliases"]
            and not high["derived"]["foreign_agent_aliases"]
        ):
            rescued.append(case)
    high_non_wallet = [row for row in non_wallet if row["limit"] == 128]
    return {
        "wallet_queries": len(wallet),
        "wallet_queries_with_foreign_agent_rows": sum(
            bool(row["derived"]["foreign_agent_aliases"]) for row in wallet
        ),
        "wallet_foreign_aliases": sorted(
            {
                alias
                for row in wallet
                for alias in row["derived"]["foreign_agent_aliases"]
            }
        ),
        "non_wallet_k128_n": len(high_non_wallet),
        "non_wallet_k128_pair_visible": sum(
            bool(row["derived"]["both_pair_members_visible"]) for row in high_non_wallet
        ),
        "non_wallet_k128_foreign_agent_rows": sum(
            len(row["derived"]["foreign_agent_aliases"]) for row in high_non_wallet
        ),
        "low_k_missing_ledger_rescued_at_k128_n": len(rescued),
        "low_k_missing_ledger_rescued_at_k128_cases": rescued,
    }


def wallet_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_group[row["group"]].append(row)
    result: dict[str, Any] = {}
    for group, group_rows in sorted(by_group.items()):
        missing = next(row for row in group_rows if row["query_id"] == "wallet_missing:k128")
        repeated: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
        for row in group_rows:
            if row["query_id"] != "wallet_missing:k128":
                repeated[(str(row["requested_agent"]), int(row["limit"]))].append(row)
        cache_invariant = all(
            len({json.dumps(alias_signature(row), sort_keys=True) for row in pair}) == 1
            for pair in repeated.values()
        )
        result[group] = {
            "queries": len(group_rows),
            "queries_with_foreign_agent_rows": sum(
                bool(row["derived"]["foreign_agent_aliases"]) for row in group_rows
            ),
            "cache_repetitions_alias_invariant": cache_invariant,
            "missing_agent_top_alias": missing["derived"]["top_alias"],
            "missing_agent_foreign_aliases": missing["derived"]["foreign_agent_aliases"],
            "top_by_query": {
                row["query_id"]: row["derived"]["top_alias"] for row in group_rows
            },
        }
    return result


def exact_or_shipping_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "queries": len(rows),
        "empty_queries": [row["query_id"] for row in rows if row["derived"]["empty"]],
        "queries_with_foreign_agent_rows": [
            row["query_id"] for row in rows if row["derived"]["foreign_agent_aliases"]
        ],
        "top_by_query": {row["query_id"]: row["derived"]["top_alias"] for row in rows},
        "foreign_by_query": {
            row["query_id"]: row["derived"]["foreign_agent_aliases"] for row in rows
        },
    }


def analysis(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    missing: list[str] = []
    matrix_receipts: dict[str, Any] = {}
    runs: dict[tuple[str, int, str], dict[str, Any]] = {}
    compact_rows: list[dict[str, Any]] = []

    for revision in REVISIONS:
        for repeat in REPEATS:
            receipt_path = root / f"{revision}.r{repeat}.matrix-receipt.json"
            if not receipt_path.exists():
                missing.append(str(receipt_path))
                continue
            receipt = load(receipt_path)
            matrix_receipts[f"{revision}.r{repeat}"] = {
                "status": receipt["status"],
                "completed": len(receipt["commands"]),
                "exit_codes": [command["exit_code"] for command in receipt["commands"]],
            }
            for treatment in TREATMENTS:
                path = root / f"{revision}.r{repeat}.{treatment}.json"
                if not path.exists():
                    missing.append(str(path))
                    continue
                payload = load(path)
                runs[(revision, repeat, treatment)] = payload
                for group, query in iter_queries(payload["result"]):
                    compact_rows.append(
                        compact_query(revision, repeat, treatment, group, query)
                    )

    official: dict[str, Any] = {}
    for revision in REVISIONS:
        official[revision] = {}
        for condition in ("isolated", "shared"):
            path = root / f"{revision}.official-{condition}.json"
            if not path.exists():
                missing.append(str(path))
                continue
            official[revision][condition] = official_summary(load(path))

    if missing:
        return {"status": "INCOMPLETE", "missing": missing}, compact_rows, missing

    observed: dict[str, Any] = {}
    for revision in REVISIONS:
        observed[revision] = {}
        for repeat in REPEATS:
            observed[revision][f"r{repeat}"] = {
                "ambiguous": runs[(revision, repeat, "ambiguous")]["result"]["derived"],
                "lexical_primary": lexical_primary(
                    select_rows(compact_rows, revision=revision, repeat=repeat, treatment="lexical")
                ),
                "scoped": scoped_summary(
                    select_rows(compact_rows, revision=revision, repeat=repeat, treatment="scoped")
                ),
                "wallet": wallet_summary(
                    select_rows(compact_rows, revision=revision, repeat=repeat, treatment="wallet")
                ),
                "exact": exact_or_shipping_summary(
                    select_rows(compact_rows, revision=revision, repeat=repeat, treatment="exact")
                ),
                "shipping": exact_or_shipping_summary(
                    select_rows(compact_rows, revision=revision, repeat=repeat, treatment="shipping")
                ),
            }

    reproducibility: dict[str, Any] = {}
    for revision in REVISIONS:
        r1 = observed[revision]["r1"]
        r2 = observed[revision]["r2"]
        ambiguous_core_1 = {
            "hits": r1["ambiguous"]["top1_exact_id_hits"],
            "invariant": r1["ambiguous"]["within_store_top1_invariant_by_cue"],
        }
        ambiguous_core_2 = {
            "hits": r2["ambiguous"]["top1_exact_id_hits"],
            "invariant": r2["ambiguous"]["within_store_top1_invariant_by_cue"],
        }
        reproducibility[revision] = {
            "ambiguous_core_stable": ambiguous_core_1 == ambiguous_core_2,
            "ambiguous_specific_winner_stable": (
                r1["ambiguous"]["top_ids_by_cue"] == r2["ambiguous"]["top_ids_by_cue"]
            ),
            "lexical_non_wallet_k128_stable": r1["lexical_primary"] == r2["lexical_primary"],
            "scoped_wallet_foreign_pattern_stable": {
                key: r1["scoped"][key] == r2["scoped"][key]
                for key in (
                    "wallet_queries_with_foreign_agent_rows",
                    "wallet_foreign_aliases",
                    "non_wallet_k128_pair_visible",
                    "non_wallet_k128_foreign_agent_rows",
                )
            },
            "scoped_low_k_rescued_case_set_stable": (
                r1["scoped"]["low_k_missing_ledger_rescued_at_k128_cases"]
                == r2["scoped"]["low_k_missing_ledger_rescued_at_k128_cases"]
            ),
            "wallet_stable": r1["wallet"] == r2["wallet"],
            "exact_full_signature_stable": r1["exact"] == r2["exact"],
            "exact_missing_agent_control_stable": {
                key: {
                    query_id: r1["exact"][key][query_id]
                    for query_id in r1["exact"][key]
                    if query_id.startswith("ticket_missing:")
                }
                == {
                    query_id: r2["exact"][key][query_id]
                    for query_id in r2["exact"][key]
                    if query_id.startswith("ticket_missing:")
                }
                for key in ("top_by_query", "foreign_by_query")
            },
            "shipping_stable": r1["shipping"] == r2["shipping"],
        }

    official_gate = {
        revision: {
            "isolated_script_threshold_pass": official[revision]["isolated"]["top1_accuracy"] >= 0.9,
            "shared_within_store_invariant": official[revision]["shared"]["all_domains_invariant"],
            "shared_within_conditional_ceiling": sum(
                bool(row["hit"]) for row in official[revision]["shared"]["rows"]
            )
            <= 10,
        }
        for revision in REVISIONS
    }
    protocol_gate = {
        "matrix_receipts": matrix_receipts,
        "all_matrix_receipts_pass": all(
            receipt["status"] == "PASS"
            and receipt["completed"] == len(TREATMENTS)
            and set(receipt["exit_codes"]) == {0}
            for receipt in matrix_receipts.values()
        ),
        "all_official_gates_pass": all(
            all(values.values()) for values in official_gate.values()
        ),
    }

    summary = {
        "schema": "ams-fluctlightdb-compact-analysis/1",
        "status": "COMPLETE",
        "protocol_gate": protocol_gate,
        "official": official,
        "official_gate": official_gate,
        "observed": observed,
        "logical_reproducibility": reproducibility,
        "interpretation_contract": {
            "structural_ceiling": "conditional on within-frozen-store top-1 invariance",
            "paired_provenance_population": "45 non-wallet lexical-bound cases with both pair members visible at K=128",
            "scope_failure_observable": "returned stored episode.agent_id differs from requested agent_id",
            "tenant_claims": "not assessed",
            "security_or_production_claims": "not assessed",
        },
        "compact_query_rows": len(compact_rows),
    }
    return summary, compact_rows, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary, rows, missing = analysis(args.runs.resolve())
    output_dir = args.output_dir.resolve()
    summary_path = output_dir / "summary.json"
    rows_path = output_dir / "compact-query-rows.json"
    dump(summary_path, summary)
    dump(rows_path, rows)
    def evidence_row(row: dict[str, Any]) -> dict[str, Any]:
        if row["treatment"] == "lexical":
            return {
                "revision": row["revision"],
                "repeat": row["repeat"],
                "treatment": "lexical",
                "query_id": row["query_id"],
                "ledger_rank": row["derived"]["ledger_rank"],
                "chat_rank": row["derived"]["chat_rank"],
                "both_pair_members_visible": row["derived"]["both_pair_members_visible"],
                "ledger_above_chat": row["derived"]["ledger_above_chat"],
                "recall_aliases": [recall["alias"] for recall in row["recalls"]],
                "recall_verified": [recall["verified"] for recall in row["recalls"]],
            }
        return {
            "revision": row["revision"],
            "repeat": row["repeat"],
            "treatment": row["treatment"],
            "group": row["group"],
            "query_id": row["query_id"],
            "requested_agent": row["requested_agent"],
            "limit": row["limit"],
            "repetition": row["repetition"],
            "wallet_helper_positive": row["wallet_helper_positive"],
            "current_exact_router_positive": row["current_exact_router_positive"],
            "expected_ledger_alias": row["expected_ledger_alias"],
            "expected_chat_alias": row["expected_chat_alias"],
            "top_alias": row["derived"]["top_alias"],
            "ledger_rank": row["derived"]["ledger_rank"],
            "chat_rank": row["derived"]["chat_rank"],
            "both_pair_members_visible": row["derived"]["both_pair_members_visible"],
            "ledger_above_chat": row["derived"]["ledger_above_chat"],
            "foreign_agent_aliases": row["derived"]["foreign_agent_aliases"],
            "empty": row["derived"]["empty"],
            "recalls": [
                {
                    "alias": recall["alias"],
                    "verified": recall["verified"],
                    "agent_id": recall["agent_id"],
                    "provenance_kind": (recall.get("provenance") or {}).get("kind"),
                }
                for recall in row["recalls"]
            ],
        }

    evidence_rows = [
        evidence_row(row)
        for row in rows
        if row["treatment"] in {"wallet", "exact", "shipping"}
        or (row["treatment"] == "scoped" and row["query_id"].startswith("wallet_"))
        or (
            row["treatment"] == "lexical"
            and row["limit"] == 128
            and not row["query_id"].startswith("wallet_")
        )
    ]
    evidence_path = output_dir / "posttest-evidence.json"
    dump(
        evidence_path,
        {
            "schema": "ams-fluctlightdb-posttest-evidence/1",
            "selection_contract": [
                "all wallet, exact-helper, and shipping-control query rows",
                "all scoped wallet rows",
                "all 45 non-wallet lexical K=128 rows for both revisions and repeats",
            ],
            "summary_sha256": sha256(summary_path),
            "rows": evidence_rows,
        },
    )
    manifest = {
        "summary.json": sha256(summary_path),
        "compact-query-rows.json": sha256(rows_path),
        "posttest-evidence.json": sha256(evidence_path),
        "audit.py": sha256(Path(__file__).resolve().parent / "audit.py"),
        "analyze_results.py": sha256(Path(__file__).resolve()),
    }
    dump(output_dir / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "compact_query_rows": len(rows),
                "missing": missing,
                "output_dir": str(output_dir),
            }
        )
    )
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
