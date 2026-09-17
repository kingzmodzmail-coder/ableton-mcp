import math, json, subprocess
from pathlib import Path
import numpy as np

mp3 = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\figment-162\EvAIx_Figment_162_v2.mp3")
raw = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\figment-162\_analyze.f32")
subprocess.run(["ffmpeg","-y","-i",str(mp3),"-ac","1","-ar","48000","-f","f32le",str(raw)], check=True, capture_output=True)
x = np.fromfile(raw, dtype=np.float32).astype(np.float64)
sr = 48000.0

def band_energy_db(seg, lo, hi):
    n = len(seg)
    if n < 64: return -120.0
    bs = min(n, 48000)
    vals = []
    step = max(1, bs // 2)
    for i0 in range(0, max(1, n - bs // 2), step):
        chunk = seg[i0:i0+bs]
        if len(chunk) < max(64, bs // 2): break
        win = np.hanning(len(chunk))
        spec = np.fft.rfft(chunk * win)
        freqs = np.fft.rfftfreq(len(chunk), 1.0/sr)
        mag2 = np.abs(spec)**2
        mask = (freqs >= lo) & (freqs < hi)
        vals.append(float(np.sum(mag2[mask])) + 1e-20)
    e = float(np.mean(vals)) if vals else 1e-20
    return 10.0 * math.log10(e)

def section(t0,t1):
    return x[int(t0*sr):int(t1*sr)]

def rel(seg):
    full = band_energy_db(seg, 20, 12000)
    mid = band_energy_db(seg, 700, 3000)
    low = band_energy_db(seg, 30, 200)
    harsh = band_energy_db(seg, 3000, 6000)
    return mid-full, low-full, harsh-full, mid

mute = section(240, 280)
opn = section(280, 339)
mr, ml, mh, madd = rel(mute)
or_, ol, oh, oadd = rel(opn)
out = {
  "mute_mid_rel": round(mr,2),
  "open_mid_rel": round(or_,2),
  "delta_open_minus_mute": round(or_-mr,2),
  "mute_low_rel": round(ml,2),
  "open_low_rel": round(ol,2),
  "mute_harsh_rel": round(mh,2),
  "open_harsh_rel": round(oh,2),
  "mute_abs": round(madd,2),
  "open_abs": round(oadd,2),
  "abs_mid_rise_db": round(oadd - madd, 2),
  "I": -9.1, "TP": -1.2, "LRA": 3.5,
  "qc_v1_mute_mid_rel": -5.9,
  "qc_v1_open_mid_rel": -8.9,
}
print(json.dumps(out, indent=2))
Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\figment-162\_mid_bloom.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
