"""Offline author intake and draft tests; no network or model calls."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from tools import author


def fresh_fixture() -> dict:
    return {
        "room": {"edition": "2026-10-25", "domains": [
            {"id": "navigation", "title": "Navigation", "materialIds": ["source-a"]}
        ]},
        "materials": [{
            "id": "source-a", "title": "Synthetic Source", "authors": ["Paper Author"],
            "year": 2025, "sourceUrl": "https://example.test/source",
            "readingScope": "Abstract and section 1 in a synthetic fixture.",
            "noteDepth": "skim", "intro": "A synthetic public source.",
        }],
        "studies": [{
            "id": "entry-a", "title": "Synthetic Note", "byline": "Site Author",
            "date": "2026-10-20", "intro": "A synthetic public note.",
            "sourcePath": "study/entries/entry-a.md", "readings": [{"materialId": "source-a"}],
            "bodyHtml": '<a href="?material=source-a">source</a>',
        }],
        "questions": [{
            "id": "question-a", "title": "Synthetic Question", "byline": "Site Author",
            "updated": "2026-10-21", "question": "What remains synthetic?", "intro": "A question.",
            "studyIds": ["entry-a"], "materialIds": ["source-a"], "findingIds": [],
        }],
        "findings": [{
            "id": "finding-a", "title": "Synthetic Finding", "byline": "Site Author",
            "updated": "2026-10-22", "claim": "A synthetic claim.", "when": "Only in this test.",
            "limit": "No empirical claim.", "questionIds": ["question-a"], "materialIds": ["source-a"],
        }],
    }


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
        for field in ("entries", "inquiries", "transfers", "mapDomains", "mapDirections"):
            self.assertIsInstance(result[field], list)
        self.assertEqual(result["target"], f"material/{source['id']}")
        self.assertIsInstance(result["affected"], list)


class ImpactAndBridgeTests(unittest.TestCase):
    def test_new_canonical_body_link_is_seen_without_rebuilding_projections(self):
        from tools import content
        projection = (author.ROOT / 'data/materials.json').read_bytes()
        old_entry = next(row for row in json.loads(projection)['studies'] if row['id'] == 'retrieval-and-relevance')
        self.assertNotIn('?study=after-a-correction', old_entry['bodyHtml'])
        compile_content = content.compile_content
        with tempfile.TemporaryDirectory() as temp:
            study = Path(temp) / 'study'
            shutil.copytree(author.STUDY_ROOT, study)
            body = study / 'entries/retrieval-and-relevance.md'
            body.write_text(body.read_text() + '\n\n[New explicit relation](after-a-correction.md)\n')
            with mock.patch.object(content, 'compile_content', side_effect=lambda: compile_content(study)):
                result = author.deep_impact('study', 'after-a-correction')
        affected = next(row for row in result['affected'] if row['id'] == 'retrieval-and-relevance')
        self.assertEqual(affected['distance'], 1)
        self.assertEqual(affected['path'][0]['relation'], 'body-link')
        self.assertEqual((author.ROOT / 'data/materials.json').read_bytes(), projection)

    def test_deep_impact_uses_fresh_compilation_and_shared_node_contract(self):
        payload = fresh_fixture()
        with mock.patch.object(author, "fresh_data", return_value=payload):
            material = author.deep_impact("material", "source-a")
            study = author.deep_impact("study", "entry-a")
            question = author.deep_impact("question", "question-a")
            finding = author.deep_impact("finding", "finding-a")
        self.assertEqual(material["target"], "material/source-a")
        self.assertEqual([(item["key"], item["distance"]) for item in material["affected"]],
                         [("finding/finding-a", 1), ("question/question-a", 1), ("study/entry-a", 1)])
        self.assertEqual(study["affected"][0]["key"], "question/question-a")
        self.assertEqual(question["affected"][0]["key"], "finding/finding-a")
        self.assertEqual(finding["affected"], [])
        for result in (material, study, question):
            for item in result["affected"]:
                self.assertEqual(len(item["path"]), item["distance"])
                self.assertIn("relation", item["path"][0])
        with mock.patch.object(author, "fresh_data", return_value=payload):
            with self.assertRaisesRegex(ValueError, "Unknown public object"):
                author.deep_impact("material", "missing")

    def test_missing_markdown_dependency_is_an_actionable_error(self):
        with mock.patch.object(author, "_compiler",
                               side_effect=ModuleNotFoundError("markdown_it")):
            with self.assertRaisesRegex(RuntimeError, "content-requirements"):
                author.fresh_data()

    def test_legacy_impact_keeps_original_fields_and_adds_paths(self):
        payload = fresh_fixture()
        payload['studies'][0]['continuation'] = {'materialIds':['source-a']}
        payload['questions'][0]['continuation'] = {'materialIds':['source-a']}
        payload['findings'].append({'id':'indirect', 'title':'Indirect', 'questionIds':['question-a']})
        with mock.patch.object(author, "fresh_data", return_value=payload) as compile_data, \
             mock.patch.object(author, "family", return_value=payload['materials']):
            output = author.impact('source-a')
        compile_data.assert_called_once()
        self.assertEqual(output["sourceId"], 'source-a')
        for field in ("entries", "inquiries", "transfers", "mapDomains", "mapDirections"):
            self.assertIsInstance(output[field], list)
        self.assertEqual([row['role'] for row in output['entries']], ['reading', 'continuation'])
        self.assertEqual([row['role'] for row in output['inquiries']], ['evidence-reading', 'continuation'])
        self.assertEqual([row['id'] for row in output['transfers']], ['finding-a'])
        self.assertEqual(output["target"], 'material/source-a')
        indirect = next(row for row in output['affected'] if row['id'] == 'indirect')
        self.assertEqual(indirect['distance'], 2)

    def test_bridge_does_not_trust_a_non_absolute_data_path(self):
        process = subprocess.run(
            [author._node(), str(author.BRIDGE)],
            input=json.dumps({"command": "impact", "dataFile": "data/materials.json",
                              "kind": "material", "id": "source-a"}),
            text=True, capture_output=True, cwd=author.ROOT,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("absolute dataFile", json.loads(process.stdout)["error"])

    def test_explicit_node_override_must_be_executable(self):
        with mock.patch.dict(os.environ, {"AMS_NODE": "/definitely/missing/node"}):
            with self.assertRaisesRegex(RuntimeError, "AMS_NODE"):
                author._node()


class DraftTests(unittest.TestCase):
    def test_legacy_impact_rejects_an_unknown_source_before_building(self):
        with mock.patch.object(author, "deep_impact") as deep:
            with self.assertRaisesRegex(ValueError, "Unknown source id"):
                author.impact("not-a-source")
        deep.assert_not_called()

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
            self.assertIn("私人作者草稿", prose)
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

    def test_workspace_draft_preserves_private_and_public_roles_without_public_readings(self):
        work = {
            "schema": "ams-workspace/2", "title": "Private desk",
            "question": "What should I check?", "synthesis": "My current synthesis.",
            "next": "Compare the examples.", "compare": [],
            "items": [{
                "kind": "material", "id": "source-a", "note": "Private material note.",
                "anchor": "#section-1", "contentVersion": "2026-10-25", "basis": "opaque",
                "excerpts": [{
                    "id": "excerpt-1", "quote": "Literal quoted text.\nSecond line.",
                    "comment": "Private excerpt comment.", "role": "contrast",
                    "anchor": "#section-2", "contentVersion": "2026-10-25", "basis": "opaque",
                }],
            }, {
                "kind": "study", "id": "entry-a", "note": "Private study note.",
                "anchor": "", "contentVersion": "2026-10-20", "basis": "opaque", "excerpts": [],
            }],
        }
        payload = fresh_fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace_file = root / "workspace.json"
            workspace_file.write_text(json.dumps(work, ensure_ascii=False), encoding="utf-8")
            output = root / "draft"
            with mock.patch.object(author, "fresh_data", return_value=payload):
                json_path, markdown_path = author.draft_from_workspace(
                    workspace_file, "workspace-note", "Workspace draft", "research-essay", output
                )
            record = json.loads(json_path.read_text())
            self.assertTrue(record["draft"])
            self.assertNotIn("readings", record)
            prose = markdown_path.read_text()
            for text in ("What should I check?", "My current synthesis.", "Compare the examples.",
                         "Private material note.", "Private study note.", "Literal quoted text.",
                         "Second line.", "Private excerpt comment.", "Paper Author",
                         "readingScope：Abstract and section 1", "sourceUrl",
                         "study/entries/entry-a.md", "Site Author",
                         "材料作者与本站札记作者是两个不同身份"):
                self.assertIn(text, prose)
            self.assertIn("> 私人作者草稿", prose)
            self.assertIn("作者角色：可能对照或反例（作者待核对）", prose)
            self.assertIn("接续位置：#section-1", prose)

    def test_workspace_rejection_is_atomic_and_unknown_or_oversize_input_writes_nothing(self):
        payload = fresh_fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "draft"
            workspace_file = root / "workspace.json"
            workspace_file.write_text('{"schema": "ams-workspace/2"}', encoding="utf-8")
            with mock.patch.object(author, "fresh_data", return_value=payload), \
                 mock.patch.object(author, "_bridge_call", side_effect=ValueError("当前书房没有")):
                with self.assertRaisesRegex(ValueError, "当前书房没有"):
                    author.draft_from_workspace(workspace_file, "bad", "Bad", "learning-note", output)
            self.assertFalse(output.exists(), "workspace validation happens before output creation")

            oversized = root / "oversized.json"
            oversized.write_bytes(b"x" * (author.WORKSPACE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "2 MiB"):
                author.draft_from_workspace(oversized, "bad", "Bad", "learning-note", output)
            self.assertFalse(output.exists())

            workspace_file.write_text(json.dumps({
                "schema": "ams-workspace/2", "title": "", "question": "",
                "synthesis": "", "next": "", "compare": [],
                "items": [{
                    "kind": "material", "id": "missing-source", "note": "", "anchor": "",
                    "contentVersion": "", "basis": "", "excerpts": [],
                }],
            }), encoding="utf-8")
            with mock.patch.object(author, "fresh_data", return_value=payload):
                with self.assertRaisesRegex(ValueError, "当前书房没有"):
                    author.draft_from_workspace(
                        workspace_file, "unknown-source", "Unknown", "learning-note", output
                    )
            self.assertFalse(output.exists(), "unknown public identities write no output")

            workspace_file.write_text(json.dumps({
                "schema": "ams-workspace/2", "title": "", "question": "",
                "synthesis": "", "next": "", "compare": [],
                "items": [{
                    "kind": "material", "id": "source-a", "note": "", "anchor": "",
                    "contentVersion": "", "basis": "",
                }],
            }), encoding="utf-8")
            with mock.patch.object(author, "fresh_data", return_value=payload):
                with self.assertRaisesRegex(ValueError, "摘录"):
                    author.draft_from_workspace(
                        workspace_file, "unknown-fields", "Unknown", "learning-note", output
                    )
            self.assertFalse(output.exists())

    def test_workspace_output_symlink_conflict_input_and_repo_boundaries(self):
        payload = fresh_fixture()
        work = {
            "schema": "ams-workspace/1", "title": "", "question": "", "synthesis": "",
            "next": "", "items": [], "compare": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace_file = root / "workspace.json"
            workspace_file.write_text(json.dumps(work), encoding="utf-8")
            real = root / "real"
            real.mkdir()
            link = root / "link"
            link.symlink_to(real, target_is_directory=True)
            with mock.patch.object(author, "ROOT", root / "public"):
                with mock.patch.object(author, "fresh_data", return_value=payload):
                    with self.assertRaisesRegex(ValueError, "symlink"):
                        author.draft_from_workspace(
                            workspace_file, "linked", "Linked", "learning-note", link
                        )

            output = root / "draft"
            output.mkdir()
            (output / "conflict.md").write_text("existing private text", encoding="utf-8")
            with mock.patch.object(author, "fresh_data", return_value=payload):
                with self.assertRaises(FileExistsError):
                    author.draft_from_workspace(
                        workspace_file, "conflict", "Conflict", "learning-note", output
                    )
            self.assertEqual((output / "conflict.md").read_text(), "existing private text")
            self.assertFalse((output / "conflict.json").exists())

            linked_input = root / "linked-workspace.json"
            linked_input.symlink_to(workspace_file)
            with self.assertRaisesRegex(ValueError, "non-symlink"):
                author.draft_from_workspace(
                    linked_input, "linked-input", "Linked", "learning-note", root / "other"
                )

            repository = root / "repository"
            repository.mkdir()
            repository_link = root / "repository-link"
            repository_link.symlink_to(repository, target_is_directory=True)
            with mock.patch.object(author, "ROOT", repository):
                with self.assertRaisesRegex(ValueError, "outside"):
                    author.draft_from_workspace(
                        workspace_file, "inside", "Inside", "learning-note",
                        repository / "output"
                    )
                with self.assertRaisesRegex(ValueError, "symlink|outside"):
                    author.draft_from_workspace(
                        workspace_file, "inside-link", "Inside", "learning-note",
                        repository_link / "output"
                    )

    def test_cli_contract_names_and_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = {
                "schema": "ams-workspace/1", "title": "", "question": "", "synthesis": "",
                "next": "", "items": [], "compare": [],
            }
            workspace_file = root / "workspace.json"
            workspace_file.write_text(json.dumps(work), encoding="utf-8")
            output = root / "draft"
            with mock.patch.object(author, "fresh_data", return_value=fresh_fixture()):
                with redirect_stdout(StringIO()):
                    code = author.main([
                        "draft-from-workspace", "--input", str(workspace_file),
                        "--slug", "cli-note", "--title", "CLI Note",
                        "--kind", "learning-note", "--out", str(output),
                    ])
            self.assertEqual(code, 0)
            self.assertTrue((output / "cli-note.json").is_file())
            self.assertTrue((output / "cli-note.md").is_file())

    def test_large_escape_dense_workspace_crosses_real_bridge_without_envelope_inflation(self):
        payload = fresh_fixture()
        payload['materials'] = [dict(payload['materials'][0], id=f'source-{i}') for i in range(5)]
        work = {'schema':'ams-workspace/2', 'title':'', 'question':'', 'synthesis':'', 'next':'', 'compare':[],
                'items':[{'kind':'material', 'id':f'source-{i}', 'note':'课'*18000, 'anchor':'',
                          'contentVersion':'2026-10-25', 'basis':'"\\'*90000, 'excerpts':[]} for i in range(5)]}
        text = json.dumps(work, ensure_ascii=False)
        self.assertGreater(len(text.encode()), 1900000)
        self.assertLess(len(text.encode()), author.WORKSPACE_BYTES)
        self.assertGreater(len(json.dumps({'text':text}, ensure_ascii=False).encode()), author.WORKSPACE_BYTES)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'large.json'; source.write_text(text)
            with mock.patch.object(author, 'fresh_data', return_value=payload):
                _, markdown = author.draft_from_workspace(source, 'large', 'Large', 'learning-note', Path(temp)/'out')
            prose = markdown.read_text()
        self.assertIn('课'*18000, prose)
        self.assertIn('快照不可比较', prose)
        self.assertNotIn('"\\'*100, prose, 'raw old snapshots are not echoed into the author draft')

    def test_draft_keeps_independent_excerpt_revision_after_object_rebase(self):
        payload = fresh_fixture()
        current = json.dumps(payload['studies'][0])
        old = dict(payload['studies'][0], intro='An older same-day explanation')
        work = {'schema':'ams-workspace/2', 'title':'', 'question':'', 'synthesis':'', 'next':'', 'compare':[],
                'items':[{'kind':'study', 'id':'entry-a', 'note':'', 'anchor':'', 'contentVersion':'2026-10-20',
                          'basis':current, 'excerpts':[{'id':'excerpt-1', 'quote':'A quotation', 'comment':'Private commentary',
                           'role':'question', 'anchor':'#section-1', 'contentVersion':'2026-10-20', 'basis':json.dumps(old)}]}]}
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'work.json'; source.write_text(json.dumps(work))
            with mock.patch.object(author, 'fresh_data', return_value=payload):
                _, markdown = author.draft_from_workspace(source, 'revisited', 'Revisited', 'learning-note', Path(temp)/'out')
            prose = markdown.read_text()
        self.assertIn('笔记版本检查：所据公开内容与当前相同', prose)
        self.assertIn('摘录版本检查：所据公开内容在保存后已有变化', prose)
        self.assertIn('https://indeliblevivi.github.io/agent-memory-study/study/entry-a/#section-1', prose)
        self.assertIn('Private commentary', prose)

    def test_pair_publication_refuses_a_racing_writer_and_rolls_back_only_its_own_new_file(self):
        real_link = os.link
        for racing_file in ('note.json', 'note.md'):
            with self.subTest(racing_file=racing_file), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); target = root/racing_file
                def race(source, destination):
                    if Path(destination) == target:
                        target.write_text('other writer')
                    return real_link(source, destination)
                with mock.patch.object(author.os, 'link', side_effect=race):
                    with self.assertRaises(FileExistsError):
                        author._write_pair(root/'note.json', {'draft':True}, root/'note.md', 'new text')
                self.assertEqual(target.read_text(), 'other writer')
                other = root/('note.md' if racing_file == 'note.json' else 'note.json')
                self.assertFalse(other.exists())
                self.assertEqual(sorted(p.name for p in root.iterdir()), [racing_file])


if __name__ == "__main__":
    unittest.main()
