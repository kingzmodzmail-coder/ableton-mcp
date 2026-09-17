"""The QC gate: hard rules, reference profiles, and the things it must refuse."""
import json

import pytest

from MCP_Server.producer.ear import build_profile, check, load_profile, save_profile
from MCP_Server.producer.ear.qc import DEFAULT_RULES
from MCP_Server.producer.ear.reference import read_metric


def scan(**overrides):
    """A scan that passes every hard rule, so each test changes one thing."""
    base = {
        "usable_signal": True,
        "path": "render.wav",
        "bpm": 162.0,
        "duration_seconds": 120.0,
        "true_peak_dbtp": -1.2,
        "crest_db": 9.0,
        "stereo_width_db": -8.0,
        "lufs_integrated": -8.5,
        "band_energy_fraction": {"sub_30_80": 0.30, "low_80_250": 0.28,
                                 "mid_250_3000": 0.30, "presence_3000_6000": 0.07,
                                 "air_6000_20000": 0.05},
        "low_end": {"side_to_mid_db": -18.0, "low_correlation": 0.95, "cutoff_hz": 120.0},
        "kick_bass": {"measured": True, "between_to_kick_db": -12.0,
                      "kicks_found": 64},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = dict(base[key], **value)
        else:
            base[key] = value
    return base


# ----------------------------------------------------------------- hard rules

def test_clean_render_passes_the_hard_rules():
    verdict = check(scan())
    assert verdict["passed"] is True
    assert verdict["failures"] == []
    assert "audition" in verdict["next_step"].lower()


def test_true_peak_over_the_ceiling_fails():
    verdict = check(scan(true_peak_dbtp=-0.1))
    assert verdict["passed"] is False
    assert "true_peak_ceiling" in verdict["failures"]


def test_wide_low_end_fails_mono_compatibility():
    verdict = check(scan(low_end={"side_to_mid_db": -2.0}))
    assert "low_end_mono" in verdict["failures"]


def test_inverted_low_end_phase_fails():
    verdict = check(scan(low_end={"low_correlation": -0.4}))
    assert "low_end_phase" in verdict["failures"]


def test_bass_holding_the_sub_between_kicks_fails():
    """The HarvestMix defect: statistics said fine, the low end was fighting."""
    verdict = check(scan(kick_bass={"between_to_kick_db": -1.0}))
    assert verdict["passed"] is False
    assert "sub_ownership" in verdict["failures"]
    detail = next(c["detail"] for c in verdict["checks"] if c["check"] == "sub_ownership")
    assert "Kick weight first" in detail


def test_silent_capture_fails_before_anything_else_is_read():
    verdict = check(scan(usable_signal=False))
    assert verdict["passed"] is False
    assert "usable_signal" in verdict["failures"]


def test_loudness_alone_never_passes_a_failing_render():
    """Louder is not better: a loud render with a low-end fault still fails."""
    verdict = check(scan(lufs_integrated=-5.0, kick_bass={"between_to_kick_db": 0.5}))
    assert verdict["passed"] is False


def test_unmeasured_metric_blocks_a_pass_unless_explicitly_allowed():
    partial = scan()
    partial["kick_bass"] = {"measured": False, "reason": "clip too short"}
    strict = check(partial)
    assert strict["passed"] is False and "sub_ownership" in strict["unmeasured"]
    lenient = check(partial, allow_unmeasured=True)
    assert lenient["passed"] is True


def test_every_default_rule_has_a_reason_and_a_known_comparison():
    for name, metric, comparison, limit, why in DEFAULT_RULES:
        assert comparison in ("<=", ">=")
        assert isinstance(limit, float)
        assert len(why) > 20, name


# ------------------------------------------------------------ reference profile

def test_profile_targets_bracket_the_references():
    references = [scan(true_peak_dbtp=-1.0, crest_db=9.0),
                  scan(true_peak_dbtp=-1.4, crest_db=11.0)]
    profile = build_profile(references, "suno-v6-acidcore")
    target = profile["targets"]["crest_db"]
    assert target["low"] < 9.0 and target["high"] > 11.0
    assert target["median"] == pytest.approx(10.0)
    assert profile["reference_count"] == 2


def test_profile_flags_metrics_it_could_not_measure():
    references = [scan(lufs_integrated=None)]
    profile = build_profile(references, "no-loudness")
    assert "lufs_integrated" in profile["unmeasured_metrics"]
    assert "lufs_integrated" not in profile["targets"]


def test_render_outside_the_reference_range_fails_that_check():
    profile = build_profile([scan(crest_db=9.0), scan(crest_db=9.5)], "tight")
    verdict = check(scan(crest_db=20.0), profile)
    assert verdict["passed"] is False
    assert "reference:crest_db" in verdict["failures"]
    assert verdict["profile"] == "tight"


def test_render_inside_the_reference_range_passes():
    profile = build_profile([scan(crest_db=9.0), scan(crest_db=11.0)], "tight")
    assert check(scan(crest_db=10.0), profile)["passed"] is True


def test_profile_round_trips_through_disk(tmp_path):
    profile = build_profile([scan()], "round-trip")
    path = save_profile(profile, tmp_path / "profiles" / "p.json")
    assert load_profile(path)["targets"] == profile["targets"]


def test_unsupported_profile_version_is_refused(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"profile_version": 0, "targets": {"a": {}}}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_profile(path)


def test_build_profile_needs_at_least_one_reference():
    with pytest.raises(ValueError):
        build_profile([], "empty")


def test_read_metric_follows_dotted_paths_and_ignores_non_numbers():
    assert read_metric(scan(), "low_end.side_to_mid_db") == -18.0
    assert read_metric(scan(), "kick_bass.measured") is None   # bool, not a number
    assert read_metric(scan(), "nope.nope") is None
