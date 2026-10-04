# Blue team module

Owned by Member 4. Implement the async `observe(context, tools)` boundary described in [the shared contract](../../../../shared/contracts/README.md).

Start with sanitized telemetry and a fake defense executor. Return alerts/proposals, not independent verification verdicts. Full assignment: [Member 4](../../../../docs/team/04-blue-team-defense.md).

## Detection

`detection.py` flags successful owner-only reads made by another user (`cross_user_read`) or by no user (`anonymous_read`). It reads telemetry and the access policy only, never red's findings or referee verdicts.

```python
from app.agents.blue import PRIVATE_ORDERS_POLICY, detect_suspicious_access

result = detect_suspicious_access(telemetry_records, PRIVATE_ORDERS_POLICY)
for alert in result.alerts:
    alert.event_data()  # alert.created payload: alert_id, request_ids, summary, ...
```

- An owner reading their own record never alerts. Denied attempts (4xx/5xx) do not alert.
- Alerts group per session and target version, so an exposure after a patch is a separate alert.
- Alert IDs are stable as telemetry grows, so repeated observations update the same alert.
- Records with missing or malformed fields go to `result.skipped` with a reason and never raise an alert.
- Alerts reference telemetry by `request_ids`; core maps those to evidence IDs.
- `PRIVATE_ORDERS_POLICY` stands in until core supplies the access policy through the agent context.

## Session revocation proposals

`proposals.py` turns cross-user alerts into `revoke_session` proposals. Blue proposes; core's dispatcher executes.

```python
from app.agents.blue import propose_session_revocations

proposals = propose_session_revocations(result.alerts, previous_defenses)
for proposal in proposals:
    proposal.event_data()  # defense.proposed payload: defense_id, action_type, summary, reason, parameters, ...
```

- One proposal per session. `parameters` holds only `session_ref`; the executor resolves the real credential through core.
- Every proposal is labeled `effect: "containment"` and says it does not fix the ownership check. A new session for the same user is unaffected.
- Sessions named by an earlier `revoke_session` in `previous_defenses` are not proposed again. A fresh session that repeats the read gets its own proposal.
- Anonymous reads have no session to revoke. They need the ownership patch.
- Defense IDs are stable, so repeated observations produce the same proposal.

## Ownership patch proposal

`propose_ownership_patch` proposes the fix in [defenses/patches/ownership-fix-001](../../../../defenses/patches/ownership-fix-001/manifest.json) when the current target version still leaks data. `patches.py` validates the manifest first.

```python
from app.agents.blue import load_patch_manifest, propose_ownership_patch

manifest = load_patch_manifest("ownership-fix-001")
proposal = propose_ownership_patch(result.alerts, manifest, current_version, previous_defenses)
```

- `parameters` holds `patch_id` and `base_version` only. The proposal never carries code.
- Labeled `effect: "remediation"` and says the fix is unverified until the referee retests.
- Not proposed when the patch was built for a different base version, when no alert on the current version matches the patch's policy, or when it was already proposed.
- Carries provenance in `origin` (`known_good_fallback` or `generated`) and `patch_status`.
- The manifest is a **draft** until Member 3 publishes the lab's order handler. The executor must refuse a draft.

## Incident evidence report

`incident.py` builds one report per run from telemetry, blue's alerts, and system and referee events. It never reads red's candidates or reasoning. `render_markdown` turns it into a document a person can read or attach to a ticket.

```sh
# From backend/: build the report for the shared sample run
python -m app.agents.blue.report
python -m app.agents.blue.report --format json --out incident.json
```

The report follows the NIST CSF 2.0 Functions used by NIST SP 800-61 Rev. 3:

| Section | CSF | Contents |
| --- | --- | --- |
| Detect | DE.CM, DE.AE | Alerts: session, records, request IDs, first and last seen |
| Respond: analysis | RS.AN | ATT&CK T1190 and T1078, CWE-639, OWASP API1:2023, scope and impact |
| Respond: mitigation | RS.MI | Each defense, its effect (containment or remediation), outcome, and provenance |
| Recover | RC.RP | Referee verdicts and retest checks, kept separate from blue's claims |
| Prevent and improve | ID.IM and related | Code, test, detection, and process steps, each with a CSF category and references |
| Evidence | | Every telemetry record and event used, with a SHA-256 digest |

### Which evidence is kept, and why

| Evidence | Why it is needed |
| --- | --- |
| Sanitized telemetry for each alerted request | Shows who read what, whose it was, and when. It is the basis for the alert. |
| Alert grouping by session and target version | Shows what to contain and whether the exposure continued after a patch |
| Key times (first read, detected, contained, patched, verified) | Feeds the detection and containment times the spec asks for |
| Defense outcomes with origin and versions | Separates containment from remediation, and a generated patch from a fallback |
| Referee verdicts and retest checks | Only the referee can say a finding or fix is verified. Blue never restates it. |
| Data source label | A fixture or recorded run can never pass for live evidence |
| Limitations | States which checks are still missing, and what containment does not fix |
| SHA-256 per item and for the whole report | Anyone can confirm the evidence was not changed after the report was made |

Fields named like secrets (`password`, `token`, `cookie`, `authorization`, `api_key`, `secret`) are removed before hashing. The report status is `resolved` only after a passed retest of an applied patch, and `fix_failed` if the cross-user read appears on the patched version.

Framework mappings live in `frameworks.py` with source links. They are analyst judgments for this scenario.

**How people get the report:** for now, run the command above. In the app, Member 2 would serve it from an endpoint such as `GET /api/assessments/{id}/incident-report`, and Member 1 would add a download button to the evidence panel. Both need a contract change, which Member 2 coordinates.

## Entry point: `observe(context, tools)`

`observe.py` is the blue module boundary from the shared contract. It runs detection, session revocations, the ownership patch, and the incident report in that order, and returns one JSON-ready result. It adds no detection logic, makes no network calls, and executes nothing.

```python
from app.agents.blue import observe

result = await observe({
    "target_id": "storefront-lab", "target_version": "lab-v1", "data_source": "live",
    "telemetry": telemetry_records,
    "access_policy": {"id": "private-orders-owner-only", "owner_only_actions": ["read_private_order"]},
    "previous_defenses": [],                     # optional
    "budgets": {"max_steps": 5},                 # optional
    "assessment_id": "run-1",                    # optional
    "generated_at": "2026-09-30T16:00:00Z",      # or tools.now()
}, tools)
# result: schema, status, target/version, data_source, alerts, defense_proposals,
#         evidence_refs, skipped, summary, report, report_scope, notes
```

- **Strict context.** Any other top-level key (`events`, `candidates`, `ground_truth`, `red_*`, `verdicts`, ...) raises `ContextError`, so a leak from red or evaluation fails loudly. The raw context is never passed to the helpers.
- **No fallback policy.** A missing or malformed `access_policy` raises `ContextError`; `PRIVATE_ORDERS_POLICY` is never substituted.
- **Scoped, projected telemetry.** Records for another target, version, assessment, or data source, records the detector cannot evaluate, and repeats of a valid record's `request_id` go to `skipped`, never to an alert. A record is validated before its `request_id` is reserved, so a malformed record cannot hide a valid one with the same ID. Kept records are cut down to the detector's telemetry fields with string, integer, or null values, so extra fields (ground truth, secrets, nested data) never reach the report or its digests.
- **Previous defenses** must be contract `defense.proposed` (actor `blue`), `defense.applied`, or `defense.failed` (actor `system`) events, or blue's own `DefenseProposal` objects. Bare payloads are rejected because they name no target or assessment. Any other event type, such as `retest.completed` or `finding.verified`, raises `ContextError`. Each entry is validated and projected onto IDs, action type, session or patch parameters, origin, and versions. Summaries, reasons on proposals, and unknown fields are dropped. A `defense.failed` reason is checked to be a string and replaced with a fixed message (`FAILED_REASON`); core's free text is never copied, since it may hold a credential value.
- **Scoped previous defenses.** Only defenses for this target, assessment, and `data_source` deduplicate proposals, so a fixture or recorded event never changes a live report and the reverse. `DefenseProposal` objects carry no assessment or data source and count for the current ones. Only `defense.applied`/`defense.failed` outcomes that also concern this target version (its own version, or a patch from or to it) reach the report. Everything left out is counted in `notes`.
- **Containment must cover every alert.** `defense.applied` names no session, so an applied revocation is tied to a session through a scoped `defense.proposed` with the same `defense_id`, or through the revocation ID blue derives for an alerted session (`revocation_id`). If any alert is anonymous, comes from a session no applied revocation names (a fresh session, say), or shows an unauthorized read at or after its session's first applied revocation (same-second reads count, since they cannot be ordered), the applied revocations are left out of the report with a note, so it stays `open` instead of claiming `contained`. Revoked sessions are not proposed again.
- **Blue-side report.** The report gets blue's own alerts and proposals from this observation plus those scoped system outcomes, never referee verdicts or retests. Its status is `open`, `contained`, `awaiting_retest`, or `fix_failed`, never `resolved`. `report_scope` says it is not the final incident record; the full report with Recover verdicts stays with core and `report.py`.
- **Patch.** Always `ownership-fix-001` from `defenses/patches/`, never a path or ID from the context. If the manifest cannot be loaded, alerts and revocations are still returned with a note.
- **Budgets and cancellation.** `max_steps` or `timeout_seconds` at 0 or below, or `tools.cancelled()` returning true, gives an empty result with status `budget_exhausted` or `cancelled`. `max_requests` is not checked because observe sends no requests; check it once tools can execute.
- **Tools are inert in M1.** observe reads only `tools.cancelled()` and `tools.now()` when present.
- `data_source` must be `fixture`, `live`, or `recorded` and is passed through unchanged.
- `app.agents.blue.observe` is the function, not the module. To patch the module, use `importlib.import_module("app.agents.blue.observe")`.

The context key names and the `access_policy` shape are a blue proposal. Member 2 must confirm them before core integration.

Not yet: the patch diff (waiting on the lab), detection of repeated denied probing, and a stricter `incident._status` that resolves only when every required retest check passed (needed before core builds reports with referee events).

## Tests

Standard library only. Run from `backend/`:

```sh
python -m unittest discover -s tests/blue -v
```
