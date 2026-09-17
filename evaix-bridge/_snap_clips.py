import json, socket
def send(cmd, params=None, timeout=60):
    p = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection(("127.0.0.1", 9877), timeout=5) as s:
        s.sendall(p)
        s.settimeout(timeout)
        chunks = []
        while True:
            c = s.recv(8192)
            if not c:
                break
            chunks.append(c)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue
    return {"status": "error"}
r = send("get_session_snapshot", {"include_devices": False})
print("status", r.get("status"))
if r.get("status") != "success":
    print(r)
else:
    for t in r["result"]["tracks"]:
        clips = [(sl["index"], sl.get("name") or "") for sl in (t.get("clip_slots") or []) if sl.get("has_clip")]
        if clips:
            extra = "..." if len(clips) > 8 else ""
            print(t["index"], repr(t["name"]), clips[:8], extra)
