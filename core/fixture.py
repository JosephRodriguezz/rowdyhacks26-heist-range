"""Scripted integration decisions; not an adaptive-model performance baseline.

Runs through the real Scout/Operator workers, using only their observed context.
No seed, target state, scenario answer, Blue plan, or referee record is available.
"""

import json
import threading

from red.prototype.domain import ActionProposal, AgentStep, HypothesisUpdate


class IntegrationFixtureProvider:
    label = "scripted_integration_fixture"

    def __init__(self):
        self.lock = threading.Lock()
        self.turns = {"scout": 0, "operator": 0}
        self.old_session = None
        self.baseline, self.comparison = None, None
        self.initial_supported = False

    def propose(self, *, role, context, system_prompt, timeout):
        with self.lock:
            turn = self.turns[role]
            self.turns[role] += 1
            evidence = context["evidence"]
            own = [e for e in evidence if e["role"] == role]
            def latest(capability=None, path=None):
                return next(e for e in reversed(own)
                            if (capability is None or e["capability"] == capability)
                            and (path is None or e["path"] == path))
            def act(capability, **kwargs):
                return AgentStep("act", "Labeled integration fixture comparison.", "", ActionProposal(capability, **kwargs))
            def session():
                return latest("start_account_session")["session_ref"]
            def record_ids():
                catalog = next(e for e in evidence if e["path"] == "/api/catalog")
                records = json.loads(catalog["body"])["records"]
                profile = json.loads(latest(path="/api/profile")["body"])
                username = profile["username"]
                return (next(r["record_id"] for r in records if r["owner"] == username),
                        next(r["record_id"] for r in records if r["owner"] != username))
            key = "owner-only-bank-record-comparison"
            if role == "scout":
                if turn == 0:
                    return act("read_page", path="/")
                if turn == 1:
                    return act("read_page", path="/api/catalog")
                if turn == 2:
                    return act("start_account_session", identity_ref="account_b")
                if turn == 3:
                    return act("read_page", path="/api/profile", session_ref=session())
                if turn == 4:
                    refs = tuple(e["evidence_id"] for e in own if e["path"] in ("/api/catalog", "/api/profile"))
                    return AgentStep(
                        "handoff", "Compare ordinary own-record access with a different owner's record.", "",
                        ActionProposal("start_account_session", identity_ref="account_a"),
                        key, refs, HypothesisUpdate(
                            "create", key, "A current ordinary session may read a different owner's bank record.",
                            "The controlled cross-owner response contains that other record's private content.", refs,
                            assessment="Public catalog and ordinary profile observations suggest a controlled owner comparison.",
                        ),
                    )
                return AgentStep("finished", "Fixture surface survey and handoff finished.", "")
            if turn == 0:
                return act("start_account_session", identity_ref="account_a")
            if turn == 1:
                return act("read_page", path="/api/profile", session_ref=session())
            own_id, other_id = record_ids()
            if turn == 2:
                self.old_session = session()
                return act("read_page", path="/api/records/" + own_id, session_ref=session())
            if turn == 3:
                self.baseline = latest(path="/api/records/" + own_id)["evidence_id"]
                return act("read_page", path="/api/records/" + other_id, session_ref=session())
            hypothesis = next(h for h in context["hypotheses"] if h["candidate_key"] == key)
            if turn in (4, 10):
                comparison = latest(path="/api/records/" + other_id)
                self.comparison = comparison["evidence_id"]
                self.initial_supported = comparison["status"] == 200 and "content" in json.loads(comparison["body"])
                status = "supported" if self.initial_supported else "rejected" if comparison["status"] == 403 else "inconclusive"
                return AgentStep("update_hypothesis", "Fixture compares observed content with the prediction.", "",
                    evidence_refs=(self.baseline, self.comparison), hypothesis_update=HypothesisUpdate(
                        "assess", key, evidence_refs=(self.baseline, self.comparison), status=status,
                        baseline_evidence_ref=self.baseline, comparison_evidence_ref=self.comparison,
                        changed_condition="record reference changed from own record to the other owner's record",
                        assessment="Own-record baseline succeeded; comparison " + ("returned the other owner's content." if status == "supported" else "did not establish the predicted private-data effect."),
                        expected_revision=hypothesis["revision"],
                    ))
            if not self.initial_supported:
                return AgentStep("finished", "Fixture comparison did not support access; no containment assumed.", "")
            if turn == 5:
                return act("read_page", path="/api/records/" + other_id, session_ref=self.old_session)
            if turn == 6:
                observation = latest(path="/api/records/" + other_id)
                return AgentStep("update_hypothesis", "Changed response requires a fresh comparison, not a fix claim.", "",
                    evidence_refs=(observation["evidence_id"],), hypothesis_update=HypothesisUpdate(
                        "reopen", key, evidence_refs=(observation["evidence_id"],),
                        assessment="The earlier session now returns a denial. Cause and lasting protection remain unproven.",
                        expected_revision=hypothesis["revision"],
                    ))
            if turn == 7:
                return act("start_account_session", identity_ref="account_a")
            if turn == 8:
                return act("read_page", path="/api/records/" + own_id, session_ref=session())
            if turn == 9:
                self.baseline = latest(path="/api/records/" + own_id)["evidence_id"]
                return act("read_page", path="/api/records/" + other_id, session_ref=session())
            return AgentStep("finished", "Fixture fresh-session comparison finished; referee determines outcomes.", "")
