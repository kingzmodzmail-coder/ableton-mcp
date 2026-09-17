"""Build Cue+ESX dense 8-bar loops @167 into Ableton Live via AbletonMCP.

Creates new audio tracks when possible; if Live is at track limit
(Couldn't create track), reuses empty audio tracks / existing Cue* tracks.
Never deletes tracks. Skips failed create_audio_clip and continues.
"""
import json, socket, time, wave
from pathlib import Path
import numpy as np

ESX = Path(r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav")
CUE = Path(r"C:\Users\Gebruiker\Downloads\7OkqeRxk8Gzjr5xi-grok-workspace\public\samples")
OUT = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\cue167")
OUT.mkdir(parents=True, exist_ok=True)

BPM = 167.0
BARS = 8
BEATS = BARS * 4
SR = 44100
HOST, PORT = "127.0.0.1", 9877

# Prefer shorter Cue one-shots for perc/texture beds
CUE_SMP = ["smp26.wav", "smp35.wav", "smp6.wav", "smp20.wav", "smp4.wav", "smp27.wav"]


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n, *_ = w.getparams()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError(f"unsupported width {sw} in {path}")
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch == 2:
        data = data.reshape(-1, 2).mean(axis=1)
    elif ch > 2:
        data = data.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        x = np.linspace(0, 1, num=len(data), endpoint=False)
        new_len = max(1, int(len(data) * SR / sr))
        xi = np.linspace(0, 1, num=new_len, endpoint=False)
        data = np.interp(xi, x, data).astype(np.float32)
    return data


def write_wav(path: Path, mono: np.ndarray):
    mono = np.clip(mono, -1.0, 1.0)
    stereo = np.column_stack([mono, mono]).astype(np.float32)
    pcm = (stereo * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def place(buf, sample, beat, gain=1.0):
    start = int(beat * (60.0 / BPM) * SR)
    end = min(len(buf), start + len(sample))
    n = end - start
    if n <= 0:
        return
    buf[start:end] += sample[:n] * gain


def normalize(buf, peak=0.9):
    m = float(np.max(np.abs(buf))) or 1.0
    return (buf / m * peak).astype(np.float32)


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


def ok(resp, label):
    if resp.get("status") != "success":
        raise RuntimeError(f"{label}: {resp}")
    print(label, "OK")
    return resp["result"]


# --- render loops ---
total = int(BEATS * (60.0 / BPM) * SR)
print(f"BPM={BPM} bars={BARS} beats={BEATS} samples={total} dur={total/SR:.3f}s")

kick = read_wav(ESX / "001_BD-2.wav")
snare = read_wav(ESX / "024_SD-4.wav")
hhc = read_wav(ESX / "054_HH-1C.wav")
hho = read_wav(ESX / "055_HH-1O.wav")
clap = read_wav(ESX / "048_Clap-1.wav")
rim = read_wav(ESX / "045_Rim-1.wav")
hhc2 = read_wav(ESX / "056_HH-2C.wav")

kick_buf = np.zeros(total, dtype=np.float32)
snare_buf = np.zeros(total, dtype=np.float32)
hat_buf = np.zeros(total, dtype=np.float32)
kick_hits = snare_hits = hat_hits = 0

for bar in range(BARS):
    base = bar * 4
    for b in (0, 1, 2, 3):
        place(kick_buf, kick, base + b, 0.95)
        kick_hits += 1
    place(kick_buf, kick, base + 1.5, 0.42)
    place(kick_buf, kick, base + 3.5, 0.38)
    kick_hits += 2
    if bar % 2 == 1:
        place(kick_buf, kick, base + 2.25, 0.35)
        place(kick_buf, kick, base + 2.75, 0.28)
        kick_hits += 2
    if bar == BARS - 1:
        for t in (3.25, 3.5, 3.75):
            place(kick_buf, kick, base + t, 0.55)
            kick_hits += 1

    place(snare_buf, snare, base + 1, 0.92)
    place(snare_buf, snare, base + 3, 0.92)
    place(snare_buf, clap, base + 3, 0.32)
    snare_hits += 3
    place(snare_buf, snare, base + 1.75, 0.28)
    place(snare_buf, rim, base + 2.5, 0.4)
    snare_hits += 2
    if bar % 2 == 1:
        for t in (3.25, 3.5, 3.625, 3.75):
            place(snare_buf, rim if t != 3.5 else snare, base + t, 0.45 if t == 3.5 else 0.33)
            snare_hits += 1
    if bar == BARS - 1:
        for t in np.arange(2.0, 4.0, 0.125):
            place(snare_buf, rim, base + float(t), 0.28)
            snare_hits += 1

    for step in range(16):
        beat = base + step * 0.25
        if step % 4 == 2 and bar % 2 == 1:
            place(hat_buf, hho, beat, 0.5)
        elif step % 2 == 0:
            place(hat_buf, hhc, beat, 0.68 if step % 4 == 0 else 0.48)
        else:
            place(hat_buf, hhc2, beat, 0.32)
        hat_hits += 1
    if bar in (3, 7):
        place(hat_buf, hho, base + 3.5, 0.6)
        hat_hits += 1

cue_bufs = {}
cue_hit_counts = {}
for i, name in enumerate(CUE_SMP):
    p = CUE / name
    if not p.exists():
        print("MISSING cue", p)
        continue
    try:
        samp = read_wav(p)
    except Exception as e:
        print("skip read", name, e)
        continue
    buf = np.zeros(total, dtype=np.float32)
    hits = 0
    phase = i * 0.25
    spacing = 1.0 + (i % 3) * 0.5
    gain = 0.55 - i * 0.04
    t = phase
    while t < BEATS:
        place(buf, samp, t, gain)
        hits += 1
        bar = int(t // 4)
        step = spacing * (0.75 if bar % 2 == 1 else 1.0)
        t += step
    num = name.replace("smp", "").replace(".wav", "")
    track = f"CueSmp{num}"
    cue_bufs[track] = normalize(buf, 0.85)
    cue_hit_counts[track] = hits
    print(f"cue {name} -> {track}: hits={hits} samp_len={len(samp)}")

kick_n = normalize(kick_buf, 0.92)
snare_n = normalize(snare_buf, 0.9)
hat_n = normalize(hat_buf, 0.88)
mix = kick_n * 0.9 + snare_n * 0.82 + hat_n * 0.65
for buf in cue_bufs.values():
    mix = mix + buf * 0.35
mix = normalize(mix, 0.89)

total_hits = kick_hits + snare_hits + hat_hits + sum(cue_hit_counts.values())
dur = total / SR
print(f"onset density ~{total_hits/dur:.2f}/s (hits={total_hits} dur={dur:.2f}s)")
print(f"  kick={kick_hits} snare={snare_hits} hats={hat_hits} cue={sum(cue_hit_counts.values())}")

written = {"CueKick": kick_n, "CueSnare": snare_n, "CueHats": hat_n}
written.update(cue_bufs)
written["CueMix"] = mix

paths = {}
for track_name, audio in written.items():
    fp = OUT / f"{track_name}.wav"
    write_wav(fp, audio)
    paths[track_name] = fp
    print("wrote", fp)

order = ["CueKick", "CueSnare", "CueHats"] + sorted(
    [k for k in paths if k.startswith("CueSmp")],
    key=lambda s: int(s.replace("CueSmp", "") or 0),
) + ["CueMix"]

# FORCE 167 + stop so Live accepts edits
tempo_r = ok(send("set_tempo", {"tempo": BPM}), "set_tempo")
try:
    ok(send("stop_playback"), "stop")
except Exception as e:
    print("stop warn", e)
time.sleep(0.4)

created = []
errors = []
fired = []
mode = "create_new"


def snapshot_tracks():
    return ok(send("get_session_snapshot"), "snapshot")["tracks"]


def pick_reuse_targets(needed_names):
    """Map needed names -> (track_index, clip_index) without deleting tracks.

    Prefer: (1) empty audio tracks, (2) existing Cue* audio tracks empty slots,
    (3) existing Cue* audio tracks slot 0 after delete_clip, (4) other empty audio slots.
    Never touch MIDI-only non-Cue instrument tracks for audio clips.
    """
    tracks = snapshot_tracks()
    assignments = {}
    used = set()  # (ti, ci)

    def claim(ti, ci):
        key = (ti, ci)
        if key in used:
            return False
        used.add(key)
        return True

    # Build candidate lists
    empty_audio = []  # fully empty audio tracks
    cue_audio = []    # audio tracks whose name starts with Cue
    other_empty_slots = []  # (ti, ci, name)

    for t in tracks:
        if not t.get("is_audio_track"):
            continue
        slots = t.get("clip_slots", [])
        empty = [cs["index"] for cs in slots if not cs.get("has_clip")]
        filled = [cs["index"] for cs in slots if cs.get("has_clip")]
        name = t.get("name") or ""
        if not filled:
            empty_audio.append((t["index"], empty, name))
        if name.lower().startswith("cue"):
            cue_audio.append((t["index"], empty, filled, name))
        for ci in empty:
            other_empty_slots.append((t["index"], ci, name))

    # Preferred rename map for old Cue*167 names
    rename_pref = {
        "CueKick": ["CueKick", "CueKick167"],
        "CueSnare": ["CueSnare", "CueSnare167"],
        "CueHats": ["CueHats", "CueHats167"],
        "CueMix": ["CueMix", "CueMix167"],
        "CueSmp26": ["CuePerc167", "CuePerc"],
    }

    # 1) Match preferred Cue* tracks by name (one primary name per track)
    claimed_track_names = set()
    for need in needed_names:
        prefs = rename_pref.get(need, [need])
        for t in tracks:
            if not t.get("is_audio_track"):
                continue
            if t.get("name") not in prefs:
                continue
            ti = t["index"]
            if ti in claimed_track_names:
                continue
            empty = [cs["index"] for cs in t.get("clip_slots", []) if not cs.get("has_clip")]
            filled = [cs["index"] for cs in t.get("clip_slots", []) if cs.get("has_clip")]
            if empty and claim(ti, empty[0]):
                assignments[need] = {"track_index": ti, "clip_index": empty[0], "rename": need, "clear": False}
                claimed_track_names.add(ti)
                break
            if filled and claim(ti, filled[0]):
                assignments[need] = {"track_index": ti, "clip_index": filled[0], "rename": need, "clear": True}
                claimed_track_names.add(ti)
                break

    # 2) Fully empty audio tracks for remaining
    ei = 0
    for need in needed_names:
        if need in assignments:
            continue
        while ei < len(empty_audio):
            ti, empty, _old = empty_audio[ei]
            ei += 1
            if empty and claim(ti, empty[0]):
                assignments[need] = {"track_index": ti, "clip_index": empty[0], "rename": need, "clear": False}
                break

    # Tracks already claimed for a primary rename (one Cue* name per track)
    renamed_tracks = {a["track_index"] for a in assignments.values()}

    # 3) Any remaining empty slots — only rename if track not already named for another Cue layer
    for need in needed_names:
        if need in assignments:
            continue
        for ti, ci, _n in other_empty_slots:
            if not claim(ti, ci):
                continue
            do_rename = ti not in renamed_tracks
            if do_rename:
                renamed_tracks.add(ti)
            assignments[need] = {
                "track_index": ti,
                "clip_index": ci,
                "rename": need if do_rename else None,
                "clear": False,
            }
            break

    # 4) Last resort: clear slot 0 on Cue audio tracks not yet used for this need
    for need in needed_names:
        if need in assignments:
            continue
        for ti, empty, filled, _n in cue_audio:
            if not filled:
                continue
            ci = filled[0]
            if claim(ti, ci):
                assignments[need] = {"track_index": ti, "clip_index": ci, "rename": need, "clear": True}
                break

    return assignments


# Try create_audio_track for each; fall back to reuse if any create fails
reuse_map = None
for name in order:
    path = paths[name]
    try:
        r = ok(send("create_audio_track", {"index": -1}), f"create {name}")
        idx = r["index"]
        ok(send("set_track_name", {"track_index": idx, "name": name}), f"name {name}")
        try:
            ok(send("create_audio_clip", {
                "track_index": idx,
                "clip_index": 0,
                "path": str(path),
            }, timeout=90), f"clip {name}")
            try:
                ok(send("set_clip_name", {
                    "track_index": idx,
                    "clip_index": 0,
                    "name": name,
                }), f"clipname {name}")
            except Exception as e:
                print("clipname warn", name, e)
            created.append({"name": name, "index": idx, "clip_index": 0, "clip": True, "mode": "new"})
        except Exception as e:
            print("SKIP create_audio_clip", name, e)
            errors.append({"name": name, "stage": "create_audio_clip", "error": str(e)})
            created.append({"name": name, "index": idx, "clip_index": 0, "clip": False, "mode": "new"})
    except Exception as e:
        print("create_audio_track failed for", name, "-> switching to REUSE mode:", e)
        errors.append({"name": name, "stage": "create_audio_track", "error": str(e)})
        mode = "reuse"
        remaining = [n for n in order if n not in {c["name"] for c in created}]
        reuse_map = pick_reuse_targets(remaining)
        print("reuse_map", json.dumps(reuse_map))
        for need in remaining:
            tgt = reuse_map.get(need)
            if not tgt:
                errors.append({"name": need, "stage": "reuse", "error": "no free audio slot"})
                print("NO SLOT for", need)
                continue
            ti, ci = tgt["track_index"], tgt["clip_index"]
            try:
                if tgt.get("rename"):
                    ok(send("set_track_name", {"track_index": ti, "name": tgt["rename"]}), f"rename->{need}")
                if tgt.get("clear"):
                    try:
                        ok(send("delete_clip", {"track_index": ti, "clip_index": ci}), f"clear {need}@{ti}:{ci}")
                    except Exception as de:
                        print("delete_clip warn", de)
                try:
                    ok(send("create_audio_clip", {
                        "track_index": ti,
                        "clip_index": ci,
                        "path": str(paths[need]),
                    }, timeout=90), f"clip {need}@{ti}:{ci}")
                    try:
                        ok(send("set_clip_name", {
                            "track_index": ti,
                            "clip_index": ci,
                            "name": need,
                        }), f"clipname {need}")
                    except Exception as e2:
                        print("clipname warn", need, e2)
                    created.append({"name": need, "index": ti, "clip_index": ci, "clip": True, "mode": "reuse"})
                except Exception as e3:
                    print("SKIP create_audio_clip", need, e3)
                    errors.append({"name": need, "stage": "create_audio_clip", "error": str(e3)})
                    created.append({"name": need, "index": ti, "clip_index": ci, "clip": False, "mode": "reuse"})
            except Exception as e4:
                print("FAIL reuse", need, e4)
                errors.append({"name": need, "stage": "reuse", "error": str(e4)})
        break

# Fire main drum layers + first two CueSmp
fire_names = {"CueKick", "CueSnare", "CueHats"}
for item in created:
    if item.get("clip") and item["name"] in fire_names:
        try:
            ok(send("fire_clip", {
                "track_index": item["index"],
                "clip_index": item.get("clip_index", 0),
            }), f"fire {item['name']}")
            fired.append(item["name"])
        except Exception as e:
            print("fire fail", item["name"], e)
            errors.append({"name": item["name"], "stage": "fire_clip", "error": str(e)})

smp_fired = 0
for item in created:
    if item.get("clip") and item["name"].startswith("CueSmp") and smp_fired < 2:
        try:
            ok(send("fire_clip", {
                "track_index": item["index"],
                "clip_index": item.get("clip_index", 0),
            }), f"fire {item['name']}")
            fired.append(item["name"])
            smp_fired += 1
        except Exception as e:
            print("fire fail", item["name"], e)
            errors.append({"name": item["name"], "stage": "fire_clip", "error": str(e)})

info = ok(send("get_session_info"), "final_session")
# print track names for confirmation
try:
    tracks = snapshot_tracks()
    print("TRACKS:")
    for t in tracks:
        filled = [cs["index"] for cs in t.get("clip_slots", []) if cs.get("has_clip")]
        print(f"  {t['index']:2d} {t['name']!r} audio={t['is_audio_track']} clips={filled}")
except Exception as e:
    print("snapshot end warn", e)

print("=== SUMMARY ===")
print("mode", mode)
print("tempo_result", json.dumps(tempo_r))
print("created", json.dumps(created))
print("fired", fired)
print("errors", json.dumps(errors))
print(json.dumps(info, indent=2))
