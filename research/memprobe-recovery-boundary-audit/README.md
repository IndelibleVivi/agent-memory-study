# MEMPROBE fixed released-artifact recovery-boundary audit

This checked artifact accompanies an Agent Memory Study close read of
*MEMPROBE: Probing Long-Term Agent Memory via Hidden User-State Recovery*
([`arXiv:2606.24595v1`](https://arxiv.org/abs/2606.24595v1)) and the official
[`sora1998/MemProbe`](https://github.com/sora1998/MemProbe) source at exact
revision `19bb83644b082489b4e181e59f1cded1a00d0529`.

Its scope is deliberately narrow: an offline, standard-library checker reads
the fixed JSON release, verifies exact cross-artifact identities, recomputes
arithmetic over stored historical quarter-step judge scores, checks stored
retrieve-packet items against designated released final dumps under four
frozen system adapters, checks the deterministic reduction of stored
attribution stages to stored labels, and inventories missing replay material.

The package has no unscoped PASS. [`raw/decision.json`](./raw/decision.json)
records the single-run fixed-artifact gates. [`raw/comparison.json`](./raw/comparison.json)
binds two checked run envelopes whose 16-file primary manifests are byte-identical
and whose recorded hash seeds are distinct. The comparison receipt does not by
itself prove OS-process freshness or independent source-root creation; those are
properties of the documented formal execution procedure.
Only a successful source-bound invocation of [`verify_checked.py`](./verify_checked.py)
supports reader-side revalidation against an exact clean checkout and paper
PDF. Receipt-only verification establishes internal package integrity, not the
identity of external evidence.

## Reader-visible boundary

No simulator, assistant, memory writer, retriever, slot filler, judge,
attribution model, OpenAI endpoint, or Mem-T/vLLM service was run. Historical
retrieval was not reissued, and the benchmark was not freshly reproduced.

- The source field `ground_truth` is treated as a synthetic benchmark hidden
  target, not independently established real-world truth.
- Stored predictions, reasons, quarter-step scores, disclosure verdicts,
  attribution stages, and attribution labels remain historical LLM artifacts.
  No semantic re-judgment or human validation was performed.
- Exact packet membership does not prove that a packet or full dump was the
  exact historical slot-fill payload. It does not establish semantic
  relevance, sufficiency, or the absence of equivalent evidence elsewhere.
- A full-store/retrieve difference is a paired historical artifact delta, not
  an identified retrieval effect, retrieval loss, or retrieval failure.
- The audit does not causally separate writing, storage, serialization,
  retrieval, context construction, slot filling, judging, or attribution.
- Arithmetic is recomputation over fixed historical judge scores. It does not
  establish model quality, significance, ranking, run-to-run uncertainty,
  prevalence, real-user validity, privacy performance, deployment behavior,
  or generalization.
- Two-run byte identity establishes checker repeatability only. It is not
  correctness, portability, independent third-party replication, or
  historical execution replay.
- Current-source defaults do not fill absent historical model snapshots,
  requests, responses, prompt hashes, retry receipts, runtime receipts, or
  usage receipts.

## Evidence and receipt map

The frozen pre-execution contract is in [`PROTOCOL.md`](./PROTOCOL.md). The
checked package uses the following public-safe surfaces:

| Surface | Contents | Claim boundary |
| --- | --- | --- |
| `raw/input_manifest.json` | Every read input locator, byte size, and SHA-256 | Identity of registered bytes, not their semantic truth |
| `raw/target_registry.json` | Closed user/run/category/dimension/task-index registry | Identifier geometry only; no task or target text |
| `raw/target_joins.jsonl` | One row per run-bound benchmark target | Exact typed joins, fixed score, locators, and denied-value hashes |
| `raw/arithmetic.json` | Per-user exact category/overall values and across-user statistics | Recalculation of historical scores only |
| `raw/packet_rows.jsonl` | One row per stored retrieve packet | Packet cardinality and packet digest |
| `raw/packet_items.jsonl` | One row per stored packet item | Adapter status, match count, item ID/digest, and candidate store pointers |
| `raw/attribution_rows.jsonl` | One row per stored attribution | Stage-shape reduction and partial input observability |
| `raw/observability.json` | Typed missing/null/blank/string/score inventory | Stored-output presence and type, not semantic correctness |
| `raw/paired_deltas.jsonl` | Full/retrieve fixed-output deltas for matched targets | Historical artifact differences, explicitly noncausal |
| `raw/replay_inventory.json` | Named scripts, prompt fields, histories, native state, and provenance receipts | Replay-material status; no repaired substitute is presented as official |
| `raw/mutation_controls.json` | Isolated composite-fixture controls and pre/post evidence-object digests | Contract falsifiers and immutability checks |
| `raw/public_safety.json` | Public projection scan receipt | No copied upstream free text in the checked primary receipts |
| `raw/cases.json` | Three protocol-frozen public-safe illustrative strata | Explanatory cases, not an unbiased or representative sample |
| `raw/comparison.json` | Byte comparison of two primary receipt sets | Same-checker repeatability in the locked envelope |

Public rows contain only identifiers, source-relative locators, enumerated
states, counts, fixed numeric values, packet item IDs, and SHA-256 digests of
denied source values. They contain no hidden-bank values, task text, persona
profiles, transcripts, memory or retrieved content, predictions, reasons,
rationales, prompt text, or local paths. `raw/microfixture.json` is separately
declared AMS-authored synthetic material and is not a MEMPROBE record.

## Result vocabulary

The fixed edge vocabulary is machine-readable in the receipts:

- target joins: `VERIFIED_JOIN` / `FAILED_JOIN` at the summary boundary;
- packet items: `EXACT_MEMBER`, `AMBIGUOUS_MEMBER`, or `NO_MATCH`;
- attribution reduction: `REDUCTION_CONSISTENT` or
  `REDUCTION_INCONSISTENT`;
- attribution episode binding: at most `PARTIALLY_BOUND` when an episode
  exists but no exact released prompt/input hash binds the stored stage;
- replay material: `COMPLETE`, `PARTIAL`, or `BLOCKED`;
- historical execution replay: `NOT_ATTEMPTED`.

The unqualified word `lineage` is permitted only when the complete packet
population has exactly one designated-store match per non-empty item and the
separate `packet_unique_binding` gate is `PASS`.

## Reproduce

Acquire the official source and paper outside this artifact. Check out the
exact commit in two independent clean roots, then run the same checked runner
in two fresh processes and output directories:

```bash
TZ=UTC LC_ALL=C PYTHONHASHSEED=313 PYTHONDONTWRITEBYTECODE=1 \
  python3 audit.py run \
  --source /path/to/MemProbe-source-a \
  --paper-pdf /path/to/memprobe-arxiv-2606.24595v1.pdf \
  --output /fresh/path/run-a

TZ=UTC LC_ALL=C PYTHONHASHSEED=727 PYTHONDONTWRITEBYTECODE=1 \
  python3 audit.py run \
  --source /path/to/MemProbe-source-b \
  --paper-pdf /path/to/memprobe-arxiv-2606.24595v1.pdf \
  --output /fresh/path/run-b

python3 audit.py compare \
  --run-a /fresh/path/run-a \
  --run-b /fresh/path/run-b \
  --output /fresh/path/comparison.json
```

The two primary sets must be byte-identical. Environment receipts are
deliberately outside that comparison because they retain the distinct explicit
hash seeds. Package installation is a separate local packaging step:

```bash
python3 audit.py install \
  --run-a /fresh/path/run-a \
  --run-b /fresh/path/run-b \
  --comparison /fresh/path/comparison.json \
  --artifact-root /path/to/memprobe-recovery-boundary-audit
```

Verify an installed package without reopening external evidence:

```bash
python3 verify_checked.py --mode receipt-only
```

Revalidate every registered input and freshly recompute the primary receipts
with the same checked runner:

```bash
python3 verify_checked.py \
  --mode source-bound \
  --source /path/to/clean/MemProbe \
  --paper-pdf /path/to/memprobe-arxiv-2606.24595v1.pdf
```

The source-bound mode requires exact commit
`19bb83644b082489b4e181e59f1cded1a00d0529`, an entirely clean checkout, and
paper SHA-256
`e5b3699c00a0731cc00e165f12efb755c57886058e311c01e5643df6e56897b5`.
It creates only a temporary out-of-tree output and rejects an output beneath
the official checkout.

## Rights

See [`NOTICE.md`](./NOTICE.md). The official top-level MEMPROBE code and
generated benchmark artifacts are identified upstream as CC BY 4.0. Vendored
systems, taxonomies, model weights, and services retain separate terms. This
artifact copies no upstream free text and grants no new rights in upstream
material. AMS-authored code and prose currently receive no new public license
grant.
