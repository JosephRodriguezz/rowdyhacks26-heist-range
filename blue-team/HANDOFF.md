# Blue team handoff: state of the Mayo branch

Written 2026-10-01 for the PM's planning of the new repository. Branch `Mayo` of `JosephRodriguezz/RowdyHacks26`, owned by Member 4 (blue team). Latest commit `6e244f7`, pushed.

## 1. What blue is

Blue is the defending side of RANGE. It reads telemetry from the lab target, detects attacks, proposes defenses, and produces evidence. It follows three rules from the team spec (`docs/PROJECT_SPEC.md`, `shared/contracts/README.md`):

- **Blue detects from telemetry and the access policy only.** It never sees red's plans, candidate findings, reasoning, or the evaluation answer key.
- **Blue proposes, core executes, the referee verifies.** Blue never applies a defense itself and never marks its own fix as verified.
- **Containment is never presented as a fix.** Revoking a session stops one attacker; only a referee-verified patch fixes the flaw.

## 2. What is built and tested

Everything is in `backend/app/agents/blue/` (code), `backend/tests/blue/` (105 passing tests), and `defenses/` (patch artifacts). It uses only the Python standard library.

| Piece | File | What it does |
| --- | --- | --- |
| Detector | `detection.py` | Flags successful private-record reads by a different user (`cross_user_read`) or by no user (`anonymous_read`). Owner reads never alert. Refused requests do not alert yet. Malformed records are skipped, never alerted on. |
| Containment proposals | `proposals.py` | One `revoke_session` proposal per attacking session, by session reference only, labeled containment. Skips sessions already revoked. |
| Patch proposal | `proposals.py`, `patches.py`, `defenses/patches/ownership-fix-001/` | Proposes the ownership-check patch for `GET /api/orders/{id}` when the current version still leaks. The patch is a **draft** until Member 3 publishes the lab's order handler. |
| Incident report | `incident.py`, `report.py`, `frameworks.py` | Evidence report organized by NIST CSF 2.0 (per NIST SP 800-61 Rev. 3). Classified with MITRE ATT&CK T1190/T1078, CWE-639, OWASP API1:2023. SHA-256 digest per evidence item and for the report. |
| Entry point | `observe.py` | `async observe(context, tools)`, the contract boundary core calls. Chains detection, proposals, and the report. Hardened over five review rounds (section 4). |

### observe() interface

**Input context** (any other top-level key is rejected): `target_id`, `target_version`, `data_source` (`fixture`, `live`, or `recorded`), `telemetry`, `access_policy`, `previous_defenses`, `budgets`, `assessment_id`, `generated_at`. The first five are required. At most 10,000 telemetry records per call.

**Telemetry record fields** (from the shared contract): `request_id`, `timestamp`, `target_id`, `target_version`, `actor_ref`, `session_ref`, `resource_id`, `resource_owner_ref`, `action`, `http_status`. Any other field is stripped before use.

**Output** (`range.blue.observe/v1`): `alerts`, `defense_proposals`, `evidence_refs`, `skipped`, `summary`, `report`, `report_scope`, `notes`, plus target and source labels. Alert and proposal payloads already match the contract's `alert.created` and `defense.proposed` events.

## 3. How blue is built: the multi-model framework

Blue is developed by three AI coding agents working together through files on the branch, under a deterministic Python orchestrator in `blue-team/`. The design is in `blue-team/ARCHITECTURE.md`; the rules are in `blue-team/AGENTS.md`.

- **Models:** Claude (`claude`), Codex (`codex`), Antigravity (`agy`). Default roles:
  - Claude facilitates and handles isolation-sensitive code.
  - Codex handles implementation and tests.
  - Antigravity handles cross-repo analysis and research.

  Roles are configurable.
- **Flow per task:**
  1. Independent proposals.
  2. A facilitator summary (not a vote).
  3. A vote counted by code.
  4. Human approval.
  5. Implementation.
  6. Independent review by the other models.
  7. Deterministic checks.
  8. The human closes it.
- **Controls:**
  - Any security objection or tie stops for the human.
  - No model reviews its own work, and at least 2 independent reviewers are required.
  - Models cannot commit, push, or switch branches.
  - Snapshots around every model run catch out-of-bounds file changes and git changes.
  - Git hooks limit commits to `Mayo` and the blue folders, and keep threads, decisions, and state history append-only.
- **Tooling:**
  - `orchestrate.py doctor` and `doctor --live` check tools, git, and each model.
  - `auto <task> --dry-run` shows the plan.
  - `auto <task>` runs until a human step.
  - 63 framework tests run against stand-in model programs.
- **Shared memory:**
  - `tasks.json` / `CHECKLIST.md`: task board.
  - `comms/threads/`: discussion.
  - `decisions/`: vote records.
  - `state/`: workflow history.

Model consensus is advisory. Tests, isolation, guardrails, and the human are the real controls.

## 4. What the B-06 review rounds taught us

B-06 (`observe`) took five rounds. Codex raised four security objections; each was verified and fixed. These are now guarantees blue relies on, and the red side should know them:

| Round | Weakness found | Now enforced |
| --- | --- | --- |
| 1 | Extra telemetry fields (for example `ground_truth`) leaked into the report; other targets' or assessments' events changed this one | Records reduced to allowed fields; everything scoped by target, version, assessment |
| 2 | A malformed record with the same request ID hid a real alert; "contained" claimed for the wrong session | Records are validated before their ID is reserved; containment needs the alerted session revoked |
| 3 | A session that kept reading after revocation still counted as contained | Containment needs no unauthorized read from that session after the revocation |
| 4 | Fixture events could change a live report; free-text failure reasons were copied into the report | Scoped by `data_source`; failure reasons replaced with a fixed message |

## 5. What the red side should know

Built for the scenario in the spec: one website/API, Alice and Bob with private orders, an ownership flaw on `GET /api/orders/{id}`, a protected control at `GET /api/secure-orders/{id}`.

- **Blue detects red only through lab telemetry.** Whatever red does must appear in the lab's logs with the fields above. Attacks that leave no telemetry are invisible to blue by design. Red's agents, plans, and prompts must never be passed into blue's context; `observe` rejects unknown keys.
- **Today blue detects:** cross-user private reads and anonymous private reads.
- **Planned:**
  - probing, from repeated refused reads (B-09),
  - credential attacks (needs login and session telemetry from the lab),
  - swarm clusters (section 6).
- **Blue's response to red today:**
  1. Revoke the attacking session.
  2. If red comes back with a fresh session, propose the ownership patch.
  3. The referee retests.

  Red should expect revocation and design for fresh-session retries; that adaptation is part of the planned demo.
- **Known open weakness red could exploit:** flooding telemetry past 10,000 records makes `observe` reject the input instead of degrading. Core should window telemetry. Listed for the swarm plan.
- **Correlation limit:** telemetry has no client fingerprint, so blue can link sessions into one swarm only by timing and targets. A hashed `client_ref` from the lab would make swarm detection much stronger.

## 6. Swarm direction (discussed, not decided)

Following the PM's 2026-10-01 direction (heist theme, red and blue swarms, 3D bot UI, live target on a second laptop), the three models and Member 4 discussed blue's swarm. The full thread is `blue-team/comms/threads/swarm.md`.

**Agreed in principle by all three models:**
- **Blue specialists are deterministic modules, not separate AI models.** AI writes only summaries.
- **The roles:**

  | Role | Status |
  | --- | --- |
  | Sentry: input validation | Exists |
  | Detector | Exists |
  | Correlator: swarm clusters | New |
  | Risk assessor | New |
  | PACE planner | New |
  | Patch engineer | Exists |
  | Evidence clerk | Exists |
  | Posture accountant: armor and threat-model data for the UI | New |

**Proposed designs:**
- **Clusters.** Group activity that shares a session or actor, hits the same records from different sessions, or walks sequential IDs, within a time window. Score each cluster on three axes:
  - **Type:** mapped to ATT&CK, CWE, and the OWASP Automated Threats list.
  - **Size:** lone (1 session), crew (2–4), or syndicate (5+).
  - **Risk:** likelihood × impact per NIST SP 800-30, with every factor shown. Not CVSS.
- **PACE response tiers,** ordered by harm to legitimate users:

  | Tier | Action |
  | --- | --- |
  | Primary | Revoke the attacking session |
  | Alternate | Ownership patch |
  | Contingency | Reroute the vulnerable endpoint or force re-login |
  | Emergency | Lockdown or reset, human-only |

  Contingency and Emergency need new contract action types.
- **Fail-safes:**
  - act only on the attacking session, never the victim,
  - refused requests never lock accounts,
  - step-by-step escalation with cooldowns,
  - a circuit breaker on how many users an action affects,
  - every action reversible.
- **Game armor.** Use MITRE D3FEND's seven tactics (Model, Harden, Detect, Isolate, Deceive, Evict, Restore) as armor slots, with heist names on top. Credit by state: verified fixes count fully, applied patches partly, containment a little, failures show as "cracked". The player picks defenses only from a fixed catalog.
- **Proactive measures:**
  - canary records ("dye packs"),
  - decoy endpoints,
  - graduated rate limiting and slowdowns,
  - unpredictable record IDs.

**Open decisions:**
1. **PACE Primary:** contain first, or observe first? The recommendation is to let confidence decide.
2. **Timing:** finish Milestone 1 first, or build the scoring module in parallel?
3. **Armor model:** grouping, credit scale, and armor per attack path.
4. **Requests to teammates** (below).
5. **Website or network** (the PM's decision). Blue recommends a website/API "bank" with several services, with network attacks as a stretch goal.

## 7. What blue needs from other members

| Request | From | Why |
| --- | --- | --- |
| Confirm `observe` input field names and the `access_policy` format | Member 2 (core) | The strict input check rejects anything else |
| New action types (reroute, force re-login, lockdown/reset) and events (cluster, PACE tier, posture) | Member 2 | Contingency and Emergency tiers, UI data |
| Window telemetry rather than send it all at once | Member 2 | Closes the flood weakness |
| Hashed `client_ref` in telemetry | Members 2 and 3 | Real swarm correlation |
| Login and session telemetry; canary records; a decoy endpoint | Member 3 (lab) | Credential-attack detection; certain alerts with no false positives |
| The order-route handler file | Member 3 | Finalize the patch (B-13) |
| Display armor, threat model, and labels | Member 1 (UI) | The game view |

## 8. Task board snapshot

- **Done:**
  - B-01: detector.
  - B-02: revocation.
  - B-03: patch proposal.
  - B-04: incident report.
  - B-06: `observe`.
- **In review:** B-05, the multi-model framework.
- **To do, Milestone 1:**
  - B-07: stand-in executor and end-to-end test.
  - B-08: failed and rolled-back defense results.
  - B-09: probing detection.
  - B-10: executor edge tests.
  - B-11: defense-action docs.
- **To do, other:**
  - B-12: contract requests.
  - B-14: UI labels.
  - B-15: cross-branch review.
  - B-18: strategy review.
- **Blocked:**
  - B-13: patch, waiting on the lab.
  - B-16: needs PR #1 merged.
  - B-17: live run, waiting on lab and core.

**Known issue to fix before live reporting:** `incident.py` marks a fix "resolved" when any retest passes, without checking that every required check passed.

## 9. Alignment with the team kickoff kit

`Mayo` now includes the kickoff kit from the PR #1 branch (`docs/weekend/`), merged in commit `52d2a05`.

**Roster to confirm.** `docs/weekend/START_HERE.md` lists Aaron as Member 2 (core and integration) and Omar as Member 4 (blue), marked provisional. All work on `Mayo` so far was done by Aaron as blue. Confirm roles at kickoff.

**Website first.** `docs/weekend/DECISIONS.md` fixes one isolated website/API for the first slice, with the bank as a visual skin over the storefront contract. That matches everything blue has built. Network attacks remain a stretch goal.

**Blue's build-board tasks map onto blue's work:**

| Build board | Blue work on Mayo | Status |
| --- | --- | --- |
| BLUE-01: telemetry-only detection with an owner-read negative control | B-01 detector, B-06 `observe` | Done |
| BLUE-02: reviewed ownership patch pinned to the original version | B-03 patch artifact, B-13 handler | Draft; waiting on Diego's RED-01 handler |
| BLUE-03: session revocation with real executor results | B-02 proposals, B-08 executor outcomes | Proposals done; results to do |
| BLUE-04: patch application, provenance, bounded decision loop | B-03, B-07 end-to-end | To do |
| BLUE-05: stale or rejected patches, missing telemetry, executor errors | B-10 | To do |

**Swarm scope.** `DECISIONS.md` says to drop extra characters and autonomous mode if behind at H14. The swarm (section 6) is post-MVP work.

**Found while merging.** `scripts/doctor.py` crashes on Windows: `npm` resolves to `npm.CMD`, `subprocess.run(["npm", ...])` raises `FileNotFoundError`, and the script catches only timeouts. Member 2's file, so it is reported rather than changed.

## 10. Moving to the new repository

Blue's work moves as the `Mayo` branch with full history; a bundle backup is also planned. In the new repo:
- run `python blue-team/bin/guard.py install`,
- set `remote` in `blue-team/config.json` if it is not `origin`,
- check that every model CLI is signed in with `python blue-team/bin/orchestrate.py doctor`.

The framework (`blue-team/`) is reusable: other members can run the same orchestrator for their own work by changing `model_write_paths` and the roles.
