import asyncio
import unittest

from backend.app.agents.red.runner import ContextError, execute


class FakeTools:
    def __init__(self, *, secure_allowed=False):
        self.calls = []
        self.secure_allowed = secure_allowed

    async def http_request(self, request):
        self.calls.append(request)
        path = request["path"]
        credential = request["credential_ref"]
        actor = (None if credential is None else
                 ("alice-session" if credential.startswith("alice-session") else "bob-session"))
        evidence = f"evidence-{len(self.calls)}"
        if path == "/":
            body = {"links": [{"rel": "orders", "href": "/api/orders"}]}
            return {"request_id": request["request_id"], "status": 200, "body": body,
                    "evidence_id": evidence}
        if path == "/api/orders":
            order_id = 101 if actor == "alice-session" else 204
            body = {"orders": [{"id": order_id, "href": f"/api/orders/{order_id}",
                                 "secure_href": f"/api/secure-orders/{order_id}"}]}
            return {"request_id": request["request_id"], "status": 200, "body": body,
                    "evidence_id": evidence}
        if path.endswith("/204"):
            secure = path.startswith("/api/secure-")
            allowed = (actor == "bob-session") if secure else True
            body = {"order": {"id": 204, "canary": "ORDER-204-PRIVATE"}}
            return {"request_id": request["request_id"], "status": 200 if allowed else 403,
                    "body": body if allowed else {"error": {"code": "forbidden"}},
                    "evidence_id": evidence}
        if path.endswith("/101"):
            secure = path.startswith("/api/secure-")
            allowed = (actor == "alice-session") if secure else True
            body = {"order": {"id": 101, "canary": "ORDER-101-PRIVATE"}}
            return {"request_id": request["request_id"], "status": 200 if allowed else 403,
                    "body": body if allowed else {"error": {"code": "forbidden"}},
                    "evidence_id": evidence}
        return {"request_id": request["request_id"], "status": 404,
                "body": {"error": {"code": "not_found"}}, "evidence_id": evidence}


def context(**budgets):
    return {
        "assessment_id": "assessment-1", "target_id": "storefront-lab",
        "target_version": "lab-v1", "entry_path": "/",
        "account_refs": {"alice": "alice-session", "bob": "bob-session"},
        "budgets": {"max_steps": 16, "max_requests": 16, "timeout_seconds": 2, **budgets},
    }


class RedRunnerTests(unittest.TestCase):
    def test_deterministic_runner_returns_candidate_only(self):
        tools = FakeTools()
        result = asyncio.run(execute(context(), tools))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["decision_source"], "deterministic")
        self.assertEqual(len(result["candidates"]), 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["status"], "candidate")
        self.assertEqual(candidate["endpoint"], "/api/orders/{id}")
        self.assertEqual(candidate["repro"]["expected"], "denied")
        self.assertNotIn("verdict", candidate)

    def test_protected_control_is_not_reported(self):
        class SecureOnly:
            async def choose(self, options):
                secure = [item for item in options if item.endpoint.startswith("/api/secure-")]
                return secure[0] if secure else None

        result = asyncio.run(execute(context(), FakeTools(), decision_policy=SecureOnly()))
        self.assertEqual(result["candidates"], [])

    def test_budget_is_enforced_before_adapter_call(self):
        tools = FakeTools()
        result = asyncio.run(execute(context(max_requests=1), tools))
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(len(tools.calls), 1)

    def test_privileged_context_is_rejected(self):
        raw = context()
        raw["ground_truth"] = [{"id": "hidden"}]
        with self.assertRaises(ContextError):
            asyncio.run(execute(raw, FakeTools()))

    def test_fresh_reference_supports_post_revocation_adaptation(self):
        raw = context()
        raw["fresh_account_refs"] = {"alice": "alice-session-fresh"}
        result = asyncio.run(execute(raw, FakeTools()))
        self.assertEqual(result["adaptation"]["outcome"], "still_exposed")
        self.assertEqual(result["adaptation"]["credential_ref"], "alice-session-fresh")


if __name__ == "__main__":
    unittest.main()
