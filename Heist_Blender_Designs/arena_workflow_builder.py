"""Build the RowdyHacks visual-workflow prototype in the open Blender file.

Run through the Blender bridge while heist_district.blend is open. The script
adds three scenes and augments the original exterior scene. It does not create
security outcomes; every screen and animation is a labeled fixture preview.
"""

import math
import random
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(bpy.data.filepath).parent
BRAND_REFERENCE = ROOT / "references" / "rowdyhacks-brand.png"
if not BRAND_REFERENCE.exists():
    raise FileNotFoundError(f"RowdyHacks brand reference is missing: {BRAND_REFERENCE}")
if "Battle • Fixture Preview" in bpy.data.scenes:
    raise RuntimeError("The arena workflow already exists; no duplicate scenes were created.")


def mat(name, color, metallic=0.0, roughness=0.65, emission=0.0):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    if emission:
        shader = nodes.new("ShaderNodeEmission")
        shader.inputs["Color"].default_value = (*color, 1)
        shader.inputs["Strength"].default_value = emission
    else:
        shader = nodes.new("ShaderNodeBsdfPrincipled")
        shader.inputs["Base Color"].default_value = (*color, 1)
        shader.inputs["Metallic"].default_value = metallic
        shader.inputs["Roughness"].default_value = roughness
    material.node_tree.links.new(shader.outputs[0], output.inputs["Surface"])
    return material


IVORY = mat("Arena | ivory", (0.79, 0.73, 0.61))
PAPER = mat("Arena | paper", (0.94, 0.88, 0.76))
KRAFT = mat("Arena | kraft", (0.39, 0.27, 0.18))
INK = mat("Arena | ink", (0.022, 0.025, 0.031), roughness=0.48)
CHARCOAL = mat("Arena | charcoal steel", (0.075, 0.078, 0.082), metallic=0.35)
FLOOR = mat("Arena | polished floor", (0.11, 0.105, 0.10), metallic=0.27, roughness=0.27)
BRASS = mat("Arena | brass", (0.56, 0.37, 0.15), metallic=0.74, roughness=0.3)
CRIMSON = mat("Arena | crimson", (0.61, 0.035, 0.027), roughness=0.43)
BLUE = mat("Arena | blue", (0.025, 0.26, 0.70), roughness=0.38)
RED_GLOW = mat("Arena | red glow", (0.90, 0.04, 0.025), emission=2.5)
BLUE_GLOW = mat("Arena | blue glow", (0.06, 0.36, 1.0), emission=2.2)
WARM_GLOW = mat("Arena | warm glow", (1.0, 0.75, 0.40), emission=2.5)
SCREEN = mat("Arena | screen white", (0.78, 0.86, 0.90), emission=1.25)
SCREEN_DARK = mat("Arena | screen dark", (0.015, 0.022, 0.035), emission=0.35)
GOLD = mat("Arena | gold", (0.83, 0.57, 0.20), metallic=0.5, roughness=0.32)
UI_IVORY = mat("Arena | ivory UI text", (0.96, 0.89, 0.74), emission=1.0)


def put(obj, collection):
    collection.objects.link(obj)
    return obj


def box(collection, name, location, size, material, bevel=0.0, parent=None):
    x, y, z = (value / 2 for value in size)
    vertices = [
        (-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
        (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z),
    ]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(name + " mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    obj = put(bpy.data.objects.new(name, mesh), collection)
    obj.parent = parent
    obj.location = location
    if bevel:
        modifier = obj.modifiers.new("Soft edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def cylinder(collection, name, location, radius, depth, material,
             vertices=32, parent=None, rotate_x=0.0):
    points = []
    for z in (-depth / 2, depth / 2):
        for i in range(vertices):
            angle = i * 2 * math.pi / vertices
            points.append((radius * math.cos(angle), radius * math.sin(angle), z))
    faces = []
    for i in range(vertices):
        j = (i + 1) % vertices
        faces.append((i, j, j + vertices, i + vertices))
    faces += [tuple(range(vertices - 1, -1, -1)),
              tuple(range(vertices, 2 * vertices))]
    mesh = bpy.data.meshes.new(name + " mesh")
    mesh.from_pydata(points, [], faces)
    mesh.materials.append(material)
    obj = put(bpy.data.objects.new(name, mesh), collection)
    obj.parent = parent
    obj.location = location
    obj.rotation_euler.x = rotate_x
    return obj


def torus(collection, name, location, major, minor, material,
          parent=None, rotate_x=0.0, segments=48):
    points, faces = [], []
    for i in range(segments):
        a = i * 2 * math.pi / segments
        for j in range(8):
            b = j * 2 * math.pi / 8
            r = major + minor * math.cos(b)
            points.append((r * math.cos(a), r * math.sin(a), minor * math.sin(b)))
    for i in range(segments):
        for j in range(8):
            n = i * 8 + j
            faces.append((n, i * 8 + (j + 1) % 8,
                          ((i + 1) % segments) * 8 + (j + 1) % 8,
                          ((i + 1) % segments) * 8 + j))
    mesh = bpy.data.meshes.new(name + " mesh")
    mesh.from_pydata(points, [], faces)
    mesh.materials.append(material)
    obj = put(bpy.data.objects.new(name, mesh), collection)
    obj.parent = parent
    obj.location = location
    obj.rotation_euler.x = rotate_x
    return obj


def label(collection, name, body, location, size, material,
          parent=None, face_front=True):
    data = bpy.data.curves.new(name + " text", "FONT")
    data.body = body
    data.size = size
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.extrude = 0.001
    data.materials.append(material)
    obj = put(bpy.data.objects.new(name, data), collection)
    obj.parent = parent
    obj.location = location
    if face_front:
        obj.rotation_euler.x = math.pi / 2
    return obj


def empty(collection, name, location=(0, 0, 0)):
    obj = put(bpy.data.objects.new(name, None), collection)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.28
    obj.location = location
    return obj


def area_light(collection, name, location, target, energy, color, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = size
    obj = put(bpy.data.objects.new(name, data), collection)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def camera(collection, name, location, target, lens=38):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    obj = put(bpy.data.objects.new(name, data), collection)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def new_collection(scene, name):
    collection = bpy.data.collections.new(name)
    scene.collection.children.link(collection)
    return collection


def clone_character(source_name, collection, prefix, location):
    source = bpy.data.objects[source_name + " • move entire character"]
    copies = {}
    root = source.copy()
    root.name = prefix + " | root"
    root.animation_data_clear()
    put(root, collection)
    root.parent = None
    root.location = location
    root.rotation_euler = (0, 0, 0)
    root.scale = (1, 1, 1)
    copies[source] = root
    for child in source.children_recursive:
        # The exterior scene's START prop is parented to its auditor; it must
        # not appear on the battle, referee, or ending actor duplicates.
        if "START" in child.name:
            continue
        copied = child.copy()
        copied.name = prefix + " | " + child.name
        copied.animation_data_clear()
        if child.data:
            copied.data = child.data.copy()
        put(copied, collection)
        copied.parent = copies[child.parent]
        copied.matrix_basis = child.matrix_basis.copy()
        copies[child] = copied
        if source_name == "Auditor" and "Clipboard" in child.name or (
            source_name == "Auditor" and "Audit clipboard" in child.name
        ):
            copied.hide_render = True
            copied.hide_viewport = True
    return root, copies


def add_tablet(collection, auditor):
    back = box(collection, "Auditor | referee tablet", (0.42, -0.54, 1.05),
               (0.57, 0.08, 0.68), INK, 0.04, auditor)
    glass = box(collection, "Auditor | tablet display", (0.42, -0.591, 1.05),
                (0.47, 0.01, 0.56), SCREEN_DARK, 0.015, auditor)
    for index in range(3):
        box(collection, "Auditor | tablet evidence line", (0.42, -0.602, 1.18 - index * 0.13),
            (0.3, 0.005, 0.023), BLUE_GLOW, parent=auditor)
    back["display_role"] = "referee evidence only; no ground truth in arena"
    return back, glass


brand_image = bpy.data.images.load(str(BRAND_REFERENCE), check_existing=True)
brand_image.name = "RowdyHacks 2026 supplied brand reference (packed)"
brand_image.pack()
brand_material = bpy.data.materials.new("Arena | supplied RH emblem crop")
brand_material.use_nodes = True
bsdf = brand_material.node_tree.nodes.get("Principled BSDF")
image_node = brand_material.node_tree.nodes.new("ShaderNodeTexImage")
image_node.image = brand_image
brand_material.node_tree.links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])


def logo_patch(collection, name, x, y, z, width):
    # Crop the circle from the supplied poster via UVs; the original image is packed.
    half = width / 2
    verts = [(-half, 0, -half), (half, 0, -half),
             (half, 0, half), (-half, 0, half)]
    mesh = bpy.data.meshes.new(name + " mesh")
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="Brand crop")
    coords = [(0.19, 0.435), (0.56, 0.435), (0.56, 0.72), (0.19, 0.72)]
    for loop in mesh.loops:
        uv.data[loop.index].uv = coords[loop.vertex_index]
    mesh.materials.append(brand_material)
    obj = put(bpy.data.objects.new(name, mesh), collection)
    obj.location = (x, y, z)
    return obj


def banner(collection, x, y, z, scale=1):
    w, h = 1.6 * scale, 2.65 * scale
    box(collection, "RowdyHacks | ivory hanging banner", (x, y, z),
        (w, 0.035, h), PAPER, 0.025)
    box(collection, "RowdyHacks | top rail", (x, y - 0.035, z + h / 2),
        (w + 0.14, 0.085, 0.08), BRASS, 0.02)
    logo_patch(collection, "RowdyHacks | exact supplied RH emblem", x,
               y - 0.045, z + 0.25 * scale, 1.27 * scale)
    label(collection, "RowdyHacks | banner name", "ROWDYHACKS", (x, y - 0.06, z - 0.58 * scale),
          0.19 * scale, INK)
    label(collection, "RowdyHacks | banner year", "2026", (x, y - 0.06, z - 0.91 * scale),
          0.23 * scale, CRIMSON)


def scene_setup(scene, end):
    scene.frame_start = 1
    scene.frame_end = end
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new(scene.name + " | warm world")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.16, 0.13, 0.11, 1)
    background.inputs["Strength"].default_value = 0.65
    scene["source_mode"] = "fixture_preview"
    scene["mission"] = "protected vault-data access; website availability is separate"
    scene["verdict_source"] = "independent referee, never a character animation"


def key_location(obj, frames_and_locations):
    for frame, loc in frames_and_locations:
        obj.location = loc
        obj.keyframe_insert(data_path="location", frame=frame)


def corner_result(collection, cam, text_body, accent):
    plate = box(collection, text_body + " | subtle result plaque", (-2.65, -1.70, -7.0),
                (1.72, 0.29, 0.025), INK, 0.025, cam)
    # In camera-local coordinates, text lies in the XY plane and faces the camera.
    label(collection, text_body + " | caption", text_body,
          (-2.65, -1.70, -6.96), 0.125, UI_IVORY, parent=cam, face_front=False)
    plate["verdict_ui"] = "show only after independent referee result"
    plate["accent_team"] = accent


# ---------------------------------------------------------------------------
# 01 / Exterior setup and walk-in; augment the already-open source scene.
# ---------------------------------------------------------------------------
exterior = bpy.data.scenes[0]
exterior.name = "01 • Exterior / Start and Walk-in"
scene_setup(exterior, 108)
for old, color in {
    "Asphalt": (0.07, 0.068, 0.07),
    "Ground": (0.19, 0.16, 0.12),
    "Bank stone": (0.49, 0.42, 0.33),
    "Sandstone": (0.80, 0.73, 0.61),
    "Ivory": (0.88, 0.83, 0.72),
    "Ink": (0.03, 0.03, 0.035),
    "Red": (0.62, 0.045, 0.035),
    "Slate blue": (0.23, 0.24, 0.25),
    "Roof blue": (0.34, 0.33, 0.31),
}.items():
    source_material = bpy.data.materials.get(old)
    if source_material:
        source_material.diffuse_color = (*color, 1)
        if source_material.use_nodes:
            source_material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*color, 1)

ext_art = new_collection(exterior, "ARENA | Exterior additions")
banner(ext_art, -2.95, 2.01, 3.65, 0.67)
banner(ext_art, 2.95, 2.01, 3.65, 0.67)
auditor_ext = bpy.data.objects["Auditor • move entire character"]
for child in auditor_ext.children:
    if "Clipboard" in child.name or "Audit clipboard" in child.name:
        child.hide_render = True
        child.hide_viewport = True
start_parts = [
    box(ext_art, "Auditor | START tray", (0, -0.66, 1.15), (0.92, 0.14, 0.61), INK, 0.08, auditor_ext),
    cylinder(ext_art, "Auditor | START button", (0, -0.76, 1.16), 0.36, 0.13,
             RED_GLOW, parent=auditor_ext, rotate_x=math.pi / 2),
    label(ext_art, "Auditor | START lettering", "START", (0, -0.844, 1.16),
          0.16, PAPER, auditor_ext),
]
for part in start_parts:
    part["interactive_anchor"] = "session.start (website control, not a Blender click handler)"
    part.scale = (1, 1, 1)
    part.keyframe_insert(data_path="scale", frame=1)
    part.keyframe_insert(data_path="scale", frame=22)
    part.scale = (0.001, 0.001, 0.001)
    part.keyframe_insert(data_path="scale", frame=23)

for role, path in {
    "Robber": [(1, (-3.4, -1.55, 0.25)), (24, (-3.4, -1.55, 0.25)),
               (70, (-1.05, 0.95, 0.25)), (96, (-0.6, 2.55, 0.25))],
    "Officer": [(1, (3.3, -1.5, 0.25)), (24, (3.3, -1.5, 0.25)),
                (70, (1.05, 0.95, 0.25)), (96, (0.6, 2.55, 0.25))],
    "Auditor": [(1, (0.3, -6.1, 0.25)), (24, (0.3, -6.1, 0.25)),
                (70, (0, 0.75, 0.25)), (104, (0, 2.58, 0.25))],
}.items():
    actor = bpy.data.objects[role + " • move entire character"]
    key_location(actor, path)
    for frame, rotation in [(1, 0), (24, 0), (38, math.pi), (108, math.pi)]:
        actor.rotation_euler.z = rotation
        actor.keyframe_insert(data_path="rotation_euler", frame=frame)
    for frame, rise in [(24, 0), (32, 0.06), (40, 0), (48, 0.06),
                        (56, 0), (64, 0.06), (72, 0), (80, 0.06), (88, 0)]:
        actor.scale.z = 1 + rise
        actor.keyframe_insert(data_path="scale", frame=frame)
exterior.camera = camera(ext_art, "Arena | exterior presentation camera",
                         (0, -23.0, 7.5), (0, -0.2, 2.3), 42)
area_light(ext_art, "Arena | exterior warm key", (0, -5.5, 12), (0, 1, 2),
           2400, (1, 0.77, 0.49), 8)
for frame, name in [(1, "Choose Scout / Operator and Monitor / Defender"),
                    (24, "START click / begin walk-in"),
                    (108, "Cut to battle room")]:
    exterior.timeline_markers.new(name, frame=frame)
exterior.frame_set(1)


# ---------------------------------------------------------------------------
# Shared arena set. This SAME collection is linked into battle and Blue scenes.
# ---------------------------------------------------------------------------
battle = bpy.data.scenes.new("02 • Battle / BEGIN and Live Screens")
scene_setup(battle, 360)
arena_set = new_collection(battle, "ARENA | Shared battle-room set")
blue_scene = bpy.data.scenes.new("04 • Blue Win / Same Battle Room")
scene_setup(blue_scene, 96)
blue_scene.collection.children.link(arena_set)

box(arena_set, "Bank interior | reflective charcoal floor", (0, 2.3, -0.11),
    (16.2, 13, 0.22), FLOOR, 0.05)
box(arena_set, "Bank interior | back wall", (0, 8.58, 3.2),
    (16.2, 0.35, 6.4), CHARCOAL, 0.05)
for x in (-8, 8):
    box(arena_set, "Bank interior | side wall", (x, 2.3, 3.2),
        (0.22, 12.7, 6.4), CHARCOAL)
box(arena_set, "Bank interior | ceiling", (0, 2.3, 6.45),
    (16.2, 13, 0.2), INK)
for x in (-6.5, -3.8, -1.1, 1.6, 4.3, 7.0):
    for y in (-1.3, 2.0, 5.3):
        box(arena_set, "Bank interior | ceiling light", (x, y, 6.31),
            (1.1, 0.36, 0.04), WARM_GLOW, 0.04)
for x in (-6.9, 6.9):
    for z in (0.8, 2.6, 4.5):
        box(arena_set, "Bank interior | wall gold rib", (x, 8.31, z),
            (0.12, 0.045, 1.15), BRASS, 0.02)
for x in (-1.75, 1.75):
    box(arena_set, "Battle aisle | brass guide line", (x, 2.2, 0.015),
        (0.055, 11.5, 0.025), BRASS)
box(arena_set, "Red zone | edge strip", (-5.1, -1.8, 0.018),
    (5.6, 0.08, 0.035), RED_GLOW)
box(arena_set, "Blue zone | edge strip", (5.1, -1.8, 0.018),
    (5.6, 0.08, 0.035), BLUE_GLOW)

# Closed vault, physically behind the same jumbotron in both arena scenes.
cylinder(arena_set, "Battle vault | dark recess", (0, 8.20, 2.15), 1.72, 0.18,
         INK, rotate_x=math.pi / 2)
torus(arena_set, "Battle vault | brass door ring", (0, 8.07, 2.15), 1.56, 0.09,
      BRASS, rotate_x=math.pi / 2)
cylinder(arena_set, "Battle vault | sealed disk", (0, 8.0, 2.15), 1.43, 0.12,
         CHARCOAL, rotate_x=math.pi / 2)
torus(arena_set, "Battle vault | central brass ring", (0, 7.91, 2.15), 0.65, 0.06,
      BRASS, rotate_x=math.pi / 2)
cylinder(arena_set, "Battle vault | hub", (0, 7.82, 2.15), 0.18, 0.14,
         BRASS, rotate_x=math.pi / 2)
for i in range(12):
    angle = 2 * math.pi * i / 12
    cylinder(arena_set, "Battle vault | perimeter bolt",
             (1.51 * math.cos(angle), 7.87, 2.15 + 1.51 * math.sin(angle)),
             0.047, 0.075, BRASS, vertices=12, rotate_x=math.pi / 2)
for i in range(8):
    angle = 2 * math.pi * i / 8
    spoke = box(arena_set, "Battle vault | spoke",
                (0.44 * math.cos(angle), 7.89, 2.15 + 0.44 * math.sin(angle)),
                (0.78, 0.055, 0.06), BRASS)
    spoke.rotation_euler.y = -angle

banner(arena_set, -6.25, 7.95, 4.93)
banner(arena_set, 6.25, 7.95, 4.93)

# Three intentionally separate screen anchors; content here is preview-only.
box(arena_set, "BANK_WEBSITE_SCREEN | black housing", (0, 7.76, 5.15),
    (8.2, 0.25, 2.15), INK, 0.13)
bank_screen = box(arena_set, "BANK_WEBSITE_SCREEN | fixture surface", (0, 7.60, 5.15),
                  (7.78, 0.018, 1.79), SCREEN, 0.03)
bank_screen["screen_role"] = "registered fictional bank website; web runtime replaces this fixture"
bank_screen["source_mode"] = "fixture_preview"
label(arena_set, "Bank screen | title", "BANK LAB", (-2.60, 7.575, 5.70), 0.37, INK)
label(arena_set, "Bank screen | source label", "FIXTURE PREVIEW", (2.38, 7.575, 5.70), 0.19, CRIMSON)
box(arena_set, "Bank screen | header rule", (0, 7.56, 5.39), (7.3, 0.008, 0.025), BRASS)
label(arena_set, "Bank screen | home heading", "Welcome to your bank", (-1.63, 7.55, 4.98), 0.35, INK)
for i, width in enumerate((2.9, 2.3, 1.65)):
    box(arena_set, "Bank screen | website body line", (0.4, 7.54, 5.08 - i * 0.25),
        (width, 0.008, 0.045), IVORY)
box(arena_set, "Bank screen | health indicator", (3.24, 7.53, 4.59),
    (0.17, 0.012, 0.17), BLUE_GLOW, 0.03)
label(arena_set, "Bank screen | health label", "TARGET HEALTH", (2.38, 7.52, 4.60), 0.15, INK)

for team, x, accent, headings in [
    ("RED_ACTIVITY_SCREEN", -5.1, RED_GLOW, ("SCOUT", "OPERATOR")),
    ("BLUE_ACTIVITY_SCREEN", 5.1, BLUE_GLOW, ("MONITOR", "DEFENDER")),
]:
    box(arena_set, team + " | desk", (x, 0.33, 0.54), (3.7, 1.35, 0.18),
        CHARCOAL, 0.08)
    for dx in (-1.45, 1.45):
        box(arena_set, team + " | desk leg", (x + dx, 0.48, 0.27),
            (0.13, 0.92, 0.55), INK)
    box(arena_set, team + " | accent", (x, -0.37, 0.48),
        (3.6, 0.035, 0.055), accent)
    box(arena_set, team + " | monitor frame", (x, 0.06, 1.78),
        (2.9, 0.16, 1.50), INK, 0.07)
    surface = box(arena_set, team + " | fixture display", (x, -0.033, 1.78),
                  (2.67, 0.016, 1.25), SCREEN_DARK, 0.03)
    surface["screen_role"] = "judge-safe team activity; no private board or secrets"
    surface["source_mode"] = "fixture_preview"
    for index, heading in enumerate(headings):
        label(arena_set, team + " | " + heading, heading,
              (x - 0.62 + index * 1.24, -0.051, 2.18), 0.17, accent)
    for index in range(5):
        line_width = 1.8 - (index % 3) * 0.29
        box(arena_set, team + " | event line", (x - 0.23, -0.052, 1.92 - index * 0.19),
            (line_width, 0.006, 0.025), PAPER if index % 3 else accent)
    keyboard_x = x + (1.45 if team.startswith("RED") else -1.45)
    box(arena_set, team + " | keyboard", (keyboard_x, -0.25, 0.73),
        (1.65, 0.37, 0.055), INK, 0.02)
    box(arena_set, team + " | chair", (x, 1.58, 0.48),
        (1.05, 0.69, 0.18), INK, 0.08)
    box(arena_set, team + " | chair back", (x, 1.85, 1.02),
        (1.05, 0.14, 0.95), INK, 0.08)

arena_cam = camera(arena_set, "Arena | LOCKED battle and Blue camera",
                   (0, -13.0, 4.75), (0, 3.2, 2.82), 33)
battle.camera = arena_cam
blue_scene.camera = arena_cam
area_light(arena_set, "Arena | warm front key", (0, -3, 5.8), (0, 2, 1),
           2400, (1, 0.79, 0.57), 8)
area_light(arena_set, "Arena | left red accent", (-6, 2.4, 4), (-5, 0, 1),
           700, (1, 0.15, 0.08), 5)
area_light(arena_set, "Arena | right blue accent", (6, 2.4, 4), (5, 0, 1),
           700, (0.11, 0.38, 1), 5)


# ---------------------------------------------------------------------------
# 02 / Battle character motion and BEGIN cue.
# ---------------------------------------------------------------------------
battle_actors = new_collection(battle, "ARENA | Battle actors and BEGIN")
red_root, red_copies = clone_character("Robber", battle_actors, "Battle Robber", (-3.40, 0.15, 0.02))
blue_root, blue_copies = clone_character("Officer", battle_actors, "Battle Officer", (3.40, 0.15, 0.02))
audit_root, _ = clone_character("Auditor", battle_actors, "Battle Auditor", (0, -0.45, 0.02))
add_tablet(battle_actors, audit_root)
for actor in (red_root, blue_root):
    actor.scale = (0.90, 0.90, 0.90)
    for frame, y in [(1, 0.15), (24, 0.15), (55, 0.15), (360, 0.15)]:
        actor.location.y = y
        actor.keyframe_insert(data_path="location", frame=frame)
    typing_hands = [child for child in actor.children if " hand" in child.name]
    for child in typing_hands:
        child.location.y = -0.34
        child.location.z = 0.79
        child.keyframe_insert(data_path="location", frame=1)
        child.keyframe_insert(data_path="location", frame=38)
    for frame in range(42, 361, 12):
        for index, child in enumerate(typing_hands):
            child.location.z = 0.79 + (0.045 if (frame // 12 + index) % 2 else -0.025)
            child.location.y = -0.34 + (0.025 if (frame // 12 + index) % 2 else 0)
            child.keyframe_insert(data_path="location", frame=frame)
begin = label(battle_actors, "BEGIN | fixture visual cue", "BEGIN",
              (0, 0.10, -7.0), 0.92, UI_IVORY, arena_cam, face_front=False)
begin["display_rule"] = "show only after start and walk-in, not proof of a live run"
begin.scale = (0.001, 0.001, 0.001)
begin.keyframe_insert(data_path="scale", frame=1)
begin.scale = (1, 1, 1)
begin.keyframe_insert(data_path="scale", frame=8)
begin.keyframe_insert(data_path="scale", frame=31)
begin.scale = (0.001, 0.001, 0.001)
begin.keyframe_insert(data_path="scale", frame=38)
for frame, name in [(1, "Walk-in complete"), (8, "BEGIN"),
                    (38, "Fixture typing loop / await live events"),
                    (360, "Referee verdict required")]:
    battle.timeline_markers.new(name, frame=frame)
battle.frame_set(62)


# ---------------------------------------------------------------------------
# 04 / Blue ending uses the SAME set collection and camera as the battle.
# ---------------------------------------------------------------------------
blue_actors = new_collection(blue_scene, "ARENA | Blue arrest actors")
blue_red, _ = clone_character("Robber", blue_actors, "Blue End Robber", (-3.40, 0.15, 0.02))
blue_cop, _ = clone_character("Officer", blue_actors, "Blue End Officer", (3.40, 0.15, 0.02))
blue_auditor, _ = clone_character("Auditor", blue_actors, "Blue End Auditor", (0, -0.45, 0.02))
add_tablet(blue_actors, blue_auditor)
key_location(blue_red, [(1, (-3.40, 0.15, 0.02)), (32, (-2.25, 0.55, 0.02)),
                        (62, (-0.18, 0.15, 0.02)), (96, (-0.18, 0.15, 0.02))])
key_location(blue_cop, [(1, (3.40, 0.15, 0.02)), (32, (2.0, 0.55, 0.02)),
                        (62, (0.66, 0.12, 0.02)), (96, (0.66, 0.12, 0.02))])
key_location(blue_auditor, [(1, (0, -0.45, 0.02)), (32, (-2.15, -0.42, 0.02)),
                            (96, (-2.15, -0.42, 0.02))])
for x in (-0.75, 0.75):
    cuff = torus(blue_actors, "Blue arrest | cartoon cuff", (x, -0.10, 0.88),
                 0.145, 0.025, BRASS, parent=blue_red, rotate_x=math.pi / 2)
    cuff.scale = (0.001, 0.001, 0.001)
    cuff.keyframe_insert(data_path="scale", frame=1)
    cuff.keyframe_insert(data_path="scale", frame=52)
    cuff.scale = (1, 1, 1)
    cuff.keyframe_insert(data_path="scale", frame=62)
corner_result(blue_actors, arena_cam, "BLUE TEAM WINS", "blue")
for frame, name in [(1, "Referee confirms vault data protected"),
                    (32, "Cop crosses SAME battle room"),
                    (62, "Cartoon arrest / BLUE TEAM WINS")]:
    blue_scene.timeline_markers.new(name, frame=frame)
blue_scene.frame_set(72)


# ---------------------------------------------------------------------------
# 03 / Red ending: a separate vault chamber and camera cut.
# ---------------------------------------------------------------------------
red_scene = bpy.data.scenes.new("03 • Red Win / Inside Vault")
scene_setup(red_scene, 132)
vault = new_collection(red_scene, "ARENA | Separate vault chamber")
box(vault, "Vault chamber | floor", (0, 2.0, -0.12), (13.8, 10.8, 0.24),
    FLOOR, 0.06)
box(vault, "Vault chamber | back wall", (0, 7.2, 3.4), (13.8, 0.28, 6.8),
    CHARCOAL)
for x in (-6.8, 6.8):
    box(vault, "Vault chamber | side wall", (x, 2.0, 3.4),
        (0.24, 10.8, 6.8), CHARCOAL)
box(vault, "Vault chamber | dark ceiling", (0, 2.0, 6.85),
    (13.8, 10.8, 0.22), INK)
for x in (-5.5, 5.5):
    for z in (1.0, 2.5, 4.0, 5.5):
        box(vault, "Vault chamber | light rib", (x, 6.98, z),
            (0.12, 0.04, 0.85), WARM_GLOW)
for x in (-4.9, 4.9):
    for z in (0.8, 2.2, 3.6):
        box(vault, "Vault chamber | bullion shelf", (x, 4.85, z),
            (1.5, 1.9, 0.13), BRASS, 0.02)
        for dx in (-0.38, 0.0, 0.38):
            box(vault, "Vault chamber | stylized bullion", (x + dx, 4.85, z + 0.16),
                (0.33, 0.55, 0.16), GOLD, 0.03)

# Open gear-lined vault door, inspired by Omar's approved vault photo.
cylinder(vault, "Open vault | black wall recess", (1.1, 6.93, 2.60),
         2.25, 0.18, INK, rotate_x=math.pi / 2)
torus(vault, "Open vault | outer brass ring", (1.1, 6.78, 2.60),
      2.13, 0.14, BRASS, rotate_x=math.pi / 2)
torus(vault, "Open vault | gear ring", (1.1, 6.73, 2.60),
      1.72, 0.08, GOLD, rotate_x=math.pi / 2)
for i in range(22):
    angle = i * 2 * math.pi / 22
    bolt = cylinder(vault, "Open vault | perimeter bolt",
                    (1.1 + 2.12 * math.cos(angle), 6.58,
                     2.60 + 2.12 * math.sin(angle)),
                    0.065, 0.09, GOLD, vertices=12, rotate_x=math.pi / 2)
door_hinge = empty(vault, "Open vault | animated door hinge", (3.48, 6.56, 2.6))
door_disk = cylinder(vault, "Open vault | open door disk", (-2.0, -0.18, 0),
                     1.98, 0.33, CHARCOAL, parent=door_hinge, rotate_x=math.pi / 2)
torus(vault, "Open vault | door brass edge", (-2.0, -0.39, 0),
      1.8, 0.09, GOLD, parent=door_hinge, rotate_x=math.pi / 2)
torus(vault, "Open vault | door central gear", (-2.0, -0.42, 0),
      0.86, 0.07, BRASS, parent=door_hinge, rotate_x=math.pi / 2)
for i in range(16):
    angle = i * 2 * math.pi / 16
    cylinder(vault, "Open vault | door bolt",
             (-2.0 + 1.77 * math.cos(angle), -0.47, 1.77 * math.sin(angle)),
             0.055, 0.07, GOLD, vertices=12, parent=door_hinge,
             rotate_x=math.pi / 2)
for frame, angle in [(1, 0), (35, 0.85), (56, 1.13), (132, 1.13)]:
    door_hinge.rotation_euler.z = angle
    door_hinge.keyframe_insert(data_path="rotation_euler", frame=frame)

red_actors = new_collection(red_scene, "ARENA | Red victory actor and cash")
vault_robber, _ = clone_character("Robber", red_actors, "Vault Robber", (1.1, 7.1, 0.02))
key_location(vault_robber, [(1, (1.1, 7.1, 0.02)),
                            (56, (1.1, 6.5, 0.02)),
                            (87, (-2.2, 1.9, 0.02)),
                            (132, (-2.2, 1.9, 0.02))])
for frame, angle in [(1, 0.0), (56, 0.0), (70, math.pi * 0.85),
                     (87, 0.0), (132, 0.0)]:
    vault_robber.rotation_euler.z = angle
    vault_robber.keyframe_insert(data_path="rotation_euler", frame=frame)
random.seed(26)
for i in range(55):
    x = random.uniform(-4.5, 4.6)
    y = random.uniform(1.1, 5.8)
    start = random.randint(72, 104)
    bill = box(red_actors, f"Cash rain | symbolic bill {i:02d}",
               (x, y, random.uniform(3.8, 6.1)),
               (0.35, 0.17, 0.008), PAPER, 0.003)
    bill["meaning"] = "celebration only; actual objective is verified vault-data access"
    bill.keyframe_insert(data_path="location", frame=start)
    bill.rotation_euler = (0, 0, random.uniform(-math.pi, math.pi))
    bill.keyframe_insert(data_path="rotation_euler", frame=start)
    bill.location.z = 0.08
    bill.location.x += random.uniform(-0.7, 0.7)
    bill.keyframe_insert(data_path="location", frame=min(start + 42, 132))
    bill.rotation_euler.z += random.uniform(2.0, 5.5)
    bill.keyframe_insert(data_path="rotation_euler", frame=min(start + 42, 132))
for i in range(7):
    x = -4.0 + i * 1.15
    box(red_actors, "Vault | banknote stack", (x, 2.9 + (i % 2) * 1.25, 0.2),
        (0.7, 0.32, 0.3), PAPER, 0.02)
    box(red_actors, "Vault | banknote stack band", (x, 2.9 + (i % 2) * 1.25, 0.36),
        (0.15, 0.34, 0.02), BRASS)

vault_cam = camera(vault, "Arena | separate vault celebration camera",
                   (0.3, -10.4, 4.5), (0.8, 4.6, 2.45), 36)
red_scene.camera = vault_cam
area_light(vault, "Vault | warm key", (0, 1, 6.2), (0, 4, 2),
           2400, (1, 0.77, 0.45), 7)
area_light(vault, "Vault | gold rim light", (4.4, 5.1, 5.3), (1, 5, 2),
           1200, (1, 0.53, 0.20), 4)
corner_result(red_actors, vault_cam, "RED TEAM WINS", "red")
for frame, name in [(1, "Referee confirms vault-data access"),
                    (35, "Vault door opens"),
                    (56, "Camera cuts INSIDE vault"),
                    (87, "Robber enters vault"),
                    (104, "Cash-rain celebration (metaphor)")]:
    red_scene.timeline_markers.new(name, frame=frame)
red_scene.frame_set(108)


# Reopen battle room in the same visible Blender window for Omar.
bpy.context.window.scene = battle
battle.frame_set(62)
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        space = area.spaces.active
        space.region_3d.view_perspective = "CAMERA"
        space.shading.type = "MATERIAL"
        space.overlay.show_overlays = False

bpy.ops.wm.save_mainfile()
__result__ = {
    "blend": bpy.data.filepath,
    "scenes": [(s.name, len(s.objects), s.frame_end) for s in bpy.data.scenes],
    "shared_battle_set": arena_set.name,
    "shared_blue_set": arena_set.name in [c.name for c in blue_scene.collection.children],
    "brand_image_packed": brand_image.packed_file is not None,
    "status": "fixture-preview Blender visuals; live bank/events/verdict require website and core",
}
