# StateFuse interpretation-contract and semantic-reference audit

This deterministic, model-free artifact accompanies an Agent Memory Study close
read of *StateFuse: Deterministic Conflict-Preserving Memory for Multi-Agent
Systems* (`arXiv:2607.05844v1`). It tests two bounded implementation questions
against StateFuse `0.3.0` at the locked official commit. The repository's
`paper/main.tex` at that commit is the unpublished successor manuscript
*StateFuse: Taxonomy-Aware Conflict-Preserving Memory for Heterogeneous Agent
Systems*; it is neither the paper authority nor a source of claims for arXiv v1.

The primary result is **interpretation-contract binding**: byte-identical
immutable operations produced different materialized and projected semantic
views when deterministic equality, semantic-ref, or detector contracts changed.
The secondary result is **semantic-ref tombstone carryover** across two
disjoint-validity occurrences that shared the default semantic handle.

These results make the repository's same-contract deployment precondition and
semantic-handle scope operationally visible. They are not failures of OpSet
merge convergence, benchmark or paper-experiment reproductions, model
evaluations, vulnerability findings, or estimates of production frequency,
harm, accuracy, safety, or reliability.

The checked artifact is a **completed local evidence audit**. It is not an AMS
essay, does not assign `noteDepth`, and cannot by itself make a material
`worked`. The separately authored reader-facing essay has since integrated the
evidence into the canonical material and assigned `worked` on current `main`;
that editorial decision remains outside this artifact. Canonical integration
and its commit have therefore occurred, while publication and live deployment
remain separate gates that this repository-local artifact does not establish.

Historical wording note: the frozen preregistration retains the phrase
`No worked artifact is permitted`. In that pre-execution document, `worked
artifact` meant an evidence package eligible for later editorial consideration.
It does not assign AMS `noteDepth`, determine canonical integration, or
substitute for a complete reader-facing worked essay.

## Locked evidence objects

The unit keeps four evidence objects separate:

| Object | Identity | Evidence label | Boundary |
| --- | --- | --- | --- |
| Paper | [`arXiv:2607.05844v1`](https://arxiv.org/abs/2607.05844v1); reviewed PDF SHA-256 `128853be83e65122ff6f29b006416c7d79b5c74a601fe277b65b82b6ff9dc96e` | `paper-reported` | Current context/validity, taxonomy detector lifecycle, connector, and workshop results are not attributed backward to v1. |
| Official code | [`nZiben/statefuse`](https://github.com/nZiben/statefuse) commit `79a6229f83a7b174a2a9ac8fd0ace267ae30e79b`, package `0.3.0` | `official-source` | This is the implementation authority; synthetic probes do not reproduce paper experiments. |
| Repository manuscript | `paper/main.tex` at the pinned commit; Git blob `9fe67c385111e15ffc31c0fa2b9cac4e9dd8a68c` | `official-source / unpublished_repository_manuscript` | It is a distinct anonymous workshop extension, not arXiv v1, peer reviewed, or verified accepted. |
| Local upstream suite | Python 3.13.3, pytest 9.1.1, macOS 26.5.2 arm64; 139 collected and 139 passed | `official-source execution receipt` | Environment-specific verification only; not a `released-input audit` or benchmark reproduction. |

The unpublished repository manuscript reports 135 passed and four optional
skipped in its unspecified build environment. This local environment collected
139 nodes and reported 139 passed, zero skipped. Whether these are the same 139
node IDs, and why four outcomes differ, is not established without the
manuscript's exact command, environment, node IDs, extras or markers, and skip
reasons. No defect is inferred.

Exact Git blobs and SHA-256 values for every inspected source/test file are in
[`raw/source_manifest.json`](./raw/source_manifest.json). The artifact neither
copies the paper PDF nor any upstream source or test.

## Result

The runner produced 428 synthetic result rows with preregistered frozen
observable state/projection snapshots across 17 fixed-contract permutation
groups. Every group had exactly one state digest and one projection digest:

- H1-EQ: 2 contracts x all 2 operation permutations;
- H1-REF: 2 contracts x all 6 permutations;
- H1-DET/H1-VID: 3 contracts x all 120 permutations;
- H2-NONE: 2 permutations x Tuesday/no-validity queries;
- H2-ID/REF/CTX/VALUE: 4 cases x all 6 permutations x both queries.

`OpLog` stores the submitted operations by immutable `op_id`, and
`OpLog.iter_ops()` supplies them to materialization in sorted-`op_id` order.
These groups therefore test constructor insertion-order independence,
canonicalization into the same set-like log, and repeated deterministic
execution of the frozen interpretation/projection pipeline. They do not vary
the internal replay order or merge tree and are not a new CRDT merge-order
claim. The exact 17-group matrix, every expected permutation sequence, all 428
rows, and every recomputed state/projection digest are readiness gates; a
one-row group cannot pass.

One runner invocation performed two complete passes in distinct output roots.
Each pass rechecked source/paper identity, reran the two upstream pytest
commands, rebuilt all fixtures/contracts/queries/permutations, rederived the
decision from raw payloads, and serialized the eight primary output files. The
runner then byte-matched those files before emitting the final reproduction,
readiness, compact result, and checksum receipts. This is a same-environment
deterministic repeatability result, not evidence of byte identity across Python
or operating-system environments. The verdict is `REPRODUCIBLE`; its bounded
receipt is in [`raw/reproduction.json`](./raw/reproduction.json).

### H1-EQ — equality changes conflict formation and selection

The operation bytes and OpSet hash remained identical:

```text
f5725fca19bb22581f5f7ea437358787f442381676eb506f1954f3a48f5e5154
```

Both executions retained the same two active claim IDs and the same raw-derived
semantic refs. Under raw equality, `"Open"` and `"open"` formed a direct
conflict. The fixed `ConservativeHeuristicResolver` observed exact tied scores,
abstained, and left one unresolved conflict. Under strip-and-casefold equality,
the same claims formed no conflict and `h1-eq-upper` was selected by the source's
deterministic no-conflict tie-break.

This isolates equality behavior: `normalize_for_claim_ref=False` in both
conditions, so semantic-ref identity did not change.

### H1-REF — semantic-handle normalization changes claim activity

The operation bytes and OpSet hash again remained identical:

```text
f5375bcd19b3d6307781d65f69b7fdb9af517884706d831d291c9f98e2f45515
```

Both contracts used the same strip-and-casefold equality. With raw values in
claim-ref derivation, `" Open "` and `"open"` had different effective refs and
the semantic retraction suppressed only `h1-ref-lower`. With value
normalization enabled for claim refs, both mapped to
`sha256:9407c6cab01a5060294f0c9f31c0dedf6e034915340b854df8762110ff7e04e9`
and both became inactive. Neither condition created a conflict.

This isolates semantic-handle derivation: equality behavior, operations, query,
and resolver remained fixed.

### H1-DET — silent same-ID detector drift reopens a resolution

All three detector executions used the byte-identical five-operation OpSet:

```text
126a828f6b867431c5fc66a912750b2220dc2f556c9ecbfa15a8da69f1e22a6d
```

The operations contain one capacity, cost claims A/B/C sharing a multi-valued
cost key, and one committed resolution over D1's capacity+A/B candidate set.

| Contract | Detector locus | Candidates | Snapshot/lifecycle | Projection consequence |
| --- | --- | --- | --- | --- |
| D1: A/B, `budget/v1` | `conflict-ref:912291…e18e` | capacity, A, B | `conflict:bbd9ff…52e1`; resolution effective, `resolved` | committed resolution applies; after A/B rejection the remaining compatible cost C is promoted to a single selected cost |
| D2: A/B/C, same `budget/v1` | same `conflict-ref:912291…e18e` | capacity, A, B, C | `conflict:80dc05…51cf3`; resolution ineffective, `reopened` | unresolved finding; explanation names uncovered candidate C |
| D2 behavior, declared `budget/v2` | new `conflict-ref:eb0dce…f45e` | capacity, A, B, C | `conflict:61422c…148f8`; current v2 locus `open` | unresolved finding has no committed v2 resolution; the old v1 resolution remains recorded only on its old lane |

The same-ID pair demonstrates an audit-induced silent contract drift that the
library does not bind with a cross-replica manifest. It does not show that
ordinary correctly versioned deployments inevitably drift. The v2 control does
not make views converge; it makes the changed interpretation locus visible.

The D1 promotion of C is a **post-test observed projection consequence**. The
frozen serializer captured it and the artifact-readiness check verifies that the
reported observation remains present, but it was not a separately preregistered
hypothesis and is not an H1-DET decision gate.

### H2 — semantic-ref tombstone carryover crosses validity occurrences

Monday M and Tuesday T used disjoint half-open validity intervals, distinct
claim IDs, timestamps, evidence IDs, provenance, and confidence. Under the
default registry, those fields do not distinguish their semantic refs. At the
Tuesday-noon query:

| Case | Inactive | Inapplicable | Selected | Result |
| --- | --- | --- | --- | --- |
| H2-NONE | none | M | T | temporal applicability alone leaves Tuesday active |
| H2-ID | M | none | T | exact-ID correction remains assertion-local |
| H2-REF | M, T | none | none | same-ref correction suppresses both occurrences |
| H2-CTX | M | none | T | Tuesday occurrence context changes its ref |
| H2-VALUE | M | none | T | `"open-again"` changes Tuesday's ref |

The `valid_at=None` diagnostic also left both M and T inactive in H2-REF, with
neither classified as temporally inapplicable. This confirms a semantic-ref
tombstone consequence rather than a Tuesday query-filter artifact.

This is the operational consequence of a documented broad correction handle.
It does not establish that the source chose the wrong domain ontology. An
application requiring occurrence-local semantic correction can encode
occurrence identity in key/value/context or use exact-ID retraction; that is an
editorial representation inference, not test output.

## Method and controls

The newly authored standard-library runner:

1. rejects a wrong source commit, dirty checkout, paper hash, package version
   parsed from `pyproject.toml`, Git blob, or SHA-256;
2. records full `pytest --collect-only -q` and `pytest -q -ra` receipts; Python
   text mode performs universal-newline decoding, and only elapsed-time tokens
   on pytest summary lines are replaced with `<elapsed>`, while terminal
   whitespace and all other stdout/stderr text are retained;
3. stores canonical operation JSON and one OpSet hash per fixture;
4. binds every registry/detector to a canonical descriptor, parameters, returned
   detector ID, and runner-source hash;
5. submits every expected constructor permutation under one fixed contract,
   verifies exact sequence coverage, and checks the source's sorted-`op_id`
   canonicalization/repeated-execution result;
6. captures schema-versioned frozen observable snapshots of refs and ref
   groups, retraction targets, inactive/inapplicable/active sets, resolution
   records and lanes, complete conflicts and witnesses, lifecycle state,
   projection selections, unresolved/surfaced findings, and explanations;
7. recomputes every payload digest, validates the exact fixture/contract/query
   matrix and 428-row coverage, and derives H1/H2 decisions from the complete
   preregistered field-level expectations used by the result wording;
8. performs a fresh second pass, byte-compares all eight primary files, and
   computes `integration_readiness_passed` only after source, suite, execution,
   H1, H2, reported-observation, output-completeness, and reproduction gates
   pass; this flag describes the evidence package, not AMS essay depth; and
9. keeps the source checkout clean while every custom registry/detector
   invocation runs under a socket network guard.

The resolver parameters, query time/context, serialization, locale
`C.UTF-8`, timezone `Asia/Singapore`, and Python process inputs are frozen. No
model, API, credential, personal data, benchmark trace, live connector, or
network service is used.

## Reproduce

Acquire the official source and exact paper without placing either inside this
artifact:

```bash
git clone https://github.com/nZiben/statefuse.git StateFuse
git -C StateFuse checkout 79a6229f83a7b174a2a9ac8fd0ace267ae30e79b
git -C StateFuse status --short
curl -L https://arxiv.org/pdf/2607.05844v1 -o statefuse-arxiv-2607.05844v1.pdf
```

Create an isolated environment with pytest and run into a new output directory:

```bash
python3 -m venv .venv-statefuse-audit
.venv-statefuse-audit/bin/python -m pip install pytest==9.1.1
LC_ALL=C.UTF-8 TZ=Asia/Singapore \
  .venv-statefuse-audit/bin/python \
  research/statefuse-interpretation-contract-audit/audit.py \
  --source-repo /path/to/StateFuse \
  --paper-pdf /path/to/statefuse-arxiv-2607.05844v1.pdf \
  --output-dir /tmp/statefuse-contract-rebuild
```

Verify the checked artifact without the upstream checkout:

```bash
python3 research/statefuse-interpretation-contract-audit/audit.py --verify-checked
```

Each invocation already includes an internal fresh second pass. After a fresh
two-pass rebuild, compare every generated raw byte and `RESULTS.txt` with the
checked artifact:

```bash
python3 research/statefuse-interpretation-contract-audit/audit.py \
  --compare-checked \
  --output-dir /tmp/statefuse-contract-rebuild
```

Reproduction requires a reader-supplied exact checkout and reviewed PDF. The
artifact does not rely on the local paths used to create the checked result.

## Artifact map

- [`PREREGISTRATION.md`](./PREREGISTRATION.md): hypotheses, exact fixtures,
  controls, falsifiers, stop conditions, and claim ceiling frozen before
  execution.
- [`RESULTS.txt`](./RESULTS.txt): compact derived result.
- [`raw/source_manifest.json`](./raw/source_manifest.json): paper, source,
  workshop, blob, and runner identities.
- [`raw/environment.json`](./raw/environment.json): Python/platform/dependency
  and no-network/no-model receipt.
- [`raw/pytest_collect.txt`](./raw/pytest_collect.txt) and
  [`raw/pytest_run.txt`](./raw/pytest_run.txt): complete node and upstream-suite
  receipts after universal-newline decoding, with only pytest-summary elapsed
  tokens normalized.
- [`raw/contract_descriptors.json`](./raw/contract_descriptors.json): all eight
  registry/detector treatments and the fixed resolver.
- [`raw/cases.jsonl`](./raw/cases.jsonl): eight exact fixtures, canonical
  operation JSON, queries, permutation counts, and OpSet hashes.
- [`raw/run_results.jsonl`](./raw/run_results.jsonl): all 428 raw state and
  projection snapshots.
- [`raw/decision.json`](./raw/decision.json): mechanically rederivable primary
  execution, H1, and H2 gates; it does not declare AMS essay or note-depth
  status.
- [`raw/reproduction.json`](./raw/reproduction.json): mechanically emitted
  eight-primary-file byte-match receipt from the internal fresh second pass.
- [`raw/readiness.json`](./raw/readiness.json): evidence-package integration
  readiness, computed only after source, suite, execution, H1/H2, reported
  observation, complete output, and reproduction gates pass. Canonical AMS
  status and public note depth are explicitly outside this artifact's authority.
- [`checksums.sha256`](./checksums.sha256): complete checked file-set manifest;
  unlisted residue is rejected.

## Limits and publication boundary

- H1 compares deliberately different deterministic contracts. Constructor
  permutations are canonicalized to sorted-`op_id` replay by the source; this is
  not a replay-order or merge-tree test and not a counterexample to same-contract
  replay or OpSet commutativity, associativity, or idempotence.
- H1-EQ/REF use two-claim synthetic fixtures. H1-DET uses one deliberately
  adversarial detector/version scenario. They do not estimate prevalence or
  operational impact.
- H2 combines documented broad semantic tombstones with validity-independent
  identity. Its contribution is the controlled recurrence consequence, not
  discovery of an undocumented permanence rule.
- No natural-language extraction, model, user trace, concurrency fault, storage
  backend, live service, or sensitive information is tested.
- The repository manuscript and current code are kept distinct from arXiv v1;
  none of the workshop model/live-backend claims is validated here.
- The upstream repository has no root `LICENSE` file while package metadata
  declares MIT. Supply-your-own checkout avoids unnecessary redistribution.
- Licensing of newly authored AMS code/docs remains `pending_owner_choice`.
  This local candidate does not add or imply license terms.
- Canonical-material integration and its commit now exist on current `main`.
  This evidence artifact still does not decide publication or deployment, and
  this repository-local record makes no live-deployment claim.
