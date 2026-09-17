import socket, json, wave, contextlib
from pathlib import Path

HOST, PORT = "127.0.0.1", 9877
STEM = Path(r"C:\Users\Gebruiker\ableton-mcp\suno-harvest\disappear_in_sound")
BPM = 180.0
TRACKS = list(range(2, 11))

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

def ok(r, label=""):
    if r.get("status") == "error":
        raise RuntimeError("%s: %s" % (label, r.get("message", r)))
    return r.get("result", r)

with contextlib.closing(wave.open(str(STEM / "disappear_drums.wav"), "rb")) as w:
    DUR = w.getnframes() / float(w.getframerate())
BEATS = DUR * BPM / 60.0
print("DUR", DUR, "BEATS", BEATS)

ok(send("stop_playback"))
ok(send("set_tempo", {"tempo": BPM}))
ok(send("set_current_song_time", {"time": 0.0}))

for ti in TRACKS:
    print("==== fix track", ti)
    # clear arrangement
    arr = ok(send("get_arrangement_clips", {"track_index": ti}))
    for idx in reversed(range(len(arr.get("clips") or []))):
        send("delete_arrangement_clip", {"track_index": ti, "arrangement_clip_index": idx})

    # force session clip markers in BEATS (Astra arrange pattern)
    print("LOOP_BEATS", send("set_clip_loop", {
        "track_index": ti, "clip_index": 0,
        "looping": False, "start_marker": 0.0, "end_marker": BEATS,
    }))
    info = ok(send("get_clip_info", {"track_index": ti, "clip_index": 0}))
    print("INFO", "warp", info.get("warping"), "end", info.get("end_marker"), "len", info.get("length"))

    dup = send("duplicate_session_clip_to_arrangement", {
        "track_index": ti, "clip_index": 0, "destination_time": 0.0,
    })
    print("DUP", dup.get("status"), dup.get("result") or dup.get("message"))

print("==== VERIFY ARR")
lens=[]
for ti in TRACKS:
    arr = ok(send("get_arrangement_clips", {"track_index": ti}))
    clips = arr.get("clips") or []
    if not clips:
        print(ti, "EMPTY"); continue
    c = clips[0]
    lens.append(float(c.get("length") or 0))
    print(ti, "len", c.get("length"), "end", c.get("end_time"), "n", len(clips))
print("MIN", min(lens) if lens else None, "MAX", max(lens) if lens else None, "SPREAD", (max(lens)-min(lens)) if lens else None)
