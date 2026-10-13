# Joseph — Red Team

## Mission

Build the Red side of the first vault-access contest. Red explores the registered bank lab, gathers evidence, evaluates supported paths, and adapts during the run. It should not enter with a known exploit sequence or access to the seeded answer key.

## Suggested responsibilities

- **Scout:** map reachable, in-scope behavior; formulate and prioritize hypotheses; gather and record evidence.
- **Operator:** take evidence-backed candidate paths from Scout, decide what to test next, and attempt the mission through the core’s approved capabilities.
- **Team board:** track task owner, hypothesis, evidence references, status, handoffs, and remaining budget. Keep it Red-private.
- **Evaluation:** compare exploration quality, objective progress, adaptation after Blue responses, and safe behavior across repeatable runs.

These roles may be implemented as separate model executions or another team-approved arrangement, provided the responsibilities, handoff, and evidence are visible and testable.

## Before the hackathon

- Maintain the [standalone Red prototype](../red/README.md), review its deterministic regression checks, and document observed gaps before integration.
- Read the project brief, architecture, integration contracts, and evaluation plan.
- Study the supplied OWASP references for the initial integrated families and the [six-family standalone preparation catalog](../red/VULNERABILITY_CATALOG.md). Review additional bank families with Diego and Aaron before depending on them in joint runs.
- Propose bounded exploration and ranking criteria. Separate observed facts from hypotheses and confirmed findings.
- Review the target/action contract with Diego and the team. Identify the evidence Red needs without requesting hidden ground truth.
- Use the [integration readiness checklist](../red/INTEGRATION_READINESS.md) to map the local prototype to core-owned targets, actions, tasks, evidence, and referee records.
- Write down a small set of evaluation cases for normal exploration, inconclusive results, a Blue containment event, and a blocked route.

Preparation can include research, plans, and isolated prototypes. The integrated contest and final demo are built during the hackathon.

## During the event

1. Connect to the core using the agreed Red task, handoff, and evidence shapes.
2. Explore only the assigned registered target and capabilities; respect action budgets, timeouts, and cancellation.
3. Record evidence references and confidence for each hypothesis. Do not treat an attempted request or an error response as a verified vulnerability.
4. Hand promising, evidence-backed paths from Scout to Operator with remaining budget and any dependencies.
5. Reassess when target observations change after Blue response. Do not read or infer private Blue plans through unauthorized channels.
6. Report objective evidence to the referee path; do not claim success based solely on the agent’s interpretation.

## Acceptance checks

- Red can complete a run without any fixed path or seeded vulnerability answer being supplied to it.
- Red’s exploration, evidence, selection rationale, and handoff are visible in its private board and safe arena fields.
- Operator can choose among supported, evidence-backed paths and adjust after a target response changes.
- Red cannot address unregistered destinations, exceed core-enforced budgets, bypass cancellation, or receive Blue/referee-only data.
- The result distinguishes attempted, evidence-backed, and independently verified outcomes.
- Repeated evaluation runs record enough detail to compare objective progress, evidence quality, safety violations, and budget use.

## Dependencies and handoffs

- Diego owns the target registry, tool capabilities, session identity, event order, and referee interface.
- Aaron owns the Blue event view; Red does not depend on Blue exposing its private board.
- Omar consumes only arena-approved Red events and evidence summaries.
- Changes to task or handoff fields are coordinated through the shared contract.
