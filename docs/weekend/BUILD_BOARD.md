# 24-hour build board

Use elapsed hours from the official start, not a guessed calendar date. Each row is one small handoff; copy it into an issue if the team wants GitHub tracking. Keep new dependencies pinned in the owning module's lockfile and document exact run/test commands in every handoff.

## Schedule and gates

| Window | Deliverable | Gate / response if late |
| --- | --- | --- |
| H0–H0:30 | Roles, one base commit, interfaces, tool access agreed | Resolve blockers before four implementations diverge |
| H0:30–H3 | Four independently runnable slices | Joseph has fixture UI; Aaron fixture API; Diego deterministic lab; Omar telemetry detector |
| H3–H6 | Real candidate and independent proof | If missing, stop city polish and extra model work; pair on the lab/tool/verifier path |
| H6–H10 | Detection → containment → fresh-session retry | No hand-entered verdicts; both teams consume their scoped observations |
| H10–H14 | Patch applied and independent regression checks pass | Explicit fallback provenance allowed; don't call containment a fix |
| H14–H18 | UI follows real events; bounded red/blue model loops | Freeze new features at H18; scripted-only behavior must be labeled honestly |
| H18–H21 | Stop, reset, reconnect, two clean runs on demo laptop | Focus on reproducibility, not additional attack types |
| H21–H23 | Rehearsal, screenshots/video, submission materials | Capture a known-good run; label recorded playback if used |
| H23–H24 | Final verification and submission buffer | No dependency upgrades or feature merges; submit before the organizer deadline |

Take staggered food/rest breaks and keep at least one person available for integration. These windows are targets, not a requirement to work without breaks. Review dependencies every two hours and after each gate.

## Joseph — Member 1: city / UI

- [ ] **UI-01 / H0–3:** Bootstrap React + TypeScript under `frontend/`; preserve `frontend/preview`. Show the same city and three selectable characters using the shared fixture through an adapter. Deliver an actual install/run/build command and lockfile. Input: fixture. Receiver: Aaron.
- [ ] **UI-02 / H3–6:** Connect snapshot/events from Aaron's fixture API. Handle event ordering and retain character/tab selection. Show fixture/live mode visibly. Done: refresh reconstructs the same state.
- [ ] **UI-03 / H6–14:** Wire allowed launch/advance/defense/retest/stop/reset actions and sanitized evidence. Done: controls reflect API state, never timers manufacturing verdicts.
- [ ] **UI-04 / H14–18:** Switch the adapter to live events; show failures/disconnection and target versions. Done: one complete live cycle appears in the city and inspector.
- [ ] **UI-05 / H18–23:** Verify keyboard/narrow layout, rehearse the walkthrough, prepare pitch screenshots and captions. No new scenery after H18.

## Aaron — Member 2: core / independent referee

- [ ] **CORE-01 / H0–3:** Bootstrap FastAPI with health, targets, fixture snapshot/events/SSE and typed contract models. Agree the model interface and dependency lock. Receiver: Joseph. Fixture endpoints must be labeled fixture.
- [ ] **CORE-02 / H3–6:** Integrate Diego's registered target through bounded HTTP tools and fresh-session verifier. Deliver a real candidate → independently verified result with request-linked evidence. Reject arbitrary destinations and redirect escapes.
- [ ] **CORE-03 / H6–10:** Persist assessment state/events, dispatch Omar's proposals, and support bounded fresh-session retry. Add idempotency and one-active-assessment behavior; fake executors must stay labeled.
- [ ] **CORE-04 / H10–14:** Execute a version-pinned scoped patch in a disposable target and verify unauthorized denial plus owner access. Preserve patch provenance and original finding status.
- [ ] **CORE-05 / H14–18:** Connect all live flows, bounded cancellation, SSE recovery, and reset. Own Compose and documented launch/test commands. Coordinate agent budgets with Diego and Omar.
- [ ] **CORE-06 / H18–21:** Run full acceptance twice on the demo laptop. Record exact commit, target versions, and test results.

## Diego — Member 3: lab / robbers

- [ ] **RED-01 / H0–3:** Build the resettable lab, Alice/Bob seeds, protected control, and ownership behavior tests. Deliver startup/reset commands, sanitized example telemetry, and a stable patchable handler. Receivers: Aaron and Omar.
- [ ] **RED-02 / H3–6:** Return a candidate through core's tool interface; establish deterministic discovery/replay tests before the model loop. Never verify your own candidate. Deliver tool inputs/outputs, not prose-only claims.
- [ ] **RED-03 / H6–10:** Support session revocation and fresh permitted session acquisition; prove the first response is containment only. Keep lab source, ownership telemetry, and ground truth outside red's model context.
- [ ] **RED-04 / H10–18:** Add the bounded model observe/test/adapt loop through approved tools; handle refusal, timeout, malformed output, and budget exhaustion. Keep the deterministic harness for tests, distinctly labeled.
- [ ] **RED-05 / H18–21:** Verify reset reliability and negative controls; help rehearse fresh-session retry.

## Omar — Member 4: cops / defenses

- [ ] **BLUE-01 / H0–3:** Consume only telemetry and policy; detect cross-user private reads and return alerts/proposals with references. Test ordinary owner access as a negative control. Receiver: Aaron.
- [ ] **BLUE-02 / H3–6:** Agree Diego's handler and Aaron's executor interface. Prepare a reviewed ownership patch artifact pinned to the original target version. Keep source changes within the agreed scope.
- [ ] **BLUE-03 / H6–10:** Connect session-revocation proposals; record actual executor results and errors. Done: original session denied, ownership flaw still observable with a fresh session.
- [ ] **BLUE-04 / H10–18:** Connect patch proposal/application and bounded model decision loop; show generated vs known-good provenance. Request independent retests; never set the referee's verdict.
- [ ] **BLUE-05 / H18–21:** Exercise stale/rejected patches, missing telemetry, executor errors, and preserved legitimate access. Help rehearse defense limitations.

## Handoff message template

```text
Task ID / commit / PR:
What now runs (fixture, scripted, or live):
Install and run command:
Verification command and result:
Input -> output example (sanitized):
Target version / contract changes:
Known limitation / next dependency:
Receiving member:
```

A handoff is accepted when the receiver runs it. If blocked for 20 minutes, bring the failing input/output to the owning member; continue against the agreed fake adapter where possible. Keep PRs narrow and use the [merge order](../team/INTEGRATION.md).
