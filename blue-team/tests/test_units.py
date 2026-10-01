"""Unit tests: state machine rules, reply parsing, adapters, and repository snapshots.
Run from the repository root: python -m unittest discover -s blue-team/tests -v
"""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from sandbox import FAKE_MODEL  # also puts blue-team/bin on sys.path

import adapters
from common import load_config
import replies
import state as sm
import watch


class VoteRules(unittest.TestCase):
    def evaluate(self, *stances, malformed=(), quorum=2):
        votes = dict(zip(("claude", "codex", "antigravity"), stances))
        return sm.evaluate_votes(votes, list(malformed), quorum)

    def test_majority_without_security_objection_is_accepted(self):
        self.assertEqual(self.evaluate("agree", "agree", "object")["status"], "accepted")
        self.assertEqual(self.evaluate("agree", "agree", "abstain")["status"], "accepted")

    def test_security_objection_always_escalates(self):
        result = self.evaluate("agree", "agree", "security-objection")
        self.assertEqual((result["status"], result["reason"]), ("needs_human", "security-objection"))
        self.assertEqual(result["security_objections"], ["antigravity"])

    def test_tie_escalates(self):
        self.assertEqual(self.evaluate("agree", "object")["reason"], "tie")

    def test_quorum_majority_objection_and_malformed(self):
        self.assertEqual(self.evaluate("agree", "abstain", "abstain")["reason"], "no-quorum")
        self.assertEqual(self.evaluate("agree", "object", "object")["reason"], "majority-objection")
        self.assertEqual(self.evaluate("agree", "agree", malformed=["antigravity"])["reason"], "malformed-output")
        with self.assertRaises(sm.StateError):
            self.evaluate("agree", "maybe")

    def test_implementer_selection_is_deterministic(self):
        tiebreak = ["codex", "claude", "antigravity"]
        self.assertEqual(sm.select_implementer({"a": "claude", "b": "claude", "c": "codex"},
                                               ["claude", "codex"], tiebreak)[0], "claude")
        self.assertEqual(sm.select_implementer({"a": "claude", "b": "codex"}, ["claude", "codex"], tiebreak)[0], "codex")
        self.assertEqual(sm.select_implementer({"a": "antigravity"}, ["claude", "codex"], tiebreak), (None, {}))


class ReviewRules(unittest.TestCase):
    def test_self_review_is_rejected(self):
        with self.assertRaises(sm.StateError):
            sm.evaluate_reviews({"codex": "approve", "claude": "approve"}, "codex", [], 2)

    def test_outcomes(self):
        cases = [
            ({"claude": "approve", "antigravity": "approve"}, [], "approved"),
            ({"claude": "approve", "antigravity": "changes-requested"}, [], "changes_requested"),
            ({"claude": "approve", "antigravity": "security-objection"}, [], "needs_human"),
            ({"claude": "approve"}, [], "needs_human"),
            ({"claude": "approve"}, ["antigravity"], "needs_human"),
        ]
        for verdicts, malformed, expected in cases:
            with self.subTest(verdicts=verdicts, malformed=malformed):
                self.assertEqual(sm.evaluate_reviews(verdicts, "codex", malformed, 2)["status"], expected)
        self.assertEqual(sm.evaluate_reviews({"claude": "approve"}, "codex", [], 2)["reason"], "insufficient-reviewers")


class Transitions(unittest.TestCase):
    def test_illegal_transitions_raise(self):
        st = sm.fresh("B-90")
        with self.assertRaises(sm.StateError):
            sm.transition(st, "implementing", "skip ahead")
        sm.transition(st, "proposing", "start")
        self.assertEqual(st["history"][-1]["to"], "proposing")

    def test_human_gate_is_bound_to_decision_and_attempt(self):
        st = sm.fresh("B-90")
        st["phase"] = "accepted"
        with self.assertRaises(sm.StateError):
            sm.consume_approval(st, "abc")
        sm.approve_implementation(st, "codex", "abc", "ok")
        with self.assertRaises(sm.StateError):
            sm.consume_approval(st, "changed-decision")
        self.assertEqual(sm.consume_approval(st, "abc")["implementer"], "codex")
        with self.assertRaises(sm.StateError):
            sm.consume_approval(st, "abc")

    def test_escalate_and_resume(self):
        st = sm.fresh("B-90")
        sm.transition(st, "proposing", "start")
        sm.escalate(st, "malformed-output", "bad reply", "new")
        self.assertEqual(st["phase"], "needs_human")
        sm.resume(st, "new", "try again")
        self.assertEqual((st["phase"], st["needs_human"]), ("new", None))


class Replies(unittest.TestCase):
    def test_extracts_json_from_raw_fenced_and_embedded_text(self):
        for text in ('{"a": 1}', 'Here:\n```json\n{"a": 1}\n```', 'Answer {"a": 1} done'):
            self.assertEqual(replies.extract_json(text), {"a": 1})
        with self.assertRaises(replies.ReplyError):
            replies.extract_json("no json here")

    def test_schema_validation_fails_closed(self):
        good = {"task": "B-90", "stance": "agree", "reason": "fine"}
        self.assertEqual(replies.parse_reply(json.dumps(good), "vote", "B-90", ("claude",))["stance"], "agree")
        for bad in ({**good, "stance": "maybe"}, {"task": "B-90", "stance": "agree"}, {**good, "extra": 1},
                    {**good, "task": "B-01"}):
            with self.subTest(bad=bad), self.assertRaises(replies.ReplyError):
                replies.parse_reply(json.dumps(bad), "vote", "B-90", ("claude",))
        proposal = {"task": "B-90", "summary": "", "security": "", "approach": "", "tests": "", "efficiency": "",
                    "files": [], "recommended_implementer": "gemini", "concerns": []}
        with self.assertRaises(replies.ReplyError):
            replies.parse_reply(json.dumps(proposal), "propose", "B-90", ("claude", "codex"))

    def test_secrets_are_redacted(self):
        text = "key sk-ant-" + "a" * 30 + " and ghp_" + "b" * 36 + " and Bearer " + "c" * 30
        cleaned = replies.redact({"reason": text})["reason"]
        self.assertNotIn("a" * 30, cleaned)
        self.assertNotIn("b" * 36, cleaned)
        self.assertIn("[REDACTED:anthropic-key]", cleaned)


class Adapters(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.fake = self.base / "fake.py"
        self.fake.write_text(FAKE_MODEL, encoding="utf-8")
        self.config = load_config()

    def adapter(self, name, **changes):
        spec = {**self.config["models"][name], "executable": [sys.executable], "prefix": [str(self.fake), name],
                "auth_command": ["auth-status"], **changes}
        return adapters.ADAPTERS[spec["adapter"]](name, spec, root=self.base)

    def prompt(self, name, phase="vote"):
        path = self.base / f"B-90-{phase}-{name}.prompt.md"
        path.write_text(f"# Blue-team {phase}: B-90\n\nRead blue-team/AGENTS.md and blue-team/roles/{name}.md\n",
                        encoding="utf-8")
        return f"Read the file {path} and follow its instructions exactly."

    def test_availability_statuses(self):
        self.assertEqual(self.adapter("claude").availability().status, "READY")
        self.assertEqual(self.adapter("antigravity", auth_command=None).availability().status, "WARNING")
        self.assertEqual(self.adapter("codex", executable=[str(self.base / "missing.exe")]).availability().status,
                         "NOT INSTALLED")
        with mock.patch.dict(os.environ, {"FAKE_CODEX": "signed-out"}):
            self.assertIn("not signed in", self.adapter("codex").availability().detail)
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE": "noversion"}):
            self.assertEqual(self.adapter("claude").availability().status, "MISCONFIGURED")
        flags = self.adapter("claude", expected_flags=["--print", "--no-such-flag"]).availability(check_flags=True)
        self.assertEqual(flags.status, "MISCONFIGURED")
        self.assertEqual(self.adapter("claude", read=["-p"]).availability().status, "MISCONFIGURED")

    def test_antigravity_prompt_goes_last(self):
        parts = self.adapter("antigravity").command("read", "PROMPT", Path("s.json"), Path("o.txt"), 600)
        self.assertEqual(parts[-2:], ["--print", "PROMPT"])
        self.assertIn("600s", parts)
        self.assertNotIn("{schema}", " ".join(parts))

    def test_each_vendor_format_is_normalized(self):
        for name in ("claude", "codex", "antigravity"):
            with self.subTest(name=name):
                result = self.adapter(name).run("read", self.prompt(name), replies.schema_path("vote"), self.base,
                                                name, retries=0)
                self.assertTrue(result.ok, result.error)
                self.assertEqual(json.loads(result.text)["stance"], "agree")
                self.assertTrue(result.reply_sha256)

    def test_failures_are_bounded_and_reported(self):
        with mock.patch.dict(os.environ, {"FAKE_CODEX": "fail"}):
            result = self.adapter("codex").run("read", self.prompt("codex"), replies.schema_path("vote"), self.base,
                                               "codex", retries=1)
        self.assertFalse(result.ok)
        self.assertEqual(result.attempts, 2)
        self.assertIn("exit 1", result.error)
        counter = self.base / "counter"
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE": "flaky", "FAKE_COUNTER": str(counter)}):
            result = self.adapter("claude").run("read", self.prompt("claude"), replies.schema_path("vote"), self.base,
                                                "claude", retries=1)
        self.assertTrue(result.ok)
        self.assertEqual(result.attempts, 2)
        missing = self.adapter("claude", executable=[str(self.base / "nope.exe")])
        self.assertEqual(missing.run("read", "x", replies.schema_path("vote"), self.base, "c", 0).error, "CLI not installed")

    def test_error_envelopes_are_not_replies(self):
        self.assertEqual(adapters.ClaudeAdapter("claude", {}).extract_text('{"is_error": true, "result": "x"}', Path("n")), "")
        agy = adapters.AntigravityAdapter("antigravity", {})
        self.assertEqual(agy.extract_text('{"status": "SUCCESS", "response": "ok"}', Path("n")), "ok")
        self.assertEqual(agy.extract_text('{"status": "SUCCESS", "response": "", "denied_actions": [{}]}', Path("n")), "")
        self.assertEqual(agy.extract_text('{"status": "ERROR", "response": "partial"}', Path("n")), "")

    def test_antigravity_structured_output_wins_over_repeated_response(self):
        agy = adapters.AntigravityAdapter("antigravity", {})
        reply = {"task": "probe", "stance": "abstain", "reason": "write blocked"}
        envelope = {"status": "SUCCESS", "response": json.dumps(reply) + "\n" + json.dumps({**reply, "toolAction": "x"}),
                    "structured_output": reply}
        self.assertEqual(json.loads(agy.extract_text(json.dumps(envelope), Path("n"))), reply)
        del envelope["structured_output"]
        self.assertEqual(replies.extract_json(agy.extract_text(json.dumps(envelope), Path("n"))), reply)

    def test_antigravity_permission_denial_is_a_failed_call(self):
        with mock.patch.dict(os.environ, {"FAKE_ANTIGRAVITY": "denied"}):
            result = self.adapter("antigravity").run("read", self.prompt("antigravity"), replies.schema_path("vote"),
                                                     self.base, "antigravity", retries=0)
        self.assertFalse(result.ok)
        self.assertIn("auto-denied", result.error)


class Snapshots(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def snap(self, branch="Mayo", head="a", files=None):
        return watch.Snapshot(branch, head, "refs", "cfg", "blue-team/hooks", files or {})

    def test_ignored_patterns(self):
        patterns = self.config["watch_ignore"]
        self.assertTrue(watch.ignored("backend/app/agents/blue/__pycache__/x.pyc", patterns))
        self.assertTrue(watch.ignored("blue-team/runs/abc/prompt.md", patterns))
        self.assertFalse(watch.ignored("backend/app/agents/blue/feature.py", patterns))

    def test_branch_switch_and_commit_are_violations(self):
        report = watch.compare(self.snap(), self.snap(branch="rogue", head="b"), self.config, allow_writes=True)
        self.assertTrue(any("branch changed" in v for v in report.violations))
        self.assertTrue(any("HEAD moved" in v for v in report.violations))

    def test_write_boundaries(self):
        before = self.snap()
        allowed = self.snap(files={"backend/app/agents/blue/feature.py": "h"})
        self.assertEqual(watch.compare(before, allowed, self.config, allow_writes=True).violations, [])
        self.assertTrue(watch.compare(before, allowed, self.config, allow_writes=False).violations)
        for path in ("README.md", "backend/app/agents/blue/AGENTS.md", "blue-team/state/B-90.json"):
            with self.subTest(path=path):
                report = watch.compare(before, self.snap(files={path: "h"}), self.config, allow_writes=True)
                self.assertTrue(report.violations)


if __name__ == "__main__":
    unittest.main()
