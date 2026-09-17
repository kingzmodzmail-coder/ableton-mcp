# -*- coding: utf-8 -*-
"""CueCurrent_167 v3 — CLEAN kit_v3 only, sub+kick dominant, mute acid mirror.
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

# --- paths: box-first; PC override via CUE167_V3_ROOT ---
BOX_KIT = Path("/workspace/exports/CueCurrent_167_kit_v3")
BOX_OUT = Path("/workspace/exports/_cue167_v3_build")
PC_BRIDGE = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge")
PC_KIT = PC_BRIDGE / "samples" / "cue167_kit_v3"
PC_OUT = PC_BRIDGE / "samples" / "cue167_v3"

def _paths():
    if PC_KIT.exists() and (PC_KIT / "kick_a.wav").exists():
        return PC_KIT, PC_OUT, True
    return BOX_KIT, BOX_OUT, False

KIT, OUT, ON_PC = _paths()
SEC = OUT / "sections"
SEC.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

MP3_NAME = "EvAIx_CueCurrent_167_v3.mp3"
WAV_NAME = "EvAIx_CueCurrent_167_v3.wav"
if ON_PC:
    MP3_DL = Path(r"C:\Users\Gebruiker\Downloads") / MP3_NAME
    WAV_DL = Path(r"C:\Users\Gebruiker\Downloads") / WAV_NAME
    NOTES_DL = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_CueCurrent_167_v3_NOTES.md")
    MAP_DL = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_CueCurrent_167_v3_ABLETON_MAP.md")
    ALS_NOTE = Path(r"C:\Users\Gebruiker\Documents\Ableton\CueCurrent_167_v3_SESSION.txt")
else:
    MP3_DL = Path("/workspace/exports") / MP3_NAME
    WAV_DL = Path("/workspace/exports") / WAV_NAME
    NOTES_DL = Path("/workspace/exports/EvAIx_CueCurrent_167_v3_NOTES.md")
    MAP_DL = Path("/workspace/exports/EvAIx_CueCurrent_167_v3_ABLETON_MAP.md")
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
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        if section != "Break":
            for b in (0, 1, 2, 3):
                notes.append({"pitch": 36, "start_time": base + b, "duration": 0.2, "velocity": 118 if b == 0 else 108, "mute": False})
            if section in ("Drop", "Drop2", "Build"):
                notes.append({"pitch": 37, "start_time": base + 0.0, "duration": 0.25, "velocity": 85, "mute": False})
            if section in ("Drop", "Drop2") and bar % 2 == 1:
                notes.append({"pitch": 36, "start_time": base + 2.5, "duration": 0.15, "velocity": 95, "mute": False})
        elif bar >= bars - 4:
            for b in (0, 1, 2, 3):
                notes.append({"pitch": 36, "start_time": base + b, "duration": 0.2, "velocity": 110, "mute": False})
        if section in ("Build", "Drop", "Drop2"):
            notes.append({"pitch": 38, "start_time": base + 1, "duration": 0.18, "velocity": 100, "mute": False})
            notes.append({"pitch": 38, "start_time": base + 3, "duration": 0.18, "velocity": 100, "mute": False})
            if section != "Build":
                notes.append({"pitch": 39, "start_time": base + 3, "duration": 0.12, "velocity": 55, "mute": False})
        if section == "Intro":
            for st in range(0, 16, 2):
                notes.append({"pitch": 42, "start_time": base + st * 0.25, "duration": 0.08, "velocity": 42, "mute": False})
        elif section == "Break":
            for st in range(0, 16, 4):
                notes.append({"pitch": 41, "start_time": base + st * 0.25, "duration": 0.08, "velocity": 50, "mute": False})
        elif section == "Outro":
            if bar < bars // 2:
                for st in range(0, 16, 2):
                    notes.append({"pitch": 42, "start_time": base + st * 0.25, "duration": 0.08, "velocity": 40, "mute": False})
        else:
            for st in range(16):
                vel = 62 if st % 2 == 0 else 38
                notes.append({"pitch": 42, "start_time": base + st * 0.25, "duration": 0.07, "velocity": vel, "mute": False})
            if bar % 4 == 3:
                notes.append({"pitch": 46, "start_time": base + 3.5, "duration": 0.3, "velocity": 70, "mute": False})
        if section in ("Intro", "Break"):
            notes.append({"pitch": 41, "start_time": base + 0.75, "duration": 0.06, "velocity": 48, "mute": False})
            notes.append({"pitch": 41, "start_time": base + 2.75, "duration": 0.06, "velocity": 42, "mute": False})
        if section in ("Drop", "Drop2") and bar % 8 == 7:
            for t in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75):
                notes.append({"pitch": 45 if section == "Drop2" else 43, "start_time": base + 2 + t, "duration": 0.06, "velocity": 70, "mute": False})
    return notes


def render_drums(section: str, bars: int, kit: dict):
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
        if section == "Intro":
            prog = bar / max(1, bars - 1)
            for b in (0, 1, 2, 3):
                g = 0.55 + 0.45 * prog
                place(kick, ka, base + b, g)
                hits += 1
            if bar >= bars // 2:
                place(kick, ka, base + 1.5, 0.30 * prog)
                hits += 1
            if ba is not None and bar % 4 == 0:
                place(kick, ba[: int(0.35 * SR)], base, 0.35 * prog)
        elif section == "Break":
            if bar < 8:
                pass
            elif bar < 16:
                if bar % 2 == 0:
                    place(kick, ka, base, 0.45)
                    hits += 1
            else:
                for b in (0, 1, 2, 3):
                    place(kick, ka, base + b, 0.95)
                    hits += 1
        elif section == "Outro":
            fade = 1.0 - 0.7 * (bar / max(1, bars - 1))
            for b in (0, 1, 2, 3):
                place(kick, ka, base + b, 0.95 * fade)
                hits += 1
            if bar < bars // 3:
                place(kick, kb, base, 0.40 * fade)
                hits += 1
        else:
            # HEAVY kick_a/b — lf~0.95/0.88
            for b in (0, 1, 2, 3):
                place(kick, ka, base + b, 1.05)
                hits += 1
            if section in ("Drop", "Drop2"):
                place(kick, kb, base, 0.55 if section == "Drop" else 0.70)
                hits += 1
                if ba is not None:
                    place(kick, ba[: int(0.28 * SR)], base, 0.45)
                place(kick, ka, base + 1.5, 0.42)
                place(kick, ka, base + 3.5, 0.38)
                hits += 2
                if bar % 2 == 1:
                    place(kick, ka, base + 2.25, 0.35)
                    hits += 1
            if section == "Build":
                place(kick, kb, base, 0.35)
                place(kick, ka, base + 2.5, 0.32)
                hits += 2
                if ba is not None and bar % 2 == 0:
                    place(kick, ba[: int(0.28 * SR)], base, 0.30)

        if section in ("Build", "Drop", "Drop2"):
            place(snare, sn, base + 1, 0.70)
            place(snare, sn, base + 3, 0.70)
            hits += 2
            if section != "Build":
                place(snare, cl, base + 3, 0.22)
                hits += 1
                if bar % 4 == 3:
                    place(snare, sn, base + 3.5, 0.32)
                    hits += 1
            if section == "Build" and bar >= bars - 4:
                place(snare, cl, base + 1.75, 0.15)
                hits += 1
        if section == "Break" and bar in (4, 12, 20):
            place(snare, sn[::-1] if len(sn) > 10 else sn, base + 2, 0.18)
            hits += 1

        # hats LOWER than v2 — tops must not dominate
        if section == "Intro":
            for st in range(0, 16, 2):
                place(hats, hc, base + st * 0.25, 0.18)
                hits += 1
        elif section == "Break":
            pass
        elif section == "Build" and bar >= bars - 4:
            pass
        elif section == "Outro":
            if bar < bars * 2 // 3:
                for st in range(0, 16, 2):
                    place(hats, hc, base + st * 0.25, 0.20 * (1 - bar / bars))
                    hits += 1
        else:
            for st in range(16):
                g = 0.28 if st % 2 == 0 else 0.14
                place(hats, hc, base + st * 0.25, g)
                hits += 1
            if bar % 4 == 3 or (section == "Drop2" and bar % 2 == 1):
                place(hats, ho, base + 3.5, 0.28)
                hits += 1

        if section in ("Intro", "Break"):
            place(perc, pa, base + 0.75, 0.28)
            place(perc, pa, base + 2.75, 0.24)
            hits += 2
        if section == "Build":
            place(perc, pb, base + 1.5, 0.22)
            hits += 1
        if section in ("Drop", "Drop2"):
            if bar % 8 == 7:
                fill = pc if section == "Drop2" else pb
                for t in np.arange(2.0, 4.0, 0.125):
                    place(perc, fill, base + float(t), 0.22)
                    hits += 1
            elif bar % 4 == 2:
                place(perc, pb if section == "Drop" else pc, base + 2.5, 0.24)
                hits += 1

    if section == "Intro":
        # mild HPF open — still keep body
        kick = hpf_inplace(kick, 55.0) * 0.35 + kick * 0.65
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
    base_bars = min(bars, LOOP_BARS)
    kick, snare, hats, perc, hits = render_drums(section, base_bars, kit)
    acid = render_acid(base_bars, pattern, whisper=whisper, open_=open_, grit=1.5 if whisper else 1.7)
    reps = max(1, bars // base_bars)
    hits = hits * reps
    kick = tile_buf(kick, base_bars, bars)
    snare = tile_buf(snare, base_bars, bars)
    hats = tile_buf(hats, base_bars, bars)
    perc = tile_buf(perc, base_bars, bars)
    acid = tile_buf(acid, base_bars, bars)
    N = n_for_bars(bars)
    if section == "Intro":
        env = np.linspace(0.60, 1.0, N, dtype=np.float32)
        kick *= env
        acid *= np.linspace(0.25, 0.7, N, dtype=np.float32)
    elif section == "Outro":
        env = np.linspace(1.0, 0.22, N, dtype=np.float32)
        kick *= env
        snare *= env
        hats *= env
        acid *= env
    elif section == "Break":
        half = N // 2
        kick[:half] *= 0.12
        hats[:half] *= 0.08
    # KICK-DOMINANT mix (target sub+kick ~87% feel)
    kick_g = {"Intro": 1.25, "Build": 1.35, "Drop": 1.45, "Break": 1.05, "Drop2": 1.50, "Outro": 1.20}[section]
    mix = (
        kick * kick_g
        + snare * 0.45
        + hats * 0.22
        + perc * 0.20
        + acid * acid_g
    )
    # soft saturation then dark LPF so tops never mic-blow
    mix = tanh_drive(mix, 0.95)
    mix = lpf_inplace(mix, 2800.0 if section in ("Drop", "Drop2") else 2400.0)
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
    print("=== CueCurrent_167 v3 RENDER @", BPM, "kit=", KIT, "ON_PC=", ON_PC, "===")
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
        "Intro": 0.06,
        "Build": 0.10,
        "Drop": 0.16,
        "Break": 0.10,
        "Drop2": 0.18,
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

    raw = OUT / "cue167_v3_concat.wav"
    loud = OUT / "cue167_v3_loud.wav"
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
    (OUT / "v3_render_meta.json").write_text(json.dumps({
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
    print("=== Ableton session load v3 ===")
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
        send("set_track_name", {"track_index": t_drum_midi, "name": "Cue Drum Rack v3"})
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

    amap = f"""# CueCurrent_167 v3 — Ableton session map

Tempo: **167** · Key: **G#m** · Kit: **CueCurrent_167_kit_v3 ONLY** (poison kit_v1/esx NEVER)
Scenes/rows 0–5 = Intro, Build, Drop, Break, Drop2, Outro (16-bar loops)

| Idx | Track | Role |
|-----|-------|------|
| {t_acid_midi} | Drift Acid G#m | MIDI Drift acid (Noise LOW; filter not open) |
| {t_drum_midi} | Cue Drum Rack v3 | MIDI kit map — pads from kit_v3 oneshots on CueSmp* |
| {t_kick} | CueKick | kick stems (kick_a/b heavy) |
| {t_hats} | CueHats | hat stems (low in mix) |
| {t_snare} | CueSnare | snare/clap stems |
| {t_perc} | perc audio | perc stems (no poisoned perc_loop) |
| {t_acid_aud} | Acid 303 | **MUTED** acid mirror (silent clips) until kick thumps solo |
| {t_mix} | mix bus clip | section mix reference |
| 10/13/14 | CueSmp* | kit_v3 one-shots for Drum Rack pads |

Locators: 0_Intro … 5_Outro. Arrangement ~288 bars.
Save Live set as `CueCurrent_167_v3.als`.
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


def write_notes(mp3_dur, onset_density, ableton_map_info=None):
    notes = f"""# EvAIx CueCurrent_167 v3 — NOTES

**BPM:** 167 · **Key:** G#m · **Length:** ~{mp3_dur:.1f}s ({mp3_dur/60:.2f} min)
**Kit:** `/workspace/exports/CueCurrent_167_kit_v3/` ONLY (10 verified WAVs). kick_a/b Insane Teknology (lf~0.95/0.88).
**POISON NEVER LOADED:** CueCurrent_167_kit/, esx-unpack/*, esx-factory, es1-factory.
**Acid:** Drift MIDI (Noise LOW, filter capped ~1.6–2.2k). Acid 303 audio mirror **MUTED**.
**Mix doctrine:** sub+kick dominant toward USER_REF ~87%; hats/perc/acid ducked; master LPF ~2.4–2.8k.

## Form (ARRANGEMENT.md)
| Section | Bars | ~time | Energy |
|---------|------|-------|--------|
| Intro | 1–64 | 0:00–1:32 | filtered kick roll, whisper acid |
| Build | 65–96 | 1:32–2:18 | snare in, hats peel last 4 |
| Drop | 97–160 | 2:18–4:10 | kick_a+kick_b+bass layer, low acid |
| Break | 161–192 | 4:10–4:56 | subtract kick, perc ticks |
| Drop2 | 193–256 | 4:56–6:28 | heavier kicks, metallic perc_c |
| Outro | 257–288 | 6:28–6:54 | peel to DJ stub |

## Deliverables
- MP3: `{MP3_DL}` (+ `/workspace/exports/{MP3_NAME}`)
- WAV: `{WAV_DL}`
- Kit: `{KIT}`
- Ableton: open @167; map `{MAP_DL}`
- Builder: `build_cue_current_167_v3.py`
"""
    NOTES_DL.write_text(notes, encoding="utf-8")
    if not ON_PC:
        # also write exports copies already at NOTES_DL
        pass
    return str(NOTES_DL)


def main():
    import sys
    mode = "all"
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    section_paths, patterns, acid_gains, mp3_dur, onset_density, total_hits = render_audio_only()
    ableton_info = None
    if mode in ("all", "ableton") and ON_PC:
        ableton_info = load_ableton(section_paths, patterns)
    notes_path = write_notes(mp3_dur, onset_density, ableton_info)
    summary = {
        "mp3": str(MP3_DL), "wav": str(WAV_DL), "notes": notes_path,
        "map": str(MAP_DL), "mp3_dur_s": mp3_dur, "onset_density": onset_density,
        "total_hits": total_hits, "bpm": BPM, "key": "G#m", "kit": str(KIT),
        "on_pc": ON_PC, "ableton": ableton_info, "acid_gains": acid_gains,
        "poison_guard": "kit_v3 only; kick_a lf/flat checked at load",
    }
    (OUT / "v3_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print("=== SUMMARY ===")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
