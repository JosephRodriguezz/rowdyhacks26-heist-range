# Shared interface contract — v1

This contract is the handoff between the four workstreams. It defines interfaces to implement, not live endpoints already available. Member 2 coordinates changes. `v1.json` defines the vocabulary and minimum fields; `../fixtures/demo-run.json` is synthetic UI/integration data.

## Module boundaries

| Module | Receives | Returns |
| --- | --- | --- |
| Red `execute(context, tools)` | assessment/target/version IDs, permitted account refs, discovered endpoints, own observations, remaining budgets | discoveries, candidate proposals with replay recipes, evidence refs, short summary |
| Blue `observe(context, tools)` | target/version IDs, sanitized telemetry, access policy, previous defenses, remaining budgets | alerts, defense proposals, evidence refs, short summary |
| Referee `verify(candidate, tools)` | candidate replay recipe, access policy, scoped fresh-session capability | verified/rejected/inconclusive + independently obtained evidence refs |
| Defense executor `apply(proposal, tools)` | approved proposal, pinned base version, scoped executor capabilities | applied/failed/rejected, evidence refs, original/new version, patch provenance |

These are async Python module boundaries inside one backend. Do not require inter-agent HTTP services. Core supplies the tools, validates results, persists them, and emits events. Members 3 and 4 can implement fake tools while core is under construction.

Common budgets: `max_steps`, `max_requests`, `timeout_seconds`; core tracks remaining values and cancellation. Agent summaries describe actions, not private reasoning traces.

## HTTP tool

```json
{
  "target_id": "storefront-lab",
  "target_version": "lab-v1",
  "method": "GET",
  "path": "/api/orders/204",
  "credential_ref": "alice-session-1",
  "request_id": "req-3"
}
```

Tools resolve an account/session reference internally. Models cannot set a host, origin, authentication header, proxy, redirect destination, or arbitrary file path. Paths beginning `//` and URLs with schemes must be rejected. Core pins target origin/port/version and validates every network operation. Results contain request ID, status/error, sanitized response, elapsed time, and evidence ID.

## Lab interface — Member 3

`GET /health`; `POST /api/session` (backend-held seed credentials); `GET /api/orders` (own records only); `GET /api/orders/{id}` (seeded flaw); `GET /api/secure-orders/{id}` (protected control).

Alice owns order 101 and Bob owns order 204 in the initial scenario. Both can discover their own IDs through their own permitted sessions. Core injects only permitted observations into red. Public fixture IDs are for integration convenience, not a general discovery strategy.

Expose reset/revoke-session through trusted lab adapters, not red-accessible application routes. Reset returns a known target version. Blue patch artifacts target an agreed stable lab handler; the executor verifies base version and file scope before applying them to a disposable copy.

Telemetry fields: `request_id`, `timestamp`, `target_id`, `target_version`, `actor_ref`, `session_ref`, `resource_id`, `resource_owner_ref`, `action`, `http_status`. `actor_ref` may be null for anonymous access. No raw token or password. Blue may read ownership metadata; red may not read this telemetry.

## API — Member 2

All paths have the `/api` prefix. Except for stream and list responses, use JSON. Errors use `{ "error": { "code": "...", "message": "..." } }`.

| Method and path | Request | Success response |
| --- | --- | --- |
| `GET /health` | none | 200 `{ "status": "ok" }` |
| `GET /targets` | none | 200 `{ "targets": [{ "id", "name", "version" }] }` |
| `POST /assessments` | `{ "action_id", "target_id", "mode": "guided" }` | 201 snapshot |
| `GET /assessments/{id}` | none | 200 snapshot |
| `POST /assessments/{id}/actions` | action object below | 202 snapshot |
| `GET /assessments/{id}/events?after=0` | numeric exclusive cursor | 200 `{ "events": [...], "last_event_id": 14 }` |
| `GET /assessments/{id}/stream` | `Last-Event-ID` or `after` query fallback | SSE events with stable IDs |
| `GET /assessments/{id}/evidence/{evidence_id}` | scoped reference | 200 sanitized evidence object |

Actions: `start`, `advance`, `apply_defense`, `retest`, `stop`, `reset`. `apply_defense` requires a `defense_id` previously proposed in this assessment. Requests include `action_id`; idempotency applies to creation and actions. Use `{ "action_id": "action-3", "type": "apply_defense", "defense_id": "defense-patch" }`. Never accept a raw patch or arbitrary command from this endpoint.

Core returns `allowed_actions` for the current phase. Stop remains possible during active work. Reset is allowed only after execution has ended; it restores the lab and returns a fresh `created` assessment with a new ID and an empty event cursor, preserving the old run's history. Unsupported transitions, busy target, reused action IDs with different bodies, and stale patch versions return 409.

Snapshot fields: `schema_version`, `id`, `target_id`, `target_version`, `mode`, `data_source`, `status`, `phase`, `last_event_id`, `allowed_actions`, `finding_ids`, `defense_ids`. Consumers obtain findings/defenses from the ordered event history; no extra list endpoints are required for the first slice.

## Event transport

Every event has `schema_version`, increasing integer `id` scoped to its assessment, `assessment_id`, ISO UTC `timestamp`, `type`, `actor`, `target_id`, `target_version`, `data_source`, `evidence_refs`, and typed `data`. See v1.json for exact event names and minimum payload keys.

SSE uses `id: <event.id>`, `event: <event.type>`, and `data: <JSON event>`. Resume strictly after the supplied cursor. Clients ignore duplicates. The snapshot's `last_event_id` defines its cutoff: reconstruct detail history through that ID, then tail subsequent events. Obtain snapshot and cutoff consistently. A refresh must never replay prior actions against the lab.

Event IDs provide order; timestamps are display data. No fabricated duration implies successful execution. UI transports and agent contexts are distinct: never send the whole event stream to a team's model.

## Verification and defense

A candidate contains ID, category, target/version, endpoint, policy ID, actor/resource refs, a replay recipe, and evidence refs. A fresh authenticated baseline is required for cross-user tests. A 200 response alone does not verify exposure; assert access policy and private-record content. Unavailable services or invalid sessions are inconclusive.

Defense proposals have ID, type (`revoke_session` or `apply_patch`), target/version, summary, reason, and scoped parameters (`session_ref` or `patch_id` plus `base_version`). `defense.applied` records origin (`policy_action`, `generated`, or `known_good_fallback`) and resulting version. Referee tests produce a separate `retest.completed` event; keep original verification history intact.

The shared sample run is intentionally short. Full acceptance also covers Alice's own order, anonymous requests, protected controls, containment rejection, cancellation, and failures. All runtime result payloads must be validated; the starter checker validates the handoff manifest and sample fixture only, not untrusted live inputs.
