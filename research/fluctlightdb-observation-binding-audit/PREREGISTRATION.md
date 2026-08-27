# FluctlightDB observation-binding audit: frozen preregistration

This protocol was frozen before any FluctlightDB benchmark or synthetic recall
execution. A pre-test independent review required the lexical-key, construction,
provenance-partition, exact-helper, logical-reproducibility, source-packet, negative-control,
and static-preflight amendments already reflected below. The execution is now complete;
results and post-test interpretation live in `README.md` and `raw/`, not in this historical
protocol.

## Evidence vocabulary and source objects

- arXiv statements: `paper-reported`;
- commit `593623eea50361e563180c112322e26d0ab4093b`: `paper-time official-source`;
- commit `d867f3cdbcffcefe4e14473333a78ce33a06ae47`: `current official-source`;
- official descendant `f5d51e247b544503f8f47960b9dc6ecd43c2f464`:
  `official repair-descendant execution`;
- unmodified upstream commands: `official-source execution receipt`;
- newly authored fixtures: `synthetic contract test`;
- architectural recommendations: `editorial inference`.

The arXiv paper, paper-time source, current main, and repair descendant are four distinct
evidence objects. Successor source or runtime behavior must not be attributed backward to
arXiv v1. A current-main compile failure may narrow the executable successor lane but does
not authorize patching the checkout or relabeling a descendant as current main.

## Static premises

The official provenance-conflict suite contains 10 domains times five incompatible numeric
variants. Within each domain all five rows issue the same cue against the same shared brain
while changing the expected verified-ledger engram ID. Shared mode stores all 50 ledger/chat
pairs and supplies no case identity at query time. Every verified ledger uses salience `0.95`,
confidence `0.99`, and verified provenance; every chat uses salience `0.35`, confidence `0.25`,
and unverified provenance.

At both source lines, `activate_scoped()` globally activates, sorts, and truncates before it
retains matching `episode.agent_id`. It then calls the balance/wallet ledger helper, which
scans the hippocampus without an agent predicate and can boost or insert an engram after the
retain. Current successor source additionally invokes `exact_verified_recall()` after the
retain; it scans provenance-backed engrams by life rather than agent.

These are source-inspected premises, not runtime findings.

## H1-S — conditional structural ceiling

For one frozen store and cue, if the five identical calls in a domain return one invariant
top ID, no more than one of the five mutually distinct expected IDs can match. Across ten
domains:

```text
maximum exact-ID hits = 10 domains × 1 = 10/50 = 20%
```

The strict ceiling is conditional on within-frozen-store top-1 invariance. Different arbitrary
winners across freshly reconstructed brains do not falsify it. Hidden per-case state, varying
top IDs across identical calls, a non-10-by-5 census, or a query-side target identity would
narrow or invalidate the theorem.

Strongest permitted result: the locked official shared exact-ID scalar is structurally
underidentified and cannot by itself estimate provenance-ranking quality or the amount of
cross-case contamination. This is not a benchmark invalidation and does not prove that
provenance ranking works.

## H1-I — identity-bearing controls

Run three constructions over the same official 50 pairs:

1. `ambiguous`: official cue/content with no case identity;
2. `scoped`: tag every pair with `agent_id=<case>` and query with the same agent at K=3 and
   K=128;
3. `lexical`: append one neutral tokenizer-verified key to both observations and query, in one
   unscoped shared brain, at K=3 and K=128.

The lexical keys are the ordinal tokens `x000` through `x049`, assigned in exact
`build_cases()` order and embedded as `[bindkey=xNNN]`. Every token must survive the official
Rust-style split as one distinct alphanumeric token and must remain negative under the current
exact-query router.

The paired-ranking population is frozen as the 45 non-wallet lexical rows at K=128 for which
both the intended ledger and paired chat are returned. Wallet rows are excluded because their
cue invokes the post-filter helper. A treatment is invalid if construction changes verified,
provenance, salience, confidence, source, or content-role inputs outside the registered suffix.

Even a 45/45 ledger-over-chat result would describe the whole official-format treatment, not a
single-variable provenance intervention: ledger and chat also differ in salience, confidence,
context, source, and wording.

## H2-L — late scope filtering and candidate truncation

In one 50-pair agent-tagged brain, query every case with matching `agent_id` at K=3 and K=128.
Record every returned ID, rank, activation, `episode.agent_id`, verified flag, provenance,
content, expected-pair rank, and empty result.

- missing at K=3 but present at K=128 is evidence consistent with global top-K before late
  retain; it does not uniquely identify a causal stage;
- any returned stored row whose `episode.agent_id` differs from the requested agent is a direct
  output-scope preservation failure for that exact local call;
- an empty result is not leakage and is reported separately.

## H2-R — post-retain helper probes

Build two tied-salience agents for the wallet cue and run forward/reverse ingest order. Query
both agents at K=1, K=3, and K=128 twice on each frozen store; also query a nonexistent agent at
K=128. The registered expectation is order-sensitive helper selection, not one universal
winner.

Add two non-wallet controls:

- current-router-positive `ticket status is approved` verified rows, queried for A, B, and a
  nonexistent agent at K=1/K=3; paper-time is the negative revision control;
- router-negative `when does my order ship` ledger/chat pairs, queried for A, B, and a
  nonexistent agent at K=128.

A helper attribution requires both a returned stored-agent mismatch and a source path that can
insert after the scope retain. A helper-positive nonexistent-agent result rules out candidate
truncation alone for that row.

No result from these fixtures is evidence about tenant isolation, authentication, remote data
flow, security vulnerability, production exposure, prevalence, severity, or model quality.

## Construction and completeness gates

Every official command runs unmodified in a fresh child process whose initial environment has
no `FLUCTLIGHT_*` variables. Every independent child clears inherited variables, then sets only
`FLUCTLIGHT_SEPARATION_GATE=0` and `FLUCTLIGHT_ACTIVATE_CACHE=1` before `connect_agent()`; the
official SDK may subsequently apply its own mode defaults, which remain observable in raw
receipts.

Before querying, require:

- exactly 50 cases, ten cue classes, five distinct labels per class, and 50 unique bind tokens;
- exactly one non-nil ledger and one non-nil chat ID per case;
- no separation-gate rejection or deduplication;
- correct stored agent metadata and complete expected snapshot census;
- wallet-helper classification only for the five wallet cases and exact-router-negative
  official/lexically bound cues.

Any failure invalidates construction rather than becoming a retrieval miss.

## Repetition and reducer contract

For paper-time and every executable successor object:

- run the unmodified isolated and shared scripts;
- run six independent treatments in separate child processes;
- execute the full six-treatment matrix twice from fresh processes;
- retain raw UUID-bearing receipts but compare logical results after mapping generated UUIDs to
  stable `(case, role)` aliases.

Required stable objects are the official conditional-ceiling premise, 45-case K=128 paired
classification, wallet scope pattern, exact-helper missing-agent classification, shipping
negative control, and within-store cache repetition. Specific tied winners, low-K lexical
visibility, and exact rescued-case sets may vary and must not be converted into stable rates.

## Stop and publication boundaries

Stop or narrow the affected stratum if the source identity is wrong, checkout is dirty,
construction is incomplete, source paths differ from the locked manifest, the official isolated
script falls below its own 0.9 threshold, a required control is absent, or the reducer cannot be
recomputed from the complete raw matrix.

A public artifact may include only public source identities, a self-contained model-free runner,
normalized receipts, source locators, deviations, and bounded claims. It must not include local
workspace paths or private review material. `worked` additionally requires a complete reader-facing
close read, post-test independent review, documentation/build/browser verification, and explicit
source/runtime/evidence-label separation.

Licensing of newly authored AMS code and documentation remains `pending_owner_choice`; this
protocol does not create or imply a license grant.
