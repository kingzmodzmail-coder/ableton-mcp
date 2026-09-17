import wave, array, subprocess
from pathlib import Path

SR = 44100
BPM = 155.0
FACTORY = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
OUTDIR = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set")
OUTDIR.mkdir(parents=True, exist_ok=True)

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
    # trim silence edges lightly
    thr = 0.01
    a = 0
    while a < len(samples) and abs(samples[a]) < thr:
        a += 1
    b = len(samples) - 1
    while b > a and abs(samples[b]) < thr:
        b -= 1
    return samples[a:b+1] if b > a else samples

def write_wav(path, mono):
    peak = max(1e-9, max(abs(x) for x in mono))
    scale = 0.9 / peak
    frames = array.array("h", [max(-32767, min(32767, int(x * scale * 32767))) for x in mono])
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(frames.tobytes())
    print("wrote", path.name, "dur", round(len(mono)/SR, 2), "peak", round(peak, 3))

def place(buf, sample, beat, gain=1.0):
    start = int(beat * 60.0 / BPM * SR)
    for i, v in enumerate(sample):
        j = start + i
        if 0 <= j < len(buf):
            buf[j] += v * gain

# Clean ESX one-shots
kick = read_wav(FACTORY / "146_SinKick.wav")
sd = read_wav(FACTORY / "028_SD-8.wav")
hhc = read_wav(FACTORY / "054_HH-1C.wav")
hho = read_wav(FACTORY / "055_HH-1O.wav")
bass = read_wav(FACTORY / "148_OctBass.wav")  # short clean bass
# fallback bass
if len(bass) < 10:
    bass = read_wav(FACTORY / "150_RingBass.wav")
syn = read_wav(FACTORY / "159_SynHit-1.wav")  # clean syn hit, not long noisy LP

# 64 bars arrangement with BUILD
# 0-8 intro hats only
# 8-16 + kick
# 16-24 + bass
# 24-32 + snare
# 32-48 + syn full
# 48-56 break hats+syn
# 56-64 full drop
TOTAL_BARS = 64
N = int(TOTAL_BARS * 4 * 60.0 / BPM * SR)

trk_kick = [0.0] * N
trk_snare = [0.0] * N
trk_hats = [0.0] * N
trk_bass = [0.0] * N
trk_syn = [0.0] * N

def in_range(bar, a, b):
    return a <= bar < b

for bar in range(TOTAL_BARS):
    base = bar * 4.0
    # hats always except maybe silence at end - 16ths
    if bar < 64:
        for i in range(16):
            beat = base + i * 0.25
            g = 0.5 if i % 2 == 0 else 0.32
            if in_range(bar, 48, 56):
                g *= 0.7  # quieter in break
            sample = hho if i % 4 == 2 else hhc
            place(trk_hats, sample, beat, g)

    # kick from bar 8, out in break 48-56, back 56-64
    if in_range(bar, 8, 48) or in_range(bar, 56, 64):
        for step in range(4):
            accent = 1.0 if step == 0 else 0.88
            place(trk_kick, kick, base + step, accent)

    # bass from bar 16 (with kick), out in break
    if in_range(bar, 16, 48) or in_range(bar, 56, 64):
        # offbeat + downbeat pulse (tekno-ish but clean)
        for step, g in [(0, 0.95), (1.5, 0.55), (2, 0.75), (3.5, 0.45)]:
            place(trk_bass, bass, base + step, g)

    # snare from bar 24
    if in_range(bar, 24, 48) or in_range(bar, 56, 64):
        place(trk_snare, sd, base + 2.0, 0.9)

    # syn stabs from bar 32, keep in break softer, full in drop
    if in_range(bar, 32, 48) or in_range(bar, 56, 64):
        place(trk_syn, syn, base + 0.0, 0.75)
        place(trk_syn, syn, base + 1.5, 0.4)
    elif in_range(bar, 48, 56):
        place(trk_syn, syn, base + 0.0, 0.45)

# write stems
stems = {
    "clean_kick.wav": trk_kick,
    "clean_snare.wav": trk_snare,
    "clean_hats.wav": trk_hats,
    "clean_bass.wav": trk_bass,
    "clean_syn.wav": trk_syn,
}
for name, buf in stems.items():
    write_wav(OUTDIR / name, buf)

# stereo master mix with section gains already in programming
mixL = [0.0] * N
mixR = [0.0] * N
gains = [
    (trk_kick, 1.05),
    (trk_snare, 0.85),
    (trk_hats, 0.55),
    (trk_bass, 0.9),
    (trk_syn, 0.7),
]
for buf, g in gains:
    for i in range(N):
        v = buf[i] * g
        mixL[i] += v
        mixR[i] += v * 0.98  # slight mono-ish clean

peak = max(1e-9, max(max(abs(x) for x in mixL), max(abs(x) for x in mixR)))
scale = 0.88 / peak
print("mix peak", peak)

frames = array.array("h")
for i in range(N):
    frames.append(max(-32767, min(32767, int(mixL[i] * scale * 32767))))
    frames.append(max(-32767, min(32767, int(mixR[i] * scale * 32767))))

wav_path = OUTDIR / "clean_esx_build_155.wav"
with wave.open(str(wav_path), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(frames.tobytes())
print("WAV", wav_path, "dur", round(N/SR, 1))

mp3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_ESX_clean_build_155.mp3")
subprocess.run(["ffmpeg", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3)], check=True, capture_output=True)
print("MP3", mp3)
print("DONE")
