"""Kick and bass in the sub region: who owns 30-120 Hz, and when.

Kick weight first is the taste rule, so the gate needs a number for it. This
measures energy overlap on the beat grid; it does not claim to hear a clash.
A four-on-the-floor grid is assumed (the acidcore/mental/tribe lane), so the
figures are meaningless for material without a kick on every beat.
"""
import numpy as np

from ..audio import db
from .bands import SUB_REGION_HZ
from .metrics import as_frames, band_limited, decimate, mono, rms

KICK_WINDOW_SECONDS = 0.09       # the kick's own sub window
BETWEEN_WINDOW = (0.35, 0.85)    # fraction of a beat, between two kicks
SEARCH_SECONDS = 0.08            # grid tolerance when locating each kick


def _sub_envelope(frames, rate, region=SUB_REGION_HZ):
    signal, low_rate = decimate(mono(frames), rate)
    sub = band_limited(signal, low_rate, low=region[0], high=region[1])
    return sub, low_rate


def detect_kicks(frames, rate, bpm, region=SUB_REGION_HZ):
    """Locate one sub transient per beat. Returns [{beat, time_seconds, peak_dbfs}]."""
    if not 20 <= float(bpm) <= 300:
        raise ValueError("Invalid tempo")
    sub, low_rate = _sub_envelope(frames, rate, region)
    envelope = np.abs(sub)
    beat_seconds = 60.0 / float(bpm)
    duration = len(sub) / low_rate
    search = int(SEARCH_SECONDS * low_rate)
    kicks = []
    beat = 0
    while beat * beat_seconds < duration:
        centre = int(beat * beat_seconds * low_rate)
        lo, hi = max(0, centre - search), min(len(envelope), centre + search)
        if hi - lo < 2:
            break
        offset = int(np.argmax(envelope[lo:hi]))
        index = lo + offset
        kicks.append({"beat": beat,
                      "time_seconds": round(index / low_rate, 4),
                      "peak_dbfs": db(envelope[index])})
        beat += 1
    return kicks


def kick_bass_overlap(frames, rate, bpm, region=SUB_REGION_HZ):
    """Compare sub energy under each kick with the gaps between kicks.

    ``between_to_kick_db`` near 0 means something holds the sub region while
    the kick is not playing — the kick has lost ownership of it. Well below 0
    means the kick owns the sub and the bass sits above or ducks out of it.
    """
    x = as_frames(frames)
    sub, low_rate = _sub_envelope(x, rate, region)
    kicks = detect_kicks(x, rate, bpm, region)
    beat_frames = 60.0 / float(bpm) * low_rate
    kick_rms, between_rms = [], []
    for kick in kicks:
        start = int(kick["time_seconds"] * low_rate)
        kick_slice = sub[start:start + max(2, int(KICK_WINDOW_SECONDS * low_rate))]
        gap = sub[start + int(BETWEEN_WINDOW[0] * beat_frames):
                  start + int(BETWEEN_WINDOW[1] * beat_frames)]
        if len(kick_slice) > 1:
            kick_rms.append(rms(kick_slice))
        if len(gap) > 1:
            between_rms.append(rms(gap))
    if not kick_rms or not between_rms:
        return {"kicks_found": len(kicks), "measured": False,
                "reason": "clip too short for a kick window and a gap window",
                "region_hz": list(region)}
    kick_level = db(float(np.median(kick_rms)))
    between_level = db(float(np.median(between_rms)))
    return {
        "measured": True,
        "region_hz": list(region),
        "kicks_found": len(kicks),
        "kick_sub_rms_dbfs": kick_level,
        "between_sub_rms_dbfs": between_level,
        "between_to_kick_db": between_level - kick_level,
        "sub_rms_dbfs": db(rms(sub)),
        "note": ("Assumes a kick on every beat. between_to_kick_db near 0 means "
                 "another element owns the sub between kicks."),
    }
