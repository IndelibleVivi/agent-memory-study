"""Migration identity and selected private export, using the real core schema."""
import base64
import copy
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from schemas.validate import validate_command
from services.local import portable
from services.local.records import command, record, ref, revise
from services.local.repository import Repository, RepositoryError, encoded


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.repo = Repository(self.root / "data", self.project, validate_command)
        public = record("entry", {"title":"Original public entry","byline":"Test author","entry_type":"learning-note","date":"2026-10-29","intro":"basis","body_file":"study/entries/known.md","payload":{}},id="entry:known")
        public["revision"] = public["state_revision"] = "rev:public-old"
        self.repo.cache_public_records([public])
        self.lookup = lambda kind, id: {"kind": "entry", "id": "entry:" + id, "revision": "rev:public-old"} if id == "known" else None

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def legacy(self):
        return {"schema": "ams-workspace/2", "title": "旧案头", "question": "PRIVATE_CANARY_这是谁的依据", "synthesis": "", "next": "稍后读", "compare": [], "items": [
            {"kind": "study", "id": "known", "note": "原有文字", "anchor": "#section-2", "basis": '{"id":"known","bodyHtml":"<script>alert(1)</script>"}', "contentVersion": "旧日期", "excerpts": [
                {"id": "excerpt-one", "quote": "旧的句子", "basis": "与对象basis不同的摘录依据", "anchor": "#old", "contentVersion": "更旧日期", "purpose": "question", "note": "未确认"}]},
            {"kind": "study", "id": "missing", "note": "https://never-fetch.invalid/", "anchor": "", "basis": "<img src=x onerror=steal()>", "contentVersion": "", "excerpts": []}]}

    def test_preview_never_writes_and_unknown_html_is_preserved_as_inert_bytes(self):
        raw = encoded(self.legacy()).encode()
        report = portable.preview(raw, self.lookup)
        self.assertEqual(report["unresolved"], [{"kind": "study", "id": "missing"}])
        self.assertEqual(self.repo.list(), [])
        result = portable.confirm(self.repo, raw, report["digest"], self.lookup)
        session = self.repo.load("session", result["mapping"]["roots"][1]["id"])
        self.assertEqual(session["payload"]["question"], self.legacy()["question"])
        known, missing = session["payload"]["items"]
        self.assertEqual(known["binding"], "review-required")
        self.assertEqual(known["legacy_excerpts"][0]["basis"], "与对象basis不同的摘录依据")
        self.assertEqual(missing["binding"], "unresolved")
        art = self.repo.load(**missing["representation_ref"])
        original = json.loads(self.repo.read_blob(art["artifact_digest"]))
        self.assertEqual(original["basis"], "<img src=x onerror=steal()>")
        count = len(self.repo.events())
        again = portable.confirm(self.repo, raw, report["digest"], self.lookup)
        self.assertTrue(again["already_imported"])
        self.assertEqual(len(self.repo.events()), count)

    def test_multibyte_limit_duplicate_item_and_excerpt_reject_atomically(self):
        for mutation in ("item", "excerpt", "large"):
            value = self.legacy()
            if mutation == "item": value["items"].append(copy.deepcopy(value["items"][0]))
            elif mutation == "excerpt": value["items"][0]["excerpts"] *= 2
            else: value["question"] = "字" * (2 * 1024 * 1024 // 3 + 1)
            with self.assertRaises(RepositoryError): portable.preview(encoded(value).encode(), self.lookup)
        self.assertEqual(self.repo.list(), [])

    def test_twelve_distinct_excerpts_preserve_order(self):
        value = self.legacy()
        value["items"][0]["excerpts"] = [{"id": f"quote-{i}", "text": f"第{i}段", "basis": f"依据{i}"} for i in range(12)]
        raw = encoded(value).encode(); report = portable.preview(raw, self.lookup)
        portable.confirm(self.repo, raw, report["digest"], self.lookup)
        self.assertEqual([e["id"] for e in self.repo.list("session")[0]["payload"]["items"][0]["legacy_excerpts"]], [f"quote-{i}" for i in range(12)])

    def test_export_closure_does_not_include_an_unselected_private_thread(self):
        raw = encoded(self.legacy()).encode(); report = portable.preview(raw, self.lookup)
        result = portable.confirm(self.repo, raw, report["digest"], self.lookup)
        unrelated = record("thread", {"title": "不在选材里", "byline": "Local researcher", "status": "open", "payload": {"secret": "PRIVATE_CANARY_UNSELECTED"}})
        self.repo.apply(command(unrelated))
        bundle = portable.export(self.repo, result["mapping"]["roots"])
        self.assertNotIn("PRIVATE_CANARY_UNSELECTED", encoded(bundle))
        check = portable.preview(encoded(bundle).encode(), self.lookup)
        target = Repository(self.root / "restored", self.project, validate_command)
        try:
            migrated = portable.confirm(target, encoded(bundle).encode(), check["digest"], self.lookup)
            self.assertEqual(migrated["mapping"]["roots"], result["mapping"]["roots"])
            self.assertEqual(target.list("session"), self.repo.list("session"))
            self.assertTrue(target.doctor()["ok"])
        finally: target.close()

    def test_changed_preview_and_corrupt_portable_bytes_reject(self):
        raw = encoded(self.legacy()).encode(); report = portable.preview(raw, self.lookup)
        with self.assertRaisesRegex(RepositoryError, "预览不同"):
            portable.confirm(self.repo, raw+b" ", report["digest"], self.lookup)
        result = portable.confirm(self.repo, raw, report["digest"], self.lookup)
        bundle = portable.export(self.repo, result["mapping"]["roots"])
        first = next(iter(bundle["blobs"])); bundle["blobs"][first] = base64.b64encode(b"wrong").decode()
        with self.assertRaisesRegex(RepositoryError, "身份不一致"):
            portable.preview(encoded(bundle).encode(), self.lookup)

    def test_all_legacy_versions_have_an_explicit_migration_lane(self):
        for schema in ("ams-workspace/1", "ams-continuation/1"):
            value = self.legacy()
            if schema == "ams-continuation/1": value = {**value["items"][0], "schema": schema, "title": "接续迁移"}
            else: value["schema"] = schema
            raw = encoded(value).encode(); report = portable.preview(raw, self.lookup)
            portable.confirm(self.repo, raw, report["digest"], self.lookup)
        self.assertEqual(len(self.repo.list("thread")), 2)

    def test_unacknowledged_input_recovers_as_separate_inert_workspace(self):
        raw = encoded({'schema':portable.RECOVERY_FORMAT,'record':{'kind':'session','payload':{
            'question':'尚未收到 ack 的输入','synthesis':'保留这段','next':'核对原依据',
            'items':[{'key':'old:one','note':'原旁注','target_ref':{'kind':'entry','id':'lost','revision':'rev:missing'},
                      'anchor':'#section-2','legacy_excerpts':[{'id':'old-q','quote':'原句','basis':'旧快照'}]}]}}}).encode()
        report=portable.preview(raw,self.lookup)
        result=portable.confirm(self.repo,raw,report['digest'],self.lookup)
        session=self.repo.load('session',result['mapping']['roots'][1]['id'])
        self.assertEqual(session['payload']['question'],'尚未收到 ack 的输入')
        item=session['payload']['items'][0]
        self.assertEqual(item['note'],'原旁注')
        artifact=self.repo.load(**item['target_ref'])
        saved=json.loads(self.repo.read_blob(artifact['artifact_digest']))
        self.assertIn('rev:missing',saved['basis'])
        self.assertEqual(self.repo.read_blob(self.repo.load(**result['mapping']['original_ref'])['artifact_digest']),raw)

    def test_concurrent_import_confirms_create_one_mapping(self):
        raw=encoded(self.legacy()).encode();report=portable.preview(raw,self.lookup)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:portable.confirm(self.repo,raw,report['digest'],self.lookup),range(2)))
        self.assertEqual(results[0]['mapping'],results[1]['mapping'])
        self.assertEqual(len(self.repo.list('thread')),1)

    def test_missing_blob_and_oversize_legacy_continuation_rejected_before_writing(self):
        raw=encoded(self.legacy()).encode();report=portable.preview(raw,self.lookup)
        result=portable.confirm(self.repo,raw,report['digest'],self.lookup)
        bundle=portable.export(self.repo,result['mapping']['roots']);bundle['blobs']={}
        with self.assertRaisesRegex(RepositoryError,'完整依据'):portable.preview(encoded(bundle).encode(),self.lookup)
        old={**self.legacy()['items'][0],'schema':'ams-continuation/1','note':'x'*(128*1024)}
        with self.assertRaisesRegex(RepositoryError,'容量'):portable.preview(encoded(old).encode(),self.lookup)


if __name__ == "__main__": unittest.main()
