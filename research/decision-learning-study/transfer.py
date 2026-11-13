#!/usr/bin/env python3
"""Pre-specified finite synthetic v1 combination-transfer diagnostic."""
import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parent
BASELINE_COMMIT = "f16b3156325078b557b02c4742a280d623220fde"
PROTOCOL_SHA256 = "6dd2e5db6d5df0d3e0f52ba3807673bf929e5cc08dd2947683557c57395dbcef"
SOURCE_FILES = (
    "fixture_build.py", "study.py", "fixtures.json", "results.json",
    "support_audit.py", "support-results.json", "transfer-protocol.md",
)
LABELS = ("useful", "redundant", "irrelevant", "harmful")
SCOPE_FIRST = ("irrelevant", "harmful", "redundant", "useful")
HAZARD_FIRST = ("harmful", "irrelevant", "redundant", "useful")
ARM_ADDED = 32
ARM_CLASS_COUNT = 8


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_original():
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("ams_original_decision", ROOT / "study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


original = load_original()
import support_audit


def make_modes():
    """Return named coherent priorities and a per-case tie collector."""
    def ordered(train, key, reverse=False):
        return sorted(train, key=key, reverse=reverse)

    scope_priority = SCOPE_FIRST
    hazard_priority = HAZARD_FIRST
    scope_key = lambda r: scope_priority.index(r["expected"])
    hazard_key = lambda r: hazard_priority.index(r["expected"])
    return {
        "scope-first": lambda train: ordered(train, scope_key),
        "hazard-first": lambda train: ordered(train, hazard_key),
    }


def filtered_train(fixture):
    rows = [r for r in original.rows_for(fixture, "train") if original.vector(r)[9] == 0]
    assert rows and all(original.vector(r)[9] == 0 for r in rows)
    return rows


def class_candidates(train):
    candidates = {}
    source = {}
    for row in train:
        x = tuple(original.vector(row))
        candidates.setdefault(row["expected"], set()).add(x)
        source.setdefault((row["expected"], x), row)
    return (
        {label: [source[(label, x)] for x in sorted(vectors)]
         for label, vectors in candidates.items()},
        {label: len(vectors) for label, vectors in candidates.items()},
    )


def assert_class_histogram(rows):
    histogram = {
        label: sum(row["expected"] == label for row in rows) for label in LABELS
    }
    assert len(rows) == ARM_ADDED, (len(rows), ARM_ADDED)
    assert histogram == {label: ARM_CLASS_COUNT for label in LABELS}, histogram
    return histogram


def cycle(rows, count):
    return [copy.deepcopy(rows[i % len(rows)]) for i in range(count)]


def additions(train, name):
    by_class, unique = class_candidates(train)
    additions_rows = []
    chosen_vectors = {}
    if name == "balanced-repeats":
        for label in LABELS:
            shared = cycle(by_class[label], ARM_CLASS_COUNT)
            additions_rows.extend(shared)
            chosen_vectors[label] = [tuple(original.vector(r)) for r in shared]
        return additions_rows, {"unique": unique, "selected_unique": {
            label: len(set(vectors)) for label, vectors in chosen_vectors.items()}}
    if name != "balanced-counterexamples":
        raise ValueError(name)
    support = {tuple(original.vector(r)) for r in train}
    pool = [
        support_audit.construct(x, i, original)
        for i, x in enumerate(itertools.product((0, 1), repeat=10))
        if x[9] == 0
    ]
    for label in LABELS:
        rows = [r for r in pool if r["expected"] == label]
        rows.sort(key=lambda r: (tuple(original.vector(r)) in support, tuple(original.vector(r))))
        selected = cycle(rows[:ARM_CLASS_COUNT], ARM_CLASS_COUNT)
        additions_rows.extend(selected)
        chosen_vectors[label] = [tuple(original.vector(r)) for r in selected]
    return additions_rows, {"unique": unique, "selected_unique": {
        label: len(set(vectors)) for label, vectors in chosen_vectors.items()}}


def build_arms(fixture):
    base = filtered_train(fixture)
    arms = {"filtered-original": {"training": base, "added": [], "selection": {"unique": {
        label: len({tuple(original.vector(r)) for r in base if r["expected"] == label})
        for label in LABELS}}}}
    for name in ("balanced-repeats", "balanced-counterexamples"):
        selected, selection = additions(base, name)
        if name == "balanced-counterexamples":
            support = {tuple(original.vector(r)) for r in base}
            expected_pool = sorted(
                x for x in itertools.product((0, 1), repeat=10)
                if x[9] == 0 and x not in support
            )
            selected_vectors = [tuple(original.vector(r)) for r in selected]
            assert all(x in expected_pool or x in support for x in selected_vectors)
        assert_class_histogram(selected)
        assert all(original.vector(r)[9] == 0 for r in selected)
        arms[name] = {"training": base + selected, "added": selected, "selection": selection}
    return arms


def build_test(fixture):
    all_rows = [
        support_audit.construct(x, i, original)
        for i, x in enumerate(itertools.product((0, 1), repeat=10))
    ]
    test = [r for r in all_rows if original.vector(r)[9] == 1]
    assert len(test) == 512
    by_vector = {tuple(original.vector(r)): r for r in test}
    positives = [x for x, r in by_vector.items() if r["expected"] == "useful"]
    assert len(positives) == 2
    neighbors = {}
    neighbor_features = {
        3: "missing-prerequisite", 6: "expired", 7: "side-effect", 8: "verified",
    }
    for x in positives:
        vector_neighbors = {}
        for feature, name_for_feature in neighbor_features.items():
            y = list(x)
            y[feature] = 1 - y[feature]
            neighbour = by_vector[tuple(y)]
            vector_neighbors[name_for_feature] = {
                "vector": list(y), "label": neighbour["expected"],
                "distance": sum(a != b for a, b in zip(x, y)),
                "flipped_feature": original.FEATURES[feature],
            }
        neighbors[tuple(x)] = vector_neighbors
    return test, positives, neighbors


def count_metrics(rows, labels, prediction, indices=None):
    indices = list(range(len(rows))) if indices is None else list(indices)
    ys = [labels[i] if isinstance(labels, list) else rows[i]["expected"] for i in indices]
    ps = [prediction[i] for i in indices]
    per_class = {}
    for label in LABELS:
        positions = [i for i, y in enumerate(ys) if y == label]
        per_class[label] = {
            "n": len(positions),
            "correct": sum(ps[i] == label for i in positions),
        }
    useful = [i for i, y in enumerate(ys) if y == "useful"]
    harmful = [i for i, y in enumerate(ys) if y == "harmful"]
    other = [i for i, y in enumerate(ys) if y in ("redundant", "irrelevant")]
    selected = [i for i, p in enumerate(ps) if p == "useful"]
    return {
        "n": len(indices),
        "class_correct": sum(y == p for y, p in zip(ys, ps)),
        "class_accuracy": (sum(y == p for y, p in zip(ys, ps)) / len(indices)
                           if indices else None),
        "per_class": per_class,
        "selection": {
            "selected": len(selected),
            "rejected": len(indices) - len(selected),
            "useful_recall": {
                "correct": sum(ps[i] == "useful" for i in useful),
                "n": len(useful),
            },
            "expected_useful_but_rejected": sum(ps[i] != "useful" for i in useful),
            "harmful_false_injection": {
                "count": sum(ps[i] == "useful" for i in harmful),
                "n": len(harmful),
            },
            "other_false_injection": {
                "count": sum(ps[i] == "useful" for i in other),
                "n": len(other),
            },
        },
        "frozen_unit_utility": (
            sum((1 if ps[i] == "useful" and ys[i] == "useful" else
                 -1 if ps[i] == "useful" and ys[i] != "useful" else 0)
                for i in range(len(indices)))
        ),
    }


def nearest_details(train, test):
    xs = [original.vector(r) for r in train]
    details = []
    for row in test:
        x = original.vector(row)
        distances = [sum(a != b for a, b in zip(train_x, x)) for train_x in xs]
        minimum = min(distances)
        tied = sorted({train[i]["expected"] for i, d in enumerate(distances) if d == minimum})
        details.append({"distance": minimum, "tied_classes": tied})
    return details


def tie_report(train, test):
    details = nearest_details(train, test)
    labels = [r["expected"] for r in test]
    best = worst = 0
    per_case = []
    for row, detail in zip(test, details):
        offered = detail["tied_classes"]
        outcomes = [count_metrics([row], [row["expected"]], [choice])["frozen_unit_utility"]
                    for choice in offered]
        low, high = min(outcomes), max(outcomes)
        best += high
        worst += low
        per_case.append({
            "vector": original.vector(row),
            "tied_classes": offered,
            "best_outcome": high,
            "worst_outcome": low,
        })
    modes = make_modes()
    named = {}
    for name, sorter in modes.items():
        ordered = sorter(train)
        prediction = original.episodic(ordered, test)
        named[name] = {
            "training_order": [r["id"] for r in ordered],
            "metrics": count_metrics(test, labels, prediction),
        }
    return {
        "kind": "per-case independent minima over all nearest-row classes",
        "warning": "Independent per-case choices need not be jointly attainable under one global order.",
        "note": "Extrema are reported per case and summed; they are not a single ordering.",
        "class_correct_best": sum(
            max(choice == row["expected"] for choice in detail["tied_classes"])
            for row, detail in zip(test, details)
        ),
        "class_correct_worst": sum(
            min(choice == row["expected"] for choice in detail["tied_classes"])
            for row, detail in zip(test, details)
        ),
        "selection_correct_best": sum(
            max((choice == "useful") == (row["expected"] == "useful")
                for choice in detail["tied_classes"])
            for row, detail in zip(test, details)
        ),
        "selection_correct_worst": sum(
            min((choice == "useful") == (row["expected"] == "useful")
                for choice in detail["tied_classes"])
            for row, detail in zip(test, details)
        ),
        "utility_best": best,
        "utility_worst": worst,
        "per_case": per_case,
        "named_finite_orders": named,
        "named_orders_are_not_global_extrema": True,
    }


def priority_ties(train, test):
    details = nearest_details(train, test)
    by_vector = {tuple(original.vector(row)): detail for row, detail in zip(test, details)}
    priorities = {
        "scope-first": SCOPE_FIRST,
        "hazard-first": HAZARD_FIRST,
    }
    result = {}
    for name, order in priorities.items():
        ranks = {label: order.index(label) for label in LABELS}
        predictions = [
            min(by_vector[tuple(original.vector(row))]["tied_classes"], key=ranks.__getitem__)
            for row in test
        ]
        result[name] = {
            "priority": list(order),
            "prediction_boundary": "coherent class priority within each minimum-distance tie set",
            "global_extrema_claim": False,
            "metrics": count_metrics(test, [r["expected"] for r in test], predictions),
        }
    return result


def verified_flips(test, predictions):
    lookup = {tuple(original.vector(r)): i for i, r in enumerate(test)}
    pairs = []
    conflicts = []
    for i, row in enumerate(test):
        x = tuple(original.vector(row))
        if x[8] == 1:
            continue
        y = list(x)
        y[8] = 1
        j = lookup[tuple(y)]
        pairs.append((i, j))
    summary = {}
    for name, prediction in predictions.items():
        summary[name] = {
            "pairs": len(pairs),
            "class_changes": sum(prediction[i] != prediction[j] for i, j in pairs),
            "selection_changes": sum((prediction[i] == "useful") != (prediction[j] == "useful")
                                     for i, j in pairs),
        }
    conflict_pairs = []
    for i, row in enumerate(test):
        x = tuple(original.vector(row))
        if support_audit.direct_label(x) != support_audit.direct_label(x, hazard_first=True):
            conflict_pairs.append({
                "vector": list(x), "scope_first": support_audit.direct_label(x),
                "hazard_first": support_audit.direct_label(x, hazard_first=True),
            })
    return summary, conflict_pairs


def report():
    fixture = json.loads((ROOT / "fixtures.json").read_text())
    test, positives, neighbors = build_test(fixture)
    assert [tuple(original.vector(r)) for r in test] == sorted(
        tuple(original.vector(r)) for r in test
    )
    arms = build_arms(fixture)
    train_vectors = {tuple(original.vector(r)) for arm in arms.values() for r in arm["training"]}
    base_vectors = {
        tuple(original.vector(r)) for r in arms["filtered-original"]["training"]
    }
    test_vectors = {tuple(original.vector(r)) for r in test}
    assert train_vectors.isdisjoint(test_vectors)
    for name, arm in arms.items():
        if name == "filtered-original":
            continue
        assert_class_histogram(arm["added"])
        assert len(arm["training"]) == (
            len(arms["filtered-original"]["training"]) + ARM_ADDED
        )
        assert all(original.vector(row)[9] == 0 for row in arm["added"])
    for row in test:
        assert support_audit.direct_label(original.vector(row)) == row["expected"]
    labels = [r["expected"] for r in test]
    v2_labels = [support_audit.direct_label(original.vector(r), 2) for r in test]
    predictions = {
        "oracle-v1": labels,
        "constant-reject": ["irrelevant"] * len(test),
    }
    models = {}
    for name, arm in arms.items():
        fitted = original.fit(arm["training"])
        tree = original.induce(arm["training"])
        predictions[name] = original.scorer(fitted, test)
        predictions[f"{name}-rules"] = original.rule_predict(tree, test)
        predictions[f"{name}-nearest"] = original.episodic(arm["training"], test)
        models[name] = {
            "scorer": original.rounded(fitted), "tree": tree,
            "training_vectors": [original.vector(r) for r in arm["training"]],
            "added_vectors": [original.vector(r) for r in arm["added"]],
            "training_ids": [r["id"] for r in arm["training"]],
            "added_ids": [r["id"] for r in arm["added"]],
            "support": {
                "rows": len(arm["training"]),
                "unique_vectors": len({tuple(original.vector(r)) for r in arm["training"]}),
                "added_rows": len(arm["added"]),
                "added_class_histogram": {
                    label: sum(r["expected"] == label for r in arm["added"]) for label in LABELS
                },
                "added_unique_vectors": len({tuple(original.vector(r)) for r in arm["added"]}),
                "selection": arm["selection"],
            },
        }
    validation = [r for r in original.rows_for(fixture, "validation") if original.vector(r)[9] == 0]
    validation_predictions = {
        "filtered-original": original.scorer(models["filtered-original"]["scorer"], validation),
    }
    flips, conflicts = verified_flips(test, predictions)
    changed = [i for i, (a, b) in enumerate(zip(labels, v2_labels)) if a != b]
    preserved = [i for i in range(len(test)) if i not in changed]
    boundary = [i for i in range(len(test)) if v2_labels[i] == "useful"]
    assert set(boundary) <= set(preserved)
    assert len(boundary) < len(preserved)
    v2_scopes = {"changed": changed, "preserved": preserved, "boundary": boundary}
    sensitivity_training = [
        r for r in original.rows_for(fixture, "train") if original.vector(r)[9] == 1
    ]
    validation_sensitive = [
        r for r in original.rows_for(fixture, "validation") if original.vector(r)[9] == 1
    ]
    metrics = {name: count_metrics(test, labels, pred) for name, pred in predictions.items()}
    v2_metrics = {
        name: {
            scope: count_metrics(test, v2_labels, pred, indices)
            for scope, indices in v2_scopes.items()
        }
        for name, pred in predictions.items()
    }
    cases = []
    for i, row in enumerate(test):
        x = original.vector(row)
        cases.append({
            "vector": x,
            "event": row["event"],
            "context": row["context"],
            "candidate": row["candidate"],
            "label_v1": labels[i],
            "label_v2": v2_labels[i],
            "predictions": {name: pred[i] for name, pred in predictions.items()},
        })
    source_hash = {name: sha256(ROOT / name) for name in SOURCE_FILES}
    source_hash["transfer.py"] = sha256(Path(__file__))
    assert source_hash["transfer-protocol.md"] == PROTOCOL_SHA256
    assert all(original.vector(r)[9] == 0 for arm in arms.values() for r in arm["training"])
    return {
        "schema": "ams-decision-transfer/1",
        "study": "decision-learning-study",
        "baseline_commit": BASELINE_COMMIT,
        "evidence_kind": "pre-specified follow-up diagnostic after exhaustive-domain observation",
        "not_independent_blind_confirmation": True,
        "not_preregistration": True,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_sha256": source_hash,
        "split": {
            "test_definition": "every lexicographic 10-bit vector with sensitive=1",
            "test_vectors": len(test),
            "training_definition": "original train rows with sensitive=0",
            "training_rows": len(arms["filtered-original"]["training"]),
            "training_unique_vectors": len(base_vectors),
            "all_arm_union_unique_vectors": len(train_vectors),
            "sensitive_training_rows_available_but_unused": len(sensitivity_training),
            "sensitive_training_rows_used": 0,
            "sensitive_validation_rows_available_but_unused": len(validation_sensitive),
            "sensitive_validation_rows_used": 0,
            "overlap": len(train_vectors & test_vectors),
            "useful_test_vectors": [list(x) for x in positives],
            "neighbors": {repr(x): v for x, v in neighbors.items()},
            "identifiability": {
                "sensitive_flip_pairs": 0,
                "reason": "All test vectors have sensitive=1; no within-test sensitive flip is identifiable.",
            },
        },
        "arm_contract": {
            "classes": list(LABELS),
            "added_rows": ARM_ADDED,
            "added_per_class": ARM_CLASS_COUNT,
            "original_budget": {
                "steps": original.STEPS, "rate": original.RATE,
                "l2": original.L2, "tree_max_depth": 4, "features": list(original.FEATURES),
            },
        },
        "arms": models,
        "validation_sensitive_zero": {
            "rows": len(validation),
            "metrics": metrics["filtered-original"] if not validation else
                count_metrics(validation, [r["expected"] for r in validation],
                              validation_predictions["filtered-original"]),
        },
        "metrics_v1": metrics,
        "metrics_v2_policy_mismatch": {
            "status": "frozen v1 policy mismatch; no v2 fitting or corrected-learning claim",
            "full_domain": {
                name: count_metrics(test, v2_labels, pred)
                for name, pred in predictions.items()
            },
            "methods": v2_metrics,
        },
        "tie_report": {
            **tie_report(arms["filtered-original"]["training"], test),
            "priority_tie_controls": priority_ties(arms["filtered-original"]["training"], test),
        },
        "verified_flips": flips,
        "scope_hazard_conflicts": conflicts,
        "v2_scope": {
            "changed": len(changed),
            "preserved": len(preserved),
            "boundary": len(boundary),
            "boundary_subset_of_preserved": True,
            "rule": "unchanged v2 in-scope correction with sensitive=1 and verified=0",
        },
        "cases": cases,
    }


def finish(receipt, elapsed):
    receipt["execution"] = {
        "python": platform.python_version(),
        "elapsed_seconds": round(elapsed, 4),
        "note": "One local runtime, excluded from deterministic --check.",
    }
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "transfer-results.json")
    args = parser.parse_args()
    started = time.perf_counter()
    result = report()
    if args.check:
        saved = json.loads(args.output.read_text())
        saved.pop("execution", None)
        assert saved == result, "deterministic receipt mismatch"
        assert sha256(ROOT / "transfer-protocol.md") == PROTOCOL_SHA256
        print("PASS: transfer protocol, split, arms, fits, predictions and metrics recomputed")
    else:
        args.output.write_text(json.dumps(finish(result, time.perf_counter() - started),
                                          ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({
            name: {
                "accuracy": metric["class_accuracy"],
                "utility": metric["frozen_unit_utility"],
                "useful_recall": metric["selection"]["useful_recall"],
            }
            for name, metric in result["metrics_v1"].items()
        }, indent=2))


if __name__ == "__main__":
    main()
