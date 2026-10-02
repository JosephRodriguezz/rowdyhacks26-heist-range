# Diego — Core and bank lab

## Mission

Own the system boundary that makes the contest safe, observable, repeatable, and gradable. The **core** is the control plane, not just the bank website: it controls sessions and task dispatch, validates registered target/capability use, enforces budgets and cancellation, records and routes events, and asks an independent referee to evaluate the objective.

Own the purpose-built bank website/API as a distinct component and milestone. It is a synthetic, deliberately vulnerable lab target that can be reset to a known baseline.

## Before the hackathon

- Review the project brief, architecture, integration contracts, and acceptance checks.
- Inventory the current Aaron Blue source and its integration needs with Aaron; identify what the core must preserve or adapt.
- Draft the target registry entry shape, allowed capability names, session lifecycle, reset/health behavior, and referee input/output.
- Confirm the three initial vulnerability families can lead to the single vault objective while the answer key remains referee-only.
- Identify the smallest event/task contract slice that Red, Blue, and Omar can all prepare against.
- Propose implementation technologies based on team familiarity and event constraints; document choices without expanding the agreed product scope.

Planning, local isolated spikes, and contracts can happen before the event. The integrated contest and final demo are built during it.

## During the event: separate milestones

### Bank lab milestone

1. Create the fictional bank surface, synthetic accounts, protected vault objective, and scenario reset.
2. Provide deterministic baseline checks for authorized and unauthorized access.
3. Add the initial controlled vulnerability families and target telemetry needed for Blue.
4. Ensure the lab can be restarted/reset and reports health before a session.

### Core milestone

1. Create a session against one registered lab target.
2. Dispatch bounded team-specific tasks and validate task ownership/handoffs.
3. Route tool actions only through registered targets and capabilities; reject arbitrary origins and cross-origin redirects.
4. Enforce time/action budgets, timeouts, cancellation, pause, stop, and reset outside the models.
5. Record ordered events and evidence references, then route Red, Blue, judge-safe, and referee-only views separately.
6. Evaluate the vault objective from lab state and independent evidence. Provide an inconclusive result for missing or ambiguous proof.

## Acceptance checks

- The bank lab starts healthy, uses synthetic data, and resets to a reproducible baseline.
- Authorized user access succeeds in the baseline and after a fix; the protected vault remains inaccessible to unauthorized users.
- The registry rejects unknown targets and the tool layer cannot be redirected outside the registered origin.
- Session budgets, timeouts, cancellation, stop, and reset are enforced even when an agent misbehaves or returns late.
- A task handoff cannot alter the sender’s permissions or exceed remaining budget.
- Red cannot read Blue-private or referee-only records; Blue cannot read Red-private plans; arena output omits referee ground truth.
- The referee reports achieved, not achieved, or inconclusive from actual target evidence, not agent self-report.
- Event records distinguish attempt, verified finding, applied action, and verified fix. Fixture and live modes remain explicit.
- Every core and lab milestone has a reproducible operator command and an observable pass/fail result before other components depend on it.

## Dependencies and handoffs

- Joseph needs the registered target ID, observation format, allowed Red capabilities, and task/handoff contract.
- Aaron needs the sanitized Blue telemetry, response policy, and retest path; coordinate preservation of his existing work early.
- Omar needs stable session/event examples, a fixture source, and the live event subscription boundary.
- The core owns canonical state and authorization. Do not move those checks into the arena or rely on model compliance.
