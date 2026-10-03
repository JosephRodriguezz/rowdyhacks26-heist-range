"""Fixture-only flow through Blue and an in-memory stand-in executor."""

import asyncio
from copy import deepcopy
from datetime import datetime
import json
import unittest

from app.agents.blue import observe, parse_patch_manifest
from app.agents.blue.executor_stub import StandInExecutor
from blue_test_helpers import load_shared


def ready_manifest(*, status="ready", base_version="lab-v1", origin="known_good_fallback"):
    return parse_patch_manifest({
        "patch_id": "ownership-fix-001", "title": "Ownership check", "status": status,
        "origin": origin, "base_version": base_version, "policy_id": "private-orders-owner-only",
        "target_route": "GET /api/orders/{id}", "allowed_files": ["cyber_range/app.py"],
        "diff_file": "fix.diff", "change": "Check ownership.", "explanation": "Bounded test double.",
        "regression_checks": [
            {"id": "unauthorized_access", "description": "Cross-user read", "expected": "denied"},
            {"id": "owner_access", "description": "Owner read", "expected": "allowed"},
        ],
    })


class BlueFlow(unittest.TestCase):
    def setUp(self):
        fixture = load_shared("shared/fixtures/demo-run.json")
        self.contract = load_shared("shared/contracts/v1.json")
        self.context = {
            "target_id": "storefront-lab", "target_version": "lab-v1", "data_source": "fixture",
            "assessment_id": fixture["snapshot"]["id"], "telemetry": fixture["telemetry"],
            "access_policy": {"id": "private-orders-owner-only", "owner_only_actions": ["read_private_order"]},
            "previous_defenses": [], "generated_at": "2026-09-30T16:00:00Z",
        }
        self.first = asyncio.run(observe(self.context))
        self.manifest = ready_manifest()
        self.executor = StandInExecutor(manifest_loader=lambda patch_id: self.manifest,
                                        known_sessions={"alice-session-1", "bob-session-1"})

    def proposal(self, action="apply_patch", event_id=1):
        payload = next(p for p in self.first["defense_proposals"] if p["action_type"] == action)
        return {
            "schema_version": "1.0", "id": event_id, "assessment_id": self.context["assessment_id"],
            "timestamp": self.context["generated_at"], "type": "defense.proposed", "actor": "blue",
            "target_id": self.context["target_id"], "target_version": "lab-v1", "data_source": "fixture",
            "evidence_refs": [], "data": deepcopy(payload),
        }

    def assert_event(self, result, proposal):
        self.assertLessEqual(set(self.contract["event_required"]), result.keys())
        spec = self.contract["event_types"][result["type"]]
        self.assertLessEqual(set(spec["required"]), result["data"].keys())
        self.assertEqual(result["actor"], spec["actor"])
        self.assertEqual(result["schema_version"], "1.0")
        self.assertEqual(result["executor"], "stand-in")
        self.assertEqual(result["data"]["defense_id"], proposal["data"]["defense_id"])
        for key in ("assessment_id", "target_id", "data_source"):
            self.assertEqual(result[key], proposal[key])
        self.assertEqual(result["target_version"], self.executor.current_version)
        self.assertIs(type(result["id"]), int)
        self.assertGreater(result["id"], proposal["id"])
        self.assertTrue(result["timestamp"].endswith("Z"))
        self.assertIsNotNone(datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00")).tzinfo)
        self.assertEqual(result["evidence_refs"], [])
        # The actual executor result, without repairs, must be accepted by observe.
        second = asyncio.run(observe({**self.context, "data_source": result["data_source"],
                                     "previous_defenses": [result]}))
        self.assertNotEqual(second["report"]["status"], "resolved")
        self.assertEqual(second["report"]["recover"], {"verdicts": [], "retests": []})
        return second

    def assert_failure(self, proposal, code, executor=None):
        executor = executor or self.executor
        before = (executor.current_version, set(executor.revoked_sessions))
        result = executor.apply(proposal)
        self.assertEqual(result["type"], "defense.failed")
        self.assertEqual(result["data"]["code"], code)
        self.assertIsInstance(result["data"]["reason"], str)
        self.assertTrue(result["data"]["reason"])
        self.assertNotIn("reason-marker", json.dumps(result))
        self.assertEqual((executor.current_version, set(executor.revoked_sessions)), before)
        previous = self.executor
        self.executor = executor
        try:
            self.assert_event(result, proposal)
        finally:
            self.executor = previous
        return result

    def test_revoke_result_prevents_repeat_proposal_and_is_containment(self):
        proposal = self.proposal("revoke_session")
        result = self.executor.apply(proposal)
        self.assertEqual(result["type"], "defense.applied")
        self.assertEqual(result["data"]["action_type"], "revoke_session")
        self.assertEqual(result["data"]["origin"], "policy_action")
        self.assertEqual((result["data"]["original_version"], result["data"]["resulting_version"]),
                         ("lab-v1", "lab-v1"))
        self.assertEqual(self.executor.revoked_sessions, {"alice-session-1"})
        second = self.assert_event(result, proposal)
        self.assertEqual(second["report"]["status"], "contained")
        self.assertNotIn("revoke_session", [p["action_type"] for p in second["defense_proposals"]])
        self.assertIn("does not fix", " ".join(second["report"]["limitations"]))
        self.assertIsNone(second["report"]["times"]["fix_verified"])

    def test_draft_patch_is_refused(self):
        self.manifest = ready_manifest(status="draft")
        self.assert_failure(self.proposal(), "draft_patch")

    def test_default_loader_refuses_shipped_draft(self):
        # Default loader only reads the committed draft; it executes no patch.
        self.assert_failure(self.proposal(), "draft_patch", StandInExecutor())

    def test_ready_patch_applies_with_manifest_provenance_and_awaits_retest(self):
        for origin in ("known_good_fallback", "generated"):
            with self.subTest(origin=origin):
                self.manifest = ready_manifest(origin=origin)
                self.executor = StandInExecutor(manifest_loader=lambda patch_id: self.manifest)
                proposal = self.proposal()
                proposal["data"]["origin"] = "untrusted-origin-marker"
                result = self.executor.apply(proposal)
                self.assertEqual(result["type"], "defense.applied")
                self.assertEqual(result["data"]["action_type"], "apply_patch")
                self.assertEqual(result["data"]["origin"], origin)
                self.assertEqual((result["data"]["original_version"], result["data"]["resulting_version"]),
                                 ("lab-v1", "lab-v2"))
                self.assertEqual(self.executor.current_version, "lab-v2")
                second = self.assert_event(result, proposal)
                self.assertEqual(second["report"]["status"], "awaiting_retest")
                self.assertIsNone(second["report"]["times"]["fix_verified"])

    def test_stale_proposal_base_version_is_refused(self):
        proposal = self.proposal()
        proposal["data"]["parameters"]["base_version"] = "lab-v0"
        self.assert_failure(proposal, "stale_base_version")

    def test_stale_manifest_base_version_is_refused(self):
        self.manifest = ready_manifest(base_version="lab-v0")
        self.assert_failure(self.proposal(), "stale_base_version")

    def test_target_current_version_is_used_for_stale_check(self):
        executor = StandInExecutor("lab-v2", manifest_loader=lambda patch_id: self.manifest)
        self.assert_failure(self.proposal(), "stale_base_version", executor)

    def test_patch_advances_injected_current_version(self):
        self.manifest = ready_manifest(base_version="lab-v7")
        self.executor = StandInExecutor("lab-v7", manifest_loader=lambda patch_id: self.manifest)
        proposal = self.proposal()
        proposal["target_version"] = "lab-v7"
        proposal["data"]["parameters"]["base_version"] = "lab-v7"
        result = self.executor.apply(proposal)
        self.assertEqual(result["type"], "defense.applied")
        self.assertEqual((result["data"]["original_version"], result["data"]["resulting_version"]),
                         ("lab-v7", "lab-v8"))
        self.assert_event(result, proposal)

    def test_same_defense_id_cannot_be_applied_twice(self):
        for action in ("revoke_session", "apply_patch"):
            with self.subTest(action=action):
                self.executor = StandInExecutor(manifest_loader=lambda patch_id: self.manifest,
                                                known_sessions={"alice-session-1"})
                proposal = self.proposal(action)
                first = self.executor.apply(proposal)
                self.assertEqual(first["type"], "defense.applied")
                repeated = self.assert_failure(proposal, "already_applied")
                self.assertGreater(repeated["id"], first["id"])
                # Changing the action cannot bypass defense ID deduplication.
                proposal["data"]["action_type"] = "unsupported-marker"
                self.assert_failure(proposal, "already_applied")

    def test_unsupported_action_is_refused_with_fixed_reason(self):
        reasons = []
        for marker in ("reason-marker-one", "reason-marker-two"):
            proposal = self.proposal()
            proposal["data"].update(action_type="unsupported-marker", reason=marker, summary=marker)
            result = self.assert_failure(proposal, "unsupported_action")
            self.assertNotIn("unsupported-marker", json.dumps(result))
            reasons.append(result["data"]["reason"])
        self.assertEqual(reasons[0], reasons[1])

    def test_unknown_or_malformed_session_is_refused(self):
        for session in ("unknown-session", "", None, [], "reason-marker-session"):
            with self.subTest(session=session):
                proposal = self.proposal("revoke_session")
                proposal["data"]["parameters"]["session_ref"] = session
                self.assert_failure(proposal, "unknown_session")
        proposal["data"]["parameters"] = {}
        self.assert_failure(proposal, "unknown_session")

    def test_default_session_registry_is_empty_and_injected_registry_is_copied(self):
        self.assert_failure(self.proposal("revoke_session"), "unknown_session", StandInExecutor())
        known = {"alice-session-1"}
        executor = StandInExecutor(known_sessions=known)
        known.clear()
        self.assertEqual(executor.apply(self.proposal("revoke_session"))["type"], "defense.applied")

    def test_failed_attempt_does_not_consume_defense_id(self):
        proposal = self.proposal()
        self.manifest = ready_manifest(status="draft")
        self.assert_failure(proposal, "draft_patch")
        self.manifest = ready_manifest()
        result = self.executor.apply(proposal)
        self.assertEqual(result["type"], "defense.applied")
        self.assert_event(result, proposal)

    def test_result_projects_fields_and_preserves_source_without_mutating_proposal(self):
        for source in ("fixture", "recorded"):
            with self.subTest(source=source):
                self.executor = StandInExecutor(known_sessions={"alice-session-1"})
                proposal = self.proposal("revoke_session", event_id=20)
                proposal.update(data_source=source, extra="reason-marker-envelope")
                proposal["data"].update(summary="reason-marker-summary", reason="reason-marker-reason",
                                        extra={"value": "reason-marker-extra"})
                before = deepcopy(proposal)
                result = self.executor.apply(proposal)
                self.assertEqual(proposal, before)
                self.assertNotIn("reason-marker", json.dumps(result))
                self.assert_event(result, proposal)

    def test_loader_failures_are_fixed_and_leave_state_unchanged(self):
        for exception in (FileNotFoundError("reason-marker-file"), ValueError("reason-marker-manifest")):
            with self.subTest(exception=type(exception).__name__):
                def unavailable(patch_id):
                    raise exception
                executor = StandInExecutor(manifest_loader=unavailable)
                self.assert_failure(self.proposal(), "unsupported_action", executor)

    def test_malformed_envelopes_fail_closed_before_state_changes(self):
        invalid = [None, {}, {**self.proposal(), "type": "defense.applied"},
                   {**self.proposal(), "actor": "system"}, {**self.proposal(), "id": True},
                   {**self.proposal(), "data_source": "unlabeled"},
                   {**self.proposal(), "target_id": "reason-marker invalid"}]
        missing = self.proposal()
        missing.pop("assessment_id")
        invalid.append(missing)
        for proposal in invalid:
            with self.subTest(proposal=proposal), self.assertRaisesRegex(ValueError, "^Expected a defense.proposed contract event.$"):
                self.executor.apply(proposal)
            self.assertEqual(self.executor.current_version, "lab-v1")
            self.assertEqual(self.executor.revoked_sessions, set())


if __name__ == "__main__":
    unittest.main()
