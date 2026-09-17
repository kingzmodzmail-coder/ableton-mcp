import subprocess, json, time

cmd = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\ableton_cmd.py"

def run_ableton(action, params=None):
    args = ["python", cmd, action]
    if params:
        args += ["--params", json.dumps(params)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    out = r.stdout.strip()
    print(f"> {action} {json.dumps(params) if params else ''}")
    print(out[:300])
    print()
    return r.returncode == 0

# Step 1: Set tempo
run_ableton("set_tempo", {"tempo": 162.0})

# Step 2: Rename existing tracks
run_ableton("set_track_name", {"track_index": 0, "name": "Kick"})
run_ableton("set_track_name", {"track_index": 1, "name": "Snare"})
run_ableton("set_track_name", {"track_index": 2, "name": "Hats"})
run_ableton("set_track_name", {"track_index": 3, "name": "Perc"})
run_ableton("set_track_name", {"track_index": 4, "name": "Acid"})

# Step 3: Create bass and mix tracks
run_ableton("create_audio_track", {})
time.sleep(0.5)
run_ableton("set_track_name", {"track_index": 5, "name": "Bass"})

run_ableton("create_audio_track", {})
time.sleep(0.5)
run_ableton("set_track_name", {"track_index": 6, "name": "Mix"})

print("=== TRACKS DONE ===")
