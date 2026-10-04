"""Presenter auth and actual disposable demo checks; no deployed bank traffic."""
import http.client
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from urllib.parse import urlsplit

from core.api import CoreHTTPServer
from core.availability import AvailabilityBridge
from core.service import CoreService

TOKEN = "synthetic-demo-test-credential-00000001"
NODE = os.environ.get("HEIST_TEST_NODE") or shutil.which("node")
DEPS = Path(__file__).resolve().parents[1] / "apps/bank-lab/node_modules/@electric-sql/pglite"


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.core = CoreService(str(Path(self.directory.name) / "demo.sqlite3"), enable_availability_fixture=True,
            availability_bridge_factory=lambda sid: AvailabilityBridge(sid, node=NODE))
        self.addCleanup(self.core.close)
        self.api = CoreHTTPServer(self.core, token=TOKEN, demo=True).start()
        self.addCleanup(self.api.close)

    def request(self, path, body=None, headers=None):
        parsed = urlsplit(self.api.origin)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=6)
        try:
            values = headers or {}
            if body is not None:
                values = {"Content-Type": "application/json", **values}
            connection.request("GET" if body is None else "POST", path,
                body=None if body is None else json.dumps(body), headers=values)
            response = connection.getresponse()
            raw = response.read()
            return response.status, dict(response.getheaders()), raw
        finally:
            connection.close()

    def login(self):
        code, headers, raw = self.request("/api/targets", headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(code, 200)
        self.assertNotIn(TOKEN.encode(), raw)
        self.assertNotIn("Set-Cookie", headers)
        return {"Authorization": "Bearer " + TOKEN, "Origin": self.api.origin}

    def test_static_shell_has_no_secrets_and_is_opt_in(self):
        for path in ("/", "/demo", "/monitor", "/demo.js", "/demo.css"):
            code, headers, raw = self.request(path)
            self.assertEqual(code, 200)
            self.assertNotIn(TOKEN.encode(), raw)
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("/../service.py")[0], 404)
        self.assertEqual(self.request("/demo?token=secret")[0], 400)
        with CoreHTTPServer(self.core, token=TOKEN) as default:
            parsed = urlsplit(default.origin)
            conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
            try:
                conn.request("GET", "/demo")
                self.assertEqual(conn.getresponse().status, 404)
            finally: conn.close()

    def test_auth_remains_bearer_only_and_cross_origin_is_rejected(self):
        self.assertEqual(self.request("/api/targets")[0], 401)
        headers = self.login()
        self.assertEqual(self.request("/api/targets", headers={"Cookie": "rowdy_presenter=" + TOKEN})[0], 401)
        self.assertEqual(self.request("/api/targets", headers={**headers, "Origin": "http://evil.invalid"})[0], 403)
        body = {"action_id": "create", "target_id": "availability-fixture"}
        self.assertEqual(self.request("/api/assessments", body, {"Cookie": "rowdy_presenter=" + TOKEN})[0], 401)
        self.assertEqual(self.request("/api/assessments", body, headers)[0], 201)
        with CoreHTTPServer(self.core, token=TOKEN) as default:
            parsed = urlsplit(default.origin); conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
            try:
                conn.request("GET", "/api/targets", headers={"Cookie": "rowdy_presenter=" + TOKEN})
                self.assertEqual(conn.getresponse().status, 401)
            finally: conn.close()

    def test_reset_unstarted_fixture_preserves_fixture_label(self):
        sid = self.core.create(target_id="availability-fixture", action_id="create")["id"]
        self.core.action(sid, "reset", action_id="reset")
        self.assertTrue(all(e["data_source"] == "fixture" for e in self.core.events(sid)["events"]))

    @unittest.skipUnless(NODE and DEPS.exists(), "Node and locked bank dependencies required")
    def test_presenter_runs_repeats_and_reads_only_safe_observations(self):
        headers = self.login()
        code, _, raw = self.request("/api/assessments", {"action_id": "create", "target_id": "availability-fixture"}, headers)
        self.assertEqual(code, 201)
        sid = json.loads(raw)["id"]
        for index in range(2):
            code, _, _ = self.request(f"/api/assessments/{sid}/actions", {"action_id": f"start-{index}", "type": "start"}, headers)
            self.assertEqual(code, 202)
            final = self.core.wait(sid, 20)
            self.assertEqual(final["verdict"]["result"], "achieved")
            code, _, raw = self.request(f"/api/assessments/{sid}/events", headers=headers)
            self.assertEqual(code, 200)
            events = json.loads(raw)["events"]
            probes = [e for e in events if e["type"] == "availability.probe.observed"]
            requests = [e for e in events if e["type"] == "availability.request.observed"]
            self.assertTrue(any(e["data"].get("status") == "degraded" for e in probes))
            self.assertTrue(any(e["data"].get("kind") == "ordinary" and e["data"]["status"] == "available" for e in probes))
            self.assertTrue(any(e["data"].get("refusal_reason") == "rate_limit" for e in requests))
            self.assertLessEqual(len(requests), 60)
            self.assertTrue(all(e["visibility"] == "judge_safe" and e["data_source"] == "fixture" for e in events))
            for forbidden in ("bank_session", "window_digest", "integrity_sha256", "balance_cents", TOKEN):
                self.assertNotIn(forbidden.encode(), raw)
            for e in probes + requests:
                self.assertEqual(e["evidence_refs"], [])
                self.assertNotIn("exercise_id", e["data"])
                self.assertNotIn("run_id", e["data"])
            self.assertEqual(self.request(f"/api/assessments/{sid}/evidence/availability-referee", headers=headers)[0], 404)
            if index == 0:
                code, _, raw = self.request(f"/api/assessments/{sid}/actions", {"action_id": "reset", "type": "reset"}, headers)
                self.assertEqual(code, 202)
                new_sid = json.loads(raw)["id"]
                self.assertNotEqual(sid, new_sid)
                self.assertEqual(self.core.status(sid)["verdict"]["result"], "achieved")
                sid = new_sid


if __name__ == "__main__":
    unittest.main()
