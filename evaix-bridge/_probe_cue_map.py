import json, socket
from pathlib import Path

snap = json.loads(Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\_snap_cue167.txt").read_text(encoding="utf-8"))
print("tempo", snap["session"]["tempo"], "tracks", snap["session"]["track_count"], "song_len", snap["session"]["song_length"])
for t in snap["tracks"]:
    kind = "AUD" if t["is_audio_track"] else "MID"
    clips = []
    for cs in t.get("clip_slots", []):
        if cs.get("has_clip"):
            c = cs.get("clip") or {}
            clips.append((cs["index"], c.get("name"), c.get("length")))
    print(f"{t['index']:2d} {kind} mute={t['mute']} vol={t['volume']:.2f} {t['name']!r} clips={clips[:8]}")

def send(cmd, params=None, timeout=60):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection(("127.0.0.1", 9877), timeout=5) as s:
        s.sendall(payload)
        s.settimeout(timeout)
        chunks = []
        while True:
            b = s.recv(8192)
            if not b:
                break
            chunks.append(b)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue

r = send("get_arrangement_clips", {})
Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\_arr_clips_cue.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
print("arrangement status", r.get("status"), "keys", list(r.keys())[:10])
res = r.get("result", r)
if isinstance(res, dict):
    print("result keys", list(res.keys())[:20])
    clips = res.get("clips") or res.get("arrangement_clips") or []
    print("n_clips", len(clips) if isinstance(clips, list) else type(clips))
    if isinstance(clips, list):
        for c in clips[:30]:
            print(c)
elif isinstance(res, list):
    print("n_clips", len(res))
    for c in res[:30]:
        print(c)
