"""The mix ear: measured mix properties, a reference profile and the QC gate.

These modules measure. They do not listen, and nothing here establishes that
a track is good — a build is only Suno-grade when the measurements pass AND a
blind, loudness-matched A/B says so (docs/SUNO_V6_BENCHMARK.md).
"""

from .bands import BAND_EDGES, band_energy_fraction
from .metrics import scan, scan_file
from .kickbass import kick_bass_overlap, detect_kicks
from .reference import build_profile, load_profile, save_profile
from .qc import check, DEFAULT_RULES

__all__ = [
    "BAND_EDGES", "band_energy_fraction", "scan", "scan_file",
    "kick_bass_overlap", "detect_kicks",
    "build_profile", "load_profile", "save_profile",
    "check", "DEFAULT_RULES",
]
