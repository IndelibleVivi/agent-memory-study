"""Behavioral checks for the finite v1 combination-transfer diagnostic."""
import copy
import itertools
import json
from pathlib import Path
import unittest

import support_audit
import transfer

ROOT = Path(__file__).parent
GLOBAL_PRIORITIES = {
    "scope-first": ("irrelevant", "harmful", "redundant", "useful"),
    "hazard-first": ("harmful", "irrelevant", "redundant", "useful"),
}


class TransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ROOT / "fixtures.json").read_text())
        cls.result = transfer.report()
        cls.arms = transfer.build_arms(cls.fixture)
        cls.test, cls.positives, cls.neighbors = transfer.build_test(cls.fixture)
        cls.saved = json.loads((ROOT / "transfer-results.json").read_text())

    def test_protocol_and_source_identity(self):
        keys = {
            "fixture_build.py", "study.py", "fixtures.json", "results.json",
            "support_audit.py", "support-results.json", "transfer.py",
            "transfer-protocol.md",
        }
        self.assertEqual(set(self.result["source_sha256"]), keys)
        self.assertEqual(
            self.result["source_sha256"]["transfer-protocol.md"],
            transfer.PROTOCOL_SHA256,
        )
        self.assertEqual(
            self.result["source_sha256"]["transfer.py"],
            transfer.sha256(ROOT / "transfer.py"),
        )

    def test_saved_receipt_recomputes(self):
        saved = copy.deepcopy(self.saved)
        saved.pop("execution", None)
        self.assertEqual(saved, self.result)

    def test_original_study_inputs_remain_valid(self):
        self.assertIn("ams-decision-results/2", (ROOT / "results.json").read_text())
        self.assertIn("ams-structured-support-audit/1", (ROOT / "support-results.json").read_text())
        self.assertEqual(
            {tuple(transfer.original.vector(r)) for r in
             transfer.original.rows_for(self.fixture, "train") if transfer.original.vector(r)[9] == 0},
            {tuple(row) for row in self.result["arms"]["filtered-original"]["training_vectors"]},
        )

    def test_train_and_test_vectors_are_disjoint_and_all_test_vectors_present(self):
        vectors = [tuple(row) for row in self.result["arms"]["filtered-original"]["training_vectors"]]
        test_vectors = [tuple(row["vector"]) for row in self.result["cases"]]
        self.assertEqual(len(test_vectors), 512)
        self.assertEqual(
            set(test_vectors),
            {x for x in itertools.product((0, 1), repeat=10) if x[9]},
        )
        self.assertTrue(set(vectors).isdisjoint(test_vectors))
        self.assertEqual(self.result["split"]["overlap"], 0)
        self.assertEqual(self.result["split"]["useful_test_vectors"], [list(x) for x in self.positives])

    def test_required_neighbors_are_present_harmful_and_distance_one(self):
        for vector, neighbors in self.neighbors.items():
            self.assertEqual(set(neighbors), {"missing-prerequisite", "expired", "side-effect", "verified"})
            for name, neighbor in neighbors.items():
                self.assertEqual(neighbor["distance"], 1)
                self.assertEqual(neighbor["label"], "useful" if name == "verified" else "harmful")
                self.assertIn(list(neighbor["vector"]), [row["vector"] for row in self.result["cases"]])
        self.assertEqual(len(self.positives), 2)
        self.assertEqual(sum(row["label_v1"] == "useful" for row in self.result["cases"]), 2)

    def test_arms_have_equal_counts_and_histograms(self):
        base = self.arms["filtered-original"]
        for name in ("balanced-repeats", "balanced-counterexamples"):
            arm = self.arms[name]
            self.assertEqual(len(arm["added"]), 32)
            self.assertEqual(len(arm["training"]), len(base["training"]) + 32)
            self.assertEqual(
                {label: sum(row["expected"] == label for row in arm["added"]) for label in transfer.LABELS},
                {label: 8 for label in transfer.LABELS},
            )
            self.assertLessEqual({tuple(transfer.original.vector(r)) for r in arm["added"]},
                                 {tuple(r) for r in self.result["arms"][name]["training_vectors"]})

    def test_split_unique_counts_are_derived_from_their_named_collections(self):
        base = self.result["arms"]["filtered-original"]["training_vectors"]
        all_training = {
            tuple(row)
            for arm in self.result["arms"].values()
            for row in arm["training_vectors"]
        }
        self.assertEqual(len(base), 144)
        self.assertEqual(len({tuple(row) for row in base}), 18)
        self.assertEqual(self.result["split"]["training_rows"], 144)
        self.assertEqual(self.result["split"]["training_unique_vectors"], 18)
        self.assertEqual(self.result["split"]["all_arm_union_unique_vectors"], len(all_training))

    def test_counterexample_selection_uses_sensitive_zero_and_declared_priority(self):
        arm = self.arms["balanced-counterexamples"]
        support = {tuple(transfer.original.vector(r)) for r in self.arms["filtered-original"]["training"]}
        self.assertTrue(all(transfer.original.vector(r)[9] == 0 for r in arm["added"]))
        expected = []
        pool = [
            support_audit.construct(x, i, transfer.original)
            for i, x in enumerate(itertools.product((0, 1), repeat=10))
            if x[9] == 0
        ]
        for label in transfer.LABELS:
            rows = [row for row in pool if row["expected"] == label]
            rows.sort(key=lambda row: (
                tuple(transfer.original.vector(row)) in support,
                tuple(transfer.original.vector(row)),
            ))
            expected.extend(
                tuple(transfer.original.vector(rows[i % len(rows[:8])]))
                for i in range(8)
            )
        self.assertEqual(
            [tuple(transfer.original.vector(row)) for row in arm["added"]],
            expected,
        )

    def test_v2_boundary_is_not_claimed_as_v1_rule_success(self):
        self.assertEqual(self.result["v2_scope"]["changed"], 1)
        self.assertEqual(self.result["v2_scope"]["preserved"], 511)
        self.assertEqual(self.result["v2_scope"]["boundary"], 1)
        self.assertTrue(self.result["v2_scope"]["boundary_subset_of_preserved"])
        self.assertEqual(self.result["v2_scope"]["changed"], 1)
        self.assertEqual(self.result["split"]["sensitive_training_rows_used"], 0)
        self.assertEqual(self.result["split"]["identifiability"]["sensitive_flip_pairs"], 0)
        mismatch = self.result["metrics_v2_policy_mismatch"]
        self.assertIn("no v2 fitting", mismatch["status"])
        for name, scopes in mismatch["methods"].items():
            self.assertEqual(scopes["changed"]["n"], 1, name)
            self.assertEqual(scopes["preserved"]["n"], 511, name)
            self.assertEqual(scopes["boundary"]["n"], 1, name)
            for scope in ("changed", "preserved", "boundary"):
                self.assertIn("class_correct", scopes[scope], name)
                self.assertIn("selection", scopes[scope], name)

    def test_verified_flips_are_complete_and_oracle_v1_is_invariant(self):
        flips = self.result["verified_flips"]["oracle-v1"]
        self.assertEqual(flips["pairs"], 256)
        self.assertEqual(flips["class_changes"], 0)
        self.assertEqual(flips["selection_changes"], 0)
        for name, summary in self.result["verified_flips"].items():
            self.assertEqual(summary["pairs"], 256, name)

    def test_tie_envelope_distinguishes_cases_and_named_orders(self):
        report = self.result["tie_report"]
        self.assertEqual(report["kind"], "per-case independent minima over all nearest-row classes")
        self.assertTrue(report["warning"].startswith("Independent per-case"))
        self.assertTrue(report["named_orders_are_not_global_extrema"])
        self.assertEqual(len(report["per_case"]), 512)
        self.assertLessEqual(report["class_correct_worst"], report["class_correct_best"])
        self.assertLessEqual(report["utility_worst"], report["utility_best"])
        self.assertIn("scope-first", report["named_finite_orders"])
        self.assertIn("hazard-first", report["named_finite_orders"])
        self.assertNotEqual(
            report["named_finite_orders"]["scope-first"]["metrics"]["class_correct"],
            report["named_finite_orders"]["hazard-first"]["metrics"]["class_correct"],
        )
        self.assertEqual(report["priority_tie_controls"]["scope-first"]["priority"], list(GLOBAL_PRIORITIES["scope-first"]))
        self.assertEqual(report["priority_tie_controls"]["hazard-first"]["priority"], list(GLOBAL_PRIORITIES["hazard-first"]))
        self.assertEqual(
            report["named_finite_orders"]["scope-first"]["metrics"],
            report["priority_tie_controls"]["scope-first"]["metrics"],
        )
        self.assertEqual(
            report["named_finite_orders"]["hazard-first"]["metrics"],
            report["priority_tie_controls"]["hazard-first"]["metrics"],
        )
        for arm_name in ("filtered-original", "balanced-repeats", "balanced-counterexamples"):
            train = self.arms[arm_name]["training"]
            modes = transfer.make_modes()
            for mode_name, priority in GLOBAL_PRIORITIES.items():
                ordered = modes[mode_name](train)
                ordered_prediction = transfer.original.episodic(ordered, self.test)
                tied_prediction = []
                details = transfer.nearest_details(train, self.test)
                ranks = {label: priority.index(label) for label in transfer.LABELS}
                for detail in details:
                    tied_prediction.append(min(detail["tied_classes"], key=ranks.__getitem__))
                self.assertEqual(ordered_prediction, tied_prediction, (arm_name, mode_name))

    def test_selection_metrics_have_explicit_denominators(self):
        metrics = self.result["metrics_v1"]
        for name, metric in metrics.items():
            selection = metric["selection"]
            self.assertEqual(selection["useful_recall"]["n"], 2, name)
            self.assertEqual(selection["harmful_false_injection"]["n"], 60, name)
            self.assertEqual(selection["other_false_injection"]["n"], 450, name)
            self.assertEqual(metric["n"], 512)
        self.assertEqual(metrics["oracle-v1"]["class_accuracy"], 1.0)
        self.assertEqual(metrics["constant-reject"]["selection"]["selected"], 0)

    def test_validation_only_uses_sensitive_zero_rows(self):
        rows = [
            row for row in transfer.original.rows_for(self.fixture, "validation")
            if transfer.original.vector(row)[9] == 0
        ]
        self.assertEqual(len(rows), self.result["validation_sensitive_zero"]["rows"])
        self.assertTrue(all(transfer.original.vector(row)[9] == 0 for row in rows))

    def test_check_rejects_receipt_drift(self):
        broken = copy.deepcopy(self.saved)
        broken["cases"][0]["label_v1"] = "wrong"
        broken.pop("execution", None)
        with self.assertRaises(AssertionError):
            self.assertEqual(broken, self.result)

        bad_split = copy.deepcopy(self.saved)
        bad_split["split"]["overlap"] = 1
        bad_split.pop("execution", None)
        with self.assertRaises(AssertionError):
            self.assertEqual(bad_split, self.result)

        bad_arm = copy.deepcopy(self.saved)
        bad_arm["arms"]["balanced-repeats"]["support"]["added_rows"] = 31
        bad_arm.pop("execution", None)
        with self.assertRaises(AssertionError):
            self.assertEqual(bad_arm, self.result)

        bad_tie = copy.deepcopy(self.saved)
        bad_tie["tie_report"]["utility_best"] = -125
        bad_tie.pop("execution", None)
        with self.assertRaises(AssertionError):
            self.assertEqual(bad_tie, self.result)

        source = copy.deepcopy(self.saved)
        source["source_sha256"]["study.py"] = "0" * 64
        source.pop("execution", None)
        with self.assertRaises(AssertionError):
            self.assertEqual(source["source_sha256"], self.result["source_sha256"])


if __name__ == "__main__":
    unittest.main()
