"""Shared, deliberately small records used by the local Red prototype."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Role = Literal["scout", "operator"]
RunMode = Literal["model", "deterministic_baseline"]
Verdict = Literal["achieved", "not_achieved", "inconclusive"]


@dataclass(frozen=True)
class RunLimits:
    action_calls: int = 60
    model_calls: int = 30
    wall_seconds: float = 180.0
    request_timeout_seconds: float = 2.0
    response_bytes: int = 16_384
    model_timeout_seconds: float = 30.0
    max_agent_turns: int = 18

    def __post_init__(self) -> None:
        if self.action_calls < 1 or self.model_calls < 1 or self.max_agent_turns < 1:
            raise ValueError("call and turn limits must be positive")
        if min(self.wall_seconds, self.request_timeout_seconds, self.model_timeout_seconds) <= 0:
            raise ValueError("time limits must be positive")
        if self.response_bytes < 256:
            raise ValueError("response_bytes must be at least 256")
        if self.action_calls > 200 or self.model_calls > 100 or self.max_agent_turns > 50:
            raise ValueError("configured call limits exceed the prototype hard ceiling")
        if self.wall_seconds > 600 or self.request_timeout_seconds > 30 or self.model_timeout_seconds > 60:
            raise ValueError("configured time limits exceed the prototype hard ceiling")
        if self.response_bytes > 65_536:
            raise ValueError("response_bytes exceeds the prototype hard ceiling")


@dataclass(frozen=True)
class ActionProposal:
    capability: str
    target_id: str = "bank-local"
    path: str = "/"
    method: str = "GET"
    identity_ref: str | None = None
    session_ref: str | None = None
    form_ref: str | None = None
    body: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ActionProposal":
        allowed = {
            "capability", "target_id", "path", "method", "identity_ref",
            "session_ref", "form_ref", "body",
        }
        if not isinstance(value, dict) or set(value) - allowed:
            raise ValueError("action contains unknown fields")
        body = value.get("body", {})
        if not isinstance(body, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in body.items()):
            raise ValueError("action body must contain string fields")
        for key in ("capability", "target_id", "path", "method"):
            if key in value and not isinstance(value[key], str):
                raise ValueError(f"{key} must be a string")
        for key in ("identity_ref", "session_ref", "form_ref"):
            if value.get(key) is not None and not isinstance(value.get(key), str):
                raise ValueError(f"{key} must be a string or null")
        return cls(
            capability=value.get("capability", ""),
            target_id=value.get("target_id", "bank-local"),
            path=value.get("path", "/"),
            method=value.get("method", "GET"),
            identity_ref=value.get("identity_ref"),
            session_ref=value.get("session_ref"),
            form_ref=value.get("form_ref"),
            body=dict(body),
        )


@dataclass(frozen=True)
class AgentStep:
    kind: Literal["act", "handoff", "blocked", "finished"]
    rationale: str
    hypothesis: str
    action: ActionProposal | None = None
    candidate_key: str = ""
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    sequence: int
    role: Role
    capability: str
    method: str
    path: str
    status: int | None
    summary: str
    body: str
    session_id: str = ""
    request_summary: str = ""
    session_ref: str | None = None
    failure_kind: str | None = None

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TargetRead:
    action_id: str
    record_id: str
    principal: str | None
    session_active: bool
    authorized: bool
    content_digest: str


@dataclass
class RunReport:
    run_id: str
    target_kind: str
    planner_mode: str
    defense_mode: str
    verdict: Verdict
    verdict_reason: str
    adaptation: str = "not_measured"
    evidence_refs: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    evidence_records: list[dict[str, Any]] = field(default_factory=list)
    tasks: list[dict[str, Any]] = field(default_factory=list)
    handoffs: list[dict[str, Any]] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_private: dict[str, Any] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
