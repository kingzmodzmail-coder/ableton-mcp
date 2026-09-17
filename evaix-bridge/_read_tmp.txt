import wave, array, math, json, socket, subprocess
from pathlib import Path

SR = 44100
BPM = 165.0
BARS = 8
BEATS = BARS * 4
N = int(BEATS * 60.0 / BPM * SR)
FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set")
OUT.mkdir(parents=True, exist_ok=True)

def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nframes)
    data = array.array("h"); data.frombytes(raw)
    samples = [x / 32768.0 for x in data]
    if ch == 2:
        samples = [(samples[i] + samples[i+1]) * 0.5 for i in range(0, len(samples), 2)]
    if sr != SR:
        ratio = SR / sr
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
    thr = 0.008
    a = 0
    while a < len(samples) and abs(samples[a]) < thr:
        a += 1
    b = len(samples) - 1
    while b > a and abs(samples[b]) < thr:
        b -= 1
    return samples[a:b+1] if b > a else samples

def drive(samples, amt=1.5):
    return [math.tanh(x * amt) for x in samples]

def write_wav(path, mono):
    peak = max(1e-9, max(abs(x) for x in mono))
    scale = 0.9 / peak
    frames = array.array("h", [max(-32767, min(32767, int(x * scale * 32767))) for x in mono])
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(frames.tobytes())
    print("wrote", path.name)

def place(buf, sample, beat, gain=1.0):
    start = int(beat * 60.0 / BPM * SR)
    for i, v in enumerate(sample):
        j = start + i
        if 0 <= j < len(buf):
            buf[j] += v * gain

kick = drive(read_wav(FACTORY / "146_SinKick.wav"), 1.7)
bd = drive(read_wav(FACTORY / "000_BD-1.wav"), 1.2)
sd = drive(read_wav(FACTORY / "028_SD-8.wav"), 1.3)
hhc = read_wav(FACTORY / "054_HH-1C.wav")
hho = read_wav(FACTORY / "055_HH-1O.wav")
clank = read_wav(FACTORY / "092_JunkPerc.wav")
# atmosphere soft noise pad - keep VERY quiet if used; skip grainy for now

trk_k = [0.0] * N
trk_h = [0.0] * N
trk_oh = [0.0] * N
trk_c = [0.0] * N

for bar in range(BARS):
    base = bar * 4.0
    # PART 9 kick steps 1,5,9,13 = beats 0,1,2,3 ? vel 110,100,110,100
    for step, vel in [(0, 1.05), (1, 0.95), (2, 1.05), (3, 0.95)]:
        place(trk_k, kick, base + step, vel)
        place(trk_k, bd, base + step, 0.22 * vel)
    # PART 10 closed hats odd 16ths with 70/50 tribal
    # steps 1,3,5,7,9,11,13,15 = 16th indices 0,2,4,6,8,10,12,14
    for i, odd in enumerate(range(0, 16, 2)):
        vel = 0.70 if i % 2 == 0 else 0.50
        place(trk_h, hhc, base + odd * 0.25, vel)
    # PART 11 open hat 3,7,11,15 = 16th indices 2,6,10,14
    for odd in (2, 6, 10, 14):
        place(trk_oh, hho, base + odd * 0.25, 0.85)
    # PART 13 industrial clank steps 4, 12 = 16th indices 3, 11
    place(trk_c, clank, base + 3 * 0.25, 0.95)
    place(trk_c, clank, base + 11 * 0.25, 0.95)

write_wav(OUT / "pneu_kick_165.wav", trk_k)
write_wav(OUT / "pneu_hats_165.wav", trk_h)
write_wav(OUT / "pneu_ohat_165.wav", trk_oh)
write_wav(OUT / "pneu_clank_165.wav", trk_c)

# mix drums
mix = [0.0] * N
for buf, g in [(trk_k, 1.0), (trk_h, 0.55), (trk_oh, 0.5), (trk_c, 0.6)]:
    for i in range(N):
        mix[i] += buf[i] * g
mix = [math.tanh(x * 1.1) for x in mix]
write_wav(OUT / "pneu_drum_bus_165.wav", mix)

# Ableton
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

def ok(r, label):
    if r.get("status") != "success":
        print("FAIL", label, r)
        return None
    print(label)
    return r["result"]

snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
ok(send("set_tempo", {"tempo": BPM}), "tempo")

# stop non-acid first
for t in snap["tracks"]:
    for sl in (t.get("clip_slots") or []):
        if sl.get("has_clip"):
            send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})

by = {t["name"]: t["index"] for t in snap["tracks"]}

# Pneumatix acid MIDI ? A minor pattern from training
# Steps (1-indexed in doc): 1-A1, 3-A1(accent), 5-A2(slide), 7-E2(accent), 9-D2, 11-A1, 13-G1(slide+accent), 15-A1
# MIDI: A1=33, A2=45, E2=40, D2=38, G1=31
acid_steps = [
    # (sixteenth_index 0-based, pitch, velocity, duration_beats)
    (0, 33, 100, 0.35),
    (2, 33, 115, 0.35),
    (4, 45, 100, 0.55),  # slide feel = longer gate
    (6, 40, 115, 0.4),
    (8, 38, 95, 0.35),
    (10, 33, 100, 0.35),
    (12, 31, 120, 0.55),
    (14, 33, 100, 0.35),
]

# find/create Acid track
acid_idx = by.get("Acid 303 Poly")
if acid_idx is None:
    midi = [t for t in snap["tracks"] if t.get("is_midi_track")]
    acid_idx = midi[0]["index"] if midi else None
    if acid_idx is not None:
        send("set_track_name", {"track_index": acid_idx, "name": "Acid 303 Poly"})

if acid_idx is not None:
    send("delete_clip", {"track_index": acid_idx, "clip_index": 0})
    ok(send("create_clip", {"track_index": acid_idx, "clip_index": 0, "length": 4.0}), "acid clip 1bar*4? use 16 beats")
    # recreate length 16 beats = 4 bars
    send("delete_clip", {"track_index": acid_idx, "clip_index": 0})
    ok(send("create_clip", {"track_index": acid_idx, "clip_index": 0, "length": 16.0}), "acid 4 bars")
    send("set_clip_name", {"track_index": acid_idx, "clip_index": 0, "name": "Daciada_Roll_acid"})
    notes = []
    for bar in range(4):  # fill 4 bars of the 16-beat clip
        base = bar * 4.0
        for step, pitch, vel, dur in acid_steps:
            notes.append({
                "pitch": pitch,
                "start_time": base + step * 0.25,
                "duration": dur,
                "velocity": vel,
                "mute": False,
            })
    ok(send("add_notes_to_clip", {"track_index": acid_idx, "clip_index": 0, "notes": notes}), "acid notes")
    # ensure Drift loaded
    send("load_browser_item", {"track_index": acid_idx, "item_uri": "query:Synths#Drift"})

mapping = [
    ("E-Kick", "pneu_kick_165.wav"),
    ("E-Hats", "pneu_hats_165.wav"),
    ("E-Snare", "pneu_ohat_165.wav"),  # open hats on snare track slot
    ("E-Perc", "pneu_clank_165.wav"),
]
for name, wav in mapping:
    if name not in by:
        print("missing", name)
        continue
    idx = by[name]
    path = str(OUT / wav)
    send("delete_clip", {"track_index": idx, "clip_index": 0})
    ok(send("create_audio_clip", {"track_index": idx, "clip_index": 0, "path": path}), name)
    send("set_clip_name", {"track_index": idx, "clip_index": 0, "name": Path(wav).stem})
    ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), "fire " + name)

if acid_idx is not None:
    ok(send("fire_clip", {"track_index": acid_idx, "clip_index": 0}), "fire acid")

# rename snare track conceptually - optional
if "E-Snare" in by:
    send("set_track_name", {"track_index": by["E-Snare"], "name": "E-OHat"})

# bounce mp3
st_path = OUT / "pneu_drum_bus_165_st.wav"
with wave.open(str(OUT / "pneu_drum_bus_165.wav"), "rb") as w:
    raw = w.readframes(w.getnframes())
data = array.array("h"); data.frombytes(raw)
st = array.array("h")
for x in data:
    st.append(x); st.append(x)
with wave.open(str(st_path), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(st.tobytes())
mp3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_Pneumatix_Daciada_165.mp3")
subprocess.run(["ffmpeg", "-y", "-i", str(st_path), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3)], check=True, capture_output=True)
print("MP3", mp3)
print("DONE Pneumatix 165")
