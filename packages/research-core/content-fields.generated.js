// Generated from schemas/core.schema.json. Do not edit.
export const CONTENT_FIELDS = {
  "capture": [
    "actor",
    "attention",
    "captured_at",
    "channel",
    "input",
    "visibility",
    "why_now"
  ],
  "source_work": [
    "aliases",
    "authors",
    "identifiers",
    "manifestations",
    "short_author",
    "title",
    "visibility",
    "work_type",
    "year"
  ],
  "source_revision": [
    "identity",
    "predecessor_ref",
    "work_ref"
  ],
  "artifact": [
    "artifact_digest",
    "byte_length",
    "media_type",
    "obtained_at",
    "representation_of",
    "role",
    "source_revision_ref",
    "storage",
    "visibility"
  ],
  "extraction": [
    "config_digest",
    "coverage",
    "extractor",
    "extractor_version",
    "input_artifact_ref",
    "output_artifact_ref",
    "source_revision_ref"
  ],
  "read_activity": [
    "actor",
    "extent",
    "method",
    "occurred_at",
    "receipt_ref",
    "representation_ref",
    "target_ref"
  ],
  "excerpt": [
    "comment",
    "representation_ref",
    "selector",
    "target_ref"
  ],
  "source_note": [
    "alias",
    "byline",
    "date",
    "intro",
    "navigation",
    "note_depth",
    "payload",
    "reading_scope",
    "source_revision_ref",
    "title",
    "work_ref"
  ],
  "entry": [
    "body_file",
    "byline",
    "date",
    "entry_type",
    "intro",
    "payload",
    "references",
    "title"
  ],
  "claim_revision": [
    "byline",
    "claim",
    "payload",
    "scope",
    "scope_binding",
    "title"
  ],
  "thread": [
    "byline",
    "payload",
    "status",
    "title"
  ],
  "session": [
    "payload",
    "started_at",
    "thread_ref",
    "visibility"
  ],
  "relation_proposal": [
    "from_ref",
    "generated_by",
    "locator",
    "method_version",
    "rationale",
    "relation",
    "scope",
    "scope_binding",
    "status",
    "to_ref"
  ],
  "evidence_relation": [
    "from_ref",
    "locator",
    "proposal_ref",
    "rationale",
    "relation",
    "review",
    "scope",
    "scope_binding",
    "status",
    "to_ref"
  ],
  "support_bundle": [
    "combination",
    "conclusion_ref",
    "independence",
    "premise_refs",
    "rationale",
    "relation_refs",
    "review",
    "scope",
    "scope_binding",
    "warrant_refs"
  ],
  "observation": [
    "basis_refs",
    "run_ref",
    "scope",
    "statement"
  ],
  "design": [
    "body",
    "status",
    "title"
  ],
  "run": [
    "code_ref",
    "config_ref",
    "dataset_refs",
    "executor",
    "protocol_ref",
    "result_artifact_refs",
    "rubric_ref",
    "started_at",
    "status"
  ],
  "analysis": [
    "method",
    "observation_refs",
    "result",
    "run_refs",
    "scope"
  ],
  "changeset": [
    "application_state",
    "items",
    "publication_refs",
    "review_state"
  ],
  "publication_manifest": [
    "base_git_commit",
    "prepared_by",
    "selected_refs",
    "visibility"
  ],
  "command": [
    "actor",
    "command_id",
    "expected_revision",
    "idempotency_key",
    "operation",
    "record",
    "target"
  ]
};
