"""Local record construction using the canonical schema and digest implementation."""
from __future__ import annotations

import uuid

from schemas.validate import content_digest, content_fields, validate_command, validate_entity


ACTOR = {"kind": "human", "id": "actor:local-researcher"}


def identity(kind):
    return kind + ":" + uuid.uuid4().hex


def ref(record):
    return {key: record[key] for key in ("kind", "id", "revision")}


def record(kind, fields, *, id=None, previous=None):
    value = {"schema": "ams-core/2", "kind": kind, "id": id or (previous and previous["id"]) or identity(kind),
             **fields, "revision": identity("rev")}
    value["state_revision"] = value["revision"]
    fields = content_fields(value)
    value["content_digest"] = content_digest(value, fields)
    validate_entity(value)
    return value


def command(value, *, previous=None, actor=None, command_id=None):
    key = command_id or identity("command")
    result = {"schema": "ams-command/1", "kind": "command", "command_id": key,
              "idempotency_key": key, "operation": "update" if previous else "create",
              "target": {"kind": value["kind"], "id": value["id"]},
              "actor": actor or ACTOR, "record": value}
    if previous:
        result["expected_revision"] = previous["state_revision"]
    validate_command(result)
    return result


def revise(previous, **changes):
    fields = {k: v for k, v in previous.items() if k not in {"schema", "kind", "id", "revision", "state_revision", "content_digest"}}
    return record(previous["kind"], {**fields, **changes}, previous=previous)
