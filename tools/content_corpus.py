"""Load the canonical Work/Revision/Note corpus without legacy material shapes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from schemas.validate import validate_graph, ContractError

CONTRACT_VERSION = "ams-core/2"
COMPILER_VERSION = "ams-content-compiler/2"
PUBLIC_MANIFEST_VERSION = "ams-public-corpus-manifest/1"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CorpusError(ValueError):
    pass


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CorpusError(f"missing corpus file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CorpusError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CorpusError(f"corpus record must be an object: {path}")
    return value


def _family(folder: Path) -> list[dict[str, Any]]:
    if not folder.is_dir():
        raise CorpusError(f"missing corpus family: {folder}")
    return [_read(path) for path in sorted(folder.glob("*.json"))]


def _ref(record: dict[str, Any]) -> dict[str, str]:
    return {key: record[key] for key in ("kind", "id", "revision")}


def load(corpus_root: Path) -> dict[str, Any]:
    works = _family(corpus_root / "works")
    revisions = _family(corpus_root / "revisions")
    notes = _family(corpus_root / "notes")
    try:
        validate_graph([*works, *revisions, *notes])
    except ContractError as exc:
        raise CorpusError(f"invalid canonical source corpus: {exc}") from exc
    by_alias: dict[str, tuple[dict, dict, dict]] = {}
    work_by_ref: dict[tuple[str, str, str], dict] = {}
    revision_by_ref: dict[tuple[str, str, str], dict] = {}
    for work in works:
        if work.get("schema") != CONTRACT_VERSION or work.get("kind") != "source_work":
            raise CorpusError(f"invalid source work: {work.get('id')}")
        work_by_ref[tuple(_ref(work)[k] for k in ("kind", "id", "revision"))] = work
    for revision in revisions:
        if revision.get("schema") != CONTRACT_VERSION or revision.get("kind") != "source_revision":
            raise CorpusError(f"invalid source revision: {revision.get('id')}")
        revision_by_ref[tuple(_ref(revision)[k] for k in ("kind", "id", "revision"))] = revision
    for note in notes:
        if note.get("schema") != CONTRACT_VERSION or note.get("kind") != "source_note":
            raise CorpusError(f"invalid source note: {note.get('id')}")
        alias = note.get("alias")
        if not isinstance(alias, str) or not SLUG.fullmatch(alias):
            raise CorpusError(f"source note has invalid alias: {alias!r}")
        if alias in by_alias:
            raise CorpusError(f"duplicate source alias: {alias}")
        work_ref = tuple(note["work_ref"][k] for k in ("kind", "id", "revision"))
        revision_ref = tuple(note["source_revision_ref"][k] for k in ("kind", "id", "revision"))
        if work_ref not in work_by_ref or revision_ref not in revision_by_ref:
            raise CorpusError(f"source note {alias} has unresolved source refs")
        work = work_by_ref[work_ref]
        revision = revision_by_ref[revision_ref]
        if alias not in work.get("aliases", []):
            raise CorpusError(f"source note {alias} alias is not owned by its work")
        if revision.get("work_ref") != _ref(work):
            raise CorpusError(f"source revision {alias} belongs to another work")
        by_alias[alias] = (work, revision, note)
    missing_aliases = {
        alias for work in works for alias in work.get("aliases", [])
    } - set(by_alias)
    if missing_aliases:
        raise CorpusError(f"source aliases without notes: {sorted(missing_aliases)}")
    return {
        "schema": "ams-core-corpus/2",
        "contract_version": CONTRACT_VERSION,
        "works": works,
        "revisions": revisions,
        "notes": notes,
        "relations": [],
        "by_alias": by_alias,
    }
