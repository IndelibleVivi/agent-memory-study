# v1 combination-transfer diagnostic

Agent Memory Study editors · 2026-11-13 additions: Cove, AI-assisted research.

**Protocol status:** frozen before the first fit or test evaluation in this
follow-up. The earlier support audit already enumerated and observed all 1,024
Boolean outcomes. This is therefore a pre-specified follow-up diagnostic, not
an independent blind or held-out confirmation, and not a preregistration.

## Question and bound

Can the original v1 learner transfer the decision-rule conditions to full
feature vectors whose `sensitive` bit is one, when all training rows come from
the original split with `sensitive=0`?

The v1 rule has one useful semantic core: the first three relation bits are one,
the prerequisite and tool bits are one, the candidate is not already known, and
it is neither expired nor a side-effect candidate. The `verified` and
`sensitive` bits are v1 nuisances. Consequently, the test can vary only those
two bits around the one observed useful core. It can test unseen full-vector
positive transfer, but cannot test transfer to a new useful semantic core.

The uniform enumeration below describes this finite Boolean domain only. Class
proportions are not deployment rates.

## Frozen split

- Read the unchanged original inputs: `fixture_build.py`, `study.py`,
  `fixtures.json`, `results.json`, and the support-audit implementation and
  receipt.
- Construct every 10-bit vector once, in lexicographic order, through
  `support_audit.construct`. Check that the result round-trips through the
  original `study.vector`.
- Test every one of the 512 vectors with `sensitive=1`. No test vector is used
  for fitting, tree induction, arm selection, or protocol revision.
- Use only original `train` rows with `sensitive=0` as the filtered original
  training collection. Validation and test rows are never training data.
- Require exact train/test vector disjointness. Require both useful test
  vectors, and require Hamming-distance-one expired, missing-prerequisite, and
  side-effect neighbors of each.
- Validation is descriptive only. Rows with `sensitive=0` may be reported; rows
  with `sensitive=1` may not become training or selection input. No validation
  result chooses a threshold, feature set, arm, or other hyperparameter.

## Three supervision arms

All arms retain every feature and use the original implementations imported
from `study.py`. No new learning algorithm or scoring rule is introduced.

1. `filtered-original`: only the filtered original training rows.
2. `balanced-repeats`: the filtered rows plus 32 copies of original training
   labels, eight from each of the four classes. For each class, sort the unique
   filtered-training vectors lexicographically and cycle through them to choose
   eight rows. The source row is the lexicographically first original row with
   that vector. This is an equal-count supervision control, not independent
   evidence.
3. `balanced-counterexamples`: the filtered rows plus 32 additional
   `sensitive=0` oracle-labelled rows, eight from each class. For each class,
   sort candidate vectors by `(is_already_in_filtered_support, vector)`, so
   vectors absent from filtered support have priority. Select at most the first
   eight unique vectors; when the class has fewer than eight unique candidates,
   cycle through all its unique candidates in that order. Report unique counts.
   Candidate selection never uses model predictions, errors, or test feedback.

Both additions contain exactly 32 rows with class histogram
`useful=8, redundant=8, irrelevant=8, harmful=8`, and no added vector has
`sensitive=1`.

## Fixed learners and baselines

For each arm, fit the original scorer exactly once from zero initialization with
400 full-batch steps, rate 0.5, L2 0.01, and all ten features. Induce the
original decision tree exactly once per arm with its fixed depth-4 and feature
order rules. Run the original deterministic Hamming nearest-case implementation
once per arm. Do not tune any result on validation or test.

Also report:

- `oracle-v1`: the unchanged public v1 rule;
- `constant-reject`: class `irrelevant` for every row.

Class prediction and binary action (`predicted useful` versus not useful) are
reported separately. Useful recall uses the two positive test vectors as its
denominator. False injection is split into harmful and other
(`redundant`/`irrelevant`) classes with their own denominators. The optional
utility is the frozen unit cost: correctly selected useful `+1`, any false
injection `-1`, and missed/rejected `0`. It is a synthetic diagnostic, not a
real-world utility estimate.

## Tie analysis

For nearest case, compute every minimum-Hamming-distance training-row class for
each test vector. Report a **per-case independent tie envelope**: best and worst
sums obtained by independently choosing an offered class per case. This is not
claimed to be jointly attainable by one global row ordering.

Also report attained results for two named, coherent global training orders:
scope-first (`irrelevant` before `harmful` as the suppression priority) and
hazard-first (`harmful` before `irrelevant`). Keep all remaining priorities
fixed and stable. Call these two finite order controls, not global extrema and
not a permutation search.

## Invariance, conflicts, and v2 boundary

- Check complete within-test verified flips: for all 256 pairs that differ only
  in `verified`, report class and action changes under every method. The v1
  oracle must change neither.
- The test cannot measure a sensitive-bit pair because every test vector has
  `sensitive=1`. State this identifiability limit.
- Report scope-plus-hazard conflicts, where scope-first v1 labels the case
  `irrelevant` but hazard-first priority labels it `harmful`, with class labels
  and binary actions kept separate.
- Re-score the unchanged methods against v2 labels as a frozen policy-mismatch
  diagnostic. Report changed, preserved, and boundary scopes, with boundary a
  proper subset of preserved. This is not corrected-learning success.
- Because no sensitive training row is available, this split cannot identify
  v2's unverified-and-sensitive correction. Do not extend v1 invariance to v2.
  Identifying the new rule requires an independently designed split with
  correction supervision, not a transfer success claim.

## Saved evidence and checks

Save the protocol and source hashes; every test vector and v1/v2 label; arm
membership, support, and unique-vector counts; fitted initial/final weights and
induced trees; per-arm predictions; all metrics; tie envelopes and named finite
orders; complete verified flips; conflict subsets; validation-sensitive-zero
rows and predictions; and all test cases.

`--check` recomputes the complete deterministic receipt and rejects changed
source hashes, split membership, arm construction, fitted state, predictions,
metrics, tie report, or saved output. Behavior tests reject train/test overlap,
absent useful test vectors, unequal or wrongly balanced additions, false v2
nuisance-invariance claims, invalid tie envelopes, and source/receipt drift.
