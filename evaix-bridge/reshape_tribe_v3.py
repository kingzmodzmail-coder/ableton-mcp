import json, math, socket, wave
from pathlib import Path
import numpy as np

OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples")
KICKS = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\packs\insane-teknology-kicks-2") / "Insane Teknology Kicks 2"
ESX = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT.mkdir(parents=True, exist_ok=True)
BPM, BARS, SR = 175.0, 4, 44100
total = int(BARS * 4 * (60.0 / BPM) * SR)
HOST, PORT = "127.0.0.1", 9877

def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, nframes, *_ = w.getparams()
        raw = w.readframes(nframes)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    if ch == 2:
        data = data.reshape(-1, 2).mean(axis=1)
    if sr != SR:
        x = np.linspace(0, 1, len(data), endpoint=False)
        xi = np.linspace(0, 1, int(len(data) * SR / sr), endpoint=False)
        data = np.interp(xi, x, data)
    return data.astype(np.float32)

def write_wav(path, mono):
    mono = np.nan_to_num(np.asarray(mono, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    mono = np.clip(mono, -1, 1)
    stereo = np.column_stack([mono, mono])
    pcm = (stereo * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

def place(buf, sample, beat, gain=1.0):
    start = int(beat * (60.0 / BPM) * SR)
    n = min(len(sample), total - start)
    if n > 0:
        buf[start:start + n] += sample[:n] * gain

def env_adsr(n, a=0.002, d=0.04, s=0.35, r=0.05):
    ea, ed, er = int(a * SR), int(d * SR), int(r * SR)
    es = max(0, n - ea - ed - er)
    parts = []
    if ea:
        parts.append(np.linspace(0, 1, ea, endpoint=False))
    if ed:
        parts.append(np.linspace(1, s, ed, endpoint=False))
    if es:
        parts.append(np.full(es, s))
    if er:
        parts.append(np.linspace(s, 0, er, endpoint=False))
    e = np.concatenate(parts) if parts else np.zeros(0)
    if len(e) < n:
        e = np.pad(e, (0, n - len(e)))
    return e[:n].astype(np.float32)

def one_pole_lp(x, cutoff_hz):
    y = np.zeros(len(x), dtype=np.float64)
    s = 0.0
    for i, sample in enumerate(x):
        c = float(np.clip(cutoff_hz[i], 80.0, SR * 0.4))
        a = math.exp(-2.0 * math.pi * c / SR)
        s = (1 - a) * float(sample) + a * s
        y[i] = s
    return y.astype(np.float32)

# drums
k_main = read_wav(KICKS / "24_KICK BASS E01.wav")
k_alt = read_wav(KICKS / "1_KICK E01.wav")
kick = np.zeros(total, np.float32)
for bar in range(BARS):
    base = bar * 4
    for b in range(4):
        place(kick, k_main if b % 2 == 0 else k_alt, base + b, 0.95)
    if bar >= 2:
        place(kick, k_alt, base + 0.5, 0.2)

snare_s = read_wav(ESX / "033_SD-13.wav")
clap_s = read_wav(ESX / "048_Clap-1.wav")
rim_s = read_wav(ESX / "045_Rim-1.wav")
snare = np.zeros(total, np.float32)
for bar in range(BARS):
    base = bar * 4
    place(snare, snare_s, base + 1, 0.75)
    place(snare, clap_s, base + 1, 0.3)
    place(snare, snare_s, base + 3, 0.8)
    place(snare, clap_s, base + 3, 0.35)
    if bar == 3:
        for off in (3.25, 3.5, 3.75):
            place(snare, rim_s, base + off, 0.5)

hhc = read_wav(ESX / "056_HH-2C.wav")
hho = read_wav(ESX / "057_HH-2O.wav")
hats = np.zeros(total, np.float32)
for bar in range(BARS):
    base = bar * 4
    for step in range(16):
        place(hats, hhc, base + step * 0.25, 0.55 if step % 2 == 0 else 0.28)
    place(hats, hho, base + 3.5, 0.45)

NOTE = {"C2": 65.41, "Eb2": 77.78, "F2": 87.31, "G2": 98.0, "Ab2": 103.83, "Bb2": 116.54, "C3": 130.81}

# Technique A: resonant acid 16ths (303-ish)
seq = [
    ("C2", 0.25, 0.9), ("C2", 0.25, 0.5), ("Eb2", 0.25, 0.85), ("C2", 0.25, 0.45),
    ("F2", 0.25, 0.9), ("Eb2", 0.25, 0.55), ("G2", 0.25, 0.8), ("Bb2", 0.25, 0.7),
    ("C2", 0.25, 0.9), ("Ab2", 0.25, 0.6), ("G2", 0.25, 0.75), ("F2", 0.25, 0.5),
    ("Eb2", 0.25, 0.85), ("C2", 0.25, 0.55), ("Bb2", 0.35, 0.9), ("C3", 0.4, 0.95),
]
acid = np.zeros(total, np.float32)
for bar in range(BARS):
    tbeat = float(bar * 4)
    for name, dur, vel in seq:
        start = int(tbeat * (60.0 / BPM) * SR)
        n = min(int(dur * (60.0 / BPM) * SR), total - start)
        if n <= 0:
            break
        freq = NOTE[name]
        t = np.arange(n, dtype=np.float64) / SR
        if vel > 0.85:
            freqs = np.linspace(freq * (2 ** (-1 / 12)), freq, n)
            phase = np.cumsum(freqs / SR)
            osc = 2.0 * (phase - np.floor(phase + 0.5))
        else:
            osc = 2.0 * ((t * freq) - np.floor(t * freq + 0.5))
        cut0 = 600 + vel * 1200
        cut1 = 250 + (1 - vel) * 150
        if bar % 2:
            cut0 *= 1.1
        cutoff = np.linspace(cut0, cut1, n)
        tone = one_pole_lp(osc.astype(np.float32), cutoff)
        tone = tone + 0.3 * (osc.astype(np.float32) - tone)
        tone = np.tanh(tone * (1.2 + vel)).astype(np.float32)
        tone *= env_adsr(n) * vel
        acid[start:start + n] += tone
        tbeat += dur
acid = np.tanh(np.nan_to_num(acid) * 1.5).astype(np.float32)
acid /= (np.max(np.abs(acid)) or 1.0) * 1.12

# Technique B: offbeat / afterbeat square bass (classic tribe)
offbeat = np.zeros(total, np.float32)
for bar in range(BARS):
    base = bar * 4
    for b in (0.5, 1.5, 2.5, 3.5):
        start = int((base + b) * (60.0 / BPM) * SR)
        n = int(0.22 * (60.0 / BPM) * SR)
        n = min(n, total - start)
        if n <= 0:
            continue
        freq = NOTE["C2"] if b in (0.5, 2.5) else NOTE["Eb2"]
        t = np.arange(n, dtype=np.float64) / SR
        sq = np.sign(np.sin(2 * math.pi * freq * t))
        # slight PWM morph
        pwm = 0.35 + 0.15 * np.sin(2 * math.pi * 2 * t)
        phase = (t * freq) % 1.0
        sq = np.where(phase < pwm, 1.0, -1.0)
        tone = one_pole_lp(sq.astype(np.float32), np.full(n, 380.0))
        tone = np.tanh(tone * 2.2).astype(np.float32) * env_adsr(n, a=0.001, d=0.03, s=0.25, r=0.05) * 0.85
        offbeat[start:start + n] += tone
offbeat /= (np.max(np.abs(offbeat)) or 1.0) * 1.15

for arr in (kick, snare, hats):
    arr /= (np.max(np.abs(arr)) or 1.0)
    arr *= 0.9

files = {
    "tribe_kick_013202.wav": kick,
    "tribe_snare_013202.wav": snare,
    "tribe_hats_013202.wav": hats,
    "tribe_acid_013202.wav": acid,
    "tribe_offbeat_013202.wav": offbeat,
}
for fname, audio in files.items():
    write_wav(OUT / fname, audio)
    print("wrote", fname)

def send(cmd, params=None, timeout=65.0):
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
    raise RuntimeError("no response")

def ok(r, label):
    if r.get("status") != "success":
        raise RuntimeError("%s: %s" % (label, r))
    print(label, "->", json.dumps(r.get("result"))[:240])
    return r["result"]

ok(send("set_tempo", {"tempo": BPM}), "tempo")
snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
by = {t["name"]: t["index"] for t in snap["tracks"]}
print("tracks", by)

for nm, idx in list(by.items()):
    try:
        ok(send("stop_clip", {"track_index": idx, "clip_index": 0}), "stop " + nm)
    except Exception as e:
        print("stop skip", nm, e)

# Map onto existing tracks by preference order
assignments = [
    (("Tribe Kick", "Kick ESX", "Tek Kick"), "Tribe Kick", "tribe_kick_013202.wav"),
    (("Tribe Snare", "Snare ESX"), "Tribe Snare", "tribe_snare_013202.wav"),
    (("Tribe Hats", "Hats ESX"), "Tribe Hats", "tribe_hats_013202.wav"),
    (("Tribe Acid", "Acid 303"), "Tribe Acid", "tribe_acid_013202.wav"),
    (("Offbeat Bass", "Sub Bass"), "Offbeat Bass", "tribe_offbeat_013202.wav"),
]

for candidates, new_name, fname in assignments:
    idx = None
    for c in candidates:
        if c in by:
            idx = by[c]
            break
    if idx is None:
        print("NO TRACK for", new_name, "candidates", candidates)
        continue
    path = OUT / fname
    try:
        ok(send("delete_clip", {"track_index": idx, "clip_index": 0}), "del " + new_name)
    except Exception as e:
        print("del skip", e)
    ok(send("set_track_name", {"track_index": idx, "name": new_name}), "rename " + new_name)
    ok(send("create_audio_clip", {"track_index": idx, "clip_index": 0, "path": str(path)}), "clip " + new_name)
    ok(send("set_clip_name", {"track_index": idx, "clip_index": 0, "name": path.stem}), "clipname " + new_name)
    ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), "fire " + new_name)

print("FINAL", json.dumps(ok(send("get_session_info"), "session"), indent=2))

