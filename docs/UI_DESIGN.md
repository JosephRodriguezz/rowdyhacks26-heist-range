# Dashboard design direction

The interface should let a judge understand what is happening and choose the next action without security-tool expertise.

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

The preview in frontend/preview/index.html demonstrates layout and interaction only. Its sample scenario compresses the full planned containment-and-adaptation sequence. It does not establish backend functionality or replace the live acceptance tests.

The editable original design fragment is in docs/design/dashboard.fragment.html. The standalone preview is a rendered export; keep it updated when changing the design source, or replace it with the real frontend once implemented.
