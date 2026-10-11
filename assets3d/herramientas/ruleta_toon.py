"""La ruleta en vivo en el estilo de los dibujos (decisión del dueño, 11-oct): la ruleta 2D de static/casino-icons
llevada a una rueda que funciona, con sus 37 casillas, sus números y la bola.

En Blender 5.2, con assets3d/juegos/juegos.blend abierto (vive también como bloque de texto `ruleta_toon.py`):

    exec(bpy.data.texts["ruleta_toon.py"].as_string())
    build_roulette(r"<ruta>/ruleta-numeros.png")        # arma la escena T_ruleta_vivo
    export_roulette(r"<ruta>/ruleta-exportada.glb")      # la exporta para la web

O sin abrir Blender, con Blender como módulo de Python (`pip install bpy==5.2.2`, Python 3.13), desde la raíz:

    python -c "import bpy, runpy; bpy.ops.wm.read_factory_settings(use_empty=True); \
      bpy.context.scene.name = 'T_ruleta_vivo'; ns = runpy.run_path('assets3d/herramientas/ruleta_toon.py'); \
      ns['build_roulette']('assets3d/texturas/ruleta-numeros.png'); \
      ns['export_roulette']('assets3d/juegos/ruleta-exportada.glb')"

Después: node assets3d/herramientas/optimizar-glb.mjs assets3d/juegos/ruleta-exportada.glb static/3d/ruleta.glb
La prueba: python -m unittest tests.test_arte (RouletteModel comprueba casillas, números y bola contra la animación).

Cómo está hecha (equipo/contratos/arte3d.md §9, §12 y §13):
- Las medidas salen de docs/arte/ruleta-animacion.mjs: la bola (radio BALL_RADIUS) apoya su centro en la pista a
  0.379 m y en el fondo de su casilla a 0.244 m. Cada superficie está a un radio de bola debajo de ese perfil.
- La casilla en la posición k del orden de la rueda está centrada en -2π(k + 0.5)/37 en el marco del rotor.
- Colores del dibujo: aro de papel, pista de tinta con rombos lima, casillas bermellón y tinta con el 0 en lima,
  trastes de papel, centro de tinta y la torreta lima de tres brazos. Rojo y negro son los de las apuestas
  (backend/games.py); el verde del 0 es el lima de la marca.
- Sin contorno en la malla: la web dibuja el trazo de tinta con un casco invertido (docs/arte/estilo-toon.mjs).
  Las piezas con `no_outline` (las de tinta y las delgadas y planas) no lo llevan.
- Materiales `roulette_<color>`: Principled de un color plano para que cualquier visor de glTF la vea bien; la web
  los cambia por el sombreado de dos tonos con los colores exactos de la paleta.
- Presupuesto: menos de 8 mil triángulos (§6).
"""
import math

import bmesh
import bpy
import mathutils

TAU = 2 * math.pi
WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
               22, 18, 29, 7, 28, 12, 35, 3, 26]
REDS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
N = 37
BALL_RADIUS = 0.016                     # el de docs/arte/ruleta-animacion.mjs
POCKET_FLOOR = 0.0565 - BALL_RADIUS     # el centro de la bola en su casilla, menos su radio
NUMBER_RING = (0.264, 0.303)            # los radios de assets3d/herramientas/ruleta_numeros.py
RING_Z = 0.047                          # la cara de arriba del anillo: justo bajo la bola cuando pasa (0.0635 - radio)
# La tira de números (ruleta_numeros.layout()): 1024 × 92 px, dos filas de 44 px con 4 de papel entre ellas, 19 celdas
STRIP = {"width": 1024, "height": 92, "row": 44, "gap": 4, "cells": 19}
SEGMENTS = 96                           # vueltas de la parte fija; el rotor usa 3 por casilla (111)
COLORS = {"cream": "#EFE6D2", "ink": "#1A1612", "lime": "#C6F432", "verm": "#FF4B2B"}

SCENE, COLLECTION = "T_ruleta_vivo", "T-ruleta-vivo"


def _linear(hex_color):
    h = hex_color.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def material(color, image=None):
    """roulette_<color>: a flat Principled colour (or the number strip) that the web swaps for its toon shading."""
    name = f"roulette_{color}"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Metallic"].default_value = 0.0
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Linear"
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        mat.diffuse_color = (1, 1, 1, 1)
    else:
        bsdf.inputs["Base Color"].default_value = _linear(COLORS[color])
        mat.diffuse_color = _linear(COLORS[color])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mat.use_backface_culling = True
    return mat


# ─── geometría ───────────────────────────────────────────────────────────────────────────────────────────────────────
def lathe(bm, profile, segs, uv=None, face_material=None, a0=0.0):
    """Revolve (r, z) points around Z. Walk the profile with the visible side on your left (its normal is the walking
    direction turned a quarter towards +Z). uv=(layer, v_of_point) maps u to the angle; face_material(s) picks a slot."""
    rings = []
    for s in range(segs + 1):
        a = a0 + TAU * s / segs
        rings.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in profile])
    for s in range(segs):
        a, b = rings[s], rings[s + 1]
        for i in range(len(profile) - 1):
            f = bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
            f.smooth = True
            if face_material is not None:
                f.material_index = face_material(s)
            if uv is not None:
                layer, v_of = uv
                for loop, (ss, ii) in zip(f.loops, ((s, i), (s, i + 1), (s + 1, i + 1), (s + 1, i))):
                    loop[layer].uv = (ss / segs, v_of[ii])
    return rings


def weld_seam(bm):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)


def add_sphere(bm, r, loc, segs=16, scale=(1, 1, 1)):
    m = mathutils.Matrix.Translation(loc) @ mathutils.Matrix.Diagonal((*scale, 1))
    res = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=max(6, segs // 2), radius=r, matrix=m)
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.smooth = True


def add_cylinder(bm, r, length, loc, rot, segs=12):
    m = mathutils.Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=length, matrix=m)
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.smooth = True


def make_object(col, name, build, mats, parent=None, no_outline=False):
    mesh_name = f"ME-vivo_{name[4:]}"            # la rueda de madera de la primera prueba usa ME-ruleta_*
    me = bpy.data.meshes.get(mesh_name)
    if me is not None:
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(mesh_name)
    bm = bmesh.new()
    build(bm)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.get(name)
    if o is not None:
        bpy.data.objects.remove(o, do_unlink=True)
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    o.parent = parent
    if no_outline:
        o["no_outline"] = True
    return o


def _empty(col, name, parent=None):
    o = bpy.data.objects.get(name)
    if o is not None:
        bpy.data.objects.remove(o, do_unlink=True)
    o = bpy.data.objects.new(name, None)
    o.empty_display_type = "PLAIN_AXES"
    o.empty_display_size = 0.1
    col.objects.link(o)
    o.parent = parent
    return o


def _free_names():
    """The wood-and-brass wheel of the first test (scene J_roulette) used these names; it keeps them with `_madera`."""
    old = bpy.data.collections.get("J-ruleta")
    if old is None:
        return
    for o in old.objects:
        if (o.name.startswith("GEO-ruleta") or o.name.startswith("RIG-ruleta")) and not o.name.endswith("_madera"):
            o.name = o.name + "_madera"


def build_roulette(numbers_png):
    _free_names()
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    col = bpy.data.collections.get(COLLECTION) or bpy.data.collections.new(COLLECTION)
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    cream, ink, lime, verm = (material(c) for c in ("cream", "ink", "lime", "verm"))
    img = bpy.data.images.get("ruleta-numeros.png")
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.load(numbers_png)
    img.colorspace_settings.name = "sRGB"
    img.pack()                                   # dentro del .blend: sin rutas de la computadora de nadie (§2)
    img.filepath = "//ruleta-numeros.png"        # y la ruta que recuerda, relativa
    numbers = material("numbers", image=img)

    root = _empty(col, "RIG-ruleta")
    rotor = _empty(col, "RIG-ruleta_rotor", parent=root)

    # ── la parte fija: aro de papel, pista de tinta y rombos lima ──
    def rim(bm):
        lathe(bm, [(0.395, 0.086), (0.395, 0.118), (0.397, 0.125), (0.402, 0.129), (0.409, 0.130), (0.452, 0.130),
                   (0.462, 0.128), (0.468, 0.122), (0.470, 0.112), (0.470, 0.020), (0.466, 0.005), (0.455, 0.0)],
              SEGMENTS)
        weld_seam(bm)
    make_object(col, "GEO-ruleta_aro", rim, [cream], parent=root)

    def track(bm):
        # el perfil de la animación menos un radio de bola: la bola corre arriba y baja hacia las casillas
        lathe(bm, [(0.305, 0.047), (0.310, 0.051), (0.331, 0.063), (0.353, 0.073), (0.362, 0.0745), (0.372, 0.0845),
                   (0.379, 0.0875), (0.397, 0.0875)], SEGMENTS)
        weld_seam(bm)
    make_object(col, "GEO-ruleta_pista", track, [ink], parent=root, no_outline=True)

    def diamonds(bm):
        for i in range(8):
            a = TAU * (i + 0.5) / 8
            c = mathutils.Vector((0.342 * math.cos(a), 0.342 * math.sin(a), 0.0685))
            radial = mathutils.Vector((math.cos(a), math.sin(a), 0.0))
            tangent = mathutils.Vector((-math.sin(a), math.cos(a), 0.0))
            up = mathutils.Vector((-0.42 * math.cos(a), -0.42 * math.sin(a), 1.0)).normalized()   # sobre la pendiente
            tips = [c + radial * 0.016, c + tangent * 0.0075, c - radial * 0.016, c - tangent * 0.0075]
            top, bottom = bm.verts.new(c + up * 0.008), bm.verts.new(c - up * 0.002)
            ring = [bm.verts.new(p) for p in tips]
            for j in range(4):
                bm.faces.new((ring[j], ring[(j + 1) % 4], top))
                bm.faces.new((ring[(j + 1) % 4], ring[j], bottom))
    make_object(col, "GEO-ruleta_rombos", diamonds, [lime], parent=root, no_outline=True)

    # ── el rotor: centro de tinta, labio de papel, casillas, trastes, números y torreta lima ──
    def cone(bm):
        lathe(bm, [(0.0, 0.098), (0.03, 0.097), (0.09, 0.086), (0.15, 0.069), (0.186, 0.058)], 64)
        weld_seam(bm)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)     # el polo del centro
    make_object(col, "GEO-ruleta_cono", cone, [ink], parent=rotor, no_outline=True)

    def inner_lip(bm):
        lathe(bm, [(0.182, 0.057), (0.185, 0.064), (0.196, 0.064), (0.199, POCKET_FLOOR)], 74)
        weld_seam(bm)
    make_object(col, "GEO-ruleta_labio", inner_lip, [cream], parent=rotor)

    def slot_material(s):
        # 3 tramos por casilla; el tramo s cae en la casilla j = s // 3, que es la posición k = 36 - j del orden
        n = WHEEL_ORDER[N - 1 - s // 3]
        return 0 if n == 0 else (1 if n in REDS else 2)

    def pockets(bm):
        lathe(bm, [(0.199, POCKET_FLOOR), (0.262, POCKET_FLOOR), (0.262, RING_Z)], 3 * N, face_material=slot_material)
        weld_seam(bm)
    make_object(col, "GEO-ruleta_casillas", pockets, [lime, verm, ink], parent=rotor, no_outline=True)

    def number_ring(bm):
        # 3 tramos por casilla; el tramo de la casilla j cae en la celda j % 19 de la fila j // 19 de la tira, con su
        # borde de adentro arriba (v = 1 en Blender es arriba de la imagen): se lee derecho desde afuera de la rueda
        layer = bm.loops.layers.uv.new("UVMap")
        lathe(bm, [(NUMBER_RING[0], RING_Z), (NUMBER_RING[1], RING_Z)], 3 * N)
        slot = TAU / N
        for s, face in enumerate(bm.faces):
            j = s // 3
            row, col = divmod(j, STRIP["cells"])
            y_in = row * (STRIP["row"] + STRIP["gap"])
            for loop in face.loops:
                x, y = loop.vert.co.x, loop.vert.co.y
                a = math.atan2(y, x) % TAU
                frac = (a - j * slot) / slot
                if frac < -0.5:                  # el borde de 2π de la última casilla se lee como 0
                    frac += N
                elif frac > N - 0.5:             # y el 0 de la primera, como 2π (atan2 da −0.0)
                    frac -= N
                frac = min(1.0, max(0.0, frac))
                inner = math.hypot(x, y) < sum(NUMBER_RING) / 2
                py = y_in if inner else y_in + STRIP["row"]
                loop[layer].uv = ((col + frac) / STRIP["cells"], 1.0 - py / STRIP["height"])
    make_object(col, "GEO-ruleta_numeros", number_ring, [numbers], parent=rotor, no_outline=True)

    def outer_lip(bm):
        # a ras del anillo: la bola pasa por encima al bajar de la pista (su centro va a 0.0635 m sobre 0.306 m)
        lathe(bm, [(0.300, 0.0465), (0.302, 0.0475), (0.306, 0.0475), (0.308, 0.046)], 74)
        weld_seam(bm)
    make_object(col, "GEO-ruleta_borde", outer_lip, [cream], parent=rotor)

    def frets(bm):
        top = 0.0505        # bajos: se ve el color de las casillas y la bola apenas los roza al entrar
        for j in range(N):
            a = TAU * j / N
            m = (mathutils.Matrix.Rotation(a, 4, "Z") @ mathutils.Matrix.Translation((0.2305, 0, (POCKET_FLOOR + top) / 2))
                 @ mathutils.Matrix.Diagonal((0.063, 0.0045, top - POCKET_FLOOR, 1)))
            res = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
            for f in {f for v in res["verts"] for f in v.link_faces}:
                f.smooth = False
    make_object(col, "GEO-ruleta_trastes", frets, [cream], parent=rotor)

    def turret(bm):
        z = 0.121
        add_cylinder(bm, 0.015, 0.03, (0, 0, 0.105), mathutils.Euler((0, 0, 0)), segs=12)
        add_sphere(bm, 0.038, (0, 0, z), segs=20)
        for i in range(3):
            a = math.radians(90 + 120 * i)
            add_cylinder(bm, 0.013, 0.08, (0.055 * math.cos(a), 0.055 * math.sin(a), z),
                         mathutils.Euler((0, math.radians(90), a), "XYZ"), segs=10)
            add_sphere(bm, 0.025, (0.105 * math.cos(a), 0.105 * math.sin(a), z), segs=14)
    make_object(col, "GEO-ruleta_torreta", turret, [lime], parent=rotor)

    # ── la bola: de papel, cuelga de la rueda y no del rotor (la web la mueve sola) ──
    def ball(bm):
        add_sphere(bm, BALL_RADIUS, (0, 0, 0), segs=16)
    b = make_object(col, "GEO-ruleta_bola", ball, [cream], parent=root)
    b.location = (0.0, -0.244, 0.0565)      # en el fondo de la casilla bajo el marcador

    for o in col.objects:
        if o.type == "MESH":
            o.data.update()
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in col.objects if o.type == "MESH")
    return {"objects": len(col.objects), "triangles": tris}


def export_roulette(path):
    """Only this scene goes out: the selection lives in the scene's own view layer, so the export runs inside it."""
    sc = bpy.data.scenes[SCENE]
    layer = sc.view_layers[0]
    col = bpy.data.collections[COLLECTION]
    layer.update()                               # recién armada, la capa aún puede listar objetos borrados
    for o in layer.objects:
        if o is not None:
            o.select_set(False, view_layer=layer)
    for o in col.objects:
        o.select_set(True, view_layer=layer)
    options = dict(filepath=path, export_format="GLB", use_selection=True, use_active_scene=True, export_yup=True,
                   export_apply=True, export_cameras=False, export_lights=False, export_image_format="WEBP",
                   export_draco_mesh_compression_enable=False, export_extras=True)
    if bpy.context.window is None:
        # Blender sin ventana (bpy como módulo, la prueba de E6): la escena del contexto ya es esta
        assert bpy.context.scene == sc, "sin ventana, arma la ruleta en la escena del contexto"
        bpy.ops.export_scene.gltf(**options)
    else:
        with bpy.context.temp_override(window=bpy.context.window, scene=sc, view_layer=layer):
            bpy.ops.export_scene.gltf(**options)
    return path
