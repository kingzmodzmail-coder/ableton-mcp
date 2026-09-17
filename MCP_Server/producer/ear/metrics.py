"""Mix measurements for the QC gate.

Honest about method: RMS is not LUFS, and the true-peak figure here is a 4x
oversampled estimate, not a certified ITU-R BS.1770 meter. Integrated LUFS is
reported only when ``pyloudnorm`` is installed; otherwise the field is None
and the QC gate says so instead of guessing.
"""
import math

import numpy as np

from ..audio import db, read_wav
from .bands import band_energy_fraction

LOW_BAND_RATE = 1000  # sub/low work runs on a decimated signal; cheap and enough
DEFAULT_MONO_CUTOFF_HZ = 120.0


def as_frames(samples):
    x = np.asarray(samples, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    if x.ndim != 2 or len(x) < 2 or not 1 <= x.shape[1] <= 8:
        raise ValueError("Expected frames x channels audio (1-8 channels)")
    if not np.isfinite(x).all():
        raise ValueError("Audio contains NaN or Inf samples")
    return x


def mono(frames):
    return np.mean(as_frames(frames), axis=1)


def mid_side(frames):
    x = as_frames(frames)
    if x.shape[1] < 2:
        return x[:, 0], np.zeros(len(x))
    left, right = x[:, 0], x[:, 1]
    return (left + right) / 2.0, (left - right) / 2.0


def decimate(signal, rate, target_rate=LOW_BAND_RATE):
    """Averaging decimation: a crude low-pass, adequate below ~200 Hz."""
    signal = np.asarray(signal, dtype=float)
    factor = max(1, int(rate // target_rate))
    if factor == 1:
        return signal, float(rate)
    usable = len(signal) - (len(signal) % factor)
    if usable < factor:
        raise ValueError("Signal too short to decimate")
    return signal[:usable].reshape(-1, factor).mean(axis=1), rate / factor


def band_limited(signal, rate, low=None, high=None):
    """Zero-phase band limit via rFFT masking (whole-signal, use decimated input)."""
    signal = np.asarray(signal, dtype=float)
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(len(signal), 1.0 / rate)
    mask = np.ones(len(spectrum), dtype=bool)
    if low is not None:
        mask &= freqs >= low
    if high is not None:
        mask &= freqs < high
    return np.fft.irfft(spectrum * mask, n=len(signal))


def rms(signal):
    signal = np.asarray(signal, dtype=float)
    if not len(signal):
        return 0.0
    return float(np.sqrt(np.mean(signal ** 2)))


def true_peak_dbtp(frames, rate, oversample=4, block=1 << 15):
    """4x-oversampled peak estimate (dBTP-ish). Not a certified true-peak meter."""
    x = as_frames(frames)
    peak = 0.0
    for offset in range(0, len(x), block):
        chunk = x[offset:offset + block]
        if len(chunk) < 8:
            peak = max(peak, float(np.max(np.abs(chunk))) if len(chunk) else 0.0)
            continue
        spectrum = np.fft.rfft(chunk, axis=0)
        upsampled = np.fft.irfft(spectrum, n=len(chunk) * oversample, axis=0) * oversample
        peak = max(peak, float(np.max(np.abs(upsampled))))
    return db(peak)


def integrated_lufs(frames, rate):
    """Integrated loudness via pyloudnorm when available, else (None, reason)."""
    try:
        import pyloudnorm
    except Exception:
        return None, "pyloudnorm not installed (pip install '.[producer]')"
    x = as_frames(frames)
    if len(x) / float(rate) < 0.4:
        return None, "clip shorter than the 400 ms gating block"
    try:
        meter = pyloudnorm.Meter(int(rate))
        value = float(meter.integrated_loudness(x if x.shape[1] > 1 else x[:, 0]))
    except Exception as error:  # a short or silent clip can defeat the gate
        return None, "pyloudnorm could not measure this clip: %s" % error
    if not math.isfinite(value):
        return None, "loudness below the gating threshold (near-silent clip)"
    return value, "pyloudnorm (ITU-R BS.1770-4)"


def low_end(frames, rate, cutoff=DEFAULT_MONO_CUTOFF_HZ):
    """Mono compatibility below ``cutoff``: side energy relative to mid, and phase."""
    mid, side = mid_side(frames)
    mid_low, low_rate = decimate(mid, rate)
    side_low, _ = decimate(side, rate)
    mid_low = band_limited(mid_low, low_rate, high=cutoff)
    side_low = band_limited(side_low, low_rate, high=cutoff)
    mid_rms, side_rms = rms(mid_low), rms(side_low)
    correlation = None
    x = as_frames(frames)
    if x.shape[1] >= 2:
        left = band_limited(decimate(x[:, 0], rate)[0], low_rate, high=cutoff)
        right = band_limited(decimate(x[:, 1], rate)[0], low_rate, high=cutoff)
        if np.std(left) > 1e-9 and np.std(right) > 1e-9:
            correlation = float(np.corrcoef(left, right)[0, 1])
    return {
        "cutoff_hz": float(cutoff),
        "mid_rms_dbfs": db(mid_rms),
        "side_rms_dbfs": db(side_rms),
        # 0 dB means as much energy off-centre as centred below the cutoff.
        "side_to_mid_db": db(side_rms) - db(mid_rms),
        "low_correlation": correlation,
    }


def stereo_width_db(frames):
    mid, side = mid_side(frames)
    return db(rms(side)) - db(rms(mid))


def section_energy(frames, rate, bpm, bars_per_section=8, beats_per_bar=4):
    """RMS per section: the energy map an arrangement is judged against."""
    if not 20 <= float(bpm) <= 300:
        raise ValueError("Invalid tempo")
    x = as_frames(frames)
    frames_per_section = rate * 60.0 / float(bpm) * beats_per_bar * bars_per_section
    if frames_per_section < 1:
        raise ValueError("Section shorter than one frame")
    out = []
    count = max(1, int(len(x) / frames_per_section))
    for index in range(count):
        chunk = x[round(index * frames_per_section):round((index + 1) * frames_per_section)]
        if len(chunk) < 2:
            continue
        out.append({"section_index": index,
                    "start_seconds": round(index * frames_per_section / rate, 3),
                    "rms_dbfs": db(rms(chunk))})
    return out


def scan(samples, rate, bpm, beats_per_bar=4, bars_per_section=8,
         mono_cutoff=DEFAULT_MONO_CUTOFF_HZ):
    """Every measurement the QC gate reads, from one pass over the audio."""
    from .kickbass import kick_bass_overlap

    x = as_frames(samples)
    peak = float(np.max(np.abs(x)))
    loudness, loudness_method = integrated_lufs(x, rate)
    result = {
        "duration_seconds": len(x) / float(rate),
        "sample_rate": int(rate),
        "channels": int(x.shape[1]),
        "bpm": float(bpm),
        "sample_peak_dbfs": db(peak),
        "true_peak_dbtp": true_peak_dbtp(x, rate),
        "rms_dbfs": db(rms(x)),
        "crest_db": db(peak) - db(rms(x)),
        "lufs_integrated": loudness,
        "lufs_method": loudness_method,
        "band_energy_fraction": band_energy_fraction(x, rate),
        "low_end": low_end(x, rate, mono_cutoff),
        "stereo_width_db": stereo_width_db(x),
        "section_energy": section_energy(x, rate, bpm, bars_per_section, beats_per_bar),
        "kick_bass": kick_bass_overlap(x, rate, bpm),
        "usable_signal": bool(peak >= 1e-5),
        "limits": ("Measurement only. RMS is not LUFS; true peak is a 4x "
                   "oversampled estimate; spectral ratios and overlap figures "
                   "do not establish musical quality. Audition before deciding."),
    }
    if not result["usable_signal"]:
        result["findings"] = ["Silent capture: check output routing and transport "
                              "before reading anything else here."]
    return result


def scan_file(path, bpm, beats_per_bar=4, bars_per_section=8,
              mono_cutoff=DEFAULT_MONO_CUTOFF_HZ):
    """Scan a local PCM WAV (same reader, size and duration limits as producer.audio)."""
    samples, rate = read_wav(path)
    out = scan(samples, rate, bpm, beats_per_bar, bars_per_section, mono_cutoff)
    out["path"] = str(path)
    return out
