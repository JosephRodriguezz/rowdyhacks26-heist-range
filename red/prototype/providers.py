"""Replaceable proposal providers. The optional OpenAI adapter is never enabled implicitly."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol

from .domain import API_BODY_FIELDS, AgentStep, ActionProposal, HypothesisUpdate, Role


class ProviderError(RuntimeError):
    pass


class ProposalProvider(Protocol):
    label: str

    def propose(self, *, role: Role, context: dict[str, Any], system_prompt: str, timeout: float) -> AgentStep:
        """Return one typed step; the caller still validates and executes every action."""


HYPOTHESIS_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "properties": {
        "operation": {"type": "string", "enum": ["create", "assess", "reopen"]},
        "candidate_key": {"type": "string"},
        "statement": {"type": "string"},
        "expected_result": {"type": "string"},
        "evidence_refs": {"type": "array", "items": {"type": "string"}},
        "status": {"type": "string", "enum": ["supported", "rejected", "inconclusive"]},
        "baseline_evidence_ref": {"type": ["string", "null"]},
        "comparison_evidence_ref": {"type": ["string", "null"]},
        "changed_condition": {"type": "string"},
        "assessment": {"type": "string"},
        "expected_revision": {"type": "integer"},
    },
    "required": list(HypothesisUpdate.__dataclass_fields__),
    "additionalProperties": False,
}


STEP_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "red_step",
    "description": "Choose one bounded next step for the Red role. This proposes an action; local policy decides whether it may execute.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["act", "handoff", "update_hypothesis", "blocked", "finished"]},
            "rationale": {"type": "string"},
            "hypothesis": {"type": "string"},
            "candidate_key": {"type": "string"},
            "evidence_refs": {"type": "array", "items": {"type": "string"}},
            "hypothesis_update": HYPOTHESIS_SCHEMA,
            "action": {
                "type": ["object", "null"],
                "properties": {
                    "capability": {"type": "string", "enum": ["read_page", "submit_form", "request_api", "start_account_session", "end_account_session"]},
                    "target_id": {"type": "string", "enum": ["bank-local"]},
                    "path": {"type": "string"},
                    "method": {"type": "string", "enum": ["GET", "POST"]},
                    "identity_ref": {"type": ["string", "null"], "enum": ["account_a", "account_b", None]},
                    "session_ref": {"type": ["string", "null"]},
                    "form_ref": {"type": ["string", "null"], "enum": ["contact_form", None]},
                    "body": {
                        "type": "object",
                        "properties": {name: {"type": ["string", "null"]} for name in API_BODY_FIELDS},
                        "required": list(API_BODY_FIELDS),
                        "additionalProperties": False,
                    },
                },
                "required": ["capability", "target_id", "path", "method", "identity_ref", "session_ref", "form_ref", "body"],
                "additionalProperties": False,
            },
        },
        "required": ["kind", "rationale", "hypothesis", "candidate_key", "evidence_refs", "hypothesis_update", "action"],
        "additionalProperties": False,
    },
}


def parse_step(value: Any) -> AgentStep:
    if not isinstance(value, dict):
        raise ProviderError("provider returned an invalid proposal")
    required = {"kind", "rationale", "hypothesis", "candidate_key", "evidence_refs", "hypothesis_update", "action"}
    if set(value) != required:
        raise ProviderError("provider proposal did not match the typed schema")
    if value["kind"] not in ("act", "handoff", "update_hypothesis", "blocked", "finished"):
        raise ProviderError("provider selected an unknown step kind")
    for name in ("rationale", "hypothesis", "candidate_key"):
        if not isinstance(value[name], str) or len(value[name]) > (160 if name == "candidate_key" else 800):
            raise ProviderError("provider proposal contains invalid text")
    refs = value["evidence_refs"]
    if not isinstance(refs, list) or len(refs) > 12 or any(not isinstance(ref, str) or len(ref) > 80 for ref in refs):
        raise ProviderError("provider evidence references are invalid")
    action = value["action"]
    if action is not None:
        if not isinstance(action, dict):
            raise ProviderError("provider action is not an object")
        props = dict(action)
        body = props.get("body")
        if not isinstance(body, dict):
            raise ProviderError("provider action body is invalid")
        if set(body) - set(API_BODY_FIELDS):
            raise ProviderError("provider action body contains unknown fields")
        props["body"] = {k: v for k, v in body.items() if v is not None}
        for name in ("identity_ref", "session_ref", "form_ref"):
            if props.get(name) is None:
                props.pop(name, None)
        try:
            action_value = ActionProposal.from_mapping(props)
        except ValueError as exc:
            raise ProviderError(str(exc)) from None
    else:
        action_value = None
    try:
        update = HypothesisUpdate.from_mapping(value["hypothesis_update"]) if value["hypothesis_update"] is not None else None
    except ValueError as exc:
        raise ProviderError(str(exc)) from None
    if value["kind"] == "update_hypothesis" and (update is None or action_value is not None):
        raise ProviderError("update_hypothesis requires a structured update and no target action")
    if update is not None and update.operation != "create" and value["kind"] != "update_hypothesis":
        raise ProviderError("assessment and reopening require a board-only step")
    return AgentStep(
        kind=value["kind"], rationale=value["rationale"][:800], hypothesis=value["hypothesis"][:800],
        action=action_value, candidate_key=value["candidate_key"][:160], evidence_refs=tuple(refs),
        hypothesis_update=update,
    )


class OpenAIResponsesProvider:
    """Minimal stdlib Responses API client; sends no requests until explicitly selected."""

    label = "openai_responses"
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model or os.environ.get("OPENAI_MODEL")
        if not self._api_key:
            raise ProviderError("OPENAI_API_KEY is required when remote model mode is explicitly enabled")
        if not self._model:
            raise ProviderError("OPENAI_MODEL must name a model before remote model mode can run")

    def propose(self, *, role: Role, context: dict[str, Any], system_prompt: str, timeout: float) -> AgentStep:
        payload = {
            "model": self._model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps({"role": role, "observations": context}, ensure_ascii=False)},
            ],
            "tools": [STEP_TOOL],
            "tool_choice": {"type": "function", "name": "red_step"},
            "parallel_tool_calls": False,
            "max_output_tokens": 900,
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + self._api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(96_000)
        except urllib.error.HTTPError as exc:
            # Do not include response bodies or provider request metadata in the local report.
            raise ProviderError(f"model provider returned HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"model provider request failed ({type(exc).__name__})") from None
        try:
            decoded = json.loads(raw.decode("utf-8"))
            calls = [item for item in decoded.get("output", []) if item.get("type") == "function_call" and item.get("name") == "red_step"]
            if len(calls) != 1:
                raise ProviderError("model did not return exactly one typed action proposal")
            args = json.loads(calls[0]["arguments"])
            return parse_step(args)
        except (ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError("model response could not be parsed as the typed proposal") from None
