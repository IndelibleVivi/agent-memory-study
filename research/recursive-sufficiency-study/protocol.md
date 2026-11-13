# Recursive sufficiency: analytic witness protocol

Version: 1 · 2026-11-13 · Cove · AI-assisted research

## Status and purpose

This is an executed collection of original finite mathematical constructions. It has no empirical samples, model calls, trained parameters, natural-language parsers, or upstream benchmark executions. The Chinese research argument and general proofs live in `study/entries/history-and-update-sufficiency.md`; this directory preserves its explicit numerical inputs and reproducible calculations.

The constructions were explored and run before this canonical package was assembled. The package re-executes those constructions with a published input contract and source receipt; it is not a prospective preregistration. The two-state hidden-coin calculation was added during canonical authoring. Source identity supports reproducibility, not independent priority, timestamp certification, or empirical validity.

## Input and interpretation contract

`inputs.json` is the complete numerical input. All probabilities are rational strings. `study.py` uses Python standard-library `Fraction` for probability products, posteriors, Bayes risks, state comparisons, and recovery errors. Decimal probabilities are display projections; entropy values are floating-point calculations rounded to 12 decimal places.

1. **A current action cannot encode every future update.** There are two equally likely history labels. Their hidden-bit posteriors are 1/10 and 1/5. A positive observation occurs with probability 4/5 given hidden bit 1 and 1/10 given hidden bit 0. The task is to guess the hidden bit under symmetric 0–1 loss, choosing 0 on ties. Enumerate the eight joint cells of history, hidden bit, and observation sign. Compute the best risk with the full history label and sign, and the best risk with only the old optimal action and sign. Expected exact results: positive posteriors 8/17 and 2/3; risks 11/100 and 23/200; gap 1/200.

2. **A growing exact learner state for a fixed task.** Use a Beta(1,1) prior over a stationary Bernoulli probability. At each listed horizon T, enumerate success counts 0 through T and distinct exact predictive means. The target is the full-history Bayes decision for the next bit under the same symmetric loss and tie rule, not certain knowledge of the next bit. For each pair of counts at the same T, search for a shared suffix of only successes or only failures, length at most T+1, that separates the required decisions. Record every pair at T=8. The article proves the statement for arbitrary T; these finite enumerations are checks of examples, not a finite proof of the unbounded claim.

3. **Prediction can require more distinction than one decision.** Compare Beta(1,1) with Beta(2,2). For the initial histories, each is produced by one batch event from the common prior: an empty batch or a batch containing one success and one failure. Batch sample count is absent from mean-only memory. Calculate next-success, two-success, and success-after-success probabilities, plus the decisions after a success with threshold 63/100. Their identical count difference implies action equivalence under every common Bernoulli continuation for the fixed threshold 1/2; the article supplies that algebraic argument. No finite enumeration is presented as proving all continuations.

4. **Finite hidden state does not bound exact belief precision.** A known model selects a static hidden coin with parameter 1/4 or 3/4 under equal prior. All observation probabilities are known. Record posterior odds and next-bit predictions at the listed success-minus-failure counts. Independently multiply the specified emission likelihoods and check every pair and selected suffix from construction 2 in this model, preserving its T=8 probabilities. The article proves that equal count differences remain decision-equivalent under every suffix and unequal differences admit a separating suffix. This is a noisy-observation model and does not refute a noiseless, completely specified finite-state quotient. Mutual information between history and the binary hidden mode is at most one bit; it is a different quantity from exact belief-encoding capacity or the number of continuation-decision classes.

5. **Restoration is target- and channel-dependent.** Enumerate four independent fair bits, retain the first, and compare the full missing vector with its parity. The exact fixed-width information requirements are three and one bit. For each missing bit, independently flip each re-observation with probability 1/10. Enumerate every observation string for 1, 3, and 5 re-observations and compute the optimal bit error by summing the smaller joint mass. Sanity controls use zero noise and independent 1/2 noise. Multiply per-bit success probabilities only because channels and missing bits are independent. Repeated deterministic or correlated interpretation mistakes do not satisfy this model.

## Evidence and comparison contract

`results.json` is produced by a real local execution. It includes the complete finite collision joint distribution, selected continuation witnesses, exact fraction results, and SHA-256 identities of `study.py`, `inputs.json`, and this protocol. `--check` recomputes the scientific payload and source identities and compares them with the saved result. The recorded Python version is historical runtime metadata and is not required to match another interpreter's patch version.

The assertions check mathematical identities and degenerate channel controls. No count of these checks is an empirical sample size. A changed input, source, protocol, missing field, extra field, or result changes the checked payload. Fresh output uses exclusive creation and cannot overwrite an existing receipt.

## Boundaries

The Bernoulli model is stationary and has either a continuously unknown parameter or a noisy finite hidden mode; it has no user preference changes, semantic ambiguity, retrieval, natural-language evidence, or learned event schema. Every finite observation suffix has positive probability. Exact worst-case continuation preservation can be stricter than small expected regret. A finite horizon, approximate answers, restricted continuation family, different loss, or additional side information changes the capacity requirement. Information bits are not tokens, latency, energy, or monetary cost.
