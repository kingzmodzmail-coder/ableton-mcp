import socket, json, time, wave, contextlib
from pathlib import Path

HOST, PORT = "127.0.0.1", 9877
STEM = Path(r"C:\Users\Gebruiker\ableton-mcp\suno-harvest\disappear_in_sound")
BPM = 180.0

TRACKS = [
    (2, "DIS Drums", "disappear_drums.wav", 0.78),
    (3, "DIS Bass", "disappear_bass.wav", 0.75),
    (4, "DIS Synth", "disappear_synth.wav", 0.62),
    (5, "DIS Keyboard", "disappear_keyboard.wav", 0.58),
    (6, "DIS Perc", "disappear_percussion.wav", 0.55),
    (7, "DIS Other", "disappear_other.wav", 0.45),
    (8, "DIS Brass", "disappear_brass.wav", 0.50),
    (9, "DIS Lead Vox", "disappear_lead_vocals.wav", 0.70),
    (10, "DIS Back Vox", "disappear_backing_vocals.wav", 0.55),
]

def send(cmd, params=None, timeout=90):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.sendall(payload)
        s.settimeout(timeout)
        chunks = []
        while True:
            b = s.recv(65536)
            if not b:
                break
            chunks.append(b)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue
    raise RuntimeError("no response for " + cmd)

def ok(r, label=""):
    if not isinstance(r, dict):
        raise RuntimeError("bad resp %s: %r" % (label, r))
    if r.get("status") == "error":
        raise RuntimeError("%s: %s" % (label, r.get("message", r)))
    return r.get("result", r)

with contextlib.closing(wave.open(str(STEM / "disappear_drums.wav"), "rb")) as w:
    DUR = w.getnframes() / float(w.getframerate())
print("DUR_S", DUR, "beats", DUR * BPM / 60)

print("STOP", send("stop_playback"))
print("TEMPO", ok(send("set_tempo", {"tempo": BPM}), "tempo"))
print("SEEK0", send("set_current_song_time", {"time": 0.0}))

for i in (0, 1, 11, 12):
    print("MUTE", i, send("set_track_mute", {"track_index": i, "mute": True}))
    print("VOL0", send("set_track_volume", {"track_index": i, "volume": 0.0}))
    arr = ok(send("get_arrangement_clips", {"track_index": i}), "arr%d" % i)
    for idx in reversed(range(len(arr.get("clips") or []))):
        print("DELARR", i, idx, send("delete_arrangement_clip", {"track_index": i, "arrangement_clip_index": idx}))

for ti, name, fname, vol in TRACKS:
    path = str(STEM / fname)
    print("====", ti, name)
    print("NAME", send("set_track_name", {"track_index": ti, "name": name}))
    print("UNMUTE", send("set_track_mute", {"track_index": ti, "mute": False}))
    print("VOL", send("set_track_volume", {"track_index": ti, "volume": vol}))

    arr = ok(send("get_arrangement_clips", {"track_index": ti}), "arr%d" % ti)
    for idx in reversed(range(len(arr.get("clips") or []))):
        print("DELARR", send("delete_arrangement_clip", {"track_index": ti, "arrangement_clip_index": idx}))

    for slot in range(0, 4):
        send("delete_clip", {"track_index": ti, "clip_index": slot})

    print("CREATE", ok(send("create_audio_clip", {"track_index": ti, "clip_index": 0, "path": path}), "create"))
    print("WARP OFF", ok(send("set_clip_audio", {"track_index": ti, "clip_index": 0, "warping": False}), "warp"))
    print("LOOP", ok(send("set_clip_loop", {"track_index": ti, "clip_index": 0, "looping": False, "start_marker": 0, "end_marker": DUR}), "loop"))
    info = ok(send("get_clip_info", {"track_index": ti, "clip_index": 0}), "info")
    print("INFO warping", info.get("warping"), "end", info.get("end_marker"), "len", info.get("length"))

    # try both command names used across bridges
    dup = send("duplicate_session_clip_to_arrangement", {"track_index": ti, "clip_index": 0, "destination_time": 0.0})
    if dup.get("status") == "error":
        dup = send("duplicate_clip_to_arrangement", {"track_index": ti, "clip_index": 0, "destination_time": 0.0})
    print("TO ARR", dup)

STRUCTURE = [("Intro", 0.0), ("Build", 64.0), ("Drop", 128.0), ("Break", 224.0), ("Drop2", 288.0), ("Outro", 400.0)]
for name, t in STRUCTURE:
    send("set_current_song_time", {"time": t})
    time.sleep(0.05)
    print("LOC", name, t, send("create_locator", {"name": name}))

send("set_current_song_time", {"time": 0.0})
print("==== VERIFY")
for ti, name, fname, vol in TRACKS:
    arr = ok(send("get_arrangement_clips", {"track_index": ti}))
    clips = arr.get("clips") or []
    if not clips:
        print(ti, name, "NO ARR CLIPS")
        continue
    c = clips[0]
    print(ti, name, "start", c.get("start_time"), "end", c.get("end_time"), "len", c.get("length"), "n", len(clips))

sess = ok(send("get_session_info"))
print("SESSION tempo", sess.get("tempo"), "time", sess.get("current_song_time"))
print("DONE")
