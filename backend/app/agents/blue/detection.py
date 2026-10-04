"""Detect suspicious private-record access from sanitized lab telemetry.

The detector receives telemetry and the access policy only. It never sees red's
plan, candidate findings, or referee verdicts, so its alerts are independent
observations. An alert is not a verified finding.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
from typing import Any

TELEMETRY_FIELDS = ("request_id", "timestamp", "target_id", "target_version", "actor_ref",
                    "session_ref", "resource_id", "resource_owner_ref", "action", "http_status")
CROSS_USER_READ = "cross_user_read"
ANONYMOUS_READ = "anonymous_read"


@dataclass(frozen=True)
class AccessPolicy:
    id: str
    owner_only_actions: frozenset[str]


PRIVATE_ORDERS_POLICY = AccessPolicy("private-orders-owner-only", frozenset({"read_private_order"}))


@dataclass(frozen=True)
class Alert:
    alert_id: str
    kind: str
    policy_id: str
    target_id: str
    target_version: str
    actor_ref: str | None
    session_ref: str | None
    request_ids: tuple[str, ...]
    resource_ids: tuple[str, ...]
    resource_owner_refs: tuple[str, ...]
    first_seen: str
    last_seen: str
    summary: str

    def event_data(self) -> dict[str, Any]:
        """Payload for an `alert.created` event; core maps request IDs to evidence refs."""
        return {
            "alert_id": self.alert_id,
            "request_ids": list(self.request_ids),
            "summary": self.summary,
            "kind": self.kind,
            "policy_id": self.policy_id,
            "session_ref": self.session_ref,
            "resource_ids": list(self.resource_ids),
        }


@dataclass(frozen=True)
class SkippedRecord:
    request_id: str | None
    reason: str


@dataclass(frozen=True)
class DetectionResult:
    alerts: tuple[Alert, ...]
    skipped: tuple[SkippedRecord, ...]


def detect_suspicious_access(telemetry: Iterable[Any], policy: AccessPolicy) -> DetectionResult:
    """Alert on successful owner-only reads by another user or by no user.

    Records that cannot be evaluated are skipped with a reason, never alerted on.
    Denied attempts do not raise alerts. Alerts are grouped per session and target
    version, so an exposure that survives a patch produces a separate alert.
    """
    skipped, hits = [], []
    for record in telemetry:
        problem = record_problem(record, policy)
        if problem:
            request_id = record.get("request_id") if isinstance(record, Mapping) else None
            skipped.append(SkippedRecord(request_id if isinstance(request_id, str) else None, problem))
            continue
        kind = _classify(record, policy)
        if kind:
            hits.append((kind, record))

    groups: dict[tuple, list[Mapping[str, Any]]] = {}
    for kind, record in sorted(hits, key=lambda hit: (parse_utc_timestamp(hit[1]["timestamp"]), hit[1]["request_id"])):
        key = (policy.id, kind, record["target_id"], record["target_version"],
               record["actor_ref"], record["session_ref"])
        groups.setdefault(key, []).append(record)
    return DetectionResult(tuple(_alert(key, records) for key, records in groups.items()), tuple(skipped))


def record_problem(record: Any, policy: AccessPolicy) -> str | None:
    """Why the detector cannot evaluate this record, or None when it can."""
    if not isinstance(record, Mapping):
        return "record is not an object"
    missing = [name for name in TELEMETRY_FIELDS if name not in record]
    if missing:
        return "missing " + ", ".join(missing)
    for name in ("request_id", "target_id", "target_version", "resource_id", "action"):
        if not isinstance(record[name], str) or not record[name]:
            return f"{name} must be a non-empty string"
    for name in ("actor_ref", "session_ref", "resource_owner_ref"):
        if record[name] is not None and (not isinstance(record[name], str) or not record[name]):
            return f"{name} must be a non-empty string or null"
    if type(record["http_status"]) is not int:
        return "http_status must be an integer"
    if parse_utc_timestamp(record["timestamp"]) is None:
        return "timestamp must be ISO 8601 UTC ending in Z"
    if record["action"] in policy.owner_only_actions and record["resource_owner_ref"] is None:
        return "resource owner unknown for an owner-only action"
    return None


def _classify(record: Mapping[str, Any], policy: AccessPolicy) -> str | None:
    if record["action"] not in policy.owner_only_actions or not 200 <= record["http_status"] < 300:
        return None
    if record["actor_ref"] is None:
        return ANONYMOUS_READ
    if record["actor_ref"] != record["resource_owner_ref"]:
        return CROSS_USER_READ
    return None


def _alert(key: tuple, records: list[Mapping[str, Any]]) -> Alert:
    policy_id, kind, target_id, target_version, actor_ref, session_ref = key
    owners = _unique(record["resource_owner_ref"] for record in records)
    requests = f"{len(records)} request{'' if len(records) == 1 else 's'}"
    if kind == CROSS_USER_READ:
        summary = f"{actor_ref} read private data owned by {', '.join(owners)} ({requests})."
    else:
        summary = f"Unauthenticated access to private data ({requests})."
    return Alert(
        alert_id="alert-" + hashlib.sha256(repr(key).encode()).hexdigest()[:12],
        kind=kind,
        policy_id=policy_id,
        target_id=target_id,
        target_version=target_version,
        actor_ref=actor_ref,
        session_ref=session_ref,
        request_ids=tuple(record["request_id"] for record in records),
        resource_ids=_unique(record["resource_id"] for record in records),
        resource_owner_refs=owners,
        first_seen=records[0]["timestamp"],
        last_seen=records[-1]["timestamp"],
        summary=summary,
    )


def parse_utc_timestamp(value: Any) -> datetime | None:
    """Parse legacy Z timestamps, never returning a naive or non-UTC datetime."""
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    # A date-only input can consume +00:00 as a time instead of an offset.
    return parsed if parsed.utcoffset() == timedelta(0) else None


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
