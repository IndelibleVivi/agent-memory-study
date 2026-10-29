"""Loopback-only HTTP boundary for the explicitly launched local application.

No general directory serving, CORS, cookies, request-content logging or public
localhost discovery. The application owns typed operations, this module owns
same-origin admission and bounded HTTP input.
"""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
from urllib.parse import unquote, urlsplit

from .repository import RepositoryError, encoded

MAX_REQUEST = 32 * 1024 * 1024


class LocalHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = True

    def __init__(self, app, site_root, port=0):
        self.app = app
        self.site_root = Path(site_root).resolve()
        if not (self.site_root / "index.html").is_file():
            raise RepositoryError("site-missing", "先构建公开 reader，再启动本地环境。")
        receipt = self.site_root / "build-receipt.json"
        self.site_base = json.loads(receipt.read_text()).get("base", "/") if receipt.is_file() else "/"
        if not self.site_base.startswith("/") or not self.site_base.endswith("/") or ".." in self.site_base:
            raise RepositoryError("site-base", "公开构建的 base 无效。")
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), LocalHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.entry_url = self.origin + self.site_base


class LocalHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AMSLocal/1"
    sys_version = ""

    def log_message(self, *args):
        # URL/query/body may contain private research. CLI reports startup only.
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def send(self, status, data, media_type="application/json; charset=utf-8"):
        if not isinstance(data, bytes):
            data = encoded(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'; object-src 'none'; base-uri 'self'")
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                # A write may already be committed. Retry uses the same ID.
                pass

    def admission(self, api=False):
        expected = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != expected:
            self.send(403, {"code": "host-rejected", "message": "只接受启动地址的 Host。"})
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.origin:
            self.send(403, {"code": "origin-rejected", "message": "请求不来自本地 AMS 页面。"})
            return False
        if self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
            self.send(403, {"code": "origin-rejected", "message": "跨站请求被拒绝。"})
            return False
        if api:
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied, "Bearer " + self.server.token):
                self.send(401, {"code": "session-expired", "message": "本地服务会话已改变；先导出当前输入，再重新打开页面。"})
                return False
        return True

    def do_GET(self):
        self.dispatch()

    def do_HEAD(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def do_OPTIONS(self):
        self.send(405, {"code": "cors-disabled"})

    def read_json(self):
        if self.headers.get("Transfer-Encoding") is not None:
            raise RepositoryError("invalid-body", "不接受未知长度或分块请求。")
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_REQUEST:
            raise RepositoryError("request-size", "单次请求限 32 MiB。")
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            raise RepositoryError("content-type", "写入须使用 JSON 请求。")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise RepositoryError("incomplete-body", "请求未完整收到，没有接受写入。")
        def object_hook(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate JSON key")
                value[key] = item
            return value
        try:
            return json.loads(raw.decode("utf-8"), object_pairs_hook=object_hook,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        except (UnicodeDecodeError, ValueError, RecursionError) as error:
            raise RepositoryError("invalid-json", "输入不是合法、无重复键的 UTF-8 JSON。") from error

    def dispatch(self):
        parts = urlsplit(self.path)
        api = parts.path.startswith("/api/")
        if not self.admission(api):
            self.close_connection = self.command == "POST"
            return
        try:
            if api:
                body = self.read_json() if self.command == "POST" else None
                result = self.server.app.handle('GET' if self.command == 'HEAD' else self.command, parts.path, parts.query, body)
                self.send(200, result)
            elif self.command in ("GET", "HEAD"):
                self.static(parts.path)
            else:
                self.send(405, {"code": "method-not-allowed"})
        except RepositoryError as error:
            status = 409 if error.code in ("revision-conflict", "idempotency-conflict", "revision-reuse") else 404 if error.code == "not-found" else 400
            self.send(status, error.as_dict())
        except (ValueError, TypeError, KeyError) as error:
            self.send(400, {"code": "invalid-operation", "message": str(error)[:1000]})
        except Exception:
            # Never echo paths, stack frames, records or environment into errors.
            self.send(500, {"code": "local-error", "message": "本地操作未完成。输入仍可导出；请运行 ams doctor。"})

    def static(self, path):
        decoded = unquote(path)
        if "\x00" in decoded or "\\" in decoded or any(part in (".", "..") for part in decoded.split("/")):
            raise RepositoryError("not-found", "资源不存在。")
        root = self.server.site_root
        if decoded == "/" and self.server.site_base != "/":
            self.send_response(302); self.send_header("Location", self.server.site_base); self.send_header("Content-Length", "0"); self.end_headers(); return
        if self.server.site_base != "/":
            if not decoded.startswith(self.server.site_base):
                raise RepositoryError("not-found", "资源不存在。")
            decoded = decoded[len(self.server.site_base):]
        candidate = root / decoded.lstrip("/")
        if candidate.is_dir():
            candidate = candidate / "index.html"
        resolved = candidate.resolve()
        if root not in resolved.parents or not resolved.is_file():
            raise RepositoryError("not-found", "资源不存在。")
        value = resolved.read_bytes()
        media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        if media_type == "text/html":
            bootstrap = encoded({"mode": "local", "api": "/api", "token": self.server.token})
            script = '<script id="ams-local-bootstrap" type="application/json">' + bootstrap + '</script>'
            value = value.replace(b"</head>", script.encode() + b"</head>", 1)
            media_type += "; charset=utf-8"
        self.send(200, value, media_type)
