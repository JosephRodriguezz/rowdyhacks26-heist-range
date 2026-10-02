"""A deterministic surface-survey baseline, intentionally separate from model mode."""

from __future__ import annotations

import json
from typing import Any, Callable

from .actions import ActionExecutor
from .board import BudgetExceeded, RedBoard, RunCancelled
from .domain import ActionProposal


def run_surface_survey(
    *,
    executor: ActionExecutor,
    board: RedBoard,
    task_id: str,
    stop_if_achieved: Callable[[], bool],
) -> None:
    """Compare discovered account/resource behavior without scenario-specific payloads."""
    owner = "deterministic-baseline"
    if not board.claim_task(task_id, owner):
        raise RuntimeError("baseline task could not be claimed")

    def act(capability: str, *, path: str = "/", method: str = "GET", identity: str | None = None,
            session: str | None = None, body: dict[str, str] | None = None, form: str | None = None) -> str:
        result = executor.execute(
            ActionProposal(capability=capability, path=path, method=method, identity_ref=identity,
                           session_ref=session, body=body or {}, form_ref=form),
            role="scout", task_id=task_id,
        )
        board.record_event("baseline.step", {
            "evidence_id": result.evidence.evidence_id if result.evidence else None,
            "action_count": executor.budget.snapshot()["actions_used"],
        })
        if stop_if_achieved():
            board.finish_task(task_id, "completed")
            return "__achieved__"
        if not result.evidence or result.evidence.status is None:
            return ""
        return result.evidence.body

    try:
        page = act("read_page")
        if page == "__achieved__":
            return
        try:
            links = json.loads(page).get("links", [])
        except (ValueError, AttributeError):
            links = []
        catalog_body = ""
        for path in links:
            if not isinstance(path, str) or not path.startswith("/api/"):
                continue
            if act("request_api", path=path) == "__achieved__":
                return
            if path == "/api/catalog":
                evidence = board.evidence()[-1]
                catalog_body = evidence.body
        if not catalog_body:
            return
        try:
            records: list[dict[str, Any]] = json.loads(catalog_body).get("records", [])
        except (ValueError, AttributeError):
            return
        for identity_ref in ("account_a", "account_b"):
            login_body = act("start_account_session", identity=identity_ref)
            if login_body == "__achieved__":
                return
            login_evidence = board.evidence()[-1]
            session_ref = login_evidence.session_ref
            if not session_ref:
                continue
            profile_body = act("request_api", path="/api/profile", session=session_ref)
            if profile_body == "__achieved__":
                return
            try:
                username = json.loads(profile_body).get("username")
            except (ValueError, AttributeError):
                username = None
            own = [r for r in records if r.get("owner") == username]
            other = [r for r in records if r.get("owner") != username]
            if own:
                # First check the ordinary path and an observed search term.
                if act("read_page", path="/api/records/" + str(own[0].get("record_id")), session=session_ref) == "__achieved__":
                    return
                title = str(own[0].get("title", ""))[:120]
                if title and act("request_api", path="/api/search", method="POST", session=session_ref,
                                 body={"query": title}) == "__achieved__":
                    return
            # Compare a resource reference that the public catalog actually exposed.
            for record in other[:1]:
                record_id = record.get("record_id")
                if isinstance(record_id, str):
                    if act("read_page", path="/api/records/" + record_id, session=session_ref) == "__achieved__":
                        return
            if own:
                own_id = own[0].get("record_id")
                act("end_account_session", session=session_ref)
                if isinstance(own_id, str) and act("read_page", path="/api/records/" + own_id, session=session_ref) == "__achieved__":
                    return
        board.finish_task(task_id, "completed")
    except (BudgetExceeded, RunCancelled):
        board.finish_task(task_id, "yielded")
