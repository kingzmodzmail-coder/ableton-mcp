import json, math, socket, wave
from pathlib import Path
import numpy as np

OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples")
BASE = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT.mkdir(parents=True, exist_ok=True)
BPM = 148.0
BARS = 4
BEATS = BARS * 4
SR = 44100
HOST, PORT = "127.0.0.1", 9877
total = int(BEATS * (60.0 / BPM) * SR)

NOTE = {
    "C2": 65.41, "D2": 73.42, "Eb2": 77.78, "F2": 87.31,
    "G2": 98.00, "Ab2": 103.83, "Bb2": 116.54, "C3": 130.81,
}

def saw(freq, n):
    t = (np.arange(n) / SR) * freq
    return 2.0 * (t - np.floor(t + 0.5))

def env_adsr(n, a=0.005, d=0.08, s=0.55, r=0.12):
    ea, ed, er = int(a*SR), int(d*SR), int(r*SR)
    es = max(0, n - ea - ed - er)
    parts = []
    if ea: parts.append(np.linspace(0, 1, ea, endpoint=False))
    if ed: parts.append(np.linspace(1, s, ed, endpoint=False))
    if es: parts.append(np.full(es, s))
    if er: parts.append(np.linspace(s, 0, er, endpoint=False))
    e = np.concatenate(parts) if parts else np.zeros(0)
    if len(e) < n:
        e = np.pad(e, (0, n-len(e)))
    return e[:n].astype(np.float32)

def soft_clip(x, drive=1.4):
    return np.tanh(x * drive).astype(np.float32)

def lowpass_resonant(x, cutoff_hz, q=8.0):
    y = np.zeros_like(x)
    lp = 0.0
    bp = 0.0
    for i, s in enumerate(x):
        f = 2.0 * math.sin(math.pi * min(float(cutoff_hz[i]), SR*0.45) / SR)
        hp = s - lp - q * bp
        bp = bp + f * hp
        lp = lp + f * bp
        y[i] = lp
    return y.astype(np.float32)

pattern = [
    ("C2", 0.0, 0.45, 0.9), ("C2", 0.5, 0.2, 0.55), ("Eb2", 1.0, 0.35, 0.85),
    ("C2", 1.5, 0.2, 0.5), ("F2", 2.0, 0.4, 0.9), ("Eb2", 2.5, 0.25, 0.6),
    ("G2", 3.0, 0.35, 0.8), ("Bb2", 3.5, 0.4, 0.85),
]
buf = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    base = bar * 4
    for name, off, dur, vel in pattern:
        nname = name
        if bar >= 2 and name == "G2":
            nname = "Ab2"
        if bar == 3 and off == 3.5:
            nname = "C3"
        start = int((base + off) * (60.0/BPM) * SR)
        n = int(dur * (60.0/BPM) * SR)
        if start >= total:
            continue
        n = min(n, total - start)
        freq = NOTE[nname]
        if dur >= 0.35:
            f0 = freq * (2 ** (-2/12))
            freqs = np.linspace(f0, freq, n)
            phase = np.cumsum(freqs / SR)
            osc = 2.0 * (phase - np.floor(phase + 0.5))
        else:
            osc = saw(freq, n)
        cut0 = 400 + vel * 900
        cut1 = 180 + (1-vel) * 200
        cutoff = np.linspace(cut0, cut1, n)
        if bar % 2 == 1:
            cutoff = cutoff * 1.25
        tone = lowpass_resonant(osc.astype(np.float32), cutoff, q=6.5 + vel*3)
        tone *= env_adsr(n, a=0.003, d=0.05, s=0.5, r=0.08) * vel
        buf[start:start+n] += tone

buf = soft_clip(buf, 1.6)
peak = float(np.max(np.abs(buf))) or 1.0
buf = buf / peak * 0.85

def write_wav(path, mono):
    mono = np.clip(mono, -1, 1)
    stereo = np.column_stack([mono, mono])
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())

acid_path = OUT / "acid_303.wav"
write_wav(acid_path, buf)
print("wrote", acid_path)

def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, nframes, *_ = w.getparams()
        raw = w.readframes(nframes)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch == 2:
        data = data.reshape(-1, 2).mean(axis=1)
    if sr != SR:
        x = np.linspace(0,1,len(data),endpoint=False)
        xi = np.linspace(0,1,int(len(data)*SR/sr),endpoint=False)
        data = np.interp(xi,x,data).astype(np.float32)
    return data

candidates = list(BASE.glob("*SyncBass*")) + list(BASE.glob("*NuBass*")) + list(BASE.glob("*OctBass*")) + list(BASE.glob("*RingBass*"))
print("bass oneshots", [p.name for p in candidates])
sub = np.zeros(total, dtype=np.float32)
if candidates:
    sample = read_wav(candidates[0])
    for bar in range(BARS):
        for beat in (0.0, 2.0):
            start = int((bar*4 + beat) * (60.0/BPM) * SR)
            n = min(len(sample), total-start)
            if n > 0:
                sub[start:start+n] += sample[:n] * 0.7
    peak = float(np.max(np.abs(sub))) or 1.0
    sub = sub/peak*0.8
    write_wav(OUT / "sub_bass.wav", sub)
    print("wrote sub_bass.wav")

def send(cmd, params=None, timeout=65.0):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall(payload)
        sock.settimeout(timeout)
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
    print(label, "->", json.dumps(r.get("result"))[:300])
    return r["result"]

for name, path in [("Acid 303", acid_path), ("Sub Bass", OUT/"sub_bass.wav")]:
    if not Path(path).exists():
        continue
    r = ok(send("create_audio_track", {"index": -1}), f"create {name}")
    idx = r["index"]
    ok(send("set_track_name", {"track_index": idx, "name": name}), f"name {name}")
    ok(send("create_audio_clip", {"track_index": idx, "clip_index": 0, "path": str(path)}), f"clip {name}")
    ok(send("set_clip_name", {"track_index": idx, "clip_index": 0, "name": Path(path).stem}), f"clipname {name}")
    ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), f"fire {name}")

print("SESSION", json.dumps(ok(send("get_session_info"), "session"), indent=2))
