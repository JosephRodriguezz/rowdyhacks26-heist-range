# 0002: framework

- Thread: framework
- Date: 2026-10-01T06:35:37Z
- Status: accepted
- Implementer: claude
- Recorded by: human
- Rule: Approved by the human.

## Outcome

Migrate the blue-team framework to a deterministic orchestrator with Claude, Codex, and Antigravity: a state machine owns workflow state; adapters per CLI driven by config.json; run snapshots for write boundaries; schema-checked replies that fail closed; security objections and ties escalate to the human; at least 2 independent reviewers; human approval before write access; human-only close and push; no Blue-specific changes to the shared root AGENTS.md. Codex and Antigravity review it in their first orchestrated round.

## Positions

| Participant | Stance | Reason |
| --- | --- | --- |
| human | agree | Approved in chat on 2026-10-01 (delete root CLAUDE.md: yes; min reviewers: 2; remove --push and --yes: yes; live smoke test: yes) |
| claude | agree | Implemented it; Codex and Antigravity have not reviewed it yet |

## Security objections

None.
