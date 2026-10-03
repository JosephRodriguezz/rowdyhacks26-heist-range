"""Typed fixture traces exercise workflow, not remote model performance."""

from __future__ import annotations

import json
import queue
import threading
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from red.prototype.agents import AgentWorker
from red.prototype.board import BudgetLedger, RedBoard
from red.prototype.domain import API_BODY_FIELDS, ActionProposal, AgentStep, Evidence, HypothesisUpdate, RunLimits
from red.prototype.providers import HYPOTHESIS_SCHEMA, ProviderError, parse_step
from red.prototype.replay import ReplayError, load_recorded_trace
from red.prototype.runner import PrototypeRunner, RunOptions


def typed_step(kind, *, action=None, update=None, rationale="Review the observed result.", refs=(), key=""):
    value = {
        "kind": kind, "rationale": rationale, "hypothesis": update.statement if update else "",
        "candidate_key": key, "evidence_refs": list(refs),
        "hypothesis_update": asdict(update) if update else None,
        "action": asdict(action) if action else None,
    }
    if action:
        value["action"]["body"] = {name: action.body.get(name) for name in API_BODY_FIELDS}
    return parse_step(json.loads(json.dumps(value)))


class ComparisonFixtureProvider:
    label = "test_fixture_hypothesis_workflow"
    key = "profile name persistence"

    def __init__(self):
        self.turns = {"scout": 0, "operator": 0}
        self.contexts = []
        self.baseline = None
        self.comparison = None

    @staticmethod
    def latest(context, predicate):
        return next(item for item in reversed(context["evidence"]) if predicate(item))

    def propose(self, *, role, context, system_prompt, timeout):
        self.contexts.append(context)
        turn = self.turns[role]
        self.turns[role] += 1
        if role == "scout":
            if turn == 0:
                return typed_step("act", action=ActionProposal("read_page"))
            if turn == 1:
                entry = self.latest(context, lambda ev: ev["path"] == "/")
                update = HypothesisUpdate(
                    "create", self.key, statement="An ordinary profile name update can be observed in account responses.",
                    expected_result="After setting the name to Review name, the response shows Review name with the same username.",
                    evidence_refs=(entry["evidence_id"],), assessment="The public entry links to ordinary profile behavior.",
                )
                return typed_step(
                    "handoff", update=update, action=ActionProposal("request_api", path="/api/profile"),
                    rationale="Does a normal profile update produce its predicted account effect?", refs=update.evidence_refs, key=self.key,
                )
            return typed_step("finished")

        candidate = next(item for item in context["hypotheses"] if item["candidate_key"] == self.key)
        revision = candidate["revision"]
        if turn in (0, 9):
            return typed_step("act", action=ActionProposal("start_account_session", identity_ref="account_b"))
        session = self.latest(context, lambda ev: ev["role"] == "operator" and ev["capability"] == "start_account_session")["session_ref"]
        if turn in (1, 5, 10):
            return typed_step("act", action=ActionProposal("request_api", path="/api/profile", session_ref=session))
        if turn in (2, 4, 11):
            if turn == 2:
                self.baseline = self.latest(context, lambda ev: ev["path"] == "/api/profile" and ev["method"] == "GET")["evidence_id"]
            return typed_step("act", action=ActionProposal(
                "request_api", path="/api/profile", method="POST", session_ref=session,
                body={"name": "Intervening name" if turn == 4 else "Review name"},
            ))
        if turn in (3, 7, 12):
            if turn == 3:
                self.comparison = self.latest(context, lambda ev: ev["path"] == "/api/profile" and ev["method"] == "POST")["evidence_id"]
            baseline, comparison = self.baseline, self.comparison
            if turn == 12:
                baseline = self.latest(context, lambda ev: ev["path"] == "/api/profile" and ev["method"] == "GET" and ev["session_ref"] == session)["evidence_id"]
                comparison = self.latest(context, lambda ev: ev["path"] == "/api/profile" and ev["method"] == "POST" and ev["session_ref"] == session)["evidence_id"]
            if turn != 7:
                before = json.loads(next(ev["body"] for ev in context["evidence"] if ev["evidence_id"] == baseline))
                after = json.loads(next(ev["body"] for ev in context["evidence"] if ev["evidence_id"] == comparison))
                if after["name"] != "Review name" or before["username"] != after["username"] or before["name"] == after["name"]:
                    raise AssertionError("fixture comparison did not demonstrate the expected ordinary-account effect")
            return typed_step("update_hypothesis", update=HypothesisUpdate(
                "assess", self.key, status="supported", baseline_evidence_ref=baseline,
                comparison_evidence_ref=comparison, changed_condition="profile name input",
                assessment="The ordinary baseline and altered-name response show the same username and the predicted display name.",
                expected_revision=revision,
            ))
        if turn == 6:
            changed = self.latest(context, lambda ev: ev["path"] == "/api/profile" and ev["method"] == "GET")
            return typed_step("update_hypothesis", update=HypothesisUpdate(
                "reopen", self.key, evidence_refs=(changed["evidence_id"],), expected_revision=revision,
                assessment="The display value has changed since the comparison. Preserve the earlier result and retest current state.",
            ))
        if turn == 8:
            return typed_step("act", action=ActionProposal("end_account_session", session_ref=session))
        return typed_step("finished")


class HypothesisAgentTests(unittest.TestCase):
    def test_rejected_operator_handoff_cannot_commit_an_assessment(self):
        class RejectedHandoffFixture(ComparisonFixtureProvider):
            handoff_attempted = False

            def propose(self, *, role, **kwargs):
                if role == "operator" and self.handoff_attempted:
                    return typed_step("finished")
                step = super().propose(role=role, **kwargs)
                if role == "operator" and self.turns[role] == 4:
                    self.handoff_attempted = True
                    return replace(step, kind="handoff", candidate_key=self.key, action=ActionProposal("read_page"))
                return step

        report = PrototypeRunner(RunOptions(scenario_id="clean", mode="model"), provider=RejectedHandoffFixture()).run()
        self.assertEqual(report.failures, [])
        self.assertEqual(report.hypotheses[0]["status"], "inconclusive")
        self.assertEqual(report.hypotheses[0]["revision"], 1)
        self.assertEqual([item["operation"] for item in report.hypotheses[0]["history"]], ["create"])
        self.assertEqual(report.budget["actions_used"], 4)
        self.assertTrue(any(item["failure_kind"] == "policy_denial" for item in report.evidence_records))

    def test_typed_trace_assesses_reopens_and_requires_fresh_comparison(self):
        provider = ComparisonFixtureProvider()
        report = PrototypeRunner(RunOptions(
            scenario_id="clean", mode="model", limits=RunLimits(
                action_calls=20, model_calls=24, wall_seconds=10, request_timeout_seconds=1,
                model_timeout_seconds=1, max_agent_turns=18,
            ),
        ), provider=provider).run().to_dict()
        self.assertEqual(report["failures"], [])
        self.assertEqual(len(report["hypotheses"]), 1)
        candidate = report["hypotheses"][0]
        self.assertEqual(candidate["status"], "supported")
        self.assertEqual([item["operation"] for item in candidate["history"]], ["create", "assess", "reopen", "assess"])
        self.assertEqual([item["status"] for item in candidate["history"]], ["inconclusive", "supported", "inconclusive", "supported"])
        self.assertTrue(any("fresh baseline" in item["summary"] for item in report["evidence_records"] if item["failure_kind"] == "policy_denial"))
        self.assertNotEqual(candidate["history"][1]["baseline_evidence_ref"], candidate["history"][3]["baseline_evidence_ref"])
        self.assertNotEqual(candidate["history"][1]["comparison_evidence_ref"], candidate["history"][3]["comparison_evidence_ref"])
        self.assertEqual(report["handoffs"][0]["expected_result"], candidate["expected_result"])
        self.assertEqual(report["handoffs"][0]["hypothesis_id"], candidate["hypothesis_id"])
        revision = next(event for event in report["events"] if event.get("revision_kind") == "assessment_reopened")
        self.assertEqual(revision["hypothesis_id"], candidate["hypothesis_id"])
        self.assertEqual(revision["evidence_refs"], candidate["history"][2]["evidence_refs"])
        self.assertEqual(revision["to"], "inconclusive")
        self.assertTrue(any(event["event_type"] == "action.observed" and event["action_count"] > revision["action_count"] for event in report["events"]))
        operator_context = next(ctx for ctx in provider.contexts if ctx["role"] == "operator")
        self.assertEqual(operator_context["evidence_backed_candidate"]["hypothesis"]["expected_result"], candidate["expected_result"])
        self.assertEqual(report["budget"]["actions_used"], 10)
        # A supported account-behavior hypothesis cannot set mission success.
        self.assertEqual(report["verdict"], "not_achieved")
        self.assertEqual(report["evidence_refs"], [])
        serialized = json.dumps(provider.contexts)
        self.assertNotIn("scenario_id", serialized)
        self.assertNotIn("target_reads", serialized)
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "run.json"
            saved.write_text(json.dumps(report), encoding="utf-8")
            replay = load_recorded_trace(saved)
        self.assertEqual(replay["hypotheses"], report["hypotheses"])
        self.assertEqual(replay["source_mode"], "recorded_replay")
        self.assertNotIn("target_reads", json.dumps(replay))

    def test_invalid_hypothesis_update_prevents_accompanying_target_action(self):
        class InvalidFixture:
            label = "test_fixture_invalid_assessment"
            turn = 0

            def propose(self, *, context, **kwargs):
                self.turn += 1
                if self.turn == 1:
                    return typed_step("act", action=ActionProposal("read_page"))
                if self.turn == 2:
                    update = HypothesisUpdate(
                        "create", "unsupported claim", statement="A public route proves vault access.",
                        expected_result="Protected content is returned.", status="supported",
                        evidence_refs=(context["evidence"][0]["evidence_id"],), assessment="Claim before a comparison.",
                    )
                    return typed_step("act", update=update, action=ActionProposal("read_page", path="/api/catalog"))
                return typed_step("finished")

        report = PrototypeRunner(RunOptions(scenario_id="clean", mode="model"), provider=InvalidFixture()).run()
        self.assertEqual(report.budget["actions_used"], 1)
        self.assertEqual(report.hypotheses, [])
        self.assertTrue(any(item["failure_kind"] == "policy_denial" for item in report.evidence_records))

    def test_cancellation_during_proposal_prevents_late_candidate_creation(self):
        cancel = threading.Event()
        board = RedBoard()
        task = board.add_task("scout", "explore")
        board.add_evidence(Evidence("entry", 0, "scout", "read_page", "GET", "/", 200, "public", "{}"))

        class LateFixture:
            def propose(self, **kwargs):
                cancel.set()
                return typed_step("update_hypothesis", update=HypothesisUpdate(
                    "create", "late", statement="Late proposal.", expected_result="An observable result.",
                    evidence_refs=("entry",), assessment="Returned after stop.",
                ))

        limits = RunLimits()
        worker = AgentWorker(
            role="scout", task_id=task.task_id, provider=LateFixture(), executor=object(), board=board,
            budget=BudgetLedger(limits, cancel), limits=limits, operator_queue=queue.Queue(), stop_event=cancel,
            evaluate_after_action=lambda: False, failures=[], failure_lock=threading.Lock(), scout_done_event=threading.Event(),
        )
        worker.run()
        self.assertEqual(board.hypotheses(), [])

    def test_provider_context_never_receives_foreign_run_content(self):
        board = RedBoard()
        task = board.add_task("scout", "explore")
        board.add_evidence(Evidence("foreign", 0, "scout", "read_page", "GET", "/", 200,
                                    "another run", "foreign-run-private-marker", session_id="another-run"))
        limits = RunLimits()
        cancel = threading.Event()
        worker = AgentWorker(
            role="scout", task_id=task.task_id, provider=object(), executor=object(), board=board,
            budget=BudgetLedger(limits, cancel), limits=limits, operator_queue=queue.Queue(), stop_event=cancel,
            evaluate_after_action=lambda: False, failures=[], failure_lock=threading.Lock(), scout_done_event=threading.Event(),
        )
        self.assertNotIn("foreign-run-private-marker", json.dumps(worker._build_context(task.task_id, None)))


class HypothesisSchemaTests(unittest.TestCase):
    def test_replay_rejects_malformed_hypothesis_records(self):
        for hypotheses in ({"status": "supported"}, ["not an object"]):
            with self.subTest(hypotheses=hypotheses), tempfile.TemporaryDirectory() as directory:
                saved = Path(directory) / "run.json"
                saved.write_text(json.dumps({"events": [], "evidence_records": [], "hypotheses": hypotheses}), encoding="utf-8")
                with self.assertRaises(ReplayError):
                    load_recorded_trace(saved)

    def test_schema_and_parser_cover_bounded_structured_updates(self):
        self.assertEqual(set(HYPOTHESIS_SCHEMA["properties"]), set(HypothesisUpdate.__dataclass_fields__))
        update = HypothesisUpdate("create", "candidate", statement="A narrow hypothesis.",
                                  expected_result="An observable effect.", evidence_refs=("ev",), assessment="Observed behavior warrants testing.")
        step = typed_step("update_hypothesis", update=update)
        self.assertEqual(step.hypothesis_update, update)
        with self.assertRaises(ProviderError):
            typed_step("update_hypothesis", update=update, action=ActionProposal("read_page"))
        for operation in ("assess", "reopen"):
            with self.subTest(operation=operation), self.assertRaises(ProviderError):
                typed_step("act", update=replace(update, operation=operation), action=ActionProposal("read_page"))
        for change in ({"expected_revision": True}, {"status": "verified"}, {"evidence_refs": (None,)}, {"statement": "x" * 801}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(update, **change)
        value = asdict(update)
        value["evidence_refs"] = ["ev"]
        value["arbitrary_instruction"] = "widen permissions"
        with self.assertRaises(ValueError):
            HypothesisUpdate.from_mapping(value)


if __name__ == "__main__":
    unittest.main()
