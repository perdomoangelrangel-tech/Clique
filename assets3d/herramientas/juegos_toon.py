"""Los 14 juegos del casino en el estilo de los dibujos, en 3D. Cada función arma la escena T_<juego> de juegos.blend
siguiendo el dibujo 2D de static/casino-icons/<juego>.png (la referencia que eligió el dueño el 11-oct).

En Blender, con juegos.blend abierto:
    exec(bpy.data.texts["juegos_toon.py"].as_string()); render_game("roulette", out_dir)
Después: python assets3d/herramientas/iconos_juego.py <out_dir>/roulette_960.png roulette

Usa e6_toon.py (materiales, contorno, primitivas) y e6_util.py (encuadre de cámara), que también viven en el .blend.
"""
import bpy
import math
import mathutils

_ns = {}
exec(bpy.data.texts["e6_toon.py"].as_string(), _ns)
exec(bpy.data.texts["e6_util.py"].as_string(), _ns)
toon, setup_toon, sun, obj, outline = _ns["toon"], _ns["setup_toon"], _ns["sun"], _ns["obj"], _ns["outline"]
cylinder, sphere, box, wedge = _ns["cylinder"], _ns["sphere"], _ns["box"], _ns["wedge"]
camera, bounds = _ns["camera"], _ns["bounds"]
LINE = 0.021          # grueso del contorno como fracción del ancho del cuadro
TAU = 2 * math.pi


def _scene(game):
    sc = bpy.data.scenes.get(f"T_{game}") or bpy.data.scenes.new(f"T_{game}")
    bpy.context.window.scene = sc
    setup_toon(sc)
    col = bpy.data.collections.get(f"T-{game}") or bpy.data.collections.new(f"T-{game}")
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return sc, col


# ─── ruleta: aro de papel, 8 gajos bermellón y papel, centro de tinta, cubo lima con tres brazos ───────────────────
def build_roulette(col):
    cream, ink, lime, soft = toon("cream"), toon("ink"), toon("lime"), toon("verm_soft")
    h = 0.16
    obj(col, "GEO-t_ruleta_aro", cylinder("ME-t_aro", 1.0, h, 96), cream, loc=(0, 0, h / 2), bevel=0.05, segments=4)
    # los gajos van sobre una base de tinta y separados: la tinta que asoma entre ellos es el trazo del dibujo
    # la base y el centro ya son de tinta: sin casco, que en un disco delgado asoma por detrás como rayas sobre el aro
    obj(col, "GEO-t_ruleta_base", cylinder("ME-t_base", 0.87, 0.03, 96), ink, loc=(0, 0, h + 0.012))["no_outline"] = True
    # gajos sin casco: la tinta de la base asoma entre ellos con el mismo grueso, como el trazo del dibujo
    for i in range(8):
        a0 = math.radians(22.5 + 45 * i)
        g = obj(col, f"GEO-t_ruleta_gajo_{i}", wedge(f"ME-t_gajo_{i}", 0.45, 0.83, a0, a0 + math.radians(45), 0.05, 16,
                                                    inset=0.022), soft if i % 2 == 0 else cream, loc=(0, 0, h + 0.02))
        g["no_outline"] = True
    obj(col, "GEO-t_ruleta_centro", cylinder("ME-t_centro", 0.42, 0.06, 64), ink, loc=(0, 0, h + 0.04),
        bevel=0.01)["no_outline"] = True
    # el cubo del dibujo: bolita lima chica con tres brazos delgados que terminan en bolitas, todo dentro del centro
    top = h + 0.13
    obj(col, "GEO-t_ruleta_cubo", sphere("ME-t_cubo", 0.115, 32), lime, loc=(0, 0, top))
    for i in range(3):
        a = math.radians(90 + 120 * i)
        obj(col, f"GEO-t_ruleta_brazo_{i}", cylinder(f"ME-t_brazo_{i}", 0.045, 0.24, 16), lime,
            loc=(0.15 * math.cos(a), 0.15 * math.sin(a), top), rot=(0, math.radians(90), a))
        obj(col, f"GEO-t_ruleta_bolita_{i}", sphere(f"ME-t_bolita_{i}", 0.08, 24), lime,
            loc=(0.29 * math.cos(a), 0.29 * math.sin(a), top))
    return dict(elev=68, azim=-10, lens=60, fill=0.86)


# ─── figuras planas extruidas (corazón, pica, diamante, flecha, corona…) ─────────────────────────────────────────────
def _outline_points(kind, n=96):
    """Closed 2D outline (x, y), about 1 unit tall, centred."""
    pts = []
    if kind == "heart":
        for i in range(n):
            t = TAU * i / n
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((x / 32, (y + 2.5) / 32))
    elif kind == "spade":
        for i in range(n):
            t = TAU * i / n
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((x / 32, -(y + 2.5) / 32 + 0.12))
    elif kind == "diamond":
        pts = [(0, 0.55), (0.38, 0), (0, -0.55), (-0.38, 0)]
    return pts


def flat(name, kind, depth, scale=1.0, pts=None):
    """A flat piece extruded from an outline: suits on cards, arrows, crowns."""
    import bmesh
    pts = pts or _outline_points(kind)

    def build(bm):
        vs = [bm.verts.new((x * scale, y * scale, 0)) for x, y in pts]
        f = bm.faces.new(vs)
        ext = bmesh.ops.extrude_face_region(bm, geom=[f])
        bmesh.ops.translate(bm, vec=(0, 0, depth), verts=[e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _ns["mesh_from"](name, build)


def card(col, name, mat_face, suit, suit_mat, loc, rot, size=1.0, suit_scale=0.42):
    """A playing card like the drawing: a thick rounded slab of paper with one big suit in the middle."""
    w, h, d = 0.63 * size, 0.88 * size, 0.035 * size
    c = obj(col, name, box(f"ME-{name}", w, h, d), mat_face, loc=loc, rot=rot, bevel=0.06 * size, segments=6)
    c.modifiers["bevel"].limit_method = "NONE"
    s = obj(col, f"{name}_palo", flat(f"ME-{name}_palo", suit, 0.03 * size, scale=suit_scale * size), suit_mat,
            loc=(0, 0, d / 2), bevel=0.008 * size, segments=2)
    s.parent = c
    s["no_outline"] = True                 # en el dibujo el palo es una mancha de color, sin trazo
    if suit == "spade":                    # el pie de la pica
        stem = [(-0.16, -0.42), (0.16, -0.42), (0.035, -0.12), (-0.035, -0.12)]
        f = obj(col, f"{name}_pie", flat(f"ME-{name}_pie", None, 0.03 * size, scale=suit_scale * size, pts=stem),
                suit_mat, loc=(0, 0, d / 2))
        f.parent = c
        f["no_outline"] = True
    return c


# ─── blackjack: dos cartas en abanico, pica de tinta y corazón bermellón ──────────────────────────────────────────
def build_blackjack(col):
    cream, ink, verm = toon("cream"), toon("ink"), toon("verm")
    card(col, "GEO-t_bj_pica", cream, "spade", ink, loc=(-0.30, 0.10, 0.02), rot=(math.radians(62), 0, math.radians(14)))
    card(col, "GEO-t_bj_corazon", cream, "heart", verm, loc=(0.28, -0.08, 0.0), rot=(math.radians(66), 0, math.radians(-10)))
    return dict(elev=12, azim=-6, lens=70, fill=0.84)


# ─── dados: uno de papel y uno lima, con puntos de tinta hundidos ──────────────────────────────────────────────────
PIPS = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)], 4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
        5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)], 6: [(-1, -1), (-1, 0), (-1, 1), (1, -1), (1, 0), (1, 1)]}
FACES = {"+Z": ((0, 0, 1), (1, 0, 0), (0, 1, 0)), "-Z": ((0, 0, -1), (1, 0, 0), (0, -1, 0)),
         "+X": ((1, 0, 0), (0, 1, 0), (0, 0, 1)), "-X": ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
         "+Y": ((0, 1, 0), (-1, 0, 0), (0, 0, 1)), "-Y": ((0, -1, 0), (1, 0, 0), (0, 0, 1))}


def die(col, name, mat, faces, loc, rot, a=1.0):
    import mathutils
    d = obj(col, name, box(f"ME-{name}", a, a, a), mat, loc=loc, rot=rot, bevel=0.16 * a, segments=5)
    d.modifiers["bevel"].limit_method = "NONE"
    ink = toon("ink")
    p = 0.26 * a
    for face, n in faces.items():
        nn, uu, vv = (mathutils.Vector(x) for x in FACES[face])
        for k, (u, v) in enumerate(PIPS[n]):
            c = nn * (a / 2 - 0.004 * a) + uu * (u * p) + vv * (v * p)
            pip = obj(col, f"{name}_p{face}{k}", cylinder(f"ME-{name}_p{face}{k}", 0.085 * a, 0.02 * a, 32), ink,
                      loc=c, rot=nn.to_track_quat("Z", "Y").to_euler())
            pip.parent = d
            pip["no_outline"] = True
    return d


def build_dice(col):
    cream, lime = toon("cream"), toon("lime")
    bpy.context.view_layer.update()
    die(col, "GEO-t_dado_papel", cream, {"+Z": 3, "-Y": 2, "+X": 1, "-X": 6, "+Y": 5, "-Z": 4},
        loc=(-0.62, 0.15, 0.5), rot=(0, 0, math.radians(24)))
    die(col, "GEO-t_dado_lima", lime, {"+Z": 4, "-Y": 5, "+X": 6, "-X": 1, "+Y": 2, "-Z": 3},
        loc=(0.62, -0.12, 0.5), rot=(0, 0, math.radians(-16)))
    return dict(elev=30, azim=-8, lens=60, fill=0.84)


def ball(col, name, r, mat, loc, scale=(1, 1, 1), rot=(0, 0, 0)):
    """A sphere stretched into an ellipsoid: bodies, heads, fingers, paws. The stretch goes into the mesh, not the object
    scale: the outline's thickness is measured in the object's own space, and a squashed object squashes its line."""
    me = sphere(f"ME-{name}", r, 32)
    me.transform(mathutils.Matrix.Diagonal((*scale, 1.0)))
    return obj(col, name, me, mat, loc=loc, rot=rot)


def rig(col, name, loc=(0, 0, 0), rot=(0, 0, 0)):
    e = bpy.data.objects.get(name)
    if e is None:
        e = bpy.data.objects.new(name, None)
        col.objects.link(e)
    e.location, e.rotation_euler = loc, rot
    return e


def parent_all(col, parent, prefix):
    for o in col.objects:
        if o is not parent and o.name.startswith(prefix) and o.parent is None:
            o.parent = parent


# ─── chicken: gallina de papel de perfil, cresta bermellón, pico y patas lima ───────────────────────────────────────
def build_chicken(col):
    cream, ink, lime, verm = toon("cream"), toon("ink"), toon("lime"), toon("verm")
    ball(col, "GEO-t_gallina_cuerpo", 1, cream, (0, 0, 0.9), (0.72, 0.5, 0.56))
    # la cola del dibujo: tres plumas en abanico, cada una con su trazo
    for k, (x, z, ang, sz) in enumerate([(-0.70, 1.08, -62, 0.25), (-0.66, 1.26, -38, 0.29), (-0.55, 1.40, -14, 0.26)]):
        ball(col, f"GEO-t_gallina_cola_{k}", 1, cream, (x, 0.02 * k, z), (0.12, 0.22, sz), rot=(0, math.radians(ang), 0))
    ball(col, "GEO-t_gallina_ala", 1, cream, (-0.05, -0.47, 0.9), (0.42, 0.1, 0.27), rot=(0, math.radians(-12), 0))
    ball(col, "GEO-t_gallina_cabeza", 0.3, cream, (0.55, 0, 1.48))
    for k, (x, z, r) in enumerate([(0.42, 1.78, 0.1), (0.55, 1.83, 0.115), (0.68, 1.77, 0.1)]):
        ball(col, f"GEO-t_gallina_cresta_{k}", r, verm, (x, 0, z))
    ball(col, "GEO-t_gallina_barba", 0.08, verm, (0.74, -0.02, 1.28), (0.8, 0.7, 1.3))
    obj(col, "GEO-t_gallina_pico", cylinder("ME-t_pico", 0.09, 0.2, 24, r2=0.0), lime, loc=(0.92, 0, 1.45),
        rot=(0, math.radians(90), 0))
    e = ball(col, "GEO-t_gallina_ojo", 0.055, ink, (0.68, -0.25, 1.54))
    e["no_outline"] = True
    # patas de paso, como el dibujo: la de atrás inclinada hacia atrás y la de adelante hacia adelante
    for k, (fx, lean) in enumerate(((-0.22, 12), (0.3, -12))):          # (x del pie, inclinación en grados)
        tilt = math.radians(lean)
        obj(col, f"GEO-t_gallina_pata_{k}", cylinder(f"ME-t_pata_{k}", 0.06, 0.46, 16), lime,
            loc=(fx + 0.23 * math.sin(tilt), -0.05, 0.04 + 0.23 * math.cos(tilt)), rot=(0, tilt, 0))
        for j, a in enumerate((-30, 0, 30)):
            t = math.radians(a)
            ball(col, f"GEO-t_gallina_dedo_{k}{j}", 0.05, lime, (fx + 0.11 * math.cos(t), -0.05 + 0.11 * math.sin(t), 0.04),
                 (2.2, 0.9, 0.7), rot=(0, 0, t))
    return dict(elev=12, azim=0, lens=70, fill=0.84)


# ─── limbo: cohete de papel con nariz y aletas bermellón y llama lima, subiendo en diagonal ─────────────────────────
def build_limbo(col):
    cream, ink, lime, verm = toon("cream"), toon("ink"), toon("lime"), toon("verm")
    obj(col, "GEO-t_cohete_cuerpo", cylinder("ME-t_cuerpo", 0.28, 1.1, 48), cream, loc=(0, 0, 0.55), bevel=0.04)
    obj(col, "GEO-t_cohete_nariz", cylinder("ME-t_nariz", 0.28, 0.5, 48, r2=0.02), verm, loc=(0, 0, 1.35), bevel=0.02)
    obj(col, "GEO-t_cohete_ventana", cylinder("ME-t_ventana", 0.15, 0.08, 32), ink, loc=(0, -0.26, 0.78),
        rot=(math.radians(90), 0, 0), bevel=0.01)
    w = obj(col, "GEO-t_cohete_vidrio", cylinder("ME-t_vidrio", 0.095, 0.04, 32), cream, loc=(0, -0.31, 0.78),
            rot=(math.radians(90), 0, 0))
    w["no_outline"] = True
    for k in range(3):
        a = math.radians((0, 180, 90)[k])
        fin = [(0, 0), (0.32, -0.12), (0.32, -0.42), (0, -0.2)]
        f = obj(col, f"GEO-t_cohete_aleta_{k}", flat(f"ME-t_aleta_{k}", None, 0.07, pts=fin), verm,
                loc=(0.26 * math.cos(a), 0.26 * math.sin(a), 0.36), rot=(math.radians(90), 0, a), bevel=0.015)
    obj(col, "GEO-t_cohete_tobera", cylinder("ME-t_tobera", 0.2, 0.12, 32, r2=0.24), cream, loc=(0, 0, -0.05))
    obj(col, "GEO-t_cohete_llama", cylinder("ME-t_llama", 0.18, 0.5, 32, r2=0.0), lime, loc=(0, 0, -0.36),
        rot=(math.radians(180), 0, 0), bevel=0.02)
    r = rig(col, "RIG-t_cohete", rot=(0, math.radians(42), 0))
    parent_all(col, r, "GEO-t_cohete")
    return dict(elev=8, azim=0, lens=70, fill=0.84)


# ─── coinflip: moneda de papel con aro de tinta y corona lima ───────────────────────────────────────────────────────
def build_coinflip(col):
    cream, ink, lime = toon("cream"), toon("ink"), toon("lime")
    r = rig(col, "RIG-t_moneda", rot=(math.radians(76), 0, math.radians(-8)))
    obj(col, "GEO-t_moneda_disco", cylinder("ME-t_disco", 1.0, 0.18, 96), cream, loc=(0, 0, 0), bevel=0.05, segments=4)
    aro = obj(col, "GEO-t_moneda_aro", wedge("ME-t_aro_m", 0.78, 0.85, 0, TAU, 0.02, 96), ink, loc=(0, 0, 0.09))
    aro["no_outline"] = True
    crown = [(-0.5, -0.3), (0.5, -0.3), (0.55, 0.28), (0.27, 0.05), (0, 0.38), (-0.27, 0.05), (-0.55, 0.28)]
    obj(col, "GEO-t_moneda_corona", flat("ME-t_corona", None, 0.08, pts=crown), lime, loc=(0, -0.05, 0.09), bevel=0.02)
    for k, (x, y) in enumerate([(-0.55, 0.3), (0, 0.42), (0.55, 0.3)]):
        ball(col, f"GEO-t_moneda_punta_{k}", 0.08, lime, (x, y - 0.05, 0.13))
    parent_all(col, r, "GEO-t_moneda")
    return dict(elev=8, azim=0, lens=70, fill=0.84)


# ─── war: dos espadas cruzadas, guardas y empuñaduras bermellón y lima ──────────────────────────────────────────────
def sword(col, name, hilt, angle, x):
    cream = toon("cream")
    r = rig(col, f"RIG-{name}", loc=(x, 0, 0), rot=(math.radians(90), math.radians(angle), 0))
    blade = [(-0.09, 0), (0.09, 0), (0.09, 1.25), (0, 1.42), (-0.09, 1.25)]
    obj(col, f"GEO-{name}_hoja", flat(f"ME-{name}_hoja", None, 0.05, pts=blade), cream, loc=(0, 0, -0.025), bevel=0.012)
    obj(col, f"GEO-{name}_guarda", box(f"ME-{name}_guarda", 0.6, 0.13, 0.14), hilt, loc=(0, -0.03, 0), bevel=0.05)
    obj(col, f"GEO-{name}_puno", cylinder(f"ME-{name}_puno", 0.075, 0.36, 24), hilt, loc=(0, -0.25, 0),
        rot=(math.radians(90), 0, 0))
    ball(col, f"GEO-{name}_pomo", 0.12, hilt, (0, -0.46, 0))
    parent_all(col, r, f"GEO-{name}")


def build_war(col):
    sword(col, "t_espada_a", toon("verm"), 38, -0.48)
    sword(col, "t_espada_b", toon("lime"), -38, 0.48)
    bpy.data.objects["RIG-t_espada_b"].location.y = -0.08
    return dict(elev=6, azim=0, lens=70, fill=0.84)


# ─── mines: bomba de tinta con brillo lima, mecha de papel y chispa bermellón ───────────────────────────────────────
def build_mines(col):
    cream, ink, lime, verm = toon("cream"), toon("ink"), toon("lime"), toon("verm")
    ball(col, "GEO-t_bomba", 0.8, ink, (0, 0, 0.8))
    h = ball(col, "GEO-t_bomba_brillo", 0.2, lime, (-0.32, -0.66, 1.14), (1, 0.4, 1), rot=(math.radians(-20), 0, math.radians(-25)))
    h["no_outline"] = True
    obj(col, "GEO-t_bomba_tapa", cylinder("ME-t_tapa", 0.2, 0.22, 32), cream, loc=(0.42, 0, 1.5),
        rot=(0, math.radians(32), 0), bevel=0.03)
    # mecha: un tubo curvo de papel
    cu = bpy.data.curves.get("CU-t_mecha") or bpy.data.curves.new("CU-t_mecha", "CURVE")
    cu.dimensions = "3D"
    cu.splines.clear()
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(2)
    for bp, co in zip(sp.bezier_points, [(0.5, 0, 1.6), (0.7, 0, 1.95), (1.05, 0, 1.95)]):
        bp.co = co
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    cu.bevel_depth = 0.06
    cu.bevel_resolution = 4
    m = bpy.data.objects.get("GEO-t_bomba_mecha")
    if m is not None:
        bpy.data.objects.remove(m, do_unlink=True)
    m = bpy.data.objects.new("GEO-t_bomba_mecha", cu)
    col.objects.link(m)
    cu.materials.clear()
    cu.materials.append(cream)
    star = []
    for i in range(8):
        a = TAU * i / 8 + math.pi / 2
        rr = 0.32 if i % 2 == 0 else 0.1
        star.append((rr * math.cos(a), rr * math.sin(a)))
    obj(col, "GEO-t_bomba_chispa", flat("ME-t_chispa", None, 0.08, pts=star), verm, loc=(1.12, 0.04, 2.02),
        rot=(math.radians(90), 0, 0), bevel=0.015)
    return dict(elev=10, azim=0, lens=70, fill=0.84)


# ─── moles: topo de papel asomando de un hoyo de tinta, nariz bermellón ─────────────────────────────────────────────
def build_moles(col):
    cream, ink, verm = toon("cream"), toon("ink"), toon("verm")
    hole = obj(col, "GEO-t_topo_hoyo", cylinder("ME-t_hoyo", 1.25, 0.04, 96), ink, loc=(0, 0.1, 0.02))
    hole.scale = (1, 0.42, 1)
    ball(col, "GEO-t_topo_cabeza", 1, cream, (0, 0.1, 0.35), (0.68, 0.55, 0.62))
    for k, x in enumerate((-0.5, 0.5)):
        ball(col, f"GEO-t_topo_oreja_{k}", 0.2, cream, (x, 0.12, 0.88), (1, 0.6, 1))
    for k, x in enumerate((-0.24, 0.24)):
        e = ball(col, f"GEO-t_topo_ojo_{k}", 0.06, ink, (x, -0.43, 0.55))
        e["no_outline"] = True
    ball(col, "GEO-t_topo_nariz", 0.11, verm, (0, -0.5, 0.38), (1.3, 0.8, 0.9))
    for k, x in enumerate((-0.42, 0.42)):
        ball(col, f"GEO-t_topo_pata_{k}", 0.22, cream, (x, -0.42, 0.06), (1.1, 0.8, 0.6))
    return dict(elev=14, azim=0, lens=70, fill=0.84)


# ─── tower: torre de papel con almenas, puerta de tinta y bandera lima ─────────────────────────────────────────────
def build_tower(col):
    cream, ink, lime = toon("cream"), toon("ink"), toon("lime")
    obj(col, "GEO-t_torre_base", box("ME-t_base_t", 1.2, 0.9, 0.14), cream, loc=(0, 0, 0.07), bevel=0.03)
    obj(col, "GEO-t_torre_escalon", box("ME-t_esc", 1.0, 0.78, 0.12), cream, loc=(0, 0, 0.2), bevel=0.03)
    obj(col, "GEO-t_torre_cuerpo", box("ME-t_cuerpo_t", 0.78, 0.6, 1.05), cream, loc=(0, 0, 0.78), bevel=0.03)
    obj(col, "GEO-t_torre_corona", box("ME-t_corona_t", 1.0, 0.78, 0.22), cream, loc=(0, 0, 1.4), bevel=0.03)
    for k, x in enumerate((-0.38, 0, 0.38)):
        obj(col, f"GEO-t_torre_almena_{k}", box(f"ME-t_almena_{k}", 0.22, 0.78, 0.22), cream, loc=(x, 0, 1.62), bevel=0.03)
    obj(col, "GEO-t_torre_puerta", box("ME-t_puerta", 0.3, 0.06, 0.34), ink, loc=(0, -0.29, 0.43), bevel=0.01)
    obj(col, "GEO-t_torre_arco", cylinder("ME-t_arco", 0.15, 0.06, 32), ink, loc=(0, -0.29, 0.6),
        rot=(math.radians(90), 0, 0))
    obj(col, "GEO-t_torre_asta", cylinder("ME-t_asta", 0.03, 0.62, 16), ink, loc=(-0.1, 0, 2.0))
    flag = [(0, 0), (0.42, -0.04), (0.36, -0.14), (0.44, -0.26), (0, -0.24)]
    obj(col, "GEO-t_torre_bandera", flat("ME-t_bandera", None, 0.04, pts=flag), lime, loc=(-0.07, -0.02, 2.3),
        rot=(math.radians(90), 0, 0), bevel=0.01)
    return dict(elev=10, azim=-14, lens=70, fill=0.84)


# ─── poker: carta con diamante bermellón y dos fichas al frente ─────────────────────────────────────────────────────
def chip(col, name, body, insert, loc, rot):
    r = rig(col, f"RIG-{name}", loc=loc, rot=rot)
    obj(col, f"GEO-{name}", cylinder(f"ME-{name}", 0.5, 0.14, 64), body, bevel=0.03, segments=3)
    obj(col, f"GEO-{name}_aro", wedge(f"ME-{name}_aro", 0.3, 0.34, 0, TAU, 0.02, 64), toon("ink"), loc=(0, 0, 0.07))
    for k in range(8):
        a0 = TAU * k / 8
        p = obj(col, f"GEO-{name}_inserto_{k}", wedge(f"ME-{name}_ins_{k}", 0.38, 0.5, a0, a0 + 0.3, 0.02, 6), insert,
                loc=(0, 0, 0.07))
        p["no_outline"] = True
    parent_all(col, r, f"GEO-{name}")


def build_poker(col):
    cream, verm, lime = toon("cream"), toon("verm"), toon("lime")
    card(col, "GEO-t_poker_carta", cream, "diamond", verm, loc=(0, 0.35, 0.95), rot=(math.radians(82), 0, 0), size=1.05,
         suit_scale=0.36)
    for o in col.objects:
        if o.name.startswith("GEO-t_poker_carta_"):
            o.location.y += 0.14
    chip(col, "t_poker_ficha_a", lime, cream, loc=(-0.24, -0.25, 0.36), rot=(math.radians(74), 0, math.radians(6)))
    chip(col, "t_poker_ficha_b", cream, verm, loc=(0.36, -0.12, 0.33), rot=(math.radians(70), 0, math.radians(-12)))
    for o in col.objects:
        if o.name.startswith("RIG-t_poker_ficha"):
            o.scale = (0.72, 0.72, 0.72)
    return dict(elev=10, azim=0, lens=70, fill=0.84)


# ─── hilo: dos cartas, pica con flecha lima arriba y corazón con flecha bermellón abajo ─────────────────────────────
ARROW = [(-0.12, -0.3), (0.12, -0.3), (0.12, 0.02), (0.26, 0.02), (0, 0.32), (-0.26, 0.02), (-0.12, 0.02)]


def build_hilo(col):
    cream, ink, lime, verm = toon("cream"), toon("ink"), toon("lime"), toon("verm")
    for name, suit, mat, arrow_mat, flip, loc, rz in (
            ("GEO-t_hilo_pica", "spade", ink, lime, False, (-0.32, 0.1, 0.02), 12),
            ("GEO-t_hilo_corazon", "heart", verm, verm, True, (0.3, -0.08, 0.0), -9)):
        c = card(col, name, cream, suit, mat, loc=loc, rot=(math.radians(64), 0, math.radians(rz)), suit_scale=0.3)
        for o in col.objects:
            if o.parent is c:
                o.location.y += 0.18
        pts = [(x * 0.62, -y * 0.62) for x, y in ARROW] if flip else [(x * 0.62, y * 0.62) for x, y in ARROW]
        a = obj(col, f"{name}_flecha", flat(f"ME-{name}_flecha", None, 0.04, pts=pts), arrow_mat, loc=(0, -0.18, 0.03))
        a.parent = c
        a["no_outline"] = True
        back = obj(col, f"{name}_flecha_trazo", flat(f"ME-{name}_flecha_trazo", None, 0.04,
                                                     pts=[(x * 1.22, y * 1.16) for x, y in pts]), ink, loc=(0, -0.18, 0.012))
        back.parent = c
        back["no_outline"] = True
    return dict(elev=12, azim=-6, lens=70, fill=0.84)


# ─── wheel: rueda de la fortuna de pie, gajos lima, bermellón y papel, flecha bermellón arriba ─────────────────────
def build_wheel(col):
    cream, ink, lime, verm = toon("cream"), toon("ink"), toon("lime"), toon("verm")
    r = rig(col, "RIG-t_rueda", rot=(math.radians(90), 0, 0))
    obj(col, "GEO-t_rueda_aro", cylinder("ME-t_rueda_aro", 1.0, 0.16, 96), cream, bevel=0.04, segments=3)
    # la base es de tinta y delgada: sin casco, que asomaría por detrás como rayas sobre el aro
    obj(col, "GEO-t_rueda_base", cylinder("ME-t_rueda_base", 0.88, 0.03, 96), ink, loc=(0, 0, 0.08))["no_outline"] = True
    for i in range(8):
        a0 = math.radians(22.5 + 45 * i)
        m = (lime, verm, cream, verm, lime, verm, cream, verm)[i]
        g = obj(col, f"GEO-t_rueda_gajo_{i}", wedge(f"ME-t_rueda_gajo_{i}", 0.12, 0.83, a0, a0 + math.radians(45), 0.05, 16,
                                                    inset=0.022), m, loc=(0, 0, 0.09))
        g["no_outline"] = True
    obj(col, "GEO-t_rueda_cubo", cylinder("ME-t_rueda_cubo", 0.13, 0.12, 32), cream, loc=(0, 0, 0.14), bevel=0.02)
    parent_all(col, r, "GEO-t_rueda")
    tri = [(-0.16, 0.2), (0.16, 0.2), (0, -0.14)]
    obj(col, "GEO-t_flecha_rueda", flat("ME-t_flecha_rueda", None, 0.1, pts=tri), verm, loc=(0, -0.12, 1.08),
        rot=(math.radians(90), 0, 0), bevel=0.02)
    return dict(elev=6, azim=0, lens=70, fill=0.86)


# ─── rps: puño, mano abierta y paz; puños de manga lima, bermellón y papel ──────────────────────────────────────────
def hand(col, name, cuff, fingers_up, loc, rz, spread=0.0):
    """A chunky cartoon hand: a soft palm, four fingers (up or curled), a thumb and a coloured cuff."""
    cream = toon("cream")
    r = rig(col, f"RIG-{name}", loc=loc, rot=(0, math.radians(rz), 0))
    obj(col, f"GEO-{name}_palma", box(f"ME-{name}_palma", 0.56, 0.36, 0.5), cream, loc=(0, 0, 0.3), bevel=0.17, segments=5)
    obj(col, f"GEO-{name}_manga", cylinder(f"ME-{name}_manga", 0.26, 0.2, 32), cuff, loc=(0, 0, -0.05), bevel=0.04)
    xs = (-0.19, -0.063, 0.063, 0.19)
    for k, x in enumerate(xs):
        if fingers_up[k]:
            tall = 0.19 if k in (1, 2) else 0.16
            # `spread` abre los dedos en V (la tijera): cada uno se inclina hacia su lado desde su base
            tilt = -x * 0.5 + (math.copysign(spread, x) if spread else 0.0)
            ball(col, f"GEO-{name}_dedo_{k}", 1, cream, (x * 1.08 + tall * math.sin(tilt), 0, 0.5 + tall * math.cos(tilt)),
                 (0.075, 0.09, tall), rot=(0, tilt, 0))
        else:
            ball(col, f"GEO-{name}_dedo_{k}", 1, cream, (x, -0.16, 0.5), (0.075, 0.11, 0.11))
    if len(fingers_up) > 4 and fingers_up[4]:
        ball(col, f"GEO-{name}_pulgar", 1, cream, (-0.32, -0.02, 0.34), (0.085, 0.09, 0.16), rot=(0, math.radians(-50), 0))
    else:
        ball(col, f"GEO-{name}_pulgar", 1, cream, (-0.08, -0.2, 0.3), (0.18, 0.085, 0.085), rot=(0, math.radians(-14), 0))
    parent_all(col, r, f"GEO-{name}")


def build_rps(col):
    hand(col, "t_mano_puno", toon("lime"), (False, False, False, False), loc=(-0.62, 0, 0.62), rz=-12)
    hand(col, "t_mano_abierta", toon("verm"), (True, True, True, True, True), loc=(0.62, 0, 0.62), rz=12)
    hand(col, "t_mano_paz", toon("cream"), (False, True, True, False), loc=(0, -0.2, -0.45), rz=0, spread=0.36)
    return dict(elev=6, azim=0, lens=70, fill=0.84)


GAMES = {"roulette": build_roulette, "blackjack": build_blackjack, "dice": build_dice, "chicken": build_chicken,
         "limbo": build_limbo, "coinflip": build_coinflip, "war": build_war, "mines": build_mines, "moles": build_moles,
         "tower": build_tower, "poker": build_poker, "hilo": build_hilo, "wheel": build_wheel, "rps": build_rps}


def render_game(game, out_dir):
    sc, col = _scene(game)
    view = GAMES[game](col)
    sun(sc, col, direction=(-0.40, -0.62, 0.68))       # de frente y un poco de arriba: casi todo en luz, como el dibujo
    bpy.context.view_layer.update()
    objs = [o for o in col.objects if o.type in ("MESH", "CURVE")]
    lo, hi, _ = bounds(objs)
    span = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)
    for o in objs:
        if not o.get("no_outline"):
            # el casco se mide en el espacio del objeto: una pieza escalada (las fichas del póker) lo compensa
            outline(o, LINE * span / view["fill"] / max(abs(v) for v in o.matrix_world.to_scale()))
    bpy.context.view_layer.update()
    camera(sc, col, objs, elev=view["elev"], azim=view["azim"], lens=view["lens"], fill=view["fill"], name=f"CAM-t_{game}")
    sc.render.filepath = f"{out_dir}/{game}_960.png"
    bpy.ops.render.render(write_still=True)
    return sc.render.filepath
