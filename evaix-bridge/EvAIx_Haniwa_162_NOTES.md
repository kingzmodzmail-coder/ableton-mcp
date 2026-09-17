# EvAIx Haniwa — Vestiges slots 05–08 @ 162 F

**MP3:** `EvAIx_Haniwa_162.mp3`
- Downloads: `C:\\Users\\Gebruiker\\Downloads\\EvAIx_Haniwa_162.mp3`
- Workspace: `/workspace/EvAIx_Haniwa_162.mp3`
- Exports: `/workspace/exports/EvAIx_Haniwa_162.mp3`
- Script: `/workspace/build_haniwa_162.py`
- Bridge: `C:\\Users\\Gebruiker\\ableton-mcp\\evaix-bridge\\build_haniwa_162.py`
- Pool: `/workspace/exports/haniwa-pool/oneshots/` (38 WAVs)

Duration: **419.30 s** (~6.99 min) · BPM **162** · Key **F major** (dark filters · settle −1 from Figment F#)

## Measured loudness
- **I** = −9.0 LUFS (target −8…−9)
- **TP** = −1.1 dBFS (target ≤ −1.0 dBTP)
- **LRA** = 4.2 LU

## Mid-bloom (Figment v2 lesson applied — PASS)
- Acid muted→open shows **700Hz–3k rise** (not LF-only fail).
- Recipe: HPF acid ~160 Hz · presence 1.8–2.8 kHz · sat AFTER EQ · tame 3–6 kHz.
- Drop_mute open≈0.18 heavy LPF; Drop_open≈0.92 cutoff+presence + bus peaking.
- Surgical window EQ on Drop_open 280–339s: +1.8@900 / +2.8@1800 / +3.0@2400 / +2.2@2800 / −2.0@5200.
- Res spikes bars 4/8/12/16 on Drop_open.

## Mid-band open vs mute (measured)
| Metric | Value |
|--------|-------|
| Mute mid rel (700Hz–3k vs full) | **−21.63** dB |
| Open mid rel (700Hz–3k vs full) | **−13.30** dB |
| Delta open−mute | **+8.32 dB** (clear rise · PASS) |
| Abs mid rise open−mute | **+4.94 dB** |
| Open low-rel vs mute | open −0.77 / mute −0.13 (**not LF-only**) |
| Harsh 3–6k open vs mute | open −28.96 / mute −35.25 (acid presence, still tamed tops) |

## Slot map (skeleton-locked · chapter-relative)
| Slot | ID | Time | Energy | Character |
|------|-----|------|--------|-----------|
| 05 | Haniwa_Intro | 0:00–2:00 | 2 | Brighter atm LFO · settle −1 from F# · no kick |
| 06 | Haniwa_Build | 2:00–4:00 | 4 | +kick · sparse CH · tribal wood/clank poly LS7 |
| 07 | Haniwa_Drop | 4:00–6:00 | 8 | Dual acid mid-bloom + hats + tribal + metallic ride |
| 08 | Haniwa_Out | 6:00–7:00 | 5 | Kill tribal · acid filter down → E handoff |

## Mute staircase
| Bars (chapter) | Action |
|----------------|--------|
| 1–16 | PercLP/SynLP atm only (05) |
| 17–32 | +voice grain · short noise · LFO brighten |
| 33–48 | +kick F02 · sparse HH5C (06) |
| 49–64 | +cowbel/metal LS7 |
| 65–80 | +synperc/zap · ride still out |
| 81–96 | dual acid muted (07) |
| 97–128 | acid opens mid-bloom · full tribal · metallic ride · res spikes |
| 129–end | kill tribal · acid down · thin BD → E (08) |

## Poly doctrine
- Acid **Last Step 13** vs kick **16** vs hats **15** vs perc **7**
- Kick grid: steps 0/4/8/12 (Electribe 1/5/9/13)
- Dual acid: Acid LPF 303 saw + MG LPF square −8va · F major
- SD1 / clap = sparse accent only — **no gabber spine**

## Sample families (pool WAVs used)
- Slot 05: `atm_perclp_1/2/3` · `atm_synlp_bright` · `atm_voice_1_pad` · `atm_voice_7_grain` · `sfx_noise_mi` · `sfx_noise_short` · `sfx_2_mi` · `hh_7c_noiseish` (BD held: sinkick_veiled / f01)
- Slot 06: `bd_f01_organic` → `bd_f02_dry` → `bd_f03_groove` · `hh_5c_sparse` · `hh_1c_mi` · `hh_7c_noiseish` · `hh_5o_bright` · `perc_cowbel` · `perc_metal_0/1` · `perc_clank_rev` · `perc_synperc` · `perc_zap` · `perc_rim2`
- Slot 07: `bd_f03/f04/f05` · `bd_kick_ready_morph` · `hh_5o/1o/7o` · `perc_metal_0–3` · cowbel/synperc/zap/clank/junk/rim2 · `perc_kb_clap` + `perc_sd1_accent` (sparse) · `ride_metallic_synperc` + `ride_zap_tip` · `atm_synlp_bright`
- Slot 08: `bd_f06_thin_out` · `bd_sinkick_veiled` · `atm_perclp_1/3` · `atm_voice_7_grain` · `sfx_3_mi_out` · `sfx_noise_short` · tribal OFF

## Section timeline
- **0.0–59.3s** `Haniwa_Intro_a` (slot 05, 40 bars) — PercLP/SynLP brighter LFO; NO KICK [open=0.12]
- **59.3–120.0s** `Haniwa_Intro_b` (slot 05, 41 bars) — voice grain + noise haze; LFO brighten [open=0.18]
- **120.0–179.3s** `Haniwa_Build_kick` (slot 06, 40 bars) — kick F02 1/5/9/13; sparse HH5C [open=0.20]
- **179.3–240.0s** `Haniwa_Build_tribal` (slot 06, 41 bars) — cowbel/metal poly LS7; ride held out [open=0.25]
- **240.0–280.0s** `Haniwa_Drop_mute` (slot 07, 27 bars) — dual acid MUTED + tribal + ride tease [open=0.18]
- **280.0–339.3s** `Haniwa_Drop_open` (slot 07, 40 bars) — acid mid-bloom open; Res spikes 4/8/12/16 [open=0.92]
- **339.3–360.0s** `Haniwa_Drop_close` (slot 07, 14 bars) — strip ride/OH; acid closes [open=0.28]
- **360.0–419.3s** `Haniwa_Out` (slot 08, 40 bars) — kill tribal; acid filter down; thin BD → E [open=0.12]

## Sound design locks
- Acid: mid-bloom muted→open on Drop, presence 1.8–2.8 kHz, LS13, res spikes 4/8/12/16
- Kick: root-tuned F (~43.65 Hz sub), punch body ~110 Hz, EQ before sat, mono
- Perc: Pneumatix tribal wood/clank UP · poly LS7
- Ride: metallic SynPerc / Zap tip (Drop only) — not Figment dark Ride-1
- Master: mid lift + PA tame 4.5–10 kHz, loudnorm I=-8.5 TP=-1.0 → measured I=-9.0 TP=-1.1

## Doctrine kept
- Free-party / mental tekno / acidcore — **no commercial EDM drops**
- Pneumatix weight UP · plateaus not festival builds
- New sample family every slot · no Figment factory spine reuse
- Kick/bass mono · Haas only on hats/atm/acid

Ableton: skipped (--skip-ableton / DSP bounce)

*EvAIx · Haniwa Vestiges 05–08 · Figment v2 PASS unlock · mid-bloom +8.32 dB*
