# RANGE project specification

## Objective

Build an interactive AI red-team vs. blue-team cyber range. Judges operate a clear dashboard that controls real, bounded lab activity and shows evidence for its outcomes.

The initial target is one website/API inside an isolated network. Multi-host network exercises and extra vulnerability categories are stretch goals.

## Teams and referee

**Red team:** discover routes, select access-control tests, execute through approved tools, inspect responses, and adapt to observed defenses. It receives application observations and scoped lab account access, not source-code answers or hidden ground truth.

**Blue team:** observe application telemetry, detect suspicious access, investigate, and apply supported defenses. Initial actions are revoking a lab session and applying a reviewed ownership-check patch in a disposable copy. It must not receive red's private plan or verified findings before making claims of independent detection.

**Neutral referee:** independently reproduce policy violations with fresh sessions, verify defenses, preserve evidence, and evaluate against hidden ground truth. Verification outcomes are verified, rejected, or inconclusive.

The orchestrator enforces phases, capabilities, request budgets, timeouts, cancellation, and persistence. Agent reasoning does not override these controls.

## Golden scenario

- Alice and Bob own separate private orders.
- One endpoint incorrectly returns another user's private order.
- A protected control endpoint enforces ownership correctly.
- Red finds a candidate and the referee independently reproduces it.
- Blue detects cross-user access from telemetry and revokes the attacking session.
- Red obtains a fresh permitted lab session and demonstrates the remaining ownership flaw.
- Blue applies an ownership check to a disposable target copy.
- The referee tests unauthorized access and legitimate access again.

| Check | Before fix | Required after fix |
| --- | --- | --- |
| Alice reads Alice's private order | Allowed | Allowed |
| Alice reads Bob's private order | Incorrectly allowed | Denied |
| Bob reads Bob's private order | Allowed | Allowed |
| Unauthenticated access to a private order | Denied | Denied |

Canary record markers identify retrieved data. An explicit access policy determines whether access is unauthorized. Canary presence alone is not a verdict.

## Execution and isolation

- Expose target IDs and relative paths to tools, not arbitrary URLs.
- Resolve destinations through one server-controlled registry and HTTP client.
- Reject origin overrides, unsupported schemes, unapproved ports, and external redirect hops.
- Keep target/tool execution isolated; separate any model-provider egress path.
- Restrict source and patch access to approved lab files and disposable copies.
- Reset seed data and target versions before each assessment. Run one assessment at a time initially.
- Preserve clean separation between credentials, team observations, and evaluation ground truth.

## State and evidence

Use SQLite state tables with an append-only event history. Persist state changes and related events together. SSE carries ordered event IDs and supports reconnection.

Minimum concepts: assessment, agent execution, endpoint, candidate finding, verification attempt, telemetry event, defense action, patch proposal, target version, and retest result.

Verification, remediation, and retesting have separate statuses. A verified finding remains verified even if its fix fails. Assessment outcomes include completed, partial, failed, and cancelled.

Correlate each tool action, HTTP request, application log event, and defensive alert using assessment, execution, and request IDs. Detection should use behavior; correlation IDs are for attribution.

## Remediation provenance

The live MVP supports applying a constrained, reviewable defense to a disposable target. General autonomous source editing is deferred.

Record patch origin (generated or known-good fallback), patch identity, original and patched target versions, test inputs, and results. A prebuilt fixed target demonstrates regression checking, not successful application of a generated patch. Label the distinction.

## User experience

- One main screen: controls, environment map, red/blue activity, timeline, and selected evidence.
- Guided mode: the presenter controls progression and authorizes supported defenses.
- Autonomous mode: the same policies and bounded tools execute successive rounds automatically; add after guided mode is reliable.
- Click services or timeline entries to inspect details; collapse raw technical evidence by default.
- A visible stop control cancels execution. Reset restores lab state.
- Every displayed outcome comes from a persisted event or verification result.
- Sample data, recorded playback, and live execution must have visibly distinct labels.

## Evaluation

Report counts alongside precision and recall. Match deduplicated findings to hidden seeded flaws using normalized endpoint, category, action, and violated policy. Define a scoped matching rule per scenario.

Measure confirmed discoveries, accepted false positives, missed seeded flaws, rejected genuine candidates, inconclusive results, detection/containment times, request count, and retest outcomes. Use the same candidate set for before/after verifier comparisons. Undefined ratios display N/A.

Claims of success are limited to the tested scenario. Taking the target offline or denying every request is not a successful fix.

## Acceptance

A clean reset followed by a judge-operated run must produce a reproducible finding, independent evidence, a blue-team action, and a retest showing both protection and legitimate functionality. Only then expand scope.
