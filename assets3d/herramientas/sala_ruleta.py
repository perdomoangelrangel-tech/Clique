"""La sala de ruleta (decisión del dueño, 11-oct: "haz los ambientes de los juegos como un casino real y que seas
transportado a esas salas"). Parte del cuadro aprobado assets3d/estilo/01-mesa-ruleta.blend (mesa de fieltro, riel
lacado, paño de apuestas, fichas, boleto, lámparas y bokeh) y le pone la rueda del dibujo con acabado de casino:
laca marfil, negra y roja, latón en trastes y bordes, y el lima de la marca en el 0 y en la torreta.

Sin abrir Blender (pip install bpy==5.2.2), desde la raíz del repositorio:

    python -c "import runpy; runpy.run_path('assets3d/herramientas/sala_ruleta.py')['main']('.', 'salida/')"

Escribe <salida>/sala-ruleta-1920x1080.png y sala-ruleta-1080x2340.png, y guarda la escena en <salida>/sala-ruleta.blend.
Con main_panorama(repo, salida) escribe el panorama de la sala visto desde la cámara del juego en vivo (PNG de
3072 × 1536, 32 muestras con eliminación de ruido), el fondo que la web pone alrededor de la rueda. Para la app:

    python -c "from PIL import Image, ImageEnhance; im = Image.open('salida/sala-ruleta-panorama-3072.png').convert('RGB'); \
      ImageEnhance.Brightness(im).enhance(1.18).save('static/3d/salas/ruleta.webp', 'WEBP', quality=88, method=6)"

(un 18 % más de luz: en la web el panorama no pasa por el tone mapping y la rueda sí). El tope es 4096 × 2048 y 600 KB
(equipo/contratos/arte3d.md §6 y §14). La rueda es la misma geometría de la ruleta en vivo (ruleta_toon.py): lo que se
ve en la sala es lo que gira en la app.
"""
import math
import os
import runpy

import bpy

WHEEL_AT = (-0.86, 0.0, 0.0)        # donde estaba la rueda de madera del cuadro
WHEEL_SCALE = 1.0                    # la misma medida que la rueda en vivo: la sala y el juego coinciden
# La cámara del juego en vivo (docs/arte/prueba-ruleta.html): fija, a la altura de los ojos de quien juega de pie
# frente a la rueda (−Y en Blender), a VIEW_OFFSET del centro de la rueda. La sala se renderiza como panorama desde ese
# punto, así que la web puede girar la cámara y abrir o cerrar el ángulo sin que la rueda se despegue de su mesa.
VIEW_OFFSET = (0.0, -1.15, 0.80)       # en three.js: (0, 0.80, 1.15) desde el centro de la rueda
PANORAMA_FSTOP = 0.5                   # bokeh de los candiles, la barra y las otras mesas


def view_point():
    import mathutils
    return mathutils.Vector(WHEEL_AT) + mathutils.Vector(VIEW_OFFSET)


def panorama(sc, path, width=3072, samples=32):
    """The room seen from the live camera, all around (equirectangular). The wheel is not in it (the web draws it)
    but its shadow and its reflection on the felt are. Image centre = Blender +X = three.js +X."""
    cam_data = bpy.data.cameras.get("CAM-sala_panorama") or bpy.data.cameras.new("CAM-sala_panorama")
    cam_data.type = "PANO"
    cam_data.panorama_type = "EQUIRECTANGULAR"
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = math.hypot(*VIEW_OFFSET)
    cam_data.dof.aperture_fstop = PANORAMA_FSTOP
    cam = bpy.data.objects.get("CAM-sala_panorama") or bpy.data.objects.new("CAM-sala_panorama", cam_data)
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.location = view_point()
    cam.rotation_euler = (math.radians(90), 0.0, math.radians(-90))
    wheel = [o for o in bpy.data.collections["T-ruleta-vivo"].objects if o.type == "MESH"]
    for o in wheel:
        o.visible_camera = False                  # la rueda la pone la web; su sombra y su reflejo se quedan
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.film_transparent = False
    sc.render.resolution_x, sc.render.resolution_y = width, width // 2
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for o in wheel:
        o.visible_camera = True
    return path


def live_view(sc, path, width, height, pitch_deg, vfov_deg, samples=32):
    """What the live game shows: the room from the panorama point, the wheel in the lower part of the frame."""
    cam_data = bpy.data.cameras.get("CAM-sala_vivo") or bpy.data.cameras.new("CAM-sala_vivo")
    cam_data.type = "PERSP"
    cam_data.sensor_fit = "VERTICAL"
    cam_data.angle_y = math.radians(vfov_deg)
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = math.hypot(*VIEW_OFFSET)
    cam_data.dof.aperture_fstop = 0.6
    cam = bpy.data.objects.get("CAM-sala_vivo") or bpy.data.objects.new("CAM-sala_vivo", cam_data)
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.location = view_point()
    cam.rotation_euler = (math.radians(90 - pitch_deg), 0.0, 0.0)     # mirando hacia +Y, inclinada hacia abajo
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.film_transparent = False
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def main_preview(repo, out_dir):
    sc = open_room(repo, out_dir)
    return [live_view(sc, os.path.join(out_dir, "vivo-escritorio.png"), 960, 540, 23, 42),
            live_view(sc, os.path.join(out_dir, "vivo-celular.png"), 450, 975, 22, 74)]


def premium_materials():
    """Only the brass changes: the room's own (M_laton, with its grain) instead of the plain one of the live wheel."""
    brass = bpy.data.materials["M_laton"]
    for o in bpy.data.collections["T-ruleta-vivo"].objects:
        if o.type == "MESH":
            for i, m in enumerate(o.data.materials):
                if m and m.name == "roulette_gold":
                    o.data.materials[i] = brass


def build_room(repo):
    sc = bpy.data.scenes["01_ruleta"]
    hall = runpy.run_path(os.path.join(repo, "assets3d", "herramientas", "sala_casino.py"))
    parts = [bpy.data.objects[n] for n in ("GEO-ruleta_falda", "GEO-ruleta_fieltro", "GEO-ruleta_riel",
                                            "GEO-ruleta_filete", "GEO-ruleta_pano")]
    # el bokeh del cuadro eran esferas sueltas en lo oscuro; ahora lo dan los candiles y las mesas del salón
    for o in [o for o in bpy.data.objects if o.name.startswith("FX-bokeh")]:
        bpy.data.objects.remove(o, do_unlink=True)
    hall["build_hall"](sc, "ruleta", parts)
    old = bpy.data.objects.get("RIG-ruleta")
    if old is not None:
        doomed = [old] + list(old.children_recursive)
        for o in doomed:
            bpy.data.objects.remove(o, do_unlink=True)
    ns = runpy.run_path(os.path.join(repo, "assets3d", "herramientas", "ruleta_toon.py"))
    ns["build_roulette"](os.path.join(repo, "assets3d", "texturas", "ruleta-numeros.png"))
    col = bpy.data.collections["T-ruleta-vivo"]
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    tmp = bpy.data.scenes.get("T_ruleta_vivo")
    if tmp is not None and tmp != sc:
        bpy.data.scenes.remove(tmp)
    rig = bpy.data.objects["RIG-ruleta"]
    rig.location = WHEEL_AT
    rig.scale = (WHEEL_SCALE,) * 3
    premium_materials()
    # la rueda quieta con la bola en el 0, frente a quien juega (como la deja la animación al empezar)
    ball = bpy.data.objects["GEO-ruleta_bola"]
    ball.location = (0.0, -0.244, 0.0565)
    for o in col.objects:
        o.hide_render = False
    return sc


def render(sc, out_dir, percentage=100, samples=128):
    sc.render.resolution_percentage = percentage
    sc.eevee.taa_render_samples = samples
    sc.render.image_settings.file_format = "PNG"
    shots = (("CAM-ruleta", 1920, 1080), ("CAM-ruleta_v", 1080, 2340))
    paths = []
    for cam, w, h in shots:
        sc.camera = bpy.data.objects[cam]
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.render.filepath = os.path.join(out_dir, f"sala-ruleta-{w}x{h}.png")
        bpy.ops.render.render(write_still=True)
        paths.append(sc.render.filepath)
    return paths


def open_room(repo, out_dir):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(repo, "assets3d", "estilo", "01-mesa-ruleta.blend"))
    sc = build_room(os.path.abspath(repo))
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.abspath(out_dir), "sala-ruleta.blend"), copy=True)
    return sc


def main(repo, out_dir, percentage=100, samples=128):
    sc = open_room(repo, out_dir)
    return render(sc, out_dir, percentage, samples)


def main_panorama(repo, out_dir, width=3072, samples=32):
    sc = open_room(repo, out_dir)
    return panorama(sc, os.path.join(out_dir, f"sala-ruleta-panorama-{width}.png"), width, samples)
