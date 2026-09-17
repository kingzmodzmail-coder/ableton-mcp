# -*- coding: utf-8 -*-
"""MENTAL CLEAN DSP @ 162 — classic saw 303 + controlled industrial.

DSP CONTROLS the sound (baked into stems + master):
  Kick: HP~28Hz, mild tanh, peak norm with headroom
  Hats: HP~200, LP~13kHz, quieter
  Industrial: HP~150, LP~9kHz, short gates, -6..-10dB under kick, light room
  Acid: HP~60, LP~5.5kHz, duck ~2.5dB under kick
  Master: glue compress, dip~300Hz, shelf cut >11kHz, TP limiter 0.92, ~-9.5 LUFS

Fewer metal hits in Full (1-2 voices); denser Peak only with DSP taming.
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
import build_liveset_15s_morphs as morph  # noqa: E402
import build_classic_acid_liveset as classic  # noqa: E402

SR = dna.SR
BPM = 162.0
BARS = 10
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR)
HOST, PORT = "127.0.0.1", 9877
FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")

OUT = BRIDGE / "samples" / "crisp-dna" / "mental-clean-dsp"
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"
ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_LiveSet_MentalClean_DSP_162.mp3")

SCENES = [
    (0, "Intro_Kick"),
    (1, "Hats"),
    (2, "Acid_In"),
    (3, "Clank_In"),
    (4, "Full_Mental"),
    (5, "Break"),
    (6, "Peak_Industrial"),
    (7, "Outro"),
]

RES_Q = 0.15
BASE_CUT0 = 320.0
ENV_AMT = 2500.0
ROLL_MAX = 160.0
GRIT = 2.0
ACID_MIX_BED = 0.50
ENV_DECAY = 0.9972
OSC_KIND = "saw"

dna.BPM = BPM
dna.BARS = BARS
dna.BEATS = BEATS
dna.N = N
classic.BPM = BPM
classic.BARS = BARS
classic.BEATS = BEATS
classic.N = N
classic.RES_Q = RES_Q
classic.BASE_CUT0 = BASE_CUT0
classic.ENV_AMT = ENV_AMT
classic.ROLL_MAX = ROLL_MAX
classic.GRIT = GRIT
classic.ENV_DECAY = ENV_DECAY
classic.OSC_KIND = OSC_KIND
classic.OUT = OUT
classic.SECTION_MIX_DIR = SECTION_MIX_DIR


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


def load_audio(track_index, clip_index, path: Path, name: str):
    safe_delete(track_index, clip_index)
    r = send(
        "create_audio_clip",
        {"track_index": track_index, "clip_index": clip_index, "path": str(path)},
        timeout=120,
    )
    if r.get("status") != "success":
        print("FAIL audio", name, r)
        return False
    send("set_clip_name", {"track_index": track_index, "clip_index": clip_index, "name": name})
    print("OK audio", name, "->", track_index, clip_index)
    return True


def put_midi(track_index, clip_index, length, name, notes):
    safe_delete(track_index, clip_index)
    if not notes:
        return False
    r = send("create_clip", {"track_index": track_index, "clip_index": clip_index, "length": length})
    if r.get("status") != "success":
        print("FAIL midi create", name, r)
        return False
    send("set_clip_name", {"track_index": track_index, "clip_index": clip_index, "name": name})
    r2 = send("add_notes_to_clip", {"track_index": track_index, "clip_index": clip_index, "notes": notes})
    if r2.get("status") != "success":
        print("FAIL midi notes", name, r2)
        return False
    print("OK midi", name, "notes", len(notes))
    return True


# --------------- DSP primitives ---------------

def one_pole_hp(buf: list[float], cutoff_hz: float) -> list[float]:
    """Simple one-pole highpass."""
    if cutoff_hz <= 0:
        return list(buf)
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    dt = 1.0 / SR
    a = rc / (rc + dt)
    out = [0.0] * len(buf)
    prev_x = buf[0] if buf else 0.0
    prev_y = 0.0
    for i, x in enumerate(buf):
        y = a * (prev_y + x - prev_x)
        out[i] = y
        prev_x, prev_y = x, y
    return out


def one_pole_lp(buf: list[float], cutoff_hz: float) -> list[float]:
    """Simple one-pole lowpass — tames air/hash."""
    if cutoff_hz <= 0 or cutoff_hz >= SR * 0.49:
        return list(buf)
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    dt = 1.0 / SR
    a = dt / (rc + dt)
    out = [0.0] * len(buf)
    y = buf[0] if buf else 0.0
    for i, x in enumerate(buf):
        y += a * (x - y)
        out[i] = y
    return out


def biquad_peak_dip(buf: list[float], freq: float, gain_db: float, q: float = 1.0) -> list[float]:
    """Peaking EQ (negative gain = dip mud)."""
    A = 10 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * freq / SR
    alpha = math.sin(w0) / (2.0 * q)
    cosw = math.cos(w0)
    b0 = 1 + alpha * A
    b1 = -2 * cosw
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * cosw
    a2 = 1 - alpha / A
    b0, b1, b2 = b0 / a0, b1 / a0, b2 / a0
    a1, a2 = a1 / a0, a2 / a0
    out = [0.0] * len(buf)
    x1 = x2 = y1 = y2 = 0.0
    for i, x in enumerate(buf):
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        out[i] = y
        x2, x1 = x1, x
        y2, y1 = y1, y
    return out


def high_shelf_cut(buf: list[float], freq: float, gain_db: float) -> list[float]:
    """Gentle high shelf (negative gain_db cuts air)."""
    A = 10 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * freq / SR
    cosw = math.cos(w0)
    sinw = math.sin(w0)
    S = 1.0
    alpha = sinw / 2.0 * math.sqrt((A + 1 / A) * (1 / S - 1) + 2)
    b0 = A * ((A + 1) - (A - 1) * cosw + 2 * math.sqrt(A) * alpha)
    b1 = 2 * A * ((A - 1) - (A + 1) * cosw)
    b2 = A * ((A + 1) - (A - 1) * cosw - 2 * math.sqrt(A) * alpha)
    a0 = (A + 1) + (A - 1) * cosw + 2 * math.sqrt(A) * alpha
    a1 = -2 * ((A - 1) + (A + 1) * cosw)
    a2 = (A + 1) + (A - 1) * cosw - 2 * math.sqrt(A) * alpha
    b0, b1, b2 = b0 / a0, b1 / a0, b2 / a0
    a1, a2 = a1 / a0, a2 / a0
    out = [0.0] * len(buf)
    x1 = x2 = y1 = y2 = 0.0
    for i, x in enumerate(buf):
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        out[i] = y
        x2, x1 = x1, x
        y2, y1 = y1, y
    return out


def peak_normalize(buf: list[float], target: float = 0.88) -> list[float]:
    peak = max(1e-9, max(abs(x) for x in buf))
    scale = target / peak
    return [x * scale for x in buf]


def soft_gate(buf: list[float], thresh: float = 0.018, hold_ms: float = 18.0, release_ms: float = 35.0) -> list[float]:
    """Short industrial gate — kills hash tails, keeps clank body."""
    hold_n = int(hold_ms * 0.001 * SR)
    rel_n = max(1, int(release_ms * 0.001 * SR))
    out = [0.0] * len(buf)
    open_left = 0
    gain = 0.0
    for i, x in enumerate(buf):
        if abs(x) >= thresh:
            open_left = hold_n
            gain = 1.0
        elif open_left > 0:
            open_left -= 1
            gain = 1.0
        else:
            gain = max(0.0, gain - 1.0 / rel_n)
        out[i] = x * gain
    return out


def sidechain_duck(signal: list[float], kick: list[float], depth_db: float = 2.5, attack_ms: float = 4.0, release_ms: float = 90.0) -> list[float]:
    """Duck signal ~depth_db under kick envelope (no pumping slam)."""
    depth = 10 ** (-abs(depth_db) / 20.0)
    atk = math.exp(-1.0 / max(1, attack_ms * 0.001 * SR))
    rel = math.exp(-1.0 / max(1, release_ms * 0.001 * SR))
    env = 0.0
    # kick detector threshold relative to kick peak
    kpeak = max(1e-9, max(abs(x) for x in kick))
    thr = 0.18 * kpeak
    out = [0.0] * len(signal)
    n = min(len(signal), len(kick))
    for i in range(n):
        det = abs(kick[i])
        if det > thr:
            env = atk * env + (1 - atk) * 1.0
        else:
            env = rel * env
        g = 1.0 - env * (1.0 - depth)
        out[i] = signal[i] * g
    if len(signal) > n:
        out.extend(signal[n:])
    return out


def soft_glue_compress(buf: list[float], thresh: float = 0.55, ratio: float = 2.2, makeup: float = 1.08) -> list[float]:
    """Mild glue — slow-ish, no pumping."""
    atk = math.exp(-1.0 / (0.012 * SR))
    rel = math.exp(-1.0 / (0.180 * SR))
    env = 0.0
    out = [0.0] * len(buf)
    for i, x in enumerate(buf):
        a = abs(x)
        if a > env:
            env = atk * env + (1 - atk) * a
        else:
            env = rel * env + (1 - rel) * a
        if env > thresh:
            over = env / thresh
            gain = (over ** (1.0 / ratio - 1.0))
            # convert envelope excess to gain reduction gently
            gr = thresh / (thresh + (env - thresh) / ratio)
            out[i] = x * gr * makeup
        else:
            out[i] = x * makeup
    return out


def write_mono(path: Path, mono: list[float], peak_target=0.88):
    dna.write_wav_mono(path, mono, peak_target=peak_target)


def write_stereo_mix(path: Path, mono: list[float], peak_target=0.90):
    peak = max(1e-9, max(abs(x) for x in mono))
    scale = peak_target / peak
    st = array.array("h")
    for x in mono:
        v = max(-32767, min(32767, int(x * scale * 32767)))
        st.append(v)
        st.append(v)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())


def bake_short_reverb(samples: list[float], decay_ms=55.0, wet=0.22, taps=4) -> list[float]:
    """LIGHT room only — not wash (DSP-controlled)."""
    out = list(samples)
    n = len(samples)
    for t in range(1, taps + 1):
        delay = int((decay_ms * 0.001 * SR) * (0.16 + 0.12 * t))
        g = wet * (0.48 ** t)
        for i in range(n):
            j = i + delay
            if j < len(out):
                out[j] += samples[i] * g
            else:
                out.append(samples[i] * g)
    thr = 0.0035
    end = len(out) - 1
    while end > n and abs(out[end]) < thr:
        end -= 1
    return out[: end + 1]


def truncate_noise(samples: list[float], max_ms=70.0) -> list[float]:
    max_n = int(max_ms * 0.001 * SR)
    buf = list(samples[:max_n])
    fade = min(len(buf), int(0.010 * SR))
    for i in range(fade):
        buf[-(i + 1)] *= i / max(1, fade)
    return buf


def dsp_kick(buf: list[float]) -> list[float]:
    x = one_pole_hp(buf, 28.0)
    x = [dna.tanh_drive(v, 1.25) for v in x]  # mild sat
    return peak_normalize(x, 0.90)


def dsp_hats(buf: list[float]) -> list[float]:
    x = one_pole_hp(buf, 200.0)
    x = one_pole_lp(x, 13000.0)  # tame air hash
    x = [v * 0.72 for v in x]  # quieter
    return peak_normalize(x, 0.72)


def dsp_oh(buf: list[float]) -> list[float]:
    x = one_pole_hp(buf, 180.0)
    x = one_pole_lp(x, 12000.0)
    x = [v * 0.65 for v in x]
    return peak_normalize(x, 0.68)


def dsp_industrial(buf: list[float], under_kick_db: float = -8.0) -> list[float]:
    """HP150, LP9k, short gate, light room already on oneshots, level under kick."""
    x = one_pole_hp(buf, 150.0)
    x = one_pole_lp(x, 9000.0)  # kill harsh metallic hash
    x = soft_gate(x, thresh=0.020, hold_ms=16.0, release_ms=28.0)
    gain = 10 ** (under_kick_db / 20.0)
    x = [v * gain for v in x]
    return peak_normalize(x, 0.55)  # keep well under kick peak 0.90


def dsp_acid(buf: list[float], kick: list[float]) -> list[float]:
    x = one_pole_hp(buf, 60.0)
    x = one_pole_lp(x, 5500.0)  # controlled resonance already classic
    x = sidechain_duck(x, kick, depth_db=2.5, attack_ms=3.5, release_ms=85.0)
    return peak_normalize(x, 0.78)


def master_bus_python(mono: list[float]) -> list[float]:
    """Glue + EQ dip 300 + shelf cut >11k + soft limit headroom."""
    x = soft_glue_compress(mono, thresh=0.52, ratio=2.0, makeup=1.05)
    x = biquad_peak_dip(x, 300.0, gain_db=-2.2, q=0.85)
    x = high_shelf_cut(x, 11000.0, gain_db=-2.5)
    x = one_pole_hp(x, 28.0)
    # soft true-peak-ish ceiling ~0.92
    lim = 0.92
    out = []
    for v in x:
        if abs(v) > lim:
            out.append(math.copysign(lim + (abs(v) - lim) * 0.08, v))
        else:
            out.append(v)
    return peak_normalize(out, 0.91)


def master_factory(src_name: str, dst_name: str) -> Path | None:
    src = FACTORY / src_name
    dst = ONESHOT / dst_name
    if not src.exists():
        print("MISSING factory", src_name)
        return None
    try:
        dna.electribe_master(src, dst)
        return dst
    except Exception as e:
        print("FAIL master", src_name, e)
        return None


def ensure_industrial_oneshots():
    used = []
    mapping = {
        "092_JunkPerc.wav": "esx_JunkPerc_mi.wav",
        "095_SynPerc.wav": "esx_SynPerc_mi.wav",
        "099_Zap.wav": "esx_Zap_mi.wav",
        "102_SFX-1.wav": "esx_SFX1_mi.wav",
        "103_SFX-2.wav": "esx_SFX2_mi.wav",
        "045_Rim-1.wav": "esx_Rim1_mi.wav",
        "088_CowbelSy.wav": "esx_Cowbel_mi.wav",
        "054_HH-1C.wav": "esx_HH1C_mi.wav",
        "066_HH-7C.wav": "esx_HH7C_noiseish_mi.wav",
        "146_SinKick.wav": "esx_SinKick_mi.wav",
        "200_Noise.wav": "esx_Noise_mi.wav",
    }
    paths = {}
    for src_name, dst_name in mapping.items():
        p = master_factory(src_name, dst_name)
        if p is not None:
            paths[dst_name] = p
            used.append(src_name)

    kick_path = dna.OUT / "kb_kick_sledge_esx.wav"
    if kick_path.exists():
        kick_main = list(dna.read_wav(kick_path))
    else:
        rng = dna.mulberry32(dna.SEED ^ 0x4D4901)
        kick_main = list(dna.synth_kick_sledge(rng, "full"))

    esx_kick = None
    if "esx_SinKick_mi.wav" in paths:
        esx_kick = list(dna.read_wav(paths["esx_SinKick_mi.wav"]))
    elif (dna.OUT / "esx_SinKick_mastered.wav").exists():
        esx_kick = list(dna.read_wav(dna.OUT / "esx_SinKick_mastered.wav"))

    if "esx_HH7C_noiseish_mi.wav" in paths:
        hat_c = list(dna.read_wav(paths["esx_HH7C_noiseish_mi.wav"]))
        used_hat = "066_HH-7C.wav"
    elif "esx_HH1C_mi.wav" in paths:
        hat_c = list(dna.read_wav(paths["esx_HH1C_mi.wav"]))
        used_hat = "054_HH-1C.wav"
    else:
        hat_c = dna.read_wav(dna.OUT / "esx_HH1C_mastered.wav") if (dna.OUT / "esx_HH1C_mastered.wav").exists() else dna.synth_hat(dna.mulberry32(1), False)
        used_hat = "fallback_hat"

    hat_o = None
    oh_src = FACTORY / "055_HH-1O.wav"
    if oh_src.exists():
        oh_dst = ONESHOT / "esx_HH1O_mi.wav"
        try:
            dna.electribe_master(oh_src, oh_dst)
            hat_o = list(dna.read_wav(oh_dst))
            used.append("055_HH-1O.wav")
        except Exception:
            hat_o = None
    if hat_o is None and (dna.OUT / "esx_HH1O_mastered.wav").exists():
        hat_o = list(dna.read_wav(dna.OUT / "esx_HH1O_mastered.wav"))

    junk_raw = None
    if "esx_JunkPerc_mi.wav" in paths:
        junk_raw = dna.read_wav(paths["esx_JunkPerc_mi.wav"])
    elif (dna.OUT / "esx_JunkPerc_mastered.wav").exists():
        junk_raw = dna.read_wav(dna.OUT / "esx_JunkPerc_mastered.wav")
    clank = None
    if junk_raw is not None:
        # LIGHT room only
        clank = bake_short_reverb([dna.tanh_drive(x, 1.35) for x in junk_raw], decay_ms=55.0, wet=0.22, taps=4)
        clank = soft_gate(clank, thresh=0.022, hold_ms=14.0, release_ms=24.0)
        write_mono(ONESHOT / "clank_dsp_baked.wav", clank, 0.85)

    # Only keep 2 primary metal voices for Full; extras for Peak only
    metal_keys = [
        ("esx_SynPerc_mi.wav", 1.35),
        ("esx_Rim1_mi.wav", 1.30),
        ("esx_Cowbel_mi.wav", 1.25),
        ("esx_Zap_mi.wav", 1.20),
    ]
    metals = []
    for i, (key, drive) in enumerate(metal_keys):
        if key not in paths:
            continue
        m = [dna.tanh_drive(x, drive) for x in dna.read_wav(paths[key])]
        m = bake_short_reverb(m, decay_ms=40.0 + 8 * i, wet=0.16, taps=3)
        m = soft_gate(m, thresh=0.024, hold_ms=12.0, release_ms=22.0)
        metals.append(m)
        write_mono(ONESHOT / f"metal_{i}_dsp.wav", m, 0.82)

    noise = None
    if "esx_Noise_mi.wav" in paths:
        noise = truncate_noise([dna.tanh_drive(x, 1.15) for x in dna.read_wav(paths["esx_Noise_mi.wav"])], max_ms=65.0)
        noise = soft_gate(noise, thresh=0.030, hold_ms=10.0, release_ms=18.0)
        write_mono(ONESHOT / "noise_short_dsp.wav", noise, 0.75)

    atm_metal = metals[1] if len(metals) > 1 else (metals[0] if metals else None)

    print("INDUSTRIAL_SAMPLES_USED", used)
    print("HAT", used_hat, "metals", len(metals), "clank", clank is not None)
    return {
        "kick_main": kick_main,
        "esx_kick": esx_kick,
        "hat_c": hat_c,
        "hat_o": hat_o or hat_c,
        "clank": clank,
        "metals": metals,
        "atm_metal": atm_metal,
        "noise": noise,
        "used": used,
        "hat_src": used_hat,
    }


def place(buf, sample, beat, gain=1.0):
    if sample is None:
        return
    start = int(beat * 60.0 / BPM * SR)
    for i, v in enumerate(sample):
        j = start + i
        if 0 <= j < len(buf):
            buf[j] += v * gain


def render_scene_layers(sid, name, shots, pattern):
    kick_main = shots["kick_main"]
    esx_kick = shots["esx_kick"]
    hat_c = shots["hat_c"]
    hat_o = shots["hat_o"]
    clank = shots["clank"]
    metals = shots["metals"]
    atm_metal = shots["atm_metal"]
    noise = shots["noise"]

    trk_k = [0.0] * N
    trk_h = [0.0] * N
    trk_oh = [0.0] * N
    trk_p = [0.0] * N

    # Primary 2 voices for Full; extras only Peak
    m0 = metals[0] if metals else None
    m1 = metals[1] if len(metals) > 1 else m0
    m2 = metals[2] if len(metals) > 2 else None
    m3 = metals[3] if len(metals) > 3 else None

    for bar in range(BARS):
        base = bar * 4.0

        # --- KICK ---
        if sid == 5:
            pass
        elif sid == 7:
            if bar < 5:
                for step in (0, 4, 8, 12):
                    place(trk_k, kick_main, base + step * 0.25, 1.0 if bar < 3 else 0.78)
                    if esx_kick is not None:
                        place(trk_k, esx_kick, base + step * 0.25, 0.14)
            elif bar < 8:
                for step in (0, 8):
                    place(trk_k, kick_main, base + step * 0.25, 0.55)
        elif sid == 0:
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base + step * 0.25, 0.88)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base + step * 0.25, 0.12)
        elif sid == 6:
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base + step * 0.25, 1.15)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base + step * 0.25, 0.20)
            if bar >= 3:
                place(trk_k, kick_main, base + 1.5, 0.32)
                place(trk_k, kick_main, base + 3.5, 0.28)
        else:
            g = 1.0 if sid >= 3 else 0.92
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base + step * 0.25, g)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base + step * 0.25, 0.14 * g)

        # --- HATS ---
        if sid == 0:
            pass
        elif sid == 1:
            for i, st in enumerate(range(0, 16, 2)):
                place(trk_h, hat_c, base + st * 0.25, 0.68 if i % 2 == 0 else 0.45)
        elif sid == 2:
            for i, st in enumerate(range(0, 16, 2)):
                place(trk_h, hat_c, base + st * 0.25, 0.70 if i % 2 == 0 else 0.48)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.36)
        elif sid in (3, 4):
            for st in range(16):
                swing = 0.012 if st % 2 else 0.0
                g = 0.76 if st % 2 == 0 else 0.46
                place(trk_h, hat_c, base + st * 0.25 + swing, g)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.42 if sid == 4 else 0.36)
        elif sid == 5:
            for st in range(16):
                swing = 0.016 if st % 2 else 0.0
                place(trk_h, hat_c, base + st * 0.25 + swing, 0.38 if st % 2 == 0 else 0.24)
            for st in (6, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.26)
        elif sid == 6:
            for st in range(16):
                swing = 0.010 if st % 2 else 0.0
                place(trk_h, hat_c, base + st * 0.25 + swing, 0.82 if st % 2 == 0 else 0.52)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.48)
        elif sid == 7:
            if bar < 3:
                for i, st in enumerate(range(0, 16, 2)):
                    place(trk_h, hat_c, base + st * 0.25, 0.40 if i % 2 == 0 else 0.24)

        # --- INDUSTRIAL: fewer simultaneous metals ---
        if sid == 3:
            # Clank_In: clanks only + occasional 1 metal
            place(trk_p, clank, base + 3 * 0.25, 0.85)
            place(trk_p, clank, base + 11 * 0.25, 0.80)
            if m0 is not None and bar % 2 == 1:
                place(trk_p, m0, base + 7 * 0.25, 0.42)
        elif sid == 4:
            # Full_Mental: clank + MAX 1-2 metal voices (not 4)
            place(trk_p, clank, base + 3 * 0.25, 0.90)
            place(trk_p, clank, base + 11 * 0.25, 0.86)
            # rotate between m0/m1 only — never stack 3+
            if bar % 2 == 0:
                place(trk_p, m0, base + 5 * 0.25, 0.48)
            else:
                place(trk_p, m1, base + 9 * 0.25, 0.45)
            if noise is not None and bar in (4, 8):
                place(trk_p, noise, base + 7 * 0.25, 0.28)
        elif sid == 5:
            if atm_metal is not None:
                place(trk_p, atm_metal, base + 1.0, 0.36)
            if clank is not None and bar % 2 == 0:
                place(trk_p, clank, base + 11 * 0.25, 0.40)
            if noise is not None and bar in (2, 6):
                place(trk_p, noise, base + 2.5, 0.24)
        elif sid == 6:
            # Peak denser BUT still DSP-controlled gains
            place(trk_p, clank, base + 3 * 0.25, 0.95)
            place(trk_p, clank, base + 11 * 0.25, 0.92)
            if bar >= 4:
                place(trk_p, clank, base + 7 * 0.25, 0.55)
            place(trk_p, m0, base + 1 * 0.25, 0.50)
            place(trk_p, m1, base + 5 * 0.25, 0.52)
            if m2 is not None:
                place(trk_p, m2, base + 9 * 0.25, 0.42)
            if m3 is not None and bar % 2 == 0:
                place(trk_p, m3, base + 13 * 0.25, 0.38)
            if noise is not None:
                place(trk_p, noise, base + 7 * 0.25, 0.32)
        elif sid == 7:
            if bar < 2 and clank is not None:
                place(trk_p, clank, base + 3 * 0.25, 0.42)
                place(trk_p, clank, base + 11 * 0.25, 0.36)

    acid_drive = {0: 0.0, 1: 0.0, 2: 0.92, 3: 0.95, 4: 1.0, 5: 1.05, 6: 1.0, 7: 0.35}.get(sid, 0.90)
    acid_full = classic.render_classic_acid(pattern, grit=GRIT + (0.10 if sid == 6 else 0.0), roll=True)
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))

    # === APPLY PER-STEM DSP ===
    trk_k = dsp_kick(trk_k)
    trk_h = dsp_hats(trk_h)
    trk_oh = dsp_oh(trk_oh)
    under_db = {-3: -7.0, 4: -8.0, 5: -7.5, 6: -6.5, 7: -10.0}.get(sid, -8.0)
    trk_p = dsp_industrial(trk_p, under_kick_db=under_db)
    acid = dsp_acid(acid, trk_k)

    prefix = f"s{sid}_{name}"
    paths = {
        "kick": OUT / f"{prefix}_kick.wav",
        "hats": OUT / f"{prefix}_hats.wav",
        "oh": OUT / f"{prefix}_oh.wav",
        "perc": OUT / f"{prefix}_perc.wav",
        "acid": OUT / f"{prefix}_acid_classic.wav",
    }
    write_mono(paths["kick"], trk_k, 0.90)
    write_mono(paths["hats"], trk_h, 0.72)
    write_mono(paths["oh"], trk_oh, 0.68)
    write_mono(paths["perc"], trk_p, 0.55)
    write_mono(paths["acid"], acid, 0.78)

    acid_mix_g = {
        0: 0.0, 1: 0.0, 2: 0.46, 3: 0.48, 4: 0.48, 5: 0.52, 6: 0.48, 7: 0.26,
    }.get(sid, ACID_MIX_BED)
    # perc already -6..-10dB in dsp_industrial; mix gain modest
    perc_g = {
        0: 0.0, 1: 0.0, 2: 0.0, 3: 0.85, 4: 0.90, 5: 0.80, 6: 1.00, 7: 0.55,
    }.get(sid, 0.85)
    kick_g = 0.0 if sid == 5 else 1.10
    hats_g = 0.85
    oh_g = 0.70

    mix = [0.0] * N
    for i in range(N):
        mono = (
            trk_k[i] * kick_g
            + acid[i] * acid_mix_g
            + trk_h[i] * hats_g
            + trk_oh[i] * oh_g
            + trk_p[i] * perc_g
        )
        mix[i] = mono

    mix = master_bus_python(mix)
    mix_path = SECTION_MIX_DIR / f"{prefix}_mix.wav"
    write_stereo_mix(mix_path, mix, peak_target=0.91)
    paths["mix"] = mix_path
    print("scene", sid, name, "acid_mix", acid_mix_g, "perc_under_db", under_db, "perc_g", perc_g)
    return paths


def quiet_midi_for_scene(pattern, sid, bars=10):
    notes = []
    gate = 0.14
    slide_dur = 0.32
    keep = {
        0: lambda st, bar: False,
        1: lambda st, bar: False,
        2: lambda st, bar: st % 2 == 0,
        3: lambda st, bar: True,
        4: lambda st, bar: True,
        5: lambda st, bar: True,
        6: lambda st, bar: True,
        7: lambda st, bar: st % 4 == 0 and bar < 4,
    }[sid]
    for bar in range(bars):
        base = bar * 4.0
        for st, p in enumerate(pattern):
            if p["midi"] <= 0 or not keep(st, bar):
                continue
            dur = slide_dur if p["slide"] else gate
            vel = 44 if p["accent"] else 30
            notes.append(
                {
                    "pitch": int(p["midi"]),
                    "start_time": base + st * 0.25,
                    "duration": dur,
                    "velocity": vel,
                    "mute": False,
                }
            )
    return notes


def bounce_mp3(scene_paths):
    concat_list = OUT / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for sid, name in SCENES:
            p = str(scene_paths[sid]["mix"]).replace("\\", "/")
            f.write(f"file '{p}'\n")
    raw_concat = OUT / "mental_clean_dsp_concat.wav"
    subprocess.run(
        [dna.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw_concat)],
        check=True,
        capture_output=True,
    )
    # Master ffmpeg: mild acompressor + EQ + alimiter (NOT brickwall crush)
    # Target ~-9.5 LUFS without aggressive pumping — softer loudnorm LRA
    loud = OUT / "mental_clean_dsp_club.wav"
    af = (
        "highpass=f=28,"
        "equalizer=f=300:t=q:w=0.9:g=-2.0,"
        "treble=f=11000:t=q:w=0.7:g=-2.5,"
        "acompressor=threshold=-18dB:ratio=2.0:attack=12:release=180:makeup=2,"
        "alimiter=limit=0.92:attack=5:release=50,"
        "loudnorm=I=-9.5:TP=-1.2:LRA=8"
    )
    try:
        r = subprocess.run(
            [dna.FFMPEG, "-y", "-i", str(raw_concat), "-af", af, "-ar", "44100", str(loud)],
            check=True,
            capture_output=True,
            text=True,
        )
        src = loud
        print("ffmpeg master OK")
    except Exception as e:
        print("ffmpeg master fail, using python-mastered concat", e)
        src = raw_concat
    subprocess.run(
        [dna.FFMPEG, "-y", "-i", str(src), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3)],
        check=True,
        capture_output=True,
    )
    dur = 8 * (N / SR)
    try:
        ffprobe = dna.FFMPEG.replace("ffmpeg.exe", "ffprobe.exe") if "ffmpeg.exe" in dna.FFMPEG else "ffprobe"
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(MP3)],
            capture_output=True,
            text=True,
            check=True,
        )
        dur = float(probe.stdout.strip())
    except Exception:
        try:
            import re
            p = subprocess.run([dna.FFMPEG, "-i", str(MP3)], capture_output=True, text=True)
            m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", p.stderr)
            if m:
                dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        except Exception:
            pass
    print("MP3", MP3, "dur", round(dur, 2))
    return dur


def silence_mental_atm(by_full):
    morph.silence_noisy(by_full)
    for name, t in list(by_full.items()):
        low = name.lower()
        if any(k in low for k in ("mental", "atm", "grain", "atmosphere", "bed")):
            idx = t["index"]
            for row in range(8):
                send("stop_clip", {"track_index": idx, "clip_index": row})
                send("delete_clip", {"track_index": idx, "clip_index": row})
            send("set_track_mute", {"track_index": idx, "mute": True})
            print("silenced/muted bed", name, idx)


def try_load_ableton_fx(track_indices):
    """Best-effort stock FX on master/returns if browser allows."""
    # Probe master track index via snapshot later; try load on first audio track returns
    uris = [
        ("query:Audio Effects#EQ Eight", "EQ Eight"),
        ("query:Audio Effects#Compressor", "Compressor"),
        ("query:Audio Effects#Saturator", "Saturator"),
    ]
    loaded = []
    # Try on kick track as stand-in if master URI unsupported
    for idx in track_indices:
        if idx is None:
            continue
        for uri, label in uris:
            r = send("load_browser_item", {"track_index": idx, "item_uri": uri})
            st = r.get("status")
            print("FX try", label, "on", idx, st, r.get("message", r.get("result")))
            if st == "success":
                loaded.append(label)
            # only attempt once per effect type on first workable track
            break
        break
    return loaded


def main():
    errors = []
    print("=== MENTAL CLEAN DSP classic 303 @", BPM, "N=", N, f"sec/scene={N/SR:.2f} ===")
    print("PARAMS osc=", OSC_KIND, "resQ=", RES_Q, "envAmt=", ENV_AMT, "grit=", GRIT)
    print("DSP: kick HP28+tanh | hats HP200 LP13k quiet | ind HP150 LP9k gate -6..-10dB | acid HP60 LP5.5k duck2.5dB")
    print("MASTER: glue + dip300 + shelf11k + lim0.92 + loudnorm -9.5 LUFS")

    shots = ensure_industrial_oneshots()
    pattern = classic.classic_pattern(dna.SEED + 303)
    accents = sum(1 for p in pattern if p["accent"])
    slides = sum(1 for p in pattern if p["slide"])
    print("pattern accents", accents, "slides", slides)

    scene_paths = {}
    for sid, name in SCENES:
        scene_paths[sid] = render_scene_layers(sid, name, shots, pattern)

    print("=== Bounce MentalClean_DSP MP3 ===")
    try:
        mp3_dur = bounce_mp3(scene_paths)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        mp3_dur = 0.0

    print("=== Ableton load cleaned stems + fire Full_Mental ===")
    snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=60)
    snap = ok(snap_r, "snapshot")
    if not snap:
        print("ABORT no Ableton — MP3 still written")
        print("MP3_PATH", str(MP3))
        print("MP3_DURATION_SEC", round(mp3_dur, 2))
        print("INDUSTRIAL_SAMPLES", shots["used"])
        print("ERRORS", errors)
        return

    ok(send("set_tempo", {"tempo": BPM}), "tempo 162")
    ok(send("stop_playback"), "stop")

    for t in snap["tracks"]:
        for sl in t.get("clip_slots") or []:
            if sl.get("has_clip"):
                send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})

    by = {t["name"]: t["index"] for t in snap["tracks"]}
    by_full = {t["name"]: t for t in snap["tracks"]}
    print("tracks", by)

    silence_mental_atm(by_full)

    acid_midi_idx = by.get("Acid 303 Poly")
    acid_audio_idx = by.get("Acid 303") or by.get("Acid Scream Audio") or by.get("E-Syn")
    kick_idx = by.get("E-Kick")
    hats_idx = by.get("E-Hats")
    perc_idx = by.get("E-Perc")
    oh_idx = by.get("E-OHat") or by.get("E-Snare")
    bass_idx = by.get("Tholin Bass") or by.get("E-Bass")

    if acid_audio_idx is not None:
        send("set_track_name", {"track_index": acid_audio_idx, "name": "Acid 303"})
        by["Acid 303"] = acid_audio_idx

    if acid_midi_idx is not None:
        r = send("load_browser_item", {"track_index": acid_midi_idx, "item_uri": "query:Synths#Drift"})
        print("Drift load", r.get("status"), r.get("message", r.get("result")))

    fx_loaded = try_load_ableton_fx([kick_idx])
    print("ABLETON_FX_ATTEMPTED", fx_loaded if fx_loaded else "browser empty / baked into wavs")

    for row, _ in SCENES:
        for idx in (acid_midi_idx, acid_audio_idx, kick_idx, hats_idx, perc_idx, oh_idx, bass_idx):
            if idx is not None:
                safe_delete(idx, row)

    clip_len = float(BEATS)

    for sid, name in SCENES:
        paths = scene_paths[sid]
        if kick_idx is not None and morph.layer_has_signal(paths["kick"]):
            load_audio(kick_idx, sid, paths["kick"], f"{name}_kick_dsp")
        if hats_idx is not None and morph.layer_has_signal(paths["hats"]):
            load_audio(hats_idx, sid, paths["hats"], f"{name}_hats_dsp")
        if oh_idx is not None and morph.layer_has_signal(paths["oh"]):
            load_audio(oh_idx, sid, paths["oh"], f"{name}_oh_dsp")
        if perc_idx is not None and morph.layer_has_signal(paths["perc"]):
            load_audio(perc_idx, sid, paths["perc"], f"{name}_ind_dsp")
        if acid_audio_idx is not None and morph.layer_has_signal(paths["acid"]):
            load_audio(acid_audio_idx, sid, paths["acid"], f"{name}_classic303_dsp")
        midi = quiet_midi_for_scene(pattern, sid, bars=BARS)
        if acid_midi_idx is not None and midi:
            put_midi(acid_midi_idx, sid, clip_len, f"{name}_drift_quiet", midi)
        send("create_locator", {"name": f"{sid}_{name}", "time": float(sid * clip_len)})

    FIRE_ROW = 4
    fire_name = "Full_Mental"
    if not morph.layer_has_signal(scene_paths[4]["acid"]):
        FIRE_ROW = 6
        fire_name = "Peak_Industrial"

    print("=== Fire", fire_name, "row", FIRE_ROW, "===")
    fired = []
    for label, idx, key in [
        ("kick", kick_idx, "kick"),
        ("hats", hats_idx, "hats"),
        ("oh", oh_idx, "oh"),
        ("perc", perc_idx, "perc"),
        ("acid_audio", acid_audio_idx, "acid"),
        ("acid_midi", acid_midi_idx, None),
    ]:
        if idx is None:
            continue
        if key and not morph.layer_has_signal(scene_paths[FIRE_ROW][key]):
            continue
        if label == "acid_midi" and not quiet_midi_for_scene(pattern, FIRE_ROW, bars=BARS):
            continue
        r = send("fire_clip", {"track_index": idx, "clip_index": FIRE_ROW})
        if r.get("status") == "success":
            fired.append(label)
            print("FIRE", label, "row", FIRE_ROW)
        else:
            print("fire fail", label, r)

    ok(send("start_playback"), "start_playback")
    info = send("get_session_info")
    res = info.get("result") or info
    playing = res.get("is_playing")
    print("tempo", res.get("tempo"), "is_playing", playing)

    print("DSP_CHAIN", {
        "kick": "HP28 + mild tanh + peakNorm 0.90",
        "hats": "HP200 LP13k *0.72 quieter",
        "industrial": "HP150 LP9k shortGate lightRoom -6..-10dB under kick",
        "acid": "HP60 LP5.5k duck 2.5dB under kick",
        "master": "glue acomp + dip300 -2dB + shelf11k -2.5dB + alimiter 0.92 + loudnorm -9.5 LUFS",
        "full_mental_metals": "1-2 voices max",
        "peak_metals": "denser with DSP",
        "harsh_hash": "REDUCED via LP+gates",
    })
    print("FIRED", fire_name, fired)
    print("INDUSTRIAL_SAMPLES", shots["used"])
    print("HAT_SRC", shots["hat_src"])
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(mp3_dur, 2))
    print("IS_PLAYING", playing)
    print("ERRORS", errors)
    print("DONE build_mental_clean_dsp_liveset")


if __name__ == "__main__":
    main()
