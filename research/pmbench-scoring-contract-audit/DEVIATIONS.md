# Deviations from the pre-publication candidate package

The supplied candidate ZIP was used as a hypothesis package, not as authority.
Its SHA-256 and internal manifest passed, and every original assertion was
reproduced against the exact official checkout. Publication nevertheless uses
the independently reviewed runner in this directory and newly generated raw
outputs.

## Independent source interpretation came first

Before opening the candidate result files, the locked official scorer was read
and three predictions were frozen: monitoring/channel buckets were not query-
conditioned; updated off-due selection could be both accepted late and counted
as a violation; and action rows were consumed positionally without `step_id`
realignment. Candidate inspection and execution happened only afterward.

## The bounded runner did not write the named result file

The candidate README said `bounded_reference_probe.py` wrote
`RESULTS.bounded-reference.json`. The script printed JSON to stdout; the package
contained a separately captured result file. This did not change an assertion,
but the public artifact does not repeat the claim.

## Synthetic fixtures are scorer-level, not whole-scenario fixtures

The candidate exact-checkout harness used minimal dictionaries sufficient for
direct `score_day` / `score_log` execution. It did not establish that those
objects satisfy every full-scenario validator invariant. The public method says
this explicitly and uses the unmodified released scenario as the separately
validated end-to-end fixture.

## Released-corpus analysis was added

The candidate probes demonstrated possibility. They did not establish released
prevalence or impact. The public runner adds all 64 primary logs, exact 8 x 8
inventory, live/replay distinction, per-step identity validation, independent
identity alignment, full query-window reconstruction, revision-locked violation
tracing, official report rebuild, and paper Table 2 assertions.

## Raw and derived outputs were separated

The initial independent audit held detailed rows and decisions in one large JSON
object. Publication separates 64 run summaries, 1,062 hidden-channel findings,
541 update-violation findings, exact source hashes, probe output, environment,
and aggregate interpretation. `RESULTS.txt` contains only the compact derived
decision.

## Claim strength was narrowed

- Claim A is a measurement-meaning boundary, not a paper-definition violation.
  The published category-conditioned hit cannot alone prove query provenance.
- Claim B is a real taxonomy mismatch between stale-version wording and the
  current mutable-state/off-due implementation. Released semantic intention is
  bounded, not guessed.
- Claim C is a real source-level integrity risk. Exact alignment changes zero of
  the 64 released scores, so no released headline impact is claimed.

## The abstract's 65.1% wording was separated from scorer defects

The 65.1% value is reproduced as the across-model optional-heartbeat macro in
Table 2. Table 3 gives GPT-5.4 optional heartbeat as 79.1%. The abstract's
appositive attribution is recorded as a statistical-object wording mismatch;
it is not used to suggest that the checked tables or released aggregates fail.
