#!/usr/bin/env python3
"""Genera TODOS los assets placeholder del prototipo de pelea.

Salida (determinística, se versiona):
  assets/fighter.gif   tiles únicos del luchador (grilla de 16 tiles de ancho)
  assets/fx.gif        bola de energía, chispa de impacto y sombra
  assets/sky.gif       capa lejana (parallax 1/4)
  assets/city.gif      capa media: edificios y público (parallax 1/2)
  assets/street.gif    capa cercana: piso en perspectiva (parallax 1)
  assets/hud.gif       tiles 8x8 del fix layer: barras de vida y dígitos grandes
  src/gen/assets.h     tiles base, dimensiones de capas, enums de animación
  src/gen/assets.c     paletas, tilemaps por frame, animaciones y cajas

El orden de la C-ROM lo define el Makefile y tiene que coincidir con TILE_* acá:
  logo del BIOS (256) -> fighter -> fx -> sky -> city -> street
Reglas del formato: GIF indexado, índice 0 transparente, tiles 16x16 fila por fila.

El arte final lo reemplaza el autor; este script solo existe para que el
código tenga datos con las mismas dimensiones y reglas.
"""
import math
import os
import random
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ASSETS = os.path.join(ROOT, "assets")
GEN = os.path.join(ROOT, "src", "gen")

# --------------------------------------------------------------------------
# utilidades de paleta y tiles
# --------------------------------------------------------------------------

def packed15(rgb):
    """Mismo algoritmo que paltool.py de ngdevkit."""
    r, g, b = [c >> 2 for c in rgb]
    darkbit = 1 if ((r & 1) + (g & 1) + (b & 1)) == 0 else 0
    r, g, b = r >> 1, g >> 1, b >> 1
    lsb = ((r & 1) << 2) | ((g & 1) << 1) | (b & 1)
    r, g, b = r >> 1, g >> 1, b >> 1
    return darkbit << 15 | lsb << 12 | r << 8 | g << 4 | b


def pad16(pal):
    pal = list(pal)[:16]
    return pal + [(0, 0, 0)] * (16 - len(pal))


def new_p(w, h, pal, fill=0):
    img = Image.new("P", (w, h), fill)
    img.putpalette([c for rgb in pad16(pal) for c in rgb])
    return img


def save_gif(img, name):
    img.save(os.path.join(ASSETS, name), transparency=0, optimize=False)


def tiles_of(img, tw=16, th=16):
    w, h = img.size
    out = []
    for ty in range(h // th):
        for tx in range(w // tw):
            out.append(img.crop((tx * tw, ty * th, tx * tw + tw, ty * th + th)))
    return out


def tile_key(t):
    return bytes(t.tobytes())


def grid_sheet(tiles, pal, cols=16, tw=16, th=16):
    rows = (len(tiles) + cols - 1) // cols
    sheet = new_p(cols * tw, rows * th, pal)
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * tw, (i // cols) * th))
    return sheet, rows * cols   # tiles ocupados en la C-ROM (incluye relleno)


# --------------------------------------------------------------------------
# luchador procedural: esqueleto 2D + poses
# --------------------------------------------------------------------------

FW, FH = 112, 128           # lienzo por frame: 7x8 tiles
AX, AY = 56, 124            # ancla (entre los pies) dentro del lienzo
FCOLS, FROWS = FW // 16, FH // 16

FIGHTER_PAL = [
    (255, 0, 255),    # 0 transparente
    (24, 16, 32),     # 1 contorno
    (255, 214, 170),  # 2 piel luz
    (228, 158, 112),  # 3 piel
    (170, 100, 70),   # 4 piel sombra
    (255, 128, 96),   # 5 chaqueta luz
    (212, 44, 40),    # 6 chaqueta
    (128, 20, 32),    # 7 chaqueta sombra
    (120, 136, 184),  # 8 pantalón luz
    (64, 72, 124),    # 9 pantalón
    (32, 34, 72),     # 10 pantalón sombra
    (56, 36, 26),     # 11 pelo
    (112, 76, 50),    # 12 pelo luz
    (236, 236, 236),  # 13 guantes / zapatillas
    (150, 150, 168),  # 14 guantes sombra
    (250, 204, 40),   # 15 vincha / cinturón
]
# P2: misma figura, otra ropa (palette swap como en KOF)
FIGHTER_PAL_P2 = list(FIGHTER_PAL)
FIGHTER_PAL_P2[5:8] = [(120, 190, 255), (40, 100, 216), (20, 44, 128)]
FIGHTER_PAL_P2[8:11] = [(208, 208, 200), (140, 140, 132), (80, 80, 76)]
FIGHTER_PAL_P2[11:13] = [(236, 236, 240), (255, 255, 255)]
FIGHTER_PAL_P2[15] = (40, 40, 48)

SKIN = (2, 3, 4)
JACKET = (5, 6, 7)
PANTS = (8, 9, 10)
GLOVE = (13, 13, 14)
HAIR = (12, 11, 11)

L_TORSO, L_NECK, R_HEAD = 32, 5, 9
L_UARM, L_FARM = 19, 17
L_THIGH, L_SHIN = 26, 26


def vdown(deg):
    a = math.radians(deg)
    return (math.sin(a), math.cos(a))          # 0 = hacia abajo, + = hacia adelante


def vup(deg):
    a = math.radians(deg)
    return (math.sin(a), -math.cos(a))         # 0 = hacia arriba, + = hacia adelante


def add(p, v, k=1.0):
    return (p[0] + v[0] * k, p[1] + v[1] * k)


def capsule(d, a, b, width, cols, outline=True):
    light, mid, dark = cols
    if outline:
        d.line([a, b], fill=1, width=width + 2)
        r = (width + 2) / 2
        for p in (a, b):
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=1)
    d.line([a, b], fill=mid, width=width)
    r = width / 2
    for p in (a, b):
        d.ellipse([p[0] - r + 0.5, p[1] - r + 0.5, p[0] + r - 0.5, p[1] + r - 0.5], fill=mid)
    # sombreado: normal hacia la luz (arriba-adelante)
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1
    nx, ny = -dy / n, dx / n
    if nx * 0.5 + ny * -1 < 0:
        nx, ny = -nx, -ny
    off = width / 4
    if width >= 6:
        d.line([add(a, (-nx, -ny), off), add(b, (-nx, -ny), off)], fill=dark, width=max(2, width // 3))
        d.line([add(a, (nx, ny), off), add(b, (nx, ny), off)], fill=light, width=max(1, width // 4))


def solve(pose):
    """Devuelve las posiciones de las articulaciones (mirando a la derecha)."""
    hip = (AX + pose.get("hx", 0), AY + pose.get("hy", -56))
    t = pose.get("torso", 6)
    neck = add(hip, vup(t), L_TORSO)
    head = add(neck, vup(t + pose.get("head", 0)), L_NECK + R_HEAD)
    j = {"hip": hip, "neck": neck, "head": head, "t": t}
    for side, sx in (("f", 3), ("b", -3)):
        sh = add(neck, (sx, 3))
        s, e = pose["arm_" + side]
        el = add(sh, vdown(s), L_UARM)
        ha = add(el, vdown(s + e), L_FARM)
        j["sh" + side], j["el" + side], j["ha" + side] = sh, el, ha
        hp = add(hip, (sx, 0))
        h, k = pose["leg_" + side]
        kn = add(hp, vdown(h), L_THIGH)
        sd = vdown(h - k)
        an = add(kn, sd, L_SHIN)
        toe = add(an, (sd[1], -sd[0]), 10)
        j["hp" + side], j["kn" + side], j["an" + side], j["toe" + side] = hp, kn, an, toe
    return j


def draw_pose(pose):
    img = new_p(FW, FH, FIGHTER_PAL)
    d = ImageDraw.Draw(img)
    j = solve(pose)

    def arm(s):
        capsule(d, j["sh" + s], j["el" + s], 9, SKIN if s == "f" else (3, 4, 4))
        capsule(d, j["el" + s], j["ha" + s], 8, SKIN if s == "f" else (3, 4, 4))
        h = j["ha" + s]
        d.ellipse([h[0] - 6, h[1] - 6, h[0] + 6, h[1] + 6], fill=1)
        d.ellipse([h[0] - 5, h[1] - 5, h[0] + 5, h[1] + 5], fill=13 if s == "f" else 14)

    def leg(s):
        cols = PANTS if s == "f" else (9, 10, 10)
        capsule(d, j["hp" + s], j["kn" + s], 13, cols)
        capsule(d, j["kn" + s], j["an" + s], 11, cols)
        capsule(d, j["an" + s], j["toe" + s], 6, GLOVE)

    arm("b")
    leg("b")
    # torso: trapecio orientado
    hip, neck, t = j["hip"], j["neck"], j["t"]
    ux, uy = vup(t)
    px, py = -uy, ux                      # perpendicular
    pts = [add(add(hip, (px, py), 9), (0, 0)), add(hip, (px, py), -9),
           add(neck, (px, py), -13), add(neck, (px, py), 13)]
    d.polygon(pts, fill=1)
    inner = [add(pts[0], (-px, -py), 1), add(pts[1], (px, py), 1),
             add(pts[2], (px, py), 1), add(pts[3], (-px, -py), 1)]
    d.polygon(inner, fill=6)
    d.polygon([inner[3], add(inner[3], (-px, -py), 4), add(inner[0], (-px, -py), 4), inner[0]], fill=5)
    d.polygon([inner[1], add(inner[1], (px, py), 3), add(inner[2], (px, py), 3), inner[2]], fill=7)
    # cinturón
    b0, b1 = add(hip, vup(t), 3), add(hip, vup(t), 7)
    d.line([add(b0, (px, py), 9), add(b0, (px, py), -9)], fill=15, width=3)
    leg("f")
    # cabeza
    h = j["head"]
    d.ellipse([h[0] - R_HEAD - 1, h[1] - R_HEAD - 1, h[0] + R_HEAD + 1, h[1] + R_HEAD + 1], fill=1)
    d.ellipse([h[0] - R_HEAD, h[1] - R_HEAD, h[0] + R_HEAD, h[1] + R_HEAD], fill=3)
    d.ellipse([h[0] - R_HEAD + 3, h[1] - R_HEAD + 2, h[0] + R_HEAD - 1, h[1] + 2], fill=2)
    # pelo en punta hacia atrás
    d.polygon([(h[0] - 10, h[1] - 2), (h[0] - 4, h[1] - 12), (h[0] + 6, h[1] - 10),
               (h[0] + 8, h[1] - 5), (h[0] - 2, h[1] - 6), (h[0] - 14, h[1] + 4)], fill=11)
    d.line([(h[0] - 4, h[1] - 10), (h[0] + 5, h[1] - 9)], fill=12, width=1)
    d.line([(h[0] - 9, h[1] - 4), (h[0] + 8, h[1] - 4)], fill=15, width=2)   # vincha
    d.point([(h[0] + 5, h[1] - 1)], fill=1)                                  # ojo
    arm("f")
    return img, j


def box_around(pts, pad):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def rel(box):
    """Caja del lienzo -> (x, y, w, h) relativa al ancla, recortada a s8."""
    x0, y0, x1, y1 = box
    x, y, w, h = int(x0 - AX), int(y0 - AY), int(x1 - x0), int(y1 - y0)
    clamp = lambda v: max(-127, min(127, v))
    return (clamp(x), clamp(y), clamp(w), clamp(h))


GUARD = dict(torso=8, arm_f=(48, 88), arm_b=(26, 104), leg_f=(20, 12), leg_b=(-18, 8))


def P(**kw):
    p = dict(GUARD)
    p.update(kw)
    return p


def walk(i, n=6):
    ph = 2 * math.pi * i / n
    s = math.sin(ph)
    return P(hy=-56 + int(abs(math.cos(ph)) * 2), leg_f=(18 * s + 2, 10 + max(0, 18 * math.cos(ph))),
             leg_b=(-18 * s - 2, 10 + max(0, -18 * math.cos(ph))), arm_f=(48 - 6 * s, 88), arm_b=(26 + 6 * s, 104))


CROUCH = dict(hy=-31, torso=20, leg_f=(80, 112), leg_b=(34, 126))

POSES = {
    "idle0": P(hy=-56), "idle1": P(hy=-55, arm_f=(46, 90)), "idle2": P(hy=-54, arm_f=(44, 92), arm_b=(24, 106)),
    "crouch": P(**CROUCH),
    "crouch_t": P(hy=-42, torso=14, leg_f=(50, 70), leg_b=(10, 80)),
    "prejump": P(hy=-44, torso=12, leg_f=(40, 60), leg_b=(0, 60)),
    "air_up": P(hy=-66, torso=4, leg_f=(64, 110), leg_b=(20, 110), arm_f=(80, 70), arm_b=(60, 90)),
    "air_down": P(hy=-62, torso=0, leg_f=(30, 40), leg_b=(-10, 30), arm_f=(70, 60), arm_b=(40, 80)),
    "p_start": P(torso=10, arm_f=(30, 110), arm_b=(40, 96)),
    "p_active": P(torso=18, hx=4, arm_f=(92, 2), arm_b=(20, 110), leg_f=(26, 10)),
    "k_start": P(torso=0, leg_f=(76, 110), arm_f=(40, 90), arm_b=(10, 100)),
    "k_active": P(torso=-14, hx=-2, leg_f=(92, 4), leg_b=(-6, 6), arm_f=(30, 90), arm_b=(-10, 90)),
    "cp_start": P(**CROUCH, arm_f=(40, 100)),
    "cp_active": P(**dict(CROUCH, torso=26), arm_f=(96, 0)),
    "jk_active": P(hy=-62, torso=-6, leg_f=(58, 0), leg_b=(30, 110), arm_f=(60, 80), arm_b=(20, 90)),
    "fb_wind": P(torso=-6, hx=-3, arm_f=(-40, 70), arm_b=(-50, 60), leg_f=(24, 10), leg_b=(-20, 6)),
    "fb_release": P(torso=22, hx=6, arm_f=(92, 0), arm_b=(84, 8), leg_f=(38, 20), leg_b=(-30, 0)),
    "block": P(torso=-6, hx=-3, arm_f=(64, 120), arm_b=(52, 128)),
    "cblock": P(**CROUCH, arm_f=(70, 120), arm_b=(58, 128)),
    "hit0": P(torso=-22, hx=-4, head=-10, arm_f=(-10, 40), arm_b=(-30, 30), leg_f=(22, 6)),
    "hit1": P(torso=-12, hx=-2, head=-6, arm_f=(10, 60), arm_b=(-10, 50)),
    "chit": P(**dict(CROUCH, torso=0), head=-10, arm_f=(10, 60), arm_b=(-10, 50)),
    "kd0": P(hy=-50, torso=-45, head=-10, leg_f=(50, 20), leg_b=(20, 10), arm_f=(-40, 30), arm_b=(-60, 20)),
    "kd1": P(hy=-26, torso=-78, leg_f=(70, 20), leg_b=(50, 10), arm_f=(-80, 20), arm_b=(-100, 10)),
    "lying": P(hy=-8, hx=8, torso=-92, head=4, leg_f=(88, 2), leg_b=(84, 0), arm_f=(-100, 10), arm_b=(-120, 10)),
    "getup": P(hy=-36, torso=24, leg_f=(76, 100), leg_b=(24, 110), arm_f=(60, 60), arm_b=(30, 80)),
    "win0": P(torso=2, arm_f=(172, 6), arm_b=(12, 100), leg_f=(10, 4), leg_b=(-12, 4)),
    "win1": P(hy=-57, torso=0, arm_f=(176, 2), arm_b=(14, 100), leg_f=(10, 4), leg_b=(-12, 4)),
}
for i in range(6):
    POSES["walk%d" % i] = walk(i)

# flags de frame (tienen que coincidir con fighter.h)
F_ACTIVE, F_LOW, F_OVERHEAD, F_SPAWN = 1, 2, 4, 8

# (nombre, loop, [(pose, duración, flags)], limb activo para la hitbox)
ANIMS = [
    ("IDLE", 1, [("idle0", 8, 0), ("idle1", 8, 0), ("idle2", 8, 0), ("idle1", 8, 0)], None),
    ("WALK_F", 1, [("walk%d" % i, 5, 0) for i in range(6)], None),
    ("WALK_B", 1, [("walk%d" % i, 6, 0) for i in reversed(range(6))], None),
    ("CROUCH_T", 0, [("crouch_t", 3, 0)], None),
    ("CROUCH", 1, [("crouch", 60, 0)], None),
    ("PREJUMP", 0, [("prejump", 4, 0)], None),
    ("AIR_UP", 1, [("air_up", 60, 0)], None),
    ("AIR_DOWN", 1, [("air_down", 60, 0)], None),
    ("LAND", 0, [("prejump", 4, 0)], None),
    ("PUNCH", 0, [("p_start", 3, 0), ("p_active", 3, F_ACTIVE), ("p_start", 6, 0)], "haf"),
    ("KICK", 0, [("k_start", 5, 0), ("k_active", 4, F_ACTIVE), ("k_start", 10, 0)], "toef"),
    ("CPUNCH", 0, [("cp_start", 3, 0), ("cp_active", 3, F_ACTIVE | F_LOW), ("cp_start", 7, 0)], "haf"),
    ("JKICK", 1, [("jk_active", 60, F_ACTIVE | F_OVERHEAD)], "toef"),
    ("FIREBALL", 0, [("fb_wind", 8, 0), ("fb_release", 4, F_SPAWN), ("fb_release", 14, 0), ("fb_wind", 8, 0)], None),
    ("BLOCK", 1, [("block", 60, 0)], None),
    ("CBLOCK", 1, [("cblock", 60, 0)], None),
    ("HIT", 0, [("hit0", 5, 0), ("hit1", 60, 0)], None),
    ("CHIT", 1, [("chit", 60, 0)], None),
    ("KNOCKDOWN", 0, [("kd0", 6, 0), ("kd1", 6, 0), ("lying", 30, 0), ("getup", 10, 0)], None),
    ("KO", 0, [("kd0", 8, 0), ("kd1", 8, 0), ("lying", 250, 0)], None),
    ("WIN", 1, [("win0", 12, 0), ("win1", 12, 0)], None),
]


def build_fighter(tile_base):
    uniq = {}
    tiles = []

    def tid(t):
        k = tile_key(t)
        if k not in uniq:
            uniq[k] = len(tiles)
            tiles.append(t)
        return uniq[k]

    tid(new_p(16, 16, FIGHTER_PAL))           # tile 0 del set = vacío
    pose_frames = {}
    for name, pose in POSES.items():
        img, j = draw_pose(pose)
        tmap = [tile_base + tid(t) for t in tiles_of(img)]
        upper = box_around([j["head"], j["neck"], j["hip"], j["elf"], j["elb"]], 6)
        lower = box_around([j["hip"], j["knf"], j["knb"], j["anf"], j["anb"]], 6)
        pose_frames[name] = (tmap, j, rel(upper), rel(lower))
    sheet, used = grid_sheet(tiles, FIGHTER_PAL)
    return sheet, used, pose_frames


# --------------------------------------------------------------------------
# efectos: bola de energía (3 frames), chispa (3 frames), sombra
# --------------------------------------------------------------------------

FX_PAL = [(255, 0, 255), (20, 20, 40), (255, 255, 255), (170, 230, 255), (80, 170, 255),
          (30, 80, 220), (255, 250, 180), (255, 210, 60), (255, 130, 20), (200, 50, 10),
          (40, 40, 56), (70, 70, 90)]


def build_fx(tile_base):
    img = new_p(32 * 7 + 32, 32, FX_PAL)
    d = ImageDraw.Draw(img)
    for f in range(3):                          # bola: x = 0, 32, 64
        ox = f * 32
        r = 11 + f
        d.ellipse([ox + 16 - r, 16 - r + 2, ox + 16 + r, 16 + r - 2], fill=5)
        d.ellipse([ox + 16 - r + 3, 16 - r + 5, ox + 16 + r - 3, 16 + r - 5], fill=4)
        d.ellipse([ox + 16 - 6, 11, ox + 16 + 6, 21], fill=3)
        d.ellipse([ox + 16 - 3, 13, ox + 16 + 3, 19], fill=2)
        for k in range(4):                      # estela
            a = f * 0.9 + k * 1.6
            x = ox + 6 + int(4 * math.cos(a))
            y = 16 + int(9 * math.sin(a))
            d.point([(x, y), (x - 2, y)], fill=3)
    for f in range(3):                          # chispa: x = 96, 128, 160
        ox = 96 + f * 32
        r = [6, 12, 15][f]
        for k in range(8):
            a = k * math.pi / 4 + f * 0.3
            rr = r if k % 2 == 0 else r * 0.55
            d.line([(ox + 16, 16), (ox + 16 + rr * math.cos(a), 16 + rr * math.sin(a))],
                   fill=[6, 7, 8][f], width=3 - (f == 2))
        d.ellipse([ox + 16 - 4 + f, 12 + f, ox + 16 + 4 - f, 20 - f], fill=2 if f < 2 else 7)
    # sombra con trama (en Neo Geo no hay transparencia): x = 192..223, y 8..24
    for y in range(10, 22):
        for x in range(192, 224):
            if ((x - 208) / 15.0) ** 2 + ((y - 16) / 5.5) ** 2 <= 1 and (x + y) % 2 == 0:
                img.putpixel((x, y), 10)
    # bloqueo: chispa azul, x = 224
    d.ellipse([224 + 8, 8, 224 + 24, 24], outline=4, width=2)
    d.ellipse([224 + 12, 12, 224 + 20, 20], fill=3)
    tiles = tiles_of(img)                      # fila 0 y fila 1 de 16px
    save_gif(img, "fx.gif")
    return len(tiles)


# --------------------------------------------------------------------------
# escenario: tres capas con parallax
# --------------------------------------------------------------------------

CAM_RANGE = 192                                # recorrido de cámara en px
LAYERS = [  # nombre, shift (ratio = 1/2^shift), alto en tiles, y en pantalla
    ("sky", 2, 9, 0),
    ("city", 1, 10, 16),
    ("street", 0, 5, 144),
]


def layer_cols(shift):
    return (320 + (CAM_RANGE >> shift) + 15) // 16


SKY_PAL = [(0, 0, 0), (32, 20, 64), (60, 32, 96), (104, 48, 120), (160, 64, 120), (220, 96, 104),
           (255, 150, 90), (255, 206, 120), (255, 240, 190), (70, 50, 100), (110, 80, 130),
           (48, 36, 80), (255, 255, 230), (190, 110, 140)]
CITY_PAL = [(0, 0, 0), (18, 14, 34), (34, 28, 60), (52, 44, 86), (80, 68, 116), (255, 214, 110),
            (255, 170, 60), (120, 100, 150), (200, 60, 70), (250, 250, 240), (60, 40, 50),
            (110, 70, 60), (160, 110, 80), (90, 150, 200), (40, 30, 36)]
STREET_PAL = [(0, 0, 0), (40, 34, 44), (70, 60, 72), (100, 88, 96), (130, 116, 118),
              (160, 146, 140), (190, 176, 164), (220, 208, 190), (90, 70, 60), (140, 60, 50),
              (230, 200, 90), (24, 20, 28), (60, 52, 110), (120, 108, 170)]


def dither_band(d, x0, y0, x1, y1, c_top, c_bot):
    """Degradé de dos colores con trama ordenada (look de 16 bits)."""
    h = y1 - y0
    bayer = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
    for y in range(y0, y1):
        t = (y - y0) / max(1, h - 1)
        for x in range(x0, x1):
            d.point([(x, y)], fill=c_bot if t * 16 > bayer[y % 4][x % 4] else c_top)


def build_sky():
    w, h = layer_cols(2) * 16, 9 * 16
    img = new_p(w, h, SKY_PAL, 1)
    d = ImageDraw.Draw(img)
    bands = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7)]
    bh = h // len(bands)
    for i, (a, b) in enumerate(bands):
        dither_band(d, 0, i * bh, w, (i + 1) * bh if i < len(bands) - 1 else h, a, b)
    d.ellipse([w * 0.62 - 22, h - 58, w * 0.62 + 22, h - 14], fill=8)       # sol
    d.ellipse([w * 0.62 - 17, h - 53, w * 0.62 + 17, h - 19], fill=12)
    rnd = random.Random(7)
    for _ in range(9):                                                     # nubes
        cx, cy = rnd.randrange(w), rnd.randrange(12, 70)
        for k in range(5):
            rx = rnd.randrange(10, 26)
            d.ellipse([cx + k * 12 - rx, cy - 5, cx + k * 12 + rx, cy + 6], fill=13 if cy > 40 else 10)
    for x in range(0, w, 3):                                               # montañas lejanas
        y = h - 18 - int(14 * abs(math.sin(x / 37.0)) + 8 * abs(math.sin(x / 13.0)))
        d.line([(x, y), (x, h)], fill=9, width=3)
    save_gif(img, "sky.gif")
    return img


def build_city():
    w, h = layer_cols(1) * 16, 10 * 16
    img = new_p(w, h, CITY_PAL, 0)
    d = ImageDraw.Draw(img)
    rnd = random.Random(98)
    x = 0
    while x < w:                                                           # edificios
        bw = rnd.randrange(34, 70)
        top = rnd.randrange(8, 70)
        col = rnd.choice([2, 3, 4])
        d.rectangle([x, top, x + bw, h], fill=col, outline=1)
        for wy in range(top + 6, h - 50, 9):
            for wx in range(x + 5, x + bw - 5, 8):
                if rnd.random() < 0.55:
                    d.rectangle([wx, wy, wx + 3, wy + 4], fill=rnd.choice([5, 5, 6, 1]))
        x += bw + rnd.randrange(0, 6)
    # cartel luminoso
    bx = w // 2 - 60
    d.rectangle([bx, 40, bx + 120, 70], fill=8, outline=1)
    d.rectangle([bx + 4, 44, bx + 116, 66], fill=10)
    for i, c in enumerate("NEO FIGHT"):
        d.text((bx + 12 + i * 11, 48), c, fill=9)
    # baranda y público (de 100 a 136)
    d.rectangle([0, 128, w, 131], fill=7)
    for px in range(0, w, 12):
        d.line([(px, 131), (px, 150)], fill=7, width=2)
    for px in range(4, w, 9):                                              # cabezas y cuerpos
        py = 104 + rnd.randrange(-4, 5)
        shirt = rnd.choice([8, 13, 11, 12, 3, 9])
        d.rectangle([px - 4, py + 8, px + 4, 150], fill=shirt, outline=1)
        d.ellipse([px - 4, py, px + 4, py + 9], fill=rnd.choice([12, 11, 12]), outline=1)
        if rnd.random() < 0.3:                                             # brazos arriba
            d.line([(px + 3, py + 9), (px + 7, py - 3)], fill=12, width=2)
    d.rectangle([0, 150, w, h], fill=14)
    save_gif(img, "city.gif")
    return img


def build_street():
    w, h = layer_cols(0) * 16, 5 * 16
    img = new_p(w, h, STREET_PAL, 3)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 7], fill=6)                                      # cordón
    d.rectangle([0, 7, w, 9], fill=1)
    # baldosas en perspectiva: filas cada vez más altas hacia abajo
    ys, y, step = [10], 10, 5
    while y < h:
        y += step
        step += 2
        ys.append(min(y, h))
    vpx, vpy = w / 2, -160
    for i in range(len(ys) - 1):
        y0, y1 = ys[i], ys[i + 1]
        dither_band(d, 0, y0, w, y1, 3 if i % 2 else 4, 4 if i % 2 else 5)
        d.line([(0, y0), (w, y0)], fill=2)
    for gx in range(-w, 2 * w, 32):                                        # juntas hacia el punto de fuga
        x_top = vpx + (gx - vpx) * (10 - vpy) / (h - vpy)
        d.line([(x_top, 10), (gx, h)], fill=2)
    rnd = random.Random(3)
    for _ in range(40):                                                    # manchas / papelitos
        px, py = rnd.randrange(w), rnd.randrange(14, h)
        d.point([(px, py)], fill=rnd.choice([10, 9, 13, 7]))
    save_gif(img, "street.gif")
    return img


# --------------------------------------------------------------------------
# HUD: tiles 8x8 del fix layer
# --------------------------------------------------------------------------

HUD_PAL = [(255, 0, 255), (16, 12, 20), (170, 255, 90), (60, 180, 40), (120, 20, 30),
           (60, 10, 20), (255, 255, 255), (150, 150, 170), (255, 240, 120), (255, 170, 30),
           (170, 60, 10), (230, 40, 40), (80, 80, 100)]
HUD_BAR_FULL, HUD_BAR_EMPTY = 1, 2
HUD_P1_PART, HUD_P2_PART = 3, 10               # +k-1 para k = 1..7 px llenos
HUD_CAP_L, HUD_CAP_R, HUD_WIN_OFF, HUD_WIN_ON = 17, 18, 19, 20
HUD_DIGITS = 21                                # 10 dígitos x 6 tiles (2x3)

DIGIT_SEGS = {  # segmentos estilo 7 seg: a b c d e f g
    0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc", 5: "afgcd",
    6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg"}


def bar_tile(fill_mask):
    t = new_p(8, 8, HUD_PAL)
    d = ImageDraw.Draw(t)
    d.rectangle([0, 0, 7, 7], fill=1)
    for x in range(8):
        on = fill_mask[x]
        d.line([(x, 1), (x, 3)], fill=2 if on else 4)
        d.line([(x, 4), (x, 6)], fill=3 if on else 5)
    return t


def digit_img(n):
    img = new_p(16, 24, HUD_PAL)
    d = ImageDraw.Draw(img)
    seg = {"a": [(3, 1), (12, 1), (10, 4), (5, 4)], "d": [(3, 22), (12, 22), (10, 19), (5, 19)],
           "g": [(4, 11), (11, 11), (12, 12), (11, 13), (4, 13), (3, 12)],
           "f": [(1, 3), (4, 5), (4, 10), (1, 11)], "b": [(14, 3), (11, 5), (11, 10), (14, 11)],
           "e": [(1, 13), (4, 14), (4, 18), (1, 20)], "c": [(14, 13), (11, 14), (11, 18), (14, 20)]}
    for s in DIGIT_SEGS[n]:
        pts = seg[s]
        d.polygon([(x + 1, y + 1) for x, y in pts], fill=1)
    for s in DIGIT_SEGS[n]:
        d.polygon(seg[s], fill=9 if s in "edc" else 8, outline=10)
    return img


def build_hud():
    tiles = [new_p(8, 8, HUD_PAL)]                                        # 0 vacío
    tiles.append(bar_tile([1] * 8))                                       # 1 lleno
    tiles.append(bar_tile([0] * 8))                                       # 2 vacío
    for k in range(1, 8):                                                 # 3..9 P1: llenos a la derecha
        tiles.append(bar_tile([0] * (8 - k) + [1] * k))
    for k in range(1, 8):                                                 # 10..16 P2: llenos a la izquierda
        tiles.append(bar_tile([1] * k + [0] * (8 - k)))
    for side in (0, 1):                                                   # 17, 18 tapas
        t = new_p(8, 8, HUD_PAL)
        d = ImageDraw.Draw(t)
        d.rectangle([0, 0, 7, 7], fill=7, outline=1)
        d.rectangle([2 if side == 0 else 1, 2, 6 if side == 0 else 5, 5], fill=11)
        tiles.append(t)
    for on in (0, 1):                                                     # 19, 20 marcas de round
        t = new_p(8, 8, HUD_PAL)
        d = ImageDraw.Draw(t)
        d.ellipse([0, 0, 7, 7], fill=1)
        d.ellipse([1, 1, 6, 6], fill=8 if on else 12)
        tiles.append(t)
    for n in range(10):                                                   # 21.. dígitos 2x3
        tiles.extend(tiles_of(digit_img(n), 8, 8))
    strip = new_p(8 * len(tiles), 8, HUD_PAL)
    for i, t in enumerate(tiles):
        strip.paste(t, (i * 8, 0))
    save_gif(strip, "hud.gif")
    return len(tiles)


# --------------------------------------------------------------------------
# salida C
# --------------------------------------------------------------------------

def c_pal(name, pal):
    return "const u16 %s[16] = {%s};\n" % (name, ", ".join("0x%04x" % packed15(c) for c in pad16(pal)))


def main():
    os.makedirs(GEN, exist_ok=True)
    tile_fighter = 256
    fsheet, fused, frames = build_fighter(tile_fighter)
    save_gif(fsheet, "fighter.gif")
    tile_fx = tile_fighter + fused
    fx_used = build_fx(tile_fx)
    tile_sky = tile_fx + fx_used
    sky = build_sky()
    tile_city = tile_sky + (sky.size[0] // 16) * (sky.size[1] // 16)
    city = build_city()
    tile_street = tile_city + (city.size[0] // 16) * (city.size[1] // 16)
    street = build_street()
    tile_end = tile_street + (street.size[0] // 16) * (street.size[1] // 16)
    hud_count = build_hud()

    # ---------------------------------------------------------------- frames
    pose_index = {}
    frame_rows = []            # (tmap_idx, dur, flags, hit, hurt_u, hurt_l)
    tmaps = []
    anim_rows = []
    for name, loop, seq, limb in ANIMS:
        first = len(frame_rows)
        for pose, dur, flags in seq:
            tmap, j, up, lo = frames[pose]
            if pose not in pose_index:
                pose_index[pose] = len(tmaps)
                tmaps.append(tmap)
            hit = (0, 0, 0, 0)
            if flags & F_ACTIVE and limb:
                # la caja cubre la extremidad activa entera, no solo la punta:
                # así el golpe conecta también cuerpo a cuerpo (como en KOF)
                side = limb[-1]
                if limb.startswith("toe"):
                    hit = rel(box_around([j[limb], j["an" + side], j["kn" + side]], 5))
                else:
                    hit = rel(box_around([j[limb], j["el" + side]], 6))
            frame_rows.append((pose_index[pose], dur, flags, hit, up, lo))
        anim_rows.append((name, first, len(seq), loop))

    h = []
    h.append("/* Generado por tools/make_assets.py: no editar a mano. */\n")
    h.append("#ifndef GEN_ASSETS_H\n#define GEN_ASSETS_H\n#include <ngdevkit/types.h>\n\n")
    h.append("#define TILE_FIGHTER %d\n#define TILE_FX %d\n#define TILE_SKY %d\n#define TILE_CITY %d\n#define TILE_STREET %d\n#define TILE_END %d\n\n"
             % (tile_fighter, tile_fx, tile_sky, tile_city, tile_street, tile_end))
    h.append("/* efectos: tiles de 16x16 en fx.gif (2 filas de %d) */\n" % ((32 * 7 + 32) // 16))
    h.append("#define FX_ROW %d\n#define FX_FIREBALL 0\n#define FX_SPARK 6\n#define FX_SHADOW 12\n#define FX_BLOCK 14\n\n" % ((32 * 7 + 32) // 16))
    h.append("#define FIGHTER_PX_W %d\n#define FIGHTER_PX_H %d\n#define FIGHTER_COLS %d\n#define FIGHTER_ROWS %d\n#define FIGHTER_AX %d\n#define FIGHTER_AY %d\n\n"
             % (FW, FH, FCOLS, FROWS, AX, AY))
    h.append("#define CAM_RANGE %d\n#define NUM_LAYERS %d\n" % (CAM_RANGE, len(LAYERS)))
    for i, (n, sh, ht, y) in enumerate(LAYERS):
        h.append("#define LAYER_%s_COLS %d\n#define LAYER_%s_ROWS %d\n#define LAYER_%s_SHIFT %d\n#define LAYER_%s_Y %d\n"
                 % (n.upper(), layer_cols(sh), n.upper(), ht, n.upper(), sh, n.upper(), y))
    h.append("\n#define HUD_TILES %d\n#define HUD_BAR_FULL %d\n#define HUD_BAR_EMPTY %d\n#define HUD_P1_PART %d\n#define HUD_P2_PART %d\n"
             "#define HUD_CAP_L %d\n#define HUD_CAP_R %d\n#define HUD_WIN_OFF %d\n#define HUD_WIN_ON %d\n#define HUD_DIGITS %d\n\n"
             % (hud_count, HUD_BAR_FULL, HUD_BAR_EMPTY, HUD_P1_PART, HUD_P2_PART, HUD_CAP_L, HUD_CAP_R,
                HUD_WIN_OFF, HUD_WIN_ON, HUD_DIGITS))
    h.append("#define FF_ACTIVE %d\n#define FF_LOW %d\n#define FF_OVERHEAD %d\n#define FF_SPAWN %d\n\n" % (F_ACTIVE, F_LOW, F_OVERHEAD, F_SPAWN))
    h.append("enum {\n" + "".join("    ANIM_%s,\n" % a[0] for a in ANIMS) + "    ANIM_COUNT\n};\n\n")
    h.append("typedef struct { s8 x, y, w, h; } box_t;\n")
    h.append("typedef struct {\n    u16 tmap;       /* índice en fighter_tmaps */\n    u8 dur;\n    u8 flags;\n"
             "    box_t hit;      /* w == 0: sin hitbox */\n    box_t hurt_hi;\n    box_t hurt_lo;\n} frame_t;\n")
    h.append("typedef struct { u16 first; u8 count; u8 loop; } anim_t;\n\n")
    h.append("extern const u16 fighter_tmaps[][%d];\nextern const frame_t fighter_frames[];\nextern const anim_t fighter_anims[];\n" % (FCOLS * FROWS))
    h.append("extern const u16 pal_fighter_p1[16], pal_fighter_p2[16], pal_fx[16], pal_sky[16], pal_city[16], pal_street[16], pal_hud[16];\n")
    h.append("\n#endif\n")
    open(os.path.join(GEN, "assets.h"), "w").write("".join(h))

    c = ["/* Generado por tools/make_assets.py: no editar a mano. */\n#include \"assets.h\"\n\n"]
    for name, pal in (("pal_fighter_p1", FIGHTER_PAL), ("pal_fighter_p2", FIGHTER_PAL_P2), ("pal_fx", FX_PAL),
                      ("pal_sky", SKY_PAL), ("pal_city", CITY_PAL), ("pal_street", STREET_PAL), ("pal_hud", HUD_PAL)):
        c.append(c_pal(name, pal))
    c.append("\nconst u16 fighter_tmaps[][%d] = {\n" % (FCOLS * FROWS))
    for t in tmaps:
        c.append("    {" + ", ".join(str(v) for v in t) + "},\n")
    c.append("};\n\nconst frame_t fighter_frames[] = {\n")
    for tm, dur, fl, hit, up, lo in frame_rows:
        c.append("    {%d, %d, %d, {%d, %d, %d, %d}, {%d, %d, %d, %d}, {%d, %d, %d, %d}},\n"
                 % ((tm, dur, fl) + hit + up + lo))
    c.append("};\n\nconst anim_t fighter_anims[] = {\n")
    for name, first, count, loop in anim_rows:
        c.append("    {%d, %d, %d},  /* %s */\n" % (first, count, loop, name))
    c.append("};\n")
    open(os.path.join(GEN, "assets.c"), "w").write("".join(c))

    import json
    idle, _ = draw_pose(POSES["idle0"])
    bbox = idle.point(lambda v: 255 if v else 0).getbbox()
    metrics = {"stand_height_px": bbox[3] - bbox[1], "stand_height_frac": round((bbox[3] - bbox[1]) / 224, 3),
               "feet_row_in_canvas": bbox[3], "anchor_row": AY,
               "idle_frames": len(ANIMS[0][2]), "walk_frames": len(ANIMS[1][2])}
    open(os.path.join(ASSETS, "metrics.json"), "w").write(json.dumps(metrics, indent=1))

    print("tiles: fighter %d (+relleno=%d), fx %d, sky %d, city %d, street %d, fin %d; hud %d; poses %d, frames %d"
          % (len(frames), fused, fx_used, tile_city - tile_sky, tile_street - tile_city, tile_end - tile_street,
             tile_end, hud_count, len(tmaps), len(frame_rows)))


if __name__ == "__main__":
    main()
