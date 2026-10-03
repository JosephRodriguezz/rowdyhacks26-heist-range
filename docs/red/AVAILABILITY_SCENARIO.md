# Standalone availability (load/recovery) scenario

**Status:** Implemented on the `red/availability-ddos` branch, off `codex/red-team-design`. Not reviewed or
merged by Joseph. **Scope:** extends the standalone Red prototype only; it does not touch Diego's
core/bank, Aaron's Blue agents, or Omar's arena. **Owner review needed before this becomes part of the
event build.**

## Why this exists

`blue-team/proposals/red-availability-subtasks.md` (on the `Mayo` branch, not this one — written earlier
from a review of this branch) gated an availability/outage scenario behind Gate 6, a team go/no-go
decision (AV-01), and Diego's contract work (AV-02–AV-04). The team has since decided to build this now,
ahead of that sequence, and to drop the Blue-side wiring (AV-08) for the moment. This document records
what exists so Joseph (and whoever picks this back up) can review it against that original plan rather
than discover it cold.

## What it does

A seventh, independent scenario: `availability`. Unlike the six vault-access families, it is never mixed
into `active_flaws`/`FAMILIES` — an outage must never be countable as vault access, and this code keeps
that true structurally, not just by convention:

- `evaluate_availability()` is a separate function in `red/evaluation/evaluator.py`, scored only from the
  lab's own `status_log` (never from Red's self-reported claims).
- `RunReport.availability` is populated on **every** run, vault scenarios included (always
  `not_achieved` there, since no load test runs), and never substitutes for the vault verdict.

### The action

Two new typed capabilities, `start_load_test` and `stop_load_test`. Neither accepts any parameter beyond
the registered target — a model can ask to start or stop *the one registered profile*, never choose its
size. The profile itself (`LoadProfile` in `red/prototype/domain.py`) is a frozen, hard-ceiling-checked
dataclass (≤60 requests, ≤12 concurrent, ≤10s, ≤5s per-request timeout by construction) configured by the
runner/CLI, never by a proposal.

`start_load_test` spawns one bounded, labeled burst against the registered loopback target's `/api/status`
route in a background thread and returns immediately with a `load_started` event. `stop_load_test` cancels
it and joins with a bounded timeout. If nobody calls stop, the burst still ends on its own at the hard
request/duration ceiling — cancellation and the run's own `executor.close()` also stop it promptly.

### The target effect

`/api/status` now reflects real capacity: a per-request processing delay lets concurrent requests build up,
and past `degraded_threshold` (default 4) it returns `503 degraded` instead of `200 available`. This is a
real, bounded, in-process effect confined to the disposable loopback lab — nothing leaves 127.0.0.1, and no
request count can exceed the hard ceiling above.

### The defended counterpart

`disable_family("availability")` (or the simulated-defense harness, or scenario `"all"`) turns on a
request-rate limiter (`rate_limit_per_second`, default 3 — kept below `degraded_threshold` **by
construction**, so the limiter always sheds load before concurrency can reach the point that degrades the
service, regardless of how large a later burst gets). Shed requests get an immediate `429`; ordinary
single-request traffic is unaffected either way.

### The demo arc

Because the load is bounded and self-terminating, "Normal → Degraded → Recovered" falls out naturally from
one `start_load_test` → (observe `503`s) → `stop_load_test` → (observe `200` again) sequence, with no Blue
agent required to produce the recovery. `python -m red.prototype.cli run --scenario availability --mode
deterministic_baseline` runs this whole arc without a live model call, for a demo-reliable path — mirroring
why the vault scenarios ship a deterministic baseline instead of depending on an unverified remote model.

## What this does not do (read before claiming it in the demo)

- **No real network traffic leaves the lab.** This is a bounded, in-process capacity simulation — not a
  volumetric/network-layer DDoS, and it cannot become one: the registry only resolves to the fixed loopback
  target, there is no proxy or shell access, and every bound above is a hard ceiling in code.
- **Not wired to Blue, core, or the arena.** AV-02 (wire contract), AV-03/04 (Diego's bank health +
  guardrails), AV-07 (judge view), and AV-08 (Blue telemetry) from the original proposal are all still
  outstanding. This only runs against the prototype's own disposable `LabState`/`LocalBankServer`, same
  limitation the rest of the Red prototype already has.
- **No live-model run has been made.** `start_load_test`/`stop_load_test` were added to the model-mode tool
  schema (`providers.py`) but the system prompt (`agents.py`) was not rewritten to mention them or to frame
  an availability mission — a live model run today would not reliably choose these actions. The
  deterministic baseline is the only verified path.
- **The one pre-existing test failure on this branch** (`test_virtual_traversal_cannot_read_a_real_host_file`,
  expects 404 and gets 400) predates this work and is unrelated to it; it looks like a Windows path-handling
  difference, not confirmed to be the actual cause yet.

## Verification run

```sh
python3 -m compileall -q red
python3 -m unittest discover -s tests -v                     # 108 tests, the one pre-existing failure above
python3 -m red.prototype.cli run --scenario availability --mode deterministic_baseline
python3 -m red.prototype.cli run --scenario availability --mode deterministic_baseline \
  --simulated-defense availability --defense-after-actions 0
```

The first `run` reports `"availability": {"verdict": "achieved", ...}`; the defended one reports
`"not_achieved"`. Both were re-run multiple times in this session with no flake observed.

## Suggested next steps, in the original proposal's terms

- AV-01 (go/no-go) and AV-05 (point Red at Diego's bank instead of its own loopback lab) are still real
  gaps if this is meant to run against the integrated contest rather than the standalone prototype.
  AV-05 now has a prototype-only origin switch: a caller-started `LocalBankServer` in the same process
  can be selected by origin, with real loopback HTTP and its actual evaluation state. This does not
  implement Diego's bank protocol or cross-process integration; see [integration readiness](INTEGRATION_READINESS.md).
- AV-07 (judge view) has a natural hook: poll `/api/status` or watch for `availability.load_started` /
  `availability.load_completed` / `availability.load_stopped` board events.
- AV-08 (Blue wiring) is out of scope for now per the team's current direction; the deterministic recovery
  above stands in for it in the demo.
