# Bank Lab — demo sim v0

## Launch

Open **index.html** in Edge or Chrome. No server, installation, account, or network connection is required. Keep this directory together with fixtures/ and scenes-v2/.

Press **Start demo** below the artwork or click the pictured Start button in scene 01. The complete sequence runs for **85.5 seconds** at 1× speed.

- Pause / Resume preserves your position.
- Previous / Next or the 01–14 buttons jump to a scene and pause for presenting.
- Stop freezes the current scene; Resume continues.
- Reset returns to scene 01.
- Speed offers 0.5×, 1×, and 2×.
- Cinema view uses browser fullscreen when available, otherwise fills the page. Escape exits.
- Keyboard: Space plays/pauses, Left/Right changes scene, R resets (outside native buttons, links and form controls).
- Switching away from the page pauses playback.

## What is included

All 14 approved images in order, with each scene held long enough to explain. Scene 04 shows the synthetic Bank Lab website and a separate animated Red activity screen. Scene 05 uses the approved black website, open vault and Red check image. Scene 06 shows only Blue's alert. Scene 11 begins the Blue recovery feed; scenes 12–13 show its approved completion screen.

Activity text is revealed as each scene plays. Four recent lines fit within the small terminal displays. The bank account is synthetic.

The judge view includes current website availability, Red/Blue status, four selectable agent cards, a public activity inspector, a chronological timeline with team filters, and visible FIXTURE labels. Independent referee remains **Not connected** throughout, including after the arrest.

## Implementation and data boundary

- index.html / styles.css / arena.js: local presenter and screen overlays.
- demo-core.js: deterministic playback state, timing, and fixture validation; no networking or target actions.
- fixtures/session.json: canonical 14-event demo data.
- fixtures/session.js: identical classic-script bundle for direct file opening. This avoids browser fetch restrictions on file URLs.
- scenes-v2/manifest.json: approved image selection.
- archive/pre-v0/: preserved older 8-event prototype files.

The data uses stable event IDs, session IDs, monotonic sequence numbers, source mode, producer, visibility, target ID, evidence references, and typed events. Only the local FIXTURE adapter is connected. The player rejects live/private/mismatched events and any supposed referee verification in this demo.

For later integration, Diego supplies a registered Bank Lab target, validated judge-safe stream, session/control endpoints, and independent referee results. Add a separate source adapter; do not relabel the fixture as live. Map incoming events to approved scenes and use the validated public summaries for the screen surfaces. Checkmarks and narrative events never establish a referee verdict.

When updating the fixture JSON, regenerate the local bundle from the arena directory:

~~~powershell
node -e "const fs=require('fs'); const data=JSON.parse(fs.readFileSync('fixtures/session.json','utf8')); fs.writeFileSync('fixtures/session.js','// Generated local-file bundle of session.json; both carry the same FIXTURE data.\nglobalThis.ARENA_FIXTURE = '+JSON.stringify(data,null,2)+';\n');"
~~~

## Verification

Run from this directory:

~~~powershell
node --check demo-core.js
node --check arena.js
node --test tests/core.test.cjs tests/ui.test.cjs
~~~

Automated checks cover the approved asset selection and bundle parity; full sequence, outage/recovery timing, pause/stop/resume/reset/replay/speed; rejection of private/live/misordered events; delayed Blue code; scene-specific screen visibility; agent selection, timeline filters, cinema fallback, and hidden-page pause.

The UI tests run the actual presenter against an in-memory DOM harness. They validate behavior and bindings, not browser layout. Browser rendering and native fullscreen have not been visually verified in this session because earlier local-file browser automation was denied. Approved raster artwork was inspected during scene review.

## Usage-limit handoff

Read ../../HANDOFF.md, ../../CLAUDE.md, and all ../../_status/ files first. Codex owns arena/ while claims are active. Current work and verification checkpoint are in ../../_status/codex.md. Do not edit another agent's claimed files or use Git mutations unless Omar asks. If usage runs out, record the exact incomplete step and test result before stopping; the next executor is Claude, then Antigravity.
