"""Refine the existing arena scenes with free Poly Haven materials and lighting."""

from pathlib import Path
import math

import bpy
from mathutils import Vector


ROOT = Path(bpy.data.filepath).parent
ASSETS = ROOT / "assets" / "polyhaven"
OUTFILE = ROOT / "heist_district_v0_2.blend"
SCENE_BATTLE = bpy.data.scenes["02 • Battle / BEGIN and Live Screens"]
SCENE_BLUE = bpy.data.scenes["04 • Blue Win / Same Battle Room"]
SCENE_RED = bpy.data.scenes["03 • Red Win / Inside Vault"]


def image(slug, suffix):
    matches = list(ASSETS.glob(f"{slug}_{suffix}_2k.*"))
    if not matches:
        raise FileNotFoundError(f"Missing Poly Haven texture: {slug} / {suffix}")
    return bpy.data.images.load(str(matches[0]), check_existing=True)


def pbr_material(name, slug, tint, roughness_scale=0.7, repeat=(3, 3, 3)):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*tint, 1)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    links = material.node_tree.links
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Metallic"].default_value = 0.18 if "metal" in slug else 0.0
    shader.inputs["Roughness"].default_value = 0.38 if "floor" in slug else 0.53
    texcoord = nodes.new("ShaderNodeTexCoord")
    scale = nodes.new("ShaderNodeVectorMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = repeat
    links.new(texcoord.outputs["Generated"], scale.inputs[0])

    diffuse = nodes.new("ShaderNodeTexImage")
    diffuse.image = image(slug, "diff")
    diffuse.projection = "BOX"
    diffuse.projection_blend = 0.15
    links.new(scale.outputs["Vector"], diffuse.inputs["Vector"])
    tint_node = nodes.new("ShaderNodeMixRGB")
    tint_node.blend_type = "MULTIPLY"
    tint_node.inputs["Fac"].default_value = 0.62
    tint_node.inputs["Color2"].default_value = (*tint, 1)
    links.new(diffuse.outputs["Color"], tint_node.inputs["Color1"])
    links.new(tint_node.outputs["Color"], shader.inputs["Base Color"])

    rough = nodes.new("ShaderNodeTexImage")
    rough.image = image(slug, "rough")
    rough.image.colorspace_settings.name = "Non-Color"
    rough.projection = "BOX"
    rough.projection_blend = 0.15
    links.new(scale.outputs["Vector"], rough.inputs["Vector"])
    rough_mix = nodes.new("ShaderNodeMath")
    rough_mix.operation = "MULTIPLY"
    rough_mix.inputs[1].default_value = roughness_scale
    links.new(rough.outputs["Color"], rough_mix.inputs[0])
    links.new(rough_mix.outputs[0], shader.inputs["Roughness"])

    normal = nodes.new("ShaderNodeTexImage")
    normal.image = image(slug, "nor_gl")
    normal.image.colorspace_settings.name = "Non-Color"
    normal.projection = "BOX"
    normal.projection_blend = 0.15
    links.new(scale.outputs["Vector"], normal.inputs["Vector"])
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.inputs["Strength"].default_value = 0.28
    links.new(normal.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def box(collection, name, location, size, material, bevel=0.04):
    hx, hy, hz = (v * 0.5 for v in size)
    verts = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
             (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(name + " mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = location
    if bevel:
        mod = obj.modifiers.new("Machined edge highlights", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        obj.modifiers.new("Weighted corner normals", "WEIGHTED_NORMAL")
    return obj


def cylinder(collection, name, location, radius, depth, material, axis="Z"):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=depth,
                                        location=location)
    obj = bpy.context.object
    obj.name = name
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)
    if axis == "Y":
        obj.rotation_euler[0] = math.pi / 2
    bevel = obj.modifiers.new("Machined bevel", "BEVEL")
    bevel.width = min(radius * 0.12, 0.035)
    bevel.segments = 3
    obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    obj.data.materials.append(material)
    return obj


def add_environment(scene, filepath):
    world = scene.world or bpy.data.worlds.new(scene.name + " | Poly Haven studio")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    background = next((n for n in nodes if n.type == "BACKGROUND"), None)
    output = next((n for n in nodes if n.type == "OUTPUT_WORLD"), None)
    if background is None:
        background = nodes.new("ShaderNodeBackground")
    if output is None:
        output = nodes.new("ShaderNodeOutputWorld")
    env = nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(filepath), check_existing=True)
    links.new(env.outputs["Color"], background.inputs["Color"])
    background.inputs["Strength"].default_value = 0.22
    links.new(background.outputs["Background"], output.inputs["Surface"])


def area(collection, scene, name, location, color, power, size, target):
    light_data = bpy.data.lights.new(name, "AREA")
    light_data.energy = power
    light_data.color = color
    light_data.shape = "DISK"
    light_data.size = size
    light = bpy.data.objects.new(name, light_data)
    collection.objects.link(light)
    light.location = location
    light.rotation_euler = (Vector(target) - light.location).to_track_quat("-Z", "Y").to_euler()
    light_data.use_shadow = True
    scene.collection.objects.link(light)
    return light


required = [
    ASSETS / "floor_tiles_04_diff_2k.jpg",
    ASSETS / "floor_tiles_04_nor_gl_2k.jpg",
    ASSETS / "floor_tiles_04_rough_2k.jpg",
    ASSETS / "blue_metal_plate_diff_2k.jpg",
    ASSETS / "blue_metal_plate_nor_gl_2k.jpg",
    ASSETS / "blue_metal_plate_rough_2k.jpg",
    ASSETS / "concrete_wall_004_diff_2k.jpg",
    ASSETS / "concrete_wall_004_nor_gl_2k.jpg",
    ASSETS / "concrete_wall_004_rough_2k.jpg",
    ASSETS / "studio_small_05_2k.exr",
]
missing = [path for path in required if not path.is_file()]
if missing:
    raise FileNotFoundError("Missing Poly Haven files: " + ", ".join(map(str, missing)))

floor_mat = pbr_material("V0.2 | midnight marble tile", "floor_tiles_04",
                          (0.47, 0.56, 0.70), 0.62, (5, 4, 1))
steel_mat = pbr_material("V0.2 | brushed blue steel", "blue_metal_plate",
                          (0.29, 0.43, 0.62), 0.68, (4, 3, 3))
concrete_mat = pbr_material("V0.2 | tinted poured concrete", "concrete_wall_004",
                             (0.38, 0.43, 0.52), 0.72, (4, 2, 3))
red_steel_mat = pbr_material("V0.2 | oxblood operator steel", "blue_metal_plate",
                              (0.58, 0.20, 0.17), 0.72, (2, 2, 2))
blue_steel_mat = pbr_material("V0.2 | cobalt defender steel", "blue_metal_plate",
                               (0.12, 0.36, 0.66), 0.72, (2, 2, 2))

detail = bpy.data.collections.new("ARENA | V0.2 architecture and lighting")
SCENE_BATTLE.collection.children.link(detail)
SCENE_BLUE.collection.children.link(detail)

def assign(scene, object_name, material):
    obj = scene.objects.get(object_name)
    if obj and obj.type == "MESH":
        obj.data.materials.clear()
        obj.data.materials.append(material)


for scene in (SCENE_BATTLE, SCENE_BLUE):
    assign(scene, "Bank interior | reflective charcoal floor", floor_mat)
    for obj in scene.objects:
        low = obj.name.lower()
        if "back wall" in low:
            assign(scene, obj.name, steel_mat)
        elif "side wall" in low:
            assign(scene, obj.name, concrete_mat)
        elif low.endswith("| desk"):
            assign(scene, obj.name, red_steel_mat if "red_" in low else blue_steel_mat)
    for name in ("Battle vault | dark recess", "Battle vault | sealed disk"):
        assign(scene, name, steel_mat)

SCENE_RED.objects.get("RED VICTORY VAULT | floor") and assign(
    SCENE_RED, "RED VICTORY VAULT | floor", floor_mat)

brass = bpy.data.materials.get("Arena | brass")
gold = bpy.data.materials.get("Arena | gold") or brass
ink = bpy.data.materials.get("Arena | ink")
red_glow = bpy.data.materials.get("Arena | red glow")
blue_glow = bpy.data.materials.get("Arena | blue glow")
warm_glow = bpy.data.materials.get("Arena | warm glow")

# Deepen and detail the room with machined wall panels, layered base/crown rails,
# vertical warm sconces, and brass reveals. Blue ending links this same collection.
for z, name in ((6.13, "crown"), (0.32, "base")):
    box(detail, f"V0.2 | rear wall {name} rail", (0, 8.27, z), (15.6, 0.16, 0.15), gold, 0.025)
for x in (-7.55, 7.55):
    box(detail, f"V0.2 | rear wall outer pilaster {x}", (x, 8.25, 3.15), (0.28, 0.20, 5.75), steel_mat, 0.07)
    box(detail, f"V0.2 | pilaster brass inlay {x}", (x, 8.13, 3.18), (0.055, 0.035, 5.50), gold, 0.015)

for side in (-1, 1):
    x = side * 7.77
    for idx, y in enumerate((-3.8, -0.9, 2.0, 4.9, 7.3)):
        box(detail, f"V0.2 | side wall panel {side} {idx}", (x, y, 3.0),
            (0.09, 2.36, 4.82), steel_mat if idx % 2 else concrete_mat, 0.045)
        for dy in (-1.10, 1.10):
            box(detail, f"V0.2 | side panel reveal {side} {idx} {dy}",
                (side * 7.70, y + dy, 3.0), (0.045, 0.035, 4.45), gold, 0.012)
    accent = red_glow if side < 0 else blue_glow
    box(detail, f"V0.2 | red-blue vertical light {side}",
        (side * 7.68, 0.1, 3.15), (0.045, 0.17, 3.9), accent, 0.02)
    box(detail, f"V0.2 | side sconce bezel {side}",
        (side * 7.70, 3.85, 4.85), (0.18, 0.68, 1.35), brass, 0.09)
    box(detail, f"V0.2 | side sconce diffuser {side}",
        (side * 7.57, 3.85, 4.85), (0.07, 0.42, 1.05), warm_glow, 0.06)

# Give the vault wheel more depth and exposed mechanical detail.
for radius, thickness in ((1.52, 0.045), (1.13, 0.035), (0.70, 0.028)):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=thickness,
                                     major_segments=72, minor_segments=12,
                                     location=(0, 7.90, 2.15), rotation=(math.pi / 2, 0, 0))
    ring = bpy.context.object
    ring.name = f"V0.2 | vault concentric machined ring {radius}"
    for owner in list(ring.users_collection):
        owner.objects.unlink(ring)
    detail.objects.link(ring)
    ring.data.materials.append(gold if radius != 1.13 else steel_mat)
for idx in range(16):
    angle = 2 * math.pi * idx / 16
    x, z = 1.40 * math.cos(angle), 2.15 + 1.40 * math.sin(angle)
    cylinder(detail, f"V0.2 | vault lock pin {idx:02d}", (x, 7.81, z), 0.052, 0.10,
             brass, "Y")
for side in (-1, 1):
    box(detail, f"V0.2 | vault hinge casing {side}",
        (side * 1.87, 7.89, 2.35), (0.34, 0.29, 1.05), steel_mat, 0.07)
    for offset in (-0.30, 0, 0.30):
        cylinder(detail, f"V0.2 | vault hinge axle {side} {offset}",
                 (side * 1.87, 7.69, 2.35 + offset), 0.085, 0.30, gold, "Y")

# Finish the room lighting with warm key and team-colored rim lights.
for name, loc, color, power, size, target in (
    ("V0.2 | warm cinematic key", (0, -4.7, 8.7), (1.0, 0.72, 0.44), 1600, 7.0, (0, 3, 1.8)),
    ("V0.2 | red operator rim", (-7.0, -0.2, 4.4), (1.0, 0.10, 0.065), 900, 4.0, (-3.6, 0.5, 1.7)),
    ("V0.2 | blue defender rim", (7.0, -0.2, 4.4), (0.08, 0.34, 1.0), 1000, 4.0, (3.6, 0.5, 1.7)),
    ("V0.2 | soft camera fill", (0, -10.0, 5.8), (0.70, 0.80, 1.0), 500, 6.0, (0, 3.0, 2.0)),
):
    area(detail, SCENE_BATTLE, name, loc, color, power, size, target)

studio_hdri = ASSETS / "studio_small_05_2k.exr"
for scene in bpy.data.scenes:
    if scene.name.startswith(("02", "03", "04")):
        add_environment(scene, studio_hdri)
    if scene.camera:
        scene.camera.data.dof.use_dof = False
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

# Ensure the same enhanced set appears in both battle outcomes; pack textures/HDRI.
for image_data in bpy.data.images:
    if image_data.filepath and "polyhaven" in image_data.filepath.lower():
        image_data.pack()

bpy.context.window.scene = SCENE_BATTLE
SCENE_BATTLE.frame_set(62)
for area_data in bpy.context.screen.areas:
    if area_data.type == "VIEW_3D":
        area_data.spaces.active.region_3d.view_perspective = "CAMERA"
        area_data.spaces.active.shading.type = "MATERIAL"
        area_data.spaces.active.overlay.show_overlays = False

bpy.ops.wm.save_as_mainfile(filepath=str(OUTFILE))
__result__ = {
    "output": str(OUTFILE),
    "polyhaven_images_packed": [i.name for i in bpy.data.images if i.packed_file],
    "battle_detail_objects": len(detail.objects),
    "scenes": [(s.name, s.render.resolution_x, s.render.resolution_y,
                s.render.engine, s.cycles.samples) for s in bpy.data.scenes],
}
