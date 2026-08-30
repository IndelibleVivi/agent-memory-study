import copy
import hashlib
import json
import os
import subprocess
import sys
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

    def test_material_payload_cache_key_tracks_current_projection(self):
        source = (build.ROOT / "index.html").read_text(encoding="utf-8")
        self.assertEqual(
            source.count('assets/materials-data.js?v=20260830-mnl-1'),
            1,
        )
        self.assertNotIn('assets/materials-data.js?v=20260829-memprobe-1', source)

    def test_article_copy_wraps_unbroken_evidence_tokens(self):
        css = (build.ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        self.assertRegex(
            css,
            r"(?s)\.article-main\s*\{[^}]*overflow-wrap:\s*anywhere;",
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

    def test_only_approved_cloudflare_web_analytics_beacon_is_present(self):
        build.validate_public_copy_files()
        source = (build.ROOT / "index.html").read_text(encoding="utf-8")
        self.assertEqual(source.count(build.CLOUDFLARE_WEB_ANALYTICS_SRC), 1)
        self.assertEqual(source.count(build.CLOUDFLARE_WEB_ANALYTICS_TOKEN), 1)
        self.assertIn('<script type="module"', source)

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

    def test_reader_copy_matches_canonical_delivery_counts(self):
        total = len(self.data["materials"])
        bundled = sum(
            material["pdf"]["delivery"] == "bundled"
            for material in self.data["materials"]
        )
        official = sum(
            material["pdf"]["delivery"] == "official"
            for material in self.data["materials"]
        )
        readme = (build.ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            f"{total} 份 canonical materials：{bundled} 份按原许可随站提供的 PDF，"
            f"另 {official} 份从 reader 直达 official full text",
            readme,
        )
        self.assertIn(
            f"{total} 份 canonical materials 中，{bundled} 篇有明确的 `CC BY 4.0` "
            f"或 `CC BY-NC-SA 4.0` 许可",
            readme,
        )
        self.assertIn(
            f"另 {official} 篇只链接作者、publisher、arXiv 或 institutional repository "
            "的 official full text",
            readme,
        )

        notice = (build.ROOT / "NOTICE.md").read_text(encoding="utf-8")
        self.assertIn(
            f"- {bundled} unmodified PDFs are redistributed",
            notice,
        )
        self.assertIn(
            f"- {official} other full texts are linked",
            notice,
        )

        zotero_import = (build.ROOT / "ZOTERO-IMPORT.md").read_text(encoding="utf-8")
        self.assertIn(
            f"{total} top-level bibliographic items with {total} attachments",
            zotero_import,
        )
        self.assertIn(
            f"- {bundled} stored PDFs copied into Zotero storage",
            zotero_import,
        )
        self.assertIn(
            f"- {official} linked official PDF URLs",
            zotero_import,
        )
        self.assertIn(
            f"relative paths for the {bundled} bundled files",
            zotero_import,
        )

    def test_memora_worked_essay_keeps_paper_source_and_audit_boundaries_separate(self):
        material = next(
            item for item in self.data["materials"]
            if item["id"] == "memora-from-recall-to-forgetting"
        )
        self.assertEqual(material["noteDepth"], "worked")
        self.assertEqual(material["doi"], "10.48550/arXiv.2604.20006")
        self.assertEqual(material["sourceUrl"], "https://arxiv.org/abs/2604.20006v1")
        self.assertEqual(
            material["pdf"],
            {
                "delivery": "official",
                "url": "https://arxiv.org/pdf/2604.20006v1",
                "accessNote": "本站不重新分发这份 PDF；请从 arXiv official source 阅读 v1。",
            },
        )
        self.assertEqual(set(material["categories"]), {"可靠性", "信念修正"})
        self.assertEqual(
            set(material["failureSurfaces"]),
            {"write-consolidation", "justification-revision"},
        )
        self.assertIn("28 个 physical PDF pages", material["readingScope"])
        self.assertIn("current official source 是 post-paper successor", material["readingScope"])
        self.assertIn("没有重建 Table 3", material["readingScope"])
        for field in (
            "whyRead", "argumentMap", "methodNotes", "reportedFindings", "evidenceLimits",
            "sourceTensions", "editorialInferences", "openProtocols",
        ):
            self.assertTrue(material[field])
        self.assertTrue(all(
            protocol["status"] == "proposed-not-run"
            for protocol in material["openProtocols"]
        ))
        self.assertTrue(any(
            "Table 3" in limit and "source revision" in limit
            for limit in material["evidenceLimits"]
        ))
        self.assertTrue(any(
            "全部 200 个 Reasoning questions" in tension["observation"]
            for tension in material["sourceTensions"]
        ))
        atlas_memberships = {
            surface["id"]
            for surface in self.data["atlas"]["failureSurfaces"]
            if material["id"] in surface["materialIds"]
        }
        self.assertEqual(atlas_memberships, set(material["failureSurfaces"]))

    def test_worked_entries_have_a_public_test_artifact(self):
        for material in self.data["materials"]:
            if material["noteDepth"] != "worked":
                continue
            self.assertTrue(
                any(
                    contribution["type"] == "public-test"
                    for contribution in material.get("contributions", [])
                ),
                f"worked material lacks public-test artifact: {material['id']}",
            )

    def test_mnl_worked_close_read_keeps_paper_and_current_source_separate(self):
        material = next(
            item for item in self.data["materials"]
            if item["id"] == "mistake-notebook-learning"
        )
        self.assertEqual(material["number"], 7)
        self.assertEqual(material["noteDepth"], "worked")
        self.assertEqual(material["doi"], "10.18653/v1/2026.findings-acl.719")
        self.assertEqual(
            material["sourceUrl"],
            "https://aclanthology.org/2026.findings-acl.719/",
        )
        self.assertEqual(
            material["pdf"],
            {
                "delivery": "bundled",
                "url": "papers/07-su-2026-mistake-notebook-learning.pdf",
                "originalUrl": "https://aclanthology.org/2026.findings-acl.719.pdf",
                "license": "CC BY 4.0",
                "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
            },
        )
        self.assertIn("17 个 physical PDF pages", material["readingScope"])
        self.assertIn("Appendices A–D", material["readingScope"])
        self.assertIn(
            "dc7de755522ad58864c62b74ab8e9959c01b7f23",
            material["readingScope"],
        )
        self.assertIn("paper-production source", material["readingScope"])
        self.assertEqual(
            set(material["failureSurfaces"]),
            {
                "write-consolidation",
                "retrieval-active-context",
                "abstraction-experience",
            },
        )
        atlas_memberships = {
            surface["id"]
            for surface in self.data["atlas"]["failureSurfaces"]
            if material["id"] in surface["materialIds"]
        }
        self.assertEqual(atlas_memberships, set(material["failureSurfaces"]))
        for field in (
            "whyRead", "argumentMap", "methodNotes", "reportedFindings", "evidenceLimits",
            "sourceTensions", "editorialInferences", "openProtocols", "contributions",
        ):
            self.assertTrue(material[field])
        self.assertTrue(all(
            protocol["status"] == "proposed-not-run"
            for protocol in material["openProtocols"]
        ))

        contribution = next(
            item for item in material["contributions"]
            if item["type"] == "public-test"
        )
        self.assertEqual(contribution["byline"], "Agent Memory Study editors")
        self.assertIn("not an MNL benchmark or paper-experiment rerun", contribution["boundary"])
        self.assertIn("Missing updated items remain unavailable observations", contribution["boundary"])
        self.assertIn("full-cohort, per-item, subgroup, held-out", contribution["boundary"])
        self.assertIn("source-to-paper reproduction", contribution["boundary"])

        prefix = "research/mnl-promotion-cohort-audit/"
        linked_paths = {
            link["url"].split("/blob/main/", 1)[1]
            for link in contribution["links"]
        }
        self.assertEqual(
            linked_paths,
            {
                f"{prefix}README.md",
                f"{prefix}PROTOCOL.md",
                f"{prefix}audit.py",
                f"{prefix}verify_checked.py",
                f"{prefix}raw/cases.json",
                f"{prefix}raw/run_results.jsonl",
                f"{prefix}raw/decision.json",
                f"{prefix}raw/source_manifest.json",
                f"{prefix}raw/mutation_controls.json",
                f"{prefix}raw/comparison.json",
            },
        )
        self.assertTrue(all((build.ROOT / path).is_file() for path in linked_paths))

    def test_mnl_checked_package_inventory_checksums_and_privacy(self):
        artifact_root = build.ROOT / "research" / "mnl-promotion-cohort-audit"
        expected_files = {
            "PROTOCOL.md",
            "README.md",
            "audit.py",
            "checksums.sha256",
            "raw/cases.json",
            "raw/comparison.json",
            "raw/decision.json",
            "raw/environment_run_a.json",
            "raw/environment_run_b.json",
            "raw/mutation_controls.json",
            "raw/public_safety.json",
            "raw/run_results.jsonl",
            "raw/source_manifest.json",
            "verify_checked.py",
        }
        observed_files = {
            path.relative_to(artifact_root).as_posix()
            for path in artifact_root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(observed_files, expected_files)

        checksum_rows = (
            artifact_root / "checksums.sha256"
        ).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(checksum_rows), 13)
        checksums = {}
        for row in checksum_rows:
            digest, separator, relative_path = row.partition("  ")
            self.assertEqual(separator, "  ")
            self.assertEqual(len(digest), 64)
            self.assertNotIn(relative_path, checksums)
            checksums[relative_path] = digest
        self.assertEqual(
            set(checksums),
            expected_files - {"checksums.sha256"},
        )
        for relative_path, expected_digest in checksums.items():
            self.assertEqual(
                hashlib.sha256((artifact_root / relative_path).read_bytes()).hexdigest(),
                expected_digest,
                relative_path,
            )

        slash = b"/"
        denied_markers = (
            slash + b"Users" + slash,
            slash + b"Volumes" + slash,
            b"file" + b"://",
            b"Zotero" + slash + b"storage",
            b"@" + b"chatroom",
            b"wxid" + b"_",
            b"BEGIN " + b"PRIVATE KEY",
            b"sk" + b"-",
            b"ghp" + b"_",
            b"github" + b"_pat_",
            b"OPENAI" + b"_API_KEY=",
            b"ANTHROPIC" + b"_API_KEY=",
        )
        for relative_path in sorted(expected_files):
            payload = (artifact_root / relative_path).read_bytes()
            for marker in denied_markers:
                self.assertNotIn(marker, payload, f"{relative_path}: {marker!r}")

        manifest = json.loads(
            (artifact_root / "raw" / "source_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["schema"], "mnl-source-manifest/2")
        self.assertEqual(
            manifest["source"]["runner_declared_source_code_read_allowlist"],
            [
                {
                    "git_blob": "2a39b9d8921760476b3f2ae2f2d1397fcadb163a",
                    "path": "mnl/trainer.py",
                    "sha256": "398ef9fc98ef418454cc3c243c762a65ee733cf687b94c16e80b92a6b4ce6033",
                },
                {
                    "git_blob": "be97b6e6da5157e1e7c3501961b6fad4b7d2a542",
                    "path": "mnl/evaluator.py",
                    "sha256": "47d429f2962b0423ce2a48dfaf3910d5ce2efcaacc9e69018912b3a963a90347",
                },
                {
                    "git_blob": "50483b9a18d97ef743993644f657f982a95a3d59",
                    "path": "mnl/knowledge_base.py",
                    "sha256": "c4a62fd6b47b8ca4bd6a8265b1d218fedd3e67f5cdd52a27668ef89fd64116c5",
                },
            ],
        )
        self.assertFalse(manifest["source"]["read_access_instrumented"])
        self.assertFalse(manifest["source"]["upstream_source_copied_into_artifact"])
        self.assertEqual(
            manifest["checkout_observations"],
            {
                "allowlisted_bytes_match_lock_after": True,
                "allowlisted_bytes_match_lock_before": True,
                "git_status_clean_after": True,
                "git_status_clean_before": True,
                "transient_or_ignored_writes_instrumented": False,
            },
        )
        safety = json.loads(
            (artifact_root / "raw" / "public_safety.json").read_text(encoding="utf-8")
        )
        self.assertEqual(safety["schema"], "mnl-public-safety/1")
        self.assertTrue(safety["no_local_paths_credentials_or_upstream_source"])
        self.assertFalse(safety["copied_upstream_source"])
        self.assertEqual(safety["denied_content_hits"], [])
        self.assertEqual(
            safety["scan_scope"],
            [
                "cases.json",
                "decision.json",
                "mutation_controls.json",
                "run_results.jsonl",
                "source_manifest.json",
            ],
        )

    def test_mnl_receipts_bind_cohort_conservation_and_claim_ceiling(self):
        raw_root = (
            build.ROOT / "research" / "mnl-promotion-cohort-audit" / "raw"
        )
        cases = json.loads((raw_root / "cases.json").read_text(encoding="utf-8"))
        rows = [
            json.loads(line)
            for line in (raw_root / "run_results.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(cases["schema"], "mnl-promotion-cases/1")
        self.assertEqual(
            [case["id"] for case in cases["batch_cases"]],
            [
                "complete_positive_accept",
                "complete_balanced_reject",
                "complete_all_ties_reject",
                "partial_updated_none_survivor_accept",
                "partial_empty_prompt_survivor_accept",
                "all_updated_prompts_empty_rollback",
                "all_updated_responses_none_rollback",
                "net_accept_with_group_loss",
            ],
        )
        self.assertEqual(
            [probe["id"] for probe in cases["probes"]],
            [
                "exact_subject_equal_embedding_top1",
                "all_failed_question_denominator",
                "socket_network_guard",
            ],
        )
        self.assertEqual(sum(len(case["items"]) for case in cases["batch_cases"]), 29)
        self.assertEqual(len(rows), 11)
        indexed = {
            (row["kind"], row.get("case_id", row.get("id"))): row
            for row in rows
        }
        self.assertEqual(len(indexed), len(rows))

        partial_ids = {
            "partial_updated_none_survivor_accept",
            "partial_empty_prompt_survivor_accept",
        }
        all_missing_ids = {
            "all_updated_prompts_empty_rollback",
            "all_updated_responses_none_rollback",
        }
        for case in cases["batch_cases"]:
            row = indexed[("batch_promotion", case["id"])]
            ledger = row["identity_ledger"]
            original_ids = [item["id"] for item in case["items"]]
            prompt_ids = [
                item["id"] for item in case["items"]
                if item["updated_prompt"] == "nonempty"
            ]
            response_ids = [
                item["id"] for item in case["items"]
                if item["updated_prompt"] == "nonempty"
                and item["updated_response"] != "none"
            ]
            self.assertEqual(ledger["original_ids"], original_ids)
            self.assertEqual(ledger["baseline_valid_ids"], original_ids)
            self.assertEqual(ledger["updated_prompt_nonempty_ids"], prompt_ids)
            self.assertEqual(ledger["updated_generation_ids"], prompt_ids)
            self.assertEqual(ledger["updated_response_valid_ids"], response_ids)
            self.assertEqual(ledger["evaluated_ids"], response_ids)
            self.assertEqual(set(ledger["dispositions"]), set(original_ids))
            self.assertTrue(set(response_ids) <= set(prompt_ids) <= set(original_ids))

            outcomes = [
                item["observed_outcome_if_evaluated"]
                for item in case["items"]
                if item["id"] in response_ids
            ]
            wins = outcomes.count("win")
            losses = outcomes.count("loss")
            ties = outcomes.count("tie")
            admission = row["admission"]
            self.assertEqual(admission["source_observed_wins"], wins)
            self.assertEqual(admission["source_observed_losses"], losses)
            self.assertEqual(admission["source_observed_ties"], ties)
            self.assertEqual(admission["source_observed_delta"], wins - losses)
            self.assertIs(admission["source_accepted"], case["expected_source_acceptance"])
            self.assertEqual(
                row["missing_as_failure_sensitivity"]["missing_count"],
                len(original_ids) - len(response_ids),
            )
            self.assertTrue(
                row["missing_as_failure_sensitivity"]["not_observed_source_outcomes"]
            )
            if case["id"] in partial_ids:
                self.assertTrue(admission["source_accepted"])
                self.assertEqual(
                    admission["full_enrolled_decision"],
                    "UNDEFINED_FROM_OBSERVED_RESULTS",
                )
            if case["id"] in all_missing_ids:
                self.assertFalse(admission["source_accepted"])
                self.assertEqual(row["source_return"], "NONE")
                self.assertEqual(ledger["evaluated_ids"], [])
            if admission["source_accepted"]:
                self.assertEqual(row["kb_state"]["in_memory_delta"], 1)
                self.assertTrue(row["kb_state"]["accepted_entry_exact"])
            else:
                self.assertEqual(row["kb_state"]["in_memory_delta"], 0)
                self.assertEqual(
                    row["kb_state"]["in_memory_post_sha256"],
                    row["kb_state"]["in_memory_pre_sha256"],
                )
                self.assertEqual(
                    row["kb_state"]["serialized_post_sha256"],
                    row["kb_state"]["serialized_pre_sha256"],
                )

        self.assertTrue(
            indexed[("batch_promotion", "complete_positive_accept")]["admission"]
            ["source_accepted"]
        )
        self.assertFalse(
            indexed[("batch_promotion", "complete_balanced_reject")]["admission"]
            ["source_accepted"]
        )
        self.assertFalse(
            indexed[("batch_promotion", "complete_all_ties_reject")]["admission"]
            ["source_accepted"]
        )
        subgroup = indexed[("batch_promotion", "net_accept_with_group_loss")]
        self.assertTrue(subgroup["admission"]["source_accepted"])
        self.assertEqual(subgroup["group_observed_deltas"], {"A": 3, "B": -1})

        knowledge_base = indexed[("knowledge_base", "exact_subject_equal_embedding_top1")]
        self.assertEqual(knowledge_base["entry_count_before"], 1)
        self.assertEqual(knowledge_base["entry_count_after"], 2)
        self.assertEqual(knowledge_base["exact_subject_count_after"], 2)
        self.assertEqual(knowledge_base["top1_guidance"], "older-guidance")
        evaluation = indexed[("evaluation_coverage", "all_failed_question_denominator")]
        self.assertEqual(evaluation["enrolled_count"], 2)
        self.assertEqual(evaluation["surviving_question_count"], 1)
        self.assertEqual(evaluation["source_reported_accuracy"], 1.0)
        self.assertEqual(evaluation["enrolled_coverage"], 0.5)
        self.assertTrue(evaluation["all_failed_question_omitted_from_denominator"])
        self.assertEqual(indexed[("runtime_guard", "socket_network_guard")]["attempts"], 0)

        decision = json.loads((raw_root / "decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["schema"], "mnl-promotion-decision/1")
        self.assertEqual(decision["batch_case_count"], 8)
        self.assertEqual(
            decision["incomplete_survivor_admissions"],
            [
                "partial_updated_none_survivor_accept",
                "partial_empty_prompt_survivor_accept",
            ],
        )
        self.assertEqual(
            decision["full_cohort_status_for_filtered_admissions"],
            "UNDEFINED_FROM_OBSERVED_RESULTS",
        )
        self.assertEqual(
            decision["subgroup_non_regression_guarantee"],
            "NOT_ESTABLISHED_BY_NET_BATCH_ACCEPTANCE",
        )
        self.assertEqual(
            decision["paper_or_benchmark_experiment_reproduction"],
            "NOT_ATTEMPTED",
        )
        self.assertEqual(decision["source_to_paper_revision_binding"], "NOT_ESTABLISHED")
        self.assertEqual(decision["model_or_api_calls"], 0)
        self.assertEqual(
            decision["canonical_ams_status"],
            {"public_note_depth": "not_assessed_by_evidence_artifact"},
        )

    def test_mnl_mutations_repeatability_and_environments_are_checked(self):
        raw_root = (
            build.ROOT / "research" / "mnl-promotion-cohort-audit" / "raw"
        )
        controls = json.loads(
            (raw_root / "mutation_controls.json").read_text(encoding="utf-8")
        )
        expected_controls = {
            "delete_original_identity": "BATCH_ORIGINAL_IDS",
            "flip_source_admission": "BATCH_ACCEPTANCE",
            "relabel_unavailable_as_observed_loss": "BATCH_DISPOSITIONS",
            "alter_rejected_serialized_poststate": "KB_REJECTED_SERIALIZED",
            "change_eval_enrolled_denominator": "EVAL_ENROLLED",
            "replace_stable_top1_with_new_entry": "KB_TOP1",
        }
        self.assertEqual(controls["schema"], "mnl-mutation-controls/1")
        self.assertTrue(controls["all_detected"])
        self.assertEqual(
            {control["id"] for control in controls["controls"]},
            set(expected_controls),
        )
        for control in controls["controls"]:
            self.assertTrue(control["detected"])
            self.assertEqual(
                control["expected_error_code"],
                expected_controls[control["id"]],
            )
            self.assertEqual(
                control["observed_error_code"],
                expected_controls[control["id"]],
            )

        comparison = json.loads(
            (raw_root / "comparison.json").read_text(encoding="utf-8")
        )
        primary_names = {
            "cases.json",
            "decision.json",
            "mutation_controls.json",
            "public_safety.json",
            "run_results.jsonl",
            "source_manifest.json",
        }
        self.assertEqual(comparison["schema"], "mnl-run-comparison/1")
        self.assertTrue(comparison["byte_identical"])
        self.assertEqual(comparison["primary_file_count"], 6)
        self.assertEqual(set(comparison["primary_files"]), primary_names)
        self.assertEqual(comparison["run_a_hash_seed"], "313")
        self.assertEqual(comparison["run_b_hash_seed"], "727")
        self.assertNotEqual(comparison["run_a_hash_seed"], comparison["run_b_hash_seed"])
        for name in primary_names:
            actual_digest = hashlib.sha256((raw_root / name).read_bytes()).hexdigest()
            self.assertEqual(
                comparison["primary_files"][name],
                {
                    "run_a_sha256": actual_digest,
                    "run_b_sha256": actual_digest,
                },
            )

        environment_a = json.loads(
            (raw_root / "environment_run_a.json").read_text(encoding="utf-8")
        )
        environment_b = json.loads(
            (raw_root / "environment_run_b.json").read_text(encoding="utf-8")
        )
        self.assertEqual(environment_a["schema"], "mnl-environment/1")
        self.assertEqual(environment_b["schema"], "mnl-environment/1")
        self.assertEqual(environment_a["run_label"], "A")
        self.assertEqual(environment_b["run_label"], "B")
        self.assertEqual(environment_a["hash_seed"], "313")
        self.assertEqual(environment_b["hash_seed"], "727")
        for environment in (environment_a, environment_b):
            self.assertEqual(environment["timezone"], "UTC")
            self.assertEqual(environment["locale"], "C.UTF-8")
            self.assertEqual(environment["operating_system"], "Darwin")
            self.assertEqual(environment["machine"], "arm64")
            self.assertRegex(environment["python"], r"^3\.13\.")

    def test_mnl_checked_verifier_receipt_only_passes(self):
        verifier = (
            build.ROOT
            / "research"
            / "mnl-promotion-cohort-audit"
            / "verify_checked.py"
        )
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-B", str(verifier), "--mode", "receipt-only"],
            cwd=build.ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(
            completed.stdout,
            "Verified checked receipt inventory, hashes, derivations, controls, "
            "and claim boundary.\n",
        )

    def test_memora_public_audit_is_complete_checked_and_bounded(self):
        material = next(
            item for item in self.data["materials"]
            if item["id"] == "memora-from-recall-to-forgetting"
        )
        contribution = material["contributions"][0]
        self.assertEqual(contribution["type"], "public-test")
        self.assertEqual(contribution["byline"], "Agent Memory Study editors")
        self.assertIn("729 positive-denominator", contribution["method"])
        self.assertIn("55 source-defined zero-bucket", contribution["method"])
        self.assertIn("729 paper-equation-domain", contribution["fixture"])
        self.assertIn("55 separately labeled source zero-bucket", contribution["fixture"])
        self.assertIn("public-safe protocol record was derived after execution", contribution["boundary"])
        self.assertIn("rerun twice under the amended protocol", contribution["boundary"])
        self.assertNotIn("preregistered exact-revision", contribution["boundary"])
        self.assertIn("fresh exact-helper probe", contribution["rawResult"])
        self.assertIn("pre-cached or earlier-path", contribution["rawResult"])
        self.assertIn("single-run completeness", contribution["limitations"])
        self.assertNotIn("Fraction oracle over 784 valid", contribution["rawResult"])
        linked_paths = {
            link["url"].split("/blob/main/", 1)[1]
            for link in contribution["links"]
        }
        self.assertEqual(
            linked_paths,
            {
                "research/memora-forgetting-contract-audit/README.md",
                "research/memora-forgetting-contract-audit/PREREGISTRATION.md",
                "research/memora-forgetting-contract-audit/audit.py",
                "research/memora-forgetting-contract-audit/raw/decision.json",
                "research/memora-forgetting-contract-audit/raw/census.json",
                "research/memora-forgetting-contract-audit/raw/judge_binding.json",
                "research/memora-forgetting-contract-audit/raw/fama.json",
                "research/memora-forgetting-contract-audit/raw/aggregator.json",
                "research/memora-forgetting-contract-audit/raw/source_manifest.json",
                "research/memora-forgetting-contract-audit/raw/reproduction.json",
            },
        )

        artifact_root = build.ROOT / "research" / "memora-forgetting-contract-audit"
        expected_files = {
            "PREREGISTRATION.md",
            "README.md",
            "audit.py",
            "checksums.sha256",
            "verify_checked.py",
            "raw/aggregator.json",
            "raw/census.json",
            "raw/decision.json",
            "raw/environment.json",
            "raw/fama.json",
            "raw/judge_binding.json",
            "raw/official_pytest.txt",
            "raw/official_tests.json",
            "raw/paper_locator.json",
            "raw/release_boundary.json",
            "raw/reproduction.json",
            "raw/source_manifest.json",
        }
        observed_files = {
            path.relative_to(artifact_root).as_posix()
            for path in artifact_root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(observed_files, expected_files)
        self.assertFalse(any(
            path.name == "__pycache__" or path.suffix in {".pyc", ".pyo", ".tmp", ".log"}
            for path in artifact_root.rglob("*")
        ))

        decision = json.loads(
            (artifact_root / "raw" / "decision.json").read_text(encoding="utf-8")
        )
        self.assertEqual(decision["schema"], "memora-forgetting-contract-audit-decision/3")
        self.assertEqual(decision["verdict"], "PASS")
        self.assertEqual(decision["decision_scope"], "single_run_completeness")
        self.assertEqual(
            decision["package_acceptance_status"],
            "not_evaluated_within_single_run",
        )
        self.assertEqual(len(decision["package_acceptance_requirements"]), 3)
        self.assertTrue(decision["gates"] and all(decision["gates"].values()))
        protocol = decision["protocol_provenance"]
        self.assertEqual(protocol["public_protocol_file"], "PREREGISTRATION.md")
        self.assertEqual(protocol["public_record_timing"], "post_execution")
        self.assertFalse(protocol["private_pretest_source_published"])
        self.assertFalse(protocol["same_day_clock_times_asserted"])
        self.assertEqual(len(protocol["post_execution_amendments"]), 5)
        self.assertTrue(
            protocol["pretest_aggregation_hypothesis_status"].startswith(
                "not_supported_as_exact_source_contract"
            )
        )
        self.assertIn("benchmark reproduction", decision["claim_ceiling"]["not_established"])
        self.assertIn("Table 3 reconstruction or paper-result invalidation", decision["claim_ceiling"]["not_established"])

        official_tests = json.loads(
            (artifact_root / "raw" / "official_tests.json").read_text(encoding="utf-8")
        )
        self.assertEqual(official_tests["schema"], "memora-official-tests/1")
        self.assertEqual(official_tests["passed"], 5)
        self.assertTrue(official_tests["complete"])
        self.assertFalse(official_tests["api_credentials_inherited"])
        for key in ("created_paths", "deleted_paths", "modified_paths", "cache_paths_after"):
            self.assertEqual(official_tests[key], [])

        census = json.loads(
            (artifact_root / "raw" / "census.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            census["totals"],
            {
                "files": 30,
                "questions": 600,
                "criteria": 6415,
                "memory_presence": 2947,
                "forgetting_absence": 3468,
                "zero_forgetting": 204,
                "zero_presence": 0,
            },
        )
        self.assertEqual(census["empty_buckets"]["zero_forgetting_by_task"]["reasoning"], 200)
        self.assertEqual(census["paper_release_census_drift"]["paper_table2_total"], 7054)
        self.assertEqual(census["paper_release_census_drift"]["difference"], 639)
        self.assertEqual(census["identity"]["file_local_question_duplicates"], 0)
        self.assertEqual(census["identity"]["file_local_criterion_duplicates"], 0)
        self.assertEqual(census["identity"]["bare_question_id_collisions"]["groups"], 38)
        self.assertEqual(census["identity"]["bare_criterion_id_collisions"]["groups"], 178)
        self.assertEqual(
            census["identity"]["bare_criterion_id_collisions"]["payload_different_groups"],
            175,
        )
        self.assertEqual(
            census["identity"]["bare_criterion_id_collisions"]["payload_identical_groups"],
            3,
        )

        judges = json.loads(
            (artifact_root / "raw" / "judge_binding.json").read_text(encoding="utf-8")
        )
        self.assertFalse(judges["historical_track2"]["use_multi_judge_after_import_error"])
        current_origin = judges["current_track2_fresh_import_origin"]
        self.assertEqual(
            current_origin["api_client_module_file"],
            "evals/model_eval/api_client.py",
        )
        self.assertEqual(
            current_origin["openrouter_client_source_file"],
            "evals/model_eval/api_client.py",
        )
        self.assertTrue(current_origin["both_origins_match_expected"])
        self.assertFalse(current_origin["fresh_process_api_client_initially_cached"])
        self.assertFalse(current_origin["real_client_constructed"])
        import_mechanics = judges["current_track2_import_mechanics"]
        self.assertEqual(import_mechanics["path_mutation"], "sys.path.append")
        self.assertTrue(import_mechanics["unqualified_import"])
        self.assertTrue(import_mechanics["pre_cached_api_client_can_shadow_expected_module"])
        self.assertTrue(import_mechanics["earlier_sys_path_api_client_can_shadow_expected_module"])
        self.assertTrue(import_mechanics["official_test_asserts_class_name_only"])
        self.assertFalse(import_mechanics["official_test_asserts_source_origin"])
        self.assertEqual(
            [row["accepted"] for row in judges["current_track1_initialization_matrix"]],
            [False, True, True, True],
        )
        track2 = judges["current_track2_initialization_matrix"]
        self.assertEqual(len(track2), 8)
        self.assertTrue(all(
            row["accepted"] == (
                row["requested_successful_clients"] == 3 or not row["strict"]
            )
            for row in track2
        ))
        self.assertEqual(
            [row["num_valid_judges"] for row in judges["runtime_valid_judge_quorum"]["track1"]],
            [0, 1, 2, 3],
        )
        self.assertEqual(
            [row["num_valid_judges"] for row in judges["runtime_valid_judge_quorum"]["track2"]],
            [0, 1, 2, 3],
        )

        fama = json.loads(
            (artifact_root / "raw" / "fama.json").read_text(encoding="utf-8")
        )
        self.assertEqual(fama["schema"], "memora-fama-audit/2")
        matrix = fama["bounded_valid_matrix"]
        self.assertEqual(matrix["source_valid_counter_fixtures"], 784)
        self.assertEqual(matrix["source_valid_function_comparisons"], 1568)
        paper_domain = matrix["paper_equation_domain"]
        self.assertEqual(paper_domain["fixtures"], 729)
        self.assertEqual(paper_domain["function_comparisons"], 1458)
        self.assertFalse(paper_domain["oracle_zero_division_defined"])
        source_extensions = matrix["source_zero_bucket_extensions"]
        self.assertEqual(source_extensions["fixtures"], 55)
        self.assertEqual(source_extensions["function_comparisons"], 110)
        self.assertFalse(source_extensions["paper_defined"])
        self.assertEqual(matrix["bounds_failures"], 0)
        self.assertEqual(matrix["monotonicity_failures"], 0)
        self.assertLessEqual(matrix["maximum_absolute_error"], 1e-12)
        self.assertEqual(fama["released_counter_pair_corners"]["distinct_pairs"], 156)
        self.assertEqual(
            fama["out_of_domain_direct_function_probe"]["track1"],
            1.5,
        )
        self.assertEqual(
            fama["out_of_domain_direct_function_probe"]["track2"],
            1.5,
        )

        aggregator = json.loads(
            (artifact_root / "raw" / "aggregator.json").read_text(encoding="utf-8")
        )
        macro = aggregator["synthetic_fixtures"]["unweighted_report_macro"]
        self.assertEqual(macro["source_aggregate"], 0.5)
        self.assertEqual(macro["question_weighted_control"], 0.9)
        self.assertTrue(aggregator["synthetic_fixtures"]["duplicate_report_rows_retained"])

        release = json.loads(
            (artifact_root / "raw" / "release_boundary.json").read_text(encoding="utf-8")
        )
        self.assertTrue(all(value == 0 for value in release["tracked_inventory"].values()))
        self.assertTrue(all(value == 0 for value in release["reader_checkout_inventory"].values()))
        self.assertFalse(
            release["derived_boundary"]["table3_reconstructable_model_free_from_locked_release"]
        )

        source_manifest = json.loads(
            (artifact_root / "raw" / "source_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(source_manifest["head"], "a6493188efc836d6511ed5e4163fe3ba87da30ff")
        self.assertEqual(source_manifest["direct_parent"], "e19ebbd1089465876dca11b09e70256977f9755f")
        self.assertEqual(source_manifest["worktree_status"], "clean")

        reproduction = json.loads(
            (artifact_root / "raw" / "reproduction.json").read_text(encoding="utf-8")
        )
        self.assertEqual(reproduction["schema"], "memora-audit-reproduction/1")
        self.assertEqual(reproduction["verdict"], "REPRODUCIBLE")
        self.assertTrue(reproduction["byte_identical"])
        self.assertEqual(reproduction["stable_files_compared"], 11)

        checksum_lines = (
            artifact_root / "checksums.sha256"
        ).read_text(encoding="utf-8").splitlines()
        checksummed_paths = set()
        for line in checksum_lines:
            expected, relative = line.split("  ", 1)
            self.assertNotIn(relative, checksummed_paths)
            checksummed_paths.add(relative)
            observed = hashlib.sha256((artifact_root / relative).read_bytes()).hexdigest()
            self.assertEqual(observed, expected)
        self.assertEqual(checksummed_paths, expected_files - {"checksums.sha256"})

    def test_memprobe_worked_audit_keeps_fixed_artifact_and_replay_boundaries(self):
        material = next(
            item for item in self.data["materials"]
            if item["id"] == "memprobe-hidden-user-state-recovery"
        )
        self.assertEqual(material["number"], 21)
        self.assertEqual(material["noteDepth"], "worked")
        self.assertEqual(material["doi"], "10.48550/arXiv.2606.24595")
        self.assertEqual(material["sourceUrl"], "https://arxiv.org/abs/2606.24595v1")
        self.assertEqual(
            material["pdf"],
            {
                "delivery": "official",
                "url": "https://arxiv.org/pdf/2606.24595v1",
                "accessNote": "本站不重新分发这份 PDF；请从 arXiv official source 阅读 reviewed v1。",
            },
        )
        self.assertEqual(set(material["categories"]), {"可靠性", "记忆架构"})
        self.assertEqual(
            set(material["failureSurfaces"]),
            {"state-representation", "retrieval-active-context"},
        )

        atlas_memberships = {
            surface["id"]
            for surface in self.data["atlas"]["failureSurfaces"]
            if material["id"] in surface["materialIds"]
        }
        self.assertEqual(atlas_memberships, set(material["failureSurfaces"]))
        answer_failure_path = next(
            path for path in self.data["atlas"]["readingPaths"]
            if path["id"] == "from-answer-failure"
        )
        self.assertIn(material["id"], answer_failure_path["materialIds"])

        contribution = next(
            item for item in material["contributions"]
            if item["type"] == "public-test"
        )
        self.assertEqual(contribution["byline"], "Agent Memory Study editors")
        self.assertIn("not a MEMPROBE benchmark rerun", contribution["boundary"])
        self.assertRegex(
            contribution["boundary"],
            r"historical .*retriever.* replay",
        )
        self.assertIn("Historical LLM outputs remain historical artifacts", contribution["boundary"])

        prefix = "research/memprobe-recovery-boundary-audit/"
        linked_paths = {
            link["url"].split("/blob/main/", 1)[1]
            for link in contribution["links"]
        }
        self.assertTrue(all(path.startswith(prefix) for path in linked_paths))
        self.assertTrue(
            {
                f"{prefix}README.md",
                f"{prefix}PROTOCOL.md",
                f"{prefix}audit.py",
                f"{prefix}verify_checked.py",
            }.issubset(linked_paths)
        )
        self.assertTrue(all((build.ROOT / path).is_file() for path in linked_paths))

        artifact_root = build.ROOT / prefix
        artifact_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in artifact_root.rglob("*")
            if path.is_file() and path.suffix in {".py", ".md", ".json", ".jsonl"}
        )
        self.assertNotIn("file://", artifact_text)
        self.assertNotIn("/Users/", artifact_text)
        self.assertNotIn("/Volumes/", artifact_text)

        checksum_lines = (artifact_root / "checksums.sha256").read_text(
            encoding="utf-8"
        ).splitlines()
        checksummed_paths = set()
        for line in checksum_lines:
            expected, relative = line.split("  ", 1)
            self.assertNotIn(relative, checksummed_paths)
            checksummed_paths.add(relative)
            observed = hashlib.sha256((artifact_root / relative).read_bytes()).hexdigest()
            self.assertEqual(observed, expected)
        expected_checksummed_paths = {
            path.relative_to(artifact_root).as_posix()
            for path in artifact_root.rglob("*")
            if path.is_file() and path.name != "checksums.sha256"
        }
        self.assertEqual(checksummed_paths, expected_checksummed_paths)

    def test_memprobe_checked_package_binds_decision_population_and_repeatability(self):
        artifact_root = build.ROOT / "research" / "memprobe-recovery-boundary-audit"
        raw = artifact_root / "raw"
        expected_root_files = {
            "NOTICE.md",
            "PROTOCOL.md",
            "README.md",
            "audit.py",
            "checksums.sha256",
            "verify_checked.py",
            "raw",
        }
        self.assertEqual(
            {path.name for path in artifact_root.iterdir()},
            expected_root_files,
        )
        primary_files = {
            "arithmetic.json",
            "attribution_rows.jsonl",
            "cases.json",
            "decision.json",
            "input_manifest.json",
            "microfixture.json",
            "mutation_controls.json",
            "observability.json",
            "packet_items.jsonl",
            "packet_rows.jsonl",
            "paired_deltas.jsonl",
            "public_safety.json",
            "replay_inventory.json",
            "store_census.json",
            "target_joins.jsonl",
            "target_registry.json",
        }
        self.assertEqual(
            {path.name for path in raw.iterdir()},
            primary_files | {
                "comparison.json",
                "environment_run_a.json",
                "environment_run_b.json",
            },
        )

        decision = json.loads((raw / "decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["schema"], "memprobe-fixed-artifact-decision/1")
        self.assertEqual(
            decision["source_commit"],
            "19bb83644b082489b4e181e59f1cded1a00d0529",
        )
        self.assertEqual(
            decision["fixed_artifact_gates"],
            {
                "aggregate_reports": True,
                "attribution_input_linkage": True,
                "attribution_reduction": True,
                "checkout_immutable": True,
                "fixed_score_arithmetic": True,
                "mutation_controls": True,
                "network_guard": True,
                "packet_membership_complete": True,
                "packet_schema": True,
                "public_population": True,
                "target_identity": True,
            },
        )
        self.assertEqual(decision["packet_unique_binding"], "PASS")
        self.assertEqual(
            decision["stored_output_observability"],
            "COMPLETE_TYPED_INVENTORY",
        )
        self.assertEqual(decision["attribution_input_observability"], "PARTIAL")
        self.assertEqual(decision["source_replay_material_status"], "BLOCKED")
        self.assertEqual(decision["historical_execution_replay"], "NOT_ATTEMPTED")
        self.assertEqual(
            decision["worked_fixed_artifact_audit"],
            "SINGLE_RUN_PASS_PENDING_REPEATABILITY_AND_SOURCE_BOUND_REVALIDATION",
        )
        self.assertEqual(
            decision["primary_receipt_cardinalities"],
            {
                "attribution_rows": 13950,
                "packet_items": 30379,
                "packet_rows": 6200,
                "paired_historical_artifact_deltas": 6200,
                "registered_targets": 1550,
                "target_join_rows": 13950,
            },
        )

        registry = json.loads((raw / "target_registry.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["schema"], "memprobe-target-registry/1")
        self.assertEqual(
            registry["categories"],
            {
                "assistance_preference": 5,
                "episodic_memory": 7,
                "knowledge_memory": 7,
                "self_model": 5,
                "skill_memory": 7,
            },
        )
        self.assertEqual(len(registry["users"]), 50)
        self.assertEqual(len(registry["run_registry"]), 9)
        self.assertEqual(len(registry["targets"]), 1550)

        manifest = json.loads((raw / "input_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest), {"inputs", "paper_sha256", "schema", "source_commit"})
        self.assertEqual(manifest["schema"], "memprobe-input-manifest/1")
        self.assertEqual(
            manifest["paper_sha256"],
            "e5b3699c00a0731cc00e165f12efb755c57886058e311c01e5643df6e56897b5",
        )
        self.assertEqual(manifest["source_commit"], decision["source_commit"])
        self.assertEqual(len(manifest["inputs"]), 8980)
        self.assertTrue(all(
            set(row) == {"input_scope", "locator", "sha256", "size_bytes"}
            for row in manifest["inputs"]
        ))

        comparison = json.loads((raw / "comparison.json").read_text(encoding="utf-8"))
        self.assertEqual(
            set(comparison),
            {
                "schema",
                "combined_primary_manifest_digest",
                "differing_primary_files",
                "environment_bindings",
                "primary_file_count",
                "primary_receipts_byte_identical",
                "run_a_primary_manifest",
                "run_a_environment_sha256",
                "run_b_primary_manifest",
                "run_b_environment_sha256",
                "runner_repeatability",
                "seeds_distinct",
                "source_and_input_identity",
            },
        )
        self.assertEqual(comparison["schema"], "memprobe-run-comparison/1")
        self.assertEqual(comparison["primary_file_count"], len(primary_files))
        self.assertEqual(comparison["differing_primary_files"], [])
        self.assertTrue(comparison["primary_receipts_byte_identical"])
        self.assertTrue(comparison["seeds_distinct"])
        self.assertEqual(comparison["environment_bindings"], "PASS")
        self.assertEqual(comparison["runner_repeatability"], "PASS")
        self.assertEqual(comparison["source_and_input_identity"], "PASS")
        self.assertEqual(set(comparison["run_a_primary_manifest"]), primary_files)
        self.assertEqual(
            comparison["run_a_primary_manifest"],
            comparison["run_b_primary_manifest"],
        )

        environment_keys = {
            "architecture",
            "input_manifest_sha256",
            "locale",
            "network_attempt_count",
            "network_guard",
            "operating_system",
            "primary_manifest",
            "primary_manifest_digest",
            "python_hash_seed",
            "python_implementation",
            "python_version",
            "runner_sha256",
            "schema",
            "timezone",
        }
        environments = [
            json.loads((raw / name).read_text(encoding="utf-8"))
            for name in ("environment_run_a.json", "environment_run_b.json")
        ]
        for environment in environments:
            self.assertEqual(set(environment), environment_keys)
            self.assertEqual(environment["schema"], "memprobe-audit-environment/1")
            self.assertEqual(environment["network_guard"], "PASS")
            self.assertEqual(environment["network_attempt_count"], 0)
            self.assertEqual(environment["locale"], "C")
            self.assertEqual(environment["timezone"], "UTC")
            self.assertEqual(environment["primary_manifest"], comparison["run_a_primary_manifest"])
        self.assertNotEqual(
            environments[0]["python_hash_seed"],
            environments[1]["python_hash_seed"],
        )

    def test_memprobe_checked_verifier_receipt_only_passes(self):
        artifact_root = build.ROOT / "research" / "memprobe-recovery-boundary-audit"
        result = subprocess.run(
            [
                sys.executable,
                str(artifact_root / "verify_checked.py"),
                "--mode",
                "receipt-only",
                "--artifact-root",
                str(artifact_root),
            ],
            cwd=build.ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "PASS: receipt-only integrity; original evidence not revalidated",
        )
        self.assertEqual(result.stderr, "")

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
        pmbench = by_id["pm-bench"]
        self.assertEqual(atma["noteDepth"], "read")
        self.assertEqual(insightemb["noteDepth"], "read")
        self.assertEqual(doyle["noteDepth"], "read")
        self.assertEqual(longmemeval["noteDepth"], "read")
        self.assertEqual(pmbench["noteDepth"], "worked")
        current_skim_ids = {
            "trustmem-consolidation", "verifiable-memory", "mosaic-long-term-memory",
            "proactive-wake-anchor",
            "coala-cognitive-architecture", "storage-to-experience",
            "continual-learning-experience-reuse", "agentic-memory", "midca-dual-cycle",
            "agm-theory-change", "memory-beyond-recall",
        }
        self.assertTrue(all(by_id[material_id]["noteDepth"] == "skim" for material_id in current_skim_ids))
        for material in (atma, insightemb, doyle, longmemeval, pmbench):
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
        self.assertEqual(pmbench["contributions"][0]["type"], "public-test")

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

    def test_pmbench_worked_audit_is_checked_and_bounded(self):
        material = next(
            item for item in self.data["materials"]
            if item["id"] == "pm-bench"
        )
        self.assertEqual(material["noteDepth"], "worked")
        contribution = material["contributions"][0]
        self.assertEqual(contribution["type"], "public-test")
        self.assertEqual(contribution["byline"], "Agent Memory Study editors")
        linked_names = {link["url"].rsplit("/", 1)[-1] for link in contribution["links"]}
        self.assertEqual(
            linked_names,
            {"README.md", "audit.py", "RESULTS.txt", "decision.json", "source_manifest.json"},
        )

        artifact_root = build.ROOT / "research" / "pmbench-scoring-contract-audit"
        decision = json.loads((artifact_root / "raw" / "decision.json").read_text(encoding="utf-8"))
        probes = json.loads(
            (artifact_root / "raw" / "official_probes.json").read_text(encoding="utf-8")
        )
        report = json.loads(
            (artifact_root / "raw" / "report_comparison.json").read_text(encoding="utf-8")
        )
        source_manifest = json.loads(
            (artifact_root / "raw" / "source_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(probes["status"], "PASS")
        self.assertEqual(decision["inventory"]["primary_run_count"], 64)
        self.assertEqual(decision["inventory"]["live_run_count"], 48)
        self.assertEqual(decision["inventory"]["replay_run_count"], 16)
        self.assertEqual(
            decision["hidden_channel_attribution"][
                "without_required_query_from_due_through_completion_count"
            ],
            381,
        )
        self.assertEqual(
            decision["update_violation"]["accepted_late_current_state_by_scorer_count"],
            27,
        )
        self.assertEqual(decision["step_identity"]["identity_problem_run_count"], 0)
        self.assertEqual(
            decision["step_identity"]["score_changed_after_identity_alignment_run_count"],
            0,
        )
        self.assertTrue(report["semantic_content_identical_after_single_path_repair"])
        self.assertEqual(len(source_manifest["released_primary_log_sha256"]), 64)
        self.assertEqual(
            len((artifact_root / "raw" / "run_scores.jsonl").read_text(encoding="utf-8").splitlines()),
            64,
        )
        self.assertEqual(
            len(
                (artifact_root / "raw" / "hidden_channel_findings.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ),
            1062,
        )
        self.assertEqual(
            len(
                (artifact_root / "raw" / "update_violation_findings.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ),
            541,
        )

        checksum_lines = (artifact_root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(checksum_lines), 9)
        for line in checksum_lines:
            expected, relative = line.split("  ", 1)
            observed = hashlib.sha256((artifact_root / relative).read_bytes()).hexdigest()
            self.assertEqual(observed, expected)

    def test_statefuse_worked_essay_and_evidence_audit_are_checked_and_separate(self):
        material = next(
            item for item in self.data["materials"]
            if item["id"] == "statefuse-conflict-preserving-memory"
        )
        self.assertEqual(material["noteDepth"], "worked")
        self.assertIn("完整读了 arXiv v1", material["readingScope"])

        contribution = material["contributions"][0]
        self.assertEqual(contribution["type"], "public-test")
        self.assertEqual(contribution["byline"], "Agent Memory Study editors")
        linked_names = {link["url"].rsplit("/", 1)[-1] for link in contribution["links"]}
        self.assertEqual(
            linked_names,
            {
                "README.md", "PREREGISTRATION.md", "audit.py", "decision.json",
                "readiness.json", "reproduction.json", "source_manifest.json",
            },
        )

        artifact_root = build.ROOT / "research" / "statefuse-interpretation-contract-audit"
        decision = json.loads((artifact_root / "raw" / "decision.json").read_text(encoding="utf-8"))
        readiness = json.loads(
            (artifact_root / "raw" / "readiness.json").read_text(encoding="utf-8")
        )
        source_manifest = json.loads(
            (artifact_root / "raw" / "source_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(decision["official_suite"]["passed_count"], 139)
        self.assertEqual(decision["official_suite"]["skipped_count"], 0)
        self.assertEqual(decision["case_count"], 8)
        self.assertEqual(decision["permutation_group_count"], 17)
        self.assertEqual(decision["run_result_count"], 428)
        self.assertTrue(decision["h1"]["supported"])
        self.assertTrue(decision["h2"]["supported"])
        self.assertEqual(readiness["schema"], "statefuse-readiness/2")
        self.assertTrue(readiness["integration_readiness_passed"])
        self.assertEqual(readiness["canonical_ams_status"], "not_assessed_by_evidence_artifact")
        self.assertEqual(readiness["public_note_depth"], "not_assessed_by_evidence_artifact")
        self.assertNotIn("worked_candidate", readiness)
        self.assertEqual(
            source_manifest["workshop_manuscript"]["title"],
            "StateFuse: Taxonomy-Aware Conflict-Preserving Memory for Heterogeneous Agent Systems",
        )
        self.assertNotEqual(source_manifest["workshop_manuscript"]["title"], material["title"])
        self.assertNotIn(
            "Local worked candidate",
            (artifact_root / "RESULTS.txt").read_text(encoding="utf-8"),
        )

        checksum_lines = (artifact_root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(checksum_lines), 14)
        for line in checksum_lines:
            expected, relative = line.split("  ", 1)
            observed = hashlib.sha256((artifact_root / relative).read_bytes()).hexdigest()
            self.assertEqual(observed, expected)

    def test_fluctlightdb_worked_essay_and_scope_audit_are_checked_and_bounded(self):
        material = next(
            item for item in self.data["materials"]
            if item["id"] == "fluctlightdb-observation-binding"
        )
        self.assertEqual(material["number"], 19)
        self.assertEqual(material["noteDepth"], "worked")
        self.assertIn("完整读了 arXiv v1", material["readingScope"])
        self.assertEqual(
            set(material["failureSurfaces"]),
            {"state-representation", "retrieval-active-context"},
        )

        contribution = material["contributions"][0]
        self.assertEqual(contribution["type"], "public-test")
        self.assertEqual(contribution["byline"], "Agent Memory Study editors")
        self.assertIn("not a LoCoMo/LongMemEval/BEIR/FAMB reproduction", contribution["boundary"])
        linked_names = {link["url"].rsplit("/", 1)[-1] for link in contribution["links"]}
        self.assertEqual(
            linked_names,
            {
                "README.md", "PREREGISTRATION.md", "audit.py",
                "compact-query-rows.json", "summary.json", "posttest-evidence.json",
                "source-manifest.json", "current-main-build-receipt.md",
                "reproduction.json",
            },
        )

        artifact_root = build.ROOT / "research" / "fluctlightdb-observation-binding-audit"
        raw = artifact_root / "raw"
        summary = json.loads((raw / "summary.json").read_text(encoding="utf-8"))
        evidence = json.loads((raw / "posttest-evidence.json").read_text(encoding="utf-8"))
        compact_rows = json.loads((raw / "compact-query-rows.json").read_text(encoding="utf-8"))
        source_manifest = json.loads((raw / "source-manifest.json").read_text(encoding="utf-8"))
        reproduction = json.loads((raw / "reproduction.json").read_text(encoding="utf-8"))
        manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["status"], "COMPLETE")
        self.assertEqual(summary["compact_query_rows"], 1140)
        self.assertTrue(summary["protocol_gate"]["all_matrix_receipts_pass"])
        self.assertTrue(summary["protocol_gate"]["all_official_gates_pass"])
        self.assertEqual(len(compact_rows), 1140)
        self.assertEqual(len(evidence["rows"]), 360)
        self.assertEqual(
            evidence["summary_sha256"],
            hashlib.sha256((raw / "summary.json").read_bytes()).hexdigest(),
        )

        for revision in ("paper-time", "repair-descendant"):
            self.assertEqual(summary["official"][revision]["isolated"]["hits"], "50/50")
            self.assertEqual(summary["official"][revision]["shared"]["hits"], "9/50")
            self.assertTrue(summary["official"][revision]["shared"]["all_domains_invariant"])
            for repeat in ("r1", "r2"):
                lexical = summary["observed"][revision][repeat]["lexical_primary"]
                self.assertEqual(lexical["n"], 45)
                self.assertEqual(lexical["both_pair_members_visible"], 45)
                self.assertEqual(lexical["ledger_above_chat"], 45)
                self.assertEqual(lexical["chat_above_ledger"], 0)
                self.assertEqual(lexical["foreign_agent_rows"], 0)
                scoped = summary["observed"][revision][repeat]["scoped"]
                self.assertEqual(scoped["wallet_queries_with_foreign_agent_rows"], 10)
                self.assertEqual(scoped["non_wallet_k128_foreign_agent_rows"], 0)

        self.assertEqual(
            source_manifest["runtime_objects"]["paper-time"]["commit"],
            "593623eea50361e563180c112322e26d0ab4093b",
        )
        self.assertEqual(
            source_manifest["runtime_objects"]["current-main"]["runtime_status"],
            "exact_source_compile_failure",
        )
        self.assertEqual(
            source_manifest["runtime_objects"]["repair-descendant"]["commit"],
            "f5d51e247b544503f8f47960b9dc6ecd43c2f464",
        )
        self.assertTrue(
            source_manifest["runtime_objects"]["repair-descendant"]
            ["retrieval_blobs_match_current_main"]
        )
        self.assertTrue(reproduction["public_reducer_on_complete_executed_matrix"]
                        ["summary_byte_matches_checked"])
        self.assertTrue(reproduction["public_reducer_on_complete_executed_matrix"]
                        ["posttest_evidence_byte_matches_checked"])

        artifact_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in artifact_root.rglob("*")
            if path.is_file() and path.suffix in {".py", ".md", ".json"}
        )
        self.assertNotIn("file://", artifact_text)
        self.assertNotIn("/Users/", artifact_text)
        self.assertNotIn("/Volumes/", artifact_text)
        self.assertIn("synthetic-source:", (raw / "compact-query-rows.json").read_text(encoding="utf-8"))

        checked_paths = {
            "summary.json": raw / "summary.json",
            "compact-query-rows.json": raw / "compact-query-rows.json",
            "posttest-evidence.json": raw / "posttest-evidence.json",
            "audit.py": artifact_root / "audit.py",
            "analyze_results.py": artifact_root / "analyze_results.py",
        }
        self.assertEqual(set(manifest), set(checked_paths))
        for name, path in checked_paths.items():
            self.assertEqual(manifest[name], hashlib.sha256(path.read_bytes()).hexdigest())

        checksum_lines = (artifact_root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(checksum_lines), 12)
        for line in checksum_lines:
            expected, relative = line.split("  ", 1)
            observed = hashlib.sha256((artifact_root / relative).read_bytes()).hexdigest()
            self.assertEqual(observed, expected)

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
        self.assertIn(
            "research/statefuse-interpretation-contract-audit/audit.py",
            relative_paths,
        )
        self.assertIn(
            "research/statefuse-interpretation-contract-audit/raw/decision.json",
            relative_paths,
        )
        self.assertIn(
            "research/statefuse-interpretation-contract-audit/raw/readiness.json",
            relative_paths,
        )
        self.assertIn(
            "research/mnl-promotion-cohort-audit/audit.py",
            relative_paths,
        )
        self.assertIn(
            "research/mnl-promotion-cohort-audit/raw/decision.json",
            relative_paths,
        )
        self.assertIn(
            "research/mnl-promotion-cohort-audit/raw/run_results.jsonl",
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
