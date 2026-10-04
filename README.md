# Heist Range (working title)

An adaptive Red Team vs. Blue Team cyber range for RowdyHacks 2026, built around a fictional bank and a protected vault.

**Status:** Bank website, standalone Red prototype, local access-control core, a browser availability demo on a disposable fixture, and a separately verified full-bank Docker Desktop rehearsal on loopback port 3001. The current demo priority is bounded availability and verified recovery, then defacement. The existing port-3000 bank, adaptive Red decisions, arena integration, and model performance remain unverified.

## Start here

- [Run the browser demo](docs/core/DEMO.md) — one-command local presenter with live request metadata, Red load, Blue response, referee verdict, stop/reset, and retained history; Omar's arena is optional.
- [Disposable full-bank rehearsal](docs/core/DISPOSABLE_BANK.md) — separate Docker Desktop bank on port 3001, measured limits, actual Blue observation, and an independent recovery check.
- [Repository agent instructions](AGENTS.md) — project boundaries, safety rules, owners, and current checks.
- [Ubuntu bank walkthrough](docs/UBUNTU_BANK_LAB.md) — install Docker, transfer the prototype, configure credentials, start/reset the bank, and open it through SSH.
- [Local Docker Desktop walkthrough](docs/LOCAL_DOCKER_DESKTOP.md) — run an independent bank copy on Windows for isolated development.
- [Bank availability handoff](docs/BANK_AVAILABILITY_HANDOFF.md) — fixed registration, opt-in capacity exercise, bounded core adapter, and independent fixture verification.
- [Project brief](docs/PROJECT_BRIEF.md) — objective, first mission, scope, and non-goals.
- [Architecture](docs/ARCHITECTURE.md) — system boundaries, control flow, and information separation.
- [Team brief](docs/TEAM_BRIEF.md) — copy-ready project message for Discord.
- [Role packets](docs/roles/README.md) — responsibilities, preparation, event work, and acceptance checks.
- [Red prototype preparation](docs/red/README.md) — standalone prototype boundaries, evaluation cases, and build sequence.
- [Red integration readiness](docs/red/INTEGRATION_READINESS.md) — what works locally and what Joseph, Diego, and Aaron need to connect.
- [Integration contracts](docs/INTEGRATION_CONTRACTS.md) — draft task, handoff, event, target, and referee records.
- [Runnable local core](docs/core/README.md) — shared-session Red/Blue integration, loopback controls/SSE, SQLite, and independent containment/retry checks.
- [Core availability runbook](docs/core/AVAILABILITY.md) — run the connected disposable slice, private evidence, precise limits, and remaining live-bank gate.
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

This opt-in component preserves the access-control interface. Core now calls its
actual detector in the disposable bank-library availability slice. The deployed
Next.js bank remains unconnected. See the [Blue handoff](backend/app/agents/blue/AVAILABILITY.md)
for trusted client registration, calibration, recovery checks and remaining demo work.
Python standard library only; no API credentials are needed.

```sh
PYTHONPATH=backend python3 -m unittest discover -s backend/tests/blue -v
PYTHONPATH=backend python3 -m app.agents.blue.availability_replay
```

The replay emits fixture-only proposals, not live traffic or a verified recovery.

With Node.js and the locked dependencies installed in `apps/bank-lab`, run
`python3 -m core.cli availability`. This starts and stops only an owned ephemeral
loopback target, uses synthetic credentials, runs actual Blue detection and
approved training-route limiting, and persists an independent fixture recovery
assessment. See the [runbook](docs/core/AVAILABILITY.md) for commands and boundaries.

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

These names identify current coordination contacts, not additional approval barriers for authorized work. Start with two specialist agents per side.

## Bank website prototype

`apps/bank-lab` provides a Next.js/TypeScript website and PostgreSQL-backed API. It includes synthetic customer accounts, server-side vault authorization, expiring sessions, health checks, private target events, and a separate operator reset. The default baseline preserves bank authorization. A local-only opt-in SQL injection training search is restricted to synthetic fixture records, and `/monitor` shows bounded, sanitized API request metadata. The availability variant adds measured training capacity, private load/probe/executor roles, target-side aggregates, and a temporary positive source rate. The core browser connection is verified on disposable HTTP/PGlite fixtures. A separate local runner now exercises the full Docker bank with actual Blue observation and independent recovery evidence; the existing bank and arena remain unconnected.

For a local Windows copy, follow [the Docker Desktop walkthrough](docs/LOCAL_DOCKER_DESKTOP.md). For Ubuntu setup, follow [the full walkthrough](docs/UBUNTU_BANK_LAB.md), including its Docker installation and private credential setup. From the project root, after creating `.env.bank-lab`:

```sh
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml up --build -d
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml run --rm operator node scripts/reset.mjs
curl --fail --silent --show-error http://127.0.0.1:3000/api/health
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml run --rm operator node scripts/verify.mjs http://bank:3000
```

The Nginx proxy binds to `127.0.0.1:3000`; PostgreSQL and the bank app have no published ports. The bank and database remain on internal Docker networks with no general Internet route from the bank app. On Ubuntu, use the walkthrough's SSH tunnel to reach the local proxy. Reset invalidates existing sessions, restores synthetic balances, rotates the bank run ID and vault record, and clears raw events. Preserve any events needed for evaluation before resetting.

An opt-in SQL injection training variant is available only in the local Docker Desktop walkthrough. Its intentionally unsafe search runs with a dedicated role that can read only synthetic training fixtures; it does not weaken login, account ownership, or vault authorization. Keep the scenario on the local loopback-bound copy.

To demonstrate it, set `BANK_SCENARIO=sqli-training` and a unique `BANK_TRAINING_DB_PASSWORD` in the private `.env.bank-lab`, recreate the local stack and run the operator reset and baseline verification commands from the walkthrough. Then query `http://127.0.0.1:3000/api/training/search?term=identity` and compare it with a URL-encoded `term=' OR TRUE --`. Return to `BANK_SCENARIO=baseline` and recreate the stack to disable the route. Reset clears bank state/events and invalidates sessions; preserve needed evidence first.

The separate local request monitor is available at `http://127.0.0.1:3000/monitor`. It shows sanitized API method, route, status, and latency from a bounded in-memory buffer. It does not capture packets or request contents; see the Docker Desktop walkthrough for a low-rate 20-request display exercise.

Local source checks with Node.js 24 and pnpm 11.19.0:

```sh
cd apps/bank-lab
pnpm install --frozen-lockfile --ignore-scripts
pnpm test
pnpm build
```

Tests use embedded PostgreSQL (PGlite) to check authorization, sessions, reset, event sanitization, database permissions, origin validation, and bounded request parsing. The production Next.js build also checks TypeScript. These checks do not replace the live Docker/PostgreSQL verification command on Ubuntu or an independent contest referee.

`pnpm test:availability` runs the availability module and disposable HTTP integration checks, including two repeated degradation/mitigation/recovery slices and ordinary authorized access during continuing bounded load. The fixture responder is explicit test code, not a live Blue agent. Real-bank traffic stays disabled until the exact registration, isolated scope, healthy calibration, limits, and verification criteria are approved; follow [the handoff](docs/BANK_AVAILABILITY_HANDOFF.md).
