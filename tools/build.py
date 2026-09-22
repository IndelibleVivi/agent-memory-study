#!/usr/bin/env python3
"""Validate public reading-room data and build its browser/Zotero artifacts."""

from __future__ import annotations

import argparse
import copy
import json
import re
import struct
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATTERNS = (
    re.compile(r"/Users/"),
    re.compile(r"file://", re.IGNORECASE),
    re.compile(r"@chatroom", re.IGNORECASE),
    re.compile(r"\bwxid_", re.IGNORECASE),
    re.compile(r"Zotero/storage", re.IGNORECASE),
    re.compile(
        r"\b(?:repo-inspected|source-only-offline-probe|internal source inspection|"
        r"network-denied|temp-store|private runtime probe|offline probe)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:commit|sha|revision|rev)\s*[@:=#-]\s*[0-9a-f]{7,40}\b",
        re.IGNORECASE,
    ),
)
DISALLOWED_TRACKING_PATTERNS = (
    re.compile(r"google-analytics|googletagmanager", re.IGNORECASE),
    re.compile(r"plausible\.io|posthog|mixpanel|hotjar|segment\.com", re.IGNORECASE),
)
CLOUDFLARE_WEB_ANALYTICS_SRC = "https://static.cloudflareinsights.com/beacon.min.js"
CLOUDFLARE_WEB_ANALYTICS_TOKEN = "4e0929eca0504d43aca1cc1a1f30ffaf"
PUBLIC_COPY_PATHS = (
    "index.html",
    "site.webmanifest",
    "assets/app.js",
    "assets/seo.js",
    "assets/revision-study.js",
    "assets/reading-search.js",
    "assets/practice.js",
    "assets/styles.css",
    "assets/materials-data.js",
    "data/materials.json",
    "README.md",
    "NOTICE.md",
    "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTING.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "ZOTERO-IMPORT.md",
    "agent-memory-study.rdf",
)
PUBLIC_DOC_SUFFIXES = {".md"}
ICON_SIZES = {
    "assets/icons/ams-icon-512.png": 512,
    "assets/icons/ams-icon-192.png": 192,
    "assets/icons/apple-touch-icon.png": 180,
    "assets/icons/favicon-48.png": 48,
    "assets/icons/favicon-32.png": 32,
    "assets/icons/favicon-16.png": 16,
}
MANIFEST_ICONS = {
    "assets/icons/ams-icon-192.png": "192x192",
    "assets/icons/ams-icon-512.png": "512x512",
}
PUBLIC_RESEARCH_SUFFIXES = {".csv", ".js", ".json", ".jsonl", ".md", ".py", ".sha256", ".txt"}
NS = {
    "bib": "http://purl.org/net/biblio#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "link": "http://purl.org/rss/1.0/modules/link/",
    "prism": "http://prismstandard.org/namespaces/1.2/basic/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "vcard": "http://nwalsh.com/rdf/vCard#",
    "z": "http://www.zotero.org/namespaces/export#",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "materials.json")
    parser.add_argument("--js-output", type=Path, default=ROOT / "assets" / "materials-data.js")
    parser.add_argument("--rdf-source", type=Path)
    parser.add_argument("--rdf-output", type=Path, default=ROOT / "agent-memory-study.rdf")
    parser.add_argument("--package-output", type=Path)
    return parser.parse_args()


def walk_strings(value: Any, where: str = "root"):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from walk_strings(nested, f"{where}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from walk_strings(nested, f"{where}[{index}]")
    elif isinstance(value, str):
        yield where, value


def assert_public_text(value: Any) -> None:
    for where, text in walk_strings(value):
        for pattern in PRIVATE_PATTERNS:
            match = pattern.search(text)
            if match:
                raise ValueError(f"private token at {where}: {match.group(0)!r}")


def assert_string_list(value: Any, where: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"{where} must be a {'possibly empty ' if allow_empty else 'non-empty '}list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{where} must contain non-empty text values")


def assert_exact_text_object(value: Any, fields: set[str], where: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{where} fields must be exactly {sorted(fields)}")
    if any(not isinstance(value[field], str) or not value[field].strip() for field in fields):
        raise ValueError(f"{where} must contain non-empty text")


def assert_links(value: Any, where: str, *, allow_empty: bool = True) -> None:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValueError(f"{where} must be a {'possibly empty' if allow_empty else 'non-empty'} list")
    for index, link in enumerate(value):
        if not isinstance(link, dict) or set(link) != {"label", "url"}:
            raise ValueError(f"{where}[{index}] must contain label and url")
        if not isinstance(link["label"], str) or not link["label"].strip():
            raise ValueError(f"{where}[{index}].label must be non-empty text")
        if not is_https_url(link["url"]):
            raise ValueError(f"{where}[{index}].url must use HTTPS")


def public_copy_paths() -> list[Path]:
    paths = [ROOT / relative_path for relative_path in PUBLIC_COPY_PATHS]
    for root, suffixes in ((ROOT / "research", PUBLIC_RESEARCH_SUFFIXES),
                           (ROOT / "docs", PUBLIC_DOC_SUFFIXES)):
        if root.is_dir():
            paths.extend(
                path
                for path in sorted(root.rglob("*"))
                if path.is_file() and path.suffix.lower() in suffixes
            )
    return paths


def validate_public_copy_files() -> None:
    global _PUBLIC_COPY_CACHE
    paths = public_copy_paths()
    _PUBLIC_COPY_CACHE = set(paths)
    for path in paths:
        relative_path = path.relative_to(ROOT).as_posix()
        if not path.is_file():
            raise ValueError(f"public copy file is missing: {relative_path}")
        text = path.read_text(encoding="utf-8")
        assert_public_text({relative_path: text})
        for pattern in DISALLOWED_TRACKING_PATTERNS:
            match = pattern.search(text)
            if match:
                raise ValueError(
                    f"unapproved analytics or tracking token in {relative_path}: {match.group(0)!r}"
                )

    index_text = (ROOT / "index.html").read_text(encoding="utf-8")
    beacon_pattern = re.compile(
        r'<script\s+type="module"\s+'
        rf'src="{re.escape(CLOUDFLARE_WEB_ANALYTICS_SRC)}"\s+'
        rf'data-cf-beacon=\'\{{"token":"{CLOUDFLARE_WEB_ANALYTICS_TOKEN}"\}}\'>'
        r'</script>'
    )
    if len(beacon_pattern.findall(index_text)) != 1:
        raise ValueError("index.html must contain exactly one approved Cloudflare Web Analytics beacon")
    if index_text.count("static.cloudflareinsights.com") != 1:
        raise ValueError("index.html must not contain additional Cloudflare Insights scripts")
    root_relative_asset = re.search(r"(?:src|href)=[\"']/[^/\"']", index_text)
    if root_relative_asset:
        raise ValueError(
            "index.html uses a root-relative asset URL that will break on the GitHub Pages subpath: "
            f"{root_relative_asset.group(0)!r}"
        )


def validate_icon_assets() -> None:
    for relative_path, expected_size in ICON_SIZES.items():
        path = ROOT / relative_path
        if not path.is_file():
            raise ValueError(f"icon asset is missing: {relative_path}")
        header = path.read_bytes()[:24]
        if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            raise ValueError(f"icon asset is not a valid PNG: {relative_path}")
        width, height = struct.unpack(">II", header[16:24])
        if (width, height) != (expected_size, expected_size):
            raise ValueError(
                f"icon asset has size {width}x{height}; expected {expected_size}x{expected_size}: "
                f"{relative_path}"
            )

    manifest = json.loads((ROOT / "site.webmanifest").read_text(encoding="utf-8"))
    manifest_icons = {
        icon.get("src"): icon.get("sizes")
        for icon in manifest.get("icons", [])
        if isinstance(icon, dict)
    }
    if manifest_icons != MANIFEST_ICONS:
        raise ValueError("site.webmanifest icons differ from the public app-icon contract")

    index_text = (ROOT / "index.html").read_text(encoding="utf-8")
    browser_icons = set(ICON_SIZES) - set(MANIFEST_ICONS)
    missing_links = sorted(path for path in browser_icons if f'href="{path}"' not in index_text)
    if missing_links:
        raise ValueError(f"index.html does not link browser icons: {missing_links}")


def is_https_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("https://")


def bundled_pdf_paths(data: dict[str, Any]) -> list[str]:
    return [
        paper["pdf"]["url"]
        for paper in data["materials"]
        if paper["pdf"]["delivery"] == "bundled"
    ]


def validate_bundled_files(data: dict[str, Any]) -> None:
    expected = set(bundled_pdf_paths(data))
    papers_dir = ROOT / "papers"
    actual = {
        path.relative_to(ROOT).as_posix()
        for path in papers_dir.rglob("*")
        if path.is_file()
    } if papers_dir.is_dir() else set()
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"papers/ differs from data (missing={missing}, extra={extra})")

    for relative_path in sorted(expected):
        path = ROOT / relative_path
        with path.open("rb") as pdf_file:
            header = pdf_file.read(4)
        if header != b"%PDF":
            raise ValueError(f"bundled file does not start with %PDF: {relative_path}")


def validate_studies(data: dict[str, Any], material_ids: set[str]) -> None:
    studies = data.get("studies")
    if not isinstance(studies, list):
        raise ValueError("data.studies must be a list")
    seen = set()
    text_fields = {"id", "number", "title", "subtitle", "byline", "date", "kind", "intro", "labTitle", "labIntro", "boundary", "closing", "artifactUrl"}
    for study in studies:
        if not isinstance(study, dict) or not text_fields.issubset(study):
            raise ValueError("study missing text fields")
        assert_exact_text_object({k: study[k] for k in text_fields}, text_fields, "study")
        if not re.fullmatch(r"[a-z0-9-]+", study["id"]) or study["id"] in seen:
            raise ValueError("invalid or duplicate study id")
        seen.add(study["id"])
        if study["kind"] not in {"editorial-synthesis-with-deterministic-demo", "editorial-synthesis-with-recorded-experiment"}:
            raise ValueError("unsupported study kind")
        artifact = PurePosixPath(study["artifactUrl"])
        if artifact.is_absolute() or ".." in artifact.parts or artifact.parts[0] != "research" or not (ROOT / artifact).is_file():
            raise ValueError("study artifact must be an existing public research file")
        for field, keys in [("sections", {"title", "text"}), ("takeaways", {"title", "text"}),
                            ("readings", {"materialId", "label", "locator", "takeaway", "limit"})]:
            if not isinstance(study.get(field), list) or not study[field]:
                raise ValueError(f"study {field} must be non-empty")
            for item in study[field]:
                assert_exact_text_object(item, keys, f"study {field}")
        if any(item["materialId"] not in material_ids for item in study["readings"]):
            raise ValueError("study references unknown material")
        for source in study.get("externalReadings", []):
            assert_exact_text_object(source, {"label", "kind", "url", "locator", "takeaway", "limit"}, "external reading")
            if not is_https_url(source["url"]):
                raise ValueError("external reading requires a public HTTPS source")
        if "recordedResults" in study:
            raise ValueError("recordedResults belongs to the generated browser projection")
        if study["kind"] == "editorial-synthesis-with-recorded-experiment":
            result = PurePosixPath(study.get("resultsUrl", ""))
            if result.is_absolute() or ".." in result.parts or result.parts[:1] != ("research",) or result.suffix != ".json" or not (ROOT / result).is_file():
                raise ValueError("recorded study requires an existing public research JSON")
            load_recorded_results(study)
            continue
        if not isinstance(study.get("policies"), list) or not study["policies"]:
            raise ValueError("study policies must be non-empty")
        for policy in study["policies"]:
            assert_exact_text_object(policy, {"id", "label", "description"}, "study policy")
        if [p["id"] for p in study["policies"]] != ["none", "frozen", "latest", "scoped"]:
            raise ValueError("study policies differ from supported engine")
        if not isinstance(study.get("scenarios"), list) or not study["scenarios"]:
            raise ValueError("study scenarios must be non-empty")
        scenario_ids = set()
        for scenario in study["scenarios"]:
            keys = {"id", "title", "description", "target", "lesson"}
            if not isinstance(scenario, dict) or not keys.issubset(scenario):
                raise ValueError("study scenario missing text")
            assert_exact_text_object({k: scenario[k] for k in keys}, keys, "scenario")
            if not re.fullmatch(r"[a-z0-9-]+", scenario["id"]) or scenario["id"] in scenario_ids:
                raise ValueError("invalid or duplicate study scenario id")
            scenario_ids.add(scenario["id"])
            change = scenario.get("change")
            if not isinstance(change, dict) or set(change) != {"label", "adds", "retracts"}:
                raise ValueError("scenario change must declare label, adds, retracts")
            assert_exact_text_object({"label": change["label"]}, {"label"}, "change")
            assert_string_list(change["retracts"], "change retracts", allow_empty=True)
            sources = []
            for values in [scenario.get("initial"), change["adds"]]:
                if not isinstance(values, list):
                    raise ValueError("scenario sources must be lists")
                for source in values:
                    assert_exact_text_object(source, {"id", "scope", "flag"}, "scenario source")
                    if source["flag"] not in {"--format", "--output"}:
                        raise ValueError("unsupported synthetic source flag")
                sources.extend(values)
            source_ids = [source["id"] for source in sources]
            if len(set(source_ids)) != len(source_ids):
                raise ValueError("duplicate scenario source id")
            if not set(change["retracts"]).issubset({source["id"] for source in scenario["initial"]}):
                raise ValueError("scenario retracts unknown initial source")
            env = scenario.get("environment")
            assert_exact_text_object(env, {"before", "after"}, "environment")
            if any(flag not in {"--format", "--output"} for flag in env.values()):
                raise ValueError("unsupported synthetic environment flag")


def validate_ams_evidence(paper: dict[str, Any]) -> None:
    evidence = paper.get("amsEvidence")
    if evidence is None:
        return
    where = f"{paper['id']}.amsEvidence"
    fields = {"byline", "artifactUrl", "observations", "reasoning", "methods", "findings"}
    if not isinstance(evidence, dict) or set(evidence) != fields:
        raise ValueError(f"{where} fields must be exactly {sorted(fields)}")
    assert_exact_text_object({k: evidence[k] for k in ("byline", "artifactUrl")},
                             {"byline", "artifactUrl"}, where)
    artifact = PurePosixPath(evidence["artifactUrl"])
    if (artifact.is_absolute() or ".." in artifact.parts or artifact.parts[0] != "research"
            or not (ROOT / artifact).is_file()):
        raise ValueError(f"{where} must link an existing public research artifact")
    url = "https://github.com/IndelibleVivi/agent-memory-study/blob/main/" + artifact.as_posix()
    if not any(c.get("type") == "public-test" and c.get("byline") == evidence["byline"]
               and any(link.get("url") == url for link in c.get("links", []))
               for c in paper.get("contributions", [])):
        raise ValueError(f"{where} must bind to an attributed public-test contribution")
    for field in ("observations", "findings"):
        assert_string_list(evidence[field], f"{where}.{field}", allow_empty=True)
    for field, keys in (("reasoning", {"step", "claim", "locator"}),
                        ("methods", {"label", "text", "locator"})):
        if not isinstance(evidence[field], list):
            raise ValueError(f"{where}.{field} must be a list")
        for item in evidence[field]:
            assert_exact_text_object(item, keys, f"{where}.{field}")
    if not any(evidence[k] for k in ("observations", "reasoning", "methods", "findings")):
        raise ValueError(f"{where} must contain evidence")
    paper_text = [text for _, text in walk_strings({k: paper.get(k, []) for k in
                  ("intro", "keyPoints", "argumentMap", "methodNotes", "reportedFindings")})]
    # Structural duplication only. Source attribution still needs editorial review.
    audit_text = [*evidence["observations"], *evidence["findings"],
                  *(x["claim"] for x in evidence["reasoning"]),
                  *(x["text"] for x in evidence["methods"])]
    normalized_paper = [normalize_evidence_statement(text) for text in paper_text]
    normalized_audit = [normalize_evidence_statement(text) for text in audit_text]
    if any(evidence_statements_duplicate(audit, paper)
           for audit in normalized_audit for paper in normalized_paper):
        raise ValueError(f"{where} duplicates a statement in a paper-only section")


def normalize_evidence_statement(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def evidence_statements_duplicate(left: str, right: str) -> bool:
    if left == right:
        return True
    minimum_contained_length = 40
    return min(len(left), len(right)) >= minimum_contained_length and (
        left in right or right in left
    )


_PUBLIC_COPY_CACHE: set[Path] | None = None

def public_copy_path_set() -> set[Path]:
    global _PUBLIC_COPY_CACHE
    if _PUBLIC_COPY_CACHE is None:
        _PUBLIC_COPY_CACHE = set(public_copy_paths())
    return _PUBLIC_COPY_CACHE

def assert_public_relative_url(url: Any, where: str) -> None:
    """Evidence links are HTTPS or repo-relative files that exist in the public tree."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"{where} must be non-empty text")
    if url.startswith("https://"):
        return
    if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.IGNORECASE):
        raise ValueError(f"{where} must be HTTPS or a repo-relative path: {url!r}")
    relative = PurePosixPath(url.split("#", 1)[0])
    if (relative.is_absolute() or "\\" in url
            or any(part in {"", ".", ".."} or part.startswith(".") for part in relative.parts)):
        raise ValueError(f"{where} must be a safe repo-relative path: {url!r}")
    candidate = ROOT / relative
    if not candidate.is_file():
        raise ValueError(f"{where} must resolve to an existing public file: {url!r}")
    if candidate not in public_copy_path_set():
        raise ValueError(
            f"{where} must point at a published surface, not an arbitrary checkout file: {url!r}"
        )

def validate_evidence_list(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{where} must be a non-empty list")
    keys = {"label", "url", "observation", "limit"}
    urls: list[str] = []
    for index, evidence in enumerate(value):
        assert_exact_text_object(evidence, keys, f"{where}[{index}]")
        assert_public_relative_url(evidence["url"], f"{where}[{index}].url")
        urls.append(evidence["url"])
    return urls

def validate_reference_list(value: Any, where: str, known: set[str]) -> set[str]:
    assert_string_list(value, where, allow_empty=True)
    unknown = set(value) - known
    if unknown:
        raise ValueError(f"{where} references unknown ids: {sorted(unknown)}")
    if len(set(value)) != len(value):
        raise ValueError(f"{where} must not repeat ids")
    return set(value)

def validate_question_dossiers(data: dict[str, Any], material_ids: set[str],
                               study_ids: set[str]) -> None:
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("data.questions must be a non-empty list")
    findings = data.get("findings")
    finding_ids = {
        finding.get("id") for finding in findings or [] if isinstance(finding, dict)
    }
    # Detect duplicate or malformed ids before any reciprocal membership check, so
    # a duplicate id is reported as such rather than as a membership fault.
    seen_ids: set[str] = set()
    for question in questions:
        if not isinstance(question, dict):
            continue
        question_id = question.get("id")
        if not isinstance(question_id, str):
            continue
        if question_id in seen_ids:
            raise ValueError(f"duplicate question id: {question_id}")
        seen_ids.add(question_id)
    question_ids: set[str] = set()
    for index, question in enumerate(questions):
        where = f"questions[{index}]"
        if not isinstance(question, dict):
            raise ValueError(f"{where} must be an object")
        text_fields = {"id", "title", "question", "intro", "judgment", "byline", "updated", "status"}
        missing = text_fields.difference(question)
        if missing:
            raise ValueError(f"{where} missing fields: {sorted(missing)}")
        assert_exact_text_object({k: question[k] for k in text_fields}, text_fields, where)
        if not re.fullmatch(r"[a-z0-9-]+", question["id"]):
            raise ValueError(f"{where}.id must be a slug")
        if question["id"] in question_ids:
            raise ValueError(f"duplicate question id: {question['id']}")
        question_ids.add(question["id"])
        if question["status"] != "open":
            raise ValueError(f"{where}.status must be open")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", question["updated"]):
            raise ValueError(f"{where}.updated must be YYYY-MM-DD")
        explanations = question.get("explanations")
        if not isinstance(explanations, list) or not explanations:
            raise ValueError(f"{where}.explanations must be a non-empty list")
        for position, explanation in enumerate(explanations):
            assert_exact_text_object(
                explanation, {"title", "text"}, f"{where}.explanations[{position}]"
            )
        validate_evidence_list(question.get("evidence"), f"{where}.evidence")
        validate_reference_list(question.get("materialIds"), f"{where}.materialIds", material_ids)
        validate_reference_list(question.get("studyIds"), f"{where}.studyIds", study_ids)
        validate_reference_list(question.get("findingIds"), f"{where}.findingIds", finding_ids)
        assert_exact_text_object(
            question.get("nextTest"),
            {"question", "comparison", "success", "reviseWhen", "boundary"},
            f"{where}.nextTest",
        )
    by_finding = {
        finding["id"]: finding for finding in data["findings"]
    }
    for question in questions:
        for finding_id in question["findingIds"]:
            if question["id"] not in by_finding[finding_id]["questionIds"]:
                raise ValueError(
                    f"question {question['id']} lists finding {finding_id}, "
                    "but the finding does not list the question"
                )

def validate_findings(data: dict[str, Any], material_ids: set[str],
                      question_ids: set[str]) -> None:
    findings = data.get("findings")
    if not isinstance(findings, list) or not findings:
        raise ValueError("data.findings must be a non-empty list")
    finding_ids: set[str] = set()
    memberships: dict[str, set[str]] = {}
    for index, finding in enumerate(findings):
        where = f"findings[{index}]"
        if not isinstance(finding, dict):
            raise ValueError(f"{where} must be an object")
        text_fields = {
            "id", "title", "byline", "updated", "status", "claim", "when", "action", "avoid",
            "validation", "limit",
        }
        missing = text_fields.difference(finding)
        if missing:
            raise ValueError(f"{where} missing fields: {sorted(missing)}")
        assert_exact_text_object({k: finding[k] for k in text_fields}, text_fields, where)
        if not re.fullmatch(r"[a-z0-9-]+", finding["id"]):
            raise ValueError(f"{where}.id must be a slug")
        if finding["id"] in finding_ids:
            raise ValueError(f"duplicate finding id: {finding['id']}")
        finding_ids.add(finding["id"])
        if finding["status"] != "proposed-transfer":
            raise ValueError(f"{where}.status must be proposed-transfer")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", finding["updated"]):
            raise ValueError(f"{where}.updated must be YYYY-MM-DD")
        assert_string_list(finding.get("triggers"), f"{where}.triggers")
        validate_evidence_list(finding.get("evidence"), f"{where}.evidence")
        validate_reference_list(finding.get("materialIds"), f"{where}.materialIds", material_ids)
        memberships[finding["id"]] = validate_reference_list(
            finding.get("questionIds"), f"{where}.questionIds", question_ids
        )
        applications = finding.get("applications")
        if not isinstance(applications, list):
            raise ValueError(f"{where}.applications must be a possibly empty list")
        for position, application in enumerate(applications):
            application_where = f"{where}.applications[{position}]"
            assert_exact_text_object(
                application,
                {"title", "status", "date", "url", "decision", "observation", "limit"},
                application_where,
            )
            if application["status"] not in {"adopted", "rejected", "inconclusive", "cited"}:
                raise ValueError(f"{application_where}.status is unsupported")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", application["date"]):
                raise ValueError(f"{application_where}.date must be YYYY-MM-DD")
            assert_public_relative_url(application["url"], f"{application_where}.url")
    questions = data.get("questions")
    if not isinstance(questions, list) or any(
        not isinstance(question, dict) or "id" not in question for question in questions
    ):
        # Malformed questions are reported by validate_question_dossiers.
        return
    by_id = {question["id"]: question for question in questions}
    for finding_id, linked in memberships.items():
        for question_id in linked:
            if finding_id not in by_id[question_id].get("findingIds", []):
                raise ValueError(
                    f"finding {finding_id} lists question {question_id}, "
                    "but the question does not list the finding"
                )

def load_and_validate(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    materials = data.get("materials")
    if not isinstance(materials, list) or not materials:
        raise ValueError("data.materials must be a non-empty list")
    if "attachmentCount" in data:
        raise ValueError("the public projection must not advertise attachments")

    filters = data.get("filters")
    assert_string_list(filters, "data.filters")
    if len(set(filters)) != len(filters):
        raise ValueError("data.filters must be unique")

    atlas = data.get("atlas")
    if not isinstance(atlas, dict):
        raise ValueError("data.atlas must be an object")
    atlas_required = {
        "thesis", "dek", "editorialLabel", "easterEgg", "failureSurfaces", "readingPaths"
    }
    atlas_missing = atlas_required.difference(atlas)
    if atlas_missing:
        raise ValueError(f"data.atlas missing fields: {sorted(atlas_missing)}")
    for field in ("thesis", "dek", "editorialLabel"):
        if not isinstance(atlas[field], str) or not atlas[field].strip():
            raise ValueError(f"data.atlas.{field} must be non-empty text")

    easter_egg = atlas["easterEgg"]
    assert_exact_text_object(
        easter_egg,
        {"heroWord", "heroReveal", "aboutLine", "aboutReveal"},
        "data.atlas.easterEgg",
    )
    if atlas["thesis"].count(easter_egg["heroWord"]) != 1:
        raise ValueError("data.atlas.thesis must contain easterEgg.heroWord exactly once")
    if len(easter_egg["heroWord"]) != len(easter_egg["heroReveal"]):
        raise ValueError("easterEgg hero words must have equal length to prevent title reflow")

    failure_surfaces = atlas["failureSurfaces"]
    if not isinstance(failure_surfaces, list) or not failure_surfaces:
        raise ValueError("data.atlas.failureSurfaces must be a non-empty list")
    surface_ids: set[str] = set()
    surface_numbers: set[str] = set()
    for surface in failure_surfaces:
        if not isinstance(surface, dict):
            raise ValueError("each failure surface must be an object")
        required = {"number", "id", "label", "question", "tension", "materialIds"}
        missing = required.difference(surface)
        if missing:
            raise ValueError(f"failure surface missing fields: {sorted(missing)}")
        if surface["id"] in surface_ids or surface["number"] in surface_numbers:
            raise ValueError(f"duplicate failure surface id or number: {surface['id']}")
        surface_ids.add(surface["id"])
        surface_numbers.add(surface["number"])
        for field in ("number", "id", "label", "question", "tension"):
            if not isinstance(surface[field], str) or not surface[field].strip():
                raise ValueError(f"failure surface {surface['id']}.{field} must be non-empty text")
        assert_string_list(surface["materialIds"], f"failure surface {surface['id']}.materialIds")

    reading_paths = atlas["readingPaths"]
    if not isinstance(reading_paths, list) or not reading_paths:
        raise ValueError("data.atlas.readingPaths must be a non-empty list")
    path_ids: set[str] = set()
    path_numbers: set[str] = set()
    for reading_path in reading_paths:
        if not isinstance(reading_path, dict):
            raise ValueError("each reading path must be an object")
        required = {"number", "id", "title", "description", "materialIds"}
        missing = required.difference(reading_path)
        if missing:
            raise ValueError(f"reading path missing fields: {sorted(missing)}")
        if reading_path["id"] in path_ids or reading_path["number"] in path_numbers:
            raise ValueError(f"duplicate reading path id or number: {reading_path['id']}")
        path_ids.add(reading_path["id"])
        path_numbers.add(reading_path["number"])
        for field in ("number", "id", "title", "description"):
            if not isinstance(reading_path[field], str) or not reading_path[field].strip():
                raise ValueError(f"reading path {reading_path['id']}.{field} must be non-empty text")
        assert_string_list(reading_path["materialIds"], f"reading path {reading_path['id']}.materialIds")

    ids: set[str] = set()
    numbers: set[int] = set()
    delivery_counts = {"bundled": 0, "official": 0}
    forbidden_fields = {
        "pdfBytes",
        "pdf_path",
        "assetNote",
        "zoteroKey",
        "citationKey",
        "projectMapping",
        "sourceInspection",
        "runtimeProbe",
        "offlineProbe",
        "internalRevision",
        "promptEvidence",
        "sessionEvidence",
        "routingEvidence",
        "privateContinuity",
    }
    for paper in materials:
        if not isinstance(paper, dict):
            raise ValueError("each material must be an object")
        overlap = forbidden_fields.intersection(paper)
        if overlap:
            raise ValueError(f"{paper.get('id', '[unknown]')} has private fields: {sorted(overlap)}")
        required = {
            "number", "id", "title", "authors", "year", "sourceUrl", "noteDepth",
            "readingScope", "intro", "keyPoints", "editorialQuestion", "categories",
            "failureSurfaces", "pdf",
        }
        missing = required.difference(paper)
        if missing:
            raise ValueError(f"{paper.get('id', '[unknown]')} missing fields: {sorted(missing)}")
        if paper["id"] in ids or paper["number"] in numbers:
            raise ValueError(f"duplicate id or number: {paper['id']}")
        ids.add(paper["id"])
        numbers.add(paper["number"])
        if not str(paper["sourceUrl"]).startswith("https://"):
            raise ValueError(f"source URL must use HTTPS: {paper['sourceUrl']}")
        if paper["noteDepth"] not in {"skim", "abstract", "read", "worked"}:
            raise ValueError(f"invalid noteDepth for {paper['id']}: {paper['noteDepth']}")
        assert_string_list(paper["authors"], f"{paper['id']}.authors")
        assert_string_list(paper["keyPoints"], f"{paper['id']}.keyPoints")
        assert_string_list(paper["categories"], f"{paper['id']}.categories")
        assert_string_list(paper["failureSurfaces"], f"{paper['id']}.failureSurfaces")
        unknown_topics = set(paper["categories"]) - set(filters)
        if unknown_topics:
            raise ValueError(f"{paper['id']} has unknown topics: {sorted(unknown_topics)}")
        unknown_surfaces = set(paper["failureSurfaces"]) - surface_ids
        if unknown_surfaces:
            raise ValueError(f"{paper['id']} has unknown failure surfaces: {sorted(unknown_surfaces)}")

        for optional_list in ("reportedFindings", "evidenceLimits"):
            if optional_list in paper:
                assert_string_list(paper[optional_list], f"{paper['id']}.{optional_list}")

        rich_object_lists = {
            "argumentMap": {"step", "claim", "locator"},
            "methodNotes": {"label", "text", "locator"},
        }
        for field, item_fields in rich_object_lists.items():
            if field not in paper:
                continue
            items = paper[field]
            if not isinstance(items, list) or not items:
                raise ValueError(f"{paper['id']}.{field} must be a non-empty list")
            for index, item in enumerate(items):
                assert_exact_text_object(item, item_fields, f"{paper['id']}.{field}[{index}]")

        if "sourceTensions" in paper:
            tensions = paper["sourceTensions"]
            if not isinstance(tensions, list) or not tensions:
                raise ValueError(f"{paper['id']}.sourceTensions must be a non-empty list")
            for index, tension in enumerate(tensions):
                if not isinstance(tension, dict) or set(tension) != {
                    "label", "observation", "implication", "locators"
                }:
                    raise ValueError(
                        f"{paper['id']}.sourceTensions[{index}] must contain label, observation, "
                        "implication, and locators"
                    )
                for field in ("label", "observation", "implication"):
                    if not isinstance(tension[field], str) or not tension[field].strip():
                        raise ValueError(
                            f"{paper['id']}.sourceTensions[{index}].{field} must be non-empty text"
                        )
                assert_string_list(
                    tension["locators"], f"{paper['id']}.sourceTensions[{index}].locators"
                )

        if "designTransfer" in paper:
            transfer = paper["designTransfer"]
            assert_exact_text_object(
                transfer, {"byline", "date", "status", "when", "move", "check", "boundary", "basis"},
                f"{paper['id']}.designTransfer",
            )
            if transfer["status"] != "proposed-not-run":
                raise ValueError(f"{paper['id']}.designTransfer must be proposed-not-run")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", transfer["date"]):
                raise ValueError(f"{paper['id']}.designTransfer.date must be YYYY-MM-DD")

        if "editorialInferences" in paper:
            inferences = paper["editorialInferences"]
            if not isinstance(inferences, list) or not inferences:
                raise ValueError(f"{paper['id']}.editorialInferences must be a non-empty list")
            for inference in inferences:
                if not isinstance(inference, dict) or set(inference) != {"label", "text", "boundary"}:
                    raise ValueError(
                        f"{paper['id']}.editorialInferences items must contain label, text, and boundary"
                    )
                if any(not isinstance(inference[field], str) or not inference[field].strip()
                       for field in ("label", "text", "boundary")):
                    raise ValueError(f"{paper['id']}.editorialInferences must contain non-empty text")

        if "openProtocols" in paper:
            protocols = paper["openProtocols"]
            if not isinstance(protocols, list) or not protocols:
                raise ValueError(f"{paper['id']}.openProtocols must be a non-empty list")
            protocol_fields = {
                "title", "status", "question", "method", "fixtures", "controls", "measures",
                "limitations",
            }
            for index, protocol in enumerate(protocols):
                assert_exact_text_object(
                    protocol, protocol_fields, f"{paper['id']}.openProtocols[{index}]"
                )
                if protocol["status"] != "proposed-not-run":
                    raise ValueError(
                        f"{paper['id']}.openProtocols[{index}].status must be proposed-not-run"
                    )

        if "contributions" in paper:
            contributions = paper["contributions"]
            if not isinstance(contributions, list) or not contributions:
                raise ValueError(f"{paper['id']}.contributions must be a non-empty list")
            common = {"type", "title", "byline", "date", "basis", "boundary", "links"}
            type_fields = {
                "perspective": common | {"text"},
                "public-test": common | {
                    "method", "environment", "fixture", "controls", "rawResult", "derivedResult",
                    "limitations",
                },
            }
            for index, contribution in enumerate(contributions):
                if not isinstance(contribution, dict):
                    raise ValueError(f"{paper['id']}.contributions[{index}] must be an object")
                contribution_type = contribution.get("type")
                expected = type_fields.get(contribution_type)
                if expected is None or set(contribution) != expected:
                    raise ValueError(
                        f"{paper['id']}.contributions[{index}] has invalid fields for "
                        f"type {contribution_type!r}"
                    )
                for field in expected - {"links"}:
                    if not isinstance(contribution[field], str) or not contribution[field].strip():
                        raise ValueError(
                            f"{paper['id']}.contributions[{index}].{field} must be non-empty text"
                        )
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", contribution["date"]):
                    raise ValueError(
                        f"{paper['id']}.contributions[{index}].date must be YYYY-MM-DD"
                    )
                assert_links(
                    contribution["links"],
                    f"{paper['id']}.contributions[{index}].links",
                    allow_empty=contribution_type != "public-test",
                )

        validate_ams_evidence(paper)
        if paper["noteDepth"] == "worked" and not any(
            c.get("type") == "public-test" and c.get("links")
            for c in paper.get("contributions", [])
        ):
            raise ValueError(f"{paper['id']} worked requires an attributed public-test artifact")

        if paper["noteDepth"] in {"read", "worked"}:
            rich_required = {
                "whyRead", "argumentMap", "evidenceLimits", "editorialInferences",
            }
            rich_missing = rich_required.difference(paper)
            if rich_missing:
                raise ValueError(
                    f"{paper['id']} read/worked entry missing rich fields: {sorted(rich_missing)}"
                )
            if not isinstance(paper["whyRead"], str) or not paper["whyRead"].strip():
                raise ValueError(f"{paper['id']}.whyRead must be non-empty text")

        pdf = paper["pdf"]
        if not isinstance(pdf, dict):
            raise ValueError(f"{paper['id']}.pdf must be an object")
        delivery = pdf.get("delivery")
        if delivery not in delivery_counts:
            raise ValueError(f"invalid PDF delivery for {paper['id']}: {delivery!r}")
        delivery_counts[delivery] += 1

        if delivery == "bundled":
            expected_keys = {"delivery", "url", "originalUrl", "license", "licenseUrl"}
            if set(pdf) != expected_keys:
                raise ValueError(
                    f"{paper['id']}.pdf bundled fields must be exactly {sorted(expected_keys)}"
                )
            relative_path = PurePosixPath(pdf["url"])
            if (
                relative_path.is_absolute()
                or len(relative_path.parts) != 2
                or relative_path.parts[0] != "papers"
                or any(part in {"", ".", ".."} for part in relative_path.parts)
                or relative_path.suffix.lower() != ".pdf"
            ):
                raise ValueError(f"invalid bundled PDF path for {paper['id']}: {pdf['url']!r}")
            if not is_https_url(pdf["originalUrl"]):
                raise ValueError(f"originalUrl must use HTTPS for {paper['id']}")
            if not isinstance(pdf["license"], str) or not pdf["license"].strip():
                raise ValueError(f"license is required for bundled PDF {paper['id']}")
            if not is_https_url(pdf["licenseUrl"]):
                raise ValueError(f"licenseUrl must use HTTPS for {paper['id']}")
        else:
            expected_keys = {"delivery", "url"}
            allowed_keys = expected_keys | {"accessNote"}
            if not expected_keys.issubset(pdf) or not set(pdf).issubset(allowed_keys):
                raise ValueError(
                    f"{paper['id']}.pdf official fields must be delivery, url, and optional accessNote"
                )
            if not is_https_url(pdf["url"]):
                raise ValueError(f"official PDF URL must use HTTPS for {paper['id']}")
            if "accessNote" in pdf and not isinstance(pdf["accessNote"], str):
                raise ValueError(f"accessNote must be text for {paper['id']}")

    if numbers != set(range(1, len(materials) + 1)):
        raise ValueError("material numbers must be contiguous from 1")
    for surface in failure_surfaces:
        unknown_materials = set(surface["materialIds"]) - ids
        if unknown_materials:
            raise ValueError(
                f"failure surface {surface['id']} references unknown materials: {sorted(unknown_materials)}"
            )
        listed_materials = set(surface["materialIds"])
        claimed_materials = {
            paper["id"]
            for paper in materials
            if surface["id"] in paper["failureSurfaces"]
        }
        if listed_materials != claimed_materials:
            raise ValueError(
                f"failure surface membership mismatch for {surface['id']} "
                f"(surface-only={sorted(listed_materials - claimed_materials)}, "
                f"material-only={sorted(claimed_materials - listed_materials)})"
            )
    for reading_path in reading_paths:
        unknown_materials = set(reading_path["materialIds"]) - ids
        if unknown_materials:
            raise ValueError(
                f"reading path {reading_path['id']} references unknown materials: {sorted(unknown_materials)}"
            )
    validate_studies(data, ids)
    study_ids = {study["id"] for study in data["studies"]}
    question_ids = {
        question.get("id") for question in data.get("questions") or [] if isinstance(question, dict)
    }
    question_id_list = [
        question.get("id") for question in data.get("questions") or [] if isinstance(question, dict)
    ]
    duplicates = {qid for qid in question_id_list if question_id_list.count(qid) > 1}
    if duplicates:
        raise ValueError(f"duplicate question id: {sorted(duplicates)[0]}")
    validate_findings(data, ids, question_ids)
    validate_question_dossiers(data, ids, study_ids)
    bundled_paths = bundled_pdf_paths(data)
    if len(set(bundled_paths)) != delivery_counts["bundled"]:
        raise ValueError("each bundled material must use a distinct PDF path")
    assert_public_text(data)
    validate_bundled_files(data)
    return data


def load_recorded_results(study: dict[str, Any]) -> dict[str, Any]:
    result = json.loads((ROOT / study["resultsUrl"]).read_text(encoding="utf-8"))
    if result.get("schema") == "ams-jev-contract-results/1":
        if not isinstance(result.get("cases"), list) or not result["cases"]:
            raise ValueError("source contract study requires cases")
        seen = set()
        for case in result["cases"]:
            for field in ("id", "title", "intervention"):
                if not isinstance(case.get(field), str) or not case[field].strip():
                    raise ValueError("source contract case requires identity and intervention")
            if not re.fullmatch(r"[a-z0-9-]+", case["id"]) or case["id"] in seen:
                raise ValueError("invalid or duplicate source contract case id")
            seen.add(case["id"])
            for phase in ("before", "after"):
                snapshot = case.get(phase, {})
                for field in ("stored_ids", "vector_ids", "summary_ids"):
                    assert_string_list(snapshot.get(field), f"source contract {phase}.{field}", allow_empty=True)
                if not isinstance(snapshot.get("links"), list):
                    raise ValueError("source contract snapshot requires links")
            if not isinstance(case.get("observations"), dict):
                raise ValueError("source contract requires observations")
            if not isinstance(case.get("checks"), dict) or not case["checks"] or any(type(v) is not bool for v in case["checks"].values()):
                raise ValueError("source contract requires boolean checks")
        assert_public_text(result)
        return result
    if result.get("schema") != "ams-decision-results/2" or not result.get("cases"):
        raise ValueError("unsupported recorded experiment result")
    for phase, methods in [("before", {"no-experience", "episodic", "rules", "scorer"}),
                           ("after", {"frozen", "refit", "incremental", "guard"})]:
        predictions = result[phase]["predictions"]
        if set(predictions) != methods or set(result[phase]["metrics"]) != methods:
            raise ValueError("recorded experiment methods differ from its display contract")
        if any(len(rows) != len(result["cases"]) for rows in predictions.values()):
            raise ValueError("recorded predictions do not match case order")
    assert_public_text(result)
    return result


def write_browser_data(data: dict[str, Any], output: Path) -> None:
    projection = copy.deepcopy(data)
    for study in projection["studies"]:
        if study["kind"] == "editorial-synthesis-with-recorded-experiment":
            study["recordedResults"] = load_recorded_results(study)
    encoded = json.dumps(projection, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    output.write_text(f"window.READING_ROOM = {encoded};\n", encoding="utf-8")


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", normalized).split())


def add_identifier_url(parent: ET.Element, url: str) -> None:
    identifier = ET.SubElement(parent, f"{{{NS['dc']}}}identifier")
    uri = ET.SubElement(identifier, f"{{{NS['dcterms']}}}URI")
    ET.SubElement(uri, f"{{{NS['rdf']}}}value").text = url


def identifier_url(parent: ET.Element) -> str | None:
    value = parent.find(
        f"{{{NS['dc']}}}identifier/"
        f"{{{NS['dcterms']}}}URI/"
        f"{{{NS['rdf']}}}value"
    )
    return value.text if value is not None else None


def attachment_ref(paper: dict[str, Any]) -> str:
    return f"#attachment_{paper['number']:02d}_{paper['id']}"


def parent_items_by_title(root: ET.Element, material_count: int) -> dict[str, ET.Element]:
    title_tag = f"{{{NS['dc']}}}title"
    attachment_tag = f"{{{NS['z']}}}Attachment"
    item_type_tag = f"{{{NS['z']}}}itemType"
    parents: dict[str, ET.Element] = {}
    for child in root:
        if child.tag == attachment_tag or child.findtext(item_type_tag) == "attachment":
            continue
        title_node = child.find(title_tag)
        if title_node is None or not title_node.text:
            continue
        title = normalize_title(title_node.text)
        if title in parents:
            raise ValueError(f"duplicate normalized title in RDF: {title_node.text!r}")
        parents[title] = child
    if len(parents) != material_count:
        raise ValueError(f"RDF has {len(parents)} parent items; expected {material_count}")
    return parents


def write_hybrid_rdf(source: Path, output: Path, data: dict[str, Any]) -> None:
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)
    tree = ET.parse(source)
    root = tree.getroot()

    attachment_tag = f"{{{NS['z']}}}Attachment"
    item_type_tag = f"{{{NS['z']}}}itemType"
    link_tag = f"{{{NS['link']}}}link"
    forbidden_tags = {
        f"{{{NS['dc']}}}subject",
        f"{{{NS['z']}}}citationKey",
        f"{{{NS['dcterms']}}}dateSubmitted",
        f"{{{NS['bib']}}}Memo",
    }
    for child in list(root):
        if (
            child.tag in {attachment_tag, f"{{{NS['bib']}}}Memo"}
            or child.findtext(item_type_tag) == "attachment"
        ):
            root.remove(child)
            continue
        for link in child.findall(link_tag):
            child.remove(link)
        for node in list(child):
            if node.tag in forbidden_tags:
                child.remove(node)

    parents = parent_items_by_title(root, len(data["materials"]))
    for paper in data["materials"]:
        normalized_title = normalize_title(paper["title"])
        parent = parents.get(normalized_title)
        if parent is None:
            raise ValueError(f"RDF parent not found by title: {paper['title']!r}")

        reference = attachment_ref(paper)
        ET.SubElement(
            parent,
            link_tag,
            {f"{{{NS['rdf']}}}resource": reference},
        )
        attachment = ET.SubElement(
            root,
            attachment_tag,
            {f"{{{NS['rdf']}}}about": reference},
        )
        ET.SubElement(attachment, item_type_tag).text = "attachment"
        ET.SubElement(attachment, f"{{{NS['dc']}}}title").text = "Full Text PDF"
        ET.SubElement(attachment, f"{{{NS['link']}}}type").text = "application/pdf"
        pdf = paper["pdf"]
        if pdf["delivery"] == "bundled":
            ET.SubElement(
                attachment,
                f"{{{NS['z']}}}path",
                {f"{{{NS['rdf']}}}resource": pdf["url"]},
            )
        else:
            add_identifier_url(attachment, pdf["url"])
            ET.SubElement(attachment, f"{{{NS['z']}}}linkMode").text = "3"

    ET.indent(tree, space="    ")
    tree.write(output, encoding="utf-8", xml_declaration=True)


def validate_hybrid_rdf(output: Path, data: dict[str, Any]) -> None:
    tree = ET.parse(output)
    root = tree.getroot()
    attachment_tag = f"{{{NS['z']}}}Attachment"
    link_tag = f"{{{NS['link']}}}link"
    item_type_tag = f"{{{NS['z']}}}itemType"
    path_tag = f"{{{NS['z']}}}path"
    link_mode_tag = f"{{{NS['z']}}}linkMode"
    rdf_about = f"{{{NS['rdf']}}}about"
    rdf_resource = f"{{{NS['rdf']}}}resource"

    parents = parent_items_by_title(root, len(data["materials"]))
    attachments = [child for child in root if child.tag == attachment_tag]
    if len(attachments) != len(data["materials"]):
        raise ValueError(
            f"RDF has {len(attachments)} attachments; expected {len(data['materials'])}"
        )
    attachments_by_ref = {attachment.get(rdf_about): attachment for attachment in attachments}
    expected_refs = {attachment_ref(paper) for paper in data["materials"]}
    if set(attachments_by_ref) != expected_refs:
        raise ValueError("RDF attachment identifiers do not match material identifiers")

    all_links = root.findall(f".//{link_tag}")
    if len(all_links) != len(data["materials"]):
        raise ValueError(
            f"RDF has {len(all_links)} parent links; expected {len(data['materials'])}"
        )

    for paper in data["materials"]:
        parent = parents.get(normalize_title(paper["title"]))
        if parent is None:
            raise ValueError(f"RDF parent not found by title: {paper['title']!r}")
        reference = attachment_ref(paper)
        links = parent.findall(link_tag)
        if len(links) != 1 or links[0].get(rdf_resource) != reference:
            raise ValueError(f"RDF parent link mismatch for {paper['id']}")

        attachment = attachments_by_ref[reference]
        if attachment.findtext(item_type_tag) != "attachment":
            raise ValueError(f"invalid RDF attachment itemType for {paper['id']}")
        path = attachment.find(path_tag)
        link_mode = attachment.find(link_mode_tag)
        url = identifier_url(attachment)
        if paper["pdf"]["delivery"] == "bundled":
            if path is None or path.get(rdf_resource) != paper["pdf"]["url"]:
                raise ValueError(f"bundled RDF path mismatch for {paper['id']}")
            if link_mode is not None or url is not None:
                raise ValueError(f"bundled RDF attachment must be path-only for {paper['id']}")
        else:
            if path is not None:
                raise ValueError(f"official RDF attachment must not contain z:path for {paper['id']}")
            if link_mode is None or link_mode.text != "3" or url != paper["pdf"]["url"]:
                raise ValueError(f"official RDF attachment mismatch for {paper['id']}")

    assert_public_text(output.read_text(encoding="utf-8"))


def write_zotero_package(output: Path, rdf_output: Path, data: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    files: list[tuple[Path, str]] = [(rdf_output, "agent-memory-study.rdf")]
    for name in ("README.md", "NOTICE.md", "ZOTERO-IMPORT.md", "THIRD_PARTY_NOTICES.md"):
        path = ROOT / name
        if path.is_file():
            files.append((path, name))
    files.extend((ROOT / relative_path, relative_path) for relative_path in bundled_pdf_paths(data))

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, archive_name in files:
            archive.write(source, archive_name)

    expected = [archive_name for _, archive_name in files]
    with zipfile.ZipFile(output) as archive:
        if archive.namelist() != expected:
            raise ValueError("Zotero package contents differ from the expected file set")


def main() -> int:
    args = parse_args()
    data = load_and_validate(args.data)
    write_browser_data(data, args.js_output)
    if args.rdf_source:
        write_hybrid_rdf(args.rdf_source, args.rdf_output, data)
    validate_hybrid_rdf(args.rdf_output, data)
    validate_public_copy_files()
    validate_icon_assets()
    if args.package_output:
        write_zotero_package(args.package_output, args.rdf_output, data)
    bundled_count = len(bundled_pdf_paths(data))
    official_count = len(data["materials"]) - bundled_count
    print(
        f"validated {len(data['materials'])} materials "
        f"({bundled_count} bundled PDFs, {official_count} official PDF links); "
        f"wrote {args.js_output}"
    )
    if args.rdf_source:
        print(f"wrote hybrid RDF: {args.rdf_output}")
    if args.package_output:
        print(f"wrote Zotero package: {args.package_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
