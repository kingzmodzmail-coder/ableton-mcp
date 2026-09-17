import json, socket
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

send("start_playback")
info = send("get_session_info").get("result") or {}
print("tempo", info.get("tempo"), "playing", info.get("is_playing"))
# check drop clips playing
for ti, name in [(0,"Acid"), (2,"Kick"), (3,"OHat"), (5,"Bass"), (6,"Hats"), (8,"Perc"), (9,"Syn"), (10,"Mental"), (11,"Atm")]:
    t = send("get_track_info", {"track_index": ti}).get("result") or {}
    slots = t.get("clip_slots") or []
    playing = []
    for sl in slots:
        c = sl.get("clip")
        if c and c.get("is_playing"):
            playing.append(f"{sl['index']}:{c.get('name')}")
    has = [f"{sl['index']}:{((sl.get('clip') or {}).get('name'))}" for sl in slots if sl.get("has_clip")]
    print(f"t{ti} {t.get('name')} mute={t.get('mute')} playing={playing} clips={has[:8]}")
