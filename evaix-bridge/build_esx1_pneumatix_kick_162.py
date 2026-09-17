# -*- coding: utf-8 -*-
"""ESX-1 Valve Force -> Pneumatix kick/rhythm balance @162 + PA master bounce.

Rebuilds from lossless SwingFX stems (not lossy MP3):
- Kick hotter (~1.50 / break ~0.70)
- Hats/OH quieter acoustic (closed ~0.36, OH ~0.30)
- Perc down; acid/stretch sit under kick
- Valve Tube ~2.1, Swing already baked in stems, Decimator already on JunkPerc
- Ping-pong delay wet lowered (hats quieter)
- PA master: HP26, kick weight @52 bumped, tops shelves, loudnorm I=-8.5
No sidechain. No factory ROM as main voice.
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

_FF_FULL = r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
if Path(_FF_FULL).exists():
    dna.FFMPEG = _FF_FULL

SR = dna.SR
BPM = 162.0
BARS = 24
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR)
HOST, PORT = "127.0.0.1", 9877

STEM_SRC = BRIDGE / "samples" / "crisp-dna" / "esx1-valveforce-swingfx"
OUT = STEM_SRC / "pneumatix_kick"
OUT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_ESX1_PneumatixKick_PA_162.mp3")
NOTES = OUT / "pneumatix_kick_notes.md"

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
FIRE_ROW = 6

TUBE_GAIN = 2.1
DELAY_TIME_BEATS = 0.375
DELAY_WET = 0.11  # lower than SwingFX 0.16 — hats quieter
DELAY_FB = 0.26

# Pneumatix push vs prior PA remix (kick 1.28 / hats 0.52 / OH 0.42)
KICK_G = 1.50
KICK_BREAK_G = 0.70
HATS_G = 0.36
OH_G = 0.30
PERC_SCALE = 0.78  # further down vs SwingFX scene perc_g (was PA ~-1.5dB; more here)
ACID_SCALE = 0.92  # sit under kick
STRETCH_SCALE = 0.88

# PA master with kick bump (+0.7 @52, +0.3 @3.2k) and denser loudnorm
AF_CHAIN = (
    "highpass=f=26:poles=2,"
    "lowshelf=f=90:t=q:w=0.7:g=1.8,"
    "equalizer=f=52:t=q:w=1.1:g=2.9,"
    "equalizer=f=72:t=q:w=1.4:g=-1.2,"
    "equalizer=f=380:t=q:w=1.0:g=-1.0,"
    "equalizer=f=3200:t=q:w=1.6:g=1.9,"
    "equalizer=f=6500:t=q:w=1.2:g=-0.5,"
    "equalizer=f=10000:t=q:w=1.1:g=-2.2,"
    "highshelf=f=7000:t=q:w=0.7:g=-3.2,"
    "lowpass=f=15500:poles=1,"
    "acompressor=threshold=-18dB:ratio=1.6:attack=12:release=180:makeup=1.2,"
    "alimiter=limit=0.89,"
    "loudnorm=I=-8.5:TP=-1.0:LRA=7"
)

GAINS_USED = {
    "kick": KICK_G,
    "kick_break": KICK_BREAK_G,
    "hats_closed": HATS_G,
    "oh": OH_G,
    "perc_scale_vs_swingfx_scene": PERC_SCALE,
    "acid_scale": ACID_SCALE,
    "stretch_scale": STRETCH_SCALE,
    "tube_gain": TUBE_GAIN,
    "delay_wet": DELAY_WET,
    "bpm": BPM,
    "bars_per_scene": BARS,
}


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


def read_wav(path: Path) -> list[float]:
    return dna.read_wav(path)


def valve_force(samples: list[float], tube_gain: float = TUBE_GAIN) -> list[float]:
    bias = 0.045
    norm = math.tanh(tube_gain)
    out = [0.0] * len(samples)
    for i, x in enumerate(samples):
        driven = (x + bias) * tube_gain
        y = math.tanh(driven) / norm - bias * 0.55
        y = 0.88 * y + 0.12 * math.tanh(x * (tube_gain * 0.65))
        out[i] = y
    return out


def pingpong_stereo(
    samples: list[float],
    time_beats: float = DELAY_TIME_BEATS,
    feedback: float = DELAY_FB,
    wet: float = DELAY_WET,
) -> tuple[list[float], list[float]]:
    d = max(1, int(time_beats * 60.0 / BPM * SR))
    L = list(samples)
    R = list(samples)
    for tap in range(4):
        delay = d * (tap + 1)
        g = wet * (feedback ** tap)
        side = tap % 2
        for i in range(delay, len(samples)):
            v = samples[i - delay] * g
            if side == 0:
                L[i] += v
            else:
                R[i] += v
    return L, R


def write_stereo_lr(path: Path, left: list[float], right: list[float], peak_target=0.90):
    n = min(len(left), len(right))
    peak = 1e-9
    for i in range(n):
        peak = max(peak, abs(left[i]), abs(right[i]))
    scale = peak_target / peak
    st = array.array("h")
    for i in range(n):
        lv = max(-32767, min(32767, int(left[i] * scale * 32767)))
        rv = max(-32767, min(32767, int(right[i] * scale * 32767)))
        st.append(lv)
        st.append(rv)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())


def find_ffprobe() -> str:
    cands = [
        r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffprobe.exe",
        r"C:\ffmpeg\bin\ffprobe.exe",
        "ffprobe",
    ]
    ff = Path(dna.FFMPEG)
    cands.insert(0, str(ff.parent / "ffprobe.exe"))
    for c in cands:
        try:
            subprocess.run([c, "-version"], capture_output=True, check=True)
            return c
        except Exception:
            continue
    raise RuntimeError("ffprobe not found")


def scene_gains(sid: int):
    # SwingFX scene tables, then Pneumatix scales
    acid_base = {0: 0.0, 1: 0.0, 2: 0.42, 3: 0.44, 4: 0.46, 5: 0.5, 6: 0.45, 7: 0.22}.get(sid, 0.4)
    perc_base = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.8, 4: 0.88, 5: 0.7, 6: 0.95, 7: 0.4}.get(sid, 0.8)
    st_base = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.85, 4: 0.9, 5: 1.0, 6: 0.8, 7: 0.55}.get(sid, 0.8)
    kick_g = KICK_BREAK_G if sid == 5 else KICK_G
    return {
        "kick": kick_g,
        "hats": HATS_G,
        "oh": OH_G,
        "perc": perc_base * PERC_SCALE,
        "stretch": st_base * STRETCH_SCALE,
        "acid": acid_base * ACID_SCALE,
    }


def remix_scene(sid: int, name: str) -> dict:
    prefix = f"s{sid}_{name}"
    paths_in = {
        "kick": STEM_SRC / f"{prefix}_kick.wav",
        "hats": STEM_SRC / f"{prefix}_hats.wav",
        "oh": STEM_SRC / f"{prefix}_oh.wav",
        "perc": STEM_SRC / f"{prefix}_perc.wav",
        "stretch": STEM_SRC / f"{prefix}_stretch.wav",
        "acid": STEM_SRC / f"{prefix}_acid.wav",
    }
    for k, p in paths_in.items():
        if not p.exists():
            raise FileNotFoundError(f"missing stem {p}")

    trk_k = read_wav(paths_in["kick"])
    trk_h = read_wav(paths_in["hats"])
    trk_oh = read_wav(paths_in["oh"])
    trk_p = read_wav(paths_in["perc"])
    trk_st = read_wav(paths_in["stretch"])
    acid = read_wav(paths_in["acid"])

    # normalize length to N
    def fit(buf):
        if len(buf) > N:
            return buf[:N]
        if len(buf) < N:
            return buf + [0.0] * (N - len(buf))
        return buf

    trk_k, trk_h, trk_oh, trk_p, trk_st, acid = map(fit, (trk_k, trk_h, trk_oh, trk_p, trk_st, acid))
    g = scene_gains(sid)

    # Copy stems out (same content, for Ableton reload) under OUT
    out_paths = {}
    for key, src in paths_in.items():
        dst = OUT / src.name
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            dst.write_bytes(src.read_bytes())
        out_paths[key] = dst

    dry = [0.0] * N
    for i in range(N):
        dry[i] = (
            trk_k[i] * g["kick"]
            + acid[i] * g["acid"]
            + trk_h[i] * g["hats"]
            + trk_oh[i] * g["oh"]
            + trk_p[i] * g["perc"]
            + trk_st[i] * g["stretch"]
        )

    send_src = [0.0] * N
    for i in range(N):
        send_src[i] = (
            acid[i] * g["acid"] * 0.55
            + trk_h[i] * g["hats"] * 0.7
            + trk_oh[i] * g["oh"] * 0.45
        )
    Lpp, Rpp = pingpong_stereo(send_src, wet=DELAY_WET, feedback=DELAY_FB)
    left = [0.0] * N
    right = [0.0] * N
    for i in range(N):
        left[i] = dry[i] + (Lpp[i] - send_src[i]) * 0.9
        right[i] = dry[i] + (Rpp[i] - send_src[i]) * 0.9

    left = valve_force(left, TUBE_GAIN)
    right = valve_force(right, TUBE_GAIN)
    peak = 1e-9
    for i in range(N):
        peak = max(peak, abs(left[i]), abs(right[i]))
    if peak > 0.95:
        s = 0.92 / peak
        left = [x * s for x in left]
        right = [x * s for x in right]

    mix_path = SECTION_MIX_DIR / f"{prefix}_pnx_mix.wav"
    write_stereo_lr(mix_path, left, right, peak_target=0.90)
    out_paths["mix"] = mix_path
    print(
        "scene", sid, name,
        "gains", {k: round(v, 3) for k, v in g.items()},
        "peak", round(peak, 4),
    )
    return out_paths


def bounce_mp3(scene_paths):
    listfile = OUT / "_pnx_concat.txt"
    raw_concat = OUT / "_pnx_concat.wav"
    mastered = OUT / "_pnx_master.wav"
    with open(listfile, "w", encoding="utf-8") as f:
        for sid, name in SCENES:
            p = str(scene_paths[sid]["mix"]).replace("\\", "/")
            f.write(f"file '{p}'\n")
    subprocess.run(
        [dna.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(raw_concat)],
        check=True,
        capture_output=True,
    )
    r = subprocess.run(
        [dna.FFMPEG, "-y", "-i", str(raw_concat), "-af", AF_CHAIN, str(mastered)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print("master fail stderr:", r.stderr[-2000:])
        raise RuntimeError("PA master ffmpeg failed")
    subprocess.run(
        [dna.FFMPEG, "-y", "-i", str(mastered), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3)],
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
    except Exception as e:
        print("ffprobe dur fail", e)
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


def write_notes(dur: float, errors: list):
    text = f"""# EvAIx ESX-1 PneumatixKick PA @162

**Source:** lossless SwingFX stems (`esx1-valveforce-swingfx`)
**Output:** `{MP3}`
**Duration:** {dur:.2f}s
**BPM:** {BPM} (kept 162; Pneumatix ref ~158)

## Stem gains (vs prior PA remix kick 1.28 / hats 0.52 / OH 0.42)

| Bus | Gain |
|-----|------|
| Kick | **{KICK_G}** (break **{KICK_BREAK_G}**) |
| Closed hats | **{HATS_G}** |
| Open hats | **{OH_G}** |
| Perc | SwingFX scene perc × **{PERC_SCALE}** |
| Acid | SwingFX scene acid × **{ACID_SCALE}** |
| Stretch | SwingFX scene stretch × **{STRETCH_SCALE}** |
| Valve Tube | {TUBE_GAIN} |
| Ping-pong delay wet | {DELAY_WET} (was 0.16) |

## ffmpeg -af

```
{AF_CHAIN}
```

## Notes
- No sidechain
- Decimator remains on JunkPerc (baked in SwingFX stems)
- Swing ~59% already in hat/perc stem timing
- Kick EQ @52 = +2.9 dB; punch @3.2k = +1.9 dB; loudnorm I=-8.5
- Errors: {errors or "none"}
"""
    NOTES.write_text(text, encoding="utf-8")
    print("NOTES", NOTES)


def main():
    errors = []
    print("=== ESX-1 PneumatixKick PA remaster @", BPM, "===")
    print("GAINS", GAINS_USED)
    print("AF", AF_CHAIN)

    scene_paths = {}
    for sid, name in SCENES:
        try:
            scene_paths[sid] = remix_scene(sid, name)
        except Exception as e:
            errors.append(f"scene{sid}: {e}")
            print("FAIL scene", sid, e)
            raise

    print("=== Bounce MP3 ===")
    try:
        mp3_dur = bounce_mp3(scene_paths)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        mp3_dur = 0.0

    write_notes(mp3_dur, errors)

    print("=== Ableton load ===")
    try:
        snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=60)
    except Exception as e:
        errors.append(f"ableton connect: {e}")
        print("ABORT no Ableton — MP3 still written", e)
        print("MP3_PATH", str(MP3))
        print("MP3_DURATION_SEC", round(mp3_dur, 2))
        print("STEM_GAINS", GAINS_USED)
        print("AF_CHAIN", AF_CHAIN)
        print("ERRORS", errors)
        return

    snap = ok(snap_r, "snapshot")
    if not snap:
        errors.append("ableton snapshot failed")
        print("ABORT no Ableton snapshot — MP3 still written")
        print("MP3_PATH", str(MP3))
        print("MP3_DURATION_SEC", round(mp3_dur, 2))
        print("STEM_GAINS", GAINS_USED)
        print("AF_CHAIN", AF_CHAIN)
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
    stretch_idx = by.get("ESX Stretch") or by.get("E-Bass") or by.get("ESX Jam") or by.get("E2S Jam")
    jam_idx = by.get("ESX Jam") or by.get("E2S Jam")

    if acid_audio_idx is not None:
        send("set_track_name", {"track_index": acid_audio_idx, "name": "Acid 303"})
    if stretch_idx is not None and stretch_idx not in (kick_idx, hats_idx, perc_idx, oh_idx, acid_audio_idx):
        send("set_track_name", {"track_index": stretch_idx, "name": "ESX Stretch"})
        send("set_track_mute", {"track_index": stretch_idx, "mute": False})

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
        if jam_idx is not None and jam_idx != stretch_idx:
            load_audio(jam_idx, sid, paths["mix"], f"{name}_PNX_mix")
        send("create_locator", {"name": f"{sid}_{name}", "time": float(sid * clip_len)})

    print("=== Fire Peak_Drive row", FIRE_ROW, "===")
    fired = []
    for label, idx, key in [
        ("kick", kick_idx, "kick"),
        ("hats", hats_idx, "hats"),
        ("oh", oh_idx, "oh"),
        ("perc", perc_idx, "perc"),
        ("stretch", stretch_idx, "stretch"),
        ("acid_audio", acid_audio_idx, "acid"),
        ("jam_mix", jam_idx if jam_idx != stretch_idx else None, "mix"),
    ]:
        if idx is None:
            continue
        p = scene_paths[FIRE_ROW].get(key)
        if key != "mix" and (p is None or not morph.layer_has_signal(p)):
            continue
        r = send("fire_clip", {"track_index": idx, "clip_index": FIRE_ROW})
        if r.get("status") == "success":
            fired.append(label)
            print("FIRE", label)
        else:
            print("fire fail", label, r)

    ok(send("start_playback"), "start_playback")
    info = send("get_session_info")
    res = info.get("result") or info
    playing = res.get("is_playing")
    tempo = res.get("tempo")

    if jam_idx is not None and jam_idx != stretch_idx and "jam_mix" in fired and len(fired) > 3:
        send("stop_clip", {"track_index": jam_idx, "clip_index": FIRE_ROW})
        print("stopped jam mix to avoid double with stems")
        fired = [f for f in fired if f != "jam_mix"]

    print("STEM_GAINS", GAINS_USED)
    print("AF_CHAIN", AF_CHAIN)
    print("FIRED", fired)
    print("SCENES", [n for _, n in SCENES])
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(mp3_dur, 2))
    print("IS_PLAYING", playing)
    print("TEMPO", tempo)
    print("ERRORS", errors)
    print("DONE build_esx1_pneumatix_kick_162")


if __name__ == "__main__":
    main()
