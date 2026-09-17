#!/usr/bin/env python3
"""Arrange Disappear-in-Sound materials ALREADY in Live into finishable track.
Run ON PC: python C:\\Users\\Gebruiker\\ableton-mcp\\evaix-bridge\\arrange_disappear_ableton.py
Requires AbletonMCP :9877. Live Intro 16-track cap — reuse tracks, do not create beyond.
"""
from __future__ import annotations

import json
import socket
import time
from pathlib import Path

HOST, PORT = "127.0.0.1", 9877
BPM = 180.0
BAR_BEATS = 4.0

# Structure (bars) — matches stem bounce NOTES
STRUCTURE = [
    ("Intro", 0, 16),
    ("Build", 16, 32),
    ("Drop", 32, 56),
    ("Break", 56, 72),
    ("Drop2", 72, 100),
    ("Outro", 100, 112),
]

# Mute keywords for non-DIS full mixes
MUTE_IF = (
    "warehouse", "vit3", "vite", "how about", "everyone else", "inspired",
)


def send(cmd: str, params: dict | None = None, timeout: float = 30.0):
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


def result(resp):
    if resp.get("status") == "error":
        raise RuntimeError(resp.get("message", resp))
    return resp.get("result", resp)


def main():
    info = result(send("get_session_info", timeout=20))
    print("SESSION", json.dumps(info, indent=2)[:2000])
    tracks = info.get("tracks") or info.get("track_list") or []
    # normalize
    if not tracks and "result" in info:
        tracks = info["result"].get("tracks", [])

    result(send("set_tempo", {"tempo": BPM}))
    print("tempo ->", BPM)

    # Mute non-DIS / unmute DIS
    for i, t in enumerate(tracks):
        name = (t.get("name") or t.get("track_name") or "").strip()
        low = name.lower()
        is_dis = "dis " in low or low.startswith("dis") or "disappear" in low
        is_noise = any(k in low for k in MUTE_IF)
        # empty audio slots keep available
        mute = bool(is_noise) or (not is_dis and "audio" in low and any(x in low for x in ("3-audio", "4-audio")))
        # Prefer: mute only clear full-mix refs
        if is_noise:
            for cmd in ("set_track_mute", "mute_track", "set_mute"):
                try:
                    result(send(cmd, {"track_index": i, "mute": True}))
                    print(f"MUTE {i} {name}")
                    break
                except Exception as e:
                    last = e
            else:
                print(f"mute fail {i} {name}: {last}")
        elif is_dis:
            for cmd in ("set_track_mute", "mute_track", "set_mute"):
                try:
                    result(send(cmd, {"track_index": i, "mute": False}))
                    print(f"UNMUTE {i} {name}")
                    break
                except Exception:
                    pass

    # Locators for structure
    for name, b0, _b1 in STRUCTURE:
        t = b0 * BAR_BEATS
        try:
            result(send("create_locator", {"name": name, "time": t}))
            print(f"locator {name} @ {t}")
        except Exception as e:
            print(f"locator skip {name}: {e}")

    # Duplicate session clips → arrangement by section energy
    # Heuristic: for each DIS audio track, place clip at 0 and rely on mute automation via clip launch scenes
    # Fire intro scene clips if present
    try:
        result(send("stop_playback"))
    except Exception:
        pass

    # Place arrangement copies at bar 0 for DIS tracks (full length stems already in session)
    for i, t in enumerate(tracks):
        name = (t.get("name") or "").lower()
        if not ("dis " in name or name.startswith("dis")):
            continue
        # try duplicate session clip 0 → arrangement at beat 0
        for clip_index in range(0, 8):
            try:
                result(send(
                    "duplicate_session_clip_to_arrangement",
                    {"track_index": i, "clip_index": clip_index, "arrangement_time": 0.0},
                    timeout=60,
                ))
                print(f"arr clip track={i} slot={clip_index}")
                break
            except Exception as e:
                if clip_index == 0:
                    print(f"dup fail {i}/{clip_index}: {e}")

    # Switch arrangement view + set song start
    try:
        result(send("switch_to_arrangement_view"))
    except Exception as e:
        print("arr view", e)
    try:
        result(send("set_current_song_time", {"time": 0.0}))
    except Exception:
        pass

    # Fire DIS session clips as fallback audition
    for i, t in enumerate(tracks):
        name = (t.get("name") or "").lower()
        if "dis " in name or name.startswith("dis"):
            try:
                result(send("fire_clip", {"track_index": i, "clip_index": 0}))
                print(f"fire {i} {t.get('name')}")
            except Exception as e:
                print(f"fire skip {i}: {e}")

    try:
        result(send("start_playback"))
    except Exception as e:
        print("play", e)

    # Write session note for FineTuniX
    note = Path(r"C:\Users\Gebruiker\Documents\Ableton\DisappearInSound_v1_SESSION.txt")
    try:
        note.write_text(
            f"Disappear in Sound Ableton v1\nBPM {BPM}\nKey C#m\n"
            f"Structure: Intro 1-16, Build 17-32, Drop 33-56, Break 57-72, Drop2 73-100, Outro 101-112\n"
            f"Mute Vit3/Warehouse full mixes; focus DIS MIDI + stems.\n"
            f"Bounce Export Audio → Downloads\\EvAIx_DisappearInSound_Ableton_v1.mp3\n"
        )
        print("wrote", note)
    except Exception as e:
        print("note fail", e)

    info2 = result(send("get_session_info", timeout=20))
    print("DONE tempo", info2.get("tempo") or info2.get("song_tempo"))
    print(json.dumps({"tracks": len(tracks), "bpm": BPM, "structure": STRUCTURE}, indent=2))


if __name__ == "__main__":
    main()
