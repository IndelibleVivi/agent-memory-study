"""Offline author intake and draft tests; no network or model calls."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import author


class AuthorIntakeTests(unittest.TestCase):
    def test_exact_doi_and_url_recognize_existing_source(self):
        data = author.family(author.SOURCES)
        source = data[0]
        first = author.inspect(source["sourceUrl"])
        self.assertEqual(first["matchStatus"], "exact")
        self.assertEqual(first["source"]["id"], source["id"])
        if source.get("doi"):
            second = author.inspect(source["doi"])
            self.assertEqual(second["source"]["id"], source["id"])

    def test_generic_urls_do_not_merge_distinct_paths_queries_or_versions(self):
        sources = [{"id": "a", "title": "A", "sourceUrl": "https://example.org/Paper?id=1"}]
        for value in ["https://example.org/paper?id=1", "https://example.org/Paper?id=2",
                      "https://example.org/Other", "https://example.org/Paper/v2"]:
            self.assertEqual(author.match_source(sources, value)["status"], "unrecognized")
        key, _ = author.canonical_url("https://notarxiv.org/abs/2502.01736")
        self.assertNotEqual(key, "arxiv:2502.01736")

    def test_title_match_is_conservative(self):
        source = author.family(author.SOURCES)[0]
        result = author.inspect(source["title"])
        self.assertIn(result["matchStatus"], {"exact", "title-match"})
        self.assertFalse(result["note"].startswith("Input was not recognized"))

    def test_unknown_input_does_not_claim_fetch(self):
        result = author.inspect("https://example.invalid/not-a-known-paper")
        self.assertEqual(result["matchStatus"], "unrecognized")
        self.assertFalse(result["recognized"])
        self.assertIsNone(result["dependencies"])
        self.assertIn("not recognized", result["note"])

    def test_version_identifier_is_distinguished_from_same_source(self):
        source = author.family(author.SOURCES)[0]
        if "arxiv.org/abs/" not in source.get("sourceUrl", ""):
            self.skipTest("fixture requires an arXiv source")
        base = source["sourceUrl"].removesuffix("v1").removesuffix("v2").removesuffix("v3")
        result = author.inspect(f"{base}v99")
        self.assertEqual(result["matchStatus"], "new-version")
        self.assertTrue(result["versionCandidates"])

    def test_impact_lists_explicit_dependencies_and_map_navigation_separately(self):
        source = author.family(author.SOURCES)[0]
        result = author.impact(source["id"])
        self.assertEqual(result["sourceId"], source["id"])
        self.assertIsInstance(result["entries"], list)
        self.assertIsInstance(result["inquiries"], list)
        self.assertIsInstance(result["transfers"], list)
        self.assertIsInstance(result["mapDomains"], list)


class DraftTests(unittest.TestCase):
    def test_minimal_draft_is_outside_canonical_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            json_path, markdown_path = author.create_draft(
                "new-research-note", "A new research note", "learning-note", root
            )
            record = json.loads(json_path.read_text())
            self.assertEqual(set(record), {
                "id", "title", "kind", "date", "byline", "intro", "bodyFile", "draft"
            })
            self.assertTrue(record["draft"])
            self.assertNotIn("readings", record)
            self.assertNotIn("takeaways", record)
            self.assertNotIn("artifactUrl", record)
            prose = markdown_path.read_text()
            self.assertNotIn("results", prose.casefold())
            with self.assertRaises(FileExistsError):
                author.create_draft("new-research-note", "A new research note", "learning-note", root)

    def test_draft_cannot_be_created_inside_public_repo(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            author.create_draft("private-note", "Title", "learning-note", author.ROOT / "drafts")

    def test_draft_rejects_unknown_kind_and_unsafe_slug(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                author.create_draft("valid-slug", "Title", "experiment", root)
            with self.assertRaises(ValueError):
                author.create_draft("../private", "Title", "learning-note", root)


if __name__ == "__main__":
    unittest.main()
