"""Regression checks for the standalone availability (load/recovery) scenario.

These are independent of tests/test_red_prototype.py so that file is never touched by
this feature. The availability score must never leak into, or be confused with, the
vault-access objective checked there.
"""

from __future__ import annotations

import json
import threading
import time
import unittest

from red.evaluation.evaluator import evaluate_availability, evaluate_objective
from red.prototype.actions import ActionExecutor, ActionRejected, ActionResult, FixedTargetRegistry
from red.prototype.board import BudgetLedger, RedBoard
from red.prototype.domain import ActionProposal, LoadProfile, RunLimits
from red.prototype.lab import AVAILABILITY_FAMILY, LabState, LocalBankServer
from red.prototype.runner import PrototypeRunner, RunOptions


AGGRESSIVE_PROFILE = LoadProfile(max_requests=30, concurrency=10, duration_seconds=2.0, request_timeout_seconds=1.0)


class LoadActionHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.state = LabState("availability", seed=17)
        self.server = LocalBankServer(self.state).start()
        self.limits = RunLimits(action_calls=20, model_calls=10, wall_seconds=30, request_timeout_seconds=2,
                                 response_bytes=16_384, model_timeout_seconds=1, max_agent_turns=8)
        self.cancel = threading.Event()
        self.budget = BudgetLedger(self.limits, self.cancel)
        self.board = RedBoard()
        self.task = self.board.add_task("scout", "availability test task")
        self.assertTrue(self.board.claim_task(self.task.task_id, "scout-test"))
        # Keep the lab's default degraded_threshold (4): it must stay above
        # rate_limit_per_second (3) so the defended tests below exercise the real
        # invariant, not a threshold this harness happened to weaken. A slightly longer
        # processing delay just makes the burst's concurrency overlap window reliable.
        self.state.status_processing_seconds = 0.2
        self.executor = ActionExecutor(
            registry=FixedTargetRegistry(self.server.origin), state=self.state, limits=self.limits,
            budget=self.budget, board=self.board, load_profile=AGGRESSIVE_PROFILE,
        )

    def tearDown(self) -> None:
        self.executor.close()
        self.server.close()

    def act(self, capability: str, **kwargs) -> ActionResult:
        return self.executor.execute(
            ActionProposal(capability, path=kwargs.get("path", "/"), method=kwargs.get("method", "GET")),
            role="scout", task_id=self.task.task_id,
        )

    def probe_status(self) -> dict:
        result = self.act("request_api", path="/api/status")
        return json.loads(result.evidence.body)


class StartStopLoadTests(LoadActionHarness):
    def test_start_load_test_degrades_then_recovers_after_stop(self) -> None:
        start = self.act("start_load_test")
        self.assertIsNone(start.evidence.failure_kind)
        self.assertEqual(start.evidence.capability, "start_load_test")
        # Give the background burst a moment to build sustained concurrency.
        time.sleep(0.6)
        self.assertTrue(any(row["label"] == "degraded" for row in self.state.status_log))

        stop = self.act("stop_load_test")
        self.assertIsNone(stop.evidence.failure_kind)
        counts = json.loads(stop.evidence.body)
        self.assertGreater(counts["dispatched"], 0)

        # Recovery: a fresh probe after stopping must observe "available" again.
        time.sleep(0.1)
        recovered = self.probe_status()
        self.assertEqual(recovered["status"], "available")
        self.assertEqual(evaluate_availability(self.state).verdict, "achieved")

    def test_second_start_is_rejected_while_one_load_test_is_active(self) -> None:
        self.act("start_load_test")
        second = self.act("start_load_test")
        self.assertEqual(second.evidence.failure_kind, "load_test_already_active")
        self.act("stop_load_test")

    def test_stop_without_an_active_load_test_is_reported_not_raised(self) -> None:
        result = self.act("stop_load_test")
        self.assertEqual(result.evidence.failure_kind, "no_active_load_test")

    def test_load_actions_reject_any_parameters(self) -> None:
        with self.assertRaises(ActionRejected):
            self.executor.execute(
                ActionProposal("start_load_test", path="/api/status", method="GET"),
                role="scout", task_id=self.task.task_id,
            )
        with self.assertRaises(ActionRejected):
            self.executor.execute(
                ActionProposal("start_load_test", target_id="not-registered"),
                role="scout", task_id=self.task.task_id,
            )

    def test_cancelling_the_run_stops_a_background_burst_promptly(self) -> None:
        self.act("start_load_test")
        time.sleep(0.1)
        started = time.monotonic()
        self.executor.close()  # Simulates run-level cancellation/teardown.
        self.assertLess(time.monotonic() - started, AGGRESSIVE_PROFILE.request_timeout_seconds + 3)


class DefendedAvailabilityTests(LoadActionHarness):
    def test_rate_limited_defense_prevents_degradation_under_the_same_burst(self) -> None:
        self.state.disable_family(AVAILABILITY_FAMILY)
        self.act("start_load_test")
        time.sleep(0.6)
        self.act("stop_load_test")
        self.assertFalse(any(row["label"] == "degraded" for row in self.state.status_log))
        self.assertTrue(any(row["label"] == "rate_limited" for row in self.state.status_log))
        self.assertEqual(evaluate_availability(self.state).verdict, "not_achieved")

    def test_ordinary_single_status_probe_is_unaffected_by_the_defense(self) -> None:
        self.state.disable_family(AVAILABILITY_FAMILY)
        probe = self.probe_status()
        self.assertEqual(probe["status"], "available")


class AvailabilityEvaluatorTests(unittest.TestCase):
    def test_no_degradation_is_not_achieved(self) -> None:
        state = LabState("availability", seed=1)
        self.assertEqual(evaluate_availability(state).verdict, "not_achieved")
        state.close()

    def test_degradation_without_a_later_recovery_is_inconclusive(self) -> None:
        state = LabState("availability", seed=1)
        state.record_status_observation("degraded", "load-x")
        self.assertEqual(evaluate_availability(state).verdict, "inconclusive")
        state.close()

    def test_degradation_followed_by_recovery_is_achieved(self) -> None:
        state = LabState("availability", seed=1)
        state.record_status_observation("degraded", "load-x")
        state.record_status_observation("available", "load-x")
        result = evaluate_availability(state)
        self.assertEqual(result.verdict, "achieved")
        self.assertTrue(result.evidence_refs)
        state.close()

    def test_recovery_recorded_before_degradation_does_not_count(self) -> None:
        state = LabState("availability", seed=1)
        state.record_status_observation("available", None)
        state.record_status_observation("degraded", "load-x")
        self.assertEqual(evaluate_availability(state).verdict, "inconclusive")
        state.close()


class AvailabilityScoreIsolationTests(unittest.TestCase):
    def test_availability_never_counts_as_vault_access(self) -> None:
        state = LabState("availability", seed=1)
        state.record_status_observation("degraded", "load-x")
        state.record_status_observation("available", "load-x")
        self.assertEqual(evaluate_availability(state).verdict, "achieved")
        self.assertEqual(evaluate_objective(state, []).verdict, "not_achieved")
        state.close()

    def test_load_profile_hard_ceiling_is_enforced(self) -> None:
        with self.assertRaises(ValueError):
            LoadProfile(max_requests=1_000)
        with self.assertRaises(ValueError):
            LoadProfile(concurrency=50)
        with self.assertRaises(ValueError):
            LoadProfile(duration_seconds=3_600)


class AvailabilityRunnerTests(unittest.TestCase):
    def test_deterministic_baseline_completes_the_availability_scenario_end_to_end(self) -> None:
        report = PrototypeRunner(RunOptions(
            scenario_id="availability", mode="deterministic_baseline",
            load_profile=LoadProfile(max_requests=20, concurrency=8, duration_seconds=1.5, request_timeout_seconds=1.0),
            limits=RunLimits(action_calls=20, model_calls=5, wall_seconds=30, request_timeout_seconds=2,
                              response_bytes=16_384, model_timeout_seconds=5, max_agent_turns=10),
        )).run()
        self.assertEqual(report.verdict, "achieved")
        self.assertEqual(report.availability["verdict"], "achieved")
        self.assertIn("load_test_id", json.dumps(report.events))

    def test_defended_availability_run_reports_not_achieved(self) -> None:
        report = PrototypeRunner(RunOptions(
            scenario_id="availability", mode="deterministic_baseline",
            defense_family="availability", defense_after_actions=0,
            load_profile=LoadProfile(max_requests=30, concurrency=10, duration_seconds=1.5, request_timeout_seconds=1.0),
            limits=RunLimits(action_calls=20, model_calls=5, wall_seconds=30, request_timeout_seconds=2,
                              response_bytes=16_384, model_timeout_seconds=5, max_agent_turns=10),
        )).run()
        self.assertEqual(report.verdict, "not_achieved")
        self.assertEqual(report.availability["verdict"], "not_achieved")

    def test_a_vault_scenario_run_still_reports_an_empty_availability_score(self) -> None:
        report = PrototypeRunner(RunOptions(scenario_id="access_control", mode="deterministic_baseline")).run()
        self.assertEqual(report.availability["verdict"], "not_achieved")
        # The vault verdict is unaffected by the (unused) availability score.
        self.assertIn(report.verdict, ("achieved", "not_achieved", "inconclusive"))


if __name__ == "__main__":
    unittest.main()
