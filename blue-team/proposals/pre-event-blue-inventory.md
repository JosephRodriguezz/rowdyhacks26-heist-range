# Blue team: inventory of work prepared before the event (draft for B-20)

Drafted 2026-10-03 by Claude for Aaron, to give Joseph, who owns the submission disclosure. Board task: B-20. **This is a draft for review, not a disclosure statement.** It lists facts from the repository so Joseph can write the disclosure in the organizer's format, which this draft has not seen.

## 1. The open fact: the event start time

**The official event start time is not recorded anywhere in the repository.** What the record does contain:

- Decision 0007 (`blue-team/decisions/0007-swarm.md`), recorded 2026-10-03T18:44:43Z (13:44 CDT), says "the RowdyHacks event has started and building has begun." That is the human's declaration, not the organizer's clock. The event may have started earlier.
- `docs/weekend/DEMO.md` and `docs/weekend/START_HERE.md` tell the team to follow the organizer's disclosure requirement and to keep the commit history so preparation work can be disclosed.
- Decision 0005 (recorded 2026-10-02) limited blue to the design spec and small disclosed prototypes before the event.

Because the start time is open, section 2 lists everything with its timestamp, and section 5 gives the one command that recomputes the "last commit before the event" for any start time Joseph confirms.

**Times are CDT (UTC-5)** unless marked Z. They are commit timestamps and state-file times, which a person with repository access could edit; the history was preserved and not rewritten while this was drafted.

## 2. Timeline of blue work, by what existed when

### A. Committed on `Mayo` before the declaration (up to commit `a5fa4a3`, 2026-10-02 18:48)

There are no commits between `a5fa4a3` and the first commit after the declaration (`90f6ad3`, 2026-10-03 14:15). So for any start time between those two moments, `a5fa4a3` is the last commit before the event.

| Commit | Date | What it added |
| --- | --- | --- |
| `5a06d9d` | 2026-09-30 23:12 | Telemetry-based access detector (`detection.py`): flags successful private-record reads by a different user or by no user. |
| `df91162` | 2026-09-30 23:20 | Session revocation proposals (`proposals.py`), labeled containment. |
| `67e0aaf` | 2026-09-30 23:35 | Ownership patch proposal (`patches.py`, `defenses/patches/ownership-fix-001/`, a **draft**) and the incident evidence report (`incident.py`, `report.py`, `frameworks.py`). |
| `52cf485` | 2026-10-01 11:58 | The multi-model orchestration framework in `blue-team/` (orchestrator, adapters, state machine, guard hooks, board). |
| `4eca327` | 2026-10-01 15:18 | `observe(context, tools)` entry point (task B-06) after five review rounds. |
| `6e244f7` | 2026-10-01 15:19 | `resolve revise` and commit-every-attempt fixes to the framework. |
| `52d2a05` | 2026-10-01 18:15 | Merge of the team kickoff kit from `codex/team-frameworks` (this is Joseph's work, merged in). |
| `adb289b`, `8fd249d` | 2026-10-01 18:21, 23:54 | Blue handoff document and swarm design discussion; mapping onto the new roster. |
| `5847bde` | 2026-10-02 00:19 | Decision 0004: blue's response principle. |
| `998944f`, `9a3c831` | 2026-10-02 14:57, 15:29 | Obsidian ignore rules and the generated `STATUS.md` dashboard. |
| `a5fa4a3` | 2026-10-02 18:48 | Decision 0005 and the swarm board tasks. |

**State of the code at `a5fa4a3`:** 105 blue test functions and 81 framework test functions (counted from the files; the handoff of that date reported 105 passing blue tests). Built: detection of cross-user and anonymous reads, revocation proposals, the draft ownership-patch proposal, the incident report, and `observe()`. Not built: any stand-in executor, any clustering or scoring, any availability signal.

### B. Existed only in the working folder on the declaration date (not yet committed)

The swarm design spec (task B-19) was drafted by Antigravity under the orchestrator. Attempts 1 to 3 started before the declaration (attempt 1 at 2026-10-02 19:13; attempt 3 at 2026-10-03 13:23). **None of it was committed until `f0b5075` on 2026-10-03 17:17**, after attempt 18 and the close. It is a design document with no code. Decision 0005 allowed a design spec before the event. The committed spec is the final text, so the earlier drafts exist only in the orchestrator's run records (`blue-team/runs/`, not committed) and the B-19 thread.

### C. Built after the declaration (2026-10-03 13:44 onward)

This is not prepared work, and is listed so the two are not mixed:

- **B-19 swarm design spec**: attempts 4 to 18 (2026-10-03 13:45 to 16:53), closed and committed as `f0b5075`.
- **Codex lane**: B-23 (retest completeness fix), B-25 (fixture-based patch tests), B-07 (stand-in executor and flow tests). Commits dated 2026-10-03 14:15 to 14:43, merged 17:18.
- **Cursor lane**: F1 adversarial tests, F2 mutation-gap tests, F3 defense docs, F4 contract requests for Diego. Commits dated 14:21 to 15:38, merged 17:18 to 17:19.
- **Framework hardening** (`f72187f`), the Codex handoff and board updates (`197c25d`, `b3e719d`), and later coordination commits.

## 3. How the work was produced (for the disclosure)

- **AI coding tools wrote and reviewed the blue code.** The board shows tasks B-01 to B-06 owned by Claude. B-01 to B-04 (detector, revocation proposals, patch proposal, incident report) were written directly with Claude before the orchestrator existed, with no model review round. B-06 (`observe`) ran through the orchestrator and took five review rounds (see `blue-team/comms/threads/B-06.md`). The framework itself (B-05) is still marked in review on the board. The B-19 spec was written by Antigravity, and reviewed by Claude and Codex. The lane work was written by Codex (B-23, B-25, B-07) and by Cursor (F1 to F4).
- **Commit authorship does not show this.** Nearly all blue commits are under one human git identity (Aaron Mayo), because the models do not commit; a human closed and committed each task. Anyone reading `git log` alone would misread who wrote the code.
- **The human approved each implementation** (recorded in each task's state file and thread), and under decision 0007 delegated B-19 revision approvals to Claude, recorded as such.
- **Models used:** Claude, Codex (`gpt-6.1-sol` for the lane and reviews later), and Antigravity. The Codex model setting changed during the work.

## 4. What this inventory does not cover

- **Shared and Red work.** `shared/contracts`, `shared/fixtures`, the arena, and the Red design branch were authored mostly by Joseph, per the commit log, and some blue code depends on them. They are not blue work and are not listed here.
- **Joseph's unpublished Blue work.** His `codex/core-orchestrator` worktree (the availability adapter and related fixes) was not seen and is not covered. It needs its own entry once it has a commit.
- **The organizer's rules and format.** I have not seen the organizer's text on prebuilt work, AI tools, or public repositories, so I cannot say which items need disclosure.
- **Uncommitted local files and the old repository.** The history before the move to the new repository was preserved in `Mayo`. The old repository was left untouched and was not re-checked for this draft.

## 5. To finish: recompute from the official start time

When the official start time is confirmed, find the last blue commit before it, with the offset included:

```bash
git log origin/Mayo --before="2026-10-03 13:00 -0500" -1 --format="%h %ad %s" --date=iso
```

Joseph records the start time and that commit. If the official start was earlier than 2026-10-02 18:48, the commits after it in section A move to the "after the event" list.
