# Agent Memory Study Agent Instructions

Agent Memory Study is a public research atlas and annotated reading room for
long-term agent Memory, belief revision, prospective Memory, and cognitive
architecture. Its credibility depends on one canonical public data source,
explicit evidence depth, accurate source attribution, reproducible public or
synthetic artifacts, and strict private/publication and licensing boundaries.

Read `README.md`, `CONTRIBUTING.md`, `NOTICE.md`, `THIRD_PARTY_NOTICES.md`, and
`ZOTERO-IMPORT.md` before changing content or build behavior. Global Faye/Cove
collaboration style and private continuity live outside this repository.

## Canonical Data And Generated Artifacts

- `data/materials.json` is the only canonical public materials/atlas source.
- `assets/materials-data.js` is generated. Never edit it by hand.
- `agent-memory-study.rdf` is generated from canonical public data plus the
  explicitly supplied local Zotero export according to the builder contract.
- Constellation coordinates, links, rings, brightness, filters, threads, and
  reading paths derive from canonical data; do not create a second hand-maintained
  layout/content truth.
- Material and failure-surface membership must remain bidirectionally consistent.
- Stable IDs, query URLs, and generated asset paths are public compatibility
  surfaces.
- A tagged Zotero ZIP is a release artifact and may lag `main`. Do not present it
  as current-main truth without checking the release.

Canonical build:

```bash
python3 tools/build.py --rdf-source /path/to/local-zotero-export.rdf
```

Optional release package:

```bash
python3 tools/build.py \
  --rdf-source /path/to/local-zotero-export.rdf \
  --package-output dist/agent-memory-study-zotero.zip
```

## Evidence And Note Depth

- Every material declares `noteDepth`, `readingScope`, `failureSurfaces`, and an
  editorial question.
- Meet the richer evidence schema before assigning `read` or `worked` depth.
- Keep source-backed paraphrase, paper-reported findings, evidence limits,
  editorial synthesis, and inference visibly distinct.
- Never fill absent fields with plausible claims or upgrade a skim/metadata entry
  from memory.
- Reading navigation notes do not replace the original source. Citation guidance
  must point readers back to the official work.
- Mark proposed but unexecuted protocols `proposed-not-run`.
- Executed public/synthetic tests must preserve authorship, method, environment,
  raw/derived result, controls, limitations, and reproducible artifact links.
- A boundary audit, static oracle, metadata check, or pre-registration audit must
  not be described as a benchmark/model/system reproduction when it does not run
  that experiment.
- Coordinates and visual prominence do not express quality, importance, or
  reading progress.

## Research Artifact Discipline

- Pin public source revisions and record exact required checkout state.
- Keep raw outputs when the project claims reproducibility, subject to public
  safety and license boundaries.
- Do not alter checked results after the fact to match an interpretation. Add a
  new version/run and preserve the earlier record.
- Separate source facts, normalized data, derived computation, editorial
  interpretation, and unresolved limitation.
- Deterministic or model-free audits must not imply model evaluation.
- Private experiments, local papers, personal annotations, and unpublished
  model transcripts stay outside the repository until deliberately sanitized
  and accepted as public contributions.

## PDF And Copyright Boundary

- `pdf.delivery = bundled` is allowed only for a file with explicit public
  redistribution permission, canonical source, and complete file-level
  attribution/notice.
- `pdf.delivery = official` links to the author, publisher, or institutional
  repository. Do not mirror the PDF.
- “Available online” does not establish redistribution permission.
- Keep the exact bundled-PDF allowlist and `THIRD_PARTY_NOTICES.md` synchronized.
- Bundled paper licenses apply to those files only. They do not license reader
  code, editorial notes, or unrelated repository content.
- Do not commit local OCR derivatives, library downloads, paywalled copies, or
  Zotero attachment paths without a separately verified right and publication
  decision.

## Zotero And Private/Public Boundary

- Local Zotero exports are build input, not public authority by themselves.
- Strip local-only notes, keys, tags, collection habits, filesystem paths, and
  attachment metadata not intended for publication.
- RDF relative attachments must remain usable through the documented full ZIP
  workflow.
- Do not tell readers to download RDF alone when its bundled attachments depend
  on repository-relative paths.
- GitHub `main` records selected public synchronization state. It must not reveal
  or imply Faye's private reading queue, unread count, progress, library contents,
  or experimental backlog.
- Browser UI has no transient annotation feature because unreviewed local-only
  browser state is not a research contribution.

## Reader And Analytics

- The reader remains static and GitHub Pages compatible; do not depend on an
  unmentioned backend or SPA rewrite.
- Preserve query URL behavior for material/thread/path/search/filter state and
  browser back/forward navigation.
- Desktop SVG and mobile matrix remain two projections of the same canonical
  data.
- Cloudflare Web Analytics stays aggregate-only under the approved boundary: no
  cookies/localStorage identity, custom per-material events, or query-string
  reading surveillance.
- Any new analytics or telemetry requires an explicit privacy/product decision
  and README/NOTICE update.
- Keep assets compatible with the GitHub Pages subpath.

## Tests And Validation

Run the public schema/boundary suite:

```bash
python3 -m unittest tools.test_build
```

Run the builder for data/content changes and inspect the generated diff. Run the
focused research artifact verifier documented in that artifact's own README for
changes under `research/`.

- Do not hand-fix generated output after a failed build.
- Keep builds deterministic where the current contract requires it.
- Verify public schema, private/public boundary, analytics boundary, subpath
  URLs, PDF allowlist, RDF attachments, and generated payload consistency.
- Use public/synthetic fixtures. Do not make CI depend on Faye's Zotero library,
  local paper paths, private data, or unredistributable source files.
- Report any unavailable pinned external checkout or source as `未验证`.

## Documentation And Bilingual/Public Voice

- `README.md` owns project identity, reader behavior, distribution, build, and
  public contribution entrypoints.
- `CONTRIBUTING.md` owns evidence, attribution, privacy, schema, and contribution
  requirements.
- `NOTICE.md`, `THIRD_PARTY_NOTICES.md`, and `ZOTERO-IMPORT.md` own their exact
  legal/distribution/import boundaries.
- Update this file when canonical data, generated artifacts, evidence depth,
  build, privacy, analytics, or licensing authority changes.
- Keep claims dense and specific. Do not convert editorial judgment into source
  fact or add inflated release/validation language.

Private continuity lives outside Git in the external private-continuity root
governed by the user-level working contract.

## Git And Release

- Inspect `git status --short`, stage explicit source and generated files, review
  the staged diff, and run `git diff --cached --check`.
- Do not commit private Zotero exports, local-only papers, reading progress,
  private notes, raw private model logs, or continuity.
- Keep source data and its generated payload/RDF in one coherent commit when the
  builder contract changes them together.
- Tag/upload a Zotero ZIP or other release artifact only after explicit release
  intent and current-main validation.
- Source commit, GitHub Pages deployment, tagged release, and downloadable Zotero
  package are separate facts.
