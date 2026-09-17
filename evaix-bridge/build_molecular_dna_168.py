# -*- coding: utf-8 -*-
"""EvAIx Molecular DNA stem-render @168 — Mix Learner blueprint.

Authority: pneumatix-molecular-modulation.blueprint.json
- BPM 168, bar≈1.4286s, full ~450s / 315 bars
- Sections: intro→predrop→drop_1→break_1→build→drop_2→groove→break_2→drop_3→outro
- Bass ~8dB under kick; drops kick-first; strip kick in breaks; hats/air last
- Pozek: mid flange 800–4500 only (not arrangement)

Output: C:\\Users\\Gebruiker\\Downloads\\EvAIx_MolecularDNA_168.mp3
"""
from __future__ import annotations

import array
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

BRIDGE = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge")
sys.path.insert(0, str(BRIDGE))
import crisp_dna_to_ableton as dna  # noqa: E402
import build_classic_acid_liveset as classic  # noqa: E402

_FF_FULL = r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
if Path(_FF_FULL).exists():
    dna.FFMPEG = _FF_FULL

SR = dna.SR
BPM = 168.0
BAR_S = 4.0 * 60.0 / BPM  # 1.428571...
HOST, PORT = "127.0.0.1", 9877

FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT = BRIDGE / "samples" / "crisp-dna" / "esx1-molecular-dna-168"
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"
ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_MolecularDNA_168.mp3")
NOTES = OUT / "molecular_dna_168_notes.md"

# Mix Learner section map (bars)
SECTIONS = [
    # name, bars, mode
    ("intro", 24, "intro"),
    ("predrop_vocal", 24, "predrop"),
    ("drop_1", 32, "drop"),
    ("break_1", 16, "break"),
    ("build", 24, "build"),
    ("drop_2_climax", 56, "drop_climax"),
    ("groove_sparse", 16, "groove"),
    ("break_2", 16, "break"),
    ("drop_3", 80, "drop"),
    ("outro", 27, "outro"),
]

TUBE_GAIN = 2.05
DELAY_TIME_BEATS = 0.375
DELAY_WET = 0.07
DELAY_FB = 0.18
SWING_PCT = 0.54
SWING_DELAY = (SWING_PCT - 0.5) / ((2.0 / 3.0) - 0.5) * (0.25 / 3.0)

# Absolute stem gains (drop peak) — bass relative −8 dB ≈ *0.4
KICK_G = 1.58
BASS_G = KICK_G * (10 ** (-8.0 / 20.0))  # ≈0.629
HATS_G = 0.16
OH_G = 0.12
PERC_G = 0.18
ACID_G = 0.22
STRETCH_G = 0.28
VOX_G = 0.28  # ≥8 dB under kick bus at drop

# PA / Mix Learner loudness target
AF_CHAIN = (
    "highpass=f=28:poles=2,"
    "lowshelf=f=85:t=q:w=0.7:g=1.6,"
    "equalizer=f=52:t=q:w=1.0:g=3.6,"
    "equalizer=f=75:t=q:w=1.3:g=-2.0,"
    "equalizer=f=180:t=q:w=1.0:g=-1.4,"
    "equalizer=f=380:t=q:w=1.0:g=-1.5,"
    "equalizer=f=1200:t=q:w=1.0:g=0.6,"
    "equalizer=f=2800:t=q:w=1.4:g=1.4,"
    "equalizer=f=4500:t=q:w=1.2:g=0.8,"
    "equalizer=f=7000:t=q:w=1.1:g=-1.6,"
    "equalizer=f=11000:t=q:w=1.0:g=-3.2,"
    "highshelf=f=8000:t=q:w=0.7:g=-3.0,"
    "lowpass=f=14500:poles=1,"
    "acompressor=threshold=-17dB:ratio=1.5:attack=10:release=160:makeup=1.15,"
    "alimiter=limit=0.90,"
    "loudnorm=I=-7.0:TP=-1.0:LRA=13"
)

classic.RES_Q = 0.11
classic.BASE_CUT0 = 220.0
classic.ENV_AMT = 1500.0
classic.ROLL_MAX = 70.0
classic.GRIT = 1.5
classic.ENV_DECAY = 0.9974
classic.OSC_KIND = "saw"
classic.OUT = OUT
classic.SECTION_MIX_DIR = SECTION_MIX_DIR
classic.BPM = BPM


def section_n(bars: int) -> int:
    return int(bars * 4.0 * 60.0 / BPM * SR)


def swing_offset(st: int) -> float:
    return SWING_DELAY if (st % 2 == 1) else 0.0


def place(buf, sample, beat, gain=1.0):
    dna.place(buf, sample, beat, gain)


def read_wav(path: Path) -> list[float]:
    return dna.read_wav(path)


def write_mono(path: Path, samples, peak_target=0.90):
    peak = max(1e-9, max((abs(x) for x in samples), default=1e-9))
    scale = peak_target / peak
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
    bias = 0.035
    norm = math.tanh(tube_gain)
    out = [0.0] * len(samples)
    for i, x in enumerate(samples):
        driven = (x + bias) * tube_gain
        y = math.tanh(driven) / norm - bias * 0.5
        y = 0.88 * y + 0.12 * math.tanh(x * (tube_gain * 0.55))
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
    """Short sub pulse ~52 Hz — sits under kick by gain bus, not muddy 70–120."""
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
    """Strong HF transient for Molecular kick click (Somatic missed this)."""
    n = int(0.022 * SR)
    out = [0.0] * n
    rng = dna.mulberry32(0xC11C)
    for i in range(n):
        t = i / SR
        env = math.exp(-t / 0.0032)
        nse = (rng() * 2 - 1) * env
        # add short pitched tick ~2.8k
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
    rb_in = ONESHOT / "stretch_rb_in.wav"
    rb_out = ONESHOT / "stretch_rb_out.wav"
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
    mapping = {
        "146_SinKick.wav": "esx_SinKick.wav",
        "054_HH-1C.wav": "esx_HH1C.wav",
        "055_HH-1O.wav": "esx_HH1O.wav",
        "045_Rim-1.wav": "esx_Rim1.wav",
        "021_SD-1.wav": "esx_SD1.wav",
        "092_JunkPerc.wav": "esx_JunkPerc.wav",
    }
    used = []
    shots = {}
    for src_name, dst_name in mapping.items():
        src = FACTORY / src_name
        dst = ONESHOT / dst_name
        if not src.exists():
            print("MISSING", src_name)
            continue
        electribe_master(src, dst)
        used.append(src_name)
        shots[dst_name] = read_wav(dst)

    # Kick: blend sledge (clicky free-party) with SinKick body weight
    sledge = dna.synth_kick_sledge(dna.mulberry32(0xE51), "full")
    sledge = [dna.tanh_drive(x, 2.0) for x in sledge]
    sledge = mild_compress_kick(sledge)
    sink = shots.get("esx_SinKick.wav")
    if sink:
        # align lengths
        n = max(len(sledge), len(sink))
        sledge = sledge + [0.0] * (n - len(sledge))
        sink = sink + [0.0] * (n - len(sink))
        body = one_pole(sink, 140.0, mode="lpf")
        kick = [0.55 * sledge[i] + 0.55 * body[i] for i in range(n)]
    else:
        kick = sledge
        body = one_pole(kick, 140.0, mode="lpf")
        kick = [0.7 * kick[i] + 0.4 * body[i] for i in range(len(kick))]
    kick = mild_compress_kick(kick)
    kick_veiled = one_pole(kick, 90.0, mode="lpf")
    kick_veiled = [x * 0.75 for x in kick_veiled]

    click = synth_hard_click()
    bass = synth_bass_pulse()

    hat_c = shots.get("esx_HH1C.wav") or dna.synth_hat(dna.mulberry32(1), False)
    hat_c = one_pole([dna.tanh_drive(x, 1.0) for x in hat_c], 6800.0, mode="lpf")
    hat_o = shots.get("esx_HH1O.wav") or dna.synth_hat(dna.mulberry32(2), True)
    hat_o = one_pole([dna.tanh_drive(x, 1.0) for x in hat_o], 6500.0, mode="lpf")
    rim = shots.get("esx_Rim1.wav")
    junk = shots.get("esx_JunkPerc.wav")
    if junk:
        junk = one_pole([dna.tanh_drive(x, 1.1) for x in junk], 4000.0, mode="lpf")

    stretch_src = "189_SynLP-1.wav" if (FACTORY / "189_SynLP-1.wav").exists() else "175_PercLP-1.wav"
    stretch = make_stretch_loop(stretch_src, bars=2)
    used.append(f"STRETCH:{stretch_src}")
    used.append("synth_sledge+SinKick+hard_click+bass52")

    write_mono(ONESHOT / "kick_ready.wav", kick, 0.94)
    write_mono(ONESHOT / "bass_ready.wav", bass, 0.88)
    write_mono(ONESHOT / "click_ready.wav", click, 0.85)
    return {
        "kick": kick,
        "kick_veiled": kick_veiled,
        "click": click,
        "bass": bass,
        "hat_c": hat_c,
        "hat_o": hat_o,
        "rim": rim,
        "junk": junk,
        "stretch": stretch,
        "used": used,
    }


def ensure_vox_phrases():
    """Pozek mid flange tone 800–4500 — organic chops, not Pozek form."""
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
        for dur_s, tag in ((0.10, "short"), (0.16, "mid"), (0.26, "long")):
            start = max(0, peak_i - int(0.012 * SR))
            end = min(len(raw), start + int(dur_s * SR))
            chop = raw[start:end]
            if max(abs(x) for x in chop) < 1e-4:
                continue
            # Pozek band wider 800–4500
            chop = bandpass(chop, 800.0, 4500.0)
            chop = soft_gate(chop, 0.012)
            chop = [math.tanh(x * 1.5) for x in chop]
            rate = 0.85 + 0.45 * rng()
            chop = flanger(
                chop, rate_hz=rate, depth_ms=3.8 + 2.0 * rng(),
                base_ms=2.0, feedback=0.22, mix=0.48 + 0.1 * rng(),
            )
            chop = chorus(chop, rate_hz=0.4 + 0.3 * rng(), mix=0.32 + 0.1 * rng())
            chop = bandpass(chop, 800.0, 4500.0)
            pk = max((abs(x) for x in chop), default=0.0)
            if pk > 0.95:
                chop = [x * (0.85 / pk) for x in chop]
            phrases.append(chop)
            used.append(f"{src_name}:{tag}")
    packs = []
    if phrases:
        for pi in range(6):
            pack = [0.0] * int(0.5 * SR)
            hits = 2 + int(rng() * 3)
            for h in range(hits):
                shot = phrases[int(rng() * len(phrases)) % len(phrases)]
                place(pack, shot, h * (0.14 + 0.05 * rng()) * (BPM / 60.0), 0.7 + 0.25 * rng())
            pack = mono_delay(pack, time_beats=0.375, wet=0.14, fb=0.18)
            pack = bandpass(pack, 800.0, 4500.0)
            packs.append(pack)
    print("VOX", len(phrases), "packs", len(packs))
    return phrases, packs, used


def mode_gains(mode: str):
    """Relative multipliers per Mix Learner density / air rules."""
    # kick, bass, hats, oh, perc, stretch, acid, vox, click, valve, air_send
    table = {
        "intro": dict(kick=0.0, bass=0.15, hats=0.0, oh=0.0, perc=0.0, stretch=0.35, acid=0.08, vox=0.55, click=0.0, valve=0.55, air=0.05),
        "predrop": dict(kick=0.12, bass=0.35, hats=0.15, oh=0.0, perc=0.05, stretch=0.45, acid=0.15, vox=0.95, click=0.0, valve=0.7, air=0.15),
        "drop": dict(kick=1.0, bass=1.0, hats=0.85, oh=0.7, perc=0.55, stretch=0.4, acid=0.55, vox=0.55, click=1.0, valve=1.0, air=0.85),
        "drop_climax": dict(kick=1.05, bass=1.0, hats=0.9, oh=0.75, perc=0.6, stretch=0.45, acid=0.7, vox=0.6, click=1.1, valve=1.05, air=0.95),
        "break": dict(kick=0.08, bass=0.4, hats=0.1, oh=0.0, perc=0.0, stretch=0.55, acid=0.2, vox=0.7, click=0.0, valve=0.6, air=0.1),
        "build": dict(kick=0.35, bass=0.55, hats=0.4, oh=0.25, perc=0.25, stretch=0.5, acid=0.45, vox=0.85, click=0.25, valve=0.85, air=0.35),
        "groove": dict(kick=0.55, bass=0.7, hats=0.35, oh=0.15, perc=0.2, stretch=0.4, acid=0.25, vox=0.4, click=0.4, valve=0.75, air=0.2),
        "outro": dict(kick=0.75, bass=0.55, hats=0.25, oh=0.0, perc=0.1, stretch=0.25, acid=0.1, vox=0.2, click=0.35, valve=0.65, air=0.1),
    }
    return table[mode]


def render_section(idx: int, name: str, bars: int, mode: str, shots, pattern, phrases, packs):
    N = section_n(bars)
    # sync classic module length for acid
    classic.BPM = BPM
    classic.BARS = bars
    classic.BEATS = bars * 4
    classic.N = N
    dna.BPM = BPM
    dna.BARS = bars
    dna.BEATS = bars * 4
    dna.N = N

    kick = shots["kick"]
    kick_veiled = shots["kick_veiled"]
    click = shots["click"]
    bass = shots["bass"]
    hat_c = shots["hat_c"]
    hat_o = shots["hat_o"]
    rim = shots["rim"]
    junk = shots["junk"]
    stretch_one = shots["stretch"]

    trk_k = [0.0] * N
    trk_b = [0.0] * N
    trk_h = [0.0] * N
    trk_oh = [0.0] * N
    trk_p = [0.0] * N
    trk_st = [0.0] * N
    trk_v = [0.0] * N

    mg = mode_gains(mode)
    rng = dna.mulberry32(0x1680 + idx * 97)

    for bar in range(bars):
        base = bar * 4.0

        # --- DROP ENTRY RULE: kick 1–2 bars alone-ish, then bass, then mid, then vox ---
        drop_entry = mode in ("drop", "drop_climax") and bar < 2
        mid_ok = not (mode in ("drop", "drop_climax") and bar < 2)
        vox_ok = not (mode in ("drop", "drop_climax") and bar < 4)
        bass_ok = not (mode in ("drop", "drop_climax") and bar < 1)

        # KICK
        if mode in ("intro",):
            # sparse absent — maybe 1 ghost every 4 bars
            if bar % 4 == 3:
                place(trk_k, kick_veiled, base + 0.0, 0.35)
        elif mode == "predrop":
            if bar % 2 == 1:
                for step in (0, 8):
                    place(trk_k, kick_veiled, base + step * 0.25, 0.4)
        elif mode == "break":
            # ~strip kick — occasional filtered hit
            if bar % 4 == 2:
                place(trk_k, kick_veiled, base, 0.3)
        elif mode == "build":
            # rising kick presence late in build
            dens = 0.25 + 0.75 * (bar / max(1, bars - 1))
            if dens < 0.45:
                if bar % 2 == 0:
                    place(trk_k, kick_veiled, base, 0.5 * dens)
            else:
                for qi, step in enumerate((0, 4, 8, 12)):
                    g = (0.7 if qi in (0, 3) else 0.6) * dens
                    place(trk_k, kick if dens > 0.7 else kick_veiled, base + step * 0.25, g)
                    if dens > 0.75:
                        place(trk_k, click, base + step * 0.25, 0.25 * dens)
        elif mode in ("drop", "drop_climax", "groove", "outro"):
            fade = 1.0
            if mode == "outro":
                fade = max(0.12, 1.0 - (bar / max(1, bars)) * 0.95)
            for qi, step in enumerate((0, 4, 8, 12)):
                g = (1.12 if qi in (0, 3) else 1.0) * fade
                if mode == "groove":
                    g *= 0.85
                place(trk_k, kick, base + step * 0.25, g)
                place(trk_k, click, base + step * 0.25, (0.42 if mode == "drop_climax" else 0.35) * fade)

        # BASS under kick (~8 dB via bus gain); only with kick lock / after entry bar
        if bass_ok and mode in ("drop", "drop_climax", "groove", "outro", "build", "predrop"):
            steps = (0, 4, 8, 12) if mode in ("drop", "drop_climax", "groove", "outro") else ((0, 8) if mode == "build" else (0,))
            for step in steps:
                if mode == "predrop" and bar % 2 == 0:
                    continue
                place(trk_b, bass, base + step * 0.25, 0.9 if mode.startswith("drop") else 0.65)

        # HATS / AIR last — only when kick full
        if mg["air"] >= 0.5 and mode in ("drop", "drop_climax") and mid_ok:
            for st in (2, 6, 10, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.48)
            if bar % 2 == 1:
                place(trk_oh, hat_o, base + 14 * 0.25 + swing_offset(14), 0.28)
            # sparse 16ths — NOT busy grid
            if mode == "drop_climax" and bar % 4 == 0:
                for st in (3, 11):
                    place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.18)
        elif mode == "build" and bar > bars // 2:
            for st in (6, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.35)
        elif mode == "groove":
            for st in (6, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.32)
        elif mode == "predrop" and bar > 8:
            place(trk_h, hat_c, base + 14 * 0.25 + swing_offset(14), 0.25)

        # PERC minimal
        if mid_ok and mode in ("drop", "drop_climax", "build", "groove") and rim is not None:
            place(trk_p, rim, base + 1.0, 0.28)
            if mode == "drop_climax" and bar % 2 == 1:
                place(trk_p, rim, base + 3.0, 0.22)
        if mode == "drop_climax" and junk is not None and bar % 8 == 4 and mid_ok:
            place(trk_p, junk, base + 2.75 + swing_offset(11), 0.1)

        # STRETCH / body bed — sectional, not continuous wall
        if mode in ("intro", "predrop", "break"):
            if bar % 2 == 0:
                place(trk_st, stretch_one, base, 0.45 if mode != "break" else 0.55)
        elif mode == "build":
            place(trk_st, stretch_one, base, 0.35 + 0.25 * (bar / max(1, bars - 1)))
        elif mid_ok and mode in ("drop", "drop_climax", "groove") and bar % 2 == 0:
            place(trk_st, stretch_one, base, 0.28 if mode != "drop_climax" else 0.32)
        elif mode == "outro" and bar < bars * 0.6 and bar % 2 == 0:
            place(trk_st, stretch_one, base, 0.22)

        # VOX shouts — predrop + drops after entry; carve off kick downbeats
        if phrases and (
            (mode == "predrop")
            or (mode in ("drop", "drop_climax") and vox_ok)
            or (mode == "break")
            or (mode == "build" and bar > 4)
        ):
            # shout packs every 2–4 bars on offbeats
            period = 2 if mode in ("drop_climax", "predrop") else 3
            if packs and bar % period == 0:
                pack = packs[int(rng() * len(packs)) % len(packs)]
                start_beat = 1.5 if mode.startswith("drop") else 2.0
                g = 0.65 if mode == "predrop" else 0.5
                place(trk_v, pack, base + start_beat, g)
            # sparse single chops
            if mode in ("drop", "drop_climax") and bar % 2 == 1:
                shot = phrases[int(rng() * len(phrases)) % len(phrases)]
                place(trk_v, shot, base + 2.5 + swing_offset(10), 0.4)
            elif mode == "break" and bar % 2 == 0:
                shot = phrases[int(rng() * len(phrases)) % len(phrases)]
                place(trk_v, shot, base + 1.0, 0.55)
            elif mode == "predrop":
                if bar % 2 == 0:
                    shot = phrases[int(rng() * len(phrases)) % len(phrases)]
                    place(trk_v, shot, base + 1.5, 0.6)

    # Acid: carved, sectional — never continuous mid wall
    acid_drive = {
        "intro": 0.08, "predrop": 0.18, "break": 0.22, "build": 0.55,
        "drop": 0.45, "drop_climax": 0.65, "groove": 0.25, "outro": 0.1,
    }.get(mode, 0.2)
    acid_full = classic.render_classic_acid(pattern, grit=classic.GRIT, roll=True)
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))
    # carve: duck acid on kick frames for drop modes
    if mode in ("drop", "drop_climax") and acid_drive > 0:
        acid = one_pole(acid, 1400.0, mode="lpf")
        beat_n = int(60.0 / BPM * SR)
        for b in range(bars * 4):
            i0 = b * beat_n
            # 40ms dip on each beat
            for j in range(min(int(0.04 * SR), N - i0)):
                acid[i0 + j] *= 0.35
    elif acid_drive > 0:
        acid = one_pole(acid, 1500.0, mode="lpf")

    # Vox processing — Pozek band
    if any(abs(x) > 1e-6 for x in trk_v):
        trk_v = flanger(trk_v, rate_hz=0.95, depth_ms=4.0, base_ms=2.2, feedback=0.2, mix=0.4)
        trk_v = mono_delay(trk_v, time_beats=0.375, wet=0.12, fb=0.16)
        trk_v = bandpass(trk_v, 800.0, 4500.0)
        trk_v = soft_gate(trk_v, 0.008)

    g_kick = KICK_G * mg["kick"]
    g_bass = BASS_G * mg["bass"]
    g_hats = HATS_G * mg["hats"]
    g_oh = OH_G * mg["oh"]
    g_perc = PERC_G * mg["perc"]
    g_st = STRETCH_G * mg["stretch"]
    g_acid = ACID_G * mg["acid"]
    g_vox = VOX_G * mg["vox"]
    tube = TUBE_GAIN * mg["valve"]

    dry = [0.0] * N
    for i in range(N):
        dry[i] = (
            trk_k[i] * g_kick
            + trk_b[i] * g_bass
            + acid[i] * g_acid
            + trk_h[i] * g_hats
            + trk_oh[i] * g_oh
            + trk_p[i] * g_perc
            + trk_st[i] * g_st
            + trk_v[i] * g_vox
        )
    send_src = [0.0] * N
    air = mg["air"]
    for i in range(N):
        send_src[i] = (
            acid[i] * g_acid * 0.35 * air
            + trk_h[i] * g_hats * 0.55 * air
            + trk_oh[i] * g_oh * 0.35 * air
            + trk_v[i] * g_vox * 0.55
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

    mix_path = SECTION_MIX_DIR / f"s{idx:02d}_{name}_mix.wav"
    write_stereo_lr(mix_path, left, right, 0.90)
    print(
        f"section {idx} {name} bars={bars} mode={mode} "
        f"gains k={g_kick:.2f} b={g_bass:.2f} h={g_hats:.2f} v={g_vox:.2f} "
        f"valve={tube:.2f} peak={peak:.3f}"
    )
    return mix_path, {
        "kick": g_kick, "bass": g_bass, "hats": g_hats, "oh": g_oh,
        "perc": g_perc, "stretch": g_st, "acid": g_acid, "vox": g_vox,
        "valve": tube, "mode": mode, "bars": bars,
    }


def bounce_mp3(mix_paths, mp3_path: Path) -> float:
    listfile = OUT / "_concat_mol.txt"
    raw_concat = OUT / "_concat_mol.wav"
    mastered = OUT / "_master_mol.wav"
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
        raise RuntimeError("PA master failed")
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
        dur = sum(bars for _, bars, _ in SECTIONS) * BAR_S
    print("MP3", mp3_path, "dur", round(dur, 2))
    return dur


def main():
    print("=== Molecular DNA Mix Learner bounce @", BPM, "===")
    print("bar_s", round(BAR_S, 4), "bass_under_kick_db 8.0", "BASS_G", round(BASS_G, 3))
    shots = ensure_oneshots()
    phrases, packs, used_vox = ensure_vox_phrases()
    pattern = classic.classic_pattern(dna.SEED + 303)

    mix_paths = []
    logs = []
    for idx, (name, bars, mode) in enumerate(SECTIONS):
        path, g = render_section(idx, name, bars, mode, shots, pattern, phrases, packs)
        mix_paths.append(path)
        logs.append((name, g))

    print("=== Bounce MP3 ===")
    dur = bounce_mp3(mix_paths, MP3)

    lines = [
        "# EvAIx Molecular DNA @168 — Mix Learner bounce",
        f"Output: `{MP3}`",
        f"Duration: {dur:.2f}s · BPM {BPM} · bar {BAR_S:.4f}s",
        f"Bass under kick: 8 dB (BASS_G={BASS_G:.3f})",
        f"Drums: {shots['used']}",
        f"Vox phrases: {len(used_vox)}",
        "",
        "## Sections",
    ]
    for name, g in logs:
        lines.append(
            f"- {name}: bars={g['bars']} mode={g['mode']} "
            f"kick={g['kick']:.2f} bass={g['bass']:.2f} hats={g['hats']:.2f} "
            f"vox={g['vox']:.2f} acid={g['acid']:.2f} valve={g['valve']:.2f}"
        )
    lines.extend(["", f"AF: `{AF_CHAIN}`", ""])
    NOTES.write_text("\n".join(lines), encoding="utf-8")
    print("NOTES", NOTES)
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(dur, 2))
    print("DONE build_molecular_dna_168")


if __name__ == "__main__":
    main()
