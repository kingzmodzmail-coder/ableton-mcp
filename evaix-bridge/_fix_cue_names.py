import json, socket
from pathlib import Path

HOST, PORT = "127.0.0.1", 9877
OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\cue167")

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
    raise RuntimeError("no response")

def ok(resp, label):
    if resp.get("status") != "success":
        raise RuntimeError(f"{label}: {resp}")
    print(label, "OK")
    return resp["result"]

ok(send("stop_playback"), "stop")
ok(send("set_tempo", {"tempo": 167.0}), "tempo")

# Restore CueHats name on track 3 (drums live in slot 1)
ok(send("set_track_name", {"track_index": 3, "name": "CueHats"}), "name CueHats")

# Place leftover CueSmp beds on free slots of track 13 (ESX Stretch duplicate) + 11
placements = [
    ("CueSmp20", 13, 4),
    ("CueSmp27", 13, 5),
    ("CueSmp35", 11, 6),
]
# Rename track 13 to CueSmp20 as primary for that bed cluster; keep 11 as ESX VoxAud
# Better: rename 13 to CueSmpBeds — user asked CueSmp*. Use CueSmp20 for track 13 name
# and put 27/35 as extra clips; also rename nothing on 11 — put CueSmp35 there and set name CueSmp35 only if empty-ish.
# Track 11 has vox clips — only add slot 6/7 without renaming.
# Track 13: rename to CueSmp20 (duplicate stretch exists at 7)

ok(send("set_track_name", {"track_index": 13, "name": "CueSmp20"}), "name CueSmp20")

for name, ti, ci in placements:
    path = str(OUT / f"{name}.wav")
    # clear if occupied
    snap = ok(send("get_session_snapshot"), "snap")
    t = snap["tracks"][ti]
    slot = t["clip_slots"][ci]
    if slot.get("has_clip"):
        try:
            ok(send("delete_clip", {"track_index": ti, "clip_index": ci}), f"clear {ti}:{ci}")
        except Exception as e:
            print("clear warn", e)
    try:
        ok(send("create_audio_clip", {"track_index": ti, "clip_index": ci, "path": path}, timeout=90), f"clip {name}@{ti}:{ci}")
        try:
            ok(send("set_clip_name", {"track_index": ti, "clip_index": ci, "name": name}), f"clipname {name}")
        except Exception as e:
            print("clipname warn", e)
    except Exception as e:
        print("SKIP", name, e)

# Ensure dedicated names still correct
ok(send("set_track_name", {"track_index": 2, "name": "CueKick"}), "n2")
ok(send("set_track_name", {"track_index": 12, "name": "CueSnare"}), "n12")
ok(send("set_track_name", {"track_index": 6, "name": "CueSmp26"}), "n6")
ok(send("set_track_name", {"track_index": 8, "name": "CueMix"}), "n8")
ok(send("set_track_name", {"track_index": 10, "name": "CueSmp4"}), "n10")
ok(send("set_track_name", {"track_index": 14, "name": "CueSmp6"}), "n14")

# Fire main drums + two smp
for ti, ci, label in [
    (2, 0, "CueKick"),
    (12, 1, "CueSnare"),
    (3, 1, "CueHats"),
    (10, 0, "CueSmp4"),
    (14, 0, "CueSmp6"),
    (6, 3, "CueSmp26"),
]:
    try:
        ok(send("fire_clip", {"track_index": ti, "clip_index": ci}), f"fire {label}")
    except Exception as e:
        print("fire fail", label, e)

info = ok(send("get_session_info"), "info")
tracks = ok(send("get_session_snapshot"), "final")["tracks"]
print("TRACKS:")
for t in tracks:
    filled = [cs["index"] for cs in t.get("clip_slots", []) if cs.get("has_clip")]
    print(f"  {t['index']:2d} {t['name']!r} audio={t['is_audio_track']} clips={filled}")
print("tempo", info.get("tempo"), "playing", info.get("is_playing"))
