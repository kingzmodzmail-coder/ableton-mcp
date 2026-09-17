# -*- coding: utf-8 -*-
"""ESX-1 Valve Force Live @ 162 — hardware character from factory one-shots.

DNA:
- Valve Force master: soft even-order tube sat (asymmetric tanh / Tube Gain)
- One-shot drums: SinKick, HH, rim/snare, JunkPerc via CRISP esx-1 convert chain
- Stretch part: PercLP/SynLP rubberband time-stretch to tempo (no chipmunk)
- Filter motion: stepped LPF cutoff/res every few bars (motion seq feel)
- Mild Decimator on JunkPerc industrial only; light kick compress
- Classic saw 303 under kick (no Star Wars)
- 8 scenes x 24 bars (~4.74 min) Peak/Full fire
"""
from __future__ import annotations

import array
import json
import math
import random
import socket
import subprocess
import sys
import wave
from pathlib import Path

BRIDGE = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge")
sys.path.insert(0, str(BRIDGE))
import crisp_dna_to_ableton as dna  # noqa: E402
import build_classic_acid_liveset as classic  # noqa: E402
import build_liveset_15s_morphs as morph  # noqa: E402

# Prefer full ffmpeg path on this machine
_FF_FULL = r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
if Path(_FF_FULL).exists():
    dna.FFMPEG = _FF_FULL

SR = dna.SR
BPM = 162.0
BARS = 24  # ~35.6s/scene -> ~4.74 min total
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR)
HOST, PORT = "127.0.0.1", 9877

FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT = BRIDGE / "samples" / "crisp-dna" / "esx1-valveforce"
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"
ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_ESX1_ValveForce_Live_162.mp3")

SCENES = [
    (0, "Intro_Kick"),
    (1, "Hats_In"),
    (2, "Acid_Under"),
    (3, "Stretch_Roll"),
    (4, "Full_Groove"),
    (5, "Break_Filter"),
    (6, "Peak_Drive"),
    (7, "Outro_Valve"),
]
FIRE_ROW = 6  # Peak_Drive; Full_Groove=4 also loaded

# Classic saw 303 — musical, under kick
RES_Q = 0.14
BASE_CUT0 = 300.0
ENV_AMT = 2200.0
ROLL_MAX = 140.0
GRIT = 1.85
ENV_DECAY = 0.9970
OSC_KIND = "saw"
TUBE_GAIN = 2.15  # Valve Force Tube Gain feel

for mod in (dna, classic, morph):
    mod.BPM = BPM
    mod.BARS = BARS
    mod.BEATS = BEATS
    mod.N = N
classic.RES_Q = RES_Q
classic.BASE_CUT0 = BASE_CUT0
classic.ENV_AMT = ENV_AMT
classic.ROLL_MAX = ROLL_MAX
classic.GRIT = GRIT
classic.ENV_DECAY = ENV_DECAY
classic.OSC_KIND = OSC_KIND
classic.OUT = OUT
classic.SECTION_MIX_DIR = SECTION_MIX_DIR

STRETCH_METHOD = "ffmpeg rubberband (tempo only, pitch preserve)"
VALVE_METHOD = f"asymmetric tanh Tube Gain={TUBE_GAIN} + mild even harmonic bias + alimiter"


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
    print("OK midi", name)
    return True


def place(buf, sample, beat, gain=1.0):
    dna.place(buf, sample, beat, gain)


def write_mono(path: Path, samples, peak_target=0.90):
    peak = max(1e-9, max(abs(x) for x in samples))
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


def write_stereo_mix(path: Path, mono: list[float], peak_target=0.90):
    classic.write_stereo_mix(path, mono, peak_target=peak_target)


def electribe_master(src: Path, dst: Path):
    """CRISP ESX-1 convert chain."""
    dna.electribe_master(src, dst)


def read_wav(path: Path) -> list[float]:
    return dna.read_wav(path)


def valve_force(samples: list[float], tube_gain: float = TUBE_GAIN) -> list[float]:
    """Tube-like soft even-order sat — warm, not laser."""
    # Asymmetry biases even harmonics (classic tube character)
    bias = 0.045
    norm = math.tanh(tube_gain)
    out = [0.0] * len(samples)
    # gentle pre-emphasis into tubes
    for i, x in enumerate(samples):
        driven = (x + bias) * tube_gain
        y = math.tanh(driven) / norm - bias * 0.55
        # soft second-order blend
        y = 0.88 * y + 0.12 * math.tanh(x * (tube_gain * 0.65))
        out[i] = y
    return out


def mild_compress_kick(samples: list[float], thr=0.42, ratio=1.8) -> list[float]:
    out = [0.0] * len(samples)
    env = 0.0
    atk, rel = 0.003, 0.12
    atk_c = math.exp(-1.0 / (SR * atk))
    rel_c = math.exp(-1.0 / (SR * rel))
    for i, x in enumerate(samples):
        a = abs(x)
        env = a + (env - a) * (atk_c if a > env else rel_c)
        if env > thr:
            over = env - thr
            gain = thr + over / ratio
            g = gain / max(1e-9, env)
        else:
            g = 1.0
        out[i] = x * g * 1.06
    return out


def bitcrush_mild(samples: list[float], bits=10, rate_div=3) -> list[float]:
    """Mild Decimator — industrial part only."""
    levels = float(2 ** bits)
    out = [0.0] * len(samples)
    hold = 0.0
    for i, x in enumerate(samples):
        if i % rate_div == 0:
            q = math.floor(x * levels * 0.5 + 0.5) / (levels * 0.5)
            hold = q
        out[i] = hold * 0.92 + x * 0.08  # keep some clean
    return out


def one_pole_lpf(samples: list[float], cutoff_hz: float, res: float = 0.0) -> list[float]:
    """Simple resonant-ish LPF for stretch motion."""
    out = [0.0] * len(samples)
    # state-variable-ish light
    l = b = 0.0
    q = 0.05 + res * 0.25
    for i, x in enumerate(samples):
        f = 2 * math.sin(math.pi * dna.clamp(cutoff_hz / SR, 0.0001, 0.45))
        l += f * b
        h = x - l - q * b
        b += f * h
        out[i] = l
    return out


def apply_motion_filter(samples: list[float], sid: int) -> list[float]:
    """Stepped cutoff/res every 2-4 bars — ESX motion seq feel."""
    out = [0.0] * len(samples)
    samples_per_bar = int(4.0 * 60.0 / BPM * SR)
    # motion table: (cutoff, res) per 2-bar block
    tables = {
        0: [(400, 0.1)] * 12,
        1: [(500, 0.12), (600, 0.14)] * 6,
        2: [(700, 0.15), (900, 0.18), (800, 0.16), (1100, 0.2)] * 3,
        3: [(900, 0.22), (1400, 0.28), (700, 0.18), (1800, 0.32), (1000, 0.24), (2200, 0.35)] * 2,
        4: [(1200, 0.25), (1800, 0.3), (900, 0.2), (2400, 0.34), (1400, 0.26), (2000, 0.3)] * 2,
        5: [(600, 0.35), (400, 0.4), (900, 0.38), (300, 0.42), (1100, 0.36), (500, 0.4)] * 2,
        6: [(1600, 0.28), (2400, 0.34), (1200, 0.24), (2800, 0.38), (1800, 0.3), (2200, 0.32)] * 2,
        7: [(1000, 0.2), (700, 0.16), (500, 0.12), (400, 0.1)] * 3,
    }
    tab = tables.get(sid, tables[4])
    # process in 2-bar chunks
    chunk = samples_per_bar * 2
    for bi, start in enumerate(range(0, len(samples), chunk)):
        cut, res = tab[min(bi, len(tab) - 1)]
        end = min(len(samples), start + chunk)
        seg = samples[start:end]
        filt = one_pole_lpf(seg, cut, res)
        # wet/dry — keep body
        wet = 0.72 if sid >= 3 else 0.55
        for i, (a, b) in enumerate(zip(seg, filt)):
            out[start + i] = a * (1 - wet) + b * wet
    return out


def find_ffprobe() -> str:
    cands = [
        r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffprobe.exe",
        r"C:\ffmpeg\bin\ffprobe.exe",
        "ffprobe",
    ]
    ff = Path(dna.FFMPEG)
    if ff.name.lower().startswith("ffmpeg"):
        cands.insert(0, str(ff.with_name(ff.name.replace("ffmpeg", "ffprobe").replace("FFMPEG", "ffprobe"))))
        cands.insert(0, str(ff.parent / "ffprobe.exe"))
    for c in cands:
        try:
            subprocess.run([c, "-version"], capture_output=True, check=True)
            return c
        except Exception:
            continue
    raise RuntimeError("ffprobe not found")


def make_stretch_loop(src_name: str, bars: int = 2) -> list[float]:
    """Time-stretch factory loop to tempo without pitch change (ESX Stretch Part)."""
    src = FACTORY / src_name
    raw = ONESHOT / f"stretch_raw_{Path(src_name).stem}.wav"
    stretched = ONESHOT / f"stretch_{Path(src_name).stem}.wav"
    electribe_master(src, raw)

    # Target length = bars at BPM
    target_sec = bars * 4.0 * 60.0 / BPM
    # Probe duration
    ffprobe = find_ffprobe()
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(raw)],
        capture_output=True,
        text=True,
        check=True,
    )
    dur = float(probe.stdout.strip() or "1")
    tempo_ratio = dur / max(1e-6, target_sec)  # rubberband tempo>1 = faster/shorter

    # Prefer rubberband; fallback atempo chain
    ok_rb = False
    try:
        cmd = [
            dna.FFMPEG, "-y", "-i", str(raw),
            "-af", f"rubberband=tempo={tempo_ratio:.6f}:pitch=1.0:channels=1",
            "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", "-c:a", "pcm_s16le",
            str(stretched),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        ok_rb = True
        print("STRETCH rubberband", src_name, f"dur {dur:.3f}->{target_sec:.3f} tempo={tempo_ratio:.4f}")
    except Exception as e:
        print("rubberband fail, atempo fallback", e)
        # atempo only accepts 0.5..2.0 — chain
        ratio = tempo_ratio
        filters = []
        # atempo speeds up: need factor = dur/target = tempo_ratio
        while ratio > 2.0:
            filters.append("atempo=2.0")
            ratio /= 2.0
        while ratio < 0.5:
            filters.append("atempo=0.5")
            ratio /= 0.5
        filters.append(f"atempo={ratio:.6f}")
        af = ",".join(filters)
        cmd = [
            dna.FFMPEG, "-y", "-i", str(raw),
            "-af", af,
            "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", "-c:a", "pcm_s16le",
            str(stretched),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        global STRETCH_METHOD
        STRETCH_METHOD = "ffmpeg atempo chain (pitch-ish preserve via tempo only)"
        print("STRETCH atempo", src_name, af)

    samples = read_wav(stretched)
    # Trim/pad to exact target
    target_n = int(target_sec * SR)
    if len(samples) > target_n:
        samples = samples[:target_n]
    elif len(samples) < target_n:
        samples = samples + [0.0] * (target_n - len(samples))
    # Soft edges for seamless loop
    fade = int(0.008 * SR)
    for i in range(fade):
        g = i / fade
        samples[i] *= g
        samples[-(i + 1)] *= g
    write_mono(ONESHOT / "stretch_loop_ready.wav", samples, 0.88)
    if not ok_rb:
        pass
    return samples


def ensure_oneshots():
    mapping = {
        "146_SinKick.wav": "esx_SinKick.wav",
        "054_HH-1C.wav": "esx_HH1C.wav",
        "055_HH-1O.wav": "esx_HH1O.wav",
        "045_Rim-1.wav": "esx_Rim1.wav",
        "021_SD-1.wav": "esx_SD1.wav",
        "092_JunkPerc.wav": "esx_JunkPerc.wav",
        "095_SynPerc.wav": "esx_SynPerc.wav",
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

    # Kick: prefer SinKick with light tube + compress; layer tiny synth click
    kick = shots.get("esx_SinKick.wav") or dna.synth_kick_sledge(dna.mulberry32(0xE51), "full")
    kick = mild_compress_kick([dna.tanh_drive(x, 1.55) for x in kick])
    # short click layer from synth
    click = dna.synth_kick_sledge(dna.mulberry32(0xC11C), "full")
    click = click[: int(0.02 * SR)]

    hat_c = shots.get("esx_HH1C.wav") or dna.synth_hat(dna.mulberry32(1), False)
    hat_c = [dna.tanh_drive(x, 1.15) for x in hat_c]
    hat_o = shots.get("esx_HH1O.wav") or dna.synth_hat(dna.mulberry32(2), True)
    hat_o = [dna.tanh_drive(x, 1.1) for x in hat_o]
    rim = shots.get("esx_Rim1.wav") or shots.get("esx_SD1.wav")
    snare = shots.get("esx_SD1.wav")
    junk = shots.get("esx_JunkPerc.wav")
    if junk:
        junk = bitcrush_mild([dna.tanh_drive(x, 1.35) for x in junk], bits=10, rate_div=3)
    synp = shots.get("esx_SynPerc.wav")

    # Stretch: prefer SynLP then PercLP
    stretch_src = "189_SynLP-1.wav" if (FACTORY / "189_SynLP-1.wav").exists() else "175_PercLP-1.wav"
    stretch = make_stretch_loop(stretch_src, bars=2)
    used.append(f"STRETCH:{stretch_src}")

    write_mono(ONESHOT / "kick_ready.wav", kick, 0.92)
    write_mono(ONESHOT / "junk_crushed.wav", junk or [0.0], 0.80)

    return {
        "kick": kick,
        "click": click,
        "hat_c": hat_c,
        "hat_o": hat_o,
        "rim": rim,
        "snare": snare,
        "junk": junk,
        "synp": synp,
        "stretch": stretch,
        "stretch_src": stretch_src,
        "used": used,
    }


def quiet_midi_for_scene(pattern, sid, bars=BARS):
    notes = []
    gate = 0.14
    slide_dur = 0.30
    keep = {
        0: lambda st, bar: False,
        1: lambda st, bar: False,
        2: lambda st, bar: st % 4 == 0,
        3: lambda st, bar: st % 2 == 0,
        4: lambda st, bar: True,
        5: lambda st, bar: st % 2 == 0,
        6: lambda st, bar: True,
        7: lambda st, bar: st % 4 == 0 and bar < 8,
    }[sid]
    for bar in range(bars):
        base = bar * 4.0
        for st, p in enumerate(pattern):
            if p["midi"] <= 0 or not keep(st, bar):
                continue
            dur = slide_dur if p["slide"] else gate
            vel = 110 if p["accent"] else 88
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


def render_scene(sid, name, shots, pattern):
    kick = shots["kick"]
    click = shots["click"]
    hat_c = shots["hat_c"]
    hat_o = shots["hat_o"]
    rim = shots["rim"]
    snare = shots["snare"]
    junk = shots["junk"]
    synp = shots["synp"]
    stretch_one = shots["stretch"]

    trk_k = [0.0] * N
    trk_h = [0.0] * N
    trk_oh = [0.0] * N
    trk_p = [0.0] * N
    trk_st = [0.0] * N

    stretch_beats = 2 * 4.0  # 2 bars

    for bar in range(BARS):
        base = bar * 4.0

        # --- KICK 4/4 (ESX drum part) ---
        if sid == 5:  # break — sparse kick
            if bar % 4 == 0:
                place(trk_k, kick, base, 0.7)
                place(trk_k, click, base, 0.2)
        elif sid == 7:
            if bar < 12:
                for step in (0, 4, 8, 12):
                    g = 0.95 if bar < 6 else 0.7
                    place(trk_k, kick, base + step * 0.25, g)
                    place(trk_k, click, base + step * 0.25, 0.15)
            elif bar < 18:
                for step in (0, 8):
                    place(trk_k, kick, base + step * 0.25, 0.55)
        elif sid == 0:
            for step in (0, 4, 8, 12):
                place(trk_k, kick, base + step * 0.25, 0.9)
                place(trk_k, click, base + step * 0.25, 0.14)
        elif sid == 6:
            for step in (0, 4, 8, 12):
                place(trk_k, kick, base + step * 0.25, 1.12)
                place(trk_k, click, base + step * 0.25, 0.18)
            if bar >= 8:
                place(trk_k, kick, base + 1.5, 0.28)
        else:
            g = 1.0 if sid >= 3 else 0.92
            for step in (0, 4, 8, 12):
                place(trk_k, kick, base + step * 0.25, g)
                place(trk_k, click, base + step * 0.25, 0.14 * g)

        # --- HATS ---
        if sid == 0:
            pass
        elif sid == 1:
            for i, st in enumerate(range(0, 16, 2)):
                place(trk_h, hat_c, base + st * 0.25, 0.7 if i % 2 == 0 else 0.42)
        elif sid == 2:
            for i, st in enumerate(range(0, 16, 2)):
                place(trk_h, hat_c, base + st * 0.25, 0.72 if i % 2 == 0 else 0.46)
            for st in (6, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.34)
        elif sid in (3, 4):
            for st in range(16):
                swing = 0.011 if st % 2 else 0.0
                place(trk_h, hat_c, base + st * 0.25 + swing, 0.74 if st % 2 == 0 else 0.44)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.4 if sid == 4 else 0.34)
        elif sid == 5:
            for st in range(0, 16, 2):
                place(trk_h, hat_c, base + st * 0.25, 0.36)
            for st in (6, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.28)
        elif sid == 6:
            for st in range(16):
                swing = 0.009 if st % 2 else 0.0
                place(trk_h, hat_c, base + st * 0.25 + swing, 0.8 if st % 2 == 0 else 0.5)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.46)
        elif sid == 7 and bar < 8:
            for i, st in enumerate(range(0, 16, 2)):
                place(trk_h, hat_c, base + st * 0.25, 0.4 if i % 2 == 0 else 0.22)

        # --- ONE-SHOT perc: rim/snare/junk (controlled) ---
        if sid in (3, 4, 6):
            if rim is not None:
                place(trk_p, rim, base + 1.0, 0.55 if sid != 6 else 0.65)
                place(trk_p, rim, base + 3.0, 0.5)
            if snare is not None and sid >= 4:
                place(trk_p, snare, base + 1.0, 0.35)
            if junk is not None:
                # industrial short one-shots with motion — sparse
                if bar % 2 == 0:
                    place(trk_p, junk, base + 0.75, 0.42 if sid < 6 else 0.5)
                if sid == 6 and bar % 2 == 1:
                    place(trk_p, junk, base + 2.75, 0.38)
            if synp is not None and sid == 6 and bar % 4 == 0:
                place(trk_p, synp, base + 1.75, 0.32)
        elif sid == 5 and junk is not None and bar % 2 == 0:
            place(trk_p, junk, base + 2.75, 0.28)

        # --- STRETCH PART: loop every 2 bars (ESX Stretch workflow) ---
        if sid >= 3 and sid != 7:
            # trigger at start of even bars
            if bar % 2 == 0:
                g = {3: 0.55, 4: 0.62, 5: 0.72, 6: 0.58}.get(sid, 0.5)
                place(trk_st, stretch_one, base, g)
        elif sid == 7 and bar < 8 and bar % 2 == 0:
            place(trk_st, stretch_one, base, 0.4)

    # Acid classic saw under kick
    acid_drive = {0: 0.0, 1: 0.0, 2: 0.85, 3: 0.9, 4: 0.95, 5: 1.0, 6: 0.92, 7: 0.3}.get(sid, 0.85)
    acid_full = classic.render_classic_acid(pattern, grit=GRIT + (0.08 if sid == 6 else 0.0), roll=True)
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))

    # Stretch filter motion (motion seq)
    if any(abs(x) > 1e-6 for x in trk_st):
        trk_st = apply_motion_filter(trk_st, sid)
    # Also mild motion on acid for sid>=3
    if sid >= 3 and acid_drive > 0:
        acid = apply_motion_filter(acid, sid)

    # Light HP on hats for clean ESX
    # (already factory-mastered)

    prefix = f"s{sid}_{name}"
    paths = {
        "kick": OUT / f"{prefix}_kick.wav",
        "hats": OUT / f"{prefix}_hats.wav",
        "oh": OUT / f"{prefix}_oh.wav",
        "perc": OUT / f"{prefix}_perc.wav",
        "stretch": OUT / f"{prefix}_stretch.wav",
        "acid": OUT / f"{prefix}_acid.wav",
    }
    write_mono(paths["kick"], trk_k, 0.92)
    write_mono(paths["hats"], trk_h, 0.74)
    write_mono(paths["oh"], trk_oh, 0.7)
    write_mono(paths["perc"], trk_p, 0.58)
    write_mono(paths["stretch"], trk_st, 0.7)
    write_mono(paths["acid"], acid, 0.78)

    acid_g = {0: 0.0, 1: 0.0, 2: 0.42, 3: 0.44, 4: 0.46, 5: 0.5, 6: 0.45, 7: 0.22}.get(sid, 0.4)
    perc_g = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.8, 4: 0.88, 5: 0.7, 6: 0.95, 7: 0.4}.get(sid, 0.8)
    st_g = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.85, 4: 0.9, 5: 1.0, 6: 0.8, 7: 0.55}.get(sid, 0.8)
    kick_g = 0.55 if sid == 5 else 1.08
    hats_g = 0.82
    oh_g = 0.68

    mix = [0.0] * N
    for i in range(N):
        mix[i] = (
            trk_k[i] * kick_g
            + acid[i] * acid_g
            + trk_h[i] * hats_g
            + trk_oh[i] * oh_g
            + trk_p[i] * perc_g
            + trk_st[i] * st_g
        )

    # Valve Force on section mix
    mix = valve_force(mix, TUBE_GAIN)
    # soft peak normalize before write
    peak = max(1e-9, max(abs(x) for x in mix))
    if peak > 0.95:
        mix = [x * (0.92 / peak) for x in mix]

    mix_path = SECTION_MIX_DIR / f"{prefix}_mix.wav"
    write_stereo_mix(mix_path, mix, peak_target=0.90)
    paths["mix"] = mix_path
    print("scene", sid, name, "stretch_peak", round(max(abs(x) for x in trk_st), 4))
    return paths


def bounce_mp3(scene_paths):
    raw_concat = OUT / "_vf_concat.wav"
    # ffmpeg concat demuxer
    listfile = OUT / "_concat.txt"
    with open(listfile, "w", encoding="utf-8") as f:
        for sid, name in SCENES:
            p = str(scene_paths[sid]["mix"]).replace("\\", "/")
            f.write(f"file '{p}'\n")
    subprocess.run(
        [dna.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(raw_concat)],
        check=True,
        capture_output=True,
    )
    mastered = OUT / "_vf_master.wav"
    # Valve Force again lightly + glue + ESX-ish lim
    af = (
        f"asplit=2[m][s];"
        f"[s]asubboost=dry=0.5:wet=0.3:decay=0.0:feedback=0.0:cutoff=90:slope=0.5,"
        f"volume=0.35[sw];"
        f"[m][sw]amix=inputs=2:weights=1 0.25,"
        f"acompressor=threshold=-16dB:ratio=1.8:attack=10:release=160:makeup=1.5,"
        f"equalizer=f=280:t=q:w=0.8:g=-1.5,"
        f"equalizer=f=5500:t=q:w=0.9:g=1.2,"
        f"alimiter=limit=0.92,"
        f"loudnorm=I=-9.5:TP=-1.2:LRA=8"
    )
    # Simpler portable chain — Valve already baked; master polish
    af2 = (
        "acompressor=threshold=-16dB:ratio=1.8:attack=10:release=160:makeup=1.8,"
        "equalizer=f=280:t=q:w=0.8:g=-1.5,"
        "equalizer=f=5200:t=q:w=0.9:g=1.0,"
        "alimiter=limit=0.92,"
        "loudnorm=I=-9.5:TP=-1.2:LRA=8"
    )
    try:
        subprocess.run(
            [dna.FFMPEG, "-y", "-i", str(raw_concat), "-af", af2, str(mastered)],
            check=True,
            capture_output=True,
        )
        src = mastered
    except Exception as e:
        print("master polish fail", e)
        src = raw_concat
    subprocess.run(
        [dna.FFMPEG, "-y", "-i", str(src), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3)],
        check=True,
        capture_output=True,
    )
    dur = 8 * (N / SR)
    try:
        ffprobe = find_ffprobe()
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(MP3)],
            capture_output=True,
            text=True,
            check=True,
        )
        dur = float(probe.stdout.strip())
    except Exception:
        pass
    print("MP3", MP3, "dur", round(dur, 2))
    return dur


def silence_beds(by_full):
    try:
        morph.silence_noisy(by_full)
    except Exception as e:
        print("silence_noisy", e)
    for name, t in list(by_full.items()):
        low = name.lower()
        if any(k in low for k in ("mental", "atm", "grain", "atmosphere", "crisp_e2e", "es1", "drumlp", "tholin")):
            idx = t["index"]
            for row in range(8):
                send("stop_clip", {"track_index": idx, "clip_index": row})
                send("delete_clip", {"track_index": idx, "clip_index": row})
            send("set_track_mute", {"track_index": idx, "mute": True})
            print("muted bed", name)


def try_saturator(track_idx):
    if track_idx is None:
        return []
    loaded = []
    for uri, label in [
        ("query:Audio Effects#Saturator", "Saturator"),
        ("query:Audio Effects#Compressor", "Compressor"),
    ]:
        r = send("load_browser_item", {"track_index": track_idx, "item_uri": uri})
        print("FX try", label, r.get("status"), r.get("message", r.get("result")))
        if r.get("status") == "success":
            loaded.append(label)
    return loaded


def main():
    errors = []
    print("=== ESX-1 Valve Force Live @", BPM, "bars/scene", BARS, f"sec/scene={N/SR:.2f} ===")
    print("VALVE", VALVE_METHOD)
    print("STRETCH_METHOD_PLANNED", STRETCH_METHOD)

    shots = ensure_oneshots()
    print("ONESHOTS", shots["used"])
    print("STRETCH_SRC", shots["stretch_src"], "METHOD", STRETCH_METHOD)

    pattern = classic.classic_pattern(dna.SEED + 0xE51)
    scene_paths = {}
    for sid, name in SCENES:
        scene_paths[sid] = render_scene(sid, name, shots, pattern)

    print("=== Bounce MP3 ===")
    try:
        mp3_dur = bounce_mp3(scene_paths)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        mp3_dur = 0.0

    print("=== Ableton load ===")
    snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=60)
    snap = ok(snap_r, "snapshot")
    if not snap:
        print("ABORT no Ableton — MP3 still written")
        print("MP3_PATH", str(MP3))
        print("MP3_DURATION_SEC", round(mp3_dur, 2))
        print("VALVE_FORCE", VALVE_METHOD)
        print("STRETCH_METHOD", STRETCH_METHOD)
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
    silence_beds(by_full)

    acid_midi_idx = by.get("Acid 303 Poly")
    acid_audio_idx = by.get("Acid 303") or by.get("E-Syn")
    kick_idx = by.get("E-Kick")
    hats_idx = by.get("E-Hats")
    perc_idx = by.get("E-Perc")
    oh_idx = by.get("E-OHat") or by.get("E-Snare")
    stretch_idx = by.get("E-Bass") or by.get("ESX Jam") or by.get("E2S Jam")
    jam_idx = by.get("ESX Jam") or by.get("E2S Jam")

    if acid_audio_idx is not None:
        send("set_track_name", {"track_index": acid_audio_idx, "name": "Acid 303"})

    if stretch_idx is not None and stretch_idx not in (kick_idx, hats_idx, perc_idx, oh_idx, acid_audio_idx):
        send("set_track_name", {"track_index": stretch_idx, "name": "ESX Stretch"})
        by["ESX Stretch"] = stretch_idx

    if acid_midi_idx is not None:
        r = send("load_browser_item", {"track_index": acid_midi_idx, "item_uri": "query:Synths#Drift"})
        print("Drift", r.get("status"))

    fx_loaded = try_saturator(kick_idx)
    # Also try Saturator on jam/master-ish track
    if jam_idx is not None:
        fx_loaded += try_saturator(jam_idx)
    print("ABLETON_FX", fx_loaded)

    for row, _ in SCENES:
        for idx in (acid_midi_idx, acid_audio_idx, kick_idx, hats_idx, perc_idx, oh_idx, stretch_idx):
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
            load_audio(perc_idx, sid, paths["perc"], f"{name}_junk")
        if stretch_idx is not None and morph.layer_has_signal(paths["stretch"]):
            load_audio(stretch_idx, sid, paths["stretch"], f"{name}_stretch")
        if acid_audio_idx is not None and morph.layer_has_signal(paths["acid"]):
            load_audio(acid_audio_idx, sid, paths["acid"], f"{name}_saw303")
        midi = quiet_midi_for_scene(pattern, sid, bars=BARS)
        if acid_midi_idx is not None and midi:
            put_midi(acid_midi_idx, sid, clip_len, f"{name}_drift", midi)
        # Also put section mix on jam for quick listen row
        if jam_idx is not None and jam_idx != stretch_idx:
            load_audio(jam_idx, sid, paths["mix"], f"{name}_VF_mix")
        send("create_locator", {"name": f"{sid}_{name}", "time": float(sid * clip_len)})

    # Fire Peak_Drive (6) and also ensure Full_Groove layers ready
    print("=== Fire Peak_Drive row", FIRE_ROW, "+ start ===")
    fired = []
    for label, idx, key in [
        ("kick", kick_idx, "kick"),
        ("hats", hats_idx, "hats"),
        ("oh", oh_idx, "oh"),
        ("perc", perc_idx, "perc"),
        ("stretch", stretch_idx, "stretch"),
        ("acid_audio", acid_audio_idx, "acid"),
        ("acid_midi", acid_midi_idx, None),
        ("jam_mix", jam_idx if jam_idx != stretch_idx else None, "mix"),
    ]:
        if idx is None:
            continue
        if key and key != "mix" and not morph.layer_has_signal(scene_paths[FIRE_ROW].get(key, scene_paths[FIRE_ROW]["kick"])):
            # stretch/perc may be empty on some — check path
            p = scene_paths[FIRE_ROW].get(key)
            if p is None or not morph.layer_has_signal(p):
                continue
        if label == "acid_midi" and not quiet_midi_for_scene(pattern, FIRE_ROW, bars=BARS):
            continue
        r = send("fire_clip", {"track_index": idx, "clip_index": FIRE_ROW})
        if r.get("status") == "success":
            fired.append(label)
            print("FIRE", label)
        else:
            print("fire fail", label, r)

    # Also fire Full_Groove mix on a second listen if Peak jam failed — already Peak
    ok(send("start_playback"), "start_playback")
    info = send("get_session_info")
    res = info.get("result") or info
    playing = res.get("is_playing")
    tempo = res.get("tempo")
    print("tempo", tempo, "is_playing", playing)

    # If jam got both Peak stems AND mix, mute jam to avoid double — prefer stems
    if jam_idx is not None and jam_idx != stretch_idx and "jam_mix" in fired and len(fired) > 3:
        send("stop_clip", {"track_index": jam_idx, "clip_index": FIRE_ROW})
        print("stopped jam mix to avoid double with stems")
        fired = [f for f in fired if f != "jam_mix"]

    print("VALVE_FORCE", VALVE_METHOD)
    print("STRETCH_METHOD", STRETCH_METHOD)
    print("STRETCH_SRC", shots["stretch_src"])
    print("ONESHOTS", shots["used"])
    print("FIRED", "Peak_Drive", fired)
    print("SCENES", [n for _, n in SCENES])
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(mp3_dur, 2))
    print("IS_PLAYING", playing)
    print("TEMPO", tempo)
    print("ERRORS", errors)
    print("DONE build_esx1_valveforce_live")


if __name__ == "__main__":
    main()
