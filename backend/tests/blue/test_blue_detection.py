"""Blue detector tests. Run from backend/: python -m unittest discover -s tests/blue -v"""

import unittest

from app.agents.blue import (
    ANONYMOUS_READ,
    CROSS_USER_READ,
    PRIVATE_ORDERS_POLICY,
    detect_suspicious_access,
)
from blue_test_helpers import load_shared, log, secret_keys


def detect(*records):
    return detect_suspicious_access(list(records), PRIVATE_ORDERS_POLICY)


class FixtureTelemetry(unittest.TestCase):
    def setUp(self):
        self.fixture = load_shared("shared/fixtures/demo-run.json")
        self.contract = load_shared("shared/contracts/v1.json")

    def test_flags_only_the_cross_user_read(self):
        result = detect_suspicious_access(self.fixture["telemetry"], PRIVATE_ORDERS_POLICY)
        self.assertEqual(result.skipped, ())
        self.assertEqual(len(result.alerts), 1)
        alert = result.alerts[0]
        self.assertEqual(alert.kind, CROSS_USER_READ)
        self.assertEqual(alert.request_ids, ("req-red",))
        self.assertEqual(alert.session_ref, "alice-session-1")
        self.assertEqual(alert.resource_owner_refs, ("bob",))
        self.assertEqual(alert.target_version, "lab-v1")

    def test_matches_fixture_alert_and_contract(self):
        alert = detect_suspicious_access(self.fixture["telemetry"], PRIVATE_ORDERS_POLICY).alerts[0]
        data = alert.event_data()
        required = self.contract["event_types"]["alert.created"]["required"]
        self.assertLessEqual(set(required), data.keys())
        expected = next(e for e in self.fixture["events"] if e["type"] == "alert.created")
        self.assertEqual(data["request_ids"], expected["data"]["request_ids"])
        self.assertEqual(secret_keys(data), set())


class Detection(unittest.TestCase):
    def test_owner_reading_own_record_is_not_suspicious(self):
        self.assertEqual(detect(log("r1", "bob", "bob"), log("r2", "alice", "alice")).alerts, ())

    def test_denied_attempts_do_not_alert(self):
        records = [log(f"r{status}", "alice", "bob", status) for status in (401, 403, 404, 500)]
        self.assertEqual(detect(*records).alerts, ())

    def test_anonymous_successful_read_alerts(self):
        result = detect(log("r1", None, "bob"), log("r2", None, "bob", 401))
        self.assertEqual([a.kind for a in result.alerts], [ANONYMOUS_READ])
        self.assertEqual(result.alerts[0].request_ids, ("r1",))

    def test_other_actions_are_ignored(self):
        self.assertEqual(detect(log("r1", "alice", "bob", action="list_own_orders")).alerts, ())

    def test_groups_by_session_in_time_order(self):
        result = detect(
            log("r3", "alice", "bob", second=9, resource="order-205"),
            log("r1", "alice", "bob", second=4),
            log("r2", "mallory", "alice", second=6, resource="order-101"),
            log("r4", "alice", "carol", second=12, session="alice-session-2", resource="order-301"),
        )
        self.assertEqual([a.request_ids for a in result.alerts], [("r1", "r3"), ("r2",), ("r4",)])
        first = result.alerts[0]
        self.assertEqual(first.resource_ids, ("order-204", "order-205"))
        self.assertEqual((first.first_seen, first.last_seen), ("2026-09-30T15:00:04Z", "2026-09-30T15:00:09Z"))
        self.assertIn("(2 requests)", first.summary)

    def test_exposure_after_patch_is_a_separate_alert(self):
        result = detect(log("r1", "alice", "bob"), log("r2", "alice", "bob", second=30, version="lab-v2"))
        self.assertEqual([a.target_version for a in result.alerts], ["lab-v1", "lab-v2"])
        self.assertNotEqual(result.alerts[0].alert_id, result.alerts[1].alert_id)

    def test_alert_ids_are_stable_as_telemetry_grows(self):
        first = detect(log("r1", "alice", "bob")).alerts[0]
        later = detect(log("r1", "alice", "bob"), log("r2", "alice", "bob", second=5)).alerts[0]
        self.assertEqual(first.alert_id, later.alert_id)
        self.assertEqual(later.request_ids, ("r1", "r2"))


class MissingOrInvalidData(unittest.TestCase):
    def test_incomplete_records_are_skipped_not_alerted(self):
        missing_owner = log("r1", "alice", "bob")
        del missing_owner["resource_owner_ref"]
        cases = {
            "missing": missing_owner,
            "unknown owner": log("r2", "alice", None),
            "string status": log("r3", "alice", "bob", "200"),
            "boolean status": log("r4", "alice", "bob", True),
            "local time": {**log("r5", "alice", "bob"), "timestamp": "2026-09-30T15:00:00"},
            "bad time": {**log("r6", "alice", "bob"), "timestamp": "yesterdayZ"},
            "empty actor": log("r7", "", "bob"),
        }
        result = detect(*cases.values(), "not a record", log("ok", "alice", "bob"))
        self.assertEqual(len(result.skipped), len(cases) + 1)
        self.assertTrue(all(skip.reason for skip in result.skipped))
        self.assertEqual([a.request_ids for a in result.alerts], [("ok",)])

    def test_skip_reasons_name_the_problem(self):
        result = detect(log("r1", "alice", None), {"request_id": "r2"})
        self.assertEqual(result.skipped[0].request_id, "r1")
        self.assertIn("owner unknown", result.skipped[0].reason)
        self.assertIn("missing", result.skipped[1].reason)

    def test_empty_telemetry(self):
        result = detect()
        self.assertEqual((result.alerts, result.skipped), ((), ()))


if __name__ == "__main__":
    unittest.main()
