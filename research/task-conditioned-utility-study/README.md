# Public memory-utility outcomes: reproduction and bounded reanalysis

AMS research renewal, 2026-11-13. This folder reanalyses **archived model outputs** from Chih-Hsuan Yang, Anjir Ahmed Chowdhury, Feng Yan and Rajeev Thakur, *What Is This Memory Useful For? Measuring Task-Conditioned Utility in Long-Term Agent Memory*, [arXiv:2611.03930v1](https://arxiv.org/html/2611.03930v1). No new model inference, retrieval call, or natural-world sampling was performed.

## What was actually run

The [upstream repository](https://github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory/tree/386ac65a8b5fc46414abdd2755375f2a52d4d3b8) was cloned and pinned at `386ac65a8b5fc46414abdd2755375f2a52d4d3b8`. The official headline and fixed-context scripts completed successfully. AMS's `reanalyze.py` independently deduplicates paired records, recomputes the headline and selected intervals, reports opportunity-conditioned transitions, compares readers on their common cells, and checks a narrow additive restriction on the observed memory–task graph. Commands, versions, source hashes and input hashes are bound in `receipt.json`.

The paper already analyses baseline-conditioned help/harm and warns that sign flips do not establish interaction. Those are reproduced diagnostics. The graph calculation adds an algebraic check of the saved records; it does not identify semantic causal interaction. The baseline-accuracy standardisation is a mathematical scenario, not another model experiment.

## Offline saved-artifact check

From the AMS repository root, with Python 3.10+ and no third-party dependency:

```bash
python3 -B research/task-conditioned-utility-study/check_saved.py --check
python3 -B -m unittest discover -s research/task-conditioned-utility-study -p test_saved.py
```

This gate verifies saved artifact hashes, input/source identity bindings, transition denominators, opportunity identities, the per-memory headline mean, graph accounting, fixed-context contrasts, and figure-data derivation. Its negative checks reject changed artifacts, a changed formula even after its file hash is refreshed, inconsistent figure data, and a false claim of upstream replay.

**The offline gate does not replay upstream rows, recompute confidence intervals, render the figure, contact any service, or authenticate the original inference history.** The compact package checks its own numerical identities and detects drift against its receipt. It is not a substitute for the raw-input replay below. Jointly editing artifacts and their receipt can bypass hash identity; the receipt is a reproducibility contract, not a signature.

## Replay the archived outcomes

Requirements: Python 3.10+ and NumPy. The saved AMS computation used Python 3.12.14 and NumPy 2.3.5. Run these commands from the AMS repository root:

```bash
git clone https://github.com/ChihHsuan-Yang/AAMAS2027-ConditionalMemory.git /tmp/conditional-memory-upstream
git -C /tmp/conditional-memory-upstream checkout 386ac65a8b5fc46414abdd2755375f2a52d4d3b8
python3 /tmp/conditional-memory-upstream/scripts/reproduce_headline.py --bootstrap 10000
python3 -B research/task-conditioned-utility-study/reanalyze.py --upstream /tmp/conditional-memory-upstream --out /tmp/ams-utility-reanalysis.json
```

`reanalyze.py` verifies the commit and SHA-256 of its three upstream inputs before analysis. It rejects nonbinary outcomes, conflicting strata and nonidentical within-cell replicates. Missing rewards are excluded, never set to zero. Its method checks include an additive sign-flip example, an edge-perturbation example, replicate deduplication and missingness.

The optional fixed-total-context reproduction uses a 29.9 MB JSONL at Hugging Face revision `332cd047e9093a948606c4251bf5b294b0664762`:

```bash
python3 -B research/task-conditioned-utility-study/fetch_fixed_context.py --out /tmp/ams-fixed-context-cells.jsonl
python3 /tmp/conditional-memory-upstream/scripts/x2_analyze_fixed_context.py /tmp/ams-fixed-context-cells.jsonl --out /tmp/ams-fixed-context-result.json
```

The fetcher verifies SHA-256 `d7a7309044ffb02aed7ddb786359939c51de12bf910a5825f3a6933ef651b033`. These commands analyse existing outcomes; none requests new inference. The large input and original benchmark text are not included. The pinned source repository has no root licence file, so this package ships original AMS analysis code, numerical derivatives, locators and hashes without copying upstream code or records.

## Saved evidence and uncertainty

| File | Evidence and boundary |
| --- | --- |
| `results.json` | Independently computed from three pinned public slices; includes runtime, seed, missingness, 60 per-memory contrasts, input and analysis-source hashes |
| `official-headline-output.txt` | Successful official headline execution; its local input-path prefix is normalised to `<UPSTREAM>`, with numerical output unchanged |
| `official-fixed-context-output.txt` / `official_fixed_context.json` | Successful execution of the authors' fixed-context script; these point estimates and confidence intervals use the authors' analysis code |
| `receipt.json` | Exact upstream/input identities, public command templates and artifact SHA-256 bindings; also records the historic writer provenance limit |
| `figure-data.json` / `utility-opportunities.svg` / `utility-opportunities.png` | Compact plotted numbers and rendered figure; the right panel is explicitly hypothetical |
| `research-note.md` | Complete technical interpretation, independent derivations, counterexample and limits |
| `source-notes.md` | Primary source versions, actual reading scope and source locators |

The author-script intervals in `official_fixed_context.json` were recomputed by executing that script, not independently reimplemented. The headline, reader-transfer and conditional-harm intervals in `results.json` were independently computed by AMS. The offline gate checks both saved sets for identity and valid bounds; it does not regenerate either set of intervals.

To regenerate only plot data and rendered figures from compact summaries, with matplotlib 3.10.8 and NumPy installed:

```bash
python3 -B research/task-conditioned-utility-study/figure_data.py
python3 -B research/task-conditioned-utility-study/plot_results.py
```

An SVG can acquire new renderer metadata when regenerated. The committed receipt binds the saved rendering; after a deliberate artifact update, review the output and update the receipt instead of claiming the old hash still applies.

## Main numerical checks

The primary archive contains 2,599 replicate rows, 1,157 unique cells, 60 memories and 35 source episodes. Replicates within each cell have identical paired binary outcomes. The memory-weighted bearing-minus-control contrast is **+0.3348611111**. The official memory and episode percentile intervals reproduce as `[+0.209,+0.463]` and `[+0.196,+0.475]`. AMS's independent seed 20261113 gives `[+0.2080,+0.4639]` and `[+0.1998,+0.4765]`; small differences are expected bootstrap variation.

| Design stratum | Cells | Wrong → correct | Correct → wrong | Help opportunities | Harm opportunities | Mean paired change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Answer-bearing | 139 | 50 | 2 | 123 | 16 | +0.345324 |
| Matched control | 146 | 10 | 6 | 125 | 21 | +0.027397 |
| Random task | 872 | 82 | 26 | 693 | 179 | +0.064220 |

These are frequencies in a constructed measurement design, not deployment frequencies. Dividing the two bearing harms by all 139 cells obscures that only 16 cells offered an opportunity to turn a correct answer into a wrong one. The bearing-minus-control headline is memory-weighted; subtracting the two cell-weighted means in this table gives a different estimand.

The fixed-context input contains 277 cells. The official exclusion rule marks 63 exposed pairs affected by a disclosed cache-key defect and leaves 77 of 135 bearing cells. On these 77, Raw gains +0.35065, Summary +0.03896 and Structured +0.01299. Summary-minus-Raw is −0.31169, task-clustered interval `[−0.441,−0.187]`. This reproduces the authors' conditional comparison. It does not establish that raw storage beats every compression scheme or the best alternative use of freed context.

The graph check finds two connected components, rank 276 and an 881-dimensional space of cycle restrictions. Of 70,638 overlapping four-cycles, 20,016 have nonzero alternating sums. This refutes exact additivity of these archived edge values while leaving the semantic cause unidentified. It is not a prevalence estimate or 70,638 independent experiments.

## Information boundary and limits

At the pinned source commit, writer calls render only `segment.text`; writer signature checks passed. Fixed-context rows carry prompt-version identifiers matching that source's normalised prompt hashes. However, all 2,216 rows record their original inference `code_sha` as `unknown`. The source audit supports the published information boundary; it cannot authenticate which code every original inference used. Details and hashes are in the receipt and technical note.

Any future live study must retain a query-blind writer, answer-blind deployment selection, matched placement, separate tool-error and missingness reporting, and an irrelevant-content placebo. These remain an unexecuted candidate protocol, not results of this package.
