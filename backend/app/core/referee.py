"""Independent candidate replay for the first ownership scenario."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, Protocol


class RefereeTools(Protocol):
    async def http_request(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...

    async def new_session(self, account_ref: str) -> str: ...


def _body(result: Mapping[str, Any]) -> Any:
    body = result.get("body")
    if isinstance(body, Mapping) and isinstance(body.get("order"), Mapping):
        return body["order"]
    return body


def _identity(result: Mapping[str, Any]) -> tuple[str, str] | None:
    body = _body(result)
    if not isinstance(body, Mapping):
        return None
    record_id, canary = body.get("id"), body.get("canary")
    if record_id is None or not isinstance(canary, str) or not canary:
        return None
    return str(record_id), canary


class IndependentReferee:
    """Replays a candidate without trusting its status or evidence claims."""

    async def verify(self, candidate: Mapping[str, Any], tools: RefereeTools) -> dict[str, Any]:
        finding_id = candidate.get("id")
        target_id = candidate.get("target_id")
        target_version = candidate.get("target_version")
        repro = candidate.get("repro")
        actor_ref = candidate.get("actor_ref")
        owner_ref = repro.get("owner_ref") if isinstance(repro, Mapping) else None
        path = repro.get("path") if isinstance(repro, Mapping) else None
        if not all(isinstance(value, str) and value for value in
                   (finding_id, target_id, target_version, actor_ref, owner_ref, path)):
            return self._result(finding_id, "inconclusive", "candidate replay recipe is incomplete")
        try:
            owner_credential = await tools.new_session(owner_ref)
            actor_credential = await tools.new_session(actor_ref)
            owner_result = await tools.http_request({
                "target_id": target_id, "target_version": target_version,
                "method": "GET", "path": path, "credential_ref": owner_credential,
                "request_id": f"referee-{finding_id}-owner",
            })
            baseline = _identity(owner_result)
            if owner_result.get("status") != 200 or baseline is None:
                return self._result(finding_id, "inconclusive", "fresh owner baseline was unavailable")
            actor_result = await tools.http_request({
                "target_id": target_id, "target_version": target_version,
                "method": "GET", "path": path, "credential_ref": actor_credential,
                "request_id": f"referee-{finding_id}-actor",
            })
            if actor_result.get("status") in (401, 403):
                return self._result(finding_id, "rejected", "fresh actor session was denied")
            if actor_result.get("status") == 200 and _identity(actor_result) == baseline:
                return self._result(finding_id, "verified", "fresh sessions reproduced cross-user private access")
            return self._result(finding_id, "rejected", "fresh actor session did not receive the owner record")
        except (asyncio.CancelledError, TimeoutError):
            raise
        except Exception as error:  # adapters must turn operational failures into inconclusive outcomes
            return self._result(finding_id, "inconclusive", f"replay adapter unavailable: {type(error).__name__}")

    @staticmethod
    def _result(finding_id: Any, verdict: str, summary: str) -> dict[str, Any]:
        return {"finding_id": finding_id, "verdict": verdict, "summary": summary,
                "independent": True, "evidence_refs": []}
