#!/usr/bin/env python3
"""Offline casebook calibration tool for the multilingual memory-use protocol.

Reads an architecture-independent casebook JSON (schema ``ams-memory-casebook/1``),
validates it, builds review sidecars and check reports, and renders a fully offline,
no-server HTML review surface. No network, telemetry, storage, training or scoring
happens here; this is material calibration for human reviewers only.

Subcommands::

    python3 casebook.py validate        --casebook cases.json [--reviews reviews.json]
    python3 casebook.py review-template --casebook cases.json [--out reviews.json]
    python3 casebook.py render          --casebook cases.json --out review.html [--reviews reviews.json]
    python3 casebook.py check-reviews   --casebook cases.json --reviews reviews.json

Adapters that build ``representations`` from source evidence must construct the
episode and coexistence strings with :func:`build_episodes` and
:func:`build_coexistence` so validation can check them deterministically.
"""
import argparse
import json
import sys
from pathlib import Path

CASEBOOK_SCHEMA = "ams-memory-casebook/1"
REVIEWS_SCHEMA = "ams-memory-reviews/1"

COVERAGES = ("resolved-message-window", "quoted-excerpts", "unresolved")
CONTEXT_KINDS = ("retrospective-next-user", "missing", "constructed")
LABELS = ("useful", "not-useful", "insufficient-context")
REVIEW_STATUSES = ("unreviewed", "draft", "confirmed")
CORRECTION_STATUSES = ("unreviewed", "none")

_UNKNOWN_TIME = "unknown"


def build_episodes(evidence):
    """Deterministic episode rendering: one line per evidence item, in order.

    Line format: ``<id> | <role> | <time> | <text>`` with ``time`` rendered as
    ``"unknown"`` when null. Adapters call this to fill ``representations.episodes``.
    """
    lines = []
    for item in evidence:
        when = item.get("time")
        when = _UNKNOWN_TIME if when is None else when
        lines.append("%s | %s | %s | %s" % (
            item.get("id", ""), item.get("role", _UNKNOWN_TIME), when, item.get("text", "")))
    return "\n".join(lines)


def build_coexistence(episodes, summary):
    """Deterministic coexistence rendering of episodes and summary."""
    return "EPISODES:\n%s\n\nSUMMARY:\n%s" % (episodes, summary)


def load_json(path):
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit("error: file not found: %s" % p)
    except json.JSONDecodeError as exc:
        raise SystemExit("error: invalid JSON in %s: %s" % (p, exc))


def _is_nonempty_str(value):
    return isinstance(value, str) and bool(value.strip())


# --------------------------------------------------------------------------- #
# Casebook validation
# --------------------------------------------------------------------------- #
def validate_casebook(data):
    """Return a list of human-readable errors; empty means the casebook is valid."""
    errors = []
    if not isinstance(data, dict):
        return ["top level must be a JSON object"]
    if data.get("schema") != CASEBOOK_SCHEMA:
        errors.append("schema must be %r" % CASEBOOK_SCHEMA)
    if not _is_nonempty_str(data.get("dataset_id")):
        errors.append("dataset_id must be a non-empty string")
    cases = data.get("cases")
    if not isinstance(cases, list):
        errors.append("cases must be a list")
        return errors

    seen_case_ids = set()
    for index, case in enumerate(cases):
        where = "cases[%d]" % index
        if not isinstance(case, dict):
            errors.append("%s must be an object" % where)
            continue
        case_id = case.get("case_id")
        if not _is_nonempty_str(case_id):
            errors.append("%s.case_id must be a non-empty string" % where)
        elif case_id in seen_case_ids:
            errors.append("%s has duplicate case_id %r" % (where, case_id))
        else:
            seen_case_ids.add(case_id)
        label = "%s (case_id=%r)" % (where, case_id)
        if not _is_nonempty_str(case.get("group_id")):
            errors.append("%s.group_id must be a non-empty string" % label)
        if case.get("split") != "exploration":
            errors.append("%s.split must be \"exploration\"" % label)

        evidence = _validate_memory_and_source(case, label, errors)
        _validate_context(case, label, errors)
        _validate_representations(case, evidence, label, errors)
        _validate_correction(case, evidence, label, errors)
    return errors


def _validate_memory_and_source(case, label, errors):
    evidence_ids = set()
    evidence = []
    memory = case.get("memory")
    if not isinstance(memory, dict):
        errors.append("%s.memory must be an object" % label)
    else:
        if not _is_nonempty_str(memory.get("id")):
            errors.append("%s.memory.id must be a non-empty string" % label)
        if not _is_nonempty_str(memory.get("text")):
            errors.append("%s.memory.text must be a non-empty string" % label)
        if not isinstance(memory.get("source_refs"), list):
            errors.append("%s.memory.source_refs must be a list" % label)

    source = case.get("source")
    if not isinstance(source, dict):
        errors.append("%s.source must be an object" % label)
        return evidence
    coverage = source.get("coverage")
    if coverage not in COVERAGES:
        errors.append("%s.source.coverage must be one of %s" % (label, list(COVERAGES)))
    raw_evidence = source.get("evidence")
    if not isinstance(raw_evidence, list):
        errors.append("%s.source.evidence must be a list" % label)
        raw_evidence = []
    for j, item in enumerate(raw_evidence):
        ewhere = "%s.source.evidence[%d]" % (label, j)
        if not isinstance(item, dict):
            errors.append("%s must be an object" % ewhere)
            continue
        eid = item.get("id")
        if not _is_nonempty_str(eid):
            errors.append("%s.id must be a non-empty string" % ewhere)
        elif eid in evidence_ids:
            errors.append("%s has duplicate evidence id %r" % (ewhere, eid))
        else:
            evidence_ids.add(eid)
        if not isinstance(item.get("role"), str):
            errors.append("%s.role must be a string" % ewhere)
        if not (item.get("time") is None or isinstance(item.get("time"), str)):
            errors.append("%s.time must be a string or null" % ewhere)
        if not isinstance(item.get("text"), str):
            errors.append("%s.text must be a string" % ewhere)
        locator = item.get("locator")
        if not isinstance(locator, dict):
            errors.append("%s.locator must be an object with file and pointer" % ewhere)
        else:
            if not _is_nonempty_str(locator.get("file")):
                errors.append("%s.locator.file must be a non-empty string" % ewhere)
            if not isinstance(locator.get("pointer"), str):
                errors.append("%s.locator.pointer must be a string" % ewhere)
        evidence.append(item)

    if source.get("complete_conversation") is not False:
        errors.append("%s.source.complete_conversation must be false; evidence is a window, not the full conversation" % label)
    sequence = source.get("sequence_verified")
    if not isinstance(sequence, bool):
        errors.append("%s.source.sequence_verified must be a boolean" % label)
    elif coverage == "unresolved":
        if raw_evidence:
            errors.append("%s.source.coverage \"unresolved\" must not carry evidence" % label)
        if sequence is not False:
            errors.append("%s.source.sequence_verified must be false for unresolved coverage" % label)
    elif coverage == "quoted-excerpts":
        if not raw_evidence:
            errors.append("%s.source.coverage \"quoted-excerpts\" requires at least one evidence item" % label)
        if sequence is not False:
            errors.append("%s.source.sequence_verified must be false for quoted excerpts" % label)
    elif coverage == "resolved-message-window":
        if not raw_evidence:
            errors.append("%s.source.coverage \"resolved-message-window\" requires at least one evidence item" % label)

    if isinstance(memory, dict) and isinstance(memory.get("source_refs"), list):
        _check_refs(memory["source_refs"], evidence_ids, label + ".memory.source_refs", "evidence id", errors)
        if coverage != "unresolved" and not memory["source_refs"]:
            errors.append("%s.memory.source_refs must cite at least one evidence id when coverage is %r" % (label, coverage))
    return evidence


def _check_refs(refs, evidence_ids, where, kind, errors, allow_external=False):
    for ref in refs:
        if not _is_nonempty_str(ref):
            errors.append("%s entries must be non-empty strings" % where)
            continue
        if ref in evidence_ids:
            continue
        if allow_external:
            continue
        errors.append("%s references unknown %s %r" % (where, kind, ref))


def _validate_context(case, label, errors):
    context = case.get("context")
    if not isinstance(context, dict):
        errors.append("%s.context must be an object" % label)
        return
    kind = context.get("kind")
    if kind not in CONTEXT_KINDS:
        errors.append("%s.context.kind must be one of %s" % (label, list(CONTEXT_KINDS)))
    text = context.get("text")
    if not (text is None or isinstance(text, str)):
        errors.append("%s.context.text must be a string or null" % label)
        text = None
    if kind == "missing":
        if text is not None:
            errors.append("%s.context.kind \"missing\" requires text to be null" % label)
        if context.get("refs") not in ([], None):
            errors.append("%s.context with missing kind must have empty refs" % label)
        if context.get("as_of") is not None:
            errors.append("%s.context with missing kind must have null as_of" % label)
    elif kind in ("retrospective-next-user", "constructed"):
        if not _is_nonempty_str(text):
            errors.append("%s.context.kind %r requires non-empty text" % (label, kind))
    if kind == "retrospective-next-user":
        refs = context.get("refs")
        if not isinstance(refs, list) or not refs:
            errors.append("%s.context.kind \"retrospective-next-user\" must cite at least one ref" % label)
    refs = context.get("refs")
    if refs is not None and not isinstance(refs, list):
        errors.append("%s.context.refs must be a list" % label)
    elif isinstance(refs, list):
        for ref in refs:
            if not _is_nonempty_str(ref):
                errors.append("%s.context.refs entries must be non-empty strings" % label)
    if context.get("as_of") is not None and not isinstance(context.get("as_of"), str):
        errors.append("%s.context.as_of must be a string or null" % label)
    if context.get("known_information") is not None:
        errors.append("%s.context.known_information must be null" % label)
    if context.get("recipient") != "answerer":
        errors.append("%s.context.recipient must be \"answerer\"" % label)
    if context.get("purpose") != "background":
        errors.append("%s.context.purpose must be \"background\"" % label)
    if context.get("already_selected") != []:
        errors.append("%s.context.already_selected must be []" % label)
    if context.get("budget_tokens") is not None:
        errors.append("%s.context.budget_tokens must be null (do not encode a token budget as string length)" % label)


def _validate_representations(case, evidence, label, errors):
    reps = case.get("representations")
    if not isinstance(reps, dict):
        errors.append("%s.representations must be an object" % label)
        return
    for key in ("episodes", "summary", "coexistence"):
        if not isinstance(reps.get(key), str):
            errors.append("%s.representations.%s must be a string" % (label, key))
    if not isinstance(reps.get("episodes"), str) or not isinstance(reps.get("summary"), str) \
            or not isinstance(reps.get("coexistence"), str):
        return
    expected_episodes = build_episodes(evidence)
    if reps["episodes"] != expected_episodes:
        errors.append("%s.representations.episodes must equal build_episodes(source.evidence)" % label)
    memory = case.get("memory")
    if isinstance(memory, dict) and reps["summary"] != memory.get("text"):
        errors.append("%s.representations.summary must equal memory.text" % label)
    if not reps["summary"]:
        errors.append("%s.representations.summary must be a non-empty string" % label)
    if reps["coexistence"] != build_coexistence(reps["episodes"], reps["summary"]):
        errors.append("%s.representations.coexistence must equal build_coexistence(episodes, summary)" % label)


def _validate_correction(case, evidence, label, errors):
    correction = case.get("correction_candidate")
    if not isinstance(correction, dict):
        errors.append("%s.correction_candidate must be an object" % label)
        return
    if correction.get("status") not in CORRECTION_STATUSES:
        errors.append("%s.correction_candidate.status must be one of %s" % (label, list(CORRECTION_STATUSES)))
    evidence_ids = {item["id"] for item in evidence if _is_nonempty_str(item.get("id"))}
    if not isinstance(correction.get("evidence_ids"), list):
        errors.append("%s.correction_candidate.evidence_ids must be a list" % label)
    else:
        _check_refs(correction["evidence_ids"], evidence_ids, label + ".correction_candidate.evidence_ids", "evidence id", errors)


# --------------------------------------------------------------------------- #
# Review sidecar validation
# --------------------------------------------------------------------------- #
def validate_reviews(data, casebook):
    """Return a list of review-sidecar errors; empty means the sidecar is valid."""
    errors = []
    if not isinstance(data, dict):
        return ["reviews top level must be a JSON object"]
    if data.get("schema") != REVIEWS_SCHEMA:
        errors.append("reviews schema must be %r" % REVIEWS_SCHEMA)
    if data.get("dataset_id") != casebook.get("dataset_id"):
        errors.append("reviews dataset_id %r does not match casebook dataset_id %r"
                      % (data.get("dataset_id"), casebook.get("dataset_id")))
    reviews = data.get("reviews")
    if not isinstance(reviews, list):
        errors.append("reviews must be a list")
        return errors

    case_ids = {case["case_id"] for case in casebook.get("cases", []) if isinstance(case, dict)}
    cases_by_id = {case["case_id"]: case for case in casebook.get("cases", [])
                   if isinstance(case, dict) and isinstance(case.get("case_id"), str)}
    seen = set()
    for index, review in enumerate(reviews):
        where = "reviews[%d]" % index
        if not isinstance(review, dict):
            errors.append("%s must be an object" % where)
            continue
        case_id = review.get("case_id")
        if not _is_nonempty_str(case_id):
            errors.append("%s.case_id must be a non-empty string" % where)
        elif case_id not in case_ids:
            errors.append("%s references unknown case_id %r" % (where, case_id))
        elif case_id in seen:
            errors.append("%s has duplicate case_id %r" % (where, case_id))
        else:
            seen.add(case_id)
        label = "%s (case_id=%r)" % (where, case_id)
        status = review.get("status")
        if status not in REVIEW_STATUSES:
            errors.append("%s.status must be one of %s" % (label, list(REVIEW_STATUSES)))
        if review.get("label") is not None and review.get("label") not in LABELS:
            errors.append("%s.label must be null or one of %s" % (label, list(LABELS)))
        cs = review.get("context_sufficient")
        if cs is not None and not isinstance(cs, bool):
            errors.append("%s.context_sufficient must be a boolean or null" % label)
        for field in ("reviewer", "reviewed_at"):
            value = review.get(field)
            if value is not None and not isinstance(value, str):
                errors.append("%s.%s must be a string or null" % (label, field))
        if not isinstance(review.get("rationale"), str):
            errors.append("%s.rationale must be a string" % label)
        case = cases_by_id.get(case_id) if isinstance(case_id, str) else None
        _validate_review_state(review, case, label, errors)
    return errors


def _validate_review_state(review, case, label, errors):
    status = review.get("status")
    context_sufficient = review.get("context_sufficient")
    label_value = review.get("label")
    if status == "unreviewed":
        if label_value is not None or context_sufficient is not None \
                or review.get("reviewer") is not None or review.get("reviewed_at") is not None:
            errors.append("%s unreviewed must not carry a label, context decision, reviewer or timestamp" % label)
        return
    if status != "confirmed":
        return
    if not _is_nonempty_str(review.get("reviewer")):
        errors.append("%s confirmed requires a reviewer" % label)
    if not _is_nonempty_str(review.get("reviewed_at")):
        errors.append("%s confirmed requires reviewed_at" % label)
    if not _is_nonempty_str(review.get("rationale")):
        errors.append("%s confirmed requires a non-empty rationale" % label)
    if label_value is None:
        errors.append("%s confirmed requires a label" % label)
        return
    context_text = (case or {}).get("context", {}).get("text") if isinstance(case, dict) else None
    has_context = isinstance(context_text, str) and context_text != ""
    if label_value in ("useful", "not-useful"):
        if context_sufficient is not True:
            errors.append("%s confirmed %r requires context_sufficient=true" % (label, label_value))
        if not has_context:
            errors.append("%s confirmed %r requires a non-empty context text" % (label, label_value))
    elif label_value == "insufficient-context":
        if context_sufficient is not False:
            errors.append("%s confirmed \"insufficient-context\" requires context_sufficient=false" % label)


# --------------------------------------------------------------------------- #
# Template and aggregate
# --------------------------------------------------------------------------- #
def template_reviews(casebook):
    reviews = [{"case_id": case["case_id"], "status": "unreviewed", "reviewer": None,
                "reviewed_at": None, "context_sufficient": None, "label": None, "rationale": ""}
               for case in casebook.get("cases", [])]
    return {"schema": REVIEWS_SCHEMA, "dataset_id": casebook.get("dataset_id"), "reviews": reviews}


def aggregate(casebook, reviews):
    """Counts only: no raw texts, no per-case labels, no training gold."""
    cases = [case for case in casebook.get("cases", []) if isinstance(case, dict)]
    status_by_case = {case.get("case_id"): "unreviewed" for case in cases}
    label_by_case = {case.get("case_id"): None for case in cases}
    context_by_case = {case.get("case_id"): None for case in cases}
    for review in reviews.get("reviews", []):
        if not isinstance(review, dict):
            continue
        case_id = review.get("case_id")
        if case_id in status_by_case:
            status_by_case[case_id] = review.get("status")
            label_by_case[case_id] = review.get("label")
            context_by_case[case_id] = review.get("context_sufficient")

    status_counts = {status: 0 for status in REVIEW_STATUSES}
    for status in status_by_case.values():
        status_counts[status if status in status_counts else "unreviewed"] += 1
    label_counts = {"null": 0}
    label_counts.update({value: 0 for value in LABELS})
    for value in label_by_case.values():
        label_counts[value if value in LABELS else "null"] += 1
    context_counts = {"true": 0, "false": 0, "null": 0}
    for value in context_by_case.values():
        context_counts["true" if value is True else "false" if value is False else "null"] += 1

    groups = {}
    for case in cases:
        group = case.get("group_id")
        entry = groups.setdefault(group, {"cases": 0, "status": {s: 0 for s in REVIEW_STATUSES}})
        entry["cases"] += 1
        entry["status"][status_by_case[case.get("case_id")]] += 1

    return {
        "schema": "ams-memory-review-aggregate/1",
        "dataset_id": casebook.get("dataset_id"),
        "totals": {"cases": len(cases), "groups": len(groups), "sidecar_reviews": len(reviews.get("reviews", []))},
        "status_counts": status_counts,
        "label_counts": label_counts,
        "context_sufficient_counts": context_counts,
        "by_group": groups,
        "notes": [
            "Group IDs group related cases; equal group IDs are not independent samples.",
            "The sidecar may contain only a subset of cases; absent cases count as unreviewed.",
            "Insufficient-context is a reviewed outcome and is distinct from unreviewed.",
            "Counts only: no raw texts and no per-case label export.",
        ],
    }


# --------------------------------------------------------------------------- #
# HTML rendering
# --------------------------------------------------------------------------- #
def _embed_json(payload):
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c")


def render_html(casebook, reviews):
    payload = {"casebook": casebook, "reviews": reviews}
    return HTML_HEAD + _embed_json(payload) + HTML_TAIL


HTML_HEAD = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Memory casebook calibration</title>
<style>
:root{color-scheme:light;--bg:#f5f6f8;--panel:#fff;--line:#d7dce3;--ink:#1b232e;--muted:#59636f;--accent:#0f6f6f;--accent-ink:#fff;--warn:#7a5200;--warn-bg:#fff4dd;--ok:#1d6f45;--bad:#8a2b2b;--chip:#eef1f5;}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif;letter-spacing:0}
h1{font-size:18px;margin:0}
h2{font-size:15px;margin:18px 0 6px}
h3{font-size:13px;margin:12px 0 4px;color:var(--muted);text-transform:uppercase}
a{color:var(--accent)}
header.top{background:#fff;border-bottom:1px solid var(--line);padding:12px 16px;position:sticky;top:0;z-index:5}
.top-row{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;max-width:1400px;margin:0 auto}
.top-meta{color:var(--muted);font-size:13px}
button{font:inherit;cursor:pointer;border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:6px;padding:6px 12px}
button:hover{border-color:var(--accent)}
button.primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
button.primary:hover{filter:brightness(1.05)}
.banner{max-width:1400px;margin:8px auto 0;padding:8px 12px;border:1px solid var(--line);border-radius:6px;background:#fff;font-size:13px;color:var(--muted)}
.banner.warn{background:var(--warn-bg);border-color:#e6cf9c;color:var(--warn)}
.layout{display:grid;grid-template-columns:340px minmax(0,1fr);gap:16px;padding:16px;max-width:1400px;margin:0 auto;align-items:start}
@media (max-width:920px){.layout{grid-template-columns:1fr}}
aside{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;position:sticky;top:96px;max-height:calc(100vh - 120px);overflow:auto}
@media (max-width:920px){aside{position:static;max-height:320px}header.top{position:static}}
li.case-btn button{display:block;width:100%;text-align:left;border:0;padding:0;background:transparent}
summary{cursor:pointer;font-weight:600}
.context-body{max-height:420px;overflow:auto}
.filters{display:grid;gap:8px;margin-bottom:12px}
label.field{display:block;font-size:12px;color:var(--muted);margin:8px 0 2px}
input[type=text],select,textarea{width:100%;font:inherit;color:var(--ink);background:#fff;border:1px solid var(--line);border-radius:6px;padding:6px 8px}
textarea{min-height:72px;resize:vertical}
ul.cases{list-style:none;margin:0;padding:0;display:grid;gap:6px}
li.case-btn{border:1px solid var(--line);border-radius:6px;padding:8px;cursor:pointer;background:#fff}
li.case-btn:hover{border-color:var(--accent)}
li.case-btn.active{border-color:var(--accent);box-shadow:inset 3px 0 0 var(--accent)}
.case-id{font-weight:600;word-break:break-word}
.case-sub{font-size:12px;color:var(--muted);word-break:break-word}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.chip{font-size:11px;border:1px solid var(--line);border-radius:999px;padding:1px 7px;background:var(--chip);color:var(--muted);overflow-wrap:anywhere;white-space:normal}
.chip.ok{background:#e6f4ec;color:var(--ok);border-color:#bfe3cd}
.chip.bad{background:#fbeaea;color:var(--bad);border-color:#eec4c4}
.chip.warn{background:var(--warn-bg);color:var(--warn);border-color:#e6cf9c}
main.detail{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;min-width:0}
.block{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:10px 0;background:#fff}
.block.subject{background:#f8fafb}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
.pre{white-space:pre-wrap;word-break:break-word}
.evidence{border-left:3px solid var(--accent);padding:6px 0 6px 10px;margin:8px 0}
.evidence .meta{font-size:12px;color:var(--muted)}
.context-note{font-size:12px;color:var(--warn)}
.rep-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
@media (max-width:1100px){.rep-grid{grid-template-columns:1fr}}
.rep{border:1px solid var(--line);border-radius:6px;padding:8px}
.rep h4{margin:0 0 6px;font-size:12px;color:var(--muted);text-transform:uppercase}
.radios{display:flex;flex-wrap:wrap;gap:12px;margin:4px 0 8px}
.radios label{display:inline-flex;align-items:center;gap:5px;font-size:13px}
.form-msg{font-size:13px;margin-top:8px;min-height:18px}
.form-msg.err{color:var(--bad)}
.form-msg.ok{color:var(--ok)}
.status-line{font-size:12px;color:var(--muted);margin-top:4px}
.empty{color:var(--muted)}
footer{padding:16px;max-width:1400px;margin:0 auto;color:var(--muted);font-size:12px}
</style>
</head>
<body>
<header class="top">
  <div class="top-row">
    <div>
      <h1>Memory casebook 材料校准</h1>
      <div class="top-meta">dataset: <span id="dataset" class="mono"></span> · <span id="counts"></span></div>
    </div>
    <div><button id="download" class="primary">下载 reviews JSON</button></div>
  </div>
  <p class="banner">这是<strong>材料校准</strong>界面，用于人工记录“在给定情境下这条记忆是否值得送入 answerer”。它<strong>不训练任何模型、不计算准确率</strong>，也不证明真实偏好或线上效果。</p>
  <p class="banner warn">情境来源按每个案例的 kind 标明：历史消息的回顾性重建、明确构造的情境，或缺失。它们并不证明当时生产系统已拥有该派生记忆。修改仅保留在当前页面内存，请下载 JSON 保存。</p>
</header>
<div class="layout">
  <aside>
    <div class="filters">
      <div><label class="field" for="q">搜索 case / group / 文本</label><input type="text" id="q" placeholder="case_id、group_id、memory 或 evidence 文本"></div>
      <div><label class="field" for="cov">来源覆盖</label><select id="cov"><option value="all">全部</option><option value="resolved-message-window">resolved-message-window</option><option value="quoted-excerpts">quoted-excerpts</option><option value="unresolved">unresolved</option></select></div>
      <div><label class="field" for="ctx">情境</label><select id="ctx"><option value="all">全部</option><option value="has">有情境</option><option value="missing">缺情境</option></select></div>
    </div>
    <ul class="cases" id="case-list"></ul>
  </aside>
  <main class="detail" id="detail"></main>
</div>
<footer>完全离线页面：无网络请求、无浏览器本地存储、无 telemetry、无服务端。所有数据以 textContent 呈现。此处是材料校准，不是训练、准确率测量或真实偏好结论。</footer>
<script type="application/json" id="casebook-data">"""


HTML_TAIL = """</script>
<script>
(function () {
  var DATA = JSON.parse(document.getElementById('casebook-data').textContent);
  var CASES = DATA.casebook.cases || [];
  var state = new Map();
  function blank(id) {
    return {case_id: id, status: 'unreviewed', reviewer: null, reviewed_at: null,
            context_sufficient: null, label: null, rationale: ''};
  }
  CASES.forEach(function (c) { state.set(c.case_id, blank(c.case_id)); });
  ((DATA.reviews && DATA.reviews.reviews) || []).forEach(function (r) {
    var base = blank(r.case_id);
    Object.keys(base).forEach(function (k) { if (r[k] !== undefined) { base[k] = r[k]; } });
    state.set(r.case_id, base);
  });

  var filters = {q: '', coverage: 'all', context: 'all'};
  var selected = CASES.length ? CASES[0].case_id : null;
  var listEl = document.getElementById('case-list');
  var detailEl = document.getElementById('detail');
  var countsEl = document.getElementById('counts');
  document.getElementById('dataset').textContent = DATA.casebook.dataset_id || '(none)';

  function el(tag, text, cls) {
    var n = document.createElement(tag);
    if (text !== null && text !== undefined) { n.textContent = text; }
    if (cls) { n.className = cls; }
    return n;
  }
  function chip(text, cls) { return el('span', text, 'chip' + (cls ? ' ' + cls : '')); }
  function contextPresent(c) {
    var t = c.context || {};
    return t.kind !== 'missing' && typeof t.text === 'string' && t.text !== '';
  }
  function matches(c) {
    if (filters.coverage !== 'all' && (c.source || {}).coverage !== filters.coverage) { return false; }
    var has = contextPresent(c);
    if (filters.context === 'has' && !has) { return false; }
    if (filters.context === 'missing' && has) { return false; }
    var q = filters.q.trim().toLowerCase();
    if (q) {
      var parts = [c.case_id, c.group_id, (c.memory || {}).text];
      ((c.source || {}).evidence || []).forEach(function (e) { parts.push(e.text); });
      if (parts.join(' ').toLowerCase().indexOf(q) === -1) { return false; }
    }
    return true;
  }
  function statusChip(status) {
    if (status === 'confirmed') { return chip(status, 'ok'); }
    if (status === 'draft') { return chip(status, 'warn'); }
    return chip(status);
  }

  function renderList() {
    listEl.textContent = '';
    var shown = CASES.filter(matches);
    if (!shown.length) { listEl.appendChild(el('li', '没有匹配的 case', 'empty')); }
    shown.forEach(function (c) {
      var r = state.get(c.case_id);
      var li = el('li', null, 'case-btn' + (c.case_id === selected ? ' active' : ''));
      var choose = el('button');
      choose.type = 'button';
      choose.appendChild(el('div', c.case_id, 'case-id'));
      choose.appendChild(el('div', 'group: ' + c.group_id, 'case-sub'));
      var chips = el('div', null, 'chips');
      chips.appendChild(chip((c.source || {}).coverage || '?'));
      chips.appendChild(chip(contextPresent(c) ? '有情境' : '缺情境', contextPresent(c) ? '' : 'warn'));
      chips.appendChild(statusChip(r.status));
      choose.appendChild(chips);
      choose.addEventListener('click', function () { selected = c.case_id; renderList(); renderDetail(); });
      li.appendChild(choose);
      listEl.appendChild(li);
    });
    updateCounts();
  }

  function repView(label, text) {
    var box = el('div', null, 'rep');
    box.appendChild(el('h4', label));
    box.appendChild(el('div', text && text !== '' ? text : '(空)', 'pre mono'));
    return box;
  }

  function renderEvidence(box, c) {
    var src = c.source || {};
    var ev = src.evidence || [];
    box.appendChild(el('h3', '原消息（关联窗口，不是完整对话）'));
    if (!ev.length) {
      box.appendChild(el('div', '来源窗口未解析（' + (src.coverage || '?') + '）。不能据此推断完整对话。', 'empty'));
      return;
    }
    ev.forEach(function (e) {
      var d = el('div', null, 'evidence');
      d.appendChild(el('div', (e.id || '?') + ' · role=' + (e.role || 'unknown') + ' · time=' + (e.time === null ? 'null' : e.time), 'meta mono'));
      var loc = e.locator || {};
      d.appendChild(el('div', 'locator: ' + (loc.file || '?') + ' @ ' + (loc.pointer || '?'), 'meta mono'));
      d.appendChild(el('div', e.text, 'pre'));
      box.appendChild(d);
    });
  }

  function radioGroup(name, options, current, onPick) {
    var wrap = el('div', null, 'radios');
    options.forEach(function (opt) {
      var labelEl = el('label');
      var input = document.createElement('input');
      input.type = 'radio';
      input.name = name;
      input.value = opt.value;
      if (current === opt.value) { input.checked = true; }
      input.addEventListener('change', function () { onPick(opt.value); });
      labelEl.appendChild(input);
      labelEl.appendChild(el('span', opt.text));
      wrap.appendChild(labelEl);
    });
    return wrap;
  }

  function confirmBlockers(c, r) {
    var errs = [];
    if (!r.label) { errs.push('必须选择一个 label。'); }
    if (!r.reviewer || !r.reviewer.trim()) { errs.push('confirmed 需要 reviewer。'); }
    if (!r.rationale || !r.rationale.trim()) { errs.push('confirmed 需要非空 rationale。'); }
    if (r.label === 'useful' || r.label === 'not-useful') {
      if (!contextPresent(c)) { errs.push('useful / not-useful 需要非空 context 文本。'); }
      if (r.context_sufficient !== true) { errs.push('useful / not-useful 需要 context_sufficient=true。'); }
    }
    if (r.label === 'insufficient-context' && r.context_sufficient !== false) {
      errs.push('insufficient-context 需要 context_sufficient=false。');
    }
    return errs;
  }

  function buildForm(c, r) {
    function edited() {
      r.status = 'draft';
      r.reviewed_at = null;
      refreshStatus();
      msg.textContent = '已修改，状态为 draft；需要重新确认。请下载 JSON 保存。';
      msg.className = 'form-msg';
      renderList();
    }
    var box = el('div', null, 'block');
    box.appendChild(el('h3', '校准标注'));
    box.appendChild(el('p', '在给定情境下，这条 memory 对 answerer 的背景是否有增量价值？缺情境必须与未审阅分开。', 'case-sub'));

    box.appendChild(el('label', 'label', 'field'));
    box.appendChild(radioGroup('label-' + c.case_id, [
      {value: 'useful', text: 'useful'},
      {value: 'not-useful', text: 'not-useful'},
      {value: 'insufficient-context', text: 'insufficient-context'}
    ], r.label, function (v) { r.label = v; edited(); }));

    box.appendChild(el('label', 'context_sufficient', 'field'));
    box.appendChild(radioGroup('cs-' + c.case_id, [
      {value: 'true', text: '情境充分 true'},
      {value: 'false', text: '情境不足 false'},
      {value: 'unset', text: '未定 null'}
    ], r.context_sufficient === true ? 'true' : r.context_sufficient === false ? 'false' : 'unset',
      function (v) { r.context_sufficient = v === 'unset' ? null : (v === 'true'); edited(); }));

    box.appendChild(el('label', 'reviewer', 'field'));
    var reviewer = document.createElement('input');
    reviewer.type = 'text';
    reviewer.value = r.reviewer || '';
    reviewer.addEventListener('input', function () { r.reviewer = reviewer.value; edited(); });
    box.appendChild(reviewer);

    box.appendChild(el('label', 'rationale', 'field'));
    var rationale = document.createElement('textarea');
    rationale.value = r.rationale || '';
    rationale.addEventListener('input', function () { r.rationale = rationale.value; edited(); });
    box.appendChild(rationale);

    var msg = el('div', null, 'form-msg');
    var statusLine = el('div', null, 'status-line');
    function refreshStatus() {
      var badge = detailEl.querySelector('[data-review-status]');
      if (badge) { badge.textContent = r.status; badge.className = 'chip' + (r.status === 'confirmed' ? ' ok' : r.status === 'draft' ? ' warn' : ''); }
      statusLine.textContent = 'status=' + r.status + ' · reviewed_at=' + (r.reviewed_at === null ? 'null' : r.reviewed_at);
    }
    refreshStatus();

    var actions = el('div');
    actions.style.marginTop = '8px';
    actions.style.display = 'flex';
    actions.style.gap = '8px';
    var saveBtn = el('button', '保存草稿');
    saveBtn.addEventListener('click', function () {
      r.status = 'draft';
      r.reviewed_at = new Date().toISOString();
      msg.className = 'form-msg ok';
      msg.textContent = '已保存草稿（仅本地内存，刷新会丢失，请下载 JSON）。';
      refreshStatus();
      renderList();
    });
    var confirmBtn = el('button', '确认', 'primary');
    confirmBtn.addEventListener('click', function () {
      var blockers = confirmBlockers(c, r);
      if (blockers.length) {
        msg.className = 'form-msg err';
        msg.textContent = '无法确认：' + blockers.join(' ');
        return;
      }
      r.status = 'confirmed';
      r.reviewed_at = new Date().toISOString();
      msg.className = 'form-msg ok';
      msg.textContent = '已确认（仅本地内存，请下载 JSON 保存）。';
      refreshStatus();
      renderList();
    });
    actions.appendChild(saveBtn);
    actions.appendChild(confirmBtn);
    box.appendChild(actions);
    box.appendChild(statusLine);
    box.appendChild(msg);
    return box;
  }

  function renderDetail() {
    detailEl.textContent = '';
    var c = CASES.filter(function (x) { return x.case_id === selected; })[0];
    if (!c) { detailEl.appendChild(el('p', '没有可显示的 case。', 'empty')); return; }
    var r = state.get(c.case_id);
    var src = c.source || {};

    var header = el('div');
    header.appendChild(el('h2', 'case ' + c.case_id));
    var chips = el('div', null, 'chips');
    chips.appendChild(chip('group: ' + c.group_id));
    chips.appendChild(chip('split: ' + c.split));
    chips.appendChild(chip('coverage: ' + (src.coverage || '?')));
    chips.appendChild(chip('sequence_verified: ' + String(src.sequence_verified)));
    chips.appendChild(chip('complete_conversation: ' + String(src.complete_conversation)));
    var reviewBadge = statusChip(r.status);
    reviewBadge.setAttribute('data-review-status', '');
    chips.appendChild(reviewBadge);
    header.appendChild(chips);
    detailEl.appendChild(header);

    var mem = el('div', null, 'block subject');
    mem.appendChild(el('h3', '派生 memory'));
    mem.appendChild(el('div', (c.memory || {}).text || '(空)', 'pre'));
    mem.appendChild(el('div', 'memory id: ' + ((c.memory || {}).id || '?') + ' · source_refs: ' + JSON.stringify((c.memory || {}).source_refs || []), 'case-sub mono'));
    detailEl.appendChild(mem);

    var srcBox = el('details', null, 'block');
    srcBox.appendChild(el('summary', '原消息与来源定位'));
    renderEvidence(srcBox, c);

    var reps = c.representations || {};
    var repBox = el('details', null, 'block');
    repBox.appendChild(el('summary', '比较三种表示'));
    repBox.appendChild(el('h3', '三种表示'));
    var grid = el('div', null, 'rep-grid');
    grid.appendChild(repView('episodes（原消息窗口）', reps.episodes));
    grid.appendChild(repView('summary（概括）', reps.summary));
    grid.appendChild(repView('coexistence（并存）', reps.coexistence));
    repBox.appendChild(grid);

    var ctx = el('div', null, 'block');
    var ct = c.context || {};
    var contextTitle = ct.kind === 'constructed' ? '构造情境' : ct.kind === 'missing' ? '情境缺失' : '回顾性情境（后续 user 消息及有限前文）';
    ctx.appendChild(el('h3', contextTitle));
    ctx.appendChild(el('div', 'kind=' + ct.kind + ' · as_of=' + (ct.as_of === null ? 'null' : ct.as_of) + ' · recipient=' + ct.recipient + ' · purpose=' + ct.purpose, 'context-note mono'));
    if (contextPresent(c)) { ctx.appendChild(el('div', ct.text, 'pre context-body')); }
    else { ctx.appendChild(el('div', '情境缺失。仅可确认 insufficient-context，不能标 useful / not-useful。', 'empty')); }
    ctx.appendChild(el('div', 'refs: ' + JSON.stringify(ct.refs || []) + ' · 情境来源以 kind 为准；不证明当时的生产记忆可用性。', 'case-sub'));
    detailEl.appendChild(ctx);

    var corr = el('details', null, 'block');
    corr.appendChild(el('summary', '纠正候选线索'));
    corr.appendChild(el('h3', '纠正候选（检索线索，不等于真实纠正标签）'));
    var cc = c.correction_candidate || {};
    corr.appendChild(el('div', 'status=' + cc.status + ' · evidence_ids=' + JSON.stringify(cc.evidence_ids || []), 'mono'));

    var diag = null;
    if (c.diagnostics !== undefined) {
      diag = el('details', null, 'block');
      diag.appendChild(el('summary', '来源限制与适配记录'));
      diag.appendChild(el('h3', 'diagnostics（原样保留）'));
      diag.appendChild(el('div', JSON.stringify(c.diagnostics, null, 2), 'pre mono'));
    }

    detailEl.appendChild(buildForm(c, r));
    detailEl.appendChild(srcBox);
    detailEl.appendChild(repBox);
    detailEl.appendChild(corr);
    if (diag) { detailEl.appendChild(diag); }
  }

  function updateCounts() {
    var counts = {unreviewed: 0, draft: 0, confirmed: 0};
    CASES.forEach(function (c) { counts[state.get(c.case_id).status] += 1; });
    countsEl.textContent = CASES.length + ' cases · ' + counts.confirmed + ' confirmed · ' + counts.draft + ' draft · ' + counts.unreviewed + ' unreviewed';
  }

  function refilter() {
    var shown = CASES.filter(matches);
    if (!shown.some(function (c) { return c.case_id === selected; })) { selected = shown.length ? shown[0].case_id : null; }
    renderList();
    renderDetail();
  }

  document.getElementById('q').addEventListener('input', function (e) { filters.q = e.target.value; refilter(); });
  document.getElementById('cov').addEventListener('change', function (e) { filters.coverage = e.target.value; refilter(); });
  document.getElementById('ctx').addEventListener('change', function (e) { filters.context = e.target.value; refilter(); });

  document.getElementById('download').addEventListener('click', function () {
    var out = {
      schema: 'ams-memory-reviews/1',
      dataset_id: DATA.casebook.dataset_id,
      reviews: CASES.map(function (c) {
        var r = state.get(c.case_id);
        return {case_id: r.case_id, status: r.status, reviewer: r.reviewer, reviewed_at: r.reviewed_at,
                context_sufficient: r.context_sufficient, label: r.label, rationale: r.rationale};
      })
    };
    var blob = new Blob([JSON.stringify(out, null, 2)], {type: 'application/json'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = (DATA.casebook.dataset_id || 'casebook') + '.reviews.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  });

  renderList();
  renderDetail();
  updateCounts();
})();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _print_errors(errors, kind):
    for err in errors:
        print("- " + err, file=sys.stderr)
    print("FAIL: %d %s error(s)" % (len(errors), kind), file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="casebook.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a casebook and, optionally, a review sidecar")
    p_validate.add_argument("--casebook", required=True)
    p_validate.add_argument("--reviews")

    p_template = sub.add_parser("review-template", help="write an all-unreviewed review sidecar")
    p_template.add_argument("--casebook", required=True)
    p_template.add_argument("--out")

    p_render = sub.add_parser("render", help="render a fully offline HTML review surface")
    p_render.add_argument("--casebook", required=True)
    p_render.add_argument("--out", required=True)
    p_render.add_argument("--reviews")

    p_check = sub.add_parser("check-reviews", help="validate a sidecar and print pooled counts")
    p_check.add_argument("--casebook", required=True)
    p_check.add_argument("--reviews", required=True)

    args = parser.parse_args(argv)

    casebook = load_json(args.casebook)
    casebook_errors = validate_casebook(casebook)
    if casebook_errors:
        _print_errors(casebook_errors, "casebook")
        return 1

    reviews = None
    if getattr(args, "reviews", None):
        reviews = load_json(args.reviews)
        review_errors = validate_reviews(reviews, casebook)
        if review_errors:
            _print_errors(review_errors, "review")
            return 1

    if args.command == "validate":
        counts = {}
        for case in casebook["cases"]:
            coverage = case["source"]["coverage"]
            counts[coverage] = counts.get(coverage, 0) + 1
        groups = len({case["group_id"] for case in casebook["cases"]})
        summary = "OK: %d cases, %d groups, coverage=%s" % (len(casebook["cases"]), groups, counts)
        if reviews is not None:
            summary += ", %d review(s)" % len(reviews["reviews"])
        print(summary)
        return 0

    if args.command == "review-template":
        template = template_reviews(casebook)
        text = json.dumps(template, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print("wrote review template for %d case(s) to %s" % (len(template["reviews"]), args.out))
        else:
            sys.stdout.write(text)
        return 0

    if args.command == "render":
        embedded = reviews if reviews is not None else template_reviews(casebook)
        html = render_html(casebook, embedded)
        Path(args.out).write_text(html, encoding="utf-8")
        print("wrote offline review surface for %d case(s) to %s" % (len(casebook["cases"]), args.out))
        return 0

    if args.command == "check-reviews":
        report = aggregate(casebook, reviews)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
