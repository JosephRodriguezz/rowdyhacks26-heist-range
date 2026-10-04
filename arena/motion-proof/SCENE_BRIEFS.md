# Scene briefs

Direction for each scene in the 14-scene motion demo. Read `ENGINE_API.md` first (contract, library, rules, checklist).
Pixel coordinates are read by eye off the 1672 x 941 art and are **approximate**: measure with `tools/measure.ps1` and confirm
with a snapshot and a crop before relying on them. Story states (bank, alarm, Blue) come from the v0 fixture via `story.js`.

## Shared look

Night, wet, glossy city. The same small vocabulary in every scene so the demo reads as one piece:

- **Lamps** breathe with `MP.flick` (gentle, never a blink). **Rain** (`MP.fx.rain`) is light to moderate; **ripples** (`MP.fx.ripples`) on wet ground.
- **Camera**: a slow push of 3 to 8 % plus a small handheld sway. Shake only on a real impact (scenes 02 and 13).
- **Emergency lights** only through `MP.lightbar` (alternating red/blue, about 2.2 Hz, soft edges). They fade in and out with `level`.
- **Screens** type at 30 characters per second. Text is calm, small and honest.
- Continuity: a scene's first moment should look like the last moment of the scene before it.

Do not animate characters or cars as objects. Do not add elements the art does not show.

---

## 01 driver (3.0 s) `01_driver_start.png`
HUD: bank ONLINE, alarm off, Blue Standby, Red Ready. This is the opening: the viewer presses Play over a still of this scene.
Art: Red at the wheel; a tablet (x 590-1045, y 480-815) with a glowing red route line and a red **START** button (centre about 845,708);
the lit bank ahead (880-1215, 190-480); wet street; rear-view mirror (1145-1620, 70-210); red dash LED strips (1105-1325, 727-742) and (1550-1672, 715-775);
street lamps at about (558,115) (667,330) (1350,340) (1455,290) (1645,245); white car on the left with headlights (580,495).
Ideas: a soft START button pulse (about 1 Hz) that says "go"; the route line gently shimmering or marching toward the bank icon
(path roughly 712,715 to 735,625 to 860,622 to 866,568 to 880,548); dash LEDs breathing; lamp flicker; bank facade lights breathing;
a slow, calm push toward the bank (about 3 %, origin near 58,46). Gentle ease-in so the first frame matches the still.
**Do not animate** the police cruiser at the far right (about 1470-1670, 445-555): Blue is on standby and no emergency lights flash before scene 06.

## 05 alarm (6.5 s) `05_open_vault_matched-r3.png`
HUD: bank OFFLINE, alarm **ON**, Red "Demo action complete", Blue Alert pending.
Art: the vault door is now open (gold shelves inside, x 300-660, y 150-610); the large display is **black**; the small display shows a green check
(centre about 1428,590, display x 1290-1568, y 515-668); a red beacon lamp is lit at the top (about 1125, 25-50); the robber at the keypad.
**Continuity with scene 04:** scene 04 ends with the website slow (about 4 s response, spinner and "Slow response" line up, rows dimmed, pill ONLINE).
Scene 05 should *begin* with an `MP.siteScreen` over the same glass (left 49.1, top 10.1, width 45.9, height 37.8; measure the black glass in this image to confirm) showing exactly that last state,
then within about 0.2 to 0.9 s: a short horizontal tear (`glitch`, under 0.5 s), the pill flips to OFFLINE, then it fades to black (`dark` to 1) and the overlay hides,
revealing the art's own black screen. This is the story beat "Bank Lab goes dark".
Also: `MP.beacon` on the lamp (smooth sweep, under one turn per second); a faint red wash on the wall at 1.1 Hz or slower and low opacity;
warm light spill from the open vault with a few gold glints; one soft green pulse on the check around 1.0 s; slow push toward the vault.
Keep the room's red wash smooth and below 0.2 opacity: this is an alarm, not a strobe.

## 06 dispatch (6.5 s) `06_car_orientation-r9.png`
HUD: bank OFFLINE, alarm ON, Blue "Alert received", active agent Blue Monitor. **Alert only: no recovery code yet.**
Art: Blue's cabin at night, blue light wash at the top left (about 330,30) and in the mirror (750-1260, 0-130); a large dark dashboard display (roughly x 810-1395, y 450-790, tilted: measure its four corners);
the wet avenue ahead with the bank (about 990,280) and the red hatchback far away (about 1055,348); rain drops on the windscreen and side mirror (0-100, 380-540).
Overlay the v0 wording on the display, tilted to match its perspective: `BLUE DISPATCH · FIXTURE` / `⚠ BANK LAB ALERT` / `Website unavailable` / a thin rule / `Respond to Bank Lab` / `Recovery team on standby`.
Animation: the display wakes (dark, one short stutter, then text types in); the alert line pulses softly (at most 1 Hz); a warm-red edge glow on the display;
`MP.lightbar` blue-led, rising from low to normal after about 1.2 s as the team responds (the art already has a blue wash, so start dim); rain on the windscreen (`fx.rain` over the glass region) and drops on the side mirror;
wet road reflections breathing; light sway as if idling; slow push toward the road ahead.

**Omar's explicit request (this scene): the alert must be BIG.** A viewer should read `⚠ BANK LAB ALERT` from across the room. Make that headline the dominant element of the display: bold, filling most of the glass's width (roughly 2.6 to 3.2 cqw type, sized to fit the measured glass), with a large ⚠ mark and a pulsing red border or glow (soft, at most 1 Hz). The v0 sub-lines stay, but smaller, beneath it. Check legibility in a normal 1500 px window, not only zoomed in. If it looks like small grey text, it is not done.

## 07 money (4.5 s) `07_inside_vault_money-r2.png`
HUD: bank OFFLINE, alarm off, Blue Responding, active agent Story.
Art: a vault chamber lined with gold bars and cash; the robber crouches filling a cloth bag (about 690-1180, 235-760); warm light strips on the shelves; a glossy floor.
Ideas: glints twinkling across the gold (`fx.glints` over the shelves, the bag's cash bundles on the floor at about 480-1340, 720-820); warm strip lights breathing;
dust motes drifting in the light (`fx.motes`); floor reflections shimmering (a few glows on the floor); slow push toward the robber (origin about 58,52).
Nothing red: the alarm is not on in this scene.

## 08 exit (4.5 s) `08_bank_exit.png`
HUD: bank OFFLINE, alarm off, Blue Approaching, active agent Story.
Art: the robber with the bag on the damaged bank steps; a **police car far left** coming down the street (about 135-255, 495-585) with a light bar at about (190,492) and headlights at (150,543) and (235,543);
red and blue reflections on the wet road below it (about 130-260, 600-870); the red hatchback at the right with a lit tail light (about 1540,590); lamps; the bank's interior light (1230,215); rain.
Ideas: `MP.lightbar` on the cruiser's bar and its reflections on the road (alternating, the reflections elongated and vertical); headlights breathing; lamp flicker; the red car's tail light pulse;
rain over the whole frame (light) and ripples on the road; a slow push toward the left (origin about 14,56) to "notice" the approaching car, or a gentle pan. Emergency lights fade in over the first 0.6 s.
Scene 09 shares this exact viewpoint, so keep the cruiser and light positions identical to scene 09's.

## 09 rush (4.0 s) `09_rush_same_parking-r2.png`
HUD: bank OFFLINE, alarm off, Blue Arriving, active agent Story.
Art: same street and parking spot as 08; the robber runs to the open driver door of the red hatchback (open door about 1170-1320, 400-690), splashes under his feet (about 960-1100, 690-730).
Ideas: the cruiser is closer in feel: lights stronger than in 08 (`level` up), headlight glows larger, road reflections brighter; water splash from the footsteps (`fx.splash` near 1000,720 and 1100,725, triggered at a believable moment);
slight handheld run shake (small); push toward the car (origin about 85,60); tail light pulse; rain and ripples as in 08. Same positions as 08 for the cruiser and its reflections.

## 10 mirror (4.5 s) `10_rear_view.png`
HUD: bank OFFLINE, alarm off, Blue Following, active agent Story.
Art: Red driving (hat at left); a large rear-view mirror (about 680-1540, 100-340) showing a police car close behind (about 960-1300, 130-320) with a light bar at about (1050-1215,148)
and flashing grille lights (about 1005-1250,262); rain drops on the glass; a wet street with lamps; red dash strips (800-1330, 740-775); a lit hazard button (about 880,890).
Ideas: `MP.lightbar` on the cruiser's bar and grille *inside the mirror region only*, plus a blue/red wash spilling on the dash, windscreen edge and Red's hat/shoulder; rain on the windscreen (`fx.rain` clipped to the glass) and drops;
headlights in the mirror breathing; hazard button pulse; road vibration sway (small, faster than elsewhere) and a slight push toward the mirror (origin about 60,25).

## 11 pursuit (13.0 s) `11_blue_pursuit.png`
HUD: bank **RECOVERING**, alarm off, Blue "Recovery action applied", **Blue feed starts**.
Art: Blue's windscreen view of the red hatchback driving away down a wet avenue (car about 910-1135, 295-455, tail lights at about 950,382 and 1100,382);
a large dark dashboard display (about x 895-1620, y 575-850, slightly tilted: measure it); light-bar glints along the top of the windscreen (about 700,18 red and 1010,12 blue) and a red/blue strip along the dash top (about 700-1672, 550);
instrument dials at (440,640) and (620,650); a police radio at the right (1380-1520, 590-760).
Overlay on the display, with the v0 look (header `BLUE / SERVICE RECOVERY` and `FIXTURE`, blue theme `MP.codeScreen({theme:'blue', title:...})`, tilted to the glass), typing the six `sc.blueLines` at 30 cps,
lines starting about 0.8, 2.6, 4.6, 6.4, 8.2, 10.0 s. The last line is "// awaiting demo health event": **do not add a progress bar, a percentage or any success text.**
Animation: `MP.lightbar` along the dash strip and windscreen top; the red car's tail lights pulse; wet-road reflections breathe; rain on the windscreen and streaks; the display wakes with a short stutter;
dial glow breathing; driving sway and a slow push toward the red car (origin about 60,42). Scene 12 shares this viewpoint and display.

**Omar's explicit request (this scene): the Blue team's code must type on the dashboard display, like the Red team's code does in scene 04.** Same typed-line look (caret, 30 cps), in blue. This display is much bigger than scene 04's small Red screen, so the text must be bigger too: body text no smaller than about 1.0 cqw (roughly 12 px in a 1226 px-wide stage; v0 uses 1.14 cqw), with the `BLUE / SERVICE RECOVERY` header above it. It must be clearly legible in a normal 1500 px window, not a few pixels of grey text.

## 12 recovered (6.5 s) `12_blue_recovery_complete.png`
HUD: bank ONLINE, alarm off, Blue "Demo action complete", Blue check true.
Art: the same view as 11, but the large display now shows a big **green check in a circle** (centre about 1233,693, radius about 88). It is part of the image.
**Continuity with scene 11:** begin with the *same* Blue feed overlay on the display, all six lines fully typed, exactly as scene 11 ended; at about 0.4 to 1.0 s dissolve it away so the baked check is revealed;
then one soft green pulse: a glow behind the check and one expanding ring (draw it on the canvas). Keep the lights, rain, sway and push of scene 11.
Do not add text that claims anything is verified: the check is the approved art, nothing more.

## 13 hydroplane (4.5 s) `13_hydroplane_check-r2.png`
HUD: bank ONLINE, alarm off, Blue "Stopping", active agent Story.
Art: same view; the red hatchback has skidded sideways into a light pole at the right (car about 1095-1465, 290-455; pole about 1470-1520, 0-440); skid marks across the road; splash at the wheels (about 1100-1200, 420-460); the green check on the dash display.
Ideas: a believable beat at about 0.5 s: Blue brakes (small camera jolt: `shake` amplitude about 0.5), sparks from the pole (`fx.sparks`), spray from the wheels and the pole (`fx.splash`), a few small bits of debris;
the pole's lamp (about 1500,60) and its neighbour (1385,125) flicker once, softly; heavier rain than before; the check on the dash gently pulsing; lights continue; settle into a slow push toward the crashed car (origin about 75,45).

## 14 arrest (6.5 s) `14_street_arrest.png`
HUD: bank ONLINE, alarm off, Blue and Red "Story complete".
Art: a police car at the left (about 35-575, 285-580) with a light bar at about (260-460, 293), headlights at (75,435) and (350,445); an officer handcuffing the robber beside the crashed red hatchback (about 800-1540, 300-740);
a money bag; wet street with strong red/blue reflections at the lower left (about 0-480, 540-820); puddles; tall lamps; heavy rain.
Ideas: `MP.lightbar` on the bar and its reflections on the road and on the car's wet paint; headlight breathing; ripples in the puddles (`fx.ripples`) and rain over the frame;
lamp flicker; the red car's tail light pulse (about 1145,515); a little steam or smoke from the crumpled front (about 1490,480, `fx.dust` in grey, small);
slow push toward the officer and robber (origin about 55,55). In the last second ease the emergency lights down (`level` to about 0.4) so the ending settles; the engine shows the "Demo complete" card when the timeline ends.
