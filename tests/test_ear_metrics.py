"""Mix-ear measurements against synthetic signals with known properties.

Every assertion has a ground truth we construct here: a sine of known
amplitude, a kick-only pattern, the same pattern with a continuous sub bass
under it, and an out-of-phase low end. No Ableton, no audio hardware.
"""
import math

import numpy as np
import pytest

from MCP_Server.producer.audio import measure
from MCP_Server.producer.ear import bands, kickbass, metrics

RATE = 44100
BPM = 160.0
BEAT = 60.0 / BPM


def sine(freq, seconds, amplitude=0.5, rate=RATE, channels=2):
    t = np.arange(int(seconds * rate)) / rate
    wave = amplitude * np.sin(2 * math.pi * freq * t)
    return np.repeat(wave[:, None], channels, axis=1)


def kick_pattern(beats=16, with_sub_bass=False, rate=RATE, bpm=BPM):
    """Four-on-the-floor sub thumps, optionally over a continuous 55 Hz bass."""
    total = int(beats * 60.0 / bpm * rate)
    t = np.arange(total) / rate
    signal = np.zeros(total)
    for beat in range(beats):
        start = int(beat * 60.0 / bpm * rate)
        length = int(0.08 * rate)
        local = np.arange(length) / rate
        envelope = np.exp(-local * 40)
        signal[start:start + length] += 0.9 * envelope * np.sin(2 * math.pi * 55 * local)
    if with_sub_bass:
        signal += 0.35 * np.sin(2 * math.pi * 50 * t)
    return np.repeat(signal[:, None], 2, axis=1)


# ------------------------------------------------------------------ basics

def test_band_edges_match_the_existing_audio_module():
    """One source of truth: producer.audio and the ear must agree on bands."""
    frames = sine(1000, 1.0)
    from_audio = set(measure(frames, RATE, BPM)["band_energy_fraction"])
    assert from_audio == {name for name, _, _ in bands.BAND_EDGES}


def test_rms_and_peak_of_a_known_sine():
    frames = sine(1000, 1.0, amplitude=0.5)
    scan = metrics.scan(frames, RATE, BPM)
    assert scan["sample_peak_dbfs"] == pytest.approx(-6.02, abs=0.1)
    assert scan["rms_dbfs"] == pytest.approx(-9.03, abs=0.1)   # -6 dB sine = -9 dBFS RMS
    assert scan["crest_db"] == pytest.approx(3.01, abs=0.1)
    assert scan["usable_signal"] is True


def test_band_energy_lands_in_the_right_band():
    energy = bands.band_energy_fraction(sine(1000, 1.0), RATE)
    assert energy["mid_250_3000"] > 0.9
    assert energy["sub_30_80"] < 0.01


def test_true_peak_is_at_least_sample_peak():
    frames = sine(7000, 0.5, amplitude=0.9)   # inter-sample peaks above samples
    scan = metrics.scan(frames, RATE, BPM)
    assert scan["true_peak_dbtp"] >= scan["sample_peak_dbfs"] - 0.01


def test_silence_is_flagged_not_scored():
    scan = metrics.scan(np.zeros((RATE, 2)), RATE, BPM)
    assert scan["usable_signal"] is False
    assert "findings" in scan


def test_nan_audio_is_rejected():
    frames = sine(100, 0.2)
    frames[10, 0] = np.nan
    with pytest.raises(ValueError):
        metrics.scan(frames, RATE, BPM)


def test_lufs_is_none_with_a_reason_when_unavailable():
    value, method = metrics.integrated_lufs(sine(1000, 1.0), RATE)
    assert (value is None) == ("pyloudnorm" in method and "not installed" in method) \
        or isinstance(value, float)


# ------------------------------------------------------------- stereo / lows

def test_identical_channels_are_centred_below_the_cutoff():
    low = metrics.low_end(sine(60, 1.0), RATE)
    assert low["side_to_mid_db"] < -40           # nothing off-centre
    assert low["low_correlation"] == pytest.approx(1.0, abs=0.01)


def test_out_of_phase_low_end_is_detected():
    frames = sine(60, 1.0)
    frames[:, 1] *= -1                            # inverted right channel
    low = metrics.low_end(frames, RATE)
    assert low["side_to_mid_db"] > 0              # more side than mid
    assert low["low_correlation"] < -0.9


def test_stereo_width_of_a_mono_signal_is_very_negative():
    assert metrics.stereo_width_db(sine(500, 0.5)) < -40


def test_section_energy_tracks_a_level_change():
    quiet = sine(500, 4 * BEAT * 8, amplitude=0.05)   # 8 bars
    loud = sine(500, 4 * BEAT * 8, amplitude=0.5)
    frames = np.concatenate([quiet, loud])
    sections = metrics.section_energy(frames, RATE, BPM, bars_per_section=8)
    assert len(sections) == 2
    assert sections[1]["rms_dbfs"] - sections[0]["rms_dbfs"] == pytest.approx(20, abs=1.0)


# -------------------------------------------------------------- kick / bass

def test_kicks_are_found_on_every_beat():
    kicks = kickbass.detect_kicks(kick_pattern(), RATE, BPM)
    assert len(kicks) >= 15
    spacing = np.diff([k["time_seconds"] for k in kicks])
    assert np.allclose(spacing, BEAT, atol=0.02)


def test_kick_owns_the_sub_when_nothing_else_plays():
    overlap = kickbass.kick_bass_overlap(kick_pattern(), RATE, BPM)
    assert overlap["measured"] is True
    assert overlap["between_to_kick_db"] < -6      # gaps are much quieter


def test_continuous_sub_bass_shows_up_as_lost_ownership():
    clean = kickbass.kick_bass_overlap(kick_pattern(), RATE, BPM)
    fighting = kickbass.kick_bass_overlap(kick_pattern(with_sub_bass=True), RATE, BPM)
    assert fighting["between_to_kick_db"] > clean["between_to_kick_db"] + 6
    assert fighting["between_to_kick_db"] > -6     # fails the sub-ownership rule


def test_overlap_reports_unmeasured_on_a_clip_that_is_too_short():
    overlap = kickbass.kick_bass_overlap(sine(50, 0.05), RATE, BPM)
    assert overlap["measured"] is False and "reason" in overlap


def test_scan_includes_every_field_the_gate_reads():
    scan = metrics.scan(kick_pattern(), RATE, BPM)
    for key in ("true_peak_dbtp", "crest_db", "lufs_integrated", "band_energy_fraction",
                "low_end", "stereo_width_db", "section_energy", "kick_bass", "limits"):
        assert key in scan
