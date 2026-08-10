#!/usr/bin/env python3
"""Validate public reading-room data and build its browser/Zotero artifacts."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath
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


def load_and_validate(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    materials = data.get("materials")
    if not isinstance(materials, list) or not materials:
        raise ValueError("data.materials must be a non-empty list")
    if "attachmentCount" in data:
        raise ValueError("the public projection must not advertise attachments")

    ids: set[str] = set()
    numbers: set[int] = set()
    delivery_counts = {"bundled": 0, "official": 0}
    forbidden_fields = {"pdfBytes", "pdf_path", "assetNote", "zoteroKey", "citationKey"}
    for paper in materials:
        if not isinstance(paper, dict):
            raise ValueError("each material must be an object")
        overlap = forbidden_fields.intersection(paper)
        if overlap:
            raise ValueError(f"{paper.get('id', '[unknown]')} has private fields: {sorted(overlap)}")
        required = {
            "number", "id", "title", "authors", "year", "sourceUrl", "noteDepth",
            "readingScope", "intro", "keyPoints", "editorialQuestion", "categories", "pdf",
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
    bundled_paths = bundled_pdf_paths(data)
    if len(set(bundled_paths)) != delivery_counts["bundled"]:
        raise ValueError("each bundled material must use a distinct PDF path")
    assert_public_text(data)
    validate_bundled_files(data)
    return data


def write_browser_data(data: dict[str, Any], output: Path) -> None:
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
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
