"""Synthetic regressions for Red's evidence-backed hypothesis workflow.

These tests use the board directly: no lab server, executor, or model provider.
Agent assessments remain distinct from independent mission verification.
"""

from __future__ import annotations

import copy
import json
import queue
import threading
import unittest
from dataclasses import replace

from red.prototype.board import RedBoard
from red.prototype.domain import Evidence, HypothesisUpdate


class HypothesisHarness(unittest.TestCase):
    candidate_key = "cross-owner record read"
    statement = "The record route may omit the owner's access check."
    expected_result = "Account B receives Account A's protected record content."
    scout_owner = "synthetic-scout"
    operator_owner = "synthetic-operator"

    def setUp(self) -> None:
        self.board = RedBoard(session_id="synthetic-run")
        self.scout = self.board.add_task("scout", "Survey the synthetic record catalog")
        self.assertTrue(self.board.claim_task(self.scout.task_id, self.scout_owner))
        self.observation("ev-catalog", role="scout", path="/api/catalog")

    def observation(
        self, ref, *, status=200, role="operator", capability="request_api",
        path="/api/records/record-a", failure_kind=None, session_id="", session_ref=None,
    ):
        if status is None:
            body = ""
        elif not 200 <= status < 300:
            body = json.dumps({"error": "synthetic denial or failure"})
        elif path == "/api/records/record-a":
            body = json.dumps({"record_id": "record-a", "owner": "account_a", "content": "synthetic vault data"})
        else:
            body = json.dumps({"synthetic": True})
        self.board.add_evidence(Evidence(
            evidence_id=ref, sequence=0, role=role, capability=capability,
            method="POST" if capability == "start_account_session" else "GET", path=path, status=status,
            summary="Synthetic response observation", body=body,
            session_id=session_id, failure_kind=failure_kind, session_ref=session_ref,
        ))
        evidence = self.board.get_evidence(ref)
        self.assertIsNotNone(evidence)
        return evidence

    def creation(self, **changes):
        return replace(HypothesisUpdate(
            operation="create", candidate_key=self.candidate_key,
            statement=self.statement, expected_result=self.expected_result,
            evidence_refs=("ev-catalog",), status="inconclusive",
            assessment="The catalog identifies a candidate; cross-owner behavior is untested.",
            expected_revision=0,
        ), **changes)

    def create_candidate(self, **changes):
        return self.board.apply_hypothesis(
            self.creation(**changes), task_id=self.scout.task_id, owner=self.scout_owner,
        )

    def handoff(self, **changes):
        arguments = {
            "from_task_id": self.scout.task_id, "sender": self.scout_owner,
            "evidence_refs": ["ev-catalog"],
            "reason": "Compare owner access with a request from the other account.",
            "candidate_key": self.candidate_key,
        }
        return self.board.handoff(**{**arguments, **changes})

    def ready_operator(self):
        self.create_candidate()
        self.operator = self.handoff()
        self.assertTrue(self.board.claim_task(self.operator.task_id, self.operator_owner))
        self.assertTrue(self.board.claim_candidate(
            self.candidate_key, self.operator.task_id, self.operator_owner,
        ))
        self.observation("ev-baseline", session_ref="synthetic-owner-session")
        self.observation("ev-comparison", session_ref="synthetic-other-account-session")

    def assessment(self, **changes):
        record = self.board.get_hypothesis(self.candidate_key)
        self.assertIsNotNone(record)
        return replace(HypothesisUpdate(
            operation="assess", candidate_key=self.candidate_key,
            status="supported", baseline_evidence_ref="ev-baseline",
            comparison_evidence_ref="ev-comparison",
            changed_condition="Request the same record as Account B instead of Account A.",
            assessment="Both requests returned the same protected synthetic content.",
            expected_revision=record["revision"],
        ), **changes)

    def apply_operator(self, update):
        return self.board.apply_hypothesis(
            update, task_id=self.operator.task_id, owner=self.operator_owner,
        )

    def reopening(self, **changes):
        record = self.board.get_hypothesis(self.candidate_key)
        self.assertIsNotNone(record)
        return replace(HypothesisUpdate(
            operation="reopen", candidate_key=self.candidate_key,
            evidence_refs=("ev-contradiction",), status="inconclusive",
            assessment="A later response contradicts the earlier comparison; retest both conditions.",
            expected_revision=record["revision"],
        ), **changes)

    def conclude_and_reopen(self):
        self.ready_operator()
        concluded = self.apply_operator(self.assessment())
        self.observation("ev-contradiction", status=403)
        reopened = self.apply_operator(self.reopening())
        return concluded, reopened

    def assert_update_rejected(self, update, *, task_id=None, owner=None):
        before = (self.board.hypotheses(), self.board.events(), self.board.tasks())
        with self.assertRaises(ValueError):
            self.board.apply_hypothesis(
                update, task_id=task_id or self.operator.task_id,
                owner=owner or self.operator_owner,
            )
        self.assertEqual(
            (self.board.hypotheses(), self.board.events(), self.board.tasks()), before,
            "A rejected update must not change revisions, history, events, or task associations.",
        )

    def assert_handoff_rejected(self, **changes):
        before = (self.board.hypotheses(), self.board.events(), self.board.tasks(), self.board.handoffs())
        with self.assertRaises(ValueError):
            self.handoff(**changes)
        self.assertEqual(
            (self.board.hypotheses(), self.board.events(), self.board.tasks(), self.board.handoffs()), before,
        )


class CandidateAndHandoffTests(HypothesisHarness):
    def test_candidate_creation_records_an_unproven_prediction_and_provenance(self):
        record = self.create_candidate(candidate_key="  CROSS-OWNER RECORD READ  ")
        self.assertEqual(record["candidate_key"], self.candidate_key)
        self.assertEqual(record["statement"], self.statement)
        self.assertEqual(record["expected_result"], self.expected_result)
        self.assertEqual(record["status"], "inconclusive")
        self.assertEqual(record["revision"], 1)
        self.assertEqual(record["session_id"], self.board.session_id)
        self.assertEqual(record["assessment_source"], "agent_assessed")
        self.assertEqual(record["supporting_evidence_refs"], ["ev-catalog"])
        self.assertIsNone(record["baseline_evidence_ref"])
        self.assertIsNone(record["comparison_evidence_ref"])
        self.assertEqual(record["history"][0]["operation"], "create")
        self.assertEqual(record["history"][0]["task_id"], self.scout.task_id)
        self.assertEqual(record, self.board.get_hypothesis(self.candidate_key.upper()))
        event = self.board.events()[-1]
        self.assertEqual(event["event_type"], "hypothesis.created")
        self.assertEqual(event["sequence"], record["history"][0]["sequence"])
        self.assertEqual(event["evidence_refs"], ["ev-catalog"])

    def test_creation_requires_statement_prediction_evidence_and_assessment(self):
        for changes in (
            {"statement": " "}, {"expected_result": " "},
            {"evidence_refs": ()}, {"assessment": " "}, {"expected_revision": 1},
            {"status": "supported"}, {"status": "rejected"},
            {"baseline_evidence_ref": "ev-catalog"},
            {"comparison_evidence_ref": "ev-catalog"}, {"changed_condition": "identity"},
        ):
            with self.subTest(changes=changes):
                self.assert_update_rejected(
                    self.creation(**changes), task_id=self.scout.task_id, owner=self.scout_owner,
                )
        self.assertEqual(self.board.hypotheses(), [])

    def test_creation_rejects_missing_foreign_and_policy_denial_only_evidence(self):
        self.observation("ev-foreign", session_id="another-run", role="scout")
        self.observation("ev-denied", status=None, failure_kind="policy_denial", role="scout")
        for refs in (("missing",), ("ev-foreign",), ("ev-catalog", "ev-foreign"), ("ev-denied",)):
            with self.subTest(refs=refs):
                self.assert_update_rejected(
                    self.creation(evidence_refs=refs), task_id=self.scout.task_id, owner=self.scout_owner,
                )

    def test_normalized_candidate_cannot_be_created_twice(self):
        self.create_candidate()
        self.assert_update_rejected(
            self.creation(candidate_key=" CROSS-OWNER RECORD READ "),
            task_id=self.scout.task_id, owner=self.scout_owner,
        )

    def test_creation_requires_owned_active_task(self):
        queued = self.board.add_task("scout", "Unclaimed synthetic survey")
        for task_id, owner in (
            (queued.task_id, "unclaimed-scout"), ("missing-task", self.scout_owner),
            (self.scout.task_id, "wrong-owner"),
        ):
            with self.subTest(task_id=task_id, owner=owner):
                self.assert_update_rejected(self.creation(), task_id=task_id, owner=owner)
        self.board.finish_task(self.scout.task_id)
        self.assert_update_rejected(self.creation(), task_id=self.scout.task_id, owner=self.scout_owner)

    def test_handoff_carries_prediction_and_queues_claimable_operator_work(self):
        candidate = self.create_candidate()
        task = self.handoff(candidate_key=self.candidate_key.upper())
        handoff = self.board.handoffs()[0]
        self.assertEqual(task.role, "operator")
        self.assertEqual(task.status, "queued")
        self.assertIsNone(task.owner)
        self.assertEqual(task.evidence_refs, ["ev-catalog"])
        self.assertEqual(task.hypothesis_ids, [candidate["hypothesis_id"]])
        self.assertEqual(handoff["hypothesis_id"], candidate["hypothesis_id"])
        self.assertEqual(handoff["hypothesis_revision"], candidate["revision"])
        self.assertEqual(handoff["statement"], self.statement)
        self.assertEqual(handoff["expected_result"], self.expected_result)
        self.assertEqual(handoff["session_id"], self.board.session_id)
        self.assertEqual(handoff["to_task_id"], task.task_id)
        self.assertFalse(self.board.claim_candidate(self.candidate_key, task.task_id, self.operator_owner))
        self.assertTrue(self.board.claim_task(task.task_id, self.operator_owner))
        self.assertTrue(self.board.claim_candidate(self.candidate_key, task.task_id, self.operator_owner))
        self.assertEqual(self.board.tasks()[0]["status"], "active")

    def test_handoff_requires_existing_candidate_and_its_cited_evidence(self):
        self.assert_handoff_rejected()
        self.create_candidate()
        self.observation("ev-unrelated", role="scout")
        self.observation("ev-foreign", role="scout", session_id="another-run")
        for refs in ([], ["missing"], ["ev-unrelated"], ["ev-foreign"], ["ev-catalog", "ev-unrelated"]):
            with self.subTest(refs=refs):
                self.assert_handoff_rejected(evidence_refs=refs)
        self.assert_handoff_rejected(candidate_key="unknown candidate")

    def test_handoff_requires_owned_active_scout_and_cannot_duplicate_work(self):
        self.create_candidate()
        self.assert_handoff_rejected(sender="other-scout")
        self.assert_handoff_rejected(from_task_id="unknown-task")
        self.handoff()
        self.assert_handoff_rejected()
        self.board.finish_task(self.scout.task_id)
        self.assert_handoff_rejected()

    def test_handoff_requires_nonempty_test_question_without_consuming_candidate(self):
        self.create_candidate()
        for reason in ("", " ", "\t\n"):
            with self.subTest(reason=repr(reason)):
                self.assert_handoff_rejected(reason=reason)
        reason = "Compare owner access with the same request from the other account."
        task = self.handoff(reason=reason)
        self.assertEqual(task.status, "queued")
        self.assertEqual(self.board.handoffs()[0]["test_question"], reason)
        self.assertTrue(self.board.claim_task(task.task_id, self.operator_owner))
        self.assertTrue(self.board.claim_candidate(self.candidate_key, task.task_id, self.operator_owner))

    def test_invalid_combined_handoff_cannot_create_a_candidate(self):
        self.observation("ev-unrelated", role="scout")
        for changes in (
            {"reason": " "}, {"candidate_key": "different candidate"},
            {"evidence_refs": ["ev-unrelated"]}, {"sender": "unrelated-scout"},
        ):
            with self.subTest(changes=changes):
                self.assert_handoff_rejected(hypothesis_update=self.creation(), **changes)
        task = self.handoff(hypothesis_update=self.creation())
        self.assertEqual(task.status, "queued")
        self.assertEqual(len(self.board.hypotheses()), 1)


class HypothesisPredictionTimingTests(HypothesisHarness):
    def test_comparison_must_follow_prediction_even_when_baseline_order_is_valid(self):
        baseline = self.observation("ev-before-prediction-baseline", session_ref="synthetic-owner-session")
        supported = self.observation("ev-before-prediction-success", session_ref="synthetic-other-account-session")
        rejected = self.observation("ev-before-prediction-denial", status=403)
        self.ready_operator()
        candidate = self.board.get_hypothesis(self.candidate_key)
        creation_sequence = candidate["history"][0]["sequence"]
        for status, comparison in (("supported", supported), ("rejected", rejected)):
            with self.subTest(status=status):
                self.assertLess(baseline.sequence, comparison.sequence)
                self.assertLess(comparison.sequence, creation_sequence)
                self.assert_update_rejected(self.assessment(
                    status=status, baseline_evidence_ref=baseline.evidence_id,
                    comparison_evidence_ref=comparison.evidence_id,
                ))
        # The ordinary baseline may predate the prediction; the test must follow it.
        later = self.board.get_evidence("ev-comparison")
        self.assertGreater(later.sequence, creation_sequence)
        record = self.apply_operator(self.assessment(baseline_evidence_ref=baseline.evidence_id))
        self.assertEqual(record["status"], "supported")
        self.assertEqual(record["revision"], candidate["revision"] + 1)
        self.assertEqual(record["history"][:-1], candidate["history"])


class HypothesisAssessmentTests(HypothesisHarness):
    def setUp(self):
        super().setUp()
        self.ready_operator()

    def test_operator_supports_candidate_with_ordered_baseline_and_comparison(self):
        record = self.apply_operator(self.assessment())
        baseline = self.board.get_evidence(record["baseline_evidence_ref"])
        comparison = self.board.get_evidence(record["comparison_evidence_ref"])
        self.assertEqual(record["status"], "supported")
        self.assertEqual(record["revision"], 2)
        self.assertEqual(record["assessment_source"], "agent_assessed")
        self.assertLess(baseline.sequence, comparison.sequence)
        self.assertEqual(record["supporting_evidence_refs"], ["ev-catalog", "ev-baseline", "ev-comparison"])
        self.assertEqual(record["history"][-1]["from_status"], "inconclusive")
        self.assertEqual(record["history"][-1]["role"], "operator")
        self.assertEqual(record["history"][-1]["task_id"], self.operator.task_id)
        event = self.board.events()[-1]
        self.assertEqual(event["event_type"], "hypothesis.assessed")
        self.assertEqual(event["revision"], record["revision"])
        self.assertEqual(event["sequence"], record["history"][-1]["sequence"])

    def test_ordinary_403_can_reject_candidate_with_successful_owner_baseline(self):
        self.observation("ev-forbidden", status=403)
        record = self.apply_operator(self.assessment(
            status="rejected", comparison_evidence_ref="ev-forbidden",
            assessment="Owner access works, while Account B receives an ordinary access denial.",
        ))
        self.assertEqual(record["status"], "rejected")
        self.assertEqual(record["baseline_evidence_ref"], "ev-baseline")
        self.assertEqual(record["comparison_evidence_ref"], "ev-forbidden")
        self.assertEqual(record["revision"], 2)

    def test_operator_can_use_successful_scout_baseline_with_its_later_comparison(self):
        self.observation("ev-scout-owner-baseline", role="scout", session_ref="synthetic-owner-session")
        self.observation("ev-operator-after-scout", session_ref="synthetic-other-account-session")
        record = self.apply_operator(self.assessment(
            baseline_evidence_ref="ev-scout-owner-baseline",
            comparison_evidence_ref="ev-operator-after-scout",
        ))
        self.assertEqual(record["status"], "supported")
        self.assertEqual(record["history"][-1]["role"], "operator")

    def test_conclusion_requires_both_refs_and_a_changed_condition(self):
        for status in ("supported", "rejected"):
            for changes in (
                {"baseline_evidence_ref": None}, {"comparison_evidence_ref": None},
                {"changed_condition": " "}, {"assessment": " "},
            ):
                with self.subTest(status=status, changes=changes):
                    self.assert_update_rejected(self.assessment(status=status, **changes))

    def test_all_cited_refs_must_exist_and_belong_to_this_run(self):
        self.observation("ev-foreign", session_id="another-run")
        for ref in ("missing", "ev-foreign"):
            for field in ("evidence_refs", "baseline_evidence_ref", "comparison_evidence_ref"):
                with self.subTest(ref=ref, field=field):
                    self.assert_update_rejected(self.assessment(**{field: (ref,) if field == "evidence_refs" else ref}))

    def test_comparison_must_be_distinct_later_and_observed_by_operator(self):
        self.observation("ev-late-baseline")
        self.observation("ev-scout-comparison", role="scout")
        for changes in (
            {"comparison_evidence_ref": "ev-baseline"},
            {"baseline_evidence_ref": "ev-comparison", "comparison_evidence_ref": "ev-baseline"},
            {"baseline_evidence_ref": "ev-late-baseline"},
            {"comparison_evidence_ref": "ev-scout-comparison"},
        ):
            with self.subTest(changes=changes):
                self.assert_update_rejected(self.assessment(**changes))

    def test_ambiguous_comparisons_cannot_support_or_reject(self):
        observations = (
            (None, None, "request_api"),
            (200, "target_transport", "request_api"),
            (200, "response_truncated", "request_api"),
            (200, "policy_denial", "request_api"),
            (302, "redirect_not_followed", "request_api"),
            (408, None, "request_api"), (429, None, "request_api"),
            (500, None, "request_api"), (503, None, "request_api"),
            (599, None, "request_api"),
            (401, None, "start_account_session"), (403, None, "start_account_session"),
        )
        for index, (http_status, failure, capability) in enumerate(observations):
            ref = "ev-ambiguous-" + str(index)
            self.observation(ref, status=http_status, failure_kind=failure, capability=capability)
            for conclusion in ("supported", "rejected"):
                with self.subTest(http_status=http_status, failure=failure, capability=capability, conclusion=conclusion):
                    self.assert_update_rejected(self.assessment(status=conclusion, comparison_evidence_ref=ref))

    def test_redirect_without_failure_marker_cannot_support_or_reject(self):
        for http_status in (301, 302, 303, 304, 307, 308):
            ref = "ev-unmarked-redirect-" + str(http_status)
            redirect = self.observation(ref, status=http_status)
            self.assertIsNone(redirect.failure_kind)
            for conclusion in ("supported", "rejected"):
                with self.subTest(http_status=http_status, conclusion=conclusion):
                    self.assert_update_rejected(self.assessment(status=conclusion, comparison_evidence_ref=ref))
        record = self.apply_operator(self.assessment(
            status="inconclusive", evidence_refs=(ref,),
            baseline_evidence_ref=None, comparison_evidence_ref=None, changed_condition="",
            assessment="The target redirected; protected record access remains untested.",
        ))
        self.assertEqual(record["status"], "inconclusive")
        self.assertIn(ref, record["supporting_evidence_refs"])

    def test_baseline_must_be_successful_and_have_no_failure_marker(self):
        for index, (status, failure) in enumerate((
            (None, None), (200, "response_truncated"), (302, None),
            (401, None), (403, None), (408, None), (429, None), (503, None),
        )):
            baseline_ref = "ev-bad-baseline-" + str(index)
            comparison_ref = "ev-later-comparison-" + str(index)
            self.observation(baseline_ref, status=status, failure_kind=failure)
            self.observation(comparison_ref)
            for conclusion in ("supported", "rejected"):
                with self.subTest(status=status, failure=failure, conclusion=conclusion):
                    self.assert_update_rejected(self.assessment(
                        status=conclusion, baseline_evidence_ref=baseline_ref,
                        comparison_evidence_ref=comparison_ref,
                    ))

    def test_ambiguous_failure_can_be_recorded_as_inconclusive(self):
        self.observation("ev-timeout", status=None, failure_kind="target_transport")
        record = self.apply_operator(self.assessment(
            status="inconclusive", evidence_refs=("ev-timeout",),
            baseline_evidence_ref=None, comparison_evidence_ref=None, changed_condition="",
            assessment="The comparison timed out; access behavior remains unknown.",
        ))
        self.assertEqual(record["status"], "inconclusive")
        self.assertEqual(record["revision"], 2)
        self.assertIn("ev-timeout", record["supporting_evidence_refs"])
        self.assertIsNone(record["comparison_evidence_ref"])

    def test_scout_cannot_conclude_candidate(self):
        for status in ("supported", "rejected"):
            with self.subTest(status=status):
                self.assert_update_rejected(
                    self.assessment(status=status), task_id=self.scout.task_id, owner=self.scout_owner,
                )

    def test_assessment_requires_owned_active_task_and_candidate_claim(self):
        queued = self.board.add_task("operator", "Unclaimed work")
        unrelated = self.board.add_task("operator", "Other candidate work")
        self.assertTrue(self.board.claim_task(unrelated.task_id, "other-operator"))
        self.assertFalse(self.board.claim_candidate(self.candidate_key, unrelated.task_id, "other-operator"))
        for task_id, owner in (
            ("missing-task", self.operator_owner), (queued.task_id, self.operator_owner),
            (self.operator.task_id, "wrong-owner"), (unrelated.task_id, "other-operator"),
        ):
            with self.subTest(task_id=task_id, owner=owner):
                self.assert_update_rejected(self.assessment(), task_id=task_id, owner=owner)
        self.board.finish_task(self.operator.task_id)
        self.assert_update_rejected(self.assessment())

    def test_operator_must_claim_candidate_even_when_it_has_an_active_task(self):
        self.create_candidate(candidate_key="separate unclaimed candidate")
        self.assert_update_rejected(self.assessment(candidate_key="separate unclaimed candidate"))

    def test_prediction_cannot_change_during_assessment(self):
        for changes in (
            {"statement": "A different route is vulnerable."},
            {"expected_result": "Only a timeout is expected."},
        ):
            with self.subTest(changes=changes):
                self.assert_update_rejected(self.assessment(**changes))
        record = self.apply_operator(self.assessment(statement=self.statement, expected_result=self.expected_result))
        self.assertEqual(record["statement"], self.statement)
        self.assertEqual(record["expected_result"], self.expected_result)

    def test_stale_revision_or_unknown_candidate_cannot_change_state(self):
        original_update = self.assessment()
        self.apply_operator(original_update)
        self.observation("ev-new-comparison")
        self.assert_update_rejected(replace(original_update, comparison_evidence_ref="ev-new-comparison"))
        self.assert_update_rejected(self.assessment(candidate_key="unknown candidate"))

    def test_concluded_candidate_cannot_flip_status_without_reopening(self):
        self.apply_operator(self.assessment())
        self.observation("ev-new-denial", status=403)
        self.assert_update_rejected(self.assessment(
            status="rejected", comparison_evidence_ref="ev-new-denial",
        ))

    def test_reassessing_a_conclusion_requires_a_new_comparison(self):
        self.apply_operator(self.assessment())
        self.assert_update_rejected(self.assessment())
        self.observation("ev-new-comparison")
        record = self.apply_operator(self.assessment(comparison_evidence_ref="ev-new-comparison"))
        self.assertEqual(record["revision"], 3)
        self.assertEqual(record["comparison_evidence_ref"], "ev-new-comparison")

    def test_competing_updates_with_same_revision_have_one_atomic_winner(self):
        contenders = 8
        barrier = threading.Barrier(contenders)
        outcomes = queue.Queue()
        updates = []
        for index in range(contenders):
            ref = "ev-race-comparison-" + str(index)
            self.observation(ref)
            updates.append(self.assessment(
                comparison_evidence_ref=ref, assessment="Synthetic assessment contender " + str(index),
            ))
        before = self.board.get_hypothesis(self.candidate_key)
        before_events = self.board.events()

        def assess(update):
            try:
                barrier.wait(timeout=5)
                result = self.apply_operator(update)
                outcomes.put(("won", result))
            except ValueError as error:
                outcomes.put(("stale", str(error)))
            except Exception as error:
                outcomes.put(("unexpected", repr(error)))

        threads = [threading.Thread(target=assess, args=(update,), daemon=True) for update in updates]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertFalse(any(thread.is_alive() for thread in threads), "Hypothesis updates must not deadlock.")
        results = [outcomes.get_nowait() for _ in range(outcomes.qsize())]
        self.assertEqual(len(results), contenders)
        self.assertEqual(sum(kind == "won" for kind, _ in results), 1, results)
        self.assertEqual(sum(kind == "stale" for kind, _ in results), contenders - 1, results)
        winner = next(record for kind, record in results if kind == "won")
        current = self.board.get_hypothesis(self.candidate_key)
        self.assertEqual(current, winner)
        self.assertEqual(current["revision"], before["revision"] + 1)
        self.assertEqual(current["history"][:-1], before["history"])
        self.assertEqual(current["supporting_evidence_refs"], [
            "ev-catalog", "ev-baseline", winner["comparison_evidence_ref"],
        ])
        self.assertEqual(len(self.board.events()), len(before_events) + 1)
        self.assertEqual(self.board.events()[-1]["revision"], current["revision"])


class HypothesisReopeningTests(HypothesisHarness):
    def setUp(self):
        super().setUp()
        self.ready_operator()
        self.concluded = self.apply_operator(self.assessment())
        self.observation("ev-contradiction", status=403)

    def test_reopening_preserves_prior_assessments_and_clears_current_comparison(self):
        reopened = self.apply_operator(self.reopening())
        self.assertEqual(reopened["status"], "inconclusive")
        self.assertEqual(reopened["revision"], self.concluded["revision"] + 1)
        self.assertEqual(reopened["history"][:-1], self.concluded["history"])
        self.assertEqual(reopened["hypothesis_id"], self.concluded["hypothesis_id"])
        self.assertEqual(reopened["statement"], self.statement)
        self.assertEqual(reopened["expected_result"], self.expected_result)
        self.assertEqual(reopened["supporting_evidence_refs"], [
            "ev-catalog", "ev-baseline", "ev-comparison", "ev-contradiction",
        ])
        self.assertIsNone(reopened["baseline_evidence_ref"])
        self.assertIsNone(reopened["comparison_evidence_ref"])
        self.assertEqual(reopened["changed_condition"], "")
        event = self.board.events()[-1]
        self.assertEqual(event["event_type"], "hypothesis.reopened")
        self.assertEqual(reopened["reopened_at_sequence"], event["sequence"])
        self.assertGreater(event["sequence"], self.board.get_evidence("ev-contradiction").sequence)
        self.assertEqual(reopened["history"][-1]["from_status"], "supported")

    def test_reopening_requires_new_same_run_observations_and_inconclusive_status(self):
        self.observation("ev-foreign", session_id="another-run")
        for changes in (
            {"evidence_refs": ()}, {"evidence_refs": ("missing",)},
            {"evidence_refs": ("ev-foreign",)}, {"evidence_refs": ("ev-comparison",)},
            {"evidence_refs": ("ev-contradiction", "ev-baseline")},
            {"status": "supported"}, {"status": "rejected"},
            {"baseline_evidence_ref": "ev-baseline"},
            {"comparison_evidence_ref": "ev-contradiction"}, {"changed_condition": "identity"},
            {"assessment": " "}, {"expected_revision": self.concluded["revision"] - 1},
        ):
            with self.subTest(changes=changes):
                self.assert_update_rejected(self.reopening(**changes))

    def test_prediction_cannot_be_rewritten_when_reopening(self):
        for changes in (
            {"statement": "The request should crash the server."},
            {"expected_result": "Any error proves the prediction."},
        ):
            with self.subTest(changes=changes):
                self.assert_update_rejected(self.reopening(**changes))

    def test_operator_cannot_reopen_candidate_owned_by_another_task(self):
        unrelated = self.board.add_task("operator", "Work on an unrelated candidate")
        self.assertTrue(self.board.claim_task(unrelated.task_id, "other-operator"))
        self.assertFalse(self.board.claim_candidate(self.candidate_key, unrelated.task_id, "other-operator"))
        self.assert_update_rejected(self.reopening(), task_id=unrelated.task_id, owner="other-operator")

    def test_scout_can_reopen_and_rehandoff_after_operator_finishes(self):
        self.board.finish_task(self.operator.task_id)
        reopened = self.board.apply_hypothesis(self.reopening(), task_id=self.scout.task_id, owner=self.scout_owner)
        self.assertEqual(reopened["status"], "inconclusive")
        replacement = self.handoff(evidence_refs=["ev-contradiction"])
        self.assertNotEqual(replacement.task_id, self.operator.task_id)
        self.assertEqual(replacement.hypothesis_ids, [self.concluded["hypothesis_id"]])
        self.assertEqual(self.board.handoffs()[-1]["hypothesis_revision"], reopened["revision"])
        self.assertTrue(self.board.claim_task(replacement.task_id, "replacement-operator"))
        self.assertTrue(self.board.claim_candidate(self.candidate_key, replacement.task_id, "replacement-operator"))

    def test_reopening_already_inconclusive_candidate_is_rejected(self):
        self.apply_operator(self.reopening())
        self.observation("ev-another-contradiction", status=403)
        self.assert_update_rejected(self.reopening(evidence_refs=("ev-another-contradiction",)))

    def test_reopened_candidate_requires_both_fresh_baseline_and_comparison(self):
        reopened = self.apply_operator(self.reopening())
        self.observation("ev-fresh-baseline", session_ref="synthetic-owner-session")
        self.observation("ev-fresh-comparison", status=403)
        for baseline, comparison in (
            ("ev-baseline", "ev-comparison"),
            ("ev-baseline", "ev-fresh-comparison"),
            ("ev-fresh-baseline", "ev-comparison"),
            ("ev-contradiction", "ev-fresh-comparison"),
        ):
            with self.subTest(baseline=baseline, comparison=comparison):
                self.assert_update_rejected(self.assessment(
                    status="rejected", baseline_evidence_ref=baseline, comparison_evidence_ref=comparison,
                ))
        revised = self.apply_operator(self.assessment(
            status="rejected", baseline_evidence_ref="ev-fresh-baseline",
            comparison_evidence_ref="ev-fresh-comparison",
            assessment="Fresh owner access succeeds and fresh cross-owner access is denied.",
        ))
        self.assertEqual(revised["status"], "rejected")
        self.assertEqual(revised["revision"], reopened["revision"] + 1)
        self.assertEqual(revised["history"][:-1], reopened["history"])
        self.assertGreater(self.board.get_evidence("ev-fresh-baseline").sequence, reopened["reopened_at_sequence"])


class HypothesisSnapshotTests(HypothesisHarness):
    def test_foreign_run_evidence_is_excluded_from_agent_context(self):
        self.observation("ev-foreign", role="scout", session_id="another-run")
        for role in ("scout", "operator"):
            with self.subTest(role=role):
                context = self.board.context_snapshot(role)
                self.assertNotIn("ev-foreign", {item["evidence_id"] for item in context["evidence"]})
                self.assertIn("ev-catalog", {item["evidence_id"] for item in context["evidence"]})
                self.assertTrue(all(item["session_id"] == self.board.session_id for item in context["evidence"]))

    def test_context_keeps_all_old_cited_evidence_beyond_recent_window(self):
        self.conclude_and_reopen()
        self.observation("ev-fresh-baseline", session_ref="synthetic-owner-session")
        self.observation("ev-fresh-comparison", status=403)
        current = self.apply_operator(self.assessment(
            status="rejected", baseline_evidence_ref="ev-fresh-baseline",
            comparison_evidence_ref="ev-fresh-comparison",
            assessment="Fresh owner access works while fresh cross-owner access is denied.",
        ))
        for index in range(30):
            self.observation("ev-recent-" + str(index), path="/api/status")
        cited = set(current["supporting_evidence_refs"])
        recent = {evidence.evidence_id for evidence in self.board.evidence()}
        self.assertEqual(len(recent), 24)
        self.assertTrue(cited.isdisjoint(recent))
        for role in ("scout", "operator"):
            with self.subTest(role=role):
                context = self.board.context_snapshot(role)
                self.assertEqual({item["evidence_id"] for item in context["evidence"]}, cited | recent)
                self.assertEqual(context["hypotheses"], [current])
                self.assertTrue(all(item["session_id"] == self.board.session_id for item in context["evidence"]))

    def test_hypothesis_return_values_are_detached_including_nested_history(self):
        self.ready_operator()
        returned = self.apply_operator(self.assessment())
        expected = copy.deepcopy(returned)
        for label, snapshot in (
            ("apply result", returned),
            ("lookup", self.board.get_hypothesis(self.candidate_key)),
            ("records", self.board.hypotheses()[0]),
            ("context", self.board.context_snapshot("operator")["hypotheses"][0]),
        ):
            with self.subTest(source=label):
                snapshot["status"] = "rejected"
                snapshot["supporting_evidence_refs"].clear()
                snapshot["history"][0]["evidence_refs"].append("forged-ref")
                snapshot["history"][-1]["assessment"] = "forged assessment"
                self.assertEqual(self.board.get_hypothesis(self.candidate_key), expected)

    def test_context_task_and_evidence_snapshots_cannot_mutate_board(self):
        self.ready_operator()
        before_tasks = self.board.tasks()
        before_evidence = self.board.evidence_records()
        context = self.board.context_snapshot("operator")
        context["tasks"][0]["evidence_refs"].clear()
        context["tasks"][0]["hypothesis_ids"].clear()
        context["tasks"][0]["status"] = "completed"
        context["evidence"][0]["body"] = "forged target response"
        context["evidence"].clear()
        self.assertEqual(self.board.tasks(), before_tasks)
        self.assertEqual(self.board.evidence_records(), before_evidence)

    def test_handoff_snapshot_evidence_lists_are_detached(self):
        self.ready_operator()
        expected = copy.deepcopy(self.board.handoffs())
        snapshot = self.board.handoffs()
        snapshot[0]["expected_result"] = "forged prediction"
        snapshot[0]["evidence_refs"].append("forged-ref")
        self.assertEqual(self.board.handoffs(), expected)

    def test_context_handoff_evidence_lists_are_detached(self):
        self.ready_operator()
        expected = copy.deepcopy(self.board.handoffs())
        self.board.context_snapshot("operator")["handoffs"][0]["evidence_refs"].clear()
        self.assertEqual(self.board.handoffs(), expected)

    def test_hypothesis_and_handoff_event_evidence_lists_are_detached(self):
        self.ready_operator()
        self.apply_operator(self.assessment())
        expected = copy.deepcopy(self.board.events())
        for event in self.board.events():
            if event["event_type"].startswith("hypothesis.") or event["event_type"] == "task.handoff":
                event["evidence_refs"].append("forged-ref")
        self.assertEqual(self.board.events(), expected)


if __name__ == "__main__":
    unittest.main()
