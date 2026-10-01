# Thread framework: How the three models work together

### 2026-10-01T04:52:19Z | claude | proposal

I set up the multi-model framework at Member 4's request. Rules: blue-team/AGENTS.md. Roles: blue-team/roles/. Automation: blue-team/bin/orchestrate.py. Guardrails: git hooks that call blue-team/bin/guard.py.

Gemini and Codex: in your first session, please review three things and post a position here.
1. Your role card. Does it match what you do well? Propose edits.
2. The task flow and decision rule in AGENTS.md (majority of voting models; any security objection goes to the human).
3. The read and write commands for your CLI in config.json. Correct any flag that is wrong for your current version.

Known limits: only Claude Code is installed on this machine so far. Until Gemini and Codex are installed, decisions are made by Claude and the human.

### 2026-10-01T04:52:21Z | claude | decision

Decision 0001 recorded: **accepted**. Approved by the human.

Adopt the multi-model framework on Mayo: shared rules in blue-team/AGENTS.md, roles per model, task board and threads stored as files on the branch, decisions by majority of voting models with security objections escalated to the human, and git-hook guardrails that limit writes to Mayo and the blue paths. Gemini and Codex review it in their first session; changes go through a new decision.

Record: blue-team/decisions/0001-framework.md

### 2026-10-01T06:35:37Z | claude | proposal

Migration to the deterministic architecture (decision 0002):

- Models are now Claude, Codex, and Antigravity (agy). The Gemini CLI is retired.
- bin/state.py owns workflow state. Votes, reviews, approvals, and checks are counted by code from schema-checked replies.
- bin/adapters.py wraps each CLI. Every flag comes from config.json and was checked against the installed --help.
- bin/watch.py snapshots the repository around every model run and stops the task on any branch, HEAD, ref, git config, or out-of-bounds file change.
- Human gates: approve before write access; close --commit to commit. Pushing stays manual.
- The root AGENTS.md, CLAUDE.md, and GEMINI.md are untouched. Small AGENTS.md files in the blue folders point to blue-team/AGENTS.md.

Codex and Antigravity: please review this in your first orchestrated round. Changes go through a new decision.

### 2026-10-01T06:35:37Z | human | decision

Decision 0002: **accepted**. Approved by the human.

Record: blue-team/decisions/0002-framework.md

### 2026-10-01T06:48:55Z | claude | status

Live read-only smoke test (doctor --live, one call per CLI, 2026-10-01):

- claude 2.1.286: write denied by permissions; structured reply ok (14s, about 0.37 USD).
- codex 0.159.3: the read-only sandbox blocked the write at the OS level (UnauthorizedAccess); structured reply ok through --output-schema (226s).
- antigravity 1.2.14: no write. Two findings: --disable-slash-commands silently disabled --mode plan, and headless mode ends the run with an empty response whenever it auto-denies a permission. Fixed: the flag is removed, Antigravity is told to use file tools only, and an empty response now counts as a failed call. Antigravity's reply format is not yet confirmed live.

### 2026-10-01T16:44:24Z | claude | status

Antigravity live re-check (2026-10-01): with --mode plan now active, the write was blocked (it replied 'write blocked: mode is read-only') and no probe file was created (86s). The reply carried the schema-checked JSON in structured_output, while response held two JSON objects in a row. The adapter now uses structured_output first, and the parser reads the first complete JSON object. Re-checking the saved output with the fixed adapter gives a valid vote. All three CLIs have now shown read-only enforcement live.
