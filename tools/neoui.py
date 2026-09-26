#!/usr/bin/env python3
"""neoui: arte de las pantallas previas al combate (logos, título, selector).

Lee art/src/ui/ (contrato en art/src/ui/README.md). Lo que falte se genera
como placeholder en art/tmp-procedural/ui/ para que el flujo se pueda probar:

  logos/*.png              logos de la presentación, en orden (hasta 320x224)
  title.png                logo del juego para la pantalla de título (hasta 320x160)
  portraits/<NOMBRE>.png   retrato de 64x64 para la grilla del selector
  cursor.png               marco de 64x64 del cursor (claro sobre transparente)

Cada imagen se parte en tiles de 16x16 y cada tile elige una de hasta N
paletas de 15 colores (atributo de paleta por tile en SCB1): así un logo con
degradé entra en la Neo Geo sin quedar posterizado a 15 colores.

Salida: assets/ui.gif (tiles, van después de los personajes en la C-ROM) y
src/gen/ui_gen.c/.h. Solo Python 3 + Pillow.
"""
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_assets as MA  # noqa: E402
import neosprite as NS    # noqa: E402

ROOT = NS.ROOT
SRC = os.path.join(ROOT, "art", "src", "ui")
PROC = os.path.join(ROOT, "art", "tmp-procedural", "ui")
ROSTER = ["ROBOCLICK", "NINJAODA"]          # orden de la grilla del selector
MAX_PALS = {"logo": 6, "title": 6, "portrait": 3, "cursor": 1, "bg": 8, "layer": 4}
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"


# --------------------------------------------------------------------------
# placeholders
# --------------------------------------------------------------------------

def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def glow_text(size, text, fnt, fill, glow, stroke=0, blur=4):
    """Texto con halo difuso, al estilo de los logos de los 90."""
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bb = d.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
    x = (size[0] - (bb[2] - bb[0])) // 2 - bb[0]
    y = (size[1] - (bb[3] - bb[1])) // 2 - bb[1]
    halo = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).text((x, y), text, font=fnt, fill=glow, stroke_width=stroke + 3)
    halo = halo.filter(ImageFilter.GaussianBlur(blur))
    im.alpha_composite(halo)
    d.text((x, y), text, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=(10, 10, 30, 255))
    return im


def binarize(im, bg=None):
    """Alfa binario sobre fondo negro: lo que queda semitransparente se
    mezcla con negro (el backdrop de las pantallas previas es negro)."""
    im = im.convert("RGBA")
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    px, po = im.load(), out.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            if a >= 110:
                k = a / 255.0
                po[x, y] = (int(r * k), int(g * k), int(b * k), 255)
    return out


def placeholder_odaclick():
    """Logo de la presentación (si falta art/src/ui/logos/): solo la cabeza
    del perro, chica (64 px), sin el nombre. El arte final es
    art/src/ui/logos/00_odaclick.png (pixel art desde la referencia)."""
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ref = os.path.join(ROOT, "art", "ref", "odaclick-dog.jpg")
    if os.path.exists(ref):
        dog = Image.open(ref).convert("RGBA")
        px = dog.load()
        for y in range(dog.size[1]):
            for x in range(dog.size[0]):
                r, g, b, _ = px[x, y]
                if min(r, g, b) > 225:
                    px[x, y] = (0, 0, 0, 0)
        dog = dog.crop(dog.getbbox()).resize((64, 64), Image.BOX)
        im.alpha_composite(dog)
    return binarize(im)


def placeholder_title():
    """Logo del juego provisorio (lo reemplaza art/src/ui/title.png)."""
    im = Image.new("RGBA", (304, 128), (0, 0, 0, 0))
    top = glow_text((304, 40), "ROBOCLICK", font(FONT_IMPACT, 36), (0, 230, 220, 255), (0, 120, 255, 220))
    vs = glow_text((304, 36), "VS", font(FONT_IMPACT, 30), (255, 230, 90, 255), (255, 80, 0, 220))
    bot = glow_text((304, 40), "NINJAODA", font(FONT_IMPACT, 36), (255, 60, 170, 255), (160, 0, 255, 220))
    im.alpha_composite(top, (0, 4))
    im.alpha_composite(vs, (0, 44))
    im.alpha_composite(bot, (0, 80))
    return binarize(im)


def _hsv(r, g, b):
    import colorsys
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)


def fire_ramp():
    """15 colores del fuego: rojo muy oscuro -> amarillo pálido."""
    stops = [(40, 0, 0), (110, 8, 0), (190, 30, 0), (240, 80, 0), (255, 150, 10), (255, 210, 60), (255, 250, 190)]
    out = []
    for i in range(15):
        t = i / 14 * (len(stops) - 1)
        a, b = stops[int(t)], stops[min(int(t) + 1, len(stops) - 1)]
        f = t - int(t)
        out.append(tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3)))
    return out


def periodic_noise(w, h, cell, seed):
    """Ruido de valor suave, periódico en x (w) y en y (h)."""
    import random
    rnd = random.Random(seed)
    gw, gh = max(1, w // cell), max(1, h // cell)
    grid = [[rnd.random() for _ in range(gw)] for _ in range(gh)]

    def at(x, y):
        fx, fy = x / cell, y / cell
        x0, y0 = int(fx) % gw, int(fy) % gh
        x1, y1 = (x0 + 1) % gw, (y0 + 1) % gh
        tx, ty = fx - int(fx), fy - int(fy)
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        a = grid[y0][x0] + (grid[y0][x1] - grid[y0][x0]) * tx
        b = grid[y1][x0] + (grid[y1][x1] - grid[y1][x0]) * tx
        return a + (b - a) * ty
    return at


def fire_frames(mask, n=8, period=64):
    """n cuadros de fuego dentro de la máscara. El ruido es periódico en y
    con período `period` y se corre period/n px por cuadro: el cuadro n
    vuelve a ser el 0 (loop perfecto) y las llamas suben."""
    w, h = mask.size
    m = mask.load()
    ys = [y for y in range(h) for x in range(w) if m[x, y]]
    y0, y1 = min(ys), max(ys)
    n1 = periodic_noise(w, period, 8, 7)
    n2 = periodic_noise(w, period, 4, 11)
    ramp = fire_ramp()
    frames = []
    for k in range(n):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = im.load()
        sh = k * period // n
        for y in range(h):
            g = (y - y0) / max(1, y1 - y0)
            for x in range(w):
                if not m[x, y]:
                    continue
                v = 0.62 * n1(x, (y + sh) % period) + 0.38 * n2(x * 1.3, (y + sh * 2) % period)
                i = 0.25 + 0.7 * g + 0.75 * (v - 0.5)
                i = min(max(i, 0.0), 1.0)
                px[x, y] = ramp[int(i * 14 + 0.5)] + (255,)
        frames.append(im)
    return frames


def placeholder_fieras(size=(288, 144)):
    """Logo provisorio del usuario (art/ref/fieras-fighters-logo.png) achicado,
    con la máscara de las letras de FIERAS sacada por color. Lo reemplaza
    el arte en art/src/ui/title/."""
    src = Image.open(os.path.join(ROOT, "art", "ref", "fieras-fighters-logo.png")).convert("RGB")
    W, H = src.size
    small = src.resize(size, Image.LANCZOS)
    base = Image.new("RGBA", size, (0, 0, 0, 0))
    mask = Image.new("L", size, 0)
    bp, sp, mp = base.load(), small.load(), mask.load()
    w, h = size
    for y in range(h):
        for x in range(w):
            r, g, b = sp[x, y]
            hh, ss, vv = _hsv(r, g, b)
            if vv > 0.16:
                bp[x, y] = (r, g, b, 255)
            # letras de FIERAS: rojo-naranja-amarillo saturado, fuera del sol
            sun = (x - 0.494 * w) ** 2 + ((y - 0.79 * h) * 1.0) ** 2 < (0.058 * w) ** 2
            if vv > 0.45 and ss > 0.55 and (hh < 0.15 or hh > 0.97) and not sun:
                mp[x, y] = 255
    # contorno oscuro alrededor de todo lo opaco (1 px)
    a = base.getchannel("A")
    grown = a.filter(ImageFilter.MaxFilter(3))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    op, gp = out.load(), grown.load()
    for y in range(h):
        for x in range(w):
            if gp[x, y]:
                op[x, y] = (12, 4, 8, 255)
    out.alpha_composite(base)
    inner = mask.filter(ImageFilter.MinFilter(3))       # la máscara deja 1 px de borde
    return out, fire_frames(inner), inner


def char_idle(name):
    for base in (os.path.join(ROOT, "art", "src", "characters", name),
                 os.path.join(ROOT, "art", "tmp-procedural", name)):
        files = NS.frame_files(os.path.join(base, "idle")) if os.path.isdir(os.path.join(base, "idle")) else []
        if files:
            return Image.open(files[0]).convert("RGBA")
    return None


def placeholder_portrait(name):
    """Retrato de 64x64: la cabeza recortada del idle 0 sobre un panel oscuro."""
    panel = Image.new("RGBA", (64, 64), (14, 14, 34, 255))
    d = ImageDraw.Draw(panel)
    for y in range(64):                                  # degradé vertical
        c = 14 + y // 3
        d.line([(0, y), (63, y)], fill=(c // 2, c // 2, c + 10, 255))
    idle = char_idle(name)
    if idle is not None:
        k = NS.grid_factor(idle)
        if k > 1:
            idle = idle.resize((idle.size[0] // k, idle.size[1] // k), Image.NEAREST)
        a = idle.getchannel("A").point(lambda v: 255 if v >= NS.ALPHA_MIN else 0)
        x0, y0, x1, y1 = a.getbbox()
        band = a.crop((x0, y0, x1, min(y1, y0 + 56))).getbbox()
        cx = x0 + (band[0] + band[2]) // 2
        head = idle.crop((cx - 32, y0 - 4, cx + 32, y0 + 60))
        m = head.getchannel("A").point(lambda v: 255 if v >= NS.ALPHA_MIN else 0)
        panel.paste(head, (0, 0), m)
    return panel


def placeholder_cursor():
    """Marco con esquinas marcadas. Índice 1 = oscuro, 2 = claro (lo tiñe el juego)."""
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 63, 63], outline=(90, 90, 90, 255), width=4)
    d.rectangle([1, 1, 62, 62], outline=(255, 255, 255, 255), width=2)
    for (x, y) in ((0, 0), (52, 0), (0, 52), (52, 52)):
        d.rectangle([x, y, x + 11, y + 11], outline=(255, 255, 255, 255), width=3)
    return im


# --------------------------------------------------------------------------
# conversión con paleta por tile
# --------------------------------------------------------------------------

def load(path, maxw, maxh):
    im = Image.open(path).convert("RGBA")
    k = NS.grid_factor(im)
    if k > 1:
        im = im.resize((im.size[0] // k, im.size[1] // k), Image.NEAREST)
    if im.size[0] > maxw or im.size[1] > maxh:
        s = min(maxw / im.size[0], maxh / im.size[1])
        im = im.resize((int(im.size[0] * s), int(im.size[1] * s)), Image.LANCZOS)
        print("neoui: %s reescalada a %dx%d" % (os.path.relpath(path, ROOT), *im.size))
    return binarize(im)


def palettize(im, max_pals):
    """Devuelve (paletas, tiles): cada tile es (índice de paleta, bytes 16x16)."""
    w, h = im.size
    tw, th = (w + 15) // 16, (h + 15) // 16
    canvas = Image.new("RGBA", (tw * 16, th * 16), (0, 0, 0, 0))
    canvas.paste(im, (0, 0))
    px = canvas.load()
    counts = {}
    for y in range(canvas.size[1]):
        for x in range(canvas.size[0]):
            r, g, b, a = px[x, y]
            if a:
                c = NS.neo_rgb((r, g, b))
                counts[c] = counts.get(c, 0) + 1
    n = min(len(counts), 15 * max_pals)
    while True:
        cols = NS.quantize(counts, n) if len(counts) > n else sorted(counts)
        mapper = NS.Mapper(cols)
        # color final de cada píxel: primero la paleta global y, si el tile
        # se pasa de 15, una reducción propia de ese tile (no de toda la imagen)
        tile_map = []
        tsets = []
        for ty in range(th):
            for tx in range(tw):
                tc = {}
                for y in range(16):
                    for x in range(16):
                        r, g, b, a = px[tx * 16 + x, ty * 16 + y]
                        if a:
                            c = cols[mapper(NS.neo_rgb((r, g, b))) - 1]
                            tc[c] = tc.get(c, 0) + 1
                remap = {c: c for c in tc}
                if len(tc) > 15:
                    keep = NS.quantize(tc, 15)
                    km = NS.Mapper(keep)
                    remap = {c: keep[km(c) - 1] for c in tc}
                tile_map.append(remap)
                tsets.append(set(remap.values()))
        pals = []
        order = sorted(range(len(tsets)), key=lambda i: -len(tsets[i]))
        assign = [0] * len(tsets)
        for i in order:
            st = tsets[i]
            best = None
            for pi, pset in enumerate(pals):
                if st <= pset:
                    best = pi
                    break
                if len(pset | st) <= 15 and (best is None or len(pset | st) < len(pals[best] | st)):
                    best = pi
            if best is None:
                pals.append(set(st))
                best = len(pals) - 1
            else:
                pals[best] |= st
            assign[i] = best
        if len(pals) <= max_pals or n <= 15:
            break
        n = max(15, int(n * 0.88))
    pals = [NS.sort_palette(p) for p in pals]
    tiles = []
    # orden por columnas: así se cargan en SCB1 (una columna por sprite)
    for tx in range(tw):
        for ty in range(th):
            i = ty * tw + tx
            pal = pals[assign[i]]
            idx = {c: k + 1 for k, c in enumerate(pal)}
            rm = tile_map[i]
            data = bytearray()
            for y in range(16):
                for x in range(16):
                    r, g, b, a = px[tx * 16 + x, ty * 16 + y]
                    data.append(idx[rm[cols[mapper(NS.neo_rgb((r, g, b))) - 1]]] if a else 0)
            tiles.append((assign[i], bytes(data)))
    return pals, tiles, tw, th


# --------------------------------------------------------------------------

def tile_ui_base():
    """TILE_UI absoluto (para alinear los grupos animados), leído de los
    headers que generan make_assets.py y neosprite.py."""
    import re
    def num(path, name):
        txt = open(os.path.join(NS.GEN, path)).read()
        return int(re.search(r"#define %s (\d+)" % name, txt).group(1))
    return (num("assets.h", "TILE_CITY") + num("stage_gen.h", "CITY_TILES") +
            num("char_p1.h", "CHAR_P1_TILES") + num("char_p2.h", "CHAR_P2_TILES"))


def palettize_anim(paths):
    """8 cuadros del mismo tamaño -> una paleta de 15 y, por posición de tile
    (por columnas), None si está vacía en todos o los 8 tiles indexados."""
    frames = [load(p, 320, 160) for p in paths]
    assert frames, "sin cuadros"
    while len(frames) < 8:
        frames = frames + frames
    frames = frames[:8]
    w, h = frames[0].size
    tw, th = (w + 15) // 16, (h + 15) // 16
    counts = {}
    for f in frames:
        for r, g, b, a in list(f.getdata()):
            if a:
                c = NS.neo_rgb((r, g, b))
                counts[c] = counts.get(c, 0) + 1
    pal = NS.sort_palette(NS.quantize(counts, 15))
    mapper = NS.Mapper(pal)
    canv = []
    for f in frames:
        c = Image.new("RGBA", (tw * 16, th * 16), (0, 0, 0, 0))
        c.paste(f, (0, 0))
        canv.append(c.load())
    groups = []
    for tx in range(tw):
        for ty in range(th):
            tiles = []
            for px in canv:
                data = bytearray()
                for y in range(16):
                    for x in range(16):
                        r, g, b, a = px[tx * 16 + x, ty * 16 + y]
                        data.append(mapper(NS.neo_rgb((r, g, b))) if a else 0)
                tiles.append(bytes(data))
            groups.append((0, None if all(not any(t) for t in tiles) else tiles))
    return [pal], groups, tw, th


def gather():
    """Lista de (símbolo, ruta, tipo); genera placeholders para lo que falte."""
    os.makedirs(PROC, exist_ok=True)
    items = []
    logos = sorted(glob.glob(os.path.join(SRC, "logos", "*.png")))
    if not logos:
        p = os.path.join(PROC, "logo_00_odaclick.png")
        placeholder_odaclick().save(p)
        logos = [p]
    for i, p in enumerate(logos):
        items.append(("UI_LOGO%d" % i, p, "logo"))
    tdir = os.path.join(SRC, "title")
    fire = sorted(glob.glob(os.path.join(tdir, "fire", "*.png")))
    if os.path.exists(os.path.join(tdir, "base.png")):
        items.append(("UI_TITLE", os.path.join(tdir, "base.png"), "title"))
    elif os.path.exists(os.path.join(SRC, "title.png")):
        items.append(("UI_TITLE", os.path.join(SRC, "title.png"), "title"))
    elif os.path.exists(os.path.join(ROOT, "art", "ref", "fieras-fighters-logo.png")):
        pdir = os.path.join(PROC, "title")
        os.makedirs(os.path.join(pdir, "fire"), exist_ok=True)
        b, frames, m = placeholder_fieras()
        b.save(os.path.join(pdir, "base.png"))
        m.save(os.path.join(pdir, "mask.png"))
        fire = []
        for i, f in enumerate(frames):
            fire.append(os.path.join(pdir, "fire", "%02d.png" % i))
            f.save(fire[-1])
        items.append(("UI_TITLE", os.path.join(pdir, "base.png"), "title"))
    else:
        t = os.path.join(PROC, "title.png")
        placeholder_title().save(t)
        items.append(("UI_TITLE", t, "title"))
    if fire:
        # fuego dentro de las letras de FIERAS: 8 cuadros de auto-animación
        items.append(("UI_TITLE_FIRE", fire, "anim8"))
    # fondo del título: cielo fijo y los dos bustos (se recortan a su caja)
    bg = os.path.join(SRC, "title_bg")
    if all(os.path.exists(os.path.join(bg, f)) for f in ("sky.png", "left.png", "right.png")):
        items.append(("UI_TITLE_SKY", os.path.join(bg, "sky.png"), "bg"))
        items.append(("UI_TITLE_LEFT", os.path.join(bg, "left.png"), "layer"))
        items.append(("UI_TITLE_RIGHT", os.path.join(bg, "right.png"), "layer"))
    for name in ROSTER:
        p = os.path.join(SRC, "portraits", name + ".png")
        if not os.path.exists(p):
            p = os.path.join(PROC, "portrait_%s.png" % name)
            placeholder_portrait(name).save(p)
        items.append(("UI_PORTRAIT_" + name, p, "portrait"))
    c = os.path.join(SRC, "cursor.png")
    if not os.path.exists(c):
        c = os.path.join(PROC, "cursor.png")
        placeholder_cursor().save(c)
    items.append(("UI_CURSOR", c, "cursor"))
    return items, len(logos)


def main():
    items, nlogos = gather()
    limits = {"logo": (320, 224), "title": (320, 160), "portrait": (64, 64), "cursor": (64, 64),
              "bg": (320, 224), "layer": (320, 224)}
    blank = bytes(256)
    uniq = {blank: 0}
    sheet_tiles = [blank]
    all_pals, imgs, cmap = [], [], []
    tile_ui = tile_ui_base()
    for sym, path, kind in items:
        if kind == "anim8":
            pals, groups, tw, th = palettize_anim(path)
            first = len(cmap)
            for pi, frames in groups:
                if frames is None:
                    cmap.append(0)
                    continue
                # grupo de 8 tiles consecutivos con el número absoluto múltiplo de 8
                while (tile_ui + len(sheet_tiles)) % 8:
                    sheet_tiles.append(blank)
                t = len(sheet_tiles)
                sheet_tiles.extend(frames)
                assert t < 2048
                cmap.append(t | 0x800 | (pi << 12))
            src = os.path.relpath(os.path.dirname(path[0]), ROOT)
            imgs.append((sym, first, tw, th, len(all_pals), len(pals), src + " (8 cuadros)", 0, 0))
            all_pals += pals
            print("neoui: %-22s %2dx%-2d tiles, %d grupos animados  <- %s" % (sym, tw, th, sum(1 for g in groups if g[1]), src))
            continue
        im = load(path, *limits[kind])
        ox = oy = 0
        if kind == "layer":
            # solo la caja opaca: las columnas vacías contarían en el límite
            # de 96 sprites por línea
            ox, oy, x1, y1 = im.getchannel("A").getbbox()
            im = im.crop((ox, oy, x1, y1))
            assert im.size[0] <= 160, "%s: la capa mide %d px de ancho (máx. 160)" % (path, im.size[0])
        pals, tiles, tw, th = palettize(im, MAX_PALS[kind])
        first = len(cmap)
        for pi, data in tiles:
            if data not in uniq:
                uniq[data] = len(sheet_tiles)
                sheet_tiles.append(data)
            t = uniq[data]
            assert t < 2048
            cmap.append(t | (pi << 12))
        imgs.append((sym, first, tw, th, len(all_pals), len(pals), os.path.relpath(path, ROOT), ox, oy))
        all_pals += pals
        print("neoui: %-22s %2dx%-2d tiles, %d paleta(s)  <- %s" % (sym, tw, th, len(pals), os.path.relpath(path, ROOT)))

    gray = [(i * 17, i * 17, i * 17) for i in range(16)]
    tiles_img = []
    for data in sheet_tiles:
        t = MA.new_p(16, 16, gray)
        t.putdata(list(data))
        tiles_img.append(t)
    sheet, used = MA.grid_sheet(tiles_img, gray)
    MA.save_gif(sheet, "ui.gif")

    with open(os.path.join(NS.GEN, "ui_gen.h"), "w") as f:
        f.write("/* Generado por tools/neoui.py: no editar a mano. */\n#ifndef GEN_UI_H\n#define GEN_UI_H\n"
                "#include <ngdevkit/types.h>\n#include \"gen/assets.h\"\n#include \"gen/char_p1.h\"\n"
                "#include \"gen/char_p2.h\"\n\n/* los tiles de la UI van después de los dos personajes */\n"
                "#define TILE_UI (TILE_END + CHAR_P1_TILES + CHAR_P2_TILES)\n#define UI_TILES %d\n"
                "#define UI_PALS %d\n#define UI_NLOGOS %d\n#define UI_ROSTER %d\n#define UI_HAS_FIRE %d\n#define UI_HAS_TITLE_BG %d\n\n"
                % (used, len(all_pals), nlogos, len(ROSTER), int(any(i[0] == "UI_TITLE_FIRE" for i in imgs)),
                   int(any(i[0] == "UI_TITLE_SKY" for i in imgs))))
        f.write("enum {\n" + "".join("    %s,\n" % i[0] for i in imgs) + "    UI_COUNT\n};\n\n")
        f.write("/* imagen: entradas de ui_map por columnas: tile (bits 0-10), bit 11 = grupo de\n"
                "   8 cuadros con auto-animación por hardware, paleta relativa en bits 12-15 */\n"
                "/* x, y: esquina de la imagen en su lienzo original (capas recortadas) */\n"
                "typedef struct { u16 first; u8 w, h; u8 pal0, npal; s16 x, y; } uiimg_t;\n"
                "extern const uiimg_t ui_imgs[UI_COUNT];\nextern const u16 ui_map[];\n"
                "extern const u16 ui_pals[UI_PALS][16];\n#endif\n")
    with open(os.path.join(NS.GEN, "ui_gen.c"), "w") as f:
        f.write("/* Generado por tools/neoui.py: no editar a mano. */\n#include \"gen/ui_gen.h\"\n\n"
                "typedef char crom_fits[(TILE_UI + UI_TILES <= 16384) ? 1 : -1];\n"
                "/* los grupos animados se alinearon a 8 suponiendo este TILE_UI */\n"
                "typedef char anim_aligned[(TILE_UI == %d) ? 1 : -1];\n"
                "/* paletas de UI: de PAL_UI (32) a PAL_SHINE (96) */\n"
                "typedef char pals_fit[(UI_PALS <= 64) ? 1 : -1];\n\n" % tile_ui)
        f.write("const uiimg_t ui_imgs[UI_COUNT] = {\n")
        for sym, first, tw, th, p0, np_, src, ox, oy in imgs:
            f.write("    {%d, %d, %d, %d, %d, %d, %d},   /* %s: %s */\n" % (first, tw, th, p0, np_, ox, oy, sym, src))
        f.write("};\n\nconst u16 ui_map[] = {\n")
        for i in range(0, len(cmap), 12):
            f.write("    " + ", ".join("0x%04x" % v for v in cmap[i:i + 12]) + ",\n")
        f.write("};\n\nconst u16 ui_pals[UI_PALS][16] = {\n")
        for p in all_pals:
            v = [0x8000] + [MA.packed15(c) for c in p] + [0] * (15 - len(p))
            f.write("    {" + ", ".join("0x%04x" % x for x in v) + "},\n")
        f.write("};\n")
    print("neoui: %d tiles únicos (%d con relleno), %d paletas" % (len(sheet_tiles), used, len(all_pals)))


if __name__ == "__main__":
    main()
