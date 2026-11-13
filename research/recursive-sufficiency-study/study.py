#!/usr/bin/env python3
"""Recompute finite analytic witnesses; no empirical data or model calls."""
from __future__ import annotations

import argparse
from fractions import Fraction as F
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parent
IDENTITY_FILES = ("study.py", "inputs.json", "protocol.md")


def f(value: F) -> dict:
    return {"exact": str(value), "decimal": float(value)}


def posterior(p: F, positive: bool, channel: tuple[F, F]) -> F:
    a, b = channel if positive else tuple(1 - value for value in channel)
    return p * a / (p * a + (1 - p) * b)


def decision(p: F) -> int:
    return int(p > F(1, 2))


def current_action_collision(config: dict) -> dict:
    priors = tuple(map(F, config["history_priors"]))
    weights = tuple(map(F, config["history_weights"]))
    channel = (F(config["positive_given_hidden_one"]),
               F(config["positive_given_hidden_zero"]))
    assert len(priors) == len(weights) == 2 and sum(weights) == 1
    rows = []
    joint = []
    for h, p in enumerate(priors):
        for theta in (0, 1):
            for positive in (False, True):
                ptheta = p if theta else 1 - p
                pplus = channel[0] if theta else channel[1]
                mass = weights[h] * ptheta * (pplus if positive else 1 - pplus)
                joint.append((h, theta, positive, mass))
        rows.append({"history": h, "prior": f(p), "old_action": decision(p),
                     "posterior_positive": f(posterior(p, True, channel)),
                     "posterior_negative": f(posterior(p, False, channel)),
                     "positive_action": decision(posterior(p, True, channel))})
    assert sum(r[3] for r in joint) == 1
    full_risk = F(0)
    compressed_risk = F(0)
    for h in range(2):
        for positive in (False, True):
            mass = [sum(r[3] for r in joint if r[0] == h and r[1] == theta and r[2] == positive)
                    for theta in (0, 1)]
            full_risk += min(mass)
    compressed_actions = {}
    for positive in (False, True):
        mass = [sum(r[3] for r in joint if r[1] == theta and r[2] == positive)
                for theta in (0, 1)]
        compressed_risk += min(mass)
        compressed_actions[str(positive)] = int(mass[1] > mass[0])
    assert [row["old_action"] for row in rows] == [0, 0]
    assert [row["positive_action"] for row in rows] == [0, 1]
    assert full_risk == F(11, 100)
    assert compressed_risk == F(23, 200)
    return {"rows": rows, "full_history_bayes_risk": f(full_risk),
            "old_action_only_bayes_risk": f(compressed_risk),
            "irrecoverable_risk_gap": f(compressed_risk - full_risk),
            "best_compressed_actions": compressed_actions,
            "enumerated_joint_cells": len(joint),
            "joint_distribution": [
                {"history": h, "hidden_bit": theta, "positive": positive, "mass": f(mass)}
                for h, theta, positive, mass in joint]}


def known_hidden_prediction(successes: int, failures: int,
                            coins: tuple[F, F], prior: tuple[F, F]) -> F:
    """Compute from emission likelihoods, independently of the odds shorthand."""
    masses = [weight * coin**successes * (1-coin)**failures
              for coin, weight in zip(coins, prior)]
    return sum(mass * coin for mass, coin in zip(masses, coins)) / sum(masses)


def learning_state(config: dict) -> dict:
    assert config["base_beta_prior"] == [1, 1]
    changed_threshold = F(config["changed_decision_threshold"])
    rows = []
    for alpha, beta in config["same_mean_posteriors"]:
        rows.append({"alpha": alpha, "beta": beta,
                     "one_step_success": f(F(alpha, alpha + beta)),
                     "two_successes": f(F(alpha * (alpha + 1), (alpha + beta) * (alpha + beta + 1))),
                     "success_after_success": f(F(alpha + 1, alpha + beta + 1)),
                     "after_success_action_at_changed_threshold":
                         int(F(alpha + 1, alpha + beta + 1) > changed_threshold)})
    counts = []
    for t in config["mean_count_horizons"]:
        means = {F(s + 1, t + 2) for s in range(t + 1)}
        assert len(means) == t + 1
        counts.append({"observations": t, "distinct_posterior_means": len(means),
                       "fixed_width_bits_lower_bound": (len(means) - 1).bit_length()})
    continuation_counts = []
    selected_witnesses = []
    hidden_coins = tuple(map(F, config["known_hidden_coin_probabilities"]))
    hidden_prior = tuple(map(F, config["known_hidden_coin_prior"]))
    assert hidden_coins == (F(1, 4), F(3, 4))
    assert hidden_prior == (F(1, 2), F(1, 2))
    hidden_continuation_counts = []
    hidden_selected_witnesses = []
    for t in config["decision_pair_horizons"]:
        witnessed = 0
        max_length = 0
        for s1, s2 in itertools.combinations(range(t+1), 2):
            witness = None
            for length in range(t+2):
                for bit in (0, 1):
                    a1 = decision(F(s1 + bit*length + 1, t + length + 2))
                    a2 = decision(F(s2 + bit*length + 1, t + length + 2))
                    if a1 != a2:
                        witness = {"T": t, "success_counts": [s1, s2],
                                   "suffix_bit": bit, "suffix_length": length,
                                   "resulting_actions": [a1, a2]}
                        break
                if witness is not None:
                    break
            assert witness is not None
            hidden_predictions = [known_hidden_prediction(
                s + witness["suffix_bit"] * witness["suffix_length"],
                t - s + (1-witness["suffix_bit"]) * witness["suffix_length"],
                hidden_coins, hidden_prior) for s in (s1, s2)]
            hidden_actions = list(map(decision, hidden_predictions))
            assert hidden_actions == witness["resulting_actions"]
            assert hidden_actions[0] != hidden_actions[1]
            witnessed += 1
            max_length = max(max_length, witness["suffix_length"])
            if t == config["saved_pair_witness_horizon"]:
                selected_witnesses.append(witness)
                hidden_selected_witnesses.append({**witness,
                    "next_success_probabilities_after_suffix": list(map(f, hidden_predictions))})
        continuation_counts.append({"T": t, "current_action_classes": len({decision(F(s+1,t+2)) for s in range(t+1)}),
                                    "pair_count": t*(t+1)//2, "pairs_with_common_suffix_witness": witnessed,
                                    "longest_selected_suffix": max_length,
                                    "recursive_decision_classes_lower_bound": t+1})
        hidden_continuation_counts.append({"T": t, "pair_count": t*(t+1)//2,
            "pairs_separated_using_emission_likelihoods": witnessed,
            "recursive_decision_classes_lower_bound": t+1})
    assert rows[0]["one_step_success"] == rows[1]["one_step_success"]
    assert rows[0]["two_successes"] != rows[1]["two_successes"]
    assert [row["after_success_action_at_changed_threshold"] for row in rows] == [1, 0]
    hidden_rows = []
    for difference in config["known_hidden_coin_count_differences"]:
        odds = F(3) ** difference
        prediction = hidden_coins[0] + (hidden_coins[1] - hidden_coins[0]) * odds / (1 + odds)
        assert prediction == known_hidden_prediction(max(0, difference), max(0, -difference),
                                                      hidden_coins, hidden_prior)
        assert decision(prediction) == int(difference > 0)
        hidden_rows.append({"success_minus_failure": difference,
                            "posterior_high_coin_odds": f(odds),
                            "next_success_probability": f(prediction),
                            "symmetric_loss_action": decision(prediction)})
    return {"same_one_step_different_continuation": rows, "exact_mean_state_counts": counts,
            "changed_decision_threshold": f(changed_threshold),
            "fixed_loss_continuation_classes": continuation_counts,
            "fixed_loss_T8_pair_witnesses": selected_witnesses,
            "known_two_state_noisy_model": hidden_rows,
            "known_two_state_continuation_classes": hidden_continuation_counts,
            "known_two_state_T8_pair_witnesses": hidden_selected_witnesses,
            "information_scope_caveat": "The static binary hidden mode has at most one bit of mutual information with history. This does not bound the number of exactly distinct posterior beliefs or continuation-decision classes. Each fixed horizon still has finitely many classes.",
            "decision_scope_caveat": "Beta(1,1) and Beta(2,2) remain action-equivalent for the fixed symmetric-loss task under all common Bernoulli continuations; their differing predictive distributions matter for an expanded loss/threshold family.",
            "event_clock_control": "Both histories use one batch event; batch sample counts are omitted from mean-only memory."}


def h2(p: F) -> float:
    if p in (0, 1):
        return 0.0
    return -float(p) * math.log2(float(p)) - float(1 - p) * math.log2(float(1 - p))


def noisy_bit_error(epsilon: F, repeats: int) -> F:
    error = F(0)
    for observed in itertools.product((0, 1), repeat=repeats):
        joint = []
        for truth in (0, 1):
            mass = F(1, 2)
            for obs in observed:
                mass *= 1 - epsilon if obs == truth else epsilon
            joint.append(mass)
        error += min(joint)
    return error


def restoration_cost(config: dict) -> dict:
    missing_bits = config["missing_independent_fair_bits"]
    epsilon = F(config["independent_binary_channel_error"])
    histories = list(itertools.product((0, 1), repeat=missing_bits + 1))
    fibers = {x: [h for h in histories if h[0] == x] for x in (0, 1)}
    full_sizes = [len(set(v)) for v in fibers.values()]
    parity_sizes = [len({sum(h[1:]) % 2 for h in v}) for v in fibers.values()]
    noise = []
    for n in config["observations_per_bit"]:
        e = noisy_bit_error(epsilon, n)
        assert noisy_bit_error(F(1, 2), n) == F(1, 2)
        assert noisy_bit_error(F(0), n) == 0
        noise.append({"independent_observations_per_bit": n,
                      "bit_error": f(e), "three_bit_exact_recovery_probability": f((1-e)**missing_bits),
                      "observed_channel_bits": missing_bits*n})
    assert [row["bit_error"]["exact"] for row in noise] == ["1/10", "7/250", "107/12500"]
    return {"history_count": len(histories), "old_memory_classes": len(fibers),
            "full_target_fiber_sizes": full_sizes, "parity_target_fiber_sizes": parity_sizes,
            "uniform_missing_full_information_bits": round(math.log2(full_sizes[0]), 12),
            "uniform_missing_parity_information_bits": round(math.log2(parity_sizes[0]), 12),
            "one_noisy_read_remaining_entropy_bits": round(missing_bits*h2(epsilon), 12),
            "noise_channel": noise}


def build_results() -> dict:
    config = json.loads((ROOT / "inputs.json").read_text(encoding="utf-8"))
    assert config["schema"] == "ams-recursive-sufficiency-inputs/1"
    return {"schema": "ams-recursive-sufficiency-results/1",
            "status": "executed-exact-constructions",
            "empirical_sample_count": 0, "model_calls": 0,
            "source_identity": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                for name in IDENTITY_FILES},
            "runtime": {"python": platform.python_version()},
            "current_action_collision": current_action_collision(config["current_action_collision"]),
            "learning_state": learning_state(config["learning_state"]),
            "restoration_cost": restoration_cost(config["restoration_cost"])}


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="Create a fresh result; existing files are rejected")
    mode.add_argument("--check", action="store_true", help="Recompute and check the saved receipt")
    parser.add_argument("--results", type=Path, default=ROOT / "results.json",
                        help="Receipt to check (default: this directory's results.json)")
    args = parser.parse_args()
    result = build_results()
    if args.check:
        try:
            recorded = json.loads(args.results.read_text(encoding="utf-8"))
            if not isinstance(recorded, dict):
                raise ValueError("result root must be an object")
            runtime = recorded.pop("runtime")
            expected = dict(result)
            expected.pop("runtime")
            if (not isinstance(runtime, dict) or set(runtime) != {"python"}
                    or not isinstance(runtime["python"], str) or not runtime["python"]):
                raise ValueError("invalid historical runtime metadata")
            if recorded != expected:
                raise ValueError("scientific payload or source identity differs")
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"CHECK FAILED: {error}", file=sys.stderr)
            return 1
        print("PASS: analytic results and source/input/protocol identities match; no model calls")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "status": result["status"],
                      "risk_gap": result["current_action_collision"]["irrecoverable_risk_gap"],
                      "source_identity": result["source_identity"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
