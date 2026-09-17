import json, socket
from pathlib import Path

HOST, PORT = "127.0.0.1", 9877
S = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\electribe-set")

def send(cmd, params=None, timeout=120.0):
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
        raise RuntimeError(f"{label}: {r}")
    print(label)
    return r["result"]

snap = ok(send("get_session_snapshot", {"include_devices": False}), "snap")
audio = [t for t in snap["tracks"] if not t.get("is_midi_track")]
print("audio", [(t["index"], t["name"]) for t in audio])

parts = [
    ("E-Kick", "e_kick_155.wav"),
    ("E-Snare", "e_snare_155.wav"),
    ("E-Hats", "e_hats_155.wav"),
    ("E-Bass", "e_bass_155.wav"),
    ("E-Perc", "e_perc_155.wav"),
    ("E-Syn", "e_synhit_155.wav"),
    ("E-Mental", "esx_202_SynLP-4.wav"),
    ("E-Atm", "e_noise_155.wav"),
    ("E2S Jam", "e2s_jam_mono.wav"),
    ("ESX Jam", "esx_jam.wav"),
    ("ES1 90s", "es1_90s.wav"),
    ("E-DrumLP", "esx_217_DrumLP-7.wav"),
]
parts = parts[: len(audio)]

ok(send("set_tempo", {"tempo": 155.0}), "tempo155")

for t in snap["tracks"]:
    for sl in (t.get("clip_slots") or []):
        if sl.get("has_clip"):
            try:
                send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})
            except Exception:
                pass

for i, (name, wav) in enumerate(parts):
    t = audio[i]
    idx = t["index"]
    path = S / wav
    if not path.exists():
        print("MISSING", path)
        continue
    for row in range(0, 8):
        try:
            send("delete_clip", {"track_index": idx, "clip_index": row})
        except Exception:
            pass
    ok(send("set_track_name", {"track_index": idx, "name": name}), "rename " + name)
    ok(send("create_audio_clip", {"track_index": idx, "clip_index": 0, "path": str(path)}), "clip0 " + name)
    ok(send("set_clip_name", {"track_index": idx, "clip_index": 0, "name": path.stem}), "name0 " + name)

snap2 = ok(send("get_session_snapshot", {"include_devices": False}), "snap2")
by = {t["name"]: t["index"] for t in snap2["tracks"]}
wav_for = dict(parts)

scenes = [
    (1, "1 Dawn", ["E-Atm", "E-Hats"]),
    (2, "2 Gathering", ["E-Atm", "E-Hats", "E-Kick"]),
    (3, "3 Psycho", ["E-Hats", "E-Kick", "E-Bass", "E-Syn", "E-Mental"]),
    (4, "4 Peak", ["E-Hats", "E-Kick", "E-Snare", "E-Bass", "E-Perc", "E-Syn", "E-Mental", "E2S Jam"]),
    (5, "5 Break", ["E-Atm", "E-Hats", "E-Mental", "E-Syn"]),
    (6, "6 Drop2", ["E-Hats", "E-Kick", "E-Snare", "E-Bass", "E-Perc", "E-Syn", "E-Mental", "ESX Jam", "E-DrumLP"]),
    (7, "7 Outro", ["E-Hats", "E-Kick", "E-Atm", "ES1 90s"]),
]

for row, label, ons in scenes:
    for name, wav in wav_for.items():
        if name not in by or name not in ons:
            continue
        idx = by[name]
        path = S / wav
        ok(send("create_audio_clip", {"track_index": idx, "clip_index": row, "path": str(path)}), label + " " + name)
        ok(send("set_clip_name", {"track_index": idx, "clip_index": row, "name": label}), "n " + label + " " + name)

for name in ("E-Hats", "E-Kick", "E-Bass", "E-Syn", "E-Mental"):
    if name in by:
        ok(send("fire_clip", {"track_index": by[name], "clip_index": 0}), "fire " + name)

print("READY")
print("tracks", [p[0] for p in parts])
