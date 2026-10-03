# 0007: swarm

- Thread: swarm
- Date: 2026-10-03T18:44:43Z
- Status: accepted
- Implementer: none
- Recorded by: human
- Rule: Approved by the human.

## Outcome

The event has started and building proceeds. Decided by the human on 2026-10-03, answering the questions Claude put in chat.

1. The RowdyHacks event has started and building has begun. This lifts the rule in decision 0005 that no new blue code is written until Joseph confirms the organizer's rules on pre-built code. The rest of decision 0005 stands. B-20 now covers only disclosing the work prepared before the event.

2. The first release of blue is staged. Deterministic Monitor and Defender agents, each reporting its own status, ship first. The AI advisor layer follows, through a model-call tool supplied by core, once the interface is agreed with Diego (B-12). The advisor may only rank and explain proposals that deterministic code produced, a labeled deterministic fallback covers any model failure, and decision 0004 still governs who executes.

3. B-19 (the swarm design spec) is finished first. For B-19 only, Claude may resolve valid review findings, send the task back for revision, and approve each revision without asking, until both reviewers approve and every check passes. Claude stops at ready_to_close; closing, committing, and pushing stay with the human. Each approval records that Claude executed it under this authorization. The Codex model is gpt-6-astra for now.

4. The human may hand well-bounded tasks to Codex by hand in a separate clone, never in the main working folder while an orchestrated run is active (see blue-team/CODEX_LANE.md). That work returns as a branch that Claude fetches, reviews, tests, and merges between runs.

## Positions

| Participant | Stance | Reason |
| --- | --- | --- |
| human | agree | Decided by Aaron (Blue) in chat on 2026-10-03 |

## Security objections

None.
