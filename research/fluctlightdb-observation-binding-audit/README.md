# FluctlightDB observation-binding and scoped-recall audit

This model-free artifact accompanies an Agent Memory Study close read of
*FluctlightDB: A Memory Model of Data for AI Agents* (`arXiv:2608.12365v1`). It
re-executes the paper's unmodified 50-case provenance-conflict script and tests two narrower
implementation questions: whether the official shared exact-ID score first identifies one
target observation, and whether `agent_id` output scope survives post-ranking recall helpers.

The checked result is **complete but bounded**:

- the unmodified official script produced 50/50 isolated and 9/50 shared at both the exact
  paper-time source and a separately labeled official repair descendant;
- every five-call shared cue class returned one invariant top ID on its frozen store, satisfying
  the premise of a conditional 10/50 structural ceiling;
- in all 45 non-wallet, uniquely bound K=128 official-format pairs, both intended rows were
  visible and the verified higher-salience ledger ranked above its paired chat in both revisions
  and both fresh repeats;
- scoped wallet queries in both revisions, and scoped exact-status queries in the repair
  descendant, returned stored rows whose `episode.agent_id` differed from the requested agent,
  including helper-positive nonexistent-agent controls;
- the router-negative shipping control preserved scope and returned nothing for a nonexistent
  agent.

The 45/45 control is not a single-variable provenance experiment. Ledger and chat also differ in
salience, confidence, context, source, verification, and wording. The result therefore supports
an official-format paired-ranking claim, not the causal phrase “provenance alone works.” The
scope result is a local output-postcondition finding, not a tenant, authentication, remote,
security, production, prevalence, or severity claim.

## Evidence objects

| Object | Exact identity | Evidence label | Boundary |
| --- | --- | --- | --- |
| Paper | [`arXiv:2608.12365v1`](https://arxiv.org/abs/2608.12365v1); PDF SHA-256 `d940a8d5…bd89` | `paper-reported` | LoCoMo, LongMemEval, BEIR, FAMB, and the paper's interpretation remain author-reported; this audit does not reproduce them. |
| Paper-time source | [`voxmastery/FluctlightDB`](https://github.com/voxmastery/FluctlightDB) `593623eea50361e563180c112322e26d0ab4093b`, native/SDK 0.5.9 | `paper-time official-source` and execution receipt | Closest locked source to arXiv v1; environment-specific execution is not a paper reproduction. |
| Current main | `d867f3cdbcffcefe4e14473333a78ce33a06ae47`, native/SDK 0.5.10 | `current official-source` | Exact native build fails with Rust E0425; it produced no runtime output. |
| Official repair descendant | `f5d51e247b544503f8f47960b9dc6ecd43c2f464` | `official repair-descendant execution` | Descends from current main and restores the missing crate-root export. Benchmark, retrieval `brain.rs`, and Python `brain.py` bytes match current main; it is neither current-main runtime evidence nor arXiv-v1 code. |
| Independent treatments | Six frozen fixture families, twice per executable revision | `synthetic contract test` | Mechanism and output-contract audit only; no model, private data, benchmark corpus, API, reader, judge, or remote service. |

The paper PDF is not redistributed. Exact identities, source blobs, wheel hashes, and the
normalized environment contract are in [`raw/source-manifest.json`](./raw/source-manifest.json).

## What the official 9/50 can and cannot measure

The official shared fixture stores five incompatible verified ledger values for each of ten
domains. It then asks the same cue five times against the same frozen store while changing the
expected exact engram ID. If those identical calls return one invariant top ID, no more than one
of the five labels can match:

```text
10 cue classes × at most 1 exact-ID match = at most 10/50 = 20%
```

Both executable revisions met that premise and produced 9/50. Nine domain cues top-ranked one
of their five ledger labels; the wallet cue top-ranked `refund_4:ledger`, outside its cue class.
The particular winner changed in several classes when a fresh brain regenerated UUIDs, but each
five-call class remained invariant within its own store. Cross-process winner identity is not a
premise of the theorem.

This establishes a **query–observation target underidentification** in the locked exact-ID
fixture. It does not show that every shared-memory query needs an explicit case ID, that the
underlying retriever is globally deterministic, that the paper's cross-case contamination
interpretation is wholly false, or that provenance ranking succeeds. It says only that the 9/50
scalar cannot by itself distinguish those explanations or quantify provenance-ranking loss.

## Identity-bearing paired control

The lexical treatment assigns `x000…x049` in exact official case order and appends
`[bindkey=xNNN]` to each ledger/chat pair and its query. Static preflight verifies that every key
survives source-matched token splitting as one distinct token and remains negative under the
successor exact-query router.

The primary population excludes the five wallet rows because their cue invokes a separate
post-filter ledger helper. For every other K=128 row:

| Runtime object | Fresh repeats | Both paired rows visible | Ledger above chat | Chat above ledger | Foreign-agent rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| paper-time 0.5.9 | 2 | 45/45 each | 45/45 each | 0/45 | 0 |
| repair descendant 0.5.10 | 2 | 45/45 each | 45/45 each | 0/45 | 0 |

This control shows that the 41 official shared misses are not equivalent to 41 observed
chat-over-ledger pairwise losses in this identity-bearing treatment. It still preserves the
official ledger/chat differences in salience, confidence, context, source, verification, and
wording, so no one field receives a standalone causal estimate.

## Scoped output findings

Source inspection places the `agent_id` retain after global activation, sort, and top-K. Both
source lines then call `prefer_ledger_truth_on_balance_cue()` without an agent predicate; the
repair/current retrieval line additionally calls `exact_verified_recall()` without an agent
predicate. Both helpers can insert after the retain.

| Fixture | Paper-time | Repair descendant | Negative/control meaning |
| --- | --- | --- | --- |
| 50-case scoped wallet, K=3/K=128 | 10/10 queries returned foreign `refund_4:ledger` | same | Stored `episode.agent_id` mismatch is directly observed. |
| 50-case non-wallet, K=128 | 45/45 matching pairs visible; zero foreign-agent rows | same | Scope works on this bounded non-helper lane. |
| Two-agent wallet, K=1/3/128 | later-ingested tied ledger injected into the other agent; nonexistent agent returns it | same | Winner reverses with ingest order; repeated cached calls are alias-identical. |
| Exact-status, K=1/K=3 | nonexistent-agent rows empty and non-foreign | every A/B/nonexistent query returns foreign verified rows; nonexistent K=3 receives both agents | Separates the successor exact helper from paper-time behavior. |
| Shipping, K=128 | A/B return their own pair; nonexistent empty | same | Router-negative non-helper control. |

The helper-positive nonexistent-agent controls cannot be explained by global candidate
truncation alone because no in-scope candidate exists to rescue. For wallet, the source anchor is
the post-retain balance helper. For repair/current exact-status, it is the separately introduced
post-retain exact helper. The tests do not establish what a remote server, authentication layer,
tenant contract, deployment, or production caller does; `tenant_id` is not an activation
parameter in the audited Python surface.

## Low-K and repeatability boundary

Widening scoped K from 3 to 128 rescued the in-scope ledger in multiple non-wallet cases in
every run. The exact case set varied: paper-time rescued 22 then 21 cases; the repair descendant
rescued 20 then 22. This is evidence consistent with global top-K before the late retain, not a
stable failure rate or a complete causal decomposition.

The following logical classifications were stable across fresh reconstructed brains:

- official 50/50 isolated, 9/50 shared, and within-store cue-class invariance;
- 45-case K=128 paired official-format result;
- wallet mismatch/order/cache pattern;
- repair exact-helper and paper-time nonexistent-agent negative controls;
- shipping control.

The following were not treated as stable claims: particular arbitrary winners in underidentified
cue classes, K=3 rescued-case identity, lexical low-K visibility, and one paper-time matching-agent
K=1 exact row. UUID-bearing raw bytes are intentionally not required to match across processes.

## Construction and execution controls

The runner rejects a wrong commit or dirty checkout and records exact Git blobs/SHA-256 for seven
source paths. Every treatment runs in its own child process. Before connection it clears inherited
`FLUCTLIGHT_*`, then sets only `FLUCTLIGHT_SEPARATION_GATE=0` and
`FLUCTLIGHT_ACTIVATE_CACHE=1`; `connect_agent()` subsequently applies the official SDK's own mode
defaults inside that process. Official scripts start with no `FLUCTLIGHT_*` variables and run
unmodified.

Every treatment fails unless all registered ledger/chat ingests produce non-nil IDs, are neither
gate-rejected nor deduplicated, appear in a full export snapshot, and retain expected agent
metadata. Static preflight fixes the 10×5 census, binding tokens, router/helper classification,
and expected snapshot count. The reducer consumes all four complete six-treatment matrices plus
four official runs and emits 1,140 compact query rows; it does not select cases before computing
the matrix summary.

The checked public evidence contains the complete normalized summary and all 360 rows used for
the paired/scope/control claims. Full UUID-bearing snapshots and ingest reports are intentionally
omitted from the repository because the public reader can regenerate them from exact official
checkouts. The checked verifier binds the compact files by hash and recomputes every headline
gate used above.

## Build chain and disclosed deviations

The exact paper-time source built a native 0.5.9 arm64 wheel. Exact current main did not compile:
`crates/fluctlight-py/src/lib.rs:726` calls `fluctlightdb::sync_once`, which that crate root does
not export. The full compiler excerpt is in
[`raw/current-main-build-receipt.md`](./raw/current-main-build-receipt.md). No current-main wheel,
import, benchmark, or treatment result exists.

The official repair descendant explicitly restores that export and built as 0.5.10. Its
benchmark and audited retrieval/SDK blobs match current main, but the build repair is part of its
identity. Treating it as a distinct runtime object narrows successor claims without discarding
the exact current-source build receipt.

An early source ledger accidentally appended six characters to the true paper-time commit. The
runner's exact-commit gate rejected the invalid identity before import or execution; the frozen
executable protocol uses the real 40-hex commit above. No result was produced under the invalid
identity.

The checked outputs were produced by a pre-publication runner/reducer whose exact SHA-256 values
are preserved in the source manifest. Public `audit.py` changes only its private-facing module
description; public `analyze_results.py` changes only the manifest key from the old runner
filename to `audit.py`. Running the public reducer over the complete raw matrix byte-reproduced
the checked `summary.json` and `posttest-evidence.json`. These source-delta and byte-comparison
facts are recorded in [`raw/reproduction.json`](./raw/reproduction.json).

## Verify the checked artifact

No upstream checkout or native package is needed:

```bash
python3 research/fluctlightdb-observation-binding-audit/verify_checked.py
```

Expected compact result:

```text
status=PASS; compact_query_rows=1140; selected_evidence_rows=360
```

## Reproduce from exact official source

Obtain distinct clean checkouts outside this artifact:

```bash
git clone https://github.com/voxmastery/FluctlightDB.git FluctlightDB-paper
git -C FluctlightDB-paper checkout 593623eea50361e563180c112322e26d0ab4093b

git clone https://github.com/voxmastery/FluctlightDB.git FluctlightDB-repair
git -C FluctlightDB-repair checkout f5d51e247b544503f8f47960b9dc6ecd43c2f464
```

Build each checkout's native wheel in a separate Python environment using Rust 1.98.0,
Cargo 1.98.0, maturin 1.15.0, CPython 3.13.3, pyo3 abi3-py39, and macOS 11.0 deployment target;
install that checkout's Python SDK and exact wheel into its own environment. Verify the resulting
wheel against `raw/source-manifest.json` before execution.

For each environment, run both unmodified official conditions and two complete matrices into one
new output directory. Example for paper-time:

```bash
PY=.venv-paper/bin/python
RUNS=/tmp/fluctlightdb-observation-binding-runs
AUDIT=research/fluctlightdb-observation-binding-audit/audit.py
SOURCE=/path/to/FluctlightDB-paper

$PY "$AUDIT" run-official --source-repo "$SOURCE" \
  --expected-commit 593623eea50361e563180c112322e26d0ab4093b \
  --revision-label paper-time --condition isolated --output-dir "$RUNS"
$PY "$AUDIT" run-official --source-repo "$SOURCE" \
  --expected-commit 593623eea50361e563180c112322e26d0ab4093b \
  --revision-label paper-time --condition shared --output-dir "$RUNS"
$PY "$AUDIT" run-matrix --source-repo "$SOURCE" \
  --expected-commit 593623eea50361e563180c112322e26d0ab4093b \
  --revision-label paper-time --repeat 1 --output-dir "$RUNS"
$PY "$AUDIT" run-matrix --source-repo "$SOURCE" \
  --expected-commit 593623eea50361e563180c112322e26d0ab4093b \
  --revision-label paper-time --repeat 2 --output-dir "$RUNS"
```

Repeat with the repair environment, repair checkout/commit, and label `repair-descendant`. Then
reduce the combined raw directory:

```bash
python3 research/fluctlightdb-observation-binding-audit/analyze_results.py \
  --runs "$RUNS" --output-dir /tmp/fluctlightdb-observation-binding-compact
```

Absolute paths and generated UUIDs will differ. Compare the structural, paired, scope, negative-
control, and logical-repeatability fields rather than requiring byte identity of full raw output.

## Artifact map

- [`PREREGISTRATION.md`](./PREREGISTRATION.md): frozen questions, controls, falsifiers, and claim ceiling;
- [`audit.py`](./audit.py): source-locked official and six-treatment runner;
- [`analyze_results.py`](./analyze_results.py): complete-matrix deterministic reducer;
- [`verify_checked.py`](./verify_checked.py): offline checked-receipt verifier;
- [`raw/source-manifest.json`](./raw/source-manifest.json): paper/source/wheel/runtime identities;
- [`raw/summary.json`](./raw/summary.json): all official aggregates, treatment aggregates, gates, and logical repeatability;
- [`raw/posttest-evidence.json`](./raw/posttest-evidence.json): all 360 normalized rows used by public claims;
- [`raw/current-main-build-receipt.md`](./raw/current-main-build-receipt.md): exact compile boundary;
- [`raw/reproduction.json`](./raw/reproduction.json): public-source delta and reducer byte comparison;
- `checksums.sha256`: checked public file-set identity.

## Claim ceiling

This artifact may support a complete reader-facing `worked` essay only if the essay keeps its
evidence labels and causal boundaries intact. It does not reproduce paper benchmarks, validate
LoCoMo/LongMemEval/BEIR/FAMB claims, isolate the causal effect of provenance alone, establish a
tenant or security boundary, test a remote or production deployment, estimate prevalence or harm,
or show that every scope mechanism fails.

The strongest reusable engineering lesson is narrower: **ranking trust requires a target
observation contract, and any scope filter must remain a postcondition after every recall helper
that can add or reorder results.** That is an architectural synthesis from the paper, exact
source, and bounded synthetic controls—not an upstream claim.
