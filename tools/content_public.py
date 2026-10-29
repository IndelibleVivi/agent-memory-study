"""Build the public corpus manifest and v2 packets from compiled content."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from schemas.validate import content_digest, record_ref, validate_entity
from typing import Any

try:
    from tools.content_corpus import COMPILER_VERSION, CONTRACT_VERSION, PUBLIC_MANIFEST_VERSION
except ModuleNotFoundError:  # Support direct `tools/build.py` execution.
    from content_corpus import COMPILER_VERSION, CONTRACT_VERSION, PUBLIC_MANIFEST_VERSION

FAMILIES = {
    "material": "materials", "study": "studies",
    "question": "questions", "finding": "findings",
}
CORE_KIND = {
    "study": "entry", "question": "thread", "finding": "claim_revision",
}


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True,
                   separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _ref(record: dict[str, Any]) -> dict[str, str]:
    return {key: record[key] for key in ("kind", "id", "revision")}


def _identity_content(item):
    content = copy.deepcopy(item)
    # Rendering and saved-result projection do not revise authored meaning.
    for key in ("bodyHtml", "sections", "ast", "recordedResults"):
        content.pop(key, None)
    return content


def _authored_record(item, public_kind):
    content = _identity_content(item)
    kind = CORE_KIND[public_kind]
    prefix = {"entry": "entry", "thread": "thread", "claim_revision": "claim"}[kind]
    fields = {"title": item["title"], "byline": item["byline"], "payload": content}
    if kind == "entry":
        fields.update(entry_type=item.get("kind") if item.get("kind") in {"learning-note", "research-essay"} else "editorial-synthesis",
                      date=item["date"], intro=item["intro"], body_file=item["sourcePath"])
    elif kind == "thread":
        fields["status"] = "open"
    else:
        fields.update(claim=item["claim"], scope=json.dumps({key: item.get(key) for key in ("when", "avoid", "limit")},ensure_ascii=False,sort_keys=True),
                      scope_binding="Published editorial transfer; applicability remains the explicit when/avoid/limit text. No formal support is inferred.")
    record = {"schema": CONTRACT_VERSION, "kind": kind, "id": prefix+":"+item["id"], **fields}
    record["content_digest"] = content_digest(record)
    record["revision"] = "rev:"+kind+"-sha256:"+record["content_digest"]["value"]
    record["state_revision"] = record["revision"]
    validate_entity(record)
    return record


def _current_ref(record, public_kind):
    return record_ref(_authored_record(record, public_kind))


def entity_files(manifest: dict[str, Any],
                 packets: dict[tuple[str, str], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return JSON values keyed by repository-relative public corpus paths."""
    files: dict[str, Any] = {}
    object_packets = packets or {}
    for entry in manifest["objects"]:
        packet = dict(object_packets[(entry["public_kind"], entry["public_id"])])
        files[entry["packet_v2"]] = packet
        files[entry["shard"]] = {
            "schema": "ams-public-entity/1",
            "public_kind": entry["public_kind"],
            "entity_ref": {key: entry[key] for key in ("kind", "id", "revision")},
            "route": entry["route"], "packet": packet,
        }
        files[entry["revision_shard"]] = {
            "schema": "ams-public-revision/1",
            "public_kind": entry["public_kind"],
            "entity_ref": {key: entry[key] for key in ("kind", "id", "revision")},
            "payload": packet["content"],
        }
    return files


def _source_packet(item: dict[str, Any], work: dict[str, Any],
                   revision: dict[str, Any], note: dict[str, Any]) -> dict[str, Any]:
    """The legacy reader content, with Work/Revision/Note identity explicit."""
    content = copy.deepcopy(item)
    for internal in ("_aliasWork", "_aliasRevision", "_aliasNote"):
        content.pop(internal, None)
    return {
        "schema": "ams-study-packet/2",
        "contract_version": CONTRACT_VERSION,
        "compiler_version": COMPILER_VERSION,
        "kind": "material", "id": item["id"], "title": item["title"],
        "entity_refs": [_ref(work), _ref(revision), _ref(note)],
        "attribution": {
            "source_authors": work["authors"],
            "note_byline": note["byline"],
            "source_revision_mode": revision["identity"]["mode"],
            "note_depth": note["note_depth"],
            "reading_scope": note["reading_scope"],
        },
        "content": content,
        "manifest": _direct_manifest(item),
        "manifest_policy": (
            "Current public object plus bounded direct references; no linked full "
            "texts, private workflow, or inferred support."
        ),
    }


def build(compiled: dict[str, Any]) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    for public_kind, family in FAMILIES.items():
        for item in compiled[family]:
            if public_kind == "material":
                work, revision, note = compiled["corpus"]["by_alias"][item["id"]]
                primary = _ref(note)
                packet = _source_packet(item, work, revision, note)
            else:
                primary = _current_ref(item, public_kind)
                packet = _authored_packet(item, public_kind)
            safe = item["id"]
            objects.append({
                **primary, "public_kind": public_kind, "public_id": safe,
                "route": f"/{public_kind}/{safe}/",
                "shard": f"data/corpus/entities/{primary['kind']}/{safe}.json",
                "revision_shard": (
                    f"data/corpus/revisions/{primary['kind']}/{safe}/"
                    f"{primary['revision'].replace(':', '-')}.json"
                ),
                "packet_v2": f"data/corpus/packets/{public_kind}/{safe}/index.json",
            })
    by_key = {(item["public_kind"], item["public_id"]): item for item in objects}

    navigation: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    arguments: list[dict[str, Any]] = []

    def connect(public_kind: str, object_id: str, relation: str, locator: str,
                target_kind: str | None = None, target_id: str | None = None) -> None:
        source = by_key.get((public_kind, object_id))
        target = by_key.get((target_kind or public_kind, target_id or object_id))
        if not source or not target:
            return
        row = {
            "from": f"{public_kind}/{object_id}",
            "to": f"{target['public_kind']}/{target['public_id']}",
            "relation": relation, "locator": locator,
        }
        if row["from"] == row["to"]:
            return
        graph = navigation if relation == "navigation" else references
        if row not in graph:
            graph.append(row)

    for public_kind, family in FAMILIES.items():
        for item in compiled[family]:
            for field, target_kind in (
                ("materialIds", "material"), ("studyIds", "study"),
                ("questionIds", "question"), ("findingIds", "finding"),
            ):
                for index, target_id in enumerate(item.get(field, [])):
                    connect(public_kind, item["id"], "reference",
                            f"{field}[{index}]", target_kind, target_id)
            for index, reading in enumerate(item.get("readings", [])):
                connect(public_kind, item["id"], "reading",
                        f"readings[{index}].materialId", "material",
                        reading.get("materialId"))
            for index, reference in enumerate(item.get("ast", {}).get("references", [])):
                target_kind = {
                    "entry": "study", "source_note": "material",
                    "thread": "question", "claim_revision": "finding",
                }.get(reference.get("kind"))
                if target_kind:
                    connect(public_kind, item["id"], "body-link",
                            f"ast.references[{index}]", target_kind, reference["id"])
    for domain in compiled.get("room", {}).get("domains", []):
        for public_kind, field in (
            ("material", "materialIds"), ("study", "studyIds"),
            ("question", "questionIds"),
        ):
            for target_id in domain.get(field, []):
                if (public_kind, target_id) in by_key:
                    navigation.append({
                        "kind": "domain", "id": domain["id"],
                        "member": f"{public_kind}/{target_id}",
                        "relation": "navigation",
                    })

    return {
        "schema": PUBLIC_MANIFEST_VERSION,
        "contract_version": CONTRACT_VERSION,
        "compiler_version": COMPILER_VERSION,
        "canonicalization": "ams-json-canonical/1",
        "objects": objects,
        "routes": {
            "home": "/",
            **{
                kind: [f"/{kind}/{item['id']}/" for item in compiled[family]]
                for kind, family in FAMILIES.items()
            },
        },
        "graphs": {
            "navigation_memberships": navigation,
            "references": references,
            "arguments": arguments,
        },
    }


def _direct_manifest(item: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for field, kind in (
        ("materialIds", "material"), ("studyIds", "study"),
        ("questionIds", "question"), ("findingIds", "finding"),
    ):
        for object_id in item.get(field, []):
            entries.append({"kind": kind, "id": object_id})
    for reading in item.get("readings", []):
        entries.append({"kind": "material", "id": reading["materialId"]})
    continuation = item.get("continuation") or {}
    for field, kind in (
        ("materialIds", "material"), ("studyIds", "study"),
    ):
        for object_id in continuation.get(field, []):
            entries.append({"kind": kind, "id": object_id})
    seen = set()
    return [
        entry for entry in entries
        if not (f"{entry['kind']}:{entry['id']}" in seen
                or seen.add(f"{entry['kind']}:{entry['id']}"))
    ]


def attach_packet_manifest(packets: dict, references: list[dict[str, Any]]) -> None:
    by_key = {}
    for (public_kind, object_id), packet in packets.items():
        by_key[f"{public_kind}/{object_id}"] = packet
    for key, packet in by_key.items():
        packet["manifest"] = [
            {
                "kind": by_key[reference["to"]]["kind"],
                "id": by_key[reference["to"]]["id"],
                "revision": by_key[reference["to"]]["entity_refs"][-1]["revision"]
                    if "entity_refs" in by_key[reference["to"]] else "",
                "publicKind": by_key[reference["to"]]["kind"],
                "title": by_key[reference["to"]]["title"],
                "url": "https://indeliblevivi.github.io/agent-memory-study/"
                    + by_key[reference["to"]]["kind"] + "/"
                    + by_key[reference["to"]]["id"] + "/",
            }
            for reference in references if reference["from"] == key
        ]


def _packet_map(compiled: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for public_kind, family in FAMILIES.items():
        for item in compiled[family]:
            if public_kind == "material":
                work, revision, note = compiled["corpus"]["by_alias"][item["id"]]
                result[(public_kind, item["id"])] = _source_packet(
                    item, work, revision, note
                )
            else:
                result[(public_kind, item["id"])] = _authored_packet(item, public_kind)
    return result


def _authored_payload(compiled, public_kind, item):
    return _authored_record(item, public_kind)


def material_entity_files(compiled: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Add canonical core records to the public shard set."""
    packets = _packet_map(compiled)
    attach_packet_manifest(packets, manifest["graphs"]["references"])
    files = entity_files(manifest, packets)
    for work in compiled["corpus"]["works"]:
        files[f"data/corpus/entities/source_work/{work['id'].split(':', 1)[1]}.json"] = work
        files[
            f"data/corpus/revisions/source_work/{work['id'].split(':', 1)[1]}/"
            f"{work['revision'].replace(':', '-')}.json"
        ] = work
    for revision in compiled["corpus"]["revisions"]:
        files[
            f"data/corpus/revisions/source_revision/{revision['id'].split(':', 1)[1]}/"
            f"{revision['revision'].replace(':', '-')}.json"
        ] = revision
    for note in compiled["corpus"]["notes"]:
        files[f"data/corpus/entities/source_note/{note['alias']}.json"] = note
        files[
            f"data/corpus/revisions/source_note/{note['alias']}/"
            f"{note['revision'].replace(':', '-')}.json"
        ] = note
    for public_kind, family in FAMILIES.items():
        if public_kind == "material":
            continue
        for item in compiled[family]:
            record = _authored_payload(compiled, public_kind, item)
            files[f"data/corpus/entities/{record['kind']}/{item['id']}.json"] = record
            files[
                f"data/corpus/revisions/{record['kind']}/{item['id']}/"
                f"{record['revision'].replace(':', '-')}.json"
            ] = record
    manifest["record_shards"] = sorted(path for path, value in files.items()
                                       if path.startswith("data/corpus/revisions/") and value.get("schema") == CONTRACT_VERSION)
    return files


def _authored_packet(item: dict[str, Any], public_kind: str) -> dict[str, Any]:
    content = copy.deepcopy(item)
    content.pop("recordedResults", None)
    return {
        "schema": "ams-study-packet/2",
        "contract_version": CONTRACT_VERSION,
        "compiler_version": COMPILER_VERSION,
        "kind": public_kind, "id": item["id"], "title": item["title"],
        "entity_refs": [_current_ref(item, public_kind)],
        "attribution": {
            "byline": item.get("byline", ""),
            "date": item.get("date") or item.get("updated"),
        },
        "content": content,
        "manifest_policy": (
            "Current public object plus bounded direct references; no linked full "
            "texts, private workflow, or inferred support."
        ),
    }
