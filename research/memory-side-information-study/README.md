# Memory value under reader side information

**Status:** executed exact finite enumeration, 2026-11-05. Authored theory controls; no model/provider execution, retrieval engine, human observation, training or benchmark promotion. Author: Cove (AI-assisted research). The article is canonical at [study/entries/memory-value-side-information.md](../../study/entries/memory-value-side-information.md).

## What was actually computed

`study.py` builds four fully enumerated probability distributions: an eight-row XOR/key channel, its sixteen-row independent-noise control, sixteen rows for three conditionally independent noisy reports, and a sixteen-row duplicate-report control. Repeated rows in the duplicate control marginalize unobserved error variables; they are not independent samples. The script partitions worlds by actually exposed variables, then computes Bayes 0–1 accuracy and conditional entropy. World probabilities and accuracy are exact `Fraction` values. Entropy uses `math.log2` and is rounded to twelve decimals.

`results.json` contains complete authored inputs, outputs, equality checks and evidence limits. The three witnesses share one authored theoretical study. They are not three validations of a natural-language method. No gold is supplied to a tested selector because no selector is tested; the evaluator calculates optimal decisions from the stipulated distribution.

`receipt.json` records the actual recomputation command, UTC time, Python/platform, stdout, exit code and SHA256 of the script and result. This receipt witnesses local execution; it does not add an independent scientific replication.

```bash
python3 -B research/memory-side-information-study/study.py
python3 -B research/memory-side-information-study/study.py --check
```

The first writes the deterministic result; the second recomputes and compares its full JSON. Both execute independent analytic checks for 1/2, 3/4, 1 and 27/32, probability normalization, six equal marginal laws, a different joint law, ordering invariance and ideal-reader information monotonicity. Only the entropy column uses floating point; the saved precision may require reinspection on a platform with different transcendental rounding.

## Source record

- **Identity:** Benjamin Brooks, Alexander Frankel, Emir Kamenica, *Comparisons of Signals*, American Economic Review 114(9), 2981–3006, 2024; DOI [10.1257/aer.20230430](https://doi.org/10.1257/aer.20230430).
- **Read object:** [author manuscript](https://benjaminbrooks.net/downloads/bfk_comparisons.pdf), dated March 2024; accessed 2026-11-05. Identity, definitions in §2, comparisons in §3.1–3.2, Theorem 1 and its argument on pp. 8–9 were inspected. This is a specified-section reading, not a claim of reviewing all appendices.
- **Contribution retained:** comparisons of channels in isolation do not generally determine comparisons after correlated side information. The paper's strong comparison is distinct from ordinary Blackwell comparison.
- **Our contribution:** the concrete XOR/noise control, equal-marginal witness, action-accuracy plateau, exact implementation and implications for AMS label transport. These are explanatory applications of established ideas, not a new information-order theorem.
- **Blackwell 1953:** bibliographic lineage only. The original publisher page did not expose readable full text in this session. The general theorem is not claimed as independently close-read; the argument used here is fully visible in the constructed examples.

No external full-text PDF is redistributed. The article uses existing `externalReadings`, so this does not change the Zotero/RDF inventory.

## Result and interpretation

| Witness | Exact observation | What it rules out | What remains open |
| --- | --- | --- | --- |
| Rank reversal | X: 1/2 → 1 after adding C; Y: 3/4 → 3/4 | A single X/Y order is optimal in both fixed contexts | Prevalence, observability and cost in real histories |
| Matched marginals | All unary and pairwise laws on Θ/C/X match, while joint accuracy is 1 vs 1/2 | These marginals determine the needed joint relation | Which real representations preserve it |
| Accuracy plateau | Independent N2 adds conditional information but changes accuracy by zero | Zero accuracy uplift implies no extra information | Effects under other losses or subsequent tasks |

## Follow-up protocol, not executed

The [full proposed protocol](protocol.md) fixes a small fictional routing task, complete rendering rules for the eight enumerated worlds, a valid-key versus irrelevant-key comparison crossed with X/Y, label controls, the weighted accuracy interaction estimand, calibration handling, and failure conditions. It keeps forced binary choice separate from any later abstention study. A stimulus renderer and semantic review must precede subject execution. The actual provider/model, permitted cost/call budget, repetition count and stopping criterion remain to be fixed for that separate execution. This result does not activate such a study.

## Integration

The `--check` command is part of `tools/verify_reader.py`. The entry joins the existing relevance, representation, learning and evaluation routes; the programme, experience article, representation article and two existing inquiries carry the new conditions. Past receipts remain unchanged. After editing canonical text, regenerate `data/materials.json` and `assets/materials-data.js` through `tools/build.py --write-json`; do not hand-edit the projections. This external-reading article does not add a bibliographic source or require a new RDF import.
