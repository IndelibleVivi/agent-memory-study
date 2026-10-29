"""Storage guarantees; domain/schema fixtures are tested by research-core."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

from services.local.repository import Repository, RepositoryError, byte_digest, restore


def storage_command_validator(command):
    # A deliberately narrow fixture: this suite exercises storage, not schema.
    required = {"command_id", "idempotency_key", "operation", "target", "record"}
    if not isinstance(command, dict) or not required <= command.keys():
        raise ValueError("invalid storage fixture command")


def command(id="thread:one", *, expected=None, text="未命名", revision=None):
    key = "command:" + uuid.uuid4().hex
    value = {"command_id": key, "idempotency_key": key, "operation": "update" if expected else "create",
             "target": {"kind": "thread", "id": id},
             "record": {"kind": "thread", "id": id, "revision": revision or "rev:" + uuid.uuid4().hex, "title": text}}
    if expected:
        value["expected_revision"] = expected
    return value


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.repo = Repository(self.base / "data", self.project, storage_command_validator, graph_validator=None)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_commit_retry_and_reopen_keep_same_receipt(self):
        c = command(text="长期问题 🌱")
        receipt = self.repo.apply(c)
        self.assertEqual(receipt, self.repo.apply(copy.deepcopy(c)))
        self.assertEqual(len(self.repo.events()), 1)
        another = Repository(self.base / "data", self.project, storage_command_validator, graph_validator=None)
        try:
            self.assertEqual(another.load("thread", "thread:one")["title"], "长期问题 🌱")
            self.assertEqual(another.apply(c), receipt)
        finally:
            another.close()

    def test_same_id_or_key_with_changed_payload_is_rejected(self):
        c = command()
        self.repo.apply(c)
        changed = copy.deepcopy(c)
        changed["record"]["title"] = "不能覆盖"
        for use_new_command_id in (False, True):
            if use_new_command_id:
                changed["command_id"] = "command:different"
            with self.assertRaisesRegex(RepositoryError, "幂等"):
                self.repo.apply(changed)
        self.assertEqual(len(self.repo.events()), 1)

    def test_two_writers_conflict_retains_current_and_rejected(self):
        first = command()
        self.repo.apply(first)
        expected = first["record"]["revision"]
        commands = [command(expected=expected, text=name) for name in ("A", "B")]
        results = []
        barrier = threading.Barrier(2)
        def apply(c):
            db = Repository(self.base / "data", self.project, storage_command_validator, graph_validator=None)
            try:
                barrier.wait()
                try:
                    results.append(db.apply(c))
                except RepositoryError as error:
                    results.append(error.as_dict())
            finally:
                db.close()
        threads = [threading.Thread(target=apply, args=(c,)) for c in commands]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
            self.assertFalse(thread.is_alive())
        failures = [r for r in results if r.get("code") == "revision-conflict"]
        self.assertEqual(len(failures), 1)
        failure = failures[0]
        self.assertEqual(failure["current"]["revision"], self.repo.load("thread", "thread:one")["revision"])
        self.assertNotEqual(failure["current"]["title"], failure["rejected_command"]["record"]["title"])

    def test_atomic_unit_rolls_back_earlier_accepted_item(self):
        a = command()
        b = command(id="thread:two", expected="rev:missing")
        with self.assertRaises(RepositoryError):
            self.repo.apply_unit([a, b])
        self.assertEqual(self.repo.list(), [])
        self.assertEqual(self.repo.events(), [])
        self.repo.apply(a)

    def test_old_revision_is_readable_and_cannot_be_reused(self):
        a = command(text="旧依据")
        self.repo.apply(a)
        b = command(expected=a["record"]["revision"], text="新依据")
        self.repo.apply(b)
        self.assertEqual(self.repo.load("thread", "thread:one", a["record"]["revision"])["title"], "旧依据")
        c = command(expected=b["record"]["revision"], revision=a["record"]["revision"])
        with self.assertRaisesRegex(RepositoryError, "不可变"):
            self.repo.apply(c)

    def artifact(self, data=b"original bytes"):
        digest = self.repo.put_blob(data)
        c = command(id="artifact:one")
        c["target"]["kind"] = "artifact"
        c["record"].update(kind="artifact", artifact_digest=digest, byte_length=len(data))
        return c

    def test_blob_write_before_failed_transaction_does_not_create_artifact(self):
        c = self.artifact()
        with self.assertRaises(RepositoryError):
            self.repo.apply_unit([c, command(expected="rev:absent")])
        self.assertEqual(self.repo.list(), [])
        self.assertEqual(self.repo.read_blob(c["record"]["artifact_digest"]), b"original bytes")

    def test_backup_restore_binds_database_and_all_referenced_bytes(self):
        self.repo.apply(self.artifact())
        self.repo.apply(command(text="private canary"))
        self.repo.backup(self.base / "backup")
        self.repo.apply(command(id="thread:later"))
        report = restore(self.base / "backup", self.base / "restored", self.project, storage_command_validator, graph_validator=None)
        self.assertTrue(report["ok"])
        db = Repository(self.base / "restored", self.project, storage_command_validator, graph_validator=None)
        try:
            self.assertEqual(len(db.list()), 2)
            self.assertEqual(db.load("thread", "thread:one")["title"], "private canary")
        finally:
            db.close()
        with self.assertRaises(RepositoryError):
            restore(self.base / "backup", self.base / "restored", self.project, storage_command_validator, graph_validator=None)
        manifest = json.loads((self.base / "backup/manifest.json").read_text())
        digest = manifest["blobs"][0]["digest"]
        blob = self.base / "backup/blobs" / digest[7:9] / digest[9:]
        blob.write_bytes(b"tampered")
        with self.assertRaisesRegex(RepositoryError, "损坏"):
            restore(self.base / "backup", self.base / "bad-restore", self.project, storage_command_validator, graph_validator=None)
        self.assertFalse((self.base / "bad-restore").exists())

    def test_missing_blob_is_reported_without_erasing_old_record(self):
        c = self.artifact()
        self.repo.apply(c)
        self.repo.blob_path(c["record"]["artifact_digest"]).unlink()
        self.assertFalse(self.repo.doctor()["ok"])
        self.assertEqual(self.repo.load("artifact", "artifact:one"), c["record"])

    def test_process_kill_before_commit_leaves_no_receipt_or_snapshot(self):
        code = '''
import json,sys,time
from services.local.repository import Repository
from services.local.test_repository import storage_command_validator
r=Repository(sys.argv[1],sys.argv[2],storage_command_validator, graph_validator=None)
with r.transaction():
 r._apply(json.loads(sys.argv[3]))
 print('uncommitted',flush=True)
 time.sleep(60)
'''
        c = command()
        process = subprocess.Popen([sys.executable, "-c", code, str(self.base / "data"), str(self.project), json.dumps(c)], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), "uncommitted")
            process.kill()
            process.wait(5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
        self.assertEqual(self.repo.list(), [])
        self.assertEqual(self.repo.events(), [])
        self.repo.apply(c)
        self.assertEqual(len(self.repo.events()), 1)

    def test_root_and_future_schema_boundaries(self):
        with self.assertRaises(RepositoryError):
            Repository(self.project / "private", self.project, storage_command_validator, graph_validator=None)
        with self.assertRaises(RepositoryError):
            self.repo.backup(self.project / "private-backup")
        self.repo.db.execute("PRAGMA user_version=99")
        with self.assertRaises(RepositoryError):
            Repository(self.base / "data", self.project, storage_command_validator, graph_validator=None)

    def test_upgrade_failure_rolls_back_and_retry_preserves_records(self):
        from services.local.intake import INTAKE_MIGRATION_SQL
        from services.local.identity import IDENTITY_MIGRATION_SQL
        from services.local.acquisition import ACQUISITION_MIGRATION_SQL
        from services.local.connectors import CONNECTORS_MIGRATION_SQL
        c = command(text="升级前固定输入")
        receipt = self.repo.apply(c)
        # Reconstruct the immediately preceding schema by removing only v4 tables.
        with self.repo.transaction():
            for statement in (*INTAKE_MIGRATION_SQL, *IDENTITY_MIGRATION_SQL, *ACQUISITION_MIGRATION_SQL, *CONNECTORS_MIGRATION_SQL):
                table = statement.split()[2]
                self.repo.db.execute('DROP TABLE ' + table)
            self.repo.db.execute("PRAGMA user_version=3")
        self.repo.close()
        with patch('services.local.intake.INTAKE_MIGRATION_SQL', (*INTAKE_MIGRATION_SQL, 'INVALID migration')):
            with self.assertRaises(sqlite3.OperationalError):
                Repository(self.base / "data", self.project, storage_command_validator, graph_validator=None)
        with sqlite3.connect(self.base / "data/research.sqlite3") as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE name='intake_links'").fetchone()[0], 0)
            backup = self.base / "version3-backup"
            backup.mkdir()
            copied = sqlite3.connect(backup / "research.sqlite3")
            try:
                db.backup(copied)
            finally:
                copied.close()
        (backup / "manifest.json").write_text(json.dumps({"schema":"ams-backup/1", "schema_version":3, "database_digest":byte_digest((backup / "research.sqlite3").read_bytes()), "blobs":[]}))
        report = restore(backup, self.base / "upgraded-restore", self.project, storage_command_validator, graph_validator=None)
        self.assertTrue(report['ok'])
        self.assertEqual(report['schema_version'], 4)
        self.repo = Repository(self.base / "data", self.project, storage_command_validator, graph_validator=None)
        self.assertEqual(self.repo.load("thread", "thread:one"), c['record'])
        self.assertEqual(self.repo.apply(c), receipt)
        self.assertEqual(self.repo.db.execute("PRAGMA user_version").fetchone()[0], 4)


if __name__ == "__main__":
    unittest.main()
