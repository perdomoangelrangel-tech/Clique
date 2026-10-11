"""The pictures the app shows: every file is there, at its exact size, with a transparent background where it sits on a coloured
poster, and inside the budget of equipo/contratos/arte3d.md. Standard library only: the sizes are read from the file headers.

E6 · Arte 3D owns this file. The list of games is read from static/js/art.js, so a new game without its pictures fails here."""
import os
import re
import struct
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
FALLBACK_2D = (512, 512)                                            # the 2D stand-in of each live model


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
