import json, socket
HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=60):
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
    return {"status": "error"}

r = send("get_session_snapshot", {"include_devices": False})
print("status", r.get("status"))
res = r.get("result", r)
tracks = res.get("tracks", [])
print("ntracks", len(tracks))
for t in tracks:
    print(t["index"], repr(t["name"]), "midi" if t.get("is_midi_track") else "audio", "slots", len(t.get("clip_slots") or []))
info = send("get_script_info")
print("script_info keys", list((info.get("result") or info).keys())[:20] if isinstance(info.get("result") or info, dict) else info)
si = info.get("result") or info
if isinstance(si, dict) and "commands" in si:
    print("commands", si["commands"][:80] if isinstance(si["commands"], list) else si["commands"])
elif isinstance(si, dict):
    for k,v in si.items():
        if "command" in k.lower() or "api" in k.lower():
            print(k, str(v)[:500])
