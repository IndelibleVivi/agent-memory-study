# Memory value under reader side information

**Status:** executed exact finite enumeration: fixed-exposure witnesses on 2026-11-05, selection-channel continuation on 2026-11-07. A separately frozen natural-language reader experiment ran on 2026-11-07 (Asia/Singapore) using official OpenAI Responses API. No retrieval engine, human observation, training or benchmark promotion. Author: Cove (AI-assisted research). The article is canonical at [study/entries/memory-value-side-information.md](../../study/entries/memory-value-side-information.md).

## What was actually computed

`study.py` builds four fully enumerated probability distributions: an eight-row XOR/key channel, its sixteen-row independent-noise control, sixteen rows for three conditionally independent noisy reports, and a sixteen-row duplicate-report control. Repeated rows in the duplicate control marginalize unobserved error variables; they are not independent samples. The script partitions worlds by actually exposed variables, then computes Bayes 0–1 accuracy and conditional entropy. World probabilities and accuracy are exact `Fraction` values. Entropy uses `math.log2` and is rounded to twelve decimals.

`results.json` contains complete authored inputs, outputs, equality checks and evidence limits. These three fixed-exposure witnesses share one authored theoretical study. They are not three validations of a natural-language method. This original script has no selector; the evaluator calculates optimal decisions from the stipulated distribution. The later selection controls are separate below.

`receipt.json` records the original recomputation command, UTC time, Python/platform, stdout, exit code and SHA256 of `study.py` and `results.json`. It covers only that original execution and remains unchanged; it does not cover the selection continuation or add an independent scientific replication.

```bash
python3 -B research/memory-side-information-study/study.py
python3 -B research/memory-side-information-study/study.py --check
```

The first writes the deterministic result; the second recomputes and compares its full JSON. Both execute independent analytic checks for 1/2, 3/4, 1 and 27/32, probability normalization, six equal marginal laws, a different joint law, ordering invariance and ideal-reader information monotonicity. Only the entropy column uses floating point; the saved precision may require reinspection on a platform with different transcendental rounding.

## Selection as an information channel

`selection.py` adds three finite controls and reuses the original `study.py` evaluator. It does not modify the original distributions or saved result. `selection-results.json` preserves the authored worlds, exact weights, selector observations, candidate payloads and reader measurements. The policies are declared functions, not learned retrievers; the Bayes reader knows the actual joint law.

| Control | Active observation and selection | Payload-only accuracy | Identity + payload accuracy | Independent selection control |
| --- | --- | ---: | ---: | ---: |
| Identical constant records | Noisy report Z; J=Z | 1/2 | 3/4 | 1/2 |
| Identical coded records | Independent key C; J=C, payload X=Θ XOR C | 1/2 | 1 | 1/2 |
| Fixed distinct records | Noisy report Z; J=Z, payloads 0 and 1 | 3/4 | 3/4 | 1/2 |

In the second control, identity alone also has accuracy 1/2: zero marginal target information does not exclude one bit of information conditional on the payload. In the third, hiding identity preserves the selected-content channel. All three full-pool-only baselines have accuracy 1/2; the full pool plus the selector's actual extra observation achieves 3/4, 1 and 3/4. No selector reads gold. These are explanatory counterexamples, not estimates of how often deployed systems encode information this way.

```bash
python3 -B research/memory-side-information-study/selection.py
python3 -B research/memory-side-information-study/selection.py --check
python3 -B -m unittest discover -s research/memory-side-information-study -p 'test_*.py'
```

The write command produces only the new `selection-results.json`. The check recomputes it; tests check analytic fractions, observation boundaries, projection, independent controls, consistent relabeling and the complete-source information bound. Independent selector coins are exactly enumerated, not sampled. Repeated worlds are marginalized and do not increase an empirical sample size. The old `study.py`, `results.json` and `receipt.json` stay intact.

## Source record

- **Identity:** Benjamin Brooks, Alexander Frankel, Emir Kamenica, *Comparisons of Signals*, American Economic Review 114(9), 2981–3006, 2024; DOI [10.1257/aer.20230430](https://doi.org/10.1257/aer.20230430).
- **Read object:** [author manuscript](https://benjaminbrooks.net/downloads/bfk_comparisons.pdf), dated March 2024; accessed 2026-11-05. Identity, definitions in §2, comparisons in §3.1–3.2, Theorem 1 and its argument on pp. 8–9 were inspected. This is a specified-section reading, not a claim of reviewing all appendices.
- **Contribution retained:** comparisons of channels in isolation do not generally determine comparisons after correlated side information. The paper's strong comparison is distinct from ordinary Blackwell comparison.
- **Our contribution:** the concrete XOR/noise control, equal-marginal witness, action-accuracy plateau, exact implementation and implications for AMS label transport. These are explanatory applications of established ideas, not a new information-order theorem.
- **Blackwell 1953:** bibliographic lineage only. The original publisher page did not expose readable full text in this session. The general theorem is not claimed as independently close-read; the argument used here is fully visible in the constructed examples.
- **Selection continuation:** Neil Jethani, Mukund Sudarshan, Yindalon Aphinyanaphongs and Rajesh Ranganath, *Have We Learned to Explain?: How Interpretability Methods Can Learn to Encode Predictions in their Interpretations.*, AISTATS 2021, PMLR 130:1459–1467. [Official paper record](https://proceedings.mlr.press/v130/jethani21a.html), [proceedings PDF](https://proceedings.mlr.press/v130/jethani21a/jethani21a.pdf), accessed 2026-11-07. Read scope: §§2–4, particularly §3.1 selection encoding, §3.2 omitted control-flow features and §4 evaluation using independent masks. No appendix-proof review, upstream execution or empirical replication is claimed. The three AMS selection examples are independently authored applications; the prior work supplies the distinction between predictive communication and feature-based explanation.

No external full-text PDF is redistributed. The article uses existing `externalReadings`, so this does not change the Zotero/RDF inventory.

## Result and interpretation

| Witness | Exact observation | What it rules out | What remains open |
| --- | --- | --- | --- |
| Rank reversal | X: 1/2 → 1 after adding C; Y: 3/4 → 3/4 | A single X/Y order is optimal in both fixed contexts | Prevalence, observability and cost in real histories |
| Matched marginals | All unary and pairwise laws on Θ/C/X match, while joint accuracy is 1 vs 1/2 | These marginals determine the needed joint relation | Which real representations preserve it |
| Accuracy plateau | Independent N2 adds conditional information but changes accuracy by zero | Zero accuracy uplift implies no extra information | Effects under other losses or subsequent tasks |

## Executed natural-language reader experiment

The [frozen protocol](protocol.md) and [compact result](reader-results.json) cover a separate, explicitly authorized execution. `reader.py` owns authored input rendering and offline scoring; `reader_api.py` owns the bounded official API calls. The original finite results and receipt above remain unchanged.

**Observed:** GPT-6.1 Sol, low reasoning effort, standard tier; 68 distinct input messages × 3 predeclared calls = 204 valid responses, no retries, refusals, malformed outputs, timeouts or missing calls. The 64 core inputs cross X/Y, valid/irrelevant project keys, both visible record values, both mappings, both codebook row orders and both paragraph positions. Four no-key inputs are auxiliary diagnostics. The 272 weighted latent rows reuse responses for identical visible input; they are not 272 independent tasks. All input/output and scoring bindings were replayed locally from the retained raw run.

| Fixed record | Valid project P key | Independent project Q key | No key (auxiliary) |
| --- | ---: | ---: | ---: |
| Reliable coded X | 1.00 | 0.50 | 0.50 |
| Noisy direct Y | 0.75 | 0.75 | 0.75 |

The weighted interaction D is .50 in all three repeats and all four order combinations. These are scores under the authored finite distribution, not binomial estimates from 204 independent tasks. The .75 reflects the stipulated report error, not a count of independently sampled real-world failures.

Accuracy alone would miss blindly applying Q's mapping: that policy also gets .50 on X+Q and can produce D=.50. Here X+Q and X alone always report p_A=.50; flipping Q's mapping changes neither the reported probability nor choice. Flipping a valid P mapping with fixed X reverses the probability completely, as the compatible target also reverses. Y's probability remains .75/.25 according to the report. Brier is 0 for X+P, .25 for X+Q / X alone, and .1875 for Y; posterior MAE is zero in each cell. All 68 inputs have zero probability range across the three calls. This is agreement with the stipulated posterior in one short task, not evidence of general calibration or internal reasoning transparency.

The result supports **observable use of project-scoped complementary information in this task**. It does not justify a complex memory architecture: the reader already succeeds when the appropriate information is directly present. Actual no-record/side-information-only reader behavior was not measured; incremental values against .50 use a theoretical baseline. Long histories, inferred rather than explicit scope, selector behavior, another model and real task families remain outside this execution.

**Configuration and cost:** all 204 responses report `gpt-6.1-sol`, `service_tier=default`, `reasoning.effort=low`, `max_output_tokens=2048`, `store=false`; returned sampling defaults were `temperature=1.0`, `top_p=.98` (neither sent by the runner). The model name has no separately published date snapshot. Official input-token preflight matched all 32 P/Q pairs; all 204 usage counts matched preflight, 279–302 tokens per input. Formal calls used 61,062 input and 4,544 output tokens (492 reasoning, zero cached input). At the [observed official prices](https://developers.openai.com/api/docs/models/gpt-6.1-sol), the uncached estimate is **0.167564 USD**, or **0.167872 USD** including the separate 64-input/18-output-token format canary. This is a usage-based estimate, not an account invoice. The predeclared budget was 5 USD; the conservative generation cap was 4.356055 USD. The 68 token-count requests are non-generation preflight, not subject responses.

### Verification and a fresh authorized execution

Offline checks need only Python stdlib and never contact OpenAI:

```bash
python3 -B -m unittest discover -s research/memory-side-information-study -p 'test_*.py'
python3 -B research/memory-side-information-study/reader.py check-saved
```

The compact check validates saved-summary consistency and binding to the current stimuli/truth; it cannot reproduce provider outputs without the private raw run. Scorer controls include a correct reader, an always-A reader and a blind-Q reader that achieves the same main D but fails the scope diagnostics. It also checks missing responses, invalid probabilities, corrupted envelopes and actual-delivery mismatch.

A **new** run needs explicit operator authorization and current model/pricing verification. Supply `OPENAI_API_KEY` through the operator's approved environment; never put it in the repo. Choose a new directory outside the checkout:

```bash
RUN_DIR=/absolute/path/outside-repository/new-reader-run
python3 -B research/memory-side-information-study/reader.py prepare "$RUN_DIR"
# The following two commands contact official OpenAI and spend API credits.
python3 -B research/memory-side-information-study/reader_api.py preflight "$RUN_DIR"
python3 -B research/memory-side-information-study/reader_api.py run "$RUN_DIR"
# Offline: verify every delivered request/response binding and recompute scores.
python3 -B research/memory-side-information-study/reader_api.py replay "$RUN_DIR" --output "$RUN_DIR/analysis.json"
```

`preflight` sends one non-research format canary and 68 input-token count requests. `run` sends at most 204 measurements, four at a time; it stops after a batch brings HTTP/transport/incomplete failures to three or more. It never retries or resumes automatically. A request file without its response may already have been delivered: preserve it and investigate, do not resend blindly. Fresh execution/analysis destinations refuse overwriting. Raw requests, responses, account metadata and private execution traces stay outside Git; public files contain only authored methods/stimulus code and aggregate observations. `store=false` is a request setting, not a claim of zero provider retention.

## Integration

Both finite `--check` commands, all offline tests and `reader.py check-saved` are part of `tools/verify_reader.py`. The unified verifier does not run `reader_api.py preflight` or `run`. The entry joins the existing relevance, representation, learning and evaluation routes; the programme, experience article, representation article and two existing inquiries carry the fixed-exposure conditions. The selection continuation updates this article, the relevance direction and the evidence-complementarity protocol's interpretation of correct answers without annotated support. Past receipts remain unchanged. After editing canonical text, regenerate `data/materials.json` and `assets/materials-data.js` through `tools/build.py --write-json`; do not hand-edit the projections. These external readings do not add bibliographic sources or require a new RDF import.
