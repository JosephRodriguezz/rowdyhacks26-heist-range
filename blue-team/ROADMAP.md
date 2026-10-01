# Mayo branch roadmap

Branch `Mayo` holds the blue-team work for RANGE (Member 4). Claude, Codex, and Antigravity build it together under [AGENTS.md](AGENTS.md), coordinated by a deterministic orchestrator ([ARCHITECTURE.md](ARCHITECTURE.md)). Live status is in [CHECKLIST.md](CHECKLIST.md).

## End goal

In a clean live run, blue detects the cross-user read from telemetry alone and proposes containment, which is shown to block the original session. It flags the fresh-session retry, proposes the ownership patch with full provenance, and produces an incident report whose evidence anyone can verify. The referee independently confirms that the fix blocks unauthorized access and that owners keep access to their own orders.

## Scope

**In scope:** `backend/app/agents/blue/`, `backend/tests/blue/`, `defenses/`, and this `blue-team/` folder. Also proposals to teammates about the interfaces blue depends on.

**Out of scope:** the lab (Member 3), core, the referee, the executor, and shared contracts (Member 2), and the frontend (Member 1). Blue reads their work and proposes changes in `comms/threads/handoffs.md`. It never edits their files.

## Milestones

| Milestone | Exit criteria | Tasks |
| --- | --- | --- |
| **M1: Complete on the fixture** | Detection, containment proposal, patch proposal, incident report, `observe()`, and a stand-in executor all run end to end on the shared fixture, with tests that fail when the code is wrong | B-01 to B-11 |
| **M2: Ready to integrate** | Member 2 accepts the interfaces (blue context, previous defenses, executor results, report endpoint). The patch is finalized against Member 3's handler. Labels are handed to Member 1. Mayo is up to date with main. | B-12 to B-16 |
| **M3: Live demo gate** | Every blue item on the integration checklist's live demo gate passes from a clean reset, and a live incident report is produced | B-17 |
| **Ongoing** | The strategy thread is reviewed at least once per milestone and accepted ideas become tasks or handoffs | B-18 |

## Dependencies on teammates

| Needed from | What | Blocks |
| --- | --- | --- |
| Whole team | Merge PR #1 so Mayo can update from main | B-16 |
| Member 3 | The lab's order handler file and its stable patch surface | B-13, B-17 |
| Member 2 | Blue context shape, executor results, refusal of draft patches, report endpoint | B-12, B-17 |
| Member 1 | A report download in the evidence panel | after B-12 |

## Standing questions for the strategy thread

- **More secure:** Can isolation be enforced by structure rather than by convention? For example, a blue context type that cannot hold red events, or telemetry hashed at the source.
- **More efficient:** Can blue run incrementally on new telemetry only? Can tests and the report share fixtures? Are we duplicating work another member already does?
- **More effective:** Which detections, labels, and report sections help a judge understand the defense fastest? What would make a failed fix obvious?

## Risks

- The lab's handler location is unknown until Member 3 ships, so the patch stays a draft.
- Contract changes happen on Member 2's schedule. Blue keeps adapters thin so it can follow.
- Model CLIs change their flags. `orchestrate.py doctor` checks them against `config.json`, and `doctor --live` confirms each read-only mode.
- Model agreement is advisory. Tests, isolation, and escalation to the human are the controls that matter.
