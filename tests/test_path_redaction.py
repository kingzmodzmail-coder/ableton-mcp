"""Phase 0 / gate R0: the dataset must not record identifying paths.

A relative, separator-clean, extension-free path used to be accepted as a Live
browser category. That let client names, label names and project titles reach
diagnostic logs and the training set verbatim.
"""

import pytest

from MCP_Server.dataset.trajectory_decorator import _extract_params, _is_browser_path


@pytest.mark.parametrize("value", [
    "Drums/Kits/808 Core Kit",
    "Sounds/Bass/Analog Sub",
    "drums/kits/909",                      # roots are case-insensitive
    "User Library/Remote Scripts",
    "Plug-ins/VST3",
])
def test_genuine_browser_paths_are_kept(value):
    assert _is_browser_path(value) is True


@pytest.mark.parametrize("value", [
    "Projects/ClientName/Stems",           # the leak named in the audit
    "OneDrive/Label/unreleased",
    "Google Drive/Masters/2026",
    "Music/Ableton/Gabber time Remastered",
    "Documents/Ableton/User Library",      # real root is not the first segment
    "C:/Users/Gebruiker/Music",
    "/Users/ryan/Music/stems",
    "~/Music/secret project",
    "\\\\NAS\\share\\stems",
    "Drums/Kits/my kick.wav",              # a file, not a category
])
def test_identifying_paths_are_rejected(value):
    assert _is_browser_path(value) is False


def test_rejected_path_is_reduced_to_extension_only():
    """A redacted path must leave nothing but its shape behind."""
    params = _extract_params({"path": "Projects/AcidCorp/Stems/kick.wav"})
    assert params["has_path"] is True
    assert params["file_extension"] == ".wav"
    assert "browser_path" not in params
    assert not any(
        isinstance(v, str) and "AcidCorp" in v for v in params.values())


def test_accepted_browser_path_is_recorded():
    params = _extract_params({"path": "Drums/Kits/808 Core Kit"})
    assert params["browser_path"] == "Drums/Kits/808 Core Kit"
    assert "has_path" not in params


def test_empty_and_oversized_paths_rejected():
    assert _is_browser_path("") is False
    assert _is_browser_path("Drums/" + "x" * 600) is False
