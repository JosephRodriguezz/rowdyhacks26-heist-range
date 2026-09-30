# Integration checklist

## Merge order

1. Shared contracts and fixtures (this starter kit).
2. Member 3's resettable lab and Member 2's fixture API; these can merge independently.
3. Member 1's fixture-driven UI and Member 4's fixture-driven detector/proposals.
4. Core + real lab + red candidate + independent verification.
5. Core + telemetry + blue containment + red fresh-session retry.
6. Patch application + independent retesting + full frontend event flow.
7. Root Compose, reset reliability, cancellation/reconnect, and rehearsals.

Merge small interface-compatible slices throughout the hackathon. Never wait for four finished branches.

## Each module PR

- [ ] Own-directory edits only, or explicit coordination with the owner.
- [ ] `python3 scripts/check_handoff.py --self-test` passes.
- [ ] Relevant functional checks pass and exact commands appear in the PR.
- [ ] Fixtures/sample output still match the shared vocabulary.
- [ ] New dependency and environment-variable changes are documented.
- [ ] Receiving member verifies the handoff against their adapter.
- [ ] No credentials or real private records in events, fixtures, or screenshots.

## Live demo gate

- [ ] Clean seed state and known original target version.
- [ ] Launch from the UI using a registered target ID.
- [ ] Observe a real candidate; independently reproduce the policy violation.
- [ ] Detect the behavior from telemetry, independent of red's conclusion.
- [ ] Apply session revocation and show the original session rejected.
- [ ] Retry with a fresh permitted lab session and demonstrate the remaining flaw.
- [ ] Apply a scoped patch to a disposable target; show provenance and version.
- [ ] Deny unauthorized access while preserving owner access.
- [ ] Confirm unauthenticated and protected-control behavior.
- [ ] Stream actual events into character states, timeline, and evidence.
- [ ] Stop a run, reconnect a UI, and reset without duplicate actions or stale results.
- [ ] Repeat from a clean state. Clearly label any recorded fallback.

## Minimal integration rules

Use a single backend process and one active assessment initially. Red and blue are in-process modules with separate contexts, not separate web services. Only core writes persistent state and events. The lab is a separate process/container. Do not add a message broker or distributed scheduling for the MVP.

All client commands include an `action_id`. Core serializes accepted actions, rejects stale/unsupported actions with 409, deduplicates retries, and returns the current snapshot. A stop transitions the run to `cancelled` after cancellation is confirmed; a UI button click alone does not establish cancellation.

UI replay may use the complete sanitized run fixture. Blue and red must receive only their scoped inputs. Public sample data is not live evaluation ground truth.
