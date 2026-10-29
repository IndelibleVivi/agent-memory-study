# AMS core contract

`ams-core/2` is the versioned contract shared by the Python compiler and
`packages/research-core`. It is not the reader's compatibility JSON shape.

## Stable interfaces

- Contract: `schemas/core.schema.json`
- Python validation: `python3 -B schemas/validate.py`
- TypeScript/Node API: `packages/research-core/index.js` and
  `packages/research-core/index.d.ts`
- Immutable reference: `{kind, id, revision}`. `state_revision` points at the
  current immutable snapshot; `expected_revision` compares that pointer.
- Command: `ams-command/1` with `command_id`, `idempotency_key`, `operation`,
  `target`, `actor`, and `record`. Create commands have no base; update commands
  require the prior `expected_revision`.
- Public index: `data/public-corpus.manifest.json`
- Entity shard: `data/corpus/entities/<kind>/<id>.json`
- Revision shard: `data/corpus/revisions/<kind>/<id>/<revision-token>.json`
- Packet shard: `data/corpus/packets/<public-kind>/<public-id>/index.json`
- Route inventory: `data/route-inventory.json`
- Portable packet: `ams-study-packet/2`
- Multi-object collection: `ams-study-collection/2`
- Canonical JSON: `ams-json-canonical/1`; content digests are SHA-256 over the
  named fields under that canonicalization.

`PublicationManifest` is a private selection record. `PublicCorpusManifest` is
the allowlisted compiler index. They are never aliases. The public manifest is
metadata and typed graph only; it does not embed packet or article bodies. Each
object has a reader-visible `public_id` plus an exact core `{kind,id,revision}`;
consumers use `packet_v2`, `shard`, and `revision_shard` directly rather than
guessing a prefix or downloading every object.

The schema carries `x-ams-content-fields` per entity kind. Python derives
`schemas.validate.CONTENT_FIELDS` from it; Node uses
`packages/research-core/content-fields.generated.js` and
`contentFieldsFor(record)`. Regenerate that file from the schema whenever field
ownership changes; `assert_generated_field_parity()` rejects drift. Callers do
not choose digest fields.

`validate_command(command)` validates the envelope, full entity structure,
content digest, identity match, self-pointing new snapshot, and create/update
base rules. Repositories should additionally call
`validate_graph(records, public_records=...)` within the same transaction after
building the candidate snapshot set. That check covers dangling refs, reused
revisions, source lineages, selector/representation binding, accepted
proposals, support bundles, draft bases, and change application state.

## Scientific distinctions

`SourceWork` is stable work identity. `SourceRevision` is a pinned publisher
version or an explicitly observed source snapshot. `Artifact` is exact bytes;
`Extraction` is parser/configuration output; a source note is AMS-authored
content with its own revision, byline, and scope. Re-parsing bytes never creates
a new paper version, and rendering CSS never changes an author content digest.

Navigation membership is separate from references and from argument support.
Candidate proposals stay out of the accepted argument graph. Accepted
`EvidenceRelation` records pin their proposal and carry review or delegation.
`SupportBundle` expresses AND premises and explicit OR warrants. Equal scope
strings do not prove scientific comparability, so accepted relationships also
record a scope binding and rationale.

An Observation can bind historical fixed evidence without inventing a new Run.
Without `run_ref`, `basis_refs` must be nonempty; an Analysis with empty `run_refs`
must name at least one exact Observation. Run and Observation fields enforce their
respective kinds, and all references still resolve inside the validated closure.

The schema checks structure. The semantic validator checks reference resolution,
immutable payload identity, artifact byte hashes, proposal/review alignment,
support structure, command bases, draft bases, and public-manifest shards. It
does not certify truth, independence, reading comprehension, rights, or external
publisher identity.

Private `Thread.title` may be empty until the author names a direction. A
published question must meet the public compiler's title and provenance rules;
that publication requirement does not belong in the private storage contract.
