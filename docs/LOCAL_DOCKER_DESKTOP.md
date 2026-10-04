# Run a separate bank copy with Docker Desktop

This guide runs a second, local bank stack from the prepared source archive. It uses its own containers, database volume, and credentials. It does not connect to or change the Oracle server.

## 1. Start Docker Desktop

Install Docker Desktop for Windows using its WSL 2 backend, start Docker Desktop, and check its requirements. The current WSL 2 requirements include Windows virtualization support and at least 8 GB of system RAM. See [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/).

In PowerShell, confirm the engine is available:

```powershell
docker version
docker compose version
```

## 2. Extract the local copy

Open PowerShell in the `RowdyHacks25` folder. Extract into a new child folder to avoid mixing the lab into the existing project. The archive path below is where it was prepared in Diego's workspace; adjust it if you saved the archive elsewhere. If `bank-lab-local` already exists, choose a different folder name so you preserve it.

```powershell
$bankLab = Join-Path $PWD 'bank-lab-local'
New-Item -ItemType Directory -Path $bankLab
tar.exe -xzf 'C:\Users\diego\OneDrive\Desktop\OneDrive\Documents\ChatGPT\New project\rowdy-bank-lab.tar.gz' -C $bankLab
Copy-Item (Join-Path $bankLab '.env.bank-lab.example') (Join-Path $bankLab '.env.bank-lab')
Set-Location $bankLab
notepad .env.bank-lab
```

Set new, different credentials in `.env.bank-lab`; do not reuse the credentials from the OCI server. Keep this file private and never paste it into chat or commit it.

## 3. Build, initialize, and verify

If your OCI SSH tunnel is still listening on Windows port 3000, press **Ctrl+C** in that PowerShell window first. The local copy uses the same browser port.

In PowerShell, while in `bank-lab-local`, run:

```powershell
docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml up --build -d
docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml ps
docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml run --rm operator node scripts/reset.mjs
docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml run --rm operator node scripts/verify.mjs http://bank:3000
```

The local stack includes a small Nginx proxy. It publishes the browser endpoint on `127.0.0.1:3000`, while the bank and database stay on internal Docker networks. The database has no published port; the bank app has no general outbound Internet route. The local database volume is separate from OCI's.

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). Sign in with the local `customer` or `vault` password you just set. The verification command should print `PASS`.

For this isolated copy, keep availability experiments local and bounded. Requests through the OCI SSH tunnel still reach the Oracle-hosted target. See Oracle's [current security testing policy](https://www.oracle.com/corporate/security-practices/testing/cloud/).

Stop the local containers, preserving their local database volume, with:

```powershell
docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml down
```

## Optional SQL injection training scenario

This opt-in scenario is for the local Docker Desktop copy only. It exposes `GET /api/training/search?term=...` over three synthetic training records. The intentionally unsafe search uses a separate `bank_training` role that can read only `bank.training_records`, and the request runs in a read-only transaction. Login, account ownership, and vault authorization continue to use the baseline code path.

1. In `.env.bank-lab`, add a third unique 64-character hexadecimal password for `BANK_TRAINING_DB_PASSWORD`, and set `BANK_SCENARIO=sqli-training`. Keep all passwords private. Generate a value in PowerShell with `[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLower()`.
2. Recreate the local stack so the bank receives its dedicated training connection setting:

   ```powershell
   docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml up --build -d --force-recreate
   ```

3. Initialize the fixture and role, then verify the normal bank baseline:

   ```powershell
   docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml run --rm operator node scripts/reset.mjs
   docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml run --rm operator node scripts/verify.mjs http://bank:3000
   ```

   Reset rotates the run, clears bank events, restores synthetic data, and invalidates existing sessions. Preserve any needed evidence first.
4. In PowerShell, show a normal search and then the bounded injection demonstration:

   ```powershell
   curl.exe --get --data-urlencode "term=identity" http://127.0.0.1:3000/api/training/search
   curl.exe --get --data-urlencode "term=' OR TRUE --" http://127.0.0.1:3000/api/training/search
   ```

   The first returns one matching training record; the second returns the three fixture records. The endpoint is not an authenticated bank operation and does not expose a credential for the bank, accounts, vault, or event table.
5. To turn the scenario off, set `BANK_SCENARIO=baseline` (or remove the setting), recreate the stack, then reset and verify the baseline. The route returns 404 while disabled. Do not publish this stack on a public interface or use it against a target outside this local lab.

## Live request monitor

Open [http://127.0.0.1:3000/monitor](http://127.0.0.1:3000/monitor) or use the `Live monitor` link in the bank header. The page polls a local in-memory ring buffer and displays API route, method, response status, and latency. It records neither raw packets nor source addresses, query strings, request bodies, cookies, or credentials. Logs are limited to the latest 250 requests and disappear when the bank process restarts. The monitor API excludes its own polling requests.

To see a small, bounded local request stream, keep the monitor open in one tab and run this in PowerShell in another. This makes at most 20 requests, one per second; it is a display exercise, not a denial-of-service test:

```powershell
1..20 | ForEach-Object {
  curl.exe --silent --output NUL --get --data-urlencode "term=identity" http://127.0.0.1:3000/api/training/search
  Start-Sleep -Seconds 1
}
```
