import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools import build


class PublicReadingRoomBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_path = build.ROOT / "data" / "materials.json"
        cls.data = json.loads(cls.data_path.read_text(encoding="utf-8"))

    def validate_copy(self, data):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "materials.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return build.load_and_validate(path)

    def test_current_public_data_validates(self):
        validated = build.load_and_validate(self.data_path)
        self.assertGreater(len(validated["materials"]), 0)
        self.assertEqual(
            [material["number"] for material in validated["materials"]],
            list(range(1, len(validated["materials"]) + 1)),
        )

    def test_pdf_delivery_counts_and_exact_allowlist(self):
        bundled = [
            material for material in self.data["materials"]
            if material["pdf"]["delivery"] == "bundled"
        ]
        official = [
            material for material in self.data["materials"]
            if material["pdf"]["delivery"] == "official"
        ]
        self.assertEqual(len(bundled) + len(official), len(self.data["materials"]))
        self.assertEqual(
            {material["pdf"]["url"] for material in bundled},
            {
                path.relative_to(build.ROOT).as_posix()
                for path in (build.ROOT / "papers").glob("*.pdf")
            },
        )

    def test_collection_can_grow_without_fixed_material_count(self):
        grown = copy.deepcopy(self.data)
        material = copy.deepcopy(grown["materials"][-1])
        material.update({
            "number": len(grown["materials"]) + 1,
            "id": "future-public-material",
            "title": "A future public material",
            "authors": ["Example Author"],
            "shortAuthor": "Example",
            "noteDepth": "skim",
            "readingScope": "Public abstract and introduction.",
            "intro": "A public fixture proving that corpus size is not fixed by the schema.",
            "keyPoints": ["The new material remains source-linked and independently understandable."],
            "editorialQuestion": "What would change this failure-surface mapping?",
            "categories": [grown["filters"][0]],
            "failureSurfaces": ["state-representation"],
            "sourceUrl": "https://example.org/future-material",
            "pdf": {"delivery": "official", "url": "https://example.org/future-material.pdf"},
        })
        for optional_field in (
            "whyRead", "argumentMap", "methodNotes", "reportedFindings", "evidenceLimits",
            "sourceTensions", "editorialInferences", "openProtocols", "contributions",
        ):
            material.pop(optional_field, None)
        grown["materials"].append(material)
        grown["atlas"]["failureSurfaces"][0]["materialIds"].append(material["id"])

        validated = self.validate_copy(grown)
        self.assertEqual(len(validated["materials"]), len(self.data["materials"]) + 1)

    def test_existing_close_read_entries_keep_richer_read_schema(self):
        by_id = {material["id"]: material for material in self.data["materials"]}
        atma = by_id["a-tma-state-aware-memory"]
        insightemb = by_id["insightemb-action-intent-retrieval"]
        self.assertEqual(atma["noteDepth"], "read")
        self.assertEqual(insightemb["noteDepth"], "read")
        current_skim_ids = {
            "trustmem-consolidation", "verifiable-memory", "mosaic-long-term-memory",
            "proactive-wake-anchor", "pm-bench", "mistake-notebook-learning",
            "coala-cognitive-architecture", "storage-to-experience",
            "continual-learning-experience-reuse", "agentic-memory", "midca-dual-cycle",
            "truth-maintenance-system", "agm-theory-change", "memory-beyond-recall",
        }
        self.assertTrue(all(by_id[material_id]["noteDepth"] == "skim" for material_id in current_skim_ids))
        for material in (atma, insightemb):
            for field in (
                "whyRead", "argumentMap", "methodNotes", "reportedFindings", "evidenceLimits",
                "sourceTensions", "editorialInferences", "openProtocols",
            ):
                self.assertTrue(material[field])
            self.assertTrue(all(
                protocol["status"] == "proposed-not-run"
                for protocol in material["openProtocols"]
            ))
        self.assertEqual(atma["editorialInferences"][0]["label"], "Read-side label amplification")
        self.assertEqual(insightemb["editorialInferences"][0]["label"], "Retrieval is a staged decision")

    def test_sparse_records_remain_valid_without_invented_richer_fields(self):
        validated = self.validate_copy(copy.deepcopy(self.data))
        truth_maintenance = next(
            material for material in validated["materials"]
            if material["id"] == "truth-maintenance-system"
        )
        self.assertNotIn("reportedFindings", truth_maintenance)
        self.assertNotIn("evidenceLimits", truth_maintenance)
        self.assertNotIn("editorialInferences", truth_maintenance)

    def test_unknown_failure_surface_is_rejected(self):
        invalid = copy.deepcopy(self.data)
        invalid["materials"][0]["failureSurfaces"] = ["not-a-public-surface"]
        with self.assertRaisesRegex(ValueError, "unknown failure surfaces"):
            self.validate_copy(invalid)

    def test_failure_surface_membership_must_match_both_directions(self):
        material_only = copy.deepcopy(self.data)
        material_only["atlas"]["failureSurfaces"][0]["materialIds"].remove(
            "a-tma-state-aware-memory"
        )
        with self.assertRaisesRegex(ValueError, "failure surface membership mismatch"):
            self.validate_copy(material_only)

        surface_only = copy.deepcopy(self.data)
        surface_only["materials"][0]["failureSurfaces"].remove("state-representation")
        with self.assertRaisesRegex(ValueError, "failure surface membership mismatch"):
            self.validate_copy(surface_only)

    def test_private_runtime_copy_is_rejected(self):
        invalid = copy.deepcopy(self.data)
        invalid["materials"][0]["editorialQuestion"] = "Private runtime probe and offline probe"
        with self.assertRaisesRegex(ValueError, "private token"):
            self.validate_copy(invalid)

    def test_private_project_mapping_names_are_rejected(self):
        invalid = copy.deepcopy(self.data)
        invalid["materials"][0]["editorialQuestion"] = "Could Tilia use this architecture?"
        with self.assertRaisesRegex(ValueError, "private token"):
            self.validate_copy(invalid)

    def test_private_engineering_fields_are_rejected(self):
        invalid = copy.deepcopy(self.data)
        invalid["materials"][0]["projectMapping"] = {"status": "internal"}
        with self.assertRaisesRegex(ValueError, "private fields"):
            self.validate_copy(invalid)

    def test_atlas_references_only_canonical_material_ids(self):
        material_ids = {material["id"] for material in self.data["materials"]}
        for surface in self.data["atlas"]["failureSurfaces"]:
            self.assertTrue(set(surface["materialIds"]).issubset(material_ids))
        for reading_path in self.data["atlas"]["readingPaths"]:
            self.assertTrue(set(reading_path["materialIds"]).issubset(material_ids))

    def test_read_depth_cannot_drop_required_evidence_layers(self):
        invalid = copy.deepcopy(self.data)
        del invalid["materials"][0]["argumentMap"]
        with self.assertRaisesRegex(ValueError, "read/worked entry missing rich fields"):
            self.validate_copy(invalid)

    def test_public_test_contribution_requires_reproducible_fields(self):
        valid = copy.deepcopy(self.data)
        valid["materials"][0]["contributions"] = [{
            "type": "public-test",
            "title": "Synthetic label perturbation",
            "byline": "Example contributor",
            "date": "2026-08-13",
            "basis": "A paper-facing stress test of serialized state roles.",
            "boundary": "This does not reproduce the paper or validate a production system.",
            "method": "Hold candidates fixed and permute state labels.",
            "environment": "Static public fixture and a documented local model.",
            "fixture": "Synthetic current, historical, and transition records.",
            "controls": "A no-label baseline and a shuffled-label condition.",
            "rawResult": "Public per-case outputs.",
            "derivedResult": "Aggregate wrong-state intrusion rate.",
            "limitations": "Synthetic scope only.",
            "links": [{"label": "artifact", "url": "https://example.org/artifact"}],
        }]
        self.validate_copy(valid)

        invalid = copy.deepcopy(valid)
        del invalid["materials"][0]["contributions"][0]["rawResult"]
        with self.assertRaisesRegex(ValueError, "invalid fields"):
            self.validate_copy(invalid)

        no_artifact = copy.deepcopy(valid)
        no_artifact["materials"][0]["contributions"][0]["links"] = []
        with self.assertRaisesRegex(ValueError, "non-empty list"):
            self.validate_copy(no_artifact)

    def test_contributor_perspective_keeps_byline_and_boundary(self):
        valid = copy.deepcopy(self.data)
        valid["materials"][0]["contributions"] = [{
            "type": "perspective",
            "title": "A distinct reading",
            "byline": "Example contributor",
            "date": "2026-08-13",
            "text": "This critique remains separate from the paper and site editorial voice.",
            "basis": "Table 2 and the public source.",
            "boundary": "An editorial perspective, not a paper result.",
            "links": [],
        }]
        validated = self.validate_copy(valid)
        contribution = validated["materials"][0]["contributions"][0]
        self.assertEqual(contribution["byline"], "Example contributor")
        self.assertIn("not a paper result", contribution["boundary"])


if __name__ == "__main__":
    unittest.main()
