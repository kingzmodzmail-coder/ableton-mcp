"""Band edges shared by every ear measurement.

These are the same edges ``producer.audio.measure`` reports, so reference
profiles, captures and A/B comparisons stay comparable. A test pins them
together; change them in one place only.
"""
import numpy as np

BAND_EDGES = (
    ("sub_30_80", 30.0, 80.0),
    ("low_80_250", 80.0, 250.0),
    ("mid_250_3000", 250.0, 3000.0),
    ("presence_3000_6000", 3000.0, 6000.0),
    ("air_6000_20000", 6000.0, 20000.0),
)

# The sub region the kick owns; see SUB_OWNERSHIP in qc.py.
SUB_REGION_HZ = (30.0, 120.0)


def band_energy_fraction(frames, rate, block=8192):
    """Fraction of total spectral power per band (Hann-windowed, block-averaged)."""
    x = np.asarray(frames, dtype=float)
    if x.ndim != 2 or len(x) < 2:
        raise ValueError("Expected finite frames x channels audio")
    power = np.zeros(block // 2 + 1)
    window = np.hanning(block)[:, None]
    for offset in range(0, len(x), block):
        chunk = x[offset:offset + block]
        if len(chunk) < block:
            chunk = np.pad(chunk, ((0, block - len(chunk)), (0, 0)))
        power += np.mean(np.abs(np.fft.rfft(chunk * window, axis=0)) ** 2, axis=1)
    freqs = np.fft.rfftfreq(block, 1.0 / rate)
    total = max(float(power.sum()), 1e-30)
    return {name: float(power[(freqs >= lo) & (freqs < hi)].sum() / total)
            for name, lo, hi in BAND_EDGES}
