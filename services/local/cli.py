"""Explicit local research service. No account access or provider calls at startup."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from schemas.validate import validate_command
from .application import Application
from .http import LocalHTTPServer
from .records import command, revise, identity
from .repository import RepositoryError, encoded, restore
from . import portable


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", type=Path, default=Path.cwd())
    common.add_argument("--data-root", type=Path, default=Path.home() / ".local/share/agent-memory-study")
    configuration, remaining = common.parse_known_args(argv)
    parser = argparse.ArgumentParser(prog="ams", description=__doc__, parents=[common])
    subs = parser.add_subparsers(dest="action", required=True)
    serve = subs.add_parser("serve")
    serve.add_argument("--port", type=int, default=8317)
    serve.add_argument("--site-root", type=Path)
    subs.add_parser("doctor")
    subs.add_parser("index-rebuild")
    new = subs.add_parser("new")
    new.add_argument("title", nargs="?", default="")
    subs.add_parser("list")
    load = subs.add_parser("open")
    load.add_argument("id")
    capture = subs.add_parser("capture", help="先保存遭遇；文件必须明确选择")
    capture.add_argument("text", nargs="?", default="")
    capture.add_argument("--why", default="")
    capture.add_argument("--file", type=Path)
    capture.add_argument("--idempotency-key")
    request = subs.add_parser("request", help="从 JSON 调用与界面相同的本地研究操作")
    request.add_argument("path", help="例如 /identity/resolve；没有 Git 发布执行入口")
    request.add_argument("--json", type=Path, required=True)
    request.add_argument("--get", action="store_true")
    stop = subs.add_parser("stop")
    stop.add_argument("session")
    stop.add_argument("--next", required=True)
    stop.add_argument("--expected-revision", required=True)
    exp = subs.add_parser("export")
    exp.add_argument("id")
    exp.add_argument("--out", type=Path, required=True)
    imp = subs.add_parser("import")
    imp.add_argument("file", type=Path)
    imp.add_argument("--confirm-digest")
    backup = subs.add_parser("backup")
    backup.add_argument("destination", type=Path)
    res = subs.add_parser("restore")
    res.add_argument("source", type=Path)
    res.add_argument("destination", type=Path)
    args = parser.parse_args(remaining)
    args.project, args.data_root = configuration.project, configuration.data_root
    app = None
    try:
        if args.action == "restore":
            result = restore(args.source, args.destination, args.project, validate_command)
        else:
            app = Application(args.project, args.data_root, enable_jobs=args.action in ("serve", "request"))
            if args.action == "serve":
                server = LocalHTTPServer(app, args.site_root or args.project / "dist/site", args.port)
                print(f"AMS local: {server.entry_url}\n数据只写入指定的本地目录。按 Ctrl+C 停止。", flush=True)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    server.server_close()
                return 0
            if args.action == "doctor":
                result = app.repo.doctor()
            elif args.action == "capture":
                key = args.idempotency_key or identity('capture-command')
                if args.file:
                    import mimetypes
                    result = app.workspace.capture.capture_bytes(args.text or args.file.name,args.file.read_bytes(),media_type=mimetypes.guess_type(args.file.name)[0] or 'application/octet-stream',idempotency_key=key,why_now=args.why)
                else:
                    result = app.workspace.capture.capture(args.text,why_now=args.why,idempotency_key=key)
            elif args.action == "request":
                from urllib.parse import urlencode
                value = json.loads(args.json.read_text(encoding='utf-8'))
                if not args.path.startswith('/') or args.path.startswith('/api/') or '?' in args.path:
                    raise ValueError('使用 /identity/resolve 这样的本地操作路径。')
                result = app.handle('GET' if args.get else 'POST','/api'+args.path,urlencode(value) if args.get else '',None if args.get else value)
                if not args.get and args.path in ('/jobs','/job/retry'):
                    result=app.jobs.wait(result['id'])
            elif args.action == "index-rebuild":
                result = app.rebuild_index()
            elif args.action == "new":
                result = app.new_thread(args.title)
            elif args.action == "list":
                result = [{"id": item["id"], "title": item["title"], "state_revision": item["state_revision"]} for item in app.repo.list("thread")]
            elif args.action == "open":
                result = app.load_thread(args.id)
            elif args.action == "stop":
                previous = app.repo.load("session", args.session)
                value = revise(previous, payload={**previous["payload"], "next": args.next})
                c = command(value, previous=previous)
                c["expected_revision"] = args.expected_revision
                result = app.repo.apply(c)
            elif args.action == "export":
                loaded = app.load_thread(args.id)
                roots = [{key: item[key] for key in ("kind", "id", "revision")} for item in [loaded["thread"], *loaded["sessions"]]]
                result = portable.export(app.repo, roots)
                with args.out.open("x", encoding="utf-8") as stream:
                    stream.write(encoded(result))
                result = {"exported": str(args.out), "records": len(result["records"])}
            elif args.action == "import":
                raw = args.file.read_bytes()
                result = app.import_preview(raw)
                if args.confirm_digest:
                    result = app.import_confirm(args.confirm_digest)
            elif args.action == "backup":
                result = app.repo.backup(args.destination)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        print('任务已中断；本次证据保留，可在本地实验空间明确重试。',file=sys.stderr)
        return 130
    except (RepositoryError, ValueError, OSError) as error:
        print(json.dumps(error.as_dict() if isinstance(error, RepositoryError) else {"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if app:
            app.close()


if __name__ == "__main__":
    raise SystemExit(main())
