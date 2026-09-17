# -*- coding: utf-8 -*-
"""Live-set 15s morphs @ 162 BPM — Electribe-style scene launches.

8 Session scenes with DISTINCT rhythms (10 bars each ~14.8s).
Reuses Kickback/CRISP DNA one-shots + Electribe master chain.
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

# Reuse CRISP DNA pipeline helpers
BRIDGE = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge")
sys.path.insert(0, str(BRIDGE))
import crisp_dna_to_ableton as dna  # noqa: E402

SR = dna.SR
BPM = 162.0
BARS = 10  # ~14.81s per section
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR)
HOST, PORT = "127.0.0.1", 9877

OUT = BRIDGE / "samples" / "crisp-dna" / "morphs"
OUT.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_LiveSet_15sMorphs_162.mp3")
README = BRIDGE / "LIVESET_15s_MORPHS_README.md"
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)

SCENES = [
    (0, "Intro_Kick"),
    (1, "Hats_Sparse"),
    (2, "Hats_Shuffle"),
    (3, "Perc_Offs"),
    (4, "Full_Tribal"),
    (5, "Break_NoKick"),
    (6, "Peak_Drive"),
    (7, "Outro_Strip"),
]

# Override DNA module BPM/N for placement consistency when calling place()
dna.BPM = BPM
dna.BARS = BARS
dna.BEATS = BEATS
dna.N = N


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


def silence_noisy(by_full):
    for name in ("E-Mental", "E-Atm", "E-Syn", "E2S Jam", "ESX Jam", "ES1 90s", "E-DrumLP", "CRISP_e2e_kick"):
        t = by_full.get(name)
        if not t:
            continue
        idx = t["index"]
        for row in range(8):
            send("stop_clip", {"track_index": idx, "clip_index": row})
            send("delete_clip", {"track_index": idx, "clip_index": row})
        print("silenced", name, idx)


def ensure_oneshots(rng):
    """Ensure Kickback/ESX one-shots exist (reuse crisp-dna folder)."""
    base = dna.OUT
    need = [
        "kb_kick_sledge_esx.wav",
        "kb_hat_closed_esx.wav",
        "kb_hat_open_esx.wav",
        "kb_clap_esx.wav",
        "esx_SinKick_mastered.wav",
        "esx_HH1C_mastered.wav",
        "esx_HH1O_mastered.wav",
        "esx_JunkPerc_mastered.wav",
    ]
    if all((base / n).exists() for n in need[:4]):
        print("reusing existing CRISP DNA one-shots")
    else:
        print("generating missing one-shots via DNA synth")
        kick_dna = dna.synth_kick_sledge(rng, "full")
        hat_c = dna.synth_hat(rng, False)
        hat_o = dna.synth_hat(rng, True)
        clap = dna.synth_clap(rng)
        dna.write_wav_mono(base / "kb_kick_sledge.wav", kick_dna)
        dna.write_wav_mono(base / "kb_hat_closed.wav", hat_c)
        dna.write_wav_mono(base / "kb_hat_open.wav", hat_o)
        dna.write_wav_mono(base / "kb_clap.wav", clap)
        for name in ("kb_kick_sledge.wav", "kb_hat_closed.wav", "kb_hat_open.wav", "kb_clap.wav"):
            src = base / name
            dst = base / name.replace(".wav", "_esx.wav")
            try:
                dna.electribe_master(src, dst)
            except Exception as e:
                print("FAIL master", name, e)

    kick_main = dna.read_wav(base / "kb_kick_sledge_esx.wav") if (base / "kb_kick_sledge_esx.wav").exists() else dna.synth_kick_sledge(rng, "full")
    kick_main = [dna.tanh_drive(x, 1.35) for x in kick_main]
    esx_kick = None
    if (base / "esx_SinKick_mastered.wav").exists():
        esx_kick = [dna.tanh_drive(x, 1.7) for x in dna.read_wav(base / "esx_SinKick_mastered.wav")]
    if (base / "esx_HH1C_mastered.wav").exists():
        hat_c = [dna.tanh_drive(x, 1.2) for x in dna.read_wav(base / "esx_HH1C_mastered.wav")]
    elif (base / "kb_hat_closed_esx.wav").exists():
        hat_c = dna.read_wav(base / "kb_hat_closed_esx.wav")
    else:
        hat_c = dna.synth_hat(rng, False)
    if (base / "esx_HH1O_mastered.wav").exists():
        hat_o = [dna.tanh_drive(x, 1.15) for x in dna.read_wav(base / "esx_HH1O_mastered.wav")]
    elif (base / "kb_hat_open_esx.wav").exists():
        hat_o = dna.read_wav(base / "kb_hat_open_esx.wav")
    else:
        hat_o = dna.synth_hat(rng, True)
    clap = dna.read_wav(base / "kb_clap_esx.wav") if (base / "kb_clap_esx.wav").exists() else dna.synth_clap(rng)
    junk = None
    if (base / "esx_JunkPerc_mastered.wav").exists():
        junk = [dna.tanh_drive(x, 1.4) for x in dna.read_wav(base / "esx_JunkPerc_mastered.wav")]
    return kick_main, esx_kick, hat_c, hat_o, clap, junk


def place(buf, sample, beat, gain=1.0):
    start = int(beat * 60.0 / BPM * SR)
    for i, v in enumerate(sample):
        j = start + i
        if 0 <= j < len(buf):
            buf[j] += v * gain


def render_scene_layers(sid, name, kick_main, esx_kick, hat_c, hat_o, clap, junk, pattern):
    """Render distinct 10-bar stems for one scene. Returns dict of layer wavs + mix."""
    trk_k = [0.0] * N
    trk_h = [0.0] * N
    trk_oh = [0.0] * N
    trk_p = [0.0] * N

    for bar in range(BARS):
        base = bar * 4.0
        # progress within section for outro thin-out
        progress = bar / max(1, BARS - 1)

        # --- KICK ---
        if sid == 5:
            pass  # Break_NoKick
        elif sid == 7:
            # Outro_Strip: kick only early bars, then thin
            if bar < 6:
                g = 1.0 if bar < 4 else 0.75
                for step in (0, 4, 8, 12):
                    place(trk_k, kick_main, base + step * 0.25, g)
                    if esx_kick is not None:
                        place(trk_k, esx_kick, base + step * 0.25, 0.16 * g)
            elif bar < 8:
                for step in (0, 8):
                    place(trk_k, kick_main, base + step * 0.25, 0.55)
        elif sid == 0:
            # Intro_Kick: 4/4 only
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base + step * 0.25, 0.82)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base + step * 0.25, 0.14)
        elif sid == 6:
            # Peak_Drive: harder kick
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base + step * 0.25, 1.15)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base + step * 0.25, 0.22)
            # extra ghost on offbeat late bars
            if bar >= 4:
                place(trk_k, kick_main, base + 1.5, 0.35)
                place(trk_k, kick_main, base + 3.5, 0.30)
        else:
            # standard 4/4
            g = 0.95 if sid >= 3 else 0.88
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base + step * 0.25, g)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base + step * 0.25, 0.16 * g)

        # --- HATS ---
        if sid == 0 or sid == 7:
            pass  # no hats (outro strip / intro kick only)
        elif sid == 1:
            # Hats_Sparse: CH on 1,5,9,13 only (16th steps 0,4,8,12)
            for st in (0, 4, 8, 12):
                place(trk_h, hat_c, base + st * 0.25, 0.72)
        elif sid == 2:
            # Hats_Shuffle: 16ths with 70/50 swing (odd steps delayed + quieter)
            for st in range(16):
                swing = 0.028 if (st % 2 == 1) else 0.0  # ~70% swing feel
                g = 0.70 if st % 2 == 0 else 0.42  # 70/50-ish
                place(trk_h, hat_c, base + st * 0.25 + swing, g)
        elif sid == 3:
            # Perc_Offs: medium hats (even 8ths)
            for st in range(0, 16, 2):
                place(trk_h, hat_c, base + st * 0.25, 0.55 if st % 4 else 0.78)
        elif sid == 4:
            # Full_Tribal: dense 16ths + OH offs
            for st in range(16):
                swing = 0.012 if st % 2 else 0.0
                g = 0.85 if st % 2 == 0 else 0.55
                place(trk_h, hat_c, base + st * 0.25 + swing, g)
            # open hats on offs (steps 2,6,10,14 ≈ & of beats)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.48)
        elif sid == 5:
            # Break_NoKick: soft dense hats
            for st in range(16):
                swing = 0.018 if st % 2 else 0.0
                g = 0.50 if st % 2 == 0 else 0.32
                place(trk_h, hat_c, base + st * 0.25 + swing, g)
            for st in (6, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.35)
        elif sid == 6:
            # Peak denser hats + OH
            for st in range(16):
                swing = 0.010 if st % 2 else 0.0
                g = 0.92 if st % 2 == 0 else 0.62
                place(trk_h, hat_c, base + st * 0.25 + swing, g)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base + st * 0.25, 0.55)
            # extra OH on 3+ of bar late
            if bar >= 5:
                place(trk_oh, hat_o, base + 3.5, 0.40)

        # --- PERC / CLAP ---
        if sid in (0, 1, 2, 7):
            pass
        elif sid == 3:
            # Perc_Offs: clap on 5+13 (16th steps 4 and 12) = beat 2 and 4
            place(trk_p, clap, base + 1.0, 0.70)   # beat 2 (= step 4)
            place(trk_p, clap, base + 3.0, 0.70)   # beat 4 (= step 12)
            if junk is not None:
                place(trk_p, junk, base + 0.75, 0.38)
                place(trk_p, junk, base + 2.75, 0.34)
        elif sid == 4:
            place(trk_p, clap, base + 1.0, 0.68)
            place(trk_p, clap, base + 3.0, 0.68)
            if junk is not None:
                place(trk_p, junk, base + 0.5, 0.42)
                place(trk_p, junk, base + 1.75, 0.36)
                place(trk_p, junk, base + 2.5, 0.40)
                place(trk_p, junk, base + 3.75, 0.32)
        elif sid == 5:
            place(trk_p, clap, base + 1.0, 0.45)
            place(trk_p, clap, base + 3.0, 0.40)
            if junk is not None:
                place(trk_p, junk, base + 0.75, 0.30)
                place(trk_p, junk, base + 2.25, 0.28)
                place(trk_p, junk, base + 3.5, 0.25)
        elif sid == 6:
            place(trk_p, clap, base + 1.0, 0.85)
            place(trk_p, clap, base + 3.0, 0.85)
            if junk is not None:
                for off in (0.5, 0.75, 1.5, 1.75, 2.5, 2.75, 3.5, 3.75):
                    place(trk_p, junk, base + off, 0.38 if off % 1 == 0.5 else 0.28)

    # Acid audio stem density by scene (also MIDI separately)
    # muted intro; open from scene 2+
    acid_drive = {0: 0.0, 1: 0.12, 2: 0.55, 3: 0.65, 4: 0.75, 5: 0.85, 6: 1.0, 7: 0.25}.get(sid, 0.5)
    acid_full = dna.render_acid_stem(pattern, grit_drive=2.8 if sid < 6 else 3.2)
    # stretch/trim acid to N (dna.render_acid uses dna.N which we set)
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))

    if sid == 6:
        trk_k = [x * 1.08 for x in trk_k]
        trk_p = [x * 1.12 for x in trk_p]

    # write layer wavs
    prefix = f"s{sid}_{name}"
    paths = {}
    paths["kick"] = OUT / f"{prefix}_kick.wav"
    paths["hats"] = OUT / f"{prefix}_hats.wav"
    paths["oh"] = OUT / f"{prefix}_oh.wav"
    paths["perc"] = OUT / f"{prefix}_perc.wav"
    paths["acid"] = OUT / f"{prefix}_acid.wav"

    dna.write_wav_mono(paths["kick"], trk_k, peak_target=0.92)
    dna.write_wav_mono(paths["hats"], trk_h, peak_target=0.85)
    dna.write_wav_mono(paths["oh"], trk_oh, peak_target=0.80)
    dna.write_wav_mono(paths["perc"], trk_p, peak_target=0.85)
    dna.write_wav_mono(paths["acid"], acid, peak_target=0.80)

    # club-ish kick-dominated section mix for bounce
    mix = [0.0] * N
    for i in range(N):
        mono = (
            trk_k[i] * 1.08
            + acid[i] * 0.30
            + trk_h[i] * 0.24
            + trk_oh[i] * 0.18
            + trk_p[i] * 0.20
        )
        mix[i] = dna.tanh_drive(mono, 1.10)
    mix_path = SECTION_MIX_DIR / f"{prefix}_mix.wav"
    # stereo write
    peak = max(1e-9, max(abs(x) for x in mix))
    scale = 0.90 / peak
    st = array.array("h")
    for x in mix:
        v = max(-32767, min(32767, int(x * scale * 32767)))
        st.append(v)
        st.append(v)
    with wave.open(str(mix_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())
    paths["mix"] = mix_path
    print("scene", sid, name, "rendered", f"{len(mix)/SR:.2f}s")
    return paths, trk_k, trk_h, trk_oh, trk_p, acid


def make_acid_midi_for_scene(pattern, sid, bars=10):
    """Vary acid density by scene."""
    notes = []
    gate = 0.1875
    slide_dur = 0.45
    # density: mute intro, sparse scene1, open from 2+
    keep = {
        0: lambda st, bar: False,
        1: lambda st, bar: st % 4 == 0 and bar % 2 == 0,
        2: lambda st, bar: True,
        3: lambda st, bar: True,
        4: lambda st, bar: True,
        5: lambda st, bar: True,
        6: lambda st, bar: True,
        7: lambda st, bar: st % 4 == 0 and bar < 4,
    }[sid]
    harder = sid >= 6
    vel_boost = 12 if harder else 0
    for bar in range(bars):
        base = bar * 4.0
        for st, p in enumerate(pattern):
            if p["midi"] <= 0:
                continue
            if not keep(st, bar):
                continue
            # scene 5: denser; scene 2/3: normal
            if sid == 5 and st % 2 == 1 and not p["accent"]:
                continue
            dur = slide_dur if p["slide"] else gate
            vel = (118 if p["accent"] else 95) + vel_boost
            if sid == 1:
                vel = max(1, int(vel * 0.7))
            notes.append(
                {
                    "pitch": int(p["midi"]),
                    "start_time": base + st * 0.25,
                    "duration": dur,
                    "velocity": min(127, vel),
                    "mute": False,
                }
            )
    return notes


def layer_has_signal(path: Path, thr=0.002) -> bool:
    try:
        samples = dna.read_wav(path)
        return max(abs(x) for x in samples) > thr
    except Exception:
        return False


def main():
    errors = []
    rng = dna.mulberry32(dna.SEED ^ 0x15F)
    print("=== LiveSet 15s Morphs @", BPM, "bars=", BARS, "N=", N, f"sec={N/SR:.2f} ===")

    kick_main, esx_kick, hat_c, hat_o, clap, junk = ensure_oneshots(rng)
    pattern = dna.acid_pattern(dna.SEED + 7)

    # Force acid render length
    dna.N = N
    dna.BARS = BARS

    scene_paths = {}
    for sid, name in SCENES:
        paths, *_ = render_scene_layers(sid, name, kick_main, esx_kick, hat_c, hat_o, clap, junk, pattern)
        scene_paths[sid] = paths

    # --- Concatenate 8 section mixes into ONE continuous MP3 ---
    print("=== Bounce concatenated MP3 ===")
    concat_list = OUT / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for sid, name in SCENES:
            p = scene_paths[sid]["mix"].as_posix().replace("'", "'\\''")
            f.write(f"file '{scene_paths[sid]['mix']}'\n")

    raw_concat = OUT / "liveset_morphs_concat.wav"
    try:
        # Normalize each then concat; club loudness on full file
        subprocess.run(
            [
                dna.FFMPEG,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                str(raw_concat),
            ],
            check=True,
            capture_output=True,
        )
        loud = OUT / "liveset_morphs_club.wav"
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
        subprocess.run(
            [
                dna.FFMPEG,
                "-y",
                "-i",
                str(loud),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(MP3),
            ],
            check=True,
            capture_output=True,
        )
        print("MP3 written", MP3)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        # fallback: try without loudnorm
        try:
            subprocess.run(
                [dna.FFMPEG, "-y", "-i", str(raw_concat), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3)],
                check=True,
                capture_output=True,
            )
            print("MP3 fallback OK", MP3)
        except Exception as e2:
            errors.append(f"mp3 fallback: {e2}")

    # duration probe
    mp3_dur = 0.0
    try:
        probe = subprocess.run(
            [
                dna.FFMPEG.replace("ffmpeg.exe", "ffprobe.exe") if "ffmpeg.exe" in dna.FFMPEG else "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(MP3),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        mp3_dur = float(probe.stdout.strip())
    except Exception:
        # estimate from samples
        mp3_dur = 8 * (N / SR)
        try:
            # try ffmpeg -i
            p = subprocess.run([dna.FFMPEG, "-i", str(MP3)], capture_output=True, text=True)
            import re
            m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", p.stderr)
            if m:
                mp3_dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        except Exception as e:
            errors.append(f"dur: {e}")

    print("MP3_DURATION_SEC", round(mp3_dur, 2))

    # --- Ableton load ---
    print("=== Ableton load 8 morph scenes ===")
    snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=60)
    snap = ok(snap_r, "snapshot")
    if not snap:
        print("ABORT no Ableton — samples/MP3 still written")
        print("ERRORS", errors)
        print("MP3_PATH", str(MP3))
        print("MP3_DURATION_SEC", round(mp3_dur, 2))
        write_readme(mp3_dur)
        return

    ok(send("set_tempo", {"tempo": BPM}), "tempo 162")
    ok(send("stop_playback"), "stop")

    for t in snap["tracks"]:
        for sl in t.get("clip_slots") or []:
            if sl.get("has_clip"):
                send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})

    by_full = {t["name"]: t for t in snap["tracks"]}
    by = {t["name"]: t["index"] for t in snap["tracks"]}
    print("tracks", by)

    silence_noisy(by_full)

    acid_idx = by.get("Acid 303 Poly")
    kick_idx = by.get("E-Kick")
    hats_idx = by.get("E-Hats")
    perc_idx = by.get("E-Perc")
    oh_idx = by.get("E-OHat") or by.get("E-Snare")
    bass_idx = by.get("Tholin Bass") or by.get("E-Bass")

    if acid_idx is not None:
        r = send("load_browser_item", {"track_index": acid_idx, "item_uri": "query:Synths#Drift"})
        print("Drift", r.get("status"), r.get("message", r.get("result")))

    # Clear rows 0-7 on key tracks
    for row, _ in SCENES:
        for idx in (acid_idx, kick_idx, hats_idx, perc_idx, oh_idx, bass_idx):
            if idx is not None:
                safe_delete(idx, row)

    clip_len = float(BEATS)  # 40 beats for 10 bars

    for sid, name in SCENES:
        paths = scene_paths[sid]
        # Kick
        if kick_idx is not None and layer_has_signal(paths["kick"]):
            load_audio(kick_idx, sid, paths["kick"], f"{name}_kick")
        # Hats
        if hats_idx is not None and layer_has_signal(paths["hats"]):
            load_audio(hats_idx, sid, paths["hats"], f"{name}_hats")
        # OH
        if oh_idx is not None and layer_has_signal(paths["oh"]):
            load_audio(oh_idx, sid, paths["oh"], f"{name}_oh")
        # Perc
        if perc_idx is not None and layer_has_signal(paths["perc"]):
            load_audio(perc_idx, sid, paths["perc"], f"{name}_perc")
        # Acid MIDI
        midi = make_acid_midi_for_scene(pattern, sid, bars=BARS)
        if acid_idx is not None and midi:
            put_midi(acid_idx, sid, clip_len, f"{name}_acid", midi)
        # Bass shadow (scenes 2+)
        if bass_idx is not None and sid >= 2 and midi:
            bass_notes = []
            for n in midi:
                bn = dict(n)
                bn["pitch"] = max(0, n["pitch"] - 12)
                bn["velocity"] = max(1, int(n["velocity"] * 0.75))
                bass_notes.append(bn)
            put_midi(bass_idx, sid, clip_len, f"{name}_bass", bass_notes)

        send("create_locator", {"name": f"{sid}_{name}", "time": float(sid * clip_len)})

    # Fire scene 0 (Intro_Kick) by firing clips in row 0
    print("=== Fire scene 0 Intro_Kick ===")
    fired0 = []
    for label, idx in [("E-Kick", kick_idx)]:
        if idx is None:
            continue
        # Intro may only have kick
        r = send("fire_clip", {"track_index": idx, "clip_index": 0})
        if r.get("status") == "success":
            fired0.append(label)
            print("FIRE", label, "row0")
        else:
            # try anyway if clip exists
            print("fire attempt", label, r)

    ok(send("start_playback"), "start_playback")

    info = send("get_session_info")
    res = info.get("result") or info
    print("tempo", res.get("tempo"), "is_playing", res.get("is_playing"))

    # Document launch every 10 bars; optionally demo-fire through scenes
    # Demo: fire each scene row quickly for verification (not timed to 15s — user hears MP3 for that)
    print("=== Demo fire scenes 0-7 (clip rows) ===")
    demo_fired = []
    for sid, name in SCENES:
        row_tracks = []
        for label, idx, key in [
            ("kick", kick_idx, "kick"),
            ("hats", hats_idx, "hats"),
            ("oh", oh_idx, "oh"),
            ("perc", perc_idx, "perc"),
            ("acid", acid_idx, None),
            ("bass", bass_idx, None),
        ]:
            if idx is None:
                continue
            if key and not layer_has_signal(scene_paths[sid][key]):
                continue
            if label == "acid" and not make_acid_midi_for_scene(pattern, sid, bars=BARS):
                continue
            if label == "bass" and sid < 2:
                continue
            r = send("fire_clip", {"track_index": idx, "clip_index": sid})
            if r.get("status") == "success":
                row_tracks.append(label)
        demo_fired.append((sid, name, row_tracks))
        print("DEMO fire scene", sid, name, row_tracks)

    # Leave playing on scene 0 again for live use
    for label, idx in [("E-Kick", kick_idx)]:
        if idx is not None and layer_has_signal(scene_paths[0]["kick"]):
            send("fire_clip", {"track_index": idx, "clip_index": 0})
    ok(send("start_playback"), "start_playback again")

    info2 = send("get_session_info")
    res2 = info2.get("result") or info2

    write_readme(mp3_dur)

    print("SCENES", [n for _, n in SCENES])
    print("LAUNCH_HINT", "Launch next Session scene every 10 bars (~14.8s) quantized to 1 bar")
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(mp3_dur, 2))
    print("is_playing", res2.get("is_playing"), "tempo", res2.get("tempo"))
    print("FIRED0", fired0)
    print("DEMO_FIRED", demo_fired)
    print("ERRORS", errors)
    print("DONE build_liveset_15s_morphs")


def write_readme(mp3_dur: float):
    text = f"""# EvAIx LiveSet — 15s Morphs @ 162 BPM

Electribe-style pattern launches: **8 Session scenes**, each with a **different rhythm**.

## Timing

- Tempo: **162 BPM**
- 1 bar ≈ 1.481 s
- Section length: **10 bars ≈ 14.8 s**
- Full morph bounce: ~{mp3_dur:.1f} s (8 × ~15 s)

## Scenes (rows 0–7)

| Row | Name | Rhythm |
|-----|------|--------|
| 0 | Intro_Kick | Kick 4/4 only |
| 1 | Hats_Sparse | Kick + closed hats on 1,5,9,13 |
| 2 | Hats_Shuffle | Kick + 16th hats 70/50 swing |
| 3 | Perc_Offs | + clap/perc on beats 2 & 4 (steps 5+13) |
| 4 | Full_Tribal | Kick + dense hats + OH offs + perc |
| 5 | Break_NoKick | NO kick; hats + perc + acid |
| 6 | Peak_Drive | Full + harder kick + denser perc |
| 7 | Outro_Strip | Kick only, then thin out |

Acid MIDI: muted on Intro, sparse on Hats_Sparse, open from scene 2+.

## How to play live

1. Open the set with AbletonMCP / this session loaded.
2. Fire **scene row 0** (Intro_Kick).
3. **Launch the next Session scene every 8–16 bars** (default **10 bars**), quantized to **1 bar**.
4. Mental / Atm / Syn beds stay silenced — drums + acid carry the morph.

## Listen bounce

`C:\\Users\\Gebruiker\\Downloads\\EvAIx_LiveSet_15sMorphs_162.mp3`

Layer WAVs: `evaix-bridge\\samples\\crisp-dna\\morphs\\`

## Rebuild

```bat
python C:\\Users\\Gebruiker\\ableton-mcp\\evaix-bridge\\build_liveset_15s_morphs.py
```

Requires AbletonMCP TCP `127.0.0.1:9877` and ffmpeg. Reuses CRISP DNA pipeline (`crisp_dna_to_ableton.py`).
"""
    README.write_text(text, encoding="utf-8")
    print("README", README)


if __name__ == "__main__":
    main()
