# Memora audit protocol provenance and amendments

## Record status and chronology

This file is a **post-execution public-safe protocol record**, created on
2026-08-29 after the first source execution and release-wide audit. It is not
itself a contemporaneously public preregistration.

A privately held working-continuity protocol was frozen earlier on 2026-08-29,
before any Memora source test or dataset-wide audit was run. The private source
is not published, quoted wholesale, or redistributed here. This file instead
preserves its questions, hypotheses, fixtures, controls, falsifiers and claim
ceiling at public-safe claim-level granularity, then separates the controls and
interpretive boundaries added after execution and independent review.

The preserved order is:

1. private pretest freeze;
2. initial exact-source execution and release census;
3. construction of the checked public artifact; and
4. post-execution reviewer-driven amendments recorded below.

All four events occurred on 2026-08-29 in Asia/Singapore. Exact same-day clock
times are not asserted. The public file's later creation must not be used as
evidence that its amended wording existed before execution.

## Public-safe reconstruction of the pre-execution commitments

### Locked evidence identities

- Paper: *From Recall to Forgetting: Benchmarking Long-Term Memory for
  Personalized Agents*, [`arXiv:2604.20006v1`](https://arxiv.org/abs/2604.20006v1).
- Paper PDF SHA-256:
  `683a21a6b6fa09f1a6ad270832b3d891e41ecff6e6893298d8efe0df702566b2`.
- Official source:
  [`geniesinc/Memora`](https://github.com/geniesinc/Memora).
- Current revision under test:
  `a6493188efc836d6511ed5e4163fe3ba87da30ff`.
- Historical comparison revision, required to be the current revision's direct
  parent: `e19ebbd1089465876dca11b09e70256977f9755f`.
- The current revision is a post-paper repair. Neither revision was assumed to
  be the paper-production revision without a separate exact run-provenance
  record.
- The official checkout had to be exact and clean before source execution;
  support files and outputs had to remain outside it.

### Frozen Q1 — Track-2 judge-protocol binding

Question: does the executable Track-2 path bind the declared three-judge
majority protocol, or can judge discovery or initialization silently degrade
it?

Pre-execution hypotheses:

- At the historical revision, the production path would append the nonexistent
  `evals/agent_eval/model_eval` directory; the import would fail; and the
  caught failure would set `use_multi_judge=False`.
- At the current revision, the production helper would resolve the existing
  `evals/model_eval` directory and import `OpenRouterClient` without requiring
  credentials or network at import time; strict failure handling would raise
  instead of emitting a single-judge result.
- At the current revision, 0/3, 1/3 and 2/3 initialized judges would all fail
  the declared three-judge protocol; only 3/3 would satisfy its initialization
  cardinality.

Falsifiers were a historical import that resolved through another in-tree
mechanism, or a current strict path that permitted a partial cardinality to
continue.

The frozen question was Track-2 initialization binding. It did not pre-specify
the later Track-1 initialization matrix, the two runtime-valid-judge matrices,
or an exact `api_client.__file__` origin assertion.

### Frozen Q2 — FAMA arithmetic and denominator policy

Question: do both released FAMA implementations match the paper equation over
the bounded valid integer matrix, and are their boundary policies explicit?

The frozen matrix contained every total from 0 through 6 and every
non-negative corresponding correct count satisfying `correct <= total`:

```text
FAMA = max(0, MPA - lambda * (1 - FAA))
MPA = presence_correct / presence_total
FAA = absence_correct / absence_total
lambda = absence_total / (presence_total + absence_total)
```

Pre-execution hypotheses:

- For mixed non-empty fixtures, both Track-1 and Track-2 functions would equal
  an independent standard-library oracle within `1e-12` and stay in `[0,1]`.
- Holding presence counters fixed, decreasing correct forgetting-absence
  criteria by one would never increase FAMA.
- The released implementation would use explicit policies of `0` when
  `presence_total == 0` and `FAMA = MPA` when `absence_total == 0`; those
  source policies would be reported separately if the paper did not state
  them.

Arithmetic mismatch, an out-of-range result, a monotonicity violation,
Track-1/Track-2 divergence, or implicit/exceptional empty-bucket behavior was a
falsifier. The frozen protocol excluded invalid counters; it did not
preregister a `correct > total` direct-function probe.

The freeze fixed the underlying 784 valid inputs. It did not pre-count or name
the later 729/55 evidence-domain partition, and it did not define the paper
equation's independent oracle over a zero denominator.

### Frozen Q3 — released composition and aggregation geometry

Question: what question/criterion population is released, which denominator
and penalty geometry does it encode, and how does the released aggregator
combine FAMA values before any new model output exists?

Pre-execution hypotheses and controls required:

- Every released question and criterion would have an identity unique in its
  declared scope, and every criterion would use a recognized presence or
  forgetting-absence type.
- The full released population would be enumerated by period, persona, task
  and question without sampling or silently dropping unknown rows.
- For each non-empty question, the mechanically derived penalty weight would
  be `N_forget / (N_presence + N_forget)`.
- The aggregation hypothesis predicted an equal mean of per-question FAMA
  within a subject/task/period bucket, rather than a criterion-level
  micro-average.

Unknown types, missing identities, duplicate scoped identities, unreadable
files, unaccounted rows, or source aggregation inconsistent with that
hypothesis were falsifiers.

### Frozen Q4 — one paper-authored forgetting-semantics tension

The pre-specified paper anchor was Appendix D.2, physical PDF pages 23–24. The
desired answer says the user is `leaning away from James Stewart`; the adjacent
expected-No criterion uses the surface `reflect or mention ... James Stewart`.

The frozen hypothesis was limited to one written mention-versus-reliance
tension. It did not authorize an inference about a real judge verdict,
dataset-wide semantic prevalence, an aggregate effect, or paper invalidity.
Failure to verify the answer/criterion pairing, or an explicit contrastive-use
exception in the criterion, would falsify it. String counts could be used only
for mechanical discovery, not semantic classification.

### Frozen Q5 — release/result provenance boundary

The pre-execution hypothesis was that the locked release contained question,
data and evaluator surfaces but no checked provenance-bearing
`eval_report_*` population sufficient to reconstruct Table 3 without new model
or judge outputs. Finding a complete checked result population mapped to the
paper table would falsify it.

### Frozen fixtures and controls

The pre-execution fixture set comprised:

1. the exact current and direct-parent revisions;
2. the two selected official offline test files;
3. source-level Track-2 judge-path probes with no client construction, API key
   read or network call;
4. Track-2 synthetic initialization cardinalities 0/3 through 3/3;
5. the exhaustive valid FAMA matrix with totals 0 through 6;
6. the complete released evaluation-question population;
7. the released aggregator plus unequal-weight synthetic rows;
8. the paper pages containing the FAMA equation and Appendix D.2 objects; and
9. a complete inventory of declared checked-result locations.

Controls required exact revision and clean-worktree checks, no credentials or
model/backend/network calls, separate historical/current identities, an
independent arithmetic oracle, loud rejection of unknown release rows,
macro-versus-micro aggregation controls, PDF text plus rendered-page checking,
separate raw/derived claims, and reproducible checked public outputs.

The frozen audit could not pass without exact source identity, captured
selected official tests, complete valid-matrix execution, a full released-file
reconciliation, every frozen Track-2 initialization treatment, verified paper
locators, complete result-location inventory, and a public verifier capable of
checking identity, completeness and hashes without model/API access.

## Post-execution status of the frozen questions

This section records results; it is not part of the pretest freeze.

| Frozen question | Post-execution status |
| --- | --- |
| Q1 Track-2 binding | Supported with a scope qualification: historical fallback and current strict 3/3 behavior were observed, while non-strict mode still explicitly degrades. |
| Q2 valid FAMA arithmetic | Supported on the frozen 784 valid inputs once paper-equation and source-only zero-bucket evidence were separated as described in the amendment below. |
| Q3 released composition | Supported with identity qualification: file-local and composite `(period, persona, id)` identities are unique, while bare IDs collide across files. |
| Q3 aggregation hypothesis | **Not supported as the exact executable aggregation contract.** Current `aggregate_table3` averages report-level task FAMA rows; it coincides with a per-question mean only under additional complete equal-question geometry. |
| Q4 paper example | Supported only as the pre-specified one-example wording tension. |
| Q5 release boundary | Supported: no checked response/report population sufficient for model-free Table-3 reconstruction was found. |

## Post-execution amendments — 2026-08-29

These amendments were added after source execution and reviewer inspection.
They are not represented as preregistered gates.

### A1 — FAMA oracle-domain and interpretation amendment

Review found that reporting all 784 valid tuples as matches to the paper
equation attributed released-source zero-bucket conventions to prose that does
not define them. The checked artifact now partitions the unchanged 784 inputs
into:

- 729 `paper_equation_domain` fixtures, with both denominators positive and an
  independent `Fraction` implementation of the reported equation; and
- 55 `source_zero_bucket_extensions`, checked against separately encoded
  conventions observed in the two released functions.

This changed the oracle scope and result-interpretation boundary after review.
It did not change the underlying 784 frozen valid inputs, the mixed-non-empty
arithmetic hypothesis, or the claim ceiling. The paper-equation oracle now
rejects zero-denominator use instead of defining it.

### A2 — fresh current import-origin and shadowability amendment

A fresh guarded child-process probe was added with no initially cached
`api_client`. It records and requires both `api_client.__file__` and the
`OpenRouterClient` class source to resolve to
`evals/model_eval/api_client.py`.

A static companion receipt records that upstream uses `sys.path.append` plus
`from api_client import OpenRouterClient`. A pre-cached module or an earlier
`sys.path` entry can therefore still shadow the intended file. The selected
official regression test asserts the returned class name, not its source
origin. This origin/shadowability contract was not part of the frozen Q1
falsifier.

### A3 — additional judge matrices

The Track-1 initialization matrix and both tracks' 0/1/2/3-valid-runtime-judge
matrices were added after execution to characterize adjacent current-source
contracts. They use exact upstream class control flow with deterministic fake
clients; they do not construct a real backend client or estimate production
failure rates.

### A4 — invalid direct-function probe

The invalid direct-function probe `(3,2,0,0)` was added after execution even
though the frozen matrix deliberately excluded invalid counters. It is kept as
a separately labeled exploratory standalone-function observation. It is not a
frozen completeness gate, a released call-site input, or benchmark output.

### A5 — decision, reproduction and regression-gate naming

`raw/decision.json` evaluates one fresh run only. It cannot itself establish
two-run byte identity or checked-package acceptance. Package acceptance also
requires `raw/reproduction.json` and a passing `verify_checked.py` over the
installed package and reader-supplied exact evidence.

Exact observed release totals, collision counts, output hashes and the
post-execution amendments above are checked-candidate regression gates. They
protect the installed artifact from drift; they were not pretest falsifiers.

## Current checked-package acceptance

The amended package is accepted only when all three layers pass:

1. `raw/decision.json` reports single-run completeness;
2. `raw/reproduction.json` records byte-identical primary receipts from two
   fresh runs in the stated same-machine environment; and
3. `verify_checked.py` validates the exact external source/PDF identities,
   installed hashes, protocol provenance, raw logic and reproduction receipt.

## Claim ceiling

Permitted claims remain limited to exact-revision source behavior, selected
official offline tests, synthetic contract observations, released-input
composition, one paper-authored specification tension, and the locked-release
result boundary.

This is not a benchmark reproduction. It generates no conversation, memory,
answer, judge verdict or Table-3 cell; compares no models or memory systems;
estimates no effect or semantic prevalence; does not establish the
paper-production source revision; and cannot support “Table 3 is wrong” or
“the paper is invalid.”
