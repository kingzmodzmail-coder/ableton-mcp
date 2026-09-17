import socket, json, os
from pathlib import Path

def send(cmd, params=None, timeout=60):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection(("127.0.0.1", 9877), timeout=5) as sock:
        sock.sendall(payload)
        sock.settimeout(timeout)
        d = b""
        while True:
            c = sock.recv(65536)
            if not c:
                break
            d += c
            try:
                return json.loads(d.decode())
            except Exception:
                pass
    return {"status": "error", "raw": d[:200]}

# probe commands
for cmd in ["get_commands", "list_commands", "help", "get_api"]:
    r = send(cmd)
    print(cmd, r.get("status"), str(r)[:300])

# try set volume / mute variants
for cmd, params in [
    ("set_track_volume", {"track_index": 0, "volume": 0.4}),
    ("set_volume", {"track_index": 0, "volume": 0.4}),
    ("set_track_mute", {"track_index": 0, "mute": False}),
    ("mute_track", {"track_index": 0, "mute": False}),
]:
    r = send(cmd, params)
    print(cmd, r.get("status"), r.get("message", r.get("result")) )

# find a short wav
wav = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\crisp-dna\morphs")
cands = list(wav.glob("*_acid.wav")) if wav.exists() else []
print("acid wavs", len(cands), cands[:3])
if cands:
    # try audio on Acid 303 Poly (MIDI) slot 7
    r = send("create_audio_clip", {"track_index": 0, "clip_index": 7, "path": str(cands[0])})
    print("audio on Acid303", r.get("status"), r.get("message", r.get("result")))
    # try on E-Syn
    r2 = send("create_audio_clip", {"track_index": 9, "clip_index": 7, "path": str(cands[0])})
    print("audio on E-Syn", r2.get("status"), r2.get("message", r2.get("result")))
