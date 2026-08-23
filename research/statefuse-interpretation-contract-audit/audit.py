#!/usr/bin/env python3
"""Run the preregistered StateFuse interpretation-contract audit.

The runner imports a reader-supplied exact StateFuse checkout, verifies the
locked source and paper identities, records the official pytest receipt, and
executes deterministic synthetic H1/H2 fixtures. It makes no model or network
call and does not copy upstream source or tests into this artifact.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import itertools
import json
import locale
import math
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Iterator, Sequence


sys.dont_write_bytecode = True

ARTIFACT_ROOT = Path(__file__).resolve().parent
EXPECTED_COMMIT = "79a6229f83a7b174a2a9ac8fd0ace267ae30e79b"
EXPECTED_VERSION = "0.3.0"
EXPECTED_PYTEST_COUNT = 139
EXPECTED_PAPER_SHA256 = "128853be83e65122ff6f29b006416c7d79b5c74a601fe277b65b82b6ff9dc96e"
EXPECTED_SUCCESSOR_MANUSCRIPT_TITLE = (
    "StateFuse: Taxonomy-Aware Conflict-Preserving Memory "
    "for Heterogeneous Agent Systems"
)
PAPER_ID = "arXiv:2607.05844v1"
PAPER_URL = "https://arxiv.org/pdf/2607.05844v1"
SOURCE_URL = "https://github.com/nZiben/statefuse"
AMS_BASE_COMMIT = "8385c4bc9e4fcec24fa84cd740b6a0d8e7998522"

EXPECTED_SOURCE_FILES = {
    "README.md": {
        "git_blob": "6251e3d40693e37188a4283f50ded875b180109b",
        "sha256": "f267ff33faa160aee03ade44c76e4247e748e1a6d666be1c506574186e5c7998",
    },
    "paper/main.tex": {
        "git_blob": "9fe67c385111e15ffc31c0fa2b9cac4e9dd8a68c",
        "sha256": "f1097cb838055b6631402d610661e447b2ab4bd1bbd98eddea3748bf82aec404",
    },
    "pyproject.toml": {
        "git_blob": "d99fb7bba787124d8745fecc343d94610c9c7440",
        "sha256": "9dfbb6496ffb7b821dfe76f728f19e25024d4eada5a85645fa09cf98b86e9647",
    },
    "src/statefuse/conflict.py": {
        "git_blob": "e9b24469121adea208b67a11b5437da8bd569fca",
        "sha256": "39b4b895a8701202f256927ea03c6f4de9757294bfd571d703836df648799444",
    },
    "src/statefuse/materialize.py": {
        "git_blob": "513ed8c1aa4e0088580b7a9d3f33ddb5987ae283",
        "sha256": "75de266ba3822afc65681b452315a755e80d7f8f42e95812525af3e6225fb928",
    },
    "src/statefuse/model.py": {
        "git_blob": "17073f82dcaa722ba4706c57baea00a9305e5ef7",
        "sha256": "21f5948ccb974aa483a8ce988398bbb7c84e508cf422c8673993ca06d4182bb9",
    },
    "src/statefuse/oplog.py": {
        "git_blob": "6b7a59c348cc486d56e8911f44578ac0b9dd3642",
        "sha256": "ecaa86d68836b4016bad8ee89444e0e891860e6d9110a4c0fcf4b3d0eccecb80",
    },
    "src/statefuse/ops.py": {
        "git_blob": "12aa5f9d32ef26493826ef55e63dccb6b70d3212",
        "sha256": "4f8c86ff2ddc270119567ece0f96af67975cc81491543420f82b2964ce9b36d2",
    },
    "src/statefuse/resolver.py": {
        "git_blob": "d6b667ff401bfcbbcd5c820bff10862ba6b68980",
        "sha256": "31b25a08cb07b260d8e6aa910cb3d4b3d2b3abaf9178f898cf148f2ba3ba5804",
    },
    "src/statefuse/utils.py": {
        "git_blob": "d88a26c049e18535952b3ec5adeaf9520b59a320",
        "sha256": "face7a288e566980326a71b0ca8e48dc8ef4e9b6774048b3b366a4eb14aa1bf9",
    },
    "src/statefuse/view.py": {
        "git_blob": "6c3e7782fa1a06d1eb423a9b4d0bdb90ecbad037",
        "sha256": "332095b8dd6229ef0de8bb0e917ca04ad29dd5769aaa4f0c9a1af1e8b8e25dc3",
    },
    "tests/test_conflicts.py": {
        "git_blob": "08cd7249925f8bfa57e811fdbb3a18602ceefbcc",
        "sha256": "67f784ed7de5a2350b6247e1b50c939fdab9fad6ce9929cbb0d81cbddccf2948",
    },
    "tests/test_resolution_lifecycle.py": {
        "git_blob": "2127f863b5e2a20727f1a794d95c77b208008eea",
        "sha256": "7ed669673da5486646a93401eedd9aaf2812495a386e0c3677f6e55f7dbd00c5",
    },
    "tests/test_taxonomy_conflicts.py": {
        "git_blob": "8826063ff01ee38be1e1dd68dfd2a73670bee1b8",
        "sha256": "931cce1c04edb5370736aed53aba65ded2319c78d3a9a029c0150cf68b1f3790",
    },
    "tests/test_view_projection.py": {
        "git_blob": "598d583cab76012f49427065874af1863b21cf2c",
        "sha256": "c2ef9f3e82051159868207e3c18cf565fe6110c25a61f9c03bebe2155968193e",
    },
}

PUBLIC_SUFFIXES = {".json", ".jsonl", ".md", ".py", ".txt"}
FORBIDDEN_NAMES = {".DS_Store", "__pycache__"}
FORBIDDEN_SUFFIXES = {".log", ".pyc", ".pyo", ".tmp"}
PRIMARY_RELATIVE_PATHS = {
    "raw/cases.jsonl",
    "raw/contract_descriptors.json",
    "raw/decision.json",
    "raw/environment.json",
    "raw/pytest_collect.txt",
    "raw/pytest_run.txt",
    "raw/run_results.jsonl",
    "raw/source_manifest.json",
}
GENERATED_RELATIVE_PATHS = PRIMARY_RELATIVE_PATHS | {
    "RESULTS.txt",
    "raw/readiness.json",
    "raw/reproduction.json",
}
EXPECTED_CASE_COUNT = 8
EXPECTED_GROUP_COUNT = 17
EXPECTED_RESULT_COUNT = 428
STATE_SNAPSHOT_SCHEMA = "statefuse-observable-state/1"
PROJECTION_SNAPSHOT_SCHEMA = "statefuse-observable-projection/1"

EXPECTED_CASES = {
    "H1-EQ": {
        "contract_ids": ("E0-raw-equality", "E1-folded-equality"),
        "op_count": 2,
        "op_ids": ("op-h1-eq-lower", "op-h1-eq-upper"),
        "opset_sha256": "f5725fca19bb22581f5f7ea437358787f442381676eb506f1954f3a48f5e5154",
        "permutation_count": 2,
        "queries": ({"query_id": "fixed", "valid_at": None, "context": {}},),
    },
    "H1-REF": {
        "contract_ids": ("R0-raw-ref", "R1-folded-ref"),
        "op_count": 3,
        "op_ids": ("op-h1-ref-lower", "op-h1-ref-retract", "op-h1-ref-upper"),
        "opset_sha256": "f5375bcd19b3d6307781d65f69b7fdb9af517884706d831d291c9f98e2f45515",
        "permutation_count": 6,
        "queries": ({"query_id": "fixed", "valid_at": None, "context": {}},),
    },
    "H1-DET": {
        "contract_ids": (
            "D1-budget-v1-ab",
            "D2-budget-v1-abc",
            "D2-budget-v2-abc",
        ),
        "op_count": 5,
        "op_ids": (
            "op-h1-det-capacity",
            "op-h1-det-cost-a",
            "op-h1-det-cost-b",
            "op-h1-det-cost-c",
            "op-h1-det-resolution",
        ),
        "opset_sha256": "126a828f6b867431c5fc66a912750b2220dc2f556c9ecbfa15a8da69f1e22a6d",
        "permutation_count": 120,
        "queries": ({"query_id": "fixed", "valid_at": None, "context": {}},),
    },
    "H2-NONE": {
        "contract_ids": ("H2-identity",),
        "op_count": 2,
        "op_ids": ("op-h2-monday", "op-h2-tuesday"),
        "opset_sha256": "b9066e9681c111a775809917fce80d9c504b7d08c10239c0c54438091125bf78",
        "permutation_count": 2,
        "queries": (
            {
                "query_id": "tuesday-noon",
                "valid_at": "2026-04-07T12:00:00Z",
                "context": {},
            },
            {"query_id": "valid-at-none", "valid_at": None, "context": {}},
        ),
    },
    "H2-ID": {
        "contract_ids": ("H2-identity",),
        "op_count": 3,
        "op_ids": ("op-h2-monday", "op-h2-retract-id", "op-h2-tuesday"),
        "opset_sha256": "15b42eadf02e9c9f019eca93b5a773242236c933829b67bbe142dd1786898008",
        "permutation_count": 6,
        "queries": (
            {
                "query_id": "tuesday-noon",
                "valid_at": "2026-04-07T12:00:00Z",
                "context": {},
            },
            {"query_id": "valid-at-none", "valid_at": None, "context": {}},
        ),
    },
    "H2-REF": {
        "contract_ids": ("H2-identity",),
        "op_count": 3,
        "op_ids": ("op-h2-monday", "op-h2-retract-ref", "op-h2-tuesday"),
        "opset_sha256": "e1070f57a3fa6777ce562670428a11642843c66083eaa77464e836b848d8e8b4",
        "permutation_count": 6,
        "queries": (
            {
                "query_id": "tuesday-noon",
                "valid_at": "2026-04-07T12:00:00Z",
                "context": {},
            },
            {"query_id": "valid-at-none", "valid_at": None, "context": {}},
        ),
    },
    "H2-CTX": {
        "contract_ids": ("H2-identity",),
        "op_count": 3,
        "op_ids": ("op-h2-monday", "op-h2-retract-ref", "op-h2-tuesday"),
        "opset_sha256": "86f232b9a94179708da1f8f746120862152698de05806922b7e7508d722346e5",
        "permutation_count": 6,
        "queries": (
            {
                "query_id": "tuesday-noon",
                "valid_at": "2026-04-07T12:00:00Z",
                "context": {"occurrence": "2026-04-07"},
            },
            {
                "query_id": "valid-at-none",
                "valid_at": None,
                "context": {"occurrence": "2026-04-07"},
            },
        ),
    },
    "H2-VALUE": {
        "contract_ids": ("H2-identity",),
        "op_count": 3,
        "op_ids": ("op-h2-monday", "op-h2-retract-ref", "op-h2-tuesday"),
        "opset_sha256": "955160510cdad647629a4e0ff71fa7e4de3ef369a356670be3ce8df95d623d71",
        "permutation_count": 6,
        "queries": (
            {
                "query_id": "tuesday-noon",
                "valid_at": "2026-04-07T12:00:00Z",
                "context": {},
            },
            {"query_id": "valid-at-none", "valid_at": None, "context": {}},
        ),
    },
}

EXPECTED_CONTRACT_PARAMETERS = {
    "D1-budget-v1-ab": {"detector_id": "budget/v1", "included_costs": ["A", "B"]},
    "D2-budget-v1-abc": {
        "detector_id": "budget/v1",
        "included_costs": ["A", "B", "C"],
    },
    "D2-budget-v2-abc": {
        "detector_id": "budget/v2",
        "included_costs": ["A", "B", "C"],
    },
    "E0-raw-equality": {"equality": "raw", "normalize_for_claim_ref": False},
    "E1-folded-equality": {
        "equality": "strip_casefold",
        "normalize_for_claim_ref": False,
    },
    "H2-identity": {"equality": "raw", "normalize_for_claim_ref": False},
    "R0-raw-ref": {
        "equality": "strip_casefold",
        "normalize_for_claim_ref": False,
    },
    "R1-folded-ref": {
        "equality": "strip_casefold",
        "normalize_for_claim_ref": True,
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def save_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def git_output(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path)
    parser.add_argument("--paper-pdf", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACT_ROOT,
        help="New output root. Existing generated outputs are never overwritten.",
    )
    parser.add_argument("--verify-checked", action="store_true")
    parser.add_argument("--compare-checked", action="store_true")
    parser.add_argument("--refresh-checksums", action="store_true")
    return parser.parse_args()


def normalize_pytest_output(text: str) -> str:
    summary_line = re.compile(
        r"(?m)^.*\b(?:collected|passed|failed|skipped|errors?|warnings?)\b.*$"
    )

    def replace_elapsed(match: re.Match[str]) -> str:
        return re.sub(
            r"\bin \d+(?:\.\d+)?s\b",
            "in <elapsed>s",
            match.group(0),
        )

    return summary_line.sub(replace_elapsed, text)


def command_receipt(command: Sequence[str], cwd_label: str, completed: subprocess.CompletedProcess[str]) -> str:
    stdout = normalize_pytest_output(completed.stdout)
    stderr = normalize_pytest_output(completed.stderr)
    return (
        f"command: {' '.join(command)}\n"
        f"working_directory: {cwd_label}\n"
        f"exit_code: {completed.returncode}\n"
        "elapsed_time: normalized_as_non_semantic_receipt_metadata\n"
        "stdout:\n"
        f"{stdout}"
        "stderr:\n"
        f"{stderr}"
    )


def run_pytest(source_root: Path, raw_dir: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(
        {
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(source_root / "src"),
            "TZ": "Asia/Singapore",
        }
    )
    commands = {
        "collect": ["<PYTHON>", "-m", "pytest", "--collect-only", "-q"],
        "run": ["<PYTHON>", "-m", "pytest", "-q", "-ra"],
    }
    actual = {
        name: [sys.executable, *command[1:]]
        for name, command in commands.items()
    }
    completed: dict[str, subprocess.CompletedProcess[str]] = {}
    for name in ("collect", "run"):
        completed[name] = subprocess.run(
            actual[name],
            cwd=source_root,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        (raw_dir / f"pytest_{name}.txt").write_text(
            command_receipt(commands[name], "<SOURCE_REPO>", completed[name]),
            encoding="utf-8",
        )
        require(completed[name].returncode == 0, f"pytest {name} failed")

    collected_stdout = normalize_pytest_output(completed["collect"].stdout)
    run_stdout = normalize_pytest_output(completed["run"].stdout)
    node_ids = [line for line in collected_stdout.splitlines() if "::test_" in line]
    require(len(node_ids) == EXPECTED_PYTEST_COUNT, "unexpected pytest collected-node count")
    require(
        re.search(rf"\b{EXPECTED_PYTEST_COUNT} passed\b", run_stdout) is not None,
        "unexpected pytest pass count",
    )
    require(" skipped" not in run_stdout, "unexpected skipped tests in local receipt")
    return {
        "collect_command": commands["collect"],
        "collected_node_count": len(node_ids),
        "run_command": commands["run"],
        "passed_count": EXPECTED_PYTEST_COUNT,
        "skipped_count": 0,
        "status": "passed",
    }


@contextlib.contextmanager
def blocked_network() -> Iterator[None]:
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    def deny(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("network access is disabled during the synthetic audit")

    socket.socket.connect = deny  # type: ignore[method-assign,assignment]
    socket.socket.connect_ex = deny  # type: ignore[method-assign,assignment]
    socket.create_connection = deny  # type: ignore[assignment]
    socket.getaddrinfo = deny  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign,assignment]
        socket.socket.connect_ex = original_connect_ex  # type: ignore[method-assign,assignment]
        socket.create_connection = original_create_connection
        socket.getaddrinfo = original_getaddrinfo


def load_api(source_root: Path) -> SimpleNamespace:
    source_path = str(source_root / "src")
    if source_path not in sys.path:
        sys.path.insert(0, source_path)

    from statefuse.conflict import (  # type: ignore[import-not-found]
        ConflictDetectionContext,
        PredicateRegistry,
        make_conflict,
    )
    from statefuse.materialize import materialize  # type: ignore[import-not-found]
    from statefuse.model import (  # type: ignore[import-not-found]
        Claim,
        ClaimKey,
        ResolutionRecord,
        ValidityInterval,
    )
    from statefuse.oplog import OpLog  # type: ignore[import-not-found]
    from statefuse.ops import (  # type: ignore[import-not-found]
        ClaimAdded,
        ClaimRetracted,
        ResolutionAdded,
    )
    from statefuse.resolver import (  # type: ignore[import-not-found]
        ConservativeHeuristicResolver,
        ViewConstraints,
    )
    from statefuse.view import build_view  # type: ignore[import-not-found]

    return SimpleNamespace(
        Claim=Claim,
        ClaimAdded=ClaimAdded,
        ClaimKey=ClaimKey,
        ClaimRetracted=ClaimRetracted,
        ConflictDetectionContext=ConflictDetectionContext,
        ConservativeHeuristicResolver=ConservativeHeuristicResolver,
        materialize=materialize,
        make_conflict=make_conflict,
        OpLog=OpLog,
        PredicateRegistry=PredicateRegistry,
        ResolutionAdded=ResolutionAdded,
        ResolutionRecord=ResolutionRecord,
        ValidityInterval=ValidityInterval,
        ViewConstraints=ViewConstraints,
        build_view=build_view,
    )


def key_label(key: Any) -> str:
    return f"{key.namespace}:{key.subject}:{key.predicate}"


def lane_rows(mapping: dict[tuple[str, str | None], Any], value_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (conflict_ref, scope), value in sorted(
        mapping.items(), key=lambda item: (item[0][0], item[0][1] is not None, item[0][1] or "")
    ):
        rows.append(
            {
                "conflict_ref": conflict_ref,
                "scope": scope,
                value_name: value if isinstance(value, str) else value.resolution_id,
            }
        )
    return rows


def snapshot_conflict(conflict: Any) -> dict[str, Any]:
    return {
        "annotations": conflict.annotations,
        "candidate_ids": [claim.claim_id for claim in conflict.candidates],
        "candidate_values": [claim.value for claim in conflict.candidates],
        "conflict_class": conflict.conflict_class,
        "conflict_id": conflict.conflict_id,
        "conflict_ref": conflict.conflict_ref,
        "conflict_subclass": conflict.conflict_subclass,
        "conflict_type": conflict.conflict_type,
        "detector_id": conflict.detector_id,
        "key": key_label(conflict.key),
        "keys": [key_label(key) for key in conflict.keys],
        "reason": conflict.reason,
        "witness": conflict.witness,
    }


def snapshot_state(state: Any) -> dict[str, Any]:
    return {
        "active_claim_ids_by_key": {
            key_label(key): [claim.claim_id for claim in claims]
            for key, claims in sorted(state.active_claims_by_key.items())
        },
        "active_resolutions": lane_rows(
            state.active_resolutions_by_conflict_ref_and_scope, "resolution_id"
        ),
        "claim_ids_by_ref": {
            claim_ref: list(claim_ids)
            for claim_ref, claim_ids in sorted(state.claim_ids_by_ref.items())
        },
        "claim_refs_by_id": dict(sorted(state.claim_refs_by_id.items())),
        "conflicts": [snapshot_conflict(conflict) for conflict in state.conflicts],
        "effective_resolutions": lane_rows(
            state.effective_resolutions_by_conflict_ref_and_scope, "resolution_id"
        ),
        "inapplicable_claim_ids": sorted(state.inapplicable_claim_ids),
        "inactive_claim_ids": sorted(state.inactive_claim_ids),
        "lifecycle_statuses": lane_rows(
            state.lifecycle_status_by_conflict_ref_and_scope, "status"
        ),
        "resolution_records": [
            state.resolutions_by_id[resolution_id].to_dict()
            for resolution_id in sorted(state.resolutions_by_id)
        ],
        "retracted_claim_ids": sorted(state.retractions_by_target),
        "retracted_claim_refs": sorted(state.retractions_by_target_ref),
        "schema": STATE_SNAPSHOT_SCHEMA,
    }


def snapshot_projection(projection: Any) -> dict[str, Any]:
    return {
        "compatible_claim_ids_by_key": {
            key_label(key): [claim.claim_id for claim in claims]
            for key, claims in sorted(projection.compatible_claims.items())
        },
        "explanations": dict(sorted(projection.explanations.items())),
        "selected_claims_by_key": {
            key_label(key): {"claim_id": claim.claim_id, "value": claim.value}
            for key, claim in sorted(projection.selected_claims.items())
        },
        "surfaced_conflicts_by_key": {
            key_label(key): conflict.conflict_id
            for key, conflict in sorted(projection.surfaced_conflicts.items())
        },
        "surfaced_finding_ids": sorted(projection.surfaced_findings),
        "unresolved_conflict_ids": [
            conflict.conflict_id for conflict in projection.unresolved_conflicts
        ],
        "schema": PROJECTION_SNAPSHOT_SCHEMA,
    }


def make_claim_op(
    api: SimpleNamespace,
    *,
    claim_id: str,
    key: Any,
    value: Any,
    timestamp: str,
    confidence: float = 0.8,
    evidence_ids: tuple[str, ...] = (),
    provenance: dict[str, Any] | None = None,
    validity: Any = None,
    context: dict[str, Any] | None = None,
) -> Any:
    return api.ClaimAdded(
        op_id=f"op-{claim_id}",
        replica_id=f"replica-{claim_id}",
        timestamp=timestamp,
        claim=api.Claim(
            claim_id=claim_id,
            key=key,
            value=value,
            confidence=confidence,
            timestamp=timestamp,
            evidence_ids=evidence_ids,
            provenance=dict(provenance or {}),
            validity=validity,
            context=dict(context or {}),
        ),
    )


def make_retraction(
    api: SimpleNamespace,
    *,
    op_id: str,
    target_claim_id: str | None = None,
    target_claim_ref: str | None = None,
    reason: str,
) -> Any:
    return api.ClaimRetracted(
        op_id=op_id,
        replica_id="replica-reviewer",
        timestamp="2026-04-06T18:00:00Z",
        target_claim_id=target_claim_id,
        target_claim_ref=target_claim_ref,
        reason=reason,
    )


def fold_value(value: Any) -> str:
    return str(value).strip().casefold()


@dataclass(frozen=True)
class ContractSpec:
    contract_id: str
    description: str
    registry_factory: Callable[[], Any]
    detector_factory: Callable[[], tuple[Callable[[Any], Iterable[Any]], ...]]
    samples_by_predicate: dict[str, tuple[Any, ...]]
    parameters: dict[str, Any]


@dataclass(frozen=True)
class FixtureSpec:
    fixture_id: str
    ops: tuple[Any, ...]
    contract_ids: tuple[str, ...]
    queries: tuple[dict[str, Any], ...]


def make_contracts(api: SimpleNamespace) -> dict[str, ContractSpec]:
    def raw_registry() -> Any:
        return api.PredicateRegistry()

    def folded_registry(normalize_for_ref: bool) -> Any:
        registry = api.PredicateRegistry()
        registry.register(
            "state",
            normalize=fold_value,
            normalize_for_claim_ref=normalize_for_ref,
        )
        return registry

    def budget_registry() -> Any:
        registry = api.PredicateRegistry()
        registry.register("cost", multi_valued=True)
        return registry

    def budget_detector(include_c: bool, detector_id: str) -> Callable[[Any], Iterable[Any]]:
        def detect(context: Any) -> Iterable[Any]:
            capacity = context.claims_by_id.get("h1-det-capacity")
            requested = ["h1-det-cost-a", "h1-det-cost-b"]
            if include_c:
                requested.append("h1-det-cost-c")
            costs = [context.claims_by_id.get(claim_id) for claim_id in requested]
            if capacity is None or any(claim is None for claim in costs):
                return ()
            candidates = (capacity, *(claim for claim in costs if claim is not None))
            total = sum(int(claim.value["amount"]) for claim in costs if claim is not None)
            return (
                api.make_conflict(
                    candidates=candidates,
                    key=capacity.key,
                    keys=tuple(claim.key for claim in candidates),
                    conflict_type="execution.constraint.budget",
                    conflict_class="execution",
                    conflict_subclass="resource.budget",
                    detector_id=detector_id,
                    reason="Synthetic requested costs exceed the declared capacity.",
                    annotations={"fixture": "h1-det", "total_cost": total},
                    witness={
                        "capacity": capacity.value["amount"],
                        "cost_claim_ids": [claim.claim_id for claim in costs if claim is not None],
                        "total_cost": total,
                    },
                ),
            )

        return detect

    return {
        "E0-raw-equality": ContractSpec(
            "E0-raw-equality",
            "Default raw equality; semantic refs retain raw values.",
            raw_registry,
            lambda: (),
            {},
            {"equality": "raw", "normalize_for_claim_ref": False},
        ),
        "E1-folded-equality": ContractSpec(
            "E1-folded-equality",
            "Strip-and-casefold equality; semantic refs retain raw values.",
            lambda: folded_registry(False),
            lambda: (),
            {"state": ("Open", "open")},
            {"equality": "strip_casefold", "normalize_for_claim_ref": False},
        ),
        "R0-raw-ref": ContractSpec(
            "R0-raw-ref",
            "Strip-and-casefold equality without claim-ref normalization.",
            lambda: folded_registry(False),
            lambda: (),
            {"state": (" Open ", "open")},
            {"equality": "strip_casefold", "normalize_for_claim_ref": False},
        ),
        "R1-folded-ref": ContractSpec(
            "R1-folded-ref",
            "The same equality with claim-ref value normalization enabled.",
            lambda: folded_registry(True),
            lambda: (),
            {"state": (" Open ", "open")},
            {"equality": "strip_casefold", "normalize_for_claim_ref": True},
        ),
        "D1-budget-v1-ab": ContractSpec(
            "D1-budget-v1-ab",
            "Budget detector budget/v1 includes capacity and cost claims A/B.",
            budget_registry,
            lambda: (budget_detector(False, "budget/v1"),),
            {},
            {"detector_id": "budget/v1", "included_costs": ["A", "B"]},
        ),
        "D2-budget-v1-abc": ContractSpec(
            "D2-budget-v1-abc",
            "Deliberate silent drift: budget/v1 includes capacity and A/B/C.",
            budget_registry,
            lambda: (budget_detector(True, "budget/v1"),),
            {},
            {"detector_id": "budget/v1", "included_costs": ["A", "B", "C"]},
        ),
        "D2-budget-v2-abc": ContractSpec(
            "D2-budget-v2-abc",
            "Declared-version control: D2 behavior reports budget/v2.",
            budget_registry,
            lambda: (budget_detector(True, "budget/v2"),),
            {},
            {"detector_id": "budget/v2", "included_costs": ["A", "B", "C"]},
        ),
        "H2-identity": ContractSpec(
            "H2-identity",
            "Default identity registry with no normalization or custom detector.",
            raw_registry,
            lambda: (),
            {},
            {"equality": "raw", "normalize_for_claim_ref": False},
        ),
    }


def make_fixtures(api: SimpleNamespace, contracts: dict[str, ContractSpec]) -> list[FixtureSpec]:
    eq_key = api.ClaimKey("synthetic", "shop", "state")
    equal_timestamp = "2026-04-05T12:00:00Z"
    eq_ops = (
        make_claim_op(
            api,
            claim_id="h1-eq-upper",
            key=eq_key,
            value="Open",
            timestamp=equal_timestamp,
            provenance={"replica_id": "equal-score"},
        ),
        make_claim_op(
            api,
            claim_id="h1-eq-lower",
            key=eq_key,
            value="open",
            timestamp=equal_timestamp,
            provenance={"replica_id": "equal-score"},
        ),
    )

    ref_upper = make_claim_op(
        api,
        claim_id="h1-ref-upper",
        key=eq_key,
        value=" Open ",
        timestamp="2026-04-05T13:00:00Z",
    )
    ref_lower = make_claim_op(
        api,
        claim_id="h1-ref-lower",
        key=eq_key,
        value="open",
        timestamp="2026-04-05T13:01:00Z",
    )
    ref_retraction = make_retraction(
        api,
        op_id="op-h1-ref-retract",
        target_claim_ref=ref_lower.claim.claim_ref,
        reason="Synthetic semantic correction targets the normalized open handle.",
    )
    ref_ops = (ref_upper, ref_lower, ref_retraction)

    capacity_key = api.ClaimKey("synthetic", "budget", "capacity")
    cost_key = api.ClaimKey("synthetic", "budget", "cost")
    detector_claims = (
        make_claim_op(
            api,
            claim_id="h1-det-capacity",
            key=capacity_key,
            value={"amount": 10, "currency": "credits"},
            timestamp="2026-04-05T14:00:00Z",
        ),
        make_claim_op(
            api,
            claim_id="h1-det-cost-a",
            key=cost_key,
            value={"amount": 6, "item": "A"},
            timestamp="2026-04-05T14:01:00Z",
        ),
        make_claim_op(
            api,
            claim_id="h1-det-cost-b",
            key=cost_key,
            value={"amount": 5, "item": "B"},
            timestamp="2026-04-05T14:02:00Z",
        ),
        make_claim_op(
            api,
            claim_id="h1-det-cost-c",
            key=cost_key,
            value={"amount": 4, "item": "C"},
            timestamp="2026-04-05T14:03:00Z",
        ),
    )
    d1 = contracts["D1-budget-v1-ab"]
    d1_registry = d1.registry_factory()
    baseline = api.materialize(
        api.OpLog(detector_claims),
        d1_registry,
        conflict_detectors=d1.detector_factory(),
    )
    require(len(baseline.conflicts) == 1, "detector baseline must create one conflict")
    baseline_conflict = baseline.conflicts[0]
    resolution = api.ResolutionAdded(
        op_id="op-h1-det-resolution",
        replica_id="replica-reviewer",
        timestamp="2026-04-05T14:10:00Z",
        resolution=api.ResolutionRecord(
            resolution_id="h1-det-resolution",
            conflict_ref=baseline_conflict.conflict_ref,
            observed_conflict_id=baseline_conflict.conflict_id,
            selected_claim_ids=("h1-det-capacity",),
            rejected_claim_ids=("h1-det-cost-a", "h1-det-cost-b"),
            retained_claim_ids=(),
            resolution_type="synthetic_review",
            reason="Synthetic committed resolution classifies detector-v1 candidates.",
            evidence_ids=(),
            actor_id="ams-audit",
            timestamp="2026-04-05T14:10:00Z",
        ),
    )
    detector_ops = (*detector_claims, resolution)

    monday = make_claim_op(
        api,
        claim_id="h2-monday",
        key=eq_key,
        value="open",
        timestamp="2026-04-06T12:00:00Z",
        confidence=0.71,
        evidence_ids=("evidence-monday",),
        provenance={"replica_id": "monday", "source": "synthetic-observation-monday"},
        validity=api.ValidityInterval(
            "2026-04-06T00:00:00Z", "2026-04-07T00:00:00Z"
        ),
    )

    def tuesday(*, value: str = "open", context: dict[str, Any] | None = None) -> Any:
        return make_claim_op(
            api,
            claim_id="h2-tuesday",
            key=eq_key,
            value=value,
            timestamp="2026-04-07T09:00:00Z",
            confidence=0.93,
            evidence_ids=("evidence-tuesday",),
            provenance={"replica_id": "tuesday", "source": "synthetic-observation-tuesday"},
            validity=api.ValidityInterval(
                "2026-04-07T00:00:00Z", "2026-04-08T00:00:00Z"
            ),
            context=context,
        )

    exact_retraction = make_retraction(
        api,
        op_id="op-h2-retract-id",
        target_claim_id="h2-monday",
        reason="Synthetic occurrence-local exact-ID correction.",
    )
    semantic_retraction = make_retraction(
        api,
        op_id="op-h2-retract-ref",
        target_claim_ref=monday.claim.claim_ref,
        reason="Synthetic correction expressed through the broad semantic handle.",
    )
    tuesday_query = {
        "query_id": "tuesday-noon",
        "valid_at": "2026-04-07T12:00:00Z",
        "context": {},
    }
    all_time_query = {"query_id": "valid-at-none", "valid_at": None, "context": {}}
    context_query = {
        "query_id": "tuesday-noon",
        "valid_at": "2026-04-07T12:00:00Z",
        "context": {"occurrence": "2026-04-07"},
    }
    context_all_time = {
        "query_id": "valid-at-none",
        "valid_at": None,
        "context": {"occurrence": "2026-04-07"},
    }

    return [
        FixtureSpec(
            "H1-EQ",
            eq_ops,
            ("E0-raw-equality", "E1-folded-equality"),
            ({"query_id": "fixed", "valid_at": None, "context": {}},),
        ),
        FixtureSpec(
            "H1-REF",
            ref_ops,
            ("R0-raw-ref", "R1-folded-ref"),
            ({"query_id": "fixed", "valid_at": None, "context": {}},),
        ),
        FixtureSpec(
            "H1-DET",
            detector_ops,
            ("D1-budget-v1-ab", "D2-budget-v1-abc", "D2-budget-v2-abc"),
            ({"query_id": "fixed", "valid_at": None, "context": {}},),
        ),
        FixtureSpec(
            "H2-NONE",
            (monday, tuesday()),
            ("H2-identity",),
            (tuesday_query, all_time_query),
        ),
        FixtureSpec(
            "H2-ID",
            (monday, tuesday(), exact_retraction),
            ("H2-identity",),
            (tuesday_query, all_time_query),
        ),
        FixtureSpec(
            "H2-REF",
            (monday, tuesday(), semantic_retraction),
            ("H2-identity",),
            (tuesday_query, all_time_query),
        ),
        FixtureSpec(
            "H2-CTX",
            (
                monday,
                tuesday(context={"occurrence": "2026-04-07"}),
                semantic_retraction,
            ),
            ("H2-identity",),
            (context_query, context_all_time),
        ),
        FixtureSpec(
            "H2-VALUE",
            (monday, tuesday(value="open-again"), semantic_retraction),
            ("H2-identity",),
            (tuesday_query, all_time_query),
        ),
    ]


def operation_set(ops: Sequence[Any]) -> tuple[list[str], str]:
    op_json = sorted(op.to_json() for op in ops)
    payload = ("\n".join(op_json) + "\n").encode("utf-8")
    return op_json, hashlib.sha256(payload).hexdigest()


def contract_descriptors(
    contracts: dict[str, ContractSpec], runner_sha256: str
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for contract_id in sorted(contracts):
        contract = contracts[contract_id]
        base = {
            "contract_id": contract.contract_id,
            "description": contract.description,
            "implementation_source": "audit.py",
            "implementation_source_sha256": runner_sha256,
            "model_free": True,
            "parameters": contract.parameters,
            "pure": True,
        }
        base["descriptor_sha256"] = digest_value(base)
        rows.append(base)
    return {
        "contract_count": len(rows),
        "contracts": rows,
        "network_access": "blocked during synthetic runs",
        "resolver": {
            "class": "ConservativeHeuristicResolver",
            "confidence_margin": 0.05,
            "evidence_count_margin": 1,
            "time_margin_seconds": 300.0,
        },
    }


def execute_fixtures(
    api: SimpleNamespace,
    fixtures: Sequence[FixtureSpec],
    contracts: dict[str, ContractSpec],
    descriptors: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    descriptor_by_id = {
        row["contract_id"]: row for row in descriptors["contracts"]
    }
    cases: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    resolver = api.ConservativeHeuristicResolver(
        confidence_margin=0.05,
        time_margin_seconds=300.0,
        evidence_count_margin=1,
    )

    with blocked_network():
        for fixture in fixtures:
            op_json, opset_sha256 = operation_set(fixture.ops)
            permutations = list(itertools.permutations(fixture.ops))
            cases.append(
                {
                    "contract_ids": list(fixture.contract_ids),
                    "fixture_id": fixture.fixture_id,
                    "op_count": len(fixture.ops),
                    "operation_json": op_json,
                    "opset_sha256": opset_sha256,
                    "permutation_count": len(permutations),
                    "queries": list(fixture.queries),
                }
            )
            for contract_id in fixture.contract_ids:
                contract = contracts[contract_id]
                registry = contract.registry_factory()
                registry.validate_contracts(contract.samples_by_predicate, repeats=3)
                detectors = contract.detector_factory()
                for query in fixture.queries:
                    for permutation_index, permutation in enumerate(permutations):
                        state = api.materialize(
                            api.OpLog(permutation),
                            registry,
                            conflict_detectors=detectors,
                            valid_at=query["valid_at"],
                            context=query["context"],
                        )
                        projection = api.build_view(
                            state,
                            api.ViewConstraints(
                                valid_at=query["valid_at"],
                                context=query["context"],
                            ),
                            resolver=resolver,
                        )
                        state_payload = snapshot_state(state)
                        projection_payload = snapshot_projection(projection)
                        results.append(
                            {
                                "contract_id": contract_id,
                                "contract_sha256": descriptor_by_id[contract_id][
                                    "descriptor_sha256"
                                ],
                                "fixture_id": fixture.fixture_id,
                                "opset_sha256": opset_sha256,
                                "permutation_index": permutation_index,
                                "projection": projection_payload,
                                "projection_sha256": digest_value(projection_payload),
                                "query": query,
                                "state": state_payload,
                                "state_sha256": digest_value(state_payload),
                                "submitted_op_ids": [op.op_id for op in permutation],
                            }
                        )
    return cases, results


def first_result(
    results: Sequence[dict[str, Any]], fixture_id: str, contract_id: str, query_id: str
) -> dict[str, Any]:
    return next(
        row
        for row in results
        if row["fixture_id"] == fixture_id
        and row["contract_id"] == contract_id
        and row["query"]["query_id"] == query_id
        and row["permutation_index"] == 0
    )


def status_for(state: dict[str, Any], conflict_ref: str) -> str | None:
    for row in state["lifecycle_statuses"]:
        if row["conflict_ref"] == conflict_ref and row["scope"] is None:
            return row["status"]
    return None


def selected_ids(projection: dict[str, Any]) -> list[str]:
    return sorted(
        item["claim_id"] for item in projection["selected_claims_by_key"].values()
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def validate_contract_descriptors(
    descriptors: dict[str, Any], runner_sha256: str
) -> dict[str, dict[str, Any]]:
    rows = descriptors.get("contracts")
    require(isinstance(rows, list), "contract descriptor rows are missing")
    require(descriptors.get("contract_count") == len(EXPECTED_CONTRACT_PARAMETERS), "contract count changed")
    by_id = {row["contract_id"]: row for row in rows}
    require(len(by_id) == len(rows), "duplicate contract descriptor")
    require(set(by_id) == set(EXPECTED_CONTRACT_PARAMETERS), "contract descriptor matrix changed")
    for contract_id, expected_parameters in EXPECTED_CONTRACT_PARAMETERS.items():
        row = by_id[contract_id]
        require(row["parameters"] == expected_parameters, f"contract parameters changed: {contract_id}")
        require(row["implementation_source"] == "audit.py", f"contract source changed: {contract_id}")
        require(
            row["implementation_source_sha256"] == runner_sha256,
            f"contract runner binding changed: {contract_id}",
        )
        require(row["model_free"] is True, f"contract is not model-free: {contract_id}")
        require(row["pure"] is True, f"contract purity declaration changed: {contract_id}")
        unsigned = {key: value for key, value in row.items() if key != "descriptor_sha256"}
        require(
            row["descriptor_sha256"] == digest_value(unsigned),
            f"contract descriptor digest changed: {contract_id}",
        )
    require(descriptors.get("network_access") == "blocked during synthetic runs", "network contract changed")
    require(
        descriptors.get("resolver")
        == {
            "class": "ConservativeHeuristicResolver",
            "confidence_margin": 0.05,
            "evidence_count_margin": 1,
            "time_margin_seconds": 300.0,
        },
        "resolver contract changed",
    )
    return by_id


def validate_execution_contract(
    cases: Sequence[dict[str, Any]],
    results: Sequence[dict[str, Any]],
    descriptors: dict[str, Any],
    runner_sha256: str,
) -> dict[str, Any]:
    require(len(cases) == EXPECTED_CASE_COUNT, "unexpected fixture count")
    require(len(results) == EXPECTED_RESULT_COUNT, "unexpected synthetic result count")
    descriptor_by_id = validate_contract_descriptors(descriptors, runner_sha256)

    case_by_id = {case["fixture_id"]: case for case in cases}
    require(len(case_by_id) == len(cases), "duplicate fixture descriptor")
    require(set(case_by_id) == set(EXPECTED_CASES), "fixture matrix changed")

    expected_groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for fixture_id, expected in EXPECTED_CASES.items():
        case = case_by_id[fixture_id]
        require(tuple(case["contract_ids"]) == expected["contract_ids"], f"contract set changed: {fixture_id}")
        require(case["op_count"] == expected["op_count"], f"operation count changed: {fixture_id}")
        require(
            case["permutation_count"] == expected["permutation_count"] == math.factorial(case["op_count"]),
            f"permutation count changed: {fixture_id}",
        )
        require(tuple(case["queries"]) == expected["queries"], f"query contract changed: {fixture_id}")
        operation_json = case["operation_json"]
        require(operation_json == sorted(operation_json), f"operation JSON is not canonical: {fixture_id}")
        require(len(operation_json) == case["op_count"], f"operation JSON count changed: {fixture_id}")
        operations = [json.loads(payload) for payload in operation_json]
        op_ids = [operation["op_id"] for operation in operations]
        require(len(op_ids) == len(set(op_ids)), f"duplicate fixture operation ID: {fixture_id}")
        require(tuple(sorted(op_ids)) == expected["op_ids"], f"fixture operation IDs changed: {fixture_id}")
        expected_opset = hashlib.sha256(("\n".join(operation_json) + "\n").encode("utf-8")).hexdigest()
        require(case["opset_sha256"] == expected_opset, f"OpSet digest changed: {fixture_id}")
        require(expected_opset == expected["opset_sha256"], f"fixture operation bytes changed: {fixture_id}")
        query_by_id = {query["query_id"]: query for query in case["queries"]}
        require(len(query_by_id) == len(case["queries"]), f"duplicate query ID: {fixture_id}")
        for contract_id in case["contract_ids"]:
            require(contract_id in descriptor_by_id, f"unknown contract: {contract_id}")
            for query_id, query in query_by_id.items():
                expected_groups[(fixture_id, contract_id, query_id)] = {
                    "contract_sha256": descriptor_by_id[contract_id]["descriptor_sha256"],
                    "op_ids": tuple(sorted(op_ids)),
                    "opset_sha256": expected_opset,
                    "permutation_count": case["permutation_count"],
                    "query": query,
                }

    require(len(expected_groups) == EXPECTED_GROUP_COUNT, "unexpected permutation-group matrix")
    require(
        sum(group["permutation_count"] for group in expected_groups.values())
        == EXPECTED_RESULT_COUNT,
        "group matrix does not account for every result row",
    )

    grouped: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        require(isinstance(row.get("query"), dict), "result query is missing")
        key = (row["fixture_id"], row["contract_id"], row["query"]["query_id"])
        grouped[key].append(row)
    require(set(grouped) == set(expected_groups), "observed permutation-group matrix changed")

    permutation_groups: list[dict[str, Any]] = []
    for key in sorted(expected_groups):
        expected = expected_groups[key]
        rows = sorted(grouped[key], key=lambda row: row["permutation_index"])
        count = expected["permutation_count"]
        require(len(rows) == count, f"incomplete permutation group: {key}")
        require(
            [row["permutation_index"] for row in rows] == list(range(count)),
            f"permutation index coverage changed: {key}",
        )
        submitted_orders: set[tuple[str, ...]] = set()
        for row in rows:
            require(row["query"] == expected["query"], f"query payload changed: {key}")
            require(row["opset_sha256"] == expected["opset_sha256"], f"result OpSet changed: {key}")
            require(
                row["contract_sha256"] == expected["contract_sha256"],
                f"result contract binding changed: {key}",
            )
            submitted = tuple(row["submitted_op_ids"])
            require(tuple(sorted(submitted)) == expected["op_ids"], f"submitted operation set changed: {key}")
            submitted_orders.add(submitted)
            require(row["state"].get("schema") == STATE_SNAPSHOT_SCHEMA, f"state schema changed: {key}")
            require(
                row["projection"].get("schema") == PROJECTION_SNAPSHOT_SCHEMA,
                f"projection schema changed: {key}",
            )
            require(row["state_sha256"] == digest_value(row["state"]), f"state digest mismatch: {key}")
            require(
                row["projection_sha256"] == digest_value(row["projection"]),
                f"projection digest mismatch: {key}",
            )
        require(len(submitted_orders) == count, f"submitted permutations are incomplete: {key}")
        state_digests = {row["state_sha256"] for row in rows}
        projection_digests = {row["projection_sha256"] for row in rows}
        require(len(state_digests) == 1, f"same-contract state diverged: {key}")
        require(len(projection_digests) == 1, f"same-contract projection diverged: {key}")
        permutation_groups.append(
            {
                "contract_id": key[1],
                "fixture_id": key[0],
                "permutation_count": count,
                "projection_digest_count": 1,
                "query_id": key[2],
                "state_digest_count": 1,
            }
        )

    return {
        "exact_case_matrix": True,
        "exact_group_matrix": True,
        "expected_case_count": EXPECTED_CASE_COUNT,
        "expected_group_count": EXPECTED_GROUP_COUNT,
        "expected_result_count": EXPECTED_RESULT_COUNT,
        "fixture_bindings_verified": True,
        "payload_digests_recomputed": True,
        "permutation_coverage_verified": True,
        "permutation_groups": permutation_groups,
        "supported": True,
    }


def h2_observation_matches(
    row: dict[str, Any],
    *,
    active_ids: list[str],
    inactive_ids: list[str],
    inapplicable_ids: list[str],
    selected: list[str],
) -> bool:
    state = row["state"]
    expected_active = {"synthetic:shop:state": active_ids} if active_ids else {}
    return (
        state["active_claim_ids_by_key"] == expected_active
        and state["inactive_claim_ids"] == inactive_ids
        and state["inapplicable_claim_ids"] == inapplicable_ids
        and state["conflicts"] == []
        and selected_ids(row["projection"]) == selected
        and row["projection"]["unresolved_conflict_ids"] == []
        and row["projection"]["surfaced_finding_ids"] == []
    )


def derive_decision(
    cases: Sequence[dict[str, Any]],
    results: Sequence[dict[str, Any]],
    pytest_receipt: dict[str, Any],
    descriptors: dict[str, Any],
    runner_sha256: str,
) -> dict[str, Any]:
    execution_contract = validate_execution_contract(
        cases, results, descriptors, runner_sha256
    )

    e0 = first_result(results, "H1-EQ", "E0-raw-equality", "fixed")
    e1 = first_result(results, "H1-EQ", "E1-folded-equality", "fixed")
    e0_conflicts = e0["state"]["conflicts"]
    e1_conflicts = e1["state"]["conflicts"]
    eq_active = {"synthetic:shop:state": ["h1-eq-lower", "h1-eq-upper"]}
    h1_eq_supported = (
        e0["state"]["active_claim_ids_by_key"]
        == e1["state"]["active_claim_ids_by_key"]
        == eq_active
        and e0["state"]["claim_refs_by_id"] == e1["state"]["claim_refs_by_id"]
        and e0["state"]["inactive_claim_ids"] == e1["state"]["inactive_claim_ids"] == []
        and e0["state"]["inapplicable_claim_ids"] == e1["state"]["inapplicable_claim_ids"] == []
        and len(e0_conflicts) == 1
        and len(e1_conflicts) == 0
        and e0_conflicts[0]["candidate_ids"] == ["h1-eq-lower", "h1-eq-upper"]
        and e0_conflicts[0]["detector_id"] == "direct"
        and e0_conflicts[0]["conflict_type"] == "same_key_distinct_value"
        and selected_ids(e0["projection"]) == []
        and e0["projection"]["unresolved_conflict_ids"] == [e0_conflicts[0]["conflict_id"]]
        and selected_ids(e1["projection"]) == ["h1-eq-upper"]
        and e1["projection"]["unresolved_conflict_ids"] == []
    )

    r0 = first_result(results, "H1-REF", "R0-raw-ref", "fixed")
    r1 = first_result(results, "H1-REF", "R1-folded-ref", "fixed")
    r0_refs = r0["state"]["claim_refs_by_id"]
    r1_refs = r1["state"]["claim_refs_by_id"]
    h1_ref_supported = (
        len(r0["state"]["conflicts"]) == len(r1["state"]["conflicts"]) == 0
        and r0_refs["h1-ref-upper"] != r0_refs["h1-ref-lower"]
        and r1_refs["h1-ref-upper"] == r1_refs["h1-ref-lower"]
        and r0["state"]["inactive_claim_ids"] == ["h1-ref-lower"]
        and r1["state"]["inactive_claim_ids"]
        == ["h1-ref-lower", "h1-ref-upper"]
        and r0["state"]["active_claim_ids_by_key"]
        == {"synthetic:shop:state": ["h1-ref-upper"]}
        and r1["state"]["active_claim_ids_by_key"] == {}
        and r0["state"]["inapplicable_claim_ids"] == r1["state"]["inapplicable_claim_ids"] == []
        and r0["state"]["retracted_claim_refs"] == [r0_refs["h1-ref-lower"]]
        and r1["state"]["retracted_claim_refs"] == [r1_refs["h1-ref-lower"]]
        and selected_ids(r0["projection"]) == ["h1-ref-upper"]
        and selected_ids(r1["projection"]) == []
        and r0["projection"]["unresolved_conflict_ids"]
        == r1["projection"]["unresolved_conflict_ids"]
        == []
    )

    d1 = first_result(results, "H1-DET", "D1-budget-v1-ab", "fixed")
    d2 = first_result(results, "H1-DET", "D2-budget-v1-abc", "fixed")
    d2v2 = first_result(results, "H1-DET", "D2-budget-v2-abc", "fixed")
    d1_conflict = d1["state"]["conflicts"][0]
    d2_conflict = d2["state"]["conflicts"][0]
    d2v2_conflict = d2v2["state"]["conflicts"][0]
    d1_lane = {
        "conflict_ref": d1_conflict["conflict_ref"],
        "resolution_id": "h1-det-resolution",
        "scope": None,
    }
    d1_record = d1["state"]["resolution_records"]
    h1_det_supported = (
        d1_conflict["conflict_ref"] == d2_conflict["conflict_ref"]
        and d1_conflict["conflict_id"] != d2_conflict["conflict_id"]
        and d1_conflict["detector_id"] == d2_conflict["detector_id"] == "budget/v1"
        and d1_conflict["candidate_ids"]
        == ["h1-det-capacity", "h1-det-cost-a", "h1-det-cost-b"]
        and d2_conflict["candidate_ids"]
        == ["h1-det-capacity", "h1-det-cost-a", "h1-det-cost-b", "h1-det-cost-c"]
        and d1_conflict["witness"]["cost_claim_ids"] == ["h1-det-cost-a", "h1-det-cost-b"]
        and d2_conflict["witness"]["cost_claim_ids"]
        == ["h1-det-cost-a", "h1-det-cost-b", "h1-det-cost-c"]
        and len(d1_record) == 1
        and d1_record[0]["resolution_id"] == "h1-det-resolution"
        and d1_record[0]["observed_conflict_id"] == d1_conflict["conflict_id"]
        and d1_record[0]["selected_claim_ids"] == ["h1-det-capacity"]
        and d1_record[0]["rejected_claim_ids"] == ["h1-det-cost-a", "h1-det-cost-b"]
        and d1["state"]["active_resolutions"] == d2["state"]["active_resolutions"] == [d1_lane]
        and d1["state"]["effective_resolutions"] == [d1_lane]
        and d2["state"]["effective_resolutions"] == []
        and status_for(d1["state"], d1_conflict["conflict_ref"]) == "resolved"
        and status_for(d2["state"], d2_conflict["conflict_ref"]) == "reopened"
        and d1["projection"]["unresolved_conflict_ids"] == []
        and d2["projection"]["unresolved_conflict_ids"] == [d2_conflict["conflict_id"]]
        and selected_ids(d2["projection"]) == ["h1-det-capacity"]
        and d2["projection"]["compatible_claim_ids_by_key"]
        == {"synthetic:budget:cost": ["h1-det-cost-a", "h1-det-cost-b", "h1-det-cost-c"]}
        and any(
            "uncovered candidates: h1-det-cost-c" in explanation
            for explanation in d2["projection"]["explanations"].values()
        )
    )
    c_promotion_observed = (
        d1["projection"]["selected_claims_by_key"].get("synthetic:budget:cost", {}).get("claim_id")
        == "h1-det-cost-c"
        and "synthetic:budget:cost" not in d1["projection"]["compatible_claim_ids_by_key"]
    )
    h1_vid_control_supported = (
        d2v2_conflict["detector_id"] == "budget/v2"
        and d2v2_conflict["conflict_ref"] != d2_conflict["conflict_ref"]
        and d2v2_conflict["candidate_ids"] == d2_conflict["candidate_ids"]
        and d2v2["state"]["active_resolutions"] == [d1_lane]
        and d2v2["state"]["effective_resolutions"] == []
        and status_for(d2v2["state"], d1_conflict["conflict_ref"]) == "resolved"
        and status_for(d2v2["state"], d2v2_conflict["conflict_ref"]) == "open"
        and d2v2["projection"]["unresolved_conflict_ids"]
        == [d2v2_conflict["conflict_id"]]
        and selected_ids(d2v2["projection"]) == ["h1-det-capacity"]
    )

    h1_opset_pairs = {
        "H1-EQ": {e0["opset_sha256"], e1["opset_sha256"]},
        "H1-REF": {r0["opset_sha256"], r1["opset_sha256"]},
        "H1-DET": {
            d1["opset_sha256"],
            d2["opset_sha256"],
            d2v2["opset_sha256"],
        },
    }
    identical_ops_across_h1_pairs = all(len(values) == 1 for values in h1_opset_pairs.values())

    h2_rows = {
        (fixture_id, query_id): first_result(results, fixture_id, "H2-identity", query_id)
        for fixture_id in ("H2-NONE", "H2-ID", "H2-REF", "H2-CTX", "H2-VALUE")
        for query_id in ("tuesday-noon", "valid-at-none")
    }
    h2_none = h2_rows[("H2-NONE", "tuesday-noon")]
    h2_id = h2_rows[("H2-ID", "tuesday-noon")]
    h2_ref = h2_rows[("H2-REF", "tuesday-noon")]
    h2_ctx = h2_rows[("H2-CTX", "tuesday-noon")]
    h2_value = h2_rows[("H2-VALUE", "tuesday-noon")]
    h2_ref_all_time = h2_rows[("H2-REF", "valid-at-none")]
    h2_none_refs = h2_none["state"]["claim_refs_by_id"]
    h2_id_refs = h2_id["state"]["claim_refs_by_id"]
    h2_ref_refs = h2_ref["state"]["claim_refs_by_id"]
    h2_ctx_refs = h2_ctx["state"]["claim_refs_by_id"]
    h2_value_refs = h2_value["state"]["claim_refs_by_id"]
    h2_supported = (
        h2_none_refs["h2-monday"] == h2_none_refs["h2-tuesday"]
        and h2_id_refs["h2-monday"] == h2_id_refs["h2-tuesday"]
        and h2_ref_refs["h2-monday"] == h2_ref_refs["h2-tuesday"]
        and h2_ctx_refs["h2-monday"] != h2_ctx_refs["h2-tuesday"]
        and h2_value_refs["h2-monday"] != h2_value_refs["h2-tuesday"]
        and h2_none["state"]["retracted_claim_ids"] == []
        and h2_none["state"]["retracted_claim_refs"] == []
        and h2_id["state"]["retracted_claim_ids"] == ["h2-monday"]
        and h2_id["state"]["retracted_claim_refs"] == []
        and h2_ref["state"]["retracted_claim_refs"] == [h2_ref_refs["h2-monday"]]
        and h2_ctx["state"]["retracted_claim_refs"] == [h2_ctx_refs["h2-monday"]]
        and h2_value["state"]["retracted_claim_refs"] == [h2_value_refs["h2-monday"]]
        and h2_observation_matches(
            h2_none,
            active_ids=["h2-tuesday"],
            inactive_ids=[],
            inapplicable_ids=["h2-monday"],
            selected=["h2-tuesday"],
        )
        and h2_observation_matches(
            h2_id,
            active_ids=["h2-tuesday"],
            inactive_ids=["h2-monday"],
            inapplicable_ids=[],
            selected=["h2-tuesday"],
        )
        and h2_observation_matches(
            h2_ref,
            active_ids=[],
            inactive_ids=["h2-monday", "h2-tuesday"],
            inapplicable_ids=[],
            selected=[],
        )
        and h2_observation_matches(
            h2_ctx,
            active_ids=["h2-tuesday"],
            inactive_ids=["h2-monday"],
            inapplicable_ids=[],
            selected=["h2-tuesday"],
        )
        and h2_observation_matches(
            h2_value,
            active_ids=["h2-tuesday"],
            inactive_ids=["h2-monday"],
            inapplicable_ids=[],
            selected=["h2-tuesday"],
        )
        and h2_observation_matches(
            h2_rows[("H2-NONE", "valid-at-none")],
            active_ids=["h2-monday", "h2-tuesday"],
            inactive_ids=[],
            inapplicable_ids=[],
            selected=["h2-tuesday"],
        )
        and h2_observation_matches(
            h2_rows[("H2-ID", "valid-at-none")],
            active_ids=["h2-tuesday"],
            inactive_ids=["h2-monday"],
            inapplicable_ids=[],
            selected=["h2-tuesday"],
        )
        and h2_observation_matches(
            h2_ref_all_time,
            active_ids=[],
            inactive_ids=["h2-monday", "h2-tuesday"],
            inapplicable_ids=[],
            selected=[],
        )
        and h2_observation_matches(
            h2_rows[("H2-CTX", "valid-at-none")],
            active_ids=["h2-tuesday"],
            inactive_ids=["h2-monday"],
            inapplicable_ids=[],
            selected=["h2-tuesday"],
        )
        and h2_observation_matches(
            h2_rows[("H2-VALUE", "valid-at-none")],
            active_ids=["h2-tuesday"],
            inactive_ids=["h2-monday"],
            inapplicable_ids=[],
            selected=["h2-tuesday"],
        )
    )

    h1_supported = (
        execution_contract["supported"]
        and identical_ops_across_h1_pairs
        and h1_eq_supported
        and h1_ref_supported
        and h1_det_supported
        and h1_vid_control_supported
    )
    primary_probe_supported = (
        pytest_receipt["status"] == "passed"
        and execution_contract["supported"]
        and h1_supported
        and h2_supported
    )
    return {
        "artifact_status": "primary_probe_supported_pending_fresh_reproduction",
        "case_count": len(cases),
        "evidence_labels": {
            "local_pytest": "official-source execution receipt",
            "paper": "paper-reported",
            "probe": "synthetic contract test",
            "source": "official-source",
            "workshop": "official-source / unpublished_repository_manuscript",
        },
        "h1": {
            "c_promotion_decision_gate": False,
            "c_promotion_observed_post_test": c_promotion_observed,
            "detector_lifecycle_supported": h1_det_supported,
            "equality_supported": h1_eq_supported,
            "headline": "interpretation-contract binding",
            "identical_ops_across_contract_pairs": identical_ops_across_h1_pairs,
            "ref_normalization_supported": h1_ref_supported,
            "supported": h1_supported,
            "versioned_detector_control_supported": h1_vid_control_supported,
        },
        "h2": {
            "mechanism": "semantic-ref tombstone carryover",
            "question": "semantic-reference recurrence scope",
            "supported": h2_supported,
        },
        "interpretation_boundary": {
            "benchmark_reproduction": False,
            "crdt_merge_law_failure": False,
            "model_evaluation": False,
            "production_frequency_or_harm_estimate": False,
            "security_vulnerability": False,
            "semantic_ref_behavior_labeled_bug": False,
        },
        "execution_contract": execution_contract,
        "official_suite": pytest_receipt,
        "permutation_group_count": len(execution_contract["permutation_groups"]),
        "permutation_groups": execution_contract["permutation_groups"],
        "permutation_integrity_passed": execution_contract["supported"],
        "primary_probe_supported": primary_probe_supported,
        "run_result_count": len(results),
        "strongest_claim_level": (
            "preregistered_synthetic_interpretation_contract_and_recurrence_consequences"
            if primary_probe_supported
            else "narrow_or_hold"
        ),
    }


def build_source_manifest(source_root: Path, paper_pdf: Path, runner_sha256: str) -> dict[str, Any]:
    observed_files: dict[str, Any] = {}
    for relative, expected in sorted(EXPECTED_SOURCE_FILES.items()):
        path = source_root / relative
        require(path.is_file(), f"missing locked source file: {relative}")
        observed = {
            "git_blob": git_output(source_root, "rev-parse", f"HEAD:{relative}"),
            "sha256": sha256_path(path),
        }
        require(observed == expected, f"locked source identity mismatch: {relative}")
        observed_files[relative] = observed
    with (source_root / "pyproject.toml").open("rb") as handle:
        declared_version = tomllib.load(handle).get("project", {}).get("version")
    require(declared_version == EXPECTED_VERSION, "package version mismatch")
    require(sha256_path(paper_pdf) == EXPECTED_PAPER_SHA256, "paper PDF hash mismatch")
    return {
        "ams_audit": {
            "base_commit": AMS_BASE_COMMIT,
            "runner": "audit.py",
            "runner_sha256": runner_sha256,
        },
        "arxiv_paper": {
            "identifier": PAPER_ID,
            "reviewed_pdf_sha256": EXPECTED_PAPER_SHA256,
            "url": PAPER_URL,
        },
        "official_source": {
            "commit": EXPECTED_COMMIT,
            "files": observed_files,
            "package_version": declared_version,
            "package_version_verified_from": "pyproject.toml:project.version",
            "repository": SOURCE_URL,
        },
        "out_of_scope": [
            "PM-Bench audit results and artifacts",
            "StateFuse paper benchmark/model experiments",
            "live connectors and service credentials",
        ],
        "retrieval_date": "2026-08-23",
        "workshop_manuscript": {
            "git_blob": EXPECTED_SOURCE_FILES["paper/main.tex"]["git_blob"],
            "path": "paper/main.tex",
            "sha256": EXPECTED_SOURCE_FILES["paper/main.tex"]["sha256"],
            "status": "unpublished_repository_manuscript",
            "title": EXPECTED_SUCCESSOR_MANUSCRIPT_TITLE,
        },
    }


def environment_receipt(pytest_receipt: dict[str, Any]) -> dict[str, Any]:
    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.splitlines()
    return {
        "architecture": platform.machine(),
        "dependency_receipt": sorted(freeze),
        "locale": locale.setlocale(locale.LC_ALL, None),
        "network": "socket-blocked for every custom registry/detector invocation; no network used by synthetic runner",
        "operating_system": platform.system(),
        "platform": platform.platform(),
        "pytest": pytest_receipt,
        "pytest_version": package_version("pytest"),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "receipt_normalization": (
            "Python subprocess text mode performs universal-newline decoding; only elapsed-time "
            "tokens on pytest summary lines are replaced with <elapsed>; terminal whitespace and "
            "all other stdout/stderr text are retained"
        ),
        "statefuse_import": "reader-supplied exact checkout via PYTHONPATH; package not copied or installed",
        "timezone": os.environ.get("TZ", ""),
    }


def results_text(decision: dict[str, Any], readiness: dict[str, Any]) -> str:
    return (
        "StateFuse interpretation-contract audit\n\n"
        f"Official suite: {decision['official_suite']['passed_count']} passed; "
        f"{decision['official_suite']['skipped_count']} skipped\n"
        f"Synthetic result rows: {decision['run_result_count']}\n"
        f"Fixed-contract constructor-permutation groups: {decision['permutation_group_count']}\n"
        f"Exact execution contract: {decision['execution_contract']['supported']}\n"
        f"Insertion-order/canonicalization integrity: {decision['permutation_integrity_passed']}\n"
        f"H1 equality stratum: {decision['h1']['equality_supported']}\n"
        f"H1 semantic-handle stratum: {decision['h1']['ref_normalization_supported']}\n"
        f"H1 detector/lifecycle stratum: {decision['h1']['detector_lifecycle_supported']}\n"
        f"H1 declared-version control: {decision['h1']['versioned_detector_control_supported']}\n"
        f"H1 interpretation-contract binding: {decision['h1']['supported']}\n"
        f"H2 semantic-ref tombstone carryover: {decision['h2']['supported']}\n"
        f"Fresh byte reproduction: {readiness['criteria']['fresh_byte_reproduction']}\n"
        f"Local audit complete: {readiness['integration_readiness_passed']}\n"
        f"Integration evidence ready: {readiness['integration_readiness_passed']}\n"
        "AMS essay, note depth, and canonical integration: not determined by this evidence artifact\n"
        "Commit, push, publication, and deployment: not performed\n"
        "Boundary: synthetic contract test, not paper/benchmark/model reproduction, "
        "CRDT-law failure, vulnerability, production estimate, or bug claim.\n"
    )


def artifact_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in FORBIDDEN_NAMES for part in relative.parts):
            raise RuntimeError(f"forbidden artifact residue: {relative.as_posix()}")
        if not path.is_file() or path.name == "checksums.sha256":
            continue
        require(path.suffix.lower() in PUBLIC_SUFFIXES, f"unexpected artifact type: {relative}")
        require(path.suffix.lower() not in FORBIDDEN_SUFFIXES, f"forbidden residue: {relative}")
        files.append(path)
    return files


def write_checksums(root: Path) -> None:
    with (root / "checksums.sha256").open("w", encoding="utf-8") as handle:
        for path in artifact_files(root):
            handle.write(f"{sha256_path(path)}  {path.relative_to(root).as_posix()}\n")


def verify_manifest(root: Path) -> None:
    manifest = root / "checksums.sha256"
    require(manifest.is_file(), f"missing checksum manifest: {manifest}")
    expected_files = {path.relative_to(root).as_posix() for path in artifact_files(root)}
    listed: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        require(relative not in listed, f"duplicate checksum entry: {relative}")
        listed[relative] = expected
    require(set(listed) == expected_files, "checksum file set is incomplete or contains residue")
    for relative, expected in listed.items():
        require(sha256_path(root / relative) == expected, f"checksum mismatch: {relative}")


def validate_source_manifest_payload(
    manifest: dict[str, Any], runner_sha256: str
) -> None:
    require(
        manifest.get("ams_audit")
        == {
            "base_commit": AMS_BASE_COMMIT,
            "runner": "audit.py",
            "runner_sha256": runner_sha256,
        },
        "AMS runner source binding changed",
    )
    require(
        manifest.get("arxiv_paper")
        == {
            "identifier": PAPER_ID,
            "reviewed_pdf_sha256": EXPECTED_PAPER_SHA256,
            "url": PAPER_URL,
        },
        "paper source binding changed",
    )
    official = manifest.get("official_source", {})
    require(official.get("commit") == EXPECTED_COMMIT, "official source commit changed")
    require(official.get("repository") == SOURCE_URL, "official source repository changed")
    require(official.get("files") == EXPECTED_SOURCE_FILES, "official source file bindings changed")
    require(official.get("package_version") == EXPECTED_VERSION, "package version receipt changed")
    require(
        official.get("package_version_verified_from") == "pyproject.toml:project.version",
        "package version verification receipt changed",
    )
    require(
        manifest.get("workshop_manuscript")
        == {
            "git_blob": EXPECTED_SOURCE_FILES["paper/main.tex"]["git_blob"],
            "path": "paper/main.tex",
            "sha256": EXPECTED_SOURCE_FILES["paper/main.tex"]["sha256"],
            "status": "unpublished_repository_manuscript",
            "title": EXPECTED_SUCCESSOR_MANUSCRIPT_TITLE,
        },
        "workshop manuscript identity changed",
    )


def parse_pytest_receipt(root: Path) -> dict[str, Any]:
    expected_commands = {
        "collect": ["<PYTHON>", "-m", "pytest", "--collect-only", "-q"],
        "run": ["<PYTHON>", "-m", "pytest", "-q", "-ra"],
    }
    stdout_by_name: dict[str, str] = {}
    for name, command in expected_commands.items():
        text = (root / f"raw/pytest_{name}.txt").read_text(encoding="utf-8")
        header = (
            f"command: {' '.join(command)}\n"
            "working_directory: <SOURCE_REPO>\n"
            "exit_code: 0\n"
            "elapsed_time: normalized_as_non_semantic_receipt_metadata\n"
            "stdout:\n"
        )
        require(text.startswith(header), f"pytest {name} receipt header changed")
        require("\nstderr:\n" in text, f"pytest {name} receipt stderr boundary missing")
        stdout, stderr = text[len(header) :].rsplit("\nstderr:\n", 1)
        require(stderr == "", f"pytest {name} stderr is not empty")
        stdout_by_name[name] = stdout + "\n"

    node_ids = [
        line
        for line in stdout_by_name["collect"].splitlines()
        if line.startswith("tests/") and "::" in line
    ]
    require(len(node_ids) == EXPECTED_PYTEST_COUNT, "checked pytest node count changed")
    require(len(node_ids) == len(set(node_ids)), "checked pytest node IDs are duplicated")
    require(
        re.search(rf"\b{EXPECTED_PYTEST_COUNT} tests collected in <elapsed>s\b", stdout_by_name["collect"])
        is not None,
        "checked pytest collection summary changed",
    )
    require(
        re.search(rf"\b{EXPECTED_PYTEST_COUNT} passed in <elapsed>s\b", stdout_by_name["run"])
        is not None,
        "checked pytest run summary changed",
    )
    require(" skipped" not in stdout_by_name["run"], "checked pytest receipt contains skips")
    return {
        "collect_command": expected_commands["collect"],
        "collected_node_count": EXPECTED_PYTEST_COUNT,
        "run_command": expected_commands["run"],
        "passed_count": EXPECTED_PYTEST_COUNT,
        "skipped_count": 0,
        "status": "passed",
    }


def build_reproduction_receipt(primary_root: Path, repeat_root: Path) -> dict[str, Any]:
    matched: dict[str, str] = {}
    for relative in sorted(PRIMARY_RELATIVE_PATHS):
        primary = primary_root / relative
        repeated = repeat_root / relative
        require(primary.is_file() and repeated.is_file(), f"reproduction file missing: {relative}")
        require(primary.read_bytes() == repeated.read_bytes(), f"fresh repeat differs: {relative}")
        matched[relative] = sha256_path(primary)
    return {
        "comparison": "byte-for-byte",
        "comparison_emitted_by": "audit.py after an internal fresh second pass; any mismatch aborts the run",
        "determinism_class": "same-environment deterministic repeatability",
        "generated_files": matched,
        "matched_file_count": len(matched),
        "method": (
            "One runner invocation executed two complete passes in distinct output roots. Each pass "
            "rechecked the locked source and paper, reran both upstream pytest commands, rebuilt every "
            "fixture/contract/query/permutation, rederived the decision from raw payloads, and serialized "
            "the complete primary output set before byte comparison."
        ),
        "receipt_normalization": (
            "Python subprocess text mode performs universal-newline decoding; only elapsed-time tokens "
            "on pytest summary lines are replaced with <elapsed>; terminal whitespace and all other "
            "stdout/stderr text are retained"
        ),
        "schema": "statefuse-reproduction/2",
        "verdict": "REPRODUCIBLE",
    }


def derive_readiness(
    decision: dict[str, Any],
    reproduction: dict[str, Any],
    source_manifest: dict[str, Any],
) -> dict[str, Any]:
    source_lock = (
        source_manifest["official_source"]["commit"] == EXPECTED_COMMIT
        and source_manifest["official_source"]["package_version"] == EXPECTED_VERSION
        and source_manifest["arxiv_paper"]["reviewed_pdf_sha256"] == EXPECTED_PAPER_SHA256
    )
    reproduction_supported = (
        reproduction.get("verdict") == "REPRODUCIBLE"
        and reproduction.get("matched_file_count") == len(PRIMARY_RELATIVE_PATHS)
        and set(reproduction.get("generated_files", {})) == PRIMARY_RELATIVE_PATHS
    )
    criteria = {
        "complete_primary_outputs": set(reproduction.get("generated_files", {}))
        == PRIMARY_RELATIVE_PATHS,
        "exact_execution_contract": decision["execution_contract"]["supported"],
        "exact_source_lock": source_lock,
        "fresh_byte_reproduction": reproduction_supported,
        "h1_supported": decision["h1"]["supported"],
        "h2_supported": decision["h2"]["supported"],
        "official_suite_passed": decision["official_suite"]["status"] == "passed",
        "primary_probe_supported": decision["primary_probe_supported"],
        "reported_post_test_observations": decision["h1"][
            "c_promotion_observed_post_test"
        ],
    }
    integration_readiness_passed = all(criteria.values())
    return {
        "artifact_status": (
            "local_audit_complete"
            if integration_readiness_passed
            else "local_audit_hold"
        ),
        "canonical_ams_status": "not_assessed_by_evidence_artifact",
        "criteria": criteria,
        "integration_readiness_passed": integration_readiness_passed,
        "public_note_depth": "not_assessed_by_evidence_artifact",
        "schema": "statefuse-readiness/2",
        "strongest_claim_level": (
            "preregistered_synthetic_interpretation_contract_and_recurrence_consequences"
            if integration_readiness_passed
            else "narrow_or_hold"
        ),
    }


def verify_generated_artifact(root: Path, *, check_manifest: bool) -> None:
    if check_manifest:
        verify_manifest(root)
    for relative in GENERATED_RELATIVE_PATHS:
        require((root / relative).is_file(), f"generated artifact file missing: {relative}")

    runner_sha256 = sha256_path(ARTIFACT_ROOT / "audit.py")
    source_manifest = json.loads((root / "raw/source_manifest.json").read_text(encoding="utf-8"))
    validate_source_manifest_payload(source_manifest, runner_sha256)
    pytest_receipt = parse_pytest_receipt(root)
    environment = json.loads((root / "raw/environment.json").read_text(encoding="utf-8"))
    require(environment["pytest"] == pytest_receipt, "environment pytest receipt changed")
    require(environment["timezone"] == "Asia/Singapore", "environment timezone changed")
    require(environment["locale"] == "C/C.UTF-8/C/C/C/C", "environment locale changed")

    descriptors = json.loads((root / "raw/contract_descriptors.json").read_text(encoding="utf-8"))
    cases = load_jsonl(root / "raw/cases.jsonl")
    results = load_jsonl(root / "raw/run_results.jsonl")
    stored_decision = json.loads((root / "raw/decision.json").read_text(encoding="utf-8"))
    rederived_decision = derive_decision(
        cases, results, pytest_receipt, descriptors, runner_sha256
    )
    require(stored_decision == rederived_decision, "stored decision differs from raw rederivation")

    reproduction = json.loads((root / "raw/reproduction.json").read_text(encoding="utf-8"))
    require(reproduction["schema"] == "statefuse-reproduction/2", "reproduction schema changed")
    require(reproduction["verdict"] == "REPRODUCIBLE", "reproduction verdict changed")
    require(set(reproduction["generated_files"]) == PRIMARY_RELATIVE_PATHS, "reproduction file set changed")
    for relative, expected in reproduction["generated_files"].items():
        require(sha256_path(root / relative) == expected, f"reproduction hash changed: {relative}")

    stored_readiness = json.loads((root / "raw/readiness.json").read_text(encoding="utf-8"))
    rederived_readiness = derive_readiness(stored_decision, reproduction, source_manifest)
    require(stored_readiness == rederived_readiness, "stored readiness differs from rederivation")
    require(
        stored_readiness["integration_readiness_passed"],
        "artifact evidence is not ready for integration review",
    )
    require(
        (root / "RESULTS.txt").read_text(encoding="utf-8")
        == results_text(stored_decision, stored_readiness),
        "RESULTS.txt differs from rederived result",
    )


def verify_checked() -> None:
    verify_generated_artifact(ARTIFACT_ROOT, check_manifest=True)
    print(
        "Verified checked file set; exact source/suite receipts; raw-rederived execution, "
        "H1, and H2 decisions; fresh reproduction; readiness; and local-only boundary."
    )


def compare_checked(rebuild_root: Path) -> None:
    verify_generated_artifact(ARTIFACT_ROOT, check_manifest=True)
    verify_generated_artifact(rebuild_root, check_manifest=True)
    expected = sorted(GENERATED_RELATIVE_PATHS)
    observed = sorted(
        path.relative_to(rebuild_root).as_posix()
        for path in artifact_files(rebuild_root)
    )
    require(observed == expected, "rebuild generated file set differs from contract")
    for relative in expected:
        require(
            (ARTIFACT_ROOT / relative).read_bytes() == (rebuild_root / relative).read_bytes(),
            f"rebuild differs from checked artifact: {relative}",
        )
    print("Fresh two-pass rebuild byte-matches every checked generated raw file and RESULTS.txt.")


def run_primary_pass(
    source_root: Path,
    paper_pdf: Path,
    output_root: Path,
    runner_sha256: str,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    raw_dir = output_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=False)

    source_manifest = build_source_manifest(source_root, paper_pdf, runner_sha256)
    pytest_receipt = run_pytest(source_root, raw_dir)
    require(not git_output(source_root, "status", "--porcelain"), "pytest dirtied source checkout")

    api = load_api(source_root)
    contracts = make_contracts(api)
    with blocked_network():
        fixtures = make_fixtures(api, contracts)
    descriptors = contract_descriptors(contracts, runner_sha256)
    cases, results = execute_fixtures(api, fixtures, contracts, descriptors)
    decision = derive_decision(cases, results, pytest_receipt, descriptors, runner_sha256)
    require(decision["permutation_integrity_passed"], "same-contract permutation gate failed")
    require(decision["h1"]["supported"], "H1 preregistered expectations not supported")
    require(decision["h2"]["supported"], "H2 preregistered expectations not supported")
    require(decision["primary_probe_supported"], "primary probe readiness gate failed")
    require(not git_output(source_root, "status", "--porcelain"), "synthetic run dirtied source checkout")

    save_json(raw_dir / "source_manifest.json", source_manifest)
    save_json(raw_dir / "environment.json", environment_receipt(pytest_receipt))
    save_json(raw_dir / "contract_descriptors.json", descriptors)
    save_jsonl(raw_dir / "cases.jsonl", cases)
    save_jsonl(raw_dir / "run_results.jsonl", results)
    save_json(raw_dir / "decision.json", decision)
    return decision


def run(args: argparse.Namespace) -> None:
    require(args.source_repo is not None, "run requires --source-repo")
    require(args.paper_pdf is not None, "run requires --paper-pdf")
    require(os.environ.get("TZ") == "Asia/Singapore", "run requires TZ=Asia/Singapore")
    require(os.environ.get("LC_ALL") == "C.UTF-8", "run requires LC_ALL=C.UTF-8")

    source_root = args.source_repo.resolve()
    paper_pdf = args.paper_pdf.resolve()
    output_root = args.output_dir.resolve()
    require(source_root.is_dir(), "source repo is missing")
    require(paper_pdf.is_file(), "paper PDF is missing")
    require(git_output(source_root, "rev-parse", "HEAD") == EXPECTED_COMMIT, "source HEAD mismatch")
    require(not git_output(source_root, "status", "--porcelain"), "source checkout is dirty")
    existing_generated = [
        relative for relative in GENERATED_RELATIVE_PATHS if (output_root / relative).exists()
    ]
    require(not existing_generated, f"refusing to overwrite generated outputs: {existing_generated}")

    runner_sha256 = sha256_path(ARTIFACT_ROOT / "audit.py")
    decision = run_primary_pass(source_root, paper_pdf, output_root, runner_sha256)
    with tempfile.TemporaryDirectory(prefix="statefuse-contract-repeat-") as repeat_temp:
        repeat_root = Path(repeat_temp) / "repeat"
        repeated_decision = run_primary_pass(
            source_root, paper_pdf, repeat_root, runner_sha256
        )
        require(repeated_decision == decision, "fresh repeat decision changed")
        reproduction = build_reproduction_receipt(output_root, repeat_root)

    source_manifest = json.loads(
        (output_root / "raw/source_manifest.json").read_text(encoding="utf-8")
    )
    readiness = derive_readiness(decision, reproduction, source_manifest)
    require(
        readiness["integration_readiness_passed"],
        "final integration-evidence readiness gate failed",
    )
    save_json(output_root / "raw/reproduction.json", reproduction)
    save_json(output_root / "raw/readiness.json", readiness)
    (output_root / "RESULTS.txt").write_text(
        results_text(decision, readiness), encoding="utf-8"
    )
    write_checksums(output_root)
    verify_generated_artifact(output_root, check_manifest=True)
    print(results_text(decision, readiness), end="")


def main() -> None:
    args = parse_args()
    if args.verify_checked:
        verify_checked()
        return
    if args.compare_checked:
        compare_checked(args.output_dir.resolve())
        return
    if args.refresh_checksums:
        verify_generated_artifact(ARTIFACT_ROOT, check_manifest=False)
        write_checksums(ARTIFACT_ROOT)
        verify_generated_artifact(ARTIFACT_ROOT, check_manifest=True)
        print("Refreshed complete checked-artifact checksum manifest.")
        return
    run(args)


if __name__ == "__main__":
    main()
