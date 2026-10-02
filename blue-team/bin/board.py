"""Shared task board, message threads, and decision records for the Mayo branch.

Every model and person uses this script instead of editing tasks.json, CHECKLIST.md,
threads, or decisions by hand. Threads are append-only. Thread messages are the
human-readable record; the orchestrator's state files, not thread text, drive the
workflow, so a message posted under another model's name cannot change a decision.

    python blue-team/bin/board.py status
    python blue-team/bin/board.py claim B-06 --model codex
    python blue-team/bin/board.py move B-06 review --model codex --note "tests pass"
    python blue-team/bin/board.py post B-06 --model antigravity --type review --body "..."
    python blue-team/bin/board.py read B-06
    python blue-team/bin/board.py decide B-06 --model human --outcome "..." --position human=agree --human-approve
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sys
import time

import dashboard
from common import FRAMEWORK, atomic_write, load_config, now, participants, sha256_bytes, voters
import state as workflow

TASKS = FRAMEWORK / "tasks.json"
CHECKLIST = FRAMEWORK / "CHECKLIST.md"
THREADS = FRAMEWORK / "comms" / "threads"
DECISIONS = FRAMEWORK / "decisions"
LOCK = FRAMEWORK / ".board.lock"

STATUSES = ("in_progress", "review", "blocked", "todo", "done")
STATUS_TITLES = {"in_progress": "In progress", "review": "In review", "blocked": "Blocked", "todo": "To do",
                 "done": "Done"}
MESSAGE_TYPES = ("proposal", "position", "plan", "decision-draft", "decision", "implementation", "review",
                 "question", "answer", "status", "handoff", "strategy", "note", "vote")
STANCES = workflow.STANCES
THREAD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
TASK_ID = re.compile(r"B-\d{2,3}")
HEADER = re.compile(r"^### (\S+) \| ([\w-]+) \| ([\w-]+)$")


class BoardError(ValueError):
    pass


# Tasks ---------------------------------------------------------------------

def load_tasks() -> dict:
    return json.loads(TASKS.read_text(encoding="utf-8"))


def save_tasks(data: dict, who: str) -> None:
    data["updated"] = now()
    data["updated_by"] = who
    atomic_write(TASKS, json.dumps(data, indent=2) + "\n")
    atomic_write(CHECKLIST, render_checklist(data))
    dashboard.refresh()


def find_task(data: dict, task_id: str) -> dict:
    for task in data["tasks"]:
        if task["id"] == task_id:
            return task
    raise BoardError(f"No task {task_id}. Run board.py status to see task IDs.")


def add_task(task_id: str, title: str, milestone: str, who: str, owner: str | None = None,
             notes: str = "", status: str = "todo", context: list[str] | None = None) -> dict:
    _require(TASK_ID.fullmatch(task_id) is not None, "Task IDs look like B-07.")
    _require(status in STATUSES, f"Status must be one of: {', '.join(STATUSES)}.")
    _require(bool(title.strip()) and bool(milestone.strip()), "A task needs a title and a milestone.")
    _check_context(context or [])
    with _locked():
        data = load_tasks()
        _require(all(t["id"] != task_id for t in data["tasks"]), f"{task_id} already exists.")
        task = {"id": task_id, "title": title, "milestone": milestone, "status": status, "owner": owner,
                "reviewers": [], "notes": notes, "commits": [], "context": context or [], "updated": now()}
        data["tasks"].append(task)
        save_tasks(data, who)
    return task


def edit_task(task_id: str, who: str, title: str | None = None, notes: str | None = None,
              milestone: str | None = None, owner: str | None = None, context: list[str] | None = None) -> dict:
    """Correct a task's text, milestone, owner, or context files. Status changes go through move().

    A done task is final: its closing commit and decision records name it, so it cannot be edited.
    """
    changes = {"title": title, "notes": notes, "milestone": milestone, "owner": owner, "context": context}
    changes = {key: value for key, value in changes.items() if value is not None}
    _require(bool(changes), "Nothing to change: pass --title, --notes, --milestone, --owner, or --context.")
    for key in ("title", "milestone"):
        _require(key not in changes or bool(changes[key].strip()), f"{key} cannot be empty.")
    _check_context(changes.get("context", []))
    with _locked():
        data = load_tasks()
        task = find_task(data, task_id)
        _require(task["status"] != "done", f"{task_id} is done; its record is final.")
        task.update(changes, updated=now())
        save_tasks(data, who)
    return task


def _check_context(paths: list[str]) -> None:
    """Context files are read by every model, so they must be plain repository-relative paths."""
    for path in paths:
        parts = path.replace("\\", "/").split("/")
        _require(bool(path) and not path.startswith(("/", "\\")) and ":" not in path and ".." not in parts,
                 f"Context path {path!r} must be a repository-relative path without '..'.")


def claim(task_id: str, who: str, force: bool = False) -> dict:
    """Claim a task exclusively. Only the human may take over a task someone else holds."""
    _require(not force or who == "human", "Only the human may force a claim.")
    with _locked():
        data = load_tasks()
        task = find_task(data, task_id)
        if task["status"] == "done":
            raise BoardError(f"{task_id} is already done.")
        if task["status"] in ("in_progress", "review") and task.get("owner") not in (None, who) and not force:
            raise BoardError(f"{task_id} is claimed by {task['owner']}. Ask in its thread before taking it over.")
        task.update(status="in_progress", owner=who, updated=now())
        save_tasks(data, who)
    return task


def move(task_id: str, status: str, who: str, note: str | None = None, commit: str | None = None,
         reviewers: list[str] | None = None, owner: str | None = None) -> dict:
    _require(status in STATUSES, f"Status must be one of: {', '.join(STATUSES)}.")
    with _locked():
        data = load_tasks()
        task = find_task(data, task_id)
        task.update(status=status, updated=now())
        if note:
            task["notes"] = note
        if commit:
            task.setdefault("commits", []).append(commit)
        if reviewers is not None:
            task["reviewers"] = reviewers
        if owner is not None:
            task["owner"] = owner
        save_tasks(data, who)
    return task


def render_checklist(data: dict) -> str:
    tasks = data["tasks"]
    counts = {status: sum(1 for t in tasks if t["status"] == status) for status in STATUSES}
    lines = ["# Mayo branch checklist", "",
             "Generated from `tasks.json` by `python blue-team/bin/board.py`. Do not edit by hand.", "",
             f"Last updated {data.get('updated', 'never')} by {data.get('updated_by', 'nobody')}.", "",
             "Progress: " + " · ".join(f"{counts[s]} {STATUS_TITLES[s].lower()}" for s in STATUSES), ""]
    for status in STATUSES:
        group = [t for t in tasks if t["status"] == status]
        lines += [f"## {STATUS_TITLES[status]}", ""]
        if not group:
            lines += ["None.", ""]
            continue
        for task in group:
            box = "x" if status == "done" else " "
            details = [f"milestone {task['milestone']}", f"owner: {task.get('owner') or 'unassigned'}"]
            if task.get("reviewers"):
                details.append("reviewers: " + ", ".join(task["reviewers"]))
            if task.get("commits"):
                details.append("commits: " + ", ".join(task["commits"]))
            if (THREADS / f"{task['id']}.md").exists():
                details.append(f"[thread](comms/threads/{task['id']}.md)")
            lines.append(f"- [{box}] **{task['id']}** {task['title']} · " + " · ".join(details))
            if task.get("notes"):
                lines.append(f"  - {task['notes']}")
        lines.append("")
    return "\n".join(lines)


# Threads -------------------------------------------------------------------

def thread_path(thread: str) -> Path:
    _require(THREAD_ID.fullmatch(thread) is not None, "Thread IDs use letters, digits, dot, dash, underscore.")
    return THREADS / f"{thread}.md"


def post(thread: str, who: str, kind: str, body: str, title: str | None = None, evidence: str | None = None) -> dict:
    _require(who in participants(), f"--model must be one of: {', '.join(participants())}.")
    _require(kind in MESSAGE_TYPES, f"--type must be one of: {', '.join(MESSAGE_TYPES)}.")
    body = body.strip()
    _require(bool(body), "Message body is empty.")
    path = thread_path(thread)
    with _locked():
        THREADS.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            atomic_write(path, f"# Thread {thread}: {title or _default_title(thread)}\n")
        safe = "\n".join("\\" + line if HEADER.match(line) else line for line in body.splitlines())
        source = f"\n\n_Recorded by the orchestrator: {evidence}._" if evidence else ""
        message = {"time": now(), "from": who, "type": kind, "body": safe}
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"\n### {message['time']} | {who} | {kind}\n\n{safe}{source}\n")
        dashboard.refresh()
    return message


def read_thread(thread: str) -> list[dict]:
    path = thread_path(thread)
    if not path.exists():
        return []
    messages, current = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADER.match(line)
        if match and match.group(3) in MESSAGE_TYPES:
            current = {"time": match.group(1), "from": match.group(2), "type": match.group(3), "lines": []}
            messages.append(current)
        elif current is not None:
            current["lines"].append(line)
    for message in messages:
        message["body"] = "\n".join(message.pop("lines")).strip()
    return messages


# Decisions -----------------------------------------------------------------

def decide(thread: str, who: str, outcome: str, positions: dict[str, tuple[str, str]],
           implementer: str | None = None, human_approve: bool = False, evaluation: dict | None = None,
           extra: dict[str, str] | None = None) -> dict:
    """Write a numbered, immutable decision record. Status comes from the state machine's rules."""
    _require(bool(outcome.strip()), "Describe the outcome.")
    _require(bool(positions), "Record at least one position.")
    for name, (stance, _) in positions.items():
        _require(name in voters(), f"Unknown participant {name}.")
        _require(stance in STANCES, f"Stance must be one of: {', '.join(STANCES)}.")
    _require(implementer is None or implementer in voters(), f"Unknown implementer {implementer}.")
    status, rule = decision_status(positions, human_approve, evaluation)
    with _locked():
        DECISIONS.mkdir(parents=True, exist_ok=True)
        numbers = [int(p.name[:4]) for p in DECISIONS.glob("[0-9][0-9][0-9][0-9]-*.md")]
        number = max(numbers, default=0) + 1
        slug = re.sub(r"[^a-z0-9]+", "-", thread.lower()).strip("-")
        path = DECISIONS / f"{number:04d}-{slug}.md"
        rows = "\n".join(f"| {name} | {stance} | {note.replace('|', '/').replace(chr(10), ' ') or '-'} |"
                         for name, (stance, note) in positions.items())
        objections = [f"- {name} on {thread}: {note or 'no reason given'}" for name, (stance, note) in positions.items()
                      if stance == "security-objection"]
        sections = [f"# {number:04d}: {thread}", "",
                    f"- Thread: {thread}", f"- Date: {now()}", f"- Status: {status}",
                    f"- Implementer: {implementer or 'none'}", f"- Recorded by: {who}", f"- Rule: {rule}", "",
                    "## Outcome", "", outcome.strip(), "",
                    "## Positions", "", "| Participant | Stance | Reason |", "| --- | --- | --- |", rows, "",
                    "## Security objections", "", "\n".join(objections) or "None.", ""]
        for heading, text in (extra or {}).items():
            sections += [f"## {heading}", "", text.strip() or "None.", ""]
        atomic_write(path, "\n".join(sections))
    digest = sha256_bytes(path.read_bytes())
    post(thread, who, "decision", f"Decision {number:04d}: **{status}**. {rule}\n\nRecord: blue-team/decisions/{path.name}")
    return {"number": number, "path": path, "status": status, "rule": rule, "implementer": implementer,
            "sha256": digest}


def decision_status(positions: dict[str, tuple[str, str]], human_approve: bool,
                    evaluation: dict | None = None) -> tuple[str, str]:
    stances = {name: stance for name, (stance, _) in positions.items()}
    if human_approve:
        overridden = " over a recorded security objection" if "security-objection" in stances.values() else ""
        return "accepted", f"Approved by the human{overridden}."
    if evaluation is None:
        model_votes = {n: s for n, s in stances.items() if n != "human"}
        evaluation = workflow.evaluate_votes(model_votes, [], load_config()["policy"]["quorum"])
    status = "accepted" if evaluation["status"] == "accepted" else "needs-human"
    return status, evaluation["rule"]


def latest_decision(thread: str) -> dict | None:
    found = None
    for path in sorted(DECISIONS.glob("[0-9][0-9][0-9][0-9]-*.md")):
        text = path.read_text(encoding="utf-8")
        fields = dict(re.findall(r"^- (Thread|Status|Implementer): (.+)$", text, flags=re.MULTILINE))
        if fields.get("Thread") == thread:
            found = {"path": path, "status": fields.get("Status"), "implementer": fields.get("Implementer"),
                     "sha256": sha256_bytes(path.read_bytes())}
    return found


# Helpers -------------------------------------------------------------------

def _default_title(thread: str) -> str:
    try:
        return find_task(load_tasks(), thread)["title"]
    except (BoardError, FileNotFoundError):
        return thread


@contextmanager
def _locked(timeout: float = 15.0):
    deadline = time.monotonic() + timeout
    while True:
        try:
            handle = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                age = int(time.time() - LOCK.stat().st_mtime) if LOCK.exists() else 0
                raise BoardError(f"Board is locked by another process (lock is {age}s old). "
                                 f"If nothing else is running, delete {LOCK}.")
            time.sleep(0.2)
    try:
        os.write(handle, str(os.getpid()).encode())
        yield
    finally:
        os.close(handle)
        LOCK.unlink(missing_ok=True)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BoardError(message)


def _status_text() -> str:
    data = load_tasks()
    lines = []
    for status in ("in_progress", "review", "blocked"):
        for task in data["tasks"]:
            if task["status"] == status:
                lines.append(f"{STATUS_TITLES[status]:<12} {task['id']}  {task['title']}  ({task.get('owner') or 'unassigned'})")
    todo = [t for t in data["tasks"] if t["status"] == "todo"]
    lines.append(f"To do        {len(todo)} tasks: " + ", ".join(t["id"] for t in todo))
    lines.append(f"Done         {sum(1 for t in data['tasks'] if t['status'] == 'done')} tasks")
    if THREADS.exists():
        lines += ["", "Threads (latest message):"]
        for path in sorted(THREADS.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
            messages = read_thread(path.stem)
            if messages:
                last = messages[-1]
                lines.append(f"  {path.stem:<14} {last['time']}  {last['from']:<12} {last['type']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    names = participants()
    parser = argparse.ArgumentParser(description="Mayo branch task board and message threads.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="summary of tasks and recent threads")
    sub.add_parser("render", help="regenerate CHECKLIST.md from tasks.json")

    p = sub.add_parser("add", help="add a task")
    p.add_argument("task_id"); p.add_argument("title"); p.add_argument("--milestone", required=True)
    p.add_argument("--model", required=True, choices=names); p.add_argument("--owner", choices=names)
    p.add_argument("--notes", default=""); p.add_argument("--status", default="todo", choices=STATUSES)
    p.add_argument("--context", nargs="*", default=[], help="files every model must read for this task")

    p = sub.add_parser("edit", help="correct a task's title, notes, milestone, owner, or context (not once done)")
    p.add_argument("task_id"); p.add_argument("--model", required=True, choices=names)
    p.add_argument("--title"); p.add_argument("--notes"); p.add_argument("--milestone")
    p.add_argument("--owner", choices=names)
    p.add_argument("--context", nargs="*", help="replaces the task's context files")

    p = sub.add_parser("claim", help="claim a task and mark it in progress")
    p.add_argument("task_id"); p.add_argument("--model", required=True, choices=names)
    p.add_argument("--force", action="store_true", help="human only: take over a task someone else holds")

    p = sub.add_parser("move", help="change a task's status")
    p.add_argument("task_id"); p.add_argument("status", choices=STATUSES)
    p.add_argument("--model", required=True, choices=names); p.add_argument("--note")
    p.add_argument("--commit"); p.add_argument("--reviewers", nargs="*")

    p = sub.add_parser("post", help="append a message to a thread")
    p.add_argument("thread"); p.add_argument("--model", required=True, choices=names)
    p.add_argument("--type", required=True, choices=MESSAGE_TYPES); p.add_argument("--title")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--body"); group.add_argument("--body-file", type=Path)

    p = sub.add_parser("read", help="print a thread")
    p.add_argument("thread"); p.add_argument("--last", type=int, default=0)

    p = sub.add_parser("decide", help="record a decision manually (the orchestrator records task decisions)")
    p.add_argument("thread"); p.add_argument("--model", required=True, choices=names)
    p.add_argument("--outcome", required=True); p.add_argument("--implementer", choices=voters())
    p.add_argument("--position", action="append", default=[], metavar="WHO=STANCE[:REASON]")
    p.add_argument("--human-approve", action="store_true", help="only when the human explicitly approves")

    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            print(_status_text())
        elif args.command == "render":
            atomic_write(CHECKLIST, render_checklist(load_tasks()))
            dashboard.refresh()
            print("Rendered blue-team/CHECKLIST.md and blue-team/STATUS.md")
        elif args.command == "add":
            task = add_task(args.task_id, args.title, args.milestone, args.model, args.owner, args.notes,
                            args.status, args.context)
            print(f"Added {task['id']}.")
        elif args.command == "edit":
            task = edit_task(args.task_id, args.model, args.title, args.notes, args.milestone, args.owner,
                             args.context)
            print(f"Updated {task['id']}.")
        elif args.command == "claim":
            print(f"{claim(args.task_id, args.model, args.force)['id']} is now in progress, owned by {args.model}.")
        elif args.command == "move":
            task = move(args.task_id, args.status, args.model, args.note, args.commit, args.reviewers)
            print(f"{task['id']} is now {STATUS_TITLES[task['status']].lower()}.")
        elif args.command == "post":
            body = args.body_file.read_text(encoding="utf-8") if args.body_file else args.body
            post(args.thread, args.model, args.type, body, args.title)
            print(f"Posted to {args.thread}.")
        elif args.command == "read":
            messages = read_thread(args.thread)
            for message in messages[-args.last:] if args.last else messages:
                print(f"--- {message['time']} | {message['from']} | {message['type']}\n{message['body']}\n")
            if not messages:
                print(f"No messages in {args.thread}.")
        elif args.command == "decide":
            _require(args.model == "human" or not args.human_approve, "Only the human may use --human-approve.")
            positions = {}
            for raw in args.position:
                name, _, rest = raw.partition("=")
                stance, _, note = rest.partition(":")
                positions[name.strip()] = (stance.strip(), note.strip())
            result = decide(args.thread, args.model, args.outcome, positions, args.implementer, args.human_approve)
            print(f"Decision {result['number']:04d}: {result['status']} ({result['path'].name}).")
    except (BoardError, workflow.StateError) as error:
        print(f"board: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
