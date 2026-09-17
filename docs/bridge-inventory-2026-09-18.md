# Remote Script bridge inventory — 18 September 2026

Measured on DESKTOP-4O4CU12 while Live was **not** running, so nothing was
loaded or locked at the time.

| Location | Version | Size | Notes |
|---|---|---|---|
| `C:\Users\Gebruiker\Documents\Ableton\User Library\Remote Scripts\AbletonMCP\__init__.py` | **1.7.1** (deployed today) | 115,567 B | Writable. Installer wrote it and kept a unique `.bak` of the previous 1.7.0. |
| `C:\Users\Gebruiker\OneDrive\Documents\Ableton\User Library\Remote Scripts\AbletonMCP\__init__.py` | 1.7.0 (unpatched, 15 Sept) | 112,520 B | **This is the copy Live actually loaded** — its `__pycache__` holds a `cpython-311` .pyc from 17 Sept 03:45, and Live 12.4.x embeds Python 3.11. Writes are denied here (see below). |
| `C:\ProgramData\Ableton\Live 12 Intro\Resources\MIDI Remote Scripts\AbletonMCP\__init__.py` | 1.8.0 (other bridge family) | 114,747 B | Belongs to the **Live 12 Intro** install. Left untouched. Its compact snapshot is the contract the producer refuses. |

Windows redirects `Documents` to `OneDrive\Documents` (`HKCU\...\User Shell
Folders\Personal`), which is why Live's User Library resolves inside OneDrive.

## The blocker

Every write into the OneDrive User Library is refused — creating a file fails
with "Could not find file" and overwriting `__init__.py` with "Access to the
path is denied", even after clearing the read-only flag. The folder carries
`ReadOnly, Directory, Archive, ReparsePoint`. That is OneDrive/Defender
protection on a known folder, not a repo problem, and it cannot be fixed from
a shell.

## Recommended fix (about a minute, in Live)

Preferences -> Library -> "Location of User Library" -> Browse to
`C:\Users\Gebruiker\Documents\Ableton\User Library` (the non-OneDrive path,
which already holds 1.7.1), then restart Live. This:

- makes the deployed script the one Live loads,
- removes the two-copy skew the workspace review flagged,
- keeps live audio projects and scripts out of OneDrive sync, which is the
  standing recommendation anyway.

Then verify: `python -m MCP_Server.producer.cli preflight` should report
`script_version` 1.7.1 and a full v2 snapshot.

If you would rather keep the User Library inside OneDrive, allow the copy
through instead (Windows Security -> Ransomware protection -> Controlled
folder access -> allow an app, or pause OneDrive) and re-run
`python -m MCP_Server.remote_script_install --force`.

## Live 12 Intro

A previous cloud session launched **Live 12 Intro**, which loads the 1.8.0
bridge from its own ProgramData folder. Build with **Suite**; if Intro is
opened, expect the compact-snapshot refusal. Deciding what to do with that
1.8.0 file is a separate call — the installer deliberately refuses to
overwrite it across bridge families.
