"""Network-level reconnaissance: a separate scope/registry for port-range targets,
distinct from engagement.py's URL-shaped EngagementScope. Web pentesting and network
pentesting are different kinds of boundary (a URL path to exclude vs. a port range to
allow), so this is its own type rather than optional fields bolted onto the other --
see the engagement/network split decided for this phase.

Ownership verification reuses engagement.py's well-known-file HTTP check: proving
control of a host doesn't need a second mechanism just because the thing being
scoped afterward is ports instead of paths. A NetworkTarget's verification_port is
the HTTP port that serves that file -- normally the mock site's own port, since this
prototype only ever tests hosts this team builds and controls.

Scanning is a stdlib-only TCP connect scan (the socket module), never a wrapped
external tool (nmap, etc.) and never a privileged raw-socket SYN scan. A connect
scan needs no special privileges and is the same fundamental technique, just slower
and more visible on the wire -- the right tradeoff for a bounded, authorized
prototype that explicitly chose not to add subprocess/shell execution anywhere.
"""

from __future__ import annotations

import secrets
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from .engagement import EngagementError, verify_ownership

NetworkTargetStatus = Literal["pending_verification", "verified", "revoked"]
PortState = Literal["open", "closed", "filtered", "shed"]


class NetworkScanError(ValueError):
    pass


@dataclass(frozen=True)
class NetworkScope:
    """What a network-pentest capability may do against a verified host -- nothing
    beyond this is implied. Mirrors EngagementScope's hard-ceiling discipline for a
    different kind of boundary: a port range, not a URL path."""

    min_port: int = 1
    max_port: int = 1024
    allowed_protocols: frozenset[str] = frozenset({"tcp"})
    max_ports_per_window: int = 100
    window_seconds: float = 10.0
    max_concurrency: int = 8
    scan_timeout_seconds: float = 0.5

    def __post_init__(self) -> None:
        if not (1 <= self.min_port <= self.max_port <= 65_535):
            raise NetworkScanError("port range must be within 1-65535 with min <= max")
        if self.max_port - self.min_port + 1 > 2_000:
            raise NetworkScanError("declared port range exceeds this prototype's hard limit (2000 ports)")
        if not self.allowed_protocols or (self.allowed_protocols - {"tcp"}):
            raise NetworkScanError("this prototype's scanner only supports tcp")
        if self.max_ports_per_window < 1 or self.max_concurrency < 1:
            raise NetworkScanError("scope ceilings must be positive")
        if self.window_seconds <= 0:
            raise NetworkScanError("scope window must be positive")
        # Mirrors EngagementScope/LoadProfile's own hard-ceiling discipline: a scope
        # that is only numerically smaller than one chosen scan size is not a real
        # boundary.
        if self.max_ports_per_window > 2_000 or self.max_concurrency > 50 or self.window_seconds > 120:
            raise NetworkScanError("scope ceilings exceed this prototype's own hard limit")
        if not (0 < self.scan_timeout_seconds <= 5):
            raise NetworkScanError("scan timeout must be positive and at most 5 seconds")

    def port_in_scope(self, port: int) -> bool:
        return self.min_port <= port <= self.max_port


@dataclass
class NetworkTarget:
    target_id: str
    host: str
    scope: NetworkScope
    verification_port: int = 80
    status: NetworkTargetStatus = "pending_verification"
    verification_token: str = field(default_factory=lambda: secrets.token_hex(16))
    created_at: float = field(default_factory=time.monotonic)
    verified_at: float | None = None

    def __post_init__(self) -> None:
        if not self.target_id.strip() or len(self.target_id) > 80:
            raise NetworkScanError("network target requires a valid target id")
        if not self.host.strip():
            raise NetworkScanError("network target requires a host")
        if not (1 <= self.verification_port <= 65_535):
            raise NetworkScanError("verification_port must be a valid port number")


class NetworkTargetRegistry:
    """Red's own in-memory prototype of a network-scope registry, mirroring
    EngagementRegistry's register -> verify -> resolve discipline: registration alone
    never authorizes a scan; only a verified target does."""

    def __init__(self) -> None:
        self._targets: dict[str, NetworkTarget] = {}

    def register(self, target_id: str, host: str, scope: NetworkScope, *,
                 verification_port: int = 80) -> NetworkTarget:
        if target_id in self._targets:
            raise NetworkScanError(f"target '{target_id}' is already registered")
        target = NetworkTarget(target_id=target_id, host=host, scope=scope, verification_port=verification_port)
        self._targets[target_id] = target
        return target

    def verify(self, target_id: str, *, timeout: float = 2.0) -> NetworkTarget:
        """Re-checkable, not a one-time event -- same posture as EngagementRegistry."""
        target = self._targets.get(target_id)
        if target is None:
            raise NetworkScanError(f"target '{target_id}' is not registered")
        if target.status == "revoked":
            raise NetworkScanError(f"target '{target_id}' has been revoked")
        origin = f"http://{target.host}:{target.verification_port}"
        try:
            verified = verify_ownership(origin, target_id, target.verification_token, timeout=timeout)
        except EngagementError as exc:
            raise NetworkScanError(str(exc)) from exc
        if verified:
            target.status = "verified"
            target.verified_at = time.monotonic()
        else:
            target.status = "pending_verification"
            target.verified_at = None
        return target

    def revoke(self, target_id: str) -> None:
        target = self._targets.get(target_id)
        if target is None:
            raise NetworkScanError(f"target '{target_id}' is not registered")
        target.status = "revoked"

    def resolve(self, target_id: str) -> NetworkTarget:
        target = self._targets.get(target_id)
        if target is None or target.status != "verified":
            raise NetworkScanError(f"target '{target_id}' is not an authorized, verified network target")
        return target

    def targets(self) -> list[NetworkTarget]:
        return list(self._targets.values())


@dataclass(frozen=True)
class PortScanResult:
    port: int
    state: PortState
    banner: str | None = None
    detail: str | None = None  # e.g. why a scan was shed


def _tcp_connect_scan(host: str, port: int, *, timeout: float) -> PortScanResult:
    """One bounded TCP connect attempt. 'open' = the connection actually completed;
    'closed' = the target actively refused it (ECONNREFUSED on most platforms);
    'filtered' = no response either way within the timeout, the same observable
    shape as a firewall silently dropping the packet. This is the raw mechanism;
    NetworkScanExecutor.scan_port is the scope-enforcing, rate-limited entry point
    that should be used instead of calling this directly."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((host, port))
        if result == 0:
            return PortScanResult(port, "open", banner=_try_read_banner(sock))
        return PortScanResult(port, "closed")
    except socket.timeout:
        return PortScanResult(port, "filtered")
    except OSError:
        return PortScanResult(port, "filtered")
    finally:
        sock.close()


def _try_read_banner(sock: socket.socket, *, max_bytes: int = 256) -> str | None:
    try:
        sock.settimeout(0.3)
        data = sock.recv(max_bytes)
    except (socket.timeout, OSError):
        return None
    if not data:
        return None
    return data.decode("utf-8", errors="replace").strip() or None


@dataclass(frozen=True)
class PortProbeResult:
    """A connect-and-send probe, distinct from a plain scan: it sends a payload
    with no credential and reports whatever the service sends back, so a
    vulnerability test can judge whether access was granted. responded=False
    means no usable response came back at all (closed, filtered, or a transport
    failure) -- never treated as a grant."""

    port: int
    responded: bool
    response: str | None = None
    detail: str | None = None  # e.g. why a probe was shed


def _tcp_probe(host: str, port: int, payload: bytes, *, timeout: float) -> tuple[bool, str | None]:
    """Connects, sends payload with no credential of any kind, and reads whatever
    comes back. (False, None) on any connection failure or timeout -- fails closed
    the same way _tcp_connect_scan does; never raises past this function."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        if sock.connect_ex((host, port)) != 0:
            return False, None
        sock.sendall(payload)
        sock.settimeout(timeout)
        data = sock.recv(256)
        if not data:
            return False, None
        return True, data.decode("utf-8", errors="replace").strip() or None
    except (socket.timeout, OSError):
        return False, None
    finally:
        sock.close()


class NetworkScanExecutor:
    """Dispatches bounded, scope-enforcing, rate-limited port scans. Mirrors
    ActionExecutor's own discipline (resolve -> check scope -> admit against the
    ceiling -> dispatch -> record) for a different capability domain, not a
    different set of rules."""

    def __init__(self, *, registry: NetworkTargetRegistry, board: Any | None = None) -> None:
        self.registry = registry
        self.board = board
        self._lock = threading.Lock()
        self._request_times: dict[str, list[float]] = {}
        self._concurrency: dict[str, int] = {}

    def _admit(self, target_id: str, scope: NetworkScope) -> str | None:
        now = time.monotonic()
        with self._lock:
            recent = self._request_times.setdefault(target_id, [])
            cutoff = now - scope.window_seconds
            recent[:] = [t for t in recent if t > cutoff]
            if len(recent) >= scope.max_ports_per_window:
                return (f"network scope rate limit exceeded: {scope.max_ports_per_window} "
                        f"ports per {scope.window_seconds}s window")
            if self._concurrency.get(target_id, 0) >= scope.max_concurrency:
                return f"network scope concurrency limit exceeded: {scope.max_concurrency} in flight"
            recent.append(now)
            self._concurrency[target_id] = self._concurrency.get(target_id, 0) + 1
            return None

    def _release(self, target_id: str) -> None:
        with self._lock:
            current = self._concurrency.get(target_id, 0)
            if current > 0:
                self._concurrency[target_id] = current - 1

    def scan_port(self, target_id: str, port: int) -> PortScanResult:
        target = self.registry.resolve(target_id)  # raises NetworkScanError if unregistered/unverified
        if not target.scope.port_in_scope(port):
            raise NetworkScanError("port is outside this target's authorized scope")
        shed_reason = self._admit(target_id, target.scope)
        if shed_reason is not None:
            result = PortScanResult(port, "shed", detail=shed_reason)
            self._record(target_id, result)
            return result
        try:
            result = _tcp_connect_scan(target.host, port, timeout=target.scope.scan_timeout_seconds)
        finally:
            self._release(target_id)
        self._record(target_id, result)
        return result

    def scan_ports(
        self, target_id: str, ports: list[int], *, max_retry_wait_seconds: float = 30.0,
    ) -> list[PortScanResult]:
        """Scans every declared port, pacing to the scope's own rate window rather
        than reporting a partial range as if it were complete: a port shed by the
        rate ceiling is retried after waiting out that same window, not abandoned,
        so a scan of a wide range at a tight ceiling genuinely covers the whole
        range (slower, correctly) instead of silently only covering however many
        ports fit in the first window. Bounded by max_retry_wait_seconds of total
        wait per port, so a misbehaving or permanently exhausted ceiling cannot
        hang forever; a port still shed once that bound is reached keeps its
        honest 'shed' result rather than claiming a scan that never happened."""
        window_seconds: float | None = None
        results: list[PortScanResult] = []
        for port in ports:
            result = self.scan_port(target_id, port)
            waited = 0.0
            while result.state == "shed" and waited < max_retry_wait_seconds:
                if window_seconds is None:
                    window_seconds = self.registry.resolve(target_id).scope.window_seconds
                sleep_for = min(window_seconds, max_retry_wait_seconds - waited)
                time.sleep(sleep_for)
                waited += sleep_for
                result = self.scan_port(target_id, port)
            results.append(result)
        return results

    def probe_unauthenticated_access(
        self, target_id: str, port: int, *, payload: bytes = b"PROBE\r\n",
    ) -> PortProbeResult:
        """Same resolve -> check scope -> admit -> dispatch -> record discipline as
        scan_port, for a different mechanism: connects and sends payload with no
        credential, then reports whatever came back so a vulnerability test can
        judge it. Never itself decides vulnerable/not -- that judgment belongs to
        vulnerability.py, which knows what response shape counts as a grant."""
        target = self.registry.resolve(target_id)  # raises NetworkScanError if unregistered/unverified
        if not target.scope.port_in_scope(port):
            raise NetworkScanError("port is outside this target's authorized scope")
        shed_reason = self._admit(target_id, target.scope)
        if shed_reason is not None:
            result = PortProbeResult(port, responded=False, detail=shed_reason)
            self._record_probe(target_id, result)
            return result
        try:
            responded, response = _tcp_probe(target.host, port, payload, timeout=target.scope.scan_timeout_seconds)
        finally:
            self._release(target_id)
        result = PortProbeResult(port, responded=responded, response=response)
        self._record_probe(target_id, result)
        return result

    def _record(self, target_id: str, result: PortScanResult) -> None:
        if self.board is None:
            return
        self.board.record_event("network.port_scanned", {
            "target_id": target_id, "port": result.port, "state": result.state,
            "banner": (result.banner or "")[:256], "detail": result.detail,
        })

    def _record_probe(self, target_id: str, result: PortProbeResult) -> None:
        if self.board is None:
            return
        self.board.record_event("network.port_probed", {
            "target_id": target_id, "port": result.port, "responded": result.responded,
            "response": (result.response or "")[:256], "detail": result.detail,
        })
