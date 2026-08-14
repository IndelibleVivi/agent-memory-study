# Revised pre-registration: exact-pair alias/order controller panel

## Evidence object

The proposed study targets current-source AgentRunbook-C's query controller and
the reader-neutral context packages produced from its output. It does not target
the paper's fixed Qwen3.5-9B reader or reproduce LongMemEval-V2 accuracy.

Locked identities:

- paper: arXiv `2605.12493v1`;
- paper-day release: `c5c552dfcf023f5a2939f586541c7f6e55a36d5d`;
- query-boundary fix: `ef67f10aacd9080c75aeb2dd527a0af25dc26f1b`;
- treatment source: `2cc8c540bdb87fe6761629b585e727e1c4704520`;
- public dataset snapshot: `f152293e235517d504809563c833d7190b8c713b`.

Exact file hashes are in `raw/source_lock.json`.

## Eligibility and deterministic selector

Exclude every image-bearing question and every `errors-gotchas` item before
class formation. Retain text-only static, dynamic, procedure, and their `-abs`
variants only when both locked tier maps contain the question and the domain is
`web` or `enterprise`.

For each eligible question, remove only the exact trailing `-abs` from its type
and hash the ordered Medium array using compact ASCII JSON. Form classes keyed
by domain, base type, and ordered-array hash. Select every class containing at
least one answerable and one abstention member; within a class select the
lexicographically smallest member of each role while retaining complete class
membership in the ledger.

The locked files yield three exact classes, six question IDs, and one observed
scope: `web x procedure`. They are a census of public exact-pair support, not a
sample from six domains/types and not recovered hidden provenance.

## Final resolution gate

Before controller execution, stream the locked `trajectories.jsonl` once and
resolve the union required by the selected Small and Medium haystacks. Proceed
only if every selected ID resolves exactly once, every projected record passes
the AXTree schema, state order is preserved, domain membership is unambiguous,
and all three classes remain valid. There are no replacements. Failure of any
class holds the entire controller phase.

## Treatment matrix

Each answerable/abstention question is tested at Small and Medium under:

| Cell | Identity surface | Observable order |
| --- | --- | --- |
| `C00` | original IDs | official order |
| `C10` | rank-preserving opaque aliases | official order |
| `C01` | original IDs | seeded shuffled order |
| `C11` | the same aliases as `C10` | the same shuffle as `C01` |

The declared directly exposed order treatment is the complete concise/full
summary-record order. Current source accepts pre-existing summary files without
rerendering; the checked probe exercises that exact ensure path and the
sandbox-linked `trajectories/` surface. Insertion/index/manifest order is kept
synchronized as a consistency surface but is not claimed to be directly exposed.
Filesystem materialization order is excluded. Medium members of one class share
treatment maps and permutations. All Small members share the web-Small map and
permutations but run in fresh workspaces.

## Planned jobs and repeats

- 48 factorial jobs: 3 classes x 2 roles x 2 tiers x 4 cells;
- 12 exact-input duplicates, one per question-tier unit, rotated evenly across
  the four cells;
- 6 query-only empty-memory controls, one per selected question.

Total: 66 query-method jobs. Current-source retries are system behavior; timeout,
empty, malformed, invalid-span, and exhausted-retry results remain outcomes.

`raw/protocol_ledger.json` prospectively records the hash-derived root seed,
SHA-256 ranking algorithm, all three Medium and one shared Small permutations,
all rank-preserving alias maps, balanced repeat cells, all 66 job records and
their deterministic execution order. It also pins the proposed current-source
runtime configuration: Codex `0.117.0-darwin-arm64`, `gpt-5.4-mini`, `xhigh`,
1800-second timeout, three attempts, empty extra config/args, and the exact query
prompt hash. The ledger is checked but not released for execution because the
full-resolution, signing-trust, and controller-tool network-isolation gates have
not passed.

## Reader-neutral outputs

Primary comparisons are de-aliased selected-state and selected-trajectory set
distances, normalized prose distance, exact evidence-context hash disagreement,
completion/retry outcomes, and valid/invalid/empty span outcomes. Exact-input
repeat distances are reported beside treatment distances as the noise floor;
they are never additional observations or mechanically subtracted.

The ledger defines both set distances as Jaccard distance (empty/empty = 0),
state expansion as de-aliased `(trajectory_id, state_index)` pairs, prose as
Unicode-NFKC/whitespace-normalized character-level Levenshtein divided by maximum
length, and evidence context as SHA-256 over compact canonical JSON containing
ordered valid spans and exact selected public state objects. Missing, malformed,
timeout, exhausted-retry, empty and invalid-span outcomes remain coded; they are
never post-hoc exclusions.

Derived packages are:

- `P`: controller prose only;
- `E`: valid selected AXTree evidence only;
- `B`: current combined context unchanged;
- `G`: semantically supported prose plus the same evidence as `E`.

`G` remains blocked without two independent blinded human raters whose direct-
support labels include intersecting public state locators. A lexical diagnostic
must not be relabeled as semantic support.

## Aggregation boundary

The inferential unit is the exact Medium equivalence class (`N=3`). Report all
three Medium family values, answerable/abstention members, paired differences,
mean, median, range, and leave-one-family-out means. Report all six Small query
effects with the explicit caveat that they share one ordered web Small haystack.
No p-values, standard errors, confidence intervals, or cluster bootstrap are
permitted.

## Whole-phase invalidators

Hold before any controller output if source/data hashes differ, a selected class
fails trajectory resolution, the exact intended CLI/model invocation is not
available, alias/order cells change membership or state content, excluded
question metadata or the sentinel reaches the sandbox, original IDs survive on
declared alias surfaces, controller tool network access succeeds, or output is
opened before the randomization ledger and execution order are frozen.

## Claim ladder

Without controller execution, only selection and intervention feasibility may be
claimed. A complete 66-job run could support finite-panel current-controller
alias/order sensitivity claims for the three web-procedure classes. It could not
support benchmark reproduction, all-question robustness, enterprise/static/
dynamic/gotcha behavior, reader effects, accuracy, Table 2 attribution, or
claims about the May controller run.
