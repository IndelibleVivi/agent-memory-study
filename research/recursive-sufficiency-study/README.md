# Recursive sufficiency: executed analytic witnesses

Cove · AI-assisted research · 2026-11-13

This directory supports [历史怎样留下继续更新的能力](../../study/entries/history-and-update-sufficiency.md). It records exact mathematical constructions about retaining the ability to update a decision. **There are no empirical samples, model calls, or upstream replications.** General claims are proved in the article; finite enumerations check explicit instances.

## Reproduce

Python 3.10 or newer; standard library only. No network or credentials are used. From the repository root:

```bash
python3 -B research/recursive-sufficiency-study/study.py --check
python3 -B research/recursive-sufficiency-study/study.py --output /tmp/ams-recursive-sufficiency-results.json
python3 -B research/recursive-sufficiency-study/study.py --check --results /tmp/ams-recursive-sufficiency-results.json
```

Choose a new output path if that file already exists. Output creation is exclusive. `--check` recomputes results and identities; it does not trust the saved summary or execute archived code. Python patch-version metadata is retained but does not have to match the current interpreter.

Validation performed for this package: the saved receipt passed `--check`; a fresh execution reproduced it; altered scientific values and an altered input hash were rejected; a different historical Python version was allowed; and a second write to an existing output was rejected. These are artifact-integrity checks, not additional scientific observations.

## Files and executed results

| File | Role |
| --- | --- |
| [inputs.json](inputs.json) | All authored numerical inputs and enumerated horizons |
| [protocol.md](protocol.md) | Models, assumptions, expected identities, evidence boundaries |
| [study.py](study.py) | Single implementation of exact probability calculations and receipt checking |
| [results.json](results.json) | Executed results, joint cells, separating witnesses, and source/input/protocol hashes |

The canonical result was executed with Python 3.12.14. Its collision risks are **11/100** with the history identity and **23/200** with only the old action, an exact gap of **1/200**. At T=32, all 528 pairs among 33 success counts have a shared continuation that requires different actions, both in the Beta–Bernoulli learner and in the completely known two-state noisy model. The result retains all 36 pairs at T=8 and the latter model's exact likelihood-derived posteriors. These pair counts are mathematical coverage, not empirical sample sizes.

For the restoration construction, the full missing vector requires three exact bits while its parity requires one. A single independent binary-noise observation per bit leaves **1.406986780768** bits of conditional entropy. Optimal per-bit errors after 1, 3, and 5 independent reads are **1/10**, **7/250**, and **107/12500**. Those gains require the declared independent channel and do not apply to repeated identical parser mistakes.

## Scope

Current action equality is weaker than recursive action equivalence. Exact prediction can also retain more distinctions than a specified decision needs. In the two-state noisy model, information about the binary hidden type is at most one bit, while the exact continuation-decision quotient has infinitely many classes across all horizons. This does not imply infinite entropy at any fixed time or a requirement that practical systems use unlimited precision.

The conclusions depend on stationary kernels, positive-probability continuations, explicit loss, the tie rule, and exact matching to a declared Bayes policy. Finite horizons, approximation, restricted actions, additional side information, and changed tasks alter the requirements. The programme contains no language model, semantic event parser, personalized record, or learned memory policy. Source hashes bind content; they do not certify provenance or preregistration.
