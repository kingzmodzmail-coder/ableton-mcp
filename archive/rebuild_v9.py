"""Rebuild seeds 307/308 sections from raw model output with proper gain.

The first pass clamped gain at 2.0 so those sections sit ~4 dB below the
approved context, and seed 308 peaks at full scale. Re-derive from
"Raw codec output.wav" (pre-gain): tail 589 frames = generated audio.
"""
import json, os, shutil, subprocess
import numpy as np, soundfile as sf, librosa

PROJ = r"C:\Users\Gebruiker\ableton-mcp\.producer\projects\how-about-everyone-else"
V8 = os.path.join(PROJ, "dry-next-v8")
V9 = os.path.join(PROJ, "dry-next-v9")
SR_MODEL, SR_OUT = 32000, 44100
FRAMES = 589
SPLICE = 47.11927437641723
FADE_MS = 2.0

approved, sr = sf.read(os.path.join(V8, "Dry approved passage plus next eight bars.wav"), dtype="float64")
assert sr == SR_OUT
ctxm = sf.read(os.path.join(V8, "New eight bars only.wav"), dtype="float64")[0].mean(axis=1)
target = float(np.sqrt(np.mean(ctxm ** 2)))
i0 = int(round(SPLICE * SR_OUT))
F = int(round(FADE_MS / 1000 * SR_OUT))

for seed in (307, 308):
    d = os.path.join(V9, f"seed-{seed}")
    raw = sf.read(os.path.join(d, "Raw codec output.wav"), dtype="float64")[0]
    tail = raw[-FRAMES * 640:]
    clip_raw = float(np.mean(np.abs(tail) >= 0.999))
    g = target / float(np.sqrt(np.mean(tail ** 2)))
    gen32 = tail * g
    if np.max(np.abs(gen32)) > 0.98:
        gen32 *= 0.98 / np.max(np.abs(gen32))
    gen441 = librosa.resample(gen32, orig_sr=SR_MODEL, target_sr=SR_OUT)
    gen441 = np.repeat(gen441[:, None], 2, axis=1)
    fade = np.linspace(0, 1, F) ** 0.5
    gen441[:F] *= fade[:, None]
    gen441[-F:] *= fade[::-1][:, None]
    preview = np.concatenate([approved[:i0], gen441, approved[i0:]])
    wavp = os.path.join(d, "Dry approved passage plus next eight bars.wav")
    mp3p = os.path.join(d, "Dry approved passage plus next eight bars.mp3")
    nbp = os.path.join(d, "New eight bars only.wav")
    shutil.copy2(nbp, nbp + ".firstpass.bak")
    sf.write(nbp, gen441, SR_OUT, subtype="PCM_24")
    sf.write(wavp, preview, SR_OUT, subtype="PCM_24")
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", wavp,
                        "-b:a", "320k", mp3p], capture_output=True, text=True)
    man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
    man.update({"rebuilt_from_raw": True,
                "rebuild_reason": "first pass clamped gain at 2.0 -> section 4 dB low, seed 308 peaked at full scale",
                "gain_final": round(g, 4),
                "peak_final": round(float(np.max(np.abs(gen441))), 4),
                "clip_fraction_raw": round(clip_raw, 6),
                "mp3_encoder": "ok" if r.returncode == 0 else r.stderr[:200]})
    json.dump(man, open(os.path.join(d, "manifest.json"), "w", encoding="utf-8"), indent=2)
    print(f"seed {seed}: gain {g:.3f} peak {np.max(np.abs(gen441)):.3f} "
          f"clip_raw {clip_raw:.4f} new_rms {np.sqrt(np.mean(gen441**2)):.4f} "
          f"target {target:.4f} mp3 {'ok' if r.returncode == 0 else 'FAIL'}")
