from pathlib import Path
import bpy

root = Path(bpy.data.filepath).parent
output = root / "arena_previews_v0_2"
output.mkdir(parents=True, exist_ok=True)
shots = [
    ("01 • Exterior / Start and Walk-in", 1, "01_exterior_start.png"),
    ("02 • Battle / BEGIN and Live Screens", 62, "02_battle.png"),
    ("03 • Red Win / Inside Vault", 108, "03_red_vault.png"),
    ("04 • Blue Win / Same Battle Room", 72, "04_blue_arrest.png"),
]
for name, frame, filename in shots:
    scene = bpy.data.scenes[name]
    scene.frame_set(frame)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(output / filename)
    bpy.ops.render.render(write_still=True, scene=scene.name)
    print(f"V02_RENDER {name} -> {scene.render.filepath}")
