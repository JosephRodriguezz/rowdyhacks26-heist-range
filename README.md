# Heist Range (working title)

An adaptive Red Team vs. Blue Team cyber range for RowdyHacks 2026, built around a fictional bank and a protected vault.

**Status:** Planning foundation plus a standalone Red preparation prototype. The integrated contest and final demo will be built during the hackathon. The project name and arena implementation remain open for the team to decide.

## Start here

- [Repository agent instructions](AGENTS.md) — project boundaries, safety rules, owners, and current checks.
- [Project brief](docs/PROJECT_BRIEF.md) — objective, first mission, scope, and non-goals.
- [Architecture](docs/ARCHITECTURE.md) — system boundaries, control flow, and information separation.
- [Team brief](docs/TEAM_BRIEF.md) — copy-ready project message for Discord.
- [Role packets](docs/roles/README.md) — responsibilities, preparation, event work, and acceptance checks.
- [Red prototype preparation](docs/red/README.md) — standalone prototype boundaries, evaluation cases, and build sequence.
- [Red integration readiness](docs/red/INTEGRATION_READINESS.md) — what works locally and what Joseph, Diego, and Aaron need to connect.
- [Red deployment](docs/red/DEPLOYMENT.md) — running the Red prototype on a machine other than the one it was built on, with or without Docker.
- [Integration contracts](docs/INTEGRATION_CONTRACTS.md) — draft task, handoff, event, target, and referee records.
- [Hackathon plan](docs/HACKATHON_PLAN.md) — pre-event preparation and event build sequence.
- [Evaluation plan](docs/EVALUATION_PLAN.md) — safe, evidence-based iteration criteria.
- [References](docs/REFERENCES.md) — learning and verification resources.
- [Decision log](docs/DECISIONS.md) — confirmed choices and open questions.

## Run the standalone Red prototype

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

The deterministic baseline surveys the site, compares account access, checks logout behavior, and exercises ordinary document/export flows. It does not attempt every supported exploit; `not_achieved` in a baseline run is not proof that a scenario is secure. The unit suite checks the six controlled flaws and their defenses. No real-model performance or integrated Red/Blue contest has been verified. By default the runner creates its own local target; connecting Diego's bank requires the integration work described above.

AV-05 optionally selects an already-running prototype server by origin. The server must be in the
same Python process, with matching scenario/seed and fresh evaluation state. It retains ownership of
its lifecycle; the runner uses the actual serving `LabState` and makes real HTTP requests. For example,
run this from the repository root to exercise the CLI switch:

```sh
python3 -c "from red.prototype.lab import LabState, LocalBankServer; from red.prototype.cli import main; server = LocalBankServer(LabState('availability')).start(); main(['run', '--scenario', 'availability', '--target-origin', server.origin]); server.close()"
python3 -m unittest discover -s tests -p 'test_external_target.py' -v
```

Embedded callers can instead use `PrototypeRunner(RunOptions(scenario_id='availability',
external_target_origin=server.origin)).run()` inside the server's context manager. The flag is accepted
only by `run`; a standalone invocation pointing at a separate `serve` process fails explicitly.
No substitute state is fabricated, no external reset is claimed, and no real bank integration is
implemented. Create a fresh server/state before each run; keep the origin on `http://127.0.0.1:PORT`.

Model-mode candidates now retain supporting evidence, a prediction, and a status history in the Red-only board. Scout can hand off an unproven candidate. Operator must cite a successful ordinary baseline and a later controlled comparison before recording a supported or rejected assessment. New contradictory observations reopen the same candidate as inconclusive; both baseline and comparison must then be fresh. Run records and replay include this history. Code validates references, ordering, ownership, and required comparison fields; the model interprets response content, and the independent referee determines mission success. The focused tests use typed fixture providers and local HTTP; they do not measure real-model improvement.

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
