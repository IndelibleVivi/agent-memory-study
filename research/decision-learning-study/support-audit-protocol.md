# Structured policy support audit

Agent Memory Study editors · 2026-11-13 additions: Cove, AI-assisted research.

Exploratory audit designed after reading the existing study and its saved results,
before running this extension. It is not a preregistered statistical experiment.

## Question

What does the existing classifier's perfect test score identify about its rule
outside the feature combinations used in training? Does label disagreement imply
different memory selection behavior in this study?

## Frozen surfaces

Baseline repository: `IndelibleVivi/agent-memory-study`,
`196880924ae501dd8103bdcb4c03e5c27c7df8ed`.

Use unchanged `research/decision-learning-study/{fixture_build.py,study.py,
fixtures.json,results.json}`. First replay the original `--check` and unittest.
Do not alter the training distribution, saved weights, optimizer, thresholds,
label rule, or original receipts to make a branch win.

## Probe

Construct one context/candidate pair for each of the 1,024 Boolean vectors of
the existing ten features. Each pair must round-trip through the original
`vector()` function. Labels are produced by the unchanged public oracle and
also checked against an independent vector-level description of the rule.

Replay the saved classifier weights and induced tree, and the original nearest
case implementation. Report multiclass predictions and the narrower action
`selected = predicted useful` separately. Partition observations into seen and
unseen training feature vectors and rule regions. The uniform enumeration is a
finite diagnostic domain; its class proportions are not a deployment measure.

Compare the published v1 label rule (scope before hazard) with a rule that
checks hazards before scope. Check where they agree on all original splits and
where they disagree on the enumerated domain. Both labels `irrelevant` and
`harmful` suppress selection in the existing study; this precedence probe cannot
establish a difference in that binary action by itself.

## Evidence and scope

Save source hashes, exact counts, predictions for every constructed vector,
small interpretable witnesses, and deterministic verification checks. No
significance test: this is an exhaustive finite-domain mechanism probe, not a
random sample. There is no language model call, natural-language inference,
real memory system, downstream reward, or human judgment. A result here says
what the particular representation and frozen decision functions do.

## Reopening observation

If all useful states of the enumerated domain are already in training support,
the extension has no unseen positive state on which to test useful-action
generalization. Record that explicitly rather than labeling rejection of unseen
negatives as broad policy transfer.

## Exploratory amendment after first enumeration

The first enumeration exposed harmful selections concentrated on combinations
with `verified=true`. The v1 oracle ignores verification and sensitivity. The
following analyses were added after seeing that observation; they are explicitly
post-observation mechanism probes, not preregistered confirmations:

1. Pair each vector with its verification-bit flip, and separately its
   sensitivity-bit flip. Count prediction and selection changes while checking
   that the v1 oracle label is invariant.
2. Retrain the same scorer once, with the original 400 steps/rate/regularization
   and original rows, using only v1's eight task-relevant features. Compute a
   nearest-case control on the same eight-feature distance. Do not tune either
   implementation after observing the results.

These controls receive designer knowledge of v1's rule. They do not establish
that an agent can discover which feature will matter in the future: verification
does matter in v2. Report class and selection behavior separately.

The nuisance-free nearest case attained complete class agreement in the first
control run. A further explanatory probe reverses the training-case order while
preserving its entire multiset and the eight-feature distance. This tests whether
scope-versus-hazard priority was supplied by the deterministic tie breaker. It is
also post-observation analysis, with no refitting or parameter search.
