# Arena motion demo — all 14 scenes

Open `RowdyHacks26_Project/arena/motion-proof/index.html` directly and press **Play animated demo**. No server or installation is needed.
The full fixture story runs for 85.5 seconds. The original arena v0 and all approved artwork remain unchanged.

## Controls

- Play / Pause, Replay, numbered scene buttons, timeline scrubber, 0.5× / 1× / 2× speed.
- Space: play/pause. R: replay. 1–9: jump. [ / ]: previous/next scene. Arrow keys: seek one second.
- Reduced motion: still camera, steady emergency light washes, no impact flash or flying debris/spray.
- Leaving the tab pauses playback.
- URL options: `?scene=6&lt=2`, `?t=57`, `?play=1`, `?reduced=1`.

## Motion across the story

| Scene | Motion |
|---|---|
| 01 Driver | Route-light sweep, START glow, dashboard lights, camera push |
| 02 Bank crash | One impact flash, shake, debris, sparks and dust |
| 03 Bank entry | Rain through the doorway, glass glints, slow vault approach |
| 04 Keypad | Website slows, Red fixture feed types, keypad lights, brass glint |
| 05 Outage | Website goes black, alarm beacon/wash, open-vault light, Red check glow |
| 06 Dispatch | Large BANK LAB ALERT, windscreen rain, cabin emergency lights; no Blue code |
| 07 Money | Gold glints, shelf light, dust motes, camera push |
| 08 Exit | Distant cruiser lights and wet-road reflections, rain |
| 09 Rush | Continuous street lighting/weather, foot splash, camera moves toward car |
| 10 Mirror | Police lights in the mirror, glass droplets and cabin vibration |
| 11 Pursuit | Blue fixture code types on the dashboard; rain, lights and camera motion |
| 12 Recovery | Code dissolves into the approved green check, continuous camera/weather |
| 13 Hydroplane | Braking jolt, clipped wheel spray and pole sparks, unchanged check artwork |
| 14 Arrest | Rain, puddles, cruiser lights and a settled ending |

Characters, vehicles and the vault door are part of the approved stills. They do not move independently. This build animates the camera, weather, lighting, particles and displays.

## Implementation

`story.js` snapshots the canonical v0 fixture. `lib.js` supplies deterministic effects; `scenes/sNN_*.js` defines each scene; `engine.js` drives playback.
Scene 12 calls scene 11's hooks with the continued clock instead of duplicating its display geometry and weather.
See `ENGINE_API.md` and `SCENE_BRIEFS.md` for coordinates and authoring guidance.

The website and feeds are local mock content. FIXTURE stays visible. Blue code begins in scene 11; the independent referee stays Not connected.
The website display uses the motion proof's synthetic sign-in/activity layout; it is not a live team website.

## Verification

Codex: **17 automated tests pass** (6 motion checks and 11 v0 regressions). All scenes execute at sampled timestamps in both motion modes. Seek/replay produce identical DOM and canvas commands; the complete timeline, controls, story display states, continuity and error fallback pass.

Run from the workspace root:

```powershell
node --test RowdyHacks26_Project/arena/motion-proof/tests/motion.test.cjs RowdyHacks26_Project/arena/tests/core.test.cjs RowdyHacks26_Project/arena/tests/ui.test.cjs
```

The tests run against an in-memory DOM/canvas, so they do not prove rendered alignment, text wrapping or frame rate. Codex did not run a new browser capture because file:// browser automation was explicitly blocked earlier. Claude's old three-scene rendered checks predate this build.

**Next review:** watch once on the actual demo display; inspect the scene 06 headline and scene 11 code readability, the 11→12 check reveal, and the 13 crash effects. No claim of projector or cross-browser verification.

Current ownership and usage-limit resume instructions: `BUILD_STATUS.md`.
