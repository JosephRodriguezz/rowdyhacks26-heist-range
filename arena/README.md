# Omar's arena v2 baseline

Branch: `omar/arena-v2-baseline`. Owner: Omar. Version: **0.2.0**.

This is the portable starting point for the team's next visual experiments. It includes the 14 approved scene images, the full 85.5-second motion demo, the earlier judge UI, source assets and visual history.

## Run

Open **[motion-proof/index.html](motion-proof/index.html)** in a current Edge or Chrome and press Play. No server, install, Blender, Unity or Unreal is needed to run the baseline.

- [Scene review](scene-review.html): approved sequence and archived revisions.
- [Earlier judge UI](index.html): agent cards, inspector, timeline and fixture controls.
- [Motion controls and verification](motion-proof/MOTION_PROOF.md).

## Included files

| Location | Contents |
|---|---|
| `motion-proof/` | Player, shared effects, all 14 scene modules, story snapshot, tests and PowerShell capture/measurement tools |
| `scenes-v2/` | All scene images and revisions, approved manifest, generation prompts and prior review notes |
| `concept-scenes/` | Original six concepts, including superseded concepts for historical reference |
| `fixtures/`, `tests/` | Canonical fixture, direct-open bundle, judge UI/core tests |
| `archive/` | Earlier player files |
| `references/user-feedback/` | All 12 screenshot attachments from Omar's review in this conversation |
| `assets/agents/` | Four transparent Red/Blue role sprites and lineup |
| `../Heist_Blender_Designs/` | All existing Blender projects, split characters/setting, builder scripts, preview images, textures, model sources and add-on archive |
| `ASSET_INVENTORY.json` | Relative file paths, byte sizes and SHA-256 checksums for this package |

The Blender brand reference is bundled in `Heist_Blender_Designs/references/rowdyhacks-brand.png`; its builder uses that relative path. Poly Haven source/attribution notes remain in `Heist_Blender_Designs/ASSET_SOURCES.md`.

Historical prompts, review notes, scripts and the initial request preserve earlier decisions. **This README and the approved `scenes-v2/manifest.json` define the v2 baseline.** Superseded concepts are not active scenes. Historical Windows paths in notes describe where work happened; the current web player uses relative files.

## Verify after checkout

From `arena/`, with Node installed:

```sh
npm test
npm run verify-assets
```

No npm install is needed. The tests use an in-memory DOM/canvas; they do not prove browser pixel alignment or smoothness. Watch the demo on the actual display. The archived PowerShell capture tools are provided for teammates; Codex did not use them to bypass its browser-access restriction.

## Start a visual experiment

Keep this branch as the known baseline. Create a new experiment branch from it:

```sh
git fetch origin
git switch -c your-experiment-name origin/omar/arena-v2-baseline
```

- **Higgsfield / Hixfield cutscenes:** use the approved images, `scenes-v2/prompts.md`, and `motion-proof/SCENE_BRIEFS.md` as visual direction. Put candidate clips under a new `arena/media/` directory and record which scene each replaces. Do not remove the image fallback. No generated clips are included yet.
- **Blender:** start with `../Heist_Blender_Designs/START_HERE.md` and the editable `.blend` files. These older 3D concepts differ from the approved raster art; there are no matching animated 3D versions of the 14 approved images. Characters in those concepts are not rigged.
- **Unity / Unreal:** create a separate engine project in your experiment branch. Use the approved manifest for scene IDs and ordering, and the fixture/story for timing and screen states. Existing Blender models and sprites are source material, not finished engine projects.

Across experiments preserve Red/Blue identities, the red hatchback, rainy bank/street continuity, closed vault in 04/open in 05, alert-only 06, Blue code beginning in 11, and the same check size in 12/13. Screen content should remain replaceable independently of background media.

## What v2 demonstrates

Camera, weather, lights, particles and displays animate over the approved stills. Characters and cars remain baked into those images. Website and code feeds are synthetic **FIXTURE** data; independent referee is **Not connected**. This is Omar's availability-story visual baseline, not a replacement for the team's live mission or shared event contracts. Team website/feed integration is pending.

No engine choice or live integration is locked by this branch. The branch provides reusable source files and a working visual reference.
