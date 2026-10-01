"""Blue observe(context, tools) entry-point tests. Run from backend/: python -m unittest discover -s tests/blue -v"""

import asyncio
import importlib
import json
import unittest
from unittest import mock

from app.agents.blue import (
    CONTAINMENT,
    OBSERVE_SCHEMA,
    PRIVATE_ORDERS_POLICY,
    REMEDIATION,
    ContextError,
    DefenseProposal,
    PatchManifestError,
    observe,
)
from app.agents.blue.detection import TELEMETRY_FIELDS
from blue_test_helpers import load_shared, log, secret_keys

# The package exports the function under the same name, so fetch the module itself for patching.
observe_module = importlib.import_module("app.agents.blue.observe")

GENERATED_AT = "2026-09-30T16:00:00Z"
POLICY = {"id": "private-orders-owner-only", "owner_only_actions": ["read_private_order"]}


class InertTools:
    """Fake tools: answers cancellation and time, fails if blue tries anything else."""

    def __init__(self, cancelled=False, now=GENERATED_AT):
        self._cancelled, self._now = cancelled, now

    def cancelled(self):
        return self._cancelled

    def now(self):
        return self._now

    def __getattr__(self, name):
        raise AssertionError(f"observe must not use tools.{name} in M1")


def context(telemetry, **overrides):
    base = {"target_id": "storefront-lab", "target_version": "lab-v1", "data_source": "live",
            "telemetry": telemetry, "access_policy": POLICY, "previous_defenses": [],
            "budgets": {"max_steps": 5, "max_requests": 10, "timeout_seconds": 30},
            "assessment_id": "run-1", "generated_at": GENERATED_AT}
    base.update(overrides)
    return base


def run(ctx, tools=None):
    return asyncio.run(observe(ctx, tools if tools is not None else InertTools()))


def event(kind, data, event_id, version="lab-v1", target="storefront-lab", second=10, assessment="run-1",
          source="live"):
    actor = "blue" if kind == "defense.proposed" else "system"
    return {"schema_version": "1.0", "id": event_id, "assessment_id": assessment, "type": kind, "actor": actor,
            "timestamp": f"2026-09-30T15:01:{second:02d}Z", "target_id": target, "target_version": version,
            "data_source": source, "evidence_refs": [], "data": data}


def revoked(session="alice-session-1", event_id=1, **scope):
    return event("defense.proposed", {"defense_id": f"d-{session}", "action_type": "revoke_session",
                 "summary": "Revoke.", "reason": "Contain.", "parameters": {"session_ref": session}}, event_id, **scope)


def revoke_applied(defense_id="d-alice-session-1", event_id=3, **scope):
    return event("defense.applied", {"defense_id": defense_id, "action_type": "revoke_session", "origin": "policy_action",
                 "original_version": "lab-v1", "resulting_version": "lab-v1"}, event_id, **scope)


def patch_applied(event_id=3, original="lab-v1", resulting="lab-v2", **scope):
    return event("defense.applied", {"defense_id": "d-patch", "action_type": "apply_patch", "origin": "known_good_fallback",
                 "original_version": original, "resulting_version": resulting}, event_id, **scope)


def as_events(payloads):
    return [event("defense.proposed", payload, i) for i, payload in enumerate(payloads, 1)]


class FixtureObservation(unittest.TestCase):
    def setUp(self):
        self.fixture = load_shared("shared/fixtures/demo-run.json")
        self.contract = load_shared("shared/contracts/v1.json")
        self.result = run(context(self.fixture["telemetry"], data_source="fixture",
                                  assessment_id=self.fixture["snapshot"]["id"]))

    def test_alerts_contains_and_proposes_draft_patch(self):
        r = self.result
        self.assertEqual(r["schema"], OBSERVE_SCHEMA)
        self.assertEqual(r["status"], "completed")
        self.assertEqual(r["data_source"], "fixture")
        self.assertEqual([a["kind"] for a in r["alerts"]], ["cross_user_read"])
        self.assertEqual(r["alerts"][0]["request_ids"], ["req-red"])
        revoke, patch = r["defense_proposals"]
        self.assertEqual((revoke["action_type"], revoke["effect"]), ("revoke_session", CONTAINMENT))
        self.assertEqual(revoke["parameters"], {"session_ref": "alice-session-1"})
        self.assertEqual((patch["action_type"], patch["effect"]), ("apply_patch", REMEDIATION))
        self.assertEqual(patch["patch_status"], "draft")
        self.assertEqual(patch["parameters"], {"patch_id": "ownership-fix-001", "base_version": "lab-v1"})
        self.assertEqual(r["evidence_refs"], ["telemetry:req-red"])
        self.assertIn("draft", " ".join(r["notes"]))

    def test_report_is_open_labeled_and_hashed(self):
        report = self.result["report"]
        self.assertEqual(report["status"], "open")
        self.assertEqual(report["data_source"], "fixture")
        self.assertEqual(report["recover"], {"verdicts": [], "retests": []})
        self.assertIn("not the final incident record", self.result["report_scope"])
        telemetry = next(e for e in report["evidence"] if e["kind"] == "telemetry")
        self.assertRegex(telemetry["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual({e["outcome"] for e in report["respond"]["mitigation"]}, {"proposed"})

    def test_payloads_meet_contract(self):
        for kind, payloads in (("alert.created", self.result["alerts"]),
                               ("defense.proposed", self.result["defense_proposals"])):
            required = self.contract["event_types"][kind]["required"]
            for payload in payloads:
                self.assertLessEqual(set(required), payload.keys())

    def test_required_key_constants_mirror_contract(self):
        types = self.contract["event_types"]
        self.assertEqual(list(observe_module.ALERT_REQUIRED), types["alert.created"]["required"])
        self.assertEqual(list(observe_module.PROPOSAL_REQUIRED), types["defense.proposed"]["required"])
        self.assertEqual(observe_module.DATA_SOURCES, set(self.contract["data_sources"]))
        self.assertEqual(list(observe_module.EVENT_REQUIRED), self.contract["event_required"])
        for kind, (actor, required) in observe_module.DEFENSE_EVENTS.items():
            self.assertEqual((actor, list(required)), (types[kind]["actor"], types[kind]["required"]))

    def test_summary_reports_counts_and_labels(self):
        summary = self.result["summary"]
        self.assertIn("1 alert", summary)
        self.assertIn("containment, not a fix", summary)
        self.assertIn("unverified until the referee retests", summary)

    def test_output_is_json_ready_and_deterministic(self):
        again = run(context(self.fixture["telemetry"], data_source="fixture",
                            assessment_id=self.fixture["snapshot"]["id"]))
        self.assertEqual(json.dumps(self.result, sort_keys=True), json.dumps(again, sort_keys=True))

    def test_red_and_referee_events_never_appear(self):
        text = json.dumps(self.result)
        for marker in ("finding.candidate", "finding.verified", "candidate_reproduced", "retest.completed"):
            self.assertNotIn(marker, text)


class Detection(unittest.TestCase):
    def test_owner_reads_give_nothing(self):
        r = run(context([log("r1", "bob", "bob"), log("r2", "alice", "alice", resource="order-101")]))
        self.assertEqual((r["alerts"], r["defense_proposals"], r["report"]), ([], [], None))
        self.assertIn("No suspicious access", r["summary"])

    def test_denied_reads_do_not_alert(self):
        r = run(context([log("r1", "alice", "bob", 403), log("r2", None, "bob", 401)]))
        self.assertEqual(r["alerts"], [])

    def test_anonymous_read_gets_patch_but_no_revocation(self):
        r = run(context([log("r1", None, "bob")]))
        self.assertEqual([a["kind"] for a in r["alerts"]], ["anonymous_read"])
        self.assertEqual([p["action_type"] for p in r["defense_proposals"]], ["apply_patch"])
        self.assertTrue(r["report"]["scope"]["unauthenticated_access"])

    def test_malformed_telemetry_is_skipped_without_raising(self):
        missing = log("r2", "alice", "bob")
        del missing["resource_owner_ref"]
        r = run(context([None, "text", missing, {**log("r3", "alice", "bob"), "http_status": "200"},
                         log("r4", "alice", "bob")]))
        self.assertEqual(len(r["alerts"]), 1)
        self.assertEqual(len(r["skipped"]), 4)
        self.assertEqual({s["request_id"] for s in r["skipped"]}, {None, "r2", "r3"})
        self.assertIn("Skipped 4 telemetry records", r["summary"])


class Scoping(unittest.TestCase):
    def test_other_target_version_and_assessment_are_skipped(self):
        other_target = {**log("r1", "alice", "bob"), "target_id": "other-lab"}
        other_version = log("r2", "alice", "bob", version="lab-v2")
        other_run = {**log("r3", "alice", "bob"), "assessment_id": "run-2"}
        other_source = {**log("r4", "alice", "bob"), "data_source": "fixture"}
        r = run(context([other_target, other_version, other_run, other_source]))
        self.assertEqual((r["alerts"], r["defense_proposals"], r["report"]), ([], [], None))
        self.assertEqual([s["reason"].split()[0] for s in r["skipped"]],
                         ["target_id", "target_version", "assessment_id", "data_source"])

    def test_same_assessment_records_are_kept(self):
        r = run(context([{**log("r1", "alice", "bob"), "assessment_id": "run-1"}]))
        self.assertEqual(len(r["alerts"]), 1)

    def test_post_patch_exposure_is_fix_failed_not_resolved(self):
        r = run(context([log("r1", "alice", "bob", version="lab-v2")], target_version="lab-v2",
                        previous_defenses=[patch_applied(version="lab-v2")]))
        self.assertEqual(r["report"]["status"], "fix_failed")
        self.assertNotIn("apply_patch", [p["action_type"] for p in r["defense_proposals"]])
        self.assertIn("targets lab-v1", " ".join(r["notes"]))

    def test_other_target_defense_events_stay_out_of_report(self):
        applied = patch_applied(original="lab-v0", resulting="lab-v1", target="other-lab")
        r = run(context([log("r1", "alice", "bob")], previous_defenses=[applied]))
        self.assertEqual(r["report"]["status"], "open")
        self.assertIn("another target", " ".join(r["notes"]))

    def test_other_assessment_or_version_patch_does_not_change_status(self):
        cases = {"another assessment": patch_applied(original="lab-v0", resulting="lab-v1", assessment="run-2"),
                 "another target version": patch_applied(original="lab-v5", resulting="lab-v6", version="lab-v6")}
        for scope, applied in cases.items():
            with self.subTest(scope=scope):
                r = run(context([log("r1", "alice", "bob")], previous_defenses=[applied]))
                self.assertEqual(r["report"]["status"], "open")
                self.assertEqual(r["report"]["respond"]["mitigation"][-1]["outcome"], "proposed")
                self.assertIn(f"for {scope} were left out", " ".join(r["notes"]))

    def test_other_scope_revocation_does_not_suppress_containment(self):
        foreign = [revoked(target="other-lab"), revoked(assessment="run-2"),
                   DefenseProposal("d-x", "revoke_session", CONTAINMENT, "other-lab", "lab-v1", "Revoke.", "Contain.",
                                   "Rejected.", {"session_ref": "alice-session-1"})]
        for entry in foreign:
            with self.subTest(entry=getattr(entry, "target_id", None) or entry["assessment_id"]):
                r = run(context([log("r1", "alice", "bob")], previous_defenses=[entry]))
                revokes = [p for p in r["defense_proposals"] if p["action_type"] == "revoke_session"]
                self.assertEqual([p["parameters"]["session_ref"] for p in revokes], ["alice-session-1"])

    def test_context_without_assessment_ignores_assessment_scoped_events(self):
        r = run(context([log("r1", "alice", "bob")], assessment_id=None, previous_defenses=[revoked()]))
        self.assertIn("revoke_session", [p["action_type"] for p in r["defense_proposals"]])

    def test_malformed_record_does_not_reserve_its_request_id(self):
        # Codex review: a malformed record must not shadow a valid suspicious record with the same ID.
        missing = log("r1", "alice", "bob")
        del missing["resource_owner_ref"]
        for bad in (missing, {**log("r1", "alice", "bob"), "http_status": "200"},
                    {**log("r1", "alice", "bob"), "timestamp": "yesterday"}):
            with self.subTest(bad=bad):
                r = run(context([bad, log("r1", "alice", "bob")]))
                self.assertEqual([a["request_ids"] for a in r["alerts"]], [["r1"]])
                self.assertEqual(len(r["skipped"]), 1)
                self.assertNotEqual(r["skipped"][0]["reason"], "duplicate request_id")

    def test_out_of_scope_record_does_not_reserve_its_request_id(self):
        r = run(context([log("r1", "alice", "bob", version="lab-v2"), log("r1", "alice", "bob")]))
        self.assertEqual(len(r["alerts"]), 1)

    def test_duplicate_request_id_is_skipped_and_first_record_is_evidence(self):
        r = run(context([log("r1", "alice", "bob"), log("r1", "carol", "bob", session="carol-session-1")]))
        self.assertEqual(r["skipped"], [{"request_id": "r1", "reason": "duplicate request_id"}])
        self.assertEqual([a["summary"].split()[0] for a in r["alerts"]], ["alice"])
        record = next(e for e in r["report"]["evidence"] if e["kind"] == "telemetry")["record"]
        self.assertEqual(record["actor_ref"], "alice")


class PreviousDefenses(unittest.TestCase):
    def test_revoked_session_is_not_proposed_again(self):
        r = run(context([log("r1", "alice", "bob")], previous_defenses=[revoked()]))
        self.assertEqual([p["action_type"] for p in r["defense_proposals"]], ["apply_patch"])

    def test_defense_events_deduplicate_and_feed_the_report(self):
        r = run(context([log("r1", "alice", "bob")], previous_defenses=[revoked(event_id=2), revoke_applied()]))
        self.assertNotIn("revoke_session", [p["action_type"] for p in r["defense_proposals"]])
        self.assertEqual(r["report"]["status"], "contained")

    def test_applied_revocation_matches_derived_id_without_proposal_event(self):
        first = run(context([log("r1", "alice", "bob")]))
        defense_id = first["defense_proposals"][0]["defense_id"]
        r = run(context([log("r1", "alice", "bob")], previous_defenses=[revoke_applied(defense_id)]))
        self.assertEqual(r["report"]["status"], "contained")
        self.assertNotIn("revoke_session", [p["action_type"] for p in r["defense_proposals"]])

    def test_revocation_of_another_session_is_not_containment(self):
        # Codex review: a fresh session still reading while the report said "contained".
        cases = {
            "fresh session": ([log("r2", "alice", "bob", second=20, session="alice-session-2")],
                              [revoked(), revoke_applied()]),
            "old and fresh session": ([log("r1", "alice", "bob", second=1),
                                       log("r2", "alice", "bob", second=20, session="alice-session-2")],
                                      [revoked(), revoke_applied()]),
            "unmatched defense id": ([log("r1", "alice", "bob")], [revoked(), revoke_applied("d-other")]),
            "anonymous read": ([log("r1", "alice", "bob"), log("r2", None, "bob", second=2)],
                               [revoked(), revoke_applied()]),
        }
        for name, (telemetry, defenses) in cases.items():
            with self.subTest(case=name):
                r = run(context(telemetry, previous_defenses=defenses))
                self.assertEqual(r["report"]["status"], "open")
                self.assertIsNone(r["report"]["times"]["contained"])
                self.assertIn("not contained", " ".join(r["notes"]))
        r = run(context(cases["fresh session"][0], previous_defenses=cases["fresh session"][1]))
        revokes = [p for p in r["defense_proposals"] if p["action_type"] == "revoke_session"]
        self.assertEqual([p["parameters"]["session_ref"] for p in revokes], ["alice-session-2"])

    def test_every_alerted_session_revoked_is_contained(self):
        # Reads at 15:00:01 and 15:00:20; both revocations applied later, at 15:01:10.
        telemetry = [log("r1", "alice", "bob", second=1),
                     log("r2", "alice", "bob", second=20, session="alice-session-2")]
        defenses = [revoked(), revoked("alice-session-2", event_id=2),
                    revoke_applied(event_id=3), revoke_applied("d-alice-session-2", event_id=4)]
        r = run(context(telemetry, previous_defenses=defenses))
        self.assertEqual(r["report"]["status"], "contained")
        self.assertNotIn("not contained", " ".join(r["notes"]))

    def test_reads_after_revocation_are_not_containment(self):
        # Codex review: a successful read after the session's revocation was reported as contained.
        def late(request_id, second, session="alice-session-1"):
            return {**log(request_id, "alice", "bob", session=session), "timestamp": f"2026-09-30T15:01:{second:02d}Z"}

        both = [revoked(), revoked("alice-session-2", event_id=2)]
        cases = {
            "read after revocation": ([log("r1", "alice", "bob", second=1), late("r2", 20)],
                                      [revoked(), revoke_applied(second=10)]),
            "read in the same second": ([late("r1", 10)], [revoked(), revoke_applied(second=10)]),
            "first revocation counts": ([late("r1", 20)],
                                        [revoked(), revoke_applied(second=10), revoke_applied(event_id=4, second=30)]),
            "one of two sessions read after revocation": (
                [log("r1", "alice", "bob", second=1), late("r2", 20, session="alice-session-2")],
                both + [revoke_applied(event_id=3, second=10),
                        revoke_applied("d-alice-session-2", event_id=4, second=10)]),
        }
        for name, (telemetry, defenses) in cases.items():
            with self.subTest(case=name):
                r = run(context(telemetry, previous_defenses=defenses))
                self.assertEqual(r["report"]["status"], "open")
                self.assertIsNone(r["report"]["times"]["contained"])
                self.assertIn("reads at or after the revocation", " ".join(r["notes"]))
                self.assertNotIn("revoke_session", [p["action_type"] for p in r["defense_proposals"]])

    def test_fresh_session_after_revocation_gets_a_new_proposal(self):
        r = run(context([log("r1", "alice", "bob", second=1),
                         log("r2", "alice", "bob", second=20, session="alice-session-2")], previous_defenses=[revoked()]))
        revokes = [p for p in r["defense_proposals"] if p["action_type"] == "revoke_session"]
        self.assertEqual([p["parameters"]["session_ref"] for p in revokes], ["alice-session-2"])

    def test_patch_already_proposed_is_not_repeated(self):
        first = run(context([log("r1", "alice", "bob")]))
        r = run(context([log("r1", "alice", "bob")], previous_defenses=as_events(first["defense_proposals"])))
        self.assertEqual(r["defense_proposals"], [])

    def test_own_proposal_objects_deduplicate(self):
        proposal = DefenseProposal("d-s", "revoke_session", CONTAINMENT, "storefront-lab", "lab-v1", "Revoke.",
                                   "Contain.", "Rejected.", {"session_ref": "alice-session-1"})
        r = run(context([log("r1", "alice", "bob")], previous_defenses=[proposal]))
        self.assertEqual([p["action_type"] for p in r["defense_proposals"]], ["apply_patch"])

    def test_previous_defense_extras_never_reach_the_output(self):
        proposed = revoked()
        proposed["data"].update(summary="tok-123 leaked", reason="see ground truth GT-MARKER",
                                ground_truth={"flaw": "GT-MARKER"}, parameters={"session_ref": "alice-session-1",
                                                                                "note": "GT-MARKER"})
        applied = event("defense.applied", {"defense_id": "d-alice-session-1", "action_type": "revoke_session",
                        "origin": "policy_action",
                        "original_version": "lab-v1", "resulting_version": "lab-v1",
                        "detail": {"ground_truth": "GT-MARKER"}}, 3)
        applied["ground_truth"] = "GT-MARKER"
        r = run(context([log("r1", "alice", "bob")], previous_defenses=[proposed, applied]))
        text = json.dumps(r)
        for marker in ("GT-MARKER", "ground_truth", "tok-123"):
            self.assertNotIn(marker, text)
        self.assertNotIn("revoke_session", [p["action_type"] for p in r["defense_proposals"]])
        self.assertEqual(r["report"]["status"], "contained")

    def test_failed_defense_reason_text_is_never_copied(self):
        # Codex review: a credential value without a marker word ("tok-123", "hunter2") was forwarded.
        for reason in ("Bearer token tok-123 rejected", "login as admin/hunter2 refused", "x" * 500, ""):
            with self.subTest(reason=reason[:20]):
                failed = event("defense.failed", {"defense_id": "d-s", "reason": reason}, 3)
                r = run(context([log("r1", "alice", "bob")], previous_defenses=[failed]))
                mitigation = r["report"]["respond"]["mitigation"][-1]
                self.assertEqual(mitigation["outcome"], "failed")
                self.assertIn(observe_module.FAILED_REASON, mitigation["details"])
                text = json.dumps(r)
                for leaked in ("tok-123", "hunter2", "xxxx"):
                    self.assertNotIn(leaked, text)

    def test_other_data_source_defenses_neither_deduplicate_nor_change_status(self):
        # Codex review: a fixture defense.applied with the same IDs made a live report "contained".
        for observed, foreign in (("live", "fixture"), ("live", "recorded"), ("fixture", "live")):
            with self.subTest(observed=observed, foreign=foreign):
                defenses = [revoked(source=foreign), revoke_applied(source=foreign),
                            patch_applied(event_id=4, original="lab-v0", resulting="lab-v1", source=foreign),
                            event("defense.failed", {"defense_id": "d-s", "reason": "x"}, 5, source=foreign)]
                r = run(context([log("r1", "alice", "bob")], data_source=observed, previous_defenses=defenses))
                self.assertEqual(r["report"]["status"], "open")
                self.assertEqual(r["report"]["data_source"], observed)
                self.assertIsNone(r["report"]["times"]["contained"])
                self.assertEqual({m["outcome"] for m in r["report"]["respond"]["mitigation"]}, {"proposed"})
                self.assertEqual([p["action_type"] for p in r["defense_proposals"]], ["revoke_session", "apply_patch"])
                self.assertIn("4 previous defense event(s) for another data source were left out",
                              " ".join(r["notes"]))

    def test_mixed_source_assessment_uses_only_matching_source(self):
        defenses = [revoked(source="fixture"), revoke_applied(source="fixture"),
                    revoked(event_id=5), revoke_applied(event_id=6)]
        r = run(context([log("r1", "alice", "bob")], previous_defenses=defenses))
        self.assertEqual(r["report"]["status"], "contained")
        self.assertIn("2 previous defense event(s) for another data source", " ".join(r["notes"]))

    def test_ids_are_stable_across_repeated_observations(self):
        first = run(context([log("r1", "alice", "bob")]))
        grown = run(context([log("r1", "alice", "bob"), log("r2", "alice", "bob", second=9)]))
        self.assertEqual([a["alert_id"] for a in first["alerts"]], [a["alert_id"] for a in grown["alerts"]])
        self.assertEqual([p["defense_id"] for p in first["defense_proposals"]],
                         [p["defense_id"] for p in grown["defense_proposals"]])

    def test_smuggled_retest_or_verdict_is_rejected(self):
        retest = {**event("retest.completed", {"finding_id": "f-1", "defense_id": "d-patch", "result": "passed",
                          "checks": []}, 4), "actor": "referee"}
        verdict = event("finding.verified", {"finding_id": "f-1", "verdict": "verified", "summary": "x"}, 5)
        for entry in (retest, verdict):
            with self.subTest(kind=entry["type"]), self.assertRaises(ContextError):
                run(context([log("r1", "alice", "bob")], previous_defenses=[entry]))

    def test_malformed_previous_defenses_are_rejected(self):
        no_assessment = revoked()
        del no_assessment["assessment_id"]
        bad = [
            "revoke", [None], [{"type": "defense.applied", "data": "x"}],
            [{"action_type": "revoke_session", "parameters": {"session_ref": "alice-session-1"}}],  # no scope
            [no_assessment], [{**revoked(), "actor": "system"}], [{**patch_applied(), "actor": "blue"}],
            [{**revoked(), "data": {**revoked()["data"], "action_type": "drop_table"}}],
            [{**revoked(), "data": {**revoked()["data"], "defense_id": {"nested": 1}}}],
            [{**patch_applied(), "data": {**patch_applied()["data"], "resulting_version": "lab v2; rm"}}],
            [{**revoked(), "timestamp": "yesterday"}], [{**revoked(), "evidence_refs": [{"x": 1}]}],
            [event("defense.failed", {"defense_id": "d-s", "reason": ["x"]}, 3)],
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ContextError):
                run(context([log("r1", "alice", "bob")], previous_defenses=value))


class ContextIsolation(unittest.TestCase):
    def test_red_and_evaluation_keys_are_rejected(self):
        fixture = load_shared("shared/fixtures/demo-run.json")
        leaks = {"events": fixture["events"], "candidates": [{"finding_id": "f-1"}], "ground_truth": {"flaw": "x"},
                 "red_plan": "probe orders", "verdicts": []}
        for key, value in leaks.items():
            with self.subTest(key=key), self.assertRaises(ContextError) as caught:
                run(context(fixture["telemetry"], **{key: value}))
            self.assertIn(key, str(caught.exception))

    def test_missing_or_malformed_policy_fails_closed(self):
        detector = mock.Mock(side_effect=AssertionError("detector must not run"))
        bad = [None, {}, {"id": "p"}, {"id": "", "owner_only_actions": ["read_private_order"]},
               {"id": "p", "owner_only_actions": []}, {"id": "p", "owner_only_actions": "read_private_order"},
               {"id": "p", "owner_only_actions": ["read_private_order"], "extra": 1}]
        with mock.patch.object(observe_module, "detect_suspicious_access", detector):
            for policy in bad:
                with self.subTest(policy=policy), self.assertRaises(ContextError):
                    run(context([log("r1", "alice", "bob")], access_policy=policy))
            ctx = context([log("r1", "alice", "bob")])
            del ctx["access_policy"]
            with self.assertRaises(ContextError):
                run(ctx)
        detector.assert_not_called()

    def test_policy_comes_from_context_not_the_default(self):
        other = {"id": "other-policy", "owner_only_actions": ["read_invoice"]}
        r = run(context([log("r1", "alice", "bob")], access_policy=other))
        self.assertEqual(r["alerts"], [])
        r = run(context([log("r1", "alice", "bob")], access_policy=PRIVATE_ORDERS_POLICY))
        self.assertEqual(len(r["alerts"]), 1)

    def test_data_source_must_be_a_contract_label(self):
        for value in ("liveish", None, ""):
            with self.subTest(value=value), self.assertRaises(ContextError):
                run(context([], data_source=value))
        ctx = context([])
        del ctx["data_source"]
        with self.assertRaises(ContextError):
            run(ctx)

    def test_other_shape_errors(self):
        for telemetry, overrides in (("x", {}), ([None] * 10_001, {}), ([], {"target_id": ""}),
                                     ([], {"generated_at": "2026-09-30 16:00"}),
                                     ([], {"budgets": {"max_tokens": 5}}), ([], {"budgets": {"max_steps": "5"}})):
            with self.subTest(overrides=overrides), self.assertRaises(ContextError):
                run(context(telemetry, **overrides))
        with self.assertRaises(ContextError):
            run(["not", "a", "mapping"])

    def test_secret_fields_never_reach_the_output(self):
        record = {**log("r1", "alice", "bob"), "token": "tok-123", "Cookie": "sid=abc", "Authorization": "Bearer x"}
        r = run(context([record]))
        text = json.dumps(r)
        for secret in ("tok-123", "sid=abc", "Bearer x"):
            self.assertNotIn(secret, text)
        self.assertEqual(secret_keys(r), set())

    def test_extra_telemetry_fields_never_reach_the_output(self):
        record = {**log("r1", "alice", "bob"), "ground_truth": {"flaw": "GT-MARKER"}, "note": "GT-MARKER"}
        nested = {**log("r2", "alice", "bob", second=2), "resource_owner_ref": {"ground_truth": "GT-MARKER"}}
        r = run(context([record, nested]))
        self.assertEqual(len(r["alerts"]), 1)
        self.assertEqual(r["skipped"], [{"request_id": "r2", "reason": "missing resource_owner_ref"}])
        text = json.dumps(r)
        self.assertNotIn("GT-MARKER", text)
        self.assertNotIn("ground_truth", text)
        evidence = next(e for e in r["report"]["evidence"] if e["kind"] == "telemetry")
        self.assertLessEqual(evidence["record"].keys(), set(TELEMETRY_FIELDS))

    def test_context_is_not_mutated(self):
        ctx = context([log("r1", "alice", "bob")])
        before = json.dumps(ctx, sort_keys=True)
        run(ctx)
        self.assertEqual(json.dumps(ctx, sort_keys=True), before)


class BudgetsAndTools(unittest.TestCase):
    def assert_empty_without_work(self, ctx, tools, status):
        detector = mock.Mock(side_effect=AssertionError("detector must not run"))
        loader = mock.Mock(side_effect=AssertionError("loader must not run"))
        with mock.patch.object(observe_module, "detect_suspicious_access", detector), \
                mock.patch.object(observe_module, "load_patch_manifest", loader):
            r = run(ctx, tools)
        self.assertEqual(r["status"], status)
        self.assertEqual((r["alerts"], r["defense_proposals"], r["report"]), ([], [], None))
        detector.assert_not_called()
        loader.assert_not_called()
        return r

    def test_exhausted_budget_returns_empty_result(self):
        for budgets in ({"max_steps": 0}, {"timeout_seconds": 0}, {"max_steps": -1, "max_requests": 3}):
            with self.subTest(budgets=budgets):
                r = self.assert_empty_without_work(context([log("r1", "alice", "bob")], budgets=budgets),
                                                   InertTools(), "budget_exhausted")
                self.assertIn("budget exhausted", r["summary"])

    def test_spent_request_budget_does_not_stop_passive_observation(self):
        r = run(context([log("r1", "alice", "bob")], budgets={"max_steps": 5, "max_requests": 0}))
        self.assertEqual((r["status"], len(r["alerts"])), ("completed", 1))

    def test_cancelled_returns_empty_result(self):
        r = self.assert_empty_without_work(context([log("r1", "alice", "bob")]), InertTools(cancelled=True),
                                           "cancelled")
        self.assertIn("cancelled", r["summary"])

    def test_no_tools_and_no_budgets_still_runs(self):
        ctx = context([log("r1", "alice", "bob")])
        del ctx["budgets"]
        r = asyncio.run(observe(ctx))
        self.assertEqual(len(r["alerts"]), 1)

    def test_generated_at_falls_back_to_tools_then_fails_closed(self):
        ctx = context([log("r1", "alice", "bob")])
        del ctx["generated_at"]
        self.assertEqual(run(ctx, InertTools(now="2026-09-30T17:00:00Z"))["report"]["generated_at"],
                         "2026-09-30T17:00:00Z")
        with self.assertRaises(ContextError):
            asyncio.run(observe(ctx))
        with self.assertRaises(ContextError):
            run(ctx, InertTools(now="yesterday"))


class PatchAvailability(unittest.TestCase):
    def test_unreadable_manifest_still_returns_alerts_and_revocations(self):
        for error in (PatchManifestError("manifest missing title"), FileNotFoundError("manifest.json"),
                      json.JSONDecodeError("bad", "{", 0)):
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(observe_module, "load_patch_manifest", side_effect=error):
                r = run(context([log("r1", "alice", "bob")]))
                self.assertEqual(len(r["alerts"]), 1)
                self.assertEqual([p["action_type"] for p in r["defense_proposals"]], ["revoke_session"])
                self.assertIn("could not be loaded", " ".join(r["notes"]))
                self.assertEqual(r["report"]["status"], "open")

    def test_patch_id_is_constant(self):
        loader = mock.Mock(side_effect=PatchManifestError("x"))
        with mock.patch.object(observe_module, "load_patch_manifest", loader):
            run(context([log("r1", "alice", "bob")]))
        loader.assert_called_once_with("ownership-fix-001")


if __name__ == "__main__":
    unittest.main()
