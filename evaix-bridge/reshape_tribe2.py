import json, math, socket, wave
from pathlib import Path
import numpy as np

OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples")
KICKS = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\packs\insane-teknology-kicks-2") / "Insane Teknology Kicks 2"
ESX = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
BPM, BARS, SR = 175.0, 4, 44100
BEATS = BARS * 4
total = int(BEATS * (60.0 / BPM) * SR)
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
    mono = np.nan_to_num(mono, nan=0.0, posinf=0.0, neginf=0.0)
    mono = np.clip(mono, -1, 1)
    stereo = np.column_stack([mono, mono])
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())

def place(buf, sample, beat, gain=1.0):
    start = int(beat * (60.0 / BPM) * SR)
    n = min(len(sample), total - start)
    if n > 0:
        buf[start:start+n] += sample[:n] * gain

k_main = read_wav(KICKS / "24_KICK BASS E01.wav")
k_alt = read_wav(KICKS / "1_KICK E01.wav")
kick = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    base = bar * 4
    for b in range(4):
        place(kick, k_main if b % 2 == 0 else k_alt, base + b, 0.95)
    if bar >= 2:
        place(kick, k_alt, base + 0.5, 0.22)

snare_s = read_wav(ESX / "033_SD-13.wav")
clap_s = read_wav(ESX / "048_Clap-1.wav")
rim_s = read_wav(ESX / "045_Rim-1.wav")
snare = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    base = bar * 4
    place(snare, snare_s, base + 1, 0.75)
    place(snare, clap_s, base + 1, 0.35)
    place(snare, snare_s, base + 3, 0.8)
    place(snare, clap_s, base + 3, 0.4)
    if bar == 3:
        for off in (3.25, 3.5, 3.75):
            place(snare, rim_s, base + off, 0.5)

hhc = read_wav(ESX / "056_HH-2C.wav")
hho = read_wav(ESX / "057_HH-2O.wav")
hats = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    base = bar * 4
    for step in range(16):
        beat = base + step * 0.25
        g = 0.55 if step % 2 == 0 else 0.28
        place(hats, hhc, beat, g)
    place(hats, hho, base + 3.5, 0.45)

NOTE = {"C2":65.41,"Eb2":77.78,"F2":87.31,"G2":98.0,"Ab2":103.83,"Bb2":116.54,"C3":130.81}

def env_adsr(n, a=0.002, d=0.04, s=0.35, r=0.05):
    ea, ed, er = int(a*SR), int(d*SR), int(r*SR)
    es = max(0, n - ea - ed - er)
    parts = []
    if ea: parts.append(np.linspace(0,1,ea,endpoint=False))
    if ed: parts.append(np.linspace(1,s,ed,endpoint=False))
    if es: parts.append(np.full(es,s))
    if er: parts.append(np.linspace(s,0,er,endpoint=False))
    e = np.concatenate(parts) if parts else np.zeros(0)
    if len(e) < n: e = np.pad(e,(0,n-len(e)))
    return e[:n].astype(np.float32)

def one_pole_lp(x, cutoff_hz):
    y = np.zeros_like(x, dtype=np.float64)
    s = 0.0
    for i in range(len(x)):
        c = float(np.clip(cutoff_hz[i], 80.0, SR*0.4))
        a = math.exp(-2.0 * math.pi * c / SR)
        s = (1-a)*x[i] + a*s
        y[i] = s
    return y.astype(np.float32)

seq = [
    ("C2",0.25,0.9),("C2",0.25,0.5),("Eb2",0.25,0.85),("C2",0.25,0.45),
    ("F2",0.25,0.9),("Eb2",0.25,0.55),("G2",0.25,0.8),("Bb2",0.25,0.7),
    ("C2",0.25,0.9),("Ab2",0.25,0.6),("G2",0.25,0.75),("F2",0.25,0.5),
    ("Eb2",0.25,0.85),("C2",0.25,0.55),("Bb2",0.35,0.9),("C3",0.4,0.95),
]
acid = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    tbeat = float(bar * 4)
    for name, dur, vel in seq:
        start = int(tbeat * (60.0/BPM) * SR)
        n = min(int(dur * (60.0/BPM) * SR), total-start)
        if n <= 0: break
        freq = NOTE[name]
        t = np.arange(n, dtype=np.float64) / SR
        if vel > 0.85:
            freqs = np.linspace(freq*(2**(-1/12)), freq, n)
            phase = np.cumsum(freqs/SR)
            osc = 2.0*(phase-np.floor(phase+0.5))
        else:
            osc = 2.0*((t*freq) - np.floor(t*freq + 0.5))
        cut0 = 600 + vel*1200
        cut1 = 250 + (1-vel)*150
        if bar % 2: cut0 *= 1.1
        cutoff = np.linspace(cut0, cut1, n)
        tone = one_pole_lp(osc.astype(np.float32), cutoff)
        # cheap resonance: blend lightly with bandpass-ish difference
        tone = tone + 0.35*(osc.astype(np.float32)-tone)
        tone = np.tanh(tone * (1.2+vel)).astype(np.float32)
        tone *= env_adsr(n) * vel
        acid[start:start+n] += tone
        tbeat += dur

acid = np.tanh(np.nan_to_num(acid)*1.5).astype(np.float32)
acid /= (np.max(np.abs(acid)) or 1) * 1.12

for arr in (kick, snare, hats):
    peak = float(np.max(np.abs(arr))) or 1.0
    arr /= peak; arr *= 0.9

mapping = {
    "Kick ESX": ("Tribe Kick", kick, "tribe_kick.wav"),
    "Snare ESX": ("Tribe Snare", snare, "tribe_snare.wav"),
    "Hats ESX": ("Tribe Hats", hats, "tribe_hats.wav"),
    "Acid 303": ("Tribe Acid", acid, "tribe_acid.wav"),
}
for _, audio, fname in mapping.values():
    write_wav(OUT/fname, audio)
    print("wrote", fname)

def send(cmd, params=None, timeout=65.0):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall(payload); sock.settimeout(timeout)
        chunks=[]
        while True:
            chunk=sock.recv(8192)
            if not chunk: break
            chunks.append(chunk)
            try: return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError: continue
    raise RuntimeError("no response")

def ok(r, label):
    if r.get("status")!="success":
        raise RuntimeError(f"{label}: {r}")
    print(label, "->", json.dumps(r.get("result"))[:260])
    return r["result"]

ok(send("set_tempo", {"tempo": BPM}), "tempo")
snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
by_name = {t["name"]: t["index"] for t in snap["tracks"]}
print("tracks", by_name)

# stop everything
for nm, idx in by_name.items():
    try: ok(send("stop_clip", {"track_index": idx, "clip_index": 0}), f"stop {nm}")
    except Exception as e: print("stop skip", nm, e)

# also stop tribe kick/snare if created earlier
for nm in ("Tribe Kick", "Tribe Snare"):
    if nm in by_name:
        try: ok(send("stop_clip", {"track_index": by_name[nm], "clip_index": 0}), f"stop {nm}")
        except Exception: pass

for old, (new_name, audio, fname) in mapping.items():
    path = OUT/fname
    if old not in by_name:
        print("MISSING", old); continue
    idx = by_name[old]
    try: ok(send("delete_clip", {"track_index": idx, "clip_index": 0}), f"del {old}")
    except Exception as e: print("del skip", e)
    ok(send("set_track_name", {"track_index": idx, "name": new_name}), f"rename {new_name}")
    ok(send("create_audio_clip", {"track_index": idx, "clip_index": 0, "path": str(path)}), f"clip {new_name}")
    ok(send("set_clip_name", {"track_index": idx, "clip_index": 0, "name": path.stem}), f"clipname {new_name}")
    ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), f"fire {new_name}")

# if Tribe Kick/Snare from partial run exist, fire those instead of duplicates
# mute/stop Tek Kick Sub Bass etc already stopped

print("FINAL", json.dumps(ok(send("get_session_info"), "session"), indent=2))
