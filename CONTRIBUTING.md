# Contributing

Contributions that improve source locators, bibliographic accuracy, accessibility, or the reader itself are welcome.

For a new material entry:

- link to the canonical or official source over a mirror;
- do not add PDFs, screenshots of full texts, private exports, Zotero keys/tags, chat locators, or local filesystem paths;
- keep quotation distinct from paraphrase and attach a precise source locator to any quotation;
- set `noteDepth` honestly: `skim`, `abstract`, `read`, or `worked`;
- leave uncertainty visible rather than completing a citation, page number, or claim by guesswork;
- preserve disagreement instead of rewriting it into a consensus;
- put human-machine editorial judgment in `editorialQuestion`, never in the source author's voice.

Run `python3 tools/build.py` before opening a pull request. The command validates the public data boundary and rebuilds the browser payload.
