"""Deterministic baseline for the standalone availability (load/recovery) scenario.

Intentionally separate from baseline.py's generic surface survey: starting and stopping
a bounded load profile is specific to this one scenario, not a general comparison any
scenario can reuse.
"""

from __future__ import annotations

import time
from typing import Callable

from .actions import ActionExecutor
from .board import BudgetExceeded, RedBoard, RunCancelled
from .domain import ActionProposal


def run_availability_baseline(
    *,
    executor: ActionExecutor,
    board: RedBoard,
    task_id: str,
    stop_if_achieved: Callable[[], bool],
) -> None:
    """Start the one bounded load profile, let it run, stop it, then confirm recovery.

    This gives the availability scenario a repeatable, model-free demo path: the
    degraded-then-recovered cycle does not depend on a live model call succeeding.
    """
    owner = "deterministic-baseline"
    if not board.claim_task(task_id, owner):
        raise RuntimeError("baseline task could not be claimed")

    def act(capability: str, *, path: str = "/", method: str = "GET") -> None:
        executor.execute(
            ActionProposal(capability=capability, path=path, method=method),
            role="scout", task_id=task_id,
        )

    try:
        # One idle-baseline ordinary-access observation before any load exists, so the
        # independent during-load check (evaluate_ordinary_access_during_load) has this
        # lab's own measured baseline to compare against, not an invented threshold.
        # Each probe below carries a distinct, harmless query string (the server ignores
        # it; /api/catalog's routing is on the path alone) so the action boundary's own
        # exact-replay dedup -- correct for a literal repeat -- does not also swallow a
        # second, later, genuinely new observation of the same route.
        act("request_api", path="/api/catalog?probe=baseline")
        act("start_load_test")
        deadline = time.monotonic() + executor.load_profile.duration_seconds + 0.5
        max_probes, probes_sent, attempts = 5, 0, 0
        # Paced by the load's own observed state, not a fixed wall-clock schedule: a
        # bounded burst can self-terminate (hits its own request ceiling) well before
        # `duration_seconds` elapses, so waiting out any fixed interval risks missing the
        # active window entirely. `start_load_test` sets active_load_test_id before its
        # background thread starts, so it is reliably set the instant this call returns;
        # send the next probe immediately, with no gap for the load to end in between.
        while time.monotonic() < deadline and probes_sent < max_probes and attempts < 200:
            if stop_if_achieved():
                break
            attempts += 1
            if executor.state.active_load_test_id is None:
                if probes_sent > 0:
                    break  # the load already ended; stop waiting on a dead window
                time.sleep(0.01)
                continue
            # Ordinary access, requested while the load is active and recorded
            # target-side with that tag -- not Red's own claim that it "still worked."
            act("request_api", path=f"/api/catalog?probe={probes_sent}")
            probes_sent += 1
        act("stop_load_test")
        time.sleep(0.1)
        # Confirm recovery with one explicit, recorded observation rather than assuming it.
        act("request_api", path="/api/status")
        board.finish_task(task_id, "completed")
    except (BudgetExceeded, RunCancelled):
        board.finish_task(task_id, "yielded")
