"""Contract tests that execute the real C2C classes.

These import the actual ``TokenAligner`` and ``C2CProjector`` from a pinned
checkout of https://github.com/thu-nics/C2C and assert their behaviour directly.
They are the contract checks; ``audit.py run`` is the recorded receipt.

They need an interpreter with torch/transformers installed, for example:

    C2C_SOURCE_DIR=<checkout> \\
      /path/to/venv/bin/python -B -m unittest discover -s tests -p "test_*.py"

Without ``C2C_SOURCE_DIR`` every test skips instead of silently passing.
"""

import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_AUDIT_DIR = os.path.dirname(_HERE)
if _AUDIT_DIR not in sys.path:
    sys.path.insert(0, _AUDIT_DIR)

import audit  # noqa: E402

SOURCE_DIR = os.environ.get("C2C_SOURCE_DIR")
if SOURCE_DIR and SOURCE_DIR not in sys.path:
    sys.path.insert(0, SOURCE_DIR)

try:
    import torch
except ImportError:  # pragma: no cover - environment dependent
    torch = None

requires_source = unittest.skipUnless(
    SOURCE_DIR and os.path.isdir(SOURCE_DIR), "set C2C_SOURCE_DIR to the pinned checkout"
)
requires_env = unittest.skipUnless(
    SOURCE_DIR and os.path.isdir(SOURCE_DIR) and torch is not None,
    "needs the pinned checkout plus torch/transformers",
)


def _fixtures():
    with open(os.path.join(_AUDIT_DIR, "fixtures.json"), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _mocks():
    mocks = _fixtures()["tokenizer_mocks"]
    return audit.MockTokenizer(mocks["slm"]), audit.MockTokenizer(mocks["llm"])


@requires_source
class AlignerStrategyContract(unittest.TestCase):
    def setUp(self):
        from rosetta.model.aligner import AlignmentStrategy, TokenAligner

        self.TokenAligner = TokenAligner
        self.AlignmentStrategy = AlignmentStrategy
        self.slm, self.llm = _mocks()

    def _select(self, token_id, strategy):
        aligner = self.TokenAligner(
            slm_tokenizer=self.slm, llm_tokenizer=self.llm, strategy=strategy
        )
        aligned, mapping = aligner.align_tokens([token_id], return_mapping=True)
        return aligned[0], list(mapping[0][1])

    def test_constructor_default_is_first(self):
        aligner = self.TokenAligner(slm_tokenizer=self.slm, llm_tokenizer=self.llm)
        self.assertIs(aligner.strategy, self.AlignmentStrategy.FIRST)

    def test_first_takes_position_zero_and_longest_takes_longest(self):
        # F1: candidates are (" ", "not"); only longest keeps the negation lexeme.
        first, candidates = self._select(101, "first")
        longest, _ = self._select(101, "longest")
        self.assertEqual(candidates, [200, 202])
        self.assertEqual(self.llm.decode([first]), " ")
        self.assertEqual(self.llm.decode([longest]), "not")

    def test_longest_keeps_earliest_candidate_on_equal_lengths(self):
        # F2: candidates are ("20", "24"), equal length; the source uses a strict
        # '>' comparison, so the earliest candidate wins and no error is raised.
        first, candidates = self._select(102, "first")
        longest, _ = self._select(102, "longest")
        self.assertEqual(candidates, [203, 204])
        self.assertEqual(first, 203)
        self.assertEqual(longest, 203)
        self.assertEqual(self.llm.decode([longest]), "20")

    def test_one_to_one_mapping_ignores_strategy(self):
        first, candidates = self._select(100, "first")
        longest, _ = self._select(100, "longest")
        self.assertEqual(candidates, [207])
        self.assertEqual(first, longest)

    def test_negation_before_trailing_space_survives_both_strategies(self):
        for strategy in ("first", "longest"):
            selected, candidates = self._select(103, strategy)
            self.assertEqual(candidates, [202, 200])
            self.assertEqual(self.llm.decode([selected]), "not")

    def test_special_token_takes_mapping_branch_not_strategy(self):
        aligned, mapping = self.TokenAligner(
            slm_tokenizer=self.slm, llm_tokenizer=self.llm, strategy="longest"
        ).align_tokens([self.slm.eos_token_id], return_mapping=True)
        self.assertEqual(aligned, [self.llm.eos_token_id])
        self.assertEqual(list(mapping[0][1]), [self.llm.eos_token_id])

    def test_unknown_strategy_string_is_rejected(self):
        with self.assertRaises(ValueError):
            self.TokenAligner(slm_tokenizer=self.slm, llm_tokenizer=self.llm, strategy="prefix")


@requires_env
class ProjectorGateContract(unittest.TestCase):
    def setUp(self):
        from rosetta.model.projector import C2CProjector

        torch.manual_seed(20260918)
        self.projector = C2CProjector(
            source_dim=8,
            target_dim=6,
            source_num_heads=1,
            target_num_heads=1,
            intermediate_dim=16,
            hidden_dim=16,
            num_layers=3,
            dropout=0.1,
        )
        self.projector.eval()
        self.source = (torch.randn(1, 1, 4, 8), torch.randn(1, 1, 4, 8))
        self.target = (torch.randn(1, 1, 4, 6), torch.randn(1, 1, 4, 6))

    def test_default_logits_close_the_gate_to_exact_identity(self):
        out_key, out_value = self.projector(self.source, self.target)
        self.assertTrue(torch.equal(out_key, self.target[0]))
        self.assertTrue(torch.equal(out_value, self.target[1]))

    def test_gate_threshold_is_strictly_greater_than_zero(self):
        self.projector.key_gate_logit.data.fill_(0.0)
        closed, _ = self.projector(self.source, self.target)
        self.assertTrue(torch.equal(closed, self.target[0]))
        self.projector.key_gate_logit.data.fill_(1e-6)
        opened, _ = self.projector(self.source, self.target)
        self.assertFalse(torch.equal(opened, self.target[0]))

    def test_added_term_comes_only_from_the_projection_path(self):
        self.projector.key_gate_logit.data.fill_(1.0)
        self.projector.value_gate_logit.data.fill_(1.0)
        opened, _ = self.projector(self.source, self.target)
        self.assertFalse(torch.equal(opened, self.target[0]))
        for module in (self.projector.key_proj_out, self.projector.value_proj_out):
            torch.nn.init.zeros_(module.weight)
            torch.nn.init.zeros_(module.bias)
        zeroed_key, zeroed_value = self.projector(self.source, self.target)
        self.assertTrue(torch.equal(zeroed_key, self.target[0]))
        self.assertTrue(torch.equal(zeroed_value, self.target[1]))

    def test_temperature_anneals_from_initial_to_final(self):
        self.projector.update_temperature(0)
        self.assertAlmostEqual(float(self.projector.gate_temperature), 1.0, places=6)
        self.projector.update_temperature(self.projector.anneal_steps)
        self.assertAlmostEqual(float(self.projector.gate_temperature), 0.001, places=6)
        self.projector.update_temperature(10 ** 7)
        self.assertAlmostEqual(float(self.projector.gate_temperature), 0.001, places=6)

    def test_rejects_fewer_than_three_layers(self):
        from rosetta.model.projector import C2CProjector

        with self.assertRaises(AssertionError):
            C2CProjector(
                source_dim=8, target_dim=6, intermediate_dim=16, hidden_dim=16, num_layers=2
            )


@requires_source
class SourceBindingContract(unittest.TestCase):
    def test_checkout_matches_the_registered_commit(self):
        head = audit.git(SOURCE_DIR, "rev-parse", "HEAD")
        self.assertEqual(head, audit.PINNED_COMMIT)

    def test_shipped_training_recipe_freezes_both_models(self):
        path = os.path.join(SOURCE_DIR, "recipe/train_recipe/C2C_0.6+0.5.json")
        with open(path, "r", encoding="utf-8") as handle:
            recipe = json.load(handle)
        self.assertGreaterEqual(set(recipe["training"]["freeze"]), {"base", "teacher"})
        self.assertEqual(recipe["model"]["projector"]["type"], "C2CProjector")


if __name__ == "__main__":
    unittest.main()
