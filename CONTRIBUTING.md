# Contributing

Contributions that improve source locators, bibliographic accuracy, accessibility, or the reader itself are welcome.

For a new material entry:

- link to the canonical or official source over a mirror;
- use `pdf.delivery: official` by default and link the official full text;
- add a PDF to `papers/` only when its public redistribution license has been checked, then record its exact author/title/source/license attribution in `THIRD_PARTY_NOTICES.md` and whitelist the exact filename;
- do not add OCR derivatives, screenshots of full texts, private exports, Zotero keys/tags, chat locators, or local filesystem paths;
- keep quotation distinct from paraphrase and attach a precise source locator to any quotation;
- set `noteDepth` honestly: `skim`, `abstract`, `read`, or `worked`;
- leave uncertainty visible rather than completing a citation, page number, or claim by guesswork;
- preserve disagreement instead of rewriting it into a consensus;
- put human-machine editorial judgment in `editorialQuestion`, never in the source author's voice.

Run `python3 tools/build.py` before opening a pull request. The command validates the public data boundary, RDF attachment modes, and exact set of bundled PDFs, then rebuilds the browser payload.
