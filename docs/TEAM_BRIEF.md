# Discord team brief

Copy-ready project update. The repository is currently private, so teammates will need Joseph to grant access before they can open it.

**Status:** The role assignments and vault-first demo sequence in this original brief are superseded. Current direction is Joseph → Blue, Aaron → Red, DDoS/availability recovery first, then defacement, with no winning-team scoreboard. See [the decision log](DECISIONS.md) and [current DDoS handoff](DDOS_DEMO_HANDOFF.txt); do not forward the older text below as the current plan.

---

## RowdyHacks project: adaptive heist cyber range

We’re building a Red Team vs. Blue Team contest around a fictional bank and protected vault. Red investigates the registered lab and chooses a path based on evidence; Blue independently monitors and responds during the run. The arena will help judges follow agent work, inspect evidence, and open the live bank target.

**First mission:** reach protected vault data. Keep normal bank access working. Availability disruption and recovery can be a separate follow-up scenario; an outage does not count as vault access.

### Roles

- **Joseph — Red Team:** Build a Scout to explore and record evidence, then an Operator to evaluate promising paths and attempt the heist. Red adapts during the run instead of following a fixed attack script.
- **Aaron — Blue Team:** Extend the Blue implementation already underway. Build around a Monitor that analyzes sanitized telemetry and a Defender that recommends or performs bounded, reviewable responses. Blue does not see Red’s private plans or findings.
- **Diego — Core and bank lab:** Build the control plane that starts/stops sessions, dispatches bounded agent tasks, enforces registered-target/tool limits, records events, supports cancellation/reset, and connects an independent referee. Build the separate, resettable bank website/API with synthetic accounts and controlled vulnerabilities.
- **Omar — Arena:** Build the judge-facing view of agent roles, tasks, status, events, and the live target. A 3D bank with 2D agent characters is the starting visual direction; Omar can revise the component proposal and pitch alternatives before the team commits. His technology choices remain open.

### First-scope boundaries

- Start with two specialist roles per team. Add more agents after the first contest loop works.
- The first lab scenario centers on one vault objective with broken access control, authentication/session weakness, and input handling as supported paths.
- Keep Red, Blue, and referee information separate. Only the referee sees seeded scenario truth.
- Run security tools only against our registered, isolated lab. Use synthetic data and enforce permissions, budgets, timeouts, and cancellation outside the models.
- Distinguish attempts, verified findings, applied defenses, and fixes that passed retest. A fix must preserve authorized access.
- Label fixtures and recorded runs accurately; never present them as live activity.

### Before the event / during the event

**Before:** align on the draft task/event contracts, inventory Aaron’s current Blue behavior/tests, research the curated references, sketch the bank/core boundaries, and explore the arena direction. Plans and isolated prototypes are preparation; we should not arrive with the finished integrated contest or final demo.

**During:** make the bank lab resettable, connect it through the core, integrate Red and Blue through their separate task/event views, and connect the arena. Prove the vault mission end to end before attempting the separate availability scenario.

### Repo

Planning repo: https://github.com/JosephRodriguezz/rowdyhacks26-heist-range

The project name and implementation choices remain open. Start with the README and role packets; shared draft contracts and acceptance checks are in the docs. Ask Joseph for repository access.

---
