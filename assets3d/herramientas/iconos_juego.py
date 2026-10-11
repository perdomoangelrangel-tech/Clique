"""Convierte el render de un juego (960×960, fondo transparente) en las dos imágenes que usa la app.

    python assets3d/herramientas/iconos_juego.py <render.png> <id_del_juego> [--dest static/casino-icons]

Escribe `<dest>/<id>.png` (480 px, pósters) y `<dest>/small/<id>.png` (128 px, mosaicos pequeños),
con el mismo nombre y formato que ya lee `static/js/art.js`: la app las toma sin tocar código.

Por qué así:
- Se renderiza al doble y se reduce con Lanczos: los bordes y las marcas finas salen limpios a 128 px.
- Se cuantiza a 256 colores con libimagequant (la de pngquant), que respeta la transparencia de la sombra
  suave. La cuantización de Pillow sola (octree) la convierte en una media luna dura.
- Presupuesto (equipo/contratos/arte3d.md y tests/test_arte.py): ≤ 100 KB a 480 px y ≤ 15 KB a 128 px.

Herramienta de E6, no de la app: necesita `pip install pillow==12.3.0 imagequant==1.1.5`. Con esas versiones
el resultado sale igual byte por byte.
"""
import argparse
import io
import os
import sys

from PIL import Image

try:
    import imagequant
except ImportError:  # pragma: no cover - mensaje para quien no la tenga
    sys.exit("Falta imagequant: pip install pillow==12.3.0 imagequant==1.1.5")

SIZES = {"": 480, "small": 128}           # subcarpeta → lado en px
BUDGET = {480: 100_000, 128: 15_000}      # bytes


def quantized_png(im: Image.Image) -> bytes:
    q = imagequant.quantize_pil_image(im, dithering_level=1.0, max_colors=256, min_quality=0, max_quality=100)
    out = io.BytesIO()
    q.save(out, "PNG", optimize=True)
    return out.getvalue()


def convert(render: str, game: str, dest: str) -> list[tuple[str, int, int]]:
    im = Image.open(render).convert("RGBA")
    if im.width != im.height:
        sys.exit(f"{render}: el render debe ser cuadrado (es {im.width}×{im.height})")
    done = []
    for folder, side in SIZES.items():
        data = quantized_png(im.resize((side, side), Image.LANCZOS))
        path = os.path.join(dest, folder, f"{game}.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        done.append((path, side, len(data)))
        if len(data) > BUDGET[side]:
            print(f"AVISO: {path} pesa {len(data):,} bytes; el presupuesto a {side} px es {BUDGET[side]:,}")
    return done


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("render")
    p.add_argument("game")
    p.add_argument("--dest", default="static/casino-icons")
    a = p.parse_args()
    for path, side, size in convert(a.render, a.game, a.dest):
        print(f"{path}: {side}×{side}, {size:,} bytes")


if __name__ == "__main__":
    main()
