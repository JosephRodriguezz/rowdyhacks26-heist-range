"""Core-owned guided access-control assessment for the first golden scenario.

This module deliberately keeps the orchestration small and explicit.  It wires
the existing red runner, blue observer, bounded executor, and referee together,
and stores an append-only event trail in SQLite.  The patch step uses a named
known-good fallback on a disposable target; it never edits the running target
or treats applying a patch as proof that the fix works.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import json
import sqlite3
from threading import Thread
from typing import Any, Mapping
from uuid import uuid4

from backend.app.agents.blue import PRIVATE_ORDERS_POLICY, observe
from backend.app.agents.red.runner import execute as run_red
from cyber_range.storefront import LabState, create_server
from cyber_range.storefront import patched_policy

from .http_executor import BoundedHttpExecutor, RequestBudget
from .referee import IndependentReferee
from .registry import TargetRegistry, TargetSpec


DATA_SOURCE = "live"
BASE_TARGET = "storefront-lab"
BASE_VERSION = "lab-v1"
PATCHED_VERSION = "lab-v2"


class AssessmentStore:
    """Minimal durable assessment/event store owned by core."""

    def __init__(self, path: str = ":memory:") -> None:
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS assessments (
                assessment_id TEXT PRIMARY KEY,
                target_id TEXT NOT NULL,
                target_version TEXT NOT NULL,
                data_source TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assessment_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id TEXT NOT NULL REFERENCES assessments(assessment_id),
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_version TEXT NOT NULL,
                data_source TEXT NOT NULL,
                evidence_refs TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def create_assessment(self, assessment_id: str, target_id: str, version: str) -> None:
        now = _now()
        self.connection.execute(
            "INSERT INTO assessments VALUES (?, ?, ?, ?, ?, ?, ?)",
            (assessment_id, target_id, version, DATA_SOURCE, "running", now, now),
        )
        self.connection.commit()

    def set_status(self, assessment_id: str, status: str, version: str) -> None:
        self.connection.execute(
            "UPDATE assessments SET status = ?, target_version = ?, updated_at = ? WHERE assessment_id = ?",
            (status, version, _now(), assessment_id),
        )
        self.connection.commit()

    def append(self, assessment_id: str, event_type: str, actor: str, target_id: str,
               target_version: str, data: Mapping[str, Any], evidence_refs: tuple[str, ...] = ()) -> dict[str, Any]:
        created = _now()
        payload = dict(data)
        cursor = self.connection.execute(
            "INSERT INTO assessment_events(assessment_id, event_type, actor, target_id, target_version, "
            "data_source, evidence_refs, payload, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (assessment_id, event_type, actor, target_id, target_version, DATA_SOURCE,
             json.dumps(list(evidence_refs), sort_keys=True), json.dumps(payload, sort_keys=True), created),
        )
        self.connection.commit()
        return {"schema_version": "1.0", "id": cursor.lastrowid, "type": event_type, "actor": actor,
                "assessment_id": assessment_id, "target_id": target_id,
                "target_version": target_version, "data_source": DATA_SOURCE,
                "evidence_refs": list(evidence_refs), "data": payload, "timestamp": created}

    def events(self, assessment_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT event_id, event_type, actor, target_id, target_version, data_source, evidence_refs, payload, created_at "
            "FROM assessment_events WHERE assessment_id = ? ORDER BY event_id", (assessment_id,)
        ).fetchall()
        return [{"id": row[0], "type": row[1], "actor": row[2], "target_id": row[3],
                 "target_version": row[4], "data_source": row[5],
                 "evidence_refs": json.loads(row[6]), "data": json.loads(row[7]),
                 "timestamp": row[8]} for row in rows]

    def close(self) -> None:
        self.connection.close()


class _LabTools:
    def __init__(self, state: LabState, server: Any, target_version: str) -> None:
        self.state = state
        self.server = server
        self.target_version = target_version
        self.credentials: dict[str, str] = {}
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        self.executor = BoundedHttpExecutor(
            TargetRegistry([TargetSpec(BASE_TARGET, target_version, origin)]),
            self.credentials, RequestBudget(max_requests=64, timeout_seconds=3),
        )

    def new_session_sync(self, account_ref: str) -> str:
        grant = self.state.trusted_new_session(account_ref)
        self.credentials[grant.session_ref] = grant.token
        return grant.session_ref

    async def new_session(self, account_ref: str) -> str:
        return self.new_session_sync(account_ref)

    async def http_request(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self.executor.http_request(request)


class GuidedAccessControlRun:
    """Run the guided find/prove/defend/adapt/fix/retest scenario."""

    def __init__(self, store: AssessmentStore | None = None, assessment_id: str | None = None) -> None:
        self.store = store or AssessmentStore()
        self.assessment_id = assessment_id or f"guided-{uuid4().hex[:12]}"

    def run(self) -> dict[str, Any]:
        return asyncio.run(self._run())

    async def _run(self) -> dict[str, Any]:
        self.store.create_assessment(self.assessment_id, BASE_TARGET, BASE_VERSION)
        base_state = LabState()
        base_server = create_server(state=base_state)
        base_worker = Thread(target=base_server.serve_forever, daemon=True)
        base_worker.start()
        try:
            tools = _LabTools(base_state, base_server, BASE_VERSION)
            alice_ref = tools.new_session_sync("alice")
            bob_ref = tools.new_session_sync("bob")
            red_context = self._red_context({"alice": alice_ref, "bob": bob_ref})
            red_result = await run_red(red_context, tools)
            self.store.append(self.assessment_id, "red.completed", "red", BASE_TARGET, BASE_VERSION,
                              {"status": red_result["status"], "discoveries": red_result["discoveries"],
                               "candidates": red_result["candidates"], "request_count": red_result["request_count"]},
                              tuple(red_result.get("evidence_refs", ())))
            candidate = (red_result.get("candidates") or [None])[0]
            if not isinstance(candidate, Mapping):
                return self._finish("failed", BASE_VERSION, {"reason": "red produced no candidate"})

            referee = IndependentReferee()
            verification = await referee.verify(candidate, tools)
            self.store.append(self.assessment_id, "finding.verified", "referee", BASE_TARGET, BASE_VERSION,
                              verification, tuple(verification.get("evidence_refs", ())))
            if verification.get("verdict") != "verified":
                return self._finish("failed", BASE_VERSION, {"reason": "candidate was not verified"})

            defense_events: list[dict[str, Any]] = []
            first_blue = await self._observe(base_state, BASE_VERSION, defense_events)
            await self._apply_revocations(first_blue, defense_events, base_state, BASE_VERSION)

            fresh_alice = tools.new_session_sync("alice")
            adapted = await run_red(self._red_context({"alice": fresh_alice, "bob": bob_ref},
                                                       fresh={"alice": fresh_alice}), tools)
            self.store.append(self.assessment_id, "red.adapted", "red", BASE_TARGET, BASE_VERSION,
                              {"status": adapted["status"], "adaptation": adapted.get("adaptation"),
                               "candidates": adapted["candidates"], "request_count": adapted["request_count"]},
                              tuple(adapted.get("evidence_refs", ())))
            if adapted.get("adaptation", {}).get("outcome") != "still_exposed":
                return self._finish("failed", BASE_VERSION, {"reason": "adaptation did not reproduce exposure"})

            second_blue = await self._observe(base_state, BASE_VERSION, defense_events)
            await self._apply_revocations(second_blue, defense_events, base_state, BASE_VERSION)
            patched_state, patched_server, patched_worker = self._start_patched_target()
            try:
                patched_tools = _LabTools(patched_state, patched_server, PATCHED_VERSION)
                fallback = self._authorize_fallback(second_blue, first_blue)
                self.store.append(self.assessment_id, "patch.authorized", "system", BASE_TARGET,
                                  BASE_VERSION, fallback["data"])
                retest_candidate = dict(candidate)
                retest_candidate["target_version"] = PATCHED_VERSION
                patched_verification = await referee.verify(retest_candidate, patched_tools)
                checks = await self._regression_checks(patched_tools)
                retest = {"verdict": patched_verification.get("verdict"),
                          "referee": patched_verification, "checks": checks,
                          "all_checks_passed": all(checks.values())}
                self.store.append(self.assessment_id, "retest.completed", "referee", BASE_TARGET,
                                  PATCHED_VERSION, retest, tuple(patched_verification.get("evidence_refs", ())))
                if patched_verification.get("verdict") != "rejected" or not all(checks.values()):
                    return self._finish("failed", PATCHED_VERSION, {"reason": "retest regression failed"})
                return self._finish("completed", PATCHED_VERSION,
                                    {"finding": "verified", "adaptation": "still_exposed",
                                     "containment": "applied", "fix": "known_good_fallback",
                                     "retest": "verified"})
            finally:
                patched_server.shutdown()
                patched_worker.join(timeout=2)
                patched_server.server_close()
        finally:
            base_server.shutdown()
            base_worker.join(timeout=2)
            base_server.server_close()

    def _red_context(self, accounts: Mapping[str, str], fresh: Mapping[str, str] | None = None) -> dict[str, Any]:
        return {"assessment_id": self.assessment_id, "target_id": BASE_TARGET,
                "target_version": BASE_VERSION, "entry_path": "/", "account_refs": dict(accounts),
                "fresh_account_refs": dict(fresh or {}),
                "budgets": {"max_steps": 24, "max_requests": 48, "timeout_seconds": 3}}

    async def _observe(self, state: LabState, version: str, previous: list[dict[str, Any]]) -> dict[str, Any]:
        result = await observe({"target_id": BASE_TARGET, "target_version": version,
                                "data_source": DATA_SOURCE, "assessment_id": self.assessment_id,
                                "telemetry": state.trusted_telemetry(),
                                "access_policy": PRIVATE_ORDERS_POLICY,
                                "previous_defenses": previous,
                                "generated_at": _now()})
        for alert in result["alerts"]:
            self.store.append(self.assessment_id, "alert.created", "blue", BASE_TARGET, version,
                              alert, tuple(f"telemetry:{ref}" for ref in alert["request_ids"]))
        for proposal in result["defense_proposals"]:
            event = self._proposal_event(proposal, version)
            previous.append(event)
            self.store.append(self.assessment_id, "defense.proposed", "blue", BASE_TARGET, version,
                              proposal, tuple(f"telemetry:{ref}" for ref in proposal.get("alert_ids", ())))
        return result

    async def _apply_revocations(self, blue_result: Mapping[str, Any], previous: list[dict[str, Any]],
                                 state: LabState, version: str) -> None:
        proposals = [proposal for proposal in blue_result.get("defense_proposals", ())
                     if proposal.get("action_type") == "revoke_session"]
        for proposal in proposals:
            session_ref = proposal.get("parameters", {}).get("session_ref")
            applied = isinstance(session_ref, str) and state.trusted_revoke_session(session_ref)
            event = self.store.append(
                self.assessment_id, "defense.applied" if applied else "defense.failed", "system",
                BASE_TARGET, version,
                {"defense_id": proposal["defense_id"], "action_type": "revoke_session",
                 "origin": "policy_action", "original_version": version, "resulting_version": version}
                if applied else {"defense_id": proposal["defense_id"], "reason": "session reference unavailable"},
            )
            if applied:
                previous.append(event)

    def _authorize_fallback(self, *blue_results: Mapping[str, Any]) -> dict[str, Any]:
        patch = next((proposal for result in blue_results for proposal in result.get("defense_proposals", ())
                      if proposal.get("action_type") == "apply_patch"), None)
        if patch is None:
            raise RuntimeError("blue did not propose the ownership patch")
        return {"data": {"patch_id": "ownership-fix-001", "origin": "known_good_fallback",
                          "base_version": BASE_VERSION, "resulting_version": PATCHED_VERSION,
                          "source_proposal": patch["defense_id"]}}

    def _proposal_event(self, proposal: Mapping[str, Any], version: str) -> dict[str, Any]:
        return {"schema_version": "1.0", "id": f"proposal-{proposal['defense_id']}", "type": "defense.proposed", "actor": "blue",
                "assessment_id": self.assessment_id, "target_id": BASE_TARGET,
                "target_version": version, "data_source": DATA_SOURCE,
                "evidence_refs": [], "data": dict(proposal), "timestamp": _now()}

    async def _regression_checks(self, tools: _LabTools) -> dict[str, bool]:
        alice = tools.new_session_sync("alice")
        bob = tools.new_session_sync("bob")
        checks = {}
        checks["alice_cross_user_denied"] = (await self._get(tools, "/api/orders/204", alice))["status"] == 403
        checks["bob_owner_allowed"] = (await self._get(tools, "/api/orders/204", bob))["status"] == 200
        checks["alice_owner_allowed"] = (await self._get(tools, "/api/orders/101", alice))["status"] == 200
        checks["anonymous_denied"] = (await self._get(tools, "/api/orders/204", None))["status"] == 401
        checks["protected_control_unchanged"] = (await self._get(tools, "/api/secure-orders/204", bob))["status"] == 200
        return checks

    @staticmethod
    async def _get(tools: _LabTools, path: str, credential_ref: str | None) -> Mapping[str, Any]:
        return await tools.http_request({"target_id": BASE_TARGET, "target_version": tools.target_version,
                                         "method": "GET", "path": path, "credential_ref": credential_ref,
                                         "request_id": f"retest-{uuid4().hex[:10]}"})

    def _start_patched_target(self):
        state = LabState(target_version=PATCHED_VERSION, policy_module=patched_policy)
        server = create_server(state=state)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        return state, server, worker

    def _finish(self, status: str, version: str, summary: Mapping[str, Any]) -> dict[str, Any]:
        self.store.set_status(self.assessment_id, status, version)
        self.store.append(self.assessment_id, "assessment.completed", "system", BASE_TARGET, version,
                          {"status": status, **dict(summary)})
        return {"assessment_id": self.assessment_id, "status": status, "target_id": BASE_TARGET,
                "target_version": version, "data_source": DATA_SOURCE,
                "summary": dict(summary), "events": self.store.events(self.assessment_id)}


def run_guided_access_control(path: str = ":memory:", assessment_id: str | None = None) -> dict[str, Any]:
    store = AssessmentStore(path)
    try:
        return GuidedAccessControlRun(store, assessment_id).run()
    finally:
        store.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
