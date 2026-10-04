# Connected disposable availability slice

For the runnable browser presentation without Omar's arena, use `python -m core.cli demo` and follow [the demo walkthrough](DEMO.md). It uses the exact disposable slice described here and does not activate the deployed bank.
Core now runs the bank's actual account and capacity libraries with the actual Blue availability detector against an owned HTTP/PGlite fixture. It proves the backend seam before deployed-bank calibration: healthy ordinary access, bounded Red load, measured training occupancy, evidence-backed temporary limiting, independent recovery under continuing load, and teardown.

All records and decisions are labeled `fixture`. Red start/stop decisions are scripted typed proposals, not an adaptive Red model run. The target is an ephemeral loopback server created by core's child process, never the running website on port 3000. This is a training capacity exercise; it does not measure whole-bank overload, packets, network saturation, or general DDoS protection. The UI/arena and live arrest remain downstream.

## Sources and commands

This branch combines published core `codex/core-orchestrator` at `99bc29c` and bank `codex/bank-availability-interface` at `21b4f81`. Aaron's separate availability source remains `red/availability-ddos` at `09b3bc4`; its standalone runner is not imported or modified. The action seam uses Red's existing `ActionProposal` with explicit `target_id=availability-fixture`. The unchanged `integrations/mayo/` snapshot stays byte-identical to its provenance manifest. The default vault runtime still uses that older Blue access-control observer.

Install the bank's locked test dependencies, then return to the repository root:

```sh
cd apps/bank-lab
pnpm install --frozen-lockfile --ignore-scripts
cd ../..
python3 -m core.cli availability
python3 -m core.cli availability --db .core-state/availability.sqlite3
python3 -m unittest discover -s tests -p 'test_core_availability.py' -v
```

Node must be on PATH. Alternatively supply the trusted local executable through `--node /absolute/path/to/node`; for tests set `HEIST_TEST_NODE` to that executable. Python uses only its standard library. No `.env.bank-lab`, real credentials, Docker services, model API, or bank destination is read. CLI returns nonzero for incomplete/inconclusive recovery.

The existing authenticated loopback presenter API can opt in with `python3 -m core.cli serve --availability-fixture`, after privately setting `HEIST_CORE_TOKEN` as in [the core runbook](README.md). Create an assessment with `target_id=availability-fixture` and `planner_mode=fixture`, then use the existing start/pause/resume/stop/reset controls. Omitting the flag keeps the target unregistered. The deployed `bank-lab`, arbitrary origins, and model mode are rejected for this slice. No service is started automatically by checkout or import.

## Execution and evidence

`CoreService` registers the fixture explicitly and constructs `AvailabilityRuntime`. Its private bounded stdin/stdout bridge owns a fresh synthetic bank, ordinary session, three capability tokens, and fixed registry. Red proposes only `start_load_test` or `stop_load_test`; core rejects route, identity, payload, profile, and destination overrides before dispatch. There is no arbitrary URL control. These capabilities map to the existing bank adapter; Aaron can use the same typed seam when his planner is connected.

Target-side status contains a reconciled, bounded aggregate window for the one registered load client: requests, admissions, refusals, measured in-flight work, latency, and explicit measurement loss. It contains no IP, cookie, request contents, or Red plan. Core retains the canonical window privately, invokes `observe_availability`, and re-derives the exact proposal before approval. A stale window, wrong scope/digest/source, or rate/burst/TTL mismatch is rejected. The bridge applies only the approved fixed source limit against the same pinned exercise. This adapter does not use Python's WSGI middleware to protect Next.js.

The fixture policy is explicit: baseline example 1 request/s, suspicion threshold 4 requests/s, in-flight threshold 2, and a 1 request/s bucket with burst 1 and 3-second TTL. The bucket starts empty and refills; ordinary banking remains outside this synthetic work pool. These are fixture settings, not calibration findings or approved live-bank limits.

| Bound | Fixture ceiling |
|---|---|
| Load requests, including refused attempts | 60 |
| Aggregate concurrent HTTP | 6, including two reserved observer/executor slots |
| Load dispatch deadline | 4 seconds |
| Request timeout | 500 ms |
| Pacing per worker | At least 100 ms between completed attempts |
| Observation/control calls | 30 / 4, with reserved remote stop |
| Ordinary/readiness latency | At most 400 ms; fixture assertion only |
| Recovery samples | 3, separated by continuing load |
| Core round / child lifetime | 15 / 20 seconds |
| Bridge input/output message | 16 KiB / 128 KiB |

Pause reaches the Node admission hook before its receipt, drains bounded in-flight HTTP, and prevents new background load dispatch. Resume keeps the original deadline. Stop aborts pending HTTP and invokes the reserved target stop; child EOF or process failure destroys the owned target. Reset requires completed teardown, creates a new assessment, and retains old evidence. Policy expiry and restoration cannot be mistaken for a verified defense. Stop and terminal verdict publication linearize through the same core gate.

The independent evaluator reads the trusted adapter journal, not Red/Blue conclusions. It requires a fresh healthy baseline, observed occupancy degradation, scoped mitigation receipt, correct owner-authorized accounts and latency, continuing validated work bracketing the probes, and healthy status after stop. Each verification interval must also show increasing target policy-refusal counters above the reviewed suspicion rate, under the same active policy revision and exact positive parameters. Generic capacity 429s, missing work, expired/replaced policies, failed ordinary access, ambiguous transport, or changed exercises stay inconclusive.

Core assigns canonical SQLite order and visibility. Raw adapter records and referee results are `referee_only`; aggregate windows, proposals and the Blue board are `blue_private`. Presenter events are separately constructed `judge_safe` records with fixture labels, counts, containment state and fixed summaries. Private evidence IDs cannot be read through presenter HTTP. Every fixture verdict has `arrest_permitted=false` and `fix_status=not_assessed`.

## Remaining team handoffs

Validation on 2026-10-04: 185 core/Red tests (including 10 availability checks), 353 Blue tests, 105 unchanged Mayo tests, and 48 bank tests passed. The production Next.js/TypeScript build, Python compilation and toolkit validation passed. Two persisted core fixture repetitions achieved recovery; denied ordinary access, removed policy, early expiry, bridge failure, cancellation at the referee, and cleanup failure remained inconclusive. Test portability fixes preserve snapshot bytes, accept either safe path-denial stage on Windows, and distinguish POSIX permissions from NTFS ACLs. The separate WSGI reference fixture now synchronizes its bounded load burst and uses burst 1; Blue algorithms and referee assertions are unchanged.

Diego supplies the deployed bank's exact fixed registration, isolated runtime, approved calibration procedure and measured profile. Aaron supplies the planner dispatch call using these typed capabilities and target ID; the bank's deployed registration is `bank-lab`, while `bank-local` remains the separate vault fixture and is never silently aliased. Joseph supplies a reviewed bank policy based on actual measurements and retains Blue's evidence/proposal boundary. Core supplies persistent routing and independent assessment; Omar can consume the sanitized event stream after agreeing its presentation mapping.

The current runtime intentionally has no live-bank switch. A future trusted deployment bootstrap must inject the registered bank adapter and private credentials after separate approval, then prove the same bounded slice on that exact stack. Test success approves neither public deployment nor traffic to the existing bank/Tailscale website.
