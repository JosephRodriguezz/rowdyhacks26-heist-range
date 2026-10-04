"""Blue session-revocation proposal tests. Run from backend/: python -m unittest discover -s tests/blue -v"""

import unittest

from app.agents.blue import (
    CONTAINMENT,
    PRIVATE_ORDERS_POLICY,
    REVOKE_SESSION,
    detect_suspicious_access,
    propose_session_revocations,
)
from blue_test_helpers import load_shared, log, secret_keys


def propose(*records, previous=()):
    alerts = detect_suspicious_access(list(records), PRIVATE_ORDERS_POLICY).alerts
    return propose_session_revocations(alerts, previous)


def revoked(session_ref):
    return {"action_type": REVOKE_SESSION, "parameters": {"session_ref": session_ref}}


class FixtureProposal(unittest.TestCase):
    def setUp(self):
        self.fixture = load_shared("shared/fixtures/demo-run.json")
        self.contract = load_shared("shared/contracts/v1.json")

    def test_proposes_revoking_the_attacking_session(self):
        proposals = propose(*self.fixture["telemetry"])
        self.assertEqual(len(proposals), 1)
        data = proposals[0].event_data()
        expected = next(e for e in self.fixture["events"] if e["type"] == "defense.proposed")
        self.assertEqual(data["action_type"], expected["data"]["action_type"])
        self.assertEqual(data["parameters"], expected["data"]["parameters"])

    def test_payload_meets_contract(self):
        data = propose(*self.fixture["telemetry"])[0].event_data()
        required = self.contract["event_types"]["defense.proposed"]["required"]
        self.assertLessEqual(set(required), data.keys())
        self.assertIn(data["action_type"], {"revoke_session", "apply_patch"})
        self.assertEqual(set(data["parameters"]), {"session_ref"})
        self.assertEqual(secret_keys(data), set())


class Revocation(unittest.TestCase):
    def test_labeled_as_containment_not_a_fix(self):
        proposal = propose(log("r1", "alice", "bob"))[0]
        self.assertEqual(proposal.effect, CONTAINMENT)
        self.assertIn("does not fix", proposal.reason)
        self.assertIn("alice-session-1", proposal.summary)
        self.assertIn("new session for alice", proposal.expected_effect)

    def test_links_back_to_its_alerts(self):
        alerts = detect_suspicious_access([log("r1", "alice", "bob")], PRIVATE_ORDERS_POLICY).alerts
        proposal = propose_session_revocations(alerts)[0]
        self.assertEqual(proposal.alert_ids, (alerts[0].alert_id,))

    def test_no_alerts_no_proposals(self):
        self.assertEqual(propose(log("r1", "bob", "bob"), log("r2", "alice", "bob", 403)), ())

    def test_anonymous_reads_have_no_session_to_revoke(self):
        self.assertEqual(propose(log("r1", None, "bob")), ())

    def test_one_proposal_per_session(self):
        proposals = propose(
            log("r1", "alice", "bob", second=1),
            log("r2", "alice", "bob", second=40, version="lab-v2"),
            log("r3", "mallory", "alice", second=5, resource="order-101"),
        )
        self.assertEqual([p.parameters["session_ref"] for p in proposals], ["alice-session-1", "mallory-session-1"])
        self.assertEqual(len(proposals[0].alert_ids), 2)
        self.assertEqual(proposals[0].target_version, "lab-v2")

    def test_latest_version_uses_real_time_order(self):
        early = log("r1", "alice", "bob", version="lab-v2")
        early["timestamp"] = "2026-09-30T15:00:04Z"
        late = log("r2", "alice", "bob", version="lab-v1")
        late["timestamp"] = "2026-09-30T15:00:04.500Z"
        self.assertEqual(propose(late, early)[0].target_version, "lab-v1")

    def test_defense_ids_are_stable_and_distinct(self):
        first = propose(log("r1", "alice", "bob"))[0]
        again = propose(log("r1", "alice", "bob"), log("r2", "alice", "bob", second=9))[0]
        other = propose(log("r3", "mallory", "bob"))[0]
        self.assertEqual(first.defense_id, again.defense_id)
        self.assertNotEqual(first.defense_id, other.defense_id)


class PreviousDefenses(unittest.TestCase):
    def test_already_revoked_session_is_not_proposed_again(self):
        self.assertEqual(propose(log("r1", "alice", "bob"), previous=[revoked("alice-session-1")]), ())

    def test_accepts_its_own_earlier_proposals(self):
        earlier = propose(log("r1", "alice", "bob"))
        self.assertEqual(propose(log("r1", "alice", "bob"), previous=earlier), ())

    def test_fresh_session_after_revocation_gets_a_new_proposal(self):
        proposals = propose(
            log("r1", "alice", "bob", second=1),
            log("r2", "alice", "bob", second=20, session="alice-session-2"),
            previous=[revoked("alice-session-1")],
        )
        self.assertEqual([p.parameters["session_ref"] for p in proposals], ["alice-session-2"])

    def test_other_defenses_do_not_suppress_revocation(self):
        patch = {"action_type": "apply_patch", "parameters": {"patch_id": "ownership-fix-001", "base_version": "lab-v1"}}
        malformed = [None, "revoke", {"action_type": REVOKE_SESSION}, {"action_type": REVOKE_SESSION, "parameters": []}]
        proposals = propose(log("r1", "alice", "bob"), previous=[patch, revoked("bob-session-1"), *malformed])
        self.assertEqual([p.parameters["session_ref"] for p in proposals], ["alice-session-1"])


if __name__ == "__main__":
    unittest.main()
