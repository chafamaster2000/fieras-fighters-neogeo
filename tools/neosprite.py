#!/usr/bin/env python3
"""neosprite: convierte arte PNG en datos Neo Geo para este motor.

Subcomandos (detalle y contrato de entrada en tools/README-neosprite.md):
  char <dir> --name ROBOCLICK     personaje: paleta de 15 colores, ancla fija, tiles
                             16x16 con dedupe por flips, recorte por frame, cajas
                             -> assets/char_<slot>.gif, assets/char_<slot>.json,
                                src/gen/char_<slot>.c/.h (y assets/metrics.json para P1)
  stage <dir>                sky.png, city.png, floor.png -> GIF de las 7 capas
  preview <nombre|slot>      visor HTML autocontenido en doc/viewer/<NOMBRE>.html

Solo Python 3 + Pillow. Ideas de formato tomadas de cómo KOF arma sus luchadores:
ancho variable por frame, flips por tile en SCB1,
una paleta por personaje y un guion de animación con duraciones y cajas.
"""
import argparse
import base64
import io
import json
import math
import os
import re
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
ASSETS = os.path.join(ROOT, "assets")
GEN = os.path.join(ROOT, "src", "gen")
VIEWER_DIR = os.path.join(ROOT, "doc", "viewer")
sys.path.insert(0, HERE)
import make_assets as MA  # noqa: E402  (constantes del escenario, packed15)

# Nombre -> ranura en la C-ROM. P1 va primero, P2 a continuación.
SLOTS = {"ROBOCLICK": "p1", "NINJAODA": "p2"}
PROC_DIR = os.path.join(ROOT, "art", "tmp-procedural")
# frame data del juego (tools/framedata.json): pisa las duraciones del arte en los golpes
_fd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "framedata.json")
FRAMEDATA = {k: v for k, v in (json.load(open(_fd)) if os.path.exists(_fd) else {}).items() if not k.startswith("_")}
TARGET_H = (110, 118)          # alto parado aceptado sin reescalar (KOF)
TARGET_H_DEFAULT = 114
ALPHA_MIN = 128


# --------------------------------------------------------------------------
# contrato con el motor: se lee de src/character.h
# --------------------------------------------------------------------------

def engine_contract():
    src = open(os.path.join(ROOT, "src", "character.h")).read()
    body = re.search(r"enum\s*{([^}]*)}", src).group(1)
    anims = [a for a in re.findall(r"ANIM_(\w+)", body) if a != "COUNT"]
    flags = {k: int(v) for k, v in re.findall(r"#define FF_(\w+)\s+(\d+)", src)}
    hw_cols = int(re.search(r"#define FIGHTER_HW_COLS\s+(\d+)", src).group(1))
    return anims, flags, hw_cols


ANIMS, FLAGS, HW_COLS = engine_contract()

# Dónde busca cada animación en la carpeta del personaje, en orden. El
# selector elige qué frames de la carpeta usa (ver README-neosprite.md).
CANDIDATES = {
    "IDLE": [("idle", "all")],
    "WALK_F": [("walk", "all"), ("walk_f", "all")],
    "WALK_B": [("walk_b", "all"), ("walk", "rev")],
    "CROUCH_T": [("crouch_t", "all"), ("crouch", "but_last")],
    "CROUCH": [("crouch", "last")],
    "PREJUMP": [("prejump", "all"), ("crouch_t", "first"), ("crouch", "first")],
    "AIR_UP": [("jump_up", "all"), ("jump", "half1")],
    "AIR_DOWN": [("jump_down", "all"), ("jump", "half2")],
    "LAND": [("land", "all"), ("prejump", "all"), ("crouch_t", "first"), ("crouch", "first")],
    "PUNCH": [("punch", "all")],
    "KICK": [("kick", "all")],
    "CPUNCH": [("cpunch", "all"), ("crouch_punch", "all")],
    "JKICK": [("jkick", "all"), ("jump_kick", "all"), ("kick", "active")],
    "FIREBALL": [("fireball", "all"), ("special", "all")],
    "BLOCK": [("block", "all")],
    "CBLOCK": [("cblock", "all"), ("crouch_block", "all"), ("crouch", "last")],
    "HIT": [("hit", "all")],
    "CHIT": [("chit", "all"), ("crouch_hit", "all"), ("hit", "all")],
    "KNOCKDOWN": [("knockdown", "all")],
    "KO": [("ko", "all"), ("knockdown", "but_last")],
    "WIN": [("win", "all"), ("idle", "all")],
}
# referencia para la hitbox (silueta "en reposo" de la que sobresale el golpe)
HIT_REF = {"CPUNCH": "CROUCH", "JKICK": "AIR_DOWN"}


# --------------------------------------------------------------------------
# color: OKLab, paleta, Neo Geo
# --------------------------------------------------------------------------

def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def oklab(rgb):
    r, g, b = (_lin(float(v)) for v in rgb)
    l_ = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m_ = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s_ = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l_, m_, s_))
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def d2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def neo_unpack(v):
    """Color de 16 bits Neo Geo -> RGB de 8 bits. Cada canal es de 6 bits:
    5 bits + el bit bajo compartido (!dark), inverso exacto de packed15."""
    nd = 1 - ((v >> 15) & 1)
    r = ((v >> 7) & 0x1e) | ((v >> 14) & 1)
    g = ((v >> 3) & 0x1e) | ((v >> 13) & 1)
    b = ((v << 1) & 0x1e) | ((v >> 12) & 1)
    f = lambda c: ((c << 1 | nd) << 2) | ((c << 1 | nd) >> 4)
    return (f(r), f(g), f(b))


def neo_rgb(rgb):
    return neo_unpack(MA.packed15(rgb))


def quantize(counts, n=15):
    """counts: {rgb: peso}. Devuelve hasta n colores (k-means en OKLab con
    semilla determinística). Si hay n o menos colores, los devuelve tal cual."""
    cols = sorted(counts)
    if len(cols) <= n:
        return cols
    labs = {c: oklab(c) for c in cols}
    # semilla: el color más pesado, después el más lejos ponderado por peso
    centers = [labs[max(cols, key=lambda c: (counts[c], c))]]
    best = {c: d2(labs[c], centers[0]) for c in cols}
    while len(centers) < n:
        c = max(cols, key=lambda c: (math.sqrt(counts[c]) * best[c], c))
        centers.append(labs[c])
        for k in cols:
            best[k] = min(best[k], d2(labs[k], centers[-1]))
    for _ in range(16):
        acc = [[0.0, 0.0, 0.0, 0.0] for _ in centers]
        for c in cols:
            lab = labs[c]
            i = min(range(len(centers)), key=lambda j: d2(lab, centers[j]))
            w = math.sqrt(counts[c])   # raíz: no gasta 3 colores en variantes del contorno
            a = acc[i]
            a[0] += lab[0] * w; a[1] += lab[1] * w; a[2] += lab[2] * w; a[3] += w
        new = [(a[0] / a[3], a[1] / a[3], a[2] / a[3]) if a[3] else centers[i] for i, a in enumerate(acc)]
        if new == centers:
            break
        centers = new
    # cada centro se reemplaza por el color real más cercano (sin colores inventados)
    out = []
    for cen in centers:
        c = min(cols, key=lambda c: (d2(labs[c], cen), c))
        if c not in out:
            out.append(c)
    return out


def sort_palette(cols):
    return sorted(cols, key=lambda c: (oklab(c)[0], c))


class Mapper:
    """Asigna a cada RGB el índice de paleta más cercano en OKLab (con caché)."""

    def __init__(self, pal):
        self.pal = pal                    # lista de RGB, índice 1..len
        self.labs = [oklab(c) for c in pal]
        self.cache = {}

    def __call__(self, rgb):
        i = self.cache.get(rgb)
        if i is None:
            lab = oklab(rgb)
            i = 1 + min(range(len(self.pal)), key=lambda j: d2(lab, self.labs[j]))
            self.cache[rgb] = i
        return i


# --------------------------------------------------------------------------
# imágenes
# --------------------------------------------------------------------------

def frame_files(folder):
    if not os.path.isdir(folder):
        return []
    fs = [f for f in os.listdir(folder) if f.lower().endswith(".png") and re.search(r"\d+", f)]
    return [os.path.join(folder, f) for f in sorted(fs, key=lambda f: int(re.findall(r"\d+", f)[-1]))]


def opaque_bbox(img):
    return img.getchannel("A").point(lambda a: 255 if a >= ALPHA_MIN else 0).getbbox()


def grid_factor(img):
    """Factor k si la imagen es pixel art agrandado k veces (bloques k x k lisos)."""
    w, h = img.size
    for k in range(8, 1, -1):
        if w % k or h % k:
            continue
        small = img.resize((w // k, h // k), Image.NEAREST)
        if small.resize((w, h), Image.NEAREST).tobytes() == img.tobytes():
            return k
    return 1


class Frame:
    """Un PNG de entrada ya escalado, con su ancla y sus píxeles indexados."""

    def __init__(self, path, img, anchor, fallback):
        self.path, self.img, self.anchor, self.fallback = path, img, anchor, fallback
        self.idx = None       # bytes indexados (0 transparente), mismo tamaño que img

    def mask_points(self):
        w, h = self.img.size
        ax, ay = self.anchor
        a = self.img.getchannel("A").tobytes()
        return {(i % w - ax, i // w - ay) for i, v in enumerate(a) if v >= ALPHA_MIN}


class Source:
    """Una carpeta de personaje (arte real o procedural) con su escala y ancla."""

    def __init__(self, path, fallback, anchor=None, height=None, log=print):
        self.path, self.fallback, self.log = path, fallback, log
        self.meta = {}
        for fn in ("anims.json", "anims.yaml"):
            p = os.path.join(path, fn)
            if os.path.exists(p):
                self.meta = load_meta(p)
        self.cache = {}
        idle = frame_files(os.path.join(path, "idle"))
        if not idle:
            raise SystemExit("neosprite: %s no tiene idle/ con PNG (obligatorio)" % path)
        base = Image.open(idle[0]).convert("RGBA")
        self.k = grid_factor(base)
        base = self._down(base)
        bb = opaque_bbox(base)
        if not bb:
            raise SystemExit("neosprite: %s está vacío (fondo sin alfa?)" % idle[0])
        h0 = bb[3] - bb[1]
        want = height or self.meta.get("height")
        if want:
            self.scale = want / h0
        elif TARGET_H[0] <= h0 <= TARGET_H[1] or fallback:
            self.scale = 1.0
        else:
            self.scale = TARGET_H_DEFAULT / h0
        if abs(self.scale - 1.0) < 1e-6:
            self.scale = 1.0
        base = self._rescale(base)
        anc = anchor or self.meta.get("anchor")
        if anc:
            self.anchor = (int(round(anc[0] * self.scale)), int(round(anc[1] * self.scale)))
        else:
            self.anchor = detect_anchor(base)
        self.stand_h = opaque_bbox(base)[3] - opaque_bbox(base)[1]
        if self.k > 1:
            log("  %s: pixel art agrandado x%d, se reduce con nearest" % (rel(path), self.k))
        if self.scale != 1.0:
            log("  %s: alto parado %d px fuera de %d..%d: reescalado nearest x%.3f (mejor entregar al tamaño final)"
                % (rel(path), h0, TARGET_H[0], TARGET_H[1], self.scale))

    def _down(self, img):
        if self.k > 1 and img.size[0] % self.k == 0 and img.size[1] % self.k == 0:
            return img.resize((img.size[0] // self.k, img.size[1] // self.k), Image.NEAREST)
        return img

    def _rescale(self, img):
        if self.scale == 1.0:
            return img
        w, h = img.size
        return img.resize((max(1, round(w * self.scale)), max(1, round(h * self.scale))), Image.NEAREST)

    def folder(self, name):
        return frame_files(os.path.join(self.path, name))

    def frame(self, path):
        f = self.cache.get(path)
        if f is None:
            img = self._rescale(self._down(Image.open(path).convert("RGBA")))
            # alfa binario: lo forzamos por las dudas
            a = img.getchannel("A").point(lambda v: 255 if v >= ALPHA_MIN else 0)
            img.putalpha(a)
            f = self.cache[path] = Frame(path, img, self.anchor, self.fallback)
        return f


def detect_anchor(img):
    """Ancla = centro x de los píxeles de las 4 filas más bajas, y la fila de abajo de los pies."""
    w, h = img.size
    a = img.getchannel("A").tobytes()
    ys = [i // w for i, v in enumerate(a) if v >= ALPHA_MIN]
    yb = max(ys)
    xs = [i % w for i, v in enumerate(a) if v >= ALPHA_MIN and i // w >= yb - 3]
    return ((min(xs) + max(xs) + 1) // 2, yb + 1)


def load_meta(p):
    txt = open(p).read()
    if p.endswith(".json"):
        return json.loads(txt)
    try:
        import yaml  # opcional; si no está, se pide JSON
        return yaml.safe_load(txt)
    except ImportError:
        raise SystemExit("neosprite: %s necesita PyYAML; usá anims.json" % p)


def rel(p):
    return os.path.relpath(p, ROOT)


# --------------------------------------------------------------------------
# guion de animación: qué frames, cuánto dura cada uno, flags
# --------------------------------------------------------------------------

def spread(total, k):
    """Reparte `total` frames de 60 Hz entre k imágenes (cada una >= 1)."""
    k = max(1, min(k, total))
    base, extra = divmod(total, k)
    return [base + (1 if i < extra else 0) for i in range(k)]


def pick(seq, k):
    """k elementos de seq repartidos parejo (conserva primero y último)."""
    if k >= len(seq):
        return list(seq)
    if k == 1:
        return [seq[0]]
    return [seq[round(i * (len(seq) - 1) / (k - 1))] for i in range(k)]


def select(files, sel, active=None):
    n = len(files)
    idx = list(range(n))
    if sel == "all":
        return idx
    if sel == "rev":
        return idx[::-1]
    if sel == "first":
        return idx[:1]
    if sel == "last":
        return idx[-1:]
    if sel == "but_last":
        return idx[:-1] if n > 1 else idx
    if sel == "half1":
        return idx[:(n + 1) // 2]
    if sel == "half2":
        return idx[(n + 1) // 2:] if n > 1 else idx
    if sel == "active":
        return [active if active is not None else n // 2]
    raise ValueError(sel)


def attack(seq, a, startup, active, recovery, flag):
    """Fases de un golpe: arranque, frame activo, recuperación (tiempos del procedural)."""
    pos = seq.index(a) if a in seq else len(seq) // 2
    pre, post = seq[:pos], seq[pos + 1:]
    if not pre:
        pre = [a]
    if not post:
        post = [pre[-1]]
    pre = pick(pre, startup)
    post = pick(post, recovery)
    out = [(i, d, 0) for i, d in zip(pre, spread(startup, len(pre)))]
    out.append((a, active, flag))
    out += [(i, d, 0) for i, d in zip(post, spread(recovery, len(post)))]
    return out, False


def timing(anim, seq, a):
    """Duraciones por defecto (las del luchador procedural) para len(seq) imágenes."""
    F = FLAGS
    n = len(seq)

    def cycle(d, loop=True):
        return [(i, d, 0) for i in seq], loop

    def squeeze(total):
        s = pick(seq, total)
        return [(i, d, 0) for i, d in zip(s, spread(total, len(s)))], False

    def settle(first, last):         # anima y se queda en la última
        if n == 1:
            return [(seq[0], last, 0)], True
        s = pick(seq[:-1], first)
        return [(i, d, 0) for i, d in zip(s, spread(first, len(s)))] + [(seq[-1], last, 0)], False

    if anim in ("IDLE",):
        return cycle(8)
    if anim == "WALK_F":
        return cycle(5)
    if anim == "WALK_B":
        return cycle(6)
    if anim == "WIN":
        return cycle(12)
    if anim == "CROUCH_T":
        return squeeze(3)
    if anim in ("PREJUMP", "LAND"):
        return squeeze(4)
    if anim in ("CROUCH", "BLOCK", "CBLOCK", "CHIT"):
        return settle(3 * (n - 1), 60) if n > 1 else ([(seq[0], 60, 0)], True)
    if anim in ("AIR_UP", "AIR_DOWN"):
        return settle(4 * (n - 1), 60) if n > 1 else ([(seq[0], 60, 0)], True)
    if anim == "HIT":
        return settle(5, 60) if n > 1 else ([(seq[0], 5, 0), (seq[0], 60, 0)], False)
    if anim == "PUNCH":
        return attack(seq, a, 3, 3, 6, F["ACTIVE"])
    if anim == "KICK":
        return attack(seq, a, 5, 4, 10, F["ACTIVE"])
    if anim == "CPUNCH":
        return attack(seq, a, 3, 3, 7, F["ACTIVE"] | F["LOW"])
    if anim == "JKICK":
        fl = F["ACTIVE"] | F["OVERHEAD"]
        if n == 1 or a == seq[0]:
            return [(a, 60, fl)], True
        pre = pick(seq[:seq.index(a)], 3)
        return [(i, d, 0) for i, d in zip(pre, spread(3, len(pre)))] + [(a, 60, fl)], False
    if anim == "FIREBALL":
        pos = seq.index(a) if a in seq else len(seq) // 2
        pre, post = seq[:pos] or [seq[0]], seq[pos + 1:]
        pre = pick(pre, 8)
        out = [(i, d, 0) for i, d in zip(pre, spread(8, len(pre)))]
        out += [(a, 4, F["SPAWN"]), (a, 14, 0)]
        post = pick(post, 8) or [pre[0]]
        out += [(i, d, 0) for i, d in zip(post, spread(8, len(post)))]
        return out, False
    if anim == "KNOCKDOWN":
        if n >= 3:
            s = pick(seq[:-2], 12)
            return [(i, d, 0) for i, d in zip(s, spread(12, len(s)))] + [(seq[-2], 30, 0), (seq[-1], 10, 0)], False
        return [(i, d, 0) for i, d in zip(seq, [22, 30][-n:] if n == 2 else [52])], False
    if anim == "KO":
        return settle(16, 250) if n > 1 else ([(seq[0], 250, 0)], False)
    raise KeyError(anim)


def parse_flags(v):
    if isinstance(v, int):
        return v
    out = 0
    for name in filter(None, re.split(r"[|,+ ]+", v or "")):
        if name.upper() not in FLAGS:
            raise SystemExit("neosprite: flag desconocido %r (válidos: %s)" % (name, ", ".join(FLAGS)))
        out |= FLAGS[name.upper()]
    return out


# --------------------------------------------------------------------------
# cajas
# --------------------------------------------------------------------------

def clamp8(v):
    return max(-127, min(127, int(v)))


def box(x0, y0, x1, y1):
    """(x0, y0) inclusive, (x1, y1) exclusivo -> box_t (x, y, w, h)."""
    return (clamp8(x0), clamp8(y0), clamp8(x1 - x0), clamp8(y1 - y0))


def pct(vals, p):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(p * len(vals)))]


def hurtboxes(pts):
    ys = [p[1] for p in pts]
    top, bot = min(ys), max(ys) + 1
    split = top + (bot - top) // 2
    out = []
    for lo, hi in ((top, split), (split, bot)):
        xs = [p[0] for p in pts if lo <= p[1] < hi]
        if not xs:
            out.append((0, 0, 0, 0))
            continue
        # sin los extremos finos (pelo, cola, dedos): percentil 4..96
        out.append(box(pct(xs, 0.04), lo, pct(xs, 0.96) + 1, hi))
    return out


def dilate(pts, r):
    return {(x + dx, y + dy) for x, y in pts for dx in range(-r, r + 1) for dy in range(-r, r + 1)}


def hitbox(pts, ref_pts, stand_h):
    """Caja de la extremidad que golpea. La punta es el píxel más adelantado
    (+x) de la zona que sobresale de la silueta de referencia; la caja va desde
    el centro del cuerpo (hombro/cadera) hasta la punta, en una franja de
    +-12% del alto parado alrededor de la punta. Así cubre la extremidad entera
    y conecta también cuerpo a cuerpo, sin tapar de la cabeza a los pies."""
    rxs = [p[0] for p in ref_pts]
    body_x = (min(rxs) + max(rxs)) // 2
    ref = set(ref_pts)
    out = [p for p in pts if p not in ref and p[0] > body_x] or [p for p in pts if p[0] > body_x] or list(pts)
    tip = max(p[0] for p in out)
    tys = [p[1] for p in out if p[0] >= tip - 4]
    ty = sum(tys) // len(tys)
    half = max(8, int(0.12 * stand_h))
    band = [p for p in pts if ty - half <= p[1] <= ty + half and p[0] >= body_x]
    x0 = min(p[0] for p in band)
    y0 = min(p[1] for p in band)
    y1 = max(p[1] for p in band) + 1
    return box(x0 - 2, y0 - 2, tip + 3, y1 + 2)


# --------------------------------------------------------------------------
# tiles
# --------------------------------------------------------------------------

def flip_t(t, f):
    rows = [t[i * 16:(i + 1) * 16] for i in range(16)]
    if f & 1:
        rows = [r[::-1] for r in rows]
    if f & 2:
        rows = rows[::-1]
    return b"".join(rows)


class TileBank:
    def __init__(self, vflip=True):
        self.tiles = [bytes(256)]           # 0 = vacío compartido
        self.lookup = {}
        self.flips = (0, 1, 2, 3) if vflip else (0, 1)
        self.stats = {"refs": 0, "empty": 0, "same": 0, "hflip": 0, "vflip": 0, "hvflip": 0}

    def add(self, t):
        self.stats["refs"] += 1
        if not any(t):
            self.stats["empty"] += 1
            return 0
        hit = self.lookup.get(t)
        if hit:
            i, f = hit
            self.stats[["same", "hflip", "vflip", "hvflip"][f]] += 1
            return i | (f << 14)
        i = len(self.tiles)
        if i >= 0x4000:
            raise SystemExit("neosprite: más de 16383 tiles en un personaje")
        self.tiles.append(t)
        for f in self.flips:
            self.lookup.setdefault(flip_t(t, f), (i, f))
        return i


# --------------------------------------------------------------------------
# char
# --------------------------------------------------------------------------

def build_char(args):
    name = args.name.upper()
    slot = args.slot or SLOTS.get(name)
    if slot not in ("p1", "p2"):
        raise SystemExit("neosprite: --slot p1|p2 (no hay ranura por defecto para %s)" % name)
    log = print
    anchor = tuple(int(v) for v in args.anchor.split(",")) if args.anchor else None
    prim = Source(os.path.abspath(args.dir), False, anchor, args.height, log)
    fb = None
    fb_dir = args.fallback or os.path.join(PROC_DIR, name)
    if not args.fallback and not os.path.isdir(fb_dir):
        fb_dir = os.path.join(PROC_DIR, "ROBOCLICK")
    if not args.no_fallback and os.path.isdir(fb_dir) and os.path.abspath(fb_dir) != prim.path:
        fb = Source(os.path.abspath(fb_dir), True, log=log)

    # 1. resolver cada animación: carpeta, frames, duraciones, flags
    plan = {}
    for anim in ANIMS:
        plan[anim] = resolve_anim(anim, prim, fb)
        if plan[anim] is None:
            raise SystemExit("neosprite: falta la animación %s en %s y no hay fallback" % (anim, rel(prim.path)))

    # 2. paleta (solo con los frames del arte real; el fallback se adapta)
    used = {}
    for anim, p in plan.items():
        for path, _, _ in p["steps"]:
            used[path] = p["src"].frame(path)
    real = [f for f in used.values() if not f.fallback] or list(used.values())
    if args.palette_from:
        counts = color_counts([Image.open(args.palette_from).convert("RGBA")])
    else:
        counts = color_counts([f.img for f in real])
    pal = sort_palette(quantize(counts, 15))
    mapper = Mapper(pal)
    for f in used.values():
        f.idx = index_image(f.img, mapper)

    # 3. imágenes recortadas y tiles: se prueba el desfase de la grilla de 16 px
    #    respecto del ancla que da menos columnas y menos tiles únicos
    pimgs = {}
    for path, f in used.items():
        pimgs[path] = Image.frombytes("L", f.img.size, f.idx)
        f.pts = f.mask_points()
        if not f.pts:
            raise SystemExit("neosprite: %s está vacío" % rel(path))
    if args.grid:
        grid = tuple(int(v) for v in args.grid.split(","))
    else:
        grid = search_grid(used, pimgs, not args.no_vflip)
    bank, imgs, img_of, entries = cut_tiles(used, pimgs, grid, not args.no_vflip)
    for im in imgs:
        if im["w"] > HW_COLS:
            raise SystemExit("neosprite: %s mide %d columnas (máximo FIGHTER_HW_COLS=%d = %d px)"
                             % (im["path"], im["w"], HW_COLS, HW_COLS * 16))
        if im["h"] > 32:
            raise SystemExit("neosprite: %s mide %d filas de tiles (máximo 32)" % (im["path"], im["h"]))

    # 4. frames con cajas
    refs = {}

    def ref_for(anim, src):
        key = (HIT_REF.get(anim, "IDLE"), id(src))
        if key not in refs:
            rp = plan[HIT_REF.get(anim, "IDLE")]
            p0 = rp["steps"][0][0] if rp["src"] is src else plan["IDLE"]["steps"][0][0]
            pts = imgs[img_of[p0]]["pts"]
            refs[key] = pts
        return refs[key]

    frames, anims_out, sources = [], [], {}
    for anim in ANIMS:
        p = plan[anim]
        first = len(frames)
        hits = p.get("hit")
        for path, dur, flags in p["steps"]:
            im = imgs[img_of[path]]
            hurt = hurtboxes(im["pts"])
            hit = (0, 0, 0, 0)
            if flags & FLAGS["ACTIVE"]:
                hit = hitbox(im["pts"], ref_for(anim, p["src"]), p["src"].stand_h)
            if hits and hits[len(frames) - first]:
                hit = tuple(hits[len(frames) - first])
            frames.append({"img": img_of[path], "dur": dur, "flags": flags, "hit": hit,
                           "hurt_hi": hurt[0], "hurt_lo": hurt[1]})
        anims_out.append({"name": anim, "first": first, "count": len(p["steps"]), "loop": int(p["loop"])})
        sources[anim] = p["how"]

    # 5. salida
    sheet_tiles = len(bank.tiles)
    rows = (sheet_tiles + 15) // 16
    used_tiles = rows * 16
    sheet = Image.new("P", (256, rows * 16), 0)
    gpal = [(255, 0, 255)] + pal
    gpal += [(0, 0, 0)] * (16 - len(gpal))
    sheet.putpalette([c for rgb in gpal for c in rgb])
    for i, t in enumerate(bank.tiles):
        timg = Image.frombytes("P", (16, 16), t)
        sheet.paste(timg, ((i % 16) * 16, (i // 16) * 16))
    gif = os.path.join(ASSETS, "char_%s.gif" % slot)
    sheet.save(gif, transparency=0, optimize=False)

    neo_pal = [0x8000] + [MA.packed15(c) for c in pal]
    neo_pal += [0x8000] * (16 - len(neo_pal))
    write_c(slot, name, entries, imgs, frames, anims_out, neo_pal, used_tiles)

    # métricas y reporte
    idle_img = imgs[frames[anims_out[0]["first"]]["img"]]
    iys = [p[1] for p in idle_img["pts"]]
    stand_h = max(iys) - min(iys) + 1
    worst = max(imgs, key=lambda im: im["w"])
    st = bank.stats
    dedup_saved = st["same"] + st["hflip"] + st["vflip"] + st["hvflip"]
    naive = sum(im["w"] * im["h"] for im in imgs)
    full = len(imgs) * max(im["w"] for im in imgs) * max(im["h"] for im in imgs)
    report = {
        "name": name, "slot": slot, "source": rel(prim.path),
        "fallback": rel(fb.path) if fb else None,
        "anims_from_fallback": sorted(a for a in ANIMS if plan[a]["src"] is fb),
        "anchor": list(prim.anchor), "scale": prim.scale, "pixel_grid": prim.k, "tile_grid": list(grid),
        "stand_height_px": stand_h,
        "colors": len(pal),
        "images": len(imgs), "frames": len(frames),
        "tile_refs": st["refs"], "tile_refs_uncropped": full, "empty_refs": st["empty"],
        "unique_tiles": sheet_tiles, "sheet_tiles": used_tiles,
        "saved_same": st["same"], "saved_hflip": st["hflip"], "saved_vflip": st["vflip"], "saved_hvflip": st["hvflip"],
        "saved_total": dedup_saved,
        "max_cols": worst["w"], "max_rows": max(im["h"] for im in imgs),
        "worst_frame": worst["path"],
        "sprites_per_line_worst": worst["w"],
        "crom_bytes": used_tiles * 128,
    }
    side = {
        "name": name, "slot": slot, "anchor": list(prim.anchor),
        "palette": [list(neo_unpack(v)) for v in neo_pal], "palette_src": [list(c) for c in pal],
        "tiles": entries,
        "imgs": [{k: v for k, v in im.items() if k != "pts"} for im in imgs],
        "frames": frames, "anims": anims_out, "sources": sources, "report": report,
    }
    with open(os.path.join(ASSETS, "char_%s.json" % slot), "w") as fh:
        json.dump(side, fh, separators=(",", ":"))
    if slot == "p1":
        m = {"character": name, "stand_height_px": stand_h, "stand_height_frac": round(stand_h / 224, 3),
             "feet_row_in_canvas": prim.anchor[1], "anchor_row": prim.anchor[1],
             "idle_frames": anims_out[ANIMS.index("IDLE")]["count"],
             "walk_frames": anims_out[ANIMS.index("WALK_F")]["count"]}
        with open(os.path.join(ASSETS, "metrics.json"), "w") as fh:
            fh.write(json.dumps(m, indent=1))

    print("neosprite char %s -> %s (%s)" % (name, slot, rel(prim.path)))
    if report["anims_from_fallback"]:
        print("  del fallback %s: %s" % (report["fallback"], " ".join(report["anims_from_fallback"])))
    print("  paleta: %d colores + transparente; ancla %d,%d; alto parado %d px (%.3f de la pantalla); grilla %d,%d"
          % (len(pal), prim.anchor[0], prim.anchor[1], stand_h, stand_h / 224, grid[0], grid[1]))
    print("  %d imágenes, %d frames; referencias a tiles %d (sin recorte serían %d), vacías %d"
          % (len(imgs), len(frames), st["refs"], full, st["empty"]))
    print("  tiles únicos %d (+relleno %d); ahorrados por dedupe %d: iguales %d, flip H %d, flip V %d, flip HV %d"
          % (sheet_tiles, used_tiles, dedup_saved, st["same"], st["hflip"], st["vflip"], st["hvflip"]))
    print("  sprites por línea en el peor frame: %d columnas (%s); máx %d filas; C-ROM %d bytes"
          % (worst["w"], worst["path"], report["max_rows"], used_tiles * 128))
    if args.preview:
        preview(slot)
    return report


def cut_tiles(used, pimgs, grid, vflip):
    """Corta cada frame en tiles de 16x16 con la grilla desplazada `grid`
    (gx, gy: borde de una columna/fila relativo al ancla) y los deduplica."""
    gx, gy = grid
    bank = TileBank(vflip=vflip)
    imgs, img_of, entries = [], {}, []
    for path, f in used.items():
        ax, ay = f.anchor
        xs = [p[0] for p in f.pts]
        ys = [p[1] for p in f.pts]
        k0, k1 = (min(xs) - gx) // 16, (max(xs) - gx) // 16
        j0, j1 = (min(ys) - gy) // 16, (max(ys) - gy) // 16
        cw, ch = k1 - k0 + 1, j1 - j0 + 1
        pim = pimgs[path]
        first = len(entries)
        for c in range(cw):
            for r in range(ch):
                ox = ax + gx + (k0 + c) * 16
                oy = ay + gy + (j0 + r) * 16
                entries.append(bank.add(pim.crop((ox, oy, ox + 16, oy + 16)).tobytes()))
        img_of[path] = len(imgs)
        imgs.append({"path": rel(path), "first": first, "x0": gx + k0 * 16, "y0": gy + j0 * 16, "w": cw, "h": ch,
                     "fallback": f.fallback, "pts": f.pts})
    return bank, imgs, img_of, entries


def search_grid(used, pimgs, vflip):
    def cost(g):
        bank, imgs, _, _ = cut_tiles(used, pimgs, g, vflip)
        return (max(im["w"] for im in imgs), len(bank.tiles), sum(im["w"] * im["h"] for im in imgs))
    gx = min(range(-16, 0), key=lambda x: (cost((x, 0)), abs(x + 8)))
    gy = min(range(-15, 1), key=lambda y: (cost((gx, y)), -y))
    return gx, gy


def resolve_anim(anim, prim, fb):
    for src in (prim, fb):
        if src is None:
            continue
        ent = (src.meta.get("anims") or {}).get(anim)
        if ent and src.folder(ent.get("src", "")):
            return from_meta(anim, src, ent)
        for folder, sel in CANDIDATES[anim]:
            files = src.folder(folder)
            if files:
                active = None
                fent = (src.meta.get("anims") or {}).get(folder_anim(folder))
                if fent and "active" in fent:
                    active = fent["active"]
                if sel == "active" and active is None:
                    active = auto_active(src, files, prim_idle(src))
                seq = select(files, sel, active)
                if src.fallback and src is fb:
                    how = "fallback %s/%s" % (folder, sel)
                else:
                    how = "%s/%s" % (folder, sel)
                a = None
                if anim in ("PUNCH", "KICK", "CPUNCH", "JKICK", "FIREBALL"):
                    a = active if sel == "active" else auto_active(src, [files[i] for i in seq], prim_idle(src), seq)
                steps, loop = timing(anim, seq, a)
                return {"src": src, "loop": loop, "how": how,
                        "steps": [(files[i], d, fl) for i, d, fl in steps]}
    return None


def folder_anim(folder):
    return {"punch": "PUNCH", "kick": "KICK", "cpunch": "CPUNCH", "jkick": "JKICK", "fireball": "FIREBALL"}.get(folder, "")


def prim_idle(src):
    return src.frame(src.folder("idle")[0])


def auto_active(src, files, idle, seq=None):
    """El frame activo es el que más sobresale hacia adelante de la guardia."""
    ref = idle.mask_points()
    rxs = [p[0] for p in ref]
    front = max(rxs)
    best, best_v = 0, -1
    for i, fp in enumerate(files):
        pts = src.frame(fp).mask_points()
        v = max(p[0] for p in pts) - front
        if v > best_v:
            best, best_v = i, v
    return seq[best] if seq is not None else best


def from_meta(anim, src, ent):
    files = src.folder(ent["src"])
    n = len(files)
    seq = ent.get("seq", list(range(n)))
    for i in seq:
        if not 0 <= i < n:
            raise SystemExit("neosprite: %s: seq usa el frame %d y %s/ tiene %d" % (anim, i, ent["src"], n))
    if "dur" in ent:
        durs = ent["dur"] if isinstance(ent["dur"], list) else [ent["dur"]] * len(seq)
        flags = [parse_flags(f) for f in ent.get("flags", [0] * len(seq))]
        if not (len(durs) == len(seq) == len(flags)):
            raise SystemExit("neosprite: %s: seq, dur y flags tienen que tener el mismo largo" % anim)
        steps, loop = list(zip(seq, durs, flags)), bool(ent.get("loop", False))
    else:
        a = ent.get("active")
        if a is None and anim in ("PUNCH", "KICK", "CPUNCH", "JKICK", "FIREBALL"):
            a = auto_active(src, [files[i] for i in seq], prim_idle(src), seq)
        steps, loop = timing(anim, seq, a)
        if "loop" in ent:
            loop = bool(ent["loop"])
    fd = FRAMEDATA.get(anim)
    if fd and len(fd.get("dur", [])) == len(steps):
        steps = [(i, d, fl) for (i, _, fl), d in zip(steps, fd["dur"])]
    tag = "fallback " if src.fallback else ""
    hit = ent.get("hit")
    if hit is not None and len(hit) != len(steps):
        raise SystemExit("neosprite: %s: hit tiene que tener una caja (o null) por frame" % anim)
    return {"src": src, "loop": loop, "how": "%sanims.json %s" % (tag, ent["src"]), "hit": hit,
            "steps": [(files[i], d, fl) for i, d, fl in steps]}


def color_counts(images):
    counts = {}
    for img in images:
        data = img.tobytes()
        for i in range(0, len(data), 4):
            if data[i + 3] >= ALPHA_MIN:
                c = neo_rgb((data[i], data[i + 1], data[i + 2]))
                counts[c] = counts.get(c, 0) + 1
    return counts


def index_image(img, mapper):
    data = img.tobytes()
    out = bytearray(len(data) // 4)
    for i in range(0, len(data), 4):
        if data[i + 3] >= ALPHA_MIN:
            out[i >> 2] = mapper(neo_rgb((data[i], data[i + 1], data[i + 2])))
    return bytes(out)


def write_c(slot, name, entries, imgs, frames, anims, neo_pal, used_tiles):
    up = slot.upper()
    h = ["/* Generado por tools/neosprite.py char (%s): no editar a mano. */\n" % name,
         "#ifndef GEN_CHAR_%s_H\n#define GEN_CHAR_%s_H\n" % (up, up),
         "/* tiles que ocupa en la C-ROM (con relleno hasta múltiplo de 16) */\n",
         "#define CHAR_%s_TILES %d\n#endif\n" % (up, used_tiles)]
    open(os.path.join(GEN, "char_%s.h" % slot), "w").write("".join(h))
    base = "TILE_END" if slot == "p1" else "(TILE_END + CHAR_P1_TILES)"
    c = ["/* Generado por tools/neosprite.py char (%s): no editar a mano. */\n" % name,
         '#include "character.h"\n#include "gen/assets.h"\n#include "gen/char_p1.h"\n',
         '#include "gen/char_%s.h"\n\n' % slot if slot != "p1" else "\n"]
    c.append("static const u16 tiles[%d] = {\n" % len(entries))
    for i in range(0, len(entries), 16):
        c.append("    " + ", ".join("0x%04x" % e for e in entries[i:i + 16]) + ",\n")
    c.append("};\n\nstatic const cimg_t imgs[%d] = {\n" % len(imgs))
    for im in imgs:
        c.append("    {%d, %d, %d, %d, %d},  /* %s */\n" % (im["first"], im["x0"], im["y0"], im["w"], im["h"], im["path"]))
    c.append("};\n\nstatic const frame_t frames[%d] = {\n" % len(frames))
    for f in frames:
        c.append("    {%d, %d, %d, {%d, %d, %d, %d}, {%d, %d, %d, %d}, {%d, %d, %d, %d}},\n"
                 % ((f["img"], f["dur"], f["flags"]) + tuple(f["hit"]) + tuple(f["hurt_hi"]) + tuple(f["hurt_lo"])))
    c.append("};\n\nstatic const anim_t anims[ANIM_COUNT] = {\n")
    for a in anims:
        c.append("    {%d, %d, %d},  /* %s */\n" % (a["first"], a["count"], a["loop"], a["name"]))
    c.append("};\n\nstatic const u16 pal[16] = {%s};\n\n" % ", ".join("0x%04x" % v for v in neo_pal))
    c.append('const character_t char_%s = {"%s", %s, tiles, imgs, frames, anims, pal};\n' % (slot, name, base))
    if slot == "p2":
        c.append("\n/* la C-ROM de 2 MB tiene 16384 tiles */\n"
                 "typedef char crom_fits[(TILE_END + CHAR_P1_TILES + CHAR_P2_TILES <= 16384) ? 1 : -1];\n")
    open(os.path.join(GEN, "char_%s.c" % slot), "w").write("".join(c))


# --------------------------------------------------------------------------
# stage
# --------------------------------------------------------------------------

def load_layer(path, w, h):
    img = Image.open(path).convert("RGBA")
    if img.size != (w, h):
        k = img.size[0] // w
        if k > 1 and img.size == (w * k, h * k):
            img = img.resize((w, h), Image.NEAREST)
        else:
            raise SystemExit("neosprite: %s mide %dx%d y tiene que medir %dx%d (o un múltiplo exacto)"
                             % (rel(path), img.size[0], img.size[1], w, h))
    return img


def indexed_layer(img, opaque):
    """Imagen RGBA -> P de <=15 colores en los índices 1..15 (0 = transparente)."""
    if opaque:
        img = img.copy()
        img.putalpha(255)
    pal = sort_palette(quantize(color_counts([img]), 15))
    mp = Mapper(pal)
    out = Image.frombytes("P", img.size, index_image(img, mp))
    gpal = [(0, 0, 0)] + pal
    gpal += [(0, 0, 0)] * (16 - len(gpal))
    out.putpalette([c for rgb in gpal for c in rgb])
    return out, len(pal)


CROWD_SPEED = 7      # REG_LSPCMODE: la auto-animación avanza cada 8 frames (4 cuadros = 32 frames)


def build_city_layer(base, crowd, tile_city, speed=CROWD_SPEED):
    """Ciudad + público animado por hardware (auto-animación de 4 cuadros, ver
    Las filas de tiles que tocan el público se
    componen 4 veces (base + cuadro f); cada tile que cambia entre cuadros se
    guarda como 4 tiles consecutivos alineados a 4 en la C-ROM y en SCB1 lleva
    el bit 2 del atributo: el hardware reemplaza los 2 bits bajos del número
    de tile con su contador. Sin CPU ni sprites extra.
    Escribe assets/city.gif, assets/city.json y src/gen/stage_gen.c/.h."""
    w, h = base.size
    cols, rows = w // 16, h // 16
    y0 = MA.CROWD_Y
    r0, r1 = y0 // 16, (y0 + MA.CROWD_H - 1) // 16
    comps = []
    for f in crowd:
        c = base.copy()
        c.alpha_composite(f.convert("RGBA"), (0, y0))
        comps.append(c)
    # paletas: la ciudad arriba del público y la franja del público aparte
    top = base.crop((0, 0, w, r0 * 16))
    band = [c.crop((0, r0 * 16, w, (r1 + 1) * 16)) for c in comps]
    pal_city = sort_palette(quantize(color_counts([top]), 15))
    pal_crowd = sort_palette(quantize(color_counts(band), 15))
    top_idx = Image.frombytes("L", top.size, index_image(top, Mapper(pal_city)))
    band_idx = [Image.frombytes("L", b.size, index_image(b, Mapper(pal_crowd))) for b in band]
    pad = (-tile_city) % 4
    groups, gindex = [], {}
    statics, sindex = [bytes(256)], {bytes(256): 0}
    cells = {}
    for r in range(rows):
        for k in range(cols):
            if r < r0:
                t = top_idx.crop((k * 16, r * 16, k * 16 + 16, r * 16 + 16)).tobytes()
                cells[r, k] = ("s", t, 0)
            else:
                fr = tuple(bi.crop((k * 16, (r - r0) * 16, k * 16 + 16, (r - r0) * 16 + 16)).tobytes() for bi in band_idx)
                if len(set(fr)) == 1:
                    cells[r, k] = ("s", fr[0], 1)
                else:
                    cells[r, k] = ("a", fr, 1)
                    if fr not in gindex:
                        gindex[fr] = len(groups)
                        groups.append(fr)
            if cells[r, k][0] == "s" and cells[r, k][1] not in sindex:
                sindex[cells[r, k][1]] = len(statics)
                statics.append(cells[r, k][1])
    # hoja: relleno hasta múltiplo de 4, grupos animados, tiles fijos
    sheet = [bytes(256)] * pad
    for g in groups:
        sheet.extend(g)
    sbase = len(sheet)
    sheet.extend(statics)
    m = []
    for r in range(rows):
        for k in range(cols):
            kind, t, crowd_pal = cells[r, k]
            if kind == "a":
                e = (pad + gindex[t] * 4) | (1 << 14)
            else:
                e = sbase + sindex[t]
            m.append(e | (crowd_pal << 15))
    assert all((tile_city + (e & 0x3fff)) % 4 == 0 for e in m if e & (1 << 14))
    nrows = (len(sheet) + 15) // 16
    img = Image.new("P", (256, nrows * 16), 0)
    gpal = [(255, 0, 255)] + pal_city
    gpal += [(0, 0, 0)] * (16 - len(gpal))
    img.putpalette([c for rgb in gpal for c in rgb])
    for i, t in enumerate(sheet):
        img.paste(Image.frombytes("P", (16, 16), t), ((i % 16) * 16, (i // 16) * 16))
    MA.save_gif(img, "city.gif")
    pad16 = lambda p: [(0, 0, 0)] + p + [(0, 0, 0)] * (15 - len(p))
    meta = {"cols": cols, "rows": rows, "tiles": nrows * 16, "anim_groups": len(groups), "speed": speed,
            "crowd_rows": [r0, r1], "pal_city": pad16(pal_city), "pal_crowd": pad16(pal_crowd), "map": m}
    with open(os.path.join(ASSETS, "city.json"), "w") as fh:
        json.dump(meta, fh, separators=(",", ":"))
    MA.stage_gen()
    return meta


def tile_city_base():
    txt = open(os.path.join(GEN, "assets.h")).read()
    return int(re.search(r"#define TILE_CITY (\d+)", txt).group(1))


def build_stage(args):
    d = os.path.abspath(args.dir)
    proc = os.path.join(PROC_DIR, "stage")
    done = []
    sky_w, sky_h = MA.layer_cols(4) * 16, 9 * 16
    city_w, city_h = MA.layer_cols(8) * 16, 10 * 16
    floor_w, floor_h = 320 + MA.CAM_RANGE * 18 // 16, 80
    p = os.path.join(d, "sky.png")
    if os.path.exists(p):
        img, n = indexed_layer(load_layer(p, sky_w, sky_h), True)
        MA.save_gif(img, "sky.gif")
        done.append("sky (%d colores)" % n)
    p = os.path.join(d, "floor.png")
    if os.path.exists(p):
        fimg, n = indexed_layer(load_layer(p, floor_w, floor_h), True)
        src = fimg.load()
        for i, (name, num, rows, y) in enumerate(MA.LAYERS[2:]):
            w = MA.layer_cols(num) * 16
            strip = Image.new("P", (w, 16), 0)
            strip.putpalette(fimg.getpalette())
            px = strip.load()
            off = MA.CAM_CENTER * num // 16
            for u in range(w):
                x = max(0, min(floor_w - 1, u - off + 108))
                for yy in range(16):
                    px[u, yy] = src[x, i * 16 + yy]
            MA.save_gif(strip, name + ".gif")
        done.append("floor0..4 (%d colores)" % n)
    city_p = os.path.join(d, "city.png")
    crowd_fs = frame_files(os.path.join(d, "crowd"))
    if os.path.exists(city_p) or crowd_fs:
        base = load_layer(city_p if os.path.exists(city_p) else os.path.join(proc, "city.png"), city_w, city_h)
        if not crowd_fs:
            crowd_fs = frame_files(os.path.join(proc, "crowd"))
        if len(crowd_fs) != 4:
            raise SystemExit("neosprite: crowd/ tiene que tener 4 cuadros (tiene %d)" % len(crowd_fs))
        crowd = [load_layer(f, city_w, MA.CROWD_H) for f in crowd_fs]
        meta = build_city_layer(base, crowd, tile_city_base())
        done.append("city%s + público%s (%d tiles, %d animados x4)"
                    % ("" if os.path.exists(city_p) else " procedural",
                       "" if frame_files(os.path.join(d, "crowd")) else " procedural",
                       meta["tiles"], meta["anim_groups"]))
    else:
        MA.stage_gen()
    print("neosprite stage: %s" % (", ".join(done) or "sin PNG en %s: quedan las capas procedurales" % rel(d)))
    print("  tamaños: sky.png %dx%d, city.png %dx%d, crowd/NN.png %dx%d (x4), floor.png %dx%d"
          % (sky_w, sky_h, city_w, city_h, city_w, MA.CROWD_H, floor_w, floor_h))


# --------------------------------------------------------------------------
# preview
# --------------------------------------------------------------------------

def compose(side, sheet, im):
    """Rearma una imagen desde los tiles y flips (lo mismo que hace el motor)."""
    w, h = im["w"] * 16, im["h"] * 16
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pal = [tuple(c) + (255,) for c in side["palette"]]
    for c in range(im["w"]):
        for r in range(im["h"]):
            e = side["tiles"][im["first"] + c * im["h"] + r]
            t = e & 0x3fff
            tile = sheet.crop(((t % 16) * 16, (t // 16) * 16, (t % 16) * 16 + 16, (t // 16) * 16 + 16))
            if e >> 14 & 1:
                tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
            if e >> 15 & 1:
                tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
            data = tile.tobytes()
            rgba = Image.new("RGBA", (16, 16))
            rgba.putdata([pal[v] if v else (0, 0, 0, 0) for v in data])
            out.paste(rgba, (c * 16, r * 16))
    return out


def preview(which):
    slot = SLOTS.get(which.upper(), which.lower())
    js = os.path.join(ASSETS, "char_%s.json" % slot)
    if not os.path.exists(js):
        raise SystemExit("neosprite: no existe %s; corré primero `neosprite.py char`" % rel(js))
    side = json.load(open(js))
    sheet = Image.open(os.path.join(ASSETS, "char_%s.gif" % slot))
    pngs = []
    for im in side["imgs"]:
        buf = io.BytesIO()
        compose(side, sheet, im).save(buf, "PNG")
        pngs.append("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
    buf = io.BytesIO()
    sheet.convert("RGBA").save(buf, "PNG")
    data = {
        "name": side["name"], "slot": side["slot"], "palette": side["palette"],
        "imgs": [{"x0": im["x0"], "y0": im["y0"], "w": im["w"], "h": im["h"], "path": im["path"],
                  "fallback": im.get("fallback", False)} for im in side["imgs"]],
        "frames": side["frames"], "anims": side["anims"], "sources": side["sources"],
        "report": side["report"], "flags": FLAGS,
    }
    html = VIEWER_HTML.replace("__DATA__", json.dumps(data, separators=(",", ":"))) \
                      .replace("__PNGS__", json.dumps(pngs)) \
                      .replace("__SHEET__", "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()) \
                      .replace("__NAME__", side["name"])
    os.makedirs(VIEWER_DIR, exist_ok=True)
    out = os.path.join(VIEWER_DIR, "%s.html" % side["name"])
    open(out, "w").write(html)
    print("  visor: %s" % rel(out))
    return out


VIEWER_HTML = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__NAME__ sprites</title>
<style>
:root{--bg:#15131c;--panel:#1f1c29;--fg:#e8e4f0;--mut:#9a93ad;--line:#3a3550;--acc:#35d6c9;--hit:#ff3b5c;--hurt:#35d06a;--hurt2:#3aa0ff;--anc:#ffd23f}
:root[data-theme="light"]{--bg:#f4f2f8;--panel:#fff;--fg:#1d1a26;--mut:#6a6480;--line:#d8d3e4}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#f4f2f8;--panel:#fff;--fg:#1d1a26;--mut:#6a6480;--line:#d8d3e4}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 ui-monospace,Menlo,Consolas,monospace}
header{padding:12px 16px;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:12px;align-items:baseline}
h1{font-size:18px;margin:0}
.mut{color:var(--mut)}
main{display:grid;grid-template-columns:220px 1fr 300px;gap:0;min-height:calc(100vh - 50px)}
@media (max-width:900px){main{grid-template-columns:1fr}}
nav{border-right:1px solid var(--line);overflow:auto;max-height:calc(100vh - 50px)}
nav button{display:flex;justify-content:space-between;width:100%;text-align:left;background:none;border:0;border-bottom:1px solid var(--line);color:var(--fg);padding:6px 12px;font:inherit;cursor:pointer}
nav button.on{background:var(--panel);color:var(--acc)}
nav small{color:var(--mut)}
#stage{display:flex;flex-direction:column;align-items:center;padding:12px;gap:8px;min-width:0}
canvas{image-rendering:pixelated;background:repeating-conic-gradient(#2a2638 0 25%,#232030 0 50%) 0 0/16px 16px;max-width:100%}
.ctl{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:center}
.ctl label{display:flex;gap:4px;align-items:center}
.ctl button{background:var(--panel);color:var(--fg);border:1px solid var(--line);padding:4px 10px;font:inherit;cursor:pointer;border-radius:4px}
aside{border-left:1px solid var(--line);padding:12px;overflow:auto;max-height:calc(100vh - 50px)}
table{border-collapse:collapse;width:100%;font-size:12px}
td,th{border-bottom:1px solid var(--line);padding:3px 4px;text-align:left}
tr.cur{background:var(--panel);color:var(--acc)}
.pal{display:flex;gap:2px;flex-wrap:wrap;margin:6px 0}
.pal span{width:22px;height:22px;border:1px solid var(--line);font-size:9px;display:flex;align-items:flex-end;justify-content:flex-end;color:#fff;text-shadow:0 0 2px #000}
.key span{display:inline-block;width:10px;height:10px;margin-right:4px;border:2px solid}
#sheet{width:100%;image-rendering:pixelated;border:1px solid var(--line);background:#222}
</style></head><body>
<header><h1>__NAME__</h1><span class="mut" id="sum"></span>
<span class="key"><span style="border-color:var(--hit)"></span>hitbox <span style="border-color:var(--hurt)"></span>hurt alta <span style="border-color:var(--hurt2)"></span>hurt baja <span style="border-color:var(--anc)"></span>ancla</span></header>
<main>
<nav id="list"></nav>
<section id="stage">
<canvas id="cv" width="360" height="240"></canvas>
<div class="ctl">
<button id="play">pausa</button><button id="prev">&lt; frame</button><button id="next">frame &gt;</button>
<label>zoom <input id="zoom" type="range" min="1" max="5" value="3"></label>
<label><input id="flip" type="checkbox"> mirar a la izquierda</label>
<label><input id="boxes" type="checkbox" checked> cajas</label>
<label><input id="grid" type="checkbox"> tiles</label>
<label>velocidad <select id="speed"><option value="0.25">1/4</option><option value="0.5">1/2</option><option value="1" selected>60 Hz</option></select></label>
</div>
<div id="info" class="mut"></div>
</section>
<aside>
<h3>Paleta</h3><div class="pal" id="pal"></div>
<h3>Frames</h3><table id="ftab"></table>
<h3>Reporte</h3><table id="rep"></table>
<h3>Hoja de tiles (C-ROM)</h3><img id="sheet" src="__SHEET__" alt="tiles">
</aside></main>
<script>
const D=__DATA__, P=__PNGS__;
const imgs=P.map(s=>{const i=new Image();i.src=s;return i});
const cv=document.getElementById('cv'),cx=cv.getContext('2d');
let cur=0,fi=0,tick=0,playing=true,last=0,acc=0;
const $=id=>document.getElementById(id);
const FL=Object.entries(D.flags);
function flagNames(v){return FL.filter(([n,b])=>v&b).map(([n])=>n).join('|')}
function css(v){return getComputedStyle(document.documentElement).getPropertyValue(v)}
D.anims.forEach((a,i)=>{const b=document.createElement('button');b.innerHTML=a.name+' <small>'+a.count+(a.loop?' loop':'')+'</small>';b.onclick=()=>{cur=i;fi=0;tick=0;render()};$('list').appendChild(b)});
D.palette.forEach((c,i)=>{const s=document.createElement('span');s.style.background=i?`rgb(${c})`:'transparent';s.textContent=i;s.title=i?'rgb('+c+')':'transparente';$('pal').appendChild(s)});
const R=D.report;$('sum').textContent=`${R.slot} · ${R.unique_tiles} tiles únicos · ${R.colors} colores · peor frame ${R.sprites_per_line_worst} sprites/línea · C-ROM ${(R.crom_bytes/1024).toFixed(1)} KB`;
$('rep').innerHTML=Object.entries(R).map(([k,v])=>`<tr><td>${k}</td><td>${Array.isArray(v)?v.join(', '):v}</td></tr>`).join('');
function frame(){const a=D.anims[cur];return D.frames[a.first+fi]}
function step(){const a=D.anims[cur];const f=frame();if(++tick>=f.dur){tick=0;if(fi+1<a.count)fi++;else if(a.loop)fi=0;else tick=f.dur-1}}
function render(){
 const z=+$('zoom').value,flip=$('flip').checked,a=D.anims[cur],f=frame(),im=D.imgs[f.img];
 const W=240,H=190;cv.width=W*z;cv.height=H*z;cx.imageSmoothingEnabled=false;
 const ax=W/2,ay=H-24;
 cx.fillStyle='rgba(0,0,0,.25)';cx.fillRect(0,ay*z,cv.width,1*z);
 cx.save();cx.scale(z,z);
 const x=flip?ax-im.x0-im.w*16:ax+im.x0,y=ay+im.y0;
 if(flip){cx.save();cx.translate(x+im.w*16,y);cx.scale(-1,1);cx.drawImage(imgs[f.img],0,0);cx.restore()}else cx.drawImage(imgs[f.img],x,y);
 if($('grid').checked){cx.strokeStyle='rgba(255,255,255,.35)';cx.lineWidth=1/z;for(let c=0;c<=im.w;c++){cx.beginPath();cx.moveTo(x+c*16,y);cx.lineTo(x+c*16,y+im.h*16);cx.stroke()}for(let r=0;r<=im.h;r++){cx.beginPath();cx.moveTo(x,y+r*16);cx.lineTo(x+im.w*16,y+r*16);cx.stroke()}}
 if($('boxes').checked){
  const bx=(b,col)=>{if(!b[2])return;const X=flip?ax-b[0]-b[2]:ax+b[0];cx.strokeStyle=col;cx.lineWidth=1;cx.strokeRect(X+.5,ay+b[1]+.5,b[2]-1,b[3]-1)};
  bx(f.hurt_hi,css('--hurt'));bx(f.hurt_lo,css('--hurt2'));bx(f.hit,css('--hit'));
  cx.fillStyle=css('--anc');cx.fillRect(ax-4,ay,9,1);cx.fillRect(ax,ay-4,1,9);
 }
 cx.restore();
 [...$('list').children].forEach((b,i)=>b.classList.toggle('on',i==cur));
 $('info').textContent=`${a.name} frame ${fi+1}/${a.count} · ${f.dur} ticks · ${flagNames(f.flags)||'-'} · imagen ${im.path}${im.fallback?' (fallback)':''} · ${im.w}x${im.h} tiles · fuente: ${D.sources[a.name]}`;
 $('ftab').innerHTML='<tr><th>#</th><th>img</th><th>dur</th><th>flags</th><th>hit</th></tr>'+Array.from({length:a.count},(_,i)=>{const g=D.frames[a.first+i];return `<tr class="${i==fi?'cur':''}"><td>${i}</td><td>${g.img}</td><td>${g.dur}</td><td>${flagNames(g.flags)}</td><td>${g.hit[2]?g.hit.join(','):''}</td></tr>`}).join('');
}
function loop(t){if(playing){acc+=(t-last)*(+$('speed').value);while(acc>=1000/60){acc-=1000/60;step()}}last=t;render();requestAnimationFrame(loop)}
$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'pausa':'play'};
$('next').onclick=()=>{playing=false;$('play').textContent='play';const a=D.anims[cur];fi=(fi+1)%a.count;tick=0};
$('prev').onclick=()=>{playing=false;$('play').textContent='play';const a=D.anims[cur];fi=(fi+a.count-1)%a.count;tick=0};
Promise.all(imgs.map(i=>i.decode())).then(()=>requestAnimationFrame(t=>{last=t;loop(t)}));
</script></body></html>
"""


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("char", help="personaje -> tiles, paleta, frames y cajas")
    c.add_argument("dir", help="carpeta del personaje (art/src/characters/<NOMBRE>)")
    c.add_argument("--name", required=True, help="nombre del personaje (ROBOCLICK, NINJAODA)")
    c.add_argument("--slot", choices=["p1", "p2"], help="ranura en la C-ROM (por defecto según el nombre)")
    c.add_argument("--palette-from", help="PNG de referencia para la paleta (colores opacos)")
    c.add_argument("--anchor", help="X,Y del ancla en el lienzo de entrada (por defecto: pies del idle 0)")
    c.add_argument("--height", type=int, help="alto parado deseado en px (por defecto no escala si está en 110..118)")
    c.add_argument("--fallback", help="carpeta para completar animaciones faltantes (por defecto art/tmp-procedural/<NOMBRE>)")
    c.add_argument("--no-fallback", action="store_true", help="error si falta alguna animación")
    c.add_argument("--no-vflip", action="store_true", help="dedupe solo con flip horizontal")
    c.add_argument("--grid", help="GX,GY: borde de la grilla de tiles relativo al ancla (por defecto se busca el mejor)")
    c.add_argument("--preview", action="store_true", help="generar también el visor HTML")
    s = sub.add_parser("stage", help="capas del escenario")
    s.add_argument("dir", help="carpeta con sky.png, city.png, floor.png (art/src/stage)")
    p = sub.add_parser("preview", help="visor HTML de un personaje ya convertido")
    p.add_argument("name", help="ROBOCLICK, NINJAODA, p1 o p2")
    a = ap.parse_args()
    if a.cmd == "char":
        build_char(a)
    elif a.cmd == "stage":
        build_stage(a)
    else:
        preview(a.name)


if __name__ == "__main__":
    main()
