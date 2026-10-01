# Mayo branch checklist

Generated from `tasks.json` by `python blue-team/bin/board.py`. Do not edit by hand.

Last updated 2026-10-01T20:18:54Z by orchestrator.

Progress: 0 in progress · 1 in review · 3 blocked · 9 to do · 5 done

## In progress

None.

## In review

- [ ] **B-05** Multi-model framework: deterministic orchestrator, adapters, state machine, guardrails · milestone M1 · owner: claude
  - Migrated to Claude, Codex, and Antigravity with a deterministic state machine (decision 0002). Codex and Antigravity review it in their first orchestrated round.

## Blocked

- [ ] **B-13** Finalize ownership-fix-001: allowed_files and diff against Member 3's order handler · milestone M2 · owner: unassigned
  - Waiting on Member 3 to publish the lab's order handler.
- [ ] **B-16** Update Mayo from main after PR #1 merges, then open the blue-team pull request · milestone M2 · owner: human
  - Waiting on PR #1. Merging from main is a human step.
- [ ] **B-17** Run blue against the live lab from a clean reset and produce a live incident report · milestone M3 · owner: unassigned
  - Waiting on the lab (Member 3) and core (Member 2).

## To do

- [ ] **B-07** Stand-in defense executor and an end-to-end blue flow test on the shared fixture · milestone M1 · owner: unassigned
  - Work packet step 6. Suggested implementer: codex.
- [ ] **B-08** Structured outcomes for rejected, failed, and rolled-back defenses; request a referee retest · milestone M1 · owner: unassigned
  - Work packet step 7. Suggested implementer: codex.
- [ ] **B-09** Detect repeated denied cross-user reads by one session (probing) · milestone M1 · owner: unassigned
  - From the report's prevention step detect-probing.
- [ ] **B-10** Blue tests for executor failure, stale patch version at apply time, and rejected proposals · milestone M1 · owner: unassigned
  - Work packet test list. Suggested implementer: codex.
- [ ] **B-11** Document supported defense actions, rollback, and reset behavior · milestone M1 · owner: unassigned
  - Work packet step 8. Suggested implementer: antigravity.
- [ ] **B-12** Contract proposals for Member 2: blue context, previous_defenses format, executor results, report endpoint, refusing draft patches · milestone M2 · owner: unassigned
  - Draft in the handoffs thread. Suggested: antigravity drafts, claude reviews.
- [ ] **B-14** Plain-language alert and defense labels for Member 1's UI · milestone M2 · owner: unassigned
  - Suggested implementer: antigravity.
- [ ] **B-15** Cross-branch review of blue code against other members' latest branches and the shared contract · milestone M2 · owner: unassigned
  - Repeat each time a teammate pushes. Suggested: antigravity.
- [ ] **B-18** Strategy review: more secure, more efficient, more effective blue work across the project · milestone ongoing · owner: unassigned
  - Run orchestrate.py strategy at least once per milestone.

## Done

- [x] **B-01** Telemetry detector for cross-user and anonymous private reads · milestone M1 · owner: claude · commits: 5a06d9d
- [x] **B-02** Session revocation proposals labeled as containment · milestone M1 · owner: claude · commits: df91162
- [x] **B-03** Patch manifest format and ownership patch proposal (patch is a draft) · milestone M1 · owner: claude · commits: 67e0aaf
- [x] **B-04** Incident evidence report: NIST CSF 2.0 sections, ATT&CK/CWE/OWASP mapping, SHA-256 evidence · milestone M1 · owner: claude · commits: 67e0aaf
- [x] **B-06** observe(context, tools) entry point that runs detection, proposals, and the report · milestone M1 · owner: claude · reviewers: antigravity, codex · [thread](comms/threads/B-06.md)
  - Ready to close. The human runs: orchestrate.py close B-06 --commit
