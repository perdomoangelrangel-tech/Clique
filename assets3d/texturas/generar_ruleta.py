"""Texturas de la ruleta para el cuadro de estilo 1 (OT-006).

Uso:  python generar_ruleta.py <carpeta_de_trabajo>   (mismas fuentes que generar_texturas.py)

ruleta_pano.png     tapete de apuestas impreso sobre fieltro (RGBA, solo la tinta)
ruleta_anillo.png   tira de 37 sectores para el rotor: arriba números, abajo bolsas
Colores de la paleta v2: papel #EFE6D2, bermellón-700 #B8200A, tinta #1A1612,
fieltro-2 #2F6B47, oro-400 #FBB635.
"""
import math, os, sys
from PIL import Image, ImageDraw, ImageFont

SP = sys.argv[1]
F = lambda n, s: ImageFont.truetype(f"{SP}/fonts/{n}.ttf", s)
PAPER = (239, 230, 210); VERM700 = (184, 32, 10); INK = (26, 22, 18)
FELT2 = (47, 107, 71); ORO = (251, 182, 53)
ROJOS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
RUEDA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16,
         33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
OUT = f"{SP}/tex"


def color_de(n):
    return FELT2 if n == 0 else (VERM700 if n in ROJOS else INK)


def centrado(d, cx, cy, txt, font, fill, angle=0, im=None):
    if angle == 0:
        d.text((cx, cy), txt, font=font, fill=fill, anchor="mm")
        return
    w = int(font.size * 3); tmp = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((w / 2, w / 2), txt, font=font, fill=fill, anchor="mm")
    tmp = tmp.rotate(angle, resample=Image.BICUBIC)
    im.alpha_composite(tmp, (int(cx - w / 2), int(cy - w / 2)))


def pano():
    SS = 2
    W, H = 2400 * SS, 1000 * SS
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lw = 5 * SS
    x0, y0 = 60 * SS, 60 * SS
    cw, ch = 150 * SS, 170 * SS            # celda de número
    zw = 170 * SS                          # celda del cero
    gx = x0 + zw                           # inicio de la cuadrícula
    gy = y0
    # cero: pentágono con punta a la izquierda
    zp = [(gx, gy), (gx, gy + 3 * ch), (x0 + 40 * SS, gy + 3 * ch), (x0, gy + 1.5 * ch), (x0 + 40 * SS, gy)]
    d.polygon(zp, fill=FELT2 + (235,), outline=PAPER + (230,), width=lw)
    centrado(d, (x0 + gx) / 2 + 10 * SS, gy + 1.5 * ch, "0", F("bricolage-800", 96 * SS), PAPER + (240,))
    numf = F("bricolage-800", 80 * SS)
    for col in range(12):
        for row in range(3):
            n = col * 3 + (3 - row)
            x = gx + col * cw; y = gy + row * ch
            d.rectangle([x, y, x + cw, y + ch], outline=PAPER + (230,), width=lw)
            r = 52 * SS
            d.ellipse([x + cw / 2 - r * 1.05, y + ch / 2 - r, x + cw / 2 + r * 1.05, y + ch / 2 + r], fill=color_de(n) + (235,))
            centrado(d, x + cw / 2, y + ch / 2, str(n), numf, PAPER + (245,))
    # columna "2 a 1"
    xc = gx + 12 * cw
    smallf = F("instrument-600", 44 * SS)
    for row in range(3):
        y = gy + row * ch
        d.rectangle([xc, y, xc + cw, y + ch], outline=PAPER + (230,), width=lw)
        centrado(d, xc + cw / 2, y + ch / 2, "2 a 1", smallf, PAPER + (235,))
    # docenas
    yd = gy + 3 * ch; dh = 120 * SS
    labf = F("instrument-600", 54 * SS)
    for k, txt in enumerate(["1ª docena", "2ª docena", "3ª docena"]):
        x = gx + k * 4 * cw
        d.rectangle([x, yd, x + 4 * cw, yd + dh], outline=PAPER + (230,), width=lw)
        centrado(d, x + 2 * cw, yd + dh / 2, txt, labf, PAPER + (235,))
    # suertes sencillas
    ys = yd + dh; sh = 120 * SS
    etiquetas = ["1 a 18", "Par", "ROJO", "NEGRO", "Impar", "19 a 36"]
    for k, txt in enumerate(etiquetas):
        x = gx + k * 2 * cw
        d.rectangle([x, ys, x + 2 * cw, ys + sh], outline=PAPER + (230,), width=lw)
        cx, cy = x + cw, ys + sh / 2
        if txt in ("ROJO", "NEGRO"):
            col = VERM700 if txt == "ROJO" else INK
            rx, ry = 95 * SS, 42 * SS
            d.polygon([(cx - rx, cy), (cx, cy - ry), (cx + rx, cy), (cx, cy + ry)], fill=col + (240,), outline=PAPER + (230,))
        else:
            centrado(d, cx, cy, txt, labf, PAPER + (235,))
    # filete de oro alrededor de todo
    pad = 22 * SS
    d.rounded_rectangle([x0 - pad, y0 - pad, xc + cw + pad, ys + sh + pad], radius=30 * SS, outline=ORO + (210,), width=3 * SS)
    # marca de la casa, discreta, en papel
    centrado(d, (xc + cw + pad + W) / 2 - 10 * SS, gy + 1.5 * ch, "CLIQUE", F("bricolage-800", 70 * SS), PAPER + (120,), angle=90, im=im)
    im = im.resize((W // SS, H // SS), Image.LANCZOS)
    im.save(f"{OUT}/ruleta_pano.png")
    return im.size


def anillo():
    SS = 2
    W, H = 4070 * SS, 360 * SS            # 37 sectores de 110 px
    sw = W / 37
    im = Image.new("RGBA", (W, H), INK + (255,)); d = ImageDraw.Draw(im)
    numf = F("bricolage-800", 70 * SS)
    for i, n in enumerate(RUEDA):
        x = i * sw
        d.rectangle([x, 0, x + sw, H], fill=color_de(n) + (255,))
        # banda de números (mitad de arriba = borde exterior del anillo)
        centrado(d, x + sw / 2, H * 0.25, str(n), numf, PAPER + (255,))
        # separador fino de oro entre números
        d.line([(x, 0), (x, H * 0.5)], fill=ORO + (255,), width=3 * SS)
    d.line([(0, H * 0.5), (W, H * 0.5)], fill=ORO + (255,), width=4 * SS)
    im = im.resize((W // SS, H // SS), Image.LANCZOS)
    im.convert("RGB").save(f"{OUT}/ruleta_anillo.png")
    return im.size


if __name__ == "__main__":
    print("pano", pano())
    print("anillo", anillo())
