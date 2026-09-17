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

def ok(r, label):
    print(label, r.get("status"), str(r.get("message", ""))[:80])
    return r.get("status") == "success"

send("set_tempo", {"tempo": 162.0})
send("start_playback")

snap = send("get_session_snapshot", {"include_devices": False}, timeout=60)
tracks = (snap.get("result") or {}).get("tracks", [])
by = {t["name"]: t["index"] for t in tracks}
print("by", by)

acid = by.get("Acid 303 Poly") or by.get("1-Drift") or by.get("Drift")
bass = by.get("Tholin Bass")
kick = by.get("E-Kick")
hats = by.get("E-Hats")
ohat = by.get("E-OHat")
perc = by.get("E-Perc")
print("acid", acid, "bass", bass)

# silence other potential noise sources
for name in ("E-Mental", "E-Atm", "E-Syn", "E-Bass", "E-DrumLP", "ESX Drum Rack", "CRISP_e2e_kick", "E2S Jam", "ESX Jam", "ES1 90s"):
    idx = by.get(name)
    if idx is None:
        continue
    for row in range(8):
        send("stop_clip", {"track_index": idx, "clip_index": row})
        send("delete_clip", {"track_index": idx, "clip_index": row})
    print("silenced", name)

if acid is not None:
    send("set_track_name", {"track_index": acid, "name": "Acid 303 Poly"})
    r = send("load_browser_item", {"track_index": acid, "item_uri": "query:Synths#Drift"})
    if r.get("status") != "success":
        r = send("load_instrument_or_effect", {"track_index": acid, "uri": "query:Synths#Drift"})
    print("Drift acid", r.get("status"), r.get("message", ""))

if bass is not None:
    r = send("load_browser_item", {"track_index": bass, "item_uri": "query:Synths#Drift"})
    print("Drift bass", r.get("status"), r.get("message", ""))

gate, slide = 0.22, 0.50
steps = [
    (0, 40, 100, gate), (2, 44, 100, slide), (4, 47, 120, gate),
    (6, 52, 105, gate), (8, 47, 100, gate), (9, 45, 100, slide),
    (11, 44, 100, gate), (13, 40, 120, gate), (15, 35, 100, slide),
]

def notes(bars=4, muted=False, harder=False, bass_oct=False):
    vel_mod = -35 if muted else (12 if harder else 0)
    g = 0.12 if muted else gate
    s = 0.28 if muted else slide
    out = []
    for bar in range(bars):
        base = bar * 4.0
        for step, pitch, vel, dur0 in steps:
            dur = s if dur0 >= 0.4 else g
            if muted:
                dur = 0.12 if dur0 < 0.4 else 0.28
            p = pitch - 12 if bass_oct else pitch
            out.append({
                "pitch": max(0, p),
                "start_time": base + step * 0.25,
                "duration": dur,
                "velocity": max(1, min(127, int((vel + vel_mod) * (0.82 if bass_oct else 1)))),
                "mute": False,
            })
    return out

def put_midi(idx, row, name, ns):
    send("delete_clip", {"track_index": idx, "clip_index": row})
    r = send("create_clip", {"track_index": idx, "clip_index": row, "length": 16.0})
    if r.get("status") != "success":
        print("FAIL create", name, r)
        return False
    send("set_clip_name", {"track_index": idx, "clip_index": row, "name": name})
    r2 = send("add_notes_to_clip", {"track_index": idx, "clip_index": row, "notes": ns})
    print("midi", name, r2.get("status"), "n", len(ns))
    return r2.get("status") == "success"

# Acid scenes: 3 muted, 4 drop open, 5 tribal, 6 break, 7 peak+bass
if acid is not None:
    put_midi(acid, 3, "Acid_Muted_acid", notes(muted=True))
    put_midi(acid, 4, "Drop_Clean_acid", notes())
    put_midi(acid, 5, "Tribal_Add_acid", notes())
    put_midi(acid, 6, "Break_Fragile_acid", notes())
    put_midi(acid, 7, "Peak_Full_acid", notes(harder=True))
if bass is not None:
    put_midi(bass, 7, "Peak_Full_bass", notes(harder=True, bass_oct=True))
    # also dual acid on Drop for Digitone-clean feel? User: Drop = acid open; Peak = dual bass
    # Optional light bass on Drop - user said Drop without requiring bass; Peak has dual

# Fire Drop_Clean row 4 on CLEAN tracks only
drop = 4
fired = []
for label, idx in [("Acid 303 Poly", acid), ("E-Kick", kick), ("E-Hats", hats), ("E-OHat", ohat), ("E-Perc", perc)]:
    if idx is None:
        continue
    r = send("fire_clip", {"track_index": idx, "clip_index": drop})
    if r.get("status") == "success":
        fired.append(label)
        print("FIRE", label)
    else:
        print("FAIL fire", label, r.get("message"))

send("start_playback")
info = send("get_session_info")
res = info.get("result") or info
print("RESULT playing", res.get("is_playing"), "tempo", res.get("tempo"), "fired", fired)
