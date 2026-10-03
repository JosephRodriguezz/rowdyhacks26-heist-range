# Mayo branch checklist

Generated from `tasks.json` by `python blue-team/bin/board.py`. Do not edit by hand.

Last updated 2026-10-03T22:34:08Z by claude.

Progress: 0 in progress · 1 in review · 5 blocked · 17 to do · 10 done

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
- [ ] **B-33** Blue availability signal: telemetry fields and a detector for load and outage, with reversible responses · milestone ship · owner: unassigned
  - From the availability sub-tasks (blue-team/proposals/red-availability-subtasks.md, AV-08). Blocked until the team decides to attempt the availability mission (AV-01), Gate 5 passes, and B-12 answers. Blue detects only cross-user and anonymous private reads today. Any new response action is a contract change and human-gated.

## To do

- [ ] **B-08** Structured outcomes for rejected, failed, and rolled-back defenses; request a referee retest · milestone M1 · owner: unassigned
  - Work packet step 7. Suggested implementer: codex.
- [ ] **B-09** Detect repeated denied cross-user reads by one session (probing) · milestone M1 · owner: unassigned
  - From the report's prevention step detect-probing.
- [ ] **B-10** Blue tests for executor failure, stale patch version at apply time, and rejected proposals · milestone M1 · owner: unassigned
  - Work packet test list. Suggested implementer: codex. Partly covered by merged lane work: F1 adversarial tests and F2 mutation-gap tests (malformed input, oversize, nested) and B-07 flow tests (stale patch, draft refusal, duplicate defense). Still open: telemetry flood and circuit-breaker queue (gated on B-12), executor failure ingestion with B-08.
- [ ] **B-12** Send Diego the interface requests: observe input names and access_policy shape, new actions and events, windowed telemetry, hashed client_ref, login telemetry, canary records and decoy endpoint, refusal of draft patches · milestone M2 · owner: unassigned
  - The requests are drafted and merged (lane F4): blue-team/proposals/contract-v1.1-blue-requests.md, reconciled with the approved B-19 spec section 10.2. NOT yet sent to Diego; a person must send it and collect answers (section 10 of that file lists his questions). Two earlier handoff messages are unanswered.
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
- [ ] **B-24** Ship package for core integration: a README for Diego, an example context, a replay script, and a version tag · milestone ship · owner: unassigned
  - After B-21 and B-23 (B-23 is merged). Shows exactly how core calls observe and what comes back.
- [ ] **B-26** Fix the date-only timestamp crash: parse_utc_timestamp must reject date-only values so one bad record cannot crash detection, observe, or the report · milestone ship · owner: unassigned
  - Medium bug found by lane F1 (reproduced and confirmed by an independent review). detection.parse_utc_timestamp('2026-09-30Z') returns a naive datetime, then comparisons raise TypeError (detection.py:91, observe.py:373, incident.py:362). Return None so the record is skipped; make a bad generated_at a ContextError. Remove the 4 expectedFailure decorators in backend/tests/blue/test_blue_adversarial.py without editing assertions. Prompt: blue-team/CODEX_HANDOFF.md section 9.
- [ ] **B-27** Reject NaN budgets and make unhashable values raise ContextError or PatchManifestError instead of TypeError · milestone ship · owner: unassigned
  - Low bugs found by lane F1 (confirmed by an independent review). observe._budgets accepts NaN so a NaN budget runs as completed (observe.py:267,115); unhashable values crash membership tests in observe.py (87,218,229,246) and patches.py (77,78,96). Remove the 3 remaining expectedFailure decorators. Prompt: blue-team/CODEX_HANDOFF.md section 9.
- [ ] **B-28** Make the human gate honest: record delegated approvals truthfully, refuse human-only commands inside model runs, and ratify the B-06 overrides · milestone ongoing · owner: unassigned
  - Fable audit finding 16, P0 for the framework. approve, resolve, close --commit, and decide --human-approve are plain CLI calls; B-06 attempts 4 and 5 were approved by Claude under standing authorization but recorded by: human (sm.approve_implementation hard-codes it). Fix: record delegated-by-human, set an env flag in adapters that human-only commands refuse, and write a decision record ratifying the B-06 overrides. A plain TTY check would stop delegated approvals. Needs the three-model setup; not for a Codex-only owner.
- [ ] **B-29** Fix the two incident.py gaps found in review and the Fable audit report items · milestone ship · owner: unassigned
  - Reproduced 2026-10-03 (independent review). (1) With two applied patches, status follows the last retest of any patch, so a second patch never retested still shows resolved. (2) times.fix_verified keeps an earlier passed retest timestamp after a later failed retest although status is fix_failed. Also Fable audit 3 and 7: ACCEPTANCE_CHECKS (five) versus REQUIRED_CHECKS (two), the weaker second path in report.py, and the containment-time rule location. One shared required-check list needs a contract change through Diego. Repro: blue-team/CODEX_HANDOFF.md section 7.
- [ ] **B-30** Ask Diego to run backend/tests/blue and blue-team/tests in CI · milestone M2 · owner: unassigned
  - Fable audit finding 14. CI runs only the handoff check, the preview check, and a HEAD patch check. A request to a teammate; do not edit .github/ directly.
- [ ] **B-31** Report team-owned file issues to their owners · milestone M2 · owner: unassigned
  - Fable audit findings 1, 11, 13, 15. Roster duplication (docs/team and docs/weekend versus blue-team) to Joseph; empty __init__.py and pyproject bootstrap files to Diego; scripts/doctor.py crashes on Windows (npm.CMD) to Diego; no root .gitattributes (git warns about LF and CRLF) to Joseph. Reports only; do not edit those files.
- [ ] **B-32** Framework hygiene from the Fable audit · milestone ongoing · owner: unassigned
  - Findings 17-21: document that a human resolve revise overrides max_revisions; stop the facilitator implementing the same task it facilitates; require one reviewer who ran tests for backend/ changes; run B-05 through its own review; smaller items (8 and 21 were kept only as titles; ask Aaron for the original audit). Needs the three-model setup.

## Done

- [x] **B-01** Telemetry detector for cross-user and anonymous private reads · milestone M1 · owner: claude · commits: 5a06d9d
- [x] **B-02** Session revocation proposals labeled as containment · milestone M1 · owner: claude · commits: df91162
- [x] **B-03** Patch manifest format and ownership patch proposal (patch is a draft) · milestone M1 · owner: claude · commits: 67e0aaf
- [x] **B-04** Incident evidence report: NIST CSF 2.0 sections, ATT&CK/CWE/OWASP mapping, SHA-256 evidence · milestone M1 · owner: claude · commits: 67e0aaf
- [x] **B-06** observe(context, tools) entry point that runs detection, proposals, and the report · milestone M1 · owner: claude · reviewers: antigravity, codex · [thread](comms/threads/B-06.md)
  - Ready to close. The human runs: orchestrate.py close B-06 --commit
- [x] **B-07** Stand-in defense executor and an end-to-end blue flow test on the shared fixture · milestone M1 · owner: unassigned · reviewers: claude, antigravity · commits: 02b3fdf
  - Merged from the Codex lane (48cd7f0): executor_stub.py (StandInExecutor, a test double marked executor: stand-in, never core's executor) and test_blue_flow.py. Reviewed by Claude and independently by Antigravity (lane-review thread). Not a lab adapter; core's real executor is still not built.
- [x] **B-11** Document supported defense actions, rollback, and reset behavior · milestone M1 · owner: unassigned · reviewers: claude, antigravity · commits: 90c4962
  - Written by Cursor lane F3 (defenses/README.md), merged 90c4962, then corrected for the stand-in executor and the final B-19 spec. Every cited identifier was checked in code and Antigravity checked each factual claim independently (lane-review thread, no findings).
- [x] **B-19** Write the blue swarm design spec: cluster rules, scoring weights, PACE triggers by confidence, D3FEND armor scale and heist names, Monitor and Defender grouping, swarm mode · milestone swarm · owner: antigravity · reviewers: claude, codex · [thread](comms/threads/B-19.md)
  - Ready to close. The human runs: orchestrate.py close B-19 --commit
- [x] **B-23** Fix the incident report so a fix is resolved only when every required retest check passed · milestone ship · owner: unassigned · reviewers: claude, antigravity · commits: 212758d
  - Merged from the Codex lane (90f6ad3). A passed retest now resolves an incident only when every REQUIRED_CHECKS entry is present, passed, and actual equals expected; otherwise awaiting_retest with the missing checks named. Verified by blue tests (233 pass), a Claude diff review, and an independent Antigravity read-only review (blue-team/comms/threads/lane-review.md), which found two low edge cases now tracked as B-29.
- [x] **B-25** Make the patch tests runnable in a read-only sandbox by using committed fixture folders instead of temp folders · milestone ship · owner: unassigned · reviewers: claude, antigravity · commits: c1b996e
  - Merged from the Codex lane (e815426). Patch tests use committed fixture folders and create no files. Reviewed by Claude and independently by Antigravity (lane-review thread, no findings).
