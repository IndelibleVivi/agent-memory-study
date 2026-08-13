#!/usr/bin/env python3
"""Static small-graph oracle for a bounded subset of Doyle-style SL semantics.

This is not Doyle's TMS, an execution trace, or an incremental simulator. It
enumerates support-status assignments, retains support-complete assignments,
and requires every IN node to have a finite positive proof through valid SL
justifications. Negative antecedents are assignment checks only.

Fixtures 11--13 compare two explicitly different abstraction lifecycle
policies. They do not claim that Doyle's FIS or proposed SUM form naturally
retains or retires a derived SL justification after later graph changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class SL:
    target: str
    inlist: tuple[str, ...] = ()
    outlist: tuple[str, ...] = ()


def validate_graph(nodes: tuple[str, ...], justifications: tuple[SL, ...]) -> None:
    if len(nodes) != len(set(nodes)):
        raise ValueError("duplicate node identifiers")

    declared = set(nodes)
    for justification in justifications:
        referenced = {justification.target, *justification.inlist, *justification.outlist}
        undeclared = sorted(referenced - declared)
        if undeclared:
            raise ValueError(f"undeclared node reference(s): {', '.join(undeclared)}")


def actor_of(node: str) -> str | None:
    return node.split(":", 1)[0] if ":" in node else None


def validate_actor_scope(
    justifications: tuple[SL, ...],
    allowed_bridges: frozenset[tuple[str, str]] = frozenset(),
) -> None:
    """Reject cross-actor dependencies unless an external schema admits a bridge."""

    for justification in justifications:
        target_actor = actor_of(justification.target)
        for dependency in (*justification.inlist, *justification.outlist):
            source_actor = actor_of(dependency)
            if (
                source_actor is not None
                and target_actor is not None
                and source_actor != target_actor
                and (source_actor, target_actor) not in allowed_bridges
            ):
                raise ValueError(
                    "undeclared cross-actor dependency: "
                    f"{dependency} -> {justification.target}"
                )


def valid(justification: SL, inside: set[str]) -> bool:
    return all(node in inside for node in justification.inlist) and all(
        node not in inside for node in justification.outlist
    )


def has_finite_positive_proof(
    target: str, inside: set[str], justifications: tuple[SL, ...]
) -> bool:
    """Find one finite positive proof for an IN node in this assignment."""

    by_target: dict[str, list[SL]] = {}
    for justification in justifications:
        by_target.setdefault(justification.target, []).append(justification)

    def prove(node: str, trail: frozenset[str]) -> bool:
        if node in trail:
            return False
        return any(
            valid(justification, inside)
            and all(prove(parent, trail | {node}) for parent in justification.inlist)
            for justification in by_target.get(node, [])
        )

    return prove(target, frozenset())


def admissible_sl_models(
    nodes: tuple[str, ...],
    justifications: tuple[SL, ...],
    *,
    enforce_actor_scope: bool = False,
    allowed_actor_bridges: frozenset[tuple[str, str]] = frozenset(),
) -> list[tuple[str, ...]]:
    validate_graph(nodes, justifications)
    if enforce_actor_scope:
        validate_actor_scope(justifications, allowed_actor_bridges)

    results: list[tuple[str, ...]] = []
    for bits in product((False, True), repeat=len(nodes)):
        inside = {node for node, bit in zip(nodes, bits) if bit}
        support_complete = {
            node
            for node in nodes
            if any(
                valid(justification, inside)
                for justification in justifications
                if justification.target == node
            )
        }
        if support_complete != inside:
            continue
        if all(
            has_finite_positive_proof(node, inside, justifications) for node in inside
        ):
            results.append(tuple(node for node in nodes if node in inside))
    return results


def show(
    name: str,
    nodes: tuple[str, ...],
    justifications: tuple[SL, ...],
    expected: list[tuple[str, ...]],
    *,
    enforce_actor_scope: bool = False,
) -> None:
    found = admissible_sl_models(
        nodes,
        justifications,
        enforce_actor_scope=enforce_actor_scope,
    )
    assert found == expected, f"{name}: expected {expected}, found {found}"
    rendered: object = found if found else "NO STATIC ADMISSIBLE MODEL"
    print(f"{name}: {rendered}")


def expect_rejection(
    name: str, operation: Callable[[], object], expected_fragment: str
) -> None:
    try:
        operation()
    except ValueError as error:
        assert expected_fragment in str(error), (name, error)
        print(f"{name}: REJECTED ({error})")
        return
    raise AssertionError(f"{name}: expected schema rejection")


def main() -> None:
    show("01 static default", ("W", "NOT_W"), (SL("W", outlist=("NOT_W",)),), [("W",)])
    show(
        "02 static default overridden",
        ("W", "NOT_W"),
        (SL("W", outlist=("NOT_W",)), SL("NOT_W")),
        [("NOT_W",)],
    )
    show(
        "03 static closure with foundation",
        ("A", "B", "C"),
        (SL("A"), SL("B", ("A",)), SL("C", ("B",))),
        [("A", "B", "C")],
    )
    show(
        "04 static graph after foundation removal",
        ("A", "B", "C"),
        (SL("B", ("A",)), SL("C", ("B",))),
        [()],
    )
    show(
        "05 positive cycle without foundation",
        ("F", "G"),
        (SL("F", ("G",)), SL("G", ("F",))),
        [()],
    )
    show(
        "06 positive cycle with foundation",
        ("F", "G"),
        (SL("F"), SL("F", ("G",)), SL("G", ("F",))),
        [("F", "G")],
    )
    show(
        "07 two admissible negative-loop assignments",
        ("F", "G"),
        (SL("F", outlist=("G",)), SL("G", outlist=("F",))),
        [("G",), ("F",)],
    )
    show(
        "08 unsatisfiable self-negation",
        ("F",),
        (SL("F", outlist=("F",)),),
        [],
    )
    show(
        "09 backtracking precondition",
        ("TIME10", "NOT_TIME10", "ROOM813", "ROOM801", "CONTRADICTION"),
        (
            SL("TIME10", outlist=("NOT_TIME10",)),
            SL("ROOM813", outlist=("ROOM801",)),
            SL("CONTRADICTION", ("TIME10", "ROOM813")),
        ),
        [("TIME10", "ROOM813", "CONTRADICTION")],
    )
    show(
        "10 externally supplied room denial",
        ("TIME10", "NOT_TIME10", "ROOM813", "ROOM801", "CONTRADICTION"),
        (
            SL("TIME10", outlist=("NOT_TIME10",)),
            SL("ROOM813", outlist=("ROOM801",)),
            SL("ROOM801"),
            SL("CONTRADICTION", ("TIME10", "ROOM813")),
        ),
        [("TIME10", "ROOM801")],
    )

    abstraction_nodes = ("D", "E", "X", "INTERNAL", "RAW", "SUMMARY")
    show(
        "11 materialized abstraction initially agrees",
        abstraction_nodes,
        (
            SL("D"),
            SL("E"),
            SL("INTERNAL", ("D", "E"), ("X",)),
            SL("RAW", ("INTERNAL",)),
            SL("SUMMARY", ("D", "E")),
        ),
        [("D", "E", "INTERNAL", "RAW", "SUMMARY")],
    )
    show(
        "12 retained abstraction under persist-derived-SL policy",
        abstraction_nodes,
        (
            SL("D"),
            SL("E"),
            SL("X"),
            SL("INTERNAL", ("D", "E"), ("X",)),
            SL("RAW", ("INTERNAL",)),
            SL("SUMMARY", ("D", "E")),
        ),
        [("D", "E", "X", "SUMMARY")],
    )
    show(
        "13 recompute policy retires materialized abstraction",
        abstraction_nodes,
        (
            SL("D"),
            SL("E"),
            SL("X"),
            SL("INTERNAL", ("D", "E"), ("X",)),
            SL("RAW", ("INTERNAL",)),
        ),
        [("D", "E", "X")],
    )

    actor_nodes = ("U:RAIN", "U:UMBRELLA", "V:RAIN", "V:UMBRELLA")
    show(
        "14 scoped actor schema",
        actor_nodes,
        (
            SL("U:RAIN"),
            SL("U:UMBRELLA", ("U:RAIN",)),
            SL("V:UMBRELLA", ("V:RAIN",)),
        ),
        [("U:RAIN", "U:UMBRELLA")],
        enforce_actor_scope=True,
    )
    malformed_actor_graph = (
        SL("U:RAIN"),
        SL("U:UMBRELLA", ("U:RAIN",)),
        SL("V:UMBRELLA", ("U:RAIN",)),
    )
    show(
        "15 raw SL evaluator propagates misindexed actor edge",
        actor_nodes,
        malformed_actor_graph,
        [("U:RAIN", "U:UMBRELLA", "V:UMBRELLA")],
    )
    expect_rejection(
        "15b actor schema rejects misindexed edge",
        lambda: validate_actor_scope(malformed_actor_graph),
        "undeclared cross-actor dependency",
    )
    expect_rejection(
        "16 graph schema rejects undeclared reference",
        lambda: validate_graph(("A",), (SL("A", ("MISSING",)),)),
        "undeclared node reference",
    )


if __name__ == "__main__":
    main()
