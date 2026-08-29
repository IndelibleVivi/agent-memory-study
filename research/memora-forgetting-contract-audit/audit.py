#!/usr/bin/env python3
"""Run the source-locked, model-free Memora contract audit.

The runner reads an exact official checkout and an exact paper PDF supplied by
the reader. It never constructs a model/API/backend client. Official regression
tests run from a temporary ``git archive`` export under a Python network guard;
all other executable upstream behavior is AST-extracted and driven with
standard-library fakes in isolated guarded child processes.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import inspect
import itertools
import json
import math
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import types
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


sys.dont_write_bytecode = True

CURRENT_COMMIT = "a6493188efc836d6511ed5e4163fe3ba87da30ff"
PARENT_COMMIT = "e19ebbd1089465876dca11b09e70256977f9755f"
PAPER_SHA256 = "683a21a6b6fa09f1a6ad270832b3d891e41ecff6e6893298d8efe0df702566b2"
PAPER_ID = "arXiv:2604.20006v1"
SOURCE_URL = "https://github.com/geniesinc/Memora"
PAPER_URL = "https://arxiv.org/abs/2604.20006v1"

TRACK1 = "evals/model_eval/model_based_evaluator.py"
TRACK2 = "evals/agent_eval/memory_to_answer.py"
AGGREGATOR = "evals/model_eval/aggregate_results.py"
OFFICIAL_TESTS = (
    "evals/agent_eval/test_judge_import.py",
    "evals/agent_eval/test_stats_initialized.py",
)
SOURCE_LOCATORS = (
    ".gitignore",
    "README.md",
    "evals/README.md",
    TRACK1,
    TRACK2,
    AGGREGATOR,
    *OFFICIAL_TESTS,
)

EXPECTED = {
    "files": 30,
    "questions": 600,
    "criteria": 6415,
    "memory_presence": 2947,
    "forgetting_absence": 3468,
    "zero_forgetting": 204,
    "zero_presence": 0,
    "question_collision_groups": 38,
    "question_collision_payload_different": 38,
    "criterion_collision_groups": 178,
    "criterion_collision_payload_different": 175,
    "criterion_collision_payload_identical": 3,
    "distinct_release_counter_pairs": 156,
}
EXPECTED_PERIOD_CRITERIA = {"weekly": 735, "monthly": 1315, "quarterly": 4365}
EXPECTED_PERIOD_QUESTIONS = {"weekly": 150, "monthly": 150, "quarterly": 300}
EXPECTED_TASK_QUESTIONS = {"remembering": 200, "reasoning": 200, "recommending": 200}
EXPECTED_TASK_CRITERIA = {"remembering": 2877, "reasoning": 287, "recommending": 3251}
EXPECTED_PAPER_TABLE2 = {"weekly": 749, "monthly": 1421, "quarterly": 4884}

LEXICAL_TERMS = (
    "mention",
    "reflect",
    "include",
    "rely",
    "use",
    "avoid",
    "recommend",
    "listed",
)

PRIMARY_OUTPUTS = (
    "source_manifest.json",
    "official_pytest.txt",
    "official_tests.json",
    "judge_binding.json",
    "fama.json",
    "census.json",
    "aggregator.json",
    "release_boundary.json",
    "paper_locator.json",
    "environment.json",
    "decision.json",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(json_bytes(value))


def run_command(
    argv: List[str],
    *,
    cwd: Path | None = None,
    env: Dict[str, str] | None = None,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=check,
        capture_output=True,
        text=text,
    )


def git(source: Path, *args: str, text: bool = True) -> Any:
    result = run_command(["/usr/bin/git", "-C", str(source), *args], text=text)
    if text:
        return result.stdout.strip()
    return result.stdout


def source_blob(source: Path, revision: str, relative: str) -> bytes:
    return git(source, "show", f"{revision}:{relative}", text=False)


def normalized_source_path(path: Path, source: Path) -> str:
    return path.resolve().relative_to(source.resolve()).as_posix()


def assert_source(source: Path) -> Dict[str, Any]:
    if not (source / ".git").exists():
        raise AssertionError("--source must be a Git checkout, not an exported tree")
    head = git(source, "rev-parse", "HEAD")
    parent = git(source, "rev-parse", "HEAD^")
    status = git(source, "status", "--porcelain=v1", "--untracked-files=all")
    if head != CURRENT_COMMIT:
        raise AssertionError(f"source HEAD mismatch: {head} != {CURRENT_COMMIT}")
    if parent != PARENT_COMMIT:
        raise AssertionError(f"source direct parent mismatch: {parent} != {PARENT_COMMIT}")
    if status:
        raise AssertionError(f"source checkout has tracked/untracked changes:\n{status}")
    tree = git(source, "rev-parse", "HEAD^{tree}")
    parent_tree = git(source, "rev-parse", "HEAD^^{tree}")
    return {
        "head": head,
        "direct_parent": parent,
        "head_tree": tree,
        "parent_tree": parent_tree,
        "worktree_status": "clean",
    }


def build_source_manifest(source: Path, identity: Dict[str, Any]) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    for relative in SOURCE_LOCATORS:
        current = source_blob(source, CURRENT_COMMIT, relative)
        row: Dict[str, Any] = {
            "path": relative,
            "revision": CURRENT_COMMIT,
            "git_blob": git(source, "rev-parse", f"{CURRENT_COMMIT}:{relative}"),
            "sha256": sha256_bytes(current),
            "bytes": len(current),
        }
        if relative == TRACK2:
            historical = source_blob(source, PARENT_COMMIT, relative)
            row["historical_direct_parent"] = {
                "revision": PARENT_COMMIT,
                "git_blob": git(source, "rev-parse", f"{PARENT_COMMIT}:{relative}"),
                "sha256": sha256_bytes(historical),
                "bytes": len(historical),
            }
        files.append(row)

    return {
        "schema": "memora-source-manifest/1",
        "repository": SOURCE_URL,
        **identity,
        "inspected_files": files,
        "note": "Question-file hashes are recorded in census.json; no upstream source is copied.",
    }


NETWORK_GUARD = r'''\
import socket

class OfflineAuditNetworkBlocked(RuntimeError):
    pass

def _blocked(*args, **kwargs):
    raise OfflineAuditNetworkBlocked("network and DNS disabled by Memora audit")

class _GuardedSocket(socket.socket):
    def connect(self, *args, **kwargs):
        return _blocked(*args, **kwargs)
    def connect_ex(self, *args, **kwargs):
        return _blocked(*args, **kwargs)
    def sendto(self, *args, **kwargs):
        return _blocked(*args, **kwargs)

socket.socket = _GuardedSocket
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
socket.gethostbyname = _blocked
socket.gethostbyname_ex = _blocked
socket.gethostbyaddr = _blocked
'''


def guarded_environment(runtime_root: Path, guard_dir: Path) -> Dict[str, str]:
    """Return an allowlisted child environment with no credential variables."""
    home = runtime_root / "home"
    tmp = runtime_root / "tmp"
    home.mkdir(exist_ok=True)
    tmp.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONPATH": str(guard_dir),
    }


def make_guard(runtime_root: Path) -> Path:
    guard = runtime_root / "network-guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(NETWORK_GUARD, encoding="utf-8")
    return guard


def assert_network_guard_active() -> None:
    blocked = 0
    for probe in (
        lambda: socket.getaddrinfo("example.invalid", 443),
        lambda: socket.socket().connect(("127.0.0.1", 9)),
    ):
        try:
            probe()
        except RuntimeError as exc:
            if "disabled by Memora audit" not in str(exc):
                raise
            blocked += 1
    if blocked != 2:
        raise AssertionError("Python DNS/connect guard is not active")


def tree_snapshot(root: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file() or p.is_symlink()):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            out[rel] = "symlink:" + os.readlink(path)
        else:
            out[rel] = sha256_file(path)
    return out


def export_current_source(source: Path, target: Path) -> None:
    archive = git(source, "archive", "--format=tar", CURRENT_COMMIT, text=False)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        try:
            bundle.extractall(target, filter="data")
        except TypeError:  # Python <3.12 compatibility for this trusted git archive.
            bundle.extractall(target)


def normalize_receipt(text: str, replacements: Dict[str, str]) -> str:
    normalized = text
    for actual, token in sorted(replacements.items(), key=lambda item: -len(item[0])):
        normalized = normalized.replace(actual, token)
    normalized = re.sub(r"\b\d+(?:\.\d+)?s\b", "<duration>", normalized)
    normalized = re.sub(r"\bin \d+(?:\.\d+)? seconds\b", "in <duration>", normalized)
    return normalized.rstrip() + "\n"


def run_official_tests(
    source: Path,
    pytest_python: Path | None,
    runtime_root: Path,
    guard_dir: Path,
) -> Tuple[Dict[str, Any], str]:
    if pytest_python is None:
        receipt = {
            "schema": "memora-official-tests/1",
            "status": "not_run",
            "complete": False,
            "reason": "No --pytest-python supplied.",
        }
        return receipt, "Official pytest: NOT RUN (no --pytest-python supplied)\n"
    if not pytest_python.is_file():
        raise AssertionError(f"--pytest-python is not a file: {pytest_python}")

    export = runtime_root / "source-export"
    export.mkdir()
    export_current_source(source, export)
    before = tree_snapshot(export)
    env = guarded_environment(runtime_root, guard_dir)
    command = [
        str(pytest_python),
        "-m",
        "pytest",
        *OFFICIAL_TESTS,
        "-vv",
        "-p",
        "no:cacheprovider",
        "--tb=short",
    ]
    result = run_command(command, cwd=export, env=env, check=False)
    after = tree_snapshot(export)
    created = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = sorted(path for path in before.keys() & after.keys() if before[path] != after[path])
    cache_paths = sorted(
        path for path in after if "__pycache__" in Path(path).parts or ".pytest_cache" in Path(path).parts
    )
    combined = (result.stdout or "") + (result.stderr or "")
    normalized = normalize_receipt(
        combined,
        {
            str(export): "<SOURCE_EXPORT>",
            str(export.resolve()): "<SOURCE_EXPORT>",
            str(source): "<SOURCE_CHECKOUT>",
            str(source.resolve()): "<SOURCE_CHECKOUT>",
            str(pytest_python): "<PYTEST_PYTHON>",
            str(pytest_python.resolve()): "<PYTEST_PYTHON>",
            str(runtime_root): "<RUNTIME_ROOT>",
            str(runtime_root.resolve()): "<RUNTIME_ROOT>",
        },
    )
    passed_match = re.search(r"(?:^|\s)(\d+) passed(?:\s|,)", normalized)
    passed = int(passed_match.group(1)) if passed_match else 0
    if result.returncode != 0 or passed != 5:
        raise AssertionError(
            f"official tests did not produce the locked 5-pass receipt (exit={result.returncode}, passed={passed})\n"
            + normalized
        )
    if created or deleted or modified or cache_paths:
        raise AssertionError(
            "official tests changed the temporary source export: "
            f"created={created}, deleted={deleted}, modified={modified}, cache={cache_paths}"
        )
    receipt = {
        "schema": "memora-official-tests/1",
        "status": "passed",
        "complete": True,
        "selected_files": list(OFFICIAL_TESTS),
        "exit_code": result.returncode,
        "passed": passed,
        "source_export_before_files": len(before),
        "source_export_after_files": len(after),
        "created_paths": created,
        "deleted_paths": deleted,
        "modified_paths": modified,
        "cache_paths_after": cache_paths,
        "bytecode_disabled": True,
        "pytest_cacheprovider_disabled": True,
        "environment_allowlisted": True,
        "api_credentials_inherited": False,
        "python_network_guard": {"dns": "blocked", "connect": "blocked"},
        "receipt_sha256": sha256_bytes(normalized.encode("utf-8")),
    }
    return receipt, normalized


def find_ast_node(source_text: str, kind: type[ast.AST], name: str) -> ast.AST:
    tree = ast.parse(source_text)
    for node in tree.body:
        if isinstance(node, kind) and getattr(node, "name", None) == name:
            return node
    raise AssertionError(f"AST node not found: {kind.__name__} {name}")


def execute_nodes(nodes: List[ast.AST], namespace: Dict[str, Any], filename: str) -> Dict[str, Any]:
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, filename, "exec"), namespace)
    return namespace


class FakeMemorySystem:
    def validate_environment(self) -> bool:
        return True

    def initialize_client(self) -> bool:
        return True


class FakeOpenAI:
    @staticmethod
    def OpenAI(**_: Any) -> Any:
        return types.SimpleNamespace(kind="offline-fake-openai")


def common_track2_namespace(successes: int) -> Dict[str, Any]:
    state = {"constructed": 0}

    class FakeOpenRouterClient:
        def __init__(self, model: str):
            index = state["constructed"]
            state["constructed"] += 1
            if index >= successes:
                raise RuntimeError("synthetic offline initialization failure")
            self.model = model
            self.client = types.SimpleNamespace(base_url="offline://fake")

    return {
        "__name__": "locked_track2",
        "Path": Path,
        "Optional": Optional,
        "Dict": Dict,
        "List": List,
        "Any": Any,
        "Tuple": Tuple,
        "DEFAULT_JUDGE_MODELS": {"j0": "m0", "j1": "m1", "j2": "m2"},
        "OPENAI_AVAILABLE": True,
        "DOTENV_AVAILABLE": False,
        "openai": FakeOpenAI,
        "get_memory_system": lambda _name, _user: FakeMemorySystem(),
        # Source-exact ``__init__`` reads this one key before constructing the
        # injected fake OpenAI class. Keep the real child environment scrubbed.
        "os": types.SimpleNamespace(
            getenv=lambda key, default=None: "offline-placeholder" if key == "OPENAI_API_KEY" else default
        ),
        "sys": sys,
        "import_openrouter_client": lambda: FakeOpenRouterClient,
        "model_eval_dir": lambda: Path("evals/model_eval"),
        "state": state,
    }


def internal_track2_init(source: Path, successes: int, strict: bool) -> Dict[str, Any]:
    text = source_blob(source, CURRENT_COMMIT, TRACK2).decode("utf-8")
    class_node = find_ast_node(text, ast.ClassDef, "MemoryQuestionAnswering")
    namespace = common_track2_namespace(successes)
    execute_nodes([class_node], namespace, f"{CURRENT_COMMIT}:{TRACK2}")
    cls = namespace["MemoryQuestionAnswering"]
    error: Exception | None = None
    obj: Any = cls.__new__(cls)
    with tempfile.TemporaryDirectory(prefix="memora-track2-init-") as tmp:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                cls.__init__(
                    obj,
                    "synthetic-memory",
                    "synthetic-user",
                    output_dir=Path(tmp) / "out",
                    judge_models={"j0": "m0", "j1": "m1", "j2": "m2"},
                    use_multi_judge=True,
                    strict_judges=strict,
                )
            except Exception as exc:  # Exact source behavior is the observation.
                error = exc
    accepted = error is None
    return {
        "requested_successful_clients": successes,
        "strict": strict,
        "accepted": accepted,
        "exception": type(error).__name__ if error else None,
        "judge_clients": len(getattr(obj, "judge_clients", {})),
        "use_multi_judge": getattr(obj, "use_multi_judge", None),
        "constructed_fake_clients": namespace["state"]["constructed"],
    }


def internal_current_track2_import_origin(source: Path) -> Dict[str, Any]:
    """Execute the exact current import helper in a fresh guarded process."""
    initially_cached = "api_client" in sys.modules
    if initially_cached:
        raise AssertionError("fresh import-origin probe unexpectedly started with cached api_client")

    text = source_blob(source, CURRENT_COMMIT, TRACK2).decode("utf-8")
    path_node = find_ast_node(text, ast.FunctionDef, "model_eval_dir")
    import_node = find_ast_node(text, ast.FunctionDef, "import_openrouter_client")
    namespace: Dict[str, Any] = {
        "Path": Path,
        "sys": sys,
        "__file__": str(source / TRACK2),
    }
    execute_nodes([path_node, import_node], namespace, f"{CURRENT_COMMIT}:{TRACK2}")
    helper_path = namespace["model_eval_dir"]().resolve()
    client_class = namespace["import_openrouter_client"]()
    module = sys.modules.get("api_client")
    if module is None or not getattr(module, "__file__", None):
        raise AssertionError("exact current helper did not load a file-backed api_client module")

    module_path = Path(module.__file__).resolve()
    class_source = inspect.getsourcefile(client_class)
    if class_source is None:
        raise AssertionError("OpenRouterClient has no inspectable source file")
    class_path = Path(class_source).resolve()
    expected = (source / "evals/model_eval/api_client.py").resolve()
    if helper_path != expected.parent or module_path != expected or class_path != expected:
        raise AssertionError(
            "current Track-2 import origin mismatch: "
            f"helper={helper_path}, module={module_path}, class={class_path}, expected={expected}"
        )

    return {
        "revision": CURRENT_COMMIT,
        "source_exact_helpers": ["model_eval_dir", "import_openrouter_client"],
        "fresh_process_api_client_initially_cached": initially_cached,
        "helper_resolved_directory": normalized_source_path(helper_path, source),
        "api_client_module_file": normalized_source_path(module_path, source),
        "openrouter_client_source_file": normalized_source_path(class_path, source),
        "expected_origin": "evals/model_eval/api_client.py",
        "both_origins_match_expected": True,
        "real_client_constructed": False,
    }


def internal_historical_track2(source: Path) -> Dict[str, Any]:
    text = source_blob(source, PARENT_COMMIT, TRACK2).decode("utf-8")
    class_node = find_ast_node(text, ast.ClassDef, "MemoryQuestionAnswering")
    namespace = common_track2_namespace(0)
    namespace.pop("import_openrouter_client")
    namespace.pop("model_eval_dir")
    namespace["__file__"] = str(source / TRACK2)

    class BlockApiClient:
        def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
            if fullname == "api_client":
                raise ModuleNotFoundError("ambient api_client blocked for isolated historical probe")
            return None

    execute_nodes([class_node], namespace, f"{PARENT_COMMIT}:{TRACK2}")
    cls = namespace["MemoryQuestionAnswering"]
    blocker = BlockApiClient()
    old_path = list(sys.path)
    old_api_client = sys.modules.pop("api_client", None)
    sys.meta_path.insert(0, blocker)
    try:
        with tempfile.TemporaryDirectory(prefix="memora-historical-init-") as tmp:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                obj = cls(
                    "synthetic-memory",
                    "synthetic-user",
                    output_dir=Path(tmp) / "out",
                    judge_models={"j0": "m0", "j1": "m1", "j2": "m2"},
                    use_multi_judge=True,
                )
    finally:
        sys.meta_path.remove(blocker)
        sys.path[:] = old_path
        if old_api_client is not None:
            sys.modules["api_client"] = old_api_client
    wrong = source / "evals/agent_eval/model_eval"
    return {
        "revision": PARENT_COMMIT,
        "source_exact_init": True,
        "resolved_path": "evals/agent_eval/model_eval",
        "resolved_path_exists": wrong.exists(),
        "ambient_api_client_blocked": True,
        "judge_clients": len(obj.judge_clients),
        "use_multi_judge_after_import_error": obj.use_multi_judge,
        "exception": None,
    }


def internal_track1_init(source: Path, successes: int) -> Dict[str, Any]:
    text = source_blob(source, CURRENT_COMMIT, TRACK1).decode("utf-8")
    class_node = find_ast_node(text, ast.ClassDef, "MultiJudgeEvaluator")
    state = {"constructed": 0}

    class FakeOpenRouterClient:
        def __init__(self, model: str):
            index = state["constructed"]
            state["constructed"] += 1
            if index >= successes:
                raise RuntimeError("synthetic offline initialization failure")
            self.model = model
            self.client = types.SimpleNamespace(base_url="offline://fake")

    class FakeModelEvaluator:
        def __init__(self, client: Any):
            self.client = client

    namespace = {
        "__name__": "locked_track1",
        "Dict": Dict,
        "Any": Any,
        "DEFAULT_JUDGE_MODELS": {"j0": "m0", "j1": "m1", "j2": "m2"},
        "ModelEvaluator": FakeModelEvaluator,
    }
    execute_nodes([class_node], namespace, f"{CURRENT_COMMIT}:{TRACK1}")
    fake_module = types.ModuleType("api_client")
    fake_module.OpenRouterClient = FakeOpenRouterClient
    old = sys.modules.get("api_client")
    sys.modules["api_client"] = fake_module
    error: Exception | None = None
    obj: Any = None
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                obj = namespace["MultiJudgeEvaluator"](
                    judge_models={"j0": "m0", "j1": "m1", "j2": "m2"}
                )
            except Exception as exc:
                error = exc
    finally:
        if old is None:
            sys.modules.pop("api_client", None)
        else:
            sys.modules["api_client"] = old
    return {
        "requested_successful_clients": successes,
        "accepted": error is None,
        "exception": type(error).__name__ if error else None,
        "judges": len(obj.judges) if obj else 0,
        "constructed_fake_clients": state["constructed"],
    }


def runtime_votes(valid: int) -> Dict[str, Dict[str, Any]]:
    if valid not in range(4):
        raise AssertionError(valid)
    valid_rows: List[Dict[str, Any]] = []
    if valid >= 1:
        valid_rows.append({"is_correct": True, "confidence": 1.0, "llm_answer": "yes"})
    if valid >= 2:
        valid_rows.append({"is_correct": False, "confidence": 1.0, "llm_answer": "no"})
    if valid >= 3:
        valid_rows.append({"is_correct": True, "confidence": 1.0, "llm_answer": "yes"})
    rows: Dict[str, Dict[str, Any]] = {}
    for index in range(3):
        rows[f"j{index}"] = (
            valid_rows[index]
            if index < valid
            else {"is_correct": False, "confidence": 0.0, "llm_answer": "error"}
        )
    return rows


def internal_track1_runtime(source: Path, valid: int) -> Dict[str, Any]:
    text = source_blob(source, CURRENT_COMMIT, TRACK1).decode("utf-8")
    class_node = find_ast_node(text, ast.ClassDef, "MultiJudgeEvaluator")

    rows = runtime_votes(valid)

    class FakeJudge:
        def __init__(self, name: str):
            self.name = name

        def evaluate_response(self, **_: Any) -> Dict[str, Any]:
            return dict(rows[self.name])

    namespace = {
        "__name__": "locked_track1_runtime",
        "Dict": Dict,
        "Any": Any,
        "DEFAULT_JUDGE_MODELS": {},
        "ModelEvaluator": object,
    }
    execute_nodes([class_node], namespace, f"{CURRENT_COMMIT}:{TRACK1}")
    cls = namespace["MultiJudgeEvaluator"]
    obj = cls.__new__(cls)
    obj.judges = {name: FakeJudge(name) for name in rows}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        result = obj.evaluate_response("response", "criterion", "yes", {})
    return {
        "valid_judges": valid,
        "num_judges": result["num_judges"],
        "num_valid_judges": result["num_valid_judges"],
        "correct_votes": result.get("correct_votes", 0),
        "is_correct": result["is_correct"],
        "consensus": result["llm_answer"],
    }


def internal_track2_runtime(source: Path, valid: int) -> Dict[str, Any]:
    text = source_blob(source, CURRENT_COMMIT, TRACK2).decode("utf-8")
    class_node = find_ast_node(text, ast.ClassDef, "MemoryQuestionAnswering")
    namespace = common_track2_namespace(3)
    execute_nodes([class_node], namespace, f"{CURRENT_COMMIT}:{TRACK2}")
    cls = namespace["MemoryQuestionAnswering"]
    obj = cls.__new__(cls)
    rows = runtime_votes(valid)
    clients = {name: types.SimpleNamespace(name=name) for name in rows}
    obj.use_multi_judge = True
    obj.judge_clients = clients
    obj.judge_models = {name: name for name in rows}
    obj.model = "offline"
    obj.openai_client = None

    def fake_single(self: Any, _answer: str, _question: str, _expected: str, client: Any, _model: str) -> Dict[str, Any]:
        return dict(rows[client.name])

    obj._evaluate_with_single_judge = types.MethodType(fake_single, obj)
    criterion = {
        "evaluation_question_id": "synthetic",
        "evaluation_question": "synthetic",
        "expected_answer": "yes",
        "evaluation_type": "memory_presence",
    }
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        wrapped = obj.evaluate_answer_with_llm("response", [criterion])
    result = wrapped[0]["evaluation_result"]
    return {
        "valid_judges": valid,
        "num_judges": result["num_judges"],
        "num_valid_judges": result["num_valid_judges"],
        "correct_votes": result.get("correct_votes", 0),
        "is_correct": result["is_correct"],
        "consensus": result["llm_answer"],
    }


def internal_main(args: argparse.Namespace) -> None:
    assert_network_guard_active()
    source = args.source.resolve()
    if args.internal_case == "historical-track2":
        result = internal_historical_track2(source)
    elif args.internal_case == "current-track2-import-origin":
        result = internal_current_track2_import_origin(source)
    elif args.internal_case == "track2-init":
        result = internal_track2_init(source, args.count, args.strict)
    elif args.internal_case == "track1-init":
        result = internal_track1_init(source, args.count)
    elif args.internal_case == "track1-runtime":
        result = internal_track1_runtime(source, args.count)
    elif args.internal_case == "track2-runtime":
        result = internal_track2_runtime(source, args.count)
    else:
        raise AssertionError(args.internal_case)
    result["network_guard"] = {"dns": "blocked", "connect": "blocked"}
    print(json.dumps(result, sort_keys=True))


def run_internal(
    source: Path,
    runtime_root: Path,
    guard_dir: Path,
    case: str,
    *,
    count: int = 0,
    strict: bool = False,
) -> Dict[str, Any]:
    env = guarded_environment(runtime_root, guard_dir)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--source",
        str(source),
        "--internal-case",
        case,
        "--count",
        str(count),
    ]
    if strict:
        command.append("--strict")
    result = run_command(command, env=env, check=False)
    if result.returncode != 0:
        raise AssertionError(
            f"isolated case failed: {case}/{count}/{strict}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"isolated case did not return JSON: {result.stdout}\n{result.stderr}") from exc


def judge_path_observation(source: Path) -> Dict[str, Any]:
    text = source_blob(source, CURRENT_COMMIT, TRACK2).decode("utf-8")
    path_node = find_ast_node(text, ast.FunctionDef, "model_eval_dir")
    namespace: Dict[str, Any] = {"Path": Path, "__file__": str(source / TRACK2)}
    execute_nodes([path_node], namespace, f"{CURRENT_COMMIT}:{TRACK2}")
    resolved = namespace["model_eval_dir"]().resolve()
    expected = (source / "evals/model_eval").resolve()
    if resolved != expected or not (resolved / "api_client.py").is_file():
        raise AssertionError(f"current Track-2 judge path does not resolve exactly: {resolved}")
    return {
        "revision": CURRENT_COMMIT,
        "source_exact_helper": True,
        "resolved_path": normalized_source_path(resolved, source),
        "directory_exists": resolved.is_dir(),
        "api_client_exists": (resolved / "api_client.py").is_file(),
        "api_client_sha256": sha256_file(resolved / "api_client.py"),
    }


def judge_import_static_observation(source: Path) -> Dict[str, Any]:
    """Record the current helper's import mechanics and official-test ceiling."""
    text = source_blob(source, CURRENT_COMMIT, TRACK2).decode("utf-8")
    node = find_ast_node(text, ast.FunctionDef, "import_openrouter_client")
    uses_path_append = any(
        isinstance(candidate, ast.Call)
        and isinstance(candidate.func, ast.Attribute)
        and candidate.func.attr == "append"
        and isinstance(candidate.func.value, ast.Attribute)
        and candidate.func.value.attr == "path"
        and isinstance(candidate.func.value.value, ast.Name)
        and candidate.func.value.value.id == "sys"
        for candidate in ast.walk(node)
    )
    unqualified_import = any(
        isinstance(candidate, ast.ImportFrom)
        and candidate.module == "api_client"
        and candidate.level == 0
        and any(alias.name == "OpenRouterClient" for alias in candidate.names)
        for candidate in ast.walk(node)
    )
    if not uses_path_append or not unqualified_import:
        raise AssertionError("current Track-2 import mechanics changed")

    test_text = source_blob(source, CURRENT_COMMIT, OFFICIAL_TESTS[0]).decode("utf-8")
    class_name_assertion = 'client_cls.__name__ == "OpenRouterClient"' in test_text
    origin_assertion = "client_cls.__module__" in test_text or "inspect.getsourcefile" in test_text
    if not class_name_assertion or origin_assertion:
        raise AssertionError("official import-test assertion ceiling changed")
    return {
        "path_mutation": "sys.path.append",
        "import_form": "from api_client import OpenRouterClient",
        "unqualified_import": True,
        "pre_cached_api_client_can_shadow_expected_module": True,
        "earlier_sys_path_api_client_can_shadow_expected_module": True,
        "official_test": OFFICIAL_TESTS[0],
        "official_test_asserts_class_name_only": True,
        "official_test_asserts_source_origin": False,
        "interpretation": (
            "The fresh guarded probe resolves the intended in-tree file, but append plus an unqualified import "
            "remains shadowable by a pre-cached api_client or an earlier sys.path entry."
        ),
    }


def audit_judges(source: Path, runtime_root: Path, guard_dir: Path) -> Dict[str, Any]:
    historical = run_internal(source, runtime_root, guard_dir, "historical-track2")
    current_import_origin = run_internal(
        source, runtime_root, guard_dir, "current-track2-import-origin"
    )
    track2_init = [
        run_internal(source, runtime_root, guard_dir, "track2-init", count=count, strict=strict)
        for strict in (False, True)
        for count in range(4)
    ]
    track1_init = [
        run_internal(source, runtime_root, guard_dir, "track1-init", count=count)
        for count in range(4)
    ]
    track1_runtime = [
        run_internal(source, runtime_root, guard_dir, "track1-runtime", count=count)
        for count in range(4)
    ]
    track2_runtime = [
        run_internal(source, runtime_root, guard_dir, "track2-runtime", count=count)
        for count in range(4)
    ]

    if historical["resolved_path_exists"] or historical["use_multi_judge_after_import_error"]:
        raise AssertionError("historical wrong-path/silent-fallback observation changed")
    if (
        current_import_origin["fresh_process_api_client_initially_cached"]
        or not current_import_origin["both_origins_match_expected"]
    ):
        raise AssertionError("current Track-2 import origin gate failed")
    for row in track2_init:
        n = row["requested_successful_clients"]
        strict = row["strict"]
        expected_accepted = n == 3 or not strict
        if row["accepted"] != expected_accepted:
            raise AssertionError(f"Track-2 init matrix mismatch: {row}")
        if row["accepted"] and row["use_multi_judge"] != (n == 3):
            raise AssertionError(f"Track-2 non-strict fallback mismatch: {row}")
    for row in track1_init:
        if row["accepted"] != (row["requested_successful_clients"] > 0):
            raise AssertionError(f"Track-1 init matrix mismatch: {row}")

    expected_runtime = {
        0: (False, "error"),
        1: (True, "yes"),
        2: (False, "tie"),
        3: (True, "yes"),
    }
    for row in track1_runtime:
        if (row["is_correct"], row["consensus"]) != expected_runtime[row["valid_judges"]]:
            raise AssertionError(f"Track-1 runtime vote mismatch: {row}")
    expected_track2 = dict(expected_runtime)
    expected_track2[2] = (False, "no")
    for row in track2_runtime:
        if (row["is_correct"], row["consensus"]) != expected_track2[row["valid_judges"]]:
            raise AssertionError(f"Track-2 runtime vote mismatch: {row}")

    return {
        "schema": "memora-judge-binding/1",
        "historical_track2": historical,
        "current_track2_path": judge_path_observation(source),
        "current_track2_fresh_import_origin": current_import_origin,
        "current_track2_import_mechanics": judge_import_static_observation(source),
        "current_track2_initialization_matrix": track2_init,
        "current_track1_initialization_matrix": track1_init,
        "runtime_valid_judge_quorum": {
            "track1": track1_runtime,
            "track2": track2_runtime,
            "two_valid_judge_tie_difference": {
                "track1_consensus": "tie",
                "track2_consensus": "no",
                "is_correct_both": False,
                "reason": "Both use strict correct-vote majority; their yes/no tie labels differ.",
            },
        },
        "execution_boundary": {
            "source_exact_ast": True,
            "cases_isolated_by_child_process": True,
            "fake_api_client_only": True,
            "initialization_matrix_scope": (
                "Exact upstream constructor control flow with deterministic fake client constructors; "
                "not real api_client.OpenRouterClient backend construction."
            ),
            "synthetic_fake_constructor_calls_recorded": True,
            "real_client_or_model_constructed": False,
            "credential_environment_inherited": False,
            "network": "blocked",
        },
    }


def extracted_function(source: Path, relative: str, name: str) -> Tuple[Any, str]:
    text = source_blob(source, CURRENT_COMMIT, relative).decode("utf-8")
    node = find_ast_node(text, ast.FunctionDef, name)
    segment = ast.get_source_segment(text, node)
    if segment is None:
        raise AssertionError(f"unable to recover source segment: {relative}:{name}")
    namespace: Dict[str, Any] = {}
    execute_nodes([node], namespace, f"{CURRENT_COMMIT}:{relative}")
    return namespace[name], sha256_bytes(segment.encode("utf-8"))


def fama_paper_equation_reference(cp: int, np: int, cf: int, nf: int) -> Fraction:
    """Independent exact implementation on the paper equation's defined domain."""
    if np <= 0 or nf <= 0:
        raise ValueError("paper-equation oracle requires both denominators to be positive")
    mpa = Fraction(cp, np)
    faa = Fraction(cf, nf)
    weight = Fraction(nf, np + nf)
    value = mpa - weight * (1 - faa)
    return max(Fraction(0, 1), value)


def fama_source_zero_bucket_reference(cp: int, np: int, cf: int, nf: int) -> Fraction:
    """Exact reference for zero-bucket conventions observed in released source."""
    if np > 0 and nf > 0:
        raise ValueError("zero-bucket source extension requires at least one zero total")
    if np == 0 and nf == 0:
        return Fraction(0, 1)
    mpa = Fraction(cp, np) if np else Fraction(0, 1)
    faa = Fraction(cf, nf) if nf else Fraction(1, 1)
    weight = Fraction(nf, np + nf)
    value = mpa - weight * (1 - faa)
    return max(Fraction(0, 1), value)


def fama_source_valid_reference(cp: int, np: int, cf: int, nf: int) -> Fraction:
    if np > 0 and nf > 0:
        return fama_paper_equation_reference(cp, np, cf, nf)
    return fama_source_zero_bucket_reference(cp, np, cf, nf)


def audit_fama(source: Path, release_pairs: Counter[Tuple[int, int]]) -> Dict[str, Any]:
    track1, track1_ast_sha = extracted_function(source, TRACK1, "fama_score")
    track2, track2_ast_sha = extracted_function(source, TRACK2, "fama_score")
    functions = {"track1": track1, "track2": track2}
    total_fixtures = 0
    comparisons = 0
    monotonic_checks = 0
    max_error = 0.0
    paper_fixtures = 0
    paper_comparisons = 0
    paper_monotonic_checks = 0
    paper_max_error = 0.0
    extension_fixtures = 0
    extension_comparisons = 0
    extension_monotonic_checks = 0
    extension_max_error = 0.0
    for np in range(7):
        for nf in range(7):
            for cp in range(np + 1):
                prior: Dict[str, float] = {}
                for cf in range(nf + 1):
                    paper_domain = np > 0 and nf > 0
                    expected = float(
                        fama_paper_equation_reference(cp, np, cf, nf)
                        if paper_domain
                        else fama_source_zero_bucket_reference(cp, np, cf, nf)
                    )
                    total_fixtures += 1
                    if paper_domain:
                        paper_fixtures += 1
                    else:
                        extension_fixtures += 1
                    for label, function in functions.items():
                        observed = float(function(cp, np, cf, nf))
                        comparisons += 1
                        error = abs(observed - expected)
                        max_error = max(max_error, error)
                        if paper_domain:
                            paper_comparisons += 1
                            paper_max_error = max(paper_max_error, error)
                        else:
                            extension_comparisons += 1
                            extension_max_error = max(extension_max_error, error)
                        if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-12):
                            raise AssertionError(
                                f"FAMA mismatch {label}: {(cp, np, cf, nf)} -> {observed} != {expected}"
                            )
                        if not (0.0 <= observed <= 1.0):
                            raise AssertionError(f"FAMA valid-domain bound failure {label}: {observed}")
                        if cf > 0:
                            monotonic_checks += 1
                            if paper_domain:
                                paper_monotonic_checks += 1
                            else:
                                extension_monotonic_checks += 1
                            if observed + 1e-12 < prior[label]:
                                raise AssertionError("FAMA decreases when forgetting correctness increases")
                        prior[label] = observed

    release_corner_checks = 0
    release_rows: List[Dict[str, Any]] = []
    for (np, nf), frequency in sorted(release_pairs.items()):
        fixtures = {(0, 0), (0, nf), (np, 0), (np, nf)}
        for cp, cf in sorted(fixtures):
            expected = float(fama_source_valid_reference(cp, np, cf, nf))
            for label, function in functions.items():
                observed = float(function(cp, np, cf, nf))
                release_corner_checks += 1
                if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-12):
                    raise AssertionError(f"release-corner FAMA mismatch: {label}/{np}/{nf}/{cp}/{cf}")
        release_rows.append(
            {
                "memory_presence_total": np,
                "forgetting_absence_total": nf,
                "question_count": frequency,
                "lambda": str(Fraction(nf, np + nf)),
            }
        )
    if len(release_rows) != EXPECTED["distinct_release_counter_pairs"]:
        raise AssertionError(f"release counter-pair count changed: {len(release_rows)}")
    if (total_fixtures, paper_fixtures, extension_fixtures) != (784, 729, 55):
        raise AssertionError(
            "FAMA domain partition changed: "
            f"source={total_fixtures}, paper={paper_fixtures}, extension={extension_fixtures}"
        )

    out_of_domain = {label: function(3, 2, 0, 0) for label, function in functions.items()}
    if out_of_domain != {"track1": 1.5, "track2": 1.5}:
        raise AssertionError(f"out-of-domain probe changed: {out_of_domain}")
    return {
        "schema": "memora-fama-audit/2",
        "exact_functions": {
            "track1": {"path": TRACK1, "ast_source_sha256": track1_ast_sha},
            "track2": {"path": TRACK2, "ast_source_sha256": track2_ast_sha},
        },
        "bounded_valid_matrix": {
            "scope": "released-source-valid integer counters, explicitly partitioned by evidence domain",
            "totals": "memory_presence_total and forgetting_absence_total each 0..6",
            "source_valid_counter_fixtures": total_fixtures,
            "source_valid_function_comparisons": comparisons,
            "maximum_absolute_error": max_error,
            "bounds_failures": 0,
            "monotonicity_checks": monotonic_checks,
            "monotonicity_failures": 0,
            "paper_equation_domain": {
                "domain": "memory_presence_total > 0 and forgetting_absence_total > 0",
                "fixtures": paper_fixtures,
                "function_comparisons": paper_comparisons,
                "independent_oracle": "fractions.Fraction implementation of the reported equation",
                "oracle_zero_division_defined": False,
                "maximum_absolute_error": paper_max_error,
                "monotonicity_checks": paper_monotonic_checks,
            },
            "source_zero_bucket_extensions": {
                "domain": "memory_presence_total == 0 and/or forgetting_absence_total == 0",
                "fixtures": extension_fixtures,
                "function_comparisons": extension_comparisons,
                "reference": "zero-bucket conventions observed in both exact released source functions",
                "paper_defined": False,
                "maximum_absolute_error": extension_max_error,
                "monotonicity_checks": extension_monotonic_checks,
            },
        },
        "empty_bucket_policies": {
            "both_totals_zero": 0.0,
            "presence_total_zero": "0.0 after non-negative clamp",
            "forgetting_total_zero": "FAMA equals MPA",
            "paper_n_forget_zero_convention": "not specified in the equation prose on physical page 6",
        },
        "out_of_domain_direct_function_probe": {
            "input": {
                "memory_presence_correct": 3,
                "memory_presence_total": 2,
                "forgetting_absence_correct": 0,
                "forgetting_absence_total": 0,
            },
            "track1": out_of_domain["track1"],
            "track2": out_of_domain["track2"],
            "interpretation": (
                "The exact functions do not validate correct<=total or upper-clamp. "
                "Released call sites derive valid counters; this synthetic probe is not benchmark output."
            ),
        },
        "released_counter_pair_corners": {
            "distinct_pairs": len(release_rows),
            "function_comparisons": release_corner_checks,
            "rows": release_rows,
        },
    }


def relative_question_files(source: Path) -> List[Path]:
    return sorted(source.glob("data/*/*/evaluation_questions_*.json"))


def payload_digest(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def audit_census(source: Path) -> Tuple[Dict[str, Any], Counter[Tuple[int, int]]]:
    files = relative_question_files(source)
    file_rows: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []
    criteria: List[Dict[str, Any]] = []
    release_pairs: Counter[Tuple[int, int]] = Counter()
    declared_mismatches: List[Dict[str, str]] = []
    file_local_question_duplicates: List[str] = []
    file_local_criterion_duplicates: List[str] = []
    composite_question_ids: set[Tuple[str, str, str]] = set()
    composite_criterion_ids: set[Tuple[str, str, str]] = set()

    for path in files:
        relative = path.relative_to(source).as_posix()
        parts = Path(relative).parts
        period, persona = parts[1], parts[2]
        data = json.loads(path.read_text(encoding="utf-8"))
        if set(data) != {"date_range", "persona", "questions"}:
            raise AssertionError(f"unexpected top-level schema in {relative}: {sorted(data)}")
        if data["persona"] != persona:
            raise AssertionError(f"persona/path mismatch: {relative}")
        if set(data["questions"]) != {"remembering", "reasoning", "recommending"}:
            raise AssertionError(f"unexpected task keys: {relative}")

        local_q: set[str] = set()
        local_e: set[str] = set()
        task_rows: List[Dict[str, Any]] = []
        file_q = file_c = file_p = file_f = 0
        for task in ("remembering", "reasoning", "recommending"):
            task_q = task_c = task_p = task_f = 0
            for question in data["questions"][task]:
                qid = question.get("question_id")
                if not isinstance(qid, str) or not qid:
                    raise AssertionError(f"missing question_id: {relative}/{task}")
                if qid in local_q:
                    file_local_question_duplicates.append(f"{relative}:{qid}")
                local_q.add(qid)
                composite_q = (period, persona, qid)
                if composite_q in composite_question_ids:
                    raise AssertionError(f"duplicate composite question identity: {composite_q}")
                composite_question_ids.add(composite_q)

                evaluation = question.get("evaluation")
                if not isinstance(evaluation, dict) or not isinstance(evaluation.get("evaluation_questions"), list):
                    raise AssertionError(f"missing evaluation list: {relative}:{qid}")
                eval_rows = evaluation["evaluation_questions"]
                n_p = n_f = 0
                for criterion in eval_rows:
                    eid = criterion.get("evaluation_question_id")
                    kind = criterion.get("evaluation_type")
                    expected = criterion.get("expected_answer")
                    if not isinstance(eid, str) or not eid:
                        raise AssertionError(f"missing criterion ID: {relative}:{qid}")
                    if (kind, expected) not in {
                        ("memory_presence", "yes"),
                        ("forgetting_absence", "no"),
                    }:
                        raise AssertionError(f"unknown type/expected pair: {relative}:{qid}:{kind}/{expected}")
                    if eid in local_e:
                        file_local_criterion_duplicates.append(f"{relative}:{eid}")
                    local_e.add(eid)
                    composite_e = (period, persona, eid)
                    if composite_e in composite_criterion_ids:
                        raise AssertionError(f"duplicate composite criterion identity: {composite_e}")
                    composite_criterion_ids.add(composite_e)
                    n_p += kind == "memory_presence"
                    n_f += kind == "forgetting_absence"
                    criteria.append(
                        {
                            "period": period,
                            "persona": persona,
                            "task": task,
                            "question_id": qid,
                            "criterion_id": eid,
                            "type": kind,
                            "expected": expected,
                            "text_lower": str(criterion.get("evaluation_question", "")).lower(),
                            "payload_digest": payload_digest(criterion),
                        }
                    )
                declared = {
                    "total_evaluation_questions": len(eval_rows),
                    "memory_presence_questions": n_p,
                    "forgetting_absence_questions": n_f,
                }
                for key, observed in declared.items():
                    if evaluation.get(key) != observed:
                        declared_mismatches.append({"path": relative, "question_id": qid, "counter": key})
                release_pairs[(n_p, n_f)] += 1
                questions.append(
                    {
                        "period": period,
                        "persona": persona,
                        "task": task,
                        "question_id": qid,
                        "n_presence": n_p,
                        "n_forget": n_f,
                        "payload_digest": payload_digest(question),
                    }
                )
                task_q += 1
                task_c += len(eval_rows)
                task_p += n_p
                task_f += n_f
            task_rows.append(
                {
                    "task": task,
                    "questions": task_q,
                    "criteria": task_c,
                    "memory_presence": task_p,
                    "forgetting_absence": task_f,
                }
            )
            file_q += task_q
            file_c += task_c
            file_p += task_p
            file_f += task_f
        file_rows.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "period": period,
                "persona": persona,
                "questions": file_q,
                "criteria": file_c,
                "memory_presence": file_p,
                "forgetting_absence": file_f,
                "tasks": task_rows,
            }
        )

    if file_local_question_duplicates or file_local_criterion_duplicates:
        raise AssertionError(
            f"file-local duplicates: questions={file_local_question_duplicates}, criteria={file_local_criterion_duplicates}"
        )
    if declared_mismatches:
        raise AssertionError(f"declared counter mismatches: {declared_mismatches}")

    totals = {
        "files": len(files),
        "questions": len(questions),
        "criteria": len(criteria),
        "memory_presence": sum(row["type"] == "memory_presence" for row in criteria),
        "forgetting_absence": sum(row["type"] == "forgetting_absence" for row in criteria),
        "zero_forgetting": sum(row["n_forget"] == 0 for row in questions),
        "zero_presence": sum(row["n_presence"] == 0 for row in questions),
    }
    for key, expected in EXPECTED.items():
        if key in totals and totals[key] != expected:
            raise AssertionError(f"census total changed: {key}={totals[key]} != {expected}")

    period_questions = Counter(row["period"] for row in questions)
    period_criteria = Counter(row["period"] for row in criteria)
    task_questions = Counter(row["task"] for row in questions)
    task_criteria = Counter(row["task"] for row in criteria)
    if dict(period_questions) != EXPECTED_PERIOD_QUESTIONS:
        raise AssertionError(f"period question census changed: {period_questions}")
    if dict(period_criteria) != EXPECTED_PERIOD_CRITERIA:
        raise AssertionError(f"period criterion census changed: {period_criteria}")
    if dict(task_questions) != EXPECTED_TASK_QUESTIONS:
        raise AssertionError(f"task question census changed: {task_questions}")
    if dict(task_criteria) != EXPECTED_TASK_CRITERIA:
        raise AssertionError(f"task criterion census changed: {task_criteria}")

    def collisions(rows: List[Dict[str, Any]], id_key: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row[id_key]].append(row)
        collided = {key: group for key, group in grouped.items() if len(group) > 1}
        if any(len(group) != 2 for group in collided.values()):
            raise AssertionError(f"non-pair bare-ID collision in {id_key}")
        different = sum(len({row["payload_digest"] for row in group}) > 1 for group in collided.values())
        identical_loci: List[Dict[str, Any]] = []
        relation_counts: Counter[str] = Counter()
        for bare_id, group in sorted(collided.items()):
            left, right = group
            if left["period"] == right["period"] and left["persona"] != right["persona"]:
                relation = "same_period_cross_persona"
            elif left["period"] != right["period"] and left["persona"] == right["persona"]:
                relation = "cross_period_same_persona"
            elif left["period"] != right["period"] and left["persona"] != right["persona"]:
                relation = "cross_period_cross_persona"
            else:
                relation = "same_path"
            relation_counts[relation] += 1
            if left["payload_digest"] == right["payload_digest"]:
                identical_loci.append(
                    {
                        "bare_id": bare_id,
                        "left": {
                            key: left[key]
                            for key in ("period", "persona", "task", "question_id")
                            if key in left
                        },
                        "right": {
                            key: right[key]
                            for key in ("period", "persona", "task", "question_id")
                            if key in right
                        },
                    }
                )
        return (
            {
                "groups": len(collided),
                "rows": sum(len(group) for group in collided.values()),
                "payload_different_groups": different,
                "payload_identical_groups": len(collided) - different,
                "pair_relation_counts": dict(sorted(relation_counts.items())),
            },
            identical_loci,
        )

    q_collision, q_identical = collisions(questions, "question_id")
    c_collision, c_identical = collisions(criteria, "criterion_id")
    expected_collision = (
        q_collision["groups"],
        q_collision["payload_different_groups"],
        c_collision["groups"],
        c_collision["payload_different_groups"],
        c_collision["payload_identical_groups"],
    )
    if expected_collision != (38, 38, 178, 175, 3) or q_identical or len(c_identical) != 3:
        raise AssertionError(f"collision geometry changed: {expected_collision}, {q_identical}, {c_identical}")

    lexical: Dict[str, Dict[str, Any]] = {}
    for term in LEXICAL_TERMS:
        matched = [row for row in criteria if term in row["text_lower"]]
        lexical[term] = {
            "criteria": len(matched),
            "by_type": dict(sorted(Counter(row["type"] for row in matched).items())),
        }

    james = [
        row
        for row in criteria
        if row["period"] == "quarterly"
        and row["persona"] == "academic_researcher"
        and row["criterion_id"] == "pref_movies_general_2005_eval_forgetting_9"
    ]
    if len(james) != 1 or james[0]["type"] != "forgetting_absence" or james[0]["expected"] != "no":
        raise AssertionError("locked James-Stewart release criterion locator changed")

    zero_forgetting_by_task = dict(
        sorted(Counter(row["task"] for row in questions if row["n_forget"] == 0).items())
    )
    if zero_forgetting_by_task != {"reasoning": 200, "remembering": 4}:
        raise AssertionError(f"zero-forgetting task geometry changed: {zero_forgetting_by_task}")

    paper_total = sum(EXPECTED_PAPER_TABLE2.values())
    release_total = sum(EXPECTED_PERIOD_CRITERIA.values())
    census = {
        "schema": "memora-release-census/1",
        "totals": totals,
        "by_period": {
            period: {
                "questions": period_questions[period],
                "criteria": period_criteria[period],
                "paper_table2_criteria": EXPECTED_PAPER_TABLE2[period],
                "paper_minus_release": EXPECTED_PAPER_TABLE2[period] - period_criteria[period],
            }
            for period in ("weekly", "monthly", "quarterly")
        },
        "by_task": {
            task: {"questions": task_questions[task], "criteria": task_criteria[task]}
            for task in ("remembering", "reasoning", "recommending")
        },
        "paper_release_census_drift": {
            "paper_table2_total": paper_total,
            "locked_release_total": release_total,
            "difference": paper_total - release_total,
            "interpretation": (
                "This is paper/release input-census drift only. It does not identify the "
                "paper's production input revision or invalidate any reported result."
            ),
        },
        "schema_contract": {
            "accepted_type_expected_pairs": [
                {"evaluation_type": "forgetting_absence", "expected_answer": "no"},
                {"evaluation_type": "memory_presence", "expected_answer": "yes"},
            ],
            "unknown_pairs": 0,
            "declared_counter_mismatches": 0,
        },
        "identity": {
            "file_local_question_duplicates": 0,
            "file_local_criterion_duplicates": 0,
            "composite_question_identity": "(period, persona, question_id)",
            "composite_question_duplicates": 0,
            "composite_criterion_identity": "(period, persona, evaluation_question_id)",
            "composite_criterion_duplicates": 0,
            "bare_question_id_collisions": q_collision,
            "bare_criterion_id_collisions": c_collision,
            "three_identical_criterion_payload_path_pair_loci": c_identical,
        },
        "empty_buckets": {
            "zero_forgetting_questions": totals["zero_forgetting"],
            "zero_forgetting_by_task": zero_forgetting_by_task,
            "zero_presence_questions": totals["zero_presence"],
        },
        "lexical_surface_discovery": {
            "matching": "case-insensitive substring in criterion text",
            "counts": lexical,
            "claim_boundary": "Mechanical lexical discovery only; not semantic reliance or prevalence.",
        },
        "james_stewart_expected_no_locator": {
            "path": "data/quarterly/academic_researcher/evaluation_questions_academic_researcher.json",
            "task": james[0]["task"],
            "question_id": james[0]["question_id"],
            "criterion_id": james[0]["criterion_id"],
            "evaluation_type": james[0]["type"],
            "expected_answer": james[0]["expected"],
            "checked_response_population_in_release": False,
        },
        "files": file_rows,
    }
    return census, release_pairs


def audit_aggregator(source: Path, census: Dict[str, Any]) -> Dict[str, Any]:
    text = source_blob(source, CURRENT_COMMIT, AGGREGATOR).decode("utf-8")
    node = find_ast_node(text, ast.FunctionDef, "aggregate_table3")
    segment = ast.get_source_segment(text, node)
    namespace = {
        "defaultdict": defaultdict,
        "TASK_TYPES": ("Remembering", "Reasoning", "Recommending"),
        "List": List,
        "Dict": Dict,
        "Any": Any,
    }
    execute_nodes([node], namespace, f"{CURRENT_COMMIT}:{AGGREGATOR}")
    aggregate = namespace["aggregate_table3"]

    def row(
        report: str,
        *,
        period: str | None = "weekly",
        fama: float | None = None,
        questions: int = 1,
        subject: str = "synthetic",
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {"report": report, "subject": subject, "period": period}
        for task in ("remembering", "reasoning", "recommending"):
            out[f"fama_{task}"] = None
            out[f"questions_{task}"] = 0
        out["fama_remembering"] = fama
        out["questions_remembering"] = questions
        return out

    unequal = [row("small", fama=0.0, questions=1), row("large", fama=1.0, questions=9)]
    unequal_value = aggregate(unequal)["synthetic"]["Remembering"]["weekly"]
    per_question = (0.0 * 1 + 1.0 * 9) / 10
    if unequal_value != 0.5 or per_question != 0.9:
        raise AssertionError("unweighted macro fixture changed")

    filters = [
        row("zero", fama=0.0, questions=2),
        row("missing", fama=None, questions=2),
        row("empty", fama=1.0, questions=0),
        row("unknown", period=None, fama=0.75, questions=1),
    ]
    filtered = aggregate(filters)
    if filtered["synthetic"]["Remembering"] != {"weekly": 0.0, "unknown": 0.75}:
        raise AssertionError(f"zero/missing/empty/unknown fixture changed: {filtered}")

    duplicate = [row("same", fama=0.0), row("same", fama=0.0), row("other", fama=1.0)]
    duplicate_value = aggregate(duplicate)["synthetic"]["Remembering"]["weekly"]
    if not math.isclose(duplicate_value, 1 / 3, rel_tol=0.0, abs_tol=1e-12):
        raise AssertionError(f"duplicate report fixture changed: {duplicate_value}")

    per_file_task_counts: Dict[str, set[int]] = defaultdict(set)
    for file_row in census["files"]:
        for task_row in file_row["tasks"]:
            per_file_task_counts[f"{file_row['period']}:{task_row['task']}"] .add(task_row["questions"])
    expected_uniform = {
        f"{period}:{task}": ({10} if period == "quarterly" else {5})
        for period in ("weekly", "monthly", "quarterly")
        for task in ("remembering", "reasoning", "recommending")
    }
    if dict(per_file_task_counts) != expected_uniform:
        raise AssertionError(f"released per-file task counts are not uniform: {per_file_task_counts}")

    return {
        "schema": "memora-aggregator-audit/1",
        "exact_function": {
            "path": AGGREGATOR,
            "name": "aggregate_table3",
            "ast_source_sha256": sha256_bytes((segment or "").encode("utf-8")),
        },
        "synthetic_fixtures": {
            "unweighted_report_macro": {
                "report_fama": [0.0, 1.0],
                "report_question_counts": [1, 9],
                "source_aggregate": unequal_value,
                "question_weighted_control": per_question,
            },
            "zero_fama_included": True,
            "missing_fama_excluded": True,
            "question_count_zero_excluded": True,
            "missing_period_bucket": "unknown",
            "duplicate_report_rows_retained": True,
            "duplicate_fixture_value": duplicate_value,
        },
        "released_input_geometry": {
            "per_file_task_question_counts": {
                key: sorted(values) for key, values in sorted(per_file_task_counts.items())
            },
            "conditional_equivalence": (
                "For a complete release population with one complete report per released "
                "period/persona run, equal-report and per-question task means coincide because "
                "each report has 5 task questions (weekly/monthly) or 10 (quarterly)."
            ),
            "boundary": (
                "aggregate_table3 itself checks neither expected report completeness nor report "
                "identity uniqueness; partial, unequal, or duplicate rows can diverge."
            ),
        },
    }


def line_locators(text: str, patterns: Dict[str, str]) -> Dict[str, int]:
    lines = text.splitlines()
    out: Dict[str, int] = {}
    for label, pattern in patterns.items():
        matches = [index for index, line in enumerate(lines, 1) if pattern in line]
        if not matches:
            raise AssertionError(f"source locator not found: {label}/{pattern}")
        out[label] = matches[0]
    return out


def audit_release_boundary(source: Path) -> Dict[str, Any]:
    tracked = git(source, "ls-tree", "-r", "--name-only", CURRENT_COMMIT).splitlines()
    reports = sorted(path for path in tracked if Path(path).name.startswith("eval_report_") and path.endswith(".json"))
    results = sorted(path for path in tracked if Path(path).name.startswith("eval_results_") and path.endswith(".json"))
    result_dirs = sorted({path.split("/eval_results/", 1)[0] + "/eval_results" for path in tracked if "/eval_results/" in path})
    if reports or results or result_dirs:
        raise AssertionError(f"checked evaluation outputs unexpectedly exist: {reports}, {results}, {result_dirs}")
    checkout_reports = sorted(source.glob("data/*/*/eval_results/**/eval_report_*.json"))
    checkout_results = sorted(source.glob("data/*/*/eval_results/**/eval_results_*.json"))
    checkout_result_dirs = sorted(source.glob("data/*/*/eval_results"))
    if checkout_reports or checkout_results or checkout_result_dirs:
        raise AssertionError(
            "reader-supplied checkout contains ignored/generated evaluation outputs: "
            f"reports={len(checkout_reports)}, results={len(checkout_results)}, dirs={len(checkout_result_dirs)}"
        )

    eval_readme = source_blob(source, CURRENT_COMMIT, "evals/README.md").decode("utf-8")
    gitignore = source_blob(source, CURRENT_COMMIT, ".gitignore").decode("utf-8")
    track1 = source_blob(source, CURRENT_COMMIT, TRACK1).decode("utf-8")
    track2 = source_blob(source, CURRENT_COMMIT, TRACK2).decode("utf-8")
    aggregator = source_blob(source, CURRENT_COMMIT, AGGREGATOR).decode("utf-8")
    return {
        "schema": "memora-release-boundary/1",
        "tracked_inventory": {
            "eval_report_json_files": len(reports),
            "eval_results_json_files": len(results),
            "eval_results_directories_with_tracked_content": len(result_dirs),
        },
        "reader_checkout_inventory": {
            "eval_report_json_files": len(checkout_reports),
            "eval_results_json_files": len(checkout_results),
            "eval_results_directories": len(checkout_result_dirs),
        },
        "source_locators": {
            "evals/README.md": line_locators(
                eval_readme,
                {
                    "result_directory": "eval_results/",
                    "detailed_output": "eval_results_<TIMESTAMP>.json",
                    "report_output": "eval_report_<TIMESTAMP>.json",
                    "aggregation_command": "aggregate_results.py",
                },
            ),
            ".gitignore": line_locators(gitignore, {"ignored_result_tree": "data/*/*/eval_results/"}),
            TRACK1: line_locators(track1, {"result_write": 'f"eval_results_{timestamp}.json"', "report_write": 'f"eval_report_{timestamp}.json"'}),
            TRACK2: line_locators(track2, {"result_write": 'f"eval_results_{timestamp}', "report_write": 'f"eval_report_{timestamp}'}),
            AGGREGATOR: line_locators(aggregator, {"report_discovery": 'rglob("eval_report_*.json")', "aggregation": "def aggregate_table3"}),
        },
        "derived_boundary": {
            "table3_reconstructable_model_free_from_locked_release": False,
            "reason": (
                "The locked tree includes questions, evaluators, output schemas and aggregation code, "
                "but zero checked response/report population. Reconstructing Table 3 would require new model/judge outputs or separate provenance-bearing results."
            ),
        },
    }


def paper_locator(paper_pdf: Path, census: Dict[str, Any]) -> Dict[str, Any]:
    actual = sha256_file(paper_pdf)
    if actual != PAPER_SHA256:
        raise AssertionError(f"paper PDF hash mismatch: {actual} != {PAPER_SHA256}")
    locator = census["james_stewart_expected_no_locator"]
    return {
        "schema": "memora-paper-locator/1",
        "paper": {
            "id": PAPER_ID,
            "url": PAPER_URL,
            "pdf_sha256": actual,
            "physical_pages": 28,
        },
        "fama_equation": {
            "physical_page": 6,
            "reported": "FAMA = max(0, MPA - lambda * (1 - FAA))",
            "reported_lambda": "N_forget / (N_presence + N_forget)",
            "n_forget_zero_convention_in_prose": "unspecified",
        },
        "appendix_d2_example": {
            "physical_pages": [23, 24],
            "desired_answer_short_fragment": "leaning away from James Stewart",
            "adjacent_expected_no_short_fragment": "reflect or mention ... James Stewart",
            "release_criterion_locator": locator,
            "observation": (
                "The paper-authored desired answer uses an obsolete preference contrastively while "
                "the adjacent criterion literally asks about mention as well as reflection."
            ),
            "editorial_inference": "This is a mention-versus-reliance specification tension in one authored example.",
            "claim_boundary": (
                "No scorer result, judge behavior, dataset-wide semantic prevalence, or aggregate-score effect is inferred."
            ),
        },
        "verification": {
            "pdf_identity_checked_by_runner": True,
            "locators_preflighted_and_visually_inspected": True,
            "full_pdf_or_dataset_text_copied": False,
        },
    }


def decision_document(
    source_manifest: Dict[str, Any],
    tests: Dict[str, Any],
    judges: Dict[str, Any],
    fama: Dict[str, Any],
    census: Dict[str, Any],
    aggregator: Dict[str, Any],
    release: Dict[str, Any],
    paper: Dict[str, Any],
) -> Dict[str, Any]:
    gates = {
        "exact_current_and_direct_parent": (
            source_manifest["head"] == CURRENT_COMMIT and source_manifest["direct_parent"] == PARENT_COMMIT
        ),
        "clean_source_checkout": source_manifest["worktree_status"] == "clean",
        "official_offline_tests_5_passed": tests.get("passed") == 5 and tests.get("complete") is True,
        "official_test_source_export_unchanged": not (
            tests.get("created_paths") or tests.get("deleted_paths") or tests.get("modified_paths") or tests.get("cache_paths_after")
        ),
        "judge_binding_matrix_complete": (
            len(judges["current_track2_initialization_matrix"]) == 8
            and len(judges["current_track1_initialization_matrix"]) == 4
            and len(judges["runtime_valid_judge_quorum"]["track1"]) == 4
            and len(judges["runtime_valid_judge_quorum"]["track2"]) == 4
        ),
        "current_track2_import_origin_exact": (
            judges["current_track2_fresh_import_origin"]["both_origins_match_expected"]
            and not judges["current_track2_fresh_import_origin"][
                "fresh_process_api_client_initially_cached"
            ]
        ),
        "fama_exact_matrix_passed": (
            fama["bounded_valid_matrix"]["maximum_absolute_error"] <= 1e-12
            and fama["bounded_valid_matrix"]["bounds_failures"] == 0
            and fama["bounded_valid_matrix"]["monotonicity_failures"] == 0
        ),
        "fama_evidence_domain_partition_exact": (
            fama["bounded_valid_matrix"]["source_valid_counter_fixtures"] == 784
            and fama["bounded_valid_matrix"]["paper_equation_domain"]["fixtures"] == 729
            and fama["bounded_valid_matrix"]["source_zero_bucket_extensions"]["fixtures"] == 55
        ),
        "release_census_complete": census["totals"]["files"] == 30 and census["totals"]["questions"] == 600,
        "aggregator_synthetic_contract_passed": aggregator["synthetic_fixtures"]["unweighted_report_macro"]["source_aggregate"] == 0.5,
        "checked_results_absent": (
            not any(release["tracked_inventory"].values())
            and not any(release["reader_checkout_inventory"].values())
        ),
        "paper_identity_and_locator_bound": paper["paper"]["pdf_sha256"] == PAPER_SHA256,
        "no_model_api_backend_or_network": True,
    }
    verdict = "PASS" if all(gates.values()) else "INCOMPLETE"
    return {
        "schema": "memora-forgetting-contract-audit-decision/3",
        "verdict": verdict,
        "decision_scope": "single_run_completeness",
        "package_acceptance_status": "not_evaluated_within_single_run",
        "package_acceptance_requirements": [
            "raw/decision.json records PASS for one complete fresh run",
            "raw/reproduction.json records byte-identical primary receipts from two fresh runs",
            "verify_checked.py validates the installed tree, hashes, exact external evidence, and both receipts",
        ],
        "protocol_provenance": {
            "public_protocol_file": "PREREGISTRATION.md",
            "public_record_timing": "post_execution",
            "private_pretest_freeze_date": "2026-08-29",
            "private_pretest_source_published": False,
            "public_reconstruction_scope": (
                "Public-safe claim-level reconstruction of a privately held pretest freeze, "
                "followed by explicitly separated post-execution amendments."
            ),
            "same_day_clock_times_asserted": False,
            "post_execution_amendments": [
                "729/55 evidence-domain reporting partition and domain-separated FAMA references",
                "fresh current Track-2 import-origin and static shadowability probes",
                "Track-1 initialization and both runtime-valid-quorum matrices beyond the frozen Track-2 question",
                "separate invalid direct-function probe despite the frozen valid-counter-only matrix",
                "single-run decision versus checked-package acceptance terminology",
            ],
            "pretest_aggregation_hypothesis_status": (
                "not_supported_as_exact_source_contract: current aggregate_table3 averages report-level task FAMA rows; "
                "it only coincides with a per-question mean under additional complete equal-question geometry"
            ),
        },
        "gates": gates,
        "raw_result": {
            "historical_track2": (
                "At direct parent e19ebbd, the exact initialization path targeted the nonexistent "
                "evals/agent_eval/model_eval and converted ImportError into use_multi_judge=False."
            ),
            "current_track2": (
                "At a6493188, a fresh guarded exact-helper import resolved both api_client and "
                "OpenRouterClient to evals/model_eval/api_client.py. The helper still uses sys.path.append "
                "plus an unqualified import and is shadowable by a pre-cached or earlier-path api_client. "
                "In the deterministic fake-client constructor matrix, strict 0/1/2 raised while non-strict "
                "0/1/2 explicitly fell back; no real backend client was constructed."
            ),
            "current_track1": (
                "In the deterministic fake-client constructor matrix, exact Track-1 control flow raises "
                "at 0/3 and accepts 1/3, 2/3, and 3/3; no real backend client was constructed."
            ),
            "runtime_quorum": (
                "Both tracks compute correctness by strict majority of valid judges. At one yes/one no, "
                "Track 1 labels consensus tie while Track 2 labels it no; both mark is_correct false."
            ),
            "fama": (
                "Both exact functions matched an independent Fraction oracle across 729 paper-equation-domain "
                "fixtures. A separate 55-fixture source extension matched the released zero-bucket conventions; "
                "those conventions are not paper-defined. The out-of-domain direct probe (3,2,0,0) returned 1.5 in both."
            ),
            "released_input": "30 files, 600 questions, 6,415 criteria: 2,947 presence and 3,468 forgetting-absence.",
            "paper_release_census": "Paper Table 2 totals 7,054 criteria; the locked release totals 6,415.",
            "aggregation": "The exact aggregator is an unweighted mean of report-level task FAMA rows.",
            "release_boundary": "The locked tree contains zero checked eval report/result population.",
            "paper_example": "Physical pages 23-24 contain one mention-versus-reliance specification tension.",
        },
        "derived_result": {
            "judge_protocol": (
                "The repair closes Track-2 initialization cardinality only when strict mode is used; Track 1 "
                "and runtime judge failures still permit smaller valid-judge quorums."
            ),
            "metric_contract": (
                "FAMA matches the reported equation when both denominators are positive and separately matches "
                "released-source zero-bucket conventions; the standalone functions do not validate counter "
                "domains or upper-clamp invalid inputs."
            ),
            "aggregation_contract": (
                "Equal-report and per-question means coincide only under complete equal-question report geometry; "
                "the aggregator has no completeness or deduplication gate."
            ),
            "release_contract": (
                "The paper/release criterion-count difference is input-census drift, not result invalidation; "
                "Table 3 cannot be reconstructed model-free from this release."
            ),
            "example_contract": (
                "The James-Stewart example exposes one written mention-versus-reliance tension, not observed scorer behavior."
            ),
        },
        "claim_ceiling": {
            "allowed": [
                "exact-revision source behavior",
                "official offline test receipt",
                "synthetic contract behavior",
                "released-input geometry",
                "one paper-authored specification tension",
                "locked-release result boundary",
            ],
            "not_established": [
                "benchmark reproduction",
                "model or memory-system comparison",
                "effect size or semantic prevalence",
                "paper-production source revision",
                "Table 3 reconstruction or paper-result invalidation",
            ],
        },
    }


def execute_audit(args: argparse.Namespace) -> None:
    source = args.source.resolve()
    paper = args.paper_pdf.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing existing --output: {output}")
    if not paper.is_file():
        raise AssertionError(f"--paper-pdf is not a file: {paper}")
    output.parent.mkdir(parents=True, exist_ok=True)
    identity_before = assert_source(source)

    with tempfile.TemporaryDirectory(prefix="memora-audit-runtime-") as runtime_name:
        runtime = Path(runtime_name)
        guard = make_guard(runtime)
        tests, pytest_text = run_official_tests(source, args.pytest_python, runtime, guard)
        census, release_pairs = audit_census(source)
        judges = audit_judges(source, runtime, guard)
        fama = audit_fama(source, release_pairs)
        aggregator = audit_aggregator(source, census)
        release = audit_release_boundary(source)
        paper_receipt = paper_locator(paper, census)

    identity_after = assert_source(source)
    if identity_before != identity_after:
        raise AssertionError("source identity/status changed during audit")
    manifest = build_source_manifest(source, identity_after)
    environment = {
        "schema": "memora-audit-environment/1",
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "machine": platform.machine(),
        "credential_policy": "child subprocess environment allowlist; no inherited API/key/token/secret/password variables",
        "network_policy": "Python child DNS/connect/sendto blocked by sitecustomize guard",
        "source_execution": "official pytest runs from a temporary git-archive export; source checkout remains unchanged",
        "timing_recorded": False,
        "absolute_paths_recorded": False,
    }
    decision = decision_document(manifest, tests, judges, fama, census, aggregator, release, paper_receipt)
    if decision["verdict"] != "PASS":
        raise AssertionError(f"audit did not pass all completeness gates: {decision['gates']}")

    with tempfile.TemporaryDirectory(prefix="memora-audit-stage-", dir=output.parent) as stage_name:
        stage = Path(stage_name)
        payloads = {
            "source_manifest.json": manifest,
            "official_tests.json": tests,
            "judge_binding.json": judges,
            "fama.json": fama,
            "census.json": census,
            "aggregator.json": aggregator,
            "release_boundary.json": release,
            "paper_locator.json": paper_receipt,
            "environment.json": environment,
            "decision.json": decision,
        }
        for name, value in payloads.items():
            write_json(stage / name, value)
        (stage / "official_pytest.txt").write_text(pytest_text, encoding="utf-8")
        if sorted(path.name for path in stage.iterdir()) != sorted(PRIMARY_OUTPUTS):
            raise AssertionError("primary output set mismatch")
        os.rename(stage, output)


def compare_outputs(left: Path, right: Path, receipt: Path) -> None:
    if receipt.exists():
        raise SystemExit(f"refusing existing --compare-receipt: {receipt}")
    left_files = sorted(path.name for path in left.iterdir() if path.is_file())
    right_files = sorted(path.name for path in right.iterdir() if path.is_file())
    if left_files != sorted(PRIMARY_OUTPUTS) or right_files != sorted(PRIMARY_OUTPUTS):
        raise AssertionError(f"comparison input set mismatch: {left_files}, {right_files}")
    rows: List[Dict[str, str]] = []
    for name in PRIMARY_OUTPUTS:
        lhash = sha256_file(left / name)
        rhash = sha256_file(right / name)
        if lhash != rhash:
            raise AssertionError(f"non-deterministic output: {name}: {lhash} != {rhash}")
        rows.append({"path": name, "sha256": lhash})
    combined = sha256_bytes("".join(f"{row['sha256']}  {row['path']}\n" for row in rows).encode("utf-8"))
    write_json(
        receipt,
        {
            "schema": "memora-audit-reproduction/1",
            "verdict": "REPRODUCIBLE",
            "fresh_output_roots": 2,
            "stable_files_compared": len(rows),
            "byte_identical": True,
            "combined_manifest_sha256": combined,
            "files": rows,
            "boundary": "Same source, paper, Python executable, dependency environment, OS, and machine.",
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=False, help="Exact clean official Memora checkout")
    parser.add_argument("--paper-pdf", type=Path, help="Exact arXiv 2604.20006v1 PDF")
    parser.add_argument("--output", type=Path, help="Fresh output directory (must not exist)")
    parser.add_argument("--pytest-python", type=Path, default=None, help="Python with pytest for official offline tests")
    parser.add_argument("--compare-left", type=Path)
    parser.add_argument("--compare-right", type=Path)
    parser.add_argument("--compare-receipt", type=Path)
    parser.add_argument(
        "--internal-case",
        choices=(
            "historical-track2",
            "current-track2-import-origin",
            "track2-init",
            "track1-init",
            "track1-runtime",
            "track2-runtime",
        ),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--count", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--strict", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.internal_case:
        if args.source is None:
            parser.error("--internal-case requires --source")
        return args
    if args.compare_left or args.compare_right or args.compare_receipt:
        if not all((args.compare_left, args.compare_right, args.compare_receipt)):
            parser.error("comparison requires --compare-left, --compare-right, and --compare-receipt")
        return args
    if not all((args.source, args.paper_pdf, args.output)):
        parser.error("audit mode requires --source, --paper-pdf, and --output")
    return args


def main() -> None:
    args = parse_args()
    if args.internal_case:
        internal_main(args)
    elif args.compare_left:
        compare_outputs(args.compare_left.resolve(), args.compare_right.resolve(), args.compare_receipt.resolve())
    else:
        execute_audit(args)


if __name__ == "__main__":
    main()
