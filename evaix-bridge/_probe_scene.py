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
    ("set_scene_name", {"scene_index": 0, "name": "Intro"}),
    ("set_scene_name", {"index": 0, "name": "Intro"}),
    ("fire_scene", {"scene_index": 2}),
    ("fire_scene", {"index": 2}),
    ("create_scene", {"index": -1}),
]
for cmd, params in tests:
    r = send(cmd, params)
    print(cmd, params, "->", json.dumps(r)[:300])
