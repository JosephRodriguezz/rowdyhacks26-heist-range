# RowdyHacks arena — Blender visual pass

For the latest enhanced visual pass, open `heist_district_v0_3.blend` in Blender. It opens on the battle room at frame 62 in camera view. Use the scene selector at the top right of Blender to switch scenes; press Numpad 0 if you leave camera view. Press Space to play the selected scene's timeline. Timeline markers describe the beats. `heist_district_v0_2.blend` is the preceding material-and-lighting pass; `heist_district.blend` remains the preserved original arena build.

| Scene | What to inspect |
| --- | --- |
| `01 • Exterior / Start and Walk-in` | Original district repainted and branded; auditor's START prop; three character walk-in keyframes. Frames 1, 24, 108. |
| `02 • Battle / BEGIN and Live Screens` | New bank interior, Red/Blue desks, auditorium-style bank jumbotron, RH banners, auditor tablet, BEGIN cue and simple typing motion. Frames 1, 8, 38, 62. |
| `03 • Red Win / Inside Vault` | Separate vault set, opening door, robber enters, symbolic cash-rain and small result caption. Inspect around frame 108. |
| `04 • Blue Win / Same Battle Room` | The same shared battle-room set and camera, cop arrest movement and small result caption. Inspect around frame 72. |

`arena_previews_v0_3/` contains full-HD renders of the battle and blue-win scenes. `arena_previews_v0_2/` has all four V0.2 scene previews. The V0.3 room adds Poly Haven security-camera and caged-sconce props; see `ASSET_SOURCES.md` for the asset sources and tool-access notes. `heist_district_before_arena_2026-10-03.blend` is a backup of the original open scene before this visual pass. `arena_workflow_builder.py`, `v0_2_refinement.py`, and `refine_v0_3_props.py` are the builder/refinement scripts.

## Boundaries for the first demo

These are Blender visuals and fixture placeholders, **not a live cyber-range UI**. The jumbotron and side monitors are labeled `FIXTURE PREVIEW`; they do not yet display the registered fictional bank site or live Red/Blue events. The START prop is not a clickable web button, scenes do not branch automatically, and no music has been added. The animation uses keyframed object/hand motion, not character rigs. The cash is a victory metaphor: mission one is independently verified **vault-data access**, not a real-money theft or a website-availability objective. A later web runtime must receive referee-verified results before selecting the Red or Blue outcome; character animation must never determine the verdict.

If Blender was already showing the older version of `heist_district.blend` while this file was rebuilt in the background, reopen the file from disk (File > Open) to load these scenes. Do not save the stale window over the updated file.
