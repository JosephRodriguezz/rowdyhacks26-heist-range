"""Typed action validation and the fixed-origin, cookie-owning HTTP boundary."""

from __future__ import annotations

import http.client
import json
import re
import threading
import uuid
import urllib.parse
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any

from .board import BudgetExceeded, BudgetLedger, RedBoard, RunCancelled
from .domain import ActionProposal, Evidence, Role, RunLimits
from .lab import LabState


TARGET_ID = "bank-local"
IDENTITY_REFS = frozenset({"account_a", "account_b"})
BODY_FIELDS = frozenset({"query", "name", "message"})
SENSITIVE_KEYS = frozenset({
    "password", "passwd", "cookie", "set-cookie", "authorization", "token", "access_token", "session_token",
})


class ActionRejected(ValueError):
    pass


@dataclass(frozen=True)
class ActionResult:
    evidence: Evidence
    created_session_ref: str | None = None
    read_receipt: str | None = None
    dispatched: bool = True


class FixedTargetRegistry:
    """The model can name one registered target; it never supplies an origin."""

    def __init__(self, origin: str) -> None:
        parsed = urllib.parse.urlsplit(origin)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("prototype targets must be an HTTP origin on 127.0.0.1")
        if parsed.port is None:
            raise ValueError("loopback target origin must include its registered port")
        self._target = {TARGET_ID: (parsed.hostname, parsed.port)}

    def resolve(self, target_id: str) -> tuple[str, int]:
        try:
            return self._target[target_id]
        except KeyError as exc:
            raise ActionRejected("target is not registered") from exc


class ActionExecutor:
    def __init__(
        self,
        *,
        registry: FixedTargetRegistry,
        state: LabState,
        limits: RunLimits,
        budget: BudgetLedger,
        board: RedBoard,
        max_response_bytes: int | None = None,
        before_dispatch: Any | None = None,
    ) -> None:
        self.registry, self.state, self.limits, self.budget, self.board = registry, state, limits, budget, board
        self.max_response_bytes = max_response_bytes or limits.response_bytes
        self.before_dispatch = before_dispatch
        self._session_lock = threading.RLock()
        self._sessions: dict[str, dict[str, str]] = {}
        self._session_revision: dict[str, int] = {}
        self._closed = False

    def close(self) -> None:
        with self._session_lock:
            self._sessions.clear()
            self._session_revision.clear()
            self._closed = True

    def _session_cookie(self, session_ref: str | None, role: Role) -> str | None:
        if session_ref is None:
            return None
        with self._session_lock:
            entry = self._sessions.get(session_ref)
            if entry is None or entry["role"] != role:
                raise ActionRejected("session reference is unknown or belongs to another role")
            return entry["cookie"]

    @staticmethod
    def _sanitize_payload(value: Any) -> Any:
        if isinstance(value, dict):
            safe = {}
            for key, child in value.items():
                normalized = key.casefold().replace("_", "").replace("-", "")
                sensitive = {name.replace("_", "").replace("-", "") for name in SENSITIVE_KEYS}
                if normalized not in sensitive:
                    safe[key] = ActionExecutor._sanitize_payload(child)
            return safe
        if isinstance(value, list):
            return [ActionExecutor._sanitize_payload(item) for item in value]
        if isinstance(value, str):
            # The lab never sends credentials in a body; scrub common accidental diagnostic formats too.
            return re.sub(
                r"(?i)(?:set-cookie|authorization|password|session_token|access_token)\s*[:=]\s*[^\s,;]+",
                "[REDACTED]",
                value,
            )
        return value

    @staticmethod
    def _validate_path(path: str) -> str:
        if not isinstance(path, str) or not path or len(path) > 2_048:
            raise ActionRejected("relative path is invalid")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in path) or "\\" in path:
            raise ActionRejected("path contains forbidden characters")
        parsed = urllib.parse.urlsplit(path)
        decoded = urllib.parse.unquote(parsed.path)
        if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith("/") or parsed.path.startswith("//"):
            raise ActionRejected("only same-origin absolute paths are accepted")
        if any(part == ".." for part in decoded.split("/")):
            raise ActionRejected("path traversal is not accepted")
        if len(parsed.query) > 1_200:
            raise ActionRejected("query string is too long")
        sensitive_query_names = {
            "password", "passwd", "cookie", "set-cookie", "authorization", "auth", "token", "api_key",
            "credential", "access_token", "session_token",
        }
        if any(
            key.casefold() in sensitive_query_names
            for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        ):
            raise ActionRejected("credential-like query fields are not accepted")
        return urllib.parse.urlunsplit(("", "", parsed.path, parsed.query, ""))

    def _validate(self, proposal: ActionProposal) -> tuple[str, str, dict[str, str], str | None]:
        if proposal.target_id != TARGET_ID:
            raise ActionRejected("target is not registered")
        host, port = self.registry.resolve(proposal.target_id)
        if host != "127.0.0.1" or port <= 0:
            raise ActionRejected("registered target is outside loopback scope")
        capability = proposal.capability
        if capability == "start_account_session":
            if proposal.identity_ref not in IDENTITY_REFS:
                raise ActionRejected("identity reference is not supplied to Red")
            if proposal.path != "/" or proposal.body or proposal.session_ref or proposal.form_ref:
                raise ActionRejected("account login accepts only an identity reference")
            return "POST", "/api/login", {}, proposal.identity_ref
        if capability == "end_account_session":
            if proposal.path not in ("/", "/api/logout"):
                raise ActionRejected("logout path is fixed by the action boundary")
            if not proposal.session_ref or proposal.body or proposal.identity_ref or proposal.form_ref:
                raise ActionRejected("logout requires an owned session reference")
            return "POST", "/api/logout", {}, None
        if capability == "submit_form":
            if proposal.form_ref != "contact_form":
                raise ActionRejected("form reference was not discovered or registered")
            if proposal.identity_ref:
                raise ActionRejected("form submission does not accept account credentials")
            if proposal.method != "POST" or proposal.path not in ("/", "/api/contact"):
                raise ActionRejected("form destination and method are fixed")
            if set(proposal.body) - {"name", "message"}:
                raise ActionRejected("form contains fields outside its schema")
            path, method = "/api/contact", "POST"
        elif capability == "read_page":
            if proposal.identity_ref or proposal.form_ref:
                raise ActionRejected("read_page does not accept identity or form references")
            if proposal.method != "GET" or proposal.body:
                raise ActionRejected("read_page accepts only a GET without a body")
            path, method = self._validate_path(proposal.path), "GET"
        elif capability == "request_api":
            if proposal.identity_ref or proposal.form_ref:
                raise ActionRejected("request_api does not accept identity or form references")
            if proposal.method not in ("GET", "POST"):
                raise ActionRejected("API method is not allowed")
            path = self._validate_path(proposal.path)
            parsed = urllib.parse.urlsplit(path)
            if not (parsed.path.startswith("/api/") or parsed.path.startswith("/demo/")):
                raise ActionRejected("API action must use a registered local app path")
            if set(proposal.body) - BODY_FIELDS:
                raise ActionRejected("API body contains fields outside its schema")
            if proposal.method == "GET" and proposal.body:
                raise ActionRejected("GET body is not supported")
            method = proposal.method
        else:
            raise ActionRejected("capability is not allowlisted")
        if any(len(k) > 32 or len(v) > 512 for k, v in proposal.body.items()):
            raise ActionRejected("body field exceeds the configured bound")
        if len(json.dumps(proposal.body).encode("utf-8")) > 2_048:
            raise ActionRejected("request body exceeds the configured bound")
        with self.state.lock:
            known_secrets = [item["password"] for item in self.state.identities.values()]
            known_secrets.extend(self.state.sessions.keys())
        if any(secret and secret in urllib.parse.unquote(path) for secret in known_secrets):
            raise ActionRejected("tool-owned credential material cannot be placed in a target path")
        if any(
            secret and any(secret in urllib.parse.unquote(value) for value in proposal.body.values())
            for secret in known_secrets
        ):
            raise ActionRejected("tool-owned credential material cannot be supplied in an action body")
        return method, path, dict(proposal.body), None

    def _request_summary(self, proposal: ActionProposal, identity_ref: str | None) -> str:
        if identity_ref:
            return json.dumps({"identity_ref": identity_ref}, separators=(",", ":"))
        safe_body = self._sanitize_payload(proposal.body)
        rendered = json.dumps(safe_body, ensure_ascii=False, separators=(",", ":")) if safe_body else ""
        if not rendered:
            return ""
        with self.state.lock:
            known_secrets = [item["password"] for item in self.state.identities.values()]
            known_secrets.extend(self.state.sessions.keys())
        for secret in known_secrets:
            if secret:
                rendered = rendered.replace(secret, "[REDACTED]")
        return rendered[:2_048]

    def execute(self, proposal: ActionProposal, *, role: Role, task_id: str) -> ActionResult:
        evidence_id = "ev-" + uuid.uuid4().hex[:16]
        method, path, body, identity_ref = self._validate(proposal)
        host, port = self.registry.resolve(proposal.target_id)
        cookie: str | None = None
        if proposal.capability == "end_account_session":
            cookie = self._session_cookie(proposal.session_ref, role)
        elif proposal.session_ref:
            cookie = self._session_cookie(proposal.session_ref, role)
        # Exact same test cannot be independently dispatched by a different task in the same target generation.
        with self._session_lock, self.state.lock:
            session_revision = self._session_revision.get(proposal.session_ref or "", 0)
            defense_generation = tuple(sorted(self.state.defenses))
        fingerprint = json.dumps(
            [proposal.capability, method, path, sorted(body.items()), proposal.identity_ref, proposal.session_ref,
             session_revision, defense_generation], separators=(",", ":"),
        )
        if not self.board.claim_action_fingerprint(fingerprint, task_id):
            evidence = Evidence(
                evidence_id, 0, role, proposal.capability, method, path, None,
                "Duplicate test blocked by Red task ownership.", "",
                session_ref=proposal.session_ref, failure_kind="duplicate_test",
            )
            self.board.add_evidence(evidence)
            return ActionResult(self.board.get_evidence(evidence_id), dispatched=False)  # type: ignore[arg-type]
        self.budget.reserve_action(evidence_id)
        self.budget.check_active()
        if self._closed:
            raise RunCancelled("action executor is closed")
        if self.before_dispatch:
            self.before_dispatch()
        headers = {"Accept": "application/json", "X-Lab-Action-ID": evidence_id}
        if cookie:
            headers["Cookie"] = "heist_session=" + cookie
        request_bytes: bytes | None = None
        if identity_ref:
            identity = self.state.identities[identity_ref]
            request_bytes = json.dumps(identity, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif body:
            request_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        conn = http.client.HTTPConnection(host, port, timeout=self.limits.request_timeout_seconds)
        status: int | None = None
        response_text = ""
        summary = ""
        failure_kind: str | None = None
        receipt: str | None = None
        created_session_ref: str | None = None
        try:
            conn.request(method, path, body=request_bytes, headers=headers)
            response = conn.getresponse()
            status = response.status
            raw = response.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                raw = raw[: self.max_response_bytes]
                failure_kind = "response_truncated"
            # Never follow any redirect; the underlying client is fixed to the registered loopback host.
            if 300 <= status < 400:
                failure_kind = "redirect_not_followed"
                response_text = "Redirect response observed; the action boundary did not follow it."
            else:
                try:
                    parsed_body = json.loads(raw.decode("utf-8")) if raw else {}
                    safe_body = self._sanitize_payload(parsed_body)
                    response_text = json.dumps(safe_body, ensure_ascii=False, separators=(",", ":"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    response_text = raw.decode("utf-8", errors="replace")
                    response_text = response_text[: self.max_response_bytes]
            receipt = response.getheader("X-Lab-Read-Receipt")
            set_cookie = response.getheader("Set-Cookie")
            if proposal.capability == "start_account_session" and status == 200 and set_cookie:
                morsel = SimpleCookie()
                morsel.load(set_cookie)
                cookie_morsel = morsel.get("heist_session")
                if cookie_morsel:
                    created_session_ref = "sess-" + uuid.uuid4().hex[:16]
                    with self._session_lock:
                        self._sessions[created_session_ref] = {"cookie": cookie_morsel.value, "role": role}
                        self._session_revision[created_session_ref] = 0
            summary = f"{method} {urllib.parse.urlsplit(path).path} returned HTTP {status}."
            if proposal.capability == "end_account_session" and proposal.session_ref and status == 200:
                with self._session_lock:
                    self._session_revision[proposal.session_ref] = self._session_revision.get(proposal.session_ref, 0) + 1
            if failure_kind == "response_truncated":
                summary += " Response exceeded the configured output limit and was truncated."
            if failure_kind == "redirect_not_followed":
                summary += " Redirect was not followed."
        except (OSError, http.client.HTTPException, TimeoutError) as exc:
            failure_kind = "target_transport"
            # Do not include exception text; libraries may echo request metadata.
            summary = f"Local target request failed ({type(exc).__name__}); result is inconclusive."
        finally:
            conn.close()
        evidence = Evidence(
            evidence_id=evidence_id,
            sequence=0,
            role=role,
            capability=proposal.capability,
            method=method,
            path=urllib.parse.urlsplit(path).path,
            status=status,
            summary=summary or "Action completed.",
            body=response_text,
            request_summary=self._request_summary(proposal, identity_ref),
            session_ref=created_session_ref or proposal.session_ref,
            failure_kind=failure_kind,
        )
        self.board.add_evidence(evidence)
        return ActionResult(self.board.get_evidence(evidence_id), created_session_ref, receipt)  # type: ignore[arg-type]
