#!/usr/bin/env python3
"""Música de FIERAS FIGHTERS escrita como datos: genera módulos Furnace (.fur)
para el YM2610 que después convierten nsstool/furtool de ngdevkit al formato
NSS que reproduce el driver nullsound en el Z80.

  python3 tools/make_music.py          -> assets/music/{title,select,fight,win}.fur

Por qué .fur y no audio grabado: la música FM ocupa unos pocos KB de M-ROM
(el Z80 toca las notas en vivo), igual que en los juegos de SNK, y deja la
V-ROM para los golpes, las voces y la batería en ADPCM-A.

Canales:
  FM1 bajo | FM2 melodía | FM3 y FM4 acordes, guitarras o arpegios
  ADPCM-A 5 bombo/redoblante | ADPCM-A 6 hi-hat, platillo, güira
  ADPCM-A 1-4 quedan libres para los efectos y el locutor.

Composiciones originales. Tempo: 60 ticks/s y "speed" = ticks por fila;
4 filas por negra, 16 por compás, 64 filas por patrón (4 compases).
El .fur usa el formato "viejo" (versión 224, bloque INFO), el mismo que el
ejemplo de ngdevkit, así que también se puede abrir y editar en Furnace.
"""
import os
import struct
import sys
import wave
import zlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT_DIR = os.path.join(ROOT, "assets", "music")
DRUM_DIR = os.path.join(OUT_DIR, "drums")

FUR_VERSION = 224
INS_VERSION = 224
NCH = 14                      # 4 FM, 3 SSG, 6 ADPCM-A, 1 ADPCM-B
F1, F2, F3, F4 = 0, 1, 2, 3
A5, A6 = 11, 12               # los dos ADPCM-A de la batería
ROWS = 64
OFF = 180                     # nota "OFF" en Furnace

# ------------------------------------------------------------------ notas
NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def n(name):
    """'E5', 'F#4', 'Bb3' -> valor de nota de Furnace (C-0 = 60, MIDI + 48)."""
    base = NAMES[name[0]]
    i = 1
    while i < len(name) and name[i] in "#b":
        base += 1 if name[i] == "#" else -1
        i += 1
    octave = int(name[i:])
    midi = (octave + 1) * 12 + base
    return midi + 48


# -------------------------------------------------------------- instrumentos
def op(ar=31, dr=0, sr=0, rr=7, sl=0, tl=0, mul=1, dt=0, ks=0):
    return dict(ar=ar, dr=dr, sr=sr, rr=rr, sl=sl, tl=tl, mul=mul, dt=dt, ks=ks)


class FM:
    """Instrumento FM de 4 operadores. s1..s4 en la numeración de los
    algoritmos del YM2610 (S1 es el que tiene feedback)."""
    def __init__(self, name, alg, fb, s1, s2, s3, s4, ams=0, fms=0):
        self.name, self.alg, self.fb = name, alg, fb
        self.ops = [s1, s2, s3, s4]
        self.ams, self.fms = ams, fms


class ADPCMA:
    def __init__(self, name, wav):
        self.name, self.wav = name, wav


# Patches propios. Portadoras con TL bajo (el volumen del patrón las escala).
BAJO = FM("bajo", 4, 5,
          op(ar=31, dr=12, sr=5, sl=3, rr=7, tl=28, mul=1),
          op(ar=31, dr=7, sr=3, sl=2, rr=9, tl=4, mul=1),
          op(ar=31, dr=10, sr=4, sl=4, rr=7, tl=34, mul=1, dt=1),
          op(ar=31, dr=6, sr=3, sl=2, rr=9, tl=8, mul=1, dt=-1))
GUITARRA = FM("guitarra", 3, 6,
              op(ar=31, dr=4, sr=2, sl=2, rr=6, tl=22, mul=1),
              op(ar=31, dr=5, sr=2, sl=2, rr=6, tl=27, mul=1, dt=2),
              op(ar=31, dr=8, sr=3, sl=3, rr=6, tl=30, mul=2),
              op(ar=31, dr=3, sr=1, sl=1, rr=8, tl=4, mul=1))
LIDER = FM("lider", 4, 5,
           op(ar=26, dr=6, sr=2, sl=2, rr=6, tl=26, mul=1),
           op(ar=28, dr=4, sr=1, sl=1, rr=7, tl=0, mul=1),
           op(ar=31, dr=8, sr=3, sl=3, rr=6, tl=36, mul=2, dt=1),
           op(ar=28, dr=4, sr=1, sl=1, rr=7, tl=10, mul=1, dt=-1))
ACORDEON = FM("acordeon", 4, 3,
              op(ar=24, dr=0, sr=0, sl=0, rr=6, tl=38, mul=3),
              op(ar=24, dr=2, sr=0, sl=1, rr=7, tl=2, mul=1, dt=1),
              op(ar=24, dr=0, sr=0, sl=0, rr=6, tl=34, mul=2),
              op(ar=24, dr=2, sr=0, sl=1, rr=7, tl=12, mul=2, dt=-1))
METALES = FM("metales", 4, 4,
             op(ar=18, dr=6, sr=1, sl=2, rr=5, tl=24, mul=1),
             op(ar=20, dr=3, sr=0, sl=1, rr=6, tl=0, mul=1),
             op(ar=18, dr=6, sr=1, sl=2, rr=5, tl=28, mul=1, dt=2),
             op(ar=20, dr=3, sr=0, sl=1, rr=6, tl=4, mul=1, dt=-2))
CAMPANA = FM("campana", 4, 2,
             op(ar=31, dr=10, sr=6, sl=5, rr=7, tl=32, mul=7),
             op(ar=31, dr=7, sr=4, sl=4, rr=7, tl=4, mul=2),
             op(ar=31, dr=12, sr=6, sl=5, rr=7, tl=30, mul=1),
             op(ar=31, dr=6, sr=3, sl=3, rr=7, tl=8, mul=1))
PIANO = FM("piano", 4, 3,
           op(ar=31, dr=10, sr=5, sl=4, rr=7, tl=30, mul=1),
           op(ar=31, dr=6, sr=3, sl=3, rr=8, tl=0, mul=1),
           op(ar=31, dr=14, sr=8, sl=6, rr=8, tl=40, mul=4),
           op(ar=31, dr=7, sr=3, sl=3, rr=8, tl=10, mul=2))


def load_pcm16(path):
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        return w.readframes(w.getnframes()), w.getnframes()


# ----------------------------------------------------------- escritura .fur
class Buf:
    def __init__(self):
        self.b = bytearray()

    def u1(self, v): self.b += struct.pack("<B", v)
    def u2(self, v): self.b += struct.pack("<H", v)
    def u4(self, v): self.b += struct.pack("<I", v)
    def s4(self, v): self.b += struct.pack("<i", v)
    def f4(self, v): self.b += struct.pack("<f", v)
    def raw(self, v): self.b += bytes(v)
    def str(self, s): self.b += s.encode("utf-8") + b"\0"


def block(tag, payload):
    return tag + struct.pack("<I", len(payload)) + bytes(payload)


def feature(code, payload):
    return code + struct.pack("<H", len(payload)) + bytes(payload)


def ins_block(ins):
    b = Buf()
    b.u2(INS_VERSION)
    if isinstance(ins, FM):
        b.u2(1)
        b.raw(feature(b"NA", ins.name.encode() + b"\0"))
        f = Buf()
        f.u1(0xf4)                                   # 4 operadores, todos activos
        f.u1((ins.alg & 7) << 4 | (ins.fb & 7))
        f.u1((ins.ams & 3) << 3 | (ins.fms & 7))
        f.u1(0)
        f.u1(0)                                      # block (>=224)
        s1, s2, s3, s4 = ins.ops
        for o in (s1, s3, s2, s4):                   # orden interno de Furnace: 1/3/2/4
            f.u1(((o["dt"] + 3) & 7) << 4 | (o["mul"] & 15))
            f.u1(o["tl"] & 0x7f)
            f.u1((o["ks"] & 3) << 6 | (o["ar"] & 31))
            f.u1(o["dr"] & 31)
            f.u1(o["sr"] & 31)
            f.u1((o["sl"] & 15) << 4 | (o["rr"] & 15))
            f.u1(0)
            f.u1(0)
        b.raw(feature(b"FM", f.b))
    else:
        b.u2(37)                                     # ADPCM-A
        b.raw(feature(b"NA", ins.name.encode() + b"\0"))
        b.raw(feature(b"SM", struct.pack("<HBB", ins.sample_idx, 0x02, 0)))
    return block(b"INS2", b.b)


def smp_block(name, pcm, nframes):
    b = Buf()
    b.str(name)
    b.u4(nframes)
    b.u4(18500)
    b.u4(18500)
    b.u1(16)                                         # PCM 16 bits: furtool lo pasa a ADPCM-A
    b.u1(0); b.u1(0); b.u1(0)
    b.s4(-1); b.s4(-1)
    b.raw(bytes(16))
    b.raw(pcm)
    return block(b"SMP2", b.b)


def patn_block(channel, index, rows):
    b = Buf()
    b.u1(0)
    b.u1(channel)
    b.u2(index)
    b.str("")
    empty = 0

    def flush():
        nonlocal empty
        while empty >= 2:
            m = min(empty, 129)
            b.u1(0x80 | (m - 2))
            empty -= m
        if empty == 1:
            b.u1(0)
            empty = 0

    for r in rows:
        if r is None:
            empty += 1
            continue
        flush()
        note, ins, vol, fx = r.get("note"), r.get("ins"), r.get("vol"), r.get("fx", [])
        desc = 0
        if note is not None: desc |= 1
        if ins is not None: desc |= 2
        if vol is not None: desc |= 4
        fxdesc = 0
        for i, _ in enumerate(fx):
            fxdesc |= 3 << (2 * i)
        if fxdesc & ~3:
            desc |= 0x20
        elif fxdesc:
            desc |= 0x18
        b.u1(desc)
        if desc & 0x20:
            b.u1(fxdesc & 0xff)
        if note is not None: b.u1(note)
        if ins is not None: b.u1(ins)
        if vol is not None: b.u1(vol)
        for f, val in fx:
            b.u1(f); b.u1(val)
    b.u1(0xff)
    return block(b"PATN", b.b)


class Song:
    def __init__(self, name, title, speed, orders, loop_to=0, fxcols=None):
        self.name, self.title, self.speed = name, title, speed
        self.norders = orders
        self.loop_to = loop_to
        self.instruments = []
        self.rows = [[None] * (orders * ROWS) for _ in range(NCH)]
        self.fxcols = fxcols or [2] * NCH

    def ins(self, instr):
        if instr not in self.instruments:
            self.instruments.append(instr)
        return self.instruments.index(instr)

    def cell(self, ch, pos):
        r = self.rows[ch][pos]
        if r is None:
            r = {}
            self.rows[ch][pos] = r
        return r

    def note(self, ch, pos, note, instr, vol=None, gate=None, fx=None):
        """Nota en la fila pos. gate = filas hasta el OFF (None: sin OFF)."""
        if pos >= len(self.rows[ch]):
            return
        r = self.cell(ch, pos)
        r["note"] = note
        r["ins"] = self.ins(instr)
        if vol is not None:
            r["vol"] = vol
        if fx:
            r.setdefault("fx", []).extend(fx)
        if gate is not None and pos + gate < len(self.rows[ch]):
            nxt = self.rows[ch][pos + gate]
            if nxt is None or "note" not in nxt:
                self.cell(ch, pos + gate)["note"] = OFF

    def fx(self, ch, pos, f, v):
        self.cell(ch, pos).setdefault("fx", []).append((f, v))

    def build(self):
        # loop: salto 0Bxx en la última fila (o parada si loop_to es None)
        last = self.norders * ROWS - 1
        if self.loop_to is not None:
            self.fx(F1, last, 0x0B, self.loop_to)
        # cortar en patrones de 64 filas y deduplicar por canal
        patterns = []                 # (canal, índice, filas)
        orders = [[0] * NCH for _ in range(self.norders)]
        for ch in range(NCH):
            seen = {}
            for o in range(self.norders):
                rows = self.rows[ch][o * ROWS:(o + 1) * ROWS]
                key = repr(rows)
                if key not in seen:
                    seen[key] = len(seen)
                    patterns.append((ch, seen[key], rows))
                orders[o][ch] = seen[key]
            for ch_, idx, rows in patterns:
                if ch_ == ch:
                    for r in rows:
                        if r and len(r.get("fx", [])) > self.fxcols[ch]:
                            raise ValueError("demasiados efectos en canal %d" % ch)
        return patterns, orders

    def to_fur(self):
        patterns, orders = self.build()
        # samples ADPCM-A (uno por instrumento de batería)
        samples = []
        for ins in self.instruments:
            if isinstance(ins, ADPCMA):
                pcm, nfr = load_pcm16(os.path.join(DRUM_DIR, ins.wav))
                ins.sample_idx = len(samples)
                samples.append(smp_block(ins.name, pcm, nfr))
        ins_blocks = [ins_block(i) for i in self.instruments]
        pat_blocks = [patn_block(ch, idx, rows) for ch, idx, rows in patterns]
        flag_block = block(b"FLAG", b"clockSel=0\nfmVol=256\nssgVol=256\n\0")

        def info(ptrs):
            b = Buf()
            b.u1(0); b.u1(self.speed); b.u1(self.speed); b.u1(1)
            b.f4(60.0)
            b.u2(ROWS); b.u2(self.norders)
            b.u1(4); b.u1(16)
            b.u2(len(ins_blocks)); b.u2(0); b.u2(len(samples)); b.u4(len(pat_blocks))
            b.raw(bytes([0xa5]) + bytes(31))                    # un solo chip: YM2610 (Neo Geo)
            b.raw(bytes([64]) + bytes(31))
            b.raw(bytes(32))
            b.u4(ptrs["flag"]); b.raw(bytes(124))
            b.str(self.title)
            b.str("Odaclick / FIERAS FIGHTERS")
            b.f4(440.0)
            b.raw(bytes([0, 2, 1, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0]))
            for p in ptrs["ins"]: b.u4(p)
            for p in ptrs["smp"]: b.u4(p)
            for p in ptrs["pat"]: b.u4(p)
            for ch in range(NCH):
                for o in range(self.norders):
                    b.u1(orders[o][ch])
            for ch in range(NCH): b.u1(self.fxcols[ch])
            b.raw(bytes(NCH)); b.raw(bytes(NCH))
            for _ in range(NCH): b.str("")
            for _ in range(NCH): b.str("")
            b.str("Generado por tools/make_music.py")
            b.f4(1.0)
            b.raw(bytes(28))
            b.u2(150); b.u2(150)
            b.str(""); b.str(""); b.u1(0); b.raw(bytes(3))
            b.str("Neo Geo MVS"); b.str("FIERAS FIGHTERS")
            b.str(""); b.str(""); b.str(""); b.str("")
            b.f4(1.0); b.f4(0.0); b.f4(0.0)
            b.u4(0); b.u1(1)
            b.raw(bytes(8))
            b.u1(1); b.raw(bytes([self.speed]) + bytes(15))
            b.u1(0)
            b.u4(0); b.u4(0); b.u4(0)
            return block(b"INFO", b.b)

        # dos pasadas: la primera calcula el tamaño del INFO, la segunda los punteros
        dummy = {"ins": [0] * len(ins_blocks), "smp": [0] * len(samples),
                 "pat": [0] * len(pat_blocks), "flag": 0}
        pos = 32 + len(info(dummy))
        ptrs = {"ins": [], "smp": [], "pat": []}
        for b_ in ins_blocks:
            ptrs["ins"].append(pos); pos += len(b_)
        for b_ in samples:
            ptrs["smp"].append(pos); pos += len(b_)
        for b_ in pat_blocks:
            ptrs["pat"].append(pos); pos += len(b_)
        ptrs["flag"] = pos
        hdr = b"-Furnace module-" + struct.pack("<HHI", FUR_VERSION, 0, 32) + bytes(8)
        data = hdr + info(ptrs) + b"".join(ins_blocks) + b"".join(samples) \
            + b"".join(pat_blocks) + flag_block
        return zlib.compress(data, 9)


# ------------------------------------------------------ ayudas de composición
KICK = ADPCMA("bombo", "kick.wav")
SNARE = ADPCMA("redoblante", "snare.wav")
HAT = ADPCMA("hihat", "hat.wav")
OHAT = ADPCMA("hihat_abierto", "openhat.wav")
CRASH = ADPCMA("platillo", "crash.wav")
TOM = ADPCMA("tom", "tom.wav")
GUIRA = ADPCMA("guira", "guira.wav")


def melody(song, ch, start, seq, instr, vol, legato=False, vib_from=8):
    """seq: 'E5:4 D5:2 r:2 ...' duraciones en filas (4 = negra)."""
    pos = start
    for tok in seq.split():
        name, dur = tok.split(":")
        dur = int(dur)
        if name != "r":
            fx = [(0x04, 0x34)] if dur >= vib_from else [(0x04, 0x00)]
            gate = dur if legato else max(dur - 1, 1)
            song.note(ch, pos, n(name), instr, vol, gate=gate, fx=fx)
        pos += dur
    return pos


def drums(song, start, bars, pattern, vol_k=0x1f, vol_s=0x1c, vol_h=0x12):
    """pattern: dict con listas de filas dentro del compás (0-15)."""
    for bar in range(bars):
        b0 = start + bar * 16
        for r in pattern.get("k", []):
            song.note(A5, b0 + r, n("C4"), KICK, vol_k)
        for r in pattern.get("s", []):
            song.note(A5, b0 + r, n("C4"), SNARE, vol_s)
        for r in pattern.get("h", []):
            song.note(A6, b0 + r, n("C4"), HAT, vol_h)
        for r in pattern.get("o", []):
            song.note(A6, b0 + r, n("C4"), OHAT, vol_h + 2)
        for r in pattern.get("g", []):
            song.note(A6, b0 + r, n("C4"), GUIRA, vol_h + 4)


def crash(song, pos, vol=0x1a):
    song.note(A6, pos, n("C4"), CRASH, vol)


def fill(song, pos, vol=0x1c):
    """Redoble de tom y redoblante en el último compás."""
    for i, r in enumerate([8, 10, 11, 12, 13, 14, 15]):
        song.note(A5, pos + r, n("C4"), TOM if i < 3 else SNARE, vol)


ROCK = {"k": [0, 6, 8, 10], "s": [4, 12], "h": [0, 2, 4, 6, 8, 10, 12, 14]}
ROCK_B = {"k": [0, 3, 8, 10], "s": [4, 12], "h": [0, 2, 4, 6, 8, 10, 12], "o": [14]}
CUARTETO = {"k": [0, 8], "s": [12], "h": [0, 4, 8], "g": [2, 6, 10, 14]}
EPIC = {"k": [0, 10], "s": [8], "h": [0, 4, 8, 12]}


def bass_rock(song, pos, root, bars=1, vol=0x7f):
    """Corcheas con salto de octava (rock nacional de guitarra al palo)."""
    r = n(root)
    for bar in range(bars):
        for i, off in enumerate([0, 2, 4, 6, 8, 10, 12, 14]):
            note = r + 12 if i in (3, 7) else r
            song.note(F1, pos + bar * 16 + off, note, BAJO, vol, gate=1)


def power(song, pos, root, rows, vol=0x6c, gate=1):
    """Quinta de guitarra distorsionada en FM3 (raíz) y FM4 (quinta)."""
    r = n(root)
    for off in rows:
        song.note(F3, pos + off, r, GUITARRA, vol, gate=gate)
        song.note(F4, pos + off, r + 7, GUITARRA, vol - 6, gate=gate)


# ------------------------------------------------------------------ canciones
def fight_theme():
    """'Córdoba en llamas' - Mi menor, 150 BPM. Rock nacional con un puente
    de cuarteto (bajo tunga-tunga, güira en los contratiempos y acordeón)."""
    s = Song("fight", "Cordoba en llamas", speed=6, orders=8, loop_to=1)
    R = ROWS
    # --- 0: intro, golpes de guitarra
    hits = [("E2", [0]), ("E2", [0, 6, 10]), ("C2", [0]), ("D2", [0, 6, 10])]
    for bar, (root, rows) in enumerate(hits):
        p = bar * 16
        for r in rows:
            s.note(F1, p + r, n(root), BAJO, 0x7f, gate=5 if r == 0 else 3)
        power(s, p, root.replace("2", "3"), rows, gate=5)
        for r in rows:
            s.note(A5, p + r, n("C4"), KICK, 0x1f)
        crash(s, p)
    melody(s, F2, 32, "B4:4 D5:4 E5:4 F#5:4 G5:4 A5:4 B5:8", LIDER, 0x6a)
    fill(s, 48)
    # --- 1-2: estrofa A
    chords_a = ["E", "C", "D", "B", "E", "C", "A", "B"]
    for i, c in enumerate(chords_a):
        p = R + i * 16
        bass_rock(s, p, c + "2")
        power(s, p, c + "3", [0, 3, 6, 10, 12])
    drums(s, R, 8, ROCK)
    crash(s, R)
    fill(s, R + 7 * 16)
    melody(s, F2, R,
           "E5:4 D5:2 E5:2 G5:4 A5:2 G5:2 "
           "E5:6 D5:2 C5:4 D5:4 "
           "D5:4 E5:2 F#5:2 A5:4 F#5:2 D5:2 "
           "D#5:8 F#5:4 B5:4 "
           "E5:4 D5:2 E5:2 G5:4 B5:4 "
           "C6:6 B5:2 A5:4 G5:4 "
           "A5:4 G5:2 E5:2 C5:4 E5:2 A5:2 "
           "B5:8 A5:2 G5:2 F#5:2 D#5:2", LIDER, 0x70)
    # --- 3-4: estrofa A' (riff más agudo)
    for i, c in enumerate(chords_a):
        p = 3 * R + i * 16
        bass_rock(s, p, c + "2")
        power(s, p, c + "3", [0, 2, 4, 6, 8, 10, 12, 14], vol=0x64)
    drums(s, 3 * R, 8, ROCK_B)
    crash(s, 3 * R)
    fill(s, 3 * R + 7 * 16)
    melody(s, F2, 3 * R,
           "B5:2 B5:2 A5:2 B5:2 G5:2 A5:2 E5:4 "
           "G5:2 G5:2 E5:2 G5:2 C6:4 B5:4 "
           "A5:2 A5:2 F#5:2 A5:2 D6:4 C6:2 A5:2 "
           "B5:12 r:4 "
           "B5:2 B5:2 A5:2 B5:2 G5:2 A5:2 E5:4 "
           "G5:2 G5:2 E5:2 G5:2 C6:4 E6:4 "
           "D6:4 C6:4 B5:4 A5:4 "
           "B5:4 F#5:4 D#5:4 B4:4", LIDER, 0x70)
    # --- 5-6: puente de cuarteto cordobés
    chords_b = [("A", "C", "E"), ("D", "F#", "A"), ("G", "B", "D"), ("C", "E", "G"),
                ("A", "C", "E"), ("B", "D#", "F#"), ("E", "G", "B"), ("B", "D#", "F#")]
    for i, (root, third, fifth) in enumerate(chords_b):
        p = 5 * R + i * 16
        r2, f2 = n(root + "2"), n(fifth + "2")
        if f2 < r2:
            f2 += 12
        for off, note, g in [(0, r2, 3), (6, r2, 1), (8, f2, 3), (14, f2, 1)]:   # tunga-tunga
            s.note(F1, p + off, note, BAJO, 0x7f, gate=g)
        t4, q4 = n(third + "4"), n(fifth + "4")
        if q4 < t4:
            q4 += 12
        for off in (2, 6, 10, 14):                                             # "chas" del piano
            s.note(F3, p + off, t4, PIANO, 0x5c, gate=1)
            s.note(F4, p + off, q4, PIANO, 0x56, gate=1)
    drums(s, 5 * R, 8, CUARTETO)
    crash(s, 5 * R)
    melody(s, F2, 5 * R,
           "A5:2 C6:2 E6:4 D6:2 C6:2 B5:2 C6:2 "
           "A5:4 F#5:2 A5:2 D6:4 C6:2 A5:2 "
           "B5:2 D6:2 G6:4 F#6:2 E6:2 D6:2 B5:2 "
           "C6:6 B5:2 A5:2 G5:2 E5:4 "
           "A5:2 C6:2 E6:4 D6:2 C6:2 B5:2 C6:2 "
           "D#6:4 B5:2 F#5:2 A5:4 B5:4 "
           "G5:2 B5:2 E6:4 D6:2 B5:2 G5:2 E5:2 "
           "F#5:4 A5:4 D#6:4 B5:4", ACORDEON, 0x6c, vib_from=4)
    # --- 7: puente de vuelta, crece
    p = 7 * R
    for bar in range(4):
        for i in range(8):
            s.note(F1, p + bar * 16 + i * 2, n("E2"), BAJO, 0x6a + bar * 5, gate=1)
        power(s, p + bar * 16, "E3", [0, 2, 4, 6, 8, 10, 12, 14], vol=0x58 + bar * 5)
    drums(s, p, 3, {"k": [0, 4, 8, 12], "h": [0, 2, 4, 6, 8, 10, 12, 14]})
    for r in range(0, 16, 2):
        s.note(A5, p + 48 + r, n("C4"), SNARE if r % 4 else TOM, 0x14 + r // 2)
    melody(s, F2, p + 48, "B4:2 C#5:2 D#5:2 E5:2 F#5:2 G5:2 A5:2 B5:2", LIDER, 0x70)
    return s


def title_theme():
    """'Fieras' - La menor, ~129 BPM. Épico: metales, bajo largo, campanas."""
    s = Song("title", "Fieras", speed=7, orders=4, loop_to=1)
    R = ROWS
    prog_intro = [("A", "C", "E"), ("F", "A", "C"), ("G", "B", "D"), ("E", "G#", "B")]
    # --- 0: intro
    for i, (root, third, fifth) in enumerate(prog_intro):
        p = i * 16
        s.note(F1, p, n(root + "2"), BAJO, 0x7a, gate=14)
        s.note(F3, p, n(third + "4") if third < "C" or third[0] in "AB" else n(third + "4"),
               METALES, 0x64, gate=15)
        s.note(F4, p, n(fifth + "4"), METALES, 0x5e, gate=15)
        s.note(A5, p, n("C4"), TOM, 0x1c)
        s.note(A5, p + 8, n("C4"), TOM, 0x16)
    crash(s, 0)
    fill(s, 48, vol=0x18)
    # --- 1-2: tema
    prog = [("A", "C", "E"), ("F", "A", "C"), ("C", "E", "G"), ("G", "B", "D"),
            ("A", "C", "E"), ("F", "A", "C"), ("G", "B", "D"), ("E", "G#", "B")]
    for i, (root, third, fifth) in enumerate(prog):
        p = R + i * 16
        s.note(F1, p, n(root + "2"), BAJO, 0x7f, gate=7)
        s.note(F1, p + 8, n(root + "3"), BAJO, 0x78, gate=5)
        s.note(F1, p + 14, n(root + "2"), BAJO, 0x70, gate=1)
        s.note(F3, p, n(third + "4"), METALES, 0x5c, gate=15)
        s.note(F4, p, n(fifth + "4"), METALES, 0x56, gate=15)
    drums(s, R, 8, EPIC)
    crash(s, R)
    fill(s, R + 7 * 16, vol=0x18)
    melody(s, F2, R,
           "A4:4 C5:4 E5:6 D5:2 "
           "C5:4 A4:4 F5:8 "
           "E5:4 G5:4 C6:6 B5:2 "
           "B5:4 A5:2 G5:2 D5:8 "
           "E5:4 A5:4 C6:6 B5:2 "
           "A5:4 F5:4 C6:8 "
           "B5:4 D6:4 G5:4 B5:4 "
           "G#5:8 B5:4 E5:4", LIDER, 0x72)
    # --- 3: puente con arpegio de campanas
    bridge = [("D", ["D5", "F5", "A5", "D6"], "F5"), ("A", ["C5", "E5", "A5", "C6"], "E5"),
              ("F", ["C5", "F5", "A5", "C6"], "A5"), ("E", ["B4", "E5", "G#5", "B5"], "G#5")]
    for i, (root, arp, lead) in enumerate(bridge):
        p = 3 * R + i * 16
        s.note(F1, p, n(root + "2"), BAJO, 0x7c, gate=14)
        for k in range(16):
            s.note(F4, p + k, n(arp[k % 4]), CAMPANA, 0x5a if k % 4 else 0x66, gate=1)
        s.note(F3, p, n(arp[1].replace("5", "4").replace("6", "5")), METALES, 0x56, gate=15)
        s.note(F2, p, n(lead), LIDER, 0x6a, gate=15, fx=[(0x04, 0x34)])
    drums(s, 3 * R, 4, {"k": [0, 8], "h": [0, 2, 4, 6, 8, 10, 12, 14]}, vol_h=0x0e)
    fill(s, 3 * R + 48, vol=0x18)
    return s


def select_theme():
    """Selector: Re menor, 150 BPM, ostinato tenso de 8 compases."""
    s = Song("select", "Elegi tu fiera", speed=6, orders=2, loop_to=0)
    prog = [("D", "F", "A"), ("Bb", "D", "F"), ("C", "E", "G"), ("A", "C#", "E")] * 2
    for i, (root, third, fifth) in enumerate(prog):
        p = i * 16
        r = n(root + "2")
        for k, off in enumerate([0, 2, 4, 6, 8, 10, 12, 14]):
            s.note(F1, p + off, r + (12 if k % 4 == 2 else 0), BAJO, 0x78, gate=1)
        t, f = n(third + "4"), n(fifth + "4")
        if f < t:
            f += 12
        for off in (0, 3, 6, 10, 12):
            s.note(F3, p + off, t, PIANO, 0x5c, gate=1)
            s.note(F4, p + off, f, PIANO, 0x56, gate=1)
    drums(s, 0, 8, {"k": [0, 6, 8], "s": [4, 12], "h": [0, 2, 4, 6, 8, 10, 12, 14]}, vol_h=0x10)
    crash(s, 0)
    melody(s, F2, 64,
           "D5:4 F5:4 A5:4 G5:2 F5:2 "
           "F5:4 D5:4 Bb5:8 "
           "G5:4 E5:4 C6:4 Bb5:2 A5:2 "
           "A5:8 C#6:4 E6:4", LIDER, 0x66)
    fill(s, 7 * 16)
    return s


def win_jingle():
    """Fanfarria corta de victoria en Mi mayor (no loopea). Dura ~2.3 s para
    entrar en el cartel final del match (150 frames) antes de volver al attract."""
    s = Song("win", "Victoria", speed=6, orders=1, loop_to=None)
    melody(s, F2, 0, "E5:2 G#5:2 B5:2 E6:6 D#6:1 E6:1 F#6:2 E6:7", LIDER, 0x74, vib_from=6)
    for p, (t, f), g in [(0, ("G#4", "B4"), 11), (12, ("A4", "C#5"), 3), (16, ("G#4", "B4"), 7)]:
        s.note(F3, p, n(t), METALES, 0x62, gate=g)
        s.note(F4, p, n(f), METALES, 0x5c, gate=g)
    for p, root, g in [(0, "E2", 11), (12, "A2", 3), (16, "E2", 7)]:
        s.note(F1, p, n(root), BAJO, 0x7f, gate=g)
    for r in (0, 6, 16):
        s.note(A5, r, n("C4"), KICK, 0x1f)
    s.note(A5, 12, n("C4"), SNARE, 0x1c)
    s.note(A5, 14, n("C4"), SNARE, 0x1c)
    crash(s, 0)
    crash(s, 16)
    return s


SONGS = [title_theme, select_theme, fight_theme, win_jingle]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for fn in SONGS:
        song = fn()
        data = song.to_fur()
        path = os.path.join(OUT_DIR, song.name + ".fur")
        with open(path, "wb") as f:
            f.write(data)
        secs = song.norders * ROWS * song.speed / 60.0
        print("%-7s %5d bytes  %2d patrones x 64 filas  %.1f s" % (song.name, len(data), song.norders, secs))


if __name__ == "__main__":
    sys.exit(main())
