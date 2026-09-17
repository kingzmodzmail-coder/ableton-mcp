import json, socket
from pathlib import Path

HOST, PORT = "127.0.0.1", 9877
S = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set")

def send(cmd, params=None, timeout=90.0):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall(payload)
        sock.settimeout(timeout)
        chunks = []
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue

def ok(r, label):
    if r.get("status") != "success":
        print("FAIL", label, r)
        return None
    print(label)
    return r["result"]

snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
by = {t["name"]: t["index"] for t in snap["tracks"]}

# stop all
for t in snap["tracks"]:
    for sl in (t.get("clip_slots") or []):
        if sl.get("has_clip"):
            send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})

ok(send("set_tempo", {"tempo": 155.0}), "tempo")

# map clean stems onto Electribe tracks; mute noisy mental/atm by loading silence or stopping
mapping = [
    ("E-Kick", "clean_kick.wav"),
    ("E-Snare", "clean_snare.wav"),
    ("E-Hats", "clean_hats.wav"),
    ("E-Bass", "clean_bass.wav"),
    ("E-Syn", "clean_syn.wav"),
]
# also put full build bounce on E2S Jam for one-clip listen
mapping.append(("E2S Jam", "clean_esx_build_155.wav"))

for name, wav in mapping:
    if name not in by:
        print("missing", name)
        continue
    idx = by[name]
    path = str(S / wav)
    send("delete_clip", {"track_index": idx, "clip_index": 0})
    ok(send("create_audio_clip", {"track_index": idx, "clip_index": 0, "path": path}), name)
    send("set_clip_name", {"track_index": idx, "clip_index": 0, "name": Path(wav).stem})

# stop noisy tracks if present
for noisy in ("E-Mental", "E-Atm", "E-Perc", "E-DrumLP", "ESX Jam"):
    if noisy in by:
        send("stop_clip", {"track_index": by[noisy], "clip_index": 0})

# fire clean bed stems (not the full bounce - or fire bounce alone for clear listen)
# Fire the arranged full bounce on E2S Jam so they hear the BUILD in Ableton too
ok(send("fire_clip", {"track_index": by["E2S Jam"], "clip_index": 0}), "fire full build")
print("DONE")
