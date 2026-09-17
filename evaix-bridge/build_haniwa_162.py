# -*- coding: utf-8 -*-
"""EvAIx Haniwa Vestiges slots 05–08 @ 162 BPM F major — FULL RENDER.

Figment v2 PASS unlock · Pneumatix tribal UP · mid-bloom acid (700Hz–3k).
Doctrine: plateaus 16–32 · mute staircase · new family every slot
Tension = filter + mute + ride/kick — no festival drops · no gabber spine
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
KEY = "F"

_HERE = Path(__file__).resolve().parent
_POOL_CANDIDATES = [
    Path("/workspace/exports/haniwa-pool"),
    Path("/workspace/samples/haniwa-162"),
    _HERE / "samples" / "haniwa-162",
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\haniwa-162"),
]
POOL = next((p for p in _POOL_CANDIDATES if (p / "oneshots").exists()), _POOL_CANDIDATES[0])
ONESHOT_SRC = POOL / "oneshots"

OUT = Path("/workspace/samples/haniwa-162-render") if Path("/workspace").exists() else (
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\haniwa-162-render")
)
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"; ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_DIR = OUT / "sections"; SECTION_DIR.mkdir(parents=True, exist_ok=True)

MP3_NAME = "EvAIx_Haniwa_162.mp3"
MP3_WORKSPACE = Path("/workspace") / MP3_NAME if Path("/workspace").exists() else OUT / MP3_NAME
MP3_EXPORTS = Path("/workspace/exports") / MP3_NAME if Path("/workspace/exports").exists() else OUT / MP3_NAME
MP3_DOWNLOADS = Path(r"C:\Users\Gebruiker\Downloads") / MP3_NAME
NOTES_PATH = (
    Path("/workspace/exports/EvAIx_Haniwa_162_NOTES.md")
    if Path("/workspace/exports").exists()
    else OUT / "EvAIx_Haniwa_162_NOTES.md"
)
NOTES_WORKSPACE = Path("/workspace/EvAIx_Haniwa_162_NOTES.md") if Path("/workspace").exists() else NOTES_PATH
BRIDGE_COPY = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\build_haniwa_162.py")
MID_JSON = Path("/workspace/exports/_haniwa_mid_bloom.json") if Path("/workspace/exports").exists() else OUT / "_haniwa_mid_bloom.json"

# Gains — Pneumatix UP: tribal perc louder than Figment; quiet acoustic tops
KICK_G = 1.40
BASS_G = KICK_G * (10 ** (-8.0 / 20.0))
HATS_G, OH_G, RIDE_G, PERC_G = 0.12, 0.10, 0.16, 0.28  # perc UP vs Figment 0.18
ACID_G, MG_G, ATM_G, PAD_G, FX_G = 0.34, 0.15, 0.20, 0.18, 0.11
TUBE_GAIN = 1.55
HAAS_W, HAAS_MS = 0.18, 7.0
ACID_HPF_HZ = 160.0
ACID_PRESENCE_HZ = 2200.0
ACID_PRESENCE_DB_OPEN = 3.4
ACID_PRESENCE_DB_MUTE = -4.0

# F major (dark filters) — settle −1 semitone from Figment F#
F_MAJ = np.array([
    87.31,   # F2
    98.00,   # G2
    110.00,  # A2
    116.54,  # Bb2
    130.81,  # C3
    146.83,  # D3
    174.61,  # F3
    196.00,  # G3
], dtype=np.float64)
F_LOW = F_MAJ / 2.0  # MG LPF −8va
F_PAD = np.array([87.31, 130.81, 174.61, 220.00], dtype=np.float64)  # F C F A

# Template A 7′ chapter — chapter-relative times (0:00–7:00)
FULL_SECTIONS = [
    # 05 Haniwa_Intro 0:00–2:00 E2 — brighter atm LFO, no kick
    ("Haniwa_Intro_a", 40, "intro_atm", "05"),
    ("Haniwa_Intro_b", 41, "intro_open", "05"),
    # 06 Haniwa_Build 2:00–4:00 E4 — +kick · sparse CH · tribal LS7
    ("Haniwa_Build_kick", 40, "build_kick", "06"),
    ("Haniwa_Build_tribal", 41, "build_tribal", "06"),
    # 07 Haniwa_Drop 4:00–6:00 E8 — dual acid muted→open mid-bloom
    ("Haniwa_Drop_mute", 27, "drop_muted", "07"),
    ("Haniwa_Drop_open", 40, "drop_open", "07"),
    ("Haniwa_Drop_close", 14, "drop_close", "07"),
    # 08 Haniwa_Out 6:00–7:00 E5 — kill tribal · acid down → E
    ("Haniwa_Out", 40, "outro", "08"),
]

SLOTS = {
    "05": {
        "id": "Haniwa_Intro", "time": "0:00–2:00", "dur_min": 2.0, "energy": 2,
        "kick": False, "dir": "05_intro",
        "bd": ["bd_sinkick_veiled.wav", "bd_f01_organic.wav"],
        "hh": ["hh_7c_noiseish.wav"],
        "perc": [],
        "atm": [
            "atm_perclp_1.wav", "atm_perclp_2.wav", "atm_perclp_3.wav",
            "atm_synlp_bright.wav", "atm_voice_1_pad.wav", "atm_voice_7_grain.wav",
        ],
        "sfx": ["sfx_noise_mi.wav", "sfx_noise_short.wav", "sfx_2_mi.wav"],
        "ride": [],
        "note": "brighter atm LFO · settle −1 from F# · NO KICK",
    },
    "06": {
        "id": "Haniwa_Build", "time": "2:00–4:00", "dur_min": 2.0, "energy": 4,
        "kick": True, "dir": "06_build",
        "bd": ["bd_f01_organic.wav", "bd_f02_dry.wav", "bd_f03_groove.wav"],
        "hh": ["hh_5c_sparse.wav", "hh_1c_mi.wav", "hh_7c_noiseish.wav", "hh_5o_bright.wav"],
        "perc": [
            "perc_cowbel.wav", "perc_metal_0.wav", "perc_metal_1.wav",
            "perc_clank_rev.wav", "perc_synperc.wav", "perc_zap.wav", "perc_rim2.wav",
        ],
        "atm": [], "sfx": ["sfx_2_mi.wav"], "ride": [],
        "note": "+kick · sparse CH · tribal wood/clank poly LS7",
    },
    "07": {
        "id": "Haniwa_Drop", "time": "4:00–6:00", "dur_min": 2.0, "energy": 8,
        "kick": True, "dir": "07_drop",
        "bd": ["bd_f03_groove.wav", "bd_f04_peak.wav", "bd_f05_hard.wav", "bd_kick_ready_morph.wav"],
        "hh": ["hh_5o_bright.wav", "hh_1o_mi.wav", "hh_7o_peak.wav"],
        "perc": [
            "perc_metal_0.wav", "perc_metal_1.wav", "perc_metal_2.wav", "perc_metal_3.wav",
            "perc_cowbel.wav", "perc_synperc.wav", "perc_zap.wav", "perc_clank_rev.wav",
            "perc_junk_crushed.wav", "perc_rim2.wav", "perc_kb_clap.wav", "perc_sd1_accent.wav",
        ],
        "atm": ["atm_synlp_bright.wav"], "sfx": [],
        "ride": ["ride_metallic_synperc.wav", "ride_zap_tip.wav"],
        "note": "Full dual acid + hats + tribal + ride · Res spikes 4/8/12/16",
    },
    "08": {
        "id": "Haniwa_Out", "time": "6:00–7:00", "dur_min": 1.0, "energy": 5,
        "kick": True, "dir": "08_out",
        "bd": ["bd_f06_thin_out.wav", "bd_sinkick_veiled.wav"],
        "hh": [], "perc": [],
        "atm": ["atm_perclp_1.wav", "atm_perclp_3.wav", "atm_voice_7_grain.wav"],
        "sfx": ["sfx_3_mi_out.wav", "sfx_noise_short.wav"], "ride": [],
        "note": "Kill tribal · acid filter down → E handoff",
    },
}

FIGMENT_BLACKLIST = {
    "014_BD-15.wav", "012_BD-13.wav", "016_BD-17.wav", "018_BD-19.wav",
    "019_BD-20.wav", "020_BD-21.wav", "010_BD-11.wav", "008_BD-9.wav",
    "054_HH-1C.wav", "056_HH-2C.wav", "058_HH-3C.wav", "062_HH-5C.wav",
    "066_HH-7C.wav", "045_Rim-1.wav", "047_Rim-3.wav", "048_Clap-1.wav",
    "052_Clap-5.wav", "076_Tom-1.wav", "078_Tom-3.wav", "092_JunkPerc.wav",
    "102_SFX-1.wav", "104_SFX-3.wav", "200_Noise.wav", "068_Ride-1.wav",
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


def prepare_bd(name: str, drive: float = 2.15) -> np.ndarray:
    src = ONESHOT_SRC / name
    if not src.exists():
        raise FileNotFoundError(src)
    raw = read_wav(src)
    y = one_pole(raw, 36.0, mode="hpf")
    y = one_pole(y, 4500.0, mode="lpf")
    y = peaking_eq(y, 110.0, 1.6, q=0.85)
    y = tanh_drive(y, drive)
    y = mild_compress(y, thr=0.42, ratio=1.40)
    y = one_pole(y, 9000.0, mode="lpf")
    peak = float(np.max(np.abs(y))) + 1e-12
    return y / peak * 0.95


def synth_sub_bass(root_hz: float = 43.65) -> np.ndarray:
    """F1 fund (~43.65) for mono kick pocket."""
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    env = np.exp(-t / 0.11)
    pitch = root_hz * (1.0 + 1.5 * np.exp(-t / 0.015))
    phase = np.cumsum(2 * np.pi * pitch / SR)
    return mild_compress(np.sin(phase) * env * 0.9, thr=0.48, ratio=1.35)


def synth_drift_pad(n: int, open_amt: float = 0.25, seed: int = 42) -> np.ndarray:
    """Brighter LFO atm pad — F major dark, OB LPF character (Haniwa brighter than Figment)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    pad = np.zeros(n)
    for i, hz in enumerate(F_PAD):
        det = 1.0 + rng.uniform(-0.004, 0.004)
        phase = 2 * np.pi * hz * det * t
        saw = 2.0 * (np.mod(phase / (2 * np.pi), 1.0) - 0.5)
        sine = np.sin(phase)
        amp = 0.24 if i < 2 else 0.15
        pad += amp * (0.50 * sine + 0.50 * saw * 0.40)
    # brighter LFO breathe than Figment
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.075 * t)
    lfo2 = 0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t + 0.7)
    pad *= 0.50 + 0.35 * lfo + 0.15 * lfo2
    cut = 550.0 + 4800.0 * float(np.clip(open_amt, 0.05, 1.0))
    pad = one_pole(pad, 90.0, mode="hpf")
    pad = one_pole(pad, cut, mode="lpf")
    pad = one_pole(pad, 5800.0, mode="lpf")
    return pad * 0.55


def synth_atm_haze(n: int, seed: int = 77, bright: float = 0.3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, n)
    x = one_pole(x, 320.0, mode="hpf")
    x = one_pole(x, 1800.0 + 1600.0 * bright, mode="lpf")
    t = np.arange(n) / SR
    x *= 0.40 + 0.60 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t))
    return x * 0.24


def acid_303_note(freq: float, dur_s: float, accent: bool = False,
                  cutoff_open: float = 0.35, res_boost: float = 0.0) -> np.ndarray:
    """Acid LPF 303 saw — Mental Tribe mid bloom when open (700Hz–3kHz). Figment v2 lesson."""
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

    # BD family rotation F01–F06 + veiled + morph
    bd_map = {
        "bd_veiled": ("bd_sinkick_veiled.wav", 1.85),
        "bd_f01": ("bd_f01_organic.wav", 2.00),
        "bd_f02": ("bd_f02_dry.wav", 2.08),
        "bd_f03": ("bd_f03_groove.wav", 2.15),
        "bd_f04": ("bd_f04_peak.wav", 2.22),
        "bd_f05": ("bd_f05_hard.wav", 2.28),
        "bd_f06": ("bd_f06_thin_out.wav", 1.95),
        "bd_morph": ("bd_kick_ready_morph.wav", 2.10),
    }
    for key, (name, drive) in bd_map.items():
        shots[key] = prepare_bd(name, drive=drive)
        write_mono(ONESHOT / f"{key}_{name}", shots[key], 0.94)
        used.append(name)
    shots["bd_thin"] = one_pole(shots["bd_f06"], 110.0, mode="lpf") * 0.72

    # Hats
    for key, name, drive, hpf, lpf in [
        ("hh7c", "hh_7c_noiseish.wav", 0.95, 4000, 11500),
        ("hh5c", "hh_5c_sparse.wav", 0.95, 4200, 11500),
        ("hh1c", "hh_1c_mi.wav", 1.0, 4000, 11500),
        ("hh5o", "hh_5o_bright.wav", 1.0, 3200, 10500),
        ("hh1o", "hh_1o_mi.wav", 1.0, 3200, 10500),
        ("hh7o", "hh_7o_peak.wav", 1.05, 3000, 10000),
    ]:
        shots[key] = load_shot(name, drive, hpf, lpf)
        used.append(name)

    # Tribal perc (Pneumatix UP)
    for key, name, drive, hpf, lpf in [
        ("cowbel", "perc_cowbel.wav", 1.20, 400, 7000),
        ("metal0", "perc_metal_0.wav", 1.25, 350, 6500),
        ("metal1", "perc_metal_1.wav", 1.25, 350, 6500),
        ("metal2", "perc_metal_2.wav", 1.30, 300, 6000),
        ("metal3", "perc_metal_3.wav", 1.30, 280, 6000),
        ("clank", "perc_clank_rev.wav", 1.35, 200, 5500),
        ("synperc", "perc_synperc.wav", 1.15, 500, 7500),
        ("zap", "perc_zap.wav", 1.20, 600, 8000),
        ("rim2", "perc_rim2.wav", 1.15, 900, 7000),
        ("junk", "perc_junk_crushed.wav", 1.30, 250, 5500),
        ("clap", "perc_kb_clap.wav", 1.10, 700, 8000),
        ("sd1", "perc_sd1_accent.wav", 1.15, 800, 7500),  # sparse accent ONLY
    ]:
        shots[key] = load_shot(name, drive, hpf, lpf)
        used.append(name)

    # Metallic rides (≠ Figment dark Ride-1)
    shots["ride_met"] = load_shot("ride_metallic_synperc.wav", 0.95, 2200, 10000)
    shots["ride_zap"] = load_shot("ride_zap_tip.wav", 0.95, 2500, 10500)
    used.extend(["ride_metallic_synperc.wav", "ride_zap_tip.wav"])

    # Atm / SFX beds as loops (place periodically)
    for key, name in [
        ("atm_p1", "atm_perclp_1.wav"), ("atm_p2", "atm_perclp_2.wav"), ("atm_p3", "atm_perclp_3.wav"),
        ("atm_syn", "atm_synlp_bright.wav"),
        ("atm_v1", "atm_voice_1_pad.wav"), ("atm_v7", "atm_voice_7_grain.wav"),
        ("sfx_nmi", "sfx_noise_mi.wav"), ("sfx_nsh", "sfx_noise_short.wav"),
        ("sfx_2", "sfx_2_mi.wav"), ("sfx_3", "sfx_3_mi_out.wav"),
    ]:
        y = read_wav(ONESHOT_SRC / name)
        y = one_pole(y, 80.0, mode="hpf")
        y = one_pole(y, 7500.0, mode="lpf")
        peak = float(np.max(np.abs(y))) + 1e-12
        shots[key] = y / peak * 0.85
        used.append(name)

    for k in ("hh7c", "hh5c", "hh1c", "hh5o", "hh1o", "hh7o", "ride_met", "ride_zap"):
        shots[k] = one_pole(shots[k], 9500.0, mode="lpf") * 0.92

    shots["bass"] = synth_sub_bass(43.65)
    write_mono(ONESHOT / "bass_sub_F.wav", shots["bass"], 0.9)
    shots["used"] = sorted(set(used))
    print("shots ready", len(shots["used"]))
    return shots


def kit_for_mode(mode: str, slot: str, shots: dict) -> dict:
    bd_pick = {
        "intro_atm": shots["bd_veiled"],
        "intro_open": shots["bd_veiled"],
        "build_kick": shots["bd_f02"],
        "build_tribal": shots["bd_f03"],
        "drop_muted": shots["bd_f04"],
        "drop_open": shots["bd_f05"],
        "drop_close": shots["bd_f04"],
        "outro": shots["bd_thin"],
    }
    hat_pick = {
        "intro_atm": shots["hh7c"], "intro_open": shots["hh7c"],
        "build_kick": shots["hh5c"], "build_tribal": shots["hh1c"],
        "drop_muted": shots["hh5o"], "drop_open": shots["hh7o"],
        "drop_close": shots["hh5o"], "outro": shots["hh7c"],
    }
    # Pneumatix tribal denser on build_tribal / drop
    gains = {
        "intro_atm":  dict(kick=0.0, bass=0.0, hats=0.06, oh=0.0, ride=0.0, perc=0.0,
                           acid=0.0, mg=0.0, atm=1.0, pad=1.0, fx=0.40, acid_open=0.12),
        "intro_open": dict(kick=0.0, bass=0.0, hats=0.10, oh=0.0, ride=0.0, perc=0.0,
                           acid=0.0, mg=0.0, atm=0.90, pad=1.05, fx=0.35, acid_open=0.18),
        "build_kick": dict(kick=0.90, bass=0.45, hats=0.32, oh=0.06, ride=0.0, perc=0.22,
                           acid=0.0, mg=0.0, atm=0.30, pad=0.55, fx=0.18, acid_open=0.20),
        "build_tribal": dict(kick=0.95, bass=0.55, hats=0.38, oh=0.12, ride=0.0, perc=0.70,
                             acid=0.0, mg=0.0, atm=0.18, pad=0.40, fx=0.22, acid_open=0.25),
        "drop_muted": dict(kick=1.0, bass=0.85, hats=0.50, oh=0.25, ride=0.55, perc=0.75,
                           acid=0.45, mg=0.30, atm=0.10, pad=0.28, fx=0.20, acid_open=0.18),
        "drop_open":  dict(kick=1.02, bass=0.92, hats=0.60, oh=0.35, ride=0.90, perc=0.95,
                           acid=1.18, mg=0.72, atm=0.08, pad=0.20, fx=0.28, acid_open=0.92),
        "drop_close": dict(kick=0.95, bass=0.70, hats=0.28, oh=0.08, ride=0.15, perc=0.25,
                           acid=0.48, mg=0.30, atm=0.22, pad=0.40, fx=0.28, acid_open=0.28),
        "outro":      dict(kick=0.65, bass=0.30, hats=0.08, oh=0.0, ride=0.0, perc=0.0,
                           acid=0.18, mg=0.12, atm=0.70, pad=0.75, fx=0.45, acid_open=0.12),
    }
    stories = {
        "intro_atm":  "Slot05 Intro — PercLP/SynLP brighter LFO; settle −1st from F#; NO KICK",
        "intro_open": "Slot05 Intro — voice grain + noise haze; LFO brighten; still no kick",
        "build_kick": "Slot06 Build — kick F02 lands 1/5/9/13; sparse HH5C; restraint",
        "build_tribal": "Slot06 Build — cowbel/metal poly LS7; synperc/zap; ride held out",
        "drop_muted": "Slot07 Drop — dual acid MUTED + tribal + metallic ride tease",
        "drop_open":  "Slot07 Drop — acid mid-bloom open; Res spikes 4/8/12/16; full tribal+ride",
        "drop_close": "Slot07→08 — strip ride/OH; acid closes toward Out",
        "outro":      "Slot08 Out — kill tribal; acid filter down; thin BD → E handoff",
    }
    kick_on = {
        "intro_atm": [], "intro_open": [],
        "build_kick": [0, 4, 8, 12], "build_tribal": [0, 4, 8, 12],
        "drop_muted": [0, 4, 8, 12], "drop_open": [0, 4, 8, 12],
        "drop_close": [0, 4, 8, 12], "outro": [0, 8],
    }
    bd_name = {
        "intro_atm": "veiled sinkick", "intro_open": "veiled sinkick",
        "build_kick": "bd_f02_dry", "build_tribal": "bd_f03_groove",
        "drop_muted": "bd_f04_peak", "drop_open": "bd_f05_hard",
        "drop_close": "bd_f04_peak", "outro": "bd_f06_thin",
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
    seed = 0xA162 + idx * 23
    rng = np.random.default_rng(seed)

    # optional kick mute plateau mid-drop (4–8 bars) — free-party gesture, not EDM
    mute_kick_bars = set()
    if mode == "drop_muted" and bars >= 16:
        mute_kick_bars = set(range(12, 16))  # brief mute before open

    for bar in range(bars):
        kick_steps = [] if bar in mute_kick_bars else kit["kick_steps"]
        for st in kick_steps:
            beat = bar * 4 + st / 4.0
            place(trk_k, kit["kick"], beat, 1.0)
            place(trk_b, shots["bass"], beat, 1.0)

        if g["hats"] > 0.05:
            dens = 0.30 if mode.startswith("intro") else (
                0.50 if "build" in mode else (0.80 if mode == "drop_open" else 0.65)
            )
            for s in hat_poly15(1, dens=dens):
                if s < 16:
                    beat = bar * 4 + s / 4.0
                    place(trk_h, kit["hat"], beat, 0.75 if s % 4 == 2 else 0.55)

        # open hats on drop / late build
        if g["oh"] > 0.05 and bar % 2 == 1:
            place(trk_oh, shots["hh5o"] if mode != "drop_open" else shots["hh7o"],
                  bar * 4 + 1.5, 0.55)

        # metallic ride 8ths — Drop only (held out of Build)
        if g["ride"] > 0.05:
            ride_samp = shots["ride_met"] if bar % 2 == 0 else shots["ride_zap"]
            for eighth in range(8):
                beat = bar * 4 + eighth * 0.5
                place(trk_ride, ride_samp, beat, 0.55 if eighth % 2 == 0 else 0.40)

        # tribal poly LS7 — Pneumatix wood/clank (Build tribal + Drop); OFF on Out
        if g["perc"] > 0.08:
            dens = 0.55 if mode == "build_kick" else (0.85 if mode in ("build_tribal", "drop_open") else 0.70)
            tribal_bank = [
                shots["cowbel"], shots["metal0"], shots["metal1"], shots["clank"],
                shots["synperc"], shots["zap"], shots["rim2"],
            ]
            if mode in ("drop_muted", "drop_open"):
                tribal_bank += [shots["metal2"], shots["metal3"], shots["junk"]]
            for s in perc_poly7(1, dens=dens):
                if s < 16:
                    beat = bar * 4 + s / 4.0
                    samp = tribal_bank[s % len(tribal_bank)]
                    place(trk_p, samp, beat, 0.60 if s % 7 == 0 else 0.48)

        # SD1 / clap sparse accent ONLY on drop_open peaks — never gabber grid
        if mode == "drop_open" and bar % 8 == 7:
            place(trk_p, shots["clap"], bar * 4 + 1.0, 0.42)
        if mode == "drop_open" and bar % 16 == 15:
            place(trk_p, shots["sd1"], bar * 4 + 2.0, 0.38)

    # --- atm + brighter pad ---
    pad_open = {
        "intro_atm": 0.28, "intro_open": 0.55, "build_kick": 0.48, "build_tribal": 0.42,
        "drop_muted": 0.35, "drop_open": 0.30, "drop_close": 0.45, "outro": 0.60,
    }[mode]
    if g["pad"] > 0.01:
        trk_pad += synth_drift_pad(N, open_amt=pad_open, seed=seed)
    if g["atm"] > 0.01:
        bright = 0.55 if mode.startswith("intro") else 0.30
        trk_atm += synth_atm_haze(N, seed=seed + 3, bright=bright)
        # place pool atm grains
        atm_bank = {
            "intro_atm": [shots["atm_p1"], shots["atm_p2"], shots["atm_syn"]],
            "intro_open": [shots["atm_p3"], shots["atm_syn"], shots["atm_v1"], shots["atm_v7"]],
            "build_kick": [shots["atm_p1"]],
            "build_tribal": [shots["atm_syn"]],
            "drop_muted": [shots["atm_syn"]],
            "drop_open": [shots["atm_syn"]],
            "drop_close": [shots["atm_p3"], shots["atm_v7"]],
            "outro": [shots["atm_p1"], shots["atm_p3"], shots["atm_v7"]],
        }[mode]
        for bar in range(0, bars, 2):
            samp = atm_bank[bar % len(atm_bank)]
            place(trk_atm, samp, bar * 4 + rng.uniform(0, 0.5), 0.35)
        sfx_bank = {
            "intro_atm": [shots["sfx_nmi"], shots["sfx_nsh"]],
            "intro_open": [shots["sfx_nsh"], shots["sfx_2"], shots["sfx_nmi"]],
            "build_kick": [shots["sfx_2"]],
            "build_tribal": [shots["sfx_2"]],
            "drop_muted": [],
            "drop_open": [],
            "drop_close": [shots["sfx_nsh"]],
            "outro": [shots["sfx_3"], shots["sfx_nsh"]],
        }[mode]
        for bar in range(0, bars, 3):
            if sfx_bank:
                place(trk_fx, sfx_bank[bar % len(sfx_bank)],
                      bar * 4 + rng.uniform(0, 1.2), 0.38)

    # --- dual acid LS13 ---
    acid_open = float(g["acid_open"])
    dens = {
        "intro_atm": 0.0, "intro_open": 0.0, "build_kick": 0.0, "build_tribal": 0.0,
        "drop_muted": 0.58, "drop_open": 0.88, "drop_close": 0.42, "outro": 0.22,
    }[mode]
    if dens > 0.01 and (g["acid"] > 0.05 or g["mg"] > 0.05):
        for step, note_i, accent, dur_steps in acid_poly13(bars, dens, seed):
            # Res spikes bars 4/8/12/16 within Drop open
            bar_i = step // 16
            res = 0.0
            if mode == "drop_open":
                local_bar = (bar_i % 16) + 1
                if local_bar in (4, 8, 12, 16):
                    res = 0.85
                elif accent:
                    res = 0.45
            freq = float(F_MAJ[note_i % len(F_MAJ)])
            note = acid_303_note(freq, dur_steps * STEP_S, accent=accent,
                                 cutoff_open=acid_open, res_boost=res)
            place(trk_acid, note, step / 4.0, 1.15 if accent else 0.88)
            mg = mg_lpf_note(float(F_LOW[note_i % len(F_LOW)]), dur_steps * STEP_S * 1.1,
                             accent=accent, cutoff_open=acid_open * 0.88)
            place(trk_mg, mg, step / 4.0, 0.85)

    # gains
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
        "intro_atm": (700.0, 2200.0),    # brighter than Figment intro
        "intro_open": (1600.0, 4200.0),
        "build_kick": (2800.0, 4800.0),
        "build_tribal": (3400.0, 5800.0),
        "drop_muted": (2200.0, 3800.0),
        "drop_open": (4500.0, 9500.0),
        "drop_close": (5000.0, 2800.0),
        "outro": (3200.0, 1600.0),
    }
    c0, c1 = cut_map[mode]
    mono_bed = apply_moving_lpf(mono_bed, c0, c1)
    hats_atm = apply_moving_lpf(hats_atm, c0, c1)
    if mode == "drop_open":
        acid_bus = apply_moving_lpf(acid_bus, 5200.0, 9000.0)
        fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, c1 * 1.05)
    elif mode == "drop_muted":
        acid_bus = apply_moving_lpf(acid_bus, 900.0, 1600.0)
        fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, c1 * 1.05)
    else:
        acid_bus = apply_moving_lpf(acid_bus, c0 * 0.85, c1 * 0.95)
        fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, c1 * 1.05)

    mono_bed = valve_force(mono_bed, TUBE_GAIN * 0.80)
    hats_atm = valve_force(hats_atm, TUBE_GAIN * 0.75)
    acid_bus = valve_force(acid_bus, TUBE_GAIN * 0.90)
    fx_bus = valve_force(fx_bus, TUBE_GAIN * 0.95)
    mono_bed = one_pole(mono_bed, 11000.0, mode="lpf")
    hats_atm = one_pole(hats_atm, 9500.0, mode="lpf")
    acid_bus = one_pole(acid_bus, 5600.0 if mode == "drop_open" else 7500.0, mode="lpf")
    fx_bus = one_pole(fx_bus, 8500.0, mode="lpf")

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
    concat_list = OUT / "_haniwa_concat.txt"
    raw = OUT / "_haniwa_raw.wav"
    mastered = OUT / "_haniwa_master.wav"
    with concat_list.open("w", encoding="utf-8") as f:
        for p in mixes:
            f.write(f"file '{p.as_posix()}'\n")
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw)],
        check=True, capture_output=True,
    )
    # PA master + Drop_open surgical mid bloom (Figment v2 recipe) via asplit windows later if needed
    af = (
        "highpass=f=26:poles=2,"
        "lowshelf=f=90:t=q:w=0.7:g=1.6,"
        "equalizer=f=48:t=q:w=1.1:g=2.0,"   # F1 pocket
        "equalizer=f=72:t=q:w=1.4:g=-1.1,"
        "equalizer=f=380:t=q:w=1.0:g=-0.8,"
        "equalizer=f=900:t=q:w=1.0:g=0.8,"
        "equalizer=f=1800:t=q:w=1.0:g=1.4,"
        "equalizer=f=2400:t=q:w=1.1:g=1.6,"
        "equalizer=f=2800:t=q:w=1.0:g=1.0,"
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

    # Surgical Drop_open mid boost window (~240–339s) — Figment v2 lesson
    # Timeline: Intro 81 bars ~120s, Build 81 ~120s → Drop starts ~240s
    # Drop_mute 27 bars ~40s → open starts ~280s, open 40 bars ~59s → ~339s
    surg = OUT / "_haniwa_surg.wav"
    # enable=between(t,280,339) peaking on mid
    af2 = (
        "equalizer=f=900:t=q:w=1.0:g=1.8:enable='between(t,280,339)',"
        "equalizer=f=1800:t=q:w=1.0:g=2.8:enable='between(t,280,339)',"
        "equalizer=f=2400:t=q:w=1.1:g=3.0:enable='between(t,280,339)',"
        "equalizer=f=2800:t=q:w=1.0:g=2.2:enable='between(t,280,339)',"
        "equalizer=f=5200:t=q:w=1.2:g=-2.0:enable='between(t,280,339)',"
        "loudnorm=I=-8.5:TP=-1.0:LRA=7,"
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
    raw = OUT / "_haniwa_analyze.f32"
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
        "open_low_note": f"open low-rel={open_low:.2f} dB (mute low-rel={mute_low:.2f})",
    }
    print("MID-BLOOM mute_rel", out["mute_mid_rel"], "open_rel", out["open_mid_rel"],
          "delta", out["delta_open_minus_mute"], out["open_low_note"])
    MID_JSON.parent.mkdir(parents=True, exist_ok=True)
    MID_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    (OUT / "_haniwa_mid_bloom.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def write_notes(dur: float, metas: list, lufs: dict, shots: dict, errors: list,
                mid_delta: dict | None = None):
    t0 = 0.0
    lines = [
        "# EvAIx Haniwa — Vestiges slots 05–08 @ 162 F",
        "",
        f"**MP3:** `{MP3_NAME}`",
        f"- Downloads: `C:\\\\Users\\\\Gebruiker\\\\Downloads\\\\{MP3_NAME}`",
        f"- Workspace: `/workspace/{MP3_NAME}`",
        f"- Exports: `/workspace/exports/{MP3_NAME}`",
        f"- Script: `/workspace/build_haniwa_162.py`",
        f"- Bridge: `C:\\\\Users\\\\Gebruiker\\\\ableton-mcp\\\\evaix-bridge\\\\build_haniwa_162.py`",
        f"- Pool: `/workspace/exports/haniwa-pool/oneshots/` (38 WAVs)",
        "",
        f"Duration: **{dur:.2f} s** (~{dur/60:.2f} min) · BPM **{BPM:.0f}** · Key **F major** (dark filters)",
        "",
        "## Measured loudness",
        f"- **I** = {lufs.get('I')} LUFS (target −8…−9)",
        f"- **TP** = {lufs.get('TP')} dB (target ≤ −1.0 dBTP)",
        f"- **LRA** = {lufs.get('LRA')} LU",
        "",
        "## Mid-bloom (Figment v2 lesson applied)",
        "- Acid muted→open must show **700Hz–3k rise** (not LF-only).",
        "- Recipe: HPF acid ~160 Hz · presence 1.8–2.8 kHz · sat AFTER EQ · tame 3–6 kHz.",
        "- Drop_mute open≈0.18 heavy LPF; Drop_open≈0.92 cutoff+presence + bus peaking.",
        "- Surgical window EQ on Drop_open 280–339s: +1.8@900 / +2.8@1800 / +3.0@2400 / +2.2@2800 / −2.0@5200.",
        "- Res spikes bars 4/8/12/16 on Drop_open.",
        "",
    ]
    if mid_delta:
        lines += [
            "## Mid-band open vs mute (measured)",
            f"- Mute mid rel (700Hz–3k vs full): **{mid_delta.get('mute_mid_rel')}** dB",
            f"- Open mid rel (700Hz–3k vs full): **{mid_delta.get('open_mid_rel')}** dB",
            f"- Delta open−mute: **{mid_delta.get('delta_open_minus_mute')}** dB (target: clear rise)",
            f"- Abs mid rise: **{mid_delta.get('abs_mid_rise_db')}** dB",
            f"- Low-band: {mid_delta.get('open_low_note', 'n/a')}",
            f"- Harsh 3–6k open rel: {mid_delta.get('open_harsh_rel')} (mute {mid_delta.get('mute_harsh_rel')})",
            "",
        ]
    lines += [
        "## Slot map (skeleton-locked · chapter-relative)",
        "| Slot | ID | Time | Energy | Character |",
        "|------|-----|------|--------|-----------|",
        "| 05 | Haniwa_Intro | 0:00–2:00 | 2 | Brighter atm LFO · settle −1 from F# · no kick |",
        "| 06 | Haniwa_Build | 2:00–4:00 | 4 | +kick · sparse CH · tribal wood/clank poly LS7 |",
        "| 07 | Haniwa_Drop | 4:00–6:00 | 8 | Dual acid mid-bloom + hats + tribal + metallic ride |",
        "| 08 | Haniwa_Out | 6:00–7:00 | 5 | Kill tribal · acid filter down → E handoff |",
        "",
        "## Mute staircase",
        "| Bars (chapter) | Action |",
        "|----------------|--------|",
        "| 1–16 | PercLP/SynLP atm only (05) |",
        "| 17–32 | +voice grain · short noise · LFO brighten |",
        "| 33–48 | +kick F02 · sparse HH5C (06) |",
        "| 49–64 | +cowbel/metal LS7 |",
        "| 65–80 | +synperc/zap · ride still out |",
        "| 81–96 | dual acid muted (07) |",
        "| 97–128 | acid opens mid-bloom · full tribal · metallic ride · res spikes |",
        "| 129–end | kill tribal · acid down · thin BD → E (08) |",
        "",
        "## Poly doctrine",
        "- Acid **Last Step 13** vs kick **16** vs hats **15** vs perc **7**",
        "- Kick grid: steps 0/4/8/12 (Electribe 1/5/9/13)",
        "- Dual acid: Acid LPF 303 saw + MG LPF square −8va · F major",
        "- SD1 / clap = sparse accent only — **no gabber spine**",
        "",
        "## Sample families (pool WAVs used)",
        "- Slot 05: atm_perclp_1/2/3 · atm_synlp_bright · atm_voice_1/7 · sfx_noise_mi/short · sfx_2_mi · hh_7c_noiseish (BD held)",
        "- Slot 06: bd_f01→f02→f03 · hh_5c/1c/7c/5o · perc_cowbel/metal_0–1/clank/synperc/zap/rim2",
        "- Slot 07: bd_f03→f04→f05 · hh_5o/1o/7o · perc_metal_0–3 + cowbel/synperc/zap/clank/junk/rim2 · clap+sd1 accent · ride_metallic_synperc + ride_zap_tip",
        "- Slot 08: bd_f06_thin + sinkick_veiled · atm_perclp_1/3 · atm_voice_7 · sfx_3_mi_out · sfx_noise_short · tribal OFF",
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
        "- Acid: mid-bloom muted→open on Drop, presence 1.8–2.8 kHz, LS13, res spikes 4/8/12/16",
        "- Kick: root-tuned F (~43.65 Hz sub), punch body ~110 Hz, EQ before sat, mono",
        "- Perc: Pneumatix tribal wood/clank UP · poly LS7",
        "- Ride: metallic SynPerc / Zap tip (Drop only) — not Figment dark Ride-1",
        "- Master: mid lift + PA tame 4.5–10 kHz, loudnorm I=-8.5 TP=-1.0",
        "",
        "## Doctrine kept",
        "- Free-party / mental tekno / acidcore — **no commercial EDM drops**",
        "- Pneumatix weight UP · plateaus not festival builds",
        "- New sample family every slot · no Figment factory spine reuse",
        "- Kick/bass mono · Haas only on hats/atm/acid",
        "",
        f"Samples used ({len(shots.get('used', []))}): {shots.get('used', [])}",
        f"Errors: {errors}",
        "Ableton: skipped (--skip-ableton / DSP bounce)",
        "",
        "*EvAIx · Haniwa Vestiges 05–08 · Figment v2 PASS unlock*",
    ]
    text = "\n".join(lines)
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTES_PATH.write_text(text, encoding="utf-8")
    print("NOTES", NOTES_PATH)
    try:
        NOTES_WORKSPACE.write_text(text, encoding="utf-8")
    except Exception as e:
        print("NOTES workspace copy", e)


def all_assigned() -> list[str]:
    names: list[str] = []
    for slot in SLOTS.values():
        for key in ("bd", "hh", "perc", "atm", "sfx", "ride"):
            names.extend(slot[key])
    return sorted(set(names))


def pool_check() -> int:
    print(f"POOL = {POOL}")
    print(f"ONESHOT exists = {ONESHOT_SRC.exists()}")
    if not ONESHOT_SRC.exists():
        print("ERROR: oneshots dir missing", file=sys.stderr)
        return 1
    present = {p.name for p in ONESHOT_SRC.glob("*.wav")}
    assigned = all_assigned()
    missing = [n for n in assigned if n not in present]
    print(f"oneshots on disk: {len(present)}")
    print(f"assigned unique:  {len(assigned)}")
    if missing:
        print("MISSING:", missing)
        return 2
    collisions = [n for n in present if n in FIGMENT_BLACKLIST]
    if collisions:
        print("BLACKLIST HIT:", collisions)
        return 3
    print("OK — pool distinct from Figment blacklist; all slot WAVs present")
    for sid, slot in SLOTS.items():
        print(f"  [{sid}] {slot['id']:16} E{slot['energy']} kick={slot['kick']} — {slot['note']}")
    return 0


def render_full() -> int:
    print("=== EvAIx Haniwa 162 F · mid-bloom · Pneumatix UP ===")
    print("POOL", POOL, "exists", ONESHOT_SRC.exists())
    rc = pool_check()
    if rc != 0:
        return rc
    print("BPM", BPM, "BAR_S", round(BAR_S, 4), "total bars",
          sum(b for _, b, _, _ in FULL_SECTIONS),
          "est dur", round(sum(b for _, b, _, _ in FULL_SECTIONS) * BAR_S, 1))
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
        tmp = OUT / "_haniwa_remaster.wav"
        af = "loudnorm=I=-8.5:TP=-1.0:LRA=7,alimiter=limit=0.891:attack=1:release=50:level=disabled"
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
        shutil.copy2(Path(__file__).resolve(), Path("/workspace/exports/build_haniwa_162.py"))
    except Exception:
        pass

    print("DONE", MP3_WORKSPACE, "I=", lufs.get("I"), "TP=", lufs.get("TP"),
          "LRA=", lufs.get("LRA"), "dur=", round(dur, 1),
          "mid_delta=", mid_delta.get("delta_open_minus_mute"))
    if errors:
        print("ERRORS", errors)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if "--render" in argv or "--skip-ableton" in argv:
        return render_full()
    if "--pool-check" in argv:
        return pool_check()
    # default GO: full render (Architect PASS unlock)
    if not argv:
        return render_full()
    return pool_check()


if __name__ == "__main__":
    raise SystemExit(main())
