"""Target authorization and scope: who may be tested, how, and within what bounds.

This models the thing every registered target needs before Red can touch it: proof of
ownership/control, an explicit scope (which capabilities are allowed, which paths are
off-limits), and bounded rules of engagement (rate/concurrency ceilings, mirroring
LoadProfile's own hard-ceiling discipline). It replaces "the target is 127.0.0.1" as
the safety boundary with the thing that actually has to hold once a target can be
anything: real, verified proof of control.

Scope: this is Red's own working prototype of a concept that -- once proven -- belongs
in shared, core-owned infrastructure (see docs/red/CORE_DISPATCH_MAPPING.md for the
same reasoning applied to dispatch). Nothing here is wired into ActionExecutor's live
dispatch path yet; that integration is deliberately the next phase, not this one.

Every engagement this prototype can create is for a test site this team builds and
controls (see mocksite.py) -- proven by actually fetching a well-known file from it,
never by an unverified claim. This prototype has no path that points at, or could be
pointed at, a real third party's site: verify() only ever performs a real HTTP GET to
an origin this process was explicitly given, nothing is auto-discovered or guessed.
"""

from __future__ import annotations

import http.client
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit

EngagementStatus = Literal["pending_verification", "verified", "revoked"]

# Same shape as the ACME HTTP-01 / Google Search Console HTML-file pattern: the
# registrant proves control by placing a specific value somewhere only the real
# controller of the origin could put it, and we fetch it ourselves rather than trust
# a claim.
WELL_KNOWN_PATH = "/.well-known/heist-range-authorization.json"


class EngagementError(ValueError):
    pass


def _parse_bare_origin(origin: str) -> tuple[str, str, int]:
    parsed = urlsplit(origin)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.path or parsed.query or parsed.fragment:
        raise EngagementError("origin must be a bare http(s) origin, no path, query, or fragment")
    if parsed.port is None:
        raise EngagementError("origin must include its port explicitly")
    return parsed.scheme, parsed.hostname, parsed.port


@dataclass(frozen=True)
class EngagementScope:
    """What Red may do against a verified target -- nothing beyond this is implied."""

    allowed_capabilities: frozenset[str]
    excluded_paths: tuple[str, ...] = ()
    max_requests_per_window: int = 60
    window_seconds: float = 10.0
    max_concurrency: int = 12

    def __post_init__(self) -> None:
        if not self.allowed_capabilities:
            raise EngagementError("scope requires at least one allowed capability")
        if self.max_requests_per_window < 1 or self.max_concurrency < 1:
            raise EngagementError("scope ceilings must be positive")
        if self.window_seconds <= 0:
            raise EngagementError("scope window must be positive")
        # Mirrors LoadProfile's own hard-ceiling discipline: a scope that is only
        # numerically smaller than one chosen attack size is not a real boundary.
        if self.max_requests_per_window > 600 or self.max_concurrency > 50 or self.window_seconds > 120:
            raise EngagementError("scope ceilings exceed this prototype's own hard limit")

    def path_excluded(self, path: str) -> bool:
        normalized = path.split("?", 1)[0]
        return any(
            normalized == excluded or normalized.startswith(excluded.rstrip("/") + "/")
            for excluded in self.excluded_paths
        )


@dataclass
class TargetEngagement:
    target_id: str
    origin: str
    scope: EngagementScope
    status: EngagementStatus = "pending_verification"
    verification_token: str = field(default_factory=lambda: secrets.token_hex(16))
    created_at: float = field(default_factory=time.monotonic)
    verified_at: float | None = None

    def __post_init__(self) -> None:
        if not self.target_id.strip() or len(self.target_id) > 80:
            raise EngagementError("engagement requires a valid target id")
        _parse_bare_origin(self.origin)  # validated for its side effect: raises if malformed


def verify_ownership(origin: str, target_id: str, expected_token: str, *, timeout: float = 2.0) -> bool:
    """Fetch the well-known file over real HTTP and confirm it carries this exact
    engagement's token. This is the actual proof of control -- never a claim, never
    skipped, never inferred from anything other than one successful, matching fetch.
    Any transport failure, non-200, or malformed/missing token is simply "not verified",
    never raised -- the same fail-closed posture as the rest of this project."""
    scheme, hostname, port = _parse_bare_origin(origin)
    conn_cls = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(hostname, port, timeout=timeout)
    try:
        conn.request("GET", WELL_KNOWN_PATH, headers={"Accept": "application/json"})
        response = conn.getresponse()
        if response.status != 200:
            return False
        raw = response.read(8_192)
    except (OSError, http.client.HTTPException, TimeoutError):
        return False
    finally:
        conn.close()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    tokens = payload.get("tokens") if isinstance(payload, dict) else None
    if not isinstance(tokens, dict):
        return False
    return tokens.get(target_id) == expected_token


class EngagementRegistry:
    """Red's own in-memory prototype of what a shared, core-owned registry should
    enforce before this can safely point at anything beyond a prototype's own mock
    sites: registration alone is never enough to resolve a target. Verification,
    performed by this process over real HTTP, is the only thing that is."""

    def __init__(self) -> None:
        self._engagements: dict[str, TargetEngagement] = {}

    def register(self, target_id: str, origin: str, scope: EngagementScope) -> TargetEngagement:
        if target_id in self._engagements:
            raise EngagementError(f"target '{target_id}' is already registered")
        engagement = TargetEngagement(target_id=target_id, origin=origin, scope=scope)
        self._engagements[target_id] = engagement
        return engagement

    def verify(self, target_id: str, *, timeout: float = 2.0) -> TargetEngagement:
        """Re-checkable, not a one-time event: a target that stops passing verification
        (the well-known file is removed or changed) falls back to pending_verification
        the next time this is called, rather than staying verified from stale state."""
        engagement = self._engagements.get(target_id)
        if engagement is None:
            raise EngagementError(f"target '{target_id}' is not registered")
        if engagement.status == "revoked":
            raise EngagementError(f"target '{target_id}' has been revoked")
        if verify_ownership(engagement.origin, target_id, engagement.verification_token, timeout=timeout):
            engagement.status = "verified"
            engagement.verified_at = time.monotonic()
        else:
            engagement.status = "pending_verification"
            engagement.verified_at = None
        return engagement

    def revoke(self, target_id: str) -> None:
        engagement = self._engagements.get(target_id)
        if engagement is None:
            raise EngagementError(f"target '{target_id}' is not registered")
        engagement.status = "revoked"

    def resolve(self, target_id: str) -> TargetEngagement:
        """Only ever returns a usable engagement for a currently verified target --
        mirrors FixedTargetRegistry.resolve's "unregistered -> rejected" contract, plus
        the new "registered but not (yet, or no longer) verified -> still rejected"
        state. There is deliberately no path that returns an engagement by origin or by
        any means other than an exact, verified target_id."""
        engagement = self._engagements.get(target_id)
        if engagement is None or engagement.status != "verified":
            raise EngagementError(f"target '{target_id}' is not an authorized, verified engagement")
        return engagement

    def capability_allowed(self, target_id: str, capability: str, path: str = "/") -> bool:
        """Convenience check combining resolve() with the engagement's own scope. This
        does not yet enforce the rate/concurrency ceilings -- that requires a live
        dispatch path to count against, which does not exist for this registry yet."""
        engagement = self.resolve(target_id)
        if capability not in engagement.scope.allowed_capabilities:
            return False
        return not engagement.scope.path_excluded(path)

    def engagements(self) -> list[TargetEngagement]:
        return list(self._engagements.values())
