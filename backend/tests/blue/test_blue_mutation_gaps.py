"""Tests that close gaps found by a manual mutation sweep of blue's pure modules.

Run from backend/: python -m unittest discover -s tests/blue -v

Each test kills one mutation that the baseline blue suite did not notice when
it was applied by hand to detection.py, proposals.py, patches.py, or
observe.py. The comment above each test names the line and the surviving
mutation. Tests read the shipped manifest; they create no files.
"""

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib
import unittest
from unittest import mock

from app.agents.blue import (
    ANONYMOUS_READ,
    APPLY_PATCH,
    CROSS_USER_READ,
    PRIVATE_ORDERS_POLICY,
    REVOKE_SESSION,
    ContextError,
    PatchManifestError,
    SkippedRecord,
    detect_suspicious_access,
    load_patch_manifest,
    observe,
    parse_patch_manifest,
    parse_utc_timestamp,
    propose_ownership_patch,
    propose_session_revocations,
)
from app.agents.blue.proposals import revocation_id
from blue_test_helpers import load_shared, log

observe_module = importlib.import_module("app.agents.blue.observe")
MANIFEST_FILE = "defenses/patches/ownership-fix-001/manifest.json"
GENERATED_AT = "2026-09-30T16:00:00Z"
POLICY = {"id": "private-orders-owner-only", "owner_only_actions": ["read_private_order"]}


def detect(*records):
    return detect_suspicious_access(list(records), PRIVATE_ORDERS_POLICY)


def alerts_for(*records):
    return detect(*records).alerts


def manifest_data():
    return load_shared(MANIFEST_FILE)


def context(telemetry, **overrides):
    base = {"target_id": "storefront-lab", "target_version": "lab-v1", "data_source": "live",
            "telemetry": telemetry, "access_policy": POLICY, "previous_defenses": [],
            "budgets": {"max_steps": 5, "max_requests": 10, "timeout_seconds": 30},
            "assessment_id": "run-1", "generated_at": GENERATED_AT}
    base.update(overrides)
    return base


def run(ctx):
    return asyncio.run(observe(ctx))


def event(kind, data, event_id, version="lab-v1", second=10):
    actor = "blue" if kind == "defense.proposed" else "system"
    return {"schema_version": "1.0", "id": event_id, "assessment_id": "run-1", "type": kind, "actor": actor,
            "timestamp": f"2026-09-30T15:01:{second:02d}Z", "target_id": "storefront-lab", "target_version": version,
            "data_source": "live", "evidence_refs": [], "data": data}


def proposed(session="alice-session-1", defense_id=None, event_id=1):
    return event("defense.proposed", {"defense_id": defense_id or f"d-{session}", "action_type": REVOKE_SESSION,
                 "summary": "Revoke.", "reason": "Contain.", "parameters": {"session_ref": session}}, event_id)


def revoke_applied(defense_id="d-alice-session-1", event_id=3, second=10):
    return event("defense.applied", {"defense_id": defense_id, "action_type": REVOKE_SESSION, "origin": "policy_action",
                 "original_version": "lab-v1", "resulting_version": "lab-v1"}, event_id, second=second)


def patch_applied(version, original="lab-v1", resulting="lab-v2", event_id=3):
    return event("defense.applied", {"defense_id": "d-patch", "action_type": APPLY_PATCH, "origin": "known_good_fallback",
                 "original_version": original, "resulting_version": resulting}, event_id, version=version)


def mitigation_ids(result):
    return [entry["defense_id"] for entry in result["report"]["respond"]["mitigation"]]


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


class ObserveGaps(unittest.TestCase):
    def assertContextError(self, ctx, pattern):
        with self.assertRaises(ContextError) as caught:
            run(ctx)
        self.assertRegex(str(caught.exception), pattern)

    # observe.py:85 - dropping target_version from the non-empty loop accepts a blank or non-string version.
    def test_target_version_must_be_a_non_empty_string(self):
        for value in ("", "   ", 5, None):
            with self.subTest(value=value):
                self.assertContextError(context([], target_version=value), "target_version must be a non-empty string")

    # observe.py:88 - dropping assessment_id from the loop accepts a blank or non-string assessment.
    def test_assessment_id_must_be_a_non_empty_string_when_present(self):
        for value in ("", "  ", 5):
            with self.subTest(value=value):
                self.assertContextError(context([], assessment_id=value), "assessment_id must be a non-empty string")

    # observe.py:94 - <= to < rejects a batch of exactly MAX_TELEMETRY_RECORDS.
    def test_telemetry_limit_is_inclusive(self):
        limit = observe_module.MAX_TELEMETRY_RECORDS
        result = run(context([{}] * limit))
        self.assertEqual((result["status"], len(result["skipped"])), ("completed", limit))
        self.assertContextError(context([{}] * (limit + 1)), f"telemetry exceeds {limit} records")

    # observe.py:133 - running the patch step without alerts loads the manifest and writes patch notes
    # for a clean observation.
    def test_patch_step_is_skipped_when_nothing_is_detected(self):
        loader = mock.Mock(side_effect=AssertionError("manifest must not be loaded without alerts"))
        with mock.patch.object(observe_module, "load_patch_manifest", loader):
            result = run(context([log("r1", "bob", "bob", version="lab-v2")], target_version="lab-v2"))
        loader.assert_not_called()
        self.assertEqual((result["alerts"], result["defense_proposals"], result["notes"]), ([], [], []))

    # observe.py:190 - dropping the per-item string check accepts non-string or blank owner-only actions.
    def test_policy_actions_must_all_be_non_empty_strings(self):
        for actions in ([5], [""], ["  "], ["read_private_order", None]):
            with self.subTest(actions=actions):
                policy = {"id": "private-orders-owner-only", "owner_only_actions": actions}
                self.assertContextError(context([], access_policy=policy), "owner_only_actions must be a non-empty list")

    # observe.py:203 - skipping the list check lets a mapping pass silently and a scalar crash with TypeError.
    def test_previous_defenses_must_be_a_list(self):
        for value in ({}, None, 5):
            with self.subTest(value=value):
                self.assertContextError(context([], previous_defenses=value), "previous_defenses must be a list")

    # observe.py:211 - skipping the identifier check accepts a DefenseProposal with an unusable target.
    def test_in_process_proposal_needs_identifier_target_and_version(self):
        proposal = propose_session_revocations(alerts_for(log("r1", "alice", "bob")))[0]
        for change in ({"target_id": "bad target!"}, {"target_version": ""}, {"target_id": "a" * 200}):
            with self.subTest(change=change):
                ctx = context([log("r1", "alice", "bob")], previous_defenses=[replace(proposal, **change)])
                self.assertContextError(ctx, "DefenseProposal target_id and target_version must be identifiers")

    # observe.py:224 - skipping the schema_version check accepts events from another contract version.
    def test_previous_defense_events_must_be_schema_version_1_0(self):
        for value in ("2.0", 1.0, None):
            with self.subTest(value=value):
                ctx = context([], previous_defenses=[{**proposed(), "schema_version": value}])
                self.assertContextError(ctx, "schema_version must be 1.0")

    # observe.py:225 - isinstance(..., int) lets a boolean pass as an event id.
    def test_previous_defense_event_id_rejects_booleans(self):
        for value in (True, False):
            with self.subTest(value=value):
                ctx = context([], previous_defenses=[{**proposed(), "id": value}])
                self.assertContextError(ctx, "event id must be an integer or identifier")

    # observe.py:228 - skipping the scope identifier checks lets malformed scope fields through
    # (they would be silently left out of scope instead of rejected).
    def test_previous_defense_event_scope_fields_must_be_identifiers(self):
        for key, value in (("target_id", "bad target!"), ("assessment_id", ""), ("target_version", None)):
            with self.subTest(key=key):
                ctx = context([], previous_defenses=[{**proposed(), key: value}])
                self.assertContextError(ctx, f"event {key} must be an identifier")

    # observe.py:229 - skipping the data_source check accepts an unlabeled event.
    def test_previous_defense_event_data_source_must_be_a_contract_label(self):
        for value in ("liveish", None, ""):
            with self.subTest(value=value):
                ctx = context([], previous_defenses=[{**proposed(), "data_source": value}])
                self.assertContextError(ctx, "data_source must be fixture, live, or recorded")

    # observe.py:242 - skipping the missing-key check accepts a proposal without a summary and turns a
    # missing origin or reason into a KeyError.
    def test_previous_defense_data_must_hold_every_required_key(self):
        proposal_data = dict(proposed()["data"])
        del proposal_data["summary"]
        applied_data = dict(revoke_applied()["data"])
        del applied_data["origin"]
        cases = (("defense.proposed", proposal_data, "summary"),
                 ("defense.applied", applied_data, "origin"),
                 ("defense.failed", {"defense_id": "d-alice-session-1"}, "reason"))
        for kind, data, missing in cases:
            with self.subTest(kind=kind):
                ctx = context([], previous_defenses=[event(kind, data, 1)])
                self.assertContextError(ctx, f"{kind} data missing {missing}")

    # observe.py:252 - keeping non-identifier parameters lets a session reference that failed the
    # identifier check credit containment and suppress blue's own proposal.
    def test_non_identifier_session_parameter_never_credits_containment(self):
        session = "alice session 1"
        previous = [proposed(session, defense_id="d-1"), revoke_applied("d-1")]
        result = run(context([log("r1", "alice", "bob", session=session)], previous_defenses=previous))
        self.assertEqual(result["report"]["status"], "open")
        self.assertEqual([p["parameters"] for p in result["defense_proposals"] if p["action_type"] == REVOKE_SESSION],
                         [{"session_ref": session}])
        self.assertTrue(any("left out of the report" in note for note in result["notes"]), result["notes"])

    # observe.py:286 - dropping the str guard echoes a non-string request_id in the skipped list.
    def test_skipped_entries_never_echo_a_non_string_request_id(self):
        result = run(context([{**log("r1", "alice", "bob"), "request_id": 7}]))
        self.assertEqual(result["skipped"], [{"request_id": None, "reason": "request_id must be a non-empty string"}])

    # observe.py:288 - isinstance(..., (str, int)) keeps booleans, which detection then reports as typed values
    # instead of missing fields.
    def test_projection_drops_booleans(self):
        for field in ("actor_ref", "http_status", "resource_id"):
            with self.subTest(field=field):
                result = run(context([{**log("r1", "alice", "bob"), field: True}]))
                self.assertEqual(result["alerts"], [])
                self.assertEqual([entry["reason"] for entry in result["skipped"]], [f"missing {field}"])

    # observe.py:333 - letting defense.proposed events through to outcomes puts a previous proposal in the report.
    def test_previous_proposals_deduplicate_but_stay_out_of_the_report(self):
        result = run(context([log("r1", "alice", "bob")], previous_defenses=[proposed()]))
        self.assertEqual([p["action_type"] for p in result["defense_proposals"]], [APPLY_PATCH])
        self.assertEqual(mitigation_ids(result), [p["defense_id"] for p in result["defense_proposals"]])

    # observe.py:335 - ignoring original_version drops a patch whose event carries the resulting version.
    def test_applied_patch_counts_for_its_original_version(self):
        previous = [patch_applied(version="lab-v2", original="lab-v1", resulting="lab-v2")]
        result = run(context([log("r1", "alice", "bob")], previous_defenses=previous))
        self.assertEqual(result["report"]["status"], "awaiting_retest")
        self.assertIn("d-patch", mitigation_ids(result))
        self.assertFalse(any("another target version" in note for note in result["notes"]), result["notes"])

    # observe.py:336 - ignoring resulting_version drops a patch whose event carries the original version.
    def test_applied_patch_counts_for_its_resulting_version(self):
        previous = [patch_applied(version="lab-v1", original="lab-v1", resulting="lab-v2")]
        result = run(context([log("r1", "alice", "bob", version="lab-v2")], target_version="lab-v2",
                             previous_defenses=previous))
        self.assertEqual(result["report"]["status"], "fix_failed")
        self.assertIn("d-patch", mitigation_ids(result))
        self.assertFalse(any("another target version" in note for note in result["notes"]), result["notes"])

    # observe.py:370 - dropping the kind check lets a revoked session cover an anonymous read.
    def test_anonymous_read_is_never_contained_by_a_revoked_session(self):
        previous = [proposed("s-anon"), revoke_applied("d-s-anon")]
        result = run(context([log("r1", None, "bob", session="s-anon")], previous_defenses=previous))
        self.assertEqual([a["kind"] for a in result["alerts"]], [ANONYMOUS_READ])
        self.assertEqual(result["report"]["status"], "open")
        self.assertNotIn("d-s-anon", mitigation_ids(result))
        self.assertTrue(any("not covered by a revoked session" in note for note in result["notes"]), result["notes"])

    # observe.py:435 - n <= 1 writes "0 patch" and "0 session revocation".
    def test_zero_counts_are_plural(self):
        result = run(context([log("r1", None, "bob", version="lab-v2")], target_version="lab-v2"))
        self.assertIn("Proposed 0 session revocations (containment, not a fix) and 0 patches.", result["summary"])

    # observe.py:439 - dropping strip() accepts whitespace-only identifiers.
    def test_whitespace_only_text_fields_are_rejected(self):
        for key in ("target_id", "target_version", "assessment_id", "generated_at"):
            with self.subTest(key=key):
                self.assertContextError(context([], **{key: " \t"}), f"{key} must be a non-empty string")
        policy = {"id": "   ", "owner_only_actions": ["read_private_order"]}
        self.assertContextError(context([], access_policy=policy), "access_policy id must be a non-empty string")


if __name__ == "__main__":
    unittest.main()
