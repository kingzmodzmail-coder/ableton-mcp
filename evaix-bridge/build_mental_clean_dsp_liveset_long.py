# -*- coding: utf-8 -*-
"""MENTAL CLEAN DSP LONG @ 162 — 16-section free-party live (~10 min).

Reuses DSP / classic saw 303 / industrial from build_mental_clean_dsp_liveset.
Ableton: 8 launchable scenes covering the arc.
MP3: full continuous 16-section bounce >= 8 min.
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
import build_classic_acid_liveset as classic  # noqa: E402
import build_mental_clean_dsp_liveset as base  # noqa: E402

SR = dna.SR
BPM = 162.0
# 16 sections x 24 bars @ 162 => ~35.56s each => ~9.48 min total
BARS = 24
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR)
HOST, PORT = "127.0.0.1", 9877

OUT = BRIDGE / "samples" / "crisp-dna" / "mental-clean-dsp-long"
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"
ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_LiveSet_MentalClean_Long_162.mp3")

# 16 continuous arrangement sections (Pneumatix/VdW hybrid)
SECTIONS = [
    (0, "Atm_Kick_A"),
    (1, "Atm_Kick_B"),
    (2, "Hats_In"),
    (3, "Muted_Acid"),
    (4, "Clank_Build"),
    (5, "Full_Mental"),
    (6, "Break_Fragile"),
    (7, "Peak_A"),
    (8, "Peak_B"),
    (9, "Break2_Mute"),
    (10, "Return_Hard"),
    (11, "Dual_Energy"),
    (12, "Acid_Exposed"),
    (13, "Final_Peak_A"),
    (14, "Final_Peak_B"),
    (15, "Outro_Strip"),
]

# Ableton only ~8 scene rows: group the arc (representative section per row)
ABLETON_SCENES = [
    (0, 1, "Intro"),          # secs 1-2
    (1, 3, "Hats_Acid"),      # secs 3-4
    (2, 5, "Full_Mental"),    # secs 5-6
    (3, 6, "Break"),          # sec 7
    (4, 8, "Peak"),           # secs 8-9  <-- fire mid/peak
    (5, 9, "Break2"),         # sec 10
    (6, 11, "Return"),        # secs 11-12
    (7, 14, "Final_Outro"),   # secs 13-15 peak/outro feel
]
FIRE_ABLETON_ROW = 4  # Peak

RES_Q = base.RES_Q
BASE_CUT0 = base.BASE_CUT0
ENV_AMT = base.ENV_AMT
ROLL_MAX = base.ROLL_MAX
GRIT = base.GRIT
ACID_MIX_BED = base.ACID_MIX_BED
ENV_DECAY = base.ENV_DECAY
OSC_KIND = base.OSC_KIND

# Sync shared module lengths
for mod in (dna, classic, base):
    mod.BPM = BPM
    mod.BARS = BARS
    mod.BEATS = BEATS
    mod.N = N
classic.RES_Q = RES_Q
classic.BASE_CUT0 = BASE_CUT0
classic.ENV_AMT = ENV_AMT
classic.ROLL_MAX = ROLL_MAX
classic.GRIT = GRIT
classic.ENV_DECAY = ENV_DECAY
classic.OSC_KIND = OSC_KIND
classic.OUT = OUT
classic.SECTION_MIX_DIR = SECTION_MIX_DIR
base.OUT = OUT
base.ONESHOT = ONESHOT
base.SECTION_MIX_DIR = SECTION_MIX_DIR
base.BPM = BPM
base.BARS = BARS
base.BEATS = BEATS
base.N = N


def send(cmd, params=None, timeout=90.0):
    return base.send(cmd, params, timeout)


def ok(r, label):
    return base.ok(r, label)


def safe_delete(track_index, clip_index):
    base.safe_delete(track_index, clip_index)


def load_audio(track_index, clip_index, path: Path, name: str):
    return base.load_audio(track_index, clip_index, path, name)


def put_midi(track_index, clip_index, length, name, notes):
    return base.put_midi(track_index, clip_index, length, name, notes)


def place(buf, sample, beat, gain=1.0):
    if sample is None:
        return
    start = int(beat * 60.0 / BPM * SR)
    for i, v in enumerate(sample):
        j = start + i
        if 0 <= j < len(buf):
            buf[j] += v * gain


def ensure_shots():
    """Reuse base oneshot bake but redirect ONESHOT/OUT already set."""
    # Prefer already-baked oneshots from short set if present
    short = BRIDGE / "samples" / "crisp-dna" / "mental-clean-dsp" / "oneshots"
    if short.exists():
        for p in short.glob("*.wav"):
            dst = ONESHOT / p.name
            if not dst.exists():
                try:
                    dst.write_bytes(p.read_bytes())
                except Exception:
                    pass
    shots = base.ensure_industrial_oneshots()
    return shots


def render_section(sid: int, name: str, shots: dict, pattern):
    kick_main = shots["kick_main"]
    esx_kick = shots["esx_kick"]
    hat_c = shots["hat_c"]
    hat_o = shots["hat_o"]
    clank = shots["clank"]
    metals = shots["metals"]
    atm_metal = shots["atm_metal"]
    noise = shots["noise"]

    trk_k = [0.0] * N
    trk_h = [0.0] * N
    trk_oh = [0.0] * N
    trk_p = [0.0] * N

    m0 = metals[0] if metals else None
    m1 = metals[1] if len(metals) > 1 else m0
    m2 = metals[2] if len(metals) > 2 else None
    m3 = metals[3] if len(metals) > 3 else None

    for bar in range(BARS):
        base_b = bar * 4.0
        mid = bar >= BARS // 2
        late = bar >= (BARS * 3) // 4

        # --- KICK ---
        if sid in (6, 12):
            # fragile / acid-exposed breaks: mostly mute kick
            if sid == 12 and bar % 4 == 0:
                place(trk_k, kick_main, base_b + 0.0, 0.35)
            elif sid == 6 and bar in (0, BARS - 1):
                place(trk_k, kick_main, base_b, 0.22)
        elif sid == 9:
            # Break2 kick mute game: on/off every 2 bars
            if (bar // 2) % 2 == 0:
                for step in (0, 4, 8, 12):
                    place(trk_k, kick_main, base_b + step * 0.25, 1.05)
                    if esx_kick is not None:
                        place(trk_k, esx_kick, base_b + step * 0.25, 0.16)
            else:
                if bar % 2 == 1:
                    place(trk_k, kick_main, base_b, 0.40)
        elif sid == 15:
            if bar < BARS // 2:
                for step in (0, 4, 8, 12):
                    g = 0.95 if bar < BARS // 3 else 0.70
                    place(trk_k, kick_main, base_b + step * 0.25, g)
            elif bar < (BARS * 3) // 4:
                for step in (0, 8):
                    place(trk_k, kick_main, base_b + step * 0.25, 0.50)
        elif sid in (0, 1):
            # longer atm/kick intro
            kg = 0.72 if sid == 0 else 0.88
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base_b + step * 0.25, kg)
                if esx_kick is not None and sid == 1:
                    place(trk_k, esx_kick, base_b + step * 0.25, 0.12)
            if sid == 0 and atm_metal is not None and bar % 4 == 2:
                place(trk_p, atm_metal, base_b + 1.5, 0.28)
        elif sid in (7, 8, 13, 14):
            kg = 1.15 if sid in (8, 14) else 1.10
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base_b + step * 0.25, kg)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base_b + step * 0.25, 0.20)
            if late or sid in (8, 14):
                place(trk_k, kick_main, base_b + 1.5, 0.30)
                place(trk_k, kick_main, base_b + 3.5, 0.26)
        else:
            kg = 1.05 if sid >= 10 else (1.0 if sid >= 4 else 0.92)
            for step in (0, 4, 8, 12):
                place(trk_k, kick_main, base_b + step * 0.25, kg)
                if esx_kick is not None:
                    place(trk_k, esx_kick, base_b + step * 0.25, 0.14 * kg)

        # --- HATS ---
        if sid == 0:
            pass
        elif sid == 1:
            if mid:
                for i, st in enumerate(range(0, 16, 2)):
                    place(trk_h, hat_c, base_b + st * 0.25, 0.40 if i % 2 == 0 else 0.26)
        elif sid == 2:
            for i, st in enumerate(range(0, 16, 2)):
                place(trk_h, hat_c, base_b + st * 0.25, 0.68 if i % 2 == 0 else 0.45)
        elif sid == 3:
            for i, st in enumerate(range(0, 16, 2)):
                place(trk_h, hat_c, base_b + st * 0.25, 0.70 if i % 2 == 0 else 0.48)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base_b + st * 0.25, 0.36)
        elif sid in (4, 5, 10, 11):
            for st in range(16):
                swing = 0.012 if st % 2 else 0.0
                g = 0.76 if st % 2 == 0 else 0.46
                place(trk_h, hat_c, base_b + st * 0.25 + swing, g)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base_b + st * 0.25, 0.42 if sid in (5, 11) else 0.36)
        elif sid in (6, 12):
            for st in range(16):
                swing = 0.016 if st % 2 else 0.0
                place(trk_h, hat_c, base_b + st * 0.25 + swing, 0.38 if st % 2 == 0 else 0.24)
            for st in (6, 14):
                place(trk_oh, hat_o, base_b + st * 0.25, 0.26)
        elif sid in (7, 8, 13, 14):
            for st in range(16):
                swing = 0.010 if st % 2 else 0.0
                place(trk_h, hat_c, base_b + st * 0.25 + swing, 0.82 if st % 2 == 0 else 0.52)
            for st in (2, 6, 10, 14):
                place(trk_oh, hat_o, base_b + st * 0.25, 0.48)
        elif sid == 9:
            if (bar // 2) % 2 == 0:
                for i, st in enumerate(range(0, 16, 2)):
                    place(trk_h, hat_c, base_b + st * 0.25, 0.55 if i % 2 == 0 else 0.34)
            else:
                for st in range(16):
                    swing = 0.014 if st % 2 else 0.0
                    place(trk_h, hat_c, base_b + st * 0.25 + swing, 0.42 if st % 2 == 0 else 0.28)
        elif sid == 15:
            if bar < BARS // 3:
                for i, st in enumerate(range(0, 16, 2)):
                    place(trk_h, hat_c, base_b + st * 0.25, 0.40 if i % 2 == 0 else 0.24)

        # --- INDUSTRIAL (1-2 Full; denser Peak only) ---
        if sid == 0 and atm_metal is not None and bar % 3 == 0:
            place(trk_p, atm_metal, base_b + 2.0, 0.22)
        elif sid == 4:
            place(trk_p, clank, base_b + 3 * 0.25, 0.85)
            place(trk_p, clank, base_b + 11 * 0.25, 0.80)
            if m0 is not None and bar % 2 == 1:
                place(trk_p, m0, base_b + 7 * 0.25, 0.42)
        elif sid in (5, 10, 11):
            place(trk_p, clank, base_b + 3 * 0.25, 0.90)
            place(trk_p, clank, base_b + 11 * 0.25, 0.86)
            if bar % 2 == 0:
                place(trk_p, m0, base_b + 5 * 0.25, 0.48)
            else:
                place(trk_p, m1, base_b + 9 * 0.25, 0.45)
            if noise is not None and bar % 8 in (4,):
                place(trk_p, noise, base_b + 7 * 0.25, 0.28)
            if sid == 11 and m0 is not None and mid:
                # dual energy: still only 1-2 voices, slightly busier placement
                place(trk_p, m0 if bar % 2 else m1, base_b + 13 * 0.25, 0.40)
        elif sid in (6, 12):
            if atm_metal is not None:
                place(trk_p, atm_metal, base_b + 1.0, 0.36)
            if clank is not None and bar % 2 == 0:
                place(trk_p, clank, base_b + 11 * 0.25, 0.40)
            if noise is not None and bar % 4 == 2:
                place(trk_p, noise, base_b + 2.5, 0.24)
        elif sid in (7, 8, 13, 14):
            place(trk_p, clank, base_b + 3 * 0.25, 0.95)
            place(trk_p, clank, base_b + 11 * 0.25, 0.92)
            if mid or sid in (8, 14):
                place(trk_p, clank, base_b + 7 * 0.25, 0.55)
            place(trk_p, m0, base_b + 1 * 0.25, 0.50)
            place(trk_p, m1, base_b + 5 * 0.25, 0.52)
            if m2 is not None:
                place(trk_p, m2, base_b + 9 * 0.25, 0.42)
            if m3 is not None and bar % 2 == 0:
                place(trk_p, m3, base_b + 13 * 0.25, 0.38)
            if noise is not None:
                place(trk_p, noise, base_b + 7 * 0.25, 0.32)
        elif sid == 9:
            if clank is not None:
                place(trk_p, clank, base_b + 3 * 0.25, 0.55)
                place(trk_p, clank, base_b + 11 * 0.25, 0.50)
            if m0 is not None and bar % 2:
                place(trk_p, m0, base_b + 7 * 0.25, 0.36)
        elif sid == 15:
            if bar < 4 and clank is not None:
                place(trk_p, clank, base_b + 3 * 0.25, 0.42)
                place(trk_p, clank, base_b + 11 * 0.25, 0.36)

    # Acid drive per section
    acid_drive = {
        0: 0.0, 1: 0.0, 2: 0.0, 3: 0.78, 4: 0.92, 5: 1.0,
        6: 1.05, 7: 1.0, 8: 1.0, 9: 0.95, 10: 1.0, 11: 1.02,
        12: 1.12, 13: 1.0, 14: 1.0, 15: 0.30,
    }.get(sid, 0.90)
    grit_extra = 0.10 if sid in (7, 8, 13, 14) else 0.0
    acid_full = classic.render_classic_acid(pattern, grit=GRIT + grit_extra, roll=True)
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))

    # Per-stem DSP
    trk_k = base.dsp_kick(trk_k)
    trk_h = base.dsp_hats(trk_h)
    trk_oh = base.dsp_oh(trk_oh)
    under_db = {
        4: -7.0, 5: -8.0, 6: -7.5, 7: -6.5, 8: -6.5,
        9: -8.0, 10: -8.0, 11: -7.5, 12: -7.5,
        13: -6.5, 14: -6.5, 15: -10.0,
    }.get(sid, -8.0)
    trk_p = base.dsp_industrial(trk_p, under_kick_db=under_db)
    acid = base.dsp_acid(acid, trk_k)

    prefix = f"s{sid:02d}_{name}"
    paths = {
        "kick": OUT / f"{prefix}_kick.wav",
        "hats": OUT / f"{prefix}_hats.wav",
        "oh": OUT / f"{prefix}_oh.wav",
        "perc": OUT / f"{prefix}_perc.wav",
        "acid": OUT / f"{prefix}_acid_classic.wav",
    }
    base.write_mono(paths["kick"], trk_k, 0.90)
    base.write_mono(paths["hats"], trk_h, 0.72)
    base.write_mono(paths["oh"], trk_oh, 0.68)
    base.write_mono(paths["perc"], trk_p, 0.55)
    base.write_mono(paths["acid"], acid, 0.78)

    acid_mix_g = {
        0: 0.0, 1: 0.0, 2: 0.0, 3: 0.40, 4: 0.46, 5: 0.48,
        6: 0.52, 7: 0.48, 8: 0.48, 9: 0.50, 10: 0.48, 11: 0.50,
        12: 0.58, 13: 0.48, 14: 0.50, 15: 0.22,
    }.get(sid, ACID_MIX_BED)
    perc_g = {
        0: 0.35, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.85, 5: 0.90,
        6: 0.80, 7: 1.00, 8: 1.00, 9: 0.70, 10: 0.90, 11: 0.95,
        12: 0.75, 13: 1.00, 14: 1.00, 15: 0.50,
    }.get(sid, 0.85)
    kick_g = 0.0 if sid in (6, 12) and False else (0.15 if sid == 6 else (0.25 if sid == 12 else 1.10))
    if sid == 6:
        kick_g = 0.12
    elif sid == 12:
        kick_g = 0.18
    hats_g = 0.85
    oh_g = 0.70

    mix = [0.0] * N
    for i in range(N):
        mix[i] = (
            trk_k[i] * kick_g
            + acid[i] * acid_mix_g
            + trk_h[i] * hats_g
            + trk_oh[i] * oh_g
            + trk_p[i] * perc_g
        )
    mix = base.master_bus_python(mix)
    mix_path = SECTION_MIX_DIR / f"{prefix}_mix.wav"
    base.write_stereo_mix(mix_path, mix, peak_target=0.91)
    paths["mix"] = mix_path
    print("section", sid, name, "acid_mix", acid_mix_g, "perc_under_db", under_db, "sec", round(N / SR, 2))
    return paths


def quiet_midi_for_section(pattern, sid, bars=BARS):
    notes = []
    gate = 0.14
    slide_dur = 0.32
    keep = {
        0: lambda st, bar: False,
        1: lambda st, bar: False,
        2: lambda st, bar: False,
        3: lambda st, bar: st % 2 == 0,
        4: lambda st, bar: True,
        5: lambda st, bar: True,
        6: lambda st, bar: True,
        7: lambda st, bar: True,
        8: lambda st, bar: True,
        9: lambda st, bar: True,
        10: lambda st, bar: True,
        11: lambda st, bar: True,
        12: lambda st, bar: True,
        13: lambda st, bar: True,
        14: lambda st, bar: True,
        15: lambda st, bar: st % 4 == 0 and bar < bars // 3,
    }.get(sid, lambda st, bar: True)
    for bar in range(bars):
        base_b = bar * 4.0
        for st, p in enumerate(pattern):
            if p["midi"] <= 0 or not keep(st, bar):
                continue
            dur = slide_dur if p["slide"] else gate
            vel = 44 if p["accent"] else 30
            notes.append(
                {
                    "pitch": int(p["midi"]),
                    "start_time": base_b + st * 0.25,
                    "duration": dur,
                    "velocity": vel,
                    "mute": False,
                }
            )
    return notes


def bounce_mp3(section_paths):
    concat_list = OUT / "concat_list_long.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for sid, name in SECTIONS:
            p = str(section_paths[sid]["mix"]).replace("\\", "/")
            f.write(f"file '{p}'\n")
    raw_concat = OUT / "mental_clean_dsp_long_concat.wav"
    subprocess.run(
        [dna.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw_concat)],
        check=True,
        capture_output=True,
    )
    loud = OUT / "mental_clean_dsp_long_club.wav"
    af = (
        "highpass=f=28,"
        "equalizer=f=300:t=q:w=0.9:g=-2.0,"
        "treble=f=11000:t=q:w=0.7:g=-2.5,"
        "acompressor=threshold=-18dB:ratio=2.0:attack=12:release=180:makeup=2,"
        "alimiter=limit=0.92:attack=5:release=50,"
        "loudnorm=I=-9.5:TP=-1.2:LRA=8"
    )
    try:
        subprocess.run(
            [dna.FFMPEG, "-y", "-i", str(raw_concat), "-af", af, "-ar", "44100", str(loud)],
            check=True,
            capture_output=True,
            text=True,
        )
        src = loud
        print("ffmpeg master OK")
    except Exception as e:
        print("ffmpeg master fail, using python-mastered concat", e)
        src = raw_concat
    subprocess.run(
        [dna.FFMPEG, "-y", "-i", str(src), "-codec:a", "libmp3lame", "-b:a", "192k", str(MP3)],
        check=True,
        capture_output=True,
    )
    dur = 16 * (N / SR)
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
            import re
            p = subprocess.run([dna.FFMPEG, "-i", str(MP3)], capture_output=True, text=True)
            m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", p.stderr)
            if m:
                dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        except Exception:
            pass
    print("MP3", MP3, "dur", round(dur, 2))
    return dur


def silence_mental_atm(by_full):
    base.silence_mental_atm(by_full)


def main():
    errors = []
    sec_len = N / SR
    total_est = 16 * sec_len
    print("=== MENTAL CLEAN DSP LONG classic 303 @", BPM, "N=", N, f"sec/section={sec_len:.2f} total~{total_est:.1f}s ===")
    print("PARAMS osc=", OSC_KIND, "resQ=", RES_Q, "16 sections x", BARS, "bars")
    print("DSP: kick HP28+tanh | hats HP200 LP13k | ind HP150 LP9k gate | acid HP60 LP5.5k duck | lim0.92 -9.5 LUFS")

    shots = ensure_shots()
    pattern = classic.classic_pattern(dna.SEED + 303)
    accents = sum(1 for p in pattern if p["accent"])
    slides = sum(1 for p in pattern if p["slide"])
    print("pattern accents", accents, "slides", slides)

    section_paths = {}
    for sid, name in SECTIONS:
        section_paths[sid] = render_section(sid, name, shots, pattern)

    print("=== Bounce MentalClean_Long MP3 ===")
    try:
        mp3_dur = bounce_mp3(section_paths)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        mp3_dur = 0.0

    print("=== Ableton load 8 scenes covering 16-section arc ===")
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

    silence_mental_atm(by_full)

    acid_midi_idx = by.get("Acid 303 Poly")
    acid_audio_idx = by.get("Acid 303") or by.get("Acid Scream Audio") or by.get("E-Syn")
    kick_idx = by.get("E-Kick")
    hats_idx = by.get("E-Hats")
    perc_idx = by.get("E-Perc")
    oh_idx = by.get("E-OHat") or by.get("E-Snare")
    bass_idx = by.get("Tholin Bass") or by.get("E-Bass")

    if acid_audio_idx is not None:
        send("set_track_name", {"track_index": acid_audio_idx, "name": "Acid 303"})
        by["Acid 303"] = acid_audio_idx

    if acid_midi_idx is not None:
        r = send("load_browser_item", {"track_index": acid_midi_idx, "item_uri": "query:Synths#Drift"})
        print("Drift load", r.get("status"), r.get("message", r.get("result")))

    for row in range(8):
        for idx in (acid_midi_idx, acid_audio_idx, kick_idx, hats_idx, perc_idx, oh_idx, bass_idx):
            if idx is not None:
                safe_delete(idx, row)

    clip_len = float(BEATS)

    for row, src_sid, scene_name in ABLETON_SCENES:
        paths = section_paths[src_sid]
        if kick_idx is not None and morph.layer_has_signal(paths["kick"]):
            load_audio(kick_idx, row, paths["kick"], f"{scene_name}_kick_dsp")
        if hats_idx is not None and morph.layer_has_signal(paths["hats"]):
            load_audio(hats_idx, row, paths["hats"], f"{scene_name}_hats_dsp")
        if oh_idx is not None and morph.layer_has_signal(paths["oh"]):
            load_audio(oh_idx, row, paths["oh"], f"{scene_name}_oh_dsp")
        if perc_idx is not None and morph.layer_has_signal(paths["perc"]):
            load_audio(perc_idx, row, paths["perc"], f"{scene_name}_ind_dsp")
        if acid_audio_idx is not None and morph.layer_has_signal(paths["acid"]):
            load_audio(acid_audio_idx, row, paths["acid"], f"{scene_name}_classic303_dsp")
        midi = quiet_midi_for_section(pattern, src_sid, bars=BARS)
        if acid_midi_idx is not None and midi:
            put_midi(acid_midi_idx, row, clip_len, f"{scene_name}_drift_quiet", midi)
        send("create_locator", {"name": f"{row}_{scene_name}", "time": float(row * clip_len)})

    fire_name = ABLETON_SCENES[FIRE_ABLETON_ROW][2]
    fire_src = ABLETON_SCENES[FIRE_ABLETON_ROW][1]
    print("=== Fire", fire_name, "row", FIRE_ABLETON_ROW, "src_section", fire_src, "===")
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
        if key and not morph.layer_has_signal(section_paths[fire_src][key]):
            continue
        if label == "acid_midi" and not quiet_midi_for_section(pattern, fire_src, bars=BARS):
            continue
        r = send("fire_clip", {"track_index": idx, "clip_index": FIRE_ABLETON_ROW})
        if r.get("status") == "success":
            fired.append(label)
            print("FIRE", label, "row", FIRE_ABLETON_ROW)
        else:
            print("fire fail", label, r)

    ok(send("start_playback"), "start_playback")
    info = send("get_session_info")
    res = info.get("result") or info
    playing = res.get("is_playing")
    print("tempo", res.get("tempo"), "is_playing", playing)

    print("ABLETON_SCENES", [(r, n, f"src=s{s}") for r, s, n in ABLETON_SCENES])
    print("FIRED", fire_name, fired)
    print("INDUSTRIAL_SAMPLES", shots["used"])
    print("HAT_SRC", shots["hat_src"])
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(mp3_dur, 2))
    print("IS_PLAYING", playing)
    print("ERRORS", errors)
    print("DONE build_mental_clean_dsp_liveset_long")


if __name__ == "__main__":
    main()
