"""Stage implementations.

What runs headless: intake (inventory), align (tempo/downbeat estimates), qc
(measure and gate), publish (the standard result message). What does not:
build, mix and master drive Ableton through the bridge, so they raise
``StageNeedsLive`` naming the pre-flight command rather than faking progress.
"""
import hashlib
import json
import wave
from pathlib import Path

import numpy as np

AUDIO_SUFFIXES = (".wav",)
MIDI_SUFFIXES = (".mid", ".midi")
HASH_CHUNK = 1 << 20
BPM_SEARCH = (60.0, 200.0)
ENVELOPE_HZ = 100  # onset envelope resolution


class StageNeedsLive(RuntimeError):
    """This stage needs a reachable Ableton bridge and a running Live."""


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wav_header(path):
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        frames = handle.getnframes()
        return {"sample_rate": rate, "channels": handle.getnchannels(),
                "sample_width_bits": handle.getsampwidth() * 8,
                "frames": frames,
                "duration_seconds": round(frames / float(rate), 3) if rate else None}


def intake(inbox, state=None):
    """Inventory an approved pack: hashes and headers, nothing moved or renamed.

    Nothing is downloaded here. Suno material reaches the inbox only after the
    approval gate; this stage just records what arrived.
    """
    folder = Path(inbox)
    if not folder.is_dir():
        raise FileNotFoundError("Inbox folder does not exist: %s" % folder)
    audio, midi, other = [], [], []
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        entry = {"path": str(path), "name": path.name,
                 "bytes": path.stat().st_size, "sha256": _sha256(path)}
        suffix = path.suffix.lower()
        if suffix in AUDIO_SUFFIXES:
            try:
                entry.update(_wav_header(path))
            except Exception as error:
                entry["error"] = "unreadable WAV header: %s" % error
            audio.append(entry)
        elif suffix in MIDI_SUFFIXES:
            midi.append(entry)
        else:
            other.append(entry)
    manifest = {"inbox": str(folder), "audio": audio, "midi": midi,
                "other": other,
                "counts": {"audio": len(audio), "midi": len(midi), "other": len(other)},
                "note": "Inventory only: no tempo or key claims until align runs."}
    if not audio:
        manifest["findings"] = ["No WAV files found; align and build have nothing to work from."]
    if state is not None:
        path = state.root / "pipeline" / (state.slug + ".manifest.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
        state.record("intake", "completed", {"manifest": str(path)},
                     "%d audio, %d MIDI file(s)" % (len(audio), len(midi)))
        manifest["manifest_path"] = str(path)
    return manifest


def onset_envelope(samples, rate, envelope_hz=ENVELOPE_HZ):
    """Half-wave rectified energy difference per frame: crude, cheap, adequate."""
    from ..ear.metrics import mono

    signal = mono(samples)
    hop = max(1, int(rate / float(envelope_hz)))
    usable = len(signal) - (len(signal) % hop)
    if usable < hop * 8:
        raise ValueError("Clip too short for a tempo estimate")
    energy = np.sqrt((signal[:usable].reshape(-1, hop) ** 2).mean(axis=1))
    rise = np.diff(energy, prepend=energy[:1])
    return np.clip(rise, 0, None), rate / float(hop)


def estimate_bpm(samples, rate, search=BPM_SEARCH):
    """Autocorrelation tempo estimate with a confidence figure (peak / mean)."""
    envelope, envelope_rate = onset_envelope(samples, rate)
    envelope = envelope - envelope.mean()
    if not np.any(envelope):
        raise ValueError("No onsets detected; cannot estimate tempo")
    correlation = np.correlate(envelope, envelope, mode="full")[len(envelope) - 1:]
    lags = np.arange(len(correlation)) / envelope_rate
    with np.errstate(divide="ignore", invalid="ignore"):
        bpms = np.where(lags > 0, 60.0 / np.maximum(lags, 1e-9), 0.0)
    window = (bpms >= search[0]) & (bpms <= search[1])
    if not window.any():
        raise ValueError("Clip too short to cover the tempo search range")
    scores = np.where(window, correlation, -np.inf)
    best = int(np.argmax(scores))
    baseline = float(np.mean(correlation[window])) or 1e-9
    return {"bpm": round(float(bpms[best]), 2),
            "confidence": round(float(correlation[best] / abs(baseline)), 2),
            "search_range_bpm": list(search),
            "method": "onset-envelope autocorrelation",
            "note": ("A tempo estimate, not a grid. Confirm against the pack's "
                     "stated BPM before building; half/double-tempo confusions "
                     "are normal.")}


def align(manifest, expected_bpm=None, state=None, max_files=24):
    """Tempo and downbeat estimates per stem, compared against the expected BPM."""
    from ..audio import read_wav
    from ..ear.kickbass import detect_kicks

    files = [entry for entry in manifest.get("audio", []) if "error" not in entry]
    if not files:
        raise ValueError("Manifest has no readable audio; run intake first")
    results = []
    for entry in files[:max_files]:
        row = {"name": entry["name"], "path": entry["path"]}
        try:
            samples, rate = read_wav(entry["path"])
            estimate = estimate_bpm(samples, rate)
            row.update(estimate)
            bpm = expected_bpm or estimate["bpm"]
            kicks = detect_kicks(samples, rate, bpm)
            row["first_transient_seconds"] = kicks[0]["time_seconds"] if kicks else None
            row["downbeat_offset_seconds"] = row["first_transient_seconds"]
            if expected_bpm:
                row["matches_expected_bpm"] = abs(estimate["bpm"] - float(expected_bpm)) <= 1.0
                row["half_or_double"] = any(
                    abs(estimate["bpm"] * factor - float(expected_bpm)) <= 1.0
                    for factor in (0.5, 2.0))
        except Exception as error:
            row["error"] = str(error)
        results.append(row)
    out = {"expected_bpm": expected_bpm, "files": results,
           "skipped": max(0, len(files) - max_files),
           "note": "Estimates only; nothing was rendered, moved or time-stretched."}
    if state is not None:
        state.record("align", "completed", {"files": len(results)},
                     "tempo/downbeat estimates for %d file(s)" % len(results))
    return out


def _needs_live(stage, state=None):
    if state is not None:
        state.record(stage, "needs_live", {},
                     "Requires a reachable bridge and a running Live")
    raise StageNeedsLive(
        "Stage %r drives Ableton and cannot run headless. Run the pre-flight "
        "check first (python -m MCP_Server.producer.cli preflight), then build "
        "from Claude Desktop on the PC with the producer tools." % stage)


def build(section_map=None, state=None, **_):
    """Create the set from the template and the section map (needs Live)."""
    _needs_live("build", state)


def mix(state=None, **_):
    """Apply the low-end template: sidechain, high-pass, bass mono (needs Live)."""
    _needs_live("mix", state)


def master(state=None, **_):
    """Resample and match the reference render's loudness and tone (needs Live)."""
    _needs_live("master", state)


def qc(capture_path, bpm, profile=None, state=None, allow_unmeasured=False):
    """Measure a render and run the gate. A failure blocks publish."""
    from ..ear import check, scan_file

    measurements = scan_file(capture_path, bpm)
    verdict = check(measurements, profile, allow_unmeasured=allow_unmeasured)
    result = {"capture": str(capture_path), "metrics": measurements, "qc": verdict}
    if state is not None:
        report = state.root / "pipeline" / (state.slug + ".qc.json")
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        result["report_path"] = str(report)
        state.record("qc", "completed" if verdict["passed"] else "failed",
                     {"capture": str(capture_path), "report": str(report),
                      "passed": verdict["passed"]},
                     "failures: %s" % (", ".join(verdict["failures"]) or "none"))
    return result


def publish(qc_result, title, bpm, key="", file_link="", state=None):
    """Render the standard result message. Refuses when QC did not pass."""
    verdict = qc_result.get("qc", {})
    if not verdict.get("passed"):
        raise PermissionError(
            "QC did not pass (%s); nothing is published. Fix and re-capture."
            % (", ".join(verdict.get("failures") or verdict.get("unmeasured") or ["unknown"])))
    metrics = qc_result.get("metrics", {})
    lufs = metrics.get("lufs_integrated")
    message = "\n".join([
        "%s - %s BPM%s" % (title, bpm, (" - %s" % key) if key else ""),
        "LUFS: %s" % ("%.1f" % lufs if isinstance(lufs, (int, float)) else "not measured"),
        "True peak: %.2f dBTP" % metrics.get("true_peak_dbtp", float("nan")),
        "Sub ownership: %.1f dB between kicks vs kick"
        % metrics.get("kick_bass", {}).get("between_to_kick_db", float("nan")),
        "QC: passed against profile %s" % (verdict.get("profile") or "hard rules only"),
        "File: %s" % (file_link or "(attach the render)"),
    ])
    out = {"message": message, "title": title, "bpm": bpm, "key": key,
           "qc_profile": verdict.get("profile"),
           "note": "Posting is a human action; this stage only writes the message."}
    if state is not None:
        state.record("publish", "completed", {"title": title}, "message prepared")
    return out
