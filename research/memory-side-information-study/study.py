#!/usr/bin/env python3
"""Exact finite information-channel witnesses; no learned reader or provider.

The distribution, signal definitions, and fixed observation sets are authored
controls. Bayes value is computed by partitioning worlds by observable inputs.
No answer labels enter a retrieval/selection policy: there is no fitted policy.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from fractions import Fraction as F
from itertools import combinations, product
import json
from math import log2
from pathlib import Path


def channels(coupled: bool):
    """theta, key and noise are independent; X may depend on key."""
    rows = []
    for theta, key, error in product(range(2), repeat=3):
        mass = F(1, 4) * (F(3, 4) if error == 0 else F(1, 4))
        if coupled:
            rows.append(({"theta": theta, "C": key, "X": theta ^ key,
                          "Y": theta ^ error}, mass))
        else:
            for uninformative in range(2):
                rows.append(({"theta": theta, "C": key, "X": uninformative,
                              "Y": theta ^ error}, mass / 2))
    return rows


def noisy_reports(duplicate: bool = False):
    rows = []
    for theta, e1, e2, e3 in product(range(2), repeat=4):
        mass = F(1, 2)
        for error in (e1, e2, e3):
            mass *= F(3, 4) if error == 0 else F(1, 4)
        rows.append(({"theta": theta, "N1": theta ^ e1,
                      "N2": theta ^ (e1 if duplicate else e2),
                      "N3": theta ^ e3}, mass))
    return rows


def partition(rows, observed):
    cells = defaultdict(lambda: defaultdict(F))
    for world, mass in rows:
        cells[tuple(world[name] for name in observed)][world["theta"]] += mass
    return cells


def bayes_accuracy(rows, observed):
    return sum((max(cell.values()) for cell in partition(rows, observed).values()), F())


def conditional_entropy(rows, observed):
    total = 0.0
    for cell in partition(rows, observed).values():
        mass = sum(cell.values(), F())
        total += float(mass) * -sum(float(p / mass) * log2(float(p / mass))
                                   for p in cell.values() if p)
    return total


def marginal(rows, names):
    distribution = defaultdict(F)
    for world, mass in rows:
        distribution[tuple(world[name] for name in names)] += mass
    return dict(distribution)


def measure(rows, observed):
    accuracy = bayes_accuracy(rows, observed)
    return {"observed": list(observed), "bayes_accuracy_exact": str(accuracy),
            "bayes_accuracy": float(accuracy),
            "conditional_entropy_bits": round(conditional_entropy(rows, observed), 12)}


def build_results():
    coupled, independent = channels(True), channels(False)
    reports, copies = noisy_reports(), noisy_reports(True)
    all_rows = (coupled, independent, reports, copies)
    assert all(sum((p for _, p in rows), F()) == 1 for rows in all_rows)
    # Distinct authored worlds have exactly equal all one- and two-variable
    # marginals on theta/C/X. Their three-variable law is different.
    marginal_sets = [names for k in (1, 2)
                     for names in combinations(("theta", "C", "X"), k)]
    marginal_checks = {"/".join(names): marginal(coupled, names) == marginal(independent, names)
                       for names in marginal_sets}
    assert all(marginal_checks.values())
    assert marginal(coupled, ("theta", "C", "X")) != marginal(independent, ("theta", "C", "X"))
    # Analytic controls, independent of enumeration order and dictionary keys.
    assert bayes_accuracy(coupled, ("X",)) == F(1, 2)
    assert bayes_accuracy(coupled, ("Y",)) == F(3, 4)
    assert bayes_accuracy(coupled, ("C", "X")) == 1
    assert bayes_accuracy(coupled, ("C", "Y")) == F(3, 4)
    assert bayes_accuracy(independent, ("C", "X")) == F(1, 2)
    assert bayes_accuracy(reports, ("N1", "N2")) == F(3, 4)
    assert bayes_accuracy(reports, ("N1", "N2", "N3")) == F(27, 32)
    assert conditional_entropy(reports, ("N1", "N2")) < conditional_entropy(reports, ("N1",))
    assert conditional_entropy(copies, ("N1", "N2")) == conditional_entropy(copies, ("N1",))
    # Order of input rows and order of delivered variables do not alter the
    # ideal-reader result. This is a mathematical control, not an LLM claim.
    assert bayes_accuracy(list(reversed(coupled)), ("X", "C")) == 1
    for rows, variables in ((coupled, ("C", "X", "Y")), (reports, ("N1", "N2", "N3"))):
        for size in range(len(variables) + 1):
            for subset in combinations(variables, size):
                for extra in variables:
                    if extra not in subset:
                        assert bayes_accuracy(rows, subset + (extra,)) >= bayes_accuracy(rows, subset)
    return {
        "study": "memory-side-information-study", "edition": "2026-11-05",
        "evidence_status": "executed-exact-finite-enumeration",
        "independent_validation": False,
        "scope": "Authored finite distributions and ideal Bayesian 0-1 decisions; no model, retrieval engine, training, latency, natural-language or human study.",
        "rank_reversal": {
            "world_rows": len(coupled),
            "measurements": [measure(coupled, s) for s in ((), ("C",), ("X",), ("Y",), ("C", "X"), ("C", "Y"))],
            "incremental_accuracy_without_C": {"X": "0", "Y": "1/4"},
            "incremental_accuracy_with_C": {"X": "1/2", "Y": "1/4"},
        },
        "marginally_indistinguishable_control": {
            "world_rows": len(independent), "equal_marginals": marginal_checks,
            "joint_theta_C_X_equal": False,
            "measurements": [measure(independent, s) for s in (("X",), ("C", "X"), ("C", "Y"))],
        },
        "information_without_action_accuracy_gain": {
            "world_rows": len(reports),
            "measurements": [measure(reports, s) for s in ((), ("N1",), ("N1", "N2"), ("N1", "N2", "N3"))],
            "second_report_conditional_information_bits": round(conditional_entropy(reports, ("N1",)) - conditional_entropy(reports, ("N1", "N2")), 12),
            "duplicate_control": measure(copies, ("N1", "N2")),
        },
        "controls": {"probability_mass_exact": True, "analytic_values_verified": True,
                     "variable_order_invariance": True, "ideal_reader_information_monotonicity": True},
        "inputs": {"coupled": [{**w, "probability": str(p)} for w, p in coupled],
                   "independent": [{**w, "probability": str(p)} for w, p in independent],
                   "independent_reports": [{**w, "probability": str(p)} for w, p in reports],
                   "duplicate_reports": [{**w, "probability": str(p)} for w, p in copies]},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(__file__).with_name("results.json")
    data = build_results()
    if args.check:
        if json.loads(path.read_text(encoding="utf-8")) != data:
            raise SystemExit("saved results differ from exact recomputation")
        print("memory-side-information-study: exact results and analytic controls match")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("wrote results.json: three authored finite witnesses; no model execution")


if __name__ == "__main__":
    main()
