# Member 3 — Red team and vulnerable lab

## Mission

Build the real, resettable target and a red agent that can discover its ownership flaw through application behavior. Shipping the target first unblocks all other members.

## Own

`cyber_range/`, `backend/app/agents/red/`, `backend/tests/red/`, and lab-specific tests. Member 2 owns the shared HTTP executor and root Compose; Member 4 owns defense proposals and patch artifacts.

## Build in order

1. Implement the [lab interface](../../shared/contracts/README.md): health, sessions, own-order listing, private-order retrieval, and a protected control route.
2. Seed Alice and Bob with separate private orders and stable reset behavior. Seed credentials are provisioned to the backend, not returned in public UI events.
3. Emit structured telemetry containing request correlation, actor, resource owner, action, status, and time. Exclude raw session tokens and passwords.
4. Provide test-only reset and session-revocation adapters, callable by trusted orchestration only. Document the isolated runtime boundary.
5. Build red's route discovery and bounded observe/test/adapt loop using the core HTTP tool interface. For independent development, use a fake tool adapter with the same signature.
6. Return a structured candidate with target/version, endpoint, policy ID, replay recipe, and evidence references. Never mark your own candidate verified.
7. Support retrying with a fresh authorized lab session after blue revokes the first session.
8. Coordinate the ownership-fix location with Member 4. Preserve stable interfaces while the defense is developed.

## Isolation of challenge knowledge

The developer knows the challenge. The runtime red agent must not read lab source, seed internals, telemetry ownership fields, or hidden vulnerability ground truth. It discovers record IDs through permitted accounts and responses. Member 2 maintains evaluation truth separately. Source access for remediation is a different, blue-team capability.

## Done when

- A reset deterministically reproduces the expected vulnerable and protected behavior.
- The protected control never becomes a finding merely because it returns HTTP 200.
- Red produces a replayable candidate rather than a prose-only claim.
- Revocation blocks the original token but does not masquerade as an ownership fix.
- Application logs correlate to requests without leaking credentials.
- The target can run without an LLM key; red unit tests use a bounded fake tool.

## Verification and handoff

Run `python3 scripts/check_handoff.py --self-test`. Add lab tests covering Alice's own order, Bob's private order, Bob's own access, unauthenticated access, protected control, reset, and revocation. Give Member 2 startup/reset and registration details; give Member 4 sample telemetry and the stable patch surface.

## Starter prompt

> Implement Member 3's work packet in docs/team/03-red-team-lab.md. Read AGENTS.md and shared/contracts/README.md. Build the resettable local storefront lab first, then the bounded red agent. Own cyber_range and red-agent files only. Use the core target-scoped tool interface, emit sanitized correlated telemetry, and return candidate findings with reproducible evidence. Keep source, seed answers, and ground truth out of the runtime red context. Coordinate root infrastructure with Member 2 and the patch surface with Member 4.
