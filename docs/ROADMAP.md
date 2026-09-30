# Implementation roadmap

- [x] Capture the project direction, safety boundaries, and UI requirements.
- [x] Preserve the interactive sample-data dashboard preview.
- [x] Create four work packets, ownership boundaries, shared handoff vocabulary, and validated fixtures.
- [ ] Build the lab, seed/reset command, ownership policy, and deterministic regression checks.
- [ ] Define typed API/event contracts and a server-owned target registry.
- [ ] Implement bounded tools, SQLite persistence, assessment phases, and cancellation.
- [ ] Implement red's bounded observe/test/adapt loop and independent verification.
- [ ] Connect the dashboard to actual persisted events and SSE.
- [ ] Implement telemetry-driven blue detection and scoped session revocation.
- [ ] Apply a reviewable ownership fix to a disposable target and run both regression checks.
- [ ] Add scenario-scoped evaluation, exact patch provenance, and partial-failure reporting.
- [ ] Package with Docker Compose; verify reset, reconnection, cancellation, and a complete guided demo.
- [ ] Add autonomous rounds once guided execution is reliable.

## Gate before stretch work

Run the whole scenario from a clean state without manually editing app data: find, prove, detect, defend, adapt, fix, retest. UI outcomes must reflect real execution.

## Stretch goals

Additional injection scenarios, multi-host networks, richer defenses, generated-patch automation, attack graphs, and recorded replay. Do not trade away a reliable primary scenario for more agent cards.
