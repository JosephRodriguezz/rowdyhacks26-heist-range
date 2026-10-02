# Red Team prototype preparation

**Owner:** Joseph. **Status:** Standalone prototype implemented; integration and measured remote-model behavior remain future work.

This packet describes the standalone Red prototype. It uses a disposable local web app to examine how Scout and Operator discover, test, and revise candidate paths toward protected synthetic vault data. It prepares the Red subsystem for possible integration during the hackathon.

- [Prototype specification](PROTOTYPE_SPEC.md) — implemented boundaries and local action, coordination, and evidence behavior.
- [Evaluation cases](EVALUATION_CASES.md) — mission, adaptation, isolation, and failure checks.
- [Joseph's role packet](../roles/JOSEPH_RED.md) — ownership and event responsibilities.
- [Project references](../REFERENCES.md) — starting material for model-readable lessons.

## Confirmed preparation scope

The prototype uses a model to select typed, allowlisted actions. Deterministic code enforces the registered local target, credentials, budgets, timeouts, and cancellation. Scout continues exploring while Operator tests evidence-backed candidates. They share one Red-only board and one enforced budget; task ownership prevents duplicate work.

The target supplies real HTTP responses, synthetic users, fresh state per run, and evaluator-private scenario variations. Red starts with the public surface and references for two ordinary accounts. The tool layer handles credentials. An evaluation harness applies simulated defenses, while Red receives the changed target responses.

The first mission and vulnerability-family scope remain those of the [project brief](../PROJECT_BRIEF.md). The larger swarm remains an expansion after the first loop works.

## Implemented build sequence and evidence

| Step | Working outcome | Evidence needed before the next step |
|---|---|---|
| 1. Resolve build settings | Python standard library; replaceable provider interface; optional OpenAI Responses adapter; bounded configuration | Defaults and hard ceilings recorded below; no provider key is stored |
| 2. Local target and evaluator | In-memory synthetic bank app, fresh state per run, three controlled flaw families, private objective evidence | Health/authorized-access preflight, repeatability and independent verdict checks pass |
| 3. Deterministic action boundary | Typed HTTP/account/form actions, fixed loopback registry, tool-owned credentials and cookie contexts | Scope, redirect, redaction, budget, timeout, cancellation, and output checks pass |
| 4. Red board and baseline | Thread-safe shared Red board, evidence refs, task claims, Scout-to-Operator handoff, survey baseline | Concurrent ownership and shared-budget tests pass |
| 5. Model-driven Scout and Operator | Optional model adapter uses strict typed proposals through the same boundary | Fixture-provider integration verifies overlap and separation; no remote model run is claimed |
| 6. Adaptation run | Hidden harness disables one local path; an alternate path can remain available | Fixture-provider run revises from the changed response and tests the alternate path |
| 7. Repeat and compare | Scenario suite emits labeled local run records; saved traces can be replayed without target requests | Baseline comparison and reset evidence are available; performance thresholds and repeated remote-model measurements remain open |
| 8. Prepare event handoff | Keep this board and executor behind prototype-only interfaces | Mapping to Diego's core and shared contracts still needs team review |

The deterministic planner is a comparison baseline for the tool and evaluation machinery. It is labeled as a baseline in every run and does not establish adaptive model capability.

## Organization

| Path | Purpose |
|---|---|
| red/prototype/ | Standalone runner, typed action boundary, optional provider adapter, Red board, deterministic baseline, and operator commands |
| red/knowledge/ | Source-linked, scenario-independent notes for authorization, sessions, and input handling |
| red/evaluation/ | Hidden scenario setup, objective checks, simulated defense schedule, and private evaluation record |
| red/prototype/lab.py | Disposable HTTP app with synthetic state, fresh per-run reset, and ordinary-user access checks |
| tests/ | Standard-library regression checks for boundaries, state, secrecy, and fixture-run coordination |

Keep hidden evaluation/target internals outside the material assembled for model prompts. The model action interface has no filesystem access.

## Implemented prototype settings

- **Action set:** read page, submit the registered contact form, bounded API GET/POST, start an account session by reference, and end an owned session.
- **Default limits:** 60 HTTP actions, 30 model calls, 180 seconds, 2 seconds per target request, 16 KiB response output, 30 seconds per model call, and 18 turns per role. Hard ceilings are 200 actions, 100 model calls, 600 seconds, 30 seconds per target request, 64 KiB output, 60 seconds per model call, and 50 turns.
- **Provider:** provider interface is replaceable. The OpenAI Responses adapter is optional; the full project's model provider remains undecided. Remote calls require explicit `--allow-remote-model` plus `OPENAI_API_KEY` and `OPENAI_MODEL`.
- **Controlled local flaws:** cross-owner record access, use of a revoked session after logout, and an in-memory SQL query built with unsafe string interpolation. Secure counterparts are checked for legitimate owner behavior.
- **Simulated defense:** disable one family or all active families after a configured action count. `all_paths_blocked` exercises the blocked outcome while owner access remains available.
- **Reset:** each `run` creates a fresh target and synthetic state from the selected seed. A standalone `serve` target resets when stopped and restarted.
- **Commands:** `python3 -m red.prototype.cli run --scenario access_control --mode deterministic_baseline --report artifacts/access.run.json`, `python3 -m red.prototype.cli replay --from artifacts/access.run.json`, `python3 -m red.prototype.cli evaluate`, and `python3 -m unittest discover -s tests -v`.

## Remaining decisions and gates

- **Joseph:** Set the repeated-run schedule and behavioral performance thresholds after measuring a real model baseline. Fixture-provider results do not count as model performance.
- **Joseph and Diego:** Review the local board/action/evidence shapes against the shared contract and target registry before event integration.
- **Team:** Select a project-wide model provider and decide whether the optional prototype adapter is appropriate for the event build.
- **Joseph:** Decide how scenario prevalence and held-out variants should be selected after the first evaluation passes.

This is a standalone local preparation artifact. It does not implement Diego's core or bank, Aaron's Blue agents, Omar's arena, a live registered network, or the integrated hackathon demo. The evaluator report has a `referee_only` `evaluation_private` object; do not forward it into Red model prompts or team-visible event streams.
