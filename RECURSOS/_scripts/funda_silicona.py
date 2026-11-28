"""
Funda de silicona puesta sobre el modelo 3D oficial del iPhone (USDZ de AR Quick Look de Apple).
La carcasa se construye alrededor del contorno medido del equipo: pared de 1,3 mm, borde que abraza
la pantalla, recorte de la meseta de cámaras y logo de Apple tomado de la foto oficial de la funda.
Exporta un .usdc sólo con la funda; anim_media_vuelta.py la carga sobre el USDZ oficial con EXTRA_USD
(KEEP=<grupo> EXTRA_USD=funda.usdc FILL=0.78 EXPO=0.3) y funda_post.py calibra el color contra la foto oficial.

    blenv/bin/python funda_silicona.py -- iphone.usdz GRUPO_KEEP "R G B" logo_mask.png salida.usdc
      GRUPO_KEEP: objeto raíz del equipo en archivos con dos teléfonos ('-' si hay uno solo)
      "R G B": color sRGB de la silicona medido en la foto oficial (p. ej. "170.2 57.8 130.7")
"""
import sys, math, os
import bpy, bmesh, mathutils
import numpy as np

args = sys.argv[sys.argv.index('--') + 1:]
src, keep, rgb, logo_png, salida = args[0], args[1], args[2], args[3], args[4]
MM = 0.001
PARED, LABIO, R_LOGO_W, LOGO_Y = 1.3, 1.25, 0.196, 0.486  # mm, mm, fracción del ancho, fracción de la altura

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=src)
sc = bpy.context.scene
if keep and keep != '-':
    dentro = set(bpy.data.objects[keep].children_recursive) | {bpy.data.objects[keep]}
    for o in list(sc.objects):
        if o not in dentro and o.type == 'MESH':
            bpy.data.objects.remove(o, do_unlink=True)


def verts(o):
    n = len(o.data.vertices); a = np.empty(n * 3); o.data.vertices.foreach_get('co', a); a = a.reshape(-1, 3)
    M = np.array(o.matrix_world); return a @ M[:3, :3].T + M[:3, 3]


ms = [o for o in sc.objects if o.type == 'MESH']
V = np.concatenate([verts(o) for o in ms]) / MM  # en mm
mn, mx = V.min(0), V.max(0); ext = mx - mn
ax = 0 if ext[0] < ext[1] else 1          # eje del grosor
lat = 1 - ax                               # eje del ancho
z0, Hh = mn[2], ext[2]
mid = V[(V[:, 2] > z0 + 0.30 * Hh) & (V[:, 2] < z0 + 0.60 * Hh)]
top = V[V[:, 2] > z0 + 0.72 * Hh]
b0, b1 = np.percentile(mid[:, ax], 0.5), np.percentile(mid[:, ax], 99.5)
back_neg = (b0 - top[:, ax].min()) > (top[:, ax].max() - b1)
s_back = -1.0 if back_neg else 1.0         # la trasera está hacia s_back en el eje ax
cuerpo_frente = b1 if back_neg else b0     # plano de la pantalla
cuerpo_dorso = b0 if back_neg else b1      # plano del dorso (sin la meseta)
x_min, x_max = np.percentile(mid[:, lat], 0.2), np.percentile(mid[:, lat], 99.8)
W = x_max - x_min; H = Hh; xc = (x_min + x_max) / 2; zc = z0 + Hh / 2
# meseta de cámaras: vértices más allá del dorso
mas_alla = V[(V[:, ax] - cuerpo_dorso) * s_back > 0.4]
p_xmin, p_xmax = mas_alla[:, lat].min(), mas_alla[:, lat].max()
p_zmin, p_zmax = mas_alla[:, 2].min(), mas_alla[:, 2].max()
print('equipo mm: ancho', round(W, 1), 'alto', round(H, 1), 'grosor cuerpo', round(abs(b1 - b0), 1),
      'meseta', round(p_xmax - p_xmin, 1), 'x', round(p_zmax - p_zmin, 1))
R_TEL = 0.155 * W  # radio de esquina del equipo (proporción de los iPhone recientes)


def prisma(nombre, w, h, d, r, centro, segs=24, bisel=0.0):
    """Prisma de sección rectangular redondeada w x h (en el plano lat-Z) y profundidad d (en ax)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= w; v.co.y *= d; v.co.z *= h
    vert_e = [e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).normalized().y) > 0.99]
    bmesh.ops.bevel(bm, geom=vert_e, offset=r, segments=segs, affect='EDGES', profile=0.5)
    me = bpy.data.meshes.new(nombre); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(nombre, me); sc.collection.objects.link(o)
    # el eje "y" local es el grosor: si el grosor real es X, rotar 90° en Z
    if ax == 0:
        o.rotation_euler = (0, 0, math.radians(90))
    loc = [0.0, 0.0, 0.0]; loc[lat] = centro[0]; loc[ax] = centro[1]; loc[2] = centro[2]
    o.location = mathutils.Vector(loc) * MM
    o.scale = (MM, MM, MM)
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    o.select_set(False)
    if bisel > 0:
        md = o.modifiers.new('b', 'BEVEL'); md.width = bisel * MM; md.segments = 8
        md.limit_method = 'ANGLE'; md.angle_limit = math.radians(40)
        bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier=md.name)
    return o


def restar(a, b):
    md = a.modifiers.new('bool', 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.object = b; md.solver = 'EXACT'
    bpy.context.view_layer.objects.active = a; bpy.ops.object.modifier_apply(modifier=md.name)
    bpy.data.objects.remove(b, do_unlink=True)


# dimensiones de la funda (todo en mm, coordenadas del equipo)
frente_case = cuerpo_frente - s_back * 0.9          # el borde sobresale 0,9 mm por delante de la pantalla
dorso_case = cuerpo_dorso + s_back * PARED           # pared trasera
prof = abs(dorso_case - frente_case); centro_ax = (dorso_case + frente_case) / 2
funda = prisma('funda', W + 2 * PARED, H + 2 * PARED, prof, R_TEL + PARED, (xc, centro_ax, zc), bisel=2.2)
# cavidad del equipo (desde un poco detrás del frente hasta el dorso)
cav_d = abs(cuerpo_dorso - (cuerpo_frente + s_back * 0.35)) + 0.02
cav_c = (cuerpo_dorso + cuerpo_frente + s_back * 0.35) / 2
restar(funda, prisma('cav', W + 0.15, H + 0.15, cav_d, R_TEL, (xc, cav_c, zc)))
# abertura frontal (el labio cubre LABIO mm del borde del equipo)
restar(funda, prisma('abertura', W - 2 * LABIO, H - 2 * LABIO, 6.0, R_TEL - LABIO, (xc, cuerpo_frente - s_back * 2.0, zc)))
# recorte de la meseta de cámaras (atraviesa la pared trasera)
m = 0.9
pw, ph = (p_xmax - p_xmin) + 2 * m, (p_zmax - p_zmin) + 2 * m
restar(funda, prisma('camara', pw, ph, 12.0, min(R_TEL - 1.0, 0.25 * ph), ((p_xmin + p_xmax) / 2, cuerpo_dorso + s_back * 3, (p_zmin + p_zmax) / 2)))
bpy.context.view_layer.objects.active = funda; bpy.ops.object.shade_smooth()
md = funda.modifiers.new('nrm', 'WEIGHTED_NORMAL'); bpy.ops.object.modifier_apply(modifier=md.name)

col = [float(v) / 255 for v in rgb.split()]
lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in col]
mat = bpy.data.materials.new('silicona'); mat.use_nodes = True
b = mat.node_tree.nodes['Principled BSDF']
b.inputs['Base Color'].default_value = (*lin, 1); b.inputs['Roughness'].default_value = 0.62
funda.data.materials.append(mat)

# logo: plano con la máscara de la foto oficial, apenas por fuera del dorso
lw = R_LOGO_W * (W + 2 * PARED)
img = bpy.data.images.load(logo_png); lh = lw * img.size[1] / img.size[0]
bpy.ops.mesh.primitive_plane_add(size=1)
lg = bpy.context.active_object; lg.name = 'logo'
lg.scale = (lw * MM, lh * MM, 1)
zl = (zc + (H + 2 * PARED) / 2) - LOGO_Y * (H + 2 * PARED)
loc = [0.0, 0.0, 0.0]; loc[lat] = xc; loc[ax] = dorso_case + s_back * 0.02; loc[2] = zl
# el plano mira hacia s_back en el eje ax; vista desde atrás no debe quedar espejado
rot = [math.radians(90), 0, 0] if ax == 1 else [math.radians(90), 0, math.radians(90)]
if (ax == 1 and s_back > 0) or (ax == 0 and s_back < 0):
    rot[2] += math.radians(180)
lg.rotation_euler = rot; lg.location = mathutils.Vector(loc) * MM
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
ml = bpy.data.materials.new('logo'); ml.use_nodes = True
nt = ml.node_tree; bl = nt.nodes['Principled BSDF']
tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img
bl.inputs['Base Color'].default_value = tuple(c * 0.72 for c in lin) + (1,)
bl.inputs['Roughness'].default_value = 0.42
nt.links.new(tex.outputs['Alpha'], bl.inputs['Alpha'])
ml.blend_method = 'HASHED' if hasattr(ml, 'blend_method') else None
lg.data.materials.append(ml)

# se exporta SÓLO la funda y el logo; el teléfono se carga aparte desde el USDZ oficial (texturas intactas)
for o in list(sc.objects):
    if o.name not in ('funda', 'logo'):
        bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.wm.usd_export(filepath=salida, export_materials=True, selected_objects_only=False)
print('OK', salida)
