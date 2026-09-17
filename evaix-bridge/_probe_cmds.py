import json, socket
HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=15):
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

candidates = [
    "rename_scene", "set_scene_tempo", "trigger_scene", "launch_scene",
    "fire_clip", "stop_clip", "stop_all_clips", "start_playback", "stop_playback",
    "set_tempo", "set_track_name", "set_clip_name", "set_track_mute", "mute_track",
    "set_mute", "load_browser_item", "get_browser_tree", "get_browser_items_at_path",
    "duplicate_clip", "delete_track", "create_return_track",
]
for cmd in candidates:
    r = send(cmd, {})
    msg = r.get("message", "")
    st = r.get("status")
    if "Unknown command" in str(msg):
        print("NO ", cmd)
    else:
        print("YES", cmd, "->", st, str(msg)[:120], str(r.get("result", ""))[:80])
