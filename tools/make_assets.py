#!/usr/bin/env python3
"""Genera TODOS los assets placeholder del prototipo de pelea.

Salida (determinística, se versiona):
  art/tmp-procedural/<NOMBRE>/  poses del luchador procedural en PNG + anims.json
                       (mismo formato que entrega el arte; lo convierte
                       tools/neosprite.py en assets/char_p1.gif y src/gen/char_p1.c)
  assets/fx.gif        bola de energía, chispa de impacto y sombra
  assets/sky.gif       capa lejana (parallax 1/4)
  assets/city.gif      capa media: edificios y público (parallax 1/2)
  assets/street.gif    capa cercana: piso en perspectiva (parallax 1)
  assets/hud.gif       tiles 8x8 del fix layer: barras de vida y dígitos grandes
  src/gen/assets.h     tiles base, dimensiones de capas
  src/gen/assets.c     paletas de efectos, HUD y mensajes
  src/gen/stage_gen.c  paletas del escenario y mapa de la ciudad con el público animado

El orden de la C-ROM lo define el Makefile y tiene que coincidir con TILE_* acá:
  logo del BIOS (256) -> fx -> proj -> sky -> floor0..4 -> font -> city (con público) -> TILE_END
  -> personajes (char_p1, char_p2: los arma tools/neosprite.py a partir de TILE_END)
Uso: make_assets.py [--poses-only]  (--poses-only: solo exporta las poses procedurales)
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

L_TORSO, L_NECK, R_HEAD = 32, 5, 10
L_UARM, L_FARM = 22, 20
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
        sh = add(neck, (sx + (pose.get("shf", 0) if side == "f" else 0), 3))
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
        sh = j["sh" + s]
        d.ellipse([sh[0] - 8, sh[1] - 7, sh[0] + 8, sh[1] + 8], fill=1)
        d.ellipse([sh[0] - 7, sh[1] - 6, sh[0] + 7, sh[1] + 7], fill=6 if s == "f" else 7)
        capsule(d, j["sh" + s], j["el" + s], 11, SKIN if s == "f" else (3, 4, 4))
        capsule(d, j["el" + s], j["ha" + s], 10, SKIN if s == "f" else (3, 4, 4))
        h = j["ha" + s]
        d.ellipse([h[0] - 8, h[1] - 7, h[0] + 8, h[1] + 7], fill=1)
        d.ellipse([h[0] - 7, h[1] - 6, h[0] + 7, h[1] + 6], fill=13 if s == "f" else 14)
        d.line([(h[0] - 3, h[1] - 5), (h[0] - 3, h[1] + 5)], fill=14)

    def leg(s):
        cols = PANTS if s == "f" else (9, 10, 10)
        capsule(d, j["hp" + s], j["kn" + s], 15, cols)
        capsule(d, j["kn" + s], j["an" + s], 13, cols)
        capsule(d, j["an" + s], j["toe" + s], 9, GLOVE)

    arm("b")
    leg("b")
    # torso: trapecio orientado
    hip, neck, t = j["hip"], j["neck"], j["t"]
    ux, uy = vup(t)
    px, py = -uy, ux                      # perpendicular
    pts = [add(add(hip, (px, py), 11), (0, 0)), add(hip, (px, py), -11),
           add(neck, (px, py), -18), add(neck, (px, py), 18)]
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


GUARD = dict(hy=-52, torso=16, head=-4, arm_f=(58, 118), arm_b=(36, 126), leg_f=(30, 32), leg_b=(-22, 26))


def P(**kw):
    p = dict(GUARD)
    p.update(kw)
    return p


def walk(i, n=6):
    ph = 2 * math.pi * i / n
    s = math.sin(ph)
    return P(hy=-53 + int(abs(math.cos(ph)) * 2), leg_f=(20 * s + 6, 24 + max(0, 18 * math.cos(ph))),
             leg_b=(-20 * s - 6, 20 + max(0, -18 * math.cos(ph))), arm_f=(58 - 6 * s, 118), arm_b=(36 + 6 * s, 126))


CROUCH = dict(hy=-31, torso=20, leg_f=(80, 112), leg_b=(34, 126))

POSES = {
    "idle0": P(), "idle1": P(hy=-51, arm_f=(56, 120)), "idle2": P(hy=-50, arm_f=(54, 122), arm_b=(34, 128)),
    "crouch": P(**CROUCH),
    "crouch_t": P(hy=-42, torso=14, leg_f=(50, 70), leg_b=(10, 80)),
    "prejump": P(hy=-44, torso=12, leg_f=(40, 60), leg_b=(0, 60)),
    "air_up": P(hy=-66, torso=4, leg_f=(64, 110), leg_b=(20, 110), arm_f=(80, 70), arm_b=(60, 90)),
    "air_down": P(hy=-62, torso=0, leg_f=(30, 40), leg_b=(-10, 30), arm_f=(70, 60), arm_b=(40, 80)),
    "p_start": P(torso=14, hx=3, arm_f=(20, 130), arm_b=(30, 100), leg_f=(30, 20)),
    "p_recover": P(torso=24, hx=7, hy=-50, arm_f=(80, 50), arm_b=(-20, 130), leg_f=(42, 40), leg_b=(-30, 6)),
    "p_active": P(torso=36, hx=12, hy=-48, head=-14, shf=9, arm_f=(96, -4), arm_b=(-50, 140), leg_f=(50, 52), leg_b=(-34, 0)),
    "k_start": P(torso=-6, hy=-54, leg_f=(96, 140), leg_b=(-8, 14), arm_f=(40, 120), arm_b=(-20, 100)),
    "k_active": P(torso=-30, hx=-6, hy=-54, head=12, leg_f=(96, 0), leg_b=(-12, 20), arm_f=(-20, 60), arm_b=(-70, 40)),
    "cp_start": P(**CROUCH, arm_f=(40, 100)),
    "cp_active": P(**dict(CROUCH, torso=26), arm_f=(96, 0)),
    "jk_active": P(hy=-62, torso=-6, leg_f=(58, 0), leg_b=(30, 110), arm_f=(60, 80), arm_b=(20, 90)),
    "fb_wind": P(torso=-6, hx=-3, arm_f=(-40, 70), arm_b=(-50, 60), leg_f=(24, 10), leg_b=(-20, 6)),
    "fb_release": P(torso=22, hx=6, arm_f=(92, 0), arm_b=(84, 8), leg_f=(38, 20), leg_b=(-30, 0)),
    "block": P(torso=-8, hx=-4, head=-8, arm_f=(40, 135), arm_b=(70, 110), leg_f=(24, 20), leg_b=(-22, 14)),
    "cblock": P(**dict(CROUCH, torso=6), head=-8, arm_f=(40, 135), arm_b=(70, 110)),
    "hit0": P(torso=-38, hx=-10, hy=-50, head=-24, arm_f=(-40, 20), arm_b=(-70, 20), leg_f=(40, 10), leg_b=(-24, 30)),
    "hit1": P(torso=-24, hx=-6, hy=-51, head=-14, arm_f=(-10, 50), arm_b=(-40, 40), leg_f=(34, 16), leg_b=(-22, 24)),
    "chit": P(**dict(CROUCH, torso=-20), head=-22, arm_f=(-30, 40), arm_b=(-60, 30)),
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
    ("PUNCH", 0, [("p_start", 3, 0), ("p_active", 3, F_ACTIVE), ("p_recover", 6, 0)], "haf"),
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


# Carpeta y número de frame de cada pose al exportarla (mismo contrato que el
# arte final, ver tools/README-neosprite.md). Cada animación toma sus poses de
# una sola carpeta; las poses compartidas (k_start, kd0...) se reusan con seq.
POSE_SRC = {
    "idle0": ("idle", 0), "idle1": ("idle", 1), "idle2": ("idle", 2),
    "crouch_t": ("crouch_t", 0), "crouch": ("crouch", 0), "prejump": ("prejump", 0),
    "air_up": ("jump", 0), "air_down": ("jump", 1),
    "p_start": ("punch", 0), "p_active": ("punch", 1), "p_recover": ("punch", 2),
    "k_start": ("kick", 0), "k_active": ("kick", 1),
    "cp_start": ("cpunch", 0), "cp_active": ("cpunch", 1),
    "jk_active": ("jkick", 0),
    "fb_wind": ("fireball", 0), "fb_release": ("fireball", 1),
    "block": ("block", 0), "cblock": ("cblock", 0),
    "hit0": ("hit", 0), "hit1": ("hit", 1), "chit": ("chit", 0),
    "kd0": ("knockdown", 0), "kd1": ("knockdown", 1), "lying": ("knockdown", 2), "getup": ("knockdown", 3),
    "win0": ("win", 0), "win1": ("win", 1),
}
POSE_SRC.update({"walk%d" % i: ("walk", i) for i in range(6)})
FLAG_NAMES = [(F_ACTIVE, "ACTIVE"), (F_LOW, "LOW"), (F_OVERHEAD, "OVERHEAD"), (F_SPAWN, "SPAWN")]

# personajes procedurales: nombre -> paleta (P2 es un palette swap, como hoy)
PROCEDURAL_CHARS = {"ROBOCLICK": FIGHTER_PAL, "NINJAODA": FIGHTER_PAL_P2}
PROC_DIR = os.path.join(ROOT, "art", "tmp-procedural")
EXPORT_W = 176


def export_procedural(name, pal, root=PROC_DIR):
    """Exporta las poses como PNG RGBA de 112x128 (fondo transparente, cámara
    fija, ancla en 56,124) y un anims.json con duraciones y flags."""
    import json
    import shutil
    out = os.path.join(root, name)
    if os.path.isdir(out):
        shutil.rmtree(out)
    rgba = [tuple(c) + (255,) for c in pad16(pal)]
    rgba[0] = (0, 0, 0, 0)
    # lienzo más ancho que el de 112 px original: el puño del golpe y el pie
    # de la patada ya no se cortan en el borde (la hitbox sale del alfa)
    global FW, AX
    old = FW, AX
    FW, AX = EXPORT_W, EXPORT_W // 2
    for pose, (folder, idx) in POSE_SRC.items():
        img, _ = draw_pose(POSES[pose])
        d = os.path.join(out, folder)
        os.makedirs(d, exist_ok=True)
        rgb = Image.new("RGBA", img.size)
        rgb.putdata([rgba[v] for v in img.tobytes()])
        rgb.save(os.path.join(d, "%02d.png" % idx))
    FW, AX = old
    anims = {}
    for aname, loop, seq, _limb in ANIMS:
        folders = {POSE_SRC[p][0] for p, _, _ in seq}
        assert len(folders) == 1, aname
        anims[aname] = {
            "src": folders.pop(),
            "seq": [POSE_SRC[p][1] for p, _, _ in seq],
            "dur": [d for _, d, _ in seq],
            "flags": ["|".join(n for bit, n in FLAG_NAMES if fl & bit) for _, _, fl in seq],
            "loop": bool(loop),
        }
    meta = {"_comment": "Generado por tools/make_assets.py (luchador procedural).",
            "anchor": [EXPORT_W // 2, AY], "anims": anims}
    with open(os.path.join(out, "anims.json"), "w") as fh:
        fh.write('{\n "_comment": %s,\n "anchor": %s,\n "anims": {\n' % (json.dumps(meta["_comment"]), json.dumps(meta["anchor"])))
        fh.write(",\n".join("  %s: %s" % (json.dumps(k), json.dumps(v)) for k, v in anims.items()))
        fh.write("\n }\n}\n")
    return out


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
    for f in range(3):                          # chispa de golpe: x = 96, 128, 160
        ox = 96 + f * 32
        r = [15, 15, 13][f]
        pts = []
        for k in range(16):
            a = k * math.pi / 8 + f * 0.25
            rr = r if k % 2 == 0 else r * [0.55, 0.4, 0.3][f]
            pts.append((ox + 16 + rr * math.cos(a), 16 + rr * math.sin(a)))
        d.polygon(pts, fill=[8, 8, 9][f], outline=1)
        inner = [(ox + 16 + (x - ox - 16) * 0.72, 16 + (y - 16) * 0.72) for x, y in pts]
        d.polygon(inner, fill=[7, 7, 8][f])
        d.ellipse([ox + 16 - 5 + f, 11 + f, ox + 16 + 5 - f, 21 - f], fill=[6, 6, 7][f])
        d.ellipse([ox + 16 - 2, 14, ox + 16 + 2, 18], fill=[2, 6, 7][f])
    # sombra con trama (en Neo Geo no hay transparencia): x = 192..223, y 8..24
    for y in range(10, 22):
        for x in range(192, 224):
            if ((x - 208) / 15.0) ** 2 + ((y - 16) / 5.5) ** 2 <= 1 and (x + y) % 2 == 0:
                img.putpixel((x, y), 10)
    # bloqueo: destello de escudo cian con forma de rombo, x = 224
    cx = 224 + 16
    d.polygon([(cx, 1), (cx + 14, 16), (cx, 31), (cx - 14, 16)], fill=1)
    d.polygon([(cx, 3), (cx + 12, 16), (cx, 29), (cx - 12, 16)], fill=4)
    d.polygon([(cx, 7), (cx + 8, 16), (cx, 25), (cx - 8, 16)], fill=3)
    d.polygon([(cx, 11), (cx + 4, 16), (cx, 21), (cx - 4, 16)], fill=2)
    d.line([(cx - 15, 16), (cx + 15, 16)], fill=2)
    tiles = tiles_of(img)                      # fila 0 y fila 1 de 16px
    save_gif(img, "fx.gif")
    return len(tiles)




PROJ_PAL = [(255, 0, 255), (10, 10, 40), (255, 255, 255), (190, 240, 255), (110, 200, 255),
            (40, 120, 255), (20, 50, 190), (60, 30, 140), (150, 110, 255), (220, 200, 255)]


def build_proj():
    img = new_p(48 * 3, 48, PROJ_PAL)
    d = ImageDraw.Draw(img)
    for f in range(3):
        ox, cx, cy = f * 48, f * 48 + 30, 24
        for k in range(5):                                          # estela hacia atrás
            tx = cx - 14 - k * 5
            r = 9 - k * 1.5 + (f % 2)
            d.ellipse([tx - r, cy - r * 0.6 + (k % 2) * 2, tx + r, cy + r * 0.6 + (k % 2) * 2], fill=[7, 6, 7, 1, 7][k])
        r = 16 + f
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=1)          # halo
        d.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], fill=6)
        d.ellipse([cx - r + 5, cy - r + 5, cx + r - 5, cy + r - 5], fill=5)
        d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=4)
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=3)
        d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=2)
        for k in range(6):                                          # rayos que giran
            a = k * math.pi / 3 + f * 0.5
            d.line([(cx + 8 * math.cos(a), cy + 8 * math.sin(a)), (cx + (r - 1) * math.cos(a), cy + (r - 1) * math.sin(a))], fill=9)
        for k in range(8):
            a = k * math.pi / 4 + f
            d.point([(cx + (r + 3) * math.cos(a), cy + (r + 3) * math.sin(a))], fill=8)
    save_gif(img, "proj.gif")
    return 9 * 3


# --------------------------------------------------------------------------
# escenario: tres capas con parallax
# --------------------------------------------------------------------------

CAM_RANGE = 192                                # recorrido de cámara en px
# nombre, ratio en dieciseisavos, alto en tiles, y en pantalla
LAYERS = [
    ("sky", 4, 9, 0),
    ("city", 8, 10, 16),
    ("floor0", 10, 1, 144),
    ("floor1", 12, 1, 160),
    ("floor2", 14, 1, 176),
    ("floor3", 16, 1, 192),     # la franja donde apoyan los pies: ratio 1
    ("floor4", 18, 1, 208),
]
CAM_CENTER = CAM_RANGE // 2


def layer_cols(num):
    return (320 + (CAM_RANGE * num) // 16 + 15) // 16


SKY_PAL = [(0, 0, 0), (32, 20, 64), (60, 32, 96), (104, 48, 120), (160, 64, 120), (220, 96, 104),
           (255, 150, 90), (255, 206, 120), (255, 240, 190), (70, 50, 100), (110, 80, 130),
           (48, 36, 80), (255, 255, 230), (190, 110, 140)]
CITY_PAL = [(0, 0, 0), (122, 86, 136), (128, 92, 140), (136, 100, 148), (146, 110, 156), (170, 132, 158),
            (158, 120, 152), (150, 130, 170), (230, 50, 60), (255, 255, 240), (60, 40, 50),
            (120, 70, 50), (220, 150, 100), (60, 170, 240), (30, 20, 30)]
STREET_PAL = [(0, 0, 0), (30, 24, 34), (60, 50, 62), (96, 82, 90), (128, 110, 108),
              (172, 152, 138), (226, 210, 186), (240, 228, 200), (90, 70, 60), (160, 50, 40),
              (250, 210, 70), (16, 12, 20), (60, 52, 110), (120, 108, 170)]


def dither_band(d, x0, y0, x1, y1, c_top, c_bot):
    """Degradé de dos colores con trama ordenada (look de 16 bits)."""
    h = y1 - y0
    bayer = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
    for y in range(y0, y1):
        t = (y - y0) / max(1, h - 1)
        for x in range(x0, x1):
            d.point([(x, y)], fill=c_bot if t * 16 > bayer[y % 4][x % 4] else c_top)


def build_sky():
    w, h = layer_cols(4) * 16, 9 * 16
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


CROWD_Y, CROWD_H, CROWD_FRAMES = 96, 56, 4      # público: filas 96..151 de city (pantalla 112..167)


def build_city():
    """Devuelve (base, [4 cuadros de público]) en RGBA: la base es la ciudad
    sin gente; cada cuadro del público es de 416x56 con transparencia. Los
    compone y los auto-anima tools/neosprite.py (build_city_layer)."""
    w, h = layer_cols(8) * 16, 10 * 16
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
    bx = 36                                     # cartel lateral, fuera de la zona de la pelea
    d.rectangle([bx, 22, bx + 44, 58], fill=8, outline=1)
    d.rectangle([bx + 3, 25, bx + 41, 55], fill=10)
    d.ellipse([bx + 10, 28, bx + 34, 52], outline=9, width=3)
    d.line([(bx + 22, 30), (bx + 22, 50)], fill=9, width=3)
    # baranda
    d.rectangle([0, 128, w, 131], fill=7)
    for px in range(0, w, 12):
        d.line([(px, 131), (px, 150)], fill=7, width=2)
    d.rectangle([0, 150, w, h], fill=14)
    state = rnd.getstate()
    frames = []
    for f in range(CROWD_FRAMES):                                          # público que salta y alienta
        rnd.setstate(state)
        cr = new_p(w, CROWD_H, CITY_PAL, 0)
        cd = ImageDraw.Draw(cr)
        for k, px in enumerate(range(4, w, 9)):
            py = 104 + rnd.randrange(-4, 5) - CROWD_Y + [0, -1, -2, -1][(f + k) % 4]
            shirt = rnd.choice([7, 6, 11, 12, 3, 5])
            skin = rnd.choice([12, 11, 12])
            r = rnd.random()
            cd.rectangle([px - 4, py + 8, px + 4, 149 - CROWD_Y], fill=shirt, outline=1)
            cd.ellipse([px - 4, py, px + 4, py + 9], fill=skin, outline=1)
            if r < 0.3 or (r < 0.65 and (f + k // 3) % 4 in (1, 2)):      # brazos arriba (ola)
                cd.line([(px + 3, py + 9), (px + 7, py - 3 - (f + k) % 2 * 2)], fill=12, width=2)
        frames.append(to_rgba(cr, CITY_PAL))
    return to_rgba(img, CITY_PAL, opaque0=False), frames


def to_rgba(img, pal, opaque0=False):
    rgba = [tuple(c) + (255,) for c in pad16(pal)]
    if not opaque0:
        rgba[0] = (0, 0, 0, 0)
    out = Image.new("RGBA", img.size)
    out.putdata([rgba[v] for v in img.tobytes()])
    return out


def floor_screen(sx, sy):
    """Color del piso en el punto de pantalla (sx, sy) con la cámara centrada.
    Perspectiva real: el punto de fuga está sobre el centro de la pantalla."""
    vpx, vpy = 160.0, 40.0
    if sy < 154:
        return 6 if sy < 151 else 1                       # cordón
    z = 1.0 / (sy - vpy)                                    # profundidad
    wx = (sx - vpx) * z * 120.0                             # coordenada del mundo sobre el piso
    wz = z * 2400.0
    gx, gz = math.floor(wx / 28.0), math.floor(wz / 4.0)
    fx, fz = wx / 28.0 - gx, wz / 4.0 - gz
    if fx < 0.07 or fz < 0.1:
        return 11                                           # junta oscura
    if fx < 0.13 or fz < 0.18:
        return 6                                            # bisel claro
    base = 4 if (gx + gz) % 2 == 0 else 5
    if sy < 172:
        base -= 1                                           # más oscuro lejos
    return base


def build_street():
    """Genera las 5 franjas del piso. Cada franja se desplaza a su propio ritmo;
    con la cámara al centro las cinco arman una única imagen en perspectiva."""
    rnd = random.Random(3)
    for name, num, rows, y in LAYERS[2:]:
        w = layer_cols(num) * 16
        img = new_p(w, 16, STREET_PAL, 3)
        px = img.load()
        off = (CAM_CENTER * num) // 16                      # scroll de la franja con la cámara centrada
        for u in range(w):
            sx = u - off
            for yy in range(16):
                px[u, yy] = floor_screen(sx, y + yy)
        for _ in range(w // 12):                            # papelitos
            u, yy = rnd.randrange(w), rnd.randrange(16)
            if y + yy > 156:
                px[u, yy] = rnd.choice([10, 9, 13, 7])
        save_gif(img, name + ".gif")


# --------------------------------------------------------------------------
# HUD: tiles 8x8 del fix layer
# --------------------------------------------------------------------------

HUD_PAL = [(255, 0, 255), (16, 12, 20), (170, 255, 90), (60, 180, 40), (120, 20, 30),
           (60, 10, 20), (255, 255, 255), (150, 150, 170), (255, 240, 120), (255, 170, 30),
           (170, 60, 10), (230, 40, 40), (80, 80, 100)]
HUD_BAR_SOLID = 1                              # + estado*2 + fila (F=0, D=1, E=2)
HUD_BAR_EDGE = 7                               # + (par*7 + m-1)*2 + fila, pares en BAR_PAIRS
HUD_CAP_L = 7 + 6 * 7 * 2
HUD_CAP_R, HUD_WIN_OFF, HUD_WIN_ON = HUD_CAP_L + 1, HUD_CAP_L + 2, HUD_CAP_L + 3
HUD_DIGITS = HUD_CAP_L + 4                     # 10 dígitos x 12 tiles (3x4)
HUD_MEDAL = HUD_DIGITS + 120                   # apagado +0..3, encendido +4..7 (2x2)

DIGIT_SEGS = {  # segmentos estilo 7 seg: a b c d e f g
    0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc", 5: "afgcd",
    6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg"}


BAR_COL = {"F": (2, 3), "D": (9, 10), "E": (4, 5)}     # (luz, sombra) por estado


def bar_tile(states, row):
    """states: 8 letras F (lleno), D (daño reciente), E (vacío); row 0 arriba, 1 abajo."""
    t = new_p(8, 8, HUD_PAL)
    d = ImageDraw.Draw(t)
    d.rectangle([0, 0, 7, 7], fill=1)
    for x in range(8):
        light, dark = BAR_COL[states[x]]
        if row == 0:
            d.line([(x, 2), (x, 3)], fill=6 if states[x] == "F" else light)
            d.line([(x, 4), (x, 7)], fill=light)
        else:
            d.line([(x, 0), (x, 4)], fill=light if x % 2 or states[x] != "F" else light)
            d.line([(x, 5), (x, 5)], fill=dark)
    return t


def digit_img(n):
    img = new_p(24, 32, HUD_PAL, 1)                     # placa oscura propia
    d = ImageDraw.Draw(img)
    k = 1.5
    seg = {"a": [(3, 1), (12, 1), (10, 4), (5, 4)], "d": [(3, 22), (12, 22), (10, 19), (5, 19)],
           "g": [(4, 11), (11, 11), (12, 12), (11, 13), (4, 13), (3, 12)],
           "f": [(1, 3), (4, 5), (4, 10), (1, 11)], "b": [(14, 3), (11, 5), (11, 10), (14, 11)],
           "e": [(1, 13), (4, 14), (4, 18), (1, 20)], "c": [(14, 13), (11, 14), (11, 18), (14, 20)]}
    tr = lambda pts: [(x * k + 1, y * k + 0.5) for x, y in pts]
    for s_ in DIGIT_SEGS[n]:
        d.polygon(tr(seg[s_]), fill=9 if s_ in "edc" else 8, outline=10)
    return img


BAR_PAIRS = ["ED", "DF", "EF", "FD", "DE", "FE"]


def build_hud():
    tiles = [new_p(8, 8, HUD_PAL)]                                        # 0 vacío
    for st in "FDE":                                                      # 1..6 sólidos (estado, fila)
        for row in (0, 1):
            tiles.append(bar_tile(st * 8, row))
    for pair in BAR_PAIRS:                                                # 7.. bordes: m px del primer estado
        for m in range(1, 8):
            for row in (0, 1):
                tiles.append(bar_tile(pair[0] * m + pair[1] * (8 - m), row))
    assert len(tiles) == HUD_CAP_L
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
    for n in range(10):                                                   # dígitos 2x3
        tiles.extend(tiles_of(digit_img(n), 8, 8))
    for on in (0, 1):                                                     # medallones 2x2 de round ganado
        m = new_p(16, 16, HUD_PAL)
        d = ImageDraw.Draw(m)
        d.ellipse([0, 0, 15, 15], fill=1)
        d.ellipse([1, 1, 14, 14], fill=9 if on else 7)
        d.ellipse([3, 3, 12, 12], fill=8 if on else 12)
        if on:
            d.polygon([(8, 4), (9, 7), (12, 7), (10, 9), (11, 12), (8, 10), (5, 12), (6, 9), (4, 7), (7, 7)], fill=6)
        tiles.extend(tiles_of(m, 8, 8))
    strip = new_p(8 * len(tiles), 8, HUD_PAL)
    for i, t in enumerate(tiles):
        strip.paste(t, (i * 8, 0))
    save_gif(strip, "hud.gif")
    return len(tiles)



# --------------------------------------------------------------------------
# fuente grande para mensajes (ROUND, FIGHT!, K.O.): bloques 5x7 propios
# --------------------------------------------------------------------------

MSG_PAL = [(255, 0, 255), (16, 8, 16), (255, 255, 240), (255, 236, 90), (255, 170, 30),
           (230, 70, 20), (120, 20, 20), (60, 10, 20)]
FONT_CHARS = " ABCDEFGHIJKLMNOPRSTUVWXZ0123456789!."
GLYPHS = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10011", "10101", "10101", "10101", "11001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    ".": ["00000", "00000", "00000", "00000", "00000", "00000", "00100"],
    " ": ["00000"] * 7,
}


def build_font():
    n = len(FONT_CHARS)
    img = new_p(32 * n, 32, MSG_PAL)
    for gi, ch in enumerate(FONT_CHARS):
        cell = new_p(32, 32, MSG_PAL)
        mask = [[0] * 32 for _ in range(32)]
        for r, row in enumerate(GLYPHS[ch]):
            for c, bit in enumerate(row):
                if bit == "1":
                    for yy in range(4):
                        for xx in range(4):
                            mask[2 + r * 4 + yy][5 + c * 4 + xx] = 1
        px = cell.load()
        for y in range(32):                     # sombra desplazada
            for x in range(32):
                if y >= 2 and x >= 2 and mask[y - 2][x - 2]:
                    px[x, y] = 7
        for y in range(32):                     # contorno
            for x in range(32):
                if any(0 <= y + dy < 32 and 0 <= x + dx < 32 and mask[y + dy][x + dx]
                       for dy in (-1, 0, 1) for dx in (-1, 0, 1)) and not mask[y][x]:
                    px[x, y] = 1
        for y in range(32):                     # relleno con degradé vertical
            for x in range(32):
                if mask[y][x]:
                    t = (y - 2) / 28.0
                    px[x, y] = 2 if t < 0.12 else 3 if t < 0.4 else 4 if t < 0.7 else 5 if t < 0.9 else 6
        img.paste(cell, (gi * 32, 0))
    save_gif(img, "font.gif")
    return n


# --------------------------------------------------------------------------
# salida C
# --------------------------------------------------------------------------

def c_pal(name, pal):
    return "const u16 %s[16] = {%s};\n" % (name, ", ".join("0x%04x" % packed15(c) for c in pad16(pal)))


def stage_gen():
    """src/gen/stage_gen.c/.h: paletas del escenario (de los GIF de sky y
    floor0, y de assets/city.json para la ciudad y el público) y el mapa de
    tiles de la ciudad. Lo usa también tools/neosprite.py stage."""
    import json
    city = json.load(open(os.path.join(ASSETS, "city.json")))
    out = ["/* Generado por tools/make_assets.py o tools/neosprite.py stage: no editar a mano. */\n",
           '#include "gen/stage_gen.h"\n\n']
    for var, gif in (("pal_sky", "sky.gif"), ("pal_street", "floor0.gif")):
        img = Image.open(os.path.join(ASSETS, gif))
        p = img.getpalette()[:48]
        p += [0] * (48 - len(p))
        out.append(c_pal(var, [tuple(p[i:i + 3]) for i in range(0, 48, 3)]))
    out.append(c_pal("pal_city", [tuple(c) for c in city["pal_city"]]))
    out.append(c_pal("pal_crowd", [tuple(c) for c in city["pal_crowd"]]))
    m = city["map"]
    out.append("\n/* ciudad: fila por fila; bits 0-13 tile desde TILE_CITY, bit 14 auto-animación\n"
               "   de 4 cuadros, bit 15 paleta del público */\nconst u16 city_map[%d] = {\n" % len(m))
    cols = city["cols"]
    for i in range(0, len(m), cols):
        out.append("    " + ", ".join("0x%04x" % v for v in m[i:i + cols]) + ",\n")
    out.append("};\n")
    open(os.path.join(GEN, "stage_gen.c"), "w").write("".join(out))
    h = ["/* Generado por tools/make_assets.py o tools/neosprite.py stage: no editar a mano. */\n",
         "#ifndef GEN_STAGE_GEN_H\n#define GEN_STAGE_GEN_H\n#include <ngdevkit/types.h>\n",
         "#define CITY_TILES %d          /* tiles de city.gif en la C-ROM */\n" % city["tiles"],
         "#define CROWD_ANIM_SPEED %d     /* REG_LSPCMODE: cuadro nuevo cada n+1 frames */\n" % city["speed"],
         "#define CROWD_ANIM_TILES %d\n" % city["anim_groups"],
         "extern const u16 city_map[%d];\n" % len(m),
         "extern const u16 pal_sky[16], pal_city[16], pal_crowd[16], pal_street[16];\n#endif\n"]
    open(os.path.join(GEN, "stage_gen.h"), "w").write("".join(h))


def export_stage_sources(city_base, crowd):
    d = os.path.join(PROC_DIR, "stage")
    os.makedirs(os.path.join(d, "crowd"), exist_ok=True)
    city_base.save(os.path.join(d, "city.png"))
    for i, f in enumerate(crowd):
        f.save(os.path.join(d, "crowd", "%02d.png" % i))


def main():
    import sys
    for name, pal in PROCEDURAL_CHARS.items():
        export_procedural(name, pal)
    if "--poses-only" in sys.argv:
        print("poses procedurales en", PROC_DIR)
        return
    os.makedirs(GEN, exist_ok=True)
    tile_fx = 256
    fx_used = build_fx(tile_fx)
    tile_proj = tile_fx + fx_used
    proj_used = build_proj()
    tile_sky = tile_proj + proj_used
    sky = build_sky()
    tile_street = tile_sky + (sky.size[0] // 16) * (sky.size[1] // 16)
    build_street()
    floor_tiles = {}
    t = tile_street
    for name, num, rows, y in LAYERS[2:]:
        floor_tiles[name] = t
        t += layer_cols(num) * rows
    tile_font = t
    font_n = build_font()
    tile_city = tile_font + font_n * 4
    city_base, crowd = build_city()
    export_stage_sources(city_base, crowd)
    import neosprite
    neosprite.build_city_layer(city_base, crowd, tile_city)
    hud_count = build_hud()

    h = []
    h.append("/* Generado por tools/make_assets.py: no editar a mano. */\n")
    h.append("#ifndef GEN_ASSETS_H\n#define GEN_ASSETS_H\n#include <ngdevkit/types.h>\n\n")
    h.append('#include "gen/stage_gen.h"\n\n')
    h.append("/* orden de la C-ROM (Makefile CROM_PARTS): fx proj sky floor0..4 font city char_p1 char_p2.\n"
             "   city.gif empieza con relleno para que sus grupos animados queden alineados a 4.\n"
             "   TILE_END: primer tile libre; ahí empiezan los personajes (src/gen/char_p1.c) */\n")
    h.append("#define TILE_FX %d\n#define TILE_PROJ %d\n#define TILE_SKY %d\n#define TILE_STREET %d\n#define TILE_FONT %d\n#define TILE_CITY %d\n#define TILE_END (TILE_CITY + CITY_TILES)\n\n"
             % (tile_fx, tile_proj, tile_sky, tile_street, tile_font, tile_city))
    h.append("/* fuente de mensajes: glifo i ocupa 2x2 tiles; fila de abajo a FONT_GLYPHS*2 */\n#define FONT_GLYPHS %d\nextern const u8 font_map[96];\n\n" % font_n)
    h.append("/* efectos: tiles de 16x16 en fx.gif (2 filas de %d) */\n" % ((32 * 7 + 32) // 16))
    h.append("#define FX_ROW %d\n#define FX_FIREBALL 0\n#define FX_SPARK 6\n#define FX_SHADOW 12\n#define FX_BLOCK 14\n\n" % ((32 * 7 + 32) // 16))
    h.append("#define CAM_RANGE %d\n#define NUM_LAYERS %d\n" % (CAM_RANGE, len(LAYERS)))
    tbase = {"sky": tile_sky, "city": tile_city}
    tbase.update(floor_tiles)
    h.append("/* capas: tile base, columnas, filas, ratio (dieciseisavos de la cámara), y.\n"
             "   La ciudad (capa 1) usa city_map en vez de tiles consecutivos. */\n#define LAYER_CITY 1\n#define LAYER_TABLE \\\n")
    for n, num, ht, y in LAYERS:
        h.append("    {%s, %d, %d, %d, %d}, \\\n" % ("TILE_CITY" if n == "city" else tbase[n], layer_cols(num), ht, num, y))
    h.append("\n#define STAGE_W %d\n" % (320 + CAM_RANGE))
    h.append("\n#define HUD_TILES %d\n#define HUD_BAR_SOLID %d\n#define HUD_BAR_EDGE %d\n"
             "/* pares de borde: ED DF EF FD DE FE */\n"
             "#define HUD_CAP_L %d\n#define HUD_CAP_R %d\n#define HUD_WIN_OFF %d\n#define HUD_WIN_ON %d\n#define HUD_DIGITS %d\n#define HUD_MEDAL %d\n\n"
             % (hud_count, HUD_BAR_SOLID, HUD_BAR_EDGE, HUD_CAP_L, HUD_CAP_R, HUD_WIN_OFF, HUD_WIN_ON, HUD_DIGITS, HUD_MEDAL))
    h.append("extern const u16 pal_fx[16], pal_proj[16], pal_hud[16], pal_msg[16];\n")
    h.append("\n#endif\n")
    open(os.path.join(GEN, "assets.h"), "w").write("".join(h))

    c = ["/* Generado por tools/make_assets.py: no editar a mano. */\n#include \"assets.h\"\n\n"]
    for name, pal in (("pal_fx", FX_PAL), ("pal_proj", PROJ_PAL), ("pal_hud", HUD_PAL), ("pal_msg", MSG_PAL)):
        c.append(c_pal(name, pal))
    fm = [FONT_CHARS.index(chr(i)) if chr(i) in FONT_CHARS else 0 for i in range(32, 128)]
    c.append("\nconst u8 font_map[96] = {" + ", ".join(str(v) for v in fm) + "};\n")
    open(os.path.join(GEN, "assets.c"), "w").write("".join(c))
    print("tiles: fx %d, proj %d, ciudad desde %d; hud %d; poses y escenario procedurales en %s"
          % (fx_used, proj_used, tile_city, hud_count, PROC_DIR))


if __name__ == "__main__":
    main()
