"""Trusted lab adapter, NOT an agent or a network/firewall configuration tool.

Real token-bucket enforcement and bounded target-side telemetry. A WSGI adapter
is supplied for a Python bank; other stacks must implement equivalent admission
and trusted source resolution. No artificial outage switch or low-capacity demo
bottleneck. Middleware never exposes runtime policy operations over HTTP.
"""
from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
from http.cookies import SimpleCookie, CookieError
import math
import secrets
import threading
import time

from .availability import (SCOPE_KEYS, identifier, number, _observe_availability, parse_policy, require)


@dataclass
class _Request:
    source_ref: str
    started: float
    admitted: bool
    status: int | None = None
    elapsed_ms: float | None = None
    sequence: int = 0
    defense_id: str | None = None


@dataclass
class _Bucket:
    rate: float
    burst: int
    tokens: float
    updated: float
    expires: float
    defense_id: str
    min_verification_rps: float


class TrafficGuard:
    cookie_name = "heist_lab_client"

    def __init__(self, assessment_id, target_id, target_version, *, data_source="live", clock=time.monotonic,
                 max_records=4096, max_clients=128, max_inflight=64):
        require(all(identifier(v) for v in (assessment_id, target_id, target_version)))
        require(type(data_source) is str and data_source in {"live", "fixture", "recorded"})
        require(type(max_records) is int and 16 <= max_records <= 10000)
        require(type(max_clients) is int and 2 <= max_clients <= 256)
        require(type(max_inflight) is int and 1 <= max_inflight <= 256)
        self.scope = dict(zip(SCOPE_KEYS, (assessment_id, target_id, target_version, data_source)))
        self.clock, self.lock = clock, threading.RLock()
        self.max_clients, self.max_inflight = max_clients, max_inflight
        self._records = deque(maxlen=max_records)
        self._dropped_until = -math.inf
        self._clients, self._buckets, self._active, self._windows = {}, {}, {}, {}
        self._salt = secrets.token_bytes(32)
        self._sequence, self.revision, self.closed = 0, 0, False
        self._request_sequence = 0

    def register_client(self, source_ref):
        """Core-only identity binding. Return secret cookie material privately.

        Ordinary and attacking clients use the SAME admission policy. Tokens
        identify a client; they never whitelist it or bypass rate limits.
        Browser bootstrap/session binding belongs to the trusted bank adapter.
        """
        require(identifier(source_ref))
        with self.lock:
            require(not self.closed and len(self._clients) < self.max_clients, "Client registry unavailable")
            require(source_ref not in self._clients.values(), "Client reference already registered")
            token = secrets.token_urlsafe(32)
            self._clients[token] = source_ref
            return token

    def source_for(self, environ):
        # Ignore caller-supplied IP/source-reference headers. A trusted opaque
        # lab cookie or the actual socket peer is the only identity input.
        cookie = environ.get("HTTP_COOKIE", "")
        token = None
        if type(cookie) is str and len(cookie) <= 4096:
            try:
                values = SimpleCookie(cookie)
                if self.cookie_name in values:
                    token = values[self.cookie_name].value
            except CookieError:
                pass
        with self.lock:
            if token in self._clients:
                return self._clients[token]
        peer = environ.get("REMOTE_ADDR", "unknown")
        if not isinstance(peer, str) or len(peer) > 128:
            peer = "unknown"
        return "peer-" + hashlib.sha256(self._salt + peer.encode()).hexdigest()[:20]

    def _expire(self, now):
        for ref in list(self._buckets):
            if now >= self._buckets[ref].expires:
                del self._buckets[ref]

    def begin(self, source_ref, *, _unregistered=False):
        require(identifier(source_ref))
        require(type(_unregistered) is bool)
        with self.lock:
            now = self.clock()
            self._expire(now)
            status = 503 if self.closed else (401 if _unregistered else None)
            bucket = self._buckets.get(source_ref)
            if status is None and bucket:
                bucket.tokens = min(bucket.burst, bucket.tokens + max(0, now - bucket.updated) * bucket.rate)
                bucket.updated = now
                if bucket.tokens < 1:
                    status = 429
                else:
                    bucket.tokens -= 1
            if status is None and len(self._active) >= self.max_inflight:
                status = 503
            self._request_sequence += 1
            record = _Request(source_ref, now, status is None, status, sequence=self._request_sequence,
                              defense_id=bucket.defense_id if bucket and status == 429 else None)
            if len(self._records) == self._records.maxlen:
                self._dropped_until = self._records[0].started
            self._records.append(record)
            handle = secrets.token_hex(16)
            if status is None:
                self._active[handle] = record
            return handle, status

    def admit(self, environ):
        """Public bank admission requires an issued, stable lab client token.

        A missing/invalid token cannot open an unlimited alternate peer bucket.
        The hashed peer remains only a safe attribution for refused attempts.
        Trusted bootstrap must bind ordinary browsers before serving the bank.
        """
        with self.lock:
            source = self.source_for(environ)
            return self.begin(source, _unregistered=source not in self._clients.values())

    def finish(self, handle, status):
        require(type(status) is int and 100 <= status <= 599, "Invalid target response status")
        require(identifier(handle), "Invalid target request handle")
        with self.lock:
            record = self._active.pop(handle, None)
            if record is None or self.closed:
                return False
            record.status = status
            record.elapsed_ms = max(0, self.clock() - record.started) * 1000
            return True

    def sample(self, policy, *, seconds=2.0):
        policy = parse_policy(policy)
        require(number(seconds, .1, 300))
        with self.lock:
            require(not self.closed, "Target guard closed")
            now = self.clock()
            self._expire(now)
            records = [r for r in self._records if now - seconds <= r.started <= now]
            refs = {r.source_ref for r in records} | {r.source_ref for r in self._active.values()}
            lost = self._dropped_until >= now - seconds or len(refs) > 256
            # Too many sources produce an explicitly incomplete window, never
            # an unbounded context or permission to block unobserved clients.
            refs = sorted(refs)[:256]
            rows = []
            for ref in refs:
                own = [r for r in records if r.source_ref == ref]
                rows.append({"source_ref": ref, "requests": len(own),
                    "backend_requests": sum(r.admitted for r in own),
                    "server_errors": sum(r.admitted and r.status is not None and r.status >= 500 for r in own),
                    "denied_requests": sum(not r.admitted for r in own),
                    "inflight": sum(r.source_ref == ref for r in self._active.values())})
            latencies = sorted(r.elapsed_ms for r in records if r.elapsed_ms is not None)
            self._sequence += 1
            window = {"window_id": "window-" + str(self._sequence), "seconds": seconds, "sources": rows,
                      "latency_p95_ms": latencies[math.ceil(.95 * len(latencies)) - 1] if latencies else None,
                      "data_loss": lost}
            for field in ("requests", "backend_requests", "server_errors", "denied_requests", "inflight"):
                window[field] = sum(row[field] for row in rows)
            context = {**self.scope, "window": window, "policy": asdict(policy),
                       "active_source_refs": sorted(self._buckets), "budgets": {"max_steps": 5, "timeout_seconds": 10}}
            if len(self._windows) >= 32:
                del self._windows[next(iter(self._windows))]
            self._windows[window["window_id"]] = (deepcopy(context), now)
            return deepcopy(context)

    def evidence(self, window_id, *, max_age=10):
        require(identifier(window_id) and number(max_age, 0, 10), "Invalid availability evidence handle or age")
        with self.lock:
            require(not self.closed and window_id in self._windows, "Unknown or stale availability evidence")
            require(window_id == next(reversed(self._windows)), "Newer availability evidence requires a fresh comparison")
            context, when = self._windows[window_id]
            require(0 <= self.clock() - when <= max_age, "Unknown or stale availability evidence")
            result = deepcopy(context)
            self._expire(self.clock())
            result["active_source_refs"] = sorted(self._buckets)
            return result

    def _install(self, proposal, *, min_verification_rps=0):
        parameters = proposal["parameters"]
        now = self.clock()
        self._buckets[parameters["source_ref"]] = _Bucket(parameters["rate_per_second"], parameters["burst"],
            float(parameters["burst"]), now, now + parameters["ttl_seconds"], proposal["defense_id"], min_verification_rps)
        self.revision += 1

    def rollback(self, defense_id):
        """Trusted adapter operation; never exposed as a bank route."""
        with self.lock:
            require(not self.closed, "Target guard closed")
            found = [ref for ref, bucket in self._buckets.items() if bucket.defense_id == defense_id]
            for ref in found:
                del self._buckets[ref]
            if found:
                self.revision += 1
            return bool(found)

    def close(self):
        with self.lock:
            self.closed = True
            self._clients.clear()
            self._active.clear()
            self._buckets.clear()
            self._windows.clear()

    def middleware(self, application):
        """WSGI bank instrumentation. Bodies, cookies, paths and headers are not logged."""
        def protected(environ, start_response):
            handle, refusal = self.admit(environ)
            if refusal is not None:
                reason = {401: "Unauthorized", 429: "Too Many Requests", 503: "Service Unavailable"}[refusal]
                start_response(f"{refusal} {reason}",
                    [("Content-Type", "text/plain"), ("Cache-Control", "no-store"), ("Retry-After", "1")])
                return [b"Lab traffic protection refused this request.\n"]
            status = 500
            response = None
            def observed_start(value, headers, exc_info=None):
                nonlocal status
                status = int(value.split(" ", 1)[0])
                return start_response(value, headers, exc_info)
            def stream():
                nonlocal response, status
                try:
                    response = application(environ, observed_start)
                    yield from response
                except BaseException:
                    status = 500
                    raise
                finally:
                    try:
                        if response is not None and hasattr(response, "close"):
                            response.close()
                    except BaseException:
                        status = 500
                        raise
                    finally:
                        self.finish(handle, status)
            generator = stream()
            guard = self
            class Response:
                def __iter__(self): return self
                def __next__(self): return next(generator)
                def close(self):
                    try:
                        generator.close()
                    finally:
                        # Closing a never-started generator does not execute its
                        # finally block. Release that admitted request too.
                        guard.finish(handle, status)
            return Response()
        return protected


class ScopedAvailabilityExecutor:
    """Core-side bounded adapter: approve proposals, then apply by ID only.

    Agent code cannot supply destinations, raw rules, commands, new thresholds,
    or fabricated evidence. Approval re-derives the proposal from the guard's
    canonical measurement using core's reviewed policy. No HTTP admin endpoint.
    Parent core must enforce dispatch pause and persist returned ordered events.
    """
    def __init__(self, guard, policy, *, max_actions=16, timeout_seconds=120, cancelled=lambda: False):
        require(type(max_actions) is int and 1 <= max_actions <= 64)
        require(number(timeout_seconds, 1, 300))
        self.guard, self.policy = guard, parse_policy(policy)
        self.cancelled = cancelled
        self.deadline = guard.clock() + timeout_seconds
        self.max_actions, self.actions_used = max_actions, 0
        self._approved, self._results, self._rollbacks = {}, {}, {}
        self._lock, self.stopped = threading.RLock(), False

    def _check(self):
        require(not self.stopped and not self.cancelled() and self.guard.clock() < self.deadline,
                "Availability execution stopped or expired")
        require(not self.guard.closed, "Target guard closed")

    async def approve(self, proposal):
        require(type(proposal) is dict and identifier(proposal.get("defense_id")), "Invalid availability proposal")
        with self._lock, self.guard.lock:
            self._check()
            require(all(proposal.get(k) == self.guard.scope[k] for k in SCOPE_KEYS), "Availability scope mismatch")
            require(identifier(proposal.get("window_id")), "Invalid availability evidence")
            canonical = self.guard.evidence(proposal["window_id"])
            canonical["policy"] = asdict(self.policy)
            result = _observe_availability(canonical)
            require(proposal in result["defense_proposals"], "Proposal lacks current canonical availability evidence")
            require(len(self._approved) < self.max_actions or proposal["defense_id"] in self._approved,
                    "Availability approval budget exhausted")
            self._approved[proposal["defense_id"]] = deepcopy(proposal)
            return proposal["defense_id"]

    def apply(self, defense_id):
        require(identifier(defense_id))
        with self._lock, self.guard.lock:
            self._check()
            if defense_id in self._results:
                return deepcopy(self._results[defense_id])
            require(defense_id in self._approved, "Unapproved availability defense")
            require(self.actions_used < self.max_actions, "Availability action budget exhausted")
            proposal = self._approved[defense_id]
            canonical = self.guard.evidence(proposal["window_id"])
            canonical["policy"] = asdict(self.policy)
            require(proposal in _observe_availability(canonical)["defense_proposals"],
                    "Proposal lacks current canonical availability evidence")
            # Check and policy installation are atomic with stop/reset and
            # target request admission; no post-stop policy writes.
            self._check()
            original = self.guard.revision
            self.guard._install(proposal, min_verification_rps=self.policy.suspect_source_rps)
            self.actions_used += 1
            result = {"schema": "range.availability.action/v1", **self.guard.scope,
                "type": "availability.defense.applied", "evidence_refs": proposal["evidence_refs"],
                "data": {"defense_id": defense_id, "action_type": "limit_http_source", "origin": "policy_action",
                         "original_policy_revision": original, "policy_revision": self.guard.revision,
                         "effect": "containment", "recovery_verified": False,
                         "expires_after_seconds": proposal["parameters"]["ttl_seconds"]}}
            self._results[defense_id] = result
            return deepcopy(result)

    def rollback(self, defense_id):
        require(identifier(defense_id))
        with self._lock, self.guard.lock:
            # Trusted safety cleanup remains available after stop/deadline or
            # exhausted apply quota. Each applied ID has one rollback receipt.
            # Reset/close still invalidates all handles.
            require(not self.guard.closed, "Target guard closed")
            require(defense_id in self._results, "Unknown availability defense")
            if defense_id in self._rollbacks:
                return deepcopy(self._rollbacks[defense_id])
            changed = self.guard.rollback(defense_id)
            result = {"schema": "range.availability.action/v1", **self.guard.scope,
                    "type": "availability.defense.rolled_back", "evidence_refs": [],
                    "data": {"defense_id": defense_id, "changed": changed, "policy_revision": self.guard.revision}}
            self._rollbacks[defense_id] = result
            return deepcopy(result)

    def stop(self):
        with self._lock:
            self.stopped = True
