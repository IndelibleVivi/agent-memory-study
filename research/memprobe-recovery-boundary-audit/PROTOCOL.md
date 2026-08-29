# MEMPROBE released-artifact consistency and recovery-boundary audit protocol

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: plan
- Origin Date: 2026-08-29
- Verification Status: FROZEN_UNVERIFIED
- Version Label: code_plan_v2_oracle_amended

## Record status and chronology

This is a pre-execution protocol for an independently authored deterministic
audit of the released MEMPROBE artifacts. Paper reading, exact-source
inspection, schema reconnaissance, and rights review preceded this record. A
recoverable Oracle pretest review then returned `REVISE THEN FREEZE`; its P0
amendments are incorporated here. The audit runner and checked results do not
exist at this point in the history.

The protocol is therefore not a blinded prediction about an unseen release.
Here, `independently authored` means that the checker will not import or execute
upstream scorer, attribution, runner, agent-wrapper, or helper functions. It
does not mean source-independent, blinded, or statistically independent. This
record freezes the questions, joins, schema adapters, controls, decision rules,
and claim ceiling before the runner is authored or executed. Results must be
written to separate receipts and must not be back-edited into this protocol.

## Locked evidence objects

- Paper: *MEMPROBE: Probing Long-Term Agent Memory via Hidden User-State
  Recovery*, [`arXiv:2606.24595v1`](https://arxiv.org/abs/2606.24595v1), a
  preprint submitted on 2026-06-23.
- Paper PDF: 32 physical pages; SHA-256
  `e5b3699c00a0731cc00e165f12efb755c57886058e311c01e5643df6e56897b5`.
- Official release: [`sora1998/MemProbe`](https://github.com/sora1998/MemProbe)
  at exact revision `19bb83644b082489b4e181e59f1cded1a00d0529`.
- The exact revision is current `main` at protocol time. It has no tag or
  GitHub Release, so the commit is the release identity.
- Top-level MemProbe code and generated benchmark artifacts are released under
  CC BY 4.0. Vendored A-Mem, Mem-T, external taxonomies, model weights, and API
  services retain their own terms. The audit will not redistribute vendored
  source, model weights, full transcripts, full memory dumps, or hidden banks.

Evidence vocabulary is fixed:

- claims in the paper are `paper-reported`;
- paths, code, and JSON at the locked commit are `official-source` or
  `released-artifact` observations;
- recomputation over fixed released JSON is `fixed-artifact recalculation`;
- newly written controls are `synthetic contract tests`;
- human interpretation is `editorial inference`;
- stored slot-fill, judge, disclosure, and attribution outputs remain
  `historical LLM artifacts`, never model-free ground truth.

## Research question, edge vocabulary, and population

The audit asks:

> Which cross-artifact identities and deterministic reductions can be verified
> at the locked release, and which historical execution edges remain
> unobservable?

The following edge results are normative. A checked result may not silently
promote a weaker status to a stronger one:

| Edge | Permitted result |
| --- | --- |
| hidden-bank target ↔ task/reconstruction target fields | `VERIFIED_JOIN` / `FAILED_JOIN` |
| stored retrieve-packet item ↔ designated final-store item | `EXACT_MEMBER`, `AMBIGUOUS_MEMBER`, or `NO_MATCH` |
| final store ↔ target-specific semantic write success | `NOT_TESTED` |
| full store or packet ↔ exact historical slot-fill payload | `UNVERIFIABLE_FROM_RELEASE` unless an exact released payload hash exists |
| stored prediction ↔ exact historical slot-fill response | `UNVERIFIABLE_FROM_RELEASE` |
| stored judge result ↔ exact historical judge request/response | `UNVERIFIABLE_FROM_RELEASE` |
| task/history episode ↔ stored attribution inputs | `PARTIALLY_BOUND` when the episode exists but no exact prompt/input hash exists; otherwise `UNBOUND` |
| stored attribution stages → stored attribution label | `REDUCTION_CONSISTENT` / `REDUCTION_INCONSISTENT` |
| historical retriever execution | `NOT_REPLAYED` |

The registered population is exhaustive, not sampled:

- 50 released synthetic users;
- 31 hidden dimensions per user in the declared `7/7/7/5/5` categories;
- the exact run registry `nomem_pooled_50`, `amem_pooled_50`,
  `amem_pooled_50_retrieve`, `longctx_full_pooled_50`,
  `longctx_full_pooled_50_retrieve`, `mem0_pooled_50`,
  `mem0_pooled_50_retrieve`, `memt_memonly_pooled_50`, and
  `memt_memonly_pooled_50_retrieve`;
- every released final-memory, reconstruction, attribution, task, history, and
  aggregate-report object needed by the registered joins.

No fresh simulator, assistant, memory writer, retriever, slot filler, judge, or
attribution model will run. Historical retrieval will not be reissued. The
audit must not read an API key, contact a model endpoint, start vLLM, or install
the upstream environment.

## Q1 - release census and target identity

For every user, require one 31-dimension hidden bank and one 31-task file.
Within a user, the five bank categories must contain exactly `7/7/7/5/5`
distinct dimension names, and the tasks must target exactly that same set once
each.

For every released reconstruction and attribution file, require 31 details.
The primary key is
`(run_id, system_variant, scoring_mode, user_id, category, dimension)`.
Path-derived run identity must agree with the registered system and internal
scoring mode. Each of the nine registered runs must contain exactly 50 × 31
unique keys, with no unregistered run, user, category, or dimension.

Require an exact typed value-level join on `user_id`, category, dimension, the
benchmark hidden target stored in the literal source field `ground_truth`, the
hidden explanation, and declared scoring mode. Public prose will call this a
`benchmark hidden target`, not unqualified ground truth.

For every target, also require its task index to resolve to the same numbered
history episode in the applicable base run, with exact `user_id` and task-text
equality. This is an identity/linkage check over locally held source. Task text
and episode content are denied from public receipts.

Attribution-copy equality means recursive typed equality of every
reconstruction field after removing only the added `attribution` member. Any
omitted, added, or changed nested packet value is a mismatch. Dictionary key
order is irrelevant; key presence, value type, list order, and nested values
are exact. Booleans are never equal to numbers, and integer and decimal JSON
representations are not coerced.

Unknown categories, missing or duplicated dimensions, target drift, unreadable
JSON, absent users, unregistered extra users, or a non-identical attribution
copy falsifies the affected completeness gate. A bare dimension name is scoped
by run, user, and category; the audit must not invent a wider identity.

## Q2 - fixed-score arithmetic

Raw JSON decimals must be parsed losslessly. Every stored score must exactly
equal one of `{0, 0.25, 0.5, 0.75, 1}` before arithmetic. The independently
implemented checker will convert the decimal representation to
`fractions.Fraction`, recompute exact category means over the registered
`7/7/7/5/5` dimensions, and compute `overall` as the unweighted exact mean of
the five registered category means. Stored per-category and overall values are
checked first; conversion to a binary float occurs only for comparison with a
stored float, under the frozen absolute tolerance `1e-12`.

Recompute across-user exact means and sample standard deviations using the
exact 50 per-user records and denominator `n - 1`. Compare those values only
with aggregate reports that contain
exactly the registered 50-user set and whose embedded per-user reconstructions
match the canonical `recon_judge` files. Partial reports and one-user shards are
inventoried but never summed or silently selected as canonical. When more than
one 50-user report exists, every matching candidate and its digest remain
visible; the audit does not choose by filename recency. An absent aggregate is
`REPORT_ABSENT`, not an arithmetic mismatch and not permission to select a
partial report. A paper table comparison must name the exact table/cell and its
displayed rounding; it remains a descriptive cross-check.

This is recomputed arithmetic over released historical judge scores. It does
not re-evaluate
semantic correctness, model behavior, run-to-run uncertainty, significance, or
the approximately `0.6` headline as fresh evidence.

## Q3 - stored top-k packet membership in the designated final dump

Every retrieve detail must contain a list-valued `retrieved_memories` packet of
at most five items. An empty or short packet is recorded, not converted into an
error. The registered adapter table is closed:

| System | Retrieve run | Designated store run | Store / packet pointers | Exact typed match contract |
| --- | --- | --- | --- | --- |
| A-Mem | `amem_pooled_50_retrieve` | `amem_pooled_50` | `memory/<store>/<user>/memories.json#/memories`; `output/<retrieve>/recon_judge/<user>.json#/details/<i>/retrieved_memories` | packet keys must be exactly `id,content,keywords,context,tags,category,score`; `score` is retrieval-only; match on exact `id` + exact `content`; other packet fields are retained as observed metadata because released store `category` is not invariant |
| LongCtx | `longctx_full_pooled_50_retrieve` | `longctx_full_pooled_50` | same pointer pattern | packet minus exactly the numeric retrieval-only `score` member must be recursively identical to one store item; allowed key sets are `content,category,task_index` with optional `turn` on both sides |
| Mem0 | `mem0_pooled_50_retrieve` | `mem0_pooled_50` | same pointer pattern | complete packet dictionary must be recursively identical to one store item; no field is removed |
| Mem-T | `memt_memonly_pooled_50_retrieve` | `memt_memonly_pooled_50` | same pointer pattern | packet keys must be exactly `id,content,category,score,timestamp`; `score` must be JSON null; match exact `id`, packet `content` to store `metadata.memory_content`, exact `category`, and exact `timestamp` |

No runtime schema inference, fuzzy matching, trimming, case-folding, Unicode
normalization, string parsing, list reordering, numeric coercion, or
Boolean/number equivalence is permitted. An unrecognized key set or type is a
schema failure, not an invitation to add a fallback. Dictionary key order alone
is irrelevant.

Two results are reported separately:

1. `packet_membership_complete`: every non-empty item has at least one exact
   match in its designated store;
2. `packet_unique_binding`: every non-empty item has exactly one exact match.

Zero matches is `NO_MATCH` and blocks the fixed-artifact audit. Multiple matches
is `AMBIGUOUS_MEMBER`; membership may pass, but the public artifact may use the
word `lineage` only if unique binding passes across the complete population.
Packet order, cardinality, IDs, hashes, match count, and every candidate store
pointer are recorded.

Semantic relevance is outside the mechanical gate: exact store membership does
not prove support for the benchmark target, sufficiency for reconstruction, or
absence of semantically equivalent evidence elsewhere. The release contains
JSON final dumps but no native retriever snapshots, so historical retrieval is
`NOT_REPLAYED`; the audit does not show that current code returns the stored
packets or that a stored packet was the exact historical prompt payload.

## Q4 - stored attribution reduction consistency and input observability

This is a current-source conformance property, not an independent causal
judgment. The checker must not import or call `failure_attribution.py`. It must
apply this frozen declarative table to strict typed JSON values:

| Condition and legal stage sequence | Required stored label |
| --- | --- |
| exact rubric score `>= 0.75`; `stages` is exactly empty; no later-stage payload | `ok` |
| score `< 0.75`; Stage 0 is exactly `oracle` with strict Boolean `can_invite: false`; no trailing stage | `task_design_failure` |
| score `< 0.75`; Stage 0 `can_invite: true`; Stage 1 is exactly `disclosure` with strict Boolean `disclosed: true`; no trailing stage | `memory_failure` |
| score `< 0.75`; Stage 0 true; Stage 1 false; Stage 2 is exactly `disclosure_subclass` with exact `category: "A"` | `agent_elicitation_failure` |
| same three-stage prefix with exact `category: "B"` | `simulator_too_strict` |
| same three-stage prefix with exact `category: "?"` | `unclassified` |

Stage names, order, count, required fields, and permitted extra explanatory
string fields are validated. Truthy coercion, malformed Booleans, unknown
stages, missing stages, and trailing stages fail the reduction gate. Threshold
behavior at exactly `0.75` is tested. A `no_targeted_task` branch is inventoried
but contradicts a passing Q1 population because every dimension must have one
targeted task; it cannot be accepted as an ordinary successful branch.

For every attribution row, separately record the designated task file and
index, designated base history run, episode path/hash, episode existence,
task-text equality, and whether the transcript has at least one non-empty
agent/user turn. Also record whether an exact released prompt/input hash binds
the stored stage to that episode. Where the episode exists but no such hash
does, the row is `HISTORICAL_INPUT_UNVERIFIED` and at most `PARTIALLY_BOUND`.

`memory_failure` is never accepted as a causal ground-truth label. Current
source explicitly aggregates write and read loss, while the released record may
also reflect slot-fill phrasing, judge interpretation, serialization, context
budget, or missing prompt observability. Public fields must be qualified as
`stored_attribution_label`, `stored_disclosure_verdict`, and
`stored_task_design_verdict`.

The `nomem` rows are a negative control for causal over-reading: their labels
may be reduction-consistent while still not establishing that the LLM-assigned
categories are true causes.

## Q5 - stored-output observability and paired historical artifact deltas

For predictions, slot-fill reasons, judge reasons, and rationales, preserve the
raw typed value and classify separately as `FIELD_ABSENT`, `NULL`,
`EMPTY_STRING`, `WHITESPACE_ONLY`, `NONEMPTY_STRING`, or `WRONG_TYPE`.
Additionally record `EXACT_LITERAL_UNKNOWN` only for the exact string
`"unknown"`; case-folded or whitespace-normalized indicators are descriptive
only and never drive a gate. Scores are separated into valid quarter-step,
missing, null, wrong-type, and out-of-rubric states.

For the same run-bound target, full-store/retrieve score and output differences
are called `paired historical artifact deltas`. They are never called a
retrieval effect, retrieval loss, or retrieval failure.

Current source can emit an `unknown` prediction with an empty reason when the
slot-fill response is empty or fails structured parsing. The released JSON does
not retain raw model responses, request IDs, prompt hashes, exact model
snapshots, or API usage receipts. The audit will therefore call the joint
`unknown` plus blank-reason pattern a `fallback-compatible artifact signature`,
not proof that one specific parser or API failure occurred.

Likewise, the default model name in current source does not establish the exact
model snapshot used for every historical output. The surface ledger is fixed:

| Surface | Model-free audit question |
| --- | --- |
| benchmark target identity | do target fields join exactly? |
| released full store | does the designated dump exist, parse, and reconcile its declared count? |
| target support in store | `NOT_TESTED` |
| stored retrieve packet | does it satisfy registered cardinality, key, and type contracts? |
| packet/store relationship | is every item an exact member, and uniquely so? |
| slot-fill output | what is the lossless presence/type/unknown state? |
| judge output | is the stored score in-rubric and arithmetic-consistent? |
| attribution | does the stored label reduce mechanically from stored stages? |
| historical causal cause | `NOT_DETERMINED` |

## Q6 - source-replay-material and documentation boundary

Inventory, without repairing, the current source paths needed to reproduce the
released artifacts:

- named analysis scripts in Appendix C / Table 7;
- rendered prompt fields claimed as released scoring artifacts;
- base-run versus `_retrieve` history lookup in `failure_attribution.py`;
- native-state save/restore paths used by memory systems;
- released history, native-state, raw-response, prompt, and usage receipts.

The runner will distinguish three machine-readable statuses:

- `worked_fixed_artifact_audit`: identity, arithmetic, exact packet/store
  matching, stored-stage reduction, controls, and deterministic receipts;
- `source_replay_material_status`: `COMPLETE`, `PARTIAL`, or `BLOCKED`, based
  only on whether the release contains the named scripts, state, prompts,
  histories, and provenance needed for replay;
- `historical_execution_replay`: fixed to `NOT_ATTEMPTED`.

An internally consistent artifact may pass the first status while replay
materials are partial. Missing named scripts or runtime state must be reported
as `NAMED_SOURCE_PATH_ABSENT`, `RELEASED_INPUT_ABSENT`, or
`RELEASED_AGGREGATE_ABSENT`, not filled with AMS-authored compatibility code and
then described as official reproduction. Arithmetic outcomes remain distinct:
`INDEPENDENT_RECALCULATION_SUCCEEDED`, `RELEASED_AGGREGATE_MATCH`,
`RELEASED_AGGREGATE_MISMATCH`, and paper-display matches or mismatches after
declared rounding.

Produce a separate historical provenance inventory for exact model snapshot,
endpoint, runtime, sampling values, request IDs, raw requests/responses,
rendered prompt hashes, retry path, dependency receipt, and usage receipt.
Every field is `PRESENT`, `PARTIAL`, or `ABSENT`; current-source defaults and
README examples may not fill historical fields.

## Pre-execution frozen, non-blinded illustrative strata

The audit will project only bounded public fields and exact official locators
for three strata:

1. `user_022 / pushback_tolerance`, all available systems and modes,
   labeled `KNOWN_PAPER_OR_RECONNAISSANCE_CASE`: a paper-identified
   directional slot-label polarity boundary;
2. `user_005 / geographic_knowledge`, `amem` full versus retrieve, labeled
   `KNOWN_PAPER_OR_RECONNAISSANCE_CASE`: a paper-identified final-store to
   actual-packet seam;
3. the lexicographically first `(system, user, category, dimension)` whose
   fixed full score is at least `0.75` and fixed retrieve score is below
   `0.75`, if one exists, labeled `RULE_SELECTED_ILLUSTRATION`.

The projection may contain only source commit, run/system/mode, synthetic
`user_id`, category and dimension identifiers, source-relative locators,
record indices, counts, packet item IDs, fixed numeric scores, enumerated
historical labels, and SHA-256 digests of denied source values. It must not copy
target or task text, predictions, explanations, rationales, evidence strings,
persona profiles, transcripts, memory content, retrieved content, prompts,
local paths, or unrelated upstream artifacts. A separate AMS-authored
schema-compatible microfixture may explain the transition vocabulary, but it
must declare `fixture_origin: "AMS-authored synthetic fixture"`,
`not_a_memprobe_record: true`, and
`not_for_benchmark_score_reproduction: true`; no continuous eight-token span
may be copied from upstream free text.

Adapters, joins, and gates must execute over the full population before case
rows are rendered. Cases may not determine severity, alter a schema/matching
rule, or supply a missing adapter. The first two strata were known from the
paper and source reconnaissance before the run; they are explanatory seams,
not discoveries or an unbiased prevalence sample. The third is selected by a
fixed mechanical rule and is likewise not representative or confirmatory.

## Controls, falsifiers, and deterministic execution

The runner must use only the Python standard library and a reader-supplied exact
checkout. It will reject a wrong Git revision or dirty official checkout before
reading release artifacts. It will install a process-local network guard and
record any attempted DNS or socket access as a failure.

Every mutation operates on an isolated deep copy. Pre/post hashes must prove
that the official checkout and original parsed objects are unchanged. The
suite must catch, and name the expected failing gate for:

- wrong retrieve-run to designated-store-run mapping;
- one absent packet item in each of the four adapters;
- same ID with changed immutable content, and changed ID with otherwise
  identical content;
- duplicate ID or duplicate exact item producing multiple matches;
- omitted required packet field, forbidden extra packet field, and one allowed
  retrieval-only `score` difference;
- Boolean/number and integer/decimal typed substitutions;
- changed run, user, category, dimension, benchmark target, explanation, or
  scoring mode; duplicated and cross-run-swapped reconstruction rows;
- every legal attribution branch plus wrong stage order, malformed Boolean,
  unknown stage, extra trailing stage, immediately-below-threshold and exact
  `0.75` cases;
- changed category mean, overall mean, across-user mean, and sample standard
  deviation; missing, null, wrongly typed, and out-of-rubric scores.

Each control must also confirm that unrelated gates remain stable. The runner
must not mutate upstream objects while generating a control.

Run the complete audit in two separate processes, with two fresh working roots,
two fresh output directories, no shared application cache, frozen locale and
timezone, and distinct explicit `PYTHONHASHSEED` values. Primary receipts must
be byte-identical. They may contain no timestamps, temporary paths, absolute
paths, hostnames, or seed-specific values. Per-run environment receipts record
the differing seeds outside the closed primary comparison set. The comparison
receipt is also excluded from that set; its combined manifest digest covers
primary receipts only and cannot self-reference.

This `runner_repeatability` gate establishes only that the same checker and
inputs produce the same primary bytes in the locked execution envelope. It does
not establish correctness, portability, historical replay, or independent
third-party replication. The environment receipt records OS, architecture,
Python implementation/full version, locale, timezone, hash seeds, runner hash,
input-manifest hash, and network-guard result.

The checked verifier has two explicit modes:

1. receipt-only integrity: recompute package hashes and deterministic reductions
   from installed receipts; it cannot verify original evidence;
2. source-bound revalidation: reopen a reader-supplied exact clean checkout and
   paper PDF, verify every registered input hash, and independently recompute
   all gates.

Only source-bound revalidation supports reader-side reproduction of this audit.

## Exhaustive witness receipts

The public checked package must contain machine-readable, public-safe evidence
for the exhaustive population without copying denied upstream free text:

- complete registered-input manifest with relative path, byte size, and
  SHA-256 for every file read;
- one target/join row per run, user, category, and dimension, with source JSON
  pointers and hashes of denied target values;
- exact arithmetic components and derived category/user/run values;
- one packet-item row with packet index/hash, designated store path, match
  count, and every candidate store pointer;
- one attribution row with legal-stage-shape result, reduction result, and
  historical-input observability status;
- lossless missing/null/blank/type inventory;
- source-replay-material and historical-provenance inventories;
- mutation-control receipts, two-run comparison receipt, and a gate summary
  derived from the exhaustive rows.

`Raw result` means these complete audit observations and locators. It never
means copied full bank, task, transcript, memory, prediction/reason, retrieved
content, judge rationale, or attribution evidence.

## Decision and publication boundary

There is no unscoped PASS. The public result reports at least:

- `worked_fixed_artifact_audit`: `PASS` only when exact evidence identity,
  registered run/target joins, fixed-score arithmetic, packet membership,
  stored-attribution reduction, immutability/mutation controls,
  runner repeatability, and source-bound package verification pass;
- `packet_unique_binding`: separately `PASS` or `FAIL`; only `PASS` permits the
  unqualified word `lineage`;
- `stored_output_observability`: complete typed inventory, which may expose
  missing historical artifacts without inventing them;
- `attribution_input_observability`: may remain partial, but then blocks any
  historically bound attribution claim;
- `source_replay_material_status`: `COMPLETE`, `PARTIAL`, or `BLOCKED`;
- `historical_execution_replay`: always `NOT_ATTEMPTED` in this audit.

Source omissions do not automatically turn an otherwise valid fixed-artifact
audit red, but they categorically block a replay claim. The artifact title,
opening summary, badge, and contribution boundary must all carry the
`fixed released-artifact audit` scope, with replay-material status adjacent and
equally visible. The phrases `reproduced MEMPROBE`, `replayed retrieval`,
`end-to-end verified`, `validated benchmark`, and equivalents are prohibited.

If every required fixed-artifact gate passes, the strongest permitted claim is:

> At exact MEMPROBE revision
> `19bb83644b082489b4e181e59f1cded1a00d0529`, an independently authored,
> offline, standard-library checker exhaustively verified run-bound released
> artifact joins; recomputed category-balanced and across-user arithmetic from
> stored historical quarter-step judge outputs; established exact membership
> and, where unambiguous, unique binding of each stored retrieve-packet item to
> its designated released final dump under frozen system-specific contracts;
> checked only the deterministic reduction of stored attribution stages to
> stored labels; and inventoried replay materials. Two fresh offline executions
> produced byte-identical primary receipts. This is released-artifact
> consistency at one exact revision, not a MEMPROBE rerun or historical model
> and retrieval replay.

## Reader-visible non-claims

These must appear in the opening result block, not only in limitations:

- no simulator, assistant, memory writer, retriever, slot filler, judge,
  attribution model, OpenAI endpoint, or Mem-T/vLLM service was run;
- the benchmark was not freshly reproduced and historical retrieval was not
  reissued;
- packet membership does not prove the packet or full dump was the exact
  historical slot-fill payload;
- the source field `ground_truth` is a synthetic benchmark target, not
  independently established real-world truth;
- no semantic re-judgment or human validation of targets, predictions, reasons,
  scores, rationales, disclosure verdicts, or stages was performed;
- recomputed scores remain arithmetic over historical LLM judge outputs;
- a full-store/retrieve delta is not an identified retrieval effect;
- packet/store matching does not establish semantic relevance, sufficiency, or
  absence of equivalent evidence elsewhere;
- no causal separation of writing, storage, serialization, retrieval, context
  construction, slot filling, judging, or attribution is established;
- stored attribution labels remain historical labels, not causal ground truth;
- no historical model snapshot, request, response, prompt hash, retry path,
  runtime, or usage receipt is inferred from current defaults;
- two-run byte identity proves checker repeatability only;
- no significance, prevalence, ranking, real-user, privacy, deployment, or
  generalization claim is produced;
- no absent official script or state is reconstructed and represented as
  official release material.

## Rights and publication notice

Public receipts contain identifiers, locators, hashes, counts, schema states,
and AMS-authored fixtures only. They copy no upstream free text. The checked
README and NOTICE must identify the MEMPROBE paper, official repository, exact
revision, top-level CC BY 4.0 status, AMS modifications, and third-party
exclusions. Hashes and locators grant no additional rights in upstream material.

Consistent with the repository's existing owner-selected boundary, newly
authored AMS code and editorial prose currently receive no new open-source or
Creative Commons license grant. This protocol does not silently choose one.
That boundary must remain reader-visible; any future license grant is a separate
owner decision and must follow the repository's licensing workflow.
