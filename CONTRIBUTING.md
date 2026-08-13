# Contributing

Contributions that improve source locators, bibliographic accuracy, accessibility, or the reader itself are welcome.

For a new material entry:

- link to the canonical or official source over a mirror;
- use `pdf.delivery: official` by default and link the official full text;
- add a PDF to `papers/` only when its public redistribution license has been checked, then record its exact author/title/source/license attribution in `THIRD_PARTY_NOTICES.md` and whitelist the exact filename;
- do not add OCR derivatives, screenshots of full texts, private exports, Zotero keys/tags, chat locators, or local filesystem paths;
- keep quotation distinct from paraphrase and attach a precise source locator to any quotation;
- set `noteDepth` honestly: `skim`, `abstract`, `read`, or `worked`;
- map the entry to one or more existing `failureSurfaces`; add or change the atlas taxonomy only when the cross-source editorial frame itself needs revision;
- keep `reportedFindings`, `evidenceLimits`, and `editorialInferences` distinct. An inference item must say that it is editorial and name the paper-facing evidence gap that makes it untested;
- leave uncertainty visible rather than completing a citation, page number, or claim by guesswork;
- preserve disagreement instead of rewriting it into a consensus;
- put human-machine editorial judgment in `editorialQuestion`, never in the source author's voice.

Do not add private project architecture, internal source-inspection or probe results, commit/revision identifiers, prompts, sessions, routing evidence, private names, or private continuity to any public copy. A publishable test artifact must instead be system-agnostic, use public or synthetic fixtures, and state method, environment, raw versus derived result, and limitations.

Run `python3 tools/build.py` before opening a pull request. The command validates the public schema and publication boundary, no-tracking/static contract, GitHub Pages subpath asset URLs, RDF attachment modes, and exact set of bundled PDFs, then rebuilds the generated browser payload from `data/materials.json`.
