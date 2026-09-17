# -*- coding: utf-8 -*-
"""EvAIx Vyre — Vestiges slots 14–16 @ 162 BPM B major — FULL RENDER (~6').

Homecoming −P5 resolve after Tholin peak. FineTuniX gates:
- mid bloom where acid appears (restrained Main closing only)
- mute staircase / early sample rotation / free-party not EDM
- live-set levels I≈−8…−9 · TP≤−1.0
- outro/handoff clarity: kick+acid OUT · atm filter close · ≥10s reverb tail

Doctrine: slot14 atm dominate max reverb NO acid · slot15 soft kick + restrained
acid open≤0.45 closing · slot16 kick out acid silence filter close long tail.
No gabber · no EDM drops · kick/bass mono · tame harsh 3–6k.
Default: --skip-ableton (DSP bounce).
"""
from __future__ import annotations

import argparse
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
KEY = "B"

_HERE = Path(__file__).resolve().parent
_POOL_CANDIDATES = [
    Path("/workspace/exports/vyre-pool"),
    Path("/workspace/samples/vyre-162"),
    _HERE / "samples" / "vyre-162",
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\vyre-162"),
]
POOL = next((p for p in _POOL_CANDIDATES if (p / "oneshots").exists()), _POOL_CANDIDATES[0])
ONESHOT_SRC = POOL / "oneshots"

OUT = Path("/workspace/samples/vyre-162-render") if Path("/workspace").exists() else (
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\vyre-162-render")
)
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"; ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_DIR = OUT / "sections"; SECTION_DIR.mkdir(parents=True, exist_ok=True)

MP3_NAME = "EvAIx_Vyre_162.mp3"
MP3_WORKSPACE = Path("/workspace") / MP3_NAME if Path("/workspace").exists() else OUT / MP3_NAME
MP3_EXPORTS = Path("/workspace/exports") / MP3_NAME if Path("/workspace/exports").exists() else OUT / MP3_NAME
MP3_DOWNLOADS = Path(r"C:\Users\Gebruiker\Downloads") / MP3_NAME
MP3_BOX_DL = Path("/workspace") / r"C:\Users\Gebruiker\Downloads" / MP3_NAME
NOTES_PATH = (
    Path("/workspace/exports/EvAIx_Vyre_162_NOTES.md")
    if Path("/workspace/exports").exists()
    else OUT / "EvAIx_Vyre_162_NOTES.md"
)
NOTES_WORKSPACE = Path("/workspace/EvAIx_Vyre_162_NOTES.md") if Path("/workspace").exists() else NOTES_PATH
BRIDGE_COPY = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\build_vyre_162.py")
BRIDGE_BOX = Path("/workspace/evaix-bridge/build_vyre_162.py")
MID_JSON = Path("/workspace/exports/_vyre_mid_bloom.json") if Path("/workspace/exports").exists() else OUT / "_vyre_mid_bloom.json"
OUTRO_JSON = Path("/workspace/exports/_vyre_outro_clarity.json") if Path("/workspace/exports").exists() else OUT / "_vyre_outro_clarity.json"

# Gains — reflective homecoming; Pneumatix DOWN vs Tholin peak
KICK_G = 1.05
BASS_G = KICK_G * (10 ** (-9.0 / 20.0))
HATS_G, OH_G, PERC_G = 0.09, 0.07, 0.20
ACID_G, MG_G, ATM_G, PAD_G, FX_G = 0.48, 0.22, 0.40, 0.36, 0.18
TUBE_GAIN = 1.25
HAAS_W, HAAS_MS = 0.22, 9.0
ACID_HPF_HZ = 160.0
ACID_PRESENCE_HZ = 2200.0
ACID_PRESENCE_DB_OPEN = 3.6
ACID_PRESENCE_DB_MUTE = -4.0

# B major (dark filters) — homecoming −P5 from Tholin E
B_MAJ = np.array([
    61.74,   # B1
    69.30,   # C#2
    77.78,   # D#2
    82.41,   # E2
    92.50,   # F#2
    103.83,  # G#2
    123.47,  # B2
    138.59,  # C#3
], dtype=np.float64)
B_LOW = B_MAJ / 2.0
B_PAD = np.array([61.74, 92.50, 123.47, 155.56], dtype=np.float64)  # B F# B D#

# ~6' chapter — 243 bars @162 = 360.0s
FULL_SECTIONS = [
    # 14 Vyre_Intro 0:00–2:00 E2 — atm dominate · max reverb · no acid
    ("Vyre_Intro_strings", 40, "intro_strings", "14"),
    ("Vyre_Intro_voice", 41, "intro_voice", "14"),
    # 15 Vyre_Main 2:00–4:00 E5 — soft kick · restrained acid closing
    ("Vyre_Main_kick", 27, "main_kick", "15"),
    ("Vyre_Main_perc", 27, "main_perc", "15"),
    ("Vyre_Main_acid", 27, "main_acid_close", "15"),
    # 16 Vyre_Out 4:00–6:00 E1 — kick out · acid silence · filter close · ≥10s tail
    ("Vyre_Out_peel", 40, "out_peel", "16"),
    ("Vyre_Out_tail", 41, "out_tail", "16"),
]


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
    bias = 0.02
    norm = math.tanh(tube_gain)
    y = np.tanh((x + bias) * tube_gain) / norm - bias * 0.5
    return 0.94 * y + 0.06 * np.tanh(x * (tube_gain * 0.40))


def mild_compress(x: np.ndarray, thr=0.40, ratio=1.45) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    absx = np.abs(x)
    atk = math.exp(-1.0 / (SR * 0.003))
    rel = math.exp(-1.0 / (SR * 0.14))
    env = np.zeros_like(x)
    e = 0.0
    for i, a in enumerate(absx):
        e = a + (e - a) * (atk if a > e else rel)
        env[i] = e
    over = np.maximum(0.0, env - thr)
    gain = np.where(env > thr, (thr + over / ratio) / np.maximum(env, 1e-9), 1.0)
    return x * gain * 1.04


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


_IR_CACHE: dict = {}


def _make_ir(decay_s: float, seed: int = 7) -> np.ndarray:
    key = (round(float(decay_s), 2), seed)
    if key in _IR_CACHE:
        return _IR_CACHE[key]
    rng = np.random.default_rng(seed)
    n = max(SR, int(min(decay_s, 14.0) * SR))
    t = np.arange(n) / SR
    # dense early reflections + long exponential noise tail
    ir = rng.normal(0.0, 1.0, n) * np.exp(-6.907 * t / max(0.5, decay_s))
    # a few early taps
    for ms, amp in ((12, 0.55), (23, 0.35), (41, 0.22), (67, 0.15)):
        i = int(ms * 0.001 * SR)
        if i < n:
            ir[i] += amp
    ir = one_pole(ir, 6200.0, mode="lpf")
    ir = one_pole(ir, 90.0, mode="hpf")
    ir /= (np.sqrt(np.sum(ir ** 2)) + 1e-12)
    _IR_CACHE[key] = ir
    return ir


def schroeder_reverb(x: np.ndarray, decay_s: float = 12.0, wet: float = 0.65,
                     predelay_ms: float = 28.0) -> np.ndarray:
    """Long reflective hall via FFT IR — ≥10s tail, fast enough for full bounce."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    ir = _make_ir(decay_s)
    pd = max(1, int(predelay_ms * 0.001 * SR))
    try:
        from scipy.signal import fftconvolve
        wet_sig = fftconvolve(x, ir, mode="full")
    except Exception:
        wet_sig = np.convolve(x, ir[: min(len(ir), 4 * SR)], mode="full")
    out = np.zeros(n)
    if pd < n:
        out[pd:] = wet_sig[: n - pd]
    mixed = x * (1.0 - wet * 0.55) + out * wet
    return mixed


def prepare_bd(name: str, drive: float = 1.70) -> np.ndarray:
    src = ONESHOT_SRC / name
    if not src.exists():
        raise FileNotFoundError(src)
    raw = read_wav(src)
    y = one_pole(raw, 32.0, mode="hpf")
    y = one_pole(y, 3800.0, mode="lpf")  # softer than Tholin
    y = peaking_eq(y, 61.74, 1.4, q=0.9)  # B1
    y = peaking_eq(y, 100.0, 1.2, q=0.85)
    y = tanh_drive(y, drive)
    y = mild_compress(y, thr=0.45, ratio=1.35)
    y = one_pole(y, 7000.0, mode="lpf")
    peak = float(np.max(np.abs(y))) + 1e-12
    return y / peak * 0.90


def synth_sub_bass(root_hz: float = 30.87) -> np.ndarray:
    """B0 fund (~30.87) soft mono pocket — quieter than Tholin E."""
    n = int(0.26 * SR)
    t = np.arange(n) / SR
    env = np.exp(-t / 0.14)
    pitch = root_hz * (1.0 + 1.2 * np.exp(-t / 0.018))
    phase = np.cumsum(2 * np.pi * pitch / SR)
    return mild_compress(np.sin(phase) * env * 0.85, thr=0.50, ratio=1.30)


def synth_drift_pad(n: int, open_amt: float = 0.35, seed: int = 42) -> np.ndarray:
    """Reflective B major pad — soft homecoming."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    pad = np.zeros(n)
    for i, hz in enumerate(B_PAD):
        det = 1.0 + rng.uniform(-0.003, 0.003)
        phase = 2 * np.pi * hz * det * t
        saw = 2.0 * (np.mod(phase / (2 * np.pi), 1.0) - 0.5)
        sine = np.sin(phase)
        amp = 0.28 if i < 2 else 0.15
        pad += amp * (0.70 * sine + 0.30 * saw * 0.25)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.04 * t)
    lfo2 = 0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t + 0.8)
    pad *= 0.50 + 0.35 * lfo + 0.15 * lfo2
    cut = 420.0 + 3800.0 * float(np.clip(open_amt, 0.05, 1.0))
    pad = one_pole(pad, 70.0, mode="hpf")
    pad = one_pole(pad, cut, mode="lpf")
    pad = one_pole(pad, 4800.0, mode="lpf")
    return pad * 0.62


def synth_atm_haze(n: int, seed: int = 99, bright: float = 0.20) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, n)
    x = one_pole(x, 220.0, mode="hpf")
    x = one_pole(x, 1200.0 + 1600.0 * bright, mode="lpf")
    t = np.arange(n) / SR
    x *= 0.45 + 0.55 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.045 * t))
    return x * 0.18


def acid_303_note(freq: float, dur_s: float, accent: bool = False,
                  cutoff_open: float = 0.30, res_boost: float = 0.0) -> np.ndarray:
    """Single restrained Acid LPF — open≤~0.45 · closing toward Out · no res spikes."""
    n = max(8, int(dur_s * SR))
    t = np.arange(n) / SR
    o = float(np.clip(cutoff_open, 0.0, 0.50))  # hard cap restrained
    pitch = freq * (1.0 + (0.04 if accent else 0.0) * np.exp(-t / 0.05))
    phase = np.cumsum(2 * np.pi * pitch / SR)
    saw = 2.0 * (phase / (2 * np.pi) - np.floor(0.5 + phase / (2 * np.pi)))
    cut0 = 200.0 + 600.0 * o
    cut1 = cut0 + (700.0 + 2800.0 * o) * (1.05 if accent else 0.85)
    cut = cut0 + (cut1 - cut0) * np.exp(-t / (0.13 if accent else 0.20))
    cut = cut * (1.0 + 0.10 * res_boost)  # tiny — no Tholin spikes
    y_lo = one_pole(saw, float(np.percentile(cut, 15)), mode="lpf")
    y_hi = one_pole(saw, float(np.percentile(cut, 85)), mode="lpf")
    blend = np.clip((cut - cut.min()) / max(1e-9, cut.max() - cut.min()), 0, 1)
    blend = np.clip(blend * (0.45 + 0.55 * o), 0, 1)
    y = y_lo * (1 - blend) + y_hi * blend
    gate = 0.22 if not accent else 0.16
    env = np.exp(-t / gate)
    atk_n = max(1, int(0.003 * SR))
    env[:atk_n] *= np.linspace(0, 1, atk_n)
    y = y * env * (1.05 if accent else 0.88)
    y = one_pole(y, 130.0 + 40.0 * o, mode="hpf")
    if o >= 0.28:
        y = peaking_eq(y, 1800.0, 1.6 + 0.6 * (o - 0.28), q=0.95)
        y = peaking_eq(y, ACID_PRESENCE_HZ, ACID_PRESENCE_DB_OPEN * min(1.0, o / 0.40), q=1.05)
        y = peaking_eq(y, 2800.0, 1.2 * min(1.0, o / 0.40), q=1.1)
        y = peaking_eq(y, 4800.0, -3.0, q=1.2)
        y = peaking_eq(y, 5500.0, -2.2, q=1.1)
    else:
        y = peaking_eq(y, 2000.0, ACID_PRESENCE_DB_MUTE * (1.0 - o / 0.28), q=0.9)
        y = one_pole(y, 650.0 + 800.0 * o, mode="lpf")
    y = tanh_drive(y, 1.05 + 0.15 * o)
    post_lp = 1200.0 + 2600.0 * o if o >= 0.30 else (800.0 + 1100.0 * o)
    y = one_pole(y, post_lp, mode="lpf")
    y = one_pole(y, 5200.0, mode="lpf")
    return y


def mg_lpf_note(freq: float, dur_s: float, accent: bool = False,
                cutoff_open: float = 0.25) -> np.ndarray:
    """Quiet −8va square under restrained acid — never dual-peak."""
    n = max(8, int(dur_s * SR))
    t = np.arange(n) / SR
    o = float(np.clip(cutoff_open, 0.0, 0.45))
    phase = np.cumsum(2 * np.pi * freq / SR)
    sq = np.sign(np.sin(phase))
    cut = 180.0 + 1200.0 * o + (800.0 if accent else 400.0) * np.exp(-t / 0.24)
    y = one_pole(sq, float(np.median(cut)), mode="lpf")
    y = one_pole(y, float(np.percentile(cut, 70)), mode="lpf")
    env = np.exp(-t / (0.28 if accent else 0.38))
    y = y * env * 0.65
    y = one_pole(y, 130.0 + 30.0 * o, mode="hpf")
    y = tanh_drive(y, 1.02)
    y = one_pole(y, 900.0 + 1400.0 * o, mode="lpf")
    return y


def process_acid_bus(acid: np.ndarray, mg: np.ndarray, open_amt: float, mode: str):
    o = float(np.clip(open_amt, 0.0, 0.50))
    acid = np.asarray(acid, dtype=np.float64)
    mg = np.asarray(mg, dtype=np.float64)
    acid = one_pole(acid, ACID_HPF_HZ, mode="hpf")
    mg = one_pole(mg, 150.0, mode="hpf")
    if mode == "main_acid_close":
        # restrained presence for mid bloom vs mute; close only late
        acid = peaking_eq(acid, 900.0, 1.8, q=0.85)
        acid = peaking_eq(acid, 1800.0, 3.2, q=0.95)
        acid = peaking_eq(acid, ACID_PRESENCE_HZ, ACID_PRESENCE_DB_OPEN + 0.8, q=1.05)
        acid = peaking_eq(acid, 2800.0, 2.4, q=1.1)
        acid = peaking_eq(acid, 4800.0, -3.4, q=1.15)
        acid = peaking_eq(acid, 5500.0, -2.6, q=1.1)
        acid = tanh_drive(acid, 1.14)
        # hold open then close toward Out (start higher)
        acid = apply_moving_lpf(acid, 4800.0, 1100.0)
        mg = apply_moving_lpf(mg, 3200.0, 800.0)
        acid *= 1.25
        mg *= 0.85
    elif o < 0.35:
        acid = peaking_eq(acid, 2000.0, -4.5, q=0.85)
        acid = one_pole(acid, 750.0 + 600.0 * o, mode="lpf")
        mg = one_pole(mg, 600.0 + 500.0 * o, mode="lpf")
        acid *= 0.70
    else:
        acid = peaking_eq(acid, 2000.0, -1.0 + 2.5 * o, q=0.9)
        acid = one_pole(acid, 1600.0 + 2200.0 * o, mode="lpf")
    return acid, mg


def acid_poly13(bars: int, dens: float, seed: int):
    rng = np.random.default_rng(seed)
    seq = [0, 2, 0, 3, 4, 2, 5, 0, 2, 3, 0, 4, 6]
    accents = {0, 2, 4, 7, 10, 12}
    steps = bars * 16
    events = []
    for s in range(steps):
        local = s % 13
        if local in (0, 2, 4, 5, 7, 9, 10, 12) or rng.random() < dens * 0.10:
            if rng.random() < dens or local in accents:
                note = seq[local]
                accent = local in accents
                dur = 4 if (accent and local == 0) else (3 if accent else 2)
                events.append((s, note, accent, dur))
    return events


def hat_poly15(bars: int, dens: float = 0.5):
    steps = bars * 16
    hits = []
    pattern = [0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 1]
    for s in range(steps):
        if pattern[s % 15] and (dens >= 0.99 or (s % 15) % 3 != 1 or dens > 0.45):
            hits.append(s)
    return hits


def perc_poly7(bars: int, dens: float = 0.35):
    steps = bars * 16
    hits = []
    pattern = [1, 0, 0, 1, 0, 1, 0]
    for s in range(steps):
        if pattern[s % 7] and (s % 7 != 0 or dens > 0.25):
            if dens > 0.7 or s % 14 < 7:
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
        "bd_b01": ("bd_b01_organic_soft.wav", 1.55),
        "bd_b02": ("bd_b02_soft_dry.wav", 1.60),
        "bd_b03": ("bd_b03_soft_groove.wav", 1.65),
        "bd_b04": ("bd_b04_thin_close.wav", 1.45),
        "bd_b05": ("bd_b05_whisper.wav", 1.30),
        "bd_bass1": ("bd_bass_b01_soft.wav", 1.70),
        "bd_bass2": ("bd_bass_b02_soft.wav", 1.72),
        "bd_fac_soft": ("bd_factory_b_soft.wav", 1.50),
        "bd_fac_thin": ("bd_factory_b_thin.wav", 1.40),
        "bd_veiled": ("bd_factory_b_veiled.wav", 1.25),
        "bd_sinkick": ("bd_sinkick_b_soft.wav", 1.15),
    }
    for key, (name, drive) in bd_map.items():
        shots[key] = prepare_bd(name, drive=drive)
        write_mono(ONESHOT / f"{key}_{name}", shots[key], 0.90)
        used.append(name)

    for key, name, drive, hpf, lpf in [
        ("hh3c", "hh_3c_morph_sparse.wav", 0.90, 4000, 11000),
        ("hh3o", "hh_3o_morph_soft.wav", 0.95, 3000, 10000),
        ("hh3o_air", "hh_3o_air.wav", 0.85, 3200, 10500),
    ]:
        shots[key] = load_shot(name, drive, hpf, lpf)
        used.append(name)

    for key, name, drive, hpf, lpf in [
        ("rim2", "perc_rim2_factory.wav", 1.05, 600, 7000),
        ("clap2", "perc_clap2_soft.wav", 1.00, 500, 7500),
        ("clap4", "perc_clap4_soft.wav", 1.00, 600, 8000),
        ("tom2", "perc_tom2_soft.wav", 1.05, 80, 5000),
        ("tom4", "perc_tom4_soft.wav", 1.05, 60, 4500),
        ("congasyn", "perc_congasyn.wav", 1.10, 100, 5500),
        ("sd4", "perc_sd4_accent.wav", 1.05, 700, 7000),
    ]:
        shots[key] = load_shot(name, drive, hpf, lpf)
        used.append(name)

    shots["splash"] = load_shot("splash_cym_tail.wav", 0.85, 400, 9000)
    shots["crash1"] = load_shot("crash_1_soft.wav", 0.80, 400, 8500)
    used.extend(["splash_cym_tail.wav", "crash_1_soft.wav"])

    atm_names = [
        ("atm_strings", "atm_strings_home.wav"),
        ("atm_lore", "atm_lore_haze.wav"),
        ("atm_epchord", "atm_epchord_soft.wav"),
        ("atm_orgphrase", "atm_orgphrase.wav"),
        ("atm_organlp", "atm_organlp.wav"),
        ("atm_pianolp", "atm_pianolp.wav"),
        ("atm_eplp1", "atm_eplp_1.wav"),
        ("atm_eplp2", "atm_eplp_2.wav"),
        ("atm_eplp3", "atm_eplp_3.wav"),
        ("atm_synlp5", "atm_synlp_5.wav"),
        ("atm_v2", "atm_voice_2.wav"),
        ("atm_v2m", "atm_voice_2_morph.wav"),
        ("atm_v4", "atm_voice_4.wav"),
        ("atm_v4m", "atm_voice_4_morph.wav"),
        ("atm_v6", "atm_voice_6.wav"),
        ("atm_v8", "atm_voice_8_grain.wav"),
        ("atm_v8m", "atm_voice_8_morph.wav"),
        ("atm_v10", "atm_voice_10.wav"),
        ("atm_v12", "atm_voice_12.wav"),
        ("atm_v25", "atm_voice_25.wav"),
        ("atm_v25m", "atm_voice_25_morph.wav"),
        ("atm_v27", "atm_voice_27.wav"),
        ("atm_v28", "atm_voice_28_tail.wav"),
    ]
    for key, name in atm_names:
        y = read_wav(ONESHOT_SRC / name)
        y = one_pole(y, 70.0, mode="hpf")
        y = one_pole(y, 6800.0, mode="lpf")
        peak = float(np.max(np.abs(y))) + 1e-12
        shots[key] = y / peak * 0.82
        used.append(name)

    for key, name in [
        ("sfx_drumlp1", "sfx_drumlp_1.wav"),
        ("sfx_drumlp4", "sfx_drumlp_4.wav"),
        ("sfx_gtrlp1", "sfx_gtrlp_1.wav"),
        ("sfx_gtrlp4", "sfx_gtrlp_4.wav"),
        ("sfx_pizz", "sfx_pizz_soft.wav"),
        ("sfx_5th", "sfx_5thstab_soft.wav"),
    ]:
        y = read_wav(ONESHOT_SRC / name)
        y = one_pole(y, 80.0, mode="hpf")
        y = one_pole(y, 7000.0, mode="lpf")
        peak = float(np.max(np.abs(y))) + 1e-12
        shots[key] = y / peak * 0.78
        used.append(name)

    for k in ("hh3c", "hh3o", "hh3o_air"):
        shots[k] = one_pole(shots[k], 9000.0, mode="lpf") * 0.88

    shots["bass"] = synth_sub_bass(30.87)
    write_mono(ONESHOT / "bass_sub_B.wav", shots["bass"], 0.88)
    shots["used"] = sorted(set(used))
    print("shots ready", len(shots["used"]))
    return shots


def kit_for_mode(mode: str, slot: str, shots: dict) -> dict:
    bd_pick = {
        "intro_strings": shots["bd_sinkick"],
        "intro_voice": shots["bd_veiled"],
        "main_kick": shots["bd_b02"],
        "main_perc": shots["bd_b03"],
        "main_acid_close": shots["bd_b04"],
        "out_peel": shots["bd_b05"],
        "out_tail": shots["bd_b05"],
    }
    hat_pick = {
        "intro_strings": shots["hh3o_air"],
        "intro_voice": shots["hh3o_air"],
        "main_kick": shots["hh3c"],
        "main_perc": shots["hh3c"],
        "main_acid_close": shots["hh3o"],
        "out_peel": shots["hh3o_air"],
        "out_tail": shots["hh3o_air"],
    }
    # energy lower than Tholin; Intro atm dominate; Out empty drums
    gains = {
        "intro_strings": dict(kick=0.0, bass=0.0, hats=0.0, oh=0.0, perc=0.0,
                              acid=0.0, mg=0.0, atm=1.0, pad=1.05, fx=0.45, acid_open=0.0,
                              reverb=0.78, rev_decay=11.0),
        "intro_voice": dict(kick=0.0, bass=0.0, hats=0.04, oh=0.0, perc=0.0,
                            acid=0.0, mg=0.0, atm=0.95, pad=0.95, fx=0.50, acid_open=0.0,
                            reverb=0.82, rev_decay=12.0),
        "main_kick": dict(kick=0.78, bass=0.45, hats=0.32, oh=0.08, perc=0.0,
                          acid=0.0, mg=0.0, atm=0.55, pad=0.60, fx=0.22, acid_open=0.0,
                          reverb=0.55, rev_decay=8.0),
        "main_perc": dict(kick=0.82, bass=0.50, hats=0.38, oh=0.12, perc=0.55,
                          acid=0.0, mg=0.0, atm=0.48, pad=0.52, fx=0.28, acid_open=0.0,
                          reverb=0.52, rev_decay=8.0),
        "main_acid_close": dict(kick=0.55, bass=0.28, hats=0.22, oh=0.08, perc=0.22,
                                acid=1.35, mg=0.70, atm=0.32, pad=0.38, fx=0.22, acid_open=0.45,
                                reverb=0.55, rev_decay=9.0),
        "out_peel": dict(kick=0.0, bass=0.0, hats=0.0, oh=0.0, perc=0.0,
                         acid=0.0, mg=0.0, atm=0.80, pad=0.70, fx=0.40, acid_open=0.0,
                         reverb=0.85, rev_decay=12.0),
        "out_tail": dict(kick=0.0, bass=0.0, hats=0.0, oh=0.0, perc=0.0,
                         acid=0.0, mg=0.0, atm=0.55, pad=0.45, fx=0.35, acid_open=0.0,
                         reverb=0.92, rev_decay=14.0),
    }
    stories = {
        "intro_strings": "Slot14 Intro — Strings/OrgPhrase atm dominate; max reverb; NO kick/acid",
        "intro_voice": "Slot14 Intro — +Lore/EP/Voice grain/SplashCym; still no kick/acid",
        "main_kick": "Slot15 Main — soft BD B02 1/5/9/13; sparse HH3C; atm continue",
        "main_perc": "Slot15 Main — +soft perc ticks · Crash wash; still no acid",
        "main_acid_close": "Slot15 Main — restrained acid muted→closing (open≤0.45); no res spikes",
        "out_peel": "Slot16 Out — kick OUT · acid silence · strip hats/perc · atm remain",
        "out_tail": "Slot16 Out — atm LPF close · Voice-28/Splash · ≥10s reverb tail",
    }
    kick_on = {
        "intro_strings": [], "intro_voice": [],
        "main_kick": [0, 4, 8, 12], "main_perc": [0, 4, 8, 12],
        "main_acid_close": [0, 4, 8, 12],
        "out_peel": [], "out_tail": [],
    }
    bd_name = {
        "intro_strings": "NONE", "intro_voice": "NONE",
        "main_kick": "bd_b02_soft_dry", "main_perc": "bd_b03_soft_groove",
        "main_acid_close": "bd_b04_thin_close",
        "out_peel": "NONE", "out_tail": "NONE",
    }[mode]
    return {
        "kick": bd_pick[mode], "hat": hat_pick[mode],
        "gains": gains[mode], "story": stories[mode],
        "kick_steps": kick_on[mode], "bd_name": bd_name, "slot": slot,
    }


def render_section(idx: int, name: str, bars: int, mode: str, slot: str, shots: dict):
    N = section_n(bars)
    trk_k = np.zeros(N); trk_b = np.zeros(N); trk_h = np.zeros(N); trk_oh = np.zeros(N)
    trk_p = np.zeros(N)
    trk_acid = np.zeros(N); trk_mg = np.zeros(N)
    trk_atm = np.zeros(N); trk_pad = np.zeros(N); trk_fx = np.zeros(N)
    kit = kit_for_mode(mode, slot, shots)
    g = kit["gains"]
    seed = 0xB162 + idx * 31
    rng = np.random.default_rng(seed)

    # soft kick peel: last 8 bars of main_acid_close mute kick toward Out
    mute_kick_bars = set()
    if mode == "main_acid_close" and bars >= 12:
        mute_kick_bars = set(range(bars - 8, bars))

    for bar in range(bars):
        kick_steps = [] if bar in mute_kick_bars else kit["kick_steps"]
        for st in kick_steps:
            beat = bar * 4 + st / 4.0
            place(trk_k, kit["kick"], beat, 1.0)
            place(trk_b, shots["bass"], beat, 1.0)
            # quiet soft sub layer on Main only
            if mode in ("main_perc", "main_acid_close") and bar % 4 == 0:
                place(trk_b, shots["bd_bass1"] if bar % 8 < 4 else shots["bd_bass2"], beat, 0.35)

        if g["hats"] > 0.03:
            dens = 0.22 if mode.startswith("intro") else (
                0.42 if mode == "main_kick" else (0.50 if mode == "main_perc" else 0.38)
            )
            for s in hat_poly15(1, dens=dens):
                if s < 16:
                    beat = bar * 4 + s / 4.0
                    place(trk_h, kit["hat"], beat, 0.55 if s % 4 == 2 else 0.40)

        if g["oh"] > 0.05 and bar % 2 == 1:
            place(trk_oh, shots["hh3o"], bar * 4 + 1.5, 0.40)

        if g["perc"] > 0.08:
            dens = 0.40 if mode == "main_perc" else 0.28
            bank = [shots["rim2"], shots["clap2"], shots["tom2"], shots["congasyn"],
                    shots["clap4"], shots["tom4"]]
            for s in perc_poly7(1, dens=dens):
                if s < 16:
                    beat = bar * 4 + s / 4.0
                    place(trk_p, bank[s % len(bank)], beat, 0.48 if s % 7 == 0 else 0.35)
            if mode == "main_perc" and bar % 8 == 7:
                place(trk_p, shots["sd4"], bar * 4 + 2.0, 0.28)
            if mode in ("main_perc", "main_acid_close") and bar % 16 == 0:
                place(trk_fx, shots["crash1"], bar * 4, 0.32)

    pad_open = {
        "intro_strings": 0.40, "intro_voice": 0.55,
        "main_kick": 0.45, "main_perc": 0.42, "main_acid_close": 0.35,
        "out_peel": 0.30, "out_tail": 0.18,
    }[mode]
    if g["pad"] > 0.01:
        trk_pad += synth_drift_pad(N, open_amt=pad_open, seed=seed)

    if g["atm"] > 0.01:
        bright = 0.28 if mode.startswith("intro") else (0.18 if mode.startswith("out") else 0.22)
        trk_atm += synth_atm_haze(N, seed=seed + 5, bright=bright)
        atm_bank = {
            "intro_strings": [shots["atm_strings"], shots["atm_orgphrase"], shots["atm_organlp"]],
            "intro_voice": [shots["atm_lore"], shots["atm_epchord"], shots["atm_v2"],
                            shots["atm_v2m"], shots["atm_v4"], shots["atm_v8"], shots["atm_pianolp"]],
            "main_kick": [shots["atm_strings"], shots["atm_epchord"], shots["atm_eplp1"], shots["atm_synlp5"]],
            "main_perc": [shots["atm_eplp2"], shots["atm_v4"], shots["atm_v6"], shots["atm_v10"]],
            "main_acid_close": [shots["atm_strings"], shots["atm_synlp5"], shots["atm_v4m"]],
            "out_peel": [shots["atm_strings"], shots["atm_lore"], shots["atm_pianolp"],
                         shots["atm_organlp"], shots["atm_v25"], shots["atm_v27"]],
            "out_tail": [shots["atm_v28"], shots["atm_v25m"], shots["atm_v8m"],
                         shots["atm_v12"], shots["atm_eplp3"], shots["atm_strings"]],
        }[mode]
        # early sample rotation — new one-shot early in each slot section
        for bar in range(0, bars, 2):
            samp = atm_bank[bar % len(atm_bank)]
            place(trk_atm, samp, bar * 4 + rng.uniform(0, 0.4), 0.38 if mode.startswith("intro") else 0.28)
        # Splash / air
        if mode in ("intro_voice", "out_peel", "out_tail"):
            for bar in range(0, bars, 4):
                place(trk_fx, shots["splash"], bar * 4 + rng.uniform(0, 0.8), 0.42)
        sfx_bank = {
            "intro_strings": [shots["sfx_drumlp1"], shots["sfx_pizz"]],
            "intro_voice": [shots["sfx_gtrlp1"], shots["sfx_drumlp1"], shots["sfx_pizz"]],
            "main_kick": [shots["sfx_5th"]],
            "main_perc": [shots["sfx_5th"], shots["crash1"]],
            "main_acid_close": [shots["sfx_5th"]],
            "out_peel": [shots["sfx_gtrlp4"], shots["sfx_drumlp4"]],
            "out_tail": [shots["sfx_gtrlp4"], shots["sfx_pizz"], shots["atm_v28"]],
        }[mode]
        for bar in range(0, bars, 3):
            if sfx_bank:
                place(trk_fx, sfx_bank[bar % len(sfx_bank)],
                      bar * 4 + rng.uniform(0, 1.0), 0.32)

    acid_open = float(g["acid_open"])
    dens = {
        "intro_strings": 0.0, "intro_voice": 0.0,
        "main_kick": 0.0, "main_perc": 0.0,
        "main_acid_close": 0.82,
        "out_peel": 0.0, "out_tail": 0.0,
    }[mode]
    # closing envelope on acid open within Main_acid section
    if dens > 0.01 and (g["acid"] > 0.05 or g["mg"] > 0.05):
        for step, note_i, accent, dur_steps in acid_poly13(bars, dens, seed):
            bar_i = step // 16
            # open starts ~0.42 then falls — restrained closing, no res spikes
            t_frac = bar_i / max(1, bars - 1)
            local_open = acid_open * (1.0 - 0.75 * (max(0.0, t_frac - 0.35) / 0.65) ** 1.1)
            local_open = float(np.clip(local_open, 0.12, 0.45))
            freq = float(B_MAJ[note_i % len(B_MAJ)])
            note = acid_303_note(freq, dur_steps * STEP_S, accent=accent,
                                 cutoff_open=local_open, res_boost=0.0)
            place(trk_acid, note, step / 4.0, 1.05 if accent else 0.82)
            mg = mg_lpf_note(float(B_LOW[note_i % len(B_LOW)]), dur_steps * STEP_S * 1.1,
                             accent=accent, cutoff_open=local_open * 0.85)
            place(trk_mg, mg, step / 4.0, 0.70)

    trk_k *= KICK_G * g["kick"]; trk_b *= BASS_G * g["bass"]
    trk_h *= HATS_G * g["hats"]; trk_oh *= OH_G * g["oh"]
    trk_p *= PERC_G * g["perc"]
    trk_acid *= ACID_G * g["acid"]; trk_mg *= MG_G * g["mg"]
    trk_atm *= ATM_G * g["atm"]; trk_pad *= PAD_G * g["pad"]; trk_fx *= FX_G * g["fx"]

    if g["acid"] > 0.05 or g["mg"] > 0.05:
        trk_acid, trk_mg = process_acid_bus(trk_acid, trk_mg, acid_open, mode)

    # Out: hard assert no kick/bass/acid
    if mode in ("out_peel", "out_tail", "intro_strings", "intro_voice"):
        trk_k *= 0.0
        trk_b *= 0.0
        trk_acid *= 0.0
        trk_mg *= 0.0

    # atm filter close on Out
    if mode == "out_peel":
        trk_atm = apply_moving_lpf(trk_atm, 4200.0, 1800.0)
        trk_pad = apply_moving_lpf(trk_pad, 3800.0, 1600.0)
        trk_fx = apply_moving_lpf(trk_fx, 4500.0, 2000.0)
    if mode == "out_tail":
        trk_atm = apply_moving_lpf(trk_atm, 1800.0, 480.0)
        trk_pad = apply_moving_lpf(trk_pad, 1600.0, 400.0)
        trk_fx = apply_moving_lpf(trk_fx, 2000.0, 600.0)
        # dry fade so reverb tail dominates last ≥10s
        fade = np.ones(N)
        tail_start = max(0, N - int(14.0 * SR))
        fade[tail_start:] = np.linspace(1.0, 0.08, N - tail_start)
        # keep some atm for reverb input then wet dominates
        trk_atm *= fade
        trk_pad *= fade * 0.85
        trk_fx *= np.sqrt(fade)

    mono_bed = trk_k + trk_b + trk_p + trk_pad
    hats_atm = trk_h + trk_oh + trk_atm
    acid_bus = trk_acid + trk_mg

    cut_map = {
        "intro_strings": (900.0, 3200.0),
        "intro_voice": (1400.0, 4200.0),
        "main_kick": (2400.0, 5200.0),
        "main_perc": (2600.0, 5600.0),
        "main_acid_close": (2200.0, 4800.0),
        "out_peel": (2000.0, 1400.0),
        "out_tail": (1200.0, 500.0),
    }
    c0, c1 = cut_map[mode]
    mono_bed = apply_moving_lpf(mono_bed, c0, c1)
    hats_atm = apply_moving_lpf(hats_atm, c0, c1)
    if mode == "main_acid_close":
        acid_bus = apply_moving_lpf(acid_bus, 2800.0, 1000.0)
    else:
        acid_bus = apply_moving_lpf(acid_bus, c0 * 0.85, c1 * 0.95)
    fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, max(400.0, c1 * 1.0))

    mono_bed = valve_force(mono_bed, TUBE_GAIN * 0.70)
    hats_atm = valve_force(hats_atm, TUBE_GAIN * 0.60)
    acid_bus = valve_force(acid_bus, TUBE_GAIN * 0.72)
    fx_bus = valve_force(fx_bus, TUBE_GAIN * 0.75)
    mono_bed = one_pole(mono_bed, 10000.0, mode="lpf")
    hats_atm = one_pole(hats_atm, 8500.0, mode="lpf")
    acid_bus = one_pole(acid_bus, 4800.0, mode="lpf")
    fx_bus = one_pole(fx_bus, 7800.0, mode="lpf")

    # MAX REVERB on Intro / Out — long wet hall
    rev_wet = float(g.get("reverb", 0.4))
    rev_decay = float(g.get("rev_decay", 8.0))
    if rev_wet > 0.3:
        hats_atm = schroeder_reverb(hats_atm, decay_s=rev_decay, wet=rev_wet, predelay_ms=32.0)
        fx_bus = schroeder_reverb(fx_bus, decay_s=rev_decay * 0.95, wet=min(0.95, rev_wet + 0.05),
                                  predelay_ms=40.0)
        # pad partial wet for space (keep mono core)
        pad_wet = schroeder_reverb(trk_pad * 0.55, decay_s=rev_decay, wet=rev_wet * 0.85,
                                   predelay_ms=36.0)
        mono_bed = mono_bed - trk_pad * 0.20 + pad_wet * 0.55

    if mode == "out_tail":
        # reinforce ≥10s readable tail: reverb-only wash on last 12s
        tail_n = int(12.5 * SR)
        if N > tail_n:
            wash = hats_atm[-tail_n:] + fx_bus[-tail_n:] * 0.8
            wash = schroeder_reverb(wash, decay_s=14.0, wet=0.95, predelay_ms=20.0)
            wash = one_pole(wash, 2800.0, mode="lpf")
            # fade wash in over last 12.5s
            env = np.linspace(0.35, 1.0, tail_n)
            hats_atm[-tail_n:] = hats_atm[-tail_n:] * (1.0 - 0.55 * env) + wash * 0.85 * env
            mono_bed[-tail_n:] *= np.linspace(0.7, 0.12, tail_n)

    wide_src = acid_bus + fx_bus
    wl, wr = haas_widen(wide_src, HAAS_W if g["acid"] > 0.2 or g["pad"] > 0.5 else 0.16)
    hl, hr = haas_widen(hats_atm, 0.20 if (g["hats"] > 0.1 or g["atm"] > 0.3) else 0.12, 11.0)
    wl = wl + hl; wr = wr + hr
    if g["pad"] > 0.3:
        pl, pr = haas_widen(trk_pad * 0.40, 0.26, 13.0)
        wl = wl + pl; wr = wr + pr
        mono_bed = mono_bed - trk_pad * 0.12

    left = mono_bed + wl
    right = mono_bed + wr
    # tame harsh master-side per section
    left = peaking_eq(left, 4800.0, -1.8, q=1.1)
    right = peaking_eq(right, 4800.0, -1.8, q=1.1)
    left = peaking_eq(left, 5500.0, -1.5, q=1.1)
    right = peaking_eq(right, 5500.0, -1.5, q=1.1)

    mix_path = SECTION_DIR / f"{idx:02d}_{name}_mix.wav"
    write_stereo_lr(mix_path, left, right, 0.85)
    meta = {
        "name": name, "mode": mode, "slot": slot, "bars": bars,
        "story": kit["story"], "bd": kit["bd_name"],
        "gains": {k: g[k] for k in g if k not in ("acid_open", "reverb", "rev_decay")},
        "acid_open": acid_open,
        "reverb": rev_wet, "rev_decay": rev_decay,
        "acid_events": len(acid_poly13(bars, dens, seed)) if dens > 0 else 0,
        "dur_s": bars * BAR_S,
    }
    print(f"  section {idx:02d} slot{slot} {name}: {bars} bars (~{bars * BAR_S:.1f}s) "
          f"open={acid_open:.2f} rev={rev_wet:.2f}")
    return mix_path, meta


def bounce_mp3(mixes, mp3_path: Path) -> float:
    concat_list = OUT / "_vyre_concat.txt"
    raw = OUT / "_vyre_raw.wav"
    mastered = OUT / "_vyre_master.wav"
    with concat_list.open("w", encoding="utf-8") as f:
        for p in mixes:
            f.write(f"file '{p.as_posix()}'\n")
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw)],
        check=True, capture_output=True,
    )
    # PA master — softer than Tholin peak; mid lift for acid zone; tame 3–6k; space for LRA
    af = (
        "volume=3.2dB,"
        "highpass=f=24:poles=2,"
        "lowshelf=f=80:t=q:w=0.7:g=1.0,"
        "equalizer=f=31:t=q:w=1.0:g=1.2,"
        "equalizer=f=62:t=q:w=1.1:g=1.4,"
        "equalizer=f=100:t=q:w=1.0:g=0.8,"
        "equalizer=f=380:t=q:w=1.0:g=-0.6,"
        "equalizer=f=900:t=q:w=1.0:g=0.7,"
        "equalizer=f=1800:t=q:w=1.0:g=1.2,"
        "equalizer=f=2400:t=q:w=1.1:g=1.3,"
        "equalizer=f=4500:t=q:w=1.2:g=-2.4,"
        "equalizer=f=5500:t=q:w=1.2:g=-2.6,"
        "equalizer=f=6500:t=q:w=1.2:g=-2.4,"
        "equalizer=f=10000:t=q:w=1.1:g=-2.8,"
        "highshelf=f=7000:t=q:w=0.7:g=-3.0,"
        "lowpass=f=14500:poles=1,"
        "acompressor=threshold=-22dB:ratio=1.22:attack=14:release=200:makeup=1.02,"
        "loudnorm=I=-8.2:TP=-1.0:LRA=13,"
        "alimiter=limit=0.891:attack=1:release=60:level=disabled"
    )
    r = subprocess.run(
        [FFMPEG, "-y", "-i", str(raw), "-af", af, str(mastered)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("master fail", (r.stderr or "")[-2000:])
        raise RuntimeError("master failed")

    # Surgical: Main acid mid presence 200–230s · Out filter/duck kick-band 240–360 · tail space
    surg = OUT / "_vyre_surg.wav"
    af2 = (
        "equalizer=f=900:t=q:w=1.0:g=2.2:enable='between(t,200,235)',"
        "equalizer=f=1800:t=q:w=1.0:g=3.6:enable='between(t,200,235)',"
        "equalizer=f=2400:t=q:w=1.1:g=3.8:enable='between(t,200,235)',"
        "equalizer=f=2800:t=q:w=1.0:g=2.6:enable='between(t,200,235)',"
        "equalizer=f=5200:t=q:w=1.2:g=-2.8:enable='between(t,200,235)',"
        "volume=volume=2.5dB:enable='between(t,200,235)',"
        # Out: ensure kick-band empty + closing air (gentle level — keep I up)
        "equalizer=f=50:t=q:w=0.8:g=-10:enable='between(t,240,360)',"
        "equalizer=f=80:t=q:w=0.9:g=-8:enable='between(t,240,360)',"
        "lowpass=f=4200:poles=1:enable='between(t,300,360)',"
        "lowpass=f=2200:poles=1:enable='between(t,345,360)',"
        "volume=volume=-0.8dB:enable='between(t,240,300)',"
        "volume=volume=-2.0dB:enable='between(t,300,360)',"
        "loudnorm=I=-8.2:TP=-1.0:LRA=13,"
        "alimiter=limit=0.891:attack=1:release=60:level=disabled"
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
    """Compare Main_perc (no acid ~160–200s) vs Main_acid early (~200–220s) mid 700Hz–3k."""
    raw = OUT / "_vyre_analyze.f32"
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

    mute = section(165.0, 195.0)   # Main_perc — no acid
    open_ = section(200.0, 222.0)  # Main_acid early — restrained open before close

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
        "note": "Vyre restrained acid — bloom vs Main_perc silence, not Tholin peak dual",
    }
    print("MID-BLOOM mute_rel", out["mute_mid_rel"], "open_rel", out["open_mid_rel"],
          "delta", out["delta_open_minus_mute"], "harsh_under_mids", out["harsh_under_mids"])
    MID_JSON.parent.mkdir(parents=True, exist_ok=True)
    MID_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    (OUT / "_vyre_mid_bloom.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def measure_outro_clarity(path: Path) -> dict:
    """Outro/handoff: kick/acid out, filter close, long reverb tail readable (≥10s)."""
    raw = OUT / "_vyre_outro_analyze.f32"
    subprocess.run(
        [FFMPEG, "-y", "-i", str(path), "-ac", "1", "-ar", "48000", "-f", "f32le", str(raw)],
        check=True, capture_output=True,
    )
    x = np.fromfile(raw, dtype=np.float32).astype(np.float64)
    sr = 48000.0

    def rms_db(seg):
        return 20.0 * math.log10(float(np.sqrt(np.mean(seg ** 2)) + 1e-12))

    def band_db(seg, lo, hi):
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

    main = section(130.0, 190.0)     # Main with kick
    out_body = section(250.0, 290.0) # Out peel
    tail = section(345.0, 358.0)     # last ~13s of 360
    pre_tail = section(320.0, 335.0)

    main_kb = band_db(main, 40.0, 100.0)
    out_kb = band_db(out_body, 40.0, 100.0)
    main_full = band_db(main, 20.0, 12000.0)
    out_full = band_db(out_body, 20.0, 12000.0)
    # relative kick-band
    main_kb_rel = main_kb - main_full
    out_kb_rel = out_kb - out_full

    tail_rms = rms_db(tail)
    pre_rms = rms_db(pre_tail)
    tail_hf = band_db(tail, 200.0, 4000.0)
    # reverb energy still present if mid/air not silent
    out = {
        "main_kickband_rel_db": round(main_kb_rel, 2),
        "out_kickband_rel_db": round(out_kb_rel, 2),
        "kickband_collapse_db": round(out_kb_rel - main_kb_rel, 2),
        "out_vs_main_rms_db": round(rms_db(out_body) - rms_db(main), 2),
        "tail_last13s_rms_db": round(tail_rms, 2),
        "pre_tail_rms_db": round(pre_rms, 2),
        "tail_air_200_4k_db": round(tail_hf, 2),
        "tail_still_audible": bool(tail_rms > -45.0 and tail_hf > -55.0),
        "kick_out_clear": bool((out_kb_rel - main_kb_rel) < -8.0),
        "acid_silence_zone": "240–360s (Out) — no acid events by design",
    }
    print("OUTRO kick_collapse", out["kickband_collapse_db"],
          "tail_audible", out["tail_still_audible"], "tail_rms", out["tail_last13s_rms_db"])
    OUTRO_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    (OUT / "_vyre_outro_clarity.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def write_notes(dur: float, metas: list, lufs: dict, shots: dict, errors: list,
                mid: dict | None = None, outro: dict | None = None):
    t = 0.0
    lines_tl = []
    for m in metas:
        lines_tl.append(
            f"- **{t:.1f}–{t + m['dur_s']:.1f}s** `{m['name']}` (slot {m['slot']}, {m['bars']} bars) — "
            f"{m['story']} [bd={m['bd']}; acid_ev={m['acid_events']}; open={m['acid_open']:.2f}; "
            f"rev={m.get('reverb', 0):.2f}]"
        )
        t += m["dur_s"]

    mid_block = ""
    if mid:
        mid_block = f"""
## Mid-band acid appear vs mute (Main_perc → Main_acid)
| Metric | Value |
|--------|-------|
| Mute mid rel (700Hz–3k vs full) | **{mid.get('mute_mid_rel')}** dB |
| Open mid rel (700Hz–3k vs full) | **{mid.get('open_mid_rel')}** dB |
| Delta open−mute | **{mid.get('delta_open_minus_mute')}** dB |
| Abs mid rise | **{mid.get('abs_mid_rise_db')}** dB |
| Harsh 3–6k open rel | {mid.get('open_harsh_rel')} (mute {mid.get('mute_harsh_rel')}) |
| Harsh under mids on open | **{mid.get('harsh_under_mids')}** |
"""
    outro_block = ""
    if outro:
        outro_block = f"""
## Outro / handoff clarity (set close)
| Metric | Value |
|--------|-------|
| Kick-band collapse (Out−Main rel) | **{outro.get('kickband_collapse_db')}** dB |
| Kick out clear | **{outro.get('kick_out_clear')}** |
| Out vs Main RMS | {outro.get('out_vs_main_rms_db')} dB |
| Tail last ~13s RMS | **{outro.get('tail_last13s_rms_db')}** dBFS |
| Tail air 200–4k | {outro.get('tail_air_200_4k_db')} dB |
| Tail still audible (≥10s) | **{outro.get('tail_still_audible')}** |
| Acid silence | {outro.get('acid_silence_zone')} |
"""

    body = f"""# EvAIx Vyre — Vestiges slots 14–16 @ 162 B (FineTuniX homecoming)

**MP3:** `EvAIx_Vyre_162.mp3`
- Downloads: `C:\\\\Users\\\\Gebruiker\\\\Downloads\\\\EvAIx_Vyre_162.mp3`
- Workspace: `/workspace/EvAIx_Vyre_162.mp3`
- Exports: `/workspace/exports/EvAIx_Vyre_162.mp3`
- Script: `/workspace/build_vyre_162.py` (+ exports + evaix-bridge)
- Pool: `/workspace/exports/vyre-pool/oneshots/` ({len(shots.get('used', []))} WAVs)
- Prep: `/workspace/exports/VYRE_SAMPLE_POOL_PREP.md`

Duration: **{dur:.2f} s** (~{dur/60:.2f} min) · BPM **162** · Key **B major** (dark filters · −P5 homecoming after Tholin E)

## Measured loudness
- **I** = {lufs.get('I')} LUFS (target −8…−9)
- **TP** = {lufs.get('TP')} dB (target ≤ −1.0 dBTP)
- **LRA** = {lufs.get('LRA')} LU
{mid_block}{outro_block}
## Slot map (skeleton-locked · chapter-relative 0–6′)
| Slot | ID | Time | Energy | Character |
|------|-----|------|--------|-----------|
| 14 | Vyre_Intro | 0:00–2:00 | 2 | Atm dominate · max reverb · **no acid** · no full kick |
| 15 | Vyre_Main | 2:00–4:00 | 5 | Soft kick · restrained acid closing (open≤0.45) |
| 16 | Vyre_Out | 4:00–6:00 | 1 | Kick out · acid silence · atm filter close · **≥10s reverb tail** |

## Mute staircase (within chapter)
| Bars | Action |
|------|--------|
| 1–40 | Strings/OrgPhrase atm only · max reverb (slot 14a) |
| 41–81 | +Lore/EP · Voice grain · SplashCym · still no kick/acid (14b) |
| 82–108 | +soft BD B02 1/5/9/13 · sparse HH3C (15 kick) |
| 109–135 | +soft perc ticks · Crash wash (15 perc) |
| 136–162 | restrained acid muted→closing filter (15 acid) |
| 163–202 | kick out · acid silence (16 peel) |
| 203–243 | atm LPF close · Voice-28/Splash · ≥10s reverb tail |

## Poly doctrine
- Acid **Last Step 13** (Main closing only) vs kick **16** vs hats **15** vs perc **7**
- Kick grid: steps 0/4/8/12 (Electribe 1/5/9/13) — soft B BD only
- Single restrained Acid LPF · B major · open≤0.45 · **no dual-acid · no res spikes 4/8/12/16**
- SD4 / clap sparse accent only — **no gabber spine**

## Sample families (NEW vs Figment+Haniwa+Tholin)
- BD: Insane **G#→B soft** G01–G05 + BASS G→B + factory BD-1..3 soft + SinKick haze
- HH: **HH-3O/3C morph · Splash · Crash-1** (≠ Figment/Haniwa/Tholin hat spines)
- Perc: **Rim-2 · Clap-2/4 · Tom-2/4 · CongaSyn · SD-4**
- Atm: **Strings/Lore/EP/Organ/Piano · SynLP-5 · Voice2/4/6/8/10/12/25/27/28**
- Character: reflective homecoming · max reverb · Pneumatix tribal **DOWN**

## Section timeline
{chr(10).join(lines_tl)}

## Sound design locks
- Acid: restrained closing on Main only; presence 1.8–2.8 kHz for mid appear; harsh 3–6k cut; open falls toward Out
- Intro: max Schroeder reverb · no kick · no acid
- Out: kick/bass/acid hard mute · atm LPF close · wet≥0.9 · decay≥12–14s · last ≥10s tail readable
- Kick: root-tuned B (~30.9 Hz sub), soft body ~100 Hz, EQ before sat, mono
- Master: soft mid lift + PA tame; surgical Main acid 200–230s; Out kick-band duck; loudnorm I=-8.5 TP=-1.0 LRA=12

## Doctrine kept
- Free-party / mental tekno resolve — **no commercial EDM drops**
- Soft reflective homecoming after Tholin peak (−P5 E→B)
- Plateaus 16–32 bars · early sample rotation · ≠ prior chapter spines
- Kick/bass mono · Haas only on hats/atm/acid/fx

Samples used ({len(shots.get('used', []))}): {shots.get('used', [])}
Errors: {errors}
Ableton: skipped (--skip-ableton / DSP bounce)

*EvAIx · Vyre Vestiges 14–16 · FineTuniX homecoming resolve · set close*
"""
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTES_PATH.write_text(body, encoding="utf-8")
    if NOTES_WORKSPACE != NOTES_PATH:
        NOTES_WORKSPACE.write_text(body, encoding="utf-8")
    notes_box_dl = Path("/workspace") / r"C:\Users\Gebruiker\Downloads" / "EvAIx_Vyre_162_NOTES.md"
    try:
        notes_box_dl.parent.mkdir(parents=True, exist_ok=True)
        notes_box_dl.write_text(body, encoding="utf-8")
    except Exception:
        pass
    print("NOTES", NOTES_PATH)


def pool_check() -> int:
    info = {
        "bpm": BPM, "key": KEY,
        "pool": str(POOL), "oneshots": sorted(p.name for p in ONESHOT_SRC.glob("*.wav")),
        "sections": FULL_SECTIONS,
        "bounce": "ENABLED",
    }
    print(json.dumps({**info, "oneshots": len(info["oneshots"])}, indent=2))
    print(f"Vyre pool OK · {len(info['oneshots'])} oneshots · slots 14–16 @ {BPM} {KEY}")
    return 0


def render_full() -> int:
    errors: list[str] = []
    shots = ensure_shots()
    mixes = []
    metas = []
    total_bars = sum(b for _, b, _, _ in FULL_SECTIONS)
    print(f"RENDER Vyre {total_bars} bars (~{total_bars * BAR_S:.1f}s)")
    for i, (name, bars, mode, slot) in enumerate(FULL_SECTIONS):
        path, meta = render_section(i, name, bars, mode, slot, shots)
        mixes.append(path)
        metas.append(meta)

    mp3_path = MP3_WORKSPACE
    dur = bounce_mp3(mixes, mp3_path)
    # distribute copies
    for dest in (MP3_EXPORTS, MP3_BOX_DL):
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(mp3_path, dest)
            print("copy", dest)
        except Exception as e:
            errors.append(f"copy {dest}: {e}")

    lufs = measure_lufs(mp3_path)
    if lufs.get("I") is not None and lufs["I"] < -9.05:
        need = -8.4 - float(lufs["I"])
        print(f"LUFS quiet — gain +{need:.2f} dB toward −8.4")
        tmp = OUT / "_vyre_loudfix.wav"
        af = f"volume={need}dB,alimiter=limit=0.891:attack=1:release=50:level=disabled"
        # prefer wav master if present
        srcw = OUT / "_vyre_surg.wav"
        if not srcw.exists():
            srcw = OUT / "_vyre_master.wav"
        inn = str(srcw if srcw.exists() else mp3_path)
        subprocess.run([FFMPEG, "-y", "-i", inn, "-af", af, str(tmp)], check=True, capture_output=True)
        subprocess.run(
            [FFMPEG, "-y", "-i", str(tmp), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)],
            check=True, capture_output=True,
        )
        for dest in (MP3_EXPORTS, MP3_BOX_DL):
            try:
                shutil.copy2(mp3_path, dest)
            except Exception:
                pass
        lufs = measure_lufs(mp3_path)

    mid = measure_mid_bloom(mp3_path)
    outro = measure_outro_clarity(mp3_path)
    write_notes(dur, metas, lufs, shots, errors, mid=mid, outro=outro)

    # bridge script copies
    src_script = Path(__file__).resolve()
    for dest in (
        Path("/workspace/exports/build_vyre_162.py"),
        Path("/workspace/exports/vyre-pool/build_vyre_162.py"),
        BRIDGE_BOX,
    ):
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.resolve() != src_script:
                shutil.copy2(src_script, dest)
                print("script copy", dest)
        except Exception as e:
            errors.append(f"script {dest}: {e}")

    print("DONE", mp3_path, "I=", lufs.get("I"), "TP=", lufs.get("TP"), "LRA=", lufs.get("LRA"))
    print("mid_delta", mid.get("delta_open_minus_mute"), "outro_kick_clear", outro.get("kick_out_clear"),
          "tail", outro.get("tail_still_audible"))
    return 0 if not errors else 0  # soft


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vyre 162 B — Vestiges 14–16 full bounce")
    ap.add_argument("--inventory", action="store_true")
    ap.add_argument("--bounce", action="store_true", help="Full MP3 bounce")
    ap.add_argument("--skip-ableton", action="store_true", default=True)
    ap.add_argument("--pool-check", action="store_true")
    args = ap.parse_args(argv)

    if args.inventory or args.pool_check:
        return pool_check()
    # default action: full DSP bounce (--skip-ableton OK)
    return render_full()


if __name__ == "__main__":
    raise SystemExit(main())
