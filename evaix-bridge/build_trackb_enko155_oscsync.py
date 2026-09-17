# -*- coding: utf-8 -*-
"""EvAIx Track B — Enko 155 Minor / OSC Sync / BD-Dist (NEW identity).

LOCKED: NOT MentalClean Morph DNA.
- Kick: ESX BD-* dry distorted one-shots (NOT kb_kick_sledge + SinKick blend)
- Lead: EMX-style OSC Sync saw (ModPitch + single-shot LFO, modest Depth)
- Spine: Dawn→Kick enter→Industrial perc→Sync tease→Drop A→Mute break→
         Dual acid/sync→Strip→Rebuild→Peak→Outro peel
- BPM 155, Minor (A minor industrial pocket)
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
BPM = 155.0
BAR_S = 4.0 * 60.0 / BPM
BEAT_S = 60.0 / BPM
STEP_S = BEAT_S / 4.0

_HERE = Path(__file__).resolve().parent
_CANDIDATE_SAMPLES = [
    _HERE / "samples" / "trackb-enko155" / "factory_src",
    Path("/workspace/samples/trackb-enko155/factory_src"),
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\trackb-enko155\factory_src"),
    Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav"),
]
FACTORY = next((p for p in _CANDIDATE_SAMPLES if p.exists()), _CANDIDATE_SAMPLES[0])

OUT = Path("/workspace/samples/trackb-enko155") if Path("/workspace").exists() else (
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\trackb-enko155")
)
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"; ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_DIR = OUT / "sections"; SECTION_DIR.mkdir(parents=True, exist_ok=True)

MP3_NAME = "EvAIx_TrackB_Enko155_OscSync.mp3"
MP3_WORKSPACE = Path("/workspace") / MP3_NAME if Path("/workspace").exists() else OUT / MP3_NAME
MP3_EXPORTS = Path("/workspace/exports") / MP3_NAME if Path("/workspace/exports").exists() else OUT / MP3_NAME
MP3_DOWNLOADS = Path(r"C:\Users\Gebruiker\Downloads") / MP3_NAME
NOTES_PATH = (
    Path("/workspace/exports/trackb_enko155_oscsync_notes.md")
    if Path("/workspace/exports").exists()
    else OUT / "trackb_enko155_oscsync_notes.md"
)

KICK_G = 1.48
BASS_G = KICK_G * (10 ** (-8.0 / 20.0))
HATS_G, OH_G, PERC_G = 0.14, 0.10, 0.22
SYNC_G, ACID_G, ATM_G, FX_G = 0.28, 0.16, 0.12, 0.10
TUBE_GAIN = 1.75
SYNC_WIDTH, SYNC_HAAS_MS = 0.20, 8.0
SYNC_RATIO, SYNC_MODPITCH = 2.35, 7
SYNC_LFO_DEPTH, SYNC_LFO_HZ = 0.085, 0.41
SYNC_ONESHOT_DEPTH, SYNC_ONESHOT_DECAY = 0.12, 0.28
SYNC_HPF, SYNC_LPF, SYNC_GRIT = 170.0, 3800.0, 1.45

AMINOR = np.array([110.00, 123.47, 130.81, 146.83, 164.81, 174.61, 196.00, 220.00], dtype=np.float64)
AMINOR_LOW = AMINOR / 2.0

FULL_SECTIONS = [
    ("dawn_atm", 16, "dawn"),
    ("kick_enter", 16, "kick_enter"),
    ("industrial_perc", 16, "ind_perc"),
    ("sync_tease", 16, "sync_tease"),
    ("drop_a", 32, "drop_a"),
    ("mute_break", 16, "mute_break"),
    ("dual_acid_sync", 32, "dual"),
    ("strip", 16, "strip"),
    ("rebuild", 24, "rebuild"),
    ("peak", 48, "peak"),
    ("outro_peel", 24, "outro"),
]

BD_PRIMARY = [
    "014_BD-15.wav", "016_BD-17.wav", "018_BD-19.wav", "019_BD-20.wav",
    "020_BD-21.wav", "012_BD-13.wav", "010_BD-11.wav", "008_BD-9.wav",
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
    return int(bars * 4.0 * 60.0 / BPM * SR)


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


def one_pole(x: np.ndarray, cutoff_hz: float, mode="lpf", q=0.12) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    # bilinear one-pole via lfilter (fast)
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


def tanh_drive(x: np.ndarray, amt: float) -> np.ndarray:
    return np.tanh(x * amt)


def valve_force(x: np.ndarray, tube_gain: float = TUBE_GAIN) -> np.ndarray:
    bias = 0.03
    norm = math.tanh(tube_gain)
    y = np.tanh((x + bias) * tube_gain) / norm - bias * 0.5
    return 0.9 * y + 0.1 * np.tanh(x * (tube_gain * 0.5))


def mild_compress(x: np.ndarray, thr=0.40, ratio=1.55) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    absx = np.abs(x)
    # approx envelope via causal IIR on abs
    atk = math.exp(-1.0 / (SR * 0.0025))
    rel = math.exp(-1.0 / (SR * 0.12))
    env = np.zeros_like(x)
    e = 0.0
    for i, a in enumerate(absx):
        e = a + (e - a) * (atk if a > e else rel)
        env[i] = e
    over = np.maximum(0.0, env - thr)
    gain = np.where(env > thr, (thr + over / ratio) / np.maximum(env, 1e-9), 1.0)
    return x * gain * 1.08


def place(buf: np.ndarray, sample: np.ndarray, beat: float, gain: float = 1.0):
    i0 = int(beat * BEAT_S * SR)
    if i0 >= len(buf) or i0 < 0:
        return
    n = min(len(sample), len(buf) - i0)
    buf[i0:i0 + n] += sample[:n] * gain


def haas_widen(mono: np.ndarray, width=SYNC_WIDTH, delay_ms=SYNC_HAAS_MS):
    n = len(mono)
    if width <= 0.001:
        return mono.copy(), mono.copy()
    d = max(1, int(delay_ms * 0.001 * SR))
    delayed = np.zeros(n)
    delayed[d:] = mono[:-d]
    return mono + delayed * width * 0.55, mono - delayed * width * 0.55


def modpitch_hz(base_hz: float, edit2: float) -> float:
    return base_hz * (2.0 ** (edit2 * (2.0 / 63.0)))


def prepare_bd_dist(name: str, drive: float = 2.35) -> np.ndarray:
    src = FACTORY / name
    if not src.exists():
        raise FileNotFoundError(src)
    raw = read_wav(src)
    y = one_pole(raw, 38.0, mode="hpf", q=0.08)
    y = tanh_drive(y, drive)
    y = mild_compress(y, thr=0.42, ratio=1.45)
    peak = float(np.max(np.abs(y))) + 1e-12
    return y / peak * 0.95


def synth_sub_bass() -> np.ndarray:
    n = int(0.20 * SR)
    t = np.arange(n) / SR
    env = np.exp(-t / 0.10)
    pitch = 48.0 * (1.0 + 1.6 * np.exp(-t / 0.016))
    phase = np.cumsum(2 * np.pi * pitch / SR)
    return mild_compress(np.sin(phase) * env * 0.9, thr=0.48, ratio=1.35)


def synth_atm_noise(n: int, seed: int = 77) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, n)
    x = one_pole(x, 400.0, mode="hpf")
    x = one_pole(x, 2800.0, mode="lpf")
    t = np.arange(n) / SR
    x *= 0.35 + 0.65 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t))
    return x * 0.25


def osc_sync_note(freq: float, dur_s: float, accent: bool = False, oneshot: bool = True,
                  ratio: float = SYNC_RATIO) -> np.ndarray:
    """EMX-style OSC Sync saw: hard-sync slave to master; ModPitch + LFO."""
    n = max(8, int(dur_s * SR))
    t = np.arange(n) / SR
    master_hz = modpitch_hz(freq, SYNC_MODPITCH)
    lfo = np.sin(2 * np.pi * SYNC_LFO_HZ * t)
    shot = np.exp(-t / SYNC_ONESHOT_DECAY) if oneshot else np.zeros(n)
    mod = 1.0 + SYNC_LFO_DEPTH * lfo + SYNC_ONESHOT_DEPTH * shot
    slave_hz = master_hz * ratio * mod
    master_phase = np.cumsum(master_hz * mod / SR)
    master_frac = np.mod(master_phase, 1.0)
    resets = np.where(np.diff(master_frac, prepend=master_frac[0]) < -0.5)[0]
    # hard-sync via segment-wise phase integrate between master wraps
    bounds = np.concatenate(([0], resets, [n]))
    slave = np.zeros(n)
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b <= a:
            continue
        seg = np.cumsum(slave_hz[a:b] / SR)
        slave[a:b] = 2.0 * (seg - np.floor(seg)) - 1.0
    a = 0.004 if not accent else 0.002
    d = 0.22 if not accent else 0.16
    slev = 0.45 if not accent else 0.55
    r = 0.12
    env = np.full(n, slev)
    atk_n = max(1, int(a * SR)); dec_n = max(1, int(d * SR)); rel_n = max(1, int(r * SR))
    env[:atk_n] = np.linspace(0.0, 1.0, atk_n, endpoint=False)
    if atk_n + dec_n <= n:
        env[atk_n:atk_n + dec_n] = np.linspace(1.0, slev, dec_n, endpoint=False)
    if rel_n < n:
        env[-rel_n:] = np.linspace(slev, 0.0, rel_n)
    y = slave * env * (1.15 if accent else 0.95)
    y = tanh_drive(y, SYNC_GRIT)
    y = one_pole(y, SYNC_HPF, mode="hpf")
    y = one_pole(y, SYNC_LPF, mode="lpf")
    return y


def acid_support_note(freq: float, dur_s: float, accent: bool = False) -> np.ndarray:
    """Supporting dual acid — quieter; NOT Morph RingMod/303 hero."""
    n = max(8, int(dur_s * SR))
    t = np.arange(n) / SR
    phase = np.cumsum(2 * np.pi * freq / SR)
    saw = 2.0 * (phase / (2 * np.pi) - np.floor(0.5 + phase / (2 * np.pi)))
    cut0 = 420.0 if not accent else 900.0
    cut = cut0 + (2200.0 if accent else 1400.0) * np.exp(-t / 0.18)
    # approximate moving cutoff via 2-stage one_pole blend
    y_lo = one_pole(saw, float(np.percentile(cut, 25)), mode="lpf")
    y_hi = one_pole(saw, float(np.percentile(cut, 75)), mode="lpf")
    blend = np.clip((cut - cut.min()) / max(1e-9, cut.max() - cut.min()), 0, 1)
    y = y_lo * (1 - blend) + y_hi * blend
    env = np.exp(-t / (0.20 if accent else 0.28))
    y = tanh_drive(y * env * (1.1 if accent else 0.85), 1.35)
    return one_pole(y, 150.0, mode="hpf")


def sync_pattern(mode: str, bars: int, seed: int):
    rng = np.random.default_rng(seed)
    steps = bars * 16
    events = []
    if mode in ("dawn", "mute_break"):
        return events
    if mode == "sync_tease":
        for s in range(0, steps, 16):
            events.append((s, int(rng.integers(0, 5)), True, 6))
            if rng.random() < 0.45:
                events.append((s + 10, int(rng.integers(2, 7)), False, 3))
        return events
    if mode in ("kick_enter", "ind_perc", "strip"):
        for s in range(0, steps, 32):
            events.append((s + 8, int(rng.integers(0, 4)), False, 4))
        return events
    dens = {"rebuild": 0.28, "dual": 0.42, "drop_a": 0.38, "peak": 0.50, "outro": 0.18}.get(mode, 0.30)
    cycle = 14 if mode in ("dual", "peak") else 16
    for s in range(steps):
        local = s % cycle
        if local == 0 or (rng.random() < dens and local not in (1, 5, 9)):
            accent = local in (0, 4, 8, 12) or rng.random() < 0.2
            note = int(rng.integers(0, len(AMINOR)))
            if accent and rng.random() < 0.25:
                note = min(len(AMINOR) - 1, note + 3)
            dur = 5 if (mode == "peak" and local == 0) else (3 if accent else 2)
            events.append((s, note, accent, dur))
    return events


def acid_pattern(mode: str, bars: int, seed: int):
    rng = np.random.default_rng(seed + 99)
    steps = bars * 16
    events = []
    if mode not in ("dual", "peak", "drop_a", "rebuild"):
        return events
    dens = 0.35 if mode == "dual" else 0.22
    for s in range(steps):
        if s % 16 in (0, 3, 6, 10, 12) or rng.random() < dens * 0.15:
            if rng.random() < 0.55 or s % 4 == 0:
                events.append((s, int(rng.integers(0, len(AMINOR_LOW))), s % 4 == 0, 2))
    return events


def kit_for_mode(mode: str, shots: dict) -> dict:
    bd_map = {
        "dawn": shots["bd_veiled"], "kick_enter": shots["bd_a"], "ind_perc": shots["bd_b"],
        "sync_tease": shots["bd_c"], "drop_a": shots["bd_a"], "mute_break": shots["bd_thin"],
        "dual": shots["bd_d"], "strip": shots["bd_b"], "rebuild": shots["bd_c"],
        "peak": shots["bd_e"], "outro": shots["bd_thin"],
    }
    hat_map = {
        "dawn": shots["hh1"], "kick_enter": shots["hh1"], "ind_perc": shots["hh7"],
        "sync_tease": shots["hh3"], "drop_a": shots["hh5"], "mute_break": shots["hh2"],
        "dual": shots["hh7"], "strip": shots["hh2"], "rebuild": shots["hh3"],
        "peak": shots["hh5"], "outro": shots["hh1"],
    }
    oh_map = {
        "dawn": shots["oh1"], "kick_enter": shots["oh1"], "ind_perc": shots["oh7"],
        "sync_tease": shots["oh3"], "drop_a": shots["oh3"], "mute_break": shots["oh1"],
        "dual": shots["oh7"], "strip": shots["oh1"], "rebuild": shots["oh3"],
        "peak": shots["oh7"], "outro": shots["oh1"],
    }
    gains = {
        "dawn": dict(kick=0.0, bass=0.0, hats=0.15, oh=0.0, perc=0.05, sync=0.0, acid=0.0, atm=1.0, fx=0.4),
        "kick_enter": dict(kick=0.85, bass=0.35, hats=0.25, oh=0.05, perc=0.15, sync=0.08, acid=0.0, atm=0.45, fx=0.2),
        "ind_perc": dict(kick=0.95, bass=0.55, hats=0.55, oh=0.35, perc=0.95, sync=0.10, acid=0.0, atm=0.25, fx=0.35),
        "sync_tease": dict(kick=0.90, bass=0.70, hats=0.40, oh=0.20, perc=0.35, sync=0.75, acid=0.0, atm=0.15, fx=0.25),
        "drop_a": dict(kick=1.0, bass=1.0, hats=0.85, oh=0.55, perc=0.55, sync=1.0, acid=0.35, atm=0.05, fx=0.2),
        "mute_break": dict(kick=0.25, bass=0.15, hats=0.05, oh=0.0, perc=0.0, sync=0.0, acid=0.0, atm=0.7, fx=0.55),
        "dual": dict(kick=1.0, bass=0.95, hats=0.75, oh=0.50, perc=0.45, sync=0.95, acid=1.0, atm=0.05, fx=0.25),
        "strip": dict(kick=0.80, bass=0.45, hats=0.20, oh=0.0, perc=0.15, sync=0.25, acid=0.0, atm=0.2, fx=0.15),
        "rebuild": dict(kick=0.70, bass=0.65, hats=0.50, oh=0.30, perc=0.40, sync=0.55, acid=0.40, atm=0.15, fx=0.35),
        "peak": dict(kick=1.05, bass=1.0, hats=0.95, oh=0.70, perc=0.70, sync=1.1, acid=0.75, atm=0.0, fx=0.3),
        "outro": dict(kick=0.55, bass=0.25, hats=0.15, oh=0.05, perc=0.10, sync=0.35, acid=0.0, atm=0.55, fx=0.45),
    }
    stories = {
        "dawn": "Dawn atm — noise/SFX bed, no kick; industrial haze",
        "kick_enter": "Kick enter — dry BD-Dist lands; bass ghost; hats sparse",
        "ind_perc": "Industrial perc — JunkPerc/rim/tom grid; HH-7C; kick solid",
        "sync_tease": "OSC Sync tease — bar-hit Sync saw ModPitch+oneshot LFO",
        "drop_a": "Drop A — full kick+bass mono; Sync lead hero; light support acid",
        "mute_break": "Mute break — kick ~25%, silence/space, atm peel",
        "dual": "Dual acid/sync — Sync hero + quieter dual acid; denser hats",
        "strip": "Strip — remove OH/acid; kick+thin sync ghosts",
        "rebuild": "Rebuild — layers return; filter opens; Sync densifies",
        "peak": "Peak — max kick; Sync Depth present; dual acid accents",
        "outro": "Outro peel — kick thins; Sync peels; atm returns",
    }
    kick_steps = {
        "dawn": [], "kick_enter": [0, 4, 8, 12], "ind_perc": [0, 4, 8, 12],
        "sync_tease": [0, 4, 8, 12], "drop_a": [0, 4, 8, 12], "mute_break": [0, 8],
        "dual": [0, 4, 8, 12], "strip": [0, 4, 8, 12], "rebuild": [0, 4, 8, 12],
        "peak": [0, 4, 8, 12], "outro": [0, 8],
    }
    hat_steps = {
        "dawn": [2, 6, 10, 14], "kick_enter": [2, 6, 10, 14],
        "ind_perc": [1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15],
        "sync_tease": [2, 6, 8, 10, 14], "drop_a": [2, 6, 10, 14, 3, 11],
        "mute_break": [6], "dual": [1, 2, 5, 6, 9, 10, 13, 14],
        "strip": [2, 10], "rebuild": [2, 6, 10, 14],
        "peak": [1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15], "outro": [2, 10],
    }
    bd_name = {
        "dawn": "veiled BD-15", "kick_enter": BD_PRIMARY[0], "ind_perc": BD_PRIMARY[1],
        "sync_tease": BD_PRIMARY[2], "drop_a": BD_PRIMARY[0], "mute_break": "thin BD-17",
        "dual": BD_PRIMARY[3], "strip": BD_PRIMARY[1], "rebuild": BD_PRIMARY[2],
        "peak": BD_PRIMARY[4], "outro": "thin BD-17",
    }[mode]
    return {
        "kick": bd_map[mode], "hat": hat_map[mode], "oh": oh_map[mode],
        "gains": gains[mode], "story": stories[mode],
        "kick_steps": kick_steps[mode], "hat_steps": hat_steps[mode], "bd_name": bd_name,
    }


def ensure_shots() -> dict:
    print("FACTORY", FACTORY)
    used = []
    bds = {}
    keys = ["bd_a", "bd_b", "bd_c", "bd_d", "bd_e", "bd_f", "bd_g", "bd_h"]
    for i, name in enumerate(BD_PRIMARY):
        key = keys[i]
        bds[key] = prepare_bd_dist(name, drive=2.2 + 0.08 * i)
        write_mono(ONESHOT / f"{key}_{name}", bds[key], 0.94)
        used.append(name)
    bds["bd_veiled"] = one_pole(bds["bd_a"], 85.0, mode="lpf") * 0.55
    bds["bd_thin"] = one_pole(bds["bd_b"], 100.0, mode="lpf") * 0.72

    def load_perc(name, drive=1.05, hpf=0.0, lpf=9000.0):
        y = read_wav(FACTORY / name)
        if hpf:
            y = one_pole(y, hpf, mode="hpf")
        y = tanh_drive(y, drive)
        y = one_pole(y, lpf, mode="lpf")
        used.append(name)
        return y

    shots = dict(bds)
    shots["hh1"] = load_perc("054_HH-1C.wav", 1.0, 4000, 14000)
    shots["hh2"] = load_perc("056_HH-2C.wav", 1.0, 4000, 14000)
    shots["hh3"] = load_perc("058_HH-3C.wav", 1.05, 3500, 14000)
    shots["hh5"] = load_perc("062_HH-5C.wav", 1.05, 3500, 14000)
    shots["hh7"] = load_perc("066_HH-7C.wav", 1.1, 3000, 14000)
    shots["oh1"] = load_perc("055_HH-1O.wav", 1.0, 3000, 12000)
    shots["oh3"] = load_perc("059_HH-3O.wav", 1.0, 3000, 12000)
    shots["oh7"] = load_perc("067_HH-7O.wav", 1.05, 2800, 12000)
    shots["rim1"] = load_perc("045_Rim-1.wav", 1.2, 800, 8000)
    shots["rim3"] = load_perc("047_Rim-3.wav", 1.3, 900, 9000)
    shots["clap1"] = load_perc("048_Clap-1.wav", 1.15, 600, 9000)
    shots["clap5"] = load_perc("052_Clap-5.wav", 1.2, 700, 9500)
    shots["tom1"] = load_perc("076_Tom-1.wav", 1.3, 80, 4000)
    shots["tom3"] = load_perc("078_Tom-3.wav", 1.25, 60, 3500)
    shots["junk"] = load_perc("092_JunkPerc.wav", 1.4, 200, 7000)
    shots["sfx1"] = load_perc("102_SFX-1.wav", 1.1, 150, 6000)
    shots["sfx3"] = load_perc("104_SFX-3.wav", 1.05, 100, 5000)
    shots["noise"] = load_perc("200_Noise.wav", 1.0, 200, 8000)
    shots["crash"] = load_perc("073_Crash-1.wav", 1.0, 200, 12000)
    shots["ride"] = load_perc("068_Ride-1.wav", 1.0, 2000, 12000)
    shots["bass"] = synth_sub_bass()
    write_mono(ONESHOT / "bass_sub.wav", shots["bass"], 0.9)
    shots["used"] = used
    print("shots ready", len(used), "BD family", BD_PRIMARY[:5])
    return shots


def render_section(idx: int, name: str, bars: int, mode: str, shots: dict):
    N = section_n(bars)
    trk_k = np.zeros(N); trk_b = np.zeros(N); trk_h = np.zeros(N); trk_oh = np.zeros(N)
    trk_p = np.zeros(N); trk_sync = np.zeros(N); trk_acid = np.zeros(N)
    trk_atm = np.zeros(N); trk_fx = np.zeros(N)
    kit = kit_for_mode(mode, shots)
    g = kit["gains"]
    seed = 0xB155 + idx * 17

    for bar in range(bars):
        for st in kit["kick_steps"]:
            beat = bar * 4 + st / 4.0
            place(trk_k, kit["kick"], beat, 1.0)
            place(trk_b, shots["bass"], beat, 1.0)
        if mode == "ind_perc":
            place(trk_p, shots["junk"], bar * 4 + 1.0, 0.85)
            place(trk_p, shots["rim1"], bar * 4 + 1.5, 0.7)
            place(trk_p, shots["tom1"], bar * 4 + 2.75, 0.55)
            if bar % 2 == 1:
                place(trk_p, shots["clap5"], bar * 4 + 1.0, 0.5)
        elif mode in ("drop_a", "dual", "peak"):
            if bar % 2 == 0:
                place(trk_p, shots["rim3"], bar * 4 + 1.0, 0.45)
            if bar % 4 == 3:
                place(trk_p, shots["clap1"], bar * 4 + 1.0, 0.55)
            if mode == "peak" and bar % 8 == 7:
                place(trk_p, shots["crash"], bar * 4, 0.5)
        elif mode == "rebuild":
            place(trk_p, shots["tom3"], bar * 4 + 2.0, 0.4)
            if bar % 2 == 0:
                place(trk_p, shots["junk"], bar * 4 + 3.0, 0.35)
        elif mode == "kick_enter" and bar >= bars // 2:
            place(trk_p, shots["rim1"], bar * 4 + 1.0, 0.35)
        for st in kit["hat_steps"]:
            beat = bar * 4 + st / 4.0
            place(trk_h, kit["hat"], beat, 0.85 if st % 4 == 2 else 0.65)
        if mode in ("ind_perc", "drop_a", "dual", "peak", "rebuild") and bar % 2 == 1:
            place(trk_oh, kit["oh"], bar * 4 + 1.5, 0.7)
        if mode == "peak" and bar % 4 == 0:
            place(trk_oh, kit["oh"], bar * 4 + 3.5, 0.55)

    if g["atm"] > 0.01:
        trk_atm += synth_atm_noise(N, seed=seed)
        rng = np.random.default_rng(seed)
        for bar in range(0, bars, 2):
            place(trk_fx, shots["sfx1"] if bar % 4 == 0 else shots["sfx3"], bar * 4 + rng.uniform(0, 2), 0.5)
            if mode in ("dawn", "mute_break", "outro"):
                place(trk_fx, shots["noise"], bar * 4, 0.25)

    for step, note_i, accent, dur_steps in sync_pattern(mode, bars, seed):
        freq = float(AMINOR[note_i % len(AMINOR)])
        note = osc_sync_note(freq, dur_steps * STEP_S, accent=accent, oneshot=True)
        place(trk_sync, note, step / 4.0, 1.15 if accent else 0.9)

    for step, note_i, accent, dur_steps in acid_pattern(mode, bars, seed):
        freq = float(AMINOR_LOW[note_i % len(AMINOR_LOW)])
        note = acid_support_note(freq, dur_steps * STEP_S, accent=accent)
        place(trk_acid, note, step / 4.0, 1.0)

    trk_k *= KICK_G * g["kick"]; trk_b *= BASS_G * g["bass"]
    trk_h *= HATS_G * g["hats"]; trk_oh *= OH_G * g["oh"]; trk_p *= PERC_G * g["perc"]
    trk_sync *= SYNC_G * g["sync"]; trk_acid *= ACID_G * g["acid"]
    trk_atm *= ATM_G * g["atm"]; trk_fx *= FX_G * g["fx"]

    mono_bed = trk_k + trk_b + trk_h + trk_oh + trk_p + trk_atm
    wide_src = trk_sync + trk_acid * 0.85 + trk_fx
    mono_bed = valve_force(mono_bed, TUBE_GAIN * 0.85)
    wide_src = valve_force(wide_src, TUBE_GAIN)

    macro = {
        "dawn": 0.35, "kick_enter": 0.55, "ind_perc": 0.7, "sync_tease": 0.75,
        "drop_a": 0.95, "mute_break": 0.40, "dual": 0.92, "strip": 0.55,
        "rebuild": 0.72, "peak": 1.0, "outro": 0.45,
    }[mode]
    cut = 1800.0 + 7000.0 * macro
    mono_bed = one_pole(mono_bed, cut, mode="lpf")
    wide_src = one_pole(wide_src, cut * 1.05, mode="lpf")
    wl, wr = haas_widen(wide_src, SYNC_WIDTH if g["sync"] > 0.2 or g["acid"] > 0.2 else 0.08)
    left = mono_bed + wl; right = mono_bed + wr
    mix_path = SECTION_DIR / f"{idx:02d}_{name}_mix.wav"
    write_stereo_lr(mix_path, left, right, 0.90)
    meta = {
        "name": name, "mode": mode, "bars": bars, "story": kit["story"], "bd": kit["bd_name"],
        "gains": g, "sync_events": len(sync_pattern(mode, bars, seed)),
        "acid_events": len(acid_pattern(mode, bars, seed)),
    }
    print(f"  section {idx:02d} {name}: {bars} bars")
    return mix_path, meta


def bounce_mp3(mixes, mp3_path: Path) -> float:
    concat_list = OUT / "_trackb_concat.txt"
    raw = OUT / "_trackb_raw.wav"
    mastered = OUT / "_trackb_master.wav"
    with concat_list.open("w", encoding="utf-8") as f:
        for p in mixes:
            f.write(f"file '{p.as_posix()}'\n")
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw)],
        check=True, capture_output=True,
    )
    af = (
        "acompressor=threshold=-18dB:ratio=1.30:attack=8:release=120:makeup=1.5,"
        "equalizer=f=60:t=q:w=0.7:g=1.2,"
        "equalizer=f=2800:t=q:w=1.0:g=1.4,"
        "equalizer=f=6500:t=q:w=1.0:g=1.2,"
        "loudnorm=I=-8.5:TP=-1.5:LRA=8,"
        "volume=-0.4dB,"
        "alimiter=limit=0.841:attack=1:release=50:level=disabled"
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
    dur = sum(b for _, b, _ in FULL_SECTIONS) * BAR_S
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
    m_tp = re.search(r"Peak:\s+(-?[0-9.]+)\s+dBFS", summ) or re.search(
        r"True peak:\s+(-?[0-9.]+)\s+dBTP", summ, re.I
    )
    if m_i: out["I"] = float(m_i.group(1))
    if m_tp: out["TP"] = float(m_tp.group(1))
    if m_lra: out["LRA"] = float(m_lra.group(1))
    print("LUFS", path.name, "I=", out["I"], "TP=", out["TP"], "LRA=", out["LRA"])
    return out


def write_notes(dur: float, metas: list, lufs: dict, shots: dict, errors: list):
    t0 = 0.0
    lines = [
        "# EvAIx Track B — Enko 155 / OSC Sync / BD-Dist",
        "",
        f"**MP3:** `{MP3_NAME}`",
        f"- Downloads: `C:\\\\Users\\\\Gebruiker\\\\Downloads\\\\{MP3_NAME}`",
        f"- Workspace: `/workspace/{MP3_NAME}`",
        f"- Exports: `/workspace/exports/{MP3_NAME}`",
        f"- Script: `/workspace/build_trackb_enko155_oscsync.py`",
        f"- Bridge: `C:\\\\Users\\\\Gebruiker\\\\ableton-mcp\\\\evaix-bridge\\\\build_trackb_enko155_oscsync.py`",
        "",
        f"Duration: **{dur:.2f} s** · BPM **{BPM:.0f}** · Key **A Minor** (Enko industrial pocket)",
        "",
        "## Measured loudness",
        f"- **I** = {lufs.get('I')} LUFS (target −8…−9)",
        f"- **TP** = {lufs.get('TP')} dB (target ≤ −1.0 dBTP)",
        f"- **LRA** = {lufs.get('LRA')} LU (allowed to breathe)",
        "",
        "## Kick sources (BD-Dist / dry distorted) — NOT Morph DNA",
        "- Primary family: ESX factory BD one-shots with dry tanh grit + mild compress",
        f"- Used: {', '.join(BD_PRIMARY)}",
        "- Explicitly **NOT** `kb_kick_sledge` + `146_SinKick` MentalClean blend as primary voice",
        "- Per-chapter rotation of BD-15 / BD-17 / BD-19 / BD-20 / BD-21 (+ veiled/thin variants)",
        "- CRISP acoustic path (Valve Force mild, no dense smash)",
        "",
        "## OSC Sync lead params (EMX-style) — NOT Morph RingMod+303 hero",
        "- Type: **OSC Sync** hard-sync saw (slave reset on master wrap)",
        f"- Sync ratio: **{SYNC_RATIO}**",
        f"- ModPitch (EDIT2-ish): **{SYNC_MODPITCH}** → pitch offset via 2^(edit·2/63)",
        f"- Continuous LFO: **{SYNC_LFO_HZ} Hz**, Depth **{SYNC_LFO_DEPTH}** (modest)",
        f"- Single-shot LFO on attack: Depth **{SYNC_ONESHOT_DEPTH}**, decay **{SYNC_ONESHOT_DECAY}s**",
        f"- Filter: HPF {SYNC_HPF} Hz / LPF {SYNC_LPF} Hz · grit tanh {SYNC_GRIT}",
        f"- Width: Haas {SYNC_HAAS_MS} ms @ {SYNC_WIDTH} on sync/FX only; kick/bass mono",
        "- Supporting dual acid is quieter saw+LPF — **not** Morph RingMod / same 303 stack as hero",
        "",
        "## How this differs from Morph / FTX DNA",
        "| | Morph / FTX | Track B |",
        "|--|--|--|",
        "| BPM | 162 | **155** |",
        "| Kick | sledge + SinKick MentalClean | **ESX BD-Dist dry** |",
        "| Lead | RingMod + 303 hero | **OSC Sync saw** |",
        "| Spine | Intro→Predrop→Drop×3 | **Dawn→…→Peak→Outro peel** |",
        "| Poly | 13/15 Morph phrases | optional cycle-14, new phrases |",
        "",
        "## Section time map",
    ]
    for m in metas:
        end = t0 + m["bars"] * BAR_S
        lines.append(
            f"- **{t0:.1f}–{end:.1f}s** `{m['name']}` ({m['bars']} bars) — {m['story']} "
            f"[bd={m['bd']}; sync_ev={m['sync_events']}; acid_ev={m['acid_events']}]"
        )
        t0 = end
    lines.extend([
        "",
        "## Doctrine kept",
        "- Free-party / mental tekno / acidcore — no commercial EDM drops",
        "- Kick-dominated; bass ≈ −8 dB under kick (BASS_G/KICK_G)",
        "- Valve Force mild grit; CRISP acoustic not dense smash",
        "- Master: loudnorm I=-8.5 TP=-1.5 + alimiter ≈ −1.5 dBTP ceiling",
        "",
        f"Samples used: {shots.get('used')}",
        f"Errors: {errors or 'none'}",
        "Ableton: skipped (--skip-ableton / DSP bounce)",
        "",
    ])
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTES_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("NOTES", NOTES_PATH)


def main():
    errors = []
    skip_ab = True  # prefer skip; don't hang on AbletonMCP
    print("=== Track B Enko155 OSC Sync / BD-Dist ===")
    print("FACTORY", FACTORY, "exists", FACTORY.exists())
    print("skip_ableton", skip_ab)
    if "--help-ableton" in sys.argv:
        print("Ableton load not in this bounce; use continue-loader pattern if needed.")
    shots = ensure_shots()
    mixes, metas = [], []
    t0 = 0.0
    for idx, (name, bars, mode) in enumerate(FULL_SECTIONS):
        path, meta = render_section(idx, name, bars, mode, shots)
        meta["start_s"] = round(t0, 2)
        meta["end_s"] = round(t0 + bars * BAR_S, 2)
        t0 = meta["end_s"]
        mixes.append(path); metas.append(meta)

    print("=== Bounce MP3 ===")
    primary = MP3_WORKSPACE if Path("/workspace").exists() else MP3_DOWNLOADS
    try:
        dur = bounce_mp3(mixes, primary)
    except Exception as e:
        errors.append(f"mp3: {e}"); print("FAIL mp3", e); dur = 0.0; primary = None

    if primary and primary.exists():
        if Path("/workspace/exports").exists():
            shutil.copy2(primary, MP3_EXPORTS)
            print("copied exports", MP3_EXPORTS)
        try:
            if MP3_DOWNLOADS.parent.exists():
                shutil.copy2(primary, MP3_DOWNLOADS)
                print("copied Downloads", MP3_DOWNLOADS)
        except Exception as e:
            errors.append(f"downloads_copy: {e}")
            print("Downloads copy deferred:", e)

    lufs = {"I": None, "TP": None, "LRA": None}
    if primary and primary.exists():
        try:
            lufs = measure_lufs(primary)
        except Exception as e:
            errors.append(f"lufs: {e}")

    write_notes(dur, metas, lufs, shots, errors)
    if Path("/workspace").exists():
        shutil.copy2(NOTES_PATH, Path("/workspace/trackb_enko155_oscsync_notes.md"))

    print("MP3_PATH", str(primary))
    print("MP3_EXISTS", bool(primary and primary.exists()))
    print("LUFS_I", lufs.get("I"), "LUFS_TP", lufs.get("TP"), "LUFS_LRA", lufs.get("LRA"))
    print("ERRORS", errors)
    print("DONE build_trackb_enko155_oscsync")


if __name__ == "__main__":
    main()
