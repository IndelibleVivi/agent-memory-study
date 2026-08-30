# MNL promotion-cohort and coverage audit

This checked, deterministic artifact accompanies an Agent Memory Study close
read of *Mistake Notebook Learning: Batch-Clustered Failures for Training-Free
Agent Adaptation* ([ACL Anthology `2026.findings-acl.719`](https://aclanthology.org/2026.findings-acl.719/)).
It executes model-free synthetic contract cases through exact methods loaded
from the current official
[`Bairong-Xdynamics/MistakeNotebookLearning`](https://github.com/Bairong-Xdynamics/MistakeNotebookLearning)
source at commit `dc7de755522ad58864c62b74ab8e9959c01b7f23`.

The primary result is a **cohort-conservation boundary**. Complete-cohort
positive, balanced, and all-tie controls followed the expected net
win-minus-loss admission rule. But three stage-specific filtered cases admitted
one KB update after evaluating only survivors from four enrolled items:

- two baseline responses were unavailable before candidate construction;
- two updated responses were unavailable in one case; and
- two updated prompts were empty and filtered before updated generation in the
  other.

In all three cases, exact current source accepted the survivor-level `+2`
result.
The full enrolled-cohort decision is `UNDEFINED_FROM_OBSERVED_RESULTS`, because
two items have no updated comparison. A separately labeled
`missing_as_failure` sensitivity produces delta `0`; that counterfactual is not
an observation and this artifact does **not** call unavailable items losses.

A fourth incomplete case placed an empty updated prompt in the middle of the
cohort and retained a later loss. Exact current source accepted the three
survivors at `2W / 1L`, but its source-owned negative/debug record paired the
later question with the preceding survivor's baseline prompt. This is a
prompt-provenance mismatch: baseline prompts are not inputs to the evaluator,
so the result does not claim changed admission arithmetic or KB state.

The complete net-positive group case also accepted `3` wins in group A and `1`
loss in group B. Net batch admission therefore does not by itself establish
per-item or subgroup non-regression.

Three secondary current-source probes passed:

- `KnowledgeBase.update_entry` appended a second exact-subject entry; with
  equal embeddings and `top_k=1`, stable equal-score ordering returned the
  older entry; and
- `_evaluate_on_eval_set` reported accuracy `1.0` after one of two enrolled
  questions had no surviving candidate. The separate enrolled coverage is
  `0.5`, and unconditional correct-over-attempted is also `0.5`; and
- the exact class default asked for only two to three sentences and required
  none of the paper's five named guidance components, while static AST
  inspection found all five in the hash-locked DBQA custom template and
  confirmed that the example injects it. The same current example points its
  train and eval variables at one file. These are default/example source
  contracts, not paper-experiment claims.

These are bounded synthetic source-contract results. They are not paper
headline reproduction, model evaluation, a prevalence estimate, a production
incident, a security finding, or proof of behavior at the paper-time revision.
The locked commit was current official `main` when selected, but its binding to
the paper's production revision is `NOT_ESTABLISHED`.

The artifact also does not decide canonical AMS integration. Its machine
decision explicitly records
`canonical_ams_status.public_note_depth = not_assessed_by_evidence_artifact`.

## Method

[`PROTOCOL.md`](./PROTOCOL.md) froze the original eight batch cases, the
exact-subject probe, the evaluation-denominator probe, identity ledgers, KB
state checks, mutation controls, falsifiers, and the claim ceiling before their
formal execution. An independent review requested before execution arrived
only afterward. [`REVIEW-AMENDMENT.md`](./REVIEW-AMENDMENT.md) preserves that
chronology, records the disposition, and freezes the two added cases before
their follow-up execution.

The standard-library runner declares four direct source-code inputs:

- `examples/example_dbqa.py`, inspected statically and never imported;
- `mnl/trainer.py`;
- `mnl/evaluator.py`; and
- `mnl/knowledge_base.py`.

It dynamically loads exact `PromptTuner`, `Evaluator`, and `KnowledgeBase`
methods under narrow synthetic adapters for classification/generation,
embeddings/rewards, JSONL I/O, batching, minimal vector operations, and optional
imports. The JSONL and batching adapters are AMS-authored test infrastructure,
not upstream `mnl/utils.py` execution. A process-local guard recorded zero calls
through Python's `socket.socket` and `socket.create_connection`; it is not
raw-syscall or operating-system network instrumentation. No model, API,
credential, dataset, paper experiment, or upstream environment was used.

The manifest records clean Git status and matching allowlisted-byte locks both
before and after each run. Those are endpoint observations, not proof of mount
immutability or absence of transient/ignored writes. File reads were not
instrumented; the four-file allowlist is a declared and code-reviewable runner
contract, not an operating-system access trace. Runtime bindings for the three
imported modules are stored as repo-relative paths; the fourth allowlisted file
is static evidence only.

The `None` fixtures exercise a return value that the exact trainer explicitly
handles at its custom generation boundary. They do not establish that bundled
ordinary wrappers commonly return `None` or estimate the frequency of this
path.

For every rejected or skipped batch, both in-memory KB state and serialized KB
bytes exactly matched prestate. Every accepted batch produced exactly one
declared synthetic entry, and the serialized state exactly matched memory.
Every batch row also retains explicit per-item original index, stage states,
missing stage, effective comparison index, reward vector, and normalized
outcome. Eight isolated mutations were all rejected, including deletion of an enrolled
identity, relabeling an unavailable result as a loss, a flipped admission,
rejected-state drift, evaluation-denominator drift, changed top-1 output,
relabeling baseline-stage missingness, and hiding the prompt-provenance
mismatch.

Formal run A used `PYTHONHASHSEED=313`; run B used `727`. All six stable primary
receipts were byte-identical. This proves repeatability only inside the checked
execution envelope, not correctness across platforms or independent empirical
replication.

## Evidence map

The package intentionally contains fifteen files: six root surfaces and nine
public-safe raw receipts.

| Surface | Contents | Boundary |
| --- | --- | --- |
| `PROTOCOL.md` | Frozen pre-execution cases and claim ceiling | Source inspection preceded freezing; not blinded research. |
| `REVIEW-AMENDMENT.md` | Delayed-review chronology, disposition, and two frozen follow-up cases | Does not rewrite the original protocol or redistribute the private review. |
| `audit.py` | Source-bound runner, derivation, controls, compare/install checks | Newly authored stdlib test infrastructure. |
| `verify_checked.py` | Receipt-only and fresh source-bound verifier | Receipt-only mode does not reopen external evidence. |
| `raw/cases.json` | Exact synthetic inputs and expectations | AMS-authored fixtures, not benchmark records. |
| `raw/run_results.jsonl` | Per-item and stage identity receipts, admissions, prompt bindings, state digests, group deltas, KB/eval/static/Python-socket probes | Synthetic source-bound execution plus explicitly labeled static source evidence. |
| `raw/decision.json` | Re-derived bounded decision and canonical-status non-authority | Does not assign public note depth. |
| `raw/source_manifest.json` | Commit/tree, four-file allowlist, repo-relative runtime bindings, pre/post endpoint checks, Git blobs/SHA-256, paper identity | No read-access or mount-immutability proof; paper-time binding absent. |
| `raw/mutation_controls.json` | Eight detected falsifiers | Verifier sensitivity, not upstream tests. |
| `raw/public_safety.json` | Stable-primary receipt scan | No local paths, credentials, or copied upstream source in scanned receipts. |
| `raw/comparison.json` | A/B primary byte-identity binding | Distinct hash seeds, same environment. |
| `raw/environment_run_a.json`, `raw/environment_run_b.json` | Bounded runtime envelopes | Environment description, not portability evidence. |
| `checksums.sha256` | Every package file except the manifest itself | Package integrity only. |

## Verify and reproduce

Verify the installed receipts without reopening source or paper:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 verify_checked.py --mode receipt-only
```

For fresh source-bound verification, acquire the official source and paper
outside this artifact, check out the exact commit in a clean worktree, and put
all transient output on a roomy external disk. The `--work-root` path must not
already exist:

```bash
MNL_SOURCE=/path/to/MistakeNotebookLearning
MNL_PAPER=/path/to/07-su-2026-mistake-notebook-learning.pdf
MNL_VERIFY_WORK=/external-disk/mnl-source-bound-fresh

git -C "$MNL_SOURCE" checkout dc7de755522ad58864c62b74ab8e9959c01b7f23
git -C "$MNL_SOURCE" status --short

PYTHONDONTWRITEBYTECODE=1 python3 verify_checked.py \
  --mode source-bound \
  --source "$MNL_SOURCE" \
  --paper-pdf "$MNL_PAPER" \
  --work-root "$MNL_VERIFY_WORK"
```

The verifier creates fresh A/B roots, reruns exact-source probes under seeds
`313` and `727`, requires their six stable receipts to match, and then requires
both fresh sets to byte-match the checked package. It leaves the work roots in
place for inspection and requires the official checkout to remain clean.

The lower-level commands are also available when separate run envelopes are
needed:

```bash
MNL_WORK=/external-disk/mnl-audit-two-run

TZ=UTC LC_ALL=C.UTF-8 PYTHONHASHSEED=313 PYTHONDONTWRITEBYTECODE=1 \
  python3 audit.py run --source "$MNL_SOURCE" --paper-pdf "$MNL_PAPER" \
  --output "$MNL_WORK/run-a" --run-label A

TZ=UTC LC_ALL=C.UTF-8 PYTHONHASHSEED=727 PYTHONDONTWRITEBYTECODE=1 \
  python3 audit.py run --source "$MNL_SOURCE" --paper-pdf "$MNL_PAPER" \
  --output "$MNL_WORK/run-b" --run-label B

PYTHONDONTWRITEBYTECODE=1 python3 audit.py compare \
  --run-a "$MNL_WORK/run-a" --run-b "$MNL_WORK/run-b" \
  --output "$MNL_WORK/comparison.json"
```

## Rights and publication boundary

The artifact copies no upstream source, paper PDF, dataset, prompt, response,
or model output. The official source and paper retain their own terms. Newly
authored AMS code and prose currently receive no new public license grant; the
repository's owner must choose any future license deliberately.
