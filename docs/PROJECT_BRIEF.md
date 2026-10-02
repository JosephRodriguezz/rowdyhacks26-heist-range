# Project brief

## Working concept

Build an adaptive, heist-themed cyber range for a live Red Team vs. Blue Team contest. The target is a purpose-built, fictional bank website/API running in an isolated, resettable lab. The demo should let judges see how Red investigates, how Blue responds independently, and what the referee can verify.

The GitHub repository name is a working identifier. The product name is not decided.

## Outcome for the first complete mission

The mission objective is to access protected vault data in the lab. Red is not given a fixed exploit sequence. It receives observations from the registered target, investigates the supported vulnerability families, records evidence, compares viable paths, and adapts to Blue’s responses.

Blue receives its permitted target telemetry without Red’s task board, hypotheses, or private agent messages. It investigates, records evidence, and responds while the run is active. The referee evaluates the mission from its own protected context; it does not rely on Red’s or Blue’s claim of success.

The first target scenario is intended to exercise three families: broken access control, authentication or session weakness, and input handling. They are paths toward one objective, not three separate success conditions. The vulnerability answers stay hidden from both teams.

## Demo experience

- A judge starts one contest and can pause, stop, or reset the lab.
- The arena shows actual agent roles, current tasks, status, and recorded events.
- Selecting an agent exposes its current task and evidence references; it must not invent activity to make the visualization look busy.
- Selecting the bank or vault opens the live lab target so a second screen can show its behavior.
- The judge can see the referee’s final verdict and the evidence category supporting it.
- The visual starting point is a 3D bank space with 2D characters. Omar can suggest another visual approach before the team commits; no framework is selected here.

## Initial swarm shape

The initial design has two specialist executions on each side:

- Red Scout explores and records evidence; Red Operator assesses promising routes and attempts the mission.
- Blue Monitor analyzes permitted telemetry; Blue Defender proposes or performs a bounded response.

These are role boundaries, not a requirement to deploy four separate servers or a particular agent framework. The team may adjust how the roles are hosted while keeping task ownership, context isolation, and evidence traceability.

## Scope

### In the first mission

- One registered, synthetic-data bank lab with reset and health checks.
- One vault-access objective with the three supported vulnerability families above.
- A control plane that starts the session, schedules work, enforces tool and budget limits, records events, and supports cancellation.
- Separate Red and Blue work boards and a referee-only ground-truth context.
- A judge interface that distinguishes fixture events from live events.
- A referee that distinguishes attempts, verified access, defenses, and verified fixes.

### Later or optional

- A separate availability-disruption and recovery mission, after the access mission works.
- More vulnerability families, agent roles, and registered lab targets.
- Registered lab networks beyond the initial website/API target.
- More elaborate arena movement, animation, or effects, provided they continue to reflect actual events.

### Out of scope

- Attacking real third-party websites, networks, accounts, or devices.
- Agent-selected arbitrary destinations or cross-origin redirects.
- A scripted attack path presented as adaptive investigation.
- Treating a service outage as proof that vault data was accessed.
- Giving Red, Blue, or the arena the referee’s hidden vulnerability answers.

## Principles for judging success

1. **Objective evidence:** A mission result is based on observable lab state and referee evidence, not self-reported agent success.
2. **Fair separation:** Blue can act during the contest without receiving Red’s private plans; Red can adapt to observations available at the target boundary.
3. **Safe execution:** Target registration, tool permissions, budgets, timeouts, cancellation, and reset are enforced by the core.
4. **Useful defense:** A defense must block unauthorized behavior while preserving authorized behavior. Failed logins and timeouts are inconclusive.
5. **Honest presentation:** The arena marks whether data is fixture, recorded, or live and shows only events the system actually produced.
6. **Incremental scope:** Make the first access mission reliable before adding more agents, targets, or the availability mission.
