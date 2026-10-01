# Member 1 — Character arena and frontend

## Mission

Make the exercise understandable and fun for a judge who has never used the project. Use flat 2D robber, police officer, and independent auditor characters inside a fixed-perspective 3D-style bank world. The bank is the lab target: lobby = website, security gate = API access control, vault = private data. Preserve clickable character inspection and evidence-based outcomes. The current preview uses a clearly labeled bank-themed storefront fixture; coordinate any future bank-record contract migration with Members 2 and 3.

## Own

`frontend/`, `docs/design/`, `docs/UI_DESIGN.md`, and frontend test/config files. Do not implement agent decisions or infer security verdicts from animations.

## Inputs and outputs

Consume the [shared contract](../../shared/contracts/README.md) and `shared/fixtures/demo-run.json`. Send assessment commands to the backend; receive snapshot, ordered events, and sanitized evidence. No model keys or target credentials belong in the frontend.

Build a small transport adapter with `getSnapshot`, `getEvents`, `subscribe`, and `sendAction`. Implement a fixture transport first and a live API transport second. Both feed the same state reducer and render components.

## Build in order

1. Create the React + TypeScript frontend, preserving the existing static preview as a reference.
2. Build the bank diorama, mapped lobby/gate/vault services, and three selectable 2D characters, following docs/design/agent-inspector.fragment.html. Each character opens the same agent inspector with Overview, Activity, and Evidence sections. Show the task/status, target/version, actions, tool inputs/outputs, observed results, errors, next steps, and evidence when available. Use short summaries with expandable details; never invent missing operational data.
3. Map `agent.status` events onto idle, investigating, executing, blocked, completed, and failed visual states. Do not invent additional successful actions.
4. Implement the five-checkpoint fixture replay shown in the preview, keeping actions and evidence bounded by the selected checkpoint. Animate brief attack and defense effects from events, respecting reduced motion. Show a concise timeline. Selecting an event highlights its target and opens its evidence without losing the current live position.
5. Implement launch, advance, apply proposed defense, stop, and reset. Disable unavailable actions based on the snapshot's `allowed_actions`.
6. Connect the live transport. Recover the snapshot and missing events after reconnect; deduplicate by event ID.
7. Check keyboard navigation, reduced motion, loading/error states, and narrow layouts. Keep an accessible service list alongside the arena.

## Done when

- The complete shared fixture can be explored without a backend or API key.
- Every character is selectable, and every sample evidence reference resolves.
- Switching agents changes the inspector's content without losing the chosen section. The mobile inspector follows the scene, and keyboard users can select agents and navigate sections.
- Activity separates agent proposals from system-executed actions. Evidence includes version and patch provenance; secrets and private reasoning are excluded.
- Red/blue identity is conveyed through labels and shapes as well as color.
- Applying a defense is visually different from verifying a fix.
- Stop, waiting, partial failure, reconnect, and fixture/live labels are clear.
- An integration run uses real backend events with no frontend timers manufacturing verdicts.

## Verification and handoff

Run `python3 scripts/check_handoff.py --self-test`. Add and document `npm run build` and the exact frontend test command when the app exists. Exercise duplicate/reconnected events, stop while running, and evidence selection. Hand Member 2 the API adapter and any contract mismatch; hand the team a working UI run command.

## Starter prompt

> Implement Member 1's work packet in docs/team/01-arena-ui.md. Read AGENTS.md and shared/contracts/README.md first. Own frontend and UI design only. Start with shared/fixtures/demo-run.json and keep fixture/live transports interchangeable. Build a readable character-based arena with evidence panels, keyboard access, and reduced motion. Do not claim live security behavior from fixture data. Coordinate contract changes with Member 2. Deliver a runnable frontend and documented verification commands.
