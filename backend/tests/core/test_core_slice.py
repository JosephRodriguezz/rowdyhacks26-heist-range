import asyncio
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
import unittest

from backend.app.core import BoundedHttpExecutor, IndependentReferee, RequestBudget, TargetRegistry, TargetScopeError, TargetSpec
from cyber_range.storefront import LabState, create_server


@contextmanager
def running_lab(state):
    server = create_server(state=state)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


class CoreTools:
    def __init__(self, state, server):
        self.state = state
        self.server = server
        self.credentials = {}
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        self.executor = BoundedHttpExecutor(
            TargetRegistry([TargetSpec("storefront-lab", "lab-v1", origin)]),
            self.credentials,
            RequestBudget(max_requests=16, timeout_seconds=2),
        )

    async def new_session(self, account_ref):
        grant = self.state.trusted_new_session(account_ref)
        self.credentials[grant.session_ref] = grant.token
        return grant.session_ref

    async def http_request(self, request):
        return await self.executor.http_request(request)


class CoreSliceTests(unittest.TestCase):
    def test_registry_rejects_unregistered_and_cross_origin_paths(self):
        registry = TargetRegistry([TargetSpec("storefront-lab", "lab-v1", "http://127.0.0.1:8123")])
        with self.assertRaises(TargetScopeError):
            registry.resolve("other-target", "lab-v1")
        for path in ("//evil.example/x", "https://evil.example/x", "/api/orders/1?redirect=https://evil.example", "/api/../secret", "/api\\secret"):
            with self.subTest(path=path):
                with self.assertRaises(TargetScopeError):
                    registry.resolve_path("storefront-lab", "lab-v1", path)

    def test_executor_returns_sanitized_result_and_enforces_budget(self):
        state = LabState()
        with running_lab(state) as server:
            grant = state.trusted_new_session("alice")
            origin = f"http://127.0.0.1:{server.server_address[1]}"
            executor = BoundedHttpExecutor(
                TargetRegistry([TargetSpec("storefront-lab", "lab-v1", origin)]),
                {grant.session_ref: grant.token}, RequestBudget(max_requests=1, timeout_seconds=2),
            )
            result = asyncio.run(executor.http_request({
                "target_id": "storefront-lab", "target_version": "lab-v1",
                "method": "GET", "path": "/api/orders/101", "credential_ref": grant.session_ref,
                "request_id": "core-1",
            }))
            self.assertEqual(result["status"], 200)
            self.assertNotIn(grant.token, json.dumps(result))
            exhausted = asyncio.run(executor.http_request({
                "target_id": "storefront-lab", "target_version": "lab-v1",
                "method": "GET", "path": "/api/orders/101", "credential_ref": grant.session_ref,
                "request_id": "core-2",
            }))
            self.assertEqual(exhausted["error"]["code"], "rejected")

    def test_executor_does_not_follow_external_redirects(self):
        external_hits = []

        class ExternalHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                external_hits.append(self.path)
                body = b'{"secret":"outside"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        external_server = ThreadingHTTPServer(("127.0.0.1", 0), ExternalHandler)
        external_worker = Thread(target=external_server.serve_forever, daemon=True)
        external_worker.start()

        class RedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b'{"status":"redirect"}'
                external_origin = f"http://127.0.0.1:{external_server.server_address[1]}"
                self.send_response(302)
                self.send_header("Location", f"{external_origin}/private")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        redirect_server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        redirect_worker = Thread(target=redirect_server.serve_forever, daemon=True)
        redirect_worker.start()
        try:
            origin = f"http://127.0.0.1:{redirect_server.server_address[1]}"
            executor = BoundedHttpExecutor(
                TargetRegistry([TargetSpec("storefront-lab", "lab-v1", origin)]),
                {}, RequestBudget(max_requests=1, timeout_seconds=2),
            )
            result = asyncio.run(executor.http_request({
                "target_id": "storefront-lab", "target_version": "lab-v1",
                "method": "GET", "path": "/redirect", "request_id": "redirect-test",
            }))
            self.assertEqual(result["status"], 302)
            self.assertEqual(external_hits, [])
        finally:
            redirect_server.shutdown()
            redirect_worker.join(timeout=2)
            redirect_server.server_close()
            external_server.shutdown()
            external_worker.join(timeout=2)
            external_server.server_close()

    def test_referee_uses_fresh_sessions_and_verifies_candidate(self):
        state = LabState()
        with running_lab(state) as server:
            tools = CoreTools(state, server)
            candidate = {
                "id": "red-candidate-1", "target_id": "storefront-lab", "target_version": "lab-v1",
                "actor_ref": "alice", "repro": {"owner_ref": "bob", "path": "/api/orders/204"},
            }
            result = asyncio.run(IndependentReferee().verify(candidate, tools))
            self.assertEqual(result["verdict"], "verified")
            self.assertTrue(result["independent"])

    def test_referee_rejects_protected_control_false_positive(self):
        state = LabState()
        with running_lab(state) as server:
            tools = CoreTools(state, server)
            candidate = {
                "id": "red-candidate-2", "target_id": "storefront-lab", "target_version": "lab-v1",
                "actor_ref": "alice", "repro": {"owner_ref": "bob", "path": "/api/secure-orders/204"},
            }
            result = asyncio.run(IndependentReferee().verify(candidate, tools))
            self.assertEqual(result["verdict"], "rejected")


if __name__ == "__main__":
    unittest.main()
