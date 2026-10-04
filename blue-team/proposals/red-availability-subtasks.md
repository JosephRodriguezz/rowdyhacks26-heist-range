# Proposal: sub-tasks for the availability (outage and recovery) mission

First written 2026-10-03 by Claude for Aaron, and **revised the same day** after Joseph's new direction and the interface Blue sent to Diego. It sits in blue's folder only because blue does not own Red, core, or arena files. **It is a proposal: Joseph, Diego, and Omar own the files these tasks touch and decide what to accept.** Move it to the Red docs if they adopt it.

## What changed since the first version

- **Direction.** The first version followed the repository plan: availability only after the vault mission passes Gate 6. Joseph has since changed the order. Per the Codex reply in `blue-team/comms/threads/gate-status.md`: Joseph takes Blue and Aaron takes Red; DDoS and availability first, defacement afterwards; the demo is an attack and recovery story, not a scored contest with a winning team.
- **Interface.** The "health endpoint plus a bounded degrade trigger" idea is replaced by a core-owned design (below). A fake outage toggle is explicitly out.
- **Tooling.** GrokBot cannot edit the repository, so its role is paste-in only.

## What was checked, and what is only reported

**Verified by Claude on 2026-10-03 against the published branches:**
- `codex/bank-lab-integration` (Diego): `GET /api/health` returns `ready` when the database check succeeds and `unavailable` (HTTP 503) when it fails. It has no degraded state. The `/monitor` request buffer is in memory and holds 250 entries.
- `docs/INTEGRATION_CONTRACTS.md` lists a `target.health` event type.
- `codex/red-team-design` still calls availability an open, vault-dependent decision, and `docs/HACKATHON_PLAN.md` still says availability only after Gate 6. So the repository text is now out of date against Joseph's direction.
- `red/availability-ddos` exists on `origin` (tip `5fc41e2`). Claude has not reviewed its code.
- No capability named `availability.load` exists on the Red branch; it is a proposed name.

**Reported, not verified by Claude:**
- Gate 6 has not passed, and the local core preparation has two failing tests (Codex's reply in the gate-status thread, which says it is not a gate certificate).
- No formal AV-01 record exists in the repository. Joseph's direction was given in chat and is not yet written into `docs/DECISIONS.md`.
- Joseph's local Blue preparation (an HTTP-flood mitigation adapter, 353 passing blue tests) lives on `codex/core-orchestrator` and is not published on `Mayo`.
- The interface below comes from the message Blue sent to Diego. Diego has not accepted it, and nothing is in the contract yet.

## Ground rules for every sub-task

1. **Registered lab only.** Load comes from a bounded, core-provided capability against a registry target. No arbitrary destinations, no cross-origin redirects, no shell commands, and no traffic to anything outside the lab.
2. **Bounded.** A fixed ceiling (the scenario's existing ceiling is reported as 60 requests, 12 concurrent, 10 seconds), a timeout, cancellation, and an audit event with labeled start and stop.
3. **The disruption must be real, not toggled.** Bounded load against a disposable, resource-isolated bank must actually degrade it. Never make the health route stateful to force a signal. If bounded load does not degrade the bank, the fallback is an opt-in, fixed-cost training workload under Compose resource limits.
4. **The referee decides.** Core's independent observer sets available, degraded, or unavailable from thresholds agreed after measuring the normal baseline. Red's report, Blue's report, and the bank UI never count as verification. Do not invent threshold or latency defaults; calibrate them.
5. **An outage is not vault access.** Availability is scored and shown separately from vault access.
6. **Recovery needs proof.** Recovery is claimed only after independent probes keep running after the load stops and show a healthy window, with ordinary access working within the agreed latency while high-rate load continues. Blocking everyone, failed logins, timeouts, and application-generated 429s are not proof that Blue mitigated anything.
7. **Cut line.** Do not claim live recovery or play a verified "arrest" animation unless the real isolated bank, the bounded registry-only load, the reviewed Blue response, the continuing-load ordinary-access checks, and truthful event and UI integration all work repeatably. Otherwise the result is inconclusive and the fallback is explicitly labeled as a fallback or replay. Never relabel a fixture as live or force a verdict.
8. **Label everything.** Fixture, recorded, and live runs are different and must be shown as different. Only the bank's public interface goes to the second computer; core controls, telemetry, recovery tools, and the arena stay separate.

## The interface Blue proposed to Diego (not yet accepted)

| Part | Design | Owner |
| --- | --- | --- |
| Signal | Keep the real `GET /api/health` as the HTTP check. A core-side observer measures its status and latency and emits the existing `target.health` event with `available`, `degraded`, or `unavailable` and a sanitized evidence reference. | Diego |
| Trigger | Red requests one registered `availability.load` capability for the selected target. Core fixes the route and enforces the ceiling, cancellation, and an audit event. The request cannot choose a URL or set a "degraded" flag. | Diego (enforces); Red (requests) |
| Recovery proof | An independent core and referee observer keeps probing after the load stops, records samples in the core's session event history (which survives a bank reset), and reports recovery only after the agreed healthy-probe window. Blue consumes the same sanitized events and may recommend a narrow rate limit, but its report is not verification. | Diego |

## Sub-tasks

Under Joseph's direction the vault-first order no longer gates the start. The integrated demo still needs the contract, a resettable bank, and core and the referee (Gates 1 to 3), so AV-02 to AV-04 come first.

| ID | Sub-task | Owner (suggested) | Needs | Done when |
| --- | --- | --- | --- | --- |
| AV-01 | **Record the direction.** Write the DDoS-first order, the attack and recovery framing, and the cut line (rule 7) into `docs/DECISIONS.md` and the plan, replacing the vault-first sequencing. Joseph's chat direction exists; the repository record does not. | Joseph, with Diego | none | The decision and cut line are written in the repository and the old sequencing is reconciled |
| AV-02 | **Extend the wire contract.** Use the existing `target.health` event with `available`, `degraded`, and `unavailable` plus a sanitized evidence reference; add the `availability.load` capability and its audit event. Negative cases: an outage never produces a vault-access result, a Red-reported outcome is never a referee verdict, and an unregistered target or a request carrying a URL is rejected. | Diego with Joseph | Gate 1 draft | Fixtures for each shape exist and all owners can consume them without referee-only data |
| AV-03 | **Calibrate and prepare the bank.** Measure normal latency and behavior; agree the thresholds from the measurement; run the bank in a disposable, resource-isolated container. If bounded load does not degrade it, add the opt-in training workload with Compose limits. `/api/health` stays honest. | Diego | Gate 2 | Thresholds are written down with their measurements, and bounded load produces a real, repeatable degradation |
| AV-04 | **Build the core capability and observer.** Registry-only `availability.load` with the ceiling, cancellation, and audit event; the independent observer that emits `target.health`; probes that continue after the load; samples persisted in the session history across a bank reset; recovery only after the healthy-probe window. | Diego | Gate 3; AV-02; AV-03 | Rejection tests pass, cancel stops the load within its bound, and recovery is reported only from the independent observer |
| AV-05 | **Point Red at the registry target.** Reported state: a run can already target a prototype in the same process (`e970727` on `red/availability-ddos`), and a probe of a registered cross-process target is reported in progress and not pushed. Needed: the runner resolves a registry target ID and requests `availability.load`, never a URL. | Red (Aaron) | Gate 3 | The runner reaches only registered targets, and an arbitrary URL is refused |
| AV-06 | **Adapt the Red availability scenario.** The scenario is reported to exist and to be verified against Red's own in-process lab. Adapt it to request the registered capability and consume the events, with availability scored apart from vault access and the referee judging achieved, not achieved, or inconclusive. | Red (Aaron) | AV-04, AV-05 | The scenario runs against the real bank, and a Red claim alone never counts as achieved |
| AV-07 | **Build the judge view.** A health timeline from `target.health` events, the labeled load start and stop, recovery, and availability shown apart from vault access. Fixtures labeled as fixtures. The arrest animation plays only after independently verified recovery. It is a story, not a contest scoreboard. | Omar | Gate 4; AV-02 | A judge can see the bank degrade and recover, and cannot see a verified arrest without verified recovery |
| AV-08 | **Wire Blue.** Joseph owns Blue. His prepared adapter uses temporary application-level source limits with expiry and rollback and privately registered client identities; it is not a firewall or a network defense. Diego must review the identity and bootstrap boundary, especially for the second browser, and adapt it to the bank's actual stack. The recovery test must follow rule 6. Reconcile his 353-test local suite with the 233 blue tests on `Mayo` before merging. Board task B-33 stays blocked and unchanged on `Mayo`. | Joseph (Blue); Diego reviews | AV-04; B-12 answers | Blue raises an availability alert from sanitized events, proposes a reversible, evidence-backed response through core, and the referee verifies recovery under continuing load |
| AV-09 | **Rehearse and set the cut line.** Repeated runs covering real degradation, recovery, an inconclusive outcome, and a fallback, with agent claims compared against the referee. If it is not repeatable, apply the cut line. | Joseph, Diego, Aaron | AV-06, AV-07, AV-08 | Repeated runs match the referee, or the live claim is dropped and a labeled fallback runs |

## What GrokBot can do, given that it cannot edit the repository

- **Paste-in only.** Everything it writes is text that a person reviews, copies into the right file, and commits. It cannot open a change itself.
- **Reasonable to draft:** AV-02 fixtures and negative cases, the AV-06 scenario adaptation and its evaluation case, and the test lists for AV-03 and AV-04.
- **Needs a person:** AV-01 (a team record), anything that changes a contract (Diego coordinates), the core guardrails in AV-04 (security-sensitive, Diego reviews), and the Blue adapter's identity boundary in AV-08.
- **Onboarding:** point it at the root `AGENTS.md`, the Red branch's `AGENTS.md` and `docs/DECISIONS.md`, the gate-status thread, and the ground rules above. Give it one sub-task at a time. It must say when it cannot open a file and must not guess its contents.
