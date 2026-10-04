"""Opt-in disposable availability slice; trusted core dispatch and persistence.

Uses the actual bank capacity/account libraries over owned loopback HTTP and
Joseph's deterministic Blue observer. Decisions and all target records remain
fixture-labeled. No arbitrary origin, real-bank option, remote model, or live
arrest is available through this preparation runtime.
"""
import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

from backend.app.agents.blue.availability import AvailabilityPolicy, _observe_availability, observe_availability
from red.prototype.domain import ActionProposal
from red.prototype.board import BudgetExceeded, RunCancelled
from .gate import DispatchGate


TARGET = "availability-fixture"
VERSION = "baseline-v1"
POLICY = AvailabilityPolicy(baseline_rps=1, rate_multiplier=2, min_requests=4,
    min_backend_samples=2, latency_limit_ms=400, inflight_threshold=2,
    suspect_source_rps=4, limit_rps=1, burst=1, ttl_seconds=3, max_proposals=1)


def validate_red(proposal):
    """Aaron's existing typed action, restricted to this explicit registration."""
    value = ActionProposal.from_mapping(proposal) if type(proposal) is dict else proposal
    if (not isinstance(value, ActionProposal) or value.target_id != TARGET or
        value.capability not in {"start_load_test", "stop_load_test"} or
        value.path != "/" or value.method != "GET" or value.body or
        any(getattr(value, field) is not None for field in ("identity_ref", "session_ref", "form_ref"))):
        raise ValueError("Availability action violates the fixed registry")
    return asdict(value)


def approve_defense(proposal, canonical, *, measured_at, target_policy, now=None):
    """Re-derive exact proposal from current private canonical target evidence."""
    now = time.monotonic() if now is None else now
    if (not 0 <= now - measured_at <= .5 or canonical.get("target_id") != TARGET or
        canonical.get("data_source") != "fixture" or canonical.get("policy") != asdict(POLICY) or
        target_policy != {"rate": POLICY.limit_rps, "burst": POLICY.burst, "ttlMs": POLICY.ttl_seconds * 1000} or
        proposal not in _observe_availability(canonical)["defense_proposals"] or
        proposal.get("parameters", {}).get("source_ref") != "load-demo"):
        raise ValueError("Defense lacks current canonical approved evidence")
    return proposal["defense_id"]


class AvailabilityBridge:
    """Private bounded process protocol; child owns fixture lifetime and secrets."""
    def __init__(self, assessment_id, *, node=None, fixture_case="normal"):
        executable = node or shutil.which("node")
        if not executable:
            raise ValueError("Node runtime is required for the disposable bank")
        script = Path(__file__).resolve().parents[1] / "apps/bank-lab/integration/core-bridge.mjs"
        env = {key: value for key, value in os.environ.items() if key in
               {"PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME"}}
        self.process = subprocess.Popen([executable, str(script), assessment_id, fixture_case],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.lock, self.responses = threading.RLock(), queue.Queue(maxsize=4)
        self.sequence, self.closed = 0, False
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            self.ready = self._receive(10)
            if self.ready.get("ready") is not True or self.ready.get("target_id") != TARGET or self.ready.get("data_source") != "fixture":
                raise ValueError("Fixture registration failed")
        except Exception:
            self.close(); raise ValueError("Fixture registration failed") from None

    def _read(self):
        try:
            while True:
                raw = self.process.stdout.readline(131073)
                if not raw or len(raw) > 131072 or not raw.endswith(b"\n"):
                    break
                value = json.loads(raw)
                if type(value) is not dict:
                    break
                self.responses.put(value, timeout=1)
        except (ValueError, OSError, queue.Full):
            pass
        finally:
            try: self.responses.put(None, timeout=1)
            except queue.Full: pass

    def _receive(self, seconds):
        try: value = self.responses.get(timeout=seconds)
        except queue.Empty: raise ValueError("Private fixture bridge timed out") from None
        if value is None:
            raise ValueError("Private fixture bridge closed")
        return value

    def call(self, op, **fields):
        with self.lock:
            if self.closed: raise ValueError("Private fixture bridge closed")
            self.sequence += 1
            request = json.dumps({"id": self.sequence, "op": op, **fields}, allow_nan=False).encode() + b"\n"
            if len(request) > 16384: raise ValueError("Private command exceeds bound")
            try:
                self.process.stdin.write(request); self.process.stdin.flush()
                result = self._receive(2)
            except (OSError, ValueError):
                self.close(); raise ValueError("Private fixture operation failed") from None
            if result.get("id") != self.sequence or result.get("ok") is not True:
                raise ValueError("Private fixture operation failed")
            return result

    def close(self):
        with self.lock:
            if self.closed: return
            self.closed = True
            try: self.process.stdin.close()
            except OSError: pass
            try: self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=2)
            self.process.stdout.close()
            self.reader.join(timeout=.2)


class AvailabilityGate(DispatchGate):
    def __init__(self, runtime):
        super().__init__(15, runtime.cancel, runtime.changed)
        self.runtime = runtime

    def pause(self):
        with self.condition:
            self._check()
            if self.state != "running": raise ValueError("Pause requires running")
            if self.runtime.bridge:
                self.runtime._call("pause")
            super().pause()

    def resume(self):
        with self.condition:
            self._check()
            if self.runtime.bridge:
                self.runtime._call("resume")
            super().resume()


class AvailabilityRuntime:
    def __init__(self, service, session_id, planner_mode):
        if planner_mode != "fixture": raise ValueError("Availability fixture does not run remote models")
        self.service, self.store, self.session_id = service, service.store, session_id
        self.cancel, self.bridge = threading.Event(), None
        self.gate = AvailabilityGate(self)
        self.thread = threading.Thread(target=self.run, name="core-availability", daemon=True)
        # Readiness10 + stop2 + close(wait2 + kill/wait2 + reader.2),
        # with a margin. Core additionally refuses to close Store if still alive.
        self.close_timeout = 18
        self.evidence_ids, self.entry_sequence = set(), 0
        self.load_id, self.defense_id = None, None

    def event(self, kind, actor, data, *, visibility="judge_safe", refs=()):
        return {"type": kind, "actor": actor, "producer": actor, "data_source": "fixture",
                "visibility": visibility, "evidence_refs": list(refs), "data": data}

    def changed(self, state):
        from .service import ALLOWED_ACTIONS
        self.store.apply(self.session_id, updates={"status": state, "allowed_actions": ALLOWED_ACTIONS[state]},
            events=[self.event("session." + state, "core", {"status": state})])

    def _call(self, op, **fields):
        response = self.bridge.call(op, **fields)
        entries = response.get("entries", [])
        evidence, events = [], []
        for entry in entries:
            if (entry.get("session_id") != self.session_id or entry.get("target_id") != TARGET or
                entry.get("source_mode") != "fixture" or entry.get("sequence") != self.entry_sequence + 1):
                raise ValueError("Fixture evidence scope/order mismatch")
            self.entry_sequence += 1
            ref = entry["evidence_id"]
            self.evidence_ids.add(ref)
            evidence.append({"evidence_id": ref, "visibility": "referee_only", "data": entry})
            events.append(self.event("bank." + entry["event_type"], "core-bank-adapter", entry["data"],
                visibility="referee_only", refs=[ref]))
        if evidence: self.store.apply(self.session_id, evidence=evidence, events=events)
        return response

    def command(self, op, **fields):
        # The same gate -> store lock order as presenter controls also keeps
        # bridge evidence batches ordered with pause/resume receipts. Calls are
        # bounded to two seconds; no model/provider executes under this lock.
        with self.gate.condition:
            with self.gate.operation():
                return self._call(op, **fields)

    def dispatch_red(self, proposal):
        action = validate_red(proposal)
        response = self.command("dispatch", proposal=action)
        self.store.apply(self.session_id, events=[self.event("availability.load.dispatched", "core", {
            "capability": action["capability"], "registered_target": TARGET,
            "decision_source": "scripted_fixture", "limits": self.bridge.ready["approval"]["profile"]})])
        return response

    def observe(self, kind):
        return self.command("observe", kind=kind)

    def run(self):
        from .service import ALLOWED_ACTIONS
        outcome, verdict, checks = "completed", "inconclusive", {}
        try:
            with self.gate.operation():
                self.bridge = self.service.availability_bridge_factory(self.session_id)
                self.gate._check()
            for kind in ("status", "health", "ordinary"):
                if self.observe(kind)["result"]["data"]["status"] != "available":
                    raise ValueError("Healthy baseline is inconclusive")
            self.store.apply(self.session_id, updates={"phase": "healthy_baseline"}, events=[self.event("target.health", "core", {
                "status": "healthy", "execution": "disposable_bank_library_http", "baseline_verified": True})])
            self.load_id = self.dispatch_red(ActionProposal(capability="start_load_test", target_id=TARGET))["result"]["load_id"]
            for _ in range(8):
                observation = self.observe("status")
                measured_at = time.monotonic()
                telemetry = observation["telemetry"]
                context = {"assessment_id": self.session_id, "target_id": TARGET,
                    "target_version": self.bridge.ready["target_version"], "data_source": "fixture",
                    "window": telemetry["window"], "policy": asdict(POLICY)}
                output = asyncio.run(observe_availability(deepcopy(context)))
                ref = "blue-window-" + context["window"]["window_id"]
                self.store.apply(self.session_id, evidence=[{"evidence_id": ref, "visibility": "blue_private", "data": context}],
                    boards={"blue": output}, events=[self.event("availability.observed", "blue", {
                        "assessment": output["assessment"], "requests": context["window"]["requests"],
                        "inflight": context["window"]["inflight"], "recovery_verified": False})])
                if output["defense_proposals"]:
                    proposal = output["defense_proposals"][0]
                    self.defense_id = approve_defense(proposal, context, measured_at=measured_at, target_policy=telemetry["policy"])
                    receipt = self.command("apply", window_id=context["window"]["window_id"])["result"]
                    if receipt["data"]["status"] != "applied": raise ValueError("Containment not applied")
                    self.store.apply(self.session_id, updates={"phase": "containment_applied", "defense_ids": [self.defense_id]},
                        evidence=[{"evidence_id": "blue-defense", "visibility": "blue_private", "data": {"proposal": proposal, "receipt": receipt}}],
                        events=[self.event("availability.defense.applied", "core", {"action_type": "limit_http_source",
                            "source_ref": "load-demo", "effect": "containment", "recovery_verified": False})])
                    break
                self.cancel.wait(.03)
            if not self.defense_id: raise ValueError("No safe evidence-backed defense")
            # Allow admitted bounded work to drain. A renewed degraded sample
            # resets the referee's successful verification window.
            for _ in range(8):
                self.cancel.wait(.05)
                if self.observe("status")["result"]["data"]["status"] == "available": break
            # Each independent sample is separated by actual continuing load;
            # target counters prove policy-specific refusals in every interval.
            for _ in range(self.bridge.ready["approval"]["criteria"]["recoverySamples"]):
                self.cancel.wait(.12)
                for kind in ("status", "health", "ordinary"): self.observe(kind)
            self.cancel.wait(.12)
            self.dispatch_red(ActionProposal(capability="stop_load_test", target_id=TARGET))
            self.observe("status")
            with self.gate.condition:
                self.gate._check()
                result = self.command("referee")["result"]
                verdict = result["result"]
                if any(ref not in self.evidence_ids for ref in result["evidence_refs"]): raise ValueError("Referee evidence missing")
                checks = {"result": "passed" if verdict == "achieved" else "inconclusive", "arrest_permitted": False,
                          "fix_status": "not_assessed", "scope": "disposable_training_capacity_and_ordinary_accounts"}
                self.store.apply(self.session_id, evidence=[{"evidence_id": "availability-referee", "visibility": "referee_only", "data": result}],
                    events=[self.event("availability.referee.pending", "referee", {"result": verdict},
                                       visibility="referee_only", refs=["availability-referee"])])
        except RunCancelled:
            outcome = "cancelled"
        except (BudgetExceeded, ValueError, OSError):
            outcome = "failed"
        except Exception:
            outcome = "failed"
        finally:
            with self.gate.condition:
                # Stop and the terminal verdict linearize on the same gate.
                # A stop admitted before completion cannot become achieved.
                if self.cancel.is_set():
                    outcome, verdict = "cancelled", "inconclusive"
                self.cancel.set()
                if self.bridge:
                    try: self._call("stop")
                    except Exception: verdict = "inconclusive"; outcome = "failed" if outcome != "cancelled" else outcome
                    self.bridge.close()
                if outcome != "completed":
                    verdict = "inconclusive"
                    checks = {"result": "inconclusive", "arrest_permitted": False, "fix_status": "not_assessed"}
                self.store.apply(self.session_id, updates={"status": outcome, "phase": "ended", "allowed_actions": ALLOWED_ACTIONS[outcome],
                    "verdict": {"result": verdict, "scope": "availability-recovery", "data_source": "fixture", "arrest_permitted": False},
                    "defense_verification": checks, "budget": {"max_load_requests": 60, "max_concurrent_http": 6,
                        "load_deadline_seconds": 4, "max_probes": 30, "max_controls": 4}},
                    events=[self.event("availability.referee.assessed", "referee", {
                        "result": verdict, "data_source": "fixture", "arrest_permitted": False, "fix_status": "not_assessed",
                        "summary": "Disposable recovery verified under continuing bounded load." if verdict == "achieved" else "Availability recovery remains inconclusive."}),
                        self.event("session." + outcome, "core", {"status": outcome, "result": verdict, "arrest_permitted": False})])
                self.gate.condition.notify_all()
