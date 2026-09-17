import subprocess, json, time

cmd = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\ableton_cmd.py"
samples = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\cue167_v41"

def run(action, params=None):
    args = ["python", cmd, action]
    if params:
        args += ["--params", json.dumps(params)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    out = r.stdout.strip()
    err = r.stderr.strip()
    if err and '"error"' in err.lower():
        print(f"  FAIL {action}: {err[:200]}")
        return False
    print(f"  {action}: OK")
    return True

# Create audio tracks for Kick, Snare, Acid
print("Creating audio tracks...")
run("create_audio_track", {})  # Track 7
time.sleep(0.3)
run("set_track_name", {"track_index": 7, "name": "Kick"})

run("create_audio_track", {})  # Track 8
time.sleep(0.3)
run("set_track_name", {"track_index": 8, "name": "Snare"})

run("create_audio_track", {})  # Track 9
time.sleep(0.3)
run("set_track_name", {"track_index": 9, "name": "Acid"})

print("\n=== Loading clips ===")
sections = ["Intro", "Build", "Drop", "Break", "Drop2", "Outro"]
stem_tracks = {"kick": 7, "snare": 8, "hats": 2, "perc": 3, "acid": 9, "bass": 5, "mix": 6}

for slot_idx, section in enumerate(sections):
    print(f"\n--- {section} (slot {slot_idx}) ---")
    for stem, track_idx in stem_tracks.items():
        path = f"{samples}\\loop_{slot_idx:02d}_{section}_{stem}.wav"
        run("create_audio_clip", {"track_index": track_idx, "clip_index": slot_idx, "path": path})
        time.sleep(0.2)

print("\n=== ALL CLIPS LOADED ===")
