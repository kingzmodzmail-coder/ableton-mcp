# -*- coding: utf-8 -*-
"""CueCurrent_167 v2 GREENLIGHT — kit one-shots + Drift acid @167 G#m.

Follows CueCurrent_167_ARRANGEMENT.md (~288 bars / ~6:54).
Real ESX kit WAVs only. No toy preview / acid_preview source.
Reuses existing Live tracks (16-track Intro cap). Bounces MP3.
"""
from __future__ import annotations

import json
import math
import shutil
import socket
import subprocess
import wave
from array import array
from pathlib import Path

import numpy as np

BRIDGE = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge")
KIT = BRIDGE / "samples" / "cue167_kit"
OUT = BRIDGE / "samples" / "cue167_v2"
OUT.mkdir(parents=True, exist_ok=True)
SEC = OUT / "sections"
SEC.mkdir(parents=True, exist_ok=True)

MP3_DL = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_CueCurrent_167_v2.mp3")
WAV_DL = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_CueCurrent_167_v2.wav")
NOTES_DL = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_CueCurrent_167_v2_NOTES.md")
MAP_DL = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_CueCurrent_167_v2_ABLETON_MAP.md")
ALS_NOTE = Path(r"C:\Users\Gebruiker\Documents\Ableton\CueCurrent_167_v2_SESSION.txt")

BPM = 167.0
SR = 44100
HOST, PORT = "127.0.0.1", 9877

# G#m natural (dark acidcore)
GSM_MIDI = [32, 35, 37, 39, 42, 44, 47, 49]  # G#1 B1 C#2 D#2 F#2 G#2 B2 C#3
GSM_HZ = [440.0 * (2 ** ((m - 69) / 12.0)) for m in GSM_MIDI]

# Arrangement (bars) from ARRANGEMENT.md
SECTIONS = [
    ("Intro", 64, 0),
    ("Build", 32, 1),
    ("Drop", 64, 2),
    ("Break", 32, 3),
    ("Drop2", 64, 4),
    ("Outro", 32, 5),
]
# Live session loops: 16 bars each character
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
    """Simple 1-pole HPF for filtered intro kicks."""
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


def tanh_drive(x: np.ndarray, amt: float) -> np.ndarray:
    return np.tanh(x * amt).astype(np.float32)


def acid_pattern_gsm(seed: int, denser: bool = False):
    rng = np.random.default_rng(seed)
    steps = []
    prev = 0
    rest_p = 0.12 if denser else 0.22
    for i in range(16):
        if rng.random() < (0.35 if i % 4 == 1 else rest_p):
            steps.append({"midi": 0, "hz": 0.0, "accent": False, "slide": False})
            continue
        idx = int(rng.integers(0, len(GSM_MIDI)))
        # bias toward root/fifth
        if rng.random() < 0.35:
            idx = 0 if rng.random() < 0.6 else 4
        midi = int(GSM_MIDI[idx])
        accent = bool(rng.random() < 0.30 or i % 4 == 0)
        slide = bool(prev > 0 and rng.random() < 0.22)
        steps.append({"midi": midi, "hz": GSM_HZ[idx], "accent": accent, "slide": slide})
        prev = midi
    return steps


def render_acid(bars: int, pattern, *, whisper=False, open_=False, grit=2.0) -> np.ndarray:
    """Saw/square hybrid SVF acid — cutoff presence ~700Hz–3k, Drift-matching.

    Renders per 16th-note block with local numpy phase (fast enough for 16-bar loops).
    """
    N = n_for_bars(bars)
    out = np.zeros(N, dtype=np.float32)
    step_n = max(1, int((60.0 / BPM) / 4.0 * SR))
    total_steps = bars * 16
    l = b = 0.0
    phase = 0.0
    cur_hz = GSM_HZ[0]
    target_hz = cur_hz
    env = 0.0
    res_q = 0.08 if whisper else (0.16 if open_ else 0.13)
    base_cut = 180.0 if whisper else (420.0 if open_ else 300.0)
    env_amt = 900.0 if whisper else (2800.0 if open_ else 2200.0)
    env_decay = 0.99955 if whisper else 0.99915
    amp = 0.22 if whisper else 0.42
    pos = 0
    for s in range(total_steps):
        st = s % 16
        p = pattern[st]
        if p["hz"] > 0:
            target_hz = p["hz"]
            if not p["slide"]:
                cur_hz = target_hz
            env = 1.0 if p["accent"] else 0.52
        elif not p["slide"]:
            env *= 0.32
        n = min(step_n, N - pos)
        if n <= 0:
            break
        slide = bool(p.get("slide"))
        for i in range(n):
            if slide:
                cur_hz += (target_hz - cur_hz) * 0.0018
            else:
                cur_hz += (target_hz - cur_hz) * 0.45
            env *= env_decay
            phase += cur_hz / SR
            if phase >= 1.0:
                phase -= math.floor(phase)
            saw = 2.0 * phase - 1.0
            sq = 1.0 if phase < 0.5 else -1.0
            osc = (0.65 * saw + 0.35 * sq) * env * amp
            cut = base_cut + env * env_amt
            if cut < 120.0:
                cut = 120.0
            elif cut > 4200.0:
                cut = 4200.0
            f = 2 * math.sin(math.pi * min(0.45, max(0.0001, cut / SR)))
            l += f * b
            h = osc - l - res_q * b
            b += f * h
            out[pos + i] = math.tanh(l * grit)
        pos += n
    out = hpf_inplace(out, 140.0 if not whisper else 220.0)
    return out.astype(np.float32)


def make_acid_midi(pattern, bars=16, denser=False):
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        for st, p in enumerate(pattern):
            if p["midi"] <= 0:
                continue
            dur = 0.55 if p["slide"] else 0.18
            if denser and st % 2 == 0:
                dur = max(dur, 0.22)
            vel = 118 if p["accent"] else 88
            notes.append({
                "pitch": int(p["midi"]),
                "start_time": base + st * 0.25,
                "duration": dur,
                "velocity": min(127, vel),
                "mute": False,
            })
    return notes


def make_drum_midi(section: str, bars=16):
    """GM-ish Drum Rack map: 36 kick, 37 kick_b, 38 snare, 39 clap, 42 ch, 46 oh, 41/43/45 perc, 60 voice."""
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        # kicks
        if section != "Break":
            for b in (0, 1, 2, 3):
                notes.append({"pitch": 36, "start_time": base + b, "duration": 0.2, "velocity": 110 if b == 0 else 100, "mute": False})
            if section in ("Drop", "Drop2", "Build"):
                notes.append({"pitch": 37, "start_time": base + 0.0, "duration": 0.25, "velocity": 70, "mute": False})
            if section in ("Drop", "Drop2") and bar % 2 == 1:
                notes.append({"pitch": 36, "start_time": base + 2.5, "duration": 0.15, "velocity": 85, "mute": False})
        elif bar >= bars - 4:  # re-entry last 4 bars of break
            for b in (0, 1, 2, 3):
                notes.append({"pitch": 36, "start_time": base + b, "duration": 0.2, "velocity": 105, "mute": False})
        # snare/clap
        if section in ("Build", "Drop", "Drop2"):
            notes.append({"pitch": 38, "start_time": base + 1, "duration": 0.18, "velocity": 108, "mute": False})
            notes.append({"pitch": 38, "start_time": base + 3, "duration": 0.18, "velocity": 108, "mute": False})
            if section != "Build":
                notes.append({"pitch": 39, "start_time": base + 3, "duration": 0.12, "velocity": 70, "mute": False})
        # hats
        if section == "Intro":
            for st in range(0, 16, 2):
                notes.append({"pitch": 42, "start_time": base + st * 0.25, "duration": 0.08, "velocity": 55, "mute": False})
        elif section == "Break":
            for st in range(0, 16, 4):
                notes.append({"pitch": 41, "start_time": base + st * 0.25, "duration": 0.08, "velocity": 60, "mute": False})
        elif section == "Outro":
            if bar < bars // 2:
                for st in range(0, 16, 2):
                    notes.append({"pitch": 42, "start_time": base + st * 0.25, "duration": 0.08, "velocity": 50, "mute": False})
        else:
            for st in range(16):
                vel = 78 if st % 2 == 0 else 48
                notes.append({"pitch": 42, "start_time": base + st * 0.25, "duration": 0.07, "velocity": vel, "mute": False})
            if bar % 4 == 3:
                notes.append({"pitch": 46, "start_time": base + 3.5, "duration": 0.3, "velocity": 90, "mute": False})
        # perc ticks
        if section in ("Intro", "Break"):
            notes.append({"pitch": 41, "start_time": base + 0.75, "duration": 0.06, "velocity": 55, "mute": False})
            notes.append({"pitch": 41, "start_time": base + 2.75, "duration": 0.06, "velocity": 50, "mute": False})
        if section in ("Drop", "Drop2") and bar % 8 == 7:
            for t in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75):
                notes.append({"pitch": 45 if section == "Drop2" else 43, "start_time": base + 2 + t, "duration": 0.06, "velocity": 80, "mute": False})
        if section == "Intro" and bar == 12:
            notes.append({"pitch": 60, "start_time": base, "duration": 1.0, "velocity": 95, "mute": False})
        if section == "Break" and bar == 8:
            notes.append({"pitch": 60, "start_time": base, "duration": 1.0, "velocity": 100, "mute": False})
    return notes


def render_drums(section: str, bars: int, kit: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    """Returns kick, snare, hats, perc buffers + hit count."""
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
    pl = kit["perc_loop"]
    vo = kit["voice_a"]

    for bar in range(bars):
        base = bar * 4.0
        # --- kick ---
        if section == "Intro":
            # filtered kick builds over section
            prog = bar / max(1, bars - 1)
            for b in (0, 1, 2, 3):
                g = 0.35 + 0.55 * prog
                place(kick, ka, base + b, g)
                hits += 1
            if bar >= bars // 2:
                place(kick, ka, base + 1.5, 0.25 * prog)
                hits += 1
        elif section == "Break":
            if bar < 8:
                pass  # mute kick hole
            elif bar < 16:
                # dig / filtered residue every other
                if bar % 2 == 0:
                    place(kick, ka, base, 0.35)
                    hits += 1
            else:
                for b in (0, 1, 2, 3):
                    place(kick, ka, base + b, 0.9)
                    hits += 1
        elif section == "Outro":
            fade = 1.0 - 0.7 * (bar / max(1, bars - 1))
            for b in (0, 1, 2, 3):
                place(kick, ka, base + b, 0.85 * fade)
                hits += 1
            if bar < bars // 3:
                place(kick, kb, base, 0.25 * fade)
                hits += 1
        else:
            for b in (0, 1, 2, 3):
                place(kick, ka, base + b, 0.95)
                hits += 1
            if section in ("Drop", "Drop2"):
                place(kick, kb, base, 0.32 if section == "Drop" else 0.42)
                hits += 1
                place(kick, ka, base + 1.5, 0.38)
                place(kick, ka, base + 3.5, 0.34)
                hits += 2
                if bar % 2 == 1:
                    place(kick, ka, base + 2.25, 0.30)
                    hits += 1
            if section == "Build":
                place(kick, ka, base + 2.5, 0.28)
                hits += 1

        # --- snare/clap ---
        if section in ("Build", "Drop", "Drop2"):
            place(snare, sn, base + 1, 0.9)
            place(snare, sn, base + 3, 0.9)
            hits += 2
            if section != "Build":
                place(snare, cl, base + 3, 0.35)
                hits += 1
                if bar % 4 == 3:
                    place(snare, sn, base + 3.5, 0.45)
                    hits += 1
            if section == "Build" and bar >= bars - 4:
                # subtract hats later; snare ghosts only
                place(snare, cl, base + 1.75, 0.22)
                hits += 1
        if section == "Break" and bar in (4, 12, 20):
            # reverse-ish: place soft snare early in bar
            place(snare, sn[::-1] if len(sn) > 10 else sn, base + 2, 0.25)
            hits += 1

        # --- hats ---
        if section == "Intro":
            for st in range(0, 16, 2):
                place(hats, hc, base + st * 0.25, 0.35)
                hits += 1
        elif section == "Break":
            pass  # subtract hats
        elif section == "Build" and bar >= bars - 4:
            pass  # subtract last 4 bars before drop
        elif section == "Outro":
            if bar < bars * 2 // 3:
                for st in range(0, 16, 2):
                    place(hats, hc, base + st * 0.25, 0.4 * (1 - bar / bars))
                    hits += 1
        else:
            for st in range(16):
                g = 0.62 if st % 2 == 0 else 0.32
                place(hats, hc, base + st * 0.25, g)
                hits += 1
            if bar % 4 == 3 or (section == "Drop2" and bar % 2 == 1):
                place(hats, ho, base + 3.5, 0.55)
                hits += 1
            if section == "Drop2":
                # invert: accent offs
                place(hats, hc, base + 0.125, 0.28)
                hits += 1

        # --- perc ---
        if section in ("Intro", "Break"):
            place(perc, pa, base + 0.75, 0.45)
            place(perc, pa, base + 2.75, 0.40)
            hits += 2
            if section == "Break":
                # tile perc_loop quietly
                place(perc, pl, base, 0.18)
                hits += 1
        if section == "Build":
            place(perc, pl, base, 0.22)
            hits += 1
            place(perc, pb, base + 1.5, 0.35)
            hits += 1
        if section in ("Drop", "Drop2"):
            place(perc, pl, base, 0.28 if section == "Drop" else 0.32)
            hits += 1
            if bar % 8 == 7:
                fill = pc if section == "Drop2" else pb
                for t in np.arange(2.0, 4.0, 0.125):
                    place(perc, fill, base + float(t), 0.38)
                    hits += 1
            elif bar % 4 == 2:
                place(perc, pb if section == "Drop" else pc, base + 2.5, 0.4)
                hits += 1
        if section == "Intro" and bar == 48:  # ~bar 49 absolute ≈ mid-late intro in 64
            place(perc, vo, base, 0.55)
            hits += 1
        if section == "Break" and bar == 8:
            place(perc, vo, base, 0.65)
            hits += 1

    if section == "Intro":
        # progressive HPF open on kick
        kick = hpf_inplace(kick, 80.0) * 0.7 + kick * 0.3
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
    """Render LOOP_BARS of character then tile to full section (fast, arrangement-faithful)."""
    base_bars = min(bars, LOOP_BARS)
    kick, snare, hats, perc, hits = render_drums(section, base_bars, kit)
    acid = render_acid(base_bars, pattern, whisper=whisper, open_=open_, grit=1.9 if whisper else 2.2)
    # scale hit count for tiled length
    reps = max(1, bars // base_bars)
    hits = hits * reps
    kick = tile_buf(kick, base_bars, bars)
    snare = tile_buf(snare, base_bars, bars)
    hats = tile_buf(hats, base_bars, bars)
    perc = tile_buf(perc, base_bars, bars)
    acid = tile_buf(acid, base_bars, bars)
    N = n_for_bars(bars)
    bass = np.zeros(N, dtype=np.float32)
    if section in ("Drop", "Drop2") and "bass_a" in kit:
        for bar in range(0, bars, 8):
            place(bass, kit["bass_a"], bar * 4.0, 0.25)
            hits += 1
    # section-scale envelopes
    if section == "Intro":
        env = np.linspace(0.55, 1.0, N, dtype=np.float32)
        kick *= env
        acid *= np.linspace(0.4, 1.0, N, dtype=np.float32)
    elif section == "Outro":
        env = np.linspace(1.0, 0.25, N, dtype=np.float32)
        kick *= env
        snare *= env
        hats *= env
        acid *= env
    elif section == "Break":
        # dig first half
        half = N // 2
        kick[:half] *= 0.15
        hats[:half] *= 0.1
    kick_g = {"Intro": 1.0, "Build": 1.08, "Drop": 1.12, "Break": 0.9, "Drop2": 1.15, "Outro": 1.0}[section]
    mix = (
        kick * kick_g
        + snare * 0.88
        + hats * 0.55
        + perc * 0.45
        + acid * acid_g
        + bass * 0.35
    )
    mix = tanh_drive(mix, 1.05)
    return {
        "kick": kick,
        "snare": snare,
        "hats": hats,
        "perc": perc,
        "acid": acid,
        "mix": mix,
        "hits": hits,
        "bars": bars,
        "n": N,
    }


def load_kit():
    names = [
        "kick_a", "kick_b", "snare_a", "clap_a", "hat_closed", "hat_open",
        "perc_loop", "perc_a", "perc_b", "perc_c", "bass_a", "voice_a",
    ]
    kit = {}
    for n in names:
        p = KIT / f"{n}.wav"
        if not p.exists():
            raise FileNotFoundError(p)
        kit[n] = read_wav(p)
        print("kit", n, "len", len(kit[n]), "peak", float(np.max(np.abs(kit[n]))))
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
    # chunk notes if huge
    chunk = 200
    for i in range(0, len(notes), chunk):
        rr = send("add_notes_to_clip", {"track_index": ti, "clip_index": ci, "notes": notes[i:i+chunk]})
        if rr.get("status") != "success":
            print("FAIL notes", name, rr)
            return False
    print("OK midi", name, "notes", len(notes), "->", ti, ci)
    return True


def snapshot_by_name():
    r = ok(send("get_session_snapshot"), "snapshot")
    tracks = r["tracks"]
    return {t["name"]: t["index"] for t in tracks}, tracks


def main():
    errors = []
    print("=== CueCurrent_167 v2 GREENLIGHT @", BPM, "===")
    kit = load_kit()

    # patterns per section
    patterns = {
        "Intro": acid_pattern_gsm(16701, denser=False),
        "Build": acid_pattern_gsm(16702, denser=False),
        "Drop": acid_pattern_gsm(16703, denser=True),
        "Break": acid_pattern_gsm(16704, denser=False),
        "Drop2": acid_pattern_gsm(16705, denser=True),
        "Outro": acid_pattern_gsm(16706, denser=False),
    }
    acid_gains = {
        "Intro": 0.18,
        "Build": 0.32,
        "Drop": 0.52,
        "Break": 0.28,
        "Drop2": 0.58,
        "Outro": 0.20,
    }

    section_paths = {}
    total_hits = 0
    total_dur = 0.0
    concat_list = OUT / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as flist:
        for name, bars, row in SECTIONS:
            whisper = name in ("Intro", "Outro")
            open_ = name in ("Drop", "Drop2")
            print(f"--- render {name} bars={bars} ---")
            data = render_section_mix(
                name, bars, kit, patterns[name],
                acid_gains[name], whisper=whisper, open_=open_,
            )
            total_hits += data["hits"]
            total_dur += data["n"] / SR
            # write stems + mix
            for key in ("kick", "snare", "hats", "perc", "acid", "mix"):
                fp = SEC / f"{row:02d}_{name}_{key}.wav"
                if key == "mix":
                    write_wav_stereo(fp, data[key], peak=0.90)
                else:
                    write_wav_mono(fp, data[key], peak=0.88)
            section_paths[name] = {
                "row": row,
                "bars": bars,
                "paths": {k: SEC / f"{row:02d}_{name}_{k}.wav" for k in ("kick", "snare", "hats", "perc", "acid", "mix")},
                "hits": data["hits"],
                "dur": data["n"] / SR,
            }
            # also 16-bar loop stems for Live session slots
            loop = render_section_mix(
                name, LOOP_BARS, kit, patterns[name],
                acid_gains[name], whisper=whisper, open_=open_,
            )
            for key in ("kick", "snare", "hats", "perc", "acid", "mix"):
                fp = SEC / f"loop_{row:02d}_{name}_{key}.wav"
                if key == "mix":
                    write_wav_stereo(fp, loop[key], peak=0.90)
                else:
                    write_wav_mono(fp, loop[key], peak=0.88)
            section_paths[name]["loop"] = {k: SEC / f"loop_{row:02d}_{name}_{k}.wav" for k in ("kick", "snare", "hats", "perc", "acid", "mix")}
            p = str(section_paths[name]["paths"]["mix"]).replace("\\", "/")
            flist.write(f"file '{p}'\n")
            dens = data["hits"] / (data["n"] / SR)
            print(f"  hits={data['hits']} dens={dens:.2f}/s dur={data['n']/SR:.1f}s")

    onset_density = total_hits / total_dur if total_dur else 0
    print(f"TOTAL hits={total_hits} dur={total_dur:.1f}s onset≈{onset_density:.2f}/s")

    # --- bounce concat + loudnorm ---
    raw = OUT / "cue167_v2_concat.wav"
    loud = OUT / "cue167_v2_loud.wav"
    ff = "ffmpeg"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw)], check=True, capture_output=True)
    try:
        subprocess.run([
            ff, "-y", "-i", str(raw),
            "-af", "loudnorm=I=-9:TP=-1.0:LRA=6,highpass=f=30,alimiter=limit=0.94",
            "-ar", "44100", str(loud),
        ], check=True, capture_output=True)
        src = loud
    except Exception as e:
        print("loudnorm fail", e)
        src = raw
    subprocess.run([ff, "-y", "-i", str(src), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3_DL)], check=True, capture_output=True)
    shutil.copy2(src, WAV_DL)
    # probe duration
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

    # --- Ableton session ---
    ok(send("set_tempo", {"tempo": BPM}), "tempo 167")
    try:
        ok(send("stop_playback"), "stop")
    except Exception:
        pass

    by, tracks = snapshot_by_name()
    print("TRACKS", by)

    # Prefer named tracks; fall back by index from known map
    def ti(*names, default=None):
        for n in names:
            if n in by:
                return by[n]
        return default

    t_acid_midi = ti("Drift Acid G#m", "Acid 303 Poly", default=0)
    t_drum_midi = ti("ESX Drum Rack", default=1)
    t_kick = ti("CueKick", default=2)
    t_hats = ti("CueHats", default=3)
    t_bass_midi = ti("Drift Bass G#m", default=5)
    t_perc = ti("CueSmp26", "ESX Stretch", default=6)
    t_acid_aud = ti("Acid 303", default=9)
    t_vox = ti("ESX VoxAud", default=11)
    t_snare = ti("CueSnare", default=12)
    t_mix = ti("E-DrumLP", "CueMix", default=15)

    # Ensure Drift on acid midi track
    try:
        r = send("load_instrument_or_effect", {"track_index": t_acid_midi, "uri": "query:Synths#Drift"})
        print("Drift load", r.get("status"), r.get("message", r.get("result")))
    except Exception as e:
        print("Drift load warn", e)
        errors.append(str(e))

    try:
        send("set_track_name", {"track_index": t_acid_midi, "name": "Drift Acid G#m"})
        send("set_track_name", {"track_index": t_drum_midi, "name": "ESX Drum Rack"})
    except Exception:
        pass

    # Load kit one-shots onto spare audio slots for Drum Rack drag (CueSmp4/6/20)
    oneshot_targets = [
        (ti("CueSmp4", default=10), 0, KIT / "kick_a.wav", "kit_kick_a"),
        (ti("CueSmp6", default=14), 0, KIT / "snare_a.wav", "kit_snare_a"),
        (ti("CueSmp20", default=13), 0, KIT / "hat_closed.wav", "kit_hat_c"),
        (ti("CueSmp4", default=10), 1, KIT / "kick_b.wav", "kit_kick_b"),
        (ti("CueSmp6", default=14), 1, KIT / "clap_a.wav", "kit_clap_a"),
        (ti("CueSmp20", default=13), 1, KIT / "hat_open.wav", "kit_hat_o"),
        (ti("CueSmp4", default=10), 2, KIT / "perc_a.wav", "kit_perc_a"),
        (ti("CueSmp6", default=14), 2, KIT / "perc_b.wav", "kit_perc_b"),
        (ti("CueSmp20", default=13), 2, KIT / "perc_c.wav", "kit_perc_c"),
        (ti("CueSmp4", default=10), 3, KIT / "voice_a.wav", "kit_voice_a"),
        (ti("CueSmp6", default=14), 3, KIT / "bass_a.wav", "kit_bass_a"),
        (ti("CueSmp20", default=13), 3, KIT / "perc_loop.wav", "kit_perc_loop"),
    ]
    for ti_, ci, path, nm in oneshot_targets:
        if ti_ is None:
            continue
        try:
            load_audio(ti_, ci, path, nm)
        except Exception as e:
            print("oneshot warn", nm, e)
            errors.append(f"oneshot {nm}: {e}")

    # Section loops into main stems + MIDI
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
        if t_acid_aud is not None:
            load_audio(t_acid_aud, row, loops["acid"], f"{name}_acid")
        if t_mix is not None:
            load_audio(t_mix, row, loops["mix"], f"{name}_mix")
        # MIDI Drift
        denser = name in ("Drop", "Drop2")
        midi = make_acid_midi(patterns[name], bars=LOOP_BARS, denser=denser)
        if name == "Intro":
            # whisper: fewer notes
            midi = [n for i, n in enumerate(midi) if i % 3 != 1]
        put_midi(t_acid_midi, row, clip_len, f"{name}_drift_Gsm", midi)
        # Drum Rack MIDI
        put_midi(t_drum_midi, row, clip_len, f"{name}_kit_midi", make_drum_midi(name, LOOP_BARS))
        # locator at cumulative time
        t0 = sum(SECTIONS[i][1] for i in range(row)) * 4.0
        send("create_locator", {"name": f"{row}_{name}", "time": float(t0)})

    # Arrange: duplicate Drop loop across arrangement for spine (best-effort)
    try:
        for row_name, bars, row in SECTIONS:
            start = sum(SECTIONS[i][1] for i in range(row)) * 4.0
            # place several 16-bar copies to fill section
            n_copies = max(1, bars // LOOP_BARS)
            for c in range(n_copies):
                for tlabel, tidx in [
                    ("kick", t_kick), ("hats", t_hats), ("snare", t_snare),
                    ("perc", t_perc), ("acid", t_acid_aud), ("mix", t_mix),
                    ("drift", t_acid_midi), ("drums", t_drum_midi),
                ]:
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

    # Fire Drop scene for Live hear-now
    FIRE = 2  # Drop
    for tidx in (t_kick, t_hats, t_snare, t_perc, t_acid_aud, t_acid_midi, t_drum_midi, t_mix):
        if tidx is None:
            continue
        r = send("fire_clip", {"track_index": tidx, "clip_index": FIRE})
        print("fire", tidx, r.get("status"))
    ok(send("start_playback"), "start_playback")

    # NOTES + MAP
    notes = f"""# EvAIx CueCurrent_167 v2 — NOTES

**BPM:** 167 · **Key:** G#m · **Length:** ~{mp3_dur:.1f}s ({mp3_dur/60:.2f} min)
**Kit:** CueCurrent_167_kit (ESX factory BD-6/5, SD-3, Clap-6, HH-1C/3O + Chronic Mn loop + Twolone perc + Voice-5 + BoostSaw seed)
**Acid:** Ableton Drift MIDI on track "Drift Acid G#m" + matching resonant saw/square audio stem (slides+accents, presence ~700Hz–3k). NOT CueCurrent acid_preview / toy bed.

## Form (ARRANGEMENT.md)
| Section | Bars | ~time | Energy |
|---------|------|-------|--------|
| Intro | 1–64 | 0:00–1:32 | filtered kick roll, whisper acid |
| Build | 65–96 | 1:32–2:18 | snare in, perc_loop, hats peel last 4 |
| Drop | 97–160 | 2:18–4:10 | kick+kick_b, 16th hats, Drift main |
| Break | 161–192 | 4:10–4:56 | subtract kick, perc+filtered acid, voice |
| Drop2 | 193–256 | 4:56–6:28 | heavier, metallic perc_c, open acid |
| Outro | 257–288 | 6:28–6:54 | peel to DJ stub |

## Metrics vs USER_CURRENT_TRACK_ref
| | Ref | v2 |
|--|-----|----|
| BPM | 167 (best candidate) | 167 |
| Duration | 419.6s (~6:59) | ~{mp3_dur:.1f}s |
| Onset density | ~5.58/s (stated) | ~{onset_density:.2f}/s |
| Source | USER_CURRENT_TRACK_ref.mp3 | ESX kit WAVs + Drift acid (no toy preview) |

## Deliverables
- MP3: `{MP3_DL}`
- WAV: `{WAV_DL}`
- Session: Live set currently open @167 with section clips rows 0–5 + locators (save as CueCurrent_167_v2.als)
- Kit path: `{KIT}`
"""
    NOTES_DL.write_text(notes, encoding="utf-8")
    amap = f"""# CueCurrent_167 v2 — Ableton session map

Tempo: **167** · Key: **G#m** · Scenes/rows 0–5 = Intro, Build, Drop, Break, Drop2, Outro (16-bar loops)

| Idx | Track | Role |
|-----|-------|------|
| {t_acid_midi} | Drift Acid G#m | MIDI Drift acid (poly/slides) |
| {t_drum_midi} | ESX Drum Rack | MIDI kit map (36/37/38/39/42/46/41/43/45/60) — load oneshots from CueSmp* clips |
| {t_kick} | CueKick | kick stems per section |
| {t_hats} | CueHats | hat stems |
| {t_snare} | CueSnare | snare/clap stems |
| {t_perc} | perc audio | perc/loop stems |
| {t_acid_aud} | Acid 303 | acid audio mirror of Drift character |
| {t_mix} | mix bus clip | section mix reference |
| 10/13/14 | CueSmp* | **kit one-shots** for Drum Rack pads |

Locators: 0_Intro, 1_Build, 2_Drop, 3_Break, 4_Drop2, 5_Outro at section starts.
Arrangement: session clips duplicated to fill ~288 bars (best-effort via MCP).

Save Live set to: Documents/Ableton/ or User Library as `CueCurrent_167_v2.als`.
"""
    MAP_DL.write_text(amap, encoding="utf-8")
    try:
        ALS_NOTE.parent.mkdir(parents=True, exist_ok=True)
        ALS_NOTE.write_text(amap, encoding="utf-8")
    except Exception as e:
        print("als note warn", e)

    summary = {
        "mp3": str(MP3_DL),
        "wav": str(WAV_DL),
        "notes": str(NOTES_DL),
        "map": str(MAP_DL),
        "mp3_dur_s": mp3_dur,
        "onset_density": onset_density,
        "total_hits": total_hits,
        "bpm": BPM,
        "key": "G#m",
        "kit": str(KIT),
        "errors": errors,
    }
    (OUT / "v2_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("=== SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
