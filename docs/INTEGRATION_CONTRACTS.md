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

## Bank preparation prototype interfaces

The isolated prototype in `apps/bank-lab` implements the following target interfaces. These are available building blocks, not a completed implementation of the canonical contracts above. See [the Ubuntu walkthrough](UBUNTU_BANK_LAB.md) or [the local Docker Desktop walkthrough](LOCAL_DOCKER_DESKTOP.md) for startup and verification.

| Interface | Current behavior |
|---|---|
| `GET /api/health` | 200 with `status`, `target_id`, `run_id`, and `scenario_version` when initialized/reachable; 503 when unavailable |
| `POST /api/login` | JSON `username`/`password`; returns an HttpOnly, SameSite=Strict session cookie on success |
| `POST /api/logout` | Revokes the current session and clears its cookie |
| `GET /api/me` | Current identity and bank run ID, or 401 |
| `GET /api/accounts` | Authenticated owner's synthetic accounts and run ID |
| `GET /api/accounts/:account_id` | Four-digit identifier; owner check; cross-owner access denied |
| `GET /api/vault` | Authenticated vault role only; synthetic protected records and run ID |
| `GET /api/training/search?term=...` | Opt-in `sqli-training` scenario only; intentionally unsafe search over synthetic training rows via a separate read-only database role. It cannot access bank users, accounts, vault, sessions, or events. |
| `GET /api/monitor/logs?after=...` | Returns a bounded cursor page of sanitized in-process HTTP API request metadata for the local monitor page. It excludes itself and never returns bodies, cookies, query strings, or source addresses. |
| `GET /api/availability/status` | Opt-in availability variant; private probe credential; measured training occupancy and current exercise/history |
| `POST /api/availability/work` | Private load credential; exact empty JSON body, approved Origin and exercise pin; bounded fixed-cost work with no queue |
| `POST /api/availability/control` | Private executor credential; exact approved mitigation/restore/stop/idle-reset actions scoped to the current exercise |
| `node scripts/reset.mjs` in the operator service | Initializes/restores baseline, invalidates sessions, rotates run ID/record, and clears events; no public HTTP reset route |
| `node scripts/verify.mjs http://bank:3000` in the operator service | Checks target readiness, authorized accounts/vault, unauthorized denial, and logout |

State-changing HTTP calls require an `Origin` header from the explicit `BANK_ALLOWED_ORIGINS` list. The default Compose configuration permits the localhost browser origin and the internal operator origin. A fixed Nginx proxy publishes only `127.0.0.1:3000` and forwards to the bank over the internal frontend network; the proxy cannot reach the database. The bank and database networks are internal, leaving the bank app without general Internet egress. HTTP cookies are permitted only for this private browser path (`BANK_COOKIE_SECURE=0`); configure HTTPS and secure cookies before providing a different browser access path.

The web service uses a restricted `bank_app` database role. Its credentials are not an agent capability. The operator alone receives administrator credentials. No HTTP route exposes reset or event export.

Raw `bank.events` rows contain `event_id`, bank-local `sequence`, `run_id`, `occurred_at`, `target_id`, `event_type`, `actor_id`, `visibility`, `summary`, `producer=lab`, and `source_mode=live`. Events classify real target requests; they exclude passwords, cookie values, request/response bodies, and vault contents. Visibility is initially `blue_private`. The database permissions restrict reads to an operator; the core routing adapter is not implemented.

The future core adapter must map bank `run_id` to canonical `session_id`, allocate session-wide event order, add team/status and evidence references where appropriate, enforce visibility, and emit separate sanitized `judge_safe` events for Omar. Bank-local sequence values restart on reset and are not canonical contest order. An authenticated vault event alone is not proof of unauthorized Red success; the referee still needs independent objective evidence and legitimate-use regression checks. Export required evidence before reset, because raw bank events are cleared.

An embeddable availability adapter now supplies fixed target registration, redirect rejection, separate credentials, bounded HTTP dispatch, cancellation, sanitized durable evidence, and a pure recovery assessment for this slice. The [availability handoff](BANK_AVAILABILITY_HANDOFF.md) is the normative bank-side interface: target `bank-lab`, opaque clients `load-demo`/`referee-probe`/`core-executor`/`ordinary-demo`, pinned run/version/exercise, and explicit calibrated approval. Red's `start_load_test`/`stop_load_test` proposals map to fixed work/control operations; models cannot supply origins, limits, credentials, or payload overrides.

This library's sequence/history is local. The opt-in core availability runtime now provides session lifecycle, canonical SQLite order, private credential injection, Blue observation and approved defense dispatch, and independent fixture assessment. Arena routing and deployed-bank bootstrap remain pending. Recovery needs independent scoped status/readiness/ordinary probes during continuing validated load, post-stop status, and a complete trusted journal; timeouts or incomplete evidence stay inconclusive. See the handoff and [core runbook](core/AVAILABILITY.md) for the exact boundaries.

## Opt-in availability core adapter (2026-10-04)

`availability-fixture` is registered only by an explicit trusted opt-in, owns an ephemeral loopback server, and remains `data_source=fixture`. It maps Red's existing typed `start_load_test`/`stop_load_test` proposals to the fixed JS bank adapter. It does not alias the separate `bank-local` vault fixture or activate the deployed `bank-lab`. Fixture planning cannot use remote model mode or supply destinations, routes, limits, identities or payloads.

Core consumes target-produced `range.blue.availability/v1` windows. It retains canonical aggregates privately, invokes the actual Blue observer, and validates the exact proposal against the same recent window and configured positive source rate/burst/TTL before execution. This adapter implements a training-route token bucket; Python WSGI middleware is not in Next.js's path.

Source adapter records use private local order; core persists them with its own globally ordered assessment envelope and referee-only visibility. Blue aggregates and proposals are blue-private. Judge events are separately constructed fixture-labeled summaries: `availability.load.dispatched`, `availability.observed`, `availability.defense.applied`, and `availability.referee.assessed`. Their action receipts do not imply recovery. Only the terminal referee projection after successful teardown may report fixture recovery, and it always sets `arrest_permitted=false` and `fix_status=not_assessed`.

Recovery additionally requires the same policy revision to remain active, exact approved positive parameters, and target-issued policy refusals above the fixture suspicion rate in each successful verification interval. Quota/capacity 429s do not count. Pause reaches the background admission loop, drains bounded requests, and preserves deadlines; stop aborts and invokes reserved cleanup; reset retains history after teardown. Lost bridges, cancelled rounds, removed/expired policies and denied ordinary access stay inconclusive. The runbook fixes the request, concurrency, time, probe, control and message ceilings. Real-bank calibration and approved activation are separate changes.
