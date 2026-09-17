import json, socket
from pathlib import Path

HOST, PORT = "127.0.0.1", 9877
S = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set")

def send(cmd, params=None, timeout=90.0):
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
        print("FAIL", label, r.get("message"))
        return None
    print(label)
    return r["result"]

snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
by = {t["name"]: t["index"] for t in snap["tracks"]}
print("by", {k: by[k] for k in by if k.startswith("E") or "Jam" in k or "90s" in k})

wav_for = {
    "E-Kick": "e_kick_155.wav",
    "E-Snare": "e_snare_155.wav",
    "E-Hats": "e_hats_155.wav",
    "E-Bass": "e_bass_155.wav",
    "E-Perc": "e_perc_155.wav",
    "E-Syn": "e_synhit_155.wav",
    "E-Mental": "esx_202_SynLP-4.wav",
    "E-Atm": "e_noise_155.wav",
    "E2S Jam": "e2s_jam_mono.wav",
    "ESX Jam": "esx_jam.wav",
    "ES1 90s": "es1_90s.wav",
    "E-DrumLP": "esx_217_DrumLP-7.wav",
}

scenes = [
    (1, "1 Dawn", ["E-Atm", "E-Hats"]),
    (2, "2 Gathering", ["E-Atm", "E-Hats", "E-Kick"]),
    (3, "3 Psycho", ["E-Hats", "E-Kick", "E-Bass", "E-Syn", "E-Mental"]),
    (4, "4 Peak", ["E-Hats", "E-Kick", "E-Snare", "E-Bass", "E-Perc", "E-Syn", "E-Mental", "E2S Jam"]),
    (5, "5 Break", ["E-Atm", "E-Hats", "E-Mental", "E-Syn"]),
    (6, "6 Drop2", ["E-Hats", "E-Kick", "E-Snare", "E-Bass", "E-Perc", "E-Syn", "E-Mental", "ESX Jam", "E-DrumLP"]),
    (7, "7 Outro", ["E-Hats", "E-Kick", "E-Atm", "ES1 90s"]),
]

# clear rows 1-7 then rebuild
for name, wav in wav_for.items():
    if name not in by:
        print("missing track", name)
        continue
    idx = by[name]
    for row in range(1, 8):
        send("delete_clip", {"track_index": idx, "clip_index": row})

for row, label, ons in scenes:
    for name in ons:
        if name not in by:
            continue
        idx = by[name]
        path = S / wav_for[name]
        send("delete_clip", {"track_index": idx, "clip_index": row})
        r = send("create_audio_clip", {"track_index": idx, "clip_index": row, "path": str(path)})
        ok(r, f"{label} {name}")
        if r.get("status") == "success":
            send("set_clip_name", {"track_index": idx, "clip_index": row, "name": label})

# fire psycho bed
for t in snap["tracks"]:
    for sl in (t.get("clip_slots") or []):
        if sl.get("has_clip"):
            send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})

ok(send("set_tempo", {"tempo": 155.0}), "tempo")
for name in ("E-Hats", "E-Kick", "E-Bass", "E-Syn", "E-Mental"):
    if name in by:
        ok(send("fire_clip", {"track_index": by[name], "clip_index": 0}), "fire " + name)

print("DONE")
