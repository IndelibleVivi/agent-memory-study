#!/usr/bin/env python3
"""Derive compact plot data from saved numerical summaries; no raw replay."""
from pathlib import Path
import json


def derive(results, fixed):
    actual = fixed["excluding_exposed"]
    arms = ["raw", "summary", "structured", "trunc_last_matched"]
    return {
        "schema": "ams-task-conditioned-utility-figure/1",
        "left_panel": {
            "evidence": "recomputed_author_analysis_of_archived_outputs",
            "n_bearing_cells": actual["n_bearing_cells"],
            "arms": [{"arm": key, **actual["arms"][key]} for key in arms],
        },
        "right_panel": {
            "evidence": "hypothetical_standardisation_not_new_inference",
            "assumption": "Hold h and e fixed while varying p; no forecast of model scaling",
            "curves": [{"stratum": name, "h": value["help_given_wrong_h"],
                        "e": value["harm_given_correct_e"],
                        "observed_p": value["baseline_correctness_p"],
                        "observed_delta": value["mean_delta"],
                        "points": [[i/100, (1-i/100)*value["help_given_wrong_h"]-(i/100)*value["harm_given_correct_e"]] for i in range(101)]}
                       for name, value in results["strata"].items()],
        },
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    data = derive(json.loads((root/"results.json").read_text()), json.loads((root/"official_fixed_context.json").read_text()))
    (root/"figure-data.json").write_text(json.dumps(data, indent=2)+"\n")
    print("Wrote compact figure data from saved summaries; did not replay upstream outcomes")
