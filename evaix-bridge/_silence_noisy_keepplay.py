import json, socket, time
HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=30):
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

# Keep playing + tempo
print("tempo", send("set_tempo", {"tempo": 162.0}))
print("play", send("start_playback"))

snap = send("get_session_snapshot", {"include_devices": False}, timeout=60)
tracks = (snap.get("result") or {}).get("tracks", [])
by = {t["name"]: t for t in tracks}
print("tracks", list(by))

# Stop+delete noisy beds entirely
for name in ("E-Mental", "E-Atm", "E-Syn"):
    t = by.get(name)
    if not t:
        print("missing", name)
        continue
    idx = t["index"]
    for sl in t.get("clip_slots") or []:
        if sl.get("has_clip"):
            send("stop_clip", {"track_index": idx, "clip_index": sl["index"]})
            send("delete_clip", {"track_index": idx, "clip_index": sl["index"]})
    # also clear all 8 slots
    for row in range(8):
        send("stop_clip", {"track_index": idx, "clip_index": row})
        send("delete_clip", {"track_index": idx, "clip_index": row})
    print("silenced", name, idx)

info = send("get_session_info")
print("is_playing", (info.get("result") or info).get("is_playing"))
print("tempo_now", (info.get("result") or info).get("tempo"))
