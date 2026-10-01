# Blue-team multi-model framework

Claude, Codex, and Antigravity build the blue team on the `Mayo` branch. A deterministic Python orchestrator runs the workflow: models propose, vote, implement, and review, and their replies are evidence it checks. You approve write access and close tasks. [ARCHITECTURE.md](ARCHITECTURE.md) explains the design, and [AGENTS.md](AGENTS.md) is the rulebook every model follows.

## One-time setup

```sh
python blue-team/bin/guard.py install          # enable the git guardrails in this clone
python blue-team/bin/orchestrate.py doctor     # check tools, sign-in, git state, files, config
```

Each CLI must be installed and signed in: `claude` (Claude Code), `codex` (OpenAI Codex CLI), and `agy` (Antigravity CLI). `doctor` reports each as READY, WARNING, NOT INSTALLED, or MISCONFIGURED. Antigravity has no sign-in status command, so it shows WARNING until it is used. `doctor --live` makes one real read-only call per model. It confirms the reply format and that read-only mode really blocks writes.

## Running a task

```sh
python blue-team/bin/orchestrate.py auto B-06 --dry-run   # see the plan; no model is called
python blue-team/bin/orchestrate.py auto B-06             # runs until it needs you
python blue-team/bin/orchestrate.py approve B-06          # give the implementer write access once
python blue-team/bin/orchestrate.py auto B-06             # implement, review, run checks
python blue-team/bin/orchestrate.py close B-06            # show what would be committed
python blue-team/bin/orchestrate.py close B-06 --commit   # commit it; push yourself
```

`auto` stops at every human step. It never approves for you, never commits, and never pushes. If it stops for a security objection, a tie, an unreadable reply, too few reviewers, failed checks, or an unexpected file change, run `orchestrate.py escalations` and see [recovering from a failed run](ARCHITECTURE.md#recovering-from-a-failed-run).

Other commands:
- `strategy`: a read-only round on more secure, efficient, and effective blue work across the project.
- `discuss <thread> "<question>"`: ask every model a question in a thread.
- `state B-06`: show a task's phase and recent history.
- `resolve B-06 retry|reopen|accept --note "..."`: answer an escalation.

## Who does what

| Model | Default role |
| --- | --- |
| Claude | Facilitates discussion and drafts decision summaries (not votes); isolation-sensitive implementation; evidence reasoning |
| Codex | Implementation, tests, test-gap analysis, refactoring, end-to-end validation |
| Antigravity | Broad repository and cross-branch analysis, research, threat modeling, integration consistency review |

These are defaults. Change them in [roles/](roles/) and `policy` in [config.json](config.json). The orchestrator picks the implementer from the proposals, and you confirm it when you approve.

## Safety at a glance

| Rule | Enforced by |
| --- | --- |
| Only the orchestrator changes workflow state | `state.py`; replies must match `schemas/` |
| Security objection or tie goes to you | `state.evaluate_votes` |
| No write access without your approval for that decision and attempt | `state.consume_approval` |
| No self-review; at least 2 independent reviewers | `state.evaluate_reviews` |
| Reviewers cannot edit | Read-only CLI modes, plus run snapshots |
| No writes outside `backend/app/agents/blue/`, `backend/tests/blue/`, `defenses/` | Run snapshots (`watch.py`) |
| No commits, branch switches, or git config changes by models | CLI settings, run snapshots, git hooks |
| Commits only on `Mayo` and in blue paths; append-only records | `pre-commit` hook |
| Pushes only `Mayo` to `origin`, never forced or deleted | `pre-push` hook |
| Failed checks block closing | `run_checks_phase` |

The hooks apply to everyone using this clone, including you. To commit elsewhere, run `python blue-team/bin/guard.py uninstall` first and `install` again afterwards.

## Files

| Path | What it is |
| --- | --- |
| `AGENTS.md`, `ARCHITECTURE.md` | Rules for models; design for people |
| `ROADMAP.md`, `CHECKLIST.md`, `tasks.json` | Scope and goal; live task board (edit with `board.py`) |
| `roles/`, `prompts/`, `schemas/` | Role cards, phase instructions, reply formats |
| `config.json` | Branch, paths, checks, policy, and each CLI's commands |
| `state/`, `decisions/`, `comms/threads/` | Workflow state, decision records, and threads (shared memory) |
| `bin/` | `orchestrate.py`, `state.py`, `adapters.py`, `watch.py`, `replies.py`, `board.py`, `guard.py` |
| `hooks/` | Git hooks that call `guard.py` |
| `tests/` | Framework tests, using fake CLIs (no model quota) |
| `runs/` | Local prompts and raw CLI output (not committed) |
