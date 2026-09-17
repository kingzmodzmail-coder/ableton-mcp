"""Reference profiles: target ranges measured from approved reference renders.

A profile is built from audio you have chosen and are allowed to use (for
Suno material, after the Hermes approval gate). It records what those
references measure - not what anyone believes "good" sounds like.
"""
import json
import statistics
from pathlib import Path

PROFILED_METRICS = (
    "lufs_integrated",
    "true_peak_dbtp",
    "crest_db",
    "stereo_width_db",
    "band_energy_fraction.sub_30_80",
    "band_energy_fraction.low_80_250",
    "band_energy_fraction.mid_250_3000",
    "band_energy_fraction.presence_3000_6000",
    "band_energy_fraction.air_6000_20000",
    "low_end.side_to_mid_db",
    "kick_bass.between_to_kick_db",
)

PROFILE_VERSION = 1
MIN_PAD = {"band_energy_fraction": 0.01}
DEFAULT_PAD_FRACTION = 0.15


def read_metric(scan, dotted):
    """Follow a dotted path into a scan; None when absent or not numeric."""
    node = scan
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        return None
    return float(node)


def build_profile(scans, name, pad_fraction=DEFAULT_PAD_FRACTION, metrics=PROFILED_METRICS):
    """Turn reference scans into target ranges.

    The range is the observed span widened by ``pad_fraction`` (so a single
    reference still yields a usable, clearly wide band), with the median kept
    for reporting. Metrics missing from any scan are listed as unmeasured
    rather than silently dropped.
    """
    scans = list(scans)
    if not scans:
        raise ValueError("A profile needs at least one reference scan")
    targets, unmeasured = {}, []
    for metric in metrics:
        values = [v for v in (read_metric(s, metric) for s in scans) if v is not None]
        if not values:
            unmeasured.append(metric)
            continue
        low, high = min(values), max(values)
        span = high - low
        pad = max(span * pad_fraction, MIN_PAD.get(metric.split(".")[0], 0.0),
                  abs(statistics.median(values)) * pad_fraction * 0.5)
        targets[metric] = {
            "low": round(low - pad, 6),
            "high": round(high + pad, 6),
            "median": round(statistics.median(values), 6),
            "observed_low": round(low, 6),
            "observed_high": round(high, 6),
            "references": len(values),
        }
    return {
        "profile_version": PROFILE_VERSION,
        "name": name,
        "reference_count": len(scans),
        "references": [{"path": s.get("path"), "bpm": s.get("bpm"),
                        "duration_seconds": round(float(s.get("duration_seconds", 0)), 2)}
                       for s in scans],
        "targets": targets,
        "unmeasured_metrics": unmeasured,
        "note": ("Ranges describe the references, not a quality threshold. "
                 "Widen them deliberately; never widen one to let a failing "
                 "build through."),
    }


def save_profile(profile, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2, allow_nan=False), encoding="utf-8")
    return str(path)


def load_profile(path):
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    if profile.get("profile_version") != PROFILE_VERSION:
        raise ValueError("Unsupported profile version: %r" % profile.get("profile_version"))
    if not profile.get("targets"):
        raise ValueError("Profile has no targets")
    return profile
