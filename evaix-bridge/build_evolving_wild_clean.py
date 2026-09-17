# -*- coding: utf-8 -*-
"""EvAIx Evolving Wild CLEAN — 162 BPM Ableton Session (Rytm+Digitone aesthetic).

SinKick-only drums, Tholin E-major dual Drift acid, sparse→dense scene morph.
NO grainy Atm/Mental beds. Session has 8 scene rows (AbletonMCP cannot create more);
full 12-section performance map is encoded in clip names + locators + MP3 morph.
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
OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set\ew162")
OUT.mkdir(parents=True, exist_ok=True)
ROOT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set")
HOST, PORT = "127.0.0.1", 9877
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_EvolvingWild_CleanLive_162.mp3")
MP3_COPY = ROOT / "EvAIx_EvolvingWild_CleanLive_162.mp3"

# Physical Session rows 0..7 (Ableton currently has 8 scenes; cannot create more via MCP)
SCENES = [
    (0, "Intro_Atm"),
    (1, "Kick_In"),
    (2, "Hats_In"),
    (3, "Acid_Muted"),
    (4, "Drop_Clean"),
    (5, "Tribal_Add"),
    (6, "Break_Fragile"),
    (7, "Peak_Full"),
]

CONCEPTUAL_12 = [
    "0 Intro_Atm",
    "1 Kick_In",
    "2 Hats_In",
    "3 Acid_Muted",
    "4 Drop_Clean",
    "5 Tribal_Add",
    "6 Break_Fragile",
    "7 Peak_Full",
    "8 Peak_MuteGame (folded into Peak/MP3)",
    "9 Break2 (folded into Break morph)",
    "10 Return_Hard (Peak_Full harder velocities)",
    "11 Outro_Strip (MP3 outro)",
]


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


def write_wav(path: Path, mono):
    if not mono:
        mono = [0.0]
    peak = max(1e-9, max(abs(x) for x in mono))
    scale = 0.92 / peak if peak > 1e-6 else 1.0
    frames = array.array("h", [max(-32767, min(32767, int(x * scale * 32767))) for x in mono])
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
        # locked destination — keep tmp as final alternate name
        alt = path.with_name(path.stem + "_v2" + path.suffix)
        try:
            tmp.replace(alt)
            print("wrote ALT", alt.name, "peak", round(peak, 4))
            return
        except Exception as e:
            print("write fail", path, e)
            return
    print("wrote", path.name, "peak", round(peak, 4))


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


def make_acid_notes(bars=4, muted=False, harder=False, open_gate=False):
    """Tholin E major: E2, G#2 slide, B2 accent, E3, B2, A2 slide, G#2, E2 accent, B1 slide."""
    gate = 0.22 if open_gate else 0.1875
    slide = 0.50 if open_gate else 0.42
    if muted:
        gate = 0.12
        slide = 0.28
    steps = [
        (0, 40, 100, gate),
        (2, 44, 100, slide),
        (4, 47, 120, gate),
        (6, 52, 105, gate),
        (8, 47, 100, gate),
        (9, 45, 100, slide),
        (11, 44, 100, gate),
        (13, 40, 120, gate),
        (15, 35, 100, slide),
    ]
    vel_mod = -35 if muted else (12 if harder else 0)
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


def make_bass_notes(bars=4, muted=False, harder=False, open_gate=False):
    notes = make_acid_notes(bars=bars, muted=muted, harder=harder, open_gate=open_gate)
    for n in notes:
        n["pitch"] = max(0, n["pitch"] - 12)
        n["velocity"] = max(1, int(n["velocity"] * 0.82))
    return notes


def synth_acid_tone(bars_total, muted=False, harder=False, with_bass=False):
    """Simple Digitone-ish resonant saw for offline MP3 morph (not a grainy pad)."""
    n = int(bars_total * 4 * 60.0 / BPM * SR)
    buf = [0.0] * n
    notes = make_acid_notes(bars=bars_total, muted=muted, harder=harder, open_gate=not muted)
    if with_bass:
        notes = notes + make_bass_notes(bars=bars_total, muted=muted, harder=harder, open_gate=not muted)
    for note in notes:
        pitch = note["pitch"]
        freq = 440.0 * (2.0 ** ((pitch - 69) / 12.0))
        start = int(note["start_time"] * 60.0 / BPM * SR)
        dur_samp = max(1, int(note["duration"] * 60.0 / BPM * SR))
        vel = note["velocity"] / 127.0
        for i in range(dur_samp):
            j = start + i
            if j >= n:
                break
            t = i / SR
            phase = 2 * math.pi * freq * t
            saw = 0.0
            for h in range(1, 8):
                saw += math.sin(phase * h) / h
            env = math.exp(-t * (6.0 if muted else 3.5))
            dark = 0.55 + 0.45 * math.exp(-t * 8.0)
            buf[j] += saw * 0.18 * vel * env * dark * (1.15 if harder else 1.0)
    return [math.tanh(x * 1.2) for x in buf]


def concat_mono(parts):
    out = []
    for p in parts:
        out.extend(p)
    return out


def mono_to_stereo_wav(path: Path, mono):
    peak = max(1e-9, max(abs(x) for x in mono) if mono else 1e-9)
    scale = 0.90 / peak
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
    print("=== CLEAN drum loops @", BPM, "SinKick ONLY ===")
    kick_s = drive(read_wav(FACTORY / "146_SinKick.wav"), 1.65)
    hhc = read_wav(FACTORY / "054_HH-1C.wav")
    hho = read_wav(FACTORY / "055_HH-1O.wav")
    ride = read_wav(FACTORY / "068_Ride-1.wav")
    junk = read_wav(FACTORY / "092_JunkPerc.wav")

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

    for bar in range(BARS):
        base = bar * 4.0
        for step in (0, 4, 8, 12):
            beat = base + step * 0.25
            place(trk_k, kick_s, beat, 1.0)
            place(trk_k_hard, kick_s, beat, 1.14)
        for step in (0, 4, 8, 12):
            place(trk_h_sp, hhc, base + step * 0.25, 0.72)
        for i in range(16):
            vel = 0.70 if (i % 2 == 0) else 0.50
            place(trk_h_dn, hhc, base + i * 0.25, vel)
            place(trk_h_hard, hhc, base + i * 0.25, vel * 1.15)
        for step in (2, 6, 10, 14):
            place(trk_oh, hho, base + step * 0.25, 0.78)
            place(trk_oh_hard, hho, base + step * 0.25, 0.92)
        for step in range(0, 16, 2):
            place(trk_ride, ride, base + step * 0.25, 0.55)
        place(trk_perc_l, junk, base + 3 * 0.25, 0.40)
        place(trk_perc_l, junk, base + 11 * 0.25, 0.38)
        place(trk_perc_t, junk, base + 3 * 0.25, 0.85)
        place(trk_perc_t, junk, base + 11 * 0.25, 0.85)
        place(trk_perc_h, junk, base + 3 * 0.25, 0.95)
        place(trk_perc_h, junk, base + 11 * 0.25, 0.95)
        place(trk_perc_h, junk, base + 7 * 0.25, 0.45)

    files = {
        "ew_kick_162.wav": trk_k,
        "ew_kick_hard_162.wav": trk_k_hard,
        "ew_hats_sparse_162.wav": trk_h_sp,
        "ew_hats_dense_162.wav": trk_h_dn,
        "ew_hats_hard_162.wav": trk_h_hard,
        "ew_ohat_162.wav": trk_oh,
        "ew_ohat_hard_162.wav": trk_oh_hard,
        "ew_ride_162.wav": trk_ride,
        "ew_perc_light_162.wav": trk_perc_l,
        "ew_perc_tribal_162.wav": trk_perc_t,
        "ew_perc_hard_162.wav": trk_perc_h,
    }
    for name, buf in files.items():
        write_wav(OUT / name, buf)
    return files


def mix_layers(layers, bars=8):
    n = int(bars * 4 * 60.0 / BPM * SR)
    out = [0.0] * n
    for buf, g in layers:
        ln = len(buf)
        for i in range(n):
            out[i] += buf[i % ln] * g
    return [math.tanh(x * 1.05) for x in out]


def build_morph_mp3():
    print("=== CLEAN morph MP3 ===")
    kick = read_wav(OUT / "ew_kick_162.wav")
    hats_sp = read_wav(OUT / "ew_hats_sparse_162.wav")
    hats_dn = read_wav(OUT / "ew_hats_dense_162.wav")
    hats_h = read_wav(OUT / "ew_hats_hard_162.wav")
    ohat = read_wav(OUT / "ew_ohat_162.wav")
    ohat_h = read_wav(OUT / "ew_ohat_hard_162.wav")
    ride = read_wav(OUT / "ew_ride_162.wav")
    perc_l = read_wav(OUT / "ew_perc_light_162.wav")
    perc_h = read_wav(OUT / "ew_perc_hard_162.wav")
    kick_h = read_wav(OUT / "ew_kick_hard_162.wav")

    silent = [0.0] * N
    sec_intro = silent[:]
    sec_kick = mix_layers([(kick, 1.0)], 8)
    sec_hats = mix_layers([(kick, 1.0), (hats_sp, 0.75)], 8)
    acid8 = synth_acid_tone(8, muted=True, with_bass=False)
    drums_acid = mix_layers([(kick, 1.0), (hats_sp, 0.65)], 8)
    sec_acid = [drums_acid[i] + acid8[i] * 0.85 for i in range(N)]

    acid16o = synth_acid_tone(16, muted=False, harder=False, with_bass=False)
    drop_drums = mix_layers([(kick, 1.0), (hats_dn, 0.70), (ohat, 0.55), (perc_l, 0.50)], 16)
    sec_drop = [drop_drums[i] + acid16o[i] * 0.95 for i in range(len(drop_drums))]

    acid_break = synth_acid_tone(8, muted=False, harder=False, with_bass=False)
    break_drums = mix_layers([(ride, 0.70)], 8)
    sec_break = [break_drums[i] + acid_break[i] * 1.0 for i in range(N)]

    acid_peak = synth_acid_tone(16, muted=False, harder=True, with_bass=True)
    peak_drums = mix_layers([(kick_h, 1.0), (hats_h, 0.72), (ohat_h, 0.58), (perc_h, 0.55)], 16)
    sec_peak = [peak_drums[i] + acid_peak[i] * 1.0 for i in range(len(peak_drums))]

    outro = mix_layers([(kick, 1.0)], 8)
    half = len(outro) // 2
    for i in range(half, len(outro)):
        outro[i] = 0.0
    sec_outro = outro

    morph = concat_mono([sec_intro, sec_kick, sec_hats, sec_acid, sec_drop, sec_break, sec_peak, sec_outro])
    st = OUT / "ew_clean_morph_162_st.wav"
    mono_to_stereo_wav(st, morph)
    write_wav(OUT / "ew_clean_morph_162.wav", morph)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(st), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3)],
        check=True,
        capture_output=True,
    )
    shutil.copy2(MP3, MP3_COPY)
    print("MP3", MP3, "size", MP3.stat().st_size)
    print("MP3_COPY", MP3_COPY)


def stop_all(snap):
    for t in snap["tracks"]:
        for sl in t.get("clip_slots") or []:
            if sl.get("has_clip"):
                send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})


def main():
    errors = []
    generate_drums()
    if MP3.exists() and MP3.stat().st_size > 100000:
        print("MP3 already exists, skip rebuild", MP3, MP3.stat().st_size)
        if not MP3_COPY.exists():
            import shutil
            try:
                shutil.copy2(MP3, MP3_COPY)
            except Exception as e:
                errors.append(f"mp3 copy: {e}")
    else:
        try:
            build_morph_mp3()
        except Exception as e:
            errors.append(f"mp3: {e}")
            print("FAIL mp3", e)

    print("=== Ableton CLEAN Evolving Wild ===")
    snap = ok(send("get_session_snapshot", {"include_devices": False}, timeout=60), "snapshot")
    if not snap:
        print("ABORT")
        return

    ok(send("set_tempo", {"tempo": BPM}), "tempo 162")
    # KEEP PLAYING — do not stop_playback / stop_all (user must hear continuously)
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

    for idx in (atm_idx, mental_idx, syn_idx):
        if idx is None:
            continue
        for row in range(8):
            safe_delete(idx, row)
        print("cleared noisy track", idx)

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

    def scene_acid(row, name, include=True, muted=False, harder=False, open_gate=False, bass=False):
        if acid_idx is not None:
            if include:
                put_midi(
                    acid_idx,
                    row,
                    16.0,
                    f"{name}_acid",
                    make_acid_notes(4, muted=muted, harder=harder, open_gate=open_gate),
                )
            else:
                safe_delete(acid_idx, row)
        if bass_idx is not None:
            if bass and include:
                put_midi(
                    bass_idx,
                    row,
                    16.0,
                    f"{name}_bass",
                    make_bass_notes(4, muted=muted, harder=harder, open_gate=open_gate),
                )
            else:
                safe_delete(bass_idx, row)

    scene_drums(0, "Intro_Atm")
    scene_acid(0, "Intro_Atm", include=False)

    scene_drums(1, "Kick_In", kick="ew_kick_162.wav")
    scene_acid(1, "Kick_In", include=False)

    scene_drums(2, "Hats_In", kick="ew_kick_162.wav", hats="ew_hats_sparse_162.wav")
    scene_acid(2, "Hats_In", include=False)

    scene_drums(3, "Acid_Muted", kick="ew_kick_162.wav", hats="ew_hats_sparse_162.wav")
    scene_acid(3, "Acid_Muted", include=True, muted=True, bass=False)

    scene_drums(
        4,
        "Drop_Clean",
        kick="ew_kick_162.wav",
        hats="ew_hats_dense_162.wav",
        ohat="ew_ohat_162.wav",
        perc="ew_perc_light_162.wav",
    )
    scene_acid(4, "Drop_Clean", include=True, muted=False, open_gate=True, bass=False)

    scene_drums(
        5,
        "Tribal_Add",
        kick="ew_kick_162.wav",
        hats="ew_hats_dense_162.wav",
        ohat="ew_ohat_162.wav",
        perc="ew_perc_tribal_162.wav",
    )
    scene_acid(5, "Tribal_Add", include=True, open_gate=True, bass=False)

    scene_drums(6, "Break_Fragile", ohat="ew_ride_162.wav")
    scene_acid(6, "Break_Fragile", include=True, open_gate=True, bass=False)

    scene_drums(
        7,
        "Peak_Full",
        kick="ew_kick_hard_162.wav",
        hats="ew_hats_hard_162.wav",
        ohat="ew_ohat_hard_162.wav",
        perc="ew_perc_hard_162.wav",
    )
    scene_acid(7, "Peak_Full", include=True, harder=True, open_gate=True, bass=True)

    for i, name in enumerate(CONCEPTUAL_12):
        short = name.split(" (")[0].replace(" ", "_")
        send("create_locator", {"name": short[:20], "time": float(i * 32.0)})

    # heartbeat play before Drop
    send("start_playback")

    drop_row = 4
    fired = []
    for label, idx in [
        ("Acid 303 Poly", acid_idx),
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
    # final heartbeat
    send("start_playback")

    info = send("get_session_info")
    tempo = (info.get("result") or info).get("tempo")
    mp3_size = MP3.stat().st_size if MP3.exists() else 0

    print("==== RESULT ====")
    print("TEMPO", tempo)
    print("SCENES_PHYSICAL", [(i, n) for i, n in SCENES])
    print("SCENES_CONCEPTUAL_12", CONCEPTUAL_12)
    print(
        "TRACKS_USED",
        {
            "Acid 303 Poly": acid_idx,
            "Tholin Bass": bass_idx,
            "E-Kick": kick_idx,
            "E-Hats": hats_idx,
            "E-OHat": ohat_idx,
            "E-Perc": perc_idx,
        },
    )
    print("DROP_FIRED", fired)
    print("MP3_PATH", str(MP3))
    print("MP3_SIZE", mp3_size)
    print("MP3_COPY", str(MP3_COPY))
    print("NO_GRAINY_ATM", True)
    print("SINKICK_ONLY", True)
    print("ERRORS", errors)
    print("DONE EvolvingWild CLEAN 162")


if __name__ == "__main__":
    main()
