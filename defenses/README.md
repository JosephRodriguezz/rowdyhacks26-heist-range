# Defense artifacts

Owned by Member 4. Store scoped lab patch artifacts and their metadata here. Each patch needs an ID, allowed file list, expected base version, origin, explanation, and regression checks.

Member 2's executor controls application to disposable targets; Member 3 owns the source lab. Do not directly patch another member's checkout during development. See [Member 4's assignment](../docs/team/04-blue-team-defense.md).

## Patch layout

Each patch has its own folder, named by its ID:

```text
defenses/patches/<patch_id>/
  manifest.json   metadata, file scope, and regression checks
  <diff file>     the change itself, named in the manifest
```

| Field | Meaning |
| --- | --- |
| `patch_id` | Lowercase letters, digits, and hyphens; matches the folder name |
| `status` | `draft` or `ready`. The executor must refuse a draft. |
| `origin` | `known_good_fallback` (written by a person) or `generated` |
| `base_version` | The only lab version the patch applies to |
| `policy_id` | The access policy the patch enforces |
| `target_route` | The route the patch changes |
| `allowed_files` | Repository-relative paths the patch may touch. Required when ready. |
| `diff_file` | File name of the diff in this folder. Required when ready. |
| `change`, `explanation` | What changes and why, in plain language |
| `regression_checks` | Checks the referee must run. Must include `unauthorized_access` and `owner_access`. |

`backend/app/agents/blue/patches.py` validates every manifest. It rejects absolute paths, `..`, and paths outside the patch folder.

## Current patches

- [ownership-fix-001](patches/ownership-fix-001/manifest.json): checks order ownership on `GET /api/orders/{id}`. **Draft** until Member 3 publishes the lab's order handler. Then fill in `allowed_files`, add the diff, and set `status` to `ready`.

## Supported defense actions

Blue proposes; it never executes. `backend/app/agents/blue/observe.py` makes no network calls, reads only `tools.cancelled()` and `tools.now()`, and returns JSON. Core's approved-action dispatcher executes an approved proposal and records the outcome as a `defense.applied` or `defense.failed` event; the referee's separate `retest.completed` event is the only thing that can verify a fix (`shared/contracts/README.md`, "Module boundaries" and "Verification and defense"). The executor itself (`apply(proposal, tools)` returning applied, failed, or rejected with evidence refs, original and new version, and patch provenance) is defined by the contract. Core's real executor is **not built** in this repository. A test double, `backend/app/agents/blue/executor_stub.py` (`StandInExecutor`), exists for Blue development only: it is in memory, marks every event it returns `"executor": "stand-in"`, never touches a lab or a credential, and never verifies a fix (`backend/README.md`: no backend service is implemented yet).

Every proposal is built by `backend/app/agents/blue/proposals.py` and carries `defense_id`, `action_type`, `effect`, `target_id`, `target_version`, `summary`, `reason`, `expected_effect`, `parameters`, and `alert_ids`. These are the only two action types (`ACTION_TYPES` in `observe.py`); a previous defense event with any other `action_type` is rejected as malformed.

| Action | `parameters` (exact keys) | `effect` label | Scope of one proposal | What it is not |
| --- | --- | --- | --- | --- |
| `revoke_session` | `{"session_ref": "<session reference>"}` | `containment` | One session on one target that was seen reading another user's private data. `defense_id` is derived from the action, target, and session, so the same session gets the same ID. | Not a fix. A fresh session can still use the flaw ([docs/team/04](../docs/team/04-blue-team-defense.md), item 4). The proposal's `reason` says: "Revoking it is containment and does not fix the ownership check." |
| `apply_patch` | `{"patch_id": "<manifest patch_id>", "base_version": "<manifest base_version>"}` | `remediation` | The ownership check on the server, named by a validated manifest from this folder; never raw code. `details` carry `origin`, `patch_status`, `target_route`, and `regression_check_ids`. | Not verified. `expected_effect` says: "Applied to a disposable copy only. The fix is unverified until the referee reruns every regression check, including owners reading their own orders." |

Behavior an executor can rely on (all in `proposals.py` and `observe.py`, covered by `backend/tests/blue/`):

- A session proposal names the session by reference only. The executor resolves the real credential through core's credential service, so no token passes through blue (`proposals.py` docstring; docs/team/04, item 3).
- Blue proposes no revocation for an anonymous read (there is no session to revoke) and does not propose a session already named by a previous `revoke_session` defense in this assessment, target, and data source.
- Blue proposes the patch only when an alert matches the manifest's `policy_id` on the current target version and the manifest's `base_version` equals that version. A stale manifest yields no proposal and the note "targets `<base_version>`, not `<target_version>`; not proposed." The contract makes a stale patch version a `409` at the API (`shared/contracts/README.md`, "API").
- The only patch blue knows is `ownership-fix-001` (`OWNERSHIP_PATCH_ID` in `observe.py`). If its manifest cannot be loaded, blue still returns alerts and revocations and adds a note; it never fabricates a patch.
- `apply_defense` requires a `defense_id` previously proposed in the same assessment, and the endpoint never accepts a raw patch or arbitrary command (`shared/contracts/README.md`, "API"). That endpoint is **planned**, not built.

## Patch states: draft and ready

`patches.py` accepts exactly two `status` values (`STATUSES`):

- `draft`: metadata and regression checks exist, but `allowed_files` may be empty and `diff_file` may be `null`. Blue still proposes a draft so the pipeline can be exercised end to end, and labels it three ways: the proposal's `details.patch_status` is `draft`, `PatchManifest.ready` is false, and `observe()` adds the note "is a draft; the executor must refuse it."
- `ready`: `allowed_files` must be non-empty and `diff_file` must name a file in the patch folder; `load_patch_manifest` rejects any manifest whose named diff file is missing.

Refusing a draft is the executor's responsibility. Core's real executor is **not built**; the stand-in executor refuses drafts (code `draft_patch`) so the flow can be tested, and blue's own tests prove that blue labels drafts correctly. `ownership-fix-001` is a draft today.

## Provenance: origins

The contract names three origins, and every `defense.applied` event must record one of them together with `original_version` and `resulting_version` (`shared/contracts/v1.json`; `shared/contracts/README.md`, "Verification and defense"):

| Origin | Meaning | Where it appears today |
| --- | --- | --- |
| `policy_action` | A built-in action with no patch artifact, such as `revoke_session`. | `defense.applied` for the revocation in `shared/fixtures/demo-run.json` (`lab-v1 -> lab-v1`). |
| `generated` | A patch produced by a model at run time. | Accepted by manifest validation; no generated patch exists in this folder. |
| `known_good_fallback` | A patch written and reviewed by a person in advance. | `ownership-fix-001`; the fixture's applied patch (`lab-v1 -> lab-v2`). |

A patch manifest may declare only `generated` or `known_good_fallback` (`ORIGINS` in `patches.py`); `policy_action` belongs to actions without an artifact. The blue-side report (`backend/app/agents/blue/incident.py`) copies the origin and both versions into each mitigation's details. [docs/PROJECT_SPEC.md](../docs/PROJECT_SPEC.md) ("Remediation provenance") sets the rule for presenting this: a prebuilt fixed target demonstrates regression checking, not successful application of a generated patch, and the distinction must be labeled.

## Rollback and reset

What the contract and work packets define:

- Patches are applied to a disposable copy of the target after the executor verifies base version and file scope; patch access is restricted to approved lab files and disposable copies (`shared/contracts/README.md`, "Lab interface"; PROJECT_SPEC, "Restrict source and patch access to approved lab files and disposable copies"). Rolling back a patch therefore means discarding that copy. The unpatched version is the one named in `original_version`.
- Reset is a trusted lab adapter, not a red-accessible application route. It restores the lab and returns a known target version. At the API it is allowed only after execution has ended and returns a fresh `created` assessment with a new ID and an empty event cursor, preserving the old run's history; it is refused while work is active (`shared/contracts/README.md`, "Lab interface" and "API"; [docs/team/02](../docs/team/02-orchestrator-referee.md)). In the fixture, a completed run's `allowed_actions` is `["reset"]`.
- Session revocation is also a trusted lab adapter callable by orchestration only ([docs/team/03](../docs/team/03-red-team-lab.md), item 4). No document defines reversing a revocation; the recovery path is a fresh authorized session (docs/team/03, item 7), which is exactly why revocation is containment and not a fix.

What blue does with outcomes today (built, in `observe.py` and `incident.py`, covered by tests):

- Blue accepts only `defense.proposed`, `defense.applied`, and `defense.failed` as previous defenses, and uses only those for its own target, assessment, and data source; an outcome must also concern its target version (the event's version, or a patch whose original or resulting version is this one). Retests and verdicts never reach blue's report, so its status can never be `resolved`; `observe()` raises if it ever is.
- `defense.failed`: the report shows the defense as `failed`. Blue never copies core's free-text failure reason into its output, because that text may hold a credential value (`FAILED_REASON` in `observe.py`). Blue also does not propose the same session again once a `revoke_session` proposal for it exists in scope, so a failed revocation is reported, not retried, within one assessment.
- Applied revocations count as containment in the report only when they cover every alert. An anonymous read is never covered; a read at or after its session's first applied revocation counts as continued access (a same-second read cannot be ordered, so it counts as continued). Otherwise the applied revocations are left out of the report with a note and the status stays `open`.
- Report statuses (`incident.py`): `open` ("exposure detected, not contained"), `contained` ("sessions revoked, flaw not fixed"), `awaiting_retest` (a patch is applied and no retest has passed every required check; a retest that says `passed` but lacks a required check, or has a check that failed or whose `actual` differs from `expected`, also stays here and the report's limitations name what is missing), `fix_failed` ("exposure continues after the patch"), and `resolved`, which requires a passed referee retest that covers every required check (`unauthorized_access` and `owner_access`, each with `passed` true and `actual` equal to `expected`). Mitigation outcomes are `proposed`, `applied`, `applied, awaiting retest`, `applied, retest <result>`, or `failed`.

Not built, and not pretended:

- Core's real executor and its applied/failed/rejected results, including refusing drafts and stale base versions. `StandInExecutor` simulates these outcomes for Blue's tests (`backend/tests/blue/test_blue_flow.py`); it is a test double, not core's executor.
- Rollback of an applied patch inside a running assessment. The only defined paths are discarding the disposable copy and reset.
- The lab, its reset and revoke adapters, and the `apply_defense`, `retest`, and `reset` actions ([cyber_range/README.md](../cyber_range/README.md) and `backend/README.md`: nothing is implemented yet).
- A diff for `ownership-fix-001`. It stays a draft until Member 3 publishes the lab's order handler.
- Known gaps in `incident.py`, tracked as task B-29 (found by an independent review on 2026-10-03; both reproduced): with two applied patches, the status follows the last retest of any patch, so a later patch that was never retested can still show `resolved`; and `times.fix_verified` keeps an earlier passed retest's timestamp after a later retest fails, although the status then says `fix_failed`. The first slice has one patch, so neither affects it.

## What blue never does

Set by docs/team/04, item 8 ("Defer arbitrary shell commands, firewall orchestration, and unrestricted source rewriting"), the contract's tool rules, and the code as it stands:

- No arbitrary commands, scripts, or file writes. Blue's output is JSON proposals; a patch is a manifest plus a diff limited to `allowed_files` on one `base_version`, applied by the executor, not by blue.
- No firewall, network, routing, or rate-limit changes. None of these is an action type, and no tool for them exists in blue's boundary.
- No account lockout, password reset, or user deletion. The only identity action is revoking one session reference.
- No broad blocking. Each revocation names one session; its `expected_effect` states that other sessions, including a new session for the same actor, are not affected. Blocking everyone is not a successful defense ([docs/weekend/DEMO.md](../docs/weekend/DEMO.md); root `AGENTS.md`: a fix must preserve authorized behavior).
- No execution and no verification. Blue never calls the lab, never marks its own fix verified, never emits `retest.completed`, and labels its report as blue-side, not the final incident record (`REPORT_SCOPE` in `observe.py`).
- No credentials. Sessions are references; failure reason text is not copied; telemetry is projected onto the ten contract fields before it reaches detection or the report.

## Adding a new defense: checklist

1. **Action type.** `revoke_session` and `apply_patch` are the only types in the contract (`shared/contracts/README.md`, "Verification and defense"). A new type is a contract change that Member 2 coordinates before any code; its `effect` must be either `containment` or `remediation` so the labels above stay true.
2. **Manifest (for a patch).** Create `defenses/patches/<patch_id>/manifest.json` with every field in the table above. `patch_id` is lowercase letters, digits, and hyphens and matches the folder; `status` stays `draft` until the diff exists; `origin` is `generated` or `known_good_fallback`; `base_version` is the one lab version it applies to; `allowed_files` are relative paths with no `..`, backslash, colon, or absolute prefix; `diff_file` is a plain file name inside the folder; `regression_checks` have unique IDs, include `unauthorized_access` and `owner_access`, and each `expected` is `allowed`, `denied`, or `unchanged`. Check it loads: from `backend/`, `python -c "from app.agents.blue import load_patch_manifest; print(load_patch_manifest('<patch_id>'))"`.
3. **Tests** in `backend/tests/blue/`: the manifest loads and malformed variants are rejected; the proposal appears for the right alerts and version, not for a stale version, and not twice; a draft is labeled as a draft; summary and report text keep the labels (containment is not a fix; a patch is unverified until the referee retests); no output contains a secret (`blue_test_helpers.secret_keys`). Run `cd backend && python -m unittest discover -s tests/blue` and `python scripts/check_handoff.py --self-test`.
4. **Labels for the UI.** `effect`, `details.patch_status`, and `details.origin` must be set on the proposal, and the `summary` and `expected_effect` must say what changes, where, and what remains unverified. Hand Member 1 the plain-language labels (docs/team/04, "Verification and handoff").
5. **Executor support (Member 2).** Accept the action type and its exact parameters; verify base version and file scope; refuse drafts; apply only to a disposable copy; emit `defense.applied` with `origin`, `original_version`, and `resulting_version`, or `defense.failed` with a reason that holds no credential; return `409` for a stale base version. Until this exists, document the defense as proposal-only.
6. **Retest checks (referee).** The regression checks must prove both halves: unauthorized access denied and owner access allowed. A timeout, outage, or failed login is inconclusive, never a defense (root `AGENTS.md`; [docs/weekend/DECISIONS.md](../docs/weekend/DECISIONS.md)). Only a `retest.completed` with `result: passed` can make an incident `resolved`, and blue never emits it.
7. **This file.** Add the patch under "Current patches" with its status, and keep "not built" labels accurate as the executor and lab land.
