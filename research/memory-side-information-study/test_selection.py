#!/usr/bin/env python3
"""Regression checks for the exact finite selection-channel witnesses."""
from __future__ import annotations

from fractions import Fraction as F
import json
from pathlib import Path
import unittest

from study import bayes_accuracy, conditional_entropy, marginal
from selection import (
    build_results,
    content_rows,
    identity_rows,
    select_from_c,
    select_from_z,
    synergy_rows,
)


def accuracies(case: dict) -> dict[str, F]:
    return {
        measurement["name"]: F(measurement["bayes_accuracy_exact"])
        for measurement in case["measurements"]
    }


def remap_delivery_ids(rows, mapping):
    id_fields = {"delivered_id_active", "delivered_id_control"}
    return [
        (
            {
                **world,
                **{
                    name: mapping[value]
                    for name, value in world.items()
                    if name in id_fields
                },
            },
            probability,
        )
        for world, probability in rows
    ]


class SelectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = build_results()
        cls.cases = {case["id"]: case for case in cls.result["cases"]}

    def test_declared_selector_view_rejects_missing_and_extra_observations(self):
        self.assertEqual(select_from_z({"Z": 1}), 1)
        self.assertEqual(select_from_c({"C": 0}), 0)
        with self.assertRaises(ValueError):
            select_from_z({})
        with self.assertRaises(ValueError):
            select_from_z({"Z": 1, "theta": 0})
        with self.assertRaises(ValueError):
            select_from_c({"C": 1, "E": 0})

    def test_declarations_make_selector_sources_explicit(self):
        self.assertEqual(
            self.cases["identity_channel"]["selector_observation"],
            "Z",
        )
        self.assertEqual(
            self.cases["relational_synergy"]["selector_observation"],
            "C",
        )
        self.assertEqual(
            self.cases["content_mediated_selection"]["selector_observation"],
            "Z",
        )
        self.assertIn("gold", self.result["selector_interface"]["does_not_receive"])

    def test_gold_and_error_are_not_on_the_policy_interface(self):
        for selector, name in (
            (select_from_z, "Z"),
            (select_from_c, "C"),
        ):
            for leaked_name in ("theta", "E", "gold"):
                with self.assertRaises(ValueError):
                    selector({name: 0, leaked_name: 1})

    def test_identity_control_has_expected_analytic_fractions(self):
        values = accuracies(self.cases["identity_channel"])
        self.assertEqual(values["labeled_message"], F(3, 4))
        self.assertEqual(values["payload_only"], F(1, 2))
        self.assertEqual(values["random_control_message"], F(1, 2))
        self.assertEqual(values["full_pool"], F(1, 2))
        self.assertEqual(values["full_pool_plus_selector_source"], F(3, 4))

    def test_synergy_is_joint_not_a_sum_of_marginal_accuracy(self):
        values = accuracies(self.cases["relational_synergy"])
        self.assertEqual(values["id_only"], F(1, 2))
        self.assertEqual(values["payload_only"], F(1, 2))
        self.assertEqual(values["labeled_message"], 1)
        self.assertGreater(
            values["labeled_message"],
            values["id_only"] + values["payload_only"] - F(1, 2),
        )
        information = self.cases["relational_synergy"]["information"]
        self.assertEqual(
            information["active_id_mutual_information_bits"], 0
        )
        self.assertEqual(
            information["id_conditional_information_given_payload_bits"], 1
        )

    def test_content_mediated_channel_survives_hidden_ids(self):
        values = accuracies(self.cases["content_mediated_selection"])
        self.assertEqual(values["identity_hidden_message"], F(3, 4))
        self.assertEqual(values["labeled_message"], F(3, 4))
        self.assertEqual(values["random_control_message"], F(1, 2))
        self.assertEqual(values["full_pool"], F(1, 2))
        self.assertEqual(values["full_pool_plus_selector_source"], F(3, 4))

    def test_all_selection_controls_are_exogenous(self):
        builders = (
            (identity_rows, "identity_channel"),
            (synergy_rows, "relational_synergy"),
            (content_rows, "content_mediated_selection"),
        )
        fair_theta_random = {
            (theta, random_id): F(1, 4)
            for theta in range(2)
            for random_id in range(2)
        }
        for builder, case_id in builders:
            rows, _, _ = builder()
            source_names = ("theta", "C", "X", "Y") if "C" in rows[0][0] else ("theta", "E", "Z")
            source_law = marginal(rows, source_names)
            self.assertEqual(marginal(rows, source_names + ("R",)), {
                values + (coin,): mass / 2
                for values, mass in source_law.items() for coin in (0, 1)
            }, case_id)
            self.assertEqual(
                marginal(rows, ("theta", "R")),
                fair_theta_random,
                case_id,
            )
            values = accuracies(self.cases[case_id])
            self.assertEqual(
                values["random_control_message"], F(1, 2), case_id
            )
            self.assertEqual(
                marginal(rows, ("theta", "delivered_id_control")),
                {
                    (theta, record_id): F(1, 4)
                    for theta in range(2)
                    for record_id in range(2)
                },
                case_id,
            )

    def test_payload_projection_matches_the_fixed_pool(self):
        identity, _, _ = identity_rows()
        for world, _ in identity:
            self.assertEqual(
                (world["pool_payload_0"], world["pool_payload_1"]),
                (0, 0),
            )
            self.assertEqual(world["delivered_payload_active"], 0)
            self.assertEqual(world["delivered_payload_control"], 0)

        content, _, _ = content_rows()
        for world, _ in content:
            self.assertEqual(
                (world["pool_payload_0"], world["pool_payload_1"]),
                (0, 1),
            )
            self.assertEqual(world["delivered_payload_active"], world["Z"])
            self.assertEqual(
                world["delivered_payload_control"],
                world["delivered_id_control"],
            )

        synergy, _, _ = synergy_rows()
        for world, _ in synergy:
            self.assertEqual(
                (world["pool_payload_0"], world["pool_payload_1"]),
                (world["X"], world["X"]),
            )
            self.assertEqual(world["delivered_payload_active"], world["X"])
            self.assertEqual(world["delivered_payload_control"], world["X"])

    def test_incorrect_control_payload_projection_is_detected(self):
        rows, _, _ = content_rows()
        correct = accuracies(self.cases["content_mediated_selection"])[
            "random_control_message"
        ]
        self.assertEqual(correct, F(1, 2))

        # The control must pair its random ID with that record's payload.
        # Accidentally reusing the active selector's payload leaks the active
        # selection channel into the supposedly independent control.
        active_payload = [
            (
                {
                    **world,
                    "delivered_payload_control":
                        world["delivered_payload_active"],
                },
                probability,
            )
            for world, probability in rows
        ]
        self.assertEqual(
            bayes_accuracy(
                rows,
                ("delivered_id_control", "delivered_payload_control"),
            ),
            correct,
        )
        self.assertEqual(
            bayes_accuracy(
                active_payload,
                ("delivered_id_control", "delivered_payload_control"),
            ),
            F(3, 4),
        )

    def test_random_control_differs_from_using_the_active_observation(self):
        for case_id in (
            "identity_channel",
            "relational_synergy",
            "content_mediated_selection",
        ):
            values = accuracies(self.cases[case_id])
            self.assertEqual(values["random_control_message"], F(1, 2))
            self.assertNotEqual(values["labeled_message"], F(1, 2))

    def test_irrelevant_noise_is_marginalized_in_synergy(self):
        rows, _, _ = synergy_rows()
        # Independent analytic law after summing the irrelevant noisy report.
        expected = {(theta, key, theta ^ key, coin): F(1, 8)
                    for theta in (0, 1) for key in (0, 1) for coin in (0, 1)}
        self.assertEqual(
            marginal(rows, ("theta", "C", "X", "R")),
            expected,
        )
        self.assertEqual(conditional_entropy(rows, ("C", "X")), 0.0)

    def test_extra_target_information_is_not_causal_selection_credit(self):
        for builder in (identity_rows, synergy_rows, content_rows):
            rows, _, _ = builder()
            with_gold = [
                ({**world, "gold": world["theta"]}, probability)
                for world, probability in rows
            ]
            self.assertEqual(
                bayes_accuracy(
                    with_gold,
                    (
                        "gold",
                        "delivered_id_active",
                        "delivered_payload_active",
                    ),
                ),
                1,
            )
            self.assertLess(
                bayes_accuracy(
                    rows,
                    ("pool_payload_0", "pool_payload_1"),
                ),
                1,
            )

    def test_missing_selector_source_is_not_equivalent_to_full_source(self):
        for case_id in (
            "identity_channel",
            "relational_synergy",
            "content_mediated_selection",
        ):
            values = accuracies(self.cases[case_id])
            self.assertEqual(values["full_pool"], F(1, 2), case_id)
            self.assertNotEqual(
                values["full_pool_plus_selector_source"],
                values["full_pool"],
                case_id,
            )

    def test_marking_active_choice_is_not_a_pool_only_observation(self):
        synergy = accuracies(self.cases["relational_synergy"])
        self.assertEqual(
            synergy["full_pool_with_selected_id_not_source"], 1
        )
        identity, _, _ = identity_rows()
        payload_only = bayes_accuracy(
            identity, ("delivered_payload_active",)
        )
        selected_id = bayes_accuracy(
            identity,
            ("pool_payload_0", "pool_payload_1", "delivered_id_active"),
        )
        self.assertEqual(payload_only, F(1, 2))
        self.assertEqual(selected_id, F(3, 4))

    def test_accidentally_available_gold_would_change_the_bound(self):
        rows, _, _ = identity_rows()
        leaked = [
            (
                {
                    "theta": world["theta"],
                    "delivered_id_active": world["delivered_id_active"],
                    "delivered_payload_active":
                        world["delivered_payload_active"],
                },
                probability,
            )
            for world, probability in rows
        ]
        labeled = bayes_accuracy(
            rows,
            ("delivered_id_active", "delivered_payload_active"),
        )
        self.assertEqual(labeled, F(3, 4))
        self.assertEqual(
            bayes_accuracy(
                leaked,
                (
                    "theta",
                    "delivered_id_active",
                    "delivered_payload_active",
                ),
            ),
            1,
        )

    def test_row_order_and_consistent_id_relabeling_preserve_bayes_value(self):
        for builder in (identity_rows, synergy_rows, content_rows):
            rows, _, _ = builder()
            observed = ("delivered_id_active", "delivered_payload_active")
            original = bayes_accuracy(rows, observed)
            self.assertEqual(
                bayes_accuracy(list(reversed(rows)), observed),
                original,
            )
            remapped = remap_delivery_ids(rows, {0: 1, 1: 0})
            self.assertEqual(
                bayes_accuracy(remapped, observed),
                original,
            )

    def test_stale_policy_aware_decoder_is_not_claimed_relabel_invariant(self):
        rows, _, _ = content_rows()
        remapped = remap_delivery_ids(rows, {0: 1, 1: 0})

        def stale_decoder(message):
            # Deliberately leave the decoder's learned ID meaning unchanged.
            return message["delivered_id_active"]

        original_accuracy = sum(
            probability
            for world, probability in rows
            if stale_decoder({"delivered_id_active": world["delivered_id_active"]}) == world["theta"]
        )
        stale_accuracy = sum(
            probability
            for world, probability in remapped
            if stale_decoder({"delivered_id_active": world["delivered_id_active"]}) == world["theta"]
        )
        self.assertEqual(original_accuracy, F(3, 4))
        self.assertEqual(stale_accuracy, F(1, 4))

    def test_dropping_identity_maps_to_named_control_by_case(self):
        value = self.result["cases"][0]["delivery_projection"]
        self.assertEqual(value["payload_only"], ["payload"])
        content = self.result["cases"][2]["delivery_projection"]
        self.assertEqual(content["identity_hidden"], ["payload=J"])

    def test_message_value_never_exceeds_full_pool_and_source(self):
        for case in self.result["cases"]:
            values = accuracies(case)
            bound = values["full_pool_plus_selector_source"]
            for name, value in values.items():
                if "message" in name or name in {"payload_only", "id_only"}:
                    self.assertLessEqual(
                        value,
                        bound,
                        (case["id"], name),
                    )

    def test_every_authored_world_is_retained_and_normalized(self):
        for case in self.result["cases"]:
            probabilities = [
                F(row["probability"]) for row in case["inputs"]
            ]
            self.assertEqual(sum(probabilities, F()), 1, case["id"])
            self.assertEqual(
                case["world_rows"],
                len(probabilities),
                case["id"],
            )
            self.assertTrue(
                case["rows_are_not_independent_samples"],
                case["id"],
            )
        self.assertEqual(self.result["edition"], "2026-11-07")

    def test_saved_results_match_recomputation(self):
        path = Path(__file__).with_name("selection-results.json")
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved, self.result)


if __name__ == "__main__":
    unittest.main()
