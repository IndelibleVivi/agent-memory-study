#!/usr/bin/env python3
"""Deterministic source-bound audit for MNL promotion and coverage seams.

The runner loads three exact files from a reader-supplied checkout while
providing narrow standard-library stubs for optional dependencies.  It never
copies upstream source into the artifact and never contacts a model or API.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import importlib.util
import json
import math
import os
import platform
import shutil
import socket
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Iterable, Iterator


sys.dont_write_bytecode = True

ARTIFACT_ROOT = Path(__file__).resolve().parent
EXPECTED_COMMIT = "dc7de755522ad58864c62b74ab8e9959c01b7f23"
PAPER_SHA256 = "39137385c4e96bd83bfc0dfc4363733d0c91107a605999e074e5681065335c9c"
PAPER_SIZE = 5_855_586
SOURCE_FILES: dict[str, dict[str, str]] = {
    "mnl/trainer.py": {
        "sha256": "398ef9fc98ef418454cc3c243c762a65ee733cf687b94c16e80b92a6b4ce6033",
        "git_blob": "2a39b9d8921760476b3f2ae2f2d1397fcadb163a",
    },
    "mnl/evaluator.py": {
        "sha256": "47d429f2962b0423ce2a48dfaf3910d5ce2efcaacc9e69018912b3a963a90347",
        "git_blob": "be97b6e6da5157e1e7c3501961b6fad4b7d2a542",
    },
    "mnl/knowledge_base.py": {
        "sha256": "c4a62fd6b47b8ca4bd6a8265b1d218fedd3e67f5cdd52a27668ef89fd64116c5",
        "git_blob": "50483b9a18d97ef743993644f657f982a95a3d59",
    },
}

PRIMARY_FILES = (
    "cases.json",
    "run_results.jsonl",
    "decision.json",
    "source_manifest.json",
    "mutation_controls.json",
    "public_safety.json",
)
RAW_FILES = set(PRIMARY_FILES) | {
    "comparison.json",
    "environment_run_a.json",
    "environment_run_b.json",
}
ROOT_FILES = {"README.md", "PROTOCOL.md", "audit.py", "verify_checked.py", "checksums.sha256", "raw"}


class AuditFailure(RuntimeError):
    """A stable, machine-checkable audit failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise AuditFailure(code, detail)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def save_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "JSON_OBJECT", path.name)
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        require(bool(line), "JSONL_BLANK", f"{path.name}:{index}")
        value = json.loads(line)
        require(isinstance(value, dict), "JSONL_OBJECT", f"{path.name}:{index}")
        rows.append(value)
    return rows


def git_output(source: Path, *args: str) -> str:
    completed = subprocess.run(
        ["/usr/bin/git", "-C", str(source), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def item(item_id: str, outcome: str, *, group: str = "all", prompt: str = "nonempty", updated: str = "value") -> dict[str, str]:
    return {
        "group": group,
        "id": item_id,
        "observed_outcome_if_evaluated": outcome,
        "updated_prompt": prompt,
        "updated_response": updated,
    }


def batch_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "complete_positive_accept",
            "expected_source_acceptance": True,
            "items": [
                item("cpa-01", "win"), item("cpa-02", "win"),
                item("cpa-03", "win"), item("cpa-04", "loss"),
            ],
        },
        {
            "id": "complete_balanced_reject",
            "expected_source_acceptance": False,
            "items": [
                item("cbr-01", "win"), item("cbr-02", "win"),
                item("cbr-03", "loss"), item("cbr-04", "loss"),
            ],
        },
        {
            "id": "complete_all_ties_reject",
            "expected_source_acceptance": False,
            "items": [item("ctr-01", "tie"), item("ctr-02", "tie"), item("ctr-03", "tie")],
        },
        {
            "id": "partial_updated_none_survivor_accept",
            "expected_source_acceptance": True,
            "items": [
                item("pun-01", "win"), item("pun-02", "win"),
                item("pun-03", "unavailable", updated="none"),
                item("pun-04", "unavailable", updated="none"),
            ],
        },
        {
            "id": "partial_empty_prompt_survivor_accept",
            "expected_source_acceptance": True,
            "items": [
                item("pep-01", "win"), item("pep-02", "win"),
                item("pep-03", "unavailable", prompt="empty", updated="not_called"),
                item("pep-04", "unavailable", prompt="empty", updated="not_called"),
            ],
        },
        {
            "id": "all_updated_prompts_empty_rollback",
            "expected_source_acceptance": False,
            "items": [
                item("ape-01", "unavailable", prompt="empty", updated="not_called"),
                item("ape-02", "unavailable", prompt="empty", updated="not_called"),
                item("ape-03", "unavailable", prompt="empty", updated="not_called"),
            ],
        },
        {
            "id": "all_updated_responses_none_rollback",
            "expected_source_acceptance": False,
            "items": [
                item("arn-01", "unavailable", updated="none"),
                item("arn-02", "unavailable", updated="none"),
                item("arn-03", "unavailable", updated="none"),
            ],
        },
        {
            "id": "net_accept_with_group_loss",
            "expected_source_acceptance": True,
            "items": [
                item("ngl-01", "win", group="A"), item("ngl-02", "win", group="A"),
                item("ngl-03", "win", group="A"), item("ngl-04", "loss", group="B"),
            ],
        },
    ]


def cases_payload() -> dict[str, Any]:
    return {
        "batch_cases": batch_specs(),
        "probes": [
            {
                "id": "exact_subject_equal_embedding_top1",
                "kind": "knowledge_base",
                "expected": "append_two_entries_old_entry_top1",
            },
            {
                "id": "all_failed_question_denominator",
                "kind": "evaluation_coverage",
                "expected": "source_accuracy_1_enrolled_coverage_half",
            },
            {
                "id": "socket_network_guard",
                "kind": "runtime_guard",
                "expected": "zero_attempts",
            },
        ],
        "schema": "mnl-promotion-cases/1",
    }


class MiniArray:
    """Only the vector operations exercised by exact KnowledgeBase.retrieve."""

    def __init__(self, data: Any) -> None:
        if isinstance(data, MiniArray):
            data = data.data
        self.data = copy.deepcopy(data)

    def __iter__(self) -> Iterator[Any]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, index: int) -> Any:
        return self.data[index]

    def __mul__(self, other: Any) -> "MiniArray":
        if isinstance(other, MiniArray):
            return MiniArray([left * right for left, right in zip(self.data, other.data)])
        return MiniArray([value * other for value in self.data])

    def __truediv__(self, other: Any) -> "MiniArray":
        denominator = other.data if isinstance(other, MiniArray) else [other] * len(self.data)
        return MiniArray([left / right for left, right in zip(self.data, denominator)])

    def __ge__(self, other: float) -> "MiniArray":
        return MiniArray([value >= other for value in self.data])


def mini_numpy_module() -> types.ModuleType:
    module = types.ModuleType("numpy")

    def array(value: Any) -> MiniArray:
        return MiniArray(value)

    def norm(value: MiniArray, axis: int | None = None) -> Any:
        data = value.data if isinstance(value, MiniArray) else value
        if axis == 1:
            return MiniArray([math.sqrt(sum(float(part) ** 2 for part in row)) for row in data])
        return math.sqrt(sum(float(part) ** 2 for part in data))

    def dot(left: MiniArray, right: MiniArray) -> Any:
        left_data = left.data if isinstance(left, MiniArray) else left
        right_data = right.data if isinstance(right, MiniArray) else right
        if left_data and isinstance(left_data[0], list):
            return MiniArray([sum(a * b for a, b in zip(row, right_data)) for row in left_data])
        return sum(a * b for a, b in zip(left_data, right_data))

    def where(condition: MiniArray) -> tuple[list[int]]:
        return ([index for index, value in enumerate(condition.data) if value],)

    module.array = array  # type: ignore[attr-defined]
    module.dot = dot  # type: ignore[attr-defined]
    module.where = where  # type: ignore[attr-defined]
    module.linalg = types.SimpleNamespace(norm=norm)  # type: ignore[attr-defined]
    module.errstate = lambda **_kwargs: contextlib.nullcontext()  # type: ignore[attr-defined]
    module.nan_to_num = lambda value, **_kwargs: value  # type: ignore[attr-defined]
    return module


def adapter_load_jsonl(file_path: str) -> list[dict[str, Any]]:
    path = Path(file_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def adapter_save_jsonl(data: list[dict[str, Any]], file_path: str, append: bool = False) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8", newline="\n") as handle:
        for value in data:
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def adapter_batch_data(data: list[Any], batch_size: int) -> list[list[Any]]:
    return [data[index:index + batch_size] for index in range(0, len(data), batch_size)]


@contextlib.contextmanager
def loaded_exact_api(source: Path) -> Iterator[types.SimpleNamespace]:
    """Directly load the three declared source files under dependency stubs."""

    names = (
        "numpy", "mlflow", "tqdm", "mnl", "mnl.llm_client", "mnl.prompt_builder",
        "mnl.utils", "mnl.evaluator", "mnl.knowledge_base", "mnl.trainer",
    )
    sentinel = object()
    previous = {name: sys.modules.get(name, sentinel) for name in names}
    try:
        sys.modules["numpy"] = mini_numpy_module()
        sys.modules["mlflow"] = types.ModuleType("mlflow")
        tqdm_module = types.ModuleType("tqdm")
        tqdm_module.tqdm = lambda iterable, **_kwargs: iterable  # type: ignore[attr-defined]
        sys.modules["tqdm"] = tqdm_module

        package = types.ModuleType("mnl")
        package.__path__ = [str(source / "mnl")]  # type: ignore[attr-defined]
        sys.modules["mnl"] = package

        llm_module = types.ModuleType("mnl.llm_client")
        llm_module.LLMClient = object  # type: ignore[attr-defined]
        sys.modules["mnl.llm_client"] = llm_module
        prompt_module = types.ModuleType("mnl.prompt_builder")
        prompt_module.PromptBuilder = object  # type: ignore[attr-defined]
        sys.modules["mnl.prompt_builder"] = prompt_module

        utils_module = types.ModuleType("mnl.utils")
        utils_module.load_jsonl = adapter_load_jsonl  # type: ignore[attr-defined]
        utils_module.save_jsonl = adapter_save_jsonl  # type: ignore[attr-defined]
        utils_module.batch_data = adapter_batch_data  # type: ignore[attr-defined]
        utils_module.setup_mlflow = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
        utils_module.log_metrics_to_mlflow = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
        sys.modules["mnl.utils"] = utils_module

        loaded: dict[str, types.ModuleType] = {}
        for module_name, relative in (
            ("mnl.evaluator", "mnl/evaluator.py"),
            ("mnl.knowledge_base", "mnl/knowledge_base.py"),
            ("mnl.trainer", "mnl/trainer.py"),
        ):
            spec = importlib.util.spec_from_file_location(module_name, source / relative)
            require(spec is not None and spec.loader is not None, "SOURCE_IMPORT_SPEC", relative)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            loaded[module_name] = module
        yield types.SimpleNamespace(
            Evaluator=loaded["mnl.evaluator"].Evaluator,
            KnowledgeBase=loaded["mnl.knowledge_base"].KnowledgeBase,
            PromptTuner=loaded["mnl.trainer"].PromptTuner,
        )
    finally:
        for name, value in previous.items():
            if value is sentinel:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value  # type: ignore[assignment]


@contextlib.contextmanager
def blocked_network() -> Iterator[dict[str, int]]:
    attempts = {"count": 0}
    original_socket = socket.socket
    original_create = socket.create_connection

    def deny(*_args: Any, **_kwargs: Any) -> Any:
        attempts["count"] += 1
        raise AuditFailure("NETWORK_ATTEMPT")

    socket.socket = deny  # type: ignore[assignment]
    socket.create_connection = deny  # type: ignore[assignment]
    try:
        yield attempts
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create  # type: ignore[assignment]


def configure_tuner(api: types.SimpleNamespace, fake: Any, kb: Any, reward_fn: Any) -> Any:
    tuner = object.__new__(api.PromptTuner)
    tuner.llm_client = fake
    tuner.knowledge_base = kb
    tuner.evaluator = api.Evaluator(reward_fn=reward_fn, llm_client=fake)
    tuner.step_count = 0
    tuner.negative_optimization_cases = []
    tuner.cumulative_stats = {
        "total_wins": 0, "total_losses": 0, "total_ties": 0, "total_comparisons": 0,
    }
    return tuner


def run_batch_case(api: types.SimpleNamespace, spec: dict[str, Any], work_root: Path) -> dict[str, Any]:
    item_by_id = {value["id"]: value for value in spec["items"]}

    class FakeLLM:
        def __init__(self) -> None:
            self.generation_logs: list[list[str]] = []
            self.reward_calls: list[str] = []

        def classify_subjects(self, questions: list[str]) -> list[str]:
            return [f"subject::{question}" for question in questions]

        def batch_generate(self, prompts: list[str], system_prompt: Any, **_kwargs: Any) -> list[Any]:
            del system_prompt
            ids = list(prompts)
            self.generation_logs.append(ids)
            if len(self.generation_logs) == 1:
                return [f"baseline::{value}" for value in ids]
            return [
                None if item_by_id[value]["updated_response"] == "none" else f"updated::{value}"
                for value in ids
            ]

        def get_embedding(self, _subject: str) -> list[float]:
            return [1.0, 0.0]

    fake = FakeLLM()
    storage = work_root / f"{spec['id']}.jsonl"
    initial_entries = [{"embedding": [0.0, 1.0], "guidance": "prestate", "subject": "preexisting"}]
    adapter_save_jsonl(initial_entries, str(storage), append=False)
    kb = api.KnowledgeBase(storage_path=str(storage), llm_client=fake, max_guidance_length=500)

    def reward(question: str, _updated: str, _baseline: str, _standard: str) -> list[float]:
        fake.reward_calls.append(question)
        outcome = item_by_id[question]["observed_outcome_if_evaluated"]
        if outcome == "win":
            return [1, 0]
        if outcome == "loss":
            return [0, 1]
        if outcome == "tie":
            return [0.5, 0.5]
        raise AuditFailure("UNAVAILABLE_WAS_EVALUATED", question)

    tuner = configure_tuner(api, fake, kb, reward)
    retrieval_calls = {"count": 0, "updated_nonempty_ids": []}

    def retrieve(_self: Any, subjects: list[str], **_kwargs: Any) -> list[str]:
        retrieval_calls["count"] += 1
        ids = [value.split("subject::", 1)[1] for value in subjects]
        if retrieval_calls["count"] == 1:
            return [f"baseline-guidance::{value}" for value in ids]
        nonempty = [value for value in ids if item_by_id[value]["updated_prompt"] == "nonempty"]
        retrieval_calls["updated_nonempty_ids"] = nonempty
        return [
            f"updated-guidance::{value}" if item_by_id[value]["updated_prompt"] == "nonempty" else ""
            for value in ids
        ]

    def generate(_self: Any, **_kwargs: Any) -> dict[str, str]:
        return {f"audit::{spec['id']}": f"guidance::{spec['id']}"}

    tuner._retrieve_guidance_for_batch = types.MethodType(retrieve, tuner)
    tuner._generate_guidance_for_batch = types.MethodType(generate, tuner)

    pre_memory = copy.deepcopy(kb.entries)
    pre_bytes = storage.read_bytes()
    source_result = tuner._process_batch(
        [{"question": value["id"], "answer": f"standard::{value['id']}"} for value in spec["items"]],
        update_knowledge_base=True,
    )
    post_memory = copy.deepcopy(kb.entries)
    post_bytes = storage.read_bytes()
    post_serialized = adapter_load_jsonl(str(storage))

    original_ids = [value["id"] for value in spec["items"]]
    baseline_valid_ids = fake.generation_logs[0] if fake.generation_logs else []
    prompt_nonempty_ids = list(retrieval_calls["updated_nonempty_ids"])
    updated_generation_ids = fake.generation_logs[1] if len(fake.generation_logs) > 1 else []
    updated_response_valid_ids = [
        value for value in updated_generation_ids if item_by_id[value]["updated_response"] != "none"
    ]
    evaluated_ids = list(fake.reward_calls)
    dispositions: dict[str, str] = {}
    for value in original_ids:
        fixture = item_by_id[value]
        if value in evaluated_ids:
            dispositions[value] = f"observed_{fixture['observed_outcome_if_evaluated']}"
        elif fixture["updated_prompt"] == "empty":
            dispositions[value] = "filtered_empty_updated_prompt"
        elif fixture["updated_response"] == "none":
            dispositions[value] = "updated_response_unavailable"
        else:
            dispositions[value] = "unexpected_not_evaluated"

    observed = [item_by_id[value]["observed_outcome_if_evaluated"] for value in evaluated_ids]
    wins, losses, ties = observed.count("win"), observed.count("loss"), observed.count("tie")
    missing_count = len(original_ids) - len(evaluated_ids)
    accepted = source_result is not None
    memory_delta = len(post_memory) - len(pre_memory)
    expected_entry = {
        "embedding": [1.0, 0.0],
        "guidance": f"guidance::{spec['id']}",
        "subject": f"audit::{spec['id']}",
    }
    group_deltas: dict[str, int] = {}
    for group in sorted({value["group"] for value in spec["items"]}):
        group_outcomes = [
            item_by_id[value]["observed_outcome_if_evaluated"]
            for value in evaluated_ids if item_by_id[value]["group"] == group
        ]
        group_deltas[group] = group_outcomes.count("win") - group_outcomes.count("loss")

    return {
        "admission": {
            "full_enrolled_decision": (
                ("ACCEPT" if wins - losses > 0 else "REJECT")
                if missing_count == 0 else "UNDEFINED_FROM_OBSERVED_RESULTS"
            ),
            "source_accepted": accepted,
            "source_observed_delta": wins - losses,
            "source_observed_losses": losses,
            "source_observed_ties": ties,
            "source_observed_wins": wins,
        },
        "case_id": spec["id"],
        "expected_source_acceptance": spec["expected_source_acceptance"],
        "group_observed_deltas": group_deltas,
        "identity_ledger": {
            "baseline_valid_ids": baseline_valid_ids,
            "dispositions": dispositions,
            "evaluated_ids": evaluated_ids,
            "original_ids": original_ids,
            "updated_generation_ids": updated_generation_ids,
            "updated_prompt_nonempty_ids": prompt_nonempty_ids,
            "updated_response_valid_ids": updated_response_valid_ids,
        },
        "kb_state": {
            "accepted_entry_exact": expected_entry in post_memory,
            "in_memory_delta": memory_delta,
            "in_memory_post_sha256": digest_value(post_memory),
            "in_memory_pre_sha256": digest_value(pre_memory),
            "serialized_matches_in_memory": post_serialized == post_memory,
            "serialized_post_sha256": sha256_bytes(post_bytes),
            "serialized_pre_sha256": sha256_bytes(pre_bytes),
        },
        "kind": "batch_promotion",
        "missing_as_failure_sensitivity": {
            "assumption": "counterfactual_unavailable_as_loss",
            "counterfactual_delta": wins - losses - missing_count,
            "missing_count": missing_count,
            "not_observed_source_outcomes": True,
            "would_accept": wins - losses - missing_count > 0,
        },
        "schema": "mnl-batch-result/1",
        "source_return": "METRICS" if source_result is not None else "NONE",
    }


def run_knowledge_base_probe(api: types.SimpleNamespace, work_root: Path) -> dict[str, Any]:
    class Embeddings:
        def get_embedding(self, _subject: str) -> list[float]:
            return [1.0, 0.0]

    storage = work_root / "exact-subject.jsonl"
    initial = [{"embedding": [1.0, 0.0], "guidance": "older-guidance", "subject": "shared-subject"}]
    adapter_save_jsonl(initial, str(storage), append=False)
    kb = api.KnowledgeBase(storage_path=str(storage), llm_client=Embeddings(), max_guidance_length=500)
    kb.update_entry("shared-subject", "newer-guidance")
    kb._save_entries()
    retrieved = kb.retrieve_by_subject("shared-subject", top_k=1, threshold=0.0)
    return {
        "entry_count_after": len(kb.entries),
        "entry_count_before": len(initial),
        "exact_subject_count_after": sum(value.get("subject") == "shared-subject" for value in kb.entries),
        "id": "exact_subject_equal_embedding_top1",
        "kind": "knowledge_base",
        "schema": "mnl-knowledge-base-result/1",
        "serialized_matches_in_memory": adapter_load_jsonl(str(storage)) == kb.entries,
        "top1_guidance": retrieved[0]["entry"]["guidance"] if retrieved else None,
        "top1_similarity": retrieved[0]["similarity"] if retrieved else None,
    }


def run_eval_probe(api: types.SimpleNamespace) -> dict[str, Any]:
    class EvalLLM:
        def __init__(self) -> None:
            self.generated_ids: list[str] = []

        def batch_generate(self, prompts: list[str], system_prompt: Any, **_kwargs: Any) -> list[Any]:
            del system_prompt
            self.generated_ids.extend(prompts)
            return ["correct" if value == "eval-01" else None for value in prompts]

    fake = EvalLLM()

    def reward(_question: str, candidate: str, _other: str, standard: str) -> list[int]:
        return [1, 0] if candidate == standard else [0, 1]

    tuner = configure_tuner(api, fake, types.SimpleNamespace(), reward)
    tuner.eval_batch_size = 10
    tuner.eval_at_n = 1
    tuner.eval_retrieval_top_k = 3
    tuner.eval_retrieval_threshold = 0.7

    def retrieve(_self: Any, subjects: list[str], **_kwargs: Any) -> list[str]:
        return ["eval-guidance"] * len(subjects)

    tuner._retrieve_guidance_for_batch = types.MethodType(retrieve, tuner)
    enrolled = [
        {"question": "eval-01", "answer": "correct"},
        {"question": "eval-02", "answer": "correct"},
    ]
    accuracy = tuner._evaluate_on_eval_set(enrolled, is_retrieval_subject=False, eval_at_n=1)
    surviving = 1
    return {
        "all_failed_question_omitted_from_denominator": True,
        "enrolled_count": len(enrolled),
        "enrolled_coverage": surviving / len(enrolled),
        "generated_ids": fake.generated_ids,
        "id": "all_failed_question_denominator",
        "kind": "evaluation_coverage",
        "schema": "mnl-eval-coverage-result/1",
        "source_reported_accuracy": accuracy,
        "surviving_question_count": surviving,
    }


def expected_ledger(spec: dict[str, Any]) -> dict[str, Any]:
    original = [value["id"] for value in spec["items"]]
    prompt_valid = [value["id"] for value in spec["items"] if value["updated_prompt"] == "nonempty"]
    response_valid = [
        value["id"] for value in spec["items"]
        if value["updated_prompt"] == "nonempty" and value["updated_response"] != "none"
    ]
    dispositions = {}
    for value in spec["items"]:
        if value["id"] in response_valid:
            dispositions[value["id"]] = f"observed_{value['observed_outcome_if_evaluated']}"
        elif value["updated_prompt"] == "empty":
            dispositions[value["id"]] = "filtered_empty_updated_prompt"
        else:
            dispositions[value["id"]] = "updated_response_unavailable"
    return {
        "baseline_valid_ids": original,
        "dispositions": dispositions,
        "evaluated_ids": response_valid,
        "original_ids": original,
        "updated_generation_ids": prompt_valid,
        "updated_prompt_nonempty_ids": prompt_valid,
        "updated_response_valid_ids": response_valid,
    }


def index_results(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row.get("kind"), row.get("case_id", row.get("id")))
        require(all(isinstance(part, str) for part in key), "RESULT_KEY")
        require(key not in indexed, "RESULT_DUPLICATE", str(key))
        indexed[key] = row
    return indexed


def validate_results(cases: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    require(cases == cases_payload(), "CASES_DRIFT")
    indexed = index_results(rows)
    expected_keys = {("batch_promotion", spec["id"]) for spec in batch_specs()} | {
        ("knowledge_base", "exact_subject_equal_embedding_top1"),
        ("evaluation_coverage", "all_failed_question_denominator"),
        ("runtime_guard", "socket_network_guard"),
    }
    require(set(indexed) == expected_keys, "RESULT_SET")

    for spec in batch_specs():
        row = indexed[("batch_promotion", spec["id"])]
        require(row.get("schema") == "mnl-batch-result/1", "BATCH_SCHEMA", spec["id"])
        ledger = row.get("identity_ledger")
        expected = expected_ledger(spec)
        require(isinstance(ledger, dict), "BATCH_LEDGER", spec["id"])
        require(ledger.get("original_ids") == expected["original_ids"], "BATCH_ORIGINAL_IDS", spec["id"])
        require(ledger.get("baseline_valid_ids") == expected["baseline_valid_ids"], "BATCH_BASELINE_IDS", spec["id"])
        require(ledger.get("updated_prompt_nonempty_ids") == expected["updated_prompt_nonempty_ids"], "BATCH_PROMPT_IDS", spec["id"])
        require(ledger.get("updated_generation_ids") == expected["updated_generation_ids"], "BATCH_GENERATION_IDS", spec["id"])
        require(ledger.get("updated_response_valid_ids") == expected["updated_response_valid_ids"], "BATCH_RESPONSE_IDS", spec["id"])
        require(ledger.get("evaluated_ids") == expected["evaluated_ids"], "BATCH_EVALUATED_IDS", spec["id"])
        require(ledger.get("dispositions") == expected["dispositions"], "BATCH_DISPOSITIONS", spec["id"])

        observed = [
            value["observed_outcome_if_evaluated"]
            for value in spec["items"] if value["id"] in expected["evaluated_ids"]
        ]
        wins, losses, ties = observed.count("win"), observed.count("loss"), observed.count("tie")
        admission = row.get("admission", {})
        require(admission.get("source_observed_wins") == wins, "BATCH_WINS", spec["id"])
        require(admission.get("source_observed_losses") == losses, "BATCH_LOSSES", spec["id"])
        require(admission.get("source_observed_ties") == ties, "BATCH_TIES", spec["id"])
        require(admission.get("source_observed_delta") == wins - losses, "BATCH_DELTA", spec["id"])
        require(admission.get("source_accepted") is spec["expected_source_acceptance"], "BATCH_ACCEPTANCE", spec["id"])
        missing = len(spec["items"]) - len(expected["evaluated_ids"])
        full_decision = ("ACCEPT" if wins - losses > 0 else "REJECT") if missing == 0 else "UNDEFINED_FROM_OBSERVED_RESULTS"
        require(admission.get("full_enrolled_decision") == full_decision, "BATCH_FULL_DECISION", spec["id"])
        sensitivity = row.get("missing_as_failure_sensitivity", {})
        require(sensitivity.get("missing_count") == missing, "BATCH_MISSING_COUNT", spec["id"])
        require(sensitivity.get("counterfactual_delta") == wins - losses - missing, "BATCH_SENSITIVITY", spec["id"])
        require(sensitivity.get("not_observed_source_outcomes") is True, "BATCH_SENSITIVITY_LABEL", spec["id"])

        kb = row.get("kb_state", {})
        if spec["expected_source_acceptance"]:
            require(kb.get("in_memory_delta") == 1, "KB_ACCEPTED_DELTA", spec["id"])
            require(kb.get("accepted_entry_exact") is True, "KB_ACCEPTED_ENTRY", spec["id"])
            require(kb.get("in_memory_post_sha256") != kb.get("in_memory_pre_sha256"), "KB_ACCEPTED_MEMORY", spec["id"])
            require(kb.get("serialized_post_sha256") != kb.get("serialized_pre_sha256"), "KB_ACCEPTED_SERIALIZED", spec["id"])
            require(row.get("source_return") == "METRICS", "BATCH_ACCEPTED_RETURN", spec["id"])
        else:
            require(kb.get("in_memory_delta") == 0, "KB_REJECTED_DELTA", spec["id"])
            require(kb.get("in_memory_post_sha256") == kb.get("in_memory_pre_sha256"), "KB_REJECTED_MEMORY", spec["id"])
            require(kb.get("serialized_post_sha256") == kb.get("serialized_pre_sha256"), "KB_REJECTED_SERIALIZED", spec["id"])
            require(row.get("source_return") == "NONE", "BATCH_REJECTED_RETURN", spec["id"])
        require(kb.get("serialized_matches_in_memory") is True, "KB_SERIALIZATION_BINDING", spec["id"])

    kb_row = indexed[("knowledge_base", "exact_subject_equal_embedding_top1")]
    require(kb_row.get("entry_count_before") == 1 and kb_row.get("entry_count_after") == 2, "KB_APPEND_COUNT")
    require(kb_row.get("exact_subject_count_after") == 2, "KB_EXACT_SUBJECT_COUNT")
    require(kb_row.get("top1_guidance") == "older-guidance", "KB_TOP1")
    require(kb_row.get("top1_similarity") == 1.0, "KB_TOP1_SIMILARITY")
    require(kb_row.get("serialized_matches_in_memory") is True, "KB_PROBE_SERIALIZATION")

    eval_row = indexed[("evaluation_coverage", "all_failed_question_denominator")]
    require(eval_row.get("enrolled_count") == 2, "EVAL_ENROLLED")
    require(eval_row.get("surviving_question_count") == 1, "EVAL_SURVIVING")
    require(eval_row.get("source_reported_accuracy") == 1.0, "EVAL_ACCURACY")
    require(eval_row.get("enrolled_coverage") == 0.5, "EVAL_COVERAGE")
    require(eval_row.get("all_failed_question_omitted_from_denominator") is True, "EVAL_OMISSION")
    guard = indexed[("runtime_guard", "socket_network_guard")]
    require(guard.get("attempts") == 0 and guard.get("status") == "PASS", "NETWORK_GUARD")


def mutation_controls(cases: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    controls: list[dict[str, Any]] = []

    def check(control_id: str, expected_code: str, mutate: Any) -> None:
        altered = copy.deepcopy(rows)
        mutate(index_results(altered))
        observed_code = None
        try:
            validate_results(cases, altered)
        except AuditFailure as exc:
            observed_code = exc.code
        controls.append({
            "detected": observed_code == expected_code,
            "expected_error_code": expected_code,
            "id": control_id,
            "observed_error_code": observed_code,
        })

    check(
        "delete_original_identity",
        "BATCH_ORIGINAL_IDS",
        lambda idx: idx[("batch_promotion", "complete_positive_accept")]["identity_ledger"]["original_ids"].pop(),
    )
    check(
        "flip_source_admission",
        "BATCH_ACCEPTANCE",
        lambda idx: idx[("batch_promotion", "complete_positive_accept")]["admission"].update(source_accepted=False),
    )
    check(
        "relabel_unavailable_as_observed_loss",
        "BATCH_DISPOSITIONS",
        lambda idx: idx[("batch_promotion", "partial_updated_none_survivor_accept")]["identity_ledger"]["dispositions"].update({"pun-03": "observed_loss"}),
    )
    check(
        "alter_rejected_serialized_poststate",
        "KB_REJECTED_SERIALIZED",
        lambda idx: idx[("batch_promotion", "complete_balanced_reject")]["kb_state"].update(serialized_post_sha256="0" * 64),
    )
    check(
        "change_eval_enrolled_denominator",
        "EVAL_ENROLLED",
        lambda idx: idx[("evaluation_coverage", "all_failed_question_denominator")].update(enrolled_count=1),
    )
    check(
        "replace_stable_top1_with_new_entry",
        "KB_TOP1",
        lambda idx: idx[("knowledge_base", "exact_subject_equal_embedding_top1")].update(top1_guidance="newer-guidance"),
    )
    return {
        "all_detected": all(value["detected"] for value in controls),
        "controls": controls,
        "schema": "mnl-mutation-controls/1",
    }


def derive_decision(rows: list[dict[str, Any]], controls: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    indexed = index_results(rows)
    incomplete_accepts = [
        spec["id"] for spec in batch_specs()
        if indexed[("batch_promotion", spec["id"])]["admission"]["source_accepted"]
        and indexed[("batch_promotion", spec["id"])]["admission"]["full_enrolled_decision"]
        == "UNDEFINED_FROM_OBSERVED_RESULTS"
    ]
    group_case = indexed[("batch_promotion", "net_accept_with_group_loss")]
    eval_case = indexed[("evaluation_coverage", "all_failed_question_denominator")]
    kb_case = indexed[("knowledge_base", "exact_subject_equal_embedding_top1")]
    observations = manifest.get("checkout_observations", {})
    readiness = (
        observations.get("git_status_clean_before") is True
        and observations.get("git_status_clean_after") is True
        and observations.get("allowlisted_bytes_match_lock_before") is True
        and observations.get("allowlisted_bytes_match_lock_after") is True
        and controls.get("all_detected") is True
        and incomplete_accepts == [
            "partial_updated_none_survivor_accept",
            "partial_empty_prompt_survivor_accept",
        ]
        and group_case["group_observed_deltas"].get("B") == -1
        and eval_case.get("source_reported_accuracy") == 1.0
        and eval_case.get("enrolled_coverage") == 0.5
        and kb_case.get("top1_guidance") == "older-guidance"
        and indexed[("runtime_guard", "socket_network_guard")].get("attempts") == 0
    )
    return {
        "batch_case_count": len(batch_specs()),
        "canonical_ams_status": {
            "public_note_depth": "not_assessed_by_evidence_artifact",
        },
        "complete_cohort_controls": "PASS",
        "evidence_artifact_readiness": "PASS" if readiness else "HOLD",
        "evaluation_denominator_probe": {
            "enrolled_coverage": eval_case["enrolled_coverage"],
            "source_reported_accuracy": eval_case["source_reported_accuracy"],
        },
        "exact_subject_top1_probe": "OLDER_ENTRY_RETURNED_AFTER_APPEND",
        "full_cohort_status_for_filtered_admissions": "UNDEFINED_FROM_OBSERVED_RESULTS",
        "incomplete_survivor_admissions": incomplete_accepts,
        "model_or_api_calls": 0,
        "paper_or_benchmark_experiment_reproduction": "NOT_ATTEMPTED",
        "schema": "mnl-promotion-decision/1",
        "source_commit": EXPECTED_COMMIT,
        "source_to_paper_revision_binding": "NOT_ESTABLISHED",
        "subgroup_non_regression_guarantee": "NOT_ESTABLISHED_BY_NET_BATCH_ACCEPTANCE",
    }


def source_manifest(source: Path, paper_pdf: Path) -> dict[str, Any]:
    files = []
    for relative, expected in SOURCE_FILES.items():
        path = source / relative
        require(path.is_file(), "SOURCE_FILE_MISSING", relative)
        observed_sha = sha256_path(path)
        observed_blob = git_output(source, "rev-parse", f"HEAD:{relative}")
        require(observed_sha == expected["sha256"], "SOURCE_FILE_SHA", relative)
        require(observed_blob == expected["git_blob"], "SOURCE_FILE_BLOB", relative)
        files.append({"git_blob": observed_blob, "path": relative, "sha256": observed_sha})
    return {
        "checkout_observations": {
            "allowlisted_bytes_match_lock_after": True,
            "allowlisted_bytes_match_lock_before": True,
            "git_status_clean_after": True,
            "git_status_clean_before": True,
            "transient_or_ignored_writes_instrumented": False,
        },
        "paper": {
            "acl_anthology_id": "2026.findings-acl.719",
            "physical_page_count_reviewed": 17,
            "sha256": sha256_path(paper_pdf),
            "size_bytes": paper_pdf.stat().st_size,
        },
        "schema": "mnl-source-manifest/2",
        "source": {
            "commit": EXPECTED_COMMIT,
            "paper_production_revision_binding": "NOT_ESTABLISHED",
            "read_access_instrumented": False,
            "runner_declared_source_code_read_allowlist": files,
            "upstream_source_copied_into_artifact": False,
        },
        "source_methods_executed": [
            "PromptTuner._process_batch",
            "PromptTuner._evaluate_on_eval_set",
            "Evaluator.evaluate_batch",
            "Evaluator.evaluate_single",
            "KnowledgeBase.update_entry",
            "KnowledgeBase._save_entries",
            "KnowledgeBase.retrieve_by_subject",
        ],
        "synthetic_adapters": [
            "classification_and_generation",
            "embedding_and_reward",
            "jsonl_load_save",
            "batch_splitter",
            "minimal_vector_operations",
            "optional_import_modules",
        ],
    }


def scan_public_payloads(payloads: dict[str, bytes]) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    slash = b"/"
    path_markers = (
        slash + b"Users" + slash,
        slash + b"Volumes" + slash,
        slash + b"home" + slash,
        b"file" + b"://",
    )
    secret_markers = (
        b"BEGIN " + b"PRIVATE KEY",
        b"api" + b"_key",
        b"access" + b"_token",
        b"refresh" + b"_token",
    )
    for name, payload in payloads.items():
        for marker in path_markers:
            if marker in payload:
                hits.append({"category": "local_path", "file": name})
        for marker in secret_markers:
            if marker.lower() in payload.lower():
                hits.append({"category": "credential_marker", "file": name})
    return {
        "copied_upstream_source": False,
        "denied_content_hits": hits,
        "no_local_paths_credentials_or_upstream_source": not hits,
        "scan_scope": sorted(payloads),
        "schema": "mnl-public-safety/1",
    }


def environment_receipt(run_label: str) -> dict[str, Any]:
    return {
        "hash_seed": os.environ.get("PYTHONHASHSEED"),
        "locale": os.environ.get("LC_ALL"),
        "machine": platform.machine(),
        "operating_system": platform.system(),
        "python": platform.python_version(),
        "run_label": run_label,
        "schema": "mnl-environment/1",
        "timezone": os.environ.get("TZ"),
    }


def read_primary(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    raw = root / "raw"
    return (
        load_json(raw / "cases.json"),
        load_jsonl(raw / "run_results.jsonl"),
        load_json(raw / "decision.json"),
        load_json(raw / "source_manifest.json"),
        load_json(raw / "mutation_controls.json"),
        load_json(raw / "public_safety.json"),
    )


def validate_primary(root: Path) -> None:
    cases, rows, decision, manifest, controls, safety = read_primary(root)
    validate_results(cases, rows)
    require(manifest.get("schema") == "mnl-source-manifest/2", "MANIFEST_SCHEMA")
    require(manifest.get("source", {}).get("commit") == EXPECTED_COMMIT, "MANIFEST_COMMIT")
    require(manifest.get("paper", {}).get("sha256") == PAPER_SHA256, "MANIFEST_PAPER_SHA")
    require(manifest.get("paper", {}).get("size_bytes") == PAPER_SIZE, "MANIFEST_PAPER_SIZE")
    observations = manifest.get("checkout_observations", {})
    require(observations.get("git_status_clean_before") is True, "MANIFEST_CLEAN_BEFORE")
    require(observations.get("git_status_clean_after") is True, "MANIFEST_CLEAN_AFTER")
    require(observations.get("allowlisted_bytes_match_lock_before") is True, "MANIFEST_BYTES_BEFORE")
    require(observations.get("allowlisted_bytes_match_lock_after") is True, "MANIFEST_BYTES_AFTER")
    require(observations.get("transient_or_ignored_writes_instrumented") is False, "MANIFEST_INSTRUMENTATION_BOUNDARY")
    expected_controls = mutation_controls(cases, rows)
    require(controls == expected_controls, "MUTATION_RECEIPT")
    expected_decision = derive_decision(rows, controls, manifest)
    require(decision == expected_decision, "DECISION_REDERIVATION")
    base_payloads = {
        "cases.json": (root / "raw/cases.json").read_bytes(),
        "run_results.jsonl": (root / "raw/run_results.jsonl").read_bytes(),
        "decision.json": (root / "raw/decision.json").read_bytes(),
        "source_manifest.json": (root / "raw/source_manifest.json").read_bytes(),
        "mutation_controls.json": (root / "raw/mutation_controls.json").read_bytes(),
    }
    require(safety == scan_public_payloads(base_payloads), "PUBLIC_SAFETY_REDERIVATION")
    require(safety.get("no_local_paths_credentials_or_upstream_source") is True, "PUBLIC_SAFETY_GATE")
    require(decision.get("evidence_artifact_readiness") == "PASS", "READINESS_GATE")


def run_once(source: Path, paper_pdf: Path, output: Path, run_label: str) -> None:
    require(os.environ.get("TZ") == "UTC", "ENV_TZ", "run requires TZ=UTC")
    require(os.environ.get("LC_ALL") == "C.UTF-8", "ENV_LOCALE", "run requires LC_ALL=C.UTF-8")
    expected_seed = {"A": "313", "B": "727"}.get(run_label)
    require(expected_seed is not None, "RUN_LABEL")
    require(os.environ.get("PYTHONHASHSEED") == expected_seed, "ENV_HASH_SEED", f"run {run_label}")
    require(source.is_dir(), "SOURCE_ROOT")
    require(paper_pdf.is_file(), "PAPER_PDF")
    require(not output.exists(), "OUTPUT_EXISTS", str(output))
    require(not is_within(output, source), "OUTPUT_INSIDE_SOURCE")
    require(git_output(source, "rev-parse", "HEAD") == EXPECTED_COMMIT, "SOURCE_COMMIT")
    require(git_output(source, "status", "--porcelain") == "", "SOURCE_DIRTY_PRE")
    require(sha256_path(paper_pdf) == PAPER_SHA256, "PAPER_SHA")
    require(paper_pdf.stat().st_size == PAPER_SIZE, "PAPER_SIZE")
    for relative, expected in SOURCE_FILES.items():
        require(sha256_path(source / relative) == expected["sha256"], "SOURCE_FILE_SHA", relative)

    output.mkdir(parents=True)
    raw = output / "raw"
    work = output / "work"
    raw.mkdir()
    work.mkdir()
    cases = cases_payload()
    with loaded_exact_api(source) as api:
        with blocked_network() as network:
            rows = [run_batch_case(api, spec, work) for spec in batch_specs()]
            rows.append(run_knowledge_base_probe(api, work))
            rows.append(run_eval_probe(api))
        rows.append({
            "attempts": network["count"],
            "id": "socket_network_guard",
            "kind": "runtime_guard",
            "schema": "mnl-runtime-guard-result/1",
            "status": "PASS" if network["count"] == 0 else "FAIL",
        })
    require(git_output(source, "status", "--porcelain") == "", "SOURCE_DIRTY_POST")
    for relative, expected in SOURCE_FILES.items():
        require(sha256_path(source / relative) == expected["sha256"], "SOURCE_FILE_SHA_POST", relative)
    manifest = source_manifest(source, paper_pdf)
    validate_results(cases, rows)
    controls = mutation_controls(cases, rows)
    require(controls["all_detected"] is True, "MUTATION_GATE")
    decision = derive_decision(rows, controls, manifest)
    require(decision["evidence_artifact_readiness"] == "PASS", "READINESS_GATE")

    save_json(raw / "cases.json", cases)
    save_jsonl(raw / "run_results.jsonl", rows)
    save_json(raw / "decision.json", decision)
    save_json(raw / "source_manifest.json", manifest)
    save_json(raw / "mutation_controls.json", controls)
    public_payloads = {
        "cases.json": (raw / "cases.json").read_bytes(),
        "run_results.jsonl": (raw / "run_results.jsonl").read_bytes(),
        "decision.json": (raw / "decision.json").read_bytes(),
        "source_manifest.json": (raw / "source_manifest.json").read_bytes(),
        "mutation_controls.json": (raw / "mutation_controls.json").read_bytes(),
    }
    save_json(raw / "public_safety.json", scan_public_payloads(public_payloads))
    save_json(raw / "environment.json", environment_receipt(run_label))
    validate_primary(output)
    print(f"Run {run_label}: 8 batch cases + KB/eval probes PASS; zero network attempts.")


def compare_runs(run_a: Path, run_b: Path, output: Path) -> None:
    require(not output.exists(), "COMPARE_OUTPUT_EXISTS")
    validate_primary(run_a)
    validate_primary(run_b)
    files: dict[str, dict[str, str]] = {}
    for name in PRIMARY_FILES:
        left = (run_a / "raw" / name).read_bytes()
        right = (run_b / "raw" / name).read_bytes()
        require(left == right, "RUN_BYTE_MISMATCH", name)
        files[name] = {"run_a_sha256": sha256_bytes(left), "run_b_sha256": sha256_bytes(right)}
    receipt = {
        "byte_identical": True,
        "primary_file_count": len(PRIMARY_FILES),
        "primary_files": files,
        "run_a_hash_seed": load_json(run_a / "raw/environment.json")["hash_seed"],
        "run_b_hash_seed": load_json(run_b / "raw/environment.json")["hash_seed"],
        "schema": "mnl-run-comparison/1",
    }
    require(receipt["run_a_hash_seed"] == "313" and receipt["run_b_hash_seed"] == "727", "COMPARE_SEEDS")
    save_json(output, receipt)
    print("Run A/B stable primary receipts are byte-identical under distinct hash seeds.")


def artifact_paths(root: Path) -> list[Path]:
    return sorted(
        [root / name for name in ("README.md", "PROTOCOL.md", "audit.py", "verify_checked.py")]
        + [root / "raw" / name for name in sorted(RAW_FILES)],
        key=lambda path: path.relative_to(root).as_posix(),
    )


def write_checksums(root: Path) -> None:
    paths = artifact_paths(root)
    for path in paths:
        require(path.is_file(), "CHECKSUM_INPUT_MISSING", path.relative_to(root).as_posix())
    lines = [f"{sha256_path(path)}  {path.relative_to(root).as_posix()}" for path in paths]
    (root / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def install_runs(run_a: Path, run_b: Path, comparison: Path, artifact_root: Path) -> None:
    validate_primary(run_a)
    validate_primary(run_b)
    comparison_payload = load_json(comparison)
    require(comparison_payload.get("byte_identical") is True, "COMPARE_RECEIPT")
    require(comparison_payload.get("primary_file_count") == len(PRIMARY_FILES), "COMPARE_FILE_COUNT")
    raw = artifact_root / "raw"
    require(not raw.exists(), "ARTIFACT_RAW_EXISTS")
    raw.mkdir(parents=True)
    for name in PRIMARY_FILES:
        source_file = run_a / "raw" / name
        expected = comparison_payload["primary_files"][name]["run_a_sha256"]
        require(sha256_path(source_file) == expected, "INSTALL_PRIMARY_SHA", name)
        shutil.copyfile(source_file, raw / name)
    shutil.copyfile(run_a / "raw/environment.json", raw / "environment_run_a.json")
    shutil.copyfile(run_b / "raw/environment.json", raw / "environment_run_b.json")
    shutil.copyfile(comparison, raw / "comparison.json")
    write_checksums(artifact_root)
    verify_installed(artifact_root)
    print("Installed the 9 public-safe raw receipts and complete 13-file checksum manifest.")


def verify_checksum_manifest(root: Path) -> None:
    expected_paths = [path.relative_to(root).as_posix() for path in artifact_paths(root)]
    rows: dict[str, str] = {}
    for line in (root / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        require(bool(separator) and len(digest) == 64, "CHECKSUM_ROW")
        require(relative not in rows, "CHECKSUM_DUPLICATE", relative)
        rows[relative] = digest
    require(sorted(rows) == expected_paths, "CHECKSUM_FILE_SET")
    for relative, expected in rows.items():
        require(sha256_path(root / relative) == expected, "CHECKSUM_MISMATCH", relative)


def verify_installed(root: Path) -> None:
    root_entries = {path.name for path in root.iterdir() if path.name != "__pycache__"}
    require(root_entries == ROOT_FILES, "ARTIFACT_ROOT_SET", str(sorted(root_entries)))
    raw_entries = {path.name for path in (root / "raw").iterdir()}
    require(raw_entries == RAW_FILES, "ARTIFACT_RAW_SET", str(sorted(raw_entries)))
    verify_checksum_manifest(root)
    validate_primary(root)
    comparison = load_json(root / "raw/comparison.json")
    require(comparison.get("byte_identical") is True, "INSTALLED_COMPARISON")
    require(comparison.get("run_a_hash_seed") == "313", "INSTALLED_SEED_A")
    require(comparison.get("run_b_hash_seed") == "727", "INSTALLED_SEED_B")
    for name in PRIMARY_FILES:
        payload_sha = sha256_path(root / "raw" / name)
        require(comparison["primary_files"][name]["run_a_sha256"] == payload_sha, "INSTALLED_PRIMARY_A", name)
        require(comparison["primary_files"][name]["run_b_sha256"] == payload_sha, "INSTALLED_PRIMARY_B", name)
    require(load_json(root / "raw/environment_run_a.json").get("hash_seed") == "313", "ENV_A")
    require(load_json(root / "raw/environment_run_b.json").get("hash_seed") == "727", "ENV_B")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--source", type=Path, required=True)
    run_parser.add_argument("--paper-pdf", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--run-label", choices=("A", "B"), required=True)
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--run-a", type=Path, required=True)
    compare_parser.add_argument("--run-b", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--run-a", type=Path, required=True)
    install_parser.add_argument("--run-b", type=Path, required=True)
    install_parser.add_argument("--comparison", type=Path, required=True)
    install_parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    verify_parser = subparsers.add_parser("verify-installed")
    verify_parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    refresh_parser = subparsers.add_parser("refresh-checksums")
    refresh_parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "run":
        run_once(args.source.resolve(), args.paper_pdf.resolve(), args.output.resolve(), args.run_label)
    elif args.command == "compare":
        compare_runs(args.run_a.resolve(), args.run_b.resolve(), args.output.resolve())
    elif args.command == "install":
        install_runs(args.run_a.resolve(), args.run_b.resolve(), args.comparison.resolve(), args.artifact_root.resolve())
    elif args.command == "verify-installed":
        verify_installed(args.artifact_root.resolve())
        print("Verified installed MNL checked artifact.")
    elif args.command == "refresh-checksums":
        validate_primary(args.artifact_root.resolve())
        write_checksums(args.artifact_root.resolve())
        verify_installed(args.artifact_root.resolve())
        print("Refreshed and verified the complete checksum manifest.")


if __name__ == "__main__":
    main()
