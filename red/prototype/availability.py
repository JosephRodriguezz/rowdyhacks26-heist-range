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
        act("start_load_test")
        deadline = time.monotonic() + executor.load_profile.duration_seconds + 0.5
        while time.monotonic() < deadline:
            if stop_if_achieved():
                break
            time.sleep(0.1)
        act("stop_load_test")
        time.sleep(0.1)
        # Confirm recovery with one explicit, recorded observation rather than assuming it.
        act("request_api", path="/api/status")
        board.finish_task(task_id, "completed")
    except (BudgetExceeded, RunCancelled):
        board.finish_task(task_id, "yielded")
