"""A minimal, generic standalone test website -- deliberately not bank-shaped -- used
to prove the engagement/authorization model (engagement.py) against a real site with a
different shape than lab.py's synthetic bank. This is a test site this team builds and
controls for its own prototype use, never a third party's property; see engagement.py
for why real ownership verification, not this file's existence, is the actual boundary.

It exposes the well-known authorization file a real engagement would fetch, and two
unrelated ordinary routes, to prove the authorization layer in front of something that
is not the bank's own API shape at all.
"""

from __future__ import annotations

import http.server
import json
import threading
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

    def set_authorization_token(self, target_id: str, token: str) -> None:
        with self.lock:
            self.authorization_tokens[target_id] = token

    def clear_authorization_token(self, target_id: str) -> None:
        with self.lock:
            self.authorization_tokens.pop(target_id, None)


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

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

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
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
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
