# Mayo branch checklist

Generated from `tasks.json` by `python blue-team/bin/board.py`. Do not edit by hand.

Last updated 2026-10-03T22:17:00Z by orchestrator.

Progress: 0 in progress · 1 in review · 4 blocked · 14 to do · 6 done

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
- [ ] **B-22** Add the AI advisor layer for Monitor and Defender through a model-call tool supplied by core · milestone ship · owner: unassigned
  - Blocked on B-12: Diego must agree the tools.model_call interface, budgets, and timeouts. The advisor may only rank and explain proposals that deterministic code produced; a labeled deterministic fallback covers model failure. Never a path to execute actions.

## To do

- [ ] **B-07** Stand-in defense executor and an end-to-end blue flow test on the shared fixture · milestone M1 · owner: unassigned
  - Work packet step 6. Codex lane task 3 in blue-team/CODEX_LANE.md; or run through the orchestrator. Suggested implementer: codex.
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
- [ ] **B-20** Tell Joseph which blue work was prepared before the event, so the submission discloses it · milestone swarm · owner: unassigned
  - The event has started (decision 0007), so the pre-built-code gate from decision 0005 is lifted. What remains: the submission draft asks teams to disclose prepared work. Blue's prepared work is everything committed on Mayo before the event start; record the start time and the last commit before it.
- [ ] **B-21** Build the Monitor and Defender agents: per-agent status (agent_id, status, summary) and observe returning an agents list that fits the contract's agent.status event · milestone ship · owner: unassigned
  - Decision 0007, staged scope: deterministic agents only. Monitor = sentry, detector, later the cluster correlator and risk scoring. Defender = containment and patch proposals and the evidence report. No contract change; payloads must carry the v1 required keys. Suggested implementer: claude (isolation-sensitive).
- [ ] **B-23** Fix the incident report so a fix is resolved only when every required retest check passed · milestone ship · owner: unassigned
  - Fable audit items 6, 3, and 7. Codex lane task 1 in blue-team/CODEX_LANE.md; or run through the orchestrator.
- [ ] **B-24** Ship package for core integration: a README for Diego, an example context, a replay script, and a version tag · milestone ship · owner: unassigned
  - After B-21 and B-23. Shows exactly how core calls observe and what comes back.
- [ ] **B-25** Make the patch tests runnable in a read-only sandbox by using committed fixture folders instead of temp folders · milestone ship · owner: unassigned
  - Fable audit item 12. Codex lane task 2 in blue-team/CODEX_LANE.md.

## Done

- [x] **B-01** Telemetry detector for cross-user and anonymous private reads · milestone M1 · owner: claude · commits: 5a06d9d
- [x] **B-02** Session revocation proposals labeled as containment · milestone M1 · owner: claude · commits: df91162
- [x] **B-03** Patch manifest format and ownership patch proposal (patch is a draft) · milestone M1 · owner: claude · commits: 67e0aaf
- [x] **B-04** Incident evidence report: NIST CSF 2.0 sections, ATT&CK/CWE/OWASP mapping, SHA-256 evidence · milestone M1 · owner: claude · commits: 67e0aaf
- [x] **B-06** observe(context, tools) entry point that runs detection, proposals, and the report · milestone M1 · owner: claude · reviewers: antigravity, codex · [thread](comms/threads/B-06.md)
  - Ready to close. The human runs: orchestrate.py close B-06 --commit
- [x] **B-19** Write the blue swarm design spec: cluster rules, scoring weights, PACE triggers by confidence, D3FEND armor scale and heist names, Monitor and Defender grouping, swarm mode · milestone swarm · owner: antigravity · reviewers: claude, codex · [thread](comms/threads/B-19.md)
  - Ready to close. The human runs: orchestrate.py close B-19 --commit
