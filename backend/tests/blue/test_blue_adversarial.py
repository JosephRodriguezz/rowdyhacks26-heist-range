"""Adversarial tests for blue's public functions. Run from backend/: python -m unittest discover -s tests/blue -v

Hostile inputs are pushed through detection, proposals, patches, and observe. Every
test asserts the CORRECT behavior. A test marked @unittest.expectedFailure documents a
real bug found on 2026-10-03 (lane F1); its comment names the bug, the input, and the
source line. When the source is fixed the test passes, unittest reports an unexpected
success, and the decorator is removed. Never edit a test to match a bug.

Nothing here asserts about retest events or the "resolved" report path.
"""

import asyncio
import json
import random
import unittest

from app.agents.blue import (
    CROSS_USER_READ,
    PRIVATE_ORDERS_POLICY,
    REVOKE_SESSION,
    ContextError,
    PatchManifestError,
    detect_suspicious_access,
    load_patch_manifest,
    observe,
    parse_context,
    parse_patch_manifest,
    propose_ownership_patch,
    propose_session_revocations,
)
from app.agents.blue.detection import parse_utc_timestamp
from app.agents.blue.proposals import revocation_id
from blue_test_helpers import ROOT, log, secret_keys

GENERATED_AT = "2026-09-30T16:00:00Z"
POLICY = {"id": "private-orders-owner-only", "owner_only_actions": ["read_private_order"]}
MANIFEST_PATH = ROOT / "defenses/patches/ownership-fix-001/manifest.json"


def context(telemetry, **overrides):
    base = {"target_id": "storefront-lab", "target_version": "lab-v1", "data_source": "live",
            "telemetry": telemetry, "access_policy": POLICY, "previous_defenses": [],
            "budgets": {"max_steps": 5, "max_requests": 10, "timeout_seconds": 30},
            "assessment_id": "run-1", "generated_at": GENERATED_AT}
    base.update(overrides)
    return base


def run(ctx):
    return asyncio.run(observe(ctx))


def detect(*records):
    return detect_suspicious_access(list(records), PRIVATE_ORDERS_POLICY)


def event(kind, data, event_id=1, second=10, **envelope):
    actor = "blue" if kind == "defense.proposed" else "system"
    base = {"schema_version": "1.0", "id": event_id, "assessment_id": "run-1", "type": kind, "actor": actor,
            "timestamp": f"2026-09-30T15:01:{second:02d}Z", "target_id": "storefront-lab", "target_version": "lab-v1",
            "data_source": "live", "evidence_refs": [], "data": data}
    base.update(envelope)
    return base


def proposed(session="alice-session-1", defense_id=None, event_id=1, **envelope):
    return event("defense.proposed", {"defense_id": defense_id or f"d-{session}", "action_type": REVOKE_SESSION,
                 "summary": "Revoke.", "reason": "Contain.", "parameters": {"session_ref": session}}, event_id, **envelope)


def applied(defense_id="d-alice-session-1", event_id=3, second=10, **envelope):
    data = envelope.pop("data", None) or {"defense_id": defense_id, "action_type": REVOKE_SESSION, "origin": "policy_action",
                                          "original_version": "lab-v1", "resulting_version": "lab-v1"}
    return event("defense.applied", data, event_id, second, **envelope)


def manifest_data():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def without_skipped(result):
    return json.dumps({k: v for k, v in result.items() if k != "skipped"}, sort_keys=True)


class IdentityConfusion(unittest.TestCase):
    LOOKALIKES = ("Bob", "bob ", " bob", "b\u043eb", "bo\u0301b", "bob\x00", "\u00a0", " ")

    def test_lookalike_actor_is_never_treated_as_the_owner(self):
        # Identity refs are opaque. Only a byte-identical actor_ref is the owner; anything else is another user.
        self.assertEqual(detect(log("r1", "bob", "bob")).alerts, ())
        for actor in self.LOOKALIKES:
            with self.subTest(actor=actor):
                result = detect(log("r1", actor, "bob"))
                self.assertEqual([a.kind for a in result.alerts], [CROSS_USER_READ])
                self.assertEqual(result.skipped, ())

    def test_lookalike_owner_never_authorizes_the_read(self):
        for owner in ("Bob", "bob ", "b\u043eb"):
            with self.subTest(owner=owner):
                self.assertEqual([a.kind for a in detect(log("r1", "bob", owner)).alerts], [CROSS_USER_READ])

    def test_empty_identity_strings_are_skipped_not_classified(self):
        # "" is neither anonymous (null) nor an identity; the record cannot be evaluated.
        cases = {"actor_ref": log("r1", "", "bob"), "resource_owner_ref": log("r2", "alice", ""),
                 "session_ref": {**log("r3", "alice", "bob"), "session_ref": ""}}
        result = detect(*cases.values())
        self.assertEqual(result.alerts, ())
        self.assertEqual([s.reason for s in result.skipped], [f"{name} must be a non-empty string or null" for name in cases])

    def test_observe_revokes_the_lookalike_session_and_proposes_the_patch(self):
        r = run(context([log("r1", "Bob", "bob")]))
        self.assertEqual([a["kind"] for a in r["alerts"]], [CROSS_USER_READ])
        self.assertEqual([p["action_type"] for p in r["defense_proposals"]], ["revoke_session", "apply_patch"])
        self.assertEqual(r["defense_proposals"][0]["parameters"], {"session_ref": "Bob-session-1"})

    def test_action_and_policy_names_match_exactly(self):
        # A differently spelled action is another action: not alerted, and not skipped either.
        for action in ("Read_Private_Order", "read_private_order ", "read_private_orders"):
            with self.subTest(action=action):
                result = detect(log("r1", "alice", "bob", action=action))
                self.assertEqual((result.alerts, result.skipped), ((), ()))
        r = run(context([log("r1", "alice", "bob")], access_policy={"id": "p", "owner_only_actions": ["READ_PRIVATE_ORDER"]}))
        self.assertEqual(r["alerts"], [])


class RequestIdsAndTimestamps(unittest.TestCase):
    def test_request_ids_follow_time_then_id_whatever_the_input_order(self):
        records = [log("r3", "alice", "bob", second=9), log("r1", "alice", "bob", second=4), log("r2", "alice", "bob", second=4)]
        for seed in range(4):
            random.Random(seed).shuffle(records)
            with self.subTest(order=[r["request_id"] for r in records]):
                alert = detect(*records).alerts[0]
                self.assertEqual(alert.request_ids, ("r1", "r2", "r3"))
                self.assertEqual((alert.first_seen, alert.last_seen), ("2026-09-30T15:00:04Z", "2026-09-30T15:00:09Z"))

    def test_equal_timestamps_order_by_request_id(self):
        alert = detect(log("r2", "alice", "bob"), log("r10", "alice", "bob"), log("r1", "alice", "bob")).alerts[0]
        self.assertEqual(alert.request_ids, ("r1", "r10", "r2"))
        self.assertEqual(alert.first_seen, alert.last_seen)

    def test_non_utc_or_padded_timestamps_are_skipped(self):
        bad = ("2026-09-30T15:00:04+00:00", "2026-09-30T15:00:04z", " 2026-09-30T15:00:04Z", "Z",
               "2026-09-30T23:59:60Z", "10000-01-01T00:00:00Z", "2026-09-30T15:00:04+00:00Z", "2026-09-30T15:00:04Z ")
        for stamp in bad:
            with self.subTest(stamp=stamp):
                self.assertIsNone(parse_utc_timestamp(stamp))
                result = detect({**log("r1", "alice", "bob"), "timestamp": stamp})
                self.assertEqual(result.alerts, ())
                self.assertEqual([s.reason for s in result.skipped], ["timestamp must be ISO 8601 UTC ending in Z"])

    def test_fractional_seconds_order_correctly(self):
        late = {**log("r1", "alice", "bob"), "timestamp": "2026-09-30T15:00:04.500Z"}
        early = {**log("r2", "alice", "bob"), "timestamp": "2026-09-30T15:00:04.250Z"}
        self.assertEqual(detect(late, early).alerts[0].request_ids, ("r2", "r1"))

    @unittest.expectedFailure
    def test_date_only_timestamp_is_rejected_not_parsed_as_naive(self):
        # BUG (medium): detection.parse_utc_timestamp (detection.py:159) builds "2026-09-30+00:00" from
        # "2026-09-30Z" and datetime.fromisoformat returns a NAIVE datetime. The record passes record_problem,
        # then every comparison with an aware timestamp raises TypeError: sorted() in
        # detect_suspicious_access (detection.py:91), observe._containment (observe.py:373), and
        # incident._seconds_between (incident.py:362). One record with a date-only timestamp crashes blue.
        # Correct: the value is not an ISO 8601 UTC timestamp, so parse returns None and the record is skipped.
        self.assertIsNone(parse_utc_timestamp("2026-09-30Z"))

    @unittest.expectedFailure
    def test_date_only_timestamp_record_is_skipped_and_the_rest_still_alert(self):
        # BUG (medium): same root cause as above. Input: one valid cross-user read plus one record whose
        # timestamp is "2026-09-30Z". Today detect_suspicious_access raises TypeError instead of skipping r2.
        result = detect(log("r1", "alice", "bob"), {**log("r2", "alice", "bob"), "timestamp": "2026-09-30Z"})
        self.assertEqual([a.request_ids for a in result.alerts], [("r1",)])
        self.assertEqual([s.request_id for s in result.skipped], ["r2"])

    @unittest.expectedFailure
    def test_observe_survives_a_date_only_timestamp(self):
        # BUG (medium): same root cause. observe() must complete and list r2 under skipped; today it raises
        # TypeError from the detector sort (two records) or from the report's elapsed-time math (one record).
        for telemetry in ([log("r1", "alice", "bob"), {**log("r2", "alice", "bob"), "timestamp": "2026-09-30Z"}],
                          [{**log("r2", "alice", "bob"), "timestamp": "2026-09-30Z"}]):
            with self.subTest(records=len(telemetry)):
                r = run(context(telemetry))
                self.assertEqual(r["status"], "completed")
                self.assertIn("r2", [s["request_id"] for s in r["skipped"]])

    @unittest.expectedFailure
    def test_date_only_generated_at_is_a_context_error(self):
        # BUG (medium): same root cause. generated_at="2026-09-30Z" passes parse_context (observe.py:90) and
        # then incident._seconds_between raises TypeError. Correct: ContextError before any work.
        with self.assertRaises(ContextError):
            run(context([log("r1", "alice", "bob")], generated_at="2026-09-30Z"))


class NumericEdgeCases(unittest.TestCase):
    def test_status_boundaries(self):
        expected = {199: 0, 200: 1, 299: 1, 300: 0, 0: 0, -200: 0, 2**70: 0}
        for status, alerts in expected.items():
            with self.subTest(status=status):
                result = detect(log("r1", "alice", "bob", status))
                self.assertEqual((len(result.alerts), result.skipped), (alerts, ()))

    def test_non_integer_statuses_are_skipped_through_observe(self):
        for status in (200.0, float("nan"), 2e2, True, None, "200"):
            with self.subTest(status=status):
                r = run(context([log("r1", "alice", "bob", status)]))
                self.assertEqual(r["alerts"], [])
                self.assertEqual(len(r["skipped"]), 1)
                self.assertIn("http_status", r["skipped"][0]["reason"])

    def test_budget_edges(self):
        for budgets in ({"max_steps": True}, {"timeout_seconds": False}, {"max_steps": "5"}, {"max_steps": None},
                        {"max_steps": [5]}, {"max_steps": 5, "extra": 1}):
            with self.subTest(budgets=budgets), self.assertRaises(ContextError):
                run(context([], budgets=budgets))
        for budgets in ({"timeout_seconds": float("-inf")}, {"max_steps": -0.0}, {"max_steps": -(2**70)}):
            with self.subTest(budgets=budgets):
                self.assertEqual(run(context([log("r1", "alice", "bob")], budgets=budgets))["status"], "budget_exhausted")
        for budgets in ({"max_steps": float("inf")}, {"max_steps": 2**70}, {"max_steps": 1e-9},
                        {"max_requests": -1}):  # max_requests is documented as unchecked: observe sends no requests
            with self.subTest(budgets=budgets):
                self.assertEqual(run(context([log("r1", "alice", "bob")], budgets=budgets))["status"], "completed")

    @unittest.expectedFailure
    def test_nan_budget_fails_closed(self):
        # BUG (low): observe._budgets (observe.py:267) accepts any float and the exhaustion test
        # `ctx.budgets[key] <= 0` (observe.py:115) is False for NaN, so {"max_steps": nan} runs a full
        # observation with status "completed". Correct: reject it (ContextError) or treat it as exhausted.
        for budgets in ({"max_steps": float("nan")}, {"timeout_seconds": float("nan")}):
            with self.subTest(budgets=budgets):
                try:
                    r = run(context([log("r1", "alice", "bob")], budgets=budgets))
                except ContextError:
                    continue
                self.assertNotEqual(r["status"], "completed")


class OversizedAndNested(unittest.TestCase):
    def test_huge_identifier_strings_do_not_crash_and_stay_json_ready(self):
        big = "a" * 100_000
        r = run(context([log("r1", big, "bob", session=big + "-s")]))
        self.assertEqual(len(r["alerts"]), 1)
        self.assertEqual(r["defense_proposals"][0]["parameters"], {"session_ref": big + "-s"})
        json.dumps(r)

    def test_deeply_nested_extra_fields_are_dropped_without_recursion(self):
        deep = {"ground_truth": "DEEP-MARKER"}
        for _ in range(300):
            deep = {"nested": [deep]}
        record = {**log("r1", "alice", "bob"), "detail": deep}
        broken = {**log("r2", "alice", "bob", second=2), "resource_owner_ref": deep}
        r = run(context([record, broken]))
        self.assertEqual([a["request_ids"] for a in r["alerts"]], [["r1"]])
        self.assertEqual(r["skipped"], [{"request_id": "r2", "reason": "missing resource_owner_ref"}])
        self.assertNotIn("DEEP-MARKER", json.dumps(r))

    def test_ten_thousand_records_complete_and_one_more_is_never_silently_truncated(self):
        records = [log(f"o{i}", "bob", "bob", second=i % 60) for i in range(9_999)] + [log("x", "alice", "bob")]
        r = run(context(records))
        self.assertEqual((r["status"], len(r["alerts"]), r["skipped"]), ("completed", 1, []))
        try:
            r = run(context(records + [log("y", "bob", "bob")]))
        except ContextError:
            return
        self.assertNotEqual(r["status"], "completed")

    def test_oversized_identifiers_in_previous_defenses_are_rejected(self):
        ok, too_long = "x" * 128, "x" * 129
        self.assertEqual(run(context([log("r1", "alice", "bob")], previous_defenses=[
            applied(defense_id=ok, evidence_refs=[ok], id=ok)]))["status"], "completed")
        for entry in (applied(defense_id=too_long), applied(evidence_refs=[too_long]), applied(id=too_long),
                      applied(assessment_id=too_long), applied(target_version=too_long)):
            with self.subTest(entry=entry), self.assertRaises(ContextError):
                run(context([log("r1", "alice", "bob")], previous_defenses=[entry]))


class CrossScopeMixing(unittest.TestCase):
    def test_case_variant_scope_labels_on_records_are_out_of_scope(self):
        variants = {"target_id": "Storefront-Lab", "target_version": "LAB-V1", "assessment_id": "RUN-1",
                    "data_source": "Live"}
        records = [{**log(f"r{i}", "alice", "bob"), field: value} for i, (field, value) in enumerate(variants.items())]
        r = run(context(records))
        self.assertEqual((r["alerts"], r["defense_proposals"], r["report"]), ([], [], None))
        self.assertEqual([s["reason"] for s in r["skipped"]], [f"{field} does not match the context" for field in variants])

    def test_non_string_scope_labels_on_records_are_skipped(self):
        records = [{**log("r1", "alice", "bob"), "target_id": 123}, {**log("r2", "alice", "bob"), "target_version": None},
                   {**log("r3", "alice", "bob"), "target_id": ["storefront-lab"]},
                   {**log("r4", "alice", "bob"), "assessment_id": None}, {**log("r5", "alice", "bob"), "data_source": None}]
        r = run(context(records))
        self.assertEqual(r["alerts"], [])
        self.assertEqual([s["request_id"] for s in r["skipped"]], ["r1", "r2", "r3", "r4", "r5"])
        # A list-typed target_id is dropped by the scalar projection, so that record is "missing target_id".
        self.assertEqual([s["reason"] for s in r["skipped"]],
                         ["target_id must be a non-empty string", "target_version must be a non-empty string",
                          "missing target_id", "assessment_id does not match the context",
                          "data_source does not match the context"])

    def test_mixed_batch_counts_only_this_scope(self):
        inside = [log(f"in{i}", "alice", "bob", second=i) for i in range(3)]
        outside = [{**log(f"out{i}", "alice", "bob", second=i), "assessment_id": "run-2"} for i in range(3)]
        outside += [log("v2", "alice", "bob", version="lab-v2"), {**log("t2", "alice", "bob"), "target_id": "other-lab"}]
        r = run(context(outside + inside))
        self.assertEqual([a["request_ids"] for a in r["alerts"]], [["in0", "in1", "in2"]])
        self.assertEqual(r["evidence_refs"], ["telemetry:in0", "telemetry:in1", "telemetry:in2"])
        self.assertEqual(len(r["skipped"]), 5)
        self.assertEqual({e["reference"] for e in r["report"]["evidence"] if e["kind"] == "telemetry"}, {"in0", "in1", "in2"})

    def test_case_variant_scope_on_defense_events_never_credits_containment(self):
        for envelope in ({"target_id": "Storefront-Lab"}, {"assessment_id": "RUN-1"}):
            with self.subTest(envelope=envelope):
                defenses = [proposed(**envelope), applied(**envelope)]
                r = run(context([log("r1", "alice", "bob")], previous_defenses=defenses))
                self.assertIsNone(r["report"]["times"]["contained"])
                self.assertEqual(r["report"]["status"], "open")
                self.assertIn("were left out", " ".join(r["notes"]))
                self.assertIn(REVOKE_SESSION, [p["action_type"] for p in r["defense_proposals"]])
        # An applied event whose own version and data versions are all "LAB-V1" concerns another version.
        other_version = applied(target_version="LAB-V1", data={"defense_id": "d-alice-session-1", "action_type": REVOKE_SESSION,
                                "origin": "policy_action", "original_version": "LAB-V1", "resulting_version": "LAB-V1"})
        r = run(context([log("r1", "alice", "bob")], previous_defenses=[proposed(), other_version]))
        self.assertIsNone(r["report"]["times"]["contained"])
        self.assertIn("another target version", " ".join(r["notes"]))
        with self.assertRaises(ContextError):
            run(context([log("r1", "alice", "bob")], previous_defenses=[applied(data_source="Live")]))


class ForgedPreviousDefenses(unittest.TestCase):
    def test_wrong_actor_is_rejected(self):
        for maker in (proposed, applied):
            for actor in ("red", "referee", None, "", "Blue", "System", "blue ", "system "):
                with self.subTest(kind=maker.__name__, actor=actor), self.assertRaises(ContextError):
                    run(context([log("r1", "alice", "bob")], previous_defenses=[maker(actor=actor)]))

    def test_disguised_event_types_are_rejected(self):
        payload = {"defense_id": "d-1", "reason": "x"}
        for kind, actor in (("Defense.Applied", "system"), ("defense.applied ", "system"), ("retest.completed", "system"),
                            ("finding.verified", "system"), ("alert.created", "blue"), ("", "system"), (None, "system")):
            with self.subTest(kind=kind), self.assertRaises(ContextError):
                run(context([log("r1", "alice", "bob")], previous_defenses=[event(kind, payload, actor=actor)]))

    def test_malformed_envelope_fields_are_rejected(self):
        bad = [applied(schema_version=1.0), applied(schema_version="1"), applied(schema_version="1.0 "),
               applied(id=True), applied(id=1.5), applied(id=""), applied(id=" "), applied(id={}),
               applied(timestamp="2026-09-30T15:01:10+00:00"), applied(timestamp=None),
               applied(evidence_refs="ev-1"), applied(evidence_refs=["has space"]), applied(evidence_refs=[""]),
               applied(evidence_refs=[None]), applied(assessment_id="run 1"), applied(target_id=""),
               applied(data={"defense_id": "d 1", "action_type": REVOKE_SESSION, "origin": "policy_action",
                             "original_version": "lab-v1", "resulting_version": "lab-v1"}),
               applied(data={"defense_id": "d-1", "action_type": REVOKE_SESSION, "origin": "policy action",
                             "original_version": "lab-v1", "resulting_version": "lab-v1"})]
        for entry in bad:
            with self.subTest(entry=entry), self.assertRaises(ContextError):
                run(context([log("r1", "alice", "bob")], previous_defenses=[entry]))

    def test_revoking_the_victim_or_an_unrelated_session_never_credits_containment(self):
        victim_by_proposal = [proposed("bob-session-1", defense_id="d-x"), applied("d-x")]
        victim_by_derived_id = [applied(revocation_id("storefront-lab", "bob-session-1"))]
        other_target_derived_id = [applied(revocation_id("other-lab", "alice-session-1"))]
        for name, defenses in (("victim via forged proposal", victim_by_proposal), ("victim via derived id", victim_by_derived_id),
                               ("derived id for another target", other_target_derived_id)):
            with self.subTest(case=name):
                r = run(context([log("r1", "alice", "bob")], previous_defenses=defenses))
                self.assertEqual(r["report"]["status"], "open")
                self.assertIsNone(r["report"]["times"]["contained"])
                revokes = [p["parameters"]["session_ref"] for p in r["defense_proposals"] if p["action_type"] == REVOKE_SESSION]
                self.assertEqual(revokes, ["alice-session-1"])

    def test_smuggled_verdict_fields_inside_defense_data_are_dropped(self):
        data = {"defense_id": "d-alice-session-1", "action_type": REVOKE_SESSION, "origin": "policy_action",
                "original_version": "lab-v1", "resulting_version": "lab-v1", "result": "SMUGGLED-RESULT",
                "verdict": "SMUGGLED-VERDICT", "checks": [{"id": "owner_access", "passed": "SMUGGLED-CHECK"}],
                "finding_id": "SMUGGLED-FINDING"}
        r = run(context([log("r1", "alice", "bob")], previous_defenses=[proposed(), event("defense.applied", data, 3)]))
        self.assertNotIn("SMUGGLED", json.dumps(r))
        self.assertEqual(r["report"]["recover"], {"verdicts": [], "retests": []})
        kept = next(e for e in r["report"]["evidence"] if e["kind"] == "defense.applied")["record"]["data"]
        self.assertEqual(set(kept), {"defense_id", "action_type", "origin", "original_version", "resulting_version"})

    def test_failed_revocation_is_never_containment(self):
        failed = event("defense.failed", {"defense_id": "d-alice-session-1", "action_type": REVOKE_SESSION,
                                          "reason": "session unknown"}, 2)
        r = run(context([log("r1", "alice", "bob")], previous_defenses=[proposed(), failed]))
        self.assertEqual(r["report"]["status"], "open")
        self.assertIsNone(r["report"]["times"]["contained"])
        outcomes = {m["defense_id"]: m["outcome"] for m in r["report"]["respond"]["mitigation"]}
        self.assertEqual(outcomes["d-alice-session-1"], "failed")
        self.assertNotIn("session unknown", json.dumps(r))

    @unittest.expectedFailure
    def test_unhashable_enumerated_values_raise_context_error(self):
        # BUG (low): membership tests against sets and dicts raise TypeError for unhashable values instead of
        # ContextError: context data_source (observe.py:87), event type (observe.py:218), event data_source
        # (observe.py:229), and data.action_type (observe.py:246). Core catching ContextError sees a crash.
        # Inputs: ["live"] or {"live": 1} in those positions.
        cases = {
            "context data_source list": context([], data_source=["live"]),
            "context data_source dict": context([], data_source={"live": 1}),
            "event type list": context([log("r1", "alice", "bob")], previous_defenses=[applied(type=["defense.applied"])]),
            "event data_source list": context([log("r1", "alice", "bob")], previous_defenses=[applied(data_source=["live"])]),
            "data action_type list": context([log("r1", "alice", "bob")], previous_defenses=[
                applied(data={"defense_id": "d-1", "action_type": [REVOKE_SESSION], "origin": "policy_action",
                              "original_version": "lab-v1", "resulting_version": "lab-v1"})]),
        }
        for name, ctx in cases.items():
            with self.subTest(case=name), self.assertRaises(ContextError):
                run(ctx)


class SmuggledContextKeys(unittest.TestCase):
    def test_unknown_keys_are_rejected_by_exact_name(self):
        for key in ("red_candidates", "referee_verdicts", "Telemetry", "TELEMETRY", "telemetry ", "access-policy", 0, None, ""):
            with self.subTest(key=key), self.assertRaises(ContextError) as caught:
                run(context([], **{key: "x"}) if isinstance(key, str) else {**context([]), key: "x"})
            self.assertIn("may not receive", str(caught.exception))
            self.assertIn(str(key), str(caught.exception))

    def test_rejection_messages_never_echo_values(self):
        hostile = {"red_plan": "VALUE-MARKER", "telemetry": "VALUE-MARKER", "data_source": "VALUE-MARKER",
                   "target_id": ["VALUE-MARKER"], "access_policy": {"id": "VALUE-MARKER", "owner_only_actions": []},
                   "budgets": {"max_steps": "VALUE-MARKER"}, "generated_at": "VALUE-MARKER",
                   "previous_defenses": [{"type": "VALUE-MARKER"}]}
        for key, value in hostile.items():
            with self.subTest(key=key):
                with self.assertRaises(ContextError) as caught:
                    run({**context([log("r1", "alice", "bob")]), key: value})
                self.assertNotIn("VALUE-MARKER", str(caught.exception))

    def test_null_optional_containers_fail_closed(self):
        # Core must send [] and {}, not null: a null container is malformed, not "nothing".
        for key in ("previous_defenses", "budgets", "telemetry"):
            with self.subTest(key=key), self.assertRaises(ContextError):
                run({**context([]), key: None})


class SecretBearingTelemetry(unittest.TestCase):
    def test_secret_values_in_unlisted_fields_never_reach_the_output(self):
        # Field names that avoid every marker word still never leak, because projection keeps contract fields only.
        extras = {"pwd": "SEC-1", "jwt": "SEC-2", "bearer": "SEC-3", "credential": "SEC-4", "x_session_id": "SEC-5",
                  "hdr": {"Set-Cookie": "SEC-6"}, "args": ["SEC-7"]}
        r = run(context([{**log("r1", "alice", "bob"), **extras}, {**log("r2", "bob", "bob", second=2), **extras}]))
        text = json.dumps(r)
        for i in range(1, 8):
            self.assertNotIn(f"SEC-{i}", text)
        self.assertEqual(secret_keys(r), set())
        self.assertEqual(len(r["alerts"]), 1)

    def test_secret_values_in_wrong_typed_contract_fields_are_dropped(self):
        records = [{**log("r1", "alice", "bob"), "session_ref": {"token": "SEC-A"}},
                   {**log("r2", "alice", "bob"), "http_status": "Bearer SEC-B"},
                   {**log("r3", "alice", "bob"), "request_id": ["SEC-C"]}]
        r = run(context(records))
        self.assertEqual(r["alerts"], [])
        self.assertEqual(len(r["skipped"]), 3)
        text = json.dumps(r)
        for marker in ("SEC-A", "SEC-B", "SEC-C"):
            self.assertNotIn(marker, text)

    def test_skip_reasons_name_fields_never_values(self):
        marked = {field: "VAL-MARKER" for field in ("request_id", "timestamp", "target_id", "target_version", "actor_ref",
                                                     "session_ref", "resource_id", "resource_owner_ref", "action")}
        r = run(context([{**marked, "http_status": "VAL-MARKER"}, {**log("r1", "alice", "bob"), "timestamp": "VAL-MARKER"}]))
        self.assertEqual(r["alerts"], [])
        for skip in r["skipped"]:
            self.assertNotIn("VAL-MARKER", skip["reason"])

    def test_secrets_in_forged_defense_parameters_and_envelopes_never_reach_the_output(self):
        forged = proposed()
        forged["data"]["parameters"].update(token="SEC-P1", Authorization="Bearer SEC-P2", note="SEC-P3")
        forged["cookie"] = "SEC-E1"
        done = applied()
        done["data"]["api_key"] = "SEC-D1"
        done["evidence_refs"] = ["ev-1"]
        failed = event("defense.failed", {"defense_id": "d-2", "reason": "password=SEC-F1", "password": "SEC-F2"}, 4)
        r = run(context([log("r1", "alice", "bob")], previous_defenses=[forged, done, failed]))
        text = json.dumps(r)
        for marker in ("SEC-P1", "SEC-P2", "SEC-P3", "SEC-E1", "SEC-D1", "SEC-F1", "SEC-F2"):
            self.assertNotIn(marker, text)
        self.assertEqual(secret_keys(r), set())


class Determinism(unittest.TestCase):
    RECORDS = [log("r1", "alice", "bob", second=1), log("r2", "alice", "bob", second=1),
               log("r3", "mallory", "alice", second=1, resource="order-101"), log("r4", None, "bob", second=2),
               {**log("r5", "alice", "bob"), "http_status": "200"}, {**log("r6", "alice", "bob"), "target_id": "other"},
               log("r7", "bob", "bob", second=3), log("r8", "alice", "bob", second=0, session="alice-session-2")]
    DEFENSES = [proposed(), applied(second=10), proposed("alice-session-2", event_id=5),
                event("defense.failed", {"defense_id": "d-alice-session-2", "reason": "x"}, 6)]

    def test_shuffled_input_gives_identical_output(self):
        baseline = run(context(self.RECORDS, previous_defenses=self.DEFENSES))
        for seed in range(6):
            records, defenses = list(self.RECORDS), list(self.DEFENSES)
            random.Random(seed).shuffle(records)
            random.Random(seed).shuffle(defenses)
            with self.subTest(seed=seed):
                r = run(context(records, previous_defenses=defenses))
                self.assertEqual(without_skipped(r), without_skipped(baseline))
                self.assertEqual(sorted(json.dumps(s, sort_keys=True) for s in r["skipped"]),
                                 sorted(json.dumps(s, sort_keys=True) for s in baseline["skipped"]))

    def test_observe_twice_is_identical(self):
        ctx = context(self.RECORDS, previous_defenses=self.DEFENSES)
        first, second = run(ctx), run(ctx)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(first["report"]["integrity"], second["report"]["integrity"])

    def test_detection_and_proposals_are_order_independent(self):
        records = [r for r in self.RECORDS if r["request_id"] not in ("r5", "r6")]
        baseline = detect(*records)
        for seed in range(4):
            shuffled = list(records)
            random.Random(seed).shuffle(shuffled)
            result = detect(*shuffled)
            self.assertEqual(result.alerts, baseline.alerts)
            self.assertEqual(propose_session_revocations(result.alerts), propose_session_revocations(baseline.alerts))


class Idempotency(unittest.TestCase):
    def test_feeding_back_own_proposals_and_outcomes_yields_no_new_proposals(self):
        first = run(context([log("r1", "alice", "bob")]))
        revoke_id = next(p["defense_id"] for p in first["defense_proposals"] if p["action_type"] == REVOKE_SESSION)
        fed_back = [event("defense.proposed", p, i) for i, p in enumerate(first["defense_proposals"], 1)]
        fed_back.append(applied(revoke_id, event_id=9, second=30))
        second = run(context([log("r1", "alice", "bob")], previous_defenses=fed_back))
        self.assertEqual(second["defense_proposals"], [])
        self.assertEqual(second["alerts"], first["alerts"])
        self.assertEqual(second["evidence_refs"], first["evidence_refs"])
        self.assertEqual(second["report"]["status"], "contained")

    def test_parse_context_is_pure(self):
        ctx = context([log("r1", "alice", "bob")], previous_defenses=[proposed(), applied()])
        before = json.dumps(ctx, sort_keys=True)
        self.assertEqual(parse_context(ctx), parse_context(ctx))
        self.assertEqual(json.dumps(ctx, sort_keys=True), before)

    def test_repeated_proposal_from_previous_object_is_not_duplicated(self):
        alerts = detect(log("r1", "alice", "bob")).alerts
        once = propose_session_revocations(alerts)
        self.assertEqual(propose_session_revocations(alerts, once), ())
        self.assertEqual(propose_session_revocations(alerts, once + once), ())


class PatchManifestHostileInput(unittest.TestCase):
    def test_patch_id_tricks_are_rejected_by_the_loader(self):
        for patch_id in ("", "OWNERSHIP-FIX-001", "ownership-fix-001\x00", "ownership-fix-001/..", "ownership fix",
                         "a" * 65, ".", "-fix", "ownership-fix-001\n"):
            with self.subTest(patch_id=patch_id), self.assertRaises(PatchManifestError):
                load_patch_manifest(patch_id)

    def test_path_tricks_in_file_scope_are_rejected(self):
        for bad in ("C:\\lab\\app.py", "c:/lab/app.py", "\\\\server\\share\\app.py", "//server/share/app.py", "/app.py",
                    "lab/../app.py", "../app.py", "http://host/app.py", "", "lab/..", ".."):
            with self.subTest(path=bad), self.assertRaises(PatchManifestError):
                parse_patch_manifest({**manifest_data(), "allowed_files": [bad]})
        for bad in ("", "a/b.diff", "../fix.diff", "/fix.diff", "C:fix.diff", "fix\\x.diff"):
            with self.subTest(diff=bad), self.assertRaises(PatchManifestError):
                parse_patch_manifest({**manifest_data(), "diff_file": bad})
        manifest = parse_patch_manifest({**manifest_data(), "allowed_files": ["lab/./app.py", "lab//app.py"]})
        self.assertEqual(manifest.allowed_files, ("lab/./app.py", "lab//app.py"))

    def test_ready_status_rejects_empty_scope_values(self):
        for overrides in ({"status": "ready", "allowed_files": [""], "diff_file": "fix.diff"},
                          {"status": "ready", "allowed_files": ["lab/app.py"], "diff_file": ""},
                          {"status": "ready", "allowed_files": [], "diff_file": "fix.diff"},
                          {"status": "ready", "allowed_files": ["lab/app.py"], "diff_file": None}):
            with self.subTest(overrides=overrides), self.assertRaises(PatchManifestError):
                parse_patch_manifest({**manifest_data(), **overrides})

    def test_check_ids_are_compared_as_strings(self):
        data = manifest_data()
        extra = [{"id": 1, "description": "x", "expected": "denied"}, {"id": "1", "description": "y", "expected": "allowed"}]
        with self.assertRaisesRegex(PatchManifestError, "unique"):
            parse_patch_manifest({**data, "regression_checks": data["regression_checks"] + extra})
        manifest = parse_patch_manifest({**data, "regression_checks": data["regression_checks"] + extra[:1]})
        self.assertEqual(manifest.regression_checks[-1].id, "1")

    def test_wrong_types_in_manifest_fields_are_rejected(self):
        for field, value in (("patch_id", 1), ("title", ["t"]), ("base_version", " "), ("allowed_files", "lab/app.py"),
                             ("allowed_files", [1]), ("regression_checks", {}), ("regression_checks", []),
                             ("regression_checks", ["unauthorized_access"]), ("status", None), ("origin", 1)):
            with self.subTest(field=field, value=value), self.assertRaises(PatchManifestError):
                parse_patch_manifest({**manifest_data(), field: value})
        with self.assertRaises(PatchManifestError):
            parse_patch_manifest(["not", "an", "object"])

    @unittest.expectedFailure
    def test_unhashable_manifest_values_raise_manifest_error(self):
        # BUG (low): set membership raises TypeError for unhashable values instead of PatchManifestError:
        # status (patches.py:77), origin (patches.py:78), and a check's expected (patches.py:96).
        # Inputs: ["draft"], ["generated"], and expected ["denied"].
        data = manifest_data()
        checks = [{**data["regression_checks"][0], "expected": ["denied"]}] + data["regression_checks"][1:]
        for overrides in ({"status": ["draft"]}, {"origin": ["generated"]}, {"regression_checks": checks}):
            with self.subTest(overrides=overrides), self.assertRaises(PatchManifestError):
                parse_patch_manifest({**data, **overrides})

    def test_ownership_patch_needs_an_exact_version_match(self):
        manifest = load_patch_manifest("ownership-fix-001")
        for version in ("LAB-V1", "lab-v1 ", "lab-v1\x00", "lab-v10"):
            with self.subTest(version=version):
                alerts = detect(log("r1", "alice", "bob", version=version)).alerts
                self.assertIsNone(propose_ownership_patch(alerts, manifest, version))
        self.assertIsNotNone(propose_ownership_patch(detect(log("r1", "alice", "bob")).alerts, manifest, "lab-v1"))


class ProposalsHostileInput(unittest.TestCase):
    def test_session_ref_variants_in_previous_defenses_do_not_count_as_handled(self):
        for handled in ("Alice-Session-1", " alice-session-1", "alice-session-1 ", "alice-session-10"):
            with self.subTest(handled=handled):
                previous = [{"action_type": REVOKE_SESSION, "parameters": {"session_ref": handled}}]
                proposals = propose_session_revocations(detect(log("r1", "alice", "bob")).alerts, previous)
                self.assertEqual([p.parameters["session_ref"] for p in proposals], ["alice-session-1"])

    def test_wrong_typed_previous_parameters_are_ignored_not_trusted(self):
        previous = [{"action_type": REVOKE_SESSION, "parameters": {"session_ref": ["alice-session-1"]}},
                    {"action_type": REVOKE_SESSION, "parameters": {"session_ref": None}},
                    {"action_type": REVOKE_SESSION, "parameters": None},
                    {"action_type": [REVOKE_SESSION], "parameters": {"session_ref": "alice-session-1"}},
                    {"action_type": "apply_patch", "parameters": {"patch_id": ["ownership-fix-001"]}}]
        alerts = detect(log("r1", "alice", "bob")).alerts
        self.assertEqual([p.parameters["session_ref"] for p in propose_session_revocations(alerts, previous)], ["alice-session-1"])
        manifest = load_patch_manifest("ownership-fix-001")
        self.assertIsNotNone(propose_ownership_patch(alerts, manifest, "lab-v1", previous))

    def test_shared_session_across_actors_gets_one_revocation_covering_both_alerts(self):
        result = detect(log("r1", "alice", "bob", session="shared-1"),
                        log("r2", "mallory", "alice", second=2, session="shared-1", resource="order-101"))
        self.assertEqual(len(result.alerts), 2)
        proposals = propose_session_revocations(result.alerts)
        self.assertEqual([p.parameters["session_ref"] for p in proposals], ["shared-1"])
        self.assertEqual(set(proposals[0].alert_ids), {a.alert_id for a in result.alerts})

    def test_revocation_is_never_proposed_for_the_victim_or_for_anonymous_reads(self):
        result = detect(log("r1", "alice", "bob"), log("r2", "bob", "bob", second=2), log("r3", None, "bob", second=3))
        proposals = propose_session_revocations(result.alerts)
        self.assertEqual([p.parameters["session_ref"] for p in proposals], ["alice-session-1"])


if __name__ == "__main__":
    unittest.main()
