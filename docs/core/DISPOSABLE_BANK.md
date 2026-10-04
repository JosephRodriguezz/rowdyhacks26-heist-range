# Disposable full-bank availability rehearsal

This path runs the actual Next.js bank, PostgreSQL, and Nginx in a second Docker
Compose project. It is separate from the existing `rowdy-bank-lab` project:
`rowdy-bank-disposable` has its own database volume and publishes only
`127.0.0.1:3001`. The fixed adapter registry maps `disposable-desktop` to that
origin and requires the canonical `bank-lab` target, an exact run ID, a measured
approval, and private credentials. The existing port-3000 bank is not a target.

It is an application-capacity exercise, not a network-packet DDoS test. One
bank process admits at most 30 fixed-cost training jobs for at most 4.5 seconds,
with at most four active jobs. The adapter dispatches for at most four seconds,
at most 30 attempts and four load workers, with at least 100 ms between each
worker's attempts. Blue sees sanitized target aggregates; the independent
referee requires measured degradation, a narrow applied limit, continuing load,
ordinary authorized access, and recovery. Timeout or missing evidence is
inconclusive.

From a clean checkout on a computer with Docker Desktop, Node.js 24, and
Python 3.11+, use PowerShell at the repository root:

```powershell
.\scripts\New-DisposableBankEnv.ps1
docker compose --env-file .env.bank-disposable -f compose.bank-disposable.yaml config --quiet
docker compose --env-file .env.bank-disposable -f compose.bank-disposable.yaml up --build -d db bank proxy
docker compose --env-file .env.bank-disposable -f compose.bank-disposable.yaml run --rm operator node scripts/reset.mjs
docker compose --env-file .env.bank-disposable -f compose.bank-disposable.yaml run --rm operator node scripts/verify.mjs http://bank:3000
node scripts/calibrate-disposable.mjs
node scripts/prepare-disposable-availability.mjs
```

Review `artifacts/disposable-baseline.json` and
`artifacts/disposable-approval.json` before any load. They contain safe IDs,
latencies, and explicit limits. The latter is staged only; neither script
dispatches training work. The six-request calibration must show healthy
readiness and authorized accounts with responses below 200 ms. If it fails,
leave availability disabled and investigate the bank.

Once the exact isolated run and limits are approved, enable only its bank
container, then run one rehearsal:

```powershell
docker compose --env-file .env.bank-disposable -f compose.bank-disposable.yaml up -d --no-deps --force-recreate bank
$env:HEIST_PYTHON = (Get-Command python).Source
node scripts/run-disposable-availability.mjs
```

Replay the retained referee evidence without contacting the bank:

```powershell
node scripts/verify-disposable-evidence.mjs disposable-<assessment-id-from-report>
```

Open [the bank](http://127.0.0.1:3001) and
[its sanitized request monitor](http://127.0.0.1:3001/monitor) on this computer.
The runner writes a create-only report under `artifacts/` and a durable,
sanitized JSONL journal under `artifacts/disposable-evidence/`; neither is in
Git. It also marks the approval used before dispatch. A failed attempt cannot
silently refill its budget. A new attempt needs a fresh exercise and explicit
approval, not removal of that marker. Preserve the journal before any reset.

To stop only the disposable project, run:

```powershell
docker compose --env-file .env.bank-disposable -f compose.bank-disposable.yaml down
```

This keeps its database volume for inspection. The original bank project and
its volume are untouched. The browser presenter in `docs/core/DEMO.md` still
uses the separately labeled bank-library fixture; this full-bank runner is a
backend rehearsal and does not claim that the browser presenter is wired to
the Docker bank. The outcome is evidence for this one synthetic capacity
scenario, not proof of public Internet resilience or vault access.
