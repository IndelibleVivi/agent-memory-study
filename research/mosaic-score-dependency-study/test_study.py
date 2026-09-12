"""Behavior checks for score dependencies, using hand-derived expectations."""

import copy
import json
import unittest

from study import ROOT, graph_dirty, run


class ScoreDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads((ROOT / "fixtures.json").read_text())
        cls.result = run(cls.inputs)
        cls.rows = {row["id"]: row for row in cls.result["cases"]}

    def test_remote_denominator_changes_score_and_choice(self):
        r = self.rows["remote-max-change"]
        self.assertEqual(r["graph_dirty_nodes"], ["c", "d"])
        self.assertEqual(r["before_scores"]["a"], "27/40")
        self.assertEqual(r["treatments"]["full"]["scores"]["a"], "19/40")
        self.assertEqual(r["treatments"]["graph-dirty"]["selected"], "a")
        self.assertEqual(r["treatments"]["full"]["selected"], "c")

    def test_same_choice_does_not_hide_stale_score(self):
        r = self.rows["remote-frontier-exit"]
        self.assertEqual(r["after_frontier"], ["a"])
        self.assertEqual(r["treatments"]["full"]["scores"]["a"], "31/40")
        self.assertEqual(r["treatments"]["graph-dirty"]["stale_nodes"], ["a"])
        self.assertTrue(r["treatments"]["graph-dirty"]["matches_full_choice"])

    def test_previous_community_is_context_not_entity_mutation(self):
        r = self.rows["previous-community-change"]
        self.assertEqual(r["changed_nodes"], [])
        self.assertEqual(r["treatments"]["full"]["scores"], {"a": "19/40", "c": "31/40"})
        self.assertEqual(r["treatments"]["graph-dirty"]["selected"], "a")
        self.assertEqual(r["treatments"]["full"]["selected"], "c")

    def test_local_positive_and_irrelevant_controls(self):
        r = self.rows["own-nonmax-change"]
        self.assertEqual(r["treatments"]["graph-dirty"]["scores"]["a"], "23/40")
        for name in ("own-nonmax-change", "distant-nonmax-change", "no-change", "previous-same-community"):
            r = self.rows[name]
            self.assertFalse(r["global_context_changed"])
            self.assertTrue(r["treatments"]["graph-dirty"]["matches_full_scores"])
        for name in ("no-change", "previous-same-community"):
            self.assertEqual(self.rows[name]["treatments"]["dependency-aware"]["rescored"], [])

    def test_unlock_rebuilds_frontier_before_scoring(self):
        for name in ("prerequisite-unlock-max", "prerequisite-unlock-nonmax"):
            r = self.rows[name]
            self.assertEqual(r["before_frontier"], ["a", "d"])
            self.assertEqual(r["after_frontier"], ["a", "c"])
            self.assertIn("c", r["treatments"]["graph-dirty"]["rescored"])
        self.assertFalse(self.rows["prerequisite-unlock-max"]["treatments"]["graph-dirty"]["matches_full_choice"])
        self.assertTrue(self.rows["prerequisite-unlock-nonmax"]["treatments"]["graph-dirty"]["matches_full_scores"])

    def test_dependency_aware_matches_all_exact_scores(self):
        self.assertEqual(self.result["summary"]["after_state_treatments"], 27)
        for row in self.result["cases"]:
            self.assertEqual(row["treatments"]["dependency-aware"]["scores"], row["treatments"]["full"]["scores"])
            self.assertEqual(row["treatments"]["dependency-aware"]["ranking"], row["treatments"]["full"]["ranking"])

    def test_invalidation_follows_consumers_not_predecessors(self):
        before = {"nodes": {v: 0 for v in "abc"}}
        after = {"nodes": {"a": 0, "b": 1, "c": 0}}
        changed, dirty = graph_dirty({"association_edges": [], "prerequisites": [["a", "b"], ["b", "c"]]}, before, after)
        self.assertEqual(changed, {"b"})
        self.assertEqual(dirty, {"b", "c"})

    def test_inputs_unchanged_and_repeatable(self):
        before = copy.deepcopy(self.inputs)
        self.assertEqual(run(self.inputs), self.result)
        self.assertEqual(self.inputs, before)


if __name__ == "__main__":
    unittest.main()
