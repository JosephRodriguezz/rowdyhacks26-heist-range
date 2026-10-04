"""Referee negative regressions using explicitly mocked HTTP/telemetry fixtures.

The separate runtime suite supplies actual loopback HTTP proof. These fixtures
make false-positive cases deterministic without generating additional load.
"""
import asyncio
import unittest
from unittest.mock import patch

from app.agents.blue.availability_guard import ScopedAvailabilityExecutor, _Request
from app.agents.blue.availability_verifier import BankTargetRegistry, IndependentRecoveryVerifier, OrdinaryHTTPProbe
from test_blue_availability_runtime import fixture_guard


class VerificationRegressions(unittest.TestCase):
    def setUp(self):
        self.clock, self.policy, self.guard, _, self.proposal = fixture_guard()
        cookie = self.guard.register_client("ordinary-referee")
        registry = BankTargetRegistry({"bank-reference": {"target_version": "reference-v1", "host": "127.0.0.1",
            "port": 9, "routes": {"home": {"path": "/", "expected_body": b"OK"}}}})
        self.probe = registry.probe("bank-reference", "home", private_cookie=f"heist_lab_client={cookie}")
        self.verifier = IndependentRecoveryVerifier(self.guard, [self.probe], samples=3, interval_seconds=.05)
        self.defense = None
        self.attempts, self.delta, self.application_429, self.content_matches = 5, .1, False, True
        self.refusal_defense = None
        self.probe_patch = patch.object(OrdinaryHTTPProbe, "__call__", side_effect=self.reply)
        self.probe_patch.start()
        self.addCleanup(self.probe_patch.stop)

    def reply(self):
        self.clock.now += self.delta
        if self.defense is not None:
            with self.guard.lock:
                for _ in range(self.attempts):
                    self.guard._request_sequence += 1
                    self.guard._records.append(_Request("source-high-rate", self.clock(), self.application_429,
                        429, 1.0, sequence=self.guard._request_sequence,
                        defense_id=None if self.application_429 else (self.refusal_defense or self.defense)))
        handle, status = self.guard.begin("ordinary-referee")
        assert status is None
        self.guard.finish(handle, 200)
        return {"transport_ok": True, "http_status": 200, "content_matches": self.content_matches, "latency_ms": 1}

    def setup_defense(self):
        self.assertEqual(self.verifier.baseline()["result"], "passed")
        executor = ScopedAvailabilityExecutor(self.guard, self.policy)
        self.defense = asyncio.run(executor.approve(self.proposal))
        executor.apply(self.defense)
        return executor

    def test_application_generated_429s_never_count_as_policy_refusals(self):
        self.setup_defense()
        self.application_429 = True
        result = self.verifier.verify()
        self.assertTrue(result["checks"]["ordinary_access_under_load"])
        self.assertFalse(result["checks"]["continuing_observed_load"])
        self.assertFalse(result["arrest_permitted"])

    def test_low_rate_continuing_requests_do_not_prove_mitigation(self):
        self.setup_defense()
        self.attempts, self.delta = 1, .5
        result = self.verifier.verify()
        self.assertTrue(result["checks"]["ordinary_access_under_load"])
        self.assertFalse(result["checks"]["continuing_observed_load"])

    def test_refusals_from_another_defense_cannot_prove_this_policy(self):
        self.setup_defense()
        self.refusal_defense = "wrong-defense"
        self.assertFalse(self.verifier.verify()["checks"]["continuing_observed_load"])

    def test_mutating_failed_baseline_receipt_cannot_change_private_evidence(self):
        self.content_matches = False
        receipt = self.verifier.baseline()
        self.assertEqual(receipt["result"], "inconclusive")
        receipt["samples"][0]["content_matches"] = True
        self.assertFalse(self.verifier._baseline[0]["content_matches"])
        self.assertFalse(self.verifier.verify()["checks"]["healthy_baseline"])

    def test_mitigation_during_baseline_makes_it_inconclusive(self):
        original = self.reply
        def race():
            result = original()
            self.guard._install(self.proposal)
            return result
        with patch.object(OrdinaryHTTPProbe, "__call__", side_effect=race):
            self.assertEqual(self.verifier.baseline()["result"], "inconclusive")
        self.assertFalse(self.verifier.verify()["checks"]["healthy_baseline"])

    def test_fixture_success_never_authorizes_a_live_arrest(self):
        self.setup_defense()
        result = self.verifier.verify()
        self.assertEqual(result["result"], "passed")
        self.assertEqual(result["data_source"], "fixture")
        self.assertFalse(result["arrest_permitted"])

    def test_referee_requests_are_excluded_from_attacking_load(self):
        self.setup_defense()
        self.guard.rollback(self.defense)
        self.guard._install({**self.proposal, "parameters": {**self.proposal["parameters"],
                            "source_ref": "ordinary-referee"}})
        result = self.verifier.verify()
        self.assertFalse(result["checks"]["continuing_observed_load"])

    def test_expired_baseline_is_inconclusive(self):
        self.setup_defense()
        self.clock.now += 301
        self.assertFalse(self.verifier.verify()["checks"]["healthy_baseline"])

    def test_dropped_records_cannot_certify_recovery(self):
        self.setup_defense()
        self.guard._dropped_until = self.clock() + 1
        result = self.verifier.verify()
        self.assertFalse(result["checks"]["measurement_complete"])
        self.assertFalse(result["arrest_permitted"])


if __name__ == "__main__": unittest.main()
