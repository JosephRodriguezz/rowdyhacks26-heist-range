"""Bounded adversarial availability checks; no HTTP, models, or load generators.

Guard measurements are real in-process admission/completion records. ``fixture``
labels their synthetic unit-test origin; ``live`` cases only exercise scope
validation, not live bank integration. Passing these checks does not establish
DDoS readiness, independent verification, or recovery. Human review is required.

From backend/: python3 -B -m unittest discover -s tests/blue
    -p 'test_blue_availability_adversarial.py' -v
"""
import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
import unittest

from app.agents.blue.availability import (
    AvailabilityError,
    AvailabilityPolicy,
    COUNTS,
    observe_availability,
)
from app.agents.blue.availability_guard import (
    ScopedAvailabilityExecutor,
    TrafficGuard,
)


PRIVATE = "private-unit-test-marker"
POLICY = AvailabilityPolicy(baseline_rps=1.0)


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        if seconds < 0:
            raise ValueError("Test clock must advance monotonically")
        self.now += seconds


def observe(context, tools=None):
    return asyncio.run(observe_availability(context, tools))


def complete(guard, source_ref, count=1, status=500):
    for _ in range(count):
        handle, refusal = guard.begin(source_ref)
        if refusal is not None:
            raise AssertionError("Fixture request unexpectedly refused")
        if not guard.finish(handle, status):
            raise AssertionError("Fixture request did not complete")


def pressure_fixture(*, data_source="fixture", max_records=64, **guard_options):
    clock = FakeClock()
    guard = TrafficGuard(
        "availability-run", "bank-local", "bank-v1", data_source=data_source,
        clock=clock, max_records=max_records, **guard_options,
    )
    # Twenty genuine measurements, rather than a forged aggregate dictionary.
    complete(guard, "client-pressure", count=20, status=500)
    context = guard.sample(POLICY, seconds=2.0)
    return clock, guard, context


class AdversarialAssertions(unittest.TestCase):
    def assert_static_rejection(self, operation, *args, message=None, **kwargs):
        with self.assertRaises(AvailabilityError) as caught:
            operation(*args, **kwargs)
        self.assertNotIn(PRIVATE, str(caught.exception))
        if message is not None:
            self.assertEqual(str(caught.exception), message)
        return caught.exception

    def assert_unverified(self, result):
        self.assertIs(result["recovery_verified"], False)
        self.assertEqual(result["fix_status"], "not_assessed")

    def assert_counts_reconcile(self, context):
        window = context["window"]
        for field in COUNTS:
            self.assertEqual(window[field], sum(row[field] for row in window["sources"]))


class AvailabilityInputAdversarialTests(AdversarialAssertions):
    def setUp(self):
        self.clock, self.guard, self.context = pressure_fixture()
        self.addCleanup(self.guard.close)

    def test_reference_fixture_is_measured_and_scoped(self):
        self.assertEqual(self.context["window"]["requests"], 20)
        self.assertEqual(self.context["window"]["backend_requests"], 20)
        self.assertEqual(self.context["window"]["server_errors"], 20)
        self.assert_counts_reconcile(self.context)
        result = observe(self.context)
        self.assertEqual(result["assessment"], "suspected_http_flood")
        self.assertEqual(len(result["defense_proposals"]), 1)
        self.assertEqual(result["data_source"], "fixture")
        self.assert_unverified(result)

    def test_malformed_top_level_objects_are_static_errors(self):
        for value in (None, [], [self.context], PRIVATE, 7, True):
            with self.subTest(kind=type(value).__name__):
                self.assert_static_rejection(observe, value, message="Malformed availability input")

    def test_nested_scope_and_unhashable_data_source_are_rejected(self):
        for field in ("assessment_id", "target_id", "target_version", "data_source"):
            for value in ([PRIVATE], {"private": PRIVATE}, None, True):
                with self.subTest(field=field, kind=type(value).__name__):
                    context = deepcopy(self.context)
                    context[field] = value
                    self.assert_static_rejection(observe, context)

    def test_non_mapping_window_and_sources_containers_are_rejected(self):
        for value in (None, PRIVATE, [], [self.context["window"]]):
            with self.subTest(container="window", kind=type(value).__name__):
                context = deepcopy(self.context)
                context["window"] = value
                self.assert_static_rejection(observe, context)
        for value in (None, PRIVATE, {}, tuple(self.context["window"]["sources"])):
            with self.subTest(container="sources", kind=type(value).__name__):
                context = deepcopy(self.context)
                context["window"]["sources"] = value
                self.assert_static_rejection(observe, context)

    def test_source_rows_are_validated_before_mapping_access(self):
        for value in (None, PRIVATE, [], 7, True):
            with self.subTest(kind=type(value).__name__):
                context = deepcopy(self.context)
                context["window"]["sources"] = [value]
                self.assert_static_rejection(observe, context, message="Malformed availability input")

    def test_missing_source_fields_raise_static_validation_errors(self):
        for field in self.context["window"]["sources"][0]:
            with self.subTest(field=field):
                context = deepcopy(self.context)
                del context["window"]["sources"][0][field]
                self.assert_static_rejection(observe, context)

    def test_nested_unhashable_source_and_active_references_are_rejected(self):
        for value in ([PRIVATE], {"source": PRIVATE}, None, 17):
            for location in ("source_ref", "active_source_refs"):
                with self.subTest(location=location, kind=type(value).__name__):
                    context = deepcopy(self.context)
                    if location == "source_ref":
                        context["window"]["sources"][0][location] = value
                    else:
                        context[location] = [value]
                    self.assert_static_rejection(observe, context)

    def test_counts_reject_nonfinite_boolean_float_and_nested_values(self):
        bad_values = (float("nan"), float("inf"), -float("inf"), True, 20.0,
                      -1, 1000001, [PRIVATE], {"count": PRIVATE})
        for field in COUNTS:
            for value in bad_values:
                for location in ("window", "source"):
                    with self.subTest(field=field, location=location, kind=type(value).__name__):
                        context = deepcopy(self.context)
                        target = context["window"] if location == "window" else context["window"]["sources"][0]
                        target[field] = value
                        self.assert_static_rejection(observe, context)

    def test_window_duration_and_latency_reject_nonfinite_or_nested_values(self):
        for field in ("seconds", "latency_p95_ms"):
            for value in (float("nan"), float("inf"), -float("inf"), True, [PRIVATE], {"value": PRIVATE}):
                with self.subTest(field=field, kind=type(value).__name__):
                    context = deepcopy(self.context)
                    context["window"][field] = value
                    self.assert_static_rejection(observe, context)

    def test_oversized_numeric_measurements_raise_validation_not_overflow(self):
        for field in ("seconds", "latency_p95_ms"):
            with self.subTest(field=field):
                context = deepcopy(self.context)
                context["window"][field] = 10 ** 400
                self.assert_static_rejection(observe, context)

    def test_all_policy_fields_reject_nonfinite_boolean_and_nested_values(self):
        for field in asdict(POLICY):
            for value in (float("nan"), float("inf"), -float("inf"), True, [PRIVATE], {"value": PRIVATE}):
                with self.subTest(field=field, kind=type(value).__name__):
                    context = deepcopy(self.context)
                    context["policy"][field] = value
                    self.assert_static_rejection(observe, context, message="Invalid availability policy")

    def test_oversized_numeric_policy_raises_validation_not_overflow(self):
        context = deepcopy(self.context)
        context["policy"]["baseline_rps"] = 10 ** 400
        self.assert_static_rejection(observe, context, message="Invalid availability policy")

    def test_policy_bounds_and_integer_fields_are_enforced(self):
        bounds = {
            "baseline_rps": (.09, 10001), "rate_multiplier": (1, 101),
            "min_requests": (0, 100001, 20.0), "min_backend_samples": (0, 100001, 5.0),
            "error_ratio": (0, 1.01), "latency_limit_ms": (0, 60001),
            "inflight_threshold": (0, 1025, 8.0), "suspect_source_rps": (0, 10001),
            "limit_rps": (0, 10.01), "burst": (0, 21, 2.0),
            "ttl_seconds": (0, 61), "max_proposals": (0, 9, 4.0),
        }
        for field, values in bounds.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assert_static_rejection(AvailabilityPolicy, **{field: value})
        self.assert_static_rejection(AvailabilityPolicy, limit_rps=2, suspect_source_rps=2)

    def test_malformed_policy_budget_and_active_containers_are_rejected(self):
        for field in ("policy", "budgets", "active_source_refs"):
            for value in (None, PRIVATE, 7, {"nested": {"private": PRIVATE}}):
                with self.subTest(field=field, kind=type(value).__name__):
                    context = deepcopy(self.context)
                    context[field] = value
                    self.assert_static_rejection(observe, context)

    def test_nonfinite_nested_and_oversized_budgets_are_rejected(self):
        for field in ("max_steps", "max_requests", "timeout_seconds"):
            for label, value in (("nan", float("nan")), ("inf", float("inf")),
                                 ("negative_inf", -float("inf")), ("bool", True),
                                 ("list", [PRIVATE]), ("huge_integer", 10 ** 400)):
                with self.subTest(field=field, value=label):
                    context = deepcopy(self.context)
                    context["budgets"] = {field: value}
                    self.assert_static_rejection(observe, context, message="Invalid availability budget")

    def test_private_unknown_fields_at_every_layer_have_fixed_errors(self):
        layers = (
            ((), "Malformed availability input"),
            (("window",), "Malformed availability input"),
            (("window", "sources", 0), "Malformed availability input"),
            (("policy",), "Invalid availability policy"),
            (("budgets",), "Malformed availability input"),
        )
        for path, message in layers:
            for field in ("password", "authorization", "referee_verdict", "red_plan", "ground_truth"):
                with self.subTest(path=path, field=field):
                    context = deepcopy(self.context)
                    target = context
                    for part in path:
                        target = target[part]
                    target[field] = {"nested": [PRIVATE]}
                    self.assert_static_rejection(observe, context, message=message)

    def test_duplicate_source_rows_do_not_double_count_pressure(self):
        context = deepcopy(self.context)
        context["window"]["sources"].append(deepcopy(context["window"]["sources"][0]))
        for field in COUNTS:
            context["window"][field] *= 2
        self.assert_static_rejection(observe, context, message="Duplicate availability source")

    def test_inconsistent_and_impossible_counters_do_not_produce_proposals(self):
        for field in COUNTS:
            with self.subTest(field=field):
                context = deepcopy(self.context)
                context["window"][field] += 1
                self.assert_static_rejection(observe, context)
        for field, value in (("server_errors", 21), ("backend_requests", 21), ("denied_requests", 1)):
            with self.subTest(impossible=field):
                context = deepcopy(self.context)
                context["window"][field] = value
                context["window"]["sources"][0][field] = value
                self.assert_static_rejection(observe, context)

    def test_source_and_active_reference_lists_are_bounded(self):
        for field in ("sources", "active_source_refs"):
            with self.subTest(field=field):
                context = deepcopy(self.context)
                if field == "sources":
                    row = context["window"]["sources"][0]
                    context["window"]["sources"] = [dict(row, source_ref=f"source-{i}") for i in range(257)]
                else:
                    context[field] = [f"source-{i}" for i in range(257)]
                self.assert_static_rejection(observe, context)

    def test_data_loss_requires_boolean_and_never_claims_recovery(self):
        for value in ("false", 0, 1, None, [], {"flag": PRIVATE}):
            with self.subTest(kind=type(value).__name__):
                context = deepcopy(self.context)
                context["window"]["data_loss"] = value
                self.assert_static_rejection(observe, context)
        context = deepcopy(self.context)
        context["window"]["data_loss"] = True
        result = observe(context)
        self.assertEqual(result["assessment"], "inconclusive")
        self.assertEqual(result["defense_proposals"], [])
        self.assert_unverified(result)

    def test_distributed_low_rate_pressure_has_no_fabricated_source_action(self):
        guard = TrafficGuard("distributed-run", "bank-local", "bank-v1", clock=self.clock, data_source="fixture")
        self.addCleanup(guard.close)
        for i in range(20):
            complete(guard, f"distributed-{i}")
        result = observe(guard.sample(POLICY, seconds=2.0))
        self.assertEqual(result["assessment"], "suspected_http_flood")
        self.assertEqual(len(result["alerts"]), 1)
        self.assertIn("not independently verified", result["alerts"][0]["summary"])
        self.assertEqual(result["defense_proposals"], [])
        self.assert_unverified(result)

    def test_low_rate_outage_is_ambiguous_and_healthy_is_not_recovery(self):
        result = observe(self.guard.sample(POLICY, seconds=100))
        self.assertEqual(result["assessment"], "availability_degraded_cause_unknown")
        self.assertEqual(result["defense_proposals"], [])
        self.assert_unverified(result)
        self.clock.advance(3)
        complete(self.guard, "client-normal", count=5, status=200)
        result = observe(self.guard.sample(POLICY, seconds=2))
        self.assertEqual(result["assessment"], "healthy")
        self.assertEqual(result["defense_proposals"], [])
        self.assert_unverified(result)

    def test_budget_exhaustion_cancellation_and_missing_data_are_not_recovery(self):
        class CancelledTools:
            @staticmethod
            def cancelled():
                return True

        for field in ("max_steps", "max_requests", "timeout_seconds"):
            with self.subTest(field=field):
                context = deepcopy(self.context)
                context["budgets"] = {field: 0}
                result = observe(context)
                self.assertEqual(result["status"], "budget_exhausted")
                self.assertEqual(result["defense_proposals"], [])
                self.assert_unverified(result)
        result = observe(self.context, CancelledTools())
        self.assertEqual(result["status"], "cancelled")
        self.assert_unverified(result)
        self.clock.advance(3)
        result = observe(self.guard.sample(POLICY))
        self.assertEqual(result["assessment"], "inconclusive")
        self.assert_unverified(result)

    def test_observer_only_emits_opaque_source_ref_rules(self):
        proposal = observe(self.context)["defense_proposals"][0]
        self.assertEqual(proposal["action_type"], "limit_http_source")
        self.assertEqual(proposal["parameters"], {
            "source_ref": "client-pressure", "rate_per_second": POLICY.limit_rps,
            "burst": POLICY.burst, "ttl_seconds": POLICY.ttl_seconds,
        })
        for value in ("203.0.113.9", "https://example.invalid", "0.0.0.0/0", "client; command", "../client", "client\n"):
            with self.subTest(source=value):
                context = deepcopy(self.context)
                context["window"]["sources"][0]["source_ref"] = value
                self.assert_static_rejection(observe, context)

    def test_proposal_count_is_capped_and_active_sources_are_excluded(self):
        context = deepcopy(self.context)
        rows = [dict(context["window"]["sources"][0], source_ref=f"source-{i}") for i in range(6)]
        context["window"]["sources"] = rows
        for field in COUNTS:
            context["window"][field] = sum(row[field] for row in rows)
        context["policy"]["max_proposals"] = 2
        context["active_source_refs"] = ["source-0"]
        result = observe(context)
        self.assertEqual([p["parameters"]["source_ref"] for p in result["defense_proposals"]], ["source-1", "source-2"])
        self.assert_unverified(result)


class TrafficGuardAdversarialTests(AdversarialAssertions):
    def setUp(self):
        self.clock = FakeClock()
        self.guard = TrafficGuard("guard-run", "bank-local", "bank-v1", clock=self.clock, data_source="fixture")
        self.addCleanup(self.guard.close)

    def test_guard_constructor_bounds_are_enforced(self):
        for field, values in {
            "max_records": (15, 10001, True, [], float("inf")),
            "max_clients": (1, 257, True, []),
            "max_inflight": (0, 257, True, []),
            "data_source": (["live"], {"mode": "live"}, "LIVE"),
        }.items():
            for value in values:
                with self.subTest(field=field, kind=type(value).__name__):
                    self.assert_static_rejection(TrafficGuard, "run", "bank", "v1", **{field: value})

    def test_record_overflow_is_bounded_and_inconclusive(self):
        clock, guard, _ = pressure_fixture(max_records=16)
        self.addCleanup(guard.close)
        sample = guard.sample(POLICY)
        self.assertEqual(sample["window"]["requests"], 16)
        self.assertIs(sample["window"]["data_loss"], True)
        self.assert_counts_reconcile(sample)
        result = observe(sample)
        self.assertEqual(result["assessment"], "inconclusive")
        self.assertEqual(result["defense_proposals"], [])
        self.assert_unverified(result)
        clock.advance(3)
        complete(guard, "fresh-client", count=5, status=200)
        sample = guard.sample(POLICY)
        self.assertIs(sample["window"]["data_loss"], False)
        self.assertEqual(sample["window"]["requests"], 5)
        self.assert_unverified(observe(sample))

    def test_source_overflow_produces_bounded_incomplete_telemetry(self):
        for i in range(257):
            complete(self.guard, f"source-{i:03d}")
        context = self.guard.sample(POLICY)
        self.assertEqual(len(context["window"]["sources"]), 256)
        self.assertIs(context["window"]["data_loss"], True)
        self.assert_counts_reconcile(context)
        result = observe(context)
        self.assertEqual(result["assessment"], "inconclusive")
        self.assertEqual(result["defense_proposals"], [])
        self.assert_unverified(result)

    def test_evidence_retention_is_bounded_and_evicts_old_handles(self):
        oldest = self.guard.sample(POLICY)["window"]["window_id"]
        for _ in range(32):
            newest = self.guard.sample(POLICY)["window"]["window_id"]
        self.assert_static_rejection(self.guard.evidence, oldest, message="Unknown or stale availability evidence")
        self.assertEqual(self.guard.evidence(newest)["window"]["window_id"], newest)

    def test_inflight_cap_refusals_are_not_backend_errors_or_recovery(self):
        guard = TrafficGuard("inflight-run", "bank-local", "v1", clock=self.clock, max_inflight=2, data_source="fixture")
        self.addCleanup(guard.close)
        first, refusal = guard.begin("client-one")
        self.assertIsNone(refusal)
        second, refusal = guard.begin("client-two")
        self.assertIsNone(refusal)
        refused, status = guard.begin("client-three")
        self.assertEqual(status, 503)
        self.assertFalse(guard.finish(refused, 500))
        context = guard.sample(POLICY)
        self.assertEqual((context["window"]["requests"], context["window"]["backend_requests"],
                          context["window"]["denied_requests"], context["window"]["server_errors"]), (3, 2, 1, 0))
        self.assertEqual(context["window"]["inflight"], 2)
        self.assert_counts_reconcile(context)
        self.assert_unverified(observe(context))
        self.assertTrue(guard.finish(first, 200))
        self.assertTrue(guard.finish(second, 200))
        self.assertFalse(guard.finish(first, 500))

    def test_invalid_sources_and_statuses_are_static_errors(self):
        for value in ([PRIVATE], {"private": PRIVATE}, None, "203.0.113.9", "client\n"):
            with self.subTest(kind=type(value).__name__):
                self.assert_static_rejection(self.guard.begin, value)
                self.assert_static_rejection(self.guard.register_client, value)
        handle, _ = self.guard.begin("ordinary-client")
        for value in (True, 99, 600, 200.0, [PRIVATE], float("nan")):
            with self.subTest(status_kind=type(value).__name__):
                self.assert_static_rejection(self.guard.finish, handle, value, message="Invalid target response status")
        self.assertTrue(self.guard.finish(handle, 200))
        self.assertFalse(self.guard.finish("unissued-handle", 200))

    def test_unhashable_completion_handles_are_safely_refused(self):
        valid_handle, _ = self.guard.begin("ordinary-client")
        for value in ([PRIVATE], {"handle": PRIVATE}):
            with self.subTest(kind=type(value).__name__):
                try:
                    result = self.guard.finish(value, 200)
                except AvailabilityError as error:
                    self.assertNotIn(PRIVATE, str(error))
                else:
                    self.assertIs(result, False)
        self.assertTrue(self.guard.finish(valid_handle, 200))

    def test_unhashable_evidence_handles_fail_as_static_validation_errors(self):
        for value in ([PRIVATE], {"window": PRIVATE}):
            with self.subTest(kind=type(value).__name__):
                self.assert_static_rejection(self.guard.evidence, value)

    def test_evidence_max_age_cannot_be_nonfinite_to_bypass_expiration(self):
        window_id = self.guard.sample(POLICY)["window"]["window_id"]
        self.clock.advance(11)
        for value in (float("inf"), float("nan"), -float("inf"), True, [PRIVATE]):
            with self.subTest(kind=type(value).__name__, value=str(value) if type(value) is float else "typed"):
                self.assert_static_rejection(self.guard.evidence, window_id, max_age=value)

    def test_sample_mutation_cannot_rewrite_stored_evidence(self):
        complete(self.guard, "client-pressure", count=20)
        sample = self.guard.sample(POLICY)
        window_id = sample["window"]["window_id"]
        original = deepcopy(sample)
        sample["window"]["sources"][0]["requests"] = 999
        sample["policy"]["baseline_rps"] = .1
        sample["target_id"] = "arbitrary-target"
        self.assertEqual(self.guard.evidence(window_id), original)
        retrieved = self.guard.evidence(window_id)
        retrieved["window"]["sources"].clear()
        self.assertEqual(self.guard.evidence(window_id), original)

    def test_spoofed_forwarded_and_source_headers_do_not_select_identity(self):
        env = {"REMOTE_ADDR": "127.0.0.1"}
        original = self.guard.source_for(env)
        token = self.guard.register_client("registered-client")
        for headers in (
            {"HTTP_X_FORWARDED_FOR": "203.0.113.9"},
            {"HTTP_FORWARDED": 'for="203.0.113.9"'},
            {"HTTP_X_REAL_IP": "203.0.113.9"},
            {"HTTP_X_SOURCE_REF": "registered-client", "HTTP_X_HEIST_SOURCE": "registered-client"},
            {"HTTP_X_FORWARDED_FOR": token, "HTTP_AUTHORIZATION": token},
            {"HTTP_X_SOURCE_REF": [PRIVATE]},
        ):
            with self.subTest(headers=tuple(headers)):
                self.assertEqual(self.guard.source_for(dict(env, **headers)), original)
        self.assertTrue(original.startswith("peer-"))
        self.assertNotIn("127.0.0.1", original)
        self.assertNotEqual(self.guard.source_for({"REMOTE_ADDR": "127.0.0.2"}), original)

    def test_cookie_token_is_required_and_cannot_be_replaced_by_reference(self):
        token = self.guard.register_client("registered-client")
        peer = {"REMOTE_ADDR": "127.0.0.1"}
        fallback = self.guard.source_for(peer)
        self.assertEqual(self.guard.source_for(dict(peer, HTTP_COOKIE=f"{self.guard.cookie_name}={token}")), "registered-client")
        for cookie in (f"{self.guard.cookie_name}=registered-client", f"{self.guard.cookie_name}={PRIVATE}",
                       f"other_cookie={token}", f"{self.guard.cookie_name}={token}x", "x=" + "a" * 4096,
                       [PRIVATE], {"cookie": PRIVATE}, None):
            with self.subTest(kind=type(cookie).__name__):
                self.assertEqual(self.guard.source_for(dict(peer, HTTP_COOKIE=cookie)), fallback)

    def test_client_registry_is_bounded_and_duplicate_errors_do_not_echo(self):
        guard = TrafficGuard("registry-run", "bank-local", "v1", max_clients=2, clock=self.clock)
        self.addCleanup(guard.close)
        first = guard.register_client(PRIVATE)
        self.assert_static_rejection(guard.register_client, PRIVATE, message="Client reference already registered")
        second = guard.register_client("client-two")
        self.assertNotEqual(first, second)
        self.assert_static_rejection(guard.register_client, "client-three", message="Client registry unavailable")

    def test_tokens_addresses_and_request_secrets_do_not_enter_telemetry(self):
        token = self.guard.register_client("opaque-client-ref")
        env = {"REMOTE_ADDR": "203.0.113.99", "HTTP_COOKIE": f"{self.guard.cookie_name}={token}",
               "HTTP_AUTHORIZATION": PRIVATE, "PATH_INFO": "/" + PRIVATE,
               "QUERY_STRING": "password=" + PRIVATE}
        source = self.guard.source_for(env)
        complete(self.guard, source, count=20)
        context = self.guard.sample(POLICY)
        result = observe(context)
        serialized = json.dumps([context, self.guard.evidence(context["window"]["window_id"]), result])
        for secret in (token, PRIVATE, "203.0.113.99", self.guard.cookie_name):
            self.assertNotIn(secret, serialized)
        self.assertEqual(result["defense_proposals"][0]["parameters"]["source_ref"], "opaque-client-ref")

    def test_closed_guard_refuses_new_work_and_invalidates_handles_and_tokens(self):
        token = self.guard.register_client("registered-client")
        handle, _ = self.guard.begin("registered-client")
        window_id = self.guard.sample(POLICY)["window"]["window_id"]
        self.guard.close()
        self.guard.close()
        self.assertFalse(self.guard.finish(handle, 200))
        refused, status = self.guard.begin("registered-client")
        self.assertEqual(status, 503)
        self.assertFalse(self.guard.finish(refused, 200))
        self.assert_static_rejection(self.guard.sample, POLICY, message="Target guard closed")
        self.assert_static_rejection(self.guard.evidence, window_id, message="Unknown or stale availability evidence")
        self.assert_static_rejection(self.guard.register_client, "new-client", message="Client registry unavailable")
        self.assert_static_rejection(self.guard.rollback, "limit-old", message="Target guard closed")
        self.assertNotEqual(self.guard.source_for({"HTTP_COOKIE": f"{self.guard.cookie_name}={token}"}), "registered-client")


class ScopedExecutorAdversarialTests(AdversarialAssertions):
    def setUp(self):
        self.clock, self.guard, self.context = pressure_fixture()
        self.addCleanup(self.guard.close)
        self.proposal = observe(self.context)["defense_proposals"][0]
        self.executor = ScopedAvailabilityExecutor(self.guard, POLICY)
        self.addCleanup(self.executor.stop)

    def approve(self, proposal=..., executor=None):
        return asyncio.run((executor or self.executor).approve(self.proposal if proposal is ... else proposal))

    def assert_not_installed(self):
        self.assertEqual(self.guard.revision, 0)
        self.assertEqual(self.executor.actions_used, 0)
        self.assertEqual(self.guard.sample(POLICY)["active_source_refs"], [])

    def test_unapproved_ids_commands_and_arbitrary_action_payloads_are_rejected(self):
        for value in ("limit-unapproved", "arbitrary-command", "iptables -F", "https://example.invalid",
                      [PRIVATE], {"command": PRIVATE}, self.proposal):
            with self.subTest(kind=type(value).__name__):
                self.assert_static_rejection(self.executor.apply, value)
        self.assert_not_installed()

    def test_malformed_proposals_cannot_cross_approval_boundary(self):
        for value in (None, [], PRIVATE, True, {"defense_id": [PRIVATE]},
                      {"defense_id": "limit-valid", "window_id": {"private": PRIVATE}}):
            with self.subTest(kind=type(value).__name__):
                self.assert_static_rejection(self.approve, value)
        self.assert_not_installed()

    def test_scope_substitution_is_rejected_for_every_scope_field(self):
        for field, value in (("assessment_id", "other-run"), ("target_id", "other-target"),
                             ("target_version", "bank-v2"), ("data_source", "live")):
            with self.subTest(field=field):
                proposal = deepcopy(self.proposal)
                proposal[field] = value
                self.assert_static_rejection(self.approve, proposal, message="Availability scope mismatch")
        self.assert_not_installed()

    def test_fixture_proposal_cannot_be_approved_as_live_or_recorded_evidence(self):
        for mode in ("live", "recorded"):
            with self.subTest(mode=mode):
                _, guard, context = pressure_fixture(data_source=mode)
                self.addCleanup(guard.close)
                executor = ScopedAvailabilityExecutor(guard, POLICY)
                self.addCleanup(executor.stop)
                self.assert_static_rejection(self.approve, self.proposal, executor, message="Availability scope mismatch")
                relabeled = deepcopy(self.proposal)
                relabeled["data_source"] = mode
                self.assert_static_rejection(self.approve, relabeled, executor,
                                             message="Proposal lacks current canonical availability evidence")
                self.assertEqual(guard.revision, 0)
                canonical = observe(context)["defense_proposals"][0]
                self.assertEqual(self.approve(canonical, executor), canonical["defense_id"])

    def test_manipulated_parameters_digests_ids_and_evidence_are_rejected(self):
        replacements = (
            (("window_digest",), "0" * 64), (("defense_id",), "limit-fabricated"),
            (("evidence_refs",), ["availability-fabricated"]),
            (("parameters", "ttl_seconds"), 60), (("parameters", "rate_per_second"), .1),
            (("parameters", "burst"), 20), (("parameters", "source_ref"), "unobserved-client"),
            (("action_type",), "execute_command"), (("effect",), "remediation"),
        )
        for path, value in replacements:
            with self.subTest(path=path):
                proposal = deepcopy(self.proposal)
                target = proposal
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value
                self.assert_static_rejection(self.approve, proposal,
                                             message="Proposal lacks current canonical availability evidence")
        self.assert_not_installed()

    def test_nested_parameter_and_evidence_objects_are_static_rejections(self):
        for field in ("parameters", "window_digest", "evidence_refs", "window_id"):
            for value in ([PRIVATE], {"nested": PRIVATE}, None):
                with self.subTest(field=field, kind=type(value).__name__):
                    proposal = deepcopy(self.proposal)
                    proposal[field] = value
                    self.assert_static_rejection(self.approve, proposal)
        self.assert_not_installed()

    def test_private_unknown_proposal_fields_are_rejected_without_echo(self):
        for layer in ("proposal", "parameters"):
            for field in ("command", "destination", "ip", "authorization", "referee_verdict"):
                with self.subTest(layer=layer, field=field):
                    proposal = deepcopy(self.proposal)
                    target = proposal if layer == "proposal" else proposal["parameters"]
                    target[field] = {"nested": [PRIVATE]}
                    self.assert_static_rejection(self.approve, proposal,
                                                 message="Proposal lacks current canonical availability evidence")
        self.assert_not_installed()

    def test_forged_reconciled_counters_cannot_replace_canonical_measurements(self):
        forged = deepcopy(self.context)
        for field in ("requests", "backend_requests", "server_errors"):
            forged["window"][field] = 40
            forged["window"]["sources"][0][field] = 40
        self.assert_counts_reconcile(forged)
        proposal = observe(forged)["defense_proposals"][0]
        self.assert_static_rejection(self.approve, proposal,
                                     message="Proposal lacks current canonical availability evidence")
        self.assert_not_installed()

    def test_forged_window_duration_and_policy_cannot_expand_authority(self):
        for layer, field, value in (("window", "seconds", 1), ("policy", "ttl_seconds", 60),
                                    ("policy", "limit_rps", .1), ("policy", "baseline_rps", .1)):
            with self.subTest(layer=layer, field=field):
                forged = deepcopy(self.context)
                forged[layer][field] = value
                proposal = observe(forged)["defense_proposals"][0]
                # Baseline-only changes leave the exact action unchanged; reviewed
                # policy still supplies its rate/TTL and canonical evidence.
                if proposal == self.proposal:
                    self.assertEqual(self.approve(proposal), self.proposal["defense_id"])
                else:
                    self.assert_static_rejection(self.approve, proposal,
                                                 message="Proposal lacks current canonical availability evidence")
        self.assert_not_installed()

    def test_valid_looking_unobserved_source_cannot_be_fabricated_into_rule(self):
        forged = deepcopy(self.context)
        forged["window"]["sources"][0]["source_ref"] = "203-0-113-9"
        proposal = observe(forged)["defense_proposals"][0]
        self.assertEqual(proposal["parameters"]["source_ref"], "203-0-113-9")
        self.assertEqual(set(proposal["parameters"]), {"source_ref", "rate_per_second", "burst", "ttl_seconds"})
        self.assert_static_rejection(self.approve, proposal,
                                     message="Proposal lacks current canonical availability evidence")
        self.assert_not_installed()

    def test_unknown_windows_and_stale_approval_are_rejected(self):
        proposal = deepcopy(self.proposal)
        proposal["window_id"] = "window-unobserved"
        self.assert_static_rejection(self.approve, proposal, message="Unknown or stale availability evidence")
        self.clock.advance(10.001)
        self.assert_static_rejection(self.approve, message="Unknown or stale availability evidence")
        self.assert_not_installed()

    def test_approved_proposal_cannot_be_applied_after_evidence_expires(self):
        defense_id = self.approve()
        self.clock.advance(10.001)
        self.assert_static_rejection(self.executor.apply, defense_id, message="Unknown or stale availability evidence")
        self.assert_not_installed()

    def test_apply_is_approved_only_and_idempotent_with_defensive_copies(self):
        defense_id = self.approve()
        self.assertEqual(self.approve(), defense_id)
        self.assertEqual(self.guard.revision, 0)
        original = self.executor.apply(defense_id)
        self.assertEqual(original["type"], "availability.defense.applied")
        self.assertEqual(original["data"]["effect"], "containment")
        self.assertIs(original["data"]["recovery_verified"], False)
        self.assertEqual(original["data_source"], "fixture")
        original["data"]["recovery_verified"] = True
        original["evidence_refs"].append(PRIVATE)
        repeated = self.executor.apply(defense_id)
        self.assertIs(repeated["data"]["recovery_verified"], False)
        self.assertNotIn(PRIVATE, json.dumps(repeated))
        self.assertEqual((self.guard.revision, self.executor.actions_used), (1, 1))

    def test_mutating_approved_caller_proposal_cannot_change_installed_rule(self):
        proposal = deepcopy(self.proposal)
        defense_id = self.approve(proposal)
        proposal["parameters"].update(source_ref="unobserved-client", rate_per_second=10, ttl_seconds=60)
        proposal["evidence_refs"].append(PRIVATE)
        event = self.executor.apply(defense_id)
        self.assertEqual(event["data"]["expires_after_seconds"], POLICY.ttl_seconds)
        self.assertNotIn(PRIVATE, json.dumps(event))
        self.assertEqual(self.guard.sample(POLICY)["active_source_refs"], ["client-pressure"])
        complete(self.guard, "unobserved-client", count=3, status=200)

    def test_registered_cookie_does_not_whitelist_a_limited_source(self):
        token = self.guard.register_client("client-pressure")
        defense_id = self.approve()
        event = self.executor.apply(defense_id)
        source = self.guard.source_for({"HTTP_COOKIE": f"{self.guard.cookie_name}={token}",
                                       "HTTP_X_FORWARDED_FOR": "203.0.113.9"})
        complete(self.guard, source, count=POLICY.burst, status=200)
        refused, status = self.guard.begin(source)
        self.assertEqual(status, 429)
        self.assertFalse(self.guard.finish(refused, 500))
        complete(self.guard, "ordinary-client", count=3, status=200)
        self.assertNotIn(token, json.dumps([event, self.guard.sample(POLICY)]))

    def test_idempotent_apply_does_not_refill_or_extend_expired_policy(self):
        defense_id = self.approve()
        self.executor.apply(defense_id)
        complete(self.guard, "client-pressure", count=POLICY.burst, status=200)
        self.executor.apply(defense_id)
        _, status = self.guard.begin("client-pressure")
        self.assertEqual(status, 429)
        self.clock.advance(POLICY.ttl_seconds)
        self.executor.apply(defense_id)
        self.assertEqual(self.guard.sample(POLICY)["active_source_refs"], [])
        complete(self.guard, "client-pressure", count=3, status=200)
        self.assertEqual((self.guard.revision, self.executor.actions_used), (1, 1))

    def test_rollback_is_reversible_and_never_reinstalls_on_duplicate_apply(self):
        defense_id = self.approve()
        self.executor.apply(defense_id)
        first = self.executor.rollback(defense_id)
        self.assertTrue(first["data"]["changed"])
        revision = self.guard.revision
        second = self.executor.rollback(defense_id)
        self.assertEqual(second, first)
        self.assertEqual(self.guard.revision, revision)
        first["data"]["policy_revision"] = -1
        self.assertEqual(self.executor.rollback(defense_id), second)
        self.executor.apply(defense_id)
        self.assertEqual(self.guard.sample(POLICY)["active_source_refs"], [])
        complete(self.guard, "client-pressure", count=3, status=200)

    def test_rollback_cannot_act_on_unapproved_or_unapplied_ids(self):
        self.assert_static_rejection(self.executor.rollback, "limit-unknown", message="Unknown availability defense")
        defense_id = self.approve()
        self.assert_static_rejection(self.executor.rollback, defense_id, message="Unknown availability defense")
        self.assert_not_installed()

    def test_exhausted_action_budget_allows_only_idempotent_safety_cleanup(self):
        executor = ScopedAvailabilityExecutor(self.guard, POLICY, max_actions=1)
        self.addCleanup(executor.stop)
        defense_id = self.approve(executor=executor)
        first = executor.apply(defense_id)
        self.assertEqual(executor.apply(defense_id), first)
        cleanup = executor.rollback(defense_id)
        revision = self.guard.revision
        self.assertEqual(executor.rollback(defense_id), cleanup)
        self.assertEqual(self.guard.revision, revision)
        self.assert_static_rejection(executor.rollback, "limit-unapproved", message="Unknown availability defense")
        self.assertEqual(executor.actions_used, 1)
        self.assertEqual(self.guard.sample(POLICY)["active_source_refs"], [])

    def test_approval_budget_cannot_be_expanded_by_new_windows(self):
        executor = ScopedAvailabilityExecutor(self.guard, POLICY, max_actions=1)
        self.addCleanup(executor.stop)
        first = self.approve(executor=executor)
        self.assertEqual(self.approve(executor=executor), first)
        fresh = observe(self.guard.sample(POLICY))["defense_proposals"][0]
        self.assertNotEqual(first, fresh["defense_id"])
        self.assert_static_rejection(self.approve, fresh, executor, message="Availability approval budget exhausted")
        self.assert_static_rejection(self.approve, executor=executor,
                                     message="Newer availability evidence requires a fresh comparison")
        self.assertEqual(self.guard.revision, 0)

    def test_stop_cancellation_deadline_block_writes_but_allow_scoped_cleanup(self):
        for boundary in ("stop", "cancel", "deadline", "close"):
            with self.subTest(boundary=boundary):
                clock, guard, context = pressure_fixture()
                self.addCleanup(guard.close)
                cancelled = [False]
                executor = ScopedAvailabilityExecutor(guard, POLICY, timeout_seconds=30,
                                                       cancelled=lambda: cancelled[0])
                self.addCleanup(executor.stop)
                proposal = observe(context)["defense_proposals"][0]
                defense_id = self.approve(proposal, executor)
                executor.apply(defense_id)
                revision, actions = guard.revision, executor.actions_used
                if boundary == "stop":
                    executor.stop()
                    executor.stop()
                elif boundary == "cancel":
                    cancelled[0] = True
                elif boundary == "deadline":
                    clock.advance(30)
                else:
                    guard.close()
                message = "Target guard closed" if boundary == "close" else "Availability execution stopped or expired"
                self.assert_static_rejection(self.approve, proposal, executor, message=message)
                self.assert_static_rejection(executor.apply, defense_id, message=message)
                if boundary == "close":
                    self.assert_static_rejection(executor.rollback, defense_id, message=message)
                    self.assertEqual(guard.revision, revision)
                else:
                    cleanup = executor.rollback(defense_id)
                    self.assertTrue(cleanup["data"]["changed"])
                    self.assertEqual(executor.rollback(defense_id), cleanup)
                    self.assertEqual(guard.revision, revision + 1)
                    self.assertEqual(guard.sample(POLICY)["active_source_refs"], [])
                    self.assert_static_rejection(executor.rollback, "limit-unapproved",
                                                 message="Unknown availability defense")
                self.assertEqual(executor.actions_used, actions)

    def test_new_healthy_window_invalidates_approved_pressure_without_recovery_claim(self):
        defense_id = self.approve()
        self.clock.advance(3)
        complete(self.guard, "ordinary-client", count=5, status=200)
        healthy = observe(self.guard.sample(POLICY))
        self.assertEqual(healthy["assessment"], "healthy")
        self.assert_unverified(healthy)
        self.assert_static_rejection(self.executor.apply, defense_id,
                                     message="Newer availability evidence requires a fresh comparison")
        self.assert_not_installed()

    def test_other_executor_installation_invalidates_already_approved_source_rule(self):
        other = ScopedAvailabilityExecutor(self.guard, POLICY)
        self.addCleanup(other.stop)
        defense_id = self.approve()
        self.approve(executor=other)
        other.apply(defense_id)
        self.assert_static_rejection(self.executor.apply, defense_id,
                                     message="Proposal lacks current canonical availability evidence")
        self.assertEqual((self.guard.revision, self.executor.actions_used), (1, 0))

    def test_stop_before_first_apply_does_not_install_approved_defense(self):
        defense_id = self.approve()
        self.executor.stop()
        self.assert_static_rejection(self.executor.apply, defense_id, message="Availability execution stopped or expired")
        self.assert_not_installed()

    def test_executor_constructor_rejects_nonfinite_and_unbounded_budgets(self):
        for field, values in {
            "max_actions": (0, 65, True, [], 1.0),
            "timeout_seconds": (0, 301, True, float("nan"), float("inf"), [PRIVATE]),
        }.items():
            for value in values:
                with self.subTest(field=field, kind=type(value).__name__):
                    self.assert_static_rejection(ScopedAvailabilityExecutor, self.guard, POLICY, **{field: value})


if __name__ == "__main__":
    unittest.main()
