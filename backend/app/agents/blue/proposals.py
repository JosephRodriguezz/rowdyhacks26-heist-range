"""Turn blue alerts into bounded defense proposals.

Blue proposes; core's approved-action dispatcher executes. A proposal names a
session by reference only. The executor resolves the real credential through
core's credential service, so no token passes through blue.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import hashlib
from typing import Any

from .detection import CROSS_USER_READ, Alert, _timestamp

REVOKE_SESSION = "revoke_session"
CONTAINMENT = "containment"


@dataclass(frozen=True)
class DefenseProposal:
    defense_id: str
    action_type: str
    effect: str
    target_id: str
    target_version: str
    summary: str
    reason: str
    expected_effect: str
    parameters: Mapping[str, str] = field(default_factory=dict)
    alert_ids: tuple[str, ...] = ()

    def event_data(self) -> dict[str, Any]:
        """Payload for a `defense.proposed` event (contract v1 required keys first)."""
        return {
            "defense_id": self.defense_id,
            "action_type": self.action_type,
            "summary": self.summary,
            "reason": self.reason,
            "parameters": dict(self.parameters),
            "effect": self.effect,
            "expected_effect": self.expected_effect,
            "alert_ids": list(self.alert_ids),
        }


def propose_session_revocations(alerts: Iterable[Alert],
                                previous_defenses: Iterable[Any] = ()) -> tuple[DefenseProposal, ...]:
    """Propose one `revoke_session` per session seen reading another user's data.

    Sessions already named by a previous `revoke_session` defense are not proposed
    again. Anonymous reads have no session to revoke and need the ownership patch.
    """
    handled = _revoked_sessions(previous_defenses)
    by_session: dict[tuple[str, str], list[Alert]] = {}
    for alert in alerts:
        if alert.kind != CROSS_USER_READ or not alert.session_ref or alert.session_ref in handled:
            continue
        by_session.setdefault((alert.target_id, alert.session_ref), []).append(alert)
    return tuple(_revocation(target_id, session_ref, grouped)
                 for (target_id, session_ref), grouped in by_session.items())


def _revocation(target_id: str, session_ref: str, alerts: list[Alert]) -> DefenseProposal:
    latest = max(alerts, key=lambda alert: _timestamp(alert.last_seen))
    owners = ", ".join(dict.fromkeys(owner for alert in alerts for owner in alert.resource_owner_refs))
    digest = hashlib.sha256(repr((REVOKE_SESSION, target_id, session_ref)).encode()).hexdigest()[:12]
    return DefenseProposal(
        defense_id=f"defense-revoke-{digest}",
        action_type=REVOKE_SESSION,
        effect=CONTAINMENT,
        target_id=target_id,
        target_version=latest.target_version,
        summary=f"Revoke session {session_ref} to contain cross-user access.",
        reason=(f"{latest.actor_ref} used this session to read private data owned by {owners}. "
                "Revoking it is containment and does not fix the ownership check."),
        expected_effect=(f"Requests using {session_ref} are rejected. Other sessions, including "
                         f"a new session for {latest.actor_ref}, are not affected."),
        parameters={"session_ref": session_ref},
        alert_ids=tuple(alert.alert_id for alert in alerts),
    )


def _revoked_sessions(previous_defenses: Iterable[Any]) -> set[str]:
    sessions = set()
    for defense in previous_defenses:
        data = defense.event_data() if isinstance(defense, DefenseProposal) else defense
        if not isinstance(data, Mapping) or data.get("action_type") != REVOKE_SESSION:
            continue
        parameters = data.get("parameters")
        if isinstance(parameters, Mapping) and isinstance(parameters.get("session_ref"), str):
            sessions.add(parameters["session_ref"])
    return sessions
