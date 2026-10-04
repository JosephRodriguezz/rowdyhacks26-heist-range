# Blue Team role packet (originally assigned to Aaron)

## Mission

Joseph, as the current Blue owner, extends Aaron’s existing Blue implementation into a contest-time monitoring and response capability. Preserve its useful behavior and tests; inventory and verify what exists before changing its architecture. Blue should defend independently from Red’s private reasoning.

## Blue responsibilities

- **Monitor:** consume the sanitized telemetry the core permits, correlate events, and report evidence-backed alerts with confidence and impact.
- **Defender:** recommend or perform an allowed response, track whether it was applied, and request independent retest.
- **Blue board:** track tasks, alerts, evidence references, response proposals, approvals, and verification status. Keep it Blue-private.

The roles may share a process or be implemented differently. Keep the responsibilities and decision trail inspectable.

## Before the hackathon

- Inventory the current Blue code, behavior, tests, branch/source location, and run instructions. Mark each item verified, planned, or unknown.
- Identify which current detections and responses should be preserved. Do not assume an uninspected behavior is already tested.
- Map existing telemetry and proposals to the draft event, evidence, and response contracts.
- Define what sanitized observations Blue needs for the three initial vulnerability families without exposing Red’s plan or the referee’s answer key.
- Prepare baseline evaluation cases for normal user behavior, suspicious behavior, ambiguous evidence, containment, and retest.

## During the event

1. Connect Blue to its permitted telemetry stream and private task board through the core.
2. Monitor target events and produce alerts with linked evidence, severity/confidence, and a plain-language rationale.
3. Separate a proposed action from an applied action. The core validates capability, target, budget, and approval before execution.
4. Use automatic actions only for narrow, reversible containment explicitly allowed by policy, such as revoking a confirmed attacker session.
5. Request presenter approval for patches or broader state changes. Apply approved changes to the disposable lab target.
6. Ask the independent referee to retest both the unauthorized behavior and legitimate access. Record verified, failed, or inconclusive outcomes separately.

## Standards and acceptance checks

- Blue receives sanitized target telemetry and no Red task board, messages, hypotheses, or private findings.
- Each alert links to evidence and distinguishes observed behavior from a confirmed vulnerability.
- Every response records proposer, policy decision, approval if required, execution result, and target state afterward.
- Automatic containment is narrow, reversible, bounded, and cancelable. Broad changes and patches require review.
- A fix is reported as verified only when the referee confirms unauthorized access is blocked and authorized use still works.
- Timeouts, failed logins, missing telemetry, and service errors are inconclusive unless independent evidence proves the defense result.
- Baseline Blue behavior and tests remain available for regression comparison as specialists are added.
- Events shown in the arena match recorded Blue activity and do not disclose private Red or referee data.

## Dependencies and handoffs

- Diego owns telemetry sanitation, event delivery, response policy enforcement, approvals, and independent retest orchestration.
- Aaron owns Red behavior; Blue cannot use it as a signal source unless it is also present in permitted target telemetry.
- Omar receives only the judge-safe Blue event fields defined by the shared contract.
- Record preserved baseline behaviors and any intentional deviation in the decision log.
