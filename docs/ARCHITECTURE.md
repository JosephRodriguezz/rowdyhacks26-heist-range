# Architecture and trust boundaries

This is the agreed system map for planning. It describes responsibilities and information flow, not a framework, language, deployment platform, or fixed component implementation.

## Components

### Bank lab

A purpose-built website/API with synthetic accounts, controlled vulnerability families, a health endpoint, and a repeatable reset. It runs only as a registered lab target. Target identifiers resolve through a fixed registry; an agent cannot substitute an arbitrary URL or follow an origin-changing redirect.

### Core control plane

The core owns contest sessions, registered target selection, team task queues, tool dispatch, policy enforcement, budgets, timeouts, cancellation, event ordering, and reset/stop controls. It validates task handoffs and routes each event only to recipients allowed to see it. Models propose and analyze; deterministic code enforces permissions and executes approved tool actions.

### Red team

Red receives the mission objective, target observations, its own task board, and evidence it gathered. It does not receive seeded ground truth or Blue’s internal plans. Scout-to-Operator handoffs carry hypotheses, evidence references, and remaining budget rather than secrets or unrestricted shell access.

### Blue team

Blue receives sanitized target telemetry, its own task board, and defensive evidence. It does not receive Red’s board, messages, or private findings. A narrow, reversible containment action may be automatic under policy; broad changes and patches require presenter approval and independent retest.

### Referee

The referee has the protected scenario ground truth and objective evaluator. It checks actual target state and event evidence independently of the teams’ claims. It emits a verdict and evidence references, not the hidden answer key to Red or Blue.

### Arena

The arena is a read-oriented judge surface for session state, team-safe agent activity, target status, and the event timeline. It can open the bank lab. It does not call attack tools or determine mission success. Its source adapter begins with fixtures and later consumes events from the core; each mode is labeled.

## Data flow

1. The presenter selects a scenario and registered target, then starts a session through the core.
2. The core issues Red and Blue separate task contexts and gives each only its permitted inputs.
3. Agents request actions through the core’s target registry, capability policy, and budgets.
4. The lab and tools return observations. The core records ordered events with source, actor, scope, and evidence references.
5. The core routes sanitized views to the appropriate team board and arena. Referee-only records remain isolated.
6. The referee evaluates the objective and any claimed defense using actual lab behavior and regression checks.
7. The presenter may pause, stop, or reset. Reset returns the lab to a known baseline before another run.

## Information visibility

| Data | Red | Blue | Arena/judges | Referee |
|---|---|---|---|---|
| Mission objective | Yes | Yes | Yes | Yes |
| Target observations permitted to that team | Yes | Sanitized defensive telemetry | Only approved event summaries | Yes |
| Red task board and hypotheses | Yes | No | Only selected, safe display fields | Yes, for audit if needed |
| Blue task board and response plan | No | Yes | Only selected, safe display fields | Yes, for audit if needed |
| Seeded vulnerability answer key | No | No | No | Yes |
| Session controls and final verdict | Read-only status | Read-only status | Presenter controls and verdict | Produces verdict |

## Core invariants

- Every security tool action identifies a registered target and capability; the core rejects unknown targets, unauthorized actions, and cross-origin redirects.
- Credentials stay out of prompts, event payloads, screenshots, and committed files; use credential references when the lab needs them.
- Tool execution has enforced budgets, timeouts, cancellation, and audit records.
- Untrusted target content is data, never instructions to the model or core.
- The system distinguishes attempted attack, evidence-backed finding, applied action, and independently verified outcome.
- Evaluation ground truth is referee-only at runtime.
- Fixture, recorded-run, fallback, and live execution modes are labeled distinctly.
