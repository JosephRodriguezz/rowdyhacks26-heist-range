# Rowdy Bank browser demo

This runnable local demo shows the availability slice without Omar's arena. The presenter can start, pause, resume, stop, repeat, inspect history, and export a sanitized report. Real HTTP requests reach an owned disposable bank engine; the actual Blue detector proposes a temporary limit, and the independent referee verifies recovery while ordinary account requests continue.

The page labels every run **fixture**. Red's start/stop decisions are scripted. The bank uses its account/capacity libraries with embedded PostgreSQL, not the separately deployed Next.js/PostgreSQL website. This demonstrates training-pool pressure and recovery, not network saturation, an adaptive Red model, or production DDoS protection. No existing bank, environment file, Tailscale address, or arbitrary destination is read or used.

## Start on Windows

From this checkout, install the locked dependencies once with Node.js 24 and pnpm 11.19.0:

```powershell
cd apps/bank-lab
pnpm install --frozen-lockfile --ignore-scripts
cd ../..
./scripts/Start-Demo.ps1
```

The launcher finds Python 3.11+ and Node on PATH, with a fallback to the installed Codex dependency runtime on this computer. It opens the authenticated demo at `http://127.0.0.1:8765/demo`. Keep the terminal running. `-CheckOnly` verifies prerequisites without starting a service; `-Port 8767` selects another unused local port if necessary. The existing bank's port 3000 is not used.

On any system with Python and Node on PATH, the equivalent command is:

```sh
python -m core.cli demo
```

Core generates a fresh presenter credential in memory and passes it to the browser through a URL fragment, which never reaches the HTTP server. The page immediately removes the fragment and retains the credential in tab-scoped `sessionStorage` for that exact origin, including its port. Requests attach it explicitly as a bearer header; no presenter cookie is issued, because cookies would also reach other localhost ports. The CLI never prints it. Do not share the launch URL or browser profile. Restarting core generates a new credential unless the operator privately sets `HEIST_CORE_TOKEN`. For a browser that must be opened manually, set that variable to a private 32–128 character URL-safe value, run `python -m core.cli demo --no-browser`, and enter it in the password field. The presenter API remains bound to literal loopback.

## Present the run

1. Click **Start demo**. Allow a few seconds for embedded PostgreSQL to initialize. The target is created only for this assessment.
2. Point out the healthy baseline, measured degraded training capacity, and Blue's applied source limit in the timeline. HTTP 429 responses specifically attributed to the rate policy are distinguished from other refusals.
3. Wait for **Recovery verified**. That label requires both the terminal core verdict and the terminal referee event. An applied limit, a successful health request, or the end of traffic is insufficient.
4. Use **Export safe report** to save the selected assessment and its judge-visible events. If an embedded browser blocks the download, expand **Safe report prepared — view JSON** and copy the report. Raw account contents, capability tokens, Blue-private windows, and referee-only records never enter the browser report.
5. Click **New run**, then **Start demo** to repeat. Each target is fresh; prior evidence remains in history. A stopped or ambiguous run stays **Inconclusive**.

The load is capped at 60 attempts, six aggregate concurrent HTTP calls, and a four-second dispatch deadline. Referee/executor reservations, probe/control ceilings, child lifetime, and policy expiry remain enforced outside the UI; see [the availability runbook](AVAILABILITY.md). The short measured incident is retained in the timeline so it can be discussed after completion. No animation delays the backend or fabricates traffic. Pause preserves the original deadline, so pausing too long can make a run inconclusive.

**Stop** cancels the assessment and tears down its target. **Ctrl+C** in the launcher also stops core and active work. Evidence remains in `.core-state/demo.sqlite3`; do not publish that private database. If the process is interrupted, the next launch marks unfinished runs failed rather than resuming them. The exported JSON is the sharing surface.

## Optional Docker package

`compose.demo.yaml` packages this same fixture demo separately from `compose.bank-lab.yaml`. It does not add or replace the full Next.js bank. Docker was unavailable in the implementation workspace, so this package has not been built or runtime-verified here; the native launcher above is the verified path.

From the repository root in PowerShell, generate a private token without printing it:

```powershell
$demoBytes = New-Object byte[] 32
$demoRng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$demoRng.GetBytes($demoBytes)
$demoRng.Dispose()
$env:HEIST_CORE_TOKEN = -join ($demoBytes | ForEach-Object { $_.ToString('x2') })
docker compose -f compose.demo.yaml up --build -d
Start-Process ("http://127.0.0.1:8765/demo#presenter=" + $env:HEIST_CORE_TOKEN) -WindowStyle Hidden
```

Wait until the containers are ready before using the page. The Docker package publishes only `127.0.0.1:8765`, uses an internal network, and stores core evidence in its own named volume. Its Nginx presenter shares the core network namespace and forwards to the loopback-only core listener; the original Host and Origin checks remain active. Do not open a firewall port or replace the bind with a public address. Stop with `docker compose -f compose.demo.yaml down` in the same shell; omitting `-v` preserves evidence. Keep the token in that shell for subsequent Compose commands, or configure it through a private ignored environment file. Never commit it.

## Omar's later connection

The UI is a replaceable consumer of the existing authenticated `/api/assessments`, `/actions`, `/events`, and `/stream` contract. The additive judge events are `availability.probe.observed` and `availability.request.observed`; they contain only fixed HTTP status, latency, occupancy, policy-refusal, and error fields. They have no private evidence references, exercise handles, credentials, or account data. Sequence gaps reflect omitted private events. Cursor consumers must use `last_event_id` and preserve `data_source=fixture`.

Omar can replace the presentation while retaining the core's state, controls, visibility filtering, and terminal referee decision. The UI must not infer arrest, vault access, permanent remediation, or recovery from an intermediate event. Connecting the deployed bank still requires its separate registered bootstrap, isolated scope, healthy calibration, and approved limits.

## Verification

```sh
python -m unittest discover -s tests -p 'test_core*.py' -v
node --check core/web/demo.js
git diff --check
```

The core suite includes repeated HTTP demo runs, bearer/origin boundaries, rejection of cookie authentication, default API compatibility, fixture labeling on reset, private evidence denial, request ceilings, cancellation, and negative recovery cases. Browser checks exercise authenticated start, verified completion, fresh run, stop, reload, history, and report export. Docker validation is a separate remaining check.
