#!/usr/bin/env python3
"""Validate public reading-room data and build its browser/Zotero artifacts."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATTERNS = (
    re.compile(r"(?:^|[\"'])/Users/"),
    re.compile(r"file://", re.IGNORECASE),
    re.compile(r"@chatroom", re.IGNORECASE),
    re.compile(r"\bwxid_", re.IGNORECASE),
    re.compile(r"Zotero/storage", re.IGNORECASE),
)
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


def load_and_validate(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    materials = data.get("materials")
    if not isinstance(materials, list) or not materials:
        raise ValueError("data.materials must be a non-empty list")
    if "attachmentCount" in data:
        raise ValueError("the public projection must not advertise attachments")

    ids: set[str] = set()
    numbers: set[int] = set()
    forbidden_fields = {"pdf", "pdfBytes", "pdf_path", "assetNote", "zoteroKey", "citationKey"}
    for paper in materials:
        overlap = forbidden_fields.intersection(paper)
        if overlap:
            raise ValueError(f"{paper.get('id', '[unknown]')} has private fields: {sorted(overlap)}")
        required = {
            "number", "id", "title", "authors", "year", "sourceUrl", "noteDepth",
            "readingScope", "intro", "keyPoints", "editorialQuestion", "categories",
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

    if numbers != set(range(1, len(materials) + 1)):
        raise ValueError("material numbers must be contiguous from 1")
    assert_public_text(data)
    return data


def write_browser_data(data: dict[str, Any], output: Path) -> None:
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    output.write_text(f"window.READING_ROOM = {encoded};\n", encoding="utf-8")


def write_metadata_only_rdf(source: Path, output: Path, material_count: int) -> None:
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)
    tree = ET.parse(source)
    root = tree.getroot()

    attachment_tag = f"{{{NS['z']}}}Attachment"
    link_tag = f"{{{NS['link']}}}link"
    title_tag = f"{{{NS['dc']}}}title"
    forbidden_tags = {
        f"{{{NS['dc']}}}subject",
        f"{{{NS['z']}}}citationKey",
        f"{{{NS['dcterms']}}}dateSubmitted",
        f"{{{NS['bib']}}}Memo",
    }
    for child in list(root):
        if child.tag == attachment_tag:
            root.remove(child)
            continue
        for link in child.findall(link_tag):
            child.remove(link)
        for node in list(child):
            if node.tag in forbidden_tags:
                child.remove(node)

    parent_count = sum(1 for child in root if child.find(title_tag) is not None)
    if parent_count != material_count:
        raise ValueError(f"RDF has {parent_count} parent items; expected {material_count}")

    ET.indent(tree, space="    ")
    tree.write(output, encoding="utf-8", xml_declaration=True)


def validate_metadata_only_rdf(output: Path, material_count: int) -> None:
    tree = ET.parse(output)
    root = tree.getroot()
    title_tag = f"{{{NS['dc']}}}title"
    parent_count = sum(1 for child in root if child.find(title_tag) is not None)
    if parent_count != material_count:
        raise ValueError(f"RDF has {parent_count} parent items; expected {material_count}")
    text = output.read_text(encoding="utf-8")
    forbidden_fragments = ("Attachment", "link:link", "z:path", "papers/", "#attachment_")
    for fragment in forbidden_fragments:
        if fragment in text:
            raise ValueError(f"attachment residue in RDF: {fragment}")
    assert_public_text(text)


def main() -> int:
    args = parse_args()
    data = load_and_validate(args.data)
    write_browser_data(data, args.js_output)
    if args.rdf_source:
        write_metadata_only_rdf(args.rdf_source, args.rdf_output, len(data["materials"]))
    validate_metadata_only_rdf(args.rdf_output, len(data["materials"]))
    print(f"validated {len(data['materials'])} materials; wrote {args.js_output}")
    if args.rdf_source:
        print(f"wrote metadata-only RDF: {args.rdf_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
