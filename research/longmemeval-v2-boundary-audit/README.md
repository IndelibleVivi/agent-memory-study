# LongMemEval-V2 benchmark-metadata query boundary and answer-evidence audit

This public, synthetic artifact asks two narrower questions than a benchmark
reproduction:

1. What changed between the paper-day release, the 2026-08-05 query-boundary
   fix, and the 2026-08-09 current source?
2. Does the current Codex / AgentRunbook-C postprocessor contractually prevent
   answer-like `memory_markdown` from remaining in its built memory context when
   selected trajectory spans are absent, invalid, or deliberately non-supporting?

The answer to the first question is a versioned source audit. The answer to the
second is an executed CPU-only contract test. Neither result reproduces Table 2,
estimates real-controller frequency, or changes any paper-reported accuracy.

## Decision rules fixed before execution

The query-boundary audit must find all of the following:

- the release harness passed question ID, question type, and the raw question
  item into backend query context;
- release AgentRunbook-R used question type and original goals in its planner;
- release Codex and AgentRunbook-C configs referenced the questions file;
- direct execution of the release AgentRunbook-C payload builder nevertheless
  returns only query text/image for sentinel question metadata and gold, so
  backend-level exposure is not mislabeled as sandbox transfer;
- the fix revision independently uses an exact one-key opaque query context,
  query-text-only AgentRunbook-R prompt, configs without `questions_path`, and a
  text/image-only AgentRunbook-C payload;
- the current revision preserves that boundary and contains regression tests
  asserting it. This artifact locates those tests in source; it does not execute
  the official suite.

The answer-evidence binding property passes only if supported and evidence-only
controls are accepted, the deliberately mismatched status/policy pair is
rejected, and none of these cases retains an answer claim in built context:
empty spans, unknown trajectory, out-of-range state, opposite-value decoy,
`directly_supported` with no support, or `insufficient` plus answer-like prose.
The eight substantive cases are repeated with a second opaque answer token.

## Fixed scope

- paper-day release: `c5c552dfcf023f5a2939f586541c7f6e55a36d5d`
- privacy fix: `ef67f10aacd9080c75aeb2dd527a0af25dc26f1b`
- current source: `2cc8c540bdb87fe6761629b585e727e1c4704520`
- target functions: current `validate_memory_module_output_payload`,
  `_normalize_output_for_query`, and `_build_memory_context_from_output`
- Python standard library only; no model, reader, judge, tokenizer, embedding,
  benchmark data, API key, or network service
- `evidence_mode="axtree"`; fresh temporary workspace for every case

The runner parses exact Git blobs with Python AST, records blob hashes, symbols,
line spans and matched excerpts, and directly executes AgentRunbook-C payload
builders at all three revisions with sentinel metadata. It then executes the
exact current `codex.py` through a minimal import shim. That avoids installing
unrelated optional benchmark dependencies while leaving the tested source files
unchanged. The run manifest includes `codex.py`, `agentrunbook_c.py`,
`agentrunbook_r.py`, `trajectory_store.py`, the harness and the regression test.

## Reproduce

Use a clean official LongMemEval-V2 checkout containing all three revisions and
checked out at the current revision:

```bash
PYTHONHASHSEED=0 python3 research/longmemeval-v2-boundary-audit/audit.py \
  --source-repo /path/to/LongMemEval-V2
```

The runner regenerates `raw/` and `RESULTS.txt`. The checked-in raw directory
contains public fixtures, every case row, normalized outputs, full built memory
contexts, the versioned query audit with source locators, the mechanically derived decision,
environment information, and hashes.

## Result

All sixteen versioned source/payload checks pass. They establish a real boundary
change while preserving a critical distinction: release AgentRunbook-R consumed
benchmark-derived routing hints, but direct execution of the release
AgentRunbook-C payload builder did not serialize sentinel question metadata or
gold into its sandbox question payload. The fix revision and current revision
are reported independently rather than collapsed into one chronology.

The current answer-evidence binding property fails in six patterns, each
replicated with two opaque tokens: answer-like prose remains in built memory
context when spans are empty, unknown, out of range, or point to an
opposite-value decoy; the optional evidence gate also accepts
`directly_supported` with zero valid spans and `insufficient` alongside
answer-like prose. The syntactic status/policy mismatch control is rejected as
intended. The optional gate fields are retained in normalized output but are not
rendered into built memory context; these cases do not claim that the May run or
default current configuration enabled the gate. Exact cases and contexts are in
[`raw/decision.json`](./raw/decision.json) and
[`raw/reader_contexts.jsonl`](./raw/reader_contexts.jsonl).

Current AgentRunbook-C source inherits and invokes the tested normalizer and
context builder without another semantic gate; that bridge is source-inspected,
while the exact Codex postprocessor methods are locally executed. This
demonstrates permission at the current original Codex / AgentRunbook-C
postprocessing boundary, not reader behavior or paper-run behavior. It does not
apply to AgentRunbook-C V2 and cannot estimate frequency, attribute Table 2 gain,
or establish benchmark-answer lookup, sandbox escape, or any other unobserved
transfer.
