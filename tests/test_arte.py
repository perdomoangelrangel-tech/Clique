"""The pictures the app shows: every file is there, at its exact size, with a transparent background where it sits on a coloured
poster, and inside the budget of equipo/contratos/arte3d.md. Standard library only: the sizes are read from the file headers.

E6 · Arte 3D owns this file. The list of games is read from static/js/art.js, so a new game without its pictures fails here."""
import os
import re
import shutil
import struct
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "static")

# equipo/contratos/arte3d.md, sections 6 and 11
GAME_SIZES = {"": (480, 100_000), "small": (128, 15_000)}           # folder → (side in px, budget in bytes)
APP_RENDERS = {                                                     # static/renders → (width, height, budget in bytes)
    "fondo-mesa-1920x1080.webp": (1920, 1080, 150_000),
    "fondo-mesa-1080x2340.webp": (1080, 2340, 150_000),
    "icono-192.png": (192, 192, 100_000),
    "icono-512.png": (512, 512, 100_000),
    "icono-maskable-512.png": (512, 512, 100_000),
    "apple-touch-icon-180.png": (180, 180, 100_000),
}
MODEL_BUDGET = 300_000                                              # one model, bytes
MODEL_TRIANGLES = 8_000                                             # one model (section 6)
TEXTURE_SIDE = 1024                                                 # longest side of a texture inside a model (section 6)
FALLBACK_2D = (512, 512)                                            # the 2D stand-in of each live model
TOON_MODELS = ("ruleta.glb",)                                       # live models in the style of the drawings (section 13)


class LiveAnimations(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js no está instalado: se omite la prueba de la animación de la ruleta")
    def test_the_roulette_lands_on_the_number_the_server_sent(self):
        # the maths is pure JavaScript (docs/arte/ruleta-animacion.mjs); its own test checks all 37 numbers
        r = subprocess.run(["node", os.path.join("docs", "arte", "ruleta-animacion.test.mjs")], cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])


def _art_js():
    with open(os.path.join(STATIC, "js", "art.js"), encoding="utf-8") as f:
        return f.read()


def _map_keys(src, name):
    """The entries of `const <name> = { id: {...}, ... };` in art.js, as {id: body of its object}."""
    block = re.search(rf"const {name} = \{{(.*?)\n\}};", src, re.S)
    if not block:
        raise AssertionError(f"no encuentro `const {name} = {{…}};` en static/js/art.js")
    return dict(re.findall(r"(\w+)\s*:\s*\{([^}]*)\}", block.group(1)))


def games():
    """{id: file extension} from GAME_ICON in static/js/art.js, the one mapping the posters, the menu and the game headers use.
    A game whose picture is not a PNG says so with `ext` (art.js reads it the same way)."""
    out = {}
    for game, body in _map_keys(_art_js(), "GAME_ICON").items():
        ext = re.search(r"ext\s*:\s*['\"](\w+)['\"]", body)
        out[game] = ext.group(1) if ext else "png"
    return out


def game_ids():
    return list(games())


def png_info(path):
    """(width, height, has_alpha) from the PNG header; alpha is an RGBA/grey+alpha image or a palette with a tRNS chunk."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"{path} no es un PNG")
    width, height = struct.unpack(">II", data[16:24])
    color_type = data[25]
    alpha = color_type in (4, 6)
    pos = 8
    while pos < len(data) and not alpha:                            # walk the chunks looking for tRNS before the image data
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"tRNS":
            alpha = True
        if kind == b"IDAT":
            break
        pos += 12 + length
    return width, height, alpha


def webp_size(path):
    """(width, height) of a WebP: simple lossy (VP8), lossless (VP8L) or extended (VP8X)."""
    with open(path, "rb") as f:
        data = f.read(40)
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise AssertionError(f"{path} no es un WebP")
    kind = data[12:16]
    if kind == b"VP8X":
        return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    if kind == b"VP8 ":
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if kind == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return 1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF)
    raise AssertionError(f"{path}: WebP de tipo {kind!r} desconocido")


def image_size(path):
    return png_info(path)[:2] if path.endswith(".png") else webp_size(path)


class GamePictures(unittest.TestCase):
    def test_the_list_of_games_comes_from_the_app(self):
        src = _art_js()
        icons, posters = set(_map_keys(src, "GAME_ICON")), set(_map_keys(src, "POSTER"))
        self.assertTrue(icons, "GAME_ICON está vacío")
        self.assertEqual(icons, posters, "GAME_ICON y POSTER de static/js/art.js no tienen los mismos juegos")

    def test_every_game_has_both_pictures_at_their_size_with_a_transparent_background(self):
        for game, ext in games().items():
            for folder, (side, _) in GAME_SIZES.items():
                path = os.path.join(STATIC, "casino-icons", folder, f"{game}.{ext}")
                rel = os.path.relpath(path, ROOT)
                with self.subTest(game=game, size=side):
                    self.assertTrue(os.path.exists(path), f"falta {rel}")
                    self.assertEqual(image_size(path), (side, side), f"{rel} no mide {side}×{side}")
                    if ext == "png":
                        # the corners are the poster's colour showing through: they must be fully transparent
                        self.assertEqual(corner_alphas(path), [0, 0, 0, 0], f"{rel} no tiene fondo transparente: va sobre el color del póster")
                    else:
                        self.assertTrue(webp_has_alpha(path), f"{rel} no tiene fondo transparente")

    def test_every_game_picture_fits_its_budget(self):
        for game, ext in games().items():
            for folder, (side, budget) in GAME_SIZES.items():
                path = os.path.join(STATIC, "casino-icons", folder, f"{game}.{ext}")
                if not os.path.exists(path):
                    continue                                        # the test above already says it is missing
                with self.subTest(game=game, size=side):
                    self.assertLessEqual(os.path.getsize(path), budget, f"{os.path.relpath(path, ROOT)} pasa del presupuesto de {budget:,} bytes")


class AppRenders(unittest.TestCase):
    def test_every_render_is_there_at_its_size_and_inside_its_budget(self):
        for name, (width, height, budget) in APP_RENDERS.items():
            path = os.path.join(STATIC, "renders", name)
            with self.subTest(name=name):
                self.assertTrue(os.path.exists(path), f"falta static/renders/{name}")
                self.assertEqual(image_size(path), (width, height), f"static/renders/{name} no mide {width}×{height}")
                self.assertLessEqual(os.path.getsize(path), budget, f"static/renders/{name} pasa del presupuesto de {budget:,} bytes")

    def test_nothing_else_lands_in_the_folder_without_its_row_here(self):
        # a new render needs its size and budget written down (here and in the contract, section 11) before it ships
        extra = sorted(set(os.listdir(os.path.join(STATIC, "renders"))) - set(APP_RENDERS))
        self.assertEqual(extra, [], "archivos en static/renders sin fila en APP_RENDERS ni en equipo/contratos/arte3d.md §11")

    def test_the_app_icons_have_no_transparent_corners(self):
        # Android and iOS put a transparent icon on white or black on their own: the club's dark room has to be in the file.
        for name in ("icono-192.png", "icono-512.png", "icono-maskable-512.png", "apple-touch-icon-180.png"):
            path = os.path.join(STATIC, "renders", name)
            if not os.path.exists(path):
                continue
            with self.subTest(name=name):
                self.assertEqual(corner_alphas(path), [255] * 4, f"static/renders/{name} tiene esquinas transparentes")


class LiveModels(unittest.TestCase):
    def test_every_model_is_a_glb_inside_its_budget_with_its_2d_stand_ins(self):
        folder = os.path.join(STATIC, "3d")
        models = [n for n in os.listdir(folder) if n.endswith(".glb")]
        self.assertTrue(models, "no hay modelos en static/3d")
        for name in models:
            path = os.path.join(folder, name)
            with self.subTest(model=name):
                with open(path, "rb") as f:
                    self.assertEqual(f.read(4), b"glTF", f"static/3d/{name} no es un GLB")
                self.assertLessEqual(os.path.getsize(path), MODEL_BUDGET, f"static/3d/{name} pasa de {MODEL_BUDGET:,} bytes")
                stem = name[:-4]
                stand_ins = [n for n in os.listdir(folder) if n.startswith(stem + "-") and n.endswith("-2d.webp")]
                self.assertTrue(stand_ins, f"static/3d/{name} no tiene su versión 2D ({stem}-<variante>-2d.webp)")
                for s in stand_ins:
                    self.assertEqual(webp_size(os.path.join(folder, s)), FALLBACK_2D, f"static/3d/{s} no mide 512×512")
                    self.assertTrue(webp_has_alpha(os.path.join(folder, s)), f"static/3d/{s} no tiene fondo transparente (contrato §5)")


def read_glb(path):
    """(json dict, binary chunk) of a GLB, from the standard library: the JSON says how many triangles and which
    pictures there are even when the geometry is compressed with meshopt."""
    import json
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        raise AssertionError(f"{path} no es un GLB")
    length, kind = struct.unpack("<I4s", data[12:20])
    doc = json.loads(data[20:20 + length])
    pos = 20 + length
    binary = b""
    if pos < len(data):
        blength, bkind = struct.unpack("<I4s", data[pos:pos + 8])
        binary = data[pos + 8:pos + 8 + blength]
    return doc, binary


def glb_triangles(doc):
    """Triangles of every mesh, the way assets3d/herramientas/optimizar-glb.mjs counts them."""
    n = 0
    for mesh in doc.get("meshes", []):
        for prim in mesh["primitives"]:
            acc = prim.get("indices", prim["attributes"]["POSITION"])
            n += doc["accessors"][acc]["count"] // 3
    return n


def glb_images(doc, binary):
    """{name: (width, height)} of every picture packed in the GLB."""
    out = {}
    for i, image in enumerate(doc.get("images", [])):
        view = doc["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)
        blob = binary[start:start + view["byteLength"]]
        name = image.get("name", f"imagen {i}")
        if blob[:8] == b"\x89PNG\r\n\x1a\n":
            out[name] = struct.unpack(">II", blob[16:24])
        else:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as t:
                t.write(blob[:64])
            try:
                out[name] = webp_size(t.name)
            finally:
                os.unlink(t.name)
    return out


def glb_accessor(doc, binary, index):
    """The values of an accessor as tuples of floats (FLOAT) or ints (indices), from an uncompressed GLB."""
    acc = doc["accessors"][index]
    view = doc["bufferViews"][acc["bufferView"]]
    fmt = {5126: "f", 5125: "I", 5123: "H", 5121: "B"}[acc["componentType"]]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
    size = struct.calcsize("<" + fmt) * width
    stride = view.get("byteStride", size)
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    return [struct.unpack_from("<" + fmt * width, binary, start + i * stride) for i in range(acc["count"])]


class LiveModelBudgets(unittest.TestCase):
    def test_every_model_fits_the_triangle_and_texture_budget(self):
        folder = os.path.join(STATIC, "3d")
        for name in sorted(n for n in os.listdir(folder) if n.endswith(".glb")):
            doc, binary = read_glb(os.path.join(folder, name))
            with self.subTest(model=name):
                self.assertLessEqual(glb_triangles(doc), MODEL_TRIANGLES, f"static/3d/{name} pasa de {MODEL_TRIANGLES:,} triángulos")
                for image, (w, h) in glb_images(doc, binary).items():
                    self.assertLessEqual(max(w, h), TEXTURE_SIDE, f"static/3d/{name}: la textura {image} mide {w} × {h}; el tope es {TEXTURE_SIDE} px")


ROOM_BUDGET = 600_000                                               # one room panorama, bytes (equipo/contratos/arte3d.md §6, §14)
ROOM_SIDE = 4096                                                    # widest panorama: 4096 × 2048 is 32 MB on the phone's GPU


class Rooms(unittest.TestCase):
    """The rooms of the games (section 14): a panorama of the hall per room, seen from where the live camera stands."""

    def test_every_room_is_a_full_panorama_inside_its_budget(self):
        folder = os.path.join(STATIC, "3d", "salas")
        rooms = sorted(n for n in os.listdir(folder) if n.endswith(".webp")) if os.path.isdir(folder) else []
        self.assertIn("ruleta.webp", rooms, "falta la sala de ruleta: static/3d/salas/ruleta.webp")
        for name in rooms:
            path = os.path.join(folder, name)
            with self.subTest(room=name):
                w, h = webp_size(path)
                self.assertEqual(w, 2 * h, f"static/3d/salas/{name} mide {w} × {h}: un panorama mide el doble de ancho que de alto")
                self.assertGreaterEqual(w, 2048, f"static/3d/salas/{name} es muy chico para verse en la mesa")
                self.assertLessEqual(w, ROOM_SIDE, f"static/3d/salas/{name} mide {w} px de ancho; el tope es {ROOM_SIDE} (memoria del celular)")
                self.assertLessEqual(os.path.getsize(path), ROOM_BUDGET, f"static/3d/salas/{name} pasa de {ROOM_BUDGET:,} bytes")

    def test_the_web_camera_stands_where_blender_rendered_the_room(self):
        # if the two points differ, the live wheel slides off its table in the panorama
        with open(os.path.join(ROOT, "assets3d", "herramientas", "sala_ruleta.py"), encoding="utf-8") as f:
            x, y, z = (float(v) for v in re.search(r"VIEW_OFFSET = \(([^)]*)\)", f.read()).group(1).split(","))
        with open(os.path.join(ROOT, "docs", "arte", "sala-ruleta.mjs"), encoding="utf-8") as f:
            web = [float(v) for v in re.search(r"VIEW = new THREE\.Vector3\(([^)]*)\)", f.read()).group(1).split(",")]
        for a, b in zip(web, (x, z, -y)):                            # Blender (x, y, z) → three.js (x, z, -y)
            self.assertAlmostEqual(a, b, places=6, msg="VIEW de docs/arte/sala-ruleta.mjs no es VIEW_OFFSET de sala_ruleta.py")


def _palette(path, pattern):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return {k: (lit.upper(), shade.upper()) for k, lit, shade in re.findall(pattern, f.read())}


class ToonStyle(unittest.TestCase):
    """The style of the drawings (equipo/contratos/arte3d.md, section 13): the same colours in Blender and on the web."""

    def test_the_palette_is_the_same_in_blender_and_on_the_web(self):
        blender = _palette("assets3d/herramientas/e6_toon.py", r'"(\w+)": \("(#[0-9A-Fa-f]{6})", "(#[0-9A-Fa-f]{6})"\)')
        web = _palette("docs/arte/estilo-toon.mjs", r"(\w+): \['(#[0-9A-Fa-f]{6})', '(#[0-9A-Fa-f]{6})'\]")
        self.assertTrue(blender, "no encuentro PALETTE en assets3d/herramientas/e6_toon.py")
        self.assertEqual(blender, web, "la paleta de e6_toon.py y la de docs/arte/estilo-toon.mjs no son iguales")

    def test_every_material_of_a_toon_model_is_a_palette_colour_or_a_picture(self):
        keys = _palette("docs/arte/estilo-toon.mjs", r"(\w+): \['(#[0-9A-Fa-f]{6})', '(#[0-9A-Fa-f]{6})'\]")
        for name in TOON_MODELS:
            doc, _ = read_glb(os.path.join(STATIC, "3d", name))
            for mat in doc.get("materials", []):
                with self.subTest(model=name, material=mat.get("name")):
                    picture = "baseColorTexture" in mat.get("pbrMetallicRoughness", {})
                    colour = any(mat.get("name", "").endswith("_" + k) for k in keys)
                    self.assertTrue(picture or colour, f"static/3d/{name}: el material {mat.get('name')!r} no termina en _<color de la paleta> ni lleva textura: la web lo pintaría de otro color")


def _js_list(path, name):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return [int(x) for x in re.search(rf"{name} = \[([^\]]*)\]", f.read()).group(1).replace("\n", " ").split(",") if x.strip()]


class RouletteModel(unittest.TestCase):
    """The live roulette agrees with the animation (docs/arte/ruleta-animacion.mjs) and with the bets of the server
    (backend/games.py): every pocket has its colour, every number is over its pocket and the ball is the animation's.
    Read from the raw export, whose geometry is not compressed."""

    @classmethod
    def setUpClass(cls):
        cls.doc, cls.bin = read_glb(os.path.join(ROOT, "assets3d", "juegos", "ruleta-exportada.glb"))
        cls.order = _js_list("docs/arte/ruleta-animacion.mjs", "WHEEL_ORDER")
        with open(os.path.join(ROOT, "backend", "games.py"), encoding="utf-8") as f:
            cls.reds = {int(x) for x in re.search(r"REDS = \{([^}]*)\}", f.read()).group(1).split(",")}
        with open(os.path.join(ROOT, "docs", "arte", "ruleta-animacion.mjs"), encoding="utf-8") as f:
            cls.ball_radius = float(re.search(r"BALL_RADIUS = ([\d.]+)", f.read()).group(1))
        with open(os.path.join(ROOT, "assets3d", "herramientas", "ruleta_numeros.py"), encoding="utf-8") as f:
            cls.cells = int(re.search(r"^CELLS = (\d+)", f.read(), re.M).group(1))

    def mesh(self, node_name):
        node = next(n for n in self.doc["nodes"] if n.get("name") == node_name)
        return self.doc["meshes"][node["mesh"]]

    def triangles(self, prim):
        pos = glb_accessor(self.doc, self.bin, prim["attributes"]["POSITION"])
        idx = [i[0] for i in glb_accessor(self.doc, self.bin, prim["indices"])]
        return pos, [idx[k:k + 3] for k in range(0, len(idx), 3)]

    def slot(self, points):
        """The wheel's slot j under the centre of some points (glTF Y up, so Blender's angle is atan2(-z, x))."""
        import math
        x = sum(p[0] for p in points) / len(points)
        z = sum(p[2] for p in points) / len(points)
        a = math.atan2(-z, x) % (2 * math.pi)
        width = 2 * math.pi / len(self.order)
        return int(a // width), (a % width) / width

    def colour(self, n):
        return "lime" if n == 0 else "verm" if n in self.reds else "ink"

    def test_the_web_model_comes_from_this_export(self):
        # static/3d/ruleta.glb is assets3d/juegos/ruleta-exportada.glb optimized: same meshes, same triangles
        web, _ = read_glb(os.path.join(STATIC, "3d", "ruleta.glb"))
        per_mesh = lambda doc: sorted((m.get("name", ""), glb_triangles({"meshes": [m], "accessors": doc["accessors"]})) for m in doc["meshes"])
        self.assertEqual(per_mesh(web), per_mesh(self.doc), "static/3d/ruleta.glb no sale de la exportación cruda: vuelve a correr optimizar-glb.mjs")

    def test_the_ball_is_the_size_of_the_animation(self):
        prim = self.mesh("GEO-ruleta_bola")["primitives"][0]
        pos = glb_accessor(self.doc, self.bin, prim["attributes"]["POSITION"])
        radius = max((x * x + y * y + z * z) ** 0.5 for x, y, z in pos)
        self.assertAlmostEqual(radius, self.ball_radius, delta=1e-4, msg="la bola del modelo no mide lo que la animación (BALL_RADIUS)")

    def test_every_pocket_has_the_colour_of_its_number(self):
        wrong = []
        for prim in self.mesh("GEO-ruleta_casillas")["primitives"]:
            mat = self.doc["materials"][prim["material"]]["name"].rsplit("_", 1)[-1]
            pos, tris = self.triangles(prim)
            for t in tris:
                j, _ = self.slot([pos[i] for i in t])
                n = self.order[len(self.order) - 1 - j]
                if self.colour(n) != mat:
                    wrong.append((n, mat))
        self.assertEqual(wrong, [], "casillas con el color equivocado (número, color del modelo)")

    def test_every_number_sits_over_its_pocket(self):
        prim = self.mesh("GEO-ruleta_numeros")["primitives"][0]
        pos, tris = self.triangles(prim)
        uv = glb_accessor(self.doc, self.bin, prim["attributes"]["TEXCOORD_0"])
        worst = 0.0
        for t in tris:
            j, frac = self.slot([pos[i] for i in t])
            row, col = divmod(j, self.cells)
            u = sum(uv[i][0] for i in t) / 3
            v = sum(uv[i][1] for i in t) / 3                     # glTF: v grows down the picture
            worst = max(worst, abs(u - (col + frac) / self.cells))
            self.assertEqual(int(v >= 0.5), row, f"el tramo {j} lee la fila equivocada de la tira de números")
        self.assertLess(worst, 0.02 / self.cells, "el anillo de números no cae sobre sus casillas")

    def test_the_strip_paints_each_cell_with_the_colour_of_its_number(self):
        path = os.path.join(ROOT, "assets3d", "texturas", "ruleta-numeros.png")
        rows, width, height, bpp = png_rows(path)
        cell = width / self.cells
        row_h = (height - 4) // 2                                     # two rows with 4 px of paper between them
        hexes = {"lime": (0xC6, 0xF4, 0x32), "verm": (0xFF, 0x4B, 0x2B), "ink": (0x1A, 0x16, 0x12)}
        wrong = []
        for j in range(len(self.order)):
            row, col = divmod(j, self.cells)
            x, y = int(col * cell + 5), int(row * (row_h + 4) + 4)    # inside the cell, clear of the line and the digits
            px = tuple(rows[y][x * bpp:x * bpp + 3])
            n = self.order[len(self.order) - 1 - j]
            if max(abs(a - b) for a, b in zip(px, hexes[self.colour(n)])) > 6:
                wrong.append((j, n, px))
        self.assertEqual(wrong, [], "celdas de la tira con otro color que el de su número (tramo, número, color)")


def png_rows(path):
    """Rows of an 8-bit PNG, decoded with zlib from the standard library: (rows, width, height, bytes per pixel)."""
    import zlib
    with open(path, "rb") as f:
        data = f.read()
    width, height = struct.unpack(">II", data[16:24])
    bit_depth, color_type = data[24], data[25]
    if bit_depth != 8:
        raise AssertionError(f"{os.path.relpath(path, ROOT)}: profundidad de {bit_depth} bits; las imágenes de la app son de 8")
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    pos, idat = 8, b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * bpp + 1
    rows, prev = [], bytearray(width * bpp)
    for y in range(height):                                         # undo the PNG row filters
        f, line = raw[y * stride], bytearray(raw[y * stride + 1:(y + 1) * stride])
        for x in range(len(line)):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return rows, width, height, bpp


def corner_alphas(path):
    """The alpha (0-255) of the four corner pixels of an 8-bit PNG, decoded with zlib from the standard library."""
    import zlib
    with open(path, "rb") as f:
        data = f.read()
    width, height = struct.unpack(">II", data[16:24])
    bit_depth, color_type = data[24], data[25]
    if bit_depth != 8:
        raise AssertionError(f"{os.path.relpath(path, ROOT)}: profundidad de {bit_depth} bits; las imágenes de la app son de 8")
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    pos, idat, trns = 8, b"", b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IDAT":
            idat += body
        elif kind == b"tRNS":
            trns = body
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * bpp + 1
    rows, prev = [], bytearray(width * bpp)
    for y in range(height):                                         # undo the PNG row filters
        f, line = raw[y * stride], bytearray(raw[y * stride + 1:(y + 1) * stride])
        for x in range(len(line)):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line

    def alpha(px):
        if color_type == 3:
            return trns[px[0]] if px[0] < len(trns) else 255
        if color_type in (4, 6):
            return px[-1]
        return 255                                                  # grey or RGB without alpha (a tRNS colour key is not used here)

    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    return [alpha(rows[y][x * bpp:(x + 1) * bpp]) for x, y in corners]


def webp_has_alpha(path):
    """True when a WebP carries transparency: the alpha flag of VP8X, or the alpha hint of lossless VP8L."""
    with open(path, "rb") as f:
        data = f.read(30)
    kind = data[12:16]
    if kind == b"VP8X":
        return bool(data[20] & 0x10)
    if kind == b"VP8L":
        return bool((int.from_bytes(data[21:25], "little") >> 28) & 1)
    return False


if __name__ == "__main__":
    unittest.main()
