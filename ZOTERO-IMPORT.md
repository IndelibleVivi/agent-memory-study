# Import into Zotero

1. Download `agent-memory-study-zotero.zip` from the latest GitHub release.
2. Unzip the archive. Keep `agent-memory-study.rdf` beside the `papers/` directory.
3. In Zotero Desktop, choose `File → Import… → A file` and select `agent-memory-study.rdf`.
4. Keep Zotero's default **Copy files** behavior. Do not choose **Link to files**, unless you intentionally want attachments tied to the unzip location.

The expected result is 15 top-level bibliographic items with 15 attachments:

- 8 stored PDFs copied into Zotero storage;
- 7 linked official PDF URLs;
- no tags, private notes, local Zotero keys, local filesystem paths, or OCR derivative.

The Cambridge full-text link may require institutional access. Doyle 1979 links the official MIT DSpace scan; the locally generated searchable OCR edition is deliberately absent.

The RDF relies on relative paths for the eight bundled files, so importing a separately downloaded RDF without its adjacent `papers/` directory is incomplete.
