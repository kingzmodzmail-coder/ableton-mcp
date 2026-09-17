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

tests = [
    ("set_track_property", {"track_index": 10, "name": "mute", "value": 1}),
    ("set_track_property", {"track_index": 10, "property": "mute", "value": True}),
    ("set_property", {"track_index": 10, "property": "mute", "value": True}),
    ("set_track", {"track_index": 10, "mute": True}),
    ("update_track", {"track_index": 10, "mute": True}),
]
for cmd, params in tests:
    r = send(cmd, params)
    print(cmd, r.get("status"), str(r.get("message"))[:100])

# list audio devices via powershell
