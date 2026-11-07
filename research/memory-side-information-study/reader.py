#!/usr/bin/env python3
"""Authored reader stimuli and offline scoring. This module makes no API calls."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction as F
import hashlib
from itertools import product
import json
import math
import os
from pathlib import Path
import uuid

from study import channels

ROOT = Path(__file__).resolve().parent
REPEATS = 3
MODEL = "gpt-6.1-sol"
SYSTEM = (
    "这是一项虚构样本路由任务。每份样本的真实目的地先验等可能为 A 柜或 B 柜。"
    "每个项目独立、等可能采用两种编码册之一：两个代号与两个柜一一对应。"
    "项目编码册与样本真实目的地相互独立。编码记录没有错误，但只能用同一项目的编码册解释。"
    "抄录单有四分之一概率把 A、B 写反；这个误差与真实目的地及各项目编码册相互独立。"
    "提供哪种记录由预先固定的安排决定，与样本目的地和编码册无关。每份样本独立。"
    "仅依据本次材料判断；若两项同概率，仍选其中一项。"
    "返回 JSON：choice 为 A 或 B，p_A 为本次材料下目的地是 A 柜的概率，取值 0 到 1。不要解释。"
)
QUESTION = "项目 P 的这份样本应送到 A 柜还是 B 柜？"
FORMAT = {
    "type": "json_schema", "name": "routing_choice", "strict": True,
    "schema": {"type": "object", "properties": {
        "choice": {"type": "string", "enum": ["A", "B"]},
        "p_A": {"type": "number"}},
        "required": ["choice", "p_A"], "additionalProperties": False},
}
CONFIG = {"model": MODEL, "reasoning": {"effort": "low"},
          "max_output_tokens": 2048, "service_tier": "default", "store": False,
          "text": {"format": FORMAT}}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def freeze(path, value):
    """Publish complete bytes without replacement; interrupted staging is retained."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".pending")
    with staged.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.link(staged, path)
    staged.unlink()


def render(channel, scope, record, mapping=0, row_order=0, position=0):
    """Accept only visible values, never a latent world or evaluator answer."""
    if channel not in ("X", "Y") or scope not in ("valid", "irrelevant", "none"):
        raise ValueError("unknown exposure")
    if any(type(v) is not int or v not in (0, 1) for v in (record, mapping, row_order, position)):
        raise ValueError("visible values must be bits")
    codes, labels = ("青石", "云母"), ("A", "B")
    record_text = (f"项目 P 的样本代号：{codes[record]}。" if channel == "X" else
                   f"项目 P 的抄录单目的地：{labels[record]} 柜。")
    parts = [record_text]
    if scope != "none":
        project = "P" if scope == "valid" else "Q"
        order = (0, 1) if row_order == 0 else (1, 0)
        mapping_text = f"项目 {project} 编码册：" + "；".join(
            f"{codes[i]}→{labels[i ^ mapping]} 柜" for i in order) + "。"
        parts = [mapping_text, record_text] if position == 0 else [record_text, mapping_text]
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "\n".join(parts + [QUESTION])}]


def build():
    inputs, metadata, truth = {}, {}, []

    def add(channel, scope, record, mapping=0, row_order=0, position=0):
        messages = render(channel, scope, record, mapping, row_order, position)
        identity = digest(messages)
        inputs[identity] = {"id": identity, "messages": messages}
        metadata[identity] = dict(channel=channel, scope=scope, record=record,
                                  mapping=mapping if scope != "none" else None,
                                  row_order=row_order if scope != "none" else None,
                                  position=position if scope != "none" else None)
        return identity

    # The original enumerator owns Θ,C,E. Independent Q mappings are exactly
    # balanced WITHIN each world, rather than sampled across worlds.
    for world, mass in channels(True):
        for channel, scope, d, row_order, position in product(
                ("X", "Y"), ("valid", "irrelevant"), range(2), range(2), range(2)):
            mapping = world["C"] if scope == "valid" else d
            identity = add(channel, scope, world[channel], mapping, row_order, position)
            truth.append({"id": identity, "cell": channel + "/" + scope,
                          "gold": "AB"[world["theta"]], "weight": str(mass / 8),
                          "theta": world["theta"], "C": world["C"],
                          "E": world["theta"] ^ world["Y"], "D": d,
                          "row_order": row_order, "position": position})
        for channel in ("X", "Y"):
            identity = add(channel, "none", world[channel])
            truth.append({"id": identity, "cell": channel + "/none",
                          "gold": "AB"[world["theta"]], "weight": str(mass),
                          "theta": world["theta"], "C": world["C"],
                          "E": world["theta"] ^ world["Y"], "D": None,
                          "row_order": None, "position": None})
    return list(sorted(inputs.values(), key=lambda r: r["id"])), metadata, truth


def source_identity():
    # These identities bind the frozen stimuli/scoring/transport to the run.
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("reader.py", "reader_api.py", "protocol.md", "study.py")}


def prepare(directory):
    directory = Path(directory).resolve()
    if directory.is_relative_to(ROOT.parents[1]):
        raise ValueError("run artifacts must be outside the repository")
    directory.mkdir(parents=True, exist_ok=False)
    inputs, metadata, truth = build()
    freeze(directory / "reader-inputs.json", inputs)
    freeze(directory / "evaluator-truth.json", {"metadata": metadata, "rows": truth})
    freeze(directory / "manifest.json", {
        "schema": "ams-reader-run/1", "config": CONFIG, "repeats": REPEATS,
        "unique_inputs": len(inputs), "planned_calls": len(inputs) * REPEATS,
        "inputs_digest": digest(inputs), "truth_digest": digest({"metadata": metadata, "rows": truth}),
        "source_identity": source_identity(), "order_seed": 20261107,
        "budget_usd": 5, "input_rate_upper_per_million": 2.5,
        "output_rate_per_million": 10,
    })


def parse_response(body):
    """Keep invalid choice and invalid probability separate; never repair values."""
    failure = {"status": "parse_failure", "choice": None, "p_A": None}
    if not isinstance(body, dict):
        return failure
    if body.get("status") != "completed":
        return {"status": "incomplete", "choice": None, "p_A": None}
    output = body.get("output")
    if not isinstance(output, list) or any(not isinstance(m, dict) for m in output):
        return failure
    content = []
    for message in output:
        if message.get("type") != "message":
            continue
        items = message.get("content")
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            return failure
        content.extend(items)
    if any(item.get("type") == "refusal" for item in content):
        return {"status": "refusal", "choice": None, "p_A": None}
    texts = [item.get("text") for item in content if item.get("type") == "output_text"]
    if any(not isinstance(text, str) for text in texts):
        return failure
    try:
        value = json.loads("".join(texts))
    except (ValueError, TypeError):
        value = None
    if not isinstance(value, dict) or set(value) != {"choice", "p_A"}:
        return {"status": "parse_failure", "choice": None, "p_A": None}
    choice = value["choice"] if value["choice"] in ("A", "B") else None
    probability = value["p_A"]
    if type(probability) not in (int, float) or not math.isfinite(probability) or not 0 <= probability <= 1:
        probability = None
    return {"status": "valid" if choice is not None and probability is not None else "invalid_value",
            "choice": choice, "p_A": probability}


def posterior(rows):
    weights, a_weights = defaultdict(F), defaultdict(F)
    for row in rows:
        weights[row["id"]] += F(row["weight"])
        if row["gold"] == "A":
            a_weights[row["id"]] += F(row["weight"])
    return {key: float(a_weights[key] / mass) for key, mass in weights.items()}


def score_cells(truth, responses, repeats=REPEATS):
    cells = {}
    pstar = posterior(truth)
    for cell in sorted({row["cell"] for row in truth}):
        rows = [row for row in truth if row["cell"] == cell]
        total = sum((F(row["weight"]) for row in rows), F()) * repeats
        correct = missing_choice = p_mass = brier = deviation = inconsistent = 0.0
        for row in rows:
            weight = float(F(row["weight"]) / total)
            for rep in range(repeats):
                result = responses.get((row["id"], rep), {})
                choice, p = result.get("choice"), result.get("p_A")
                correct += weight * (choice == row["gold"])
                missing_choice += weight * (choice is None)
                if p is not None:
                    p_mass += weight
                    brier += weight * (p - (row["gold"] == "A")) ** 2
                    deviation += weight * abs(p - pstar[row["id"]])
                    inconsistent += weight * (choice is not None and (
                        (p > .5 and choice == "B") or (p < .5 and choice == "A")))
        cells[cell] = {
            "accuracy": round(correct, 12), "invalid_choice_mass": round(missing_choice, 12),
            "probability_coverage": round(p_mass, 12),
            "brier_on_valid_probability": round(brier / p_mass, 12) if p_mass else None,
            "posterior_mae_on_valid_probability": round(deviation / p_mass, 12) if p_mass else None,
            "choice_probability_inconsistency_mass": round(inconsistent, 12),
        }
    return cells


def interaction(cells):
    a = lambda channel, scope: cells[channel + "/" + scope]["accuracy"]
    return round(a("X", "valid") - a("Y", "valid") - a("X", "irrelevant") + a("Y", "irrelevant"), 12)


def flip_scores(metadata, responses, repeats=REPEATS):
    lookup = {tuple(m[k] for k in ("channel", "scope", "record", "mapping", "row_order", "position")): i
              for i, m in metadata.items()}
    result = {}
    for channel, scope in product(("X", "Y"), ("valid", "irrelevant")):
        probabilities, signed, choices = [], [], []
        for record, row_order, position, rep in product(range(2), range(2), range(2), range(repeats)):
            ids = [lookup[(channel, scope, record, mapping, row_order, position)] for mapping in (0, 1)]
            a, b = [responses.get((i, rep), {}) for i in ids]
            if a.get("p_A") is not None and b.get("p_A") is not None:
                probabilities.append(abs(a["p_A"] - b["p_A"]))
                # Positive means tracking the displayed codebook, even in Q.
                signed.append((a["p_A"] - b["p_A"]) * (1 if record == 0 else -1))
            if a.get("choice") is not None and b.get("choice") is not None:
                choices.append(a["choice"] != b["choice"])
        mean = lambda xs: round(sum(xs) / len(xs), 12) if xs else None
        result[channel + "/" + scope] = {
            "planned_pairs": 8 * repeats, "valid_probability_pairs": len(probabilities),
            "mean_absolute_probability_change": mean(probabilities),
            "mean_mapping_aligned_probability_change": mean(signed),
            "valid_choice_pairs": len(choices), "choice_flip_rate": mean(choices),
        }
    return result


def summarize(inputs, metadata, truth, responses):
    expected = {(item["id"], rep) for item in inputs for rep in range(REPEATS)}
    if not set(responses) <= expected:
        raise ValueError("unknown or out-of-range response identity")
    cells = score_cells(truth, responses)
    by_repeat = []
    for rep in range(REPEATS):
        subset = {(i, 0): r for (i, j), r in responses.items() if j == rep}
        rep_cells = score_cells(truth, subset, 1)
        by_repeat.append({"repeat": rep, "cells": rep_cells, "D": interaction(rep_cells)})
    by_order = []
    for row_order, position in product(range(2), repeat=2):
        rows = [r for r in truth if r["row_order"] == row_order and r["position"] == position]
        order_cells = score_cells(rows, responses)
        by_order.append({"row_order": row_order, "position": position,
                         "cells": order_cells, "D": interaction(order_cells)})
    ranges = []
    for item in inputs:
        values = [responses.get((item["id"], rep), {}).get("p_A") for rep in range(REPEATS)]
        if all(v is not None for v in values):
            ranges.append(max(values) - min(values))
    return {"schema": "ams-reader-result/1", "unique_inputs": len(inputs),
            "planned_calls": len(expected), "recorded_calls": len(responses),
            "status_counts": dict(sorted(Counter(r["status"] for r in responses.values()).items())),
            "unrecorded_calls": len(expected - set(responses)), "cells": cells, "D": interaction(cells),
            "flip_diagnostics": flip_scores(metadata, responses), "by_repeat": by_repeat,
            "by_order": by_order,
            "repeat_stability": {"complete_probability_inputs": len(ranges),
                                 "mean_probability_range": round(sum(ranges) / len(ranges), 12) if ranges else None,
                                 "max_probability_range": max(ranges) if ranges else None},
            "scope": "One authored finite routing task; repeats/order variants are not independent tasks. "
                     "Self-reported probabilities are observable outputs, not internal beliefs. "
                     "No-record reader baseline was not measured."}


def validate_saved(result):
    """Offline compact-summary consistency check, not a provider rerun/raw replay."""
    if result["schema"] != "ams-reader-result/1" or result["unique_inputs"] != 68 or result["planned_calls"] != 204:
        raise ValueError("unexpected study identity/counts")
    if result["recorded_calls"] + result["unrecorded_calls"] != 204:
        raise ValueError("call accounting")
    if sum(result["status_counts"].values()) != result["recorded_calls"]:
        raise ValueError("status accounting")
    if result["D"] != interaction(result["cells"]):
        raise ValueError("interaction differs from cells")
    if len(result["by_repeat"]) != 3 or len(result["by_order"]) != 4:
        raise ValueError("missing repeat/order report")
    for group in [result, *result["by_repeat"], *result["by_order"]]:
        if group["D"] != interaction(group["cells"]):
            raise ValueError("stratum interaction differs")
        for cell in group["cells"].values():
            if any(value is not None and not 0 <= value <= 1 for value in cell.values()):
                raise ValueError("out-of-range cell score")
    inputs, metadata, truth = build()
    if result["inputs_digest"] != digest(inputs) or result["truth_digest"] != digest({"metadata": metadata, "rows": truth}):
        raise ValueError("saved result uses different stimuli/truth")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("directory", type=Path)
    sub.add_parser("check-saved")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.directory)
        print("Prepared 68 unique inputs, 204 planned calls; no network requests.")
    else:
        validate_saved(load(ROOT / "reader-results.json"))
        print("PASS: saved reader summary consistency and stimulus binding; no API execution.")


if __name__ == "__main__":
    main()
