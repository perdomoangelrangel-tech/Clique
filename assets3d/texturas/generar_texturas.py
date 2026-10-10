"""Texturas de los cuadros de estilo de OT-006: caras y reverso de cartas, boleto de papel y pósters.

Uso:  python generar_texturas.py <carpeta_de_trabajo> <legacy/clique/static/casino-icons>
La carpeta de trabajo debe tener fonts/ con estas fuentes en .ttf (convertidas desde los
.woff2 de legacy/clique/static/fonts con fontTools): bricolage-700, bricolage-800,
instrument-500, instrument-600, jbmono-500, jbmono-700. Escribe en <carpeta>/tex/.
Colores: paleta v2 (OT-003). Las texturas ya van empacadas dentro de los .blend; esta versión
usa semillas fijas, así que dos corridas dan el mismo archivo (la primera versión, con la que se
hicieron los renders, tenía un ruido de papel distinto en cada corrida).
"""
import math, os, sys, random, zlib
from PIL import Image, ImageDraw, ImageFont, ImageFilter
SP = sys.argv[1]; ICONS = sys.argv[2]
F = lambda n, s: ImageFont.truetype(f"{SP}/fonts/{n}.ttf", s)
INK=(26,22,18); PAPER=(239,230,210); PAPER50=(251,246,233); MUTE=(90,78,60); LINE=(179,165,130)
VERM700=(184,32,10); VERM=(255,75,43); LIME=(198,244,50); FELT=(30,59,44); FELT2=(47,107,71); ORO=(251,182,53); ORO600=(187,131,7); SALA=(20,17,16); SALA0=(14,12,10)
OUT=f"{SP}/tex"; os.makedirs(OUT, exist_ok=True)

def heart_pts(cx, cy, s, flip=False, n=240):
    pts=[]
    for i in range(n):
        t=2*math.pi*i/n
        x=16*math.sin(t)**3
        y=13*math.cos(t)-5*math.cos(2*t)-2*math.cos(3*t)-math.cos(4*t)
        y=-y if not flip else y
        pts.append((cx+x*s, cy+y*s))
    return pts

def draw_heart(d, cx, cy, s, fill):
    d.polygon(heart_pts(cx, cy, s), fill=fill)

def draw_spade(d, cx, cy, s, fill):
    # inverted heart (point up) + stem
    d.polygon(heart_pts(cx, cy - 2*s, s, flip=True), fill=fill)
    top=cy+4*s; h=16*s; pts=[]
    n=24
    for i in range(n+1):
        t=i/n; y=top+h*t; half=1.4*s+ (7.5*s-1.4*s)*(t**2.2)
        pts.append((cx+half, y))
    for i in range(n,-1,-1):
        t=i/n; y=top+h*t; half=1.4*s+ (7.5*s-1.4*s)*(t**2.2)
        pts.append((cx-half, y))
    d.polygon(pts, fill=fill)
    return (cx, top, 0, h)

def logo_c(d, cx, cy, r, stroke, color, dot=True):
    # the Clique "C": an open arc (gap on the right) plus a dot in the gap
    bbox=[cx-r, cy-r, cx+r, cy+r]
    d.arc(bbox, start=40, end=320, fill=color, width=stroke)
    # round caps
    for ang in (40, 320):
        a=math.radians(ang); px=cx+(r-stroke/2)*math.cos(a); py=cy+(r-stroke/2)*math.sin(a)
        d.ellipse([px-stroke/2, py-stroke/2, px+stroke/2, py+stroke/2], fill=color)
    if dot:
        dr=stroke*0.62; dx=cx+r*0.95; d.ellipse([dx-dr, cy-dr, dx+dr, cy+dr], fill=color)

def paper(size, base, grain=6, seed=1):
    # Ruido de papel reproducible: Image.effect_noise no acepta semilla, así que se arma con random.
    rnd=random.Random(seed)
    im=Image.new("RGB", size, base)
    small=(max(1,size[0]//4), max(1,size[1]//4))
    noise=Image.frombytes("L", small, bytes(int(max(0,min(255,rnd.gauss(128, grain*4)))) for _ in range(small[0]*small[1])))
    noise=noise.resize(size, Image.BILINEAR)
    noise=noise.point(lambda v: 128+(v-128)*0.25)
    im=Image.blend(im, Image.merge("RGB",(noise,noise,noise)), 0.06)
    return im

def card_face(rank, suit, color, fname):
    SS=2; W,H=1260*SS,1760*SS
    im=paper((W,H), PAPER50, seed=zlib.crc32(fname.encode())%999)
    d=ImageDraw.Draw(im)
    m=80*SS
    d.rounded_rectangle([m,m,W-m,H-m], radius=40*SS, outline=LINE, width=3*SS)
    d.rounded_rectangle([m+14*SS,m+14*SS,W-m-14*SS,H-m-14*SS], radius=30*SS, outline=LINE, width=1*SS)
    # corner index
    fr=F("bricolage-800", 210*SS)
    def index(img):
        dd=ImageDraw.Draw(img)
        dd.text((118*SS, 96*SS), rank, font=fr, fill=color)
        sx, sy = 168*SS, 410*SS
        if suit=="spade": draw_spade(dd, sx, sy, 3.6*SS, color)
        else: draw_heart(dd, sx, sy, 3.6*SS, color)
    index(im)
    rot=im.rotate(180); index(rot); im=rot.rotate(180)
    d=ImageDraw.Draw(im)
    cx, cy = W//2, H//2
    if suit=="spade":
        draw_spade(d, cx, cy-40*SS, 24*SS, color)
        logo_c(d, cx, cy-70*SS, 120*SS, 46*SS, PAPER50)
    else:
        draw_heart(d, cx, cy+10*SS, 24*SS, color)
        logo_c(d, cx, cy-10*SS, 105*SS, 40*SS, PAPER50)
    fm=F("jbmono-700", 30*SS)
    t="CLIQUE · CLUB PRIVADO"; tw=d.textlength(t, font=fm)
    d.text((cx-tw/2, H-m-90*SS), t, font=fm, fill=MUTE)
    im=im.resize((W//SS,H//SS), Image.LANCZOS); im.save(f"{OUT}/{fname}", optimize=True); print(fname)

def card_back(fname):
    SS=2; W,H=1260*SS,1760*SS
    im=paper((W,H), PAPER50, seed=7); d=ImageDraw.Draw(im)
    b=60*SS
    d.rounded_rectangle([b,b,W-b,H-b], radius=36*SS, fill=SALA)
    # gold lattice
    inner=[b+40*SS,b+40*SS,W-b-40*SS,H-b-40*SS]
    lat=Image.new("RGBA",(W,H),(0,0,0,0)); ld=ImageDraw.Draw(lat)
    step=70*SS
    for k in range(-H, W+H, step):
        ld.line([(k,0),(k+H,H)], fill=ORO600+(150,), width=2*SS)
        ld.line([(k,H),(k+H,0)], fill=ORO600+(150,), width=2*SS)
    mask=Image.new("L",(W,H),0); ImageDraw.Draw(mask).rounded_rectangle(inner, radius=24*SS, fill=255)
    im.paste(lat, (0,0), Image.composite(lat.split()[3], Image.new("L",(W,H),0), mask))
    d=ImageDraw.Draw(im)
    d.rounded_rectangle(inner, radius=24*SS, outline=ORO, width=4*SS)
    cx,cy=W//2,H//2; R=230*SS
    d.ellipse([cx-R-24*SS,cy-R-24*SS,cx+R+24*SS,cy+R+24*SS], fill=SALA, outline=ORO, width=4*SS)
    d.ellipse([cx-R,cy-R,cx+R,cy+R], fill=ORO)
    logo_c(d, cx-20*SS, cy, 130*SS, 52*SS, SALA0)
    im=im.resize((W//SS,H//SS), Image.LANCZOS); im.save(f"{OUT}/{fname}", optimize=True); print(fname)

def slip(fname):
    SS=2; W,H=960*SS,1560*SS
    im=paper((W,H), PAPER, seed=3).convert("RGBA"); d=ImageDraw.Draw(im)
    fm=F("jbmono-500", 30*SS); fmb=F("jbmono-700", 34*SS); fb=F("bricolage-800", 96*SS); fbm=F("bricolage-700", 56*SS); fi=F("instrument-600", 34*SS)
    x=70*SS; y=70*SS
    d.text((x,y), "CLIQUE · BOLETO DE APUESTA", font=fm, fill=MUTE); y+=56*SS
    d.text((x,y), "Nº 2637 · SEMANA 41", font=fm, fill=MUTE); y+=90*SS
    d.text((x,y), "Ruleta", font=fb, fill=INK); y+=104*SS
    d.text((x,y), "europea", font=fb, fill=INK); y+=150*SS
    d.text((x,y), "TU APUESTA", font=fm, fill=MUTE); y+=50*SS
    d.text((x,y), "Rojo", font=fbm, fill=VERM700); y+=110*SS
    # tear line with notches
    ty=y; 
    for k in range(int(x), W-int(x), 26*SS): d.line([(k,ty),(k+13*SS,ty)], fill=LINE, width=3*SS)
    y+=60*SS
    rows=[("Apuesta","$250.00"),("Paga","2.00×"),("Cobro","$500.00")]
    for a,b2 in rows:
        d.text((x,y), a.upper(), font=fm, fill=MUTE)
        tw=d.textlength(b2, font=fmb); d.text((W-x-tw,y-4*SS), b2, font=fmb, fill=INK); y+=70*SS
    y+=30*SS
    d.text((x,y), "Círculo · La Mesa del Viernes", font=fi, fill=INK); y+=60*SS
    d.text((x,y), "10 OCT 2026 · 22:41", font=fm, fill=MUTE); y+=110*SS
    # barcode
    random.seed(41); bx=x
    while bx < W-x:
        w=random.choice([2,2,3,4,6])*SS; d.rectangle([bx,y,bx+w,y+110*SS], fill=INK); bx+=w+random.choice([3,4,6])*SS
    y+=130*SS
    d.text((x,y), "Dinero ficticio. Sin valor real.", font=fm, fill=MUTE)
    # stamp
    st=Image.new("RGBA",(560*SS,200*SS),(0,0,0,0)); sd=ImageDraw.Draw(st)
    sd.rounded_rectangle([8*SS,8*SS,552*SS,192*SS], radius=18*SS, outline=VERM700+(230,), width=10*SS)
    fs=F("bricolage-800", 120*SS); tw=sd.textlength("PAGADO", font=fs); sd.text(((560*SS-tw)/2, 24*SS), "PAGADO", font=fs, fill=VERM700+(230,))
    st=st.rotate(14, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(st, (int(W*0.33), int(H*0.785)))
    # notches: transparent half-circles at the tear line
    a=im.split()[3]; ad=ImageDraw.Draw(a); r=34*SS
    ad.ellipse([-r,ty-r,r,ty+r], fill=0); ad.ellipse([W-r,ty-r,W+r,ty+r], fill=0)
    im.putalpha(a)
    im=im.resize((W//SS,H//SS), Image.LANCZOS); im.save(f"{OUT}/{fname}", optimize=True); print(fname, "tear_y_frac", ty/H)

def poster(game, title, rtp, no, bg, band, dark, fname):
    W,H=1000,1400
    im=paper((W,H), PAPER, seed=zlib.crc32(game.encode())%100); d=ImageDraw.Draw(im)
    art_h=900
    d.rectangle([0,0,W,art_h], fill=bg)
    icon=Image.open(f"{ICONS}/{game}.png").convert("RGBA").resize((720,720), Image.LANCZOS)
    im.paste(icon, ((W-720)//2, 110), icon)
    d.rectangle([0,art_h,W,art_h+26], fill=band)
    fm=F("jbmono-700", 34); fb=F("bricolage-800", 132)
    d.text((48,40), f"No.{no}", font=fm, fill=PAPER if dark else INK)
    d.text((56, art_h+70), title, font=fb, fill=INK)
    fm2=F("jbmono-500", 30)
    d.text((60, H-110), f"RETORNO {rtp}", font=fm2, fill=MUTE)
    t="JUGAR"; tw=d.textlength(t, font=fm2); ax=W-60; ay=H-110+19
    d.line([(ax-34,ay),(ax,ay)], fill=INK, width=4); d.polygon([(ax+2,ay),(ax-12,ay-10),(ax-12,ay+10)], fill=INK)
    d.text((ax-48-tw, H-110), t, font=fm2, fill=INK)
    im.save(f"{OUT}/{fname}", optimize=True); print(fname)

card_face("A", "spade", INK, "carta_as_picas.png")
card_face("A", "heart", VERM700, "carta_as_corazones.png")
card_back("carta_reverso.png")
slip("boleto_ruleta.png")
poster("roulette","Ruleta","97.3%","03",VERM,PAPER,False,"poster_ruleta.png")
poster("blackjack","Blackjack","99.5%","02",FELT,LIME,True,"poster_blackjack.png")
poster("chicken","Chicken","97%","01",LIME,VERM,False,"poster_chicken.png")
