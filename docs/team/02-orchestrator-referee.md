# Member 2 — Orchestration, referee, and integration

## Mission

Connect all four modules and make outcomes trustworthy. Own deterministic lifecycle control, API contracts, persistence, independent verification, and the final integrated launch command.

## Own

`backend/app/api/`, `backend/app/core/`, `backend/app/orchestration/`, `backend/app/tools/`, `backend/app/evaluation/`, `backend/app/main.py`, backend package/bootstrap files, `backend/tests/core/`, `shared/`, `scripts/`, `tests/integration/`, and root configuration. Do not rewrite the red/blue implementations or their tests.

## Build in order

1. Implement the shared API and a fixture adapter, so Member 1 can connect immediately.
2. Implement the fixed target registry, scoped credentials, HTTP tool, and input validation. Agent tools accept target IDs and relative paths only.
3. Add SQLite state and transactional event persistence, SSE reconnect, idempotent action IDs, and one-active-assessment enforcement.
4. Provide small in-process `RedAgent` and `BlueAgent` interfaces. Pass limited role-specific contexts. Keep agent code separate from scheduler control.
5. Implement the independent ownership-policy verifier using fresh sessions and both positive and negative controls. Do not delegate the verdict to the discovering model.
6. Register Member 3's lab and red agent. Connect Member 4's blue alert/proposal logic and bounded defense adapters.
7. Implement patch version tracking and retests. A patch result cannot update referee verdicts by itself.
8. Add cancellation, per-step timeouts/request budgets, partial outcomes, reset coordination, and scenario-scoped metrics.
9. Own root Docker Compose and the clean-reset integration test. Add exact dependency, setup, and test commands to the repository.

## Referee boundaries

The evaluator may load ground truth, but it must never inject it into red or blue prompts. The human-visible dashboard may show post-verification conclusions; the team's model contexts remain separately scoped. Blue detection consumes telemetry before confirmed findings are supplied for later explanation.

## Done when

- Contract-compatible APIs and fixture SSE work before live agents are available.
- Invalid destinations and origin-changing redirects cannot escape the lab.
- Repeated action IDs do not apply a defense twice; a reused ID with different content is rejected.
- Unsupported candidates are rejected, tool failures are inconclusive, and proven candidates are independently verified.
- Reset is refused while work is active; stopping cancels queued work and bounds in-flight work.
- A service outage never counts as a successful fix.
- One clean integrated run reaches verified retest results with complete evidence.

## Verification and handoff

Run `python3 scripts/check_handoff.py --self-test`. Add core/security/state tests and a full live integration command. Publish interface changes through a coordinated contract PR. The integration checklist is docs/team/INTEGRATION.md.

## Starter prompt

> Implement Member 2's work packet in docs/team/02-orchestrator-referee.md. Read AGENTS.md and the shared contract first. Own backend orchestration, API, fixed-destination tools, SQLite/SSE, independent referee, and integration. Provide fixture-compatible endpoints before live agents exist. Preserve the red/blue directory boundaries and limit each team's context. Use deterministic access-policy tests for verdicts. Coordinate contract changes and deliver the integrated run and test commands.
