# Contract v1.1: blue's requests to core and the lab

- To: Diego (core control plane, referee, and the bank lab)
- From: Aaron (blue team), task B-12
- Date: 2026-10-03
- Status: proposal. Nothing here is agreed until Member 2 publishes it under `shared/contracts/`. `shared/contracts/v1.json` is not edited by this document.

Every statement below about blue comes from reading the code on branch `Mayo`: `backend/app/agents/blue/observe.py`, `detection.py`, `proposals.py`, `patches.py`, `incident.py`, the manifest `defenses/patches/ownership-fix-001/manifest.json`, and `shared/contracts/README.md` and `v1.json`.

Labels used throughout:

- **implemented today**: blue's code already behaves this way and its tests cover it.
- **requested**: needs a change from core or the lab, or a line in the contract.
- **future, not built**: a design intention with no code behind it.

## 1. What `observe(context, tools)` accepts

`observe` is the blue module boundary from `shared/contracts/README.md`. `parse_context` in `observe.py` checks the context first. Any top-level key outside the nine below raises `ContextError`, so a red plan, candidate list, ground truth, or referee verdict that leaks into the context fails loudly instead of being read. **Implemented today.**

| Key | Required | Type and limits | Status |
| --- | --- | --- | --- |
| `target_id` | yes | non-empty string | implemented today |
| `target_version` | yes | non-empty string | implemented today |
| `data_source` | yes | one of `fixture`, `live`, `recorded` | implemented today |
| `telemetry` | yes | list of records (shape below); at most **10,000 records per call**, more raises `ContextError` | implemented today |
| `access_policy` | yes | object with exactly `id` (non-empty string) and `owner_only_actions` (non-empty list of non-empty strings); any other key is rejected; there is no fallback policy | implemented today |
| `previous_defenses` | no | list of contract `defense.proposed`, `defense.applied`, or `defense.failed` events (full event shape, all eleven `event_required` fields); any other event type is rejected | implemented today |
| `budgets` | no | object with only `max_steps`, `max_requests`, `timeout_seconds`; values must be `int` or `float` (booleans rejected) | implemented today |
| `assessment_id` | no | non-empty string | implemented today; see request below |
| `generated_at` | no | ISO 8601 UTC ending in `Z`; when absent blue calls `tools.now()`; if neither exists and there are alerts, `ContextError` | implemented today |

Behavior that follows from these checks, all **implemented today**:

- `max_steps` or `timeout_seconds` at 0 or below returns an empty result with `status: budget_exhausted`. `tools.cancelled()` returning true returns `status: cancelled`. `max_requests` is not checked because `observe` sends no requests.
- The `previous_defenses` entries must carry `schema_version: "1.0"`, an `id` that is an integer or an identifier, a UTC timestamp, identifier-shaped `assessment_id`, `target_id`, `target_version` (`[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}`), a valid `data_source`, and `evidence_refs` as a list of identifiers. Each entry is projected onto IDs, action type, `session_ref`/`patch_id`/`base_version`, origin, and versions. Summaries and reasons are dropped. A `defense.failed` reason is replaced with a fixed sentence because core's free text could hold a credential value.
- Only previous defenses for this `target_id`, `assessment_id`, and `data_source` are used. Outcomes also have to concern this `target_version` (their own version, or a patch from or to it). Everything left out is counted in `notes`.
- Request: **always send `assessment_id`**. It is optional today, but a telemetry record that carries `assessment_id` is skipped when it does not equal the context's value, including when the context has none.

Telemetry record shape (`TELEMETRY_FIELDS` in `detection.py`, matching `shared/contracts/README.md`). A record that fails a check is **skipped with a reason, never alerted on**, and the call continues. **Implemented today.**

| Field | Type |
| --- | --- |
| `request_id` | non-empty string, unique in the call (a repeat of a valid record's ID is skipped as `duplicate request_id`) |
| `timestamp` | ISO 8601 UTC ending in `Z` |
| `target_id`, `target_version` | non-empty strings equal to the context's values; others are skipped as out of scope |
| `actor_ref`, `session_ref` | non-empty string or `null` |
| `resource_id`, `action` | non-empty strings |
| `resource_owner_ref` | non-empty string or `null`; `null` on an owner-only action skips the record (owner unknown) |
| `http_status` | integer (booleans rejected) |
| `assessment_id`, `data_source` | optional today; when present they must equal the context's values |

Records are projected onto these ten fields with string, integer, or null values only. Floats, booleans, lists, objects, and every other field (ground truth, secrets, nested data) are dropped before detection, the report, and its digests.

Output (`schema: range.blue.observe/v1`): `status`, `assessment_id`, `target_id`, `target_version`, `data_source`, `alerts` (ready `alert.created` payloads), `defense_proposals` (ready `defense.proposed` payloads), `evidence_refs` (`telemetry:<request_id>`), `skipped`, `summary`, `report`, `report_scope`, `notes`. **Implemented today.**

## 2. Telemetry additions requested

Each item says what blue can and cannot conclude without it. None of these exist in the contract today; all are **requested**.

**2.1 `event_id`: an authoritative, increasing integer per record, scoped to the assessment.**
Today `detection.py` orders records by `(timestamp, request_id)` and `observe._containment` compares timestamps to decide whether a session kept reading after its revocation. Two reads in the same second cannot be ordered, so blue counts a same-second read as continued access and leaves the revocation out of the report (conservative, but it hides a real containment). The contract already says event IDs provide order and timestamps are display data; telemetry needs the same rule. With `event_id`, blue orders reads and revocations exactly and uses timestamps for display only.

**2.2 `assessment_id` and `data_source` on every record.**
Today both are optional per record and blue trusts the context's labels. Without them blue cannot tell a replayed fixture record from a live one, or a record left over from an earlier run, so a mislabeled batch would be reported under the wrong label. With them, blue skips every record that does not belong to this assessment and source, which `observe._scope` already does when the fields are present.

**2.3 `client_ref`: a keyed hash of the client.**
HMAC of the client fingerprint (for example source address plus user agent) under a per-assessment secret that core holds. Blue, the UI, and the logs see only the hash, never the secret or the raw fingerprint. Without it blue can link two sessions only when they share an `actor_ref` or `session_ref`, or hit the same records close in time, so "the same attacker came back with a fresh session" is an inference. With it, a fresh session from the same client is a direct observation, which is the trigger for proposing the patch after containment.

**2.4 Login and session-creation telemetry.**
Records for `POST /api/session` with an `action` such as `create_session`, `actor_ref` when the account is known, `session_ref` on success, and the `http_status`. Without them blue sees a new session only when it first reads something, and cannot see failed-login bursts at all. With them blue can report credential attacks and the exact time a fresh session appeared. Blue will keep the standing rule: failed logins and timeouts are inconclusive, never a successful defense and never, by themselves, a reason to escalate.

**2.5 Canary-record marker.**
A field such as `canary: true` on records whose `resource_id` is a seeded canary ("dye pack"), and the same marker on any decoy route the lab adds. The spec says canary presence alone is not a verdict, so blue would alert only when the access policy also says the read was unauthorized. Without it blue's certain signals are limited to policy violations it can prove from `actor_ref` versus `resource_owner_ref`. With it, a canary read by anyone but its owner is a certain signal with no false-positive path, which is what decision 0005 wants for immediate containment.

## 3. Event additions

**3.1 `defense.applied` must name what was applied.** **Requested.**
Today the payload is `defense_id`, `action_type`, `origin`, `original_version`, `resulting_version`. It names no session, so `observe._containment` has to tie an applied revocation back to a session through a `defense.proposed` with the same `defense_id`, or through the revocation ID blue derives (`proposals.revocation_id`). Please add `parameters` to `data`: `{"session_ref": ...}` for `revoke_session`, `{"patch_id": ..., "base_version": ...}` for `apply_patch`. Blue will then read the session from the applied event itself and no longer depend on a matching proposal being in the window.

**3.2 `defense.failed` gets a `code`.** **Requested.**
Blue never copies core's `reason` text (it may hold a secret), so today a failed defense is only "failed". Add a required `code` with exactly these values and no free text:

| `code` | Meaning |
| --- | --- |
| `draft_patch` | the manifest's `status` is `draft` |
| `stale_base_version` | the proposal's `base_version` is not the target's current version |
| `unsupported_action` | `action_type` is not `revoke_session` or `apply_patch` |
| `unknown_session` | the `session_ref` resolves to no live lab session |
| `already_applied` | this `defense_id` was already applied in this assessment |

`reason` stays as human text for the evidence record. If a failure fits none of the five, that is a contract change, not a sixth word invented at runtime.

**3.3 `agent.status` for two blue agents.** **Requested**, using the existing `agent.status` shape (`agent_id`, `status`, `summary`) with actor `blue` and the existing status words.

| `agent_id` | Reports | `status` values blue uses |
| --- | --- | --- |
| `blue-monitor` | detection: `investigating` during a call; `completed` with the observe `summary`; `blocked` on `budget_exhausted` or `cancelled`; `failed` on `ContextError`, with a fixed summary that echoes nothing from the context |
| `blue-defender` | proposals: `idle` when there is nothing to propose; `completed` with "Proposed N session revocations (containment) and M patch (draft or ready, unverified)" |

Neither agent ever reports `executing`: blue executes nothing, so that word would mislead the arena. Core writes the events (only core writes state and events); blue supplies the words. Whether blue returns a `status` list from `observe` or core derives it from `summary` is question 7.

**3.4 Document the extra keys blue already sends.** **Implemented today, requested for the contract text.**
`alert.created` data also carries `kind` (`cross_user_read` or `anonymous_read`), `policy_id`, `session_ref`, `resource_ids`. `defense.proposed` data also carries `effect` (`containment` or `remediation`), `expected_effect`, `alert_ids`, and for patches `origin`, `patch_status`, `target_route`, `regression_check_ids`. Listing them as optional keys lets the arena show them without a side channel.

## 4. Tools

**Implemented today.** `observe` reads only two things from `tools`, both optional, and never asks tools to make a request or run a defense:

| Tool | Blue expects | Used for |
| --- | --- | --- |
| `tools.cancelled()` | returns a boolean | checked once at the start; true returns an empty result with `status: cancelled` |
| `tools.now()` | returns ISO 8601 UTC ending in `Z`; called only when the context has no `generated_at`, and anything else raises `ContextError` | the report's `generated_at` |

Request: confirm these two names and return types, or tell blue the names core will use, before integration.

**`tools.model_call`: future, not built.** For a later AI advisor. The shape blue would want:

- Core owns the key, the provider, the budget (`max_model_calls` alongside the other budgets), the timeout, and the log of every call. Blue holds no credentials and cannot choose a provider or endpoint.
- Input is sanitized text blue already produced (alerts, proposals, notes). Output is text. The advisor only ranks or explains proposals that deterministic code already produced; it can never add a proposal, a parameter, a target, or an action type.
- Target content and telemetry values are untrusted input to the model, and its reply is untrusted input to blue.

## 5. Executor behavior blue relies on

Core's `apply(proposal, tools)` executes; blue never does. Blue's proposals already carry what the executor needs (`proposals.py`): `parameters.session_ref` for `revoke_session`, `parameters.patch_id` and `parameters.base_version` for `apply_patch`, plus `patch_status` and `origin` in the payload. What blue expects back:

| Executor rule | Blue's side today | Status |
| --- | --- | --- |
| Refuse a draft patch | `observe` notes "the executor must refuse it" whenever it proposes a draft; `ownership-fix-001` is a draft until B-13 | requested: `defense.failed` with `code: draft_patch` |
| Refuse a mismatched `base_version` against the target's current version at apply time | `propose_ownership_patch` returns `None` when the manifest's base version is not the current version, but the target can move between proposal and apply | requested: `defense.failed` with `code: stale_base_version` (the API already returns 409 for stale patch versions) |
| Apply only to a disposable copy, never the source lab | blue's proposal text says "Applied to a disposable copy only" | requested: `defense.applied` with `original_version` pinned and a new `resulting_version` |
| Apply each `defense_id` once | blue's defense IDs are stable, so repeated observations repeat the same proposal | requested: `code: already_applied` on a repeat |
| Reject anything blue did not propose | blue proposes two action types only | requested: `code: unsupported_action` or `unknown_session` |
| Return the events in section 3 for every outcome, with `evidence_refs` | blue puts scoped `defense.applied` and `defense.failed` events into its report | implemented today |

**Windowed telemetry delivery.** **Requested.** `observe` accepts at most 10,000 records per call and raises `ContextError` above that, so a flood of lab traffic would blind blue rather than slow it. Core should call `observe` per window (by `event_id` range) and pass the `previous_defenses` it has emitted so far. Blue's alert IDs (a digest of policy, kind, target, version, actor, session) and defense IDs (a digest of action, target, and either the session or the patch and version) are stable across calls, so repeated observations produce the same IDs and core can dedupe its events on them. Blue intends to degrade an oversized batch to an inconclusive status instead of raising; that is blue's change and is not in this request.

## 6. Report endpoint

**Requested.** `GET /api/assessments/{id}/incident-report`, served by core from the `report` and `report_scope` that `observe` returns.

- Returns the JSON report `incident.py` builds (`schema: range.blue.incident/v1`): `incident_id`, `status` and `status_label`, `target`, `times`, `elapsed_seconds`, `scope`, `impact`, `detect`, `respond` (classification and mitigation), `recover`, `improve`, `timeline`, `evidence` with a SHA-256 per item, `limitations`, `references`, and `integrity` with the report digest. `?format=markdown` returns `render_markdown(report)`.
- It is **labeled blue-side**: built from telemetry, blue's own alerts and proposals, and system `defense.applied`/`defense.failed` outcomes. It contains no referee verdicts or retests, its `recover` section is empty, its `status` is `open`, `contained`, `awaiting_retest`, or `fix_failed`, never `resolved`, and the `report_scope` sentence says it is not the final incident record. **Implemented today** in `observe`.
- It is never the referee's verdict. A report that merges referee events belongs to core and should wait: `incident._status` today marks a fix `resolved` on the last passed retest without checking that every required check passed (`ACCEPTANCE_CHECKS`), which blue's README lists as not yet done.
- With no alerts, blue returns `report: null`; the endpoint should return 200 with `report: null` rather than an error (question 8).

## 7. What blue guarantees

All **implemented today**, each with tests in `backend/tests/blue/`:

- **Isolation.** Unknown context keys raise. Telemetry is cut to the ten contract fields with scalar values. Previous defenses may be only the three defense event types; a `retest.completed` or `finding.*` event in the context raises. The patch is always `ownership-fix-001` from `defenses/patches/`, never a path or ID taken from the context. Fixture, recorded, and live events never change each other's results.
- **Labeling.** `data_source` passes through unchanged. Every proposal carries `effect: containment` or `effect: remediation`, and the revocation text says it does not fix the ownership check. Every patch proposal carries `origin` and `patch_status` and says it is unverified until the referee retests. The report is labeled blue-side and can never say `resolved`; `observe` raises if the report it built ever says so.
- **Determinism.** No randomness, no wall clock except the `generated_at` core supplies or `tools.now()`. Alert and defense IDs are SHA-256 digests of their grouping keys. Sorting is by timestamp and `request_id`, so the same input gives the same output.
- **No execution.** `observe` makes no network call, writes no file, runs no process, and resolves no credential. It reads one manifest from the repository. A `session_ref` is a reference; the executor resolves the real credential through core's credential service.
- **No secrets.** Blue never copies a failure reason. Report evidence drops fields whose names contain `password`, `token`, `secret`, `cookie`, `authorization`, or `api_key` before hashing.
- **Fail closed.** Missing or malformed inputs raise or skip; nothing is guessed. A missing owner on an owner-only read is "owner unknown", not "protected".

## 8. Pending B-19: swarm items, intentions only

These are not requests in v1.1. The B-19 design spec will turn whatever survives review into concrete requests.

- **Clusters.** Group related reads across sessions and actors within a time window, using only core-generated telemetry fields (and `client_ref` from 2.3 if it arrives). A cluster would be an inference, never proof of coordination, and would need its own event type.
- **PACE tiers.** Primary (revoke the attacking session) and Alternate (the ownership patch) exist today as proposals. Contingency (reroute the vulnerable route to the protected control, or force re-login) and Emergency (stop and reset, human only) would need new action types and lab adapters. Until then the arena should show them as unavailable, never armed.
- **Posture.** Armor data for the arena (D3FEND's seven tactics with heist names) credited by proven state: a referee-verified fix counts fully, an applied patch partly, containment a little, a failed defense shows as cracked. This would need a posture event or endpoint and the referee's `retest.completed` results as its only source of "verified".

## 9. Machine-readable summary of the proposed v1.1 additions

A diff against `shared/contracts/v1.json`, not a replacement. `status: existing` means the event type is already in v1 and only gains keys; nothing new is added to `event_types` in this round. The block below was parsed with Python and every event type it names was checked against `v1.json` and every telemetry field against `detection.TELEMETRY_FIELDS`.

```json
{
  "proposal": "blue requests for shared contract v1.1 (task B-12)",
  "base": {"file": "shared/contracts/v1.json", "schema_version": "1.0"},
  "proposed_schema_version": "1.1",
  "event_types": {
    "alert.created": {
      "status": "existing",
      "add_required": [],
      "add_optional": ["kind", "policy_id", "session_ref", "resource_ids"]
    },
    "defense.proposed": {
      "status": "existing",
      "add_required": [],
      "add_optional": ["effect", "expected_effect", "alert_ids", "origin", "patch_status",
                       "target_route", "regression_check_ids"],
      "enums": {"effect": ["containment", "remediation"], "patch_status": ["draft", "ready"]}
    },
    "defense.applied": {
      "status": "existing",
      "add_required": ["parameters"],
      "add_optional": [],
      "note": "parameters.session_ref for revoke_session; parameters.patch_id and parameters.base_version for apply_patch"
    },
    "defense.failed": {
      "status": "existing",
      "add_required": ["code"],
      "add_optional": [],
      "enums": {"code": ["draft_patch", "stale_base_version", "unsupported_action", "unknown_session", "already_applied"]}
    },
    "agent.status": {
      "status": "existing",
      "add_required": [],
      "add_optional": [],
      "blue_agent_ids": ["blue-monitor", "blue-defender"],
      "note": "actor blue; blue agents never report executing"
    }
  },
  "telemetry_fields": {
    "existing": ["request_id", "timestamp", "target_id", "target_version", "actor_ref", "session_ref",
                 "resource_id", "resource_owner_ref", "action", "http_status"],
    "add_required": ["event_id", "assessment_id", "data_source"],
    "add_optional": ["client_ref", "canary"],
    "notes": {
      "event_id": "increasing integer per assessment; the only ordering key, timestamps are display data",
      "client_ref": "HMAC of the client fingerprint under a per-assessment secret held by core; blue, UI, and logs see the hash only",
      "canary": "true when resource_id is a seeded canary record or a decoy route; never a verdict by itself"
    },
    "add_actions": ["create_session"]
  },
  "module_boundaries": {
    "blue.observe": {
      "context_required": ["target_id", "target_version", "data_source", "telemetry", "access_policy"],
      "context_optional": ["previous_defenses", "budgets", "assessment_id", "generated_at"],
      "access_policy": {"id": "string", "owner_only_actions": ["string"]},
      "budgets": ["max_steps", "max_requests", "timeout_seconds"],
      "max_telemetry_records_per_call": 10000,
      "previous_defenses_event_types": ["defense.proposed", "defense.applied", "defense.failed"],
      "tools": {
        "cancelled": {"returns": "bool", "status": "implemented today"},
        "now": {"returns": "ISO 8601 UTC ending in Z", "status": "implemented today"},
        "model_call": {"status": "future, not built", "budget": "max_model_calls", "keys_held_by": "core"}
      },
      "output_schema": "range.blue.observe/v1"
    }
  },
  "executor": {
    "refuses": {"draft_patch": "manifest status draft", "stale_base_version": "base_version is not the current target version",
                "unsupported_action": "not revoke_session or apply_patch", "unknown_session": "session_ref unknown",
                "already_applied": "defense_id already applied in this assessment"},
    "applies_to": "disposable copy only",
    "telemetry_delivery": "windowed by event_id, at most 10000 records per observe call"
  },
  "api": {
    "GET /assessments/{id}/incident-report": {
      "status": "new",
      "returns": "range.blue.incident/v1 JSON, or markdown with ?format=markdown; report null when there are no alerts",
      "label": "blue-side report; no referee verdicts; status never resolved"
    }
  }
}
```

## 10. Questions Diego must answer

1. Do the nine context keys and the `access_policy` shape in section 1 stand, or will core use other names? Blue's allowlist rejects anything else, so this blocks integration.
2. Will every telemetry record carry `event_id`, `assessment_id`, and `data_source`? If not, how does core guarantee ordering and scope for blue?
3. How often is `observe` called, with what window size, and does each call include the `previous_defenses` core has emitted so far in this assessment?
4. Can `defense.applied` carry `parameters` (3.1)? If not, core must guarantee that the matching `defense.proposed` is always in the same window.
5. Is the five-code list for `defense.failed` complete for the first slice? Which code does core use for a lab outage or executor error, or does that need a contract change first?
6. Are `tools.cancelled()` and `tools.now()` the names and return types core will provide (section 4)?
7. For `agent.status`: does core derive the two blue agents' status from `observe`'s result, or should blue return a `status` list? Which agent IDs does the arena expect?
8. Report endpoint: is the path and the `?format=markdown` parameter acceptable, and should "no alerts" be 200 with `report: null` or an error?
9. Lab side: can the lab emit the keyed `client_ref`, `create_session` telemetry, and a canary marker, and for which record IDs?
10. Which of these are needed for the live demo gate and which can wait until after it?
