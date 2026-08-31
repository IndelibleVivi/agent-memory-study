# Faulty-memory audit: post-review amendment

Status before corrected formal execution:
`preliminary_receipts_rejected_amendment_frozen_corrected_checker_not_run`.

The original [`PROTOCOL.md`](./PROTOCOL.md) remains frozen. Its first two-root
execution was completed locally, but a read-only code review found that three
registered controls did not exercise production validation and that the
`compare -> install -> receipt-only` path did not bind its receipts strongly
enough. Those preliminary receipts are rejected, remain outside this package,
and may not support the public verdict. This amendment was written before any
formal execution of the corrected checker.

The audit is still source-observed rather than blinded: the paper, public
release, schemas, and preliminary output were already known. The amendment
does not add a model, API, benchmark environment, inferential statistic, or
paper-experiment replay.

## Amendment A: production-path controls

The three original controls below retain their registered meaning but must now
mutate real production inputs or receipts and invoke validators also used by
the unmodified audit and installed-package verifier:

1. `shrink_mapped_tables_to_headers` passes an in-memory header-only map for
   all thirteen mapped tables through the same official assertion mapper;
2. `relabel_assertion_count_as_unique_arm_count` changes the generated
   official coverage receipt and passes it through the same coverage-unit
   validator; and
3. `relabel_missing_outcome_as_observed_failure` changes the generated
   denominator receipt and passes it through the same missingness validator.

The AppWorld null-`task_name` case is an expected-PASS regression control, not
a detected mutation. Results must therefore report negative and positive
controls separately.

Four additional negative controls are registered before corrected execution:

15. replace one ScienceWorld curve-registry method row with a duplicate;
16. replace one AppWorld schedule/checkpoint row with a duplicate;
17. clear one selected pool's `task_id` while preserving its row count; and
18. remove the Boolean `success` field from one invalid interactive row.

One additional positive metamorphic control is registered:

- reversing the ScienceWorld and AppWorld CSV row order must leave the
  canonical curve receipt unchanged.

The corrected expected accounting is **17/17 negative controls detected** and
**2/2 positive controls passed**. Every negative control must traverse shared
production code and fail with its registered code; every positive control must
traverse shared production code and byte-match or satisfy its registered
invariant.

## Amendment B: exact curve registry and pairing surface

Gate 6 is strengthened without changing its descriptive claim ceiling.

- ScienceWorld contains exactly one row for each of `langmem`, `mem0`,
  `reasoningbank`, `letta`, `ACE`, `AWM`, and `proplay`. Each curve is built in
  checkpoint order `N100, N200, N300, N400`, independent of CSV row order.
- AppWorld contains exactly one row for every registered
  `(schedule, checkpoint)` pair. Current, A, and succdrop use
  `N25, N50, N100, N150, N200`; B uses
  `N25, N50, N85, N100, N150, N200`. Curves are built in that order,
  independent of CSV row order.
- The receipt additionally reports cross-schedule evaluation-set pairing at
  every shared checkpoint. This remains a released-row identity comparison,
  not a causal schedule test.

## Amendment C: schedule and row-schema checks

Every selected pool reference and variant must contain 200 non-empty string
`task_id` values before uniqueness or multiset equality is evaluated.
`pool_D` must preserve exact key sets and exact canonical content after only
`taskDescription` is removed; missing keys and present-null fields are not
treated as equal.

The current release supplies a Boolean `success` field on every interactive
row. Gate 2 is clarified accordingly: every interactive row, including an
invalid/refusal row, must contain an exact Boolean; invalid rows must not be
successful. This is stricter than allowing an omitted outcome key and matches
the locked release bytes.

## Amendment D: source discovery and public-safety scope

The corrected source lock must discover the actual `results/*/arms.csv`
parents and require exact equality with the six registered experiments. It
must require no local tags and must normalize and verify the checkout's
`origin` locator as `DylanZSZ/Memory-Collapse-Eval`; the commit and tree remain
the byte authority.

Receipt safety must report tested path, credential-pattern, and upstream
row-payload-key hit counts rather than an unsupported prose Boolean. Before a
checksum manifest is written—and again during receipt-only verification—the
checker scans every final public package file for macOS home/volume absolute
path prefixes and registered credential patterns. This is a bounded pattern
scan, not a security audit or proof that arbitrary prose contains no sensitive
fact.

## Amendment E: receipt chain of custody

`run.json` must bind its stable receipt paths, byte counts, and SHA-256 values,
plus the exact checker SHA-256, source commit/tree, paper SHA-256, run label,
and both seeds. A shared bundle validator must parse and validate every
decision-bearing audit section, the complete control manifest, and these
cross-file bindings.

`compare` must validate both complete run bundles before comparison and record
the exact environment-receipt hashes plus the actual stable-file hashes.
`install` must independently rebuild that comparison from the supplied runs,
require byte equality with the supplied comparison receipt, and refuse a
pre-existing `raw/` target. `verify-installed` must reconstruct the same
bindings from installed files rather than trust top-level `PASS` labels or
spot-check a few scalar fields.

Checksums remain package-integrity metadata, not an external signature. An
offline receipt-only pass may therefore state only:

> Package integrity and internal receipt consistency pass; source and paper
> were not reopened.

Only a fresh source-bound two-root rebuild that byte-matches the installed
stable receipts may state exact-current-release revalidation. A Git commit or
other separately trusted publication record is still needed to anchor the
package bytes against deliberate replacement of both checker and manifest.

## Corrected stop rule

Any failure of the amended production controls, exact curve registry,
cross-file receipt binding, source discovery, pool-ID presence, interactive
Boolean schema, or final-package safety scan is a hard failure. The preliminary
receipts do not become valid merely because later receipts pass. All original
claim ceilings remain in force.
