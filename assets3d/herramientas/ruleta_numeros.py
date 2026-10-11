"""Dibuja el anillo de números de la ruleta en vivo (estilo del dibujo): las 37 casillas que el modelo envuelve
alrededor del rotor. La lee assets3d/herramientas/ruleta_toon.py desde Blender.

    python assets3d/herramientas/ruleta_numeros.py <fuente.ttf> assets3d/texturas/ruleta-numeros.png

La fuente es Bricolage Grotesque 800 de static/fonts (pasada a .ttf con fontTools, porque Pillow no lee woff2).

Cómo se lee (equipo/contratos/arte3d.md §9, §12 y §13):
- La rueda va en tramos de 2π/37. El tramo j (de 2πj/37 a 2π(j+1)/37, en sentido antihorario visto desde arriba) es
  la casilla en la posición k = 36 - j del orden de la rueda: la misma cuenta que pocketAngle en
  docs/arte/ruleta-animacion.mjs.
- Las texturas miden 1024 px como máximo (§6), así que la tira va en dos filas de 19 celdas: los tramos 0 a 18 en la
  de arriba y los 19 a 36 en la de abajo (su última celda queda vacía). Entre las filas hay una franja de papel para
  que el filtrado de una no manche la otra.
- En cada fila, arriba es el borde de adentro del anillo: los números se leen derechos desde afuera de la rueda.
- Rojo → bermellón, negro → tinta y el 0 → lima, con los colores exactos de la paleta. Los números van en papel
  (en tinta sobre el lima) y una raya de papel separa cada casilla, alineada con los trastes.
"""
import math
import sys

from PIL import Image, ImageDraw, ImageFont

WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
               22, 18, 29, 7, 28, 12, 35, 3, 26]
REDS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}   # backend/games.py
CREAM, INK, LIME, VERM = "#EFE6D2", "#1A1612", "#C6F432", "#FF4B2B"
RING_IN, RING_OUT = 0.264, 0.303           # radios del anillo en el modelo (m)
WIDTH = 1024                               # tope de textura del contrato (§6)
CELLS = 19                                 # celdas por fila: 19 + 18 = 37
GAP = 4                                    # px de papel entre las dos filas
SCALE = 4                                  # se dibuja al cuádruple y se reduce: bordes limpios


def row_height():
    """Rows of nearly square texels at the middle of the ring: a cell is 2π·mid/37 m wide and RING_OUT-RING_IN tall."""
    mid = (RING_IN + RING_OUT) / 2
    return round((WIDTH / CELLS) * (RING_OUT - RING_IN) / (2 * math.pi * mid / 37))


def layout():
    """(width, height, row height, gap) of the strip, shared with ruleta_toon.py for the UVs."""
    h = row_height()
    return WIDTH, 2 * h + GAP, h, GAP


def colors(n):
    if n == 0:
        return LIME, INK
    return (VERM, CREAM) if n in REDS else (INK, CREAM)


def draw(font_path, out):
    width, height, h, gap = layout()
    W, H, RH = width * SCALE, height * SCALE, h * SCALE
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)
    cell = W / CELLS
    font = ImageFont.truetype(font_path, round(RH * 0.74))
    line = max(1, round(1.5 * SCALE))
    for j in range(37):
        n = WHEEL_ORDER[36 - j]
        row, col = divmod(j, CELLS)
        y0 = row * (RH + gap * SCALE)
        x0, x1 = col * cell, (col + 1) * cell
        bg, fg = colors(n)
        d.rectangle([round(x0) + line, y0, round(x1) - line, y0 + RH - 1], fill=bg)
        d.text(((x0 + x1) / 2, y0 + RH * 0.48), str(n), fill=fg, font=font, anchor="mm")
    im = im.resize((width, height), Image.LANCZOS)
    im.save(out, optimize=True)
    return im.size


if __name__ == "__main__":
    print(draw(sys.argv[1], sys.argv[2]))
