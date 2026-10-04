"""Availability tests use explicit fixtures, not Diego's unbuilt bank."""
import asyncio
import copy
import unittest

from app.agents.blue.availability import AvailabilityError, observe_availability


def window(**changes):
    value = {"window_id": "window-1", "seconds": 2.0, "requests": 100,
             "backend_requests": 100, "server_errors": 40, "denied_requests": 0,
             "inflight": 0, "latency_p95_ms": 800.0, "data_loss": False,
             "sources": [
                 {"source_ref": "client-red", "requests": 96, "backend_requests": 96,
                  "server_errors": 40, "denied_requests": 0, "inflight": 0},
                 {"source_ref": "client-normal", "requests": 4, "backend_requests": 4,
                  "server_errors": 0, "denied_requests": 0, "inflight": 0}]}
    value.update(changes)
    return value


def context(**changes):
    value = {"assessment_id": "run-1", "target_id": "bank-local", "target_version": "bank-v1",
             "data_source": "fixture", "window": window(), "policy": {"baseline_rps": 5.0},
             "budgets": {"max_steps": 5, "timeout_seconds": 10}, "active_source_refs": []}
    value.update(changes)
    return value


class AvailabilityTests(unittest.TestCase):
    def run_blue(self, **changes):
        return asyncio.run(observe_availability(context(**changes)))

    def test_pressure_and_degradation_produce_scoped_source_limit(self):
        result = self.run_blue()
        self.assertEqual(result["assessment"], "suspected_http_flood")
        self.assertEqual(len(result["alerts"]), 1)
        proposal = result["defense_proposals"][0]
        self.assertEqual(proposal["action_type"], "limit_http_source")
        self.assertEqual(proposal["parameters"]["source_ref"], "client-red")
        self.assertEqual(proposal["effect"], "containment")
        self.assertEqual(proposal["data_source"], "fixture")
        self.assertEqual(proposal["target_id"], "bank-local")
        self.assertFalse(result["recovery_verified"])
        self.assertEqual([a["agent_id"] for a in result["agents"]], ["monitor", "defender"])

    def test_healthy_traffic_spike_never_proposes_a_defense(self):
        healthy = window(server_errors=0, latency_p95_ms=10)
        for s in healthy["sources"]: s["server_errors"] = 0
        result = self.run_blue(window=healthy)
        self.assertEqual(result["assessment"], "healthy")
        self.assertEqual(result["alerts"], [])
        self.assertEqual(result["defense_proposals"], [])

    def test_low_rate_outage_is_not_claimed_as_ddos(self):
        outage = window(seconds=100)
        result = self.run_blue(window=outage)
        self.assertEqual(result["assessment"], "availability_degraded_cause_unknown")
        self.assertEqual(result["defense_proposals"], [])

    def test_loss_of_telemetry_is_inconclusive(self):
        result = self.run_blue(window=window(data_loss=True))
        self.assertEqual(result["assessment"], "inconclusive")
        self.assertEqual(result["defense_proposals"], [])

    def test_missing_measurements_are_inconclusive(self):
        empty = window(requests=0, backend_requests=0, server_errors=0, sources=[], latency_p95_ms=None)
        result = self.run_blue(window=empty)
        self.assertEqual(result["assessment"], "inconclusive")

    def test_active_source_is_not_reproposed(self):
        self.assertEqual(self.run_blue(active_source_refs=["client-red"])["defense_proposals"], [])

    def test_source_counts_must_match_window(self):
        with self.assertRaises(AvailabilityError): self.run_blue(window=window(requests=101))

    def test_nonfinite_budgets_and_policy_values_are_rejected(self):
        for bad in (float("nan"), float("inf"), -float("inf"), True):
            with self.subTest(value=bad), self.assertRaises(AvailabilityError):
                self.run_blue(budgets={"max_steps": bad})
            with self.subTest(value=bad), self.assertRaises(AvailabilityError):
                self.run_blue(policy={"baseline_rps": bad})

    def test_exhaustion_and_cancellation_are_not_recovery(self):
        self.assertEqual(self.run_blue(budgets={"max_steps": 0})["assessment"], "inconclusive")
        class Tools:
            def cancelled(self): return True
        result = asyncio.run(observe_availability(context(), Tools()))
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse(result["recovery_verified"])

    def test_no_credentials_or_referee_context_accepted(self):
        for key in ("password", "referee_verdict", "red_plan", "ground_truth", "origin"):
            with self.subTest(key=key), self.assertRaises(AvailabilityError):
                asyncio.run(observe_availability(context(**{key: "private-marker"})))

    def test_proposals_are_deterministic_and_context_is_not_mutated(self):
        ctx = context()
        before = copy.deepcopy(ctx)
        self.assertEqual(asyncio.run(observe_availability(ctx)), asyncio.run(observe_availability(ctx)))
        self.assertEqual(ctx, before)

    def test_limits_are_bounded_not_blanket_blocking(self):
        proposal = self.run_blue()["defense_proposals"][0]
        self.assertGreater(proposal["parameters"]["rate_per_second"], 0)
        self.assertGreaterEqual(proposal["parameters"]["burst"], 1)
        self.assertLessEqual(proposal["parameters"]["ttl_seconds"], 60)


if __name__ == "__main__": unittest.main()
