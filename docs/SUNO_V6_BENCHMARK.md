# SUNO V6 BENCHMARK

How a build in Ableton is judged against Suno v6 output. Every agent in the
fleet applies this file; it is the definition of "done" for a track.

## What this is, and what it is not

Suno v6 is an audio-generation model: it writes a finished, mixed waveform.
The Opus 5 / Claude producer agent is a language model: it writes MIDI, device
settings, arrangements and code through the Ableton MCP bridge, and it can
neither synthesise nor hear audio. No configuration changes that.

So parity is not a setting — it is a measurement plus a listen:

1. approved **Suno v6 renders** become reference audio,
2. the agent builds in Ableton,
3. the **QC gate** measures the render against those references,
4. a **blind, loudness-matched A/B** decides.

A track is Suno-grade only when it passes both 3 and 4. Numbers alone never
make it Suno-grade, and a good number is not a good track.

## Reference set

- 10–20 Suno v6 renders that match Taste DNA: free-party acidcore / mental /
  tribe, 155–168 BPM, kick weight first, no gabber / hardstyle / trance lanes.
- **Selection and download go through the approval gate.** Inventory and list
  candidates; Hermes approves before anything is chosen, downloaded or
  exported. v6 also introduced tier-based download limits, retired the older
  models and plans watermarking, so confirm your plan's current terms before
  harvesting — that is a licensing question, not a technical one.
- Store under `Music\Reference\SunoV6\` with a manifest recording prompt,
  model variant (v6 / v6-wild / v6-mini), date and intended use.
- Keep references out of git (`.gitignore` covers audio) and back them up.

Build the profile from them:

```
python -m MCP_Server.producer.cli refprofile Music/Reference/SunoV6/*.wav \
    --bpm 162 --name suno-v6-acidcore --save-to .producer/profiles/suno-v6-acidcore.json
```

The profile records what those references measure (range plus median per
metric). It is a description, not a quality threshold.

## Hard rules (independent of any reference)

| Rule | Limit | Why |
|---|---|---|
| `true_peak_ceiling` | true peak ≤ −0.3 dBTP | Headroom for lossy encoders; clipping is not loudness. |
| `low_end_mono` | side-to-mid ≤ −6 dB below 120 Hz | Off-centre low end disappears on a big system. |
| `low_end_phase` | low-band correlation ≥ 0 | Negative correlation cancels in mono. |
| `sub_ownership` | between-kick sub ≤ −6 dB vs kick | **Kick weight first**: nothing else holds 30–120 Hz between kicks. |
| `usable_signal` | audible capture | A silent capture is a routing fault, not a mix. |

`sub_ownership` is the rule that would have caught the EvAIx_HarvestMix_162
clash: RMS and peak said "loud and not silent" while the kick and bass fought
below 120 Hz.

## Reference rules (from the profile)

Measured per render and compared against the profile range: integrated LUFS,
true peak, crest, stereo width, the five band-energy fractions
(`sub_30_80`, `low_80_250`, `mid_250_3000`, `presence_3000_6000`,
`air_6000_20000`), low-end side-to-mid, and between-kick sub level.

Integrated LUFS needs `pyloudnorm` (`pip install '.[producer]'`). Without it
the field is `None`, the gate reports the check as **unmeasured**, and an
unmeasured check blocks a pass. `allow_unmeasured` exists for diagnosis only —
never to push a render through.

## Sub ownership in the arrangement

Each section of the section map names exactly one `sub_owner`, and it must be
one of that section's elements (see `MCP_Server/producer/pipeline/sections.example.yaml`).
Where the kick plays, the kick owns the sub: bass tracks are sidechained or
volume-ducked from it, stems and pads are high-passed, and the bass bus runs
Utility Bass Mono. Where the kick is out (a break), another element may own
the sub, and the map says which.

## Blind A/B protocol

1. Loudness-match: apply the gain the comparison reports
   (`after_gain_db_for_rms_matched_audition`). **Louder is not better.**
2. At least 10 trials, order randomised, both files unlabelled.
3. Record which one you preferred each time, not a score.
4. **Parity:** the Suno reference is preferred in **no more than 60%** of
   trials. Above that, the build loses.
5. Record the verdict with `producer_remember` (category `accepted` or
   `rejected`, linked to the comparison id). An unresolved verdict blocks
   further work on that run — a pending A/B is why `mental-acid-001` stalled.

## Running the gate

```
# measure one render
python -m MCP_Server.producer.cli ear render.wav --bpm 162

# gate it against the profile
python -m MCP_Server.producer.cli qc render.wav --bpm 162 \
    --profile .producer/profiles/suno-v6-acidcore.json

# as a pipeline stage (writes a report and records the verdict)
python -m MCP_Server.producer.cli pipeline qc evaix-mental-162 render.wav \
    --bpm 162 --profile .producer/profiles/suno-v6-acidcore.json
```

From an agent: `ear_scan`, `ear_kick_bass`, `ear_qc`,
`ear_build_reference_profile`, `producer_preflight`, `pipeline_status`.
Before any build: `producer_preflight` (bridge reachable, expected script
version, full v2 snapshot, exactly one Live instance, disk headroom).

A failed gate means fix and re-capture. It is never a reason to post, share,
or report a track as finished.

## Tuning loop

- Every QC run appends its metrics and failures to the build's report
  (`.producer/pipeline/<build>.qc.json`).
- Weekly: read the most common failing check and fix the cause — a template,
  a preset, a section rule — then note the change here.
- Widen a target only with a reason recorded in the decision log, and never
  to let a specific failing render through. Adding references is the honest
  way to widen a range.
- When a blind A/B disagrees with the numbers, the numbers are incomplete:
  add a measurement, don't relax a limit.

## What the gate does not claim

It does not listen. It does not detect genre, groove, or whether the track is
any good. True peak is a 4× oversampled estimate, not a certified ITU meter;
kick/bass figures assume a kick on every beat and are meaningless without one;
band ratios do not establish musical quality. The gate exists so that the
listening you do is spent on near-finished music.
