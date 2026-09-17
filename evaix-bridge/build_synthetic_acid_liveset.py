# -*- coding: utf-8 -*-
"""Swap soft Drift acid for Kickback scream/screech synthetic TB-303 @ 162.

- Re-render morph sections with scream acid (square, envAmt 3800, resQ 0.05-0.08,
  baseCut 240, full grit) + rolling cutoff
- Main acid voice = rendered audio on E-Syn (Acid 303 Poly is MIDI-only)
- Quiet Drift MIDI double on Acid 303 Poly
- Keep CRISP-mastered drum layers; boost acid in mix (kick still dominates)
- Fire Full_Tribal (scene 4), tempo 162, is_playing true
- Bounce: Downloads\\EvAIx_LiveSet_SyntheticAcid_162.mp3 (>=90s)
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

SR = dna.SR
BPM = 162.0
BARS = 10
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR)
HOST, PORT = "127.0.0.1", 9877

OUT = BRIDGE / "samples" / "crisp-dna" / "synthetic-acid"
OUT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_LiveSet_SyntheticAcid_162.mp3")

SCENES = morph.SCENES  # 0-7 same morph scenes

# Force DNA lengths
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


def scream_pattern(seed: int):
    """Classic 303-ish: accents on downbeats, slides between adjacent, rests for groove."""
    rng = dna.mulberry32(seed + 303)
    steps = []
    prev = 0.0
    prev_midi = 0
    for i in range(16):
        # more rests off the grid for gated groove
        rest_p = 0.42 if i % 4 == 1 else (0.28 if i % 4 == 3 else 0.12)
        if rng() < rest_p:
            steps.append({"note": 0.0, "midi": 0, "accent": False, "slide": False})
            continue
        idx = int(rng() * len(dna.PHRYGIAN_HZ))
        # bias toward lower register for scream body
        if rng() < 0.55:
            idx = idx % 5
        hz = dna.PHRYGIAN_HZ[idx]
        midi = dna.PHRYGIAN_MIDI[idx]
        accent = (i % 4 == 0) or (rng() < 0.28)
        slide = prev > 0 and (i > 0) and (rng() < 0.22)
        # force occasional adjacent-step slide
        if prev > 0 and i % 4 == 2 and rng() < 0.45:
            slide = True
        steps.append({"note": hz, "midi": midi, "accent": accent, "slide": slide})
        prev = hz
        prev_midi = midi
    return steps


def render_scream_acid(pattern, acid_id="scream", grit="full", roll=True) -> list[float]:
    """Kickback scream/screech acid: square -> resonant LPF, accents+slides, rolling cut."""
    step = (60.0 / BPM) / 4.0
    total_steps = BARS * 16
    out = [0.0] * N
    l = b = 0.0
    phase = 0.0
    cur_hz = dna.PHRYGIAN_HZ[0]
    target_hz = cur_hz
    env = 0.0
    # Kickback DNA
    if acid_id == "screech":
        res_q = 0.05
    elif acid_id == "scream":
        res_q = 0.08
    else:
        res_q = 0.065
    base_cut0 = 240.0
    env_amt = 3800.0
    grit_drive = 2.8 if grit == "full" else (1.9 if grit == "medium" else 1.2)
    step_idx = -1
    for i in range(N):
        t = i / SR
        s = min(total_steps - 1, int(t / step))
        if s != step_idx:
            step_idx = s
            bar = s // 16
            st = s % 16
            # rolling cutoff rise over bars (Radze-style open scream)
            if roll:
                roll_amt = (bar / max(1, BARS - 1)) * 320.0  # +0..320 Hz base
            else:
                roll_amt = 0.0
            # peak scenes get slightly lower Q (more scream)
            local_q = res_q
            gap = False  # full continuous voice for morph sections
            p = pattern[st]
            if not gap and p["note"] > 0:
                target_hz = p["note"]
                if not p["slide"]:
                    cur_hz = target_hz
                env = 1.0 if p["accent"] else 0.58
            elif not p.get("slide"):
                env *= 0.28  # gated rests
            # stash rolling into base via closure-ish local
            render_scream_acid._base = base_cut0 + roll_amt  # type: ignore
            render_scream_acid._q = local_q  # type: ignore
        base_cut = getattr(render_scream_acid, "_base", base_cut0)
        local_q = getattr(render_scream_acid, "_q", res_q)
        cur_hz += (target_hz - cur_hz) * (0.0045 if env > 0.4 else 0.0020)  # slide glide
        env *= 0.99915
        phase += cur_hz / SR
        phase -= math.floor(phase)
        # square = scream/screech
        osc = (1.0 if phase < 0.5 else -1.0) * env * 0.50
        cut = base_cut + env * env_amt
        f = 2 * math.sin(math.pi * dna.clamp(cut / SR, 0.0001, 0.45))
        l += f * b
        h = osc - l - local_q * b
        b += f * h
        y = dna.tanh_drive(l, grit_drive)
        # soft mid presence boost (synthetic scream in mids)
        out[i] = y
    return out


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


def try_tune_drift(acid_idx: int):
    """Best-effort: push Drift toward square / high resonance if params exist."""
    r = send("get_device_parameters", {"track_index": acid_idx, "device_index": 0})
    if r.get("status") != "success":
        print("Drift params unavailable", r.get("message"))
        return
    dev = (r.get("result") or {}).get("device") or {}
    params = dev.get("parameters") or []
    print("Drift param count", len(params))
    # print interesting names
    for i, p in enumerate(params):
        name = (p.get("name") or "").lower()
        if any(k in name for k in ("osc", "wave", "shape", "filter", "res", "cut", "drive", "timbre", "tone")):
            print(" ", i, p.get("name"), "val", p.get("value"), "min", p.get("min"), "max", p.get("max"))
    # heuristic sets by name
    for i, p in enumerate(params):
        name = (p.get("name") or "").lower()
        mn = float(p.get("min", 0) or 0)
        mx = float(p.get("max", 1) or 1)
        target = None
        if "osc" in name and ("shape" in name or "wave" in name or "type" in name):
            target = mx  # toward square/pulse if continuum
        elif name in ("shape", "waveform", "oscillator"):
            target = mx
        elif "res" in name and "cut" not in name:
            target = mn + (mx - mn) * 0.85
        elif "cut" in name or "freq" in name and "filter" in name:
            target = mn + (mx - mn) * 0.35
        elif "drive" in name or "sat" in name:
            target = mn + (mx - mn) * 0.7
        if target is not None:
            rr = send(
                "set_device_parameter",
                {
                    "track_index": acid_idx,
                    "device_index": 0,
                    "parameter_index": i,
                    "value": float(target),
                },
            )
            print("set Drift", i, p.get("name"), "->", target, rr.get("status"))


def quiet_midi_for_scene(pattern, sid, bars=10):
    """Sparse quiet MIDI double (Drift) — main scream is audio."""
    notes = []
    gate = 0.1875
    slide_dur = 0.42
    keep = {
        0: lambda st, bar: False,
        1: lambda st, bar: st % 4 == 0 and bar % 2 == 0,
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
            # quiet double
            vel = 42 if p["accent"] else 28
            if sid == 1:
                vel = 22
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


def remix_scene(sid, name, kick_path, hats_path, oh_path, perc_path, pattern, acid_id):
    """Load existing CRISP drum layers + new scream acid -> section mix + acid wav."""
    trk_k = dna.read_wav(kick_path) if kick_path.exists() else [0.0] * N
    trk_h = dna.read_wav(hats_path) if hats_path.exists() else [0.0] * N
    trk_oh = dna.read_wav(oh_path) if oh_path.exists() else [0.0] * N
    trk_p = dna.read_wav(perc_path) if perc_path.exists() else [0.0] * N

    def fit(buf):
        buf = list(buf[:N])
        if len(buf) < N:
            buf.extend([0.0] * (N - len(buf)))
        return buf

    trk_k, trk_h, trk_oh, trk_p = map(fit, (trk_k, trk_h, trk_oh, trk_p))

    # scene acid density / character
    acid_drive = {0: 0.0, 1: 0.18, 2: 0.72, 3: 0.82, 4: 0.92, 5: 1.05, 6: 1.12, 7: 0.30}.get(sid, 0.7)
    # screech (lower Q) on peak/break for max scream feel; scream elsewhere
    aid = "screech" if sid in (5, 6) else acid_id
    grit_drive = 3.2 if sid >= 6 else 2.8
    acid_full = render_scream_acid(pattern, acid_id=aid, grit="full", roll=True)
    # apply grit_drive already inside; extra peak bite
    if sid >= 6:
        acid_full = [dna.tanh_drive(x, 1.15) for x in acid_full]
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))

    prefix = f"s{sid}_{name}"
    acid_path = OUT / f"{prefix}_acid_scream.wav"
    dna.write_wav_mono(acid_path, acid, peak_target=0.88)

    # Kick-dominated mix; acid loud enough to scream in mids (~0.52)
    mix = [0.0] * N
    acid_mix_g = 0.52 if sid >= 2 else (0.22 if sid == 1 else 0.0)
    if sid == 5:  # break: acid exposed
        acid_mix_g = 0.68
    if sid == 6:
        acid_mix_g = 0.58
    for i in range(N):
        mono = (
            trk_k[i] * 1.08
            + acid[i] * acid_mix_g
            + trk_h[i] * 0.24
            + trk_oh[i] * 0.18
            + trk_p[i] * 0.20
        )
        mix[i] = dna.tanh_drive(mono, 1.10)
    mix_path = SECTION_MIX_DIR / f"{prefix}_mix.wav"
    write_stereo_mix(mix_path, mix, peak_target=0.90)
    print("scene", sid, name, "acid=", aid, "drive", acid_drive, "mix_g", acid_mix_g)
    return {"acid": acid_path, "mix": mix_path, "kick": kick_path, "hats": hats_path, "oh": oh_path, "perc": perc_path}


def bounce_mp3(scene_paths):
    concat_list = OUT / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for sid, name in SCENES:
            # ffmpeg concat needs escaped paths - use absolute with forward slashes
            p = str(scene_paths[sid]["mix"]).replace("\\", "/")
            f.write(f"file '{p}'\n")
    raw_concat = OUT / "synthetic_acid_concat.wav"
    subprocess.run(
        [dna.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw_concat)],
        check=True,
        capture_output=True,
    )
    loud = OUT / "synthetic_acid_club.wav"
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
    # duration
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
            p = subprocess.run([dna.FFMPEG, "-i", str(MP3)], capture_output=True, text=True)
            import re
            m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", p.stderr)
            if m:
                dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        except Exception:
            pass
    print("MP3", MP3, "dur", round(dur, 2))
    return dur


def main():
    errors = []
    print("=== Synthetic Kickback SCREAM acid liveset @", BPM, "N=", N, f"sec/scene={N/SR:.2f} ===")

    # Ensure drum oneshots / morph drum layers exist (reuse prior morph render)
    morph_dir = BRIDGE / "samples" / "crisp-dna" / "morphs"
    need_regen_drums = False
    for sid, name in SCENES:
        if not (morph_dir / f"s{sid}_{name}_kick.wav").exists():
            need_regen_drums = True
            break
    if need_regen_drums:
        print("Missing morph drum layers — generating via morph.ensure + render")
        rng = dna.mulberry32(dna.SEED ^ 0x15F)
        kick_main, esx_kick, hat_c, hat_o, clap, junk = morph.ensure_oneshots(rng)
        pattern_tmp = scream_pattern(dna.SEED + 7)
        dna.N = N
        dna.BARS = BARS
        for sid, name in SCENES:
            morph.render_scene_layers(sid, name, kick_main, esx_kick, hat_c, hat_o, clap, junk, pattern_tmp)

    pattern = scream_pattern(dna.SEED + 303)
    acid_id = "scream"

    scene_paths = {}
    for sid, name in SCENES:
        kp = morph_dir / f"s{sid}_{name}_kick.wav"
        hp = morph_dir / f"s{sid}_{name}_hats.wav"
        op = morph_dir / f"s{sid}_{name}_oh.wav"
        pp = morph_dir / f"s{sid}_{name}_perc.wav"
        scene_paths[sid] = remix_scene(sid, name, kp, hp, op, pp, pattern, acid_id)

    print("=== Bounce SyntheticAcid MP3 ===")
    try:
        mp3_dur = bounce_mp3(scene_paths)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        mp3_dur = 0.0

    print("=== Ableton: load scream audio + quiet Drift double ===")
    snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=60)
    snap = ok(snap_r, "snapshot")
    if not snap:
        print("ABORT no Ableton — MP3 still written")
        print("MP3_PATH", str(MP3))
        print("MP3_DURATION_SEC", round(mp3_dur, 2))
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

    morph.silence_noisy(by_full)

    acid_midi_idx = by.get("Acid 303 Poly")
    acid_audio_idx = by.get("E-Syn")  # MIDI track cannot hold audio
    kick_idx = by.get("E-Kick")
    hats_idx = by.get("E-Hats")
    perc_idx = by.get("E-Perc")
    oh_idx = by.get("E-OHat") or by.get("E-Snare")
    bass_idx = by.get("Tholin Bass") or by.get("E-Bass")

    # Rename E-Syn to clarify synthetic acid audio voice
    if acid_audio_idx is not None:
        r = send("set_track_name", {"track_index": acid_audio_idx, "name": "Acid Scream Audio"})
        print("rename E-Syn", r.get("status"), r.get("message", r.get("result")))
        by["Acid Scream Audio"] = acid_audio_idx

    # Keep Drift on Acid 303 Poly as quiet double; try tune toward square/res
    if acid_midi_idx is not None:
        r = send("load_browser_item", {"track_index": acid_midi_idx, "item_uri": "query:Synths#Drift"})
        print("Drift load", r.get("status"), r.get("message", r.get("result")))
        try_tune_drift(acid_midi_idx)

    # Clear rows 0-7
    for row, _ in SCENES:
        for idx in (acid_midi_idx, acid_audio_idx, kick_idx, hats_idx, perc_idx, oh_idx, bass_idx):
            if idx is not None:
                safe_delete(idx, row)

    clip_len = float(BEATS)

    for sid, name in SCENES:
        paths = scene_paths[sid]
        # drums from prior morphs (CRISP)
        if kick_idx is not None and morph.layer_has_signal(paths["kick"]):
            load_audio(kick_idx, sid, paths["kick"], f"{name}_kick")
        if hats_idx is not None and morph.layer_has_signal(paths["hats"]):
            load_audio(hats_idx, sid, paths["hats"], f"{name}_hats")
        if oh_idx is not None and morph.layer_has_signal(paths["oh"]):
            load_audio(oh_idx, sid, paths["oh"], f"{name}_oh")
        if perc_idx is not None and morph.layer_has_signal(paths["perc"]):
            load_audio(perc_idx, sid, paths["perc"], f"{name}_perc")
        # MAIN: synthetic scream acid AUDIO
        if acid_audio_idx is not None and morph.layer_has_signal(paths["acid"]):
            load_audio(acid_audio_idx, sid, paths["acid"], f"{name}_scream303")
        # Quiet Drift MIDI double
        midi = quiet_midi_for_scene(pattern, sid, bars=BARS)
        if acid_midi_idx is not None and midi:
            put_midi(acid_midi_idx, sid, clip_len, f"{name}_drift_quiet", midi)
        send("create_locator", {"name": f"{sid}_{name}", "time": float(sid * clip_len)})

    # Fire Full_Tribal (scene 4)
    FIRE_ROW = 4
    fire_name = "Full_Tribal"
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
    print("tempo", res.get("tempo"), "is_playing", res.get("is_playing"))

    print("ACID_VOICE", "Kickback scream/screech synthetic AUDIO on Acid Scream Audio (ex-E-Syn); Drift MIDI quiet double")
    print("FIRED", fire_name, fired)
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(mp3_dur, 2))
    print("ERRORS", errors)
    print("DONE build_synthetic_acid_liveset")


if __name__ == "__main__":
    main()
