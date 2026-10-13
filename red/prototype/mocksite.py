"""A minimal, generic standalone test website -- deliberately not bank-shaped -- used
to prove the engagement/authorization model (engagement.py) against a real site with a
different shape than lab.py's synthetic bank. This is a test site this team builds and
controls for its own prototype use, never a third party's property; see engagement.py
for why real ownership verification, not this file's existence, is the actual boundary.

It exposes the well-known authorization file a real engagement would fetch, two
unrelated ordinary read routes, and a login/logout/contact-form surface that is
deliberately shaped differently from the bank's (email+password body, a differently
named session cookie, JSON error bodies) -- proving the engagement SiteProfile model
against a real, different site shape, not a relabeled copy of lab.py's API.
"""

from __future__ import annotations

import http.server
import json
import secrets
import threading
from http.cookies import SimpleCookie
from typing import Any


class MockSiteState:
    def __init__(self, *, site_name: str = "Acme Test Co.") -> None:
        self.site_name = site_name
        self.lock = threading.Lock()
        # target_id -> token this site "has been given by its owner" to publish at the
        # well-known path -- standing in for a real site operator pasting in a value an
        # engagement platform gave them.
        self.authorization_tokens: dict[str, str] = {}
        self.requests_seen: list[str] = []
        # email -> {"password": ...}: this site's own test accounts. Never a real
        # client's real users; this team creates and controls every account here.
        self.accounts: dict[str, dict[str, str]] = {}
        # session token -> email
        self.sessions: dict[str, str] = {}
        self.contact_messages: list[dict[str, str]] = []
        # A real, toggleable flaw -- off by default (the already-correct behavior
        # proven in mocksite's own earlier tests: logout actually invalidates the
        # session). When True, /logout tells the caller "ok" but secretly leaves the
        # session usable, so the standard-handling vulnerability test can prove both
        # the vulnerable and the fixed case against the same route, the same pattern
        # lab.py's own active_flaws/disable_family already uses for the bank.
        self.session_fixation_vulnerable = False

    def set_authorization_token(self, target_id: str, token: str) -> None:
        with self.lock:
            self.authorization_tokens[target_id] = token

    def clear_authorization_token(self, target_id: str) -> None:
        with self.lock:
            self.authorization_tokens.pop(target_id, None)

    def add_account(self, email: str, password: str) -> None:
        with self.lock:
            self.accounts[email] = {"password": password}


class MockSiteHandler(http.server.BaseHTTPRequestHandler):
    server_version = "HeistMockSite/0.1"
    sys_version = ""

    @property
    def state(self) -> MockSiteState:
        return self.server.mock_state  # type: ignore[attr-defined]

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(2.0)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, status: int, payload: Any, *, set_cookie: str | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 8_192)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            value = json.loads(raw.decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def _session_email(self) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        morsel = cookie.get("acme_session")
        if morsel is None:
            return None
        with self.state.lock:
            return self.state.sessions.get(morsel.value)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        with self.state.lock:
            self.state.requests_seen.append(path)
        if path == "/":
            self._send(200, {"site": self.state.site_name, "status": "ok", "kind": "generic_test_site"})
            return
        if path == "/about":
            self._send(200, {"about": f"{self.state.site_name} is a generic test site, not a bank."})
            return
        if path == "/.well-known/heist-range-authorization.json":
            with self.state.lock:
                tokens = dict(self.state.authorization_tokens)
            self._send(200, {"tokens": tokens})
            return
        if path == "/account":
            email = self._session_email()
            if email is None:
                self._send(401, {"error": "active session required"})
                return
            self._send(200, {"email": email})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        with self.state.lock:
            self.state.requests_seen.append(path)
        if path == "/login":
            body = self._body()
            email, password = body.get("email"), body.get("password")
            with self.state.lock:
                account = self.state.accounts.get(email) if isinstance(email, str) else None
                if account is None or account["password"] != password:
                    self._send(401, {"error": "invalid credentials"})
                    return
                token = secrets.token_hex(16)
                self.state.sessions[token] = email
            self._send(200, {"status": "ok", "email": email}, set_cookie=f"acme_session={token}; Path=/")
            return
        if path == "/logout":
            email = self._session_email()
            if email is None:
                self._send(401, {"error": "no active session"})
                return
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            morsel = cookie.get("acme_session")
            with self.state.lock:
                # The real, toggleable flaw: when vulnerable, this tells the caller
                # "ok" without actually removing the session, so it keeps working
                # afterward -- never a flag the caller can see or set, only the
                # site's own, separately-configured state.
                if morsel is not None and not self.state.session_fixation_vulnerable:
                    self.state.sessions.pop(morsel.value, None)
            self._send(200, {"status": "ok"})
            return
        if path == "/contact":
            body = self._body()
            name, message = body.get("name"), body.get("message")
            if not isinstance(name, str) or not isinstance(message, str) or not name or not message:
                self._send(400, {"error": "name and message are required"})
                return
            with self.state.lock:
                self.state.contact_messages.append({"name": name, "message": message})
            self._send(200, {"status": "received"})
            return
        self._send(404, {"error": "not found"})


class MockSiteServer:
    """Threaded HTTP server bound to 127.0.0.1 on an ephemeral port by default."""

    def __init__(self, state: MockSiteState, *, port: int = 0) -> None:
        self.state = state
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), MockSiteHandler)
        self.httpd.mock_state = state  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="heist-mocksite", daemon=True)

    @property
    def origin(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "MockSiteServer":
        self.thread.start()
        return self

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def __enter__(self) -> "MockSiteServer":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.close()
