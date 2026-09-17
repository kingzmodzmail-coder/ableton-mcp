from pathlib import Path
p = Path(r'C:\Users\Gebruiker\ableton-mcp\music-os-bridge\HOWTO.md')
p.write_text(r'''# Ableton → Music OS bridge (live)

## Stack

1. Ableton Live 12 + AbletonMCP Remote Script → TCP `127.0.0.1:9877`
2. This bridge (`music-os-bridge`) → MDBP `http://127.0.0.1:7843` + `/session` + `/health`
3. Cue DAW view MDBP URL pointed at `ws://127.0.0.1:7843`
4. ChatGPT operate UI = AITrackGen Slack (`Documents\\Codex\\...\\aitrackgen-crisp-slack`) — same Live tools via MCP stdio, not this HTTP bridge

## Running now

- Live owns `:9877`
- Bridge started with `node server.mjs` from this folder
- Verified session: 120 BPM, tracks 1-MIDI / 2-MIDI / 3-Audio / 4-Audio

## Restart

```powershell
cd C:\Users\Gebruiker\ableton-mcp\music-os-bridge
npm start
```

Open http://127.0.0.1:7843/session

## Note

Architect box Tailscale was down when this was wired, so the bridge runs on the PC next to Live. When Tailscale is back, Architect Music OS can point at the PC bridge over the mesh (or bind `MUSIC_OS_BRIDGE_HOST=0.0.0.0` + firewall).
''', encoding='utf-8')
print('howto written')
