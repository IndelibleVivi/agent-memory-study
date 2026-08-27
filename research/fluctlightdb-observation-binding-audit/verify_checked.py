#!/usr/bin/env python3
"""Verify the checked compact FluctlightDB audit receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
REVISIONS = ("paper-time", "repair-descendant")
REPEATS = ("r1", "r2")


def load(name: str) -> Any:
    return json.loads((RAW / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    summary_path = RAW / "summary.json"
    evidence_path = RAW / "posttest-evidence.json"
    summary = load("summary.json")
    evidence = load("posttest-evidence.json")
    compact_rows = load("compact-query-rows.json")
    manifest = load("manifest.json")

    require(summary["status"] == "COMPLETE", "summary is not complete")
    require(summary["compact_query_rows"] == 1140, "unexpected compact-row count")
    require(summary["protocol_gate"]["all_matrix_receipts_pass"], "matrix gate failed")
    require(summary["protocol_gate"]["all_official_gates_pass"], "official gate failed")
    require(evidence["summary_sha256"] == sha256(summary_path), "evidence/summary link failed")
    require(len(evidence["rows"]) == 360, "unexpected selected-evidence row count")
    require(len(compact_rows) == 1140, "unexpected complete compact-row count")
    checked_paths = {
        "summary.json": summary_path,
        "compact-query-rows.json": RAW / "compact-query-rows.json",
        "posttest-evidence.json": evidence_path,
        "audit.py": ROOT / "audit.py",
        "analyze_results.py": ROOT / "analyze_results.py",
    }
    require(set(manifest) == set(checked_paths), "manifest file set drift")
    for name, path in checked_paths.items():
        require(manifest[name] == sha256(path), f"manifest hash mismatch: {name}")

    for revision in REVISIONS:
        official = summary["official"][revision]
        require(official["isolated"]["hits"] == "50/50", f"{revision}: isolated result drift")
        require(official["shared"]["hits"] == "9/50", f"{revision}: shared result drift")
        require(
            official["shared"]["all_domains_invariant"],
            f"{revision}: conditional-ceiling premise absent",
        )
        for repeat in REPEATS:
            observed = summary["observed"][revision][repeat]
            require(observed["ambiguous"]["top1_exact_id_hits"] == 9, f"{revision}/{repeat}: ambiguous hits")
            require(
                observed["lexical_primary"]
                == {
                    "n": 45,
                    "both_pair_members_visible": 45,
                    "ledger_above_chat": 45,
                    "chat_above_ledger": 0,
                    "foreign_agent_rows": 0,
                },
                f"{revision}/{repeat}: lexical K=128 gate",
            )
            scoped = observed["scoped"]
            require(scoped["wallet_queries"] == 10, f"{revision}/{repeat}: wallet query count")
            require(
                scoped["wallet_queries_with_foreign_agent_rows"] == 10,
                f"{revision}/{repeat}: scoped wallet result",
            )
            require(scoped["non_wallet_k128_n"] == 45, f"{revision}/{repeat}: non-wallet count")
            require(scoped["non_wallet_k128_pair_visible"] == 45, f"{revision}/{repeat}: pair visibility")
            require(scoped["non_wallet_k128_foreign_agent_rows"] == 0, f"{revision}/{repeat}: foreign non-wallet")
            for order in ("forward", "reverse"):
                wallet = observed["wallet"][order]
                require(wallet["cache_repetitions_alias_invariant"], f"{revision}/{repeat}/{order}: cache")
                require(wallet["missing_agent_foreign_aliases"], f"{revision}/{repeat}/{order}: missing-agent control")
            require(
                observed["wallet"]["forward"]["missing_agent_top_alias"]
                != observed["wallet"]["reverse"]["missing_agent_top_alias"],
                f"{revision}/{repeat}: order-reversal control",
            )
            shipping = observed["shipping"]
            require(
                shipping["queries_with_foreign_agent_rows"] == []
                and shipping["top_by_query"]["shipping_missing:k128"] is None,
                f"{revision}/{repeat}: shipping negative control",
            )
            exact = observed["exact"]
            if revision == "paper-time":
                require(
                    exact["foreign_by_query"]["ticket_missing:k1"] == []
                    and exact["foreign_by_query"]["ticket_missing:k3"] == []
                    and exact["top_by_query"]["ticket_missing:k1"] is None
                    and exact["top_by_query"]["ticket_missing:k3"] is None,
                    f"{revision}/{repeat}: exact-helper negative control",
                )
            else:
                require(
                    len(exact["queries_with_foreign_agent_rows"]) == 6
                    and exact["foreign_by_query"]["ticket_missing:k1"]
                    and len(exact["foreign_by_query"]["ticket_missing:k3"]) == 2,
                    f"{revision}/{repeat}: exact-helper scope result",
                )

    reproducibility = summary["logical_reproducibility"]
    for revision in REVISIONS:
        stable = reproducibility[revision]
        require(stable["ambiguous_core_stable"], f"{revision}: ambiguous core unstable")
        require(stable["lexical_non_wallet_k128_stable"], f"{revision}: lexical core unstable")
        require(stable["wallet_stable"], f"{revision}: wallet core unstable")
        require(stable["shipping_stable"], f"{revision}: shipping control unstable")
        require(all(stable["exact_missing_agent_control_stable"].values()), f"{revision}: missing-agent control unstable")

    print(
        json.dumps(
            {
                "status": "PASS",
                "summary_sha256": sha256(summary_path),
                "posttest_evidence_sha256": sha256(evidence_path),
                "compact_query_rows": summary["compact_query_rows"],
                "selected_evidence_rows": len(evidence["rows"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
