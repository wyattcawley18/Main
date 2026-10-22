"""Fort Mill Family Restaurant hero film: morning at the window booth.

A diner mug of coffee on a maple table, backlit by low sun through window
blinds; its steam glows where it crosses the light. Sweet tea sweats beside
it, biscuits sit on a banded diner plate, and the napkin dispenser, sugar
pourer and squeeze bottle stand soft against the window.

Path-traced in Cycles. Every animated quantity is periodic over N frames so
frame N wraps exactly onto frame 0 (seamless loop). The steam is two noise
layers rising through the plume and crossfaded half a loop apart; each layer
jumps back to its start only while its weight is zero.

usage: python scene.py --out DIR --w 1920 --h 1080 --samples 48 --frames 0:192[:step]
"""
import argparse
import math
import random
import sys
import time

import bpy
import addon_utils
import bmesh
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--w", type=int, default=1920)
ap.add_argument("--h", type=int, default=1080)
ap.add_argument("--samples", type=int, default=48)
ap.add_argument("--frames", default="0:1")
ap.add_argument("--total", type=int, default=192)
ap.add_argument("--blend", default="")
ap.add_argument("--probe", action="store_true")
args = ap.parse_args(sys.argv[1:])

N = args.total
TAU = math.pi * 2
rng = random.Random(29715)

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


def principled(name, color, rough=0.5, metal=0.0, coat=0.0, trans=0.0, ior=1.45, sss=0.0, sss_r=(0.01, 0.005, 0.002)):
    m, nt, out = mat(name)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Transmission Weight"].default_value = trans
    p.inputs["IOR"].default_value = ior
    if sss:
        p.inputs["Subsurface Weight"].default_value = sss
        p.inputs["Subsurface Radius"].default_value = sss_r
        p.inputs["Subsurface Scale"].default_value = 1.0
    link(nt, p.outputs[0], out.inputs["Surface"])
    return m, nt, out, p


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
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def shell(outer, inner):
    """Closed lathe profile: outer wall up, inner wall back down."""
    return outer + inner


def box(name, size, loc, bevel=0.0, segs=3):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        b = ob.modifiers.new("bev", "BEVEL")
        b.width = bevel
        b.segments = segs
        b.limit_method = "NONE"
    return ob


def assign(ob, m):
    ob.data.materials.clear()
    ob.data.materials.append(m)


def tube(name, pts, radius, m, scale_xy=(1.0, 1.0)):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 6
    cu.resolution_u = 24
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for j, p in enumerate(pts):
        bp = sp.bezier_points[j]
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new(name, cu)
    scene.collection.objects.link(ob)
    ob.data.materials.append(m)
    return ob


# ---------------------------------------------------------------- materials

# Glazed diner china, cream white with a thin red band (object-space Z bands)
def china(name, band_lo, band_hi, band_axis="Z", radial=False):
    m, nt, out = mat(name)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Roughness"].default_value = 0.07
    p.inputs["Coat Weight"].default_value = 0.6
    p.inputs["Coat Roughness"].default_value = 0.03
    p.inputs["Subsurface Weight"].default_value = 0.08
    p.inputs["Subsurface Radius"].default_value = (0.002, 0.0015, 0.001)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    if radial:
        vm = nt.nodes.new("ShaderNodeVectorMath")
        vm.operation = "MULTIPLY"
        vm.inputs[1].default_value = (1, 1, 0)
        link(nt, tc.outputs["Object"], vm.inputs[0])
        ln = nt.nodes.new("ShaderNodeVectorMath")
        ln.operation = "LENGTH"
        link(nt, vm.outputs[0], ln.inputs[0])
        coord = ln.outputs["Value"]
    else:
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        link(nt, tc.outputs["Object"], sep.inputs[0])
        coord = sep.outputs[band_axis]
    lo = nt.nodes.new("ShaderNodeMath")
    lo.operation = "GREATER_THAN"
    lo.inputs[1].default_value = band_lo
    link(nt, coord, lo.inputs[0])
    hi = nt.nodes.new("ShaderNodeMath")
    hi.operation = "LESS_THAN"
    hi.inputs[1].default_value = band_hi
    link(nt, coord, hi.inputs[0])
    both = nt.nodes.new("ShaderNodeMath")
    both.operation = "MULTIPLY"
    link(nt, lo.outputs[0], both.inputs[0])
    link(nt, hi.outputs[0], both.inputs[1])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.80, 0.76, 0.68, 1)
    mix.inputs["B"].default_value = (0.42, 0.035, 0.03, 1)
    link(nt, both.outputs[0], mix.inputs["Factor"])
    link(nt, mix.outputs["Result"], p.inputs["Base Color"])
    link(nt, p.outputs[0], out.inputs["Surface"])
    return m


mug_m = china("MugChina", 0.0815, 0.0855)
handle_m = china("HandleChina", 9.0, 9.1)
plate_m = china("PlateChina", 0.096, 0.101, radial=True)

coffee_m, *_ = principled("Coffee", (0.006, 0.0028, 0.0012), rough=0.02, ior=1.33)

# Maple butcher block: strips running toward the window, per-strip tone,
# long grain, satin varnish
maple_m, nt, out = mat("Maple")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Coat Weight"].default_value = 0.35
p.inputs["Coat Roughness"].default_value = 0.12
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
link(nt, tc.outputs["Object"], sep.inputs[0])
strip = nt.nodes.new("ShaderNodeMath")
strip.operation = "MULTIPLY"
strip.inputs[1].default_value = 1 / 0.046
link(nt, sep.outputs["X"], strip.inputs[0])
fl = nt.nodes.new("ShaderNodeMath")
fl.operation = "FLOOR"
link(nt, strip.outputs[0], fl.inputs[0])
wn = nt.nodes.new("ShaderNodeTexWhiteNoise")
wn.noise_dimensions = "1D"
link(nt, fl.outputs[0], wn.inputs["W"])
mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Scale"].default_value = (16.0, 0.9, 16.0)
link(nt, tc.outputs["Object"], mp.inputs["Vector"])
grain = nt.nodes.new("ShaderNodeTexWave")
grain.wave_type = "BANDS"
grain.bands_direction = "X"
grain.inputs["Scale"].default_value = 1.6
grain.inputs["Distortion"].default_value = 9.0
grain.inputs["Detail"].default_value = 3.0
link(nt, mp.outputs[0], grain.inputs["Vector"])
fine = nt.nodes.new("ShaderNodeTexNoise")
fine.inputs["Scale"].default_value = 45.0
fine.inputs["Detail"].default_value = 6.0
link(nt, tc.outputs["Object"], fine.inputs["Vector"])
g2 = nt.nodes.new("ShaderNodeMix")
g2.data_type = "FLOAT"
g2.inputs["Factor"].default_value = 0.55
link(nt, grain.outputs["Fac"], g2.inputs["A"])
link(nt, fine.outputs["Fac"], g2.inputs["B"])
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.25
ramp.color_ramp.elements[0].color = (0.30, 0.135, 0.045, 1)
ramp.color_ramp.elements[1].position = 0.8
ramp.color_ramp.elements[1].color = (0.56, 0.30, 0.12, 1)
link(nt, g2.outputs["Result"], ramp.inputs["Fac"])
hsv = nt.nodes.new("ShaderNodeHueSaturation")
vr = nt.nodes.new("ShaderNodeMapRange")
vr.inputs["To Min"].default_value = 0.78
vr.inputs["To Max"].default_value = 1.15
link(nt, wn.outputs["Value"], vr.inputs["Value"])
link(nt, vr.outputs[0], hsv.inputs["Value"])
link(nt, ramp.outputs[0], hsv.inputs["Color"])
link(nt, hsv.outputs[0], p.inputs["Base Color"])
rr = nt.nodes.new("ShaderNodeMapRange")
rr.inputs["To Min"].default_value = 0.30
rr.inputs["To Max"].default_value = 0.48
link(nt, fine.outputs["Fac"], rr.inputs["Value"])
link(nt, rr.outputs[0], p.inputs["Roughness"])
bmp = nt.nodes.new("ShaderNodeBump")
bmp.inputs["Strength"].default_value = 0.08
bmp.inputs["Distance"].default_value = 0.001
link(nt, g2.outputs["Result"], bmp.inputs["Height"])
link(nt, bmp.outputs[0], p.inputs["Normal"])
link(nt, p.outputs[0], out.inputs["Surface"])

# Clear glass; the tumbler gets condensation droplets below the tea line
def glass(name, droplets_below=None):
    m, nt, out = mat(name)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (1, 1, 1, 1)
    p.inputs["Transmission Weight"].default_value = 1.0
    p.inputs["Roughness"].default_value = 0.0
    p.inputs["IOR"].default_value = 1.5
    if droplets_below is not None:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 260.0
        vor.inputs["Randomness"].default_value = 1.0
        link(nt, tc.outputs["Object"], vor.inputs["Vector"])
        drop = nt.nodes.new("ShaderNodeMapRange")
        drop.inputs["From Min"].default_value = 0.14
        drop.inputs["From Max"].default_value = 0.30
        drop.inputs["To Min"].default_value = 1.0
        drop.inputs["To Max"].default_value = 0.0
        link(nt, vor.outputs["Distance"], drop.inputs["Value"])
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        link(nt, tc.outputs["Object"], sep.inputs[0])
        lvl = nt.nodes.new("ShaderNodeMapRange")
        lvl.inputs["From Min"].default_value = droplets_below + 0.004
        lvl.inputs["From Max"].default_value = droplets_below - 0.006
        link(nt, sep.outputs["Z"], lvl.inputs["Value"])
        mask = nt.nodes.new("ShaderNodeMath")
        mask.operation = "MULTIPLY"
        link(nt, drop.outputs[0], mask.inputs[0])
        link(nt, lvl.outputs[0], mask.inputs[1])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.4
        bump.inputs["Distance"].default_value = 0.0004
        link(nt, mask.outputs[0], bump.inputs["Height"])
        link(nt, bump.outputs[0], p.inputs["Normal"])
        # fine fog of tiny droplets between the beads
        rough = nt.nodes.new("ShaderNodeMath")
        rough.operation = "MULTIPLY"
        rough.inputs[1].default_value = 0.10
        link(nt, lvl.outputs[0], rough.inputs[0])
        link(nt, rough.outputs[0], p.inputs["Roughness"])
    link(nt, p.outputs[0], out.inputs["Surface"])
    return m


glass_m = glass("Glass")
tumbler_m = glass("Tumbler", droplets_below=0.118)

# Sweet tea: deep amber absorption
tea_m, nt, out = mat("Tea")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Transmission Weight"].default_value = 1.0
p.inputs["Roughness"].default_value = 0.0
p.inputs["IOR"].default_value = 1.34
va = nt.nodes.new("ShaderNodeVolumeAbsorption")
va.inputs["Color"].default_value = (0.92, 0.42, 0.08, 1)
va.inputs["Density"].default_value = 9.0
vs = nt.nodes.new("ShaderNodeVolumeScatter")
vs.inputs["Color"].default_value = (1.0, 0.62, 0.22, 1)
vs.inputs["Density"].default_value = 5.0
vs.inputs["Anisotropy"].default_value = 0.6
addv = nt.nodes.new("ShaderNodeAddShader")
link(nt, va.outputs[0], addv.inputs[0])
link(nt, vs.outputs[0], addv.inputs[1])
link(nt, p.outputs[0], out.inputs["Surface"])
link(nt, addv.outputs[0], out.inputs["Volume"])

# ice sits mostly in tea: Cycles treats every interface as against air, so use
# the ice/tea relative index (1.31 / 1.34) rather than ice/air
ice_m, *_ = principled("Ice", (1, 1, 1), rough=0.05, trans=1.0, ior=1.04)

chrome_m, *_ = principled("Chrome", (0.92, 0.92, 0.94), rough=0.06, metal=1.0)
napkin_m, *_ = principled("Napkin", (0.86, 0.85, 0.82), rough=0.8, sss=0.2)
sugar_m, *_ = principled("Sugar", (0.9, 0.9, 0.88), rough=0.4, sss=0.4, sss_r=(0.004, 0.004, 0.004))
squeeze_m, *_ = principled("Squeeze", (0.55, 0.02, 0.015), rough=0.22, coat=0.4, sss=0.25, sss_r=(0.01, 0.002, 0.002))
paint_m, *_ = principled("Paint", (0.62, 0.55, 0.44), rough=0.75)
trim_m, *_ = principled("Trim", (0.72, 0.68, 0.60), rough=0.45)
slat_m, *_ = principled("Slat", (0.70, 0.66, 0.58), rough=0.55, sss=0.15, sss_r=(0.01, 0.008, 0.006))
butter_m, *_ = principled("Butter", (0.85, 0.62, 0.20), rough=0.3, sss=0.7, sss_r=(0.006, 0.004, 0.001))

# Buttermilk biscuits: golden tops, pale flaky sides
biscuit_m, nt, out = mat("Biscuit")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Roughness"].default_value = 0.72
p.inputs["Subsurface Weight"].default_value = 0.25
p.inputs["Subsurface Radius"].default_value = (0.004, 0.0025, 0.0012)
p.inputs["Subsurface Scale"].default_value = 1.0
geo = nt.nodes.new("ShaderNodeNewGeometry")
sepn = nt.nodes.new("ShaderNodeSeparateXYZ")
link(nt, geo.outputs["Normal"], sepn.inputs[0])
topf = nt.nodes.new("ShaderNodeMapRange")
topf.interpolation_type = "SMOOTHSTEP"
topf.inputs["From Min"].default_value = 0.25
topf.inputs["From Max"].default_value = 0.75
link(nt, sepn.outputs["Z"], topf.inputs["Value"])
tc = nt.nodes.new("ShaderNodeTexCoord")
bn = nt.nodes.new("ShaderNodeTexNoise")
bn.inputs["Scale"].default_value = 120.0
bn.inputs["Detail"].default_value = 8.0
bn.inputs["Roughness"].default_value = 0.65
link(nt, tc.outputs["Object"], bn.inputs["Vector"])
brown = nt.nodes.new("ShaderNodeValToRGB")
brown.color_ramp.elements[0].position = 0.30
brown.color_ramp.elements[0].color = (0.27, 0.105, 0.022, 1)
brown.color_ramp.elements[1].position = 0.7
brown.color_ramp.elements[1].color = (0.66, 0.36, 0.10, 1)
link(nt, bn.outputs["Fac"], brown.inputs["Fac"])
layers = nt.nodes.new("ShaderNodeTexNoise")
layers.inputs["Scale"].default_value = 260.0
layers.inputs["Detail"].default_value = 6.0
layers.inputs["Roughness"].default_value = 0.7
link(nt, tc.outputs["Object"], layers.inputs["Vector"])
pale = nt.nodes.new("ShaderNodeValToRGB")
pale.color_ramp.elements[0].color = (0.58, 0.40, 0.19, 1)
pale.color_ramp.elements[1].color = (0.80, 0.63, 0.40, 1)
link(nt, layers.outputs["Fac"], pale.inputs["Fac"])
mixc = nt.nodes.new("ShaderNodeMix")
mixc.data_type = "RGBA"
link(nt, topf.outputs[0], mixc.inputs["Factor"])
link(nt, pale.outputs[0], mixc.inputs["A"])
link(nt, brown.outputs[0], mixc.inputs["B"])
link(nt, mixc.outputs["Result"], p.inputs["Base Color"])
bb = nt.nodes.new("ShaderNodeBump")
bb.inputs["Strength"].default_value = 0.5
bb.inputs["Distance"].default_value = 0.0006
hb = nt.nodes.new("ShaderNodeMath")
hb.operation = "ADD"
link(nt, bn.outputs["Fac"], hb.inputs[0])
link(nt, layers.outputs["Fac"], hb.inputs[1])
link(nt, hb.outputs[0], bb.inputs["Height"])
link(nt, bb.outputs[0], p.inputs["Normal"])
link(nt, p.outputs[0], out.inputs["Surface"])

# ---------------------------------------------------------------- world and outdoors

world = bpy.data.worlds.new("Morning")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.62, 0.70, 0.78, 1)
bg.inputs["Strength"].default_value = 0.10

# Sunlit pines and sky beyond the glass. Leaf shimmer: the noise domain is
# translated around a closed circle once per loop.
out_m, nt, out = mat("Outdoors")
em = nt.nodes.new("ShaderNodeEmission")
tc = nt.nodes.new("ShaderNodeTexCoord")
leaf_map = nt.nodes.new("ShaderNodeMapping")
leaf_map.inputs["Scale"].default_value = (0.9, 0.9, 0.9)
link(nt, tc.outputs["Object"], leaf_map.inputs["Vector"])
ln_ = nt.nodes.new("ShaderNodeTexNoise")
ln_.inputs["Scale"].default_value = 2.2
ln_.inputs["Detail"].default_value = 5.0
ln_.inputs["Roughness"].default_value = 0.6
link(nt, leaf_map.outputs[0], ln_.inputs["Vector"])
sky = nt.nodes.new("ShaderNodeValToRGB")
el = sky.color_ramp.elements
el[0].position = 0.38
el[0].color = (0.10, 0.16, 0.05, 1)   # pine shade
el[1].position = 0.66
el[1].color = (1.0, 0.86, 0.55, 1)    # sun through needles
el.new(0.52).color = (0.42, 0.50, 0.16, 1)
link(nt, ln_.outputs["Fac"], sky.inputs["Fac"])
sepo = nt.nodes.new("ShaderNodeSeparateXYZ")
link(nt, tc.outputs["Object"], sepo.inputs[0])
hz = nt.nodes.new("ShaderNodeMapRange")  # brighter sky toward the top
hz.inputs["From Min"].default_value = -0.2
hz.inputs["From Max"].default_value = 1.0
hz.inputs["To Min"].default_value = 0.0
hz.inputs["To Max"].default_value = 1.0
link(nt, sepo.outputs["Z"], hz.inputs["Value"])
skym = nt.nodes.new("ShaderNodeMix")
skym.data_type = "RGBA"
skym.inputs["B"].default_value = (1.0, 0.93, 0.78, 1)
link(nt, hz.outputs[0], skym.inputs["Factor"])
link(nt, sky.outputs[0], skym.inputs["A"])
link(nt, skym.outputs["Result"], em.inputs["Color"])
em.inputs["Strength"].default_value = 1.15
link(nt, em.outputs[0], out.inputs["Surface"])
bpy.ops.mesh.primitive_plane_add(size=1, location=(0.0, 4.5, 1.2), rotation=(math.pi / 2, 0, 0))
outdoors = bpy.context.active_object
outdoors.scale = (9.0, 4.0, 1)
assign(outdoors, out_m)
outdoors.visible_shadow = False
# seen by the lens, the glass and the glaze, but it does not light the room:
# the sun through the blinds does that, which keeps the contre-jour contrast
outdoors.visible_diffuse = False

# ---------------------------------------------------------------- room

TABLE_W, TABLE_D = 0.92, 1.30
WALL_Y = 0.66
table = box("table", (TABLE_W * 2, TABLE_D, 0.04), (0.0, WALL_Y - TABLE_D / 2, -0.02), bevel=0.003)
assign(table, maple_m)

# wainscot under the sill, window trim, blinds
SILL_Z, HEAD_Z = 0.085, 1.30
wall = box("wall_low", (3.0, 0.04, SILL_Z + 0.8), (0.0, WALL_Y + 0.02, SILL_Z / 2 - 0.4))
assign(wall, paint_m)
sill = box("sill", (2.2, 0.10, 0.025), (0.0, WALL_Y - 0.01, SILL_Z + 0.0125), bevel=0.004)
assign(sill, trim_m)
for sx in (-1.15, 1.15):
    jamb = box(f"jamb{sx}", (0.06, 0.08, HEAD_Z - SILL_Z), (sx, WALL_Y, (SILL_Z + HEAD_Z) / 2))
    assign(jamb, trim_m)
mullion = box("mullion", (0.04, 0.05, HEAD_Z - SILL_Z), (0.62, WALL_Y + 0.02, (SILL_Z + HEAD_Z) / 2))
assign(mullion, trim_m)

SLAT_PITCH, SLAT_DEPTH, SLAT_TILT = 0.024, 0.025, -0.22
slat_mesh = None
slats = []
z = SILL_Z + 0.03
k = 0
while z < HEAD_Z:
    if slat_mesh is None:
        so = box("slat", (2.24, SLAT_DEPTH, 0.0012), (0, 0, 0))
        slat_mesh = so.data
        assign(so, slat_m)
    else:
        so = bpy.data.objects.new(f"slat{k}", slat_mesh)
        scene.collection.objects.link(so)
    so.location = (0.0, WALL_Y - 0.035, z)
    so.rotation_euler = (SLAT_TILT, 0, 0)
    slats.append(so)
    z += SLAT_PITCH
    k += 1
for lx in (-0.55, 0.55):  # ladder cords
    cord = box(f"cord{lx}", (0.0025, 0.0025, HEAD_Z - SILL_Z), (lx, WALL_Y - 0.035 - SLAT_DEPTH / 2, (SILL_Z + HEAD_Z) / 2))
    assign(cord, slat_m)

# ---------------------------------------------------------------- the mug

MX, MY = 0.065, 0.045
outer = [(0.0, 0.0), (0.030, 0.0), (0.0335, 0.0015), (0.0352, 0.004)]
for i in range(1, 15):
    t = i / 14
    z = 0.004 + t * (0.094 - 0.004)
    belly = 0.0352 + 0.0038 * math.sin(math.pi * min(1.0, t * 1.1)) + 0.0050 * t
    outer.append((belly, z))
outer += [(0.0418, 0.0955), (0.0410, 0.0968), (0.0398, 0.0972), (0.0386, 0.0964), (0.0380, 0.095)]
inner = []
for i in range(1, 13):
    t = i / 12
    z = 0.095 - t * (0.095 - 0.016)
    inner.append((0.0380 - 0.0035 * t ** 1.5, z))
inner += [(0.031, 0.0135), (0.026, 0.0125), (0.0, 0.0125)]
mug = lathe("mug", shell(outer, inner), 160)
mug.location = (MX, MY, 0)
mug.rotation_euler.z = -0.5
assign(mug, mug_m)

COFFEE_Z = 0.083
coffee = lathe("coffee", [(0.0, COFFEE_Z - 0.004), (0.0372, COFFEE_Z - 0.004), (0.0374, COFFEE_Z - 0.0005), (0.0369, COFFEE_Z), (0.0, COFFEE_Z)], 160)
coffee.location = (MX, MY, 0)
assign(coffee, coffee_m)

# handle: a fat C on the camera-right side, slightly toward the lens
hang = -0.55
hx, hy = math.cos(hang), math.sin(hang)
handle_pts = []
for (rr_, zz) in ((0.040, 0.079), (0.060, 0.080), (0.071, 0.060), (0.066, 0.034), (0.046, 0.022), (0.037, 0.024)):
    handle_pts.append((MX + rr_ * hx, MY + rr_ * hy, zz))
handle = tube("handle", handle_pts, 0.0062, handle_m)

# ---------------------------------------------------------------- steam

STEAM_H = 0.34
# unit cube scaled, not applied: object coords stay in -0.5..0.5
bpy.ops.mesh.primitive_cube_add(size=1, location=(MX, MY, COFFEE_Z + STEAM_H / 2 - 0.004))
steam_dom = bpy.context.active_object
steam_dom.name = "steam"
steam_dom.scale = (0.20, 0.20, STEAM_H)

steam_m, nt, out = mat("Steam")
pv = nt.nodes.new("ShaderNodeVolumePrincipled")
pv.inputs["Color"].default_value = (1.0, 0.98, 0.95, 1)
pv.inputs["Anisotropy"].default_value = 0.55
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
link(nt, tc.outputs["Object"], sep.inputs[0])
# h: 0 at the coffee, 1 at the top of the domain
h = nt.nodes.new("ShaderNodeMath")
h.operation = "ADD"
h.inputs[1].default_value = 0.5
link(nt, sep.outputs["Z"], h.inputs[0])


def math_node(op, a=None, b=None, va=None, vb=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    if a is not None:
        link(nt, a, n.inputs[0])
    elif va is not None:
        n.inputs[0].default_value = va
    if b is not None:
        link(nt, b, n.inputs[1])
    elif vb is not None:
        n.inputs[1].default_value = vb
    return n


# plume drifts sideways as it rises; the sway is set per frame
sway_x = math_node("MULTIPLY", math_node("POWER", h.outputs[0], vb=1.6).outputs[0], vb=0.0)
sway_y = math_node("MULTIPLY", math_node("POWER", h.outputs[0], vb=1.6).outputs[0], vb=0.0)
dx = math_node("SUBTRACT", sep.outputs["X"], sway_x.outputs[0])
dy = math_node("SUBTRACT", sep.outputs["Y"], sway_y.outputs[0])
rad = math_node("SQRT", math_node("ADD", math_node("MULTIPLY", dx.outputs[0], dx.outputs[0]).outputs[0],
                                  math_node("MULTIPLY", dy.outputs[0], dy.outputs[0]).outputs[0]).outputs[0])
width = math_node("ADD", math_node("MULTIPLY", h.outputs[0], vb=0.34).outputs[0], vb=0.13)
rn = math_node("DIVIDE", rad.outputs[0], width.outputs[0])
radial = nt.nodes.new("ShaderNodeMapRange")
radial.interpolation_type = "SMOOTHSTEP"
radial.inputs["From Min"].default_value = 1.0
radial.inputs["From Max"].default_value = 0.15
link(nt, rn.outputs[0], radial.inputs["Value"])
fade_in = nt.nodes.new("ShaderNodeMapRange")
fade_in.interpolation_type = "SMOOTHSTEP"
fade_in.inputs["From Min"].default_value = 0.0
fade_in.inputs["From Max"].default_value = 0.10
link(nt, h.outputs[0], fade_in.inputs["Value"])
fade_out = nt.nodes.new("ShaderNodeMapRange")
fade_out.interpolation_type = "SMOOTHSTEP"
fade_out.inputs["From Min"].default_value = 0.95
fade_out.inputs["From Max"].default_value = 0.35
link(nt, h.outputs[0], fade_out.inputs["Value"])
envelope = math_node("MULTIPLY", math_node("MULTIPLY", radial.outputs[0], fade_in.outputs[0]).outputs[0], fade_out.outputs[0])

steam_layers = []
for li in range(2):
    m_ = nt.nodes.new("ShaderNodeMapping")
    m_.inputs["Scale"].default_value = (1.3, 1.3, 0.62)  # stretched upward: rising filaments
    link(nt, tc.outputs["Object"], m_.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = 4.4
    nz.inputs["Detail"].default_value = 8.0
    nz.inputs["Roughness"].default_value = 0.62
    nz.inputs["Distortion"].default_value = 1.1
    link(nt, m_.outputs[0], nz.inputs["Vector"])
    steam_layers.append(dict(map=m_, noise=nz, seed=li * 17.0))
# variance-preserving crossfade: (w1 (n1 - .5) + w2 (n2 - .5)) / sqrt(w1^2 + w2^2) + .5
c1 = math_node("SUBTRACT", steam_layers[0]["noise"].outputs["Fac"], vb=0.5)
c2 = math_node("SUBTRACT", steam_layers[1]["noise"].outputs["Fac"], vb=0.5)
w1 = math_node("MULTIPLY", c1.outputs[0], vb=0.5)
w2 = math_node("MULTIPLY", c2.outputs[0], vb=0.5)
mixn = math_node("ADD", math_node("ADD", w1.outputs[0], w2.outputs[0]).outputs[0], vb=0.5)
# wisps: sharpen the noise into filaments
wisp = nt.nodes.new("ShaderNodeMapRange")
wisp.interpolation_type = "SMOOTHSTEP"
wisp.inputs["From Min"].default_value = 0.52
wisp.inputs["From Max"].default_value = 0.76
link(nt, mixn.outputs[0], wisp.inputs["Value"])
dens = math_node("MULTIPLY", wisp.outputs[0], envelope.outputs[0])
dens_k = math_node("MULTIPLY", dens.outputs[0], vb=40.0)
link(nt, dens_k.outputs[0], pv.inputs["Density"])
link(nt, pv.outputs[0], out.inputs["Volume"])
assign(steam_dom, steam_m)
steam_dom.visible_shadow = False

STEAM_RISE = 2.4   # object units each layer rises over one loop
STEAM_EVOLVE = 1.3  # 4D noise drift over one loop

# ---------------------------------------------------------------- sweet tea

TX, TY = 0.255, 0.255
t_out = [(0.0, 0.0), (0.0290, 0.0), (0.0300, 0.002)]
for i in range(1, 13):
    z = 0.002 + 0.148 * i / 12
    t_out.append((0.0300 + 0.0085 * (z / 0.15), z))
t_out += [(0.0386, 0.1505), (0.0381, 0.1512), (0.0375, 0.1505)]
t_in = []
for i in range(0, 12):
    z = 0.150 - (0.150 - 0.012) * i / 11
    t_in.append((0.0374 - 0.0083 * ((0.150 - z) / 0.138), z))
t_in += [(0.0283, 0.0108), (0.0, 0.0108)]
tumbler = lathe("tumbler", t_out + t_in, 128)
tumbler.location = (TX, TY, 0)
assign(tumbler, tumbler_m)


def r_tin(z):
    return 0.0291 + 0.0083 * (z - 0.012) / 0.138


TEA_Z = 0.118
tprof = [(0.0, 0.0111), (0.0286, 0.0111)]
for i in range(1, 8):
    z = 0.012 + (TEA_Z - 0.012) * i / 7
    tprof.append((r_tin(z) - 0.0002, z))
tprof.append((0.0, TEA_Z))
tea = lathe("tea", tprof, 128)
tea.location = (TX, TY, 0)
assign(tea, tea_m)

ice_cubes = []
for i, (ox, oy, oz, rz) in enumerate(((-0.010, 0.006, 0.112, 0.4), (0.011, -0.004, 0.110, 1.1), (0.002, 0.014, 0.103, 2.0), (-0.004, -0.012, 0.096, 0.8))):
    bpy.ops.mesh.primitive_cube_add(size=0.021, location=(TX + ox, TY + oy, oz))
    ic = bpy.context.active_object
    ic.name = f"ice{i}"
    ic.rotation_euler = (rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), rz)
    b = ic.modifiers.new("bev", "BEVEL")
    b.width = 0.0035
    b.segments = 3
    assign(ic, ice_m)
    ice_cubes.append(dict(ob=ic, base=ic.location.copy(), ph=rng.random()))


# ---------------------------------------------------------------- plate and biscuits

PX, PY = 0.165, -0.115
pprof = [(0.0, 0.0), (0.060, 0.0), (0.062, 0.003), (0.058, 0.0045), (0.075, 0.009), (0.112, 0.017), (0.116, 0.0185),
         (0.1165, 0.0175), (0.112, 0.0155), (0.075, 0.0075), (0.062, 0.006), (0.0, 0.006)]
plate = lathe("plate", pprof, 160)
plate.location = (PX, PY, 0)
assign(plate, plate_m)


def biscuit(name, loc, r=0.032, hgt=0.036, rot=0.0, seed=0.0):
    """Lathed biscuit: flat base, slightly flared sides with a layer seam,
    a soft domed top; low-frequency lumps and fine crumb via displacement."""
    prof = [(0.0, 0.0), (r * 0.90, 0.0), (r * 0.985, 0.0025), (r * 1.0, 0.007)]
    for i in range(1, 9):
        t = i / 8
        z = 0.007 + t * (hgt * 0.80 - 0.007)
        seam = -0.0012 * math.exp(-((t - 0.45) / 0.07) ** 2)  # where the layers part
        prof.append((r * (1.0 + 0.035 * math.sin(math.pi * t)) + seam, z))
    for i in range(1, 7):  # rounded shoulder
        a = (math.pi / 2) * i / 6
        prof.append((r * 1.0 - 0.009 * (1 - math.cos(a)), hgt * 0.80 + 0.0075 * math.sin(a)))
    for i in range(1, 7):  # gentle dome
        t = i / 6
        prof.append((r * (1 - 0.28) * (1 - t), hgt * 0.80 + 0.0075 + 0.0045 * math.sin(math.pi / 2 * t)))
    ob = lathe(name, prof, 96)
    ob.location = loc
    ob.rotation_euler.z = rot
    sub_ = ob.modifiers.new("sub", "SUBSURF")
    sub_.levels = sub_.render_levels = 1
    for nm, scale, strength, depth in (("lumps", 0.016, 0.0026, 2), ("crumb", 0.0022, 0.0006, 4)):
        tex = bpy.data.textures.new(f"{name}_{nm}", "CLOUDS")
        tex.noise_scale = scale
        tex.noise_depth = depth
        dp = ob.modifiers.new(nm, "DISPLACE")
        dp.texture = tex
        dp.texture_coords = "GLOBAL"
        dp.strength = strength
        dp.mid_level = 0.5
    ob.data.shade_smooth()
    assign(ob, biscuit_m)
    return ob


b0 = biscuit("biscuit0", (PX - 0.030, PY + 0.022, 0.0064), rot=0.3)
biscuit("biscuit1", (PX + 0.037, PY - 0.012, 0.0064), r=0.031, hgt=0.034, rot=1.4)
bpy.context.view_layer.update()
_me = b0.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
_top = max((b0.matrix_world @ v.co).z for v in _me.vertices if ((b0.matrix_world @ v.co).xy - Vector((PX - 0.028, PY + 0.020))).length < 0.01)
b0.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
pat = box("butter", (0.016, 0.016, 0.006), (PX - 0.028, PY + 0.020, _top + 0.0026), bevel=0.002)
pat.rotation_euler = (0.08, -0.05, 0.6)
assign(pat, butter_m)

# ---------------------------------------------------------------- condiments by the window

# chrome napkin dispenser with napkins showing at the slot
NDX, NDY = -0.30, 0.545
disp_body = box("dispenser", (0.125, 0.085, 0.128), (NDX, NDY, 0.064), bevel=0.012, segs=5)
assign(disp_body, chrome_m)
nap = box("napkins", (0.10, 0.006, 0.090), (NDX, NDY - 0.043, 0.072), bevel=0.001)
assign(nap, napkin_m)

# glass sugar pourer with chrome cap
SPX, SPY = -0.115, 0.535
sp_out = [(0.0, 0.0), (0.030, 0.0), (0.0315, 0.004), (0.0315, 0.098), (0.029, 0.102), (0.0275, 0.098), (0.0275, 0.008), (0.0, 0.008)]
spg = lathe("sugar_glass", sp_out, 64)
spg.location = (SPX, SPY, 0)
assign(spg, glass_m)
sug = lathe("sugar", [(0.0, 0.0085), (0.0272, 0.0085), (0.0272, 0.060), (0.0, 0.066)], 48)
sug.location = (SPX, SPY, 0)
assign(sug, sugar_m)
cap = lathe("sugar_cap", [(0.0, 0.140), (0.006, 0.139), (0.012, 0.128), (0.026, 0.112), (0.0322, 0.104), (0.0322, 0.096), (0.0, 0.096)], 64)
cap.location = (SPX, SPY, 0)
assign(cap, chrome_m)

# salt and pepper
for i, (sx, sy, fill) in enumerate(((-0.040, 0.560, (0.9, 0.9, 0.88)), (0.000, 0.575, (0.06, 0.05, 0.045)))):
    shp = lathe(f"shaker{i}", [(0.0, 0.0), (0.017, 0.0), (0.018, 0.004), (0.016, 0.060), (0.0, 0.060)], 48)
    shp.location = (sx, sy, 0)
    assign(shp, glass_m)
    gm, *_ = principled(f"grains{i}", fill, rough=0.6)
    gr = lathe(f"grains{i}", [(0.0, 0.002), (0.0165, 0.002), (0.0155, 0.040), (0.0, 0.042)], 32)
    gr.location = (sx, sy, 0)
    assign(gr, gm)
    tp = lathe(f"shaker_top{i}", [(0.0, 0.075), (0.012, 0.074), (0.0165, 0.066), (0.0168, 0.058), (0.0, 0.058)], 48)
    tp.location = (sx, sy, 0)
    assign(tp, chrome_m)

# red squeeze bottle
SQX, SQY = -0.215, 0.455
sq = lathe("squeeze", [(0.0, 0.0), (0.026, 0.0), (0.0285, 0.006), (0.0290, 0.150), (0.027, 0.158), (0.012, 0.166), (0.011, 0.172),
                       (0.007, 0.174), (0.003, 0.205), (0.0, 0.206)], 64)
sq.location = (SQX, SQY, 0)
assign(sq, squeeze_m)

# ---------------------------------------------------------------- lights

sun_d = bpy.data.lights.new("sun", "SUN")
sun_d.energy = 8.0
sun_d.angle = math.radians(0.9)
sun_d.color = (1.0, 0.80, 0.56)
sun = bpy.data.objects.new("sun", sun_d)
scene.collection.objects.link(sun)
SUN_DIR = Vector((-0.34, -0.88, -0.36)).normalized()  # direction light travels
sun.rotation_euler = SUN_DIR.to_track_quat("-Z", "Y").to_euler()
SUN_BASE = sun.rotation_euler.copy()


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
    lo.visible_glossy = True
    return lo


# soft daylight bouncing back from the room (behind camera), cooler
fill = area("room_fill", (0.1, -1.4, 0.7), (MX, MY, 0.05), (1.6, 0.9), 2.2, (0.82, 0.88, 1.0))
fill.visible_glossy = False
# skylight spilling through the blinds, wide and soft
area("window_soft", (0.0, WALL_Y - 0.06, 0.75), (0.05, 0.0, 0.0), (2.0, 0.9), 1.2, (1.0, 0.93, 0.82))
# long highlight strip for the mug glaze and chrome (specular only)
gl = area("glaze_spec", (MX + 0.35, MY - 0.15, 0.30), (MX, MY, 0.06), (0.06, 0.5), 2.2, (1.0, 0.92, 0.82))
gl.visible_diffuse = False
gl.visible_transmission = False
gl.visible_volume_scatter = False
# backlight for the steam only: behind the plume, aimed at the lens, so the
# forward-scattering volume glows as one form between the slat-light bands
sk = area("steam_key", (MX + 0.06, MY + 0.34, 0.24), (MX, MY, 0.15), (0.30, 0.30), 2.4, (1.0, 0.86, 0.66))
sk.visible_diffuse = False
sk.visible_glossy = False
sk.visible_transmission = False

# ---------------------------------------------------------------- camera

target = bpy.data.objects.new("target", None)
target.location = (0.045, 0.12, 0.092)
scene.collection.objects.link(target)
focus = bpy.data.objects.new("focus", None)
focus.location = (MX, MY - 0.035, 0.07)
scene.collection.objects.link(focus)

camd = bpy.data.cameras.new("cam")
camd.lens = 45
camd.sensor_width = 36
camd.dof.use_dof = True
camd.dof.focus_object = focus
camd.dof.aperture_fstop = 2.2
camd.dof.aperture_blades = 0
cam = bpy.data.objects.new("cam", camd)
scene.collection.objects.link(cam)
scene.camera = cam
tt = cam.constraints.new("TRACK_TO")
tt.target = target
tt.track_axis = "TRACK_NEGATIVE_Z"
tt.up_axis = "UP_Y"

CAM_BASE = Vector((-0.035, -0.47, 0.150))

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
c.volume_bounces = 1
c.caustics_reflective = False
c.caustics_refractive = False
c.blur_glossy = 0.6
c.sample_clamp_indirect = 6.0
c.sample_clamp_direct = 0.0
c.volume_step_rate = 1.0
c.seed = 7
c.use_animated_seed = True
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception as e:
    print("view", e)
scene.view_settings.exposure = 0.0
scene.render.threads_mode = "AUTO"

if args.blend:
    bpy.ops.wm.save_as_mainfile(filepath=args.blend)

# ---------------------------------------------------------------- per-frame state


def tri(u):
    """Triangle weight: 0 at u = 0 and 1, 1 at u = 0.5."""
    return 1.0 - abs(2.0 * u - 1.0)


def set_frame(f):
    u = f / N
    th = TAU * u
    cam.location = CAM_BASE + Vector((0.040 * math.sin(th), 0.022 * (math.cos(th) - 1), 0.008 * math.sin(2 * th + 0.7)))
    # steam: each layer rises STEAM_RISE per loop and resets at zero weight
    ws = []
    for li, L in enumerate(steam_layers):
        ph = (u + 0.5 * li) % 1.0
        ws.append(tri(ph))
        L["map"].inputs["Location"].default_value = (L["seed"] * 0.37, L["seed"] * 0.61, -STEAM_RISE * ph + L["seed"])
        L["noise"].inputs["W"].default_value = L["seed"] + STEAM_EVOLVE * ph
    norm = math.sqrt(ws[0] ** 2 + ws[1] ** 2)
    w1.inputs[1].default_value = ws[0] / norm
    w2.inputs[1].default_value = ws[1] / norm
    # the plume leans with the room air, one slow figure per loop
    sway_x.inputs[1].default_value = 0.20 * math.sin(th) + 0.07 * math.sin(3 * th + 1.1)
    sway_y.inputs[1].default_value = 0.10 * math.cos(th + 0.4) + 0.04 * math.sin(2 * th)
    # blinds breathe in a draft; leaves shimmer outside
    for i, so in enumerate(slats):
        so.rotation_euler.x = SLAT_TILT + 0.012 * math.sin(th + i * 0.11)
    leaf_map.inputs["Location"].default_value = (0.35 * math.cos(th), 0.0, 0.35 * math.sin(th))
    sun_d.energy = 8.0 * (1 + 0.025 * math.sin(2 * th) + 0.015 * math.sin(5 * th + 0.7))
    for ic in ice_cubes:
        b = ic["base"]
        ic["ob"].location = (b.x, b.y, b.z + 0.0006 * math.sin(th + TAU * ic["ph"]))


if args.probe:
    from bpy_extras.object_utils import world_to_camera_view
    set_frame(0)
    bpy.context.view_layer.update()
    for name in ("mug", "tumbler", "plate", "dispenser", "sugar_glass", "squeeze", "biscuit0", "biscuit1"):
        ob = bpy.data.objects[name]
        dg = bpy.context.evaluated_depsgraph_get()
        me = ob.evaluated_get(dg).to_mesh()
        pts = [world_to_camera_view(scene, cam, ob.matrix_world @ v.co) for v in me.vertices]
        xs = [q.x for q in pts]
        ys = [q.y for q in pts]
        print(f"{name}: x[{min(xs):.2f},{max(xs):.2f}] y[{min(ys):.2f},{max(ys):.2f}]")
    sys.exit(0)

spec = [int(v) for v in args.frames.split(":")]
start, end = spec[0], spec[1]
step = spec[2] if len(spec) > 2 else 1

for f in range(start, end, step):
    t0 = time.time()
    scene.frame_set(f % N)
    set_frame(f % N)
    r.filepath = f"{args.out}/f{f:04d}.png"
    bpy.ops.render.render(write_still=True)
    print(f"FRAME {f} {time.time() - t0:.1f}s", flush=True)
