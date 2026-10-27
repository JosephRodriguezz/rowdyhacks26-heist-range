"""HTTP and trusted-adapter regression checks for the first lab scenario."""

from __future__ import annotations

from contextlib import contextmanager
from http.client import HTTPConnection
import json
from threading import Thread
import unittest

from backend.app.agents.blue.detection import PRIVATE_ORDERS_POLICY, detect_suspicious_access
from cyber_range.storefront import LabState, create_server


@contextmanager
def running_lab(state: LabState):
    server = create_server(state=state)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


def request(port: int, method: str, path: str, token: str | None = None,
            body: dict | None = None, request_id: str = "req-test") -> tuple[int, dict]:
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    headers = {"X-Request-ID": request_id}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = None
    if body is not None:
        payload = json.dumps(body)
        headers["Content-Type"] = "application/json"
    try:
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


class StorefrontTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = LabState()
        self.server_context = running_lab(self.state)
        self.port = self.server_context.__enter__()
        self.alice = self.state.trusted_new_session("alice")
        self.bob = self.state.trusted_new_session("bob")

    def tearDown(self) -> None:
        self.server_context.__exit__(None, None, None)

    def test_public_entry_and_health_do_not_reveal_private_records(self) -> None:
        status, entry = request(self.port, "GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(entry["links"][0]["href"], "/api/orders")
        self.assertNotIn("204", json.dumps(entry))
        self.assertEqual(request(self.port, "GET", "/health"), (200, {"status": "ok"}))

    def test_patched_copy_can_report_a_distinct_trusted_version(self) -> None:
        copy = LabState(target_version="lab-v1-patch-001")
        self.assertEqual(copy.trusted_reset()["target_version"], "lab-v1-patch-001")
        with self.assertRaises(ValueError):
            LabState(target_version="not a valid version")

    def test_own_listing_and_seeded_flaw_with_protected_control(self) -> None:
        status, listing = request(self.port, "GET", "/api/orders", self.alice.token)
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in listing["orders"]], [101])
        self.assertEqual(listing["orders"][0]["href"], "/api/orders/101")
        self.assertNotIn("canary", json.dumps(listing))
        self.assertEqual(request(self.port, "GET", "/api/orders/101", self.alice.token)[0], 200)
        status, exposed = request(self.port, "GET", "/api/orders/204", self.alice.token, request_id="req-cross-user")
        self.assertEqual(status, 200)
        self.assertEqual(exposed["order"]["owner_ref"], "bob")
        self.assertEqual(exposed["order"]["canary"], "ORDER-204-PRIVATE")
        self.assertEqual(request(self.port, "GET", "/api/secure-orders/204", self.alice.token)[0], 403)
        self.assertEqual(request(self.port, "GET", "/api/orders/204", self.bob.token)[0], 200)
        self.assertEqual(request(self.port, "GET", "/api/secure-orders/204", self.bob.token)[0], 200)

    def test_anonymous_and_invalid_sessions_are_denied(self) -> None:
        for path in ("/api/orders", "/api/orders/101", "/api/secure-orders/101"):
            with self.subTest(path=path):
                self.assertEqual(request(self.port, "GET", path)[0], 401)
                self.assertEqual(request(self.port, "GET", path, "invalid-token")[0], 401)

    def test_http_login_uses_runtime_secret_and_telemetry_is_sanitized(self) -> None:
        credential = self.state.trusted_seed_credential("alice")
        status, login = request(self.port, "POST", "/api/session", body={
            "username": credential.username, "password": credential.password,
        }, request_id="req-login")
        self.assertEqual(status, 201)
        self.assertEqual(request(self.port, "GET", "/api/orders", login["token"])[0], 200)
        telemetry = self.state.trusted_telemetry()
        self.assertEqual(telemetry[0]["request_id"], "req-login")
        self.assertEqual(telemetry[0]["action"], "create_session")
        self.assertEqual(telemetry[0]["actor_ref"], "alice")
        for event in telemetry:
            encoded = json.dumps(event)
            self.assertNotIn(credential.password, encoded)
            self.assertNotIn(login["token"], encoded)
        self.assertNotIn(credential.password, repr(credential))
        self.assertNotIn(login["token"], repr(self.state.trusted_new_session("alice")))

    def test_revocation_is_containment_and_fresh_session_still_exposes_flaw(self) -> None:
        self.assertTrue(self.state.trusted_revoke_session(self.alice.session_ref))
        self.assertFalse(self.state.trusted_revoke_session(self.alice.session_ref))
        self.assertEqual(request(self.port, "GET", "/api/orders/204", self.alice.token)[0], 401)
        fresh = self.state.trusted_new_session("alice")
        self.assertNotEqual(fresh.session_ref, self.alice.session_ref)
        self.assertEqual(request(self.port, "GET", "/api/orders/204", fresh.token)[0], 200)
        self.assertEqual(request(self.port, "GET", "/api/secure-orders/204", fresh.token)[0], 403)

    def test_reset_restores_seed_records_and_revokes_old_sessions(self) -> None:
        self.assertEqual(request(self.port, "GET", "/api/orders/204", self.alice.token)[0], 200)
        self.assertEqual(self.state.trusted_reset(), {"target_id": "storefront-lab", "target_version": "lab-v1"})
        self.assertEqual(self.state.trusted_telemetry(), [])
        self.assertEqual(request(self.port, "GET", "/api/orders/204", self.alice.token)[0], 401)
        fresh = self.state.trusted_new_session("alice")
        self.assertNotEqual(fresh.session_ref, self.alice.session_ref)
        self.assertEqual(request(self.port, "GET", "/api/orders/204", fresh.token)[1]["order"]["canary"],
                         "ORDER-204-PRIVATE")

    def test_telemetry_has_owner_and_request_correlation_without_secrets(self) -> None:
        request(self.port, "GET", "/api/orders/204", self.alice.token, request_id="req-owned-cross")
        event = self.state.trusted_telemetry()[-1]
        self.assertEqual(event["request_id"], "req-owned-cross")
        self.assertEqual(event["actor_ref"], "alice")
        self.assertEqual(event["resource_owner_ref"], "bob")
        self.assertEqual(event["session_ref"], self.alice.session_ref)
        self.assertEqual(event["resource_id"], "204")
        self.assertEqual(event["action"], "read_private_order")
        self.assertTrue(event["timestamp"].endswith("Z"))
        self.assertEqual(event["http_status"], 200)
        self.assertNotIn(self.alice.token, json.dumps(event))

    def test_existing_blue_policy_recognizes_only_cross_user_exposure(self) -> None:
        request(self.port, "GET", "/api/orders/101", self.alice.token, request_id="req-owner")
        request(self.port, "GET", "/api/secure-orders/204", self.alice.token, request_id="req-control")
        request(self.port, "GET", "/api/orders/204", self.alice.token, request_id="req-exposure")
        result = detect_suspicious_access(self.state.trusted_telemetry(), PRIVATE_ORDERS_POLICY)
        self.assertEqual(len(result.alerts), 1)
        self.assertEqual(result.alerts[0].kind, "cross_user_read")
        self.assertEqual(result.alerts[0].request_ids, ("req-exposure",))
        self.assertEqual(result.skipped, ())


if __name__ == "__main__":
    unittest.main()
