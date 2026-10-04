"""Blue incident evidence report tests. Run from backend/: python -m unittest discover -s tests/blue -v"""

import hashlib
import json
import unittest

from app.agents.blue import (
    PRIVATE_ORDERS_POLICY,
    REPORT_SCHEMA,
    build_incident_report,
    detect_suspicious_access,
    render_markdown,
)
from blue_test_helpers import load_shared, log

GENERATED_AT = "2026-09-30T16:00:00Z"


def event(event_id, kind, actor, data, second, version="lab-v1", refs=()):
    return {"schema_version": "1.0", "id": event_id, "assessment_id": "run-1", "type": kind, "actor": actor,
            "timestamp": f"2026-09-30T15:01:{second:02d}Z", "target_id": "storefront-lab",
            "target_version": version, "data_source": "live", "evidence_refs": list(refs), "data": data}


REVOKE_APPLIED = event(2, "defense.applied", "system", {"defense_id": "d-session", "action_type": "revoke_session",
                       "origin": "policy_action", "original_version": "lab-v1", "resulting_version": "lab-v1"}, 10)
PATCH_APPLIED = event(3, "defense.applied", "system", {"defense_id": "d-patch", "action_type": "apply_patch",
                      "origin": "known_good_fallback", "original_version": "lab-v1", "resulting_version": "lab-v2"},
                      20, "lab-v2", ["ev-patch"])


def retest(result, checks=None):
    if checks is None:
        checks = [{"id": "unauthorized_access", "expected": "denied", "actual": "denied", "passed": True},
                  {"id": "owner_access", "expected": "allowed", "actual": "allowed", "passed": True}]
    return event(4, "retest.completed", "referee", {"finding_id": "f-1", "defense_id": "d-patch",
                 "result": result, "checks": checks}, 30, "lab-v2", ["ev-retest"])


def report_for(records, events=(), data_source="live"):
    alerts = detect_suspicious_access(records, PRIVATE_ORDERS_POLICY).alerts
    return build_incident_report(assessment_id="run-1", data_source=data_source, telemetry=records,
                                 alerts=alerts, events=events, generated_at=GENERATED_AT)


def canonical_digest(value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


class FixtureReport(unittest.TestCase):
    def setUp(self):
        fixture = load_shared("shared/fixtures/demo-run.json")
        alerts = detect_suspicious_access(fixture["telemetry"], PRIVATE_ORDERS_POLICY).alerts
        self.report = build_incident_report(assessment_id=fixture["snapshot"]["id"], data_source="fixture",
                                            telemetry=fixture["telemetry"], alerts=alerts,
                                            events=fixture["events"], generated_at=GENERATED_AT)

    def test_summarizes_the_sample_run(self):
        r = self.report
        self.assertEqual(r["schema"], REPORT_SCHEMA)
        self.assertEqual(r["status"], "resolved")
        self.assertEqual(r["scope"]["sessions"], ["alice-session-1"])
        self.assertEqual(r["scope"]["resource_owners"], ["bob"])
        self.assertEqual(r["target"]["versions"], ["lab-v1", "lab-v2"])
        self.assertEqual(r["elapsed_seconds"], {"detected": 1, "contained": 4, "patched": 7, "fix_verified": 8})

    def test_classifies_with_attack_cwe_and_owasp(self):
        classification = self.report["respond"]["classification"]
        self.assertEqual([t["id"] for t in classification["attack"]], ["T1190", "T1078"])
        self.assertEqual([w["id"] for w in classification["weaknesses"]], ["CWE-639", "API1:2023"])

    def test_prevention_steps_map_to_csf_categories(self):
        steps = {s["id"]: s for s in self.report["improve"]}
        self.assertEqual(steps["enforce-ownership"]["csf"], "PR.AA")
        self.assertEqual(steps["lessons-learned"]["csf"], "ID.IM")
        self.assertIn("containment-runbook", steps)
        self.assertNotIn("require-session", steps)
        self.assertTrue(all(s["csf_name"] for s in steps.values()))

    def test_evidence_is_hashed_and_report_digest_verifies(self):
        telemetry = next(e for e in self.report["evidence"] if e["kind"] == "telemetry")
        self.assertEqual(telemetry["reference"], "req-red")
        self.assertEqual(telemetry["sha256"], canonical_digest(telemetry["record"]))
        body = {k: v for k, v in self.report.items() if k != "integrity"}
        self.assertEqual(self.report["integrity"]["report_digest"], canonical_digest(body))

    def test_limitations_name_missing_acceptance_checks(self):
        text = " ".join(self.report["limitations"])
        self.assertIn("fixture data", text)
        self.assertIn("anonymous_access", text)
        self.assertIn("protected_control", text)

    def test_markdown_is_labeled_and_ascii(self):
        markdown = render_markdown(self.report)
        self.assertIn("Data source: FIXTURE", markdown)
        for heading in ("## Detect", "## Respond", "## Recover", "## Prevent and improve", "## Evidence"):
            self.assertIn(heading, markdown)
        markdown.encode("ascii")

    def test_red_events_are_not_used(self):
        self.assertNotIn("candidate_reproduced", json.dumps(self.report))
        self.assertNotIn("finding.candidate", json.dumps(self.report))


class Status(unittest.TestCase):
    exposure = [log("r1", "alice", "bob")]

    def test_progression(self):
        cases = [
            ((), "open"),
            ((REVOKE_APPLIED,), "contained"),
            ((REVOKE_APPLIED, PATCH_APPLIED), "awaiting_retest"),
            ((REVOKE_APPLIED, PATCH_APPLIED, retest("inconclusive")), "awaiting_retest"),
            ((REVOKE_APPLIED, PATCH_APPLIED, retest("failed")), "fix_failed"),
            ((REVOKE_APPLIED, PATCH_APPLIED, retest("passed")), "resolved"),
        ]
        for events, expected in cases:
            with self.subTest(expected=expected, events=len(events)):
                self.assertEqual(report_for(self.exposure, events)["status"], expected)

    def test_exposure_on_patched_version_overrides_a_passed_retest(self):
        records = self.exposure + [log("r2", "alice", "bob", second=40, version="lab-v2")]
        report = report_for(records, (PATCH_APPLIED, retest("passed")))
        self.assertEqual(report["status"], "fix_failed")

    def test_passed_retest_requires_each_required_check(self):
        for missing in ("unauthorized_access", "owner_access"):
            with self.subTest(missing=missing):
                checks = [c for c in retest("passed")["data"]["checks"] if c["id"] != missing]
                report = report_for(self.exposure, (PATCH_APPLIED, retest("passed", checks)))
                self.assertEqual(report["status"], "awaiting_retest")
                self.assertIn("Missing required retest checks: " + missing, " ".join(report["limitations"]))

    def test_every_check_must_explicitly_pass(self):
        for passed in (False, 1, "true", None):
            with self.subTest(passed=passed):
                checks = retest("passed")["data"]["checks"]
                checks[1]["passed"] = passed
                report = report_for(self.exposure, (PATCH_APPLIED, retest("passed", checks)))
                self.assertEqual(report["status"], "awaiting_retest")
                self.assertIn("Failed or malformed retest checks: owner_access", " ".join(report["limitations"]))

    def test_actual_must_match_expected(self):
        checks = retest("passed")["data"]["checks"]
        checks[0]["actual"] = "allowed"
        report = report_for(self.exposure, (PATCH_APPLIED, retest("passed", checks)))
        self.assertEqual(report["status"], "awaiting_retest")
        self.assertIn("Failed or malformed retest checks: unauthorized_access", " ".join(report["limitations"]))

    def test_extra_checks_must_also_pass(self):
        for passed, actual, expected_status in ((True, "denied", "resolved"),
                                                (False, "denied", "awaiting_retest"),
                                                (True, "allowed", "awaiting_retest")):
            with self.subTest(passed=passed, actual=actual):
                checks = retest("passed")["data"]["checks"] + [
                    {"id": "anonymous_access", "expected": "denied", "actual": actual, "passed": passed}]
                report = report_for(self.exposure, (PATCH_APPLIED, retest("passed", checks)))
                self.assertEqual(report["status"], expected_status)
                if expected_status == "awaiting_retest":
                    self.assertIn("Failed or malformed retest checks: anonymous_access", " ".join(report["limitations"]))

    def test_malformed_checks_fail_closed_and_can_be_rendered(self):
        complete = retest("passed")["data"]["checks"]
        malformed = [None, {}, "checks", 7, [], [None], complete + ["bad"],
                     complete + [{"id": [], "passed": True}]]
        for field in ("id", "expected", "actual", "passed"):
            checks = retest("passed")["data"]["checks"]
            checks[1].pop(field)
            malformed.append(checks)
        malformed.append([{"id": c["id"], "passed": True} for c in complete])
        for checks in malformed:
            with self.subTest(checks=checks):
                attempt = retest("passed")
                attempt["data"]["checks"] = checks
                report = report_for(self.exposure, (PATCH_APPLIED, attempt))
                self.assertEqual(report["status"], "awaiting_retest")
                self.assertIn("retest checks:", " ".join(report["limitations"]))
                render_markdown(report)

    def test_incomplete_pass_has_no_fix_verified_time(self):
        checks = retest("passed")["data"]["checks"][:1]
        report = report_for(self.exposure, (PATCH_APPLIED, retest("passed", checks)))
        self.assertIsNone(report["times"]["fix_verified"])
        self.assertIn("| Fix verified | N/A | N/A |", render_markdown(report))

    def test_last_retest_controls_status(self):
        for result, checks, status in (("passed", [], "awaiting_retest"),
                                       ("failed", [], "fix_failed"),
                                       ("passed", None, "resolved")):
            with self.subTest(result=result, checks=checks):
                latest = retest(result, checks)
                latest["id"] = 5
                report = report_for(self.exposure, (PATCH_APPLIED, retest("passed"), latest))
                self.assertEqual(report["status"], status)

    def test_later_unsuccessful_retest_clears_current_verification_preserves_history(self):
        for result, checks, status in (("failed", [], "fix_failed"),
                                       ("inconclusive", [], "awaiting_retest"),
                                       ("passed", [], "awaiting_retest")):
            with self.subTest(result=result):
                passing = retest("passed")
                latest = retest(result, checks)
                latest.update(id=5, timestamp="2026-09-30T15:01:40Z")
                report = report_for(self.exposure, (PATCH_APPLIED, passing, latest))
                self.assertEqual(report["status"], status)
                self.assertIsNone(report["times"]["fix_verified"])
                self.assertIsNone(report["elapsed_seconds"]["fix_verified"])
                self.assertIn("| Fix verified | N/A | N/A |", render_markdown(report))
                self.assertEqual([r["result"] for r in report["recover"]["retests"]], ["passed", result])
                historical = next(e for e in report["evidence"] if e["evidence_id"] == "event:4")
                self.assertEqual(historical["record"], passing)
                self.assertEqual(historical["sha256"], canonical_digest(passing))

    def test_latest_applied_patch_requires_its_own_retest(self):
        for defense_id in ("d-patch-2", "d-patch"):
            with self.subTest(defense_id=defense_id):
                latest_patch = event(5, "defense.applied", "system", {
                    **PATCH_APPLIED["data"], "defense_id": defense_id,
                    "original_version": "lab-v2", "resulting_version": "lab-v3"}, 40, "lab-v3", ["ev-patch-2"])
                report = report_for(self.exposure, (PATCH_APPLIED, retest("passed"), latest_patch))
                self.assertEqual(report["status"], "awaiting_retest")
                self.assertIsNone(report["times"]["fix_verified"])
                self.assertEqual(report["recover"]["retests"][0]["result"], "passed")
                outcome = next(d["outcome"] for d in report["respond"]["mitigation"]
                               if d["defense_id"] == defense_id)
                self.assertEqual(outcome, "applied, awaiting retest")

                latest_retest = retest("passed")
                latest_retest.update(id=6, target_version="lab-v3", timestamp="2026-09-30T15:01:50Z")
                latest_retest["data"]["defense_id"] = defense_id
                verified = report_for(self.exposure, (latest_retest, latest_patch, retest("passed"), PATCH_APPLIED))
                self.assertEqual(verified["status"], "resolved")
                self.assertEqual(verified["times"]["fix_verified"], latest_retest["timestamp"])

    def test_later_malformed_timestamp_cannot_preserve_an_old_verification(self):
        for result, status in (("passed", "awaiting_retest"), ("failed", "fix_failed"),
                               ("inconclusive", "awaiting_retest")):
            with self.subTest(result=result):
                latest = retest(result)
                latest.update(id=5, timestamp="2026-09-30Z")
                report = report_for(self.exposure, (PATCH_APPLIED, retest("passed"), latest))
                self.assertEqual(report["status"], status)
                self.assertIsNone(report["times"]["fix_verified"])

    def test_patch_retest_must_follow_application_and_match_its_scope(self):
        mismatches = ({"id": 2}, {"actor": "blue"}, {"target_id": "other-lab"},
                      {"target_version": "lab-v1"}, {"assessment_id": "run-2"}, {"data_source": "fixture"},
                      {"timestamp": "2026-09-30Z"})
        for overrides in mismatches:
            with self.subTest(overrides=overrides):
                attempt = {**retest("passed"), **overrides}
                report = report_for(self.exposure, (PATCH_APPLIED, attempt))
                self.assertEqual(report["status"], "awaiting_retest")
                self.assertIsNone(report["times"]["fix_verified"])
                self.assertEqual(report["respond"]["mitigation"][0]["outcome"], "applied, awaiting retest")

    def test_post_patch_exposure_clears_verification_time(self):
        records = self.exposure + [log("r2", "alice", "bob", second=40, version="lab-v2")]
        report = report_for(records, (PATCH_APPLIED, retest("passed")))
        self.assertEqual(report["status"], "fix_failed")
        self.assertIsNone(report["times"]["fix_verified"])

    def test_incomplete_pass_does_not_label_mitigation_as_passed(self):
        report = report_for(self.exposure, (PATCH_APPLIED, retest("passed", [])))
        self.assertEqual(report["respond"]["mitigation"][0]["outcome"], "applied, awaiting retest")
        self.assertNotIn("applied, retest passed", render_markdown(report))

    def test_passed_retest_requires_an_applied_patch(self):
        self.assertEqual(report_for(self.exposure, (retest("passed"),))["status"], "open")
        attempt = retest("passed")
        attempt["data"]["defense_id"] = "d-session"
        self.assertEqual(report_for(self.exposure, (REVOKE_APPLIED, attempt))["status"], "contained")

    def test_contained_report_says_containment_is_not_a_fix(self):
        report = report_for(self.exposure, (REVOKE_APPLIED,))
        self.assertIn("does not fix", " ".join(report["limitations"]))
        self.assertEqual(report["elapsed_seconds"]["fix_verified"], None)
        self.assertIn("| Fix verified | N/A | N/A |", render_markdown(report))

    def test_no_alerts_no_report(self):
        self.assertIsNone(report_for([log("r1", "bob", "bob")]))


class EvidenceHandling(unittest.TestCase):
    def test_access_control_detector_does_not_claim_availability_was_measured(self):
        records = [log("r1", "alice", "bob"), log("r2", "bob", "bob", 503)]
        report = report_for(records)
        self.assertEqual(report["impact"]["availability"],
                         "Availability not assessed by access-control detector.")
        self.assertNotIn("No outage observed", render_markdown(report))

    def test_secret_like_fields_are_removed_before_hashing(self):
        record = {**log("r1", "alice", "bob"), "session_token": "do-not-store", "Authorization": "Bearer x"}
        report = report_for([record])
        item = report["evidence"][0]
        self.assertNotIn("do-not-store", json.dumps(report))
        self.assertEqual(sorted(item["redacted_fields"]), ["Authorization", "session_token"])
        self.assertEqual(item["sha256"], canonical_digest(item["record"]))

    def test_missing_telemetry_is_reported_not_invented(self):
        records = [log("r1", "alice", "bob")]
        alerts = detect_suspicious_access(records, PRIVATE_ORDERS_POLICY).alerts
        report = build_incident_report(assessment_id="run-1", data_source="live", telemetry=[], alerts=alerts,
                                       generated_at=GENERATED_AT)
        item = report["evidence"][0]
        self.assertIsNone(item["record"])
        self.assertIsNone(item["sha256"])
        self.assertIn("not supplied", item["note"])
        self.assertIn("not available", render_markdown(report))

    def test_anonymous_access_changes_mapping_and_prevention(self):
        report = report_for([log("r1", None, "bob")])
        self.assertEqual([t["id"] for t in report["respond"]["classification"]["attack"]], ["T1190"])
        self.assertIn("require-session", {s["id"] for s in report["improve"]})
        self.assertTrue(report["scope"]["unauthenticated_access"])

    def test_live_reports_have_no_sample_banner_and_are_deterministic(self):
        first = report_for([log("r1", "alice", "bob")], (REVOKE_APPLIED,))
        second = report_for([log("r1", "alice", "bob")], (REVOKE_APPLIED,))
        self.assertEqual(first, second)
        self.assertNotIn("Data source:", render_markdown(first))


if __name__ == "__main__":
    unittest.main()
