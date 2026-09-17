"""Regression tests for Live process detection in producer_preflight.

Two defects this pins:

* substring counting. The old check looked for "ableton live.exe" and
  "live.exe" inside the whole tasklist output. The real executable is
  "Ableton Live 12 Suite.exe", which contains neither, so the count was 0 with
  Live running and producer_preflight always reported failure. A name that did
  match ("Ableton Live.exe") matched *both* patterns and counted twice.
* a dead exclusion list. LIVE_PROCESS_EXCLUDE held "ableton index.exe" and
  "abletonaudiocpl.exe", but the filter required the "ableton live " prefix,
  which neither has — so the exclusions could never fire, and a helper that
  *did* carry the prefix would have been counted as a second DAW.

subprocess.run is stubbed with CSV fixtures: no real process listing, so the
result does not depend on what happens to be running.
"""
import subprocess

import pytest

from MCP_Server.producer import preflight


def _tasklist_csv(*images):
    """One CSV row per image name, in tasklist /fo csv /nh shape."""
    return "".join(
        '"%s","%d","Console","1","1,149,400 K"\n' % (image, 1000 + i)
        for i, image in enumerate(images)
    )


@pytest.fixture
def fake_tasklist(monkeypatch):
    """Install a canned tasklist output and force the Windows branch."""
    def _install(*images, returncode=0):
        monkeypatch.setattr(preflight.sys, "platform", "win32")

        def _run(cmd, **kwargs):
            assert cmd[:1] == ["tasklist"], cmd
            return subprocess.CompletedProcess(
                cmd, returncode, stdout=_tasklist_csv(*images), stderr=""
            )

        monkeypatch.setattr(preflight.subprocess, "run", _run)
    return _install


# Real listing from a machine running Live 12 Suite: the DAW plus the two
# helpers Ableton ships. This exact set returned 0 before the fix.
REAL_LISTING = (
    "System Idle Process",
    "AbletonAudioCpl.exe",
    "Ableton Live 12 Suite.exe",
    "Ableton Index.exe",
    "chrome.exe",
)


def test_the_real_listing_counts_exactly_one(fake_tasklist):
    fake_tasklist(*REAL_LISTING)
    assert preflight.live_process_count() == 1


@pytest.mark.parametrize("image", [
    "Ableton Live 12 Suite.exe",
    "Ableton Live 11 Standard.exe",
    "Ableton Live 12 Lite.exe",
    "Ableton Live 10 Intro.exe",
    "Ableton Live 12 Trial.exe",
])
def test_every_edition_counts(fake_tasklist, image):
    fake_tasklist(image)
    assert preflight.live_process_count() == 1


@pytest.mark.parametrize("image", [
    "Ableton Index.exe",
    "AbletonAudioCpl.exe",
    "Ableton Live 12 Suite Helper.exe",
    "Ableton Live 12 CrashHandler.exe",
    "Ableton Live 12 Installer.exe",
    "Ableton Live Updater.exe",
    "notepad.exe",
    "live.exe",
    "ableton live.exe",
])
def test_helpers_and_lookalikes_do_not_count(fake_tasklist, image):
    fake_tasklist(image)
    assert preflight.live_process_count() == 0


def test_two_editions_running_are_both_counted(fake_tasklist):
    """The check exists to catch exactly this: two DAWs fighting for the socket."""
    fake_tasklist("Ableton Live 12 Suite.exe", "Ableton Live 11 Standard.exe")
    assert preflight.live_process_count() == 2


def test_the_same_edition_twice_is_counted_twice(fake_tasklist):
    fake_tasklist("Ableton Live 12 Suite.exe", "Ableton Live 12 Suite.exe")
    assert preflight.live_process_count() == 2


@pytest.mark.parametrize("image", [
    "ABLETON LIVE 12 SUITE.EXE",
    "ableton live 12 suite.exe",
    "AbLeToN LiVe 12 SuItE.eXe",
    "  Ableton Live 12 Suite.exe  ",
])
def test_casing_and_surrounding_space_do_not_matter(fake_tasklist, image):
    """tasklist casing is not a contract; neither is column padding."""
    fake_tasklist(image)
    assert preflight.live_process_count() == 1


def test_a_helper_alongside_the_daw_still_counts_one(fake_tasklist):
    """The case the dead exclusion list was meant to cover."""
    fake_tasklist("Ableton Live 12 Suite.exe", "Ableton Live 12 Suite Helper.exe")
    assert preflight.live_process_count() == 1


def test_nothing_running_is_zero_not_none(fake_tasklist):
    fake_tasklist("explorer.exe")
    assert preflight.live_process_count() == 0


def test_non_windows_reports_unknown_rather_than_guessing(monkeypatch):
    monkeypatch.setattr(preflight.sys, "platform", "darwin")
    assert preflight.live_process_count() is None


def test_a_failing_tasklist_reports_unknown(monkeypatch):
    monkeypatch.setattr(preflight.sys, "platform", "win32")

    def _boom(cmd, **kwargs):
        raise OSError("tasklist unavailable")

    monkeypatch.setattr(preflight.subprocess, "run", _boom)
    assert preflight.live_process_count() is None


def test_unknown_count_passes_the_check_instead_of_blocking(monkeypatch):
    """On a platform we cannot enumerate, say so — do not fail the build."""
    monkeypatch.setattr(preflight, "live_process_count", lambda: None)
    monkeypatch.setattr(preflight, "ask_bridge",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no bridge")))
    checks = {c["check"]: c for c in preflight.run()["checks"]}
    assert checks["single_live_instance"]["status"] == "pass"
    assert "cannot enumerate" in checks["single_live_instance"]["detail"]
