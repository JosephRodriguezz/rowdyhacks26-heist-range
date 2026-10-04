"""Bounded real HTTP tests of a reference bank, NOT Diego's future bank.

Only four loopback load workers, <=350 total requests, <=4 seconds. The
reference application's work pool can actually saturate; no outage toggle.
The trusted guard does not know attacker versus ordinary-client roles.
"""
import asyncio
from contextlib import redirect_stdout
import http.client
import io
import json
import threading
import time
import unittest
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

from app.agents.blue.availability import AvailabilityError, AvailabilityPolicy, observe_availability
from app.agents.blue.availability_guard import ScopedAvailabilityExecutor, TrafficGuard
from app.agents.blue.availability_verifier import BankTargetRegistry, IndependentRecoveryVerifier
from app.agents.blue.availability_replay import main as replay


class Clock:
    def __init__(self): self.now = 100.0
    def __call__(self): return self.now


def observe(ctx):
    return asyncio.run(observe_availability(ctx))


def fixture_guard():
    clock = Clock()
    policy = AvailabilityPolicy()
    guard = TrafficGuard("run-1", "bank-reference", "reference-v1", clock=clock, data_source="fixture")
    for _ in range(40):
        handle, refusal = guard.begin("source-high-rate")
        assert refusal is None
        guard.finish(handle, 503)
    context = guard.sample(policy)
    proposal = observe(context)["defense_proposals"][0]
    return clock, policy, guard, context, proposal


class GuardRuntimeTests(unittest.TestCase):
    def test_replay_is_deterministic_explicit_fixture_and_cannot_arrest(self):
        outputs = []
        for _ in range(2):
            stream = io.StringIO()
            with redirect_stdout(stream): self.assertEqual(replay(), 0)
            outputs.append(json.loads(stream.getvalue()))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0]["mode"], "fixture_replay")
        self.assertEqual(outputs[0]["blue"]["data_source"], "fixture")
        self.assertFalse(outputs[0]["live_execution"])
        self.assertFalse(outputs[0]["arrest_permitted"])

    def test_real_bucket_expires_without_an_agent_and_rollback_is_idempotent(self):
        clock, policy, guard, _, proposal = fixture_guard()
        executor = ScopedAvailabilityExecutor(guard, policy, max_actions=1)
        defense = asyncio.run(executor.approve(proposal))
        receipt = executor.apply(defense)
        self.assertFalse(receipt["data"]["recovery_verified"])
        self.assertEqual(executor.apply(defense), receipt)
        for _ in range(policy.burst):
            handle, refusal = guard.begin("source-high-rate")
            self.assertIsNone(refusal)
            guard.finish(handle, 200)
        self.assertEqual(guard.begin("source-high-rate")[1], 429)
        ordinary, refusal = guard.begin("ordinary")
        self.assertIsNone(refusal)
        guard.finish(ordinary, 200)
        clock.now += policy.ttl_seconds + .1
        handle, refusal = guard.begin("source-high-rate")
        self.assertIsNone(refusal)
        guard.finish(handle, 200)
        executor.stop()
        cleanup = executor.rollback(defense)  # allowed even after stop/quota
        self.assertEqual(executor.rollback(defense), cleanup)
        self.assertFalse(cleanup["data"]["changed"])
        self.assertEqual(executor.actions_used, 1)

    def test_stop_preserves_cleanup_but_disallows_new_policy(self):
        _, policy, guard, _, proposal = fixture_guard()
        executor = ScopedAvailabilityExecutor(guard, policy)
        defense = asyncio.run(executor.approve(proposal))
        executor.apply(defense)
        executor.stop()
        with self.assertRaises(AvailabilityError): executor.apply(defense)
        self.assertTrue(executor.rollback(defense)["data"]["changed"])
        self.assertFalse(guard._buckets)
        guard.close()
        with self.assertRaises(AvailabilityError): executor.rollback(defense)

    def test_new_measurement_invalidates_old_approval_without_erasing_history(self):
        clock, policy, guard, context, proposal = fixture_guard()
        executor = ScopedAvailabilityExecutor(guard, policy)
        defense = asyncio.run(executor.approve(proposal))
        clock.now += 3
        guard.sample(policy)
        with self.assertRaises(AvailabilityError): executor.apply(defense)
        self.assertIn(context["window"]["window_id"], guard._windows)
        self.assertEqual(guard.revision, 0)

    def test_policy_cannot_be_forged_between_observation_and_approval(self):
        _, policy, guard, _, proposal = fixture_guard()
        executor = ScopedAvailabilityExecutor(guard, policy)
        for key, value in (("data_source", "live"), ("target_id", "another-target"), ("action_type", "run_shell")):
            with self.subTest(key=key), self.assertRaises(AvailabilityError):
                asyncio.run(executor.approve({**proposal, key: value}))
        proposal["parameters"]["ttl_seconds"] = 60
        with self.assertRaises(AvailabilityError): asyncio.run(executor.approve(proposal))

    def test_records_are_bounded_and_overflow_cannot_prove_a_flood(self):
        guard = TrafficGuard("run-1", "bank-reference", "reference-v1", max_records=16)
        for _ in range(20):
            handle, _ = guard.begin("high-rate")
            guard.finish(handle, 503)
        self.assertEqual(len(guard._records), 16)
        self.assertEqual(observe(guard.sample(AvailabilityPolicy()))["assessment"], "inconclusive")

    def test_private_cookie_does_not_bypass_its_own_limit(self):
        _, policy, guard, _, proposal = fixture_guard()
        secret = guard.register_client("source-high-rate")
        source = guard.source_for({"HTTP_COOKIE": f"heist_lab_client={secret}", "REMOTE_ADDR": "127.0.0.1"})
        executor = ScopedAvailabilityExecutor(guard, policy)
        executor.apply(asyncio.run(executor.approve(proposal)))
        for _ in range(policy.burst):
            handle, _ = guard.begin(source)
            guard.finish(handle, 200)
        self.assertEqual(guard.begin(source)[1], 429)
        serialized = json.dumps(guard.sample(policy))
        self.assertNotIn(secret, serialized)
        self.assertNotIn("127.0.0.1", serialized)

    def test_missing_or_forged_cookie_cannot_open_an_unlimited_peer_bucket(self):
        _, policy, guard, _, proposal = fixture_guard()
        token = guard.register_client("source-high-rate")
        executor = ScopedAvailabilityExecutor(guard, policy)
        executor.apply(asyncio.run(executor.approve(proposal)))
        issued = {"HTTP_COOKIE": f"heist_lab_client={token}", "REMOTE_ADDR": "127.0.0.1"}
        for _ in range(policy.burst):
            handle, status = guard.admit(issued)
            self.assertIsNone(status)
            guard.finish(handle, 200)
        self.assertEqual(guard.admit(issued)[1], 429)
        for cookie in ("", "heist_lab_client=forged", "heist_lab_client=source-high-rate"):
            self.assertEqual(guard.admit({"HTTP_COOKIE": cookie, "REMOTE_ADDR": "127.0.0.1"})[1], 401)

    def test_closing_unstarted_or_partially_consumed_wsgi_response_releases_admission(self):
        guard = TrafficGuard("run-1", "bank-reference", "reference-v1", max_inflight=1)
        token = guard.register_client("normal")
        env = {"HTTP_COOKIE": f"heist_lab_client={token}", "REMOTE_ADDR": "127.0.0.1"}
        def bank(environ, start_response):
            start_response("200 OK", [])
            return [b"OK", b"still OK"]
        wrapped = guard.middleware(bank)
        for started in (False, True):
            response = wrapped(env, lambda *args: None)
            if started: next(response)
            self.assertEqual(len(guard._active), 1)
            response.close()
            response.close()
            self.assertEqual(len(guard._active), 0)


class ThreadedServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    block_on_close = False


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args): pass


class ReferenceBank:
    body = b"Reference bank: ordinary access OK.\n"
    def __init__(self):
        self.work = threading.BoundedSemaphore(2)
        self.mode = "normal"

    def __call__(self, environ, start_response):
        if self.mode == "unauthorized":
            status, body = "401 Unauthorized", b"Login failed.\n"
        elif self.mode == "wrong-content":
            status, body = "200 OK", b"Bank not available; placeholder page.\n"
        elif self.mode == "redirect":
            start_response("302 Found", [("Location", "https://example.invalid/"), ("Content-Length", "0")])
            return [b""]
        elif self.mode == "slow":
            time.sleep(.2)
            status, body = "200 OK", self.body
        elif not self.work.acquire(timeout=.006):
            status, body = "503 Service Unavailable", b"Reference application work pool busy.\n"
        else:
            try:
                time.sleep(.025)  # bounded ordinary work, no outage switch
                status, body = "200 OK", self.body
            finally:
                self.work.release()
        start_response(status, [("Content-Type", "text/plain"), ("Cache-Control", "no-store"),
                                ("Content-Length", str(len(body)))])
        return [body]


class RealHTTPAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.guard = TrafficGuard("http-test", "bank-reference", "reference-v1")
        self.bank = ReferenceBank()
        self.server = make_server("127.0.0.1", 0, self.guard.middleware(self.bank),
                                  server_class=ThreadedServer, handler_class=QuietHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.server_thread.start()
        self.stop_load = threading.Event()
        self.workers = []
        self.load_lock, self.load_count = threading.Lock(), 0
        self.red_cookie = self.guard.register_client("client-load")
        self.normal_cookie = self.guard.register_client("client-ordinary")
        self.policy = AvailabilityPolicy(baseline_rps=2, inflight_threshold=8, ttl_seconds=10)
        self.registry = BankTargetRegistry({"bank-reference": {
            "target_version": "reference-v1", "host": "127.0.0.1", "port": self.server.server_port,
            "routes": {"bank-home": {"path": "/", "expected_body": self.bank.body}}}})
        self.probe = self.registry.probe("bank-reference", "bank-home",
                                         private_cookie=f"heist_lab_client={self.normal_cookie}", timeout=.25)
        self.verifier = IndependentRecoveryVerifier(self.guard, [self.probe], samples=5, interval_seconds=.08,
                                                    cancelled=self.stop_load.is_set)

    def tearDown(self):
        self.stop_load.set()
        for worker in self.workers: worker.join(timeout=1)
        self.guard.close()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=1)

    def start_load(self):
        deadline = time.monotonic() + 4
        def worker():
            while not self.stop_load.is_set() and time.monotonic() < deadline:
                with self.load_lock:
                    if self.load_count >= 350: return
                    self.load_count += 1
                connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=.25)
                try:
                    connection.request("GET", "/", headers={"Cookie": f"heist_lab_client={self.red_cookie}"})
                    connection.getresponse().read(1024)
                except (OSError, http.client.HTTPException):
                    pass  # timeout never counts as a successful defense
                finally:
                    connection.close()
                self.stop_load.wait(.015)
        self.workers = [threading.Thread(target=worker, daemon=True) for _ in range(4)]
        for worker in self.workers: worker.start()

    def mitigate(self):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            context = self.guard.sample(self.policy, seconds=1)
            result = observe(context)
            if result["defense_proposals"] and context["window"]["server_errors"] >= 5:
                proposal = next(p for p in result["defense_proposals"] if p["parameters"]["source_ref"] == "client-load")
                executor = ScopedAvailabilityExecutor(self.guard, self.policy)
                receipt = executor.apply(asyncio.run(executor.approve(proposal)))
                self.assertEqual(receipt["type"], "availability.defense.applied")
                time.sleep(.1)  # allow the bounded burst/in-flight work to finish
                return executor, receipt["data"]["defense_id"]
            time.sleep(.02)
        self.fail("Bounded reference workload did not produce measured pressure and degradation")

    def test_detection_enforcement_and_independent_recovery_during_continuing_load(self):
        self.assertEqual(self.verifier.baseline()["result"], "passed")
        self.start_load()
        self.mitigate()
        before = self.load_count
        verdict = self.verifier.verify()
        self.assertGreater(self.load_count, before)
        self.assertEqual(verdict["result"], "passed", verdict)
        self.assertTrue(verdict["arrest_permitted"])
        self.assertTrue(all(verdict["checks"].values()))
        self.assertEqual(verdict["fix_status"], "not_assessed")
        self.assertTrue(all(s["http_status"] == 200 and s["content_matches"] for s in verdict["samples"]))
        sanitized = json.dumps(verdict)
        self.assertNotIn(self.normal_cookie, sanitized)
        self.assertNotIn(self.red_cookie, sanitized)

    def test_stopped_load_is_not_mitigation_even_if_bank_is_healthy(self):
        self.assertEqual(self.verifier.baseline()["result"], "passed")
        self.start_load()
        self.mitigate()
        self.stop_load.set()
        verdict = self.verifier.verify()
        self.assertFalse(verdict["arrest_permitted"])
        self.assertEqual(verdict["result"], "inconclusive")

    def test_failed_login_and_wrong_200_content_do_not_count_as_recovery(self):
        self.assertEqual(self.verifier.baseline()["result"], "passed")
        self.start_load()
        self.mitigate()
        for mode in ("unauthorized", "wrong-content"):
            self.bank.mode = mode
            verdict = self.verifier.verify()
            self.assertFalse(verdict["checks"]["ordinary_access_under_load"])
            self.assertFalse(verdict["arrest_permitted"])

    def test_no_baseline_and_rollback_cannot_claim_recovery(self):
        self.start_load()
        executor, defense = self.mitigate()
        self.assertFalse(self.verifier.verify()["arrest_permitted"])
        executor.rollback(defense)
        self.assertFalse(self.verifier.verify()["arrest_permitted"])

    def test_redirect_is_not_followed_or_accepted(self):
        self.bank.mode = "redirect"
        result = self.probe()
        self.assertEqual(result["http_status"], 302)
        self.assertFalse(result["content_matches"])

    def test_timeout_has_a_total_deadline_and_is_inconclusive(self):
        self.bank.mode = "slow"
        probe = self.registry.probe("bank-reference", "bank-home", timeout=.05,
                                    private_cookie=f"heist_lab_client={self.normal_cookie}")
        started = time.monotonic()
        result = probe()
        self.assertLess(time.monotonic() - started, .15)
        self.assertFalse(result["transport_ok"])
        self.assertFalse(result["content_matches"])

    def test_healthy_app_at_wrong_origin_cannot_supply_the_baseline(self):
        # Same target label/content but no attacked guard on this second server.
        other = make_server("127.0.0.1", 0, self.bank, server_class=ThreadedServer, handler_class=QuietHandler)
        thread = threading.Thread(target=other.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        try:
            registry = BankTargetRegistry({"bank-reference": {"target_version": "reference-v1",
                       "host": "127.0.0.1", "port": other.server_port,
                       "routes": {"bank-home": {"path": "/", "expected_body": self.bank.body}}}})
            probe = registry.probe("bank-reference", "bank-home", private_cookie=f"heist_lab_client={self.normal_cookie}")
            verifier = IndependentRecoveryVerifier(self.guard, [probe])
            self.assertEqual(verifier.baseline()["result"], "inconclusive")
            self.assertFalse(verifier.verify()["arrest_permitted"])
        finally:
            other.shutdown()
            other.server_close()
            thread.join(timeout=1)

    def test_blocking_everyone_fails_the_ordinary_access_check(self):
        self.assertEqual(self.verifier.baseline()["result"], "passed")
        self.start_load()
        self.mitigate()
        # Deliberately invalid defense injection, test-only. Blue/executor can
        # never approve this rule without canonical evidence of that source.
        with self.guard.lock:
            self.guard._install({"defense_id": "invalid-blanket-response", "parameters": {
                "source_ref": "client-ordinary", "rate_per_second": .1, "burst": 1, "ttl_seconds": 10}})
        verdict = self.verifier.verify()
        self.assertFalse(verdict["checks"]["ordinary_access_under_load"])
        self.assertFalse(verdict["arrest_permitted"])

    def test_fixed_registry_rejects_arbitrary_destinations_and_routes(self):
        with self.assertRaises(AvailabilityError): self.registry.probe("not-registered", "bank-home")
        with self.assertRaises(AvailabilityError): self.registry.probe("bank-reference", "https-example")
        for host in ("example.com", "192.0.2.1", "0.0.0.0", "localhost"):
            config = {"bank-reference": {"target_version": "reference-v1", "host": host, "port": 80,
                      "routes": {"home": {"path": "/", "expected_body": b"OK"}}}}
            with self.subTest(host=host), self.assertRaises(ValueError): BankTargetRegistry(config)


if __name__ == "__main__": unittest.main()
