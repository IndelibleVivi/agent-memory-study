# PM-Bench scorer-contract and released-log audit

This public, deterministic artifact accompanies the Agent Memory Study close read
of *PM-bench: Evaluating prospective memory in LLM agents*. It tests three narrow
properties of the released scorer and asks whether they affect the 64 released
primary logs at the locked official revision.

It does **not** rerun any model, create a new benchmark sample, estimate behavior
outside the released week, or claim that the paper's headline Set-F1 table is
wrong.

## Locked source

- Official repository: [`genglinliu/PMBench`](https://github.com/genglinliu/PMBench)
- Commit: `e1093c470c8981daf522d4ef047a7c3a71e077d7`
- `sim/pm_bench.py` SHA-256: `d8ec27d8dcf4679d7a789c52fc305286df460844d47e9f116b81f2400ac254d8`
- `data/synthetic_week_v9.json` SHA-256: `94a45937da1363be19ccfdc2c188d132f23093041e30abd3ec22d64d70da8f24`
- Paper: arXiv:2607.12385v1; bundled PDF SHA-256
  `ca391936e787ee6597e0ef4bb078913b54cd5ef4151e673f6bb928db39ad67a1`

The runner rejects a wrong commit, source hash, scenario hash, report-builder
hash, checked-report hash, dirty official worktree, incomplete 8 x 8 result
grid, invalid official scenario, unexpected trace site, or unexpected paper
Table 2 aggregate.

## Questions and decisions

### A. Does a monitoring hit prove that the required hidden channel was queried?

**Confirmed scorer behavior; narrower metric interpretation required.**

The exact official scorer gives paired correct actions with zero versus one
email query the same task hit, Set-F1 contribution, proactive-required hit, and
email-channel hit. Only query-call accounting differs. At the locked source,
monitoring and channel hit buckets are category-conditioned action outcomes;
they are not query-provenance metrics (`sim/pm_bench.py:2206-2226,
2522-2581`).

This does not contradict the paper's Appendix A.4 definition, which describes a
task category and its action result (PDF pp. 16-17). It narrows what that number
can establish: a correct action on a task classified as requiring monitoring is
not, by itself, evidence that the agent observed the required channel.

Across the 64 released primary logs, the scorer records 1,062 successful
hit/late completions for proactive-required tasks. Of these, 382 have no
required-channel query on the completion row, and 381 have no such query from
the reconstructed due/cue opportunity through completion. The latter comprise
317 clock and 64 non-clock cases. This is a finite released-corpus count, not a
causal explanation; correct action may arise from inference, earlier context,
or lucky selection.

### B. Does `update_violation` mean that the agent acted on a stale version?

**Confirmed taxonomy mismatch.**

In the exact official synthetic pair, a task rescheduled from 10:00 to 11:00 and
selected at 12:00 is accepted inside the 60-minute late window. The same action
increments `late`, `update_late`, and `update_violation`; the no-update control
is late without a violation. The locked scorer increments the violation when an
updated task is selected outside the exact due set (`sim/pm_bench.py:2517-2518`),
while Appendix A.4 defines the diagnostic in stale-version terms (PDF p. 17).

The released audit traces 541 exact scorer increments. Twenty-seven are also
accepted-late completions of the scorer's current mutable task state, and every
one is an `update_late`. Released action rows contain `task_ids` but no target-
or version-bound selection field, so agent intention cannot be reconstructed:
the semantic count of current-version late actions is bounded from 0 to 27. The
exact scorer-level co-occurrence is 27.

This changes the interpretation of a diagnostic taxonomy. It does not change
Set-F1 TP, FP, or FN.

### C. Is replay scoring bound to declared `step_id` identity?

**Confirmed source-level risk; no released-result impact found.**

The exact official synthetic fixture reverses two JSONL rows while preserving
their correct declared `step_id` values. The score changes from one hit to a
late completion with one FP and one FN. `score_log` groups by declared day and
preserves row order; `score_day` consumes `actions[step_idx]` without realigning
or rejecting by action `step_id` (`sim/pm_bench.py:2350-2367, 2586-2589`).

The released audit separately validates every `(day, step_id)` pair against the
official scenario. All 64 logs have exactly one valid row per scenario step and
the correct within-day order. Identity realignment changes zero scores. The
integrity boundary is real, but it did not alter the released headline results
at the locked commit.

## Released report and paper-facing checks

The official scenario validator passes with 7 days, 80 steps, 83 task
definitions, and no warnings or errors. The paper reports 81 scored tasks because
two of the 83 intentions are canceled (Table 1, PDF p. 4).

The audit finds 64 primary logs: eight models by eight setups, including 48 live
runs and 16 majority/unanimous replay-derived runs. It rescores every log with
the official scorer and asserts the rounded macro/micro Set-F1 values in paper
Table 2. Optional heartbeat remains the best across-model setup by macro Set-F1
at 65.1% (Table 2; §4.2, PDF pp. 7-8).

A fresh run of the official report builder matches the checked report after one
path-only repair: the checked prose says `runs/March_ALL_results_v9`, while the
repository actually contains and the rebuild reports `runs/all_results_v9`.
All derived report content is otherwise byte-identical.

The abstract describes 65.1% as belonging to “the best method, a GPT-5.4
agent.” Table 2 instead identifies 65.1% as the across-model macro for optional
heartbeat, while Table 3 reports 79.1% for GPT-5.4 with optional heartbeat (PDF
pp. 1, 8). This is a statistical-object wording mismatch in the abstract, not
evidence that the released aggregates or tables are wrong.

All 16 replay-derived records have zero duration in their metadata. Those
values describe deterministic replay bookkeeping, not fresh model inference,
and must not be compared as agent runtime against the 48 live runs.

## Method and controls

The runner uses Python's standard library and the official scorer from a clean,
exact checkout. It:

1. checks the commit and hashes before importing source;
2. executes paired direct-scorer fixtures for hidden-query attribution, updated
   late execution, and row-order identity;
3. validates the full released scenario with the official validator;
4. inventories the exact 8 x 8 primary-log grid and distinguishes live from
   replay-derived metadata modes;
5. computes official scores for original rows and for independently identity-
   aligned rows;
6. uses revision-locked CPython line tracing to expose scorer-local task states
   and each `update_violation` increment without editing the checkout;
7. reconstructs required-channel query counts from the due/cue opportunity
   through completion;
8. rebuilds the official comparison report and permits only the one observed
   stale-path substitution; and
9. requires the official checkout to remain clean after execution.

Controls include zero/one-query paired actions, update/no-update paired late
actions, chronological/reversed rows with unchanged IDs, exact scenario
validation, exact source and report hashes, one-run-per-model/setup inventory,
trace-count equality with official summary counts, and paper Table 2 rounded
aggregate assertions.

The three synthetic objects are deliberately scorer-function fixtures, not
complete validator-clean scenarios. The released-corpus lane is the separate
validator-clean whole-scenario control. See [`DEVIATIONS.md`](./DEVIATIONS.md).

## Environment

Checked output was produced on macOS 26.5.2 arm64 with Python 3.13.3 and Git.
No third-party Python package, model, API, API key, or network call is required.
The runner disables bytecode writes and checks that the official checkout stays
clean.

The PDF read-integrity preflight was advisory-only because `pypdf` was not
installed. Page count and anchors were independently cross-checked with
`pdfinfo`, two `pdftotext` modes, 22 page breaks, and rendered visual inspection
of the abstract, Tables 2-3, Appendix A.4, Table 7, and the final page. This is
not labeled a preflight PASS.

## Reproduce

Acquire the official repository and check out the locked commit:

```bash
git clone https://github.com/genglinliu/PMBench.git
git -C PMBench checkout e1093c470c8981daf522d4ef047a7c3a71e077d7
git -C PMBench status --short
```

Run into a new output directory; the runner refuses to overwrite generated
output:

```bash
python3 research/pmbench-scoring-contract-audit/audit.py \
  --source-repo /path/to/PMBench \
  --output-dir /tmp/pmbench-scoring-contract-rebuild
```

Verify the checked artifact without the official checkout:

```bash
python3 research/pmbench-scoring-contract-audit/audit.py --verify-checked
```

On the recorded environment, compare every generated byte with the checked
publication:

```bash
python3 research/pmbench-scoring-contract-audit/audit.py \
  --compare-checked \
  --output-dir /tmp/pmbench-scoring-contract-rebuild
```

## Artifact map

- `RESULTS.txt`: compact derived result.
- `raw/official_probes.json`: exact official scorer-function probe output.
- `raw/decision.json`: released-corpus aggregates and bounded decisions.
- `raw/run_scores.jsonl`: 64 per-run official and identity-aligned scores.
- `raw/hidden_channel_findings.jsonl`: all 1,062 successful proactive-required
  completions and their reconstructed query windows.
- `raw/update_violation_findings.jsonl`: all 541 traced scorer increments and
  current-mutable-state co-occurrence fields.
- `raw/report_comparison.json`: official report rebuild check.
- `raw/source_manifest.json`: exact source, report, and 64 primary-log hashes.
- `raw/environment.txt`: execution environment and no-model/no-network boundary.
- `checksums.sha256`: exact hashes for all generated checked outputs.

## Limits

- This is one released synthetic week generated from one seed. It does not
  estimate stability across seeds, schedule structures, task mixtures, or real
  interruption costs.
- Required-channel absence is an operational log fact, not proof that the agent
  lacked all relevant information or failed to reason about the hidden state.
- The update trace proves exact scorer behavior. Because action rows do not bind
  a task selection to a target version, it cannot label any of the 27 released
  co-occurrences as definitely current-version or definitely stale-version intent.
- Released identity integrity is established only for the 64 locked primary
  logs. It does not make the scorer safe for future malformed or reordered logs.
- Replay-derived majority/unanimous results reuse union-run evidence and are not
  fresh agent executions.
- Paper Ethics cautions that this synthetic diagnostic is not certification for
  high-stakes deployment and notes risks from over-automation and unnecessary
  monitoring (§Ethics Statement, PDF p. 10).
