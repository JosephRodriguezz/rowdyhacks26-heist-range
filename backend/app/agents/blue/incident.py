"""Build an incident evidence report from blue's observations and system results.

Inputs are sanitized telemetry, blue's alerts, and contract events of the types
in REPORT_EVENT_TYPES. Red's candidates and reasoning are never read, so the
report stays independent of the attacker. Referee verdicts appear in their own
section and are never restated as blue's conclusions.

Sections follow the NIST CSF 2.0 Functions used by NIST SP 800-61 Rev. 3:
Detect, Respond, Recover, and Identify (improvement). Every evidence item and
the report itself carry a SHA-256 digest of their canonical JSON.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from . import frameworks
from .detection import ANONYMOUS_READ, CROSS_USER_READ, Alert, parse_utc_timestamp

REPORT_SCHEMA = "range.blue.incident/v1"
REPORT_EVENT_TYPES = {"alert.created", "defense.proposed", "defense.applied", "defense.failed",
                      "finding.verified", "finding.rejected", "finding.inconclusive", "retest.completed"}
ACCEPTANCE_CHECKS = ("unauthorized_access", "owner_access", "second_owner_access", "anonymous_access",
                     "protected_control")
SECRET_MARKERS = ("password", "token", "secret", "cookie", "authorization", "api_key")
STATUS_LABELS = {
    "open": "Open: exposure detected, not contained",
    "contained": "Contained: sessions revoked, flaw not fixed",
    "awaiting_retest": "Patched: awaiting independent retest",
    "fix_failed": "Fix failed: exposure continues after the patch",
    "resolved": "Resolved: fix independently verified for the tested checks",
}


def build_incident_report(*, assessment_id: str, data_source: str, telemetry: Iterable[Any],
                          alerts: Iterable[Alert], events: Iterable[Any] = (),
                          generated_at: str) -> dict[str, Any] | None:
    """Return a JSON-ready incident report, or None when there are no alerts."""
    alerts = tuple(alerts)
    if not alerts:
        return None
    events = sorted((e for e in events if isinstance(e, Mapping) and e.get("type") in REPORT_EVENT_TYPES
                     and isinstance(e.get("data"), Mapping)), key=_event_order)
    by_type: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        by_type.setdefault(event["type"], []).append(event)

    applied = {e["data"].get("defense_id"): e for e in by_type.get("defense.applied", [])}
    patched_versions = {e["data"].get("resulting_version") for e in applied.values()
                        if e["data"].get("action_type") == "apply_patch"}
    patch_retests = [e for e in by_type.get("retest.completed", [])
                     if applied.get(e["data"].get("defense_id"), {}).get("data", {}).get("action_type") == "apply_patch"]
    first_seen = min((a.first_seen for a in alerts), key=parse_utc_timestamp)
    times = {
        "first_unauthorized_read": first_seen,
        "last_unauthorized_read": max((a.last_seen for a in alerts), key=parse_utc_timestamp),
        "detected": _first_time(by_type.get("alert.created", [])),
        "contained": _first_time(e for e in applied.values() if e["data"].get("action_type") == "revoke_session"),
        "patched": _first_time(e for e in applied.values() if e["data"].get("action_type") == "apply_patch"),
        "fix_verified": _first_time(e for e in patch_retests if e["data"].get("result") == "passed"),
    }
    status = _status(alerts, times, patched_versions, patch_retests)
    owners = _unique(o for a in alerts for o in a.resource_owner_refs)
    resources = _unique(r for a in alerts for r in a.resource_ids)
    anonymous = any(a.kind == ANONYMOUS_READ for a in alerts)
    contained = times["contained"] is not None

    report = {
        "schema": REPORT_SCHEMA,
        "incident_id": "incident-" + _digest(sorted(a.alert_id for a in alerts))[:12],
        "title": "Unauthorized access to private records",
        "assessment_id": assessment_id,
        "data_source": data_source,
        "generated_at": generated_at,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "target": {"target_id": alerts[0].target_id,
                   "versions": _unique([a.target_version for a in alerts] +
                                       [e.get("target_version") for e in events if e.get("target_version")])},
        "times": times,
        "elapsed_seconds": {name: _seconds_between(first_seen, value)
                            for name, value in times.items() if name not in ("first_unauthorized_read", "last_unauthorized_read")},
        "scope": {
            "policy_ids": _unique(a.policy_id for a in alerts),
            "actors": _unique(a.actor_ref for a in alerts if a.actor_ref),
            "sessions": _unique(a.session_ref for a in alerts if a.session_ref),
            "unauthenticated_access": anonymous,
            "resources": resources,
            "resource_owners": owners,
        },
        "impact": {
            "confidentiality": f"{len(resources)} private record{'' if len(resources) == 1 else 's'} "
                               f"belonging to {', '.join(owners)} read without authorization.",
            "integrity": "No writes observed in the supplied telemetry.",
            "availability": "No outage observed in the supplied telemetry.",
        },
        "detect": {"alerts": [_alert_entry(a) for a in alerts]},
        "respond": {
            "classification": {
                "category": "broken_access_control",
                "attack": [frameworks.ATTACK_EXPLOIT_APP] +
                          ([frameworks.ATTACK_VALID_ACCOUNTS] if any(a.kind == CROSS_USER_READ for a in alerts) else []),
                "weaknesses": list(frameworks.WEAKNESSES),
                "note": "Analyst mapping for this scenario. ATT&CK describes behavior; CWE and OWASP describe the weakness.",
            },
            "mitigation": _defenses(by_type),
        },
        "recover": {
            "verdicts": [_verdict(e) for t in ("finding.verified", "finding.rejected", "finding.inconclusive")
                         for e in by_type.get(t, [])],
            "retests": [{"finding_id": e["data"].get("finding_id"), "defense_id": e["data"].get("defense_id"),
                         "result": e["data"].get("result"), "checks": list(e["data"].get("checks", [])),
                         "timestamp": e.get("timestamp"), "evidence_refs": list(e.get("evidence_refs", []))}
                        for e in by_type.get("retest.completed", [])],
        },
        "improve": [{**{k: v for k, v in step.items() if k != "when"},
                     "csf_name": frameworks.CSF_CATEGORIES[step["csf"]]}
                    for step in frameworks.PREVENTION
                    if step.get("when") is None or (step["when"] == "anonymous" and anonymous)
                    or (step["when"] == "contained" and contained)],
        "timeline": _timeline(alerts, events),
        "evidence": _telemetry_evidence(alerts, telemetry) + [_event_evidence(e) for e in events],
        "limitations": _limitations(data_source, status, patch_retests),
        "references": frameworks.SOURCES,
    }
    report["integrity"] = {"algorithm": "sha256", "report_digest": _digest(report),
                           "scope": "Canonical JSON of this report without the integrity field."}
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    """Human-readable report. ASCII only so it prints on any console."""
    lines = [f"# Incident {report['incident_id']}: {report['title']}", ""]
    if report["data_source"] != "live":
        lines += [f"> Data source: {report['data_source'].upper()}. This report was not produced from a live run.", ""]
    target = report["target"]
    lines += [f"- **Status:** {report['status_label']}",
              f"- **Target:** {target['target_id']} ({' -> '.join(target['versions'])})",
              f"- **Assessment:** {report['assessment_id']}",
              f"- **Generated:** {report['generated_at']}", ""]

    scope, impact = report["scope"], report["impact"]
    lines += ["## Summary", "", impact["confidentiality"] + " " +
              (f"Actors: {', '.join(scope['actors'])}. " if scope["actors"] else "") +
              ("Unauthenticated requests also read private data. " if scope["unauthenticated_access"] else "") +
              f"Current status: {report['status_label']}.", ""]

    elapsed = report["elapsed_seconds"]
    lines += ["## Key times", "", "| Step | Time (UTC) | After first read |", "| --- | --- | --- |",
              f"| First unauthorized read | {report['times']['first_unauthorized_read']} | - |"]
    for name, label in (("detected", "Detected"), ("contained", "Contained"), ("patched", "Patch applied"),
                        ("fix_verified", "Fix verified")):
        value = report["times"][name]
        lines.append(f"| {label} | {value or 'N/A'} | {_duration(elapsed[name])} |")

    lines += ["", "## Detect (CSF DE.CM, DE.AE)", "",
              "| Alert | Kind | Session | Records | Requests | First seen | Last seen |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for a in report["detect"]["alerts"]:
        lines.append(_row(a["alert_id"], a["kind"], a["session_ref"] or "none", ", ".join(a["resource_ids"]),
                          ", ".join(a["request_ids"]), a["first_seen"], a["last_seen"]))

    classification = report["respond"]["classification"]
    lines += ["", "## Respond", "", "### Analysis (CSF RS.AN)", "", classification["note"], "",
              "| Framework | ID | Name | Why |", "| --- | --- | --- | --- |"]
    for item in classification["attack"] + classification["weaknesses"]:
        lines.append(_row(item["framework"], item["id"], item["name"], item["rationale"]))
    lines += ["", "### Scope and impact", "",
              f"- **Policy:** {', '.join(scope['policy_ids'])}",
              f"- **Sessions involved:** {', '.join(scope['sessions']) or 'none'}",
              f"- **Records read:** {', '.join(scope['resources'])}",
              f"- **Data owners affected:** {', '.join(scope['resource_owners'])}",
              f"- **Integrity:** {impact['integrity']}",
              f"- **Availability:** {impact['availability']}", "",
              "### Mitigation (CSF RS.MI)", ""]
    mitigation = report["respond"]["mitigation"]
    if mitigation:
        lines += ["| Defense | Type | Effect | Outcome | Details |", "| --- | --- | --- | --- | --- |"]
        for d in mitigation:
            lines.append(_row(d["defense_id"], d["action_type"], d["effect"], d["outcome"], d["details"]))
    else:
        lines.append("No defenses proposed or applied yet.")

    recover = report["recover"]
    lines += ["", "## Recover (CSF RC.RP)", "", "Results below come from the independent referee, not from blue.", ""]
    for v in recover["verdicts"]:
        lines.append(f"- Finding {v['finding_id']}: **{v['verdict']}**. {v['summary']}")
    for r in recover["retests"]:
        lines += ["", f"Retest of {r['defense_id']}: **{r['result']}**", "",
                  "| Check | Expected | Actual | Passed |", "| --- | --- | --- | --- |"]
        lines += [_row(c.get("id"), c.get("expected"), c.get("actual"), "yes" if c.get("passed") else "no")
                  for c in r["checks"]]
    if not recover["verdicts"] and not recover["retests"]:
        lines.append("No independent verification results yet.")

    lines += ["", "## Prevent and improve (CSF ID.IM and related)", "",
              "| Step | CSF | Type | References |", "| --- | --- | --- | --- |"]
    for step in report["improve"]:
        lines.append(_row(step["text"], f"{step['csf']} {step['csf_name']}", step["kind"], ", ".join(step["refs"])))

    lines += ["", "## Timeline", "", "| Time (UTC) | Source | Event |", "| --- | --- | --- |"]
    lines += [_row(t["timestamp"], t["source"], t["description"]) for t in report["timeline"]]

    lines += ["", "## Evidence", "", "| Evidence | Kind | Reference | SHA-256 |", "| --- | --- | --- | --- |"]
    for item in report["evidence"]:
        digest = f"`{item['sha256']}`" if item["sha256"] else "not available"
        lines.append(_row(item["evidence_id"], item["kind"], item["reference"], digest))

    lines += ["", "## Limitations", ""] + [f"- {text}" for text in report["limitations"]]
    lines += ["", "## References", ""] + [f"- {name}: {url}" for name, url in report["references"].items()]
    lines += ["", f"Report digest (sha256): `{report['integrity']['report_digest']}`", ""]
    return "\n".join(lines)


def _status(alerts, times, patched_versions, patch_retests) -> str:
    if any(a.target_version in patched_versions for a in alerts):
        return "fix_failed"
    if patch_retests:
        result = patch_retests[-1]["data"].get("result")
        if result == "passed":
            return "resolved"
        if result == "failed":
            return "fix_failed"
    if times["patched"]:
        return "awaiting_retest"
    return "contained" if times["contained"] else "open"


def _defenses(by_type: Mapping[str, list[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for kind in ("defense.proposed", "defense.applied", "defense.failed"):
        for event in by_type.get(kind, []):
            data = event["data"]
            entry = entries.setdefault(str(data.get("defense_id")), {
                "defense_id": str(data.get("defense_id")), "action_type": data.get("action_type"),
                "effect": "containment" if data.get("action_type") == "revoke_session" else "remediation",
                "outcome": "proposed", "details": "", "evidence_refs": []})
            entry["action_type"] = entry["action_type"] or data.get("action_type")
            entry["evidence_refs"] += list(event.get("evidence_refs", []))
            if kind == "defense.proposed":
                entry["details"] = str(data.get("summary", ""))
            elif kind == "defense.applied":
                entry["outcome"] = "applied, awaiting retest" if data.get("action_type") == "apply_patch" else "applied"
                entry["details"] = (f"{entry['details']} Origin {data.get('origin')}; "
                                    f"{data.get('original_version')} -> {data.get('resulting_version')}.").strip()
            else:
                entry["outcome"] = "failed"
                entry["details"] = f"{entry['details']} Failed: {data.get('reason')}.".strip()
    for event in by_type.get("retest.completed", []):
        entry = entries.get(str(event["data"].get("defense_id")))
        if entry and entry["outcome"].startswith("applied"):
            entry["outcome"] = f"applied, retest {event['data'].get('result')}"
    return list(entries.values())


def _limitations(data_source: str, status: str, patch_retests) -> list[str]:
    notes = []
    if data_source != "live":
        notes.append(f"Built from {data_source} data. It shows the report format, not the result of a live run.")
    if status == "resolved":
        covered = {c.get("id") for c in patch_retests[-1]["data"].get("checks", [])}
        missing = [check for check in ACCEPTANCE_CHECKS if check not in covered]
        notes.append("The fix is verified only for the scenario and checks listed under Recover.")
        if missing:
            notes.append("Full acceptance also needs these checks: " + ", ".join(missing) + ".")
    if status == "contained":
        notes.append("Session revocation contains the misuse but does not fix the ownership flaw. A new session can still read the data.")
    notes.append("Detection used telemetry only. Blue did not see red's plan, candidate findings, or reasoning.")
    notes.append("Telemetry fields named like secrets are removed before hashing; digests cover the sanitized records.")
    return notes


def _alert_entry(alert: Alert) -> dict[str, Any]:
    return {"alert_id": alert.alert_id, "kind": alert.kind, "policy_id": alert.policy_id,
            "target_version": alert.target_version, "actor_ref": alert.actor_ref, "session_ref": alert.session_ref,
            "resource_ids": list(alert.resource_ids), "resource_owner_refs": list(alert.resource_owner_refs),
            "request_ids": list(alert.request_ids), "first_seen": alert.first_seen, "last_seen": alert.last_seen,
            "summary": alert.summary}


def _verdict(event: Mapping[str, Any]) -> dict[str, Any]:
    data = event["data"]
    return {"finding_id": data.get("finding_id"), "verdict": data.get("verdict"), "summary": data.get("summary", ""),
            "timestamp": event.get("timestamp"), "evidence_refs": list(event.get("evidence_refs", []))}


def _timeline(alerts: tuple[Alert, ...], events: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    entries = [{"timestamp": a.first_seen, "source": "telemetry", "description": a.summary} for a in alerts]
    for event in events:
        data = event["data"]
        description = data.get("summary") or (
            f"{data.get('action_type')} {data.get('defense_id')} applied ({data.get('origin')})"
            if event["type"] == "defense.applied" else
            f"Retest {data.get('result')}" if event["type"] == "retest.completed" else
            f"{event['type']} {data.get('defense_id', '')}".strip())
        entries.append({"timestamp": str(event.get("timestamp")), "source": f"{event.get('actor')}: {event['type']}",
                        "description": str(description)})
    return sorted(entries, key=lambda e: (parse_utc_timestamp(e["timestamp"]) or datetime.max.replace(tzinfo=timezone.utc)))


def _telemetry_evidence(alerts: tuple[Alert, ...], telemetry: Iterable[Any]) -> list[dict[str, Any]]:
    records = {}
    for record in telemetry:
        if isinstance(record, Mapping) and isinstance(record.get("request_id"), str):
            records.setdefault(record["request_id"], record)
    items = []
    for request_id in _unique(r for a in alerts for r in a.request_ids):
        record = records.get(request_id)
        clean, redacted = _sanitize(record) if record is not None else (None, [])
        item = {"evidence_id": f"telemetry:{request_id}", "kind": "telemetry", "reference": request_id,
                "source": "lab application log", "record": clean,
                "sha256": _digest(clean) if clean is not None else None}
        if redacted:
            item["redacted_fields"] = redacted
        if record is None:
            item["note"] = "Telemetry record was not supplied with the report inputs."
        items.append(item)
    return items


def _event_evidence(event: Mapping[str, Any]) -> dict[str, Any]:
    clean, _ = _sanitize(dict(event))
    return {"evidence_id": f"event:{event.get('id')}", "kind": event["type"],
            "reference": ", ".join(event.get("evidence_refs", [])) or f"event {event.get('id')}",
            "source": str(event.get("actor")), "record": clean, "sha256": _digest(clean)}


def _sanitize(value: Any, path: str = "") -> tuple[Any, list[str]]:
    if isinstance(value, Mapping):
        clean, redacted = {}, []
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if any(marker in str(key).lower() for marker in SECRET_MARKERS):
                redacted.append(child_path)
                continue
            clean[key], nested = _sanitize(child, child_path)
            redacted += nested
        return clean, redacted
    if isinstance(value, list):
        results = [_sanitize(child, f"{path}[{i}]") for i, child in enumerate(value)]
        return [r[0] for r in results], [p for r in results for p in r[1]]
    return value, []


def _event_order(event: Mapping[str, Any]):
    event_id = event.get("id")
    return (0, event_id) if type(event_id) is int else (1, str(event.get("timestamp")))


def _first_time(events: Iterable[Mapping[str, Any]]) -> str | None:
    stamps = [e.get("timestamp") for e in events if parse_utc_timestamp(e.get("timestamp")) is not None]
    return min(stamps, key=parse_utc_timestamp) if stamps else None


def _seconds_between(start: str, end: str | None) -> float | None:
    if end is None:
        return None
    return (parse_utc_timestamp(end) - parse_utc_timestamp(start)).total_seconds()


def _duration(seconds: float | None) -> str:
    return "N/A" if seconds is None else f"+{seconds:g}s"


def _digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _unique(values: Iterable[Any]) -> list[Any]:
    return list(dict.fromkeys(values))


def _row(*cells: Any) -> str:
    return "| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |"
