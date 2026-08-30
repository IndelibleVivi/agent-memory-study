# MNL promotion-cohort audit: delayed-review amendment

Status before follow-up execution: `delayed_review_received_amendment_frozen_not_run`.

The original [`PROTOCOL.md`](./PROTOCOL.md) remains the frozen authority for
the first eight batch cases. An independent review was requested before that
execution, but its answer arrived only after the original receipts had been
generated and committed as Agent Memory Study commit
`39c409f14e354c3d12fd9a1acab69a78db1ecb12`. This amendment records the
post-execution disposition and freezes two additional cases before their own
formal run. It does not backdate the review, rewrite the original protocol, or
claim that the added cases were preregistered with the first matrix.

The returned review text is private working evidence and is not redistributed
or assigned a public identity receipt. Only the chronology and bounded
disposition needed to explain this follow-up are published here.

## Disposition

| Review point | Disposition | Follow-up consequence |
| --- | --- | --- |
| Admission can also shrink after baseline generation returns per-item `None`. | Accept. | Add a partial baseline-`None` survivor case and extend every identity ledger through that stage. |
| Filtering a middle empty updated prompt can leave `baseline_system_prompts` misaligned in the source negative/debug record. | Accept as a prompt-provenance finding, not an admission-arithmetic finding. | Add a non-suffix empty-prompt case with a later loss and compare the source-logged baseline prompt with the audit-owned question binding. |
| Raw receipts should expose original index, stage states, missing stage, effective comparison index, and reward vector. | Accept with adjustment. | Add explicit per-item records inside each immutable batch receipt while retaining separate aggregate `decision.json`. Missing-as-failure remains a namespaced counterfactual, never an observed outcome. |
| The short class default does not require the paper's five guidance components, while the current DBQA example injects a richer custom template. | Accept as static current-source evidence only. | Execute the exact default-template method and AST-inspect the hash-locked example without importing its top-level API/database/training setup. Do not project the default onto the paper experiments. |
| The current DBQA example points train and eval at the same file. | Accept as static current-example configuration only. | Record the path equality; do not call it a held-out evaluation or paper-run configuration. |
| The existing harness must not use source negative logs or `metrics["losses"]` as decision authority. | Already satisfied. | Continue deriving counts and membership from audit-owned per-item execution receipts. Source negative logs are observed only for the narrow prompt-binding probe. |
| Merge existing positive/subgroup cases and remove the public all-ties control. | Reject as a mandatory retroactive rewrite. | Preserve the executed eight-case chronology. Redundancy does not invalidate a control, and deleting it would not strengthen the bounded claims. |
| Execute exact `train()` with lower held-out evaluation and checkpoint inspection. | Defer to a separately frozen lifecycle/orchestration audit. | The present artifact continues to make no dynamic held-out rollback claim and does not explain Figure 4 or any paper result. |
| Add exact lookup, top-2 ordering, and further storage hashes to the existing exact-subject probe. | Defer. | The current claim remains limited to the already executed exact-subject, equal-embedding, `top_k=1` result. |

## Frozen follow-up cases

### `partial_baseline_none_survivor_accept`

Enroll four stable IDs. Baseline generation returns values for the first two
and intentional `None` for the last two. Only the two baseline survivors may
enter candidate construction, updated retrieval, updated generation, and
comparison. Both observed survivor comparisons are wins.

Expected exact-current-source behavior:

- return accepted metrics and persist exactly one declared KB entry;
- retain all four original IDs but only two baseline-valid and evaluated IDs;
- label the two missing items `baseline_response_unavailable`;
- record source survivor delta `+2`; and
- set the full enrolled decision to `UNDEFINED_FROM_OBSERVED_RESULTS`.

The separately labeled missing-as-failure sensitivity is expected to be zero.
It is not a paper policy and is not an observed loss assignment.

### `partial_empty_prompt_provenance_misalignment_accept`

Enroll four stable IDs. Updated prompts are non-empty for positions 0, 2, and
3, while position 1 is empty. The comparable outcomes are win, win, and loss,
so exact current source is expected to accept at survivor delta `+1`.

The source filters the questions and responses after the empty prompt without
filtering `baseline_system_prompts`. Its later reduced-list indices are then
applied to the stale prompt list. The loss at original position 3 is therefore
expected to be logged with the baseline prompt for original position 2 rather
than its own prompt. The audit must record both bindings and classify this as
`MISALIGNED`.

This finding is limited to the source-owned negative/debug record. Baseline
prompts are not inputs to `Evaluator.evaluate_batch`, so the probe does not
claim that the mismatch changes wins, losses, admission, or KB state.

## Follow-up receipt and stop contract

Every batch receipt must keep ordered original, baseline-valid,
updated-prompt-valid, updated-response-valid, and evaluated identity lists. It
must also contain one explicit per-item record with original index, subject,
external group, baseline and updated stage states, missing stage, inclusion,
effective comparison index, reward vector, and normalized outcome. Counts are
derived from those outcomes; `metrics["losses"]` is never consumed as a count.

The follow-up execution inherits the original source, paper, out-of-tree,
state-binding, public-safety, socket-guard, two-run, and no-redistribution stop
conditions. In addition, it must:

- load the same exact source modules from the locked checkout and publish only
  repo-relative runtime module bindings;
- hash-lock the statically inspected DBQA example without importing it;
- detect a mutation that relabels the baseline missing stage;
- detect a mutation that hides the prompt-provenance mismatch; and
- reproduce all ten batch cases and the KB, evaluation, static-source, and
  runtime-guard probes twice from fresh external-disk roots.

The original eight-case results remain valid within their executed scope even
if a follow-up condition fails. A failure would hold the amended package and
the broader three-stage admission-completeness claim; it would not silently
erase or reinterpret the earlier receipts.
