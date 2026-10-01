# Four-person build framework

Build four separately testable modules in one repository. Use separate clones and branches, then combine through small pull requests. Do not create four incompatible applications.

| Member | Ownership | First working handoff | Branch |
| --- | --- | --- | --- |
| [1 — Arena and UI](01-arena-ui.md) | `frontend/`, `docs/design/`, `docs/UI_DESIGN.md` | Character arena replaying the shared fixture | `codex/member-1-ui` |
| [2 — Orchestrator and referee](02-orchestrator-referee.md) | Backend core, shared contracts, integration and root infrastructure | API + ordered event stream + independent verifier | `codex/member-2-core` |
| [3 — Red team and lab](03-red-team-lab.md) | `backend/app/agents/red/`, `cyber_range/`, related tests | Resettable lab + structured attack candidate | `codex/member-3-red` |
| [4 — Blue team and defenses](04-blue-team-defense.md) | `backend/app/agents/blue/`, `defenses/`, related tests | Telemetry-based alert + reviewable defense proposal | `codex/member-4-blue` |

Working roster: Joseph → Member 1, Aaron → Member 2, Diego → Member 3, Omar → Member 4. Names are confirmed; roles are provisional until kickoff. See the [24-hour kickoff guide](../weekend/START_HERE.md).

Member numbers are role assignments, not experience rankings. Member 2 is the integration owner, not the only person who tests integration.

## Shared foundation

- [Interface contract](../../shared/contracts/README.md): tool boundaries, API commands, events, and result semantics.
- [Machine-readable vocabulary](../../shared/contracts/v1.json): field names and event payload requirements.
- [Sample run](../../shared/fixtures/demo-run.json): one explicitly synthetic event/evidence sequence for independent development.
- [Integration checklist](INTEGRATION.md): merge order and live acceptance checks.

Run the handoff checker from the repository root:

```sh
python3 scripts/check_handoff.py --self-test
```

This checks the starter contract and sample run. It is not a substitute for each module's functional tests.

## How each person starts

Merge the starter-kit PR into `main` before teammates create their branches, so all four start from the same contract revision.

```sh
git clone https://github.com/JosephRodriguezz/RowdyHacks26.git
cd RowdyHacks26
git switch -c codex/member-1-ui  # use your assigned branch from the table
```

Read `AGENTS.md`, your work packet, and the shared contract. Paste the work packet's starter prompt into your coding assistant if desired. Build the smallest working handoff first; use fixtures for unavailable neighbors.

## Merge rules

1. One owner per directory. Request another owner's change instead of silently editing their module.
2. Member 2 owns shared contracts, root Compose, backend dependencies, `.env.example`, and integration scripts. Member 1 owns frontend dependencies. Explain requested dependency changes in the PR.
3. Shared changes need a coordinated contract PR with updated fixtures before callers depend on them. Do not rename events or fields locally.
4. Return results through the agreed interfaces. Agents do not write the database, SSE stream, or UI state directly.
5. Submit small PRs against `main`; all four branches are intended to integrate continuously, not at the deadline.
6. Before merging, update from `main`, run the handoff check plus your module checks, and have the receiving teammate exercise your interface.
7. A PR lists delivered behavior, exact checks run, sample input/output, new dependencies, and remaining limitations.

## Suggested time allocation

Spend the first 10% agreeing on contracts and getting all four independent demos running. Connect the lab, backend, and UI during the next 35%. Add defense and retesting during the next 30%. Reserve the final 25% for integration, resets, failure handling, and rehearsals. Treat these as planning targets, not promises about implementation time.

## Scope for all four members

One website/API, two ordinary users, one ownership flaw, one protected control endpoint, one containment action, one durable fix. Start with guided rounds. Character art may be playful, but outcomes and security claims must be grounded in real evidence.
