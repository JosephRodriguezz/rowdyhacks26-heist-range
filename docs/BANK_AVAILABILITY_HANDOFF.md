# Bank availability adapter handoff

**Status: bank interface and opt-in core connection verified on disposable fixtures; a separate full-bank Docker Desktop rehearsal is verified.** The core browser slice calls Joseph's actual availability detector, maps Aaron's typed start/stop actions, and persists fixture assessments. The [disposable full-bank runner](core/DISPOSABLE_BANK.md) separately uses fixed registration and the actual Next.js/PostgreSQL bank on loopback port 3001, calls Blue, and independently assesses recovery. It does not register the existing port-3000 bank with the core browser presenter or pass a contest gate.

The slice measures occupied slots in a small training capacity pool inside the bank process. Load creates bounded asynchronous work; `degraded` means actual occupancy reached an approved threshold. No caller can set the health label. Ordinary bank authorization stays in place. This demonstrates application capacity and request shedding; it does not measure host CPU exhaustion, network packets, or a distributed attack.

## Sources and workspace

| Source | Inspected baseline | Use |
|---|---|---|
| Pushed bank | `codex/bank-lab-integration` at `de063b3` | Existing Next.js/PostgreSQL bank and account checks |
| Published bank interface | `codex/bank-availability-interface` at `21b4f81` | Initial bounded adapter and independent fixture checks |
| Published core/Blue preparation | `codex/core-orchestrator` at `99bc29c` | SQLite, private presenter API, and actual availability observer |
| Red | `red/availability-ddos` at `09b3bc4` | `docs/red/CORE_DISPATCH_MAPPING.md` and current proposal shape |
| Blue handoff | Mayo at `9b16046`; refreshed `origin/Mayo` at `3a2a52a` | Verified handoff baseline; Blue guard is not bypassed |
| This work | `codex/bank-availability-interface`, based on `de063b3` | Separate bank integration worktree; use this branch's commit history to pin the adapter revision |

The original dirty bank checkout and detached Mayo worktree are untouched. Current team routing is Aaron/Red, Joseph/Blue, and Diego/bank and core. Ownership does not block this authorized work. Core is published at `codex/core-orchestrator`, `99bc29c`. The separate integration branch combines that baseline and the bank interface at `21b4f81`; see [the core runbook](core/AVAILABILITY.md) for the disposable connection.

## Registration and invariants

- **AV-01 — Fixed destination.** The canonical bank target is `bank-lab`. Red's standalone `bank-local` identifies its own fixture and is rejected here, not silently aliased.
- **AV-02 — Approved scope.** [The registry](../apps/bank-lab/integration/registry.mjs) defaults to disabled. Trusted bootstrap must supply an explicit isolated-run approval and calibrated limits before any adapter request is allowed.
- **AV-03 — Bounded dispatch.** Core controls request count, aggregate concurrency, pacing, timeout, deadline, and cancellation. Model proposals cannot change them. Each adapter has one nonrenewing load budget.
- **AV-04 — Scoped evidence.** Bank run/version and exercise identity must match. Every mutating availability request carries `X-Bank-Exercise`; stale work and controls cannot affect a reset exercise.
- **AV-05 — Independent result.** An action receipt is not a verdict. Recovery needs scoped probes, successful ordinary access, and validated continuing load evidence, assessed outside Red and Blue.

The fixed deployment catalog contains `desktop` → `http://127.0.0.1:3000`, `disposable-desktop` → `http://127.0.0.1:3001`, and `docker` → `http://bank:3000`. These are code-defined origins, not a claim that any deployment is approved by default. The internal Docker origin requires core to be on the bank's internal network. Tailscale/public origins are not in this catalog. Do not replace the registry with an agent-supplied URL.

Tests register `availability-fixture` from an owned, listening loopback HTTP server on a disposable port other than 3000. Those events stay `source_mode=fixture`; they cannot be relabeled as live bank results.

## Bank HTTP surface

The [route handler](../apps/bank-lab/src/app/api/%5B...path%5D/route.ts) authenticates capability tokens before database access. It reads current bank state in a short transaction, releases the connection, then admits training work. POSTs also require an explicitly allowed Origin, JSON, a bounded object body, and the exercise header. Query parameters are rejected for all availability routes.

| Operation | Private credential mapped by server | Input | Effect |
|---|---|---|---|
| `GET /api/health` | Existing health path | None | Existing bank/database readiness: 200 `ready`, or 503 `unavailable` |
| `GET /api/accounts` | Legitimate synthetic customer's `bank_session` cookie | None | Ordinary authenticated owner-only access; core checks expected account IDs/owner and latency without exporting records |
| `GET /api/availability/status` | Probe bearer → `referee-probe` | None | Measured capacity, current exercise, and bounded transition history |
| `POST /api/availability/work` | Load bearer → `load-demo` | Exactly `{}` | One fixed-cost asynchronous work item, subject to admission quota, active cap, expiry, and mitigation |
| `POST /api/availability/control` | Executor bearer → `core-executor` | Exact action below | Narrow mitigation, restoration, stop, or idle exercise reset |

The three bearer tokens must be distinct private 64-character lowercase hex values. Their digests are compared privately; tokens, cookies, account records, raw bodies, URLs, and source addresses do not enter adapter telemetry. Models receive opaque client references, not headers or credentials.

Exact control bodies:

```json
{"action":"limit_load","client_ref":"load-demo"}
{"action":"restore","client_ref":"load-demo"}
{"action":"stop"}
{"action":"reset"}
```

`limit_load` installs a positive token bucket with explicitly configured rate, burst, and TTL for `load-demo`. It starts empty, refills up to the burst ceiling, and records a policy revision and policy-specific refusals. Existing items drain normally; referee probes and ordinary banking remain permitted. `restore` removes it. `stop` cancels pending items and closes admissions. `reset` requires idle capacity, rotates `exercise_id`, and preserves bounded history; neither team gets reset capability through the adapter.

Successful status/work responses contain `target_id`, `run_id`, `scenario_version`, `exercise_id`, `source=availability-training`, `status=available|degraded`, `active`, `max_active`, `degraded_at`, `admitted`, `completed`, `remaining_requests`, `accepting_work`, `rate_limited`, and `transitions`. Controls add `applied:true`. Each transition contains a local `sequence`, `timestamp`, `exercise_id`, `status`, and `active`. This history has a 64-row cap so it fits the adapter's 16 KiB response limit. It is not canonical contest evidence.

| Failure | Status / handling |
|---|---|
| Baseline or incomplete/malformed enablement | 404; training disabled |
| Missing credential / wrong role | 401 / 403; no work admission or DB read |
| Wrong method | 405 |
| Invalid scope, query, JSON, or action | 400; origin rejection 403; non-JSON POST 415 |
| Wrong run/version or missing/stale exercise pin | 409; run/version mismatch also cancels old pending work |
| Occupied capacity, depleted quota, expired/stopped exercise, or active limiter | 429; no hidden queue or retry |
| Bank state unavailable | 503; evaluation stays inconclusive |

## Enforced limits and approval

[The bank module](../apps/bank-lab/src/lib/availability-lab.mjs) requires every enabled environment profile field explicitly, including `BANK_AVAILABILITY_LIMIT_RPS` and `BANK_AVAILABILITY_LIMIT_BURST`. Engineering ceilings are 60 admitted items and 60 measured work attempts, 12 active items, 10 seconds per exercise, 250 ms fixed work, 10 seconds mitigation TTL, and positive rate/burst up to 10. These are not approved bank limits. Exceeding the measurement ceiling closes admission and marks data loss. The timer starts on first admitted work; quota does not refill, and stop/deadline cancel timers. Refused HTTP attempts occupy no capacity; core separately bounds all dispatch attempts.

The scope is **one bank Node process, one approved exercise, one core adapter**. In-memory limits are not aggregate protection across replicas or process restarts. Do not run multiple adapters or replicas to multiply a budget. A bank reset changes `run_id` and invalidates approval; a process/exercise reset requires fresh status, baseline, and authorization.

Trusted core approval has exactly these fields:

```text
approvalId, scope="isolated-lab", runId, scenarioVersion,
baselineEvidenceRefs=[safe reference IDs],
profile={maxRequests,maxConcurrent,durationMs,requestTimeoutMs,
         minIntervalMs,probeRequests,controlRequests},
criteria={healthMaxMs,ordinaryMaxMs,recoverySamples,baselineMaxAgeMs}
```

All profile fields are explicit positive integers. The adapter caps load attempts at 60, aggregate simultaneous HTTP calls at 12, load dispatch duration at 10 seconds, each HTTP timeout at 5 seconds, observation calls at 30, and control calls at 4. It reserves one concurrency slot each for the observer and executor; at least three total slots and two control calls are required. One control call is reserved for remote stop. Probe and control counts are separate from the load-attempt quota; all share the concurrency ceiling. Cleanup can extend beyond the dispatch deadline only by bounded in-flight control completion and one bounded stop request.

`minIntervalMs` imposes an abortable delay after each attempt, including 429s. There is no queued work, redirect following, proxy, retry, or model-selected path. Approved latency criteria cannot exceed the request timeout; `recoverySamples` is 1–5, and explicit baseline freshness cannot exceed 10 seconds. The healthy baseline must include status, readiness, and ordinary account access in the same exercise before dispatch.

The [.env example](../.env.bank-lab.example) documents bank-side fields. `BANK_SCENARIO=baseline` remains the default. `availability-training` needs all approval, pinned run/version, profile, and private token fields; malformed or missing configuration fails closed. This variant does not simultaneously enable the separate SQL injection training route. No private environment values were read or changed by this work.

## Core, Red, Blue, and referee seam

| Component | Supplied interface / next integration |
|---|---|
| Diego/core bootstrap | Construct fixed registry from approved deployment/profile; privately inject load, probe, executor, and legitimate-account credential references; own ledger/session lifetime |
| Aaron/Red | Propose `start_load_test` / `stop_load_test` with the registered `target_id`; core maps these to the adapter's fixed operations |
| Joseph/Blue | Consume sanitized health/capacity observations and opaque `load-demo` reference; propose a pre-approved defense ID; core executor calls `applyDefense(defenseId)` or `restoreDefense(defenseId)` |
| Independent referee | Evaluate trusted observation/work receipts and ordinary access; call the pure `assessRecovery` function or map these checks into the canonical evaluator |
| Arena | Receive audience-filtered projections only after the backend slice is proven; animations do not grant actions or establish outcomes |

[The adapter](../apps/bank-lab/integration/adapter.mjs) accepts Red's existing default proposal fields: `path="/"`, `method="GET"`, empty `body`, and null identity/session/form references. These are compatibility placeholders; core dispatches the fixed POST work route instead. URL, path, method, payload, identity, target-alias, and profile overrides are rejected before transport. `availability.load` / `availability.stop` are equivalent core capability names.

Trusted host methods are `describe()`, `observe("status"|"health"|"ordinary")`, `dispatch(proposal)`, `applyDefense(approvedId)`, `restoreDefense(approvedId)`, `stop()`, `wait()`, and `running()`. Only the dispatch proposal belongs in Red's tool surface. Blue does not receive Red proposals, work bodies, credential material, or this entire ledger.

[The evidence ledger](../apps/bank-lab/integration/evidence.mjs) writes allowlisted metadata for `target.health`, `availability.load_started`, `availability.work_started`, `availability.work_observed`, `availability.load_finished`, and `defense.applied`. Its envelope includes session/target/source, local sequence, timestamp, producer, evidence ID, and SHA-256 integrity digest. Optional JSONL persistence uses create-only files and fsync per entry, with a 256-entry cap. For a real run, use a core-private durable directory outside the bank; bank reset must not erase it. Digests detect accidental changes but do not replace trusted filesystem permissions or authenticate a forged journal. In-memory mode is sufficient only for disposable tests.

Core must still map these local records into its canonical sequence and apply visibility rules: sanitized observations and applied-defense receipts may be `blue_private`; work receipts and evaluation input remain `referee_only`; arena summaries are separately filtered `judge_safe` projections. The adapter does not implement a shared event bus or audience router.

The referee returns `achieved` only with a fresh healthy baseline, measured degradation, a scoped applied mitigation, a successful verification window after the last degraded sample, and healthy status after bounded stop. During that window, readiness and owner-authorized ordinary responses must meet the approved latency criteria. Validated load responses must bracket the probes, including an actual new dispatch after the last probe; a worker merely waiting in cooldown is insufficient. Missing/ambiguous work results, timeouts, identity changes, failed ordinary access, incomplete recovery samples, or later unverified regression remain `inconclusive`. A stop/defense receipt alone cannot establish success.

If evidence recording fails or the ledger closes during load, all workers are aborted and drained, and the reserved remote stop is still attempted. `wait()` rejects with a sanitized evidence failure; the host must preserve what remains and keep the run inconclusive. Do not retry with a fresh adapter to replenish its budget.

## Repeatable verification and live gate

From this branch, with Node.js 24 and pnpm installed:

```sh
cd apps/bank-lab
pnpm install --frozen-lockfile --ignore-scripts
pnpm test:availability
pnpm test
pnpm build
```

Availability tests create an ephemeral HTTP target and embedded PostgreSQL (PGlite), use actual bank login/account authorization code, and run the actual capacity module. Two repetitions record baseline → bounded load → measured degradation → explicitly approved fixture mitigation → ordinary access during continuing load → stop → independent verdict. Negative cases cover stale/reset scope, missing continuing-load proof, renewed degradation, excessive latency, authorization failure, redirects, oversized/malformed responses, and transport timeout. The responder is an explicit fixture driver, not Joseph's live Blue agent. These tests do not exercise the deployed Next.js/Nginx/PostgreSQL/Tailscale stack.

At the original bank-only `21b4f81` baseline, all 46 bank tests and the production Next.js/TypeScript build passed, with clean diff/toolkit checks. The integrated branch adds target-rate and lifecycle regressions plus actual Blue/core fixture checks; see [the current runbook](core/AVAILABILITY.md). No traffic was sent to the running bank.

Before any traffic to Diego's running bank:

1. Confirm exact source refs, canonical `bank-lab` registry entry, fixed origin, single-process isolation, and synthetic scope. No arbitrary URL adapter or `bank-local` alias.
2. Separately authorize the baseline calibration procedure. From its healthy measurements, agree on load/work limits, pacing, latency/access criteria, sample count, freshness, stop path, and evidence references. Test values and engineering ceilings are not approval.
3. Wire the actual core dispatch, approved executor, Blue telemetry routing, independent evaluator, and durable evidence retention. Verify them on the disposable target first.
4. Enable the exact approved bank run and private capability tokens, then repeat the same bounded slice. Preserve evidence before any operator bank reset; stop load before resetting.

Rollback is to stop the adapter, preserve its journal, return `BANK_SCENARIO=baseline`, and recreate only the bank service under the established local deployment procedure. Do not reset the database merely to disable the scenario. Approval and credentials must be re-established for any new exercise/run. The core dispatch and Blue/referee loop now run against an owned fixture; live-bank calibration, deployment adapter activation, adaptive Red planning, and arena routing remain pending.
