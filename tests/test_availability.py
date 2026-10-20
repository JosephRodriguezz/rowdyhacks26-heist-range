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

from red.evaluation.evaluator import evaluate_availability, evaluate_objective, evaluate_ordinary_access_during_load
from red.prototype.actions import ActionExecutor, ActionRejected, ActionResult, FixedTargetRegistry
from red.prototype.availability import run_availability_adaptive
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

    def test_ordinary_access_is_recorded_target_side_and_tagged_by_load_state(self) -> None:
        # Distinct query strings so the action boundary's exact-replay dedup (correct for
        # a literal repeat) does not also swallow these two genuinely different probes --
        # the server ignores the query entirely; /api/catalog's routing is path-only.
        # Idle baseline, before any load exists: tagged load_test_id=None.
        idle = self.act("request_api", path="/api/catalog?probe=baseline")
        self.assertEqual(idle.evidence.status, 200)
        self.assertEqual(self.state.ordinary_access_log[-1]["load_test_id"], None)

        start = self.act("start_load_test")
        load_test_id = json.loads(start.evidence.body)["load_test_id"]
        during = self.act("request_api", path="/api/catalog?probe=during")
        self.assertEqual(during.evidence.status, 200)
        self.assertEqual(self.state.ordinary_access_log[-1]["load_test_id"], load_test_id)
        self.act("stop_load_test")

        # On this lab, /api/status's processing delay and /api/catalog's handling are
        # independent, so ordinary access is expected to hold throughout -- the point of
        # this check is that it is verified, target-side, not assumed. The exact verdict
        # is a real wall-clock latency comparison (see AvailabilityRunnerTests for why
        # this test does not pin "achieved" specifically); what matters here is already
        # covered above -- correct tagging and a real recorded sample either side.
        result = evaluate_ordinary_access_during_load(self.state)
        self.assertIn(result.verdict, ("achieved", "not_achieved"))
        self.assertTrue(result.evidence_refs)

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


class AdaptiveAvailabilityTests(LoadActionHarness):
    """run_availability_adaptive: Red noticing Blue's rate-limiter and retrying the
    identical bounded profile, bounded, honestly labeled, never escalating."""

    def setUp(self) -> None:
        super().setUp()
        # Headroom for multiple full attempts (~9 actions each: baseline probe, start,
        # up to 5 during-load probes, stop, final status).
        self.limits = RunLimits(action_calls=60, model_calls=10, wall_seconds=30, request_timeout_seconds=1,
                                 response_bytes=16_384, model_timeout_seconds=1, max_agent_turns=8)
        self.budget = BudgetLedger(self.limits, self.cancel)
        self.executor.close()
        self.executor = ActionExecutor(
            registry=FixedTargetRegistry(self.server.origin), state=self.state, limits=self.limits,
            budget=self.budget, board=self.board, load_profile=AGGRESSIVE_PROFILE,
        )
        # run_availability_adaptive claims its own task (as "deterministic-adaptive");
        # self.task is already claimed as "scout-test" by the parent setUp for act().
        self.adaptive_task = self.board.add_task("scout", "adaptive availability test task")

    def _events(self, event_type: str) -> list[dict]:
        return [e for e in self.board.events() if e["event_type"] == event_type]

    def test_undefended_run_concludes_without_retrying(self) -> None:
        run_availability_adaptive(
            executor=self.executor, board=self.board, task_id=self.adaptive_task.task_id,
            stop_if_achieved=lambda: False, max_attempts=2, cooldown_seconds=0.05,
        )
        attempts = self._events("availability.adaptive_attempt")
        decisions = self._events("availability.adaptation_decision")
        self.assertEqual(len(attempts), 1)
        self.assertTrue(attempts[0]["saw_degraded"])
        self.assertFalse(attempts[0]["saw_rate_limited"])
        self.assertEqual(decisions[-1]["decision"], "no_retry_needed")
        self.assertEqual(evaluate_availability(self.state).verdict, "achieved")

    def test_defended_run_retries_up_to_the_bound_then_concludes(self) -> None:
        self.state.disable_family(AVAILABILITY_FAMILY)
        run_availability_adaptive(
            executor=self.executor, board=self.board, task_id=self.adaptive_task.task_id,
            stop_if_achieved=lambda: False, max_attempts=2, cooldown_seconds=0.05,
        )
        attempts = self._events("availability.adaptive_attempt")
        decisions = self._events("availability.adaptation_decision")
        # Bounded: never more attempts than max_attempts, no matter how long the defense holds.
        self.assertEqual(len(attempts), 2)
        self.assertTrue(all(a["saw_rate_limited"] and not a["saw_degraded"] for a in attempts))
        self.assertEqual(decisions[0]["decision"], "retry_same_bounded_profile_after_cooldown")
        self.assertEqual(decisions[-1]["decision"], "concluded_mitigation_holds")
        # Red's own narrative agrees with, but never substitutes for, the independent verdict.
        self.assertEqual(evaluate_availability(self.state).verdict, "not_achieved")

    def test_max_attempts_of_one_never_retries_even_when_defended(self) -> None:
        self.state.disable_family(AVAILABILITY_FAMILY)
        run_availability_adaptive(
            executor=self.executor, board=self.board, task_id=self.adaptive_task.task_id,
            stop_if_achieved=lambda: False, max_attempts=1, cooldown_seconds=0.05,
        )
        self.assertEqual(len(self._events("availability.adaptive_attempt")), 1)
        self.assertNotIn("retry_same_bounded_profile_after_cooldown",
                         [d["decision"] for d in self._events("availability.adaptation_decision")])

    def test_max_attempts_below_one_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_availability_adaptive(
                executor=self.executor, board=self.board, task_id=self.adaptive_task.task_id,
                stop_if_achieved=lambda: False, max_attempts=0,
            )

    def test_the_retry_is_the_identical_registered_profile_not_a_larger_one(self) -> None:
        # The adaptation is entirely about *whether/when* Red retries, never about what
        # it asks for: LoadProfile's hard ceiling applies identically to every attempt.
        self.state.disable_family(AVAILABILITY_FAMILY)
        run_availability_adaptive(
            executor=self.executor, board=self.board, task_id=self.adaptive_task.task_id,
            stop_if_achieved=lambda: False, max_attempts=2, cooldown_seconds=0.05,
        )
        self.assertIs(self.executor.load_profile, AGGRESSIVE_PROFILE)


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


class OrdinaryAccessEvaluatorTests(unittest.TestCase):
    """evaluate_ordinary_access_during_load, isolated from any real HTTP or timing --
    this is where the threshold-from-measured-baseline logic itself gets proven, not
    just exercised incidentally by a real run."""

    def test_no_observations_at_all_is_inconclusive(self) -> None:
        state = LabState("availability", seed=1)
        self.assertEqual(evaluate_ordinary_access_during_load(state).verdict, "inconclusive")
        state.close()

    def test_during_load_samples_without_any_idle_baseline_is_inconclusive(self) -> None:
        # No baseline means no threshold can be computed -- this must never fall back to
        # an invented number.
        state = LabState("availability", seed=1)
        state.record_ordinary_access_observation(200, 0.01, "load-x")
        self.assertEqual(evaluate_ordinary_access_during_load(state).verdict, "inconclusive")
        state.close()

    def test_baseline_without_any_during_load_sample_is_inconclusive(self) -> None:
        state = LabState("availability", seed=1)
        state.record_ordinary_access_observation(200, 0.01, None)
        self.assertEqual(evaluate_ordinary_access_during_load(state).verdict, "inconclusive")
        state.close()

    def test_during_load_samples_within_the_baseline_multiple_are_achieved(self) -> None:
        state = LabState("availability", seed=1)
        state.record_ordinary_access_observation(200, 0.01, None)  # baseline
        state.record_ordinary_access_observation(200, 0.02, "load-x")  # 2x baseline, under default 3x
        result = evaluate_ordinary_access_during_load(state)
        self.assertEqual(result.verdict, "achieved")
        self.assertTrue(result.evidence_refs)
        state.close()

    def test_a_during_load_sample_past_the_threshold_is_not_achieved(self) -> None:
        state = LabState("availability", seed=1)
        state.record_ordinary_access_observation(200, 0.01, None)  # baseline
        state.record_ordinary_access_observation(200, 0.05, "load-x")  # 5x baseline, over default 3x
        self.assertEqual(evaluate_ordinary_access_during_load(state).verdict, "not_achieved")
        state.close()

    def test_a_failed_during_load_request_is_not_achieved_even_if_fast(self) -> None:
        # A fast failure is still a failure -- matches the project rule that timeouts and
        # non-200s are never counted as "it still worked."
        state = LabState("availability", seed=1)
        state.record_ordinary_access_observation(200, 0.01, None)  # baseline
        state.record_ordinary_access_observation(503, 0.01, "load-x")
        self.assertEqual(evaluate_ordinary_access_during_load(state).verdict, "not_achieved")
        state.close()

    def test_the_latency_multiplier_is_an_explicit_prototype_default_not_a_calibrated_bank_value(self) -> None:
        # A stricter multiplier correctly flips the same samples to not_achieved -- proof
        # that the threshold is actually derived from the baseline argument, not hardcoded.
        state = LabState("availability", seed=1)
        state.record_ordinary_access_observation(200, 0.01, None)
        state.record_ordinary_access_observation(200, 0.02, "load-x")
        self.assertEqual(evaluate_ordinary_access_during_load(state, latency_multiplier=3.0).verdict, "achieved")
        self.assertEqual(evaluate_ordinary_access_during_load(state, latency_multiplier=1.5).verdict, "not_achieved")
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
        # Degraded/recovered is not the same claim as "ordinary access held throughout" --
        # both are checked and reported, independently, on the same run. This is a real
        # wall-clock latency measurement, not a fixture: asserting the exact achieved/
        # not_achieved outcome here would tie test-passing to this process's momentary
        # scheduling (it shares the GIL with every other test in the suite), which the
        # evaluator is correctly sensitive to by design (fail closed on real contention).
        # What must always hold is that the mechanism actually ran and recorded real
        # target-side samples; evaluate_ordinary_access_during_load's own exact-outcome
        # logic is proven deterministically, with no real timing involved, in
        # OrdinaryAccessEvaluatorTests.
        self.assertIn(report.ordinary_access["verdict"], ("achieved", "not_achieved"))
        self.assertTrue(report.ordinary_access["evidence_refs"])
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
        # The rate-limiter defense only guards /api/status; ordinary access to the
        # unrelated /api/catalog route is unaffected either way. Same real-timing
        # caveat as the undefended test above applies to the exact outcome here.
        self.assertIn(report.ordinary_access["verdict"], ("achieved", "not_achieved"))
        self.assertTrue(report.ordinary_access["evidence_refs"])

    def test_adaptive_mode_runs_through_the_cli_wired_runner_when_defended(self) -> None:
        # End-to-end through PrototypeRunner/RunOptions, not calling
        # run_availability_adaptive directly: proves the actual wiring
        # (availability_max_attempts > 1 routes here instead of the baseline).
        report = PrototypeRunner(RunOptions(
            scenario_id="availability", mode="deterministic_baseline",
            defense_family="availability", defense_after_actions=0,
            availability_max_attempts=2,
            load_profile=LoadProfile(max_requests=30, concurrency=10, duration_seconds=1.5, request_timeout_seconds=1.0),
            limits=RunLimits(action_calls=40, model_calls=5, wall_seconds=30, request_timeout_seconds=2,
                              response_bytes=16_384, model_timeout_seconds=5, max_agent_turns=10),
        )).run()
        self.assertEqual(report.verdict, "not_achieved")
        self.assertEqual(report.availability["verdict"], "not_achieved")
        attempts = [e for e in report.events if e["event_type"] == "availability.adaptive_attempt"]
        decisions = [e for e in report.events if e["event_type"] == "availability.adaptation_decision"]
        self.assertEqual(len(attempts), 2)
        self.assertEqual(decisions[-1]["decision"], "concluded_mitigation_holds")

    def test_default_availability_max_attempts_is_exactly_the_pinned_baseline_behavior(self) -> None:
        # availability_max_attempts defaults to 1, which must route to
        # run_availability_baseline, not run_availability_adaptive -- the pinned
        # byte-hash regression test (test_external_target.py) depends on this.
        report = PrototypeRunner(RunOptions(
            scenario_id="availability", mode="deterministic_baseline",
            load_profile=LoadProfile(max_requests=20, concurrency=8, duration_seconds=1.5, request_timeout_seconds=1.0),
            limits=RunLimits(action_calls=20, model_calls=5, wall_seconds=30, request_timeout_seconds=2,
                              response_bytes=16_384, model_timeout_seconds=5, max_agent_turns=10),
        )).run()
        self.assertFalse(any(e["event_type"].startswith("availability.adapt") for e in report.events))

    def test_a_vault_scenario_run_still_reports_an_empty_availability_score(self) -> None:
        report = PrototypeRunner(RunOptions(scenario_id="access_control", mode="deterministic_baseline")).run()
        self.assertEqual(report.availability["verdict"], "not_achieved")
        # No load test ever runs for a vault scenario, so there is nothing to have an
        # opinion on -- inconclusive, not a silently invented "achieved" or "not_achieved".
        self.assertEqual(report.ordinary_access["verdict"], "inconclusive")
        # The vault verdict is unaffected by the (unused) availability score.
        self.assertIn(report.verdict, ("achieved", "not_achieved", "inconclusive"))


if __name__ == "__main__":
    unittest.main()
