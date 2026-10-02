# Omar — Arena and judge interface

## Mission

Build a judge-facing interface that makes the live contest understandable: which agents are active, what they are tasked with, what evidence has appeared, how the bank target is behaving, and what the referee concluded.

The starting visual direction is a 3D bank environment with 2D character-like agents. It is a design starting point, not a technology mandate or an unchangeable requirement. Omar may revise the proposed component map below or pitch an alternative visual approach before the team commits. The UI framework, rendering engine, asset style, and state library remain open for Omar to propose.

## Suggested component map — proposal to revise

1. **Arena shell:** contest title, selected scenario, connection/source mode, overall session status, and page layout.
2. **Environment view:** bank/vault scene or Omar’s proposed alternative. Show stable, labeled locations that correspond to real target or team zones.
3. **Agent marker/card:** role, team, status, current task, and a selection control. If characters move or animate, derive changes from actual task/event state.
4. **Agent inspector:** selected agent’s current task, recent handoffs, sanitized evidence references, budget/status, and clear fixture/live labels.
5. **Event timeline:** ordered, filterable, judge-safe events for Red, Blue, target health, and referee outcomes; avoid leaking private boards or hidden answers.
6. **Bank target view:** open or display the registered live lab site, with a clear target/session label and safe navigation boundary.
7. **Session controls:** start, pause, stop, and reset according to the control permissions Diego provides; confirm destructive reset intent in the UI.
8. **Event-source adapter:** fixture data for first UI work, then a live adapter to the agreed core contract. Keep source identity visible throughout.

This is a planning aid. The scene layout and component boundaries can change if the judge workflow stays clear and the integration contract remains stable.

## Before the hackathon

- Review the project brief, architecture, team brief, and arena event contract.
- Sketch the judge journey: start/review a run, inspect an agent, open the bank, follow an event, and understand the referee result.
- Create a rough layout or visual prototype and note accessibility and screen-size needs.
- Decide whether the 3D bank with 2D agents is the best solution after a small feasibility check; present alternatives before locking in a major art or framework investment.
- Confirm which data fields are judge-safe with Diego and each team owner.

## During the event

1. Implement the smallest judge-ready screen against contract-shaped fixtures.
2. Make agent selection, status, timeline, bank target, and session state readable before adding extra scene polish.
3. Connect the live event source after fixture behavior is understood and label all fallback or fixture modes.
4. Add clear loading, disconnected, paused, stopped, and reset states.
5. Test the actual screen on the intended presentation display and keep a keyboard-operable alternative to clicking scene objects.

## Acceptance checks

- A judge can identify each visible agent’s team, role, status, and current task.
- Selecting an agent reveals real task/evidence summaries without exposing the other team’s private board or referee answer key.
- Selecting the bank/vault opens the current registered lab target or gives an equally clear live-target view.
- The event timeline preserves core event ordering and identifies fixture, recorded, and live sources correctly.
- A disconnected or fixture-only view is never presented as live.
- Start, pause, stop, and reset affordances reflect actual core state and permissions.
- Main controls and agent inspection work with keyboard navigation and have readable focus/status cues.
- The arena does not claim that a vulnerability, action, outage, or fix was verified unless the corresponding event/referee evidence supports it.

## Dependencies and handoffs

- Diego supplies session state, registered target metadata, judge-safe events, live target location, and control endpoints.
- Joseph and Aaron supply only the approved agent role labels and safe task/evidence fields.
- The shared contracts define event ordering, source mode, visibility, and stable identifiers.
- Omar owns the visual and component decisions after team review; do not block the arena on model-provider or attack-tool internals.
