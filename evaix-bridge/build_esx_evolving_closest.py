# -*- coding: utf-8 -*-
"""EvAIx ESX EvolvingClosest — free-party closest to AUSTRALOOPITEKUS Evolving Wild.

ONLY ESX factory samples + Ableton Live Intro Drift (no Digitone/Rytm).
Kick-dominated mix: hats/ohat/ride/perc baked at -12..-18 dB vs kick peaks.
SinKick only (+ optional tiny BD <=0.15). Dark short hats. No Atm/Mental/Syn beds.
"""
from __future__ import annotations

import array
import json
import math
import shutil
import socket
import subprocess
import wave
from pathlib import Path

SR = 44100
BPM = 162.0
BARS = 8
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR)
FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set\ew162_closest")
OUT.mkdir(parents=True, exist_ok=True)
ROOT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set")
HOST, PORT = "127.0.0.1", 9877
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_ESX_EvolvingClosest_162.mp3")
MP3_COPY = ROOT / "EvAIx_ESX_EvolvingClosest_162.mp3"
LOG = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\_ew_closest_build_log.txt")

# Explicit bus peaks (CRITICAL kick-heavy balance)
PEAK_KICK = 0.90
PEAK_HATS = 0.12
PEAK_OHAT = 0.10
PEAK_RIDE = 0.10
PEAK_PERC = 0.14
BD_LAYER_GAIN = 0.12  # optional tiny BD under SinKick, max 0.15

SCENES = [
    (0, "Intro_Silence"),
    (1, "Kick_In"),
    (2, "Hats_Sparse"),
    (3, "Acid_Dark"),
    (4, "Drop"),
    (5, "Tribal_Whisper"),
    (6, "Break_Fragile"),
    (7, "Peak_Outro"),
]

GAINS_REPORT = {}


def read_wav(path: Path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nframes)
    data = array.array("h")
    data.frombytes(raw)
    samples = [x / 32768.0 for x in data]
    if ch == 2:
        samples = [(samples[i] + samples[i + 1]) * 0.5 for i in range(0, len(samples), 2)]
    if sr != SR:
        ratio = SR / sr
        new_n = int(len(samples) * ratio)
        out = [0.0] * new_n
        for i in range(new_n):
            src = i / ratio
            j = int(src)
            f = src - j
            if j + 1 < len(samples):
                out[i] = samples[j] * (1 - f) + samples[j + 1] * f
            elif j < len(samples):
                out[i] = samples[j]
        samples = out
    thr = 0.008
    a = 0
    while a < len(samples) and abs(samples[a]) < thr:
        a += 1
    b = len(samples) - 1
    while b > a and abs(samples[b]) < thr:
        b -= 1
    return samples[a : b + 1] if b > a else samples


def drive(samples, amt=1.5):
    return [math.tanh(x * amt) for x in samples]


def darken(samples, cutoff=0.18):
    """Simple one-pole lowpass for darker hats/acid feel."""
    out = []
    y = 0.0
    a = cutoff
    for x in samples:
        y = y + a * (x - y)
        out.append(y)
    return out


def shorten(samples, max_ms=45.0, fade_ms=8.0):
    max_n = int(SR * max_ms / 1000.0)
    fade_n = int(SR * fade_ms / 1000.0)
    s = samples[:max_n]
    if fade_n > 0 and len(s) > fade_n:
        for i in range(fade_n):
            s[-(i + 1)] *= i / fade_n
    return s


def scale_to_peak(buf, target):
    peak = max((abs(x) for x in buf), default=0.0)
    if peak < 1e-9:
        return list(buf), 0.0
    g = target / peak
    return [x * g for x in buf], peak


def write_wav_abs(path: Path, mono, clip=0.99):
    """Write mono wav preserving absolute levels (no normalize-to-0.92)."""
    if not mono:
        mono = [0.0]
    peak = max(abs(x) for x in mono) if mono else 0.0
    frames = array.array(
        "h",
        [max(-32767, min(32767, int(max(-clip, min(clip, x)) * 32767))) for x in mono],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(frames.tobytes())
    try:
        tmp.replace(path)
    except Exception:
        alt = path.with_name(path.stem + "_v2" + path.suffix)
        tmp.replace(alt)
        print("wrote ALT", alt.name, "peak", round(peak, 4))
        return peak
    print("wrote", path.name, "peak", round(peak, 4))
    return peak


def place(buf, sample, beat, gain=1.0):
    start = int(beat * 60.0 / BPM * SR)
    for i, v in enumerate(sample):
        j = start + i
        if 0 <= j < len(buf):
            buf[j] += v * gain


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
        timeout=90,
    )
    if r.get("status") != "success":
        print("FAIL audio", name, r.get("message", r))
        return False
    send("set_clip_name", {"track_index": track_index, "clip_index": clip_index, "name": name})
    print("OK audio", name, "->", track_index, clip_index)
    return True


def put_midi(track_index, clip_index, length, name, notes):
    safe_delete(track_index, clip_index)
    r = send("create_clip", {"track_index": track_index, "clip_index": clip_index, "length": length})
    if r.get("status") != "success":
        print("FAIL create midi", name, r.get("message", r))
        return False
    send("set_clip_name", {"track_index": track_index, "clip_index": clip_index, "name": name})
    r2 = send("add_notes_to_clip", {"track_index": track_index, "clip_index": clip_index, "notes": notes})
    if r2.get("status") != "success":
        print("FAIL notes", name, r2.get("message", r2))
        return False
    print("OK midi", name, "n=", len(notes))
    return True


def make_acid_notes(bars=4, muted=False, harder=False, open_gate=False, sparse=False):
    """Tholin E major DARKER: lower octave emphasis, gates ~60-70%, fewer accents."""
    # 16th = 0.25 beats; 65% gate ~= 0.1625
    gate = 0.17 if open_gate else 0.155
    slide = 0.28 if open_gate else 0.22
    if muted:
        gate = 0.10
        slide = 0.16
    # fewer accents, lower pitches (E1/E2 family)
    # E1=28, G#1=32, B1=35, E2=40, B1, A1=33, G#1, E1, B0=23
    steps = [
        (0, 28, 95, gate),
        (2, 32, 88, slide),
        (4, 35, 105, gate),  # mild accent
        (8, 35, 90, gate),
        (9, 33, 85, slide),
        (11, 32, 88, gate),
        (13, 28, 100, gate),  # mild accent
    ]
    if not sparse and harder:
        steps.insert(3, (6, 40, 92, gate))  # light E2
        steps.append((15, 23, 80, slide))
    elif not sparse and open_gate and not muted:
        steps.insert(3, (6, 40, 85, gate))
    vel_mod = -28 if muted else (8 if harder else 0)
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        for step, pitch, vel, dur in steps:
            notes.append(
                {
                    "pitch": pitch,
                    "start_time": base + step * 0.25,
                    "duration": dur,
                    "velocity": max(1, min(127, vel + vel_mod)),
                    "mute": False,
                }
            )
    return notes


def make_bass_notes(bars=4, muted=False, harder=False, open_gate=False, sparse=False):
    """Bass layer PRIMARY — another octave down, stronger than lead."""
    notes = make_acid_notes(bars=bars, muted=muted, harder=harder, open_gate=open_gate, sparse=sparse)
    for n in notes:
        n["pitch"] = max(0, n["pitch"] - 12)
        n["velocity"] = max(1, min(127, int(n["velocity"] * 1.05)))
    return notes


def make_lead_notes(bars=4, muted=False, harder=False, open_gate=False, sparse=False):
    """Lead quieter than bass — original E2 range but soft."""
    notes = make_acid_notes(bars=bars, muted=muted, harder=harder, open_gate=open_gate, sparse=sparse)
    for n in notes:
        n["pitch"] = min(127, n["pitch"] + 12)  # up from E1 family -> E2
        n["velocity"] = max(1, int(n["velocity"] * 0.55))  # quieter than bass
    return notes


def synth_acid_tone(bars_total, muted=False, harder=False, with_bass=True, lead_quiet=True):
    """Dark rendered acid: saw through soft tanh, low cutoff feel."""
    n = int(bars_total * 4 * 60.0 / BPM * SR)
    buf = [0.0] * n
    bass = make_bass_notes(bars=bars_total, muted=muted, harder=harder, open_gate=not muted)
    lead = make_lead_notes(bars=bars_total, muted=muted, harder=harder, open_gate=not muted)
    notes = list(bass)
    if lead_quiet:
        notes = notes + lead
    for note in notes:
        pitch = note["pitch"]
        freq = 440.0 * (2.0 ** ((pitch - 69) / 12.0))
        start = int(note["start_time"] * 60.0 / BPM * SR)
        dur_samp = max(1, int(note["duration"] * 60.0 / BPM * SR))
        vel = note["velocity"] / 127.0
        is_bass = pitch < 36
        amp = 0.22 if is_bass else 0.10
        for i in range(dur_samp):
            j = start + i
            if j >= n:
                break
            t = i / SR
            phase = 2 * math.pi * freq * t
            saw = 0.0
            # fewer harmonics = darker
            for h in range(1, 5):
                saw += math.sin(phase * h) / (h * h)
            env = math.exp(-t * (9.0 if muted else 5.5))
            dark = 0.35 + 0.65 * math.exp(-t * 12.0)
            buf[j] += saw * amp * vel * env * dark * (1.1 if harder else 1.0)
    # soft lowpass
    buf = darken(buf, cutoff=0.12)
    return [math.tanh(x * 1.15) for x in buf]


def concat_mono(parts):
    out = []
    for p in parts:
        out.extend(p)
    return out


def mono_to_stereo_wav(path: Path, mono):
    peak = max(1e-9, max(abs(x) for x in mono) if mono else 1e-9)
    scale = 0.92 / peak
    st = array.array("h")
    for x in mono:
        v = max(-32767, min(32767, int(x * scale * 32767)))
        st.append(v)
        st.append(v)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())


def generate_drums():
    print("=== CLOSEST drum loops @", BPM, "SinKick + tiny BD, kick-heavy peaks ===")
    kick_s = drive(read_wav(FACTORY / "146_SinKick.wav"), 1.70)
    # optional tiny BD layer
    bd = None
    for cand in ("000_BD-1.wav", "007_BD-8.wav", "008_BD-9.wav"):
        p = FACTORY / cand
        if p.exists():
            bd = darken(read_wav(p), 0.25)
            GAINS_REPORT["bd_layer_sample"] = cand
            break
    # darker/shorter hats
    hhc = shorten(darken(read_wav(FACTORY / "064_HH-6C.wav"), 0.22), max_ms=38)
    hho = shorten(darken(read_wav(FACTORY / "065_HH-6O.wav"), 0.18), max_ms=70, fade_ms=15)
    ride = shorten(darken(read_wav(FACTORY / "070_Ride-3.wav"), 0.15), max_ms=90, fade_ms=20)
    junk = darken(read_wav(FACTORY / "092_JunkPerc.wav"), 0.20)
    claves = darken(read_wav(FACTORY / "087_Claves.wav"), 0.25)

    trk_k = [0.0] * N
    trk_k_hard = [0.0] * N
    trk_h_sp = [0.0] * N
    trk_h_dn = [0.0] * N
    trk_h_hard = [0.0] * N
    trk_oh = [0.0] * N
    trk_oh_hard = [0.0] * N
    trk_ride = [0.0] * N
    trk_perc_l = [0.0] * N
    trk_perc_t = [0.0] * N
    trk_perc_h = [0.0] * N
    silent = [0.0] * N

    for bar in range(BARS):
        base = bar * 4.0
        for step in (0, 4, 8, 12):
            beat = base + step * 0.25
            place(trk_k, kick_s, beat, 1.0)
            place(trk_k_hard, kick_s, beat, 1.12)
            if bd is not None:
                place(trk_k, bd, beat, BD_LAYER_GAIN)
                place(trk_k_hard, bd, beat, BD_LAYER_GAIN * 1.05)
        # sparse hats: only on beats (very quiet after peak scale)
        for step in (0, 4, 8, 12):
            place(trk_h_sp, hhc, base + step * 0.25, 0.85)
        # dense: 8ths, still will be peak-scaled to 0.12
        for i in range(0, 16, 2):
            vel = 0.80 if (i % 4 == 0) else 0.55
            place(trk_h_dn, hhc, base + i * 0.25, vel)
            place(trk_h_hard, hhc, base + i * 0.25, vel * 1.1)
        for step in (6, 14):  # fewer ohats — dark, not busy
            place(trk_oh, hho, base + step * 0.25, 0.75)
            place(trk_oh_hard, hho, base + step * 0.25, 0.88)
        for step in (0, 8):
            place(trk_ride, ride, base + step * 0.25, 0.60)
        # whisper perc
        place(trk_perc_l, claves, base + 3 * 0.25, 0.55)
        place(trk_perc_t, junk, base + 3 * 0.25, 0.70)
        place(trk_perc_t, claves, base + 11 * 0.25, 0.50)
        place(trk_perc_h, junk, base + 3 * 0.25, 0.85)
        place(trk_perc_h, claves, base + 11 * 0.25, 0.65)
        place(trk_perc_h, junk, base + 7 * 0.25, 0.35)

    def pack(name, buf, target):
        scaled, raw_peak = scale_to_peak(buf, target)
        out_peak = write_wav_abs(OUT / name, scaled)
        GAINS_REPORT[name] = {
            "target_peak": target,
            "raw_peak_before_scale": round(raw_peak, 4),
            "written_peak": round(out_peak, 4),
        }
        return scaled

    files = {
        "ewc_silent_162.wav": pack("ewc_silent_162.wav", silent, 0.0) or silent,
        "ewc_kick_162.wav": pack("ewc_kick_162.wav", trk_k, PEAK_KICK),
        "ewc_kick_hard_162.wav": pack("ewc_kick_hard_162.wav", trk_k_hard, min(0.95, PEAK_KICK * 1.05)),
        "ewc_hats_sparse_162.wav": pack("ewc_hats_sparse_162.wav", trk_h_sp, PEAK_HATS),
        "ewc_hats_dense_162.wav": pack("ewc_hats_dense_162.wav", trk_h_dn, PEAK_HATS),
        "ewc_hats_hard_162.wav": pack("ewc_hats_hard_162.wav", trk_h_hard, PEAK_HATS * 1.05),
        "ewc_ohat_162.wav": pack("ewc_ohat_162.wav", trk_oh, PEAK_OHAT),
        "ewc_ohat_hard_162.wav": pack("ewc_ohat_hard_162.wav", trk_oh_hard, PEAK_OHAT * 1.05),
        "ewc_ride_162.wav": pack("ewc_ride_162.wav", trk_ride, PEAK_RIDE),
        "ewc_perc_light_162.wav": pack("ewc_perc_light_162.wav", trk_perc_l, PEAK_PERC * 0.75),
        "ewc_perc_tribal_162.wav": pack("ewc_perc_tribal_162.wav", trk_perc_t, PEAK_PERC),
        "ewc_perc_hard_162.wav": pack("ewc_perc_hard_162.wav", trk_perc_h, PEAK_PERC * 1.05),
    }
    GAINS_REPORT["BD_LAYER_GAIN"] = BD_LAYER_GAIN
    GAINS_REPORT["targets"] = {
        "kick": PEAK_KICK,
        "hats": PEAK_HATS,
        "ohat": PEAK_OHAT,
        "ride": PEAK_RIDE,
        "perc": PEAK_PERC,
    }
    print("GAINS", json.dumps(GAINS_REPORT["targets"]))
    return files


def mix_layers(layers, bars=8):
    n = int(bars * 4 * 60.0 / BPM * SR)
    out = [0.0] * n
    for buf, g in layers:
        ln = len(buf)
        if ln == 0:
            continue
        for i in range(n):
            out[i] += buf[i % ln] * g
    return [math.tanh(x * 1.02) for x in out]


def build_morph_mp3():
    print("=== CLOSEST morph MP3 (kick-heavy + dark acid) ===")
    kick = read_wav(OUT / "ewc_kick_162.wav")
    hats_sp = read_wav(OUT / "ewc_hats_sparse_162.wav")
    hats_dn = read_wav(OUT / "ewc_hats_dense_162.wav")
    hats_h = read_wav(OUT / "ewc_hats_hard_162.wav")
    ohat = read_wav(OUT / "ewc_ohat_162.wav")
    ohat_h = read_wav(OUT / "ewc_ohat_hard_162.wav")
    ride = read_wav(OUT / "ewc_ride_162.wav")
    perc_l = read_wav(OUT / "ewc_perc_light_162.wav")
    perc_t = read_wav(OUT / "ewc_perc_tribal_162.wav")
    perc_h = read_wav(OUT / "ewc_perc_hard_162.wav")
    kick_h = read_wav(OUT / "ewc_kick_hard_162.wav")

    silent = [0.0] * N
    # already peak-baked; mix at unity (1.0) to keep kick king
    sec_intro = silent[:]
    sec_kick = mix_layers([(kick, 1.0)], 8)
    sec_hats = mix_layers([(kick, 1.0), (hats_sp, 1.0)], 8)

    acid8 = synth_acid_tone(8, muted=True, with_bass=True, lead_quiet=True)
    drums_acid = mix_layers([(kick, 1.0), (hats_sp, 1.0)], 8)
    # acid under kick — scale acid so peak ~0.25 vs kick 0.9
    acid8_p = max(1e-9, max(abs(x) for x in acid8))
    acid8_g = 0.22 / acid8_p
    sec_acid = [drums_acid[i] + acid8[i] * acid8_g for i in range(N)]

    acid16 = synth_acid_tone(16, muted=False, harder=False, with_bass=True)
    acid16_p = max(1e-9, max(abs(x) for x in acid16))
    acid16_g = 0.28 / acid16_p
    drop_drums = mix_layers([(kick, 1.0), (hats_dn, 1.0), (ohat, 1.0), (perc_l, 1.0)], 16)
    sec_drop = [drop_drums[i] + acid16[i] * acid16_g for i in range(len(drop_drums))]

    tribal_drums = mix_layers([(kick, 1.0), (hats_dn, 1.0), (ohat, 1.0), (perc_t, 1.0)], 8)
    acid_tr = synth_acid_tone(8, muted=False, with_bass=True)
    at_p = max(1e-9, max(abs(x) for x in acid_tr))
    sec_tribal = [tribal_drums[i] + acid_tr[i] * (0.24 / at_p) for i in range(N)]

    # break: kick OUT, fragile acid + whisper ride
    acid_break = synth_acid_tone(8, muted=False, harder=False, with_bass=True, lead_quiet=True)
    ab_p = max(1e-9, max(abs(x) for x in acid_break))
    break_drums = mix_layers([(ride, 1.0)], 8)
    sec_break = [break_drums[i] + acid_break[i] * (0.30 / ab_p) for i in range(N)]

    acid_peak = synth_acid_tone(16, muted=False, harder=True, with_bass=True)
    ap_p = max(1e-9, max(abs(x) for x in acid_peak))
    peak_drums = mix_layers([(kick_h, 1.0), (hats_h, 1.0), (ohat_h, 1.0), (perc_h, 1.0)], 16)
    sec_peak = [peak_drums[i] + acid_peak[i] * (0.26 / ap_p) for i in range(len(peak_drums))]

    # outro strip: kick only then silence
    outro = mix_layers([(kick, 1.0)], 8)
    half = len(outro) // 2
    for i in range(half, len(outro)):
        outro[i] *= max(0.0, 1.0 - (i - half) / max(1, len(outro) - half))
    sec_outro = outro

    morph = concat_mono(
        [sec_intro, sec_kick, sec_hats, sec_acid, sec_drop, sec_tribal, sec_break, sec_peak, sec_outro]
    )
    st = OUT / "ewc_morph_162_st.wav"
    mono_to_stereo_wav(st, morph)
    write_wav_abs(OUT / "ewc_morph_162.wav", morph)
    ff = shutil.which("ffmpeg") or r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
    subprocess.run(
        [ff, "-y", "-i", str(st), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3)],
        check=True,
        capture_output=True,
    )
    shutil.copy2(MP3, MP3_COPY)
    print("MP3", MP3, "size", MP3.stat().st_size)


def main():
    errors = []
    generate_drums()
    try:
        build_morph_mp3()
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)

    print("=== Ableton ESX EvolvingClosest ===")
    snap = ok(send("get_session_snapshot", {"include_devices": False}, timeout=60), "snapshot")
    if not snap:
        print("ABORT no snapshot")
        return

    ok(send("set_tempo", {"tempo": BPM}), "tempo 162")
    send("start_playback")

    by = {t["name"]: t["index"] for t in snap["tracks"]}
    print("tracks:", by)

    def _idx(*names):
        for n in names:
            if n in by:
                return by[n]
        return None

    acid_idx = _idx("Acid 303 Poly", "1-Drift", "Drift")
    bass_idx = _idx("Tholin Bass", "6-MIDI")
    if acid_idx is not None and "Acid 303 Poly" not in by:
        send("set_track_name", {"track_index": acid_idx, "name": "Acid 303 Poly"})
        by["Acid 303 Poly"] = acid_idx
    kick_idx = by.get("E-Kick")
    hats_idx = by.get("E-Hats")
    ohat_idx = by.get("E-OHat") or by.get("E-Snare")
    perc_idx = by.get("E-Perc")
    atm_idx = by.get("E-Atm")
    mental_idx = by.get("E-Mental")
    syn_idx = by.get("E-Syn")

    if ohat_idx is not None and "E-OHat" not in by:
        send("set_track_name", {"track_index": ohat_idx, "name": "E-OHat"})
    if bass_idx is not None:
        send("set_track_name", {"track_index": bass_idx, "name": "Tholin Bass"})

    for idx, label in ((acid_idx, "Acid"), (bass_idx, "Bass")):
        if idx is None:
            continue
        r = send("load_browser_item", {"track_index": idx, "item_uri": "query:Synths#Drift"})
        if r.get("status") != "success":
            r = send("load_instrument_or_effect", {"track_index": idx, "uri": "query:Synths#Drift"})
        print("Drift", label, r.get("status"), r.get("message", ""))

    # MUTE/stop noisy beds forever — clear clips + stop
    noisy_names = (
        "E-Mental",
        "E-Atm",
        "E-Syn",
        "E-Bass",
        "E-DrumLP",
        "ESX Drum Rack",
        "CRISP_e2e_kick",
        "E2S Jam",
        "ESX Jam",
        "ES1 90s",
    )
    for name in noisy_names:
        idx = by.get(name)
        if idx is None:
            continue
        for row in range(8):
            send("stop_clip", {"track_index": idx, "clip_index": row})
            safe_delete(idx, row)
        print("silenced forever", name, idx)

    for row in range(8):
        for idx in (acid_idx, bass_idx, kick_idx, hats_idx, ohat_idx, perc_idx):
            if idx is not None:
                safe_delete(idx, row)

    def scene_drums(row, name, kick=None, hats=None, ohat=None, perc=None):
        if kick_idx is not None:
            if kick:
                load_audio(kick_idx, row, OUT / kick, f"{name}_kick")
            else:
                safe_delete(kick_idx, row)
        if hats_idx is not None:
            if hats:
                load_audio(hats_idx, row, OUT / hats, f"{name}_hats")
            else:
                safe_delete(hats_idx, row)
        if ohat_idx is not None:
            if ohat:
                load_audio(ohat_idx, row, OUT / ohat, f"{name}_oh")
            else:
                safe_delete(ohat_idx, row)
        if perc_idx is not None:
            if perc:
                load_audio(perc_idx, row, OUT / perc, f"{name}_perc")
            else:
                safe_delete(perc_idx, row)

    def scene_acid(row, name, include=True, muted=False, harder=False, open_gate=False, dual=False, sparse=False):
        # bass layer PRIMARY on Tholin Bass; lead quieter on Acid 303 Poly
        if acid_idx is not None:
            if include:
                put_midi(
                    acid_idx,
                    row,
                    16.0,
                    f"{name}_acid",
                    make_lead_notes(4, muted=muted, harder=harder, open_gate=open_gate, sparse=sparse)
                    if dual
                    else make_acid_notes(4, muted=muted, harder=harder, open_gate=open_gate, sparse=sparse),
                )
            else:
                safe_delete(acid_idx, row)
        if bass_idx is not None:
            if include and (dual or True) and include:
                # Always put bass layer when acid present — bass primary for dark feel
                # except pure silence scenes
                put_midi(
                    bass_idx,
                    row,
                    16.0,
                    f"{name}_bass",
                    make_bass_notes(4, muted=muted, harder=harder, open_gate=open_gate, sparse=sparse),
                )
            else:
                safe_delete(bass_idx, row)
        if not include and bass_idx is not None:
            safe_delete(bass_idx, row)

    # 0 Intro almost silence
    scene_drums(0, "Intro_Silence")
    scene_acid(0, "Intro_Silence", include=False)

    # 1 Kick only
    scene_drums(1, "Kick_In", kick="ewc_kick_162.wav")
    scene_acid(1, "Kick_In", include=False)

    # 2 sparse hats
    scene_drums(2, "Hats_Sparse", kick="ewc_kick_162.wav", hats="ewc_hats_sparse_162.wav")
    scene_acid(2, "Hats_Sparse", include=False)

    # 3 dark acid
    scene_drums(3, "Acid_Dark", kick="ewc_kick_162.wav", hats="ewc_hats_sparse_162.wav")
    scene_acid(3, "Acid_Dark", include=True, muted=True, dual=True, sparse=True)

    # 4 Drop — kick-led full
    scene_drums(
        4,
        "Drop",
        kick="ewc_kick_162.wav",
        hats="ewc_hats_dense_162.wav",
        ohat="ewc_ohat_162.wav",
        perc="ewc_perc_light_162.wav",
    )
    scene_acid(4, "Drop", include=True, muted=False, open_gate=True, dual=True)

    # 5 tribal whisper
    scene_drums(
        5,
        "Tribal_Whisper",
        kick="ewc_kick_162.wav",
        hats="ewc_hats_dense_162.wav",
        ohat="ewc_ohat_162.wav",
        perc="ewc_perc_tribal_162.wav",
    )
    scene_acid(5, "Tribal_Whisper", include=True, open_gate=True, dual=True)

    # 6 break — kick out, acid fragile
    scene_drums(6, "Break_Fragile", ohat="ewc_ride_162.wav")
    scene_acid(6, "Break_Fragile", include=True, open_gate=True, dual=True, sparse=True)

    # 7 peak still kick king (+ outro strip encoded in MP3)
    scene_drums(
        7,
        "Peak_Outro",
        kick="ewc_kick_hard_162.wav",
        hats="ewc_hats_hard_162.wav",
        ohat="ewc_ohat_hard_162.wav",
        perc="ewc_perc_hard_162.wav",
    )
    scene_acid(7, "Peak_Outro", include=True, harder=True, open_gate=True, dual=True)

    send("start_playback")

    drop_row = 4
    fired = []
    for label, idx in [
        ("Acid 303 Poly", acid_idx),
        ("Tholin Bass", bass_idx),
        ("E-Kick", kick_idx),
        ("E-Hats", hats_idx),
        ("E-OHat", ohat_idx),
        ("E-Perc", perc_idx),
    ]:
        if idx is None:
            continue
        r = send("fire_clip", {"track_index": idx, "clip_index": drop_row})
        if r.get("status") == "success":
            fired.append(f"{label}@{drop_row}")
            print("FIRE", label)
        else:
            errors.append(f"fire {label}: {r.get('message')}")
            print("FAIL fire", label, r.get("message"))

    ok(send("start_playback"), "start playback keep")
    send("start_playback")

    info = send("get_session_info")
    res = info.get("result") or info
    tempo = res.get("tempo")
    playing = res.get("is_playing")
    mp3_size = MP3.stat().st_size if MP3.exists() else 0

    result = {
        "TEMPO": tempo,
        "IS_PLAYING": playing,
        "SCENES": SCENES,
        "TRACKS_USED": {
            "Acid 303 Poly": acid_idx,
            "Tholin Bass": bass_idx,
            "E-Kick": kick_idx,
            "E-Hats": hats_idx,
            "E-OHat": ohat_idx,
            "E-Perc": perc_idx,
        },
        "DROP_FIRED": fired,
        "GAINS": GAINS_REPORT,
        "MP3_PATH": str(MP3),
        "MP3_SIZE": mp3_size,
        "MP3_COPY": str(MP3_COPY),
        "OUT_WAVS": str(OUT),
        "NO_GRAINY_ATM": True,
        "SINKICK_ONLY": True,
        "BD_LAYER_GAIN": BD_LAYER_GAIN,
        "ERRORS": errors,
    }
    print("==== RESULT ====")
    print(json.dumps(result, indent=2, default=str))
    LOG.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print("DONE EvolvingClosest 162")


if __name__ == "__main__":
    main()
