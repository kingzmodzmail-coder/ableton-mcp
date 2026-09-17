"""Continue dry-next-v8 with eight more bars (dry-next-v9).

Replicates the approved v7 -> v8 workflow with the pinned local MusicGen:
condition on the last approved eight bars, generate 589 codec frames (~11.78 s
at 163 BPM), insert before the original return at 47.11927437641723 s.
Approved PCM stays untouched; only the generated section is faded (2 ms edges).
"""
import argparse, hashlib, json, os, subprocess, sys, time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import numpy as np
import soundfile as sf
import librosa
import torch
from transformers import AutoProcessor, MusicgenForConditionalGeneration

PROJ = r"C:\Users\Gebruiker\ableton-mcp\.producer\projects\how-about-everyone-else"
V8 = os.path.join(PROJ, "dry-next-v8")
V9 = os.path.join(PROJ, "dry-next-v9")  # overridden by --outdir
MODEL_DIR = r"C:\Users\Gebruiker\ableton-mcp\.producer\models\musicgen-small-4c8334b"
APPROVED_WAV = os.path.join(V8, "Dry approved passage plus next eight bars.wav")
CONTEXT_WAV = os.path.join(V8, "New eight bars only.wav")
APPROVED_SHA256 = "8a9ca02ffc771c42251ce0dea62dac10b4bb1da83d2c17aa570b81e324980cf8"
SPLICE_S = 47.11927437641723
SEED = 306
MAX_NEW_TOKENS = 589
TEXT = ("Instrumental underground mental acidcore and tribe tekno, around 163 BPM. "
        "Continue the recording with the same distorted rolling kick bass groove, "
        "hypnotic acid synthesizer, sparse percussion, no vocals.")
SR_MODEL = 32000
SR_OUT = 44100
FADE_MS = 2.0


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def quality(p, sr=SR_OUT):
    import librosa as _l
    S = np.abs(_l.stft(p, n_fft=2048))
    fr = _l.fft_frequencies(sr=sr, n_fft=2048)
    return {"centroid_hz": round(float(np.mean(_l.feature.spectral_centroid(y=p, sr=sr)))),
            "hf_ratio": round(float(S[fr > 8000].sum() / S.sum()), 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--outdir", default="dry-next-v9")
    args = ap.parse_args()
    global V9
    V9 = os.path.join(PROJ, args.outdir)

    got = sha256(APPROVED_WAV)
    if got != APPROVED_SHA256:
        sys.exit(f"ABORT: approved preview sha256 mismatch: {got}")

    approved, sr = sf.read(APPROVED_WAV, always_2d=True, dtype="float64")
    assert sr == SR_OUT and approved.shape[1] == 2, (sr, approved.shape)
    ctx, csr = sf.read(CONTEXT_WAV, always_2d=True, dtype="float64")
    assert csr == SR_OUT and abs(len(ctx) / csr - 11.779819) < 1e-3, (csr, len(ctx))
    ctx_mono = ctx.mean(axis=1)
    ctx32 = librosa.resample(ctx_mono, orig_sr=SR_OUT, target_sr=SR_MODEL)

    print(f"approved {approved.shape} @{sr}  context {ctx.shape}  ctx32 {ctx32.shape}", flush=True)

    t0 = time.time()
    proc = AutoProcessor.from_pretrained(MODEL_DIR, local_files_only=True)
    model = MusicgenForConditionalGeneration.from_pretrained(
        MODEL_DIR, local_files_only=True).eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    print(f"model loaded on {device} in {time.time()-t0:.1f}s", flush=True)

    n_tokens = 50 if args.smoke else MAX_NEW_TOKENS
    torch.manual_seed(args.seed)
    inputs = proc(text=[TEXT], audio=ctx32, sampling_rate=SR_MODEL,
                  padding=True, return_tensors="pt").to(device)
    t1 = time.time()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=n_tokens, do_sample=True,
                             guidance_scale=3.0)
    out = out[0, 0].float().cpu().numpy()
    elapsed = time.time() - t1
    hop = 640  # 32 kHz / 50 Hz codec frame
    n_out_frames = len(out) // hop
    # continuation mode: output = prompt + generated; the newest n_tokens frames
    # are the generated ones (same tail-cut the approved v8 used)
    gen = out[-n_tokens * hop:] if n_out_frames >= n_tokens + 100 else out
    dur = len(gen) / SR_MODEL
    print(f"model output {n_out_frames} frames; continuation {dur:.3f}s "
          f"({n_tokens} frames) in {elapsed:.1f}s on {device}", flush=True)

    if args.smoke:
        print("SMOKE OK")
        return

    os.makedirs(V9, exist_ok=True)
    sf.write(os.path.join(V9, "Raw codec output.wav"), out, SR_MODEL, subtype="FLOAT")

    # gain-match the generated section to the context it continues from
    gen_rms = float(np.sqrt(np.mean(gen ** 2)))
    ctx_rms = float(np.sqrt(np.mean(ctx_mono ** 2)))
    gain = ctx_rms / gen_rms if gen_rms > 1e-9 else 1.0
    gain = float(np.clip(gain, 0.5, 4.0))
    gen = gen * gain
    peak = float(np.max(np.abs(gen)))
    if peak > 0.99:
        gen = gen * (0.99 / peak)
        peak = 0.99

    gen441 = librosa.resample(gen, orig_sr=SR_MODEL, target_sr=SR_OUT)
    pk = np.max(np.abs(gen441))
    if pk > 0.97:  # resample can overshoot the 32k-domain guard
        gen441 *= 0.97 / pk
    crest = 20 * np.log10(np.max(np.abs(gen)) / np.sqrt(np.mean(gen ** 2)))
    kurt = float(np.mean((gen - gen.mean()) ** 4) / np.std(gen) ** 4)
    n_fade = max(1, int(FADE_MS / 1000.0 * SR_OUT))
    ramp = np.linspace(0.0, 1.0, n_fade) ** 0.5
    gen441[:n_fade] *= ramp
    gen441[-n_fade:] *= ramp[::-1]
    gen_stereo = np.stack([gen441, gen441], axis=1)

    i0 = int(round(SPLICE_S * SR_OUT))
    assert 0 < i0 < len(approved)
    before = approved[:i0]
    after = approved[i0:]
    preview = np.concatenate([before, gen_stereo, after], axis=0)

    # verify the untouched regions are byte-identical to the approved preview
    assert np.array_equal(preview[:i0], before)
    assert np.array_equal(preview[i0 + len(gen_stereo):], after)
    discont_in = float(abs(before[-1].mean() - gen441[0]))
    discont_out = float(abs(gen441[-1] - after[0].mean()))

    full_wav = os.path.join(V9, "Dry approved passage plus next eight bars.wav")
    sf.write(full_wav, preview, SR_OUT, subtype="PCM_24")
    newbars_wav = os.path.join(V9, "New eight bars only.wav")
    sf.write(newbars_wav, gen_stereo, SR_OUT, subtype="PCM_24")

    mp3 = os.path.join(V9, "Dry approved passage plus next eight bars.mp3")
    enc = "ok"
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", full_wav,
                        "-codec:a", "libmp3lame", "-b:a", "320k", mp3],
                       check=True)
    except Exception as e:  # noqa: BLE001
        enc = f"ffmpeg failed: {e}"

    manifest = {
        "approved_source_sha256": APPROVED_SHA256,
        "approved_audio_preserved": True,
        "seed": args.seed,
        "new_section_quality": quality(gen441),
        "new_section": {"crest_db": round(float(crest), 1), "kurtosis": round(kurt, 1)},
        "context_quality": quality(ctx_mono),
        "model_revision": "4c8334b02c6ec4e8664a91979669a501ec497792",
        "model_dir": MODEL_DIR,
        "device": device,
        "text_condition": TEXT,
        "prompt_codec_frames": 589,
        "new_codec_frames": MAX_NEW_TOKENS,
        "sampling": {"do_sample": True, "guidance_scale": 3.0,
                     "max_new_tokens": MAX_NEW_TOKENS, "seed": args.seed},
        "seconds_elapsed": elapsed,
        "duration_s": len(preview) / SR_OUT,
        "new_section_s": [i0 / SR_OUT, (i0 + len(gen_stereo)) / SR_OUT],
        "original_returns_s": (i0 + len(gen_stereo)) / SR_OUT,
        "generation_gain": gain,
        "generated_rms": gen_rms,
        "context_rms": ctx_rms,
        "generated_peak": peak,
        "added_echo": False,
        "added_reverb": False,
        "edge_fade_ms": FADE_MS,
        "join_discontinuity": {"in": discont_in, "out": discont_out},
        "sha256": {os.path.basename(p): sha256(p)
                   for p in (full_wav, newbars_wav) + ((mp3,) if enc == "ok" else ())},
        "mp3_encoder": enc,
        "status": "New section awaits user listening; previous dry passage remains approved",
        "limits": ("Local MusicGen private evaluation. No future conditioning or "
                   "perceptual quality claim. Natural model ambience may remain."),
    }
    with open(os.path.join(V9, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("MANIFEST " + json.dumps(manifest), flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
