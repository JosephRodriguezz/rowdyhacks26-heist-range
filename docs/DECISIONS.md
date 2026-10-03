# Decision log

This file records decisions that shape the project. Update it when the team makes a material change; include the reason, owner, and affected contracts/role packets.

## Confirmed

| Decision | Resolution |
|---|---|
| Event theme and product direction | Heist-themed adaptive Red vs. Blue cyber range around a fictional bank and vault. |
| Intended submission repository | This new repository is the planned submission repo. Its GitHub slug is a working identifier; the product name is undecided. |
| Initial target | A purpose-built, resettable bank website/API with synthetic accounts and controlled weaknesses. WebGoat is a learning reference, not the contest target. |
| First objective | Red reaches protected vault data; an independent referee determines whether the objective was achieved. |
| Initial vulnerability families | Broken access control, authentication/session weakness, and input handling are candidate paths toward the same vault objective. The scenario answer remains hidden from Red and Blue. |
| Red and Blue independence | Each team gets a separate board and limited context. Blue receives sanitized target telemetry, not Red plans/findings. |
| Agent roles | Red Scout and Operator; Blue Monitor and Defender. Start with two specialist executions per side and expand after the first loop works. |
| Core responsibility | Deterministic control plane owns session lifecycle, registered targets, dispatch, budgets, tool execution boundaries, events, stop/reset, and referee integration. |
| Blue foundation | Aaron’s existing Blue implementation is to be extended. Its actual source, tests, and behaviors must be inventoried before making preservation claims. |
| Arena direction | 3D bank environment with 2D agents is the starting vision. Omar can revise the component proposal and pitch alternatives. No framework or renderer is selected. |
| Availability mission | A bounded outage/recovery scenario is separate and comes only after the vault mission works. |
| Preparation | Planning, references, contracts, and preparation may happen before the hackathon; the completed integrated contest/final demo is built during the event. |
| Safety boundary | Security actions run only against registered isolated lab targets, with synthetic data, deterministic policy, budgets, timeouts, cancellation, and evidence. |
| Repository agent setup | Tailor the portable-agent-toolkit guidance to this project's instructions and retain its six selected workflow skills. This supports team planning and later implementation without adding runtime product code. |
| Red preparation deliverable | Define boundaries and evaluation cases, then build a standalone prototype independently of Diego's unfinished core/bank interfaces. |
| Red model/action boundary | A model chooses typed, allowlisted actions; deterministic code enforces target scope and budgets. A deterministic planner may serve as a labeled comparison baseline. |
| Red prototype target and starting access | Use a small disposable local web app with synthetic users, real HTTP responses, resettable state, and hidden variations. Red receives public access plus two ordinary account references; the tool layer handles credentials. |
| Red role overlap | Scout keeps exploring after an evidence-backed handoff while Operator tests candidates. One private board, shared enforced budget, and task ownership prevent duplicate work. |
| Prototype adaptation evaluation | The harness applies a labeled simulated defense; Red responds to changed target observations. Score revised hypotheses, justified alternatives, and supported blocked/inconclusive outcomes independently of vault success. |
| Red prototype implementation | Use Python's standard library, a loopback HTTP server, and in-memory SQLite to keep preparation independent from Diego's core. |
| Red prototype provider | Keep the provider replaceable. Add an optional OpenAI Responses adapter with strict typed actions, explicit remote-call opt-in, and no project-wide provider selection. |
| Red prototype limits | Start at 60 HTTP actions, 30 model calls, 180 seconds, 2-second target requests, 16 KiB response output, 30-second model calls, and 18 turns per role; enforce hard ceilings. |
| Red prototype local scenarios | Exercise cross-owner object access, stale access after logout, and a synthetic SQL query flaw with secure counterparts; use a labeled surface-survey comparison baseline. |
| Red preparation expansion | Joseph requested additional lab families and investigative techniques. Add mass assignment, traversal in virtual synthetic document storage, and export approval bypass with secure counterparts and evidence checks. This extends the standalone lab; event integration requires Joseph, Diego, and Aaron to agree on capabilities and telemetry. |

## Open decisions

- Product name and visual identity.
- Arena framework, rendering engine, asset style, and interaction model.
- Project-wide language, hosting/deployment arrangement, model provider, and agent framework. The prototype's Python implementation and optional adapter do not decide these for the event build.
- Exact capability names, event enums, and transport for the draft contracts.
- Held-out lab variations and scenario weights for the three initial families.
- Repetition counts and model-performance thresholds after obtaining a real model baseline.
- Which narrow Blue containment actions may run automatically; patches and broader changes remain review-gated.
- Whether to add the availability mission in the event, based on the reliability of the first mission.
- GitHub visibility and collaborator access before team-wide implementation/submission. The repo is currently private.
- Expansion plan for additional agents, vulnerability families, and registered network labs.
- Shared mapping of the six-family preparation catalog, local profile/export fields, and defense-state observations into Diego's bank/core; joint Red/Blue verification before integrated readiness claims.

## Change record

| Date | Decision/change | Rationale | Affected docs |
|---|---|---|---|
| 2026-10-02 | Created the planning foundation, role packets, shared contracts, and tailored agent workflow setup in the new submission repo. | Give each owner shared direction and safe preparation guidance without building the final integrated demo before the event. | README, AGENTS, project brief, architecture, contracts, role packets, hackathon plan, evaluation plan, agent skills |
| 2026-10-02 | Recorded confirmed Red prototype choices and drafted its local interface, evaluation cases, and build sequence. | Make Red preparation concrete before adding runnable code or integrating the team's components. | Red preparation packet, Joseph role packet, README |
| 2026-10-02 | Built the standalone loopback Red prototype, deterministic baseline, optional typed model adapter, private evaluator record, and regression harness. | Validate local policy and Red coordination before event integration without claiming a live model result. | `red/`, `tests/`, README, AGENTS, Red specification/evaluation, references |
| 2026-10-02 | Expanded the local lab to six families and added investigation lessons, defended state checks, and a core/Blue integration checklist. | Prepare additional adaptive investigation options while retaining synthetic targets and independent evidence; no shared contract or event bank implementation is selected by this extension. | `red/`, `tests/`, README, Red specification/evaluation/catalog/readiness, references |
