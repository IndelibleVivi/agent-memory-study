"""Negative controls for the public saved-evidence contract, using no raw data."""
from pathlib import Path
import json
import shutil
import tempfile
import unittest

import check_saved


class SavedEvidenceContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = Path(__file__).resolve().parent
        for name in check_saved.REQUIRED | {"receipt.json"}:
            shutil.copyfile(source/name, self.root/name)

    def edit_json(self, name, change, refresh_hash=False):
        path = self.root/name
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value, indent=2)+"\n")
        if refresh_hash:
            self.edit_json("receipt.json", lambda receipt: receipt["artifacts"].__setitem__(name, check_saved.sha(path)))

    def test_saved_package_passes_with_explicit_limited_scope(self):
        result = check_saved.check(self.root)
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["upstream_rows_replayed"])
        self.assertFalse(result["confidence_intervals_recomputed"])
        self.assertFalse(result["new_model_inference"])

    def test_changed_artifact_is_detected_before_interpretation(self):
        with (self.root/"research-note.md").open("a") as stream:
            stream.write("\nChanged outside receipt.\n")
        with self.assertRaisesRegex(check_saved.ContractError, "Artifact changed"):
            check_saved.check(self.root)

    def test_rehashed_wrong_formula_still_fails(self):
        self.edit_json("results.json", lambda result: result["strata"]["BEARING"].__setitem__("identity_reconstruction", 0.0), refresh_hash=True)
        with self.assertRaisesRegex(check_saved.ContractError, "Opportunity identity mismatch"):
            check_saved.check(self.root)

    def test_rehashed_figure_drift_still_fails(self):
        self.edit_json("figure-data.json", lambda figure: figure["right_panel"]["curves"][0]["points"][0].__setitem__(1, 0.9), refresh_hash=True)
        with self.assertRaisesRegex(check_saved.ContractError, "Figure data"):
            check_saved.check(self.root)

    def test_receipt_cannot_promote_offline_check_to_raw_replay(self):
        self.edit_json("receipt.json", lambda receipt: receipt["offline_check"].__setitem__("upstream_row_replay", True))
        with self.assertRaisesRegex(check_saved.ContractError, "must not claim upstream replay"):
            check_saved.check(self.root)

    def test_input_identity_drift_is_rejected_even_after_rehash(self):
        self.edit_json("results.json", lambda result: result["inputs"][0].__setitem__("sha256", "0"*64), refresh_hash=True)
        with self.assertRaisesRegex(check_saved.ContractError, "Public input identity mismatch"):
            check_saved.check(self.root)


if __name__ == "__main__":
    unittest.main()
