# Red-team handoff for Codex

Status: **implementation authorized on 2026-10-19; first local red/lab/core slice implemented; production assessment orchestration remains pending**. This file
preserves the user's decisions from the Codex discussion on October 13, 2026,
originally recorded locally at `docs/RED_TEAM_HANDOFF.md` in a separate, disconnected
checkout (`ChatGPT/RowdyHacks2026`, remote pointed at the old `JosephRodriguezz/RowdyHacks26`
repo). That copy was never pushed anywhere shared. This copy lives in the actual shared
repo (`rowdyhacks26-heist-range`), on a new branch (`codex-red-team`, forked from `Mayo`)
so the work is visible and coordinable instead of sitting in a checkout nobody else
could find. It is a coordination note for the implemented local slice; it does not claim a
complete live assessment or authorize unrelated scope.

## Project context

Read `README.md`, `docs/PROJECT_SPEC.md`, `docs/ROADMAP.md`, and `AGENTS.md` before
changing implementation. The repository has a sample-data dashboard preview plus local
storefront, red-runner, target-executor, and referee primitives. It does not yet have a
live persisted assessment service or orchestration layer. The review in
`docs/reference/claude-review.md` informed the current spec; it is a critique, not an
implementation of the orchestration layer.

## Current implementation on this branch

- `cyber_range/storefront/` contains a standard-library loopback lab with runtime
  credentials, Alice/Bob seed records, one intentionally flawed detail route, a
  protected control route, sanitized telemetry, reset, session revocation, and fresh
  session adapters.
- `backend/app/agents/red/` contains a provider-neutral, deterministic red runner.
  It discovers the public route, lists permitted records, compares owner and
  cross-user responses, and returns a candidate with replay and evidence references.
  It can consume fresh account references after revocation and report the bounded
  observation as still exposed, blocked, or inconclusive.
- `backend/app/core/` contains a fixed target registry, bounded credential-reference
  HTTP executor, independent referee, and guided local orchestrator. The referee obtains
  fresh sessions, establishes an owner baseline, and replays the candidate without
  trusting red's verdict or evidence. The guided run persists its event trail in SQLite,
  sequences blue containment and fresh-session adaptation, and retests a known-good
  fallback on a disposable patched target. The executor returns redirects without
  following them; a regression test confirms that a cross-origin redirect destination
  receives no request.
- Standard-library tests cover the lab, candidate runner, protected-control false
  positives, budgets, privileged-context rejection, and loopback integration.

This is still not a complete production assessment platform: service-level cancellation,
SSE API, and dashboard wiring are not implemented here. The guided run is a local live
process with SQLite persistence; do not describe it as a deployed service or a model-
driven assessment.

## Agreed direction (unchanged from the original note)

1. **First red-team milestone:** In the registered storefront lab, discover reachable
   routes from a public entry point, run bounded access-control tests, submit a
   structured candidate finding, and have the neutral referee independently reproduce
   and verify or reject it.
2. **High-priority next milestone:** After blue revokes the attacking session, red
   obtains a fresh permitted lab session and tests whether the underlying ownership
   flaw remains. Design the first milestone's interfaces to support this without
   claiming it works before it is implemented and tested.
3. **Recon:** Start with a distinct, budgeted recon stage in the red runner that returns
   structured endpoint records. Consider a separately orchestrated recon agent after the
   first end-to-end access-control scenario is reliable.
4. **Agent decisions:** Use a provider-neutral decision interface. Establish the first
   working baseline with deterministic decisions. Connect a chosen model provider later;
   do not label deterministic behavior as a live model-driven assessment.
5. **Information boundaries:** Red receives the public entry point, scoped lab account
   access through credential references, and application observations. It does not
   receive hidden seeded ground truth, source-code answers, or blue's private context.
   The server, not a model, enforces target scope, tool permissions, request budgets,
   timeouts, and cancellation.

## Where this fits next to Claude's own red-team work (new section)

Claude (Aaron's other red-team session) has been building a separate, parallel red-team
capability on `red/availability-ddos` -> `red/engagement-authorization` -> `red/network-recon`,
in `red/prototype/` -- a different codebase lineage from `backend/app/agents/red/`
(this branch's target), descended from `main`/`codex/red-team-design`, not `Mayo`.
That work is explicitly scoped **away from access-control**, to avoid two independently
designed, incompatible "candidate finding + referee verification" protocols for the same
vulnerability class:

- Availability/DDoS load testing, an authorization/scoping framework (real HTTP
  ownership verification replacing "the target is 127.0.0.1"), network port-scanning,
  and deterministic agent-delegation rules -- none of which touch `backend/app/agents/red/`,
  Mayo's storefront lab, or access-control.
- Claude's next vulnerability-testing capability is **session-handling** (session
  reuse/fixation after logout), not access-control -- a different vulnerability family,
  so there is no collision with this milestone's access-control scope.

**Practical implication for this branch:** proceed on access-control as planned in this
note. If the candidate-finding/referee-verification *shape* (the structured record
format, the verify/reject/inconclusive vocabulary) ends up being something other
red-team work should reuse rather than reinvent, that is worth a short, explicit
conversation once this milestone has a real implementation to look at -- not something
to pre-negotiate now, before either side has working code.

## Implementation and review boundary

**Authorization update, 2026-10-19:** Aaron authorized implementation of the access-control
milestone described above. This permission covers that scope only. At authorization time,
the repository had no core HTTP tool interface or target registry; this branch now supplies
a local bounded executor for integration tests, while the production assessment API and
service orchestration remain open.

The red/lab directories belong to Member 3; core and shared interfaces belong to Member 2;
the blue agent and defense artifacts belong to Member 4. Preserve the shared contract.
Coordinate changes that cross those boundaries with the owners. Claude may review the slice,
but should not independently rewrite these modules or their interfaces. This boundary can be
changed by a new user direction.

Other contributors may continue unrelated work. Preserve their changes, including
current untracked design and Unity files in the other checkout.

## Required evidence before claiming completion

- A deterministic lab reset and access-policy checks show that each owner can read their
  own order, cross-user access is possible only on the seeded flawed endpoint, and
  unauthenticated access is denied.
- Tool tests reject unregistered target IDs, arbitrary destinations, origin changes, and
  external redirect hops; budgets and cancellation are enforced outside agent reasoning.
- A red candidate includes a reproducible role, request, observed result, and expected
  policy difference. It is labeled **candidate** until an independent fresh-session
  referee test reaches **verified**, **rejected**, or **inconclusive**.
- Events and evidence identify the exact target version and distinguish deterministic,
  recorded, sample-data, and live model-driven execution.
- When adaptation is implemented, revocation alone is not presented as a fix: red
  retries with a fresh permitted session, and the referee still checks both unauthorized
  and authorized behavior after any defense.

The local first slice, adaptation observation, target registry, bounded executor,
independent referee, guided orchestration, SQLite event trail, and full local acceptance
run are implemented and tested. Service cancellation, live SSE transport, and dashboard
wiring remain open. Add dependencies, run commands, and meaningful test commands to the
relevant manifests and `AGENTS.md` when those services are introduced.
