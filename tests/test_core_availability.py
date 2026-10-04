"""Core uses actual bank libraries and Blue observer, only on owned fixtures."""
import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest

from backend.app.agents.blue.availability import observe_availability
from core.availability import AvailabilityBridge, POLICY, approve_defense, validate_red
from core.service import CoreService
from red.prototype.domain import ActionProposal


NODE = os.environ.get("HEIST_TEST_NODE") or shutil.which("node")
DEPS = Path(__file__).resolve().parents[1] / "apps/bank-lab/node_modules/@electric-sql/pglite"


class AvailabilityPolicyTests(unittest.TestCase):
    def test_red_cannot_override_target_payload_credentials_or_profile(self):
        base = {"capability": "start_load_test", "target_id": "availability-fixture"}
        self.assertEqual(validate_red(base)["capability"], "start_load_test")
        for changes in [{"target_id": "bank-local"}, {"target_id": "bank-lab"}, {"url": "http://outside.invalid"},
                        {"body": {"requests": "1000"}}, {"method": "POST"}, {"path": "/api/login"},
                        {"session_ref": "forged"}, {"profile": {}}, {"capability": "request_api"}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError): validate_red({**base, **changes})

    def test_defense_rederived_from_canonical_window_scope_and_fixed_parameters(self):
        context = {"assessment_id": "contest-1", "target_id": "availability-fixture", "target_version": "baseline-v1",
            "data_source": "fixture", "policy": asdict(POLICY), "window": {"window_id": "window-1", "seconds": .5,
            "requests": 4, "backend_requests": 4, "server_errors": 0, "denied_requests": 0,
            "inflight": 4, "latency_p95_ms": None, "data_loss": False, "sources": [{"source_ref": "load-demo",
            "requests": 4, "backend_requests": 4, "server_errors": 0, "denied_requests": 0, "inflight": 4}]}}
        proposal = asyncio.run(observe_availability(context))["defense_proposals"][0]
        policy = {"rate": 1, "burst": 1, "ttlMs": 3000}
        self.assertEqual(approve_defense(proposal, context, measured_at=1, now=1.1, target_policy=policy), proposal["defense_id"])
        for changes in [{"target_id": "bank-lab"}, {"data_source": "live"}, {"window_digest": "forged"},
                        {"parameters": {**proposal["parameters"], "rate_per_second": 10}},
                        {"parameters": {**proposal["parameters"], "source_ref": "ordinary-demo"}}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                approve_defense({**proposal, **changes}, context, measured_at=1, now=1.1, target_policy=policy)
        with self.assertRaises(ValueError): approve_defense(proposal, context, measured_at=1, now=1.6, target_policy=policy)
        replaced = deepcopy(context); replaced["window"]["window_id"] = "window-2"
        with self.assertRaises(ValueError): approve_defense(proposal, replaced, measured_at=1, now=1.1, target_policy=policy)
        with self.assertRaises(ValueError): approve_defense(proposal, context, measured_at=1, now=1.1, target_policy={**policy, "ttlMs": 10000})

    def test_availability_target_is_opt_in_and_model_or_real_bank_not_registered(self):
        with CoreService() as core:
            self.assertNotIn("availability-fixture", [r["id"] for r in core.targets()["targets"]])
            with self.assertRaises(ValueError): core.create(target_id="availability-fixture", action_id="absent")
        with CoreService(enable_availability_fixture=True) as core:
            with self.assertRaises(ValueError): core.create(target_id="bank-lab", action_id="real")
            with self.assertRaises(ValueError): core.create(target_id="availability-fixture", planner_mode="model", action_id="model")

    def test_interrupted_fixture_history_is_never_reclassified_as_live(self):
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "core.sqlite3")
            with CoreService(db, enable_availability_fixture=True) as core:
                sid = core.create(target_id="availability-fixture", action_id="interrupt-create")["id"]
                core.store.apply(sid, updates={"status": "running"})
            with CoreService(db, enable_availability_fixture=True) as core:
                self.assertEqual(core.status(sid)["status"], "failed")
                self.assertEqual(core.status(sid)["verdict"]["scope"], "availability-recovery")
                self.assertTrue(all(e["data_source"] == "fixture" for e in core.events(sid)["events"]))


@unittest.skipUnless(NODE and DEPS.exists(), "Install locked bank dependencies and set HEIST_TEST_NODE or provide Node on PATH")
class CoreAvailabilityTests(unittest.TestCase):
    def factory(self, fixture_case="normal"):
        return lambda sid: AvailabilityBridge(sid, node=NODE, fixture_case=fixture_case)

    def run_slice(self, core, prefix):
        session = core.create(target_id="availability-fixture", action_id=prefix + "-create")
        core.action(session["id"], "start", action_id=prefix + "-start")
        final = core.wait(session["id"], 15)
        self.assertIn(final["status"], ("completed", "failed"))
        return final

    def test_two_repetitions_actual_blue_and_persistent_private_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "core.sqlite3")
            with CoreService(db, enable_availability_fixture=True, availability_bridge_factory=self.factory()) as core:
                old_id = None
                for i in range(2):
                    final = self.run_slice(core, "repeat-" + str(i)); sid = final["id"]
                    self.assertEqual(final["verdict"]["result"], "achieved")
                    self.assertEqual(final["data_source"], "fixture")
                    self.assertFalse(final["verdict"]["arrest_permitted"])
                    self.assertEqual(core.store.board(sid, "blue")["assessment"], "suspected_http_flood")
                    public = core.events(sid)["events"]
                    self.assertTrue(all(e["data_source"] == "fixture" and e["visibility"] == "judge_safe" for e in public))
                    self.assertTrue(any(e["type"] == "availability.defense.applied" for e in public))
                    text = json.dumps(public)
                    for private in ("bank_session", "Authorization", "customerPassword", "window_digest", "balance_cents"):
                        self.assertNotIn(private, text)
                    with self.assertRaises(KeyError): core.evidence(sid, "availability-referee")
                    private_events = core.store.events(sid, audience="referee_only")["events"]
                    self.assertEqual([e["sequence"] for e in private_events], list(range(1, len(private_events) + 1)))
                    self.assertTrue(any(e["type"] == "bank.target.health" and e["data"].get("active", 0) >= 2 for e in private_events))
                    self.assertTrue(any(e["data"].get("refusal_reason") == "rate_limit" for e in private_events))
                    self.assertLessEqual(sum(e["type"] == "bank.availability.work_started" for e in private_events), 60)
                    if old_id: self.assertEqual(core.status(old_id)["verdict"]["result"], "achieved")
                    old_id = sid
            with CoreService(db, enable_availability_fixture=True) as reopened:
                self.assertEqual(len(reopened.list_sessions()), 2)
                self.assertEqual(reopened.status(old_id)["verdict"]["result"], "achieved")

    def test_denied_ordinary_access_policy_removed_and_expired_stay_inconclusive(self):
        for case in ("ordinary_denied", "capacity_only", "expired"):
            with self.subTest(case=case), CoreService(enable_availability_fixture=True, availability_bridge_factory=self.factory(case)) as core:
                final = self.run_slice(core, "negative-" + case)
                self.assertEqual(final["verdict"]["result"], "inconclusive")
                self.assertFalse(final["verdict"]["arrest_permitted"])

    def test_pause_drains_background_load_stop_resets_without_deleting_history(self):
        with CoreService(enable_availability_fixture=True, availability_bridge_factory=self.factory()) as core:
            sid = core.create(target_id="availability-fixture", action_id="pause-create")["id"]
            core.action(sid, "start", action_id="pause-start")
            runtime = core.runtimes[sid]
            until = time.monotonic() + 10
            while not runtime.load_id and runtime.thread.is_alive() and time.monotonic() < until: time.sleep(.005)
            self.assertTrue(runtime.load_id)
            paused = core.action(sid, "pause", action_id="pause")
            self.assertIn(paused["status"], ("paused", "pausing"))
            time.sleep(.08)
            def work_count():
                return sum(e["type"] == "bank.availability.work_started" for e in core.store.events(sid, audience="referee_only")["events"])
            before = work_count(); time.sleep(.15)
            runtime._call("poll")  # trusted evidence flush only; no target traffic
            self.assertEqual(work_count(), before)
            self.assertEqual(core.action(sid, "resume", action_id="resume")["status"], "running")
            core.action(sid, "stop", action_id="stop")
            final = core.wait(sid, 8)
            self.assertEqual(final["status"], "cancelled")
            self.assertEqual(final["verdict"]["result"], "inconclusive")
            reset = core.action(sid, "reset", action_id="reset")
            self.assertNotEqual(reset["id"], sid)
            self.assertEqual(core.status(sid)["status"], "cancelled")
            self.assertTrue(core.events(sid)["events"])

    def test_bridge_failure_stops_and_cannot_report_recovery(self):
        with CoreService(enable_availability_fixture=True, availability_bridge_factory=self.factory()) as core:
            sid = core.create(target_id="availability-fixture", action_id="failure-create")["id"]
            core.action(sid, "start", action_id="failure-start")
            runtime = core.runtimes[sid]
            until = time.monotonic() + 10
            while not runtime.load_id and runtime.thread.is_alive() and time.monotonic() < until: time.sleep(.005)
            self.assertTrue(runtime.load_id)
            runtime.bridge.process.kill()
            final = core.wait(sid, 8)
            self.assertEqual(final["status"], "failed")
            self.assertEqual(final["verdict"]["result"], "inconclusive")
            self.assertFalse(runtime.thread.is_alive())

    def test_stop_at_referee_and_cleanup_failure_do_not_publish_achieved(self):
        for mode in ("cancel", "cleanup_failure"):
            with self.subTest(mode=mode):
                holder = {}
                class InterceptBridge(AvailabilityBridge):
                    def __init__(self, sid):
                        self.sid, self.referee_seen = sid, False
                        super().__init__(sid, node=NODE)
                    def call(self, op, **fields):
                        if self.referee_seen and op == "stop" and mode == "cleanup_failure":
                            raise ValueError("Fixture cleanup failure")
                        result = super().call(op, **fields)
                        if op == "referee":
                            self.referee_seen = True
                            if mode == "cancel": holder["core"].runtimes[self.sid].gate.stop()
                        return result
                with CoreService(enable_availability_fixture=True, availability_bridge_factory=InterceptBridge) as core:
                    holder["core"] = core
                    final = self.run_slice(core, "terminal-" + mode) if mode != "cancel" else None
                    if mode == "cancel":
                        sid = core.create(target_id="availability-fixture", action_id="terminal-create")["id"]
                        core.action(sid, "start", action_id="terminal-start"); final = core.wait(sid, 15)
                    self.assertEqual(final["verdict"]["result"], "inconclusive")
                    self.assertEqual(final["defense_verification"]["result"], "inconclusive")
                    public = core.events(final["id"])["events"]
                    self.assertFalse(any(e["data"].get("result") == "achieved" for e in public))

    def test_close_during_delayed_startup_waits_for_target_and_store_teardown(self):
        started = threading.Event()
        def factory(sid):
            started.set(); time.sleep(.15)
            return AvailabilityBridge(sid, node=NODE)
        core = CoreService(enable_availability_fixture=True, availability_bridge_factory=factory)
        sid = core.create(target_id="availability-fixture", action_id="delayed-create")["id"]
        core.action(sid, "start", action_id="delayed-start")
        self.assertTrue(started.wait(1))
        core.close()
        runtime = core.runtimes[sid]
        self.assertFalse(runtime.thread.is_alive())
        self.assertIsNotNone(runtime.bridge.process.poll())
        self.assertTrue(core.store._closed)


if __name__ == "__main__": unittest.main()
