from pathlib import Path
import bpy

root = Path(bpy.data.filepath).parent / "assets" / "polyhaven" / "models"
for slug in ("security_camera_02", "industrial_caged_sconce"):
    path = root / slug / f"{slug}_1k.blend"
    with bpy.data.libraries.load(str(path), link=False) as (data_from, data_to):
        data_to.objects = list(data_from.objects)
    print(f"ASSET {slug}")
    for obj in data_to.objects:
        if obj:
            bpy.context.scene.collection.objects.link(obj)
            print("OBJECT", obj.name, "TYPE", obj.type, "LOC", tuple(round(v, 3) for v in obj.location), "ROT", tuple(round(v, 3) for v in obj.rotation_euler), "SCALE", tuple(round(v, 3) for v in obj.scale), "DIM", tuple(round(v, 3) for v in obj.dimensions))
