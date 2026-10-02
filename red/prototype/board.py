"""Thread-safe Red-only evidence board and shared budget ledger."""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .domain import Evidence, Role, RunLimits


class BudgetExceeded(RuntimeError):
    pass


class RunCancelled(RuntimeError):
    pass


class BudgetLedger:
    def __init__(self, limits: RunLimits, cancel_event: threading.Event | None = None) -> None:
        self.limits = limits
        self.cancel_event = cancel_event or threading.Event()
        self.started = time.monotonic()
        self._lock = threading.Lock()
        self._actions = 0
        self._models = 0
        self._action_ids: set[str] = set()

    def check_active(self) -> None:
        if self.cancel_event.is_set():
            raise RunCancelled("run cancelled")
        if time.monotonic() - self.started >= self.limits.wall_seconds:
            raise BudgetExceeded("wall-clock budget exhausted")

    def reserve_model(self) -> None:
        with self._lock:
            self.check_active()
            if self._models >= self.limits.model_calls:
                raise BudgetExceeded("model-call budget exhausted")
            self._models += 1

    def reserve_action(self, action_id: str) -> None:
        with self._lock:
            self.check_active()
            if action_id in self._action_ids:
                raise ValueError("duplicate action ID")
            if self._actions >= self.limits.action_calls:
                raise BudgetExceeded("HTTP-action budget exhausted")
            self._action_ids.add(action_id)
            self._actions += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            elapsed = round(time.monotonic() - self.started, 3)
            return {
                "actions_used": self._actions,
                "actions_limit": self.limits.action_calls,
                "model_calls_used": self._models,
                "model_calls_limit": self.limits.model_calls,
                "elapsed_seconds": elapsed,
                "wall_seconds_limit": self.limits.wall_seconds,
            }


@dataclass
class Task:
    task_id: str
    role: Role
    description: str
    status: str = "queued"
    owner: str | None = None
    evidence_refs: list[str] = field(default_factory=list)
    candidate_key: str = ""
    session_id: str = ""


class RedBoard:
    """Canonical in-memory Red board; contains no Blue or referee records."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id or "session-" + uuid.uuid4().hex[:12]
        self._lock = threading.RLock()
        self._sequence = 0
        self._tasks: dict[str, Task] = {}
        self._evidence: dict[str, Evidence] = {}
        self._events: list[dict[str, Any]] = []
        self._claims: dict[str, str] = {}
        self._handoffs: list[dict[str, Any]] = []
        self._action_fingerprints: dict[str, str] = {}

    @staticmethod
    def task_id() -> str:
        return "task-" + uuid.uuid4().hex[:12]

    def add_task(self, role: Role, description: str, *, status: str = "queued", candidate_key: str = "") -> Task:
        with self._lock:
            task = Task(self.task_id(), role, description, status=status, candidate_key=candidate_key,
                        session_id=self.session_id)
            self._tasks[task.task_id] = task
            self._append_event("task.created", {"task_id": task.task_id, "role": role, "status": status})
            return task

    def claim_task(self, task_id: str, owner: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status not in ("queued", "yielded") or task.owner is not None:
                return False
            task.owner, task.status = owner, "active"
            self._append_event("task.claimed", {"task_id": task_id, "owner": owner})
            return True

    def finish_task(self, task_id: str, status: str = "completed") -> None:
        with self._lock:
            task = self._tasks[task_id]
            task.status = status
            self._append_event("task." + status, {"task_id": task_id, "owner": task.owner})

    def add_evidence(self, evidence: Evidence) -> None:
        with self._lock:
            if evidence.evidence_id in self._evidence:
                raise ValueError("duplicate evidence ID")
            self._sequence += 1
            evidence = Evidence(
                evidence_id=evidence.evidence_id,
                sequence=self._sequence,
                role=evidence.role,
                capability=evidence.capability,
                method=evidence.method,
                path=evidence.path,
                status=evidence.status,
                summary=evidence.summary,
                body=evidence.body,
                session_id=evidence.session_id or self.session_id,
                request_summary=evidence.request_summary,
                session_ref=evidence.session_ref,
                failure_kind=evidence.failure_kind,
            )
            self._evidence[evidence.evidence_id] = evidence
            self._append_event("evidence.recorded", {"evidence_id": evidence.evidence_id, "role": evidence.role})

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        with self._lock:
            return self._evidence.get(evidence_id)

    def evidence(self, *, limit: int = 24) -> list[Evidence]:
        with self._lock:
            return list(self._evidence.values())[-limit:]

    def claim_candidate(self, candidate: str, task_id: str, owner: str) -> bool:
        """Only one active task can own a candidate question at a time."""
        key = hashlib.sha256(candidate.strip().lower().encode()).hexdigest()
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.owner != owner or task.status != "active":
                return False
            held = self._claims.get(key)
            if held and held != task_id:
                return False
            self._claims[key] = task_id
            task.candidate_key = key
            return True

    def claim_action_fingerprint(self, fingerprint: str, task_id: str) -> bool:
        """Prevent an exact test replay until the observed target state changes."""
        with self._lock:
            prior = self._action_fingerprints.get(fingerprint)
            if prior is not None:
                return False
            self._action_fingerprints[fingerprint] = task_id
            return True

    def handoff(self, *, from_task_id: str, sender: str, evidence_refs: list[str], reason: str, candidate_key: str) -> Task:
        with self._lock:
            source = self._tasks.get(from_task_id)
            if source is None or source.owner != sender or source.role != "scout" or source.status != "active":
                raise ValueError("handoff sender does not own an active Scout task")
            if not evidence_refs or any(ref not in self._evidence for ref in evidence_refs):
                raise ValueError("handoff requires existing evidence references")
            key = candidate_key.strip().lower()
            if not key or len(key) > 160:
                raise ValueError("handoff candidate key is invalid")
            normalized = hashlib.sha256(key.encode()).hexdigest()
            current_owner = self._claims.get(normalized)
            if current_owner and current_owner != from_task_id:
                raise ValueError("candidate already belongs to another task")
            self._claims[normalized] = "handoff-pending"
            source.status = "yielded"
            task = Task(
                self.task_id(), "operator", "Test the Scout's evidence-backed candidate",
                status="queued", evidence_refs=list(evidence_refs), candidate_key=normalized,
                session_id=self.session_id,
            )
            self._tasks[task.task_id] = task
            self._claims[normalized] = task.task_id
            source.status = "active"  # Scout keeps exploring under its own task.
            handoff = {
                "handoff_id": "handoff-" + uuid.uuid4().hex[:12],
                "session_id": self.session_id,
                "from_task_id": from_task_id,
                "to_task_id": task.task_id,
                "from_role": "scout",
                "to_role": "operator",
                "reason": reason[:400],
                "evidence_refs": list(evidence_refs),
                "candidate_key": normalized,
            }
            self._handoffs.append(handoff)
            self._append_event("task.handoff", {k: v for k, v in handoff.items() if k != "candidate_key"})
            return task

    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(event) for event in self._events]

    def evidence_records(self) -> list[dict[str, Any]]:
        with self._lock:
            return [item.public_dict() for item in self._evidence.values()]

    def record_event(self, event_type: str, data: dict[str, Any]) -> None:
        with self._lock:
            self._append_event(event_type, data)

    def handoffs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._handoffs]

    def tasks(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"task_id": t.task_id, "role": t.role, "description": t.description,
                 "session_id": t.session_id, "status": t.status, "owner": t.owner,
                 "evidence_refs": list(t.evidence_refs)}
                for t in self._tasks.values()
            ]

    def context_snapshot(self, role: Role) -> dict[str, Any]:
        with self._lock:
            return {
                "role": role,
                "tasks": [t for t in self.tasks() if t["role"] == role],
                "evidence": [ev.public_dict() for ev in self.evidence()],
                "handoffs": [dict(h) for h in self._handoffs if h["to_role"] == role or h["from_role"] == role],
            }

    def _append_event(self, event_type: str, data: dict[str, Any]) -> None:
        self._sequence += 1
        self._events.append({
            "session_id": self.session_id,
            "sequence": self._sequence,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "producer": "red-prototype",
            "event_type": event_type,
            "team": "red",
            "visibility": "red_private",
            **data,
        })
