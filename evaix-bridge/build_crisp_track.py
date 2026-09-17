import json, math, os, socket, struct, wave
from pathlib import Path
import numpy as np

BASE = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples")
OUT.mkdir(parents=True, exist_ok=True)
BPM = 148.0
BARS = 4
BEATS = BARS * 4
SR = 44100
HOST, PORT = "127.0.0.1", 9877

def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n, *_ = w.getparams()
        raw = w.readframes(n)
    if sw == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        raise ValueError(f"unsupported width {sw} in {path}")
    if ch == 2:
        data = data.reshape(-1, 2).mean(axis=1)
    if sr != SR:
        # linear resample
        x = np.linspace(0, 1, num=len(data), endpoint=False)
        new_len = int(len(data) * SR / sr)
        xi = np.linspace(0, 1, num=new_len, endpoint=False)
        data = np.interp(xi, x, data).astype(np.float32)
    return data

def write_wav(path: Path, mono: np.ndarray):
    mono = np.clip(mono, -1.0, 1.0)
    stereo = np.column_stack([mono, mono]).astype(np.float32)
    pcm = (stereo * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

def place(buf: np.ndarray, sample: np.ndarray, beat: float, gain=1.0):
    start = int(beat * (60.0 / BPM) * SR)
    end = min(len(buf), start + len(sample))
    n = end - start
    if n <= 0:
        return
    buf[start:end] += sample[:n] * gain

total = int(BEATS * (60.0 / BPM) * SR)

kick = read_wav(BASE / "001_BD-2.wav")
snare = read_wav(BASE / "024_SD-4.wav")
hhc = read_wav(BASE / "054_HH-1C.wav")
hho = read_wav(BASE / "055_HH-1O.wav")
clap = read_wav(BASE / "048_Clap-1.wav")
rim = read_wav(BASE / "045_Rim-1.wav")

# Kick pattern: four-on-floor + ghost on & of 3 in bars 2/4
kick_buf = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    base = bar * 4
    for b in (0, 1, 2, 3):
        place(kick_buf, kick, base + b, 0.95)
    if bar % 2 == 1:
        place(kick_buf, kick, base + 2.5, 0.45)

# Snare: 2 and 4 + light clap layer
snare_buf = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    base = bar * 4
    place(snare_buf, snare, base + 1, 0.9)
    place(snare_buf, snare, base + 3, 0.9)
    place(snare_buf, clap, base + 3, 0.35)
    if bar == 3:
        place(snare_buf, rim, base + 3.5, 0.55)
        place(snare_buf, rim, base + 3.75, 0.4)

# Hats: 8ths closed, open on last bar offbeats
hat_buf = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    base = bar * 4
    for step in range(8):
        beat = base + step * 0.5
        if bar == 3 and step % 2 == 1:
            place(hat_buf, hho, beat, 0.55)
        else:
            g = 0.7 if step % 2 == 0 else 0.45
            place(hat_buf, hhc, beat, g)

# Full mix bus bounce
mix = kick_buf * 0.9 + snare_buf * 0.85 + hat_buf * 0.7
peak = float(np.max(np.abs(mix))) or 1.0
mix = mix / peak * 0.89

paths = {
    "kick_loop.wav": kick_buf / (np.max(np.abs(kick_buf)) or 1) * 0.9,
    "snare_loop.wav": snare_buf / (np.max(np.abs(snare_buf)) or 1) * 0.9,
    "hats_loop.wav": hat_buf / (np.max(np.abs(hat_buf)) or 1) * 0.9,
    "drum_mix.wav": mix,
}
for name, audio in paths.items():
    write_wav(OUT / name, audio)
    print("wrote", OUT / name, "samples", len(audio))

# copy electribe preview as texture bed
import shutil
preview = Path(r"C:\Users\Gebruiker\Downloads\B9pzyxsOhOLtNutE-grok-workspace\artifacts\electribe-kit\demos\esx_preview.wav")
if preview.exists():
    shutil.copy2(preview, OUT / "electribe_bed.wav")
    print("copied electribe_bed.wav")

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

def ok(resp, label):
    if resp.get("status") != "success":
        raise RuntimeError(f"{label}: {resp}")
    print(label, "->", json.dumps(resp.get("result"), indent=2)[:500])
    return resp["result"]

ok(send("set_tempo", {"tempo": BPM}), "set_tempo")

# Create audio tracks and load loops
tracks = [
    ("Kick ESX", OUT / "kick_loop.wav"),
    ("Snare ESX", OUT / "snare_loop.wav"),
    ("Hats ESX", OUT / "hats_loop.wav"),
    ("Drum Mix", OUT / "drum_mix.wav"),
]
if (OUT / "electribe_bed.wav").exists():
    tracks.append(("Electribe Bed", OUT / "electribe_bed.wav"))

created = []
for name, path in tracks:
    r = ok(send("create_audio_track", {"index": -1}), f"create {name}")
    idx = r["index"]
    ok(send("set_track_name", {"track_index": idx, "name": name}), f"name {name}")
    ok(send("create_audio_clip", {
        "track_index": idx,
        "clip_index": 0,
        "path": str(path),
    }, timeout=65), f"clip {name}")
    ok(send("set_clip_name", {
        "track_index": idx,
        "clip_index": 0,
        "name": path.stem,
    }), f"clipname {name}")
    created.append(idx)

# Fire first three (kick/snare/hats) — mute mix to avoid double
# Lower drum mix volume if present
info = ok(send("get_session_info"), "session")
# fire kick snare hats
for idx in created[:3]:
    ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), f"fire {idx}")

# mute Drum Mix and Electribe bed initially so layered drums are clean; leave bed for user
for i, name in enumerate([t[0] for t in tracks]):
    if name in ("Drum Mix", "Electribe Bed"):
        # no mute command — skip fire for those
        pass

print("DONE tracks", created)
print(json.dumps(ok(send("get_session_info"), "final"), indent=2))
