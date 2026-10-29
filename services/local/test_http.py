import http.client
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest

from services.local.http import LocalHTTPServer
from services.local.repository import Repository
from services.local.test_repository import command, storage_command_validator


class ApplicationFixture:
    def __init__(self, repo):
        self.repo = repo

    def handle(self, method, path, query, body):
        if method == "POST" and path == "/api/commands":
            return self.repo.apply(body)
        if method == "GET" and path == "/api/records":
            return self.repo.list()
        raise ValueError("unsupported fixture operation")


class HTTPBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.site = self.base / "project/dist/site"
        self.site.mkdir(parents=True)
        (self.site / "index.html").write_text("<!doctype html><html><head></head><body>public reader</body></html>")
        self.repo = Repository(self.base / "data", self.base / "project", storage_command_validator, graph_validator=None)
        self.server = LocalHTTPServer(ApplicationFixture(self.repo), self.site)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.repo.close()
        self.temp.cleanup()

    def request(self, method="GET", path="/api/records", body=None, **headers):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        defaults = {"Authorization": "Bearer " + self.server.token, "Content-Type": "application/json"}
        defaults.update(headers)
        connection.request(method, path, json.dumps(body) if body is not None else None, headers=defaults)
        response = connection.getresponse()
        value = response.read()
        status = response.status
        connection.close()
        return status, value

    def test_private_api_needs_token_and_same_origin_host(self):
        self.repo.apply(command(text="PRIVATE_CANARY_123"))
        for headers, status in [({"Authorization": ""}, 401), ({"Origin": "https://untrusted.example"}, 403),
                                ({"Origin": "null"}, 403), ({"Host": "attacker.example"}, 403),
                                ({"Sec-Fetch-Site": "cross-site"}, 403)]:
            result, body = self.request(**headers)
            self.assertEqual(result, status)
            self.assertNotIn(b"PRIVATE_CANARY_123", body)
        status, body = self.request(Origin=self.server.origin)
        self.assertEqual(status, 200)
        self.assertIn(b"PRIVATE_CANARY_123", body)

    def test_real_command_commit_and_revision_conflict_over_http(self):
        a = command()
        status, receipt = self.request("POST", "/api/commands", a, Origin=self.server.origin)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(receipt)["state_revision"], a["record"]["revision"])
        b = command(expected="rev:stale", text="retain draft")
        status, body = self.request("POST", "/api/commands", b, Origin=self.server.origin)
        self.assertEqual(status, 409)
        self.assertEqual(json.loads(body)["rejected_command"], b)
        self.assertEqual(len(self.repo.events()), 1)

    def test_connection_lost_before_ack_retries_same_committed_command(self):
        c = command()
        value = json.dumps(c).encode()
        s = socket.create_connection(("127.0.0.1", self.server.server_port))
        headers = (f"POST /api/commands HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\n"
                   f"Authorization: Bearer {self.server.token}\r\nContent-Type: application/json\r\n"
                   f"Content-Length: {len(value)}\r\nConnection: close\r\n\r\n").encode()
        s.sendall(headers + value)
        s.close()
        status, receipt = self.request("POST", "/api/commands", c)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(receipt), self.repo.apply(c))
        self.assertEqual(len(self.repo.events()), 1)

    def test_static_bootstrap_does_not_expose_private_state(self):
        self.repo.apply(command(text="PRIVATE_CANARY_123"))
        status, body = self.request(path="/")
        self.assertEqual(status, 200)
        self.assertIn(b"ams-local-bootstrap", body)
        self.assertIn(self.server.token.encode(), body)
        self.assertNotIn(b"PRIVATE_CANARY_123", body)
        self.assertNotIn(b"ams-local-bootstrap", (self.site / "index.html").read_bytes())
        (self.site / "escape").symlink_to(self.base / "data/research.sqlite3")
        for path in ("/escape", "/../data/research.sqlite3", "/%2e%2e/data/research.sqlite3", "/%2e%2e%5cdata"):
            status, _ = self.request(path=path)
            self.assertEqual(status, 404)

    def test_invalid_json_is_rejected_before_any_write(self):
        for value in (b'{"a": 1,"a":2}', b'{"a": NaN}', b'\xff'):
            connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
            connection.request("POST", "/api/commands", value, headers={"Authorization": "Bearer " + self.server.token, "Content-Type": "application/json"})
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
            connection.close()
        self.assertEqual(self.repo.list(), [])


if __name__ == "__main__":
    unittest.main()
