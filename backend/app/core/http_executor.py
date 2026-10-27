"""Bounded, credential-reference-only HTTP execution for registered lab targets."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPSConnection
import json
import time
from typing import Any, Mapping
from urllib.parse import urlsplit
from uuid import uuid4

from .registry import TargetRegistry, TargetScopeError


class ToolInputError(ValueError):
    """Raised when a tool request cannot be safely executed."""


@dataclass
class RequestBudget:
    max_requests: int = 32
    timeout_seconds: float = 5.0
    requests_used: int = 0

    def reserve(self) -> None:
        if type(self.max_requests) is not int or self.max_requests < 0:
            raise ToolInputError("max_requests must be a nonnegative integer")
        if type(self.timeout_seconds) not in (int, float) or self.timeout_seconds <= 0:
            raise ToolInputError("timeout_seconds must be positive")
        if self.requests_used >= self.max_requests:
            raise ToolInputError("request budget exhausted")
        self.requests_used += 1


class BoundedHttpExecutor:
    """Core-owned adapter used by red and the referee.

    The adapter stores raw tokens only in memory and never returns them in a
    result. It uses `http.client`, which does not follow redirects; a redirect
    response is therefore returned as an ordinary bounded result.
    """

    def __init__(self, registry: TargetRegistry, credentials: Mapping[str, str],
                 budget: RequestBudget | None = None):
        self.registry = registry
        # Keep the core-owned vault live: trusted orchestration may provision a
        # fresh session reference after containment without exposing its token
        # to the agent or rebuilding the executor.
        self._credentials = credentials
        self.budget = budget or RequestBudget()

    async def http_request(self, request: Mapping[str, Any]) -> dict[str, Any]:
        request_id = request.get("request_id") if isinstance(request, Mapping) else None
        if not isinstance(request_id, str) or not request_id:
            request_id = f"core-{uuid4()}"
        try:
            self.budget.reserve()
            method = request.get("method")
            if method != "GET":
                raise ToolInputError("only GET is enabled for this first slice")
            target, path = self.registry.resolve_path(
                request.get("target_id"), request.get("target_version"), request.get("path"))
            credential_ref = request.get("credential_ref")
            token = None
            if credential_ref is not None:
                if not isinstance(credential_ref, str) or credential_ref not in self._credentials:
                    raise ToolInputError("unknown credential reference")
                token = self._credentials[credential_ref]
            result = await asyncio.wait_for(
                asyncio.to_thread(self._request_sync, target.origin, path, token, request_id),
                timeout=self.budget.timeout_seconds,
            )
            return result
        except (ToolInputError, TargetScopeError) as error:
            return {"request_id": request_id, "status": None,
                    "body": None, "error": {"code": "rejected", "message": str(error)},
                    "evidence_id": f"evidence-{request_id}"}
        except asyncio.TimeoutError:
            return {"request_id": request_id, "status": None,
                    "body": None, "error": {"code": "timeout", "message": "request timed out"},
                    "evidence_id": f"evidence-{request_id}"}
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return {"request_id": request_id, "status": None,
                    "body": None, "error": {"code": "transport", "message": type(error).__name__},
                    "evidence_id": f"evidence-{request_id}"}

    def _request_sync(self, origin: str, path: str, token: str | None,
                      request_id: str) -> dict[str, Any]:
        parsed = urlsplit(origin)
        connection_type = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
        connection = connection_type(parsed.hostname, parsed.port, timeout=self.budget.timeout_seconds)
        headers = {"X-Request-ID": request_id, "Accept": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        started = time.monotonic()
        try:
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            try:
                body = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = {"error": {"code": "invalid_json", "message": "target returned non-JSON"}}
            return {"request_id": request_id, "status": response.status, "body": body,
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
                    "evidence_id": f"evidence-{request_id}"}
        finally:
            connection.close()
