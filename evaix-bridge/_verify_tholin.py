import json, socket
HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=60):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.sendall(payload)
        s.settimeout(timeout)
        chunks = []
        while True:
            ch = s.recv(65536)
            if not ch:
                break
            chunks.append(ch)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue

r = send("get_session_snapshot", {"include_devices": False})
snap = r.get("result", r)
print("tempo", snap["session"]["tempo"], "playing", snap["session"]["is_playing"])
want = {"Acid 303 Poly", "Tholin Bass", "E-Kick", "E-Hats", "E-OHat", "E-Perc", "E-Atm"}
for t in snap["tracks"]:
    if t["name"] not in want:
        continue
    playing = []
    rows = []
    for sl in t.get("clip_slots") or []:
        if not sl.get("has_clip"):
            continue
        clip = sl.get("clip") or {}
        if sl["index"] <= 5:
            rows.append((sl["index"], clip.get("name")))
        if clip.get("is_playing"):
            playing.append((sl["index"], clip.get("name")))
    print(t["index"], t["name"], "PLAYING", playing, "rows", rows)
print("scenes", snap.get("scenes"))
