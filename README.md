# Heist Range (working title)

An adaptive Red Team vs. Blue Team cyber range for RowdyHacks 2026, built around a fictional bank and a protected vault.

**Status:** Planning foundation plus a bank website preparation prototype. The integrated contest and final demo will be built during the hackathon. The project name and arena implementation remain open for the team to decide.

## Start here

- [Repository agent instructions](AGENTS.md) — project boundaries, safety rules, owners, and current checks.
- [Ubuntu bank walkthrough](docs/UBUNTU_BANK_LAB.md) — install Docker, transfer the prototype, configure credentials, start/reset the bank, and open it through SSH.
- [Local Docker Desktop walkthrough](docs/LOCAL_DOCKER_DESKTOP.md) — run an independent bank copy on Windows for isolated development.
- [Project brief](docs/PROJECT_BRIEF.md) — objective, first mission, scope, and non-goals.
- [Architecture](docs/ARCHITECTURE.md) — system boundaries, control flow, and information separation.
- [Team brief](docs/TEAM_BRIEF.md) — copy-ready project message for Discord.
- [Role packets](docs/roles/README.md) — responsibilities, preparation, event work, and acceptance checks.
- [Integration contracts](docs/INTEGRATION_CONTRACTS.md) — draft task, handoff, event, target, and referee records.
- [Hackathon plan](docs/HACKATHON_PLAN.md) — pre-event preparation and event build sequence.
- [Evaluation plan](docs/EVALUATION_PLAN.md) — safe, evidence-based iteration criteria.
- [References](docs/REFERENCES.md) — learning and verification resources.
- [Decision log](docs/DECISIONS.md) — confirmed choices and open questions.

## Mission

Red explores a registered bank lab, gathers evidence, and chooses an approach during the run. Blue independently monitors permitted telemetry and responds while the contest is active. An independent referee determines whether Red reached the protected vault data.

The first mission must preserve legitimate bank access and distinguish attempted attacks, verified vulnerabilities, applied responses, and fixes that pass a retest. A bounded availability-disruption scenario may follow as a separate mission; an outage does not count as vault access.

## Safety boundaries

- Run security tools only against registered, isolated lab targets we control; never use arbitrary external targets.
- Use synthetic accounts and resettable lab state.
- Keep Red, Blue, and referee contexts separate. Only the referee sees seeded vulnerability ground truth.
- Enforce permissions, budgets, timeouts, and cancellation outside the models.
- Keep automatic Blue responses narrow and reversible; review broader changes and retest fixes.
- Label fixture and live events accurately. The arena must reflect recorded activity.

## Team ownership

- **Joseph — Red Team:** Scout and Operator roles; exploration, evidence, and adaptive task handoff.
- **Aaron — Blue Team:** Extend the existing Blue implementation into monitoring and bounded response, preserving tested behavior.
- **Diego — Core and bank lab:** Control plane, registered target boundary, resettable fictional bank website/API, and independent referee.
- **Omar — Arena:** Judge-facing event and agent view. A 3D bank with 2D agents is the starting visual direction; component layout and technology are proposals, not mandates.

Start with two specialist agents per side. Expand the roster and vulnerability catalog only after the vault mission works end to end.

## Bank website prototype

`apps/bank-lab` provides a Next.js/TypeScript website and PostgreSQL-backed API. It includes synthetic customer accounts, server-side vault authorization, expiring sessions, health checks, private target events, and a separate operator reset. The default baseline preserves bank authorization. A local-only opt-in SQL injection training search is restricted to synthetic fixture records, and `/monitor` shows bounded, sanitized API request metadata. Core adapters, Red/Blue agents, and referee/arena integration are not implemented.

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
