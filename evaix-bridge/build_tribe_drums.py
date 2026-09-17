import wave, array, math, json, socket, subprocess
from pathlib import Path

SR = 44100
BPM = 158.0
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

def drive(samples, amt=1.6):
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

kick = drive(read_wav(FACTORY / "146_SinKick.wav"), 1.8)
# add tiny body click from clean BD, low
bd = drive(read_wav(FACTORY / "000_BD-1.wav"), 1.2)
sd = drive(read_wav(FACTORY / "028_SD-8.wav"), 1.4)
hhc = read_wav(FACTORY / "054_HH-1C.wav")
hho = read_wav(FACTORY / "055_HH-1O.wav")
clap = read_wav(FACTORY / "048_Clap-1.wav")
clank = read_wav(FACTORY / "092_JunkPerc.wav")
tom = read_wav(FACTORY / "076_Tom-1.wav")
synperc = read_wav(FACTORY / "095_SynPerc.wav")

trk_k = [0.0] * N
trk_s = [0.0] * N
trk_h = [0.0] * N
trk_c = [0.0] * N  # clanks/toms tribe

for bar in range(BARS):
    base = bar * 4.0
    # kick snoeihard on grid
    for step in range(4):
        g = 1.05 if step == 0 else 0.95
        place(trk_k, kick, base + step, g)
        place(trk_k, bd, base + step, 0.25 * g)
    # snare 2 and 4
    place(trk_s, sd, base + 2.0, 0.95)
    place(trk_s, clap, base + 2.0, 0.25)
    # hats 16th variable velocity swing
    vels = [0.55, 0.28, 0.42, 0.22, 0.58, 0.3, 0.4, 0.25, 0.52, 0.28, 0.45, 0.2, 0.6, 0.32, 0.38, 0.24]
    for i, vel in enumerate(vels):
        sample = hho if i % 4 == 2 else hhc
        place(trk_h, sample, base + i * 0.25, vel)
    # industrial clanks + tribal toms offbeat
    place(trk_c, clank, base + 0.75, 0.55)
    place(trk_c, tom, base + 1.5, 0.5)
    place(trk_c, synperc, base + 2.75, 0.45)
    place(trk_c, clank, base + 3.25, 0.4)
    if bar % 2 == 1:
        place(trk_c, tom, base + 3.5, 0.35)

write_wav(OUT / "tribe_kick_158.wav", trk_k)
write_wav(OUT / "tribe_snare_158.wav", trk_s)
write_wav(OUT / "tribe_hats_158.wav", trk_h)
write_wav(OUT / "tribe_clank_158.wav", trk_c)

# mix preview with light glue (sum + soft clip)
mix = [0.0] * N
for buf, g in [(trk_k, 1.0), (trk_s, 0.85), (trk_h, 0.5), (trk_c, 0.55)]:
    for i in range(N):
        mix[i] += buf[i] * g
mix = [math.tanh(x * 1.15) for x in mix]
write_wav(OUT / "tribe_drum_bus_158.wav", mix)

# Ableton load
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
by = {t["name"]: t["index"] for t in snap["tracks"]}

# stop noisy leftover
for t in snap["tracks"]:
    for sl in (t.get("clip_slots") or []):
        if sl.get("has_clip") and t["name"] not in ("Acid 303 Poly",):
            send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})

mapping = [
    ("E-Kick", "tribe_kick_158.wav"),
    ("E-Snare", "tribe_snare_158.wav"),
    ("E-Hats", "tribe_hats_158.wav"),
    ("E-Perc", "tribe_clank_158.wav"),
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

# ensure acid playing
if "Acid 303 Poly" in by:
    ok(send("fire_clip", {"track_index": by["Acid 303 Poly"], "clip_index": 0}), "fire acid")

# try Drum Rack on free MIDI for future
midi = [t for t in snap["tracks"] if t.get("is_midi_track") and t["name"] != "Acid 303 Poly"]
if midi:
    midx = midi[0]["index"]
    send("set_track_name", {"track_index": midx, "name": "ESX Drum Rack"})
    r = send("load_browser_item", {"track_index": midx, "item_uri": "query:Synths#Drum%20Rack"})
    print("drumrack", r.get("status"), r.get("result") or r.get("message"))

# bounce mp3 of drums+ try get notes from acid - just drum bus for now + we'll mix without acid audio
mp3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_ESX_tribe_bed_158.mp3")
wav = OUT / "tribe_drum_bus_158.wav"
# stereo-ize
import array as arr
mono = read_wav(wav) if False else None
# read the bus we wrote
with wave.open(str(OUT / "tribe_drum_bus_158.wav"), "rb") as w:
    raw = w.readframes(w.getnframes())
data = array.array("h"); data.frombytes(raw)
# already mono int16 - make stereo file for ffmpeg
stereo_path = OUT / "tribe_drum_bus_158_st.wav"
st = array.array("h")
for x in data:
    st.append(x); st.append(x)
with wave.open(str(stereo_path), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(st.tobytes())
subprocess.run(["ffmpeg", "-y", "-i", str(stereo_path), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3)], check=True, capture_output=True)
print("MP3", mp3)
print("DONE")
