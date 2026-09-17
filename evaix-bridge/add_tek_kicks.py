import json, socket, wave
from pathlib import Path
import numpy as np

OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples")
KICKS = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\packs\insane-teknology-kicks-2") / "Insane Teknology Kicks 2"
BPM, BARS, SR = 148.0, 4, 44100
BEATS = BARS * 4
total = int(BEATS * (60.0 / BPM) * SR)
HOST, PORT = "127.0.0.1", 9877

def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, nframes, *_ = w.getparams()
        raw = w.readframes(nframes)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch == 2:
        data = data.reshape(-1, 2).mean(axis=1)
    if sr != SR:
        x = np.linspace(0, 1, len(data), endpoint=False)
        xi = np.linspace(0, 1, int(len(data) * SR / sr), endpoint=False)
        data = np.interp(xi, x, data).astype(np.float32)
    return data

def write_wav(path, mono):
    mono = np.clip(mono, -1, 1)
    stereo = np.column_stack([mono, mono])
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())

# Use a hard E kick + bass kick variant for drop bars
k1 = read_wav(KICKS / "1_KICK E01.wav")
k2 = read_wav(KICKS / "24_KICK BASS E01.wav")
k3 = read_wav(KICKS / "9_KICK F01.wav")

buf = np.zeros(total, dtype=np.float32)
def place(sample, beat, gain=1.0):
    start = int(beat * (60.0 / BPM) * SR)
    n = min(len(sample), total - start)
    if n > 0:
        buf[start:start+n] += sample[:n] * gain

for bar in range(BARS):
    base = bar * 4
    for b in (0, 1, 2, 3):
        sample = k2 if (bar >= 2 and b in (0, 2)) else k1
        place(sample, base + b, 0.95)
    if bar == 3:
        place(k3, base + 1.5, 0.55)
        place(k3, base + 3.5, 0.45)

peak = float(np.max(np.abs(buf))) or 1.0
buf = buf / peak * 0.9
path = OUT / "tek_kick_loop.wav"
write_wav(path, buf)
print("wrote", path)

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
        raise RuntimeError(f"{label}: {r}")
    print(label, "->", json.dumps(r.get("result"))[:350])
    return r["result"]

# stop old Kick ESX (index 6 from earlier) if still there
snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
kick_idx = None
for t in snap.get("tracks", []):
    if t.get("name") == "Kick ESX":
        kick_idx = t["index"]
        break
if kick_idx is not None:
    try:
        ok(send("stop_clip", {"track_index": kick_idx, "clip_index": 0}), "stop Kick ESX")
    except Exception as e:
        print("stop warn", e)

r = ok(send("create_audio_track", {"index": -1}), "create Tek Kick")
idx = r["index"]
ok(send("set_track_name", {"track_index": idx, "name": "Tek Kick"}), "name")
ok(send("create_audio_clip", {"track_index": idx, "clip_index": 0, "path": str(path)}), "clip")
ok(send("set_clip_name", {"track_index": idx, "clip_index": 0, "name": "tek_kick_loop"}), "clipname")
ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), "fire")
print("FINAL", json.dumps(ok(send("get_session_info"), "session"), indent=2))
