"""El estilo de los dibujos de Clique llevado a 3D (decisión del dueño, 11-oct): formas gordas, colores planos de la
paleta, una sombra de un solo tono y contorno de tinta. Lo usan las escenas T_<juego> de assets3d/juegos/juegos.blend.

En Blender: exec(bpy.data.texts["e6_toon.py"].as_string()). Es la copia en el repositorio de ese bloque de texto.

- toon(): material de dos tonos (luz y sombra) con colores exactos de la paleta. La gestión de color es "Standard"
  para que el color de la paleta salga tal cual, sin la curva de AgX de los cuadros del club.
- setup_toon(): EEVEE y fondo transparente.
- outline(): contorno de tinta como casco invertido por pieza; su grueso se calcula para que salga como el trazo de
  los dibujos 2D (2.1 % del lado de la imagen: 10 px a 480).
- La forma se arma con primitivas redondeadas (bevel y subdivisión); ver equipo/contratos/arte3d.md §13.
"""
import bpy
import bmesh
import math
import mathutils

# Paleta: el tono de luz sale de static/css/tokens.css; el de sombra es el que usa el dibujo 2D para dar volumen y aún
# no es token (petición a E4 en equipo/BITACORA.md). La misma tabla está en docs/arte/estilo-toon.mjs y
# tests/test_arte.py comprueba que sean iguales.
PALETTE = {
    "cream": ("#EFE6D2", "#CFC3A8"),     # papel · hueso
    "ink": ("#1A1612", "#0E0C0A"),       # tinta-papel · sala
    "lime": ("#C6F432", "#9CC320"),
    "verm": ("#FF4B2B", "#D2361B"),
    "verm_soft": ("#F2664A", "#D24E36"),  # el gajo claro del dibujo, para que no se pierda sobre el póster bermellón
    "felt": ("#2F6B47", "#1E3B2C"),      # fieltro-2 · fieltro
    "gold": ("#FBB635", "#D9952A"),      # oro-400
}
INK_HEX = "#1A1612"


def linear(hex_color):
    h = hex_color.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def toon(name, lit_hex=None, shade_hex=None, threshold=0.38):
    """Two-tone flat material: lit colour above the threshold of light, shade colour below. Reused by name."""
    if lit_hex is None:
        lit_hex, shade_hex = PALETTE[name]
    key = f"T_{name}"
    mat = bpy.data.materials.get(key)
    if mat is None:
        mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    diffuse = nt.nodes.new("ShaderNodeBsdfDiffuse")
    to_rgb = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    emit = nt.nodes.new("ShaderNodeEmission")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = linear(shade_hex)
    ramp.color_ramp.elements[1].position = threshold
    ramp.color_ramp.elements[1].color = linear(lit_hex)
    nt.links.new(diffuse.outputs["BSDF"], to_rgb.inputs["Shader"])
    nt.links.new(to_rgb.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    mat.diffuse_color = linear(lit_hex)   # what the viewport and the glTF export show
    return mat


def setup_toon(sc, res=960):
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 32
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    w = bpy.data.worlds.get("W-toon") or bpy.data.worlds.new("W-toon")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 0.25             # light for the shade side, so the ramp sees something
    sc.world = w
    # Sin Freestyle: el contorno es un casco invertido por pieza (outline()), lo mismo que hace
    # docs/arte/estilo-toon.mjs en la web, así el ícono y el juego en vivo se ven igual.
    sc.render.use_freestyle = False
    return sc


def outline_material():
    mat = bpy.data.materials.get("T_contorno")
    if mat is None:
        mat = bpy.data.materials.new("T_contorno")
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        emit = nt.nodes.new("ShaderNodeEmission")
        emit.inputs["Color"].default_value = linear(INK_HEX)
        nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    mat.use_backface_culling = True
    mat.diffuse_color = linear(INK_HEX)
    return mat


def outline(o, thickness):
    """Ink outline: an inverted hull around the piece (Solidify outward, flipped normals, back faces culled)."""
    if o.type != "MESH":
        return
    ink = outline_material()
    if ink.name not in [m.name for m in o.data.materials if m]:
        o.data.materials.append(ink)
    m = o.modifiers.get("contorno") or o.modifiers.new("contorno", "SOLIDIFY")
    m.thickness = thickness
    m.offset = 1.0
    m.use_flip_normals = True
    m.use_even_offset = True
    m.use_quality_normals = True
    m.use_rim = False
    m.material_offset = len(o.data.materials) - 1


def sun(sc, col, name="LGT-sol", direction=(-0.55, -0.35, 0.76), energy=3.0):
    name = f"{name}_{sc.name}"           # una luz por escena: los nombres de objeto son de todo el archivo
    o = bpy.data.objects.get(name)
    if o is None:
        d = bpy.data.lights.new(name, "SUN")
        o = bpy.data.objects.new(name, d)
    if o.name not in col.objects:
        col.objects.link(o)
    o.data.energy = energy
    o.data.angle = math.radians(2)
    o.data.use_shadow = False          # plano, como el dibujo: el tono lo da el ángulo, no las sombras
    o.rotation_euler = (-mathutils.Vector(direction)).to_track_quat("-Z", "Y").to_euler()
    return o


def obj(col, name, mesh, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), smooth=True, bevel=0.0, segments=3, subsurf=0):
    """A named object from a bmesh-built mesh, with an optional bevel, smooth shading and subdivision."""
    o = bpy.data.objects.get(name)
    if o is not None:
        bpy.data.objects.remove(o, do_unlink=True)
    o = bpy.data.objects.new(name, mesh)
    col.objects.link(o)
    if mat is not None:
        mesh.materials.clear()
        mesh.materials.append(mat)
    o.location = loc
    o.rotation_euler = rot
    if bevel:
        b = o.modifiers.new("bevel", "BEVEL")
        b.width = bevel
        b.segments = segments
        b.limit_method = "ANGLE"
    if subsurf:
        s = o.modifiers.new("sub", "SUBSURF")
        s.levels = s.render_levels = subsurf
    for p in mesh.polygons:
        p.use_smooth = smooth
    return o


def mesh_from(name, build):
    me = bpy.data.meshes.get(name)
    if me is not None:
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    build(bm)
    bm.to_mesh(me)
    bm.free()
    return me


def cylinder(name, r, h, segs=64, r2=None):
    return mesh_from(name, lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r,
                                                            radius2=r if r2 is None else r2, depth=h))


def sphere(name, r, segs=32):
    return mesh_from(name, lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=r))


def box(name, sx, sy, sz):
    def build(bm):
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    return mesh_from(name, build)


def wedge(name, r0, r1, a0, a1, h, steps=12, inset=0.0):
    """A ring sector from radius r0 to r1, angles a0→a1 (radians), height h, sitting on z=0. With `inset`, its two
    straight sides move in by that distance, parallel: the ink between two wedges is a stroke of even width."""
    def build(bm):
        ring_in, ring_out = [], []
        for r, ring in ((r0, ring_in), (r1, ring_out)):
            da = math.asin(min(1.0, inset / r)) if inset else 0.0
            for i in range(steps + 1):
                a = (a0 + da) + ((a1 - da) - (a0 + da)) * i / steps
                ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), 0)))
        faces = []
        for i in range(steps):
            faces.append(bm.faces.new((ring_in[i], ring_out[i], ring_out[i + 1], ring_in[i + 1])))
        ext = bmesh.ops.extrude_face_region(bm, geom=faces)
        verts = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=(0, 0, h), verts=verts)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_from(name, build)
