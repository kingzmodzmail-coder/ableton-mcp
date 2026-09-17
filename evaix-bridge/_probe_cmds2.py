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

for cmd in ["create_scene","insert_scene","add_scene","duplicate_scene","fire_clip","set_tempo","start_playback","stop_playback","set_track_name","set_clip_name","load_browser_item","load_instrument_or_effect","stop_clip","fire_all_clips"]:
    r = send(cmd, {"index": -1} if "scene" in cmd else {})
    msg = r.get("message", r.get("status"))
    print(f"{cmd}: {msg[:120] if isinstance(msg,str) else msg}")
