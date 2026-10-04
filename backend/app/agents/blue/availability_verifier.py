"""Independent referee integration, never called by Blue observe().

Probe real ordinary routes against one core-registered loopback target. Compare
status AND expected content to a healthy baseline, bound latency, and corroborate
continuing traffic and policy refusals from target-side records. A timeout,
failed login, absent baseline, stopped load, or missing evidence is inconclusive.
This module does not certify general Internet DDoS resilience or patch a flaw.
"""
import hashlib
from copy import deepcopy
import http.client
import ipaddress
import socket
import threading
import time
from urllib.parse import unquote

from .availability import identifier, number, require


class BankTargetRegistry:
    """Fixed trusted configuration, never populated from agent or HTTP input."""
    def __init__(self, targets):
        require(type(targets) is dict and 1 <= len(targets) <= 16)
        self._targets = {}
        for target_id, config in targets.items():
            require(identifier(target_id) and type(config) is dict and
                    set(config) == {"target_version", "host", "port", "routes"})
            require(identifier(config["target_version"]))
            try:
                address = ipaddress.ip_address(config["host"])
            except (ValueError, TypeError):
                raise ValueError("Probe origin must be a registered loopback address") from None
            require(address.is_loopback and type(config["host"]) is str and
                    type(config["port"]) is int and 1 <= config["port"] <= 65535)
            routes = config["routes"]
            require(type(routes) is dict and 1 <= len(routes) <= 4)
            copied = {}
            for ref, route in routes.items():
                require(identifier(ref) and type(route) is dict and set(route) == {"path", "expected_body"})
                path, expected = route["path"], route["expected_body"]
                require(type(path) is str and len(path) <= 1024 and path.isascii())
                decoded = unquote(path)
                require(decoded.startswith("/") and not decoded.startswith("//") and "\\" not in decoded
                        and ".." not in decoded and "?" not in decoded and "#" not in decoded
                        and not any(ord(c) < 32 or ord(c) == 127 for c in decoded))
                require(type(expected) is bytes and 1 <= len(expected) <= 65536)
                copied[ref] = dict(route)
            self._targets[target_id] = {**config, "routes": copied}

    def probe(self, target_id, route_ref, **private_options):
        return OrdinaryHTTPProbe(self, target_id, route_ref, **private_options)


class OrdinaryHTTPProbe:
    def __init__(self, registry, target_id, route_ref, *, private_cookie=None, timeout=.5, max_bytes=16384):
        require(isinstance(registry, BankTargetRegistry) and identifier(target_id) and identifier(route_ref))
        require(target_id in registry._targets, "Unknown registered bank target")
        config = registry._targets[target_id]
        require(route_ref in config["routes"], "Unknown ordinary bank route")
        route = config["routes"][route_ref]
        require(number(timeout, .05, 2) and type(max_bytes) is int and 1 <= max_bytes <= 65536)
        require(len(route["expected_body"]) <= max_bytes)
        require(private_cookie is None or (type(private_cookie) is str and len(private_cookie) <= 4096 and
                                          all(32 <= ord(c) < 127 for c in private_cookie)))
        self.target_id, self.target_version = target_id, config["target_version"]
        self.host, self.port, self.path = config["host"], config["port"], route["path"]
        self._expected_digest = hashlib.sha256(route["expected_body"]).digest()
        self._cookie = private_cookie
        self.timeout, self.max_bytes = timeout, max_bytes

    def __call__(self):
        start = time.monotonic()
        connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        timer = None
        try:
            connection.connect()
            remaining = self.timeout - (time.monotonic() - start)
            if remaining <= 0:
                raise TimeoutError
            # Socket inactivity timeout alone is not a total deadline: a slow
            # header/body sender could extend it forever. Abort the exact
            # connected socket at this probe's absolute wall-clock deadline.
            peer = connection.sock
            def abort():
                try:
                    peer.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            timer = threading.Timer(remaining, abort)
            timer.daemon = True
            timer.start()
            headers = {"Cache-Control": "no-cache"}
            if self._cookie is not None:
                headers["Cookie"] = self._cookie
            connection.request("GET", self.path, headers=headers)
            response = connection.getresponse()
            body = response.read(self.max_bytes + 1)
            completed = time.monotonic() - start < self.timeout
            matched = completed and len(body) <= self.max_bytes and hashlib.sha256(body).digest() == self._expected_digest
            return {"http_status": response.status, "content_matches": matched,
                    "latency_ms": (time.monotonic() - start) * 1000, "transport_ok": completed}
        except (OSError, http.client.HTTPException):
            return {"http_status": None, "content_matches": False,
                    "latency_ms": (time.monotonic() - start) * 1000, "transport_ok": False}
        finally:
            if timer is not None:
                timer.cancel()
            connection.close()


class IndependentRecoveryVerifier:
    def __init__(self, guard, ordinary_probes, *, latency_limit_ms=500, samples=5, interval_seconds=.1,
                 timeout_seconds=5, cancelled=lambda: False):
        require(type(ordinary_probes) in (list, tuple) and 1 <= len(ordinary_probes) <= 4)
        require(all(isinstance(p, OrdinaryHTTPProbe) and p.target_id == guard.scope["target_id"] and
                    p.target_version == guard.scope["target_version"] for p in ordinary_probes))
        with guard.lock:
            self._probe_sources = {}
            for probe in ordinary_probes:
                source = guard.source_for({"HTTP_COOKIE": probe._cookie, "REMOTE_ADDR": probe.host})
                require(source in guard._clients.values(), "Ordinary referee clients must be privately registered")
                self._probe_sources[probe] = source
        require(number(latency_limit_ms, 1, 5000) and type(samples) is int and 3 <= samples <= 20)
        require(number(interval_seconds, .05, 1) and number(timeout_seconds, 1, 30))
        self.guard, self.probes = guard, tuple(ordinary_probes)
        self.latency_limit_ms, self.samples = latency_limit_ms, samples
        self.interval, self.timeout, self.cancelled = interval_seconds, timeout_seconds, cancelled
        self._baseline = None
        self._baseline_when = None
        self._baseline_valid = False

    def _acceptable(self, result):
        return (result["guard_observed"] and result["transport_ok"] and result["http_status"] == 200 and result["content_matches"]
                and result["latency_ms"] <= self.latency_limit_ms)

    def _probe(self, probe):
        # Corroborate that this ordinary client reached this exact guard. A
        # misconfigured registry pointing at a different healthy loopback app
        # must not certify recovery of the attacked bank.
        with self.guard.lock:
            before = self.guard._request_sequence
        result = probe()
        until = time.monotonic() + .02
        while True:
            with self.guard.lock:
                own = [r for r in self.guard._records if r.sequence > before and r.source_ref == self._probe_sources[probe]]
                seen = any(r.status == result["http_status"] and r.elapsed_ms is not None for r in own)
            if seen or not own or self.guard.closed or self.cancelled() or time.monotonic() >= until:
                break
            threading.Event().wait(.001)
        return {**result, "guard_observed": seen}

    def baseline(self):
        """Must run before load; ordinary clients are never given an admission bypass."""
        require(not self.guard.closed, "Target guard closed")
        with self.guard.lock:
            self.guard._expire(self.guard.clock())
            require(not self.guard._buckets, "Healthy baseline must precede mitigation")
            revision = self.guard.revision
        self._baseline = [self._probe(probe) for probe in self.probes]
        with self.guard.lock:
            self._baseline_when = self.guard.clock()
            self._baseline_valid = (self.guard.revision == revision and not self.guard._buckets
                                    and not self.guard.closed and not self.cancelled())
        return {"result": "passed" if self._baseline_valid and all(self._acceptable(r) for r in self._baseline) else "inconclusive",
                "samples": deepcopy(self._baseline)}

    def verify(self):
        started, deadline = self.guard.clock(), time.monotonic() + self.timeout
        with self.guard.lock:
            self.guard._expire(self.guard.clock())
            policy_ids = {ref: b.defense_id for ref, b in self.guard._buckets.items()}
            sources = set(policy_ids) - set(self._probe_sources.values())
            rates = {ref: max(self.guard._buckets[ref].min_verification_rps, self.guard._buckets[ref].rate)
                     for ref in sources}
            defenses = sorted(policy_ids.values())
        results, continued = [], []
        baseline_ok = (self._baseline_valid and bool(self._baseline) and self._baseline_when is not None and
                       0 <= started - self._baseline_when <= 300 and all(self._acceptable(r) for r in self._baseline))
        last = started
        if baseline_ok and sources and not self.guard.closed:
            for _ in range(self.samples):
                if self.cancelled() or self.guard.closed or time.monotonic() >= deadline:
                    break
                for probe in self.probes:
                    results.append(self._probe(probe))
                    if time.monotonic() >= deadline:
                        break
                # This wait is bounded and cancellation is rechecked every 10ms.
                until = min(deadline, time.monotonic() + self.interval)
                while time.monotonic() < until and not self.cancelled() and not self.guard.closed:
                    threading.Event().wait(min(.01, max(0, until - time.monotonic())))
                now = self.guard.clock()
                with self.guard.lock:
                    self.guard._expire(now)
                    active = all(ref in self.guard._buckets and self.guard._buckets[ref].defense_id == policy_ids[ref]
                                 for ref in sources)
                    interval = now - last
                    interval_records = [r for r in self.guard._records if last < r.started <= now]
                    pressure = interval > 0 and all(
                        sum(r.source_ref == ref for r in interval_records) / interval > rates[ref]
                        and any(r.source_ref == ref and not r.admitted and r.status == 429
                                and r.defense_id == policy_ids[ref] for r in interval_records)
                        for ref in sources)
                    continued.append(active and pressure)
                last = now
        with self.guard.lock:
            blocked = sum(r.source_ref in sources and not r.admitted and r.status == 429
                          and r.defense_id == policy_ids[r.source_ref] and r.started > started for r in self.guard._records)
            intact = self.guard._dropped_until < started
        ordinary_ok = len(results) == self.samples * len(self.probes) and all(self._acceptable(r) for r in results)
        load_ok = len(continued) == self.samples and all(continued) and blocked > 0
        passed = (baseline_ok and ordinary_ok and load_ok and intact and not self.cancelled()
                  and not self.guard.closed and time.monotonic() < deadline)
        return {"schema": "range.availability.recovery/v1", **self.guard.scope,
                "result": "passed" if passed else "inconclusive", "defense_ids": defenses,
                "arrest_permitted": passed and self.guard.scope["data_source"] == "live", "fix_status": "not_assessed", "checks": {
                    "healthy_baseline": baseline_ok, "ordinary_access_under_load": ordinary_ok,
                    "continuing_observed_load": load_ok, "measurement_complete": intact},
                "samples": results, "latency_limit_ms": self.latency_limit_ms,
                "limitation": "Only the registered target, ordinary routes, identities and bounded traffic tested are covered."}
