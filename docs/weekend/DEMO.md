# Judge walkthrough and rehearsal

Target rehearsal: three minutes, adjustable to the organizer's actual format. This script describes the desired live product, not capabilities already built.

## Story

**0:00–0:20 — The premise.** “This city represents an isolated application. Robbers test its security, cops defend it, and an independent auditor verifies what actually happened. Click a character to see its actions and evidence.” State whether this run is live, recorded, or a fixture.

**0:20–0:55 — The break-in.** Launch the registered lab. Select the robber. Show the candidate request and independent proof that Alice can read Bob's private record. Explain that the bank vault represents private data; the current scenario uses lab orders, not real money.

**0:55–1:30 — The response.** Select the officer. Show the suspicious-access telemetry and session-revocation proposal, then the system's actual execution result. Advance to the fresh-session retry: the original access-control flaw remains.

**1:30–2:15 — The repair.** Apply the scoped ownership patch to a disposable target. Show patch origin and version. Select the auditor: unauthorized access is denied and the legitimate owner's access still succeeds. Blocking everyone is not a successful defense.

**2:15–2:40 — Why trust it.** Show one sanitized evidence record, separate team observations, request budgets, and the registered target boundary. AI chooses bounded actions; the verifier checks the outcome independently.

**2:40–3:00 — Close.** Reset cleanly. Explain the single-scenario scope and one next step. Avoid claiming general security coverage or autonomous patch generation if a known-good patch was used.

## Rehearsal checklist

- [ ] Record commit SHA, runtime versions, provider/model, and startup/reset/test commands.
- [ ] Run the [live gate](../team/INTEGRATION.md) twice from a clean state on the actual demo laptop.
- [ ] Verify stop, reconnect, reset, owner access, unauthorized access, unauthenticated access, and protected controls.
- [ ] Open the city and evidence panels before judging; hide credentials and unrelated personal tabs.
- [ ] Prepare a clearly labeled recording of a known-good run if permitted; don't substitute the synthetic preview silently.
- [ ] Capture three visuals: city overview, containment bypass, and independent before/after checks.
- [ ] Confirm repository visibility, submission URL, team names, acknowledgements, and prebuilt-work disclosure.
- [ ] Joseph presents; Diego explains red; Omar explains defense; Aaron explains verification and integration. Swap according to comfort.

## Submission draft

**Name:** RANGE — The Heist

**One sentence:** An interactive cyber range where AI robbers and cops test and defend an isolated application, with independent evidence showing whether the defense really worked.

**Problem:** Agent security demos can make attacks and fixes look convincing without proving either claim.

**Approach:** Bounded red/blue agents, a bank-themed city interface, separate observations, and an independent policy verifier that checks both unauthorized and legitimate access.

**Built during the event:** Fill in actual implemented modules and results at H21.

**Prepared beforehand:** Design prototypes, specifications, shared fixture/contracts, work packets, and starter tooling in the preserved repository history. Follow organizer disclosure requirements.

**Limitations:** One ownership scenario; disclose fixture/recorded/scripted behavior, fallback patches, missing controls, or incomplete integrations honestly.
