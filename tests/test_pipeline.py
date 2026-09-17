"""Section maps, resumable state, and the stages that refuse to fake progress."""
import json
import math
import wave

import numpy as np
import pytest

from MCP_Server.producer.pipeline import (PipelineState, STAGES, SectionMapError,
                                          StageNeedsLive, StageOrderError,
                                          estimate_bpm, intake, load_section_map,
                                          publish, qc_stage, validate_section_map)
from MCP_Server.producer.pipeline import stages as stage_module

RATE = 44100


def section_map(**overrides):
    base = {
        "name": "EvAIx_Test_162",
        "bpm": 162,
        "sections": [
            {"name": "intro", "bars": 32, "elements": ["kick", "acid"], "sub_owner": "kick"},
            {"name": "main", "bars": 48, "elements": ["kick", "acid", "bass"],
             "sub_owner": "kick"},
        ],
    }
    base.update(overrides)
    return base


def write_wav(path, seconds=2.0, freq=55.0, rate=RATE, amplitude=0.5):
    t = np.arange(int(seconds * rate)) / rate
    data = (amplitude * np.sin(2 * math.pi * freq * t) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(data.tobytes())
    return path


def click_track(path, bpm=162.0, beats=32, rate=RATE):
    total = int(beats * 60.0 / bpm * rate)
    signal = np.zeros(total)
    for beat in range(beats):
        start = int(beat * 60.0 / bpm * rate)
        length = int(0.05 * rate)
        local = np.arange(length) / rate
        signal[start:start + length] += np.exp(-local * 60) * np.sin(2 * math.pi * 60 * local)
    data = (np.clip(signal, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(data.tobytes())
    return path


# -------------------------------------------------------------- section maps

def test_valid_map_is_normalised_with_bar_positions():
    result = validate_section_map(section_map())
    assert [s["start_bar"] for s in result["sections"]] == [0, 32]
    assert result["total_bars"] == 80
    assert result["total_seconds"] == pytest.approx(80 * 4 * 60 / 162, abs=0.1)
    assert result["sub_owners"] == ["kick"]


def test_section_without_a_sub_owner_is_refused():
    data = section_map()
    del data["sections"][0]["sub_owner"]
    with pytest.raises(SectionMapError) as error:
        validate_section_map(data)
    assert "sub_owner" in str(error.value)


def test_sub_owner_must_be_one_of_the_section_elements():
    data = section_map()
    data["sections"][0]["sub_owner"] = "sub_bass"
    with pytest.raises(SectionMapError):
        validate_section_map(data)


def test_duplicate_section_names_and_bad_bars_are_refused():
    data = section_map()
    data["sections"][1]["name"] = "intro"
    with pytest.raises(SectionMapError):
        validate_section_map(data)
    data = section_map()
    data["sections"][0]["bars"] = 0
    with pytest.raises(SectionMapError):
        validate_section_map(data)


def test_tempo_outside_the_allowed_range_is_refused():
    with pytest.raises(SectionMapError):
        validate_section_map(section_map(bpm=900))


def test_json_and_yaml_maps_load_identically(tmp_path):
    as_json = tmp_path / "map.json"
    as_json.write_text(json.dumps(section_map()), encoding="utf-8")
    from_json = load_section_map(as_json)
    yaml = pytest.importorskip("yaml")
    as_yaml = tmp_path / "map.yaml"
    as_yaml.write_text(yaml.safe_dump(section_map()), encoding="utf-8")
    assert load_section_map(as_yaml) == from_json


def test_shipped_example_map_is_valid():
    from pathlib import Path
    example = (Path(stage_module.__file__).parent / "sections.example.yaml")
    pytest.importorskip("yaml")
    result = load_section_map(example)
    assert result["bpm"] == 162
    # The break drops the kick, so another element may own the sub there.
    assert {s["sub_owner"] for s in result["sections"]} == {"kick", "acid_drift"}


# --------------------------------------------------------------------- state

def test_state_starts_at_the_first_stage_and_advances(tmp_path):
    state = PipelineState(tmp_path, "EvAIx Test 162")
    assert state.slug == "evaix-test-162"
    assert state.next_stage() == "intake"
    state.record("intake", "completed", {"manifest": "m.json"})
    assert state.next_stage() == "align"
    assert state.summary()["stages"]["intake"] == "completed"


def test_state_survives_being_reloaded(tmp_path):
    PipelineState(tmp_path, "b").record("intake", "completed", {"manifest": "m"})
    reloaded = PipelineState(tmp_path, "b")
    assert reloaded.artifacts("intake") == {"manifest": "m"}
    assert reloaded.next_stage() == "align"


def test_a_stage_cannot_run_before_its_predecessors(tmp_path):
    state = PipelineState(tmp_path, "b")
    with pytest.raises(StageOrderError) as error:
        state.require("qc")
    assert "intake" in str(error.value)


def test_failed_qc_leaves_the_build_unpublished(tmp_path):
    state = PipelineState(tmp_path, "b")
    for stage in STAGES[:STAGES.index("qc")]:
        state.record(stage, "completed")
    state.record("qc", "failed", {"passed": False})
    assert state.summary()["published"] is False
    with pytest.raises(StageOrderError):
        state.require("publish")


def test_unknown_stage_or_status_is_refused(tmp_path):
    state = PipelineState(tmp_path, "b")
    with pytest.raises(ValueError):
        state.record("mixdown", "completed")
    with pytest.raises(ValueError):
        state.record("intake", "probably-fine")


# -------------------------------------------------------------------- stages

def test_intake_inventories_audio_and_hashes_it(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    write_wav(inbox / "kick.wav")
    (inbox / "riff.mid").write_bytes(b"MThd\0\0\0\6")
    (inbox / "notes.txt").write_text("from the pack", encoding="utf-8")
    state = PipelineState(tmp_path / "project", "b")
    manifest = intake(inbox, state)
    assert manifest["counts"] == {"audio": 1, "midi": 1, "other": 1}
    assert len(manifest["audio"][0]["sha256"]) == 64
    assert manifest["audio"][0]["duration_seconds"] == pytest.approx(2.0, abs=0.01)
    assert state.next_stage() == "align"
    assert json.loads(open(manifest["manifest_path"], encoding="utf-8").read())


def test_intake_says_so_when_there_is_no_audio(tmp_path):
    inbox = tmp_path / "empty"
    inbox.mkdir()
    manifest = intake(inbox)
    assert manifest["counts"]["audio"] == 0 and "findings" in manifest


def test_intake_refuses_a_missing_folder(tmp_path):
    with pytest.raises(FileNotFoundError):
        intake(tmp_path / "nope")


def test_tempo_estimate_finds_the_click_tempo(tmp_path):
    from MCP_Server.producer.audio import read_wav
    samples, rate = read_wav(click_track(tmp_path / "click.wav", bpm=162.0))
    estimate = estimate_bpm(samples, rate)
    # Half-tempo is a legitimate reading of a plain click; both are accepted,
    # which is exactly why estimate_bpm returns a note instead of a verdict.
    assert (estimate["bpm"] == pytest.approx(162.0, abs=2.0)
            or estimate["bpm"] == pytest.approx(81.0, abs=2.0))
    assert estimate["confidence"] > 1.0
    assert "not a grid" in estimate["note"]


@pytest.mark.parametrize("stage", ["build", "mix", "master"])
def test_live_stages_refuse_to_run_headless(tmp_path, stage):
    state = PipelineState(tmp_path, "b")
    with pytest.raises(StageNeedsLive) as error:
        getattr(stage_module, stage)(state=state)
    assert "preflight" in str(error.value)
    assert state.status(stage) == "needs_live"


def test_qc_stage_writes_a_report_and_records_the_verdict(tmp_path):
    state = PipelineState(tmp_path / "project", "b")
    render = write_wav(tmp_path / "render.wav", seconds=3.0)
    result = qc_stage(render, 162.0, None, state)
    assert result["qc"]["passed"] in (True, False)
    assert state.status("qc") in ("completed", "failed")
    assert json.loads(open(result["report_path"], encoding="utf-8").read())["capture"]


def test_publish_refuses_a_render_that_did_not_pass_qc():
    with pytest.raises(PermissionError) as error:
        publish({"qc": {"passed": False, "failures": ["sub_ownership"]}},
                "EvAIx_Test_162", 162.0)
    assert "sub_ownership" in str(error.value)


def test_publish_message_carries_the_numbers_a_reviewer_needs():
    passed = {"qc": {"passed": True, "profile": "suno-v6-acidcore", "failures": []},
              "metrics": {"lufs_integrated": -8.4, "true_peak_dbtp": -1.1,
                          "kick_bass": {"between_to_kick_db": -11.5}}}
    message = publish(passed, "EvAIx_MentalAcid_162", 162, key="A minor",
                      file_link="D:/renders/x.wav")["message"]
    for fragment in ("EvAIx_MentalAcid_162", "162", "A minor", "-8.4", "-1.10",
                     "-11.5", "suno-v6-acidcore", "D:/renders/x.wav"):
        assert fragment in message
