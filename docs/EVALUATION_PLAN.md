# Evaluation plan

Evaluation runs are the learning loop for improving Red and Blue. Use repeatable, authorized lab scenarios and record enough evidence to tell a real improvement from a lucky run or a misleading display. Do not tune agents against hidden judge answers or report conclusions from one unrepeatable run as established performance.

## Evaluation principles

- Run only against registered local/disposable lab targets.
- Keep the scenario answer key with the referee/evaluation harness, not in Red or Blue prompts, logs, arena events, or agent boards.
- Version the scenario, target state, prompts/configuration, tool policy, agent build, and referee rules used in each run.
- Separate fixture, recorded, and live results. A fixture can verify display behavior; it cannot prove live agent capability.
- Distinguish attempt, evidence-backed finding, applied response, and independently verified result.
- Repeat runs with controlled initial state. Record failures and inconclusive results rather than discarding them.

## Initial scenario matrix

| Scenario | Purpose | Expected evidence |
|---|---|---|
| Authorized baseline | Confirm normal account behavior before and after defensive changes | Known authorized action succeeds |
| Broken access control path | Assess whether Red can discover and verify unauthorized access to a protected record in the lab | Referee confirms whether protected data was actually returned |
| Authentication/session path | Assess evidence quality and Blue monitoring/containment for the chosen lab behavior | Session/identity observations and independently measured access outcome |
| Input-handling path | Assess discovery, evidence, and safe response to a controlled input weakness | Lab-defined effect and corresponding target telemetry |
| Blue containment | Measure whether Blue uses allowed telemetry and a narrow approved response | Detection evidence, action record, and post-action state |
| Legitimate-use regression | Prevent a repair from simply breaking the application | Authorized user can still perform required bank actions |
| Ambiguous or unavailable target | Ensure the system reports uncertainty accurately | Inconclusive result; no false claim of defense or attack success |
| Scope violation attempt | Verify the core rejects an unknown target, capability, or redirected origin | Rejection event and no action outside the lab |

These are evaluation categories. Diego and the team should map them to exact synthetic users, endpoint behaviors, and target fixtures without exposing scenario truth to the live teams.

## Measures

### Red

- Mission success rate across repeatable seeded scenarios, measured by the referee.
- Evidence precision: proportion of reported findings supported by target evidence.
- Discovery coverage and time/budget to reach useful hypotheses.
- Adaptation after target behavior changes or Blue containment.
- Out-of-scope action attempts and policy violations; desired value is zero successful out-of-scope actions.

### Blue

- Detection of target behaviors the telemetry supports, separated by scenario.
- False-alert burden on normal and ambiguous traffic.
- Time from available evidence to an actionable alert and bounded response.
- Action correctness, approval compliance, and availability of an audit trail.
- Fix verification: unauthorized behavior blocked and authorized behavior preserved.

### Core, referee, and arena

- Reproducible start/reset and session-state transitions.
- Enforcement of registered targets, capabilities, budgets, timeout, cancellation, and visibility.
- Referee agreement with independently inspectable target state.
- Event ordering, source-mode labels, and absence of private or referee-only fields in judge/team views.
- Arena usability: judges can identify status, activity, target behavior, and verdict without inferring that a fixture is live.

## Run record

Each run should record a run ID; scenario/version; target reset ID; agent/config versions; policy version; start/end time; source mode; objective result; team event/evidence references; budget usage; safety violations; Blue actions and approvals; normal-use regression result; and unresolved or inconclusive conditions.

Do not store raw credentials, session secrets, or unnecessary personal data in run records. Prefer synthetic identifiers and evidence references.

## Improvement cycle

1. Choose one observed failure or weakness from a prior run.
2. Form a specific hypothesis about the change expected to help.
3. Change one relevant agent, policy, target, or detector factor at a time where practical.
4. Re-run the same scenario and its nearby regression cases from a reset state.
5. Compare objective result, evidence quality, latency/budget, false alerts, policy behavior, and legitimate-use behavior.
6. Keep the change only when it improves the intended measure without breaking safety, fairness, or normal access.

The initial evaluation suite is a planning target. It must be implemented and validated against the actual lab before describing measured agent performance.
