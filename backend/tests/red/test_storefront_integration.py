"""Small live-local integration check for red against the resettable lab."""

import asyncio
from contextlib import contextmanager
from http.client import HTTPConnection
import json
from threading import Thread
import unittest

from backend.app.agents.red.runner import execute
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


class LocalLabTools:
    def __init__(self, server, grants):
        self.server = server
        self.grants = grants

    async def http_request(self, request):
        if request["target_id"] != "storefront-lab" or request["target_version"] != "lab-v1":
            raise AssertionError("adapter received an unregistered target")
        grant = self.grants.get(request.get("credential_ref"))
        headers = {"X-Request-ID": request["request_id"]}
        if grant:
            headers["Authorization"] = f"Bearer {grant.token}"
        connection = HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=2)
        try:
            connection.request("GET", request["path"], headers=headers)
            response = connection.getresponse()
            body = json.loads(response.read())
            return {"request_id": request["request_id"], "status": response.status,
                    "body": body, "evidence_id": f"evidence-{request['request_id']}"}
        finally:
            connection.close()


class StorefrontRedIntegrationTests(unittest.TestCase):
    def test_red_discovers_and_returns_candidate_from_local_lab(self):
        state = LabState()
        with running_lab(state) as server:
            alice = state.trusted_new_session("alice")
            bob = state.trusted_new_session("bob")
            tools = LocalLabTools(server, {alice.session_ref: alice, bob.session_ref: bob})
            context = {
                "assessment_id": "integration-1", "target_id": "storefront-lab",
                "target_version": "lab-v1", "entry_path": "/",
                "account_refs": {"alice": alice.session_ref, "bob": bob.session_ref},
                "budgets": {"max_steps": 16, "max_requests": 16, "timeout_seconds": 5},
            }
            result = asyncio.run(execute(context, tools))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["status"], "candidate")
        self.assertEqual(result["candidates"][0]["endpoint"], "/api/orders/{id}")


if __name__ == "__main__":
    unittest.main()
