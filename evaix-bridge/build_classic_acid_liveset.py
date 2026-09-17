# -*- coding: utf-8 -*-
"""CLASSIC TB-303 acid tekno @ 162 — Radze Try My Acid vibe, NOT laser/FX.

Fixes harder-acid sci-fi character:
- saw osc (or high-Q square), resQ 0.12-0.18, envAmt 2200-2800
- baseCut 280-350, gentle roll (not +520 flybys), grit 1.8-2.2
- shorter gates, acid mix 0.45-0.55 under the kick
- Re-render acid stems scenes 0-7, load Acid 303, fire Full_Tribal
- Bounce: Downloads\\EvAIx_LiveSet_ClassicAcid_162.mp3 (~118s)
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

OUT = BRIDGE / "samples" / "crisp-dna" / "acid-classic"
OUT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_LiveSet_ClassicAcid_162.mp3")

SCENES = morph.SCENES

dna.BPM = BPM
dna.BARS = BARS
dna.BEATS = BEATS
dna.N = N

# Classic TB-303 — musical squelch, not laser whoosh
RES_Q = 0.15          # was 0.04 laser scream; 0.12-0.18 = musical resonance
BASE_CUT0 = 320.0     # was 180; higher start ~280-350
ENV_AMT = 2500.0      # was 4750; gentler open ~2200-2800
ROLL_MAX = 160.0      # was 520 flybys; slow gentle cutoff motion
GRIT = 2.0            # was 3.4; moderate 1.8-2.2
ACID_MIX_BED = 0.50   # was ~0.78-0.85; sit under kick 0.45-0.55
ENV_DECAY = 0.9972    # was 0.99905 long tails; shorter gates
OSC_KIND = "saw"      # classic 303; square only with high resQ


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


def classic_pattern(seed: int):
    """Musical accents/slides — clear but not endless blaster tails."""
    rng = dna.mulberry32(seed + 909)
    steps = []
    prev = 0.0
    for i in range(16):
        rest_p = 0.36 if i % 4 == 1 else (0.26 if i % 4 == 3 else 0.10)
        if rng() < rest_p:
            steps.append({"note": 0.0, "midi": 0, "accent": False, "slide": False})
            continue
        idx = int(rng() * len(dna.PHRYGIAN_HZ))
        if rng() < 0.55:
            idx = idx % 5
        hz = dna.PHRYGIAN_HZ[idx]
        midi = dna.PHRYGIAN_MIDI[idx]
        accent = (i % 4 == 0) or (i % 8 == 3) or (rng() < 0.28)
        slide = prev > 0 and (i > 0) and (rng() < 0.28)
        if prev > 0 and i % 4 in (1, 2) and rng() < 0.40:
            slide = True
        steps.append({"note": hz, "midi": midi, "accent": accent, "slide": slide})
        prev = hz
    return steps


def render_classic_acid(pattern, grit=GRIT, roll=True) -> list[float]:
    """Classic TB-303: saw + moderate res, shorter gates, gentle cutoff motion."""
    step = (60.0 / BPM) / 4.0
    total_steps = BARS * 16
    out = [0.0] * N
    l = b = 0.0
    phase = 0.0
    cur_hz = dna.PHRYGIAN_HZ[0]
    target_hz = cur_hz
    env = 0.0
    res_q = RES_Q
    base_cut0 = BASE_CUT0
    env_amt = ENV_AMT
    grit_drive = grit
    step_idx = -1
    for i in range(N):
        t = i / SR
        s = min(total_steps - 1, int(t / step))
        if s != step_idx:
            step_idx = s
            bar = s // 16
            st = s % 16
            if roll:
                # slow linear-ish open (no aggressive x^2 flybys)
                x = bar / max(1, BARS - 1)
                roll_amt = x * ROLL_MAX
            else:
                roll_amt = 0.0
            local_q = res_q
            # slight more presence late, still musical
            if bar >= BARS - 3:
                local_q = max(0.12, res_q * 0.92)
            p = pattern[st]
            if p["note"] > 0:
                target_hz = p["note"]
                if not p["slide"]:
                    cur_hz = target_hz
                env = 1.0 if p["accent"] else 0.58
            elif not p.get("slide"):
                env *= 0.12  # hard gate off — no long resonant tails
            render_classic_acid._base = base_cut0 + roll_amt  # type: ignore
            render_classic_acid._q = local_q  # type: ignore
        base_cut = getattr(render_classic_acid, "_base", base_cut0)
        local_q = getattr(render_classic_acid, "_q", res_q)
        # slides a bit snappier / musical
        cur_hz += (target_hz - cur_hz) * (0.008 if env > 0.4 else 0.003)
        env *= ENV_DECAY
        phase += cur_hz / SR
        phase -= math.floor(phase)
        if OSC_KIND == "saw":
            osc = (2.0 * phase - 1.0) * env * 0.48
        else:
            # square only if resQ high enough to avoid laser screech
            osc = (1.0 if phase < 0.5 else -1.0) * env * 0.42
        cut = base_cut + env * env_amt
        f = 2 * math.sin(math.pi * dna.clamp(cut / SR, 0.0001, 0.45))
        l += f * b
        h = osc - l - local_q * b
        b += f * h
        y = dna.tanh_drive(l, grit_drive)
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


def quiet_midi_for_scene(pattern, sid, bars=10):
    notes = []
    gate = 0.14  # shorter gates
    slide_dur = 0.32
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
            vel = 44 if p["accent"] else 30
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


def remix_scene(sid, name, kick_path, hats_path, oh_path, perc_path, pattern):
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

    # intro mute, sparse s1, full under kick s2+, break present, peak controlled
    acid_drive = {0: 0.0, 1: 0.28, 2: 0.90, 3: 0.95, 4: 1.0, 5: 1.05, 6: 1.0, 7: 0.40}.get(sid, 0.90)
    acid_full = render_classic_acid(pattern, grit=GRIT, roll=True)
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))

    prefix = f"s{sid}_{name}"
    acid_path = OUT / f"{prefix}_acid_classic.wav"
    dna.write_wav_mono(acid_path, acid, peak_target=0.88)

    # Acid in bed ~0.45-0.55 so it squelches under the kick
    mix = [0.0] * N
    acid_mix_g = {
        0: 0.0,
        1: 0.22,
        2: 0.48,
        3: 0.50,
        4: 0.52,  # Full_Tribal
        5: 0.55,  # break a bit more exposed
        6: 0.52,
        7: 0.30,
    }.get(sid, ACID_MIX_BED)
    kick_g = 0.0 if sid == 5 else 1.08
    for i in range(N):
        mono = (
            trk_k[i] * kick_g
            + acid[i] * acid_mix_g
            + trk_h[i] * 0.24
            + trk_oh[i] * 0.18
            + trk_p[i] * 0.20
        )
        mix[i] = dna.tanh_drive(mono, 1.08)
    mix_path = SECTION_MIX_DIR / f"{prefix}_mix.wav"
    write_stereo_mix(mix_path, mix, peak_target=0.90)
    print("scene", sid, name, "osc", OSC_KIND, "drive", acid_drive, "mix_g", acid_mix_g)
    return {"acid": acid_path, "mix": mix_path, "kick": kick_path, "hats": hats_path, "oh": oh_path, "perc": perc_path}


def bounce_mp3(scene_paths):
    concat_list = OUT / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for sid, name in SCENES:
            p = str(scene_paths[sid]["mix"]).replace("\\", "/")
            f.write(f"file '{p}'\n")
    raw_concat = OUT / "acid_classic_concat.wav"
    subprocess.run(
        [dna.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw_concat)],
        check=True,
        capture_output=True,
    )
    loud = OUT / "acid_classic_club.wav"
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
    print("=== CLASSIC TB-303 acid @", BPM, "N=", N, f"sec/scene={N/SR:.2f} ===")
    print(
        "PARAMS osc=", OSC_KIND, "resQ=", RES_Q, "envAmt=", ENV_AMT,
        "baseCut0=", BASE_CUT0, "rollMax=", ROLL_MAX, "grit=", GRIT,
        "acidMix~", ACID_MIX_BED, "envDecay=", ENV_DECAY,
    )

    morph_dir = BRIDGE / "samples" / "crisp-dna" / "morphs"
    need_regen_drums = False
    for sid, name in SCENES:
        if not (morph_dir / f"s{sid}_{name}_kick.wav").exists():
            need_regen_drums = True
            break
    if need_regen_drums:
        print("Missing morph drum layers — generating")
        rng = dna.mulberry32(dna.SEED ^ 0x15F)
        kick_main, esx_kick, hat_c, hat_o, clap, junk = morph.ensure_oneshots(rng)
        pattern_tmp = classic_pattern(dna.SEED + 7)
        dna.N = N
        dna.BARS = BARS
        for sid, name in SCENES:
            morph.render_scene_layers(sid, name, kick_main, esx_kick, hat_c, hat_o, clap, junk, pattern_tmp)
    else:
        print("Reuse existing CRISP morph drum layers")

    pattern = classic_pattern(dna.SEED + 303)
    accents = sum(1 for p in pattern if p["accent"])
    slides = sum(1 for p in pattern if p["slide"])
    notes_on = sum(1 for p in pattern if p["note"] > 0)
    print("pattern notes", notes_on, "accents", accents, "slides", slides)

    scene_paths = {}
    for sid, name in SCENES:
        kp = morph_dir / f"s{sid}_{name}_kick.wav"
        hp = morph_dir / f"s{sid}_{name}_hats.wav"
        op = morph_dir / f"s{sid}_{name}_oh.wav"
        pp = morph_dir / f"s{sid}_{name}_perc.wav"
        scene_paths[sid] = remix_scene(sid, name, kp, hp, op, pp, pattern)

    print("=== Bounce ClassicAcid MP3 ===")
    try:
        mp3_dur = bounce_mp3(scene_paths)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        mp3_dur = 0.0

    print("=== Ableton: load classic acid + fire Full_Tribal ===")
    snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=60)
    snap = ok(snap_r, "snapshot")
    if not snap:
        print("ABORT no Ableton — MP3 still written")
        print("MP3_PATH", str(MP3))
        print("MP3_DURATION_SEC", round(mp3_dur, 2))
        print("ACID_PARAMS", {
            "osc": OSC_KIND, "resQ": RES_Q, "envAmt": ENV_AMT,
            "baseCut": BASE_CUT0, "rollMax": ROLL_MAX, "grit": GRIT,
            "acidMix": ACID_MIX_BED,
        })
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
    acid_audio_idx = (
        by.get("Acid 303")
        or by.get("Acid Scream Audio")
        or by.get("E-Syn")
    )
    kick_idx = by.get("E-Kick")
    hats_idx = by.get("E-Hats")
    perc_idx = by.get("E-Perc")
    oh_idx = by.get("E-OHat") or by.get("E-Snare")
    bass_idx = by.get("Tholin Bass") or by.get("E-Bass")

    if acid_audio_idx is not None:
        r = send("set_track_name", {"track_index": acid_audio_idx, "name": "Acid 303"})
        print("rename Acid 303", r.get("status"), r.get("message", r.get("result")))
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
            load_audio(perc_idx, sid, paths["perc"], f"{name}_perc")
        if acid_audio_idx is not None and morph.layer_has_signal(paths["acid"]):
            load_audio(acid_audio_idx, sid, paths["acid"], f"{name}_classic303")
        midi = quiet_midi_for_scene(pattern, sid, bars=BARS)
        if acid_midi_idx is not None and midi:
            put_midi(acid_midi_idx, sid, clip_len, f"{name}_drift_quiet", midi)
        send("create_locator", {"name": f"{sid}_{name}", "time": float(sid * clip_len)})

    FIRE_ROW = 4
    fire_name = "Full_Tribal"
    if not morph.layer_has_signal(scene_paths[4]["acid"]):
        FIRE_ROW = 6
        fire_name = "Peak_Drive"

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

    print("ACID_VOICE", "CLASSIC TB-303 SAW AUDIO on Acid 303 (ex Acid Scream Audio)")
    print("ACID_PARAMS", {
        "osc": OSC_KIND,
        "resQ": RES_Q,
        "envAmt": ENV_AMT,
        "baseCut0": BASE_CUT0,
        "rollMax": ROLL_MAX,
        "grit": GRIT,
        "envDecay": ENV_DECAY,
        "acidMix_fullTribal": 0.52,
        "acidMix_break": 0.55,
        "acidMix_peak": 0.52,
        "acidMix_bed": ACID_MIX_BED,
        "pattern_accents": accents,
        "pattern_slides": slides,
        "laser_character": "REMOVED",
    })
    print("FIRED", fire_name, fired)
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(mp3_dur, 2))
    print("ERRORS", errors)
    print("DONE build_classic_acid_liveset")


if __name__ == "__main__":
    main()
