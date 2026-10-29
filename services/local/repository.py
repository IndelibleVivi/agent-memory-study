"""Transactional immutable entity storage, independent of the public compiler.

The caller supplies the canonical command validator. This layer owns revision,
commit, retry and byte durability, never the meaning of research evidence.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import threading
import uuid


DB_VERSION = 4
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def byte_digest(value: bytes):
    return "sha256:" + hashlib.sha256(value).hexdigest()


class RepositoryError(ValueError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details

    def as_dict(self):
        return {"code": self.code, "message": str(self), **self.details}


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_durable(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_directory(path.parent)


def sync_directories(root):
    for directory in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        fsync_directory(directory)
    fsync_directory(root)


def backup_attempts(db):
    """A copied DB can only refer to immutable, terminal attempt directories."""
    from .jobs import TERMINAL
    attempts = {}
    if db.execute("PRAGMA user_version").fetchone()[0] < 2:
        return attempts
    for jid, number, state, digest in db.execute("SELECT job_id,number,state,result_digest FROM execution_attempts ORDER BY job_id,number"):
        if state not in TERMINAL:
            raise RepositoryError("backup-active-jobs", "任务尚未结束；请等待完成或停止任务后再备份。", job_id=jid)
        try:
            valid = str(uuid.UUID(jid)) == jid and type(number) is int and number > 0
        except (ValueError, AttributeError):
            valid = False
        if not valid:
            raise RepositoryError("backup-corrupt", "任务身份无效。")
        attempts[f"jobs/{jid}/attempt-{number}"] = {"state": state, "digest": digest}
    return attempts


def backup_file(root, relative):
    """Do not follow symlinks in a backup, including intermediate directories."""
    if not isinstance(relative, str) or "\\" in relative:
        raise RepositoryError("backup-corrupt", "备份文件路径无效。")
    path = Path(relative)
    if path.is_absolute() or path.as_posix() != relative or any(part in (".", "..") for part in path.parts):
        raise RepositoryError("backup-corrupt", "备份文件路径越界。")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise RepositoryError("backup-corrupt", "备份不能引用符号链接。")
    if not current.is_file():
        raise RepositoryError("backup-corrupt", "备份缺少原始文件。", path=relative)
    return current.read_bytes()


def check_attempt_results(root, attempts):
    for relative, attempt in attempts.items():
        if attempt["state"] == "succeeded":
            value = backup_file(root, relative + "/result.json")
            if hashlib.sha256(value).hexdigest() != attempt["digest"]:
                raise RepositoryError("backup-corrupt", "任务结果与数据库中的固定依据不一致。")


def local_filesystem(path):
    """WAL requires same-host shared memory; reject network/unknown mounts."""
    path = str(Path(path).resolve())
    entries = []
    if sys.platform == "darwin":
        lines = subprocess.run(["/sbin/mount"], check=True, capture_output=True, text=True).stdout.splitlines()
        for line in lines:
            match = re.fullmatch(r".+ on (.+) \((.+)\)", line)
            if match:
                entries.append((match[1], "local" in match[2].split(", ")))
    elif sys.platform.startswith("linux"):
        local_types = {"ext2", "ext3", "ext4", "xfs", "btrfs", "zfs", "tmpfs", "overlay", "f2fs", "jfs", "vfat", "exfat"}
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            left, right = line.split(" - ", 1)
            mount = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), left.split()[4])
            entries.append((mount, right.split()[0] in local_types))
    matching = [(mount, local) for mount, local in entries if path == mount or path.startswith(mount.rstrip("/") + "/")]
    if not matching or not max(matching, key=lambda entry: len(entry[0]))[1]:
        raise RepositoryError("nonlocal-filesystem", "活动数据库只支持已确认的本机文件系统；请把数据目录放到本地磁盘。")


from schemas.validate import validate_graph, exact_ref, record_ref


class Repository:
    """One serialized writer per process; SQLite also arbitrates CLI processes.

    Returned command receipts always follow COMMIT. An interrupted caller can
    resend the same command and obtain the original receipt without a new event.
    """
    def __init__(self, data_root, project, validator, *, graph_validator=validate_graph):
        self.root = Path(data_root).expanduser().resolve()
        self.project = Path(project).resolve()
        if self.root == self.project or self.project in self.root.parents:
            raise RepositoryError("private-root-in-project", "数据目录必须在 Git 项目之外。")
        if not callable(validator):
            raise TypeError("a canonical command validator is required")
        local_filesystem(self.root)
        # The WAL reset fix is required when backup/CLI connections coexist.
        version = sqlite3.sqlite_version_info
        if version < (3, 51, 3) and not ((3, 50, 7) <= version < (3, 51, 0) or (3, 44, 6) <= version < (3, 45, 0)):
            raise RepositoryError("sqlite-version", "SQLite 需要含 WAL-reset 修复的版本（推荐 3.51.3+）。", actual=sqlite3.sqlite_version)
        self.validator = validator
        self.graph_validator = graph_validator
        self.ready = False
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.blob_root = self.root / "blobs"
        self.blob_root.mkdir(exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.db = sqlite3.connect(self.root / "research.sqlite3", timeout=10, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA busy_timeout=10000")
        try:
            self._migrate()
            self.ready = True
        except BaseException:
            self.db.close()
            raise

    def _migrate(self):
        with self.transaction():
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version > DB_VERSION:
                raise RepositoryError("newer-database", "这个数据目录由更高版本创建；旧程序拒绝写入。", version=version)
            if version == 0:
                statements = [
                    "CREATE TABLE snapshots (revision TEXT PRIMARY KEY, kind TEXT NOT NULL, id TEXT NOT NULL, record TEXT NOT NULL, created_at TEXT NOT NULL)",
                    "CREATE TABLE entities (kind TEXT NOT NULL, id TEXT NOT NULL, state_revision TEXT NOT NULL REFERENCES snapshots(revision), PRIMARY KEY(kind,id))",
                    "CREATE TABLE commands (command_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, receipt TEXT NOT NULL)",
                    "CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT, command_id TEXT NOT NULL UNIQUE REFERENCES commands(command_id), kind TEXT NOT NULL, id TEXT NOT NULL, revision TEXT NOT NULL REFERENCES snapshots(revision), occurred_at TEXT NOT NULL)",
                    "CREATE TABLE blobs (digest TEXT PRIMARY KEY, byte_length INTEGER NOT NULL)",
                    "CREATE TABLE imports (digest TEXT PRIMARY KEY, source_format TEXT NOT NULL, mapping TEXT NOT NULL, imported_at TEXT NOT NULL)",
                    "CREATE TABLE public_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
                    "CREATE INDEX snapshots_address ON snapshots(kind,id)",
                ]
                for statement in statements:
                    self.db.execute(statement)
            if version < 2:
                from .jobs import JOBS_MIGRATION_SQL
                for statement in JOBS_MIGRATION_SQL:
                    self.db.execute(statement)
            if version < 3:
                from .arguments import ARGUMENTS_MIGRATION_SQL
                from .revisions import REVISIONS_MIGRATION_SQL
                from .publication import PUBLICATION_MIGRATION_SQL
                for statement in (*ARGUMENTS_MIGRATION_SQL, *REVISIONS_MIGRATION_SQL, *PUBLICATION_MIGRATION_SQL):
                    self.db.execute(statement)
            if version < 4:
                from .intake import INTAKE_MIGRATION_SQL
                from .identity import IDENTITY_MIGRATION_SQL
                from .acquisition import ACQUISITION_MIGRATION_SQL
                from .connectors import CONNECTORS_MIGRATION_SQL
                for statement in (*INTAKE_MIGRATION_SQL, *IDENTITY_MIGRATION_SQL, *ACQUISITION_MIGRATION_SQL, *CONNECTORS_MIGRATION_SQL):
                    self.db.execute(statement)
            self.db.execute(f"PRAGMA user_version={DB_VERSION}")

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                start = self.db.execute("SELECT coalesce(max(rowid),0) FROM snapshots").fetchone()[0] if self.ready else 0
                yield
                if self.ready and self.graph_validator:
                    changed = [json.loads(row[0]) for row in self.db.execute("SELECT record FROM snapshots WHERE rowid>?", (start,))]
                    if changed:
                        history = [json.loads(row[0]) for row in self.db.execute("SELECT record FROM snapshots WHERE rowid<=?", (start,))]
                        self.graph_validator(changed, [*history, *self.public_records()])
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def close(self):
        with self.lock:
            self.db.close()

    def load(self, kind, id, revision=None):
        with self.lock:
            if revision is None:
                row = self.db.execute("SELECT s.record FROM entities e JOIN snapshots s ON s.revision=e.state_revision WHERE e.kind=? AND e.id=?", (kind, id)).fetchone()
            else:
                row = self.db.execute("SELECT record FROM snapshots WHERE kind=? AND id=? AND revision=?", (kind, id, revision)).fetchone()
            if row is None:
                if revision is not None:
                    public = next((value for value in self.public_records() if (value['kind'],value['id'],value['revision']) == (kind,id,revision)), None)
                    if public is not None:
                        return public
                raise RepositoryError("not-found", "找不到该对象或指定版本。", kind=kind, id=id, revision=revision)
            return json.loads(row[0])

    def list(self, kind=None):
        with self.lock:
            rows = self.db.execute("SELECT s.record FROM entities e JOIN snapshots s ON s.revision=e.state_revision" + (" WHERE e.kind=?" if kind else "") + " ORDER BY s.created_at DESC,e.id", (kind,) if kind else ()).fetchall()
            return [json.loads(row[0]) for row in rows]

    def history(self, kind, id):
        with self.lock:
            return [json.loads(row[0]) for row in self.db.execute("SELECT record FROM snapshots WHERE kind=? AND id=? ORDER BY rowid", (kind, id))]

    def _apply(self, command):
        self.validator(command)
        payload = encoded(command)
        previous = self.db.execute("SELECT payload,receipt FROM commands WHERE command_id=? OR idempotency_key=?", (command["command_id"], command["idempotency_key"])).fetchall()
        if previous:
            if len(previous) != 1 or previous[0]["payload"] != payload:
                raise RepositoryError("idempotency-conflict", "相同命令或幂等键对应不同内容；未接受本次写入。", command_id=command["command_id"])
            return json.loads(previous[0]["receipt"])
        target, record = command["target"], command["record"]
        kind, id, revision = target["kind"], target["id"], record["revision"]
        if (record["kind"], record["id"]) != (kind, id):
            raise RepositoryError("target-mismatch", "命令目标与记录身份不同。")
        current = self.db.execute("SELECT state_revision FROM entities WHERE kind=? AND id=?", (kind, id)).fetchone()
        current_revision = current[0] if current else None
        if command["operation"] == "create":
            valid = current is None and "expected_revision" not in command
        elif command["operation"] == "update":
            valid = current is not None and command.get("expected_revision") == current_revision
        else:
            raise RepositoryError("invalid-operation", "只接受 create 或 update。")
        if not valid:
            raise RepositoryError("revision-conflict", "对象已改变；保留未接受输入，读取当前版本后再决定。", current_revision=current_revision, current=self.load(kind, id) if current else None, rejected_command=command)
        if self.db.execute("SELECT 1 FROM snapshots WHERE revision=?", (revision,)).fetchone():
            raise RepositoryError("revision-reuse", "已存在的不可变 revision 不能再次用于写入。", revision=revision)
        if record["kind"] == "artifact":
            digest = record["artifact_digest"]
            value = self.read_blob(digest)
            if len(value) != record["byte_length"]:
                raise RepositoryError("blob-length", "文件长度与 Artifact 不匹配。", digest=digest)
            self.db.execute("INSERT OR IGNORE INTO blobs VALUES (?,?)", (digest, len(value)))
        timestamp = now()
        self.db.execute("INSERT INTO snapshots VALUES (?,?,?,?,?)", (revision, kind, id, encoded(record), timestamp))
        self.db.execute("INSERT INTO entities VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET state_revision=excluded.state_revision", (kind, id, revision))
        receipt = {"schema": "ams-command-receipt/1", "command_id": command["command_id"], "target": target, "state_revision": revision, "committed_at": timestamp}
        self.db.execute("INSERT INTO commands VALUES (?,?,?,?)", (command["command_id"], command["idempotency_key"], payload, encoded(receipt)))
        self.db.execute("INSERT INTO events(command_id,kind,id,revision,occurred_at) VALUES (?,?,?,?,?)", (command["command_id"], kind, id, revision, timestamp))
        return receipt

    def apply(self, command):
        return self.apply_unit([command])[0]

    def apply_unit(self, commands, import_record=None):
        if not isinstance(commands, list) or not commands or len(commands) > 512:
            raise RepositoryError("invalid-unit", "一次事务接受 1–512 个明确命令。")
        with self.transaction():
            if import_record:
                existing = self.import_mapping(import_record['digest'])
                if existing is not None:
                    raise RepositoryError('already-imported', '同一文件已由另一笔导入完成。', mapping=existing)
            receipts = [self._apply(command) for command in commands]
            if import_record:
                self.db.execute("INSERT INTO imports VALUES (?,?,?,?)", (import_record["digest"], import_record["source_format"], encoded(import_record["mapping"]), now()))
        with self.changed:
            self.changed.notify_all()
        return receipts

    def import_mapping(self, digest):
        with self.lock:
            row = self.db.execute("SELECT mapping FROM imports WHERE digest=?", (digest,)).fetchone()
            return json.loads(row[0]) if row else None

    def events(self, after=0, timeout=0):
        with self.changed:
            def read():
                return [dict(row) for row in self.db.execute("SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT 500", (after,))]
            rows = read()
            if not rows and timeout:
                self.changed.wait(min(timeout, 25))
                rows = read()
            return rows

    def blob_path(self, digest):
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise RepositoryError("invalid-digest", "不是有效的 SHA-256 文件身份。")
        return self.blob_root / digest[7:9] / digest[9:]

    def put_blob(self, value: bytes):
        digest = byte_digest(value)
        path = self.blob_path(digest)
        path.parent.mkdir(exist_ok=True, mode=0o700)
        if path.exists():
            if self.read_blob(digest) != value:
                raise RepositoryError("blob-corrupt", "已有不可变文件损坏。", digest=digest)
            return digest
        partial = path.with_name(path.name + "." + uuid.uuid4().hex + ".partial")
        with partial.open("xb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        # Link is exclusive: a concurrent upload cannot overwrite an old blob.
        try:
            os.link(partial, path)
        except FileExistsError:
            self.read_blob(digest)
        finally:
            partial.unlink()
        fsync_directory(path.parent)
        return digest

    def read_blob(self, digest):
        path = self.blob_path(digest)
        if not path.is_file() or path.is_symlink():
            raise RepositoryError("blob-missing", "依据文件缺失；保留记录并恢复备份。", digest=digest)
        value = path.read_bytes()
        if byte_digest(value) != digest:
            raise RepositoryError("blob-corrupt", "依据文件内容与身份不匹配。", digest=digest)
        return value

    def cache_public(self, manifest, binding):
        with self.transaction():
            self.db.execute("INSERT INTO public_cache VALUES ('manifest',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (encoded({"binding": binding, "manifest": manifest}),))

    def public_records(self):
        with self.lock:
            row = self.db.execute("SELECT value FROM public_cache WHERE key='records'").fetchone()
            return json.loads(row[0]) if row else []

    def cache_public_records(self, records):
        # Rebuilding the index cannot erase versions referenced by an old desk.
        with self.transaction():
            existing = {exact_ref(record_ref(value)): value for value in self.public_records()}
            for value in records:
                key = exact_ref(record_ref(value))
                if key in existing and existing[key] != value:
                    raise RepositoryError("public-revision-reuse", "公开依据的同一 revision 出现不同内容；保留旧 cache。")
                existing[key] = value
            values = list(existing.values())
            validate_graph(values)
            self.db.execute("INSERT INTO public_cache VALUES ('records',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (encoded(values),))

    def doctor(self):
        with self.lock:
            integrity = self.db.execute("PRAGMA quick_check").fetchone()[0]
            foreign_keys = [tuple(row) for row in self.db.execute("PRAGMA foreign_key_check")]
            blobs = list(self.db.execute("SELECT * FROM blobs"))
            counts = {row[0]: row[1] for row in self.db.execute("SELECT kind,count(*) FROM entities GROUP BY kind")}
            records = [json.loads(row[0]) for row in self.db.execute("SELECT record FROM snapshots")]
            public = self.public_records()
        errors = []
        contract_errors = []
        if self.graph_validator:
            try:
                self.graph_validator(records, public)
            except ValueError as error:
                contract_errors.append(str(error))
        for blob in blobs:
            try:
                if len(self.read_blob(blob["digest"])) != blob["byte_length"]:
                    raise RepositoryError("blob-length", "文件长度不匹配。", digest=blob["digest"])
            except RepositoryError as error:
                errors.append(error.as_dict())
        return {"schema_version": DB_VERSION, "sqlite": sqlite3.sqlite_version, "journal": "wal", "integrity": integrity, "foreign_key_errors": foreign_keys, "contract_errors": contract_errors, "blob_errors": errors, "entities": counts, "ok": integrity == "ok" and not foreign_keys and not errors and not contract_errors}

    def backup(self, destination):
        destination = Path(destination).expanduser().resolve()
        if destination.exists():
            raise RepositoryError("output-exists", "备份目标已经存在；请选择新目录。")
        if destination == self.project or self.project in destination.parents:
            raise RepositoryError("private-root-in-project", "私人备份必须保存在 Git 项目之外。")
        if destination == self.root or self.root in destination.parents:
            raise RepositoryError("nested-backup", "备份应在活动数据目录之外。")
        partial = destination.with_name(destination.name + ".partial-" + uuid.uuid4().hex)
        partial.mkdir(parents=True, mode=0o700)
        copy = sqlite3.connect(partial / "research.sqlite3")
        try:
            with self.lock:
                self.db.backup(copy)
            blobs = copy.execute("SELECT digest,byte_length FROM blobs ORDER BY digest").fetchall()
            attempts = backup_attempts(copy)
        finally:
            copy.close()
        for digest, size in blobs:
            value = self.read_blob(digest)
            if len(value) != size:
                raise RepositoryError("blob-length", "备份未完成：文件长度不匹配。", digest=digest)
            path = partial / "blobs" / digest[7:9] / digest[9:]
            write_durable(path, value)
        job_files = []
        check_attempt_results(self.root, attempts)
        for relative in attempts:
            directory = self.root / relative
            # A queued attempt cancelled before it starts legitimately has no files.
            if not directory.exists() and not directory.is_symlink():
                continue
            for node in [directory, *sorted(directory.rglob("*"))]:
                if node.is_symlink():
                    raise RepositoryError("backup-corrupt", "任务原件不能是符号链接。")
                if node.is_dir():
                    continue
                name = node.relative_to(self.root).as_posix()
                value = backup_file(self.root, name)
                write_durable(partial / name, value)
                job_files.append({"path": name, "digest": byte_digest(value), "byte_length": len(value)})
        database = partial / "research.sqlite3"
        with database.open("rb") as stream:
            os.fsync(stream.fileno())
        manifest = {"schema": "ams-backup/2", "database_digest": byte_digest(database.read_bytes()), "schema_version": DB_VERSION, "created_at": now(), "blobs": [{"digest": digest, "byte_length": size} for digest, size in blobs], "job_files": job_files}
        with (partial / "manifest.json").open("x") as stream:
            stream.write(encoded(manifest))
            stream.flush()
            os.fsync(stream.fileno())
        sync_directories(partial)
        partial.rename(destination)
        fsync_directory(destination.parent)
        return manifest


def restore(source, destination, project, validator, *, graph_validator=validate_graph):
    """Restore only into a new directory; never overwrite an active database."""
    source, destination, project = Path(source).resolve(), Path(destination).resolve(), Path(project).resolve()
    if destination.exists():
        raise RepositoryError("output-exists", "恢复目标已经存在；恢复必须写入新目录。")
    if destination == project or project in destination.parents:
        raise RepositoryError("private-root-in-project", "恢复目录必须在 Git 项目之外。")
    manifest = json.loads((source / "manifest.json").read_text())
    version = manifest.get("schema_version")
    if manifest.get("schema") not in ("ams-backup/1", "ams-backup/2") or type(version) is not int or not 1 <= version <= DB_VERSION:
        raise RepositoryError("backup-version", "不支持的备份格式。")
    data = backup_file(source, "research.sqlite3")
    if byte_digest(data) != manifest["database_digest"]:
        raise RepositoryError("backup-corrupt", "备份数据库内容与 manifest 不一致。")
    partial = destination.with_name(destination.name + ".partial-" + uuid.uuid4().hex)
    partial.mkdir(parents=True, mode=0o700)
    write_durable(partial / "research.sqlite3", data)
    db = sqlite3.connect(partial / "research.sqlite3")
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RepositoryError("backup-corrupt", "备份数据库完整性检查失败。")
        if db.execute("PRAGMA user_version").fetchone()[0] != version:
            raise RepositoryError("backup-corrupt", "备份数据库版本与 manifest 不一致。")
        expected = [{"digest": row[0], "byte_length": row[1]} for row in db.execute("SELECT digest,byte_length FROM blobs ORDER BY digest")]
        if expected != manifest["blobs"]:
            raise RepositoryError("backup-corrupt", "备份文件清单不完整。")
        attempts = backup_attempts(db)
        if manifest["schema"] == "ams-backup/1" and attempts:
            raise RepositoryError("backup-incomplete", "旧格式没有保存实验原件；请从原数据目录重新生成完整备份。")
    finally:
        db.close()
    for entry in expected:
        digest = entry["digest"]
        if not DIGEST.fullmatch(digest):
            raise RepositoryError("backup-corrupt", "备份含非法文件身份。")
        relative = Path("blobs") / digest[7:9] / digest[9:]
        value = backup_file(source, relative.as_posix())
        if byte_digest(value) != digest or len(value) != entry["byte_length"]:
            raise RepositoryError("blob-corrupt", "备份依据文件损坏。", digest=digest)
        write_durable(partial / relative, value)
    files = manifest.get("job_files", [])
    if not isinstance(files, list):
        raise RepositoryError("backup-corrupt", "任务文件清单无效。")
    seen = set()
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise RepositoryError("backup-corrupt", "任务文件清单无效。")
        name = entry["path"]
        if name in seen or not any(name.startswith(directory + "/") for directory in attempts):
            raise RepositoryError("backup-corrupt", "任务文件不属于数据库中记录的 attempt。")
        seen.add(name)
        value = backup_file(source, name)
        if byte_digest(value) != entry.get("digest") or len(value) != entry.get("byte_length"):
            raise RepositoryError("backup-corrupt", "备份任务原件损坏。", path=name)
        write_durable(partial / name, value)
    check_attempt_results(partial, attempts)
    check = Repository(partial, project, validator, graph_validator=graph_validator)
    try:
        report = check.doctor()
        if not report["ok"]:
            raise RepositoryError("restore-check", "恢复检查失败。", report=report)
    finally:
        check.close()
    sync_directories(partial)
    partial.rename(destination)
    fsync_directory(destination.parent)
    return report
