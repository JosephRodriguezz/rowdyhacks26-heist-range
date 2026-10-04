"""Linearized dispatch admission, draining pause, cancellation, and deadlines."""

from contextlib import contextmanager
import threading
import time

from red.prototype.board import BudgetExceeded, RunCancelled


class DispatchGate:
    def __init__(self, seconds, cancel, changed):
        self.deadline = time.monotonic() + seconds
        self.cancel, self.changed = cancel, changed
        self.condition = threading.Condition(threading.RLock())
        self.local = threading.local()
        self.state, self.inflight = "running", 0

    def _check(self):
        if self.cancel.is_set():
            raise RunCancelled("contest stopped")
        if time.monotonic() >= self.deadline:
            raise BudgetExceeded("contest deadline exhausted")

    def wait(self):
        with self.condition:
            self._check()
            if getattr(self.local, "depth", 0):
                return
            while self.state in ("pausing", "paused"):
                self.condition.wait(timeout=min(.05, max(.001, self.deadline - time.monotonic())))
                self._check()

    @contextmanager
    def operation(self, *, drain=False):
        with self.condition:
            if not (drain and getattr(self.local, "depth", 0)):
                self.wait()
            self.inflight += 1
            self.local.depth = getattr(self.local, "depth", 0) + 1
        try:
            yield
        finally:
            with self.condition:
                self.local.depth -= 1
                self.inflight -= 1
                if self.state == "pausing" and not self.inflight:
                    self.state = "paused"
                    self.changed("paused")
                self.condition.notify_all()

    def pause(self):
        with self.condition:
            self._check()
            if self.state != "running":
                raise ValueError("pause requires running state")
            self.state = "pausing" if self.inflight else "paused"
            self.changed(self.state)
            self.condition.notify_all()

    def resume(self):
        with self.condition:
            self._check()
            if self.state not in ("pausing", "paused"):
                raise ValueError("resume requires paused state")
            self.state = "running"
            self.changed("running")
            self.condition.notify_all()

    def stop(self):
        with self.condition:
            if not self.cancel.is_set():
                self.cancel.set()
                self.state = "stopping"
                self.changed("stopping")
            self.condition.notify_all()
