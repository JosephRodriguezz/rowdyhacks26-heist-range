"""HTTP boundary tests with a fake; no lab, runtime, provider or dependencies."""

from __future__ import annotations

import contextlib
import http.client
import io
import json
import socket
import threading
import time
import types
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from core.api import CoreHTTPServer


TOKEN = "synthetic-test-token-at-least-16"
SECRET = "synthetic-private-value-must-not-escape"


class FakeConflict(ValueError):
    pass


class FakeService:
    def __init__(self) -> None:
        self.calls = []
        self.lock = threading.Lock()
        self.failure = None
        self.event_failure_after = None
        self.sessions = {"assessment-1": self.snapshot("assessment-1")}
        self.action_ids = set()
        self.event_rows = [self.event(i) for i in range(1, 4)]

    @staticmethod
    def snapshot(session_id: str) -> dict:
        return {"assessment_id": session_id, "state": "created", "target_id": "bank-local",
                "data_source": "live", "planner_mode": "fixture"}

    @staticmethod
    def event(event_id: int) -> dict:
        return {"id": event_id, "sequence": event_id, "assessment_id": "assessment-1",
                "type": "session.updated", "data_source": "live", "data": {"summary": f"Event {event_id}"}}

    def _record(self, method: str, *args, **kwargs) -> None:
        with self.lock:
            self.calls.append((method, args, kwargs))
        if self.failure is not None:
            raise self.failure

    def targets(self):
        self._record("targets")
        return {"targets": [{"target_id": "bank-local", "name": "Synthetic bank"}]}

    def create(self, *, target_id, planner_mode, action_id):
        self._record("create", target_id=target_id, planner_mode=planner_mode, action_id=action_id)
        if target_id != "bank-local" or planner_mode not in {"fixture", "model"}:
            raise ValueError(SECRET)
        session_id = f"assessment-{len(self.sessions) + 1}"
        result = self.snapshot(session_id)
        result["planner_mode"] = planner_mode
        self.sessions[session_id] = result
        return result.copy()

    def list_sessions(self):
        self._record("list_sessions")
        return [row.copy() for row in self.sessions.values()]

    def status(self, session_id):
        self._record("status", session_id)
        return self.sessions[session_id].copy()

    def action(self, session_id, action_type, *, action_id):
        self._record("action", session_id, action_type, action_id=action_id)
        snapshot = self.sessions[session_id]
        if action_id in self.action_ids:
            raise FakeConflict(SECRET)
        self.action_ids.add(action_id)
        if action_type == "reset":
            return self.create(target_id="bank-local", planner_mode="fixture", action_id=action_id)
        snapshot["state"] = {"start": "running", "pause": "paused", "resume": "running", "stop": "cancelled"}[action_type]
        return snapshot.copy()

    def events(self, session_id, *, after):
        self._record("events", session_id, after=after)
        if session_id not in self.sessions:
            raise KeyError(SECRET)
        if self.event_failure_after is not None and after >= self.event_failure_after:
            raise RuntimeError(SECRET)
        with self.lock:
            rows = [row.copy() for row in self.event_rows if row["sequence"] > after]
            last = max((row["sequence"] for row in self.event_rows), default=0)
        return {"events": rows, "last_event_id": last}

    def evidence(self, session_id, evidence_id):
        self._record("evidence", session_id, evidence_id)
        if session_id not in self.sessions or evidence_id != "safe-evidence":
            raise KeyError(SECRET)
        return {"evidence_id": evidence_id, "summary": "Authorized comparison", "data_source": "live"}


class APIHarness(unittest.TestCase):
    stream_seconds = 0.15

    def setUp(self) -> None:
        self.service = FakeService()
        self.api = CoreHTTPServer(self.service, token=TOKEN, stream_seconds=self.stream_seconds)
        self.api.__enter__()
        self.addCleanup(self.api.close)
        parsed = urlsplit(self.api.origin)
        self.host, self.port = parsed.hostname, parsed.port

    def open_request(self, path, *, method="GET", body=None, headers=None, authorized=True):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=2)
        request_headers = {"Authorization": "Bearer " + TOKEN} if authorized else {}
        request_headers.update(headers or {})
        if isinstance(body, dict):
            body = json.dumps(body).encode()
            request_headers.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=body, headers=request_headers)
        transport = conn.sock
        response = conn.getresponse()
        self.addCleanup(response.close)
        self.addCleanup(conn.close)
        return conn, response, transport

    def request(self, path, **kwargs):
        conn, response, _ = self.open_request(path, **kwargs)
        raw = response.read()
        headers = dict(response.getheaders())
        conn.close()
        return response.status, json.loads(raw), headers

    def assert_error(self, status, result, expected):
        self.assertEqual(status, expected)
        self.assertEqual(set(result), {"error"})
        self.assertEqual(set(result["error"]), {"code", "message"})
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn(TOKEN, json.dumps(result))

    def raw_request(self, head: str, body: bytes = b""):
        with socket.create_connection((self.host, self.port), timeout=2) as conn:
            conn.sendall(head.encode("ascii") + body)
            conn.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                chunk = conn.recv(65_536)
                if not chunk:
                    break
                chunks.append(chunk)
        raw = b"".join(chunks)
        response_head, response_body = raw.split(b"\r\n\r\n", 1)
        return int(response_head.split(b" ", 2)[1]), json.loads(response_body)

    def head(self, *, method="GET", path="/api/targets", extra=""):
        return (f"{method} {path} HTTP/1.1\r\nHost: {self.host}:{self.port}\r\n"
                f"Authorization: Bearer {TOKEN}\r\n{extra}\r\n")

    @staticmethod
    def sse_frames(raw: bytes):
        frames = []
        for block in raw.decode().split("\n\n"):
            fields = dict(line.split(": ", 1) for line in block.splitlines() if line and not line.startswith(":"))
            if fields:
                frames.append(fields)
        return frames


class CoreAPITests(APIHarness):
    def test_public_health_only_exposes_static_status(self):
        status, result, headers = self.request("/health", authorized=False)
        self.assertEqual((status, result), (200, {"status": "ok"}))
        self.assertEqual(self.service.calls, [])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertFalse(any(name.lower().startswith("access-control-") for name in headers))

    def test_targets_list_and_status_are_service_projections(self):
        self.assertEqual(self.request("/api/targets")[:2],
                         (200, {"targets": [{"target_id": "bank-local", "name": "Synthetic bank"}]}))
        self.assertEqual(self.request("/api/assessments")[:2],
                         (200, {"assessments": [self.service.snapshot("assessment-1")]}))
        self.assertEqual(self.request("/api/assessments/assessment-1")[:2],
                         (200, self.service.snapshot("assessment-1")))
        self.assertEqual([call[0] for call in self.service.calls], ["targets", "list_sessions", "status"])

    def test_create_uses_fixture_default_and_passes_explicit_planner_mode(self):
        for index, planner_mode in enumerate((None, "model")):
            body = {"action_id": f"create-{index}", "target_id": "bank-local"}
            if planner_mode is not None:
                body["planner_mode"] = planner_mode
            status, result, _ = self.request("/api/assessments", method="POST", body=body)
            self.assertEqual(status, 201)
            self.assertEqual(result["planner_mode"], planner_mode or "fixture")
            self.assertEqual(result["data_source"], "live")
            self.assertEqual(self.service.calls[-1], ("create", (), {
                "target_id": "bank-local", "planner_mode": planner_mode or "fixture", "action_id": f"create-{index}"}))

    def test_controls_return_accepted_and_reset_fresh_snapshot(self):
        for index, action_type in enumerate(("start", "pause", "resume", "stop", "reset")):
            status, result, _ = self.request("/api/assessments/assessment-1/actions", method="POST",
                                            body={"action_id": f"control-{index}", "type": action_type})
            self.assertEqual(status, 202)
            self.assertEqual(result["assessment_id"], "assessment-2" if action_type == "reset" else "assessment-1")
            self.assertIn(("action", ("assessment-1", action_type), {"action_id": f"control-{index}"}), self.service.calls)
        self.assertEqual(self.service.sessions["assessment-1"]["state"], "cancelled")

    def test_duplicate_control_maps_explicit_exported_conflict(self):
        module = types.ModuleType("core.service")
        module.Conflict = FakeConflict
        with patch.dict("sys.modules", {"core.service": module}):
            body = {"action_id": "duplicate-control", "type": "start"}
            self.assertEqual(self.request("/api/assessments/assessment-1/actions", method="POST", body=body)[0], 202)
            status, result, _ = self.request("/api/assessments/assessment-1/actions", method="POST", body=body)
            self.assert_error(status, result, 409)
            self.assertEqual(result["error"]["code"], "conflict")

    def test_evidence_is_scoped_and_private_evidence_is_not_found(self):
        path = "/api/assessments/assessment-1/evidence/"
        status, result, _ = self.request(path + "safe-evidence")
        self.assertEqual(status, 200)
        self.assertEqual(result["evidence_id"], "safe-evidence")
        for suffix in ("private-evidence", "missing-evidence"):
            status, result, _ = self.request(path + suffix)
            self.assert_error(status, result, 404)
        status, result, _ = self.request("/api/assessments/unknown/evidence/safe-evidence")
        self.assert_error(status, result, 404)

    def test_events_use_numeric_cursor_and_preserve_projected_envelope(self):
        for query, cursor in (("", 0), ("?after=1", 1), ("?after=100", 100)):
            status, result, _ = self.request("/api/assessments/assessment-1/events" + query)
            self.assertEqual(status, 200)
            self.assertEqual(result, {"events": [row for row in self.service.event_rows if row["id"] > cursor],
                                      "last_event_id": 3})
            self.assertEqual(self.service.calls[-1], ("events", ("assessment-1",), {"after": cursor}))

    def test_every_api_route_and_unsupported_method_requires_bearer(self):
        paths = ("/api/targets", "/api/assessments", "/api/assessments/assessment-1",
                 "/api/assessments/assessment-1/events", "/api/assessments/assessment-1/stream",
                 "/api/assessments/assessment-1/evidence/safe-evidence", "/api/unknown", "/api")
        for path in paths:
            with self.subTest(path=path):
                status, result, headers = self.request(path, authorized=False)
                self.assert_error(status, result, 401)
                self.assertEqual(headers["WWW-Authenticate"], "Bearer")
        for path in ("/api/assessments", "/api/assessments/assessment-1/actions"):
            status, result, _ = self.request(path, method="POST", body={}, authorized=False)
            self.assert_error(status, result, 401)
        for method in ("OPTIONS", "BREW"):
            status, result, _ = self.request("/api/targets", method=method, authorized=False)
            self.assert_error(status, result, 401)
        self.assertEqual(self.service.calls, [])

    def test_incorrect_and_non_bearer_tokens_are_rejected(self):
        for value in ("Bearer wrong-synthetic-token", "Basic " + TOKEN, "bearer " + TOKEN,
                      "Bearer " + TOKEN + " extra", "Bearer", ""):
            with self.subTest(value=value.split(" ")[0]):
                status, result, _ = self.request("/api/targets", headers={"Authorization": value})
                self.assert_error(status, result, 401)
        self.assertEqual(self.service.calls, [])

    def test_exact_host_blocks_rebinding_including_public_health(self):
        for host in ("evil.invalid", f"localhost:{self.port}", self.host,
                     f"{self.host}:{self.port + 1}", f"{self.host}:{self.port},evil.invalid"):
            for path in ("/health", "/api/targets"):
                with self.subTest(host=host, path=path):
                    status, result, _ = self.request(path, headers={"Host": host})
                    self.assert_error(status, result, 400)
        self.assertEqual(self.service.calls, [])

    def test_origin_must_match_exactly_with_no_cors(self):
        self.assertEqual(self.request("/api/targets", headers={"Origin": self.api.origin})[0], 200)
        self.service.calls.clear()
        for origin in ("null", "*", "https://evil.invalid", self.api.origin + "/", self.api.origin.replace("http:", "https:")):
            with self.subTest(origin=origin):
                status, result, headers = self.request("/api/targets", headers={"Origin": origin})
                self.assert_error(status, result, 403)
                self.assertFalse(any(name.lower().startswith("access-control-") for name in headers))
        self.assertEqual(self.service.calls, [])

    def test_duplicate_security_and_framing_headers_are_rejected(self):
        for extra in (f"Host: {self.host}:{self.port}\r\n", f"Authorization: Bearer {TOKEN}\r\n",
                      f"Origin: {self.api.origin}\r\nOrigin: {self.api.origin}\r\n",
                      "Content-Length: 0\r\nContent-Length: 0\r\n"):
            with self.subTest(header=extra.split(":")[0]):
                self.assert_error(*self.raw_request(self.head(extra=extra)), 400)
        self.assert_error(*self.raw_request(f"GET /health HTTP/1.1\r\nConnection: close\r\n\r\n"), 400)
        self.assertEqual(self.service.calls, [])

    def test_audience_visibility_tokens_and_unknown_query_fields_are_rejected(self):
        paths = ("/health", "/api/targets", "/api/assessments", "/api/assessments/assessment-1",
                 "/api/assessments/assessment-1/actions", "/api/assessments/assessment-1/events",
                 "/api/assessments/assessment-1/stream", "/api/assessments/assessment-1/evidence/safe-evidence")
        for path in paths:
            for query in ("audience=referee", "visibility=red_private", "token=" + TOKEN, "unknown=1"):
                with self.subTest(path=path, field=query.split("=")[0]):
                    status, result, _ = self.request(path + "?" + query)
                    self.assert_error(status, result, 400)
        status, result, _ = self.request("/api/assessments/assessment-1/stream?token=" + TOKEN, authorized=False)
        self.assert_error(status, result, 401)
        self.assertEqual(self.service.calls, [])

    def test_invalid_and_duplicate_event_cursors_are_rejected(self):
        for endpoint in ("events", "stream"):
            for query in ("after=-1", "after=1.0", "after=abc", "after=", "after=%2B1",
                          "after=1&after=2", "after", "after=" + "9" * 21):
                with self.subTest(endpoint=endpoint, query=query):
                    status, result, _ = self.request(f"/api/assessments/assessment-1/{endpoint}?{query}")
                    self.assert_error(status, result, 400)
        for query in ("?after=0", "?bad", "?a=1&" + "&".join(f"k{i}=v" for i in range(9))):
            status, result, _ = self.request("/api/targets" + query)
            self.assert_error(status, result, 400)
        self.assertEqual(self.service.calls, [])

    def test_unknown_and_ambiguous_paths_are_rejected(self):
        for path, expected in (("/api/assessments/assessment-1/private", 404), ("/api/targets/", 404),
                               ("/api/assessments/assessment-1/events/", 404),
                               ("/api/assessments/../targets", 404), ("/api/assessments/%2e%2e", 404),
                               ("/api/assessments/a%2Fb", 404), ("/api/targets#fragment", 400),
                               ("//evil.invalid/api/targets", 400),
                               (self.api.origin + "/api/targets?audience=referee", 400)):
            with self.subTest(path=path):
                status, result, _ = self.request(path)
                self.assert_error(status, result, expected)
        self.assertEqual(self.service.calls, [])

    def test_wrong_methods_are_rejected_without_invoking_service(self):
        for path, method in (("/health", "POST"), ("/api/targets", "POST"),
                             ("/api/assessments/assessment-1", "POST"),
                             ("/api/assessments/assessment-1/actions", "GET"),
                             ("/api/assessments/assessment-1/events", "POST"),
                             ("/api/targets", "PUT"), ("/api/targets", "OPTIONS"), ("/api/targets", "BREW")):
            with self.subTest(path=path, method=method):
                status, result, _ = self.request(path, method=method)
                self.assert_error(status, result, 405)
        self.assertEqual(self.service.calls, [])

    def test_json_fields_are_strict_for_create_and_controls(self):
        create = {"action_id": "create-valid", "target_id": "bank-local"}
        action = {"action_id": "action-valid", "type": "start"}
        for path, valid in (("/api/assessments", create), ("/api/assessments/assessment-1/actions", action)):
            bodies = [dict(valid, audience="referee"), dict(valid, visibility="referee_only"),
                      dict(valid, token=TOKEN), dict(valid, unknown="value"),
                      {key: value for key, value in valid.items() if key != "action_id"}]
            for value in (None, True, 1, [], {}, "", "  ", "line\nbreak", "x" * 129):
                bodies.append(dict(valid, action_id=value))
            for body in bodies:
                with self.subTest(path=path, fields=list(body)):
                    status, result, _ = self.request(path, method="POST", body=body)
                    self.assert_error(status, result, 400)
        for action_type in ("patch", "tool", "START", ""):
            status, result, _ = self.request("/api/assessments/assessment-1/actions", method="POST",
                                            body=dict(action, type=action_type))
            self.assert_error(status, result, 400)
        self.assertEqual(self.service.calls, [])

    def test_registered_target_and_planner_validation_remain_in_service(self):
        for target, mode in (("https://evil.invalid", "fixture"), ("bank-local", "unknown")):
            status, result, _ = self.request("/api/assessments", method="POST",
                                            body={"action_id": "bad-target", "target_id": target, "planner_mode": mode})
            self.assert_error(status, result, 400)
        self.assertEqual(len(self.service.calls), 2)

    def test_malformed_nonobject_duplicate_and_nonfinite_json_are_rejected(self):
        bodies = (b"{", b"null", b"[]", b'"text"', b"", b"\xff", b'{} trailing',
                  b'{"action_id":"one","action_id":"two","target_id":"bank-local"}',
                  b'{"action_id":NaN,"target_id":"bank-local"}',
                  b'{"action_id":Infinity,"target_id":"bank-local"}', b"[" * 1100 + b"]" * 1100)
        for body in bodies:
            with self.subTest(body_prefix=body[:30]):
                status, result, _ = self.request("/api/assessments", method="POST", body=body,
                                                headers={"Content-Type": "application/json"})
                self.assert_error(status, result, 400)
        self.assertEqual(self.service.calls, [])

    def test_mutations_require_json_content_type(self):
        body = b'{"action_id":"create","target_id":"bank-local"}'
        for content_type in (None, "text/plain", "application/x-www-form-urlencoded"):
            headers = {} if content_type is None else {"Content-Type": content_type}
            status, result, _ = self.request("/api/assessments", method="POST", body=body, headers=headers)
            self.assert_error(status, result, 415)
        self.assertEqual(self.service.calls, [])

    def test_content_length_is_required_bounded_and_unambiguous(self):
        for length, expected in ((None, 411), ("-1", 400), ("abc", 400), ("+2", 400),
                                 ("0", 400), ("16385", 413), ("9" * 30, 400)):
            extra = "Content-Type: application/json\r\n"
            if length is not None:
                extra += f"Content-Length: {length}\r\n"
            with self.subTest(length=length):
                self.assert_error(*self.raw_request(self.head(method="POST", path="/api/assessments", extra=extra)), expected)
        self.assert_error(*self.raw_request(self.head(extra="Content-Length: 1\r\n"), b"x"), 400)
        self.assertEqual(self.service.calls, [])

    def test_content_length_limit_inclusive_and_truncated_body_invalid(self):
        body = b'{"action_id":"create","target_id":"bank-local"}'
        padded = body + b" " * (16_384 - len(body))
        self.assertEqual(self.request("/api/assessments", method="POST", body=padded,
                                      headers={"Content-Type": "application/json"})[0], 201)
        before = len(self.service.calls)
        extra = f"Content-Type: application/json\r\nContent-Length: {len(body) + 1}\r\n"
        self.assert_error(*self.raw_request(self.head(method="POST", path="/api/assessments", extra=extra), body), 400)
        self.assertEqual(len(self.service.calls), before)

    def test_chunking_content_encoding_and_expectations_are_rejected(self):
        for extra, expected in (("Transfer-Encoding: chunked\r\n", 400),
                                ("Transfer-Encoding: chunked\r\nContent-Length: 0\r\n", 400),
                                ("Content-Encoding: gzip\r\nContent-Length: 0\r\n", 400),
                                ("Expect: 100-continue\r\nContent-Length: 10\r\n", 417)):
            with self.subTest(header=extra.split(":")[0]):
                self.assert_error(*self.raw_request(self.head(method="POST", path="/api/assessments", extra=extra)), expected)
        unauthenticated = self.head(method="POST", path="/api/assessments",
                                    extra="Expect: 100-continue\r\nContent-Length: 10\r\n")
        unauthenticated = unauthenticated.replace(f"Authorization: Bearer {TOKEN}\r\n", "")
        self.assert_error(*self.raw_request(unauthenticated), 401)
        self.assertEqual(self.service.calls, [])

    def test_service_errors_and_serialization_do_not_leak_exception_text(self):
        for exc, expected in ((KeyError(SECRET), 404), (ValueError(SECRET), 400),
                              (RuntimeError(SECRET), 500), (TimeoutError(SECRET), 500)):
            self.service.failure = exc
            with self.subTest(error_type=type(exc).__name__):
                status, result, _ = self.request("/api/targets")
                self.assert_error(status, result, expected)
        self.service.failure = None
        with patch.object(self.service, "targets", return_value={"bad": object()}):
            status, result, _ = self.request("/api/targets")
            self.assert_error(status, result, 500)
        same_name = type("Conflict", (Exception,), {})
        self.service.failure = same_name(SECRET)
        status, result, _ = self.request("/api/targets")
        self.assert_error(status, result, 500)

    def test_malformed_http_returns_static_json_and_requests_never_log_tokens(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            self.assert_error(*self.raw_request("GET /api/targets SECRET HTTP/1.1\r\n\r\n"), 400)
            self.request("/api/targets?token=" + TOKEN)
            self.request("/api/targets", headers={"Authorization": "Bearer " + SECRET})
            self.service.failure = RuntimeError(SECRET)
            self.request("/api/targets")
        self.assertEqual(output.getvalue(), "")


class CoreSSETests(APIHarness):
    def test_stream_frames_are_ordered_json_and_include_heartbeat(self):
        # Filtering can leave gaps; events need not arrive already sorted.
        self.service.event_rows = [self.service.event(5), self.service.event(1), self.service.event(3)]
        _, response, _ = self.open_request("/api/assessments/assessment-1/stream?after=1")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "text/event-stream")
        raw = response.read()
        frames = self.sse_frames(raw)
        self.assertEqual([int(frame["id"]) for frame in frames], [3, 5])
        for frame in frames:
            self.assertEqual(frame["event"], "session.updated")
            self.assertEqual(json.loads(frame["data"]), self.service.event(int(frame["id"])))
        self.assertIn(b": heartbeat\n\n", raw)
        self.assertNotIn(TOKEN.encode(), raw)

    def test_reconnect_header_precedes_after_and_replays_strictly_after_cursor(self):
        _, first, _ = self.open_request("/api/assessments/assessment-1/stream?after=0",
                                       headers={"Last-Event-ID": "2"})
        self.assertEqual([frame["id"] for frame in self.sse_frames(first.read())], ["3"])
        self.assertEqual(self.service.calls[0], ("events", ("assessment-1",), {"after": 2}))
        with self.service.lock:
            self.service.event_rows.extend((self.service.event(4), self.service.event(6)))
        _, second, _ = self.open_request("/api/assessments/assessment-1/stream", headers={"Last-Event-ID": "3"})
        self.assertEqual([frame["id"] for frame in self.sse_frames(second.read())], ["4", "6"])
        _, third, _ = self.open_request("/api/assessments/assessment-1/stream?after=4")
        self.assertEqual([frame["id"] for frame in self.sse_frames(third.read())], ["6"])

    def test_invalid_last_event_id_and_duplicate_header_are_rejected(self):
        for value in ("-1", "abc", "1.5", "", "9" * 21):
            status, result, _ = self.request("/api/assessments/assessment-1/stream", headers={"Last-Event-ID": value})
            self.assert_error(status, result, 400)
        extra = "Last-Event-ID: 1\r\nLast-Event-ID: 2\r\n"
        self.assert_error(*self.raw_request(self.head(path="/api/assessments/assessment-1/stream", extra=extra)), 400)
        self.assertEqual(self.service.calls, [])

    def test_missing_stream_session_is_json_not_successful_sse(self):
        status, result, headers = self.request("/api/assessments/missing/stream")
        self.assert_error(status, result, 404)
        self.assertEqual(headers["Content-Type"], "application/json")
        # Initial failure released its stream slot.
        _, response, _ = self.open_request("/api/assessments/assessment-1/stream")
        self.assertEqual(response.status, 200)
        response.read()

    def test_stream_duration_is_bounded_even_with_no_new_events(self):
        before = time.monotonic()
        _, response, _ = self.open_request("/api/assessments/assessment-1/stream?after=3")
        raw = response.read()
        elapsed = time.monotonic() - before
        self.assertLess(elapsed, 1)
        self.assertGreaterEqual(elapsed, self.stream_seconds * 0.8)
        self.assertEqual(self.sse_frames(raw), [])
        self.assertIn(b": heartbeat", raw)

    def test_stream_error_after_headers_is_safe_and_closes(self):
        self.service.event_failure_after = 3
        _, response, _ = self.open_request("/api/assessments/assessment-1/stream")
        raw = response.read()
        frames = self.sse_frames(raw)
        self.assertEqual([frame["id"] for frame in frames[:-1]], ["1", "2", "3"])
        self.assertEqual(frames[-1]["event"], "error")
        self.assert_error(500, json.loads(frames[-1]["data"]), 500)
        self.assertNotIn(SECRET.encode(), raw)

    def test_sse_names_cannot_inject_lines(self):
        self.service.event_rows[0]["type"] = "message\ndata: " + SECRET
        status, result, _ = self.request("/api/assessments/assessment-1/stream")
        self.assert_error(status, result, 500)


class CoreStreamLifecycleTests(APIHarness):
    stream_seconds = 5

    def test_maximum_four_streams_and_disconnect_releases_capacity(self):
        streams = [self.open_request("/api/assessments/assessment-1/stream?after=3") for _ in range(4)]
        for _, response, _ in streams:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.fp.readline(), b": heartbeat\n")
        status, result, _ = self.request("/api/assessments/assessment-1/stream")
        self.assert_error(status, result, 503)
        conn, response, transport = streams[0]
        transport.shutdown(socket.SHUT_RDWR)
        response.close()
        conn.close()
        deadline = time.monotonic() + 1.5
        statuses = []
        while time.monotonic() < deadline:
            _, replacement, _ = self.open_request("/api/assessments/assessment-1/stream?after=3")
            statuses.append(replacement.status)
            if replacement.status == 200:
                break
            replacement.read()
            time.sleep(0.05)
        self.assertEqual(statuses[-1], 200)

    def test_shutdown_interrupts_streams_without_waiting_for_lifetime(self):
        streams = [self.open_request("/api/assessments/assessment-1/stream?after=3") for _ in range(4)]
        before = time.monotonic()
        self.api.close()
        for _, response, _ in streams:
            response.read()
        self.assertLess(time.monotonic() - before, 1)
        self.assertFalse(self.api._thread.is_alive())
        with self.assertRaises(OSError), socket.create_connection((self.host, self.port), timeout=0.2):
            pass


class CoreServerConfigurationTests(unittest.TestCase):
    def test_context_starts_and_stops_and_does_not_close_service(self):
        service = FakeService()
        server = CoreHTTPServer(service, token=TOKEN)
        self.addCleanup(server.close)
        self.assertFalse(server._thread.is_alive())
        self.assertTrue(server.origin.startswith("http://127.0.0.1:"))
        with server as active:
            self.assertIs(active, server)
            self.assertTrue(server._thread.is_alive())
        self.assertFalse(server._thread.is_alive())
        server.close()
        with self.assertRaises(RuntimeError):
            server.start()
        self.assertEqual(service.calls, [])

    def test_nonloopback_or_dns_hosts_and_invalid_configuration_are_rejected(self):
        for host in ("0.0.0.0", "192.0.2.1", "example.invalid", "localhost", "::", None):
            with self.subTest(host=host), self.assertRaises(ValueError):
                CoreHTTPServer(FakeService(), token=TOKEN, host=host)
        for token in ("", "contains space", "line\nbreak", "nonascii-\u2603", None):
            with self.subTest(token_type=type(token).__name__), self.assertRaises(ValueError):
                CoreHTTPServer(FakeService(), token=token)
        for duration in (0, -1, float("inf"), float("nan"), True, "20"):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                CoreHTTPServer(FakeService(), token=TOKEN, stream_seconds=duration)
        for port in (-1, 65_536, True):
            with self.subTest(port=port), self.assertRaises(ValueError):
                CoreHTTPServer(FakeService(), token=TOKEN, port=port)

    @unittest.skipUnless(socket.has_ipv6, "IPv6 unavailable")
    def test_ipv6_loopback_has_bracketed_origin_and_exact_host(self):
        try:
            server = CoreHTTPServer(FakeService(), token=TOKEN, host="::1", stream_seconds=0.1)
        except OSError:
            self.skipTest("IPv6 loopback binding unavailable")
        with server:
            parsed = urlsplit(server.origin)
            self.assertEqual(parsed.hostname, "::1")
            self.assertTrue(server.origin.startswith("http://[::1]:"))
            conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)
            try:
                conn.request("GET", "/api/targets", headers={"Authorization": "Bearer " + TOKEN})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
