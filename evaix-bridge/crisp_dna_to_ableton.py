# -*- coding: utf-8 -*-
"""CRISP DNA -> Electribe master -> Ableton Live (162 BPM Mental).

Ports Kickback synth DNA (sledge kick / screech acid / shuffle perc / full grit)
at 162 BPM, masters ESX factory one-shots through the Electribe esx-1 convert
chain, loads Intro/Drop/Break/Peak scenes, fires Drop, bounces listen MP3.
"""
from __future__ import annotations

import array
import json
import math
import random
import shutil
import socket
import subprocess
import wave
from pathlib import Path

SR = 44100
BPM = 162.0  # Mental default is 168 in kickback.ts — FORCE 162
BARS = 8
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR)
SEED = 0xC2157

FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
BRIDGE = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge")
OUT = BRIDGE / "samples" / "crisp-dna"
OUT.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_CRISP_DNA_Ableton_162.mp3")
HOST, PORT = "127.0.0.1", 9877

# Scenes: Intro -> Drop -> Break -> Peak
SCENES = [
    (0, "Intro"),
    (1, "Drop"),
    (2, "Break"),
    (3, "Peak"),
]
DROP_ROW = 1

# Phrygian (D) like kickback.ts
PHRYGIAN_HZ = [73.42, 77.78, 87.31, 98.0, 110.0, 116.54, 130.81, 146.83]
# MIDI approx for Drift acid (D Phrygian around D2+)
PHRYGIAN_MIDI = [38, 39, 41, 43, 45, 46, 48, 50]


def find_ffmpeg() -> str:
    for c in [
        "ffmpeg",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe",
    ]:
        try:
            subprocess.run([c, "-version"], capture_output=True, check=True)
            return c
        except Exception:
            continue
    raise RuntimeError("ffmpeg not found")


FFMPEG = find_ffmpeg()


def mulberry32(seed: int):
    a = seed & 0xFFFFFFFF

    def rng():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = (t ^ (t >> 15)) * (t | 1) & 0xFFFFFFFF
        t ^= (t + ((t ^ (t >> 7)) * (t | 61) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rng


def clamp(x, a, b):
    return min(b, max(a, x))


def hp1(x, prev_x, prev_y, a):
    return a * (prev_y + x - prev_x)


def tanh_drive(x, amt):
    return math.tanh(x * amt)


# --- Kickback DNA synth (ported from kickback.ts) ---

def synth_kick_sledge(rng, grit="full") -> list[float]:
    n = int(SR * 0.34)
    out = [0.0] * n
    f0 = 50.0  # sledge
    decay = 0.16
    drive = 2.4 if grit == "full" else 1.6
    hpf = 62.0
    hp_a = math.exp((-2 * math.pi * hpf) / SR)
    phase = 0.0
    hp_x = 0.0
    hp_y = 0.0
    for i in range(n):
        t = i / SR
        body = math.exp(-t / decay)
        click_env = math.exp(-t / 0.004)
        pitch = f0 * (1 + 8 * math.exp(-t / 0.012))
        phase += (2 * math.pi * pitch) / SR
        sine = math.sin(phase)
        click = (rng() * 2 - 1) * click_env * 0.35
        x = sine * body * 0.9 + click
        x = tanh_drive(x, drive)
        y = hp1(x, hp_x, hp_y, hp_a)
        hp_x, hp_y = x, y
        out[i] = y * 0.95
    return out


def synth_hat(rng, open_hat=False) -> list[float]:
    n = int(SR * (0.18 if open_hat else 0.045))
    out = [0.0] * n
    decay = 0.07 if open_hat else 0.018
    hp_x = hp_y = 0.0
    a = math.exp((-2 * math.pi * 6200) / SR)
    gain = 0.22 if open_hat else 0.18
    for i in range(n):
        t = i / SR
        nse = rng() * 2 - 1
        y = hp1(nse, hp_x, hp_y, a)
        hp_x, hp_y = nse, y
        out[i] = y * math.exp(-t / decay) * gain
    return out


def synth_clap(rng) -> list[float]:
    n = int(SR * 0.22)
    out = [0.0] * n
    for b in (0.0, 0.012, 0.024, 0.04):
        start = int(b * SR)
        for i in range(int(0.03 * SR)):
            idx = start + i
            if idx >= n:
                break
            t = i / SR
            out[idx] += (rng() * 2 - 1) * math.exp(-t / 0.012) * 0.35
    hp_x = hp_y = 0.0
    a = math.exp((-2 * math.pi * 900) / SR)
    for i in range(n):
        y = hp1(out[i], hp_x, hp_y, a)
        hp_x = out[i]
        hp_y = y
        out[i] = tanh_drive(y, 2.2) * 0.55
    return out


def acid_pattern(seed: int):
    rng = mulberry32(seed + 99)
    steps = []
    prev = 0.0
    for i in range(16):
        rest = rng() < (0.45 if i % 4 == 1 else 0.18)
        if rest:
            steps.append({"note": 0.0, "midi": 0, "accent": False, "slide": False})
            continue
        idx = int(rng() * len(PHRYGIAN_HZ))
        hz = PHRYGIAN_HZ[idx]
        midi = PHRYGIAN_MIDI[idx]
        accent = rng() < 0.32 or i % 4 == 0
        slide = prev > 0 and rng() < 0.18
        steps.append({"note": hz, "midi": midi, "accent": accent, "slide": slide})
        prev = hz
    return steps


def write_wav_mono(path: Path, mono: list[float], peak_target=0.90):
    if not mono:
        mono = [0.0]
    peak = max(1e-9, max(abs(x) for x in mono))
    scale = peak_target / peak
    frames = array.array(
        "h", [max(-32767, min(32767, int(x * scale * 32767))) for x in mono]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(frames.tobytes())
    print("wrote", path.name, "n=", len(mono), "peak_in", round(peak, 4))


def read_wav(path: Path) -> list[float]:
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
    # trim silence
    thr = 0.008
    a = 0
    while a < len(samples) and abs(samples[a]) < thr:
        a += 1
    b = len(samples) - 1
    while b > a and abs(samples[b]) < thr:
        b -= 1
    return samples[a : b + 1] if b > a else samples


def electribe_master(src: Path, dst: Path):
    """ESX-1 convert chain: highpass=f=30, alimiter=limit=0.94, mono 44100 s16."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG,
        "-y",
        "-i",
        str(src),
        "-af",
        "highpass=f=30,alimiter=limit=0.94,aresample=44100:resampler=soxr",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-sample_fmt",
        "s16",
        "-c:a",
        "pcm_s16le",
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print("ESX-mastered", dst.name)


def place(buf, sample, beat, gain=1.0):
    start = int(beat * 60.0 / BPM * SR)
    for i, v in enumerate(sample):
        j = start + i
        if 0 <= j < len(buf):
            buf[j] += v * gain


def render_acid_stem(pattern, grit_drive=2.8) -> list[float]:
    """Continuous screech acid (square + SVF) — sidechain OFF (kick-dominated mix later)."""
    step = (60.0 / BPM) / 4.0
    total_steps = BARS * 16
    out = [0.0] * N
    # simple 1-pole-ish SVF state
    l = b = 0.0
    phase = 0.0
    cur_hz = PHRYGIAN_HZ[0]
    target_hz = cur_hz
    env = 0.0
    res_q = 0.05  # screech
    base_cut = 240.0
    env_amt = 3800.0
    step_idx = -1
    for i in range(N):
        t = i / SR
        s = min(total_steps - 1, int(t / step))
        if s != step_idx:
            step_idx = s
            bar = s // 16
            st = s % 16
            # gap near end of bar 7 like kickback 8-bar form
            gap = bar == 7 and st >= 12
            p = pattern[st]
            if not gap and p["note"] > 0:
                target_hz = p["note"]
                if not p["slide"]:
                    cur_hz = target_hz
                env = 1.0 if p["accent"] else 0.55
            elif not p["slide"]:
                env *= 0.35
        cur_hz += (target_hz - cur_hz) * 0.0028
        env *= 0.9992
        phase += cur_hz / SR
        phase -= math.floor(phase)
        osc = (1.0 if phase < 0.5 else -1.0) * env * 0.45  # square = screech
        cut = base_cut + env * env_amt
        f = 2 * math.sin(math.pi * clamp(cut / SR, 0.0001, 0.45))
        l += f * b
        h = osc - l - res_q * b
        b += f * h
        y = tanh_drive(l, grit_drive)
        out[i] = y
    return out


def make_acid_midi(pattern, bars=4, harder=False):
    notes = []
    gate = 0.1875
    slide_dur = 0.45
    vel_boost = 12 if harder else 0
    for bar in range(bars):
        base = bar * 4.0
        for st, p in enumerate(pattern):
            if p["midi"] <= 0:
                continue
            dur = slide_dur if p["slide"] else gate
            vel = (118 if p["accent"] else 95) + vel_boost
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


# --- Ableton TCP ---

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


def silence_tracks(by, names):
    for name in names:
        t = by.get(name)
        if not t:
            print("missing track", name)
            continue
        idx = t["index"]
        for row in range(8):
            send("stop_clip", {"track_index": idx, "clip_index": row})
            send("delete_clip", {"track_index": idx, "clip_index": row})
        print("silenced/muted", name, idx)


def main():
    errors = []
    rng = mulberry32(SEED)
    print("=== CRISP DNA one-shots + Kickback Mental bed @", BPM, "===")

    # 1) Kickback DNA one-shots
    kick_dna = synth_kick_sledge(rng, "full")
    hat_c = synth_hat(rng, False)
    hat_o = synth_hat(rng, True)
    clap = synth_clap(rng)
    write_wav_mono(OUT / "kb_kick_sledge.wav", kick_dna)
    write_wav_mono(OUT / "kb_hat_closed.wav", hat_c)
    write_wav_mono(OUT / "kb_hat_open.wav", hat_o)
    write_wav_mono(OUT / "kb_clap.wav", clap)

    # Pass DNA through Electribe master chain as well (same delivery format)
    for name in ("kb_kick_sledge.wav", "kb_hat_closed.wav", "kb_hat_open.wav", "kb_clap.wav"):
        src = OUT / name
        dst = OUT / name.replace(".wav", "_esx.wav")
        try:
            electribe_master(src, dst)
        except Exception as e:
            errors.append(f"master {name}: {e}")
            print("FAIL master", name, e)

    # 2) Master ESX factory one-shots through convert chain
    esx_map = {
        "146_SinKick.wav": "esx_SinKick_mastered.wav",
        "054_HH-1C.wav": "esx_HH1C_mastered.wav",
        "055_HH-1O.wav": "esx_HH1O_mastered.wav",
        "092_JunkPerc.wav": "esx_JunkPerc_mastered.wav",
    }
    for src_name, dst_name in esx_map.items():
        src = FACTORY / src_name
        if not src.exists():
            errors.append(f"missing factory {src_name}")
            print("MISSING", src)
            continue
        try:
            electribe_master(src, OUT / dst_name)
        except Exception as e:
            errors.append(f"esx master {src_name}: {e}")
            print("FAIL", src_name, e)

    # Prefer Kickback DNA kick (sledge) as main; layer tiny mastered SinKick click if present
    kick_main = read_wav(OUT / "kb_kick_sledge_esx.wav") if (OUT / "kb_kick_sledge_esx.wav").exists() else kick_dna
    # apply extra grit feel
    kick_main = [tanh_drive(x, 1.35) for x in kick_main]
    esx_kick = None
    if (OUT / "esx_SinKick_mastered.wav").exists():
        esx_kick = read_wav(OUT / "esx_SinKick_mastered.wav")
        esx_kick = [tanh_drive(x, 1.7) for x in esx_kick]  # Kickback drive feel on ESX
    hat_use = read_wav(OUT / "kb_hat_closed_esx.wav") if (OUT / "kb_hat_closed_esx.wav").exists() else hat_c
    if (OUT / "esx_HH1C_mastered.wav").exists():
        # blend DNA hat with mastered ESX HH (DNA envelope feel)
        esx_hh = read_wav(OUT / "esx_HH1C_mastered.wav")
        # prefer shorter of the two for one-shot feel in loops
        hat_use = [tanh_drive(x, 1.2) for x in esx_hh]
    junk = None
    if (OUT / "esx_JunkPerc_mastered.wav").exists():
        junk = [tanh_drive(x, 1.4) for x in read_wav(OUT / "esx_JunkPerc_mastered.wav")]
    clap_use = read_wav(OUT / "kb_clap_esx.wav") if (OUT / "kb_clap_esx.wav").exists() else clap

    pattern = acid_pattern(SEED)

    # 3) Render 8-bar Kickback DNA loops (NOT raw unprocessed ESX bar dumps)
    trk_k = [0.0] * N
    trk_h = [0.0] * N
    trk_p = [0.0] * N
    trk_k_soft = [0.0] * N
    trk_h_soft = [0.0] * N

    for bar in range(BARS):
        base = bar * 4.0
        intro = bar < 2
        # four-on-floor sledge
        for step in (0, 4, 8, 12):
            beat = base + step * 0.25
            g = 0.78 if intro else 1.0
            place(trk_k, kick_main, beat, g)
            place(trk_k_soft, kick_main, beat, 0.55 if intro else 0.72)
            if esx_kick is not None:
                place(trk_k, esx_kick, beat, 0.18 * g)  # thin click layer only
        # shuffle hats: 16ths with swing on odd
        for st in range(16):
            swing = 0.018 if (st % 2 == 1) else 0.0
            beat = base + st * 0.25 + swing
            g = (0.45 if intro else 0.78) * (0.55 if st % 2 else 0.95)
            place(trk_h, hat_use, beat, g)
            if st % 2 == 0:
                place(trk_h_soft, hat_use, beat, g * 0.7)
        # clap on 4 & 12 (shuffle/offbeat)
        place(trk_p, clap_use, base + 1.0, 0.55 if intro else 0.72)
        place(trk_p, clap_use, base + 3.0, 0.55 if intro else 0.72)
        if junk is not None:
            place(trk_p, junk, base + 0.75, 0.40)
            place(trk_p, junk, base + 2.75, 0.35)

    acid = render_acid_stem(pattern, grit_drive=2.8)

    # Peak variants (harder)
    trk_k_hard = [x * 1.12 for x in trk_k]
    trk_h_hard = [x * 1.08 for x in trk_h]
    trk_p_hard = [x * 1.15 for x in trk_p]
    acid_hard = [tanh_drive(x, 1.25) for x in acid]

    write_wav_mono(OUT / "loop_kick_162.wav", trk_k)
    write_wav_mono(OUT / "loop_hats_162.wav", trk_h)
    write_wav_mono(OUT / "loop_perc_162.wav", trk_p)
    write_wav_mono(OUT / "loop_acid_162.wav", acid)
    write_wav_mono(OUT / "loop_kick_soft_162.wav", trk_k_soft)
    write_wav_mono(OUT / "loop_hats_soft_162.wav", trk_h_soft)
    write_wav_mono(OUT / "loop_kick_hard_162.wav", trk_k_hard)
    write_wav_mono(OUT / "loop_hats_hard_162.wav", trk_h_hard)
    write_wav_mono(OUT / "loop_perc_hard_162.wav", trk_p_hard)
    write_wav_mono(OUT / "loop_acid_hard_162.wav", acid_hard)

    # Kick-dominated dark mix ~85% low (kick+sub feel), club-ish headroom
    mix = [0.0] * N
    for i in range(N):
        # ~85% low energy from kick, rest acid+perc (sidechain OFF)
        mono = trk_k[i] * 1.05 + acid[i] * 0.28 + trk_h[i] * 0.22 + trk_p[i] * 0.18
        mix[i] = tanh_drive(mono, 1.08)
    write_wav_mono(OUT / "bed_mental_162.wav", mix, peak_target=0.89)

    # stereo bed + club loudness toward -9 LUFS then MP3
    st_path = OUT / "bed_mental_162_st.wav"
    peak = max(1e-9, max(abs(x) for x in mix))
    scale = 0.89 / peak
    st = array.array("h")
    for x in mix:
        v = max(-32767, min(32767, int(x * scale * 32767)))
        st.append(v)
        st.append(v)
    with wave.open(str(st_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())

    loud_path = OUT / "bed_mental_162_club.wav"
    try:
        # loudnorm toward club -9 LUFS, then convert-style limiter headroom
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(st_path),
                "-af",
                "loudnorm=I=-9:TP=-1.0:LRA=7,highpass=f=30,alimiter=limit=0.94",
                "-ar",
                "44100",
                str(loud_path),
            ],
            check=True,
            capture_output=True,
        )
        bounce_src = loud_path
        print("club loudness OK", loud_path.name)
    except Exception as e:
        bounce_src = st_path
        errors.append(f"loudnorm: {e}")
        print("FAIL loudnorm", e)

    try:
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(bounce_src),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(MP3),
            ],
            check=True,
            capture_output=True,
        )
        print("MP3", MP3)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)

    # --- Ableton session ---
    print("=== Ableton load CRISP DNA ===")
    snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=60)
    snap = ok(snap_r, "snapshot")
    if not snap:
        print("ABORT no Ableton snapshot — samples/MP3 still written")
        print("ERRORS", errors)
        print("MP3_PATH", str(MP3))
        return

    ok(send("set_tempo", {"tempo": BPM}), "tempo 162")
    ok(send("stop_playback"), "stop")

    # stop all clips
    for t in snap["tracks"]:
        for sl in t.get("clip_slots") or []:
            if sl.get("has_clip"):
                send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})

    by_full = {t["name"]: t for t in snap["tracks"]}
    by = {t["name"]: t["index"] for t in snap["tracks"]}
    print("tracks", by)

    # Mute / silence noisy beds
    silence_tracks(by_full, ("E-Mental", "E-Atm", "E-Syn"))

    acid_idx = by.get("Acid 303 Poly")
    kick_idx = by.get("E-Kick")
    hats_idx = by.get("E-Hats")
    perc_idx = by.get("E-Perc")
    oh_idx = by.get("E-OHat") or by.get("E-Snare")
    bass_idx = by.get("Tholin Bass") or by.get("E-Bass") or by.get("6-MIDI")

    if acid_idx is not None:
        r = send("load_browser_item", {"track_index": acid_idx, "item_uri": "query:Synths#Drift"})
        print("Drift", r.get("status"), r.get("message", r.get("result")))

    # Clear scene rows 0-3 on key tracks
    for row, _ in SCENES:
        for idx in (acid_idx, kick_idx, hats_idx, perc_idx, oh_idx, bass_idx):
            if idx is not None:
                safe_delete(idx, row)

    midi_notes = make_acid_midi(pattern, bars=4, harder=False)
    midi_hard = make_acid_midi(pattern, bars=4, harder=True)

    # Intro — soft kick only (dark entry)
    if kick_idx is not None:
        load_audio(kick_idx, 0, OUT / "loop_kick_soft_162.wav", "Intro_kick")
    if hats_idx is not None:
        load_audio(hats_idx, 0, OUT / "loop_hats_soft_162.wav", "Intro_hats")
    if acid_idx is not None:
        safe_delete(acid_idx, 0)

    # Drop — full Kickback DNA bed + MIDI acid
    if kick_idx is not None:
        load_audio(kick_idx, DROP_ROW, OUT / "loop_kick_162.wav", "Drop_kick")
    if hats_idx is not None:
        load_audio(hats_idx, DROP_ROW, OUT / "loop_hats_162.wav", "Drop_hats")
    if perc_idx is not None:
        load_audio(perc_idx, DROP_ROW, OUT / "loop_perc_162.wav", "Drop_perc")
    if acid_idx is not None:
        put_midi(acid_idx, DROP_ROW, 16.0, "Drop_acid", midi_notes)
    if bass_idx is not None:
        # octave-down shadow of acid (kick-dominated still)
        bass_notes = []
        for n in midi_notes:
            bn = dict(n)
            bn["pitch"] = max(0, n["pitch"] - 12)
            bn["velocity"] = max(1, int(n["velocity"] * 0.8))
            bass_notes.append(bn)
        put_midi(bass_idx, DROP_ROW, 16.0, "Drop_bass", bass_notes)

    # Break — hats/perc sparse + acid (no kick)
    if hats_idx is not None:
        load_audio(hats_idx, 2, OUT / "loop_hats_soft_162.wav", "Break_hats")
    if perc_idx is not None:
        load_audio(perc_idx, 2, OUT / "loop_perc_162.wav", "Break_perc")
    if acid_idx is not None:
        put_midi(acid_idx, 2, 16.0, "Break_acid", midi_notes)

    # Peak — harder DNA
    if kick_idx is not None:
        load_audio(kick_idx, 3, OUT / "loop_kick_hard_162.wav", "Peak_kick")
    if hats_idx is not None:
        load_audio(hats_idx, 3, OUT / "loop_hats_hard_162.wav", "Peak_hats")
    if perc_idx is not None:
        load_audio(perc_idx, 3, OUT / "loop_perc_hard_162.wav", "Peak_perc")
    if acid_idx is not None:
        put_midi(acid_idx, 3, 16.0, "Peak_acid", midi_hard)
    if bass_idx is not None:
        bass_hard = []
        for n in midi_hard:
            bn = dict(n)
            bn["pitch"] = max(0, n["pitch"] - 12)
            bn["velocity"] = max(1, int(n["velocity"] * 0.85))
            bass_hard.append(bn)
        put_midi(bass_idx, 3, 16.0, "Peak_bass", bass_hard)

    # Locators for scene names
    for i, (row, name) in enumerate(SCENES):
        send("create_locator", {"name": f"{i+1}_{name}", "time": float(i * 32.0)})

    # Fire Drop
    fired = []
    for label, idx in [
        ("Acid 303 Poly", acid_idx),
        ("Tholin Bass", bass_idx),
        ("E-Kick", kick_idx),
        ("E-Hats", hats_idx),
        ("E-Perc", perc_idx),
    ]:
        if idx is None:
            continue
        r = send("fire_clip", {"track_index": idx, "clip_index": DROP_ROW})
        if r.get("status") == "success":
            fired.append(label)
            print("FIRE", label)
        else:
            errors.append(f"fire {label}: {r.get('message')}")
            print("FAIL fire", label, r)

    ok(send("start_playback"), "start_playback")

    info = send("get_session_info")
    res = info.get("result") or info
    print("tempo", res.get("tempo"), "is_playing", res.get("is_playing"))
    print("FIRED Drop:", fired)
    print("SCENES", [n for _, n in SCENES])
    print("SAMPLES_DIR", str(OUT))
    print("CONVERT_CHAIN", "highpass=f=30,alimiter=limit=0.94,mono 44100 s16")
    print("KICKBACK_DNA", "mental@162 sledge/screech/shuffle/full grit")
    print("MP3_PATH", str(MP3))
    print("ERRORS", errors)
    print("DONE crisp_dna_to_ableton")


if __name__ == "__main__":
    main()
