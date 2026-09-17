import json, socket
HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=20):
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

for cmd, params in [
    ("set_track_mute", {"track_index": 11, "mute": True}),
    ("mute_track", {"track_index": 11, "mute": True}),
    ("set_mute", {"track_index": 11, "mute": True}),
]:
    r = send(cmd, params)
    print(cmd, r.get("status"), str(r.get("message", r.get("result")))[:120])
