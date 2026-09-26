#!/usr/bin/env python3
"""neofx: efectos visuales del combate (chispas, guardia, bola, explosión, polvo).

Lee art/src/fx/ (contrato en art/src/fx/SOURCES.md):

  fx.json                 lista de animaciones, en orden:
                          {"name", "dir", "dur" (ticks por cuadro), "loop",
                           "anchor": [x, y] en el lienzo, "group"}
                          y "groups": {grupo: cantidad de paletas de 15 colores}
  <dir>/00.png, 01.png..  cuadros RGBA del mismo tamaño (alfa binario >= 128)

Cada grupo de animaciones comparte sus paletas; cada tile de 16x16 elige una
(atributo de paleta por tile en SCB1), así un degradé de fuego o de plasma no
queda posterizado a 15 colores. Los cuadros se recortan a su caja opaca en
tiles (las columnas vacías no gastan sprites por línea) y los tiles se
deduplican también espejados.

Salida: assets/vfx.gif (tiles, última parte de la C-ROM: TILE_VFX) y
src/gen/vfx_gen.c/.h. Solo Python 3 + Pillow.
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_assets as MA  # noqa: E402
import neosprite as NS    # noqa: E402
import neoui as NU        # noqa: E402

ROOT = NS.ROOT
SRC = os.path.join(ROOT, "art", "src", "fx")
MAX_PALS = 8          # paletas de hardware libres en el combate (ver src/fx.c)


def load_frames(folder):
    files = NS.frame_files(os.path.join(SRC, folder))
    assert files, "neofx: %s no tiene cuadros" % folder
    frames = []
    for p in files:
        im = Image.open(p).convert("RGBA")
        a = im.getchannel("A").point(lambda v: 255 if v >= NS.ALPHA_MIN else 0)
        im.putalpha(a)
        frames.append(im)
    size = frames[0].size
    assert all(f.size == size for f in frames), "neofx: %s: cuadros de distinto tamaño" % folder
    return frames


def main():
    spec = json.load(open(os.path.join(SRC, "fx.json")))
    groups = spec["groups"]
    assert sum(groups.values()) <= MAX_PALS, "neofx: más de %d paletas" % MAX_PALS
    blank = bytes(256)
    tiles = [blank]
    lookup = {blank: (0, 0)}
    all_pals, pal_base = [], {}
    fmap, frames_out, anims_out = [], [], []
    max_w = {}

    # paletas por grupo: se paletiza una tira con todos los cuadros del grupo
    anims = spec["anims"]
    loaded = {a["name"]: load_frames(a["dir"]) for a in anims}
    grid = {}   # nombre -> (lista de (pal, bytes) por cuadro [tx][ty], tw, th)
    for gname, npal in groups.items():
        members = [a for a in anims if a["group"] == gname]
        strip_w = sum(((loaded[a["name"]][0].size[0] + 15) // 16) * 16 * len(loaded[a["name"]]) for a in members)
        strip_h = max(((loaded[a["name"]][0].size[1] + 15) // 16) * 16 for a in members)
        strip = Image.new("RGBA", (strip_w, strip_h), (0, 0, 0, 0))
        x = 0
        places = []
        for a in members:
            fw = ((loaded[a["name"]][0].size[0] + 15) // 16) * 16
            for f in loaded[a["name"]]:
                strip.paste(f, (x, 0))
                places.append((a["name"], x // 16))
                x += fw
        pals, ptiles, tw, th = NU.palettize(strip, npal)
        pal_base[gname] = len(all_pals)
        all_pals += pals
        # ptiles va por columnas: índice tx * th + ty
        for a in members:
            im0 = loaded[a["name"]][0]
            ftw, fth = (im0.size[0] + 15) // 16, (im0.size[1] + 15) // 16
            per = []
            for (nm, tx0) in places:
                if nm != a["name"]:
                    continue
                per.append([[ptiles[(tx0 + cx) * th + cy] for cy in range(fth)] for cx in range(ftw)])
            grid[a["name"]] = (per, ftw, fth, pal_base[gname])
        print("neofx: grupo %-6s %d paleta(s), %d colores" % (gname, len(pals), sum(len(p) for p in pals)))

    for a in anims:
        per, ftw, fth, pb = grid[a["name"]]
        ax, ay = a["anchor"]
        first = len(frames_out)
        for cols in per:
            used = [(cx, cy) for cx in range(ftw) for cy in range(fth) if any(cols[cx][cy][1])]
            if not used:
                used = [(0, 0)]
            x0 = min(u[0] for u in used); x1 = max(u[0] for u in used)
            y0 = min(u[1] for u in used); y1 = max(u[1] for u in used)
            mfirst = len(fmap)
            for cx in range(x0, x1 + 1):
                for cy in range(y0, y1 + 1):
                    pi, data = cols[cx][cy]
                    if not any(data):
                        fmap.append(0)
                        continue
                    hit = lookup.get(data)
                    if hit is None:
                        t = len(tiles)
                        tiles.append(data)
                        lookup[data] = (t, 0)
                        lookup.setdefault(NS.flip_t(data, 1), (t, 1))
                        hit = (t, 0)
                    t, fl = hit
                    assert t < 2048
                    fmap.append(t | (fl << 11) | ((pb + pi) << 12))
            frames_out.append((mfirst, x1 - x0 + 1, y1 - y0 + 1, x0 * 16 - ax, y0 * 16 - ay))
        w = max(f[1] for f in frames_out[first:])
        h = max(f[2] for f in frames_out[first:])
        max_w[a["name"]] = w
        anims_out.append((a["name"], first, len(frames_out) - first, a["dur"], int(a.get("loop", 0)), w, h, a["dir"]))
        print("neofx: %-8s %2d cuadros x %d ticks, hasta %dx%d tiles  <- art/src/fx/%s" %
              (a["name"], len(frames_out) - first, a["dur"], w, h, a["dir"]))

    gray = [(i * 17, i * 17, i * 17) for i in range(16)]
    timg = []
    for data in tiles:
        t = MA.new_p(16, 16, gray)
        t.putdata(list(data))
        timg.append(t)
    sheet, used_tiles = MA.grid_sheet(timg, gray)
    MA.save_gif(sheet, "vfx.gif")

    with open(os.path.join(NS.GEN, "vfx_gen.h"), "w") as f:
        f.write("/* Generado por tools/neofx.py: no editar a mano. */\n#ifndef GEN_VFX_H\n#define GEN_VFX_H\n"
                "#include <ngdevkit/types.h>\n#include \"gen/ui_gen.h\"\n\n"
                "/* los tiles de los efectos van después de la UI (última parte de la C-ROM) */\n"
                "#define TILE_VFX (TILE_UI + UI_TILES)\n#define VFX_TILES %d\n#define VFX_PALS %d\n\n"
                % (used_tiles, len(all_pals)))
        f.write("enum {\n" + "".join("    VFX_%s,\n" % a[0].upper() for a in anims_out) + "    VFX_COUNT\n};\n\n")
        for a in anims_out:
            f.write("#define VFX_%s_W %d   /* columnas máximas */\n" % (a[0].upper(), a[5]))
        f.write("\n/* vfx_map: por cuadro, columnas de arriba a abajo: tile (bits 0-10),\n"
                "   espejo horizontal (bit 11), paleta relativa a vfx_pals (bits 12-15) */\n"
                "/* x, y: esquina del cuadro respecto del ancla, con el efecto mirando a la derecha */\n"
                "typedef struct { u16 first; u8 w, h; s16 x, y; } vfxframe_t;\n"
                "typedef struct { u8 first, count, dur, loop; } vfxanim_t;\n"
                "extern const vfxanim_t vfx_anims[VFX_COUNT];\nextern const vfxframe_t vfx_frames[];\n"
                "extern const u16 vfx_map[];\nextern const u16 vfx_pals[VFX_PALS][16];\n#endif\n")
    with open(os.path.join(NS.GEN, "vfx_gen.c"), "w") as f:
        f.write("/* Generado por tools/neofx.py: no editar a mano. */\n#include \"gen/vfx_gen.h\"\n\n"
                "typedef char vfx_crom_fits[(TILE_VFX + VFX_TILES <= 16384) ? 1 : -1];\n"
                "typedef char vfx_pals_fit[(VFX_PALS <= %d) ? 1 : -1];\n\n" % MAX_PALS)
        f.write("const vfxanim_t vfx_anims[VFX_COUNT] = {\n")
        for name, first, n, dur, loop, w, h, d in anims_out:
            f.write("    {%d, %d, %d, %d},   /* %s <- art/src/fx/%s */\n" % (first, n, dur, loop, name, d))
        f.write("};\n\nconst vfxframe_t vfx_frames[] = {\n")
        for fr in frames_out:
            f.write("    {%d, %d, %d, %d, %d},\n" % fr)
        f.write("};\n\nconst u16 vfx_map[] = {\n")
        for i in range(0, len(fmap), 12):
            f.write("    " + ", ".join("0x%04x" % v for v in fmap[i:i + 12]) + ",\n")
        f.write("};\n\nconst u16 vfx_pals[VFX_PALS][16] = {\n")
        for p in all_pals:
            v = [0x8000] + [MA.packed15(c) for c in p] + [0] * (15 - len(p))
            f.write("    {" + ", ".join("0x%04x" % x for x in v) + "},\n")
        f.write("};\n")
    print("neofx: %d tiles únicos (%d con relleno), %d paletas, %d cuadros" %
          (len(tiles), used_tiles, len(all_pals), len(frames_out)))


if __name__ == "__main__":
    main()
