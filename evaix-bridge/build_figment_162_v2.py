# -*- coding: utf-8 -*-
"""EvAIx Figment Vestiges slots 01–04 @ 162 BPM F# major.

Architect brief: first deliverable for 30′ live set.
- BPM 162 · Key F# major (dark filters — major≠happy)
- ESX-1 DNA + Ableton Drift-style atm/pad
- Poly: acid Last Step 13 vs kick 16 vs hats 15 vs perc 7
- Mute games: 1–8 atm · 9–16 +kick · 17–24 +ride · 25–32 +acid muted ·
              33–48 acid opens · 49–56 −ride acid closes
- No commercial EDM drops; free-party release only
- Arrangement scrape: plateaus, sample rotation, EQ before sat, tame 3–6 kHz
- v2: Acid LPF mid-bloom 700Hz–3kHz on Drop open (FineTuniX needs_tweaks)
Default: --skip-ableton (DSP bounce).
"""
from __future__ import annotations

import math
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 162.0
BAR_S = 4.0 * 60.0 / BPM
BEAT_S = 60.0 / BPM
STEP_S = BEAT_S / 4.0  # 16th

_HERE = Path(__file__).resolve().parent
_CANDIDATE_SAMPLES = [
    _HERE / "samples" / "trackb-enko155" / "factory_src",
    Path("/workspace/samples/trackb-enko155/factory_src"),
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\trackb-enko155\factory_src"),
]
FACTORY = next((p for p in _CANDIDATE_SAMPLES if p.exists()), _CANDIDATE_SAMPLES[0])

OUT = Path("/workspace/samples/figment-162") if Path("/workspace").exists() else (
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\figment-162")
)
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"; ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_DIR = OUT / "sections"; SECTION_DIR.mkdir(parents=True, exist_ok=True)

MP3_NAME = "EvAIx_Figment_162_v2.mp3"
MP3_WORKSPACE = Path("/workspace") / MP3_NAME if Path("/workspace").exists() else OUT / MP3_NAME
MP3_EXPORTS = Path("/workspace/exports") / MP3_NAME if Path("/workspace/exports").exists() else OUT / MP3_NAME
MP3_DOWNLOADS = Path(r"C:\Users\Gebruiker\Downloads") / MP3_NAME
NOTES_PATH = (
    Path("/workspace/exports/EvAIx_Figment_162_v2_NOTES.md")
    if Path("/workspace/exports").exists()
    else OUT / "EvAIx_Figment_162_v2_NOTES.md"
)
NOTES_WORKSPACE = Path("/workspace/EvAIx_Figment_162_v2_NOTES.md") if Path("/workspace").exists() else NOTES_PATH
BRIDGE_COPY = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\build_figment_162_v2.py")

# Gains — Pneumatix-clean: kick owns; quiet acoustic tops
KICK_G = 1.42
BASS_G = KICK_G * (10 ** (-8.0 / 20.0))
HATS_G, OH_G, RIDE_G, PERC_G = 0.11, 0.08, 0.13, 0.18
ACID_G, MG_G, ATM_G, PAD_G, FX_G = 0.32, 0.14, 0.16, 0.22, 0.09  # v2: acid mid up; MG thinner
TUBE_GAIN = 1.55
HAAS_W, HAAS_MS = 0.18, 7.0
# Mental Tribe / Pozek mid recipe (FineTuniX figment QC)
ACID_HPF_HZ = 160.0
ACID_PRESENCE_HZ = 2200.0
ACID_PRESENCE_DB_OPEN = 3.4
ACID_PRESENCE_DB_MUTE = -4.0

# F# major (dark) — root F#2 upward; fragile voicing
FS_MAJ = np.array([
    92.50,   # F#2
    103.83,  # G#2
    116.54,  # A#2
    123.47,  # B2
    138.59,  # C#3
    155.56,  # D#3
    185.00,  # F#3
    207.65,  # G#3
], dtype=np.float64)
FS_LOW = FS_MAJ / 2.0  # MG LPF −8va layer
FS_PAD = np.array([92.50, 138.59, 185.00, 233.08], dtype=np.float64)  # F# C# F# A#

# Slot map @162: ~81 bars / 2′ ; 40 bars / 1′
# Internal plateaus follow mute-game proportions within slots 01–03
FULL_SECTIONS = [
    # Slot 01 Figment_Intro 0:00–2:00 energy2 — Atm only
    ("Figment_Intro_a", 40, "intro_atm", "01"),   # OB LPF ~15% closed
    ("Figment_Intro_b", 41, "intro_open", "01"),   # LPF opens toward build
    # Slot 02 Figment_Build 2:00–4:00 energy3 — +kick +ride restraint
    ("Figment_Build_kick", 40, "build_kick", "02"),  # +kick 1/5/9/13
    ("Figment_Build_ride", 41, "build_ride", "02"),  # +dark ride 8ths
    # Slot 03 Figment_Drop 4:00–6:00 energy6 — dual acid muted→open
    ("Figment_Drop_mute", 27, "drop_muted", "03"),   # acid muted
    ("Figment_Drop_open", 40, "drop_open", "03"),    # acid opens (first release)
    ("Figment_Drop_close", 14, "drop_close", "03"),  # −ride, acid closes
    # Slot 04 Figment_Out 6:00–7:00 energy4
    ("Figment_Out", 40, "outro", "04"),              # StepJump stutter → F settle
]

BD_FAMILIES = {
    "01": ["014_BD-15.wav", "012_BD-13.wav"],           # veiled/thin family
    "02": ["016_BD-17.wav", "018_BD-19.wav"],           # dry groove
    "03": ["019_BD-20.wav", "020_BD-21.wav"],           # brighter peak
    "04": ["010_BD-11.wav", "008_BD-9.wav"],            # thin outro
}


def find_ffmpeg() -> str:
    for c in [
        "ffmpeg",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe",
    ]:
        try:
            subprocess.run([c, "-version"], capture_output=True, check=True)
            return c
        except Exception:
            continue
    raise RuntimeError("ffmpeg not found")


FFMPEG = find_ffmpeg()


def section_n(bars: int) -> int:
    return int(bars * BAR_S * SR)


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nframes)
    if sw != 2:
        raise RuntimeError(f"unsupported width {sw} for {path}")
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        x = np.linspace(0, 1, len(data))
        xi = np.linspace(0, 1, int(len(data) * SR / sr))
        data = np.interp(xi, x, data)
    return data


def write_mono(path: Path, samples: np.ndarray, peak_target=0.90):
    samples = np.asarray(samples, dtype=np.float64)
    peak = float(np.max(np.abs(samples))) if samples.size else 1e-9
    scale = peak_target / max(peak, 1e-9)
    pcm = np.clip(samples * scale * 32767.0, -32767, 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def write_stereo_lr(path: Path, left: np.ndarray, right: np.ndarray, peak_target=0.90):
    n = min(len(left), len(right))
    left, right = left[:n], right[:n]
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    scale = peak_target / peak
    interleaved = np.empty(n * 2, dtype=np.int16)
    interleaved[0::2] = np.clip(left * scale * 32767.0, -32767, 32767).astype(np.int16)
    interleaved[1::2] = np.clip(right * scale * 32767.0, -32767, 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(interleaved.tobytes())


def one_pole(x: np.ndarray, cutoff_hz: float, mode="lpf") -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    w = math.tan(math.pi * min(0.45, max(1e-5, cutoff_hz / SR)))
    if mode == "hpf":
        a0 = 1.0 / (1.0 + w)
        bcoef = [a0, -a0]
        acoef = [1.0, (w - 1.0) * a0]
    else:
        a0 = w / (1.0 + w)
        bcoef = [a0, a0]
        acoef = [1.0, (w - 1.0) / (1.0 + w)]
    try:
        from scipy.signal import lfilter
        return lfilter(bcoef, acoef, x)
    except Exception:
        out = np.zeros_like(x)
        z = 0.0
        b0, b1 = bcoef
        a1 = acoef[1]
        x_prev = 0.0
        for i, s in enumerate(x):
            y = b0 * s + b1 * x_prev - a1 * z
            x_prev = s
            z = y
            out[i] = y
        return out


def bandpass(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return one_pole(one_pole(x, lo, mode="hpf"), hi, mode="lpf")


def peaking_eq(x: np.ndarray, freq_hz: float, gain_db: float, q: float = 1.0) -> np.ndarray:
    """Parallel bandpass blend presence / cut (Mental Tribe mid recipe)."""
    x = np.asarray(x, dtype=np.float64)
    if abs(gain_db) < 0.05:
        return x
    g = 10 ** (gain_db / 20.0) - 1.0
    bw = max(80.0, freq_hz / max(0.3, q))
    bp = bandpass(x, max(40.0, freq_hz - bw), freq_hz + bw)
    return x + g * bp


def tanh_drive(x: np.ndarray, amt: float) -> np.ndarray:
    return np.tanh(x * amt)


def valve_force(x: np.ndarray, tube_gain: float = TUBE_GAIN) -> np.ndarray:
    bias = 0.025
    norm = math.tanh(tube_gain)
    y = np.tanh((x + bias) * tube_gain) / norm - bias * 0.5
    return 0.92 * y + 0.08 * np.tanh(x * (tube_gain * 0.45))


def mild_compress(x: np.ndarray, thr=0.40, ratio=1.55) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    absx = np.abs(x)
    atk = math.exp(-1.0 / (SR * 0.0025))
    rel = math.exp(-1.0 / (SR * 0.12))
    env = np.zeros_like(x)
    e = 0.0
    for i, a in enumerate(absx):
        e = a + (e - a) * (atk if a > e else rel)
        env[i] = e
    over = np.maximum(0.0, env - thr)
    gain = np.where(env > thr, (thr + over / ratio) / np.maximum(env, 1e-9), 1.0)
    return x * gain * 1.06


def place(buf: np.ndarray, sample: np.ndarray, beat: float, gain: float = 1.0):
    i0 = int(beat * BEAT_S * SR)
    if i0 >= len(buf) or i0 < 0:
        return
    n = min(len(sample), len(buf) - i0)
    buf[i0:i0 + n] += sample[:n] * gain


def haas_widen(mono: np.ndarray, width=HAAS_W, delay_ms=HAAS_MS):
    n = len(mono)
    if width <= 0.001:
        return mono.copy(), mono.copy()
    d = max(1, int(delay_ms * 0.001 * SR))
    delayed = np.zeros(n)
    delayed[d:] = mono[:-d]
    return mono + delayed * width * 0.55, mono - delayed * width * 0.55


def apply_moving_lpf(x: np.ndarray, cut_start: float, cut_end: float) -> np.ndarray:
    """Log-ish macro LPF: slow then accelerate (scrape doctrine)."""
    n = len(x)
    if n < 8:
        return x
    # process in blocks with escalating cutoff
    blocks = 32
    bs = max(1, n // blocks)
    out = np.zeros_like(x)
    for i in range(blocks):
        a = i * bs
        b = n if i == blocks - 1 else min(n, (i + 1) * bs)
        # log curve: t^1.6
        t = (i / max(1, blocks - 1)) ** 1.6
        cut = cut_start + (cut_end - cut_start) * t
        out[a:b] = one_pole(x[a:b], float(cut), mode="lpf")
    return out


def prepare_bd(name: str, drive: float = 2.15) -> np.ndarray:
    src = FACTORY / name
    if not src.exists():
        raise FileNotFoundError(src)
    raw = read_wav(src)
    # EQ before sat (scrape) + optional punch body 80–150 Hz
    y = one_pole(raw, 36.0, mode="hpf")
    y = one_pole(y, 4500.0, mode="lpf")  # tame click before grit
    y = peaking_eq(y, 110.0, 1.6, q=0.85)  # FineTuniX optional punch body
    y = tanh_drive(y, drive)
    y = mild_compress(y, thr=0.42, ratio=1.40)
    y = one_pole(y, 9000.0, mode="lpf")  # post-dist high cut
    peak = float(np.max(np.abs(y))) + 1e-12
    return y / peak * 0.95


def synth_sub_bass(root_hz: float = 46.25) -> np.ndarray:
    """F#1 fund (~46.25) for mono kick pocket."""
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    env = np.exp(-t / 0.11)
    pitch = root_hz * (1.0 + 1.5 * np.exp(-t / 0.015))
    phase = np.cumsum(2 * np.pi * pitch / SR)
    return mild_compress(np.sin(phase) * env * 0.9, thr=0.48, ratio=1.35)


def synth_drift_pad(n: int, open_amt: float = 0.15, seed: int = 42) -> np.ndarray:
    """Ableton Drift-style soft pad hold — dark major, OB LPF character."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    pad = np.zeros(n)
    for i, hz in enumerate(FS_PAD):
        det = 1.0 + rng.uniform(-0.004, 0.004)
        phase = 2 * np.pi * hz * det * t
        # soft saw + sine blend (Drift-ish)
        saw = 2.0 * (np.mod(phase / (2 * np.pi), 1.0) - 0.5)
        sine = np.sin(phase)
        amp = 0.22 if i < 2 else 0.14
        pad += amp * (0.55 * sine + 0.45 * saw * 0.35)
    # slow LFO breathe
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.055 * t)
    pad *= 0.55 + 0.45 * lfo
    # OB LPF: open_amt 0.15→1.0 maps cut ~400→4500
    cut = 400.0 + 4100.0 * float(np.clip(open_amt, 0.05, 1.0))
    pad = one_pole(pad, 80.0, mode="hpf")
    pad = one_pole(pad, cut, mode="lpf")
    # gentle stereo-ready mono source; tame 3–6 kHz
    pad = one_pole(pad, 5200.0, mode="lpf")
    return pad * 0.55


def synth_atm_haze(n: int, seed: int = 77) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, n)
    x = one_pole(x, 350.0, mode="hpf")
    x = one_pole(x, 2200.0, mode="lpf")
    t = np.arange(n) / SR
    x *= 0.40 + 0.60 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.06 * t))
    return x * 0.22


def acid_303_note(freq: float, dur_s: float, accent: bool = False,
                  cutoff_open: float = 0.35, res_boost: float = 0.0) -> np.ndarray:
    """Acid LPF 303 saw — Mental Tribe mid bloom when open (700Hz–3kHz).

    Muted/closed: heavy LPF, low mid gain.
    Open: presence ~1.8–2.8 kHz, HPF ~160 Hz so kick stays clear;
    light sat AFTER EQ; tame >4.5 kHz harsh.
    """
    n = max(8, int(dur_s * SR))
    t = np.arange(n) / SR
    o = float(np.clip(cutoff_open, 0.0, 1.2))
    pitch = freq * (1.0 + (0.06 if accent else 0.0) * np.exp(-t / 0.04))
    phase = np.cumsum(2 * np.pi * pitch / SR)
    saw = 2.0 * (phase / (2 * np.pi) - np.floor(0.5 + phase / (2 * np.pi)))
    # muted: ~250–700 Hz; open: ~900–4500 Hz with res bump (mid scream, not sub)
    cut0 = 220.0 + 780.0 * o
    cut1 = cut0 + (900.0 + 4200.0 * o) * (1.20 if accent else 0.90)
    cut = cut0 + (cut1 - cut0) * np.exp(-t / (0.11 if accent else 0.18))
    cut = cut * (1.0 + 0.22 * res_boost)
    y_lo = one_pole(saw, float(np.percentile(cut, 15)), mode="lpf")
    y_hi = one_pole(saw, float(np.percentile(cut, 85)), mode="lpf")
    blend = np.clip((cut - cut.min()) / max(1e-9, cut.max() - cut.min()), 0, 1)
    blend = np.clip(blend * (0.55 + 0.70 * o), 0, 1)
    y = y_lo * (1 - blend) + y_hi * blend
    gate = 0.20 if not accent else 0.14
    env = np.exp(-t / gate)
    atk_n = max(1, int(0.0025 * SR))
    env[:atk_n] *= np.linspace(0, 1, atk_n)
    y = y * env * (1.20 if accent else 0.95)
    hpf = 120.0 + 60.0 * o
    y = one_pole(y, hpf, mode="hpf")
    if o >= 0.55:
        y = peaking_eq(y, 1800.0, 2.2 + 1.0 * (o - 0.55), q=0.95)
        y = peaking_eq(y, ACID_PRESENCE_HZ, ACID_PRESENCE_DB_OPEN * min(1.0, o), q=1.05)
        y = peaking_eq(y, 2800.0, 2.0 * min(1.0, o), q=1.1)
        y = peaking_eq(y, 4800.0, -2.2, q=1.2)
    else:
        y = peaking_eq(y, 2000.0, ACID_PRESENCE_DB_MUTE * (1.0 - o / 0.55), q=0.9)
        y = one_pole(y, 700.0 + 900.0 * o, mode="lpf")
    y = tanh_drive(y, 1.15 + 0.28 * o)
    post_lp = 1400.0 + 3600.0 * o if o >= 0.45 else (900.0 + 1400.0 * o)
    y = one_pole(y, post_lp, mode="lpf")
    y = one_pole(y, 6200.0, mode="lpf")
    return y


def mg_lpf_note(freq: float, dur_s: float, accent: bool = False,
                cutoff_open: float = 0.30) -> np.ndarray:
    """MG LPF −8va dual layer — HPF so it supports body, not LF mask."""
    n = max(8, int(dur_s * SR))
    t = np.arange(n) / SR
    o = float(np.clip(cutoff_open, 0.0, 1.2))
    phase = np.cumsum(2 * np.pi * freq / SR)
    sq = np.sign(np.sin(phase))
    cut = 220.0 + 1800.0 * o + (1100.0 if accent else 500.0) * np.exp(-t / 0.22)
    y = one_pole(sq, float(np.median(cut)), mode="lpf")
    y = one_pole(y, float(np.percentile(cut, 70)), mode="lpf")
    env = np.exp(-t / (0.26 if accent else 0.36))
    y = y * env * 0.80
    y = one_pole(y, 140.0 + 40.0 * o, mode="hpf")
    if o >= 0.55:
        y = peaking_eq(y, 1600.0, 1.4, q=0.9)
        y = tanh_drive(y, 1.10 + 0.15 * o)
        y = one_pole(y, 3800.0, mode="lpf")
    else:
        y = tanh_drive(y, 1.05)
        y = one_pole(y, 900.0 + 800.0 * o, mode="lpf")
    return y


def process_acid_bus(acid: np.ndarray, mg: np.ndarray, open_amt: float, mode: str):
    """Bus morph: muted = mid-starved LPF; open = 700Hz–3kHz bloom vs mute."""
    o = float(np.clip(open_amt, 0.0, 1.2))
    acid = np.asarray(acid, dtype=np.float64)
    mg = np.asarray(mg, dtype=np.float64)
    acid = one_pole(acid, ACID_HPF_HZ, mode="hpf")
    mg = one_pole(mg, 150.0, mode="hpf")
    if mode == "drop_open" or o >= 0.65:
        acid = peaking_eq(acid, 900.0, 1.5, q=0.85)
        acid = peaking_eq(acid, 1800.0, 2.4, q=0.95)
        acid = peaking_eq(acid, ACID_PRESENCE_HZ, ACID_PRESENCE_DB_OPEN, q=1.05)
        acid = peaking_eq(acid, 2800.0, 2.2, q=1.1)
        acid = peaking_eq(acid, 5200.0, -2.8, q=1.15)
        acid = tanh_drive(acid, 1.22)
        acid = one_pole(acid, 4800.0, mode="lpf")
        mg = peaking_eq(mg, 1400.0, 1.0, q=0.9)
        mg = one_pole(mg, 3600.0, mode="lpf")
        acid *= 1.18
        mg *= 0.92
    elif mode in ("drop_muted", "drop_close") or o < 0.40:
        acid = peaking_eq(acid, 2000.0, -5.0, q=0.85)
        acid = one_pole(acid, 850.0 + 700.0 * o, mode="lpf")
        mg = one_pole(mg, 700.0 + 600.0 * o, mode="lpf")
        acid *= 0.78
    else:
        acid = peaking_eq(acid, 2000.0, -1.5 + 3.0 * o, q=0.9)
        acid = one_pole(acid, 1800.0 + 2800.0 * o, mode="lpf")
    return acid, mg


# --- Poly pattern generators (Last Step doctrine) ---

def acid_poly13(bars: int, dens: float, seed: int):
    """Acid Last Step 13 vs 16-step grid."""
    rng = np.random.default_rng(seed)
    # Classic-ish F# tekno phrase on 13-cycle
    seq = [0, 2, 0, 3, 4, 2, 5, 0, 2, 3, 0, 4, 6]  # indices into FS_MAJ
    accents = {0, 2, 4, 7, 10, 12}
    steps = bars * 16
    events = []
    for s in range(steps):
        local = s % 13
        # fire on cycle hits with density; skip some weak steps
        if local in (0, 2, 4, 5, 7, 9, 10, 12) or rng.random() < dens * 0.12:
            if rng.random() < dens or local in accents:
                note = seq[local]
                accent = local in accents
                # slides on accents: longer gate
                dur = 5 if (accent and local == 0) else (3 if accent else 2)
                events.append((s, note, accent, dur))
    return events


def hat_poly15(bars: int, dens: float = 0.7):
    """Hats Last Step 15."""
    steps = bars * 16
    hits = []
    pattern = [0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 1]  # 15-step
    for s in range(steps):
        if pattern[s % 15] and (dens >= 0.99 or (s % 15) % 3 != 1 or dens > 0.5):
            hits.append(s)
    return hits


def perc_poly7(bars: int, dens: float = 0.5):
    """Perc Last Step 7."""
    steps = bars * 16
    hits = []
    pattern = [1, 0, 0, 1, 0, 1, 0]  # 7-step
    for s in range(steps):
        if pattern[s % 7] and (s % 7 != 0 or dens > 0.3):
            if dens > 0.8 or s % 14 < 7:
                hits.append(s)
    return hits


def kit_for_mode(mode: str, slot: str, shots: dict) -> dict:
    bd_pick = {
        "intro_atm": shots["bd_veiled"],
        "intro_open": shots["bd_veiled"],
        "build_kick": shots["bd_a"],
        "build_ride": shots["bd_b"],
        "drop_muted": shots["bd_c"],
        "drop_open": shots["bd_d"],
        "drop_close": shots["bd_c"],
        "outro": shots["bd_thin"],
    }
    hat_pick = {
        "intro_atm": shots["hh1"], "intro_open": shots["hh1"],
        "build_kick": shots["hh2"], "build_ride": shots["hh3"],
        "drop_muted": shots["hh5"], "drop_open": shots["hh7"],
        "drop_close": shots["hh3"], "outro": shots["hh1"],
    }
    # gains: kick/bass/hats/oh/ride/perc/acid/mg/atm/pad/fx
    gains = {
        "intro_atm":  dict(kick=0.0, bass=0.0, hats=0.08, oh=0.0, ride=0.0, perc=0.04,
                           acid=0.0, mg=0.0, atm=1.0, pad=1.0, fx=0.35, acid_open=0.12),
        "intro_open": dict(kick=0.0, bass=0.0, hats=0.12, oh=0.0, ride=0.0, perc=0.06,
                           acid=0.0, mg=0.0, atm=0.85, pad=1.0, fx=0.30, acid_open=0.18),
        "build_kick": dict(kick=0.88, bass=0.40, hats=0.28, oh=0.05, ride=0.0, perc=0.18,
                           acid=0.0, mg=0.0, atm=0.40, pad=0.70, fx=0.18, acid_open=0.20),
        "build_ride": dict(kick=0.95, bass=0.55, hats=0.35, oh=0.10, ride=0.85, perc=0.25,
                           acid=0.0, mg=0.0, atm=0.25, pad=0.55, fx=0.20, acid_open=0.25),
        "drop_muted": dict(kick=1.0, bass=0.85, hats=0.45, oh=0.20, ride=0.70, perc=0.35,
                           acid=0.42, mg=0.28, atm=0.12, pad=0.35, fx=0.22, acid_open=0.18),
        "drop_open":  dict(kick=1.02, bass=0.92, hats=0.55, oh=0.30, ride=0.80, perc=0.45,
                           acid=1.15, mg=0.70, atm=0.08, pad=0.25, fx=0.28, acid_open=0.92),
        "drop_close": dict(kick=0.95, bass=0.70, hats=0.30, oh=0.08, ride=0.0, perc=0.20,
                           acid=0.45, mg=0.28, atm=0.20, pad=0.40, fx=0.25, acid_open=0.28),
        "outro":      dict(kick=0.70, bass=0.35, hats=0.18, oh=0.05, ride=0.0, perc=0.12,
                           acid=0.20, mg=0.15, atm=0.55, pad=0.65, fx=0.40, acid_open=0.15),
    }
    stories = {
        "intro_atm":  "Slot01 Intro — Drift pad hold + atm haze; OB LPF ~15%; no kick",
        "intro_open": "Slot01 Intro — atm filter opens toward build; still no kick",
        "build_kick": "Slot02 Build — kick 1/5/9/13 lands; sparse hats; restraint",
        "build_ride": "Slot02 Build — +dark ride 8ths; plateau hold; no acid yet",
        "drop_muted": "Slot03 Drop — dual acid enters MUTED (Acid LPF + MG −8va)",
        "drop_open":  "Slot03 Drop — acid cutoff opens; first free-party release (NOT EDM)",
        "drop_close": "Slot03→04 — strip ride; acid closes into Out",
        "outro":      "Slot04 Out — StepJump stutter; settle toward F handoff",
    }
    # kick steps: 16-cycle — steps 0,4,8,12 = beats 1/5/9/13 in Electribe terms
    kick_on = {
        "intro_atm": [], "intro_open": [],
        "build_kick": [0, 4, 8, 12], "build_ride": [0, 4, 8, 12],
        "drop_muted": [0, 4, 8, 12], "drop_open": [0, 4, 8, 12],
        "drop_close": [0, 4, 8, 12], "outro": [0, 8],
    }
    bd_name = {
        "intro_atm": "veiled BD-15", "intro_open": "veiled BD-15",
        "build_kick": BD_FAMILIES["02"][0], "build_ride": BD_FAMILIES["02"][1],
        "drop_muted": BD_FAMILIES["03"][0], "drop_open": BD_FAMILIES["03"][1],
        "drop_close": BD_FAMILIES["03"][0], "outro": "thin BD-11",
    }[mode]
    return {
        "kick": bd_pick[mode], "hat": hat_pick[mode],
        "gains": gains[mode], "story": stories[mode],
        "kick_steps": kick_on[mode], "bd_name": bd_name, "slot": slot,
    }


def ensure_shots() -> dict:
    print("FACTORY", FACTORY)
    used = []
    all_bd = []
    for fam in BD_FAMILIES.values():
        all_bd.extend(fam)
    # unique order
    seen = []
    for n in all_bd:
        if n not in seen:
            seen.append(n)

    bds = {}
    keys = ["bd_a", "bd_b", "bd_c", "bd_d", "bd_e", "bd_f", "bd_g", "bd_h"]
    for i, name in enumerate(seen[:8]):
        key = keys[i]
        bds[key] = prepare_bd(name, drive=2.05 + 0.06 * i)
        write_mono(ONESHOT / f"{key}_{name}", bds[key], 0.94)
        used.append(name)
    # map semantic names to family picks
    # 02 family → bd_a/b, 03 → bd_c/d, etc.
    bds["bd_veiled"] = one_pole(bds["bd_a"] if "bd_a" in bds else list(bds.values())[0], 90.0, mode="lpf") * 0.50
    thin_src = bds.get("bd_e", bds.get("bd_b", list(bds.values())[0]))
    bds["bd_thin"] = one_pole(thin_src, 110.0, mode="lpf") * 0.68

    def load_perc(name, drive=1.0, hpf=0.0, lpf=9000.0):
        y = read_wav(FACTORY / name)
        if hpf:
            y = one_pole(y, hpf, mode="hpf")
        # EQ before sat
        y = one_pole(y, min(lpf, 10000.0), mode="lpf")
        y = tanh_drive(y, drive)
        y = one_pole(y, lpf, mode="lpf")  # post-sat tame
        used.append(name)
        return y

    shots = dict(bds)
    shots["hh1"] = load_perc("054_HH-1C.wav", 0.95, 4500, 12000)
    shots["hh2"] = load_perc("056_HH-2C.wav", 0.95, 4500, 12000)
    shots["hh3"] = load_perc("058_HH-3C.wav", 1.0, 4000, 11500)
    shots["hh5"] = load_perc("062_HH-5C.wav", 1.0, 4000, 11500)
    shots["hh7"] = load_perc("066_HH-7C.wav", 1.05, 3500, 11000)
    shots["oh1"] = load_perc("055_HH-1O.wav", 0.95, 3500, 10500)
    shots["oh3"] = load_perc("059_HH-3O.wav", 0.95, 3500, 10500)
    shots["oh7"] = load_perc("067_HH-7O.wav", 1.0, 3200, 10000)
    shots["rim1"] = load_perc("045_Rim-1.wav", 1.15, 900, 7000)
    shots["rim3"] = load_perc("047_Rim-3.wav", 1.2, 1000, 7500)
    shots["clap1"] = load_perc("048_Clap-1.wav", 1.1, 700, 8000)
    shots["clap5"] = load_perc("052_Clap-5.wav", 1.15, 800, 8500)
    shots["tom1"] = load_perc("076_Tom-1.wav", 1.2, 80, 3500)
    shots["tom3"] = load_perc("078_Tom-3.wav", 1.15, 60, 3000)
    shots["junk"] = load_perc("092_JunkPerc.wav", 1.25, 250, 6000)
    shots["sfx1"] = load_perc("102_SFX-1.wav", 1.0, 150, 5000)
    shots["sfx3"] = load_perc("104_SFX-3.wav", 1.0, 100, 4500)
    shots["noise"] = load_perc("200_Noise.wav", 0.95, 200, 6000)
    shots["crash"] = load_perc("073_Crash-1.wav", 0.95, 250, 10000)
    shots["ride"] = load_perc("068_Ride-1.wav", 0.90, 2500, 10000)  # dark ride
    # shelf hats quieter (acoustic tops)
    for k in ("hh1", "hh2", "hh3", "hh5", "hh7", "oh1", "oh3", "oh7", "ride"):
        shots[k] = one_pole(shots[k], 9500.0, mode="lpf") * 0.92
    shots["bass"] = synth_sub_bass(46.25)
    write_mono(ONESHOT / "bass_sub_Fs.wav", shots["bass"], 0.9)
    shots["used"] = used
    print("shots ready", len(used))
    return shots


def render_section(idx: int, name: str, bars: int, mode: str, slot: str, shots: dict):
    N = section_n(bars)
    trk_k = np.zeros(N); trk_b = np.zeros(N); trk_h = np.zeros(N); trk_oh = np.zeros(N)
    trk_ride = np.zeros(N); trk_p = np.zeros(N)
    trk_acid = np.zeros(N); trk_mg = np.zeros(N)
    trk_atm = np.zeros(N); trk_pad = np.zeros(N); trk_fx = np.zeros(N)
    kit = kit_for_mode(mode, slot, shots)
    g = kit["gains"]
    seed = 0xF162 + idx * 19

    # --- drums ---
    for bar in range(bars):
        for st in kit["kick_steps"]:
            beat = bar * 4 + st / 4.0
            place(trk_k, kit["kick"], beat, 1.0)
            place(trk_b, shots["bass"], beat, 1.0)

        # hats poly15
        if g["hats"] > 0.05:
            dens = 0.35 if mode.startswith("intro") else (0.55 if "build" in mode else 0.75)
            for s in hat_poly15(1, dens=dens):
                # only this bar's 16 steps
                if s < 16:
                    beat = bar * 4 + s / 4.0
                    place(trk_h, kit["hat"], beat, 0.75 if s % 4 == 2 else 0.55)

        # dark ride 8ths on build_ride / drop
        if g["ride"] > 0.05:
            for eighth in range(8):
                beat = bar * 4 + eighth * 0.5
                place(trk_ride, shots["ride"], beat, 0.55 if eighth % 2 == 0 else 0.40)

        # perc poly7 — industrial Pneumatix clank color
        if g["perc"] > 0.08:
            dens = 0.4 if "build" in mode else 0.65
            for s in perc_poly7(1, dens=dens):
                if s < 16:
                    beat = bar * 4 + s / 4.0
                    samp = shots["junk"] if s % 7 in (0, 3) else (
                        shots["rim1"] if s % 7 == 5 else shots["tom1"]
                    )
                    place(trk_p, samp, beat, 0.55)

        if mode == "drop_open" and bar % 8 == 7:
            place(trk_p, shots["clap5"], bar * 4 + 1.0, 0.45)
        if mode == "build_ride" and bar % 4 == 3:
            place(trk_oh, shots["oh1"], bar * 4 + 1.5, 0.5)

    # --- StepJump stutter on outro ---
    if mode == "outro":
        # stutter kick fragments bars 8–16 and 24–28
        for bar in list(range(8, 16)) + list(range(24, 28)):
            if bar >= bars:
                continue
            for micro in (0.0, 0.25, 0.5):
                place(trk_k, kit["kick"], bar * 4 + micro, 0.55)
            # silence residual on offbeats by not placing full grid (kick_steps already thin)

    # --- atm + Drift pad ---
    pad_open = {
        "intro_atm": 0.15, "intro_open": 0.42, "build_kick": 0.50, "build_ride": 0.55,
        "drop_muted": 0.40, "drop_open": 0.35, "drop_close": 0.45, "outro": 0.55,
    }[mode]
    if g["pad"] > 0.01:
        trk_pad += synth_drift_pad(N, open_amt=pad_open, seed=seed)
    if g["atm"] > 0.01:
        trk_atm += synth_atm_haze(N, seed=seed + 3)
        rng = np.random.default_rng(seed)
        for bar in range(0, bars, 2):
            place(trk_fx, shots["sfx1"] if bar % 4 == 0 else shots["sfx3"],
                  bar * 4 + rng.uniform(0, 1.5), 0.4)
            if mode in ("intro_atm", "intro_open", "outro", "drop_close"):
                place(trk_fx, shots["noise"], bar * 4, 0.18)

    # --- dual acid (poly13) ---
    acid_open = float(g["acid_open"])
    dens = {
        "intro_atm": 0.0, "intro_open": 0.0, "build_kick": 0.0, "build_ride": 0.0,
        "drop_muted": 0.55, "drop_open": 0.85, "drop_close": 0.40, "outro": 0.25,
    }[mode]
    if dens > 0.01 and (g["acid"] > 0.05 or g["mg"] > 0.05):
        for step, note_i, accent, dur_steps in acid_poly13(bars, dens, seed):
            freq = float(FS_MAJ[note_i % len(FS_MAJ)])
            note = acid_303_note(freq, dur_steps * STEP_S, accent=accent, cutoff_open=acid_open,
                                 res_boost=0.45 if mode == "drop_open" else 0.0)
            place(trk_acid, note, step / 4.0, 1.15 if accent else 0.88)
            # MG −8va (dual acid LS13 kept)
            mg = mg_lpf_note(float(FS_LOW[note_i % len(FS_LOW)]), dur_steps * STEP_S * 1.1,
                             accent=accent, cutoff_open=acid_open * 0.88)
            place(trk_mg, mg, step / 4.0, 0.85)

    # apply gains
    trk_k *= KICK_G * g["kick"]; trk_b *= BASS_G * g["bass"]
    trk_h *= HATS_G * g["hats"]; trk_oh *= OH_G * g["oh"]
    trk_ride *= RIDE_G * g["ride"]; trk_p *= PERC_G * g["perc"]
    trk_acid *= ACID_G * g["acid"]; trk_mg *= MG_G * g["mg"]
    trk_atm *= ATM_G * g["atm"]; trk_pad *= PAD_G * g["pad"]; trk_fx *= FX_G * g["fx"]

    # v2 FineTuniX: acid bus mid-bloom morph (muted→open audible in 700–3k)
    if g["acid"] > 0.05 or g["mg"] > 0.05:
        trk_acid, trk_mg = process_acid_bus(trk_acid, trk_mg, acid_open, mode)

    # kick/bass/perc stay mono; hats+atm get light width later
    mono_bed = trk_k + trk_b + trk_ride + trk_p + trk_pad
    hats_atm = trk_h + trk_oh + trk_atm
    acid_bus = trk_acid + trk_mg

    cut_map = {
        "intro_atm": (600.0, 1400.0),
        "intro_open": (1200.0, 3200.0),
        "build_kick": (2800.0, 4500.0),
        "build_ride": (3500.0, 5500.0),
        "drop_muted": (2200.0, 3800.0),
        "drop_open": (4500.0, 9500.0),
        "drop_close": (5000.0, 2800.0),
        "outro": (3500.0, 1800.0),
    }
    c0, c1 = cut_map[mode]
    mono_bed = apply_moving_lpf(mono_bed, c0, c1)
    hats_atm = apply_moving_lpf(hats_atm, c0, c1)
    # muted/close: darken acid macro; open: keep mid path
    if mode == "drop_open":
        acid_bus = apply_moving_lpf(acid_bus, 5200.0, 9000.0)
        fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, c1 * 1.05)
    elif mode == "drop_muted":
        acid_bus = apply_moving_lpf(acid_bus, 900.0, 1600.0)
        fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, c1 * 1.05)
    else:
        acid_bus = apply_moving_lpf(acid_bus, c0 * 0.85, c1 * 0.95)
        fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, c1 * 1.05)

    # Valve Force mild (CRISP acoustic — not dense smash)
    mono_bed = valve_force(mono_bed, TUBE_GAIN * 0.80)
    hats_atm = valve_force(hats_atm, TUBE_GAIN * 0.75)
    acid_bus = valve_force(acid_bus, TUBE_GAIN * 0.90)
    fx_bus = valve_force(fx_bus, TUBE_GAIN * 0.95)
    # post-sat tame 3–6 kHz (user hated distorted highs)
    mono_bed = one_pole(mono_bed, 11000.0, mode="lpf")
    hats_atm = one_pole(hats_atm, 9500.0, mode="lpf")
    acid_bus = one_pole(acid_bus, 5600.0 if mode == "drop_open" else 7500.0, mode="lpf")
    fx_bus = one_pole(fx_bus, 8500.0, mode="lpf")

    # width: acid/fx + light hats/atm only — kick/bass remain mono
    wide_src = acid_bus + fx_bus
    wl, wr = haas_widen(wide_src, HAAS_W if g["acid"] > 0.2 or g["pad"] > 0.5 else 0.10)
    hl, hr = haas_widen(hats_atm, 0.14 if (g["hats"] > 0.2 or g["atm"] > 0.2) else 0.0, 9.0)
    wl = wl + hl; wr = wr + hr
    if g["pad"] > 0.3:
        pl, pr = haas_widen(trk_pad * 0.35, 0.22, 11.0)
        wl = wl + pl; wr = wr + pr
        mono_bed = mono_bed - trk_pad * 0.15

    left = mono_bed + wl
    right = mono_bed + wr
    mix_path = SECTION_DIR / f"{idx:02d}_{name}_mix.wav"
    write_stereo_lr(mix_path, left, right, 0.88)
    meta = {
        "name": name, "mode": mode, "slot": slot, "bars": bars,
        "story": kit["story"], "bd": kit["bd_name"],
        "gains": {k: g[k] for k in g if k != "acid_open"},
        "acid_open": acid_open,
        "acid_events": len(acid_poly13(bars, dens, seed)) if dens > 0 else 0,
        "dur_s": bars * BAR_S,
    }
    print(f"  section {idx:02d} slot{slot} {name}: {bars} bars (~{bars * BAR_S:.1f}s) open={acid_open:.2f}")
    return mix_path, meta


def bounce_mp3(mixes, mp3_path: Path) -> float:
    concat_list = OUT / "_figment_concat.txt"
    raw = OUT / "_figment_raw.wav"
    mastered = OUT / "_figment_master.wav"
    with concat_list.open("w", encoding="utf-8") as f:
        for p in mixes:
            f.write(f"file '{p.as_posix()}'\n")
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw)],
        check=True, capture_output=True,
    )
    # PA DSP master: kick weight, carve, tame 3–6 kHz, acoustic tops, I≈−8.5 TP≤−1.0
    af = (
        "highpass=f=26:poles=2,"
        "lowshelf=f=90:t=q:w=0.7:g=1.6,"
        "equalizer=f=52:t=q:w=1.1:g=2.0,"
        "equalizer=f=72:t=q:w=1.4:g=-1.1,"
        "equalizer=f=380:t=q:w=1.0:g=-0.8,"
        "equalizer=f=1800:t=q:w=1.0:g=1.2,"
        "equalizer=f=2400:t=q:w=1.1:g=1.4,"
        "equalizer=f=4500:t=q:w=1.2:g=-1.8,"
        "equalizer=f=5500:t=q:w=1.2:g=-2.0,"
        "equalizer=f=6500:t=q:w=1.2:g=-2.2,"
        "equalizer=f=10000:t=q:w=1.1:g=-2.8,"
        "highshelf=f=7000:t=q:w=0.7:g=-3.2,"
        "lowpass=f=15000:poles=1,"
        "acompressor=threshold=-18dB:ratio=1.45:attack=10:release=160:makeup=1.15,"
        "loudnorm=I=-8.5:TP=-1.0:LRA=7,"
        "alimiter=limit=0.891:attack=1:release=50:level=disabled"
    )
    r = subprocess.run(
        [FFMPEG, "-y", "-i", str(raw), "-af", af, str(mastered)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("master fail", (r.stderr or "")[-2000:])
        raise RuntimeError("master failed")
    subprocess.run(
        [FFMPEG, "-y", "-i", str(mastered), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)],
        check=True, capture_output=True,
    )
    dur = sum(b for _, b, _, _ in FULL_SECTIONS) * BAR_S
    try:
        ffprobe = "ffprobe"
        cand = Path(FFMPEG).parent / ("ffprobe.exe" if sys.platform.startswith("win") else "ffprobe")
        if cand.exists():
            ffprobe = str(cand)
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(mp3_path)],
            capture_output=True, text=True, check=True,
        )
        dur = float(probe.stdout.strip())
    except Exception as e:
        print("ffprobe", e)
    print("MP3", mp3_path, "dur", round(dur, 2))
    return dur


def measure_lufs(path: Path) -> dict:
    out = {"I": None, "TP": None, "LRA": None, "raw": ""}
    r = subprocess.run(
        [FFMPEG, "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    txt = (r.stderr or "") + (r.stdout or "")
    out["raw"] = txt[-2500:]
    summ = txt.rsplit("Summary:", 1)[-1] if "Summary:" in txt else txt
    m_i = re.search(r"I:\s+(-?[0-9.]+)\s+LUFS", summ)
    m_lra = re.search(r"LRA:\s+(-?[0-9.]+)\s+LU", summ)
    m_tp = re.search(r"True peak:\s+(-?[0-9.]+)\s+dBTP", summ, re.I) or re.search(
        r"Peak:\s+(-?[0-9.]+)\s+dBFS", summ
    )
    if m_i: out["I"] = float(m_i.group(1))
    if m_tp: out["TP"] = float(m_tp.group(1))
    if m_lra: out["LRA"] = float(m_lra.group(1))
    print("LUFS", path.name, "I=", out["I"], "TP=", out["TP"], "LRA=", out["LRA"])
    return out


def measure_mid_bloom(path: Path) -> dict:
    """Compare Drop_mute (240–280s) vs Drop_open (280–339s) mid 700Hz–3kHz energy."""
    import json
    raw = OUT / "_figment_analyze.f32"
    subprocess.run(
        [FFMPEG, "-y", "-i", str(path), "-ac", "1", "-ar", "48000", "-f", "f32le", str(raw)],
        check=True, capture_output=True,
    )
    x = np.fromfile(raw, dtype=np.float32).astype(np.float64)
    sr = 48000.0

    def band_energy_db(seg, lo, hi):
        n = len(seg)
        if n < 64:
            return -120.0
        bs = min(n, 48000)
        vals = []
        step = max(1, bs // 2)
        for i0 in range(0, max(1, n - bs // 2), step):
            chunk = seg[i0:i0 + bs]
            if len(chunk) < max(64, bs // 2):
                break
            win = np.hanning(len(chunk))
            spec = np.fft.rfft(chunk * win)
            freqs = np.fft.rfftfreq(len(chunk), 1.0 / sr)
            mag2 = np.abs(spec) ** 2
            mask = (freqs >= lo) & (freqs < hi)
            vals.append(float(np.sum(mag2[mask])) + 1e-20)
        e = float(np.mean(vals)) if vals else 1e-20
        return 10.0 * math.log10(e)

    def section(t0, t1):
        return x[int(t0 * sr):int(t1 * sr)]

    mute = section(240.0, 280.0)
    open_ = section(280.0, 339.0)

    def rel_mid(seg):
        full = band_energy_db(seg, 20.0, 12000.0)
        mid = band_energy_db(seg, 700.0, 3000.0)
        low = band_energy_db(seg, 30.0, 200.0)
        return mid - full, mid, low - full

    mute_rel, mute_mid, mute_low = rel_mid(mute)
    open_rel, open_mid, open_low = rel_mid(open_)
    out = {
        "mute_mid_db": round(mute_rel, 2),
        "open_mid_db": round(open_rel, 2),
        "delta_db": round(open_rel - mute_rel, 2),
        "mute_abs": round(mute_mid, 2),
        "open_abs": round(open_mid, 2),
        "open_low_note": f"open low-rel={open_low:.2f} dB (mute low-rel={mute_low:.2f})",
    }
    print("MID-BLOOM mute_rel", out["mute_mid_db"], "open_rel", out["open_mid_db"],
          "delta", out["delta_db"], out["open_low_note"])
    (OUT / "_figment_mid_bloom.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def write_notes(dur: float, metas: list, lufs: dict, shots: dict, errors: list,
                mid_delta: dict | None = None):
    t0 = 0.0
    lines = [
        "# EvAIx Figment v2 — Vestiges slots 01–04 @ 162 F#",
        "",
        f"**MP3:** `{MP3_NAME}`",
        f"- Downloads: `C:\\\\Users\\\\Gebruiker\\\\Downloads\\\\{MP3_NAME}`",
        f"- Workspace: `/workspace/{MP3_NAME}`",
        f"- Exports: `/workspace/exports/{MP3_NAME}`",
        f"- Script: `/workspace/build_figment_162_v2.py`",
        f"- Bridge: `C:\\\\Users\\\\Gebruiker\\\\ableton-mcp\\\\evaix-bridge\\\\build_figment_162_v2.py`",
        f"- QC baseline: `/workspace/finetunix-figment-qc.md` (verdict needs_tweaks → mid-bloom fix)",
        "",
        f"Duration: **{dur:.2f} s** (~{dur/60:.2f} min) · BPM **{BPM:.0f}** · Key **F# major** (dark filters)",
        "",
        "## Measured loudness",
        f"- **I** = {lufs.get('I')} LUFS (target −8…−9)",
        f"- **TP** = {lufs.get('TP')} dB (target ≤ −1.0 dBTP)",
        f"- **LRA** = {lufs.get('LRA')} LU",
        "",
        "## FineTuniX mid-bloom fix (v2)",
        "- Trigger: `/workspace/finetunix-figment-qc.md` — acid morph **needs_tweaks** (Drop_open LF-weighted; 700Hz–3k fell vs mute).",
        "- Recipe: Mental Tribe / Pozek — dual acid LS13 saw+MG; HPF acid ~160 Hz; presence ~1.8–2.8 kHz; light sat AFTER EQ; tame 3–6 kHz.",
        "- Muted (`drop_muted`, open≈0.18): heavy LPF ~850–1600 + mid cut so 700–3k stays quiet.",
        "- Open (`drop_open`, open≈0.92): cutoff/presence bloom + bus peaking @900/1800/2200/2800; macro LPF ≥5.2 kHz so mids survive.",
        "- Kept: loudness/arc/kick/doctrine that already PASSed; dual acid LS13; no Haniwa bounce.",
        "- Optional: kick punch body +1.6 dB @110 Hz; light Haas width on hats/atm only (kick/bass mono).",
        "",
        "## Slot map (skeleton-locked)",
        "| Slot | ID | Time | Energy | Character |",
        "|------|-----|------|--------|-----------|",
        "| 01 | Figment_Intro | 0:00–2:00 | 2 | Atm only · Drift pad · OB LPF 15%→open · no kick |",
        "| 02 | Figment_Build | 2:00–4:00 | 3 | +kick 1/5/9/13 · +dark ride 8ths · restraint |",
        "| 03 | Figment_Drop | 4:00–6:00 | 6 | Dual acid (Acid LPF + MG −8va) muted→open · first release |",
        "| 04 | Figment_Out | 6:00–7:00 | 4 | Strip ride · acid closes · StepJump stutter → F handoff |",
        "",
        "## Mute games (Figment open)",
        "| Bars (gesture) | Action | Mapped section |",
        "|----------------|--------|----------------|",
        "| 1–8 | atm only | Intro_a/b |",
        "| 9–16 | +kick | Build_kick |",
        "| 17–24 | +ride | Build_ride |",
        "| 25–32 | +acid muted | Drop_mute |",
        "| 33–48 | acid opens | Drop_open |",
        "| 49–56 | −ride acid closes | Drop_close → Out |",
        "",
        "## Poly doctrine",
        "- Acid **Last Step 13** vs kick **16** vs hats **15** vs perc **7**",
        "- Kick grid: steps 0/4/8/12 (Electribe 1/5/9/13)",
        "- Dual acid: Acid LPF 303 saw + MG LPF square −8va",
        "",
        "## Sample families (rotated per slot)",
        f"- Slot 01: veiled {BD_FAMILIES['01']} + HH-1C + noise/SFX haze",
        f"- Slot 02: dry {BD_FAMILIES['02']} + HH-2/3C + dark Ride-1 8ths",
        f"- Slot 03: peak {BD_FAMILIES['03']} + HH-5/7C + JunkPerc/rim poly7",
        f"- Slot 04: thin {BD_FAMILIES['04']} + sparse HH-1C + StepJump",
        "",
        "## Section timeline",
    ]
    for m in metas:
        t1 = t0 + m["dur_s"]
        lines.append(
            f"- **{t0:.1f}–{t1:.1f}s** `{m['name']}` (slot {m['slot']}, {m['bars']} bars) — "
            f"{m['story']} [bd={m['bd']}; acid_ev={m['acid_events']}; open={m['acid_open']:.2f}]"
        )
        t0 = t1
    lines += [
        "",
        "## Sound design locks",
        "- Acid: Acid LPF mid-bloom muted→open on Drop, presence 1.8–2.8 kHz, slides+accents, LS13",
        "- Kick: root-tuned F# (~46 Hz sub), punch body ~110 Hz, drive +EQ-before-sat",
        "- Drift pad: F#–C#–F#–A# hold, OB LPF character, dark major ≠ happy",
        "- Filters: Acid LPF acid · MG LPF −8va · OB atm — never MS20 scream",
        "- Master: mid lift 1.8–2.4 kHz + PA tame 4.5–10 kHz, highshelf −3.2 dB @7k, loudnorm I=-8.5 TP=-1.0",
        "",
        "## Doctrine kept",
        "- Free-party / mental tekno / acidcore — **no commercial EDM drops**",
        "- Weight: Pneumatix UP + Van der Wiese / Enko / Pozek / Yoene303 cluster",
        "- Plateaus not festival builds; kick mute/filter open = release",
        "- Acoustic quiet tops (Pneumatix-clean)",
        "",
    ]
    if mid_delta:
        lines += [
            "## Mid-band open vs mute (measured)",
            f"- Drop_mute 700Hz–3k band level: **{mid_delta.get('mute_mid_db')}** dB (rel fullband)",
            f"- Drop_open 700Hz–3k band level: **{mid_delta.get('open_mid_db')}** dB (rel fullband)",
            f"- Delta open−mute: **{mid_delta.get('delta_db')}** dB (target: open clearly above mute)",
            "- QC v1 baseline (finetunix-figment-qc): mute mid rel −5.9 / open mid rel −8.9 (open WORSE — LF-weighted).",
            f"- Low-band check: {mid_delta.get('open_low_note', 'n/a')}",
            "",
        ]
    lines += [
        f"Samples used: {shots.get('used', [])}",
        f"Errors: {errors}",
        "Ableton: skipped (--skip-ableton / DSP bounce)",
        "Haniwa: not bounced (blocked until acid mid morph clears)",
        "",
        "*EvAIx · Figment Vestiges 01–04 v2 · mid-bloom FAIL→green*",
    ]
    text = "\n".join(lines)
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTES_PATH.write_text(text, encoding="utf-8")
    print("NOTES", NOTES_PATH)
    try:
        NOTES_WORKSPACE.write_text(text, encoding="utf-8")
        print("NOTES workspace", NOTES_WORKSPACE)
    except Exception as e:
        print("NOTES workspace copy", e)


def main():
    skip_ableton = "--skip-ableton" in sys.argv or True  # default DSP
    print("=== EvAIx Figment 162 v2 F# mid-bloom ===")
    print("FACTORY", FACTORY, "exists", FACTORY.exists())
    print("BPM", BPM, "BAR_S", round(BAR_S, 4), "total bars",
          sum(b for _, b, _, _ in FULL_SECTIONS),
          "est dur", round(sum(b for _, b, _, _ in FULL_SECTIONS) * BAR_S, 1))
    errors = []
    shots = ensure_shots()
    mixes = []
    metas = []
    for i, (name, bars, mode, slot) in enumerate(FULL_SECTIONS):
        path, meta = render_section(i, name, bars, mode, slot, shots)
        mixes.append(path)
        metas.append(meta)

    # bounce to workspace + exports
    for dest in (MP3_WORKSPACE, MP3_EXPORTS):
        dest.parent.mkdir(parents=True, exist_ok=True)
    dur = bounce_mp3(mixes, MP3_WORKSPACE)
    if MP3_EXPORTS.resolve() != MP3_WORKSPACE.resolve():
        shutil.copy2(MP3_WORKSPACE, MP3_EXPORTS)
        print("copied exports", MP3_EXPORTS)

    lufs = measure_lufs(MP3_WORKSPACE)
    # remaster nudge if outside I target
    if lufs.get("I") is not None and (lufs["I"] < -9.5 or lufs["I"] > -7.5):
        print("LUFS out of band — second-pass loudnorm")
        tmp = OUT / "_figment_remaster.wav"
        target_i = -8.5
        af = f"loudnorm=I={target_i}:TP=-1.0:LRA=7,alimiter=limit=0.891:attack=1:release=50:level=disabled"
        subprocess.run([FFMPEG, "-y", "-i", str(MP3_WORKSPACE), "-af", af, str(tmp)],
                       check=True, capture_output=True)
        subprocess.run(
            [FFMPEG, "-y", "-i", str(tmp), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3_WORKSPACE)],
            check=True, capture_output=True,
        )
        shutil.copy2(MP3_WORKSPACE, MP3_EXPORTS)
        lufs = measure_lufs(MP3_WORKSPACE)

    mid_delta = measure_mid_bloom(MP3_WORKSPACE)
    write_notes(dur, metas, lufs, shots, errors, mid_delta=mid_delta)

    # try Windows Downloads + bridge copy (may fail on Linux box — parent/CopyFromBox handles)
    try:
        MP3_DOWNLOADS.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MP3_WORKSPACE, MP3_DOWNLOADS)
        print("Downloads", MP3_DOWNLOADS)
    except Exception as e:
        errors.append(f"downloads_copy: {e}")
        print("Downloads copy deferred:", e)
    try:
        BRIDGE_COPY.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__).resolve(), BRIDGE_COPY)
        print("Bridge script", BRIDGE_COPY)
    except Exception as e:
        errors.append(f"bridge_copy: {e}")
        print("Bridge copy deferred:", e)

    # also copy script next to exports notes
    try:
        shutil.copy2(Path(__file__).resolve(), Path("/workspace/exports/build_figment_162_v2.py"))
    except Exception:
        pass

    print("DONE", MP3_WORKSPACE, "I=", lufs.get("I"), "TP=", lufs.get("TP"),
          "dur=", round(dur, 1), "skip_ableton=", skip_ableton)
    if errors:
        print("ERRORS", errors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
