# Red Team standalone prototype specification

**Status:** Standalone prototype v0.1 implemented. **Owner:** Joseph. **Updated:** 2026-10-02.

The prototype implements the agreed preparation scope in Python's standard library. Local interface details are implementation choices for this standalone experiment; they do not amend the shared integration contracts. A fixture-provider test demonstrates control flow, but no real remote-model run or agent-performance result exists yet.

## Goal and scope

Build an isolated prototype in which model-driven Scout and Operator investigate a disposable local web app and attempt to obtain protected synthetic vault data. The target has actual HTTP behavior, resettable state, and hidden variations in the supported families: broken access control, authentication/session weakness, and input handling. An independent local evaluator checks the objective from target evidence.

The prototype develops Red behavior and evidence quality before integration with Diego's core/bank lab and Aaron's Blue agents. Its evaluation harness can change target behavior through a labeled simulated defense. Those changes test Red's response to observations; they are not measurements of Aaron's Blue capability.

Upstream sources are the [project brief](../PROJECT_BRIEF.md), [architecture](../ARCHITECTURE.md), [shared draft contracts](../INTEGRATION_CONTRACTS.md), [Joseph role packet](../roles/JOSEPH_RED.md), and [project evaluation plan](../EVALUATION_PLAN.md). Shared integration changes require the relevant owners' review.

## Requirements from agreed scope and repository policy

These requirements preserve the confirmed prototype choices and existing project guardrails.

| ID | Requirement | Evaluation evidence |
|---|---|---|
| R-01 | A model selects typed, allowlisted actions from observations rather than receiving a fixed exploit path | E-01–E-05; typed provider adapter and fixture-driven orchestration trace |
| R-02 | Security actions execute only through a deterministic boundary against the registered local app | E-09 |
| R-03 | Red gets public-site access and two ordinary account references; tools handle their credentials | E-03, E-13 |
| R-04 | Hidden vulnerability locations, privileged credentials, scenario truth, and defense schedules remain outside Red context | E-14 |
| R-05 | Scout and Operator overlap after an evidence-backed handoff, sharing one private board and enforced budget with explicit task ownership | E-05, E-10 |
| R-06 | The target has synthetic users, actual HTTP behavior, and reproducible reset | E-01–E-04, E-15 |
| R-07 | The harness can apply a labeled simulated defense; Red adapts from changed target responses | E-06–E-08 |
| R-08 | Mission verdicts and findings rely on independent evidence; blocked, failed, and inconclusive outcomes remain distinct | E-01–E-08 |
| R-09 | Budgets, request timeouts, cancellation, and output bounds are enforced outside the models | E-10–E-12 |
| R-10 | Records identify the target, planner, and defense modes accurately | E-15 and run-report inspection |

## Context and component boundaries

| Component | Responsibility |
|---|---|
| Scout | Discover reachable behavior, compare ordinary-user access, record observations, and propose testable hypotheses |
| Operator | Assess handed-off candidates, execute bounded tests, report results, and request objective evaluation |
| Red board | Canonical local records for tasks, evidence references, hypotheses, ownership, handoffs, and remaining budget |
| Action boundary | Validate proposals, reserve budget, manage credential/session references, execute HTTP, and record sanitized observations |
| Model adapter | Assemble permitted context and request typed proposals; keep provider credentials in transport configuration |
| Local toy app | Synthetic ordinary-user and protected-vault behavior, controlled flaws, normal-use checks, and reset |
| Evaluation harness | Hidden scenario setup, repeatable initial state, simulated defense schedule, and evaluation records |
| Objective evaluator | Independently check actual protected access and emit achieved, not_achieved, or inconclusive |

For the event, Diego's core remains the canonical owner of sessions, policies, task routing, events, and referee integration. The prototype's board and executor are local scaffolding; their shapes do not amend the shared contract.

## Implemented local action interface

The initial action set uses bounded HTTP and account/session operations. Browser automation, shell commands, arbitrary code execution, credential guessing, and third-party scanners are outside this prototype.

| Proposed capability | Inputs | Result |
|---|---|---|
| read_page | Registered target ID, relative path/query, optional opaque session reference | Sanitized page/response observation and evidence reference |
| submit_form | Registered target ID, discovered form reference, bounded fields, optional session reference | Actual form result and evidence reference |
| request_api | Registered target ID, relative path, allowed method, bounded structured body, optional session reference | Sanitized API response and evidence reference |
| start_account_session | Registered target ID and one of the two supplied identity references | Opaque session reference and sanitized login outcome |
| end_account_session | Registered target ID and owned session reference | Actual target logout outcome; retained handle permits a bounded post-logout check |

The model may select an ordinary identity/session reference but cannot supply credential values, raw cookie material, authorization headers, a host override, or a destination origin. Allowed HTTP methods, body fields, request sizes, response sizes, and session-handle checks are validated by code. API actions accept only `GET` or `POST`, fixed string fields, and `/api/` or `/demo/` paths. Form submission resolves the fixed `contact_form` reference to its registered local handler.

The runner attaches a generated action ID, task ID, actor role, and target ID to each typed proposal. Evidence and handoff records reference those generated IDs. Budgets and permissions come from runner policy; a model cannot choose or raise them. Unknown fields and malformed variants are rejected rather than broadening an action.

The toy app binds only to loopback. The runner registers its fixed origin before the run; the model cannot supply or replace that origin. Relative paths are canonicalized and must stay on it. Redirects are never followed, including redirects returned after form or login operations. The HTTP client connects directly to the registered loopback address and sends no target request through an inherited proxy or an unregistered destination.

The model-provider connection is configured separately from target actions. Its adapter receives sanitized observations and must reserve the shared model-call budget before each provider call or retry. This keeps provider transport from becoming an alternate route for target execution or a way to bypass the run limits.

Normal login/logout flows use tool-owned credentials and cookie storage. Responses and request summaries are sanitized before logging and before being supplied to either model. Evidence includes method, relative route, observed status, bounded safe content, safe request fields, and opaque session references; it excludes raw credentials and cookies.

## Implemented action and evidence flow

1. The harness resets a chosen hidden scenario and verifies target health and authorized baseline behavior.
2. The runner gives Red the objective, registered target reference, public entry surface, two ordinary identity references, lesson material, and configured limits.
3. Scout records observations and creates a hypothesis with evidence, a proposed next test, and its uncertainty.
4. An evidence-backed candidate is handed to Operator. Operator claims its task; Scout continues work on distinct questions.
5. The boundary validates each action and reserves the shared budget atomically before dispatch.
6. The actual HTTP result becomes an immutable evidence record and an ordered action/result event. The board updates through validated operations.
7. Both roles reassess from their permitted observations. Contradictory responses weaken or invalidate a hypothesis; a timeout alone does not confirm a defense.
8. The runner checks objective evidence after each observed action. Agents can report their assessment, but cannot set the verdict; the evaluator checks actual target behavior independently.
9. The runner stops at objective completion, explicit cancellation, exhausted limits, or a supported blocked/inconclusive outcome and produces a run report.

The harness may apply its hidden simulated defense between these steps. Red receives target responses rather than a message revealing what the harness changed.

## Implemented concurrency and failure rules

One task has one active owner. Claim and status updates use an atomic board lock so competing claims cannot both succeed. The board assigns the handed-off candidate to Operator and blocks another task from claiming it. The action boundary also blocks repeating the same exact test until the observed session/defense state changes. Comparing different identities or inputs remains distinct work. A handoff identifies evidence and a bounded next question; it does not grant capabilities or a second copy of the run budget.

Each opaque session reference belongs to the current run and target and identifies one cookie context. Authentication/logout changes to the same context require exclusive ownership, so one role cannot silently change the other role's test conditions. Distinct contexts can be used concurrently. Reset invalidates every old session reference.

Both roles draw from the same HTTP-action, model-call, and wall-clock limits. Reservations occur before dispatch. A denied or malformed proposal is audited and consumes a model turn; it cannot cause a request or replenish remaining budget. The defaults and hard ceilings are listed below and recorded in every report.

The runner generates unique action IDs, and the board prevents exact test replay while state is unchanged. A changed hypothesis creates a new task/action with new evidence. Do not automatically retry a mutating HTTP request after an ambiguous timeout: its target effect may already have occurred. Any further request is a deliberate bounded action with its own record.

Cancellation stops new model calls, task claims, and target dispatch. In-flight work receives cancellation where supported; late results remain auditable but cannot schedule more work. Stopping the local run does not undo a request that already reached the target. Reset cancels/drains the old run before establishing the next baseline.

| Condition | Implemented runner behavior |
|---|---|
| Malformed or unauthorized proposal | Reject, audit, and let the role revise within its remaining limits |
| Unknown target, origin-changing redirect, or forbidden header | Reject before any prohibited request |
| Budget exhausted or stop requested | End dispatch and record the terminal reason |
| HTTP timeout or ambiguous mutation | Record uncertainty; require a new deliberate observation before interpreting the effect |
| Model provider failure | Record a model-execution failure; preserve collected evidence and distinguish it from target/defense results |
| Target health/reset failure | Stop or invalidate the run; do not count it as an attack or defense success |
| Missing or inconsistent objective evidence | Evaluator reports inconclusive |

## Learning material and honest reporting

Prepare compact, source-linked lessons for the three families using the [curated references](../REFERENCES.md). Each lesson should explain the concept, ordinary versus suspicious behavior, evidence needed, common false conclusions, a bounded testing approach, and conditions for abandoning a hypothesis. Lessons teach a family; they must not contain hidden scenario endpoints, synthetic identifiers, or an answer sequence.

Model outputs should include a short evidence-based rationale and structured records suitable for inspection. The prototype report shows actions, observations, handoffs, and hypothesis changes; it does not require private model reasoning.

Record `target_kind` as `local_mock` and `planner_mode` as `model` or `deterministic_baseline`. The harness labels interventions as simulated defense. HTTP observations, fixture-provider tests, and the deterministic planner have separate labels. Scenario ID, defense schedule, and target read ledger sit under the report's `evaluation_private` object with `visibility: referee_only`; that object is not in Red's board or model context. Mapping this local metadata into shared events remains an integration review item.

Report mission result, adaptation behavior, evidence quality, policy denials, budgets, and infrastructure/model failures separately. Run model and baseline configurations with the same initial scenario and policy. Keep failures in the comparison and reserve held-out variations for checking whether improvements generalize.

## Remaining implementation decisions and gates

| Item | Owner and gate |
|---|---|
| Repeated-run schedule and behavioral performance threshold | Joseph; measure a real model baseline before setting a threshold |
| Project-wide provider choice | Team; the optional local adapter does not decide the event provider |
| Shared schema/capability mapping | Diego and Joseph; review before event integration |
| Held-out variation selection | Joseph; keep answer keys out of model-visible lessons and prompts |

The local app, baseline, action policy, fixture-driven model path, and evaluation record are implemented. See [evaluation cases](EVALUATION_CASES.md) for deterministic coverage and the explicit limits on what those checks demonstrate.
