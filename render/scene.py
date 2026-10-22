"""Bedford Falls hero film: late night on the patio.

Path-traced in Cycles. Every animated quantity is periodic over N frames so
frame N wraps exactly onto frame 0 (seamless loop).

usage: python scene.py --out DIR --w 1920 --h 1080 --samples 128 --frames 0:240[:step]
"""
import argparse
import math
import random
import sys

import bpy
import addon_utils
import bmesh
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--w", type=int, default=1920)
ap.add_argument("--h", type=int, default=1080)
ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--frames", default="0:1")
ap.add_argument("--total", type=int, default=240)
ap.add_argument("--blend", default="")
ap.add_argument("--probe", action="store_true")
args = ap.parse_args(sys.argv[1:])

N = args.total
TAU = math.pi * 2
rng = random.Random(1946)

addon_utils.enable("cycles", default_set=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- helpers

def mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out


def link(nt, a, b):
    nt.links.new(a, b)


def emission_mat(name, temp=2400, strength=20.0, color=None):
    m, nt, out = mat(name)
    em = nt.nodes.new("ShaderNodeEmission")
    if color is None:
        bb = nt.nodes.new("ShaderNodeBlackbody")
        bb.inputs["Temperature"].default_value = temp
        link(nt, bb.outputs[0], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    link(nt, em.outputs[0], out.inputs["Surface"])
    return m, em


def obj_from_mesh(name, verts, faces, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


def lathe(name, profile, segs=128, smooth=True):
    """Revolve a (r, z) profile around Z. r == 0 points collapse to the axis."""
    verts, faces, rings = [], [], []
    for r, z in profile:
        if r < 1e-9:
            rings.append([len(verts)])
            verts.append((0, 0, z))
        else:
            ring = []
            for i in range(segs):
                a = TAU * i / segs
                ring.append(len(verts))
                verts.append((r * math.cos(a), r * math.sin(a), z))
            rings.append(ring)
    for ra, rb in zip(rings, rings[1:]):
        if len(ra) == 1 and len(rb) == 1:
            continue
        if len(ra) == 1:
            for i in range(segs):
                faces.append((ra[0], rb[i], rb[(i + 1) % segs]))
        elif len(rb) == 1:
            for i in range(segs):
                faces.append((ra[i], rb[0], ra[(i + 1) % segs]))
        else:
            for i in range(segs):
                j = (i + 1) % segs
                faces.append((ra[i], rb[i], rb[j], ra[j]))
    ob = obj_from_mesh(name, verts, faces, smooth)
    # make normals point outward consistently
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def box(name, size, loc):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    return ob


def uv_sphere(name, r, loc, seg=24, rings=12, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=rings)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    bpy.ops.object.shade_smooth()
    return ob


def assign(ob, m):
    ob.data.materials.clear()
    ob.data.materials.append(m)


def hide_from_camera(ob):
    ob.visible_camera = False


# ---------------------------------------------------------------- materials

# Pint glass with condensation (voronoi droplets as bump, masked to beer level)
glass_m, nt, out = mat("Glass")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Base Color"].default_value = (1, 1, 1, 1)
p.inputs["Transmission Weight"].default_value = 1.0
p.inputs["Roughness"].default_value = 0.0
p.inputs["IOR"].default_value = 1.5
tc = nt.nodes.new("ShaderNodeTexCoord")
vor = nt.nodes.new("ShaderNodeTexVoronoi")
vor.feature = "F1"
vor.inputs["Scale"].default_value = 210.0
vor.inputs["Randomness"].default_value = 1.0
link(nt, tc.outputs["Object"], vor.inputs["Vector"])
drop = nt.nodes.new("ShaderNodeMapRange")
drop.inputs["From Min"].default_value = 0.16
drop.inputs["From Max"].default_value = 0.30
drop.inputs["To Min"].default_value = 1.0
drop.inputs["To Max"].default_value = 0.0
link(nt, vor.outputs["Distance"], drop.inputs["Value"])
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
link(nt, tc.outputs["Object"], sep.inputs[0])
lvl = nt.nodes.new("ShaderNodeMapRange")
lvl.inputs["From Min"].default_value = 0.131
lvl.inputs["From Max"].default_value = 0.118
lvl.inputs["To Min"].default_value = 0.0
lvl.inputs["To Max"].default_value = 1.0
link(nt, sep.outputs["Z"], lvl.inputs["Value"])
mask = nt.nodes.new("ShaderNodeMath")
mask.operation = "MULTIPLY"
link(nt, drop.outputs[0], mask.inputs[0])
link(nt, lvl.outputs[0], mask.inputs[1])
bump = nt.nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.35
bump.inputs["Distance"].default_value = 0.00035
link(nt, mask.outputs[0], bump.inputs["Height"])
link(nt, bump.outputs[0], p.inputs["Normal"])
# droplets slightly frost the glass where they sit
rough = nt.nodes.new("ShaderNodeMath")
rough.operation = "MULTIPLY"
rough.inputs[1].default_value = 0.025
link(nt, lvl.outputs[0], rough.inputs[0])
link(nt, rough.outputs[0], p.inputs["Roughness"])
link(nt, p.outputs[0], out.inputs["Surface"])

# Golden lager
beer_m, nt, out = mat("Beer")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Base Color"].default_value = (1.0, 0.92, 0.75, 1)
p.inputs["Transmission Weight"].default_value = 1.0
p.inputs["Roughness"].default_value = 0.0
p.inputs["IOR"].default_value = 1.34
va = nt.nodes.new("ShaderNodeVolumeAbsorption")
va.inputs["Color"].default_value = (1.0, 0.76, 0.11, 1)
va.inputs["Density"].default_value = 38.0
vs = nt.nodes.new("ShaderNodeVolumeScatter")
vs.inputs["Color"].default_value = (1.0, 0.75, 0.35, 1)
vs.inputs["Density"].default_value = 0.6
addv = nt.nodes.new("ShaderNodeAddShader")
link(nt, va.outputs[0], addv.inputs[0])
link(nt, vs.outputs[0], addv.inputs[1])
link(nt, p.outputs[0], out.inputs["Surface"])
link(nt, va.outputs[0], out.inputs["Volume"])

# Foam head
foam_m, nt, out = mat("Foam")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Base Color"].default_value = (1.0, 0.94, 0.82, 1)
p.inputs["Subsurface Weight"].default_value = 1.0
p.inputs["Subsurface Radius"].default_value = (0.004, 0.003, 0.002)
p.inputs["Subsurface Scale"].default_value = 1.0
p.inputs["Roughness"].default_value = 0.55
tc = nt.nodes.new("ShaderNodeTexCoord")
vf = nt.nodes.new("ShaderNodeTexVoronoi")
vf.inputs["Scale"].default_value = 700.0
link(nt, tc.outputs["Object"], vf.inputs["Vector"])
bmp = nt.nodes.new("ShaderNodeBump")
bmp.inputs["Strength"].default_value = 0.35
bmp.inputs["Distance"].default_value = 0.0004
link(nt, vf.outputs["Distance"], bmp.inputs["Height"])
link(nt, bmp.outputs[0], p.inputs["Normal"])
link(nt, p.outputs[0], out.inputs["Surface"])

# Air bubbles inside liquid (relative IOR < 1)
bub_m, nt, out = mat("Bubble")
g = nt.nodes.new("ShaderNodeBsdfGlass")
g.inputs["IOR"].default_value = 0.75
g.inputs["Roughness"].default_value = 0.0
link(nt, g.outputs[0], out.inputs["Surface"])

# Whiskey for the rocks glass
whisky_m, nt, out = mat("Whiskey")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Transmission Weight"].default_value = 1.0
p.inputs["Roughness"].default_value = 0.0
p.inputs["IOR"].default_value = 1.36
va = nt.nodes.new("ShaderNodeVolumeAbsorption")
va.inputs["Color"].default_value = (0.95, 0.32, 0.05, 1)
va.inputs["Density"].default_value = 40.0
link(nt, p.outputs[0], out.inputs["Surface"])
link(nt, va.outputs[0], out.inputs["Volume"])

ice_m, nt, out = mat("Ice")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Transmission Weight"].default_value = 1.0
p.inputs["Roughness"].default_value = 0.08
p.inputs["IOR"].default_value = 1.31
link(nt, p.outputs[0], out.inputs["Surface"])

# Weathered patio planks: wave-texture grain, per-plank variation, satin sheen
wood_m, nt, out = mat("Wood")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
tc = nt.nodes.new("ShaderNodeTexCoord")
oi = nt.nodes.new("ShaderNodeObjectInfo")
mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Scale"].default_value = (14.0, 1.1, 14.0)
link(nt, tc.outputs["Object"], mp.inputs["Vector"])
offs = nt.nodes.new("ShaderNodeVectorMath")
offs.operation = "MULTIPLY_ADD"
offs.inputs[1].default_value = (0, 0, 0)
link(nt, mp.outputs[0], offs.inputs[0])
rv = nt.nodes.new("ShaderNodeCombineXYZ")
rmul = nt.nodes.new("ShaderNodeMath")
rmul.operation = "MULTIPLY"
rmul.inputs[1].default_value = 37.0
link(nt, oi.outputs["Random"], rmul.inputs[0])
link(nt, rmul.outputs[0], rv.inputs["X"])
link(nt, rmul.outputs[0], rv.inputs["Z"])
offs.operation = "ADD"
link(nt, rv.outputs[0], offs.inputs[1])
wave = nt.nodes.new("ShaderNodeTexWave")
wave.wave_type = "RINGS"
wave.inputs["Scale"].default_value = 3.0
wave.inputs["Distortion"].default_value = 9.0
wave.inputs["Detail"].default_value = 4.0
wave.inputs["Detail Scale"].default_value = 1.5
link(nt, offs.outputs[0], wave.inputs["Vector"])
noise = nt.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 40.0
noise.inputs["Detail"].default_value = 8.0
link(nt, tc.outputs["Object"], noise.inputs["Vector"])
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.15
ramp.color_ramp.elements[0].color = (0.016, 0.0075, 0.004, 1)
ramp.color_ramp.elements[1].position = 0.85
ramp.color_ramp.elements[1].color = (0.085, 0.040, 0.018, 1)
mixf = nt.nodes.new("ShaderNodeMix")
mixf.data_type = "FLOAT"
mixf.inputs["Factor"].default_value = 0.35
link(nt, wave.outputs["Fac"], mixf.inputs["A"])
link(nt, noise.outputs["Fac"], mixf.inputs["B"])
link(nt, mixf.outputs["Result"], ramp.inputs["Fac"])
hsv = nt.nodes.new("ShaderNodeHueSaturation")
vmul = nt.nodes.new("ShaderNodeMapRange")
vmul.inputs["To Min"].default_value = 0.7
vmul.inputs["To Max"].default_value = 1.25
link(nt, oi.outputs["Random"], vmul.inputs["Value"])
link(nt, vmul.outputs[0], hsv.inputs["Value"])
link(nt, ramp.outputs[0], hsv.inputs["Color"])
link(nt, hsv.outputs[0], p.inputs["Base Color"])
rr = nt.nodes.new("ShaderNodeMapRange")
rr.inputs["To Min"].default_value = 0.28
rr.inputs["To Max"].default_value = 0.6
link(nt, noise.outputs["Fac"], rr.inputs["Value"])
link(nt, rr.outputs[0], p.inputs["Roughness"])
bmp = nt.nodes.new("ShaderNodeBump")
bmp.inputs["Strength"].default_value = 0.25
bmp.inputs["Distance"].default_value = 0.002
link(nt, mixf.outputs["Result"], bmp.inputs["Height"])
link(nt, bmp.outputs[0], p.inputs["Normal"])
link(nt, p.outputs[0], out.inputs["Surface"])

# Wet brick pavers far below the table
paver_m, nt, out = mat("Pavers")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
tc = nt.nodes.new("ShaderNodeTexCoord")
brick = nt.nodes.new("ShaderNodeTexBrick")
brick.inputs["Scale"].default_value = 3.5
brick.inputs["Color1"].default_value = (0.07, 0.025, 0.015, 1)
brick.inputs["Color2"].default_value = (0.05, 0.02, 0.013, 1)
brick.inputs["Mortar"].default_value = (0.012, 0.011, 0.01, 1)
brick.inputs["Mortar Size"].default_value = 0.015
link(nt, tc.outputs["Object"], brick.inputs["Vector"])
link(nt, brick.outputs["Color"], p.inputs["Base Color"])
wn = nt.nodes.new("ShaderNodeTexNoise")
wn.inputs["Scale"].default_value = 1.2
link(nt, tc.outputs["Object"], wn.inputs["Vector"])
wr = nt.nodes.new("ShaderNodeMapRange")
wr.inputs["From Min"].default_value = 0.45
wr.inputs["From Max"].default_value = 0.6
wr.inputs["To Min"].default_value = 0.05
wr.inputs["To Max"].default_value = 0.45
link(nt, wn.outputs["Fac"], wr.inputs["Value"])
link(nt, wr.outputs[0], p.inputs["Roughness"])
link(nt, p.outputs[0], out.inputs["Surface"])

dark_m, nt, out = mat("Dark")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Base Color"].default_value = (0.012, 0.012, 0.014, 1)
p.inputs["Roughness"].default_value = 0.6
link(nt, p.outputs[0], out.inputs["Surface"])

frond_m, nt, out = mat("Frond")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Base Color"].default_value = (0.006, 0.012, 0.008, 1)
p.inputs["Roughness"].default_value = 0.5
link(nt, p.outputs[0], out.inputs["Surface"])

facade_m, nt, out = mat("Facade")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Base Color"].default_value = (0.03, 0.035, 0.04, 1)
p.inputs["Roughness"].default_value = 0.9
link(nt, p.outputs[0], out.inputs["Surface"])

cup_m, nt, out = mat("Votive")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Base Color"].default_value = (1.0, 0.6, 0.3, 1)
p.inputs["Transmission Weight"].default_value = 1.0
p.inputs["Roughness"].default_value = 0.25
p.inputs["IOR"].default_value = 1.5
link(nt, p.outputs[0], out.inputs["Surface"])

# ---------------------------------------------------------------- world

world = bpy.data.worlds.new("Night")
scene.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
link(nt, tc.outputs["Generated"], sep.inputs[0])
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (0.020, 0.032, 0.050, 1)  # city glow at horizon
ramp.color_ramp.elements[1].position = 0.35
ramp.color_ramp.elements[1].color = (0.003, 0.006, 0.016, 1)  # deep navy overhead
link(nt, sep.outputs["Z"], ramp.inputs["Fac"])
link(nt, ramp.outputs[0], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0

# ---------------------------------------------------------------- hero table

TABLE_BACK = 0.85
plank_w, gap = 0.118, 0.0045
x = -0.9
i = 0
while x < 0.9:
    h = 0.04 + rng.uniform(-0.0006, 0.0006)
    pl = box(f"plank{i}", (plank_w, TABLE_BACK + 0.9, h), (x + plank_w / 2, (TABLE_BACK - 0.9) / 2, -h / 2 + rng.uniform(-0.0004, 0.0004)))
    pl.rotation_euler.y = rng.uniform(-0.002, 0.002)
    bpy.ops.object.shade_flat() if False else None
    assign(pl, wood_m)
    x += plank_w + gap
    i += 1
under = box("table_under", (1.9, TABLE_BACK + 0.9, 0.02), (0, (TABLE_BACK - 0.9) / 2, -0.05))
assign(under, dark_m)

# ---------------------------------------------------------------- pint glass

GX, GY = 0.072, 0.0
seg = 160
outer = [(0.0, 0.0), (0.0288, 0.0), (0.0297, 0.0008), (0.0301, 0.0025)]
for k in range(1, 21):
    z = 0.0025 + (0.1485 - 0.0025) * k / 20
    outer.append((0.0301 + (0.0436 - 0.0301) * (z - 0.0025) / 0.146, z))
lip = [(0.0435, 0.1495), (0.0429, 0.1503), (0.0420, 0.1506), (0.0411, 0.1503), (0.0406, 0.1495)]
inner = []
for k in range(0, 21):
    z = 0.1485 - (0.1485 - 0.0140) * k / 20
    inner.append((0.0405 - (0.0405 - 0.0277) * (0.1485 - z) / 0.1345, z))
inner += [(0.0268, 0.0124), (0.0255, 0.0120), (0.0, 0.0120)]
glass = lathe("pint", outer + lip + inner, seg)
glass.location = (GX, GY, 0)
assign(glass, glass_m)


def r_inner(z):
    return 0.0277 + (0.0405 - 0.0277) * (z - 0.0140) / 0.1345


BEER_TOP = 0.1275
FOAM_TOP = 0.1405
liq = [(0.0, 0.0123), (0.0262, 0.0123), (r_inner(0.0142) - 0.0002, 0.0142)]
for k in range(1, 12):
    z = 0.0142 + (BEER_TOP - 0.0142) * k / 11
    liq.append((r_inner(z) - 0.0002, z))
liq.append((0.0, BEER_TOP))
beer = lathe("beer", liq, seg)
beer.location = (GX, GY, 0)
assign(beer, beer_m)

foam_prof = [(0.0, BEER_TOP - 0.0003)]
for k in range(0, 8):
    z = BEER_TOP - 0.0003 + (FOAM_TOP - 0.0035 - BEER_TOP) * k / 7
    foam_prof.append((r_inner(z) - 0.0002, z))
for k in range(1, 9):  # rounded dome edge
    a = (math.pi / 2) * k / 8
    rr0 = r_inner(FOAM_TOP) - 0.0002
    foam_prof.append((rr0 - 0.006 * (1 - math.cos(a)) * 1.0, FOAM_TOP - 0.0035 + 0.0035 * math.sin(a)))
foam_prof.append((0.0, FOAM_TOP + 0.0012))
foam = lathe("foam", foam_prof, seg)
foam.location = (GX, GY, 0)
assign(foam, foam_m)

# bubble streams: positions are periodic over N frames (k_i whole cycles)
bubbles = []
bub_mesh = None
for b in range(90):
    stream = b < 45
    if stream:
        sid = b % 5
        ang = TAU * (sid / 5) + 0.4
        rad = 0.010 + 0.003 * sid
        jitter = 0.0006
    else:
        ang = rng.uniform(0, TAU)
        rad = rng.uniform(0.0, 0.024)
        jitter = 0.0
    r = rng.uniform(0.00045, 0.0010) if stream else rng.uniform(0.0003, 0.0007)
    if bub_mesh is None:
        ob = uv_sphere("bubble", 1.0, (0, 0, 0), seg=14, rings=8)
        bub_mesh = ob.data
        assign(ob, bub_m)
    else:
        ob = bpy.data.objects.new(f"bubble{b}", bub_mesh)
        scene.collection.objects.link(ob)
    ob.scale = (r, r, r)
    bubbles.append(dict(ob=ob, ang=ang, rad=rad, phase=rng.random(), cycles=rng.choice([2, 3, 3, 4]) if stream else rng.choice([1, 2]),
                        wob=rng.uniform(0, TAU), jit=jitter, r=r))

# ---------------------------------------------------------------- rocks glass (soft, behind left)

RX, RY = -0.17, 0.42
rprof = [(0.0, 0.0), (0.040, 0.0), (0.0412, 0.002)]
for k in range(1, 8):
    z = 0.002 + 0.086 * k / 7
    rprof.append((0.0414, z))
rprof += [(0.0410, 0.0895), (0.0398, 0.0895), (0.0392, 0.088)]
for k in range(1, 8):
    z = 0.088 - (0.088 - 0.022) * k / 7
    rprof.append((0.0392, z))
rprof += [(0.0380, 0.0205), (0.0, 0.0205)]
rocks = lathe("rocks", rprof, 96)
rocks.location = (RX, RY, 0)
assign(rocks, glass_m)
wprof = [(0.0, 0.0207), (0.0388, 0.0207), (0.0389, 0.055), (0.0, 0.055)]
wk = lathe("whiskey", wprof, 96)
wk.location = (RX, RY, 0)
assign(wk, whisky_m)
bpy.ops.mesh.primitive_cube_add(size=0.05, location=(RX + 0.002, RY - 0.003, 0.050))
ice = bpy.context.active_object
ice.rotation_euler = (0.08, 0.05, 0.5)
bev = ice.modifiers.new("bev", "BEVEL")
bev.width = 0.004
bev.segments = 4
assign(ice, ice_m)

# ---------------------------------------------------------------- votive candle (foreground bokeh)

VX, VY = -0.12, -0.32
vprof = [(0.0, 0.0), (0.030, 0.0), (0.0315, 0.003), (0.0315, 0.062), (0.0300, 0.064), (0.0285, 0.062), (0.0285, 0.006), (0.0, 0.006)]
vot = lathe("votive", vprof, 64)
vot.location = (VX, VY, 0)
assign(vot, cup_m)
flame_m, flame_em = emission_mat("Flame", temp=1850, strength=60)
flame = uv_sphere("flame", 1.0, (VX, VY, 0.034), seg=16, rings=10, scale=(0.0045, 0.0045, 0.012))
assign(flame, flame_m)
candle_light = bpy.data.lights.new("candle", "POINT")
candle_light.color = (1.0, 0.55, 0.22)
candle_light.energy = 0.9
candle_light.shadow_soft_size = 0.01
cl = bpy.data.objects.new("candle_light", candle_light)
cl.location = (VX, VY, 0.04)
scene.collection.objects.link(cl)

# ---------------------------------------------------------------- floor, distant tables, facade

floor = box("floor", (60, 60, 0.02), (0, 25, -0.76))
assign(floor, paver_m)

distant = []
for k in range(14):
    dx = rng.uniform(-5.5, 5.5)
    dy = rng.uniform(2.6, 13.0)
    tbl = box(f"t{k}", (0.8, 0.8, 0.04), (dx, dy, -0.02))
    assign(tbl, dark_m)
    fm, fe = emission_mat(f"cflame{k}", temp=1900, strength=45)
    fl = uv_sphere(f"cf{k}", 1.0, (dx + rng.uniform(-0.2, 0.2), dy, 0.04), seg=12, rings=8, scale=(0.012, 0.012, 0.02))
    assign(fl, fm)
    distant.append(dict(em=fe, base=22 * rng.uniform(0.6, 1.2), ph=rng.random(), f1=rng.choice([5, 7, 9]), f2=rng.choice([11, 13, 17])))

xb = -30.0
while xb < 30.0:
    wdt = rng.uniform(4.0, 9.0)
    hgt = rng.choice([4.2, 5.5, 6.8, 8.5, 11.0])
    fb = box(f"facade{xb:.0f}", (wdt, 0.4, hgt), (xb + wdt / 2, 30 + rng.uniform(0, 3), hgt / 2 - 0.76))
    assign(fb, facade_m)
    xb += wdt
# a distant steeple, the Holy City skyline cue
st = box("steeple_base", (2.2, 2.2, 14), (-7.5, 55, 6.2))
assign(st, facade_m)
bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=1.3, depth=8, location=(-7.5, 55, 17.2))
spire = bpy.context.active_object
assign(spire, facade_m)
windows = []
for row in range(3):
    for col in range(-9, 10):
        if rng.random() < 0.42:
            continue
        wx = col * 2.6 + rng.uniform(-0.3, 0.3)
        wz = 0.9 + row * 2.9
        on = rng.random() < 0.7
        wm, we = emission_mat(f"win{row}_{col}", temp=rng.choice([2500, 2700, 3000]), strength=(rng.uniform(0.12, 0.45) if on else 0.02))
        w = box(f"w{row}_{col}", (1.0, 0.05, 1.7), (wx, 29.78, wz))
        assign(w, wm)

# Charleston gas lanterns flanking a doorway in the facade
lanterns = []
for k, lx in enumerate((-2.2, -0.6, 4.6, 6.2)):
    lm, le = emission_mat(f"gas{k}", temp=1750, strength=45)
    lo = uv_sphere(f"gas{k}", 1.0, (lx, 29.5, 2.4), seg=16, rings=10, scale=(0.12, 0.12, 0.2))
    assign(lo, lm)
    lanterns.append(dict(em=le, base=45, ph=rng.random(), f=rng.choice([6, 8, 10])))

# ---------------------------------------------------------------- string lights


def catenary(p0, p1, sag, n):
    pts = []
    for i in range(n + 1):
        t = i / n
        p = p0.lerp(p1, t)
        p.z -= sag * 4 * t * (1 - t)
        pts.append(p)
    return pts


bulb_mesh = None
bulbs = []
strands = [
    (Vector((-7.0, 4.2, 2.35)), Vector((7.5, 5.2, 2.5)), 0.75),
    (Vector((-9.0, 7.5, 2.9)), Vector((8.0, 8.8, 2.8)), 0.9),
    (Vector((-6.0, 3.0, 2.2)), Vector((4.0, 16.0, 3.2)), 1.0),
    (Vector((7.0, 3.6, 2.3)), Vector((-5.0, 15.0, 3.3)), 1.0),
    (Vector((-11.0, 12.5, 3.3)), Vector((10.0, 13.5, 3.2)), 1.1),
    (Vector((-12.0, 19.0, 3.8)), Vector((12.0, 20.0, 3.6)), 1.2),
]
wire_m = dark_m
for si, (a, b, sag) in enumerate(strands):
    length = (b - a).length
    nb = int(length / 0.85)
    pts = catenary(a, b, sag, nb * 4)
    # wire as a curve
    cu = bpy.data.curves.new(f"wire{si}", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.004
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for j, p in enumerate(pts):
        sp.points[j].co = (p.x, p.y, p.z, 1)
    wo = bpy.data.objects.new(f"wire{si}", cu)
    scene.collection.objects.link(wo)
    wo.data.materials.append(wire_m)
    for j in range(1, nb):
        p = pts[j * 4]
        bm_, be = emission_mat(f"bulb{si}_{j}", temp=rng.choice([2100, 2250, 2400]), strength=1.0)
        bo = uv_sphere(f"bulb{si}_{j}", 1.0, (p.x, p.y, p.z - 0.09), seg=16, rings=10, scale=(0.032, 0.032, 0.045))
        assign(bo, bm_)
        bulbs.append(dict(em=be, base=rng.uniform(8, 13), ph=rng.random(), f=rng.choice([1, 2, 3]), amp=rng.uniform(0.02, 0.07)))

# ---------------------------------------------------------------- palmetto fronds (silhouette, sway)


def frond(name, origin, yaw, pitch, length=1.25, leaflets=44, spread=2.3):
    verts, faces = [], []
    for k in range(leaflets):
        a = -spread / 2 + spread * k / (leaflets - 1)
        L = length * (0.75 + 0.25 * math.cos(a * 0.9)) * rng.uniform(0.92, 1.05)
        w = 0.022
        steps = 8
        base_i = len(verts)
        for s_ in range(steps + 1):
            t = s_ / steps
            r = L * t
            droop = -0.32 * (t ** 2) * L
            cx = r * math.sin(a)
            cy = r * math.cos(a)
            ww = w * (1 - t * 0.85) * (0.4 + 0.6 * min(1, t * 5))
            nx, ny = math.cos(a), -math.sin(a)
            verts.append((cx - nx * ww, cy - ny * ww, droop))
            verts.append((cx + nx * ww, cy + ny * ww, droop + 0.006))
        for s_ in range(steps):
            i0 = base_i + s_ * 2
            faces.append((i0, i0 + 1, i0 + 3, i0 + 2))
    ob = obj_from_mesh(name, verts, faces)
    ob.location = origin
    ob.rotation_euler = (pitch, 0, yaw)
    assign(ob, frond_m)
    sol = ob.modifiers.new("thick", "SOLIDIFY")
    sol.thickness = 0.003
    return ob


fronds = [
    dict(ob=frond("frond0", (-1.40, 2.3, 0.44), -2.0, 0.30), ph=0.0, amp=0.035),
    dict(ob=frond("frond1", (-1.65, 2.9, 0.66), -2.5, 0.10, length=1.45), ph=0.31, amp=0.03),
    dict(ob=frond("frond2", (1.95, 3.6, 0.84), 2.3, 0.22, length=1.4), ph=0.62, amp=0.028),
]
for f in fronds:
    f["rot0"] = tuple(f["ob"].rotation_euler)
stem = bpy.data.curves.new("stem", "CURVE")
stem.dimensions = "3D"
stem.bevel_depth = 0.012
sp = stem.splines.new("POLY")
sp.points.add(1)
sp.points[0].co = (-2.0, 2.6, -0.76, 1)
sp.points[1].co = (-1.40, 2.3, 0.44, 1)
so = bpy.data.objects.new("stem", stem)
scene.collection.objects.link(so)
so.data.materials.append(frond_m)

# ---------------------------------------------------------------- practical lights on the hero


def area(name, loc, target, size, energy, color):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = size
    ld.energy = energy
    ld.color = color
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    scene.collection.objects.link(lo)
    d = Vector(target) - Vector(loc)
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    lo.visible_camera = False
    return lo


# glow card behind the pint: seen only through refraction, so the beer is
# backlit like a commercial without washing the table
card_m, nt, out = mat("GlowCard")
em = nt.nodes.new("ShaderNodeEmission")
bb = nt.nodes.new("ShaderNodeBlackbody")
bb.inputs["Temperature"].default_value = 2900
link(nt, bb.outputs[0], em.inputs["Color"])
tc = nt.nodes.new("ShaderNodeTexCoord")
grad = nt.nodes.new("ShaderNodeTexGradient")
grad.gradient_type = "SPHERICAL"
mpc = nt.nodes.new("ShaderNodeMapping")
mpc.inputs["Location"].default_value = (0.0, 0.0, 0.0)
mpc.inputs["Scale"].default_value = (1.9, 1.9, 1.9)
link(nt, tc.outputs["Object"], mpc.inputs["Vector"])
link(nt, mpc.outputs[0], grad.inputs["Vector"])
soft = nt.nodes.new("ShaderNodeMapRange")
soft.interpolation_type = "SMOOTHSTEP"
soft.inputs["From Min"].default_value = 0.0
soft.inputs["From Max"].default_value = 0.55
link(nt, grad.outputs["Fac"], soft.inputs["Value"])
gm = nt.nodes.new("ShaderNodeMath")
gm.operation = "MULTIPLY"
gm.inputs[1].default_value = 0.85
link(nt, soft.outputs[0], gm.inputs[0])
link(nt, gm.outputs[0], em.inputs["Strength"])
link(nt, em.outputs[0], out.inputs["Surface"])
bpy.ops.mesh.primitive_plane_add(size=1, location=(GX + 0.005, GY + 0.24, 0.08), rotation=(math.pi / 2, 0, 0))
card = bpy.context.active_object
card.scale = (0.30, 0.30, 1)
assign(card, card_m)
card.visible_camera = False
card.visible_diffuse = False
card.visible_glossy = False
card.visible_shadow = False
card.visible_volume_scatter = False
area("rim_cool", (GX - 0.45, GY + 0.25, 0.32), (GX, GY, 0.08), (0.25, 0.4), 4.0, (0.45, 0.72, 0.9))
area("fill", (0.0, -1.2, 0.35), (GX, GY, 0.07), (0.8, 0.5), 0.35, (1.0, 0.8, 0.62))
area("top_spec", (GX + 0.05, GY - 0.1, 0.55), (GX, GY, 0.1), (0.12, 0.6), 1.6, (1.0, 0.85, 0.7))
area("foam_key", (GX + 0.10, GY - 0.32, 0.30), (GX, GY, 0.135), (0.18, 0.10), 1.4, (1.0, 0.86, 0.68))

# ---------------------------------------------------------------- camera

target = bpy.data.objects.new("target", None)
target.location = (0.012, 0.02, 0.083)
scene.collection.objects.link(target)
focus = bpy.data.objects.new("focus", None)
focus.location = (GX, GY - 0.03, 0.08)
scene.collection.objects.link(focus)

camd = bpy.data.cameras.new("cam")
camd.lens = 50
camd.sensor_width = 36
camd.dof.use_dof = True
camd.dof.focus_object = focus
camd.dof.aperture_fstop = 2.0
camd.dof.aperture_blades = 0
camd.dof.aperture_ratio = 1.45
cam = bpy.data.objects.new("cam", camd)
scene.collection.objects.link(cam)
scene.camera = cam
tt = cam.constraints.new("TRACK_TO")
tt.target = target
tt.track_axis = "TRACK_NEGATIVE_Z"
tt.up_axis = "UP_Y"

CAM_BASE = Vector((0.0, -0.66, 0.098))

# ---------------------------------------------------------------- render settings

r = scene.render
r.engine = "CYCLES"
r.resolution_x = args.w
r.resolution_y = args.h
r.resolution_percentage = 100
r.use_persistent_data = True
r.image_settings.file_format = "PNG"
r.image_settings.color_depth = "16"
r.image_settings.color_mode = "RGB"
r.film_transparent = False
c = scene.cycles
c.device = "CPU"
c.samples = args.samples
c.use_adaptive_sampling = True
c.adaptive_threshold = 0.02
c.use_denoising = True
try:
    c.denoiser = "OPENIMAGEDENOISE"
    c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    c.denoising_prefilter = "ACCURATE"
except Exception as e:  # noqa
    print("denoise cfg", e)
c.max_bounces = 10
c.diffuse_bounces = 3
c.glossy_bounces = 4
c.transmission_bounces = 10
c.transparent_max_bounces = 10
c.volume_bounces = 0
c.caustics_reflective = False
c.caustics_refractive = False
c.blur_glossy = 0.6
c.sample_clamp_indirect = 8.0
c.sample_clamp_direct = 0.0
c.volume_step_rate = 4.0
c.seed = 7
c.use_animated_seed = True
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception as e:
    print("view", e)
scene.view_settings.exposure = -0.2
scene.render.threads_mode = "AUTO"

if args.blend:
    bpy.ops.wm.save_as_mainfile(filepath=args.blend)

# ---------------------------------------------------------------- per-frame state


def set_frame(f):
    th = TAU * f / N
    cam.location = CAM_BASE + Vector((0.052 * math.sin(th), 0.035 * math.cos(th) - 0.035, 0.010 * math.sin(2 * th + 0.6)))
    # bubbles: rise with a whole number of cycles per loop
    for b in bubbles:
        u = (b["phase"] + b["cycles"] * f / N) % 1.0
        z = 0.0135 + u * (BEER_TOP - 0.0135 - 0.002)
        wob = b["jit"] * math.sin(TAU * (6 * f / N) + b["wob"])
        rad = min(b["rad"], r_inner(z) - 0.003)
        b["ob"].location = (GX + rad * math.cos(b["ang"]) + wob, GY + rad * math.sin(b["ang"]), z)
        s = b["r"] * (0.8 + 0.4 * u)
        b["ob"].scale = (s, s, s)
    for bl in bulbs:
        bl["em"].inputs["Strength"].default_value = bl["base"] * (1 + bl["amp"] * math.sin(TAU * (bl["f"] * f / N + bl["ph"])))
    for d in distant:
        d["em"].inputs["Strength"].default_value = d["base"] * (1 + 0.12 * math.sin(TAU * (d["f1"] * f / N + d["ph"])) + 0.06 * math.sin(TAU * (d["f2"] * f / N)))
    for g in lanterns:
        g["em"].inputs["Strength"].default_value = g["base"] * (1 + 0.08 * math.sin(TAU * (g["f"] * f / N + g["ph"])))
    flick = 1 + 0.10 * math.sin(TAU * 13 * f / N) + 0.06 * math.sin(TAU * 29 * f / N + 1.3) + 0.04 * math.sin(TAU * 47 * f / N + 0.4)
    flame_em.inputs["Strength"].default_value = 60 * flick
    candle_light.energy = 0.9 * flick
    flame.scale = (0.0045, 0.0045, 0.012 * (1 + 0.06 * math.sin(TAU * 13 * f / N + 0.5)))
    for fr in fronds:
        rx, ry, rz = fr["rot0"]
        fr["ob"].rotation_euler = (rx + fr["amp"] * math.sin(TAU * (f / N + fr["ph"])), ry + 0.5 * fr["amp"] * math.sin(TAU * (2 * f / N + fr["ph"])), rz)


if args.probe:
    from bpy_extras.object_utils import world_to_camera_view
    for f in (0, N // 4, N // 2, 3 * N // 4):
        set_frame(f)
        bpy.context.view_layer.update()
        for name in ("frond0", "frond1", "frond2", "votive", "rocks", "pint"):
            ob = bpy.data.objects[name]
            pts = [world_to_camera_view(scene, cam, ob.matrix_world @ v.co) for v in ob.data.vertices]
            inside = [q for q in pts if 0 <= q.x <= 1 and 0 <= q.y <= 1 and q.z > 0]
            xs = [q.x for q in pts]; ys = [q.y for q in pts]
            print(f"f{f} {name}: in={len(inside)/len(pts):.2f} x[{min(xs):.2f},{max(xs):.2f}] y[{min(ys):.2f},{max(ys):.2f}]")
    sys.exit(0)

spec = [int(v) for v in args.frames.split(":")]
start, end = spec[0], spec[1]
step = spec[2] if len(spec) > 2 else 1
import time

for f in range(start, end, step):
    t0 = time.time()
    scene.frame_set(f % N)
    set_frame(f % N)
    r.filepath = f"{args.out}/f{f:04d}.png"
    bpy.ops.render.render(write_still=True)
    print(f"FRAME {f} {time.time() - t0:.1f}s", flush=True)
