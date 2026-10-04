"""Render four low-resolution verification frames from an arena workflow .blend."""

from pathlib import Path
import bpy

output = Path(bpy.data.filepath).parent / "arena_previews"
output.mkdir(exist_ok=True)
shots = [
    ("01 • Exterior / Start and Walk-in", 1, "01_exterior_start.png"),
    ("02 • Battle / BEGIN and Live Screens", 62, "02_battle.png"),
    ("03 • Red Win / Inside Vault", 108, "03_red_vault.png"),
    ("04 • Blue Win / Same Battle Room", 72, "04_blue_arrest.png"),
]
for name, frame, filename in shots:
    scene = bpy.data.scenes[name]
    bpy.context.window.scene = scene
    scene.frame_set(frame)
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(output / filename)
    bpy.ops.render.render(write_still=True)
    print(f"VERIFY_RENDER {name} -> {scene.render.filepath}")
