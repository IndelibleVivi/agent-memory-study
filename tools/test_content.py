"""Focused contracts for canonical study authoring and legacy projections."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import content
from tools.migrate_sources import migrate


class MarkdownCompilerTests(unittest.TestCase):
    def test_markdown_dependency_is_declared(self):
        requirements = (content.ROOT / "tools" / "content-requirements.txt").read_text()
        self.assertIn("markdown-it-py==4.0.0", requirements)

    @unittest.skipUnless(
        __import__("importlib").util.find_spec("markdown_it") is not None,
        "markdown-it-py not installed in this isolated test environment",
    )
    def test_markdown_disables_raw_html_and_unsafe_links(self):
        for source in (
            "<script>alert(1)</script>\n\n## Heading\n\nBody",
            "<details>raw</details>\n\n## Heading\n\nBody",
            "## Heading\n\n[unsafe](javascript:alert(1))",
        ):
            with self.subTest(source=source), self.assertRaises(content.ContentError):
                content._strict_markdown(source, "fixture.md")

    @unittest.skipUnless(
        __import__("importlib").util.find_spec("markdown_it") is not None,
        "markdown-it-py not installed in this isolated test environment",
    )
    def test_markdown_renders_safe_https_links(self):
        _, body_html, sections, ast = content._strict_markdown(
            "# Title\n\n## Heading\n\nA [safe](https://example.org) body.\n",
            "fixture.md",
        )
        self.assertIn('rel="noreferrer noopener"', body_html)
        self.assertEqual(sections, [{"title": "Heading", "text": "A [safe](https://example.org) body."}])


def _fixture_catalog(root: Path) -> None:
    corpus = root / "source-corpus"
    for family in ("works", "revisions", "notes"):
        (corpus / family).mkdir(parents=True)
    (root / "entries").mkdir()
    (root / "inquiries").mkdir()
    (root / "transfers").mkdir()
    source = {
        "id": "source-a", "number": 1, "title": "A source", "authors": ["Example"],
        "year": 2026, "noteDepth": "abstract", "readingScope": "Abstract only",
        "intro": "A source.", "keyPoints": ["A point."], "editorialQuestion": "What next?",
        "categories": ["Reliability"], "failureSurfaces": [], "sourceUrl": "https://example.org/a",
        "pdf": {"delivery": "official", "url": "https://example.org/a.pdf"},
    }
    work, revision, note = migrate(source)
    for family, record in (("works", work), ("revisions", revision), ("notes", note)):
        (corpus / family / "source-a.json").write_text(json.dumps(record), encoding="utf-8")
    (root / "entries" / "note-b.md").write_text(
        "# A note\n\n## What is being learned?\n\nA concrete note, not a form.\n", encoding="utf-8"
    )
    (root / "entries" / "note-b.json").write_text(json.dumps({
        "id": "note-b", "title": "A note", "kind": "learning-note",
        "date": "2026-10-18", "byline": "Author", "intro": "A short note.",
        "bodyFile": "entries/note-b.md",
    }), encoding="utf-8")
    (root / "entries" / "late-a.md").write_text(
        "## Late note\n\nA note with an earlier date.\n", encoding="utf-8"
    )
    (root / "entries" / "late-a.json").write_text(json.dumps({
        "id": "late-a", "title": "Earlier date", "kind": "research-essay",
        "date": "2026-10-17", "byline": "Author", "intro": "Sparse essay.",
        "bodyFile": "entries/late-a.md",
    }), encoding="utf-8")
    (root / "catalog.json").write_text(json.dumps({
        "title": "Study", "intro": "Intro", "editorialNote": "Note",
        "filters": ["Reliability"],
        "atlas": {"failureSurfaces": []},
        "sourceOrder": ["source-a"], "inquiryOrder": [],
        "transferOrder": [], "entryOrder": ["note-b"],
    }), encoding="utf-8")


@unittest.skipUnless(
    __import__("importlib").util.find_spec("markdown_it") is not None,
    "markdown-it-py not installed in this isolated test environment",
)
class SparseAuthoringTests(unittest.TestCase):
    def test_teaching_exercises_are_explicit_and_do_not_require_experiment_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture_catalog(root)
            path = root / "entries/note-b.json"
            record = json.loads(path.read_text())
            for kind in ("retrieval-sets", "ordered-index"):
                record["exercise"] = kind
                path.write_text(json.dumps(record))
                note = next(s for s in content.compile_content(root)["studies"] if s["id"] == "note-b")
                self.assertEqual(note["exercise"], kind)
                self.assertNotIn("resultsUrl", note)
            record["exercise"] = "arbitrary-script"
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(content.ContentError, "exercise"):
                content.compile_content(root)

    def test_external_output_paths_report_drift_and_can_be_written(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture_catalog(root)
            data = content.compile_content(root)
            json_path, js_path = root / "projection.json", root / "projection.js"
            self.assertEqual(len(content.check_projection(data, json_path, js_path)), 2)
            content.write_all(data, json_output=json_path, js_output=js_path)
            self.assertEqual(content.check_projection(data, json_path, js_path), [])
            json_path.write_text("{invalid")
            self.assertIn("generated drift", content.check_projection(data, json_path, js_path)[0])
            with self.assertRaisesRegex(content.ContentError, "invalid JSON at line"):
                content._read_json(json_path)
            with self.assertRaisesRegex(content.ContentError, "file is missing"):
                content._read_json(root / "missing.json")

    def test_missing_body_file_field_names_the_authoring_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture_catalog(root)
            path = root / "entries/note-b.json"
            record = json.loads(path.read_text())
            del record["bodyFile"]
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(content.ContentError, "bodyFile"):
                content.compile_content(root)

    def test_sparse_entries_compile_and_unlisted_order_is_date_then_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture_catalog(root)
            data = content.compile_content(root)
        self.assertEqual([entry["id"] for entry in data["studies"]], ["note-b", "late-a"])
        sparse = data["studies"][1]
        for field in ("readings", "externalReadings", "takeaways"):
            self.assertEqual(sparse[field], [])
        self.assertNotIn("artifactUrl", sparse)
        self.assertNotIn("number", sparse)
        self.assertNotIn("bodyFile", sparse)
        self.assertTrue(sparse["bodyHtml"])

    def test_note_without_headings_is_publishable_but_draft_is_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture_catalog(root)
            (root / "entries/note-b.md").write_text("A concrete explanation without a template.")
            note = content.compile_content(root)["studies"][0]
            self.assertIn("A concrete explanation", note["bodyHtml"])
            record_path = root / "entries/note-b.json"
            record = json.loads(record_path.read_text())
            record["draft"] = True
            record_path.write_text(json.dumps(record))
            with self.assertRaisesRegex(content.ContentError, "draft"):
                content.compile_content(root)

    def test_body_links_and_tables_compile_for_the_reader(self):
        _, html, _, ast = content._strict_markdown(
            "[Continue](../programme/method.md)\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n",
            "fixture.md", source_path="study/entries/fixture.md",
            link_map={"study/programme/method.md": "how-we-study"})
        self.assertIn('href="?study=how-we-study"', html)
        self.assertIn("<table>", html)
        self.assertEqual(ast["references"][0]["kind"], "entry")
        with self.assertRaisesRegex(content.ContentError, "escapes repository"):
            content._strict_markdown("[Private](../../../outside.md)", "fixture.md",
                                     source_path="study/entries/fixture.md")

    def test_catalog_rejects_unknown_and_duplicate_ids(self):
        for value in (["source-a", "missing"], ["source-a", "source-a"]):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                _fixture_catalog(root)
                catalog = json.loads((root / "catalog.json").read_text())
                catalog["sourceOrder"] = value
                (root / "catalog.json").write_text(json.dumps(catalog))
                with self.subTest(order=value), self.assertRaises(content.ContentError):
                    content.compile_content(root)

    def test_empty_failure_surfaces_are_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture_catalog(root)
            data = content.compile_content(root)
        self.assertEqual(data["materials"][0]["failureSurfaces"], [])

    def test_map_dangling_references_fail_when_present(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture_catalog(root)
            (root / "map.json").write_text(json.dumps({
                "edition": "1", "thesis": "Thesis", "intro": "Intro", "invitation": "Read",
                "domains": [{"id": "one", "title": "One", "intro": "Intro",
                             "materialIds": ["missing-source"]}],
                "directions": [], "starts": [], "changes": [],
            }))
            with self.assertRaisesRegex(content.ContentError, "dangling ids"):
                content.compile_content(root)


class LegacyMigrationTests(unittest.TestCase):
    def test_existing_four_bodies_roundtrip_without_semantic_loss(self):
        data = json.loads((content.DATA_OUTPUT).read_text(encoding="utf-8"))
        for entry in data["studies"][:4]:
            source = (content.CONTENT_ROOT / "entries" / f"{entry['id']}.md").read_text(encoding="utf-8")
            markdown = entry["bodyMarkdown"]
            for section in entry["sections"]:
                self.assertIn(f"## {section['title']}", source)
                self.assertIn(section["text"], markdown)

    def test_generated_projection_has_one_editable_truth(self):
        self.assertFalse((content.ROOT / "content").exists())
        self.assertTrue((content.CONTENT_ROOT / "catalog.json").is_file())
        self.assertTrue((content.DATA_OUTPUT).is_file())

    def test_old_source_fields_and_memberships_are_preserved(self):
        projection = json.loads(content.DATA_OUTPUT.read_text(encoding="utf-8"))
        authored = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((content.ROOT / "tests/fixtures/legacy-sources").glob("*.json"))
        ]
        by_id = {source["id"]: source for source in authored}
        self.assertEqual([source["id"] for source in projection["materials"]],
                         json.loads((content.CONTENT_ROOT / "catalog.json").read_text())["sourceOrder"])
        for source in projection["materials"]:
            original = by_id[source["id"]]
            for field, value in original.items():
                if field != "failureSurfaces":
                    self.assertEqual(source[field], value, f"{source['id']}.{field}")
            authored_memberships = set(original.get("failureSurfaces", []))
            for surface in projection["atlas"]["failureSurfaces"]:
                self.assertEqual(
                    source["id"] in surface["materialIds"],
                    surface["id"] in authored_memberships,
                )


if __name__ == "__main__":
    unittest.main()
