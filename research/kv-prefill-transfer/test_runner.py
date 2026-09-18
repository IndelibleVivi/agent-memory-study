#!/usr/bin/env python3
"""Tests for the KV prefill transfer runner.

Run with the project interpreter, for example::

    KVPREFILL_UPSTREAM=/path/to/pinned/kvbridge-streaming \\
        python3 -B research/kv-prefill-transfer/test_runner.py
    # or
    python3 -B research/kv-prefill-transfer/test_runner.py --upstream /path/to/checkout

Every test uses real ``Qwen3ForCausalLM`` objects on CPU with no pretrained
weights: the pipeline must work end to end through the on-disk phases, not
through mocks. The upstream checkout comes from ``--upstream`` or
``KVPREFILL_UPSTREAM``; no machine path is baked into this file.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import runner  # noqa: E402  (import after sys.path setup)


def _consume_upstream_argument() -> str | None:
    argv = list(sys.argv)
    if "--upstream" in argv:
        index = argv.index("--upstream")
        value = argv[index + 1]
        del argv[index : index + 2]
        sys.argv = argv
        return value
    return os.environ.get("KVPREFILL_UPSTREAM")


UPSTREAM_PATH = _consume_upstream_argument()


def build_config(models: dict, **overrides) -> dict:
    raw = {
        "evidence_kind": "random-model-smoke",
        "dtype": "float32",
        "seq_len": 32,
        "prefix_len": 24,
        "stride": 2,
        "splits": {"train": 12, "validation": 4, "test": 4},
        "data": {
            "kind": "synthetic",
            "num_documents": 24,
            "vocab_size": 128,
            "min_tokens": 32,
            "max_tokens": 44,
        },
        "source": models["source"],
        "target": models["target"],
    }
    raw.update(overrides)
    return runner.resolve_config(raw)


def build_model_directory(path: Path, *, vocab: int, hidden: int, heads: int, layers: int,
                          kv_heads: int, head_dim: int, rope_theta: float, seed: int) -> None:
    from transformers import Qwen3Config, Qwen3ForCausalLM

    torch.manual_seed(seed)
    config = Qwen3Config(
        vocab_size=vocab,
        hidden_size=hidden,
        num_hidden_layers=layers,
        num_attention_heads=heads,
        num_key_value_heads=kv_heads,
        head_dim=head_dim,
        intermediate_size=2 * hidden,
        max_position_embeddings=256,
        tie_word_embeddings=True,
        rope_theta=rope_theta,
    )
    Qwen3ForCausalLM(config).eval().save_pretrained(path)


def build_tokenizer_directory(path: Path, vocab: dict, *, lowercase: bool) -> None:
    from tokenizers import Tokenizer, models, normalizers, pre_tokenizers
    from transformers import PreTrainedTokenizerFast

    tokenizer = Tokenizer(models.WordLevel(vocab, unk_token="<unk>"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    if lowercase:
        tokenizer.normalizer = normalizers.Lowercase()
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer, unk_token="<unk>", clean_up_tokenization_spaces=False
    )
    fast.save_pretrained(path)


def model_entry(path: Path) -> dict:
    return {"model": str(path), "revision": "local", "origin": "local"}


class RunnerPipelineTests(unittest.TestCase):
    """End-to-end behaviour of the on-disk phases on tiny random Qwen3 models."""

    @classmethod
    def setUpClass(cls) -> None:
        if not UPSTREAM_PATH:
            raise unittest.SkipTest(
                "set KVPREFILL_UPSTREAM or pass --upstream to run the runner tests"
            )
        cls.temporary = tempfile.TemporaryDirectory(prefix="kv-prefill-tests-")
        cls.root = Path(cls.temporary.name)
        cls.upstream = runner.load_upstream(UPSTREAM_PATH, runner.PINNED_UPSTREAM_COMMIT)
        cls.models = runner.build_random_pair(cls.root / "models")
        cls.config = build_config(cls.models)

        # Template run: prepare plus two independent capture processes. Fit is
        # deliberately left out so tests can exercise it on their own copies.
        cls.template = cls.root / "template-run"
        runner.phase_prepare(cls.config, cls.template, cls.upstream)
        for role in runner.ROLES:
            cls.capture_in_subprocess(cls.template, role)
        cls._fitted: dict = {}
        cls._counters: dict = {}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    # -- helpers ---------------------------------------------------------

    @classmethod
    def capture_in_subprocess(cls, run_dir: Path, role: str) -> dict:
        command = [
            sys.executable, "-B", str(HERE / "runner.py"),
            "--upstream", str(cls.upstream.root),
            "capture", "--run", str(run_dir), "--role", role,
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            raise AssertionError(f"capture {role} failed:\n{completed.stderr}")
        return json.loads(completed.stdout)

    @classmethod
    def fresh_run_dir(cls, name: str) -> Path:
        cls._counters[name] = cls._counters.get(name, 0) + 1
        destination = cls.root / "runs" / f"{name}-{cls._counters[name]}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(cls.template, destination)
        return destination

    @classmethod
    def copy_run(cls, name: str) -> runner.RunDir:
        return runner.RunDir.open(cls.fresh_run_dir(name))

    @classmethod
    def fitted_run(cls, name: str) -> runner.RunDir:
        if name not in cls._fitted:
            run = cls.copy_run(name)
            runner.phase_fit(run, cls.config, cls.upstream)
            cls._fitted[name] = run
        return cls._fitted[name]

    @classmethod
    def capture_receipt(cls, run: runner.RunDir, role: str) -> dict:
        return runner.read_json(run.path("capture", role, "receipt.json"))

    @classmethod
    def expected(cls, run: runner.RunDir, role: str, split: str, index: int,
                 documents, tokens, config: dict | None = None) -> dict:
        config = config or cls.config
        capture_ids, stride, positions = runner.capture_plan(split, tokens[index], config)
        return runner.capture_identity(
            role, split, index, capture_ids, positions, stride, run.dataset_fingerprint(),
            cls.capture_receipt(run, role)["model_fingerprint"],
        )

    def rename_models(self, roles: tuple) -> dict:
        renamed = {}
        for role in roles:
            original = Path(self.models[role]["model"])
            hidden = original.with_name(original.name + ".hidden")
            os.rename(original, hidden)
            renamed[original] = hidden
        return renamed

    @staticmethod
    def restore_models(renamed: dict) -> None:
        for original, hidden in renamed.items():
            os.rename(hidden, original)

    def stash_paths(self, paths: list) -> dict:
        self._counters["stash"] = self._counters.get("stash", 0) + 1
        stash = self.root / "stash" / str(self._counters["stash"])
        stash.mkdir(parents=True, exist_ok=True)
        stashed = {}
        for path in paths:
            target = stash / "__".join(path.parts[-3:])
            path.rename(target)
            stashed[path] = target
        return stashed

    @staticmethod
    def restore_paths(stashed: dict) -> None:
        for original, target in stashed.items():
            target.rename(original)

    @staticmethod
    def held_out_paths(run: runner.RunDir, roles=runner.ROLES) -> list:
        paths = []
        for role in roles:
            for split in ("validation", "test"):
                paths.extend(sorted(run.path("shards", role, split).glob("*.safetensors")))
                paths.extend(sorted(run.path("receipts", role, split).glob("*.json")))
        return paths

    def load_source_shard(self, run: runner.RunDir, split: str, index: int, config=None):
        documents, tokens = runner.load_prepared(run)
        return runner.load_shard(
            run, "source", split, index,
            self.expected(run, "source", split, index, documents, tokens, config),
        )

    # -- pipeline --------------------------------------------------------

    def test_smoke_cli_end_to_end_json(self) -> None:
        out = self.root / "smoke-out"
        command = [
            sys.executable, "-B", str(HERE / "runner.py"),
            "--upstream", str(self.upstream.root), "smoke", "--out", str(out),
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["evidence_kind"], "random-model-smoke")
        self.assertEqual(
            summary["phases"],
            {
                "prepare": "complete",
                "capture_source": "complete",
                "capture_target": "complete",
                "fit": "complete",
                "evaluate_validation": "complete",
                "evaluate_test": "complete",
            },
        )
        self.assertEqual(summary["quality_gate"]["status"], "not-a-gate")
        self.assertEqual(summary["attention_cosine"]["validation"], "measured")
        self.assertIn("mapped", summary["validation"])
        self.assertIn("direct_source", summary["validation"])
        self.assertLess(summary["native_vs_full_reference"]["max_abs_logit_delta"], 1e-4)
        manifest = json.loads((out / "run" / "manifest.json").read_text())
        self.assertEqual(manifest["upstream_commit"], runner.PINNED_UPSTREAM_COMMIT)
        self.assertEqual(len(manifest["phases"]), 6)
        self.assertTrue((out / "run" / "smoke-summary.json").is_file())

    def test_capture_resumes_and_repairs_broken_shards(self) -> None:
        run = self.copy_run("resume")
        self.assertEqual(self.capture_receipt(run, "source")["attention_backend"], "eager")
        again = runner.phase_capture(run, "source", self.config, self.upstream)
        self.assertEqual(again["written"], 0)
        self.assertEqual(again["skipped_complete"], 20)

        shard, receipt = runner.shard_paths(run, "source", "train", 0)
        original_digest = runner.sha256_file(shard)
        with shard.open("ab") as stream:
            stream.write(b"corrupt")
        self.assertNotEqual(runner.sha256_file(shard), original_digest)

        repaired = runner.phase_capture(run, "source", self.config, self.upstream)
        self.assertEqual(repaired["written"], 1)
        self.assertEqual(repaired["skipped_complete"], 19)
        self.assertEqual(runner.sha256_file(shard), runner.read_json(receipt)["shard_sha256"])
        documents, tokens = runner.load_prepared(run)
        loaded = runner.load_shard(run, "source", "train", 0,
                                   self.expected(run, "source", "train", 0, documents, tokens))
        self.assertEqual(loaded.keys[0].shape, (4, 16, 16))
        self.assertEqual(loaded.keys[0].dtype, torch.float32)
        self.assertIsNone(loaded.raw_keys, "train shards must not carry raw post-RoPE K")

    def test_stale_capture_identity_is_not_resumed(self) -> None:
        run = self.copy_run("stale")
        receipt = run.path("receipts", "target", "validation", "00012.json")
        expected = self.expected(run, "target", "validation", 12, *runner.load_prepared(run))
        self.assertTrue(runner.shard_is_complete(run, "target", "validation", 12, expected))

        record = runner.read_json(receipt)
        self.assertTrue(record["has_raw_key"])
        self.assertEqual(record["content_key"], "rope-stripped-float32")
        self.assertEqual(record["capture_scheme"], runner.CAPTURE_SCHEME)
        self.assertEqual(record["runner_schema_version"], str(runner.SCHEMA_VERSION))

        for field, stale in (("capture_scheme", "kv-prefill-capture-v1"),
                             ("runner_code_sha256", "0" * 64),
                             ("attention_backend", "sdpa"),
                             ("transformers", "different-runtime"),
                             ("content_key", "bfloat16-native-dtype"),
                             ("position_ids_sha256", "0" * 64),
                             ("position_scheme", "absolute-with-offset"),
                             ("runner_schema_version", "0"),
                             ("has_raw_key", "false"),
                             ("token_stride", "7")):
            mutated = dict(record)
            mutated[field] = stale
            runner.write_json_atomic(receipt, mutated)
            self.assertFalse(
                runner.shard_is_complete(run, "target", "validation", 12, expected),
                f"a stale {field} must not be resumable",
            )
            rerecord = runner.phase_capture(run, "target", self.config, self.upstream)
            self.assertEqual(rerecord["written"], 1, f"{field} should force one re-capture")
            self.assertEqual(rerecord["skipped_complete"], 19)
            loaded = runner.load_shard(run, "target", "validation", 12, expected)
            self.assertIsNotNone(loaded.raw_keys)
            record = runner.read_json(receipt)

    def test_fit_reads_only_disk_shards_without_models(self) -> None:
        run = self.copy_run("fit-no-models")
        renamed = self.rename_models(("source", "target"))
        try:
            index = runner.phase_fit(run, self.config, self.upstream)
        finally:
            self.restore_models(renamed)
        self.assertEqual(index["status"], "complete")
        self.assertEqual(len(index["layers"]), 3)
        self.assertTrue(all(layer["train_documents"] == 12 for layer in index["layers"]))
        self.assertTrue(all(layer["observations"] == 192 for layer in index["layers"]))

    def test_changed_prepared_tokens_are_rejected_before_capture(self) -> None:
        run = self.copy_run("changed-prepared-tokens")
        from safetensors.torch import load_file, save_file
        path = run.path("prepare", "tokens.safetensors")
        tensors = load_file(str(path))
        tensors["tokens.0"][0] = (tensors["tokens.0"][0] + 1) % 128
        save_file(tensors, str(path))
        with self.assertRaisesRegex(runner.IdentityError, "prepared token file"):
            runner.load_prepared(run)

    def test_fixed_fit_contract_rejects_silent_precision_or_space_changes(self) -> None:
        for override in ({"accumulation_dtype": "float32"}, {"content_space": False}):
            with self.assertRaisesRegex(runner.RunnerError, "requires float64"):
                build_config(self.models, fit=override)

    def test_fit_is_identical_without_held_out_shards(self) -> None:
        with_held_out = self.fitted_run("fit-with-heldout")
        baseline = [entry["sha256"] for entry in
                    runner.read_json(with_held_out.path("mapper", "index.json"))["layers"]]

        run = self.copy_run("fit-without-heldout")
        stashed = self.stash_paths(self.held_out_paths(run))
        try:
            index = runner.phase_fit(run, self.config, self.upstream)
        finally:
            self.restore_paths(stashed)
        self.assertEqual(baseline, [entry["sha256"] for entry in index["layers"]])

    def test_evaluate_loads_only_the_target_model(self) -> None:
        run = self.fitted_run("evaluate-target-only")
        renamed = self.rename_models(("source",))
        try:
            receipt = runner.phase_evaluate(run, "validation", self.config, self.upstream)
        finally:
            self.restore_models(renamed)
        self.assertEqual(receipt["status"], "complete")
        self.assertEqual(len(receipt["documents"]), 4)

    def test_native_cached_prefix_matches_full_forward_exactly(self) -> None:
        run = self.fitted_run("native-check")
        receipt = runner.phase_evaluate(run, "validation", self.config, self.upstream)
        self.assertEqual(receipt["index_alignment"]["logit_positions"],
                         [self.config["prefix_len"] - 1, self.config["seq_len"] - 2])
        self.assertEqual(receipt["index_alignment"]["label_indices"],
                         [self.config["prefix_len"], self.config["seq_len"] - 1])
        for entry in receipt["documents"]:
            native = entry["native_target"]
            self.assertEqual(entry["native_prefix_kind"], "raw-post-rope")
            self.assertEqual(native["logit_positions"][0] + 1, native["label_indices"][0])
            # every continuation step, not only the first, aligns with the full forward
            self.assertAlmostEqual(native["nll"], entry["full_reference_nll"], delta=1e-5)
            self.assertAlmostEqual(native["first_token"]["nll"],
                                   entry["full_reference_first_token"]["nll"], delta=1e-5)
            self.assertEqual(native["first_token"]["gold_id"],
                             entry["full_reference_first_token"]["gold_id"])
            self.assertEqual(native["first_token"]["argmax"],
                             entry["full_reference_first_token"]["argmax"])
            self.assertTrue(entry["native_vs_full_reference"]["first_argmax_match"])
            # first-logit future invariance: later tokens must not move the first logit
            self.assertLess(entry["first_logit_future_invariance"]["native_target"], 1e-4)
            self.assertLess(entry["first_logit_future_invariance"]["mapped"], 1e-4)
        self.assertLess(
            receipt["aggregate"]["native_vs_full_reference"]["max_abs_logit_delta"], 1e-4
        )
        self.assertLess(
            receipt["aggregate"]["native_vs_full_reference"]["max_abs_nll_delta"], 1e-4
        )
        self.assertNotEqual(
            receipt["aggregate"]["mapped"]["nll_mean"],
            receipt["aggregate"]["native_target"]["nll_mean"],
        )
        self.assertEqual(receipt["attention_backend"], "eager")
        self.assertGreater(receipt["aggregate"]["mean_branch_ms"]["native_target"], 0.0)

    def test_candidates_need_no_target_reference_and_ignore_branch_order(self) -> None:
        run = self.fitted_run("candidate-independent")
        mapper = runner.load_mapper(run, self.config, self.upstream)
        documents, tokens = runner.load_prepared(run)
        document = runner.documents_by_split(documents)["validation"][0]
        expected = self.expected(run, "source", "validation", document.index, documents, tokens)
        target_model, _ = runner.load_role_model(self.config, "target")
        seq_len = int(self.config["seq_len"])
        prefix_len = int(self.config["prefix_len"])
        fresh_ids = tokens[document.index][prefix_len - 1:seq_len]
        inside_positions = torch.arange(prefix_len - 1, seq_len)

        # the held-out target reference is unreachable on purpose
        stashed = self.stash_paths(self.held_out_paths(run, roles=("target",)))
        try:
            source_shard = runner.load_shard(run, "source", "validation", document.index,
                                             expected)
            rope = self.upstream.huggingface.capture_rotary_factors(
                target_model, torch.arange(prefix_len - 1).unsqueeze(0)
            )
            prefixes = runner.candidate_prefixes(source_shard, mapper, rope, self.upstream)
        finally:
            self.restore_paths(stashed)
        self.assertEqual(set(prefixes), {"mapped", "direct_source"})

        swapped = runner.candidate_prefixes(
            source_shard, mapper, rope, self.upstream, order=["direct_source", "mapped"]
        )
        with torch.inference_mode():
            outputs = runner.run_candidate_branches(
                target_model, prefixes, fresh_ids, inside_positions, seq_len, self.upstream
            )
            reordered = runner.run_candidate_branches(
                target_model, swapped, fresh_ids, inside_positions, seq_len, self.upstream,
                order=["direct_source", "mapped"],
            )
        for name in prefixes:
            self.assertTrue(torch.equal(outputs[name]["logits"], reordered[name]["logits"]))

        receipt = runner.phase_evaluate(run, "validation", self.config, self.upstream)
        recorded = next(entry for entry in receipt["documents"]
                        if entry["doc_index"] == document.index)
        labels = tokens[document.index][prefix_len:seq_len]
        candidate_nll = runner.log_softmax_nll(outputs["mapped"]["logits"], labels)
        self.assertAlmostEqual(candidate_nll, recorded["branches"]["mapped"]["nll"], places=5)

    def test_wrong_mapper_or_source_shape_fails_hard(self) -> None:
        run = self.fitted_run("shape-guard")
        mapper = runner.load_mapper(run, self.config, self.upstream)
        source_shard = self.load_source_shard(run, "validation", 12)
        target_model, _ = runner.load_role_model(self.config, "target")
        rope = self.upstream.huggingface.capture_rotary_factors(
            target_model, torch.arange(int(self.config["prefix_len"]) - 1).unsqueeze(0)
        )
        shortened = runner.LoadedShard(
            role="source", split="validation", index=12,
            keys=source_shard.keys[:-1], values=source_shard.values[:-1],
            input_ids=source_shard.input_ids, position_ids=source_shard.position_ids,
            dtype_name=source_shard.dtype_name,
        )
        with self.assertRaises(runner.RunnerError):
            runner.candidate_prefixes(shortened, mapper, rope, self.upstream)

        # a mapper whose stored weights contradict its own signature must not load
        from safetensors.torch import load_file, save_file

        index = runner.read_json(run.path("mapper", "index.json"))
        entry = index["layers"][0]
        path = run.root / entry["file"]
        tensors = load_file(str(path))
        tensors["key_weight"] = tensors["key_weight"][:, :-1, :].contiguous()
        save_file(tensors, str(path))
        entry["sha256"] = runner.sha256_file(path)
        runner.write_json_atomic(run.path("mapper", "index.json"), index)
        runner.record_fit(run, index)
        with self.assertRaises((runner.RunnerError, self.upstream.errors.KVBridgeError)):
            runner.load_mapper(run, self.config, self.upstream)

    def test_head_and_layer_order_sentinels(self) -> None:
        same = model_entry(Path(self.models["source"]["model"]))
        config = build_config({"source": same, "target": same})
        run_dir = self.root / "order-run"
        runner.phase_prepare(config, run_dir, self.upstream)
        run = runner.RunDir.open(run_dir)
        for role in runner.ROLES:
            runner.phase_capture(run, role, config, self.upstream)
        source_identity, target_identity = runner.capture_role_identities(run)
        shard = self.load_source_shard(run, "validation", 12, config)
        content = shard.cache(self.upstream)
        heads = source_identity.num_kv_heads
        head_dim = source_identity.head_dim
        layers = source_identity.num_layers
        target_model, _ = runner.load_role_model(config, "target")
        rope = self.upstream.huggingface.capture_rotary_factors(
            target_model, torch.arange(int(config["prefix_len"]) - 1).unsqueeze(0)
        )

        # head-order sentinel: target head h is taken from source head (h + 1) % H
        head_shift = []
        for layer in range(layers):
            features = heads * head_dim
            weight = torch.zeros(heads, features, head_dim, dtype=torch.float32)
            for head in range(heads):
                source_head = (head + 1) % heads
                weight[head, source_head * head_dim:(source_head + 1) * head_dim, :] = (
                    torch.eye(head_dim)
                )
            head_shift.append({
                "layer": layer, "selected_layers": [layer],
                "selection_scores": [1.0] * layers,
                "key_weight": weight.clone(), "value_weight": weight.clone(),
                "key_bias": torch.zeros(heads, head_dim),
                "value_bias": torch.zeros(heads, head_dim),
                "key_r2": 1.0, "value_r2": 1.0, "observations": 0,
            })
        index = runner.write_mapper(run, config, self.upstream, source_identity, target_identity,
                                    head_shift, {"note": "head-shift sentinel"})
        runner.record_fit(run, index)
        mapper = runner.load_mapper(run, config, self.upstream)
        mapped = runner.candidate_prefixes(shard, mapper, rope, self.upstream)[
            "mapped"].to_content_space().keys
        for layer in range(layers):
            for head in range(heads):
                expected_head = content.keys[layer][0, (head + 1) % heads]
                self.assertTrue(torch.allclose(mapped[layer][0, head], expected_head,
                                               atol=1e-5, rtol=1e-4))
            self.assertFalse(torch.allclose(mapped[layer][0, 0], content.keys[layer][0, 0],
                                            atol=1e-3, rtol=1e-3))

        # layer-order sentinel: selected [1, 0] with the weight block on block zero
        order_specs = []
        for layer in range(layers):
            features = 2 * heads * head_dim
            weight = torch.zeros(heads, features, head_dim, dtype=torch.float32)
            for head in range(heads):
                weight[head, head * head_dim:(head + 1) * head_dim, :] = torch.eye(head_dim)
            order_specs.append({
                "layer": layer, "selected_layers": [1, 0],
                "selection_scores": [0.0, 1.0],
                "key_weight": weight.clone(), "value_weight": weight.clone(),
                "key_bias": torch.zeros(heads, head_dim),
                "value_bias": torch.zeros(heads, head_dim),
                "key_r2": 1.0, "value_r2": 1.0, "observations": 0,
            })
        index = runner.write_mapper(run, config, self.upstream, source_identity, target_identity,
                                    order_specs, {"note": "layer-order sentinel"})
        runner.record_fit(run, index)
        mapper = runner.load_mapper(run, config, self.upstream)
        mapped = runner.candidate_prefixes(shard, mapper, rope, self.upstream)[
            "mapped"].to_content_space().keys
        for layer in range(layers):
            self.assertTrue(torch.allclose(mapped[layer], content.keys[1],
                                           atol=1e-5, rtol=1e-4))

    def test_known_layer_selector_oracle_with_identical_models(self) -> None:
        same = model_entry(Path(self.models["source"]["model"]))
        config = build_config({"source": same, "target": same})
        run_dir = self.root / "same-model-run"
        runner.phase_prepare(config, run_dir, self.upstream)
        run = runner.RunDir.open(run_dir)
        for role in runner.ROLES:
            runner.phase_capture(run, role, config, self.upstream)
        index = runner.phase_fit(run, config, self.upstream)
        for layer, entry in enumerate(index["layers"]):
            # source layer i of the same model is the known best match for target layer i
            self.assertEqual(entry["selected_layers"], [layer])
            scores = entry["selection_scores"]
            others = [value for position, value in enumerate(scores) if position != layer]
            self.assertGreater(scores[layer], max(others))
            self.assertGreater(entry["key_r2"], 0.999)
        receipt = runner.phase_evaluate(run, "validation", config, self.upstream)
        self.assertGreater(
            receipt["aggregate"]["mapped_reconstruction"]["key"]["r2_head_average"], 0.999
        )
        self.assertGreater(
            receipt["aggregate"]["mapped_reconstruction"]["value"]["r2_head_average"], 0.999
        )
        mapped = receipt["aggregate"]["mapped"]
        self.assertEqual(mapped["first_token_top1_agreement_mean"], 1.0)
        self.assertEqual(mapped["first_token_argmax_matches_native_rate"], 1.0)
        self.assertLess(mapped["kl_native_to_candidate_mean"], 1e-4)

    def test_reconstruction_head_average_is_per_layer_and_head(self) -> None:
        """The average must be over (layer, KV head) pairs, not over layers only."""
        generator = torch.Generator().manual_seed(11)
        layer_zero_reference = torch.randn(1, 2, 6, 4, generator=generator)
        layer_zero_candidate = layer_zero_reference.clone()
        # head 0 is exact, head 1 is destroyed with a large, high-variance error
        layer_zero_candidate[0, 1] = torch.randn(6, 4, generator=generator) * 5.0

        layer_one_reference = torch.randn(1, 2, 6, 4, generator=generator)
        layer_one_reference[0, 0] = 0.25  # constant head: zero variance convention
        layer_one_candidate = layer_one_reference.clone()
        layer_one_candidate[0, 1] = layer_one_reference[0, 1] * 0.5

        reference = [layer_zero_reference, layer_one_reference]
        candidate = [layer_zero_candidate, layer_one_candidate]
        report = runner.kv_reconstruction(candidate, reference)

        per_head = []
        for candidate_layer, reference_layer in zip(candidate, reference, strict=True):
            for head in range(reference_layer.shape[1]):
                expected = reference_layer[0, head].double()
                actual = candidate_layer[0, head].double()
                total = float(((expected - expected.mean()) ** 2).sum())
                error = float(((actual - expected) ** 2).sum())
                if total > 0:
                    per_head.append(1.0 - error / total)
                else:
                    per_head.append(1.0 if error <= torch.finfo(torch.float64).eps else 0.0)
        self.assertEqual(len(per_head), 4)
        self.assertAlmostEqual(report["r2_head_average"], sum(per_head) / len(per_head), places=9)
        self.assertEqual(per_head[2], 1.0, "a constant head follows the zero-variance convention")
        # layer-level averaging would give a very different number here
        layer_level = [
            1.0 - (float(((c - r) ** 2).sum()) / float(((r - r.mean()) ** 2).sum()))
            for c, r in ((layer_zero_candidate.double(), layer_zero_reference.double()),
                         (layer_one_candidate.double(), layer_one_reference.double()))
        ]
        self.assertGreater(abs(report["r2_head_average"] - sum(layer_level) / len(layer_level)),
                           0.05)
        self.assertNotAlmostEqual(report["r2_head_average"], report["r2_overall_pooled"],
                                  places=3)

    def test_full_length_256_disk_pipeline_control(self) -> None:
        """The exact protocol cut (256/192/191/64) end to end through disk."""
        config = build_config(
            self.models,
            seq_len=256,
            prefix_len=192,
            stride=4,
            splits={"train": 3, "validation": 2, "test": 1},
            data={"kind": "synthetic", "num_documents": 8, "vocab_size": 128,
                  "min_tokens": 256, "max_tokens": 300},
        )
        run_dir = self.root / "full-length-run"
        runner.phase_prepare(config, run_dir, self.upstream)
        run = runner.RunDir.open(run_dir)
        for role in runner.ROLES:
            runner.phase_capture(run, role, config, self.upstream)
        runner.phase_fit(run, config, self.upstream)
        receipt = runner.phase_evaluate(run, "validation", config, self.upstream)

        self.assertEqual(receipt["eval_prefix_len"], 191)
        self.assertEqual(receipt["continuation_tokens"], 64)
        self.assertEqual(receipt["index_alignment"]["captured_prefix_positions"], [0, 190])
        self.assertEqual(receipt["index_alignment"]["logit_positions"], [191, 254])
        self.assertEqual(receipt["index_alignment"]["label_indices"], [192, 255])
        self.assertEqual(receipt["attention_backend"], "eager")

        documents, tokens = runner.load_prepared(run)
        document = runner.documents_by_split(documents)["validation"][0]
        stored = runner.load_shard(
            run, "target", "validation", document.index,
            self.expected(run, "target", "validation", document.index, documents, tokens, config),
        )
        train_stored = runner.load_shard(
            run, "target", "train",
            runner.documents_by_split(documents)["train"][0].index,
            self.expected(run, "target", "train", documents[0].index, documents, tokens, config),
        )
        self.assertEqual(stored.keys[0].shape[1], 191, "cached prefix is 191 tokens")
        self.assertEqual(train_stored.keys[0].shape[1], 64, "train keeps 256 tokens at stride 4")
        self.assertEqual(train_stored.position_ids.tolist()[-1], 252)

        entry = next(item for item in receipt["documents"]
                     if item["doc_index"] == document.index)
        native = entry["branches"]["native_target"]
        self.assertEqual(native["logit_positions"], [191, 254])
        self.assertEqual(native["label_indices"], [192, 255])
        self.assertEqual(native["label_indices"][1] - native["label_indices"][0] + 1, 64)
        self.assertEqual(native["logit_positions"][0] + 1, native["label_indices"][0])
        self.assertLess(entry["native_vs_full_reference"]["max_abs_logit_delta"], 1e-5)
        for name, value in entry["first_logit_future_invariance"].items():
            self.assertLess(value, 1e-5, f"{name} first logit moved with the future")
        self.assertGreater(receipt["aggregate"]["mean_branch_ms"]["native_target"], 0.0)

        # the invariance control must keep every shape and only change the future
        target_model, _ = runner.load_role_model(config, "target")
        prefix_len = int(config["prefix_len"])
        seq_len = int(config["seq_len"])
        fresh = tokens[document.index][prefix_len - 1:seq_len - 1]
        positions = torch.arange(prefix_len - 1, seq_len - 1)
        with torch.inference_mode():
            base = runner.run_branch(target_model, stored.native_cache(self.upstream), fresh,
                                     positions, seq_len - 1, self.upstream, with_queries=False)
            reported = runner.first_logit_future_invariance(
                target_model, stored.native_cache(self.upstream), fresh, positions,
                base["logits"], self.upstream,
            )
            tail = torch.roll(fresh[1:].clone(), shifts=1, dims=0)
            perturbed = torch.cat([fresh[:1], tail])
            self.assertEqual(perturbed.shape, fresh.shape)
            self.assertTrue(torch.equal(perturbed[:1], fresh[:1]))
            moved = runner.run_branch(target_model, stored.native_cache(self.upstream), perturbed,
                                      positions, seq_len - 1, self.upstream, with_queries=False)
            manual = float(
                (moved["logits"][:, 0, :] - base["logits"][:, 0, :]).abs().max()
            )
        self.assertAlmostEqual(reported, manual, places=9)
        self.assertLess(reported, 1e-5)

    def test_fp64_ridge_is_chunk_and_order_invariant(self) -> None:
        generator = torch.Generator().manual_seed(260803893)
        features = torch.randn(192, 7, dtype=torch.float64, generator=generator)
        outputs = torch.randn(192, 5, dtype=torch.float64, generator=generator)
        alpha = 0.01
        whole = self.upstream.RidgeAccumulator(7, 5, dtype=torch.float64, device="cpu")
        whole.update(features, outputs)

        chunked = self.upstream.RidgeAccumulator(7, 5, dtype=torch.float64, device="cpu")
        order = torch.randperm(192, generator=torch.Generator().manual_seed(7))
        cursor = 0
        for size in (1, 13, 32, 5, 64, 77):
            indices = order[cursor:cursor + size]
            cursor += size
            chunked.update(features[indices], outputs[indices])
        self.assertEqual(cursor, 192)

        first_half = self.upstream.RidgeAccumulator(7, 5, dtype=torch.float64, device="cpu")
        first_half.update(features[order[:100]], outputs[order[:100]])
        second_half = self.upstream.RidgeAccumulator(7, 5, dtype=torch.float64, device="cpu")
        second_half.update(features[order[100:]], outputs[order[100:]])
        merged = self.upstream.RidgeAccumulator(7, 5, dtype=torch.float64, device="cpu")
        merged.merge(first_half).merge(second_half)

        centered = features - features.mean(0)
        closed_form = torch.linalg.solve(
            centered.T @ centered + alpha * torch.eye(7, dtype=torch.float64),
            centered.T @ (outputs - outputs.mean(0)),
        )
        for accumulator in (whole, chunked, merged):
            solution = accumulator.solve(alpha)
            self.assertEqual(solution.observations, 192)
            self.assertTrue(torch.allclose(solution.weight, closed_form, atol=1e-12, rtol=1e-12))
        self.assertTrue(torch.allclose(whole.solve(alpha).weight, chunked.solve(alpha).weight,
                                       atol=1e-12, rtol=1e-12))

    def test_mapper_reapplies_target_rope_with_different_theta(self) -> None:
        """An identity mapper must reproduce the native prefix across RoPE thetas."""
        root = self.root / "identity-theta"
        root.mkdir(parents=True, exist_ok=True)
        source_dir, target_dir = root / "source", root / "target"
        # one layer: layer-0 K/V content depends only on the embeddings, so two
        # models with identical weights and different rope_theta share content K
        build_model_directory(source_dir, vocab=128, hidden=128, heads=8, layers=1,
                              kv_heads=4, head_dim=16, rope_theta=10_000.0, seed=31)
        build_model_directory(target_dir, vocab=128, hidden=128, heads=8, layers=1,
                              kv_heads=4, head_dim=16, rope_theta=500_000.0, seed=31)
        from safetensors.torch import load_file, save_file

        save_file(dict(load_file(str(source_dir / "model.safetensors"))),
                  str(target_dir / "model.safetensors"))

        config = runner.resolve_config({
            "evidence_kind": "random-model-smoke",
            "dtype": "float32",
            "seq_len": 32,
            "prefix_len": 24,
            "stride": 2,
            "splits": {"train": 4, "validation": 2, "test": 2},
            "data": {"kind": "synthetic", "num_documents": 12, "vocab_size": 128,
                     "min_tokens": 32, "max_tokens": 40},
            "source": model_entry(source_dir),
            "target": model_entry(target_dir),
        })
        run_dir = root / "run"
        runner.phase_prepare(config, run_dir, self.upstream)
        run = runner.RunDir.open(run_dir)
        for role in runner.ROLES:
            runner.phase_capture(run, role, config, self.upstream)
        source_identity, target_identity = runner.capture_role_identities(run)
        self.assertNotEqual(source_identity.rope_theta, target_identity.rope_theta)

        heads = target_identity.num_kv_heads
        head_dim = target_identity.head_dim
        specs = []
        for layer in range(target_identity.num_layers):
            features = heads * head_dim
            weight = torch.zeros(heads, features, head_dim, dtype=torch.float32)
            for head in range(heads):
                weight[head, head * head_dim:(head + 1) * head_dim, :] = torch.eye(head_dim)
            specs.append({
                "layer": layer, "selected_layers": [layer],
                "selection_scores": [1.0] * source_identity.num_layers,
                "key_weight": weight.clone(), "value_weight": weight.clone(),
                "key_bias": torch.zeros(heads, head_dim),
                "value_bias": torch.zeros(heads, head_dim),
                "key_r2": 1.0, "value_r2": 1.0, "observations": 0,
            })
        index = runner.write_mapper(run, config, self.upstream, source_identity, target_identity,
                                    specs, {"note": "hand-built identity mapper"})
        runner.record_fit(run, index)

        documents, tokens = runner.load_prepared(run)
        document = runner.documents_by_split(documents)["validation"][0]
        target_shard = runner.load_shard(
            run, "target", "validation", document.index,
            self.expected(run, "target", "validation", document.index, documents, tokens, config),
        )
        source_shard = self.load_source_shard(run, "validation", document.index, config)
        capture_ids, _, _ = runner.capture_plan("validation", tokens[document.index], config)

        # the two models share content K, yet the raw rotated K genuinely differs
        content_delta = (source_shard.cache(self.upstream).keys[0]
                         - target_shard.cache(self.upstream).keys[0]).abs().max()
        source_model, _ = runner.load_role_model(config, "source")
        with torch.inference_mode():
            _, source_raw, _ = runner.capture_kv(source_model, capture_ids, self.upstream)
        raw_delta = (source_raw.keys[0]
                     - target_shard.native_cache(self.upstream).keys[0]).abs().max()
        self.assertLess(float(content_delta), 1e-6)
        self.assertGreater(float(raw_delta), 1e-3)

        receipt = runner.phase_evaluate(run, "validation", config, self.upstream)
        entry = receipt["documents"][0]
        self.assertGreater(entry["reconstruction"]["mapped"]["key"]["r2_overall_pooled"], 0.9999)
        self.assertGreater(entry["reconstruction"]["mapped"]["value"]["r2_overall_pooled"], 0.9999)
        self.assertLess(entry["branches"]["mapped"]["kl_native_to_candidate"], 1e-6)
        self.assertEqual(entry["branches"]["mapped"]["top1_agreement"], 1.0)
        self.assertEqual(entry["branches"]["mapped"]["first_token"]["gold_id"],
                         entry["native_target"]["first_token"]["gold_id"])
        self.assertLess(abs(entry["branches"]["mapped"]["nll"] - entry["native_target"]["nll"]),
                        1e-5)
        self.assertLess(entry["native_vs_full_reference"]["max_abs_logit_delta"], 1e-5)

    def test_bfloat16_random_qwen_boundary(self) -> None:
        """The raw native path stays exact at bfloat16; the round trip is a diagnostic."""
        config = build_config(self.models, dtype="bfloat16",
                              splits={"train": 8, "validation": 3, "test": 3},
                              data={"kind": "synthetic", "num_documents": 18,
                                    "vocab_size": 128, "min_tokens": 32, "max_tokens": 40})
        run_dir = self.root / "bfloat16-run"
        runner.phase_prepare(config, run_dir, self.upstream)
        run = runner.RunDir.open(run_dir)
        for role in runner.ROLES:
            runner.phase_capture(run, role, config, self.upstream)
        record = runner.read_json(run.path("receipts", "target", "validation", "00008.json"))
        self.assertEqual(record["capture_dtype"], "bfloat16")
        self.assertEqual(record["content_key_dtype"], "float32")
        self.assertTrue(record["raw_key_stored"])
        self.assertTrue(math.isfinite(record["content_roundtrip_r2"]))
        self.assertFalse(
            runner.read_json(run.path("receipts", "target", "train", "00000.json"))[
                "raw_key_stored"
            ]
        )
        runner.phase_fit(run, config, self.upstream)
        receipt = runner.phase_evaluate(run, "validation", config, self.upstream)
        # the raw capture is used verbatim, so the split path still matches the full forward
        self.assertLess(
            receipt["aggregate"]["native_vs_full_reference"]["max_abs_logit_delta"], 1e-3
        )
        self.assertTrue(receipt["aggregate"]["native_vs_full_reference"]["first_argmax_match_all"])
        for entry in receipt["documents"]:
            self.assertEqual(entry["native_prefix_kind"], "raw-post-rope")
            roundtrip = entry["reconstruction"]["native_content_roundtrip"]["key"]
            self.assertGreaterEqual(roundtrip["r2_overall_pooled"], 0.99)
            self.assertIsNotNone(entry["branches"]["mapped"]["nll"])
        self.assertEqual(receipt["quality_gate"]["status"], "not-a-gate")
        stored = runner.load_shard(
            run, "target", "validation", 8,
            self.expected(run, "target", "validation", 8, *runner.load_prepared(run), config),
        )
        self.assertEqual(stored.keys[0].dtype, torch.float32)
        self.assertEqual(stored.raw_keys[0].dtype, torch.bfloat16)

    def test_prepare_two_tokenizers_align_and_reject_mismatch(self) -> None:
        vocab = {"<unk>": 0, "alpha": 1, "beta": 2, "gamma": 3}
        swapped = {"<unk>": 0, "alpha": 2, "beta": 1, "gamma": 3}
        root = self.root / "tokenizers"
        source_tok, target_tok = root / "source", root / "target"
        lower_tok, swapped_tok = root / "lower", root / "swapped"
        build_tokenizer_directory(source_tok, vocab, lowercase=False)
        build_tokenizer_directory(target_tok, vocab, lowercase=False)
        build_tokenizer_directory(lower_tok, vocab, lowercase=True)
        build_tokenizer_directory(swapped_tok, swapped, lowercase=False)
        self.assertEqual(
            runner.resolve_tokenizer_identity(model_entry(source_tok)),
            runner.resolve_tokenizer_identity(model_entry(target_tok)),
        )

        texts = [
            "alpha beta gamma beta alpha beta gamma beta",
            "beta gamma alpha gamma beta alpha gamma alpha",
            "gamma alpha beta alpha gamma beta alpha beta",
            "alpha gamma beta gamma alpha gamma beta gamma",
        ]
        data = root / "documents.jsonl"
        data.write_text("\n".join(json.dumps({
            "id": f"doc-{index}", "text": text,
            "source_url": f"https://example.invalid/{index}",
        }) for index, text in enumerate(texts)) + "\n", encoding="utf-8")

        def make(role_source: Path, role_target: Path, path: Path = data) -> dict:
            return runner.resolve_config({
                "evidence_kind": "pretrained-transfer",
                "dtype": "float32",
                "seq_len": 8,
                "prefix_len": 4,
                "stride": 1,
                "splits": {"train": 2, "validation": 1, "test": 1},
                "source": model_entry(role_source),
                "target": model_entry(role_target),
                "data": {"kind": "jsonl", "path": str(path)},
            })

        receipt = runner.phase_prepare(make(source_tok, target_tok),
                                       self.root / "tok-run-ok", self.upstream)
        self.assertEqual(receipt["token_alignment"], "two-tokenizers")
        self.assertEqual(receipt["counts"], {"train": 2, "validation": 1, "test": 1})
        self.assertTrue(all(document["source_url"] for document in receipt["documents"]))

        with self.assertRaises(runner.IdentityError):
            runner.phase_prepare(make(source_tok, swapped_tok),
                                 self.root / "tok-run-swapped", self.upstream)

        # same vocabulary hash, different normalizer: the per-document token
        # comparison has to catch it
        uppercase = root / "uppercase.jsonl"
        uppercase.write_text("\n".join(json.dumps({
            "id": f"up-{index}", "text": f"Alpha beta gamma beta Alpha beta gamma beta {index}",
        }) for index in range(4)) + "\n", encoding="utf-8")
        with self.assertRaises(runner.IdentityError):
            runner.phase_prepare(make(source_tok, lower_tok, uppercase),
                                 self.root / "tok-run-lower", self.upstream)

    def test_prepare_deduplicates_and_rejects_conflicting_ids(self) -> None:
        vocab = {"<unk>": 0, "alpha": 1, "beta": 2, "gamma": 3}
        root = self.root / "dedupe"
        source_tok, target_tok = root / "source", root / "target"
        build_tokenizer_directory(source_tok, vocab, lowercase=False)
        build_tokenizer_directory(target_tok, vocab, lowercase=False)
        records = [
            {"id": "keep-1", "text": "alpha beta gamma alpha beta gamma alpha beta"},
            {"id": "keep-1", "text": "alpha beta gamma alpha beta gamma alpha beta"},
            {"id": "keep-2", "text": "gamma beta alpha gamma beta alpha gamma beta"},
            {"id": "dup-text", "text": "gamma beta alpha gamma beta alpha gamma beta"},
            {"id": "keep-3", "text": "beta gamma alpha beta gamma alpha beta gamma"},
            {"id": "keep-4", "text": "alpha alpha beta beta gamma gamma alpha beta"},
        ]
        data = root / "documents.jsonl"
        data.write_text("\n".join(json.dumps(record) for record in records) + "\n",
                        encoding="utf-8")
        config = runner.resolve_config({
            "evidence_kind": "pretrained-transfer",
            "dtype": "float32",
            "seq_len": 8,
            "prefix_len": 4,
            "stride": 1,
            "splits": {"train": 2, "validation": 1, "test": 1},
            "source": model_entry(source_tok),
            "target": model_entry(target_tok),
            "data": {"kind": "jsonl", "path": str(data)},
        })
        receipt = runner.phase_prepare(config, root / "run", self.upstream)
        self.assertEqual(receipt["dedupe"], {"duplicate_ids": 1, "duplicate_text": 1})
        self.assertEqual(len(receipt["documents"]), 4)

        conflict = root / "conflict.jsonl"
        conflict.write_text(
            json.dumps({"id": "same", "text": "alpha beta gamma alpha beta gamma alpha beta"})
            + "\n"
            + json.dumps({"id": "same", "text": "beta beta beta beta beta beta beta beta"})
            + "\n",
            encoding="utf-8",
        )
        conflicted = runner.resolve_config({
            "evidence_kind": "pretrained-transfer",
            "dtype": "float32",
            "seq_len": 8,
            "prefix_len": 4,
            "stride": 1,
            "splits": {"train": 1, "validation": 1, "test": 1},
            "source": model_entry(source_tok),
            "target": model_entry(target_tok),
            "data": {"kind": "jsonl", "path": str(conflict)},
        })
        with self.assertRaises(runner.IdentityError):
            runner.phase_prepare(conflicted, root / "conflict-run", self.upstream)

    def test_upstream_commit_pin_is_enforced(self) -> None:
        with self.assertRaises(runner.RunnerError):
            runner.load_upstream(str(self.upstream.root), "0" * 40)
        with self.assertRaises(runner.RunnerError):
            runner.load_upstream(None, runner.PINNED_UPSTREAM_COMMIT)
        with self.assertRaises(runner.RunnerError):
            runner.load_upstream(str(self.root / "missing-checkout"),
                                 runner.PINNED_UPSTREAM_COMMIT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
