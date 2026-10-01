# Dashboard design direction

The interface should let a judge understand what is happening and choose the next action without security-tool expertise.

## Character-first direction

Use simple flat 2D character cutouts in a fixed-perspective 3D-style city level. Robber (red team) has a mask, striped shirt, and loot bag; Officer (blue team) has a police cap and badge; Auditor is the neutral independent verifier. The central bank has a raised roof, columns, side wall, and steps. Surround it with connected streets, crosswalks, neighboring buildings, police headquarters, a café, park trees, a getaway van, and a patrol car. Keep characters and service labels readable above the scenery. Scenery is decorative and must never imply additional assessed hosts or security outcomes. The lobby represents the website, the security gate represents the API access boundary, and the vault represents private data. Keep brief event-driven attack/defense effects, character selection, and readable evidence central. Respect reduced motion.

The heist is a presentation theme. Current evidence still comes from the storefront fixture and `/api/orders/{id}`; label that source explicitly. A future bank-record scenario must be coordinated with Members 2 and 3 through the shared contracts. Do not relabel raw evidence as financial transactions or imply that money was actually stolen.

Each character is a native keyboard-accessible button. Clicking it selects the agent and opens a shared inspector beside the scene on desktop and below it on narrow screens. Keep the selection and chosen inspector section stable when new events arrive.

The inspector has three sections:

1. **Overview:** assigned goal, current status/task, latest action, target and version, tools/capabilities, concise decision summary, result, errors, and next planned step when available.
2. **Activity:** complete ordered, paginated history for that agent with timestamps, action input, tool output, duration, retry/failure information, and evidence links. Distinguish system-executed defense actions from the blue agent's proposals.
3. **Evidence:** available sanitized requests/responses, log excerpts, finding or defense IDs, code diffs, patch provenance, and independent verification results. Clearly identify original versus patched target versions.

Present a short summary first and expandable technical details underneath. Missing fields say unavailable rather than being invented. Never expose credentials, hidden model reasoning, hidden evaluation answers during the exercise, or another team's private context. Show concise action/decision summaries instead. The human inspector is a presentation layer; its content must never be copied wholesale into either team's model context.

The current character preview reads the synthetic shared fixture. Its five manual replay checkpoints cover the verified attack, session containment, fresh-session retry, patch application, and independent retest. Overview, Activity, and Evidence reflect only events available at the selected checkpoint. Keep the selected agent and inspector section stable when moving forward, backward, or restarting. Production must support running, waiting, blocked, completed, failed, cancelled, and disconnected views.

- Calm neutral surfaces, clear type hierarchy, generous spacing, and restrained borders.
- Stable red and blue team identities paired with text and icons; never communicate solely through color.
- One primary action per phase: launch, apply defense, retest, then reset.
- A small clickable service map, with labels tied to actual target state.
- A concise chronological activity list. Selecting an entry opens its evidence.
- Separate attempted attacks, verified findings, applied defenses, and verified fixes.
- Show unauthorized and legitimate access results together.
- Hide raw requests and code under a technical-evidence disclosure by default.
- Use keyboard-accessible native controls, visible focus, readable contrast, and responsive stacking.
- Live execution needs a visible stop control and honest waiting, failure, partial, and reconnecting states.

The preview in frontend/preview/index.html demonstrates the virtual arena, a five-move sample battle replay, character selection, and agent inspection. It uses shared/fixtures/demo-run.json and does not establish backend functionality or replace live acceptance tests. The earlier guided dashboard remains at frontend/preview/dashboard.html.

The editable current design source is docs/design/agent-inspector.fragment.html, with the fixture embedded for a standalone preview. The previous design is docs/design/dashboard.fragment.html. Keep embedded data and the rendered export synchronized when changing the fixture; replace the export with the real frontend once implemented.
