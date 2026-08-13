# Doyle TMS static SL oracle

This is a small, paper-facing reconstruction used while close-reading Jon Doyle's
1979 *A truth maintenance system*. It is public, synthetic, system-agnostic, and
uses only the Python standard library.

Run it from the repository root:

```bash
python3 research/doyle-tms-static-oracle/oracle.py
```

The checked-in raw stdout is in [RESULTS.txt](./RESULTS.txt). Every printed model
or schema rejection is also an assertion, so a mismatch exits non-zero.

## What it computes

For each 1–6 node graph, the runner enumerates every `IN/OUT` assignment. It
retains assignments in which the `IN` nodes are exactly those with at least one
valid support-list justification, then requires every `IN` node to have a finite
positive proof. Negative antecedents are status checks, not positive foundations.

That makes this a history-free static model oracle for the declared fixtures. It
does not implement Doyle's incremental Steps 1–7, current supporting-justification
selection, supporting witnesses for `OUT` nodes, CP/FIS execution, signals,
justification retraction, dependency-directed backtracking, or performance.

## Why fixtures 11–13 are paired

Fixture 11 materializes a summary support that agrees with a raw path at creation.
After a new disqualifier appears, fixture 12 explicitly keeps that support under a
`persist-derived-SL` policy, while fixture 13 explicitly retires it under a
recompute policy.

The comparison does not show that Doyle's FIS or proposed `SUM` form naturally
creates a stale summary. It shows that creation-time dependency equivalence does
not choose the later lifecycle for us. A system must declare whether an
abstraction is a lossless projection, a recomputable view, or a durable
generalization with independent warrant.

## Actor boundary

Fixture 15 demonstrates that a raw SL evaluator will follow a misindexed
cross-actor rule if the rule is supplied. Fixture 15b demonstrates the separate
enclosing-system responsibility: an actor-schema validator can reject that edge
unless a bridge is explicitly declared. Core support semantics do not independently
validate external actor meaning, but the surrounding system is not prevented from
doing so.

## Limits

- This is not the original Lisp implementation or a reproduction of the paper.
- The two negative-loop models are admissible assignments, not two observed runs.
- The meeting fixtures expose a backtracking precondition and an externally
  supplied denial; they do not implement nogood construction or culprit choice.
- The abstraction lifecycle and actor-schema checks are editorial test policies,
  not claims made or tested by the paper.
- The runner provides no evidence about a private or production memory system.
