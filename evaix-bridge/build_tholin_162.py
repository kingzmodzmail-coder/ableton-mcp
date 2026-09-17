# -*- coding: utf-8 -*-
"""EvAIx Tholin Vestiges slots 09–13 @ 162 BPM E major — FULL RENDER (~10').

Haniwa PASS unlock · peak of 30' set · Pneumatix UP · mid-bloom acid (700Hz–3k).
Mute games on Drop · Break kick OUT · Return harder+sub.
Doctrine: plateaus · free-party not EDM · new families ≠ Figment/Haniwa.
Default: --skip-ableton (DSP bounce).
"""
from __future__ import annotations

import json
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
STEP_S = BEAT_S / 4.0
KEY = "E"

_HERE = Path(__file__).resolve().parent
_POOL_CANDIDATES = [
    Path("/workspace/exports/tholin-pool"),
    Path("/workspace/samples/tholin-162"),
    _HERE / "samples" / "tholin-162",
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\tholin-162"),
]
POOL = next((p for p in _POOL_CANDIDATES if (p / "oneshots").exists()), _POOL_CANDIDATES[0])
ONESHOT_SRC = POOL / "oneshots"

OUT = Path("/workspace/samples/tholin-162-render") if Path("/workspace").exists() else (
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\tholin-162-render")
)
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"; ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_DIR = OUT / "sections"; SECTION_DIR.mkdir(parents=True, exist_ok=True)

MP3_NAME = "EvAIx_Tholin_162.mp3"
MP3_WORKSPACE = Path("/workspace") / MP3_NAME if Path("/workspace").exists() else OUT / MP3_NAME
MP3_EXPORTS = Path("/workspace/exports") / MP3_NAME if Path("/workspace/exports").exists() else OUT / MP3_NAME
MP3_DOWNLOADS = Path(r"C:\Users\Gebruiker\Downloads") / MP3_NAME
NOTES_PATH = (
    Path("/workspace/exports/EvAIx_Tholin_162_NOTES.md")
    if Path("/workspace/exports").exists()
    else OUT / "EvAIx_Tholin_162_NOTES.md"
)
NOTES_WORKSPACE = Path("/workspace/EvAIx_Tholin_162_NOTES.md") if Path("/workspace").exists() else NOTES_PATH
BRIDGE_COPY = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\build_tholin_162.py")
MID_JSON = Path("/workspace/exports/_tholin_mid_bloom.json") if Path("/workspace/exports").exists() else OUT / "_tholin_mid_bloom.json"

# Gains — Pneumatix UP (industrial denser); quiet acoustic tops; harsh 3–6k under mids
KICK_G = 1.45
BASS_G = KICK_G * (10 ** (-8.0 / 20.0))
HATS_G, OH_G, RIDE_G, PERC_G = 0.11, 0.09, 0.18, 0.30
ACID_G, MG_G, ATM_G, PAD_G, FX_G = 0.36, 0.16, 0.22, 0.20, 0.12
TUBE_GAIN = 1.55
HAAS_W, HAAS_MS = 0.18, 7.0
ACID_HPF_HZ = 160.0
ACID_PRESENCE_HZ = 2200.0
ACID_PRESENCE_DB_OPEN = 3.2   # slightly softer than Haniwa 3.4 — FineTuniX soft note
ACID_PRESENCE_DB_MUTE = -4.5

# E major (dark filters) — peak key of Vestiges chain
E_MAJ = np.array([
    82.41,   # E2
    92.50,   # F#2
    103.83,  # G#2
    110.00,  # A2
    123.47,  # B2
    138.59,  # C#3
    164.81,  # E3
    185.00,  # F#3
], dtype=np.float64)
E_LOW = E_MAJ / 2.0  # MG LPF −8va
E_PAD = np.array([82.41, 123.47, 164.81, 207.65], dtype=np.float64)  # E B E G#

# ~10' chapter — 405 bars @162 ≈ 600s
# Mid-bloom windows: mute 240–280s · open 280–339s (same math as Haniwa for QC continuity)
FULL_SECTIONS = [
    # 09 Tholin_Intro 0:00–2:00 E3 — glowing atm; no full kick / sparse
    ("Tholin_Intro_a", 40, "intro_glow", "09"),
    ("Tholin_Intro_b", 41, "intro_haze", "09"),
    # 10 Tholin_Build 2:00–4:00 E5 — +kick · ride · muted acid LS13
    ("Tholin_Build_kick", 40, "build_kick", "10"),
    ("Tholin_Build_acid", 41, "build_muted_acid", "10"),
    # 11 Tholin_Drop 4:00–7:00 E10 — PEAK mute games + mid-bloom
    ("Tholin_Drop_mute", 27, "drop_muted", "11"),
    ("Tholin_Drop_open", 40, "drop_open", "11"),
    ("Tholin_Drop_mute_ind", 14, "drop_mute_ind", "11"),
    ("Tholin_Drop_mute_hats", 14, "drop_mute_hats", "11"),
    ("Tholin_Drop_max", 27, "drop_max", "11"),
    # 12 Tholin_Break 7:00–8:00 E4 — Kick OUT; acid+atm fragile major
    ("Tholin_Break", 40, "break_fragile", "12"),
    # 13 Tholin_Return 8:00–10:00 E9 — Kick harder · +sub · last peak
    ("Tholin_Return_a", 40, "return_peak", "13"),
    ("Tholin_Return_b", 41, "return_hard", "13"),
]

# Blacklists — do not reuse Figment factory spine or Haniwa F/tribal pool as spine
FIGMENT_BLACKLIST = {
    "014_BD-15.wav", "012_BD-13.wav", "016_BD-17.wav", "018_BD-19.wav",
    "019_BD-20.wav", "020_BD-21.wav", "010_BD-11.wav", "008_BD-9.wav",
    "054_HH-1C.wav", "056_HH-2C.wav", "058_HH-3C.wav", "062_HH-5C.wav",
    "066_HH-7C.wav", "045_Rim-1.wav", "047_Rim-3.wav", "048_Clap-1.wav",
    "052_Clap-5.wav", "076_Tom-1.wav", "078_Tom-3.wav", "092_JunkPerc.wav",
    "102_SFX-1.wav", "104_SFX-3.wav", "200_Noise.wav", "068_Ride-1.wav",
}
HANIWA_BLACKLIST = {
    "bd_f01_organic.wav", "bd_f02_dry.wav", "bd_f03_groove.wav", "bd_f04_peak.wav",
    "bd_f05_hard.wav", "bd_f06_thin_out.wav", "bd_sinkick_veiled.wav", "bd_kick_ready_morph.wav",
    "hh_7c_noiseish.wav", "hh_5c_sparse.wav", "hh_1c_mi.wav", "hh_5o_bright.wav",
    "hh_1o_mi.wav", "hh_7o_peak.wav",
    "perc_cowbel.wav", "perc_metal_0.wav", "perc_metal_1.wav", "perc_metal_2.wav",
    "perc_metal_3.wav", "perc_clank_rev.wav", "perc_synperc.wav", "perc_zap.wav",
    "perc_rim2.wav", "perc_junk_crushed.wav", "perc_kb_clap.wav", "perc_sd1_accent.wav",
    "ride_metallic_synperc.wav", "ride_zap_tip.wav",
    "atm_perclp_1.wav", "atm_perclp_2.wav", "atm_perclp_3.wav", "atm_synlp_bright.wav",
    "atm_voice_1_pad.wav", "atm_voice_7_grain.wav",
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
    n = len(x)
    if n < 8:
        return x
    blocks = 32
    bs = max(1, n // blocks)
    out = np.zeros_like(x)
    for i in range(blocks):
        a = i * bs
        b = n if i == blocks - 1 else min(n, (i + 1) * bs)
        t = (i / max(1, blocks - 1)) ** 1.6
        cut = cut_start + (cut_end - cut_start) * t
        out[a:b] = one_pole(x[a:b], float(cut), mode="lpf")
    return out


def prepare_bd(name: str, drive: float = 2.20) -> np.ndarray:
    src = ONESHOT_SRC / name
    if not src.exists():
        raise FileNotFoundError(src)
    raw = read_wav(src)
    y = one_pole(raw, 36.0, mode="hpf")
    y = one_pole(y, 4500.0, mode="lpf")
    y = peaking_eq(y, 110.0, 1.8, q=0.85)  # punch body
    y = tanh_drive(y, drive)
    y = mild_compress(y, thr=0.42, ratio=1.40)
    y = one_pole(y, 9000.0, mode="lpf")
    peak = float(np.max(np.abs(y))) + 1e-12
    return y / peak * 0.95


def synth_sub_bass(root_hz: float = 41.20) -> np.ndarray:
    """E1 fund (~41.20) for mono kick pocket."""
    n = int(0.24 * SR)
    t = np.arange(n) / SR
    env = np.exp(-t / 0.12)
    pitch = root_hz * (1.0 + 1.6 * np.exp(-t / 0.015))
    phase = np.cumsum(2 * np.pi * pitch / SR)
    return mild_compress(np.sin(phase) * env * 0.92, thr=0.48, ratio=1.35)


def synth_drift_pad(n: int, open_amt: float = 0.25, seed: int = 42) -> np.ndarray:
    """Glowing atm pad — E major bright harmony / dark timbre (OB LPF)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    pad = np.zeros(n)
    for i, hz in enumerate(E_PAD):
        det = 1.0 + rng.uniform(-0.004, 0.004)
        phase = 2 * np.pi * hz * det * t
        saw = 2.0 * (np.mod(phase / (2 * np.pi), 1.0) - 0.5)
        sine = np.sin(phase)
        amp = 0.26 if i < 2 else 0.14
        pad += amp * (0.55 * sine + 0.45 * saw * 0.35)
    # slow glow LFO (darker than Haniwa bright)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.055 * t)
    lfo2 = 0.5 + 0.5 * np.sin(2 * np.pi * 0.09 * t + 1.1)
    pad *= 0.48 + 0.38 * lfo + 0.14 * lfo2
    cut = 480.0 + 4200.0 * float(np.clip(open_amt, 0.05, 1.0))
    pad = one_pole(pad, 85.0, mode="hpf")
    pad = one_pole(pad, cut, mode="lpf")
    pad = one_pole(pad, 5200.0, mode="lpf")  # dark timbre despite major
    return pad * 0.58


def synth_atm_haze(n: int, seed: int = 99, bright: float = 0.25) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, n)
    x = one_pole(x, 280.0, mode="hpf")
    x = one_pole(x, 1500.0 + 1400.0 * bright, mode="lpf")
    t = np.arange(n) / SR
    x *= 0.40 + 0.60 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.06 * t))
    return x * 0.22


def acid_303_note(freq: float, dur_s: float, accent: bool = False,
                  cutoff_open: float = 0.35, res_boost: float = 0.0) -> np.ndarray:
    """Acid LPF 303 saw — mid bloom when open (700Hz–3kHz). Figment/Haniwa lesson."""
    n = max(8, int(dur_s * SR))
    t = np.arange(n) / SR
    o = float(np.clip(cutoff_open, 0.0, 1.2))
    pitch = freq * (1.0 + (0.06 if accent else 0.0) * np.exp(-t / 0.04))
    phase = np.cumsum(2 * np.pi * pitch / SR)
    saw = 2.0 * (phase / (2 * np.pi) - np.floor(0.5 + phase / (2 * np.pi)))
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
        y = peaking_eq(y, 1800.0, 2.0 + 0.9 * (o - 0.55), q=0.95)
        y = peaking_eq(y, ACID_PRESENCE_HZ, ACID_PRESENCE_DB_OPEN * min(1.0, o), q=1.05)
        y = peaking_eq(y, 2800.0, 1.8 * min(1.0, o), q=1.1)
        y = peaking_eq(y, 4800.0, -2.6, q=1.2)  # tame harsh
        y = peaking_eq(y, 5500.0, -1.8, q=1.1)
    else:
        y = peaking_eq(y, 2000.0, ACID_PRESENCE_DB_MUTE * (1.0 - o / 0.55), q=0.9)
        y = one_pole(y, 700.0 + 900.0 * o, mode="lpf")
    y = tanh_drive(y, 1.12 + 0.25 * o)  # EQ before sat already applied
    post_lp = 1400.0 + 3400.0 * o if o >= 0.45 else (900.0 + 1400.0 * o)
    y = one_pole(y, post_lp, mode="lpf")
    y = one_pole(y, 5800.0, mode="lpf")  # keep harsh under mids
    return y


def mg_lpf_note(freq: float, dur_s: float, accent: bool = False,
                cutoff_open: float = 0.30) -> np.ndarray:
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
        y = peaking_eq(y, 1600.0, 1.3, q=0.9)
        y = tanh_drive(y, 1.08 + 0.14 * o)
        y = one_pole(y, 3600.0, mode="lpf")
    else:
        y = tanh_drive(y, 1.05)
        y = one_pole(y, 900.0 + 800.0 * o, mode="lpf")
    return y


def process_acid_bus(acid: np.ndarray, mg: np.ndarray, open_amt: float, mode: str):
    o = float(np.clip(open_amt, 0.0, 1.2))
    acid = np.asarray(acid, dtype=np.float64)
    mg = np.asarray(mg, dtype=np.float64)
    acid = one_pole(acid, ACID_HPF_HZ, mode="hpf")
    mg = one_pole(mg, 150.0, mode="hpf")
    if mode in ("drop_open", "drop_max", "return_peak", "return_hard") or o >= 0.65:
        acid = peaking_eq(acid, 900.0, 1.5, q=0.85)
        acid = peaking_eq(acid, 1800.0, 2.5, q=0.95)
        acid = peaking_eq(acid, ACID_PRESENCE_HZ, ACID_PRESENCE_DB_OPEN, q=1.05)
        acid = peaking_eq(acid, 2800.0, 2.0, q=1.1)
        acid = peaking_eq(acid, 4800.0, -3.0, q=1.15)  # FineTuniX: harsh under mids
        acid = peaking_eq(acid, 5500.0, -2.2, q=1.1)
        acid = tanh_drive(acid, 1.20)
        acid = one_pole(acid, 4600.0, mode="lpf")
        mg = peaking_eq(mg, 1400.0, 1.0, q=0.9)
        mg = one_pole(mg, 3400.0, mode="lpf")
        acid *= 1.20
        mg *= 0.92
    elif mode in ("drop_muted", "drop_prep", "build_muted_acid", "break_fragile") or o < 0.40:
        acid = peaking_eq(acid, 2000.0, -5.5, q=0.85)
        acid = one_pole(acid, 800.0 + 700.0 * o, mode="lpf")
        mg = one_pole(mg, 650.0 + 600.0 * o, mode="lpf")
        acid *= 0.75
    else:
        acid = peaking_eq(acid, 2000.0, -1.5 + 3.0 * o, q=0.9)
        acid = one_pole(acid, 1800.0 + 2800.0 * o, mode="lpf")
    return acid, mg


def acid_poly13(bars: int, dens: float, seed: int):
    rng = np.random.default_rng(seed)
    seq = [0, 2, 0, 3, 4, 2, 5, 0, 2, 3, 0, 4, 6]
    accents = {0, 2, 4, 7, 10, 12}
    steps = bars * 16
    events = []
    for s in range(steps):
        local = s % 13
        if local in (0, 2, 4, 5, 7, 9, 10, 12) or rng.random() < dens * 0.12:
            if rng.random() < dens or local in accents:
                note = seq[local]
                accent = local in accents
                dur = 5 if (accent and local == 0) else (3 if accent else 2)
                events.append((s, note, accent, dur))
    return events


def hat_poly15(bars: int, dens: float = 0.7):
    steps = bars * 16
    hits = []
    pattern = [0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 1]
    for s in range(steps):
        if pattern[s % 15] and (dens >= 0.99 or (s % 15) % 3 != 1 or dens > 0.5):
            hits.append(s)
    return hits


def perc_poly7(bars: int, dens: float = 0.5):
    steps = bars * 16
    hits = []
    pattern = [1, 0, 0, 1, 0, 1, 0]
    for s in range(steps):
        if pattern[s % 7] and (s % 7 != 0 or dens > 0.3):
            if dens > 0.8 or s % 14 < 7:
                hits.append(s)
    return hits


def load_shot(name: str, drive=1.0, hpf=0.0, lpf=9000.0) -> np.ndarray:
    y = read_wav(ONESHOT_SRC / name)
    if hpf:
        y = one_pole(y, hpf, mode="hpf")
    y = one_pole(y, min(lpf, 10000.0), mode="lpf")
    y = tanh_drive(y, drive)
    y = one_pole(y, lpf, mode="lpf")
    return y


def ensure_shots() -> dict:
    print("POOL", POOL, "ONESHOT_SRC", ONESHOT_SRC)
    used: list[str] = []
    shots: dict = {}

    bd_map = {
        "bd_veiled": ("bd_sinkick_factory.wav", 1.80),
        "bd_e01": ("bd_e01_organic.wav", 2.00),
        "bd_e02": ("bd_e02_dry.wav", 2.10),
        "bd_e03": ("bd_e03_groove.wav", 2.18),
        "bd_e04": ("bd_e04_peak.wav", 2.25),
        "bd_e05": ("bd_e05_hard.wav", 2.32),
        "bd_e06": ("bd_e06_thin.wav", 1.95),
        "bd_e07": ("bd_e07_return.wav", 2.35),
        "bd_e08": ("bd_e08_hardest.wav", 2.42),
        "bd_bass1": ("bd_bass_e01.wav", 2.20),
        "bd_bass2": ("bd_bass_e02.wav", 2.28),
        "bd_bass3": ("bd_bass_e03.wav", 2.35),
        "bd_bass5": ("bd_bass_e05.wav", 2.40),
    }
    for key, (name, drive) in bd_map.items():
        shots[key] = prepare_bd(name, drive=drive)
        write_mono(ONESHOT / f"{key}_{name}", shots[key], 0.94)
        used.append(name)
    shots["bd_thin"] = one_pole(shots["bd_e06"], 110.0, mode="lpf") * 0.72
    # Return harder = bass-kick layer blend
    shots["bd_return"] = 0.62 * shots["bd_e07"] + 0.48 * shots["bd_bass3"]
    peak = float(np.max(np.abs(shots["bd_return"]))) + 1e-12
    shots["bd_return"] = shots["bd_return"] / peak * 0.95
    shots["bd_return_hard"] = 0.55 * shots["bd_e08"] + 0.55 * shots["bd_bass5"]
    peak = float(np.max(np.abs(shots["bd_return_hard"]))) + 1e-12
    shots["bd_return_hard"] = shots["bd_return_hard"] / peak * 0.95

    for key, name, drive, hpf, lpf in [
        ("hh4c", "hh_4c.wav", 0.95, 4200, 11500),
        ("hh4o", "hh_4o.wav", 1.0, 3200, 10500),
        ("hh6c", "hh_6c.wav", 0.95, 4000, 11500),
        ("hh6o", "hh_6o.wav", 1.05, 3000, 10000),
        ("hh2o", "hh_2o.wav", 1.0, 3400, 10500),
    ]:
        shots[key] = load_shot(name, drive, hpf, lpf)
        used.append(name)

    # Pneumatix industrial/tribe NEW — conga/bongo/djembe/udu/agogo
    for key, name, drive, hpf, lpf in [
        ("conga_hi", "perc_conga_hi.wav", 1.25, 200, 6500),
        ("conga_lo", "perc_conga_lo.wav", 1.20, 80, 4500),
        ("conga_lo2", "perc_conga_lo2.wav", 1.20, 80, 4500),
        ("bongo_hi", "perc_bongo_hi.wav", 1.22, 250, 7000),
        ("bongo_lo", "perc_bongo_lo.wav", 1.18, 100, 5000),
        ("agogo", "perc_agogo.wav", 1.30, 400, 7500),
        ("claves", "perc_claves.wav", 1.15, 800, 8000),
        ("djembe", "perc_djembe.wav", 1.28, 120, 5500),
        ("udu", "perc_udu.wav", 1.20, 60, 4000),
        ("timbales", "perc_timbales.wav", 1.25, 300, 6500),
        ("tambouri", "perc_tambouri.wav", 1.10, 1500, 9000),
        ("triangle", "perc_triangle.wav", 1.05, 2000, 10000),
        ("guiro", "perc_guiro.wav", 1.15, 400, 7000),
        ("shaker", "perc_shaker.wav", 1.05, 2500, 11000),
        ("wbl", "perc_wbl.wav", 1.20, 200, 6000),
        ("clap3", "perc_clap3.wav", 1.10, 700, 8000),
        ("sd2", "perc_sd2_accent.wav", 1.15, 800, 7500),
    ]:
        shots[key] = load_shot(name, drive, hpf, lpf)
        used.append(name)

    shots["ride2"] = load_shot("ride_2.wav", 0.95, 2200, 10000)
    shots["ride3"] = load_shot("ride_3.wav", 0.95, 2000, 9800)
    shots["ride4"] = load_shot("ride_4.wav", 0.95, 2400, 10200)
    shots["ride5"] = load_shot("ride_5.wav", 0.95, 2300, 10000)
    shots["crash2"] = load_shot("crash_2.wav", 0.90, 500, 9000)
    used.extend(["ride_2.wav", "ride_3.wav", "ride_4.wav", "ride_5.wav", "crash_2.wav"])

    for key, name in [
        ("atm_p4", "atm_perclp_4.wav"), ("atm_p5", "atm_perclp_5.wav"),
        ("atm_p6", "atm_perclp_6.wav"), ("atm_p7", "atm_perclp_7.wav"),
        ("atm_s2", "atm_synlp_2.wav"), ("atm_s3", "atm_synlp_3.wav"), ("atm_s4", "atm_synlp_4.wav"),
        ("atm_v3", "atm_voice_3.wav"), ("atm_v5", "atm_voice_5.wav"),
        ("atm_v9", "atm_voice_9.wav"), ("atm_v11", "atm_voice_11.wav"),
        ("atm_v24", "atm_voice_24.wav"), ("atm_v26", "atm_voice_26.wav"),
        ("atm_voc", "atm_vocodr.wav"),
        ("sfx_4", "sfx_4.wav"), ("sfx_5", "sfx_5.wav"),
        ("sfx_sc1", "sfx_scratch1.wav"), ("sfx_sc2", "sfx_scratch2.wav"),
        ("sfx_n", "sfx_noise.wav"),
    ]:
        y = read_wav(ONESHOT_SRC / name)
        y = one_pole(y, 80.0, mode="hpf")
        y = one_pole(y, 7200.0, mode="lpf")
        peak = float(np.max(np.abs(y))) + 1e-12
        shots[key] = y / peak * 0.85
        used.append(name)

    for k in ("hh4c", "hh4o", "hh6c", "hh6o", "hh2o", "ride2", "ride3", "ride4", "ride5"):
        shots[k] = one_pole(shots[k], 9200.0, mode="lpf") * 0.90  # quieter tops

    shots["bass"] = synth_sub_bass(41.20)
    shots["bass_hard"] = synth_sub_bass(41.20) * 1.15
    write_mono(ONESHOT / "bass_sub_E.wav", shots["bass"], 0.9)
    shots["used"] = sorted(set(used))
    print("shots ready", len(shots["used"]))
    return shots


def kit_for_mode(mode: str, slot: str, shots: dict) -> dict:
    bd_pick = {
        "intro_glow": shots["bd_veiled"],
        "intro_haze": shots["bd_veiled"],
        "build_kick": shots["bd_e02"],
        "build_muted_acid": shots["bd_e03"],
        "drop_muted": shots["bd_e04"],
        "drop_open": shots["bd_e05"],
        "drop_mute_ind": shots["bd_e05"],
        "drop_mute_hats": shots["bd_e04"],
        "drop_max": shots["bd_bass2"],
        "break_fragile": shots["bd_veiled"],
        "return_peak": shots["bd_return"],
        "return_hard": shots["bd_return_hard"],
    }
    hat_pick = {
        "intro_glow": shots["hh4c"], "intro_haze": shots["hh4c"],
        "build_kick": shots["hh6c"], "build_muted_acid": shots["hh4c"],
        "drop_muted": shots["hh6o"], "drop_open": shots["hh6o"],
        "drop_mute_ind": shots["hh4o"], "drop_mute_hats": shots["hh4c"],
        "drop_max": shots["hh6o"], "break_fragile": shots["hh4c"],
        "return_peak": shots["hh6o"], "return_hard": shots["hh6o"],
    }
    gains = {
        "intro_glow": dict(kick=0.0, bass=0.0, hats=0.05, oh=0.0, ride=0.0, perc=0.0,
                           acid=0.0, mg=0.0, atm=1.05, pad=1.10, fx=0.45, acid_open=0.10),
        "intro_haze": dict(kick=0.12, bass=0.0, hats=0.08, oh=0.0, ride=0.0, perc=0.0,
                           acid=0.0, mg=0.0, atm=0.95, pad=1.00, fx=0.40, acid_open=0.14),
        "build_kick": dict(kick=0.92, bass=0.50, hats=0.35, oh=0.08, ride=0.45, perc=0.35,
                           acid=0.0, mg=0.0, atm=0.28, pad=0.50, fx=0.20, acid_open=0.18),
        "build_muted_acid": dict(kick=0.96, bass=0.62, hats=0.42, oh=0.15, ride=0.70, perc=0.55,
                                 acid=0.40, mg=0.28, atm=0.18, pad=0.35, fx=0.22, acid_open=0.20),
        "drop_muted": dict(kick=1.0, bass=0.88, hats=0.52, oh=0.28, ride=0.75, perc=0.80,
                           acid=0.48, mg=0.32, atm=0.10, pad=0.25, fx=0.22, acid_open=0.18),
        "drop_open":  dict(kick=1.05, bass=0.95, hats=0.62, oh=0.38, ride=0.95, perc=1.00,
                           acid=1.22, mg=0.75, atm=0.08, pad=0.18, fx=0.30, acid_open=0.92),
        "drop_mute_ind": dict(kick=1.02, bass=0.90, hats=0.58, oh=0.32, ride=0.85, perc=0.08,
                              acid=1.10, mg=0.68, atm=0.10, pad=0.20, fx=0.25, acid_open=0.88),
        "drop_mute_hats": dict(kick=1.02, bass=0.92, hats=0.06, oh=0.02, ride=0.70, perc=0.90,
                               acid=1.12, mg=0.70, atm=0.10, pad=0.18, fx=0.25, acid_open=0.90),
        "drop_max": dict(kick=1.06, bass=0.98, hats=0.65, oh=0.40, ride=1.0, perc=1.05,
                         acid=1.25, mg=0.78, atm=0.06, pad=0.15, fx=0.32, acid_open=0.95),
        "break_fragile": dict(kick=0.0, bass=0.0, hats=0.0, oh=0.0, ride=0.0, perc=0.0,
                              acid=0.85, mg=0.55, atm=0.85, pad=0.90, fx=0.35, acid_open=0.72),
        "return_peak": dict(kick=1.12, bass=1.05, hats=0.58, oh=0.35, ride=0.90, perc=0.85,
                            acid=1.15, mg=0.70, atm=0.10, pad=0.22, fx=0.28, acid_open=0.88),
        "return_hard": dict(kick=1.18, bass=1.12, hats=0.60, oh=0.38, ride=0.95, perc=0.90,
                            acid=1.18, mg=0.72, atm=0.08, pad=0.18, fx=0.30, acid_open=0.90),
    }
    stories = {
        "intro_glow": "Slot09 Intro — glowing PercLP4–7/SynLP dark major; NO full kick",
        "intro_haze": "Slot09 Intro — voice/vocodr haze; sparse veiled BD tease; still restrained",
        "build_kick": "Slot10 Build — E02 kick 1/5/9/13; HH6C; Ride-2 enter; restraint",
        "build_muted_acid": "Slot10 Build — muted dual acid LS13 + ride denser; tribal poly LS7",
        "drop_muted": "Slot11 Drop — dual acid MUTED + full drums; pre-bloom plateau",
        "drop_open": "Slot11 Drop PEAK — acid mid-bloom open; Res spikes 4/8/12/16; all parts",
        "drop_mute_ind": "Slot11 mute game — mute industrial/clank; acid stays open",
        "drop_mute_hats": "Slot11 mute game — unmute industrial, mute hats; tension",
        "drop_max": "Slot11 all-in max before Break prep",
        "break_fragile": "Slot12 Break — Kick OUT; acid+atm only; fragile exposed E major",
        "return_peak": "Slot13 Return — Kick harder + sub-on-kick; last peak before Vyre",
        "return_hard": "Slot13 Return — hardest E08+bass-kick; handoff peel toward B",
    }
    kick_on = {
        "intro_glow": [], "intro_haze": [0],  # sparse tease only
        "build_kick": [0, 4, 8, 12], "build_muted_acid": [0, 4, 8, 12],
        "drop_muted": [0, 4, 8, 12], "drop_open": [0, 4, 8, 12],
        "drop_mute_ind": [0, 4, 8, 12], "drop_mute_hats": [0, 4, 8, 12],
        "drop_max": [0, 4, 8, 12],
        "break_fragile": [],  # Kick OUT
        "return_peak": [0, 4, 8, 12], "return_hard": [0, 4, 8, 12],
    }
    bd_name = {
        "intro_glow": "veiled sinkick", "intro_haze": "veiled sparse",
        "build_kick": "bd_e02_dry", "build_muted_acid": "bd_e03_groove",
        "drop_muted": "bd_e04_peak", "drop_open": "bd_e05_hard",
        "drop_mute_ind": "bd_e05_hard", "drop_mute_hats": "bd_e04_peak",
        "drop_max": "bd_bass_e02", "break_fragile": "NONE",
        "return_peak": "bd_e07+bass_e03", "return_hard": "bd_e08+bass_e05",
    }[mode]
    return {
        "kick": bd_pick[mode], "hat": hat_pick[mode],
        "gains": gains[mode], "story": stories[mode],
        "kick_steps": kick_on[mode], "bd_name": bd_name, "slot": slot,
    }


def render_section(idx: int, name: str, bars: int, mode: str, slot: str, shots: dict):
    N = section_n(bars)
    trk_k = np.zeros(N); trk_b = np.zeros(N); trk_h = np.zeros(N); trk_oh = np.zeros(N)
    trk_ride = np.zeros(N); trk_p = np.zeros(N)
    trk_acid = np.zeros(N); trk_mg = np.zeros(N)
    trk_atm = np.zeros(N); trk_pad = np.zeros(N); trk_fx = np.zeros(N)
    kit = kit_for_mode(mode, slot, shots)
    g = kit["gains"]
    seed = 0xE162 + idx * 29
    rng = np.random.default_rng(seed)

    # free-party kick mute: last 8 bars of drop_max prep Break; brief mute end of drop_muted
    mute_kick_bars = set()
    if mode == "drop_muted" and bars >= 16:
        mute_kick_bars = set(range(bars - 4, bars))
    if mode == "drop_max" and bars >= 16:
        mute_kick_bars = set(range(bars - 8, bars))  # classic tekno mute before Break

    bass_samp = shots["bass_hard"] if mode in ("return_peak", "return_hard", "drop_max") else shots["bass"]

    for bar in range(bars):
        kick_steps = [] if bar in mute_kick_bars else kit["kick_steps"]
        for st in kick_steps:
            beat = bar * 4 + st / 4.0
            place(trk_k, kit["kick"], beat, 1.0)
            place(trk_b, bass_samp, beat, 1.0)

        if g["hats"] > 0.05:
            dens = 0.28 if mode.startswith("intro") else (
                0.55 if "build" in mode else (0.82 if mode in ("drop_open", "drop_max", "return_hard") else 0.65)
            )
            for s in hat_poly15(1, dens=dens):
                if s < 16:
                    beat = bar * 4 + s / 4.0
                    place(trk_h, kit["hat"], beat, 0.72 if s % 4 == 2 else 0.52)

        if g["oh"] > 0.05 and bar % 2 == 1:
            oh = shots["hh6o"] if mode in ("drop_open", "drop_max", "return_hard") else shots["hh4o"]
            place(trk_oh, oh, bar * 4 + 1.5, 0.52)

        if g["ride"] > 0.05:
            rides = [shots["ride2"], shots["ride3"], shots["ride4"], shots["ride5"]]
            ride_samp = rides[bar % len(rides)]
            dens_ride = 8 if mode in ("drop_open", "drop_max", "return_hard") else (
                4 if "build" in mode or mode == "drop_muted" else 4
            )
            step = 0.5 if dens_ride == 8 else 1.0
            for i in range(int(4 / step)):
                beat = bar * 4 + i * step
                place(trk_ride, ride_samp, beat, 0.52 if i % 2 == 0 else 0.38)

        if g["perc"] > 0.08:
            dens = 0.60 if "build" in mode else (0.90 if mode in ("drop_open", "drop_max") else 0.75)
            tribal_bank = [
                shots["conga_hi"], shots["conga_lo"], shots["bongo_hi"], shots["agogo"],
                shots["claves"], shots["djembe"], shots["udu"], shots["timbales"],
            ]
            if mode in ("drop_muted", "drop_open", "drop_mute_hats", "drop_max", "return_peak", "return_hard"):
                tribal_bank += [shots["conga_lo2"], shots["bongo_lo"], shots["guiro"],
                                shots["tambouri"], shots["wbl"], shots["shaker"]]
            for s in perc_poly7(1, dens=dens):
                if s < 16:
                    beat = bar * 4 + s / 4.0
                    samp = tribal_bank[s % len(tribal_bank)]
                    place(trk_p, samp, beat, 0.62 if s % 7 == 0 else 0.48)

        if mode in ("drop_open", "drop_max") and bar % 8 == 7:
            place(trk_p, shots["clap3"], bar * 4 + 1.0, 0.40)
        if mode in ("drop_open", "drop_max") and bar % 16 == 15:
            place(trk_p, shots["sd2"], bar * 4 + 2.0, 0.36)
        if mode == "drop_max" and bar == 0:
            place(trk_fx, shots["crash2"], 0.0, 0.45)

    pad_open = {
        "intro_glow": 0.32, "intro_haze": 0.50, "build_kick": 0.45, "build_muted_acid": 0.40,
        "drop_muted": 0.32, "drop_open": 0.28, "drop_mute_ind": 0.30, "drop_mute_hats": 0.30,
        "drop_max": 0.26, "break_fragile": 0.70, "return_peak": 0.35, "return_hard": 0.30,
    }[mode]
    if g["pad"] > 0.01:
        trk_pad += synth_drift_pad(N, open_amt=pad_open, seed=seed)
    if g["atm"] > 0.01:
        bright = 0.35 if mode.startswith("intro") or mode == "break_fragile" else 0.22
        trk_atm += synth_atm_haze(N, seed=seed + 5, bright=bright)
        atm_bank = {
            "intro_glow": [shots["atm_p4"], shots["atm_p5"], shots["atm_s2"]],
            "intro_haze": [shots["atm_p6"], shots["atm_s3"], shots["atm_v3"], shots["atm_voc"]],
            "build_kick": [shots["atm_p4"]],
            "build_muted_acid": [shots["atm_s2"]],
            "drop_muted": [shots["atm_s3"]],
            "drop_open": [shots["atm_s4"]],
            "drop_mute_ind": [shots["atm_s3"]],
            "drop_mute_hats": [shots["atm_s4"]],
            "drop_max": [shots["atm_s4"]],
            "break_fragile": [shots["atm_p7"], shots["atm_v5"], shots["atm_v9"], shots["atm_voc"]],
            "return_peak": [shots["atm_s2"]],
            "return_hard": [shots["atm_p4"], shots["atm_v11"]],
        }[mode]
        for bar in range(0, bars, 2):
            samp = atm_bank[bar % len(atm_bank)]
            place(trk_atm, samp, bar * 4 + rng.uniform(0, 0.5), 0.32)
        sfx_bank = {
            "intro_glow": [shots["sfx_n"], shots["sfx_4"]],
            "intro_haze": [shots["sfx_5"], shots["sfx_sc1"], shots["sfx_n"]],
            "build_kick": [shots["sfx_4"]],
            "build_muted_acid": [shots["sfx_sc2"]],
            "drop_muted": [],
            "drop_open": [],
            "drop_mute_ind": [],
            "drop_mute_hats": [],
            "drop_max": [shots["sfx_sc1"]],
            "break_fragile": [shots["sfx_5"], shots["sfx_n"]],
            "return_peak": [],
            "return_hard": [shots["sfx_4"]],
        }[mode]
        for bar in range(0, bars, 3):
            if sfx_bank:
                place(trk_fx, sfx_bank[bar % len(sfx_bank)],
                      bar * 4 + rng.uniform(0, 1.2), 0.36)

    acid_open = float(g["acid_open"])
    dens = {
        "intro_glow": 0.0, "intro_haze": 0.0, "build_kick": 0.0,
        "build_muted_acid": 0.50, "drop_muted": 0.60, "drop_open": 0.90,
        "drop_mute_ind": 0.85, "drop_mute_hats": 0.85, "drop_max": 0.92,
        "break_fragile": 0.70, "return_peak": 0.82, "return_hard": 0.85,
    }[mode]
    if dens > 0.01 and (g["acid"] > 0.05 or g["mg"] > 0.05):
        for step, note_i, accent, dur_steps in acid_poly13(bars, dens, seed):
            bar_i = step // 16
            res = 0.0
            if mode in ("drop_open", "drop_max", "return_hard"):
                local_bar = (bar_i % 16) + 1
                if local_bar in (4, 8, 12, 16):
                    res = 0.85
                elif accent:
                    res = 0.45
            freq = float(E_MAJ[note_i % len(E_MAJ)])
            note = acid_303_note(freq, dur_steps * STEP_S, accent=accent,
                                 cutoff_open=acid_open, res_boost=res)
            place(trk_acid, note, step / 4.0, 1.15 if accent else 0.88)
            mg = mg_lpf_note(float(E_LOW[note_i % len(E_LOW)]), dur_steps * STEP_S * 1.1,
                             accent=accent, cutoff_open=acid_open * 0.88)
            place(trk_mg, mg, step / 4.0, 0.85)

    trk_k *= KICK_G * g["kick"]; trk_b *= BASS_G * g["bass"]
    trk_h *= HATS_G * g["hats"]; trk_oh *= OH_G * g["oh"]
    trk_ride *= RIDE_G * g["ride"]; trk_p *= PERC_G * g["perc"]
    trk_acid *= ACID_G * g["acid"]; trk_mg *= MG_G * g["mg"]
    trk_atm *= ATM_G * g["atm"]; trk_pad *= PAD_G * g["pad"]; trk_fx *= FX_G * g["fx"]

    if g["acid"] > 0.05 or g["mg"] > 0.05:
        trk_acid, trk_mg = process_acid_bus(trk_acid, trk_mg, acid_open, mode)

    mono_bed = trk_k + trk_b + trk_ride + trk_p + trk_pad
    hats_atm = trk_h + trk_oh + trk_atm
    acid_bus = trk_acid + trk_mg

    cut_map = {
        "intro_glow": (650.0, 2000.0),
        "intro_haze": (1400.0, 3800.0),
        "build_kick": (2800.0, 5000.0),
        "build_muted_acid": (3000.0, 5200.0),
        "drop_muted": (2000.0, 3600.0),
        "drop_open": (4500.0, 9200.0),
        "drop_mute_ind": (4200.0, 8800.0),
        "drop_mute_hats": (4200.0, 8800.0),
        "drop_max": (4800.0, 9500.0),
        "break_fragile": (2800.0, 6200.0),
        "return_peak": (4200.0, 9000.0),
        "return_hard": (4500.0, 9200.0),
    }
    c0, c1 = cut_map[mode]
    mono_bed = apply_moving_lpf(mono_bed, c0, c1)
    hats_atm = apply_moving_lpf(hats_atm, c0, c1)
    if mode in ("drop_open", "drop_max", "return_hard"):
        acid_bus = apply_moving_lpf(acid_bus, 5000.0, 8800.0)
    elif mode in ("drop_muted", "build_muted_acid"):
        acid_bus = apply_moving_lpf(acid_bus, 850.0, 1500.0)
    elif mode == "break_fragile":
        acid_bus = apply_moving_lpf(acid_bus, 2800.0, 6500.0)
    else:
        acid_bus = apply_moving_lpf(acid_bus, c0 * 0.85, c1 * 0.95)
    fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, c1 * 1.05)

    mono_bed = valve_force(mono_bed, TUBE_GAIN * 0.82)
    hats_atm = valve_force(hats_atm, TUBE_GAIN * 0.72)
    acid_bus = valve_force(acid_bus, TUBE_GAIN * 0.88)
    fx_bus = valve_force(fx_bus, TUBE_GAIN * 0.92)
    mono_bed = one_pole(mono_bed, 11000.0, mode="lpf")
    hats_atm = one_pole(hats_atm, 9000.0, mode="lpf")
    acid_lp = 5400.0 if mode in ("drop_open", "drop_max", "return_hard") else 7200.0
    acid_bus = one_pole(acid_bus, acid_lp, mode="lpf")
    fx_bus = one_pole(fx_bus, 8200.0, mode="lpf")

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
    concat_list = OUT / "_tholin_concat.txt"
    raw = OUT / "_tholin_raw.wav"
    mastered = OUT / "_tholin_master.wav"
    with concat_list.open("w", encoding="utf-8") as f:
        for p in mixes:
            f.write(f"file '{p.as_posix()}'\n")
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw)],
        check=True, capture_output=True,
    )
    # PA master — mid lift + stronger 3–6k tame (FineTuniX soft note)
    af = (
        "highpass=f=26:poles=2,"
        "lowshelf=f=85:t=q:w=0.7:g=1.7,"
        "equalizer=f=41:t=q:w=1.1:g=2.2,"
        "equalizer=f=68:t=q:w=1.4:g=-1.0,"
        "equalizer=f=380:t=q:w=1.0:g=-0.8,"
        "equalizer=f=900:t=q:w=1.0:g=0.9,"
        "equalizer=f=1800:t=q:w=1.0:g=1.5,"
        "equalizer=f=2400:t=q:w=1.1:g=1.7,"
        "equalizer=f=2800:t=q:w=1.0:g=1.0,"
        "equalizer=f=4500:t=q:w=1.2:g=-2.2,"
        "equalizer=f=5500:t=q:w=1.2:g=-2.5,"
        "equalizer=f=6500:t=q:w=1.2:g=-2.6,"
        "equalizer=f=10000:t=q:w=1.1:g=-3.0,"
        "highshelf=f=7000:t=q:w=0.7:g=-3.5,"
        "lowpass=f=14800:poles=1,"
        "acompressor=threshold=-18dB:ratio=1.45:attack=10:release=160:makeup=1.15,"
        "loudnorm=I=-8.5:TP=-1.0:LRA=8,"
        "alimiter=limit=0.891:attack=1:release=50:level=disabled"
    )
    r = subprocess.run(
        [FFMPEG, "-y", "-i", str(raw), "-af", af, str(mastered)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("master fail", (r.stderr or "")[-2000:])
        raise RuntimeError("master failed")

    # Surgical Drop_open mid boost 280–339s (Intro+Build=240s + mute 40s)
    surg = OUT / "_tholin_surg.wav"
    af2 = (
        "equalizer=f=900:t=q:w=1.0:g=1.8:enable='between(t,280,339)',"
        "equalizer=f=1800:t=q:w=1.0:g=2.8:enable='between(t,280,339)',"
        "equalizer=f=2400:t=q:w=1.1:g=3.0:enable='between(t,280,339)',"
        "equalizer=f=2800:t=q:w=1.0:g=2.0:enable='between(t,280,339)',"
        "equalizer=f=5200:t=q:w=1.2:g=-2.4:enable='between(t,280,339)',"
        "loudnorm=I=-8.5:TP=-1.0:LRA=8,"
        "alimiter=limit=0.891:attack=1:release=50:level=disabled"
    )
    r2 = subprocess.run(
        [FFMPEG, "-y", "-i", str(mastered), "-af", af2, str(surg)],
        capture_output=True, text=True,
    )
    if r2.returncode != 0:
        print("surg warn", (r2.stderr or "")[-800:])
        surg = mastered
    else:
        mastered = surg

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
    """Compare Drop_mute (~240–280s) vs Drop_open (~280–339s) mid 700Hz–3kHz."""
    raw = OUT / "_tholin_analyze.f32"
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
        harsh = band_energy_db(seg, 3000.0, 6000.0)
        return mid - full, mid, low - full, harsh - full

    mute_rel, mute_mid, mute_low, mute_harsh = rel_mid(mute)
    open_rel, open_mid, open_low, open_harsh = rel_mid(open_)
    out = {
        "mute_mid_rel": round(mute_rel, 2),
        "open_mid_rel": round(open_rel, 2),
        "delta_open_minus_mute": round(open_rel - mute_rel, 2),
        "mute_abs": round(mute_mid, 2),
        "open_abs": round(open_mid, 2),
        "abs_mid_rise_db": round(open_mid - mute_mid, 2),
        "mute_low_rel": round(mute_low, 2),
        "open_low_rel": round(open_low, 2),
        "mute_harsh_rel": round(mute_harsh, 2),
        "open_harsh_rel": round(open_harsh, 2),
        "harsh_under_mids": bool(open_harsh < open_rel),
        "open_low_note": f"open low-rel={open_low:.2f} dB (mute low-rel={mute_low:.2f})",
    }
    print("MID-BLOOM mute_rel", out["mute_mid_rel"], "open_rel", out["open_mid_rel"],
          "delta", out["delta_open_minus_mute"], "harsh_under_mids", out["harsh_under_mids"],
          out["open_low_note"])
    MID_JSON.parent.mkdir(parents=True, exist_ok=True)
    MID_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    (OUT / "_tholin_mid_bloom.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def write_notes(dur: float, metas: list, lufs: dict, shots: dict, errors: list,
                mid_delta: dict | None = None):
    t0 = 0.0
    lines = [
        "# EvAIx Tholin — Vestiges slots 09–13 @ 162 E",
        "",
        f"**MP3:** `{MP3_NAME}`",
        f"- Downloads: `C:\\\\Users\\\\Gebruiker\\\\Downloads\\\\{MP3_NAME}`",
        f"- Workspace: `/workspace/{MP3_NAME}`",
        f"- Exports: `/workspace/exports/{MP3_NAME}`",
        f"- Script: `/workspace/build_tholin_162.py`",
        f"- Bridge: `C:\\\\Users\\\\Gebruiker\\\\ableton-mcp\\\\evaix-bridge\\\\build_tholin_162.py`",
        f"- Pool: `/workspace/exports/tholin-pool/oneshots/` ({len(shots.get('used', []))} WAVs)",
        "",
        f"Duration: **{dur:.2f} s** (~{dur/60:.2f} min) · BPM **{BPM:.0f}** · Key **E major** (dark filters · peak of 30′ set)",
        "",
        "## Measured loudness",
        f"- **I** = {lufs.get('I')} LUFS (target −8…−9)",
        f"- **TP** = {lufs.get('TP')} dB (target ≤ −1.0 dBTP)",
        f"- **LRA** = {lufs.get('LRA')} LU",
        "",
        "## Mid-bloom (Figment/Haniwa lesson · FineTuniX gate)",
        "- Acid muted→open shows **700Hz–3k rise** (not LF-only).",
        "- Recipe: HPF acid ~160 Hz · presence 1.8–2.8 kHz · sat AFTER EQ · tame 3–6 kHz UNDER mids.",
        "- Drop_mute open≈0.18; Drop_open≈0.92 + surgical window 280–339s.",
        "- Res spikes bars 4/8/12/16 on Drop_open / Drop_max / Return_hard.",
        "",
    ]
    if mid_delta:
        lines += [
            "## Mid-band open vs mute (measured)",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Mute mid rel (700Hz–3k vs full) | **{mid_delta.get('mute_mid_rel')}** dB |",
            f"| Open mid rel (700Hz–3k vs full) | **{mid_delta.get('open_mid_rel')}** dB |",
            f"| Delta open−mute | **{mid_delta.get('delta_open_minus_mute')}** dB (target ≥ +5) |",
            f"| Abs mid rise | **{mid_delta.get('abs_mid_rise_db')}** dB |",
            f"| Harsh 3–6k open rel | {mid_delta.get('open_harsh_rel')} (mute {mid_delta.get('mute_harsh_rel')}) |",
            f"| Harsh under mids on open | **{mid_delta.get('harsh_under_mids')}** |",
            f"| Low-band | {mid_delta.get('open_low_note', 'n/a')} |",
            "",
        ]
    lines += [
        "## Slot map (skeleton-locked · chapter-relative 0–10′)",
        "| Slot | ID | Time | Energy | Character |",
        "|------|-----|------|--------|-----------|",
        "| 09 | Tholin_Intro | 0:00–2:00 | 3 | Glowing atm · major bright / timbre dark · sparse/no full kick |",
        "| 10 | Tholin_Build | 2:00–4:00 | 5 | +kick · ride · muted acid LS13 building |",
        "| 11 | Tholin_Drop | 4:00–7:00 | 10 | **PEAK** dual acid mid-bloom + mute games |",
        "| 12 | Tholin_Break | 7:00–8:00 | 4 | Kick OUT · acid+atm fragile exposed major |",
        "| 13 | Tholin_Return | 8:00–10:00 | 9 | Kick harder · +sub on kick · last peak before Vyre |",
        "",
        "## Mute games (slot 11 skeleton card)",
        "| Gesture | Mapped section |",
        "|---------|----------------|",
        "| full / muted→open bloom | Drop_mute → Drop_open |",
        "| mute industrial/clank | Drop_mute_ind |",
        "| unmute industrial, mute hats | Drop_mute_hats |",
        "| all in max | Drop_max |",
        "| kick mute 8 bars pre-Break | end of Drop_max |",
        "| Kick OUT fragile | Break |",
        "",
        "## Poly doctrine",
        "- Acid **Last Step 13** vs kick **16** vs hats **15** vs perc **7**",
        "- Kick grid: steps 0/4/8/12 (Electribe 1/5/9/13)",
        "- Dual acid: Acid LPF 303 saw + MG LPF square −8va · **E major**",
        "- SD2 / clap3 = sparse accent only — **no gabber spine**",
        "",
        "## Sample families (NEW vs Figment+Haniwa)",
        "- BD: Insane **E01–E08** + KICK BASS E01/E02/E03/E05 (not F01–F06)",
        "- HH: HH-4C/4O · HH-6C/6O · HH-2O (not HH-1/2/3/5/7 Figment or HH5/7 mi Haniwa)",
        "- Perc: Conga/Bongo/Agogo/Claves/Djembe/Udu/Timbales/Tambouri (not metal_0–3/cowbel)",
        "- Ride: Ride-2/3/4/5 (not Ride-1 / metallic synperc)",
        "- Atm: PercLP-4–7 · SynLP-2/3/4 · Voice-3/5/9/11/24/26 · VocodrLP",
        "- SFX: SFX-4/5 · Scratch1/2 · Noise",
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
        "- Acid: mid-bloom muted→open on Drop, presence 1.8–2.8 kHz, LS13, harsh 3–6k cut",
        "- Kick: root-tuned E (~41.2 Hz sub), punch body ~110 Hz, EQ before sat, mono",
        "- Return: E07/E08 layered with KICK BASS E for sub weight",
        "- Perc: Pneumatix tribal UP · poly LS7 conga/bongo/djembe",
        "- Master: mid lift + PA tame 4.5–10 kHz, loudnorm I=-8.5 TP=-1.0",
        "",
        "## Doctrine kept",
        "- Free-party / mental tekno / acidcore — **no commercial EDM drops**",
        "- One real kick-out break (slot 12) OK at set peak",
        "- Pneumatix weight UP · plateaus not festival builds",
        "- New sample family every slot · ≠ Figment + Haniwa pools",
        "- Kick/bass mono · Haas only on hats/atm/acid",
        "",
        f"Samples used ({len(shots.get('used', []))}): {shots.get('used', [])}",
        f"Errors: {errors}",
        "Ableton: skipped (--skip-ableton / DSP bounce)",
        "",
        "*EvAIx · Tholin Vestiges 09–13 · Haniwa PASS unlock · peak chapter*",
    ]
    text = "\n".join(lines)
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTES_PATH.write_text(text, encoding="utf-8")
    print("NOTES", NOTES_PATH)
    try:
        NOTES_WORKSPACE.write_text(text, encoding="utf-8")
    except Exception as e:
        print("NOTES workspace copy", e)


def pool_check() -> int:
    print(f"POOL = {POOL}")
    print(f"ONESHOT exists = {ONESHOT_SRC.exists()}")
    if not ONESHOT_SRC.exists():
        print("ERROR: oneshots dir missing", file=sys.stderr)
        return 1
    present = {p.name for p in ONESHOT_SRC.glob("*.wav")}
    print(f"oneshots on disk: {len(present)}")
    collisions = [n for n in present if n in HANIWA_BLACKLIST or n in FIGMENT_BLACKLIST]
    if collisions:
        print("BLACKLIST HIT:", collisions)
        return 3
    need = [
        "bd_e01_organic.wav", "bd_e05_hard.wav", "bd_e08_hardest.wav",
        "hh_4c.wav", "hh_6o.wav", "perc_conga_hi.wav", "perc_djembe.wav",
        "ride_2.wav", "atm_perclp_4.wav", "atm_synlp_2.wav", "sfx_4.wav",
    ]
    missing = [n for n in need if n not in present]
    if missing:
        print("MISSING core:", missing)
        return 2
    print("OK — Tholin pool distinct from Figment+Haniwa; core WAVs present")
    return 0


def render_full() -> int:
    print("=== EvAIx Tholin 162 E · peak · mid-bloom · mute games · Pneumatix UP ===")
    print("POOL", POOL, "exists", ONESHOT_SRC.exists())
    rc = pool_check()
    if rc != 0:
        return rc
    total_bars = sum(b for _, b, _, _ in FULL_SECTIONS)
    print("BPM", BPM, "BAR_S", round(BAR_S, 4), "total bars", total_bars,
          "est dur", round(total_bars * BAR_S, 1))
    errors: list[str] = []
    shots = ensure_shots()
    mixes = []
    metas = []
    for i, (name, bars, mode, slot) in enumerate(FULL_SECTIONS):
        path, meta = render_section(i, name, bars, mode, slot, shots)
        mixes.append(path)
        metas.append(meta)

    for dest in (MP3_WORKSPACE, MP3_EXPORTS):
        dest.parent.mkdir(parents=True, exist_ok=True)
    dur = bounce_mp3(mixes, MP3_WORKSPACE)
    if MP3_EXPORTS.resolve() != MP3_WORKSPACE.resolve():
        shutil.copy2(MP3_WORKSPACE, MP3_EXPORTS)
        print("copied exports", MP3_EXPORTS)

    lufs = measure_lufs(MP3_WORKSPACE)
    if lufs.get("I") is not None and (lufs["I"] < -9.5 or lufs["I"] > -7.5):
        print("LUFS out of band — second-pass loudnorm")
        tmp = OUT / "_tholin_remaster.wav"
        af = "loudnorm=I=-8.5:TP=-1.0:LRA=8,alimiter=limit=0.891:attack=1:release=50:level=disabled"
        subprocess.run([FFMPEG, "-y", "-i", str(MP3_WORKSPACE), "-af", af, str(tmp)],
                       check=True, capture_output=True)
        subprocess.run(
            [FFMPEG, "-y", "-i", str(tmp), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3_WORKSPACE)],
            check=True, capture_output=True,
        )
        if MP3_EXPORTS.resolve() != MP3_WORKSPACE.resolve():
            shutil.copy2(MP3_WORKSPACE, MP3_EXPORTS)
        lufs = measure_lufs(MP3_WORKSPACE)

    mid_delta = measure_mid_bloom(MP3_WORKSPACE)
    write_notes(dur, metas, lufs, shots, errors, mid_delta=mid_delta)

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
    try:
        shutil.copy2(Path(__file__).resolve(), Path("/workspace/exports/build_tholin_162.py"))
    except Exception:
        pass

    print("DONE", MP3_WORKSPACE, "I=", lufs.get("I"), "TP=", lufs.get("TP"),
          "LRA=", lufs.get("LRA"), "dur=", round(dur, 1),
          "mid_delta=", mid_delta.get("delta_open_minus_mute"),
          "harsh_under=", mid_delta.get("harsh_under_mids"))
    if errors:
        print("ERRORS", errors)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if "--render" in argv or "--skip-ableton" in argv:
        return render_full()
    if "--pool-check" in argv:
        return pool_check()
    if not argv:
        return render_full()
    return pool_check()


if __name__ == "__main__":
    raise SystemExit(main())
