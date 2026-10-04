"""Independent HTTP regression checks; never exposed to team contexts."""

import hashlib
import http.client
import json
from http.cookies import SimpleCookie
import uuid

from red.prototype.actions import FixedTargetRegistry
from red.prototype.board import BudgetExceeded, RunCancelled


class Referee:
    def __init__(self, runtime):
        self.runtime = runtime
        self.lab = runtime.lab

    def request(self, method, path, *, body=None, cookie=None):
        runtime = self.runtime
        with runtime.gate.operation():
            evidence_id = "ref-" + uuid.uuid4().hex[:16]
            runtime.budget.reserve_action(evidence_id)
            host, port = FixedTargetRegistry(self.lab.origin).resolve(self.lab.target_id)
            conn = http.client.HTTPConnection(host, port, timeout=runtime.limits.request_timeout_seconds)
            headers = {"X-Lab-Action-ID": evidence_id, "Content-Type": "application/json"}
            if cookie:
                headers["Cookie"] = "heist_session=" + cookie
            result = {"status": None, "failure": None, "body": {}, "cookie": None, "evidence_id": evidence_id}
            try:
                conn.request(method, path, body=json.dumps(body).encode() if body else None, headers=headers)
                response = conn.getresponse()
                raw = response.read(runtime.limits.response_bytes + 1)
                result["status"] = response.status
                if len(raw) > runtime.limits.response_bytes or not 200 <= response.status < 500:
                    result["failure"] = "ambiguous_response"
                else:
                    result["body"] = json.loads(raw)
                jar = SimpleCookie()
                jar.load(response.getheader("Set-Cookie", ""))
                morsel = jar.get("heist_session")
                result["cookie"] = morsel.value if morsel else None
            except (OSError, http.client.HTTPException, ValueError):
                result["failure"] = "transport_or_invalid_response"
            finally:
                conn.close()
            runtime.record_evidence(evidence_id, "referee_only", {
                "method": method, "path": path, "status": result["status"], "failure": result["failure"],
                "summary": "Independent registered-lab request; raw credentials and bodies are not retained.",
            })
            runtime.record_evidence("public-" + evidence_id, "judge_safe", {
                "method": method, "http_status": result["status"], "failure_kind": result["failure"],
                "summary": "Independent local-lab check; private data and credentials withheld.",
            })
            return result

    @staticmethod
    def readable(result, record):
        if result["status"] != 200 or result["failure"]:
            return False
        body = result["body"]
        return (isinstance(body, dict) and body.get("record_id") == record["record_id"]
                and isinstance(body.get("content"), str)
                and hashlib.sha256(body["content"].encode()).hexdigest()
                == hashlib.sha256(record["content"].encode()).hexdigest())

    def baseline(self):
        checks, cookies = [], {}
        for identity_ref, identity in self.lab.state.identities.items():
            record = next(r for r in self.lab.state.records.values() if r["owner"] == identity["username"])
            login = self.request("POST", "/api/login", body=identity)
            if login["status"] != 200 or login["failure"] or not login["cookie"]:
                checks.append({"identity_ref": identity_ref, "result": "inconclusive", "evidence_refs": ["public-" + login["evidence_id"]]})
                continue
            response = self.request("GET", "/api/records/" + record["record_id"], cookie=login["cookie"])
            checks.append({"identity_ref": identity_ref, "result": "passed" if self.readable(response, record) else "inconclusive",
                           "evidence_refs": ["public-" + login["evidence_id"], "public-" + response["evidence_id"]]})
            cookies[identity["username"]] = login["cookie"]
        return checks, cookies

    def final_checks(self):
        checks, containments = [], []
        try:
            checks, cookies = self.baseline()
            healthy = len(checks) == 2 and all(c["result"] == "passed" for c in checks)
            for ref, record in self.runtime.revoked.items():
                old_cookie = self.lab.cookie_for_referee(ref)
                denied = self.request("GET", "/api/records/" + record["resource_id"], cookie=old_cookie)
                with self.lab.state.lock:
                    inactive = not self.lab.state.sessions[old_cookie].active
                contained = healthy and inactive and not denied["failure"] and denied["status"] in (401, 403)
                other = self.lab.state.records[record["resource_id"]]
                fresh_cookie = cookies.get(record["actor_ref"])
                retry = self.request("GET", "/api/records/" + other["record_id"], cookie=fresh_cookie) if fresh_cookie else None
                fresh = "inconclusive"
                if retry and healthy and not retry["failure"]:
                    if self.readable(retry, other) and other["owner"] != record["actor_ref"]:
                        fresh = "unauthorized_access_persists"
                    elif retry["status"] == 403:
                        fresh = "blocked_for_tested_path"
                containments.append({
                    "session_ref": ref, "containment": "verified" if contained else "inconclusive",
                    "fresh_session_retry": fresh, "fix_status": "not_applied",
                    "evidence_refs": ["public-" + denied["evidence_id"]] + (["public-" + retry["evidence_id"]] if retry else []),
                })
            return {"legitimate_access": "passed" if healthy else "inconclusive", "authorized_checks": checks,
                    "containments": containments, "fix_status": "not_applied"}
        except (BudgetExceeded, RunCancelled):
            return {"legitimate_access": "inconclusive", "authorized_checks": checks,
                    "containments": containments, "fix_status": "not_applied", "limitation": "verification_budget_or_cancellation"}
