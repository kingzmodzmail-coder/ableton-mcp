# -*- coding: utf-8 -*-
"""ESX-1 PneumatixKick + Pozek-style vocal chops @162 + PA master.

Builds on lossless SwingFX stems + Pneumatix kick gains.
Adds methodical chopped vocal / vocal-like stab lane (Pozek Flangerboy character:
mid presence, narcosis-like, NOT bright pop, under the kick).

Sources for chops (no copyrighted vocal as main hook):
- ESXSD Factory Voice-*.wav one-shots (Electribe library) via CRISP convert
- Synthesized formant vowel stabs (ahh/ohh/ee) for mid-body glue

Output: C:\\Users\\Gebruiker\\Downloads\\EvAIx_ESX1_PneumatixKick_PozekVox_PA_162.mp3
"""
from __future__ import annotations

import array
import json
import math
import random
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

FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
STEM_SRC = BRIDGE / "samples" / "crisp-dna" / "esx1-valveforce-swingfx"
OUT = STEM_SRC / "pneumatix_pozekvox"
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"
ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_ESX1_PneumatixKick_PozekVox_PA_162.mp3")
NOTES = OUT / "pozekvox_notes.md"

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
DELAY_WET = 0.11
DELAY_FB = 0.26
SWING_PCT = 0.59
SWING_DELAY = (SWING_PCT - 0.5) / ((2.0 / 3.0) - 0.5) * (0.25 / 3.0)

# Locked Pneumatix kick / rhythm gains
KICK_G = 1.50
KICK_BREAK_G = 0.70
HATS_G = 0.36
OH_G = 0.30
PERC_SCALE = 0.78
ACID_SCALE = 0.92
STRETCH_SCALE = 0.88
VOX_G = 0.38  # under kick; mid presence only
VOX_BREAK_G = 0.55  # slightly more audible in break (still under kick bus)

AF_CHAIN = (
    "highpass=f=26:poles=2,"
    "lowshelf=f=90:t=q:w=0.7:g=1.8,"
    "equalizer=f=52:t=q:w=1.1:g=2.9,"
    "equalizer=f=72:t=q:w=1.4:g=-1.2,"
    "equalizer=f=380:t=q:w=1.0:g=-1.0,"
    "equalizer=f=1400:t=q:w=1.0:g=0.8,"  # slight Pozek mid pocket for chops
    "equalizer=f=3200:t=q:w=1.6:g=1.9,"
    "equalizer=f=6500:t=q:w=1.2:g=-0.6,"
    "equalizer=f=10000:t=q:w=1.1:g=-2.4,"
    "highshelf=f=7000:t=q:w=0.7:g=-3.4,"
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
    "perc_scale": PERC_SCALE,
    "acid_scale": ACID_SCALE,
    "stretch_scale": STRETCH_SCALE,
    "vox": VOX_G,
    "vox_break": VOX_BREAK_G,
    "tube_gain": TUBE_GAIN,
    "delay_wet": DELAY_WET,
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


def write_mono(path: Path, samples, peak_target=0.88):
    peak = max(1e-9, max(abs(x) for x in samples) if samples else 1e-9)
    scale = peak_target / peak
    data = array.array("h")
    for x in samples:
        data.append(max(-32767, min(32767, int(x * scale * 32767))))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def place(buf, sample, beat, gain=1.0):
    dna.place(buf, sample, beat, gain)


def swing_offset(st: int) -> float:
    return SWING_DELAY if (st % 2 == 1) else 0.0


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


def pingpong_stereo(samples, time_beats=DELAY_TIME_BEATS, feedback=DELAY_FB, wet=DELAY_WET):
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


def write_stereo_lr(path: Path, left, right, peak_target=0.90):
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


def one_pole(samples, cutoff_hz, mode="lpf"):
    out = [0.0] * len(samples)
    l = b = 0.0
    q = 0.12
    for i, x in enumerate(samples):
        f = 2 * math.sin(math.pi * dna.clamp(cutoff_hz / SR, 0.0001, 0.45))
        l += f * b
        h = x - l - q * b
        b += f * h
        out[i] = h if mode == "hpf" else l
    return out


def bandpass_mid(samples, lo=280.0, hi=3200.0):
    """Pozek mid pocket: cut sub and air so chops don't fight kick/tops."""
    hp = one_pole(samples, lo, mode="hpf")
    return one_pole(hp, hi, mode="lpf")


def soft_gate(samples, thr=0.02):
    out = [0.0] * len(samples)
    env = 0.0
    for i, x in enumerate(samples):
        a = abs(x)
        env = a if a > env else env * 0.9992
        g = 1.0 if env > thr else env / max(thr, 1e-6)
        out[i] = x * min(1.0, g)
    return out


def synth_formant_stab(rng, vowel="ah", dur=0.18, f0=110.0):
    """Original formant vowel stab — mid body, narcosis-ish."""
    # approximate formants Hz / gain
    forms = {
        "ah": [(700, 1.0), (1200, 0.55), (2600, 0.22)],
        "oh": [(450, 1.0), (800, 0.5), (2300, 0.18)],
        "ee": [(300, 0.7), (2200, 0.85), (3000, 0.25)],
        "uh": [(500, 1.0), (1000, 0.45), (2400, 0.15)],
    }[vowel]
    n = int(dur * SR)
    out = [0.0] * n
    # slight pitch drift
    for i in range(n):
        t = i / SR
        env = math.sin(math.pi * min(1.0, t / dur)) ** 1.2
        # pitch envelope down a touch
        ff0 = f0 * (1.0 - 0.08 * (t / max(dur, 1e-6)))
        # buzz source
        phase = 2 * math.pi * ff0 * t
        buzz = 0.55 * math.sin(phase) + 0.25 * math.sin(2 * phase) + 0.12 * math.sin(3 * phase)
        buzz += 0.04 * (rng() * 2 - 1)
        y = 0.0
        for fc, g in forms:
            # cheap resonator: sin at formant amp-mod by buzz envelope
            y += g * buzz * math.sin(2 * math.pi * fc * t) * math.exp(-t * (4.0 + fc / 2000.0))
        # mild tube
        y = math.tanh(y * 1.6) * env
        out[i] = y * 0.55
    out = bandpass_mid(out, 320, 3400)
    return out


def electribe_master(src: Path, dst: Path):
    dna.electribe_master(src, dst)


def ensure_vox_shots_fixed():
    voice_names = [
        "107_Voice-1.wav", "110_Voice-4.wav", "113_Voice-7.wav",
        "116_Voice-10.wav", "119_Voice-13.wav", "122_Voice-16.wav",
        "125_Voice-19.wav", "210_Voice-24.wav", "212_Voice-26.wav",
    ]
    shots = []
    used = []
    for src_name in voice_names:
        src = FACTORY / src_name
        if not src.exists():
            print("MISSING voice", src_name)
            continue
        dst = ONESHOT / f"esx_{src_name}"
        electribe_master(src, dst)
        raw = read_wav(dst)
        peak_i = max(range(len(raw)), key=lambda i: abs(raw[i])) if raw else 0
        start = max(0, peak_i - int(0.01 * SR))
        end = min(len(raw), start + int(0.20 * SR))
        chop = bandpass_mid(raw[start:end], 300, 3000)
        chop = soft_gate(chop, 0.015)
        chop = [math.tanh(x * 1.35) for x in chop]
        write_mono(ONESHOT / f"chop_{Path(src_name).stem}.wav", chop, 0.82)
        shots.append(chop)
        used.append(src_name)

    rng = dna.mulberry32(0x502E)
    formants = []
    for vowel, f0 in [("ah", 98.0), ("oh", 110.0), ("uh", 92.0), ("ee", 130.0), ("ah", 82.0)]:
        formants.append(synth_formant_stab(rng, vowel=vowel, dur=0.16 + 0.04 * rng(), f0=f0))
    for i, f in enumerate(formants):
        write_mono(ONESHOT / f"formant_{i}.wav", f, 0.8)
        shots.append(f)
        used.append(f"synth_formant_{i}")
    print("VOX_SHOTS", used)
    return shots, used


def scene_gains(sid: int):
    acid_base = {0: 0.0, 1: 0.0, 2: 0.42, 3: 0.44, 4: 0.46, 5: 0.5, 6: 0.45, 7: 0.22}.get(sid, 0.4)
    perc_base = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.8, 4: 0.88, 5: 0.7, 6: 0.95, 7: 0.4}.get(sid, 0.8)
    st_base = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.85, 4: 0.9, 5: 1.0, 6: 0.8, 7: 0.55}.get(sid, 0.8)
    kick_g = KICK_BREAK_G if sid == 5 else KICK_G
    vox_g = {
        0: 0.0,
        1: 0.0,
        2: VOX_G * 0.45,
        3: VOX_G * 0.75,
        4: VOX_G,
        5: VOX_BREAK_G,
        6: VOX_G * 1.05,
        7: VOX_G * 0.35,
    }.get(sid, VOX_G)
    return {
        "kick": kick_g,
        "hats": HATS_G,
        "oh": OH_G,
        "perc": perc_base * PERC_SCALE,
        "stretch": st_base * STRETCH_SCALE,
        "acid": acid_base * ACID_SCALE,
        "vox": vox_g,
    }


def render_vox_track(sid: int, shots: list) -> list[float]:
    """Methodical Pozek-style chops — sparse, swung offbeats, not a sung topline."""
    trk = [0.0] * N
    if not shots or sid in (0, 1):
        return trk
    rng = dna.mulberry32(0x70C5 + sid * 97)

    for bar in range(BARS):
        base = bar * 4.0
        # densify by section
        if sid == 2:
            hits = [4, 12]  # on 2 and 4, sparse
            g0 = 0.55
        elif sid == 3:
            hits = [4, 7, 12]  # add swung ghost
            g0 = 0.62
        elif sid == 4:
            hits = [4, 7, 12, 15]
            g0 = 0.7
        elif sid == 5:
            # break: call-response chops, more space
            hits = [0, 6, 10, 14] if (bar % 2 == 0) else [2, 8, 12]
            g0 = 0.85
        elif sid == 6:
            hits = [4, 6, 7, 12, 14, 15]
            g0 = 0.72
        elif sid == 7:
            if bar >= 8:
                continue
            hits = [4, 12]
            g0 = 0.45
        else:
            hits = []

        for st in hits:
            shot = shots[int(rng() * len(shots)) % len(shots)]
            # odd 16ths get swing; even stay grid (kick-safe)
            off = swing_offset(st)
            # alternate formant vs voice feel via gain jitter
            g = g0 * (0.75 + 0.35 * rng())
            # slightly quieter on denser 16ths so kick owns
            if st % 4 == 0:
                g *= 0.85
            place(trk, shot, base + st * 0.25 + off, g)

        # every 4 bars: longer held vowel stab (methodical)
        if sid >= 4 and bar % 4 == 0:
            shot = shots[int(rng() * len(shots)) % len(shots)]
            place(trk, shot, base + 0.0, 0.35 if sid != 5 else 0.5)

    # short delay color on vox only (mono), wet low
    d = max(1, int(0.375 * 60.0 / BPM * SR))
    wet = 0.14
    fb = 0.22
    out = [0.0] * N
    delay_line = [0.0] * N
    for i, x in enumerate(trk):
        delayed = delay_line[i - d] if i >= d else 0.0
        out[i] = x + delayed * wet
        delay_line[i] = x + delayed * fb
    out = bandpass_mid(out, 280, 3100)
    return out


def fit(buf):
    if len(buf) > N:
        return buf[:N]
    if len(buf) < N:
        return buf + [0.0] * (N - len(buf))
    return buf


def remix_scene(sid: int, name: str, vox_shots: list) -> dict:
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

    trk_k = fit(read_wav(paths_in["kick"]))
    trk_h = fit(read_wav(paths_in["hats"]))
    trk_oh = fit(read_wav(paths_in["oh"]))
    trk_p = fit(read_wav(paths_in["perc"]))
    trk_st = fit(read_wav(paths_in["stretch"]))
    acid = fit(read_wav(paths_in["acid"]))
    trk_v = render_vox_track(sid, vox_shots)

    out_paths = {}
    for key, src in paths_in.items():
        dst = OUT / src.name
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            dst.write_bytes(src.read_bytes())
        out_paths[key] = dst

    vox_path = OUT / f"{prefix}_vox.wav"
    write_mono(vox_path, trk_v, 0.78)
    out_paths["vox"] = vox_path

    g = scene_gains(sid)
    dry = [0.0] * N
    for i in range(N):
        dry[i] = (
            trk_k[i] * g["kick"]
            + acid[i] * g["acid"]
            + trk_h[i] * g["hats"]
            + trk_oh[i] * g["oh"]
            + trk_p[i] * g["perc"]
            + trk_st[i] * g["stretch"]
            + trk_v[i] * g["vox"]
        )

    send_src = [0.0] * N
    for i in range(N):
        send_src[i] = (
            acid[i] * g["acid"] * 0.55
            + trk_h[i] * g["hats"] * 0.7
            + trk_oh[i] * g["oh"] * 0.45
            + trk_v[i] * g["vox"] * 0.5
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

    mix_path = SECTION_MIX_DIR / f"{prefix}_pnxvox_mix.wav"
    write_stereo_lr(mix_path, left, right, peak_target=0.90)
    out_paths["mix"] = mix_path
    print(
        "scene", sid, name,
        "gains", {k: round(v, 3) for k, v in g.items()},
        "vox_peak", round(max((abs(x) for x in trk_v), default=0), 4),
        "peak", round(peak, 4),
    )
    return out_paths


def bounce_mp3(scene_paths):
    listfile = OUT / "_pnxvox_concat.txt"
    raw_concat = OUT / "_pnxvox_concat.wav"
    mastered = OUT / "_pnxvox_master.wav"
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
        print("master fail", r.stderr[-2000:])
        raise RuntimeError("PA master failed")
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
        print("ffprobe", e)
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


def write_notes(dur, errors, used_vox):
    NOTES.write_text(
        f"""# EvAIx ESX-1 PneumatixKick + PozekVox PA @162

**Output:** `{MP3}`
**Duration:** {dur:.2f}s
**BPM:** {BPM}

## Stem gains (Pneumatix kick locked)

| Bus | Gain |
|-----|------|
| Kick | **{KICK_G}** (break **{KICK_BREAK_G}**) |
| Closed hats | **{HATS_G}** |
| Open hats | **{OH_G}** |
| Perc scale | {PERC_SCALE} |
| Acid / Stretch | {ACID_SCALE} / {STRETCH_SCALE} |
| **Vox chops** | **{VOX_G}** (break **{VOX_BREAK_G}**) |

## Vox lane
- Methodical chopped stabs (not sung topline)
- ESX Voice ROM oneshots (chop layer only) + synthesized formant vowels
- Mid BP ~300–3000 Hz; under kick; swing on odd 16ths
- Used: {used_vox}
- No Pozek/Flangerboy audio sampled as hook

## ffmpeg -af
```
{AF_CHAIN}
```

Errors: {errors or "none"}
""",
        encoding="utf-8",
    )


def main():
    errors = []
    print("=== PneumatixKick + PozekVox PA @", BPM, "===")
    print("GAINS", GAINS_USED)
    vox_shots, used_vox = ensure_vox_shots_fixed()
    if not vox_shots:
        raise RuntimeError("no vox shots available")

    scene_paths = {}
    for sid, name in SCENES:
        scene_paths[sid] = remix_scene(sid, name, vox_shots)

    print("=== Bounce MP3 ===")
    try:
        mp3_dur = bounce_mp3(scene_paths)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        mp3_dur = 0.0

    write_notes(mp3_dur, errors, used_vox)

    print("=== Ableton load ===")
    try:
        snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=60)
        snap = ok(snap_r, "snapshot")
    except Exception as e:
        errors.append(f"ableton: {e}")
        snap = None
        print("Ableton unreachable", e)

    if snap:
        ok(send("set_tempo", {"tempo": BPM}), "tempo 162")
        ok(send("stop_playback"), "stop")
        for t in snap["tracks"]:
            for sl in t.get("clip_slots") or []:
                if sl.get("has_clip"):
                    send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})
        by = {t["name"]: t["index"] for t in snap["tracks"]}
        by_full = {t["name"]: t for t in snap["tracks"]}
        silence_beds(by_full)

        acid_audio_idx = by.get("Acid 303") or by.get("E-Syn")
        kick_idx = by.get("E-Kick")
        hats_idx = by.get("E-Hats")
        perc_idx = by.get("E-Perc")
        oh_idx = by.get("E-OHat") or by.get("E-Snare")
        stretch_idx = by.get("ESX Stretch") or by.get("E-Bass") or by.get("ESX Jam")
        jam_idx = by.get("ESX Jam") or by.get("E2S Jam")
        # Prefer a free track for vox: E-Snare if not used as OH, else jam, else perc double
        vox_idx = None
        for cand in ("E-Vox", "ESX Vox", "E-Snare", "E-Clap", "E-Tom"):
            if cand in by and by[cand] not in (kick_idx, hats_idx, perc_idx, oh_idx, stretch_idx, acid_audio_idx):
                vox_idx = by[cand]
                send("set_track_name", {"track_index": vox_idx, "name": "ESX Vox"})
                break
        if vox_idx is None and jam_idx is not None and jam_idx != stretch_idx:
            # use jam for mixes; vox rides on perc alternate — create name on unused
            pass
        # If E-Snare is oh_idx, try another
        if vox_idx is None:
            for t in snap["tracks"]:
                idx = t["index"]
                if idx in (kick_idx, hats_idx, perc_idx, oh_idx, stretch_idx, acid_audio_idx, jam_idx):
                    continue
                if t.get("type") == "midi":
                    continue
                vox_idx = idx
                send("set_track_name", {"track_index": vox_idx, "name": "ESX Vox"})
                print("mapped vox to", t["name"], "->", idx)
                break

        for row, _ in SCENES:
            for idx in (acid_audio_idx, kick_idx, hats_idx, perc_idx, oh_idx, stretch_idx, vox_idx):
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
            if vox_idx is not None and morph.layer_has_signal(paths["vox"]):
                load_audio(vox_idx, sid, paths["vox"], f"{name}_vox")
            if jam_idx is not None and jam_idx not in (stretch_idx, vox_idx):
                load_audio(jam_idx, sid, paths["mix"], f"{name}_PNXVox_mix")
            send("create_locator", {"name": f"{sid}_{name}", "time": float(sid * clip_len)})

        fired = []
        for label, idx, key in [
            ("kick", kick_idx, "kick"),
            ("hats", hats_idx, "hats"),
            ("oh", oh_idx, "oh"),
            ("perc", perc_idx, "perc"),
            ("stretch", stretch_idx, "stretch"),
            ("acid_audio", acid_audio_idx, "acid"),
            ("vox", vox_idx, "vox"),
        ]:
            if idx is None:
                continue
            p = scene_paths[FIRE_ROW].get(key)
            if p is None or not morph.layer_has_signal(p):
                continue
            r = send("fire_clip", {"track_index": idx, "clip_index": FIRE_ROW})
            if r.get("status") == "success":
                fired.append(label)
                print("FIRE", label)
        ok(send("start_playback"), "start_playback")
        info = send("get_session_info")
        res = info.get("result") or info
        print("IS_PLAYING", res.get("is_playing"), "TEMPO", res.get("tempo"), "FIRED", fired)

    print("STEM_GAINS", GAINS_USED)
    print("AF_CHAIN", AF_CHAIN)
    print("VOX_USED", used_vox)
    print("MP3_PATH", str(MP3))
    print("MP3_DURATION_SEC", round(mp3_dur, 2))
    print("ERRORS", errors)
    print("DONE build_esx1_pneumatix_pozekvox_162")


if __name__ == "__main__":
    main()
