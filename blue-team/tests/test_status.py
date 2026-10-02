"""STATUS.md dashboard: what needs the human, tables, bad input, and refresh hooks.
Run from the repository root: python -m unittest discover -s blue-team/tests -v
"""

import json
from pathlib import Path
import tempfile
import unittest

from sandbox import Sandbox  # also puts blue-team/bin on sys.path

import dashboard

ORCH = "python blue-team/bin/orchestrate.py"


def state(task, phase, **extra):
    base = {"task": task, "schema": 1, "phase": phase, "round": 1, "attempt": 0, "needs_human": None,
            "votes": {}, "decision": None, "approvals": [], "implementation": None,
            "history": [{"at": "2026-10-01T10:00:00Z", "from": "new", "to": phase, "event": f"moved to {phase}"}]}
    base.update(extra)
    return base


def task(task_id, title="A task", milestone="M1", status="todo", **extra):
    return {"id": task_id, "title": title, "milestone": milestone, "status": status, "owner": None,
            "notes": "", "updated": "2026-10-01T09:00:00Z", **extra}


class Folder:
    """A throwaway blue-team folder with the files the dashboard reads."""

    def __init__(self, tasks=(), states=(), decisions=(), threads=(), locks=()):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "tasks.json").write_text(json.dumps({"tasks": list(tasks)}), encoding="utf-8")
        for st in states:
            self.put(f"state/{st['task']}.json", json.dumps(st))
        for name, text in decisions:
            self.put(f"decisions/{name}", text)
        for name, text in threads:
            self.put(f"comms/threads/{name}.md", text)
        for name, text in locks:
            self.put(f"state/.locks/{name}.lock", text)

    def put(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def render(self):
        return dashboard.render(self.root)

    def close(self):
        self.tmp.cleanup()


class RenderTest(unittest.TestCase):
    def build(self, **kwargs):
        folder = Folder(**kwargs)
        self.addCleanup(folder.close)
        return folder

    def needs_section(self, text):
        return text.split("## Needs you now")[1].split("\n## ")[0]


class NeedsYou(RenderTest):
    def test_nothing_waiting(self):
        text = self.build(tasks=[task("B-01")], states=[state("B-01", "closed")]).render()
        self.assertIn("Nothing is waiting for you.", self.needs_section(text))

    def test_resolve_options_match_what_resolve_accepts(self):
        votes = {"claude": {"stance": "agree"}}
        folder = self.build(states=[
            state("B-01", "needs_human", votes=votes, needs_human={
                "reason": "tie", "details": "Tie: 1 of 2.", "from_phase": "voting", "resume_phase": "proposed"}),
            state("B-02", "needs_human", implementation={"model": "codex"}, needs_human={
                "reason": "security-objection", "details": "From codex.", "from_phase": "reviewing",
                "resume_phase": "implemented"}),
            state("B-03", "needs_human", needs_human={
                "reason": "malformed-output", "details": "Bad reply.", "from_phase": "proposing",
                "resume_phase": "new"}),
        ])
        section = self.needs_section(folder.render())
        self.assertIn(f'`{ORCH} resolve B-01 retry|reopen|accept --note "..."`', section)
        self.assertIn(f'`{ORCH} resolve B-02 retry|reopen|revise --note "..."`', section)
        self.assertIn(f'`{ORCH} resolve B-03 retry|reopen --note "..."`', section)
        self.assertIn("Stopped for a human: security-objection. From codex.", section)
        self.assertIn("Retry resumes at implemented.", section)

    def test_accept_and_revise_are_not_offered_when_resolve_would_refuse_them(self):
        folder = self.build(states=[state("B-01", "needs_human", votes={}, needs_human={
            "reason": "tie", "details": "x", "from_phase": "voting", "resume_phase": "proposed"})])
        self.assertIn("resolve B-01 retry|reopen --note", folder.render())

    def test_approval_waiting_then_approved(self):
        decision = {"implementer": "codex", "status": "accepted"}
        waiting = self.build(tasks=[task("B-01", "Entry point")], states=[
            state("B-01", "accepted", decision=decision)]).render()
        self.assertIn("**B-01** (Entry point): Waiting for your approval before codex gets write access "
                      "(implementation, attempt 1).", waiting)
        self.assertIn(f"`{ORCH} approve B-01`", waiting)

        approved = state("B-01", "accepted", decision=decision, approvals=[
            {"gate": "implementation", "implementer": "codex", "attempt": 1, "used": False}])
        text = self.build(states=[approved]).render()
        self.assertIn("You approved implementation by codex. Run it when ready.", text)
        self.assertIn(f"`{ORCH} auto B-01`", text)

        for stale in ({"attempt": 2, "used": False}, {"attempt": 1, "used": True}):
            old = state("B-01", "accepted", decision=decision,
                        approvals=[{"gate": "implementation", "implementer": "codex", **stale}])
            self.assertIn(f"`{ORCH} approve B-01`", self.build(states=[old]).render())

    def test_revision_approval_names_the_earlier_implementer(self):
        text = self.build(states=[state("B-01", "changes_requested", attempt=1,
                                        implementation={"model": "claude"})]).render()
        self.assertIn("Waiting for your approval before claude gets write access (a revision, attempt 2).", text)

    def test_ready_to_close_shows_both_commands(self):
        text = self.build(states=[state("B-01", "ready_to_close")]).render()
        self.assertIn(f"`{ORCH} close B-01`", text)
        self.assertIn(f"`{ORCH} close B-01 --commit`", text)

    def test_paused_interrupted_and_running(self):
        folder = self.build(
            states=[state("B-01", "proposed"), state("B-02", "reviewing"), state("B-03", "voting")],
            locks=[("B-03", "1234 2026-10-01T11:00:00Z")])
        text = folder.render()
        needs = self.needs_section(text)
        self.assertIn("Paused after proposed.", needs)
        self.assertIn("Interrupted while reviewing.", needs)
        self.assertNotIn("B-03", needs)
        self.assertIn("**B-03** holds the task lock since 2026-10-01T11:00:00Z", text)
        self.assertIn("voting (running)", text)


class Tables(RenderTest):
    def test_tasks_milestones_and_board_lists(self):
        tasks = [task("B-01", status="done", milestone="M1"), task("B-02", status="in_progress", owner="codex",
                                                                   notes="halfway"),
                 task("B-03", status="blocked", milestone="M2", notes="waiting on lab"),
                 task("B-04", status="todo", milestone="M2")]
        text = self.build(tasks=tasks).render()
        self.assertIn("In progress 1 · In review 0 · Blocked 1 · To do 1 · Done 1", text)
        self.assertIn("| M1 | 1 | 2 |", text)
        self.assertIn("| M2 | 0 | 2 |", text)
        self.assertIn("- **B-02** A task (codex). halfway", text)
        self.assertIn("- **B-03** A task (unassigned). waiting on lab", text)

    def test_decisions_threads_and_latest_activity(self):
        decision = ("# 0007: B-09\n\n- Thread: B-09\n- Date: 2026-10-03T08:00:00Z\n- Status: accepted\n"
                    "- Implementer: codex\n- Recorded by: orchestrator\n- Rule: 2 of 3 votes agree.\n\n"
                    "## Security objections\n\n- claude on B-09: not a field\n")
        thread = ("# Thread B-09: Probing\n\n### 2026-10-03T07:00:00Z | claude | proposal\n\nfirst\n"
                  "\\### 2026-10-03T07:30:00Z | codex | review\nnot a header\n\n"
                  "### 2026-10-03T07:45:00Z | codex | vote\n\nsecond\n")
        text = self.build(tasks=[task("B-09")], decisions=[("0007-b-09.md", decision)],
                          threads=[("B-09", thread)]).render()
        self.assertIn("| [0007](decisions/0007-b-09.md) | B-09 | accepted | codex | 2 of 3 votes agree. |", text)
        self.assertIn("| [B-09](comms/threads/B-09.md) | 2 | 2026-10-03T07:45:00Z · codex · vote |", text)
        self.assertIn("Latest activity: 2026-10-03T08:00:00Z", text)

    def test_table_cells_survive_pipes_and_newlines(self):
        text = self.build(states=[state("B-01", "closed", history=[
            {"at": "2026-10-01T10:00:00Z", "event": "closed | by\nthe human"}])]).render()
        self.assertIn("closed \\| by the human", text)

    def test_same_files_give_the_same_page(self):
        folder = self.build(tasks=[task("B-01", status="done")], states=[state("B-01", "closed")])
        self.assertEqual(folder.render(), folder.render())


class BadInput(RenderTest):
    def test_unreadable_files_are_reported_not_raised(self):
        folder = self.build(tasks=[task("B-01")], states=[state("B-02", "closed")])
        folder.put("state/B-03.json", "{not json")
        folder.put("state/B-04.json", json.dumps({"task": "B-04"}))
        text = folder.render()
        needs = self.needs_section(text)
        self.assertIn("**Problem:** state/B-03.json could not be read", needs)
        self.assertIn("**Problem:** state/B-04.json could not be read (not a workflow state file)", needs)
        self.assertIn("| [B-02](comms/threads/B-02.md) | closed |", text)

        folder.put("tasks.json", "[]")
        self.assertIn("**Problem:** tasks.json could not be read", self.needs_section(folder.render()))

    def test_empty_folder_renders(self):
        folder = Folder()
        self.addCleanup(folder.close)
        (folder.root / "tasks.json").unlink()
        text = folder.render()
        self.assertIn("tasks.json could not be read", text)
        self.assertIn("No decisions recorded yet.", text)
        self.assertIn("No threads yet.", text)


class Hooks(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.page = self.box.root / "blue-team/STATUS.md"

    def test_board_changes_refresh_the_page_and_git_ignores_it(self):
        self.assertFalse(self.page.exists())
        self.box.script("board.py", "claim", "B-90", "--model", "codex")
        text = self.page.read_text(encoding="utf-8")
        self.assertIn("In progress 1", text)
        self.assertIn("- **B-90** Sample task (codex)\n", text)
        self.box.script("board.py", "post", "B-90", "--model", "claude", "--type", "note", "--body", "hello")
        self.assertIn("| [B-90](comms/threads/B-90.md) | 1 |", self.page.read_text(encoding="utf-8"))
        self.assertEqual(self.box.git("check-ignore", "blue-team/STATUS.md").returncode, 0)
        self.assertNotIn("STATUS.md", self.box.git("status", "--porcelain").stdout)

    def test_render_command_rebuilds_a_deleted_page(self):
        self.box.script("board.py", "render")
        self.assertTrue(self.page.exists())
        self.page.unlink()
        self.assertIn("STATUS.md", self.box.script("board.py", "render").stdout)
        self.assertTrue(self.page.exists())

    def test_a_dashboard_failure_never_stops_the_workflow(self):
        self.page.mkdir()
        result = self.box.script("board.py", "claim", "B-90", "--model", "codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STATUS.md not refreshed", result.stderr)
        self.assertEqual(self.box.tasks()["B-90"]["owner"], "codex")


if __name__ == "__main__":
    unittest.main()
