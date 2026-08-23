# StateFuse interpretation-contract audit: frozen preregistration

Status before execution: `revised_preregistered_not_run`.

This protocol was frozen before H1/H2 execution after source inspection and an
external adversarial pre-test review. It targets StateFuse `0.3.0` at commit
`79a6229f83a7b174a2a9ac8fd0ace267ae30e79b`. The paper object is separately
locked as `arXiv:2607.05844v1`; `paper/main.tex` at the source commit is an
unpublished repository manuscript, not the arXiv object or a verified
publication.

## Evidence vocabulary

- arXiv statements: `paper-reported`;
- pinned implementation and repository manuscript: `official-source`, with the
  manuscript additionally tagged `unpublished_repository_manuscript`;
- the environment-specific upstream pytest result: `official-source execution
  receipt`, never `released-input audit`;
- H1/H2 results, if valid: `synthetic contract test`;
- representation recommendations: `editorial inference`.

## H1 — interpretation-contract binding

Question: given byte-identical operations, fixed query constraints, and a fixed
resolver, which materialized and projected fields can diverge solely because
two executions use different deterministic interpretation contracts?

Every final OpSet first passes an identical-contract exhaustive-permutation
gate. Two-op sets have 2 permutations, three-op sets have 6, and the five-op
detector set has 120. Any state or projection digest difference within one
fixed-contract group invalidates that fixture before cross-contract
interpretation.

### H1-EQ

Two same-key claims have equal score inputs and values `"Open"` and `"open"`.
Both contracts leave `normalize_for_claim_ref=False`. E0 uses raw equality; E1
uses deterministic strip-and-casefold equality. Expected: identical active IDs;
E0 creates a direct conflict and the fixed conservative resolver abstains on
the exact score tie; E1 creates no conflict and selects deterministically.

### H1-REF

Two same-key claims have values `" Open "` and `"open"`, followed by a
semantic-ref retraction whose frozen literal target is the normalized `"open"`
handle. Both contracts use the same strip-and-casefold equality. R0 leaves ref
values raw; R1 normalizes values for refs. Expected: no conflict in either
condition; R0 suppresses only the literal-matching claim, while R1 maps both
claims to the target ref and suppresses both.

### H1-DET and H1-VID

The five operations are one capacity claim, three cost claims A/B/C sharing a
multi-valued cost key, and one committed resolution over detector-v1's original
capacity+A/B candidate set. D1 considers A/B and reports `budget/v1`. D2
considers A/B/C but deliberately reuses `budget/v1`. Expected: one stable
conflict locus, changed candidate membership and snapshot ID, an effective D1
resolution, and a stale/reopened D2 resolution with an unresolved projection.

The declared-version control uses D2 behavior but reports `budget/v2`.
Expected: the changed behavior occupies a visibly different conflict locus and
remains unresolved/open rather than masquerading as the old detector contract.

Same-ID D2 is an audit-induced deployment error. It does not estimate how often
ordinary deployments drift.

## H2 — semantic-reference recurrence scope

Neutral mechanism name: `semantic-ref tombstone carryover`.

The fixed key is `("synthetic", "shop", "state")`. Monday M and Tuesday T both
say `"open"` but have disjoint half-open validity intervals, different IDs,
timestamps, evidence IDs, provenance, and confidence. Neither supplies a custom
claim ref. The registry has no normalization. The primary query is Tuesday noon;
the diagnostic query uses `valid_at=None`.

Cases:

- `H2-NONE`: no retraction; Tuesday remains active;
- `H2-ID`: exact-ID retraction of M; Tuesday remains active;
- `H2-REF`: semantic-ref retraction of M's handle; M and T share that handle and
  both become inactive;
- `H2-CTX`: T carries occurrence context and the query supplies it; T has a
  different ref and remains active;
- `H2-VALUE`: T says `"open-again"`; T has a different ref and remains active.

`H2-NONE` has two operations and 2 permutations. The four retraction cases have
three operations and 6 permutations each. The permutation check is an integrity
gate, not the H2 contribution.

H2 asks what follows when an occurrence-local correction is expressed through
the documented broad semantic handle while validity remains outside identity.
It does not preregister a bug, data-loss, poisoning, or permanence claim.

## Frozen observables and controls

The runner records exact operation JSON and OpSet hashes, contract descriptors
and hashes, effective refs, inactive/inapplicable IDs, active IDs by key,
complete conflicts and witnesses, lifecycle/effective-resolution state,
selected claims, unresolved/surfaced findings, explanations, and per-permutation
state/projection digests.

Operation bytes, query time/context/scope, resolver parameters, locale,
timezone, serialization, and source identities are fixed. Contract functions
are newly authored, deterministic, side-effect-free, model-free, and execute
under a socket network guard.

## Falsifiers and stop conditions

Stop or narrow the affected stratum if same-contract permutations differ, a
predeclared equality/ref/detector consequence is absent, the source enforces a
shared contract digest, operation bytes differ inside a treatment pair, or an
unregistered input changes. Do not replace a null fixture after seeing results.

No `worked` artifact is permitted if exact source objects cannot be locked,
upstream code/tests/PDF must be redistributed, raw state/projection outputs are
lost, source or query inputs are unlocked, contract functions use external or
private state, or a clean reader-supplied-checkout reproduction fails.

## Claim ceiling

A matching H1 may show that byte-identical immutable operations do not alone
determine one semantic view across different deterministic predicate/detector
contracts. That instantiates the workshop manuscript's same-contract deployment
precondition; it is not an OpSet/CRDT merge-law failure.

A matching H2 may show the disjoint-validity consequence of the documented
broad semantic handle and contrast it with exact-ID and identity-changing
controls. It is not proof of a defect or incorrect domain model.

Neither probe reproduces StateFuse paper experiments, evaluates a model or
benchmark, estimates memory accuracy/safety/reliability, demonstrates a
security vulnerability, or supports production-frequency or harm claims.

Licensing of newly authored AMS code and documentation remains
`pending_owner_choice`; this protocol does not create or imply a license grant.
