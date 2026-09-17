# -*- coding: utf-8 -*-
"""ESX-1 Pneumatix Molecular + Pozek Real DNA @162 + PA master.

Rebuild (not stem EQ remix): regenerates patterns/sounds for producer DNA.
- KICK/RHYTHM = Pneumatix Molecular Modulation: clean tribal/mental 4/4,
  kick owns pocket, sparse controlled hats, dark rolling — less industrial junk.
- VOCALS = Pozek Flangerboy/narcosis: methodical chopped Voice phrases with
  flanger/chorus + mid BP ~800–2.5k. NO synth formant beeps. No ripping Pozek audio.
- BPM 162 (Pneumatix-tight). PA master for 18\" after arrangement is right.
- Bounce path preferred; AbletonMCP load is best-effort (skip hangs).

Outputs:
  C:\\Users\\Gebruiker\\Downloads\\EvAIx_ESX1_PnxPozek_Real_PA_162.mp3
  C:\\Users\\Gebruiker\\Downloads\\EvAIx_ESX1_PnxPozek_Real_NoVox_PA_162.mp3
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
import build_classic_acid_liveset as classic  # noqa: E402

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
OUT = BRIDGE / "samples" / "crisp-dna" / "esx1-pnx-pozek-real"
OUT.mkdir(parents=True, exist_ok=True)
ONESHOT = OUT / "oneshots"
ONESHOT.mkdir(parents=True, exist_ok=True)
SECTION_MIX_DIR = OUT / "sections"
SECTION_MIX_DIR.mkdir(parents=True, exist_ok=True)
MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_ESX1_PnxPozek_Real_PA_162.mp3")
MP3_NOVOX = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_ESX1_PnxPozek_Real_NoVox_PA_162.mp3")
NOTES = OUT / "pnx_pozek_real_notes.md"

SCENES = [
    (0, "Intro_Kick"),
    (1, "Hats_In"),
    (2, "Groove_Build"),
    (3, "Vox_Enter"),
    (4, "Full_Pocket"),
    (5, "Break_Space"),
    (6, "Peak_Roll"),
    (7, "Outro_Fade"),
]

TUBE_GAIN = 2.05
DELAY_TIME_BEATS = 0.375
DELAY_WET = 0.09
DELAY_FB = 0.22
SWING_PCT = 0.56  # lighter tribal swing than Valve Force 59%
SWING_DELAY = (SWING_PCT - 0.5) / ((2.0 / 3.0) - 0.5) * (0.25 / 3.0)

# Molecular pocket: kick dominates; hats tiny; acid late/quiet; stretch subtle
KICK_G = 1.55
KICK_BREAK_G = 0.62
HATS_G = 0.22
OH_G = 0.18
PERC_G = 0.22
ACID_SCALE = 0.55
STRETCH_SCALE = 0.42
VOX_G = 0.42
VOX_BREAK_G = 0.58

# PA master — heavy kick / quiet tops (after DNA is right)
AF_CHAIN = (
    "highpass=f=26:poles=2,"
    "lowshelf=f=90:t=q:w=0.7:g=2.0,"
    "equalizer=f=52:t=q:w=1.1:g=3.2,"
    "equalizer=f=72:t=q:w=1.4:g=-1.3,"
    "equalizer=f=380:t=q:w=1.0:g=-1.2,"
    "equalizer=f=1400:t=q:w=1.0:g=0.9,"
    "equalizer=f=3200:t=q:w=1.6:g=1.7,"
    "equalizer=f=6500:t=q:w=1.2:g=-0.8,"
    "equalizer=f=10000:t=q:w=1.1:g=-2.8,"
    "highshelf=f=7000:t=q:w=0.7:g=-3.6,"
    "lowpass=f=15000:poles=1,"
    "acompressor=threshold=-18dB:ratio=1.6:attack=12:release=180:makeup=1.2,"
    "alimiter=limit=0.89,"
    "loudnorm=I=-8.5:TP=-1.0:LRA=7"
)

for mod in (dna, classic):
    mod.BPM = BPM
    mod.BARS = BARS
    mod.BEATS = BEATS
    mod.N = N
classic.RES_Q = 0.12
classic.BASE_CUT0 = 260.0
classic.ENV_AMT = 1600.0
classic.ROLL_MAX = 90.0
classic.GRIT = 1.55
classic.ENV_DECAY = 0.9972
classic.OSC_KIND = "saw"
classic.OUT = OUT
classic.SECTION_MIX_DIR = SECTION_MIX_DIR


def send(cmd, params=None, timeout=25.0):
    """Short timeouts — never hang forever on create_audio_clip."""
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=3) as sock:
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
    if not r or r.get("status") != "success":
        print("FAIL", label, (r or {}).get("message", r))
        return None
    print("OK", label)
    return r.get("result", r)


def place(buf, sample, beat, gain=1.0):
    dna.place(buf, sample, beat, gain)


def read_wav(path: Path) -> list[float]:
    return dna.read_wav(path)


def write_mono(path: Path, samples, peak_target=0.90):
    peak = max(1e-9, max((abs(x) for x in samples), default=1e-9))
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


def write_stereo_lr(path: Path, left, right, peak_target=0.90):
    n = min(len(left), len(right))
    peak = 1e-9
    for i in range(n):
        peak = max(peak, abs(left[i]), abs(right[i]))
    scale = peak_target / peak
    st = array.array("h")
    for i in range(n):
        st.append(max(-32767, min(32767, int(left[i] * scale * 32767))))
        st.append(max(-32767, min(32767, int(right[i] * scale * 32767))))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())


def electribe_master(src: Path, dst: Path):
    dna.electribe_master(src, dst)


def swing_offset(st: int) -> float:
    return SWING_DELAY if (st % 2 == 1) else 0.0


def valve_force(samples: list[float], tube_gain: float = TUBE_GAIN) -> list[float]:
    bias = 0.04
    norm = math.tanh(tube_gain)
    out = [0.0] * len(samples)
    for i, x in enumerate(samples):
        driven = (x + bias) * tube_gain
        y = math.tanh(driven) / norm - bias * 0.55
        y = 0.9 * y + 0.1 * math.tanh(x * (tube_gain * 0.6))
        out[i] = y
    return out


def mild_compress_kick(samples: list[float], thr=0.40, ratio=1.7) -> list[float]:
    out = [0.0] * len(samples)
    env = 0.0
    atk_c = math.exp(-1.0 / (SR * 0.003))
    rel_c = math.exp(-1.0 / (SR * 0.14))
    for i, x in enumerate(samples):
        a = abs(x)
        env = a + (env - a) * (atk_c if a > env else rel_c)
        if env > thr:
            over = env - thr
            gain = thr + over / ratio
            g = gain / max(1e-9, env)
        else:
            g = 1.0
        out[i] = x * g * 1.08
    return out


def one_pole(samples, cutoff_hz, mode="lpf", q=0.12):
    out = [0.0] * len(samples)
    l = b = 0.0
    for i, x in enumerate(samples):
        f = 2 * math.sin(math.pi * dna.clamp(cutoff_hz / SR, 0.0001, 0.45))
        l += f * b
        h = x - l - q * b
        b += f * h
        out[i] = h if mode == "hpf" else l
    return out


def bandpass(samples, lo, hi):
    return one_pole(one_pole(samples, lo, mode="hpf"), hi, mode="lpf")


def soft_gate(samples, thr=0.018):
    out = [0.0] * len(samples)
    env = 0.0
    for i, x in enumerate(samples):
        a = abs(x)
        env = a if a > env else env * 0.9991
        g = 1.0 if env > thr else env / max(thr, 1e-6)
        out[i] = x * min(1.0, g)
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


def flanger(samples, rate_hz=1.18, depth_ms=3.8, base_ms=2.2, feedback=0.22, mix=0.45):
    """Pozek-ish flange (~0.85s period from Flangerboy analysis → ~1.18 Hz).
    Stable circular delay — feedback clamped so long buffers cannot explode.
    """
    n = len(samples)
    out = [0.0] * n
    max_delay = max(2, int((base_ms + depth_ms) * 0.001 * SR) + 3)
    circ = [0.0] * (max_delay + 4)
    feedback = min(0.45, abs(feedback))
    for i, x in enumerate(samples):
        t = i / SR
        mod = math.sin(2 * math.pi * rate_hz * t)
        delay_ms = base_ms + depth_ms * 0.5 * (1.0 + mod)
        d = delay_ms * 0.001 * SR
        di = int(d)
        frac = d - di
        # read from circular buffer
        i0 = (i - di) % len(circ)
        i1 = (i - di - 1) % len(circ)
        delayed = circ[i0] * (1 - frac) + circ[i1] * frac
        y = x + delayed * mix
        # write input + limited feedback
        w = x + delayed * feedback
        if w > 1.2:
            w = 1.2
        elif w < -1.2:
            w = -1.2
        circ[i % len(circ)] = w
        out[i] = y
    return out


def chorus(samples, rate_hz=0.55, depth_ms=6.5, base_ms=9.0, mix=0.35):
    n = len(samples)
    out = [0.0] * n
    max_delay = int((base_ms + depth_ms) * 0.001 * SR) + 2
    for i, x in enumerate(samples):
        t = i / SR
        mod = math.sin(2 * math.pi * rate_hz * t + 0.7)
        d = (base_ms + depth_ms * 0.5 * (1.0 + mod)) * 0.001 * SR
        di = int(d)
        frac = d - di
        j = i - di
        if j - 1 >= 0:
            delayed = samples[j] * (1 - frac) + samples[j - 1] * frac
        elif j >= 0:
            delayed = samples[j]
        else:
            delayed = 0.0
        out[i] = x * (1.0 - mix * 0.5) + delayed * mix
    return out


def mono_delay(samples, time_beats=0.375, wet=0.18, fb=0.28):
    d = max(1, int(time_beats * 60.0 / BPM * SR))
    out = [0.0] * len(samples)
    line = [0.0] * len(samples)
    for i, x in enumerate(samples):
        delayed = line[i - d] if i >= d else 0.0
        out[i] = x + delayed * wet
        line[i] = x + delayed * fb
    return out


def find_ffprobe() -> str:
    cands = [
        str(Path(dna.FFMPEG).parent / "ffprobe.exe"),
        r"C:\Users\Gebruiker\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffprobe.exe",
        "ffprobe",
    ]
    for c in cands:
        try:
            subprocess.run([c, "-version"], capture_output=True, check=True)
            return c
        except Exception:
            continue
    raise RuntimeError("ffprobe not found")


def make_stretch_loop(src_name: str, bars: int = 2) -> list[float]:
    src = FACTORY / src_name
    raw_dst = ONESHOT / f"stretch_raw_{src_name}"
    electribe_master(src, raw_dst)
    samples = read_wav(raw_dst)
    target_n = int(bars * 4.0 * 60.0 / BPM * SR)
    # rubberband tempo-only if available
    rb_in = ONESHOT / "stretch_rb_in.wav"
    rb_out = ONESHOT / "stretch_rb_out.wav"
    write_mono(rb_in, samples, 0.88)
    ok_rb = False
    try:
        # stretch ratio: input length -> target_n
        if len(samples) > 100:
            tempo = len(samples) / target_n
            r = subprocess.run(
                [
                    dna.FFMPEG, "-y", "-i", str(rb_in),
                    "-af", f"rubberband=tempo={tempo}:pitch=1",
                    str(rb_out),
                ],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0 and rb_out.exists():
                samples = read_wav(rb_out)
                ok_rb = True
    except Exception as e:
        print("rubberband", e)
    if len(samples) > target_n:
        samples = samples[:target_n]
    elif len(samples) < target_n:
        # loop-fill
        out = []
        while len(out) < target_n:
            out.extend(samples)
        samples = out[:target_n]
    fade = int(0.008 * SR)
    for i in range(fade):
        g = i / max(1, fade)
        samples[i] *= g
        samples[-(i + 1)] *= g
    # darken stretch (Molecular = dark rolling)
    samples = one_pole(samples, 2200.0, mode="lpf")
    write_mono(ONESHOT / "stretch_loop_ready.wav", samples, 0.82)
    print("STRETCH", src_name, "rb", ok_rb, "n", len(samples))
    return samples


def ensure_oneshots():
    mapping = {
        "146_SinKick.wav": "esx_SinKick.wav",
        "054_HH-1C.wav": "esx_HH1C.wav",
        "055_HH-1O.wav": "esx_HH1O.wav",
        "045_Rim-1.wav": "esx_Rim1.wav",
        "021_SD-1.wav": "esx_SD1.wav",
        "092_JunkPerc.wav": "esx_JunkPerc.wav",
    }
    used = []
    shots = {}
    for src_name, dst_name in mapping.items():
        src = FACTORY / src_name
        dst = ONESHOT / dst_name
        if not src.exists():
            print("MISSING", src_name)
            continue
        electribe_master(src, dst)
        used.append(src_name)
        shots[dst_name] = read_wav(dst)

    kick = shots.get("esx_SinKick.wav") or dna.synth_kick_sledge(dna.mulberry32(0xE51), "full")
    # Molecular: heavier body — tube + compress + slight LPF weight, keep punch click short
    kick = [dna.tanh_drive(x, 1.7) for x in kick]
    kick = mild_compress_kick(kick)
    # reinforce low body with gentle LPF blend
    body = one_pole(kick, 180.0, mode="lpf")
    kick = [0.72 * kick[i] + 0.38 * body[i] for i in range(len(kick))]
    click = dna.synth_kick_sledge(dna.mulberry32(0xC11C), "full")[: int(0.018 * SR)]

    hat_c = shots.get("esx_HH1C.wav") or dna.synth_hat(dna.mulberry32(1), False)
    # darker tribal hats — cut air
    hat_c = one_pole([dna.tanh_drive(x, 1.05) for x in hat_c], 9000.0, mode="lpf")
    hat_o = shots.get("esx_HH1O.wav") or dna.synth_hat(dna.mulberry32(2), True)
    hat_o = one_pole([dna.tanh_drive(x, 1.0) for x in hat_o], 8500.0, mode="lpf")
    rim = shots.get("esx_Rim1.wav")
    snare = shots.get("esx_SD1.wav")
    junk = shots.get("esx_JunkPerc.wav")
    if junk:
        # keep junk almost unused later; still prepare quiet
        junk = one_pole([dna.tanh_drive(x, 1.15) for x in junk], 5000.0, mode="lpf")

    stretch_src = "189_SynLP-1.wav" if (FACTORY / "189_SynLP-1.wav").exists() else "175_PercLP-1.wav"
    stretch = make_stretch_loop(stretch_src, bars=2)
    used.append(f"STRETCH:{stretch_src}")

    write_mono(ONESHOT / "kick_ready.wav", kick, 0.94)
    return {
        "kick": kick,
        "click": click,
        "hat_c": hat_c,
        "hat_o": hat_o,
        "rim": rim,
        "snare": snare,
        "junk": junk,
        "stretch": stretch,
        "stretch_src": stretch_src,
        "used": used,
    }


def ensure_vox_phrases():
    """Pozek-style chopped phrases from ESX Voice ROM — flanger/chorus/mid BP.
    No synth formants. No Pozek MP3 ripping.
    """
    voice_names = [
        "107_Voice-1.wav", "108_Voice-2.wav", "109_Voice-3.wav",
        "110_Voice-4.wav", "111_Voice-5.wav", "112_Voice-6.wav",
        "113_Voice-7.wav", "114_Voice-8.wav", "116_Voice-10.wav",
        "118_Voice-12.wav", "119_Voice-13.wav", "121_Voice-15.wav",
        "122_Voice-16.wav", "124_Voice-18.wav", "125_Voice-19.wav",
        "210_Voice-24.wav", "211_Voice-25.wav", "212_Voice-26.wav",
        "213_Voice-27.wav", "214_Voice-28.wav",
    ]
    phrases = []
    used = []
    rng = dna.mulberry32(0xF1A7)

    for src_name in voice_names:
        src = FACTORY / src_name
        if not src.exists():
            print("MISSING voice", src_name)
            continue
        dst = ONESHOT / f"esx_{src_name}"
        electribe_master(src, dst)
        raw = read_wav(dst)
        if not raw:
            continue
        peak_i = max(range(len(raw)), key=lambda i: abs(raw[i]))
        # phrase-like chops: short + medium lengths (not beep stabs)
        for dur_s, tag in ((0.09, "short"), (0.14, "mid"), (0.22, "long")):
            start = max(0, peak_i - int(0.012 * SR))
            end = min(len(raw), start + int(dur_s * SR))
            chop = raw[start:end]
            if max(abs(x) for x in chop) < 1e-4:
                continue
            # mid-forward Pozek pocket ~800–2.5k (analysis centroid ~1290)
            chop = bandpass(chop, 750.0, 2600.0)
            chop = soft_gate(chop, 0.012)
            # light tube warmth
            chop = [math.tanh(x * 1.45) for x in chop]
            # flanger + chorus (character, not formant synth)
            rate = 1.05 + 0.35 * rng()
            chop = flanger(chop, rate_hz=rate, depth_ms=3.2 + 1.5 * rng(), feedback=0.2, mix=0.42 + 0.12 * rng())
            pk = max((abs(x) for x in chop), default=0.0)
            if pk > 0.95:
                chop = [x * (0.85 / pk) for x in chop]
            chop = chorus(chop, rate_hz=0.45 + 0.25 * rng(), mix=0.28 + 0.12 * rng())
            chop = bandpass(chop, 800.0, 2500.0)  # re-tighten after FX (no bright air)
            write_mono(ONESHOT / f"vox_{Path(src_name).stem}_{tag}.wav", chop, 0.78)
            phrases.append(chop)
            used.append(f"{src_name}:{tag}")

    # Build a few multi-hit "phrase packs" (methodical call feel)
    packs = []
    if phrases:
        for pi in range(8):
            pack = [0.0] * int(0.55 * SR)
            hits = 3 + int(rng() * 3)  # 3–5 chops
            for h in range(hits):
                shot = phrases[int(rng() * len(phrases)) % len(phrases)]
                # place at ~16th spacing inside pack
                beat_off = h * (0.12 + 0.04 * rng())
                place(pack, shot, beat_off * (BPM / 60.0), 0.7 + 0.3 * rng())
            pack = mono_delay(pack, time_beats=0.375, wet=0.16, fb=0.22)
            pack = bandpass(pack, 780.0, 2550.0)
            pack = soft_gate(pack, 0.01)
            pk = max((abs(x) for x in pack), default=0.0)
            if pk > 0.9:
                pack = [x * (0.8 / pk) for x in pack]
            write_mono(ONESHOT / f"vox_pack_{pi}.wav", pack, 0.75)
            packs.append(pack)
            used.append(f"pack_{pi}")

    print("VOX_PHRASES", len(phrases), "PACKS", len(packs))
    return phrases, packs, used


def scene_gains(sid: int):
    acid_base = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.12, 4: 0.28, 5: 0.18, 6: 0.32, 7: 0.08}.get(sid, 0.2)
    stretch_base = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.35, 4: 0.45, 5: 0.55, 6: 0.4, 7: 0.25}.get(sid, 0.3)
    perc_base = {0: 0.0, 1: 0.0, 2: 0.35, 3: 0.4, 4: 0.45, 5: 0.2, 6: 0.5, 7: 0.15}.get(sid, 0.3)
    kick_g = KICK_BREAK_G if sid == 5 else KICK_G
    if sid == 0:
        kick_g = KICK_G * 0.95
    vox_g = {
        0: 0.0, 1: 0.0, 2: 0.0,
        3: VOX_G * 0.55,
        4: VOX_G,
        5: VOX_BREAK_G,
        6: VOX_G * 0.95,
        7: VOX_G * 0.3,
    }.get(sid, VOX_G)
    return {
        "kick": kick_g,
        "hats": HATS_G if sid != 0 else 0.0,
        "oh": OH_G if sid >= 2 else 0.0,
        "perc": perc_base * PERC_G,
        "stretch": stretch_base * STRETCH_SCALE,
        "acid": acid_base * ACID_SCALE,
        "vox": vox_g,
    }


def render_vox_lane(sid: int, phrases, packs) -> list[float]:
    """Methodical Pozek chops — phrase packs + sparse single hits under kick."""
    trk = [0.0] * N
    if sid < 3 or not phrases:
        return trk
    rng = dna.mulberry32(0xA11 + sid * 131)

    for bar in range(BARS):
        base = bar * 4.0
        # phrase pack every 2 or 4 bars (methodical, not constant topline)
        pack_period = 2 if sid in (5, 6) else 4
        if packs and bar % pack_period == 0:
            pack = packs[int(rng() * len(packs)) % len(packs)]
            # start on beat 2 or 3 (sit around kick, not on top of downbeat always)
            start_beat = 1.0 if (bar // pack_period) % 2 == 0 else 2.0
            g = 0.72 if sid != 5 else 0.9
            if sid == 7 and bar >= 10:
                continue
            place(trk, pack, base + start_beat, g)

        # sparse single chops answering the pack
        if sid == 3:
            hits = [12] if bar % 2 == 1 else []
            g0 = 0.55
        elif sid == 4:
            hits = [6, 14] if bar % 2 == 0 else [10]
            g0 = 0.62
        elif sid == 5:
            hits = [0, 8, 12] if bar % 2 == 0 else [4, 10]
            g0 = 0.8
        elif sid == 6:
            hits = [6, 11, 14]
            g0 = 0.65
        elif sid == 7:
            hits = [12] if bar < 8 else []
            g0 = 0.4
        else:
            hits = []
            g0 = 0.5

        for st in hits:
            shot = phrases[int(rng() * len(phrases)) % len(phrases)]
            off = swing_offset(st)
            g = g0 * (0.8 + 0.25 * rng())
            # quieter if on quarter (kick owns)
            if st % 4 == 0:
                g *= 0.55
            place(trk, shot, base + st * 0.25 + off, g)

    # bus FX: flange again lightly + delay color + mid pocket
    trk = flanger(trk, rate_hz=1.18, depth_ms=2.8, base_ms=1.8, feedback=0.18, mix=0.32)
    trk = mono_delay(trk, time_beats=0.375, wet=0.14, fb=0.2)
    trk = bandpass(trk, 800.0, 2500.0)
    trk = soft_gate(trk, 0.008)
    # hard normalize — never let FX blow the mix bus
    peak = max((abs(x) for x in trk), default=0.0)
    if peak > 0.85:
        s = 0.75 / peak
        trk = [x * s for x in trk]
    elif peak > 1e-9:
        # keep relative level but cap
        pass
    return trk


def render_scene(sid, name, shots, pattern, phrases, packs):
    kick = shots["kick"]
    click = shots["click"]
    hat_c = shots["hat_c"]
    hat_o = shots["hat_o"]
    rim = shots["rim"]
    junk = shots["junk"]
    stretch_one = shots["stretch"]

    trk_k = [0.0] * N
    trk_h = [0.0] * N
    trk_oh = [0.0] * N
    trk_p = [0.0] * N
    trk_st = [0.0] * N

    for bar in range(BARS):
        base = bar * 4.0

        # --- KICK: Molecular clean heavy 4/4 (kick owns pocket) ---
        if sid == 5:
            # break space — kick on 1 every other bar, or sparse
            if bar % 2 == 0:
                place(trk_k, kick, base, 0.75)
                place(trk_k, click, base, 0.12)
            if bar % 4 == 3:
                place(trk_k, kick, base + 2.0, 0.45)
        elif sid == 7:
            if bar < 14:
                fade = 1.0 if bar < 8 else max(0.35, 1.0 - (bar - 8) * 0.1)
                for qi, step in enumerate((0, 4, 8, 12)):
                    # Molecular accent: beat 4 slightly stronger
                    g = (1.05 if qi == 3 else 0.95) * fade
                    place(trk_k, kick, base + step * 0.25, g)
                    place(trk_k, click, base + step * 0.25, 0.12 * fade)
        else:
            # steady 4/4 — no mid-beat industrial ghosts
            for qi, step in enumerate((0, 4, 8, 12)):
                # slight Molecular accent shape: 1 & 4 a touch hotter
                g = 1.08 if qi in (0, 3) else 1.0
                if sid == 6:
                    g *= 1.06
                elif sid <= 1:
                    g *= 0.96
                place(trk_k, kick, base + step * 0.25, g)
                place(trk_k, click, base + step * 0.25, 0.13)

        # --- HATS: sparse tribal/controlled (NOT busy 16ths) ---
        if sid == 0:
            pass
        elif sid == 1:
            # offbeat 8ths only — tribal sparse
            for st in (2, 6, 10, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.55)
        elif sid == 2:
            for st in (2, 6, 10, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.58)
            # light on-beat tick every other bar
            if bar % 2 == 0:
                for st in (0, 8):
                    place(trk_h, hat_c, base + st * 0.25, 0.28)
            if bar % 2 == 1:
                place(trk_oh, hat_o, base + 14 * 0.25 + swing_offset(14), 0.32)
        elif sid in (3, 4):
            for st in (2, 6, 10, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.6)
            # sparse ghost 16ths — only a couple, not full grid
            if bar % 2 == 0:
                for st in (3, 11):
                    place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.28)
            for st in (6, 14):
                if bar % 2 == (0 if st == 6 else 1):
                    place(trk_oh, hat_o, base + st * 0.25 + swing_offset(st), 0.3)
        elif sid == 5:
            for st in (6, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.35)
        elif sid == 6:
            for st in (2, 6, 10, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.62)
            for st in (1, 9):
                if bar % 2 == 0:
                    place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.26)
            place(trk_oh, hat_o, base + 14 * 0.25 + swing_offset(14), 0.34)
        elif sid == 7 and bar < 10:
            for st in (6, 14):
                place(trk_h, hat_c, base + st * 0.25 + swing_offset(st), 0.35)

        # --- PERC: minimal (kill industrial junk density) ---
        if sid in (2, 3, 4, 6) and rim is not None:
            # quiet rim on 2 and 4 only
            place(trk_p, rim, base + 1.0, 0.38 if sid != 6 else 0.45)
            if sid >= 4 and bar % 2 == 1:
                place(trk_p, rim, base + 3.0, 0.32)
        # junk almost never — only Peak as a whisper
        if sid == 6 and junk is not None and bar % 4 == 0:
            place(trk_p, junk, base + 2.75 + swing_offset(11), 0.18)

        # --- STRETCH: subtle dark bed ---
        if sid >= 3 and bar % 2 == 0:
            g = {3: 0.4, 4: 0.48, 5: 0.58, 6: 0.42, 7: 0.3}.get(sid, 0.4)
            if sid == 7 and bar >= 8:
                g *= 0.5
            place(trk_st, stretch_one, base, g)

    # Acid: muted until mid; minimal under kick
    acid_drive = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.35, 4: 0.55, 5: 0.4, 6: 0.6, 7: 0.2}.get(sid, 0.4)
    acid_full = classic.render_classic_acid(pattern, grit=classic.GRIT, roll=True)
    acid = [x * acid_drive for x in acid_full[:N]]
    if len(acid) < N:
        acid.extend([0.0] * (N - len(acid)))
    # darker acid for Molecular
    if acid_drive > 0:
        acid = one_pole(acid, 1800.0 if sid != 5 else 1400.0, mode="lpf")

    trk_v = render_vox_lane(sid, phrases, packs)

    # write stems
    prefix = f"s{sid}_{name}"
    paths = {
        "kick": OUT / f"{prefix}_kick.wav",
        "hats": OUT / f"{prefix}_hats.wav",
        "oh": OUT / f"{prefix}_oh.wav",
        "perc": OUT / f"{prefix}_perc.wav",
        "stretch": OUT / f"{prefix}_stretch.wav",
        "acid": OUT / f"{prefix}_acid.wav",
        "vox": OUT / f"{prefix}_vox.wav",
    }
    write_mono(paths["kick"], trk_k, 0.92)
    write_mono(paths["hats"], trk_h, 0.75)
    write_mono(paths["oh"], trk_oh, 0.72)
    write_mono(paths["perc"], trk_p, 0.7)
    write_mono(paths["stretch"], trk_st, 0.78)
    write_mono(paths["acid"], acid, 0.78)
    write_mono(paths["vox"], trk_v, 0.78)

    g = scene_gains(sid)

    def mix_lr(include_vox: bool):
        dry = [0.0] * N
        for i in range(N):
            dry[i] = (
                trk_k[i] * g["kick"]
                + acid[i] * g["acid"]
                + trk_h[i] * g["hats"]
                + trk_oh[i] * g["oh"]
                + trk_p[i] * g["perc"]
                + trk_st[i] * g["stretch"]
                + (trk_v[i] * g["vox"] if include_vox else 0.0)
            )
        send_src = [0.0] * N
        for i in range(N):
            send_src[i] = (
                acid[i] * g["acid"] * 0.45
                + trk_h[i] * g["hats"] * 0.55
                + trk_oh[i] * g["oh"] * 0.35
                + ((trk_v[i] * g["vox"] * 0.55) if include_vox else 0.0)
            )
        Lpp, Rpp = pingpong_stereo(send_src, wet=DELAY_WET, feedback=DELAY_FB)
        left = [0.0] * N
        right = [0.0] * N
        for i in range(N):
            left[i] = dry[i] + (Lpp[i] - send_src[i]) * 0.85
            right[i] = dry[i] + (Rpp[i] - send_src[i]) * 0.85
        left = valve_force(left)
        right = valve_force(right)
        peak = 1e-9
        for i in range(N):
            peak = max(peak, abs(left[i]), abs(right[i]))
        if peak > 0.95:
            s = 0.92 / peak
            left = [x * s for x in left]
            right = [x * s for x in right]
        return left, right, peak

    left, right, peak = mix_lr(True)
    mix_path = SECTION_MIX_DIR / f"{prefix}_real_mix.wav"
    write_stereo_lr(mix_path, left, right, 0.90)
    paths["mix"] = mix_path

    left_nv, right_nv, peak_nv = mix_lr(False)
    mix_nv = SECTION_MIX_DIR / f"{prefix}_real_novox_mix.wav"
    write_stereo_lr(mix_nv, left_nv, right_nv, 0.90)
    paths["mix_novox"] = mix_nv

    print(
        "scene", sid, name,
        "gains", {k: round(v, 3) for k, v in g.items()},
        "vox_peak", round(max((abs(x) for x in trk_v), default=0), 4),
        "peak", round(peak, 4),
    )
    return paths


def bounce_mp3(scene_paths, key: str, mp3_path: Path) -> float:
    listfile = OUT / f"_concat_{key}.txt"
    raw_concat = OUT / f"_concat_{key}.wav"
    mastered = OUT / f"_master_{key}.wav"
    with open(listfile, "w", encoding="utf-8") as f:
        for sid, name in SCENES:
            p = str(scene_paths[sid][key]).replace("\\", "/")
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
        [dna.FFMPEG, "-y", "-i", str(mastered), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)],
        check=True,
        capture_output=True,
    )
    dur = 8 * (N / SR)
    try:
        ffprobe = find_ffprobe()
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(mp3_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        dur = float(probe.stdout.strip())
    except Exception as e:
        print("ffprobe", e)
    print("MP3", mp3_path, "dur", round(dur, 2))
    return dur


def try_ableton_load(scene_paths):
    """Best-effort Ableton load — skip on any hang/fail. Bounce already done."""
    try:
        snap_r = send("get_session_snapshot", {"include_devices": False}, timeout=20)
        snap = ok(snap_r, "snapshot")
    except Exception as e:
        print("Ableton skip (unreachable)", e)
        return ["ableton_unreachable"]
    if not snap:
        return ["ableton_snapshot_fail"]
    errors = []
    try:
        ok(send("set_tempo", {"tempo": BPM}, timeout=10), "tempo")
        ok(send("stop_playback", timeout=10), "stop")
        by = {t["name"]: t["index"] for t in snap["tracks"]}
        kick_idx = by.get("E-Kick")
        hats_idx = by.get("E-Hats")
        jam_idx = by.get("ESX Jam") or by.get("E2S Jam")
        # Load ONLY Peak mix to jam track — avoid create_audio_clip forever loops
        if jam_idx is not None:
            mix = scene_paths[6]["mix"]
            send("delete_clip", {"track_index": jam_idx, "clip_index": 6})
            r = send(
                "create_audio_clip",
                {"track_index": jam_idx, "clip_index": 6, "path": str(mix)},
                timeout=45,
            )
            if r.get("status") == "success":
                send("set_clip_name", {"track_index": jam_idx, "clip_index": 6, "name": "Peak_Real_mix"})
                send("fire_clip", {"track_index": jam_idx, "clip_index": 6}, timeout=10)
                ok(send("start_playback", timeout=10), "start")
                print("Ableton loaded Peak mix only on jam")
            else:
                errors.append(f"create_audio_clip: {r}")
                print("Ableton create_audio_clip failed/skipped", r)
        else:
            errors.append("no jam track")
        print("TRACK_HINT", "kick", kick_idx, "hats", hats_idx, "jam", jam_idx)
    except Exception as e:
        errors.append(str(e))
        print("Ableton load aborted", e)
    return errors


def write_notes(dur, dur_nv, used_drums, used_vox, errors):
    NOTES.write_text(
        f"""# EvAIx ESX-1 PnxPozek REAL DNA PA @162

**Output:** `{MP3}`
**NoVox:** `{MP3_NOVOX}`
**Duration:** {dur:.2f}s / novox {dur_nv:.2f}s
**BPM:** {BPM}

## What changed vs rejected PneumatixKick / PozekVox bounces
- **Not a stem EQ remix** of ValveForce SwingFX — patterns regenerated for Molecular DNA
- Kick = steady heavy 4/4 only (Molecular pocket); no Peak mid-beat ghosts; accent on 1&4
- Hats = sparse tribal offbeat 8ths (not busy swung 16th grids); much quieter
- Perc = minimal rim; JunkPerc almost muted (was industrial clutter)
- Acid = muted until Vox_Enter/Full_Pocket and kept dark/low
- Stretch = subtle dark bed only
- Vox = ESX Voice chops + phrase packs with **real flanger/chorus** + mid BP 800–2500;
  **removed synth formant beeps** that sounded nothing like Pozek
- Ableton load best-effort (Peak mix only) — primary deliverable is stem-render MP3

## Gains
kick={KICK_G} break={KICK_BREAK_G} hats={HATS_G} oh={OH_G} perc={PERC_G}
acid_scale={ACID_SCALE} stretch_scale={STRETCH_SCALE} vox={VOX_G}/{VOX_BREAK_G}

## Samples
Drums: {used_drums}
Vox: {used_vox[:40]}{'...' if len(used_vox)>40 else ''}

## AF
```
{AF_CHAIN}
```

Errors: {errors or 'none'}
""",
        encoding="utf-8",
    )


def main():
    errors = []
    print("=== PNX Molecular + Pozek REAL DNA @", BPM, "===")
    shots = ensure_oneshots()
    phrases, packs, used_vox = ensure_vox_phrases()
    if not phrases:
        raise RuntimeError("no vox phrases")
    pattern = classic.classic_pattern(dna.SEED + 303)

    scene_paths = {}
    for sid, name in SCENES:
        scene_paths[sid] = render_scene(sid, name, shots, pattern, phrases, packs)

    print("=== Bounce MP3 (stem-render) ===")
    try:
        dur = bounce_mp3(scene_paths, "mix", MP3)
    except Exception as e:
        errors.append(f"mp3: {e}")
        print("FAIL mp3", e)
        dur = 0.0
    try:
        dur_nv = bounce_mp3(scene_paths, "mix_novox", MP3_NOVOX)
    except Exception as e:
        errors.append(f"mp3_novox: {e}")
        print("FAIL mp3_novox", e)
        dur_nv = 0.0

    print("=== Ableton (optional, short timeout) ===")
    errors.extend(try_ableton_load(scene_paths))

    write_notes(dur, dur_nv, shots["used"], used_vox, errors)
    # also mirror notes to workspace-friendly copy path on PC Downloads
    try:
        Path(r"C:\Users\Gebruiker\Downloads\EvAIx_ESX1_PnxPozek_Real_PA_162_NOTES.md").write_text(
            NOTES.read_text(encoding="utf-8"), encoding="utf-8"
        )
    except Exception:
        pass

    print("MP3_PATH", str(MP3))
    print("MP3_NOVOX_PATH", str(MP3_NOVOX))
    print("MP3_DURATION_SEC", round(dur, 2))
    print("MP3_NOVOX_DURATION_SEC", round(dur_nv, 2))
    print("ERRORS", errors)
    print("DONE build_esx1_pnx_pozek_real_162")


if __name__ == "__main__":
    main()
