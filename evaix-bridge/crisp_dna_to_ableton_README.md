# CRISP DNA → Ableton Live

Pipeline: **Kickback synth DNA** → **Electribe Sample Master (esx-1)** → **Ableton one-shots / MIDI / loops**.

## DNA (forced Mental @ 162)

From `CRISPTEK/src/lib/audio/kickback.ts` genre `mental` (defaults bpm 168 — **this bridge uses 162**):

| Param | Value |
|-------|--------|
| kick | sledge |
| acid | screech |
| perc | shuffle |
| grit | full |
| sidechain | off (kick *is* the bass) |
| loudness | club ≈ −9 LUFS |

## Master chain

Same as `attachments/convert-electribe.sh` **esx-1**:

```
ffmpeg -af "highpass=f=30,alimiter=limit=0.94,aresample=44100:resampler=soxr" -ac 1 -ar 44100 -sample_fmt s16
```

Applied to Kickback one-shots and ESX factory one-shots (`146_SinKick`, HH, `092_JunkPerc`). Outputs: `samples/crisp-dna/`.

## Ableton load

- Tempo **162**
- Scenes: **Intro → Drop → Break → Peak** (rows 0–3)
- Audio: Kickback DNA loops (not raw unmastered ESX dumps)
- MIDI: screech acid on **Drift** (`Acid 303 Poly`)
- **E-Mental / E-Atm / E-Syn** silenced
- Fires **Drop**, `is_playing` true

## Run

```bat
python C:\Users\Gebruiker\ableton-mcp\evaix-bridge\crisp_dna_to_ableton.py
```

Requires AbletonMCP TCP `127.0.0.1:9877` and ffmpeg.

## Listen bounce

`C:\Users\Gebruiker\Downloads\EvAIx_CRISP_DNA_Ableton_162.mp3`
