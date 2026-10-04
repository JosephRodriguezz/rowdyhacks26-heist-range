# Running the Red prototype on a machine that isn't this one

**Status:** Verified in this session: a from-scratch Docker build, on a different OS (Linux container,
built from Windows) than it was developed on, passes the full suite and runs every scenario identically.
**Scope:** the standalone Red prototype (`red/`) only — this does not deploy the frontend preview,
`blue-team/`, or anything else in the repo, and it does not reach a real external bank (see
[`AVAILABILITY_SCENARIO.md`](AVAILABILITY_SCENARIO.md) and [`INTEGRATION_READINESS.md`](INTEGRATION_READINESS.md)
for that gap).

## Why this needed checking, not just assuming

`red/` has zero third-party dependencies (standard library only; the optional model-mode adapter calls the
OpenAI API over `urllib.request`, not the `openai` package). That makes it *likely* portable, but this
session found a real, concrete reason not to take portability on faith: one test
(`test_virtual_traversal_cannot_read_a_real_host_file`) silently depended on `str(Path)` producing a
POSIX-style path. It does on Linux/macOS; on Windows it's `C:\Users\...`, which tripped a different,
also-safe code path and produced the wrong HTTP status for the wrong reason. Fixed in this session (see the
commit) and now verified passing — 118/118 — on both Windows and a fresh Linux container.

## What "deployed" means here

The lab target binds to `127.0.0.1` only, by design (`docs/red/VULNERABILITY_CATALOG.md`,
`FixedTargetRegistry`) — this is a deliberate safety property, not a gap to fix. It means:

- **"Deploy the Red prototype so it can run anywhere" — done, this is what's below.** Any machine with
  Docker (or just Python 3.9+, nothing else) can clone the branch and run the exact same demo that ran on
  this machine, with the exact same, independently-verified results.
- **"Expose the vulnerable lab target to the network/internet" is a different, much bigger ask that this
  does not do and that nothing here changes.** The target only ever talks to the Red prototype's own
  process over loopback. That is intentional — relaxing it would be a real security-posture change to a
  project whose explicit design is "reject arbitrary destinations," not a deployment detail, and isn't part
  of this work.

## Run it with Docker (recommended — no local Python setup required)

From the repository root, on any machine with Docker installed:

```sh
docker build -t red-prototype .
docker run --rm red-prototype scenarios
docker run --rm red-prototype run --scenario availability --mode deterministic_baseline
docker run --rm red-prototype run --scenario availability --mode deterministic_baseline \
  --simulated-defense availability --defense-after-actions 0
docker run --rm red-prototype run --scenario access_control --mode deterministic_baseline
docker run --rm --entrypoint python red-prototype -m unittest discover -s tests -v
```

Each `run` prints the same JSON report format documented in the main README. `--report /app/out.json`
writes inside the container; redirect stdout instead if you want the file on the host, e.g.
`docker run --rm red-prototype run --scenario availability --mode deterministic_baseline > result.json`.

The image only contains `red/` and `tests/` (see `Dockerfile` and `.dockerignore`) — nothing else in the
repository is copied into it.

## Run it without Docker

Only Python 3.9+ is required; nothing to `pip install` for the deterministic/demo path.

```sh
python3 -m compileall -q red
python3 -m unittest discover -s tests -v
python3 -m red.prototype.cli run --scenario availability --mode deterministic_baseline
```

Model mode (`--mode model --allow-remote-model`) additionally needs `OPENAI_API_KEY` and `OPENAI_MODEL` set
in the environment — still no package install, since the adapter talks to the API directly over
`urllib.request`. See the main README and [`AVAILABILITY_SCENARIO.md`](AVAILABILITY_SCENARIO.md) for why
that path is unverified and the deterministic baseline is what's actually relied on for the demo.

## What this does not claim

- Does not make the lab reachable from outside the machine/container it runs in — see above.
- Does not connect to a real bank/core — none exists yet anywhere in this repository (checked every
  branch).
- Does not package or verify `blue-team/`, `backend/`, or `frontend/`.
