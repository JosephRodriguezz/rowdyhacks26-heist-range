# Heist Range (working title)

An adaptive Red Team vs. Blue Team cyber range for RowdyHacks 2026, built around a fictional bank and a protected vault.

**Status:** Planning foundation, a standalone Red prototype, a runnable local access-control core slice, and opt-in Blue availability preparation. The current demo priority is a bounded DDoS/availability incident and verified recovery, then defacement. Diego's bank integration, the arena, and real-model performance remain unverified; the local core does not yet run the DDoS scenario against Diego's bank.

## Start here

- [Repository agent instructions](AGENTS.md) — project boundaries, safety rules, owners, and current checks.
- [Project brief](docs/PROJECT_BRIEF.md) — objective, first mission, scope, and non-goals.
- [Architecture](docs/ARCHITECTURE.md) — system boundaries, control flow, and information separation.
- [Team brief](docs/TEAM_BRIEF.md) — copy-ready project message for Discord.
- [Role packets](docs/roles/README.md) — responsibilities, preparation, event work, and acceptance checks.
- [Red prototype preparation](docs/red/README.md) — standalone prototype boundaries, evaluation cases, and build sequence.
- [Red integration readiness](docs/red/INTEGRATION_READINESS.md) — what works locally and what Joseph, Diego, and Aaron need to connect.
- [Integration contracts](docs/INTEGRATION_CONTRACTS.md) — draft task, handoff, event, target, and referee records.
- [Runnable local core](docs/core/README.md) — shared-session Red/Blue integration, loopback controls/SSE, SQLite, and independent containment/retry checks.
- [Blue availability preparation](backend/app/agents/blue/AVAILABILITY.md) — deterministic HTTP-flood detection, temporary source limiting, independent recovery checks, and actual-bank integration requirements.
- [Hackathon plan](docs/HACKATHON_PLAN.md) — pre-event preparation and event build sequence.
- [Evaluation plan](docs/EVALUATION_PLAN.md) — safe, evidence-based iteration criteria.
- [References](docs/REFERENCES.md) — learning and verification resources.
- [Decision log](docs/DECISIONS.md) — confirmed choices and open questions.

## Run the standalone Red prototype

For the runnable shared-session preparation loop, run `python3 -m core.cli run`. It uses the actual Scout/Operator workers and Mayo's unchanged Blue runtime, with explicitly scripted fixture decisions driving real local HTTP and real session revocation. It is integration evidence, not adaptive-model performance. Presenter controls are available with `python3 -m core.cli serve` after privately configuring `HEIST_CORE_TOKEN`; see the [core runbook](docs/core/README.md).

The prototype uses Python's standard library and starts its target on `127.0.0.1`. Each run creates a fresh synthetic bank state. Its six controlled families cover access control, session lifecycle, input handling, mass assignment, traversal in virtual document storage, and export workflow bypass. The [lab catalog](docs/red/VULNERABILITY_CATALOG.md) describes the investigative techniques and secure counterparts.

```sh
python3 -m red.prototype.cli run --scenario access_control --mode deterministic_baseline --report artifacts/access.run.json
python3 -m red.prototype.cli replay --from artifacts/access.run.json
python3 -m red.prototype.cli evaluate
python3 -m red.prototype.cli scenarios
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests -p 'test_hypoth*.py' -v
```

To inspect the target in a browser, run `python3 -m red.prototype.cli serve --scenario clean`; stop and restart the command to reset it. The model-driven mode uses an optional OpenAI Responses adapter and makes no provider request unless `--mode model --allow-remote-model` is supplied with `OPENAI_API_KEY` and `OPENAI_MODEL` configured. The provider remains replaceable and is not selected for the full project. Run records label local HTTP, deterministic-baseline, model, and simulated-defense activity; evaluator-only scenario details are stored under `evaluation_private` and never added to Red's model context.

The deterministic baseline surveys the site, compares account access, checks logout behavior, and exercises ordinary document/export flows. It does not attempt every supported exploit; `not_achieved` in a baseline run is not proof that a scenario is secure. The unit suite checks the six controlled flaws and their defenses. The separate core slice joins both teams against this disposable bank; it does not connect Diego's bank or verify real-model performance. The standalone runner still creates its own local target and remains independently runnable.

Model-mode candidates now retain supporting evidence, a prediction, and a status history in the Red-only board. Scout can hand off an unproven candidate. Operator must cite a successful ordinary baseline and a later controlled comparison before recording a supported or rejected assessment. New contradictory observations reopen the same candidate as inconclusive; both baseline and comparison must then be fresh. Run records and replay include this history. Code validates references, ordering, ownership, and required comparison fields; the model interprets response content, and the independent referee determines mission success. The focused tests use typed fixture providers and local HTTP; they do not measure real-model improvement.

## Verify Blue availability preparation

This separate opt-in component preserves the access-control interface. It has been
tested using bounded real HTTP against a loopback reference bank; Diego's bank and
the existing core are not wired to it yet. See the [Blue handoff](backend/app/agents/blue/AVAILABILITY.md)
for trusted client registration, calibration, recovery checks and remaining demo work.
Python standard library only; no API credentials are needed.

```sh
PYTHONPATH=backend python3 -m unittest discover -s backend/tests/blue -v
PYTHONPATH=backend python3 -m app.agents.blue.availability_replay
```

The replay emits fixture-only proposals, not live traffic or a verified recovery.

## Mission

The current demo sequence is a bounded availability incident and recovery first, then site defacement. Red operates only through approved tools against a registered isolated lab. Blue responds independently to permitted evidence, and a referee verifies ordinary access during continuing bounded load before recovery is claimed. The access-control/vault preparation scenario remains separate; an outage is never proof of vault access.

The separate access-control/vault scenario must preserve legitimate bank access and distinguish attempted attacks, verified vulnerabilities, applied responses, and fixes that pass a retest. It is not the current first demo scenario; an availability outage does not count as vault access.

## Safety boundaries

- Run security tools only against registered, isolated lab targets we control; never use arbitrary external targets.
- Use synthetic accounts and resettable lab state.
- Keep Red, Blue, and referee contexts separate. Only the referee sees seeded vulnerability ground truth.
- Enforce permissions, budgets, timeouts, and cancellation outside the models.
- Keep automatic Blue responses narrow and reversible; review broader changes and retest fixes.
- Label fixture and live events accurately. The arena must reflect recorded activity.

## Team ownership

- **Joseph — Blue Team:** Monitoring, evidence-backed response, and integration of the existing Blue baseline.
- **Aaron — Red Team:** Scout and Operator roles; exploration, evidence, and adaptive task handoff.
- **Diego — Core and bank lab:** Control plane, registered target boundary, resettable fictional bank website/API, and independent referee.
- **Omar — Arena:** Judge-facing event and agent view. A 3D bank with 2D agents is the starting visual direction; component layout and technology are proposals, not mandates.

Integrate the bounded availability/recovery slice before defacement. Keep additional specialists and vulnerability families out of the demo path until the chosen scenario is repeatable.
