"""El salón del casino alrededor de una mesa: alfombra, paneles de nogal con latón, terciopelo, columnas, techo de
casetones, candiles, apliques y otras mesas con su lámpara, a lo lejos. Es el "casino de verdad" al que entras al abrir
un juego (el dueño, 11-oct). Lo usan las salas de cada juego (sala_ruleta.py y las que sigan): la mesa del juego queda
en el origen con su cubierta a z = 0, y el salón se arma alrededor.

Todo es procedural (sin texturas descargadas ni modelos de terceros), con los materiales del contrato de arte (§3 y
§4): latón, nogal lacado, terciopelo, fieltro y la luz cálida de la escala oro. El color del terciopelo y de la
alfombra cambia por sala (THEMES).
"""
import math

import bmesh
import bpy
import mathutils

FLOOR_Z = -0.78                        # la mesa mide 78 cm
CEILING_Z = 3.0                        # 3.78 m sobre el piso
HALL = (-9.0, 9.0, -5.0, 13.0)         # x mín, x máx, y mín, y máx (quien juega está del lado −Y)
WARM = (1.0, 0.80, 0.58)               # la llave de los cuadros (contrato §5)

THEMES = {
    # terciopelo, alfombra base, motivo de la alfombra
    "ruleta": ("#3A0A0E", "#3A0D10", "#6B4A1A"),
    "cartas": ("#0F2A1E", "#14100D", "#6E5226"),
    "dados": ("#3B1C08", "#1E120B", "#7A5520"),
    "originales": ("#1A1612", "#121011", "#5E6B1A"),
}


def _linear(hex_color):
    h = hex_color.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


# ─── materiales ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _principled(name, color, rough, metal=0.0, coat=0.0, coat_rough=0.05, sheen=0.0, emission=None, strength=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = color if len(color) == 4 else (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = coat_rough
    b.inputs["Sheen Weight"].default_value = sheen
    if emission is not None:
        b.inputs["Emission Color"].default_value = (*emission, 1.0)
        b.inputs["Emission Strength"].default_value = strength
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return mat, nt, b


def materials(theme):
    velvet_hex, carpet_hex, motif_hex = THEMES[theme]
    m = {}
    m["brass"] = _principled("S_laton", (0.694, 0.434, 0.12), 0.3, metal=1.0)[0]
    m["walnut"] = _principled("S_nogal", (0.045, 0.022, 0.012), 0.4, coat=0.7, coat_rough=0.08)[0]
    m["velvet"] = _principled(f"S_terciopelo_{theme}", _linear(velvet_hex), 0.85, sheen=0.5)[0]
    m["dark"] = _principled("S_techo", (0.012, 0.010, 0.009), 0.7)[0]
    m["felt"] = _principled("S_fieltro", (0.005, 0.023, 0.013), 0.97, sheen=0.6)[0]
    m["bulb"] = _principled("S_foco", (1.0, 0.9, 0.75), 0.4, emission=(1.0, 0.82, 0.6), strength=40.0)[0]
    m["shade"] = _principled("S_pantalla", (1.0, 0.85, 0.6), 0.6, emission=(1.0, 0.78, 0.52), strength=6.0)[0]
    m["crystal"] = _principled("S_cristal", (1.0, 0.95, 0.85), 0.05, emission=(1.0, 0.86, 0.66), strength=40.0)[0]
    # alfombra: el motivo dorado sale de un patrón de Voronoi y anillos, sin texturas
    mat, nt, b = _principled(f"S_alfombra_{theme}", _linear(carpet_hex), 0.95)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 7.0
    vor.feature = "F1"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = _linear(motif_hex)
    ramp.color_ramp.elements[1].position = 0.05
    ramp.color_ramp.elements[1].color = _linear(carpet_hex)
    e = ramp.color_ramp.elements.new(0.34)
    e.color = _linear(carpet_hex)
    e2 = ramp.color_ramp.elements.new(0.36)
    e2.color = _linear(motif_hex)
    e3 = ramp.color_ramp.elements.new(0.375)
    e3.color = _linear(carpet_hex)
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    nt.links.new(vor.outputs["Distance"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    m["carpet"] = mat
    return m


# ─── geometría ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _mesh_object(col, name, build, mat, loc=(0, 0, 0), rot=(0, 0, 0), smooth=False):
    me = bpy.data.meshes.new(f"ME-{name}")
    bm = bmesh.new()
    build(bm)
    for f in bm.faces:
        f.smooth = smooth
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    return o


def _box(bm, center, size):
    m = mathutils.Matrix.Translation(center) @ mathutils.Matrix.Diagonal((*size, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


def _sphere(bm, center, r, segs=10):
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=max(4, segs // 2), radius=r,
                              matrix=mathutils.Matrix.Translation(center))


def _cylinder(bm, center, r, h, segs=24, r2=None, rot=None):
    m = mathutils.Matrix.Translation(center)
    if rot is not None:
        m = m @ rot.to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r if r2 is None else r2, depth=h, matrix=m)


def _point(col, name, loc, energy, radius=0.05, color=WARM):
    d = bpy.data.lights.new(name, "POINT")
    d.energy = energy
    d.color = color
    d.shadow_soft_size = radius
    o = bpy.data.objects.new(name, d)
    col.objects.link(o)
    o.location = loc
    return o


def _spot(col, name, loc, energy, size_deg=70, blend=0.6, color=WARM):
    d = bpy.data.lights.new(name, "SPOT")
    d.energy = energy
    d.color = color
    d.spot_size = math.radians(size_deg)
    d.spot_blend = blend
    d.shadow_soft_size = 0.15
    o = bpy.data.objects.new(name, d)
    col.objects.link(o)
    o.location = loc
    return o                                          # un foco apunta hacia −Z: hacia la mesa


def floor_walls_ceiling(col, m):
    x0, x1, y0, y1 = HALL
    _mesh_object(col, "GEO-sala_alfombra", lambda bm: _box(bm, (0, 4, FLOOR_Z - 0.01), (40, 40, 0.02)), m["carpet"])
    h = CEILING_Z - FLOOR_Z
    zc = FLOOR_Z + h / 2

    def walls(bm):
        _box(bm, ((x0 + x1) / 2, y1, zc), (x1 - x0, 0.2, h))          # fondo
        _box(bm, (x0, (y0 + y1) / 2, zc), (0.2, y1 - y0, h))          # izquierda
        _box(bm, (x1, (y0 + y1) / 2, zc), (0.2, y1 - y0, h))          # derecha
        _box(bm, ((x0 + x1) / 2, y0, zc), (x1 - x0, 0.2, h))          # detrás de quien juega
    _mesh_object(col, "GEO-sala_muros", walls, m["walnut"])

    # terciopelo en la parte alta de los muros y latón en el filo: paneles de 1.5 m
    def velvet(bm):
        zv = FLOOR_Z + 1.25 + (h - 1.25) / 2
        for x in [x0 + 0.75 + 1.5 * i for i in range(int((x1 - x0) / 1.5))]:
            _box(bm, (x, y1 - 0.12, zv), (1.32, 0.04, h - 1.6))
        for y in [y0 + 0.75 + 1.5 * i for i in range(int((y1 - y0) / 1.5))]:
            _box(bm, (x0 + 0.12, y, zv), (0.04, 1.32, h - 1.6))
            _box(bm, (x1 - 0.12, y, zv), (0.04, 1.32, h - 1.6))
    _mesh_object(col, "GEO-sala_terciopelo", velvet, m["velvet"])

    def trims(bm):
        for z in (FLOOR_Z + 1.05, FLOOR_Z + 1.12, CEILING_Z - 0.12):
            _box(bm, ((x0 + x1) / 2, y1 - 0.13, z), (x1 - x0, 0.03, 0.025))
            _box(bm, (x0 + 0.13, (y0 + y1) / 2, z), (0.03, y1 - y0, 0.025))
            _box(bm, (x1 - 0.13, (y0 + y1) / 2, z), (0.03, y1 - y0, 0.025))
        for x in [x0 + 1.5 * i for i in range(1, int((x1 - x0) / 1.5))]:
            _box(bm, (x, y1 - 0.13, (FLOOR_Z + CEILING_Z) / 2), (0.03, 0.03, h))
    _mesh_object(col, "GEO-sala_filetes", trims, m["brass"])

    # techo de casetones: vigas de nogal con canto de latón sobre un plafón oscuro
    _mesh_object(col, "GEO-sala_techo", lambda bm: _box(bm, (0, 4, CEILING_Z + 0.05), (40, 40, 0.1)), m["dark"])

    def beams(bm):
        for x in [x0 + 2.0 * i for i in range(int((x1 - x0) / 2.0) + 1)]:
            _box(bm, (x, (y0 + y1) / 2, CEILING_Z - 0.12), (0.22, y1 - y0, 0.24))
        for y in [y0 + 2.0 * i for i in range(int((y1 - y0) / 2.0) + 1)]:
            _box(bm, ((x0 + x1) / 2, y, CEILING_Z - 0.12), (x1 - x0, 0.22, 0.24))
    _mesh_object(col, "GEO-sala_vigas", beams, m["walnut"])


def sconces(col, m):
    """Wall lamps every 3 m: a brass plate and a warm glowing shade, the bokeh of the frames."""
    x0, x1, y0, y1 = HALL
    spots = [(x, y1 - 0.18, 0) for x in range(int(x0) + 2, int(x1) - 1, 3)]
    spots += [(x0 + 0.18, y, math.pi / 2) for y in range(int(y0) + 3, int(y1) - 1, 3)]
    spots += [(x1 - 0.18, y, -math.pi / 2) for y in range(int(y0) + 3, int(y1) - 1, 3)]
    z = FLOOR_Z + 2.0

    def plates(bm):
        for x, y, _ in spots:
            _box(bm, (x, y, z), (0.12, 0.12, 0.3))
    _mesh_object(col, "GEO-sala_apliques", plates, m["brass"])

    def shades(bm):
        for x, y, _ in spots:
            _cylinder(bm, (x, y, z + 0.12), 0.07, 0.16, segs=16, r2=0.1)
    _mesh_object(col, "GEO-sala_pantallas", shades, m["shade"], smooth=True)
    for i, (x, y, _) in enumerate(spots):
        _point(col, f"LGT-sala_aplique_{i}", (x, y, z + 0.1), 30.0, radius=0.08)


def chandelier(col, m, name, center, ring=0.6, drop=0.9):
    cx, cy = center
    z = CEILING_Z - drop

    def frame(bm):
        _cylinder(bm, (cx, cy, z + drop / 2), 0.012, drop, segs=8)
        for r, k in ((ring, 24), (ring * 0.6, 14)):
            for i in range(k):
                a = 2 * math.pi * i / k
                b = 2 * math.pi * (i + 1) / k
                p = mathutils.Vector((cx + r * math.cos(a), cy + r * math.sin(a), z))
                q = mathutils.Vector((cx + r * math.cos(b), cy + r * math.sin(b), z))
                mid = (p + q) / 2
                ln = (q - p).length
                rot = mathutils.Vector((q - p)).to_track_quat("Z", "Y").to_euler()
                _cylinder(bm, mid, 0.01, ln, segs=6, rot=rot)
    _mesh_object(col, f"GEO-{name}_marco", frame, m["brass"])

    def crystals(bm):
        for r, k, dz in ((ring, 24, -0.06), (ring * 0.6, 14, -0.12), (ring * 0.25, 6, -0.22)):
            for i in range(k):
                a = 2 * math.pi * (i + 0.5) / k
                _sphere(bm, (cx + r * math.cos(a), cy + r * math.sin(a), z + dz), 0.035, segs=8)
    _mesh_object(col, f"GEO-{name}_cristales", crystals, m["crystal"], smooth=True)
    _point(col, f"LGT-{name}", (cx, cy, z - 0.1), 900.0, radius=0.4)


def far_tables(col, m, table_parts, spots_xy):
    """Other tables of the room, each under its own pendant lamp. They reuse the meshes of the game's table."""
    for i, (x, y, rz) in enumerate(spots_xy):
        for part in table_parts:
            o = bpy.data.objects.new(f"{part.name}_lejos_{i}", part.data)
            col.objects.link(o)
            o.location = (x, y, 0.0)
            o.rotation_euler = (0, 0, rz)
        lamp_z = 1.35

        def lamp(bm, x=x, y=y):
            _cylinder(bm, (x, y, lamp_z + (CEILING_Z - lamp_z) / 2), 0.008, CEILING_Z - lamp_z, segs=6)
            _cylinder(bm, (x, y, lamp_z), 0.18, 0.16, segs=24, r2=0.05)
        _mesh_object(col, f"GEO-sala_lampara_{i}", lamp, m["brass"], smooth=True)
        _mesh_object(col, f"GEO-sala_lampara_luz_{i}", lambda bm, x=x, y=y: _sphere(bm, (x, y, lamp_z - 0.07), 0.07),
                     m["bulb"], smooth=True)
        _spot(col, f"LGT-sala_mesa_{i}", (x, y, lamp_z - 0.1), 900.0, size_deg=64, blend=0.5)


def bar(col, m):
    """The back bar: a lacquered counter and shelves of warm glowing bottles, the bokeh behind the tables."""
    x0, x1, y0, y1 = HALL
    _mesh_object(col, "GEO-sala_barra", lambda bm: _box(bm, (0, y1 - 1.4, FLOOR_Z + 0.55), (7.0, 0.7, 1.1)), m["walnut"])
    _mesh_object(col, "GEO-sala_barra_laton", lambda bm: _box(bm, (0, y1 - 1.76, FLOOR_Z + 1.11), (7.1, 0.06, 0.03)),
                 m["brass"])

    # botellas de vidrio ámbar, verde y humo, con luz por detrás: no un muro de focos
    glass = [_principled(f"S_vidrio_{k}", c, 0.15, emission=c, strength=st)[0]
             for k, (c, st) in enumerate((((0.55, 0.28, 0.06), 1.2), ((0.18, 0.32, 0.12), 0.8), ((0.42, 0.36, 0.30), 0.9)))]
    for g, mat in enumerate(glass):
        def bottles(bm, g=g):
            for row in range(3):
                for k in range(26):
                    if (k + row * 7) % 3 != g:
                        continue
                    x = -3.3 + k * 0.26 + (0.13 if row % 2 else 0.0)
                    h = 0.22 + 0.06 * ((k * 7 + row * 3) % 4) / 3
                    _cylinder(bm, (x, y1 - 0.3, FLOOR_Z + 1.30 + row * 0.42 + h / 2), 0.033, h, segs=8)
        _mesh_object(col, f"GEO-sala_botellas_{g}", bottles, mat, smooth=True)

    def shelves(bm):
        for r in range(3):
            _box(bm, (0, y1 - 0.3, FLOOR_Z + 1.28 + r * 0.42), (7.2, 0.3, 0.025))
    _mesh_object(col, "GEO-sala_repisas", shelves, m["brass"])
    for k in range(5):
        _point(col, f"LGT-sala_barra_{k}", (-2.8 + k * 1.4, y1 - 0.6, FLOOR_Z + 2.2), 60.0, radius=0.3)


def columns(col, m, spots_xy):
    def cols(bm):
        for x, y in spots_xy:
            _cylinder(bm, (x, y, (FLOOR_Z + CEILING_Z) / 2), 0.28, CEILING_Z - FLOOR_Z, segs=32)
    _mesh_object(col, "GEO-sala_columnas", cols, m["walnut"], smooth=True)

    def caps(bm):
        for x, y in spots_xy:
            for z in (FLOOR_Z + 0.12, FLOOR_Z + 1.1, CEILING_Z - 0.35):
                _cylinder(bm, (x, y, z), 0.31, 0.06, segs=32)
    _mesh_object(col, "GEO-sala_columnas_laton", caps, m["brass"], smooth=True)


def build_hall(sc, theme, table_parts):
    col = bpy.data.collections.get(f"S-sala_{theme}") or bpy.data.collections.new(f"S-sala_{theme}")
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    m = materials(theme)
    floor_walls_ceiling(col, m)
    sconces(col, m)
    for i, c in enumerate(((0.0, 5.0), (-5.0, 9.0), (5.0, 9.0), (0.0, 11.0))):
        chandelier(col, m, f"sala_candil_{i}", c)
    far_tables(col, m, table_parts, [(-3.4, 3.4, 0.35), (3.2, 3.8, -0.3), (0.2, 6.6, 0.05), (-5.6, 7.4, 1.1),
                                       (5.6, 7.8, -1.0), (-1.8, 10.4, 0.2)])
    columns(col, m, [(-4.6, 4.6), (4.6, 4.6), (-4.6, 9.4), (4.6, 9.4)])
    bar(col, m)
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.006, 0.0045, 0.0035, 1.0)
    sc.view_settings.exposure = -0.2      # el salón se ve entero, pero en penumbra: luz en charcos sobre las mesas
    return col
