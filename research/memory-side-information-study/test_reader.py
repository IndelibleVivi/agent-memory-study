#!/usr/bin/env python3
"""Offline controls that can reject misleading scientific and delivery behavior."""
from collections import Counter, defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import reader as r
import reader_api as api


def body(value=None, **extra):
    return {"status": "completed", "model": r.MODEL,
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]}],
            **extra}


class ReaderDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.metadata, cls.truth = r.build()
        cls.pstar = r.posterior(cls.truth)

    def responses(self, blind_q=False, constant=False):
        result = {}
        for identity, m in self.metadata.items():
            p = self.pstar[identity]
            if blind_q and m["scope"] == "irrelevant" and m["channel"] == "X":
                p = float((m["record"] ^ m["mapping"]) == 0)
            if constant:
                p = 1.0
            for rep in range(3):
                result[identity, rep] = {"status": "valid", "choice": "A" if p >= .5 else "B", "p_A": p}
        return result

    def test_complete_distribution_and_deduplication(self):
        self.assertEqual(len(self.inputs), 68)
        self.assertEqual(len(self.truth), 272)
        self.assertEqual(len({r.canonical(i["messages"]) for i in self.inputs}), 68)
        masses = defaultdict(F)
        for row in self.truth:
            masses[row["cell"]] += F(row["weight"])
        self.assertEqual(set(masses.values()), {F(1)})
        self.assertEqual(len(masses), 6)
        self.assertEqual(Counter(m["scope"] for m in self.metadata.values()),
                         {"valid": 32, "irrelevant": 32, "none": 4})

    def test_normative_posteriors_from_actual_visible_information(self):
        for identity, m in self.metadata.items():
            if m["channel"] == "Y":
                expected = .75 if m["record"] == 0 else .25
            elif m["scope"] == "valid":
                expected = float(m["record"] == m["mapping"])
            else:
                expected = .5
            self.assertEqual(self.pstar[identity], expected)

    def test_q_is_balanced_inside_each_world_and_order(self):
        groups = defaultdict(list)
        for row in self.truth:
            if row["cell"].endswith("/irrelevant"):
                groups[row["cell"], row["theta"], row["C"], row["E"], row["row_order"], row["position"]].append(row)
        for rows in groups.values():
            self.assertEqual({row["D"] for row in rows}, {0, 1})
            self.assertEqual(rows[0]["weight"], rows[1]["weight"])

    def test_consistent_label_and_code_permutations_are_closed(self):
        identities = set(self.metadata)
        for identity, m in self.metadata.items():
            if m["scope"] == "none":
                continue
            # Relabeling A/B flips the destination label, not code tokens.
            changed = r.render(m["channel"], m["scope"], m["record"] ^ (m["channel"] == "Y"),
                               m["mapping"] ^ 1, m["row_order"], m["position"])
            other = r.digest(changed)
            self.assertIn(other, identities)
            self.assertEqual(self.pstar[other], 1 - self.pstar[identity])
            # Relabeling code tokens flips mapping and row order, not truth.
            changed = r.render(m["channel"], m["scope"], m["record"] ^ (m["channel"] == "X"),
                               m["mapping"] ^ 1, m["row_order"] ^ 1, m["position"])
            other = r.digest(changed)
            self.assertIn(other, identities)
            self.assertEqual(self.pstar[other], self.pstar[identity])

    def test_matched_main_messages_differ_only_in_project_scope(self):
        for identity, m in self.metadata.items():
            if m["scope"] != "valid":
                continue
            valid = r.render(m["channel"], "valid", m["record"], m["mapping"], m["row_order"], m["position"])
            other = r.render(m["channel"], "irrelevant", m["record"], m["mapping"], m["row_order"], m["position"])
            self.assertEqual(r.canonical(valid).replace("项目 P 编码册", "项目 Q 编码册"), r.canonical(other))
            self.assertEqual(len(r.canonical(valid).encode()), len(r.canonical(other).encode()))

    def test_messages_contain_no_evaluator_fields_or_unexposed_record(self):
        for item in self.inputs:
            self.assertEqual(set(item), {"id", "messages"})
            self.assertEqual(item["id"], r.digest(item["messages"]))
            text = r.canonical(item["messages"])
            for forbidden in ("theta", '"gold"', '"weight"', "results.json", "Θ", "XOR"):
                self.assertNotIn(forbidden, text)
            user = item["messages"][1]["content"]
            m = self.metadata[item["id"]]
            self.assertNotIn("抄录单" if m["channel"] == "X" else "样本代号", user)

    def test_ideal_outputs_score_known_laws(self):
        result = r.summarize(self.inputs, self.metadata, self.truth, self.responses())
        self.assertEqual(result["D"], .5)
        expected = {"X/valid": (1, 0), "X/irrelevant": (.5, .25), "X/none": (.5, .25),
                    "Y/valid": (.75, .1875), "Y/irrelevant": (.75, .1875), "Y/none": (.75, .1875)}
        for cell, (accuracy, brier) in expected.items():
            self.assertEqual(result["cells"][cell]["accuracy"], accuracy)
            self.assertEqual(result["cells"][cell]["brier_on_valid_probability"], brier)
            self.assertEqual(result["cells"][cell]["posterior_mae_on_valid_probability"], 0)
        self.assertEqual(result["flip_diagnostics"]["X/valid"]["mean_mapping_aligned_probability_change"], 1)
        self.assertEqual(result["flip_diagnostics"]["X/irrelevant"]["mean_absolute_probability_change"], 0)

    def test_wrong_scope_achieves_same_D_but_is_detected(self):
        result = r.summarize(self.inputs, self.metadata, self.truth, self.responses(blind_q=True))
        self.assertEqual(result["D"], .5)
        self.assertEqual(result["cells"]["X/irrelevant"]["accuracy"], .5)
        self.assertEqual(result["cells"]["X/irrelevant"]["brier_on_valid_probability"], .5)
        self.assertEqual(result["cells"]["X/irrelevant"]["posterior_mae_on_valid_probability"], .5)
        self.assertEqual(result["flip_diagnostics"]["X/irrelevant"]["mean_mapping_aligned_probability_change"], 1)

    def test_constant_guess_cannot_look_like_mapping_ability(self):
        result = r.summarize(self.inputs, self.metadata, self.truth, self.responses(constant=True))
        self.assertEqual(result["D"], 0)
        self.assertEqual({c["accuracy"] for c in result["cells"].values()}, {.5})

    def test_missing_calls_stay_in_planned_denominator(self):
        responses = self.responses()
        identity = next(i for i, m in self.metadata.items() if m["channel"] == "X" and m["scope"] == "valid")
        del responses[identity, 0]
        result = r.summarize(self.inputs, self.metadata, self.truth, responses)
        self.assertEqual(result["unrecorded_calls"], 1)
        self.assertAlmostEqual(result["cells"]["X/valid"]["accuracy"], 47 / 48)
        self.assertAlmostEqual(result["cells"]["X/valid"]["probability_coverage"], 47 / 48)

    def test_tied_choices_can_flip_without_probability_scope_error(self):
        responses = self.responses()
        for (identity, rep), result in responses.items():
            m = self.metadata[identity]
            if m["channel"] == "X" and m["scope"] == "irrelevant":
                result["choice"] = "AB"[m["mapping"]]
        flip = r.flip_scores(self.metadata, responses)["X/irrelevant"]
        self.assertEqual(flip["choice_flip_rate"], 1)
        self.assertEqual(flip["mean_absolute_probability_change"], 0)

    def test_invalid_probability_does_not_erase_valid_choice(self):
        parsed = r.parse_response(body({"choice": "A", "p_A": 3}))
        self.assertEqual(parsed, {"status": "invalid_value", "choice": "A", "p_A": None})

    def test_parse_failure_refusal_incomplete_and_nonfinite(self):
        for value in (None, [], {"choice": "A"}, {"choice": "A", "p_A": .5, "extra": 1}):
            self.assertEqual(r.parse_response(body(value))["status"], "parse_failure")
        for value in (True, float("nan"), float("inf"), -.1, 1.1):
            self.assertIsNone(r.parse_response(body({"choice": "A", "p_A": value}))["p_A"])
        self.assertEqual(r.parse_response({"status": "incomplete"})["status"], "incomplete")
        self.assertEqual(r.parse_response({"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]})["status"], "refusal")

    def test_malformed_provider_envelopes_remain_parse_failures(self):
        bad = [[], {"status": "completed", "output": [3]},
               {"status": "completed", "output": None},
               {"status": "completed", "output": [{"type": "message", "content": [3]}]},
               {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": None}]}]}]
        for value in bad:
            self.assertEqual(api.parsed({"http_status": 200, "raw_body": json.dumps(value)})["status"], "parse_failure")

    def test_freeze_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            r.freeze(path, {"original": 1})
            with self.assertRaises(FileExistsError):
                r.freeze(path, {"replacement": 2})
            self.assertEqual(r.load(path), {"original": 1})

    def test_prepare_rejects_repository_destination(self):
        with self.assertRaises(ValueError):
            r.prepare(r.ROOT / "should-not-exist")

    def test_replay_binds_actual_request_and_counts_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "run"
            r.prepare(directory)
            item = self.inputs[0]
            payload = {**r.CONFIG, "input": item["messages"]}
            base = directory / "calls" / (item["id"] + "-0")
            r.freeze(base.with_suffix(".request.json"), payload)
            receipt = {"http_status": 200, "input_id": item["id"], "repeat": 0,
                       "request_digest": r.digest(payload), "elapsed_seconds": .1,
                       "started_at": "2026-11-07T00:00:00Z", "finished_at": "2026-11-07T00:00:01Z",
                       "raw_body": json.dumps(body({"choice": "A", "p_A": .5}, usage={"input_tokens": 500, "output_tokens": 20}))}
            r.freeze(base.with_suffix(".response.json"), receipt)
            r.freeze(directory / "preflight.json", {"input_tokens": {i["id"]: 500 for i in self.inputs}})
            result = api.replay(directory)
            self.assertEqual(result["recorded_calls"], 1)
            self.assertEqual(result["unrecorded_calls"], 203)
            request = base.with_suffix(".request.json")
            payload["input"] = [{"role": "user", "content": "a different task"}]
            request.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "actual delivery"):
                api.replay(directory)

    def test_no_implicit_resume_or_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "run"
            r.prepare(directory)
            r.freeze(directory / "preflight.json", {"valid_irrelevant_token_matched": True, "estimated_upper_cost_usd": 4.8})
            (directory / "calls").mkdir()
            with patch.object(api, "post") as post:
                with self.assertRaises(FileExistsError):
                    api.execute(directory)
                post.assert_not_called()

    def test_replay_keeps_bad_bodies_and_checks_each_repeat_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "run"
            r.prepare(directory)
            item = self.inputs[0]
            payload = {**r.CONFIG, "input": item["messages"]}
            for rep in range(3):
                base = directory / "calls" / (item["id"] + "-" + str(rep))
                r.freeze(base.with_suffix(".request.json"), payload)
                raw = "not JSON" if rep == 2 else json.dumps(body(
                    {"choice": "A", "p_A": .5}, usage={"input_tokens": 501 if rep == 0 else 500,
                                                       "output_tokens": 20, "input_tokens_details": None}))
                r.freeze(base.with_suffix(".response.json"), {
                    "http_status": 200, "input_id": item["id"], "repeat": rep,
                    "request_digest": r.digest(payload), "elapsed_seconds": .1,
                    "started_at": "2026-11-07T00:00:00Z", "finished_at": "2026-11-07T00:00:01Z", "raw_body": raw})
            r.freeze(directory / "preflight.json", {"input_tokens": {i["id"]: 500 for i in self.inputs}})
            result = api.replay(directory)
            self.assertEqual(result["recorded_calls"], 3)
            self.assertEqual(result["status_counts"], {"valid": 2, "parse_failure": 1})
            self.assertEqual(result["usage"]["calls_with_usage"], 2)
            self.assertFalse(result["token_counts"]["actual_matches_preflight"])
            self.assertEqual(result["token_counts"]["calls_with_token_count"], 2)


if __name__ == "__main__":
    unittest.main()
