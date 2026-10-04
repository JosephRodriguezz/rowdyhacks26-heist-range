"""Rebuild the heist district with Blender 4.2+ (no external assets required).

blender --background --factory-startup --python build_heist.py
"""
import bpy
import math
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != 'Collection':
        bpy.data.collections.remove(c)
ROOT = bpy.data.collections.get('Collection')
ROOT.name = 'HEIST DISTRICT'
ACTIVE = ROOT

def group(name):
    global ACTIVE
    ACTIVE = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(ACTIVE)
    return ACTIVE

def finish(obj, name, mat=None, parent=None):
    obj.name = name
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    ACTIVE.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    if parent:
        obj.parent = parent
    return obj

def material(name, rgb, metallic=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*rgb, 1)
    p.inputs['Roughness'].default_value = .72
    p.inputs['Metallic'].default_value = metallic
    return m

M = {k: material(k, v) for k, v in {
    'Asphalt':(.055,.085,.12), 'Ground':(.15,.23,.22),
    'Curb':(.35,.45,.46), 'Ivory':(.82,.80,.66),
    'Bank stone':(.48,.46,.35), 'Sandstone':(.68,.64,.49),
    'Slate blue':(.23,.34,.43), 'Roof blue':(.38,.52,.59),
    'Terracotta':(.49,.34,.30), 'Warm roof':(.65,.52,.40),
    'Mint glass':(.49,.70,.63), 'Leaf':(.24,.48,.37),
    'Leaf light':(.33,.58,.44), 'Bark':(.30,.29,.22),
    'Ink':(.035,.055,.083), 'White':(.92,.95,.95),
    'Skin':(.87,.65,.43), 'Red':(.68,.29,.32),
    'Uniform':(.34,.47,.73), 'Gold':(.92,.70,.24),
    'Auditor gray':(.48,.57,.63), 'Lavender':(.54,.66,.92),
}.items()}

def box(name, loc, scale, mat, bevel=.06, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = finish(bpy.context.object, name, mat, parent)
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        b = o.modifiers.new('Soft edges', 'BEVEL')
        b.width = bevel
        b.segments = 3
        o.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return o

def sphere(name, loc, scale, mat, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1, location=loc)
    o = finish(bpy.context.object, name, mat, parent)
    o.scale = scale
    for p in o.data.polygons:
        p.use_smooth = True
    return o

def cylinder(name, loc, radius, depth, mat, parent=None, vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    o = finish(bpy.context.object, name, mat, parent)
    b = o.modifiers.new('Edge softness','BEVEL')
    b.width = .035
    b.segments = 2
    o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return o

def rod(name, a, b, radius, mat, parent=None):
    a, b = Vector(a), Vector(b)
    o = cylinder(name, (a+b)/2, radius, (b-a).length, mat, parent)
    o.rotation_euler = (b-a).to_track_quat('Z','Y').to_euler()
    return o

def text(name, body, loc, size, mat, parent=None):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.size = size
    cu.extrude = .008
    cu.bevel_depth = .002
    o = bpy.data.objects.new(name, cu)
    ACTIVE.objects.link(o)
    o.location = loc
    o.rotation_euler = (math.pi/2, 0, 0)
    cu.materials.append(mat)
    if parent:
        o.parent = parent
    return o

def mesh(name, vertices, faces, mat, parent=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(vertices, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    ACTIVE.objects.link(o)
    me.materials.append(mat)
    if parent:
        o.parent = parent
    return o

def extrude_profile(name, profile, front, back, mat):
    n = len(profile)
    v = [(x, front, z) for x,z in profile] + [(x,back,z) for x,z in profile]
    faces = [tuple(range(n-1,-1,-1)), tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh(name,v,faces,mat)

def plaque(title, subtitle, x, y, z, width=2.5, accent=None):
    box(title+' plaque',(x,y,z),(width,.13,.58),M['Ink'],.08)
    text(title+' lettering',title,(x,y-.08,z+.08),.23,M['White'])
    if subtitle:
        text(title+' subtitle',subtitle,(x,y-.082,z-.18),.115,accent or M['Mint glass'])

group('01 • Streets and district base')
box('Rounded district plinth',(0,1,-.38),(23,21,.65),M['Ink'],.5)
box('District ground',(0,1,-.02),(22.7,20.7,.20),M['Ground'],.35)
box('Vault Avenue',(0,-3,.12),(22.7,4,.12),M['Asphalt'],.04)
for x in [-8,8]:
    box('Side street',(x,2,.112),(2.8,18.6,.12),M['Asphalt'],.04)
    for edge in [-1.52,1.52]:
        box('Sidewalk curb',(x+edge,2,.16),(.16,18.7,.22),M['Curb'],.02)
for y in [-5.15,-.85]:
    box('Avenue sidewalk',(0,y,.17),(22.7,.25,.24),M['Curb'],.03)
for x in range(-10,11,2):
    box('Dashed avenue centerline',(x,-3,.19),(.85,.085,.014),M['Ivory'],.005)
for x in [-6.4,6.4]:
    for i in range(8):
        box('Pedestrian crossing',(x,-4.65+i*.46,.195),(1.05,.23,.02),M['White'],.008)
box('Bank plaza',(0,3,.16),(11.7,7.4,.20),M['Curb'],.12)
box('Bank plaza paving',(0,3,.29),(11.3,7,.08),M['Bank stone'],.08)
for x in range(-5,6):
    box('Plaza joint',(x,3,.335),(.018,6.8,.009),M['Sandstone'],0)

group('02 • Bank architecture')
box('Bank main hall',(0,4.6,2.5),(6.8,4.4,4.35),M['Bank stone'],.09)
box('Foundation',(0,4.6,.50),(7.25,4.8,.32),M['Sandstone'],.07)
box('Cornice',(0,4.6,4.70),(7.35,4.85,.28),M['Sandstone'],.06)
extrude_profile('Triangular bank pediment',[(-3.7,4.82),(3.7,4.82),(0,6.45)],2.10,6.95,M['Sandstone'])
text('BANK facade sign','B A N K',(0,2.075,5.35),.51,M['Ink'])
# A shallow arch-shaped entry overlay retains editable, clean geometry.
def arch(radius, bottom, spring):
    return [(-radius,bottom),(radius,bottom)] + [(radius*math.cos(i*math.pi/32),spring+radius*math.sin(i*math.pi/32)) for i in range(33)]
extrude_profile('Entry arch surround',arch(1.05,.64,2.25),2.30,2.42,M['Sandstone'])
extrude_profile('Dark arched entrance',arch(.87,.67,2.25),2.265,2.29,M['Ink'])
rod('Door center seam',(0,2.23,.7),(0,2.23,2.94),.015,M['Roof blue'])
for x in [-.13,.13]:
    rod('Brass door handle',(x,2.18,1.35),(x,2.18,1.66),.028,M['Gold'])
for x in [-2.45,2.45]:
    box('Column plinth',(x,2.17,.8),(.75,.78,.30),M['Sandstone'])
    cylinder('Bank column',(x,2.25,2.63),.28,3.4,M['Ivory'])
    box('Column capital',(x,2.22,4.38),(.74,.7,.23),M['Sandstone'])
for i in range(3):
    box('Entry step',(0,1.85-i*.34,.42-i*.08),(2.8+i*.45,.7,.20),M['Sandstone'],.025)
plaque('SECURITY GATE','API / ACCESS CONTROL',0,.82,.91,3.0,M['Lavender'])

group('03 • City buildings')
def building(name,x,y,w,d,h,wall,roof,sign=None):
    box(name,(x,y,.25+h/2),(w,d,h),M[wall],.08)
    box(name+' roof',(x,y,h+.30),(w+.12,d+.12,.15),M[roof],.04)
    box(name+' base',(x,y,.35),(w+.12,d+.12,.32),M['Ink'],.04)
    for xx in [-w*.28,0,w*.28]:
        for zz in range(1,int(h)):
            if sign and zz == 1:
                continue
            box(name+' window',(x+xx,y-d/2-.025,zz+.40),(.38,.06,.55),M['Mint glass'],.025)
    # Side windows make the models useful beyond the hero camera.
    for yy in [-d*.25,d*.25]:
        for zz in range(1,int(h)):
            box(name+' side window',(x+w/2+.026,y+yy,zz+.40),(.06,.40,.55),M['Mint glass'],.02)
    if sign:
        plaque(sign,'',x,y-d/2-.11,1.03,w*.9)
building('West offices',-10,6.8,2.2,2.5,5.8,'Slate blue','Roof blue')
building('Brick apartments',-5.3,8.5,2.4,2.4,5.4,'Terracotta','Warm roof')
building('North offices',4.6,8.4,2.1,2.4,6.1,'Slate blue','Roof blue')
building('Police headquarters',10,6.2,2.3,3.0,5.7,'Slate blue','Roof blue','POLICE')
building('Corner cafe',9.8,-6.7,2.3,2.4,3.2,'Terracotta','Warm roof','CAFE')
for x in [9.05,9.8,10.55]:
    box('Cafe awning stripe',(x,-8.03,1.58),(.72,.65,.12),M['Ivory'] if x==9.8 else M['Red'],.025)

group('04 • Park and trees')
box('Park border',(-7,-7,.18),(6,3.5,.25),M['Curb'],.3)
box('Park grass',(-7,-7,.32),(5.7,3.2,.10),M['Leaf'],.3)
def tree(x,y,s=1):
    cylinder('Tree trunk',(x,y,.30+.65*s),.14*s,1.3*s,M['Bark'])
    sphere('Tree crown',(x,y,.3+1.7*s),(.75*s,.72*s,.91*s),M['Leaf'])
    sphere('Tree crown highlight',(x-.24*s,y-.22*s,.3+1.89*s),(.56*s,.54*s,.67*s),M['Leaf light'])
for x,y,s in [(-5,3,1.1),(5,1.5,1.05),(-9,-7,1),(-5.5,-7.3,.85),(10,1.7,.78),(-10,2,.8)]:
    tree(x,y,s)
box('Park bench seat',(-7.5,-6.55,.70),(1.8,.48,.13),M['Warm roof'])
box('Park bench back',(-7.5,-6.35,1.03),(1.8,.12,.50),M['Warm roof'])
for x in [-8.15,-6.85]:
    box('Bench support',(x,-6.55,.49),(.1,.4,.4),M['Ink'])

group('05 • Service props')
def kiosk(x,y,title,subtitle,vault=False):
    box(title+' cabinet',(x,y,1.34),(1.7,1.25,2.05),M['Bank stone'] if vault else M['Slate blue'],.12)
    box(title+' canopy',(x,y,2.41),(1.9,1.40,.19),M['Ink'],.06)
    if vault:
        rim = cylinder('Vault rim',(x,y-.67,1.40),.68,.16,M['Ivory'])
        rim.rotation_euler.x = math.pi/2
        door = cylinder('Vault door',(x,y-.77,1.40),.55,.08,M['Ink'])
        door.rotation_euler.x = math.pi/2
        sphere('Vault hub',(x,y-.85,1.40),(.10,.07,.10),M['Gold'])
        for a in range(4):
            angle = a*math.pi/2+math.pi/4
            rod('Vault locking spoke',(x,y-.87,1.4),(x+.30*math.cos(angle),y-.87,1.4+.30*math.sin(angle)),.036,M['Gold'])
    else:
        box('Web terminal screen',(x,y-.67,1.49),(1.03,.08,.65),M['Ink'],.03)
        box('Web screen display',(x,y-.719,1.50),(.86,.015,.48),M['Mint glass'],.02)
        for i in range(3):
            box('Terminal interface line',(x-.12,y-.733,1.65-i*.13),(.47,.008,.025),M['Ivory'],0)
        box('Keyboard shelf',(x,y-.77,.94),(1.1,.46,.1),M['Ink'])
    plaque(title,subtitle,x,y-.87,.42,2.05)
kiosk(-5,0,'LOBBY','WEB',False)
kiosk(5.3,4,'VAULT','DATA',True)

group('06 • Vehicles')
def car(name,x,y,police=False):
    paint = M['Uniform'] if police else M['Leaf light']
    box(name+' body',(x,y,.65),(2.35,1.10,.55),paint,.20)
    box(name+' cabin',(x-.10,y,1.06),(1.23,.96,.48),M['White'] if police else paint,.16)
    box(name+' windshield',(x+.43,y,1.12),(.10,.78,.30),M['Mint glass'],.05)
    for xx in [-.37,.18]:
        box(name+' side glass',(x+xx,y-.49,1.12),(.40,.035,.29),M['Mint glass'],.045)
    for xx in [-.76,.76]:
        for yy in [-.55,.55]:
            tire = cylinder(name+' wheel',(x+xx,y+yy,.48),.28,.13,M['Ink'])
            tire.rotation_euler.x = math.pi/2
    for yy in [-.33,.33]:
        box(name+' headlights',(x+1.18,y+yy,.70),(.06,.19,.15),M['Ivory'],.025)
    if police:
        box('Police lightbar base',(x-.1,y,1.35),(.68,.24,.08),M['Ink'])
        for dx,mat in [(-.18,M['Red']),(.18,M['Lavender'])]:
            box('Police beacon',(x-.1+dx,y,1.45),(.32,.23,.16),mat,.05)
        text('Police car door','POLICE',(x,y-.571,.76),.16,M['White'])
car('Getaway compact',-9.0,-3.8)
car('Patrol car',5.8,-3.7,True)

def character_root(name,loc):
    group('Character • '+name)
    o = bpy.data.objects.new(name+' • move entire character',None)
    ACTIVE.objects.link(o)
    o.location = loc
    o.empty_display_type = 'PLAIN_AXES'
    o.empty_display_size = .3
    o['role'] = name
    return o

def character(name,loc,kind):
    p = character_root(name,loc)
    blue = kind=='officer'
    auditor = kind=='auditor'
    suit = M['Uniform'] if blue else M['Auditor gray'] if auditor else M['White']
    for x in [-.25,.25]:
        box(name+' trouser leg',(x,0,.48),(.32,.42,.72),M['Ink'] if not blue else M['Uniform'],.12,p)
        box(name+' shoe',(x,-.12,.17),(.4,.65,.24),M['Ink'],.10,p)
    box(name+' torso',(0,0,1.06),(.95,.54,.91),suit,.23,p)
    sphere(name+' head',(0,-.015,1.98),(.60,.47,.62),M['Skin'],p)
    if kind=='robber':
        for z in [.76,1.00,1.24,1.47]:
            box('Robber shirt stripe',(0,-.292,z),(.86,.035,.11),M['Ink'],.025,p)
        box('Robber eye mask',(0,-.453,2.05),(1.10,.12,.33),M['Ink'],.12,p)
        sphere('Robber beanie',(0,.005,2.42),(.63,.49,.30),M['Ink'],p)
        box('Beanie rim',(0,-.015,2.35),(1.26,.95,.13),M['Ink'],.06,p)
    elif blue:
        cylinder('Officer cap crown',(0,0,2.45),.58,.28,M['Uniform'],p)
        box('Officer cap visor',(0,-.28,2.34),(1.24,.84,.12),M['Uniform'],.08,p)
        sphere('Officer badge',(.21,-.297,1.24),(.13,.035,.16),M['Gold'],p)
        box('Officer belt',(0,-.01,.76),(.95,.57,.10),M['Ink'],.04,p)
        box('Officer belt buckle',(0,-.31,.76),(.13,.045,.12),M['Gold'],.015,p)
    else:
        sphere('Auditor hair',(0,.04,2.43),(.60,.47,.22),M['Ink'],p)
        for x in [-.25,.25]:
            box('Auditor glasses lens',(x,-.469,2.05),(.37,.09,.25),M['Ink'],.07,p)
            box('Auditor glasses glass',(x,-.522,2.06),(.26,.018,.14),M['Mint glass'],.025,p)
        rod('Auditor glasses bridge',(-.1,-.53,2.05),(.1,-.53,2.05),.027,M['Ink'],p)
        box('Auditor tie',(0,-.3,1.27),(.11,.05,.43),M['Ink'],.025,p)
    for x in [-.25,.25]:
        sphere(name+' eye',(x,-.534 if kind=='robber' else -.447,2.08),(.052,.025,.081),M['White'] if kind=='robber' else M['Ink'],p)
    for side in [-1,1]:
        rod(name+' sleeve',(side*.58,0,1.36),(side*.73,-.06,.92),.115,M['Red'] if kind=='robber' else suit,p)
        sphere(name+' hand',(side*.74,-.08,.87),(.13,.13,.15),M['Skin'],p)
    if kind=='robber':
        sphere('Loot bag',(.92,-.10,.65),(.32,.28,.40),M['Gold'],p)
        box('Loot bag gathered neck',(.85,-.10,1.02),(.16,.19,.20),M['Gold'],.045,p)
        text('Loot dollar','$',(.96,-.369,.66),.28,M['Warm roof'],p)
    if auditor:
        box('Audit clipboard',(.46,-.49,1.01),(.48,.12,.64),M['Sandstone'],.05,p)
        box('Clipboard paper',(.46,-.563,1.0),(.36,.015,.48),M['White'],.015,p)
        for z in [.86,.98,1.10]:
            box('Clipboard checklist',(.46,-.579,z),(.23,.012,.025),M['Slate blue'],0,p)
        box('Clipboard clip',(.46,-.58,1.30),(.17,.035,.10),M['Ink'],.02,p)
    # Independent parts parented in local coordinates for easy posing.
    return p

character('Robber',(-3.4,-1.55,.25),'robber')
character('Officer',(3.3,-1.50,.25),'officer')
character('Auditor',(.3,-6.1,.25),'auditor')
group('07 • Character labels and district signage')
for title,sub,x,y,accent in [('ROBBER','RED TEAM',-3.4,-2.34,M['Red']),('OFFICER','BLUE TEAM',3.3,-2.29,M['Lavender']),('AUDITOR','INDEPENDENT VERIFICATION',.3,-6.92,M['Mint glass'])]:
    plaque(title,sub,x,y,.59,2.35 if title!='AUDITOR' else 3.25,accent)
text('District title','DOWNTOWN / BANK DISTRICT',(0,-9.45,.50),.43,M['White'])
text('District subtitle','RANGE  /  TRAINING CITY  /  CONCEPT SCENE',(0,-9.46,.16),.19,M['Mint glass'])

group('08 • Camera and lighting')
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.resolution_x = 1500
scene.render.resolution_y = 1400
scene.render.resolution_percentage = 100
scene.world.color = (.24,.24,.24)
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.18,.24,.28,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .6
def area(name,loc,energy,color,size):
    d = bpy.data.lights.new(name,'AREA')
    d.energy = energy
    d.color = color
    d.shape = 'DISK'
    d.size = size
    o = bpy.data.objects.new(name,d)
    ACTIVE.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector((0,1,0))-o.location).to_track_quat('-Z','Y').to_euler()
area('Large warm key',(-10,-12,20),2400,(1,.88,.72),12)
area('Cool fill',(12,-4,14),1700,(.68,.80,1),10)
area('Bank rim',(0,12,18),2100,(1,.92,.80),9)
d = bpy.data.cameras.new('Isometric hero camera')
cam = bpy.data.objects.new('Isometric hero camera',d)
ACTIVE.objects.link(cam)
cam.location = (15,-26,24)
cam.rotation_euler = (Vector((0,1,1.8))-cam.location).to_track_quat('-Z','Y').to_euler()
d.type = 'ORTHO'
d.ortho_scale = 31.8
scene.camera = cam
scene.view_settings.view_transform = 'AgX'
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(OUT/'heist_district.png')
scene['asset_status'] = 'Concept art only: no live security execution or interactive application'
scene['reference'] = 'User supplied heist theme.png'
scene['character_editing'] = 'Move the character parent empties; child geometry uses local coordinates.'
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type == 'VIEW_3D':
            a.spaces.active.region_3d.view_perspective = 'CAMERA'
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'heist_district.blend'))
print('HEIST_BUILD_OK', len(scene.objects), 'objects', str(OUT/'heist_district.blend'))
if globals().get('args',{}).get('render',True):
    bpy.ops.render.render(write_still=True)
__result__ = {'blend':str(OUT/'heist_district.blend'),'render':str(OUT/'heist_district.png'),'objects':len(scene.objects)}
