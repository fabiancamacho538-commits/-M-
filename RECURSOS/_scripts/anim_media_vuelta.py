"""
Animación 3D "media vuelta": el iPhone arranca mostrando la PANTALLA y gira 180° hasta mostrar
la TRASERA, con fondo transparente. Usa el modelo 3D oficial de Apple (USDZ de AR Quick Look).
Se ejecuta con el Python de Blender (módulo bpy):

    blenv/bin/python anim_media_vuelta.py -- modelo.usdz carpeta_frames/ [ancho alto frames muestras]

Variables de entorno: EXPO (exposición en stops), HIDE (mallas a ocultar, separadas por coma),
KEEP (en archivos con dos equipos, el objeto raíz del que se anima), TEX_DIR (PNG de las texturas HEIC),
INVERTIR (invierte la detección pantalla/trasera), FRAME (sólo ese cuadro, para pruebas), GIRO (grados, por defecto 180), INCL (inclinación
de cámara en grados, por defecto 4).
"""
import sys, os, math
import bpy, mathutils
import numpy as np

args = sys.argv[sys.argv.index('--') + 1:]
src, outdir = args[0], args[1]
RW = int(args[2]) if len(args) > 2 else 1080
RH = int(args[3]) if len(args) > 3 else 1920
NF = int(args[4]) if len(args) > 4 else 60
SPP = int(args[5]) if len(args) > 5 else 12
os.makedirs(outdir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=src)
sc = bpy.context.scene
# algunos modelos AR traen animación propia (Transform Cache / Mesh Sequence Cache): se congela
sc.frame_set(0)
bpy.context.view_layer.update()
mundo = {o.name: o.matrix_world.copy() for o in sc.objects}
for o in sc.objects:
    for c in list(o.constraints):
        if c.type == 'TRANSFORM_CACHE':
            o.constraints.remove(c)
    for m in list(getattr(o, 'modifiers', [])):
        if m.type == 'MESH_SEQUENCE_CACHE':
            o.modifiers.remove(m)
    o.animation_data_clear()


def _prof(o):
    n = 0
    while o.parent: o = o.parent; n += 1
    return n


for o in sorted(sc.objects, key=_prof):  # padres primero
    o.matrix_world = mundo[o.name]
    bpy.context.view_layer.update()


def verts(o):
    n = len(o.data.vertices); a = np.empty(n * 3); o.data.vertices.foreach_get('co', a); a = a.reshape(-1, 3)
    M = np.array(o.matrix_world); return a @ M[:3, :3].T + M[:3, 3]


allm = [o for o in sc.objects if o.type == 'MESH']
big = [o for o in allm if len(o.data.vertices) > 200]
ref_h = max(max(o.dimensions) for o in big)
for o in allm:  # cajas/planos auxiliares de AR (más grandes que el equipo, o volúmenes no planos)
    d = sorted(o.dimensions)
    if (len(o.data.vertices) <= 64 and d[2] > ref_h * 1.05) or d[0] > ref_h * 0.3:
        o.hide_render = True
# texturas HEIC (Blender no las lee): usar las versiones PNG convertidas en TEX_DIR
tex_dir = os.environ.get('TEX_DIR')
if tex_dir:
    reempl = {}
    for im in list(bpy.data.images):
        stem, ext = os.path.splitext(im.name)
        png = os.path.join(tex_dir, stem + '.png')
        if ext.lower() == '.heic' and os.path.exists(png):
            nuevo = bpy.data.images.load(png)
            nuevo.colorspace_settings.name = im.colorspace_settings.name
            reempl[im.name] = nuevo
    for mat in bpy.data.materials:  # las HEIC vienen empaquetadas: se cambia la imagen del nodo
        if mat.use_nodes:
            for nd in mat.node_tree.nodes:
                if nd.type == 'TEX_IMAGE' and nd.image and nd.image.name in reempl:
                    nd.image = reempl[nd.image.name]
for o in allm:
    if o.name in os.environ.get('HIDE', '').split(','):
        o.hide_render = True
keep = os.environ.get('KEEP')  # archivos con dos equipos (p. ej. 17 Pro + 17 Pro Max): deja sólo uno
if keep:
    dentro = set(bpy.data.objects[keep].children_recursive) | {bpy.data.objects[keep]}
    for o in allm:
        if o not in dentro:
            o.hide_render = True
seen = {}
for o in allm:  # mallas duplicadas coincidentes (z-fighting)
    if o.hide_render: continue
    vv = verts(o)
    key = (len(vv), tuple(np.round(vv.min(0) * 1e4).astype(int)), tuple(np.round(vv.max(0) * 1e4).astype(int)), round(float(vv.sum()) * 1e3))
    if key in seen: o.hide_render = True
    else: seen[key] = o.name
meshes = [o for o in allm if not o.hide_render]
for o in allm:
    if o.hide_render: o.hide_viewport = True

V = np.concatenate([verts(o) for o in meshes])
mn, mx = V.min(0), V.max(0); ctr = (mn + mx) / 2; ext = mx - mn
z0, Hh = mn[2], ext[2]
mid = V[(V[:, 2] > z0 + 0.30 * Hh) & (V[:, 2] < z0 + 0.60 * Hh)]
top = V[V[:, 2] > z0 + 0.72 * Hh]
ax = 0 if ext[0] < ext[1] else 1
b0, b1 = np.percentile(mid[:, ax], 0.5), np.percentile(mid[:, ax], 99.5)
back_neg = (b0 - top[:, ax].min()) > (top[:, ax].max() - b1)
# dirección hacia la que mira la PANTALLA (opuesta a las cámaras)
if os.environ.get('INVERTIR'):  # modelos con geometría frontal que confunde la detección
    back_neg = not back_neg
front = np.zeros(3); front[ax] = 1.0 if back_neg else -1.0
front_v = mathutils.Vector(front)


# pivote en el centro del equipo: todo cuelga de él y gira sobre Z
piv = bpy.data.objects.new('pivote', None); sc.collection.objects.link(piv)
piv.location = mathutils.Vector(ctr)
bpy.context.view_layer.update()  # el pivote debe tener su posición antes de colgarle el equipo
roots = [o for o in sc.objects if o.parent is None and o is not piv]
for o in roots:
    mw = o.matrix_world.copy(); o.parent = piv; o.matrix_world = mw

# cámara en perspectiva, de frente a la pantalla, levemente elevada
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = 85; cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 24
cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
vfov = 2 * math.atan(cam_d.sensor_height / (2 * cam_d.lens))
D = (Hh / 0.78) / (2 * math.tan(vfov / 2))
incl = math.radians(float(os.environ.get('INCL', '4')))
c = mathutils.Vector(ctr)
cam.location = c + front_v * D * math.cos(incl) + mathutils.Vector((0, 0, D * math.sin(incl)))
cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam_d.clip_start = 0.01; cam_d.clip_end = 10

# iluminación fija respecto de la cámara (estudio suave + HDRI de Blender para reflejos)
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True
nt = world.node_tree; bg = nt.nodes['Background']
env = nt.nodes.new('ShaderNodeTexEnvironment')
env.image = bpy.data.images.load(os.path.join(bpy.utils.system_resource('DATAFILES', path='studiolights/world'), 'interior.exr'))
nt.links.new(env.outputs['Color'], bg.inputs['Color']); bg.inputs['Strength'].default_value = 0.35
right = front_v.cross(mathutils.Vector((0, 0, 1))).normalized() * -1


def area(name, offset, energy, sx, sy):
    d = bpy.data.lights.new(name, 'AREA'); d.energy = energy; d.shape = 'RECTANGLE'; d.size = sx; d.size_y = sy
    o = bpy.data.objects.new(name, d); sc.collection.objects.link(o)
    o.location = c + offset; o.rotation_euler = (c - o.location).to_track_quat('-Z', 'Y').to_euler()


area('key', -right * 0.25 + front_v * 0.35 + mathutils.Vector((0, 0, 0.30)), 0.9, 0.35, 0.35)
area('fill', right * 0.30 + front_v * 0.30 + mathutils.Vector((0, 0, 0.05)), 0.4, 0.30, 0.50)
area('top', front_v * 0.10 + mathutils.Vector((0, 0, 0.45)), 0.3, 0.40, 0.20)
area('rim', -front_v * 0.30 + right * 0.20 + mathutils.Vector((0, 0, 0.20)), 0.5, 0.20, 0.40)

# animación: 0° (pantalla) -> 180° (trasera), con entrada y salida suaves
giro = math.radians(float(os.environ.get('GIRO', '180')))
sc.frame_start, sc.frame_end = 0, NF
piv.rotation_euler = (0, 0, 0); piv.keyframe_insert('rotation_euler', frame=0)
piv.rotation_euler = (0, 0, giro); piv.keyframe_insert('rotation_euler', frame=NF)
for fc in (piv.animation_data.action.fcurves if hasattr(piv.animation_data.action, 'fcurves') else []):
    for kp in fc.keyframe_points:
        kp.interpolation = 'BEZIER'; kp.easing = 'AUTO'

r = sc.render
r.resolution_x, r.resolution_y, r.resolution_percentage = RW, RH, 100
r.fps = 30
r.film_transparent = True
r.engine = 'CYCLES'
sc.cycles.device = 'CPU'; sc.cycles.samples = SPP; sc.cycles.use_denoising = True
sc.cycles.use_adaptive_sampling = True
sc.cycles.max_bounces = 8; sc.cycles.glossy_bounces = 4; sc.cycles.transmission_bounces = 6
r.use_persistent_data = True
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGBA'; r.image_settings.color_depth = '8'
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
sc.view_settings.exposure = float(os.environ.get('EXPO', '0'))

only = os.environ.get('FRAME')
rng = os.environ.get('RANGO')  # p. ej. "0-3"
if only: frames = [int(only)]
elif rng: a_, b_ = map(int, rng.split('-')); frames = range(a_, b_ + 1)
else: frames = range(sc.frame_start, sc.frame_end + 1)
import time
for f in frames:
    sc.frame_set(f)
    if os.environ.get('DEBUG'):
        bpy.context.view_layer.update()
        W_ = np.concatenate([verts(o) for o in meshes])
        print('DBG frame', f, 'bbox_mm', [round(float(v)*1000, 1) for v in W_.min(0)], [round(float(v)*1000, 1) for v in W_.max(0)],
              'cam', [round(v*1000, 1) for v in cam.location], flush=True)
        for im in bpy.data.images:
            if im.name.lower().endswith('.heic'):
                print('DBG img', im.name, im.filepath, 'packed', bool(im.packed_file), 'size', tuple(im.size), flush=True)
                break
    r.filepath = os.path.join(outdir, f'{f:04d}.png')
    t0 = time.time(); bpy.ops.render.render(write_still=True); print('FRAME', f, round(time.time() - t0, 1), 's', flush=True)
print('OK', outdir, len(list(frames)), 'frames', RW, RH)
