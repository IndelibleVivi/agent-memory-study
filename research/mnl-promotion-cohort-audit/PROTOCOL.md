# MNL promotion-cohort and coverage audit: frozen protocol

Status before execution: `source_inspected_frozen_not_run`.

This protocol freezes a deterministic, model-free, source-bound audit of
*Mistake Notebook Learning: Batch-Clustered Failures for Training-Free Agent
Adaptation* before the formal synthetic cases are executed. It was written
after reading the ACL 2026 paper and inspecting the current official source,
but before generating the checked receipts. Results belong in separate files
and must not be back-edited into this protocol.

## Locked evidence objects

- Paper: ACL Anthology `2026.findings-acl.719`, DOI
  `10.18653/v1/2026.findings-acl.719`.
- Reviewed 17-page paper PDF: SHA-256
  `39137385c4e96bd83bfc0dfc4363733d0c91107a605999e074e5681065335c9c`.
- Official source: [`Bairong-Xdynamics/MistakeNotebookLearning`](https://github.com/Bairong-Xdynamics/MistakeNotebookLearning)
  at exact commit `dc7de755522ad58864c62b74ab8e9959c01b7f23`.
- The locked commit was current `main` when selected. It is not tagged, and no
  source-to-paper production-revision receipt was found. The audit therefore
  calls it `exact current official source`, never `paper-time source`.
- Exact inspected implementation files are locked by both Git blob and SHA-256
  in the generated source manifest. The artifact copies no upstream source.

Evidence vocabulary is fixed:

- statements in the paper are `paper-reported`;
- paths and behavior at the locked commit are `exact-current-source`;
- executions of newly authored fixed inputs through exact loaded source methods
  are `synthetic source-bound contract tests`;
- calculations that assign a counterfactual score to unavailable cases are
  `audit sensitivity`, not observations and not source behavior;
- interpretations that join paper wording to current-source behavior are
  `editorial inferences`.

## Question and exact methods under test

The primary question is:

> Does the exact current `_process_batch` promotion decision conserve the full
> enrolled batch identity assumed by the paper's batch delta, and which weaker
> guarantees does a positive survivor-level aggregate actually establish?

The runner dynamically loads, without installing upstream dependencies:

- `PromptTuner._process_batch` and `PromptTuner._evaluate_on_eval_set` from
  `mnl/trainer.py`;
- `Evaluator.evaluate_batch` and `Evaluator.evaluate_single` from
  `mnl/evaluator.py`;
- `KnowledgeBase.update_entry`, `_save_entries`, and `retrieve_by_subject` from
  `mnl/knowledge_base.py`.

External modules are replaced only with narrow standard-library stubs needed
to import those files. Synthetic classification, generation, embeddings, and
reward outcomes are fixed inputs. A protocol-declared JSONL adapter captures
the exact KB method's save call, and a protocol-declared batch splitter supplies
the eval fixture; neither is presented as upstream `mnl/utils.py` execution.
The source methods named above are not reimplemented. A process-local guard
fails calls through Python's `socket.socket` and `socket.create_connection`;
it is not raw-syscall or operating-system network instrumentation. The runner
declares only those three exact files as direct
source-code inputs and stubs their relative imports; it does not intentionally
open `.env`, examples, datasets, or unrelated source. File-read access is not
instrumented, so the allowlist is a runner contract plus code-reviewable path
set, not an operating-system read trace.

`None` is deliberately injected at the custom `batch_generate` boundary because
the exact trainer explicitly handles it. This establishes behavior for that
accepted source-level return value; it does not establish that ordinary bundled
wrappers commonly emit `None`, or estimate how often any production caller does.

## Frozen batch matrix

Every batch item has a stable public-safe ID. The identity ledger must retain,
in order, the original IDs, baseline-valid IDs, non-empty-updated-prompt IDs,
updated-response-valid IDs, and evaluated IDs.

| Case | Original cohort | Fixed updated outcomes | Expected exact-source result | Required interpretation |
| --- | ---: | --- | --- | --- |
| `complete_positive_accept` | 4 | 3 wins, 1 loss | accept; exactly one KB entry appended and serialized | Complete-cohort positive control. |
| `complete_balanced_reject` | 4 | 2 wins, 2 losses | rollback | Complete-cohort non-positive control. |
| `complete_all_ties_reject` | 3 | 3 ties | rollback | All-ties control. |
| `partial_updated_none_survivor_accept` | 4 | 2 survivor wins, 2 unavailable updated responses | survivor-level accept | Admission is `INCOMPLETE`: two enrolled IDs are absent from evaluation. Missing-as-failure delta is recorded only as sensitivity and is expected to be zero. |
| `partial_empty_prompt_survivor_accept` | 4 | 2 survivor wins, 2 empty updated prompts | survivor-level accept | Admission is `INCOMPLETE`: prompt-filtered IDs never reach updated generation or comparison. Missing-as-failure is sensitivity only. |
| `all_updated_prompts_empty_rollback` | 3 | all updated prompts empty | return without admission; rollback | Empty-prompt rollback control. |
| `all_updated_responses_none_rollback` | 3 | all updated responses unavailable | return without admission; rollback | All-failed-updated rollback control. |
| `net_accept_with_group_loss` | 4 | group A: 3 wins; group B: 1 loss | accept | A positive batch aggregate does not establish subgroup or per-item non-regression. |

For every rejected or skipped batch, both the in-memory KB state and the
serialized KB bytes must exactly equal their prestate. For every accepted batch,
the in-memory and serialized states must agree and differ from the prestate by
exactly the one declared synthetic entry. Any other mutation invalidates the
case.

The source-observed admission score is computed only over evaluated survivors.
For incomplete cases, the ledger separately reports:

1. survivor wins, losses, ties, and delta;
2. unavailable/filter status by original ID; and
3. a counterfactual `missing_as_failure` delta.

The third value is never relabeled as observed loss. A full-batch decision is
`UNDEFINED_FROM_OBSERVED_RESULTS` when enrolled cases lack updated comparisons.

## Frozen knowledge-base and evaluation probes

### Exact-subject append and stable top-1 shadowing

Begin with one synthetic KB entry for an exact subject and embedding. Call the
exact `KnowledgeBase.update_entry` with the same subject and an equal embedding,
then call the exact `retrieve_by_subject(..., top_k=1)` under the frozen
standard-library vector stub. Expected current-source result: two same-subject
entries remain, and stable sorting of the equal similarity scores returns the
older entry first. This tests a bounded exact-subject/equal-embedding mechanism;
it does not estimate retrieval frequency, claim semantic incorrectness, or
reproduce the paper's experiments.

### Evaluation denominator coverage

Call exact `_evaluate_on_eval_set` on two enrolled questions at `@1`. One fixed
question has a correct response; every candidate for the second is unavailable.
Expected current-source result: reported accuracy `1.0` over one surviving
question. The audit separately records enrolled coverage `1/2 = 0.5`. This is a
denominator observability probe, not a model-accuracy estimate.

Periodic held-out rollback and `best_eval_score` lifecycle are outside this
artifact. They are distinct from the paper's within-batch promotion equation
and must not be smuggled into the primary claim.

## Controls, falsifiers, and stop conditions

The checked runner must reject isolated synthetic mutations that:

- delete an original ID from an identity ledger;
- flip an observed admission decision;
- relabel an unavailable updated response as an observed loss;
- alter a rejected batch's serialized poststate digest;
- change the evaluation enrolled denominator; or
- replace the exact-subject top-1 result with the newly appended entry.

Stop or narrow the affected case if the source commit, pre/post Git cleanliness,
pre/post allowlisted-byte locks, paper digest, case identities, or expected
exact methods do not match; if either guarded Python socket API is called; if two fresh
deterministic runs differ; or if any checked mutation survives validation.
These endpoint checks do not prove mount immutability and do not instrument
transient or ignored writes.

## Claim ceiling

A matching result may establish, at the locked current source, that:

- complete cohorts follow the net win-minus-loss admission rule in the fixed
  controls;
- updated-response and updated-prompt filtering can produce a positive
  survivor-level admission while the full enrolled-cohort decision is
  observationally incomplete;
- a net-positive batch can include a losing subgroup/item;
- exact-subject append plus equal-similarity stable top-1 can return the older
  entry; and
- an all-failed evaluation question can be absent from the reported accuracy
  denominator, requiring a separate coverage value.

It may not establish the paper's headline benchmark results, model quality,
real-world prevalence, causal harm, production reliability, a security issue,
or behavior at an unverified paper-time revision. It does not call unavailable
cases losses. It runs no model, API, benchmark dataset, upstream environment,
or paper experiment. Newly authored AMS code and prose remain
`pending_owner_choice`; this protocol creates no license grant.
