"""The HTTP/CLI boundaries against the real local shared-session service."""

import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlsplit

from core.api import CoreHTTPServer
from core.service import CoreService
from core.store import Store


class TransportTests(unittest.TestCase):
    def test_real_http_control_events_evidence_reconnect_and_reset(self):
        token = "synthetic-presenter-token-for-test-only"
        with CoreService() as service, CoreHTTPServer(service, token=token, stream_seconds=.12) as api:
            url = urlsplit(api.origin)
            def request(method, path, payload=None, extra=None):
                connection = http.client.HTTPConnection(url.hostname, url.port, timeout=3)
                headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
                headers.update(extra or {})
                connection.request(method, path, body=json.dumps(payload) if payload else None, headers=headers)
                response = connection.getresponse()
                status, content = response.status, response.read()
                connection.close()
                return status, content
            code, raw = request("POST", "/api/assessments", {"action_id": "create", "target_id": "bank-local"})
            self.assertEqual(code, 201)
            session_id = json.loads(raw)["id"]
            base = "/api/assessments/" + session_id
            self.assertEqual(request("POST", base + "/actions", {"action_id": "start", "type": "start"})[0], 202)
            final = service.wait(session_id, 5)
            self.assertEqual(final["status"], "completed")
            self.assertEqual(final["verdict"]["result"], "achieved")
            code, raw = request("GET", base + "/events")
            self.assertEqual(code, 200)
            page = json.loads(raw)
            ids = [e["id"] for e in page["events"]]
            self.assertEqual(ids, sorted(set(ids)))
            self.assertTrue(all(e["visibility"] == "judge_safe" for e in page["events"]))
            action = next(e for e in page["events"] if e["type"] == "action.observed")
            public_ref = action["evidence_refs"][0]
            self.assertEqual(request("GET", base + "/evidence/" + public_ref)[0], 200)
            private_ref = service.store.board(session_id, "red")["evidence"][0]["evidence_id"]
            self.assertEqual(request("GET", base + "/evidence/" + private_ref)[0], 404)
            after = ids[-3]
            code, stream = request("GET", base + "/stream?after=0", extra={"Last-Event-ID": str(after)})
            self.assertEqual(code, 200)
            stream_ids = [int(line[4:]) for line in stream.decode().splitlines() if line.startswith("id: ")]
            self.assertEqual(stream_ids, [i for i in ids if i > after])
            self.assertNotIn(token.encode(), stream)
            self.assertEqual(request("GET", base + "/events?audience=referee_only")[0], 400)
            code, reset = request("POST", base + "/actions", {"action_id": "reset", "type": "reset"})
            self.assertEqual(code, 202)
            fresh = json.loads(reset)
            self.assertNotEqual(fresh["id"], session_id)
            self.assertEqual(fresh["status"], "created")
            self.assertEqual(json.loads(request("GET", base + "/events")[1]), page)

    def test_cli_repeatable_fixture_and_missing_token(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-m", "core.cli", "run"], cwd=root, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["agent_decisions"], "scripted_fixture")
        self.assertFalse(report["model_performance_measured"])
        self.assertEqual(report["session"]["verdict"]["result"], "achieved")
        env = dict(os.environ)
        env.pop("HEIST_CORE_TOKEN", None)
        result = subprocess.run([sys.executable, "-m", "core.cli", "serve", "--db", ":memory:"],
                                cwd=root, env=env, text=True, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 2)
        self.assertIn("HEIST_CORE_TOKEN", result.stderr)
        result = subprocess.run([sys.executable, "-m", "core.cli", "run", "--mode", "model"],
                                cwd=root, text=True, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --allow-remote-model", result.stderr)

    def test_single_persistent_runtime_owner_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "core.sqlite3"
            with CoreService(path) as first:
                created = first.create(action_id="create")
                with self.assertRaises(ValueError):
                    CoreService(path)
                self.assertEqual(first.status(created["id"])["status"], "created")
            with CoreService(path) as second:
                self.assertEqual(second.status(created["id"])["status"], "created")
                self.assertEqual(second.create(action_id="create")["id"], created["id"])

    def test_controller_transaction_rolls_back_nested_writes(self):
        with CoreService() as service:
            created = service.create(action_id="create")
            snapshot = service.store.snapshot(created["id"])
            with self.assertRaises(ValueError):
                with service.store.transaction():
                    service.store.apply(created["id"], updates={"phase": "should-rollback"})
                    service.store.apply(created["id"], events=[{"type": "bad", "actor": "core", "data": {},
                        "visibility": "judge_safe", "evidence_refs": ["missing"]}])
            self.assertEqual(service.store.snapshot(created["id"]), snapshot)


if __name__ == "__main__":
    unittest.main()
