#!/usr/bin/env python3
"""Rebuild the LongMemEval-V2 alias/order selection and feasibility audit."""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import types
from pathlib import Path
from typing import Any


ARTIFACT_ROOT = Path(__file__).resolve().parent
EXPECTED_CURRENT_SOURCE = "2cc8c540bdb87fe6761629b585e727e1c4704520"
SOURCE_REVISIONS = {
    "paper_day_release": "c5c552dfcf023f5a2939f586541c7f6e55a36d5d",
    "query_boundary_fix": "ef67f10aacd9080c75aeb2dd527a0af25dc26f1b",
    "current_source": EXPECTED_CURRENT_SOURCE,
}
DATASET_REVISION = "f152293e235517d504809563c833d7190b8c713b"
EXPECTED_DATA_HASHES = {
    "questions.jsonl": "0a3ae5ebea938c24d7800e1e0b0828e08ae1646f939a53853b2b8cdc08e292b7",
    "lme_v2_small.json": "9b5301defb23a088a5f06e45ff8d5f35e569d78305a66d492046a9fff9b46593",
    "lme_v2_medium.json": "4756d5126347f0d18f045bb6c47b08cb3b23e9db24386cc48a9b2879e7969b59",
    "trajectories.jsonl": "363cec9a8e87aa8d9101ce4e600aadbf7031d674056ebe4f969e8424abc5f3c6",
}
EXPECTED_SOURCE_HASHES = {
    "README.md": "399cc61c9540e587017fccdde28b29b62ed66326425f16f08b5fe0457a593abd",
    "evaluation/harness.py": "93fe5855a74ad46d7e8b489cebac24de38a9b30ba7ec1de2dd8708bd4aeebdb6",
    "memory_modules/codex.py": "3d7c248f3c91a49dd7f8c15d564d41c0ecf26ad0bbc7645883757223780722e7",
    "memory_modules/agentrunbook_c.py": "18b30338c847f246734d116d6830967894867598b7b0b73c71070db3ad5dcea3",
    "memory_modules/assets/agentrunbook_c/scripts/render_trajectory_summary.py": (
        "ab20519d302b5f12f25a25e743da0acdee2c98a1e10c0e1c212a53202351c337"
    ),
}
BASE_TYPES = ("static-environment", "dynamic-environment", "procedure")
DOMAINS = ("web", "enterprise")
PUBLIC_ARTIFACT_SUFFIXES = {".json", ".jsonl", ".md", ".py", ".txt"}
FORBIDDEN_RESIDUE_NAMES = {"__pycache__", ".DS_Store"}
FORBIDDEN_RESIDUE_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path)
    parser.add_argument("--questions", type=Path)
    parser.add_argument("--small", type=Path)
    parser.add_argument("--medium", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACT_ROOT,
        help="Artifact root for a new rebuild; generated files are written below this root.",
    )
    parser.add_argument("--verify-checked", action="store_true")
    parser.add_argument(
        "--compare-checked",
        action="store_true",
        help="Compare a completed --output-dir rebuild with the checked publication artifact.",
    )
    return parser.parse_args()


def git_output(source_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=source_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def load_questions(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            require(isinstance(row, dict), f"questions row {line_number} is not an object")
            question_id = row.get("id")
            require(isinstance(question_id, str) and question_id, f"questions row {line_number} lacks id")
            require(question_id not in rows, f"duplicate question id: {question_id}")
            rows[question_id] = row
    return rows


def load_map(path: Path) -> dict[str, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"expected object in {path.name}")
    result: dict[str, list[str]] = {}
    for question_id, values in payload.items():
        require(isinstance(question_id, str) and question_id, f"invalid question id in {path.name}")
        require(
            isinstance(values, list) and all(isinstance(value, str) and value for value in values),
            f"invalid haystack for {question_id}",
        )
        require(len(values) == len(set(values)), f"duplicate trajectory id in {question_id}")
        result[question_id] = values
    return result


def base_type(question_type: str) -> str:
    return question_type.removesuffix("-abs")


def canonical_array_bytes(values: list[str]) -> bytes:
    return json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def ordered_hash(values: list[str]) -> str:
    return sha256_bytes(canonical_array_bytes(values))


def build_selection(
    questions: dict[str, dict[str, Any]],
    small: dict[str, list[str]],
    medium: dict[str, list[str]],
) -> dict[str, Any]:
    require(set(questions) == set(small) == set(medium), "question and map id sets differ")
    eligibility: list[dict[str, Any]] = []
    eligible_ids: list[str] = []
    for question_id in sorted(questions):
        row = questions[question_id]
        qtype = str(row.get("question_type", ""))
        domain = str(row.get("domain", ""))
        reasons: list[str] = []
        if row.get("image") not in (None, ""):
            reasons.append("question_has_image")
        if qtype == "errors-gotchas":
            reasons.append("errors_gotchas")
        if qtype not in {*BASE_TYPES, *(f"{item}-abs" for item in BASE_TYPES)}:
            reasons.append("question_type_out_of_scope")
        if domain not in DOMAINS:
            reasons.append("domain_out_of_scope")
        if question_id not in small:
            reasons.append("missing_small")
        if question_id not in medium:
            reasons.append("missing_medium")
        eligible = not reasons
        if eligible:
            eligible_ids.append(question_id)
        eligibility.append(
            {
                "question_id": question_id,
                "domain": domain,
                "question_type": qtype,
                "eligible": eligible,
                "reasons": reasons,
            }
        )

    classes: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)
    hash_payloads: dict[str, bytes] = {}
    for question_id in eligible_ids:
        row = questions[question_id]
        medium_bytes = canonical_array_bytes(medium[question_id])
        medium_hash = sha256_bytes(medium_bytes)
        prior_payload = hash_payloads.setdefault(medium_hash, medium_bytes)
        require(
            prior_payload == medium_bytes,
            f"SHA-256 collision across non-identical ordered Medium arrays: {medium_hash}",
        )
        key = (
            str(row["domain"]),
            base_type(str(row["question_type"])),
            medium_hash,
        )
        classes[key].append(question_id)

    class_rows: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for (domain, qtype, medium_hash), question_ids in sorted(classes.items()):
        abstention_ids = sorted(
            question_id
            for question_id in question_ids
            if str(questions[question_id]["question_type"]).endswith("-abs")
        )
        answerable_ids = sorted(set(question_ids) - set(abstention_ids))
        pair_eligible = bool(answerable_ids and abstention_ids)
        row = {
            "class_id": f"{domain}:{qtype}:{medium_hash}",
            "domain": domain,
            "base_question_type": qtype,
            "medium_ordered_hash": medium_hash,
            "all_question_ids": sorted(question_ids),
            "answerable_ids": answerable_ids,
            "abstention_ids": abstention_ids,
            "pair_eligible": pair_eligible,
            "selected_answerable_id": answerable_ids[0] if pair_eligible else None,
            "selected_abstention_id": abstention_ids[0] if pair_eligible else None,
        }
        if pair_eligible:
            selected_ids = [answerable_ids[0], abstention_ids[0]]
            row.update(
                {
                    "selected_medium_length": len(medium[selected_ids[0]]),
                    "selected_small_ordered_hashes": {
                        question_id: ordered_hash(small[question_id])
                        for question_id in selected_ids
                    },
                    "selected_small_lengths": {
                        question_id: len(small[question_id])
                        for question_id in selected_ids
                    },
                }
            )
        class_rows.append(row)
        if pair_eligible:
            selected.append(row)

    domain_ids: dict[str, set[str]] = collections.defaultdict(set)
    for question_id, row in questions.items():
        domain = str(row["domain"])
        domain_ids[domain].update(small[question_id])
        domain_ids[domain].update(medium[question_id])
    cross_domain_overlap = sorted(domain_ids["web"] & domain_ids["enterprise"])

    require(len(selected) == 3, f"locked selector expected 3 classes, got {len(selected)}")
    require(
        {(row["domain"], row["base_question_type"]) for row in selected} == {("web", "procedure")},
        "locked selector no longer yields only web procedure classes",
    )
    selected_question_ids = [
        question_id
        for row in selected
        for question_id in (row["selected_answerable_id"], row["selected_abstention_id"])
    ]
    first_small = small[selected_question_ids[0]]
    require(
        all(small[question_id] == first_small for question_id in selected_question_ids),
        "selected Small arrays are no longer exactly equal",
    )
    return {
        "eligibility": eligibility,
        "exclusions": [row for row in eligibility if not row["eligible"]],
        "classes": class_rows,
        "selected": selected,
        "selected_question_ids": selected_question_ids,
        "selected_small_ordered_hash": ordered_hash(first_small),
        "selected_small_length": len(first_small),
        "all_selected_small_arrays_equal": True,
        "cross_domain_overlap": cross_domain_overlap,
    }


def deterministic_permutation(values: list[str], *, root_seed: str, key: str) -> list[str]:
    ranked = sorted(
        enumerate(values),
        key=lambda item: (
            sha256_bytes(
                f"{root_seed}|sha256-rank-v1|{key}|{item[0]}|{item[1]}".encode("utf-8")
            ),
            item[0],
        ),
    )
    return [value for _, value in ranked]


def rank_preserving_alias_map(values: list[str], *, root_seed: str, key: str) -> dict[str, str]:
    originals = sorted(values)
    tokens = sorted(
        f"t_{sha256_bytes(f'{root_seed}|alias-token-v1|{key}|{index}'.encode('utf-8'))[:16]}"
        for index in range(len(originals))
    )
    require(len(tokens) == len(set(tokens)), f"alias token collision: {key}")
    return dict(zip(originals, tokens, strict=True))


def assigned_string(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            require(isinstance(value, str), f"{name} is not a string")
            return value
    raise RuntimeError(f"missing assigned string: {name}")


def build_protocol_ledger(
    selection: dict[str, Any],
    small: dict[str, list[str]],
    medium: dict[str, list[str]],
    source_root: Path,
) -> dict[str, Any]:
    seed_basis = {
        "protocol": "longmemeval-v2-alias-order-exact-pair-panel-v1",
        "source_commit": EXPECTED_CURRENT_SOURCE,
        "dataset_revision": DATASET_REVISION,
        "questions_sha256": EXPECTED_DATA_HASHES["questions.jsonl"],
        "small_sha256": EXPECTED_DATA_HASHES["lme_v2_small.json"],
        "medium_sha256": EXPECTED_DATA_HASHES["lme_v2_medium.json"],
    }
    root_seed = sha256_bytes(
        json.dumps(seed_basis, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    selected = sorted(selection["selected"], key=lambda row: row["class_id"])
    medium_treatments: list[dict[str, Any]] = []
    for family_rank, row in enumerate(selected):
        answerable_id = row["selected_answerable_id"]
        abstention_id = row["selected_abstention_id"]
        official = medium[answerable_id]
        require(official == medium[abstention_id], f"Medium pair drift: {row['class_id']}")
        key = f"family-{family_rank}|medium"
        medium_treatments.append(
            {
                "family_rank": family_rank,
                "class_id": row["class_id"],
                "question_ids": [answerable_id, abstention_id],
                "seed_key": key,
                "official_order": official,
                "shuffled_order": deterministic_permutation(official, root_seed=root_seed, key=f"{key}|order"),
                "rank_preserving_alias_map": rank_preserving_alias_map(
                    official,
                    root_seed=root_seed,
                    key=f"{key}|alias",
                ),
            }
        )

    selected_question_ids = selection["selected_question_ids"]
    shared_small = small[selected_question_ids[0]]
    require(all(small[question_id] == shared_small for question_id in selected_question_ids), "Small drift")
    small_treatment = {
        "seed_key": "web-small-shared",
        "question_ids": selected_question_ids,
        "official_order": shared_small,
        "shuffled_order": deterministic_permutation(
            shared_small,
            root_seed=root_seed,
            key="web-small-shared|order",
        ),
        "rank_preserving_alias_map": rank_preserving_alias_map(
            shared_small,
            root_seed=root_seed,
            key="web-small-shared|alias",
        ),
    }

    cells = ("C00", "C10", "C01", "C11")
    factorial_jobs: list[dict[str, Any]] = []
    repeat_jobs: list[dict[str, Any]] = []
    no_memory_jobs: list[dict[str, Any]] = []
    unit_positions = (
        (0, "answerable", "small"),
        (1, "abstention", "small"),
        (2, "answerable", "medium"),
        (3, "abstention", "medium"),
    )
    role_code = {"answerable": "A", "abstention": "X"}
    tier_code = {"small": "S", "medium": "M"}
    for family_rank, row in enumerate(selected):
        question_by_role = {
            "answerable": row["selected_answerable_id"],
            "abstention": row["selected_abstention_id"],
        }
        for position, role, tier in unit_positions:
            question_id = question_by_role[role]
            unit_id = f"F{family_rank}-{role_code[role]}-{tier_code[tier]}"
            for cell in cells:
                factorial_jobs.append(
                    {
                        "job_id": f"{unit_id}-{cell}",
                        "family_rank": family_rank,
                        "class_id": row["class_id"],
                        "question_id": question_id,
                        "role": role,
                        "tier": tier,
                        "cell": cell,
                        "kind": "factorial",
                    }
                )
            repeat_cell = cells[(position + family_rank) % len(cells)]
            repeat_jobs.append(
                {
                    "job_id": f"{unit_id}-{repeat_cell}-R1",
                    "duplicates_job_id": f"{unit_id}-{repeat_cell}",
                    "family_rank": family_rank,
                    "class_id": row["class_id"],
                    "question_id": question_id,
                    "role": role,
                    "tier": tier,
                    "cell": repeat_cell,
                    "kind": "exact_input_repeat",
                }
            )
        for role in ("answerable", "abstention"):
            question_id = question_by_role[role]
            no_memory_jobs.append(
                {
                    "job_id": f"F{family_rank}-{role_code[role]}-NOMEM",
                    "family_rank": family_rank,
                    "class_id": row["class_id"],
                    "question_id": question_id,
                    "role": role,
                    "tier": None,
                    "cell": None,
                    "kind": "empty_memory_control",
                }
            )
    jobs = factorial_jobs + repeat_jobs + no_memory_jobs
    require(len(factorial_jobs) == 48, "factorial job count drift")
    require(len(repeat_jobs) == 12, "repeat job count drift")
    require(len(no_memory_jobs) == 6, "no-memory job count drift")
    require(len({job["job_id"] for job in jobs}) == 66, "job IDs are not unique")
    execution_order = deterministic_permutation(
        [job["job_id"] for job in jobs],
        root_seed=root_seed,
        key="controller-execution-order",
    )

    prompt = assigned_string(source_root / "memory_modules/agentrunbook_c.py", "DEFAULT_QUERY_PROMPT")
    return {
        "status": "proposed_not_run_blocked_before_release",
        "root_seed_sha256": root_seed,
        "seed_basis": seed_basis,
        "randomization_algorithm": (
            "SHA-256 rank v1: rank each indexed item by SHA256(root_seed|purpose|index|value), "
            "breaking a digest tie by original index"
        ),
        "alias_algorithm": (
            "Generate SHA-256-derived opaque tokens from root_seed and counter, sort original IDs and tokens, "
            "then zip them to preserve lexical rank"
        ),
        "medium_treatments": medium_treatments,
        "small_treatment": small_treatment,
        "repeat_allocation": repeat_jobs,
        "jobs": jobs,
        "execution_order": execution_order,
        "runtime_contract": {
            "codex_package": "@openai/codex@0.117.0-darwin-arm64",
            "model": "gpt-5.4-mini",
            "reasoning_effort": "xhigh",
            "timeout_seconds": 1800.0,
            "max_attempts": 3,
            "extra_config": [],
            "extra_args": [],
            "query_prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
            "network_isolation_preflight": "required_but_not_implemented_or_passed",
        },
        "analysis_contract": {
            "dealiasing": "Replace declared alias tokens with original trajectory IDs before every set/hash comparison.",
            "selected_state_set": (
                "Expand each valid inclusive span to unique (trajectory_id,state_index) pairs after de-aliasing."
            ),
            "selected_trajectory_set": "Unique de-aliased trajectory IDs appearing in valid spans.",
            "set_distance": "Jaccard distance 1-|intersection|/|union|; define empty versus empty as 0.",
            "prose_normalization": (
                "Unicode NFKC; normalize CRLF/CR to LF; strip; collapse every Unicode whitespace run to one ASCII space."
            ),
            "prose_distance": (
                "Character-level Levenshtein distance on normalized prose divided by max character length; "
                "define empty versus empty as 0."
            ),
            "evidence_context_hash": (
                "SHA-256 of compact ASCII JSON with sorted object keys over the ordered valid spans; each span stores "
                "de-aliased trajectory_id, inclusive indices, and exact selected public state objects in source order."
            ),
            "failure_coding": (
                "Retain missing, malformed, timeout, exhausted-retry, empty-prose, empty-span and invalid-span outcomes. "
                "For distance calculations, no valid output contributes empty prose/sets; completion and retry states "
                "remain separate outcomes. Partial valid outputs are retained without post hoc exclusion."
            ),
        },
        "unreleased_gates": [
            "full selected trajectory union resolution",
            "exact Codex CLI no-bypass local signing-trust gate",
            "controller-tool network isolation preflight",
        ],
    }


def renderer_source_contract(renderer: Path, runbook: Path, codex: Path) -> dict[str, Any]:
    renderer_text = renderer.read_text(encoding="utf-8")
    tree = ast.parse(renderer_text)
    sort_fields: list[str] = []
    records_sort = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "sort_key":
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Subscript)
                    and isinstance(child.value, ast.Name)
                    and child.value.id == "record"
                    and isinstance(child.slice, ast.Constant)
                    and isinstance(child.slice.value, str)
                ):
                    sort_fields.append(child.slice.value)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "records"
            and node.func.attr == "sort"
        ):
            records_sort = True
    runbook_text = runbook.read_text(encoding="utf-8")
    codex_text = codex.read_text(encoding="utf-8")
    contract = {
        "sort_fields": sort_fields,
        "records_sort": records_sort,
        "sandbox_links_trajectories": (
            'relative_symlink(self.workspace_dir / "trajectories", sandbox_dir / "trajectories")'
            in runbook_text
        ),
        "runbook_exposes_workspace_manifest_directly": "haystack_manifest.json" in runbook_text,
        "base_workspace_writes_manifest": 'workspace_dir / "haystack_manifest.json"' in codex_text,
        "summary_admits_outcome": 'response_text(trajectory.get("outcome"))' in renderer_text,
    }
    require(sort_fields == ["start_url", "goal", "trajectory_id"], f"unexpected sort fields: {sort_fields}")
    require(records_sort, "renderer no longer sorts records")
    require(contract["sandbox_links_trajectories"], "sandbox trajectory surface changed")
    require(not contract["runbook_exposes_workspace_manifest_directly"], "runbook now exposes manifest directly")
    require(contract["base_workspace_writes_manifest"], "base workspace manifest behavior changed")
    require(contract["summary_admits_outcome"], "summary outcome surface changed")
    return contract


def synthetic_trajectory(trajectory_id: str, marker: str, *, other_surface: bool = False) -> dict[str, Any]:
    return {
        "id": trajectory_id,
        "start_url": "https://z.invalid/page" if other_surface else "https://same.invalid/page",
        "goal": "Inspect another surface" if other_surface else "Inspect the same surface",
        "outcome": f"OUTCOME_{marker}",
        "states": [{"text": f"[node1] marker {marker}", "action": 'click("node1")'}],
    }


def materialize(root: Path, name: str, payloads: list[dict[str, Any]]) -> Path:
    trajectories = root / name
    trajectories.mkdir(parents=True)
    for payload in payloads:
        target = trajectories / payload["id"]
        target.mkdir()
        save_json(target / "trajectory.json", payload)
    return trajectories


def render(renderer: Path, trajectories: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True)
    concise = output / "concise.md"
    full = output / "full.md"
    result = subprocess.run(
        [
            sys.executable,
            str(renderer),
            str(trajectories),
            "--concise-output",
            str(concise),
            "--full-output",
            str(full),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    require(result.returncode == 0, f"renderer failed: {result.stderr}")
    return {
        "concise_sha256": sha256_path(concise),
        "full_sha256": sha256_path(full),
        "full_order": re.findall(r"^## \d+\. (.+)$", full.read_text(encoding="utf-8"), flags=re.MULTILINE),
    }


def load_module(module_name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(spec is not None and spec.loader is not None, f"module import failed: {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_current_source_modules(source_root: Path) -> tuple[Any, Any]:
    """Load exact current Codex/AgentRunbook-C files without optional benchmark dependencies."""

    module_root = source_root / "memory_modules"
    package_name = f"_lme_v2_alias_order_{len(sys.modules)}"
    package = types.ModuleType(package_name)
    package.__path__ = [str(module_root)]
    package.__package__ = package_name
    sys.modules[package_name] = package

    memory_name = f"{package_name}.memory"
    memory_module = types.ModuleType(memory_name)

    class Memory:
        pass

    def register_memory(cls: type[Any]) -> type[Any]:
        return cls

    memory_module.Memory = Memory
    memory_module.MemoryConfig = dict
    memory_module.MemoryContextItem = dict
    memory_module.register_memory = register_memory
    memory_module.require = require
    sys.modules[memory_name] = memory_module

    prior_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        load_module(f"{package_name}.trajectory_store", module_root / "trajectory_store.py")
        codex_module = load_module(f"{package_name}.codex", module_root / "codex.py")
        agentrunbook_module = load_module(
            f"{package_name}.agentrunbook_c",
            module_root / "agentrunbook_c.py",
        )
    finally:
        sys.dont_write_bytecode = prior_dont_write_bytecode
    return codex_module, agentrunbook_module


def reorder_concise_summary(text: str, order: list[int]) -> str:
    lines = text.splitlines()
    row_indexes = [index for index, line in enumerate(lines) if re.match(r"^\| \d+ \|", line)]
    require(len(row_indexes) == len(order), "unexpected concise record count")
    require(row_indexes == list(range(row_indexes[0], row_indexes[-1] + 1)), "concise rows are not contiguous")
    rows = [lines[index] for index in row_indexes]
    reordered = [re.sub(r"^\| \d+ \|", f"| {rank} |", rows[source]) for rank, source in enumerate(order, start=1)]
    lines[row_indexes[0] : row_indexes[-1] + 1] = reordered
    return "\n".join(lines).rstrip() + "\n"


def reorder_full_summary(text: str, order: list[int]) -> str:
    matches = list(re.finditer(r"(?m)^## \d+\. .+$", text))
    require(len(matches) == len(order), "unexpected full-summary record count")
    prefix = text[: matches[0].start()]
    blocks = [
        text[match.start() : (matches[index + 1].start() if index + 1 < len(matches) else len(text))]
        for index, match in enumerate(matches)
    ]
    reordered: list[str] = []
    for rank, source in enumerate(order, start=1):
        reordered.append(re.sub(r"^## \d+\.", f"## {rank}.", blocks[source], count=1))
    return (prefix + "".join(reordered)).rstrip() + "\n"


def preseeded_summary_probe(
    source_root: Path,
    renderer: Path,
    payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    codex_module, agentrunbook_module = load_current_source_modules(source_root)
    reorder = [2, 0, 1]
    with tempfile.TemporaryDirectory(prefix="lme-v2-preseeded-summary-") as temp:
        root = Path(temp)
        workspace = root / "workspace"
        trajectories = materialize(workspace, "trajectories", payloads)
        concise = trajectories / agentrunbook_module.TRAJECTORY_SUMMARY_CONCISE_FILENAME
        full = trajectories / agentrunbook_module.TRAJECTORY_SUMMARY_FULL_FILENAME
        process = subprocess.run(
            [
                sys.executable,
                str(renderer),
                str(trajectories),
                "--concise-output",
                str(concise),
                "--full-output",
                str(full),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        require(process.returncode == 0, f"preseed renderer failed: {process.stderr}")
        original_order = re.findall(r"^## \d+\. (.+)$", full.read_text(encoding="utf-8"), flags=re.MULTILINE)
        concise.write_text(
            reorder_concise_summary(concise.read_text(encoding="utf-8"), reorder),
            encoding="utf-8",
        )
        full.write_text(
            reorder_full_summary(full.read_text(encoding="utf-8"), reorder),
            encoding="utf-8",
        )
        expected_concise = concise.read_bytes()
        expected_full = full.read_bytes()

        memory = object.__new__(agentrunbook_module.AgentRunbookC)
        memory.workspace_dir = workspace
        memory.trajectory_summary_renderer_path = renderer
        memory._trajectory_summary_lock = threading.Lock()
        attempt_dir = root / "attempt"
        attempt_dir.mkdir()
        result = memory._ensure_trajectory_summary(attempt_dir=attempt_dir)

        sandbox = root / "sandbox"
        sandbox.mkdir()
        codex_module.relative_symlink(trajectories, sandbox / "trajectories")
        sandbox_concise = sandbox / "trajectories" / concise.name
        sandbox_full = sandbox / "trajectories" / full.name
        observed_order = re.findall(
            r"^## \d+\. (.+)$",
            sandbox_full.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
        return {
            "reorder_indices": reorder,
            "original_order": original_order,
            "preseeded_order": observed_order,
            "ensure_success": result["success"],
            "summary_rendered": result["summary_rendered"],
            "concise_byte_preserved": concise.read_bytes() == expected_concise,
            "full_byte_preserved": full.read_bytes() == expected_full,
            "sandbox_trajectories_is_symlink": (sandbox / "trajectories").is_symlink(),
            "sandbox_concise_byte_equal": sandbox_concise.read_bytes() == expected_concise,
            "sandbox_full_byte_equal": sandbox_full.read_bytes() == expected_full,
            "summary_stdout_path": result["summary_stdout_path"],
            "summary_stderr_path": result["summary_stderr_path"],
            "concise_sha256": sha256_bytes(expected_concise),
            "full_sha256": sha256_bytes(expected_full),
        }


def renderer_probe(source_root: Path) -> dict[str, Any]:
    renderer = source_root / "memory_modules/assets/agentrunbook_c/scripts/render_trajectory_summary.py"
    runbook = source_root / "memory_modules/agentrunbook_c.py"
    codex = source_root / "memory_modules/codex.py"
    contract = renderer_source_contract(renderer, runbook, codex)
    base = [
        synthetic_trajectory("id-a", "ALPHA"),
        synthetic_trajectory("id-b", "BETA"),
        synthetic_trajectory("id-c", "GAMMA", other_surface=True),
    ]
    rank_aliases = {"id-a": "10000001", "id-b": "10000002", "id-c": "10000003"}
    reverse_aliases = {"id-a": "f0000002", "id-b": "f0000001", "id-c": "f0000003"}

    def relabel(mapping: dict[str, str]) -> list[dict[str, Any]]:
        return [{**payload, "id": mapping[payload["id"]]} for payload in base]

    with tempfile.TemporaryDirectory(prefix="lme-v2-renderer-audit-") as temp:
        root = Path(temp)
        forward = render(renderer, materialize(root, "forward", base), root / "out-forward")
        reverse = render(renderer, materialize(root, "reverse", list(reversed(base))), root / "out-reverse")
        rank_alias = render(renderer, materialize(root, "rank-alias", relabel(rank_aliases)), root / "out-rank")
        reverse_alias = render(
            renderer,
            materialize(root, "reverse-alias", relabel(reverse_aliases)),
            root / "out-reverse-alias",
        )

    preseeded = preseeded_summary_probe(source_root, renderer, base)
    require(preseeded["ensure_success"], "preseeded summary ensure path failed")
    require(not preseeded["summary_rendered"], "preseeded summaries were unexpectedly rerendered")
    require(preseeded["concise_byte_preserved"], "preseeded concise summary changed")
    require(preseeded["full_byte_preserved"], "preseeded full summary changed")
    require(preseeded["sandbox_concise_byte_equal"], "sandbox concise summary differs")
    require(preseeded["sandbox_full_byte_equal"], "sandbox full summary differs")

    return {
        "source_contract": contract,
        "filesystem_materialization_order_reversal": {
            "concise_equal": forward["concise_sha256"] == reverse["concise_sha256"],
            "full_equal": forward["full_sha256"] == reverse["full_sha256"],
            "forward_order": forward["full_order"],
            "reverse_order": reverse["full_order"],
        },
        "rank_preserving_alias": {
            "mapping": rank_aliases,
            "base_order": forward["full_order"],
            "aliased_order": rank_alias["full_order"],
            "dealiased_order": [
                {alias: original for original, alias in rank_aliases.items()}[item]
                for item in rank_alias["full_order"]
            ],
        },
        "order_reversing_alias_diagnostic": {
            "mapping": reverse_aliases,
            "aliased_order": reverse_alias["full_order"],
            "dealiased_order": [
                {alias: original for original, alias in reverse_aliases.items()}[item]
                for item in reverse_alias["full_order"]
            ],
        },
        "preseeded_summary_order": preseeded,
    }


def runtime_attestation() -> dict[str, Any]:
    return {
        "evidence_kind": "author_recorded_local_preflight_observation",
        "independently_reproduced_by_artifact": False,
        "candidate_package": "@openai/codex@0.117.0-darwin-arm64",
        "candidate_tarball_sha256": "a3bf799db50c61a80f2f5080bedb51223c460c7ea3b2528b4e1a072cd4e5d310",
        "candidate_binary_sha256": "89b83ea8e7a16f8ea6d35cf6015e89cc98c2ef64e84065d8a65415ebf8a53b0f",
        "version_receipt": None,
        "version_command_exit_code": 137,
        "version_command_output": "",
        "gatekeeper_assessment": "CSSMERR_TP_CERT_REVOKED",
        "signature_structure": "valid_on_disk_and_satisfies_designated_requirement",
        "bypass_attempted": False,
        "preregistered_local_signing_trust_gate": "HOLD",
        "boundary": (
            "This author-recorded observation is not replayed by the artifact. A revoked signing trust path is "
            "sufficient to prohibit execution under the preregistered no-bypass gate; it does not identify a specific "
            "malicious payload and is not generalized to other Codex releases."
        ),
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def artifact_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in FORBIDDEN_RESIDUE_NAMES for part in relative.parts):
            raise RuntimeError(f"forbidden build residue: {relative.as_posix()}")
        if not path.is_file() or path.name == "checksums.sha256":
            continue
        require(
            path.suffix.lower() in PUBLIC_ARTIFACT_SUFFIXES,
            f"unlisted artifact file type: {relative.as_posix()}",
        )
        require(
            path.suffix.lower() not in FORBIDDEN_RESIDUE_SUFFIXES,
            f"forbidden build residue: {relative.as_posix()}",
        )
        files.append(path)
    return files


def write_checksums(root: Path) -> None:
    included = artifact_files(root)
    with (root / "checksums.sha256").open("w", encoding="utf-8") as handle:
        for path in included:
            handle.write(f"{sha256_path(path)}  {path.relative_to(root).as_posix()}\n")


def verify_manifest(root: Path) -> None:
    checksums = root / "checksums.sha256"
    require(checksums.is_file(), f"missing checksum manifest: {checksums}")
    expected_files = {path.relative_to(root).as_posix() for path in artifact_files(root)}
    listed: dict[str, str] = {}
    for line in checksums.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        require(relative not in listed, f"duplicate checksum entry: {relative}")
        listed[relative] = expected
    require(set(listed) == expected_files, "checksum manifest file set is incomplete or contains extras")
    for relative, expected in listed.items():
        path = root / relative
        require(sha256_path(path) == expected, f"checksum mismatch: {relative}")


def verify_checked() -> None:
    verify_manifest(ARTIFACT_ROOT)
    decision = json.loads((ARTIFACT_ROOT / "raw/decision.json").read_text(encoding="utf-8"))
    require(decision["selection_census_passed"], "selection census no longer passes")
    require(decision["selected_exact_class_count"] == 3, "selected class count changed")
    require(decision["controller_phase"] == "HOLD", "controller phase is not held")
    require(decision["controller_jobs_executed"] == 0, "unexpected controller jobs recorded")
    require(decision["all_selected_small_arrays_equal"], "selected Small arrays differ")
    require(decision["preseeded_summary_order_surface_passed"], "preseeded summary probe no longer passes")
    print("Verified exact checked file set, selection, renderer, runtime attestation, and HOLD decision.")


def compare_checked(rebuild_root: Path) -> None:
    verify_manifest(ARTIFACT_ROOT)
    verify_manifest(rebuild_root)
    expected = sorted(
        path.relative_to(ARTIFACT_ROOT).as_posix()
        for path in artifact_files(ARTIFACT_ROOT)
        if path.name == "RESULTS.txt" or "raw" in path.relative_to(ARTIFACT_ROOT).parts
    )
    observed = sorted(path.relative_to(rebuild_root).as_posix() for path in artifact_files(rebuild_root))
    require(observed == expected, "rebuild generated file set differs from checked generated file set")
    for relative in expected:
        require(
            (rebuild_root / relative).read_bytes() == (ARTIFACT_ROOT / relative).read_bytes(),
            f"rebuild differs from checked artifact: {relative}",
        )
    print("Rebuild byte-matches every checked raw file and RESULTS.txt.")


def run(args: argparse.Namespace) -> None:
    required = (args.source_repo, args.questions, args.small, args.medium)
    require(all(path is not None for path in required), "rebuild requires source repo and three public data files")
    source_root = args.source_repo.resolve()
    paths = {
        "questions.jsonl": args.questions.resolve(),
        "lme_v2_small.json": args.small.resolve(),
        "lme_v2_medium.json": args.medium.resolve(),
    }
    output_root = args.output_dir.resolve()
    require(not output_root.exists(), f"refusing to overwrite output directory: {output_root}")
    require(git_output(source_root, "rev-parse", "HEAD") == EXPECTED_CURRENT_SOURCE, "source HEAD mismatch")
    require(not git_output(source_root, "status", "--porcelain"), "source checkout is not clean")
    observed_data_hashes = {name: sha256_path(path) for name, path in paths.items()}
    require(
        observed_data_hashes == {name: EXPECTED_DATA_HASHES[name] for name in paths},
        f"public data hash mismatch: {observed_data_hashes}",
    )
    observed_source_hashes = {
        relative: sha256_path(source_root / relative) for relative in EXPECTED_SOURCE_HASHES
    }
    require(observed_source_hashes == EXPECTED_SOURCE_HASHES, "current source file hash mismatch")

    questions = load_questions(paths["questions.jsonl"])
    small = load_map(paths["lme_v2_small.json"])
    medium = load_map(paths["lme_v2_medium.json"])
    selection = build_selection(questions, small, medium)
    renderer = renderer_probe(source_root)
    runtime = runtime_attestation()
    protocol = build_protocol_ledger(selection, small, medium, source_root)

    raw_dir = output_root / "raw"
    raw_dir.mkdir(parents=True)
    write_jsonl(raw_dir / "selection/eligibility.jsonl", selection["eligibility"])
    write_jsonl(raw_dir / "selection/exclusions.jsonl", selection["exclusions"])
    write_jsonl(raw_dir / "selection/medium_equivalence_classes.jsonl", selection["classes"])
    save_json(raw_dir / "selection/selected_families.json", selection["selected"])
    save_json(raw_dir / "renderer_surface.json", renderer)
    save_json(raw_dir / "runtime_attestation.json", runtime)
    save_json(raw_dir / "protocol_ledger.json", protocol)
    save_json(
        raw_dir / "source_lock.json",
        {
            "paper": "arXiv:2605.12493v1",
            "source_revisions": SOURCE_REVISIONS,
            "dataset_revision": DATASET_REVISION,
            "expected_dataset_hashes": EXPECTED_DATA_HASHES,
            "observed_dataset_hashes": observed_data_hashes,
            "trajectories_jsonl_observed_in_this_run": False,
            "expected_source_file_hashes": EXPECTED_SOURCE_HASHES,
            "observed_source_file_hashes": observed_source_hashes,
        },
    )
    save_json(
        raw_dir / "run_manifest.json",
        {
            "python": sys.version.split()[0],
            "os": platform.system(),
            "os_version": platform.mac_ver()[0],
            "architecture": platform.machine(),
            "network_used_by_audit": False,
            "models_called": 0,
            "controller_jobs_executed": 0,
            "reader_or_judge_called": False,
            "source_commit": EXPECTED_CURRENT_SOURCE,
            "selector": "all exact ordered-Medium answerable/abstention equivalence classes",
        },
    )
    decision = {
        "selection_census_passed": True,
        "eligible_question_count": sum(row["eligible"] for row in selection["eligibility"]),
        "excluded_question_count": len(selection["exclusions"]),
        "selected_exact_class_count": len(selection["selected"]),
        "selected_question_count": 2 * len(selection["selected"]),
        "selected_small_ordered_hash": selection["selected_small_ordered_hash"],
        "selected_small_length": selection["selected_small_length"],
        "all_selected_small_arrays_equal": selection["all_selected_small_arrays_equal"],
        "selected_domains": sorted({row["domain"] for row in selection["selected"]}),
        "selected_base_types": sorted({row["base_question_type"] for row in selection["selected"]}),
        "cross_domain_trajectory_id_overlap_count": len(selection["cross_domain_overlap"]),
        "renderer_erases_filesystem_materialization_order_reversal": (
            renderer["filesystem_materialization_order_reversal"]["concise_equal"]
            and renderer["filesystem_materialization_order_reversal"]["full_equal"]
        ),
        "rank_preserving_alias_preserves_tie_order": (
            renderer["rank_preserving_alias"]["base_order"]
            == renderer["rank_preserving_alias"]["dealiased_order"]
        ),
        "non_rank_preserving_alias_can_change_tie_order": (
            renderer["rank_preserving_alias"]["base_order"]
            != renderer["order_reversing_alias_diagnostic"]["dealiased_order"]
        ),
        "preseeded_summary_order_surface_passed": (
            not renderer["preseeded_summary_order"]["summary_rendered"]
            and renderer["preseeded_summary_order"]["concise_byte_preserved"]
            and renderer["preseeded_summary_order"]["full_byte_preserved"]
            and renderer["preseeded_summary_order"]["sandbox_concise_byte_equal"]
            and renderer["preseeded_summary_order"]["sandbox_full_byte_equal"]
        ),
        "full_trajectory_resolution_gate": "not_run",
        "exact_cli_runtime_gate": runtime["preregistered_local_signing_trust_gate"],
        "runtime_evidence_kind": runtime["evidence_kind"],
        "runtime_observation_replayed_by_artifact": runtime["independently_reproduced_by_artifact"],
        "planned_controller_jobs": 66,
        "controller_jobs_released_by_protocol": 0,
        "controller_jobs_executed": 0,
        "controller_phase": "HOLD",
        "strongest_claim_level": "selection_renderer_and_preseeded_summary_surface_only",
    }
    save_json(raw_dir / "decision.json", decision)
    results = (
        "LongMemEval-V2 alias/order pre-registration audit\n\n"
        f"Eligible text-only questions: {decision['eligible_question_count']}\n"
        f"Pre-excluded image/gotcha questions: {decision['excluded_question_count']}\n"
        f"Selected exact ordered-Medium classes: {decision['selected_exact_class_count']}\n"
        "Selected scope: web procedure only\n"
        f"Filesystem materialization-order reversal erased by official summaries: {decision['renderer_erases_filesystem_materialization_order_reversal']}\n"
        f"Rank-preserving alias keeps tie order: {decision['rank_preserving_alias_preserves_tie_order']}\n"
        f"Preseeded summary order survives exact ensure/sandbox path: {decision['preseeded_summary_order_surface_passed']}\n"
        f"Exact CLI runtime gate: {decision['exact_cli_runtime_gate']}\n"
        "Full trajectory resolution: not run\n"
        "Controller jobs executed: 0\n"
        "Final decision: HOLD before controller execution\n"
    )
    (output_root / "RESULTS.txt").write_text(results, encoding="utf-8")
    write_checksums(output_root)
    print(results, end="")


def main() -> None:
    args = parse_args()
    if args.verify_checked:
        verify_checked()
        return
    if args.compare_checked:
        compare_checked(args.output_dir.resolve())
        return
    run(args)


if __name__ == "__main__":
    main()
