"""Trusted adapter for the existing bank: target telemetry and narrow revocation.

The agent path receives no LabState. No administrative HTTP route is exposed.
The order action name is a compatibility alias for owner-only bank record reads.
"""

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
import threading
import urllib.parse

from red.prototype.lab import BankRequestHandler, LabState


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TelemetryHandler(BankRequestHandler):
    def _send(self, status, payload, *, headers=None, action_id=None):
        adapter = self.server.adapter
        parsed = urllib.parse.urlsplit(self.path)
        if self.command == "GET" and parsed.path.startswith("/api/records/"):
            record_id = urllib.parse.unquote(parsed.path.removeprefix("/api/records/"))
            jar = SimpleCookie()
            try:
                jar.load(self.headers.get("Cookie", ""))
                value = jar.get("heist_session")
                cookie = value.value if value else None
            except Exception:
                cookie = None
            adapter.observe_read(
                request_id=self.headers.get("X-Lab-Action-ID", "")[:80],
                record_id=record_id, cookie=cookie, status=status,
            )
        super()._send(status, payload, headers=headers, action_id=action_id)


class BankLabAdapter:
    target_id = "bank-local"
    version = "synthetic-bank/0.2.0"
    access_policy = {"id": "bank-records-owner-only", "owner_only_actions": ["read_private_order"]}

    def __init__(self, session_id, scenario_id="access_control", seed=26):
        self.session_id = session_id
        self.state = LabState(scenario_id, seed=seed)
        self.lock = threading.RLock()
        self._refs = {}
        self._cookies = {}
        self._telemetry = deque(maxlen=256)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), TelemetryHandler)
        self.httpd.daemon_threads = True
        self.httpd.lab_state, self.httpd.adapter = self.state, self
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="core-bank", daemon=True)
        self.thread.start()

    @property
    def origin(self):
        return "http://127.0.0.1:" + str(self.httpd.server_port)

    def register_session(self, ref, cookie, role):
        with self.lock:
            self._refs[ref] = {"cookie": cookie, "role": role}
            self._cookies[cookie] = ref

    def observe_read(self, *, request_id, record_id, cookie, status):
        # Only requests carrying this contest's tool-issued handles enter Blue's feed.
        with self.lock, self.state.lock:
            ref = self._cookies.get(cookie)
            session = self.state.sessions.get(cookie)
            record = self.state.records.get(record_id)
            if not ref or not session or not record or not request_id:
                return
            self._telemetry.append({
                "request_id": request_id, "timestamp": utc_now(),
                "target_id": self.target_id, "target_version": self.version,
                "assessment_id": self.session_id, "data_source": "live",
                "actor_ref": session.principal, "session_ref": ref,
                "resource_id": record_id, "resource_owner_ref": record["owner"],
                "action": "read_private_order", "http_status": status,
            })

    def telemetry(self):
        with self.lock:
            return deepcopy(list(self._telemetry))

    def revoke(self, ref):
        with self.lock, self.state.lock:
            entry = self._refs.get(ref)
            if entry is None or entry["role"] not in ("scout", "operator"):
                raise ValueError("session is not registered for this contest")
            session = self.state.sessions.get(entry["cookie"])
            if session is None or not session.active:
                raise ValueError("session is not active")
            session.active = False

    def cookie_for_referee(self, ref):
        with self.lock:
            return self._refs[ref]["cookie"]

    def redact(self, value):
        # Defense-in-depth for persisted private text as well as public projection.
        from red.prototype.actions import ActionExecutor
        with self.state.lock:
            secrets = [v["password"] for v in self.state.identities.values()] + list(self.state.sessions)
        def scrub(item):
            if isinstance(item, dict):
                return {k: scrub(v) for k, v in ActionExecutor._sanitize_payload(item).items()}
            if isinstance(item, list):
                return [scrub(v) for v in item]
            if isinstance(item, str):
                for secret in secrets:
                    item = item.replace(secret, "[REDACTED]")
            return item
        return scrub(value)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        with self.lock:
            self._refs.clear()
            self._cookies.clear()
        self.state.close()
