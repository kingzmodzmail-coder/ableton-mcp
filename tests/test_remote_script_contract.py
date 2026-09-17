"""Regression tests for the Ableton Remote Script bridge (audit 2026-09-17).

Each test here pins a defect that shipped once:

* every command the dispatcher routes must have a handler
  (``get_browser_categories`` / ``get_browser_items`` raised AttributeError),
* a note without ``start_time`` must fail instead of landing on beat zero,
* ``create_locator`` must accept Live snapping the stopped playhead,
* ``save_set`` must refuse clearly when Live exposes no save API,
* both copies of the script must stay byte-identical and match the version
  the installer expects.

The script normally runs inside Live's interpreter, so ``_Framework`` is
stubbed and the class is instantiated without ``__init__`` (which would open
a socket). No Ableton, no network.
"""

import ast
import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_SCRIPT = REPO_ROOT / "AbletonMCP_Remote_Script" / "__init__.py"
BUNDLED_SCRIPT = (REPO_ROOT / "MCP_Server" / "bundled_ableton_remote_script"
                  / "AbletonMCP_init.py")

BASE_CONTROL_SURFACE_METHODS = {
    "application", "log_message", "schedule_message", "show_message", "song",
}


def _load_script_module():
    """Import the Live-side script with _Framework stubbed out."""
    framework = types.ModuleType("_Framework")
    control_surface_mod = types.ModuleType("_Framework.ControlSurface")

    class _StubControlSurface(object):
        def __init__(self, *args, **kwargs):
            pass

        def log_message(self, *args, **kwargs):
            pass

        def show_message(self, *args, **kwargs):
            pass

    control_surface_mod.ControlSurface = _StubControlSurface
    framework.ControlSurface = control_surface_mod
    sys.modules.setdefault("_Framework", framework)
    sys.modules.setdefault("_Framework.ControlSurface", control_surface_mod)

    spec = importlib.util.spec_from_file_location(
        "ableton_mcp_remote_script_under_test", BUNDLED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script_module():
    return _load_script_module()


class FakeCue(object):
    def __init__(self, time, name=""):
        self.time = time
        self.name = name


class FakeSong(object):
    """Minimal Song double. ``snap_to`` mimics Live quantising the playhead."""

    def __init__(self, snap_to=None, cues=None, is_playing=False,
                 create_cue=True):
        self._current_song_time = 0.0
        self.snap_to = snap_to
        self.cue_points = list(cues or [])
        self.is_playing = is_playing
        self.create_cue = create_cue
        self.name = "Test Set"
        self.saved = 0

    @property
    def current_song_time(self):
        return self._current_song_time

    @current_song_time.setter
    def current_song_time(self, value):
        self._current_song_time = self.snap_to if self.snap_to is not None else value

    def set_or_delete_cue(self):
        if self.create_cue:
            self.cue_points.append(FakeCue(self._current_song_time))

    def save_set(self):
        self.saved += 1


def make_instance(script_module, song=None, application=None):
    inst = script_module.AbletonMCP.__new__(script_module.AbletonMCP)
    inst._song = song
    inst.application = lambda: application
    inst.log_message = lambda *a, **k: None
    inst.show_message = lambda *a, **k: None
    return inst


# ---------------------------------------------------------------- dispatcher

def test_every_dispatched_command_has_a_handler():
    """Regression: get_browser_categories/get_browser_items had no method."""
    tree = ast.parse(REPO_SCRIPT.read_text(encoding="utf-8"))
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    called = {
        n.func.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "self"
    }
    assert not (called - defined - BASE_CONTROL_SURFACE_METHODS)


def test_repo_and_bundled_copies_are_identical():
    assert REPO_SCRIPT.read_bytes() == BUNDLED_SCRIPT.read_bytes()


def _installer_expected_version():
    """Read the constant without importing MCP_Server (whose deps need the venv)."""
    tree = ast.parse((REPO_ROOT / "MCP_Server" / "remote_script_install.py")
                     .read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Name)
                        and target.id == "EXPECTED_REMOTE_SCRIPT_VERSION"):
                    return node.value.value
    raise AssertionError("EXPECTED_REMOTE_SCRIPT_VERSION not found")


def test_script_version_matches_installer_expectation(script_module):
    assert script_module.SCRIPT_VERSION == _installer_expected_version()


def test_new_commands_are_advertised_as_capabilities(script_module):
    for command in ("get_browser_categories", "get_browser_items", "save_set"):
        assert command in script_module.SCRIPT_CAPABILITIES


# ------------------------------------------------------------------- notes

class FakeClip(object):
    def __init__(self):
        self.notes = None

    def set_notes(self, notes):
        self.notes = notes


class FakeClipSlot(object):
    def __init__(self):
        self.has_clip = True
        self.clip = FakeClip()


class FakeTrack(object):
    def __init__(self):
        self.clip_slots = [FakeClipSlot()]


def song_with_one_clip():
    song = FakeSong()
    song.tracks = [FakeTrack()]
    return song


def test_add_notes_rejects_note_without_start_time(script_module):
    song = song_with_one_clip()
    inst = make_instance(script_module, song=song)
    with pytest.raises(ValueError) as excinfo:
        inst._add_notes_to_clip(0, 0, [{"pitch": 36, "duration": 1.0}])
    assert "start_time" in str(excinfo.value)
    assert song.tracks[0].clip_slots[0].clip.notes is None


def test_add_notes_accepts_start_beat_alias(script_module):
    song = song_with_one_clip()
    inst = make_instance(script_module, song=song)
    inst._add_notes_to_clip(0, 0, [{"pitch": 36, "start_beat": 4.0}])
    assert song.tracks[0].clip_slots[0].clip.notes[0][1] == 4.0


def test_add_notes_rejects_non_numeric_and_bad_duration(script_module):
    inst = make_instance(script_module, song=song_with_one_clip())
    with pytest.raises(ValueError):
        inst._add_notes_to_clip(0, 0, [{"pitch": "kick", "start_time": 0.0}])
    with pytest.raises(ValueError):
        inst._add_notes_to_clip(0, 0, [{"start_time": 0.0, "duration": 0.0}])
    with pytest.raises(ValueError):
        inst._add_notes_to_clip(0, 0, [{"start_time": -1.0}])


def test_add_notes_keeps_explicit_start_times(script_module):
    song = song_with_one_clip()
    inst = make_instance(script_module, song=song)
    inst._add_notes_to_clip(0, 0, [
        {"pitch": 36, "start_time": 0.0},
        {"pitch": 36, "start_time": 1.5, "duration": 0.5, "velocity": 110},
    ])
    starts = [n[1] for n in song.tracks[0].clip_slots[0].clip.notes]
    assert starts == [0.0, 1.5]


# ---------------------------------------------------------------- locator

def test_locator_accepts_snapped_position_with_transport_stopped(script_module):
    """Regression: a snapped playhead produced 'Failed to create cue'."""
    song = FakeSong(snap_to=4.0)
    inst = make_instance(script_module, song=song)
    result = inst._create_locator("Drop", 4.4)
    assert result["success"] is True
    assert result["snapped"] is True
    assert result["time"] == 4.0
    assert result["requested_time"] == 4.4
    assert song.cue_points[0].name == "Drop"


def test_locator_exact_hit_is_not_marked_snapped(script_module):
    song = FakeSong()
    inst = make_instance(script_module, song=song)
    result = inst._create_locator("Intro", 8.0)
    assert (result["time"], result["snapped"]) == (8.0, False)


def test_locator_restores_playhead(script_module):
    song = FakeSong()
    song.current_song_time = 16.0
    inst = make_instance(script_module, song=song)
    inst._create_locator("Break", 32.0)
    assert song.current_song_time == 16.0


def test_locator_renames_existing_cue_without_creating_one(script_module):
    song = FakeSong(cues=[FakeCue(12.0, "old")])
    inst = make_instance(script_module, song=song)
    result = inst._create_locator("new", 12.0)
    assert len(song.cue_points) == 1
    assert (song.cue_points[0].name, result["created"]) == ("new", False)


def test_locator_error_names_transport_state_when_no_cue_appears(script_module):
    song = FakeSong(create_cue=False)
    inst = make_instance(script_module, song=song)
    with pytest.raises(Exception) as excinfo:
        inst._create_locator("Nope", 64.0)
    message = str(excinfo.value)
    assert "stopped" in message and "64.0" in message


# --------------------------------------------------------------- save_set

class FakeApplication(object):
    def __init__(self, document=None, browser=None):
        self._document = document
        self.browser = browser

    def get_document(self):
        return self._document


def test_save_set_uses_the_song_save_api(script_module):
    song = FakeSong()
    inst = make_instance(script_module, song=song, application=FakeApplication())
    result = inst._save_set(None)
    assert result["success"] is True and song.saved == 1


def test_save_set_refuses_clearly_when_no_api_exists(script_module):
    class NoSaveSong(object):
        cue_points = []

    inst = make_instance(script_module, song=NoSaveSong(),
                         application=FakeApplication())
    result = inst._save_set("D:/Music/Projects/x.als")
    assert result["success"] is False
    assert result["error"] == "save_unsupported"
    assert "Ctrl+S" in result["message"]


# ---------------------------------------------------------------- browser

def test_get_browser_items_filters_by_item_type(script_module):
    inst = make_instance(script_module)
    inst.get_browser_items_at_path = lambda path: {
        "path": path,
        "items": [
            {"name": "Kits", "is_folder": True, "is_device": False,
             "is_loadable": False},
            {"name": "Drift", "is_folder": False, "is_device": True,
             "is_loadable": True},
        ],
    }
    folders = inst._get_browser_items("instruments", "folders")
    assert [i["name"] for i in folders["items"]] == ["Kits"]
    devices = inst._get_browser_items("instruments", "devices")
    assert [i["name"] for i in devices["items"]] == ["Drift"]
    everything = inst._get_browser_items("instruments", "all")
    assert len(everything["items"]) == 2


def test_get_browser_categories_reports_available_categories(script_module):
    inst = make_instance(script_module)
    inst.get_browser_tree = lambda category_type="all": {
        "categories": [{"name": "Instruments"}],
        "available_categories": ["instruments", "sounds"],
    }
    result = inst._get_browser_categories("instruments")
    assert result["type"] == "instruments"
    assert result["available_categories"] == ["instruments", "sounds"]
    assert result["categories"][0]["name"] == "Instruments"
