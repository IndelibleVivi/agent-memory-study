#!/usr/bin/env python3
"""Finite observation-cell compatibility, not a model or semantic evaluator.

Projection functions receive original event records only. The evaluator separately
reads the full record to construct the declared acceptable-answer contract. Audit
IDs and fixture answers never participate in observation equality.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures.json"
RESULTS = HERE / "results.json"
QUESTIONS = {
    "current_format": "Which format does the current v2 record specify?",
    "old_format": "Which format did the v1 record specify?",
    "old_speaker": "Who authored the v1 record?",
    "old_reason": "Which reason did the v1 record explicitly state?",
    "old_wording": "What is the exact wording of the v1 statement?",
}
AXES = ("old_format", "current_format", "old_speaker", "old_reason", "wording")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_fixtures(path=FIXTURES):
    fixture = json.loads(Path(path).read_text(encoding="utf-8"))
    if fixture.get("schema") != "ams-sufficiency-fixtures/1":
        raise ValueError("unsupported fixture schema")
    if set(fixture["axes"]) != set(AXES):
        raise ValueError("the declared event axes must be complete")
    for axis in AXES:
        values = fixture["axes"][axis]
        if not values or len(set(values)) != len(values):
            raise ValueError(f"empty or duplicate axis: {axis}")
    if set(fixture["axes"]["wording"]) - {"direct", "rephrased"}:
        raise ValueError("unknown wording transformation")
    for family, queries in fixture["query_families"].items():
        if not queries or len(set(queries)) != len(queries) or set(queries) - set(QUESTIONS):
            raise ValueError(f"invalid query family: {family}")
    if set(fixture["source_gates"]) != {
        "permitted", "available", "correct_revision", "target_bound", "adequate_coverage"
    }:
        raise ValueError("source access control must preserve all five declared gates")
    route_worlds = fixture["set_valued_control"]["worlds"]
    if len({w["audit_id"] for w in route_worlds}) != len(route_worlds):
        raise ValueError("duplicate route audit identity")
    for world in route_worlds:
        routes = world["recorded_routes"]
        if not routes or len(set(routes)) != len(routes):
            raise ValueError("route contracts need a nonempty set of unique answers")
    return fixture


def make_worlds(fixture):
    worlds = []
    for index, values in enumerate(product(*(fixture["axes"][key] for key in AXES))):
        old, current, speaker, reason, wording = values
        statement = (
            f"For v1, use {old}; stated reason: {reason}."
            if wording == "direct" else
            f"Stated reason: {reason}. The v1 format is {old}."
        )
        worlds.append({
            "audit_id": f"world-{index:02d}",
            "events": [
                {"time": "day-1", "version": "v1", "format": old,
                 "speaker": speaker, "reason": reason, "statement": statement},
                {"time": "day-2", "version": "v2", "format": current,
                 "speaker": "Rin", "reason": "v2_published",
                 "statement": f"For v2, use {current}."},
            ],
        })
    return worlds


def current_summary(events):
    latest = next(event for event in events if event["version"] == "v2")
    return {"current_version": "v2", "current_format": latest["format"]}


def version_relations(events):
    return {"formats": {event["version"]: event["format"] for event in events}}


def scoped_relations(events):
    return {"records": [
        {key: event[key] for key in ("version", "format", "speaker", "reason")}
        for event in events
    ]}


def expanded_summary(events):
    summary = current_summary(events)
    # This downstream transform sees only the already-created summary.
    return expand_existing_summary(summary)


def expand_existing_summary(summary):
    return {"statement": "The recorded current format is " + summary["current_format"],
            "version": summary["current_version"],
            "annotation": "No historical source statement is present in this view."}


def raw_events(events):
    return {"events": deepcopy(events)}


PROJECTIONS = {
    "current-summary": current_summary,
    "version-relations": version_relations,
    "scoped-relations": scoped_relations,
    "expanded-summary": expanded_summary,
    "raw-events": raw_events,
}


def reaccess(events, gates):
    """Synthetic all-gates resolver; no network, IDs, hashes, or lookup oracle.

    All-gates success makes the same complete record available independent of the
    later query. A failed gate preserves the summary without injecting raw bytes.
    This deliberately conservative resolver does not model partial retrieval.
    """
    summary = current_summary(events)
    failed = sorted(key for key, value in gates.items() if not value)
    return {"summary": summary,
            "access": {"state": "resolved" if not failed else "unresolved", "failed_gates": failed},
            "source": raw_events(events) if not failed else None}


def acceptable_answers(world, query):
    old, current = world["events"]
    values = {"current_format": current["format"], "old_format": old["format"],
              "old_speaker": old["speaker"], "old_reason": old["reason"],
              "old_wording": old["statement"]}
    return frozenset([values[query]])


def intersection(sets):
    sets = list(sets)
    if not sets:
        raise ValueError("intersection requires a nonempty observation class")
    result = set(sets[0])
    for values in sets[1:]:
        result.intersection_update(values)
    return result


def minimum_conflict(members, answer_sets):
    """Compute a smallest empty-intersection witness, including triples and up."""
    for size in range(1, len(members) + 1):
        for indices in combinations(range(len(members)), size):
            if not intersection(answer_sets[i] for i in indices):
                return [members[i]["audit_id"] for i in indices]
    return []


def evaluate_cells(worlds, observe, queries, answer_contract):
    grouped = {}
    for world in worlds:
        observation = observe(world)
        key = canonical(observation)
        grouped.setdefault(key, {"observation": observation, "members": []})["members"].append(world)
    classes = []
    for key in sorted(grouped):
        group = grouped[key]
        members = sorted(group["members"], key=lambda world: world["audit_id"])
        checks = []
        for query in queries:
            answers = [answer_contract(world, query) for world in members]
            if any(not values for values in answers):
                raise ValueError("an individually impossible task cannot diagnose representation loss")
            common = intersection(answers)
            checks.append({
                "query": query,
                "common_acceptable_answers": sorted(common),
                "compatible": bool(common),
                "minimum_empty_intersection_witness": minimum_conflict(members, answers) if not common else [],
            })
        classes.append({"observation": group["observation"],
                        "audit_members": [world["audit_id"] for world in members],
                        "task_checks": checks})
    return classes


def family_results(classes, families):
    result = {}
    for name, queries in families.items():
        checks = [check for cell in classes for check in cell["task_checks"] if check["query"] in queries]
        obstructed = [check for check in checks if not check["compatible"]]
        result[name] = {
            "queries": queries,
            "observation_class_query_pairs": len(checks),
            "obstructed_class_query_pairs": len(obstructed),
            "all_classes_compatible": not obstructed,
        }
    return result


def analyze_projection(worlds, observe, families):
    queries = sorted({query for queries in families.values() for query in queries})
    cells = evaluate_cells(worlds, observe, queries, acceptable_answers)
    return {"observation_classes": len(cells), "families": family_results(cells, families), "classes": cells}


def is_refinement(worlds, richer, coarser):
    """Every richer observation class is contained in one coarser class."""
    coarse_by_rich = {}
    for world in worlds:
        rich_key, coarse_key = canonical(richer(world)), canonical(coarser(world))
        coarse_by_rich.setdefault(rich_key, set()).add(coarse_key)
    return all(len(values) == 1 for values in coarse_by_rich.values())


def run(fixture):
    worlds = make_worlds(fixture)
    families = fixture["query_families"]
    observers = {name: (lambda world, project=project: project(world["events"]))
                 for name, project in PROJECTIONS.items()}
    projections = {name: analyze_projection(worlds, observer, families)
                   for name, observer in observers.items()}
    successful_gates = dict.fromkeys(fixture["source_gates"], True)
    source_conditions = {"all-gates-pass": successful_gates}
    for gate in fixture["source_gates"]:
        source_conditions[f"failed-{gate}"] = {**successful_gates, gate: False}
    source_access = {}
    for name, gates in source_conditions.items():
        observer = lambda world, gates=gates: reaccess(world["events"], gates)
        source_access[name] = {"gates": gates, **analyze_projection(worlds, observer, families)}

    route_worlds = fixture["set_valued_control"]["worlds"]
    route_answer = lambda world, query: frozenset(world["recorded_routes"])
    route_observer = lambda world: {"recorded_route_count": len(world["recorded_routes"])}
    route_cells = evaluate_cells(route_worlds, route_observer, ["choose-one-route"], route_answer)
    pairs = [{"audit_members": [left["audit_id"], right["audit_id"]],
              "common_acceptable_answers": sorted(set(left["recorded_routes"]) & set(right["recorded_routes"]))}
             for left, right in combinations(route_worlds, 2)]

    return {
        "schema": "ams-task-relative-sufficiency/1",
        "evidence": "Exhaustive finite compatibility checks over original synthetic worlds; no semantic decoder, model, retrieval service, or human study was run.",
        "fixture_sha256": sha256(canonical(fixture).encode("utf-8")).hexdigest(),
        "world_count": len(worlds),
        "independent_empirical_sample_count": 0,
        "questions": QUESTIONS,
        "declared_side_information": fixture["declared_side_information"],
        "projection_results": projections,
        "refinement_checks": {
            "raw_refines_scoped": is_refinement(worlds, observers["raw-events"], observers["scoped-relations"]),
            "scoped_refines_versions": is_refinement(worlds, observers["scoped-relations"], observers["version-relations"]),
            "versions_refine_current": is_refinement(worlds, observers["version-relations"], observers["current-summary"]),
            "expanded_refines_current": is_refinement(worlds, observers["expanded-summary"], observers["current-summary"]),
            "current_refines_expanded": is_refinement(worlds, observers["current-summary"], observers["expanded-summary"]),
        },
        "source_access": source_access,
        "set_valued_control": {
            "task": fixture["set_valued_control"]["task"],
            "pairs": pairs,
            "all_pairs_overlap": all(pair["common_acceptable_answers"] for pair in pairs),
            "classes": route_cells,
        },
        "limits": [
            "Compatibility is relative to this declared finite world set and answer contract, not unknown real-world histories.",
            "A nonempty intersection permits a common answer but does not demonstrate a semantic, efficient, learned, or natural-language decoder.",
            "No aggregate is a model accuracy, generalization rate, human preference, statistical significance, or token-matched comparison.",
            "The source-access controls are a synthetic all-or-nothing resolver; actual retrieval, partial coverage, authentication, and archival preservation remain untested.",
            "Original record availability, representation compatibility, candidate delivery, and actual answer use remain distinct observations.",
        ],
    }


def summary(result):
    lines = [f"Finite histories: {result['world_count']}; empirical samples: 0"]
    for name, analysis in result["projection_results"].items():
        flags = ", ".join(f"{family}={'compatible' if value['all_classes_compatible'] else 'obstructed'}"
                          for family, value in analysis["families"].items())
        lines.append(f"{name}: {analysis['observation_classes']} classes; {flags}")
    control = result["set_valued_control"]
    lines.append(f"Set-valued control: pairwise_overlap={control['all_pairs_overlap']}; "
                 f"global_compatible={control['classes'][0]['task_checks'][0]['compatible']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="recompute and compare the checked result")
    parser.add_argument("--output", type=Path, help="write to a new explicit output instead of results.json")
    args = parser.parse_args()
    if args.check and args.output:
        parser.error("--check and --output are mutually exclusive")
    result = run(load_fixtures())
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not RESULTS.exists() or json.loads(RESULTS.read_text(encoding="utf-8")) != result:
            raise SystemExit("FAIL: checked finite results differ; inspect the changed contract before updating.")
        print("PASS: finite observation-cell result recomputed")
    else:
        output = args.output or RESULTS
        if args.output and output.exists():
            raise SystemExit("Refusing to replace an existing explicit output.")
        output.write_text(payload, encoding="utf-8")
    print(summary(result))


if __name__ == "__main__":
    main()
