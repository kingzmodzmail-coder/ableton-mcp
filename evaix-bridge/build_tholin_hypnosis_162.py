"""Van der Wiese Tholin_Hypnosis — 162 BPM E Major via AbletonMCP."""
from __future__ import annotations

import array
import json
import math
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
OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set")
OUT.mkdir(parents=True, exist_ok=True)
HOST, PORT = "127.0.0.1", 9877
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_Tholin_Hypnosis_162.mp3")

# Scene row indices
SCENES = [
    (0, "Intro"),
    (1, "Build"),
    (2, "Drop"),
    (3, "Break"),
    (4, "Return"),
    (5, "Outro"),
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
    peak = max(1e-9, max(abs(x) for x in mono))
    scale = 0.9 / peak
    frames = array.array("h", [max(-32767, min(32767, int(x * scale * 32767))) for x in mono])
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(frames.tobytes())
    print("wrote", path.name, "peak", round(peak, 4))


def write_silent(path: Path):
    frames = array.array("h", [0] * N)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(frames.tobytes())
    print("wrote silent", path.name)


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
    st = r.get("status")
    if st != "success":
        print("FAIL", label, r.get("message", r))
        return None
    print("OK", label)
    return r.get("result", r)


def stop_all(snap):
    for t in snap["tracks"]:
        for sl in t.get("clip_slots") or []:
            if sl.get("has_clip"):
                send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})


def safe_delete(track_index, clip_index):
    send("delete_clip", {"track_index": track_index, "clip_index": clip_index})


def load_audio(track_index, clip_index, path: Path, name: str):
    safe_delete(track_index, clip_index)
    r = send("create_audio_clip", {"track_index": track_index, "clip_index": clip_index, "path": str(path)}, timeout=90)
    if r.get("status") != "success":
        print("FAIL audio", name, r)
        return False
    send("set_clip_name", {"track_index": track_index, "clip_index": clip_index, "name": name})
    print("OK audio", name, "-> track", track_index, "slot", clip_index)
    return True


def make_acid_notes(bars=4, harder=False):
    # 1-indexed steps -> 0-based 16ths
    # 1-E2, 3-G#2(slide), 5-B2(accent), 7-E3, 9-B2, 10-A2(slide), 12-G#2, 14-E2(accent), 16-B1(slide)
    # Gate ~75% of 16th = 0.1875; slides longer
    gate = 0.1875
    slide = 0.45
    steps = [
        (0, 40, 100, gate),       # E2
        (2, 44, 100, slide),      # G#2 slide
        (4, 47, 120, gate),       # B2 accent
        (6, 52, 105, gate),       # E3
        (8, 47, 100, gate),       # B2
        (9, 45, 100, slide),      # A2 slide
        (11, 44, 100, gate),      # G#2
        (13, 40, 120, gate),      # E2 accent
        (15, 35, 100, slide),     # B1 slide
    ]
    vel_boost = 10 if harder else 0
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        for step, pitch, vel, dur in steps:
            notes.append(
                {
                    "pitch": pitch,
                    "start_time": base + step * 0.25,
                    "duration": dur,
                    "velocity": min(127, vel + vel_boost),
                    "mute": False,
                }
            )
    return notes


def make_bass_notes(bars=4, harder=False):
    # octave lower same rhythm
    notes = make_acid_notes(bars=bars, harder=harder)
    for n in notes:
        n["pitch"] = max(0, n["pitch"] - 12)
        n["velocity"] = max(1, int(n["velocity"] * 0.85))
    return notes


def put_midi(track_index, clip_index, length, name, notes):
    safe_delete(track_index, clip_index)
    r = send("create_clip", {"track_index": track_index, "clip_index": clip_index, "length": length})
    if r.get("status") != "success":
        print("FAIL create midi", name, r)
        return False
    send("set_clip_name", {"track_index": track_index, "clip_index": clip_index, "name": name})
    r2 = send("add_notes_to_clip", {"track_index": track_index, "clip_index": clip_index, "notes": notes})
    if r2.get("status") != "success":
        print("FAIL notes", name, r2)
        return False
    print("OK midi", name, "notes", len(notes))
    return True


def main():
    errors = []
    print("=== generate drum loops @", BPM, "===")
    kick_s = drive(read_wav(FACTORY / "146_SinKick.wav"), 1.7)
    try:
        bd_s = drive(read_wav(FACTORY / "000_BD-1.wav"), 1.15)
    except Exception as e:
        bd_s = None
        print("no BD-1", e)
    hhc = read_wav(FACTORY / "054_HH-1C.wav")
    ride = read_wav(FACTORY / "068_Ride-1.wav")
    junk = read_wav(FACTORY / "092_JunkPerc.wav")

    # vel ~100 kick -> gain ~1.0; hats vel 80 -> 0.8; ride vel 60 -> 0.6
    trk_k = [0.0] * N
    trk_h = [0.0] * N
    trk_r = [0.0] * N
    trk_p = [0.0] * N
    trk_k_hard = [0.0] * N
    trk_h_hard = [0.0] * N
    trk_r_hard = [0.0] * N
    trk_p_hard = [0.0] * N

    for bar in range(BARS):
        base = bar * 4.0
        # Kick steps 1,5,9,13 = 16ths 0,4,8,12 = beats 0,1,2,3
        for step in (0, 4, 8, 12):
            beat = base + step * 0.25
            place(trk_k, kick_s, beat, 1.0)
            place(trk_k_hard, kick_s, beat, 1.12)
            if bd_s is not None:
                place(trk_k, bd_s, beat, 0.18)
                place(trk_k_hard, bd_s, beat, 0.22)
        # Closed hats ONLY 1,5,9,13 sparse vel 80
        for step in (0, 4, 8, 12):
            beat = base + step * 0.25
            place(trk_h, hhc, beat, 0.80)
            place(trk_h_hard, hhc, beat, 0.92)
        # Ride odd 16ths 1,3,5,7,9,11,13,15 = 0,2,4,6,8,10,12,14 vel 60
        for step in range(0, 16, 2):
            beat = base + step * 0.25
            place(trk_r, ride, beat, 0.60)
            place(trk_r_hard, ride, beat, 0.72)
        # Light JunkPerc industrial on 4 & 12 (16ths 3,11) for Drop/Return color
        place(trk_p, junk, base + 3 * 0.25, 0.55)
        place(trk_p, junk, base + 11 * 0.25, 0.55)
        place(trk_p_hard, junk, base + 3 * 0.25, 0.70)
        place(trk_p_hard, junk, base + 11 * 0.25, 0.70)
        place(trk_p_hard, junk, base + 7 * 0.25, 0.40)

    write_wav(OUT / "tholin_kick_162.wav", trk_k)
    write_wav(OUT / "tholin_hats_162.wav", trk_h)
    write_wav(OUT / "tholin_ride_162.wav", trk_r)
    write_wav(OUT / "tholin_perc_162.wav", trk_p)
    write_wav(OUT / "tholin_kick_hard_162.wav", trk_k_hard)
    write_wav(OUT / "tholin_hats_hard_162.wav", trk_h_hard)
    write_wav(OUT / "tholin_ride_hard_162.wav", trk_r_hard)
    write_wav(OUT / "tholin_perc_hard_162.wav", trk_p_hard)
    write_silent(OUT / "tholin_silent_162.wav")

    mix = [0.0] * N
    for buf, g in [(trk_k, 1.0), (trk_h, 0.7), (trk_r, 0.55), (trk_p, 0.45)]:
        for i in range(N):
            mix[i] += buf[i] * g
    mix = [math.tanh(x * 1.05) for x in mix]
    write_wav(OUT / "tholin_drum_bus_162.wav", mix)

    # stereo bounce + mp3
    st_path = OUT / "tholin_drum_bus_162_st.wav"
    with wave.open(str(OUT / "tholin_drum_bus_162.wav"), "rb") as w:
        raw = w.readframes(w.getnframes())
    data = array.array("h")
    data.frombytes(raw)
    st = array.array("h")
    for x in data:
        st.append(x)
        st.append(x)
    with wave.open(str(st_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(st_path), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3)],
            check=True,
            capture_output=True,
        )
        print("MP3", MP3)
    except Exception as e:
        errors.append(f"ffmpeg mp3: {e}")
        print("FAIL mp3", e)

    print("=== Ableton session ===")
    snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=60)
    snap = ok(snap_r, "snapshot")
    if not snap:
        print("ABORT no snapshot")
        return

    ok(send("set_tempo", {"tempo": BPM}), "tempo 162")
    stop_all(snap)
    ok(send("stop_playback"), "stop playback")

    by = {t["name"]: t["index"] for t in snap["tracks"]}
    print("tracks:", by)

    acid_idx = by.get("Acid 303 Poly")
    kick_idx = by.get("E-Kick")
    hats_idx = by.get("E-Hats")
    # ride on E-OHat (was renamed from E-Snare previously)
    ride_idx = by.get("E-OHat") or by.get("E-Snare")
    perc_idx = by.get("E-Perc")
    atm_idx = by.get("E-Atm")
    bass_idx = by.get("6-MIDI") or by.get("Tholin Bass")

    if ride_idx is not None and "E-OHat" not in by and "E-Snare" in by:
        send("set_track_name", {"track_index": ride_idx, "name": "E-OHat"})

    # Ensure Drift on acid
    if acid_idx is not None:
        r = send("load_browser_item", {"track_index": acid_idx, "item_uri": "query:Synths#Drift"})
        print("Drift load:", r.get("status"), r.get("message", r.get("result")))

    # Optional bass track name
    if bass_idx is not None:
        send("set_track_name", {"track_index": bass_idx, "name": "Tholin Bass"})

    # --- Scene morph clips ---
    # Intro (0): silent drums + no acid (or quiet atm only)
    # Build (1): kick + ride
    # Drop (2): kick + CH + ride + acid (+ perc)
    # Break (3): acid + ride
    # Return (4): full harder
    # Outro (5): silent / atm

    def scene_audio(row, name, kick=None, hats=None, ride=None, perc=None, atm=None):
        if kick_idx is not None:
            if kick:
                load_audio(kick_idx, row, OUT / kick, f"{name}_kick")
            else:
                # leave empty — delete any prior
                safe_delete(kick_idx, row)
        if hats_idx is not None:
            if hats:
                load_audio(hats_idx, row, OUT / hats, f"{name}_hats")
            else:
                safe_delete(hats_idx, row)
        if ride_idx is not None:
            if ride:
                load_audio(ride_idx, row, OUT / ride, f"{name}_ride")
            else:
                safe_delete(ride_idx, row)
        if perc_idx is not None:
            if perc:
                load_audio(perc_idx, row, OUT / perc, f"{name}_perc")
            else:
                safe_delete(perc_idx, row)
        if atm_idx is not None:
            if atm:
                load_audio(atm_idx, row, OUT / atm, f"{name}_atm")
            else:
                safe_delete(atm_idx, row)

    def scene_acid(row, name, include=True, harder=False):
        if acid_idx is None:
            return
        if not include:
            safe_delete(acid_idx, row)
            return
        put_midi(acid_idx, row, 16.0, f"{name}_acid", make_acid_notes(bars=4, harder=harder))

    def scene_bass(row, name, include=True, harder=False):
        if bass_idx is None:
            return
        if not include:
            safe_delete(bass_idx, row)
            return
        put_midi(bass_idx, row, 16.0, f"{name}_bass", make_bass_notes(bars=4, harder=harder))

    # Clear rows 0-5 on key tracks first
    for row, _ in SCENES:
        for idx in (acid_idx, kick_idx, hats_idx, ride_idx, perc_idx, atm_idx, bass_idx):
            if idx is not None:
                safe_delete(idx, row)

    # 0 Intro — atmosphere placeholder / silent drums, acid OFF
    scene_audio(0, "Intro", kick=None, hats=None, ride=None, perc=None, atm="tholin_silent_162.wav")
    scene_acid(0, "Intro", include=False)
    scene_bass(0, "Intro", include=False)

    # 1 Build — kick + ride enter
    scene_audio(1, "Build", kick="tholin_kick_162.wav", hats=None, ride="tholin_ride_162.wav", perc=None)
    scene_acid(1, "Build", include=False)
    scene_bass(1, "Build", include=False)

    # 2 Drop — full
    scene_audio(
        2,
        "Drop",
        kick="tholin_kick_162.wav",
        hats="tholin_hats_162.wav",
        ride="tholin_ride_162.wav",
        perc="tholin_perc_162.wav",
    )
    scene_acid(2, "Drop", include=True, harder=False)
    scene_bass(2, "Drop", include=True, harder=False)

    # 3 Break — kick muted/stopped, acid + ride
    scene_audio(3, "Break", kick=None, hats=None, ride="tholin_ride_162.wav", perc=None)
    scene_acid(3, "Break", include=True, harder=False)
    scene_bass(3, "Break", include=True, harder=False)

    # 4 Return — full harder
    scene_audio(
        4,
        "Return",
        kick="tholin_kick_hard_162.wav",
        hats="tholin_hats_hard_162.wav",
        ride="tholin_ride_hard_162.wav",
        perc="tholin_perc_hard_162.wav",
    )
    scene_acid(4, "Return", include=True, harder=True)
    scene_bass(4, "Return", include=True, harder=True)

    # 5 Outro — strip to atm/quiet
    scene_audio(5, "Outro", kick=None, hats=None, ride=None, perc=None, atm="tholin_silent_162.wav")
    scene_acid(5, "Outro", include=False)
    scene_bass(5, "Outro", include=False)

    # Locators as scene name stand-ins (API has create_locator; no set_scene_name)
    # Place at 0, 8, 16... bars in arrangement time units (beats)
    for i, (row, name) in enumerate(SCENES):
        send("create_locator", {"name": f"{i+1}_{name}", "time": float(i * 32.0)})

    # Fire Drop scene (row 2)
    drop_row = 2
    fired = []
    for label, idx in [
        ("Acid 303 Poly", acid_idx),
        ("Tholin Bass", bass_idx),
        ("E-Kick", kick_idx),
        ("E-Hats", hats_idx),
        ("E-OHat/ride", ride_idx),
        ("E-Perc", perc_idx),
    ]:
        if idx is None:
            continue
        r = send("fire_clip", {"track_index": idx, "clip_index": drop_row})
        if r.get("status") == "success":
            fired.append(f"{label} slot{drop_row}")
            print("FIRE", label)
        else:
            errors.append(f"fire {label}: {r.get('message')}")
            print("FAIL fire", label, r)

    ok(send("start_playback"), "start playback")

    # Verify tempo
    info = send("get_session_info")
    tempo = (info.get("result") or info).get("tempo")
    print("session tempo", tempo)
    print("FIRED Drop:", fired)
    print("ERRORS:", errors)
    print("MP3_PATH", str(MP3))
    print("SCENES", [n for _, n in SCENES])
    print("DONE Tholin_Hypnosis 162")


if __name__ == "__main__":
    main()
