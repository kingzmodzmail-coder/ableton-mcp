# -*- coding: utf-8 -*-
"""Somatic Resonance Engineer — full physiological test @162.

Blueprint: /workspace/somatic_test_blueprint_162.md
Mission: controlled neural discharge on 18\" PA — anticipation → visceral release → afterglow.
Adapt of build_esx1_pnx_pozek_real_162.py; stem-render ffmpeg path primary.

Output: C:\\Users\\Gebruiker\\Downloads\\EvAIx_SomaticTest_PA_162.mp3
"""
from __future__ import annotations

import array
import json
import math
import socket
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
BPM = 162.0
BARS = 24
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR)
HOST, PORT = "127.0.0.1", 9877

FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT = BRIDGE / "samples" / "crisp-dna" / "esx1-somatic-test"
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"
ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_SomaticTest_PA_162.mp3")
NOTES = OUT / "somatic_test_notes.md"
REPORT = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_SomaticTest_PA_162_REPORT.md")

# Blueprint scenes (8 × ~24 bars) — body state arc
SCENES = [
    (0, "Intro_Anticipation"),
    (1, "Hats_Desire"),
    (2, "Kick_Lock"),
    (3, "Vox_Whisper"),
    (4, "Release_Visceral"),
    (5, "Afterglow_Roll"),
    (6, "Mute_Games"),
    (7, "Outro_BodyFade"),
]

TUBE_GAIN = 2.1  # Valve ~2.1 per calibration
DELAY_TIME_BEATS = 0.375
DELAY_WET = 0.08
DELAY_FB = 0.20
SWING_PCT = 0.56
SWING_DELAY = (SWING_PCT - 0.5) / ((2.0 / 3.0) - 0.5) * (0.25 / 3.0)

# Stem gains (blueprint start points) — kick owns ribcage; tops quiet
KICK_G = 1.50
KICK_VEILED_G = 0.72   # filtered ghost anticipation
KICK_SOFT_G = 1.05     # Kick_Lock soft fund entry
KICK_RELEASE_G = 1.55  # Release_Visceral clamp
HATS_G = 0.22          # ≤0.25
OH_G = 0.18            # ≤0.22
PERC_G = 0.42          # ≤0.5
ACID_SCALE = 0.40      # dark/late
STRETCH_SCALE = 0.35   # subtle
VOX_G = 0.32           # ≤0.35 under kick

# PA master — mono-safe lows, kick +52/+3.2k, top cuts, lim 0.89, loudnorm
AF_CHAIN = (
    "highpass=f=26:poles=2,"
    "lowshelf=f=90:t=q:w=0.7:g=2.0,"
    "equalizer=f=52:t=q:w=1.1:g=3.2,"
    "equalizer=f=72:t=q:w=1.4:g=-1.3,"
    "equalizer=f=380:t=q:w=1.0:g=-1.2,"
    "equalizer=f=1400:t=q:w=1.0:g=0.9,"
    "equalizer=f=3200:t=q:w=1.6:g=1.7,"
    "equalizer=f=6500:t=q:w=1.2:g=-0.8,"
    "equalizer=f=10000:t=q:w=1.1:g=-2.8,"
    "highshelf=f=7000:t=q:w=0.7:g=-3.6,"
    "lowpass=f=15000:poles=1,"
    "acompressor=threshold=-18dB:ratio=1.6:attack=12:release=180:makeup=1.2,"
    "alimiter=limit=0.89,"
    "loudnorm=I=-8.5:TP=-1.0:LRA=7"
)

for mod in (dna, classic):
    mod.BPM = BPM
    mod.BARS = BARS
    mod.BEATS = BEATS
    mod.N = N
classic.RES_Q = 0.12
classic.BASE_CUT0 = 240.0
classic.ENV_AMT = 1400.0
classic.ROLL_MAX = 80.0
classic.GRIT = 1.45
classic.ENV_DECAY = 0.9972
classic.OSC_KIND = "saw"
classic.OUT = OUT
classic.SECTION_MIX_DIR = SECTION_MIX_DIR


def send(cmd, params=None, timeout=25.0):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=3) as sock:
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
    if not r or r.get("status") != "success":
        print("FAIL", label, (r or {}).get("message", r))
        return None
    print("OK", label)
    return r.get("result", r)


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


def swing_offset(st: int) -> float:
    return SWING_DELAY if (st % 2 == 1) else 0.0


def valve_force(samples: list[float], tube_gain: float = TUBE_GAIN) -> list[float]:
    bias = 0.04
    norm = math.tanh(tube_gain)
    out = [0.0] * len(samples)
    for i, x in enumerate(samples):
        driven = (x + bias) * tube_gain
        y = math.tanh(driven) / norm - bias * 0.55
        y = 0.9 * y + 0.1 * math.tanh(x * (tube_gain * 0.6))
        out[i] = y
    return out


def mild_compress_kick(samples: list[float], thr=0.40, ratio=1.7) -> list[float]:
    out = [0.0] * len(samples)
    env = 0.0
    atk_c = math.exp(-1.0 / (SR * 0.003))
    rel_c = math.exp(-1.0 / (SR * 0.14))
    for i, x in enumerate(samples):
        a = abs(x)
        env = a + (env - a) * (atk_c if a > env else rel_c)
        if env > thr:
            over = env - thr
            gain = thr + over / ratio
            g = gain / max(1e-9, env)
        else:
            g = 1.0
        out[i] = x * g * 1.08
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


def flanger(samples, rate_hz=1.18, depth_ms=3.8, base_ms=2.2, feedback=0.22, mix=0.45):
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
        if w > 1.2:
            w = 1.2
        elif w < -1.2:
            w = -1.2
        circ[i % len(circ)] = w
        out[i] = y
    return out


def chorus(samples, rate_hz=0.55, depth_ms=6.5, base_ms=9.0, mix=0.35):
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


def mono_delay(samples, time_beats=0.375, wet=0.18, fb=0.28):
    d = max(1, int(time_beats * 60.0 / BPM * SR))
    out = [0.0] * len(samples)
    line = [0.0] * len(samples)
    for i, x in enumerate(samples):
        delayed = line[i - d] if i >= d else 0.0
        out[i] = x + delayed * wet
        line[i] = x + delayed * fb
    return out


def find_ffprobe() -> str:
    cands = [
        str(Path(dna.FFMPEG).parent / "ffprobe.exe"),
        r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffprobe.exe",
        "ffprobe",
    ]
    for c in cands:
        try:
            subprocess.run([c, "-version"], capture_output=True, check=True)
            return c
        except Exception:
            continue
    raise RuntimeError("ffprobe not found")


def make_stretch_loop(src_name: str, bars: int = 2) -> list[float]:
    src = FACTORY / src_name
    raw_dst = ONESHOT / f"stretch_raw_{src_name}"
    electribe_master(src, raw_dst)
    samples = read_wav(raw_dst)
    target_n = int(bars * 4.0 * 60.0 / BPM * SR)
    rb_in = ONESHOT / "stretch_rb_in.wav"
    rb_out = ONESHOT / "stretch_rb_out.wav"
    write_mono(rb_in, samples, 0.88)
    ok_rb = False
    try:
        if len(samples) > 100:
            tempo = len(samples) / target_n
            r = subprocess.run(
                [
                    dna.FFMPEG, "-y", "-i", str(rb_in),
                    "-af", f"rubberband=tempo={tempo}:pitch=1",
                    str(rb_out),
                ],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0 and rb_out.exists():
                samples = read_wav(rb_out)
                ok_rb = True
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
    samples = one_pole(samples, 1800.0, mode="lpf")  # darker for body
    write_mono(ONESHOT / "stretch_loop_ready.wav", samples, 0.82)
    print("STRETCH", src_name, "rb", ok_rb, "n", len(samples))
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

    kick = shots.get("esx_SinKick.wav") or dna.synth_kick_sledge(dna.mulberry32(0xE51), "full")
    kick = [dna.tanh_drive(x, 1.7) for x in kick]
    kick = mild_compress_kick(kick)
    body = one_pole(kick, 160.0, mode="lpf")  # weight toward ~52 Hz body
    kick = [0.68 * kick[i] + 0.42 * body[i] for i in range(len(kick))]
    # veiled / ghost kick for anticipation (heavy LPF, no click)
    kick_veiled = one_pole(kick, 95.0, mode="lpf")
    kick_veiled = [x * 0.85 for x in kick_veiled]
    click = dna.synth_kick_sledge(dna.mulberry32(0xC11C), "full")[: int(0.016 * SR)]

    hat_c = shots.get("esx_HH1C.wav") or dna.synth_hat(dna.mulberry32(1), False)
    hat_c = one_pole([dna.tanh_drive(x, 1.05) for x in hat_c], 7500.0, mode="lpf")  # acoustic shelf
    hat_o = shots.get("esx_HH1O.wav") or dna.synth_hat(dna.mulberry32(2), True)
    hat_o = one_pole([dna.tanh_drive(x, 1.0) for x in hat_o], 7000.0, mode="lpf")
    rim = shots.get("esx_Rim1.wav")
    snare = shots.get("esx_SD1.wav")
    junk = shots.get("esx_JunkPerc.wav")
    if junk:
        junk = one_pole([dna.tanh_drive(x, 1.15) for x in junk], 4500.0, mode="lpf")

    stretch_src = "189_SynLP-1.wav" if (FACTORY / "189_SynLP-1.wav").exists() else "175_PercLP-1.wav"
    stretch = make_stretch_loop(stretch_src, bars=2)
    used.append(f"STRETCH:{stretch_src}")

    write_mono(ONESHOT / "kick_ready.wav", kick, 0.94)
    write_mono(ONESHOT / "kick_veiled.wav", kick_veiled, 0.88)
    return {
        "kick": kick,
        "kick_veiled": kick_veiled,
        "click": click,
        "hat_c": hat_c,
        "hat_o": hat_o,
        "rim": rim,
        "snare": snare,
        "junk": junk,
        "stretch": stretch,
        "stretch_src": stretch_src,
        "used": used,
    }


def ensure_vox_phrases():
    """Pozek-style mid chops + flanger — organic under kick, no formant beeps."""
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
            print("MISSING voice", src_name)
            continue
        dst = ONESHOT / f"esx_{src_name}"
        electribe_master(src, dst)
        raw = read_wav(dst)
        if not raw:
            continue
        peak_i = max(range(len(raw)), key=lambda i: abs(raw[i]))
        for dur_s, tag in ((0.09, "short"), (0.14, "mid"), (0.22, "long")):
            start = max(0, peak_i - int(0.012 * SR))
            end = min(len(raw), start + int(dur_s * SR))
            chop = raw[start:end]
            if max(abs(x) for x in chop) < 1e-4:
                continue
            chop = bandpass(chop, 750.0, 2600.0)
            chop = soft_gate(chop, 0.012)
            chop = [math.tanh(x * 1.45) for x in chop]
            rate = 1.05 + 0.35 * rng()
            chop = flanger(chop, rate_hz=rate, depth_ms=3.2 + 1.5 * rng(), feedback=0.2, mix=0.42 + 0.12 * rng())
            pk = max((abs(x) for x in chop), default=0.0)
            if pk > 0.95:
                chop = [x * (0.85 / pk) for x in chop]
            chop = chorus(chop, rate_hz=0.45 + 0.25 * rng(), mix=0.28 + 0.12 * rng())
            chop = bandpass(chop, 800.0, 2500.0)
            write_mono(ONESHOT / f"vox_{Path(src_name).stem}_{tag}.wav", chop, 0.78)
            phrases.append(chop)
            used.append(f"{src_name}:{tag}")

    packs = []
    if phrases:
        for pi in range(8):
            pack = [0.0] * int(0.55 * SR)
            hits = 3 + int(rng() * 3)
            for h in range(hits):
                shot = phrases[int(rng() * len(phrases)) % len(phrases)]
                beat_off = h * (0.12 + 0.04 * rng())
                place(pack, shot, beat_off * (BPM / 60.0), 0.7 + 0.3 * rng())
            pack = mono_delay(pack, time_beats=0.375, wet=0.14, fb=0.20)
            pack = bandpass(pack, 780.0, 2550.0)
            pack = soft_gate(pack, 0.01)
            pk = max((abs(x) for x in pack), default=0.0)
            if pk > 0.9:
                pack = [x * (0.8 / pk) for x in pack]
            write_mono(ONESHOT / f"vox_pack_{pi}.wav", pack, 0.75)
            packs.append(pack)
            used.append(f"pack_{pi}")

    print("VOX_PHRASES", len(phrases), "PACKS", len(packs))
    return phrases, packs, used


def scene_gains(sid: int):
    """Log build 1–4 → clamp release 5 → afterglow 6–8."""
    # kick arc
    kick_map = {
        0: KICK_VEILED_G,      # filtered ghost
        1: KICK_VEILED_G * 1.05,
        2: KICK_SOFT_G,        # soft fund lock
        3: KICK_G * 0.92,      # pre-reward
        4: KICK_RELEASE_G,     # visceral clamp
        5: KICK_G * 0.95,      # afterglow keep sub
        6: KICK_G,             # mute games (pattern handles mute)
        7: KICK_G * 0.85,      # fade out
    }
    hats_map = {
        0: 0.0,
        1: HATS_G * 0.85,
        2: HATS_G * 0.9,
        3: HATS_G,
        4: HATS_G * 0.75,      # tops shelved at release
        5: HATS_G * 0.7,       # strip density
        6: HATS_G * 0.55,
        7: HATS_G * 0.35,
    }
    oh_map = {
        0: 0.0, 1: 0.0, 2: OH_G * 0.5, 3: OH_G * 0.7,
        4: OH_G * 0.55, 5: OH_G * 0.45, 6: OH_G * 0.35, 7: 0.0,
    }
    perc_map = {
        0: 0.0, 1: 0.0, 2: 0.25, 3: 0.35, 4: 0.4, 5: 0.22, 6: 0.18, 7: 0.08,
    }
    stretch_map = {
        0: 0.0, 1: 0.0, 2: 0.15, 3: 0.35, 4: 0.4, 5: 0.5, 6: 0.35, 7: 0.2,
    }
    acid_map = {
        0: 0.0, 1: 0.0, 2: 0.0, 3: 0.08, 4: 0.18, 5: 0.12, 6: 0.1, 7: 0.04,
    }
    vox_map = {
        0: 0.0, 1: 0.0, 2: 0.0,
        3: VOX_G * 0.55,   # whisper
        4: VOX_G,          # under kick at release
        5: VOX_G * 0.75,
        6: VOX_G * 0.5,
        7: VOX_G * 0.2,
    }
    return {
        "kick": kick_map.get(sid, KICK_G),
        "hats": hats_map.get(sid, HATS_G),
        "oh": oh_map.get(sid, 0.0),
        "perc": perc_map.get(sid, 0.3) * PERC_G,
        "stretch": stretch_map.get(sid, 0.3) * STRETCH_SCALE,
        "acid": acid_map.get(sid, 0.1) * ACID_SCALE,
        "vox": vox_map.get(sid, 0.0),
    }


# Body-state labels for physiological report
BODY_STATE = {
    0: "desire / predictive tension — filtered kick ghost, no reward yet",
    1: "desire escalates — sparse tribal hats, kick still veiled",
    2: "pocket lock — 52 Hz fund enters soft, body begins to track",
    3: "pre-reward whisper — Pozek mid chops under kick, still holding",
    4: "VISCERAL RELEASE — full kick+Valve clamp, tops shelved, body hit",
    5: "afterglow roll — sustain tribe, strip density, keep sub flow",
    6: "expectancy replay — kick mute 8 bars then return (dopamine echo)",
    7: "body fade — kick+sub decay, cranial silent, residual warmth",
}


def render_vox_lane(sid: int, phrases, packs) -> list[float]:
    trk = [0.0] * N
    if sid < 3 or not phrases:
        return trk
    rng = dna.mulberry32(0xA11 + sid * 131)

    for bar in range(BARS):
        base = bar * 4.0
        pack_period = 4 if sid in (3, 7) else (2 if sid in (4, 5) else 3)
        if packs and bar % pack_period == 0:
            pack = packs[int(rng() * len(packs)) % len(packs)]
            start_beat = 1.0 if (bar // pack_period) % 2 == 0 else 2.0
            g = {3: 0.55, 4: 0.7, 5: 0.6, 6: 0.45, 7: 0.35}.get(sid, 0.55)
            if sid == 7 and bar >= 10:
                continue
            place(trk, pack, base + start_beat, g)

        if sid == 3:
            hits = [12] if bar % 2 == 1 else []
            g0 = 0.5
        elif sid == 4:
            hits = [6, 14] if bar % 2 == 0 else [10]
            g0 = 0.58
        elif sid == 5:
            hits = [6, 14] if bar % 2 == 0 else [10]
            g0 = 0.5
        elif sid == 6:
            hits = [12] if bar % 2 == 0 else []
            g0 = 0.4
        elif sid == 7:
            hits = [12] if bar < 8 else []
            g0 = 0.3
        else:
            hits = []
            g0 = 0.45

        for st in hits:
            shot = phrases[int(rng() * len(phrases)) % len(phrases)]
            off = swing_offset(st)
            g = g0 * (0.8 + 0.25 * rng())
            if st % 4 == 0:
                g *= 0.5  # kick owns downbeat
            place(trk, shot, base + st * 0.25 + off, g)

    trk = flanger(trk, rate_hz=1.18, depth_ms=2.8, base_ms=1.8, feedback=0.18, mix=0.30)
    trk = mono_delay(trk, time_beats=0.375, wet=0.12, fb=0.18)
    trk = bandpass(trk, 800.0, 2500.0)
    trk = soft_gate(trk, 0.008)
    peak = max((abs(x) for x in trk), default=0.0)
    if peak > 0.85:
        s = 0.75 / peak
        trk = [x * s for x in trk]
    return trk


def render_scene(sid, name, shots, pattern, phrases, packs):
    kick = shots["kick"]
    kick_veiled = shots["kick_veiled"]
    click = shots["click"]
    hat_c = shots["hat_c"]
    hat_o = shots["hat_o"]
    rim = shots["rim"]
    junk = shots["junk"]
    stretch_one = shots["stretch"]

    trk_k = [0.0] * N
    trk_h = [0.0] * N
    trk_oh = [0.0] * N
    trk_p = [0.0] * N
    trk_st = [0.0] * N

    for bar in range(BARS):
        base = bar * 4.0

        # --- KICK: somatic arc ---
        if sid in (0, 1):
            # Intro / Hats_Desire: filtered ghost 4/4 — predictive tension
            ksrc = kick_veiled
            for qi, step in enumerate((0, 4, 8, 12)):
                g = 0.9 if qi in (0, 3) else 0.82
                if sid == 1:
                    g *= 1.05
                place(trk_k, ksrc, base + step * 0.25, g)
                # no click — veiled

        elif sid == 2:
            # Kick_Lock: soft 52 Hz fund enters — pocket lock
            for qi, step in enumerate((0, 4, 8, 12)):
                g = 0.92 if qi in (0, 3) else 0.85
                # fade-in first 4 bars
                if bar < 4:
                    g *= 0.7 + 0.3 * (bar / 4.0)
                place(trk_k, kick, base + step * 0.25, g)
                place(trk_k, click, base + step * 0.25, 0.08)

        elif sid == 3:
            # Vox_Whisper: steady pre-reward pocket
            for qi, step in enumerate((0, 4, 8, 12)):
                g = 1.0 if qi in (0, 3) else 0.92
                place(trk_k, kick, base + step * 0.25, g)
                place(trk_k, click, base + step * 0.25, 0.11)

        elif sid == 4:
            # Release_Visceral: full kick — body hit (NO mid-beat ghosts)
            for qi, step in enumerate((0, 4, 8, 12)):
                g = 1.12 if qi in (0, 3) else 1.02
                place(trk_k, kick, base + step * 0.25, g)
                place(trk_k, click, base + step * 0.25, 0.14)

        elif sid == 5:
            # Afterglow_Roll: keep sub, slightly softer
            for qi, step in enumerate((0, 4, 8, 12)):
                g = 1.0 if qi in (0, 3) else 0.94
                place(trk_k, kick, base + step * 0.25, g)
                place(trk_k, click, base + step * 0.25, 0.10)

        elif sid == 6:
            # Mute_Games: kick mute bars 0–7, return bars 8–23 (expectancy replay)
            if bar >= 8:
                ret = 0.85 if bar < 10 else 1.05
                for qi, step in enumerate((0, 4, 8, 12)):
                    g = (1.1 if qi in (0, 3) else 1.0) * ret
                    place(trk_k, kick, base + step * 0.25, g)
                    place(trk_k, click, base + step * 0.25, 0.13 * ret)
            # bars 0-7: silence (mute)

        elif sid == 7:
            # Outro_BodyFade: decay
            if bar < 16:
                fade = 1.0 if bar < 6 else max(0.15, 1.0 - (bar - 6) * 0.09)
                for qi, step in enumerate((0, 4, 8, 12)):
                    g = (1.0 if qi in (0, 3) else 0.9) * fade
                    place(trk_k, kick, base + step * 0.25, g)
                    if fade > 0.4:
                        place(trk_k, click, base + step * 0.25, 0.08 * fade)

        # --- HATS: sparse tribal ≤0.25 bus — NO busy grids ---
        if sid == 0:
            pass
        elif sid == 1:
            # Hats_Desire: offbeat 8ths only
            for st in (2, 6, 10, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.5)
        elif sid == 2:
            for st in (2, 6, 10, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.52)
            if bar % 2 == 1:
                place(trk_oh, hat_o, base + 14 * 0.25 + swing_offset(14), 0.28)
        elif sid == 3:
            for st in (2, 6, 10, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.55)
            if bar % 2 == 0:
                for st in (3, 11):
                    place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.22)
            if bar % 2 == 1:
                place(trk_oh, hat_o, base + 14 * 0.25 + swing_offset(14), 0.28)
        elif sid == 4:
            # Release: tops shelved — quieter hats
            for st in (2, 6, 10, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.42)
            place(trk_oh, hat_o, base + 14 * 0.25 + swing_offset(14), 0.22)
        elif sid == 5:
            # Afterglow: strip density
            for st in (2, 6, 10, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.4)
            if bar % 2 == 1:
                place(trk_oh, hat_o, base + 14 * 0.25 + swing_offset(14), 0.2)
        elif sid == 6:
            # during mute: light hats keep pulse; after return stay sparse
            for st in (6, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.38 if bar < 8 else 0.45)
        elif sid == 7 and bar < 10:
            for st in (6, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.28)

        # --- PERC: minimal rim ---
        if sid in (2, 3, 4, 5) and rim is not None:
            place(trk_p, rim, base + 1.0, 0.32 if sid != 4 else 0.38)
            if sid >= 4 and bar % 2 == 1:
                place(trk_p, rim, base + 3.0, 0.28)
        if sid == 4 and junk is not None and bar % 8 == 4:
            place(trk_p, junk, base + 2.75 + swing_offset(11), 0.12)

        # --- STRETCH: subtle dark bed ---
        if sid >= 2 and bar % 2 == 0:
            g = {2: 0.25, 3: 0.38, 4: 0.42, 5: 0.5, 6: 0.35, 7: 0.25}.get(sid, 0.3)
            if sid == 7 and bar >= 8:
                g *= 0.45
            if sid == 6 and bar < 8:
                g *= 0.7  # bed during mute
            place(trk_st, stretch_one, base, g)

    # Acid: dark/late only
    acid_drive = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.25, 4: 0.4, 5: 0.3, 6: 0.22, 7: 0.12}.get(sid, 0.2)
    acid_full = classic.render_classic_acid(pattern, grit=classic.GRIT, roll=True)
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))
    if acid_drive > 0:
        acid = one_pole(acid, 1600.0 if sid != 4 else 1500.0, mode="lpf")

    trk_v = render_vox_lane(sid, phrases, packs)

    prefix = f"s{sid}_{name}"
    paths = {
        "kick": OUT / f"{prefix}_kick.wav",
        "hats": OUT / f"{prefix}_hats.wav",
        "oh": OUT / f"{prefix}_oh.wav",
        "perc": OUT / f"{prefix}_perc.wav",
        "stretch": OUT / f"{prefix}_stretch.wav",
        "acid": OUT / f"{prefix}_acid.wav",
        "vox": OUT / f"{prefix}_vox.wav",
    }
    write_mono(paths["kick"], trk_k, 0.92)
    write_mono(paths["hats"], trk_h, 0.75)
    write_mono(paths["oh"], trk_oh, 0.72)
    write_mono(paths["perc"], trk_p, 0.7)
    write_mono(paths["stretch"], trk_st, 0.78)
    write_mono(paths["acid"], acid, 0.78)
    write_mono(paths["vox"], trk_v, 0.78)

    g = scene_gains(sid)

    # Valve intensity: log build → clamp at release
    valve_scale = {
        0: 0.55, 1: 0.65, 2: 0.8, 3: 0.9,
        4: 1.0,   # full Valve clamp
        5: 0.85, 6: 0.9, 7: 0.7,
    }.get(sid, 0.85)
    tube = TUBE_GAIN * valve_scale

    def mix_lr():
        dry = [0.0] * N
        for i in range(N):
            dry[i] = (
                trk_k[i] * g["kick"]
                + acid[i] * g["acid"]
                + trk_h[i] * g["hats"]
                + trk_oh[i] * g["oh"]
                + trk_p[i] * g["perc"]
                + trk_st[i] * g["stretch"]
                + trk_v[i] * g["vox"]
            )
        # mono-safe: keep kick+stretch in center dry; send only mid/high to delay
        send_src = [0.0] * N
        for i in range(N):
            send_src[i] = (
                acid[i] * g["acid"] * 0.4
                + trk_h[i] * g["hats"] * 0.5
                + trk_oh[i] * g["oh"] * 0.3
                + trk_v[i] * g["vox"] * 0.5
            )
        Lpp, Rpp = pingpong_stereo(send_src, wet=DELAY_WET, feedback=DELAY_FB)
        left = [0.0] * N
        right = [0.0] * N
        for i in range(N):
            left[i] = dry[i] + (Lpp[i] - send_src[i]) * 0.8
            right[i] = dry[i] + (Rpp[i] - send_src[i]) * 0.8
        left = valve_force(left, tube_gain=tube)
        right = valve_force(right, tube_gain=tube)
        peak = 1e-9
        for i in range(N):
            peak = max(peak, abs(left[i]), abs(right[i]))
        if peak > 0.95:
            s = 0.92 / peak
            left = [x * s for x in left]
            right = [x * s for x in right]
        return left, right, peak

    left, right, peak = mix_lr()
    mix_path = SECTION_MIX_DIR / f"{prefix}_somatic_mix.wav"
    write_stereo_lr(mix_path, left, right, 0.90)
    paths["mix"] = mix_path

    print(
        "scene", sid, name,
        "body:", BODY_STATE[sid][:50],
        "gains", {k: round(v, 3) for k, v in g.items()},
        "valve", round(tube, 2),
        "peak", round(peak, 4),
    )
    return paths, g, tube


def bounce_mp3(scene_paths, mp3_path: Path) -> float:
    listfile = OUT / "_concat_somatic.txt"
    raw_concat = OUT / "_concat_somatic.wav"
    mastered = OUT / "_master_somatic.wav"
    with open(listfile, "w", encoding="utf-8") as f:
        for sid, name in SCENES:
            p = str(scene_paths[sid]["mix"]).replace("\\", "/")
            f.write(f"file '{p}'\n")
    subprocess.run(
        [dna.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(raw_concat)],
        check=True,
        capture_output=True,
    )
    r = subprocess.run(
        [dna.FFMPEG, "-y", "-i", str(raw_concat), "-af", AF_CHAIN, str(mastered)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print("master fail", r.stderr[-2000:])
        raise RuntimeError("PA master failed")
    subprocess.run(
        [dna.FFMPEG, "-y", "-i", str(mastered), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)],
        check=True,
        capture_output=True,
    )
    dur = 8 * (N / SR)
    try:
        ffprobe = find_ffprobe()
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(mp3_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        dur = float(probe.stdout.strip())
    except Exception as e:
        print("ffprobe", e)
    print("MP3", mp3_path, "dur", round(dur, 2))
    return dur


def write_report(dur, scene_gain_log, used_drums, used_vox, errors):
    lines = [
        "# Somatic Resonance Engineer — Physiological Report @162",
        "",
        f"**Output:** `{MP3}`",
        f"**Duration:** {dur:.2f}s",
        f"**BPM:** {BPM} · Kick fund ~52 Hz · Valve {TUBE_GAIN} · lim 0.89 · loudnorm I≈-8.5 TP=-1.0",
        "",
        "## Mission",
        "Controlled neural discharge on 18″ PA: predictive tension → visceral reward → organic recognizability.",
        "No noise / pretty / busy — body feel only.",
        "",
        "## Scene → Body State + Gains",
        "",
    ]
    for sid, name in SCENES:
        g, tube = scene_gain_log[sid]
        lines.append(f"### {sid+1}. {name}")
        lines.append(f"- **Body:** {BODY_STATE[sid]}")
        lines.append(
            f"- **Gains:** kick={g['kick']:.3f} hats={g['hats']:.3f} oh={g['oh']:.3f} "
            f"perc={g['perc']:.3f} stretch={g['stretch']:.3f} acid={g['acid']:.3f} vox={g['vox']:.3f}"
        )
        lines.append(f"- **Valve:** {tube:.2f}")
        lines.append("")
    lines.extend([
        "## Global stem targets",
        f"Kick {KICK_G} (veiled {KICK_VEILED_G} / soft {KICK_SOFT_G} / release {KICK_RELEASE_G})",
        f"Hats ≤{HATS_G} · OH ≤{OH_G} · Perc bus×{PERC_G} · Acid×{ACID_SCALE} · Stretch×{STRETCH_SCALE} · Vox ≤{VOX_G}",
        "",
        "## Samples",
        f"Drums: {used_drums}",
        f"Vox: {used_vox[:40]}{'...' if len(used_vox)>40 else ''}",
        "",
        "## AF chain",
        "```",
        AF_CHAIN,
        "```",
        "",
        f"Errors: {errors or 'none'}",
        "",
        "## Success criteria check",
        "- anticipation→visceral release→afterglow: scenes 1–4 log build, 5 clamp, 6–8 afterglow/mute/fade",
        "- kick owns ribcage: release gain 1.55 + PA +52/+3.2k",
        "- tops quiet: HS≥7k cuts, hats≤0.25 shelved at release",
        "- vox organic under kick: mid BP 800–2500, flanger, ≤0.35, no formant beeps",
    ])
    text = "\n".join(lines)
    NOTES.write_text(text, encoding="utf-8")
    REPORT.write_text(text, encoding="utf-8")
    print("REPORT", REPORT)


def main():
    errors = []
    print("=== SOMATIC RESONANCE ENGINEER TEST @", BPM, "===")
    shots = ensure_oneshots()
    phrases, packs, used_vox = ensure_vox_phrases()
    if not phrases:
        raise RuntimeError("no vox phrases")
    pattern = classic.classic_pattern(dna.SEED + 303)

    scene_paths = {}
    scene_gain_log = {}
    for sid, name in SCENES:
        paths, g, tube = render_scene(sid, name, shots, pattern, phrases, packs)
        scene_paths[sid] = paths
        scene_gain_log[sid] = (g, tube)

    print("=== Bounce MP3 (stem-render, skip Ableton) ===")
    try:
        dur = bounce_mp3(scene_paths, MP3)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        dur = 0.0

    write_report(dur, scene_gain_log, shots["used"], used_vox, errors)

    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(dur, 2))
    print("ERRORS", errors)
    print("DONE build_esx1_somatic_test_162")


if __name__ == "__main__":
    main()
