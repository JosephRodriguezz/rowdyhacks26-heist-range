# RowdyHacks26 — approved 14-scene sequence

All fourteen current scenes explicitly approved by Omar on 2026-10-03.

**14 approved:** 01–14. No scenes remain pending visual approval.

## Changes

Latest correction: turned only scene 06's red hatchback to match scene 08's parking direction. Front headlights/grille now face the opposite cop viewpoint. The accepted camera, bank, street and dashboard composition is retained.

- 04: enlarged website monitor and much smaller Red activity monitor below-right. Website content is a level rectangle with no CSS skew, rotation or perspective clipping. The vault stays shut.
- 05: same new monitor layout as 04, with the vault door open, red alarm, black website and small green Red completion check.
- 06: moved the cop car/camera to the yellow-marked street area and reversed the view down the road toward the bank. The bank is ahead-left, with intervening lamp/tree spacings. Same cop cabin and alert-only dashboard; Blue code inactive.

## Active sequence

| Scene | Asset | Approval |
|---|---|---|
| 01 — Approved opening retained | [01_driver_start.png](scenes-v2/01_driver_start.png) | APPROVED |
| 02 — Crash through the bank doors | [02_bank_crash.png](scenes-v2/02_bank_crash.png) | APPROVED |
| 03 — Enter and see the vault from far | [03_bank_entry-r2.png](scenes-v2/03_bank_entry-r2.png) | APPROVED |
| 04 — Website + separate Red screen | [04_large_straight_website-r4.png](scenes-v2/04_large_straight_website-r4.png) | APPROVED |
| 05 — Alarm + website blackout + Red check | [05_open_vault_matched-r3.png](scenes-v2/05_open_vault_matched-r3.png) | APPROVED |
| 06 — Cop view from the marked street area | [06_car_orientation-r9.png](scenes-v2/06_car_orientation-r9.png) | APPROVED |
| 07 — Red fills the money bag | [07_inside_vault_money-r2.png](scenes-v2/07_inside_vault_money-r2.png) | APPROVED |
| 08 — Exit and spot Blue far away | [08_bank_exit.png](scenes-v2/08_bank_exit.png) | APPROVED |
| 09 — Rush to the car | [09_rush_same_parking-r2.png](scenes-v2/09_rush_same_parking-r2.png) | APPROVED |
| 10 — Rear-view police reveal | [10_rear_view.png](scenes-v2/10_rear_view.png) | APPROVED |
| 11 — Street pursuit + larger Blue screen | [11_blue_pursuit.png](scenes-v2/11_blue_pursuit.png) | APPROVED |
| 12 — Blue recovery completion | [12_blue_recovery_complete.png](scenes-v2/12_blue_recovery_complete.png) | APPROVED |
| 13 — Hydroplane into the light pole | [13_hydroplane_check-r2.png](scenes-v2/13_hydroplane_check-r2.png) | APPROVED |
| 14 — Street arrest after the crash | [14_street_arrest.png](scenes-v2/14_street_arrest.png) | APPROVED |

### 01 — Approved opening retained

Your original driver viewpoint, route map and Start graphic are preserved.

Use a real keyboard-accessible Start control in the arena. The pictured START is decorative.

### 02 — Crash through the bank doors

The same red hatchback breaks through the closed double doors of the bank at night.

Door damage is a fictional visual beat; nobody is injured. The hatchback remains the vehicle for later scenes.

### 03 — Enter and see the vault from far

Red stands inside the damaged entrance and looks down the long lobby toward the distant closed vault. The red car has been removed from the doorway view.

Car removed from scene 03 only. The long lobby, robber viewpoint and distant closed vault are retained.

### 04 — Website + separate Red screen

Red uses the keypad beside the closed vault. The enlarged website screen dominates the wall; the separate Red code screen below it is much smaller. The displayed website is straight and level.

Website HTML has no skew, rotation or perspective clipping. The two displays have a clear gap. Vault remains closed during the attempt.

### 05 — Alarm + website blackout + Red check

The vault is now open. The larger website display goes black, the small Red screen shows a green completion check, and the alarm glows red.

Same screen sizes, positions, keypad, robber and camera as scene 04. Only the vault opening and alarm/completion state change. Approved by Omar.

### 06 — Cop view from the marked street area

Blue receives the alarm from inside the cop car at the marked end of the street, facing back down the road toward the bank ahead on the left.

The yellow-marked road area is the camera/car location, with the direction reversed toward the bank. Several lamp and tree spacings lead toward the bank. Dashboard is alert only; Blue code remains inactive until scene 11. The parked red hatchback is turned to preserve scene 08's direction; from this opposite cop viewpoint its front headlights and grille are visible.

### 07 — Red fills the money bag

The robber fills the cloth money bag fully inside the vault chamber, surrounded by storage shelves. No vault door, doorway or corridor is visible.

The camera looks into the enclosed storage interior, away from the entrance. Keep the fictional money collection as story art, separate from security evidence.

### 08 — Exit and spot Blue far away

Red emerges from the damaged bank entrance and notices a distant approaching police car.

Keep the police car distant here so the next rush-to-car scene has a clear trigger.

### 09 — Rush to the car

Red rushes from the bank steps to the open driver door of the red hatchback, preserving scene 08's parking spot beside the bank and its street viewpoint.

Scene 08 is the continuity reference: the car remains at the same curbside position near the damaged entrance. Only the robber action and driver door change.

### 10 — Rear-view police reveal

Red is back at the wheel, and the police car is visible behind him in the rear-view mirror.

The forward view is the city street away from the bank. This is Red's car viewpoint.

### 11 — Street pursuit + larger Blue screen

Blue's car viewpoint follows the red hatchback along the city street, away from the bank. More cabin and a much larger dashboard display are visible.

The dashboard preview contains sanitized fixture activity. Live public Blue activity will replace it once the team provides the feed.

### 12 — Blue recovery completion

The same pursuit viewpoint is retained; the enlarged Blue display switches to a green completion check.

This illustrates recovery completion. Actual restored availability and independent verification remain separate event fields.

### 13 — Hydroplane into the light pole

The red hatchback hydroplanes into the light pole in the same Blue car viewpoint. The dashboard completion check matches scene 12's larger size.

Match the completion icon's diameter, location and glow to scene 12. Preserve the crash, rain, street, car and cockpit viewpoint.

### 14 — Street arrest after the crash

Blue arrests the uninjured Red robber on the same street beside the stopped cars.

This closes the visual story. No auditor-room scene or baked winner plaque is used, and the illustration does not determine a referee verdict.

## Screen geometry

Scene 04's level website preview: left 49%, top 14%, width 45.7%, height 33.3%. Red preview: left 78%, top 56.2%, width 14.8%, height 13.6%. The website ends at 47.3% height, leaving an 8.9% vertical gap before code. Website preview area is about 7.6 times code preview area. Both scoped transforms are none; website clip-path is none. Scene 05 uses the same monitor artwork positions and sizes, with blackout/check baked into that variant.

## Review boundary

Exactly fourteen active scenes; fourteen approved images preserved. All prior variants remain available. New raster art used the built-in imagegen tool; prompts and reference roles are saved in scenes-v2/prompts.md. New outputs inspected visually; gallery markup and bounds checked from source. Browser rendering is not verified because local-file browser automation was blocked previously.

Website/activity previews are static FIXTURE HTML. Live team feeds and independent referee results are deferred. Blue activity/code is inactive before scene 11 in the separate fixture draft. Art does not establish a real security result. The runtime is not integrated during this review.

Next stage: adapt the existing arena website around this approved fourteen-scene selection. Live team feeds remain deferred.
