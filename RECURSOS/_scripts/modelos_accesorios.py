"""
Modelos 3D de accesorios que Apple no publica en 3D, construidos con Blender a partir de las
proporciones medidas en las fotos oficiales de la Apple Store. Se exportan a USD (.usdc) para
animarlos con anim_media_vuelta.py igual que los iPhone.

    blenv/bin/python modelos_accesorios.py -- cargador_20w salida.usdc
    blenv/bin/python modelos_accesorios.py -- cargador_magsafe salida.usdc

Medidas (mm):
  Cargador 20W USB-C (MWVV3AM/A): frente 42,5 x 42,3; profundidad 27,4 (0,645 del ancho, foto MWVV3_AV2);
    patas tipo A de 15,9 de largo (0,374 del ancho, foto MWVV3_AV1), 6,35 x 1,5, separadas 12,7;
    puerto USB-C de 8,4 x 2,6 en la cara opuesta.
  Cargador MagSafe (MGD74LL/A): disco de 55,9 de diámetro y 5,6 de espesor, frente blanco con aro de
    aluminio, dorso de aluminio; cable blanco de 3,5 de diámetro y conector USB-C (fotos MGD74, _AV2, _AV3).
"""
import sys, math
import bpy, bmesh
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
modelo, salida = args[0], args[1]
MM = 0.001

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.scale_length = 1.0


def material(nombre, color, rough=0.4, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(nombre); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if 'Coat Weight' in b.inputs: b.inputs['Coat Weight'].default_value = coat
    return m


def asignar(o, m):
    o.data.materials.clear(); o.data.materials.append(m)


def rect_redondeado(nombre, w, d, h, r, z0=0.0, bisel=0.0, segs=16):
    """Prisma de sección rectangular redondeada (w x d, radio r) extruido en Z desde z0 con altura h."""
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object; o.name = nombre
    o.scale = (w * MM, d * MM, h * MM); o.location = (0, 0, (z0 + h / 2) * MM)
    bpy.ops.object.transform_apply(scale=True)
    # esquinas verticales redondeadas: bevel sólo en las aristas paralelas a Z
    bm = bmesh.new(); bm.from_mesh(o.data)
    verticales = [e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).normalized().z) > 0.99]
    bmesh.ops.bevel(bm, geom=verticales, offset=r * MM, segments=segs, affect='EDGES', profile=0.5)
    bm.to_mesh(o.data); bm.free()
    if bisel > 0:  # redondeo suave de las aristas superior e inferior
        mod = o.modifiers.new('bisel', 'BEVEL'); mod.width = bisel * MM; mod.segments = 6
        mod.limit_method = 'ANGLE'; mod.angle_limit = math.radians(50)
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_smooth()
    return o


def cubo(nombre, sx, sy, sz, loc, bisel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object; o.name = nombre
    o.scale = (sx * MM, sy * MM, sz * MM); o.location = tuple(v * MM for v in loc)
    bpy.ops.object.transform_apply(scale=True)
    if bisel > 0:
        mod = o.modifiers.new('b', 'BEVEL'); mod.width = bisel * MM; mod.segments = 4
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_smooth()
    return o


def cargador_20w():
    blanco = material('plastico_blanco', (0.90, 0.90, 0.885), rough=0.32, coat=0.25)
    metal = material('metal_patas', (0.82, 0.82, 0.83), rough=0.28, metal=1.0)
    negro = material('puerto_interior', (0.015, 0.015, 0.018), rough=0.6)
    W, D, H = 42.5, 27.4, 42.3
    cuerpo = rect_redondeado('cuerpo', W, D, H, r=7.2, bisel=1.6)
    asignar(cuerpo, blanco)
    # patas tipo A (cara superior); su lado ancho mira a los costados (como en la foto frontal)
    for x in (-6.35, 6.35):
        p = cubo(f'pata_{x:+.0f}', 1.5, 6.35, 15.9, (x, 0, H + 15.9 / 2 - 0.5), bisel=0.4)
        asignar(p, metal)
    # puerto USB-C en la cara inferior: carcasa metálica + interior oscuro + lengüeta
    shell = rect_redondeado('puerto_carcasa', 8.4, 2.6, 0.6, r=1.25, z0=-0.45, segs=10)
    asignar(shell, metal)
    hueco = rect_redondeado('puerto_hueco', 7.9, 2.1, 0.6, r=1.0, z0=-0.55, segs=10)
    asignar(hueco, negro)
    leng = cubo('puerto_lengueta', 6.6, 0.7, 0.3, (0, 0, -0.6))
    asignar(leng, material('lengueta', (0.12, 0.12, 0.13), rough=0.5))


def cargador_magsafe():
    blanco = material('frente_blanco', (0.93, 0.93, 0.925), rough=0.45, coat=0.15)
    alu = material('aluminio', (0.86, 0.86, 0.87), rough=0.42, metal=1.0)
    alu_mate = material('aluminio_dorso', (0.80, 0.80, 0.81), rough=0.78, metal=0.9)
    cable_m = material('cable', (0.94, 0.94, 0.935), rough=0.65)
    negro = material('puerto_interior', (0.02, 0.02, 0.022), rough=0.6)
    R, T = 55.9 / 2, 5.6
    zc = 0.0  # centro del disco en el origen; el cable baja por -Z; el frente mira a -Y
    # cuerpo del disco (cilindro sobre el eje Y)
    bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=R * MM, depth=T * MM, location=(0, 0, zc * MM),
                                        rotation=(math.radians(90), 0, 0))
    aro = bpy.context.active_object; aro.name = 'aro'
    mod = aro.modifiers.new('b', 'BEVEL'); mod.width = 1.6 * MM; mod.segments = 8
    bpy.ops.object.modifier_apply(modifier=mod.name); bpy.ops.object.shade_smooth()
    asignar(aro, alu)
    # frente blanco (disco apenas sobresaliente en -Y)
    bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=(R - 2.4) * MM, depth=0.8 * MM,
                                        location=(0, -(T / 2 - 0.25) * MM, zc * MM), rotation=(math.radians(90), 0, 0))
    fr = bpy.context.active_object; fr.name = 'frente'
    mod = fr.modifiers.new('b', 'BEVEL'); mod.width = 0.35 * MM; mod.segments = 4
    bpy.ops.object.modifier_apply(modifier=mod.name); bpy.ops.object.shade_smooth(); asignar(fr, blanco)
    # dorso de aluminio mate
    bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=(R - 3.0) * MM, depth=0.4 * MM,
                                        location=(0, (T / 2 - 0.1) * MM, zc * MM), rotation=(math.radians(90), 0, 0))
    do = bpy.context.active_object; do.name = 'dorso'; bpy.ops.object.shade_smooth(); asignar(do, alu_mate)
    # alivio de tensión + cable hacia abajo + conector USB-C
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=2.4 * MM, depth=9 * MM, location=(0, 0, (zc - R - 3.5) * MM))
    al = bpy.context.active_object; al.name = 'alivio'; bpy.ops.object.shade_smooth(); asignar(al, cable_m)
    largo = 95.0
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=1.75 * MM, depth=largo * MM,
                                        location=(0, 0, (zc - R - 7 - largo / 2) * MM))
    ca = bpy.context.active_object; ca.name = 'cable'; bpy.ops.object.shade_smooth(); asignar(ca, cable_m)
    zcon = zc - R - 7 - largo
    carc = cubo('conector_carcasa', 11.5, 6.2, 16.0, (0, 0, zcon - 8.0), bisel=2.2); asignar(carc, cable_m)
    plug = rect_redondeado('conector_metal', 8.3, 2.5, 6.6, r=1.2, z0=zcon - 16.0 - 6.4, segs=10); asignar(plug, alu)
    boca = rect_redondeado('conector_boca', 6.9, 1.2, 0.4, r=0.6, z0=zcon - 16.0 - 6.55, segs=8); asignar(boca, negro)


{'cargador_20w': cargador_20w, 'cargador_magsafe': cargador_magsafe}[modelo]()
bpy.ops.wm.usd_export(filepath=salida, export_materials=True, selected_objects_only=False)
print('OK', salida, len([o for o in sc.objects if o.type == 'MESH']), 'mallas')
