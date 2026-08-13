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
        self.assertEqual(len(validated["materials"]), 16)

    def test_pdf_delivery_counts_and_exact_allowlist(self):
        bundled = [
            material for material in self.data["materials"]
            if material["pdf"]["delivery"] == "bundled"
        ]
        official = [
            material for material in self.data["materials"]
            if material["pdf"]["delivery"] == "official"
        ]
        self.assertEqual(len(bundled), 9)
        self.assertEqual(len(official), 7)
        self.assertEqual(
            {material["pdf"]["url"] for material in bundled},
            {
                path.relative_to(build.ROOT).as_posix()
                for path in (build.ROOT / "papers").glob("*.pdf")
            },
        )

    def test_atma_is_the_only_new_richer_read_pilot(self):
        by_id = {material["id"]: material for material in self.data["materials"]}
        atma = by_id["a-tma-state-aware-memory"]
        insightemb = by_id["insightemb-action-intent-retrieval"]
        self.assertEqual(atma["noteDepth"], "read")
        self.assertEqual(insightemb["noteDepth"], "read")
        self.assertEqual(
            [material["id"] for material in self.data["materials"] if material["noteDepth"] == "skim"],
            [material["id"] for material in self.data["materials"] if material["id"] not in {atma["id"], insightemb["id"]}],
        )
        self.assertTrue(atma["reportedFindings"])
        self.assertTrue(atma["evidenceLimits"])
        self.assertEqual(atma["editorialInferences"][0]["label"], "Read-side label amplification")
        self.assertNotIn("reportedFindings", insightemb)
        self.assertNotIn("evidenceLimits", insightemb)

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

    def test_private_runtime_copy_is_rejected(self):
        invalid = copy.deepcopy(self.data)
        invalid["materials"][0]["editorialQuestion"] = "Private runtime probe and offline probe"
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


if __name__ == "__main__":
    unittest.main()
