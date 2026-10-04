# Draft integration contracts

**Status:** Draft 0.1 for parallel planning. These shapes are implementation-neutral. The team should agree on field names and validation rules before event integration; they do not select a language, transport, or agent framework.

## Contract rules

- Every record belongs to a session and has a stable identifier.
- Each record carries an explicit audience or visibility classification. The core enforces routing; clients do not decide whether to hide data.
- Evidence is referenced by identifier. Do not copy credentials, raw secrets, or referee-only ground truth into the record.
- Unknown status values fail closed or are rejected; they are not silently treated as success.
- Timestamps support display. A monotonic per-session sequence number determines event order.
- Producers are identified so the arena can distinguish core, target, agent, referee, and fixture data.

## Agent task

| Field | Meaning |
|---|---|
| task_id | Stable task identifier |
| session_id | Contest session |
| team | red, blue, or referee |
| assigned_role | Scout, Operator, Monitor, Defender, or referee role |
| objective | Bounded task goal, not a tool command |
| target_id | Registered target identifier, when applicable |
| allowed_capabilities | Core-validated capability names |
| budget | Call, time, and/or action limits |
| status | queued, active, blocked, yielded, completed, failed, or cancelled |
| evidence_refs | Evidence IDs supporting current understanding |
| depends_on | Prior task IDs required for this task |
| visibility | Team/private audience enforced by the core |

Tasks describe what an agent should accomplish. They do not grant permissions beyond the target registry and capability policy.

## Handoff

A handoff records **handoff_id**, **session_id**, **from_task_id**, **to_role**, **reason**, **summary**, **evidence_refs**, **remaining_budget**, and **created_at**. It must not include another team’s private data. The core validates that the sender owns the task, the receiving role is in the same permitted team workflow, and the remaining budget is nonnegative.

Examples: Scout to Operator with an evidence-backed candidate path; Monitor to Defender with a detection and supporting event references. A handoff may request review without claiming a vulnerability or fix is verified.

## Arena event envelope

| Field | Meaning |
|---|---|
| event_id | Stable event identifier |
| session_id | Contest session |
| sequence | Monotonic event order within the session |
| occurred_at | Event timestamp |
| producer | Core, lab, agent, referee, or fixture source |
| event_type | Typed event such as task.started, finding.reported, action.applied, target.health, or referee.verdict |
| actor_id | Agent or component that emitted the event |
| team | red, blue, shared, or referee |
| target_id | Registered target, when applicable |
| summary | Short judge-readable description |
| evidence_refs | Evidence available to this audience |
| confidence/status | Producer assessment and state, not a substitute for referee verification |
| visibility | red_private, blue_private, judge_safe, or referee_only |
| source_mode | fixture, recorded, or live |

The event producer marks the source mode; the UI may not relabel a fixture as live. The core removes or rejects fields that exceed the recipient’s visibility.

## Evidence reference

An evidence reference should carry **evidence_id**, **session_id**, **target_id**, **evidence_type**, **observed_at**, **source**, **integrity/reference metadata**, **visibility**, and a **sanitized summary**. Raw request/response material, if retained for the lab, needs bounded retention and access control. Evidence shown in the arena must be safe for judges and must not expose credentials or hidden answers.

## Target and capability registry

The registry entry describes **target_id**, **scenario_id**, **base_origin**, **health_check**, **reset_action**, **allowed_capabilities**, and **per-session limits**. The implementation should keep origin and endpoint resolution inside the registry. No agent-supplied destination is accepted. Redirects remain on the registered origin or are rejected.

Capabilities are names in a narrow allowlist such as read_public_page, submit_lab_form, or request_lab_api. Exact capability granularity is an open integration decision for Diego and the team; the registry and core remain the enforcement points.

## Referee verdict

A verdict carries **session_id**, **objective_id**, **result** (achieved, not_achieved, or inconclusive), **evaluated_at**, **evidence_refs**, and **reason_summary**. It may carry a safe mission score or phase breakdown. The hidden answer key is not part of this output. Timeout, an unavailable lab, or failed login is inconclusive unless the objective evaluator has independent evidence for a result.

## Team boards

Each team board contains that team’s tasks, owners, hypotheses, evidence references, handoffs, state, and remaining budget. Red and Blue boards are separate. The core owns the canonical session and record state; the board is a view of validated tasks and events, not an unrestricted shared memory space.

## Integration gates

1. Agree on required fields, status enums, and visibility rules.
2. Validate fixture events and tasks against the draft shapes.
3. Connect each team to the core through its permitted task/event view.
4. Connect the arena to fixtures first, then the core’s live event stream.
5. Verify the referee result independently and check that no team receives referee-only fields.

## Local core preparation slice (2026-10-03)

Joseph approved a runnable preparation core on `codex/core-orchestrator`. It uses the existing disposable Red bank and an unchanged, commit-pinned Mayo Blue runtime behind adapters. This is not agreement that Diego's event bank already implements these interfaces. The legacy Mayo v1 records remain adapter inputs; the core owns session identity, authorization, budgets, persistence, and ordering.

The loopback presenter API reuses `/api/assessments`, `/actions`, `/events`, `/stream`, and scoped `/evidence` paths. Its control actions are `start`, `pause`, `resume`, `stop`, and `reset`; raw tool commands, patches, private audiences, and destinations are never accepted. JSON control requests include an idempotent `action_id`. Presenter API requests require a bearer credential, strict host/origin checks, and judge-safe projection. Team and referee contexts are internal adapters, not caller-selected API views.

Session states are `created`, `running`, `pausing`, `paused`, `stopping`, `completed`, `cancelled`, and `failed`. Pause prevents new model/tool dispatch, drains bounded in-flight work, then becomes paused; the original deadline still applies. Stop cancels dispatch and rejects late proposal results. Reset requires ended execution, invalidates old handles, and creates a new session without deleting previous history. Process recovery never automatically resumes an interrupted contest.

The canonical event envelope retains Mayo's `schema_version`, integer `id`, `assessment_id`, `timestamp`, `type`, `actor`, target/version, `data_source`, `evidence_refs`, and typed `data`, adding explicit `visibility`, `producer`, and `sequence`. Sequence/id order is session-scoped; filtered views can have gaps. SSE reconnects strictly after the cursor. HTTP evidence is `live` local-lab activity; fixture-provider decisions remain separately labeled `fixture`, and `planner_mode` distinguishes fixture from model execution. No fixture run establishes model performance.

Blue receives windowed, lab-produced telemetry and the owner-only policy, never Red's board or referee ground truth. The core validates evidence-backed `revoke_session` proposals against its credential-reference registry before applying containment. Patches remain disabled. The referee records historical vault disclosure separately from revoked-session containment, legitimate-use regression, and a fresh-session retry. Timeouts and invalid fresh logins are inconclusive; containment is not remediation.
