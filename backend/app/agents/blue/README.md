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

Not yet: `observe(context, tools)`, defense proposals, or detection of repeated denied probing.

## Tests

Standard library only. Run from `backend/`:

```sh
python -m unittest discover -s tests/blue -v
```
