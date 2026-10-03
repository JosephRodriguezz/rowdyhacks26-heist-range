# Codex lane: tasks Aaron can hand to Codex by hand

These are well-bounded blue tasks you can run in Codex yourself while the orchestrator works on B-19 in the main folder. They avoid every file B-19 touches, so nothing collides. Decision 0007 allows this lane.

## The rules of the lane

- **Use a separate clone, never the main folder.** The orchestrator's watcher stops a task if any file in the main folder changes during a run. The clone must be outside OneDrive so its `.git` does not sync.
- **Use Astra:** start Codex with `codex -m gpt-6-astra`.
- **Stay in your task's files.** Do not touch `blue-team/`, the task board, threads, decisions, or state files. Do not edit any `AGENTS.md` or `CLAUDE.md`. Do not touch `backend/app/agents/blue/design/` or `backend/app/agents/blue/README.md` (B-19 owns those).
- **Do not run `orchestrate.py`, `board.py`, or `guard.py install` in the clone.** You are outside the orchestrated workflow; the review below replaces it.
- **Never push.** The work comes back through a local branch that Claude fetches, as described at the end.

## Set up the clone once

```bash
git clone https://github.com/JosephRodriguezz/rowdyhacks26-heist-range.git C:/Users/Aaron/code/RowdyHacks26-codex
cd C:/Users/Aaron/code/RowdyHacks26-codex
git fetch origin Mayo
```

Then, for each task, start a fresh branch from `Mayo`:

```bash
git switch -c codex/b-23 origin/Mayo
```

## Task 1: B-23, fix the incident report's "resolved" logic

Why it matters: the report marks a fix "resolved" after any passed retest, even if a required check is missing or failed. That is a false claim about security. This is the highest-value task.

Files you may edit: `backend/app/agents/blue/incident.py` and `backend/tests/blue/test_blue_incident.py`. Nothing else.

```text
You are working in a clone of the RANGE repository on branch codex/b-23. This is a manual task outside the orchestrated workflow. Read first: backend/app/agents/blue/incident.py, backend/tests/blue/test_blue_incident.py, backend/app/agents/blue/patches.py (REQUIRED_CHECKS), and the "Verification and defense" section of shared/contracts/README.md.

Problem: incident._status() returns "resolved" whenever the last retest of an applied patch has result "passed", without checking its checks.

Make this change:
1. A fix is "resolved" only when the last retest of an applied apply_patch defense has result "passed" AND its checks include every ID in patches.REQUIRED_CHECKS (import it; do not redefine it) AND every check has passed is True AND actual == expected for every check.
2. A "passed" result that fails that test must not be "resolved". It stays "awaiting_retest", and the report's limitations must say which required checks were missing or failed. A "failed" result stays "fix_failed". Existing precedence rules for other statuses stay the same.
3. The existing tests build retests with a single check, so they encode the old weak behavior. Update the test helper so a passing retest includes both required checks. Then add tests that fail on the old code: only one required check present, a check with passed False, a check whose actual differs from expected, extra non-required checks passing (still resolved), a malformed checks list (not resolved), and the full pass (resolved).

Constraints: Python standard library only; no new dependencies; edit only incident.py and test_blue_incident.py; the report must never claim "resolved" on missing evidence. Before you change incident.py, run your new tests and confirm they FAIL on the old code; then fix and confirm they pass. Run: cd backend && python -m unittest discover -s tests/blue, and python scripts/check_handoff.py --self-test from the repo root. Finish with a short report: files changed, what each new test proves, the exact test output, and any risk or limitation. Commit on this branch with a clear message. Do not push.
```

## Task 2: B-25, make the patch tests run in a read-only sandbox

Why it matters: Codex reviews run in a read-only sandbox and cannot create temp folders. One patch test needs one, so Codex never runs it. Committed fixtures remove that.

Files you may edit: `backend/tests/blue/test_blue_patches.py` and new files under `backend/tests/blue/fixtures/patches/`. Nothing else.

```text
You are working in a clone of the RANGE repository on branch codex/b-25. This is a manual task outside the orchestrated workflow. Read first: backend/tests/blue/test_blue_patches.py (the test test_load_refuses_path_tricks_and_mismatches) and backend/app/agents/blue/patches.py (load_patch_manifest, which takes a patches_dir argument).

Problem: that test builds manifests in a temporary directory, so it fails in any read-only sandbox.

Make this change: replace the temporary directory with committed fixture folders under backend/tests/blue/fixtures/patches/<name>/, each containing a manifest.json (and a diff file where needed). Cover the same cases the test covers now: a manifest whose patch_id does not match its folder name, a "ready" manifest whose diff file is missing, and a ready manifest with its diff file present that loads and reports ready. Call load_patch_manifest(name, fixtures_dir) with the committed folder. Keep every other assertion and test unchanged.

Constraints: edit only test_blue_patches.py and add files under backend/tests/blue/fixtures/patches/. Python standard library only. No test in backend/tests/blue may create files after your change (search for tempfile and open(..., "w") to confirm). Prove it: run the whole suite with a read-only working directory if you can, or at least show that nothing in backend/tests/blue writes. Run: cd backend && python -m unittest discover -s tests/blue, and python scripts/check_handoff.py --self-test from the repo root. Finish with a short report: files changed, the cases the fixtures cover, the exact test output, and any limitation. Commit on this branch. Do not push.
```

## Task 3: B-07, a stand-in defense executor and an end-to-end blue flow test

Why it matters: blue proposes, core executes. Until Diego's executor exists, this stand-in lets us prove blue's whole flow end to end and shows what results core must return.

Files you may add: `backend/app/agents/blue/executor_stub.py` and `backend/tests/blue/test_blue_flow.py`. Do not edit existing files.

```text
You are working in a clone of the RANGE repository on branch codex/b-07. This is a manual task outside the orchestrated workflow. Read first: shared/contracts/README.md ("Module boundaries" and "Verification and defense"), shared/contracts/v1.json (defense.proposed, defense.applied, defense.failed), shared/fixtures/demo-run.json, backend/app/agents/blue/observe.py, backend/app/agents/blue/proposals.py, backend/app/agents/blue/patches.py, and docs/team/04-blue-team-defense.md (steps 6 and 7).

Build a stand-in defense executor, a test double for the executor that core will provide:
1. backend/app/agents/blue/executor_stub.py with a class StandInExecutor. apply(proposal_event, ...) takes a defense.proposed-shaped event and returns a defense.applied or defense.failed event-shaped dict (include the contract's required keys; add a field "executor": "stand-in" so it can never be mistaken for the real executor).
   - revoke_session: returns defense.applied with origin "policy_action" and the same version before and after. It remembers which sessions it revoked.
   - apply_patch: refuses any patch whose manifest status is "draft" (load it with load_patch_manifest) and refuses a base_version that does not match the target's current version; otherwise returns defense.applied with the manifest's origin and original and resulting versions (resulting version is a new label such as lab-v2).
   - Failures return defense.failed with required keys defense_id and reason (a short fixed message) plus a "code" field from this set: draft_patch, stale_base_version, unsupported_action, unknown_session, already_applied. Never copy free text from the proposal into a failure reason.
   - It never applies the same defense_id twice (already_applied), and rejects unsupported action types.
2. backend/tests/blue/test_blue_flow.py runs the whole flow on the shared fixture: observe(context built from the fixture telemetry) -> take its revoke_session proposal -> StandInExecutor.apply -> feed the resulting defense.applied back as previous_defenses -> observe again and assert the same session is not proposed again. Then the ownership patch: assert the stand-in REFUSES it while the manifest is a draft (code draft_patch), and that a ready copy of the manifest (built from a committed fixture or in memory, no temp files) is applied. Also test a stale base_version, a duplicate apply, an unsupported action, and that every returned event contains the contract's required keys for its type. Finally assert the incident report from observe never reaches status "resolved" in this flow, because no referee retest is supplied.

Constraints: add only the two new files; do not modify observe.py, proposals.py, patches.py, or any contract file. Python standard library only. Tests must not create files or use temporary directories. Run: cd backend && python -m unittest discover -s tests/blue, and python scripts/check_handoff.py --self-test from the repo root. Prove each new test can fail: temporarily break the executor rule it covers, confirm the test fails, restore it. Finish with a short report: files added, what each test proves, the exact test output, and any limitation. Commit on this branch. Do not push.
```

## When Codex is done

Tell Claude the clone path and the branch name (for example `codex/b-23`). Claude then, between orchestrated runs only:

1. Fetches the branch into the main clone from your local path. This reads your clone and does not touch the team repository.
2. Reads the diff, runs the tests, and checks the files stayed inside the task's scope.
3. Asks Claude and Antigravity for a read-only review round on the merged change (`orchestrate.py discuss`), since the lane skips the usual three-model review.
4. Merges to `Mayo` and updates the task board.

Run tasks in this order of value: Task 1, then Task 2, then Task 3. They do not depend on each other, so they can be separate Codex sessions on separate branches.
