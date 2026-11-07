#!/usr/bin/env python3
"""Explicit, bounded official OpenAI execution; default verification stays offline."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import time
import urllib.error
import urllib.request

import reader

BASE = "https://api.openai.com/v1"


def now():
    return datetime.now(timezone.utc).isoformat()


def post(path, payload_file):
    """No redirects, retries, tools, account mutations or credential persistence."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ValueError("OPENAI_API_KEY must be supplied by the operator environment")
    request = urllib.request.Request(BASE + path, data=Path(payload_file).read_bytes(),
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": "application/json"})
    started, clock = now(), time.monotonic()
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
            raw_bytes = response.read()
            status = response.status
            request_id = response.headers.get("x-request-id")
    except urllib.error.HTTPError as exc:
        raw_bytes, status, request_id = exc.read(), exc.code, exc.headers.get("x-request-id")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"started_at": started, "finished_at": now(), "elapsed_seconds": time.monotonic() - clock,
                "http_status": None, "transport_error": type(exc).__name__,
                "raw_body": None, "request_id": None}
    try:
        raw, invalid_utf8_hex = raw_bytes.decode("utf-8"), None
    except UnicodeDecodeError:
        raw, invalid_utf8_hex = raw_bytes.decode("utf-8", errors="replace"), raw_bytes.hex()
    return {"started_at": started, "finished_at": now(), "elapsed_seconds": time.monotonic() - clock,
            "http_status": status, "transport_error": None, "raw_body": raw,
            "invalid_utf8_hex": invalid_utf8_hex, "request_id": request_id}


def checked(directory):
    directory = Path(directory).resolve()
    if directory.is_relative_to(reader.ROOT.parents[1]):
        raise ValueError("raw runs must stay outside the repository")
    manifest = reader.load(directory / "manifest.json")
    inputs = reader.load(directory / "reader-inputs.json")
    truth = reader.load(directory / "evaluator-truth.json")
    if reader.digest(inputs) != manifest["inputs_digest"] or reader.digest(truth) != manifest["truth_digest"]:
        raise ValueError("frozen stimulus/truth mismatch")
    if manifest["config"] != reader.CONFIG or manifest["repeats"] != reader.REPEATS or len(inputs) != 68:
        raise ValueError("unexpected execution configuration")
    return directory, manifest, inputs, truth


def parsed(receipt):
    if receipt["http_status"] != 200:
        return {"status": "transport_error" if receipt["http_status"] is None else "http_error",
                "choice": None, "p_A": None}
    try:
        body = json.loads(receipt["raw_body"])
        if not isinstance(body, dict):
            raise ValueError("body is not an object")
        return reader.parse_response(body)
    except (ValueError, TypeError, KeyError):
        return {"status": "parse_failure", "choice": None, "p_A": None}


def preflight(directory):
    directory, manifest, inputs, _ = checked(directory)
    if manifest["source_identity"] != reader.source_identity():
        raise ValueError("source changed after preparation; prepare a new run before any calls")
    folder = directory / "preflight"
    folder.mkdir(exist_ok=False)
    canary = {**manifest["config"], "input": [{"role": "user", "content":
              "这是接口格式检查。请返回 choice 为 A、p_A 为 1 的 JSON 对象。"}]}
    reader.freeze(folder / "canary-request.json", canary)
    receipt = post("/responses", folder / "canary-request.json")
    reader.freeze(folder / "canary-response.json", receipt)
    if parsed(receipt) != {"status": "valid", "choice": "A", "p_A": 1}:
        raise ValueError("format canary failed; retained receipt, no measurement calls sent")
    print("Format canary passed; counting exact model input tokens.", flush=True)

    def count(item):
        payload = {k: manifest["config"][k] for k in ("model", "text", "reasoning")}
        payload["input"] = item["messages"]
        path = folder / (item["id"] + "-count-request.json")
        reader.freeze(path, payload)
        result = post("/responses/input_tokens", path)
        reader.freeze(folder / (item["id"] + "-count-response.json"), result)
        if result["http_status"] != 200:
            raise ValueError("token count failed; retained receipt, no measurement calls sent")
        n = json.loads(result["raw_body"])["input_tokens"]
        if type(n) is not int or n <= 0:
            raise ValueError("invalid token count")
        return item["id"], n

    with ThreadPoolExecutor(max_workers=4) as pool:
        counts = dict(pool.map(count, inputs))
    _, metadata, _ = reader.build()
    matched = []
    for item in inputs:
        m = metadata[item["id"]]
        if m["scope"] == "valid":
            other = reader.digest(reader.render(m["channel"], "irrelevant", m["record"],
                                               m["mapping"], m["row_order"], m["position"]))
            matched.append(counts[item["id"]] == counts[other])
    # Reserve the worst output cap for EVERY planned call and the canary;
    # input reserve uses the higher cache-write rate, without assuming a discount.
    bound = (sum(counts.values()) * reader.REPEATS * manifest["input_rate_upper_per_million"]
             + (len(inputs) * reader.REPEATS + 1) * reader.CONFIG["max_output_tokens"] * 10
             + 2000 * manifest["input_rate_upper_per_million"]) / 1_000_000
    report = {"input_tokens": counts, "valid_irrelevant_token_matched": all(matched),
              "matched_pairs": len(matched), "estimated_upper_cost_usd": round(bound, 6),
              "pricing_date": "2026-11-07", "pricing_url": "https://developers.openai.com/api/docs/models/gpt-6.1-sol"}
    reader.freeze(directory / "preflight.json", report)
    if not all(matched) or bound > manifest["budget_usd"]:
        raise ValueError("token matching or budget gate failed; no measurement calls sent")
    print(json.dumps({k: v for k, v in report.items() if k != "input_tokens"}), flush=True)


def execute(directory):
    directory, manifest, inputs, _ = checked(directory)
    if manifest["source_identity"] != reader.source_identity():
        raise ValueError("source changed after preparation")
    pre = reader.load(directory / "preflight.json")
    if not pre["valid_irrelevant_token_matched"] or pre["estimated_upper_cost_usd"] > manifest["budget_usd"]:
        raise ValueError("failed preflight")
    calls = directory / "calls"
    calls.mkdir(exist_ok=False)  # no implicit resume, duplicate spending or overwrites
    jobs = [(item, rep) for rep in range(reader.REPEATS) for item in inputs]
    random.Random(manifest["order_seed"]).shuffle(jobs)
    reader.freeze(directory / "schedule.json", [[item["id"], rep] for item, rep in jobs])
    errors, completed = 0, 0

    def one(job):
        item, rep = job
        prefix = calls / (item["id"] + "-" + str(rep))
        payload = {**manifest["config"], "input": item["messages"]}
        request_path = prefix.with_suffix(".request.json")
        reader.freeze(request_path, payload)
        # A request file without a response means delivery may have happened.
        # Never automatically resend it.
        receipt = post("/responses", request_path)
        receipt.update(input_id=item["id"], repeat=rep, request_digest=reader.digest(payload))
        reader.freeze(prefix.with_suffix(".response.json"), receipt)
        return parsed(receipt)["status"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        for start in range(0, len(jobs), 4):
            statuses = list(pool.map(one, jobs[start:start + 4]))
            completed += len(statuses)
            errors += sum(s in ("http_error", "transport_error", "incomplete") for s in statuses)
            print(json.dumps({"completed": completed, "planned": len(jobs), "statuses": statuses}), flush=True)
            if errors >= 3:
                break
    reader.freeze(directory / "completion.json", {"completed_at": now(), "recorded_calls": completed,
                  "planned_calls": len(jobs), "stopped_after_service_or_incomplete_errors": errors >= 3})


def replay(directory):
    directory, manifest, inputs, truth = checked(directory)
    index = {item["id"]: item for item in inputs}
    responses, usages, latencies, returned_models, token_counts = {}, [], [], set(), {}
    raw_identity = {}
    for path in sorted((directory / "calls").glob("*.response.json")):
        receipt = reader.load(path)
        identity, rep = receipt["input_id"], receipt["repeat"]
        if identity not in index or type(rep) is not int or not 0 <= rep < reader.REPEATS:
            raise ValueError("unknown response identity")
        if path.name != f"{identity}-{rep}.response.json" or (identity, rep) in responses:
            raise ValueError("duplicate or mislabeled receipt")
        request_path = path.with_name(f"{identity}-{rep}.request.json")
        payload = reader.load(request_path)
        if payload != {**manifest["config"], "input": index[identity]["messages"]} or reader.digest(payload) != receipt["request_digest"]:
            raise ValueError("actual delivery differs from frozen input")
        responses[(identity, rep)] = parsed(receipt)
        raw_identity[path.name] = reader.digest(receipt)
        latencies.append(receipt["elapsed_seconds"])
        if receipt["http_status"] == 200:
            try:
                body = json.loads(receipt["raw_body"])
            except (ValueError, TypeError):
                body = {}
            if not isinstance(body, dict):
                body = {}
            if isinstance(body.get("model"), str):
                returned_models.add(body["model"])
            usage = body.get("usage")
            if isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
                                              for k in ("input_tokens", "output_tokens")):
                # Optional metadata cannot discard a scored failure receipt.
                normalized = {k: usage[k] for k in ("input_tokens", "output_tokens")}
                for field, key in (("input_tokens_details", "cached_tokens"), ("output_tokens_details", "reasoning_tokens")):
                    details = usage.get(field)
                    number = details.get(key) if isinstance(details, dict) else None
                    normalized[field] = {key: number if type(number) is int and number >= 0 else 0}
                usages.append(normalized)
                token_counts[identity, rep] = usage["input_tokens"]
    result = reader.summarize(inputs, truth["metadata"], truth["rows"], responses)
    pre = reader.load(directory / "preflight.json")
    result.update(config=manifest["config"], inputs_digest=manifest["inputs_digest"],
                  truth_digest=manifest["truth_digest"], execution_source_identity=manifest["source_identity"],
                  analysis_source_identity=reader.source_identity(), raw_receipts_digest=reader.digest(raw_identity),
                  provider="OpenAI official Responses API", returned_models=sorted(returned_models),
                  run_started_at=min((reader.load(p)["started_at"] for p in (directory / "calls").glob("*.response.json")), default=None),
                  run_finished_at=max((reader.load(p)["finished_at"] for p in (directory / "calls").glob("*.response.json")), default=None),
                  preflight={k: v for k, v in pre.items() if k != "input_tokens"})
    input_tokens = sum(u["input_tokens"] for u in usages)
    output_tokens = sum(u["output_tokens"] for u in usages)
    result["usage"] = {"calls_with_usage": len(usages), "input_tokens": input_tokens, "output_tokens": output_tokens,
                       "reasoning_tokens": sum(u.get("output_tokens_details", {}).get("reasoning_tokens", 0) for u in usages),
                       "cached_input_tokens": sum(u.get("input_tokens_details", {}).get("cached_tokens", 0) for u in usages),
                       "estimated_cost_usd_uncached": round((input_tokens * 2 + output_tokens * 10) / 1_000_000, 6),
                       "cost_is_invoice": False, "canary_excluded": True}
    result["token_counts"] = {"preflight_min": min(pre["input_tokens"].values()),
                              "preflight_max": max(pre["input_tokens"].values()),
                              "actual_min": min(token_counts.values()) if token_counts else None,
                              "actual_max": max(token_counts.values()) if token_counts else None,
                              "calls_with_token_count": len(token_counts),
                              "actual_matches_preflight": all(v == pre["input_tokens"][i] for (i, rep), v in token_counts.items()) if token_counts else None}
    result["latency_seconds"] = {"mean": round(sum(latencies) / len(latencies), 3) if latencies else None,
                                 "max": round(max(latencies), 3) if latencies else None}
    reader.validate_saved(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "run", "replay"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "preflight":
        preflight(args.directory)
    elif args.command == "run":
        execute(args.directory)
    else:
        result = replay(args.directory)
        if args.output:
            reader.freeze(args.output, result)
        print(json.dumps({"calls": result["recorded_calls"], "D": result["D"],
                          "cells": result["cells"], "usage": result["usage"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
