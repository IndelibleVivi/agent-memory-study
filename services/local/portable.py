"""Explicit, lossless local migration. Imported text is never rendered as HTML."""
from __future__ import annotations

import base64
import binascii
import json

from schemas.validate import validate_entity, validate_graph, exact_ref, walk_exact_refs
from .records import ACTOR, command, record, ref
from .repository import RepositoryError, byte_digest, encoded, now

FORMAT = "ams-workspace/3"
LEGACY_FORMATS = ("ams-continuation/1", "ams-workspace/1", "ams-workspace/2")
RECOVERY_FORMAT = "ams-uncommitted-input/1"
MAX_BYTES = 32 * 1024 * 1024


def parse(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise RepositoryError("import-size", "私人研究文件限 32 MiB。")
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        raise RepositoryError("invalid-import", "文件必须是无重复键的 UTF-8 JSON。") from error
    if not isinstance(value, dict) or value.get("schema") not in (FORMAT, RECOVERY_FORMAT, *LEGACY_FORMATS):
        raise RepositoryError("import-format", "不是支持的 AMS 接续／案头文件。")
    legacy_limit = 128 * 1024 if value['schema'] == 'ams-continuation/1' else 2 * 1024 * 1024
    if value["schema"] in LEGACY_FORMATS and len(raw) > legacy_limit:
        raise RepositoryError("legacy-size", "旧格式文件超过其接续／案头容量合同。")
    return value


def recovery_view(value):
    if value['schema'] != RECOVERY_FORMAT:
        return value
    source = value.get('record', {})
    if source.get('kind') != 'session' or not isinstance(source.get('payload'), dict):
        raise RepositoryError('invalid-recovery', '没有可恢复的案头输入。')
    payload = source['payload']
    if not isinstance(payload.get('items'), list) or len(payload['items']) > 24:
        raise RepositoryError('invalid-recovery', '恢复案头应包含至多 24 个对象。')
    if any(not isinstance(item, dict) for item in payload['items']):
        raise RepositoryError('invalid-recovery', '恢复对象必须是记录。')
    return {'schema': RECOVERY_FORMAT, 'title': '恢复的未确认输入',
            **{key: payload.get(key, '') for key in ('question','synthesis','next')},
            'compare': [], 'items': [{'kind': 'recovered', 'id': item.get('key', str(index)),
             'note': item.get('note', ''), 'basis': encoded(item), 'anchor': item.get('anchor', ''),
             'excerpts': item.get('legacy_excerpts', [])} for index,item in enumerate(payload['items'])]}


def text(value, name, limit=200000):
    if not isinstance(value, str) or len(value) > limit:
        raise RepositoryError("import-field", f"{name} 必须是有界文字。")
    return value


def legacy_items(value):
    if value["schema"] == "ams-continuation/1":
        return [{**value, "excerpts": []}]
    items = value.get("items")
    if not isinstance(items, list) or len(items) > 24:
        raise RepositoryError("legacy-items", "旧案头应含最多 24 个对象。")
    return items


def preview(raw, public_lookup):
    value = recovery_view(parse(raw))
    digest = byte_digest(raw)
    if value["schema"] == FORMAT:
        records, blobs = value.get("records"), value.get("blobs")
        if not isinstance(records, list) or len(records) > 512 or not isinstance(blobs, dict):
            raise RepositoryError("portable-records", "一次导入限 512 个版本与明确文件清单。")
        seen = set()
        for item in records:
            validate_entity(item)
            key = (item["kind"], item["id"], item["revision"])
            if key in seen:
                raise RepositoryError("duplicate-revision", "导入文件含重复版本身份。")
            seen.add(key)
        public_records = value.get("public_records", [])
        if not isinstance(public_records, list) or len(public_records) > 512:
            raise RepositoryError("portable-public-records", "引用快照清单过大或无效。")
        validate_graph(public_records)
        validate_graph(records, public_records)
        for digest_key, contents in blobs.items():
            try:
                binary = base64.b64decode(contents, validate=True)
            except (ValueError, TypeError, binascii.Error) as error:
                raise RepositoryError("portable-blob", "文件编码损坏。") from error
            if byte_digest(binary) != digest_key:
                raise RepositoryError("portable-blob", "文件内容与身份不一致。")
        for item in records:
            if item['kind'] == 'artifact' and item['storage']['kind'] == 'blob':
                contents = blobs.get(item['artifact_digest'])
                if contents is None or len(base64.b64decode(contents, validate=True)) != item['byte_length']:
                    raise RepositoryError('portable-blob', '缺少完整依据文件。')
        roots = value.get("roots")
        if not isinstance(roots, list) or not roots or any((r.get("kind"), r.get("id"), r.get("revision")) not in seen for r in roots):
            raise RepositoryError("portable-roots", "案头入口没有对应的固定版本。")
        return {"digest": digest, "source_format": FORMAT, "records": len(records), "blobs": len(blobs), "roots": roots,
                "unresolved": [], "message": "确认后原样恢复这些固定版本；不会执行文件中的链接、HTML 或指令。"}
    items = legacy_items(value)
    seen, unresolved = set(), []
    for item in items:
        if not isinstance(item, dict):
            raise RepositoryError("legacy-item", "旧对象应为记录。")
        kind, id = text(item.get("kind"), "对象类型", 40), text(item.get("id"), "对象身份", 200)
        if (kind, id) in seen:
            raise RepositoryError("duplicate-item", "旧案头含重复对象；未写入。")
        seen.add((kind, id))
        for name in ("note", "basis", "anchor", "contentVersion"):
            text(item.get(name, ""), name)
        excerpts = item.get("excerpts", [])
        if not isinstance(excerpts, list) or len(excerpts) > 12:
            raise RepositoryError("legacy-excerpts", "旧对象最多含 12 条摘录。")
        excerpt_ids = set()
        for part in excerpts:
            if not isinstance(part, dict):
                raise RepositoryError("legacy-excerpt", "摘录应为记录。")
            eid = text(part.get("id"), "摘录身份", 200)
            if eid in excerpt_ids:
                raise RepositoryError("duplicate-excerpt", "重复摘录身份不能覆盖已有文字。")
            excerpt_ids.add(eid)
            for field in ("quote", "text", "note", "comment", "purpose", "role", "basis", "anchor", "contentVersion"):
                if field in part:
                    text(part[field], field)
        if public_lookup(kind, id) is None:
            unresolved.append({"kind": kind, "id": id})
    for field in ("title", "question", "synthesis", "next"):
        text(value.get(field, ""), field)
    return {"digest": digest, "source_format": value["schema"], "items": len(items), "unresolved": unresolved,
            "message": "旧快照与失踪对象会保留为私人纯文本依据；身份候选不会自动绑定。"}


def artifact(repo, value, role="other", media_type="application/json"):
    raw = value if isinstance(value, bytes) else encoded(value).encode("utf-8")
    digest = repo.put_blob(raw)
    return record("artifact", {"media_type": media_type, "byte_length": len(raw), "artifact_digest": digest,
                             "storage": {"kind": "blob", "locator": digest}, "role": role, "visibility": "private", "obtained_at": now()})


def confirm(repo, raw, expected_digest, public_lookup):
    report = preview(raw, public_lookup)
    if report["digest"] != expected_digest:
        raise RepositoryError("import-preview-changed", "文件与预览不同；请重新预览。")
    previous = repo.import_mapping(expected_digest)
    if previous is not None:
        return {"mapping": previous, "already_imported": True}
    value = recovery_view(parse(raw))
    commands = []
    if value["schema"] == FORMAT:
        currents = {}
        repo.cache_public_records(value.get("public_records", []))
        for binary in value["blobs"].values():
            repo.put_blob(base64.b64decode(binary, validate=True))
        for item in value["records"]:
            key = (item["kind"], item["id"])
            try:
                existing = repo.load(*key, item["revision"])
            except RepositoryError as error:
                if error.code != "not-found":
                    raise
                existing = None
            if existing is not None:
                if existing != item:
                    raise RepositoryError("revision-reuse", "相同版本身份对应不同内容。")
                continue
            if key not in currents:
                try:
                    repo.load(*key)
                except RepositoryError as error:
                    if error.code != "not-found":
                        raise
                else:
                    raise RepositoryError("import-conflict", "对象已在此环境中继续；请恢复到新数据目录或明确比较。", target={"kind": key[0], "id": key[1]})
            commands.append(command(item, previous=currents.get(key)))
            currents[key] = item
        mapping = {"roots": value["roots"], "format": FORMAT}
    else:
        original = artifact(repo, raw)
        commands.append(command(original))
        thread = record("thread", {"title": value.get("title", ""), "byline": "Local researcher", "status": "open",
                                    "payload": {"attention": "resting", "created_at": now(), "original_import_ref": ref(original)}})
        commands.append(command(thread))
        items = []
        for old in legacy_items(value):
            snapshot = artifact(repo, old)
            commands.append(command(snapshot))
            candidate = public_lookup(old["kind"], old["id"])
            # Old date/basis is not a current content identity. Even a known ID
            # remains tied to the imported bytes until the user explicitly binds.
            items.append({"key": old["kind"] + ":" + old["id"], "legacy": {"kind": old["kind"], "id": old["id"]},
                          "target_ref": ref(snapshot), "representation_ref": ref(snapshot), "binding": "unresolved" if candidate is None else "review-required",
                          "candidate_ref": candidate, "anchor": old.get("anchor", ""), "note": old.get("note", ""),
                          "legacy_excerpts": old.get("excerpts", []), "exercise": old.get("exercise")})
        session = record("session", {"thread_ref": ref(thread), "visibility": "private", "started_at": now(),
                                     "payload": {"items": items, "question": value.get("question", ""), "synthesis": value.get("synthesis", ""),
                                                 "next": value.get("next", ""), "attention": "resting", "return_when": value.get("return_when", ""), "compare": value.get("compare", [])}})
        commands.append(command(session))
        mapping = {"roots": [ref(thread), ref(session)], "format": value["schema"], "original_ref": ref(original), "unresolved": report["unresolved"]}
    if not commands:
        # Preserve the import identity transaction even if every snapshot exists.
        with repo.transaction():
            previous = repo.import_mapping(expected_digest)
            if previous is not None:
                return {'mapping': previous, 'already_imported': True}
            repo.db.execute("INSERT INTO imports VALUES (?,?,?,?)", (expected_digest, value["schema"], encoded(mapping), now()))
    else:
        try:
            repo.apply_unit(commands, import_record={"digest": expected_digest, "source_format": value["schema"], "mapping": mapping})
        except RepositoryError as error:
            if error.code != 'already-imported': raise
            return {'mapping': error.details['mapping'], 'already_imported': True}
    return {"mapping": mapping, "already_imported": False}


def export(repo, roots):
    """Portable closure of selected local roots, not the entire private database."""
    selected = {}
    public_refs, public_records = [], {}
    cached = {exact_ref(ref(value)): value for value in repo.public_records()}
    def visit(pointer):
        key = (pointer["kind"], pointer["id"], pointer["revision"])
        if key in selected or key in public_records:
            return
        if key in cached:
            item = cached[key]
            public_records[key] = item
            public_refs.append(pointer)
            for dependency in walk_exact_refs(item):
                visit(dependency)
            return
        try:
            item = repo.load(*key)
        except RepositoryError as error:
            if error.code != "not-found":
                raise
            raise RepositoryError("missing-reference", "选定案头缺少固定依据；请先恢复原快照。", reference=pointer) from error
        selected[key] = item
        for dependency in walk_exact_refs(item):
            visit(dependency)
    for root in roots:
        visit(root)
    # Immutable revision insertion order preserves each entity's local history.
    ordered = sorted(selected.values(), key=lambda item: repo.db.execute("SELECT rowid FROM snapshots WHERE revision=?", (item["revision"],)).fetchone()[0])
    blobs = {item["artifact_digest"]: base64.b64encode(repo.read_blob(item["artifact_digest"])).decode("ascii")
             for item in ordered if item["kind"] == "artifact" and item["storage"]["kind"] == "blob"}
    value = {"schema": FORMAT, "exported_at": now(), "roots": roots, "records": ordered, "blobs": blobs, "public_refs": public_refs, "public_records": list(public_records.values())}
    if len(encoded(value).encode("utf-8")) > MAX_BYTES:
        raise RepositoryError("portable-size", "选定案头超过便携文件上限；使用完整 backup 保存所有依据。")
    return value
