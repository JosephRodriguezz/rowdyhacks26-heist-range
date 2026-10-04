# Runnable local core preparation slice

The separate opt-in [availability runbook](AVAILABILITY.md) now connects the bank libraries and actual Blue availability detector on an owned disposable HTTP fixture. The commands below still describe the original access-control/vault runtime; the deployed bank and arena remain unconnected.

This is a shared-session integration of the existing disposable Red bank, actual Scout/Operator workers, and Mayo's unchanged Blue `observe()` runtime. The default provider is a **scripted integration fixture**, not adaptive AI. Its decisions drive real local HTTP and real session revocations. Diego's event bank and Omar's arena are not connected; model performance has not been measured. Patches are disabled.

## Run and verify

From the submission repository root:

```sh
python3 -m core.cli run
python3 -m core.cli run --db .core-state/core.sqlite3
python3 -m unittest discover -s tests -v
python3 -m compileall -q core red integrations/mayo/backend/app/agents/blue
git diff --check
```

The persistent CLI run creates a new contest each time and preserves previous sessions.

POSIX creation-mode checks cover private SQLite files on POSIX hosts. Windows tests validate persistence and visibility but do not certify NTFS access-control lists. Store private run databases in the operator's private workspace; do not treat a POSIX mode assertion as a Windows ACL check.

The unchanged Blue suite runs from its original relative backend layout:

```sh
cd integrations/mayo/backend
python3 -m unittest discover -s tests/blue -v
```

Expected integration: a prediction-bearing Scout handoff; Operator's own-record baseline and cross-owner comparison; Blue's telemetry-only alert and actual revocation; a denied retry with the old handle; a reopened hypothesis; a fresh login and fresh comparison; independent authorized-use, containment, and fresh-session checks. The vault verdict remains `achieved` for the earlier verified disclosure. Containment can be `verified` while `fresh_session_retry` says `unauthorized_access_persists`; `fix_status` remains `not_applied`. An unavailable service, bad fresh login, timeout, truncated response, or exhausted verification budget is inconclusive, not a successful defense.

## Presenter API

Set a strong `HEIST_CORE_TOKEN` privately in the serving process environment (at least 16 ASCII characters; a random 32-byte value is recommended). Never put it in a URL, committed file, screenshot, or shared run record. Then:

```sh
python3 -m core.cli serve --db .core-state/core.sqlite3 --port 8765
```

The CLI prints the loopback origin but never the credential. All `/api` requests require `Authorization: Bearer <presenter credential>`. `/health` is public and contains only health status. The exact loopback Host and, when provided, same-origin Origin must match. No CORS or caller-selected private audiences are supported. A future UI should use a same-origin authenticated proxy or coordinate an explicit reviewed origin policy; do not add a wildcard to make integration work.

| Method | Path | Input/result |
|---|---|---|
| GET | `/api/targets` | Registered target IDs and safe versions |
| POST | `/api/assessments` | `action_id`, `target_id: bank-local`, optional `planner_mode: fixture` |
| GET | `/api/assessments` | Judge-safe session history |
| GET | `/api/assessments/{id}` | Consistent snapshot and event cutoff |
| POST | `/api/assessments/{id}/actions` | `action_id`, `type: start/pause/resume/stop/reset` |
| GET | `/api/assessments/{id}/events?after=0` | Ordered judge-safe page and next cursor |
| GET | `/api/assessments/{id}/stream` | Authenticated SSE; `Last-Event-ID` or `after` fallback |
| GET | `/api/assessments/{id}/evidence/{id}` | Sanitized judge-safe evidence only |

POST bodies must be bounded JSON with only the documented fields. Unknown targets, destinations, tool commands, patch bodies, and private visibility selectors are rejected. Control receipts, state, and associated events commit together. Repeating the same `action_id` and request returns the recorded response; reusing it with different input conflicts. `allowed_actions` states which controls are valid. Busy targets and unsupported transitions return 409.

Events have session-scoped integer `id`/`sequence`, stable `assessment_id`, UTC timestamp, producer, visibility, data source, and evidence references. Private events leave gaps in the judge cursor. Use the returned page cutoff, not event counts, and resume strictly after it. SSE connections are bounded to 20 seconds and four concurrent streams; reconnect without replaying controls. Use fetch-based streaming to send the bearer header; native EventSource cannot set that header. Evidence and status refreshes never execute target actions.

## State, isolation, and limits

The deterministic core owns admission, target/capability policy, the shared budget, reference ownership, canonical SQLite records, and audience routing. The Red adapter uses the existing board's validated task/hypothesis logic and persists each mutation before another proposal can observe it. Blue receives at most 64 recent lab telemetry records per observation and scoped system defense outcomes, not Red's board or the referee's answer key. `read_private_order` is Mayo's compatibility action name for an owner-only read of the bank's `/api/records/{id}` surface; it does not claim that Diego implements the legacy storefront routes.

The lab's trusted adapter owns session cookies and narrow revocation; agents can name opaque references only. Revocation is authorized from actual current lab records, not caller-supplied copies of telemetry. The core issues a target revision after revocation so Red's existing duplicate-test guard allows a fresh-session comparison. No simulated defense schedule is used.

Defaults are the Red prototype's ceilings: 60 combined HTTP/admin actions (including preflight, revocation, and referee requests), 30 proposal calls, 180 wall-clock seconds, 2-second target requests, 30-second proposal calls, 16 KiB responses, and 18 turns per Red role. Blue observations additionally have a 60-step bound. Tests may use smaller budgets. Exhaustion can leave independent verification inconclusive; the referee never interprets it as a fix.

Pause stops new admission, drains bounded in-flight operations, and transitions through `pausing` to `paused`; it does not extend deadlines. Stop cancels admission and drops late proposal replies. An already-admitted HTTP action may finish and retain evidence before the terminal commit. Reset requires ended execution, closes the disposable target, invalidates old handles, and creates a new session while retaining the previous run. A process restart marks interrupted active sessions failed/inconclusive unless disclosure was already verified, never resumes actions automatically, and requires reset before another run. Only one CoreService process may own a persistent database at once; new databases are owner-readable/writable only. The SQLite file contains private synthetic evidence and must not be shared as a judge report.

## Sources and next integration

Mayo's runtime, draft patch artifact, legacy contracts/fixture, and 105-test baseline are an unchanged snapshot under `integrations/mayo/`. [SOURCE.json](../../integrations/mayo/SOURCE.json) records commit `a5fa4a375628a799198398020d6bf5dbfb8e967a` and each original Git blob hash. Its coding-workflow orchestrator was not imported. Do not edit the snapshot to resolve integration needs; update adapters or coordinate an upstream version with Mayo. In particular, the older full incident builder's incomplete-retest `resolved` behavior is not used by the core: only `observe()`'s Blue-side report is retained, and the core referee owns outcomes.

The opt-in model path reuses Red's existing replaceable provider and configuration. `python3 -m core.cli run --mode model --allow-remote-model` requires the existing provider environment configuration. The server also requires its explicit `--allow-remote-model` flag before accepting `planner_mode: model`. No remote calls are made by the default fixture run. Model-mode completion or improvement is unverified.

Diego's next boundary is a registered bank adapter with health/reset, tool-owned identity/session references, equivalent owner-only observations, sanitized telemetry, narrow revocation, and referee-only objective evidence. Omar can consume the authenticated judge projection without receiving private boards. The documented local contract additions need their review; these components are not silently migrated or assumed compatible.
