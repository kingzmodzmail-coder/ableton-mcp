import json, socket, time

HOST, PORT = "127.0.0.1", 9877
BPM = 175.0
# 8 bars breakdown at 175 BPM
BARS = 8
SECONDS = BARS * 4 * (60.0 / BPM)

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
    print(label, "->", json.dumps(r.get("result"))[:200])
    return r["result"]

ok(send("set_tempo", {"tempo": BPM}), "tempo")
snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
by = {t["name"]: t["index"] for t in snap["tracks"]}
print("tracks", by)

keep = {"Tribe Kick", "Tribe Hats"}
drop = {"Tribe Kick", "Tribe Hats", "Tribe Snare", "Tribe Acid", "Offbeat Bass"}

# BREAKDOWN: stop everything except kick+hats
print("=== BREAKDOWN ===")
for name, idx in by.items():
    if name in keep:
        # ensure firing
        try:
            ok(send("fire_clip", {"track_index": idx, "clip_index": 0}), "fire " + name)
        except Exception as e:
            print("fire keep", name, e)
    else:
        try:
            ok(send("stop_clip", {"track_index": idx, "clip_index": 0}), "stop " + name)
        except Exception as e:
            print("stop", name, e)

print("holding breakdown for %.1fs (%d bars @ %.0f BPM)" % (SECONDS, BARS, BPM))
time.sleep(SECONDS)

# DROP: fire full tribe stack
print("=== DROP ===")
for name in ("Tribe Kick", "Tribe Snare", "Tribe Hats", "Tribe Acid", "Offbeat Bass"):
    if name not in by:
        print("missing", name)
        continue
    ok(send("fire_clip", {"track_index": by[name], "clip_index": 0}), "drop " + name)

info = ok(send("get_session_info"), "session")
print("FINAL", json.dumps(info, indent=2))
