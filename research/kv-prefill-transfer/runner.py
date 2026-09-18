#!/usr/bin/env python3
"""KV prefill transfer runner: prepare / capture / fit / evaluate / smoke.

Every phase links through one run directory (``manifest.json`` plus on-disk
shards):

* ``prepare``  tokenize a local public JSONL with *both* tokenizers, verify the
  token ids agree, truncate long-enough documents to ``seq_len`` and split
  whole documents deterministically.
* ``capture``  load exactly one role model per process, prefill through
  ``model.model(...)`` so no vocabulary logits are computed, and store
  RoPE-stripped K plus native V per document with file-granular resume.
* ``fit``      stream the train shards per target layer, select source layers
  with head-averaged single-layer ridge R^2, then solve one centered ridge per
  target layer and store each layer mapper separately.
* ``evaluate`` load only the target model, rebuild the stored prefixes, and
  teacher-force the held-out continuation on the native, mapped and raw-source
  branches under identical positions and labels.

``kvbridge.ridge.RidgeAccumulator`` is imported from a pinned external checkout
(``--upstream``); this file never re-implements the ridge solver, never vendors
upstream source and never copies a parallel ridge implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from importlib.metadata import version
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, Sequence

import torch

SCHEMA_VERSION = 1
PINNED_UPSTREAM_COMMIT = "949d81d7861e998d5c42db68d7567cc70e2e58c5"
# Bumped whenever the on-disk capture format changes, so a resume cannot reuse
# shards produced by an older storage contract.
CAPTURE_SCHEME = "kv-prefill-capture-v3"
RUNNER_CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
RUNTIME_VERSIONS = {"torch": torch.__version__, "transformers": version("transformers")}
POSITION_SCHEME = "contiguous-from-zero"
DTYPE_NAMES = {
    "bfloat16": torch.bfloat16,
    "float16": torch.float16,
    "float32": torch.float32,
}
SPLITS = ("train", "validation", "test")
ROLES = ("source", "target")
DEFAULT_SEED = 260803893
EVIDENCE_KINDS = ("pretrained-transfer", "random-model-smoke")
# Stored content K is never quantized below float32: it is the fitting input and
# the input to the mapper, and the strip/re-apply RoPE round trip is only a
# real-valued inverse of a numerically rounded rotation.
CONTENT_KEY_DTYPE = torch.float32

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "evidence_kind": "pretrained-transfer",
    "seed": DEFAULT_SEED,
    "threads": 1,
    "seq_len": 256,
    "prefix_len": 192,
    "stride": 4,
    "dtype": "bfloat16",
    "top_k": 1,
    "ridge_alpha": 0.01,
    "selection_alpha": 1e-6,
    "splits": {"train": 64, "validation": 8, "test": 16},
    "source": {"model": None, "revision": None, "origin": "pretrained"},
    "target": {"model": None, "revision": None, "origin": "pretrained"},
    "data": {"kind": "jsonl", "path": None},
    "fit": {
        "accumulation_dtype": "float64",
        "content_space": True,
        "max_statistics_bytes": 536_870_912,
    },
}


class RunnerError(RuntimeError):
    """A structural contract violation raised by this runner."""


class IdentityError(RunnerError):
    """A model, tokenizer, token or configuration identity did not match."""


class PhaseStateError(RunnerError):
    """A phase was invoked before its prerequisites were complete."""


# --------------------------------------------------------------------------
# small utilities
# --------------------------------------------------------------------------


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PhaseStateError(f"missing required file: {path}") from error
    except json.JSONDecodeError as error:
        raise RunnerError(f"could not parse JSON at {path}: {error}") from error


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------


def resolve_config(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RunnerError("config must be a JSON object")
    config = deep_merge(json.loads(json.dumps(DEFAULT_CONFIG)), raw)
    if config.get("schema_version") != SCHEMA_VERSION:
        raise RunnerError(f"unsupported config schema_version: {config.get('schema_version')}")
    if config["evidence_kind"] not in EVIDENCE_KINDS:
        raise RunnerError(f"evidence_kind must be one of {EVIDENCE_KINDS}")
    if config["dtype"] not in DTYPE_NAMES:
        raise RunnerError(f"dtype must be one of {sorted(DTYPE_NAMES)}")
    config["seq_len"] = int(config["seq_len"])
    config["prefix_len"] = int(config["prefix_len"])
    config["stride"] = int(config["stride"])
    config["threads"] = int(config["threads"])
    config["top_k"] = int(config["top_k"])
    if not 0 < config["prefix_len"] < config["seq_len"]:
        raise RunnerError("require 0 < prefix_len < seq_len")
    if config["stride"] < 1:
        raise RunnerError("stride must be >= 1")
    if config["top_k"] < 1:
        raise RunnerError("top_k must be >= 1")
    if float(config["ridge_alpha"]) < 0 or float(config["selection_alpha"]) <= 0:
        raise RunnerError("require ridge_alpha >= 0 and selection_alpha > 0")
    if config["threads"] < 1:
        raise RunnerError("threads must be >= 1")
    for split in SPLITS:
        size = config["splits"].get(split)
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            raise RunnerError(f"splits.{split} must be a positive integer")
    for role in ROLES:
        entry = config[role]
        if not isinstance(entry, dict) or not entry.get("model"):
            raise RunnerError(f"config.{role}.model is required")
        if entry.get("origin") not in ("pretrained", "local"):
            raise RunnerError(f"config.{role}.origin must be pretrained or local")
        if entry["origin"] == "pretrained" and not entry.get("revision"):
            raise RunnerError(f"config.{role}.revision is required for pretrained models")
    data = config["data"]
    if not isinstance(data, dict) or data.get("kind") not in ("jsonl", "synthetic"):
        raise RunnerError("config.data.kind must be jsonl or synthetic")
    if data["kind"] == "jsonl" and not data.get("path"):
        raise RunnerError("config.data.path is required for jsonl data")
    if data["kind"] == "synthetic":
        data.setdefault("num_documents", 32)
        data.setdefault("vocab_size", 128)
        data.setdefault("min_tokens", config["seq_len"])
        data.setdefault("max_tokens", config["seq_len"] + config["seq_len"] // 2)
    if config["fit"]["accumulation_dtype"] != "float64" or config["fit"]["content_space"] is not True:
        raise RunnerError("this runner requires float64 statistics and content_space=true")
    return config


def configure_threads(config: dict[str, Any]) -> None:
    torch.set_num_threads(int(config["threads"]))
    torch.manual_seed(int(config["seed"]))


# --------------------------------------------------------------------------
# pinned upstream import
# --------------------------------------------------------------------------


def git_head(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RunnerError(
            f"could not read the git HEAD of the upstream checkout at {root}: {error}"
        ) from error
    return completed.stdout.strip()


def load_upstream(path_value: str | None, expected_commit: str) -> SimpleNamespace:
    if not path_value:
        raise RunnerError(
            "the upstream checkout is required; pass --upstream PATH or set KVPREFILL_UPSTREAM"
        )
    root = Path(path_value).expanduser().resolve()
    if not root.is_dir():
        raise RunnerError(f"upstream checkout not found: {root}")
    actual = git_head(root)
    if actual != expected_commit:
        raise RunnerError(
            f"upstream checkout {root} is at {actual}, expected pinned commit {expected_commit}"
        )
    source_root = root / "src"
    if not source_root.is_dir():
        raise RunnerError(f"upstream checkout has no src/ directory: {root}")
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

    import kvbridge.cache as cache_module
    import kvbridge.config as config_module
    import kvbridge.errors as errors_module
    import kvbridge.features as features_module
    import kvbridge.huggingface as huggingface_module
    import kvbridge.mapper as mapper_module
    import kvbridge.metrics as metrics_module
    import kvbridge.ridge as ridge_module

    modules = (
        cache_module,
        config_module,
        errors_module,
        features_module,
        huggingface_module,
        mapper_module,
        metrics_module,
        ridge_module,
    )
    for module in modules:
        resolved = Path(module.__file__).resolve()
        if not resolved.is_relative_to(root):
            raise RunnerError(
                f"module {module.__name__} resolved to {resolved}, outside the pinned checkout"
            )
    return SimpleNamespace(
        root=root,
        commit=actual,
        cache=cache_module,
        config=config_module,
        errors=errors_module,
        features=features_module,
        huggingface=huggingface_module,
        mapper=mapper_module,
        metrics=metrics_module,
        ridge=ridge_module,
        RidgeAccumulator=ridge_module.RidgeAccumulator,
        CrossModelKVMapper=mapper_module.CrossModelKVMapper,
        FitConfig=config_module.FitConfig,
        ModelSignature=config_module.ModelSignature,
    )


# --------------------------------------------------------------------------
# run directory + manifest
# --------------------------------------------------------------------------


class RunDir:
    """Filesystem contract shared by every phase."""

    def __init__(self, root: Path):
        self.root = root

    @classmethod
    def open(cls, path: str | Path) -> "RunDir":
        root = Path(path).expanduser().resolve()
        if not (root / "manifest.json").is_file():
            raise PhaseStateError(f"{root} is not a run directory (no manifest.json)")
        return cls(root)

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def manifest(self) -> dict[str, Any]:
        return read_json(self.manifest_path)

    def save_manifest(self, manifest: dict[str, Any]) -> None:
        manifest["updated_utc"] = utc_now()
        write_json_atomic(self.manifest_path, manifest)

    def config(self) -> dict[str, Any]:
        return self.manifest()["config"]

    def phase(self, name: str) -> dict[str, Any]:
        return self.manifest()["phases"].get(name, {"status": "pending"})

    def require_phase(self, name: str) -> dict[str, Any]:
        phase = self.phase(name)
        if phase.get("status") != "complete":
            raise PhaseStateError(f"phase {name!r} is not complete in {self.root}")
        return phase

    def set_phase(self, name: str, receipt: dict[str, Any]) -> None:
        manifest = self.manifest()
        manifest["phases"][name] = receipt
        self.save_manifest(manifest)

    def dataset_fingerprint(self) -> str:
        return self.require_phase("prepare")["dataset_fingerprint"]


def new_run_dir(root: Path, config: dict[str, Any], upstream: SimpleNamespace) -> RunDir:
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        raise RunnerError(f"refusing to reuse an existing run directory: {root}")
    run = RunDir(root)
    run.save_manifest(
        {
            "schema_version": SCHEMA_VERSION,
            "created_utc": utc_now(),
            "config": config,
            "config_sha256": canonical_digest(config),
            "upstream_commit": upstream.commit,
            "runner": "research/kv-prefill-transfer/runner.py",
            "runner_code_sha256": RUNNER_CODE_SHA256,
            "runtime_versions": RUNTIME_VERSIONS,
            "phases": {},
        }
    )
    return run


# --------------------------------------------------------------------------
# model / tokenizer identity
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelIdentity:
    role: str
    model_ref: str
    revision: str
    origin: str
    architecture: str
    num_layers: int
    num_kv_heads: int
    head_dim: int
    hidden_size: int
    num_attention_heads: int
    rope_theta: float
    dtype: str
    tokenizer_hash: str
    tokenizer_identity_kind: str

    def payload(self) -> dict[str, Any]:
        return {
            "model_ref": self.model_ref,
            "revision": self.revision,
            "origin": self.origin,
            "architecture": self.architecture,
            "num_layers": self.num_layers,
            "num_kv_heads": self.num_kv_heads,
            "head_dim": self.head_dim,
            "hidden_size": self.hidden_size,
            "num_attention_heads": self.num_attention_heads,
            "rope_theta": self.rope_theta,
            "dtype": self.dtype,
            "tokenizer_hash": self.tokenizer_hash,
            "tokenizer_identity_kind": self.tokenizer_identity_kind,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_digest(self.payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self.payload()
        payload["role"] = self.role
        payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_receipt(cls, receipt: dict[str, Any], role: str) -> "ModelIdentity":
        payload = {key: value for key, value in receipt.items()
                   if key not in {"role", "fingerprint"}}
        return cls(role=role, **payload)

    def upstream_signature(self, upstream: SimpleNamespace) -> Any:
        return upstream.ModelSignature(
            model_id=self.model_ref,
            revision=self.revision or "local",
            tokenizer_hash=self.tokenizer_hash,
            num_layers=self.num_layers,
            num_kv_heads=self.num_kv_heads,
            head_dim=self.head_dim,
            attention_kind="dense",
            architecture=self.architecture,
        )


def _from_pretrained_kwargs(entry: dict[str, Any]) -> dict[str, Any]:
    return {"revision": entry["revision"]} if entry["origin"] == "pretrained" else {}


def tokenizer_fingerprint(tokenizer: Any) -> str:
    payload = {
        "vocab": sorted((str(key), int(value)) for key, value in tokenizer.get_vocab().items()),
        "special_tokens_map": tokenizer.special_tokens_map,
        "added_tokens": sorted(
            (str(key), str(value)) for key, value in tokenizer.get_added_vocab().items()
        ),
    }
    return canonical_digest(payload)


def resolve_tokenizer_identity(entry: dict[str, Any]) -> tuple[str, str]:
    """Return ``(tokenizer_hash, kind)``; never silently fake a pretrained tokenizer."""
    from transformers import AutoConfig, AutoTokenizer

    kwargs = _from_pretrained_kwargs(entry)
    try:
        tokenizer = AutoTokenizer.from_pretrained(entry["model"], **kwargs)
    except Exception as error:
        if entry["origin"] == "pretrained":
            raise IdentityError(
                f"could not load the tokenizer for pretrained model {entry['model']!r}: {error}"
            ) from error
        config = AutoConfig.from_pretrained(entry["model"])
        payload = {
            "kind": "synthetic-config-fallback",
            "model_type": getattr(config, "model_type", "unknown"),
            "vocab_size": getattr(config, "vocab_size", None),
            "architecture": (getattr(config, "architectures", None) or [None])[0],
        }
        return canonical_digest(payload), "synthetic-config-fallback"
    return tokenizer_fingerprint(tokenizer), "hf-tokenizer"


def describe_model(model: Any, role: str, entry: dict[str, Any], tokenizer_hash: str,
                   tokenizer_kind: str, dtype_name: str) -> ModelIdentity:
    config = model.config
    head_dim = int(getattr(config, "head_dim") or config.hidden_size // config.num_attention_heads)
    kv_heads = int(getattr(config, "num_key_value_heads", None) or config.num_attention_heads)
    return ModelIdentity(
        role=role,
        model_ref=str(entry["model"]),
        revision=str(entry.get("revision") or "local"),
        origin=str(entry["origin"]),
        architecture=str((config.architectures or [config.model_type])[0]),
        num_layers=int(config.num_hidden_layers),
        num_kv_heads=kv_heads,
        head_dim=head_dim,
        hidden_size=int(config.hidden_size),
        num_attention_heads=int(config.num_attention_heads),
        rope_theta=float(getattr(config, "rope_theta", 0.0) or 0.0),
        dtype=dtype_name,
        tokenizer_hash=tokenizer_hash,
        tokenizer_identity_kind=tokenizer_kind,
    )


def validate_transfer_pair(source: ModelIdentity, target: ModelIdentity) -> None:
    if source.tokenizer_hash != target.tokenizer_hash:
        raise IdentityError("source and target tokenizers differ; token positions would not align")
    if source.num_kv_heads != target.num_kv_heads:
        raise IdentityError(
            "this path requires matched KV-head counts; "
            f"source={source.num_kv_heads} target={target.num_kv_heads}"
        )


def direct_source_skip_reason(source: ModelIdentity, target: ModelIdentity) -> str:
    """Why the raw-source sham cannot be built for this pair, if it cannot."""
    if source.head_dim != target.head_dim:
        return (
            f"head_dim differs ({source.head_dim} vs {target.head_dim}); raw source K cannot "
            "occupy target positions"
        )
    if source.num_kv_heads != target.num_kv_heads:
        return (
            f"KV-head count differs ({source.num_kv_heads} vs {target.num_kv_heads}); raw "
            "source K cannot occupy target positions"
        )
    if source.num_layers != target.num_layers:
        return (
            f"layer counts differ ({source.num_layers} vs {target.num_layers}); a raw source "
            "prefix cannot fill every target layer"
        )
    return "unknown geometry mismatch"


def load_role_model(config: dict[str, Any], role: str) -> tuple[Any, bool]:
    """Load one role model, returning ``(model, low_cpu_mem_usage_used)``.

    The attention implementation is pinned to eager so the measured backend is
    the one the protocol fixes; the actual resolved backend is recorded in the
    capture and evaluation receipts.
    """
    from transformers import AutoModelForCausalLM

    entry = config[role]
    dtype = DTYPE_NAMES[config["dtype"]]
    kwargs = {"torch_dtype": dtype, "attn_implementation": "eager", **_from_pretrained_kwargs(entry)}
    # A failed low-memory load must stay visible; silently disabling it would
    # invalidate the resource budget for the real-model stages.
    model = AutoModelForCausalLM.from_pretrained(
        entry["model"], low_cpu_mem_usage=True, **kwargs
    )
    model.eval()
    return model, True


def attention_backend(model: Any) -> str:
    """The attention implementation the loaded model actually resolved to."""
    return str(getattr(model.config, "_attn_implementation", "unknown"))


def accelerate_available() -> bool:
    """Whether the optional low-memory loading backend is importable."""
    import importlib.util

    return importlib.util.find_spec("accelerate") is not None


# --------------------------------------------------------------------------
# dataset preparation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedDocument:
    index: int
    doc_id: str
    split: str
    text_sha256: str
    num_tokens: int
    truncated: bool
    source_url: str | None
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "doc_id": self.doc_id,
            "split": self.split,
            "text_sha256": self.text_sha256,
            "num_tokens": self.num_tokens,
            "truncated": self.truncated,
            "source_url": self.source_url,
            "evidence": self.evidence,
        }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise RunnerError(f"{path}:{line_number} is not valid JSON: {error}") from error
            if not isinstance(record, dict) or "id" not in record or "text" not in record:
                raise RunnerError(f"{path}:{line_number} must contain 'id' and 'text'")
            records.append(record)
    return records


def synthetic_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    data = config["data"]
    generator = random.Random(int(config["seed"]))
    records = []
    for index in range(int(data["num_documents"])):
        length = generator.randint(int(data["min_tokens"]), int(data["max_tokens"]))
        token_ids = [generator.randrange(3, int(data["vocab_size"])) for _ in range(length)]
        records.append(
            {
                "id": f"synthetic-{index:05d}",
                "text": " ".join(str(token) for token in token_ids),
                "token_ids": token_ids,
                "source_url": None,
                "evidence": "synthetic-token-ids",
            }
        )
    return records


def deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_id: dict[str, str] = {}
    unique_by_id: list[dict[str, Any]] = []
    duplicate_ids = 0
    for record in records:
        doc_id = str(record["id"])
        if doc_id in by_id:
            if by_id[doc_id] != record["text_sha256"]:
                raise IdentityError(f"document id {doc_id!r} appears with two different texts")
            duplicate_ids += 1
            continue
        by_id[doc_id] = record["text_sha256"]
        unique_by_id.append(record)
    seen_text: dict[str, str] = {}
    unique: list[dict[str, Any]] = []
    duplicate_text = 0
    for record in unique_by_id:
        previous = seen_text.get(record["text_sha256"])
        if previous is not None:
            log(f"dropping {record['id']!r}: text identity already kept as {previous!r}")
            duplicate_text += 1
            continue
        seen_text[record["text_sha256"]] = record["id"]
        unique.append(record)
    return unique, {"duplicate_ids": duplicate_ids, "duplicate_text": duplicate_text}


def assign_splits(records: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    sizes = {split: int(config["splits"][split]) for split in SPLITS}
    required = sum(sizes.values())
    if len(records) < required:
        raise RunnerError(
            f"need at least {required} usable documents for splits {sizes}, found {len(records)}"
        )
    seed = int(config["seed"])
    ordered = sorted(
        records,
        key=lambda record: sha256_text(f"{seed}|{record['id']}|{record['text_sha256']}"),
    )
    cursor = 0
    assignment: dict[str, list[dict[str, Any]]] = {}
    for split in SPLITS:
        assignment[split] = ordered[cursor : cursor + sizes[split]]
        cursor += sizes[split]
    owners: dict[str, str] = {}
    for split in SPLITS:
        for record in assignment[split]:
            for key in (record["id"], record["text_sha256"]):
                if owners.setdefault(key, split) != split:
                    raise IdentityError(
                        f"identity {key!r} would appear in both {owners[key]} and {split}"
                    )
    return assignment


def phase_prepare(config: dict[str, Any], out_dir: Path, upstream: SimpleNamespace) -> dict[str, Any]:
    configure_threads(config)
    run = new_run_dir(out_dir, config, upstream)
    root = run.root

    tokenizer_identity = {}
    for role in ROLES:
        tokenizer_hash, kind = resolve_tokenizer_identity(config[role])
        tokenizer_identity[role] = {"hash": tokenizer_hash, "kind": kind}
    if tokenizer_identity["source"]["hash"] != tokenizer_identity["target"]["hash"]:
        raise IdentityError(
            "source and target tokenizer identities differ before tokenization: "
            f"{tokenizer_identity['source']} vs {tokenizer_identity['target']}"
        )

    data = config["data"]
    if data["kind"] == "jsonl":
        from transformers import AutoTokenizer

        tokenizers = {}
        for role in ROLES:
            if tokenizer_identity[role]["kind"] != "hf-tokenizer":
                raise IdentityError(
                    f"jsonl preparation requires real tokenizers; {role} resolved to "
                    f"{tokenizer_identity[role]['kind']}"
                )
            tokenizers[role] = AutoTokenizer.from_pretrained(
                config[role]["model"], **_from_pretrained_kwargs(config[role])
            )
        records = []
        for raw in read_jsonl(Path(data["path"]).expanduser()):
            text = str(raw["text"])
            if not text.strip():
                continue
            source_ids = tokenizers["source"](text, add_special_tokens=False)["input_ids"]
            target_ids = tokenizers["target"](text, add_special_tokens=False)["input_ids"]
            if source_ids != target_ids:
                shared = min(len(source_ids), len(target_ids))
                offset = next(
                    (position for position in range(shared)
                     if source_ids[position] != target_ids[position]),
                    shared,
                )
                raise IdentityError(
                    f"token ids differ for document {raw['id']!r} at position {offset}: "
                    f"source={source_ids[offset:offset + 4]} target={target_ids[offset:offset + 4]}"
                )
            records.append(
                {
                    "id": str(raw["id"]),
                    "text": text,
                    "text_sha256": sha256_text(text),
                    "token_ids": source_ids,
                    "source_url": raw.get("source_url"),
                    "evidence": "public-jsonl",
                }
            )
        alignment = "two-tokenizers"
    else:
        records = [
            {
                **record,
                "text_sha256": sha256_text(record["text"]),
                "evidence": record.get("evidence", "synthetic-token-ids"),
            }
            for record in synthetic_records(config)
        ]
        alignment = "synthetic-token-ids"

    records, dedupe = deduplicate(records)
    retained = []
    dropped_short = 0
    for record in records:
        token_ids = list(record["token_ids"])
        if len(token_ids) < config["seq_len"]:
            dropped_short += 1
            continue
        record["truncated"] = len(token_ids) > config["seq_len"]
        record["token_ids"] = token_ids[: config["seq_len"]]
        retained.append(record)
    assignment = assign_splits(retained, config)

    documents: list[PreparedDocument] = []
    tokens_payload: dict[str, torch.Tensor] = {}
    for split in SPLITS:
        for record in assignment[split]:
            index = len(documents)
            documents.append(
                PreparedDocument(
                    index=index,
                    doc_id=record["id"],
                    split=split,
                    text_sha256=record["text_sha256"],
                    num_tokens=len(record["token_ids"]),
                    truncated=bool(record["truncated"]),
                    source_url=record.get("source_url"),
                    evidence=record["evidence"],
                )
            )
            tokens_payload[f"tokens.{index}"] = torch.tensor(record["token_ids"], dtype=torch.int64)

    from safetensors.torch import save_file

    tokens_path = root / "prepare" / "tokens.safetensors"
    tokens_path.parent.mkdir(parents=True, exist_ok=True)
    save_file(tokens_payload, str(tokens_path))
    with (root / "prepare" / "docs.jsonl").open("w", encoding="utf-8") as stream:
        for document in documents:
            stream.write(json.dumps(document.to_dict(), sort_keys=True) + "\n")

    serialized = [document.to_dict() for document in documents]
    dataset_fingerprint = canonical_digest(
        {
            "schema_version": SCHEMA_VERSION,
            "config_sha256": canonical_digest(config),
            "tokenizer_identity": tokenizer_identity,
            "documents": serialized,
        }
    )
    counts = {split: sum(1 for document in documents if document.split == split)
              for split in SPLITS}
    receipt = {
        "status": "complete",
        "phase": "prepare",
        "created_utc": utc_now(),
        "dataset_fingerprint": dataset_fingerprint,
        "evidence_kind": config["evidence_kind"],
        "token_alignment": alignment,
        "tokenization": {"add_special_tokens": False},
        "tokenizer_identity": tokenizer_identity,
        "counts": counts,
        "available_documents": len(retained),
        "dropped_short": dropped_short,
        "dedupe": dedupe,
        "tokens_file": "prepare/tokens.safetensors",
        "tokens_sha256": sha256_file(tokens_path),
        "documents": serialized,
    }
    write_json_atomic(root / "prepare" / "receipt.json", receipt)
    run.set_phase(
        "prepare",
        {
            "status": "complete",
            "receipt": "prepare/receipt.json",
            "dataset_fingerprint": dataset_fingerprint,
            "counts": counts,
            "evidence_kind": config["evidence_kind"],
            "token_alignment": alignment,
        },
    )
    return receipt


def load_prepared(run: RunDir) -> tuple[list[PreparedDocument], dict[int, torch.Tensor]]:
    from safetensors.torch import load_file

    receipt = read_json(run.path("prepare", "receipt.json"))
    tokens_path = run.path("prepare", "tokens.safetensors")
    if sha256_file(tokens_path) != receipt["tokens_sha256"]:
        raise IdentityError("prepared token file differs from its recorded input identity")
    documents = [PreparedDocument(**entry) for entry in receipt["documents"]]
    tensors = load_file(str(tokens_path), device="cpu")
    return documents, {index: tensors[f"tokens.{index}"] for index in range(len(documents))}


def documents_by_split(documents: Sequence[PreparedDocument]) -> dict[str, list[PreparedDocument]]:
    return {split: [document for document in documents if document.split == split]
            for split in SPLITS}


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------


def clone_cache(cache: Any, upstream: SimpleNamespace) -> Any:
    return upstream.cache.KVCache(
        [tensor.clone() for tensor in cache.keys],
        [tensor.clone() for tensor in cache.values],
        cache.rotary,
        cache.keys_are_content,
    )


def capture_kv(model: Any, input_ids: torch.Tensor,
               upstream: SimpleNamespace) -> tuple[Any, Any, dict[str, float]]:
    """Prefill once through ``model.model(...)`` and return three things.

    ``content`` holds the RoPE-stripped K in float32 (the fitting input) with the
    native V. ``raw`` holds the model's own post-RoPE K and V exactly as the
    model produced them. The strip/re-apply round trip is only a real-valued
    inverse of a numerically rounded rotation, so it is reported as a diagnostic
    instead of being treated as an exact recovery of the pre-RoPE content.
    """
    device = model.get_input_embeddings().weight.device
    ids = input_ids.to(device).unsqueeze(0)
    positions = torch.arange(ids.shape[1], device=device).unsqueeze(0)
    base = model.model(
        input_ids=ids,
        attention_mask=torch.ones_like(ids),
        position_ids=positions,
        use_cache=True,
        return_dict=True,
    )
    layers = upstream.huggingface._legacy_layers(base.past_key_values)
    factors = upstream.huggingface.capture_rotary_factors(model, positions)
    raw_keys = tuple(layer[0].detach() for layer in layers)
    values = tuple(layer[1].detach() for layer in layers)
    content_keys = tuple(
        factors.apply(tensor.float(), inverse=True).to(CONTENT_KEY_DTYPE).contiguous()
        for tensor in raw_keys
    )
    reencoded = tuple(factors.apply(tensor) for tensor in content_keys)
    squared_error = sum(
        float(((left.double() - right.double()) ** 2).sum())
        for left, right in zip(reencoded, raw_keys, strict=True)
    )
    squared_total = sum(
        float(((tensor.double() - tensor.double().mean()) ** 2).sum()) for tensor in raw_keys
    )
    diagnostics = {
        "content_roundtrip_max_abs": max(
            float((left.double() - right.double()).abs().max())
            for left, right in zip(reencoded, raw_keys, strict=True)
        ),
        "content_roundtrip_r2": (
            1.0 - squared_error / squared_total if squared_total > 0 else float("nan")
        ),
    }
    content = upstream.cache.KVCache(content_keys, values, None, keys_are_content=True)
    raw = upstream.cache.KVCache(raw_keys, values, factors, keys_are_content=False)
    return content, raw, diagnostics


def shard_paths(run: RunDir, role: str, split: str, index: int) -> tuple[Path, Path]:
    return (
        run.path("shards", role, split, f"{index:05d}.safetensors"),
        run.path("receipts", role, split, f"{index:05d}.json"),
    )


def save_shard(path: Path, content: Any, raw: Any | None, input_ids: torch.Tensor,
               position_ids: torch.Tensor, metadata: dict[str, str]) -> None:
    from safetensors.torch import save_file

    payload: dict[str, torch.Tensor] = {}
    for layer, (key, value) in enumerate(zip(content.keys, content.values, strict=True)):
        if key.shape[0] != 1 or value.shape[0] != 1:
            raise RunnerError("shards store a single sequence; batch dimension must be one")
        # Store without the batch axis: [kv_heads, tokens, head_dim].
        payload[f"key.{layer}"] = key[0].detach().to("cpu").contiguous()
        payload[f"value.{layer}"] = value[0].detach().to("cpu").contiguous()
    if raw is not None:
        for layer, key in enumerate(raw.keys):
            payload[f"raw_key.{layer}"] = key[0].detach().to("cpu").contiguous()
    payload["input_ids"] = input_ids.to("cpu").to(torch.int64).contiguous()
    payload["position_ids"] = position_ids.to("cpu").to(torch.int64).contiguous()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    save_file(payload, str(temporary), metadata=metadata)
    os.replace(temporary, path)


@dataclass
class LoadedShard:
    role: str
    split: str
    index: int
    keys: list[torch.Tensor]
    values: list[torch.Tensor]
    input_ids: torch.Tensor
    position_ids: torch.Tensor
    dtype_name: str
    raw_keys: list[torch.Tensor] | None = None

    @property
    def num_layers(self) -> int:
        return len(self.keys)

    @property
    def num_kv_heads(self) -> int:
        return int(self.keys[0].shape[0])

    @property
    def head_dim(self) -> int:
        return int(self.keys[0].shape[2])

    def cache(self, upstream: SimpleNamespace) -> Any:
        return upstream.cache.KVCache(
            [tensor.unsqueeze(0) for tensor in self.keys],
            [tensor.unsqueeze(0) for tensor in self.values],
            None,
            keys_are_content=True,
        )

    def native_cache(self, upstream: SimpleNamespace) -> Any:
        """The model's own post-RoPE K with its native V, exactly as captured."""
        if self.raw_keys is None:
            raise PhaseStateError(
                f"target shard {self.role}/{self.split}/{self.index} carries no raw "
                "post-RoPE K; re-capture with the current capture scheme"
            )
        return upstream.cache.KVCache(
            [tensor.unsqueeze(0) for tensor in self.raw_keys],
            [tensor.unsqueeze(0) for tensor in self.values],
            None,
            keys_are_content=False,
        )

    def content_rotated(self, upstream: SimpleNamespace, factors: Any) -> Any:
        """Content K re-encoded with the target RoPE, for the round-trip diagnostic."""
        return self.cache(upstream).apply_rotary(factors)


def keeps_raw_key(role: str, split: str) -> bool:
    """Raw post-RoPE K is kept only for the held-out target reference."""
    return role == "target" and split != "train"


def capture_scheme_fields() -> dict[str, str]:
    return {
        "runner_schema_version": str(SCHEMA_VERSION),
        "capture_scheme": CAPTURE_SCHEME,
        "runner_code_sha256": RUNNER_CODE_SHA256,
        "attention_backend": "eager",
        **RUNTIME_VERSIONS,
        "content_key": "rope-stripped-float32",
        "native_value": "model-dtype",
        "position_scheme": POSITION_SCHEME,
    }


def capture_identity(role: str, split: str, index: int, capture_ids: torch.Tensor,
                     positions: torch.Tensor, stride: int, manifest_fingerprint: str,
                     model_fingerprint: str) -> dict[str, str]:
    """Every field a resume must match before a shard may be reused."""
    return {
        "role": role,
        "split": split,
        "doc_index": str(index),
        "manifest_fingerprint": manifest_fingerprint,
        "model_fingerprint": model_fingerprint,
        "input_ids_sha256": sha256_bytes(capture_ids.numpy().tobytes()),
        "position_ids_sha256": sha256_bytes(positions.numpy().tobytes()),
        "token_stride": str(stride),
        "has_raw_key": "true" if keeps_raw_key(role, split) else "false",
        **capture_scheme_fields(),
    }


def capture_input_ids(split: str, token_ids: torch.Tensor,
                      config: dict[str, Any]) -> tuple[torch.Tensor, int]:
    """The exact token slice a capture shard binds to: train uses the whole document."""
    if split == "train":
        return token_ids, int(config["stride"])
    return token_ids[: int(config["prefix_len"]) - 1], 1


def capture_plan(split: str, token_ids: torch.Tensor,
                 config: dict[str, Any]) -> tuple[torch.Tensor, int, torch.Tensor]:
    capture_ids, stride = capture_input_ids(split, token_ids, config)
    positions = torch.arange(len(capture_ids))[::stride].to(torch.int64)
    return capture_ids, stride, positions


def load_shard(run: RunDir, role: str, split: str, index: int, expected: dict[str, str]) -> LoadedShard:
    from safetensors.torch import load_file

    shard_path, receipt_path = shard_paths(run, role, split, index)
    receipt = read_json(receipt_path)
    if receipt.get("status") != "complete":
        raise PhaseStateError(f"shard receipt {receipt_path} is not complete")
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise IdentityError(
                f"shard {shard_path} has {field}={receipt.get(field)!r}, expected {value!r}"
            )
    if not shard_path.is_file():
        raise PhaseStateError(f"shard file missing: {shard_path}")
    if sha256_file(shard_path) != receipt["shard_sha256"]:
        raise IdentityError(f"shard {shard_path} does not match its recorded checksum")
    tensors = load_file(str(shard_path), device="cpu")
    layers = sum(1 for key in tensors if key.startswith("key."))
    raw_layers = sum(1 for key in tensors if key.startswith("raw_key."))
    return LoadedShard(
        role=role,
        split=split,
        index=index,
        keys=[tensors[f"key.{layer}"] for layer in range(layers)],
        values=[tensors[f"value.{layer}"] for layer in range(layers)],
        input_ids=tensors["input_ids"],
        position_ids=tensors["position_ids"],
        dtype_name=receipt["capture_dtype"],
        raw_keys=(
            [tensors[f"raw_key.{layer}"] for layer in range(raw_layers)]
            if raw_layers
            else None
        ),
    )


def shard_is_complete(run: RunDir, role: str, split: str, index: int,
                      expected: dict[str, str]) -> bool:
    shard_path, receipt_path = shard_paths(run, role, split, index)
    if not shard_path.is_file() or not receipt_path.is_file():
        return False
    try:
        receipt = read_json(receipt_path)
    except RunnerError:
        return False
    if receipt.get("status") != "complete":
        return False
    if any(receipt.get(field) != value for field, value in expected.items()):
        return False
    return sha256_file(shard_path) == receipt.get("shard_sha256")


def phase_capture(run: RunDir, role: str, config: dict[str, Any],
                  upstream: SimpleNamespace) -> dict[str, Any]:
    configure_threads(config)
    prepare = run.require_phase("prepare")
    dataset_fingerprint = prepare["dataset_fingerprint"]
    tokenizer_identity = read_json(run.path("prepare", "receipt.json"))["tokenizer_identity"][role]

    model, low_cpu_memory = load_role_model(config, role)
    identity = describe_model(
        model, role, config[role], tokenizer_identity["hash"], tokenizer_identity["kind"],
        config["dtype"],
    )
    previous = run.phase(f"capture_{role}")
    if previous.get("status") == "complete" and previous.get("model_fingerprint") != identity.fingerprint:
        raise IdentityError(
            f"capture_{role} was already recorded with a different model: "
            f"{previous['model_fingerprint']} != {identity.fingerprint}"
        )

    documents, tokens = load_prepared(run)
    splits = documents_by_split(documents)
    eval_prefix_len = int(config["prefix_len"]) - 1
    written = 0
    skipped = 0
    shard_indices: dict[str, list[int]] = {split: [] for split in SPLITS}

    for split in SPLITS:
        for document in splits[split]:
            token_ids = tokens[document.index]
            capture_ids, stride, positions = capture_plan(split, token_ids, config)
            expected = capture_identity(
                role, split, document.index, capture_ids, positions, stride,
                dataset_fingerprint, identity.fingerprint,
            )
            shard_path, receipt_path = shard_paths(run, role, split, document.index)
            if shard_is_complete(run, role, split, document.index, expected):
                skipped += 1
                shard_indices[split].append(document.index)
                continue
            with torch.inference_mode():
                content, raw, diagnostics = capture_kv(model, capture_ids, upstream)
                sampled_content = content.sample_tokens(stride)
                sampled_raw = (
                    raw.sample_tokens(stride) if keeps_raw_key(role, split) else None
                )
            save_shard(
                shard_path,
                sampled_content,
                sampled_raw,
                capture_ids,
                positions,
                {
                    "runner_schema_version": str(SCHEMA_VERSION),
                    "capture_dtype": config["dtype"],
                    "rope": "stripped-float32-content",
                    "layout": "kv_heads,tokens,head_dim",
                    **expected,
                },
            )
            write_json_atomic(
                receipt_path,
                {
                    "status": "complete",
                    "created_utc": utc_now(),
                    "shard": str(shard_path.relative_to(run.root)),
                    "shard_sha256": sha256_file(shard_path),
                    "num_key_layers": len(sampled_content.keys),
                    "num_tokens": int(sampled_content.keys[0].shape[2]),
                    "num_kv_heads": int(sampled_content.keys[0].shape[1]),
                    "head_dim": int(sampled_content.keys[0].shape[3]),
                    "first_positions": positions[:8].tolist(),
                    "capture_dtype": config["dtype"],
                    "content_key_dtype": str(CONTENT_KEY_DTYPE).replace("torch.", ""),
                    "raw_key_stored": sampled_raw is not None,
                    "content_roundtrip_max_abs": diagnostics["content_roundtrip_max_abs"],
                    "content_roundtrip_r2": diagnostics["content_roundtrip_r2"],
                    **expected,
                },
            )
            written += 1
            shard_indices[split].append(document.index)
        log(f"capture {role} {split}: {len(shard_indices[split])} shards ready")

    receipt = {
        "status": "complete",
        "phase": f"capture_{role}",
        "created_utc": utc_now(),
        "role": role,
        "model": identity.to_dict(),
        "model_fingerprint": identity.fingerprint,
        "manifest_fingerprint": dataset_fingerprint,
        "capture_dtype": config["dtype"],
        "attention_backend": attention_backend(model),
        "stride": int(config["stride"]),
        "eval_prefix_len": eval_prefix_len,
        "low_cpu_mem_usage": low_cpu_memory,
        "accelerate_available": accelerate_available(),
        "written": written,
        "skipped_complete": skipped,
        "counts": {split: len(shard_indices[split]) for split in SPLITS},
        "shards": {split: sorted(shard_indices[split]) for split in SPLITS},
    }
    write_json_atomic(run.path("capture", role, "receipt.json"), receipt)
    run.set_phase(
        f"capture_{role}",
        {
            "status": "complete",
            "receipt": f"capture/{role}/receipt.json",
            "model_fingerprint": identity.fingerprint,
            "counts": receipt["counts"],
        },
    )
    return receipt


def capture_role_identities(run: RunDir) -> tuple[ModelIdentity, ModelIdentity]:
    identities = []
    for role in ROLES:
        phase = run.require_phase(f"capture_{role}")
        payload = read_json(run.path("capture", role, "receipt.json"))["model"]
        identity = ModelIdentity.from_receipt(payload, role)
        if identity.fingerprint != phase["model_fingerprint"]:
            raise IdentityError(f"capture_{role} receipt fingerprint is inconsistent")
        identities.append(identity)
    source, target = identities
    validate_transfer_pair(source, target)
    if source.dtype != target.dtype:
        raise IdentityError(
            f"source and target were captured at different dtypes: {source.dtype} vs {target.dtype}"
        )
    return source, target


# --------------------------------------------------------------------------
# fit
# --------------------------------------------------------------------------


def train_pairs(run: RunDir, config: dict[str, Any], source: ModelIdentity,
                target: ModelIdentity) -> Iterator[tuple[int, LoadedShard, LoadedShard]]:
    documents, tokens = load_prepared(run)
    splits = documents_by_split(documents)
    fingerprint = run.dataset_fingerprint()
    for document in splits["train"]:
        token_ids = tokens[document.index]
        capture_ids, stride, positions = capture_plan("train", token_ids, config)
        expected = capture_identity(
            "source", "train", document.index, capture_ids, positions, stride,
            fingerprint, source.fingerprint,
        )
        source_shard = load_shard(run, "source", "train", document.index, expected)
        expected["role"] = "target"
        expected["model_fingerprint"] = target.fingerprint
        target_shard = load_shard(run, "target", "train", document.index, expected)
        if source_shard.input_ids.tolist() != target_shard.input_ids.tolist():
            raise IdentityError(
                f"source/target train shards disagree on tokens for doc {document.index}"
            )
        if source_shard.position_ids.tolist() != target_shard.position_ids.tolist():
            raise IdentityError(f"train shard {document.index} positions disagree")
        yield document.index, source_shard, target_shard


def select_source_layers(run: RunDir, config: dict[str, Any], upstream: SimpleNamespace,
                         source: ModelIdentity,
                         target: ModelIdentity) -> tuple[list[list[int]], list[list[float]]]:
    RidgeAccumulator = upstream.RidgeAccumulator
    selected: list[list[int]] = []
    scores: list[list[float]] = []
    for target_layer in range(target.num_layers):
        accumulators = {
            (source_layer, head, kind): RidgeAccumulator(
                source.head_dim, target.head_dim, dtype=torch.float64, device="cpu"
            )
            for source_layer in range(source.num_layers)
            for head in range(target.num_kv_heads)
            for kind in ("key", "value")
        }
        observations = 0
        for _, source_shard, target_shard in train_pairs(run, config, source, target):
            observations += 1
            for source_layer in range(source.num_layers):
                for head in range(target.num_kv_heads):
                    for kind in ("key", "value"):
                        source_tensor = (source_shard.keys if kind == "key"
                                         else source_shard.values)[source_layer]
                        target_tensor = (target_shard.keys if kind == "key"
                                         else target_shard.values)[target_layer]
                        accumulators[(source_layer, head, kind)].update(
                            upstream.features.flatten_head_tokens(source_tensor.unsqueeze(0), head),
                            upstream.features.flatten_head_tokens(target_tensor.unsqueeze(0), head),
                        )
        if observations == 0:
            raise PhaseStateError("no train shards were available for layer selection")
        layer_scores = []
        for source_layer in range(source.num_layers):
            head_scores = [
                accumulators[(source_layer, head, kind)].solve(config["selection_alpha"]).r2
                for head in range(target.num_kv_heads)
                for kind in ("key", "value")
            ]
            layer_scores.append(sum(head_scores) / len(head_scores))
        ranked = sorted(range(source.num_layers), key=layer_scores.__getitem__, reverse=True)
        selected.append(ranked[: min(int(config["top_k"]), source.num_layers)])
        scores.append(layer_scores)
        log(f"target layer {target_layer}: selected {selected[-1]} "
            f"(scores {[round(value, 4) for value in layer_scores]})")
    return selected, scores


def fit_mapper(run: RunDir, config: dict[str, Any], upstream: SimpleNamespace,
               source: ModelIdentity, target: ModelIdentity) -> dict[str, Any]:
    RidgeAccumulator = upstream.RidgeAccumulator
    selected, selection_scores = select_source_layers(run, config, upstream, source, target)

    output_count = target.num_kv_heads * target.head_dim
    feature_count = min(int(config["top_k"]), source.num_layers) * source.num_kv_heads * source.head_dim
    # One accumulator per kind (K and V): XTX is F x F, XTY is F x out and the
    # centered YTY is a single scalar, not another out x out block. This is the
    # self-reported statistics footprint of one target layer, not process RSS.
    statistics_bytes_per_kind = (feature_count * feature_count
                                 + feature_count * output_count
                                 + feature_count + output_count + 1) * 8
    statistics_bytes = 2 * statistics_bytes_per_kind
    budget = int(config["fit"]["max_statistics_bytes"])
    if statistics_bytes > budget:
        raise RunnerError(
            f"top_k={config['top_k']} needs ~{statistics_bytes} bytes of float64 accumulator "
            f"statistics per target layer (K and V each), above the configured budget of {budget}"
        )

    layer_entries: list[dict[str, Any]] = []
    for target_layer in range(target.num_layers):
        source_layers = selected[target_layer]
        features = len(source_layers) * source.num_kv_heads * source.head_dim
        key_accumulator = RidgeAccumulator(features, output_count, dtype=torch.float64, device="cpu")
        value_accumulator = RidgeAccumulator(features, output_count, dtype=torch.float64, device="cpu")
        observations = 0
        # K and V each keep their own XTX/XTY. Within one kind, a single centered
        # XTX predicts every target KV head at once, which is algebraically
        # identical to independent per-head ridge with the same lambda.
        for _, source_shard, target_shard in train_pairs(run, config, source, target):
            observations += 1
            source_keys = source_shard.cache(upstream).keys
            source_values = source_shard.cache(upstream).values
            target_keys = target_shard.cache(upstream).keys
            target_values = target_shard.cache(upstream).values
            key_accumulator.update(
                upstream.features.selected_layer_features(source_keys, source_layers),
                upstream.features.flatten_tokens(target_keys[target_layer]),
            )
            value_accumulator.update(
                upstream.features.selected_layer_features(source_values, source_layers),
                upstream.features.flatten_tokens(target_values[target_layer]),
            )
        key_solution = key_accumulator.solve(config["ridge_alpha"])
        value_solution = value_accumulator.solve(config["ridge_alpha"])

        def reshape(weight: torch.Tensor) -> torch.Tensor:
            return (
                weight.reshape(features, target.num_kv_heads, target.head_dim)
                .permute(1, 0, 2)
                .float()
                .contiguous()
            )

        # Write this target layer's artifact immediately and release its
        # statistics, so no pass ever holds all layers at once.
        layer_entries.append(write_mapper_layer(run, target_layer, {
            "layer": target_layer,
            "selected_layers": list(source_layers),
            "selection_scores": selection_scores[target_layer],
            "key_weight": reshape(key_solution.weight),
            "value_weight": reshape(value_solution.weight),
            "key_bias": key_solution.bias.reshape(
                target.num_kv_heads, target.head_dim
            ).float().contiguous(),
            "value_bias": value_solution.bias.reshape(
                target.num_kv_heads, target.head_dim
            ).float().contiguous(),
            "key_r2": key_solution.r2,
            "value_r2": value_solution.r2,
            "observations": key_solution.observations,
            "train_documents": observations,
        }))
        log(f"fitted target layer {target_layer}: key R2={key_solution.r2:.4f} "
            f"value R2={value_solution.r2:.4f} (artifact written)")
        del key_accumulator, value_accumulator, key_solution, value_solution
    return finalize_mapper(
        run, config, upstream, source, target, layer_entries,
        {
            "statistics_bytes_per_target_layer": statistics_bytes,
            "statistics_bytes_scope": (
                "float64 accumulator tensors for K and V of one target layer "
                "(2 x [F*F + F*out + F + out + 1], including means); this is not process RSS"
            ),
        },
    )


def write_mapper_layer(run: RunDir, layer: int, spec: dict[str, Any]) -> dict[str, Any]:
    """Write one target layer's mapper shard and return its index entry."""
    from safetensors.torch import save_file

    mapper_root = run.path("mapper")
    mapper_root.mkdir(parents=True, exist_ok=True)
    path = mapper_root / f"layer_{layer:05d}.safetensors"
    temporary = path.with_name("." + path.name + ".tmp")
    save_file(
        {
            "key_weight": spec["key_weight"].float().contiguous(),
            "value_weight": spec["value_weight"].float().contiguous(),
            "key_bias": spec["key_bias"].float().contiguous(),
            "value_bias": spec["value_bias"].float().contiguous(),
        },
        str(temporary),
    )
    os.replace(temporary, path)
    return {
        "layer": int(layer),
        "file": str(path.relative_to(run.root)),
        "sha256": sha256_file(path),
        "selected_layers": list(spec["selected_layers"]),
        "selection_scores": [float(value) for value in spec["selection_scores"]],
        "key_r2": float(spec["key_r2"]),
        "value_r2": float(spec["value_r2"]),
        "observations": int(spec.get("observations", 0)),
        "train_documents": int(spec.get("train_documents", 0)),
    }


def finalize_mapper(run: RunDir, config: dict[str, Any], upstream: SimpleNamespace,
                    source: ModelIdentity, target: ModelIdentity,
                    layers: Sequence[dict[str, Any]], notes: dict[str, Any]) -> dict[str, Any]:
    """Write the mapper index over already-written per-layer artifacts."""
    mapper_root = run.path("mapper")
    mapper_root.mkdir(parents=True, exist_ok=True)
    fit_config = upstream.FitConfig(
        top_k=int(config["top_k"]),
        ridge_alpha=float(config["ridge_alpha"]),
        content_space=bool(config["fit"]["content_space"]),
        selection_alpha=float(config["selection_alpha"]),
        accumulation_dtype=str(config["fit"]["accumulation_dtype"]),
        accumulation_device="cpu",
        require_matched_kv=True,
        target_layer_block_size=1,
        selection_target_layer_block_size=1,
        token_stride=int(config["stride"]),
    )
    index = {
        "status": "complete",
        "schema_version": SCHEMA_VERSION,
        "created_utc": utc_now(),
        "manifest_fingerprint": run.dataset_fingerprint(),
        "config_sha256": canonical_digest(config),
        "source_signature": source.upstream_signature(upstream).to_dict(),
        "target_signature": target.upstream_signature(upstream).to_dict(),
        "source_fingerprint": source.fingerprint,
        "target_fingerprint": target.fingerprint,
        "fit_config": fit_config.to_dict(),
        "top_k": int(config["top_k"]),
        "ridge_alpha": float(config["ridge_alpha"]),
        "selection_alpha": float(config["selection_alpha"]),
        "layers": layers,
        "notes": {
            "selection": "head-averaged single-layer ridge R2 per (target layer, source layer)",
            "ridge": "centered RidgeAccumulator statistics, lambda applied to the centered system",
            "shared_xtx": (
                "K and V each keep their own centered XTX/XTY; within one kind a single XTX "
                "predicts every target KV head at once, which is algebraically identical to "
                "independent per-head ridge with the same lambda"
            ),
            **notes,
        },
    }
    write_json_atomic(mapper_root / "index.json", index)
    return index


def write_mapper(run: RunDir, config: dict[str, Any], upstream: SimpleNamespace,
                 source: ModelIdentity, target: ModelIdentity,
                 layer_specs: Sequence[dict[str, Any]], notes: dict[str, Any]) -> dict[str, Any]:
    """Write every supplied layer spec, then the index (thin convenience wrapper)."""
    layers = [write_mapper_layer(run, int(spec["layer"]), spec) for spec in layer_specs]
    return finalize_mapper(run, config, upstream, source, target, layers, notes)


def record_fit(run: RunDir, index: dict[str, Any]) -> None:
    run.set_phase(
        "fit",
        {
            "status": "complete",
            "receipt": "mapper/index.json",
            "index_sha256": sha256_file(run.path("mapper", "index.json")),
            "manifest_fingerprint": index["manifest_fingerprint"],
            "layers": len(index["layers"]),
            "selected_layers": [entry["selected_layers"] for entry in index["layers"]],
            "key_r2": [entry["key_r2"] for entry in index["layers"]],
            "value_r2": [entry["value_r2"] for entry in index["layers"]],
        },
    )


def phase_fit(run: RunDir, config: dict[str, Any], upstream: SimpleNamespace) -> dict[str, Any]:
    configure_threads(config)
    run.require_phase("prepare")
    source, target = capture_role_identities(run)
    index = fit_mapper(run, config, upstream, source, target)
    record_fit(run, index)
    return index


def load_mapper(run: RunDir, config: dict[str, Any], upstream: SimpleNamespace) -> Any:
    from safetensors.torch import load_file

    phase = run.require_phase("fit")
    index = read_json(run.path("mapper", "index.json"))
    if index.get("status") != "complete":
        raise PhaseStateError("mapper index is not complete")
    if sha256_file(run.path("mapper", "index.json")) != phase["index_sha256"]:
        raise IdentityError("mapper index changed after the fit phase completed")
    if index["manifest_fingerprint"] != run.dataset_fingerprint():
        raise IdentityError("mapper was fitted against a different dataset/manifest fingerprint")
    if index["config_sha256"] != canonical_digest(config):
        raise IdentityError("mapper was fitted with a different configuration")
    layers = index["layers"]
    if [entry["layer"] for entry in layers] != list(range(len(layers))):
        raise IdentityError("mapper layers are incomplete or out of order")
    key_weights, value_weights, key_biases, value_biases = [], [], [], []
    for entry in layers:
        path = run.root / entry["file"]
        if sha256_file(path) != entry["sha256"]:
            raise IdentityError(f"mapper shard {path} does not match its recorded checksum")
        tensors = load_file(str(path), device="cpu")
        key_weights.append(tensors["key_weight"])
        value_weights.append(tensors["value_weight"])
        key_biases.append(tensors["key_bias"])
        value_biases.append(tensors["value_bias"])
    return upstream.CrossModelKVMapper(
        source_signature=upstream.ModelSignature.from_dict(index["source_signature"]),
        target_signature=upstream.ModelSignature.from_dict(index["target_signature"]),
        config=upstream.FitConfig.from_dict(index["fit_config"]),
        selected_layers=[entry["selected_layers"] for entry in layers],
        key_weights=key_weights,
        value_weights=value_weights,
        key_biases=key_biases,
        value_biases=value_biases,
        selection_scores=[entry["selection_scores"] for entry in layers],
        fit_key_r2=[entry["key_r2"] for entry in layers],
        fit_value_r2=[entry["value_r2"] for entry in layers],
    )


# --------------------------------------------------------------------------
# evaluate
# --------------------------------------------------------------------------


def kv_reconstruction(candidate: Sequence[torch.Tensor],
                      reference: Sequence[torch.Tensor]) -> dict[str, float]:
    """Report pooled R^2 and head-averaged R^2 separately.

    Kernels are ``[batch, kv_heads, tokens, dim]``; the head axis is 1 and the
    head-average is taken over every (layer, KV head) pair.
    """
    squared_error = 0.0
    pooled_total = 0.0
    pooled_sum = 0.0
    elements = 0
    reference_squares = 0.0
    head_scores: list[float] = []
    for candidate_layer, reference_layer in zip(candidate, reference, strict=True):
        if candidate_layer.shape != reference_layer.shape:
            raise RunnerError(
                f"candidate/reference shape mismatch: {tuple(candidate_layer.shape)} vs "
                f"{tuple(reference_layer.shape)}"
            )
        reference64 = reference_layer.double()
        difference = candidate_layer.double() - reference64
        squared_error += float((difference * difference).sum())
        reference_squares += float((reference64 * reference64).sum())
        pooled_sum += float(reference64.sum())
        elements += reference64.numel()
        for head in range(reference64.shape[1]):
            head_reference = reference64[0, head]
            head_difference = difference[0, head]
            head_total = float(((head_reference - head_reference.mean()) ** 2).sum())
            head_error = float((head_difference * head_difference).sum())
            if head_total > 0:
                head_scores.append(1.0 - head_error / head_total)
            else:
                # Same zero-variance convention as the pinned RidgeAccumulator,
                # so a constant head still contributes one equal-weight term.
                head_scores.append(1.0 if head_error <= torch.finfo(torch.float64).eps else 0.0)
    pooled_mean = pooled_sum / max(elements, 1)
    for reference_layer in reference:
        reference64 = reference_layer.double()
        pooled_total += float(((reference64 - pooled_mean) ** 2).sum())
    return {
        "mse": squared_error / max(elements, 1),
        "r2_overall_pooled": 1.0 - squared_error / pooled_total if pooled_total > 0
        else float("nan"),
        "r2_head_average": sum(head_scores) / len(head_scores) if head_scores else float("nan"),
        "elements": elements,
        "reference_squares": reference_squares,
    }


def first_token_report(first_logits: torch.Tensor, labels: torch.Tensor) -> dict[str, Any]:
    """Everything about the first continuation step, from explicit indices."""
    probabilities = torch.log_softmax(first_logits.float(), dim=-1)
    gold = int(labels[0])
    return {
        "gold_id": gold,
        "p_gold": float(probabilities[0, 0, gold].exp()),
        "log_p_gold": float(probabilities[0, 0, gold]),
        "argmax": int(first_logits[0, 0].argmax()),
        "nll": float(-probabilities[0, 0, gold]),
    }


def log_softmax_nll(logits: torch.Tensor, labels: torch.Tensor) -> float:
    """Mean token NLL with an explicit alignment, never a hidden shift.

    ``logits[:, k, :]`` predicts ``labels[k]``: the caller has already sliced
    both sides so that logit index ``k`` sits at position ``first_label - 1 + k``
    and label index ``k`` sits at ``first_label + k``.
    """
    log_probabilities = torch.log_softmax(logits.float(), dim=-1)
    rows = torch.arange(labels.numel())
    return float(-log_probabilities[0, rows, labels].mean())


def continuation_metrics(logits: torch.Tensor, native_logits: torch.Tensor,
                         labels: torch.Tensor, upstream: SimpleNamespace,
                         *, first_label_index: int) -> dict[str, Any]:
    count = labels.numel()
    candidate = logits[:, :count, :].float()
    reference = native_logits[:, :count, :].float()
    first = first_token_report(candidate[:, :1, :], labels)
    reference_first = first_token_report(reference[:, :1, :], labels)
    return {
        "logit_positions": [first_label_index - 1, first_label_index + count - 2],
        "label_indices": [first_label_index, first_label_index + count - 1],
        "nll": log_softmax_nll(candidate, labels),
        "ppl": math.exp(log_softmax_nll(candidate, labels)),
        "kl_native_to_candidate": upstream.metrics.logit_kl_divergence(candidate, reference),
        "top1_agreement": float((candidate.argmax(-1) == reference.argmax(-1)).float().mean()),
        "first_token": first,
        "first_token_nll": first["nll"],
        "first_token_gold_id": first["gold_id"],
        "first_token_p_gold": first["p_gold"],
        "first_token_argmax": first["argmax"],
        "first_token_reference_argmax": reference_first["argmax"],
        "first_token_kl": upstream.metrics.logit_kl_divergence(
            candidate[:, :1, :], reference[:, :1, :]
        ),
        "first_token_top1_agreement": float(
            (candidate[:, 0].argmax(-1) == reference[:, 0].argmax(-1)).float().mean()
        ),
    }


def query_hook(model: Any, upstream: SimpleNamespace) -> tuple[list[Any], list[Any]]:
    """Capture pre-RoPE per-head queries for attention-output cosine."""
    query_heads = int(model.config.num_attention_heads)
    head_dim = int(getattr(model.config, "head_dim", None)
                   or model.config.hidden_size // query_heads)
    raw: list[Any] = [None] * int(model.config.num_hidden_layers)
    handles = []
    for layer_index, layer in enumerate(upstream.huggingface._decoder_layers(model)):
        attention = layer.self_attn
        module = getattr(attention, "q_norm", None) or attention.q_proj

        def capture(_module: Any, _inputs: Any, output: Any, index: int = layer_index) -> None:
            raw[index] = upstream.huggingface._canonical_query(
                output, query_heads=query_heads, head_dim=head_dim
            )

        handles.append(module.register_forward_hook(capture))
    return raw, handles


def run_branch(model: Any, prefix_cache: Any, fresh_ids: torch.Tensor, positions: torch.Tensor,
               seq_len: int, upstream: SimpleNamespace, *, with_queries: bool) -> dict[str, Any]:
    # Content K is stored in float32 so fitting and mapping never add a second
    # quantization; the model itself still runs at its own dtype, so the prefix
    # is cast here, at the model boundary only.
    model_dtype = next(model.parameters()).dtype
    if (prefix_cache.keys[0].dtype != model_dtype
            or prefix_cache.values[0].dtype != model_dtype):
        prefix_cache = prefix_cache.to(prefix_cache.keys[0].device, dtype=model_dtype)
    past = upstream.huggingface.to_dynamic_cache(clone_cache(prefix_cache, upstream), model)
    raw, handles = query_hook(model, upstream) if with_queries else ([], [])
    kwargs = {
        "input_ids": fresh_ids.unsqueeze(0),
        "attention_mask": torch.ones((1, seq_len), dtype=torch.long),
        "position_ids": positions.unsqueeze(0),
        "past_key_values": past,
        "use_cache": True,
        "return_dict": True,
    }
    try:
        outputs = model(cache_position=positions, **kwargs)
    except TypeError:  # pragma: no cover - forward signature variants
        outputs = model(**kwargs)
    finally:
        for handle in handles:
            handle.remove()
    result: dict[str, Any] = {"logits": outputs.logits, "full_cache": outputs.past_key_values}
    if with_queries:
        factors = upstream.huggingface.capture_rotary_factors(model, positions.unsqueeze(0))
        result["queries"] = tuple(
            factors.apply(query) for query in raw if query is not None
        )
    return result


def cache_from_dynamic(cache: Any, upstream: SimpleNamespace) -> Any:
    layers = upstream.huggingface._legacy_layers(cache)
    return upstream.cache.KVCache([layer[0] for layer in layers], [layer[1] for layer in layers])


def candidate_prefixes(source_shard: LoadedShard, mapper: Any, target_rope: Any,
                       upstream: SimpleNamespace,
                       *, order: Sequence[str] | None = None,
                       content: Any | None = None) -> dict[str, Any]:
    """Build candidate prefixes from the source capture and the frozen mapper.

    Neither the held-out target capture nor any target reference logits are read
    here, so a candidate can be produced while the target reference is still
    unreachable. A shape disagreement with the mapper fails hard: there is no
    silent fallback to another branch.

    Each returned prefix is rotated exactly once, with the target factors, so
    what the target model actually consumes is the mapper's own prediction.
    """
    if content is None:
        content = mapped_content_prediction(source_shard, mapper, upstream)
    prefixes: dict[str, Any] = {"mapped": content.apply_rotary(target_rope)}
    target = mapper.target_signature
    if (
        source_shard.head_dim == target.head_dim
        and source_shard.num_kv_heads == target.num_kv_heads
        and source_shard.num_layers == target.num_layers
    ):
        source_content = source_shard.cache(upstream)
        prefixes["direct_source"] = source_content.apply_rotary(target_rope)
    if order is not None:
        missing = [name for name in order if name not in prefixes]
        if missing:
            raise RunnerError(f"requested candidate branches are unavailable: {missing}")
        prefixes = {name: prefixes[name] for name in order}
    return prefixes


def identity_rotary_factors(upstream: SimpleNamespace, tokens: int, head_dim: int) -> Any:
    """An exact identity rotation in float32.

    The pinned mapper requires target rotary factors whenever it maps into
    content space, so passing an identity reads out the projection itself with
    no rotation applied at all.
    """
    return upstream.cache.RotaryFactors(
        torch.ones((1, tokens, head_dim), dtype=torch.float32),
        torch.zeros((1, tokens, head_dim), dtype=torch.float32),
        interleaved=False,
    )


def mapped_content_prediction(source_shard: LoadedShard, mapper: Any,
                              upstream: SimpleNamespace) -> Any:
    """The mapper's own unrotated target-geometry prediction for one source shard."""
    expected_shape = (
        mapper.source_signature.num_layers,
        mapper.source_signature.num_kv_heads,
        mapper.source_signature.head_dim,
    )
    actual_shape = (source_shard.num_layers, source_shard.num_kv_heads, source_shard.head_dim)
    if actual_shape != expected_shape:
        raise RunnerError(
            f"source capture shape {actual_shape} does not match the mapper source "
            f"signature {expected_shape}"
        )
    source_content = source_shard.cache(upstream)
    identity = identity_rotary_factors(
        upstream, int(source_content.shape[3]), mapper.target_signature.head_dim
    )
    try:
        projected = mapper.map(source_content, target_rotary=identity)
    except Exception as error:
        raise RunnerError(f"the frozen mapper could not map the source cache: {error}") from error
    # Drop the identity rotation bookkeeping: this is content-space output.
    return upstream.cache.KVCache(
        [tensor for tensor in projected.keys],
        [tensor for tensor in projected.values],
        None,
        keys_are_content=True,
    )


def run_candidate_branches(target_model: Any, prefixes: dict[str, Any], fresh_ids: torch.Tensor,
                           positions: torch.Tensor, seq_len: int, upstream: SimpleNamespace,
                           *, order: Sequence[str] | None = None,
                           query_branch: str | None = None) -> dict[str, Any]:
    """Teacher-force the held-out continuation per branch on an independent clone."""
    names = list(order) if order is not None else list(prefixes)
    outputs: dict[str, Any] = {}
    for name in names:
        if name not in prefixes:
            raise RunnerError(f"unknown candidate branch {name!r}")
        started = time.perf_counter()
        outputs[name] = run_branch(
            target_model, prefixes[name], fresh_ids, positions, seq_len, upstream,
            with_queries=(name == query_branch),
        )
        outputs[name]["elapsed_ms"] = (time.perf_counter() - started) * 1000.0
    return outputs


def first_logit_future_invariance(target_model: Any, prefix_cache: Any, fresh_ids: torch.Tensor,
                                  positions: torch.Tensor, full_logits: torch.Tensor,
                                  upstream: SimpleNamespace) -> float:
    """The logit at the held-back position must not depend on later tokens.

    Only ``fresh_ids[1:]`` is perturbed, by a deterministic rotation (or an
    offset when the tail is a single token). The first fresh token, the token
    count and every tensor shape are unchanged, so this is a same-shape future
    intervention rather than a truncation control.
    """
    if int(fresh_ids.numel()) < 2:
        return 0.0
    tail = fresh_ids[1:].clone()
    perturbed_tail = torch.roll(tail, shifts=1, dims=0)
    if torch.equal(perturbed_tail, tail):
        vocab = int(getattr(target_model.config, "vocab_size", 0) or 0)
        perturbed_tail = (tail + 1) % vocab if vocab > 0 else tail + 1
    perturbed = torch.cat([fresh_ids[:1], perturbed_tail])
    prefix_tokens = int(prefix_cache.shape[3])
    perturbed_output = run_branch(
        target_model, prefix_cache, perturbed, positions,
        prefix_tokens + int(perturbed.numel()), upstream, with_queries=False,
    )
    return float((perturbed_output["logits"][:, 0, :] - full_logits[:, 0, :]).abs().max())


def phase_evaluate(run: RunDir, split: str, config: dict[str, Any],
                   upstream: SimpleNamespace) -> dict[str, Any]:
    configure_threads(config)
    prepare = run.require_phase("prepare")
    fit = run.require_phase("fit")
    if fit["manifest_fingerprint"] != prepare["dataset_fingerprint"]:
        raise IdentityError("fit and prepare disagree on the dataset fingerprint")
    dataset_fingerprint = prepare["dataset_fingerprint"]
    source_identity, target_identity = capture_role_identities(run)
    mapper = load_mapper(run, config, upstream)
    documents, tokens = load_prepared(run)
    splits = documents_by_split(documents)
    target_model, low_cpu_memory = load_role_model(config, "target")

    seq_len = int(config["seq_len"])
    prefix_len = int(config["prefix_len"])
    eval_prefix_len = prefix_len - 1
    continuation = seq_len - prefix_len

    results: list[dict[str, Any]] = []
    cosine_records: dict[str, list[dict[str, Any]]] = {}
    cosine_errors: dict[str, str] = {}
    for document in splits[split]:
        token_ids = tokens[document.index]
        capture_ids, stride, positions = capture_plan(split, token_ids, config)
        source_expected = capture_identity(
            "source", split, document.index, capture_ids, positions, stride,
            dataset_fingerprint, source_identity.fingerprint,
        )
        target_expected = capture_identity(
            "target", split, document.index, capture_ids, positions, stride,
            dataset_fingerprint, target_identity.fingerprint,
        )
        prefix_positions = torch.arange(eval_prefix_len)
        target_rope = upstream.huggingface.capture_rotary_factors(
            target_model, prefix_positions.unsqueeze(0)
        )
        # Index contract: past = x[:191], fresh = x[191:255], labels = x[192:256].
        # The fresh window holds exactly `continuation` tokens, so its logits are
        # exactly the logits that predict those labels: logit k at position
        # 191 + k predicts label 192 + k, with no extra or missing step.
        fresh_ids = token_ids[eval_prefix_len : seq_len - 1]
        labels = token_ids[prefix_len:seq_len]
        inside_positions = torch.arange(eval_prefix_len, seq_len - 1)
        attention_length = seq_len - 1

        # 1. candidates: source capture + frozen mapper + token ids only. The
        #    held-out target capture is not read until the candidates exist.
        source_shard = load_shard(run, "source", split, document.index, source_expected)
        started = time.perf_counter()
        # The mapper's own unrotated prediction: the reconstruction metric and
        # the branch both derive from this single projection, and the branch
        # applies the target RoPE exactly once.
        mapped_content = mapped_content_prediction(source_shard, mapper, upstream)
        prefixes = candidate_prefixes(source_shard, mapper, target_rope, upstream,
                                      content=mapped_content)
        map_ms = (time.perf_counter() - started) * 1000.0
        for name, prefix in prefixes.items():
            if int(prefix.shape[3]) != eval_prefix_len:
                raise RunnerError(
                    f"candidate {name} prefix has {prefix.shape[3]} tokens, expected "
                    f"{eval_prefix_len}"
                )
        with torch.inference_mode():
            outputs = run_candidate_branches(
                target_model, prefixes, fresh_ids, inside_positions, attention_length, upstream
            )
            candidate_invariance = {
                name: first_logit_future_invariance(
                    target_model, prefixes[name], fresh_ids, inside_positions,
                    output["logits"], upstream,
                )
                for name, output in outputs.items()
            }

            # 2. target reference: read only now, used for comparison only.
            target_shard = load_shard(run, "target", split, document.index, target_expected)
            for shard in (source_shard, target_shard):
                if shard.input_ids.tolist() != capture_ids.tolist():
                    raise IdentityError(
                        f"shard {shard.role}/{split}/{document.index} tokens do not bind "
                        "to the dataset"
                    )
            native_prefix = target_shard.native_cache(upstream)
            native_content = target_shard.cache(upstream)
            native_started = time.perf_counter()
            native_output = run_branch(
                target_model, native_prefix, fresh_ids, inside_positions, attention_length,
                upstream,
                with_queries=True,
            )
            native_output["elapsed_ms"] = (time.perf_counter() - native_started) * 1000.0
            native_invariance = first_logit_future_invariance(
                target_model, native_prefix, fresh_ids, inside_positions,
                native_output["logits"], upstream,
            )
            full_logits = target_model(
                input_ids=token_ids[: seq_len - 1].unsqueeze(0),
                attention_mask=torch.ones((1, seq_len - 1), dtype=torch.long),
                position_ids=torch.arange(seq_len - 1).unsqueeze(0),
                use_cache=False,
                return_dict=True,
            ).logits

        outputs = {"native_target": native_output, **outputs}
        native_logits = outputs["native_target"]["logits"]
        if int(native_logits.shape[1]) != continuation:
            raise RunnerError(
                f"native branch produced {native_logits.shape[1]} logits, expected "
                f"{continuation} (exactly one per held-out continuation label)"
            )
        full_reference = full_logits[:, eval_prefix_len : seq_len - 1, :]
        full_nll = log_softmax_nll(full_reference, labels)
        native_metrics = continuation_metrics(
            native_logits, native_logits, labels, upstream, first_label_index=prefix_len
        )
        native_first = first_token_report(native_logits[:, :1, :], labels)
        full_first = first_token_report(full_reference[:, :1, :], labels)
        entry: dict[str, Any] = {
            "doc_index": document.index,
            "doc_id": document.doc_id,
            "eval_prefix_len": eval_prefix_len,
            "continuation_tokens": continuation,
            "first_continuation_label_index": prefix_len,
            "map_ms": map_ms,
            "branch_ms": {name: output["elapsed_ms"] for name, output in outputs.items()},
            "native_prefix_kind": "raw-post-rope",
            "first_logit_future_invariance": {
                "native_target": native_invariance,
                **candidate_invariance,
            },
            "full_reference_nll": full_nll,
            "full_reference_first_token": full_first,
            "native_vs_full_reference": {
                "max_abs_logit_delta": float(
                    (native_logits - full_reference).abs().max()
                ),
                "nll_delta": native_metrics["nll"] - full_nll,
                "first_logit_max_abs_delta": float(
                    (native_logits[:, 0, :] - full_reference[:, 0, :]).abs().max()
                ),
                "first_gold_id": native_first["gold_id"],
                "first_p_gold": native_first["p_gold"],
                "first_argmax": native_first["argmax"],
                "full_reference_first_argmax": full_first["argmax"],
                "first_argmax_match": native_first["argmax"] == full_first["argmax"],
                "first_nll_delta": native_first["nll"] - full_first["nll"],
            },
            "direct_source": (
                {"status": "measured"}
                if "direct_source" in prefixes
                else {"status": "skipped", "reason": direct_source_skip_reason(
                    source_identity, target_identity)}
            ),
            "native_target": native_metrics,
            "branches": {
                name: continuation_metrics(
                    output["logits"], native_logits, labels, upstream,
                    first_label_index=prefix_len,
                )
                for name, output in outputs.items()
            },
            "reconstruction": {
                "mapped": {
                    "key": kv_reconstruction(mapped_content.keys, native_content.keys),
                    "value": kv_reconstruction(mapped_content.values, native_content.values),
                },
                "native_content_roundtrip": {
                    "key": kv_reconstruction(
                        target_shard.content_rotated(upstream, target_rope).keys,
                        native_prefix.keys,
                    ),
                    "note": (
                        "diagnostic only: RoPE-stripped float32 content re-encoded with the "
                        "target factors against the unmodified raw post-RoPE K. The inverse of "
                        "a numerically rounded rotation is not an exact recovery, so this is "
                        "not an error budget and the native branch never uses it."
                    ),
                },
            },
        }
        if "direct_source" in prefixes:
            source_content = source_shard.cache(upstream)
            entry["reconstruction"]["direct_source"] = {
                "key": kv_reconstruction(source_content.keys, native_content.keys),
                "value": kv_reconstruction(source_content.values, native_content.values),
            }
        results.append(entry)

        queries = outputs.get("native_target", {}).get("queries")
        if queries:
            reference_full = cache_from_dynamic(outputs["native_target"]["full_cache"], upstream)
            for name in [item for item in ("mapped", "direct_source") if item in outputs]:
                try:
                    candidate_full = cache_from_dynamic(outputs[name]["full_cache"], upstream)
                    report = upstream.metrics.attention_output_cosine(
                        queries, candidate_full, reference_full, causal=True
                    )
                    cosine_records.setdefault(name, []).append(
                        {"mean": report.mean, "minimum": report.minimum,
                         "per_layer": list(report.per_layer)}
                    )
                except Exception as error:  # pragma: no cover - geometry guard
                    cosine_errors[name] = f"{type(error).__name__}: {error}"

    def mean(values: Sequence[float]) -> float:
        return sum(values) / len(values) if values else float("nan")

    branch_names = ["native_target", "mapped"]
    if results and "direct_source" in results[0]["branches"]:
        branch_names.append("direct_source")
    aggregate: dict[str, Any] = {"documents": len(results)}
    for name in branch_names:
        pairs = [(entry["branches"][name], entry["native_target"]) for entry in results
                 if name in entry["branches"]]
        entries = [item for item, _ in pairs]
        if not entries:
            continue
        aggregate[name] = {
            "nll_mean": mean([item["nll"] for item in entries]),
            "ppl_ratio_mean_of_doc_ratios": mean(
                [math.exp(item["nll"] - native["nll"]) for item, native in pairs]
            ),
            "kl_native_to_candidate_mean": mean(
                [item["kl_native_to_candidate"] for item in entries]
            ),
            "top1_agreement_mean": mean([item["top1_agreement"] for item in entries]),
            "first_token_nll_mean": mean([item["first_token_nll"] for item in entries]),
            "first_token_kl_mean": mean([item["first_token_kl"] for item in entries]),
            "first_token_top1_agreement_mean": mean(
                [item["first_token_top1_agreement"] for item in entries]
            ),
            "first_token_p_gold_mean": mean(
                [item["first_token_p_gold"] for item in entries]
            ),
            "first_token_argmax_matches_native_rate": mean(
                [float(item["first_token_argmax"] == item["first_token_reference_argmax"])
                 for item in entries]
            ),
        }
    aggregate["native_target_reference_nll_mean"] = mean(
        [entry["native_target"]["nll"] for entry in results]
    )
    aggregate["full_reference_nll_mean"] = mean(
        [entry["full_reference_nll"] for entry in results]
    )
    aggregate["full_reference_first_token"] = {
        "gold_id": results[0]["full_reference_first_token"]["gold_id"] if results else None,
        "p_gold_mean": mean(
            [entry["full_reference_first_token"]["p_gold"] for entry in results]
        ),
        "first_token_nll_mean": mean(
            [entry["full_reference_first_token"]["nll"] for entry in results]
        ),
    }
    aggregate["native_vs_full_reference"] = {
        "max_abs_logit_delta": max(
            entry["native_vs_full_reference"]["max_abs_logit_delta"] for entry in results
        ),
        "max_abs_nll_delta": max(
            abs(entry["native_vs_full_reference"]["nll_delta"]) for entry in results
        ),
        "max_first_logit_abs_delta": max(
            entry["native_vs_full_reference"]["first_logit_max_abs_delta"] for entry in results
        ),
        "first_argmax_match_all": all(
            entry["native_vs_full_reference"]["first_argmax_match"] for entry in results
        ),
    }
    aggregate["first_logit_future_invariance"] = {
        name: max(entry["first_logit_future_invariance"][name]
                  for entry in results if name in entry["first_logit_future_invariance"])
        for name in ["native_target", *branch_names]
        if any(name in entry["first_logit_future_invariance"] for entry in results)
    }
    aggregate["mean_map_ms"] = mean([entry["map_ms"] for entry in results])
    aggregate["mean_branch_ms"] = {
        name: mean([entry["branch_ms"][name] for entry in results if name in entry["branch_ms"]])
        for name in branch_names
    }
    aggregate["mapped_reconstruction"] = {
        kind: {
            field: mean([entry["reconstruction"]["mapped"][kind][field] for entry in results])
            for field in ("mse", "r2_overall_pooled", "r2_head_average")
        }
        for kind in ("key", "value")
    }
    aggregate["native_content_roundtrip"] = {
        field: mean([entry["reconstruction"]["native_content_roundtrip"]["key"][field]
                     for entry in results])
        for field in ("mse", "r2_overall_pooled", "r2_head_average")
    }
    if "direct_source" in branch_names:
        aggregate["direct_source_sham_reconstruction"] = {
            kind: {
                field: mean([entry["reconstruction"]["direct_source"][kind][field]
                             for entry in results])
                for field in ("mse", "r2_overall_pooled", "r2_head_average")
            }
            for kind in ("key", "value")
        }

    evidence_kind = config["evidence_kind"]
    cosine_state = "not-measured"
    cosine_reason = "source/target head geometry did not match, or the query hook was unavailable"
    if cosine_records.get("mapped") and not cosine_errors:
        cosine_state = "measured"
    elif cosine_errors:
        cosine_reason = "; ".join(f"{name}: {error}" for name, error in cosine_errors.items())
    receipt = {
        "status": "complete",
        "phase": "evaluate",
        "split": split,
        "created_utc": utc_now(),
        "evidence_kind": evidence_kind,
        "manifest_fingerprint": dataset_fingerprint,
        "mapper_index_sha256": sha256_file(run.path("mapper", "index.json")),
        "low_cpu_mem_usage": low_cpu_memory,
        "accelerate_available": accelerate_available(),
        "attention_backend": attention_backend(target_model),
        "eval_prefix_len": eval_prefix_len,
        "continuation_tokens": continuation,
        "first_continuation_label_index": prefix_len,
        "comparison": (
            "identical prefix positions and identical held-out continuation labels; the fresh "
            "input starts at index prefix_len-1 so logits at the first continuation step are "
            "included"
        ),
        "index_alignment": {
            "captured_prefix_positions": [0, eval_prefix_len - 1],
            "logit_positions": [prefix_len - 1, seq_len - 2],
            "label_indices": [prefix_len, seq_len - 1],
            "rule": "logit index k predicts label index first_label_index + k (no hidden shift)",
            "log_softmax": "token NLL comes from an explicit log_softmax plus index gather",
        },
        "native_reference": {
            "prefix": "raw post-RoPE K plus native V, read back unmodified from the target capture",
            "content_key": "RoPE-stripped float32 content K, used for fitting and by the mapper",
            "note": (
                "the stored content K is not claimed to be an exact recovery of the model's "
                "pre-RoPE content: stripping and re-applying RoPE is a real-valued inverse of a "
                "numerically rounded rotation, so it carries quantization error. The native "
                "branch and the native/full comparison therefore use the untouched raw capture."
            ),
        },
        "r2_definitions": {
            "r2_overall_pooled": (
                "1 - sum((candidate-native)^2)/sum((native-mean(native))^2) over every element "
                "of one document's stored prefix (all layers, KV heads, tokens, dims)"
            ),
            "r2_head_average": (
                "mean over every (layer, KV head) of the elementwise R^2 inside that head's "
                "token x dim slice"
            ),
            "native_content_roundtrip": (
                "diagnostic: re-encoded float32 content K against the raw post-RoPE native K; "
                "it measures quantization plus the rounded-inverse residual and is reported, "
                "not gated"
            ),
            "note": (
                "these are reconstruction R^2 values; the paper's layer-selection R^2 is a "
                "single-layer ridge R^2 per (target layer, source layer, head, kind) averaged "
                "over heads, stored under mapper/index.json"
            ),
        },
        "quality_gate": {
            "status": "not-a-gate" if evidence_kind == "random-model-smoke" else "reported-only",
            "reason": (
                "random-model-smoke numbers are a structural check on a randomly initialised "
                "model and must not be read as transfer quality"
                if evidence_kind == "random-model-smoke"
                else "thresholds are set by the protocol owner; the runner only reports metrics"
            ),
        },
        "sham_baseline": {
            "branch": "direct_source",
            "note": (
                "raw source K/V rotated into target positions: an unmapped control. Producing "
                "output is not evidence of transfer quality."
            ),
        },
        "attention_cosine": {
            "status": cosine_state,
            "reason": cosine_reason,
            "queries": "native_target queries applied to both caches",
            "positions": "continuation positions (causal over prefix plus continuation)",
            "per_document": cosine_records,
        },
        "branch_map": {
            "native_target": "independent target capture prefix",
            "mapped": "source prefix through the frozen mapper, target RoPE re-applied",
            "direct_source": "raw source prefix with no mapping (requires matched head geometry)",
        },
        "aggregate": aggregate,
        "documents": results,
    }
    write_json_atomic(run.path("evaluate", split, "receipt.json"), receipt)
    run.set_phase(
        f"evaluate_{split}",
        {
            "status": "complete",
            "receipt": f"evaluate/{split}/receipt.json",
            "evidence_kind": evidence_kind,
            "documents": len(results),
            "aggregate": {
                name: {
                    "nll_mean": aggregate[name]["nll_mean"],
                    "top1_agreement_mean": aggregate[name]["top1_agreement_mean"],
                    "kl_native_to_candidate_mean": aggregate[name]["kl_native_to_candidate_mean"],
                }
                for name in branch_names
            },
        },
    )
    return receipt


# --------------------------------------------------------------------------
# smoke
# --------------------------------------------------------------------------


SMOKE_CONFIG: dict[str, Any] = {
    "evidence_kind": "random-model-smoke",
    "dtype": "float32",
    "seq_len": 32,
    "prefix_len": 24,
    "stride": 2,
    "splits": {"train": 12, "validation": 4, "test": 4},
    "data": {"kind": "synthetic", "num_documents": 24, "vocab_size": 128,
             "min_tokens": 32, "max_tokens": 44},
}


def build_random_pair(root: Path) -> dict[str, Any]:
    """Two tiny Qwen3 models: matched KV heads/head_dim, different hidden width."""
    from transformers import Qwen3Config, Qwen3ForCausalLM

    specs = {
        # Matched KV heads/head_dim/layer count, different hidden width and RoPE theta.
        "source": {"hidden": 128, "heads": 8, "layers": 3, "seed": 11, "theta": 10_000.0},
        "target": {"hidden": 256, "heads": 16, "layers": 3, "seed": 22, "theta": 250_000.0},
    }
    entries: dict[str, Any] = {}
    for role, spec in specs.items():
        directory = root / f"{role}-model"
        torch.manual_seed(spec["seed"])
        config = Qwen3Config(
            vocab_size=128,
            hidden_size=spec["hidden"],
            num_hidden_layers=spec["layers"],
            num_attention_heads=spec["heads"],
            num_key_value_heads=4,
            head_dim=16,
            intermediate_size=256,
            max_position_embeddings=256,
            tie_word_embeddings=True,
            rope_theta=spec["theta"],
        )
        Qwen3ForCausalLM(config).eval().save_pretrained(directory)
        entries[role] = {"model": str(directory), "revision": "local", "origin": "local"}
    return entries


def smoke_config(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    models = build_random_pair(root)
    raw = deep_merge(DEFAULT_CONFIG, deep_merge(SMOKE_CONFIG,
                                               {"source": models["source"],
                                                "target": models["target"]}))
    return resolve_config(raw), models


def run_smoke(upstream: SimpleNamespace, out_dir: Path | None, keep: bool) -> dict[str, Any]:
    temporary = None
    if out_dir is None:
        temporary = tempfile.TemporaryDirectory(prefix="kv-prefill-smoke-")
        root = Path(temporary.name)
    else:
        root = Path(out_dir).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
    try:
        config, _ = smoke_config(root / "models")
        run_dir = root / "run"
        phases: dict[str, Any] = {}
        phases["prepare"] = phase_prepare(config, run_dir, upstream)
        for role in ROLES:  # one model per process, on purpose
            command = [
                sys.executable, str(Path(__file__).resolve()),
                "--upstream", str(upstream.root), "capture", "--run", str(run_dir),
                "--role", role,
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode != 0:
                raise RunnerError(
                    f"smoke capture {role} failed with exit {completed.returncode}:\n"
                    f"{completed.stderr.strip()}"
                )
            phases[f"capture_{role}"] = json.loads(completed.stdout)
        phases["fit"] = phase_fit(RunDir.open(run_dir), config, upstream)
        for split in ("validation", "test"):
            phases[f"evaluate_{split}"] = phase_evaluate(
                RunDir.open(run_dir), split, config, upstream
            )
        validation = phases["evaluate_validation"]
        test = phases["evaluate_test"]
        summary = {
            "status": "complete",
            "evidence_kind": config["evidence_kind"],
            "run_dir": str(run_dir),
            "phases": {name: receipt["status"] for name, receipt in phases.items()},
            "dataset": phases["prepare"]["counts"],
            "selected_layers": [entry["selected_layers"] for entry in phases["fit"]["layers"]],
            "native_vs_full_reference": validation["aggregate"]["native_vs_full_reference"],
            "validation": {
                name: validation["aggregate"][name]
                for name in ("mapped", "direct_source")
                if name in validation["aggregate"]
            },
            "test": {
                name: test["aggregate"][name]
                for name in ("mapped", "direct_source")
                if name in test["aggregate"]
            },
            "quality_gate": validation["quality_gate"],
            "attention_cosine": {
                split: phases[f"evaluate_{split}"]["attention_cosine"]["status"]
                for split in ("validation", "test")
            },
        }
        write_json_atomic(run_dir / "smoke-summary.json", summary)
        return summary
    finally:
        if temporary is not None and not keep:
            temporary.cleanup()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def add_common(parser: argparse.ArgumentParser) -> None:
    # SUPPRESS so a value given before the phase name is not clobbered by the
    # subparser default; the value can be given either side of the phase name.
    parser.add_argument(
        "--upstream",
        default=argparse.SUPPRESS,
        help="path to the pinned kvbridge-streaming checkout (or KVPREFILL_UPSTREAM)",
    )
    parser.add_argument("--upstream-commit", default=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runner.py",
        description="KV prefill transfer runner (prepare / capture / fit / evaluate / smoke)",
    )
    parser.add_argument(
        "--upstream",
        default=os.environ.get("KVPREFILL_UPSTREAM"),
        help="path to the pinned kvbridge-streaming checkout (or KVPREFILL_UPSTREAM)",
    )
    parser.add_argument("--upstream-commit", default=PINNED_UPSTREAM_COMMIT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="tokenize and split the dataset")
    prepare.add_argument("--config", required=True)
    prepare.add_argument("--out", required=True)
    add_common(prepare)

    capture = subparsers.add_parser("capture", help="capture one role's prefill K/V")
    capture.add_argument("--run", required=True)
    capture.add_argument("--role", choices=ROLES, required=True)
    add_common(capture)

    fit = subparsers.add_parser("fit", help="select layers and fit per-layer mappers")
    fit.add_argument("--run", required=True)
    add_common(fit)

    evaluate = subparsers.add_parser("evaluate", help="teacher-force the held-out continuation")
    evaluate.add_argument("--run", required=True)
    evaluate.add_argument("--split", choices=("validation", "test"), required=True)
    add_common(evaluate)

    smoke = subparsers.add_parser("smoke", help="offline random-model end-to-end check")
    smoke.add_argument("--out", default=None)
    smoke.add_argument("--keep", action="store_true")
    add_common(smoke)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            config = resolve_config(read_json(Path(args.config).expanduser()))
            summary = phase_prepare(config, Path(args.out),
                                    load_upstream(args.upstream, args.upstream_commit))
        elif args.command == "capture":
            upstream = load_upstream(args.upstream, args.upstream_commit)
            run = RunDir.open(args.run)
            summary = phase_capture(run, args.role, run.config(), upstream)
        elif args.command == "fit":
            upstream = load_upstream(args.upstream, args.upstream_commit)
            run = RunDir.open(args.run)
            summary = phase_fit(run, run.config(), upstream)
        elif args.command == "evaluate":
            upstream = load_upstream(args.upstream, args.upstream_commit)
            run = RunDir.open(args.run)
            summary = phase_evaluate(run, args.split, run.config(), upstream)
        elif args.command == "smoke":
            upstream = load_upstream(args.upstream, args.upstream_commit)
            summary = run_smoke(upstream, args.out, args.keep)
        else:  # pragma: no cover - argparse enforces the choices
            raise RunnerError(f"unknown command {args.command!r}")
    except RunnerError as error:
        log(f"error: {error}")
        print(json.dumps(
            {"status": "error", "kind": type(error).__name__, "error": str(error)},
            indent=2, sort_keys=True,
        ))
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
