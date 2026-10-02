# Mayo branch roadmap

Branch `Mayo` holds the blue-team work for RANGE (Member 4). Claude, Codex, and Antigravity build it together under [AGENTS.md](AGENTS.md), coordinated by a deterministic orchestrator ([ARCHITECTURE.md](ARCHITECTURE.md)). Live status is in [CHECKLIST.md](CHECKLIST.md).

## End goal

In a clean live run, blue detects the cross-user read from telemetry alone and proposes containment, which is shown to block the original session. It flags the fresh-session retry, proposes the ownership patch with full provenance, and produces an incident report whose evidence anyone can verify. The referee independently confirms that the fix blocks unauthorized access and that owners keep access to their own orders.

## Scope

**In scope:** `backend/app/agents/blue/`, `backend/tests/blue/`, `defenses/`, and this `blue-team/` folder. Also proposals to teammates about the interfaces blue depends on.

**Out of scope:** Diego's core, referee, executor, shared contracts, and bank lab; Joseph's red team; and Omar's arena. Blue reads their work and proposes changes in `comms/threads/handoffs.md`. It never edits their files.

## Milestones

| Milestone | Exit criteria | Tasks |
| --- | --- | --- |
| **M1: Complete on the fixture** | Detection, containment proposal, patch proposal, incident report, `observe()`, and a stand-in executor all run end to end on the shared fixture, with tests that fail when the code is wrong | B-01 to B-11 |
| **M2: Ready to integrate** | Diego accepts the interfaces (blue context, previous defenses, executor results, report endpoint, swarm actions and events). The patch is finalized against Diego's order handler. Armor data and labels are handed to Omar. Mayo is joined into the new repository's main once the team decides how. | B-12 to B-16 |
| **M3: Live demo gate** | Every blue item on the integration checklist's live demo gate passes from a clean reset, and a live incident report is produced | B-17 |
| **Swarm design** (decision 0005) | The design spec is written, the requests to teammates are sent, and Joseph has confirmed the organizer's rules on pre-built code. Blue starts with two characters, a Monitor and a Defender; the full swarm is a separate mode built after a successful demo. Build tasks come from the spec. | B-19, B-20 |
| **Ongoing** | The strategy thread is reviewed at least once per milestone and accepted ideas become tasks or handoffs | B-18 |

## Dependencies on teammates

| Needed from | What | Blocks |
| --- | --- | --- |
| Whole team | A decision on how Mayo joins the new repository's main (all of it, or only blue's folders) | B-16 |
| Diego (lab) | The order handler file and its stable patch surface; canary records, a decoy endpoint, login and session telemetry, a hashed `client_ref` | B-13, B-17, B-19 |
| Diego (core) | Blue context shape, executor results, refusal of draft patches, report endpoint, windowed telemetry, new swarm actions and events | B-12, B-17 |
| Omar | Show the armor slots, the per-path threat model, and two blue characters (swarm mode later), with the heist labels | B-14 |
| Joseph | The organizer's rules on pre-built code, AI tools, and public repositories | B-20 |

## Standing questions for the strategy thread

- **More secure:** Can isolation be enforced by structure rather than by convention? For example, a blue context type that cannot hold red events, or telemetry hashed at the source.
- **More efficient:** Can blue run incrementally on new telemetry only? Can tests and the report share fixtures? Are we duplicating work another member already does?
- **More effective:** Which detections, labels, and report sections help a judge understand the defense fastest? What would make a failed fix obvious?

## Risks

- The lab's handler location is unknown until Member 3 ships, so the patch stays a draft.
- Contract changes happen on Member 2's schedule. Blue keeps adapters thin so it can follow.
- Model CLIs change their flags. `orchestrate.py doctor` checks them against `config.json`, and `doctor --live` confirms each read-only mode.
- Model agreement is advisory. Tests, isolation, and escalation to the human are the controls that matter.
