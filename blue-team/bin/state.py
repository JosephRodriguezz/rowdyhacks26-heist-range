"""Deterministic workflow state for each task.

Model replies are evidence. Only this module decides what state a task is in, and
every transition is checked against an explicit table and appended to the task's
history. When anything is unclear the task moves to needs_human; nothing guesses.

Authority, highest first: the human, this state machine, deterministic rules and
tests, independent multi-model review, an individual model's recommendation.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import json
import os
import time

import dashboard
from common import FRAMEWORK, atomic_write, now

STATE_DIR = FRAMEWORK / "state"
LOCK_DIR = STATE_DIR / ".locks"

PHASES = ("new", "proposing", "proposed", "voting", "accepted", "implementing", "implemented", "reviewing",
          "approved", "changes_requested", "ready_to_close", "closed", "needs_human")
TRANSITIONS = {
    "new": {"proposing"},
    "proposing": {"proposed"},
    "proposed": {"voting"},
    "voting": {"accepted"},
    "accepted": {"implementing"},
    "implementing": {"implemented"},
    "implemented": {"reviewing"},
    "reviewing": {"approved", "changes_requested"},
    "changes_requested": {"implementing"},
    "approved": {"ready_to_close"},
    "ready_to_close": {"closed", "approved"},
    "needs_human": {"new", "proposed", "accepted", "implemented", "approved", "changes_requested"},
    "closed": set(),
}
STANCES = ("agree", "object", "security-objection", "abstain")
VERDICTS = ("approve", "changes-requested", "security-objection")


class StateError(RuntimeError):
    pass


def fresh(task: str) -> dict:
    return {"task": task, "schema": 1, "phase": "new", "round": 1, "attempt": 0, "needs_human": None,
            "unavailable": {}, "proposals": {}, "draft": None, "votes": {}, "decision": None, "approvals": [],
            "implementation": None, "reviews": {}, "checks": None, "history": []}


def path_for(task: str):
    return STATE_DIR / f"{task}.json"


def load(task: str) -> dict:
    path = path_for(task)
    if not path.exists():
        return fresh(task)
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("task") != task or state.get("phase") not in PHASES or not isinstance(state.get("history"), list):
        raise StateError(f"State file for {task} is inconsistent. A human must inspect {path.name}.")
    return state


def save(state: dict) -> None:
    atomic_write(path_for(state["task"]), json.dumps(state, indent=2) + "\n")
    dashboard.refresh()


def transition(state: dict, to: str, event: str, evidence: dict | None = None) -> None:
    current = state["phase"]
    if to not in TRANSITIONS.get(current, set()):
        raise StateError(f"{state['task']}: cannot move from {current} to {to}.")
    state["phase"] = to
    state["history"].append({"at": now(), "from": current, "to": to, "event": event, "evidence": evidence or {}})


def escalate(state: dict, reason: str, details: str, resume: str) -> None:
    """Stop automatic progress and record why a human must look."""
    if state["phase"] == "closed":
        raise StateError(f"{state['task']} is closed.")
    current = state["phase"]
    state["needs_human"] = {"reason": reason, "details": details, "from_phase": current, "resume_phase": resume,
                            "at": now()}
    state["phase"] = "needs_human"
    state["history"].append({"at": now(), "from": current, "to": "needs_human", "event": f"escalated: {reason}",
                             "evidence": {"details": details, "resume_phase": resume}})


def resume(state: dict, to: str, note: str) -> None:
    if state["phase"] != "needs_human":
        raise StateError(f"{state['task']} is not waiting for a human.")
    escalation = state["needs_human"]
    transition(state, to, f"human resolved: {escalation['reason']}", {"note": note})
    state["needs_human"] = None


def evaluate_votes(votes: dict[str, str], malformed: list[str], quorum: int) -> dict:
    """Decide from structured stances. Fails closed on anything unclear."""
    for model, stance in votes.items():
        if stance not in STANCES:
            raise StateError(f"Unknown stance {stance!r} from {model}.")
    counts = Counter(votes.values())
    cast = counts["agree"] + counts["object"]
    security = sorted(m for m, s in votes.items() if s == "security-objection")
    result = {"agree": counts["agree"], "object": counts["object"], "abstain": counts["abstain"], "cast": cast,
              "security_objections": security, "malformed": sorted(malformed), "quorum": quorum}
    if malformed:
        return {**result, "status": "needs_human", "reason": "malformed-output",
                "rule": "A reply could not be parsed: " + ", ".join(sorted(malformed)) + "."}
    if security:
        return {**result, "status": "needs_human", "reason": "security-objection",
                "rule": "Security objection from " + ", ".join(security) + "; only the human can resolve it."}
    if cast < quorum:
        return {**result, "status": "needs_human", "reason": "no-quorum",
                "rule": f"{cast} votes cast; {quorum} required."}
    if counts["agree"] * 2 > cast:
        return {**result, "status": "accepted", "reason": "majority",
                "rule": f"{counts['agree']} of {cast} votes agree, no security objection."}
    if counts["agree"] * 2 == cast:
        return {**result, "status": "needs_human", "reason": "tie", "rule": f"Tie: {counts['agree']} of {cast}."}
    return {**result, "status": "needs_human", "reason": "majority-objection",
            "rule": f"Only {counts['agree']} of {cast} votes agree."}


def select_implementer(recommendations: dict[str, str], available: list[str], tiebreak: list[str]) -> tuple[str | None, dict]:
    """Most-recommended available model; ties break by the configured order."""
    tally = Counter(m for m in recommendations.values() if m in available)
    if not tally:
        return None, {}
    best = max(tally.values())
    for model in tiebreak:
        if tally.get(model) == best:
            return model, dict(tally)
    return None, dict(tally)


def reviewers_for(implementer: str, available: list[str]) -> list[str]:
    return [m for m in available if m != implementer]


def evaluate_reviews(verdicts: dict[str, str], implementer: str, malformed: list[str], min_reviewers: int) -> dict:
    if implementer in verdicts or implementer in malformed:
        raise StateError(f"{implementer} cannot review its own implementation.")
    for model, verdict in verdicts.items():
        if verdict not in VERDICTS:
            raise StateError(f"Unknown verdict {verdict!r} from {model}.")
    security = sorted(m for m, v in verdicts.items() if v == "security-objection")
    changes = sorted(m for m, v in verdicts.items() if v == "changes-requested")
    result = {"verdicts": dict(verdicts), "malformed": sorted(malformed), "min_reviewers": min_reviewers}
    if security:
        return {**result, "status": "needs_human", "reason": "security-objection",
                "rule": "Security objection from " + ", ".join(security) + "."}
    if malformed:
        return {**result, "status": "needs_human", "reason": "malformed-output",
                "rule": "A review could not be parsed: " + ", ".join(sorted(malformed)) + "."}
    if len(verdicts) < min_reviewers:
        return {**result, "status": "needs_human", "reason": "insufficient-reviewers",
                "rule": f"{len(verdicts)} independent reviews; {min_reviewers} required."}
    if changes:
        return {**result, "status": "changes_requested", "reason": "changes-requested",
                "rule": "Changes requested by " + ", ".join(changes) + "."}
    return {**result, "status": "approved", "reason": "approved",
            "rule": f"All {len(verdicts)} independent reviewers approve."}


def approve_implementation(state: dict, implementer: str, decision_sha256: str, note: str) -> dict:
    if state["phase"] not in ("accepted", "changes_requested"):
        raise StateError(f"{state['task']} is {state['phase']}; implementation can be approved only after an "
                         "accepted decision or a change request.")
    approval = {"gate": "implementation", "implementer": implementer, "decision_sha256": decision_sha256,
                "attempt": state["attempt"] + 1, "at": now(), "by": "human", "note": note, "used": False}
    state["approvals"].append(approval)
    state["history"].append({"at": now(), "from": state["phase"], "to": state["phase"],
                             "event": "human approved implementation", "evidence": dict(approval)})
    return approval


def consume_approval(state: dict, decision_sha256: str) -> dict:
    attempt = state["attempt"] + 1
    for approval in reversed(state["approvals"]):
        if (approval["gate"] == "implementation" and not approval["used"] and approval["attempt"] == attempt
                and approval["decision_sha256"] == decision_sha256):
            approval["used"] = True
            return approval
    raise StateError(f"No human approval for implementation attempt {attempt} of {state['task']}. "
                     f"Run: python blue-team/bin/orchestrate.py approve {state['task']}")


@contextmanager
def task_lock(task: str):
    """One orchestrator run per task at a time."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock = LOCK_DIR / f"{task}.lock"
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        age = int(time.time() - lock.stat().st_mtime) if lock.exists() else 0
        raise StateError(f"Another orchestrator run holds {task} (lock is {age}s old). If none is running, "
                         f"delete {lock}.")
    try:
        os.write(handle, f"{os.getpid()} {now()}".encode())
        yield
    finally:
        os.close(handle)
        lock.unlink(missing_ok=True)
        dashboard.refresh()
