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

    def test_easter_egg_copy_has_one_canonical_source(self):
        easter_egg = self.data["atlas"]["easterEgg"]
        self.assertEqual(
            easter_egg,
            {
                "heroWord": "fails",
                "heroReveal": "lives",
                "aboutLine": "Some memories are worth an architecture.",
                "aboutReveal": "ours is one of them.",
            },
        )
        for relative_path in ("index.html", "assets/app.js"):
            source = (build.ROOT / relative_path).read_text(encoding="utf-8")
            for value in easter_egg.values():
                self.assertNotIn(value, source)

    def test_easter_egg_hero_swap_cannot_reflow(self):
        invalid = copy.deepcopy(self.data)
        invalid["atlas"]["easterEgg"]["heroReveal"] = "persists"
        with self.assertRaisesRegex(ValueError, "equal length"):
            self.validate_copy(invalid)

    def test_icon_family_and_manifest_validate(self):
        build.validate_icon_assets()
        manifest = json.loads((build.ROOT / "site.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["start_url"], "./")
        self.assertEqual(manifest["scope"], "./")

    def test_landing_map_has_no_implicit_surface(self):
        source = (build.ROOT / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("defaultSurfaceId", source)
        self.assertIn("refs.surfaceFocus.hidden = !selected", source)

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
        doyle = by_id["truth-maintenance-system"]
        longmemeval = by_id["longmemeval-v2-experienced-colleague"]
        self.assertEqual(atma["noteDepth"], "read")
        self.assertEqual(insightemb["noteDepth"], "read")
        self.assertEqual(doyle["noteDepth"], "read")
        self.assertEqual(longmemeval["noteDepth"], "read")
        current_skim_ids = {
            "trustmem-consolidation", "verifiable-memory", "mosaic-long-term-memory",
            "proactive-wake-anchor", "pm-bench", "mistake-notebook-learning",
            "coala-cognitive-architecture", "storage-to-experience",
            "continual-learning-experience-reuse", "agentic-memory", "midca-dual-cycle",
            "agm-theory-change", "memory-beyond-recall",
        }
        self.assertTrue(all(by_id[material_id]["noteDepth"] == "skim" for material_id in current_skim_ids))
        for material in (atma, insightemb, doyle, longmemeval):
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
        self.assertEqual(doyle["editorialInferences"][1]["label"], "Abstraction lifecycle is a separate contract")
        self.assertEqual(longmemeval["editorialInferences"][0]["label"], "A context package is an authored evidence object")

    def test_sparse_records_remain_valid_without_invented_richer_fields(self):
        validated = self.validate_copy(copy.deepcopy(self.data))
        agm = next(
            material for material in validated["materials"]
            if material["id"] == "agm-theory-change"
        )
        self.assertNotIn("reportedFindings", agm)
        self.assertNotIn("evidenceLimits", agm)
        self.assertNotIn("editorialInferences", agm)

    def test_doyle_public_test_links_checked_in_artifacts(self):
        doyle = next(
            material for material in self.data["materials"]
            if material["id"] == "truth-maintenance-system"
        )
        contribution = doyle["contributions"][0]
        self.assertEqual(contribution["type"], "public-test")
        self.assertEqual(contribution["byline"], "Agent Memory Study editors")
        linked_names = {link["url"].rsplit("/", 1)[-1] for link in contribution["links"]}
        self.assertEqual(linked_names, {"README.md", "oracle.py", "RESULTS.txt"})
        artifact_root = build.ROOT / "research" / "doyle-tms-static-oracle"
        self.assertTrue(all((artifact_root / name).is_file() for name in linked_names))

    def test_longmemeval_public_test_links_checked_in_artifacts(self):
        material = next(
            item for item in self.data["materials"]
            if item["id"] == "longmemeval-v2-experienced-colleague"
        )
        contribution = material["contributions"][0]
        self.assertEqual(contribution["type"], "public-test")
        self.assertEqual(contribution["byline"], "Agent Memory Study editors")
        linked_names = {link["url"].rsplit("/", 1)[-1] for link in contribution["links"]}
        self.assertEqual(linked_names, {"README.md", "audit.py", "decision.json", "reader_contexts.jsonl"})
        artifact_root = build.ROOT / "research" / "longmemeval-v2-boundary-audit"
        self.assertTrue((artifact_root / "README.md").is_file())
        self.assertTrue((artifact_root / "audit.py").is_file())
        self.assertTrue((artifact_root / "raw" / "decision.json").is_file())
        self.assertTrue((artifact_root / "raw" / "reader_contexts.jsonl").is_file())
        decision = json.loads((artifact_root / "raw" / "decision.json").read_text(encoding="utf-8"))
        self.assertFalse(decision["answer_evidence_binding_property_passed"])
        self.assertEqual(decision["failing_pattern_count"], 6)
        self.assertEqual(decision["failing_row_count"], 12)
        self.assertNotIn("provenance_precision", decision)
        query_boundary = json.loads(
            (artifact_root / "raw" / "query_boundary.json").read_text(encoding="utf-8")
        )
        self.assertTrue(query_boundary["all_checks_passed"])
        self.assertEqual(query_boundary["check_count"], 16)
        manifest = json.loads(
            (artifact_root / "raw" / "run_manifest.json").read_text(encoding="utf-8")
        )
        self.assertIn("memory_modules/agentrunbook_c.py", manifest["source_file_hashes"])
        self.assertIn("memory_modules/trajectory_store.py", manifest["source_file_hashes"])

    def test_longmemeval_alias_order_census_is_checked_in_and_held(self):
        material = next(
            item for item in self.data["materials"]
            if item["id"] == "longmemeval-v2-experienced-colleague"
        )
        contribution = material["contributions"][1]
        self.assertEqual(contribution["type"], "public-test")
        self.assertEqual(contribution["byline"], "Agent Memory Study editors")
        linked_names = {link["url"].rsplit("/", 1)[-1] for link in contribution["links"]}
        self.assertEqual(
            linked_names,
            {
                "README.md", "PREREGISTRATION.md", "decision.json",
                "selected_families.json", "protocol_ledger.json",
            },
        )
        artifact_root = build.ROOT / "research" / "longmemeval-v2-alias-order-preregistration"
        self.assertTrue((artifact_root / "README.md").is_file())
        self.assertTrue((artifact_root / "PREREGISTRATION.md").is_file())
        self.assertTrue((artifact_root / "raw" / "decision.json").is_file())
        self.assertTrue((artifact_root / "raw" / "selection" / "selected_families.json").is_file())
        self.assertTrue((artifact_root / "raw" / "protocol_ledger.json").is_file())
        self.assertTrue((artifact_root / "raw" / "runtime_attestation.json").is_file())
        decision = json.loads((artifact_root / "raw" / "decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["eligible_question_count"], 422)
        self.assertEqual(decision["excluded_question_count"], 29)
        self.assertEqual(decision["selected_exact_class_count"], 3)
        self.assertEqual(decision["selected_question_count"], 6)
        self.assertEqual(decision["selected_domains"], ["web"])
        self.assertEqual(decision["selected_base_types"], ["procedure"])
        self.assertEqual(decision["selected_small_length"], 100)
        self.assertTrue(decision["all_selected_small_arrays_equal"])
        self.assertTrue(decision["renderer_erases_filesystem_materialization_order_reversal"])
        self.assertTrue(decision["rank_preserving_alias_preserves_tie_order"])
        self.assertTrue(decision["non_rank_preserving_alias_can_change_tie_order"])
        self.assertTrue(decision["preseeded_summary_order_surface_passed"])
        self.assertEqual(decision["runtime_evidence_kind"], "author_recorded_local_preflight_observation")
        self.assertFalse(decision["runtime_observation_replayed_by_artifact"])
        self.assertEqual(decision["planned_controller_jobs"], 66)
        self.assertEqual(decision["controller_jobs_released_by_protocol"], 0)
        self.assertEqual(decision["controller_jobs_executed"], 0)
        self.assertEqual(decision["controller_phase"], "HOLD")
        protocol = json.loads((artifact_root / "raw" / "protocol_ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(len(protocol["medium_treatments"]), 3)
        self.assertEqual(len(protocol["small_treatment"]["official_order"]), 100)
        self.assertEqual(len(protocol["jobs"]), 66)
        self.assertEqual(len(protocol["execution_order"]), 66)
        self.assertEqual(len(set(protocol["execution_order"])), 66)
        repeat_cells = [item["cell"] for item in protocol["repeat_allocation"]]
        self.assertEqual({cell: repeat_cells.count(cell) for cell in set(repeat_cells)}, {
            "C00": 3, "C10": 3, "C01": 3, "C11": 3,
        })
        self.assertIn("network isolation", " ".join(protocol["unreleased_gates"]))

    def test_public_research_tree_has_no_build_residue(self):
        research_root = build.ROOT / "research"
        residue = [
            path.relative_to(build.ROOT).as_posix()
            for path in research_root.rglob("*")
            if path.is_file()
            and (
                "__pycache__" in path.parts
                or path.suffix.lower() in {".pyc", ".pyo", ".log", ".tmp"}
                or path.name == ".DS_Store"
            )
        ]
        self.assertEqual(residue, [])

    def test_alias_audit_rebuild_is_output_root_scoped_and_comparable(self):
        source = (
            build.ROOT / "research" / "longmemeval-v2-alias-order-preregistration" / "audit.py"
        ).read_text(encoding="utf-8")
        self.assertIn('(output_root / "RESULTS.txt").write_text', source)
        self.assertIn("write_checksums(output_root)", source)
        self.assertNotIn('(ARTIFACT_ROOT / "RESULTS.txt").write_text', source)
        self.assertIn("compare_checked(args.output_dir.resolve())", source)
        self.assertIn("checksum manifest file set is incomplete or contains extras", source)

    def test_public_research_artifacts_are_in_boundary_scan(self):
        relative_paths = {path.relative_to(build.ROOT).as_posix() for path in build.public_copy_paths()}
        self.assertIn("research/doyle-tms-static-oracle/oracle.py", relative_paths)
        self.assertIn("research/doyle-tms-static-oracle/RESULTS.txt", relative_paths)
        self.assertIn("research/doyle-tms-static-oracle/README.md", relative_paths)
        self.assertIn("research/longmemeval-v2-boundary-audit/audit.py", relative_paths)
        self.assertIn("research/longmemeval-v2-boundary-audit/raw/decision.json", relative_paths)
        self.assertIn("research/longmemeval-v2-boundary-audit/raw/reader_contexts.jsonl", relative_paths)
        self.assertIn("research/longmemeval-v2-alias-order-preregistration/audit.py", relative_paths)
        self.assertIn(
            "research/longmemeval-v2-alias-order-preregistration/raw/decision.json",
            relative_paths,
        )
        self.assertIn(
            "research/longmemeval-v2-alias-order-preregistration/raw/selection/selected_families.json",
            relative_paths,
        )
        self.assertIn(
            "research/longmemeval-v2-alias-order-preregistration/raw/protocol_ledger.json",
            relative_paths,
        )
        self.assertIn(
            "research/longmemeval-v2-alias-order-preregistration/raw/runtime_attestation.json",
            relative_paths,
        )
        build.validate_public_copy_files()

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

    def test_private_project_mapping_copy_is_rejected(self):
        invalid = copy.deepcopy(self.data)
        invalid["materials"][0]["editorialQuestion"] = (
            "Private project mapping from internal source inspection"
        )
        with self.assertRaisesRegex(ValueError, "private token"):
            self.validate_copy(invalid)

    def test_public_test_local_path_is_rejected(self):
        doyle = next(
            material for material in copy.deepcopy(self.data["materials"])
            if material["id"] == "truth-maintenance-system"
        )
        doyle["contributions"][0]["environment"] = "Ran at /Users/private/research"
        with self.assertRaisesRegex(ValueError, "private token"):
            build.assert_public_text(doyle)

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
