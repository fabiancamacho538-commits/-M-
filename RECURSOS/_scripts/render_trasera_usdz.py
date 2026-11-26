"""
Render ortográfico de la TRASERA de un modelo 3D oficial de Apple (USDZ de AR Quick Look,
publicado en apple.com) con fondo transparente. Se ejecuta con el Python de Blender (módulo bpy):

    uv venv -p 3.11 blenv && VIRTUAL_ENV=blenv uv pip install bpy
    blenv/bin/python render_trasera_usdz.py -- modelo.usdz salida.png alto_px [auto|-y|+y|-x|+x] [muestras]

Variables de entorno: EXPO (exposición en stops), HIDE (mallas a ocultar, separadas por coma),
DEPTH (8|16 bits), KEY/ENV/HDRI (iluminación). El lado trasero se detecta solo: es la cara
hacia la que sobresale el módulo de cámaras. Se ocultan automáticamente las cajas auxiliares
de AR y las mallas duplicadas coincidentes (evita z-fighting).
"""
import sys, math, os, bpy, mathutils
args = sys.argv[sys.argv.index('--')+1:]
src, out, H = args[0], args[1], int(args[2])
side = args[3] if len(args) > 3 else 'auto'
samples = int(args[4]) if len(args) > 4 else 128
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=src)
sc = bpy.context.scene
import numpy as np
def verts(o):
    n=len(o.data.vertices); a=np.empty(n*3); o.data.vertices.foreach_get('co',a); a=a.reshape(-1,3)
    M=np.array(o.matrix_world); return a@M[:3,:3].T+M[:3,3]
allm = [o for o in sc.objects if o.type == 'MESH']
big = [o for o in allm if len(o.data.vertices) > 200]
ref_h = max(max(o.dimensions) for o in big)
hidden = []
for o in allm:  # cajas/planos auxiliares de AR (oclusión, sombra) más grandes que el equipo
    if len(o.data.vertices) <= 64 and max(o.dimensions) > ref_h * 1.05:
        o.hide_render = True; hidden.append(o.name)
for o in allm:
    if o.name in os.environ.get('HIDE','').split(','): o.hide_render = True; hidden.append(o.name)
seen = {}
for o in allm:
    if o.hide_render: continue
    vv = verts(o)
    key = (len(vv), tuple(np.round(vv.min(0)*1e4).astype(int)), tuple(np.round(vv.max(0)*1e4).astype(int)), round(float(vv.sum())*1e3))
    if key in seen: o.hide_render = True; hidden.append(o.name+'(dup)')
    else: seen[key] = o.name
meshes = [o for o in allm if not o.hide_render]
V = np.concatenate([verts(o) for o in meshes])
z0, z1 = V[:,2].min(), V[:,2].max(); Hh = z1 - z0
mid = V[(V[:,2] > z0+0.30*Hh) & (V[:,2] < z0+0.60*Hh)]
top = V[V[:,2] > z0+0.72*Hh]
ext = V.max(0) - V.min(0)
ax = 0 if ext[0] < ext[1] else 1           # eje del grosor del equipo
b0, b1 = np.percentile(mid[:,ax], 0.5), np.percentile(mid[:,ax], 99.5)
bump_neg, bump_pos = b0 - top[:,ax].min(), top[:,ax].max() - b1
axn = 'x' if ax == 0 else 'y'
if side == 'auto':
    side = ('-' if bump_neg > bump_pos else '+') + axn
print('hidden', hidden, 'bump-y', round(bump_neg*1000,2), 'bump+y', round(bump_pos*1000,2), 'side', side)
mn = mathutils.Vector((1e9,)*3); mx = mathutils.Vector((-1e9,)*3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ mathutils.Vector(c)
        mn = mathutils.Vector(map(min, mn, w)); mx = mathutils.Vector(map(max, mx, w))
ctr = (mn + mx) / 2; size = mx - mn
w_ = size.y if side.endswith('x') else size.x
h_ = size.z
margin = 1.02
# cámara ortográfica
cam_data = bpy.data.cameras.new('cam'); cam_data.type = 'ORTHO'
cam = bpy.data.objects.new('cam', cam_data); sc.collection.objects.link(cam); sc.camera = cam
dist = 1.0
if side == '-y':
    cam.location = (ctr.x, mn.y - dist, ctr.z); cam.rotation_euler = (math.pi/2, 0, 0)
elif side == '+y':
    cam.location = (ctr.x, mx.y + dist, ctr.z); cam.rotation_euler = (math.pi/2, 0, math.pi)
elif side == '-x':
    cam.location = (mn.x - dist, ctr.y, ctr.z); cam.rotation_euler = (math.pi/2, 0, -math.pi/2)
else:
    cam.location = (mx.x + dist, ctr.y, ctr.z); cam.rotation_euler = (math.pi/2, 0, math.pi/2)
cam_data.sensor_fit = 'VERTICAL'; cam_data.ortho_scale = h_ * margin
cam_data.clip_start = 0.001; cam_data.clip_end = 10
r = sc.render
r.resolution_y = H; r.resolution_x = int(round(H * (w_ * margin + (h_-w_)*0) / (h_ * margin) * 1.0 + H*0.0)); r.resolution_x = int(round(H * w_ / h_ + H*(margin-1)))
r.resolution_percentage = 100
r.film_transparent = True
r.engine = 'CYCLES'
sc.cycles.device = 'CPU'; sc.cycles.samples = samples; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 12; sc.cycles.glossy_bounces = 6; sc.cycles.transmission_bounces = 8
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGBA'; r.image_settings.color_depth = os.environ.get('DEPTH','8')
sc.view_settings.view_transform = os.environ.get('VT', 'Standard'); sc.view_settings.look = 'None'
sc.view_settings.exposure = float(os.environ.get('EXPO', '0'))
# entorno de estudio (HDRI incluido en Blender) para reflejos suaves
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True
nt = world.node_tree; bg = nt.nodes['Background']
sl = bpy.utils.system_resource('DATAFILES', path='studiolights/world')
hdr = os.path.join(sl, os.environ.get('HDRI', 'interior.exr'))
env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(hdr)
nt.links.new(env.outputs['Color'], bg.inputs['Color']); bg.inputs['Strength'].default_value = float(os.environ.get('ENV', '0.35'))
# softboxes: luz principal arriba-izquierda, relleno derecha, contraluz arriba
def area(name, loc, energy, sizex, sizey):
    d = bpy.data.lights.new(name, 'AREA'); d.energy = energy; d.shape = 'RECTANGLE'; d.size = sizex; d.size_y = sizey
    o = bpy.data.objects.new(name, d); sc.collection.objects.link(o); o.location = loc
    direction = ctr - mathutils.Vector(loc); o.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
sgn = -1 if side.startswith('-') else 1
def L(dx, dn, dz):  # dx: lateral (derecha de cámara), dn: hacia la cámara, dz: arriba
    if side.endswith('y'):
        lat = dx if side == '-y' else -dx
        return (ctr.x + lat, ctr.y + sgn*dn, ctr.z + dz)
    lat = -dx if side == '-x' else dx
    return (ctr.x + sgn*dn, ctr.y + lat, ctr.z + dz)
K = float(os.environ.get('KEY', '0.015'))
area('key',  L(-0.25, 0.35, 0.30), 60*K, 0.35, 0.35)
area('fill', L( 0.30, 0.30, 0.05), 25*K, 0.30, 0.50)
area('top',  L( 0.00, 0.10, 0.45), 20*K, 0.40, 0.20)
r.filepath = out
bpy.ops.render.render(write_still=True)
print('OK', out, r.resolution_x, r.resolution_y, 'size_mm', round(w_*1000,1), round(size.y*1000,1), round(h_*1000,1))
