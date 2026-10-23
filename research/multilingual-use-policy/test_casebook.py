import copy
import json
import unittest

import casebook

MALICIOUS = "back`tick` </script><img src=x onerror=alert(1)> <b>bold</b> & ampersand"


def evidence(eid, role, when, text, pointer="/messages/0"):
    return {"id": eid, "role": role, "time": when, "text": text,
            "locator": {"file": "/tmp/source.json", "pointer": pointer}}


def make_case(case_id, group_id, coverage, evidence_items, memory_text, memory_refs,
              context, summary):
    sequence = coverage == "resolved-message-window"
    episodes = casebook.build_episodes(evidence_items)
    return {
        "case_id": case_id,
        "group_id": group_id,
        "split": "exploration",
        "memory": {"id": case_id + "-mem", "text": memory_text, "source_refs": list(memory_refs)},
        "source": {"coverage": coverage, "evidence": evidence_items,
                   "complete_conversation": False, "sequence_verified": sequence},
        "context": context,
        "representations": {
            "episodes": episodes,
            "summary": summary,
            "coexistence": casebook.build_coexistence(episodes, summary),
        },
        "correction_candidate": {"status": "none", "evidence_ids": list(memory_refs)},
    }


def missing_context():
    return {"text": None, "kind": "missing", "as_of": None, "refs": [], "known_information": None,
            "recipient": "answerer", "purpose": "background", "already_selected": [], "budget_tokens": None}


def retro_context(text, refs):
    return {"text": text, "kind": "retrospective-next-user", "as_of": "2026-01-02",
            "refs": list(refs), "known_information": None, "recipient": "answerer",
            "purpose": "background", "already_selected": [], "budget_tokens": None}


def constructed_context(text):
    return {"text": text, "kind": "constructed", "as_of": None, "refs": [], "known_information": None,
            "recipient": "answerer", "purpose": "background", "already_selected": [], "budget_tokens": None}


def sample_casebook():
    resolved = [evidence("e1", "user", "2026-01-01T10:00:00Z", "please keep replies plain"),
                evidence("e2", "assistant", None, "understood")]
    quoted = [evidence("q1", "user", "2026-01-01T11:00:00Z", "I moved to Berlin last spring")]
    return {
        "schema": "ams-memory-casebook/1",
        "dataset_id": "synthetic-demo",
        "cases": [
            make_case("case-1", "g1", "resolved-message-window", resolved,
                      "The user prefers plain replies.", ["e1"], retro_context("Also, no code blocks.", ["e2"]),
                      "The user prefers plain replies."),
            make_case("case-2", "g1", "quoted-excerpts", quoted,
                      "The user moved to Berlin.", ["q1"], missing_context(),
                      "The user moved to Berlin."),
            make_case("case-3", "g2", "unresolved", [], "Derived from an unlocated memory.",
                      [], constructed_context("constructed background for calibration"),
                      "Derived from an unlocated memory."),
        ],
    }


def review(case_id, **overrides):
    base = {"case_id": case_id, "status": "unreviewed", "reviewer": None, "reviewed_at": None,
            "context_sufficient": None, "label": None, "rationale": ""}
    matching = next((c for c in sample_casebook()['cases'] if c['case_id'] == case_id), None)
    base.update(case_payload_digest=casebook.case_payload_digest(matching or {}),
                rubric_version=casebook.RUBRIC_VERSION, stale_reason=None, history=[])
    base.update(overrides)
    return base


class CasebookValidationTests(unittest.TestCase):
    def setUp(self):
        self.book = sample_casebook()

    def test_valid_casebook_passes(self):
        self.assertEqual(casebook.validate_casebook(self.book), [])

    def test_duplicate_case_id_is_rejected(self):
        self.book["cases"].append(copy.deepcopy(self.book["cases"][0]))
        errors = casebook.validate_casebook(self.book)
        self.assertTrue(any("duplicate case_id" in e for e in errors), errors)

    def test_dangling_memory_ref_is_rejected(self):
        self.book["cases"][0]["memory"]["source_refs"] = ["e1", "does-not-exist"]
        errors = casebook.validate_casebook(self.book)
        self.assertTrue(any("unknown evidence id" in e for e in errors), errors)

    def test_coverage_sequence_contract(self):
        self.book["cases"][0]["source"]["sequence_verified"] = False  # resolved identity does not certify sequence
        errors = casebook.validate_casebook(self.book)
        self.assertEqual(errors, [])

        book = sample_casebook()
        book["cases"][1]["source"]["sequence_verified"] = True  # quoted excerpts require false
        errors = casebook.validate_casebook(book)
        self.assertTrue(any("must be false for quoted excerpts" in e for e in errors), errors)

        book = sample_casebook()
        book["cases"][2]["source"]["evidence"] = [evidence("z", "user", None, "late")]
        errors = casebook.validate_casebook(book)
        self.assertTrue(any("must not carry evidence" in e for e in errors), errors)

    def test_summary_must_match_memory(self):
        case = self.book["cases"][0]
        case["representations"]["summary"] = "Unrelated claim"
        case["representations"]["coexistence"] = casebook.build_coexistence(
            case["representations"]["episodes"], case["representations"]["summary"])
        self.assertTrue(any("summary must equal memory.text" in e
                            for e in casebook.validate_casebook(self.book)))

    def test_whitespace_identity_rejected(self):
        self.book["dataset_id"] = "  "
        self.assertTrue(casebook.validate_casebook(self.book))

    def test_wrong_source_types_report_errors_without_crashing(self):
        self.book["cases"][0]["memory"] = None
        self.assertTrue(any("memory must be an object" in e
                            for e in casebook.validate_casebook(self.book)))
        self.book = sample_casebook()
        self.book["cases"][0]["source"]["evidence"][0]["id"] = []
        self.assertTrue(any("id must be a non-empty string" in e
                            for e in casebook.validate_casebook(self.book)))

    def test_complete_conversation_must_be_false(self):
        self.book["cases"][0]["source"]["complete_conversation"] = True
        errors = casebook.validate_casebook(self.book)
        self.assertTrue(any("complete_conversation must be false" in e for e in errors), errors)

    def test_context_kind_text_contradictions(self):
        self.book["cases"][1]["context"]["text"] = "conflicting text"
        errors = casebook.validate_casebook(self.book)
        self.assertTrue(any('requires text to be null' in e for e in errors), errors)

        book = sample_casebook()
        book["cases"][0]["context"]["text"] = None
        errors = casebook.validate_casebook(book)
        self.assertTrue(any("requires non-empty text" in e for e in errors), errors)

    def test_representation_consistency(self):
        self.book["cases"][0]["representations"]["episodes"] = "hand written episodes"
        errors = casebook.validate_casebook(self.book)
        self.assertTrue(any("build_episodes" in e for e in errors), errors)

        book = sample_casebook()
        book["cases"][0]["representations"]["coexistence"] = "unrelated"
        errors = casebook.validate_casebook(book)
        self.assertTrue(any("build_coexistence" in e for e in errors), errors)

    def test_partial_source_case_stays_in_pool(self):
        coverage = {case["source"]["coverage"] for case in self.book["cases"]}
        self.assertEqual(coverage, {"resolved-message-window", "quoted-excerpts", "unresolved"})
        self.assertEqual(casebook.validate_casebook(self.book), [])


class ReviewTemplateTests(unittest.TestCase):
    def setUp(self):
        self.book = sample_casebook()

    def test_template_is_all_unreviewed_and_unlabeled(self):
        template = casebook.template_reviews(self.book)
        self.assertEqual(template["schema"], casebook.REVIEWS_SCHEMA)
        self.assertEqual(template["dataset_id"], "synthetic-demo")
        self.assertEqual(len(template["reviews"]), 3)
        for entry in template["reviews"]:
            self.assertEqual(entry["status"], "unreviewed")
            self.assertIsNone(entry["label"])
            self.assertIsNone(entry["context_sufficient"])
            self.assertIsNone(entry["reviewer"])
            self.assertIsNone(entry["reviewed_at"])
            self.assertEqual(entry["rationale"], "")
        self.assertEqual(casebook.validate_reviews(template, self.book), [])

    def test_missing_context_does_not_become_a_label(self):
        template = casebook.template_reviews(self.book)
        by_id = {entry["case_id"]: entry for entry in template["reviews"]}
        self.assertEqual(by_id["case-2"]["status"], "unreviewed")
        self.assertIsNone(by_id["case-2"]["label"])

        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"][1] = review("case-2", status="confirmed", reviewer="r",
                                       reviewed_at="2026-01-03", label="useful",
                                       context_sufficient=True, rationale="looks useful")
        errors = casebook.validate_reviews(sidecar, self.book)
        self.assertTrue(any("requires a non-empty context text" in e for e in errors), errors)

    def test_insufficient_context_confirms_on_missing_context(self):
        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"][1] = review("case-2", status="confirmed", reviewer="r",
                                       reviewed_at="2026-01-03", label="insufficient-context",
                                       context_sufficient=False, rationale="no next message captured")
        self.assertEqual(casebook.validate_reviews(sidecar, self.book), [])

    def test_confirmed_constraints(self):
        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"][0] = review("case-1", status="confirmed", label="useful",
                                       context_sufficient=True, rationale="ok", reviewer="")
        errors = casebook.validate_reviews(sidecar, self.book)
        self.assertTrue(any("requires a reviewer" in e for e in errors), errors)
        self.assertTrue(any("requires reviewed_at" in e for e in errors), errors)

        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"][0] = review("case-1", status="confirmed", reviewer="r",
                                       reviewed_at="2026-01-03", label="useful",
                                       context_sufficient=False, rationale="ok")
        errors = casebook.validate_reviews(sidecar, self.book)
        self.assertTrue(any("requires context_sufficient=true" in e for e in errors), errors)

        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"][0] = review("case-1", status="confirmed", reviewer="r",
                                       reviewed_at="2026-01-03", label=None,
                                       context_sufficient=True, rationale="ok")
        errors = casebook.validate_reviews(sidecar, self.book)
        self.assertTrue(any("confirmed requires a label" in e for e in errors), errors)

        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"][0] = review("case-1", status="confirmed", reviewer="r",
                                       reviewed_at="2026-01-03", label="insufficient-context",
                                       context_sufficient=True, rationale="ok")
        errors = casebook.validate_reviews(sidecar, self.book)
        self.assertTrue(any("requires context_sufficient=false" in e for e in errors), errors)

    def test_confirmed_valid_entry_passes(self):
        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"][0] = review("case-1", status="confirmed", reviewer="alice",
                                       reviewed_at="2026-01-03T00:00:00Z", label="useful",
                                       context_sufficient=True, rationale="adds the plain-reply preference")
        self.assertEqual(casebook.validate_reviews(sidecar, self.book), [])

    def test_draft_may_be_partial(self):
        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"][0] = review("case-1", status="draft", reviewer="alice")
        self.assertEqual(casebook.validate_reviews(sidecar, self.book), [])

    def test_sidecar_binding(self):
        sidecar = casebook.template_reviews(self.book)
        sidecar["dataset_id"] = "other-dataset"
        self.assertTrue(any("does not match casebook dataset_id" in e
                            for e in casebook.validate_reviews(sidecar, self.book)))

        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"].append(review("ghost"))
        self.assertTrue(any("unknown case_id" in e for e in casebook.validate_reviews(sidecar, self.book)))

        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"].append(copy.deepcopy(sidecar["reviews"][0]))
        self.assertTrue(any("duplicate case_id" in e for e in casebook.validate_reviews(sidecar, self.book)))

    def test_subset_sidecar_is_valid(self):
        sidecar = {"schema": casebook.REVIEWS_SCHEMA, "dataset_id": "synthetic-demo",
                   "reviews": [review("case-1", status="draft", reviewer="alice")]}
        self.assertEqual(casebook.validate_reviews(sidecar, self.book), [])

    def test_wrong_review_id_type_reports_error_without_crashing(self):
        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"][0]["case_id"] = []
        self.assertTrue(any("case_id must be a non-empty string" in e
                            for e in casebook.validate_reviews(sidecar, self.book)))


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.book = sample_casebook()

    def _payload(self, html):
        marker = '<script type="application/json" id="casebook-data">'
        body = html.split(marker, 1)[1]
        data = body.split("</script>", 1)[0]
        return json.loads(data)

    def test_script_breakout_and_html_are_escaped(self):
        case = self.book["cases"][0]
        case["memory"]["text"] = MALICIOUS
        case["representations"]["summary"] = MALICIOUS
        case["source"]["evidence"][0]["text"] = MALICIOUS
        case["representations"]["episodes"] = casebook.build_episodes(case["source"]["evidence"])
        case["representations"]["coexistence"] = casebook.build_coexistence(
            case["representations"]["episodes"], case["representations"]["summary"])
        self.assertEqual(casebook.validate_casebook(self.book), [])
        html = casebook.render_html(self.book, casebook.template_reviews(self.book))

        self.assertEqual(html.count("</script>"), 2)
        self.assertNotIn("</script><img", html)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<b>bold</b>", html)
        self.assertIn("\\u003c/script", html)
        payload = self._payload(html)
        self.assertEqual(payload["casebook"]["cases"][0]["memory"]["text"], MALICIOUS)
        self.assertEqual(payload["casebook"]["cases"][0]["source"]["evidence"][0]["text"], MALICIOUS)

    def test_render_reloads_review_state(self):
        sidecar = casebook.template_reviews(self.book)
        sidecar["reviews"][0] = review("case-1", status="confirmed", reviewer="alice",
                                       reviewed_at="2026-01-03T00:00:00Z", label="useful",
                                       context_sufficient=True, rationale="ok")
        html = casebook.render_html(self.book, sidecar)
        payload = self._payload(html)
        kept = {entry["case_id"]: entry for entry in payload["reviews"]["reviews"]}
        self.assertEqual(kept["case-1"]["status"], "confirmed")
        self.assertEqual(kept["case-1"]["label"], "useful")
        self.assertEqual(kept["case-2"]["status"], "unreviewed")
        self.assertIsNone(kept["case-2"]["label"])

    def test_html_has_no_network_or_storage(self):
        html = casebook.render_html(self.book, casebook.template_reviews(self.book))
        for forbidden in ("localStorage", "sessionStorage", "XMLHttpRequest", "fetch(",
                          "sendBeacon", "<script src", "http://", "https://"):
            self.assertNotIn(forbidden, html, forbidden)
        self.assertEqual(self._payload(html)["casebook"]["schema"], "ams-memory-casebook/1")


class AggregateTests(unittest.TestCase):
    def test_group_and_status_counts(self):
        book = sample_casebook()
        sidecar = casebook.template_reviews(book)
        sidecar["reviews"][0] = review("case-1", status="confirmed", reviewer="alice",
                                       reviewed_at="2026-01-03T00:00:00Z", label="useful",
                                       context_sufficient=True, rationale="ok")
        sidecar["reviews"][1] = review("case-2", status="draft", reviewer="alice")
        report = casebook.aggregate(book, sidecar)
        self.assertEqual(report["totals"]["cases"], 3)
        self.assertEqual(report["totals"]["groups"], 2)
        self.assertEqual(report["by_group"]["g1"]["cases"], 2)
        self.assertEqual(report["by_group"]["g1"]["status"]["confirmed"], 1)
        self.assertEqual(report["by_group"]["g1"]["status"]["draft"], 1)
        self.assertEqual(report["by_group"]["g2"]["cases"], 1)
        self.assertEqual(report["status_counts"], {"unreviewed": 1, "draft": 1, "confirmed": 1, "stale": 0})
        self.assertEqual(report["label_counts"]["useful"], 1)
        self.assertEqual(report["label_counts"]["null"], 2)

    def test_aggregate_is_subset_aware_and_leaks_no_text(self):
        book = sample_casebook()
        sidecar = {"schema": casebook.REVIEWS_SCHEMA, "dataset_id": "synthetic-demo",
                   "reviews": [review("case-1", status="draft", reviewer="alice")]}
        report = casebook.aggregate(book, sidecar)
        self.assertEqual(report["status_counts"], {"unreviewed": 2, "draft": 1, "confirmed": 0, "stale": 0})
        blob = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("plain replies", blob)
        self.assertNotIn("Berlin", blob)


class ReviewIdentityRegressionTests(unittest.TestCase):
    def test_changed_context_same_ids_cannot_keep_confirmation(self):
        book = sample_casebook()
        sidecar = casebook.template_reviews(book)
        sidecar['reviews'][0].update(status='confirmed', reviewer='synthetic',
            reviewed_at='2026-01-03', label='useful', context_sufficient=True, rationale='reviewed')
        book['cases'][0]['context']['text'] = 'A different task.'
        self.assertTrue(casebook.validate_reviews(sidecar, book))


class BoundReviewTests(unittest.TestCase):
    def setUp(self):
        self.book = sample_casebook()
        self.sidecar = casebook.template_reviews(self.book)
        self.sidecar['reviews'][0].update(status='confirmed', reviewer='synthetic',
            reviewed_at='2026-01-03', label='useful', context_sufficient=True, rationale='reviewed',
            provenance={'method': 'synthetic original review'})

    def test_format_and_key_order_do_not_change_identity(self):
        reordered = json.loads(json.dumps(self.book, sort_keys=True, indent=4))
        self.assertEqual(casebook.validate_reviews(self.sidecar, reordered), [])
        self.assertEqual(casebook.rebind_reviews(self.sidecar, reordered)['reviews'], self.sidecar['reviews'])

    def test_all_reviewed_fields_invalidate_and_preserve_old_confirmation(self):
        def summary(c):
            c['memory']['text'] = c['representations']['summary'] = 'Changed summary.'
            c['representations']['coexistence'] = casebook.build_coexistence(
                c['representations']['episodes'], c['representations']['summary'])
        def reverse(c):
            c['source']['evidence'].reverse()
            c['representations']['episodes'] = casebook.build_episodes(c['source']['evidence'])
            c['representations']['coexistence'] = casebook.build_coexistence(
                c['representations']['episodes'], c['representations']['summary'])
        mutations = [lambda c: c['context'].update(text='Changed context'),
            lambda c: c.update(context=missing_context()), summary, reverse,
            lambda c: c['source']['evidence'][0]['locator'].update(pointer='/changed'),
            lambda c: c['correction_candidate'].update(scope='different scope'),
            lambda c: c['source'].update(sequence_verified=False)]
        for change in mutations:
            with self.subTest(change=change):
                book = copy.deepcopy(self.book)
                change(book['cases'][0])
                self.assertEqual(casebook.validate_casebook(book), [])
                self.assertTrue(casebook.validate_reviews(self.sidecar, book))
                with self.assertRaisesRegex(ValueError, 'rebind-reviews'):
                    casebook.render_html(book, self.sidecar)
                migrated = casebook.rebind_reviews(self.sidecar, book)
                r = migrated['reviews'][0]
                self.assertEqual(r['status'], 'stale')
                self.assertIsNone(r['reviewed_at'])
                old = r['history'][0]['review']
                self.assertEqual(old['status'], 'confirmed')
                self.assertEqual(old['reviewer'], 'synthetic')
                self.assertEqual(old['provenance'], {'method': 'synthetic original review'})
                self.assertEqual(old['case_payload_digest'], self.sidecar['reviews'][0]['case_payload_digest'])
                self.assertEqual(casebook.validate_reviews(migrated, book), [])
                self.assertEqual(self.sidecar['reviews'][0]['status'], 'confirmed')

    def test_rubric_revision_requires_reconfirmation(self):
        from unittest.mock import patch
        with patch.object(casebook, 'RUBRIC_VERSION', 'ams-memory-use-rubric/2'):
            self.assertTrue(casebook.validate_reviews(self.sidecar, self.book))
            migrated = casebook.rebind_reviews(self.sidecar, self.book)
            self.assertEqual(migrated['reviews'][0]['status'], 'stale')
            self.assertEqual(migrated['reviews'][0]['history'][0]['review']['rubric_version'],
                             'ams-memory-use-rubric/1')
            self.assertEqual(casebook.validate_reviews(migrated, self.book), [])

    def test_legacy_migration_and_removed_cases(self):
        legacy = copy.deepcopy(self.sidecar)
        legacy['schema'] = 'ams-memory-reviews/1'
        for r in legacy['reviews']:
            for key in ('rubric_version', 'case_payload_digest', 'history', 'stale_reason'):
                r.pop(key)
        self.book['cases'][0]['context'] = missing_context()
        self.assertTrue(casebook.validate_reviews(legacy, self.book))
        migrated = casebook.rebind_reviews(legacy, self.book)
        self.assertEqual(migrated['reviews'][0]['status'], 'stale')
        self.assertEqual(migrated['reviews'][0]['history'][0]['schema'], 'ams-memory-reviews/1')
        self.assertEqual(migrated['reviews'][0]['history'][0]['review']['status'], 'confirmed')
        self.book['cases'].pop(0)
        with self.assertRaisesRegex(ValueError, '--removed-cases archive'):
            casebook.rebind_reviews(legacy, self.book)
        archived = casebook.rebind_reviews(legacy, self.book, archive_removed=True)
        self.assertEqual(archived['removed_reviews'][0]['review']['case_id'], 'case-1')
        self.assertEqual(archived['removed_reviews'][0]['review']['status'], 'confirmed')
        self.assertEqual(casebook.validate_reviews(archived, self.book), [])

    def test_malformed_migration_and_history_are_rejected(self):
        for mutate in (lambda d: d['reviews'].append(copy.deepcopy(d['reviews'][0])),
                       lambda d: d['reviews'][0].update(case_id=[]),
                       lambda d: d['reviews'][0].update(history=[{}]),
                       lambda d: d['reviews'][0].update(case_payload_digest='wrong')):
            broken = copy.deepcopy(self.sidecar)
            mutate(broken)
            with self.assertRaises(ValueError):
                casebook.rebind_reviews(broken, self.book)

    def test_history_limit_never_silently_discards_confirmation(self):
        self.book['cases'][0]['context']['text'] = 'changed'
        once = casebook.rebind_reviews(self.sidecar, self.book)
        prior = once['reviews'][0]['history'][0]
        once['reviews'][0]['history'] = [copy.deepcopy(prior) for _ in range(casebook.MAX_HISTORY)]
        self.book['cases'][0]['context']['text'] = 'changed again'
        with self.assertRaisesRegex(ValueError, 'bounded history limit'):
            casebook.rebind_reviews(once, self.book)
        self.assertEqual(len(once['reviews'][0]['history']), casebook.MAX_HISTORY)
        self.assertEqual(once['reviews'][0]['history'][0]['review']['status'], 'confirmed')

    def test_cli_rebind_preserves_input_and_requires_fresh_output(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory(prefix='ams-casebook-') as work:
            root = Path(work)
            book_path, old_path, new_path = (root / n for n in ('book.json', 'old.json', 'new.json'))
            self.book['cases'][0]['context']['text'] = 'changed'
            book_path.write_text(json.dumps(self.book))
            original = json.dumps(self.sidecar)
            old_path.write_text(original)
            args = ['rebind-reviews', '--casebook', str(book_path), '--reviews', str(old_path), '--out']
            self.assertEqual(casebook.main(args + [str(new_path)]), 0)
            self.assertEqual(old_path.read_text(), original)
            self.assertEqual(json.loads(new_path.read_text())['reviews'][0]['status'], 'stale')
            import contextlib
            import io
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                casebook.main(args + [str(old_path)])


class EpisodeBuilderTests(unittest.TestCase):
    def test_episodes_use_role_time_id_text(self):
        items = [evidence("e1", "user", "T1", "hello"), evidence("e2", "unknown", None, "world")]
        self.assertEqual(casebook.build_episodes(items), "e1 | user | T1 | hello\ne2 | unknown | unknown | world")
        self.assertEqual(casebook.build_episodes([]), "")

    def test_coexistence_wraps_both(self):
        text = casebook.build_coexistence("EP", "SUM")
        self.assertTrue(text.startswith("EPISODES:\nEP"))
        self.assertTrue(text.endswith("SUMMARY:\nSUM"))


if __name__ == "__main__":
    unittest.main()
