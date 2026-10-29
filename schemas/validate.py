#!/usr/bin/env python3
"""Validate AMS core records, immutable references, and command envelopes."""

from __future__ import annotations

import argparse
import copy
from functools import lru_cache
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "core.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
CANONICALIZATION = "ams-json-canonical/1"


class ContractError(ValueError):
    pass


def canonical_object_bytes(value: Any) -> bytes:
    """AMS JSON canonical v1 used only for fixture and content identity."""
    if not isinstance(value, dict):
        raise ContractError("canonicalization: expected a JSON object")
    def normalize(item: Any) -> Any:
        if isinstance(item, dict):
            if not all(isinstance(key, str) for key in item):
                raise ContractError("canonicalization: object keys must be strings")
            return {key: normalize(nested) for key, nested in item.items()}
        elif isinstance(item, list):
            return [normalize(nested) for nested in item]
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            if not math.isfinite(item) or int(item) != item or abs(item) > 2**53 - 1:
                raise ContractError("canonicalization: v1 supports safe integers only")
            return int(item)
        return item
    value = normalize(value)
    try:
        return json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError(f"canonicalization: unsupported JSON value: {exc}") from exc


def content_digest(record: dict[str, Any],
                   fields: list[str] | None = None) -> dict[str, Any]:
    if fields is None:
        fields = content_fields(record)
    missing = sorted(field for field in fields if field not in record)
    if missing:
        raise ContractError(f"digest: missing canonical fields {missing}")
    payload = {field: record[field] for field in fields}
    return {
        "algorithm": "sha256",
        "value": hashlib.sha256(canonical_object_bytes(payload)).hexdigest(),
        "canonicalization": CANONICALIZATION,
        "fields": sorted(fields),
    }


def schema_content_fields() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for definition in SCHEMA["$defs"].values():
        if not isinstance(definition, dict):
            continue
        properties = definition.get("properties", {})
        kind = properties.get("kind", {}).get("const")
        fields = definition.get("x-ams-content-fields")
        if isinstance(kind, str) and isinstance(fields, list):
            result[kind] = list(fields)
    return result


CONTENT_FIELDS = schema_content_fields()

def content_fields(record: dict[str, Any], fields: list[str] | None = None) -> list[str]:
    selected = fields if fields is not None else CONTENT_FIELDS.get(record["kind"], [])
    return [field for field in selected if field in record]


def generated_js_content_fields() -> dict[str, list[str]]:
    source = (ROOT / "packages/research-core/content-fields.generated.js").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"export const CONTENT_FIELDS = (\{.*\});\s*$", source, re.S,
    )
    if not match:
        raise ContractError("generated JS field map cannot be parsed")
    return json.loads(match.group(1))


def assert_generated_field_parity() -> None:
    schema_fields = schema_content_fields()
    expected = {kind: fields for kind, fields in CONTENT_FIELDS.items() if kind in schema_fields}
    if generated_js_content_fields() != expected:
        raise ContractError("schema content-field map differs from generated JS")


def check_digest(record: dict[str, Any]) -> None:
    observed = record.get("content_digest")
    if not observed:
        return
    fields = observed.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ContractError("digest: fields must be a non-empty list")
    canonical = CONTENT_FIELDS.get(record["kind"])
    if canonical is not None and sorted(fields) != sorted(content_fields(record, canonical)):
        raise ContractError("digest: declared fields differ from the kind's canonical fields")
    if observed != content_digest(record, content_fields(record, fields)):
        raise ContractError("digest: content fields do not match declared digest")


@lru_cache(maxsize=None)
def _validator(definition):
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ModuleNotFoundError as exc:
        raise ContractError(
            "jsonschema is required: python3 -m pip install -r schemas/requirements.txt"
        ) from exc
    Draft202012Validator.check_schema(SCHEMA)
    formats = FormatChecker()
    missing = {"date-time", "uri"}.difference(formats.checkers)
    if missing:
        raise ContractError(f"format dependencies missing: {sorted(missing)}")
    schema = copy.deepcopy(SCHEMA)
    schema["$ref"] = f"#/$defs/{definition}"
    validator = Draft202012Validator(schema, format_checker=formats)
    return validator


def check_structure(value: Any, definition: str = "EntityRecord") -> None:
    errors = sorted(_validator(definition).iter_errors(value), key=lambda error: [str(part) for part in error.path])
    if errors:
        error = errors[0]
        path = "/".join(map(str, error.absolute_path)) or "<root>"
        raise ContractError(f"schema:{definition}:{path}: {error.message}")


def exact_ref(value: Any) -> tuple[str, str, str]:
    if not isinstance(value, dict) or set(value) != {"kind", "id", "revision"}:
        raise ContractError("ref: expected exact kind/id/revision")
    return value["kind"], value["id"], value["revision"]


def record_ref(record: dict[str, Any]) -> dict[str, str]:
    return {key: record[key] for key in ("kind", "id", "revision")}


def walk_exact_refs(value: Any):
    if isinstance(value, dict):
        if set(value) == {"kind", "id", "revision"}:
            yield value
        for nested in value.values():
            yield from walk_exact_refs(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk_exact_refs(nested)


def validate_entity(record: dict[str, Any]) -> None:
    names = {
        "source_work": "SourceWork", "source_revision": "SourceRevision",
        "source_note": "SourceNote", "read_activity": "ReadActivity",
        "relation_proposal": "RelationProposal",
        "evidence_relation": "EvidenceRelation",
        "support_bundle": "SupportBundle", "claim_revision": "ClaimRevision",
        "publication_manifest": "PublicationManifest", "changeset": "ChangeSet",
    }
    definition = names.get(record["kind"], record["kind"].title().replace("_", ""))
    check_structure(record, definition)
    check_digest(record)


def validate_command(command: dict[str, Any]) -> None:
    check_structure(command, "Command")
    record = command["record"]
    validate_entity(record)
    if (command["target"]["kind"], command["target"]["id"]) != (
        record["kind"], record["id"]
    ):
        raise ContractError("command: target differs from record")
    if record.get("state_revision") != record["revision"]:
        raise ContractError("command: new snapshot must point at its own revision")
    if command["operation"] == "update" and command["expected_revision"] == record["revision"]:
        raise ContractError("command: update cannot retain its expected revision")


def _ref_tuple(value: Any) -> tuple[str, str, str]:
    if not isinstance(value, dict):
        raise ContractError("graph: reference must be an object")
    try:
        return value["kind"], value["id"], value["revision"]
    except KeyError as exc:
        raise ContractError("graph: reference requires kind, id and revision") from exc


def validate_graph(records: list[dict[str, Any]],
                   public_records: list[dict[str, Any]] | None = None) -> None:
    """Validate cross-record invariants after structural command validation.

    The repository calls this within its transaction after applying the unit's
    commands to a candidate set. ``records`` and ``public_records`` are complete
    immutable snapshots, not mutable heads.
    """
    public_records = public_records or []
    all_records = [*records, *public_records]
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    revisions: dict[str, dict[str, Any]] = {}
    addresses: dict[tuple[str, str], set[tuple[str, str, str]]] = {}
    output_lineage: dict[tuple[str, str, str], list[tuple[str, str, str]]] = {}
    for record in all_records:
        validate_entity(record)
        key = _ref_tuple(record_ref(record))
        if key in index and (index[key] != record or index[key]["kind"] != record["kind"]):
            raise ContractError("graph: same revision has different payloads")
        prior = revisions.setdefault(record["revision"], record)
        if prior != record:
            raise ContractError("graph: same revision has different payloads")
        index[key] = record
        addresses.setdefault((record["kind"], record["id"]), set()).add(key)
        if record["kind"] == "extraction":
            output_lineage.setdefault(_ref_tuple(record["output_artifact_ref"]), []).append(
                _ref_tuple(record["source_revision_ref"])
            )
    for record in records:
        for nested in walk_exact_refs(record):
            if _ref_tuple(nested) not in index:
                raise ContractError(f"graph: dangling reference {_ref_tuple(nested)}")
        kind = record["kind"]
        if kind == "source_revision":
            work = index[_ref_tuple(record["work_ref"])]
            if work["kind"] != "source_work" or work["id"] != record["id"]:
                raise ContractError("graph: source revision must belong to its work")
            identity = record["identity"]
            if identity["mode"] == "observed-snapshot" and identity.get("snapshot_captured"):
                artifact = index[_ref_tuple(identity["artifact_ref"])]
                if _ref_tuple(artifact["source_revision_ref"]) != _ref_tuple(record_ref(record)):
                    raise ContractError("graph: observed snapshot bytes bind another revision")
        elif kind == "source_note":
            work, revision = index[_ref_tuple(record["work_ref"])], index[_ref_tuple(record["source_revision_ref"])]
            if work["kind"] != "source_work" or revision["kind"] != "source_revision":
                raise ContractError("graph: source note has wrong typed refs")
            if revision["work_ref"] != record["work_ref"]:
                raise ContractError("graph: source note revision belongs to another work")
            if record["alias"] not in work["aliases"]:
                raise ContractError("graph: source note alias is not owned by its work")
        elif kind in {"read_activity", "excerpt"}:
            representation = index[_ref_tuple(record["representation_ref"])]
            target = _ref_tuple(record["target_ref"])
            allowed = set(output_lineage.get(_ref_tuple(record["representation_ref"]), []))
            if representation.get("source_revision_ref"):
                allowed.add(_ref_tuple(representation["source_revision_ref"]))
            if representation.get("representation_of"):
                allowed.add(_ref_tuple(representation["representation_of"]))
            allowed.add(_ref_tuple(record["representation_ref"]))
            if target not in allowed:
                raise ContractError("graph: representation is not bound to target revision")
            if kind == "read_activity" and record["method"] == "agent-delivered":
                receipt = index[_ref_tuple(record["receipt_ref"])]
                if receipt["role"] != "receipt":
                    raise ContractError("graph: delivered reading needs receipt artifact")
        elif kind == "evidence_relation":
            proposal = index[_ref_tuple(record["proposal_ref"])]
            for field in ("from_ref", "to_ref", "relation", "scope", "scope_binding", "locator"):
                if record[field] != proposal[field]:
                    raise ContractError(f"graph: accepted relation {field} differs from proposal")
            review = record["review"]
            if review["actor"]["kind"] != "human" and "delegation_ref" not in review:
                raise ContractError("graph: acceptance needs review or delegation")
        elif kind == "support_bundle":
            if record["combination"] == "all-premises":
                premises = {_ref_tuple(ref) for ref in record.get("premise_refs", [])}
                if not premises:
                    raise ContractError("graph: AND bundle requires premises")
                covered = set()
                for relation_ref in record.get("relation_refs", []):
                    relation = index[_ref_tuple(relation_ref)]
                    if relation["relation"] not in {"supports", "derives"}:
                        raise ContractError("graph: unsupported bundle relation")
                    if relation["to_ref"] != record["conclusion_ref"]:
                        raise ContractError("graph: bundle relation targets another conclusion")
                    if any(relation[field] != record[field] for field in ("scope", "scope_binding")):
                        raise ContractError("graph: bundle scope differs from relation")
                    covered.add(_ref_tuple(relation["from_ref"]))
                if covered != premises:
                    raise ContractError("graph: each premise needs an accepted relation")
            else:
                warrants = record.get("warrant_refs", [])
                if len(warrants) < 2:
                    raise ContractError("graph: OR bundle needs two warrants")
                for warrant_ref in warrants:
                    warrant = index[_ref_tuple(warrant_ref)]
                    if warrant["combination"] != "all-premises":
                        raise ContractError("graph: OR alternatives must be AND bundles")
                    if any(warrant[field] != record[field] for field in ("scope", "scope_binding")):
                        raise ContractError("graph: OR bundle scope differs from warrant")
                    if warrant["conclusion_ref"] != record["conclusion_ref"]:
                        raise ContractError("graph: OR alternatives support different conclusions")
            conclusion = index[_ref_tuple(record["conclusion_ref"])]
            if conclusion["kind"] != "claim_revision" or any(conclusion[field] != record[field] for field in ("scope", "scope_binding")):
                raise ContractError("graph: bundle scope differs from conclusion")
            review = record["review"]
            if review["actor"]["kind"] != "human" and "delegation_ref" not in review:
                raise ContractError("graph: bundle acceptance needs review or delegation")
        elif kind == "changeset":
            for item in record["items"]:
                if item["application_state"] == "applied":
                    if item["review_state"] != "accepted":
                        raise ContractError("graph: applied item requires accepted review")
                    result, base = item.get("result_ref"), item["base_ref"]
                    if result is None:
                        raise ContractError("graph: applied item needs result")
                    if (result["kind"], result["id"]) != (base["kind"], base["id"]):
                        raise ContractError("graph: applied result changes target identity")
                    if result["revision"] == base["revision"]:
                        raise ContractError("graph: applied result needs a new revision")
                elif item["application_state"] == "checked-unchanged":
                    if item["review_state"] != "accepted":
                        raise ContractError("graph: unchanged item requires accepted review")
                    if "result_ref" in item or not isinstance(item["change"], dict) or item["change"].get("mode") != "no-change":
                        raise ContractError("graph: checked-unchanged needs no-change mode")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", type=Path)
    parser.add_argument("--definition", default="EntityRecord")
    parser.add_argument("--command", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command:
            validate_command(json.loads(args.command.read_text(encoding="utf-8")))
            print(f"PASS command {args.command.name}")
        elif args.check:
            value = json.loads(args.check.read_text(encoding="utf-8"))
            check_structure(value, args.definition)
            if args.definition == "EntityRecord":
                check_digest(value)
            print(f"PASS structure {args.check.name} as {args.definition}")
        else:
            parser.print_help()
            return 2
        return 0
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print(f"contract error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
