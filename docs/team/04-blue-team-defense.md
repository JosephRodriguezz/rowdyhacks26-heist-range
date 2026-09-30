# Member 4 — Blue team and defensive actions

## Mission

Make blue an active defender: detect suspicious behavior from telemetry, propose a bounded response, and help produce a durable code fix. The independent referee decides whether the response worked.

## Own

`backend/app/agents/blue/`, `defenses/`, `backend/tests/blue/`, and defense-specific tests. Coordinate changes to Member 3's lab through patch artifacts or a separate joint PR. Do not edit shared lifecycle or verdict logic.

## Build in order

1. Read the sample run's telemetry fixtures only and implement behavioral detection of cross-user private-record access. Do not feed attack conclusions or the whole dashboard event history into the detector.
2. Return alerts with supporting telemetry/evidence references and a concise explanation.
3. Propose a `revoke_session` action using a credential/session reference. The executor receives the actual secret only through core's credential service.
4. Show the limits of containment: a fresh session can still expose the original policy flaw.
5. Produce a bounded ownership-check patch artifact under `defenses/patches/`, scoped to the agreed lab file and base version.
6. Use a fake defense executor during independent development. Connect to Member 2's approved-action dispatcher and Member 3's isolated adapters later.
7. Return application results with the defense ID, patch origin, old/new target versions, and evidence refs. Request a referee retest rather than setting a fixed status yourself.
8. Preserve rollback/reset behavior and document supported actions. Defer arbitrary shell commands, firewall orchestration, and unrestricted source rewriting.

## Done when

- Blue flags suspicious access from telemetry without consuming red's private plan or verifier verdict.
- Ordinary owner access is a negative control and does not trigger the same alert.
- The proposal explains what will change, its target, and its expected effect.
- Session revocation is labeled containment; patch application is labeled awaiting retest.
- A known-good fallback patch is explicitly labeled `known_good_fallback`.
- Patch rejection, executor failure, and rollback have clear structured outcomes.
- No defense is called successful until independent checks preserve legitimate access.

## Verification and handoff

Run `python3 scripts/check_handoff.py --self-test`. Add blue tests for suspicious/normal telemetry, missing data, stale patch versions, action failure, and a rejected defense proposal. Hand Member 2 supported action schemas and executor results; hand Member 1 plain-language alert/action labels.

## Starter prompt

> Implement Member 4's work packet in docs/team/04-blue-team-defense.md. Read AGENTS.md and the shared contract. Own blue-agent code and defense artifacts only. Start with telemetry fixtures and a fake executor, then detect suspicious access, propose session revocation, and produce a bounded ownership patch. Keep detection independent of red conclusions, use credential references, record patch provenance, and leave verification to the referee. Coordinate lab files with Member 3 and action execution with Member 2.
