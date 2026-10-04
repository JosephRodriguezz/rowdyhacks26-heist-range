# Bank lab on an Oracle Ubuntu server

This walkthrough starts the bank website as a private preparation prototype. It provides the bank/API, synthetic accounts, protected vault, health check, and operator reset. It does not yet provide the core, Red/Blue agents, event routing, referee, or judge arena described in [Diego's role packet](roles/DIEGO_CORE_LAB.md).

The first milestone is a working baseline that you can start, verify, stop, and reset reproducibly. The controlled vulnerability variants are the next milestone.

The bank uses Next.js/TypeScript and PostgreSQL with Docker Compose. The database and bank app stay on separate internal networks. A small Nginx proxy joins the app network and a host-access network, and publishes only `127.0.0.1:3000`; it cannot reach the database. The app itself has no external network route. Your Windows browser reaches the proxy through SSH, without public ingress rules for ports 3000 or 5432.

## 1. Check the Ubuntu server

Your server reports **Ubuntu 24.04.4 LTS (`noble`), `x86_64`**, and Docker is not installed. This is a supported combination for Docker's Ubuntu installation. [Docker's supported Ubuntu versions and architectures](https://docs.docker.com/engine/install/ubuntu/)

Check memory and available disk space in your existing Ubuntu SSH terminal before building:

```bash
free -h
df -h /
```

Build time and memory use depend on the instance's resources. Continue with the Docker installation below for this server.

## 2. Install Docker and Compose

In the Ubuntu SSH terminal, run:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -d -m 0755 /etc/apt/keyrings
sudo curl -fLsS https://download.docker.com/linux/ubuntu/gpg --output /etc/apt/keyrings/docker.asc
sudo chmod 0644 /etc/apt/keyrings/docker.asc
. /etc/os-release
bank_docker_arch=$(dpkg --print-architecture)
bank_docker_suite=${UBUNTU_CODENAME:-$VERSION_CODENAME}
printf '%s\n' \
  'Types: deb' \
  'URIs: https://download.docker.com/linux/ubuntu' \
  "Suites: $bank_docker_suite" \
  'Components: stable' \
  "Architectures: $bank_docker_arch" \
  'Signed-By: /etc/apt/keyrings/docker.asc' \
  | sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl start docker
sudo docker version
sudo docker compose version
```

This uses Docker's official package repository. If the server already has a different Docker/container runtime installation, inspect that installation before replacing packages; the official guide lists conflicts. These commands retain `sudo` for Docker administration. [Official installation procedure](https://docs.docker.com/engine/install/ubuntu/)

## 3. Transfer the prepared project

The website files prepared in this chat are local changes. Cloning the repository's current GitHub `main` alone will not include them until the team publishes those changes. Transfer the supplied archive to start this prototype without changing the remote repository.

In a **Windows PowerShell window**, from the directory containing `rowdy-bank-lab.tar.gz`, run:

```powershell
scp .\rowdy-bank-lab.tar.gz ubuntu@129.158.213.76:~/
```

If your working SSH command specifies a private key, use the same key with `scp`:

```powershell
scp -i "C:\path\to\your-private-key.key" .\rowdy-bank-lab.tar.gz ubuntu@129.158.213.76:~/
```

Use the instance's current public IP if it has changed. Oracle Ubuntu images use the `ubuntu` account. [Oracle SSH connection instructions](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/connect-to-linux-instance.htm)

Back in the **Ubuntu SSH terminal**, unpack the archive into a new project directory:

```bash
mkdir -p ~/rowdyhacks26-heist-range
tar -xzf ~/rowdy-bank-lab.tar.gz -C ~/rowdyhacks26-heist-range
cd ~/rowdyhacks26-heist-range
ls compose.bank-lab.yaml apps/bank-lab/package.json
```

If that directory already contains work you need to preserve, use a different new directory for this archive. The archive has project files at its root and excludes runtime secrets, dependencies, build output, and Git internals.

## 4. Set private local credentials

From the project root on Ubuntu:

```bash
umask 077
cp .env.bank-lab.example .env.bank-lab
chmod 600 .env.bank-lab
nano .env.bank-lab
```

Replace the example placeholders with values you choose locally:

| Setting | Purpose |
|---|---|
| `BANK_DB_PASSWORD` | Administrator database password; random hexadecimal, at least 32 characters |
| `BANK_APP_DB_PASSWORD` | A different random hexadecimal value, at least 32 characters, for the restricted app database role |
| `BANK_CUSTOMER_PASSWORD` | Password of 16–256 characters for synthetic user `customer` |
| `BANK_VAULT_PASSWORD` | A different password of 16–256 characters for synthetic user `vault` |

Generate the two database passwords independently using a password manager or `openssl rand -hex 32` locally; that command creates a 64-character hexadecimal value. Do not send their output to chat. Replace every `replace_with_...` placeholder: reset rejects placeholder values, duplicate database passwords, and duplicate demo passwords.

Compose constructs the connection strings from these four settings. You do not need to add `DATABASE_URL` or `DATABASE_ADMIN_URL` to the environment file. Inside Compose, the database is `bank_lab` at `db:5432`; the administrator username is `lab_admin` and the restricted app username is `bank_app`.

Use long random alphanumeric account passwords, or single-quote their values in the environment file so Compose treats special characters such as `$` literally. Every project Compose command below supplies `--env-file .env.bank-lab` explicitly. [Compose environment-file syntax](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)

Save in nano with **Ctrl+O**, Enter, then **Ctrl+X**. Keep `.env.bank-lab` only on your machine/server; do not paste it into chat or commit it. The running web service receives only its restricted database credentials. The operator service receives the administrator credentials and seed passwords when you run reset or verification.

## 5. Build, start, and initialize the bank

Run from the project root on Ubuntu:

```bash
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml up --build -d
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml ps
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml run --rm operator node scripts/reset.mjs
curl --fail --silent --show-error http://127.0.0.1:3000/api/health
```

The first command builds the app and starts PostgreSQL. The reset command initializes or restores the synthetic bank state and rotates its run ID. It clears existing sessions and demo events, so use it between runs after stopping actions against the bank. Resetting the bank is an operator action; there is no public HTTP reset route.

The `operator` service is a one-off tool and does not run with the website. Calling it explicitly with `run --rm operator` activates it for that command, then removes its container. [Compose service profiles](https://docs.docker.com/compose/how-tos/profiles/)

A passing health check returns HTTP 200 with `status: "ready"`, `target_id: "bank-lab"`, a UUID `run_id`, and `scenario_version: "baseline-v1"`. Before initialization, or if PostgreSQL cannot be reached, it returns HTTP 503 with `status: "unavailable"`. Once initialized, the bank is ready for the browser checks below.

## 6. Open the website on Windows

Keep the Ubuntu SSH terminal available. In a **second Windows PowerShell window**, run:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:3000:127.0.0.1:3000 ubuntu@129.158.213.76
```

Or, if your SSH connection needs an explicit key:

```powershell
ssh -i "C:\path\to\your-private-key.key" -N -o ExitOnForwardFailure=yes -L 127.0.0.1:3000:127.0.0.1:3000 ubuntu@129.158.213.76
```

Leave that window running. A successful tunnel normally stays quiet. Open [http://127.0.0.1:3000](http://127.0.0.1:3000) in your Windows browser. The first `127.0.0.1:3000` in the command is your Windows listening address; the second is the website address reached from Ubuntu. `-N` keeps the connection for forwarding without opening another shell. [OpenSSH forwarding options](https://man.openbsd.org/ssh)

Close the tunnel with **Ctrl+C** when finished. If Windows port 3000 is already in use, edit `compose.bank-lab.yaml` on Ubuntu. Add `http://127.0.0.1:3001` to the bank service's `BANK_ALLOWED_ORIGINS` list and change the proxy's published mapping to `127.0.0.1:3001:8080`. Apply both changes with:

```bash
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml up -d bank proxy
```

Then use `-L 127.0.0.1:3001:127.0.0.1:3000` in the Windows SSH command and browse to `http://127.0.0.1:3001`. The server-side port stays 3000. The explicit origin list is required for login/logout requests, including tools calling the API.

## 7. Verify the authorized baseline

The first milestone establishes normal behavior before adding the three controlled vulnerability families. There are no deliberate vulnerabilities in this baseline. Sign in with synthetic username `customer` or `vault` and the corresponding password saved in your private environment file.

Run the automated baseline verification from Ubuntu:

```bash
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml run --rm operator node scripts/verify.mjs http://bank:3000
```

The verification process uses the private operator service on the lab network. A passing run must complete successfully; inspect its reported failed checks if it exits with an error. Its baseline checks supplement the browser walkthrough below.

| Check | Passing behavior |
|---|---|
| Open the website while signed out | Login surface renders |
| Sign in as the customer | Customer's account is available |
| Customer requests the protected vault | Access is denied |
| Sign out | Previously authenticated browser access is no longer accepted |
| Sign in as the vault-authorized user | Synthetic vault data is available |
| Reset the bank while signed in | The old session no longer authorizes requests |
| Sign in again after reset | Authorized account access still works |

Check signed-out vault rejection directly from Ubuntu without printing protected content:

```bash
curl --silent --output /dev/null --write-out '%{http_code}\n' http://127.0.0.1:3000/api/vault
```

Expected: HTTP 401. A timeout or failed connection does not prove unauthorized access was blocked; first establish that health passes.

These checks verify the bank baseline. They do not prove live Red/Blue activity, a successful exploit, or an independent referee result.

Before packaging, all 10 local source tests passed with embedded PostgreSQL, the production Next.js build passed (including TypeScript), and HTTP checks confirmed the page renders, unavailable health returns 503, operator routes are absent, and invalid origins/oversized JSON are rejected. Docker is unavailable in the local Windows workspace, so the actual Linux image and PostgreSQL 17 deployment remain unverified until you run the commands above.

The repository toolkit inventory also passed. Its separate validation command reports a pre-existing helper checksum mismatch caused by Windows CRLF line endings: the helper matches Git HEAD and the recorded hash after LF normalization. This is unrelated to the bank runtime; no toolkit source was changed.

## 8. Operate and troubleshoot it

Run these from the project root on Ubuntu:

```bash
# View service state.
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml ps

# Inspect recent app and database diagnostics.
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml logs --tail=80 bank db

# Restore the bank to its synthetic baseline between runs.
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml run --rm operator node scripts/reset.mjs

# Stop the services while preserving database storage.
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml down

# Start again; rebuild after changing source.
sudo docker compose --env-file .env.bank-lab -f compose.bank-lab.yaml up --build -d
```

Do not add `--volumes` to routine shutdown commands: the database volume holds the current lab state. Use the reset command for a repeatable baseline.

| Symptom | Next check |
|---|---|
| Health fails before the first reset | Initialize the bank, then retry health |
| Database is unhealthy | Inspect `db` logs and environment configuration |
| Database authentication fails | The administrator password must match the value used when the PostgreSQL volume was first initialized. Reset provisions the app role from the current app password; changing the administrator environment value does not update the existing database password |
| Browser cannot connect, but Ubuntu health passes | Keep the forwarding window open and check its error output and local port |
| `Address already in use` in PowerShell | Use Windows port 3001 as described above |
| Health works but browser cannot connect | Check that the `proxy` service is up and publishes `127.0.0.1:3000->8080/tcp`; inspect proxy logs |
| Reset reports connection failure | Check service state and database readiness; retry only after the database is healthy |
| Build is killed or exits under memory pressure | Check `free -h` and build diagnostics; use a larger instance or build the image on a compatible machine |

If you request help, share status codes and relevant error text with credentials, cookies, connection strings, and protected records removed. Do not paste the environment file or expanded Compose configuration.

## 9. Prepare integration with the rest of the project

Keep the bank as a separate target component. The core, not the website's browser UI, will own session control, target registration, capabilities, budgets, cancellation, team visibility, and referee dispatch. See the [architecture](ARCHITECTURE.md) and [draft integration contracts](INTEGRATION_CONTRACTS.md).

The implementation provides bank routes for login/logout, current identity, accounts, protected vault access, and health. Reset stays behind an operator command. It does not expose a public telemetry export route. Before connecting other owners, agree on these handoffs:

| Recipient | Next integration work |
|---|---|
| Core / Diego | Register a fixed bank origin and health check, map an operator reset action, enforce permitted target capabilities, and link the bank run ID to the contest session |
| Joseph / Red | Expose only registered target observations and permitted actions; use credential references rather than raw secrets in prompts |
| Aaron / Blue | Define sanitized telemetry and bounded defensive actions, preserving his implementation after inventorying it |
| Referee / Diego | Add independently verifiable vault-access evidence and authorized-use regression checks; keep scenario ground truth private |
| Omar / Arena | Consume judge-safe events from the core and use a deliberate browser access path to this target |

These are planned integration steps, not implemented guarantees. Do not connect agents by handing them unrestricted SSH access or the PostgreSQL credentials. The `database` network is shared by the app and database, `frontend` connects the app to its proxy, and only the proxy joins `host-access`. The app and database networks are internal, so the target app has no general outbound Internet route. Broader services need a reviewed integration boundary.

After the healthy, resettable baseline works, add isolated variants for broken access control, authentication/session weakness, and input handling. Keep their answer key in the protected evaluation path and retest both unauthorized blocking and legitimate use after a repair. For deliberate security testing on OCI, Oracle currently requires its notification form and a five-business-day lead time; arrange that before the later testing stage. [Oracle security testing policy](https://www.oracle.com/corporate/security-practices/testing/cloud/)
