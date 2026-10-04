"""Split the existing scene into teammate-ready Blender assets."""
import bpy
from pathlib import Path
from mathutils import Vector
import json

BASE = Path(__file__).resolve().parent
OUT = BASE / 'teammate_handoff'
OUT.mkdir(exist_ok=True)
SOURCE = BASE / 'heist_district.blend'
roles = ('Robber', 'Officer', 'Auditor')
reports = []

def camera(target, location, scale):
    cam = bpy.context.scene.camera
    cam.location = location
    cam.rotation_euler = (Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.ortho_scale = scale

def keep_object(obj, mode):
    collections = [c.name for c in obj.users_collection]
    lighting = any(c.startswith('08') for c in collections)
    character = next((r for r in roles if 'Character • '+r in collections), None)
    role_label = any(obj.name.startswith(r.upper()) for r in roles)
    if mode == 'setting':
        return not character and not role_label
    if mode == 'characters':
        return bool(character or role_label or lighting)
    return bool(character == mode or obj.name.startswith(mode.upper()) or lighting)

for mode, filename in [('setting','setting.blend'),('characters','characters.blend')] + [(r,r.lower()+'.blend') for r in roles]:
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    for obj in list(bpy.context.scene.objects):
        if not keep_object(obj, mode):
            bpy.data.objects.remove(obj, do_unlink=True)
    if mode == 'characters':
        camera((0,-3,1.3),(9,-19,13),12)
    elif mode in roles:
        root = bpy.data.objects[mode+' • move entire character']
        offset = root.location.copy()
        root.location = (0,0,0)
        for obj in bpy.context.scene.objects:
            if obj.name.startswith(mode.upper()):
                obj.location -= offset
        camera((0,0,1.1),(4,-8,4.6),4.2)
    for coll in list(bpy.data.collections):
        if not coll.objects and not coll.children:
            bpy.data.collections.remove(coll)
    scene = bpy.context.scene
    scene['handoff_asset'] = mode
    scene.render.filepath = str(OUT/(mode+'.png'))
    bpy.context.preferences.filepaths.save_version = 0
    path = OUT/filename
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    assert bpy.context.scene.camera
    if mode == 'setting':
        assert bpy.data.objects.get('Bank main hall')
        assert not any(o.name.endswith('• move entire character') for o in scene.objects)
    else:
        for role in roles if mode == 'characters' else (mode,):
            root = bpy.data.objects.get(role+' • move entire character')
            assert root and len(root.children)>=15
        assert not bpy.data.objects.get('Bank main hall')
    assert not any(o.library for o in bpy.context.scene.objects)
    reports.append({'file':filename,'objects':len(bpy.context.scene.objects),'reopened_and_verified':True})
(OUT/'verification.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
print('HANDOFF_OK',json.dumps(reports))
