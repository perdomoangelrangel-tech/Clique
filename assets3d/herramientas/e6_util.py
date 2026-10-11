"""Herramientas de E6 para las escenas de imágenes de juego en Blender (assets3d/juegos/juegos.blend).

Es la copia en el repositorio del bloque de texto `e6_util.py` de ese .blend: en Blender se carga con
`exec(bpy.data.texts["e6_util.py"].as_string())`. Si cambias una, cambia la otra.

- setup(): Cycles, AgX "Punchy", exposición -0.5, fondo transparente (equipo/contratos/arte3d.md §5 y §11).
- lights(): llave, cenital, contraluz y relleno escalados al tamaño del objeto.
- shadow_catcher(): el plano que guarda la sombra en la imagen transparente.
- camera(): encuadra el objeto al porcentaje pedido, con la elevación y el ángulo dados.
"""

import bpy, math, mathutils
from bpy_extras.object_utils import world_to_camera_view as w2c
KEY_COLOR = (1.0, 0.80, 0.58)

def world():
    w = bpy.data.worlds.get("W-juegos")
    if w is None:
        w = bpy.data.worlds.new("W-juegos"); w.use_nodes = True
        nt = w.node_tree; bg = nt.nodes["Background"]
        bg.inputs[0].default_value = (0.012, 0.009, 0.007, 1); bg.inputs[1].default_value = 1.0
    return w

def setup(sc, res=960, samples=128):
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.render.resolution_x = res; sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Punchy'; sc.view_settings.exposure = -0.5
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'; sc.render.image_settings.color_depth = '8'
    sc.world = world()
    sc.unit_settings.system = 'METRIC'

def collection(sc, name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name); sc.collection.children.link(c)
    return c

def bounds(objs, maxv=6000):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        if o.type != 'MESH' or o.hide_render: continue
        oe = o.evaluated_get(dg); me = oe.to_mesh()
        n = len(me.vertices); paso = max(1, n // maxv)
        mw = o.matrix_world
        pts += [mw @ me.vertices[i].co for i in range(0, n, paso)]
        oe.to_mesh_clear()
    lo = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi, pts

def light(sc, col, name, kind, energy, color, size, pos, target, spec=1.0):
    o = bpy.data.objects.get(name)
    if o is None:
        d = bpy.data.lights.new(name, kind); o = bpy.data.objects.new(name, d); col.objects.link(o)
    o.data.energy = energy; o.data.color = color
    if kind == 'AREA': o.data.size = size
    o.data.specular_factor = spec
    o.location = pos
    direction = (mathutils.Vector(target) - mathutils.Vector(pos))
    o.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return o

def lights(sc, col, center, r, k=1.5, prefix=''):
    c = mathutils.Vector(center)
    light(sc, col, f'LGT-{prefix}llave', 'AREA', 200*k*r*r, KEY_COLOR, 1.6*r, c + mathutils.Vector((-2.4*r, -0.4*r, 3.0*r)), c)
    light(sc, col, f'LGT-{prefix}cenital', 'AREA', 72*k*r*r, (1.0, 0.90, 0.76), 3.0*r, c + mathutils.Vector((0.3*r, -0.6*r, 4.0*r)), c)
    rl = light(sc, col, f'LGT-{prefix}contraluz', 'AREA', 100*k*r*r, (1.0, 0.86, 0.66), 0.5*r, c + mathutils.Vector((1.4*r, 2.6*r, 1.8*r)), c)
    f = light(sc, col, f'LGT-{prefix}relleno', 'AREA', 50*k*r*r, (1.0, 0.92, 0.80), 3.0*r, c + mathutils.Vector((2.8*r, -2.4*r, 1.2*r)), c, spec=0.4)
    f.data.use_shadow = False
    rl.data.use_shadow = False

def shadow_catcher(sc, col, z, center, r, prefix=''):
    n = f'GEO-{prefix}sombra'
    o = bpy.data.objects.get(n)
    if o is None:
        me = bpy.data.meshes.new(n)
        s = 1.0
        me.from_pydata([(-s,-s,0),(s,-s,0),(s,s,0),(-s,s,0)], [], [(0,1,2,3)])
        o = bpy.data.objects.new(n, me); col.objects.link(o)
    o.location = (center[0], center[1], z); o.scale = (8*r, 8*r, 1)
    o.is_shadow_catcher = True
    return o

def camera(sc, col, objs, elev=38, azim=-28, lens=70, fill=0.84, name='CAM-juego'):
    lo, hi, pts = bounds(objs)
    c = (lo + hi) / 2
    cam = bpy.data.objects.get(name)
    if cam is None:
        cd = bpy.data.cameras.new(name); cam = bpy.data.objects.new(name, cd); col.objects.link(cam)
    cam.data.lens = lens; cam.data.sensor_width = 36; cam.data.sensor_fit = 'HORIZONTAL'
    sc.camera = cam
    el, az = math.radians(elev), math.radians(azim)
    d = (hi - lo).length * 3
    for _ in range(30):
        direction = mathutils.Vector((math.sin(az)*math.cos(el), -math.cos(az)*math.cos(el), math.sin(el)))
        cam.location = c + direction * d
        cam.rotation_euler = (-direction).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.view_layer.update()
        ps = [w2c(sc, cam, p) for p in pts]
        xs = [p.x for p in ps]; ys = [p.y for p in ps]
        # centra el encuadre moviendo el punto de target
        cx = (min(xs)+max(xs))/2 - 0.5; cy = (min(ys)+max(ys))/2 - 0.5
        width = max(max(xs)-min(xs), max(ys)-min(ys))
        R = cam.matrix_world.to_3x3()
        w = 2 * d * math.tan(math.atan(18/lens))
        c = c + R @ mathutils.Vector((cx*w, cy*w, 0))
        d = d * width / fill
    return cam, (min(xs), max(xs), min(ys), max(ys))
