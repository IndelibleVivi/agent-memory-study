#!/usr/bin/env python3
"""Exact finite witnesses for information carried by record selection.

The selector receives only its declared observation. Record IDs, payloads and
the exogenous random-control coin are projected into explicit delivery views;
an ideal reader with the stipulated joint law chooses theta. Bayes accuracy is
delegated to ``study.py`` so there is one finite evaluator in this study.
"""
from __future__ import annotations

import argparse
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

try:
    from .study import bayes_accuracy, channels, conditional_entropy, marginal, measure
except ImportError:
    from study import bayes_accuracy, channels, conditional_entropy, marginal, measure


Record = tuple[int, int | str]
WorldRow = tuple[dict[str, int | str], F]


def _select(view: Mapping[str, int], declared_name: str) -> int:
    """Select from exactly one declared binary observation."""
    if set(view) != {declared_name}:
        raise ValueError(f"selector view must contain only {declared_name!r}")
    value = view[declared_name]
    if value not in (0, 1):
        raise ValueError(f"selector observation {declared_name!r} must be binary")
    return value


def select_from_z(view: Mapping[str, int]) -> int:
    return _select(view, "Z")


def select_from_c(view: Mapping[str, int]) -> int:
    return _select(view, "C")


def select_from_r(view: Mapping[str, int]) -> int:
    return _select(view, "R")


def deliver(pool: Sequence[Record], record_id: int) -> Record:
    """Return the selected record without accepting a scorer world."""
    matches = [record for record in pool if record[0] == record_id]
    if len(matches) != 1:
        raise ValueError("selector must choose exactly one known record")
    return matches[0]


def _with_delivery(
    rows: Iterable[WorldRow],
    pool: Sequence[Record],
    active: Callable[[Mapping[str, int]], int],
    active_name: str,
    control: Callable[[Mapping[str, int]], int],
) -> list[WorldRow]:
    projected = []
    for world, mass in rows:
        active_id, active_payload = deliver(
            pool, active({active_name: world[active_name]})
        )
        control_id, control_payload = deliver(pool, control({"R": world["R"]}))
        projected.append(({
            **world,
            "pool_payload_0": pool[0][1],
            "pool_payload_1": pool[1][1],
            "delivered_id_active": active_id,
            "delivered_payload_active": active_payload,
            "delivered_id_control": control_id,
            "delivered_payload_control": control_payload,
        }, mass))
    return projected


def identity_rows() -> tuple[list[WorldRow], list[Record], str]:
    pool = [(0, 0), (1, 0)]
    rows = []
    for theta, error, random_id in product(range(2), repeat=3):
        probability = F(1, 2) * (F(3, 4) if error == 0 else F(1, 4)) * F(1, 2)
        rows.append(({
            "theta": theta,
            "E": error,
            "Z": theta ^ error,
            "R": random_id,
        }, probability))
    return _with_delivery(rows, pool, select_from_z, "Z", select_from_r), pool, "Z"


def synergy_rows() -> tuple[list[WorldRow], str, str]:
    # ``channels`` retains the irrelevant Y. It is deliberately not projected
    # into either selector view, so partitioning marginalizes over it.
    rows = []
    for world, probability in channels(True):
        for random_id in range(2):
            rows.append(({**world, "R": random_id}, probability * F(1, 2)))

    projected = []
    for world, probability in rows:
        pool = [(0, world["X"]), (1, world["X"])]
        active_id, active_payload = deliver(
            pool, select_from_c({"C": world["C"]})
        )
        control_id, control_payload = deliver(
            pool, select_from_r({"R": world["R"]})
        )
        projected.append(({
            **world,
            "pool_payload_0": world["X"],
            "pool_payload_1": world["X"],
            "delivered_id_active": active_id,
            "delivered_payload_active": active_payload,
            "delivered_id_control": control_id,
            "delivered_payload_control": control_payload,
        }, probability))
    # The full pool is materialized per world as pool_payload_0/1 in inputs.
    return projected, "both records carry the same world-specific payload X", "C"


def content_rows() -> tuple[list[WorldRow], list[Record], str]:
    pool = [(0, 0), (1, 1)]
    rows = []
    for theta, error, random_id in product(range(2), repeat=3):
        probability = F(1, 2) * (F(3, 4) if error == 0 else F(1, 4)) * F(1, 2)
        rows.append(({
            "theta": theta,
            "E": error,
            "Z": theta ^ error,
            "R": random_id,
        }, probability))
    return _with_delivery(rows, pool, select_from_z, "Z", select_from_r), pool, "Z"


def _measurements(rows: Sequence[WorldRow], case: str) -> list[dict]:
    views = {
        "identity": (
            ("payload_only", ("delivered_payload_active",)),
            ("labeled_message", ("delivered_id_active", "delivered_payload_active")),
            (
                "random_control_message",
                ("delivered_id_control", "delivered_payload_control"),
            ),
            ("full_pool", ("pool_payload_0", "pool_payload_1")),
            (
                "full_pool_plus_selector_source",
                ("pool_payload_0", "pool_payload_1", "Z"),
            ),
        ),
        "synergy": (
            ("payload_only", ("delivered_payload_active",)),
            ("id_only", ("delivered_id_active",)),
            ("labeled_message", ("delivered_id_active", "delivered_payload_active")),
            (
                "random_control_message",
                ("delivered_id_control", "delivered_payload_control"),
            ),
            ("full_pool", ("pool_payload_0", "pool_payload_1")),
            (
                "full_pool_with_selected_id_not_source",
                ("pool_payload_0", "pool_payload_1", "delivered_id_active"),
            ),
            (
                "full_pool_plus_selector_source",
                ("pool_payload_0", "pool_payload_1", "C"),
            ),
        ),
        "content_mediated": (
            ("identity_hidden_message", ("delivered_payload_active",)),
            ("labeled_message", ("delivered_id_active", "delivered_payload_active")),
            (
                "random_control_message",
                ("delivered_id_control", "delivered_payload_control"),
            ),
            ("full_pool", ("pool_payload_0", "pool_payload_1")),
            (
                "full_pool_plus_selector_source",
                ("pool_payload_0", "pool_payload_1", "Z"),
            ),
        ),
    }
    return [
        {"name": name, **measure(rows, observed)}
        for name, observed in views[case]
    ]


def _input_rows(rows: Sequence[WorldRow]) -> list[dict]:
    return [
        {**world, "probability": str(probability)}
        for world, probability in rows
    ]


def _base_case(rows: Sequence[WorldRow], pool_kind: str) -> dict:
    return {
        "world_rows": len(rows),
        "candidate_pool_kind": pool_kind,
        "rows_are_not_independent_samples": True,
        "inputs": _input_rows(rows),
    }


def build_results() -> dict:
    identity, identity_pool, identity_source = identity_rows()
    synergy, synergy_pool, synergy_source = synergy_rows()
    content, content_pool, content_source = content_rows()
    all_rows = (identity, synergy, content)

    assert all(
        sum((probability for _, probability in rows), F()) == 1
        for rows in all_rows
    )

    identity_measurements = _measurements(identity, "identity")
    synergy_measurements = _measurements(synergy, "synergy")
    content_measurements = _measurements(content, "content_mediated")

    # Analytic controls, independent of saved JSON and enumeration order.
    identity_by_name = {
        measurement["name"]: F(measurement["bayes_accuracy_exact"])
        for measurement in identity_measurements
    }
    assert identity_by_name["labeled_message"] == F(3, 4)
    assert identity_by_name["payload_only"] == F(1, 2)
    assert identity_by_name["random_control_message"] == F(1, 2)
    assert identity_by_name["full_pool"] == F(1, 2)
    assert identity_by_name["full_pool_plus_selector_source"] == F(3, 4)

    synergy_by_name = {
        measurement["name"]: F(measurement["bayes_accuracy_exact"])
        for measurement in synergy_measurements
    }
    assert synergy_by_name["id_only"] == F(1, 2)
    assert synergy_by_name["payload_only"] == F(1, 2)
    assert synergy_by_name["labeled_message"] == 1
    assert synergy_by_name["random_control_message"] == F(1, 2)
    assert synergy_by_name["full_pool"] == F(1, 2)
    assert synergy_by_name["full_pool_with_selected_id_not_source"] == 1
    assert synergy_by_name["full_pool_plus_selector_source"] == 1

    content_by_name = {
        measurement["name"]: F(measurement["bayes_accuracy_exact"])
        for measurement in content_measurements
    }
    assert content_by_name["identity_hidden_message"] == F(3, 4)
    assert content_by_name["labeled_message"] == F(3, 4)
    assert content_by_name["random_control_message"] == F(1, 2)
    assert content_by_name["full_pool"] == F(1, 2)
    assert content_by_name["full_pool_plus_selector_source"] == F(3, 4)

    # R is independent of the entire pre-selection world, not just theta.
    for rows in all_rows:
        source_names = ("theta", "C", "X", "Y") if "C" in rows[0][0] else ("theta", "E", "Z")
        source_law = marginal(rows, source_names)
        assert marginal(rows, source_names + ("R",)) == {
            values + (coin,): mass / 2
            for values, mass in source_law.items() for coin in (0, 1)
        }

    # In the XOR case, Y is null for selection and delivery. Marginalizing it
    # leaves the relevant law unchanged.
    synergy_without_y = [
        (
            {name: value for name, value in world.items() if name != "Y"},
            probability,
        )
        for world, probability in synergy
    ]
    for names in (
        ("theta", "C", "X", "R"),
        ("theta", "delivered_id_active", "delivered_payload_active"),
        ("theta", "pool_payload_0", "pool_payload_1", "C"),
    ):
        assert marginal(synergy, names) == marginal(synergy_without_y, names)

    entropy_payload = conditional_entropy(
        synergy, ("delivered_payload_active",)
    )
    entropy_id = conditional_entropy(synergy, ("delivered_id_active",))
    entropy_message = conditional_entropy(
        synergy, ("delivered_id_active", "delivered_payload_active")
    )
    synergy_information = {
        "active_id_target_entropy_bits": round(entropy_id, 12),
        "active_id_mutual_information_bits": round(1 - entropy_id, 12),
        "id_conditional_information_given_payload_bits": round(
            entropy_payload - entropy_message, 12
        ),
        "payload_target_entropy_bits": round(entropy_payload, 12),
        "message_target_entropy_bits": round(entropy_message, 12),
    }
    assert synergy_information["active_id_mutual_information_bits"] == 0
    assert synergy_information["id_conditional_information_given_payload_bits"] == 1

    cases = [
        {
            "id": "identity_channel",
            "question": "Can a delivered identity carry the selector's observation?",
            "selector_observation": identity_source,
            "selector_policy": "J=Z",
            "candidate_pool": [
                {"id": record_id, "payload": payload}
                for record_id, payload in identity_pool
            ],
            "delivery_projection": {
                "labeled_message": ["J", "payload"],
                "payload_only": ["payload"],
                "random_control": "J=R",
            },
            "measurements": identity_measurements,
            **_base_case(identity, "two records with identical constant payload"),
        },
        {
            "id": "relational_synergy",
            "question": "Can a selected ID and fixed payload be useful only jointly?",
            "selector_observation": synergy_source,
            "selector_policy": "J=C",
            "candidate_pool": [
                {"id": 0, "payload": "X"},
                {"id": 1, "payload": "X"},
            ],
            "candidate_pool_note": (
                "Both candidate records carry the world's X, so payload alone "
                "is uninformative."
            ),
            "delivery_projection": {
                "labeled_message": ["J", "payload=X"],
                "id_only": ["J"],
                "payload_only": ["payload=X"],
                "random_control": "J=R",
            },
            "information": synergy_information,
            "measurements": synergy_measurements,
            "selected_id_information": (
                "Adding the one selected ID J=C to the pool recovers theta "
                "because X is also in the pool. J is marginally independent "
                "of theta but carries one bit conditional on X. A pool with "
                "the active choice marked is not the pool-only baseline."
            ),
            "full_pool_plus_selector_source_interpretation": (
                "The complete source includes C over and above the pool. "
                "The selected ID exactly encodes C in this stipulated policy. "
                "This equality is specific to J=C, not a general guarantee "
                "that a selection ID reveals every selector observation."
            ),
            **_base_case(synergy, "two records with identical payload X"),
        },
        {
            "id": "content_mediated_selection",
            "question": (
                "Does the selected payload preserve selection information "
                "after IDs are hidden?"
            ),
            "selector_observation": content_source,
            "selector_policy": "J=Z; deliver the record whose payload equals J",
            "candidate_pool": [
                {"id": record_id, "payload": payload}
                for record_id, payload in content_pool
            ],
            "delivery_projection": {
                "labeled_message": ["J", "payload=J"],
                "identity_hidden": ["payload=J"],
                "random_control": "J=R; payload=R",
            },
            "measurements": content_measurements,
            **_base_case(content, "two distinct fixed payloads 0 and 1"),
        },
    ]

    full_source_bound = []
    for case, measurements in zip(
        cases,
        (identity_measurements, synergy_measurements, content_measurements),
    ):
        values = {
            measurement["name"]: F(measurement["bayes_accuracy_exact"])
            for measurement in measurements
        }
        bound = values["full_pool_plus_selector_source"]
        message_names = [
            name
            for name in (
                "labeled_message",
                "payload_only",
                "identity_hidden_message",
                "id_only",
                "random_control_message",
            )
            if name in values
        ]
        assert all(values[name] <= bound for name in message_names)
        full_source_bound.append({
            "case": case["id"],
            "message_views": message_names,
            "full_source_accuracy_exact": str(bound),
            "holds": True,
        })

    return {
        "study": "memory-side-information-study",
        "measurement": "selection-channel-controls",
        "edition": "2026-11-07",
        "evidence_status": "executed-exact-finite-enumeration",
        "independent_validation": False,
        "scope": (
            "Authored finite distributions, stipulated deterministic selector "
            "policies and ideal Bayesian 0-1 decisions; no learned policy, "
            "model, retriever, natural-language reader, training, latency or "
            "human study."
        ),
        "assumptions": [
            "Theta is uniform and the reader uses the common prior.",
            (
                "The ideal reader knows the stipulated joint law and has no "
                "hidden additional inputs."
            ),
            (
                "The ideal reader knows each deterministic selection policy; "
                "a policy-unaware decoder need not realize this joint value."
            ),
            (
                "Bayes value means expected 0-1 accuracy maximized from each "
                "complete delivery view."
            ),
            (
                "Rows are weighted finite worlds and repeated control variants "
                "are not independent samples."
            ),
            (
                "Agreement with the stipulated joint law explains the ideal "
                "reader's value; it does not imply a language model learned "
                "the code or that the selector accessed theta directly."
            ),
        ],
        "selector_interface": {
            "receives": "exactly one declared binary observation",
            "does_not_receive": [
                "theta",
                "E",
                "gold",
                "the full scorer world",
                "reader side information",
            ],
            "selection_is_deterministic": True,
            "control_coin": "R is fair and independent of the pre-selection world variables",
        },
        "controls": {
            "probability_mass_exact": True,
            "analytic_values_verified": True,
            "exogenous_control_independence_verified": True,
            "irrelevant_Y_marginalized": True,
            "all_rows_retained": True,
            "full_source_bound_checked": True,
        },
        "full_source_bound": {
            "claim": (
                "Delivery Bayes accuracy <= pool plus selector-observation "
                "Bayes accuracy."
            ),
            "requires_common_reader_prior_and_no_extra_inputs": True,
            "cases": full_source_bound,
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(__file__).with_name("selection-results.json")
    data = build_results()
    if args.check:
        if json.loads(path.read_text(encoding="utf-8")) != data:
            raise SystemExit(
                "saved selection results differ from exact recomputation"
            )
        print(
            "memory-side-information-study: selection results and analytic "
            "controls match"
        )
    else:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            "wrote selection-results.json: three selection controls; "
            "no model execution"
        )


if __name__ == "__main__":
    main()
