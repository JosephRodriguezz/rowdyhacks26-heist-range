# Blue HTTP-flood defense: integration handoff

Integration update: core now invokes this actual observer in the opt-in disposable bank-library slice. See [the core runbook](../../../../docs/core/AVAILABILITY.md). That fixture uses Next.js's bank libraries with a narrow JS training-source limiter; it does not install this WSGI guard in the deployed bank. All integration outcomes remain fixture-labeled, with no live arrest.

This is a runnable **preparation component for the controlled HTTP-flood lab**, not a claim that Diego's deployed bank is protected. The website exists and the disposable bank-library core connection is verified; the deployed bank is not connected. No Internet-wide or network-layer DDoS protection is provided. Defacement remains deferred.

Joseph requested availability first. The existing access-control `observe(context, tools)` interface and v1 fixtures remain separate and compatible. The original Blue component did not change shared contracts, the website, or the immutable Mayo snapshot. The new disposable connection is documented in the core runbook and integration contracts; deployed-bank activation still needs calibrated approval. The default access-control core continues importing the older snapshot. Only the explicit availability fixture runtime uses this new observer.

## What works now

- Deterministic Monitor correlates request pressure with measured errors, latency, or in-flight work. Healthy spikes do not trigger mitigation. An outage without enough traffic evidence remains unattributed; missing or dropped measurements are inconclusive.
- Defender proposes positive-rate, temporary limits only for observed high-rate opaque source references. It never proposes a blanket bank shutdown, raw rule, shell command, URL, or firewall change. Distributed low-rate pressure can alert without yielding a safe automatic action; Defender then reports blocked.
- `TrafficGuard` actually enforces token buckets at application admission and captures bounded aggregate telemetry. Python banks can use its WSGI middleware; other stacks need an equivalent trusted adapter. There is no outage toggle or scenario-specific low-capacity bottleneck in the guard.
- `ScopedAvailabilityExecutor` re-derives proposals from the guard's latest canonical measurements and a trusted policy before approval and again before installation. It enforces scope, finite deadlines, quotas, cancellation and stop. A newer window requires a fresh comparison; retained older evidence is not rewritten.
- Policies expire automatically, even without another agent response. Trusted rollback is idempotent and remains available after stop, deadline or apply-quota exhaustion. Close/reset invalidates old tokens, windows and handles; instantiate a fresh guard/executor for a new contest.
- Independent recovery checks compare real ordinary-route responses with expected healthy content, verify latency, correlate probes with the attacked guard, and require high-rate source traffic plus actual policy-specific guard refusals in every verification interval. Application-generated 429s and referee traffic do not count. Failed logins, wrong 200 pages, redirects, timeouts, subsided/stopped traffic, changed policies and incomplete measurements cannot authorize the live arrest. Containment is not a verified fix.

No credentials or model APIs are needed for correctness. The detector is deterministic, not an LLM pretending to operate defenses. A future model adviser can suggest a candidate but cannot expand the executor's reviewed policy or certify recovery.

## Run and verify

From the repository root, Python 3.10+ and the standard library only:

```sh
# Entire imported Blue suite and new defense/security/runtime tests
PYTHONPATH=backend python3 -m unittest discover -s backend/tests/blue -v

# Only availability tests, including real loopback HTTP enforcement
PYTHONPATH=backend python3 -m unittest discover -s backend/tests/blue -p 'test_blue_availability*.py' -v

# Deterministic proposal replay, explicitly fixture-only; no traffic or tools
PYTHONPATH=backend python3 -m app.agents.blue.availability_replay

# Legacy incident report with its commit-pinned fixture (not a live report)
PYTHONPATH=backend python3 -m app.agents.blue.report --fixture backend/tests/blue/fixtures/upstream/shared/fixtures/demo-run.json
```

`test_blue_availability_runtime.py` uses a reference WSGI application with a bounded ordinary-work pool. Four loopback workers send at most 350 requests for at most four seconds per test. These real requests produce measured 503 responses under pressure; source limiting restores ordinary 200 responses with correct content while those workers continue. This is **live HTTP execution against a test reference**, not an actual-bank demo or its performance calibration. The same admission rules apply to load and ordinary clients; neither gets a referee/role bypass.

The full legacy suite now has no expected-failure markers: date-only timestamps, non-finite budgets, malformed enums, stale patch retests, and misleading availability/report claims were corrected without changing valid access-control inputs. The ownership patch remains a draft and is not executed here.

## Bank adapter and trusted executor

The bank/application owner constructs one guard for one registered disposable target. Configuration never comes from a model or a public request:

```python
from app.agents.blue import AvailabilityPolicy, observe_availability
from app.agents.blue.availability_guard import TrafficGuard, ScopedAvailabilityExecutor

policy = AvailabilityPolicy(baseline_rps=5.0)  # EXAMPLE: measure the actual bank first
guard = TrafficGuard("contest-1", "registered-bank", "bank-v1", data_source="live")
bank_wsgi_application = guard.middleware(existing_bank_wsgi_application)
executor = ScopedAvailabilityExecutor(guard, policy, max_actions=8, timeout_seconds=120,
                                      cancelled=core_round_is_cancelled)

# Trusted core samples, then invokes Monitor/Defender with aggregates only.
context = guard.sample(policy, seconds=2.0)
observation = await observe_availability(context)
for proposal in observation["defense_proposals"]:
    approved_id = await executor.approve(proposal)
    receipt = executor.apply(approved_id)  # No destination/rule accepted here.
    persist_private_receipt(receipt)        # Core supplies ordering and visibility.
```

The sample and latest stored evidence must agree; evidence is usable for at most ten seconds. Save the raw aggregate window privately with its scope and digest before dispatching Blue. Sampling again invalidates prior approval, even if the new reading is inconclusive; do not silently retry an old proposal.

Trusted `register_client(source_ref)` returns a secret opaque lab cookie token. Bind it privately to the load client and ordinary referee/browser clients without putting it in prompts, judge events, logs or source control. A token is an identity, **not an admission bypass**. The opt-in public-bank middleware requires an issued token: missing/fabricated cookies receive 401 instead of opening an unlimited alternate peer bucket. `source_for()` ignores forwarded-IP/source headers; a salted socket peer is retained only to attribute refused unregistered attempts. Guard itself sets no cookie and offers no registration/policy HTTP endpoint. The trusted bank bootstrap must privately bind ordinary browsers, including the second computer, before they use this isolated-lab interface. Other stack adapters must call the equivalent of `admit(environ)`, not bypass registration with the lower-level `begin()` instrumentation primitive.

Do not trust forwarded headers when adding a reverse proxy. Implement reviewed peer attribution at that integration boundary. NAT, stolen/rotating valid identities, distributed low-rate sources and shared peers can limit attribution; do not claim general bot detection or reliable selective recovery from these tests. Avoid restricting a shared legitimate peer merely to make the demo end successfully.

Before live use, measure normal and bounded-load request rates, latency and error ratios on the **actual** resource-isolated bank; agree a latency threshold with the team, then configure a reviewed policy. Defaults are examples, not capacity findings. Verify the mitigation on that measured failure rather than assuming app-layer limits can solve link saturation.

## Independent referee integration

Trusted core builds a fixed loopback probe registry and private ordinary client. Probe paths, expected content, origin and credentials never come from Blue or Red. Only registered IDs/routes can be resolved; redirects are not followed. Public bank traffic can use an isolated-LAN binding while core/referee probe locally. Keep core controls and recovery off the bank public surface.

```python
from app.agents.blue.availability_verifier import BankTargetRegistry, IndependentRecoveryVerifier

normal_token = guard.register_client("ordinary-referee")
registry = BankTargetRegistry({"registered-bank": {
    "target_version": "bank-v1", "host": "127.0.0.1", "port": bank_public_port,
    "routes": {"ordinary-bank-route": {"path": "/", "expected_body": expected_normal_page_bytes}}
}})
probe = registry.probe("registered-bank", "ordinary-bank-route",
                       private_cookie=f"heist_lab_client={normal_token}")
referee = IndependentRecoveryVerifier(guard, [probe], latency_limit_ms=500,
                                     cancelled=core_round_is_cancelled)
baseline = referee.baseline()       # Actual healthy access before load/mitigation.
# ... bounded lab traffic, measured degradation, Blue proposal, approved action ...
verdict = referee.verify()          # Keep bounded load running during these checks.
# Only live verdict['arrest_permitted'] may drive Omar's verified arrest event.
```

Configure up to four representative ordinary routes, including required authenticated access; combine the private lab cookie with privately supplied test-account cookies if needed. Do not substitute a trivial `/health` endpoint for usable bank access. The supplied comparator checks exact bounded content, suitable for stable reference pages; a dynamic bank needs a reviewed, target-specific content assertion adapter. A five-minute baseline lifetime and five samples are bounded defaults, not an agreed production SLO.

The referee emits `passed` only for its tested routes/identities and the observed bounded profile. Every limited load source must remain above both its reviewed suspicion threshold and applied rate, with a matching guard refusal in each interval; ordinary referee identities are excluded. It does not erase earlier disclosures, judge vault-access success, certify an ownership fix, or set the existing incident report to resolved. Fixture/recorded evidence cannot permit a **live** arrest. A labeled replay may tell the recorded story separately.

## Opt-in payloads and presentation

`range.blue.availability/v1` context has only `assessment_id`, `target_id`, `target_version`, `data_source`, `window`, `policy`, optional `budgets`, and optional `active_source_refs`. Unknown keys fail closed. The window has one bounded source list (<=256), reconciled integer counts, duration, p95 latency or null, and an explicit `data_loss` flag. Request content, URL/query, headers, IP addresses, cookies, Red plans and seeded ground truth are absent.

Output contains assessment, alerts, scoped proposals, evidence references, and fixed Monitor/Defender summaries. Blue always returns `recovery_verified: false` and `fix_status: not_assessed`. `limit_http_source` is a new **opt-in** action, not an added v1 enum. Core adapters return `range.availability.action/v1` receipts; referee returns `range.availability.recovery/v1`. These producer payloads are **not** the existing globally ordered event envelope. Integration owner must validate, persist, assign sequence/visibility and project them into the arena's reviewed contract.

Judge-safe feed: phase, data-source label, measured request/error/latency counts, fixed agent summaries, containment status, and safe evidence references. Keep canonical evidence and private policy details in core storage. Feed must not expose cookie tokens, raw requests, attacker private work, target source, or referee-only inputs. UI labels should say “suspected HTTP flood,” “temporary source limit applied,” and “normal bank access verified under continuing bounded load,” not “DDoS defeated” or “flaw fixed.” If checks fail, remain inconclusive and offer the separately labeled replay.

## Operational acceptance before the demo

1. Connect this adapter to the actual bank stack and resource isolation; configure HTTP server worker/connection/body-size/time limits. WSGI admission protects application work **after** a server accepts a connection; it cannot bound kernel backlog, threads already created by the server, network bandwidth, TLS, or database resources.
2. Calibrate strict load duration/request/concurrency ceilings on that bank and a separate healthy ordinary-user baseline. Red's load executor must enforce the fixed registry, origin, cancellation and budget; this Blue slice provides no general attack generator.
3. Core integrates receipts, independent referee checks, ordered persistence, judge-safe visibility and pause/stop/reset. Pause blocks new dispatch; stop cancels the round and invokes trusted cleanup; reset waits for work to end and closes the old guard. Do not expose policy methods on a public bank route. Existing core controls are not wired to this slice yet.
4. Test real ordinary access during mitigation, policy expiry/rollback, canceled/stale/reset replies and a second isolated-LAN browser showing the same bank. Arena arrest must wait for the live independent verdict. Keep an explicitly labeled replay for presentation failure.
5. Obtain human review of this new interface and policy, especially target attribution and dynamic-page assertions. No branch merge or deployment is implied by tests here. The supplied replay shows fixture-only Blue proposals; a complete recorded recovery/arena fallback is not implemented by this slice.

## Provenance

Imported Blue-owned runtime, tests and draft defense manifest from Mayo revision `b3e719d23466173f2d044a4e5ae83ccb45c6f329`. Shared v1 contract/demo examples were copied **only** into Blue-owned upstream test fixtures, not over this branch's shared contracts. New availability modules, replay fixture, runtime/adversarial tests, and the legacy robustness/report fixes are local changes. No external packages were introduced.
