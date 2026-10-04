"""Adapters preserve team algorithms while core controls dispatch and persistence."""

from functools import wraps
import queue
import threading
import time

from red.prototype.actions import ActionExecutor, ActionRejected
from red.prototype.agents import AgentWorker
from red.prototype.board import BudgetLedger, BudgetExceeded, RedBoard, RunCancelled
from red.prototype.domain import AgentStep
from red.prototype.providers import ProviderError


class CoreBudget(BudgetLedger):
    def __init__(self, limits, cancel, gate, changed, on_budget_exhausted=None):
        super().__init__(limits, cancel)
        self.gate, self.changed = gate, changed
        self.on_budget_exhausted = on_budget_exhausted

    def _exhausted(self):
        if self.on_budget_exhausted is not None:
            self.on_budget_exhausted()

    def check_active(self):
        try:
            self.gate.wait()
            super().check_active()
        except BudgetExceeded:
            self._exhausted()
            raise

    def reserve_model(self):
        try:
            with self.gate.operation():
                super().reserve_model()
                self.changed(self.snapshot())
        except BudgetExceeded:
            self._exhausted()
            raise

    def reserve_action(self, action_id):
        try:
            with self.gate.operation():
                super().reserve_action(action_id)
                self.changed(self.snapshot())
        except BudgetExceeded:
            self._exhausted()
            raise


class CoreBoard(RedBoard):
    def __init__(self, session_id, gate, changed):
        super().__init__(session_id)
        self.gate, self.changed = gate, changed
        self.mutation_local = threading.local()


def _guard_mutation(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        # The lock spans nested handoff/candidate changes and one persistence commit.
        with self.gate.operation(drain=True), self._lock:
            depth = getattr(self.mutation_local, "depth", 0)
            self.mutation_local.depth = depth + 1
            try:
                result = method(self, *args, **kwargs)
                if depth == 0:
                    self.changed(self)
                return result
            finally:
                self.mutation_local.depth = depth
    return guarded


for _name in ("add_task", "claim_task", "finish_task", "add_evidence", "claim_candidate",
              "apply_hypothesis", "claim_action_fingerprint", "handoff", "record_event"):
    setattr(CoreBoard, _name, _guard_mutation(getattr(RedBoard, _name)))


class BoundedProvider:
    def __init__(self, provider, gate, decision):
        self.provider, self.gate, self.decision = provider, gate, decision
        self.label = provider.label

    def propose(self, *, role, context, system_prompt, timeout):
        with self.gate.operation():
            replies = queue.Queue(maxsize=1)
            def compute():
                try:
                    value = self.provider.propose(role=role, context=context, system_prompt=system_prompt, timeout=timeout)
                    replies.put((True, value))
                except Exception:
                    # Provider exception text can carry request metadata or secrets.
                    replies.put((False, None))
            thread = threading.Thread(target=compute, name="proposal-only-provider", daemon=True)
            thread.start()
            deadline = min(time.monotonic() + timeout, self.gate.deadline)
            while True:
                self.gate._check()
                if time.monotonic() >= deadline:
                    raise ProviderError("proposal provider exceeded its enforced timeout")
                try:
                    ok, value = replies.get(timeout=min(.05, max(.001, deadline - time.monotonic())))
                except queue.Empty:
                    continue
                self.gate._check()
                if not ok or not isinstance(value, AgentStep):
                    raise ProviderError("proposal provider failed or returned an invalid typed step")
                self.decision(role, value)
                return value


class CoreExecutor(ActionExecutor):
    def __init__(self, *, runtime, **kwargs):
        super().__init__(**kwargs)
        self.runtime = runtime
        self.dispatch_lock = threading.RLock()

    def execute(self, proposal, *, role, task_id):
        with self.dispatch_lock, self.runtime.gate.operation():
            tasks = self.board.tasks()
            if not any(t["task_id"] == task_id and t["role"] == role and t["status"] == "active"
                       and t["owner"] == threading.current_thread().name for t in tasks):
                raise ActionRejected("task does not authorize this worker")
            if proposal.target_id != self.runtime.lab.target_id or proposal.capability not in self.runtime.red_capabilities:
                raise ActionRejected("target/capability is not authorized by core")
            result = super().execute(proposal, role=role, task_id=task_id)
            if result.created_session_ref:
                with self._session_lock:
                    entry = self._sessions[result.created_session_ref]
                    self.runtime.lab.register_session(result.created_session_ref, entry["cookie"], role)
            self.runtime.observed(result)
            return result


class CoreWorker(AgentWorker):
    def __init__(self, *args, on_budget_exhausted=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_budget_exhausted = on_budget_exhausted

    def run(self):
        try:
            super().run()
        except BudgetExceeded:
            if self.on_budget_exhausted is not None:
                self.on_budget_exhausted()
        except RunCancelled:
            # Terminal core state is recorded by the coordinator, not a late worker.
            pass
        finally:
            if self.role == "scout":
                self.scout_done_event.set()
