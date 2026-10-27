"""Red candidate generation from application observations only.

This module knows no seeded IDs, lab source, telemetry, or evaluator ground truth.
Every request is a relative path passed to the caller's HTTP adapter. This runner
has local budget checks as a second bound; core must enforce budgets and scope too.
"""

import asyncio
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .decision import DecisionProvider, DeterministicDecisionProvider, TestOption


POLICY_ID = "private-orders-owner-only"
FORBIDDEN_CONTEXT = frozenset({
    "ground_truth", "seeded_flaws", "lab_source", "telemetry", "blue_context",
    "verdicts", "verification", "source_code", "passwords", "tokens",
})
PATH = re.compile(r"^/(?!/)[A-Za-z0-9/_{}.-]*$")


class ContextError(ValueError):
    pass


@dataclass(frozen=True)
class RedContext:
    assessment_id: str
    target_id: str
    target_version: str
    entry_path: str
    account_refs: Mapping[str, str]
    max_steps: int
    max_requests: int
    timeout_seconds: float
    data_source: str = "live"
    policy_id: str = POLICY_ID
    fresh_account_refs: Mapping[str, str] | None = None

    @classmethod
    def from_input(cls, raw: Mapping[str, Any]) -> "RedContext":
        if not isinstance(raw, Mapping):
            raise ContextError("red context must be an object")
        if FORBIDDEN_CONTEXT.intersection(raw):
            raise ContextError("red context contains privileged fields")
        budgets = raw.get("budgets", {})
        if not isinstance(budgets, Mapping):
            raise ContextError("budgets must be an object")
        accounts = raw.get("account_refs")
        if not isinstance(accounts, Mapping) or len(accounts) < 2:
            raise ContextError("at least two account references are required")
        if any(not _identifier(k) or not _identifier(v) for k, v in accounts.items()):
            raise ContextError("account references must be nonempty identifiers")
        fresh_accounts = raw.get("fresh_account_refs")
        if fresh_accounts is not None:
            if not isinstance(fresh_accounts, Mapping) or any(
                key not in accounts or not _identifier(key) or not _identifier(value)
                for key, value in fresh_accounts.items()
            ):
                raise ContextError("fresh account references must match permitted accounts")
        values = {
            "assessment_id": raw.get("assessment_id"),
            "target_id": raw.get("target_id"),
            "target_version": raw.get("target_version"),
            "policy_id": raw.get("policy_id", POLICY_ID),
        }
        if any(not _identifier(v) for v in values.values()):
            raise ContextError("assessment, target, version, and policy identifiers are required")
        entry = raw.get("entry_path", "/")
        if not _safe_path(entry):
            raise ContextError("entry_path must be a relative-origin path")
        steps = budgets.get("max_steps", raw.get("max_steps", 16))
        requests = budgets.get("max_requests", raw.get("max_requests", 16))
        timeout = budgets.get("timeout_seconds", raw.get("timeout_seconds", 10))
        if type(steps) is not int or steps < 0 or type(requests) is not int or requests < 0:
            raise ContextError("step and request budgets must be nonnegative integers")
        if type(timeout) not in (int, float) or timeout <= 0:
            raise ContextError("timeout_seconds must be positive")
        source = raw.get("data_source", "live")
        if source not in ("live", "fixture", "recorded"):
            raise ContextError("invalid data_source")
        return cls(values["assessment_id"], values["target_id"], values["target_version"], entry,
                   dict(accounts), steps, requests, float(timeout), source, values["policy_id"],
                   dict(fresh_accounts) if fresh_accounts is not None else None)


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and len(value) <= 128 and re.fullmatch(r"[A-Za-z0-9_.:-]+", value) is not None


def _safe_path(value: Any) -> bool:
    return (isinstance(value, str) and len(value) <= 256 and PATH.fullmatch(value) is not None
            and ".." not in value and "\\" not in value and "{" not in value and "}" not in value)


def _body(result: Mapping[str, Any]) -> Any:
    response = result.get("response")
    if isinstance(response, Mapping) and "body" in response:
        return response["body"]
    return result.get("body")


def _status(result: Mapping[str, Any]) -> int | None:
    response = result.get("response")
    value = response.get("status") if isinstance(response, Mapping) else result.get("status")
    return value if type(value) is int else None


def _links(body: Any) -> list[str]:
    if not isinstance(body, Mapping):
        return []
    raw = body.get("links", [])
    if isinstance(raw, Mapping):
        raw = list(raw.values())
    if not isinstance(raw, list):
        return []
    paths = []
    for item in raw:
        path = item if isinstance(item, str) else item.get("href") if isinstance(item, Mapping) else None
        if _safe_path(path) and path not in paths:
            paths.append(path)
    return paths[:16]


def _orders(body: Any) -> list[dict[str, str]]:
    if not isinstance(body, Mapping) or not isinstance(body.get("orders"), list):
        return []
    found = []
    for item in body["orders"][:32]:
        if not isinstance(item, Mapping):
            continue
        resource_id = item.get("id")
        if type(resource_id) is int and resource_id >= 0:
            resource_id = str(resource_id)
        if not _identifier(resource_id):
            continue
        paths = {name: item.get(name) for name in ("href", "secure_href")}
        if not _safe_path(paths["href"]):
            continue
        record = {"id": resource_id, "href": paths["href"]}
        if _safe_path(paths["secure_href"]):
            record["secure_href"] = paths["secure_href"]
        found.append(record)
    return found


def _template(path: str, resource_id: str) -> str | None:
    suffix = "/" + resource_id
    if not path.endswith(suffix):
        return None
    return path[:-len(resource_id)] + "{id}"


def _private_identity(body: Any, expected_id: str) -> tuple[str, str] | None:
    if not isinstance(body, Mapping):
        return None
    # The lab wraps private records in an ``order`` object.  Keep the
    # comparison limited to the record identity and canary marker; red never
    # receives ownership telemetry or evaluator ground truth.
    if isinstance(body.get("order"), Mapping):
        body = body["order"]
    body_id = body.get("id")
    marker = body.get("canary") or body.get("private_marker")
    if str(body_id) != expected_id or not isinstance(marker, str) or not marker:
        return None
    return expected_id, marker


class _BudgetStop(Exception):
    def __init__(self, status: str):
        self.status = status


class _Runner:
    def __init__(self, context: RedContext, tools: Any, provider: DecisionProvider):
        self.ctx = context
        self.tools = tools
        self.provider = provider
        self.requests = 0
        self.steps = 0
        self.discoveries: list[dict[str, Any]] = []
        self.candidates: list[dict[str, Any]] = []
        self.evidence_refs: list[str] = []
        self.observations: list[dict[str, Any]] = []
        self.adaptation: dict[str, Any] | None = None
        self.deadline = asyncio.get_running_loop().time() + context.timeout_seconds

    async def request(self, path: str, actor: str | None = None,
                      credential_ref: str | None = None) -> Mapping[str, Any]:
        if not _safe_path(path):
            raise ContextError("observed path is unsafe")
        cancelled = getattr(self.tools, "cancelled", None)
        if callable(cancelled) and cancelled():
            raise _BudgetStop("cancelled")
        if self.requests >= self.ctx.max_requests or self.steps >= self.ctx.max_steps:
            raise _BudgetStop("budget_exhausted")
        remaining = self.deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise _BudgetStop("timeout")
        self.requests += 1
        self.steps += 1
        request_id = f"red-{self.ctx.assessment_id}-{self.requests}"
        request = {"target_id": self.ctx.target_id, "target_version": self.ctx.target_version,
                   "method": "GET", "path": path,
                   "credential_ref": credential_ref if credential_ref is not None else (
                       self.ctx.account_refs[actor] if actor else None),
                   "request_id": request_id}
        try:
            result = await asyncio.wait_for(self.tools.http_request(request), timeout=remaining)
        except asyncio.TimeoutError as error:
            raise _BudgetStop("timeout") from error
        if not isinstance(result, Mapping) or result.get("request_id") != request_id:
            raise ContextError("HTTP adapter returned an invalid request identity")
        evidence = result.get("evidence_id")
        if _identifier(evidence):
            self.evidence_refs.append(evidence)
        self.observations.append({"request_id": request_id, "path": path, "actor_ref": actor,
                                  "status": _status(result), "evidence_ref": evidence if _identifier(evidence) else None})
        return result

    def add_endpoint(self, path: str, evidence_ref: str | None) -> None:
        if path not in [d["path"] for d in self.discoveries]:
            self.discoveries.append({"method": "GET", "path": path, "service_id": "orders-api",
                                     "evidence_refs": [evidence_ref] if evidence_ref else []})

    async def run(self) -> dict[str, Any]:
        status = "completed"
        try:
            entry = await self.request(self.ctx.entry_path)
            if _status(entry) != 200:
                return self.output("inconclusive")
            listing_paths = [p for p in _links(_body(entry)) if p == "/api/orders"]
            if not listing_paths:
                return self.output("inconclusive")
            self.add_endpoint("/api/orders", entry.get("evidence_id"))
            listing = listing_paths[0]
            owned: dict[str, list[dict[str, str]]] = {}
            for actor in sorted(self.ctx.account_refs):
                result = await self.request(listing, actor)
                owned[actor] = _orders(_body(result)) if _status(result) == 200 else []
                for record in owned[actor]:
                    for key in ("href", "secure_href"):
                        if key in record:
                            template = _template(record[key], record["id"])
                            if template:
                                self.add_endpoint(template, result.get("evidence_id"))
            options: list[TestOption] = []
            for actor in sorted(owned):
                for owner in sorted(owned):
                    if owner == actor:
                        continue
                    for record in owned[owner]:
                        for key in ("href", "secure_href"):
                            if key not in record:
                                continue
                            template = _template(record[key], record["id"])
                            if template:
                                options.append(TestOption(template, record[key], actor,
                                                          "order-" + record["id"], owner, record[key]))
            remaining = tuple(options)
            while remaining:
                decision = await self.provider.choose(remaining)
                if decision is None:
                    break
                if decision not in remaining:
                    raise ContextError("decision provider selected an option outside observed scope")
                remaining = tuple(o for o in remaining if o != decision)
                record_id = decision.resource_ref.removeprefix("order-")
                owner_result = await self.request(decision.owner_path, decision.owner_ref)
                owner_identity = _private_identity(_body(owner_result), record_id) if _status(owner_result) == 200 else None
                if owner_identity is None:
                    continue
                cross_result = await self.request(decision.path, decision.actor_ref)
                cross_identity = _private_identity(_body(cross_result), record_id) if _status(cross_result) == 200 else None
                if cross_identity != owner_identity:
                    continue
                refs = [r for r in (owner_result.get("evidence_id"), cross_result.get("evidence_id")) if _identifier(r)]
                if len(refs) < 2:
                    continue
                candidate = {
                    "id": f"red-candidate-{self.ctx.assessment_id}-{len(self.candidates) + 1}",
                    "status": "candidate", "category": "broken_access_control",
                    "target_id": self.ctx.target_id, "target_version": self.ctx.target_version,
                    "endpoint": decision.endpoint, "policy_id": self.ctx.policy_id,
                    "actor_ref": decision.actor_ref, "resource_ref": decision.resource_ref,
                    "repro": {"method": "GET", "path": decision.path, "actor_ref": decision.actor_ref,
                              "owner_ref": decision.owner_ref, "fresh_session": True,
                              "expected": "denied", "observed": "private_record_returned"},
                    "evidence_refs": refs,
                }
                self.candidates.append(candidate)
                fresh_ref = ((self.ctx.fresh_account_refs or {}).get(decision.actor_ref))
                if fresh_ref is not None:
                    fresh_result = await self.request(decision.path, decision.actor_ref,
                                                      credential_ref=fresh_ref)
                    fresh_status = _status(fresh_result)
                    fresh_identity = (_private_identity(_body(fresh_result), record_id)
                                      if fresh_status == 200 else None)
                    if fresh_identity == owner_identity:
                        outcome = "still_exposed"
                    elif fresh_status in (401, 403):
                        outcome = "blocked"
                    else:
                        outcome = "inconclusive"
                    self.adaptation = {
                        "status": "observed",
                        "credential_ref": fresh_ref,
                        "path": decision.path,
                        "http_status": fresh_status,
                        "outcome": outcome,
                        "evidence_ref": fresh_result.get("evidence_id"),
                    }
                # The first verified-by-evidence candidate ends this bounded
                # access-control pass. Core/referee owns any further coverage.
                break
        except _BudgetStop as stop:
            status = stop.status
        return self.output(status)

    def output(self, status: str) -> dict[str, Any]:
        return {"schema": "range.red.execute/v1", "status": status,
                "assessment_id": self.ctx.assessment_id, "target_id": self.ctx.target_id,
                "target_version": self.ctx.target_version, "data_source": self.ctx.data_source,
                "decision_source": "deterministic" if isinstance(self.provider, DeterministicDecisionProvider) else "external_provider",
                "discoveries": self.discoveries, "candidates": self.candidates,
                "adaptation": self.adaptation,
                "evidence_refs": list(dict.fromkeys(self.evidence_refs)),
                "request_count": self.requests, "step_count": self.steps,
                "summary": f"Observed {len(self.discoveries)} endpoints and proposed {len(self.candidates)} unverified candidate(s)."}


async def execute(context: Mapping[str, Any], tools: Any,
                  decision_provider: DecisionProvider | None = None,
                  decision_policy: DecisionProvider | None = None) -> dict[str, Any]:
    """Run bounded recon and ownership comparison using only a caller's adapter."""
    if decision_provider is not None and decision_policy is not None:
        raise ContextError("provide one decision provider")
    ctx = RedContext.from_input(context)
    if not callable(getattr(tools, "http_request", None)):
        raise ContextError("tools.http_request(request) is required")
    provider = decision_provider or decision_policy or DeterministicDecisionProvider()
    return await _Runner(ctx, tools, provider).run()
