"""Add a restrained set of real CC0 Poly Haven props to the V0.2 arena."""
from pathlib import Path
import math
import bpy
from mathutils import Matrix

ROOT = Path(bpy.data.filepath).parent
ASSET_ROOT = ROOT / "assets" / "polyhaven" / "models"
OUTFILE = ROOT / "heist_district_v0_3.blend"
BATTLE = bpy.data.scenes["02 • Battle / BEGIN and Live Screens"]
BLUE = bpy.data.scenes["04 • Blue Win / Same Battle Room"]


def append_meshes(slug):
    path = ASSET_ROOT / slug / f"{slug}_1k.blend"
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = [name for name in src.objects if name and name in src.objects]
    return [obj for obj in dst.objects if obj and obj.type == "MESH"]


def make_assembly(name, meshes, collection, location, rotation_z=0.0, scale=1.0):
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "PLAIN_AXES"
    collection.objects.link(root)
    root.location = location
    root.rotation_euler[2] = rotation_z
    root.scale = (scale, scale, scale)
    for mesh in meshes:
        collection.objects.link(mesh)
        mesh.parent = root
        mesh.matrix_parent_inverse = Matrix.Identity(4)
    return root


detail = bpy.data.collections.new("V0.3 | Imported CC0 security props")
BATTLE.collection.children.link(detail)
BLUE.collection.children.link(detail)

camera_parts = append_meshes("security_camera_02")
# These are static scene props, so discard their source rig modifiers.
for part in camera_parts:
    for modifier in list(part.modifiers):
        if modifier.type == "ARMATURE":
            part.modifiers.remove(modifier)
make_assembly("CC0 • Security camera • west wall", camera_parts, detail,
              (-7.78, 4.5, 5.15), math.pi / 2, 1.2)
make_assembly("CC0 • Security camera • east wall", [obj.copy() for obj in camera_parts], detail,
              (7.78, 4.5, 5.15), -math.pi / 2, 1.2)

sconce_parts = append_meshes("industrial_caged_sconce")
make_assembly("CC0 • Industrial caged sconce • west", sconce_parts, detail,
              (-5.65, 8.34, 4.7), 0.0, 1.25)
make_assembly("CC0 • Industrial caged sconce • east", [obj.copy() for obj in sconce_parts], detail,
              (5.65, 8.34, 4.7), math.pi, 1.25)

# Make the two story scenes open on useful frames and retain V0.2's render setup.
BATTLE.frame_set(62)
BLUE.frame_set(72)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUTFILE), compress=True)
print(f"V03_SAVED {OUTFILE}")
