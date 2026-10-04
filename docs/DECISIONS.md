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
| Current team routing | Joseph handles Blue, Aaron handles Red, and Diego handles bank/core. Current user authorization removes ownership as a blocker for bank integration; existing workspaces and the Blue guard remain protected. |
| Arena direction | 3D bank environment with 2D agents is the starting vision. Omar can revise the component proposal and pitch alternatives. No framework or renderer is selected. |
| Availability mission | Current user direction begins a separate bounded availability integration slice now. It does not pass a vault gate or count as vault access. Real-bank traffic needs its own calibrated isolated approval. |
| Preparation | Planning, references, contracts, and preparation may happen before the hackathon; the completed integrated contest/final demo is built during the event. |
| Safety boundary | Security actions run only against registered isolated lab targets, with synthetic data, deterministic policy, budgets, timeouts, cancellation, and evidence. |
| Repository agent setup | Tailor the portable-agent-toolkit guidance to this project's instructions and retain its six selected workflow skills. This supports team planning and later implementation without adding runtime product code. |
| Bank preparation prototype | At Diego's request, prepare a Next.js/TypeScript bank with PostgreSQL and Docker Compose for his Oracle Ubuntu 24.04 x86-64 server. Start with an authorized baseline, private SSH browser access, synthetic data, and operator-only reset; this does not select the other owners' stacks or implement the integrated contest. |

## Open decisions

- Product name and visual identity.
- Arena framework, rendering engine, asset style, and interaction model.
- Overall language, final hosting/deployment arrangement, model provider, and agent framework. The isolated bank preparation stack is recorded above.
- Exact capability names, event enums, and transport for the draft contracts.
- Exact hidden lab variations and scenario weights for the three initial families.
- Which narrow Blue containment actions may run automatically; patches and broader changes remain review-gated.
- Exact real-bank calibrated load limits, latency/access criteria, and approval evidence for the availability slice; engineering ceilings and test profiles do not approve traffic.
- GitHub visibility and collaborator access before team-wide implementation/submission. The repo is currently private.
- Expansion plan for additional agents, vulnerability families, and registered network labs.

## Change record

| Date | Decision/change | Rationale | Affected docs |
|---|---|---|---|
| 2026-10-02 | Created the planning foundation, role packets, shared contracts, and tailored agent workflow setup in the new submission repo. | Give each owner shared direction and safe preparation guidance without building the final integrated demo before the event. | README, AGENTS, project brief, architecture, contracts, role packets, hackathon plan, evaluation plan, agent skills |
| 2026-10-03 | Added the isolated bank website baseline and an Ubuntu deployment walkthrough. | Give Diego a concrete, resettable target foundation for later core/agent integration. Controlled weaknesses and contest adapters remain future work. | README, AGENTS, Ubuntu walkthrough, prototype interface notes in contracts |
| 2026-10-03 | Added an opt-in local SQL injection training fixture and sanitized live API request monitor to the bank preparation prototype. | Provide bounded training/evidence surfaces without changing baseline bank authorization or selecting the availability mission. Core and team adapters remain future work. | README, AGENTS, local Docker walkthrough, bank API and monitor contracts |
| 2026-10-04 | Follow current direction to begin availability integration in a separate bank branch; supply opt-in measured capacity, fixed `bank-lab` registration, bounded adapter/executor, and independent evidence checks. Keep both original checkouts untouched. | Resolve the Red `bank-local` mismatch explicitly and prove a repeatable disposable backend slice before live calibration or UI work. The real core/Blue connection and live traffic are still gated. | README, AGENTS, availability handoff, bank interface notes |
