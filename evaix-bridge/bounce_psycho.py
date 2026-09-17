import wave, array, struct, subprocess, json, socket
from pathlib import Path

SR = 44100
BPM = 155.0
# ~32 bars ~= 50 sec
BARS = 32
N = int(BARS * 4 * 60.0 / BPM * SR)
S = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set")
OUT_WAV = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set\psycho_bed_bounce.wav")
OUT_MP3 = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_Electribe_Psycho_bed_155.mp3")

layers = [
    ("e_kick_sinkick_only_155.wav", 1.0),
    ("e_hats_155.wav", 0.7),
    ("e_bass_155.wav", 0.85),
    ("e_synhit_155.wav", 0.65),
    ("esx_202_SynLP-4.wav", 0.55),
]

def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nframes)
    data = array.array("h"); data.frombytes(raw)
    samples = [x / 32768.0 for x in data]
    if ch == 2:
        # return stereo lists
        L = samples[0::2]; R = samples[1::2]
    else:
        L = samples; R = list(samples)
    if sr != SR:
        def rs(mono):
            ratio = SR / sr
            new_n = int(len(mono) * ratio)
            out = [0.0] * new_n
            for i in range(new_n):
                src = i / ratio
                j = int(src); f = src - j
                if j + 1 < len(mono):
                    out[i] = mono[j] * (1 - f) + mono[j + 1] * f
                elif j < len(mono):
                    out[i] = mono[j]
            return out
        L, R = rs(L), rs(R)
    return L, R

def tile(mono, n):
    if not mono:
        return [0.0] * n
    out = [0.0] * n
    i = 0
    while i < n:
        for v in mono:
            if i >= n:
                break
            out[i] = v
            i += 1
    return out

mixL = [0.0] * N
mixR = [0.0] * N
for name, gain in layers:
    path = S / name
    if not path.exists():
        # fallback kick
        alt = S / "e_kick_clean_esx_155.wav"
        if name.startswith("e_kick") and alt.exists():
            path = alt
        else:
            print("SKIP", name)
            continue
    L, R = read_wav(path)
    L = tile(L, N); R = tile(R, N)
    for i in range(N):
        mixL[i] += L[i] * gain
        mixR[i] += R[i] * gain
    print("layer", path.name, gain)

peak = max(1e-9, max(max(abs(x) for x in mixL), max(abs(x) for x in mixR)))
scale = 0.89 / peak
print("peak", peak, "scale", scale)

frames = array.array("h")
for i in range(N):
    frames.append(max(-32767, min(32767, int(mixL[i] * scale * 32767))))
    frames.append(max(-32767, min(32767, int(mixR[i] * scale * 32767))))

with wave.open(str(OUT_WAV), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(frames.tobytes())
print("WAV", OUT_WAV, "dur", round(N / SR, 1))

# mp3 via ffmpeg if available
ff = None
for c in ["ffmpeg", r"C:\ffmpeg\bin\ffmpeg.exe"]:
    try:
        subprocess.run([c, "-version"], capture_output=True, check=True)
        ff = c
        break
    except Exception:
        pass
if ff:
    subprocess.run([ff, "-y", "-i", str(OUT_WAV), "-codec:a", "libmp3lame", "-b:a", "192k", str(OUT_MP3)], check=True)
    print("MP3", OUT_MP3)
else:
    # copy wav to downloads as fallback
    import shutil
    fallback = Path(r"C:\Users\Gebruiker\Downloads\EvAIx_Electribe_Psycho_bed_155.wav")
    shutil.copy2(OUT_WAV, fallback)
    print("NO_FFMPEG wav->", fallback)
