import json, socket
HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=60):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.sendall(payload)
        s.settimeout(timeout)
        chunks = []
        while True:
            ch = s.recv(8192)
            if not ch:
                break
            chunks.append(ch)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue

send("set_tempo", {"tempo": 162.0})
send("start_playback")
snap = send("get_session_snapshot", {"include_devices": False}, timeout=60)
tracks = (snap.get("result") or {}).get("tracks", [])
by = {t["name"]: t["index"] for t in tracks}
print("by", by)

def idx(*names):
    for n in names:
        if n in by:
            return by[n]
    return None

acid = idx("Acid 303 Poly", "1-Drift", "Drift")
bass = idx("Tholin Bass")
kick = idx("E-Kick")
hats = idx("E-Hats")
ohat = idx("E-OHat")
perc = idx("E-Perc")
print("acid", acid, "bass", bass)

if acid is None:
    raise SystemExit("no acid track")

send("set_track_name", {"track_index": acid, "name": "Acid 303 Poly"})
r = send("load_browser_item", {"track_index": acid, "item_uri": "query:Synths#Drift"})
print("Drift", r.get("status"), r.get("message", ""))

gate, slide = 0.22, 0.50
steps = [
    (0, 40, 100, gate), (2, 44, 100, slide), (4, 47, 120, gate),
    (6, 52, 105, gate), (8, 47, 100, gate), (9, 45, 100, slide),
    (11, 44, 100, gate), (13, 40, 120, gate), (15, 35, 100, slide),
]

def notes(muted=False, harder=False, bass_oct=False):
    vel_mod = -35 if muted else (12 if harder else 0)
    out = []
    for bar in range(4):
        base = bar * 4.0
        for step, pitch, vel, dur0 in steps:
            dur = (0.12 if dur0 < 0.4 else 0.28) if muted else dur0
            p = pitch - 12 if bass_oct else pitch
            out.append({
                "pitch": max(0, p),
                "start_time": base + step * 0.25,
                "duration": dur,
                "velocity": max(1, min(127, int((vel + vel_mod) * (0.82 if bass_oct else 1)))),
                "mute": False,
            })
    return out

def put_midi(ti, row, name, ns):
    send("delete_clip", {"track_index": ti, "clip_index": row})
    r = send("create_clip", {"track_index": ti, "clip_index": row, "length": 16.0})
    if r.get("status") != "success":
        print("FAIL", name, r)
        return
    send("set_clip_name", {"track_index": ti, "clip_index": row, "name": name})
    r2 = send("add_notes_to_clip", {"track_index": ti, "clip_index": row, "notes": ns})
    print("midi", name, r2.get("status"), len(ns))

put_midi(acid, 3, "Acid_Muted_acid", notes(muted=True))
put_midi(acid, 4, "Drop_Clean_acid", notes())
put_midi(acid, 5, "Tribal_Add_acid", notes())
put_midi(acid, 6, "Break_Fragile_acid", notes())
put_midi(acid, 7, "Peak_Full_acid", notes(harder=True))
if bass is not None:
    put_midi(bass, 7, "Peak_Full_bass", notes(harder=True, bass_oct=True))

fired = []
for label, ti in [("Acid 303 Poly", acid), ("E-Kick", kick), ("E-Hats", hats), ("E-OHat", ohat), ("E-Perc", perc)]:
    if ti is None:
        continue
    r = send("fire_clip", {"track_index": ti, "clip_index": 4})
    print("FIRE", label, r.get("status"))
    if r.get("status") == "success":
        fired.append(label)

send("start_playback")
info = send("get_session_info").get("result") or {}
print("RESULT", "playing", info.get("is_playing"), "tempo", info.get("tempo"), "fired", fired)
