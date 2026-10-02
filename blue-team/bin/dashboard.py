"""Generated dashboard of the blue team's live state, written to blue-team/STATUS.md.

The page is a view over tasks.json, state/, decisions/, and comms/threads/. Nothing reads
it back and no workflow step depends on it. A failure to write it is reported on stderr
but never stops a task. It uses no clock, so the same files always give the same page.
STATUS.md is git-ignored: it is local, always rebuildable, and would change on every step.
Rebuild it with: python blue-team/bin/board.py render
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from common import FRAMEWORK, atomic_write

STATUS_FILE = "STATUS.md"
ORCH = "python blue-team/bin/orchestrate.py"
HEADER = re.compile(r"^### (\S+) \| ([\w-]+) \| ([\w-]+)$")
DECISION_FIELDS = re.compile(r"^- (Thread|Date|Status|Implementer|Rule): (.+)$", re.MULTILINE)
BOARD_STATUSES = (("in_progress", "In progress"), ("review", "In review"), ("blocked", "Blocked"),
                  ("todo", "To do"), ("done", "Done"))
TRANSIENT = ("proposing", "voting", "implementing", "reviewing")
PAUSED = ("proposed", "implemented", "approved")


def refresh(framework: Path = FRAMEWORK) -> None:
    """Rebuild STATUS.md. It is a view, so a failure here must not stop the workflow."""
    try:
        atomic_write(framework / STATUS_FILE, render(framework))
    except Exception as error:  # noqa: BLE001 - a dashboard problem must never break a task
        print(f"dashboard: {STATUS_FILE} not refreshed: {error}", file=sys.stderr)


def render(framework: Path = FRAMEWORK) -> str:
    problems: list[str] = []
    tasks = _tasks(framework, problems)
    states = _states(framework, problems)
    decisions = _decisions(framework)
    threads = _threads(framework)
    locks = _locks(framework)
    titles = {t.get("id"): t.get("title", "") for t in tasks}
    attention = _attention(states, locks, titles)

    lines = ["# Blue team status", "",
             "Generated from `tasks.json`, `state/`, `decisions/`, and `comms/threads/`. Do not edit it. "
             "Rebuild with `python blue-team/bin/board.py render`. It is local only (git-ignored).", "",
             f"Latest activity: {_latest(tasks, states, decisions, threads) or 'none yet'}", "",
             "## Needs you now", ""]
    if not attention and not problems:
        lines += ["Nothing is waiting for you.", ""]
    for problem in problems:
        lines.append(f"- **Problem:** {problem} Fix or restore the file before running that task.")
    for item in attention:
        label = f"**{item['task']}**" + (f" ({item['title']})" if item["title"] else "")
        lines.append(f"- {label}: {item['text']}")
        lines += [f"  - `{command}`" for command in item["commands"]]
    if attention or problems:
        lines.append("")

    if locks:
        lines += ["## Running now", ""]
        for task, since in locks.items():
            lines.append(f"- **{task}** holds the task lock" + (f" since {since}" if since else "")
                         + ". If no run is active, the lock is stale: delete "
                         f"`blue-team/state/.locks/{task}.lock`.")
        lines.append("")

    lines += ["## Tasks", "", " · ".join(f"{label} {sum(1 for t in tasks if t.get('status') == key)}"
                                          for key, label in BOARD_STATUSES), ""]
    milestones: dict[str, list[int]] = {}
    for task in tasks:
        done_total = milestones.setdefault(str(task.get("milestone", "?")), [0, 0])
        done_total[1] += 1
        done_total[0] += task.get("status") == "done"
    if milestones:
        lines += ["| Milestone | Done | Total |", "| --- | --- | --- |"]
        lines += [_row(name, done, total) for name, (done, total) in milestones.items()]
        lines.append("")
    for key, label in BOARD_STATUSES[:3]:
        group = [t for t in tasks if t.get("status") == key]
        if group:
            lines += [f"**{label}**", ""] + [_task_line(t) for t in group] + [""]
    todo = [t for t in tasks if t.get("status") == "todo"]
    if todo:
        lines += ["**To do**", ""] + [_task_line(t, with_notes=False) for t in todo] + [""]

    lines += ["## Workflow", ""]
    if states:
        lines += ["| Task | Phase | Round / attempt | Decision | Last event |", "| --- | --- | --- | --- | --- |"]
        for task, st in sorted(states.items()):
            phase = st["phase"] + (" (running)" if task in locks else "")
            last = st["history"][-1] if st["history"] else {}
            lines.append(_row(f"[{task}](comms/threads/{task}.md)", phase,
                              f"{st.get('round', 1)} / {st.get('attempt', 0)}",
                              (st.get("decision") or {}).get("status", "-"),
                              f"{last.get('at', '')} {_clip(last.get('event', ''), 70)}".strip() or "-"))
    else:
        lines.append("No task has started the orchestrated workflow yet.")
    lines.append("")

    lines += ["## Decisions", ""]
    if decisions:
        lines += ["| # | Thread | Status | Implementer | Rule |", "| --- | --- | --- | --- | --- |"]
        lines += [_row(f"[{d['number']}](decisions/{d['file']})", d["thread"], d["status"], d["implementer"],
                       _clip(d["rule"], 90)) for d in decisions]
    else:
        lines.append("No decisions recorded yet.")
    lines.append("")

    lines += ["## Threads", ""]
    if threads:
        lines += ["| Thread | Messages | Last message |", "| --- | --- | --- |"]
        for thread in threads:
            last = thread["last"]
            lines.append(_row(f"[{thread['name']}](comms/threads/{thread['name']}.md)", thread["count"],
                              f"{last[0]} · {last[1]} · {last[2]}" if last else "-"))
    else:
        lines.append("No threads yet.")
    lines.append("")
    return "\n".join(lines)


def _attention(states: dict, locks: dict, titles: dict) -> list[dict]:
    """What only the human can do next, with the exact commands."""
    items = []
    for task in sorted(states):
        st, phase = states[task], states[task]["phase"]
        title = titles.get(task, "")
        text, commands = None, []
        if phase == "needs_human":
            info = st.get("needs_human") or {}
            actions = ["retry", "reopen"]
            if info.get("resume_phase") == "proposed" and st.get("votes"):
                actions.append("accept")
            if info.get("from_phase") == "reviewing" and st.get("implementation"):
                actions.append("revise")
            text = (f"Stopped for a human: {info.get('reason', 'unknown')}. {info.get('details', '')} "
                    f"Retry resumes at {info.get('resume_phase', 'the failed step')}.").replace("  ", " ")
            commands = [f'{ORCH} resolve {task} {"|".join(actions)} --note "..."']
        elif phase in ("accepted", "changes_requested"):
            attempt = st.get("attempt", 0) + 1
            pending = [a for a in st.get("approvals", []) if not a.get("used") and a.get("attempt") == attempt]
            revising = phase == "changes_requested"
            implementer = ((st.get("implementation") or {}).get("model") if revising
                           else (st.get("decision") or {}).get("implementer")) or "the implementer"
            what = "a revision" if revising else "implementation"
            if pending:
                text = f"You approved {what} by {pending[-1].get('implementer', implementer)}. Run it when ready."
                commands = [f"{ORCH} auto {task}"]
            else:
                text = f"Waiting for your approval before {implementer} gets write access ({what}, attempt {attempt})."
                commands = [f"{ORCH} approve {task}"]
        elif phase == "ready_to_close":
            text = "Independent reviews approved and every check passed."
            commands = [f"{ORCH} close {task}", f"{ORCH} close {task} --commit"]
        elif phase in PAUSED and task not in locks:
            text = f"Paused after {phase}. Continue the workflow."
            commands = [f"{ORCH} auto {task}"]
        elif phase in TRANSIENT and task not in locks:
            text = f"Interrupted while {phase}. The next command will stop it for review."
            commands = [f"{ORCH} state {task}"]
        if text:
            items.append({"task": task, "title": title, "text": text, "commands": commands})
    return items


def _tasks(framework: Path, problems: list[str]) -> list[dict]:
    try:
        tasks = json.loads((framework / "tasks.json").read_text(encoding="utf-8"))["tasks"]
        if not isinstance(tasks, list) or not all(isinstance(t, dict) for t in tasks):
            raise ValueError("tasks must be a list of objects")
        return tasks
    except (OSError, ValueError, KeyError, TypeError) as error:
        problems.append(f"tasks.json could not be read ({error}).")
        return []


def _states(framework: Path, problems: list[str]) -> dict[str, dict]:
    states = {}
    for path in sorted((framework / "state").glob("B-*.json")):
        try:
            st = json.loads(path.read_text(encoding="utf-8"))
            if not (isinstance(st, dict) and isinstance(st.get("task"), str) and isinstance(st.get("phase"), str)
                    and isinstance(st.get("history"), list)):
                raise ValueError("not a workflow state file")
            states[st["task"]] = st
        except (OSError, ValueError) as error:
            problems.append(f"state/{path.name} could not be read ({error}).")
    return states


def _decisions(framework: Path) -> list[dict]:
    found = []
    for path in sorted((framework / "decisions").glob("[0-9][0-9][0-9][0-9]-*.md")):
        try:
            fields = dict(DECISION_FIELDS.findall(path.read_text(encoding="utf-8")))
        except OSError:
            continue
        found.append({"number": path.name[:4], "file": path.name, "thread": fields.get("Thread", "?"),
                      "date": fields.get("Date", ""), "status": fields.get("Status", "?"),
                      "implementer": fields.get("Implementer", "?"), "rule": fields.get("Rule", "")})
    return found


def _threads(framework: Path) -> list[dict]:
    rows = []
    for path in sorted((framework / "comms" / "threads").glob("*.md")):
        count, last = 0, None
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            match = HEADER.match(line)
            if match:
                count, last = count + 1, match.groups()
        rows.append({"name": path.stem, "count": count, "last": last})
    return sorted(rows, key=lambda r: (r["last"][0] if r["last"] else "", r["name"]), reverse=True)


def _locks(framework: Path) -> dict[str, str]:
    locks = {}
    for path in sorted((framework / "state" / ".locks").glob("*.lock")):
        try:
            parts = path.read_text(encoding="utf-8").split()
        except OSError:
            parts = []
        locks[path.stem] = parts[1] if len(parts) > 1 else ""
    return locks


def _latest(tasks: list, states: dict, decisions: list, threads: list) -> str:
    stamps = [str(t.get("updated", "")) for t in tasks]
    stamps += [str(st["history"][-1].get("at", "")) for st in states.values() if st["history"]
               and isinstance(st["history"][-1], dict)]
    stamps += [d["date"] for d in decisions]
    stamps += [t["last"][0] for t in threads if t["last"]]
    return max((s for s in stamps if s), default="")


def _task_line(task: dict, with_notes: bool = True) -> str:
    line = f"- **{task.get('id', '?')}** {task.get('title', '')}"
    if task.get("status") != "todo":
        line += f" ({task.get('owner') or 'unassigned'})"
    if with_notes and task.get("notes"):
        line += f". {_clip(str(task['notes']), 140)}"
    return line


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _row(*cells) -> str:
    return "| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |"
