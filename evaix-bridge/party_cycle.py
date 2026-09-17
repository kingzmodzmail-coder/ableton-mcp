import json, socket, time

HOST, PORT = "127.0.0.1", 9877
BPM = 175.0
BREAK_BARS = 8
DROP_BARS = 16
CYCLES = 3
break_s = BREAK_BARS * 4 * (60.0 / BPM)
drop_s = DROP_BARS * 4 * (60.0 / BPM)

DROP_NAMES = ["Tribe Kick", "Tribe Snare", "Tribe Hats", "Tribe Acid", "Offbeat Bass"]
BREAK_KEEP = {"Tribe Kick", "Tribe Hats"}

def send(cmd, params=None, timeout=15.0):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall(payload)
        sock.settimeout(timeout)
        chunks = []
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue
    raise RuntimeError("no response")

def ok(r, label):
    if r.get("status") != "success":
        raise RuntimeError("%s: %s" % (label, r))
    print(label, "->", json.dumps(r.get("result"))[:160])
    return r["result"]

ok(send("set_tempo", {"tempo": BPM}), "tempo")
snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
by = {t["name"]: t["index"] for t in snap["tracks"]}
print("tracks", {k: by[k] for k in DROP_NAMES if k in by})

missing = [n for n in DROP_NAMES if n not in by]
if missing:
    raise SystemExit("missing tracks: %s" % missing)

def breakdown():
    print("=== BREAKDOWN ===")
    for name, idx in by.items():
        if name in BREAK_KEEP:
            ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), "keep " + name)
        else:
            try:
                ok(send("stop_clip", {"track_index": idx, "clip_index": 0}), "stop " + name)
            except Exception as e:
                print("stop skip", name, e)

def drop():
    print("=== DROP ===")
    for name in DROP_NAMES:
        ok(send("fire_clip", {"track_index": by[name], "clip_index": 0}), "drop " + name)

for i in range(1, CYCLES + 1):
    print("--- cycle %d/%d ---" % (i, CYCLES))
    breakdown()
    time.sleep(break_s)
    drop()
    if i < CYCLES:
        time.sleep(drop_s)

info = ok(send("get_session_info"), "session")
print("DONE on drop", json.dumps(info, indent=2))
