import socket, json

def send(cmd, params=None, timeout=30):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection(("127.0.0.1", 9877), timeout=5) as sock:
        sock.sendall(payload)
        sock.settimeout(timeout)
        d = b""
        while True:
            c = sock.recv(65536)
            if not c:
                break
            d += c
            try:
                return json.loads(d.decode())
            except Exception:
                pass
    return {"status": "error"}

r = send("get_session_snapshot", {"include_devices": True})
tracks = (r.get("result") or {}).get("tracks") or []
for t in tracks:
    name = t.get("name")
    idx = t.get("index")
    typ = t.get("type") or t.get("track_type") or t.get("has_midi_input")
    mute = t.get("mute")
    vol = t.get("volume")
    devs = [d.get("name") for d in (t.get("devices") or [])][:6]
    print(idx, "|", name, "|", typ, "| mute=", mute, "| vol=", vol, "|", devs)
