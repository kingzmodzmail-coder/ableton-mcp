import subprocess, json, time
cmd = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\ableton_cmd.py"

def dup(track, slot, label=""):
    r = subprocess.run(
        ["python", cmd, "duplicate_session_clip_to_arrangement",
         "--params", json.dumps({"track_index": track, "slot_index": slot})],
        capture_output=True, text=True, timeout=30)
    out = r.stdout.strip() or r.stderr.strip()
    ok = '"error"' not in out.lower()
    status = "OK" if ok else f"FAIL: {out[:80]}"
    print(f"  T{track}S{slot} {label}: {status}")
    time.sleep(0.1)
    return ok

# Tracks with all 6 sections
stem_tracks = [
    (2, "Hats"),
    (3, "Perc"),
    (6, "Mix"),
    (7, "Kick"),
    (8, "Snare"),
    (9, "Acid"),
    (12, "Drone"),
]
# Tracks with only 1 loop (slot 0)
loop_tracks = [
    (10, "Bass"),
    (11, "PercLoop"),
]

sections = [
    (0, "Intro"),
    (1, "Build"),
    (2, "Drop"),
    (3, "Break"),
    (4, "Drop2"),
    (5, "Outro"),
]

print("=== Duplicating clips to arrangement ===")
for slot, section in sections:
    print(f"\n--- {section} ---")
    for track, name in stem_tracks:
        dup(track, slot, f"{name}/{section}")
    # Bass/PercLoop only have slot 0 for all sections
    if slot == 0:
        for track, name in loop_tracks:
            dup(track, 0, f"{name}/all")

print("\n=== Done ===")
