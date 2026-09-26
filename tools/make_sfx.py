#!/usr/bin/env python3
"""Síntesis procedural de los efectos, las voces del locutor y la batería
de FIERAS FIGHTERS. Todo sale de numpy/scipy: no hay samples de terceros.

Salida (WAV mono 16 bits a 18500 Hz, la frecuencia fija de ADPCM-A):
  assets/sfx/*.wav            efectos y voces (los empaqueta vromtool)
  assets/music/drums/*.wav    batería que tools/make_music.py mete en los .fur

Receta general, estilo arcade de los 90:
  transitorio (click de ruido de 3-10 ms) + cuerpo (seno con caída de tono)
  + cola corta, saturación suave con tanh y un "bit-crush" leve a 10 bits
  para que suene de época. Los golpes son cortos (<250 ms) para no pisarse.

"""
import os
import sys
import wave

import numpy as np
from scipy.signal import butter, lfilter

SR = 18500
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SFX_DIR = os.path.join(ROOT, "assets", "sfx")
DRUM_DIR = os.path.join(ROOT, "assets", "music", "drums")

rng = np.random.default_rng(1986)   # semilla fija: el build es reproducible


# ---------------------------------------------------------------- utilidades
def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def env_exp(dur, tau, attack=0.0):
    t = t_axis(dur)
    e = np.exp(-t / tau)
    if attack > 0:
        e *= np.clip(t / attack, 0, 1)
    return e


def sweep_sine(dur, f0, f1, curve=0.03):
    """Seno cuyo tono cae exponencialmente de f0 a f1 (bombo, golpes)."""
    t = t_axis(dur)
    f = f1 + (f0 - f1) * np.exp(-t / curve)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def sweep_lin(dur, f0, f1, wave_fn=np.sin):
    t = t_axis(dur)
    f = np.linspace(f0, f1, len(t))
    return wave_fn(2 * np.pi * np.cumsum(f) / SR)


def square(ph):
    return np.sign(np.sin(ph))


def saw(ph):
    return 2 * ((ph / (2 * np.pi)) % 1.0) - 1


def noise(dur):
    return rng.uniform(-1, 1, int(dur * SR))


def bp(x, lo, hi, order=2):
    b, a = butter(order, [lo / (SR / 2), min(hi / (SR / 2), 0.99)], btype="band")
    return lfilter(b, a, x)


def lp(x, fc, order=2):
    b, a = butter(order, min(fc / (SR / 2), 0.99), btype="low")
    return lfilter(b, a, x)


def hp(x, fc, order=2):
    b, a = butter(order, fc / (SR / 2), btype="high")
    return lfilter(b, a, x)


def sweep_bp(x, f_start, f_end, q=2.0, steps=48):
    """Pasabanda cuyo centro se mueve (whoosh, fuego)."""
    out = np.zeros_like(x)
    n = len(x)
    edges = np.linspace(0, n, steps + 1).astype(int)
    fcs = np.interp(np.linspace(0, 1, steps), np.linspace(0, 1, len(f_start)), f_start) \
        if isinstance(f_start, (list, np.ndarray)) else np.geomspace(f_start, f_end, steps)
    for i in range(steps):
        fc = fcs[i]
        lo, hi = fc / (1 + 1 / q), fc * (1 + 1 / q)
        seg = bp(x, lo, hi)[edges[i]:edges[i + 1]]
        out[edges[i]:edges[i + 1]] = seg
    return out


def pad(x, dur):
    n = int(dur * SR)
    if len(x) >= n:
        return x[:n]
    return np.concatenate([x, np.zeros(n - len(x))])


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def delay_mix(x, delays):
    """Ecos discretos (reverb barata de estadio) -> [(segundos, ganancia)]."""
    extra = int(max(d for d, _ in delays) * SR)
    out = np.concatenate([x, np.zeros(extra)])
    for d, g in delays:
        k = int(d * SR)
        out[k:k + len(x)] += g * x
    return out


def finish(x, drive=1.5, crush_bits=10, peak=0.93, fade_ms=4):
    x = np.asarray(x, dtype=np.float64)
    x = np.tanh(drive * x / (np.max(np.abs(x)) + 1e-9))
    x = x / (np.max(np.abs(x)) + 1e-9) * peak
    if crush_bits:
        q = 2 ** (crush_bits - 1)
        x = np.round(x * q) / q
    nf = int(fade_ms * SR / 1000)
    if nf and len(x) > nf:
        x[-nf:] *= np.linspace(1, 0, nf)
    # vromtool alinea a 256 bytes de ADPCM (512 muestras): rellenamos con
    # silencio para que el final del sample no quede con basura
    rem = (-len(x)) % 512
    return np.concatenate([x, np.zeros(rem)])


def write_wav(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)


# ------------------------------------------------------------- efectos (SFX)
def sfx_hit():
    """Golpe liviano: chasquido + cuerpo corto."""
    d = 0.11
    click = hp(noise(d), 2500) * env_exp(d, 0.006)
    slap = bp(noise(d), 900, 3200) * env_exp(d, 0.03)
    body = sweep_sine(d, 260, 90, 0.02) * env_exp(d, 0.045)
    return finish(mix(0.7 * click, 0.8 * slap, 1.0 * body), drive=2.2)


def sfx_heavy():
    """Golpe fuerte: más grave, más largo, saturado."""
    d = 0.24
    click = hp(noise(d), 2000) * env_exp(d, 0.008)
    crack = bp(noise(d), 500, 2600) * env_exp(d, 0.05)
    body = sweep_sine(d, 200, 48, 0.035) * env_exp(d, 0.09)
    sub = sweep_sine(d, 90, 40, 0.06) * env_exp(d, 0.12)
    return finish(mix(0.6 * click, 0.9 * crack, 1.2 * body, 0.6 * sub), drive=3.0)


def sfx_block():
    """Bloqueo: 'clank' metálico (ROBOCLICK es cyborg) con parciales inarmónicos."""
    d = 0.14
    t = t_axis(d)
    parts = [(1180, 1.0, 0.05), (1730, 0.7, 0.04), (2610, 0.55, 0.03),
             (3890, 0.4, 0.02), (620, 0.5, 0.035)]
    ring = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau) for f, a, tau in parts)
    click = hp(noise(d), 3000) * env_exp(d, 0.004)
    thud = sweep_sine(d, 180, 110, 0.02) * env_exp(d, 0.03)
    return finish(mix(ring, 0.8 * click, 0.5 * thud), drive=1.8)


def sfx_whoosh():
    """Swing de un golpe al aire: ruido con pasabanda que sube y baja."""
    d = 0.2
    n = noise(d)
    x = sweep_bp(n, [500, 1600, 2600, 1400, 700], None, q=1.6)
    t = t_axis(d)
    e = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.5
    return finish(x * e, drive=1.2, peak=0.8)


def sfx_fireball():
    """Lanzamiento de la bola de energía: rugido que sube + zumbido tonal."""
    d = 0.5
    t = t_axis(d)
    f = 140 + 520 * (1 - np.exp(-t / 0.12))
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = 0.6 * saw(ph) + 0.4 * square(ph * 0.5)
    tone = lp(tone, 2200) * (1 + 0.35 * np.sin(2 * np.pi * 28 * t))  # temblor de energía
    roar = sweep_bp(noise(d), 400, 3000, q=1.2)
    thump = sweep_sine(d, 160, 60, 0.03) * env_exp(d, 0.06)
    e = np.clip(t / 0.02, 0, 1) * np.exp(-np.maximum(t - 0.15, 0) / 0.14)
    return finish(mix((0.8 * tone + 0.7 * roar) * e, 0.9 * thump), drive=2.2)


def sfx_fbhit():
    """Impacto de la bola: explosión corta."""
    d = 0.38
    boom = lp(noise(d), 1400) * env_exp(d, 0.09)
    crack = hp(noise(d), 2500) * env_exp(d, 0.012)
    body = sweep_sine(d, 150, 38, 0.05) * env_exp(d, 0.12)
    return finish(mix(1.0 * boom, 0.5 * crack, 1.1 * body), drive=2.6)


def sfx_ko():
    """Golpe final: impacto enorme + cola larga que resuena."""
    d = 0.95
    t = t_axis(d)
    click = hp(noise(d), 1800) * env_exp(d, 0.01)
    crack = bp(noise(d), 300, 2400) * env_exp(d, 0.08)
    body = sweep_sine(d, 170, 32, 0.06) * env_exp(d, 0.3)
    ring = (np.sin(2 * np.pi * 97 * t) + 0.5 * np.sin(2 * np.pi * 146 * t)) * env_exp(d, 0.35)
    x = mix(0.6 * click, 1.0 * crack, 1.3 * body, 0.35 * ring)
    return finish(delay_mix(x, [(0.09, 0.35), (0.19, 0.2)])[:int(1.1 * SR)], drive=3.0)


def sfx_land():
    """Caída al piso después de un salto."""
    d = 0.1
    thud = sweep_sine(d, 130, 55, 0.02) * env_exp(d, 0.035)
    dust = lp(noise(d), 1800) * env_exp(d, 0.025)
    return finish(mix(1.0 * thud, 0.5 * dust), drive=1.8, peak=0.75)


def sfx_menu_move():
    """Cursor del menú: blip de onda cuadrada, dos tonos (chip de época)."""
    t1, t2 = t_axis(0.025), t_axis(0.03)
    a = square(2 * np.pi * 1245 * t1) * 0.8
    b = square(2 * np.pi * 1865 * t2) * np.exp(-t2 / 0.015)
    return finish(np.concatenate([a, b]), drive=1.0, peak=0.6, crush_bits=8)


def sfx_menu_ok():
    """Confirmar: arpegio ascendente + golpe grave (estilo selector de KOF)."""
    notes = [1047, 1319, 1568, 2093]   # C6 E6 G6 C7
    seg = []
    for i, f in enumerate(notes):
        tt = t_axis(0.045 if i < 3 else 0.2)
        e = np.exp(-tt / (0.03 if i < 3 else 0.08))
        seg.append((0.7 * square(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)) * e)
    arp = np.concatenate(seg)
    punch = sweep_sine(0.18, 220, 70, 0.025) * env_exp(0.18, 0.05)
    return finish(mix(0.6 * arp, 0.9 * punch), drive=1.6, peak=0.85, crush_bits=9)


def sfx_logo():
    """Golpe del logo: boom de cine + anillo metálico."""
    d = 0.8
    t = t_axis(d)
    boom = sweep_sine(d, 120, 30, 0.08) * env_exp(d, 0.3)
    crack = lp(noise(d), 3000) * env_exp(d, 0.05)
    ring = sum(a * np.sin(2 * np.pi * f * t) for f, a in [(523, 0.4), (784, 0.3), (1318, 0.2)]) \
        * env_exp(d, 0.25, attack=0.005)
    x = mix(1.3 * boom, 0.8 * crack, 0.4 * ring)
    return finish(delay_mix(x, [(0.11, 0.3), (0.23, 0.15)])[:int(0.95 * SR)], drive=2.4)


def sfx_fire():
    """Ignición del fuego del título: soplido que se abre + chisporroteo."""
    d = 0.9
    t = t_axis(d)
    n = noise(d)
    x = sweep_bp(n, [250, 700, 1800, 2400, 1500], None, q=0.9)
    rumble = lp(noise(d), 180) * 2.5
    crackle = np.zeros(len(t))
    for _ in range(40):
        k = rng.integers(int(0.1 * SR), len(t) - 200)
        crackle[k:k + 60] += rng.uniform(0.4, 1.0) * hp(noise(60 / SR), 3000)
    e = np.clip(t / 0.18, 0, 1) * np.exp(-np.maximum(t - 0.35, 0) / 0.25)
    return finish(mix(x * e, rumble * e, 0.5 * crackle * e), drive=1.6, peak=0.85)


def sfx_char_ok():
    """Personaje elegido: golpe de platillo invertido + acorde brillante de
    metales FM (E mayor) + bombo cinematográfico y ecos de estadio. Es más
    ancho y grave que SND_MENU_OK (que es un arpegio chiquito): suena a
    "¡este!" como el golpe del selector de KOF. Usa su propio generador de
    ruido para no correr la semilla de los demás efectos."""
    r = np.random.default_rng(1997)
    d = 0.62
    t = t_axis(d)
    n = r.uniform(-1, 1, len(t))
    # "shing": ruido agudo que se abre de golpe y se apaga en ~120 ms
    shing = hp(n, 4200) * env_exp(d, 0.11, attack=0.004)
    crack = bp(n, 1200, 5200) * env_exp(d, 0.014)
    # acorde de metales: diente de sierra + cuadrada, un toque de desafinación
    chord = np.zeros(len(t))
    for f, a in [(659.3, 1.0), (830.6, 0.8), (987.8, 0.8), (1318.5, 0.6), (329.6, 0.7)]:
        ph = 2 * np.pi * f * t
        chord += a * (0.6 * saw(ph) + 0.4 * saw(ph * 1.006) + 0.3 * square(ph))
    chord = lp(chord, 5200) * env_exp(d, 0.16, attack=0.003)
    boom = sweep_sine(d, 190, 42, 0.04) * env_exp(d, 0.14)
    x = mix(0.55 * shing, 0.5 * crack, 0.32 * chord, 1.1 * boom)
    return finish(delay_mix(x, [(0.085, 0.3), (0.17, 0.14)])[:int(0.72 * SR)], drive=2.3, peak=0.9)


# ----------------------------------------------------------- voces (locutor)
# Locutor robótico (le queda bien a un torneo con un perro cyborg): síntesis
# por formantes en cascada tipo Klatt. Fuente glotal en diente de sierra,
# tres formantes móviles (Peterson & Barney, 1952) más F4/F5 fijos, y ruido
# filtrado para las consonantes. Cada voz va montada sobre un "stinger"
# sintético (acorde, golpe o platillo) para que funcione aunque la palabra
# no se entienda del todo. Son reemplazables por voces grabadas.
PH = {
    #      F1    F2    F3   amplitud
    "AA": (730, 1090, 2440, 1.0), "AE": (660, 1720, 2410, 1.0), "AH": (640, 1190, 2390, 1.0),
    "AO": (570, 840, 2410, 1.0), "UH": (440, 1020, 2240, 0.9), "UW": (300, 870, 2240, 0.85),
    "IY": (270, 2290, 3010, 0.8), "IH": (390, 1990, 2550, 0.9), "EH": (530, 1840, 2480, 1.0),
    "EY": (450, 2000, 2600, 0.9), "OW": (480, 850, 2400, 1.0),
    "R": (400, 1150, 1450, 0.6), "W": (300, 620, 2200, 0.5), "L": (360, 1000, 2700, 0.6),
    "N": (250, 1600, 2600, 0.35), "Y": (260, 2200, 2950, 0.5), "D": (280, 1600, 2600, 0.25),
}
FRIC = {  # consonantes de ruido: (banda baja, banda alta, ganancia, es oclusiva)
    "F": (1200, 8000, 0.45, False), "S": (4000, 8800, 0.5, False), "H": (400, 5000, 0.35, False),
    "T": (3000, 7500, 1.0, True), "K": (1200, 3200, 1.2, True), "D": (2500, 6000, 0.25, True),
}


def klatt_res(x, f_track, bw, blk=32):
    """Resonador de 2 polos con ganancia unitaria en DC y frecuencia variable."""
    n = len(x)
    out = np.zeros(n)
    y1 = y2 = 0.0
    for i0 in range(0, n, blk):
        f = f_track[i0] if hasattr(f_track, "__len__") else f_track
        C = -np.exp(-2 * np.pi * bw / SR)
        B = 2 * np.exp(-np.pi * bw / SR) * np.cos(2 * np.pi * f / SR)
        A = 1 - B - C
        o, _ = lfilter([A], [1, -B, -C], x[i0:i0 + blk], zi=np.array([B * y1 + C * y2, C * y1]))
        out[i0:i0 + blk] = o
        y1 = o[-1]
        y2 = o[-2] if len(o) > 1 else y1
    return out


def speak(segs, p0=140, p1=90):
    F = [[], [], []]
    AV = []
    marks = []
    last = (500, 1500, 2500)
    for ph, dur in segs:
        n = int(dur * SR)
        d = PH.get(ph)
        if d:
            last = d[:3]
        AV += [d[3] if d else 0.0] * n
        for i in range(3):
            F[i] += [last[i]] * n
        marks.append((ph, len(AV) - n, n))
    k = int(0.03 * SR)
    w = np.hanning(k); w /= w.sum()
    F = [np.convolve(np.array(f, float), w, "same") for f in F]
    k2 = int(0.012 * SR)
    w2 = np.hanning(k2); w2 /= w2.sum()
    AV = np.convolve(np.array(AV), w2, "same")
    n = len(AV)
    u = np.arange(n) / max(n - 1, 1)
    pitch = p0 + (p1 - p0) * u + 15 * np.sin(np.pi * np.clip(u * 2, 0, 1))
    ph = np.cumsum(pitch) / SR
    src = (1 - 2 * (ph % 1.0)) + 0.03 * rng.uniform(-1, 1, n)
    y = src * AV
    for j, bw in enumerate([80, 100, 160]):
        y = klatt_res(y, F[j], bw)
    for f, bw in [(3300, 250), (3900, 300)]:
        y = klatt_res(y, f, bw)
    y = np.diff(y, prepend=0)
    y /= np.max(np.abs(y)) + 1e-9
    nz = np.zeros(n)
    for phn, st, L in marks:
        if phn in FRIC:
            lo, hi, g, burst = FRIC[phn]
            s = bp(rng.uniform(-1, 1, L + 200), lo, hi)[200:]
            e = np.exp(-np.arange(L) / (0.3 * L + 1)) if burst else np.hanning(L) ** 0.3
            nz[st:st + L] += g * s * e / (np.max(np.abs(s)) + 1e-9)
    x = 0.9 * y + nz
    return x / (np.max(np.abs(x)) + 1e-9)


def stinger(kind, dur):
    """Colchón sintético debajo de cada voz."""
    t = t_axis(dur)
    if kind == "chord":      # quinta grave de "guitarra" con caída lenta
        x = sum(saw(2 * np.pi * f * t) for f in (82.4, 123.5, 164.8))
        return lp(x, 1800) * env_exp(dur, 0.35, attack=0.01) * 0.35
    if kind == "hit":        # golpe + platillo
        return mix(sweep_sine(dur, 160, 45, 0.04) * env_exp(dur, 0.15),
                   0.5 * hp(noise(dur), 4500) * env_exp(dur, 0.3))
    if kind == "boom":
        return mix(sweep_sine(dur, 120, 30, 0.08) * env_exp(dur, 0.4),
                   0.4 * lp(noise(dur), 900) * env_exp(dur, 0.2))
    return np.zeros(len(t))


def voice(segs, pitch, kind, stinger_gain=0.35):
    x = speak(segs, *pitch)
    x = np.tanh(1.8 * x)
    x = hp(x, 120)
    s = stinger(kind, len(x) / SR + 0.2)
    x = mix(x, stinger_gain * s)
    x = delay_mix(x, [(0.085, 0.3), (0.17, 0.16), (0.26, 0.08)])
    return finish(x, drive=1.3, peak=0.95, crush_bits=9)


def v(ph, ms):
    return (ph, ms / 1000.0)


_ROUND = [v("_", 30), v("R", 140), v("AA", 170), v("UW", 130), v("N", 120), v("_", 60), v("D", 40), v("_", 70)]
VOICES = {  # nombre: (fonemas, (tono inicial, tono final), stinger)
    "vo_round1": (_ROUND + [v("W", 120), v("AH", 260), v("N", 200), v("_", 40)], (140, 90), "chord"),
    "vo_round2": (_ROUND + [v("T", 100), v("H", 40), v("UW", 380), v("_", 40)], (140, 90), "chord"),
    "vo_final":  ([v("_", 30), v("F", 110), v("AA", 150), v("IY", 110), v("N", 70), v("AH", 80),
                   v("L", 110), v("_", 60)] + _ROUND[1:], (140, 90), "chord"),
    "vo_fight":  ([v("_", 30), v("F", 180), v("AA", 230), v("IH", 130), v("_", 80), v("T", 110),
                   v("_", 40)], (170, 110), "hit"),
    "vo_ko":     ([v("_", 30), v("K", 70), v("H", 50), v("EY", 220), v("IY", 120), v("W", 40),
                   v("OW", 260), v("UW", 180), v("_", 40)], (150, 85), "boom"),
    "vo_youwin": ([v("_", 30), v("Y", 100), v("UW", 250), v("_", 60), v("W", 120), v("IH", 220),
                   v("N", 200), v("_", 40)], (140, 95), "chord"),
}


# ----------------------------------------------------------- batería (música)
def drum_kick():
    d = 0.22
    body = sweep_sine(d, 190, 50, 0.025) * env_exp(d, 0.08)
    click = hp(noise(d), 3000) * env_exp(d, 0.004)
    return finish(mix(1.2 * body, 0.4 * click), drive=2.5, crush_bits=0)


def drum_snare():
    d = 0.2
    tone = sweep_sine(d, 260, 180, 0.02) * env_exp(d, 0.04)
    rattle = bp(noise(d), 1500, 7000) * env_exp(d, 0.07)
    return finish(mix(0.7 * tone, 1.0 * rattle), drive=2.0, crush_bits=0)


def drum_hat():
    d = 0.06
    return finish(hp(noise(d), 6000) * env_exp(d, 0.015), drive=1.2, crush_bits=0, peak=0.8)


def drum_openhat():
    d = 0.22
    return finish(hp(noise(d), 5500) * env_exp(d, 0.08), drive=1.2, crush_bits=0, peak=0.8)


def drum_crash():
    d = 0.8
    t = t_axis(d)
    metal = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f in (3120, 4470, 5930, 7010))
    x = hp(noise(d), 4000) + 0.2 * metal
    return finish(x * env_exp(d, 0.28), drive=1.3, crush_bits=0, peak=0.85)


def drum_tom():
    d = 0.25
    return finish(sweep_sine(d, 200, 100, 0.06) * env_exp(d, 0.1), drive=1.8, crush_bits=0)


def drum_guira():
    """'Chas' del cuarteto: güira/rasgueo corto de ruido medio-agudo."""
    d = 0.09
    x = bp(noise(d), 2500, 8000) * env_exp(d, 0.03, attack=0.006)
    return finish(x, drive=1.3, crush_bits=0, peak=0.75)


SFX = {
    "whoosh": sfx_whoosh, "hit": sfx_hit, "heavy": sfx_heavy, "block": sfx_block,
    "fireball": sfx_fireball, "ko": sfx_ko, "fbhit": sfx_fbhit, "land": sfx_land,
    "menu_move": sfx_menu_move, "menu_ok": sfx_menu_ok, "logo": sfx_logo, "fire": sfx_fire,
    "char_ok": sfx_char_ok,
}
DRUMS = {
    "kick": drum_kick, "snare": drum_snare, "hat": drum_hat, "openhat": drum_openhat,
    "crash": drum_crash, "tom": drum_tom, "guira": drum_guira,
}


def main():
    total = 0
    for name, fn in SFX.items():
        x = fn()
        write_wav(os.path.join(SFX_DIR, name + ".wav"), x)
        total += len(x)
    for name, (segs, pitch, kind) in VOICES.items():
        x = voice(segs, pitch, kind)
        write_wav(os.path.join(SFX_DIR, name + ".wav"), x)
        total += len(x)
    for name, fn in DRUMS.items():
        write_wav(os.path.join(DRUM_DIR, name + ".wav"), fn())
    # 2 muestras por byte en ADPCM
    print("sfx y voces: %.1f s de audio, ~%d KB en ADPCM-A" % (total / SR, total // 2 // 1024))


if __name__ == "__main__":
    sys.exit(main())
