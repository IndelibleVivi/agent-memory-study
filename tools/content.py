#!/usr/bin/env python3
"""Compile the authored research tree into the reader data projection.

The files under study/ are the only editable content source. This module is
the single owner of ordering, Markdown compilation, reverse failure-surface
membership, legacy search sections, and generated drift checks.
"""

from __future__ import annotations

import argparse
import copy
import json
import posixpath
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CONTENT_ROOT = ROOT / "study"
DATA_OUTPUT = ROOT / "data" / "materials.json"
JS_OUTPUT = ROOT / "assets" / "materials-data.js"
STUDY_KINDS = {
    "learning-note",
    "research-essay",
    "editorial-synthesis-with-deterministic-demo",
    "editorial-synthesis-with-recorded-experiment",
    "editorial-synthesis-with-proposed-experiment",
}
EXPERIMENT_KINDS = {
    "editorial-synthesis-with-deterministic-demo",
    "editorial-synthesis-with-recorded-experiment",
    "editorial-synthesis-with-proposed-experiment",
}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED_STUDY = {"id", "title", "kind", "date", "byline", "intro", "bodyFile"}
GENERATED_STUDY = {"bodyMarkdown", "bodyHtml", "sections"}
FORBIDDEN_BODY = re.compile(
    r"<(?:script|style|iframe|object|embed|form|input|button|textarea|select|"
    r"link|meta|base|svg|math|video|audio)\b",
    re.IGNORECASE,
)
FORBIDDEN_SCHEME = re.compile(r"^(?:javascript|vbscript|file|data):", re.IGNORECASE)
ROOM_FIELDS = {"heroTitle", "edition", "thesis", "intro", "invitation", "domains", "directions",
               "starts", "changes"}
REFERENCE_FIELDS = ("studyIds", "questionIds", "materialIds")
PRIVATE_TEXT = (
    re.compile(r"/Users/"),
    re.compile(r"file://", re.IGNORECASE),
    re.compile(r"\bwxid_", re.IGNORECASE),
    re.compile(r"Zotero/storage", re.IGNORECASE),
)


class ContentError(ValueError):
    """An authored content contract failed."""


def _error(where: str, message: str) -> ContentError:
    return ContentError(f"{where}: {message}")


def _path_label(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise _error(_path_label(path), "file is missing") from exc
    except json.JSONDecodeError as exc:
        raise _error(
            _path_label(path),
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
        ) from exc


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _browser_bytes(data: dict[str, Any]) -> bytes:
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"window.READING_ROOM = {encoded};\n".encode("utf-8")


def write_projection(data: dict[str, Any], output: Path = DATA_OUTPUT) -> None:
    """Write one deterministic compatibility JSON projection."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_json_bytes(data))


def write_browser_projection(data: dict[str, Any], output: Path = JS_OUTPUT) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_browser_bytes(data))


def _walk_strings(value: Any, where: str = "content"):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from _walk_strings(nested, f"{where}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _walk_strings(nested, f"{where}[{index}]")
    elif isinstance(value, str):
        yield where, value


def assert_public_content(data: Any) -> None:
    for where, text in _walk_strings(data):
        for pattern in PRIVATE_TEXT:
            match = pattern.search(text)
            if match:
                raise _error(where, f"private token {match.group(0)!r}")


def _slug(value: Any, where: str) -> str:
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise _error(where, "must be a lowercase ASCII slug")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(where, "must be non-empty text")
    return value


def _list(value: Any, where: str, *, nonempty: bool = False) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        raise _error(where, "must be a list" + (" with at least one item" if nonempty else ""))
    return value


def _text_list(value: Any, where: str, *, nonempty: bool = False) -> list[str]:
    values = _list(value, where, nonempty=nonempty)
    for index, item in enumerate(values):
        _text(item, f"{where}[{index}]")
    return values


def _exact(value: Any, fields: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise _error(where, f"fields must be exactly {sorted(fields)}")
    return value


def _object_list(value: Any, fields: set[str], where: str, *,
                 nonempty: bool = False) -> list[dict[str, Any]]:
    items = _list(value, where, nonempty=nonempty)
    for index, item in enumerate(items):
        _exact(item, fields, f"{where}[{index}]")
        for key in fields:
            _text(item[key], f"{where}[{index}].{key}")
    return items


def _ref_list(value: Any, known: set[str], where: str) -> list[str]:
    values = _text_list(value, where)
    unknown = set(values) - known
    if unknown:
        raise _error(where, f"dangling ids {sorted(unknown)}")
    if len(values) != len(set(values)):
        raise _error(where, "must not repeat ids")
    return values


def _unique_records(items: list[dict[str, Any]], where: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = _slug(item.get("id"), f"{where} id")
        if item_id in result:
            raise _error(where, f"duplicate id {item_id!r}")
        result[item_id] = item
    return result


def _content_path(base: Path, relative: Any, where: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise _error(where, "must be a non-empty repo-relative path")
    path = PurePosixPath(relative)
    if path.is_absolute() or "\\" in relative or any(
        part in {"", ".", ".."} or part.startswith(".") for part in path.parts
    ):
        raise _error(where, f"unsafe path {relative!r}")
    candidate = (base / path).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise _error(where, f"path escapes its content family: {relative!r}") from exc
    if not candidate.is_file():
        raise _error(where, f"file does not exist: {relative!r}")
    return candidate


def _strict_markdown(source: str, where: str, *, source_path: str = "", link_map: dict[str, str] | None = None) -> tuple[str, str, list[dict[str, str]]]:
    """Parse Markdown with maintained markdown-it-py; HTML is disabled."""
    try:
        from markdown_it import MarkdownIt
    except ModuleNotFoundError as exc:
        raise ContentError(
            "Markdown compilation requires markdown-it-py; run "
            "`python3 -m pip install -r tools/content-requirements.txt`."
        ) from exc

    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in normalized:
        raise _error(where, "contains a NUL byte")
    if FORBIDDEN_BODY.search(normalized):
        raise _error(where, "contains forbidden executable/embedded HTML")

    scanner = MarkdownIt("commonmark", {"html": True})
    for token in scanner.parse(normalized):
        for candidate in [token, *(token.children or [])]:
            if candidate.type in {"html_block", "html_inline"}:
                raise _error(where, "raw HTML is not allowed")
    parser = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable("table")
    default_validate = parser.validateLink
    def validate_link(target):
        if not default_validate(target) or FORBIDDEN_SCHEME.match(target):
            raise _error(where, "unsafe link destination")
        return True
    parser.validateLink = validate_link

    def reject_html(state):
        for token in state.tokens:
            if token.type in {"html_block", "html_inline"}:
                line = token.map[0] + 1 if token.map else "?"
                raise _error(where, f"raw HTML is not allowed (line {line})")

    def safe_links(state):
        for token in state.tokens:
            if token.type != "inline":
                continue
            for child in token.children or []:
                if child.type != "link_open":
                    continue
                destination = child.attrGet("href") or ""
                parsed = urlparse(destination)
                if FORBIDDEN_SCHEME.match(destination) or (
                    parsed.scheme and parsed.scheme.lower() not in {"http", "https", "mailto"}
                ):
                    raise _error(where, f"unsafe link destination {destination!r}")
                if source_path and not parsed.scheme and not destination.startswith(("#", "//")):
                    parts = urlsplit(destination)
                    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source_path), parts.path))
                    if resolved.startswith("../") or resolved.startswith("/"):
                        raise _error(where, "link escapes repository")
                    if link_map and resolved in link_map:
                        child.attrSet("href", "?study=" + link_map[resolved] + ("#" + parts.fragment if parts.fragment else ""))
                    else:
                        child.attrSet("href", urlunsplit(("", "", resolved, parts.query, parts.fragment)))
                child.attrSet("rel", "noreferrer noopener")

    parser.core.ruler.after("normalize", "ams_reject_html", reject_html)
    parser.core.ruler.after("linkify", "ams_safe_links", safe_links)
    body_html = parser.render(normalized).strip()
    if not body_html:
        raise _error(where, "Markdown body is empty")

    # The title/text projection is only for the legacy search index. Keep the
    # Markdown source as text so no second browser-side parser is introduced.
    sections: list[dict[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for line in normalized.splitlines():
        match = re.match(r"^##\s+(.+?)\s*#*\s*$", line)
        if match and not line.startswith("###"):
            if current_title is not None:
                sections.append({"title": current_title, "text": "\n".join(current_lines).strip()})
            current_title = match.group(1).strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)
    if current_title is not None:
        sections.append({"title": current_title, "text": "\n".join(current_lines).strip()})
    if not sections:
        sections = [{"title": "正文", "text": normalized.strip()}]
    # A brief learning note need not have headings. Empty headings are harmless
    # to search and are not a reason to require a research template.
    return normalized, body_html, sections


def _study_number(value: Any, where: str) -> str:
    if isinstance(value, int) and value > 0:
        return f"{value:02d}"
    if isinstance(value, str) and re.fullmatch(r"\d{2,}", value):
        return value
    raise _error(where, "must be a positive integer or a zero-padded string")


def _validate_optional_study_fields(study: dict[str, Any], material_ids: set[str],
                                    study_ids: set[str]) -> None:
    where = f"study {study['id']}"
    for field in ("domains", "directionIds"):
        if field in study:
            _text_list(study[field], f"{where}.{field}")
    if "continuation" in study:
        continuation = study["continuation"]
        _exact(continuation, {"question", "why", "studyIds", "materialIds"},
               f"{where}.continuation")
        _text(continuation["question"], f"{where}.continuation.question")
        _text(continuation["why"], f"{where}.continuation.why")
        _ref_list(continuation["studyIds"], study_ids, f"{where}.continuation.studyIds")
        _ref_list(continuation["materialIds"], material_ids,
                  f"{where}.continuation.materialIds")
    if "changes" in study:
        changes = _object_list(
            study["changes"], {"date", "before", "after", "basis"}, f"{where}.changes"
        )
        for index, change in enumerate(changes):
            if not DATE.fullmatch(change["date"]):
                raise _error(f"{where}.changes[{index}].date", "must be YYYY-MM-DD")
    if "exercise" in study and study["exercise"] != "retrieval-sets":
        raise _error(f"{where}.exercise", "currently supports only 'retrieval-sets'")


def _optionally_empty_list(study: dict[str, Any], field: str, where: str) -> list[Any]:
    if field not in study:
        return []
    return _list(study[field], f"{where}.{field}")


def _validate_study(study: dict[str, Any], base: Path, material_ids: set[str],
                    study_ids: set[str], link_map: dict[str, str] | None = None) -> dict[str, Any]:
    if not isinstance(study, dict):
        raise _error("study entry", "must be an object")
    missing = REQUIRED_STUDY - set(study)
    if missing:
        raise _error(f"study {study.get('id', '[unknown]')}", f"missing fields {sorted(missing)}")
    duplicate = GENERATED_STUDY.intersection(study)
    if duplicate:
        raise _error(f"study {study['id']}",
                     f"authored JSON must not contain generated fields {sorted(duplicate)}")
    where = f"study {_slug(study['id'], 'study id')}"
    for field in ("title", "byline", "intro"):
        _text(study[field], f"{where}.{field}")
    if "subtitle" in study:
        _text(study["subtitle"], f"{where}.subtitle")
    if "number" in study:
        _study_number(study["number"], f"{where}.number")
    if study["kind"] not in STUDY_KINDS:
        raise _error(f"{where}.kind", f"unsupported kind {study['kind']!r}")
    if not DATE.fullmatch(str(study["date"])):
        raise _error(f"{where}.date", "must be YYYY-MM-DD")
    readings = _optionally_empty_list(study, "readings", where)
    for index, reading in enumerate(readings):
        _exact(reading, {"materialId", "label", "locator", "takeaway", "limit"},
               f"{where}.readings[{index}]")
        _slug(reading["materialId"], f"{where}.readings[{index}].materialId")
        if reading["materialId"] not in material_ids:
            raise _error(f"{where}.readings[{index}].materialId", "dangling material id")
        for field in ("label", "locator", "takeaway", "limit"):
            _text(reading[field], f"{where}.readings[{index}].{field}")
    external = _optionally_empty_list(study, "externalReadings", where)
    for index, reading in enumerate(external):
        _exact(reading, {"label", "kind", "url", "locator", "takeaway", "limit"},
               f"{where}.externalReadings[{index}]")
        for field in ("label", "kind", "url", "locator", "takeaway", "limit"):
            _text(reading[field], f"{where}.externalReadings[{index}].{field}")
        parsed = urlparse(reading["url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise _error(f"{where}.externalReadings[{index}].url", "must be an HTTPS URL")
    if "takeaways" in study:
        _object_list(study["takeaways"], {"title", "text"}, f"{where}.takeaways")
    for field in ("boundary", "closing"):
        if field in study:
            _text(study[field], f"{where}.{field}")
    _validate_optional_study_fields(study, material_ids, study_ids)

    if study["kind"] in EXPERIMENT_KINDS:
        if "artifactUrl" not in study:
            raise _error(where, "experiment study requires artifactUrl")
        artifact = PurePosixPath(study["artifactUrl"])
        if (artifact.is_absolute() or ".." in artifact.parts or artifact.parts[:1] != ("research",)
                or not (ROOT / artifact).is_file()):
            raise _error(f"{where}.artifactUrl", "must reference an existing public research file")
        _text(study.get("labTitle"), f"{where}.labTitle")
        _text(study.get("labIntro"), f"{where}.labIntro")
    elif any(key in study for key in ("artifactUrl", "resultsUrl", "policies", "scenarios",
                                      "labTitle", "labIntro", "recordedResults")):
        raise _error(where, "standalone study cannot claim a lab, artifact, or recorded result")
    if study["kind"] == "editorial-synthesis-with-proposed-experiment":
        if any(key in study for key in ("resultsUrl", "scenarios", "policies", "recordedResults")):
            raise _error(where, "proposed study cannot contain executed results or demo controls")
    if study["kind"] == "editorial-synthesis-with-recorded-experiment":
        result = PurePosixPath(study.get("resultsUrl", ""))
        if (result.is_absolute() or ".." in result.parts or result.parts[:1] != ("research",)
                or result.suffix != ".json" or not (ROOT / result).is_file()):
            raise _error(f"{where}.resultsUrl", "requires an existing public research JSON")
    if study["kind"] == "editorial-synthesis-with-deterministic-demo":
        policies = _object_list(
            study.get("policies"), {"id", "label", "description"}, f"{where}.policies",
            nonempty=True,
        )
        if [policy["id"] for policy in policies] != ["none", "frozen", "latest", "scoped"]:
            raise _error(f"{where}.policies", "must follow the supported deterministic engine order")
        _list(study.get("scenarios"), f"{where}.scenarios", nonempty=True)

    if "draft" in study:
        raise _error(f"{where}.draft", "drafts remain outside study/; review content and remove the marker before publication")

    body_path = _content_path(base.parent, study["bodyFile"], f"{where}.bodyFile")
    body_source = body_path.read_text(encoding="utf-8")
    body_markdown, body_html, sections = _strict_markdown(body_source, f"{where}.bodyFile", source_path="study/" + study["bodyFile"], link_map=link_map)
    compiled = copy.deepcopy(study)
    compiled.setdefault("readings", [])
    compiled.setdefault("externalReadings", [])
    compiled.setdefault("takeaways", [])
    compiled.setdefault("boundary", "")
    compiled.setdefault("closing", "")
    if compiled["kind"] in {"learning-note", "research-essay"}:
        compiled.setdefault("subtitle", "")
    compiled["sourcePath"] = "study/" + study["bodyFile"]
    compiled["bodyMarkdown"] = body_markdown
    compiled["bodyHtml"] = body_html
    compiled["sections"] = sections
    # bodyFile is a build input, not a deployed/public asset.
    compiled.pop("bodyFile", None)
    return compiled


def _validate_question(question: dict[str, Any], material_ids: set[str],
                       study_ids: set[str], finding_ids: set[str]) -> None:
    where = f"question {_slug(question.get('id'), 'question id')}"
    required = {"id", "title", "question", "intro", "judgment", "byline", "updated",
                "status", "explanations", "evidence", "materialIds", "studyIds",
                "findingIds"}
    missing = required - set(question)
    if missing:
        raise _error(where, f"missing fields {sorted(missing)}")
    for field in ("title", "question", "intro", "judgment", "byline"):
        _text(question[field], f"{where}.{field}")
    if question["status"] != "open":
        raise _error(f"{where}.status", "must be open")
    if not DATE.fullmatch(str(question["updated"])):
        raise _error(f"{where}.updated", "must be YYYY-MM-DD")
    _object_list(question["explanations"], {"title", "text"},
                 f"{where}.explanations", nonempty=True)
    _list(question["evidence"], f"{where}.evidence", nonempty=True)
    _ref_list(question["materialIds"], material_ids, f"{where}.materialIds")
    _ref_list(question["studyIds"], study_ids, f"{where}.studyIds")
    _ref_list(question["findingIds"], finding_ids, f"{where}.findingIds")
    if "nextTest" in question:
        _exact(question["nextTest"],
               {"question", "comparison", "success", "reviseWhen", "boundary"},
               f"{where}.nextTest")
    if "continuation" in question:
        continuation = question["continuation"]
        _exact(continuation, {"question", "why", "studyIds", "materialIds"},
               f"{where}.continuation")
        _ref_list(continuation["studyIds"], study_ids, f"{where}.continuation.studyIds")
        _ref_list(continuation["materialIds"], material_ids,
                  f"{where}.continuation.materialIds")
        _text(continuation["question"], f"{where}.continuation.question")
        _text(continuation["why"], f"{where}.continuation.why")
    if "nextTest" not in question and "continuation" not in question:
        raise _error(where, "requires nextTest or continuation")


def _validate_finding(finding: dict[str, Any], material_ids: set[str],
                      question_ids: set[str]) -> None:
    where = f"finding {_slug(finding.get('id'), 'finding id')}"
    required = {"id", "title", "byline", "updated", "status", "questionIds",
                "materialIds", "triggers", "claim", "when", "action", "avoid",
                "validation", "limit", "evidence", "applications"}
    missing = required - set(finding)
    if missing:
        raise _error(where, f"missing fields {sorted(missing)}")
    for field in ("title", "byline", "claim", "when", "action", "avoid",
                  "validation", "limit"):
        _text(finding[field], f"{where}.{field}")
    if finding["status"] != "proposed-transfer":
        raise _error(f"{where}.status", "must be proposed-transfer")
    if not DATE.fullmatch(str(finding["updated"])):
        raise _error(f"{where}.updated", "must be YYYY-MM-DD")
    _text_list(finding["triggers"], f"{where}.triggers", nonempty=True)
    _ref_list(finding["questionIds"], question_ids, f"{where}.questionIds")
    _ref_list(finding["materialIds"], material_ids, f"{where}.materialIds")
    _list(finding["evidence"], f"{where}.evidence", nonempty=True)
    _list(finding["applications"], f"{where}.applications")


def _validate_map(room: dict[str, Any], study_ids: set[str], question_ids: set[str],
                  material_ids: set[str]) -> dict[str, Any]:
    if not isinstance(room, dict):
        raise _error("study/map.json", "must be an object")
    unknown = set(room) - ROOM_FIELDS
    if unknown:
        raise _error("study/map.json", f"unknown fields {sorted(unknown)}")
    if "heroTitle" in room:
        _text(room["heroTitle"], "study/map.json.heroTitle")
    for field in ("edition", "thesis", "intro", "invitation"):
        if field not in room:
            raise _error("study/map.json", f"missing field {field!r}")
        _text(room[field], f"room.{field}")
    result = copy.deepcopy(room)
    for field in ("domains", "directions"):
        entries = _list(room[field], f"room.{field}", nonempty=field == "domains")
        ids = [entry.get("id") for entry in entries]
        if len(ids) != len(set(ids)):
            raise _error(f"room.{field}", "must not repeat ids")
        for index, entry in enumerate(entries):
            where = f"room.{field}[{index}]"
            _slug(entry.get("id"), f"{where}.id")
            for key in ("title", "intro"):
                _text(entry.get(key), f"{where}.{key}")
            for key in ("english", "question", "entry"):
                if key in entry:
                    _text(entry[key], f"{where}.{key}")
            for key in REFERENCE_FIELDS:
                if key in entry:
                    known = {"studyIds": study_ids, "questionIds": question_ids,
                             "materialIds": material_ids}[key]
                    _ref_list(entry[key], known, f"{where}.{key}")
    for index, start in enumerate(_list(room["starts"], "room.starts")):
        where = f"room.starts[{index}]"
        _exact(start, {"studyId", "kicker", "prompt"}, where)
        _ref_list([start["studyId"]], study_ids, f"{where}.studyId")
        _text(start["kicker"], f"{where}.kicker")
        _text(start["prompt"], f"{where}.prompt")
    for index, change in enumerate(_list(room["changes"], "room.changes")):
        where = f"room.changes[{index}]"
        _exact(change, {"date", "title", "text", "studyId"}, where)
        if not DATE.fullmatch(change["date"]):
            raise _error(f"{where}.date", "must be YYYY-MM-DD")
        _ref_list([change["studyId"]], study_ids, f"{where}.studyId")
        for key in ("title", "text"):
            _text(change[key], f"{where}.{key}")
    return result


def _ordered(items: list[dict[str, Any]], order_value: Any, order_key: str,
             family: str, id_field: str = "id") -> list[dict[str, Any]]:
    """Apply explicit preference order, then append unlisted records by date/id."""
    order = _text_list(order_value, f"study/catalog.json.{order_key}")
    if len(order) != len(set(order)):
        raise _error(f"study/catalog.json.{order_key}", "must not repeat ids")
    by_id = {item[id_field]: item for item in items}
    unknown = set(order) - set(by_id)
    if unknown:
        raise _error(f"study/catalog.json.{order_key}", f"unknown ids {sorted(unknown)}")
    date_field = "date" if family == "entry" else "updated"
    tail = sorted(
        (item for item_id, item in by_id.items() if item_id not in set(order)),
        key=lambda item: (str(item.get(date_field, "")), str(item[id_field])),
    )
    return [by_id[item_id] for item_id in order] + tail


def compile_content(content_root: Path = CONTENT_ROOT) -> dict[str, Any]:
    """Compile authored content without writing generated projections."""
    catalog = _read_json(content_root / "catalog.json")
    if not isinstance(catalog, dict):
        raise _error("study/catalog.json", "must be an object")
    required_catalog = {"title", "intro", "editorialNote", "filters", "atlas",
                        "sourceOrder", "inquiryOrder", "transferOrder", "entryOrder"}
    missing = required_catalog - set(catalog)
    if missing:
        raise _error("study/catalog.json", f"missing fields {sorted(missing)}")
    for field in ("title", "intro", "editorialNote"):
        _text(catalog[field], f"catalog.{field}")
    _text_list(catalog["filters"], "catalog.filters", nonempty=True)

    def load_family(folder: str) -> list[dict[str, Any]]:
        directory = content_root / folder
        if not directory.is_dir():
            raise _error(f"study/{folder}", "directory is missing")
        records = []
        for path in sorted(directory.glob("*.json")):
            record = _read_json(path)
            if not isinstance(record, dict):
                raise _error(_path_label(path), "must contain a JSON object")
            records.append(record)
        return records

    materials = load_family("sources")
    studies = load_family("entries")
    questions = load_family("inquiries")
    findings = load_family("transfers")
    material_by_id = _unique_records(materials, "material")
    question_by_id = _unique_records(questions, "question")
    finding_by_id = _unique_records(findings, "finding")
    study_by_id = _unique_records(studies, "study")
    material_ids, question_ids = set(material_by_id), set(question_by_id)
    finding_ids, study_ids = set(finding_by_id), set(study_by_id)

    materials = _ordered(materials, catalog["sourceOrder"], "sourceOrder", "source")
    questions = _ordered(questions, catalog["inquiryOrder"], "inquiryOrder", "inquiry")
    findings = _ordered(findings, catalog["transferOrder"], "transferOrder", "transfer")
    studies = _ordered(studies, catalog["entryOrder"], "entryOrder", "entry")
    # Malformed metadata is diagnosed by _validate_study, not by this link index.
    link_map = {"study/" + study["bodyFile"]: study["id"] for study in studies
                if isinstance(study.get("bodyFile"), str)}

    atlas = copy.deepcopy(catalog["atlas"])
    if not isinstance(atlas, dict):
        raise _error("catalog.atlas", "must be an object")
    surfaces = atlas.get("failureSurfaces")
    if not isinstance(surfaces, list):
        raise _error("catalog.atlas.failureSurfaces", "must be a list")
    surface_ids: set[str] = set()
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, dict):
            raise _error(f"catalog.atlas.failureSurfaces[{index}]", "must be an object")
        if "materialIds" in surface:
            raise _error(
                f"catalog.atlas.failureSurfaces[{index}].materialIds",
                "is generated from material failureSurfaces; do not author both sides",
            )
        surface_id = _slug(surface.get("id"), f"catalog.atlas.failureSurfaces[{index}].id")
        if surface_id in surface_ids:
            raise _error("catalog.atlas.failureSurfaces", f"duplicate id {surface_id!r}")
        surface_ids.add(surface_id)
    for material in materials:
        _ref_list(material.get("failureSurfaces", []), surface_ids,
                  f"material {material['id']}.failureSurfaces")
    for surface in surfaces:
        surface["materialIds"] = [
            material["id"] for material in materials
            if surface["id"] in material["failureSurfaces"]
        ]

    compiled = {
        "title": catalog["title"],
        "intro": catalog["intro"],
        "editorialNote": catalog["editorialNote"],
        "atlas": atlas,
        "filters": catalog["filters"],
        "materials": materials,
        "studies": [
            _validate_study(study, content_root / "entries", material_ids, study_ids, link_map)
            for study in studies
        ],
        "questions": questions,
        "findings": findings,
    }
    for question in questions:
        _validate_question(question, material_ids, study_ids, finding_ids)
    for finding in findings:
        _validate_finding(finding, material_ids, question_ids)
    for question in questions:
        for finding_id in question["findingIds"]:
            if question["id"] not in finding_by_id[finding_id]["questionIds"]:
                raise _error(f"question {question['id']}",
                             f"finding {finding_id} does not link back")
    for finding in findings:
        for question_id in finding["questionIds"]:
            if finding["id"] not in question_by_id[question_id]["findingIds"]:
                raise _error(f"finding {finding['id']}",
                             f"question {question_id} does not link back")

    map_path = content_root / "map.json"
    if map_path.is_file():
        compiled["room"] = _validate_map(
            _read_json(map_path), study_ids, question_ids, material_ids
        )
    if "room" in compiled:
        for field, collection in (("domains", "domains"), ("directionIds", "directions")):
            known = {x["id"] for x in compiled["room"][collection]}
            for study in studies:
                _ref_list(study.get(field, []), known, f"study {study['id']}.{field}")
    assert_public_content(compiled)
    return compiled


def check_projection(data: dict[str, Any], json_output: Path = DATA_OUTPUT,
                     js_output: Path = JS_OUTPUT) -> list[str]:
    """Return descriptions of generated drift; never rewrite files."""
    drift = []
    expected_json = _json_bytes(data)
    from tools import build
    expected_js = _browser_bytes(build.browser_projection(data))
    for path, expected in ((json_output, expected_json), (js_output, expected_js)):
        try:
            actual = path.read_bytes()
        except FileNotFoundError:
            drift.append(f"missing generated file: {_path_label(path)}")
            continue
        if actual != expected:
            drift.append(f"generated drift: {_path_label(path)}")
    return drift


def write_all(data: dict[str, Any], *, json_output: Path = DATA_OUTPUT,
              js_output: Path = JS_OUTPUT) -> None:
    write_projection(data, json_output)
    from tools import build
    write_browser_projection(build.browser_projection(data), js_output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, default=CONTENT_ROOT)
    parser.add_argument("--json-output", type=Path, default=DATA_OUTPUT)
    parser.add_argument("--js-output", type=Path, default=JS_OUTPUT)
    parser.add_argument("--write-json", action="store_true",
                        help="also write the generated data/materials.json compatibility projection")
    parser.add_argument("--check", action="store_true",
                        help="fail on drift without repairing it")
    args = parser.parse_args(argv)
    try:
        from tools import build
        data = build.validate_data(compile_content(args.content.resolve()))
        drift = check_projection(data, args.json_output, args.js_output)
        if args.check:
            if drift:
                raise ContentError("; ".join(drift) +
                                   "\nRun the content compiler without --check.")
        else:
            if args.write_json:
                write_projection(data, args.json_output)
            write_browser_projection(build.browser_projection(data), args.js_output)
        print(
            f"compiled {len(data['materials'])} materials, {len(data['studies'])} studies, "
            f"{len(data['questions'])} questions, {len(data['findings'])} findings"
        )
        return 0
    except ContentError as exc:
        print(f"content error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
