import json, socket

HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=60.0):
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
    raise RuntimeError("bridge down")

def ok(r, label):
    if r.get("status") != "success":
        raise RuntimeError(f"{label}: {r}")
    print(label, r.get("result"))
    return r["result"]

snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
tempo = 158.0  # sweet spot in 155-168
ok(send("set_tempo", {"tempo": tempo}), "tempo")

# find a MIDI track
midi = [t for t in snap["tracks"] if t.get("is_midi_track")]
if not midi:
    # try create
    ok(send("create_midi_track", {"index": -1}), "create midi")
    snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap2")
    midi = [t for t in snap["tracks"] if t.get("is_midi_track")]

t = midi[0]
idx = t["index"]
ok(send("set_track_name", {"track_index": idx, "name": "Acid 303 Poly"}), "rename")

# 64-step clip = 4 bars in 16ths... wait 64 sixteenth notes = 16 beats = 4 bars
# For poly 15-step cycle across 64 sixteenths:
# Live clip length in beats: 16.0 (4 bars) covering 64 sixteenth steps
# Or longer: 64 sixteenth steps of a 15-step pattern repeating
length_beats = 16.0  # 4 bars @ 4/4 = 64 sixteenth-note slots

try:
    send("delete_clip", {"track_index": idx, "clip_index": 0})
except Exception:
    pass

ok(send("create_clip", {"track_index": idx, "clip_index": 0, "length": length_beats}), "create clip")
ok(send("set_clip_name", {"track_index": idx, "clip_index": 0, "name": "acid_poly15_64"}), "cname")

# Pitch map Gm tekno: G1=31, Bb1=34, C2=36, D2=38, F2=41, G2=43
# 15-step pattern (steps are 16th notes): classic 303-ish with slides via overlapping
# step pattern relative pitches in Gm
# 15 steps: G Bb G C D Bb F G Bb C G D Bb F G
seq = [31, 34, 31, 36, 38, 34, 41, 31, 34, 36, 31, 38, 34, 41, 43]
# accents / longer gates on some
gates = [0.35, 0.2, 0.45, 0.2, 0.55, 0.2, 0.35, 0.2, 0.4, 0.2, 0.5, 0.2, 0.35, 0.2, 0.6]
vels = [100, 70, 110, 75, 120, 70, 95, 80, 105, 75, 115, 70, 90, 75, 127]

notes = []
# fill 64 sixteenth slots by cycling 15-step pattern
for i in range(64):
    step = i % 15
    pitch = seq[step]
    start = i * 0.25  # beats
    dur = gates[step]
    # slide feel: slightly longer gate into next on accent steps
    if step in (0, 2, 4, 10, 14):
        dur = min(0.85, dur + 0.25)
    notes.append({
        "pitch": pitch,
        "start_time": start,
        "duration": dur,
        "velocity": vels[step],
        "mute": False,
    })

ok(send("add_notes_to_clip", {
    "track_index": idx,
    "clip_index": 0,
    "notes": notes,
}), "notes")

# fire acid + keep clean kick/hats if present
by = {t["name"]: t["index"] for t in snap["tracks"]}
ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), "fire acid")
for name in ("E-Kick", "E-Hats", "E-Snare"):
    if name in by:
        send("fire_clip", {"track_index": by[name], "clip_index": 0})

print("POLY15 ready @", tempo)
print("pattern cycle", seq)
print("note_count", len(notes))
