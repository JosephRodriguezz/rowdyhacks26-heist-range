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

Not yet: `observe(context, tools)`, the patch diff (waiting on the lab), or detection of repeated denied probing.

## Tests

Standard library only. Run from `backend/`:

```sh
python -m unittest discover -s tests/blue -v
```
