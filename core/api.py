"""Loopback HTTP transport for the service's already-projected judge views.

The service owns authorization of records and the registered target registry.
This adapter never requests a different audience or imports/starts a runtime.
``core.service.Conflict`` is recognized through that module's explicit export
when loaded, so a fake service can exercise this adapter independently.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import math
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlsplit


class CoreService(Protocol):
    """Synchronous, quick service calls returning JSON-safe judge projections.

    ``events`` returns ``{events: [...], last_event_id: nonnegative int}``.
    Events use a numeric ``sequence``, ``id``, or ``event_id``, and
    ``event_type`` or ``type`` as the SSE event name. Reset
    returns the new session snapshot; evidence raises KeyError when private.
    """

    def targets(self) -> Any: ...
    def create(self, *, target_id: str, planner_mode: str, action_id: str) -> Any: ...
    def list_sessions(self) -> Any: ...
    def status(self, session_id: str) -> Any: ...
    def action(self, session_id: str, action_type: str, *, action_id: str) -> Any: ...
    def events(self, session_id: str, *, after: int) -> Any: ...
    def evidence(self, session_id: str, evidence_id: str) -> Any: ...


_MAX_BODY = 16_384
_ID = r"[A-Za-z0-9_-]{1,128}"
_SESSION_PATH = re.compile(rf"/api/assessments/({_ID})(?:/(actions|events|stream)|/evidence/({_ID}))?")
_DECIMAL = re.compile(r"[0-9]+")
_EVENT_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_ACTIONS = frozenset({"start", "pause", "resume", "stop", "reset"})


class _RequestError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


def _service_error(exc: Exception) -> _RequestError:
    # Inspect the exported class, never infer conflicts from exception text or
    # a class name alone. Service instances necessarily load their own module.
    conflict = getattr(sys.modules.get("core.service"), "Conflict", None)
    if isinstance(conflict, type) and issubclass(conflict, Exception) and isinstance(exc, conflict):
        return _RequestError(409, "conflict", "Action conflicts with the current state.")
    if isinstance(exc, KeyError):
        return _RequestError(404, "not_found", "Resource not found.")
    if isinstance(exc, ValueError):
        return _RequestError(400, "invalid_request", "Invalid request.")
    return _RequestError(500, "internal_error", "Request could not be completed.")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _cursor(value: str) -> int:
    if len(value) > 20 or not _DECIMAL.fullmatch(value):
        raise _RequestError(400, "invalid_request", "Invalid event cursor.")
    return int(value)


class _HTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def handle_error(self, request: Any, client_address: Any) -> None:
        # The default traceback can contain service exception secrets.
        pass


class _IPv6HTTPServer(_HTTPServer):
    address_family = socket.AF_INET6


class CoreHTTPServer:
    """Start/stop a thin judge API in a context; bind only literal loopback IPs.

    ``origin`` is available after construction, including an ephemeral port.
    The service remains owned by the caller and is not stopped by this adapter.
    SSE connections last at most ``stream_seconds`` and reconnect by cursor.
    """

    def __init__(self, service: CoreService, *, token: str, host: str = "127.0.0.1",
                 port: int = 0, stream_seconds: float = 20.0) -> None:
        if not isinstance(token, str) or len(token) < 16 or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise ValueError("An ASCII bearer token of at least 16 characters is required.")
        if not isinstance(host, str):
            raise ValueError("A literal loopback address is required.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise ValueError("A literal loopback address is required.") from None
        if not address.is_loopback or "%" in host:
            raise ValueError("A literal loopback address is required.")
        if type(port) is not int or not 0 <= port <= 65_535:
            raise ValueError("Invalid port.")
        if isinstance(stream_seconds, bool) or not isinstance(stream_seconds, (int, float)):
            raise ValueError("Invalid stream duration.")
        if not math.isfinite(stream_seconds) or stream_seconds <= 0:
            raise ValueError("Invalid stream duration.")
        self.service = service
        self.stream_seconds = float(stream_seconds)
        self._token = token.encode("ascii")
        self._stopping = threading.Event()
        self._streams = threading.BoundedSemaphore(4)
        self._closed = False
        server_type = _IPv6HTTPServer if address.version == 6 else _HTTPServer
        self._httpd = server_type((str(address), port), _RequestHandler)
        self._httpd.api = self
        bound_host, bound_port = self._httpd.server_address[:2]
        self._authority = f"[{bound_host}]:{bound_port}" if address.version == 6 else f"{bound_host}:{bound_port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        kwargs={"poll_interval": 0.05}, name="core-api", daemon=True)

    @property
    def origin(self) -> str:
        return "http://" + self._authority

    def start(self) -> CoreHTTPServer:
        if self._closed:
            raise RuntimeError("API server is closed.")
        if not self._thread.is_alive():
            self._thread.start()
        return self

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stopping.set()
        if self._thread.is_alive():
            self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def __enter__(self) -> CoreHTTPServer:
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


class _RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "CoreAPI"
    sys_version = ""

    @property
    def api(self) -> CoreHTTPServer:
        return self.server.api

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(2.0)

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def parse_request(self) -> bool:
        if not super().parse_request():
            return False
        # The stdlib collapses leading // for redirect safety. Restore the
        # original target so this API can reject it rather than alias a route.
        self.path = self.requestline.split()[1]
        return True

    def __getattr__(self, name: str) -> Any:
        # Unknown verbs also pass authentication before receiving a JSON 405.
        if name.startswith("do_"):
            return self._handle
        raise AttributeError(name)

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        # Includes errors from the stdlib request-line/header parser. Its
        # default HTML response interpolates attacker-controlled request text.
        self._error(_RequestError(code, "invalid_request", "Invalid HTTP request."))

    def handle_expect_100(self) -> bool:
        try:
            self._boundary()
        except _RequestError as exc:
            self._error(exc)
        else:
            self._error(_RequestError(417, "invalid_request", "Request expectations are unsupported."))
        return False

    def _header(self, name: str, *, required: bool = False) -> str | None:
        values = self.headers.get_all(name, [])
        if len(values) > 1 or (required and not values):
            raise _RequestError(400, "invalid_request", "Invalid request headers.")
        return values[0] if values else None

    def _boundary(self) -> tuple[str, dict[str, str]]:
        if self._header("Host", required=True) != self.api._authority:
            raise _RequestError(400, "invalid_host", "Invalid request host.")
        origin = self._header("Origin")
        if origin is not None and origin != self.api.origin:
            raise _RequestError(403, "invalid_origin", "Request origin is not allowed.")
        # Authenticate before route/body validation, including unknown /api paths.
        if self.path == "/api" or self.path.startswith("/api/") or self.path.startswith("/api?"):
            authorization = self._header("Authorization") or ""
            supplied = authorization[7:] if authorization.startswith("Bearer ") else ""
            if not hmac.compare_digest(supplied.encode("utf-8"), self.api._token):
                raise _RequestError(401, "unauthorized", "Bearer authentication is required.")
        if len(self.path) > 4096 or not self.path.startswith("/") or self.path.startswith("//"):
            raise _RequestError(400, "invalid_request", "Invalid request path.")
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise _RequestError(400, "invalid_request", "Invalid request path.")
        try:
            pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True,
                              encoding="utf-8", errors="strict", max_num_fields=8)
        except (ValueError, UnicodeError):
            raise _RequestError(400, "invalid_request", "Invalid request query.") from None
        query = dict(pairs)
        if len(query) != len(pairs):
            raise _RequestError(400, "invalid_request", "Duplicate query fields are not allowed.")
        if self._header("Transfer-Encoding") is not None or self._header("Content-Encoding") is not None:
            raise _RequestError(400, "invalid_request", "Encoded request bodies are unsupported.")
        length = self._header("Content-Length")
        if length is not None:
            if len(length) > 20 or not _DECIMAL.fullmatch(length):
                raise _RequestError(400, "invalid_request", "Invalid content length.")
            if int(length) > _MAX_BODY:
                raise _RequestError(413, "body_too_large", "Request body is too large.")
            if self.command != "POST" and int(length) != 0:
                raise _RequestError(400, "invalid_request", "Request body is not allowed.")
        return parsed.path, query

    def _body(self, *, required: set[str], optional: set[str] = frozenset()) -> dict[str, str]:
        content_type = self._header("Content-Type")
        if content_type is None or content_type.split(";", 1)[0].strip().lower() != "application/json":
            raise _RequestError(415, "unsupported_media_type", "An application/json body is required.")
        length_header = self._header("Content-Length")
        if length_header is None:
            raise _RequestError(411, "length_required", "Content length is required.")
        length = int(length_header)
        if not length:
            raise _RequestError(400, "invalid_json", "Invalid JSON body.")

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result = dict(pairs)
            if len(result) != len(pairs):
                raise ValueError()
            return result

        def invalid_constant(value: str) -> None:
            raise ValueError()

        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError()
            body = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                              parse_constant=invalid_constant)
        except (ValueError, UnicodeError, RecursionError, TimeoutError):
            raise _RequestError(400, "invalid_json", "Invalid JSON body.") from None
        if not isinstance(body, dict) or not required <= body.keys() or body.keys() - required - optional:
            raise _RequestError(400, "invalid_request", "Invalid request fields.")
        for value in body.values():
            if not isinstance(value, str) or not value.strip() or len(value) > 128:
                raise _RequestError(400, "invalid_request", "Invalid request fields.")
            if any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise _RequestError(400, "invalid_request", "Invalid request fields.")
        return body

    def _handle(self) -> None:
        try:
            path, query = self._boundary()
            match = _SESSION_PATH.fullmatch(path)
            endpoint = match[2] if match else None
            if query.keys() - ({"after"} if endpoint in {"events", "stream"} else set()):
                raise _RequestError(400, "invalid_request", "Unknown query fields are not allowed.")
            if self.command not in {"GET", "POST"}:
                raise _RequestError(405, "method_not_allowed", "Method not allowed.")
            if path == "/health":
                self._require_method("GET")
                self._json(200, {"status": "ok"})
            elif path == "/api/targets":
                self._require_method("GET")
                self._json(200, self._call(self.api.service.targets))
            elif path == "/api/assessments":
                if self.command == "GET":
                    self._json(200, {"assessments": self._call(self.api.service.list_sessions)})
                else:
                    body = self._body(required={"action_id", "target_id"}, optional={"planner_mode"})
                    self._json(201, self._call(self.api.service.create, target_id=body["target_id"],
                               planner_mode=body.get("planner_mode", "fixture"), action_id=body["action_id"]))
            elif match:
                session_id, _, evidence_id = match.groups()
                if endpoint == "actions":
                    self._require_method("POST")
                    body = self._body(required={"action_id", "type"})
                    if body["type"] not in _ACTIONS:
                        raise _RequestError(400, "invalid_request", "Unknown action type.")
                    self._json(202, self._call(self.api.service.action, session_id, body["type"], action_id=body["action_id"]))
                else:
                    self._require_method("GET")
                    if endpoint in {"events", "stream"}:
                        after = _cursor(query.get("after", "0"))
                        if endpoint == "stream":
                            header = self._header("Last-Event-ID")
                            self._stream(session_id, after if header is None else _cursor(header))
                        else:
                            self._json(200, self._call(self.api.service.events, session_id, after=after))
                    elif evidence_id is not None:
                        self._json(200, self._call(self.api.service.evidence, session_id, evidence_id))
                    else:
                        self._json(200, self._call(self.api.service.status, session_id))
            else:
                raise _RequestError(404, "not_found", "Resource not found.")
        except _RequestError as exc:
            self._error(exc)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except Exception as exc:
            self._error(_service_error(exc))

    def _require_method(self, method: str) -> None:
        if self.command != method:
            raise _RequestError(405, "method_not_allowed", "Method not allowed.")

    def _call(self, method: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return method(*args, **kwargs)
        except Exception as exc:
            raise _service_error(exc) from None

    def _json(self, status: int, value: Any) -> None:
        raw = _json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        if status == 401:
            self.send_header("WWW-Authenticate", "Bearer")
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _error(self, error: _RequestError) -> None:
        try:
            self._json(error.status, {"error": {"code": error.code, "message": error.message}})
        except OSError:
            self.close_connection = True

    def _poll_frames(self, session_id: str, after: int) -> tuple[list[bytes], int]:
        batch = self._call(self.api.service.events, session_id, after=after)
        last = batch["last_event_id"]
        if type(last) is not int or last < 0:
            raise RuntimeError()
        ordered = []
        for event in batch["events"]:
            event_id = event.get("sequence", event.get("id", event.get("event_id")))
            if isinstance(event_id, str) and _DECIMAL.fullmatch(event_id) and len(event_id) <= 20:
                event_id = int(event_id)
            if type(event_id) is not int or event_id < 0:
                raise RuntimeError()
            name = event.get("event_type", event.get("type", "message"))
            if not isinstance(name, str) or not _EVENT_NAME.fullmatch(name):
                raise RuntimeError()
            if event_id > after:
                ordered.append((event_id, name, _json_bytes(event)))
        ordered.sort(key=lambda item: item[0])
        frames = []
        cursor = after
        for event_id, name, data in ordered:
            if event_id > cursor:
                frames.append(f"id: {event_id}\nevent: {name}\ndata: ".encode("ascii") + data + b"\n\n")
                cursor = event_id
        return frames, max(cursor, last)

    def _stream(self, session_id: str, after: int) -> None:
        if not self.api._streams.acquire(blocking=False):
            raise _RequestError(503, "stream_limit", "Too many event streams.")
        try:
            frames, cursor = self._poll_frames(session_id, after)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            deadline = time.monotonic() + self.api.stream_seconds
            heartbeat_at = 0.0
            while not self.api._stopping.is_set() and time.monotonic() < deadline:
                for frame in frames:
                    self.wfile.write(frame)
                now = time.monotonic()
                if now >= heartbeat_at:
                    self.wfile.write(b": heartbeat\n\n")
                    heartbeat_at = now + 0.25
                self.wfile.flush()
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self.api._stopping.wait(min(0.05, remaining)):
                    break
                try:
                    frames, cursor = self._poll_frames(session_id, cursor)
                except Exception as exc:
                    error = exc if isinstance(exc, _RequestError) else _service_error(exc)
                    self.wfile.write(b"event: error\ndata: " + _json_bytes({"error": {
                        "code": error.code, "message": error.message}}) + b"\n\n")
                    break
        except (OSError, TimeoutError):
            self.close_connection = True
        finally:
            self.api._streams.release()

    do_GET = _handle
    do_POST = _handle
    do_HEAD = _handle
    do_PUT = _handle
    do_PATCH = _handle
    do_DELETE = _handle
    do_OPTIONS = _handle
    do_TRACE = _handle
    do_CONNECT = _handle
