# -*- coding: utf-8 -*-
"""Continue Ableton v2 clip load — MentalClean Morph 162 v2 (RingMod + choke)."""
from __future__ import annotations
import json, socket, sys
from pathlib import Path

HOST, PORT = "127.0.0.1", 9877
CLIP_DIR = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\crisp-dna\mentalclean-molecular-morph-162-v2\ableton_clips")
BPM = 162.0
SCENES = [
    (0, "Intro"),
    (1, "Predrop_Vox"),
    (2, "Drop_1"),
    (3, "Break_1"),
    (4, "Build"),
    (5, "Drop_2_Climax"),
    (6, "Groove_Sparse"),
    (7, "Drop_3_Outro"),
]
# Prefer fewer stems if hangs: kick, hats, vox, acid, mix
STEMS = [
    ("kick", "E-Kick"),
    ("hats", "E-Hats"),
    ("oh", "E-OHat"),
    ("perc", "E-Perc"),
    ("acid", "Acid 303"),
    ("ringmod", "E-Syn"),
    ("stretch", "ESX Stretch"),
    ("vox", "ESX VoxAud"),
    ("mix", "E-DrumLP"),
]
FIRE_ROW = 2


def send(cmd, params=None, timeout=45.0):
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
    return {"status": "error", "message": "no response"}


def main():
    snap = send("get_session_snapshot", {"include_devices": False}, timeout=60)
    if snap.get("status") != "success":
        print("FAIL snapshot", snap)
        return 1
    tracks = (snap.get("result") or snap)["tracks"]
    by = {t["name"]: t["index"] for t in tracks}
    # resolve stretch duplicate — prefer index 7 if named, else first Stretch
    stretch_idxs = [t["index"] for t in tracks if "Stretch" in t["name"]]
    print("tracks", by)
    print("stretch_idxs", stretch_idxs)

    name_to_idx = {
        "E-Kick": by.get("E-Kick"),
        "E-Hats": by.get("E-Hats"),
        "E-OHat": by.get("E-OHat"),
        "E-Perc": by.get("E-Perc"),
        "Acid 303": by.get("Acid 303"),
        "E-Syn": by.get("E-Syn") or by.get("E-Mental") or by.get("Ring Mod"),
        "ESX Stretch": stretch_idxs[0] if stretch_idxs else by.get("ESX Stretch"),
        "ESX VoxAud": by.get("ESX VoxAud") or by.get("E-Atm") or by.get("E-Mental"),
        "E-DrumLP": by.get("E-DrumLP") or by.get("ES1 90s"),
    }
    if name_to_idx["ESX VoxAud"] is not None:
        send("set_track_name", {"track_index": name_to_idx["ESX VoxAud"], "name": "ESX VoxAud"})

    send("set_tempo", {"tempo": BPM})
    send("stop_playback")

    loaded = []
    errors = []
    for sid, sname in SCENES:
        for stem, tname in STEMS:
            tidx = name_to_idx.get(tname)
            if tidx is None:
                continue
            path = CLIP_DIR / f"ab_{sid:02d}_{sname}_{stem}.wav"
            if not path.exists():
                # try alternate naming from builder
                alts = list(CLIP_DIR.glob(f"ab_{sid:02d}_{sname}_{stem}.wav"))
                if not alts:
                    # builder used with_name prefix_stem
                    alts = list(CLIP_DIR.glob(f"ab_{sid:02d}_{sname}_{stem}.wav"))
                if not alts:
                    # files are like ab_00_Intro_kick.wav from with_name(prefix + "_kick")
                    pass
            if not path.exists():
                # builder: out_prefix.with_name(out_prefix.name + "_kick.wav")
                # pref = CLIP_DIR / f"ab_{sid:02d}_{sname}" -> ab_00_Intro_kick.wav
                path = CLIP_DIR / f"ab_{sid:02d}_{sname}_{stem}.wav"
            if not path.exists():
                errors.append(f"missing {path.name}")
                continue
            # skip silent non-mix
            if stem != "mix":
                import wave, array
                try:
                    with wave.open(str(path), "rb") as w:
                        raw = w.readframes(w.getnframes())
                    # quick peak check int16
                    import struct
                    n = min(len(raw)//2, 500000)
                    peak = 0
                    for i in range(0, n*2, 2):
                        v = abs(struct.unpack_from("<h", raw, i)[0])
                        if v > peak:
                            peak = v
                    if peak < 50:
                        print("SKIP silent", path.name)
                        continue
                except Exception as e:
                    print("peakcheck", e)
            send("delete_clip", {"track_index": tidx, "clip_index": sid})
            r = send(
                "create_audio_clip",
                {"track_index": tidx, "clip_index": sid, "path": str(path)},
                timeout=25,
            )
            cname = f"{sname}_{stem}"
            if r.get("status") != "success":
                print("FAIL", cname, r.get("message"))
                errors.append(f"{cname}: {r.get('message')}")
                continue
            send("set_clip_name", {"track_index": tidx, "clip_index": sid, "name": cname})
            loaded.append(cname)
            print("CLIP", cname, "->", tidx, sid)
        send("create_locator", {"name": f"{sid}_{sname}", "time": float(sid * 32)})

    # Fire Drop_1 (no jam double)
    fired = []
    for stem, tname in STEMS:
        if stem == "mix":
            continue
        tidx = name_to_idx.get(tname)
        if tidx is None:
            continue
        if f"Drop_1_{stem}" not in loaded and not any(x.endswith(f"Drop_1_{stem}") or x == f"Drop_1_{stem}" for x in loaded):
            # check loaded list
            if f"Drop_1_{stem}" not in loaded:
                continue
        r = send("fire_clip", {"track_index": tidx, "clip_index": FIRE_ROW})
        if r.get("status") == "success":
            fired.append(stem)
            print("FIRE", stem)
    # fix fire: always try if clip should exist
    fired = []
    for stem, tname in STEMS:
        if stem == "mix":
            continue
        tidx = name_to_idx.get(tname)
        if tidx is None:
            continue
        if not any(x == f"Drop_1_{stem}" for x in loaded):
            continue
        r = send("fire_clip", {"track_index": tidx, "clip_index": FIRE_ROW})
        if r.get("status") == "success":
            fired.append(stem)
            print("FIRE", stem)

    send("start_playback")
    info = send("get_session_info")
    res = info.get("result") or info
    print("TRACK_MAP", name_to_idx)
    print("LOADED", len(loaded), loaded)
    print("FIRED", fired)
    print("SCENES", [n for _, n in SCENES])
    print("TEMPO", res.get("tempo"), "PLAYING", res.get("is_playing"))
    print("ERRORS", errors)
    print("DONE load_mentalclean_morph_continue_v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
