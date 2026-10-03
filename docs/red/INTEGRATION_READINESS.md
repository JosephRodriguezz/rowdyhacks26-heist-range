# Red integration readiness

**Status:** Standalone preparation works locally. Core/bank/Blue integration and real-model performance remain unverified. **Owners:** Joseph, Diego, and Aaron.

The Red branch supplies Scout/Operator orchestration, a private evidence/task board, typed proposals, enforced local actions and limits, lesson material, a disposable six-family lab, and independent local evaluation. Its fixture-provider test demonstrates concurrent handoff and response revision; it does not prove a real model can reliably discover or adapt.

The current runner always creates `LabState` and a loopback `LocalBankServer`. The action executor depends on that local state for credentials, redaction, and simulated defense generations; prompts/provider schemas use `bank-local`. It cannot be pointed at Diego's URL as an integration switch. The local board is not yet Diego's canonical task/event store.

## Connections to agree and build

These are implementation review items against the [draft contracts](../INTEGRATION_CONTRACTS.md), not amendments to them.

| Connection | Owner | Acceptance check |
|---|---|---|
| Registered target and capabilities | Diego + Joseph | Core resolves the bank target ID and allowed operations; unknown destinations and redirects cannot escape the registry |
| Identity/session references and reset | Diego + Joseph | Tools own ordinary-account credentials; each contest starts healthy, authorized access works, and old handles cannot enter the reset contest |
| Red action/evidence adapter | Joseph + Diego | Translate typed proposals into core dispatch and responses into bounded sanitized evidence; no dependency on local scenario truth or `LabState` in the agent path |
| Tasks, handoffs, budgets, and cancellation | Joseph + Diego | Core owns canonical session/sequence/state and policy; Scout/Operator ownership works, combined limits hold, and stop prevents new dispatch |
| Blue telemetry and response adapter | Aaron + Diego | Blue sees permitted target observations, takes its bounded responses through the core, and changes actual target behavior; no Red board or referee truth reaches Blue |
| Referee objective | Diego + Joseph | Target-side truth and independent proof distinguish unauthorized vault access from ordinary use, failed requests, and outages |
| Arena projection | Omar + Diego | Judge-safe events disclose evidence progressively and label fixture, recorded, and live activity correctly |

The local `query`, `name`, `message`, `role`, `record_ref`, and `export_ref` fields need capability mapping. Diego may implement equivalent bank behavior with different routes/fields. Red should learn the usable surface from responses; keep endpoint translation in the agreed tool boundary. Start with one access-control contest before adding the other families to the joint test.

Local records also need schema mapping: task `role/description` to agreed `assigned_role/objective`; capability/budget/target/visibility fields validated by core; complete handoff metadata; and core-issued event IDs, actor/target fields, sequence, and source mode. Red-private evidence is not automatically safe for judges. Never forward an entire prototype report: its `evaluation_private` section is referee-only.

## First joint test sequence

1. Reset Diego's bank and verify public health plus normal access using both ordinary account references.
2. With Blue disabled, connect Red through core policy and verify an actual unauthorized access-control effect with independent referee evidence.
3. With the defended counterpart, verify the same unauthorized behavior fails while legitimate access succeeds.
4. Enable Aaron's telemetry and responses. Check detection, applied response, Red's changed observation, and a justified retest or alternative separately.
5. Exercise stop/reset, combined budgets, team isolation, credential redaction, and arena event routing.
6. Measure repeated real-model runs, retaining failures and inconclusive outcomes. Add other agreed families and specialists after this loop is reliable.

Completing a website/API enables the next integration step; it does not by itself satisfy these checks. Simulated defenses are local harness interventions and provide no evidence that Aaron's Blue agents work. The repository documents the broader project as an event build, and the preparation lab remains independently runnable.
