"""Local core integration regressions using real workers, Blue, and lab HTTP.

Fixture decisions are explicitly scripted; none of these tests claim remote
model performance. Coordinated providers exercise lifecycle races without
external requests, long sleeps, or changes to production code.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import replace
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from core.fixture import IntegrationFixtureProvider
from core.service import Conflict, CoreService, TERMINAL
from core.store import Store
from red.prototype.domain import ActionProposal, AgentStep, RunLimits


LIMITS = RunLimits(
    wall_seconds=8, request_timeout_seconds=.5, model_timeout_seconds=2,
)
PUBLIC_FORBIDDEN_FIELDS = {
    "body", "request_body", "response_body", "raw_body", "password", "passwd",
    "cookie", "cookies", "set-cookie", "authorization", "access_token",
    "session_token", "seed", "scenario_id", "active_flaws", "ground_truth",
    "seeded_ground_truth", "evaluation_private", "identities", "read_log",
    "target_reads", "control_requests", "boards", "hypotheses", "handoffs",
}
TEAM_FORBIDDEN_FIELDS = {
    "seed", "scenario_id", "active_flaws", "ground_truth", "evaluation_private",
    "read_log", "target_reads", "identities", "password", "cookie", "set-cookie",
}
MAYO_COMMIT = "a5fa4a375628a799198398020d6bf5dbfb8e967a"
MAYO_BLOBS = {
    "backend/app/agents/blue/README.md": "5a2adb10e9b58038a612a9abd7d08ae66a39a807",
    "backend/app/agents/blue/__init__.py": "39ebdcdae14b517a092807834fae0f6941388de8",
    "backend/app/agents/blue/detection.py": "cb947077ca6f791bf136bd9c559b2fa8294b9ff1",
    "backend/app/agents/blue/frameworks.py": "36dae9f17344c575da83b492290f9494e82f15bf",
    "backend/app/agents/blue/incident.py": "2f3521f64ee89f31a06b9c4726d9fb01cdeb1184",
    "backend/app/agents/blue/observe.py": "d49f74d11cdf1f2cd1130acee705be732769a47d",
    "backend/app/agents/blue/patches.py": "8604572e0b209889d901344c7a7d0d57b14365af",
    "backend/app/agents/blue/proposals.py": "08f2db940c84ed6054d68be4706802f2861b5561",
    "backend/app/agents/blue/report.py": "e93d08f6a13b061aec332af62347c5b45ce60df2",
    "backend/tests/blue/blue_test_helpers.py": "6a6dc9c17ecadca2b73f47406c7f0f775d3aaaa7",
    "backend/tests/blue/test_blue_detection.py": "5d52ed7531bce92d02098747f69e8388eb1000b4",
    "backend/tests/blue/test_blue_incident.py": "a18a54d085ffb7516136a33d95facdadbfa2a312",
    "backend/tests/blue/test_blue_observe.py": "3867df4a05f78a6bc1dcd3e8455b2fa23b7efa82",
    "backend/tests/blue/test_blue_patches.py": "0b484720d225db0ceb2d5130bf44549ba32952cc",
    "backend/tests/blue/test_blue_proposals.py": "4ccfd675ed50e8cf5fa2f3609c4a16518cb5ccbe",
    "defenses/patches/ownership-fix-001/manifest.json": "715d4c8802bfd589d533c58f29facfb1c1f39564",
    "shared/contracts/README.md": "48cd7cc32f78bcd16bbe0d986354df836b7566a9",
    "shared/contracts/v1.json": "bde4d3f94044b31e999d729a34851c27f9aa4c7c",
    "shared/fixtures/demo-run.json": "b9896ab4a84af29ab207ed149115e80fc1591952",
}


def finished():
    return AgentStep("finished", "Coordinated test fixture finished.", "")


def act(proposal, *, rationale="Scripted local policy regression."):
    return AgentStep("act", rationale, "", action=proposal)


def object_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key.casefold()
            yield from object_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from object_keys(child)


def evidence_refs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "evidence_refs":
                yield from child
            else:
                yield from evidence_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from evidence_refs(child)


class CoordinatedProvider:
    """Hold exactly one proposal until a test releases it, with bounded cleanup."""

    label = "coordinated_test_fixture"

    def __init__(self, delegate=None, first_step=None):
        self.delegate = delegate
        self.first_step = first_step or act(ActionProposal("read_page"))
        self.entered = threading.Event()
        self.release = threading.Event()
        self.returned = threading.Event()
        self.next_call = threading.Event()
        self.lock = threading.Lock()
        self.calls = 0
        self.threads = []

    def propose(self, **kwargs):
        with self.lock:
            self.calls += 1
            first = self.calls == 1
            self.threads.append(threading.current_thread())
        if first:
            self.entered.set()
            # An assertion failure must not strand a provider computation thread.
            if not self.release.wait(timeout=4):
                raise RuntimeError("test did not release its bounded fixture")
            try:
                return self.delegate.propose(**kwargs) if self.delegate else self.first_step
            finally:
                self.returned.set()
        self.next_call.set()
        return self.delegate.propose(**kwargs) if self.delegate else finished()

    def close(self):
        self.release.set()
        with self.lock:
            threads = list(self.threads)
        for thread in threads:
            thread.join(timeout=1)


class ScriptedProvider:
    label = "policy_test_fixture"

    def __init__(self, proposals=()):
        self.proposals = deque(proposals)
        self.lock = threading.Lock()

    def propose(self, **kwargs):
        with self.lock:
            return act(self.proposals.popleft()) if self.proposals else finished()


class RuntimeTests(unittest.TestCase):
    def service(self, **kwargs):
        # Even an accidental model-mode dispatch cannot contact a provider.
        kwargs.setdefault("provider_factory", Mock(side_effect=AssertionError("remote dispatch forbidden in tests")))
        kwargs.setdefault("limits", LIMITS)
        service = CoreService(**kwargs)
        self.addCleanup(service.close)
        return service

    def coordinated(self, **kwargs):
        provider = CoordinatedProvider(**kwargs)
        # Registered before service cleanup: cancel the runtime before releasing
        # any proposal that the test left held after an assertion failure.
        self.addCleanup(provider.close)
        return provider

    def start(self, service, prefix="run"):
        created = service.create(action_id=prefix + "-create")
        service.action(created["id"], "start", action_id=prefix + "-start")
        return created["id"]

    def ended(self, service, session_id, timeout=4):
        result = service.wait(session_id, timeout=timeout)
        self.assertFalse(service.runtimes[session_id].thread.is_alive(), "contest failed to finish within test bound")
        self.assertIn(result["status"], TERMINAL)
        runtime = service.runtimes[session_id]
        self.assertTrue(all(not worker.is_alive() for worker in runtime.workers), "worker survived terminal commit")
        if runtime.lab:
            self.assertFalse(runtime.lab.thread.is_alive(), "lab server was not cleaned up")
            self.assertTrue(runtime.lab.state._db_closed, "ephemeral lab database was not closed")
        return result

    def until(self, predicate, timeout=2):
        deadline = time.monotonic() + timeout
        tick = threading.Event()
        while not predicate():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.fail("coordinated runtime condition did not become true")
            tick.wait(min(.01, remaining))

    def public_events(self, service, session_id):
        cursor, events = 0, []
        while True:
            page = service.events(session_id, after=cursor)
            events.extend(page["events"])
            if page["last_event_id"] == cursor:
                break
            cursor = page["last_event_id"]
        self.assertEqual(cursor, service.status(session_id)["last_event_id"])
        return events

    def assert_safe(self, payload, forbidden_fields, forbidden_values=()):
        self.assertFalse(set(object_keys(payload)) & forbidden_fields,
                         "restricted fields reached a public/team view")
        rendered = json.dumps(payload, sort_keys=True)
        # Avoid assertNotIn(value, payload): its failure can print credential data.
        self.assertFalse(any(value and value in rendered for value in forbidden_values),
                         "private synthetic material reached a public/team view")

    def test_default_loop_uses_actual_workers_blue_http_and_independent_verification(self):
        service = self.service()
        red_contexts, blue_contexts = [], []
        original_propose = IntegrationFixtureProvider.propose
        from core import service as service_module
        original_observe = service_module.observe

        def record_propose(provider, **kwargs):
            red_contexts.append((kwargs["role"], deepcopy(kwargs["context"])))
            return original_propose(provider, **kwargs)

        async def record_observe(context):
            blue_contexts.append(deepcopy(context))
            return await original_observe(context)

        with patch.object(IntegrationFixtureProvider, "propose", record_propose), \
                patch("core.service.observe", record_observe):
            session_id = self.start(service)
            result = self.ended(service, session_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verdict"]["result"], "achieved")
        self.assertEqual(result["verdict"]["scope"], "historical_vault_disclosure")
        checks = result["defense_verification"]
        self.assertEqual(checks["legitimate_access"], "passed")
        self.assertGreaterEqual(len(checks["containments"]), 1)
        self.assertTrue(any(c["containment"] == "verified" for c in checks["containments"]))
        self.assertTrue(all(c["fresh_session_retry"] == "unauthorized_access_persists" for c in checks["containments"]))
        self.assertEqual(checks["fix_status"], "not_applied")
        self.assertTrue(all(c["fix_status"] == "not_applied" for c in checks["containments"]))
        service.provider_factory.assert_not_called()

        red = service.store.board(session_id, "red")
        self.assertEqual({task["role"] for task in red["tasks"]}, {"scout", "operator"})
        self.assertTrue(all(task["status"] == "completed" for task in red["tasks"]))
        self.assertEqual({task["owner"] for task in red["tasks"]}, {"red-scout", "red-operator"})
        self.assertEqual(len(red["handoffs"]), 1)
        self.assertEqual(len(red["hypotheses"]), 1)
        hypothesis = red["hypotheses"][0]
        self.assertEqual([entry["status"] for entry in hypothesis["history"]],
                         ["inconclusive", "supported", "inconclusive", "supported"])
        self.assertEqual([entry["operation"] for entry in hypothesis["history"]],
                         ["create", "assess", "reopen", "assess"])
        self.assertEqual(red["handoffs"][0]["hypothesis_id"], hypothesis["hypothesis_id"])
        self.assertNotEqual(hypothesis["history"][1]["baseline_evidence_ref"],
                            hypothesis["history"][3]["baseline_evidence_ref"])
        self.assertNotEqual(hypothesis["history"][1]["comparison_evidence_ref"],
                            hypothesis["history"][3]["comparison_evidence_ref"])

        runtime = service.runtimes[session_id]
        with runtime.lab.state.lock:
            private_values = [identity["password"] for identity in runtime.lab.state.identities.values()]
            private_values += list(runtime.lab.state.sessions)
            private_values += [record["content"] for record in runtime.lab.state.records.values()]
        public = self.public_events(service, session_id)
        self.assertTrue(public)
        self.assertTrue(all(event["visibility"] == "judge_safe" for event in public))
        public_evidence = [service.evidence(session_id, ref) for ref in set(evidence_refs([result, public]))]
        self.assert_safe([result, service.list_sessions(), public, public_evidence],
                         PUBLIC_FORBIDDEN_FIELDS, private_values)
        self.assertTrue(all(ref.startswith("public-") for ref in evidence_refs([result, public])))
        self.assertEqual(result["data_source"], "live")
        self.assertEqual(result["planner_mode"], "fixture")
        observed = [event for event in public if event["type"] == "action.observed"]
        self.assertGreater(len(observed), 0)
        self.assertTrue(all(event["data_source"] == "live" for event in observed))
        self.assertTrue(all(event["data"]["execution"] == "local_lab_http" for event in observed))

        blue = service.store.board(session_id, "blue")
        self.assertTrue(blue_contexts)
        self.assertTrue(blue["alerts"])
        self.assertTrue(blue["defense_proposals"])
        self.assert_safe([blue_contexts, blue], TEAM_FORBIDDEN_FIELDS | {"body", "hypotheses", "handoffs", "red_board"},
                         private_values + [hypothesis["statement"], hypothesis["expected_result"]])
        self.assert_safe([context for _, context in red_contexts], TEAM_FORBIDDEN_FIELDS)
        operators = [context for role, context in red_contexts if role == "operator"]
        self.assertTrue(operators)
        scout_evidence = [item for context in operators for item in context["evidence"] if item["role"] == "scout"]
        self.assertTrue(scout_evidence)
        self.assertTrue(all("session_ref" not in item for item in scout_evidence))
        private_events = service.store.events(session_id, audience="red_private", limit=1000)["events"]
        decisions = [event for event in private_events if event["type"] == "agent.decision"]
        self.assertTrue(decisions)
        self.assertTrue(all(event["data_source"] == "fixture" for event in decisions))
        with self.assertRaises(KeyError):
            service.evidence(session_id, red["evidence"][0]["evidence_id"])
        with self.assertRaises(KeyError):
            service.store.evidence(session_id, blue["evidence_refs"][0], audience="red_private")
        self.assertEqual(service.status(session_id), result)
        projected = service.status(session_id)
        projected["verdict"]["result"] = "caller-mutation"
        projected["defense_verification"]["containments"].clear()
        self.assertEqual(service.status(session_id), result)

    def test_clean_scenario_has_no_alerts_defenses_or_verified_disclosure(self):
        service = self.service(scenario_id="clean")
        session_id = self.start(service, "clean")
        result = self.ended(service, session_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verdict"]["result"], "not_achieved")
        self.assertEqual(result["defense_verification"]["legitimate_access"], "passed")
        self.assertEqual(result["defense_verification"]["containments"], [])
        self.assertEqual(result["defense_ids"], [])
        blue = service.store.board(session_id, "blue")
        self.assertEqual(blue["alerts"], [])
        self.assertEqual(blue["defense_proposals"], [])
        audit = service.store.events(session_id, audience="referee_only", limit=1000)["events"]
        self.assertFalse(any(event["type"].startswith(("alert.", "defense.")) for event in audit))
        self.assertEqual(service.store.board(session_id, "red")["hypotheses"][0]["status"], "rejected")

    def test_creation_rejects_unknown_targets_modes_and_missing_remote_opt_in(self):
        service = self.service()
        self.assertEqual([target["id"] for target in service.targets()["targets"]], ["bank-local"])
        for index, kwargs in enumerate((
            {"target_id": "unknown"}, {"target_id": "http://outside.invalid"},
            {"planner_mode": "unknown"}, {"planner_mode": "model"},
        )):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                service.create(action_id=f"invalid-create-{index}", **kwargs)
        self.assertEqual(service.list_sessions(), [])
        for action_id in ("", "with space", "x" * 81, None):
            with self.subTest(action_id=action_id), self.assertRaises(ValueError):
                service.create(action_id=action_id)
        first = service.create(action_id="valid-create")
        with self.assertRaises(Conflict):
            service.create(action_id="busy-create")
        with self.assertRaises(Conflict):
            service.action(first["id"], "pause", action_id="pause-before-start")
        with self.assertRaises(Conflict):
            service.action(first["id"], "unsafe-control", action_id="unsafe-control")
        self.assertEqual(len(service.list_sessions()), 1)
        service.provider_factory.assert_not_called()
        opted_in = self.service(allow_remote_model=True)
        self.assertEqual(opted_in.create(planner_mode="model", action_id="opted-in")["planner_mode"], "model")
        opted_in.provider_factory.assert_not_called()

    def test_unknown_session_ids_fail_without_creating_runtime_or_history(self):
        service = self.service()
        for operation in (
            lambda: service.status("unknown"), lambda: service.events("unknown"),
            lambda: service.evidence("unknown", "unknown"),
            lambda: service.action("unknown", "start", action_id="unknown-session"),
        ):
            with self.assertRaises(KeyError):
                operation()
        self.assertEqual(service.runtimes, {})
        self.assertEqual(service.list_sessions(), [])

    def test_control_idempotency_survives_reload_and_reset_preserves_old_history(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db_path = Path(directory.name) / "runtime.sqlite3"
        service = self.service(db_path=db_path)
        first = service.create(action_id="durable-create")
        session_id = first["id"]
        first["budget"]["caller-mutation"] = True
        repeated = service.create(action_id="durable-create")
        self.assertNotIn("caller-mutation", repeated["budget"])
        with self.assertRaises(Conflict):
            service.create(target_id="unknown", action_id="durable-create")
        started = service.action(session_id, "start", action_id="durable-start")
        runtime = service.runtimes[session_id]
        self.assertEqual(service.action(session_id, "start", action_id="durable-start"), started)
        self.assertIs(service.runtimes[session_id], runtime)
        self.ended(service, session_id)
        self.assertEqual(service.action(session_id, "start", action_id="durable-start"), started)
        with self.assertRaises(Conflict):
            service.action(session_id, "reset", action_id="durable-start")
        old_snapshot = service.store.snapshot(session_id)
        old_events = service.store.events(session_id, audience="referee_only", limit=1000)
        old_board = service.store.board(session_id, "red")
        reset = service.action(session_id, "reset", action_id="durable-reset")
        self.assertNotEqual(reset["id"], session_id)
        self.assertEqual(reset["status"], "created")
        self.assertEqual(service.action(session_id, "reset", action_id="durable-reset"), reset)
        self.assertEqual(service.store.events(session_id, audience="referee_only", limit=1000), old_events)
        self.assertEqual(service.store.board(session_id, "red"), old_board)
        for field in ("status", "verdict", "defense_verification", "last_event_id"):
            self.assertEqual(service.store.snapshot(session_id)[field], old_snapshot[field])
        self.assertEqual(service.store.board(reset["id"], "red"), {})
        self.assertEqual(service.store.board(reset["id"], "blue"), {})
        self.assertEqual(len(service.list_sessions()), 2)
        service.close()
        reopened = self.service(db_path=db_path)
        self.assertEqual(reopened.create(action_id="durable-create"), repeated)
        self.assertEqual(reopened.action(session_id, "start", action_id="durable-start"), started)
        self.assertEqual(reopened.action(session_id, "reset", action_id="durable-reset"), reset)
        self.assertEqual(reopened.store.events(session_id, audience="referee_only", limit=1000), old_events)
        self.assertEqual(reopened.runtimes, {})
        reopened.provider_factory.assert_not_called()

    def test_reset_before_start_retires_reservation_and_is_idempotent(self):
        service = self.service()
        created = service.create(action_id="unstarted-create")
        reset = service.action(created["id"], "reset", action_id="unstarted-reset")
        self.assertNotEqual(created["id"], reset["id"])
        self.assertEqual(service.status(created["id"])["status"], "cancelled")
        self.assertEqual(service.action(created["id"], "reset", action_id="unstarted-reset"), reset)
        self.assertEqual([s["status"] for s in service.list_sessions()], ["cancelled", "created"])
        self.assertEqual(service.runtimes, {})

    def test_failed_create_receipt_rolls_back_session_events_and_reservation(self):
        service = self.service()
        with patch.object(service, "_remember", side_effect=OSError("injected receipt write failure")):
            with self.assertRaises(OSError):
                service.create(action_id="fault-create")
        self.assertEqual(service.list_sessions(), [])
        self.assertEqual(service.runtimes, {})
        created = service.create(action_id="fault-create")
        self.assertEqual(service.create(action_id="fault-create"), created)
        self.assertEqual(len(service.list_sessions()), 1)

    def test_failed_start_receipt_rolls_back_events_state_and_runtime_launch(self):
        service = self.service()
        created = service.create(action_id="start-fault-create")
        session_id = created["id"]
        before = service.store.snapshot(session_id)
        events_before = service.events(session_id)
        try:
            with patch.object(service, "_remember", side_effect=OSError("injected receipt write failure")):
                with self.assertRaises(OSError):
                    service.action(session_id, "start", action_id="fault-start")
            self.assertEqual(service.store.snapshot(session_id), before)
            self.assertEqual(service.events(session_id), events_before)
            self.assertNotIn(session_id, service.runtimes, "failed start retained a phantom runtime")
        finally:
            # If production retains an unstarted thread, remove only that test's
            # ephemeral handle so cleanup does not obscure the original failure.
            runtime = service.runtimes.get(session_id)
            if runtime is not None and runtime.thread.ident is None:
                service.runtimes.pop(session_id)
        # The failed request consumed neither the action ID nor the reservation.
        service.action(session_id, "start", action_id="fault-start")
        result = self.ended(service, session_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verdict"]["result"], "achieved")

    def test_failed_reset_receipt_preserves_old_history_and_does_not_create_new_session(self):
        service = self.service()
        created = service.create(action_id="reset-fault-create")
        before = service.store.snapshot(created["id"])
        events_before = service.events(created["id"])
        with patch.object(service, "_remember", side_effect=OSError("injected receipt write failure")):
            with self.assertRaises(OSError):
                service.action(created["id"], "reset", action_id="fault-reset")
        self.assertEqual(service.store.snapshot(created["id"]), before)
        self.assertEqual(service.events(created["id"]), events_before)
        self.assertEqual(len(service.list_sessions()), 1)
        reset = service.action(created["id"], "reset", action_id="fault-reset")
        self.assertNotEqual(reset["id"], created["id"])

    def test_persistent_runtime_ownership_prevents_another_controller_from_recovering_live_state(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db_path = Path(directory.name) / "owned.sqlite3"
        provider = self.coordinated()
        service = self.service(db_path=db_path, fixture_provider_factory=lambda: provider)
        session_id = self.start(service, "owned")
        self.assertTrue(provider.entered.wait(timeout=2))
        before = service.status(session_id)
        with self.assertRaises(ValueError):
            CoreService(db_path=db_path, limits=LIMITS)
        self.assertEqual(service.status(session_id), before)
        service.action(session_id, "stop", action_id="owned-stop")
        self.assertEqual(self.ended(service, session_id)["status"], "cancelled")
        service.close()
        reopened = self.service(db_path=db_path)
        self.assertEqual(reopened.status(session_id)["status"], "cancelled")
        self.assertEqual(reopened.runtimes, {})

    def test_pause_drains_held_proposal_then_blocks_dispatch_until_resume(self):
        provider = self.coordinated(delegate=IntegrationFixtureProvider())
        service = self.service(fixture_provider_factory=lambda: provider)
        session_id = self.start(service, "pause")
        self.assertTrue(provider.entered.wait(timeout=2), "fixture never reached its coordinated proposal")
        runtime = service.runtimes[session_id]
        original_deadline = runtime.gate.deadline
        with self.assertRaises(Conflict):
            service.create(action_id="busy-running")
        before_reset = service.store.snapshot(session_id)
        with self.assertRaises(Conflict):
            service.action(session_id, "reset", action_id="reset-active")
        self.assertEqual(service.store.snapshot(session_id), before_reset)
        self.assertEqual(len(service.list_sessions()), 1)
        paused = service.action(session_id, "pause", action_id="pause-held")
        self.assertEqual(paused["status"], "pausing")
        self.assertEqual(runtime.gate.deadline, original_deadline)
        provider.release.set()
        self.assertTrue(provider.returned.wait(timeout=1))
        self.until(lambda: service.status(session_id)["status"] == "paused")
        self.assertEqual(runtime.gate.inflight, 0)
        with runtime.lab.state.lock:
            requests_before = list(runtime.lab.state.requests_seen)
        budget_before = runtime.budget.snapshot()
        self.assertFalse(provider.next_call.wait(timeout=.12), "provider dispatched while paused")
        with runtime.lab.state.lock:
            self.assertEqual(runtime.lab.state.requests_seen, requests_before)
        self.assertEqual(runtime.budget.snapshot()["actions_used"], budget_before["actions_used"])
        self.assertEqual(runtime.budget.snapshot()["model_calls_used"], budget_before["model_calls_used"])
        resumed = service.action(session_id, "resume", action_id="resume-held")
        self.assertEqual(resumed["status"], "running")
        self.assertEqual(runtime.gate.deadline, original_deadline)
        result = self.ended(service, session_id)
        self.assertEqual(result["status"], "completed")
        states = [e["data"]["status"] for e in self.public_events(service, session_id)
                  if e["type"] in {"session.running", "session.pausing", "session.paused"}]
        self.assertEqual(states, ["running", "pausing", "paused", "running"])

    def test_paused_contest_expires_at_original_deadline_and_cannot_resume(self):
        provider = self.coordinated()
        service = self.service(limits=replace(LIMITS, wall_seconds=1.2), fixture_provider_factory=lambda: provider)
        session_id = self.start(service, "deadline")
        self.assertTrue(provider.entered.wait(timeout=.8))
        runtime = service.runtimes[session_id]
        deadline = runtime.gate.deadline
        service.action(session_id, "pause", action_id="deadline-pause")
        provider.release.set()
        self.until(lambda: service.status(session_id)["status"] == "paused", timeout=.8)
        self.assertFalse(provider.next_call.wait(timeout=.05))
        result = self.ended(service, session_id, timeout=3)
        self.assertEqual(runtime.gate.deadline, deadline)
        self.assertEqual(result["verdict"]["result"], "inconclusive")
        with self.assertRaises(Conflict):
            service.action(session_id, "resume", action_id="deadline-resume")

    def test_stop_rejects_late_reply_without_mutating_terminal_or_new_contest(self):
        provider = self.coordinated(first_step=act(ActionProposal("read_page", path="/api/catalog"),
                                                 rationale="late-proposal-private-marker"))
        providers = iter((provider, ScriptedProvider()))
        service = self.service(fixture_provider_factory=lambda: next(providers))
        session_id = self.start(service, "stop")
        self.assertTrue(provider.entered.wait(timeout=2))
        stopped = service.action(session_id, "stop", action_id="stop-held")
        self.assertIn(stopped["status"], ("stopping", "cancelled"))
        result = self.ended(service, session_id)
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["verdict"]["result"], "inconclusive")
        old_snapshot = service.store.snapshot(session_id)
        old_events = service.store.events(session_id, audience="referee_only", limit=1000)
        old_board = service.store.board(session_id, "red")
        reset = service.action(session_id, "reset", action_id="stop-reset")
        # The reset request itself is legitimately remembered on the old snapshot.
        old_snapshot = service.store.snapshot(session_id)
        service.action(reset["id"], "start", action_id="new-contest-start")
        self.ended(service, reset["id"])
        new_snapshot = service.store.snapshot(reset["id"])
        new_events = service.store.events(reset["id"], audience="referee_only", limit=1000)
        provider.release.set()
        self.assertTrue(provider.returned.wait(timeout=1))
        provider.close()
        self.assertEqual(service.store.snapshot(session_id), old_snapshot)
        self.assertEqual(service.store.events(session_id, audience="referee_only", limit=1000), old_events)
        self.assertEqual(service.store.board(session_id, "red"), old_board)
        self.assertEqual(service.store.snapshot(reset["id"]), new_snapshot)
        self.assertEqual(service.store.events(reset["id"], audience="referee_only", limit=1000), new_events)
        self.assertFalse(any("late-proposal-private-marker" in json.dumps(item)
                             for item in old_events["events"] + new_events["events"]))

    def test_recovery_ends_interrupted_sessions_without_automatic_workers(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db_path = Path(directory.name) / "recovery.sqlite3"
        interrupted = ("running", "pausing", "paused", "stopping")
        store = Store(db_path)
        try:
            for state in (*interrupted, "created", "completed", "cancelled", "failed"):
                store.create({"id": "saved-" + state, "target_id": "bank-local", "status": state,
                              "verdict": {"result": "inconclusive", "scope": "historical_vault_disclosure"}})
            store.create({"id": "saved-achieved", "target_id": "bank-local", "status": "running",
                          "verdict": {"result": "achieved", "scope": "historical_vault_disclosure"}})
        finally:
            store.close()
        factory = Mock(side_effect=AssertionError("recovery must not construct a planner"))
        service = self.service(db_path=db_path, fixture_provider_factory=factory)
        for state in interrupted:
            with self.subTest(state=state):
                result = service.status("saved-" + state)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["verdict"]["result"], "inconclusive")
                self.assertEqual(result["limitation"], "process_interrupted_no_automatic_resume")
                events = service.events(result["id"])["events"]
                self.assertEqual([e["type"] for e in events], ["session.interrupted"])
                self.assertFalse(events[0]["data"]["resumed"])
        self.assertEqual(service.status("saved-achieved")["verdict"]["result"], "achieved")
        for state in ("created", "completed", "cancelled", "failed"):
            self.assertEqual(service.status("saved-" + state)["status"], state)
            self.assertEqual(service.events("saved-" + state)["events"], [])
        self.assertEqual(service.runtimes, {})
        factory.assert_not_called()
        before = service.list_sessions()
        service.close()
        again = self.service(db_path=db_path, fixture_provider_factory=factory)
        self.assertEqual(again.list_sessions(), before)
        self.assertEqual(again.runtimes, {})
        factory.assert_not_called()

    def test_exhausted_action_or_planner_budget_is_inconclusive(self):
        for name, limits in (("actions", replace(LIMITS, action_calls=4)),
                             ("planner", replace(LIMITS, model_calls=1))):
            with self.subTest(budget=name):
                service = self.service(limits=limits)
                session_id = self.start(service, "exhaust-" + name)
                result = self.ended(service, session_id)
                self.assertEqual(result["verdict"]["result"], "inconclusive")
                self.assertLessEqual(result["budget"]["actions_used"], limits.action_calls)
                self.assertLessEqual(result["budget"]["model_calls_used"], limits.model_calls)
                self.assertEqual(result["defense_verification"]["fix_status"], "not_applied")

    def test_malicious_fixture_actions_are_denied_and_redirect_cannot_leave_lab(self):
        provider = ScriptedProvider((
            ActionProposal("read_page", target_id="unregistered-lab"),
            ActionProposal("request_api", path="http://outside.invalid/api/blocked"),
            ActionProposal("request_api", path="//outside.invalid/api/blocked"),
            ActionProposal("request_api", path="/api/../blocked"),
            ActionProposal("unregistered-capability"),
            ActionProposal("request_api", path="/demo/redirect"),
        ))
        service = self.service(fixture_provider_factory=lambda: provider)
        original_connection = http.client.HTTPConnection
        destinations, forbidden_destinations = [], []

        def only_registered(host, port=None, *args, **kwargs):
            destinations.append((host, port))
            runtime = next(iter(service.runtimes.values()))
            if host != "127.0.0.1" or port != runtime.lab.httpd.server_port:
                forbidden_destinations.append((host, port))
                raise OSError("test denied nonregistered network access")
            return original_connection(host, port, *args, **kwargs)

        with patch("http.client.HTTPConnection", side_effect=only_registered):
            session_id = self.start(service, "policy")
            result = self.ended(service, session_id)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(destinations)
        self.assertEqual(forbidden_destinations, [])
        audit = service.store.events(session_id, audience="referee_only", limit=1000)["events"]
        self.assertEqual(len([e for e in audit if e["type"] == "policy.denied"]), 5)
        red = service.store.board(session_id, "red")
        self.assertEqual(len([e for e in red["evidence"] if e["failure_kind"] == "policy_denial"]), 5)
        redirects = [e for e in red["evidence"] if e["failure_kind"] == "redirect_not_followed"]
        self.assertEqual(len(redirects), 1)
        self.assertEqual(redirects[0]["status"], 302)
        public_evidence = service.evidence(session_id, "public-" + redirects[0]["evidence_id"])
        self.assertEqual(public_evidence["data"]["failure_kind"], "redirect_not_followed")
        requests = service.runtimes[session_id].lab.state.requests_seen
        self.assertEqual(requests.count("/demo/redirect"), 1)
        self.assertFalse(any("blocked" in path or "outside.invalid" in path for path in requests))
        self.assert_safe(self.public_events(service, session_id), PUBLIC_FORBIDDEN_FIELDS)

    def test_provider_exception_fails_closed_without_persisting_private_diagnostic(self):
        class FailingProvider:
            label = "failing_test_fixture"

            def propose(self, **kwargs):
                raise RuntimeError("private-provider-diagnostic-marker")

        service = self.service(fixture_provider_factory=FailingProvider)
        session_id = self.start(service, "provider-failure")
        result = self.ended(service, session_id)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["verdict"]["result"], "inconclusive")
        audit = service.store.events(session_id, audience="referee_only", limit=1000)
        self.assertFalse("private-provider-diagnostic-marker" in json.dumps(audit))
        self.assertFalse("private-provider-diagnostic-marker" in json.dumps(service.store.snapshot(session_id)))
        self.assertFalse("private-provider-diagnostic-marker" in json.dumps(service.store.board(session_id, "red")))

    def test_historical_disclosure_survives_blue_failure_or_cancellation(self):
        from core import service as service_module
        original_observe = service_module.observe

        for mode in ("failure", "cancellation"):
            with self.subTest(mode=mode):
                service = self.service()
                attacked = threading.Event()

                async def interrupt_blue(context):
                    unauthorized = any(
                        record["http_status"] == 200
                        and record["actor_ref"] != record["resource_owner_ref"]
                        for record in context["telemetry"]
                    )
                    if unauthorized and not attacked.is_set():
                        attacked.set()
                        if mode == "failure":
                            raise ValueError("injected Blue failure after delivered disclosure")
                        service.action(context["assessment_id"], "stop", action_id="blue-observed-stop")
                    return await original_observe(context)

                with patch("core.service.observe", interrupt_blue):
                    session_id = self.start(service, "historical-" + mode)
                    result = self.ended(service, session_id)
                self.assertTrue(attacked.is_set(), "test did not reach actual unauthorized target telemetry")
                self.assertEqual(result["verdict"]["result"], "achieved")
                self.assertEqual(result["verdict"]["scope"], "historical_vault_disclosure")
                self.assertEqual(result["status"], "failed" if mode == "failure" else "cancelled")
                public = self.public_events(service, session_id)
                historical = [e for e in public if e["type"] == "referee.verdict"]
                self.assertTrue(historical)
                self.assertTrue(all(e["data"]["result"] == "achieved" for e in historical))
                for ref in evidence_refs(historical):
                    self.assertEqual(service.evidence(session_id, ref)["visibility"], "judge_safe")

    def test_containment_cannot_be_authorized_by_a_forged_telemetry_replica(self):
        from core import service as service_module
        original_observe = service_module.observe
        service = self.service()
        probed, denied, unsafe = threading.Event(), threading.Event(), threading.Event()

        async def attempt_replica(context):
            legitimate = next((record for record in context["telemetry"]
                               if record["http_status"] == 200
                               and record["actor_ref"] == record["resource_owner_ref"]), None)
            if legitimate is not None and not probed.is_set():
                probed.set()
                forged = deepcopy(legitimate)
                forged["actor_ref"] = "fabricated-other-principal"
                proposal = {"defense_id": "forged-replica-defense", "action_type": "revoke_session",
                            "parameters": {"session_ref": legitimate["session_ref"]}}
                runtime = service.runtimes[context["assessment_id"]]
                try:
                    runtime.apply_defense(proposal, [forged])
                except ValueError:
                    denied.set()
                else:
                    unsafe.set()
            return await original_observe(context)

        with patch("core.service.observe", attempt_replica):
            session_id = self.start(service, "forged-telemetry")
            result = self.ended(service, session_id)
        self.assertTrue(probed.is_set(), "test never observed an actual authorized record read")
        self.assertTrue(denied.is_set(), "forged replica authorized containment")
        self.assertFalse(unsafe.is_set())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verdict"]["result"], "achieved")
        self.assertEqual(result["defense_verification"]["legitimate_access"], "passed")
        audit = service.store.events(session_id, audience="referee_only", limit=1000)["events"]
        self.assertFalse(any(e["data"].get("defense_id") == "forged-replica-defense"
                             for e in audit if e["type"] == "defense.applied"))


class MayoSnapshotTests(unittest.TestCase):
    def test_source_manifest_matches_exact_git_blob_bytes_and_covers_blue_modules(self):
        root = Path(__file__).resolve().parents[1] / "integrations" / "mayo"
        manifest = json.loads((root / "source.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "unchanged_runtime_and_test_snapshot")
        self.assertEqual(manifest["repository"], "https://github.com/JosephRodriguezz/rowdyhacks26-heist-range")
        self.assertEqual(manifest["ref"], "Mayo")
        self.assertEqual(manifest["commit"], MAYO_COMMIT)
        files = manifest["files"]
        self.assertTrue(files)
        self.assertEqual(len({entry["path"] for entry in files}), len(files))
        self.assertEqual({entry["path"]: entry["git_blob"] for entry in files}, MAYO_BLOBS)
        for entry in files:
            relative = Path(entry["path"])
            with self.subTest(path=entry["path"]):
                self.assertFalse(relative.is_absolute())
                self.assertNotIn("..", relative.parts)
                contents = (root / relative).read_bytes()
                blob = b"blob " + str(len(contents)).encode("ascii") + b"\0" + contents
                self.assertEqual(hashlib.sha1(blob).hexdigest(), entry["git_blob"],
                                 "vendored source differs from its pinned git blob")
        blue_root = root / "backend" / "app" / "agents" / "blue"
        modules = {path.relative_to(root).as_posix() for path in blue_root.glob("*.py")}
        self.assertTrue(modules)
        self.assertEqual(modules, {entry["path"] for entry in files
                                  if entry["path"].startswith("backend/app/agents/blue/")
                                  and entry["path"].endswith(".py")})


if __name__ == "__main__":
    unittest.main()
