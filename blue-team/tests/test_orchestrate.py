"""End-to-end orchestration with fake model CLIs. No real model is called.
Run from the repository root: python -m unittest discover -s blue-team/tests -v
"""

import json
import unittest

from sandbox import Sandbox


class FlowTest(unittest.TestCase):
    models = ("claude", "codex", "antigravity")

    def setUp(self):
        self.box = Sandbox(self.models)
        self.addCleanup(self.box.close)

    def ok(self, *args, **env):
        result = self.box.orchestrate(*args, **env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def stopped(self, *args, **env):
        result = self.box.orchestrate(*args, **env)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        return result

    def refused(self, *args, **env):
        result = self.box.orchestrate(*args, **env)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        return result

    def to_accepted(self, **env):
        self.ok("plan", "B-90", **env)
        self.ok("decide", "B-90", **env)

    def to_implemented(self, **env):
        self.to_accepted()
        self.ok("approve", "B-90", "--note", "go")
        self.ok("implement", "B-90", **env)

    def escalation(self):
        st = self.box.state()
        self.assertEqual(st["phase"], "needs_human")
        return st["needs_human"]


class HappyPath(FlowTest):
    def test_full_flow_closes_only_after_the_human_commits(self):
        self.ok("plan", "B-90")
        thread = self.box.thread()
        for model in self.models:
            self.assertIn(f"| {model} | proposal", thread)
        self.assertIn("Recorded by the orchestrator: run", thread)
        last_prompt = next((self.box.root / "blue-team/runs").rglob("B-90-propose-antigravity.prompt.md"))
        self.assertNotIn("claude plan", last_prompt.read_text(encoding="utf-8"))

        self.ok("decide", "B-90")
        st = self.box.state()
        self.assertEqual((st["phase"], st["decision"]["implementer"]), ("accepted", "codex"))
        record = (self.box.root / st["decision"]["record"]).read_text(encoding="utf-8")
        for model in self.models:
            self.assertIn(f"| {model} | agree |", record)
        self.assertIn("Facilitator summary (not a vote)", record)

        self.assertIn("No human approval", self.refused("implement", "B-90").stderr)
        self.ok("approve", "B-90", "--note", "looks right")
        self.ok("implement", "B-90")
        self.assertTrue((self.box.root / "backend/app/agents/blue/feature.py").exists())
        self.ok("review", "B-90")
        self.assertEqual(self.box.state()["phase"], "ready_to_close")
        calls = self.box.calls()
        self.assertIn("codex implement write", calls)
        self.assertEqual(sorted(c for c in calls if " review " in c), ["antigravity review read", "claude review read"])
        self.assertFalse([c for c in calls if c.endswith("write") and not c.startswith("codex implement")])

        before = self.box.head()
        self.ok("close", "B-90")
        self.assertEqual(self.box.head(), before)
        self.ok("close", "B-90", "--commit")
        self.assertNotEqual(self.box.head(), before)
        message = self.box.git("log", "-1", "--format=%B").stdout
        for trailer in ("[B-90] Sample task", "Implemented-by: codex", "Reviewed-by: antigravity, claude",
                        "Decision-SHA256:", "Implementation-approved-by: human", "Checks-passed: ok"):
            self.assertIn(trailer, message)
        files = self.box.git("show", "--name-only", "--format=", "HEAD").stdout.split()
        self.assertIn("backend/app/agents/blue/feature.py", files)
        self.assertIn("blue-team/state/B-90.json", files)
        self.assertNotIn("README.md", files)
        self.assertEqual(self.box.git("status", "--porcelain").stdout.strip(), "")
        self.assertEqual(self.box.state()["phase"], "closed")
        self.assertEqual(self.box.tasks()["B-90"]["status"], "done")
        self.assertEqual(self.box.script("guard.py", "verify").returncode, 0)

    def test_majority_without_security_objection_progresses(self):
        self.ok("plan", "B-90")
        self.ok("decide", "B-90", FAKE_ANTIGRAVITY="object")
        self.assertIn("2 of 3 votes agree", self.box.state()["decision"]["rule"])

    def test_changes_requested_need_a_new_human_approval(self):
        self.to_implemented()
        self.ok("review", "B-90", FAKE_ANTIGRAVITY="changes")
        self.assertEqual(self.box.state()["phase"], "changes_requested")
        self.refused("implement", "B-90")
        self.ok("approve", "B-90")
        self.ok("implement", "B-90")
        self.assertIn("codex revise write", self.box.calls())
        self.ok("review", "B-90")
        self.assertEqual(self.box.state()["phase"], "ready_to_close")

    def test_strategy_round_posts_each_model(self):
        self.ok("strategy")
        self.assertEqual(self.box.thread("strategy").count("| strategy"), 3)


class HumanGates(FlowTest):
    def test_dry_run_calls_no_model_and_writes_nothing(self):
        status = ["status", "--porcelain", "--untracked-files=all", "--ignored=matching"]
        before = self.box.git(*status).stdout
        result = self.ok("auto", "B-90", "--dry-run")
        for text in ("Planned phases", "Expected reviewers", "Writable during implementation", "no model was called"):
            self.assertIn(text, result.stdout)
        self.assertEqual(self.box.calls(), [])
        self.assertEqual(self.box.git(*status).stdout, before)
        self.assertIsNone(self.box.state())

    def test_implementation_cannot_begin_without_the_human_gate(self):
        self.to_accepted()
        self.refused("implement", "B-90")
        waiting = self.ok("auto", "B-90")
        self.assertIn("Waiting for your approval", waiting.stdout)
        self.assertEqual(self.box.state()["phase"], "accepted")
        self.assertFalse([c for c in self.box.calls() if c.endswith("write")])
        self.assertFalse((self.box.root / "backend/app/agents/blue/feature.py").exists())


class Decisions(FlowTest):
    def test_security_objection_stops_and_only_the_human_can_accept(self):
        self.ok("plan", "B-90")
        self.stopped("decide", "B-90", FAKE_ANTIGRAVITY="security")
        self.assertEqual(self.escalation()["reason"], "security-objection")
        record = (self.box.root / self.box.state()["decision"]["record"]).read_text(encoding="utf-8")
        self.assertIn("- antigravity on B-90: antigravity says security-objection", record)
        self.assertIn("B-90: security-objection", self.ok("escalations").stdout)
        self.refused("approve", "B-90")
        self.refused("resolve", "B-90", "accept")
        self.ok("resolve", "B-90", "accept", "--note", "I reviewed the objection; it does not apply here")
        st = self.box.state()
        self.assertEqual(st["phase"], "accepted")
        human_record = (self.box.root / st["decision"]["record"]).read_text(encoding="utf-8")
        self.assertIn("over a recorded security objection", human_record)

    def test_review_security_objection_can_be_sent_back_for_revision(self):
        self.to_implemented()
        self.refused("resolve", "B-90", "revise", "--note", "too early")
        self.stopped("review", "B-90", FAKE_CLAUDE="review-security")
        self.assertEqual(self.escalation()["reason"], "security-objection")
        self.refused("resolve", "B-90", "accept", "--note", "not a vote")
        self.ok("resolve", "B-90", "revise", "--note", "the objection is valid")
        self.assertEqual(self.box.state()["phase"], "changes_requested")
        self.assertIn("No human approval", self.refused("implement", "B-90").stderr)
        self.ok("approve", "B-90")
        self.ok("implement", "B-90")
        self.assertIn("codex revise write", self.box.calls())
        prompt = next((self.box.root / "blue-team/runs").rglob("B-90-revise-codex.prompt.md")).read_text(encoding="utf-8")
        self.assertIn("Reviews to address", prompt)
        self.assertIn("security-objection", prompt)

    def test_malformed_vote_fails_closed(self):
        self.ok("plan", "B-90")
        self.stopped("decide", "B-90", FAKE_CODEX="malformed")
        self.assertEqual(self.escalation()["reason"], "malformed-output")

    def test_malformed_or_mismatched_proposal_fails_closed(self):
        self.stopped("plan", "B-90", FAKE_CLAUDE="wrongtask")
        self.assertEqual(self.escalation()["reason"], "malformed-output")


class TwoModels(FlowTest):
    models = ("claude", "codex")

    def test_tie_escalates(self):
        self.ok("plan", "B-90")
        self.stopped("decide", "B-90", FAKE_CODEX="object")
        self.assertEqual(self.escalation()["reason"], "tie")


class Availability(FlowTest):
    def test_unavailable_cli_is_recorded_and_too_few_reviewers_escalate(self):
        self.box.config["models"]["antigravity"]["executable"] = [str(self.box.base / "missing" / "agy.exe")]
        self.box.save_config()
        doctor = self.box.orchestrate("doctor")
        self.assertIn("NOT INSTALLED", doctor.stdout)
        self.to_implemented()
        self.assertIn("antigravity", self.box.state()["unavailable"]["propose"])
        result = self.stopped("review", "B-90")
        self.assertIn("1 independent reviewers available", result.stderr)
        st = self.box.state()
        self.assertEqual(st["needs_human"]["reason"], "insufficient-reviewers")
        self.assertIn("antigravity", st["unavailable"]["review-1"])
        self.assertFalse([c for c in self.box.calls() if c.startswith("antigravity")])

    def test_failed_model_call_is_not_counted(self):
        self.ok("plan", "B-90")
        self.stopped("decide", "B-90", FAKE_CODEX="fail", FAKE_ANTIGRAVITY="fail")
        self.assertEqual(self.escalation()["reason"], "no-quorum")
        self.assertIn("could not be run", self.box.thread())


class WriteBoundaries(FlowTest):
    def test_writes_outside_allowed_paths_stop_the_task(self):
        cases = {"outside": "README.md", "protected": "backend/app/agents/blue/AGENTS.md",
                 "orchestrator-file": "blue-team/roles/codex.md"}
        for flag, path in cases.items():
            with self.subTest(flag=flag):
                box = Sandbox(self.models)
                self.addCleanup(box.close)
                self.box = box
                self.to_accepted()
                self.ok("approve", "B-90")
                result = self.stopped("implement", "B-90", FAKE_CODEX=flag)
                self.assertIn(path, result.stderr)
                self.assertEqual(self.escalation()["reason"], "unexpected-change")
                self.ok("resolve", "B-90", "retry", "--note", "reverted the stray change")
                self.assertIn("No human approval", self.refused("implement", "B-90").stderr)

    def test_model_branch_switch_is_detected(self):
        self.to_accepted()
        self.ok("approve", "B-90")
        result = self.stopped("implement", "B-90", FAKE_CODEX="switch")
        self.assertIn("branch changed from Mayo to rogue", result.stderr)
        self.assertIn("Switch to Mayo", self.refused("plan", "B-90").stderr)

    def test_model_commit_is_detected(self):
        self.to_accepted()
        self.ok("approve", "B-90")
        result = self.stopped("implement", "B-90", FAKE_CODEX="commit")
        self.assertIn("HEAD moved", result.stderr)

    def test_reviewer_cannot_modify_files(self):
        self.to_implemented()
        self.stopped("review", "B-90", FAKE_CLAUDE="reviewer-write")
        self.assertEqual(self.escalation()["reason"], "reviewer-modified-files")

    def test_self_review_is_rejected(self):
        self.to_implemented()
        self.assertIn("cannot review", self.refused("review", "B-90", "--models", "codex,claude").stderr)

    def test_unparseable_implementation_report_fails_closed(self):
        self.to_accepted()
        self.ok("approve", "B-90")
        self.stopped("implement", "B-90", FAKE_CODEX="malformed")
        self.assertEqual(self.escalation()["reason"], "malformed-output")


class Closure(FlowTest):
    def test_failed_checks_prevent_closure(self):
        self.to_implemented()
        before = self.box.head()
        self.stopped("review", "B-90", FAKE_CHECK_FAIL="1")
        self.assertEqual(self.escalation()["reason"], "checks-failed")
        self.refused("close", "B-90", "--commit")
        self.assertEqual(self.box.head(), before)

    def test_close_commits_files_from_every_attempt(self):
        self.to_implemented()
        self.ok("review", "B-90", FAKE_ANTIGRAVITY="changes")
        self.ok("approve", "B-90")
        self.ok("implement", "B-90", FAKE_CODEX="nochange,other")
        self.ok("review", "B-90")
        self.ok("close", "B-90", "--commit")
        files = self.box.git("show", "--name-only", "--format=", "HEAD").stdout.split()
        self.assertIn("backend/app/agents/blue/feature.py", files)
        self.assertIn("backend/app/agents/blue/other.py", files)
        self.assertEqual(self.box.git("status", "--porcelain").stdout.strip(), "")

    def test_files_changed_after_checks_block_close(self):
        self.to_implemented()
        self.ok("review", "B-90")
        self.box.write("backend/app/agents/blue/feature.py", "# edited after checks\n")
        self.assertIn("changed after the checks", self.refused("close", "B-90", "--commit").stderr)

    def test_interrupted_run_fails_closed(self):
        self.box.write("blue-team/state/B-90.json", json.dumps({
            "task": "B-90", "schema": 1, "phase": "proposing", "round": 1, "attempt": 0, "needs_human": None,
            "unavailable": {}, "proposals": {}, "draft": None, "votes": {}, "decision": None, "approvals": [],
            "implementation": None, "reviews": {}, "checks": None, "history": []}))
        self.stopped("plan", "B-90")
        self.assertEqual(self.escalation()["reason"], "interrupted-run")


class Doctor(FlowTest):
    def test_statuses_and_live_probe(self):
        self.box.config["models"]["antigravity"]["auth_command"] = None
        self.box.save_config()
        result = self.ok("doctor", "--live")
        self.assertIn("READY          claude", result.stdout)
        self.assertIn("WARNING        antigravity", result.stdout)
        self.assertIn("read-only write blocked", result.stdout)
        leaky = self.box.orchestrate("doctor", "--live", FAKE_CODEX="probe-write")
        self.assertEqual(leaky.returncode, 1)
        self.assertIn("codex read-only mode was NOT enforced", leaky.stdout)
        self.assertFalse((self.box.root / "backend/app/agents/blue/.doctor-probe").exists())

    def test_denied_write_without_reply_is_a_warning_not_ready(self):
        result = self.box.orchestrate("doctor", "--live", FAKE_ANTIGRAVITY="denied")
        self.assertIn("WARNING        antigravity live call: the write was blocked", result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_signed_out_cli_is_misconfigured(self):
        result = self.box.orchestrate("doctor", FAKE_CODEX="signed-out")
        self.assertIn("MISCONFIGURED  codex", result.stdout)
        self.assertIn("not signed in", result.stdout)


if __name__ == "__main__":
    unittest.main()
