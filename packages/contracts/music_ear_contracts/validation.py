"""JSON Schema validation plus timeline and document invariants."""

import json
import math
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker


class ContractError(ValueError):
    pass


def schema(kind):
    bundle = json.loads(files("music_ear_contracts").joinpath("schemas/1.0.json").read_text(encoding="utf-8"))
    if kind not in bundle["$defs"]:
        raise ContractError(f"Unknown contract: {kind}")
    return {**bundle, "$ref": f"#/$defs/{kind}"}


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _json(value):
    if isinstance(value, float):
        _require(math.isfinite(value), "Non-finite numbers are forbidden")
    elif isinstance(value, dict):
        for key, child in value.items():
            _require(isinstance(key, str), "JSON keys must be strings")
            _json(child)
    elif isinstance(value, list):
        for child in value:
            _json(child)
    else:
        _require(value is None or type(value) in (str, int, bool), "Not a JSON value")


def _location(location, duration=None):
    if "start_s" in location:
        _require(location["start_s"] < location["end_s"], "Interval must be nonempty and forward")
    if duration is not None:
        end = location.get("end_s", location.get("time_s", 0))
        _require(end <= duration + 1 / 48000, "Event exceeds master timeline")


def _label(task, label):
    if task in ("key", "chord"):
        allowed = schema("ChordLabel")["$defs"]["ChordLabel"]["enum"]
        if task == "key":
            allowed = [x for x in allowed if x not in ("N", "X")] + ["unknown"]
        _require(label in allowed, f"Invalid {task} label: {label!r}")


def _events(events, id_key, duration, task=None):
    ids = [e[id_key] for e in events]
    _require(len(ids) == len(set(ids)), "Duplicate event ID")
    for event in events:
        _location(event["location"], duration)
        event_task = task or event["task"]
        _label(event_task, event["label"])
        for alternative in event["alternatives"]:
            _label(event_task, alternative["label"])
        if "beat_in_bar" in event:
            _require(event["beat_in_bar"] <= event["beats_per_bar"], "Beat exceeds meter")


def validate(kind, document):
    """Validate without mutating input; raise ContractError on invalid data.

    Artifact bytes and external observation IDs require separate integrity
    checks by the artifact reader; metadata validation cannot prove them.
    """
    _json(document)
    errors = list(Draft202012Validator(schema(kind), format_checker=FormatChecker()).iter_errors(document))
    if errors:
        error = errors[0]
        raise ContractError(f"/{'/'.join(map(str, error.absolute_path))}: {error.message}")
    d = document
    if kind in ("Location", "IntervalTime", "PointTime"):
        _location(d)
    elif kind == "AudioSliceRef":
        _require(0 <= d["start_sample"] <= d["core_start_sample"] < d["core_end_sample"] <= d["end_sample"] <= d["master_sample_count"], "Invalid slice/context bounds")
    elif kind == "CanonicalAudioArtifact":
        _require(abs(d["duration_s"] - d["sample_count"] / 48000) <= 1e-9, "Duration differs from sample count")
        _require(d["pcm"]["byte_length"] == d["sample_count"] * d["channels"] * 4, "PCM byte length mismatch")
        _require(d["channel_order"] == (["M"] if d["channels"] == 1 else ["L", "R"]), "Channel order mismatch")
        _require(d["original"]["channels"] == d["channels"], "Initial profile preserves mono/stereo; multichannel input is unsupported")
        _require(d["original"]["sample_rate_hz"] == 48000 or d["resampler_revision"] is not None, "Resampling requires a pinned revision")
        stats = d["statistics"]
        _require(stats["rms"] <= stats["sample_peak"], "RMS exceeds peak")
        _require(stats["overrange_sample_count"] <= d["sample_count"] * d["channels"], "Overrange count exceeds samples")
    elif kind == "ObservationSet":
        _events(d["observations"], "observation_id", d["timebase"]["master_sample_count"] / 48000, d["task"])
        starts = [e["location"].get("start_s", e["location"].get("time_s", 0)) for e in d["observations"]]
        _require(starts == sorted(starts), "Observations must be time ordered")
    elif kind == "AnalysisDocument":
        validate("CanonicalAudioArtifact", d["media"])
        _require(d["track_id"] == d["media"]["track_id"], "Media track mismatch")
        _events(d["facts"], "fact_id", d["media"]["duration_s"])
        refs = {r["observation_set_id"]: r for r in d["observation_sets"]}
        _require(len(refs) == len(d["observation_sets"]), "Duplicate observation set")
        outcomes = d["task_outcomes"]
        _require(len({o["task"] for o in outcomes}) == len(outcomes), "Duplicate task outcome")
        for fact in d["facts"]:
            for evidence in fact["evidence"]:
                ref = refs.get(evidence["observation_set_id"])
                _require(ref is not None and ref["task"] == fact["task"], "Missing or incompatible evidence set")
        for outcome in outcomes:
            for set_id in outcome["observation_set_ids"]:
                _require(set_id in refs and refs[set_id]["task"] == outcome["task"], "Task observation reference mismatch")
        for embedding in d["embeddings"]:
            _location(embedding["location"], d["media"]["duration_s"])
        if d["status"] == "empty":
            _require(not any(d[k] for k in ("facts", "task_outcomes", "observation_sets", "embeddings")), "Empty analysis contains results")
        else:
            _require(bool(outcomes), "Completed analysis needs task outcomes")
            _require(all(o["status"] == "succeeded" for o in outcomes if o["required"]), "Required task did not succeed")
            partial = any(o["status"] != "succeeded" for o in outcomes)
            _require(partial == (d["status"] == "partial_success"), "Partial success status mismatch")
            _require(any(o["status"] == "succeeded" for o in outcomes), "No successful task")
    return document
