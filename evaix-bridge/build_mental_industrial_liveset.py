# -*- coding: utf-8 -*-
"""CLASSIC TB-303 acid + MORE MENTAL INDUSTRIAL @ 162 BPM.

Keep classic saw 303 (resQ~0.15, envAmt~2500). Drive vocab:
Pneumatix tribal + Enko industrial — clanks on 4/12, metal hits,
denser perc in peak, short industrial noise, short reverb baked into clanks.
NOT commercial drops. Kick-dominated; industrial HEARD under/around kick.
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

OUT = BRIDGE / "samples" / "crisp-dna" / "mental-industrial"
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"
ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_LiveSet_MentalIndustrial_162.mp3")

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

# Classic 303 params (no Star Wars laser)
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


def write_mono(path: Path, mono: list[float], peak_target=0.90):
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


def bake_short_reverb(samples: list[float], decay_ms=85.0, wet=0.38, taps=6) -> list[float]:
    """Short industrial room / plate-ish decay baked into one-shot (no long wash)."""
    out = list(samples)
    n = len(samples)
    for t in range(1, taps + 1):
        delay = int((decay_ms * 0.001 * SR) * (0.18 + 0.14 * t))
        g = wet * (0.55 ** t)
        for i in range(n):
            j = i + delay
            if j < n:
                out[j] += samples[i] * g
            elif j < len(out):
                out[j] += samples[i] * g
            else:
                # extend slightly for tail
                out.append(samples[i] * g)
    # soft truncate tail
    thr = 0.004
    end = len(out) - 1
    while end > n and abs(out[end]) < thr:
        end -= 1
    return out[: end + 1]


def truncate_noise(samples: list[float], max_ms=90.0) -> list[float]:
    max_n = int(max_ms * 0.001 * SR)
    buf = list(samples[:max_n])
    # fast fade
    fade = min(len(buf), int(0.012 * SR))
    for i in range(fade):
        buf[-(i + 1)] *= i / max(1, fade)
    return buf


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
    """Master ESX industrial/metal/noise + bake short reverb on clanks."""
    used = []
    mapping = {
        "092_JunkPerc.wav": "esx_JunkPerc_mi.wav",
        "095_SynPerc.wav": "esx_SynPerc_mi.wav",
        "099_Zap.wav": "esx_Zap_mi.wav",
        "102_SFX-1.wav": "esx_SFX1_mi.wav",
        "103_SFX-2.wav": "esx_SFX2_mi.wav",
        "104_SFX-3.wav": "esx_SFX3_mi.wav",
        "200_Noise.wav": "esx_Noise_mi.wav",
        "045_Rim-1.wav": "esx_Rim1_mi.wav",
        "088_CowbelSy.wav": "esx_Cowbel_mi.wav",
        "054_HH-1C.wav": "esx_HH1C_mi.wav",
        "066_HH-7C.wav": "esx_HH7C_noiseish_mi.wav",  # brighter/noisier hat if available
        "146_SinKick.wav": "esx_SinKick_mi.wav",
    }
    paths = {}
    for src_name, dst_name in mapping.items():
        p = master_factory(src_name, dst_name)
        if p is not None:
            paths[dst_name] = p
            used.append(src_name)

    # Prefer existing CRISP kick DNA if present
    kick_path = dna.OUT / "kb_kick_sledge_esx.wav"
    if kick_path.exists():
        kick_main = [dna.tanh_drive(x, 1.35) for x in dna.read_wav(kick_path)]
    else:
        rng = dna.mulberry32(dna.SEED ^ 0x4D4901)
        kick_main = [dna.tanh_drive(x, 1.35) for x in dna.synth_kick_sledge(rng, "full")]

    esx_kick = None
    if "esx_SinKick_mi.wav" in paths:
        esx_kick = [dna.tanh_drive(x, 1.7) for x in dna.read_wav(paths["esx_SinKick_mi.wav"])]
    elif (dna.OUT / "esx_SinKick_mastered.wav").exists():
        esx_kick = [dna.tanh_drive(x, 1.7) for x in dna.read_wav(dna.OUT / "esx_SinKick_mastered.wav")]

    # Hats: prefer noisier HH-7C, else HH-1C, else mastered
    if "esx_HH7C_noiseish_mi.wav" in paths:
        hat_c = [dna.tanh_drive(x, 1.25) for x in dna.read_wav(paths["esx_HH7C_noiseish_mi.wav"])]
        used_hat = "066_HH-7C.wav"
    elif "esx_HH1C_mi.wav" in paths:
        hat_c = [dna.tanh_drive(x, 1.2) for x in dna.read_wav(paths["esx_HH1C_mi.wav"])]
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
            hat_o = [dna.tanh_drive(x, 1.15) for x in dna.read_wav(oh_dst)]
            used.append("055_HH-1O.wav")
        except Exception:
            hat_o = None
    if hat_o is None and (dna.OUT / "esx_HH1O_mastered.wav").exists():
        hat_o = [dna.tanh_drive(x, 1.15) for x in dna.read_wav(dna.OUT / "esx_HH1O_mastered.wav")]

    # Clank = JunkPerc + short reverb bake
    junk_raw = None
    if "esx_JunkPerc_mi.wav" in paths:
        junk_raw = dna.read_wav(paths["esx_JunkPerc_mi.wav"])
    elif (dna.OUT / "esx_JunkPerc_mastered.wav").exists():
        junk_raw = dna.read_wav(dna.OUT / "esx_JunkPerc_mastered.wav")
    clank = None
    if junk_raw is not None:
        clank = bake_short_reverb([dna.tanh_drive(x, 1.55) for x in junk_raw], decay_ms=90.0, wet=0.42)
        write_mono(ONESHOT / "clank_rev_baked.wav", clank, 0.92)

    # Metal hits: SynPerc / SFX / Zap / Cowbel / Rim — pick metallic character
    metal_candidates = []
    for key, drive in [
        ("esx_SynPerc_mi.wav", 1.6),
        ("esx_SFX1_mi.wav", 1.5),
        ("esx_SFX2_mi.wav", 1.55),
        ("esx_SFX3_mi.wav", 1.45),
        ("esx_Zap_mi.wav", 1.4),
        ("esx_Cowbel_mi.wav", 1.35),
        ("esx_Rim1_mi.wav", 1.5),
    ]:
        if key in paths:
            metal_candidates.append([dna.tanh_drive(x, drive) for x in dna.read_wav(paths[key])])

    metals = []
    for i, m in enumerate(metal_candidates[:4]):
        # slightly different short decays
        baked = bake_short_reverb(m, decay_ms=55.0 + 12 * i, wet=0.28 + 0.04 * i, taps=5)
        metals.append(baked)
        write_mono(ONESHOT / f"metal_{i}_baked.wav", baked, 0.90)

    # Short industrial noise burst
    noise = None
    if "esx_Noise_mi.wav" in paths:
        noise = truncate_noise([dna.tanh_drive(x, 1.3) for x in dna.read_wav(paths["esx_Noise_mi.wav"])], max_ms=75.0)
        write_mono(ONESHOT / "noise_short_mi.wav", noise, 0.85)

    # Atm metal sparse (softer SFX)
    atm_metal = metals[1] if len(metals) > 1 else (metals[0] if metals else None)

    print("INDUSTRIAL_SAMPLES_USED", used)
    print("HAT", used_hat, "metals", len(metals), "clank", clank is not None, "noise", noise is not None)
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
    """Pneumatix tribal + Enko industrial density by scene."""
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

    m0 = metals[0] if metals else None
    m1 = metals[1] if len(metals) > 1 else m0
    m2 = metals[2] if len(metals) > 2 else m0
    m3 = metals[3] if len(metals) > 3 else m1

    for bar in range(BARS):
        base = bar * 4.0

        # --- KICK (kick-dominated) ---
        if sid == 5:
            pass  # Break — no kick
        elif sid == 7:
            # Outro: strip industrial then kick thins
            if bar < 5:
                for step in (0, 4, 8, 12):
                    place(trk_k, kick_main, base + step * 0.25, 1.0 if bar < 3 else 0.78)
                    if esx_kick is not None:
                        place(trk_k, esx_kick, base + step * 0.25, 0.16)
            elif bar < 8:
                for step in (0, 8):
                    place(trk_k, kick_main, base + step * 0.25, 0.55)
        elif sid == 0:
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base + step * 0.25, 0.88)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base + step * 0.25, 0.14)
        elif sid == 6:
            # Peak harder kick + Enko grit ghosts
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base + step * 0.25, 1.18)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base + step * 0.25, 0.24)
            if bar >= 3:
                place(trk_k, kick_main, base + 1.5, 0.38)
                place(trk_k, kick_main, base + 3.5, 0.32)
        else:
            g = 1.0 if sid >= 3 else 0.92
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base + step * 0.25, g)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base + step * 0.25, 0.16 * g)

        # --- HATS (tribal Pneumatix-ish) ---
        if sid == 0:
            pass
        elif sid == 1:
            # tribal closed on even 8ths 70/50
            for i, st in enumerate(range(0, 16, 2)):
                place(trk_h, hat_c, base + st * 0.25, 0.72 if i % 2 == 0 else 0.50)
        elif sid == 2:
            for i, st in enumerate(range(0, 16, 2)):
                place(trk_h, hat_c, base + st * 0.25, 0.74 if i % 2 == 0 else 0.52)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.40)
        elif sid in (3, 4):
            for st in range(16):
                swing = 0.012 if st % 2 else 0.0
                g = 0.82 if st % 2 == 0 else 0.52
                place(trk_h, hat_c, base + st * 0.25 + swing, g)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.48 if sid == 4 else 0.40)
        elif sid == 5:
            for st in range(16):
                swing = 0.016 if st % 2 else 0.0
                place(trk_h, hat_c, base + st * 0.25 + swing, 0.42 if st % 2 == 0 else 0.28)
            for st in (6, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.30)
        elif sid == 6:
            for st in range(16):
                swing = 0.010 if st % 2 else 0.0
                place(trk_h, hat_c, base + st * 0.25 + swing, 0.90 if st % 2 == 0 else 0.60)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.55)
            if bar >= 5:
                place(trk_oh, hat_o, base + 3.5, 0.38)
        elif sid == 7:
            if bar < 3:
                for i, st in enumerate(range(0, 16, 2)):
                    place(trk_h, hat_c, base + st * 0.25, 0.45 if i % 2 == 0 else 0.28)

        # --- INDUSTRIAL PERC (HEARD — more presence) ---
        # Pneumatix clanks on 4/12 = 16th steps 3 and 11
        if sid == 3:
            # Clank_In
            place(trk_p, clank, base + 3 * 0.25, 0.95)
            place(trk_p, clank, base + 11 * 0.25, 0.92)
            if m0 is not None and bar % 2 == 1:
                place(trk_p, m0, base + 7 * 0.25, 0.55)
        elif sid == 4:
            # Full_Mental: clanks 4/12 + metal offs
            place(trk_p, clank, base + 3 * 0.25, 1.05)
            place(trk_p, clank, base + 11 * 0.25, 1.00)
            place(trk_p, m0, base + 1 * 0.25, 0.58)   # off after kick
            place(trk_p, m1, base + 5 * 0.25, 0.62)
            place(trk_p, m2, base + 9 * 0.25, 0.55)
            place(trk_p, m1, base + 13 * 0.25, 0.50)
            if noise is not None and bar in (2, 5, 8):
                place(trk_p, noise, base + 7 * 0.25, 0.42)
        elif sid == 5:
            # Break: sparse industrial atmosphere (no kick)
            if atm_metal is not None:
                place(trk_p, atm_metal, base + 1.0, 0.48)
                place(trk_p, atm_metal, base + 3.0, 0.40)
            if clank is not None and bar % 2 == 0:
                place(trk_p, clank, base + 11 * 0.25, 0.55)
            if noise is not None and bar in (1, 4, 7):
                place(trk_p, noise, base + 2.5, 0.35)
            if m2 is not None and bar % 3 == 0:
                place(trk_p, m2, base + 0.75, 0.38)
        elif sid == 6:
            # Peak_Industrial denser clanks/metal + short noise
            place(trk_p, clank, base + 3 * 0.25, 1.12)
            place(trk_p, clank, base + 11 * 0.25, 1.08)
            # extra mid-bar clank late
            if bar >= 4:
                place(trk_p, clank, base + 7 * 0.25, 0.72)
            place(trk_p, m0, base + 1 * 0.25, 0.68)
            place(trk_p, m1, base + 5 * 0.25, 0.72)
            place(trk_p, m2, base + 6 * 0.25, 0.48)
            place(trk_p, m3, base + 9 * 0.25, 0.65)
            place(trk_p, m1, base + 13 * 0.25, 0.58)
            place(trk_p, m0, base + 14 * 0.25, 0.42)
            if noise is not None:
                place(trk_p, noise, base + 7 * 0.25, 0.50)
                if bar >= 6:
                    place(trk_p, noise, base + 15 * 0.25, 0.38)
        elif sid == 7:
            # strip industrial early then gone
            if bar < 2 and clank is not None:
                place(trk_p, clank, base + 3 * 0.25, 0.55)
                place(trk_p, clank, base + 11 * 0.25, 0.48)
            elif bar < 4 and m0 is not None:
                place(trk_p, m0, base + 11 * 0.25, 0.30)

    # Classic acid stem
    acid_drive = {0: 0.0, 1: 0.0, 2: 0.92, 3: 0.95, 4: 1.0, 5: 1.05, 6: 1.0, 7: 0.35}.get(sid, 0.90)
    acid_full = classic.render_classic_acid(pattern, grit=GRIT + (0.15 if sid == 6 else 0.0), roll=True)
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))

    if sid == 6:
        trk_k = [x * 1.06 for x in trk_k]
        trk_p = [x * 1.10 for x in trk_p]  # industrial presence boost at peak

    prefix = f"s{sid}_{name}"
    paths = {
        "kick": OUT / f"{prefix}_kick.wav",
        "hats": OUT / f"{prefix}_hats.wav",
        "oh": OUT / f"{prefix}_oh.wav",
        "perc": OUT / f"{prefix}_perc.wav",
        "acid": OUT / f"{prefix}_acid_classic.wav",
    }
    write_mono(paths["kick"], trk_k, 0.92)
    write_mono(paths["hats"], trk_h, 0.85)
    write_mono(paths["oh"], trk_oh, 0.80)
    write_mono(paths["perc"], trk_p, 0.88)
    write_mono(paths["acid"], acid, 0.88)

    # Mix: kick dominated, acid under, industrial HEARD (higher perc than classic 0.20)
    acid_mix_g = {
        0: 0.0,
        1: 0.0,
        2: 0.48,
        3: 0.50,
        4: 0.50,
        5: 0.55,
        6: 0.50,
        7: 0.28,
    }.get(sid, ACID_MIX_BED)
    perc_g = {
        0: 0.0,
        1: 0.0,
        2: 0.0,
        3: 0.38,
        4: 0.42,
        5: 0.36,
        6: 0.48,
        7: 0.18,
    }.get(sid, 0.35)
    kick_g = 0.0 if sid == 5 else 1.08

    mix = [0.0] * N
    for i in range(N):
        mono = (
            trk_k[i] * kick_g
            + acid[i] * acid_mix_g
            + trk_h[i] * 0.24
            + trk_oh[i] * 0.18
            + trk_p[i] * perc_g
        )
        mix[i] = dna.tanh_drive(mono, 1.10 if sid != 6 else 1.14)
    mix_path = SECTION_MIX_DIR / f"{prefix}_mix.wav"
    write_stereo_mix(mix_path, mix, peak_target=0.90)
    paths["mix"] = mix_path
    print("scene", sid, name, "acid_drive", acid_drive, "acid_mix", acid_mix_g, "perc_g", perc_g)
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
    raw_concat = OUT / "mental_industrial_concat.wav"
    subprocess.run(
        [dna.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw_concat)],
        check=True,
        capture_output=True,
    )
    loud = OUT / "mental_industrial_club.wav"
    try:
        subprocess.run(
            [
                dna.FFMPEG,
                "-y",
                "-i",
                str(raw_concat),
                "-af",
                "loudnorm=I=-9:TP=-1.0:LRA=7,highpass=f=30,alimiter=limit=0.94",
                "-ar",
                "44100",
                str(loud),
            ],
            check=True,
            capture_output=True,
        )
        src = loud
    except Exception as e:
        print("loudnorm fail", e)
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
    """Mute Mental/Atm grainy beds if present (+ known noisy tracks)."""
    morph.silence_noisy(by_full)
    for name, t in list(by_full.items()):
        low = name.lower()
        if any(k in low for k in ("mental", "atm", "grain", "atmosphere", "bed")):
            idx = t["index"]
            for row in range(8):
                send("stop_clip", {"track_index": idx, "clip_index": row})
                send("delete_clip", {"track_index": idx, "clip_index": row})
            # try mute if API supports
            send("set_track_mute", {"track_index": idx, "mute": True})
            print("silenced/muted bed", name, idx)


def main():
    errors = []
    print("=== MENTAL INDUSTRIAL classic 303 @", BPM, "N=", N, f"sec/scene={N/SR:.2f} ===")
    print("PARAMS osc=", OSC_KIND, "resQ=", RES_Q, "envAmt=", ENV_AMT, "grit=", GRIT)

    shots = ensure_industrial_oneshots()
    pattern = classic.classic_pattern(dna.SEED + 303)
    accents = sum(1 for p in pattern if p["accent"])
    slides = sum(1 for p in pattern if p["slide"])
    print("pattern accents", accents, "slides", slides)

    scene_paths = {}
    for sid, name in SCENES:
        scene_paths[sid] = render_scene_layers(sid, name, shots, pattern)

    print("=== Bounce MentalIndustrial MP3 ===")
    try:
        mp3_dur = bounce_mp3(scene_paths)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        mp3_dur = 0.0

    print("=== Ableton load + fire Full_Mental / Peak_Industrial ===")
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

    for row, _ in SCENES:
        for idx in (acid_midi_idx, acid_audio_idx, kick_idx, hats_idx, perc_idx, oh_idx, bass_idx):
            if idx is not None:
                safe_delete(idx, row)

    clip_len = float(BEATS)

    for sid, name in SCENES:
        paths = scene_paths[sid]
        if kick_idx is not None and morph.layer_has_signal(paths["kick"]):
            load_audio(kick_idx, sid, paths["kick"], f"{name}_kick")
        if hats_idx is not None and morph.layer_has_signal(paths["hats"]):
            load_audio(hats_idx, sid, paths["hats"], f"{name}_hats")
        if oh_idx is not None and morph.layer_has_signal(paths["oh"]):
            load_audio(oh_idx, sid, paths["oh"], f"{name}_oh")
        if perc_idx is not None and morph.layer_has_signal(paths["perc"]):
            load_audio(perc_idx, sid, paths["perc"], f"{name}_ind")
        if acid_audio_idx is not None and morph.layer_has_signal(paths["acid"]):
            load_audio(acid_audio_idx, sid, paths["acid"], f"{name}_classic303")
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

    print("ACID_PARAMS", {
        "osc": OSC_KIND, "resQ": RES_Q, "envAmt": ENV_AMT,
        "baseCut0": BASE_CUT0, "rollMax": ROLL_MAX, "grit": GRIT,
        "laser_character": "REMOVED",
    })
    print("FIRED", fire_name, fired)
    print("INDUSTRIAL_SAMPLES", shots["used"])
    print("HAT_SRC", shots["hat_src"])
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(mp3_dur, 2))
    print("IS_PLAYING", playing)
    print("ERRORS", errors)
    print("DONE build_mental_industrial_liveset")


if __name__ == "__main__":
    main()
