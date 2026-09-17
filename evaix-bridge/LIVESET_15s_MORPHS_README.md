# EvAIx LiveSet — 15s Morphs @ 162 BPM

Electribe-style pattern launches: **8 Session scenes**, each with a **different rhythm**.

## Timing

- Tempo: **162 BPM**
- 1 bar ≈ 1.481 s
- Section length: **10 bars ≈ 14.8 s**
- Full morph bounce: ~118.5 s (8 × ~15 s)

## Scenes (rows 0–7)

| Row | Name | Rhythm |
|-----|------|--------|
| 0 | Intro_Kick | Kick 4/4 only |
| 1 | Hats_Sparse | Kick + closed hats on 1,5,9,13 |
| 2 | Hats_Shuffle | Kick + 16th hats 70/50 swing |
| 3 | Perc_Offs | + clap/perc on beats 2 & 4 (steps 5+13) |
| 4 | Full_Tribal | Kick + dense hats + OH offs + perc |
| 5 | Break_NoKick | NO kick; hats + perc + acid |
| 6 | Peak_Drive | Full + harder kick + denser perc |
| 7 | Outro_Strip | Kick only, then thin out |

Acid MIDI: muted on Intro, sparse on Hats_Sparse, open from scene 2+.

## How to play live

1. Open the set with AbletonMCP / this session loaded.
2. Fire **scene row 0** (Intro_Kick).
3. **Launch the next Session scene every 8–16 bars** (default **10 bars**), quantized to **1 bar**.
4. Mental / Atm / Syn beds stay silenced — drums + acid carry the morph.

## Listen bounce

`C:\Users\Gebruiker\Downloads\EvAIx_LiveSet_15sMorphs_162.mp3`

Layer WAVs: `evaix-bridge\samples\crisp-dna\morphs\`

## Rebuild

```bat
python C:\Users\Gebruiker\ableton-mcp\evaix-bridge\build_liveset_15s_morphs.py
```

Requires AbletonMCP TCP `127.0.0.1:9877` and ffmpeg. Reuses CRISP DNA pipeline (`crisp_dna_to_ableton.py`).
