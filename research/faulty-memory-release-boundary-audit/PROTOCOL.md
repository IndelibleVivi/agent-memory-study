# Faulty-memory current-release boundary audit: frozen protocol

Status before formal independent execution:
`source_inspected_official_gates_run_frozen_not_run`.

This protocol freezes a deterministic, model-free audit of the exact current
public release associated with *Useful Memories Become Faulty When Continuously
Updated by LLMs*. It was written after the full paper close read, source/schema
inspection, a targeted hydration of selected public AppWorld pool fixtures,
and execution of the release's own arithmetic verifier, demo, and lightweight
test suite—but before formal execution of the independently authored checker.
It is therefore registered against checker execution, not blinded to the paper
or release. Results must be written to separate receipts and must not be
back-edited into this protocol.

## Locked evidence objects

- Paper: Dylan Zhang et al., arXiv `2605.12978v1`, dated 2026-05-13.
- Reviewed 69-page PDF SHA-256:
  `16613d73b3dfe8de8dd73d42c4fb7b2e803b84a78d7ecf748c9e23a7e3b4aa92`.
- Official public source:
  [`DylanZSZ/Memory-Collapse-Eval`](https://github.com/DylanZSZ/Memory-Collapse-Eval)
  at exact commit `adf347f67a81a19fc71d2529d09108c71a1f9712`.
- The locked checkout has one root commit dated 2026-08-15 and no local Git
  tag. The repository contains later experiment/archive dates and no receipt
  binding this commit to the paper's production revision. The target is thus
  `exact current public release`, never `paper-time source`.
- Selected inputs are locked by Git blob OID and SHA-256. The artifact copies
  no upstream rows, source, trajectories, memory snapshots, or paper PDF.

Evidence vocabulary is fixed:

- statements and numbers in the paper are `paper-reported`;
- repository bytes and documentation are `exact-current-source`;
- the upstream verifier/demo/tests are `official-source execution`;
- calculations over the 55,075 released JSONL rows are `released-row audit`;
- pool comparisons establish `shipped-fixture conservation` only;
- joins between paper wording and current-source facts are `editorial
  inference`; and
- absent model/environment runs remain `not run`, not negative results.

## Primary question

> At the exact current public revision, are all registered arm summaries
> internally consistent with the released rows under explicit membership and
> missingness rules, what portion of that surface is actually protected by the
> upstream 675-assertion verifier, and do the selected AppWorld schedule
> fixtures conserve full episode content rather than task IDs alone?

The audit has eight gates. A numeric execution may pass while an associated
paper/public claim still requires revision; these are separate decisions.

## Gate 1: exact source and input lock

Require the exact source commit, clean tracked status before and after, exact
paper digest, and exactly six result directories containing `arms.csv`. Hash
only decision-relevant inputs: six `arms.csv`, six merged JSONL files, thirteen
mapped number tables, the upstream verifier and relevant READMEs, the selected
schedule fixtures, three exception fixtures, and the Makefile whose direct
path-with-spaces invocation was observed.

Do not hash excluded trajectories, memories, binary snapshots, or unrelated
repository files. Commit/tree identity already protects tracked bytes; whole
repository re-hashing would not advance the question.

## Gate 2: exhaustive arm and row membership

Freeze the expected release totals:

| Experiment | Arms | JSONL rows |
| --- | ---: | ---: |
| ALFWorld | 48 | 4,320 |
| ScienceWorld | 30 | 1,500 |
| WebShop | 391 | 19,550 |
| AppWorld | 212 | 10,365 |
| ARC stream/self-eval | 48 | 2,840 |
| ARC 200-task stream | 33 | 16,500 |
| **Total** | **762** | **55,075** |

Row identity is environment-specific:

- ALFWorld, ScienceWorld, WebShop: `(arm, idx)` because invalid/refusal rows
  can omit task identifiers;
- AppWorld: `(arm, task_id)`; and
- ARC: `(arm, sample, task_id)`.

Require unique arm IDs, exact `arms.csv`/JSONL arm-set equality, complete and
unique row identities, Boolean success types, constant per-arm metadata, and
metadata agreement with `arms.csv`. Independently recompute every interactive
arm's `n_tasks`, `n_valid`, and `n_success`; for every ARC arm recompute
`n_samples`, `n_tasks`, `n_rows`, `n_success`, and require identical task sets
across samples plus a rectangular sample-by-task grid.

Only canonical digests of the full arm and identity ledgers enter the public
receipt; upstream free text does not.

## Gate 3: missingness and denominator observability

Validity is declared by environment, not guessed from whichever key happens to
exist:

- ALFWorld, ScienceWorld, WebShop require a non-empty `task_name`, no `error`,
  and no `skipped` flag;
- AppWorld requires a non-empty `task_id`, no `error`, and no `skipped` flag.

Invalid/refusal rows are observed missing outcomes. They must never be
relabelled as failures. For every arm with `n_tasks != n_valid`, emit both
`n_success / n_tasks` and `n_success / n_valid`, their exact percentage-point
delta, and the missing-row count.

Reconnaissance registered 304 such rows—ALFWorld 11, ScienceWorld 288,
WebShop 5, AppWorld 0—across 40 arms. The expected maximum sensitivity is
ScienceWorld `eval/letta_N400`: `18/50 = 36%` versus `18/32 = 56.25%`, a
20.25-point difference. These are expected release observations, not reasons
for the execution gate to fail.

## Gate 4: upstream verifier execution and scope

Execute the exact `results/verify_numbers.py` unchanged and require its summary:

```text
reproduced 675 cells, 0 mismatched, 0 with no rows
```

Separately instrument the exact locked module's declared `CHECKS` and mappers
for coverage accounting. This is not presented as an independent
reimplementation of the 675 numeric calculations; Gate 2 supplies the
independent all-arm aggregates.

Freeze:

- 13 mapped CSV files and 259 CSV data rows;
- 675 numeric assertions;
- exactly two allowlisted ALFWorld requested-arm fallbacks;
- 335 unique resolved arms;
- 33,956 raw and 33,658 valid rows belonging to those arms; and
- 27 wholly unmapped `numbers/*.csv` files containing 511 data rows.

The checker must distinguish assertions, unique arms, and rows. It must reject
silent mapper/table shrinkage; an upstream result of “0 assertions, 0
mismatches” is not success.

## Gate 5: selected AppWorld schedule conservation

Register only the schedule comparison represented by
`numbers/ACE重排_排序对N-grid.csv`:

- reference `stream_pool_v2.jsonl`;
- `pool_A.jsonl`;
- `pool_B.jsonl`; and
- `pool_succdrop.jsonl`.

Each selected variant must contain 200 rows and 200 unique task IDs, preserve
the exact full canonical-JSON row multiset of the reference, and change the
ordered task-ID vector. ID-only equality is insufficient because it would miss
changed trajectory or description content.

Register, but exclude from the pure-permutation claim:

- `pool_D`: same IDs/order but 200 modified task descriptions;
- `pool_drop50`: a 150-row subset; and
- `pool_replay2`: the natural 200-row pool repeated twice.

Passing this gate establishes shipped-fixture conservation only. `arms.csv`
does not store pool digests, so result-to-pool lineage remains naming/code
evidence rather than a cryptographic historical run binding. No causal schedule
effect follows from fixture equality plus outcome differences.

## Gate 6: registered curve descriptions

Before execution, register exactly:

- the seven ScienceWorld methods in `trend_8methods.csv` at
  `N100/N200/N300/N400`; and
- the four AppWorld ACE schedule curves in
  `ACE重排_排序对N-grid.csv`: current, A, B, and succdrop.

Every point must record its exact arm, checkpoint, successes, task and valid
denominators, exact rational rates, and full/valid evaluation-identity-set
digests. Report adjacent direction, first-to-last and peak-to-final deltas,
monotonicity classification, denominator-direction agreement, and whether task
sets are fully paired.

Do not require curves to decline. Shape is an observation, not a pass
criterion. In particular, `aceB_N25` is registered with 49—not 50—rows and must
be marked unpaired relative to its later checkpoints. Do not compute p-values,
bootstrap task rows as experimental repeats, or infer causal collapse.

## Gate 7: mutation controls

All mutations operate on in-memory copies and never alter upstream files. The
checker must detect or correctly handle the following registered cases:

1. duplicate an interactive row identity;
2. delete a mapped failure row while its success count is unchanged;
3. delete an invalid/refusal row;
4. delete an unasserted arm together with its `arms.csv` row;
5. change one `arms.csv` denominator;
6. replace Boolean `false` with string `"false"`;
7. add null `task_name` to a valid AppWorld row without making it invalid;
8. delete one ARC sample-task cell;
9. shrink mapped tables to headers;
10. permit an unregistered fallback arm;
11. change pool content while preserving task IDs;
12. delete one pool row and duplicate another;
13. relabel assertion count as unique-arm count; and
14. relabel an observed missing outcome as an observed failure.

Each negative control must fail with its registered code; the AppWorld validity
case is a positive regression control.

## Gate 8: two-root repeatability

Run A uses `PYTHONHASHSEED=313` and traversal seed 313. Run B uses 727 for both.
The traversal seed must actually shuffle row aggregation order; all stable
outputs are then canonicalized and sorted. Original schedule order is preserved
because it is itself evidence.

Both runs must use fresh output roots on external storage. Stable
`audit.json` and `mutation-controls.json` must be byte-identical. Run-specific
environment receipts remain separate and are not compared. This establishes
same-machine checker repeatability and stale-output exclusion, not
cross-platform reproduction.

## Stop conditions and claim ceiling

Stop with `FAIL` on any source/digest/status mismatch, missing registered input,
membership or aggregate mismatch, ARC grid break, official-verifier nonzero
result or assertion shrinkage, selected-pool non-permutation, missed mutation,
or two-root byte difference. Use `INCOMPLETE`, not `PASS`, if a registered pool
fixture is unavailable.

If every gate passes, the strongest permitted conclusion is:

> At exact current public commit
> `adf347f67a81a19fc71d2529d09108c71a1f9712`, all 762 arm summaries are
> internally consistent with 55,075 released rows under explicit
> environment-specific membership and missingness rules; the upstream 675
> assertions pass but resolve to 335 arms; the selected four shipped AppWorld
> schedules conserve one 200-episode payload while changing order; and two
> same-machine fresh runs of the independent checker are byte-repeatable.

It may not establish paper-production identity, benchmark/model/environment
rerun, semantic correctness of stored outcomes, historical execution replay,
causal schedule effects, statistical significance, cross-platform portability,
security impact, production reliability, or real-user generalization.

Code remains subject to the upstream MIT grant and released experimental data
to the repository's CC BY 4.0 data terms, with third-party benchmark/model
boundaries preserved. This independently authored AMS artifact receives no new
license grant; its license status remains `pending_owner_choice`.
