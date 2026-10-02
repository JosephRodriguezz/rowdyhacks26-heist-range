# Hackathon plan

This plan separates work that can prepare the team from the integrated contest that will be built during the event. It is a sequence of dependency gates, not a promise that every stretch goal will fit.

## Before the event: prepare the team

### All owners

- Read the project brief, architecture, role packets, and draft contracts.
- Agree on the smallest task, handoff, and event contract that lets each component work independently.
- Keep open decisions visible in the decision log instead of allowing different assumptions to spread.
- Use only synthetic, intentionally vulnerable local lab material for security experiments.

### Joseph — Red

- Study the allowed vulnerability families using the curated references.
- Define how Scout records observations and how Operator receives evidence and remaining budget.
- Propose evaluation cases for exploration, changing target behavior, and inconclusive outcomes.

### Aaron — Blue

- Inventory the existing Blue source, current behavior, tests, and run instructions.
- Mark what has been verified, what should be preserved, and what is planned.
- Map existing telemetry and response proposals to the shared contracts.

### Diego — Core and lab

- Define the lab registry, capability boundary, session lifecycle, event routing, reset, and referee interfaces.
- Identify how the three initial vulnerability families can point at one vault objective.
- Coordinate with Aaron on preserving his Blue integration and with both agent owners on safe telemetry.

### Omar — Arena

- Sketch the judge’s path through a contest and the data needed on each screen.
- Explore the 3D bank plus 2D agents direction and propose alternatives if a different approach better serves the demo.
- Keep visual and technology decisions open until the team reviews feasibility.

Pre-event plans, research, contracts, and isolated prototypes are preparation. They must not be represented as the completed integrated contest or final demo.

## During the event: build in dependency order

### Gate 1 — Agree on the wire contract

Confirm required task, handoff, event, evidence, source-mode, visibility, and status fields. Give each owner fixture examples and one negative case such as a wrong audience, unknown target, or exhausted budget.

**Pass when:** all four owners can produce or consume the same draft shapes without exposing referee-only data.

### Gate 2 — Resettable bank lab

Start one registered lab target with synthetic accounts, health status, a known baseline, and a repeatable reset. Verify ordinary access before testing the protected vault objective.

**Pass when:** an authorized user succeeds; unauthorized vault access is measured independently; reset restores the same baseline.

### Gate 3 — Core guardrails and referee

Create a session, dispatch bounded team tasks, validate handoffs, restrict tools to registry capabilities, record ordered events, cancel work, and independently evaluate the objective.

**Pass when:** unregistered destinations and cross-origin redirects are rejected; budgets and stop/reset work; referee outcomes can be achieved, not achieved, or inconclusive from target evidence.

### Gate 4 — Fixture-driven arena

Omar builds the judge flow against contract-shaped fixtures while Diego stabilizes the event stream. Identify fixtures visibly as fixtures.

**Pass when:** a judge can inspect an agent, see its task and safe evidence, follow the event order, and understand disconnected and stopped states.

### Gate 5 — Red and Blue integration

Connect Scout, Operator, Monitor, and Defender through the core. Preserve Aaron’s verified baseline behavior. Keep team boards isolated and limit Blue automation to approved reversible actions.

**Pass when:** a complete run is observable, bounded, cancelable, and does not depend on teams sharing private context.

### Gate 6 — Vault mission rehearsal

Run repeated end-to-end trials covering a successful Red path, a blocked path, Blue containment, normal authorized use, and an inconclusive condition. Compare agent claims with the independent referee.

**Pass when:** the first mission can be reset and replayed, legitimate access works, and scoring separates access, detection/response, and verified repair.

### Stretch — Availability mission

Only after Gate 6, add a separate bounded availability scenario with clear health checks, recovery, and a separate score. Show the target becoming unavailable only inside the registered lab, then show restoration. It cannot substitute for the vault mission.

## Demo fallback

- Keep a known-good lab reset and a short verified run available.
- If live agents fail, label any recorded or fixture run as such; do not present it as live.
- Preserve a direct path from the arena to the registered live lab for the vault mission.
- If the availability stretch is unstable, omit it rather than jeopardize the first mission.
