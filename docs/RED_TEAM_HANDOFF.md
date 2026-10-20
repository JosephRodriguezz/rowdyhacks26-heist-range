# Red-team handoff for Codex

Status: **planning agreed; implementation authorized on 2026-10-19; no code has been
written on this branch yet**. This file
preserves the user's decisions from the Codex discussion on October 13, 2026,
originally recorded locally at `docs/RED_TEAM_HANDOFF.md` in a separate, disconnected
checkout (`ChatGPT/RowdyHacks2026`, remote pointed at the old `JosephRodriguezz/RowdyHacks26`
repo). That copy was never pushed anywhere shared. This copy lives in the actual shared
repo (`rowdyhacks26-heist-range`), on a new branch (`codex-red-team`, forked from `Mayo`)
so the work is visible and coordinable instead of sitting in a checkout nobody else
could find. It is a coordination note, not evidence of a working red-team capability or
authorization to build the milestone.

## Project context

Read `README.md`, `docs/PROJECT_SPEC.md`, `docs/ROADMAP.md`, and `AGENTS.md` before
changing implementation. The repository currently has a sample-data dashboard preview
and planning documents. It does not have a live storefront lab, red agent, security
tool, or independent verifier. The review in `docs/reference/claude-review.md` informed
the current spec; it is a critique, not an implemented feature.

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

**Update, 2026-10-19: the user has authorized implementation work on the access-control
milestone described above.** Codex may begin building it. This authorizes the milestone
as scoped in "Agreed direction" above; it does not retroactively authorize any work
outside that scope, and it does not substitute for coordinating with the user before
changing shared lab, API, event, or credential interfaces that affect other members'
work (Member 2's core/API layer, Member 4's patch surface). Note that as of this update,
no core HTTP tool interface, target registry, or API layer exists anywhere in this
repository (checked on both `Mayo` and this branch) -- Member 3's red loop depends on
that core interface per the shared contract, so either build a fake tool adapter first
(as the member packet explicitly allows for independent development) or coordinate with
whoever is building core before assuming it is ready to integrate against.

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

The first milestone and the high-priority adaptation milestone are plans, not completed
features. Add dependencies, run commands, and meaningful test commands to the relevant
manifests and `AGENTS.md` when live services are introduced.
