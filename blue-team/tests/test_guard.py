"""Git hook guardrails: branch, paths, pushes, and append-only records.
Run from the repository root: python -m unittest discover -s blue-team/tests -v
"""

import json
from pathlib import Path
import unittest

from sandbox import Sandbox, run

ZERO = "0" * 40


class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)

    def commit(self, message="change"):
        self.box.git("add", "-A")
        return self.box.git("commit", "-m", message, check=False)


class BranchAndPaths(SandboxTest):
    def test_commit_inside_blue_paths_on_mayo_is_allowed(self):
        self.box.write("backend/app/agents/blue/new.py")
        self.assertEqual(self.commit().returncode, 0)

    def test_commit_outside_allowed_scope_is_blocked(self):
        self.box.write("README.md", "changed\n")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the blue-team write paths", result.stderr)

    def test_deleting_a_shared_file_is_blocked(self):
        self.box.git("rm", "-q", "README.md")
        self.assertNotEqual(self.box.git("commit", "-m", "delete", check=False).returncode, 0)

    def test_commits_on_other_branches_are_blocked(self):
        switched = self.box.git("switch", "main")
        self.assertIn("read-only", switched.stderr)
        self.box.write("backend/app/agents/blue/new.py")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("only allowed on Mayo", result.stderr)
        self.assertEqual(self.box.script("guard.py", "check").returncode, 1)


class Pushes(SandboxTest):
    def test_pre_push_rules(self):
        head = self.box.head()
        orphan = self.box.git("commit-tree", "HEAD^{tree}", "-m", "orphan").stdout.strip()
        cases = {
            ("origin", f"refs/heads/Mayo {head} refs/heads/Mayo {ZERO}"): 0,
            ("origin", f"refs/heads/main {head} refs/heads/main {ZERO}"): 1,
            ("origin", f"refs/heads/Mayo {head} refs/heads/main {ZERO}"): 1,
            ("origin", f"(delete) {ZERO} refs/heads/Mayo {head}"): 1,
            ("upstream", f"refs/heads/Mayo {head} refs/heads/Mayo {ZERO}"): 1,
            ("origin", f"refs/heads/Mayo {head} refs/heads/Mayo {orphan}"): 1,
            ("origin", f"refs/heads/Mayo {head} refs/heads/Mayo {'1' * 40}"): 1,
        }
        for (remote, line), expected in cases.items():
            with self.subTest(remote=remote, line=line):
                result = self.box.script("guard.py", "pre-push", remote, "url", stdin=line + "\n")
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_push_to_another_branch_and_force_push_are_blocked(self):
        remote = self.box.base / "remote.git"
        run(["git", "init", "-q", "--bare", str(remote)], self.box.root)
        self.box.git("remote", "add", "origin", str(remote))
        self.assertEqual(self.box.git("push", "-q", "origin", "Mayo", check=False).returncode, 0)
        self.assertNotEqual(self.box.git("push", "-q", "origin", "main", check=False).returncode, 0)
        self.assertNotEqual(self.box.git("push", "-q", "origin", "Mayo:main", check=False).returncode, 0)
        self.box.write("backend/app/agents/blue/a.py")
        self.commit("one")
        self.box.git("push", "-q", "origin", "Mayo")
        self.box.git("commit", "--amend", "-q", "-m", "rewritten")
        forced = self.box.git("push", "-q", "--force", "origin", "Mayo", check=False)
        self.assertNotEqual(forced.returncode, 0)
        self.assertIn("force pushes", forced.stderr)
        deleted = self.box.git("push", "-q", "origin", ":Mayo", check=False)
        self.assertNotEqual(deleted.returncode, 0)


class AppendOnlyRecords(SandboxTest):
    def seed(self):
        self.box.write("blue-team/comms/threads/B-90.md", "# Thread B-90: Sample\n\n### t | claude | note\n\nfirst\n")
        self.box.write("blue-team/decisions/0001-b-90.md", "# 0001\n\n- Status: accepted\n")
        self.box.write("blue-team/state/B-90.json", json.dumps({"task": "B-90", "phase": "new",
                                                                "history": [{"event": "one"}]}))
        self.assertEqual(self.commit("records").returncode, 0)

    def test_threads_accept_appends_but_not_edits(self):
        self.seed()
        path = self.box.root / "blue-team/comms/threads/B-90.md"
        path.write_text(path.read_text() + "\n### t2 | codex | note\n\nsecond\n", encoding="utf-8")
        self.assertEqual(self.commit("append").returncode, 0)
        path.write_text(path.read_text().replace("first", "edited"), encoding="utf-8")
        result = self.commit("rewrite")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("append-only", result.stderr)

    def test_decisions_are_immutable_and_cannot_be_deleted(self):
        self.seed()
        self.box.write("blue-team/decisions/0001-b-90.md", "# 0001\n\n- Status: rejected\n")
        self.assertNotEqual(self.commit("edit decision").returncode, 0)
        self.box.git("restore", "--staged", "--worktree", "blue-team/decisions/0001-b-90.md")
        self.box.git("rm", "-q", "blue-team/decisions/0001-b-90.md")
        self.assertNotEqual(self.box.git("commit", "-m", "delete", check=False).returncode, 0)

    def test_state_history_only_grows(self):
        self.seed()
        self.box.write("blue-team/state/B-90.json", json.dumps({"task": "B-90", "phase": "proposed",
                                                                "history": [{"event": "one"}, {"event": "two"}]}))
        self.assertEqual(self.commit("advance").returncode, 0)
        self.box.write("blue-team/state/B-90.json", json.dumps({"task": "B-90", "phase": "accepted",
                                                                "history": [{"event": "forged"}]}))
        self.assertNotEqual(self.commit("forge").returncode, 0)
        verify = self.box.script("guard.py", "verify")
        self.assertEqual(verify.returncode, 1)
        self.assertIn("history is append-only", verify.stdout)


if __name__ == "__main__":
    unittest.main()
