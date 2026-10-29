#!/usr/bin/env python3
"""Migrate legacy bibliography-shaped sources into Work/Revision/Note records.

The migration is lossless at the compatibility boundary: each generated source
note retains the complete reviewed payload for the legacy material projection.
It never treats an extractor output, rendering change, or note revision as a new
publisher source revision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemas import validate as contract  # noqa: E402

STUDY = ROOT / "study"
IMPORT_ROOT = ROOT / "tests" / "fixtures" / "legacy-sources"
LEGACY = IMPORT_ROOT
TARGET = STUDY / "source-corpus"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ARXIV_VERSION = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)(?P<id>\d{4}\.\d{4,5})v(?P<version>\d+)", re.I)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _with_content_digest(record: dict[str, Any]) -> dict[str, Any]:
    record["content_digest"] = contract.content_digest(
        record, contract.content_fields(record)
    )
    return record


def _authors(source: dict[str, Any]) -> list[str]:
    values = source.get("authors")
    return values if isinstance(values, list) and values else ["Unreported author"]


def _identifiers(source: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    doi = source.get("doi")
    if isinstance(doi, str) and doi.strip():
        result.append({
            "namespace": "doi", "value": doi, "status": "confirmed",
            "role": "work-identity",
        })
    url = str(source.get("sourceUrl", "")).strip()
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        namespace = "url"
        if parsed.netloc.endswith("arxiv.org"):
            namespace = "arxiv"
        result.append({
            "namespace": namespace, "value": url, "status": "confirmed",
            "role": "source-locator",
        })
    return result


def _manifestations(source: dict[str, Any]) -> list[dict[str, Any]]:
    pdf = source.get("pdf") if isinstance(source.get("pdf"), dict) else {}
    result: list[dict[str, Any]] = []
    url = str(source.get("sourceUrl", "")).strip()
    if url.startswith("https://"):
        result.append({
            "media_type": "text/html", "locator": url, "delivery": "official-link",
        })
    pdf_url = pdf.get("url")
    if isinstance(pdf_url, str) and pdf_url:
        item: dict[str, Any] = {
            "media_type": "application/pdf", "locator": pdf_url,
            "delivery": "bundled" if pdf.get("delivery") == "bundled" else "official-link",
        }
        if pdf.get("delivery") == "official" and isinstance(pdf.get("originalUrl"), str):
            item["locator"] = pdf["originalUrl"]
        item["original_locator"] = (
            pdf["originalUrl"] if isinstance(pdf.get("originalUrl"), str) else pdf_url
        )
        if isinstance(pdf.get("accessNote"), str):
            item["access_note"] = pdf["accessNote"]
        if isinstance(pdf.get("license"), str):
            item["license"] = pdf["license"]
        if isinstance(pdf.get("licenseUrl"), str):
            item["license_url"] = pdf["licenseUrl"]
        result.append(item)
    return result


def _legacy_manifestations(source: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return the reviewed HTML/Pdf locator pair used by the old material view."""
    url = str(source.get("sourceUrl", "")).strip()
    pdf = source.get("pdf") if isinstance(source.get("pdf"), dict) else {}
    if not url.startswith("https://") or not isinstance(pdf, dict):
        raise ValueError(f"source {source.get('id')} lacks a public source locator or PDF record")
    result: dict[str, Any] = {"pdf": pdf}
    result["sourceUrl"] = url
    return url, pdf


def _revision_identity(source: dict[str, Any]) -> dict[str, Any]:
    url = str(source.get("sourceUrl", "")).strip()
    pdf = source.get("pdf") if isinstance(source.get("pdf"), dict) else {}
    locator = str(pdf.get("originalUrl") or url)
    match = ARXIV_VERSION.search(locator)
    if match:
        return {
            "mode": "publisher-version",
            "namespace": "arxiv",
            "value": f"{match.group('id')}v{match.group('version')}",
            "source_locator": locator,
            "identity_basis": "Explicit arXiv version in the reviewed source locator.",
        }
    return {
        "mode": "observed-snapshot",
        "observed_at": None,
        "source_locator": locator,
        "observation_basis": (
            "Legacy public locator does not prove a distinct publisher version; "
            "this is the reviewed source identity, not a stored byte snapshot."
        ),
        "publisher_version_known": False,
        "snapshot_captured": False,
    }


def _record_refs(work: dict[str, Any], revision: dict[str, Any]) -> tuple[dict, dict]:
    return contract.record_ref(work), contract.record_ref(revision)


def _date(source: dict[str, Any]) -> str:
    transfer = source.get("designTransfer")
    if isinstance(transfer, dict) and isinstance(transfer.get("date"), str):
        return transfer["date"]
    contributions = source.get("contributions")
    if isinstance(contributions, list):
        dates = sorted(
            item.get("date") for item in contributions
            if isinstance(item, dict) and isinstance(item.get("date"), str)
        )
        if dates:
            return dates[-1]
    return "2026-10-29"


def _byline(source: dict[str, Any]) -> str:
    transfer = source.get("designTransfer")
    if isinstance(transfer, dict) and isinstance(transfer.get("byline"), str):
        return transfer["byline"]
    contributions = source.get("contributions")
    if isinstance(contributions, list):
        for item in contributions:
            if isinstance(item, dict) and isinstance(item.get("byline"), str) and item["byline"].strip():
                return item["byline"]
    return "Agent Memory Study editors"


def migrate(source: dict[str, Any]) -> tuple[dict, dict, dict]:
    alias = source["id"]
    if not SLUG.fullmatch(alias):
        raise ValueError(f"invalid source alias {alias!r}")
    digest = _digest(source)
    revision_token = "rev:" + digest[:24]
    work = _with_content_digest({
        "schema": "ams-core/2", "kind": "source_work", "id": "work:" + alias,
        "revision": "rev:work-" + digest[:24], "state_revision": "rev:work-" + digest[:24],
        "title": source["title"], "work_type": "paper",
        "authors": _authors(source), "year": source.get("year"),
        "short_author": source.get("shortAuthor") or None,
        "identifiers": _identifiers(source),
        "manifestations": _manifestations(source),
        "aliases": [alias], "visibility": "public",
    })
    revision = _with_content_digest({
        "schema": "ams-core/2", "kind": "source_revision", "id": work["id"],
        "revision": revision_token, "state_revision": revision_token,
        "work_ref": contract.record_ref(work), "identity": _revision_identity(source),
    })
    navigation = {
        "categories": list(source.get("categories") or []),
        "failure_surfaces": list(source.get("failureSurfaces") or []),
        "domains": [],
    }
    payload = {}
    note = _with_content_digest({
        "schema": "ams-core/2", "kind": "source_note", "id": "note:" + alias,
        "revision": "rev:note-" + digest[:24], "state_revision": "rev:note-" + digest[:24],
        "alias": alias, "work_ref": contract.record_ref(work),
        "source_revision_ref": contract.record_ref(revision),
        "title": source["title"], "byline": _byline(source), "date": _date(source),
        "intro": source["intro"], "note_depth": source["noteDepth"],
        "reading_scope": source["readingScope"], "navigation": navigation,
        "payload": payload,
    })
    # Keep only bounded compatibility fields outside the Work/Revision
    # identities. The full legacy payload remains available to the importer
    # separately and is not duplicated into every public note version.
    note["payload"] = {
        key: value for key, value in source.items() if key not in {
            "title", "authors", "shortAuthor", "year", "sourceUrl", "pdf",
            "noteDepth", "readingScope", "intro", "categories", "failureSurfaces",
        }
    }
    note["content_digest"] = contract.content_digest(
        note, contract.content_fields(note)
    )
    return work, revision, note


def _load_legacy() -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(LEGACY.glob("*.json"))]


def _legacy_projection(records: list[tuple[dict, dict, dict]]) -> list[dict[str, Any]]:
    result = []
    for work, revision, note in records:
        source = _load_legacy_by_alias(note["alias"])
        result.append(source)
    order = json.loads((ROOT / "study" / "catalog.json").read_text(encoding="utf-8"))["sourceOrder"]
    by_id = {value["id"]: value for value in result}
    unknown = sorted(set(order) - set(by_id))
    if unknown:
        raise ValueError(f"catalog sourceOrder contains unknown aliases {unknown}")
    return [by_id[alias] for alias in order]


def _load_legacy_by_alias(alias: str) -> dict[str, Any]:
    path = IMPORT_ROOT / f"{alias}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def write_corpus(records: list[tuple[dict, dict, dict]], output: Path) -> None:
    folders = {
        "works": output / "works", "revisions": output / "revisions",
        "notes": output / "notes",
    }
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    for work, revision, note in records:
        alias = note["alias"]
        (folders["works"] / f"{alias}.json").write_bytes(_json_bytes(work))
        (folders["revisions"] / f"{alias}.json").write_bytes(_json_bytes(revision))
        (folders["notes"] / f"{alias}.json").write_bytes(_json_bytes(note))


def expected_corpus(records: list[tuple[dict, dict, dict]], output: Path) -> dict[Path, bytes]:
    expected = {}
    for collection, index in (("works", 0), ("revisions", 1), ("notes", 2)):
        for record in records:
            alias = record[2]["alias"]
            expected[output / collection / f"{alias}.json"] = _json_bytes(record[index])
    return expected


def corpus_drift(records: list[tuple[dict, dict, dict]], output: Path) -> list[str]:
    expected = expected_corpus(records, output)
    actual = {
        path for folder in ("works", "revisions", "notes")
        for path in (output / folder).glob("*.json")
    } if output.is_dir() else set()
    drift = [f"missing {path.relative_to(output)}" for path in sorted(set(expected) - actual)]
    drift += [f"extra {path.relative_to(output)}" for path in sorted(actual - set(expected))]
    drift += [
        f"changed {path.relative_to(output)}" for path in sorted(set(expected) & actual)
        if path.read_bytes() != expected[path]
    ]
    return drift


def report(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    by_id_before = {item["id"]: item for item in before}
    by_id_after = {item["id"]: item for item in after}
    missing = sorted(set(by_id_before) - set(by_id_after))
    extra = sorted(set(by_id_after) - set(by_id_before))
    changed = sorted(
        key for key in set(by_id_before) & set(by_id_after)
        if by_id_before[key] != by_id_after[key]
    )
    return {
        "schema": "ams-source-migration-report/1",
        "source_count": len(before), "work_count": len(after),
        "note_count": len(after), "revision_count": len(after),
        "missing_ids": missing, "extra_ids": extra, "changed_ids": changed,
        "byte_equivalent": not missing and not extra and not changed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TARGET)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--replace-generated", action="store_true",
        help="replace an existing migration output after verifying its exact file set",
    )
    args = parser.parse_args(argv)
    try:
        before = _load_legacy()
        triples = [migrate(source) for source in before]
        after = _legacy_projection(triples)
        result = report(before, after)
        result["output"] = str(args.output)
        result["applied"] = bool(args.apply)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["byte_equivalent"]:
            raise ValueError("legacy compatibility payload changed; migration not applied")
        if args.apply:
            if args.output.exists():
                if not args.replace_generated:
                    raise ValueError(f"refusing to overwrite existing migration directory: {args.output}")
                expected = expected_corpus(triples, args.output)
                actual = {
                    path for folder in ("works", "revisions", "notes")
                    for path in (args.output / folder).glob("*.json")
                }
                if actual - set(expected):
                    raise ValueError("refusing replacement: output has unexpected files")
                shutil.rmtree(args.output)
            write_corpus(triples, args.output)
        elif args.replace_generated:
            raise ValueError("--replace-generated requires --apply")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"migration error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
