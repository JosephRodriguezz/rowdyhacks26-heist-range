# Mayo branch checklist

Generated from `tasks.json` by `python blue-team/bin/board.py`. Do not edit by hand.

Last updated 2026-10-02T23:37:18Z by human.

Progress: 0 in progress · 1 in review · 3 blocked · 11 to do · 5 done

## In progress

None.

## In review

- [ ] **B-05** Multi-model framework: deterministic orchestrator, adapters, state machine, guardrails · milestone M1 · owner: claude
  - Migrated to Claude, Codex, and Antigravity with a deterministic state machine (decision 0002). Codex and Antigravity review it in their first orchestrated round.

## Blocked

- [ ] **B-13** Finalize ownership-fix-001: allowed_files and diff against Diego's order handler · milestone M2 · owner: unassigned
  - Waiting on Diego (core and bank lab) to publish the lab's order handler.
- [ ] **B-16** Join Mayo into the new repository's main, once the team decides how · milestone M2 · owner: human
  - On hold by decision of Member 4 (2026-10-02). Mayo and the new main share no history, so a pull request needs a merge of unrelated histories first. Joseph owns main; agree what to bring in (all of Mayo or only blue's folders) before doing it.
- [ ] **B-17** Run blue against the live lab from a clean reset and produce a live incident report · milestone M3 · owner: unassigned
  - Waiting on Diego's lab and core.

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
- [ ] **B-12** Send Diego the interface requests: observe input names and access_policy shape, new actions and events, windowed telemetry, hashed client_ref, login telemetry, canary records and decoy endpoint, refusal of draft patches · milestone M2 · owner: unassigned
  - Decision 0005 and the swarm thread define the swarm items. Contingency and Emergency tiers need new action types; cluster, PACE tier, and posture need new events. Draft in the handoffs thread. Suggested: antigravity drafts, claude reviews.
- [ ] **B-14** Give Omar blue's arena data and labels: heist names for the seven D3FEND armor slots, plain-language alerts and defenses, status for two blue characters (swarm mode later) · milestone M2 · owner: unassigned
  - Decision 0005: armor credit follows proven state and is shown per attack path plus an overall number. Suggested implementer: antigravity.
- [ ] **B-15** Cross-branch review of blue code against other members' latest branches and the shared contract · milestone M2 · owner: unassigned
  - Repeat each time a teammate pushes. Suggested: antigravity.
- [ ] **B-18** Strategy review: more secure, more efficient, more effective blue work across the project · milestone ongoing · owner: unassigned
  - Run orchestrate.py strategy at least once per milestone.
- [ ] **B-19** Write the blue swarm design spec: cluster rules, scoring weights, PACE triggers by confidence, D3FEND armor scale and heist names, Monitor and Defender grouping, swarm mode · milestone swarm · owner: unassigned
  - Design only: no code and no contract changes. Deliverable: backend/app/agents/blue/design/swarm-spec.md. Build tasks come from the spec. Suggested: antigravity drafts the standards research, claude reviews isolation and safeguards, codex reviews testability.
- [ ] **B-20** Ask Joseph to confirm the organizer's rules on pre-built code, AI tools, and public repositories before more blue code is written · milestone swarm · owner: unassigned
  - Decision 0005 (timing): design now, check the rules, then build. The new repo's kickoff decisions list this as pending an organizer check. Blue's existing code and the swarm prototypes would be disclosed as prepared work.

## Done

- [x] **B-01** Telemetry detector for cross-user and anonymous private reads · milestone M1 · owner: claude · commits: 5a06d9d
- [x] **B-02** Session revocation proposals labeled as containment · milestone M1 · owner: claude · commits: df91162
- [x] **B-03** Patch manifest format and ownership patch proposal (patch is a draft) · milestone M1 · owner: claude · commits: 67e0aaf
- [x] **B-04** Incident evidence report: NIST CSF 2.0 sections, ATT&CK/CWE/OWASP mapping, SHA-256 evidence · milestone M1 · owner: claude · commits: 67e0aaf
- [x] **B-06** observe(context, tools) entry point that runs detection, proposals, and the report · milestone M1 · owner: claude · reviewers: antigravity, codex · [thread](comms/threads/B-06.md)
  - Ready to close. The human runs: orchestrate.py close B-06 --commit
