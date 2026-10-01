"""Turn blue alerts into bounded defense proposals.

Blue proposes; core's approved-action dispatcher executes. A session proposal
names the session by reference only; the executor resolves the real credential
through core's credential service, so no token passes through blue. A patch
proposal names a validated manifest and its base version, never raw code.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import hashlib
from typing import Any

from .detection import ANONYMOUS_READ, CROSS_USER_READ, Alert, parse_utc_timestamp
from .patches import PatchManifest

REVOKE_SESSION = "revoke_session"
APPLY_PATCH = "apply_patch"
CONTAINMENT = "containment"
REMEDIATION = "remediation"


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
    details: Mapping[str, Any] = field(default_factory=dict)

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
            **self.details,
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
    latest = max(alerts, key=lambda alert: parse_utc_timestamp(alert.last_seen))
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


def propose_ownership_patch(alerts: Iterable[Alert], manifest: PatchManifest, current_version: str,
                            previous_defenses: Iterable[Any] = ()) -> DefenseProposal | None:
    """Propose the ownership patch when the current target version still leaks data.

    Returns None when no alert on the current version matches the patch's policy,
    when the patch was built for a different base version (stale), or when the
    same patch was already proposed. A draft patch is proposed but marked draft,
    and the executor must refuse it.
    """
    relevant = [alert for alert in alerts
                if alert.kind in (CROSS_USER_READ, ANONYMOUS_READ)
                and alert.policy_id == manifest.policy_id and alert.target_version == current_version]
    if not relevant or manifest.base_version != current_version:
        return None
    if manifest.patch_id in _previous_parameters(previous_defenses, APPLY_PATCH, "patch_id"):
        return None
    target_id = relevant[0].target_id
    digest = hashlib.sha256(repr((APPLY_PATCH, target_id, manifest.patch_id, current_version)).encode()).hexdigest()[:12]
    sessions = len({alert.session_ref for alert in relevant if alert.session_ref})
    anonymous = any(alert.kind == ANONYMOUS_READ for alert in relevant)
    observed = f"{sessions} session{'' if sessions == 1 else 's'}" + (" and unauthenticated requests" if anonymous else "")
    return DefenseProposal(
        defense_id=f"defense-patch-{digest}",
        action_type=APPLY_PATCH,
        effect=REMEDIATION,
        target_id=target_id,
        target_version=current_version,
        summary=manifest.title + ".",
        reason=(f"Private data was read without ownership on {current_version} by {observed}. "
                "Revoking sessions cannot stop a new session; this patch fixes the check on the server."),
        expected_effect=("Applied to a disposable copy only. The fix is unverified until the referee "
                         "reruns every regression check, including owners reading their own orders."),
        parameters={"patch_id": manifest.patch_id, "base_version": manifest.base_version},
        alert_ids=tuple(alert.alert_id for alert in relevant),
        details={
            "origin": manifest.origin,
            "patch_status": manifest.status,
            "target_route": manifest.target_route,
            "regression_check_ids": [check.id for check in manifest.regression_checks],
        },
    )


def _revoked_sessions(previous_defenses: Iterable[Any]) -> set[str]:
    return _previous_parameters(previous_defenses, REVOKE_SESSION, "session_ref")


def _previous_parameters(previous_defenses: Iterable[Any], action_type: str, key: str) -> set[str]:
    values = set()
    for defense in previous_defenses:
        data = defense.event_data() if isinstance(defense, DefenseProposal) else defense
        if not isinstance(data, Mapping) or data.get("action_type") != action_type:
            continue
        parameters = data.get("parameters")
        if isinstance(parameters, Mapping) and isinstance(parameters.get(key), str):
            values.add(parameters[key])
    return values
