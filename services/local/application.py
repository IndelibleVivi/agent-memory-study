"""One local API shared by the CLI and the browser adapter."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import subprocess
from urllib.parse import parse_qs

from schemas.validate import validate_command
from . import portable
from .records import command, record, ref
from .repository import Repository, RepositoryError, byte_digest, now


class Application:
    def __init__(self, project, data_root, *, enable_jobs=False):
        self.project = Path(project).resolve()
        self.manifest = self.load_manifest()
        self.repo = Repository(data_root, project, validate_command)
        self.cache_public_records(self.manifest)
        from .workspace_api import WorkspaceAPI
        self.workspace = WorkspaceAPI(self.repo, self.project, self.current_public_records)
        from .authoring import ReviewAuthoringService
        self.authoring = ReviewAuthoringService(self.repo, self.project, self.current_public_records)
        self.previews = {}
        self.jobs = None
        if enable_jobs:
            from .jobs import JobManager
            try:
                self.jobs = JobManager(self.repo, self.project)
            except BaseException:
                self.repo.close()
                raise

    def close(self):
        if self.jobs:
            self.jobs.close()
        self.repo.close()

    def load_manifest(self):
        path = self.project / "data/public-corpus.manifest.json"
        if not path.is_file():
            raise RepositoryError("public-index-missing", "先运行内容 compiler，生成公开索引。")
        return json.loads(path.read_text(encoding="utf-8"))

    def cache_public_records(self, manifest):
        records = []
        for relative in manifest.get("record_shards", []):
            path = (self.project / relative).resolve()
            if not path.is_relative_to(self.project / "data/corpus/revisions"):
                raise RepositoryError("public-index-path", "公开索引含越界 snapshot 路径。")
            records.append(json.loads(path.read_text(encoding="utf-8")))
        self.repo.cache_public_records(records)
        from schemas.validate import exact_ref, walk_exact_refs
        index = {exact_ref(ref(value)): value for value in records}
        chosen = set()
        def select(pointer):
            key = exact_ref(pointer)
            if key in chosen: return
            chosen.add(key)
            for dependency in walk_exact_refs(index[key]): select(dependency)
        for value in manifest["objects"]: select(ref(value))
        self.current_public_records = [index[key] for key in sorted(chosen)]

    def public_lookup(self, kind, id):
        aliases = {"source": "material", "entry": "study", "inquiry": "question", "transfer": "finding"}
        kind = aliases.get(kind, kind)
        matches = [item for item in self.manifest["objects"] if item["public_kind"] == kind and (item.get("public_id", item["id"].split(":", 1)[-1]) == id or item["id"] == id)]
        return {key: matches[0][key] for key in ("kind", "id", "revision")} if len(matches) == 1 else None

    def rebuild_index(self):
        manifest = self.load_manifest()
        raw = (self.project / "data/public-corpus.manifest.json").read_bytes()
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.project, check=True, text=True, capture_output=True).stdout.strip()
        binding = {"git_commit": commit, "manifest_digest": byte_digest(raw)}
        self.cache_public_records(manifest)
        self.repo.cache_public(manifest, binding)
        self.manifest = manifest
        from .workspace_api import WorkspaceAPI
        self.workspace = WorkspaceAPI(self.repo, self.project, self.current_public_records)
        from .authoring import ReviewAuthoringService
        self.authoring = ReviewAuthoringService(self.repo, self.project, self.current_public_records)
        return {"binding": binding, "objects": len(manifest["objects"]), "private_records_changed": False}

    def new_thread(self, title=""):
        thread = record("thread", {"title": title, "byline": "Local researcher", "status": "open", "payload": {"attention": "active", "created_at": now()}})
        session = record("session", {"thread_ref": ref(thread), "visibility": "private", "started_at": now(),
                                     "payload": {"items": [], "question": "", "synthesis": "", "next": "", "attention": "active", "return_when": "", "compare": []}})
        self.repo.apply_unit([command(thread), command(session)])
        return {"thread": thread, "session": session}

    def load_thread(self, id):
        thread = self.repo.load("thread", id)
        sessions = [session for session in self.repo.list("session") if session["thread_ref"]["id"] == id]
        return {"thread": thread, "sessions": sessions}

    def import_preview(self, raw):
        report = portable.preview(raw, self.public_lookup)
        # One preview per browser upload; bounded memory, no auto-import.
        self.previews = {report["digest"]: raw}
        return report

    def import_confirm(self, digest):
        raw = self.previews.get(digest)
        if raw is None:
            old = self.repo.import_mapping(digest)
            if old is not None:
                return {"mapping": old, "already_imported": True}
            raise RepositoryError("preview-expired", "服务重启或预览已替换；请重新选择原文件。")
        return portable.confirm(self.repo, raw, digest, self.public_lookup)

    def handle(self, method, path, query, body):
        if path == "/api/authoring/catalogue" and method == "GET":
            return self.authoring.catalogue()
        if path.startswith("/api/authoring/") and method == "POST":
            actions = {"open": self.authoring.open, "create": self.authoring.create, "propose": self.authoring.propose, "publication": self.authoring.publication_plan, "patch": self.authoring.patch}
            action = actions.get(path.rsplit("/", 1)[-1])
            if action is not None: return action(**body)
        if path.startswith(('/api/capture', '/api/identity/', '/api/acquisition', '/api/argument/', '/api/revision/', '/api/publication/')):
            return self.workspace.handle(method, path, query, body)
        query = parse_qs(query)
        field = lambda name, default=None: query.get(name, [default])[0]
        if method == "GET":
            if path == "/api/capabilities":
                return {"mode": "local", "durable": True, "commands": True, "portable": True, "jobs": self.jobs is not None, "schema": "ams-core/2"}
            if path == "/api/studies" and self.jobs:
                return {"studies": self.jobs.registry()}
            if path == "/api/jobs" and self.jobs:
                return {"jobs": self.jobs.list()}
            if path == "/api/job" and self.jobs:
                return self.jobs.get(field("id"))
            if path == "/api/job/evidence" and self.jobs:
                return self.jobs.evidence(field("id"))
            if path == "/api/entities":
                return {"records": self.repo.list(field("kind"))}
            if path == "/api/entity":
                return self.repo.load(field("kind"), field("id"), field("revision"))
            if path == "/api/history":
                return {"records": self.repo.history(field("kind"), field("id"))}
            if path == "/api/thread":
                return self.load_thread(field("id"))
            if path == "/api/events":
                return {"events": self.repo.events(int(field("after", "0")), float(field("wait", "0")))}
            if path == "/api/doctor":
                return self.repo.doctor()
            if path == "/api/public":
                return self.manifest
            if path == "/api/blob":
                return {"digest": field("digest"), "base64": base64.b64encode(self.repo.read_blob(field("digest"))).decode("ascii")}
        if method == "POST":
            if path == "/api/job/history-snapshot" and self.jobs:
                from .experiment_views import ExperimentViewService
                return ExperimentViewService(self.repo, self.project, self.jobs).history_snapshot(body["id"])
            if path == "/api/job/snapshot" and self.jobs:
                from .experiment_views import ExperimentViewService
                return ExperimentViewService(self.repo, self.project, self.jobs).snapshot(body["id"])
            if path == "/api/jobs" and self.jobs:
                return self.jobs.submit(body["plan"], idempotency_key=body["idempotency_key"])
            if path == "/api/job/cancel" and self.jobs:
                return self.jobs.cancel(body["id"])
            if path == "/api/job/retry" and self.jobs:
                return self.jobs.retry(body["id"], idempotency_key=body["idempotency_key"])
            if path == "/api/commands":
                return {"receipt": self.repo.apply(body)}
            if path == "/api/units":
                return {"receipts": self.repo.apply_unit(body["commands"])}
            if path == "/api/blobs":
                raw = base64.b64decode(body["base64"], validate=True)
                return {"digest": self.repo.put_blob(raw), "byte_length": len(raw)}
            if path == "/api/import/preview":
                return self.import_preview(base64.b64decode(body["base64"], validate=True))
            if path == "/api/import/confirm":
                return self.import_confirm(body["digest"])
            if path == "/api/export":
                return portable.export(self.repo, body["roots"])
            if path == "/api/index/rebuild":
                return self.rebuild_index()
        raise RepositoryError("not-found", "没有这个本地操作。")
