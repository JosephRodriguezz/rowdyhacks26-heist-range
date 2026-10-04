# Heist district — Blender design handoff

Open these files directly in Blender 5.2 or newer:

- `heist_district.blend`: full setting and all three characters.
- `setting.blend`: bank, city buildings, streets, trees, cars, and service props.
- `characters.blend`: all three characters together.
- `robber.blend`, `officer.blend`, `auditor.blend`: individual character assets.
- `heist_district.png`: rendered reference for the full design.

All assets are editable and include materials, lighting, and a camera. No
external textures, fonts, add-ons, or downloads are required. Numpad 0 shows
the camera. F12 renders. For a saved individual character, use the parent
empty named “move entire character” to move the complete figure.

To combine assets, choose File > Append, select a `.blend` file, open its
Collection folder, and append the relevant collections. Append the character
collection to retain its parent hierarchy. Avoid importing duplicate camera
and lighting collections if the destination already has them.

Characters have separate body parts and accessories but are not rigged or
animated. This is a static concept design, not an interactive security demo.
The full scene and split assets share the same design and materials.

`build_heist.py` regenerates the original scene. `package_handoff.py` creates
the split assets. Their output directories follow the scripts' locations;
run them in the original repository layout to reproduce this package.
`verification.json` records the split assets' successful reopen checks.
