import json, math, socket, wave
from pathlib import Path
import numpy as np

OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples")
KICKS = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\packs\insane-teknology-kicks-2") / "Insane Teknology Kicks 2"
ESX = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUT.mkdir(parents=True, exist_ok=True)

BPM = 175.0  # classic tribe / french tekno zone
BARS = 4
BEATS = BARS * 4
SR = 44100
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

def place(buf, sample, beat, gain=1.0):
    start = int(beat * (60.0 / BPM) * SR)
    n = min(len(sample), total - start)
    if n > 0:
        buf[start:start+n] += sample[:n] * gain

# --- rolling tek kicks (4-on-floor + light offbeat ghost in later bars)
k_main = read_wav(KICKS / "24_KICK BASS E01.wav")
k_alt = read_wav(KICKS / "1_KICK E01.wav")
kick = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    base = bar * 4
    for b in range(4):
        place(kick, k_main if b % 2 == 0 else k_alt, base + b, 0.95)
    if bar >= 2:
        place(kick, k_alt, base + 0.5, 0.25)
        place(kick, k_alt, base + 2.5, 0.2)

# --- snare/clap: sparse tribe style (2+4) + tribal rim fills
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

# --- tribal hats: 16ths with shuffle feel
hhc = read_wav(ESX / "056_HH-2C.wav")
hho = read_wav(ESX / "057_HH-2O.wav")
shaker = None
for p in ESX.glob("*Shaker*"):
    shaker = read_wav(p); break
hats = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    base = bar * 4
    for step in range(16):
        beat = base + step * 0.25
        # shuffle: delay odd 16ths slightly via quieter early placement feel
        g = 0.55 if step % 2 == 0 else 0.28
        if step % 4 == 2:
            g = 0.4
        place(hats, hhc, beat, g)
    place(hats, hho, base + 3.5, 0.45)
    if shaker is not None:
        for step in (1, 3, 5, 7):
            place(hats, shaker, base + step * 0.5, 0.25)

# --- dark acid 303 (more resonant, faster 16ths)
NOTE = {"C2":65.41,"D2":73.42,"Eb2":77.78,"E2":82.41,"F2":87.31,"G2":98.0,"Ab2":103.83,"Bb2":116.54,"C3":130.81}

def saw(freq, n):
    t = (np.arange(n) / SR) * freq
    return 2.0 * (t - np.floor(t + 0.5))

def env_adsr(n, a=0.002, d=0.04, s=0.4, r=0.06):
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

def lowpass_resonant(x, cutoff_hz, q=10.0):
    y = np.zeros_like(x); lp=0.0; bp=0.0
    for i,s in enumerate(x):
        f = 2.0 * math.sin(math.pi * min(float(cutoff_hz[i]), SR*0.42) / SR)
        hp = s - lp - q*bp
        bp = bp + f*hp
        lp = lp + f*bp
        y[i] = lp
    return y.astype(np.float32)

# classic rolling 16th acid
seq = [
    ("C2",0.25,0.9),("C2",0.25,0.5),("Eb2",0.25,0.85),("C2",0.25,0.45),
    ("F2",0.25,0.9),("Eb2",0.25,0.55),("G2",0.25,0.8),("Bb2",0.25,0.7),
    ("C2",0.25,0.9),("Ab2",0.25,0.6),("G2",0.25,0.75),("F2",0.25,0.5),
    ("Eb2",0.25,0.85),("C2",0.25,0.55),("Bb2",0.35,0.9),("C3",0.4,0.95),
]
acid = np.zeros(total, dtype=np.float32)
for bar in range(BARS):
    tbeat = bar * 4.0
    for name, dur, vel in seq:
        start = int(tbeat * (60.0/BPM) * SR)
        n = int(dur * (60.0/BPM) * SR)
        n = min(n, total-start)
        if n <= 0: break
        freq = NOTE[name]
        # accent slides
        if vel > 0.85:
            freqs = np.linspace(freq*(2**(-1/12)), freq, n)
            phase = np.cumsum(freqs/SR)
            osc = 2.0*(phase-np.floor(phase+0.5))
        else:
            osc = saw(freq, n)
        cut0 = 500 + vel*1400
        cut1 = 220 + (1-vel)*180
        if bar % 2: cut0 *= 1.15
        cutoff = np.linspace(cut0, cut1, n)
        tone = lowpass_resonant(osc.astype(np.float32), cutoff, q=8+vel*5)
        tone *= env_adsr(n) * vel
        acid[start:start+n] += tone
        tbeat += dur

acid = np.tanh(acid*1.8).astype(np.float32)
acid /= (np.max(np.abs(acid)) or 1) * 1.1

# normalize drums
for arr in (kick, snare, hats):
    peak = float(np.max(np.abs(arr))) or 1.0
    arr /= peak
    arr *= 0.9

paths = {
    "tribe_kick.wav": kick,
    "tribe_snare.wav": snare,
    "tribe_hats.wav": hats,
    "tribe_acid.wav": acid,
}
for name, audio in paths.items():
    write_wav(OUT/name, audio)
    print("wrote", name)

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
    print(label, "->", json.dumps(r.get("result"))[:280])
    return r["result"]

ok(send("stop_playback"), "stop")
ok(send("set_tempo", {"tempo": BPM}), "tempo")

# stop currently firing clips we know by name
snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
name_to_idx = {t["name"]: t["index"] for t in snap.get("tracks", [])}
for nm in list(name_to_idx):
    try:
        ok(send("stop_clip", {"track_index": name_to_idx[nm], "clip_index": 0}), f"stop {nm}")
    except Exception as e:
        print("skip stop", nm, e)

# create / reuse tribe tracks
tribe = [
    ("Tribe Kick", OUT/"tribe_kick.wav"),
    ("Tribe Snare", OUT/"tribe_snare.wav"),
    ("Tribe Hats", OUT/"tribe_hats.wav"),
    ("Tribe Acid", OUT/"tribe_acid.wav"),
]
for name, path in tribe:
    if name in name_to_idx:
        idx = name_to_idx[name]
        # delete old clip if any then recreate — delete_clip then create
        try:
            ok(send("delete_clip", {"track_index": idx, "clip_index": 0}), f"del {name}")
        except Exception as e:
            print("del skip", e)
    else:
        r = ok(send("create_audio_track", {"index": -1}), f"create {name}")
        idx = r["index"]
        ok(send("set_track_name", {"track_index": idx, "name": name}), f"name {name}")
    ok(send("create_audio_clip", {"track_index": idx, "clip_index": 0, "path": str(path)}), f"clip {name}")
    ok(send("set_clip_name", {"track_index": idx, "clip_index": 0, "name": path.stem}), f"clipname {name}")
    ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), f"fire {name}")

print("FINAL", json.dumps(ok(send("get_session_info"), "session"), indent=2))
