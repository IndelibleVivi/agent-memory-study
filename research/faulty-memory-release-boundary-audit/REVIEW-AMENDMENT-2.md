# Faulty-memory audit: second post-review amendment

Status before final formal execution:
`corrected_receipts_rejected_second_amendment_frozen_final_checker_not_run`.

The original [`PROTOCOL.md`](./PROTOCOL.md) and first
[`REVIEW-AMENDMENT.md`](./REVIEW-AMENDMENT.md) remain frozen. The corrected
checker described by the first amendment completed a two-root local execution,
but a second read-only adversarial review found three remaining
chain-of-custody defects: JSON equality accepted some wrong exact types,
comparison receipts could be installed in non-canonical byte form, and the
package enumerator silently excluded two classes of files. Those corrected
receipts are rejected, remain outside this package, and may not support the
public verdict. This amendment was written before any formal execution of the
final checker.

The audit remains source-observed rather than blinded. This amendment changes
receipt and package validation only; it does not add a model, API, benchmark
environment, inferential statistic, or paper-experiment replay. The expected
stable audit facts, seventeen negative production controls, and two positive
controls remain unchanged.

## Amendment F: exact JSON types and whole-receipt lock

Every decision-bearing JSON scalar must have its registered exact JSON type.
In particular, Python's equality aliases must not make an integer equal to a
float, a Boolean equal to an integer, or a zero equal to `false`. Schema
versions, counts, seeds, byte sizes, and traversal values require exact
integers; pass/fail and equality fields require exact Booleans; hashes, paths,
labels, statuses, and locators require strings.

The installed stable audit receipt must additionally match the preregistered
whole-file canonical SHA-256. That lock complements, rather than replaces,
section validators: individual validators still produce bounded failure codes,
while the whole-receipt digest prevents an uncovered top-level field from being
changed together with its dependent environment and checksum receipts.

Before installation, the receipt-chain regression suite must reject at least
these transformations of otherwise internally rehashed receipts:

1. `schema_version: 2` changed to `2.0`;
2. a registered integer zero changed to `false`;
3. a registered Boolean `true` changed to integer `1`; and
4. a registered count changed from an integer to an equal-valued float.

These are receipt-chain regressions, not additional scientific mutation
controls, so the registered **17/17 negative** and **2/2 positive** control
accounting does not change.

## Amendment G: canonical receipt bytes

Every JSON receipt used by `compare`, `install`, or `verify-installed` must be
encoded exactly as the checker's canonical JSON bytes: sorted keys, compact
separators, UTF-8, and one trailing newline. Duplicate keys, reordered or
pretty-printed equivalents, and any other byte-distinct serialization are
rejected even if parsing would produce an equal Python value.

`install` must require the supplied comparison file's raw bytes to equal the
freshly reconstructed canonical comparison bytes before copying it. The
installed verifier must enforce the same condition. Source-bound verification
then compares the same canonical byte object instead of applying a stricter raw
comparison only after installation.

The receipt-chain regression suite must demonstrate that a semantically equal
but pretty-printed or key-reordered comparison receipt cannot be installed and
cannot pass receipt-only verification.

## Amendment H: exact package file set

The package file enumerator must inspect every regular file below the package
root except `checksums.sha256`. It may not ignore `.DS_Store`, `__pycache__`,
compiled bytecode, editor artifacts, or another unregistered file class.
Consequently any extra regular file changes the exact file set, blocks checksum
generation, and blocks receipt-only verification.

No symlink is permitted anywhere below the package root. This includes a
registered path replaced by a symlink, a directory symlink, and a dangling
symlink: target bytes or target strings must not sit outside the exact inventory
and safety scan. Any non-directory, non-regular entry type is also rejected.

The final registered package contains eleven checksummed files: the ten
surfaces listed after the first amendment plus this amendment. The manifest is
the twelfth file and does not list itself. Checksum generation safety-scans the
exact eleven-file pre-manifest set; receipt-only verification scans those eleven
files plus the manifest itself.

Before installation, the package regression suite must show that adding an
unregistered `__pycache__/*.pyc` or `.DS_Store` causes the exact-file-set gate
to fail. It must separately reject a registered-file symlink, directory
symlink, and dangling symlink. Task-generated test bytecode must stay outside
the public package.

## Amendment I: repeatability provenance ceiling

The stored comparison is a producer-recorded comparison whose internal
content bindings can be validated. It is not cryptographic proof that two
historically independent processes or execution events occurred. Run labels,
seeds, and runtime strings are receipt fields; they do not become an external
attestation merely because they are hashed.

The comparison receipt must state
`fresh_process_identity: PROCEDURAL_NOT_RECEIPT_PROVEN`. Receipt-only output
must not claim to re-establish two-run repeatability. The recorded local formal
procedure may truthfully report that two commands were run in two fresh roots,
but that history remains procedural evidence. A current source-bound invocation
re-establishes its own two-root execution by launching both runs itself and
checking their stable bytes before comparing them with the package.

Likewise, a receipt field declaring that curve targets were registered before
execution does not prove chronology by itself. Registration chronology rests
on the externally frozen protocol and amendments; the receipt only carries the
pinned declaration.

## Amendment J: portable source-bound comparison

Runtime-envelope fields and their environment-receipt hashes are retained as
producer metadata and internal bindings. A fresh source-bound acceptance does
not require those environment receipts to byte-match the historical producer
environment: a Python patch-version or platform-string change is not a
released-row mismatch.

Source-bound acceptance instead requires both freshly executed roots to pass,
their two stable receipts to be byte-identical to each other, and those stable
receipts to byte-match the installed package. It also requires the deterministic
comparison projection—schema, labels, registered seeds, checker and stable-file
hashes, equality status, provenance ceiling, and boundary—to match while
excluding environment-receipt hashes. Receipt-only still validates the stored
environment hashes internally but does not claim that they authenticate an
execution event.

## Final stop rule

Any exact-type failure, whole-audit digest mismatch, non-canonical receipt,
comparison byte mismatch at installation, extra package file, or mismatch in
an earlier gate is a hard failure. A symlink or unsupported package-entry type
is likewise a hard failure. Neither the preliminary receipts nor the
first corrected receipts become valid because a later execution passes. Only
a fresh two-root execution of the final checker, followed by independent
install, receipt-chain regressions, checksum generation, receipt-only
verification, and fresh source-bound stable-byte matching may support the
public released-row verdict. The package itself still does not attest the
historical existence or independence of those executions.
