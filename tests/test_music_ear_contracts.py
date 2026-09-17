import copy

import pytest
from jsonschema import Draft202012Validator

from music_ear_contracts import ContractError, schema, validate


def observation_set():
    revision = "baseline@1.0.0+sha256:" + "a" * 64
    return {
        "schema_version": "observation-set/1.0", "observation_set_id": "obsset_1",
        "track_id": "trk_1", "run_id": "run_1", "input_pcm_sha256": "a" * 64,
        "task": "chord", "producer": {k: revision for k in ("model_revision", "representation_id", "label_set")},
        "timebase": {"sample_rate_hz": 48000, "origin_sample": 0, "master_sample_count": 48000},
        "observations": [{"observation_id": "obs_1", "location": {"start_s": 0, "end_s": 1},
                          "label": "N", "score": {"kind": "unknown", "calibration": {"status": "unavailable"}}, "alternatives": []}],
        "warnings": [],
    }


def test_all_definitions_are_valid_schemas():
    for name in schema("ObservationSet")["$defs"]:
        Draft202012Validator.check_schema(schema(name))


@pytest.mark.parametrize("label", ["N", "X", "C:maj", "G#:min"])
def test_explicit_chord_vocabulary(label):
    doc = observation_set()
    doc["observations"][0]["label"] = label
    validate("ObservationSet", doc)


@pytest.mark.parametrize("label", [None, "E#:maj", "C", "ignore_index"])
def test_invalid_published_chords(label):
    doc = observation_set()
    doc["observations"][0]["label"] = label
    with pytest.raises(ContractError):
        validate("ObservationSet", doc)


@pytest.mark.parametrize("location", [{"start_s": 1, "end_s": 1}, {"start_s": .8, "end_s": .2}, {"time_s": 1.01}])
def test_timeline_rejects_invalid_events(location):
    doc = observation_set()
    doc["observations"][0]["location"] = location
    with pytest.raises(ContractError):
        validate("ObservationSet", doc)


def test_one_sample_tolerance_and_no_mutation():
    doc = observation_set()
    doc["observations"][0]["location"]["end_s"] += 1 / 48000
    before = copy.deepcopy(doc)
    validate("ObservationSet", doc)
    assert before == doc


@pytest.mark.parametrize("score", [
    {"kind": "calibrated_probability", "confidence": .8, "calibration": {"status": "calibrated"}},
    {"kind": "cosine_similarity", "confidence": .8, "calibration": {"status": "uncalibrated"}},
    {"kind": "heuristic", "raw_score": float("nan"), "calibration": {"status": "uncalibrated"}},
    {"kind": "logit", "raw_score": float("inf"), "calibration": {"status": "uncalibrated"}},
])
def test_score_cannot_masquerade_as_calibrated_probability(score):
    with pytest.raises(ContractError):
        validate("Score", score)


def test_slice_context_bounds():
    doc = {"schema_version": "audio-slice/1.0", "track_id": "trk_1", "pcm_sha256": "a" * 64,
           "sample_rate_hz": 48000, "master_sample_count": 100, "start_sample": 0, "end_sample": 100,
           "core_start_sample": 10, "core_end_sample": 90}
    validate("AudioSliceRef", doc)
    doc["core_end_sample"] = 101
    with pytest.raises(ContractError):
        validate("AudioSliceRef", doc)


def test_duplicate_observation_ids_rejected():
    doc = observation_set()
    doc["observations"].append(copy.deepcopy(doc["observations"][0]))
    with pytest.raises(ContractError):
        validate("ObservationSet", doc)
