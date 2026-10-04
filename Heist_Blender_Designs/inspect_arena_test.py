"""Print shot transforms from a built test file without changing it."""
import bpy

for scene_name, frame in [
    ("01 • Exterior / Start and Walk-in", 1),
    ("02 • Battle / BEGIN and Live Screens", 62),
    ("03 • Red Win / Inside Vault", 108),
    ("04 • Blue Win / Same Battle Room", 72),
]:
    scene = bpy.data.scenes[scene_name]
    bpy.context.window.scene = scene
    scene.frame_set(frame)
    print("SHOT", scene_name, "CAM", tuple(round(x, 2) for x in scene.camera.location))
    for obj in scene.objects:
        if obj.name.endswith("| root") or obj.name.endswith("move entire character"):
            print("ROOT", obj.name, tuple(round(x, 2) for x in obj.location),
                  tuple(round(x, 2) for x in obj.matrix_world.translation),
                  "rot", tuple(round(x, 2) for x in obj.rotation_euler),
                  "scale", tuple(round(x, 2) for x in obj.scale))
            heads = [o for o in obj.children if " head" in o.name]
            if heads:
                print("HEAD", heads[0].name, tuple(round(x, 2) for x in heads[0].matrix_world.translation))
