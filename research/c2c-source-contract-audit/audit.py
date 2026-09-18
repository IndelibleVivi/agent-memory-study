#!/usr/bin/env python3
"""Source-bound contract audit of the public Cache-to-Cache (C2C) implementation.

This runner imports and executes the *real* classes from a pinned local checkout
of https://github.com/thu-nics/C2C:

  rosetta.model.aligner.TokenAligner      one-to-many first/longest selection
  rosetta.model.projector.C2CProjector    learnable gate + residual fusion

plus source-level inspection of the cache-enrichment trimming example and the
shipped training/evaluation recipes.

Run it with the interpreter that has torch/transformers installed, from any cwd:

    python3 audit.py run --source-dir <checkout> --write results.json

Boundaries:
  * The tokenizers handed to TokenAligner are bounded input substitutes defined in
    ``fixtures.json``. They are not Qwen tokenizer metadata and no row here is
    evidence about real tokenizer behaviour.
  * No model weights are loaded, downloaded, or trained. The trimming example is
    inspected at source level only, because executing it needs a real model pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES_PATH = os.path.join(HERE, "fixtures.json")

PAPER = {
    "id": "arXiv:2510.03215v2",
    "url": "https://arxiv.org/abs/2510.03215v2",
    "venue": "ICLR 2026 camera-ready (arXiv v2)",
}

UPSTREAM_REPO = "https://github.com/thu-nics/C2C"
PINNED_COMMIT = "113c3a9b2538cbf096a0477e1ec99ae2a2e0d12a"

# Files the audit reads, with the reason each one is in scope.
SOURCE_FILES = [
    ("rosetta/model/aligner.py", "TokenAligner, AlignmentStrategy"),
    ("rosetta/model/projector.py", "C2CProjector gate and residual fusion"),
    ("script/train/SFT_train.py", "aligner construction default and freeze config"),
    ("script/evaluation/unified_evaluator.py", "aligner construction in evaluation"),
    ("script/evaluation/standard_kvcache_del.py", "cache-enrichment trimming example"),
    ("recipe/train_recipe/C2C_0.6+0.5.json", "shipped training recipe"),
    ("recipe/eval_recipe/unified_eval.yaml", "shipped evaluation recipe"),
]


# --------------------------------------------------------------------------
# bounded tokenizer substitutes
# --------------------------------------------------------------------------


class MockTokenizer:
    """Minimal object satisfying the interface TokenAligner actually calls.

    Deliberately bounded: greedy longest-prefix encoding over a fixed vocab, and
    decode of a single id back to its vocab string. Not a real tokenizer.
    """

    def __init__(self, spec):
        vocab = {int(k): str(v) for k, v in spec["vocab"].items()}
        inverse = {}
        for token_id, piece in vocab.items():
            inverse.setdefault(piece, token_id)
        self._vocab = vocab
        self._inverse = inverse
        self._by_len = sorted(vocab.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        self.pad_token_id = spec["pad_token_id"]
        self.eos_token_id = spec["eos_token_id"]
        self.unk_token_id = spec["unk_token_id"]
        self.bos_token_id = spec.get("bos_token_id")
        self.all_special_ids = list(spec["special_ids"])
        self.pad_token = vocab.get(self.pad_token_id, "<pad>")
        self.eos_token = vocab.get(self.eos_token_id, "<eos>")

    def decode(self, token_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False):
        return "".join(self._vocab[int(i)] for i in token_ids)

    def encode(self, text, add_special_tokens=False, return_tensors=None):
        out = []
        i = 0
        while i < len(text):
            found = None
            for token_id, piece in self._by_len:
                if piece and text.startswith(piece, i):
                    found = (token_id, len(piece))
                    break
            if found is None:
                raise ValueError("mock cannot encode %r at offset %d" % (text, i))
            out.append(found[0])
            i += found[1]
        return out

    def convert_tokens_to_ids(self, token):
        return self._inverse.get(token, self.unk_token_id)


def evaluate_criterion(kind, required, selected_text, slm_token_text):
    stripped = selected_text.strip()
    if kind == "exact_lexeme":
        return stripped == required
    if kind == "complete_content":
        return stripped == slm_token_text.strip()
    raise ValueError("unknown criterion kind: %s" % kind)


# --------------------------------------------------------------------------
# source binding
# --------------------------------------------------------------------------


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(source_dir, *args):
    out = subprocess.run(
        ["git", "-C", source_dir, *args], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def bind_source(source_dir, expect_commit):
    commit = git(source_dir, "rev-parse", "HEAD")
    binding = {
        "repo": UPSTREAM_REPO,
        "commit": commit,
        "commit_date": git(source_dir, "log", "-1", "--format=%cI"),
        "expected_commit": expect_commit,
        "commit_matches_pin": commit == expect_commit,
        "dirty": bool(git(source_dir, "status", "--porcelain")),
        "files": [],
    }
    for rel, purpose in SOURCE_FILES:
        path = os.path.join(source_dir, rel)
        binding["files"].append(
            {
                "path": rel,
                "purpose": purpose,
                "sha256": sha256_file(path),
                "bytes": os.path.getsize(path),
            }
        )
    return binding


def load_upstream(source_dir):
    if source_dir not in sys.path:
        sys.path.insert(0, source_dir)
    from rosetta.model.aligner import AlignmentStrategy, TokenAligner  # noqa: E402
    from rosetta.model.projector import C2CProjector  # noqa: E402

    return {"AlignmentStrategy": AlignmentStrategy, "TokenAligner": TokenAligner, "C2CProjector": C2CProjector}


# --------------------------------------------------------------------------
# TokenAligner probes (real class, bounded tokenizer substitutes)
# --------------------------------------------------------------------------


def run_aligner_probes(source_dir, fixtures):
    upstream = load_upstream(source_dir)
    TokenAligner = upstream["TokenAligner"]
    AlignmentStrategy = upstream["AlignmentStrategy"]

    slm = MockTokenizer(fixtures["tokenizer_mocks"]["slm"])
    llm = MockTokenizer(fixtures["tokenizer_mocks"]["llm"])

    rows = []
    for fx in fixtures["fixtures"]:
        entry = {
            "id": fx["id"],
            "role": fx["role"],
            "slm_token_id": fx["slm_token_id"],
            "slm_token_text": fx["slm_token_text"],
            "why_this_role": fx["why_this_role"],
            "criterion": fx["criterion"],
            "strategies": {},
        }
        for strategy_name in ("first", "longest"):
            # Fresh instance per strategy: the source caches by slm id tuple.
            aligner = TokenAligner(slm_tokenizer=slm, llm_tokenizer=llm, strategy=strategy_name)
            aligned, mapping = aligner.align_tokens([fx["slm_token_id"]], return_mapping=True)
            selected = aligned[0]
            candidates = list(mapping[0][1])
            selected_text = llm.decode(
                [selected], skip_special_tokens=False, clean_up_tokenization_spaces=False
            )
            criterion = fx["criterion"]
            entry["strategies"][strategy_name] = {
                "resolved_strategy": aligner.strategy.value,
                "candidates": candidates,
                "candidate_texts": [
                    llm.decode([c], skip_special_tokens=False, clean_up_tokenization_spaces=False)
                    for c in candidates
                ],
                "selected": selected,
                "selected_text": selected_text,
                "criteria_met": evaluate_criterion(
                    criterion["kind"], criterion["required"], selected_text, fx["slm_token_text"]
                ),
            }
        entry["candidate_shape_matches_fixture"] = (
            entry["strategies"]["first"]["candidates"] == list(fx["expected_llm_candidates"])
        )
        rows.append(entry)

    defaults = {
        "constructor_default_strategy": TokenAligner(
            slm_tokenizer=slm, llm_tokenizer=llm
        ).strategy.value,
        "constructor_default_is_FIRST": TokenAligner(slm_tokenizer=slm, llm_tokenizer=llm).strategy
        is AlignmentStrategy.FIRST,
        "string_longest_resolves_to": TokenAligner(
            slm_tokenizer=slm, llm_tokenizer=llm, strategy="longest"
        ).strategy.value,
    }
    try:
        TokenAligner(slm_tokenizer=slm, llm_tokenizer=llm, strategy="prefix")
        defaults["invalid_string_prefix"] = "accepted"
    except ValueError as exc:
        defaults["invalid_string_prefix"] = "ValueError: %s" % exc

    special = TokenAligner(slm_tokenizer=slm, llm_tokenizer=llm, strategy="first")
    special_aligned, special_mapping = special.align_tokens(
        [slm.eos_token_id], return_mapping=True
    )
    special_row = {
        "slm_special_id": slm.eos_token_id,
        "llm_eos_id": llm.eos_token_id,
        "aligned": special_aligned,
        "candidates": list(special_mapping[0][1]),
        "note": "special ids take the _map_special_token branch; the 1-to-many strategy is not consulted",
    }

    cached = TokenAligner(slm_tokenizer=slm, llm_tokenizer=llm, strategy="first")
    first_result = cached.align_tokens([101])
    cached.strategy = AlignmentStrategy.LONGEST
    after_mutation = cached.align_tokens([101])
    cache_row = {
        "first_result": first_result,
        "after_switching_instance_strategy_to_longest": after_mutation,
        "returned_cached_value": first_result == after_mutation,
        "scope": (
            "Documented so that every probe above uses a fresh instance. All shipped call "
            "sites pass the strategy at construction and never reassign it."
        ),
    }

    return {
        "rows": rows,
        "constructor_defaults": defaults,
        "special_token_path": special_row,
        "cache_behaviour": cache_row,
    }


# --------------------------------------------------------------------------
# C2CProjector probes (real class, synthetic tensors)
# --------------------------------------------------------------------------


def run_projector_probes(source_dir):
    import torch
    torch.set_grad_enabled(False)

    upstream = load_upstream(source_dir)
    C2CProjector = upstream["C2CProjector"]

    def build(**overrides):
        kwargs = dict(
            source_dim=8,
            target_dim=6,
            source_num_heads=1,
            target_num_heads=1,
            intermediate_dim=16,
            hidden_dim=16,
            num_layers=3,
            dropout=0.1,
        )
        kwargs.update(overrides)
        return C2CProjector(**kwargs)

    torch.manual_seed(20260918)
    batch, tokens = 1, 4
    source_key = torch.randn(batch, 1, tokens, 8)
    source_value = torch.randn(batch, 1, tokens, 8)
    target_key = torch.randn(batch, 1, tokens, 6)
    target_value = torch.randn(batch, 1, tokens, 6)

    results = {}

    projector = build()
    projector.eval()
    out_key, out_value = projector((source_key, source_value), (target_key, target_value))
    results["eval_closed_gate_is_identity"] = {
        "key_identical_to_target": bool(torch.equal(out_key, target_key)),
        "value_identical_to_target": bool(torch.equal(out_value, target_value)),
        "init_key_gate_logit": float(projector.key_gate_logit.detach()),
        "gate_rule": "inference uses (gate_logit > 0); the 0.0 initial logit therefore closes the gate",
        "shape_preserved": list(out_key.shape) == list(target_key.shape),
        "dtype_preserved": out_key.dtype == target_key.dtype,
    }

    projector.key_gate_logit.data.fill_(1.0)
    projector.value_gate_logit.data.fill_(1.0)
    open_key, open_value = projector((source_key, source_value), (target_key, target_value))
    open_key_again, open_value_again = projector((source_key, source_value), (target_key, target_value))
    results["eval_open_gate_adds_a_term"] = {
        "key_differs_from_target": bool(not torch.equal(open_key, target_key)),
        "value_differs_from_target": bool(not torch.equal(open_value, target_value)),
        "deterministic_in_eval": bool(
            torch.equal(open_key, open_key_again) and torch.equal(open_value, open_value_again)
        ),
        "delta_key_norm": float((open_key - target_key).norm()),
        "delta_value_norm": float((open_value - target_value).norm()),
    }

    # Zero the projection output so the added term must vanish; this pins the
    # residual structure (target + gated projected term) rather than replacement.
    for module in (projector.key_proj_out, projector.value_proj_out):
        torch.nn.init.zeros_(module.weight)
        torch.nn.init.zeros_(module.bias)
    zeroed_key, zeroed_value = projector((source_key, source_value), (target_key, target_value))
    results["residual_structure"] = {
        "key_identical_to_target_with_gate_open_and_zero_projection": bool(
            torch.equal(zeroed_key, target_key)
        ),
        "value_identical_to_target_with_gate_open_and_zero_projection": bool(
            torch.equal(zeroed_value, target_value)
        ),
        "reading": (
            "The gated term enters only through the projection path and is added to the "
            "target tensors, which is the residual form of Eq.(3). Whether the fused cache "
            "then replaces the receiver cache downstream is a separate wiring question."
        ),
    }

    threshold = build()
    threshold.eval()
    threshold.key_gate_logit.data.fill_(0.0)
    closed_key, _ = threshold((source_key, source_value), (target_key, target_value))
    threshold.key_gate_logit.data.fill_(1e-6)
    tiny_key, _ = threshold((source_key, source_value), (target_key, target_value))
    results["gate_threshold"] = {
        "logit_0_closes_gate": bool(torch.equal(closed_key, target_key)),
        "logit_1e_minus_6_opens_gate": bool(not torch.equal(tiny_key, target_key)),
        "rule": "strict inequality (logit > 0) at inference",
    }

    schedule = build(initial_temperature=1.0, final_temperature=0.001, anneal_steps=1929)
    temps = {}
    for step in (0, 964, 1929, 10 ** 6):
        schedule.update_temperature(step)
        temps[str(step)] = float(schedule.gate_temperature)
    results["gate_temperature_annealing"] = {
        "temperatures": temps,
        "monotonic_nonincreasing": (
            temps["0"] >= temps["964"] >= temps["1929"] >= temps["1000000"]
        ),
        # The gate_temperature buffer is float32, so 0.001 is stored as
        # 0.001000000047...; compare at float32 scale rather than bit-exactly.
        "clamped_at_final": abs(temps["1000000"] - 0.001) < 1e-6,
        "note": "gate_temperature is a float32 buffer; reported values carry float32 rounding",
    }

    try:
        build(num_layers=2)
        results["num_layers_guard"] = "accepted"
    except AssertionError as exc:
        results["num_layers_guard"] = "AssertionError: %s" % exc

    return results


# --------------------------------------------------------------------------
# trimming example and recipes (source level)
# --------------------------------------------------------------------------


def inspect_trimming(source_dir):
    path = os.path.join(source_dir, "script/evaluation/standard_kvcache_del.py")
    patterns = {
        "first_pass_len": "full_seq_len = first_pass_input_ids.shape[1]",
        "keep_prefix_slice": "key[:, :, :15, :]",
        "drop_exemplars_slice": "key[:, :, few_shot_len:, :]",
        "second_pass_positions": "position_ids = torch.arange(",
        "second_pass_forward": "past_key_values=new_past_key_values",
    }
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    locators = {}
    for name, needle in patterns.items():
        hits = [i + 1 for i, line in enumerate(lines) if needle in line]
        locators[name] = {
            "needle": needle,
            "lines": hits,
            "source": [lines[i - 1].strip() for i in hits],
        }
    return {
        "file": "script/evaluation/standard_kvcache_del.py",
        "branch": "few_shot_delete",
        "executed": False,
        "not_executed_reason": "the branch needs a real model forward pass; no weights were loaded",
        "locators": locators,
        "semantics": (
            "After the first pass over exemplars + question, each layer's cache is rebuilt as "
            "[0:15) concatenated with [few_shot_len:N), i.e. a template prefix plus everything "
            "from the exemplar boundary onward. The second pass feeds only the answer prefix and "
            "uses absolute position ids continuing at full_seq_len, so retained entries keep the "
            "positions they had before the deletion. No attention mask is passed for the second "
            "pass, so attention spans the retained cache plus the new tokens."
        ),
        "preserved_positions_is_intentional": (
            "Keeping the original absolute positions is self-consistent for a cache whose keys "
            "were already rotated at those positions; this audit does not treat it as a defect."
        ),
        "comment_note": (
            "The inline comment next to the prefix slice says it keeps 'the first element' while "
            "the code keeps 15. Recorded as a comment/code mismatch without inferring intent."
        ),
    }


def run_config_probes(source_dir):
    train_recipe = os.path.join(source_dir, "recipe/train_recipe/C2C_0.6+0.5.json")
    with open(train_recipe, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    model_cfg = recipe["model"]
    training_cfg = recipe["training"]

    eval_recipe = os.path.join(source_dir, "recipe/eval_recipe/unified_eval.yaml")
    with open(eval_recipe, "r", encoding="utf-8") as handle:
        eval_lines = [
            line.strip()
            for line in handle
            if "alignment_strategy" in line or "is_do_alignment" in line
        ]

    algo = load_upstream(source_dir)["AlignmentStrategy"]
    try:
        algo("prefix")
        evaluator_fallback = "accepted"
    except ValueError as exc:
        evaluator_fallback = "ValueError: %s" % exc

    return {
        "training_recipe": {
            "path": "recipe/train_recipe/C2C_0.6+0.5.json",
            "base_model": model_cfg["base_model"],
            "teacher_model": model_cfg["teacher_model"],
            "mapping": model_cfg["mapping"],
            "is_do_alignment": model_cfg["is_do_alignment"],
            "alignment_strategy": model_cfg["alignment_strategy"],
            "projector_type": model_cfg["projector"]["type"],
            "projector_params": model_cfg["projector"]["params"],
            "freeze": training_cfg["freeze"],
            "learning_rate": training_cfg["learning_rate"],
            "weight_decay": training_cfg["weight_decay"],
            "num_epochs": training_cfg["num_epochs"],
            "scheduler_type": training_cfg["scheduler_type"],
            "warmup_ratio": training_cfg["warmup_ratio"],
            "max_grad_norm": training_cfg["max_grad_norm"],
            "gradient_accumulation_steps": training_cfg["gradient_accumulation_steps"],
            "per_device_train_batch_size": training_cfg["per_device_train_batch_size"],
            "seed": training_cfg["seed"],
        },
        "training_recipe_checks": {
            "freezes_both_models": set(training_cfg["freeze"]) >= {"base", "teacher"},
            "alignment_disabled_in_training_recipe": model_cfg["is_do_alignment"] is False,
            "training_strategy_value": model_cfg["alignment_strategy"],
        },
        "evaluation_recipe": {
            "path": "recipe/eval_recipe/unified_eval.yaml",
            "alignment_lines": eval_lines,
        },
        "alignment_strategy_defaults": {
            "class_signature_default": "first",
            "training_script_fallback": "first",
            "evaluator_fallback_string": "prefix",
            "evaluator_fallback_is_valid_enum": evaluator_fallback,
            "note": (
                "The class default and the training-script fallback are 'first'; the evaluator "
                "falls back to the string 'prefix', which is not a member of AlignmentStrategy. "
                "The shipped recipes set the value explicitly."
            ),
        },
    }


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def run(source_dir, fixtures_path=FIXTURES_PATH):
    import torch
    import transformers
    with open(fixtures_path, "r", encoding="utf-8") as handle:
        fixtures = json.load(handle)
    binding = bind_source(source_dir, PINNED_COMMIT)
    if not binding["commit_matches_pin"]:
        raise SystemExit(
            "checkout HEAD %s does not match pinned commit %s"
            % (binding["commit"], PINNED_COMMIT)
        )
    if binding["dirty"]:
        raise SystemExit("checkout has uncommitted changes; refusing to audit a dirty tree")

    return {
        "schema": "ams/c2c-source-contract-audit.results@2",
        "environment": {"python": platform.python_version(), "torch": torch.__version__, "transformers": transformers.__version__, "device": "cpu", "seed": 20260918},
        "paper": PAPER,
        "source": binding,
        "tokenizer_mocks": fixtures["tokenizer_mocks"],
        "aligner": run_aligner_probes(source_dir, fixtures),
        "projector": run_projector_probes(source_dir),
        "trimming_example": inspect_trimming(source_dir),
        "training_config": run_config_probes(source_dir),
        "real_tokenizer_roundtrip": {
            "status": "not-tested",
            "reason": (
                "No local tokenizer metadata for the paired models was available, and the audit "
                "does not download model artifacts."
            ),
        },
        "claim_ceiling": [
            "Every aligner row exercises the real TokenAligner but with hand-written tokenizer substitutes; it is not evidence about real Qwen tokenizers.",
            "Projector rows exercise the real C2CProjector with synthetic tensors at toy dimensions; they are structure checks, not training or quality results.",
            "The trimming example is inspected at source level only and was not executed.",
            "No accuracy, benchmark, or production-behaviour claim follows from this artifact.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="C2C source-bound contract audit")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="execute the audit against a pinned checkout")
    run_parser.add_argument("--source-dir", required=True)
    run_parser.add_argument("--fixtures", default=FIXTURES_PATH)
    run_parser.add_argument("--write")
    run_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.command != "run":
        parser.error("unknown command")

    payload = run(args.source_dir, args.fixtures)
    if args.write:
        with open(args.write, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("source commit: %s" % payload["source"]["commit"])
        for row in payload["aligner"]["rows"]:
            first = row["strategies"]["first"]
            longest = row["strategies"]["longest"]
            print(
                "%-32s first=%-6r(%s) longest=%-6r(%s)"
                % (
                    row["id"],
                    first["selected_text"],
                    "keep" if first["criteria_met"] else "drop",
                    longest["selected_text"],
                    "keep" if longest["criteria_met"] else "drop",
                )
            )
        print("wrote: %s" % (args.write or "(stdout only)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
