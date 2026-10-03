# Availability scenario: what Diego's bank needs

**From:** Red team, availability/DDoS scenario (`red/availability-ddos`, off `origin/codex/red-team-design`)
**To:** Diego — core/contract owner per the root `AGENTS.md` ("Member 2 coordinates contract and root
infrastructure changes")
**Status:** Request, not a spec. We think this is the right shape; you own the actual implementation and
can change it.

## Why we're asking

The availability scenario (`start_load_test` / `stop_load_test`, documented in
[`AVAILABILITY_SCENARIO.md`](AVAILABILITY_SCENARIO.md)) is fully built and verified, but only against a
disposable in-process Python lab we wrote ourselves. It isn't wired to the real bank/core anywhere in the
repo — we checked every branch. To demo this scenario against the real bank instead of the standalone lab,
the bank needs to expose a small, specific surface. This is scoped to the availability/DDoS scenario only —
the six vault-access families have their own separate, longer-standing integration gaps already tracked in
[`INTEGRATION_READINESS.md`](INTEGRATION_READINESS.md); this doc doesn't touch those.

This also isn't a new ask grafted on top of the contract: `docs/INTEGRATION_CONTRACTS.md` (draft 0.1, on
`codex/red-team-design`) already lists `target.health` as a planned event type and `health_check` as a
field on the target registry entry. We're asking you to fill in something the shared contract already
anticipated, not inventing new scope.

## What we need, minimally

1. **A health/business-status endpoint with an observable "available" vs "degraded" shape**, driven by a
   real (but bounded/safe) capacity signal on the bank's side — not a flag Red sets or claims. Our lab's
   `/api/status` returns `200 available` or `503 degraded` based on actual concurrent-request buildup; the
   bank's equivalent doesn't need the same mechanism, just the same property: degraded status reflects
   something true about the bank's state, not Red's self-report.

2. **A safe, bounded way to deliberately trigger that degradation for the demo.** Our `LoadProfile` hard-
   ceilings every burst (≤60 requests, ≤12 concurrent, ≤10s, ≤5s per-request timeout, enforced by
   construction, not convention). Your numbers don't need to match ours — just the *shape*: a hard,
   code-enforced ceiling, not an unbounded or network-layer DoS. Whatever triggers this on your side should
   be unable to become a real attack even if misused.

3. **Somewhere independent to read verified degraded→recovered transitions from the bank's own state** —
   never from Red's self-report. This is the piece most likely to get missed if a health endpoint gets
   added without this: our evaluator (`evaluate_availability()` in `red/evaluation/evaluator.py`) scores
   strictly from the lab's own `status_log`, never from what the load-test action claims happened. Whatever
   the bank exposes needs an equivalent independently-readable record (log, status history, event stream —
   your call) so a referee can verify "it actually degraded, then actually recovered" without trusting Red.

## What this doesn't cover

This is availability/DDoS only. It doesn't ask for anything related to the six vault-access scenario
families — those integration gaps are tracked separately in
[`INTEGRATION_READINESS.md`](INTEGRATION_READINESS.md) and aren't part of this request.

## Not a spec

We're naming the properties we need (real signal, bounded trigger, independently verifiable transitions),
not dictating implementation. How you shape the endpoint, the trigger mechanism, or the verification
surface inside the bank/core is your call.
