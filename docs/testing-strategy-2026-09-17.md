# Testing strategy — ableton-mcp / producer core

## Method

This is grounded in the actual repo, not a generic template: current test
files and counts (`tests/*.py`, raw `def test_` counts, so parametrized
cases run higher — pytest reported 95 passed on 2026-09-16 against 68 raw
test functions), current source file sizes, and the specific regressions
already caught and fixed per `docs/audit-2026-09-15.md` and
`docs/audit-2026-09-16.md`. Those audits are the best available signal for
"what actually breaks here" — every gap below is prioritized against a bug
that has already shipped once, not a hypothetical.

No coverage tool is wired in (`pytest-cov` isn't a dependency, no
`[tool.pytest.ini_options]` in `pyproject.toml`). Test *counts* below are a
proxy, not a coverage measurement — a file with 2 tests can still exercise
most of its lines if they're integration-style; a file with 34 can still
miss branches. First recommendation, before anything else: add
`pytest-cov` and get a real baseline.

## Current state (2026-09-17)

| Source file | Lines | Test file | Test fns | Note |
|---|---|---|---|---|
| `MCP_Server/server.py` | 1399 | `test_clip_notes.py` + `test_bridge_transport.py` | 14 | ~24 `@mcp.tool()` entry points; only clip/notes and the transport class have dedicated tests |
| `MCP_Server/bundled_ableton_remote_script/AbletonMCP_init.py` | 2377 | none | 0 | Runs inside Live's embedded interpreter; largest file in the repo, zero direct tests |
| `MCP_Server/producer/engine.py` | 327 | `test_producer.py` | 34 | Best-covered module; prepare/apply/undo/recover |
| `MCP_Server/producer/capture.py` | 175 | (shared w/ above) | — | Audit-flagged bug here (missing `clean_capture` accepted as valid) |
| `MCP_Server/producer/audio.py` | 136 | (shared w/ above) | — | Metrics: peak/RMS/crest/band energy |
| `MCP_Server/producer/tools.py` | 106 | (shared w/ above) | — | The `producer_*` MCP tool wrappers |
| `MCP_Server/producer/cli.py` | 59 | none | 0 | `prepare/apply/undo/recover/capture/cycle/devices/analyze` |
| `MCP_Server/producer/store.py` | 58 | none | 0 | SQLite locking/journal — audit-flagged connection-leak history |
| `MCP_Server/remote_script_install.py` | 291 | `test_remote_script_install.py` | 2 | Two shipped bugs here already (force-replace bridge family, backup collisions) against 2 tests |
| `MCP_Server/script_handshake.py` | 107 | none | 0 | Audit-flagged bug: missing `get_script_info` wrongly read as "script is stale" |
| `MCP_Server/telemetry.py` + `telemetry_decorator.py` | 335 + 238 | none | 0 | Audit-flagged bug: queued private fields sent after consent revoked |
| `MCP_Server/dataset/recorder.py` | 715 | none | 0 | Two shipped bugs here (NaN/Inf samples to PCM, unbounded file read before size check) |
| `MCP_Server/dataset/consent.py` | 202 | `test_dataset_consent.py` | 10 | Well covered — matches the per-process consent-cache bug already fixed |
| `MCP_Server/dataset/schema.py` | 229 | none | 0 | |
| `MCP_Server/dataset/trajectory_decorator.py` | 398 | none | 0 | |
| `MCP_Server/dataset/hierarchy.py` / `passive_poller.py` / `snapshot.py` / `supabase_client.py` | 137/100/78/73 | none | 0 | |

## Testing pyramid for this repo

```
        /  Live E2E  \    A handful, manual/gated: real Ableton + real script,
       /  (see below)  \  run before any bridge/install change ships
      / Contract tests  \  Bridge JSON schema (v1.7.0 full vs v1.8.0 compact
     /   (bridge <-> MCP)\ snapshot), both must be recognized correctly
    /--------------------\
   /   Integration tests   \  socket transport against a fake TCP server,
  /  (no real Ableton)      \  SQLite store against a temp DB, telemetry
 /----------------------------\ queue against a fake sink
/   Unit tests (majority)      \ pure functions: audio metrics, snapshot
---------------------------------- validation, consent state machine, CLI arg parsing
```

The "Live E2E" tier is unusual for this repo and worth calling out
explicitly: a real correctness bug here is a live audio/MIDI action inside
someone's actual project, so the top tier isn't optional polish, it's risk
containment for anything that writes to a real Live Set.

## Priority gaps, ranked

1. **Remote Script bridge contract (`AbletonMCP_init.py`, 2377 lines, 0 tests).**
   This is where the live v1.7.0/v1.8.0 mismatch actually lives, and it's
   the single largest untested surface in the repo. You can't easily unit
   test code running inside Live's interpreter, but you *can* contract-test
   the JSON it emits: capture one real `get_session_info` response from
   each bridge version as a fixture, and assert `script_handshake.py` and
   `producer/engine.py` both classify them correctly (full v2 vs compact)
   instead of guessing from a version string.
2. **`remote_script_install.py` (291 lines, 2 tests, 2 shipped bugs).**
   The worst ratio in the repo, and the two bugs it already shipped
   (`--force` replacing the wrong bridge family; backup name collisions)
   are exactly the kind of thing a parametrized test over "which bridge
   family is currently installed" x "which flag is passed" would have
   caught before it shipped, not after.
3. **`dataset/recorder.py` (715 lines, 0 tests, 2 shipped bugs).**
   NaN/Inf samples reaching PCM, and full-file reads before a size check —
   both are pure-function-testable with synthetic arrays, no audio hardware
   needed. This is the biggest LOC/test-count gap in the repo.
4. **`script_handshake.py` (107 lines, 0 dedicated tests).**
   Already shipped the "missing `get_script_info` doesn't prove staleness"
   bug. Small file, cheap to fully cover, currently isn't.
5. **`telemetry.py` / `telemetry_decorator.py` (573 lines combined, 0 tests).**
   Already shipped a privacy-relevant bug (stale queued data sent post
   revocation). This touches what leaves the machine — worth treating like
   a security boundary, not just another module.
6. **`producer/store.py` (58 lines, 0 dedicated tests).**
   Small, but it's the SQLite layer backing every producer guarantee
   (undo, journal, cross-process locking). A small file with zero tests
   that everything else depends on is a bad combination.

## Strategy by component

**`server.py` tool wrappers (create_midi_track, set_tempo, load_instrument_or_effect, playback control, arrangement view, etc.)**
Unit test the parameter validation and response-shaping in isolation by
mocking `AbletonConnection.send_command`; you don't need real Ableton to
verify that `create_audio_track` rejects a bad index or that
`get_browser_items_at_path` surfaces the underlying error message instead
of swallowing it. Reserve real-socket tests for the transport class itself
(already partially done in `test_bridge_transport.py`) and real-Ableton
tests for the small "does this actually create a track" smoke layer.

**`AbletonMCP_init.py` (the Live-side script)**
Contract tests, not unit tests: fixture-capture real responses per bridge
version, assert shape. Add one regression fixture per future bridge
version bump so "does this response still parse" is a one-line assertion
instead of a live debugging session next time.

**`producer/engine.py`, `capture.py`, `audio.py`**
Keep unit-testing the reversible-edit logic against fakes (current
approach, well covered). Add synthetic-signal tests for `audio.py`'s
metrics (a known sine wave should produce a known RMS/peak/crest within
tolerance) so a future refactor of the metrics math has a ground truth to
check against, not just "did it run."

**`dataset/recorder.py`, `schema.py`, `trajectory_decorator.py`**
Pure unit tests with synthetic/malformed input: NaN arrays, Inf arrays,
zero-length arrays, oversized arrays (past the 256 MiB cap), truncated
JSON against the schema validator. None of this needs a soundcard.

**`remote_script_install.py`, `script_handshake.py`**
Table-driven tests: matrix of (installed bridge family) x (requested
action: install/force/reinstall) x (expected outcome: proceed/refuse).
This is exactly the shape of test that would have caught both shipped
installer bugs.

**Live E2E tier**
A short, manual (or CI-gated-behind-a-flag) checklist: connect to a real
Live instance, create one track, one clip, set tempo, tear down. Run this
before shipping any change to the transport layer, the installer, or the
bundled remote script — the three places a mistake reaches a real project.

## Example test cases for the top three gaps

- `test_handshake_recognizes_v2_full_snapshot()` — feed the v1.7.0 fixture,
  assert `producer` accepts it.
- `test_handshake_rejects_compact_snapshot_explicitly()` — feed the v1.8.0
  fixture, assert a clear, typed refusal (not a generic exception) —
  this is the exact case your own audit hit live.
- `test_install_refuses_force_across_bridge_families()` — installed =
  1.8.0, requested = force-install 1.7.0 bundle, assert refusal +
  no file written.
- `test_install_backup_names_never_collide()` — run install twice in the
  same second, assert both backups exist under distinct names.
- `test_recorder_rejects_nan_samples()` / `test_recorder_rejects_inf_samples()`
  — synthetic numpy arrays, assert rejection before any PCM conversion.
- `test_recorder_enforces_256mib_cap_before_full_read()` — assert the size
  check happens without reading the whole file into memory (this was the
  race the audit fixed; a regression test should assert the *order* of
  operations, not just the outcome, e.g. via a mock that fails the read if
  called before the size check).

## Coverage targets (phased, not a single number)

Setting a blanket "80% coverage" target on this repo would be misleading —
`AbletonMCP_init.py` genuinely can't be unit-tested the way `audio.py` can.
Phase instead:

1. **Now:** add `pytest-cov`, run it once, record the real baseline per
   file. No target yet — you need the number before you can target it.
2. **Next:** every file in the "priority gaps" list above gets at least
   one test file and >70% line coverage on its pure-logic functions
   (explicitly excluding real-socket/real-hardware paths).
3. **Ongoing:** any audit-caught bug from here forward ships with a
   regression test in the same change, no exceptions — this is the
   cheapest coverage you'll ever buy, since you've already done the hard
   part (finding the bug).

## Immediate next steps

1. `pip install pytest-cov` (already have `test` extras via `.[test]`;
   add it there), run `pytest --cov=MCP_Server --cov-report=term-missing`.
2. Capture one real fixture snapshot from each bridge version (1.7.0 and
   1.8.0) the next time both are reachable — this unblocks the contract
   tests in gap #1 and stops the bridge-mismatch issue from being
   re-diagnosed from scratch every audit cycle.
3. Start with `script_handshake.py` (gap #4) — smallest file, cheapest
   full-coverage win, and directly de-risks the exact problem blocking
   `mental-acid-001`/producer work right now.
