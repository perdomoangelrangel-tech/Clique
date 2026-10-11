"""Los 14 juegos con acabado de casino (el dueño, 11-oct: "hazlos más premium… que se vea profesional y como un casino
de verdad"). Las formas son las del dibujo (juegos_toon.py) y la luz y los materiales, los de los cuadros aprobados:
laca con capa transparente, esmalte, latón y fieltro, con sombra suave y luz cálida (equipo/contratos/arte3d.md §11 y
§14). Sin contorno de tinta: el borde lo dibuja la luz.

Sin abrir Blender (pip install bpy==5.2.2), desde la raíz del repositorio:

    python assets3d/herramientas/juegos_premium.py <salida> roulette,blackjack,dice [muestras]

Escribe <salida>/<juego>_960.png con fondo transparente; de ahí, iconos_juego.py como siempre.
"""
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))

# Cada color del dibujo y su acabado: (color, rugosidad, metálico, capa, rugosidad de la capa)
FINISH = {
    "cream": ("#EFE6D2", 0.38, 0.0, 0.6, 0.08),      # marfil satinado
    "ink": ("#1A1612", 0.35, 0.0, 1.0, 0.04),        # laca negra
    "lime": ("#C6F432", 0.28, 0.0, 1.0, 0.05),       # esmalte lima, el de la marca
    "verm": ("#E23A22", 0.32, 0.0, 1.0, 0.05),       # laca roja
    "verm_soft": ("#EE5A3E", 0.34, 0.0, 1.0, 0.05),
    "felt": ("#1E3B2C", 0.95, 0.0, 0.0, 0.0),        # fieltro
    "gold": ("#D9B061", 0.28, 1.0, 0.0, 0.0),        # latón (contrato §3)
}


def _load_texts():
    for name in ("e6_toon.py", "e6_util.py", "juegos_toon.py"):
        t = bpy.data.texts.get(name) or bpy.data.texts.new(name)
        t.clear()
        t.write(open(os.path.join(HERE, name), encoding="utf-8").read())
    ns = {}
    exec(bpy.data.texts["juegos_toon.py"].as_string(), ns)
    util = {}
    exec(bpy.data.texts["e6_util.py"].as_string(), util)
    return ns, util


def _linear(hex_color):
    h = hex_color.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def finish(key):
    """P_<colour>: the drawing's colour with a real finish. Reused by name."""
    hex_color, rough, metal, coat, coat_rough = FINISH[key]
    name = f"P_{key}"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = _linear(hex_color)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Coat Roughness"].default_value = coat_rough
    if key == "felt":
        bsdf.inputs["Sheen Weight"].default_value = 0.6
        bsdf.inputs["Sheen Roughness"].default_value = 0.35
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mat.diffuse_color = _linear(hex_color)
    return mat


def premium(col):
    """Every T_<colour> of the drawing becomes P_<colour>; the ink outlines go (the light draws the edge now)."""
    for o in col.objects:
        if o.type not in ("MESH", "CURVE"):
            continue
        for m in [m for m in o.modifiers if m.name == "contorno"]:
            o.modifiers.remove(m)
        mats = o.data.materials
        for i, m in enumerate(mats):
            if m is None:
                continue
            key = m.name[2:] if m.name.startswith("T_") else None
            if key in FINISH:
                mats[i] = finish(key)
        # the ink hull material slot, if any, is dropped with the modifier: nothing points to it any more
    return col


def render_game(game, out_dir, samples=64, res=960):
    ns, util = _load_texts()
    if bpy.context.window is None:
        # sin ventana (bpy como módulo) la escena del contexto es la única que evalúa el depsgraph: se usa esa
        sc = bpy.context.scene
        sc.name = f"P_{game}"
    else:
        sc = bpy.data.scenes.get(f"P_{game}") or bpy.data.scenes.new(f"P_{game}")
        bpy.context.window.scene = sc
    col = bpy.data.collections.get(f"P-{game}") or bpy.data.collections.new(f"P-{game}")
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    view = ns["GAMES"][game](col)
    premium(col)
    util["setup"](sc, res=res, samples=samples)
    objs = [o for o in col.objects if o.type in ("MESH", "CURVE")]
    lo, hi, _ = util["bounds"](objs)
    center = (lo + hi) / 2
    r = max((hi - lo).length / 2, 0.1)
    util["lights"](sc, col, center, r, prefix=f"{game}_")
    util["shadow_catcher"](sc, col, lo.z, center, r, prefix=f"{game}_")
    util["camera"](sc, col, objs, elev=max(view["elev"], 18), azim=view["azim"], lens=view["lens"], fill=view["fill"] * 0.97,
                   name=f"CAM-p_{game}")
    sc.render.filepath = os.path.join(out_dir, f"{game}_960.png")
    bpy.ops.render.render(write_still=True, scene=sc.name)
    return sc.render.filepath


if __name__ == "__main__":
    out, games = sys.argv[1], sys.argv[2].split(",")
    samples = int(sys.argv[3]) if len(sys.argv) > 3 else 64
    os.makedirs(out, exist_ok=True)
    for g in games:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        print("RENDER", render_game(g, out, samples))
