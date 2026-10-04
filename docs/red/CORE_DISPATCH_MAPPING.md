# Core-dispatch mapping: what Red has today, and what moves to core

**From:** Red (Aaron), for the handoff Joseph asked for in `blue-team/comms/threads/gate-status.md`
("Immediate handoffs: Aaron provides the Red branch ref and core-dispatch mapping").
**Branch ref:** `red/availability-ddos` @ `7979463`.
**Status:** A mapping, not a spec Diego has to match exactly. It names what exists, what the proposed
interface implies should move to core, and what should stay Red's regardless. Diego and Joseph own the
actual shape.

## Why this doc exists

There is no core control plane in this repository yet, on any branch. Red's standalone prototype currently
plays every role at once: requester, dispatcher, target registry, and referee. Once core exists and takes
over dispatch, resolution, and verification, most of that collapses onto core — Red keeps only the part that
was always meant to be Red's: deciding to ask. This is the role-by-role accounting of what moves, so the
core team (and whoever wires this) isn't guessing at Red's internals.

## Today's shape, exactly as built

| Piece | File | What it does |
| --- | --- | --- |
| Request | `ActionProposal(capability="start_load_test"\|"stop_load_test", target_id="bank-local")` | No other field accepted — `_validate_load_proposal` in `actions.py` rejects any non-default `path`, `method`, `body`, `identity_ref`, `session_ref`, or `form_ref`. The model can pick the capability and nothing else. |
| Target resolution | `FixedTargetRegistry` (`actions.py`) | Red's own registry. Resolves `target_id` to a loopback-only origin it was constructed with. There is exactly one entry (`bank-local`) in the standalone scenario. |
| Ceiling | `LoadProfile` (`domain.py`) | Frozen dataclass, hard-ceilinged in `__post_init__`: `max_requests≤60`, `concurrency≤12`, `duration_seconds≤10`, `request_timeout_seconds≤5`. No field on `ActionProposal` can raise these — they're fixed at process construction, not per-request. |
| Dispatch | `ActionExecutor._execute_start_load` / `_execute_stop_load` (`actions.py`) | Red's own code opens the HTTP connections, runs the bounded burst in a background thread pool, and tracks cancellation (`threading.Event`) and the one-active-load-at-a-time invariant. |
| Audit events | `RedBoard.record_event` (`actions.py`) | `availability.load_started`, `availability.load_completed` (self-terminated), `availability.load_stopped` (explicit stop). All board-local, not core events today. |
| Health/degrade signal | `LabState.record_status_observation` (`lab.py`) | The lab server itself, not Red, records `available`/`degraded`/`rate_limited` into `status_log` when it handles `/api/status`. Target-side, but it's *Red's own* target. |
| Ordinary-access-during-load signal | `LabState.record_ordinary_access_observation` (`lab.py`), new this session | Same pattern, for `/api/catalog`, tagged with whether a load was active. |
| Verification | `evaluate_availability`, `evaluate_ordinary_access_during_load` (`evaluator.py`) | Red's own evaluator reads Red's own target's logs. This is Red playing referee on its own fixture — honest for a standalone demo, not the real separated-referee architecture. |

## The proposed interface (Blue → Diego, not yet accepted) and where each piece lands

From `blue-team/proposals/red-availability-subtasks.md` (`f2a3f60`), the "interface Blue proposed":

| Proposed piece | Owner | Maps to / replaces |
| --- | --- | --- |
| `target.health` event (`available`/`degraded`/`unavailable` + sanitized evidence ref), emitted by a core-side observer measuring the real `GET /api/health` | Diego | Replaces `LabState.record_status_observation` + `status_log`. Core's observer takes over the role the lab server currently plays for itself. `/api/health` itself stays unchanged — same as `/api/status` isn't modified to carry a flag today. |
| `availability.load` capability: Red requests it for a registered target; core fixes the route, enforces the ceiling and cancellation, emits the audit event. **The request cannot choose a URL or set a "degraded" flag.** | Diego enforces; Red requests | Replaces `ActionExecutor._execute_start_load`/`_execute_stop_load` and `LoadProfile`'s ceiling. Red's side shrinks to exactly what `_validate_load_proposal` already enforces today: a capability name and a `target_id`, nothing else. The ceiling moves from Red's `LoadProfile` to core's own configuration — Red stops being the thing that decides or enforces the numbers. |
| Independent core/referee observer that keeps probing after load stops, records samples in core's session event history (survives a bank reset), reports recovery only after an agreed healthy-probe window | Diego | Replaces `evaluate_availability` and `evaluate_ordinary_access_during_load` reading Red's own `LabState`. Red's evaluator becomes the *fixtures-only fallback path* — useful for the standalone demo and for testing Red's own request-shape in isolation, never the verifier once core exists. |

## What this implies, concretely, for Red's own code when core exists

1. **`ActionProposal` doesn't change shape.** It already carries only `capability` + `target_id` for a load action — that was deliberate, and it's exactly what `availability.load` needs. No new field has to be added to make this work; the opposite would be the problem (any new field here would be a smuggled-in URL or flag).
2. **`FixedTargetRegistry` stops being the registry-of-record for anything but the standalone fixture.** Today it resolves `bank-local` to Red's own loopback lab, and (since this session's AV-05 work) can optionally resolve one more operator-registered id for a reachability probe. Once core exists, Red should stop trying to resolve a real target's origin itself at all — it should send `target_id` to core and let core resolve it. Keeping `FixedTargetRegistry` around for the standalone scenario (so the existing 139 tests and the demo-reliable fallback keep working) is right; extending it to simulate a *second* real registry is not the direction — that was always meant to be scaffolding, not the final answer.
3. **`LoadProfile`'s ceiling becomes Red's own fallback-only constant.** For requests core dispatches, the enforced ceiling is core's, not this dataclass's. `LoadProfile` stays exactly as it is for the standalone scenario (nothing here asks for it to change), but a core-dispatched `availability.load` call should not be assumed to inherit these specific numbers — Joseph's reply already said as much: *"60 requests / 12 concurrent / 10 seconds... are Red's standalone hard ceilings, not a calibrated bank profile."*
4. **`_execute_start_load`/`_execute_stop_load`'s HTTP-dispatch code becomes dead code for a core-dispatched run.** Red would send the request and wait for core's events, not open the connections itself. This is the biggest deletion-shaped change, and it should only happen once core's dispatch path is real and verified — not speculatively now.
5. **The evaluator split stays, but gains a second, real implementation.** `evaluate_availability`/`evaluate_ordinary_access_during_load` keep working exactly as they do today for the standalone scenario (nothing here deprecates them). A second, core-event-reading equivalent is new code, owned by whoever reads `target.health` and the session history — likely Diego's or a shared referee module, not a rename of Red's existing functions.

## The target-id mismatch Joseph flagged

Per his `gate-status` reply: the bank branch advertises `target_id: bank-lab`; Red's registry only knows
`bank-local`. These are not reconciled, and nothing in this session's work reconciles them — doing so
would mean guessing at core's eventual registry shape, which is explicitly Diego's call. What *is* true
today, independently verified this session: `codex/bank-lab-integration` (`de063b3`) runs and answers
`GET /api/health` with `{"status": "ready", "target_id": "bank-lab", ...}` when reached directly over
HTTP — so the id is real and self-reported by the bank itself, just not registered anywhere Red can
resolve it from.

## What's not in this doc

No ceiling numbers for a real bank, no claim about what core's registry format should look like beyond
"Red sends an id, never a URL," and no change to any file outside `docs/red/`. Those are explicitly
Diego's and Joseph's to set, per the interface review note: *"Reconcile the shared contract and root-plan
changes with Diego/Joseph before adopting them."*
