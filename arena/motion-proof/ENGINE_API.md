# Motion demo: how to build a scene

For anyone adding or changing a scene in `arena/motion-proof/`. Tool-agnostic: works for Codex, Claude or Antigravity.
Open `index.html` directly in Edge or Chrome. No server, Node or Python.

## Files

| File | Owner | What it is |
|---|---|---|
| `index.html` | engine | Page, styles, controls, HUD |
| `engine.js` | engine | Player: story, scenes, playback, controls |
| `lib.js` | engine | Shared helpers (`window.MP`) |
| `story.js` | generated | Snapshot of the v0 fixture. Rebuild with `tools/make-story.ps1`. Never hand-edit |
| `scenes/sNN_name.js` | **one per scene** | The only place scene motion lives |
| `tools/` | engine | `snapshot.ps1`, `realtime.ps1`, `measure.ps1`, `crop.ps1`, `imgdiff.ps1`, `make-story.ps1` |

A scene author edits **only their own `scenes/sNN_*.js` files**. If `lib.js` is missing something, write a local helper
inside your scene file. If `lib.js` or the engine has a bug, report it; do not edit them.

## Scene contract

```js
(function () {
  'use strict';
  var MP = window.MP;
  // Build seeded particle emitters here, once.
  MP.register({
    id: 'exit',                         // must match the id in story.js
    setup: function (sc, layer) {},     // once: create glows, screens, keys. Store handles on sc.g
    cam:   function (sc, lt) {},        // each frame: return [scale, tx%, ty%, originX%, originY%]  (use MP.cam({...}))
    dom:   function (sc, lt) {},        // each frame: set opacities, text, transforms on the handles from setup
    draw:  function (sc, lt) {}         // each frame: canvas particles via MP.fx.* (MP.ctx is ready, already cleared)
  });
})();
```

`lt` is seconds into the scene, 0 to `sc.dur`. Every hook is a **pure function of `lt`**. That is what makes seek, replay and
`?t=` snapshots exact. So: no `Math.random`, no `Date`, no state carried between frames (a cached string to skip a DOM write is fine).
A throw inside any hook is caught by the engine: the scene falls back to its still and an error banner appears. Treat that as a failure.

`sc` carries the story: `id n num title label alt file start dur phase actor summary red blue bank alarm redCheck blueCheck
blueCode vaultDoor screen redLines[] blueLines[]`, plus `layer`, `glows[]` and your own `g`.

## Coordinates

The art is 1672 x 941. Measure in pixels, convert:

| You have | You need | Convert |
|---|---|---|
| a point `(px, py)` | glow / box position, % of the stage | `x% = px/1672*100`, `y% = py/941*100` |
| a size in px | glow width/height in `cqw` (1 cqw = 1 % of stage width) | `cqw = px/1672*100` |
| a rectangle | `{left, top, width, height}` for `MP.box` / screens | all in % as above |
| a region | canvas emitters (`MP.fx.*`) | `MP.rectU(left%, top%, right%, bottom%)`; canvas x is 0..1, y is 0..`MP.ASPECT`; in emitter options y ranges are a fraction of height |

Everything inside `layer` is placed in % of the stage and moves with the camera, so overlays stay registered with the art.
Later-created elements sit on top. The particle canvas sits above the whole layer.

## Library (`MP`)

Math: `clamp lerp easeIn easeOut easeInOut smooth(a,b,v) wrap flick(t) pulse(t,hz,duty,soft) rng(seed) skip(r,n) rectU(...)`.
`flick` is a smooth flicker in 0..1, every component under 3 Hz. `pulse` is a soft square wave; **hz is capped at 2.5**.

DOM: `add(parent, class, css)`, `box(layer, rect, class, css)`, `css(key, text)` (inject your scene's CSS once; never edit `index.html`),
`glow(sc, layer, x%, y%, wCqw, hCqw, 'r,g,b')` returns an element, `put(el, opacity, scale)` sets it.
Keep a scene to **16 glows or fewer**; each is a blended layer.

Camera: `MP.cam({push, ease, ox, oy, pan:{x,y}, sway:{ax,ay,fx,fy,py}, shake:{t0,amp,decay,kick,kickDecay}})`. Reduced motion returns a still camera automatically.

Emergency and alarm: `MP.lightbar(sc, layer, {hz, lights:[{x,y,w,h,rgb,phase,max}]})` returns `{update(lt, level)}`.
Colours `MP.RED`, `MP.BLUE`; phase 0 and 0.5 alternate. `MP.beacon(sc, layer, {x,y,w,rgb})` returns `{update(lt, level)}`.

Screens: `MP.siteScreen(layer, rect)` returns `{el, set({ms, spinner, spin, notice, rows[3], pill, glitch, dark})}`.
`MP.codeScreen(layer, rect, {theme:'red'|'blue', title, css, font, color, maxLines})` returns `{el, update(lt, [{t,s}], cps)}`.
Screens that sit on a tilted display need CSS: pass `css` (for example `transform:skewY(2.4deg)`) or build your own with `MP.box`.

Canvas emitters, built once in the file body or `setup`, drawn from `draw`. Pass `rng` (a shared stream) or `seed`:
`MP.fx.debris(o).draw(tp)`, `.dust(o).draw(tp)`, `.sparks(o).draw(tp)`, `.splash(o).draw(tp)` take time since the event;
`.rain(o).draw(lt, mul)`, `.glints(o).draw(lt)`, `.motes(o).draw(lt)`, `.ripples(o).draw(lt)` take scene time.
Options are documented at the top of each function in `lib.js`. Budget: **about 140 canvas particles per scene or fewer**.

## Measuring the art

```powershell
# where is the screen glass? probe its colour first, then grow from a point inside it
tools\measure.ps1 -Image ..\scenes-v2\11_blue_pursuit.png -Probe "1250,700"
tools\measure.ps1 -Image ..\scenes-v2\11_blue_pursuit.png -Mode color -R 28 -G 36 -B 56 -Tol 25 -SeedX 1250 -SeedY 700 -X0 860 -Y0 560 -X1 1660 -Y1 880
# where is a lamp or light bar? bright pixels in a window you chose
tools\measure.ps1 -Image ..\scenes-v2\08_bank_exit.png -Mode bright -Threshold 200 -X0 100 -Y0 450 -X1 330 -Y1 600
```

`-Mode dark` also matches bezels and shadows, so its box is too big for screens. Use the colour probe plus a seed.
Confirm every measurement with a snapshot and `tools\crop.ps1`.

## Checking your scene

```powershell
# frames at moments in the scene (scene number 1-14, lt in seconds into the scene)
tools\snapshot.ps1 -Scene 8 -Lt 0.2,1.5,3.0,4.3 -OutDir <your folder> -Prefix exit
tools\snapshot.ps1 -Scene 8 -Lt 2.0 -Reduced -OutDir <your folder> -Prefix exit     # reduced motion
tools\snapshot.ps1 -Scene 8 -Lt 1.5,3.0 -Twice -OutDir <your folder>               # prints deterministic:True/False
tools\crop.ps1 -In <png> -X 700 -Y 120 -W 500 -H 300 -Scale 2 -Out <zoom.png>      # inspect a detail
tools\realtime.ps1 -Speed 4 -OutDir <your folder>                                  # whole demo in real time, reports console errors
```

Then **look at every frame** with the image viewer. A snapshot that returned without errors is not a checked scene.
Scene start times (global seconds, for `-T`): 01 0.0, 02 3.0, 03 7.5, 04 12.5, 05 24.5, 06 31.0, 07 37.5, 08 42.0,
09 46.5, 10 50.5, 11 55.0, 12 68.0, 13 74.5, 14 79.0, end 85.5.

## Rules

**Story (from the v0 fixture, shown in the HUD):**

| Scene | Bank site | Alarm | Blue | Blue feed | Note |
|---|---|---|---|---|---|
| 01 to 04 | ONLINE | off | Standby | none | Scene 04: site slows down but stays up |
| 05 | OFFLINE | **ON** | Alert pending | none | Website goes dark, vault open |
| 06 | OFFLINE | **ON** | Alert received | none | Alert only. No recovery code yet |
| 07 to 10 | OFFLINE | off | Responding, Approaching, Arriving, Following | none | |
| 11 | RECOVERING | off | Recovery action applied | **starts** | Blue feed types |
| 12 | ONLINE | off | Demo action complete | yes | Display switches to the green check |
| 13, 14 | ONLINE | off | Stopping, Story complete | yes | |

- No alarm beacon, red alarm wash or siren before 05 or after 06.
- **No police or emergency lights flashing before scene 06.** The cruiser and light glow baked into scenes 01 and 02 stay as they are.
- The Blue feed does not appear before 11.
- Never show text that claims something was verified, secured, patched or confirmed. Referee is always "Not connected".
  Text on screens comes from `sc.redLines` / `sc.blueLines` or from constants you write that match the fixture's wording.
- Characters and cars are baked into the stills. Never imply they move on their own. Light, camera, particles and screens move.

**Flash safety:**
- Anything that alternates or pulses must be at most 2.5 cycles per second. `MP.pulse` and `MP.lightbar` enforce it; if you write your own, enforce it too.
- No sudden full-frame brightness change except one impact flash, once, shorter than 0.4 s.
- Keep emergency-light glow opacity at 0.6 or less and avoid large saturated areas.

**Reduced motion** (`MP.reduced`, set by the checkbox and by the OS setting):
- No camera movement (`MP.cam` handles it), no flashing or alternating lights (`MP.lightbar` shows a steady dim wash), no flying particles.
- Slow, small things (breathing glows, soft rain at 40 %) are fine. Typed text is content, keep it.

**Quality:**
- Match the style of `scenes/s02_crash.js` to `s04_vault.js`: a header comment saying what moves, what does not, and what was deliberately not animated; measured geometry noted in the header; short comments only where something is not obvious.
- Do not invent story. If the art is silent about something, leave it still.

## Checklist before you call a scene done

1. File registers the right `id`; no console errors in any snapshot (`page-errors:0`).
2. Looked at frames near the start, middle and end, plus a reduced-motion frame, and they look right.
3. Every screen or light overlay is registered with the art (zoomed crop checked).
4. `-Twice` reports `deterministic:True`.
5. Every alternating or pulsing element is listed with its rate and is at most 2.5 Hz.
6. Particle count and glow count within budget.
7. Story rules above hold for this scene (bank, alarm, Blue, feed, no early police lights).
8. Nothing in the scene claims verification.
9. **Omar's two explicit asks, checked by looking at a 1500 px-wide frame:** scene 06 shows a BIG alert on the police car's display (headline dominant, readable across a room); scene 11 shows the Blue team's code typing on the dashboard display in the same style as the Red code in scene 04, large enough to read comfortably. See the notes under scenes 06 and 11 in `SCENE_BRIEFS.md`.
