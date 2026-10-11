"""Exporta la ruleta de assets3d/juegos/juegos.blend (escena J_roulette) a assets3d/juegos/ruleta-exportada.glb.

Se corre dentro de Blender 5.2, con juegos.blend abierto (está también como bloque de texto `e6_exportar_ruleta.py`):

    exec(bpy.data.texts["e6_exportar_ruleta.py"].as_string()); export_roulette(r"<ruta>/ruleta-exportada.glb")

Después: node assets3d/herramientas/optimizar-glb.mjs assets3d/juegos/ruleta-exportada.glb static/3d/ruleta.glb \
          --simplificar 0.0004 --textura 1024

Lo que hace (equipo/contratos/arte3d.md §7 y §12):
- Centra la rueda en el origen mientras exporta y la devuelve a su lugar.
- La bola cuelga de RIG-ruleta y no del rotor: en la web se mueve sola (docs/arte/ruleta-animacion.mjs).
- El exportador de glTF no lee nodos procedurales. Mientras exporta, la madera toma el color de su rampa al 60 % y
  el latón una rugosidad de 0.34; al terminar, cada material vuelve a quedar como estaba.
"""
import bpy

RAMP_POINT = 0.6
BRASS_ROUGHNESS = 0.34


def _principled(material):
    return next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def export_roulette(path, scene_name="J_roulette", collection_name="J-ruleta"):
    scene = bpy.data.scenes[scene_name]
    bpy.context.window.scene = scene
    rig = bpy.data.objects["RIG-ruleta"]
    ball = bpy.data.objects["GEO-ruleta_bola"]
    if ball.parent != rig:
        world = ball.matrix_world.copy()
        ball.parent = rig
        ball.matrix_world = world
    parts = [o for o in bpy.data.collections[collection_name].objects
             if (o.name.startswith("GEO-ruleta") or o.name.startswith("RIG-ruleta")) and "sombra" not in o.name]
    materials = {m for o in parts if o.type == "MESH" for m in o.data.materials if m}

    saved = []                                       # (material, input name, linked socket, previous value)
    for material in materials:
        tree, bsdf = material.node_tree, _principled(material)
        base = bsdf.inputs["Base Color"]
        if base.is_linked and base.links[0].from_node.type == "VALTORGB":
            link = base.links[0]
            ramp = link.from_node.color_ramp
            c0, c1 = ramp.elements[0].color, ramp.elements[-1].color
            saved.append((material, "Base Color", link.from_socket, tuple(base.default_value)))
            tree.links.remove(link)
            base.default_value = tuple(c0[i] + (c1[i] - c0[i]) * RAMP_POINT for i in range(4))
        rough = bsdf.inputs["Roughness"]
        if rough.is_linked:
            link = rough.links[0]
            saved.append((material, "Roughness", link.from_socket, rough.default_value))
            tree.links.remove(link)
            rough.default_value = BRASS_ROUGHNESS

    location = rig.location.copy()
    rig.location = (0, 0, 0)
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in parts:
        o.select_set(True)
    try:
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_yup=True,
                                  export_apply=True, export_cameras=False, export_lights=False,
                                  export_image_format="WEBP", export_draco_mesh_compression_enable=False,
                                  export_extras=False)
    finally:
        rig.location = location
        for material, name, socket, value in saved:
            bsdf = _principled(material)
            bsdf.inputs[name].default_value = value
            material.node_tree.links.new(socket, bsdf.inputs[name])
        bpy.context.view_layer.update()
