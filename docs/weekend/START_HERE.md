# Weekend kickoff — RANGE / The Heist

Build window: **24 hours**. The goal is one repeatable live heist: discover an ownership flaw, prove it independently, contain the session, retry, patch, and verify that private data is protected while legitimate access still works.

## Working roster

Names are confirmed; role assignments are provisional and can be swapped at kickoff.

| Member | Person | Owns | Start here |
| --- | --- | --- | --- |
| 1 | Joseph | City UI and clickable characters | [UI packet](../team/01-arena-ui.md) |
| 2 | Aaron | API, tools, referee, integration | [Core packet](../team/02-orchestrator-referee.md) |
| 3 | Diego | Lab and red agent / robbers | [Red packet](../team/03-red-team-lab.md) |
| 4 | Omar | Detection and blue defenses / cops | [Blue packet](../team/04-blue-team-defense.md) |

Aaron coordinates interfaces; each member tests their own module and the receiving member checks the handoff. Joseph prepares the demo story while building the UI.

## Before arriving

- [ ] Review the event's actual rules on prebuilt code, AI tools, public repositories, and submission requirements. Keep the existing commit history so preparation work can be disclosed. Eligibility has not been checked against organizer rules.
- [ ] Confirm the role assignments above and choose one integration/demo laptop.
- [ ] Repo owner confirms each teammate's GitHub access. A public repo can be cloned now; write access or fork PRs are needed for contributions. Names alone are not GitHub usernames.
- [ ] Everyone runs the setup check below and opens the preview. Do this while reliable internet is available.
- [ ] Joseph checks Node/npm; Aaron and Diego check that Docker's engine actually starts; Omar checks the Python environment and patch handoff with Diego. Exact application versions and lockfiles are chosen when the modules are bootstrapped; none exist yet.
- [ ] Choose one model provider/model and a spending cap together. Keep keys in ignored local environment files; don't send keys in chat. The starter kit uses no keys. Aaron confirms account access before integrating models.
- [ ] Bring chargers, adapters, power strip if permitted, and a browser with the local preview already loaded. Icons use a CDN; characters and core controls work without them.

## Get the starter kit

Until [PR #1](https://github.com/JosephRodriguezz/RowdyHacks26/pull/1) is merged, use its branch:

```sh
git clone --branch codex/team-frameworks https://github.com/JosephRodriguezz/RowdyHacks26.git
cd RowdyHacks26
python3 scripts/doctor.py
python3 -m http.server 8000 --bind 127.0.0.1 --directory frontend/preview
```

Open <http://127.0.0.1:8000>. Stop the preview with Ctrl+C. If port 8000 is occupied, use 8001. On Windows, substitute `py -3` for `python3` if needed.

Before starting feature branches, the repo owner should review and merge PR #1. Everyone then starts from that same `main` commit:

```sh
git fetch origin
git switch main
git pull --ff-only
git switch -c codex/member-1-ui
```

Use `codex/member-2-core`, `codex/member-3-red`, or `codex/member-4-blue` for the other roles. If PR #1 remains unmerged, create role branches from `origin/codex/team-frameworks` and target that foundation branch until the team explicitly migrates to `main`. Do not mix starting points.

## First 30 minutes

1. Confirm rules, roles, integration laptop, provider access, and starter commit.
2. Open [the build board](BUILD_BOARD.md); each member takes their first task.
3. Read the [contract](../../shared/contracts/README.md). Keep `storefront-lab`, order IDs, and event names stable for the first live slice. The bank/city is the presentation theme; bank-record renaming can wait.
4. Diego and Omar agree on the lab handler that the ownership patch will change. Aaron defines the exact credential-reference and executor adapter shapes with them.
5. Joseph starts against the shared fixture immediately. Nobody waits for a complete neighboring module.

## Commands that exist today

```sh
python3 scripts/doctor.py
python3 scripts/check_handoff.py --self-test
python3 scripts/preview.py --check
python3 scripts/preview.py  # regenerate the current standalone preview after source edits
git diff --check
```

Edit `docs/design/agent-inspector.fragment.html`; `scripts/preview.py` updates the existing standalone wrapper without needing Codex installed. If the shared fixture changes, update its embedded copy in the source first. Do not hand-edit the exported preview.

## What is ready / what is still to build

Ready: city sample replay, clickable robber/officer/auditor inspection, shared fixture and vocabulary, four role packets, preparation scripts, CI workflow, PR/issue templates, build board, and demo checklist.

Still to build: runnable frontend application, API, lab, model agents, tools, persistence, event streaming, patch executor, independent live verifier, Compose, and live tests. The preparation checks do not certify any of those future components.

Next: [24-hour build board](BUILD_BOARD.md) · [decisions and risks](DECISIONS.md) · [demo script](DEMO.md) · [integration acceptance](../team/INTEGRATION.md).
