"""Contract tests for question dossiers and portable practice findings.

These cover the additive canonical arrays and the shared practice exporter. They
use synthetic counterexamples and validate the shipped canonical content.
"""
import json
import tempfile
import unittest
from pathlib import Path

from tools import build


def fixture_evidence(label="Example link"):
    return {
        "label": label,
        "url": "https://example.org/evidence",
        "observation": "A public observation.",
        "limit": "Only covers the synthetic fixture.",
    }


def fixture_application(title="Adoption log"):
    return {
        "title": title,
        "status": "adopted",
        "date": "2026-09-21",
        "url": "https://example.org/application",
        "decision": "Adopted the ordering rule.",
        "observation": "Kept candidates distinct in the trial.",
        "limit": "Single internal trial, not a benchmark.",
    }


def fixture_question(question_id="experience-to-capability", **overrides):
    question = {
        "id": question_id,
        "title": "How does experience become capability?",
        "question": "经验怎样才不会被重复候选淹没？",
        "intro": "A public dossier framing the question.",
        "judgment": "A provisional editorial judgment.",
        "byline": "Editorial desk",
        "updated": "2026-09-21",
        "status": "open",
        "explanations": [{"title": "Candidate dilution", "text": "重复条目占据候选位。"}],
        "evidence": [fixture_evidence()],
        "materialIds": [],
        "studyIds": [],
        "findingIds": [],
        "nextTest": {
            "question": "Does dedup change ranking?",
            "comparison": "with vs without dedup",
            "success": "distinct findings survive",
            "reviseWhen": "duplicates still rank first",
            "boundary": "synthetic fixtures only",
        },
    }
    question.update(overrides)
    return question


def fixture_finding(finding_id="retrieval-candidate-competition", question_ids=None, **overrides):
    finding = {
        "id": finding_id,
        "title": "Retrieval candidate competition",
        "byline": "Editorial desk",
        "updated": "2026-09-21",
        "status": "proposed-transfer",
        "questionIds": list(question_ids or []),
        "materialIds": [],
        "triggers": ["候选增加之后，结果被重复条目占满", "candidate competition"],
        "claim": "Duplicate evidence rows should not multiply candidates.",
        "when": "When several memory items share one evidence row.",
        "action": "Deduplicate evidence rows before ranking.",
        "avoid": "Do not let duplicate rows inflate a candidate.",
        "validation": "Compare candidate counts before and after dedup.",
        "limit": "Lexical, deterministic; no semantic inference.",
        "evidence": [fixture_evidence()],
        "applications": [fixture_application()],
    }
    finding.update(overrides)
    return finding


def fixture_data(questions=None, findings=None, materials=None, studies=None):
    return {
        "materials": materials if materials is not None else [],
        "studies": studies if studies is not None else [],
        "questions": questions if questions is not None else [],
        "findings": findings if findings is not None else [],
    }


class PracticeDataValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = json.loads(
            (build.ROOT / "data" / "materials.json").read_text(encoding="utf-8")
        )

    def validate(self, data):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "materials.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return build.load_and_validate(path)

    def minimal_valid(self):
        # Root the fixture in the real materials/studies so only the additive
        # question/finding contract is under test.
        data = json.loads(json.dumps(self.canonical))
        material_id = data["materials"][0]["id"]
        question = fixture_question(
            findingIds=["retrieval-candidate-competition"], materialIds=[material_id]
        )
        finding = fixture_finding(
            question_ids=["experience-to-capability"], materialIds=[material_id]
        )
        data["questions"] = [question]
        data["findings"] = [finding]
        return data

    def test_minimal_question_and_finding_validate(self):
        validated = self.validate(self.minimal_valid())
        self.assertEqual(len(validated["questions"]), 1)
        self.assertEqual(len(validated["findings"]), 1)

    def test_questions_and_findings_are_required(self):
        for field in ("questions", "findings"):
            data = self.minimal_valid()
            del data[field]
            # Remove the reciprocal reference so the missing array is the only fault.
            for other, key in (("findings", "questionIds"), ("questions", "findingIds")):
                for record in data.get(other, []):
                    record[key] = []
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, f"data.{field}"):
                self.validate(data)

    def test_missing_required_fields_fail(self):
        question_fields = ["id", "title", "question", "intro", "judgment", "byline", "updated",
                           "status", "explanations", "evidence", "materialIds", "studyIds",
                           "findingIds", "nextTest"]
        for field in question_fields:
            data = self.minimal_valid()
            data["questions"][0].pop(field)
            # Isolate the question contract from reciprocal finding references.
            data["findings"][0]["questionIds"] = []
            with self.subTest(question=field), self.assertRaisesRegex(ValueError, r"questions\[0\]"):
                self.validate(data)
        finding_fields = ["id", "title", "byline", "updated", "status", "questionIds", "materialIds",
                          "triggers", "claim", "when", "action", "avoid", "validation", "limit",
                          "evidence", "applications"]
        for field in finding_fields:
            data = self.minimal_valid()
            data["findings"][0].pop(field)
            # Isolate the finding contract from reciprocal question references.
            data["questions"][0]["findingIds"] = []
            with self.subTest(finding=field), self.assertRaisesRegex(ValueError, r"findings\[0\]"):
                self.validate(data)

    def test_next_test_object_requires_all_parts(self):
        for field in ("question", "comparison", "success", "reviseWhen", "boundary"):
            data = self.minimal_valid()
            data["questions"][0]["nextTest"].pop(field)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "nextTest"):
                self.validate(data)

    def test_statuses_are_fixed(self):
        data = self.minimal_valid()
        data["questions"][0]["status"] = "answered"
        with self.assertRaisesRegex(ValueError, "status must be open"):
            self.validate(data)
        data = self.minimal_valid()
        data["findings"][0]["status"] = "adopted"
        with self.assertRaisesRegex(ValueError, "status must be proposed-transfer"):
            self.validate(data)

    def test_evidence_free_records_fail(self):
        data = self.minimal_valid()
        data["questions"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "evidence must be a non-empty list"):
            self.validate(data)
        data = self.minimal_valid()
        data["findings"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "evidence must be a non-empty list"):
            self.validate(data)

    def test_evidence_requires_all_fields(self):
        for field in ("label", "url", "observation", "limit"):
            data = self.minimal_valid()
            data["questions"][0]["evidence"][0].pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(data)

    def test_dangling_ids_fail(self):
        mutations = [
            lambda d: d["questions"][0]["materialIds"].append("missing-material"),
            lambda d: d["questions"][0]["studyIds"].append("missing-study"),
            lambda d: d["questions"][0]["findingIds"].append("missing-finding"),
            lambda d: d["findings"][0]["materialIds"].append("missing-material"),
            lambda d: d["findings"][0]["questionIds"].append("missing-question"),
        ]
        for mutate in mutations:
            data = self.minimal_valid()
            mutate(data)
            with self.subTest(mutation=mutate), self.assertRaisesRegex(ValueError, "unknown ids"):
                self.validate(data)

    def test_evidence_url_boundary(self):
        bad_urls = [
            "/Users/somebody/private.pdf",
            "file:///tmp/x",
            "../secrets.md",
            "research/does-not-exist.md",
            "http://example.org/insecure",
            ".git/config",
            ".env",
            "docs/.hidden.md",
            "tools/export_practice.cjs",
        ]
        for url in bad_urls:
            data = self.minimal_valid()
            data["questions"][0]["evidence"][0]["url"] = url
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "url"):
                self.validate(data)
        # HTTPS and an existing repo-relative file (with a #fragment) are allowed.
        good_urls = ["https://example.org/ok", "README.md#reader-验证",
                     "assets/practice.js", "docs/practice-brief-use.md"]
        for url in good_urls:
            data = self.minimal_valid()
            data["questions"][0]["evidence"][0]["url"] = url
            with self.subTest(url=url):
                self.validate(data)

    def test_reciprocal_membership_is_required(self):
        # A question claiming a finding that does not list it fails.
        data = self.minimal_valid()
        data["findings"][0]["questionIds"] = []
        with self.assertRaisesRegex(ValueError, "does not list the question"):
            self.validate(data)
        # The reverse direction is independently required.
        data = self.minimal_valid()
        data["questions"][0]["findingIds"] = []
        with self.assertRaisesRegex(ValueError, "does not list the finding"):
            self.validate(data)
        # Adjacent findings may legitimately carry no question membership.
        data = self.minimal_valid()
        data["questions"][0]["findingIds"] = []
        data["findings"][0]["questionIds"] = []
        self.validate(data)

    def test_applications_are_optional_and_status_bounded(self):
        data = self.minimal_valid()
        data["findings"][0]["applications"] = []
        self.validate(data)
        for status in ("adopted", "rejected", "inconclusive", "cited"):
            data = self.minimal_valid()
            data["findings"][0]["applications"][0]["status"] = status
            self.validate(data)
        data = self.minimal_valid()
        data["findings"][0]["applications"][0]["status"] = "proven"
        with self.assertRaisesRegex(ValueError, "status is unsupported"):
            self.validate(data)

    def test_application_url_and_fields_are_enforced(self):
        for field in ("title", "status", "date", "url", "decision", "observation", "limit"):
            data = self.minimal_valid()
            data["findings"][0]["applications"][0].pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(data)
        data = self.minimal_valid()
        data["findings"][0]["applications"][0]["url"] = "../private.md"
        with self.assertRaisesRegex(ValueError, "url"):
            self.validate(data)

    def test_triggers_must_be_non_empty(self):
        data = self.minimal_valid()
        data["findings"][0]["triggers"] = []
        with self.assertRaisesRegex(ValueError, "triggers"):
            self.validate(data)

    def test_duplicate_ids_fail(self):
        data = self.minimal_valid()
        duplicate = fixture_question()
        data["questions"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate question id"):
            self.validate(data)
        data = self.minimal_valid()
        data["findings"].append(fixture_finding())
        data["questions"][0]["findingIds"] = []
        with self.assertRaisesRegex(ValueError, "duplicate finding id"):
            self.validate(data)


if __name__ == "__main__":
    unittest.main()
