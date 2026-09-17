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

for cmd, params in [
    ("set_track_volume", {"track_index": 11, "volume": 0.0}),
    ("set_volume", {"track_index": 11, "volume": 0.0}),
    ("get_track_info", {"track_index": 10}),
    ("get_track_info", {"track_index": 11}),
]:
    r = send(cmd, params)
    print(cmd, json.dumps(r)[:400])
