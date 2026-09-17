# -*- coding: utf-8 -*-
"""EvAIx MentalClean + Molecular MORPH @162 v2 — Ring Mod + EMX hat choke.

Keep MentalClean kick/bass character (sledge + ESX SinKick + mild compress) at 162 BPM.
Force Molecular-style chapter changes every 8–16+ bars so it never loops the same bed.
Poly acid Last Step 13/15 against 4/4 kick. Light CRISP acoustic master ~I=-8.5.

v2 closes two EMX dry-run gaps:
1) Explicit RING MOD lead/acid (Detune + Mod Depth; optional Mod→Pitch; modest vs kick)
2) Hat choke groups mirroring EMX 6A/6B · 7A/7B (closed vs open exclusive)
"""
from __future__ import annotations

import array
import json
import math
import re
import socket
import subprocess
import sys
import wave
from collections import defaultdict
from pathlib import Path

BRIDGE = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge")
sys.path.insert(0, str(BRIDGE))
import crisp_dna_to_ableton as dna  # noqa: E402
import build_classic_acid_liveset as classic  # noqa: E402
import build_liveset_15s_morphs as morph  # noqa: E402

_FF_FULL = r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
if Path(_FF_FULL).exists():
    dna.FFMPEG = _FF_FULL

SR = dna.SR
BPM = 162.0
BAR_S = 4.0 * 60.0 / BPM
HOST, PORT = "127.0.0.1", 9877

FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT = BRIDGE / "samples" / "crisp-dna" / "mentalclean-molecular-morph-162-v2"
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"
ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
CLIP_DIR = OUT / "ableton_clips"
CLIP_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_MentalClean_MolecularMorph_162_v2.mp3")
NOTES = OUT / "mentalclean_molecular_morph_162_v2_notes.md"

# Full Mix Learner map (MP3)
FULL_SECTIONS = [
    ("intro", 24, "intro"),
    ("predrop_vocal", 24, "predrop"),
    ("drop_1", 32, "drop"),
    ("break_1", 16, "break"),
    ("build", 24, "build"),
    ("drop_2_climax", 56, "drop_climax"),
    ("groove_sparse", 16, "groove"),
    ("break_2", 16, "break2"),
    ("drop_3", 80, "drop3"),
    ("outro", 27, "outro"),
]

# Ableton session: 8 clearest chapters (scene row limit)
ABLETON_SCENES = [
    (0, "Intro", "intro", 8),
    (1, "Predrop_Vox", "predrop", 8),
    (2, "Drop_1", "drop", 8),
    (3, "Break_1", "break", 8),
    (4, "Build", "build", 8),
    (5, "Drop_2_Climax", "drop_climax", 8),
    (6, "Groove_Sparse", "groove", 8),
    (7, "Drop_3_Outro", "drop3_outro", 8),
]
FIRE_ROW = 2  # Drop_1 — kick-first event

TUBE_GAIN = 1.85
DELAY_TIME_BEATS = 0.375
DELAY_WET = 0.06
DELAY_FB = 0.16
SWING_PCT = 0.54
SWING_DELAY = (SWING_PCT - 0.5) / ((2.0 / 3.0) - 0.5) * (0.25 / 3.0)

KICK_G = 1.55
BASS_G = KICK_G * (10 ** (-8.0 / 20.0))
HATS_G = 0.15
OH_G = 0.11
PERC_G = 0.20
ACID_G = 0.24
STRETCH_G = 0.26
VOX_G = 0.42  # clearly audible in predrop

# --- EMX RING MOD lead/acid (modest so mid wall does not bury kick) ---
# OSC type RING MOD: OSC1 * OSC2; EDIT1=ModDepth, plus Detune (cents) on OSC2.
# Optional Mod DEST=PITCH (slow LFO). HPF keeps it out of the kick pocket.
RM_G = 0.14
RM_WAVE1 = "saw"          # OSC1 carrier
RM_WAVE2 = "sin"          # OSC2 modulator
RM_MOD_DEPTH = 0.38       # OSC EDIT1 ~48/127 — blend, not 100% ring
RM_DETUNE_CENTS = 8.0     # slight OSC2 detune (Unison-like thickness)
RM_MOD_PITCH = 9          # OSC EDIT2 (-63..+63); +9 ≈ +0.29 oct
RM_MOD_TO_PITCH = True    # optional Mod → Pitch
RM_MOD_SPEED_HZ = 0.37    # LFO rate
RM_MOD_PITCH_DEPTH = 0.055  # modest ±5.5% pitch wander
RM_HPF_HZ = 190.0
RM_LPF_HZ = 2400.0

# EMX hat choke: 6A/6B and 7A/7B exclusive; simultaneous → B wins
CHOKE_FADE_MS = 3.5

# CRISP acoustic: light glue, presence ~6.5k, NOT dense smash
AF_CHAIN = (
    "highpass=f=28:poles=2,"
    "lowshelf=f=85:t=q:w=0.7:g=1.4,"
    "equalizer=f=52:t=q:w=1.0:g=3.2,"
    "equalizer=f=75:t=q:w=1.3:g=-1.8,"
    "equalizer=f=260:t=q:w=1.0:g=-1.5,"
    "equalizer=f=380:t=q:w=1.0:g=-1.2,"
    "equalizer=f=1400:t=q:w=1.0:g=0.6,"
    "equalizer=f=2800:t=q:w=1.3:g=1.1,"
    "equalizer=f=6500:t=q:w=1.1:g=1.5,"
    "equalizer=f=10000:t=q:w=1.1:g=-2.2,"
    "highshelf=f=8000:t=q:w=0.7:g=-2.6,"
    "lowpass=f=15000:poles=1,"
    "acompressor=threshold=-18dB:ratio=1.35:attack=12:release=180:makeup=1.08,"
    "alimiter=limit=0.91,"
    "loudnorm=I=-8.5:TP=-1.0:LRA=11"
)

classic.RES_Q = 0.11
classic.BASE_CUT0 = 220.0
classic.ENV_AMT = 1500.0
classic.ROLL_MAX = 70.0
classic.GRIT = 1.45
classic.ENV_DECAY = 0.9974
classic.OSC_KIND = "saw"
classic.OUT = OUT
classic.SECTION_MIX_DIR = SECTION_MIX_DIR
classic.BPM = BPM


def section_n(bars: int) -> int:
    return int(bars * 4.0 * 60.0 / BPM * SR)


def swing_offset(st: int) -> float:
    return SWING_DELAY if (st % 2 == 1) else 0.0


def emx_osc(phase: float, kind: str) -> float:
    """EMX RING MOD waveform set: Saw / Squ / Tri / Sin (+ Ns)."""
    p = phase - math.floor(phase)
    if kind == "saw":
        return 2.0 * p - 1.0
    if kind == "squ":
        return 1.0 if p < 0.5 else -1.0
    if kind == "tri":
        return 1.0 - 4.0 * abs(p - 0.5)
    if kind == "sin":
        return math.sin(2.0 * math.pi * p)
    if kind == "ns":
        return math.sin(2.0 * math.pi * p * 97.13) * 0.7
    return 2.0 * p - 1.0


def emx_modpitch_ratio(edit2: float) -> float:
    """EMX OSC EDIT2 ModPitch: ±63 = ±2 octaves."""
    return 2.0 ** (float(edit2) * (2.0 / 63.0))


class EmxChokePair:
    """EMX exclusive pair (6A/6B or 7A/7B).

    A and B cannot sound simultaneously. If both trigger on the same sample,
    only B sounds (manual: 6B/7B wins). A new trigger of one fades-then-zeros
    the other's ringing tail so closed/open hats never stack muddy.
    """

    def __init__(self, n: int, fade_ms: float = CHOKE_FADE_MS):
        self.n = n
        self.fade_n = max(8, int(fade_ms * 0.001 * SR))
        self.events = []  # (i0, part, wave, gain)

    def trig(self, part: str, wave, beat: float, gain: float = 1.0):
        if wave is None or gain <= 0:
            return
        i0 = int(beat * 60.0 / BPM * SR)
        if i0 < 0 or i0 >= self.n:
            return
        self.events.append((i0, part, wave, gain))

    def render(self):
        buf_a = [0.0] * self.n
        buf_b = [0.0] * self.n
        if not self.events:
            return buf_a, buf_b
        by_t = defaultdict(list)
        for ev in self.events:
            by_t[ev[0]].append(ev)
        active = {"A": None, "B": None}

        def mute(buf, at, end):
            if end is None or at >= end:
                return
            end = min(end, self.n)
            at = max(0, at)
            fn = self.fade_n
            for k in range(at, min(at + fn, end)):
                buf[k] *= 1.0 - (k - at) / max(1, fn)
            for k in range(min(at + fn, end), end):
                buf[k] = 0.0

        def put(buf, wave, i0, gain):
            end = min(self.n, i0 + len(wave))
            for k, x in enumerate(wave):
                j = i0 + k
                if j >= self.n:
                    break
                buf[j] += x * gain
            return i0, end

        for t in sorted(by_t):
            evs = by_t[t]
            parts = {e[1] for e in evs}
            if "A" in parts and "B" in parts:
                evs = [e for e in evs if e[1] == "B"]
                if active["A"] is not None:
                    mute(buf_a, t, active["A"][1])
                    active["A"] = None
            for i0, part, wave, gain in evs:
                other = "B" if part == "A" else "A"
                other_buf = buf_b if other == "B" else buf_a
                if active[other] is not None:
                    mute(other_buf, i0, active[other][1])
                    active[other] = None
                buf = buf_a if part == "A" else buf_b
                active[part] = put(buf, wave, i0, gain)
        return buf_a, buf_b


def place(buf, sample, beat, gain=1.0):
    dna.place(buf, sample, beat, gain)


def read_wav(path: Path) -> list[float]:
    return dna.read_wav(path)


def write_mono(path: Path, samples, peak_target=0.90):
    peak = max(1e-9, max((abs(x) for x in samples), default=1e-9))
    scale = peak_target / peak if peak > 1e-9 else 1.0
    data = array.array("h")
    for x in samples:
        data.append(max(-32767, min(32767, int(x * scale * 32767))))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def write_stereo_lr(path: Path, left, right, peak_target=0.90):
    n = min(len(left), len(right))
    peak = 1e-9
    for i in range(n):
        peak = max(peak, abs(left[i]), abs(right[i]))
    scale = peak_target / peak
    st = array.array("h")
    for i in range(n):
        st.append(max(-32767, min(32767, int(left[i] * scale * 32767))))
        st.append(max(-32767, min(32767, int(right[i] * scale * 32767))))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())


def electribe_master(src: Path, dst: Path):
    dna.electribe_master(src, dst)


def valve_force(samples: list[float], tube_gain: float = TUBE_GAIN) -> list[float]:
    bias = 0.03
    norm = math.tanh(tube_gain)
    out = [0.0] * len(samples)
    for i, x in enumerate(samples):
        driven = (x + bias) * tube_gain
        y = math.tanh(driven) / norm - bias * 0.5
        y = 0.9 * y + 0.1 * math.tanh(x * (tube_gain * 0.5))
        out[i] = y
    return out


def mild_compress_kick(samples: list[float], thr=0.38, ratio=1.65) -> list[float]:
    out = [0.0] * len(samples)
    env = 0.0
    atk_c = math.exp(-1.0 / (SR * 0.0025))
    rel_c = math.exp(-1.0 / (SR * 0.12))
    for i, x in enumerate(samples):
        a = abs(x)
        env = a + (env - a) * (atk_c if a > env else rel_c)
        if env > thr:
            over = env - thr
            gain = thr + over / ratio
            g = gain / max(1e-9, env)
        else:
            g = 1.0
        out[i] = x * g * 1.1
    return out


def one_pole(samples, cutoff_hz, mode="lpf", q=0.12):
    out = [0.0] * len(samples)
    l = b = 0.0
    for i, x in enumerate(samples):
        f = 2 * math.sin(math.pi * dna.clamp(cutoff_hz / SR, 0.0001, 0.45))
        l += f * b
        h = x - l - q * b
        b += f * h
        out[i] = h if mode == "hpf" else l
    return out


def bandpass(samples, lo, hi):
    return one_pole(one_pole(samples, lo, mode="hpf"), hi, mode="lpf")


def soft_gate(samples, thr=0.018):
    out = [0.0] * len(samples)
    env = 0.0
    for i, x in enumerate(samples):
        a = abs(x)
        env = a if a > env else env * 0.9991
        g = 1.0 if env > thr else env / max(thr, 1e-6)
        out[i] = x * min(1.0, g)
    return out


def pingpong_stereo(samples, time_beats=DELAY_TIME_BEATS, feedback=DELAY_FB, wet=DELAY_WET):
    d = max(1, int(time_beats * 60.0 / BPM * SR))
    L = list(samples)
    R = list(samples)
    for tap in range(4):
        delay = d * (tap + 1)
        g = wet * (feedback ** tap)
        side = tap % 2
        for i in range(delay, len(samples)):
            v = samples[i - delay] * g
            if side == 0:
                L[i] += v
            else:
                R[i] += v
    return L, R


def flanger(samples, rate_hz=0.95, depth_ms=4.2, base_ms=2.4, feedback=0.24, mix=0.48):
    n = len(samples)
    out = [0.0] * n
    max_delay = max(2, int((base_ms + depth_ms) * 0.001 * SR) + 3)
    circ = [0.0] * (max_delay + 4)
    feedback = min(0.45, abs(feedback))
    for i, x in enumerate(samples):
        t = i / SR
        mod = math.sin(2 * math.pi * rate_hz * t)
        delay_ms = base_ms + depth_ms * 0.5 * (1.0 + mod)
        d = delay_ms * 0.001 * SR
        di = int(d)
        frac = d - di
        i0 = (i - di) % len(circ)
        i1 = (i - di - 1) % len(circ)
        delayed = circ[i0] * (1 - frac) + circ[i1] * frac
        y = x + delayed * mix
        w = x + delayed * feedback
        w = max(-1.2, min(1.2, w))
        circ[i % len(circ)] = w
        out[i] = y
    return out


def chorus(samples, rate_hz=0.48, depth_ms=7.0, base_ms=10.0, mix=0.38):
    n = len(samples)
    out = [0.0] * n
    for i, x in enumerate(samples):
        t = i / SR
        mod = math.sin(2 * math.pi * rate_hz * t + 0.7)
        d = (base_ms + depth_ms * 0.5 * (1.0 + mod)) * 0.001 * SR
        di = int(d)
        frac = d - di
        j = i - di
        if j - 1 >= 0:
            delayed = samples[j] * (1 - frac) + samples[j - 1] * frac
        elif j >= 0:
            delayed = samples[j]
        else:
            delayed = 0.0
        out[i] = x * (1.0 - mix * 0.5) + delayed * mix
    return out


def mono_delay(samples, time_beats=0.375, wet=0.16, fb=0.24):
    d = max(1, int(time_beats * 60.0 / BPM * SR))
    out = [0.0] * len(samples)
    line = [0.0] * len(samples)
    for i, x in enumerate(samples):
        delayed = line[i - d] if i >= d else 0.0
        out[i] = x + delayed * wet
        line[i] = x + delayed * fb
    return out


def synth_bass_pulse() -> list[float]:
    n = int(0.22 * SR)
    out = [0.0] * n
    phase = 0.0
    f0 = 52.0
    for i in range(n):
        t = i / SR
        env = math.exp(-t / 0.11)
        pitch = f0 * (1.0 + 1.8 * math.exp(-t / 0.018))
        phase += 2 * math.pi * pitch / SR
        out[i] = math.sin(phase) * env * 0.85
    return mild_compress_kick(out, thr=0.45, ratio=1.4)


def synth_hard_click() -> list[float]:
    n = int(0.022 * SR)
    out = [0.0] * n
    rng = dna.mulberry32(0xC11C)
    for i in range(n):
        t = i / SR
        env = math.exp(-t / 0.0032)
        nse = (rng() * 2 - 1) * env
        tick = math.sin(2 * math.pi * 2800 * t) * math.exp(-t / 0.0025) * 0.55
        out[i] = (nse * 0.65 + tick) * 0.9
    out = one_pole(out, 1800.0, mode="hpf")
    out = one_pole(out, 9000.0, mode="lpf")
    return out


def make_stretch_loop(src_name: str, bars: int = 2) -> list[float]:
    src = FACTORY / src_name
    raw_dst = ONESHOT / f"stretch_raw_{src_name}"
    electribe_master(src, raw_dst)
    samples = read_wav(raw_dst)
    target_n = int(bars * 4.0 * 60.0 / BPM * SR)
    rb_in = ONESHOT / f"stretch_rb_in_{src_name}.wav"
    rb_out = ONESHOT / f"stretch_rb_out_{src_name}.wav"
    write_mono(rb_in, samples, 0.88)
    try:
        if len(samples) > 100:
            tempo = len(samples) / target_n
            r = subprocess.run(
                [dna.FFMPEG, "-y", "-i", str(rb_in), "-af", f"rubberband=tempo={tempo}:pitch=1", str(rb_out)],
                capture_output=True, text=True,
            )
            if r.returncode == 0 and rb_out.exists():
                samples = read_wav(rb_out)
    except Exception as e:
        print("rubberband", e)
    if len(samples) > target_n:
        samples = samples[:target_n]
    elif len(samples) < target_n:
        out = []
        while len(out) < target_n:
            out.extend(samples)
        samples = out[:target_n]
    fade = int(0.008 * SR)
    for i in range(fade):
        g = i / max(1, fade)
        samples[i] *= g
        samples[-(i + 1)] *= g
    samples = one_pole(samples, 1600.0, mode="lpf")
    return samples


def ensure_oneshots():
    """Load MULTIPLE distinct ESX one-shots — vary WHICH sample plays per section."""
    hat_map = {
        "hh1c": "054_HH-1C.wav", "hh1o": "055_HH-1O.wav",
        "hh3c": "058_HH-3C.wav", "hh3o": "059_HH-3O.wav",
        "hh5c": "062_HH-5C.wav", "hh5o": "063_HH-5O.wav",
        "hh7c": "066_HH-7C.wav", "hh7o": "067_HH-7O.wav",
    }
    rim_map = {"rim1": "045_Rim-1.wav", "rim2": "046_Rim-2.wav", "rim3": "047_Rim-3.wav"}
    perc_map = {"junk": "092_JunkPerc.wav", "synperc": "095_SynPerc.wav"}
    used = []
    shots = {}

    def load_named(src_name, dst_name):
        src = FACTORY / src_name
        dst = ONESHOT / dst_name
        if not src.exists():
            print("MISSING", src_name)
            return None
        electribe_master(src, dst)
        used.append(src_name)
        return read_wav(dst)

    # MentalClean / CRISP kick DNA: kb_kick_sledge + ESX SinKick body + mild compress (NOT dense smash)
    sink = load_named("146_SinKick.wav", "esx_SinKick.wav")
    sledge = dna.synth_kick_sledge(dna.mulberry32(0xE51), "full")
    sledge = [dna.tanh_drive(x, 2.0) for x in sledge]
    sledge = mild_compress_kick(sledge)
    if sink:
        n = max(len(sledge), len(sink))
        sledge = sledge + [0.0] * (n - len(sledge))
        sink = sink + [0.0] * (n - len(sink))
        body = one_pole(sink, 140.0, mode="lpf")
        kick = [0.55 * sledge[i] + 0.55 * body[i] for i in range(n)]
    else:
        kick = sledge
    kick = mild_compress_kick(kick)
    kick_thin = one_pole(kick, 95.0, mode="lpf")
    kick_thin = [x * 0.72 for x in kick_thin]
    kick_veiled = one_pole(kick, 80.0, mode="lpf")
    kick_veiled = [x * 0.55 for x in kick_veiled]

    for k, src in hat_map.items():
        raw = load_named(src, f"esx_{k}.wav")
        if raw:
            shots[k] = one_pole([dna.tanh_drive(x, 1.0) for x in raw], 6800.0, mode="lpf")
    for k, src in rim_map.items():
        raw = load_named(src, f"esx_{k}.wav")
        if raw:
            shots[k] = one_pole([dna.tanh_drive(x, 1.05) for x in raw], 5000.0, mode="lpf")
    for k, src in perc_map.items():
        raw = load_named(src, f"esx_{k}.wav")
        if raw:
            shots[k] = one_pole([dna.tanh_drive(x, 1.1) for x in raw], 4000.0, mode="lpf")

    stretches = {}
    for src_name in ("189_SynLP-1.wav", "175_PercLP-1.wav", "176_PercLP-2.wav", "177_PercLP-3.wav"):
        if (FACTORY / src_name).exists():
            stretches[src_name] = make_stretch_loop(src_name, bars=2)
            used.append(f"STRETCH:{src_name}")

    click = synth_hard_click()
    bass = synth_bass_pulse()
    write_mono(ONESHOT / "kick_ready.wav", kick, 0.94)
    return {
        "kick": kick,
        "kick_thin": kick_thin,
        "kick_veiled": kick_veiled,
        "click": click,
        "bass": bass,
        "hats": shots,
        "stretches": stretches,
        "used": used,
    }


def ensure_vox_phrases():
    voice_names = [
        "107_Voice-1.wav", "108_Voice-2.wav", "109_Voice-3.wav",
        "110_Voice-4.wav", "111_Voice-5.wav", "112_Voice-6.wav",
        "113_Voice-7.wav", "114_Voice-8.wav", "116_Voice-10.wav",
        "118_Voice-12.wav", "119_Voice-13.wav", "121_Voice-15.wav",
        "122_Voice-16.wav", "124_Voice-18.wav", "125_Voice-19.wav",
        "210_Voice-24.wav", "211_Voice-25.wav", "212_Voice-26.wav",
        "213_Voice-27.wav", "214_Voice-28.wav",
    ]
    phrases = []
    used = []
    rng = dna.mulberry32(0xF1A7)
    for src_name in voice_names:
        src = FACTORY / src_name
        if not src.exists():
            continue
        dst = ONESHOT / f"esx_{src_name}"
        electribe_master(src, dst)
        raw = read_wav(dst)
        if not raw:
            continue
        peak_i = max(range(len(raw)), key=lambda i: abs(raw[i]))
        for dur_s, tag in ((0.12, "short"), (0.20, "mid"), (0.32, "long")):
            start = max(0, peak_i - int(0.012 * SR))
            end = min(len(raw), start + int(dur_s * SR))
            chop = raw[start:end]
            if max(abs(x) for x in chop) < 1e-4:
                continue
            chop = bandpass(chop, 800.0, 4500.0)
            chop = soft_gate(chop, 0.01)
            chop = [math.tanh(x * 1.65) for x in chop]
            rate = 0.85 + 0.45 * rng()
            chop = flanger(
                chop, rate_hz=rate, depth_ms=3.8 + 2.0 * rng(),
                base_ms=2.0, feedback=0.22, mix=0.5 + 0.1 * rng(),
            )
            chop = chorus(chop, rate_hz=0.4 + 0.3 * rng(), mix=0.34 + 0.1 * rng())
            chop = bandpass(chop, 800.0, 4500.0)
            pk = max((abs(x) for x in chop), default=0.0)
            if pk > 0.95:
                chop = [x * (0.85 / pk) for x in chop]
            phrases.append(chop)
            used.append(f"{src_name}:{tag}")
    packs = []
    if phrases:
        for pi in range(8):
            pack = [0.0] * int(0.55 * SR)
            hits = 2 + int(rng() * 3)
            for h in range(hits):
                shot = phrases[int(rng() * len(phrases)) % len(phrases)]
                place(pack, shot, h * (0.12 + 0.06 * rng()) * (BPM / 60.0), 0.75 + 0.2 * rng())
            pack = mono_delay(pack, time_beats=0.375, wet=0.16, fb=0.2)
            pack = bandpass(pack, 800.0, 4500.0)
            packs.append(pack)
    print("VOX", len(phrases), "packs", len(packs))
    return phrases, packs, used


def mode_kit(mode: str):
    """Per-mode sample kit + gain multipliers — MUST differ between chapters."""
    # kick_db relative: intro/predrop thinner; drop = 1.0
    kits = {
        "intro": dict(
            kick_mul=0.50, bass_mul=0.20, hats_mul=0.05, oh_mul=0.0, perc_mul=0.0,
            stretch_mul=0.45, acid_mul=0.06, vox_mul=0.35, click_mul=0.0, valve=0.55, air=0.05,
            hat_c="hh1c", hat_o="hh1o", rim="rim1", perc=None, stretch="175_PercLP-1.wav",
            story="sparse veiled kick ~-6dB, stretch bed, almost no hats",
        ),
        "predrop": dict(
            kick_mul=0.42, bass_mul=0.35, hats_mul=0.12, oh_mul=0.0, perc_mul=0.05,
            stretch_mul=0.40, acid_mul=0.12, vox_mul=1.15, click_mul=0.0, valve=0.7, air=0.12,
            hat_c="hh1c", hat_o="hh1o", rim="rim1", perc=None, stretch="176_PercLP-2.wav",
            story="VOICE ENTERS — mid/vox chops every bar, thin kick",
        ),
        "drop": dict(
            kick_mul=1.0, bass_mul=1.0, hats_mul=0.85, oh_mul=0.65, perc_mul=0.5,
            stretch_mul=0.32, acid_mul=0.5, vox_mul=0.45, click_mul=1.0, valve=1.0, air=0.85,
            hat_c="hh3c", hat_o="hh3o", rim="rim2", perc="junk", stretch="189_SynLP-1.wav",
            story="kick alone 1-2 bars → bass → carved acid; hats HH-3",
        ),
        "break": dict(
            kick_mul=0.35, bass_mul=0.35, hats_mul=0.08, oh_mul=0.0, perc_mul=0.0,
            stretch_mul=0.55, acid_mul=0.18, vox_mul=0.65, click_mul=0.0, valve=0.55, air=0.08,
            hat_c="hh1c", hat_o="hh1o", rim=None, perc=None, stretch="177_PercLP-3.wav",
            story="~35% sparse kick, silence/space, stretch+vox breaths",
        ),
        "break2": dict(
            kick_mul=0.30, bass_mul=0.30, hats_mul=0.0, oh_mul=0.0, perc_mul=0.15,
            stretch_mul=0.5, acid_mul=0.15, vox_mul=0.55, click_mul=0.0, valve=0.5, air=0.1,
            hat_c="hh5c", hat_o="hh5o", rim="rim3", perc="synperc", stretch="175_PercLP-1.wav",
            story="different silence — rim/synperc ghosts, no hats",
        ),
        "build": dict(
            kick_mul=0.45, bass_mul=0.55, hats_mul=0.55, oh_mul=0.35, perc_mul=0.25,
            stretch_mul=0.45, acid_mul=0.4, vox_mul=0.75, click_mul=0.3, valve=0.85, air=0.4,
            hat_c="hh5c", hat_o="hh5o", rim="rim2", perc="junk", stretch="176_PercLP-2.wav",
            story="hats/air rise HH-5, expectancy",
        ),
        "drop_climax": dict(
            kick_mul=1.05, bass_mul=1.0, hats_mul=0.9, oh_mul=0.75, perc_mul=0.65,
            stretch_mul=0.38, acid_mul=0.65, vox_mul=0.7, click_mul=1.1, valve=1.05, air=0.95,
            hat_c="hh7c", hat_o="hh7o", rim="rim3", perc="junk", stretch="189_SynLP-1.wav",
            story="densest but carved mids; HH-7 + optional vox shout",
        ),
        "groove": dict(
            kick_mul=0.7, bass_mul=0.75, hats_mul=0.35, oh_mul=0.15, perc_mul=0.35,
            stretch_mul=0.28, acid_mul=0.22, vox_mul=0.3, click_mul=0.35, valve=0.75, air=0.2,
            hat_c="hh5c", hat_o="hh5o", rim="rim1", perc="synperc", stretch="177_PercLP-3.wav",
            story="half-time hats, mute games, synperc",
        ),
        "drop3": dict(
            kick_mul=1.0, bass_mul=0.95, hats_mul=0.75, oh_mul=0.55, perc_mul=0.55,
            stretch_mul=0.3, acid_mul=0.55, vox_mul=0.4, click_mul=0.95, valve=1.0, air=0.8,
            hat_c="hh3c", hat_o="hh7o", rim="rim2", perc="synperc", stretch="175_PercLP-1.wav",
            story="new perc+acid phrase; 4-bar hat mutes",
        ),
        "outro": dict(
            kick_mul=0.55, bass_mul=0.4, hats_mul=0.15, oh_mul=0.0, perc_mul=0.08,
            stretch_mul=0.2, acid_mul=0.08, vox_mul=0.15, click_mul=0.2, valve=0.55, air=0.08,
            hat_c="hh1c", hat_o="hh1o", rim=None, perc=None, stretch="176_PercLP-2.wav",
            story="elements peel away",
        ),
        "drop3_outro": dict(
            kick_mul=0.95, bass_mul=0.85, hats_mul=0.55, oh_mul=0.35, perc_mul=0.4,
            stretch_mul=0.25, acid_mul=0.4, vox_mul=0.3, click_mul=0.8, valve=0.9, air=0.55,
            hat_c="hh3c", hat_o="hh7o", rim="rim2", perc="synperc", stretch="175_PercLP-1.wav",
            story="Ableton merge: drop3 energy then fade last bars",
        ),
    }
    return kits[mode]



def poly_last_step_pattern(seed: int, cycle: int = 15):
    """Last Step-style 13/15 cycle vs 4/4 — notes rotate, never lock to bar grid."""
    rng = dna.mulberry32(seed + 1315 + cycle * 17)
    # Gm tekno degrees
    degrees = list(dna.PHRYGIAN_HZ)
    midis = list(dna.PHRYGIAN_MIDI)
    steps = []
    prev = 0.0
    for i in range(cycle):
        # denser than 16-step classic; still leave holes for poly feel
        rest_p = 0.18 if i % 5 == 2 else (0.12 if i % 3 == 1 else 0.06)
        if rng() < rest_p:
            steps.append({"note": 0.0, "midi": 0, "accent": False, "slide": False})
            continue
        idx = int(rng() * len(degrees))
        if rng() < 0.6:
            idx = idx % 5
        hz = degrees[idx]
        midi = midis[idx]
        accent = (i % cycle in (0, 4, 8, 11)) or (rng() < 0.25)
        slide = prev > 0 and rng() < 0.32
        steps.append({"note": hz, "midi": midi, "accent": accent, "slide": slide})
        prev = hz
    return steps


def render_poly_acid(pattern, cycle: int, grit=None, roll=True) -> list[float]:
    """Render acid where pattern index = global_16th % cycle (13 or 15 vs 4/4 kick)."""
    grit = classic.GRIT if grit is None else grit
    step = (60.0 / BPM) / 4.0
    total_steps = classic.BARS * 16
    out = [0.0] * classic.N
    l = b = 0.0
    phase = 0.0
    cur_hz = dna.PHRYGIAN_HZ[0]
    target_hz = cur_hz
    env = 0.0
    res_q = classic.RES_Q
    base_cut0 = classic.BASE_CUT0
    env_amt = classic.ENV_AMT
    grit_drive = grit
    step_idx = -1
    for i in range(classic.N):
        tsec = i / SR
        s = min(total_steps - 1, int(tsec / step))
        if s != step_idx:
            step_idx = s
            bar = s // 16
            st = s % cycle  # POLY: cycle against 16ths, not bar-locked 16
            if roll:
                x = bar / max(1, classic.BARS - 1)
                roll_amt = x * classic.ROLL_MAX
            else:
                roll_amt = 0.0
            local_q = res_q
            if bar >= classic.BARS - 3:
                local_q = max(0.12, res_q * 0.92)
            p = pattern[st]
            if p["note"] > 0:
                target_hz = p["note"]
                if not p["slide"]:
                    cur_hz = target_hz
                env = 1.0 if p["accent"] else 0.58
            elif not p.get("slide"):
                env *= 0.12
            render_poly_acid._base = base_cut0 + roll_amt  # type: ignore
            render_poly_acid._q = local_q  # type: ignore
        base_cut = getattr(render_poly_acid, "_base", base_cut0)
        local_q = getattr(render_poly_acid, "_q", res_q)
        cur_hz += (target_hz - cur_hz) * (0.008 if env > 0.4 else 0.003)
        env *= classic.ENV_DECAY
        phase += cur_hz / SR
        phase -= math.floor(phase)
        if classic.OSC_KIND == "saw":
            osc = (2.0 * phase - 1.0) * env * 0.48
        else:
            osc = (1.0 if phase < 0.5 else -1.0) * env * 0.42
        cut = base_cut + env * env_amt
        f = 2 * math.sin(math.pi * dna.clamp(cut / SR, 0.0001, 0.45))
        l += f * b
        h = osc - l - local_q * b
        b += f * h
        y = dna.tanh_drive(l, grit_drive)
        out[i] = y
    return out


def render_ringmod_voice(pattern, cycle: int) -> list[float]:
    """EMX RING MOD lead/acid: OSC1×OSC2 mix via ModDepth; OSC2 = ModPitch+Detune.

    Optional Mod→Pitch LFO. Milder filter/grit than the 303 so it sits as a
    second voice without building a mid wall over the kick.
    """
    step = (60.0 / BPM) / 4.0
    total_steps = classic.BARS * 16
    out = [0.0] * classic.N
    l = b = 0.0
    phase1 = 0.0
    phase2 = 0.0
    cur_hz = dna.PHRYGIAN_HZ[0]
    target_hz = cur_hz
    env = 0.0
    res_q = 0.09
    base_cut0 = 380.0
    env_amt = 1100.0
    grit = 1.25
    env_decay = 0.9976
    ratio0 = emx_modpitch_ratio(RM_MOD_PITCH) * (2.0 ** (RM_DETUNE_CENTS / 1200.0))
    depth = RM_MOD_DEPTH
    step_idx = -1
    base_cut = base_cut0
    local_q = res_q
    for i in range(classic.N):
        tsec = i / SR
        s = min(total_steps - 1, int(tsec / step))
        if s != step_idx:
            step_idx = s
            bar = s // 16
            st = s % cycle
            roll_amt = (bar / max(1, classic.BARS - 1)) * 40.0
            p = pattern[st]
            if p["note"] > 0:
                target_hz = p["note"]
                if not p["slide"]:
                    cur_hz = target_hz
                env = 1.0 if p["accent"] else 0.55
            elif not p.get("slide"):
                env *= 0.10
            base_cut = base_cut0 + roll_amt
            local_q = res_q
        cur_hz += (target_hz - cur_hz) * (0.008 if env > 0.4 else 0.003)
        env *= env_decay
        pitch_mul = 1.0
        if RM_MOD_TO_PITCH:
            pitch_mul = 1.0 + RM_MOD_PITCH_DEPTH * math.sin(2.0 * math.pi * RM_MOD_SPEED_HZ * tsec)
        f1 = max(20.0, cur_hz * pitch_mul)
        f2 = max(20.0, cur_hz * ratio0 * pitch_mul)
        phase1 += f1 / SR
        phase1 -= math.floor(phase1)
        phase2 += f2 / SR
        phase2 -= math.floor(phase2)
        o1 = emx_osc(phase1, RM_WAVE1) * env * 0.42
        o2 = emx_osc(phase2, RM_WAVE2)
        ring = o1 * o2
        osc = (1.0 - depth) * o1 + depth * ring
        cut = base_cut + env * env_amt
        f = 2 * math.sin(math.pi * dna.clamp(cut / SR, 0.0001, 0.45))
        l += f * b
        h = osc - l - local_q * b
        b += f * h
        out[i] = dna.tanh_drive(l, grit)
    return out


def render_section(idx: int, name: str, bars: int, mode: str, shots, phrases, packs, out_prefix: Path):
    N = section_n(bars)
    classic.BPM = BPM
    classic.BARS = bars
    classic.BEATS = bars * 4
    classic.N = N
    dna.BPM = BPM
    dna.BARS = bars
    dna.BEATS = bars * 4
    dna.N = N

    kit = mode_kit(mode)
    hats = shots["hats"]
    hat_c = hats.get(kit["hat_c"]) or hats.get("hh1c") or dna.synth_hat(dna.mulberry32(1), False)
    hat_o = hats.get(kit["hat_o"]) or hats.get("hh1o") or dna.synth_hat(dna.mulberry32(2), True)
    # Intra-section morph tables (every 8–16 bars) so long drops never loop same bed
    hat_morph_c = [kit["hat_c"], "hh5c", "hh3c", "hh7c", "hh1c"]
    hat_morph_o = [kit["hat_o"], "hh5o", "hh3o", "hh7o", "hh1o"]
    rim_morph = [kit.get("rim"), "rim1", "rim2", "rim3", None]
    perc_morph = [kit.get("perc"), "junk", "synperc", None, "junk"]
    rim = hats.get(kit["rim"]) if kit["rim"] else None
    # rim stored in hats dict wrongly — fix: shots has rim keys at top via hats merge
    # actually rim/perc are in shots["hats"] only if I put them there — I put rim in shots via same dict "hats"
    # Wait - I put rim1 etc in shots dict under shots from hat_map AND rim_map into shots variable locally
    # Looking at ensure_oneshots: shots[k] for hats and rims go into local `shots` then returned as "hats": shots
    # So rim1 is in shots["hats"]["rim1"]
    rim = shots["hats"].get(kit["rim"]) if kit.get("rim") else None
    perc = shots["hats"].get(kit["perc"]) if kit.get("perc") else None
    stretch_one = shots["stretches"].get(kit["stretch"])
    if stretch_one is None and shots["stretches"]:
        stretch_one = next(iter(shots["stretches"].values()))

    kick = shots["kick"]
    kick_thin = shots["kick_thin"]
    kick_veiled = shots["kick_veiled"]
    click = shots["click"]
    bass = shots["bass"]

    trk_k = [0.0] * N
    trk_b = [0.0] * N
    trk_h = [0.0] * N
    trk_oh = [0.0] * N
    trk_p = [0.0] * N
    trk_st = [0.0] * N
    trk_v = [0.0] * N

    # EMX exclusive pairs: 6A closed / 6B open  ·  7A alt-closed / 7B alt-open
    group6 = EmxChokePair(N, fade_ms=CHOKE_FADE_MS)
    group7 = EmxChokePair(N, fade_ms=CHOKE_FADE_MS)
    hat7_c = hats.get("hh7c") if kit["hat_c"] != "hh7c" else hats.get("hh5c") or hat_c
    hat7_o = hats.get("hh7o") if kit["hat_o"] != "hh7o" else hats.get("hh5o") or hat_o

    rng = dna.mulberry32(0x1680 + idx * 97 + hash(mode) % 1000)
    pattern = classic.classic_pattern(dna.SEED + 303 + idx * 17)

    for bar in range(bars):
        base = bar * 4.0
        # flip samples/rhythm role every 8 bars (16 on very long drop3 blocks)
        morph_period = 16 if (mode in ("drop3", "drop_climax") and bars >= 48) else 8
        morph_i = (bar // morph_period) % 5
        hat_c = hats.get(hat_morph_c[morph_i]) or hat_c
        hat_o = hats.get(hat_morph_o[morph_i]) or hat_o
        hat7_c = hats.get(hat_morph_c[(morph_i + 2) % 5]) or hat7_c
        hat7_o = hats.get(hat_morph_o[(morph_i + 2) % 5]) or hat7_o
        rim_key = rim_morph[morph_i]
        perc_key = perc_morph[morph_i]
        rim = shots["hats"].get(rim_key) if rim_key else None
        perc = shots["hats"].get(perc_key) if perc_key else None
        drop_modes = ("drop", "drop_climax", "drop3", "drop3_outro")
        drop_entry = mode in drop_modes and bar < 2
        mid_ok = not (mode in drop_modes and bar < 2)
        vox_ok = not (mode in drop_modes and bar < 4)
        bass_ok = not (mode in drop_modes and bar < 1)

        # --- KICK patterns morph per mode ---
        if mode == "intro":
            if bar % 4 == 0:
                place(trk_k, kick_veiled, base, 0.85)
            elif bar % 4 == 2:
                place(trk_k, kick_veiled, base + 2.0, 0.4)
        elif mode == "predrop":
            if bar % 2 == 0:
                place(trk_k, kick_thin, base, 0.7)
            else:
                place(trk_k, kick_thin, base, 0.55)
                place(trk_k, kick_thin, base + 2.0, 0.4)
        elif mode in ("break", "break2"):
            # ~35% of bars
            if bar % 3 == 0:
                place(trk_k, kick_veiled, base, 0.7)
            elif mode == "break2" and bar % 3 == 2:
                place(trk_k, kick_thin, base + 2.0, 0.45)
        elif mode == "build":
            dens = bar / max(1, bars - 1)
            if dens < 0.35:
                if bar % 2 == 0:
                    place(trk_k, kick_thin, base, 0.55)
            elif dens < 0.7:
                for step in (0, 8):
                    place(trk_k, kick_thin, base + step * 0.25, 0.65)
            else:
                for qi, step in enumerate((0, 4, 8, 12)):
                    place(trk_k, kick, base + step * 0.25, 0.75 + 0.1 * dens)
                    place(trk_k, click, base + step * 0.25, 0.2 * dens)
        elif mode == "groove":
            # half-time-ish: kick on 1 and 3 only some bars, else 4/4 quieter
            if bar % 2 == 0:
                for step in (0, 8):
                    place(trk_k, kick, base + step * 0.25, 0.9)
                    place(trk_k, click, base + step * 0.25, 0.25)
            else:
                for qi, step in enumerate((0, 4, 8, 12)):
                    place(trk_k, kick, base + step * 0.25, 0.75)
                    place(trk_k, click, base + step * 0.25, 0.28)
        elif mode in drop_modes or mode == "outro":
            fade = 1.0
            if mode == "outro":
                fade = max(0.1, 1.0 - bar / max(1, bars))
            elif mode == "drop3_outro" and bar >= bars // 2:
                fade = max(0.15, 1.0 - (bar - bars // 2) / max(1, bars // 2))
            # mute game on drop3: skip hats later; kick always
            for qi, step in enumerate((0, 4, 8, 12)):
                if drop_entry and bar == 0 and qi > 0:
                    continue  # first bar: only downbeat-ish — actually place all but quieter mids wait
                g = (1.1 if qi in (0, 3) else 1.0) * fade
                place(trk_k, kick, base + step * 0.25, g)
                if not drop_entry:
                    place(trk_k, click, base + step * 0.25, 0.35 * fade * kit["click_mul"])

        # first bar of drop: kick only on beats (already), no bass/mid
        if bass_ok and mode not in ("intro", "break", "break2"):
            steps = (0, 4, 8, 12)
            if mode == "predrop":
                steps = (0, 8) if bar % 2 == 1 else (0,)
            elif mode == "build":
                steps = (0, 8) if bar < bars // 2 else (0, 4, 8, 12)
            elif mode == "groove":
                steps = (0, 8) if bar % 2 == 0 else (0, 4, 8, 12)
            for step in steps:
                place(trk_b, bass, base + step * 0.25, 0.9 if mode.startswith("drop") else 0.65)

        # HATS — EMX choke groups 6A/6B (main C/O) and 7A/7B (ghost/alt)
        # Simultaneous 6A+6B on the same 16th → 6B wins (open), no muddy stack.
        if mode in ("drop", "drop_climax") and mid_ok:
            for st in (2, 6, 10, 14):
                group6.trig("A", hat_c, base + st * 0.25 + swing_offset(st), 0.5)
            if bar % 2 == 1:
                group6.trig("B", hat_o, base + 14 * 0.25 + swing_offset(14), 0.3)
            if mode == "drop_climax" and bar % 4 == 0:
                for st in (3, 7, 11):
                    group7.trig("A", hat7_c, base + st * 0.25 + swing_offset(st), 0.2)
                group7.trig("B", hat7_o, base + 14 * 0.25 + swing_offset(14), 0.18)
        elif mode == "drop3" and mid_ok:
            # mute games every 4 bars
            if (bar // 4) % 2 == 0:
                for st in (2, 6, 10, 14):
                    group6.trig("A", hat_c, base + st * 0.25 + swing_offset(st), 0.45)
                group6.trig("B", hat_o, base + 6 * 0.25 + swing_offset(6), 0.28)
            else:
                for st in (6, 14):
                    group6.trig("A", hat_c, base + st * 0.25 + swing_offset(st), 0.35)
                group7.trig("A", hat7_c, base + 10 * 0.25 + swing_offset(10), 0.22)
        elif mode == "drop3_outro" and mid_ok:
            if bar < bars // 2:
                for st in (2, 6, 10, 14):
                    group6.trig("A", hat_c, base + st * 0.25 + swing_offset(st), 0.42)
            else:
                if bar % 2 == 0:
                    group6.trig("A", hat_c, base + 14 * 0.25, 0.25)
        elif mode == "build":
            dens = bar / max(1, bars - 1)
            steps = [14]
            if dens > 0.3:
                steps = [6, 14]
            if dens > 0.55:
                steps = [2, 6, 10, 14]
            if dens > 0.8:
                steps = [2, 3, 6, 10, 11, 14]
            for st in steps:
                if st in (3, 11):
                    group7.trig("A", hat7_c, base + st * 0.25 + swing_offset(st), 0.25 + 0.35 * dens)
                else:
                    group6.trig("A", hat_c, base + st * 0.25 + swing_offset(st), 0.25 + 0.35 * dens)
            if dens > 0.6:
                group6.trig("B", hat_o, base + 14 * 0.25, 0.2 + 0.2 * dens)
        elif mode == "groove":
            for st in (6, 14):
                group6.trig("A", hat_c, base + st * 0.25 + swing_offset(st), 0.38)
            if bar % 2 == 1:
                group7.trig("A", hat7_c, base + 3 * 0.25 + swing_offset(3), 0.22)
        elif mode == "predrop" and bar > 4:
            group6.trig("A", hat_c, base + 14 * 0.25 + swing_offset(14), 0.22)
        elif mode == "outro" and bar < bars * 0.5:
            group6.trig("A", hat_c, base + 14 * 0.25, 0.18)

        # PERC
        if mid_ok and rim is not None and mode in ("drop", "drop_climax", "build", "groove", "drop3", "drop3_outro"):
            place(trk_p, rim, base + 1.0, 0.32)
            if mode in ("drop_climax", "drop3") and bar % 2 == 1:
                place(trk_p, rim, base + 2.75, 0.22)
        if perc is not None and mode in ("drop_climax", "groove", "drop3", "break2", "drop3_outro"):
            if bar % 4 == (2 if mode != "break2" else 1):
                place(trk_p, perc, base + 1.75 + swing_offset(7), 0.14)

        # STRETCH
        if stretch_one is not None:
            if mode in ("intro", "predrop", "break", "break2"):
                if bar % 2 == 0:
                    place(trk_st, stretch_one, base, 0.5)
            elif mode == "build":
                place(trk_st, stretch_one, base, 0.3 + 0.3 * (bar / max(1, bars - 1)))
            elif mid_ok and mode in ("drop", "drop_climax", "groove", "drop3") and bar % 2 == 0:
                place(trk_st, stretch_one, base, 0.28)
            elif mode in ("outro", "drop3_outro") and bar < bars * 0.7 and bar % 2 == 0:
                place(trk_st, stretch_one, base, 0.2)

        # VOX — Predrop CLEARLY audible every bar
        if phrases:
            if mode == "predrop":
                pack = packs[bar % len(packs)] if packs else phrases[bar % len(phrases)]
                place(trk_v, pack, base + 0.5, 0.85)
                shot = phrases[(bar * 3) % len(phrases)]
                place(trk_v, shot, base + 2.0, 0.7)
                if bar % 2 == 1:
                    place(trk_v, phrases[(bar * 5) % len(phrases)], base + 3.25, 0.55)
            elif mode in ("break", "break2") and bar % 2 == 0:
                place(trk_v, phrases[bar % len(phrases)], base + 1.0, 0.6)
            elif mode == "build" and bar > 2:
                if bar % 2 == 0:
                    place(trk_v, phrases[bar % len(phrases)], base + 1.5, 0.5)
            elif mode in ("drop", "drop_climax", "drop3") and vox_ok:
                if mode == "drop_climax" and bar % 4 == 0 and packs:
                    place(trk_v, packs[bar % len(packs)], base + 1.5, 0.65)
                elif bar % 3 == 1:
                    place(trk_v, phrases[bar % len(phrases)], base + 2.5, 0.4)
            elif mode == "intro" and bar % 8 == 4:
                place(trk_v, phrases[0], base + 2.0, 0.35)

    # Finalize EMX hat choke groups → exclusive closed/open stems
    h6a, h6b = group6.render()
    h7a, h7b = group7.render()
    for i in range(N):
        trk_h[i] = h6a[i] + h7a[i]
        trk_oh[i] = h6b[i] + h7b[i]

    # Acid — poly Last Step 13/15 vs 4/4 kick; cycle flips per chapter
    acid_drive = {
        "intro": 0.06, "predrop": 0.14, "break": 0.18, "break2": 0.15, "build": 0.5,
        "drop": 0.42, "drop_climax": 0.62, "groove": 0.2, "drop3": 0.5,
        "outro": 0.08, "drop3_outro": 0.38,
    }.get(mode, 0.2)
    # Alternate 15 / 13 so drop_3 feels like a new phrase (not same 4 bars forever)
    cycle = 15 if mode in ("intro", "predrop", "drop", "build", "drop_climax", "outro") else 13
    if mode in ("drop3", "drop3_outro", "groove", "break2"):
        cycle = 13
    if mode in ("break",):
        cycle = 15
    poly_pat = poly_last_step_pattern(dna.SEED + 303 + idx * 17 + cycle, cycle=cycle)
    acid_full = render_poly_acid(poly_pat, cycle=cycle, grit=classic.GRIT, roll=True)
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))
    if mode in ("drop", "drop_climax", "drop3", "drop3_outro") and acid_drive > 0:
        acid = one_pole(acid, 1350.0, mode="lpf")
        beat_n = int(60.0 / BPM * SR)
        for b in range(bars * 4):
            i0 = b * beat_n
            for j in range(min(int(0.04 * SR), N - i0)):
                acid[i0 + j] *= 0.32
    elif acid_drive > 0:
        acid = one_pole(acid, 1500.0, mode="lpf")

    # Ring Mod lead — invert cycle vs 303 so the two voices weave (poly)
    rm_drive = {
        "intro": 0.04, "predrop": 0.10, "break": 0.12, "break2": 0.08, "build": 0.36,
        "drop": 0.30, "drop_climax": 0.40, "groove": 0.15, "drop3": 0.34,
        "outro": 0.05, "drop3_outro": 0.26,
    }.get(mode, 0.16)
    rm_cycle = 13 if cycle == 15 else 15
    rm_pat = poly_last_step_pattern(dna.SEED + 707 + idx * 23 + rm_cycle, cycle=rm_cycle)
    rm_full = render_ringmod_voice(rm_pat, cycle=rm_cycle)
    rm = [x * rm_drive for x in rm_full[:N]]
    if len(rm) < N:
        rm.extend([0.0] * (N - len(rm)))
    if rm_drive > 0:
        rm = one_pole(rm, RM_HPF_HZ, mode="hpf")
        rm = one_pole(rm, RM_LPF_HZ, mode="lpf")
        if mode in ("drop", "drop_climax", "drop3", "drop3_outro"):
            beat_n = int(60.0 / BPM * SR)
            for b in range(bars * 4):
                i0 = b * beat_n
                for j in range(min(int(0.045 * SR), N - i0)):
                    rm[i0 + j] *= 0.28

    if any(abs(x) > 1e-6 for x in trk_v):
        trk_v = flanger(trk_v, rate_hz=0.95, depth_ms=4.0, base_ms=2.2, feedback=0.2, mix=0.42)
        trk_v = mono_delay(trk_v, time_beats=0.375, wet=0.14, fb=0.18)
        trk_v = bandpass(trk_v, 800.0, 4500.0)
        trk_v = soft_gate(trk_v, 0.007)

    g_kick = KICK_G * kit["kick_mul"]
    g_bass = BASS_G * kit["bass_mul"]
    g_hats = HATS_G * kit["hats_mul"]
    g_oh = OH_G * kit["oh_mul"]
    g_perc = PERC_G * kit["perc_mul"]
    g_st = STRETCH_G * kit["stretch_mul"]
    g_acid = ACID_G * kit["acid_mul"]
    g_rm = RM_G * kit["acid_mul"] * 0.85
    g_vox = VOX_G * kit["vox_mul"]
    tube = TUBE_GAIN * kit["valve"]

    dry = [0.0] * N
    for i in range(N):
        dry[i] = (
            trk_k[i] * g_kick + trk_b[i] * g_bass + acid[i] * g_acid
            + rm[i] * g_rm
            + trk_h[i] * g_hats + trk_oh[i] * g_oh + trk_p[i] * g_perc
            + trk_st[i] * g_st + trk_v[i] * g_vox
        )
    send_src = [0.0] * N
    air = kit["air"]
    for i in range(N):
        send_src[i] = (
            acid[i] * g_acid * 0.3 * air + rm[i] * g_rm * 0.22 * air
            + trk_h[i] * g_hats * 0.5 * air
            + trk_oh[i] * g_oh * 0.3 * air + trk_v[i] * g_vox * 0.55
            + trk_st[i] * g_st * 0.2
        )
    Lpp, Rpp = pingpong_stereo(send_src, wet=DELAY_WET * (0.5 + 0.5 * air), feedback=DELAY_FB)
    left = [0.0] * N
    right = [0.0] * N
    for i in range(N):
        left[i] = dry[i] + (Lpp[i] - send_src[i]) * 0.85
        right[i] = dry[i] + (Rpp[i] - send_src[i]) * 0.85
    left = valve_force(left, tube_gain=tube)
    right = valve_force(right, tube_gain=tube)
    peak = 1e-9
    for i in range(N):
        peak = max(peak, abs(left[i]), abs(right[i]))
    if peak > 0.95:
        s = 0.92 / peak
        left = [x * s for x in left]
        right = [x * s for x in right]

    paths = {
        "kick": out_prefix.with_name(out_prefix.name + "_kick.wav"),
        "hats": out_prefix.with_name(out_prefix.name + "_hats.wav"),
        "oh": out_prefix.with_name(out_prefix.name + "_oh.wav"),
        "perc": out_prefix.with_name(out_prefix.name + "_perc.wav"),
        "stretch": out_prefix.with_name(out_prefix.name + "_stretch.wav"),
        "acid": out_prefix.with_name(out_prefix.name + "_acid.wav"),
        "ringmod": out_prefix.with_name(out_prefix.name + "_ringmod.wav"),
        "vox": out_prefix.with_name(out_prefix.name + "_vox.wav"),
        "bass": out_prefix.with_name(out_prefix.name + "_bass.wav"),
        "mix": out_prefix.with_name(out_prefix.name + "_mix.wav"),
    }
    write_mono(paths["kick"], [trk_k[i] * g_kick for i in range(N)], 0.9)
    write_mono(paths["hats"], [trk_h[i] * g_hats for i in range(N)], 0.85)
    write_mono(paths["oh"], [trk_oh[i] * g_oh for i in range(N)], 0.85)
    write_mono(paths["perc"], [trk_p[i] * g_perc for i in range(N)], 0.85)
    write_mono(paths["stretch"], [trk_st[i] * g_st for i in range(N)], 0.85)
    write_mono(paths["acid"], [acid[i] * g_acid for i in range(N)], 0.85)
    write_mono(paths["ringmod"], [rm[i] * g_rm for i in range(N)], 0.85)
    write_mono(paths["vox"], [trk_v[i] * g_vox for i in range(N)], 0.88)
    write_mono(paths["bass"], [trk_b[i] * g_bass for i in range(N)], 0.88)
    write_stereo_lr(paths["mix"], left, right, 0.90)

    meta = {
        "name": name, "mode": mode, "bars": bars, "story": kit["story"],
        "hat": kit["hat_c"], "rim": kit["rim"], "perc": kit["perc"], "stretch": kit["stretch"],
        "acid_cycle": cycle,
        "rm_cycle": rm_cycle,
        "choke": "EMX 6A/6B + 7A/7B exclusive (B wins if simultaneous)",
        "gains": dict(kick=g_kick, bass=g_bass, hats=g_hats, vox=g_vox, acid=g_acid, ringmod=g_rm),
    }
    print(f"section {idx} {name} mode={mode} bars={bars} poly={cycle} rm={rm_cycle} vox_g={g_vox:.2f} | {kit['story']}")
    return paths, meta


def bounce_mp3(mix_paths, mp3_path: Path) -> float:
    listfile = OUT / "_concat_story.txt"
    raw_concat = OUT / "_concat_story.wav"
    mastered = OUT / "_master_story.wav"
    with open(listfile, "w", encoding="utf-8") as f:
        for p in mix_paths:
            f.write(f"file '{str(p).replace(chr(92), '/')}'\n")
    subprocess.run(
        [dna.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(raw_concat)],
        check=True, capture_output=True,
    )
    r = subprocess.run(
        [dna.FFMPEG, "-y", "-i", str(raw_concat), "-af", AF_CHAIN, str(mastered)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("master fail", r.stderr[-2500:])
        raise RuntimeError("CRISP acoustic master failed")
    subprocess.run(
        [dna.FFMPEG, "-y", "-i", str(mastered), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)],
        check=True, capture_output=True,
    )
    dur = 0.0
    try:
        ffprobe = str(Path(dna.FFMPEG).parent / "ffprobe.exe")
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(mp3_path)],
            capture_output=True, text=True, check=True,
        )
        dur = float(probe.stdout.strip())
    except Exception as e:
        print("ffprobe", e)
        dur = sum(b for _, b, _ in FULL_SECTIONS) * BAR_S
    print("MP3", mp3_path, "dur", round(dur, 2))
    return dur


def measure_lufs(path: Path) -> dict:
    """ffmpeg ebur128 integrated / true-peak / LRA."""
    out = {"I": None, "TP": None, "LRA": None, "raw": ""}
    try:
        r = subprocess.run(
            [dna.FFMPEG, "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True,
        )
        txt = (r.stderr or "") + (r.stdout or "")
        out["raw"] = txt[-2500:]
        m_i = re.search(r"I:\s+(-?[0-9.]+)\s+LUFS", txt)
        m_tp = re.search(r"Peak:\s+(-?[0-9.]+)\s+dBFS", txt)
        if m_tp is None:
            m_tp = re.search(r"True peak:\s+(-?[0-9.]+)\s+dBTP", txt, re.I)
        if m_tp is None:
            m_tp = re.search(r"Peak:\s+(-?[0-9.]+)\s+dBTP", txt, re.I)
        m_lra = re.search(r"LRA:\s+(-?[0-9.]+)\s+LU", txt)
        if m_i:
            out["I"] = float(m_i.group(1))
        if m_tp:
            out["TP"] = float(m_tp.group(1))
        if m_lra:
            out["LRA"] = float(m_lra.group(1))
    except Exception as e:
        out["raw"] = str(e)
    print("LUFS", path.name, "I=", out["I"], "TP=", out["TP"], "LRA=", out["LRA"])
    return out


def send(cmd, params=None, timeout=90.0):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall(payload)
        sock.settimeout(timeout)
        chunks = []
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue
    return {"status": "error", "message": "no response"}


def ok(r, label):
    if r.get("status") != "success":
        print("FAIL", label, r.get("message", r))
        return None
    print("OK", label)
    return r.get("result", r)


def safe_delete(track_index, clip_index):
    send("delete_clip", {"track_index": track_index, "clip_index": clip_index})


def load_audio(track_index, clip_index, path: Path, name: str, timeout=55.0):
    """Timeout-safe create_audio_clip (hangs were common at 120s with long stems)."""
    safe_delete(track_index, clip_index)
    r = send(
        "create_audio_clip",
        {"track_index": track_index, "clip_index": clip_index, "path": str(path)},
        timeout=timeout,
    )
    if r.get("status") != "success":
        print("FAIL create_audio_clip", name, r.get("message", r))
        return False
    send("set_clip_name", {"track_index": track_index, "clip_index": clip_index, "name": name})
    print("CLIP", name, "->", track_index, clip_index)
    return True


def silence_beds(by_full):
    for name, t in by_full.items():
        if t.get("type") is False or t.get("is_audio_track") is False:
            # mute MIDI beds that fight
            if any(x in name for x in ("Drum Rack", "Tholin", "CRISP_e2e")):
                send("set_track_mute", {"track_index": t["index"], "mute": True})


def ableton_load(scene_paths, scene_meta):
    snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=60)
    snap = ok(snap_r, "snapshot")
    if not snap:
        return {"ok": False, "error": "no Ableton snapshot"}

    ok(send("set_tempo", {"tempo": BPM}), "tempo 162")
    ok(send("stop_playback"), "stop")

    for t in snap["tracks"]:
        for sl in t.get("clip_slots") or []:
            if sl.get("has_clip"):
                send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})

    by = {t["name"]: t["index"] for t in snap["tracks"]}
    by_full = {t["name"]: t for t in snap["tracks"]}
    print("tracks", by)
    try:
        silence_beds(by_full)
    except Exception as e:
        print("silence_beds", e)

    kick_idx = by.get("E-Kick")
    hats_idx = by.get("E-Hats")
    oh_idx = by.get("E-OHat") or by.get("E-Snare")
    perc_idx = by.get("E-Perc")
    acid_idx = by.get("Acid 303") or by.get("E-Syn")
    stretch_idx = by.get("ESX Stretch")
    # prefer track 7 if duplicates
    if stretch_idx is None:
        for n, i in by.items():
            if "Stretch" in n:
                stretch_idx = i
                break
    vox_idx = by.get("ESX VoxAud") or by.get("E-Atm") or by.get("E-Mental")
    if vox_idx is not None:
        send("set_track_name", {"track_index": vox_idx, "name": "ESX VoxAud"})
    jam_idx = by.get("E-DrumLP") or by.get("ES1 90s") or by.get("E-Mental")
    if jam_idx == vox_idx:
        jam_idx = by.get("ES1 90s") or by.get("E-DrumLP")
    rm_idx = by.get("E-Syn") or by.get("E-Mental") or by.get("Ring Mod")
    if rm_idx in (vox_idx, jam_idx, acid_idx, stretch_idx):
        rm_idx = None
    bass_idx = by.get("Tholin Bass")  # may be MIDI — skip if not audio
    # use E-Atm leftover? Put bass on unused audio: E-DrumLP if jam elsewhere
    # Actually put bass into stretch companion - use track E-Mental if free
    # Keep bass in mix only if no audio track; try E-DrumLP for jam mix

    track_map = {
        "E-Kick": kick_idx, "E-Hats": hats_idx, "E-OHat": oh_idx, "E-Perc": perc_idx,
        "Acid 303": acid_idx, "ESX Stretch": stretch_idx, "ESX VoxAud": vox_idx,
        "JamMix": jam_idx, "RingMod": rm_idx,
    }
    print("TRACK_MAP", track_map)

    idxs = [i for i in (kick_idx, hats_idx, oh_idx, perc_idx, acid_idx, stretch_idx, vox_idx, jam_idx, rm_idx) if i is not None]
    for row, _, _, _ in ABLETON_SCENES:
        for idx in idxs:
            safe_delete(idx, row)

    loaded = []
    for sid, sname, mode, bars in ABLETON_SCENES:
        paths = scene_paths[sid]
        pairs = [
            (kick_idx, "kick", f"{sname}_kick"),
            (hats_idx, "hats", f"{sname}_hats"),
            (oh_idx, "oh", f"{sname}_oh"),
            (perc_idx, "perc", f"{sname}_perc"),
            (stretch_idx, "stretch", f"{sname}_stretch"),
            (acid_idx, "acid", f"{sname}_acid"),
            (rm_idx, "ringmod", f"{sname}_ringmod"),
            (vox_idx, "vox", f"{sname}_vox"),
            (jam_idx, "mix", f"{sname}_MIX"),
        ]
        for tidx, key, cname in pairs:
            if tidx is None:
                continue
            p = paths.get(key)
            if p is None or not p.exists():
                continue
            if key != "mix" and not morph.layer_has_signal(p):
                continue
            # fail-fast: one short attempt; hangs go to continue loader
            ok_clip = load_audio(tidx, sid, p, cname, timeout=22.0)
            if ok_clip:
                loaded.append(cname)
                ableton_load._fails = 0
            else:
                print("DEFER clip (use load_mentalclean_morph_continue_v2.py):", cname)
                ableton_load._fails = getattr(ableton_load, "_fails", 0) + 1
                if ableton_load._fails >= 2:
                    print("ABLETON fail-fast after 2 clip timeouts — use continue loader")
                    return {
                        "ok": False,
                        "error": "create_audio_clip hang/fail — use continue loader",
                        "track_map": track_map,
                        "loaded": loaded,
                        "fired": [],
                        "scenes": [n for _, n, _, _ in ABLETON_SCENES],
                    }
        # locator for chapter
        send("create_locator", {"name": f"{sid}_{sname}", "time": float(sid * bars * 4)})

    # Fire Drop_1 stems (not jam double)
    print("=== Fire Drop_1 row", FIRE_ROW, "===")
    fired = []
    for label, tidx, key in [
        ("kick", kick_idx, "kick"),
        ("hats", hats_idx, "hats"),
        ("oh", oh_idx, "oh"),
        ("perc", perc_idx, "perc"),
        ("stretch", stretch_idx, "stretch"),
        ("acid", acid_idx, "acid"),
        ("ringmod", rm_idx, "ringmod"),
        ("vox", vox_idx, "vox"),
    ]:
        if tidx is None:
            continue
        p = scene_paths[FIRE_ROW].get(key)
        if p is None or not morph.layer_has_signal(p):
            continue
        r = send("fire_clip", {"track_index": tidx, "clip_index": FIRE_ROW})
        if r.get("status") == "success":
            fired.append(label)
            print("FIRE", label)
    ok(send("start_playback"), "start_playback")
    info = send("get_session_info")
    res = info.get("result") or info
    return {
        "ok": True,
        "track_map": track_map,
        "loaded": loaded,
        "fired": fired,
        "tempo": res.get("tempo"),
        "is_playing": res.get("is_playing"),
        "scenes": [n for _, n, _, _ in ABLETON_SCENES],
    }


def main():
    errors = []
    print("=== MentalClean Molecular MORPH @", BPM, "v2 (RingMod + choke) ===")
    shots = ensure_oneshots()
    phrases, packs, used_vox = ensure_vox_phrases()
    if not phrases:
        raise RuntimeError("no Voice ROM chops — cannot build Predrop_Vox")

    # 1) Full Mix Learner MP3 timeline
    print("=== Render FULL sections for MP3 ===")
    full_mixes = []
    full_meta = []
    t0 = 0.0
    for idx, (name, bars, mode) in enumerate(FULL_SECTIONS):
        pref = SECTION_MIX_DIR / f"full_{idx:02d}_{name}"
        paths, meta = render_section(idx, name, bars, mode, shots, phrases, packs, pref)
        full_mixes.append(paths["mix"])
        meta["start_s"] = round(t0, 2)
        meta["end_s"] = round(t0 + bars * BAR_S, 2)
        t0 = meta["end_s"]
        full_meta.append(meta)

    print("=== Bounce MP3 (CRISP acoustic) ===")
    try:
        dur = bounce_mp3(full_mixes, MP3)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        dur = 0.0

    # 2) Ableton 8-scene shorter clips
    print("=== Render Ableton 8-scene clips ===")
    ab_paths = {}
    ab_meta = []
    for sid, sname, mode, bars in ABLETON_SCENES:
        pref = CLIP_DIR / f"ab_{sid:02d}_{sname}"
        paths, meta = render_section(100 + sid, sname, bars, mode, shots, phrases, packs, pref)
        ab_paths[sid] = paths
        ab_meta.append(meta)

    skip_ab = "--skip-ableton" in sys.argv
    print("=== Ableton load ===", "SKIP" if skip_ab else "")
    ab_result = {"ok": False}
    if skip_ab:
        print("SKIP Ableton (use load_mentalclean_morph_continue_v2.py)")
        ab_result = {"ok": False, "error": "skipped — use continue loader"}
    else:
        try:
            ab_result = ableton_load(ab_paths, ab_meta)
        except Exception as e:
            errors.append(f"ableton: {e}")
            print("FAIL ableton", e)

    # LUFS of bounced v2 (do not overwrite v1)
    lufs = {"I": None, "TP": None, "LRA": None}
    if MP3.exists():
        try:
            lufs = measure_lufs(MP3)
        except Exception as e:
            errors.append(f"lufs: {e}")
            print("FAIL lufs", e)

    # notes
    lines = [
        "# EvAIx MentalClean Molecular MORPH @162 v2",
        f"MP3: `{MP3}`",
        f"Duration: {dur:.2f}s · BPM {BPM}",
        f"Ableton: tempo={ab_result.get('tempo')} playing={ab_result.get('is_playing')}",
        f"Fired: {ab_result.get('fired')}",
        f"Track map: {ab_result.get('track_map')}",
        f"Scenes: {ab_result.get('scenes')}",
        f"Drums/samples: {shots['used'][:30]}...",
        f"Vox chops: {len(used_vox)}",
        "",
        "## Ring Mod params (EMX RING MOD lead/acid)",
        f"- OSC1/OSC2: `{RM_WAVE1}` + `{RM_WAVE2}`",
        f"- Mod Depth (OSC EDIT1): {RM_MOD_DEPTH} (~{int(RM_MOD_DEPTH*127)}/127) — blend OSC1 vs ring product",
        f"- Detune: {RM_DETUNE_CENTS} cents on OSC2",
        f"- Mod Pitch (OSC EDIT2): {RM_MOD_PITCH} (range -63..+63; ±63 = ±2 oct)",
        f"- Mod→Pitch: {RM_MOD_TO_PITCH}  speed={RM_MOD_SPEED_HZ} Hz  depth=±{RM_MOD_PITCH_DEPTH}",
        f"- Voice gain RM_G={RM_G} (acid ACID_G={ACID_G}); HPF {RM_HPF_HZ} Hz / LPF {RM_LPF_HZ} Hz",
        "- Cycle inverted vs poly-303 (15↔13) so the two voices weave; kick-duck on drops",
        "",
        "## Hat choke (EMX 6A/6B · 7A/7B)",
        f"- Group 6: 6A=closed (kit hat_c) / 6B=open (kit hat_o); fade {CHOKE_FADE_MS} ms then zero tail",
        "- Group 7: 7A=alt-closed / 7B=alt-open (ghosts, climax extras, mute-game leftovers)",
        "- Exclusive within each pair: A and B cannot overlap. Simultaneous → B wins (manual).",
        "- Closed on the same 16th as open is dropped — no muddy CH+OH stack.",
        "",
        "## Loudness (measured ebur128)",
        f"- I={lufs.get('I')} LUFS  TP={lufs.get('TP')} dB  LRA={lufs.get('LRA')} LU",
        "- Target club loudnorm ~I=-8.5 to -9.5, TP=-1 (AF chain loudnorm I=-8.5 TP=-1.0 LRA=11)",
        "",
        "## Full section map (MP3)",
    ]
    for m in full_meta:
        lines.append(
            f"- {m['start_s']:.1f}–{m['end_s']:.1f}s {m['name']}: {m['story']} "
            f"[hat={m['hat']} rim={m['rim']} perc={m['perc']} polyLS={m.get('acid_cycle')} "
            f"rmLS={m.get('rm_cycle')} vox_g={m['gains']['vox']:.2f} rm_g={m['gains'].get('ringmod', 0):.2f}]"
        )
    lines.extend(["", "## Ableton scenes (8 rows)", ""])
    for sid, sname, mode, bars in ABLETON_SCENES:
        m = ab_meta[sid]
        lines.append(f"- row {sid} **{sname}** ({bars} bars): {m['story']}")
    lines.extend(["", f"AF: `{AF_CHAIN}`", f"Errors: {errors or 'none'}", ""])
    NOTES.write_text("\n".join(lines), encoding="utf-8")
    print("NOTES", NOTES)
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(dur, 2))
    print("LUFS_I", lufs.get("I"), "LUFS_TP", lufs.get("TP"), "LUFS_LRA", lufs.get("LRA"))
    print("ABLETON_OK", ab_result.get("ok"))
    print("SCENES", ab_result.get("scenes"))
    print("TRACK_MAP", ab_result.get("track_map"))
    print("FIRED", ab_result.get("fired"))
    print("ERRORS", errors)
    print("DONE build_mentalclean_molecular_morph_162_v2")


if __name__ == "__main__":
    main()
