#!/usr/bin/env python3
"""Audit LongMemEval-V2 query lineage and current answer-evidence binding.

This runner is deliberately smaller than the benchmark. It reads three exact
Git revisions from a caller-supplied official-code checkout and directly
executes the current release's output validator, normalizer, and reader-context
builder against public synthetic trajectories. It never invokes a model,
reader, judge, tokenizer, embedding package, or network service.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib.util
import inspect
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any


RELEASE_REVISION = "c5c552dfcf023f5a2939f586541c7f6e55a36d5d"
PRIVACY_FIX_REVISION = "ef67f10aacd9080c75aeb2dd527a0af25dc26f1b"
CURRENT_REVISION = "2cc8c540bdb87fe6761629b585e727e1c4704520"
TARGET_FUNCTIONS = (
    "memory_modules.codex.validate_memory_module_output_payload",
    "memory_modules.codex.CodexMemory._normalize_output_for_query",
    "memory_modules.codex.CodexMemory._build_memory_context_from_output",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-repo",
        type=Path,
        required=True,
        help="Clean official LongMemEval-V2 checkout at the exact current revision.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "raw",
        help="Regenerated machine-readable outputs.",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path(__file__).resolve().parent / "RESULTS.txt",
        help="Human-readable deterministic run summary.",
    )
    return parser.parse_args()


def run_git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_PAGER": "cat",
        }
    )
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.stdout


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def install_python_network_guard() -> None:
    def denied(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network access is disabled by the boundary-audit runner")

    socket.create_connection = denied  # type: ignore[assignment]
    socket.getaddrinfo = denied  # type: ignore[assignment]


def validate_source_checkout(repo: Path) -> dict[str, str]:
    repo = repo.resolve()
    require((repo / ".git").exists(), "--source-repo must be a Git checkout")
    head = run_git(repo, "rev-parse", "HEAD").strip()
    require(head == CURRENT_REVISION, f"expected current revision {CURRENT_REVISION}, found {head}")
    require(not run_git(repo, "status", "--porcelain").strip(), "source checkout must be clean")
    for revision in (RELEASE_REVISION, PRIVACY_FIX_REVISION, CURRENT_REVISION):
        run_git(repo, "cat-file", "-e", f"{revision}^{{commit}}")
    return {
        "release_revision": RELEASE_REVISION,
        "privacy_fix_revision": PRIVACY_FIX_REVISION,
        "current_revision": CURRENT_REVISION,
    }


def git_text(repo: Path, revision: str, relative_path: str) -> str:
    return run_git(repo, "show", f"{revision}:{relative_path}")


def git_blob_sha(repo: Path, revision: str, relative_path: str) -> str:
    return run_git(repo, "rev-parse", f"{revision}:{relative_path}").strip()


def source_locator(
    repo: Path,
    revision: str,
    relative_path: str,
    text: str,
    *,
    symbol: str,
    start_line: int,
    end_line: int,
) -> dict[str, Any]:
    lines = text.splitlines()
    excerpt = "\n".join(lines[start_line - 1 : end_line])
    return {
        "revision": revision,
        "path": relative_path,
        "symbol": symbol,
        "blob_sha": git_blob_sha(repo, revision, relative_path),
        "start_line": start_line,
        "end_line": end_line,
        "excerpt": excerpt,
    }


def node_locator(
    repo: Path,
    revision: str,
    relative_path: str,
    text: str,
    node: ast.AST,
    *,
    symbol: str,
) -> dict[str, Any]:
    start_line = getattr(node, "lineno", None)
    end_line = getattr(node, "end_lineno", None)
    require(isinstance(start_line, int) and isinstance(end_line, int), f"missing locator for {symbol}")
    return source_locator(
        repo,
        revision,
        relative_path,
        text,
        symbol=symbol,
        start_line=start_line,
        end_line=end_line,
    )


def find_class(tree: ast.AST, name: str) -> ast.ClassDef:
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == name]
    require(len(matches) == 1, f"expected one class {name}, found {len(matches)}")
    return matches[0]


def find_method(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    require(len(matches) == 1, f"expected one method {class_node.name}.{name}, found {len(matches)}")
    require(isinstance(matches[0], ast.FunctionDef), f"unexpected async method {class_node.name}.{name}")
    return matches[0]


def attribute_calls(node: ast.AST, attribute: str) -> list[ast.Call]:
    return [
        candidate
        for candidate in ast.walk(node)
        if isinstance(candidate, ast.Call)
        and isinstance(candidate.func, ast.Attribute)
        and candidate.func.attr == attribute
    ]


def check(name: str, observed: Any, expected: Any, evidence: Any) -> dict[str, Any]:
    return {
        "name": name,
        "observed": observed,
        "expected": expected,
        "passed": observed == expected,
        "evidence": evidence,
    }


def load_module(module_name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(spec is not None and spec.loader is not None, f"module import failed: {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_revision_modules(repo: Path, revision: str) -> tuple[Any, Any]:
    """Load exact codex.py and AgentRunbook-C blobs without patching source."""

    with tempfile.TemporaryDirectory(prefix=f"lme-v2-source-{revision[:8]}-") as temp_dir:
        module_root = Path(temp_dir) / "memory_modules"
        module_root.mkdir(parents=True)
        for relative_name in ("trajectory_store.py", "codex.py", "agentrunbook_c.py"):
            (module_root / relative_name).write_text(
                git_text(repo, revision, f"memory_modules/{relative_name}"),
                encoding="utf-8",
            )

        package_name = f"_lme_v2_boundary_{revision[:8]}_{len(sys.modules)}"
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

        load_module(f"{package_name}.trajectory_store", module_root / "trajectory_store.py")
        codex_module = load_module(f"{package_name}.codex", module_root / "codex.py")
        agentrunbook_c_module = load_module(
            f"{package_name}.agentrunbook_c", module_root / "agentrunbook_c.py"
        )
        return codex_module, agentrunbook_c_module


def query_context_call(repo: Path, revision: str) -> tuple[dict[str, Any], dict[str, Any]]:
    path = "evaluation/harness.py"
    text = git_text(repo, revision, path)
    tree = ast.parse(text)
    calls = attribute_calls(tree, "set_query_context")
    require(len(calls) == 1, f"expected one set_query_context call at {revision}, found {len(calls)}")
    call = calls[0]
    keywords = sorted(keyword.arg for keyword in call.keywords if keyword.arg is not None)
    observation = {
        "keyword_names": keywords,
        "has_indirect_keyword_expansion": any(keyword.arg is None for keyword in call.keywords),
    }
    return observation, node_locator(
        repo,
        revision,
        path,
        text,
        call,
        symbol="memory.set_query_context",
    )


def agentrunbook_r_prompt_contract(repo: Path, revision: str) -> tuple[dict[str, bool], dict[str, Any]]:
    path = "memory_modules/agentrunbook_r.py"
    text = git_text(repo, revision, path)
    class_node = find_class(ast.parse(text), "AgentRunbookR")
    method = find_method(class_node, "_build_query_generation_messages")
    method_text = ast.get_source_segment(text, method) or ""
    observation = {
        "question_id_label": "Question ID:" in method_text,
        "question_type_label": "Question type:" in method_text,
        "question_image_path_label": "Question image path:" in method_text,
        "original_goals_label": "Original goals attached to this benchmark question:" in method_text,
        "question_text_label": "Question text:" in method_text,
    }
    return observation, node_locator(
        repo,
        revision,
        path,
        text,
        method,
        symbol="AgentRunbookR._build_query_generation_messages",
    )


def config_questions_path_contract(repo: Path, revision: str) -> tuple[dict[str, bool], list[dict[str, Any]]]:
    observations: dict[str, bool] = {}
    evidence: list[dict[str, Any]] = []
    for config_name in ("codex.json", "agentrunbook_c.json"):
        path = f"evaluation/memory_configs/{config_name}"
        text = git_text(repo, revision, path)
        payload = json.loads(text)
        observations[config_name] = "questions_path" in payload["memory_params"]
        evidence.append(
            source_locator(
                repo,
                revision,
                path,
                text,
                symbol="memory_params",
                start_line=1,
                end_line=len(text.splitlines()),
            )
        )
    return observations, evidence


def agentrunbook_c_contract(repo: Path, revision: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = "memory_modules/agentrunbook_c.py"
    text = git_text(repo, revision, path)
    class_node = find_class(ast.parse(text), "AgentRunbookC")
    methods = {
        node.name: node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    run_method = find_method(class_node, "_run_query_attempt")
    call_names = {
        attribute
        for attribute in (
            "_build_question_payload",
            "_normalize_output_for_query",
            "_build_memory_context_from_output",
        )
        if attribute_calls(run_method, attribute)
    }
    bases = [base.id for base in class_node.bases if isinstance(base, ast.Name)]
    observation = {
        "subclasses_codex_memory": "CodexMemory" in bases,
        "overrides_build_question_payload": "_build_question_payload" in methods,
        "overrides_normalize_output_for_query": "_normalize_output_for_query" in methods,
        "overrides_build_memory_context_from_output": "_build_memory_context_from_output" in methods,
        "run_query_attempt_calls": sorted(call_names),
    }
    first_body_line = min(getattr(node, "lineno", class_node.lineno + 1) for node in class_node.body)
    evidence = [
        source_locator(
            repo,
            revision,
            path,
            text,
            symbol="AgentRunbookC declaration",
            start_line=class_node.lineno,
            end_line=max(class_node.lineno, first_body_line - 1),
        )
    ]
    for attribute in sorted(call_names):
        call = attribute_calls(run_method, attribute)[0]
        evidence.append(
            node_locator(
                repo,
                revision,
                path,
                text,
                call,
                symbol=f"AgentRunbookC._run_query_attempt::{attribute}",
            )
        )
    return observation, evidence


def execute_agentrunbook_c_payload(repo: Path, revision: str) -> dict[str, Any]:
    _codex_module, c_module = load_revision_modules(repo, revision)
    memory = object.__new__(c_module.AgentRunbookC)
    with tempfile.TemporaryDirectory(prefix="lme-v2-question-payload-") as temp_dir:
        kwargs: dict[str, Any] = {
            "query_text": "How do I complete the task?",
            "query_image": None,
            "sandbox_dir": Path(temp_dir),
        }
        signature = inspect.signature(memory._build_question_payload)
        if "question_id" in signature.parameters:
            kwargs.update(
                {
                    "question_id": "sentinel-question-id",
                    "question_item": {
                        "id": "sentinel-question-id",
                        "question_type": "procedure-abs",
                        "question": "How do I complete the task?",
                        "answer": "sentinel-gold-answer",
                        "eval_function": "sentinel-evaluator",
                        "metadata": {"original_goal": ["sentinel-original-goal"]},
                    },
                }
            )
        return memory._build_question_payload(**kwargs)


def current_regression_test_contract(repo: Path) -> tuple[list[str], list[dict[str, Any]]]:
    path = "tests/test_query_privacy.py"
    text = git_text(repo, CURRENT_REVISION, path)
    class_node = find_class(ast.parse(text), "QueryPrivacyTest")
    required_names = [
        "test_all_backends_receive_only_opaque_query_context",
        "test_query_context_api_rejects_benchmark_metadata",
        "test_agentrunbook_r_planner_uses_only_question_text",
        "test_codex_question_payload_contains_only_query_inputs",
        "test_coding_backend_configs_do_not_reference_questions_file",
    ]
    methods = {
        node.name: node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    observed = sorted(name for name in required_names if name in methods)
    evidence = [
        node_locator(
            repo,
            CURRENT_REVISION,
            path,
            text,
            methods[name],
            symbol=f"QueryPrivacyTest.{name}",
        )
        for name in observed
    ]
    return observed, evidence


def audit_query_boundary(repo: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    release_r_expected = {
        "question_id_label": True,
        "question_type_label": True,
        "question_image_path_label": True,
        "original_goals_label": True,
        "question_text_label": True,
    }
    query_only_r_expected = {
        "question_id_label": False,
        "question_type_label": False,
        "question_image_path_label": False,
        "original_goals_label": False,
        "question_text_label": True,
    }
    c_release_expected = {
        "subclasses_codex_memory": True,
        "overrides_build_question_payload": True,
        "overrides_normalize_output_for_query": False,
        "overrides_build_memory_context_from_output": False,
        "run_query_attempt_calls": [
            "_build_memory_context_from_output",
            "_build_question_payload",
            "_normalize_output_for_query",
        ],
    }
    c_successor_expected = {**c_release_expected, "overrides_build_question_payload": False}

    revision_labels = (
        ("release", RELEASE_REVISION),
        ("fix", PRIVACY_FIX_REVISION),
        ("current", CURRENT_REVISION),
    )
    for label, revision in revision_labels:
        query_observed, query_evidence = query_context_call(repo, revision)
        expected_keywords = (
            ["question_id", "question_item", "question_type"]
            if label == "release"
            else ["query_invocation_id"]
        )
        checks.append(
            check(
                f"{label}_backend_query_context_exact_keywords",
                query_observed,
                {"keyword_names": expected_keywords, "has_indirect_keyword_expansion": False},
                query_evidence,
            )
        )

        r_observed, r_evidence = agentrunbook_r_prompt_contract(repo, revision)
        checks.append(
            check(
                f"{label}_agentrunbook_r_prompt_contract",
                r_observed,
                release_r_expected if label == "release" else query_only_r_expected,
                r_evidence,
            )
        )

        config_observed, config_evidence = config_questions_path_contract(repo, revision)
        expected_config = label == "release"
        checks.append(
            check(
                f"{label}_coding_configs_reference_questions_path",
                config_observed,
                {"codex.json": expected_config, "agentrunbook_c.json": expected_config},
                config_evidence,
            )
        )

        c_observed, c_evidence = agentrunbook_c_contract(repo, revision)
        checks.append(
            check(
                f"{label}_agentrunbook_c_inheritance_and_calls",
                c_observed,
                c_release_expected if label == "release" else c_successor_expected,
                c_evidence,
            )
        )

        payload = execute_agentrunbook_c_payload(repo, revision)
        payload_sources = [
            item
            for item in c_evidence
            if item["symbol"] in {
                "AgentRunbookC declaration",
                "AgentRunbookC._run_query_attempt::_build_question_payload",
            }
        ]
        checks.append(
            check(
                f"{label}_agentrunbook_c_question_payload_exact_output",
                payload,
                {"question": "How do I complete the task?"},
                payload_sources,
            )
        )

    tests_observed, tests_evidence = current_regression_test_contract(repo)
    expected_tests = sorted(
        [
            "test_all_backends_receive_only_opaque_query_context",
            "test_query_context_api_rejects_benchmark_metadata",
            "test_agentrunbook_r_planner_uses_only_question_text",
            "test_codex_question_payload_contains_only_query_inputs",
            "test_coding_backend_configs_do_not_reference_questions_file",
        ]
    )
    checks.append(
        check(
            "current_query_boundary_regression_tests_present_in_source",
            tests_observed,
            expected_tests,
            tests_evidence,
        )
    )
    return {
        "audit_type": "versioned_source_and_payload_boundary_audit",
        "checks": checks,
        "check_count": len(checks),
        "all_checks_passed": all(item["passed"] for item in checks),
        "interpretation": {
            "release": (
                "The backend query-context call exposed question ID, question type, and raw "
                "question item; AgentRunbook-R used benchmark-derived routing hints; both coding "
                "configs referenced questions_path. Direct execution of release AgentRunbook-C's "
                "payload builder produced query text only and did not serialize sentinel metadata or gold."
            ),
            "fix": (
                "At the 2026-08-05 revision, the exact backend call uses only an opaque invocation "
                "ID; AgentRunbook-R is query-text-only; coding configs omit questions_path; "
                "AgentRunbook-C directly produces a text-only question payload."
            ),
            "current": (
                "The current source preserves the fix-revision boundary and contains regression "
                "tests asserting it. This runner locates those tests in source; it does not execute "
                "the official test suite."
            ),
        },
    }


def trajectory_payload(trajectory_id: str, token: str, *, two_states: bool) -> dict[str, Any]:
    texts = ["Status badge: AMBER"]
    if two_states:
        texts.append(f"Status badge: {token}")
    return {
        "id": trajectory_id,
        "goal": "Inspect the final status badge.",
        "outcome": "synthetic",
        "start_url": "https://example.invalid/status",
        "actions": ["click(advance)"] if two_states else [],
        "states": [
            {
                "state_index": index,
                "step": index,
                "url": "https://example.invalid/status",
                "action": "click(advance)" if index == 0 and two_states else None,
                "thoughts": None,
                "text": text,
                "screenshot": "unused.png",
            }
            for index, text in enumerate(texts)
        ],
    }


def case_definitions(token: str, decoy_token: str, *, include_controls: bool) -> list[dict[str, Any]]:
    answer = f"## Support Analysis\nThe final badge is {token}.\n\n## Relevant Procedure and Hint Notes\nNone."
    neutral = "## Support Analysis\nRelevant state selected.\n\n## Relevant Procedure and Hint Notes\nNone."
    cases = [
        {"case": "supported_exact", "markdown": answer, "spans": [("T_SUPPORT", 1, 1)]},
        {"case": "evidence_only", "markdown": neutral, "spans": [("T_SUPPORT", 1, 1)]},
        {"case": "answer_only", "markdown": answer, "spans": []},
        {"case": "unknown_trajectory", "markdown": answer, "spans": [("T_MISSING", 0, 0)]},
        {"case": "out_of_range", "markdown": answer, "spans": [("T_SUPPORT", 99, 99)]},
        {"case": "opposite_value_decoy", "markdown": answer, "spans": [("T_DECOY", 0, 0)]},
        {
            "case": "gated_empty_supported",
            "markdown": answer,
            "spans": [],
            "gate": ("directly_supported", "answer_normally"),
        },
        {
            "case": "gated_insufficient_answer",
            "markdown": answer,
            "spans": [],
            "gate": ("insufficient", "abstain_unknown"),
        },
    ]
    if include_controls:
        cases.extend(
            [
                {
                    "case": "gated_policy_mismatch",
                    "markdown": neutral,
                    "spans": [],
                    "gate": ("directly_supported", "abstain_unknown"),
                },
                {"case": "empty_control", "markdown": "", "spans": []},
            ]
        )
    for item in cases:
        item["token"] = token
        item["decoy_token"] = decoy_token
    return cases


def materialize_fixture(workspace: Path, token: str) -> dict[str, dict[str, Any]]:
    fixtures = {
        "T_SUPPORT": trajectory_payload("T_SUPPORT", token, two_states=True),
        "T_DECOY": trajectory_payload("T_DECOY", "AMBER", two_states=False),
    }
    for trajectory_id, payload in fixtures.items():
        save_json(workspace / "trajectories" / trajectory_id / "trajectory.json", payload)
    return fixtures


def selected_evidence_text(fixtures: dict[str, dict[str, Any]], valid_spans: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for span in valid_spans:
        states = fixtures[span["trajectory_id"]]["states"]
        for state in states[span["start_state_index"] : span["end_state_index"] + 1]:
            texts.append(state["text"])
    return "\n".join(texts)


def run_case(codex_module: Any, definition: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    token = definition["token"]
    with tempfile.TemporaryDirectory(prefix="lme-v2-boundary-case-") as temp_dir:
        root = Path(temp_dir)
        workspace = root / "workspace"
        fixtures = materialize_fixture(workspace, token)
        payload: dict[str, Any] = {
            "memory_markdown": definition["markdown"],
            "trajectory_spans": [
                {
                    "trajectory_id": trajectory_id,
                    "start_state_index": start,
                    "end_state_index": end,
                }
                for trajectory_id, start, end in definition["spans"]
            ],
        }
        gate = definition.get("gate")
        require_gate = gate is not None
        if gate is not None:
            payload.update(
                {
                    "evidence_status": gate[0],
                    "evidence_status_reason": "synthetic case fixed before execution",
                    "answer_policy": gate[1],
                }
            )
        output_path = root / "memory_module_output.json"
        save_json(output_path, payload)

        memory = object.__new__(codex_module.CodexMemory)
        memory.workspace_dir = workspace
        memory.evidence_mode = "axtree"
        memory.require_evidence_gate = require_gate

        error: str | None = None
        normalized: dict[str, Any] | None = None
        context: list[dict[str, str]] = []
        try:
            normalized = memory._normalize_output_for_query(output_path)
            context = memory._build_memory_context_from_output(normalized)
        except RuntimeError as exc:
            error = str(exc)

        valid_spans = normalized["trajectory_spans_valid"] if normalized is not None else []
        invalid_spans = normalized["trajectory_spans_invalid"] if normalized is not None else []
        evidence = selected_evidence_text(fixtures, valid_spans)
        context_text = "\n".join(
            item["value"] for item in context if item.get("type") == "text"
        )
        answer_claim_in_markdown = token in definition["markdown"]
        token_in_context = token in context_text
        token_in_evidence = token in evidence
        claim_without_selected_token_support = (
            answer_claim_in_markdown and token_in_context and not token_in_evidence
        )
        first_item = context[0] if context else None

        evidence_gate_consistent: bool | None = None
        if gate is not None:
            status, policy = gate
            if status == "directly_supported":
                evidence_gate_consistent = policy == "answer_normally" and token_in_evidence
            elif status == "insufficient":
                evidence_gate_consistent = policy == "abstain_unknown" and not answer_claim_in_markdown
            else:
                evidence_gate_consistent = False

        case_id = f"{definition['case']}__{token.lower()}"
        metrics = {
            "case_id": case_id,
            "case": definition["case"],
            "token": token,
            "payload_accepted": normalized is not None,
            "error": error,
            "valid_span_count": len(valid_spans),
            "invalid_span_count": len(invalid_spans),
            "invalid_reasons": [item["reason"] for item in invalid_spans],
            "answer_claim_in_memory_markdown": answer_claim_in_markdown,
            "answer_token_in_built_memory_context": token_in_context,
            "answer_token_in_selected_evidence": token_in_evidence,
            "claim_without_selected_token_support_forwarded": claim_without_selected_token_support,
            "first_context_item_type": first_item.get("type") if first_item else None,
            "first_context_item_contains_answer": bool(first_item and token in first_item.get("value", "")),
            "evidence_gate_consistent": evidence_gate_consistent,
        }
        normalized_record = {
            "case_id": case_id,
            "normalized_output": normalized,
        }
        context_record = {
            "case_id": case_id,
            "reader_context": context,
            "selected_evidence_text": evidence,
        }
        return metrics, normalized_record, context_record


def audit_answer_evidence_binding(repo: Path, output_dir: Path) -> dict[str, Any]:
    codex_module, _agentrunbook_c_module = load_revision_modules(repo, CURRENT_REVISION)
    definitions = [
        *case_definitions("CERULEAN", "MAGENTA", include_controls=True),
        *case_definitions("MAGENTA", "CERULEAN", include_controls=False),
    ]
    cases: list[dict[str, Any]] = []
    normalized_outputs: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    for definition in definitions:
        metrics, normalized, context = run_case(codex_module, definition)
        cases.append(metrics)
        normalized_outputs.append(normalized)
        contexts.append(context)

    failing_rows = sorted(
        item["case_id"]
        for item in cases
        if item["case"]
        in {
            "answer_only",
            "unknown_trajectory",
            "out_of_range",
            "opposite_value_decoy",
            "gated_empty_supported",
            "gated_insufficient_answer",
        }
        and item["claim_without_selected_token_support_forwarded"]
    )
    mismatch = next(item for item in cases if item["case"] == "gated_policy_mismatch")
    supported = next(
        item for item in cases
        if item["case"] == "supported_exact" and item["token"] == "CERULEAN"
    )
    evidence_only = next(
        item for item in cases
        if item["case"] == "evidence_only" and item["token"] == "CERULEAN"
    )
    failing_patterns = sorted({item["case"] for item in cases if item["case_id"] in failing_rows})
    decision = {
        "audit_type": "executed_synthetic_answer_evidence_binding_test",
        "case_count": len(cases),
        "failing_patterns": failing_patterns,
        "failing_pattern_count": len(failing_patterns),
        "failing_rows": failing_rows,
        "failing_row_count": len(failing_rows),
        "token_replications_per_pattern": 2,
        "syntactic_gate_rejects_policy_mismatch": not mismatch["payload_accepted"],
        "supported_exact_accepted": supported["payload_accepted"],
        "evidence_only_accepted": evidence_only["payload_accepted"],
        "answer_evidence_binding_property_passed": (
            not failing_rows
            and not mismatch["payload_accepted"]
            and supported["payload_accepted"]
            and evidence_only["payload_accepted"]
        ),
        "interpretation": (
            "A failure means the current postprocessor does not enforce that answer-like "
            "memory_markdown included in built memory context has selected token support in "
            "these synthetic fixtures. It does not execute the reader, establish controller "
            "frequency, or alter paper-reported benchmark scores."
        ),
    }

    write_jsonl(output_dir / "cases.jsonl", cases)
    write_jsonl(output_dir / "normalized_outputs.jsonl", normalized_outputs)
    write_jsonl(output_dir / "reader_contexts.jsonl", contexts)
    save_json(output_dir / "decision.json", decision)

    fieldnames = [
        "case_id",
        "payload_accepted",
        "valid_span_count",
        "invalid_span_count",
        "answer_claim_in_memory_markdown",
        "answer_token_in_built_memory_context",
        "answer_token_in_selected_evidence",
        "claim_without_selected_token_support_forwarded",
        "evidence_gate_consistent",
        "error",
    ]
    with (output_dir / "case_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for item in cases:
            writer.writerow({field: item.get(field) for field in fieldnames})
    return decision


def write_public_fixtures(output_dir: Path) -> None:
    for token in ("CERULEAN", "MAGENTA"):
        token_root = output_dir / "fixtures" / token.lower()
        fixtures = {
            "T_SUPPORT": trajectory_payload("T_SUPPORT", token, two_states=True),
            "T_DECOY": trajectory_payload("T_DECOY", "AMBER", two_states=False),
        }
        for trajectory_id, payload in fixtures.items():
            save_json(token_root / trajectory_id / "trajectory.json", payload)


def write_hash_manifest(output_dir: Path) -> None:
    hash_path = output_dir / "sha256sums.txt"
    paths = sorted(
        path
        for path in output_dir.rglob("*")
        if path.is_file() and path != hash_path
    )
    hash_path.write_text(
        "".join(f"{sha256_file(path)}  {path.relative_to(output_dir).as_posix()}\n" for path in paths),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    repo = args.source_repo.resolve()
    output_dir = args.output_dir.resolve()
    source_revisions = validate_source_checkout(repo)
    install_python_network_guard()

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    write_public_fixtures(output_dir)

    query_boundary = audit_query_boundary(repo)
    save_json(output_dir / "query_boundary.json", query_boundary)
    answer_evidence = audit_answer_evidence_binding(repo, output_dir)

    environment = (
        f"OS: {platform.system()} {platform.release()}\n"
        f"Architecture: {platform.machine()}\n"
        f"Python: {platform.python_version()}\n"
        "Dependencies: Python standard library only\n"
        "Network: Python socket DNS/connect guard installed; local Git object reads only\n"
        "Models/readers/judges/tokenizers/embeddings: not invoked\n"
    )
    (output_dir / "environment.txt").write_text(environment, encoding="utf-8")
    source_files = {
        relative_path: sha256_file(repo / relative_path)
        for relative_path in (
            "memory_modules/codex.py",
            "memory_modules/agentrunbook_r.py",
            "memory_modules/agentrunbook_c.py",
            "memory_modules/trajectory_store.py",
            "evaluation/harness.py",
            "tests/test_query_privacy.py",
        )
    }
    save_json(
        output_dir / "run_manifest.json",
        {
            **source_revisions,
            "source_repo": "caller-supplied clean official checkout",
            "source_file_hashes": source_files,
            "target_functions": list(TARGET_FUNCTIONS),
            "import_strategy": (
                "Execute the exact current codex.py through a minimal standard-library import "
                "shim so unrelated optional benchmark dependencies are not installed."
            ),
            "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
            "network_guard": "installed",
            "fixture_tokens": ["CERULEAN", "MAGENTA", "AMBER"],
        },
    )
    write_hash_manifest(output_dir)

    summary = (
        "LongMemEval-V2 boundary audit\n"
        f"release: {RELEASE_REVISION}\n"
        f"privacy fix: {PRIVACY_FIX_REVISION}\n"
        f"current: {CURRENT_REVISION}\n"
        f"query-boundary source checks: {'PASS' if query_boundary['all_checks_passed'] else 'FAIL'}\n"
        f"answer-evidence binding property: {'PASS' if answer_evidence['answer_evidence_binding_property_passed'] else 'FAIL'}\n"
        f"failing evidence-binding patterns: {answer_evidence['failing_pattern_count']}\n"
        f"failing patterns: {', '.join(answer_evidence['failing_patterns'])}\n"
        f"failing rows after two-token replication: {answer_evidence['failing_row_count']}\n"
        f"syntactic policy mismatch rejected: {answer_evidence['syntactic_gate_rejects_policy_mismatch']}\n"
        "boundary: source lineage plus a synthetic postprocessing contract test; not a benchmark reproduction\n"
    )
    args.summary_output.resolve().write_text(summary, encoding="utf-8")
    print(summary, end="")


if __name__ == "__main__":
    main()
