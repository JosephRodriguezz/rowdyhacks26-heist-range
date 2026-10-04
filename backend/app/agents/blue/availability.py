"""Deterministic HTTP availability Monitor/Defender; proposals only.

An opt-in contract, range.blue.availability/v1, separate from access-control
observe/v1. Core supplies scoped, bounded, target-side aggregate measurements
and a calibrated healthy baseline. No Red plans, credentials or referee verdicts
are accepted. High rate alone is not an attack; errors alone do not prove DDoS.
Never executes a defense or claims recovery. All summaries are fixed templates.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re

SCHEMA = "range.blue.availability/v1"
LIMIT_SOURCE = "limit_http_source"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
SOURCES = {"fixture", "recorded", "live"}
SCOPE_KEYS = ("assessment_id", "target_id", "target_version", "data_source")
CONTEXT_KEYS = {*SCOPE_KEYS, "window", "policy", "budgets", "active_source_refs"}
WINDOW_KEYS = {"window_id", "seconds", "requests", "backend_requests", "server_errors",
               "denied_requests", "inflight", "latency_p95_ms", "data_loss", "sources"}
SOURCE_KEYS = {"source_ref", "requests", "backend_requests", "server_errors", "denied_requests", "inflight"}
COUNTS = ("requests", "backend_requests", "server_errors", "denied_requests", "inflight")


class AvailabilityError(ValueError):
    """A fixed-message validation error; never echoes untrusted values."""


def require(condition, message="Malformed availability input"):
    if not condition:
        raise AvailabilityError(message)


def identifier(value):
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def number(value, low, high):
    return type(value) in (int, float) and low <= value <= high and math.isfinite(value)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class AvailabilityPolicy:
    baseline_rps: float = 5.0
    rate_multiplier: float = 4.0
    min_requests: int = 20
    min_backend_samples: int = 5
    error_ratio: float = .25
    latency_limit_ms: float = 500.0
    inflight_threshold: int = 8
    suspect_source_rps: float = 10.0
    limit_rps: float = 2.0
    burst: int = 2
    ttl_seconds: float = 15.0
    max_proposals: int = 4

    def __post_init__(self):
        ranges = {"baseline_rps": (.1, 10000), "rate_multiplier": (2, 100), "error_ratio": (.01, 1),
                  "latency_limit_ms": (1, 60000), "suspect_source_rps": (.1, 10000),
                  "limit_rps": (.1, 10), "ttl_seconds": (1, 60)}
        integers = {"min_requests": (1, 100000), "min_backend_samples": (1, 100000),
                    "inflight_threshold": (1, 1024), "burst": (1, 20), "max_proposals": (1, 8)}
        for field, (low, high) in {**ranges, **integers}.items():
            value = getattr(self, field)
            require(number(value, low, high) and (field not in integers or type(value) is int), "Invalid availability policy")
        require(self.limit_rps < self.suspect_source_rps, "Source limit must be below the suspicion threshold")


def parse_policy(value):
    if isinstance(value, AvailabilityPolicy):
        return value
    require(type(value) is dict and set(value) <= set(asdict(AvailabilityPolicy())), "Invalid availability policy")
    return AvailabilityPolicy(**value)


def validate_window(window):
    require(type(window) is dict and set(window) == WINDOW_KEYS)
    require(identifier(window["window_id"]))
    require(number(window["seconds"], .1, 300))
    require(type(window["data_loss"]) is bool)
    require(window["latency_p95_ms"] is None or number(window["latency_p95_ms"], 0, 300000))
    rows = window["sources"]
    require(type(rows) is list and len(rows) <= 256, "Availability source window exceeds its bound")
    require(all(type(row) is dict and set(row) == SOURCE_KEYS and identifier(row["source_ref"]) for row in rows))
    seen = set()
    for item in [window, *rows]:
        for field in COUNTS:
            require(type(item.get(field)) is int and 0 <= item[field] <= 1000000)
        require(item["server_errors"] <= item["backend_requests"] <= item["requests"])
        require(item["backend_requests"] + item["denied_requests"] <= item["requests"])
    for row in rows:
        require(type(row) is dict and set(row) == SOURCE_KEYS and identifier(row["source_ref"]))
        require(row["source_ref"] not in seen, "Duplicate availability source")
        seen.add(row["source_ref"])
    for field in COUNTS:
        require(sum(row[field] for row in rows) == window[field], "Availability counts do not reconcile")
    return window


def parse_context(context):
    require(type(context) is dict and set(context) <= CONTEXT_KEYS and set(SCOPE_KEYS) | {"window", "policy"} <= set(context))
    require(all(identifier(context[key]) for key in SCOPE_KEYS[:-1]), "Invalid availability scope")
    require(type(context["data_source"]) is str and context["data_source"] in SOURCES)
    validate_window(context["window"])
    policy = parse_policy(context["policy"])
    budgets = context.get("budgets", {})
    require(type(budgets) is dict and set(budgets) <= {"max_steps", "max_requests", "timeout_seconds"})
    require(all(number(v, 0, 1000000) for v in budgets.values()), "Invalid availability budget")
    active = context.get("active_source_refs", [])
    require(type(active) is list and len(active) <= 256 and all(identifier(ref) for ref in active))
    return policy, budgets, set(active)


def _output(context, status, assessment, alerts=(), proposals=(), evidence=()):
    blocked = status != "completed" or assessment == "inconclusive"
    response_blocked = blocked or (assessment != "healthy" and not proposals)
    return {"schema": SCHEMA, **{k: context[k] for k in SCOPE_KEYS}, "status": status, "assessment": assessment,
            "alerts": list(alerts), "defense_proposals": list(proposals), "evidence_refs": list(evidence),
            "recovery_verified": False, "fix_status": "not_assessed", "agents": [
                {"agent_id": "monitor", "status": "blocked" if blocked else "completed",
                 "summary": f"Availability observation recorded; {len(alerts)} alert(s)."},
                {"agent_id": "defender", "status": "blocked" if response_blocked else "completed",
                 "summary": f"{len(proposals)} bounded traffic response(s) proposed; recovery is unverified."}]}


def _observe_availability(context, tools=None):
    policy, budgets, active = parse_context(context)
    if any(v <= 0 for v in budgets.values()):
        return _output(context, "budget_exhausted", "inconclusive")
    if tools is not None and tools.cancelled():
        return _output(context, "cancelled", "inconclusive")
    window = context["window"]
    if window["data_loss"] or (window["backend_requests"] < policy.min_backend_samples and window["inflight"] < policy.inflight_threshold):
        return _output(context, "completed", "inconclusive")
    errors = window["server_errors"] / max(1, window["backend_requests"])
    degraded = (errors >= policy.error_ratio or window["inflight"] >= policy.inflight_threshold or
                (window["latency_p95_ms"] is not None and window["latency_p95_ms"] > policy.latency_limit_ms))
    if not degraded:
        return _output(context, "completed", "healthy")
    rate = window["requests"] / window["seconds"]
    pressure = window["requests"] >= policy.min_requests and rate >= policy.baseline_rps * policy.rate_multiplier
    evidence_id = "availability-" + window["window_id"]
    checksum = digest({**{k: context[k] for k in SCOPE_KEYS}, "window": window})
    assessment = "suspected_http_flood" if pressure else "availability_degraded_cause_unknown"
    alert = {"alert_id": "alert-" + checksum[:16], "kind": assessment, "evidence_refs": [evidence_id],
             "summary": "Request pressure and availability degradation observed; attack attribution is not independently verified."
                        if pressure else "Availability degraded; traffic evidence does not establish an HTTP flood."}
    proposals = []
    if pressure:
        ordered = sorted(window["sources"], key=lambda s: (-s["requests"], s["source_ref"]))
        for source in ordered:
            if (source["source_ref"] in active or source["requests"] / window["seconds"] < policy.suspect_source_rps):
                continue
            key = digest([context["assessment_id"], checksum, source["source_ref"]])
            proposals.append({**{k: context[k] for k in SCOPE_KEYS}, "defense_id": "limit-" + key[:20],
                "action_type": LIMIT_SOURCE, "effect": "containment", "window_id": window["window_id"],
                "window_digest": checksum, "evidence_refs": [evidence_id],
                "parameters": {"source_ref": source["source_ref"], "rate_per_second": policy.limit_rps,
                               "burst": policy.burst, "ttl_seconds": policy.ttl_seconds},
                "summary": "Temporarily limit one observed high-rate source; do not block all bank clients.",
                "expected_result": "This source's excess requests are refused while ordinary bank access remains available; referee checks are required."})
            if len(proposals) >= policy.max_proposals:
                break
    return _output(context, "completed", assessment, [alert], proposals, [evidence_id])


async def observe_availability(context, tools=None):
    return _observe_availability(context, tools)
