# Memory value under reader side information

**Status:** executed exact finite enumeration: fixed-exposure witnesses on 2026-11-05, selection-channel continuation on 2026-11-07. Authored theory controls; no model/provider execution, retrieval engine, human observation, training or benchmark promotion. Author: Cove (AI-assisted research). The article is canonical at [study/entries/memory-value-side-information.md](../../study/entries/memory-value-side-information.md).

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

## Follow-up protocol, not executed

The [full proposed protocol](protocol.md) fixes a small fictional routing task, complete rendering rules for the eight enumerated worlds, a valid-key versus irrelevant-key comparison crossed with X/Y, label controls, the weighted accuracy interaction estimand, calibration handling, and failure conditions. It keeps forced binary choice separate from any later abstention study. The selection continuation adds explicit exposure assignment and future selector/message controls; it does not execute the language study. A stimulus renderer and semantic review must precede subject execution. The actual provider/model, permitted cost/call budget, repetition count and stopping criterion remain to be fixed for that separate execution. This result does not activate such a study.

## Integration

Both `--check` commands and the selection tests are part of `tools/verify_reader.py`. The entry joins the existing relevance, representation, learning and evaluation routes; the programme, experience article, representation article and two existing inquiries carry the fixed-exposure conditions. The selection continuation updates this article, the relevance direction and the evidence-complementarity protocol's interpretation of correct answers without annotated support. Past receipts remain unchanged. After editing canonical text, regenerate `data/materials.json` and `assets/materials-data.js` through `tools/build.py --write-json`; do not hand-edit the projections. These external readings do not add bibliographic sources or require a new RDF import.
