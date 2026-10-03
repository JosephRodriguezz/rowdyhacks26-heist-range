# Blue team handoff for a Codex-only owner

Written 2026-10-03 by Claude for Aaron (Member 4), who is moving to the red team. Read this file first. It tells you what you now own, what is finished, what is next, and how to work with Codex alone. The long background is in [HANDOFF.md](HANDOFF.md).

**Where things stand in one paragraph.** Blue (a Monitor and a Defender) reads telemetry from the lab, detects unauthorized private-record reads, proposes defenses, and writes an evidence report. That core is built and tested (233 blue tests pass, plus 7 documented known-bug tests). The swarm design spec (B-19) is approved. A stand-in defense executor and the first end-to-end flow tests are merged. Nothing runs against the live lab yet, because the lab and core's executor are Diego's and are not built. The next work is fixing three small bugs found by adversarial tests, then building the Monitor and Defender agents (B-21) and the package Diego integrates (B-24).

## 1. What you own, and what you do not

| Yours (Blue) | Not yours |
| --- | --- |
| `backend/app/agents/blue/` (code), `backend/tests/blue/`, `defenses/`, `blue-team/` | `shared/contracts/` (Diego coordinates changes), `scripts/`, `docs/`, the root `AGENTS.md`, `.github/`, `cyber_range/`, `frontend/` |

People you depend on, and what you owe each: **Diego** (core control plane, referee, bank lab) executes your proposals and runs the retest; **Omar** (arena, 3D bank view) shows your data; **Joseph** (PM and Red team) decides scope and disclosure. Never edit another member's files; send a request instead (section 8).

## 2. The rules that cannot bend

These are the project's rules from the root `AGENTS.md`, `blue-team/AGENTS.md`, and `shared/contracts/README.md`. A change that breaks one is a bug even if tests pass.

1. **Blue proposes. Core executes. The referee verifies.** Blue never applies a defense and never marks its own fix verified. Only a referee `retest.completed` event can verify a fix.
2. **Containment is not a fix.** Revoking a session stops one attacker only.
3. **An applied patch is not a verified fix** until a referee retest passes every required check (`unauthorized_access` and `owner_access`).
4. **Fail closed.** Timeouts, failed logins, and missing evidence are inconclusive, never a successful defense and never an alert-free pass.
5. **Blue sees sanitized telemetry and the access policy only.** Never red's plans, findings, or reasoning, and never the seeded vulnerability ground truth. `observe()` rejects any other context key; keep it that way.
6. **No credentials** in prompts, events, logs, reports, or committed files. Sessions are references only.
7. **Treat target content as untrusted input.** Telemetry is data, not instructions. Enforce permissions and budgets in code, not in a model.
8. **Registered lab targets only.** Resolve target IDs from the fixed registry; reject arbitrary destinations.
9. **Label honestly.** Fixture, recorded, and live data are different. A stand-in executor is not core's executor. Specified is not built. Do not claim a live capability from fixture behavior.
10. **Preserve authorized behavior.** A fix that blocks everyone is not a defense.

## 3. State of the branch (`Mayo`) at handoff

| Area | State |
| --- | --- |
| Detector, containment proposals, patch proposal, incident report, `observe()` | Built and tested (`detection.py`, `proposals.py`, `patches.py`, `incident.py`, `report.py`, `frameworks.py`, `observe.py`). |
| B-23 retest rule | Merged. A retest that says `passed` no longer resolves an incident unless every required check is present, passed, and `actual == expected`. Two edge cases remain (B-29, section 7). |
| B-07 stand-in executor | Merged: `executor_stub.py` and `test_blue_flow.py`. It is a **test double**: in memory, no lab, no credentials, and it marks every event `"executor": "stand-in"`. It is not core's executor. |
| B-25 patch tests | Merged. They use committed fixture folders and create no files, so they run in a read-only sandbox. |
| Adversarial and gap tests (F1, F2) | Merged. 7 tests are marked `@unittest.expectedFailure`; each documents a real bug (section 7). Never edit a test to match a bug. |
| Defense docs and contract requests (F3, F4) | Merged: `defenses/README.md` and `blue-team/proposals/contract-v1.1-blue-requests.md`. The requests are **drafted, not yet sent to Diego** (B-12). |
| Swarm design spec (B-19) | Approved by two independent reviewers after 18 attempts: `backend/app/agents/blue/design/swarm-spec.md`. It is a design, not code. Section 1.4 sorts every capability into Group A (built), Group B (specified, not built), and Group C (inert until core supplies event IDs). The first demo must not show Groups B or C. |
| Patch artifact | `ownership-fix-001` is a **draft** until Diego publishes the lab's order handler (B-13). |
| Lab, core executor, referee, report endpoint | Not built (Diego's). Blue has only stand-in behavior against them. |

Review of the merged lane work: Claude read all of it, and Antigravity reviewed it read-only; the record of what each read and found is in `blue-team/comms/threads/lane-review.md`. Codex wrote B-23, B-25, and B-07, and Cursor wrote F1 to F4.

## 4. Commands

Run from the repository root unless noted. On Windows use `python`; the root docs say `python3`.

```bash
# Blue tests (233 pass, 7 expected failures). Run from backend/.
cd backend && python -m unittest discover -s tests/blue

# Whitespace check
git diff --check

# Shared handoff fixture and negative cases
python scripts/check_handoff.py --self-test

# Framework tests (84 tests, about five minutes). They need temp folders, so run
# them outside a read-only sandbox.
python -m unittest discover -s blue-team/tests
```

If you change anything under `backend/`, run the first three before every commit. If you change `blue-team/`, run the framework tests too. Board commands that work without the orchestrator: `python blue-team/bin/board.py claim|move|edit|post|read ...` (`--model codex` is accepted).

## 5. Working with Codex alone

**The orchestrator needs three models.** `blue-team/bin/orchestrate.py` requires a Claude facilitator and at least two independent reviewers, and it stops without them. Do not run `auto`, `plan`, `implement`, or `review`. Run the commands in section 4 instead. `blue-team/CODEX_LANE.md` is the working pattern we used for Codex: one task per branch, bounded files, tests first.

**Suggested flow for one task**
1. `python blue-team/bin/board.py claim B-26 --model codex`
2. Branch from `Mayo`: `git switch -c codex/b-26`.
3. Give Codex the task prompt from section 9. Make it write the failing test first and confirm it fails.
4. Run the section 4 commands. Read your own diff against the section 2 rules.
5. **Get a human to review before it reaches `Mayo`.** See below.
6. Merge to `Mayo`, then `python blue-team/bin/board.py move B-26 done --model codex --note "..."` with the commit and what review happened.

**The honest weakness: no independent AI reviewer.** A model reviewing its own work is not independent, and the project's rule is that no model reviews its own work. With Codex only, the replacement is a human. Ask a teammate to read the diff and run the commands for any change to detection, proposals, patches, the incident report, `observe()`, or the stand-in executor. Diego must agree any contract change. Say in the commit message and the board note who reviewed. If nobody reviewed, write that; do not write "reviewed". Consider asking Joseph to record a short decision in `blue-team/decisions/` that single-model mode is accepted for blue, with this human-review rule.

**Do not install the git hooks unless you want their limits.** `python blue-team/bin/guard.py install` restricts commits to branch `Mayo` and the blue folders and makes threads, decisions, and state append-only. It is built for the three-model setup. Without it, follow the same discipline by hand: keep commits inside your folders, and never rewrite history that others have pulled.

**When to stop and ask a human first:** a change to security policy, to what blue accepts as input, to a contract file, a new dependency, or anything that touches credentials, the registry, or the executor boundary.

## 6. Work queue, in priority order

Task IDs are on the board (`blue-team/tasks.json`, rendered in `blue-team/CHECKLIST.md`). Items 1 to 3 are small and have failing tests already written for them.

| # | Task | What and why | Files |
| --- | --- | --- | --- |
| 1 | **B-26** | **Medium bug.** A date-only timestamp such as `2026-09-30Z` parses as a naive datetime, then one record crashes detection, `observe()`, and the report with `TypeError`. Make the parse return `None` (record skipped) and make a bad `generated_at` a `ContextError`. | `detection.py` (`parse_utc_timestamp`), `observe.py`; remove 4 `expectedFailure` decorators |
| 2 | **B-27** | **Low bugs.** A NaN budget runs a full observation as `completed`. Unhashable values (a list where a string belongs) raise `TypeError` instead of `ContextError` or `PatchManifestError`. | `observe.py`, `patches.py`; remove 3 decorators |
| 3 | **B-29** | **`incident.py` gaps** found in review, both reproduced. A second applied patch that was never retested still shows `resolved`; `fix_verified` keeps an old timestamp after a later failed retest. Also from the Fable audit: the weaker second path in `report.py`, and one shared required-check list. | `incident.py`, `report.py`, tests |
| 4 | **B-21** | **Build the Monitor and Defender agents** (the ship goal). Deterministic wrappers over the existing modules; `observe()` returns an `agents` list of `agent.status` payloads. No AI yet (decision 0007). | new module, `observe.py`, tests |
| 5 | **B-24** | **Ship package for Diego**: a README showing how core calls `observe`, an example context, a replay script, a version tag. After B-21. | `backend/app/agents/blue/`, docs |
| 6 | **B-12** | **Send the contract requests to Diego** and get answers. The document is ready: `blue-team/proposals/contract-v1.1-blue-requests.md`. A person must send it; section 10 of that file lists Diego's questions. | none (a message or PR) |
| 7 | **B-09, B-08, B-10** | Denied-probing detection; ingest executor failure and rollback outcomes; stress tests (floods, malformed input). The circuit-breaker parts wait on B-12. | `detection.py`, `observe.py`, tests |
| 8 | **B-14** | Labels and arena data for Omar: heist names for the seven D3FEND armor slots, plain-language alerts. | a proposal file, then Omar |
| 9 | **B-20** | Tell Joseph which blue work existed before the event started, so the submission discloses it. A human task. Prepared work is everything on `Mayo` before the event start; record the start time and the last commit before it. | none |
| - | **B-13, B-17, B-22** | Blocked: B-13 on Diego's order handler; B-17 on the lab and core; B-22 (AI advisor) on B-12. | |
| - | **B-28, B-30, B-31, B-32** | Process and team-file items from the Fable audit. They need Aaron, Joseph, Diego, or the three-model setup, not Codex alone. See section 8. | |

## 7. Known issues and limits

**The 7 documented bugs** (`backend/tests/blue/test_blue_adversarial.py`, search for `expectedFailure`; each comment names the input and the source line). Date-only timestamp: 4 tests, medium, B-26. NaN budget: 1 test, low, B-27. Unhashable enumerated values in `observe.py`: 1 test, and in `patches.py`: 1 test, both low, B-27. When you fix one, its test starts to pass, `unittest` reports an unexpected success, and you delete the decorator.

**B-29, reproduce with the helpers in `backend/tests/blue/test_blue_incident.py`** (`event`, `retest`, `report_for`, `PATCH_APPLIED`, `REVOKE_APPLIED`):
- Add a failing retest after a passing one for the same patch. Status becomes `fix_failed`, but `report["times"]["fix_verified"]` still holds the earlier timestamp.
- Apply `d-patch` (to `lab-v2`), pass its retest, then apply a second patch to `lab-v3` with no retest. Status stays `resolved`. It should be `awaiting_retest`, because the latest applied patch has no passing retest.

The first demo has one patch, so neither shows. Both are false claims in the report, so fix them before multi-patch runs.

**Other limits**
- Telemetry has no `event_id` today, so persistence credit, Alternate-on-bypass, and armor cracking are specified but inert (spec Group C). Diego must add event IDs (B-12).
- Clustering, risk scoring, the PACE planner, and armor posture are specified, not built (Group B). Do not build them before B-21 ships.
- The stand-in executor adds an `executor` key to its events. The contract lists required keys only and does not forbid extras, but core's real executor must not rely on it.
- The patch is a draft; the lab does not exist yet; core's executor, referee, and report endpoint do not exist. Everything runs on fixtures.
- `observe()` rejects more than 10,000 telemetry records instead of degrading. Core should window telemetry (requested in B-12).
- The package `__init__` exports an `observe` function that shadows the module; use `importlib.import_module("app.agents.blue.observe")` when you need the module.
- `scripts/doctor.py` crashes on Windows (`npm.CMD`); it is Member 2's file, so it is reported, not changed.
- `blue-team/STATUS.md` is a generated, git-ignored dashboard and sometimes fails to refresh on OneDrive; the failure is harmless.
- Joining `Mayo` into the new repository's `main` (B-16) is on hold until the team decides.

## 8. The Fable audit (21 findings) and where each went

A Fable 5.1 audit of the repository was pasted on 2026-10-02. The original text is not in the repository; this is the summary Claude kept, with Claude's own check of it (findings 3, 4, 10, and 19 were overstated or partly wrong, as noted). Findings 8 and 21, and parts of 19 and 20, were kept only as titles; ask Aaron for the original if you need the detail.

| # | Finding (short) | Status |
| --- | --- | --- |
| 1 | Two rosters (`docs/team`, `docs/weekend` versus `blue-team`) | Team process; B-31 reports it to Joseph |
| 2 | Two repositories | Settled: the new repo is `origin`; the old repo is left alone by decision; no task |
| 3 | `ACCEPTANCE_CHECKS` (five) versus `REQUIRED_CHECKS` (two) | Partly overstated: it only feeds limitation text; the inconsistency is real, B-29 |
| 4 | Stale docs | Mostly fixed with this handoff (`HANDOFF.md` test counts and the B-16 line). The root `AGENTS.md` line about no live test suite is still true. Old thread text is append-only and gets a note, not an edit |
| 5 | Contract gaps for core | Requests written and merged (F4); **sending them is B-12** |
| 6 | `resolved` without all checks | **Fixed in B-23** (merged); two edge cases left, B-29 |
| 7 | `report.py` weaker second path; one shared required-check list; containment rule location | B-29 (the shared list needs a contract change through Diego) |
| 8 | Title only kept | Ask Aaron |
| 9 | Telemetry flood raises `ContextError` | B-10 and the windowing request in B-12 |
| 10 | Patch ID fixed in `observe` | Overstated: deliberate, and `load_patch_manifest` already takes `patches_dir`; no task |
| 11 | Empty `__init__.py`, `pyproject` | Diego's bootstrap files; B-31 requests them |
| 12 | Test needs a writable temp dir | **Fixed in B-25** (merged) |
| 13 | `scripts/doctor.py` crashes on Windows | Member 2's file; B-31 reports it |
| 14 | CI runs only the handoff check, the preview check, and a patch check | B-30 asks Diego to add `backend/tests/blue` and `blue-team/tests` |
| 15 | No root `.gitattributes` | Team file; B-31 (git already warns about LF and CRLF here) |
| 16 | The human gate is unauthenticated: approvals made by Claude under standing authorization were recorded `by: human` | **P0 for the framework**, B-28: truthful actor recording, refuse human-only commands inside model runs, and a decision record ratifying the B-06 overrides. Needs the three-model setup |
| 17 | `max_revisions` not enforced on the revise path | B-32 (document the human override) |
| 18 | Role concentration | B-32 |
| 19 | Require a reviewer who ran tests for `backend/` changes | B-32; the claim that Antigravity had no B-06 findings was wrong (it had two low) |
| 20 | Run B-05 (the framework) through its own review | B-32; B-05 is still in `review` |
| 21 | Smaller items | Title only; ask Aaron |

## 9. Prompts for Codex

**How to use them.** Start Codex on a fresh branch from `Mayo`, paste one prompt, and let it work. Ask for a report that lists files changed and the exact test results. Then do the review step in section 5. We used `gpt-6.1-sol` at medium reasoning effort; that is a setting, not a requirement.

### B-26: date-only timestamp crash

```text
You are working in the RANGE repository on a fresh branch from Mayo, as the blue team engineer. Read first: root AGENTS.md; blue-team/CODEX_HANDOFF.md section 2 (the rules); backend/app/agents/blue/detection.py (parse_utc_timestamp); backend/app/agents/blue/observe.py (parse_context and the generated_at handling); backend/app/agents/blue/incident.py (_seconds_between); backend/tests/blue/test_blue_adversarial.py (the four @unittest.expectedFailure tests about date-only timestamps).

Problem: parse_utc_timestamp("2026-09-30Z") builds "2026-09-30+00:00", and datetime.fromisoformat returns a NAIVE datetime. The record then passes validation, and any comparison with an aware timestamp raises TypeError in detect_suspicious_access, observe._containment, and incident._seconds_between. One malformed record crashes blue.

Make this change:
1. parse_utc_timestamp returns None for any value that is not a full ISO 8601 UTC timestamp (date, time, and Z or +00:00). A naive result must never be returned. Keep every currently valid form valid.
2. A record whose timestamp parses to None is skipped as malformed, as other malformed records are, and the remaining records still alert.
3. observe() raises ContextError for a generated_at that does not parse, before doing any work.
4. Remove the @unittest.expectedFailure decorator from the four tests named in the problem. Do not edit their assertions. Run them first with the decorator removed and confirm they FAIL on the old code; then fix and confirm they pass.

Constraints: Python standard library only; edit only detection.py, observe.py if needed, and the decorators in test_blue_adversarial.py; no contract changes; do not weaken any other validation. Run: cd backend && python -m unittest discover -s tests/blue, then python scripts/check_handoff.py --self-test, then git diff --check. Report the files you changed and the exact results.
```

### B-27: NaN budgets and unhashable values

```text
You are working in the RANGE repository on a fresh branch from Mayo, as the blue team engineer. Read first: root AGENTS.md; blue-team/CODEX_HANDOFF.md section 2; backend/app/agents/blue/observe.py (_budgets, the budget exhaustion check, and the places that test a value against a set or dict); backend/app/agents/blue/patches.py (status, origin, and check expected validation); backend/tests/blue/test_blue_adversarial.py (the expectedFailure tests test_nan_budget_fails_closed, test_unhashable_enumerated_values_raise_context_error, test_unhashable_manifest_values_raise_manifest_error).

Problem: (a) observe._budgets accepts any float, and the exhaustion test `<= 0` is False for NaN, so a NaN max_steps or timeout_seconds runs a full observation as "completed". (b) Membership tests against sets and dicts raise TypeError for unhashable values (a list or dict) instead of ContextError, in observe.py for the context data_source, an event type, an event data_source, and data.action_type, and instead of PatchManifestError in patches.py for status, origin, and a check's expected.

Make this change: reject non-finite budgets (NaN, infinity) with ContextError; make every unhashable value in those positions raise ContextError (observe.py) or PatchManifestError (patches.py) with a fixed message that does not echo the value. Remove the three @unittest.expectedFailure decorators without editing the assertions. Confirm the tests fail on the old code first, then pass.

Constraints: standard library only; edit only observe.py, patches.py, and the decorators; no contract changes; do not change behavior for any valid input. Run the same three commands as B-26. Report the files changed and the exact results.
```

### B-21: Monitor and Defender agents (the big one; get a human review)

```text
You are working in the RANGE repository on a fresh branch from Mayo, as the blue team engineer. Read first: root AGENTS.md; blue-team/CODEX_HANDOFF.md sections 2 and 3; blue-team/decisions/0007-swarm.md and 0004-swarm.md (staged scope: deterministic agents only, no AI yet); backend/app/agents/blue/design/swarm-spec.md sections 1.4, 7.1, and 7.2; shared/contracts/v1.json (the agent.status event type and agent_statuses); shared/contracts/README.md; backend/app/agents/blue/observe.py and its tests.

Goal: blue is shown as two characters, a Monitor and a Defender. Add per-agent status without changing any existing output key. Monitor groups the sentry (input validation in observe), the detector, and later the correlator and risk assessor. Defender groups the containment and patch proposals and the evidence report. Both are deterministic wrappers over modules that already exist. Do not build clustering, risk scoring, the PACE planner, or armor posture; they are specified, not built (spec Group B).

Make this change:
1. observe() returns an additional key "agents": a list of exactly two entries, agent_id "monitor" and "defender". Each entry is the data payload of a contract agent.status event: agent_id, status, summary. status must be one of the contract's agent_statuses. Derive status deterministically from the observation result (for example completed after a normal run; blocked when a budget is exhausted or the run is cancelled). Document the exact mapping in the module docstring.
2. summary is a fixed template filled only with counts (alerts, proposals, skipped records). It must never contain telemetry text, session references, or any free text from the input.
3. Add the new key to the documented output schema and every place that lists observe's keys, and add tests: status for a normal run, an empty-telemetry run, a cancelled run, and an exhausted budget; summaries contain no input text (use blue_test_helpers.secret_keys); the existing output keys and values are unchanged; the agents list validates against the contract's agent.status required keys.
4. Do not change shared/contracts. Do not add a dependency.

Constraints: standard library only; edit observe.py, add one small module for the agent status logic, add tests under backend/tests/blue/, and update backend/app/agents/blue/README.md. Write the failing tests first. Run the three commands from B-26. Report the files changed, the status mapping you chose, and the exact results. A human must review this change before it is merged.
```

### Any other task

```text
You are working in the RANGE repository on a fresh branch from Mayo, as the blue team engineer. Read first: root AGENTS.md; blue-team/CODEX_HANDOFF.md sections 2, 3, and 7; the task's entry in blue-team/tasks.json (title, notes, context files). Do exactly the task, in the files it names, and nothing else. Write failing tests first and confirm they fail. Follow the rules in section 2 of the handoff; where a rule conflicts with the task, stop and say so. No new dependencies unless you explain them and update the manifests. Run the section 4 commands and report the files changed and the exact results. Label stand-ins, fixtures, and unbuilt behavior honestly. A human must review before merge.
```

## 10. Where things are

| What | Where |
| --- | --- |
| Rules for blue work | root `AGENTS.md`, `blue-team/AGENTS.md`, `shared/contracts/README.md` |
| Background and history | `blue-team/HANDOFF.md`, `blue-team/ROADMAP.md`, `docs/team/04-blue-team-defense.md` |
| Swarm design (approved) | `backend/app/agents/blue/design/swarm-spec.md` |
| Defense actions, patch states, provenance, rollback and reset | `defenses/README.md` |
| Requests for Diego | `blue-team/proposals/contract-v1.1-blue-requests.md` |
| Task board | `blue-team/tasks.json`, `blue-team/CHECKLIST.md` |
| Decisions | `blue-team/decisions/` (0004 response principle, 0005 swarm direction, 0006 B-19, 0007 staged build) |
| Discussion and review records | `blue-team/comms/threads/` (`B-19`, `swarm`, `lane-review`) |
| Working pattern for Codex | `blue-team/CODEX_LANE.md` |
| Availability (outage and recovery) mission sub-tasks, a proposal for Red, core, and arena owners | `blue-team/proposals/red-availability-subtasks.md` |
| The three-model orchestrator (needs Claude, Codex, and Antigravity) | `blue-team/bin/orchestrate.py`, `blue-team/ARCHITECTURE.md` |
