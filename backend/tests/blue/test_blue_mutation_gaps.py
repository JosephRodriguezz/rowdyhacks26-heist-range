"""Tests that close gaps found by a manual mutation sweep of blue's pure modules.

Run from backend/: python -m unittest discover -s tests/blue -v

Each test kills one mutation that the baseline blue suite did not notice when
it was applied by hand to detection.py, proposals.py, or patches.py. The
comment above each test names the line and the surviving mutation. Every
observe.py mutation in the sweep was already caught, so observe.py has no
entry here. Tests read the shipped manifest; they create no files.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from app.agents.blue import (
    ANONYMOUS_READ,
    APPLY_PATCH,
    CROSS_USER_READ,
    PRIVATE_ORDERS_POLICY,
    REVOKE_SESSION,
    PatchManifestError,
    SkippedRecord,
    detect_suspicious_access,
    load_patch_manifest,
    parse_patch_manifest,
    parse_utc_timestamp,
    propose_ownership_patch,
    propose_session_revocations,
)
from app.agents.blue.proposals import revocation_id
from blue_test_helpers import load_shared, log

MANIFEST_FILE = "defenses/patches/ownership-fix-001/manifest.json"


def detect(*records):
    return detect_suspicious_access(list(records), PRIVATE_ORDERS_POLICY)


def alerts_for(*records):
    return detect(*records).alerts


def manifest_data():
    return load_shared(MANIFEST_FILE)


class DetectionGaps(unittest.TestCase):
    # detection.py:84 - dropping the str guard leaks a non-string request_id into SkippedRecord.
    def test_skipped_record_never_carries_a_non_string_request_id(self):
        result = detect({**log("r1", "alice", "bob"), "request_id": 7})
        self.assertEqual(result.alerts, ())
        self.assertEqual(result.skipped, (SkippedRecord(None, "request_id must be a non-empty string"),))

    # detection.py:91 - dropping the request_id tiebreak leaves same-second hits in input order.
    def test_same_second_requests_are_ordered_by_request_id(self):
        alerts = alerts_for(log("r2", "alice", "bob"), log("r10", "alice", "bob"), log("r1", "alice", "bob"))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].request_ids, ("r1", "r10", "r2"))

    # detection.py:105-106 - allowing "" or skipping action/resource_id lets bad records through
    # (empty strings pass the mutated type check; a None action silently matches nothing).
    def test_each_required_string_field_rejects_empty_and_non_string_values(self):
        for name in ("request_id", "target_id", "target_version", "resource_id", "action"):
            for value in ("", None, 7):
                with self.subTest(field=name, value=value):
                    result = detect({**log("r1", "alice", "bob"), name: value})
                    self.assertEqual(result.alerts, ())
                    self.assertEqual([entry.reason for entry in result.skipped],
                                     [f"{name} must be a non-empty string"])

    # detection.py:108 - skipping session_ref or resource_owner_ref turns typed garbage into alerts.
    def test_each_nullable_string_field_rejects_empty_and_non_string_values(self):
        for name in ("actor_ref", "session_ref", "resource_owner_ref"):
            for value in ("", 7):
                with self.subTest(field=name, value=value):
                    result = detect({**log("r1", "alice", "bob"), name: value})
                    self.assertEqual(result.alerts, ())
                    self.assertEqual([entry.reason for entry in result.skipped],
                                     [f"{name} must be a non-empty string or null"])

    # detection.py:115 - ignoring the action makes every record without an owner inconclusive,
    # even for actions the policy does not restrict.
    def test_unknown_owner_is_only_a_problem_for_owner_only_actions(self):
        result = detect(log("r1", "alice", None, action="list_products"))
        self.assertEqual((result.alerts, result.skipped), ((), ()))

    # detection.py:121 - widening the success range to 199 or 300 alerts on non-success statuses.
    def test_status_codes_just_outside_2xx_do_not_alert(self):
        for status in (199, 300):
            with self.subTest(status=status):
                result = detect(log("r1", "alice", "bob", status))
                self.assertEqual((result.alerts, result.skipped), ((), ()))

    # detection.py:132 - without dedup the same owner repeats in resource_owner_refs and the summary.
    def test_alert_lists_each_owner_once(self):
        alerts = alerts_for(log("r1", "alice", "bob", resource="order-204"),
                            log("r2", "alice", "bob", resource="order-205", second=1))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].resource_owner_refs, ("bob",))
        self.assertEqual(alerts[0].summary, "alice read private data owned by bob (2 requests).")

    # detection.py:147 - without dedup a resource read twice is listed twice.
    def test_alert_lists_each_resource_once_but_every_request(self):
        alerts = alerts_for(log("r1", "alice", "bob"), log("r2", "alice", "bob", second=1))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].resource_ids, ("order-204",))
        self.assertEqual(alerts[0].request_ids, ("r1", "r2"))

    # detection.py:156 - dropping the Z requirement accepts any string whose last character is noise.
    def test_timestamp_must_end_in_uppercase_z(self):
        self.assertIsNone(parse_utc_timestamp("2026-09-30T15:00:04z"))
        self.assertIsNone(parse_utc_timestamp("2026-09-30T15:00:04+00:00"))
        result = detect({**log("r1", "alice", "bob"), "timestamp": "2026-09-30T15:00:04z"})
        self.assertEqual(result.alerts, ())
        self.assertEqual([entry.reason for entry in result.skipped], ["timestamp must be ISO 8601 UTC ending in Z"])

    # detection.py:159 - parsing without the +00:00 suffix returns a naive datetime that cannot be
    # compared with aware ones.
    def test_parsed_timestamps_are_utc_aware(self):
        parsed = parse_utc_timestamp("2026-09-30T15:00:04Z")
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertLess(parsed, datetime(2026, 10, 1, tzinfo=timezone.utc))


class ProposalGaps(unittest.TestCase):
    def setUp(self):
        self.manifest = load_patch_manifest("ownership-fix-001")

    # proposals.py:64 - ignoring the alert kind revokes the session attached to an anonymous read.
    def test_anonymous_read_with_a_session_is_not_revoked(self):
        alerts = alerts_for(log("r1", None, "bob", session="anon-session-1"))
        self.assertEqual([(alert.kind, alert.session_ref) for alert in alerts], [(ANONYMOUS_READ, "anon-session-1")])
        self.assertEqual(propose_session_revocations(alerts), ())

    # proposals.py:64 - allowing a null session proposes revoking session None.
    def test_cross_user_read_without_a_session_is_not_revoked(self):
        alerts = alerts_for({**log("r1", "alice", "bob"), "session_ref": None})
        self.assertEqual([(alert.kind, alert.session_ref) for alert in alerts], [(CROSS_USER_READ, None)])
        self.assertEqual(propose_session_revocations(alerts), ())

    # proposals.py:73 - dropping the target from the digest gives one ID to revocations on two targets.
    def test_revocation_id_depends_on_the_target(self):
        self.assertNotEqual(revocation_id("storefront-lab", "alice-session-1"),
                            revocation_id("other-lab", "alice-session-1"))
        proposals = propose_session_revocations(alerts_for(
            log("r1", "alice", "bob"), {**log("r2", "alice", "bob", second=1), "target_id": "other-lab"}))
        self.assertEqual(sorted(proposal.target_id for proposal in proposals), ["other-lab", "storefront-lab"])
        self.assertEqual(len({proposal.defense_id for proposal in proposals}), 2)

    # proposals.py:78 - without dedup an owner seen on two versions is named twice in the reason.
    def test_revocation_reason_names_each_owner_once(self):
        alerts = alerts_for(log("r1", "alice", "bob"), log("r2", "alice", "bob", second=1, version="lab-v2"))
        self.assertEqual(len(alerts), 2)
        proposals = propose_session_revocations(alerts)
        self.assertEqual(len(proposals), 1)
        self.assertIn("owned by bob. ", proposals[0].reason)
        self.assertNotIn("bob, bob", proposals[0].reason)

    # proposals.py:112 - dropping the version from the digest reuses one ID across target versions.
    def test_patch_proposal_id_depends_on_the_current_version(self):
        first = propose_ownership_patch(alerts_for(log("r1", "alice", "bob")), self.manifest, "lab-v1")
        second = propose_ownership_patch(alerts_for(log("r2", "alice", "bob", version="lab-v2")),
                                         replace(self.manifest, base_version="lab-v2"), "lab-v2")
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertNotEqual(first.defense_id, second.defense_id)

    # proposals.py:113 - counting null sessions reports an anonymous-only exposure as one session.
    def test_anonymous_only_exposure_counts_zero_sessions(self):
        proposal = propose_ownership_patch(alerts_for(log("r1", None, "bob")), self.manifest, "lab-v1")
        self.assertIn("by 0 sessions and unauthenticated requests.", proposal.reason)

    # proposals.py:114-115 - any -> all drops the unauthenticated note from a mixed exposure, and
    # moving the plural boundary writes "1 sessions" or "2 session".
    def test_patch_reason_counts_sessions_and_notes_unauthenticated_reads(self):
        mixed = propose_ownership_patch(
            alerts_for(log("r1", "alice", "bob"), log("r2", None, "bob", second=1)), self.manifest, "lab-v1")
        self.assertIn("by 1 session and unauthenticated requests.", mixed.reason)
        single = propose_ownership_patch(alerts_for(log("r1", "alice", "bob")), self.manifest, "lab-v1")
        self.assertIn("by 1 session.", single.reason)
        double = propose_ownership_patch(
            alerts_for(log("r1", "alice", "bob"), log("r2", "carol", "bob", second=1)), self.manifest, "lab-v1")
        self.assertIn("by 2 sessions.", double.reason)

    # proposals.py:146 - ignoring action_type lets a patch's parameters suppress a revocation and a
    # revocation's parameters suppress the patch.
    def test_previous_defenses_only_count_for_their_own_action_type(self):
        alerts = alerts_for(log("r1", "alice", "bob"))
        wrong_kind_revocation = {"action_type": APPLY_PATCH, "parameters": {"session_ref": "alice-session-1"}}
        proposals = propose_session_revocations(alerts, [wrong_kind_revocation])
        self.assertEqual([proposal.parameters for proposal in proposals], [{"session_ref": "alice-session-1"}])
        wrong_kind_patch = {"action_type": REVOKE_SESSION, "parameters": {"patch_id": "ownership-fix-001"}}
        self.assertIsNotNone(propose_ownership_patch(alerts, self.manifest, "lab-v1", [wrong_kind_patch]))

    # proposals.py:149 - accepting non-string parameters crashes on an unhashable value.
    def test_previous_defenses_with_non_string_parameters_are_ignored(self):
        alerts = alerts_for(log("r1", "alice", "bob"))
        previous = [{"action_type": REVOKE_SESSION, "parameters": {"session_ref": ["alice-session-1"]}},
                    {"action_type": APPLY_PATCH, "parameters": {"patch_id": {"id": "ownership-fix-001"}}}]
        proposals = propose_session_revocations(alerts, previous)
        self.assertEqual([proposal.parameters for proposal in proposals], [{"session_ref": "alice-session-1"}])
        self.assertIsNotNone(propose_ownership_patch(alerts, self.manifest, "lab-v1", previous))


class ManifestGaps(unittest.TestCase):
    def assertRejected(self, data, pattern=None):
        with self.assertRaises(PatchManifestError) as caught:
            parse_patch_manifest(data)
        if pattern:
            self.assertRegex(str(caught.exception), pattern)

    # patches.py:59 - a prefix match sends a loader lookup to the filesystem instead of rejecting it.
    def test_loader_rejects_ids_that_only_start_like_a_patch_id(self):
        for patch_id in ("ownership-fix-001X", "ownership-fix-001 x", "ownership-fix-001/x"):
            with self.subTest(patch_id=patch_id):
                with self.assertRaises(PatchManifestError):
                    load_patch_manifest(patch_id)

    # patches.py:71 - skipping the object check turns None or a number into a TypeError.
    def test_non_object_manifests_are_rejected_cleanly(self):
        for data in (None, 42, 1.5):
            with self.subTest(data=data):
                self.assertRejected(data, "must be an object")

    # patches.py:75 - dropping strip() accepts whitespace-only text fields.
    def test_blank_text_fields_are_rejected(self):
        for name in ("patch_id", "title", "base_version", "policy_id", "target_route", "change", "explanation"):
            with self.subTest(field=name):
                self.assertRejected({**manifest_data(), name: " \t\n"}, f"{name} must be a non-empty string")

    # patches.py:76 - a prefix match accepts a patch_id with trailing junk.
    def test_patch_id_must_match_completely(self):
        for patch_id in ("ownership-fix-001 extra", "ownership-fix-001/x", "ownership-fix-001\n"):
            with self.subTest(patch_id=patch_id):
                self.assertRejected({**manifest_data(), "patch_id": patch_id}, "patch_id must be")

    # patches.py:81 - dropping the per-item str check crashes in the path check instead of rejecting.
    def test_non_string_allowed_files_are_rejected_cleanly(self):
        for files in ([7], [None], ["app.py", ["nested"]]):
            with self.subTest(files=files):
                self.assertRejected({**manifest_data(), "allowed_files": files}, "allowed_files must be a list of paths")

    # patches.py:91 - allowing an empty list reports the wrong problem for a manifest with no checks.
    def test_empty_regression_checks_are_reported_as_empty(self):
        self.assertRejected({**manifest_data(), "regression_checks": []}, "regression_checks must be a non-empty list")

    # patches.py:100 - a proper-subset test rejects a manifest with exactly the two required checks.
    def test_exactly_the_required_checks_are_enough(self):
        data = manifest_data()
        data["regression_checks"] = [check for check in data["regression_checks"]
                                     if check["id"] in ("unauthorized_access", "owner_access")]
        self.assertEqual(len(data["regression_checks"]), 2)
        manifest = parse_patch_manifest(data)
        self.assertEqual({check.id for check in manifest.regression_checks}, {"unauthorized_access", "owner_access"})

    # patches.py:112 - checking only the first segment accepts traversal later in the path.
    def test_parent_references_anywhere_in_an_allowed_file_are_rejected(self):
        for name in ("lab/../app.py", "app/..", "a/b/../../etc/passwd"):
            with self.subTest(name=name):
                self.assertRejected({**manifest_data(), "allowed_files": [name]}, "relative path inside the repository")


if __name__ == "__main__":
    unittest.main()
