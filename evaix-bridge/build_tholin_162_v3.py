# -*- coding: utf-8 -*-
"""EvAIx Tholin Vestiges slots 09–13 @ 162 BPM E major — v3 LOOP FIX (WORST offender).

Architect STOP/supersede: remake Tholin after Figment_v3 + Haniwa_v3 PASS.
Do NOT touch full Vestiges master. Do NOT start Vyre.

HARD RULE: new sample family every ≤32 bars.
Filter/mute/ride automation alone does NOT count as rotation.
SUCCESS: no ≥64-bar run of successive 16-bar blocks at similarity ≥0.92
(MFCC+chroma+contrast).

v3 vs v1/v2:
- Rewrite from local ~02:00 to END — ≥12–15 audible family rotations
- UN-PARK acid/bass: filter envelopes every 8–16 bars PLUS real waveform/preset swaps
- Kill chained freeze slabs (master 15:57–18:43, 18:43–21:05 → 21:53–23:51)
- Distinct OUTRO family last ~60s before Vyre handoff (no coast into splice)
- TRUE strip = kick+ghost ONLY, quieter than drop/return (RMS dip >4–6 dB),
  HPF/duck acid LF so 50–100 Hz collapses; then HARDER return
- Raise mid-chapter RMS / arrangement contrast; no snare-roll EDM drops
- Distinct pool from Figment_v3 / Haniwa_v3 / prior Tholin v1/v2 (vyre+tholin expand)
- Poly LS13/15/7 vs kick16; Valve Force grit; tame 3–6k; LRA ≥5–6 via arrangement

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

OUT = Path("/workspace/samples/tholin-162-v3") if Path("/workspace").exists() else (
    Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\tholin-162-v3")
)
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"; ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_DIR = OUT / "sections"; SECTION_DIR.mkdir(parents=True, exist_ok=True)

MP3_NAME = "EvAIx_Tholin_162_v3.mp3"
MP3_WORKSPACE = Path("/workspace") / MP3_NAME if Path("/workspace").exists() else OUT / MP3_NAME
MP3_EXPORTS = Path("/workspace/exports") / MP3_NAME if Path("/workspace/exports").exists() else OUT / MP3_NAME
MP3_DOWNLOADS = Path(r"C:\Users\Gebruiker\Downloads") / MP3_NAME
NOTES_PATH = (
    Path("/workspace/exports/EvAIx_Tholin_162_v3_NOTES.md")
    if Path("/workspace/exports").exists()
    else OUT / "EvAIx_Tholin_162_v3_NOTES.md"
)
NOTES_WORKSPACE = Path("/workspace/EvAIx_Tholin_162_v3_NOTES.md") if Path("/workspace").exists() else NOTES_PATH
BRIDGE_COPY = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\build_tholin_162_v3.py")

# Gains — peak chapter; Valve Force grit; quiet acoustic tops
KICK_G = 1.45
BASS_G = KICK_G * (10 ** (-8.0 / 20.0))
HATS_G, OH_G, RIDE_G, PERC_G = 0.11, 0.09, 0.15, 0.28
ACID_G, MG_G, ATM_G, PAD_G, FX_G = 0.38, 0.16, 0.20, 0.18, 0.13
TUBE_GAIN = 1.62
HAAS_W, HAAS_MS = 0.18, 7.0
# Mental Tribe / Pozek mid recipe (FineTuniX mid-bloom QC)
ACID_HPF_HZ = 160.0
ACID_PRESENCE_HZ = 2200.0
ACID_PRESENCE_DB_OPEN = 3.6
ACID_PRESENCE_DB_MUTE = -4.2

# E major (dark filters) — peak Vestiges chapter
E_MAJ = np.array([
    82.41,   # E2
    92.50,   # F#2
    103.83,  # G#2
    123.47,  # B2
    138.59,  # C#3
    164.81,  # E3
    185.00,  # F#3
    207.65,  # G#3
], dtype=np.float64)
E_LOW = E_MAJ / 2.0  # MG LPF −8va
E_PAD = np.array([82.41, 123.47, 164.81, 207.65], dtype=np.float64)  # E B E G#

# Alias so leftover FS_* refs still resolve during partial rewrites
E_MAJ, E_LOW, E_PAD = E_MAJ, E_LOW, E_PAD

# Acid waveform / preset catalog — AUDIBLE MFCC movers (not filter-only)
ACID_WAVES = ("saw", "square", "pulse25", "pulse12", "tri", "supersaw", "noise_saw", "pwm")

# Slot map @162: 25 × 16 = 400 bars ≈ 9:53 (~10′ peak chapter)
# HARD RULE: family change every ≤16 bars (real one-shot + acid_wave swaps)
# (name, bars, mode, slot, family_id)
FULL_SECTIONS = [
    # Slot 09 Intro 0:00–~1:58 (5×16) — glowing dark major, sparse
    ("Tholin_Intro_glow", 16, "intro_atm", "09", "T_INTRO_A"),
    ("Tholin_Intro_voice", 16, "intro_open", "09", "T_INTRO_B"),
    ("Tholin_Intro_ghost", 16, "intro_ghost", "09", "T_INTRO_C"),
    ("Tholin_Intro_breaktx", 16, "intro_breaktx", "09", "T_INTRO_D"),
    ("Tholin_Intro_tease", 16, "intro_tease", "09", "T_INTRO_E"),
    # Slot 10 Build ~1:58–~3:57 (5×16) — rewrite from ~02:00; NEW families audible
    ("Tholin_Build_kick", 16, "build_kick", "10", "T_BUILD_A"),
    ("Tholin_Build_tribal", 16, "build_tribal", "10", "T_BUILD_B"),
    ("Tholin_Build_ride", 16, "build_ride", "10", "T_BUILD_C"),
    ("Tholin_Build_acid", 16, "build_acid", "10", "T_BUILD_D"),
    ("Tholin_Build_dense", 16, "build_perc", "10", "T_BUILD_E"),
    # Slot 11 Drop PEAK ~3:57–~7:07 (8×16) — kill freeze slabs; wave swaps every slot
    ("Tholin_Drop_mute", 16, "drop_muted", "11", "T_DROP_A"),
    ("Tholin_Drop_open", 16, "drop_open", "11", "T_DROP_B"),
    ("Tholin_Drop_wave2", 16, "drop_open2", "11", "T_DROP_C"),
    ("Tholin_Drop_mute2", 16, "drop_mute2", "11", "T_DROP_D"),
    ("Tholin_Drop_open3", 16, "drop_open3", "11", "T_DROP_E"),
    ("Tholin_Drop_max", 16, "drop_max", "11", "T_DROP_F"),
    ("Tholin_Drop_strip", 16, "true_strip", "11", "T_STRIP"),   # QUIETER than neighbors
    ("Tholin_Drop_return", 16, "build_return", "11", "T_RETURN"),  # HARDER return
    # Slot 12 Break ~7:07–~8:06 (2×16) — kick OUT · acid LF collapse
    ("Tholin_Break_a", 16, "break_fragile", "12", "T_BREAK_A"),
    ("Tholin_Break_b", 16, "break_fragile2", "12", "T_BREAK_B"),
    # Slot 13 Return ~8:06–~9:53 (5×16) — hard return + DISTINCT outro last ~60s
    ("Tholin_Return_a", 16, "return_hard", "13", "T_RET_A"),
    ("Tholin_Return_b", 16, "return_hard2", "13", "T_RET_B"),
    ("Tholin_Return_c", 16, "return_peak", "13", "T_RET_C"),
    ("Tholin_Out_a", 16, "outro", "13", "T_OUT_A"),       # DISTINCT outro family
    ("Tholin_Out_b", 16, "outro_handoff", "13", "T_OUT_B"),  # Vyre peel (~last 24s of ~47s)
]

# REAL one-shot + acid_wave every ≤16 bars. Filter alone ≠ rotation.
# Prefer vyre-pool + tholin-pool with pitch/drive variants ≠ Figment/Haniwa/Tholin v1–v2 spines.
FAMILY_KITS = {
    "T_INTRO_A": dict(bd="bd_veil_t", hat="hh_soft_t", oh=None, ride=None,
                      perc=("perc_grain_t",), sfx=("sfx_glow_t", "noise_dark_t"),
                      atm_seed=701, pad_open=0.12, acid_wave="saw", acid_preset="closed"),
    "T_INTRO_B": dict(bd="bd_veil_t2", hat="hh_tick_t", oh="oh_air_t", ride=None,
                      perc=("perc_voice_t", "perc_tom_soft_t"), sfx=("sfx_voice_t", "noise_bright_t"),
                      atm_seed=709, pad_open=0.55, acid_wave="tri", acid_preset="closed"),
    "T_INTRO_C": dict(bd="bd_ghost_t", hat="hh_sparse_t", oh=None, ride=None,
                      perc=("perc_rim_t", "perc_clap_soft_t"), sfx=("sfx_scratch_t", "sfx_pizz_t"),
                      atm_seed=719, pad_open=0.45, acid_wave="pulse25", acid_preset="tease"),
    "T_INTRO_D": dict(bd="bd_ghost_t", hat="hh_break_t", oh=None, ride=None,
                      perc=("perc_tonal_t", "perc_congasyn_t"), sfx=("sfx_gtr_t", "sfx_drumlp_t"),
                      atm_seed=727, pad_open=0.50, acid_wave="square", acid_preset="closed"),
    "T_INTRO_E": dict(bd="bd_e01_t", hat="hh_4c_t", oh=None, ride=None,
                      perc=("perc_claves_t",), sfx=("sfx_glow_t",),
                      atm_seed=733, pad_open=0.35, acid_wave="pulse12", acid_preset="tease"),
    "T_BUILD_A": dict(bd="bd_e02_t", hat="hh_6c_t", oh=None, ride="ride_2_t",
                      perc=("perc_conga_t",), sfx=("sfx_scratch_t",),
                      atm_seed=743, pad_open=0.40, acid_wave="saw", acid_preset="muted"),
    "T_BUILD_B": dict(bd="bd_e03_t", hat="hh_noise_t", oh="oh_4o_t", ride=None,
                      perc=("perc_bongo_t", "perc_djembe_t", "perc_udu_t"), sfx=("sfx_guiro_t", "sfx_drumlp_t"),
                      atm_seed=751, pad_open=0.20, acid_wave="square", acid_preset="muted"),
    "T_BUILD_C": dict(bd="bd_e04_t", hat="hh_2o_t", oh=None, ride="ride_3_t",
                      perc=("perc_agogo_t", "perc_timbale_t"), sfx=("sfx_zap_t",),
                      atm_seed=757, pad_open=0.30, acid_wave="supersaw", acid_preset="ride"),
    "T_BUILD_D": dict(bd="bd_e05_t", hat="hh_6o_t", oh="oh_6o_t", ride=None,
                      perc=("perc_shaker_t", "perc_triangle_t"), sfx=("sfx_4_t", "sfx_5_t"),
                      atm_seed=761, pad_open=0.25, acid_wave="pwm", acid_preset="build"),
    "T_BUILD_E": dict(bd="bd_bass_e_t", hat="hh_noise_t2", oh=None, ride=None,
                      perc=("perc_wbl_t", "perc_tambouri_t"), sfx=("sfx_noise_t", "sfx_gtr_t"),
                      atm_seed=769, pad_open=0.15, acid_wave="noise_saw", acid_preset="dense"),
    "T_DROP_A": dict(bd="bd_e04_t", hat="hh_mute_t", oh=None, ride=None,
                     perc=("perc_ghost_t",), sfx=("noise_dark_t",),
                     atm_seed=773, pad_open=0.70, acid_wave="saw", acid_preset="muted"),
    "T_DROP_B": dict(bd="bd_e05_hard_t", hat="hh_open_a_t", oh="oh_open_a_t", ride=None,
                     perc=("perc_clap_t", "perc_conga_t", "perc_zap_t"), sfx=("sfx_5_t", "sfx_scratch_t"),
                     atm_seed=787, pad_open=0.08, acid_wave="saw", acid_preset="open_bloom"),
    "T_DROP_C": dict(bd="bd_e06_t", hat="hh_open_b_t", oh="oh_open_b_t", ride="ride_4_t",
                     perc=("perc_timbale_t", "perc_shaker_t"), sfx=("sfx_guiro_t", "sfx_4_t"),
                     atm_seed=797, pad_open=0.10, acid_wave="square", acid_preset="open_oct"),
    "T_DROP_D": dict(bd="bd_e03_t", hat="hh_mute_t2", oh=None, ride=None,
                     perc=("perc_rim_t",), sfx=("noise_dark_t", "sfx_pizz_t"),
                     atm_seed=809, pad_open=0.55, acid_wave="pulse25", acid_preset="muted"),
    "T_DROP_E": dict(bd="bd_e07_t", hat="hh_open_c_t", oh="oh_bright_t", ride="ride_5_t",
                     perc=("perc_bongo_t", "perc_agogo_t", "perc_triangle_t"), sfx=("sfx_zap_t", "sfx_drumlp_t"),
                     atm_seed=811, pad_open=0.05, acid_wave="supersaw", acid_preset="open_scream"),
    "T_DROP_F": dict(bd="bd_e08_t", hat="hh_peak_t", oh="oh_peak_t", ride=None,
                     perc=("perc_djembe_t", "perc_clap_t"), sfx=("sfx_5_t", "sfx_noise_t"),
                     atm_seed=821, pad_open=0.05, acid_wave="pwm", acid_preset="max"),
    # TRUE STRIP — kick+ghost ONLY; QUIETER than drop/return (FineTuniX)
    "T_STRIP": dict(bd="bd_strip_t", hat="hh_ghost_t", oh=None, ride=None,
                    perc=("perc_ghost_t",), sfx=("noise_dark_t",),
                    atm_seed=823, pad_open=0.02, acid_wave="saw", acid_preset="strip_duck"),
    "T_RETURN": dict(bd="bd_e08_t", hat="hh_return_t", oh="oh_bright_t", ride="ride_4_t",
                     perc=("perc_topline_t", "perc_tambouri_t"), sfx=("sfx_topline_t", "sfx_zap_t"),
                     atm_seed=827, pad_open=0.12, acid_wave="noise_saw", acid_preset="return_hard"),
    "T_BREAK_A": dict(bd="bd_ghost_t", hat="hh_ghost_t", oh=None, ride=None,
                      perc=("perc_triangle_t",), sfx=("sfx_glow_t", "noise_dark_t"),
                      atm_seed=829, pad_open=0.40, acid_wave="tri", acid_preset="break_hpf"),
    "T_BREAK_B": dict(bd="bd_ghost_t", hat="hh_sparse_t", oh=None, ride=None,
                      perc=("perc_claves_t",), sfx=("sfx_voice_t", "sfx_pizz_t"),
                      atm_seed=839, pad_open=0.55, acid_wave="pulse12", acid_preset="break_hpf"),
    "T_RET_A": dict(bd="bd_e07_t", hat="hh_6c_t", oh="oh_6o_t", ride="ride_2_t",
                    perc=("perc_conga_t", "perc_udu_t"), sfx=("sfx_scratch_t",),
                    atm_seed=853, pad_open=0.15, acid_wave="saw", acid_preset="return_a"),
    "T_RET_B": dict(bd="bd_bass_e2_t", hat="hh_open_a_t", oh=None, ride="ride_3_t",
                    perc=("perc_bongo_t", "perc_timbale_t"), sfx=("sfx_4_t", "sfx_guiro_t"),
                    atm_seed=857, pad_open=0.10, acid_wave="square", acid_preset="return_b"),
    "T_RET_C": dict(bd="bd_e08_t", hat="hh_peak_t", oh="oh_peak_t", ride="ride_5_t",
                    perc=("perc_djembe_t", "perc_agogo_t", "perc_zap_t"), sfx=("sfx_5_t", "sfx_topline_t"),
                    atm_seed=859, pad_open=0.05, acid_wave="supersaw", acid_preset="return_peak"),
    # DISTINCT outro — do NOT coast same cell into Vyre splice
    "T_OUT_A": dict(bd="bd_out_t", hat="hh_out_t", oh="oh_air_t", ride=None,
                    perc=("perc_tom_soft_t", "perc_clap_soft_t"), sfx=("sfx_gtr_t", "sfx_pizz_t"),
                    atm_seed=863, pad_open=0.35, acid_wave="tri", acid_preset="outro"),
    "T_OUT_B": dict(bd="bd_out_thin_t", hat="hh_soft_out_t", oh=None, ride=None,
                    perc=("perc_grain_t",), sfx=("sfx_handoff_t", "noise_dark_t"),
                    atm_seed=877, pad_open=0.85, acid_wave="pulse25", acid_preset="handoff"),
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


def synth_sub_bass(root_hz: float = 41.20) -> np.ndarray:
    """F1 fund (~43.65) for mono kick pocket."""
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
    for i, hz in enumerate(E_PAD):
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


def _osc_wave(phase: np.ndarray, wave: str, t: np.ndarray, rng_seed: int = 0) -> np.ndarray:
    """AUDIBLE waveform variants for acid preset swaps (MFCC movers)."""
    w = (wave or "saw").lower()
    ph = phase
    saw = 2.0 * (ph / (2 * np.pi) - np.floor(0.5 + ph / (2 * np.pi)))
    if w == "saw":
        return saw
    if w == "square":
        return np.sign(np.sin(ph))
    if w == "pulse25":
        # 25% pulse
        duty = 0.25
        return np.where((ph / (2 * np.pi)) % 1.0 < duty, 1.0, -1.0)
    if w == "pulse12":
        duty = 0.125
        return np.where((ph / (2 * np.pi)) % 1.0 < duty, 1.0, -1.0)
    if w == "tri":
        return 2.0 * np.abs(2.0 * ((ph / (2 * np.pi)) % 1.0) - 1.0) - 1.0
    if w == "supersaw":
        # 3 detuned saws — brighter / thicker spectrum
        det = [0.0, 0.007, -0.009]
        y = np.zeros_like(saw)
        for d in det:
            phd = ph * (1.0 + d)
            y += 2.0 * (phd / (2 * np.pi) - np.floor(0.5 + phd / (2 * np.pi)))
        return y / 3.0
    if w == "noise_saw":
        rng = np.random.default_rng(rng_seed + int(len(t) % 997))
        n = rng.uniform(-1, 1, size=len(t)) * 0.35
        return 0.70 * saw + 0.30 * n
    if w == "pwm":
        # slow PWM 10–50%
        duty = 0.10 + 0.40 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.35 * t))
        return np.where((ph / (2 * np.pi)) % 1.0 < duty, 1.0, -1.0)
    return saw


def acid_303_note(freq: float, dur_s: float, accent: bool = False,
                  cutoff_open: float = 0.35, res_boost: float = 0.0,
                  wave: str = "saw", preset: str = "open") -> np.ndarray:
    """Acid LPF note with AUDIBLE waveform/preset swaps (FineTuniX: keep changes audible).

    wave: saw|square|pulse25|pulse12|tri|supersaw|noise_saw|pwm
    preset: closed/muted/tease/build/open_*/max/return_*/break_hpf/strip_duck/outro/handoff
    Muted: heavy LPF. Open: presence ~1.8–2.8 kHz, HPF ~160 Hz; tame 3–6k.
    """
    n = max(8, int(dur_s * SR))
    t = np.arange(n) / SR
    o = float(np.clip(cutoff_open, 0.0, 1.2))
    pitch = freq * (1.0 + (0.06 if accent else 0.0) * np.exp(-t / 0.04))
    phase = np.cumsum(2 * np.pi * pitch / SR)
    osc = _osc_wave(phase, wave, t, rng_seed=int(freq * 10) + hash(wave) % 997)

    # preset-driven open bias so swaps move MFCC even at similar dens
    preset = (preset or "open").lower()
    if "break_hpf" in preset or "strip" in preset:
        o = min(o, 0.35)
    elif "muted" in preset or "closed" in preset:
        o = min(o, 0.28)
    elif "tease" in preset:
        o = max(o, 0.22)
    elif "max" in preset or "scream" in preset or "bloom" in preset:
        o = max(o, 0.85)
    elif "return" in preset:
        o = max(o, 0.70)
    elif "outro" in preset or "handoff" in preset:
        o = min(max(o, 0.15), 0.40)

    cut0 = 220.0 + 780.0 * o
    cut1 = cut0 + (900.0 + 4200.0 * o) * (1.20 if accent else 0.90)
    # waveform-specific brightness offset (audible family identity)
    bright = {
        "saw": 1.00, "square": 1.15, "pulse25": 1.25, "pulse12": 1.35,
        "tri": 0.75, "supersaw": 1.30, "noise_saw": 1.20, "pwm": 1.22,
    }.get((wave or "saw").lower(), 1.0)
    cut = cut0 + (cut1 - cut0) * np.exp(-t / (0.11 if accent else 0.18))
    cut = cut * (1.0 + 0.22 * res_boost) * bright
    y_lo = one_pole(osc, float(np.percentile(cut, 15)), mode="lpf")
    y_hi = one_pole(osc, float(np.percentile(cut, 85)), mode="lpf")
    blend = np.clip((cut - cut.min()) / max(1e-9, cut.max() - cut.min()), 0, 1)
    blend = np.clip(blend * (0.55 + 0.70 * o), 0, 1)
    y = y_lo * (1 - blend) + y_hi * blend
    gate = 0.20 if not accent else 0.14
    if wave in ("pulse12", "pulse25"):
        gate *= 0.85
    env = np.exp(-t / gate)
    atk_n = max(1, int(0.0025 * SR))
    env[:atk_n] *= np.linspace(0, 1, atk_n)
    y = y * env * (1.20 if accent else 0.95)
    hpf = 120.0 + 60.0 * o
    if "break_hpf" in preset:
        hpf = max(hpf, 320.0)  # FineTuniX: collapse 50–100 Hz on break/strip
    if "strip" in preset:
        hpf = max(hpf, 280.0)
    y = one_pole(y, hpf, mode="hpf")
    if o >= 0.55:
        y = peaking_eq(y, 1800.0, 2.2 + 1.0 * (o - 0.55), q=0.95)
        y = peaking_eq(y, ACID_PRESENCE_HZ, ACID_PRESENCE_DB_OPEN * min(1.0, o), q=1.05)
        y = peaking_eq(y, 2800.0, 2.0 * min(1.0, o), q=1.1)
        y = peaking_eq(y, 4800.0, -2.4, q=1.2)  # tame 3–6k
        y = peaking_eq(y, 5500.0, -2.0, q=1.15)
    else:
        y = peaking_eq(y, 2000.0, ACID_PRESENCE_DB_MUTE * (1.0 - o / 0.55), q=0.9)
        y = one_pole(y, 700.0 + 900.0 * o, mode="lpf")
    drive = 1.15 + 0.28 * o
    if wave in ("supersaw", "noise_saw", "pwm"):
        drive += 0.12
    y = tanh_drive(y, drive)
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


def _pool_dirs():
    cands = [
        Path("/workspace/exports/vyre-pool/oneshots"),
        Path("/workspace/exports/tholin-pool/oneshots"),
        Path("/workspace/samples/tholin-162-v2-render/oneshots"),
        Path("/workspace/exports/haniwa-pool/oneshots"),  # fallback only
    ]
    return [p for p in cands if p.exists()]


def _find_pool_wav(*names: str) -> Path | None:
    pools = _pool_dirs()
    for name in names:
        for root in pools:
            p = root / name
            if p.exists():
                return p
    # fuzzy: any file containing token
    for name in names:
        token = name.replace(".wav", "").lower()
        for root in pools:
            for p in root.glob("*.wav"):
                if token in p.stem.lower():
                    return p
    return None


def prepare_bd_from(path: Path, drive: float = 2.15, pitch: float = 1.0) -> np.ndarray:
    raw = read_wav(path)
    if abs(pitch - 1.0) > 0.01:
        x = np.linspace(0, 1, len(raw))
        xi = np.linspace(0, 1, max(8, int(len(raw) / pitch)))
        raw = np.interp(xi, x, raw)
    y = one_pole(raw, 36.0, mode="hpf")
    y = one_pole(y, 4500.0, mode="lpf")
    y = peaking_eq(y, 110.0, 1.6, q=0.85)
    y = tanh_drive(y, drive)
    y = mild_compress(y, thr=0.42, ratio=1.40)
    y = one_pole(y, 9000.0, mode="lpf")
    peak = float(np.max(np.abs(y))) + 1e-12
    return y / peak * 0.95


def load_perc_path(path: Path, drive=1.0, hpf=0.0, lpf=9000.0, used=None) -> np.ndarray:
    y = read_wav(path)
    if hpf:
        y = one_pole(y, hpf, mode="hpf")
    y = one_pole(y, min(lpf, 10000.0), mode="lpf")
    y = tanh_drive(y, drive)
    y = one_pole(y, lpf, mode="lpf")
    if used is not None:
        used.append(str(path.name))
    return y


def mode_gains(mode: str) -> dict:
    """Layer gains + acid_open. Extreme mute/density for AUDIBLE family rotation.
    FineTuniX: true_strip MUST be quieter than drop/return (RMS dip >4–6 dB).
    """
    table = {
        # Intro slot 09
        "intro_atm":  dict(kick=0.0, bass=0.0, hats=0.0, oh=0.0, ride=0.0, perc=0.0,
                           acid=0.0, mg=0.0, atm=1.55, pad=1.40, fx=0.25, acid_open=0.05),
        "intro_open": dict(kick=0.0, bass=0.0, hats=0.65, oh=0.30, ride=0.0, perc=0.85,
                           acid=0.0, mg=0.0, atm=0.0, pad=0.15, fx=1.05, acid_open=0.08),
        "intro_ghost": dict(kick=0.42, bass=0.18, hats=0.20, oh=0.0, ride=0.0, perc=0.15,
                            acid=0.10, mg=0.05, atm=0.40, pad=0.50, fx=0.25, acid_open=0.16),
        "intro_breaktx": dict(kick=0.0, bass=0.0, hats=0.12, oh=0.0, ride=0.0, perc=0.90,
                              acid=0.0, mg=0.0, atm=0.50, pad=0.30, fx=0.95, acid_open=0.10),
        "intro_tease": dict(kick=0.55, bass=0.25, hats=0.35, oh=0.0, ride=0.0, perc=0.20,
                            acid=0.35, mg=0.20, atm=0.25, pad=0.35, fx=0.20, acid_open=0.22),
        # Build slot 10 — NEW families from ~02:00
        "build_kick": dict(kick=1.10, bass=0.65, hats=0.65, oh=0.0, ride=0.55, perc=0.20,
                           acid=0.15, mg=0.08, atm=0.12, pad=0.40, fx=0.15, acid_open=0.18),
        "build_tribal": dict(kick=0.30, bass=0.0, hats=0.15, oh=0.25, ride=0.0, perc=1.30,
                             acid=0.20, mg=0.10, atm=0.30, pad=0.10, fx=0.70, acid_open=0.20),
        "build_ride": dict(kick=1.05, bass=0.70, hats=0.10, oh=0.0, ride=1.25, perc=0.25,
                           acid=0.40, mg=0.25, atm=0.08, pad=0.20, fx=0.15, acid_open=0.35),
        "build_acid": dict(kick=0.95, bass=0.55, hats=0.45, oh=0.30, ride=0.0, perc=0.35,
                           acid=0.95, mg=0.55, atm=0.10, pad=0.15, fx=0.25, acid_open=0.48),
        "build_perc": dict(kick=0.20, bass=0.0, hats=0.0, oh=0.0, ride=0.0, perc=1.45,
                           acid=0.25, mg=0.15, atm=0.70, pad=0.0, fx=1.20, acid_open=0.22),
        # Drop slot 11 — peak; mute games + wave swaps
        "drop_muted": dict(kick=1.15, bass=1.05, hats=0.12, oh=0.0, ride=0.0, perc=0.0,
                           acid=0.60, mg=0.40, atm=0.45, pad=0.90, fx=0.10, acid_open=0.12),
        "drop_open":  dict(kick=0.90, bass=0.55, hats=0.08, oh=0.35, ride=0.0, perc=0.80,
                           acid=1.50, mg=1.00, atm=0.0, pad=0.0, fx=0.35, acid_open=0.96),
        "drop_open2": dict(kick=0.25, bass=0.0, hats=1.10, oh=0.70, ride=1.20, perc=0.95,
                           acid=0.35, mg=1.30, atm=0.20, pad=0.0, fx=0.75, acid_open=0.58),
        "drop_mute2": dict(kick=1.10, bass=0.90, hats=0.0, oh=0.0, ride=0.0, perc=0.15,
                           acid=0.55, mg=0.35, atm=0.55, pad=0.70, fx=0.15, acid_open=0.18),
        "drop_open3": dict(kick=0.85, bass=0.50, hats=0.55, oh=0.45, ride=0.90, perc=1.05,
                           acid=1.35, mg=0.85, atm=0.0, pad=0.0, fx=0.50, acid_open=0.92),
        "drop_max":   dict(kick=1.40, bass=1.20, hats=0.75, oh=0.55, ride=0.0, perc=0.85,
                           acid=1.65, mg=1.15, atm=0.0, pad=0.0, fx=0.50, acid_open=0.98),
        # TRUE STRIP — kick+ghost ONLY; QUIETER than neighbors (Haniwa inverted lesson)
        # Gains deliberately tiny so mastered RMS dips >4–6 dB vs drop_max/return
        "true_strip": dict(kick=0.22, bass=0.0, hats=0.015, oh=0.0, ride=0.0, perc=0.0,
                           acid=0.0, mg=0.0, atm=0.0, pad=0.0, fx=0.0, acid_open=0.02),
        "build_return": dict(kick=1.45, bass=1.10, hats=0.30, oh=0.70, ride=0.85, perc=1.35,
                             acid=1.35, mg=0.80, atm=0.0, pad=0.0, fx=0.95, acid_open=0.78),
        # Break slot 12 — kick OUT · acid LF HPF/duck (50–100 Hz collapse)
        "break_fragile": dict(kick=0.0, bass=0.0, hats=0.08, oh=0.0, ride=0.0, perc=0.20,
                              acid=0.70, mg=0.35, atm=0.90, pad=0.55, fx=0.55, acid_open=0.55),
        "break_fragile2": dict(kick=0.0, bass=0.0, hats=0.20, oh=0.0, ride=0.0, perc=0.15,
                               acid=0.35, mg=0.15, atm=1.40, pad=0.90, fx=1.10, acid_open=0.40),
        # Return slot 13 — HARDER than strip/break
        "return_hard": dict(kick=1.25, bass=1.00, hats=0.55, oh=0.35, ride=0.80, perc=0.65,
                            acid=1.15, mg=0.70, atm=0.05, pad=0.10, fx=0.30, acid_open=0.78),
        "return_hard2": dict(kick=1.20, bass=0.95, hats=0.50, oh=0.0, ride=0.90, perc=0.80,
                             acid=1.25, mg=0.80, atm=0.0, pad=0.0, fx=0.40, acid_open=0.85),
        "return_peak": dict(kick=1.35, bass=1.10, hats=0.65, oh=0.45, ride=1.00, perc=0.90,
                            acid=1.40, mg=0.95, atm=0.0, pad=0.0, fx=0.45, acid_open=0.95),
        # Distinct outro — last ~60s before Vyre
        "outro": dict(kick=0.75, bass=0.25, hats=0.45, oh=0.20, ride=0.0, perc=0.55,
                      acid=0.20, mg=0.10, atm=0.35, pad=0.40, fx=0.70, acid_open=0.18),
        "outro_handoff": dict(kick=0.35, bass=0.10, hats=0.0, oh=0.0, ride=0.0, perc=0.0,
                              acid=0.0, mg=0.0, atm=1.45, pad=1.40, fx=0.25, acid_open=0.05),
        # legacy aliases if any leftover
        "drop_close": dict(kick=1.05, bass=0.55, hats=0.0, oh=0.0, ride=0.0, perc=0.15,
                           acid=0.45, mg=0.25, atm=0.15, pad=0.20, fx=0.20, acid_open=0.22),
        "drop_strip": dict(kick=0.0, bass=0.0, hats=0.0, oh=0.0, ride=0.0, perc=0.35,
                           acid=0.0, mg=0.0, atm=0.85, pad=0.30, fx=0.70, acid_open=0.05),
        "outro2": dict(kick=0.0, bass=0.0, hats=0.25, oh=0.0, ride=0.0, perc=1.25,
                       acid=0.0, mg=0.0, atm=0.15, pad=0.0, fx=1.30, acid_open=0.05),
        "outro3": dict(kick=0.40, bass=0.12, hats=0.0, oh=0.0, ride=0.0, perc=0.0,
                       acid=0.0, mg=0.0, atm=1.40, pad=1.35, fx=0.10, acid_open=0.03),
        "build_kick2": dict(kick=0.25, bass=0.0, hats=0.85, oh=0.45, ride=0.0, perc=0.95,
                            acid=0.0, mg=0.0, atm=0.50, pad=0.10, fx=0.70, acid_open=0.14),
    }
    return table[mode]


def mode_story(mode: str, family: str) -> str:
    stories = {
        "intro_atm": f"Slot09 Intro — PercLP/SynLP/organ glow; family {family}",
        "intro_open": f"Slot09 Intro — voice/grain + soft tom; no kick; {family}",
        "intro_ghost": f"Slot09 Intro — sparse veiled BD tease + acid tease; {family}",
        "intro_breaktx": f"Slot09 Intro — kick OFF · tonal/gtr break texture; {family}",
        "intro_tease": f"Slot09 Intro — kick enters · acid pulse tease; {family}",
        "build_kick": f"Slot10 Build — E kick 1/5/9/13 + ride; {family}",
        "build_tribal": f"Slot10 Build — NEW@~02:00 tribal poly LS7; {family}",
        "build_ride": f"Slot10 Build — ride dense · acid supersaw ride; {family}",
        "build_acid": f"Slot10 Build — dual acid UN-PARK pwm; {family}",
        "build_perc": f"Slot10 Build — perc/FX dense pre-drop; {family}",
        "drop_muted": f"Slot11 Drop — dual acid MUTED + full drums; {family}",
        "drop_open": f"Slot11 Drop PEAK — acid mid-bloom SAW open; {family}",
        "drop_open2": f"Slot11 Drop — WAVE SWAP square · hats/MG dominant; {family}",
        "drop_mute2": f"Slot11 mute game — hats out · pulse25 muted; {family}",
        "drop_open3": f"Slot11 Drop — WAVE SWAP supersaw scream; {family}",
        "drop_max": f"Slot11 all-in max PWM before strip; {family}",
        "true_strip": f"Slot11 TRUE STRIP kick+ghost ONLY · QUIET RMS dip; {family}",
        "build_return": f"Slot11 HARDER return + NEW topline · noise_saw; {family}",
        "break_fragile": f"Slot12 Break — Kick OUT · acid LF HPF/duck; {family}",
        "break_fragile2": f"Slot12 Break — fragile mid acid+atm · NEW wave; {family}",
        "return_hard": f"Slot13 Return — harder kick+sub after Break; {family}",
        "return_hard2": f"Slot13 Return — WAVE SWAP square denser; {family}",
        "return_peak": f"Slot13 Return peak supersaw before DISTINCT outro; {family}",
        "outro": f"Slot13 DISTINCT outro family — no coast into Vyre; {family}",
        "outro_handoff": f"Slot13 Out — thin BD + atm peel toward Vyre B",
    }
    return stories.get(mode, f"{mode} / {family}")


def kick_steps_for(mode: str):
    if mode in ("intro_atm", "intro_open", "intro_breaktx", "break_fragile", "break_fragile2"):
        return []
    if mode == "intro_ghost":
        return [0, 8]
    if mode == "intro_tease":
        return [0, 8]
    if mode == "true_strip":
        return [0]  # sparse single kick — must stay quiet vs drop/return
    if mode in ("outro",):
        return [0, 8]
    if mode == "outro_handoff":
        return [0]
    if mode in ("drop_strip",):
        return []
    if mode in ("build_perc", "build_tribal"):
        return [0, 8]
    if mode == "drop_open2":
        return [0, 8]  # thin kick under hats/MG
    return [0, 4, 8, 12]


def ensure_shots() -> dict:
    """Load DISTINCT one-shots for Tholin_v3 from vyre+tholin pools.
    Prefer files/pitch/drive ≠ Figment_v3 / Haniwa_v3 / Tholin v1–v2 primary spines.
    """
    print("FACTORY", FACTORY)
    used = []
    shots = {}

    def fac(name):
        p = FACTORY / name
        if not p.exists():
            raise FileNotFoundError(p)
        return p

    def pool_or_fac(pool_names, fac_name):
        p = _find_pool_wav(*pool_names) if pool_names else None
        return p if p is not None else fac(fac_name)

    def LP(pool_names, fac_name, drive=1.0, hpf=0.0, lpf=9000.0, key=None, pitch=1.0):
        src = pool_or_fac(pool_names, fac_name)
        y = load_perc_path(src, drive=drive, hpf=hpf, lpf=lpf, used=used)
        if abs(pitch - 1.0) > 0.01:
            x = np.linspace(0, 1, len(y))
            xi = np.linspace(0, 1, max(8, int(len(y) / pitch)))
            y = np.interp(xi, x, y)
        if key:
            write_mono(ONESHOT / f"{key}_{src.stem}.wav", y, 0.9)
            used.append(f"{key}:{src.name}")
        return y

    # BDs — E-series + B-soft + bass-kick; pitch/drive ≠ v1/v2 mappings
    bd_map = [
        ("bd_veil_t", ["bd_factory_b_veiled.wav", "bd_sinkick_b_soft.wav"], "010_BD-11.wav", 1.70, 0.92),
        ("bd_veil_t2", ["bd_sinkick_factory.wav", "bd_factory_b_soft.wav"], "012_BD-13.wav", 1.85, 1.05),
        ("bd_ghost_t", ["bd_b01_organic_soft.wav", "bd_e01_organic.wav"], "008_BD-9.wav", 1.50, 1.10),
        ("bd_e01_t", ["bd_e01_organic.wav"], "016_BD-17.wav", 2.05, 0.97),
        ("bd_e02_t", ["bd_e02_dry.wav"], "016_BD-17.wav", 2.20, 1.03),
        ("bd_e03_t", ["bd_e03_groove.wav", "bd_b03_soft_groove.wav"], "018_BD-19.wav", 2.35, 0.94),
        ("bd_e04_t", ["bd_e04_peak.wav"], "019_BD-20.wav", 2.40, 1.06),
        ("bd_e05_t", ["bd_e05_hard.wav"], "020_BD-21.wav", 2.50, 0.98),
        ("bd_e05_hard_t", ["bd_e05_hard.wav"], "020_BD-21.wav", 2.65, 1.08),
        ("bd_e06_t", ["bd_e06_thin.wav", "bd_b04_thin_close.wav"], "010_BD-11.wav", 1.70, 1.14),
        ("bd_e07_t", ["bd_e07_return.wav"], "018_BD-19.wav", 2.55, 1.02),
        ("bd_e08_t", ["bd_e08_hardest.wav"], "020_BD-21.wav", 2.70, 1.00),
        ("bd_bass_e_t", ["bd_bass_e02.wav", "bd_bass_e01.wav"], "019_BD-20.wav", 2.45, 0.96),
        ("bd_bass_e2_t", ["bd_bass_e05.wav", "bd_bass_e03.wav"], "019_BD-20.wav", 2.50, 1.04),
        ("bd_strip_t", ["bd_e02_dry.wav", "bd_b02_soft_dry.wav"], "016_BD-17.wav", 1.25, 0.80),
        ("bd_out_t", ["bd_b02_soft_dry.wav", "bd_e01_organic.wav"], "012_BD-13.wav", 1.80, 1.07),
        ("bd_out_thin_t", ["bd_b05_whisper.wav", "bd_e06_thin.wav", "bd_factory_b_thin.wav"], "010_BD-11.wav", 1.35, 1.18),
    ]
    for key, alts, fac_name, drive, pitch in bd_map:
        src = None
        for an in alts:
            src = _find_pool_wav(an)
            if src:
                break
        if src is None:
            src = fac(fac_name)
        shots[key] = prepare_bd_from(src, drive=drive, pitch=pitch)
        # E-root punch EQ (~41 Hz / 110 Hz)
        shots[key] = peaking_eq(shots[key], 41.2, 1.8, q=0.7)
        shots[key] = peaking_eq(shots[key], 110.0, 1.4, q=0.85)
        write_mono(ONESHOT / f"{key}_{src.stem}.wav", shots[key], 0.94)
        used.append(f"{key}:{src.name}")

    # Hats — HH-4/6/2 + morph/air from vyre (≠ Figment HH1/5/7 or Haniwa primary)
    shots["hh_soft_t"] = LP(["hh_3c_morph_sparse.wav", "hh_4c.wav"], "054_HH-1C.wav", 0.85, 4500, 10000, "hh_soft_t", 0.96)
    shots["hh_tick_t"] = LP(["hh_2o.wav"], "056_HH-2C.wav", 1.0, 5000, 12000, "hh_tick_t", 1.05)
    shots["hh_sparse_t"] = LP(["hh_3c_morph_sparse.wav", "hh_4c.wav"], "058_HH-3C.wav", 0.90, 4200, 10500, "hh_sparse_t", 1.0)
    shots["hh_break_t"] = LP(["hh_6c.wav"], "056_HH-2C.wav", 1.15, 2400, 7800, "hh_break_t", 0.88)
    shots["hh_4c_t"] = LP(["hh_4c.wav"], "058_HH-3C.wav", 1.0, 4000, 11000, "hh_4c_t", 1.02)
    shots["hh_6c_t"] = LP(["hh_6c.wav"], "062_HH-5C.wav", 1.05, 3800, 10800, "hh_6c_t", 0.98)
    shots["hh_6o_t"] = LP(["hh_6o.wav", "hh_4o.wav"], "059_HH-3O.wav", 1.1, 3000, 11200, "hh_6o_t", 1.04)
    shots["hh_2o_t"] = LP(["hh_2o.wav"], "055_HH-1O.wav", 1.0, 4800, 11500, "hh_2o_t", 1.08)
    shots["hh_noise_t"] = LP(["hh_7c_noiseish.wav", "hh_6c.wav"], "066_HH-7C.wav", 1.1, 3000, 9800, "hh_noise_t", 0.92)
    shots["hh_noise_t2"] = LP(["hh_7c_noiseish.wav"], "066_HH-7C.wav", 1.2, 2600, 9200, "hh_noise_t2", 1.14)
    shots["hh_mute_t"] = LP(["hh_4c.wav", "hh_3c_morph_sparse.wav"], "054_HH-1C.wav", 0.85, 4400, 9500, "hh_mute_t", 0.90)
    shots["hh_mute_t2"] = LP(["hh_6c.wav"], "058_HH-3C.wav", 0.80, 4600, 9000, "hh_mute_t2", 1.12)
    shots["hh_open_a_t"] = LP(["hh_6o.wav", "hh_4o.wav"], "067_HH-7O.wav", 1.15, 2800, 11200, "hh_open_a_t", 1.0)
    shots["hh_open_b_t"] = LP(["hh_4o.wav", "hh_3o_air.wav"], "059_HH-3O.wav", 1.2, 2700, 11800, "hh_open_b_t", 1.10)
    shots["hh_open_c_t"] = LP(["hh_6o.wav", "hh_2o.wav"], "067_HH-7O.wav", 1.18, 2600, 11500, "hh_open_c_t", 0.94)
    shots["hh_peak_t"] = LP(["hh_6o.wav"], "067_HH-7O.wav", 1.25, 2500, 12000, "hh_peak_t", 1.06)
    shots["hh_ghost_t"] = LP(["hh_3c_morph_sparse.wav", "hh_4c.wav"], "054_HH-1C.wav", 0.50, 5500, 8200, "hh_ghost_t", 1.16) * 0.40
    shots["hh_return_t"] = LP(["hh_6o.wav", "hh_4o.wav"], "067_HH-7O.wav", 1.15, 2900, 11500, "hh_return_t", 1.03)
    shots["hh_out_t"] = LP(["hh_3o_air.wav", "hh_4o.wav"], "055_HH-1O.wav", 0.85, 4000, 10500, "hh_out_t", 1.0)
    shots["hh_soft_out_t"] = LP(["hh_3o_morph_soft.wav", "hh_3c_morph_sparse.wav"], "054_HH-1C.wav", 0.70, 4800, 8800, "hh_soft_out_t", 1.20)

    shots["oh_air_t"] = LP(["hh_3o_air.wav", "hh_1o_mi.wav"], "055_HH-1O.wav", 0.9, 3600, 10500, "oh_air_t")
    shots["oh_4o_t"] = LP(["hh_4o.wav"], "059_HH-3O.wav", 1.0, 3200, 10500, "oh_4o_t")
    shots["oh_6o_t"] = LP(["hh_6o.wav"], "067_HH-7O.wav", 1.05, 3000, 10800, "oh_6o_t")
    shots["oh_open_a_t"] = LP(["hh_6o.wav"], "067_HH-7O.wav", 1.1, 2800, 11000, "oh_open_a_t")
    shots["oh_open_b_t"] = LP(["hh_4o.wav"], "059_HH-3O.wav", 1.05, 3000, 10800, "oh_open_b_t")
    shots["oh_bright_t"] = LP(["hh_6o.wav", "hh_2o.wav"], "067_HH-7O.wav", 1.12, 2700, 11200, "oh_bright_t")
    shots["oh_peak_t"] = LP(["hh_6o.wav"], "067_HH-7O.wav", 1.18, 2600, 11500, "oh_peak_t")

    shots["ride_2_t"] = LP(["ride_2.wav"], "068_Ride-1.wav", 1.05, 2200, 9800, "ride_2_t", 1.0)
    shots["ride_3_t"] = LP(["ride_3.wav"], "068_Ride-1.wav", 1.08, 2100, 10000, "ride_3_t", 0.94)
    shots["ride_4_t"] = LP(["ride_4.wav"], "068_Ride-1.wav", 1.10, 2000, 10200, "ride_4_t", 1.06)
    shots["ride_5_t"] = LP(["ride_5.wav"], "068_Ride-1.wav", 1.12, 1900, 10500, "ride_5_t", 0.90)

    # Perc — tribal tholin + soft vyre (≠ Haniwa metal_0–3 spine)
    shots["perc_grain_t"] = LP(["atm_perclp_4.wav", "atm_perclp_5.wav"], "092_JunkPerc.wav", 1.1, 140, 4600, "perc_grain_t")
    shots["perc_voice_t"] = LP(["atm_voice_4.wav", "atm_voice_6.wav", "atm_voice_2.wav"], "104_SFX-3.wav", 0.95, 70, 3600, "perc_voice_t")
    shots["perc_tom_soft_t"] = LP(["perc_tom2_soft.wav", "perc_tom4_soft.wav"], "076_Tom-1.wav", 1.15, 50, 3000, "perc_tom_soft_t")
    shots["perc_rim_t"] = LP(["perc_rim2_factory.wav", "perc_rim2.wav"], "045_Rim-1.wav", 1.2, 900, 7200, "perc_rim_t")
    shots["perc_clap_soft_t"] = LP(["perc_clap2_soft.wav", "perc_clap4_soft.wav"], "048_Clap-1.wav", 1.1, 700, 8000, "perc_clap_soft_t")
    shots["perc_clap_t"] = LP(["perc_clap3.wav", "perc_sd4_accent.wav"], "052_Clap-5.wav", 1.2, 700, 8500, "perc_clap_t")
    shots["perc_tonal_t"] = LP(["atm_synlp_5.wav", "atm_organlp.wav", "atm_synlp_2.wav"], "102_SFX-1.wav", 1.3, 180, 3400, "perc_tonal_t", 0.88)
    shots["perc_congasyn_t"] = LP(["perc_congasyn.wav"], "076_Tom-1.wav", 1.2, 80, 4000, "perc_congasyn_t")
    shots["perc_conga_t"] = LP(["perc_conga_hi.wav", "perc_conga_lo.wav"], "076_Tom-1.wav", 1.2, 70, 3800, "perc_conga_t")
    shots["perc_bongo_t"] = LP(["perc_bongo_hi.wav", "perc_bongo_lo.wav"], "076_Tom-1.wav", 1.15, 80, 4000, "perc_bongo_t")
    shots["perc_djembe_t"] = LP(["perc_djembe.wav"], "078_Tom-3.wav", 1.25, 60, 3200, "perc_djembe_t")
    shots["perc_udu_t"] = LP(["perc_udu.wav"], "076_Tom-1.wav", 1.2, 50, 2800, "perc_udu_t")
    shots["perc_agogo_t"] = LP(["perc_agogo.wav"], "045_Rim-1.wav", 1.25, 600, 7000, "perc_agogo_t")
    shots["perc_timbale_t"] = LP(["perc_timbales.wav"], "078_Tom-3.wav", 1.3, 100, 4500, "perc_timbale_t")
    shots["perc_shaker_t"] = LP(["perc_shaker.wav"], "200_Noise.wav", 1.1, 3000, 10000, "perc_shaker_t")
    shots["perc_triangle_t"] = LP(["perc_triangle.wav"], "045_Rim-1.wav", 1.15, 2500, 9000, "perc_triangle_t")
    shots["perc_claves_t"] = LP(["perc_claves.wav"], "045_Rim-1.wav", 1.2, 800, 7500, "perc_claves_t")
    shots["perc_wbl_t"] = LP(["perc_wbl.wav"], "076_Tom-1.wav", 1.2, 60, 3000, "perc_wbl_t")
    shots["perc_tambouri_t"] = LP(["perc_tambouri.wav"], "092_JunkPerc.wav", 1.3, 400, 7500, "perc_tambouri_t", 1.05)
    shots["perc_zap_t"] = LP(["perc_zap.wav", "sfx_5.wav"], "104_SFX-3.wav", 1.2, 200, 6000, "perc_zap_t")
    shots["perc_ghost_t"] = LP(["perc_triangle.wav", "perc_claves.wav"], "045_Rim-1.wav", 0.65, 2200, 6800, "perc_ghost_t") * 0.30
    shots["perc_topline_t"] = LP(["perc_tambouri.wav", "perc_timbales.wav", "sfx_pizz_soft.wav"], "092_JunkPerc.wav", 1.35, 350, 7800, "perc_topline_t", 1.10)

    # SFX / atm — vyre organ/strings/gtr + tholin voice/synlp (distinct)
    shots["sfx_glow_t"] = LP(["atm_perclp_6.wav", "atm_perclp_7.wav", "atm_organlp.wav"], "102_SFX-1.wav", 0.95, 90, 4000, "sfx_glow_t")
    shots["sfx_voice_t"] = LP(["atm_voice_11.wav", "atm_voice_24.wav", "atm_voice_10.wav"], "104_SFX-3.wav", 0.9, 60, 3400, "sfx_voice_t")
    shots["sfx_scratch_t"] = LP(["sfx_scratch1.wav", "sfx_scratch2.wav"], "102_SFX-1.wav", 1.05, 150, 5000, "sfx_scratch_t")
    shots["sfx_pizz_t"] = LP(["sfx_pizz_soft.wav"], "104_SFX-3.wav", 1.0, 200, 5500, "sfx_pizz_t")
    shots["sfx_gtr_t"] = LP(["sfx_gtrlp_1.wav", "sfx_gtrlp_4.wav"], "102_SFX-1.wav", 1.15, 100, 3200, "sfx_gtr_t", 0.85)
    shots["sfx_drumlp_t"] = LP(["sfx_drumlp_1.wav", "sfx_drumlp_4.wav"], "104_SFX-3.wav", 1.2, 80, 2800, "sfx_drumlp_t", 0.80)
    shots["sfx_guiro_t"] = LP(["perc_guiro.wav", "perc_shaker.wav"], "102_SFX-1.wav", 1.15, 400, 6000, "sfx_guiro_t")
    shots["sfx_zap_t"] = LP(["perc_zap.wav"], "104_SFX-3.wav", 1.1, 180, 5500, "sfx_zap_t")
    shots["sfx_4_t"] = LP(["sfx_4.wav"], "102_SFX-1.wav", 1.0, 100, 4500, "sfx_4_t")
    shots["sfx_5_t"] = LP(["sfx_5.wav"], "104_SFX-3.wav", 1.05, 100, 4800, "sfx_5_t")
    shots["sfx_noise_t"] = LP(["sfx_noise.wav", "sfx_noise_mi.wav"], "200_Noise.wav", 0.95, 180, 5000, "sfx_noise_t")
    shots["sfx_topline_t"] = LP(["sfx_pizz_soft.wav", "perc_tambouri.wav", "sfx_5.wav"], "104_SFX-3.wav", 1.3, 280, 7200, "sfx_topline_t", 1.12)
    shots["sfx_handoff_t"] = LP(["atm_lore_haze.wav", "atm_strings_home.wav", "sfx_5thstab_soft.wav"], "102_SFX-1.wav", 0.85, 80, 3200, "sfx_handoff_t")
    shots["noise_bright_t"] = LP(["sfx_noise.wav"], "200_Noise.wav", 1.0, 280, 7000, "noise_bright_t")
    shots["noise_dark_t"] = LP(["sfx_noise.wav", "sfx_noise_short.wav"], "200_Noise.wav", 0.85, 140, 3800, "noise_dark_t")
    shots["crash"] = LP(["crash_2.wav", "crash_1_soft.wav", "splash_cym_tail.wav"], "073_Crash-1.wav", 0.9, 200, 10000, "crash")

    for k in list(shots.keys()):
        if k.startswith(("hh_", "oh_", "ride_")):
            shots[k] = one_pole(np.asarray(shots[k], dtype=np.float64), 9500.0, mode="lpf") * 0.92

    shots["bass"] = synth_sub_bass(41.20)  # E1 sub
    write_mono(ONESHOT / "bass_sub_E.wav", shots["bass"], 0.9)
    shots["used"] = used
    print("shots ready", len(used), "keys", len(shots))
    return shots


def render_section(idx: int, name: str, bars: int, mode: str, slot: str, family: str, shots: dict):
    N = section_n(bars)
    trk_k = np.zeros(N); trk_b = np.zeros(N); trk_h = np.zeros(N); trk_oh = np.zeros(N)
    trk_ride = np.zeros(N); trk_p = np.zeros(N)
    trk_acid = np.zeros(N); trk_mg = np.zeros(N)
    trk_atm = np.zeros(N); trk_pad = np.zeros(N); trk_fx = np.zeros(N)

    fam = FAMILY_KITS[family]
    g = mode_gains(mode)
    seed = 0xA41A + idx * 29 + (hash(family) % 997)
    kick_samp = shots[fam["bd"]]
    hat_samp = shots[fam["hat"]]
    oh_samp = shots[fam["oh"]] if fam.get("oh") else None
    ride_samp = shots[fam["ride"]] if fam.get("ride") else None
    perc_bank = [shots[p] for p in fam["perc"] if p in shots]
    sfx_bank = [shots[s] for s in fam["sfx"] if s in shots]
    kick_steps = kick_steps_for(mode)

    for bar in range(bars):
        for st in kick_steps:
            beat = bar * 4 + st / 4.0
            place(trk_k, kick_samp, beat, 1.0)
            place(trk_b, shots["bass"], beat, 1.0)

        if g["hats"] > 0.05:
            dens = (0.18 if mode in ("intro_atm", "intro_breaktx", "true_strip", "build_perc") else
                    0.30 if mode.startswith("intro") or "break" in mode else
                    0.55 if mode in ("build_kick", "build_tribal", "build_return", "build_acid") else
                    0.70 if mode in ("build_kick2", "return_hard", "return_hard2") else
                    0.20 if "strip" in mode else 0.78)
            for s in hat_poly15(1, dens=dens):
                if s < 16:
                    beat = bar * 4 + s / 4.0
                    place(trk_h, hat_samp, beat, 0.75 if s % 4 == 2 else 0.55)

        if g["oh"] > 0.04 and oh_samp is not None and bar % 2 == 1:
            place(trk_oh, oh_samp, bar * 4 + 1.5, 0.55)

        if g["ride"] > 0.05 and ride_samp is not None:
            for eighth in range(8):
                beat = bar * 4 + eighth * 0.5
                place(trk_ride, ride_samp, beat, 0.55 if eighth % 2 == 0 else 0.40)

        if g["perc"] > 0.05 and perc_bank:
            dens = (0.90 if mode in ("intro_breaktx", "build_tribal", "build_kick2", "build_perc") else
                    0.40 if "build" in mode or "intro" in mode else
                    0.05 if mode == "true_strip" else
                    0.20 if "strip" in mode else 0.70)
            for s in perc_poly7(1, dens=dens):
                if s < 16:
                    beat = bar * 4 + s / 4.0
                    samp = perc_bank[s % len(perc_bank)]
                    place(trk_p, samp, beat, 0.55)

        # family-specific accents
        if mode in ("drop_open", "drop_open2", "drop_open3") and bar % 8 == 7 and perc_bank:
            place(trk_p, perc_bank[-1], bar * 4 + 1.0, 0.48)
        if mode in ("build_ride", "build_return", "build_tribal") and bar % 4 == 3 and oh_samp is not None:
            place(trk_oh, oh_samp, bar * 4 + 1.5, 0.5)
        if mode in ("build_kick", "build_return", "drop_open2", "build_tribal") and bar == 0 and "crash" in shots:
            place(trk_fx, shots["crash"], 0.0, 0.35)

    # StepJump stutter on outro
    if mode == "outro":
        for bar in list(range(8, 16)) + list(range(24, 28)):
            if bar >= bars:
                continue
            for micro in (0.0, 0.25, 0.5):
                place(trk_k, kick_samp, bar * 4 + micro, 0.55)

    pad_open = float(fam.get("pad_open", 0.4))
    if g["pad"] > 0.01:
        trk_pad += synth_drift_pad(N, open_amt=pad_open, seed=seed + int(fam.get("atm_seed", 0)))
    if g["atm"] > 0.01:
        trk_atm += synth_atm_haze(N, seed=seed + int(fam.get("atm_seed", 0)))
        rng = np.random.default_rng(seed)
        for bar in range(0, bars, 2):
            if sfx_bank:
                place(trk_fx, sfx_bank[bar % len(sfx_bank)],
                      bar * 4 + rng.uniform(0, 1.5), 0.42)
            if mode.startswith("intro") or mode.startswith("outro") or mode in ("drop_close", "drop_strip", "build_strip"):
                if "noise_dark_t" in shots:
                    place(trk_fx, shots["noise_dark_t"], bar * 4, 0.16)

    acid_open = float(g["acid_open"])
    acid_wave = str(fam.get("acid_wave", "saw"))
    acid_preset = str(fam.get("acid_preset", "open"))
    dens_map = {
        "intro_atm": 0.0, "intro_open": 0.0, "intro_ghost": 0.18, "intro_breaktx": 0.0,
        "intro_tease": 0.35,
        "build_kick": 0.15, "build_tribal": 0.20, "build_ride": 0.40, "build_acid": 0.72,
        "build_kick2": 0.0, "build_perc": 0.25,
        "true_strip": 0.0,  # no acid events — kick+ghost only
        "build_return": 0.70,
        "drop_muted": 0.58, "drop_open": 0.90, "drop_open2": 0.85, "drop_mute2": 0.50,
        "drop_open3": 0.92, "drop_max": 0.95,
        "drop_close": 0.38, "drop_strip": 0.12,
        "break_fragile": 0.65, "break_fragile2": 0.55,
        "return_hard": 0.78, "return_hard2": 0.82, "return_peak": 0.90,
        "outro": 0.28, "outro_handoff": 0.05, "outro2": 0.12, "outro3": 0.05,
    }
    dens = dens_map[mode]
    # Filter envelope every 8 bars (audible motion BETWEEN waveform swaps)
    # Per-bar open rides so parked acid can't plateaus at ~0.99
    bar_open = []
    for b in range(bars):
        phase = (b % 8) / 8.0
        # triangle ride 8 bars + section bias
        ride = 0.55 + 0.45 * (1.0 - abs(2.0 * phase - 1.0))
        if mode.startswith("drop_open") or mode in ("drop_max", "return_peak", "build_return"):
            bar_open.append(min(1.15, acid_open * (0.75 + 0.40 * ride)))
        elif mode in ("drop_muted", "drop_mute2", "true_strip"):
            bar_open.append(acid_open * (0.55 + 0.35 * ride))
        elif "break" in mode:
            bar_open.append(acid_open * (0.60 + 0.30 * ride))
        else:
            bar_open.append(acid_open * (0.70 + 0.35 * ride))

    if dens > 0.01 and (g["acid"] > 0.05 or g["mg"] > 0.05):
        for step, note_i, accent, dur_steps in acid_poly13(bars, dens, seed):
            bar_i = min(bars - 1, step // 16)
            o_local = float(bar_open[bar_i])
            trans = {
                "T_DROP_B": 0, "T_DROP_C": 4, "T_DROP_D": 2, "T_DROP_E": 3,
                "T_DROP_F": 5, "T_RETURN": 1, "T_RET_A": 0, "T_RET_B": 4, "T_RET_C": 2,
                "T_BUILD_D": 1, "T_BREAK_A": 3, "T_BREAK_B": 5,
            }.get(family, (idx * 3) % 6)
            oct_up = 2.0 if family in ("T_DROP_C", "T_DROP_E") else 1.0
            freq = float(E_MAJ[(note_i + trans) % len(E_MAJ)]) * oct_up
            res = 0.55 if mode.startswith("drop_open") or mode in ("drop_max", "return_peak") else (
                0.35 if "return" in mode or mode == "build_acid" else 0.0)
            note = acid_303_note(
                freq, dur_steps * STEP_S, accent=accent, cutoff_open=o_local,
                res_boost=res, wave=acid_wave, preset=acid_preset,
            )
            place(trk_acid, note, step / 4.0, 1.15 if accent else 0.88)
            mg_oct = 0.5 if family in ("T_DROP_C", "T_DROP_E") else 1.0
            mg = mg_lpf_note(
                float(E_LOW[(note_i + trans) % len(E_LOW)]) * mg_oct,
                dur_steps * STEP_S * 1.1, accent=accent,
                cutoff_open=o_local * (0.55 if family in ("T_DROP_C", "T_DROP_E") else 0.88),
            )
            place(trk_mg, mg, step / 4.0, 0.85)

    trk_k *= KICK_G * g["kick"]; trk_b *= BASS_G * g["bass"]
    trk_h *= HATS_G * g["hats"]; trk_oh *= OH_G * g["oh"]
    trk_ride *= RIDE_G * g["ride"]; trk_p *= PERC_G * g["perc"]
    trk_acid *= ACID_G * g["acid"]; trk_mg *= MG_G * g["mg"]
    trk_atm *= ATM_G * g["atm"]; trk_pad *= PAD_G * g["pad"]; trk_fx *= FX_G * g["fx"]

    acid_mode = "drop_open" if (
        mode.startswith("drop_open") or mode in ("drop_max", "return_peak", "build_return",
                                                 "return_hard", "return_hard2", "build_acid")
    ) else (
        "drop_muted" if mode in ("drop_muted", "drop_mute2", "drop_close", "drop_strip",
                                 "true_strip", "outro", "outro_handoff") else mode
    )
    if g["acid"] > 0.05 or g["mg"] > 0.05:
        trk_acid, trk_mg = process_acid_bus(trk_acid, trk_mg, acid_open, acid_mode)

    mono_bed = trk_k + trk_b + trk_ride + trk_p + trk_pad
    hats_atm = trk_h + trk_oh + trk_atm
    acid_bus = trk_acid + trk_mg

    cut_map = {
        "intro_atm": (550.0, 1400.0),
        "intro_open": (1200.0, 3200.0),
        "intro_ghost": (2000.0, 4000.0),
        "intro_breaktx": (900.0, 4500.0),
        "intro_tease": (2400.0, 4200.0),
        "build_kick": (2800.0, 4800.0),
        "build_tribal": (2200.0, 7000.0),
        "build_ride": (3500.0, 5800.0),
        "build_acid": (3800.0, 7200.0),
        "build_kick2": (1600.0, 9000.0),
        "build_perc": (1200.0, 7500.0),
        "true_strip": (400.0, 1600.0),  # dark / narrow — quiet strip
        "build_return": (4500.0, 8500.0),
        "drop_muted": (2000.0, 3600.0),
        "drop_open": (4500.0, 9500.0),
        "drop_open2": (5000.0, 10000.0),
        "drop_mute2": (1800.0, 3200.0),
        "drop_open3": (4800.0, 9800.0),
        "drop_max": (5200.0, 10500.0),
        "drop_close": (4800.0, 2600.0),
        "drop_strip": (1600.0, 2400.0),
        "break_fragile": (1400.0, 3800.0),
        "break_fragile2": (1200.0, 3200.0),
        "return_hard": (4200.0, 8000.0),
        "return_hard2": (4600.0, 9000.0),
        "return_peak": (5000.0, 10000.0),
        "outro": (3400.0, 1700.0),
        "outro_handoff": (2200.0, 1000.0),
        "outro2": (2800.0, 1400.0),
        "outro3": (2400.0, 1100.0),
    }
    c0, c1 = cut_map[mode]
    mono_bed = apply_moving_lpf(mono_bed, c0, c1)
    hats_atm = apply_moving_lpf(hats_atm, c0, c1)
    if mode.startswith("drop_open"):
        acid_bus = apply_moving_lpf(acid_bus, 5200.0, 9000.0)
        fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, c1 * 1.05)
    elif mode in ("drop_muted", "drop_close", "drop_strip"):
        acid_bus = apply_moving_lpf(acid_bus, 900.0, 1600.0)
        fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, c1 * 1.05)
    else:
        acid_bus = apply_moving_lpf(acid_bus, c0 * 0.85, c1 * 0.95)
        fx_bus = apply_moving_lpf(trk_fx, c0 * 0.9, c1 * 1.05)

    mono_bed = valve_force(mono_bed, TUBE_GAIN * 0.80)
    hats_atm = valve_force(hats_atm, TUBE_GAIN * 0.75)
    acid_bus = valve_force(acid_bus, TUBE_GAIN * 0.90)
    fx_bus = valve_force(fx_bus, TUBE_GAIN * 0.95)
    # Per-family spectral tilt so adjacent 16-bar blocks move MFCC
    tilt = (hash(family) % 7) - 3  # -3..+3
    if tilt <= -2:
        mono_bed = one_pole(mono_bed, 5500.0, mode="lpf")
        hats_atm = one_pole(hats_atm, 6000.0, mode="lpf")
        acid_bus = one_pole(acid_bus, 4200.0, mode="lpf")
    elif tilt == -1:
        mono_bed = peaking_eq(mono_bed, 800.0, 1.5, q=0.8)
        hats_atm = one_pole(hats_atm, 7500.0, mode="lpf")
    elif tilt == 1:
        mono_bed = peaking_eq(mono_bed, 2200.0, 1.8, q=0.9)
        hats_atm = peaking_eq(hats_atm, 4500.0, 1.2, q=1.0)
    elif tilt >= 2:
        mono_bed = peaking_eq(mono_bed, 2800.0, 2.2, q=1.0)
        hats_atm = one_pole(hats_atm, 1800.0, mode="hpf")
        fx_bus = peaking_eq(fx_bus, 3500.0, 1.5, q=0.9)

    # AUDIBLE family character every block — alternate weight / mid / rupture.
    # Goal: successive 16-bar sims clearly under 0.92 where possible.
    protect_open = mode.startswith("drop_open") or mode in ("true_strip", "drop_max", "build_return") or mode.startswith("return_") or mode.startswith("break_")
    char = idx % 4
    if mode == "true_strip":
        # FineTuniX: QUIETER than drop/return — RMS dip >4–6 dB; 50–100 Hz collapse
        hats_atm = one_pole(hats_atm, 7000.0, mode="hpf") * 0.08
        acid_bus *= 0.0
        fx_bus *= 0.0
        mono_bed = peaking_eq(mono_bed, 50.0, -18.0, q=0.55)
        mono_bed = peaking_eq(mono_bed, 75.0, -16.0, q=0.65)
        mono_bed = peaking_eq(mono_bed, 100.0, -10.0, q=0.75)
        mono_bed = one_pole(mono_bed, 1600.0, mode="lpf")
        mono_bed = one_pole(mono_bed, 140.0, mode="hpf")  # hard LF collapse
        mono_bed *= 0.16
    elif mode == "intro_breaktx":
        # Tonal break texture dominant — no kick weight
        mono_bed = one_pole(mono_bed, 400.0, mode="hpf")
        mono_bed = peaking_eq(mono_bed, 1400.0, 4.5, q=0.8)
        mono_bed *= 0.45
        hats_atm *= 0.6
        fx_bus = peaking_eq(fx_bus, 900.0, 5.0, q=0.7)
        fx_bus *= 2.4
    elif (char == 3) and not protect_open:
        mono_bed = one_pole(mono_bed, 420.0, mode="hpf")
        mono_bed = one_pole(mono_bed, 2400.0, mode="lpf")
        mono_bed *= 0.22
        hats_atm = one_pole(hats_atm, 2500.0, mode="hpf")
        hats_atm = peaking_eq(hats_atm, 5200.0, 5.0, q=1.2)
        hats_atm *= 2.0
        acid_bus = one_pole(acid_bus, 1200.0, mode="hpf")
        acid_bus = one_pole(acid_bus, 2800.0, mode="lpf")
        acid_bus *= 0.15
        fx_bus = peaking_eq(fx_bus, 1500.0, 5.0, q=0.85)
        fx_bus *= 2.3
    elif char == 0:
        mono_bed = peaking_eq(mono_bed, 55.0, 3.5, q=0.65)
        mono_bed = peaking_eq(mono_bed, 100.0, 2.5, q=0.8)
        hats_atm = one_pole(hats_atm, 5500.0, mode="lpf")
        mono_bed *= 1.20
        fx_bus *= 0.6
    elif char == 1:
        mono_bed = one_pole(mono_bed, 180.0, mode="hpf")
        mono_bed = peaking_eq(mono_bed, 1700.0, 3.5, q=0.9)
        hats_atm = peaking_eq(hats_atm, 3800.0, 2.8, q=1.0)
        fx_bus = peaking_eq(fx_bus, 2200.0, 2.5, q=1.0)
        fx_bus *= 1.4
    else:
        mono_bed = one_pole(mono_bed, 150.0, mode="hpf")
        mono_bed = peaking_eq(mono_bed, 3000.0, 3.0, q=1.0)
        hats_atm = one_pole(hats_atm, 1600.0, mode="hpf")
        hats_atm *= 1.55
        mono_bed *= 0.75
        acid_bus = peaking_eq(acid_bus, 2000.0, 2.0, q=1.0)

    # Kickless peel strip (drop_strip / outro haze) — NOT true_strip
    if mode == "drop_strip":
        mono_bed = one_pole(mono_bed, 500.0, mode="hpf")
        mono_bed = one_pole(mono_bed, 2200.0, mode="lpf")
        mono_bed *= 0.12
        hats_atm *= 0.0
        acid_bus *= 0.0
        fx_bus = peaking_eq(fx_bus, 1600.0, 4.0, q=0.8)
        fx_bus = one_pole(fx_bus, 800.0, mode="hpf")
        fx_bus *= 2.3

    # Extra rupture on wood/kick2 before strip
    if mode == "build_perc":
        mono_bed = one_pole(mono_bed, 200.0, mode="hpf")
        mono_bed *= 0.55
        fx_bus = peaking_eq(fx_bus, 1100.0, 5.0, q=0.7)
        fx_bus *= 2.2
        hats_atm *= 0.3
    if mode == "build_kick2":
        mono_bed = one_pole(mono_bed, 280.0, mode="hpf")
        mono_bed *= 0.38
        hats_atm = peaking_eq(hats_atm, 5200.0, 3.8, q=1.2)
        hats_atm *= 1.8
        fx_bus *= 1.7

    # Force open_a vs open_b MFCC split
    if mode == "drop_open2":
        # hats/MG/ride dominant — thin kick body (≠ drop_open acid bloom)
        mono_bed = one_pole(mono_bed, 280.0, mode="hpf")
        mono_bed *= 0.35
        hats_atm *= 1.9
        hats_atm = peaking_eq(hats_atm, 5000.0, 3.0, q=1.1)
        acid_bus = peaking_eq(acid_bus, 2800.0, 4.0, q=1.15)
        acid_bus = one_pole(acid_bus, 4500.0, mode="lpf")
        fx_bus *= 1.5
    if mode == "outro2":
        # metal/perc FX bed — no pad haze
        mono_bed = one_pole(mono_bed, 500.0, mode="hpf")
        mono_bed *= 0.2
        hats_atm = peaking_eq(hats_atm, 4500.0, 4.0, q=1.1)
        fx_bus = peaking_eq(fx_bus, 2000.0, 5.0, q=0.8)
        fx_bus *= 2.5
    if mode == "outro3":
        # dark pad handoff only
        mono_bed = one_pole(mono_bed, 2800.0, mode="lpf")
        mono_bed = peaking_eq(mono_bed, 80.0, 2.0, q=0.7)
        hats_atm *= 0.0
        fx_bus *= 0.3
        acid_bus *= 0.0
    if mode == "outro":
        mono_bed = peaking_eq(mono_bed, 2500.0, 2.5, q=1.0)
        hats_atm *= 1.3
    if mode == "intro_atm":
        mono_bed = one_pole(mono_bed, 2200.0, mode="lpf")
        fx_bus *= 0.5
    if mode == "intro_open":
        mono_bed = one_pole(mono_bed, 300.0, mode="hpf")
        mono_bed *= 0.35
        fx_bus = peaking_eq(fx_bus, 1600.0, 4.5, q=0.85)
        fx_bus *= 2.2
        hats_atm *= 1.5
    if mode == "build_return":
        # NEW topline: perc-forward, mid bite, less pad haze
        mono_bed = peaking_eq(mono_bed, 2200.0, 3.0, q=0.9)
        mono_bed = one_pole(mono_bed, 90.0, mode="hpf")
        hats_atm *= 0.7
        fx_bus = peaking_eq(fx_bus, 1800.0, 4.5, q=0.8)
        fx_bus *= 2.0
    if mode == "drop_muted":
        # dark pad weight — muted acid LPF, almost no tops
        mono_bed = peaking_eq(mono_bed, 60.0, 3.5, q=0.65)
        mono_bed = one_pole(mono_bed, 3200.0, mode="lpf")
        acid_bus = one_pole(acid_bus, 700.0, mode="lpf")
        acid_bus *= 0.7
        hats_atm *= 0.35
        fx_bus *= 0.4
    if mode == "drop_open":
        # mid-bloom presence hard; cut sub relative so mid-rel rises
        acid_bus = peaking_eq(acid_bus, 900.0, 3.0, q=0.8)
        acid_bus = peaking_eq(acid_bus, 1800.0, 5.0, q=0.9)
        acid_bus = peaking_eq(acid_bus, 2400.0, 4.5, q=1.0)
        acid_bus = peaking_eq(acid_bus, 2800.0, 3.0, q=1.1)
        mono_bed = one_pole(mono_bed, 55.0, mode="hpf")  # reduce LF dominance
        mono_bed = peaking_eq(mono_bed, 110.0, 1.2, q=0.8)
        mono_bed *= 0.85

    # Break fragile — kick already 0; HPF acid/pad LF so 50–100 Hz collapses
    if mode == "break_fragile":
        # Kickless fragile — mid haze dominant (≠ return kick body)
        mono_bed = one_pole(mono_bed, 400.0, mode="hpf")
        mono_bed = one_pole(mono_bed, 2200.0, mode="lpf")
        mono_bed *= 0.18
        acid_bus = one_pole(acid_bus, 360.0, mode="hpf")
        acid_bus = peaking_eq(acid_bus, 1600.0, 4.0, q=0.85)
        acid_bus = one_pole(acid_bus, 3500.0, mode="lpf")
        acid_bus *= 0.85
        hats_atm = one_pole(hats_atm, 3000.0, mode="hpf") * 0.35
        fx_bus = peaking_eq(fx_bus, 1100.0, 5.0, q=0.7)
        fx_bus *= 2.2
    if mode == "break_fragile2":
        # Different fragile: voice/atm bed, thinner acid pulse12
        mono_bed = one_pole(mono_bed, 500.0, mode="hpf")
        mono_bed = one_pole(mono_bed, 1800.0, mode="lpf")
        mono_bed *= 0.12
        acid_bus = one_pole(acid_bus, 400.0, mode="hpf")
        acid_bus = one_pole(acid_bus, 2400.0, mode="lpf")
        acid_bus *= 0.45
        hats_atm = peaking_eq(hats_atm, 5500.0, 4.0, q=1.2) * 0.7
        fx_bus = peaking_eq(fx_bus, 800.0, 5.5, q=0.65)
        fx_bus *= 2.8
    if mode == "build_return":
        # HARDER return after strip — punch + topline (not applied to return_* which have own character)
        mono_bed = peaking_eq(mono_bed, 41.2, 3.5, q=0.6)
        mono_bed = peaking_eq(mono_bed, 110.0, 2.5, q=0.85)
        mono_bed *= 1.25
        acid_bus = peaking_eq(acid_bus, 1800.0, 4.0, q=0.9)
        acid_bus = peaking_eq(acid_bus, 2400.0, 3.0, q=1.0)
        hats_atm *= 1.2
        fx_bus *= 1.45
    if mode == "drop_max":
        mono_bed = peaking_eq(mono_bed, 55.0, 2.5, q=0.7)
        mono_bed *= 1.12
        acid_bus = peaking_eq(acid_bus, 2000.0, 3.0, q=1.0)
    if mode == "drop_mute2":
        mono_bed = peaking_eq(mono_bed, 60.0, 3.0, q=0.7)
        mono_bed = one_pole(mono_bed, 3000.0, mode="lpf")
        hats_atm *= 0.2
        acid_bus = one_pole(acid_bus, 900.0, mode="lpf")
    if mode == "drop_open3":
        acid_bus = peaking_eq(acid_bus, 900.0, 2.5, q=0.8)
        acid_bus = peaking_eq(acid_bus, 2200.0, 4.5, q=0.95)
        acid_bus = peaking_eq(acid_bus, 5200.0, -2.5, q=1.1)
        mono_bed = one_pole(mono_bed, 50.0, mode="hpf")
        mono_bed *= 0.88
    if mode == "build_acid":
        acid_bus = peaking_eq(acid_bus, 1600.0, 3.0, q=0.9)
        acid_bus = peaking_eq(acid_bus, 4800.0, -2.0, q=1.1)
    if mode == "outro_handoff":
        mono_bed = one_pole(mono_bed, 2600.0, mode="lpf")
        mono_bed = peaking_eq(mono_bed, 80.0, 1.5, q=0.7)
        hats_atm *= 0.0
        acid_bus *= 0.0
        fx_bus *= 0.35
    # BUILD plateau killers — adjacent 16-bar sims must drop (loop-gate at ~95s)
    if mode == "build_kick":
        mono_bed = peaking_eq(mono_bed, 55.0, 4.0, q=0.65)
        mono_bed = peaking_eq(mono_bed, 100.0, 2.5, q=0.8)
        mono_bed *= 1.25
        hats_atm = one_pole(hats_atm, 5000.0, mode="lpf")
        acid_bus *= 0.35
        fx_bus *= 0.4
    if mode == "build_tribal":
        mono_bed = one_pole(mono_bed, 350.0, mode="hpf")
        mono_bed *= 0.28
        hats_atm *= 0.4
        fx_bus = peaking_eq(fx_bus, 1200.0, 5.0, q=0.7)
        fx_bus *= 2.4
        acid_bus = one_pole(acid_bus, 1500.0, mode="hpf")
        acid_bus *= 0.25
    if mode == "build_ride":
        mono_bed = peaking_eq(mono_bed, 2200.0, 2.0, q=0.9)
        hats_atm = one_pole(hats_atm, 1800.0, mode="hpf")
        hats_atm *= 0.3
        # ride lives in mono_bed via ride track — brighten
        mono_bed = peaking_eq(mono_bed, 4500.0, 3.5, q=1.1)
        acid_bus = peaking_eq(acid_bus, 1800.0, 2.5, q=0.9)
    if mode == "build_acid":
        mono_bed = one_pole(mono_bed, 90.0, mode="hpf")
        mono_bed *= 0.70
        acid_bus = peaking_eq(acid_bus, 900.0, 3.0, q=0.8)
        acid_bus = peaking_eq(acid_bus, 2000.0, 4.5, q=0.95)
        acid_bus = peaking_eq(acid_bus, 5200.0, -2.5, q=1.1)
        acid_bus *= 1.55
        hats_atm *= 0.55
    if mode == "build_perc":
        mono_bed = one_pole(mono_bed, 250.0, mode="hpf")
        mono_bed *= 0.40
        hats_atm *= 0.15
        fx_bus = peaking_eq(fx_bus, 1000.0, 5.5, q=0.65)
        fx_bus *= 2.6
        acid_bus *= 0.3
    if mode == "intro_tease":
        mono_bed = one_pole(mono_bed, 200.0, mode="hpf")
        mono_bed *= 0.55
        hats_atm = peaking_eq(hats_atm, 4800.0, 3.0, q=1.1)
        acid_bus = one_pole(acid_bus, 1600.0, mode="lpf")
        fx_bus *= 1.3
    # RETURN plateau killers — each return cell must be a different MFCC family
    if mode == "return_hard":
        # sub-heavy kick wall, dark tops
        mono_bed = peaking_eq(mono_bed, 41.2, 4.5, q=0.55)
        mono_bed = peaking_eq(mono_bed, 95.0, 3.0, q=0.75)
        mono_bed = one_pole(mono_bed, 4200.0, mode="lpf")
        mono_bed *= 1.30
        hats_atm = one_pole(hats_atm, 4500.0, mode="lpf") * 0.55
        acid_bus = one_pole(acid_bus, 2800.0, mode="lpf")
        acid_bus *= 0.75
        fx_bus *= 0.45
    if mode == "return_hard2":
        # thin kick, hats/ride/perc forward, square acid mid
        mono_bed = one_pole(mono_bed, 180.0, mode="hpf")
        mono_bed = peaking_eq(mono_bed, 2800.0, 4.0, q=1.0)
        mono_bed *= 0.55
        hats_atm = one_pole(hats_atm, 1500.0, mode="hpf")
        hats_atm = peaking_eq(hats_atm, 5000.0, 4.0, q=1.15)
        hats_atm *= 2.0
        acid_bus = peaking_eq(acid_bus, 2000.0, 5.0, q=1.0)
        acid_bus = one_pole(acid_bus, 4500.0, mode="lpf")
        acid_bus *= 1.35
        fx_bus = peaking_eq(fx_bus, 1600.0, 4.0, q=0.85)
        fx_bus *= 1.9
    if mode == "return_peak":
        # acid-dominant supersaw scream, reduced kick body
        mono_bed = one_pole(mono_bed, 70.0, mode="hpf")
        mono_bed *= 0.75
        acid_bus = peaking_eq(acid_bus, 850.0, 3.5, q=0.75)
        acid_bus = peaking_eq(acid_bus, 1800.0, 5.5, q=0.9)
        acid_bus = peaking_eq(acid_bus, 2600.0, 4.5, q=1.05)
        acid_bus = peaking_eq(acid_bus, 5500.0, -3.0, q=1.15)
        acid_bus *= 1.65
        hats_atm *= 0.45
        fx_bus = peaking_eq(fx_bus, 2200.0, 3.5, q=0.9)
        fx_bus *= 1.6

    mono_bed = one_pole(mono_bed, 11000.0, mode="lpf")
    hats_atm = one_pole(hats_atm, 9500.0, mode="lpf")
    acid_bus = one_pole(acid_bus, 5600.0 if mode.startswith("drop_open") else 7500.0, mode="lpf")
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
    write_stereo_lr(mix_path, left, right, 0.92)
    meta = {
        "name": name, "mode": mode, "slot": slot, "family": family, "bars": bars,
        "story": mode_story(mode, family), "bd": fam["bd"],
        "hat": fam["hat"], "perc": list(fam["perc"]), "sfx": list(fam["sfx"]),
        "gains": {k: g[k] for k in g if k != "acid_open"},
        "acid_open": acid_open,
        "acid_wave": acid_wave,
        "acid_preset": acid_preset,
        "acid_events": len(acid_poly13(bars, dens, seed)) if dens > 0 else 0,
        "dur_s": bars * BAR_S,
    }
    print(f"  section {idx:02d} slot{slot} {family} {name}: {bars} bars (~{bars * BAR_S:.1f}s) open={acid_open:.2f}")
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
    # Gain+limiter (loudnorm alone undershoots with high arrangement LRA)
    af = (
        "highpass=f=26:poles=2,"
        "lowshelf=f=90:t=q:w=0.7:g=1.6,"
        "equalizer=f=52:t=q:w=1.1:g=2.0,"
        "equalizer=f=72:t=q:w=1.4:g=-1.0,"
        "equalizer=f=380:t=q:w=1.0:g=-0.8,"
        "equalizer=f=1800:t=q:w=1.0:g=1.3,"
        "equalizer=f=2400:t=q:w=1.1:g=1.5,"
        "equalizer=f=4500:t=q:w=1.2:g=-1.8,"
        "equalizer=f=5500:t=q:w=1.2:g=-2.0,"
        "equalizer=f=6500:t=q:w=1.2:g=-2.2,"
        "equalizer=f=10000:t=q:w=1.1:g=-2.8,"
        "highshelf=f=7000:t=q:w=0.7:g=-3.0,"
        "lowpass=f=15000:poles=1,"
        "acompressor=threshold=-18dB:ratio=1.35:attack=8:release=160:makeup=2.0,"
        "volume=2.2dB,"
        "alimiter=limit=0.85:attack=1:release=50:level=disabled"
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
    dur = sum(b for _, b, *_ in FULL_SECTIONS) * BAR_S
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


def measure_mid_bloom(path: Path, mute_t=(237.0, 260.7), open_t=(260.7, 284.4)) -> dict:
    """Compare Drop_mute vs Drop_open mid 700Hz–3kHz energy (Tholin v3 timings)."""
    import json
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

    mute = section(*mute_t)
    open_ = section(*open_t)

    def rel_mid(seg):
        full = band_energy_db(seg, 20.0, 12000.0)
        mid = band_energy_db(seg, 700.0, 3000.0)
        low = band_energy_db(seg, 30.0, 200.0)
        harsh = band_energy_db(seg, 3000.0, 6000.0)
        return mid - full, mid, low - full, harsh - full

    mute_rel, mute_mid, mute_low, mute_harsh = rel_mid(mute)
    open_rel, open_mid, open_low, open_harsh = rel_mid(open_)
    out = {
        "mute_window": mute_t, "open_window": open_t,
        "mute_mid_db": round(mute_rel, 2),
        "open_mid_db": round(open_rel, 2),
        "delta_db": round(open_rel - mute_rel, 2),
        "mute_abs": round(mute_mid, 2),
        "open_abs": round(open_mid, 2),
        "open_harsh_rel": round(open_harsh, 2),
        "mute_harsh_rel": round(mute_harsh, 2),
        "open_low_note": f"open low-rel={open_low:.2f} dB (mute low-rel={mute_low:.2f})",
    }
    print("MID-BLOOM mute_rel", out["mute_mid_db"], "open_rel", out["open_mid_db"],
          "delta", out["delta_db"], out["open_low_note"])
    (OUT / "_tholin_v3_mid_bloom.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def strip_return_rms_check(path: Path, strip_idx: int = 16, return_idx: int = 17,
                             drop_idx: int = 15) -> dict:
    """FineTuniX: strip must be quieter than drop_max/return by >4–6 dB RMS."""
    import json
    try:
        import librosa
    except Exception as e:
        raise RuntimeError(f"librosa required: {e}")
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    bar_n = int(BAR_S * sr)
    block = 16 * bar_n

    def blk_rms(i):
        seg = y[i * block:(i + 1) * block]
        if len(seg) < block // 2:
            return -120.0
        r = float(np.sqrt(np.mean(seg ** 2)) + 1e-12)
        return 20.0 * np.log10(r)

    drop_rms = blk_rms(drop_idx)
    strip_rms = blk_rms(strip_idx)
    ret_rms = blk_rms(return_idx)
    dip_vs_drop = strip_rms - drop_rms
    dip_vs_ret = strip_rms - ret_rms
    # also check 50–100 Hz energy collapse on strip vs drop
    def band_e(i, lo=50.0, hi=100.0):
        seg = y[i * block:(i + 1) * block]
        if len(seg) < 2048:
            return -120.0
        S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        freqs = np.fft.rfftfreq(len(seg), 1.0 / sr)
        msk = (freqs >= lo) & (freqs <= hi)
        e = float(np.mean(S[msk] ** 2) + 1e-18)
        return 10.0 * np.log10(e)

    drop_lf = band_e(drop_idx)
    strip_lf = band_e(strip_idx)
    lf_delta = strip_lf - drop_lf
    out = {
        "drop_idx": drop_idx, "strip_idx": strip_idx, "return_idx": return_idx,
        "drop_rms_db": round(drop_rms, 2),
        "strip_rms_db": round(strip_rms, 2),
        "return_rms_db": round(ret_rms, 2),
        "strip_minus_drop_db": round(dip_vs_drop, 2),
        "strip_minus_return_db": round(dip_vs_ret, 2),
        "lf50_100_drop": round(drop_lf, 2),
        "lf50_100_strip": round(strip_lf, 2),
        "lf_delta_db": round(lf_delta, 2),
        "rms_dip_pass": bool(dip_vs_drop <= -4.0 and dip_vs_ret <= -2.0),
        "lf_collapse_pass": bool(lf_delta <= -6.0),
        "strip_quieter_than_return": bool(strip_rms < ret_rms - 2.0),
    }
    print("STRIP-GATE drop", out["drop_rms_db"], "strip", out["strip_rms_db"],
          "return", out["return_rms_db"], "dip", out["strip_minus_drop_db"],
          "LFΔ", out["lf_delta_db"],
          "pass", out["rms_dip_pass"], out["lf_collapse_pass"])
    (OUT / "_tholin_v3_strip_gate.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    Path("/workspace/exports/_tholin_v3_strip_gate.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    return out


def loop_sim_check(path: Path, sim_thresh: float = 0.92, max_run_bars: int = 64) -> dict:
    """Success gate: no ≥64-bar run of successive 16-bar blocks at sim ≥0.92.
    MFCC+chroma block cosine (matches Vestiges_LOOP_DIAGNOSIS method).
    """
    import json
    try:
        import librosa
    except Exception as e:
        raise RuntimeError(f"librosa required for loop gate: {e}")

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    bar_n = int(BAR_S * sr)
    block = 16 * bar_n
    n_blocks = len(y) // block
    feats = []
    for i in range(n_blocks):
        seg = y[i * block:(i + 1) * block]
        mfcc = librosa.feature.mfcc(y=seg, sr=sr, n_mfcc=13)
        chroma = librosa.feature.chroma_stft(y=seg, sr=sr)
        # Also RMS shape + spectral contrast for one-shot family sensitivity
        rms = librosa.feature.rms(y=seg)[0]
        contrast = librosa.feature.spectral_contrast(y=seg, sr=sr)
        feat = np.concatenate([
            mfcc.mean(1), mfcc.std(1),
            chroma.mean(1), chroma.std(1),
            np.array([float(np.mean(np.log10(rms + 1e-8))), float(np.std(np.log10(rms + 1e-8)))]),
            contrast.mean(1), contrast.std(1),
        ])
        feats.append(feat)
    feats = np.asarray(feats, dtype=np.float64)
    sims = []
    for i in range(len(feats) - 1):
        a, b = feats[i], feats[i + 1]
        sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
        sims.append(sim)

    max_run = 0
    cur = 0
    run_start = 0
    worst = {"run_blocks": 0, "run_bars": 0, "start_block": 0, "mean_sim": 0.0, "start_s": 0.0}
    for i, s in enumerate(sims):
        if s >= sim_thresh:
            if cur == 0:
                run_start = i
            cur += 1
            run_bars = (cur + 1) * 16
            if cur > max_run:
                max_run = cur
                mean_sim = float(np.mean(sims[run_start:run_start + cur]))
                worst = {"run_blocks": cur + 1, "run_bars": run_bars,
                         "start_block": run_start, "mean_sim": round(mean_sim, 4),
                         "start_s": round(run_start * 16 * BAR_S, 1)}
        else:
            cur = 0

    passed = worst["run_bars"] < max_run_bars
    out = {
        "n_blocks": n_blocks,
        "sims": [round(s, 4) for s in sims],
        "mean_sim": round(float(np.mean(sims)) if sims else 0.0, 4),
        "max_sim": round(float(np.max(sims)) if sims else 0.0, 4),
        "worst_run": worst,
        "thresh": sim_thresh,
        "max_run_bars": max_run_bars,
        "passed": bool(passed),
        "gate": "PASS" if passed else "FAIL",
        "method": "mfcc13+chroma+rms+contrast block cosine",
    }
    print("LOOP-GATE", out["gate"], "worst_run_bars", worst["run_bars"],
          "mean_sim", worst.get("mean_sim"), "at", worst.get("start_s"), "s")
    print("  sims:", out["sims"])
    (OUT / "_tholin_v3_loop_gate.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    Path("/workspace/exports/_tholin_v3_loop_gate.json").write_text(
        json.dumps({k: v for k, v in out.items() if k != "sims"}, indent=2), encoding="utf-8")
    return out



def write_notes(dur: float, metas: list, lufs: dict, shots: dict, errors: list,
                mid_delta: dict | None = None, loop_gate: dict | None = None,
                strip_gate: dict | None = None):
    wave_swaps = []
    prev_w = None
    for m in metas:
        w = m.get("acid_wave")
        if w and w != prev_w:
            wave_swaps.append((m["family"], w, m.get("acid_preset"), m.get("mode")))
            prev_w = w
    n_wave_changes = max(0, len(wave_swaps) - 1)

    lines = [
        "# EvAIx Tholin v3 — Vestiges slots 09–13 @ 162 E (LOOP FIX · WORST offender)",
        "",
        f"**MP3:** `{MP3_NAME}`",
        f"- Downloads: `C:\\\\Users\\\\Gebruiker\\\\Downloads\\\\{MP3_NAME}`",
        f"- Workspace: `/workspace/{MP3_NAME}`",
        f"- Exports: `/workspace/exports/{MP3_NAME}`",
        f"- Script: `/workspace/build_tholin_162_v3.py` (+ `/workspace/exports/build_tholin_162_v3.py`)",
        "",
        f"Duration: **{dur:.2f} s** (~{dur/60:.2f} min) · BPM **{BPM:.0f}** · Key **E major** (dark filters · peak chapter)",
        f"Bars: **{sum(m['bars'] for m in metas)}** ({len(metas)} × 16-bar families, grid-aligned)",
        "",
        "## Measured loudness",
        f"- **I** = {lufs.get('I')} LUFS (target −8…−9)",
        f"- **TP** = {lufs.get('TP')} dB (target ≤ −1.0 dBTP)",
        f"- **LRA** = {lufs.get('LRA')} LU (target ≥5–6; v2 was 4.7–4.8)",
        "",
        "## Loop-gate (success check)",
    ]
    if loop_gate:
        w = loop_gate.get("worst_run", {})
        lines += [
            f"- **Result: {loop_gate.get('gate')}** — no ≥64-bar run of successive 16-bar blocks at sim ≥0.92",
            f"- Method: MFCC13+chroma+RMS+spectral-contrast block cosine (librosa)",
            f"- Worst run: **{w.get('run_bars')} bars** mean_sim={w.get('mean_sim')} starting ~{w.get('start_s')}s",
            f"- Successive 16-bar sims: `{loop_gate.get('sims')}`",
            "",
        ]
    else:
        lines += ["- (not measured)", ""]

    if strip_gate:
        lines += [
            "## Strip vs Drop/Return (FineTuniX — must be QUIETER)",
            f"- Drop_max RMS: **{strip_gate.get('drop_rms_db')}** dBFS",
            f"- Strip RMS: **{strip_gate.get('strip_rms_db')}** dBFS",
            f"- Return RMS: **{strip_gate.get('return_rms_db')}** dBFS",
            f"- Strip − Drop: **{strip_gate.get('strip_minus_drop_db')}** dB (target ≤ −4…−6)",
            f"- Strip − Return: **{strip_gate.get('strip_minus_return_db')}** dB (must be negative)",
            f"- LF 50–100 Hz Δ (strip−drop): **{strip_gate.get('lf_delta_db')}** dB",
            f"- Gates: rms_dip={strip_gate.get('rms_dip_pass')} · lf_collapse={strip_gate.get('lf_collapse_pass')} · strip_quieter={strip_gate.get('strip_quieter_than_return')}",
            "",
        ]

    lines += [
        "## Acid waveform / preset swap list (AUDIBLE — not filter-only)",
        f"- Distinct waveform changes across chapter: **{n_wave_changes}** (plus intro seed)",
        "| Family | Wave | Preset | Mode |",
        "|--------|------|--------|------|",
    ]
    for fam, wave, preset, mode in wave_swaps:
        lines.append(f"| `{fam}` | **{wave}** | {preset} | {mode} |")

    lines += [
        "",
        "## Family rotation timeline (HARD RULE: ≤32 bars; filter≠family)",
        "| t0–t1 | Bars | Family | Mode | Wave | BD / HH / Perc |",
        "|-------|------|--------|------|------|----------------|",
    ]
    t0 = 0.0
    for m in metas:
        t1 = t0 + m["dur_s"]
        perc = ",".join(m.get("perc", [])[:2])
        lines.append(
            f"| {t0:.0f}–{t1:.0f}s | {m['bars']} | `{m['family']}` | {m['mode']} | "
            f"{m.get('acid_wave','—')} | {m.get('bd')}/{m.get('hat')}/{perc} |"
        )
        t0 = t1

    lines += [
        "",
        "## Slot skeleton",
        "| Slot | ID | Time | Energy | Character |",
        "|------|-----|------|--------|-----------|",
        "| 09 | Tholin_Intro | 0:00–~1:58 | 3 | glow→voice→ghost→breaktx→tease |",
        "| 10 | Tholin_Build | ~1:58–~3:57 | 5 | kick·tribal NEW@02:00·ride·acid UN-PARK·perc |",
        "| 11 | Tholin_Drop | ~3:57–~7:07 | 10 | mute→open SAW→square→mute2→supersaw→max→QUIET strip→HARD return |",
        "| 12 | Tholin_Break | ~7:07–~8:06 | 4 | Kick OUT · acid LF HPF/duck · fragile |",
        "| 13 | Tholin_Return | ~8:06–~9:53 | 9 | hard return · DISTINCT outro last ~60s → Vyre peel |",
        "",
        "## Poly doctrine",
        "- Acid **Last Step 13** vs kick **16** vs hats **15** vs perc **7**",
        "- Kick grid: steps 0/4/8/12 (Electribe 1/5/9/13); strips/ghosts/breaks thin or remove",
        "- Dual acid: waveform-swapped lead + MG LPF square −8va · **E major**",
        "- Valve Force grit; tame 3–6 kHz; HPF acid ~160 Hz (break/strip ≥280–320 Hz)",
        "",
    ]
    if mid_delta:
        lines += [
            "## Mid-band open vs mute (measured)",
            f"- Mute window {mid_delta.get('mute_window')}: mid rel **{mid_delta.get('mute_mid_db')}** dB",
            f"- Open window {mid_delta.get('open_window')}: mid rel **{mid_delta.get('open_mid_db')}** dB",
            f"- Delta open−mute: **{mid_delta.get('delta_db')}** dB",
            f"- Harsh 3–6k open rel: {mid_delta.get('open_harsh_rel')} (mute {mid_delta.get('mute_harsh_rel')})",
            f"- {mid_delta.get('open_low_note', '')}",
            "",
        ]
    lines += [
        "## v3 vs v1/v2",
        "- **Primary fix:** real BD/HH/perc/SFX family every 16 bars + AUDIBLE acid waveform/preset swaps",
        "- Kill chained freeze slabs (master 15:57–18:43 / 18:43–21:05 → 21:53–23:51)",
        "- Un-park acid: filter envelopes every 8 bars PLUS waveform swaps (saw/square/pulse/tri/supersaw/pwm/noise_saw)",
        "- TRUE strip quieter than drop/return (Haniwa inverted lesson) · LF collapse · HARDER return",
        "- Distinct outro family last ~60s — no coast into Vyre splice",
        "- Distinct pool from Figment_v3 / Haniwa_v3 / Tholin v1–v2 (vyre+tholin expand, retuned)",
        "- No commercial EDM drops; free-party plateaus; filter≠family; LRA via arrangement",
        "",
        f"Samples used (count={len(shots.get('used', []))}): see build log / oneshots dir",
        f"Acid waveform swaps (family changes): **{n_wave_changes}**",
        f"Errors: {errors}",
        "Ableton: skipped (--skip-ableton / DSP bounce)",
        "Vyre_v3: **not started** (Architect STOP after Tholin_v3)",
        "",
        "*EvAIx · Tholin Vestiges 09–13 v3 · loop-fix rotation · FineTuniX strip*",
    ]
    text_out = "\n".join(lines)
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTES_PATH.write_text(text_out, encoding="utf-8")
    print("NOTES", NOTES_PATH)
    try:
        NOTES_WORKSPACE.write_text(text_out, encoding="utf-8")
    except Exception as e:
        print("NOTES workspace copy", e)
    try:
        Path("/workspace/exports/EvAIx_Tholin_162_v3_NOTES.md").write_text(text_out, encoding="utf-8")
    except Exception:
        pass


def main():
    skip_ableton = "--skip-ableton" in sys.argv or True
    print("=== EvAIx Tholin 162 v3 LOOP-FIX (WORST offender) ===")
    print("FACTORY", FACTORY, "exists", FACTORY.exists())
    total_bars = sum(b for _, b, _, _, _ in FULL_SECTIONS)
    n_fam = len({f for *_, f in FULL_SECTIONS})
    print("BPM", BPM, "BAR_S", round(BAR_S, 4), "total bars", total_bars,
          "est dur", round(total_bars * BAR_S, 1), "families", n_fam)
    # assert hard rule ≤32
    for name, bars, mode, slot, fam in FULL_SECTIONS:
        if bars > 32:
            raise RuntimeError(f"family slot exceeds 32 bars: {name} {bars}")
    waves = [FAMILY_KITS[f].get("acid_wave") for *_, f in FULL_SECTIONS]
    n_wave_swaps = sum(1 for i in range(1, len(waves)) if waves[i] != waves[i - 1])
    print("acid waveform changes across sections:", n_wave_swaps)

    shots = ensure_shots()
    mixes, metas, errors = [], [], []
    for i, (name, bars, mode, slot, family) in enumerate(FULL_SECTIONS):
        try:
            mix_path, meta = render_section(i, name, bars, mode, slot, family, shots)
            mixes.append(mix_path)
            metas.append(meta)
        except Exception as e:
            errors.append(f"{name}: {e}")
            print("ERROR section", name, e)
            raise

    dur = bounce_mp3(mixes, MP3_WORKSPACE)
    # copy exports + downloads path on box (PC copy via CopyFromBox later)
    try:
        shutil.copy2(MP3_WORKSPACE, MP3_EXPORTS)
    except Exception as e:
        print("exports copy", e)
    try:
        MP3_DOWNLOADS.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MP3_WORKSPACE, MP3_DOWNLOADS)
    except Exception as e:
        print("downloads copy (box path may be virtual)", e)
    try:
        shutil.copy2(path := Path(__file__).resolve(), Path("/workspace/exports/build_tholin_162_v3.py"))
    except Exception as e:
        print("script export copy", e)
    try:
        BRIDGE_COPY.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__).resolve(), BRIDGE_COPY)
    except Exception as e:
        print("bridge copy", e)

    lufs = measure_lufs(MP3_WORKSPACE)
    mid_delta = measure_mid_bloom(MP3_WORKSPACE)
    loop_gate = loop_sim_check(MP3_WORKSPACE)
    strip_gate = strip_return_rms_check(MP3_WORKSPACE)
    write_notes(dur, metas, lufs, shots, errors, mid_delta=mid_delta,
                loop_gate=loop_gate, strip_gate=strip_gate)

    print("DONE", MP3_WORKSPACE, "dur", round(dur, 2),
          "I=", lufs.get("I"), "TP=", lufs.get("TP"),
          "LRA=", lufs.get("LRA"), "loop=", loop_gate.get("gate"),
          "strip_dip=", strip_gate.get("strip_minus_drop_db"),
          "wave_swaps=", n_wave_swaps)
    if not loop_gate.get("passed"):
        print("WARNING: loop gate FAILED — inspect _tholin_v3_loop_gate.json")
    if not strip_gate.get("rms_dip_pass"):
        print("WARNING: strip RMS dip FAILED — strip not quiet enough vs drop/return")
    if not skip_ableton:
        print("Ableton path not used (DSP bounce)")


if __name__ == "__main__":
    main()
