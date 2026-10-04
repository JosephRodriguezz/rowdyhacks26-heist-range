"""Blue's `observe(context, tools)` module boundary.

Core hands blue a bounded context: target and version IDs, sanitized telemetry,
the access policy, previous defenses, and remaining budgets. observe() runs the
existing pieces in order (detection, session revocations, the ownership patch,
the incident report) and returns JSON-ready results. It makes no network calls
and executes nothing: blue proposes, core executes, and the referee verifies.

The context is untrusted. Any top-level key outside CONTEXT_KEYS raises
ContextError, so red plans, candidates, ground truth, or referee verdicts that
leak into the context fail loudly instead of being silently dropped. Inside the
allowed keys, telemetry and previous defenses are projected onto known fields
and scoped to this target, assessment, data source, and version before anything
uses them.
No retest or referee event reaches the report, so its status can never be
`resolved`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
import re
from typing import Any

from .detection import (ANONYMOUS_READ, CROSS_USER_READ, TELEMETRY_FIELDS, AccessPolicy, detect_suspicious_access,
                        parse_utc_timestamp, record_problem)
from .incident import build_incident_report
from .patches import load_patch_manifest
from .proposals import (APPLY_PATCH, REVOKE_SESSION, DefenseProposal, propose_ownership_patch,
                        propose_session_revocations, revocation_id)

OBSERVE_SCHEMA = "range.blue.observe/v1"
OWNERSHIP_PATCH_ID = "ownership-fix-001"
CONTEXT_KEYS = frozenset({"target_id", "target_version", "data_source", "telemetry", "access_policy",
                          "previous_defenses", "budgets", "assessment_id", "generated_at"})
REQUIRED_KEYS = ("target_id", "target_version", "data_source", "telemetry", "access_policy")
DATA_SOURCES = frozenset({"fixture", "live", "recorded"})
BUDGET_KEYS = frozenset({"max_steps", "max_requests", "timeout_seconds"})
POLICY_KEYS = frozenset({"id", "owner_only_actions"})
MAX_TELEMETRY_RECORDS = 10_000
# Mirrors shared/contracts/v1.json; a test keeps the two in sync.
ALERT_REQUIRED = ("alert_id", "request_ids", "summary")
PROPOSAL_REQUIRED = ("defense_id", "action_type", "summary", "reason", "parameters")
EVENT_REQUIRED = ("schema_version", "id", "assessment_id", "timestamp", "type", "actor", "target_id",
                  "target_version", "data_source", "evidence_refs", "data")
DEFENSE_EVENTS = {  # type: (actor, required data keys)
    "defense.proposed": ("blue", PROPOSAL_REQUIRED),
    "defense.applied": ("system", ("defense_id", "action_type", "origin", "original_version", "resulting_version")),
    "defense.failed": ("system", ("defense_id", "reason")),
}
ACTION_TYPES = frozenset({REVOKE_SESSION, APPLY_PATCH})
PARAMETER_KEYS = ("session_ref", "patch_id", "base_version")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}")
# Core's free-text failure reason may hold a credential value, so blue never copies it.
FAILED_REASON = "core reported the defense failed; its reason text is not copied into blue's output"
REPORT_SCOPE = ("Blue-side report: built from telemetry, blue's own alerts and proposals, and system defense "
                "outcomes. It holds no referee verdicts or retests and is not the final incident record.")


class ContextError(ValueError):
    pass


@dataclass(frozen=True)
class BlueContext:
    target_id: str
    target_version: str
    data_source: str
    telemetry: tuple[Any, ...]
    policy: AccessPolicy
    previous_defenses: tuple[dict[str, Any], ...]  # projected defense events
    budgets: Mapping[str, float]
    assessment_id: str | None
    generated_at: str | None


def parse_context(context: Any) -> BlueContext:
    """Validate core's context against the allowlist. Never returns or keeps the raw object."""
    _require(isinstance(context, Mapping), "context must be an object")
    unknown = sorted(str(key) for key in context if key not in CONTEXT_KEYS)
    _require(not unknown, "context has keys blue may not receive: " + ", ".join(unknown))
    missing = [key for key in REQUIRED_KEYS if key not in context]
    _require(not missing, "context missing " + ", ".join(missing))
    for key in ("target_id", "target_version"):
        _require(_text(context[key]), f"{key} must be a non-empty string")
    _require(isinstance(context["data_source"], str) and context["data_source"] in DATA_SOURCES,
             "data_source must be fixture, live, or recorded")
    for key in ("assessment_id", "generated_at"):
        _require(context.get(key) is None or _text(context[key]), f"{key} must be a non-empty string")
    _require(context.get("generated_at") is None or parse_utc_timestamp(context["generated_at"]) is not None,
             "generated_at must be ISO 8601 UTC ending in Z")
    telemetry = context["telemetry"]
    _require(isinstance(telemetry, (list, tuple)), "telemetry must be a list")
    _require(len(telemetry) <= MAX_TELEMETRY_RECORDS, f"telemetry exceeds {MAX_TELEMETRY_RECORDS} records")
    return BlueContext(
        target_id=context["target_id"], target_version=context["target_version"],
        data_source=context["data_source"], telemetry=tuple(telemetry),
        policy=_policy(context["access_policy"]),
        previous_defenses=_previous_defenses(context.get("previous_defenses", ()), context.get("assessment_id"),
                                             context["data_source"]),
        budgets=_budgets(context.get("budgets", {})),
        assessment_id=context.get("assessment_id"), generated_at=context.get("generated_at"),
    )


async def observe(context: Any, tools: Any = None) -> dict[str, Any]:
    """Run detection, proposals, and the blue-side report for one observation.

    `tools` is optional and inert in M1. observe() reads only `tools.cancelled()`
    and `tools.now()` when present; it never asks tools to make a request or
    execute a defense.
    """
    ctx = parse_context(context)
    # max_requests is not checked: observe sends no requests. Recheck it when tools can execute.
    exhausted = [key for key in ("max_steps", "timeout_seconds") if key in ctx.budgets and ctx.budgets[key] <= 0]
    if exhausted:
        return _empty(ctx, "budget_exhausted", f"Observation not run: budget exhausted ({', '.join(exhausted)}).")
    cancelled = getattr(tools, "cancelled", None) if tools is not None else None
    if callable(cancelled) and cancelled():
        return _empty(ctx, "cancelled", "Observation not run: cancelled by core.")
    generated_at = ctx.generated_at or _tool_time(tools)

    in_scope, skipped = _scope(ctx)
    detection = detect_suspicious_access(in_scope, ctx.policy)
    skipped += [{"request_id": s.request_id, "reason": s.reason} for s in detection.skipped]
    alerts = detection.alerts
    notes, patch = [], None
    dedup, outcomes = _scope_defenses(ctx, notes)
    revoked, outcomes = _containment(ctx, alerts, dedup, outcomes, notes)
    dedup += [{"action_type": REVOKE_SESSION, "parameters": {"session_ref": s}} for s in sorted(revoked)]
    revocations = propose_session_revocations(alerts, dedup)

    if alerts:
        try:
            manifest = load_patch_manifest(OWNERSHIP_PATCH_ID)
        except (OSError, ValueError) as error:
            notes.append(f"Ownership patch {OWNERSHIP_PATCH_ID} could not be loaded "
                         f"({type(error).__name__}); no patch proposed.")
        else:
            patch = propose_ownership_patch(alerts, manifest, ctx.target_version, dedup)
            if manifest.base_version != ctx.target_version:
                notes.append(f"Ownership patch {OWNERSHIP_PATCH_ID} targets {manifest.base_version}, "
                             f"not {ctx.target_version}; not proposed.")
            elif patch is not None and not manifest.ready:
                notes.append(f"Ownership patch {OWNERSHIP_PATCH_ID} is a draft; the executor must refuse it.")
    proposals = revocations + ((patch,) if patch else ())

    alert_data = [alert.event_data() for alert in alerts]
    proposal_data = [proposal.event_data() for proposal in proposals]
    _check_payloads(alert_data, ALERT_REQUIRED, "alert.created")
    _check_payloads(proposal_data, PROPOSAL_REQUIRED, "defense.proposed")

    report = None
    if alerts:
        if generated_at is None:
            raise ContextError("generated_at must come from the context or tools.now() to build the report")
        events = _blue_events(ctx, alert_data, proposal_data, generated_at) + outcomes
        report = build_incident_report(assessment_id=ctx.assessment_id or "unspecified",
                                       data_source=ctx.data_source, telemetry=in_scope, alerts=alerts,
                                       events=events, generated_at=generated_at)
        if report["status"] == "resolved":
            raise RuntimeError("blue-side report must never mark a fix as resolved")

    return {
        "schema": OBSERVE_SCHEMA,
        "status": "completed",
        "assessment_id": ctx.assessment_id,
        "target_id": ctx.target_id,
        "target_version": ctx.target_version,
        "data_source": ctx.data_source,
        "alerts": alert_data,
        "defense_proposals": proposal_data,
        "evidence_refs": list(dict.fromkeys(f"telemetry:{r}" for a in alerts for r in a.request_ids)),
        "skipped": skipped,
        "summary": _summary(alerts, revocations, patch, len(skipped)),
        "report": report,
        "report_scope": REPORT_SCOPE if report else None,
        "notes": notes,
    }


def _policy(value: Any) -> AccessPolicy:
    if isinstance(value, AccessPolicy):
        policy_id, actions = value.id, value.owner_only_actions
    else:
        _require(isinstance(value, Mapping), "access_policy must be an object")
        _require(set(value) <= POLICY_KEYS, "access_policy may hold only id and owner_only_actions")
        policy_id, actions = value.get("id"), value.get("owner_only_actions")
    _require(_text(policy_id), "access_policy id must be a non-empty string")
    _require(isinstance(actions, (list, tuple, set, frozenset)) and actions and all(_text(a) for a in actions),
             "access_policy owner_only_actions must be a non-empty list of strings")
    return AccessPolicy(policy_id, frozenset(actions))


def _previous_defenses(value: Any, assessment_id: Any, data_source: str) -> tuple[dict[str, Any], ...]:
    """Validate previous defenses and project each onto the fields blue uses.

    Entries must be contract defense events or blue's own in-process
    DefenseProposal objects, so every entry names its target. Free text such as
    a proposal's summary and reason, a failure reason, and any field not listed
    here, is dropped.
    """
    _require(isinstance(value, (list, tuple)), "previous_defenses must be a list")
    return tuple(_defense_event(entry, assessment_id, data_source) for entry in value)


def _defense_event(entry: Any, assessment_id: Any, data_source: str) -> dict[str, Any]:
    if isinstance(entry, DefenseProposal):
        # Blue's own object from this process: it has a target but no assessment or data source,
        # so it counts for this observation's.
        _require(_identifier(entry.target_id) and _identifier(entry.target_version),
                 "DefenseProposal target_id and target_version must be identifiers")
        return {"type": "defense.proposed", "actor": "blue", "assessment_id": assessment_id,
                "target_id": entry.target_id, "target_version": entry.target_version, "data_source": data_source,
                "data": _defense_data("defense.proposed", entry.event_data())}
    _require(isinstance(entry, Mapping), "previous_defenses entries must be defense events or DefenseProposal objects")
    kind = entry.get("type")
    _require(isinstance(kind, str) and kind in DEFENSE_EVENTS,
             "previous_defenses may hold only defense.proposed, defense.applied, or defense.failed events")
    missing = [key for key in EVENT_REQUIRED if key not in entry]
    _require(not missing, f"{kind} event missing " + ", ".join(missing))
    actor = DEFENSE_EVENTS[kind][0]
    _require(entry["actor"] == actor, f"{kind} event actor must be {actor}")
    _require(entry["schema_version"] == "1.0", f"{kind} event schema_version must be 1.0")
    _require(type(entry["id"]) is int or _identifier(entry["id"]), f"{kind} event id must be an integer or identifier")
    _require(parse_utc_timestamp(entry["timestamp"]) is not None, f"{kind} event timestamp must be ISO 8601 UTC")
    for key in ("assessment_id", "target_id", "target_version"):
        _require(_identifier(entry[key]), f"{kind} event {key} must be an identifier")
    _require(isinstance(entry["data_source"], str) and entry["data_source"] in DATA_SOURCES,
             f"{kind} event data_source must be fixture, live, or recorded")
    refs = entry["evidence_refs"]
    _require(isinstance(refs, (list, tuple)) and all(_identifier(r) for r in refs),
             f"{kind} event evidence_refs must be a list of identifiers")
    return {"schema_version": "1.0", "id": entry["id"], "assessment_id": entry["assessment_id"],
            "timestamp": entry["timestamp"], "type": kind, "actor": actor, "target_id": entry["target_id"],
            "target_version": entry["target_version"], "data_source": entry["data_source"],
            "evidence_refs": list(refs), "data": _defense_data(kind, entry["data"])}


def _defense_data(kind: str, data: Any) -> dict[str, Any]:
    _require(isinstance(data, Mapping), f"{kind} data must be an object")
    missing = [key for key in DEFENSE_EVENTS[kind][1] if key not in data]
    _require(not missing, f"{kind} data missing " + ", ".join(missing))
    _require(_identifier(data["defense_id"]), f"{kind} defense_id must be an identifier")
    projected = {"defense_id": data["defense_id"]}
    if "action_type" in data:
        _require(isinstance(data["action_type"], str) and data["action_type"] in ACTION_TYPES,
                 f"{kind} action_type must be revoke_session or apply_patch")
        projected["action_type"] = data["action_type"]
    if kind == "defense.proposed":
        parameters = data["parameters"]
        _require(isinstance(parameters, Mapping), f"{kind} parameters must be an object")
        projected["parameters"] = {key: parameters[key] for key in PARAMETER_KEYS
                                   if key in parameters and _identifier(parameters[key])}
    elif kind == "defense.applied":
        for key in ("origin", "original_version", "resulting_version"):
            _require(_identifier(data[key]), f"{kind} {key} must be an identifier")
            projected[key] = data[key]
    else:
        _require(isinstance(data["reason"], str), f"{kind} reason must be a string")
        projected["reason"] = FAILED_REASON
    return projected


def _budgets(value: Any) -> dict[str, float]:
    _require(isinstance(value, Mapping), "budgets must be an object")
    _require(set(value) <= BUDGET_KEYS, "budgets may hold only max_steps, max_requests, timeout_seconds")
    for key, amount in value.items():
        _require(type(amount) in (int, float), f"budget {key} must be a number")
        _require(type(amount) is int or math.isfinite(amount), f"budget {key} must be finite")
    return dict(value)


def _scope(ctx: BlueContext) -> tuple[list[Any], list[dict[str, Any]]]:
    """Split telemetry into this target/version/assessment and everything else.

    In-scope records are projected onto TELEMETRY_FIELDS with scalar values only,
    so extra fields (ground truth, secrets, nested data) never reach detection,
    the report, or its digests. Each projected record is validated before its
    request_id is reserved, so a malformed record cannot shadow a valid one. A
    repeated request_id among valid records is skipped so each evidence reference
    names exactly one record.
    """
    in_scope, skipped, seen = [], [], set()
    for record in ctx.telemetry:
        if not isinstance(record, Mapping):
            skipped.append({"request_id": None, "reason": record_problem(record, ctx.policy)})
            continue
        request_id = record.get("request_id") if isinstance(record.get("request_id"), str) else None
        projected = {key: record[key] for key in TELEMETRY_FIELDS
                     if key in record and (record[key] is None or type(record[key]) in (str, int))}
        if isinstance(record.get("target_id"), str) and record["target_id"] != ctx.target_id:
            reason = "target_id does not match the context"
        elif isinstance(record.get("target_version"), str) and record["target_version"] != ctx.target_version:
            reason = "target_version does not match the context"
        elif "assessment_id" in record and record["assessment_id"] != ctx.assessment_id:
            reason = "assessment_id does not match the context"
        elif "data_source" in record and record["data_source"] != ctx.data_source:
            reason = "data_source does not match the context"
        else:
            reason = record_problem(projected, ctx.policy)
            if reason is None and request_id in seen:
                reason = "duplicate request_id"
        if reason:
            skipped.append({"request_id": request_id, "reason": reason})
            continue
        seen.add(request_id)
        in_scope.append(projected)
    return in_scope, skipped


def _scope_defenses(ctx: BlueContext, notes: list[str]) -> tuple[list[dict], list[dict]]:
    """Previous defenses for this target, assessment, and data source.

    Returns (data for deduplication, system outcomes for the report). A fixture or
    recorded event never deduplicates or changes the status of a live observation,
    and the reverse. Outcomes must also concern this target version: the event's
    own version, or a patch whose original or resulting version is this one.
    Proposals only deduplicate; blue's report uses this observation's proposals.
    Retests and verdicts never get here.
    """
    dedup, outcomes = [], []
    left_out = {"another target": 0, "another assessment": 0, "another data source": 0,
                "another target version": 0}
    for event in ctx.previous_defenses:
        if event["target_id"] != ctx.target_id:
            left_out["another target"] += 1
            continue
        if event["assessment_id"] != ctx.assessment_id:
            left_out["another assessment"] += 1
            continue
        if event["data_source"] != ctx.data_source:
            left_out["another data source"] += 1
            continue
        dedup.append(event["data"])
        if event["type"] == "defense.proposed":
            continue
        versions = {event["target_version"], event["data"].get("original_version"),
                    event["data"].get("resulting_version")}
        if ctx.target_version not in versions:
            left_out["another target version"] += 1
            continue
        outcomes.append(event)
    for scope, count in left_out.items():
        if count:
            notes.append(f"{count} previous defense event(s) for {scope} were left out.")
    return dedup, outcomes


def _containment(ctx: BlueContext, alerts, dedup: list[dict], outcomes: list[dict],
                 notes: list[str]) -> tuple[set[str], list[dict]]:
    """Tie applied revocations to sessions; keep them in the report only if they contain every alert.

    defense.applied names no session, so each applied revocation is matched to one
    through a scoped defense.proposed with the same defense_id, or the revocation
    ID blue derives for an alerted session. If any alert is anonymous, comes from
    a session no applied revocation names, or has an unauthorized read at or after
    its session's first applied revocation, the exposure is not contained, so the
    applied revocations are left out of the report and its status stays open.
    Returns (revoked session refs, outcomes for the report).
    """
    sessions = {d["defense_id"]: d["parameters"]["session_ref"] for d in dedup
                if d.get("action_type") == REVOKE_SESSION and "session_ref" in d.get("parameters", {})}
    sessions.update({revocation_id(ctx.target_id, a.session_ref): a.session_ref for a in alerts if a.session_ref})
    applied = [e for e in outcomes
               if e["type"] == "defense.applied" and e["data"].get("action_type") == REVOKE_SESSION]
    revoked_at = {}  # session_ref: first applied revocation time
    for e in applied:
        session = sessions.get(e["data"]["defense_id"])
        when = parse_utc_timestamp(e["timestamp"])
        if session is not None and (session not in revoked_at or when < revoked_at[session]):
            revoked_at[session] = when
    uncovered = [a.alert_id for a in alerts if a.kind != CROSS_USER_READ or a.session_ref not in revoked_at]
    # A read in the same second as the revocation cannot be ordered, so it counts as continued access.
    continued = [a.alert_id for a in alerts if a.alert_id not in uncovered
                 and parse_utc_timestamp(a.last_seen) >= revoked_at[a.session_ref]]
    if not applied or not (uncovered or continued):
        return set(revoked_at), outcomes
    reasons = ([f"{_count(len(uncovered), 'alert')} ({', '.join(uncovered)}) not covered by a revoked session"]
               if uncovered else []) + \
              ([f"{_count(len(continued), 'alert')} ({', '.join(continued)}) with reads at or after the revocation"]
               if continued else [])
    notes.append(f"{_count(len(applied), 'applied session revocation')} left out of the report: "
                 f"{'; '.join(reasons)}, so the exposure is not contained.")
    return set(revoked_at), [e for e in outcomes if e not in applied]


def _blue_events(ctx: BlueContext, alerts: list[dict], proposals: list[dict], timestamp: str) -> list[dict]:
    """Blue's own alert.created and defense.proposed events, timed at this observation."""
    return ([_event(ctx, "alert.created", a, timestamp, a["alert_id"], [f"telemetry:{r}" for r in a["request_ids"]])
             for a in alerts] +
            [_event(ctx, "defense.proposed", p, timestamp, p["defense_id"], []) for p in proposals])


def _event(ctx: BlueContext, kind: str, data: dict, timestamp: str, event_id: str, refs: list[str]) -> dict:
    return {"schema_version": "1.0", "id": event_id, "assessment_id": ctx.assessment_id, "timestamp": timestamp,
            "type": kind, "actor": "blue", "target_id": ctx.target_id, "target_version": ctx.target_version,
            "data_source": ctx.data_source, "evidence_refs": refs, "data": data}


def _check_payloads(payloads: list[dict], required: tuple[str, ...], kind: str) -> None:
    for payload in payloads:
        missing = [key for key in required if key not in payload]
        if missing:
            raise RuntimeError(f"{kind} payload missing {', '.join(missing)}")


def _summary(alerts, revocations, patch, skipped: int) -> str:
    cross = sum(1 for a in alerts if a.kind == CROSS_USER_READ)
    anonymous = sum(1 for a in alerts if a.kind == ANONYMOUS_READ)
    if not alerts:
        text = "No suspicious access detected. No defenses proposed."
    else:
        text = (f"Detected {_count(len(alerts), 'alert')} ({cross} {CROSS_USER_READ}, {anonymous} {ANONYMOUS_READ}). "
                f"Proposed {_count(len(revocations), 'session revocation')} (containment, not a fix) and "
                f"{_count(1 if patch else 0, 'patch', 'patches')}"
                + (f" ({patch.details.get('patch_status')}, unverified until the referee retests)." if patch else "."))
    return text + (f" Skipped {_count(skipped, 'telemetry record')}." if skipped else "")


def _empty(ctx: BlueContext, status: str, summary: str) -> dict[str, Any]:
    return {"schema": OBSERVE_SCHEMA, "status": status, "assessment_id": ctx.assessment_id,
            "target_id": ctx.target_id, "target_version": ctx.target_version, "data_source": ctx.data_source,
            "alerts": [], "defense_proposals": [], "evidence_refs": [], "skipped": [], "summary": summary,
            "report": None, "report_scope": None, "notes": [summary]}


def _tool_time(tools: Any) -> str | None:
    now = getattr(tools, "now", None) if tools is not None else None
    if not callable(now):
        return None
    value = now()
    _require(parse_utc_timestamp(value) is not None, "tools.now() must return ISO 8601 UTC ending in Z")
    return value


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else plural or singular + 's'}"


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContextError(message)
