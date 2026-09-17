import subprocess, json, time

cmd = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\ableton_cmd.py"
samples = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples"

def run(action, params=None):
    args = ["python", cmd, action]
    if params:
        args += ["--params", json.dumps(params)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    err = r.stderr.strip()
    if err and ('"error"' in err.lower()):
        print(f"  FAIL {action}: {err[:200]}")
        return False
    print(f"  {action}: OK")
    return True

# Load heavy bass into track 10
print("Loading bass loop...")
run("create_audio_clip", {"track_index": 10, "clip_index": 0, "path": f"{samples}\\heavy_bass_hc01.wav"})
run("set_track_name", {"track_index": 10, "name": "Bass"})

# Also load cue167_kit perc loop as extra texture
run("create_audio_track", {})
time.sleep(0.3)
run("set_track_name", {"track_index": 11, "name": "PercLoop"})
run("create_audio_clip", {"track_index": 11, "clip_index": 0, "path": f"{samples}\\cue167_kit\\perc_loop.wav"})

# Fire Intro clips (slot 0) on all tracks
print("\n=== Firing Intro clips ===")
for track_idx in range(12):
    run("fire_clip", {"track_index": track_idx, "clip_index": 0})

# Start playback
print("\n=== Starting playback ===")
run("start_playback")

time.sleep(2)

# Get session info to verify
r = subprocess.run(["python", cmd, "get_session_info"], capture_output=True, text=True, timeout=30)
print(f"\n{json.dumps(json.loads(r.stdout.strip()), indent=2)}")
