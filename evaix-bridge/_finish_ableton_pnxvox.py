# -*- coding: utf-8 -*-
"""Finish Ableton load for PneumatixKick+PozekVox stems."""
import json, socket, sys
from pathlib import Path
BRIDGE = Path(r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge")
sys.path.insert(0, str(BRIDGE))
import build_liveset_15s_morphs as morph

OUT = BRIDGE / "samples" / "crisp-dna" / "esx1-valveforce-swingfx" / "pneumatix_pozekvox"
HOST, PORT = "127.0.0.1", 9877
BPM = 162.0
SCENES = [
    (0, "Intro_Kick"), (1, "Hats_In"), (2, "Acid_Under"), (3, "Stretch_Roll"),
    (4, "Full_Groove"), (5, "Break_Filter"), (6, "Peak_Drive"), (7, "Outro_Valve"),
]
FIRE_ROW = 6

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
    return {"status": "error", "message": "no response"}

def safe_delete(ti, ci):
    send("delete_clip", {"track_index": ti, "clip_index": ci})

def load_audio(ti, ci, path, name):
    safe_delete(ti, ci)
    r = send("create_audio_clip", {"track_index": ti, "clip_index": ci, "path": str(path)}, timeout=120)
    if r.get("status") != "success":
        print("FAIL", name, r)
        return False
    send("set_clip_name", {"track_index": ti, "clip_index": ci, "name": name})
    print("OK", name, "->", ti, ci)
    return True

snap = send("get_session_snapshot", {"include_devices": False}, timeout=60)
if snap.get("status") != "success":
    print("ABORT", snap); raise SystemExit(1)
tracks = snap["result"]["tracks"]
by = {t["name"]: t["index"] for t in tracks}
print("tracks", by)
send("set_tempo", {"tempo": BPM})
send("stop_playback")
for t in tracks:
    for sl in t.get("clip_slots") or []:
        if sl.get("has_clip"):
            send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})

kick_idx = by.get("E-Kick")
hats_idx = by.get("E-Hats")
perc_idx = by.get("E-Perc")
oh_idx = by.get("E-OHat")
acid_idx = by.get("Acid 303") or by.get("E-Syn")
# unique stretch
stretch_idx = by.get("ESX Stretch")
# pick first ESX Stretch by scanning
for t in tracks:
    if t["name"] == "ESX Stretch":
        stretch_idx = t["index"]; break
jam_idx = by.get("ESX Jam") or by.get("E2S Jam")

# Map vox: prefer track not used; rename first free audio-ish
used = {kick_idx, hats_idx, perc_idx, oh_idx, acid_idx, stretch_idx, jam_idx}
vox_idx = by.get("ESX Vox") or by.get("E-Vox")
if vox_idx is None:
    for t in tracks:
        if t["index"] in used:
            continue
        # skip returns/master-like names
        n = t["name"].lower()
        if any(k in n for k in ("master", "return", "mental", "atm", "grain", "tholin", "poly")):
            continue
        vox_idx = t["index"]
        send("set_track_name", {"track_index": vox_idx, "name": "ESX Vox"})
        print("vox mapped from", t["name"], "->", vox_idx)
        break

# Clear target rows
for row, _ in SCENES:
    for idx in (kick_idx, hats_idx, perc_idx, oh_idx, acid_idx, stretch_idx, vox_idx, jam_idx):
        if idx is not None:
            safe_delete(idx, row)

for sid, name in SCENES:
    prefix = f"s{sid}_{name}"
    paths = {
        "kick": OUT / f"{prefix}_kick.wav",
        "hats": OUT / f"{prefix}_hats.wav",
        "oh": OUT / f"{prefix}_oh.wav",
        "perc": OUT / f"{prefix}_perc.wav",
        "stretch": OUT / f"{prefix}_stretch.wav",
        "acid": OUT / f"{prefix}_acid.wav",
        "vox": OUT / f"{prefix}_vox.wav",
        "mix": OUT / "sections" / f"{prefix}_pnxvox_mix.wav",
    }
    if kick_idx is not None and morph.layer_has_signal(paths["kick"]):
        load_audio(kick_idx, sid, paths["kick"], f"{name}_kick")
    if hats_idx is not None and morph.layer_has_signal(paths["hats"]):
        load_audio(hats_idx, sid, paths["hats"], f"{name}_hats")
    if oh_idx is not None and morph.layer_has_signal(paths["oh"]):
        load_audio(oh_idx, sid, paths["oh"], f"{name}_oh")
    if perc_idx is not None and morph.layer_has_signal(paths["perc"]):
        load_audio(perc_idx, sid, paths["perc"], f"{name}_junk")
    if stretch_idx is not None and morph.layer_has_signal(paths["stretch"]):
        load_audio(stretch_idx, sid, paths["stretch"], f"{name}_stretch")
    if acid_idx is not None and morph.layer_has_signal(paths["acid"]):
        load_audio(acid_idx, sid, paths["acid"], f"{name}_saw303")
    if vox_idx is not None and morph.layer_has_signal(paths["vox"]):
        load_audio(vox_idx, sid, paths["vox"], f"{name}_vox")
    if jam_idx is not None and jam_idx not in (stretch_idx, vox_idx) and paths["mix"].exists():
        load_audio(jam_idx, sid, paths["mix"], f"{name}_PNXVox_mix")
    send("create_locator", {"name": f"{sid}_{name}", "time": float(sid * 96)})

fired = []
for label, idx, key in [
    ("kick", kick_idx, "kick"), ("hats", hats_idx, "hats"), ("oh", oh_idx, "oh"),
    ("perc", perc_idx, "perc"), ("stretch", stretch_idx, "stretch"),
    ("acid", acid_idx, "acid"), ("vox", vox_idx, "vox"),
]:
    if idx is None:
        continue
    p = OUT / f"s{FIRE_ROW}_Peak_Drive_{key}.wav"
    if key == "acid":
        p = OUT / f"s{FIRE_ROW}_Peak_Drive_acid.wav"
    if not p.exists() or not morph.layer_has_signal(p):
        continue
    r = send("fire_clip", {"track_index": idx, "clip_index": FIRE_ROW})
    if r.get("status") == "success":
        fired.append(label)
        print("FIRE", label)
send("start_playback")
info = send("get_session_info")
res = info.get("result") or info
print("TEMPO", res.get("tempo"), "PLAYING", res.get("is_playing"), "FIRED", fired, "VOX_IDX", vox_idx)
print("DONE ableton finish load")
