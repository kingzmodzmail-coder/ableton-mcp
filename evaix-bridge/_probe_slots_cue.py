import json, socket
HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=60.0):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall(payload)
        sock.settimeout(timeout)
        chunks = []
        while True:
            c = sock.recv(8192)
            if not c:
                break
            chunks.append(c)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue
    raise RuntimeError("no response")

r = send("get_session_snapshot")["result"]
for t in r["tracks"]:
    empty = [cs["index"] for cs in t.get("clip_slots", []) if not cs.get("has_clip")]
    filled = [cs["index"] for cs in t.get("clip_slots", []) if cs.get("has_clip")]
    print(f"idx={t['index']:2d} audio={t['is_audio_track']} midi={t['is_midi_track']} name={t['name']!r} filled={filled} empty={empty}")
