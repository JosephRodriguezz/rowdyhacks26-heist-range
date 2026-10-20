# Production-readiness audit: pointing Red at a real (non-loopback) target

**Status:** Audit only. No code has been changed as part of this document. Nothing here is a gate
pass, a deployment, or an authorization to send traffic anywhere.

**Why this exists:** Aaron stated directly (in conversation, not yet in this repository) that the
product direction changed from a hackathon demo to a shippable, client-pluggable pentest product
(comparable in category, not in scale or funding, to an autonomous red-teaming platform like
Armadin). **This is not yet a recorded team decision**: `docs/DECISIONS.md` still defines the
product as the heist-themed Red-vs-Blue range, with hosting/expansion left open. This audit uses the
stated new direction to choose which architecture to point toward and what to defer — that's a
reasonable basis to audit from, but it should be recorded as an actual decision (with attribution)
before anyone treats it as the team's agreed roadmap. Joseph and Aaron are setting up an AWS sandbox
soon so Red can be tested against a real target instead of only `127.0.0.1` mocks. This document is
the readiness pass requested before that happens: what already works, what doesn't, and who owns
each gap — not a mandate to fix everything inline.

**Scope:** `red/prototype/`'s engagement-authorization, network-recon, vulnerability-testing, and
delegation code (`engagement.py`, `network.py`, `actions.py`, `vulnerability.py`, `delegation.py`).
Not in scope: building a real API/service layer (explicitly deferred — the near-term milestone is
proving the existing engine against a real target while still invoked as a library/CLI, not
standing up a service), and not live-model/autonomous attack-chaining (explicitly a later phase).

## Summary: this is better positioned than the "lift the loopback restriction" framing suggested

The first framing of this task was "lift the loopback-only restriction." That framing isn't quite
right. There are two independent target mechanisms in this codebase, and only one of them is
loopback-restricted:

- **`FixedTargetRegistry`** (bank-local + the narrower "extra_targets" AV-05 probe path) —
  hard-restricted to `127.0.0.1`, `http` only, by explicit design (see
  [`DEPLOYMENT.md`](DEPLOYMENT.md): *"this is a deliberate safety property, not a gap to
  fix... relaxing it would be a real security-posture change... isn't part of this work"*).
- **`EngagementRegistry`/`ActionExecutor`** (web) and **`NetworkTargetRegistry`/`NetworkScanExecutor`**
  (network) — never loopback-restricted. Their safety boundary was built from the start to be
  "real, re-checkable proof of control" (HTTP well-known-file ownership verification), not "is it
  127.0.0.1." These already accept any real host. **Correction, made while addressing this PR's
  review:** at the time this sentence was first drafted, only the web path was actually pinned to
  the literal verified address (`81f53ba`) — the network path still re-resolved `target.host` fresh
  on every scan/probe, a real DNS-rebinding gap a reviewer caught. Both paths are now pinned (this
  commit); see F8 below for what was wrong and how it was fixed.

**Recommendation: do not touch `FixedTargetRegistry`'s loopback check.** It protects the legacy
bank-local path and is doing exactly the job AGENTS.md assigns it ("reject arbitrary
destinations"). The engagement/network-recon path is what should be pointed at the AWS sandbox
target — that's what it was built for, and it already works against any real host in principle.
What's actually unproven is whether it's been *exercised* against one, and whether anything quietly
assumed near-zero loopback latency or a single-process lifetime. That's what the rest of this audit
covers.

## An architecture note worth surfacing, not just a finding

`red/prototype/` currently contains **two parallel systems for finding problems**, not one:

1. **The original Scout/Operator system** (`runner.py`, `agents.py`, `baseline.py`,
   `hypotheses.py`) — targets `lab.py`'s six synthetic flaw families (including a "cross-owner
   record access" family — a form of access-control bug) on the fixed vault-bank-local lab, via
   model-or-deterministic agent turns and a `HypothesisLedger`. Per `docs/red/README.md`, this
   packet is **owned by Joseph**, built for the original vault-mission demo.
2. **The newer engagement/delegation system** (`engagement.py`, `network.py`, `delegation.py`,
   `vulnerability.py`) — targets arbitrary verified engagements/network hosts, produces
   `VulnerabilityFinding` records via `AgentAssignment`-based delegation. Built this session for the
   generalized pentest direction.

These don't collide today (different target mechanisms, different record shapes, different entry
points), but they're genuinely redundant architectures for "test for a problem and report it," and
the product direction (generalized, client-pluggable, deployable) points toward (2), not (1). I'm
not recommending removing (1) unilaterally — it's Joseph's own packet — but whoever owns the
product roadmap should know this exists before investing further in either without reconciling
them. Flagging this as a decision for you and Joseph, not something I'll resolve here.

## Findings

| # | Finding | Severity | Owner |
|---|---|---|---|
| F1 | **No durable, crash-safe persistence for the engagement/network/delegation path; the older Scout/Operator path has a narrower gap.** Corrected after review: the original `PrototypeRunner`/`cli.py --report` path *does* export `RedBoard`'s evidence/tasks/hypotheses/events to disk via `RunReport` — that part was wrong to call "no persistence anywhere." What's actually true: (a) that export only happens at the very end of a run, so a crash mid-run loses everything up to that point; (b) `EngagementRegistry`/`NetworkTargetRegistry` (engagements, verification tokens, pinned IPs) and `LabState` (`sqlite3.connect(":memory:")`) have no export mechanism at all, in either path; (c) the newer engagement/delegation system has no equivalent of `--report` — `delegation.execute_plan()`'s `VulnerabilityFinding` results only ever live in the caller's return value, nothing writes them to disk. | Should-fix-before-sandbox for (b) and (c) at minimum | Needs a storage decision (see Tasks for Codex below for one bounded slice) |
| F2 | **Raw credentials live in plain Python dicts, in memory, no secrets-manager indirection.** `SiteProfile.identities` stores `{"alice": {"email": ..., "password": "correct-horse"}}` directly; it's serialized straight into the login request body. Fine for the team's own disposable lab credentials. Not fine the moment a real client's real staging credentials are involved. | Can-wait for the AWS-sandbox milestone itself (that's still testing our own lab/mock targets, just network-reachable instead of loopback) — **must-fix before any real client engagement** | Needs a product decision (AWS Secrets Manager / Vault / etc.) before that milestone, not before this one |
| F3 | `FixedTargetRegistry`'s loopback-only check | No action — confirmed correct as-is | N/A |
| F4 | **Timeout defaults tuned for loopback.** `NetworkScope.scan_timeout_seconds` defaults to 0.5s; `RunLimits.request_timeout_seconds` defaults to 2.0s. Real round-trips (especially cross-region) could occasionally exceed these, producing spurious `filtered`/shed/inconclusive results — never a false `vulnerable` (the code fails closed), just reduced scan completeness. | Can-wait — tune empirically once a real target and its actual latency exist | Claude, as part of the first real validation run |
| F5 | **Cloud-provider abuse-detection / AWS acceptable-use coordination.** Real TCP connect-scans and unauthenticated-access probes against an AWS-hosted target could trip GuardDuty/Security Hub or confuse a SOC if nobody's told it's an authorized internal test. This isn't a code gap — it's an infra/policy item for whoever stands up the sandbox. | Should-fix-before-sandbox | Joseph/Aaron (AWS setup), not a code task |
| F6 | **No operator/user auth layer on Red itself** — anyone with code execution can register/verify/dispatch engagements directly. | Can-wait — explicitly deferred to the "Red becomes a real service" phase, which this milestone isn't | Deferred |
| F7 | **`verify_ownership`'s well-known-file check needs the target to run a real web server at the verification port.** Not a code gap — just means whoever stands up the AWS sandbox target needs to expose that file, same as any real engagement onboarding would require. | Informational | Whoever builds the AWS sandbox target |
| F8 | **The DNS-pinning fix (`81f53ba`) had only been tested against loopback mocks, and review caught two real defects in it before any real-target run.** (1) The network-scanning path (`NetworkTargetRegistry`/`NetworkScanExecutor`) was never actually pinned — `verify()` didn't capture a resolved address, and `scan_port`/`probe_unauthenticated_access` re-resolved `target.host` fresh on every call, the same DNS-rebinding gap the web path's pin was built to close. (2) The web path's pin, as originally written, connected using the pinned IP as the `HTTPSConnection` constructor's `host` — which is also what TLS SNI and certificate-hostname validation check, so a real hostname-certificate dispatch would have failed with a certificate mismatch (or worse, silently validated against the wrong identity). Both fixed in this commit: network targets now pin the same way engagements do, and dispatch uses a connection that dials the pinned IP while keeping the real hostname for everything TLS-related. Proven with new white-box tests (`DialHelperTests`, `DnsPinningTests` in `network.py`'s test suite) — not yet proven against a real non-loopback target with a real certificate. | Should-validate on the first real run (now a smaller gap: tests prove the mechanism, not yet a live network/TLS round-trip) | Claude |

## Strengths worth naming, not just gaps

- **The rate/concurrency ceilings are real safety guarantees, not advisory.** `EngagementScope` and
  `NetworkScope` both enforce hard ceilings (`max_requests_per_window ≤ 600`,
  `max_concurrency ≤ 50`, `max_ports_per_window ≤ 2000`, etc.) that a caller cannot raise past —
  this is exactly the property you want before pointing anything at a real host.
- **Ownership verification, not location, is already the trust boundary** for the engagement/network
  path — this is precisely the design a real, client-pluggable product needs, and it was built that
  way from the start, not retrofitted.
- **Fail-closed is consistent everywhere checked this session**: shed/timeout/ambiguous responses
  are `inconclusive`, never `vulnerable` — this matters more, not less, once real targets are
  involved.

## Tasks for Codex

Two different things, in two different codebases — don't conflate them:

1. **A bounded, independent task in `red/prototype/` (this lineage)**, if you want Codex working in
   parallel on F1 rather than only Claude: add a durable, append-only export of `RedBoard`'s event
   stream (JSON-lines to disk, or similar) that survives process exit, without redesigning
   `RedBoard` itself or touching the engagement/delegation code paths. This is additive, mechanical,
   well-specified, and shouldn't conflict with ongoing work here.
2. **A lesson for Codex's own access-control milestone** (`backend/app/agents/red/`, a completely
   separate codebase): when you build the candidate/referee record system for that milestone, design
   it to be durably persisted from the start, not an in-memory Python object the way `RedBoard`
   currently is — that's exactly the gap F1 surfaced here, and it's cheaper to avoid up front than to
   retrofit later.

## What changes once a real AWS target actually exists

1. Run the existing engagement + network-recon machinery against it once, end to end, with nothing
   changed yet — this is the actual test F8 and F4 are waiting on.
2. Tune timeout defaults based on observed real latency (F4).
3. Confirm the AWS side is coordinated so the test doesn't trip abuse detection unannounced (F5,
   should happen before step 1, not after).
4. Everything else in this document stays exactly as scoped: findings, not fixes, until you and
   Joseph decide what to act on.
