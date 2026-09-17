import wave, array, json, socket
from pathlib import Path

SR_OUT = 44100
BPM = 155.0
BARS = 4
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR_OUT)
FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set")

def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    data = array.array("h"); data.frombytes(raw)
    samples = [x / 32768.0 for x in data]
    if ch == 2:
        samples = [(samples[i] + samples[i+1]) * 0.5 for i in range(0, len(samples), 2)]
    if sr != SR_OUT:
        ratio = SR_OUT / sr
        new_n = int(len(samples) * ratio)
        out = [0.0] * new_n
        for i in range(new_n):
            src = i / ratio
            j = int(src); f = src - j
            if j + 1 < len(samples):
                out[i] = samples[j] * (1 - f) + samples[j + 1] * f
            elif j < len(samples):
                out[i] = samples[j]
        samples = out
    return samples

def write_wav(path, mono):
    peak = max(1e-9, max(abs(x) for x in mono))
    scale = 0.92 / peak
    frames = array.array("h", [max(-32767, min(32767, int(x * scale * 32767))) for x in mono])
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR_OUT)
        w.writeframes(frames.tobytes())
    print("wrote", path, "peak", round(peak, 3))

def place(buf, sample, beat, gain=1.0):
    start = int(beat * 60.0 / BPM * SR_OUT)
    for i, v in enumerate(sample):
        j = start + i
        if j >= len(buf):
            break
        buf[j] += v * gain

# Clean ESX bass kick: SinKick sub + short clean BD click (BD-1)
sin_k = read_wav(FACTORY / "146_SinKick.wav")
bd = read_wav(FACTORY / "000_BD-1.wav")
# also try BD-4 as body if needed ? keep simple: sin dominant + light body
kick = [0.0] * N
for b in range(BEATS):
    # four on floor, slight accent on 1
    g = 1.0 if b % 4 == 0 else 0.92
    place(kick, sin_k, float(b), 1.05 * g)
    place(kick, bd, float(b), 0.45 * g)

out_path = OUT / "e_kick_clean_esx_155.wav"
write_wav(out_path, kick)

# Also write one-shot copy for reference
oneshot = [0.0] * max(len(sin_k), len(bd)) + [0.0] * int(0.05 * SR_OUT)
place(oneshot, sin_k, 0.0, 1.05)
place(oneshot, bd, 0.0, 0.45)
# place() uses beat time ? for oneshot buffer rebuild simply:
oneshot = [0.0] * (max(len(sin_k), len(bd)) + int(0.1 * SR_OUT))
for i, v in enumerate(sin_k):
    oneshot[i] += v * 1.05
for i, v in enumerate(bd):
    oneshot[i] += v * 0.45
write_wav(OUT / "e_kick_clean_esx_oneshot.wav", oneshot)

# Load into Ableton E-Kick
HOST, PORT = "127.0.0.1", 9877

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
    raise RuntimeError("bridge down")

def ok(r, label):
    if r.get("status") != "success":
        raise RuntimeError(label + ": " + str(r))
    print(label)
    return r["result"]

snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
by = {t["name"]: t["index"] for t in snap["tracks"]}
if "E-Kick" not in by:
    raise SystemExit("E-Kick track missing: " + str(sorted(by)))
idx = by["E-Kick"]
path = str(out_path)

# replace slot 0 and scene rows that use kick (2,3,4,6,7)
rows = [0, 2, 3, 4, 6, 7]
for row in rows:
    try:
        send("delete_clip", {"track_index": idx, "clip_index": row})
    except Exception:
        pass
    ok(send("create_audio_clip", {"track_index": idx, "clip_index": row, "path": path}), f"clip row{row}")
    name = "e_kick_clean_esx" if row == 0 else f"kick_s{row}"
    send("set_clip_name", {"track_index": idx, "clip_index": row, "name": name})

ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), "fire clean kick")
# keep psycho bed elements
for name in ("E-Hats", "E-Bass", "E-Syn", "E-Mental"):
    if name in by:
        send("fire_clip", {"track_index": by[name], "clip_index": 0})
print("DONE clean ESX bass kick")
