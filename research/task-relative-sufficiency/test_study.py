"""Discriminating finite witnesses, including a non-pairwise obstruction."""

from copy import deepcopy
import unittest

import study


class SufficiencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = study.load_fixtures()
        cls.worlds = study.make_worlds(cls.fixture)
        cls.result = study.run(cls.fixture)

    def test_future_questions_break_current_compatibility_without_new_events(self):
        projection = self.result["projection_results"]["current-summary"]
        self.assertTrue(projection["families"]["current"]["all_classes_compatible"])
        self.assertFalse(projection["families"]["later_semantic"]["all_classes_compatible"])
        self.assertEqual(projection["observation_classes"], 2)
        witness = next(check["minimum_empty_intersection_witness"]
                       for cell in projection["classes"] for check in cell["task_checks"]
                       if check["query"] == "old_format")
        by_id = {world["audit_id"]: world for world in self.worlds}
        left, right = (by_id[key] for key in witness)
        self.assertEqual(study.current_summary(left["events"]), study.current_summary(right["events"]))
        self.assertNotEqual(study.acceptable_answers(left, "old_format"), study.acceptable_answers(right, "old_format"))

    def test_compressed_positive_control_retains_semantics_but_not_verbatim_form(self):
        projection = self.result["projection_results"]["scoped-relations"]
        self.assertLess(projection["observation_classes"], len(self.worlds))
        self.assertTrue(projection["families"]["later_semantic"]["all_classes_compatible"])
        self.assertFalse(projection["families"]["later_with_wording"]["all_classes_compatible"])

    def test_pairwise_overlap_is_not_global_compatibility(self):
        control = self.result["set_valued_control"]
        self.assertTrue(control["all_pairs_overlap"])
        check = control["classes"][0]["task_checks"][0]
        self.assertFalse(check["compatible"])
        self.assertEqual(len(check["minimum_empty_intersection_witness"]), 3)
        for pair in control["pairs"]:
            self.assertTrue(pair["common_acceptable_answers"])

    def test_deterministic_postprocessing_preserves_the_collision(self):
        before = self.result["projection_results"]["current-summary"]
        after = self.result["projection_results"]["expanded-summary"]
        self.assertEqual(before["families"], after["families"])
        self.assertTrue(all(self.result["refinement_checks"].values()))

    def test_each_missing_source_condition_preserves_future_ambiguity(self):
        accesses = self.result["source_access"]
        self.assertTrue(accesses["all-gates-pass"]["families"]["later_with_wording"]["all_classes_compatible"])
        for gate in self.fixture["source_gates"]:
            with self.subTest(gate=gate):
                analysis = accesses[f"failed-{gate}"]
                self.assertFalse(analysis["families"]["later_semantic"]["all_classes_compatible"])
                self.assertTrue(all(cell["observation"]["source"] is None for cell in analysis["classes"]))

    def test_audit_identity_is_not_subject_information(self):
        world = deepcopy(self.worlds[0])
        changed = deepcopy(world)
        changed["audit_id"] = "a-hash-or-locator-would-not-be-evidence"
        changed["evaluation_answer"] = "unavailable-to-subject"
        for projection in study.PROJECTIONS.values():
            self.assertEqual(projection(world["events"]), projection(changed["events"]))
        forbidden = ("audit_id", "evaluation_answer", "world-", "sha256", "locator")
        for projection in study.PROJECTIONS.values():
            encoded = study.canonical(projection(world["events"]))
            self.assertFalse(any(token in encoded for token in forbidden))

    def test_order_does_not_change_cell_analysis(self):
        observer = lambda world: study.scoped_relations(world["events"])
        forward = study.analyze_projection(self.worlds, observer, self.fixture["query_families"])
        reverse = study.analyze_projection(list(reversed(self.worlds)), observer, self.fixture["query_families"])
        self.assertEqual(forward, reverse)

    def test_answer_contract_is_recomputed_not_encoded_in_success_flags(self):
        worlds = deepcopy(self.fixture["set_valued_control"]["worlds"])
        for world in worlds:
            world["recorded_routes"].append("shared-new-route")
        cells = study.evaluate_cells(worlds, lambda world: {"same_view": True}, ["choose-one-route"],
                                     lambda world, query: set(world["recorded_routes"]))
        check = cells[0]["task_checks"][0]
        self.assertTrue(check["compatible"])
        self.assertEqual(check["common_acceptable_answers"], ["shared-new-route"])

    def test_no_universal_abstention_and_no_individually_impossible_tasks(self):
        for world in self.worlds:
            for query in study.QUESTIONS:
                self.assertNotIn("abstain", study.acceptable_answers(world, query))
        with self.assertRaisesRegex(ValueError, "individually impossible"):
            study.evaluate_cells(self.worlds[:1], lambda world: {}, ["x"], lambda world, query: set())


if __name__ == "__main__":
    unittest.main()
