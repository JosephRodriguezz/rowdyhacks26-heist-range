import bpy

scene = bpy.data.scenes["02 • Battle / BEGIN and Live Screens"]
for obj in scene.objects:
    if obj.type in {"MESH", "EMPTY"} and any(term in obj.name.lower() for term in ("wall", "sconce", "vault", "panel", "screen", "floor", "light", "desk", "camera")):
        print("OBJECT", obj.name, "LOC", tuple(round(v, 2) for v in obj.location), "DIM", tuple(round(v, 2) for v in obj.dimensions), "ROT", tuple(round(v, 2) for v in obj.rotation_euler))
