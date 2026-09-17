# -*- coding: utf-8 -*-
"""CueCurrent_167 v4 — CLEAN kit_v3 only, sub+kick dominant, mute acid mirror.
Follows ARRANGEMENT.md @167 G#m ~288 bars. Never loads poisoned kit_v1 / esx-unpack.
"""
from __future__ import annotations

import json
import math
import shutil
import socket
import subprocess
import wave
from pathlib import Path

import numpy as np

# --- paths: box-first; PC override via CUE167_V4_ROOT ---
BOX_KIT = Path("/workspace/exports/CueCurrent_167_kit_v3")
BOX_OUT = Path("/workspace/exports/_cue167_v4_build")
PC_BRIDGE = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge")
PC_KIT = PC_BRIDGE / "samples" / "cue167_kit_v3"
PC_OUT = PC_BRIDGE / "samples" / "cue167_v4"

def _paths():
    if PC_KIT.exists() and (PC_KIT / "kick_a.wav").exists():
        return PC_KIT, PC_OUT, True
    return BOX_KIT, BOX_OUT, False

KIT, OUT, ON_PC = _paths()
SEC = OUT / "sections"
SEC.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

MP3_NAME = "EvAIx_CueCurrent_167_v4.mp3"
WAV_NAME = "EvAIx_CueCurrent_167_v4.wav"
if ON_PC:
    MP3_DL = Path(r"C:\Users\Gebruiker\Downloads") / MP3_NAME
    WAV_DL = Path(r"C:\Users\Gebruiker\Downloads") / WAV_NAME
    NOTES_DL = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_CueCurrent_167_v4_NOTES.md")
    MAP_DL = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_CueCurrent_167_v4_ABLETON_MAP.md")
    ALS_NOTE = Path(r"C:\Users\Gebruiker\Documents\Ableton\CueCurrent_167_v4_SESSION.txt")
else:
    MP3_DL = Path("/workspace/exports") / MP3_NAME
    WAV_DL = Path("/workspace/exports") / WAV_NAME
    NOTES_DL = Path("/workspace/exports/EvAIx_CueCurrent_167_v4_NOTES.md")
    MAP_DL = Path("/workspace/exports/EvAIx_CueCurrent_167_v4_ABLETON_MAP.md")
    ALS_NOTE = NOTES_DL

BPM = 167.0
SR = 44100
HOST, PORT = "127.0.0.1", 9877

GSM_MIDI = [32, 35, 37, 39, 42, 44, 47, 49]
GSM_HZ = [440.0 * (2 ** ((m - 69) / 12.0)) for m in GSM_MIDI]

SECTIONS = [
    ("Intro", 64, 0),
    ("Build", 32, 1),
    ("Drop", 64, 2),
    ("Break", 32, 3),
    ("Drop2", 64, 4),
    ("Outro", 32, 5),
]
LOOP_BARS = 16


def send(cmd, params=None, timeout=120.0):
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


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getparams()[:4]
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError(f"bad width {sw} {path}")
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch == 2:
        data = data.reshape(-1, 2).mean(axis=1)
    elif ch > 2:
        data = data.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        x = np.linspace(0, 1, num=len(data), endpoint=False)
        new_len = max(1, int(len(data) * SR / sr))
        xi = np.linspace(0, 1, num=new_len, endpoint=False)
        data = np.interp(xi, x, data).astype(np.float32)
    return data


def write_wav_stereo(path: Path, mono: np.ndarray, peak=0.90):
    mono = np.asarray(mono, dtype=np.float32)
    m = float(np.max(np.abs(mono))) or 1.0
    mono = mono / m * peak
    stereo = np.column_stack([mono, mono])
    pcm = (np.clip(stereo, -1, 1) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def write_wav_mono(path: Path, mono: np.ndarray, peak=0.90):
    mono = np.asarray(mono, dtype=np.float32)
    m = float(np.max(np.abs(mono))) or 1.0
    mono = mono / m * peak
    pcm = (np.clip(mono, -1, 1) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def place(buf: np.ndarray, sample: np.ndarray, beat: float, gain: float = 1.0):
    start = int(beat * (60.0 / BPM) * SR)
    end = min(len(buf), start + len(sample))
    n = end - start
    if n <= 0:
        return
    buf[start:end] += sample[:n] * gain


def beats_for_bars(bars: int) -> float:
    return float(bars * 4)


def n_for_bars(bars: int) -> int:
    return int(beats_for_bars(bars) * (60.0 / BPM) * SR)


def hpf_inplace(buf: np.ndarray, cutoff_hz: float):
    if cutoff_hz <= 20:
        return buf
    x = buf.copy()
    rc = 1.0 / (2 * math.pi * cutoff_hz)
    dt = 1.0 / SR
    a = rc / (rc + dt)
    y = 0.0
    prev = 0.0
    for i in range(len(x)):
        y = a * (y + x[i] - prev)
        prev = x[i]
        x[i] = y
    return x


def lpf_inplace(buf: np.ndarray, cutoff_hz: float):
    """1-pole LPF — keep master dark / sub-heavy."""
    x = np.asarray(buf, dtype=np.float32).copy()
    if cutoff_hz >= SR * 0.45:
        return x
    rc = 1.0 / (2 * math.pi * cutoff_hz)
    dt = 1.0 / SR
    a = dt / (rc + dt)
    y = 0.0
    for i in range(len(x)):
        y += a * (x[i] - y)
        x[i] = y
    return x


def tanh_drive(x: np.ndarray, amt: float) -> np.ndarray:
    return np.tanh(x * amt).astype(np.float32)


def acid_pattern_gsm(seed: int, denser: bool = False):
    rng = np.random.default_rng(seed)
    steps = []
    prev = 0
    rest_p = 0.18 if denser else 0.32
    for i in range(16):
        if rng.random() < (0.40 if i % 4 == 1 else rest_p):
            steps.append({"midi": 0, "hz": 0.0, "accent": False, "slide": False})
            continue
        idx = int(rng.integers(0, len(GSM_MIDI)))
        if rng.random() < 0.45:
            idx = 0 if rng.random() < 0.65 else 4
        midi = int(GSM_MIDI[idx])
        accent = bool(rng.random() < 0.28 or i % 4 == 0)
        slide = bool(prev > 0 and rng.random() < 0.18)
        steps.append({"midi": midi, "hz": GSM_HZ[idx], "accent": accent, "slide": slide})
        prev = midi
    return steps


def render_acid(bars: int, pattern, *, whisper=False, open_=False, grit=1.6) -> np.ndarray:
    """Dark acid — Noise LOW (none), filter NOT wide open. Max cut ~1.8–2.2k."""
    N = n_for_bars(bars)
    out = np.zeros(N, dtype=np.float32)
    step_n = max(1, int((60.0 / BPM) / 4.0 * SR))
    total_steps = bars * 16
    l = b = 0.0
    phase = 0.0
    cur_hz = GSM_HZ[0]
    target_hz = cur_hz
    env = 0.0
    # CLOSED filter doctrine (v3): whisper/base/open all darker than v2
    res_q = 0.06 if whisper else (0.11 if open_ else 0.09)
    base_cut = 140.0 if whisper else (260.0 if open_ else 200.0)
    env_amt = 600.0 if whisper else (1600.0 if open_ else 1100.0)
    env_decay = 0.9996 if whisper else 0.99925
    amp = 0.12 if whisper else 0.22
    cut_max = 1600.0 if whisper else (2200.0 if open_ else 1800.0)
    pos = 0
    for s in range(total_steps):
        st = s % 16
        p = pattern[st]
        if p["hz"] > 0:
            target_hz = p["hz"]
            if not p["slide"]:
                cur_hz = target_hz
            env = 1.0 if p["accent"] else 0.48
        elif not p["slide"]:
            env *= 0.28
        n = min(step_n, N - pos)
        if n <= 0:
            break
        slide = bool(p.get("slide"))
        for i in range(n):
            if slide:
                cur_hz += (target_hz - cur_hz) * 0.0015
            else:
                cur_hz += (target_hz - cur_hz) * 0.45
            env *= env_decay
            phase += cur_hz / SR
            if phase >= 1.0:
                phase -= math.floor(phase)
            saw = 2.0 * phase - 1.0
            sq = 1.0 if phase < 0.5 else -1.0
            # NO noise osc — Noise LOW
            osc = (0.70 * saw + 0.30 * sq) * env * amp
            cut = base_cut + env * env_amt
            cut = max(100.0, min(cut_max, cut))
            f = 2 * math.sin(math.pi * min(0.45, max(0.0001, cut / SR)))
            l += f * b
            h = osc - l - res_q * b
            b += f * h
            out[pos + i] = math.tanh(l * grit)
        pos += n
    out = hpf_inplace(out, 180.0 if not whisper else 240.0)
    out = lpf_inplace(out, cut_max)
    return out.astype(np.float32)


def make_acid_midi(pattern, bars=16, denser=False):
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        for st, p in enumerate(pattern):
            if p["midi"] <= 0:
                continue
            dur = 0.50 if p["slide"] else 0.16
            if denser and st % 2 == 0:
                dur = max(dur, 0.20)
            vel = 110 if p["accent"] else 78
            notes.append({
                "pitch": int(p["midi"]),
                "start_time": base + st * 0.25,
                "duration": dur,
                "velocity": min(127, vel),
                "mute": False,
            })
    return notes



def make_drum_midi(section: str, bars=16):
    """MIDI mirror — kick + tribal (conga/claves/synperc pad map)."""
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        # Kick
        if section == "Intro":
            for b in (0, 1, 2, 3):
                notes.append({"pitch": 36, "start_time": base + b, "duration": 0.2, "velocity": 90 + bar // 4, "mute": False})
        elif section == "Break":
            if bar >= bars - 4:
                for b in (0, 1, 2, 3):
                    notes.append({"pitch": 36, "start_time": base + b, "duration": 0.2, "velocity": 110, "mute": False})
            elif bar % 2 == 0 and bar >= 8:
                notes.append({"pitch": 36, "start_time": base, "duration": 0.2, "velocity": 70, "mute": False})
        elif section == "Outro":
            for b in (0, 1, 2, 3):
                notes.append({"pitch": 36, "start_time": base + b, "duration": 0.2, "velocity": max(40, 110 - bar * 3), "mute": False})
        else:
            for b in (0, 1, 2, 3):
                notes.append({"pitch": 36, "start_time": base + b, "duration": 0.2, "velocity": 118 if b == 0 else 108, "mute": False})
            if section in ("Drop", "Drop2"):
                notes.append({"pitch": 37, "start_time": base + 0.0, "duration": 0.25, "velocity": 85, "mute": False})
                if bar % 2 == 1:
                    notes.append({"pitch": 36, "start_time": base + 2.5, "duration": 0.15, "velocity": 95, "mute": False})

        # Snare/clap
        if section in ("Build", "Drop", "Drop2"):
            notes.append({"pitch": 38, "start_time": base + 1, "duration": 0.18, "velocity": 100, "mute": False})
            notes.append({"pitch": 38, "start_time": base + 3, "duration": 0.18, "velocity": 100, "mute": False})
            if section != "Build":
                notes.append({"pitch": 39, "start_time": base + 3, "duration": 0.12, "velocity": 55, "mute": False})

        # Hats
        if section == "Intro":
            for st in range(0, 16, 2):
                notes.append({"pitch": 42, "start_time": base + st * 0.25, "duration": 0.08, "velocity": 38, "mute": False})
        elif section == "Build":
            dens = 1 if bar < bars - 8 else (1 if bar < bars - 4 else 1)
            step = 2 if bar < bars - 8 else (1 if bar >= bars - 4 else 2)
            # denser last 4 bars
            step = 1 if bar >= bars - 4 else 2
            for st in range(0, 16, step):
                vel = 55 if st % 2 == 0 else 40
                notes.append({"pitch": 42, "start_time": base + st * 0.25, "duration": 0.07, "velocity": vel, "mute": False})
            if bar >= bars - 4 and bar % 2 == 1:
                notes.append({"pitch": 46, "start_time": base + 3.5, "duration": 0.25, "velocity": 60, "mute": False})
        elif section in ("Drop", "Drop2"):
            for st in range(16):
                vel = 62 if st % 2 == 0 else 38
                notes.append({"pitch": 42, "start_time": base + st * 0.25, "duration": 0.07, "velocity": vel, "mute": False})
            if section == "Drop2" and (bar % 2 == 1 or bar % 4 == 3):
                notes.append({"pitch": 46, "start_time": base + 3.5, "duration": 0.3, "velocity": 78, "mute": False})
            elif bar % 4 == 3:
                notes.append({"pitch": 46, "start_time": base + 3.5, "duration": 0.3, "velocity": 70, "mute": False})
        elif section == "Outro":
            if bar < bars // 2:
                for st in range(0, 16, 2):
                    notes.append({"pitch": 42, "start_time": base + st * 0.25, "duration": 0.08, "velocity": 40, "mute": False})

        # TEKNO TRIBAL MIDI — perc_a=41 conga, perc_b=43 claves, perc_c=45 synperc
        tribal = tribal_hits(section, bar, bars)
        for beat, kind, vel in tribal:
            pitch = {"a": 41, "b": 43, "c": 45}[kind]
            notes.append({"pitch": pitch, "start_time": base + beat, "duration": 0.06, "velocity": int(vel), "mute": False})
    return notes


def tribal_hits(section: str, bar: int, bars: int):
    """Rolling free-party tekno-tribal (conga/claves/synperc). Returns list of (beat, kind, vel).
    Not plinky EDM fills — continuous roll locked to kick grid.
    """
    hits = []
    # Conga roll skeleton (offbeat polyrhythm against 4/4)
    conga_base = [0.75, 1.5, 2.25, 2.75, 3.5]
    claves_base = [0.5, 1.25, 2.0, 3.25, 3.75]
    # Variation by bar phase
    phase = bar % 8

    if section == "Intro":
        # NO full tribal — only sparse ticks late
        if bar >= bars // 2 and bar % 4 == 0:
            hits.append((0.75, "a", 40))
        return hits

    if section == "Build":
        # peeking tribal — sparse early, denser late
        g = 0.35 + 0.55 * (bar / max(1, bars - 1))
        for t in conga_base[::2]:
            hits.append((t, "a", int(48 * g + 20)))
        if bar >= bars // 2:
            for t in claves_base[::2]:
                hits.append((t, "b", int(42 * g + 18)))
        if bar >= bars - 8 and phase == 7:
            for t in (2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75):
                hits.append((t, "c", 55))
        return hits

    if section == "Break":
        # tribal/conga FOCUS — denser, kick subtracted in audio
        for t in conga_base:
            hits.append((t, "a", 78 if t in (0.75, 2.75) else 62))
        # extra conga ghost
        hits.append((1.75, "a", 50))
        hits.append((3.0, "a", 55))
        for t in claves_base:
            hits.append((t, "b", 58 if t in (0.5, 2.0) else 45))
        if phase in (3, 7):
            for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                hits.append((2.0 + t, "c", 60))
        return hits

    if section in ("Drop", "Drop2"):
        # FULL tribal locked
        for t in conga_base:
            vel = 72 if t in (0.75, 2.75) else 58
            if section == "Drop2":
                vel = min(95, vel + 8)
            hits.append((t, "a", vel))
        # rolling 16th conga ghost every other bar
        if bar % 2 == 1:
            hits.append((1.0, "a", 45))
            hits.append((3.25, "a", 48))
        for t in claves_base:
            hits.append((t, "b", 52 if section == "Drop" else 60))
        # perc_c accents
        if section == "Drop2":
            hits.append((1.75, "c", 68))
            if bar % 2 == 0:
                hits.append((3.5, "c", 70))
            if phase == 7:
                for t in (2.0, 2.125, 2.25, 2.375, 2.5, 2.625, 2.75, 2.875, 3.0, 3.125, 3.25, 3.375, 3.5, 3.625, 3.75, 3.875):
                    hits.append((t, "c", 55))
        else:
            if bar % 4 == 2:
                hits.append((2.5, "c", 55))
            if phase == 7:
                for t in (2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75):
                    hits.append((t, "b" if int(t * 4) % 2 == 0 else "c", 58))
        return hits

    if section == "Outro":
        fade = 1.0 - bar / max(1, bars - 1)
        if fade > 0.35:
            for t in conga_base[::2]:
                hits.append((t, "a", int(50 * fade)))
            if fade > 0.55:
                hits.append((0.5, "b", int(40 * fade)))
        return hits
    return hits


def render_drums(section: str, bars: int, kit: dict):
    """Full-length section drums — audible form + tekno tribal. Kick weight kept."""
    N = n_for_bars(bars)
    kick = np.zeros(N, dtype=np.float32)
    snare = np.zeros(N, dtype=np.float32)
    hats = np.zeros(N, dtype=np.float32)
    perc = np.zeros(N, dtype=np.float32)
    hits = 0
    ka, kb = kit["kick_a"], kit["kick_b"]
    sn, cl = kit["snare_a"], kit["clap_a"]
    hc, ho = kit["hat_closed"], kit["hat_open"]
    pa, pb, pc = kit["perc_a"], kit["perc_b"], kit["perc_c"]
    ba = kit.get("bass_a")

    for bar in range(bars):
        base = bar * 4.0
        prog = bar / max(1, bars - 1)

        # ---- KICK (keep weight; do NOT thin low end) ----
        if section == "Intro":
            # filtered/subtracted kick roll — body grows
            g = 0.50 + 0.55 * prog
            for b in (0, 1, 2, 3):
                place(kick, ka, base + b, g)
                hits += 1
            if bar >= bars // 3:
                place(kick, ka, base + 1.5, 0.28 * prog)
                hits += 1
            if bar >= bars // 2 and ba is not None and bar % 4 == 0:
                place(kick, ba[: int(0.30 * SR)], base, 0.28 * prog)
        elif section == "Break":
            # subtract / half — space for tribal
            if bar < 8:
                pass  # kick out
            elif bar < bars - 8:
                if bar % 2 == 0:
                    place(kick, ka, base, 0.55)
                    place(kick, ka, base + 2, 0.40)
                    hits += 2
            else:
                for b in (0, 1, 2, 3):
                    place(kick, ka, base + b, 0.95)
                    hits += 1
        elif section == "Outro":
            fade = 1.0 - 0.75 * prog
            for b in (0, 1, 2, 3):
                place(kick, ka, base + b, 0.95 * fade)
                hits += 1
            if bar < bars // 3:
                place(kick, kb, base, 0.42 * fade)
                hits += 1
        else:
            # Build / Drop / Drop2 — FULL kick_a/b weight
            for b in (0, 1, 2, 3):
                place(kick, ka, base + b, 1.05)
                hits += 1
            if section == "Build":
                place(kick, kb, base, 0.38)
                place(kick, ka, base + 2.5, 0.34)
                hits += 2
                if ba is not None and bar % 2 == 0:
                    place(kick, ba[: int(0.28 * SR)], base, 0.32)
            elif section == "Drop":
                place(kick, kb, base, 0.58)
                hits += 1
                if ba is not None:
                    place(kick, ba[: int(0.28 * SR)], base, 0.48)
                place(kick, ka, base + 1.5, 0.44)
                place(kick, ka, base + 3.5, 0.40)
                hits += 2
                if bar % 2 == 1:
                    place(kick, ka, base + 2.25, 0.36)
                    hits += 1
            elif section == "Drop2":
                place(kick, kb, base, 0.72)
                hits += 1
                if ba is not None:
                    place(kick, ba[: int(0.30 * SR)], base, 0.52)
                place(kick, ka, base + 1.5, 0.48)
                place(kick, ka, base + 3.5, 0.44)
                hits += 2
                place(kick, ka, base + 2.25, 0.38)
                hits += 1
                if bar % 2 == 1:
                    place(kick, kb, base + 2, 0.35)
                    hits += 1

        # ---- SNARE / CLAP ----
        if section in ("Build", "Drop", "Drop2"):
            place(snare, sn, base + 1, 0.72)
            place(snare, sn, base + 3, 0.72)
            hits += 2
            if section == "Build":
                place(snare, cl, base + 3, 0.12 + 0.10 * prog)
                hits += 1
                if bar >= bars - 4:
                    place(snare, cl, base + 1.75, 0.18)
                    hits += 1
            else:
                place(snare, cl, base + 3, 0.24)
                hits += 1
                if bar % 4 == 3:
                    place(snare, sn, base + 3.5, 0.34)
                    hits += 1
                if section == "Drop2" and bar % 2 == 1:
                    place(snare, cl, base + 1.5, 0.14)
                    hits += 1
        if section == "Break" and bar in (4, 12, 20, 28):
            place(snare, sn[::-1] if len(sn) > 10 else sn, base + 2, 0.20)
            hits += 1

        # ---- HATS ----
        if section == "Intro":
            # sparse hats — no full tribal yet
            for st in range(0, 16, 2):
                place(hats, hc, base + st * 0.25, 0.16)
                hits += 1
        elif section == "Build":
            # denser last bars (Hermes v4 brief)
            step = 2 if bar < bars - 4 else 1
            for st in range(0, 16, step):
                g = 0.22 if st % 2 == 0 else 0.12
                if bar >= bars - 4:
                    g *= 1.35
                place(hats, hc, base + st * 0.25, g)
                hits += 1
            if bar >= bars - 4 and bar % 2 == 1:
                place(hats, ho, base + 3.5, 0.26)
                hits += 1
        elif section == "Break":
            # mostly off — tribal owns mid
            if bar % 4 == 3:
                place(hats, hc, base + 3.5, 0.12)
                hits += 1
        elif section == "Outro":
            if bar < bars * 2 // 3:
                for st in range(0, 16, 2):
                    place(hats, hc, base + st * 0.25, 0.18 * (1 - prog))
                    hits += 1
        else:
            # Drop / Drop2 rolling 16ths
            for st in range(16):
                g = 0.30 if st % 2 == 0 else 0.15
                place(hats, hc, base + st * 0.25, g)
                hits += 1
            if section == "Drop2":
                if bar % 2 == 1 or bar % 4 == 3:
                    place(hats, ho, base + 3.5, 0.34)
                    hits += 1
            elif bar % 4 == 3:
                place(hats, ho, base + 3.5, 0.28)
                hits += 1

        # ---- TEKNO TRIBAL (perc_a conga / perc_b claves / perc_c synperc) ----
        tribal = tribal_hits(section, bar, bars)
        samp = {"a": pa, "b": pb, "c": pc}
        # section gain for tribal (audible in Drop/Break; peek Build; none Intro)
        tg = {
            "Intro": 0.55,
            "Build": 0.70,
            "Drop": 0.95,
            "Break": 1.15,
            "Drop2": 1.05,
            "Outro": 0.60,
        }[section]
        for beat, kind, vel in tribal:
            g = (vel / 100.0) * tg * 0.55
            place(perc, samp[kind], base + beat, g)
            hits += 1

    if section == "Intro":
        # stronger filtered/subtracted feel early — keep sub body (blend)
        kick_f = hpf_inplace(kick, 70.0)
        fade = np.linspace(0.55, 0.15, N, dtype=np.float32)  # more HPF early
        kick = kick_f * fade + kick * (1.0 - fade)
    return kick, snare, hats, perc, hits

def tile_buf(src: np.ndarray, bars_src: int, bars_dst: int) -> np.ndarray:
    if bars_dst == bars_src:
        return src.copy()
    n_dst = n_for_bars(bars_dst)
    out = np.zeros(n_dst, dtype=np.float32)
    n_src = len(src)
    pos = 0
    while pos < n_dst:
        n = min(n_src, n_dst - pos)
        out[pos:pos + n] = src[:n]
        pos += n_src
    return out



def render_section_mix(section: str, bars: int, kit: dict, pattern, acid_g: float, whisper=False, open_=False):
    """Render FULL section length (no identical 16-bar tile) so form is audible."""
    kick, snare, hats, perc, hits = render_drums(section, bars, kit)
    # acid: render in 16-bar chunks with slight seed drift so it supports without washing
    acid = np.zeros(n_for_bars(bars), dtype=np.float32)
    pos = 0
    chunk = LOOP_BARS
    for i in range(0, bars, chunk):
        b = min(chunk, bars - i)
        a = render_acid(b, pattern, whisper=whisper, open_=open_, grit=1.5 if whisper else 1.7)
        # mild sidechain duck to kick envelope (simple)
        acid[pos:pos + len(a)] = a
        pos += len(a)
    N = n_for_bars(bars)
    if section == "Intro":
        env = np.linspace(0.55, 1.0, N, dtype=np.float32)
        kick *= env
        acid *= np.linspace(0.20, 0.65, N, dtype=np.float32)
        perc *= np.linspace(0.3, 0.8, N, dtype=np.float32)
    elif section == "Outro":
        env = np.linspace(1.0, 0.18, N, dtype=np.float32)
        kick *= env
        snare *= env
        hats *= env
        perc *= env * np.linspace(1.0, 0.05, N, dtype=np.float32)
        acid *= env
    elif section == "Break":
        # keep tribal up; kick already subtracted in render_drums
        half = N // 2
        hats[:half] *= 0.10
        acid[:half] *= 0.7
        perc *= 1.15  # tribal focus
    elif section == "Build":
        # tribal peeks in
        perc *= np.linspace(0.45, 1.0, N, dtype=np.float32)
        hats *= np.linspace(0.7, 1.15, N, dtype=np.float32)

    # KICK-DOMINANT mix — tribal audible but not washing kick
    kick_g = {"Intro": 1.28, "Build": 1.38, "Drop": 1.48, "Break": 1.10, "Drop2": 1.55, "Outro": 1.22}[section]
    perc_g = {"Intro": 0.18, "Build": 0.32, "Drop": 0.42, "Break": 0.55, "Drop2": 0.48, "Outro": 0.22}[section]
    mix = (
        kick * kick_g
        + snare * 0.45
        + hats * 0.22
        + perc * perc_g
        + acid * acid_g
    )
    mix = tanh_drive(mix, 0.95)
    # slightly more open for tribal body in Drop, still dark
    mix = lpf_inplace(mix, 3000.0 if section in ("Drop", "Drop2", "Break") else 2400.0)
    return {
        "kick": kick, "snare": snare, "hats": hats, "perc": perc,
        "acid": acid, "mix": mix, "hits": hits, "bars": bars, "n": N,
    }

def load_kit():
    # kit_v3 ONLY — no perc_loop / voice_a (poisoned in v1)
    names = [
        "kick_a", "kick_b", "snare_a", "clap_a", "hat_closed", "hat_open",
        "perc_a", "perc_b", "perc_c", "bass_a",
    ]
    kit = {}
    for n in names:
        p = KIT / f"{n}.wav"
        if not p.exists():
            raise FileNotFoundError(p)
        kit[n] = read_wav(p)
        peak = float(np.max(np.abs(kit[n])))
        print("kit", n, "len", len(kit[n]), "peak", peak)
        if peak < 0.01:
            raise RuntimeError(f"silent/corrupt sample: {n}")
    # poison guard: kick must have strong LF
    ka = kit["kick_a"]
    X = np.abs(np.fft.rfft(ka * np.hanning(len(ka)))) + 1e-12
    freqs = np.fft.rfftfreq(len(ka), 1 / SR)
    e = X ** 2
    lf = float(e[freqs < 200].sum() / e.sum())
    geo = float(np.exp(np.mean(np.log(X))))
    flat = geo / float(np.mean(X))
    print(f"POISON_GUARD kick_a lf={lf:.3f} flat={flat:.4f}")
    if lf < 0.3 or flat > 0.3:
        raise RuntimeError(f"POISONED kit detected: kick_a lf={lf} flat={flat} — abort")
    return kit


def safe_delete(ti, ci):
    send("delete_clip", {"track_index": ti, "clip_index": ci})


def load_audio(ti, ci, path: Path, name: str):
    safe_delete(ti, ci)
    r = send("create_audio_clip", {"track_index": ti, "clip_index": ci, "path": str(path)}, timeout=180)
    if r.get("status") != "success":
        print("FAIL audio", name, r)
        return False
    send("set_clip_name", {"track_index": ti, "clip_index": ci, "name": name})
    print("OK audio", name, "->", ti, ci)
    return True


def put_midi(ti, ci, length, name, notes):
    safe_delete(ti, ci)
    r = send("create_clip", {"track_index": ti, "clip_index": ci, "length": float(length)})
    if r.get("status") != "success":
        print("FAIL midi create", name, r)
        return False
    send("set_clip_name", {"track_index": ti, "clip_index": ci, "name": name})
    chunk = 200
    for i in range(0, len(notes), chunk):
        rr = send("add_notes_to_clip", {"track_index": ti, "clip_index": ci, "notes": notes[i:i + chunk]})
        if rr.get("status") != "success":
            print("FAIL notes", name, rr)
            return False
    print("OK midi", name, "notes", len(notes), "->", ti, ci)
    return True


def snapshot_by_name():
    r = ok(send("get_session_snapshot"), "snapshot")
    tracks = r["tracks"]
    return {t["name"]: t["index"] for t in tracks}, tracks


def mute_track(ti):
    try:
        r = send("set_track_mute", {"track_index": ti, "mute": True})
        print("mute", ti, r.get("status"))
    except Exception as e:
        # fallback: try volume near zero
        try:
            send("set_track_volume", {"track_index": ti, "volume": 0.0})
            print("vol0", ti)
        except Exception as e2:
            print("mute warn", ti, e, e2)


def render_audio_only():
    """Render full arrangement bounce from kit_v3 (no Ableton required)."""
    print("=== CueCurrent_167 v4 RENDER @", BPM, "kit=", KIT, "ON_PC=", ON_PC, "===")
    kit = load_kit()
    patterns = {
        "Intro": acid_pattern_gsm(16711, denser=False),
        "Build": acid_pattern_gsm(16712, denser=False),
        "Drop": acid_pattern_gsm(16713, denser=True),
        "Break": acid_pattern_gsm(16714, denser=False),
        "Drop2": acid_pattern_gsm(16715, denser=True),
        "Outro": acid_pattern_gsm(16716, denser=False),
    }
    # Acid gains MUCH lower — kick first; mute mirror until thump proven
    acid_gains = {
        "Intro": 0.07,
        "Build": 0.11,
        "Drop": 0.15,
        "Break": 0.12,
        "Drop2": 0.17,
        "Outro": 0.06,
    }
    section_paths = {}
    total_hits = 0
    total_dur = 0.0
    concat_list = OUT / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as flist:
        for name, bars, row in SECTIONS:
            whisper = name in ("Intro", "Outro", "Break")
            open_ = name in ("Drop2",)  # only Drop2 mildly open — still capped
            print(f"--- render {name} bars={bars} ---")
            data = render_section_mix(
                name, bars, kit, patterns[name],
                acid_gains[name], whisper=whisper, open_=open_,
            )
            total_hits += data["hits"]
            total_dur += data["n"] / SR
            for key in ("kick", "snare", "hats", "perc", "acid", "mix"):
                fp = SEC / f"{row:02d}_{name}_{key}.wav"
                if key == "mix":
                    write_wav_stereo(fp, data[key], peak=0.92)
                else:
                    write_wav_mono(fp, data[key], peak=0.90)
            section_paths[name] = {
                "row": row, "bars": bars,
                "paths": {k: SEC / f"{row:02d}_{name}_{k}.wav" for k in ("kick", "snare", "hats", "perc", "acid", "mix")},
                "hits": data["hits"], "dur": data["n"] / SR,
            }
            loop = render_section_mix(
                name, LOOP_BARS, kit, patterns[name],
                acid_gains[name], whisper=whisper, open_=open_,
            )
            for key in ("kick", "snare", "hats", "perc", "acid", "mix"):
                fp = SEC / f"loop_{row:02d}_{name}_{key}.wav"
                if key == "mix":
                    write_wav_stereo(fp, loop[key], peak=0.92)
                else:
                    write_wav_mono(fp, loop[key], peak=0.90)
            # SILENT acid mirror clips (mute until kick thumps solo first)
            silent = np.zeros(n_for_bars(LOOP_BARS), dtype=np.float32)
            write_wav_mono(SEC / f"loop_{row:02d}_{name}_acid_MUTED.wav", silent, peak=0.01)
            section_paths[name]["loop"] = {
                k: SEC / f"loop_{row:02d}_{name}_{k}.wav" for k in ("kick", "snare", "hats", "perc", "acid", "mix")
            }
            section_paths[name]["loop"]["acid_muted"] = SEC / f"loop_{row:02d}_{name}_acid_MUTED.wav"
            p = str(section_paths[name]["paths"]["mix"]).replace("\\", "/")
            flist.write(f"file '{p}'\n")
            dens = data["hits"] / (data["n"] / SR)
            print(f"  hits={data['hits']} dens={dens:.2f}/s dur={data['n']/SR:.1f}s")

    onset_density = total_hits / total_dur if total_dur else 0
    print(f"TOTAL hits={total_hits} dur={total_dur:.1f}s onset≈{onset_density:.2f}/s")

    raw = OUT / "cue167_v4_concat.wav"
    loud = OUT / "cue167_v4_loud.wav"
    ff = "ffmpeg"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw)], check=True, capture_output=True)
    # loudnorm milder + lowpass keep dark (no HF lift)
    try:
        subprocess.run([
            ff, "-y", "-i", str(raw),
            "-af", "highpass=f=28,lowpass=f=9000,loudnorm=I=-9.5:TP=-1.2:LRA=5,alimiter=limit=0.92",
            "-ar", "44100", str(loud),
        ], check=True, capture_output=True)
        src = loud
    except Exception as e:
        print("loudnorm fail", e)
        src = raw
    subprocess.run([ff, "-y", "-i", str(src), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3_DL)], check=True, capture_output=True)
    shutil.copy2(src, WAV_DL)
    mp3_dur = total_dur
    try:
        pr = subprocess.run([ff, "-i", str(MP3_DL)], capture_output=True, text=True)
        import re
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", pr.stderr)
        if m:
            mp3_dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    print("MP3", MP3_DL, "dur", round(mp3_dur, 2))
    meta = {
        "section_paths": {k: {kk: str(vv) if not isinstance(vv, dict) else {a: str(b) for a, b in vv.items()}
                              for kk, vv in v.items() if kk != "paths"} | {"paths": {a: str(b) for a, b in v["paths"].items()}}
                          for k, v in section_paths.items()},
        "patterns": {k: v for k, v in patterns.items()},
        "acid_gains": acid_gains,
        "mp3": str(MP3_DL),
        "wav": str(WAV_DL),
        "mp3_dur_s": mp3_dur,
        "onset_density": onset_density,
        "total_hits": total_hits,
        "bpm": BPM,
        "key": "G#m",
        "kit": str(KIT),
        "on_pc": ON_PC,
    }
    # patterns not JSON-serializable cleanly as nested — rewrite lighter
    meta["patterns"] = {k: "gsm_seed" for k in patterns}
    (OUT / "v4_render_meta.json").write_text(json.dumps({
        "mp3": str(MP3_DL), "wav": str(WAV_DL), "mp3_dur_s": mp3_dur,
        "onset_density": onset_density, "total_hits": total_hits,
        "bpm": BPM, "key": "G#m", "kit": str(KIT), "on_pc": ON_PC,
        "acid_gains": acid_gains,
        "sections": {k: {"row": v["row"], "bars": v["bars"], "hits": v["hits"], "dur": v["dur"],
                         "paths": {a: str(b) for a, b in v["paths"].items()},
                         "loop": {a: str(b) for a, b in v["loop"].items()}}
                    for k, v in section_paths.items()},
    }, indent=2), encoding="utf-8")
    return section_paths, patterns, acid_gains, mp3_dur, onset_density, total_hits


def load_ableton(section_paths, patterns):
    errors = []
    print("=== Ableton session load v4 ===")
    ok(send("set_tempo", {"tempo": BPM}), "tempo 167")
    try:
        ok(send("stop_playback"), "stop")
    except Exception:
        pass
    by, tracks = snapshot_by_name()
    print("TRACKS", by)

    def ti(*names, default=None):
        for n in names:
            if n in by:
                return by[n]
        return default

    t_acid_midi = ti("Drift Acid G#m", "Acid 303 Poly", default=0)
    t_drum_midi = ti("ESX Drum Rack", "CueCurrent Drum Rack", default=1)
    t_kick = ti("CueKick", default=2)
    t_hats = ti("CueHats", default=3)
    t_perc = ti("CueSmp26", "ESX Stretch", default=6)
    t_acid_aud = ti("Acid 303", default=9)
    t_snare = ti("CueSnare", default=12)
    t_mix = ti("E-DrumLP", "CueMix", default=15)

    try:
        r = send("load_instrument_or_effect", {"track_index": t_acid_midi, "uri": "query:Synths#Drift"})
        print("Drift load", r.get("status"), r.get("message", r.get("result")))
    except Exception as e:
        print("Drift load warn", e)
        errors.append(str(e))

    try:
        send("set_track_name", {"track_index": t_acid_midi, "name": "Drift Acid G#m"})
        send("set_track_name", {"track_index": t_drum_midi, "name": "Cue Drum Rack v4"})
        send("set_track_name", {"track_index": t_kick, "name": "CueKick"})
        send("set_track_name", {"track_index": t_hats, "name": "CueHats"})
        send("set_track_name", {"track_index": t_snare, "name": "CueSnare"})
    except Exception:
        pass

    # kit_v3 oneshots ONLY
    oneshot_targets = [
        (ti("CueSmp4", default=10), 0, KIT / "kick_a.wav", "kit_v3_kick_a"),
        (ti("CueSmp6", default=14), 0, KIT / "snare_a.wav", "kit_v3_snare_a"),
        (ti("CueSmp20", default=13), 0, KIT / "hat_closed.wav", "kit_v3_hat_c"),
        (ti("CueSmp4", default=10), 1, KIT / "kick_b.wav", "kit_v3_kick_b"),
        (ti("CueSmp6", default=14), 1, KIT / "clap_a.wav", "kit_v3_clap_a"),
        (ti("CueSmp20", default=13), 1, KIT / "hat_open.wav", "kit_v3_hat_o"),
        (ti("CueSmp4", default=10), 2, KIT / "perc_a.wav", "kit_v3_perc_a"),
        (ti("CueSmp6", default=14), 2, KIT / "perc_b.wav", "kit_v3_perc_b"),
        (ti("CueSmp20", default=13), 2, KIT / "perc_c.wav", "kit_v3_perc_c"),
        (ti("CueSmp6", default=14), 3, KIT / "bass_a.wav", "kit_v3_bass_a"),
    ]
    for ti_, ci, path, nm in oneshot_targets:
        if ti_ is None:
            continue
        try:
            load_audio(ti_, ci, path, nm)
        except Exception as e:
            print("oneshot warn", nm, e)
            errors.append(f"oneshot {nm}: {e}")

    clip_len = float(LOOP_BARS * 4)
    for name, bars, row in SECTIONS:
        loops = section_paths[name]["loop"]
        if t_kick is not None:
            load_audio(t_kick, row, loops["kick"], f"{name}_kick")
        if t_hats is not None:
            load_audio(t_hats, row, loops["hats"], f"{name}_hats")
        if t_snare is not None:
            load_audio(t_snare, row, loops["snare"], f"{name}_snare")
        if t_perc is not None:
            load_audio(t_perc, row, loops["perc"], f"{name}_perc")
        # MUTE acid audio mirror — load silent or skip
        if t_acid_aud is not None:
            load_audio(t_acid_aud, row, loops.get("acid_muted", loops["acid"]), f"{name}_acid_MUTED")
        if t_mix is not None:
            load_audio(t_mix, row, loops["mix"], f"{name}_mix")
        denser = name in ("Drop", "Drop2")
        midi = make_acid_midi(patterns[name], bars=LOOP_BARS, denser=denser)
        if name == "Intro":
            midi = [n for i, n in enumerate(midi) if i % 3 != 1]
        put_midi(t_acid_midi, row, clip_len, f"{name}_drift_Gsm", midi)
        put_midi(t_drum_midi, row, clip_len, f"{name}_kit_midi", make_drum_midi(name, LOOP_BARS))
        t0 = sum(SECTIONS[i][1] for i in range(row)) * 4.0
        send("create_locator", {"name": f"{row}_{name}", "time": float(t0)})

    # MUTE Acid 303 mirror track until kick proven
    if t_acid_aud is not None:
        mute_track(t_acid_aud)

    try:
        for row_name, bars, row in SECTIONS:
            start = sum(SECTIONS[i][1] for i in range(row)) * 4.0
            n_copies = max(1, bars // LOOP_BARS)
            for c in range(n_copies):
                for tidx in (t_kick, t_hats, t_snare, t_perc, t_mix, t_acid_midi, t_drum_midi):
                    if tidx is None:
                        continue
                    send("duplicate_session_clip_to_arrangement", {
                        "track_index": tidx,
                        "clip_index": row,
                        "arrangement_time": float(start + c * clip_len),
                    })
        print("OK arrangement duplicates")
    except Exception as e:
        print("arrangement warn", e)
        errors.append(f"arrangement: {e}")

    # Fire KICK + drums first (Drop) — acid midi optional low
    FIRE = 2
    for tidx in (t_kick, t_hats, t_snare, t_perc, t_drum_midi, t_mix):
        if tidx is None:
            continue
        r = send("fire_clip", {"track_index": tidx, "clip_index": FIRE})
        print("fire", tidx, r.get("status"))
    # Drift MIDI fire but keep quiet doctrine via session; acid aud stays muted
    if t_acid_midi is not None:
        send("fire_clip", {"track_index": t_acid_midi, "clip_index": FIRE})
    ok(send("start_playback"), "start_playback")

    amap = f"""# CueCurrent_167 v4 — Ableton session map

Tempo: **167** · Key: **G#m** · Kit: **CueCurrent_167_kit_v3 ONLY** · v4 audible tribal (poison kit_v1/esx NEVER)
Scenes/rows 0–5 = Intro, Build, Drop, Break, Drop2, Outro (16-bar loops)

| Idx | Track | Role |
|-----|-------|------|
| {t_acid_midi} | Drift Acid G#m | MIDI Drift acid (Noise LOW; filter not open) |
| {t_drum_midi} | Cue Drum Rack v4 | MIDI kit map — pads from kit_v3 oneshots on CueSmp* |
| {t_kick} | CueKick | kick stems (kick_a/b heavy) |
| {t_hats} | CueHats | hat stems (low in mix) |
| {t_snare} | CueSnare | snare/clap stems |
| {t_perc} | perc audio | perc stems (no poisoned perc_loop) |
| {t_acid_aud} | Acid 303 | **MUTED** acid mirror (silent clips) until kick thumps solo |
| {t_mix} | mix bus clip | section mix reference |
| 10/13/14 | CueSmp* | kit_v3 one-shots for Drum Rack pads |

Locators: 0_Intro … 5_Outro. Arrangement ~288 bars.
Save Live set as `CueCurrent_167_v4.als`. NOT publish yet.
POISON NEVER: CueCurrent_167_kit/, esx-unpack/*, esx-factory, es1-factory.
"""
    MAP_DL.write_text(amap, encoding="utf-8")
    try:
        ALS_NOTE.parent.mkdir(parents=True, exist_ok=True)
        ALS_NOTE.write_text(amap, encoding="utf-8")
    except Exception as e:
        print("als note warn", e)
    return {
        "t_acid_midi": t_acid_midi, "t_drum_midi": t_drum_midi, "t_kick": t_kick,
        "t_hats": t_hats, "t_snare": t_snare, "t_perc": t_perc,
        "t_acid_aud": t_acid_aud, "t_mix": t_mix, "errors": errors, "map": str(MAP_DL),
    }



def write_notes(mp3_dur, onset_density, section_onset=None, ableton_map_info=None):
    so = section_onset or {}
    notes = f"""# EvAIx CueCurrent_167 v4 — NOTES

**BPM:** 167 · **Key:** G#m · **Length:** ~{mp3_dur:.1f}s ({mp3_dur/60:.2f} min)
**Kit:** `/workspace/exports/CueCurrent_167_kit_v3/` ONLY (10 verified WAVs). kick_a/b Insane Teknology kept heavy.
**POISON NEVER LOADED:** CueCurrent_167_kit/, esx-unpack/*, esx-factory, es1-factory.
**Acid:** Drift MIDI (Noise LOW, filter capped). Acid 303 audio mirror **MUTED**. Controlled — supports sections, does not wash kick.
**Mix doctrine:** sub+kick dominant (v3 ~92% kept); tekno tribal audible without thinning low end.

## What changed vs v3 (section-by-section)

| Section | Bars | ~time | v4 change |
|---------|------|-------|-----------|
| **Intro** | 1–64 | 0:00–1:32 | Filtered/subtracted kick roll (HPF blend opens over 64 bars); sparse 8th hats; **no full tribal** (only rare late conga tick); whisper acid |
| **Build** | 65–96 | 1:32–2:18 | Snare+clap enter; **tribal peeking** (conga/claves ramp); **hats denser last 4 bars** + open-hat accents |
| **Drop** | 97–160 | 2:18–4:10 | Full kick_a+kick_b+bass; **tekno tribal LOCKED** (rolling conga + claves + sparse synperc fills); open energy |
| **Break** | 161–192 | 4:10–4:56 | Kick subtracted/halved; **tribal/conga focus** (perc gain up); space — not silence |
| **Drop2** | 193–256 | 4:56–6:28 | Heavier kicks; **extra perc_c + open-hat accents**; denser tribal fills every 8 |
| **Outro** | 257–288 | 6:28–6:54 | Peel tribal→hats→kick filter stub for DJ |

**Tribal sources (kit_v3 only):** perc_a=Conga Hi, perc_b=Claves, perc_c=Synperc5 — rolling free-party, not plinky EDM fills.
**Arrangement:** full-length section render (not identical 16-bar tile forever) so form is audible across ~7′.

## Onset density (Intro vs Drop)
- Intro onset≈{so.get('Intro', 0):.2f}/s
- Drop onset≈{so.get('Drop', 0):.2f}/s
- Gate Drop > Intro: {"PASS" if so.get('Drop', 0) > so.get('Intro', 0) else "FAIL"}
- Global onset≈{onset_density:.2f}/s

## Deliverables
- MP3: `{MP3_DL}` (+ `/workspace/exports/{MP3_NAME}`)
- WAV: `{WAV_DL}`
- Kit: `{KIT}`
- Ableton: open @167; map `{MAP_DL}`; reuse 16 tracks; save `CueCurrent_167_v4.als`
- Builder: `build_cue_current_167_v4.py`
- **NOT publish yet**
"""
    NOTES_DL.write_text(notes, encoding="utf-8")
    return str(NOTES_DL)


def compute_gate_metrics(mp3_path: Path, section_paths: dict):
    """Centroid/flatness/sub+kick + Intro vs Drop onset. Uses librosa if available."""
    import numpy as np
    try:
        import librosa
    except ImportError:
        return {"error": "librosa missing"}

    def load_mono(path, sr=44100):
        y, _ = librosa.load(str(path), sr=sr, mono=True)
        return y

    ref = Path("/workspace/exports/USER_CURRENT_TRACK_ref.mp3")
    y = load_mono(mp3_path)
    yr = load_mono(ref) if ref.exists() else None

    def band_shares(sig, sr=44100):
        S = np.abs(librosa.stft(sig, n_fft=2048, hop_length=512)) ** 2
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        e = S.sum(axis=1) + 1e-12
        tot = e.sum()
        def band(lo, hi):
            return float(e[(freqs >= lo) & (freqs < hi)].sum() / tot)
        sub = band(20, 60)
        kick = band(60, 120)
        bass = band(120, 250)
        low = band(20, 250)
        lowmid = band(250, 500)
        mid = band(500, 2000)
        acid_band = band(800, 2500)
        high = band(2000, 8000)
        cen = float(np.mean(librosa.feature.spectral_centroid(y=sig, sr=sr)))
        flat = float(np.mean(librosa.feature.spectral_flatness(y=sig)))
        rms = float(np.sqrt(np.mean(sig ** 2)) + 1e-12)
        peak = float(np.max(np.abs(sig)) + 1e-12)
        crest = peak / rms
        # white-noise proxy: fraction of frames with flatness > 0.4
        flat_f = librosa.feature.spectral_flatness(y=sig)[0]
        wn = float(np.mean(flat_f > 0.4))
        return {
            "sub": sub, "kick": kick, "bass": bass, "sub_kick": sub + kick,
            "low": low, "lowmid": lowmid, "mid": mid, "acid_band": acid_band, "high": high,
            "centroid_hz": cen, "flatness": flat, "rms_db": 20 * np.log10(rms),
            "crest": crest, "white_noise_frame_frac": wn,
        }

    def onset_density(sig, sr=44100):
        o = librosa.onset.onset_strength(y=sig, sr=sr)
        # count peaks
        peaks = librosa.util.peak_pick(o, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.2, wait=2)
        dur = len(sig) / sr
        return float(len(peaks) / dur) if dur > 0 else 0.0

    cand = band_shares(y)
    refm = band_shares(yr) if yr is not None else {}

    section_onset = {}
    for name, info in section_paths.items():
        mixp = info["paths"]["mix"]
        ys = load_mono(mixp)
        section_onset[name] = onset_density(ys)

    gates = {
        "spectral_centroid_le_2kHz": {
            "value": cand["centroid_hz"], "limit": 2000,
            "pass": cand["centroid_hz"] <= 2000,
        },
        "spectral_flatness_le_0.02": {
            "value": cand["flatness"], "limit": 0.02,
            "pass": cand["flatness"] <= 0.02,
        },
        "sub_kick_energy_high": {
            "value": cand["sub_kick"],
            "ref": refm.get("sub_kick"),
            "pass": cand["sub_kick"] >= 0.80,
        },
        "no_white_noise": {
            "white_noise_frame_frac": cand["white_noise_frame_frac"],
            "pass": cand["white_noise_frame_frac"] < 0.01,
        },
        "drop_onset_gt_intro": {
            "intro": section_onset.get("Intro", 0),
            "drop": section_onset.get("Drop", 0),
            "pass": section_onset.get("Drop", 0) > section_onset.get("Intro", 0),
        },
    }
    pass_all = all(g["pass"] for g in gates.values())
    return {
        "track": "EvAIx_CueCurrent_167_v4",
        "ref": str(ref),
        "cand": str(mp3_path),
        "bpm_target": 167,
        "key": "G#m",
        "kit": "/workspace/exports/CueCurrent_167_kit_v3/",
        "poison_never": [
            "/workspace/exports/CueCurrent_167_kit/",
            "esx-unpack/*", "esx-factory", "es1-factory",
        ],
        "gates": gates,
        "pass_all_gates": pass_all,
        "band_shares_vs_ref": {"ref": refm, "v4": cand},
        "section_onset_per_s": section_onset,
        "duration_s": float(len(y) / 44100.0),
    }




def main():
    import sys
    mode = "all"
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    section_paths, patterns, acid_gains, mp3_dur, onset_density, total_hits = render_audio_only()
    ableton_info = None
    if mode in ("all", "ableton") and ON_PC:
        ableton_info = load_ableton(section_paths, patterns)
    elif mode == "ableton" and not ON_PC:
        print("Ableton load skipped on box — run on PC with kit at", PC_KIT)

    metrics = None
    section_onset = {}
    try:
        metrics = compute_gate_metrics(MP3_DL if MP3_DL.exists() else Path("/workspace/exports") / MP3_NAME, section_paths)
        section_onset = metrics.get("section_onset_per_s", {})
        # always write metrics to exports
        exp_m = Path("/workspace/exports/EvAIx_CueCurrent_167_v4_metrics.json")
        exp_m.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print("METRICS", json.dumps(metrics["gates"], indent=2))
        print("pass_all_gates", metrics["pass_all_gates"])
    except Exception as e:
        print("metrics warn", e)
        metrics = {"error": str(e)}

    notes_path = write_notes(mp3_dur, onset_density, section_onset, ableton_info)
    # mirror notes/map/mp3 into exports when on PC
    try:
        exp = Path("/workspace/exports")
        if ON_PC:
            pass  # PC path; box copy done by orchestrator
        else:
            # already writing to exports via MP3_DL when not ON_PC
            pass
        # always ensure exports copies of notes/map
        Path("/workspace/exports/EvAIx_CueCurrent_167_v4_NOTES.md").write_text(Path(notes_path).read_text(encoding="utf-8"), encoding="utf-8")
        if MAP_DL.exists():
            Path("/workspace/exports/EvAIx_CueCurrent_167_v4_ABLETON_MAP.md").write_text(MAP_DL.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception as e:
        print("exports mirror warn", e)

    summary = {
        "mp3": str(MP3_DL), "wav": str(WAV_DL), "notes": notes_path,
        "map": str(MAP_DL), "mp3_dur_s": mp3_dur, "onset_density": onset_density,
        "total_hits": total_hits, "bpm": BPM, "key": "G#m", "kit": str(KIT),
        "on_pc": ON_PC, "ableton": ableton_info, "acid_gains": acid_gains,
        "section_onset": section_onset, "metrics": metrics,
        "poison_guard": "kit_v3 only; kick_a lf/flat checked at load",
        "v4": "audible arrangement + tekno tribal; kick weight kept; not publish",
    }
    (OUT / "v4_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print("=== SUMMARY ===")
    print(json.dumps({k: summary[k] for k in summary if k != "ableton"}, indent=2, default=str))


if __name__ == "__main__":
    main()
