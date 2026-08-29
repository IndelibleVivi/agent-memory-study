# Memora judge-protocol and forgetting-contract audit

This deterministic, model-free artifact accompanies an Agent Memory Study close
read of *From Recall to Forgetting: Benchmarking Long-Term Memory for
Personalized Agents* ([`arXiv:2604.20006v1`](https://arxiv.org/abs/2604.20006v1))
and the official [`geniesinc/Memora`](https://github.com/geniesinc/Memora)
release.

The checked result is **PASS** at official source
`a6493188efc836d6511ed5e4163fe3ba87da30ff`, compared with its direct parent
`e19ebbd1089465876dca11b09e70256977f9755f`. It binds six distinct evidence
objects without collapsing them:

| Evidence object | What it establishes | What it does not establish |
| --- | --- | --- |
| Paper v1 | Reported equation, Table 2 census, three-judge protocol, Appendix D.2 example | Exact production source/data revision or checked response population |
| Historical direct-parent source | The exact pre-repair Track-2 import/fallback path | That the paper's production run used this revision |
| Current official source | Current initialization, voting, FAMA and aggregation behavior | A benchmark result or repair retroactively applied to paper runs |
| Official offline tests | Five selected tests pass in the recorded local environment | Full benchmark reproduction or network/backend integration |
| Synthetic contract fixtures | Cardinality, arithmetic and aggregation edge behavior | Model quality, prevalence or production effect |
| Released inputs | Exact question/criterion/identity geometry at the locked commit | Responses, judge verdicts or Table-3 cells |

No model, LLM judge, memory backend, embedding service, API or network endpoint
was called. The artifact copies neither the paper PDF nor upstream source,
question text, conversations, responses or private notes.

Protocol chronology is explicit. The work began from a privately held pretest
freeze dated 2026-08-29. [`PREREGISTRATION.md`](./PREREGISTRATION.md) is a
post-execution public-safe claim-level reconstruction, not the contemporaneous
private source and not itself a pre-execution public preregistration. It keeps
the recovered hypotheses separate from reviewer-driven amendments to FAMA
oracle scope, import-origin evidence, adjacent judge matrices, the invalid
direct-function probe, and package-acceptance terminology.

## Results

### 1. Judge binding changed, but the two current tracks still have different edges

At the historical direct parent, Track 2 appended
`evals/agent_eval/model_eval`, a nonexistent in-tree directory. In an isolated
source-exact constructor probe with no ambient `api_client`, the import failed
and the caught failure set `use_multi_judge=False` without raising.

At the current revision, the shared helper resolves `evals/model_eval`. The
audit also executed the exact `model_eval_dir()` and
`import_openrouter_client()` helpers in a fresh guarded process with no
pre-cached `api_client`: both `api_client.__file__` and the
`OpenRouterClient` class source resolved to
`evals/model_eval/api_client.py`.

That successful origin is environment-specific, not a binding guarantee. The
upstream helper uses `sys.path.append` followed by the unqualified import
`from api_client import OpenRouterClient`; a pre-cached `api_client` or one on
an earlier `sys.path` entry can still shadow the intended file. The official
regression test asserts the returned class name only, not its source origin.

The current Track-2 constructor-control-flow matrix behaved as follows under
deterministic fake client constructors:

| Initialized fake clients | Non-strict | Strict |
| ---: | --- | --- |
| 0/3 | continues with `use_multi_judge=False` | raises `RuntimeError` |
| 1/3 | continues with `use_multi_judge=False` | raises `RuntimeError` |
| 2/3 | continues with `use_multi_judge=False` | raises `RuntimeError` |
| 3/3 | continues with three judges | continues with three judges |

The exact current Track-1 constructor control flow has no corresponding
all-three gate: under the same fake-client method it raises at 0/3 but accepts
1/3, 2/3 and 3/3. These matrices execute exact upstream class logic but do not
construct `api_client.OpenRouterClient`, contact a backend, or establish real
backend initialization rates.

Initialization is not the whole quorum contract. Once three clients exist,
both tracks drop runtime judge errors and vote over only the valid results. In
the synthetic 0/1/2/3-valid matrix, strict-majority correctness was
`false/true/false/true`. With one `yes` and one `no`, Track 1 labeled consensus
`tie`; Track 2 labeled it `no`; both marked correctness false. Thus Track-2
`--strict-judges` binds initialization cardinality, but neither runtime voting
path requires three valid decisions for each criterion.

These are source-contract observations, not evidence that any paper result used
a reduced quorum. The exact matrices are in
[`raw/judge_binding.json`](./raw/judge_binding.json).

### 2. FAMA evidence splits between the paper equation and source-only zero-bucket conventions

The runner AST-extracted both exact `fama_score` definitions. The 784
source-valid integer counter tuples whose totals are each 0–6 are partitioned
by evidence domain:

- 729 `paper_equation_domain` fixtures, where both denominators are positive,
  produced 1,458 function comparisons against an independent
  `fractions.Fraction` implementation of the reported equation;
- 55 `source_zero_bucket_extensions` fixtures produced 110 comparisons
  against separately encoded conventions observed in both released source
  functions; these conventions are not paper-defined;
- across the combined source-valid matrix, maximum absolute error was
  `1.1102230246251565e-16`, all values stayed in `[0,1]`, and 1,176
  forgetting-monotonicity checks passed; and
- all 156 distinct `(N_presence, N_forget)` pairs in the release passed corner
  checks against both functions.

The 729/55 partition and zero-denominator oracle guard are a post-execution
review amendment. The pretest protocol fixed the same exhaustive 784 valid
inputs but did not pre-count/name those evidence domains.

Current source returns `0` when both totals are zero, returns `0` after the
non-negative clamp when presence is empty, and reduces to `MPA` when forgetting
is empty. The paper's physical-page-6 prose does not specify either empty-bucket
convention, and the independent paper-equation oracle is never defined or
called with a zero denominator.

The deliberately out-of-domain direct call `(3, 2, 0, 0)` returned `1.5` in
both implementations. This shows that the standalone functions neither reject
`correct > total` nor upper-clamp invalid input. Released call sites derive
valid counters; the probe is not observed benchmark output and was added after
execution rather than preregistered in the frozen valid-only matrix. See
[`raw/fama.json`](./raw/fama.json).

### 3. The locked release has 6,415 criteria, not the paper's 7,054

The full release census is:

| Period | Files | Questions | Released criteria | Paper Table 2 | Difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| Weekly | 10 | 150 | 735 | 749 | 14 |
| Monthly | 10 | 150 | 1,315 | 1,421 | 106 |
| Quarterly | 10 | 300 | 4,365 | 4,884 | 519 |
| **Total** | **30** | **600** | **6,415** | **7,054** | **639** |

The locked 6,415 criteria contain 2,947 `memory_presence/yes` and 3,468
`forgetting_absence/no` objects. All declared counters reconcile. Every
question has at least one presence criterion. There are 204 zero-forgetting
questions: all 200 Reasoning questions and four Remembering questions.

This is **paper/release input-census drift only**. Without the paper-run input
revision and result provenance, it does not identify which population produced
Table 3 or invalidate a reported cell.

Identity also needs a scope. File-local and composite
`(period, persona, id)` identities are unique, but bare IDs are not:

- 38 question-ID collision groups (76 rows), all with different payloads;
- 178 criterion-ID collision groups (356 rows), 175 with different payloads;
- three criterion collision groups have identical payloads, and the checked
  receipt records all three path-pair loci.

Lexical substring counts for `mention`, `reflect`, `include` and other frozen
surfaces are included only as mechanical discovery, not semantic reliance or
prevalence. Exact per-file/task rows, file hashes, collision geometry and
lexical counts are in [`raw/census.json`](./raw/census.json).

### 4. Aggregation is an unweighted report macro with no completeness or dedupe gate

The exact `aggregate_table3` function averages report-level task FAMA values.
Two synthetic reports with FAMA `0` and `1` but one and nine questions produced
`0.5`; the question-weighted control was `0.9`. A real zero-FAMA row was
included, while missing FAMA and zero-question task rows were excluded. A
missing period became `unknown`, and duplicate report rows were retained.

In the complete released question geometry, every persona file contains five
questions per task for weekly/monthly and ten per task for quarterly. Under the
additional condition of exactly one complete report per released run,
equal-report and per-question task means therefore coincide. The aggregator
itself does not check that condition; partial, unequal or duplicate reports can
diverge. See [`raw/aggregator.json`](./raw/aggregator.json).

The recovered pretest aggregation hypothesis had predicted an equal mean of
per-question FAMA inside each bucket. Exact source did not support that as the
executable aggregation contract. The protocol record marks the hypothesis as
not supported and preserves the conditional equal-question coincidence rather
than rewriting the prediction after seeing the source.

### 5. One paper-authored example creates a mention-versus-reliance tension

On physical pages 23–24, the desired Appendix D.2 answer says the user is
`leaning away from James Stewart`. The adjacent expected-No criterion asks
whether the answer will `reflect or mention ... James Stewart`. The exact
expected-No object also exists in the locked release at the locator recorded in
[`raw/paper_locator.json`](./raw/paper_locator.json).

A literal mention rule can reject a contrastive statement that expresses
movement away from obsolete state. That is a specification tension in one
paper-authored example. It is not an observed judge verdict, scorer result,
dataset-wide semantic count, prevalence estimate or aggregate-score effect.

### 6. Table 3 cannot be reconstructed model-free from the locked release

The Git tree contains zero checked `eval_report_*.json`, zero checked
`eval_results_*.json`, and zero tracked `eval_results` content. Documentation,
write sites, `.gitignore`, and report discovery all point to run-generated
outputs. The release therefore provides questions, code and schemas, but no
checked response/report population from which Table 3 can be reconstructed
without new model/judge outputs or separate provenance-bearing results. The
source locators are in
[`raw/release_boundary.json`](./raw/release_boundary.json).

## Evidence map

- Protocol provenance, public-safe reconstruction of the private pretest
  commitments, result status and dated post-execution amendments:
  [`PREREGISTRATION.md`](./PREREGISTRATION.md)
- Standard-library runner: [`audit.py`](./audit.py)
- Checked verifier: [`verify_checked.py`](./verify_checked.py)
- Single-run completeness decision:
  [`raw/decision.json`](./raw/decision.json)
- Exact source identities/blobs: [`raw/source_manifest.json`](./raw/source_manifest.json)
- Official test receipt:
  [`raw/official_tests.json`](./raw/official_tests.json) and
  [`raw/official_pytest.txt`](./raw/official_pytest.txt)
- Judge matrices: [`raw/judge_binding.json`](./raw/judge_binding.json)
- FAMA matrix: [`raw/fama.json`](./raw/fama.json)
- Full released-input census: [`raw/census.json`](./raw/census.json)
- Aggregation fixtures: [`raw/aggregator.json`](./raw/aggregator.json)
- Result inventory: [`raw/release_boundary.json`](./raw/release_boundary.json)
- Paper anchors: [`raw/paper_locator.json`](./raw/paper_locator.json)
- Normalized environment: [`raw/environment.json`](./raw/environment.json)
- Two-run byte comparison required for package acceptance:
  [`raw/reproduction.json`](./raw/reproduction.json)
- Exact artifact hashes: [`checksums.sha256`](./checksums.sha256)

## Reproduce

Acquire the official source and paper outside this artifact:

```bash
git clone https://github.com/geniesinc/Memora.git /path/to/Memora
git -C /path/to/Memora checkout a6493188efc836d6511ed5e4163fe3ba87da30ff
git -C /path/to/Memora status --short
```

Prepare an isolated Python interpreter with the official test dependencies. A
complete audit requires `--pytest-python`; omitting it cannot pass the
completeness decision. Run into a fresh path that does not already exist:

```bash
python3 audit.py \
  --source /path/to/Memora \
  --paper-pdf /path/to/from-recall-to-forgetting-arxiv-2604.20006v1.pdf \
  --pytest-python /path/to/audit-venv/bin/python \
  --output /tmp/memora-audit-run-a/out
```

The official tests run from a temporary `git archive` export with Python
bytecode disabled and pytest cache disabled. The runner rejects a changed
export, an existing output path, the wrong/dirty checkout, a non-direct parent,
the wrong paper hash, any failed completeness gate, or any attempt by its
Python children to resolve DNS/connect a socket.

For the checked package, the command was repeated into a second fresh root and
the primary receipts were compared:

```bash
python3 audit.py \
  --compare-left /tmp/memora-audit-run-a/out \
  --compare-right /tmp/memora-audit-run-b/out \
  --compare-receipt /tmp/memora-reproduction.json
```

The 11 primary receipts were byte-identical in the same source, paper, Python,
dependency, OS and machine environment. A `PASS` in `raw/decision.json` covers
one run only; it does not evaluate the reproduction receipt or accept the
installed package. Checked-package acceptance additionally requires
`raw/reproduction.json` and a passing package verifier against reader-supplied
exact evidence:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 verify_checked.py \
  --source /path/to/Memora \
  --paper-pdf /path/to/from-recall-to-forgetting-arxiv-2604.20006v1.pdf
```

## Claim ceiling

This artifact supports exact-revision source behavior, the selected official
offline-test receipt, synthetic contract behavior, released-input geometry, one
paper-authored specification tension and the locked-release result boundary.

It is not a benchmark reproduction. It creates no response or judge verdict,
compares no model or memory system, estimates no effect or semantic prevalence,
does not establish the paper-production source revision, and cannot support a
claim that Table 3 or the paper is invalid.
