# Ableton producer: project brain and audio feedback

The existing chat agent is the producer. This module gives it persistent local
project state, bounded edit plans, a durable inverse-edit journal and measured
A/B previews. It uses the existing AbletonMCP Remote Script on port 9877.

## Run locally

Use Python 3.10+. Verify the selected interpreter with `python --version`;
prefer `.venv/Scripts/python.exe` from the repository for installed dependencies.

```powershell
.venv/Scripts/python.exe -m pip install -e '.[producer,test]'
.venv/Scripts/python.exe -m MCP_Server.producer.cli --project .producer sync
.venv/Scripts/python.exe -m MCP_Server.producer.cli --project .producer context
```

`.producer/project.sqlite3` contains named snapshots, song metadata, taste,
decisions, feedback, plans, execution journals and analyses. Retained WAVs live
under `.producer/audio`. These files stay local. Snapshots contain device
parameters and MIDI, but are **not ALS saves or full-set restore points**.

The existing MCP server now registers 13 `producer_*` tools. Restart that MCP
server to discover them. Producer edits require a full `ableton_mcp_snapshot_v2`
with notes and parameters. The alternative bridge 1.8.0 compact snapshot does
not satisfy this contract; do not replace that bridge solely on its version number. Set
`ABLETON_PRODUCER_HOME` to an absolute per-project directory in its environment;
otherwise MCP uses `~/.ableton-producer`. CLI defaults to `.producer`.

`start-producer-mcp.ps1` launches the MCP server with this repository's `.producer`
directory. Example MCP configuration for this machine:

```json
{
  "mcpServers": {
    "AbletonProducer": {
      "command": "C:/Users/Gebruiker/ableton-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "MCP_Server.server"],
      "env": {"ABLETON_PRODUCER_HOME": "C:/Users/Gebruiker/ableton-mcp/.producer"}
    }
  }
}
```

Use this in place of an existing Ableton MCP entry so both access the same brain.
The CLI can already use it directly from this checkout without an MCP restart.

## Agent workflow

1. `producer_context` retrieves the song, taste and prior verdicts. `producer_sync`
   captures current Live state. Store song metadata with `producer_set_profile`.
2. The chat model reasons about an eight-bar section and calls `producer_prepare`
   with explicit operations. The returned plan contains exact old values and
   inverse edits, plus a full baseline snapshot.
3. `producer_apply` verifies the baseline has not changed, executes once and
   reads back each result. Or use `producer_cycle` for capture A → apply →
   capture B → measured comparison.
4. Audition the retained A/B files. `producer_compare` supplies a gain offset for
   RMS-matched listening and measured changes. Record the user's or critic's
   verdict with `producer_remember` linked to the comparison/run.
5. Keep the edit, call `producer_undo`, or plan the next small improvement. The
   model supplies musical reasoning; no separate API key or second LLM is used.

Memory categories distinguish lasting `taste`, per-song `song`, `decision`,
`problem`, `todo`, and linked `accepted`/`rejected` feedback. A different track's
tempo or a tutorial example must not silently replace the current song's settings.

## Supported reversible actions

| Tool in action JSON | Fields | Scope |
| --- | --- | --- |
| `set_tempo` | `tempo` | Whole song |
| `set_device_parameter` | `track_index`, `device_index`, `parameter_index`, `value` | Track device, global over time |
| `replace_midi_notes` | `track_index`, `clip_index`, `notes` | Existing Session clip, at most eight bars |
| `create_midi_clip` | `track_index`, `clip_index`, `length`, `name`, `notes` | Empty existing MIDI Session slot |

Indices are zero-based; lengths and note times are quarter-note beats. Notes
contain `pitch`, `start_time`, `duration`, `velocity`, optional `mute`. One action
per target per plan. `start_beat` describes the intended song section; it does
not turn a parameter change into Arrangement automation. Creating a Session
clip does not place it in Arrangement.

Automated/disabled parameters and existing probabilistic/expressive MIDI notes
are rejected because the installed five-field note writer cannot restore them
faithfully. New tracks, device deletion, arbitrary commands, arrangement
replacement and automation writing remain available only through other existing
bridge tools, outside this journal's undo guarantees.

`producer.example.json` documents the schema. Inspect your actual tracks/slots
before preparing it; the example slot may not exist or may already be occupied.

```powershell
.venv/Scripts/python.exe -m MCP_Server.producer.cli prepare plan.json
.venv/Scripts/python.exe -m MCP_Server.producer.cli apply PLAN_ID
.venv/Scripts/python.exe -m MCP_Server.producer.cli undo RUN_ID
```

## Capture and compare

List output devices with `devices`. Select the output Ableton actually uses.
WASAPI output loopback includes other audio on that device; ASIO output may not
appear there. This is a **realtime Session loop audition**, not Live's offline
export, sample-accurate Arrangement rendering, or an automatic mastering system.
Its two-bar preroll is intended for repeating grooves, not one-shot transitions.

Write `clips.json` containing explicit selections, for example:

```json
[{"track_index":0,"clip_index":6},{"track_index":2,"clip_index":6}]
```

```powershell
.venv/Scripts/python.exe -m MCP_Server.producer.cli devices
.venv/Scripts/python.exe -m MCP_Server.producer.cli capture clips.json --label baseline --bars 8 --device 'Realtek HD Audio 2nd output'
.venv/Scripts/python.exe -m MCP_Server.producer.cli cycle clips.json --plan PLAN_ID --device 'Realtek HD Audio 2nd output'
```

Start with transport stopped, recording and Arrangement looping off, and selected tracks disarmed. Capture moves beyond
existing Arrangement audio, starts the chosen clips, waits two bars, captures
1–8 bars, then stops and restores the previous playhead and launched slots.
It does not restore clip playback phase. A separate recorder process has a
deadline; capture failures attempt transport cleanup. An OS/process crash still
requires stopping Live manually. Do not interact with Live during a cycle.

For an exported preview use `analyze WAV --label NAME --bpm BPM --version VERSION_ID`.
Export integer PCM WAV (8/16/24/32-bit). Use matching section, tempo, source and
duration for comparisons. Imported files are retained by content hash, so
overwriting the original does not change past comparisons.

Metrics: sample peak, RMS, crest factor, fraction near full scale, DC offset,
stereo correlation, approximate spectral energy bands and full-bar RMS.
Discontinuities during preroll are logged separately from warnings during the
measured audio. Warnings during the measured portion block A/B judgment.

These are **not integrated LUFS or oversampled true peak**. No metric alone
determines whether the kick, groove or style is good. Silence blocks a cycle
before editing; louder audio is never automatically labeled better.

## Failures and recovery

A journal entry is committed before each mutation. Timed-out writes are never
retried automatically. `producer_context` exposes unresolved runs, which block
new plans from applying. `producer_recover`/CLI `recover RUN_ID` checks whether
each target matches its saved before state or the intended after state and
restores provable changes. Partial/conflicting targets remain blocked: inspect
the retained before/inverse values, repair the target, then reconcile again.

Undo refuses to overwrite later edits to the same targets. If capture B fails,
the edit remains applied and the cycle returns its run ID for a capture retry
or undo. Model/user acceptance is recorded separately from execution success.

## Scope and follow-up

This is the first producer core, not the full multi-agent/dashboard architecture.
The chat model plans and critiques; specialist agents, a persistent autonomous
scheduler, sample-library search, an audio listening model, Arrangement rendering,
LUFS/true-peak mastering and a dashboard remain separate follow-up work.

Tests: `.venv/Scripts/python.exe -m pytest tests -q`.
Audio capture follows the [SoundCard API](https://soundcard.readthedocs.io/en/latest/).

## Quality bar: the Suno v6 benchmark

Every render is judged by `docs/SUNO_V6_BENCHMARK.md`: hard rules (true-peak
ceiling, low-end mono, kick owns 30-120 Hz) plus a reference profile built
from approved Suno v6 renders, then a blind loudness-matched A/B. Run
`producer_preflight` before a build and `ear_qc` after every capture; a failed
gate means fix and re-capture, never post. The mix ear lives in
`MCP_Server/producer/ear/`, the stages in `MCP_Server/producer/pipeline/`.
