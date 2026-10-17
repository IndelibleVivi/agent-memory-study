#!/usr/bin/env python3
"""Offline source intake and minimal study-entry drafting.

This tool does not fetch URLs, resolve DOIs over the network, or infer claims.
It only compares the supplied input with the public study/sources records and
their explicit relationships. Study map membership is navigation, not coverage.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STUDY_ROOT = ROOT / "study"
SOURCES = STUDY_ROOT / "sources"
ENTRIES = STUDY_ROOT / "entries"
INQUIRIES = STUDY_ROOT / "inquiries"
TRANSFERS = STUDY_ROOT / "transfers"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DOI = re.compile(r"^(?:doi:|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)
ARXIV = re.compile(
    r"^(?:arxiv:)?(?P<id>\d{4}\.\d{4,5})(?:v(?P<version>\d+))?$",
    re.IGNORECASE,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def family(folder: Path) -> list[dict[str, Any]]:
    if not folder.is_dir():
        raise ValueError(f"Missing study family: {folder.relative_to(ROOT).as_posix()}")
    return [load_json(path) for path in sorted(folder.glob("*.json"))]


def normalize(value: Any) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", str(value or "").casefold()).split())


def canonical_url(value: str) -> tuple[str, str | None]:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", None
    host = parsed.netloc.casefold().removeprefix("www.")
    path = re.sub(r"/+$", "", parsed.path)
    version = None
    doi_match = DOI.fullmatch(value.strip())
    if doi_match:
        return f"doi:{doi_match.group(1).casefold().rstrip('.')}", None
    arxiv_match = re.search(r"/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v(\d+))?(?:\.pdf)?$", path)
    if (host == "arxiv.org" or host.endswith(".arxiv.org")) and arxiv_match:
        return f"arxiv:{arxiv_match.group(1)}", arxiv_match.group(2)
    return f"{host}{path}" + (f"?{parsed.query}" if parsed.query else ""), version


def source_links(source: dict[str, Any]) -> set[str]:
    links = set()
    for key in ("sourceUrl", "doi"):
        value = source.get(key)
        if not isinstance(value, str):
            continue
        target, _ = canonical_url(value if "://" in value else f"https://doi.org/{value}")
        if target:
            links.add(target)
    pdf = source.get("pdf")
    if isinstance(pdf, dict):
        for value in (pdf.get("url"), pdf.get("originalUrl")):
            if isinstance(value, str):
                target, _ = canonical_url(value)
                if target:
                    links.add(target)
    return links


def source_version(source: dict[str, Any]) -> str | None:
    scope = str(source.get("readingScope", ""))
    match = re.search(r"\bv(\d+)\b", scope, re.IGNORECASE)
    return match.group(1) if match else None


def match_source(sources: list[dict[str, Any]], value: str) -> dict[str, Any]:
    query = value.strip()
    doi_match = DOI.fullmatch(query)
    arxiv_match = ARXIV.fullmatch(query)
    target, version = canonical_url(query) if "://" in query else ("", None)
    if doi_match:
        target = f"doi:{doi_match.group(1).casefold().rstrip('.')}"
    elif arxiv_match:
        target = f"arxiv:{arxiv_match.group('id')}"
        version = arxiv_match.group("version")

    def family_identity(link: str) -> str:
        arxiv_doi = re.match(r"^(doi:10\.48550/arxiv\.)(\d{4}\.\d{4,5})(?:v\d+)?$", link)
        if arxiv_doi:
            return f"arxiv:{arxiv_doi.group(2)}"
        arxiv = re.match(r"^(arxiv:\d{4}\.\d{4,5})(?:v\d+)?$", link)
        if arxiv:
            return arxiv.group(1)
        return link

    exact_identity: list[dict[str, Any]] = []
    version_matches: list[dict[str, Any]] = []
    title_matches: list[dict[str, Any]] = []
    normalized_query = normalize(query)
    for source in sources:
        links = source_links(source)
        if target and target in links:
            exact_identity.append(source)
            if version and source_version(source) and source_version(source) != version:
                version_matches.append(source)
        elif target:
            family_ids = {family_identity(link) for link in links}
            if family_identity(target) in family_ids:
                version_matches.append(source)
        title = normalize(source.get("title"))
        if normalized_query and (normalized_query == title or (
            len(normalized_query) >= 24 and normalized_query in title
        )):
            title_matches.append(source)

    exact = exact_identity[0] if exact_identity else (title_matches[0] if len(title_matches) == 1 else None)
    if exact:
        identity_status = "exact" if exact_identity else "title-match"
        if version and exact_identity and source_version(exact) and source_version(exact) != version:
            identity_status = "new-version"
        return {
            "status": identity_status,
            "source": exact,
            "versionCandidates": version_matches if version else [],
            "titleCandidates": [item for item in title_matches if item is not exact],
        }
    if version_matches:
        return {"status": "version-family", "source": None, "versionCandidates": version_matches,
                "titleCandidates": title_matches}
    if title_matches:
        return {"status": "uncertain-title", "source": None, "versionCandidates": [],
                "titleCandidates": title_matches}
    return {"status": "unrecognized", "source": None, "versionCandidates": [],
            "titleCandidates": []}


def impact(source_id: str) -> dict[str, Any]:
    sources = {source["id"]: source for source in family(SOURCES)}
    if source_id not in sources:
        raise ValueError(f"Unknown source id: {source_id}")
    result = {"sourceId": source_id, "entries": [], "inquiries": [], "transfers": [],
              "mapDomains": [], "mapDirections": []}
    for entry in family(ENTRIES):
        if any(reading.get("materialId") == source_id for reading in entry.get("readings", [])):
            result["entries"].append({"id": entry["id"], "title": entry["title"],
                                      "role": "reading"})
        cont = entry.get("continuation", {})
        if source_id in cont.get("materialIds", []):
            result["entries"].append({"id": entry["id"], "title": entry["title"],
                                      "role": "continuation"})
    for inquiry in family(INQUIRIES):
        if source_id in inquiry.get("materialIds", []):
            result["inquiries"].append({"id": inquiry["id"], "title": inquiry["title"],
                                        "role": "evidence-reading"})
        cont = inquiry.get("continuation", {})
        if source_id in cont.get("materialIds", []):
            result["inquiries"].append({"id": inquiry["id"], "title": inquiry["title"],
                                        "role": "continuation"})
    for transfer in family(TRANSFERS):
        if source_id in transfer.get("materialIds", []):
            result["transfers"].append({"id": transfer["id"], "title": transfer["title"],
                                        "role": "evidence"})
    map_path = STUDY_ROOT / "map.json"
    if map_path.is_file():
        mapping = load_json(map_path)
        for domain in mapping.get("domains", []):
            if source_id in domain.get("materialIds", []):
                result["mapDomains"].append(domain["id"])
        for direction in mapping.get("directions", []):
            if source_id in direction.get("materialIds", []):
                result["mapDirections"].append(direction["id"])
    # Deduplicate the two possible entry/inquiry relationships while preserving role.
    for key in ("entries", "inquiries"):
        result[key] = list({(item["id"], item["role"]): item for item in result[key]}.values())
    return result


def inspect(value: str) -> dict[str, Any]:
    sources = family(SOURCES)
    match = match_source(sources, value)
    source = match["source"]
    output = {
        "input": value,
        "lookup": "offline-identity-comparison",
        "matchStatus": match["status"],
        "recognized": source is not None,
        "source": None,
        "versionCandidates": [
            {"id": item["id"], "title": item["title"], "version": source_version(item)}
            for item in match["versionCandidates"]
        ],
        "titleCandidates": [
            {"id": item["id"], "title": item["title"]} for item in match["titleCandidates"]
        ],
        "dependencies": None,
        "note": (
            "Input was not recognized. No title, version, claims, or content were fetched or invented."
            if source is None else
            "A public source candidate was found; inspect matchStatus. Dependencies are explicit editorial links, not claim validation."
        ),
    }
    if source:
        output["source"] = {key: source.get(key) for key in
                            ("id", "title", "authors", "year", "sourceUrl", "doi",
                             "readingScope", "noteDepth")}
        output["dependencies"] = impact(source["id"])
    return output


DRAFT_BODY = """# {title}

从使你想研究这个对象的一句话、例子或疑惑开始。把已经讲清的内容写在这里；外部事实附上实际阅读的来源与范围。

这仍是草稿。进入公开研究体之前，替换提示文字，核对署名与依据。
"""


def create_draft(slug: str, title: str, kind: str, out_dir: Path) -> tuple[Path, Path]:
    if not SLUG.fullmatch(slug):
        raise ValueError("SLUG must use lowercase ASCII words separated by hyphens")
    if kind not in {"learning-note", "research-essay"}:
        raise ValueError("--kind must be learning-note or research-essay")
    if not title.strip():
        raise ValueError("--title must be non-empty")
    if out_dir.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Draft output must be outside this public repository")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{slug}.json"
    markdown_path = out_dir / f"{slug}.md"
    if json_path.exists() or markdown_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing draft: {json_path if json_path.exists() else markdown_path}")
    record = {
        "id": slug,
        "title": title.strip(),
        "kind": kind,
        "date": datetime.date.today().isoformat(),
        "byline": "Draft author",
        "intro": "Draft introduction to complete before editorial review.",
        "bodyFile": markdown_path.name,
        "draft": True,
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(DRAFT_BODY.format(title=title.strip()), encoding="utf-8")
    return json_path, markdown_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect", help="compare an offline URL, DOI, arXiv id, or title")
    inspect_parser.add_argument("input")
    impact_parser = sub.add_parser("impact", help="list explicit editorial dependents of a source")
    impact_parser.add_argument("source_id")
    draft_parser = sub.add_parser("new-study", help="write a minimal editable draft outside the canonical tree")
    draft_parser.add_argument("slug")
    draft_parser.add_argument("--title", required=True)
    draft_parser.add_argument("--kind", required=True)
    draft_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            print(json.dumps(inspect(args.input), ensure_ascii=False, indent=2))
        elif args.command == "impact":
            print(json.dumps(impact(args.source_id), ensure_ascii=False, indent=2))
        else:
            json_path, markdown_path = create_draft(args.slug, args.title, args.kind, args.out.resolve())
            print(f"wrote draft JSON: {json_path}")
            print(f"wrote draft Markdown: {markdown_path}")
            print("Draft is outside the canonical study tree. Review it before moving it into study/entries/.")
    except (ValueError, FileExistsError) as exc:
        print(f"author error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
