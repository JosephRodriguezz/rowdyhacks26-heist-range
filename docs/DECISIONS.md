# Decision log

This file records decisions that shape the project. Update it when the team makes a material change; include the reason, owner, and affected contracts/role packets.

## Confirmed

| Decision | Resolution |
|---|---|
| Event theme and product direction | Heist-themed adaptive Red vs. Blue cyber range around a fictional bank and vault. |
| Intended submission repository | This new repository is the planned submission repo. Its GitHub slug is a working identifier; the product name is undecided. |
| Initial target | A purpose-built, resettable bank website/API with synthetic accounts and controlled weaknesses. WebGoat is a learning reference, not the contest target. |
| Access-control objective | Red reaches protected vault data; an independent referee determines whether the objective was achieved. This remains a separate scenario and is not implied by an availability incident. |
| Initial vulnerability families | Broken access control, authentication/session weakness, and input handling are candidate paths toward the same vault objective. The scenario answer remains hidden from Red and Blue. |
| Red and Blue independence | Each team gets a separate board and limited context. Blue receives sanitized target telemetry, not Red plans/findings. |
| Agent roles | Red Scout and Operator; Blue Monitor and Defender. Start with two specialist executions per side and expand after the first loop works. |
| Core responsibility | Deterministic control plane owns session lifecycle, registered targets, dispatch, budgets, tool execution boundaries, events, stop/reset, and referee integration. |
| Disposable availability connection | Authorized separate integration branch joins the published bank and core baselines. Use an opt-in Node bank-library fixture bridge, actual Blue availability detection, narrow positive training-source limits, canonical private persistence and independent fixture recovery. No live-bank option, adaptive-model claim or live arrest is added. |
| Current team ownership | Joseph â†’ Blue; Aaron â†’ Red; Diego â†’ core and bank lab; Omar â†’ arena. This supersedes the original pre-event owner mapping while retaining the technical role boundaries. |
| Blue foundation | Aaronâ€™s existing Blue implementation remains the technical baseline. Joseph now owns Blue; preserve tested behavior and verify source/tests before extending it. |
| Arena direction | 3D bank environment with 2D agents is the starting vision. Omar can revise the component proposal and pitch alternatives. No framework or renderer is selected. |
| Demo scenario order (AV-01) | DDoS/availability incident and recovery first; site defacement second. This changes demo priority, not the access-control objective or its evidence. No scoreboard or winning-team claim. A live recovery claim requires measured degradation on an isolated registered bank, Blue response, and independent ordinary-access checks passing within team-calibrated limits while bounded load continues. Otherwise report inconclusive and use only a clearly labeled replay. |
| Local core preparation slice | Joseph approved a reusable Python core, CLI, authenticated loopback controls/SSE, SQLite state and ordered evidence, adapters for the Red workers and pinned Mayo Blue runtime, real local session revocation, and independent containment/retry evaluation. The deterministic fixture-provider run is the correctness baseline; model mode is opt-in. This access-control preparation does not connect Diegoâ€™s event bank, the Blue availability adapter, or Omarâ€™s arena. |
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
| Red hypothesis investigation | Joseph confirmed persistent candidate evidence, predictions, and status history. Scout may hand off unproven candidates; Operator conclusions require a baseline/comparison. New contradictory observations reopen the same candidate as inconclusive and require fresh tests. Code validates structure and provenance; the model interprets observations and the referee decides mission success. |
| Current team routing | Joseph handles Blue, Aaron handles Red, and Diego handles bank/core. Current user authorization removes ownership as a blocker for bank integration; existing workspaces and the Blue guard remain protected. |
| Availability mission | Current user direction begins a separate bounded availability integration slice now. It does not pass a vault gate or count as vault access. Real-bank traffic needs its own calibrated isolated approval. |
| Bank preparation prototype | At Diego's request, prepare a Next.js/TypeScript bank with PostgreSQL and Docker Compose for his Oracle Ubuntu 24.04 x86-64 server. Start with an authorized baseline, private SSH browser access, synthetic data, and operator-only reset; this does not select the other owners' stacks or implement the integrated contest. |

## Open decisions

- Product name and visual identity.
- Arena framework, rendering engine, asset style, and interaction model.
- Project-wide language, hosting/deployment arrangement, model provider, and agent framework. The prototype's Python implementation and optional adapter do not decide these for the event build.

- Overall language, final hosting/deployment arrangement, model provider, and agent framework. The isolated bank preparation stack is recorded above.
- Exact capability names, event enums, and transport for the draft contracts.
- Held-out lab variations and scenario weights for the three initial families.
- Repetition counts and model-performance thresholds after obtaining a real model baseline.
- Which narrow Blue containment actions may run automatically; patches and broader changes remain review-gated.

- Exact real-bank calibrated load limits, latency/access criteria, and approval evidence for the availability slice; engineering ceilings and test profiles do not approve traffic.
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
| 2026-10-03 | Added the standalone Red hypothesis ledger, typed updates, prediction-bearing handoffs, comparison guards, reopening history, and focused lifecycle/fixture checks. | Make candidate testing and reassessment inspectable without allowing agent conclusions to determine the objective. Real-model improvement remains unmeasured. | `red/`, `tests/`, README, AGENTS, Red specification/evaluation/readiness |
| 2026-10-04 | Reassigned Joseph to Blue and Aaron to Red; set bounded DDoS/availability recovery as the first demo scenario and defacement second (AV-01). Published the local core preparation slice and its runbook as a reviewable baseline. | Match current team ownership and demo priority while keeping the access-control core distinct, preserving independent verification, and avoiding claims of Diego-bank or arena integration. | AGENTS, README, role index, decisions, core runbook, integration contracts, Red readiness |
| 2026-10-03 | Added the isolated bank website baseline and an Ubuntu deployment walkthrough. | Give Diego a concrete, resettable target foundation for later core/agent integration. Controlled weaknesses and contest adapters remain future work. | README, AGENTS, Ubuntu walkthrough, prototype interface notes in contracts |
| 2026-10-04 | After the core branch was published at `99bc29c`, connect the availability seam to core and Blue on an owned HTTP/PGlite fixture. Preserve both source histories and the pinned Mayo snapshot; leave dirty original workspaces untouched. | Prove bounded dispatch, genuine target measurements, positive source-rate enforcement, continuing ordinary access and durable private assessment before activating a deployed-bank adapter. | Core availability runtime/runbook, bank target telemetry/limiter, contracts, checks |
| 2026-10-03 | Added an opt-in local SQL injection training fixture and sanitized live API request monitor to the bank preparation prototype. | Provide bounded training/evidence surfaces without changing baseline bank authorization or selecting the availability mission. Core and team adapters remain future work. | README, AGENTS, local Docker walkthrough, bank API and monitor contracts |
| 2026-10-04 | Follow current direction to begin availability integration in a separate bank branch; supply opt-in measured capacity, fixed `bank-lab` registration, bounded adapter/executor, and independent evidence checks. Keep both original checkouts untouched. | Resolve the Red `bank-local` mismatch explicitly and prove a repeatable disposable backend slice before live calibration or UI work. The real core/Blue connection and live traffic are still gated. | README, AGENTS, availability handoff, bank interface notes |
