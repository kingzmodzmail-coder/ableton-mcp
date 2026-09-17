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
    if err and ('"error"' in err.lower()):
        print(f"  FAIL {action}: {err[:200]}")
        return False
    print(f"  {action}: OK")
    return True

# Create fresh bass track
print("Creating bass track...")
run("create_audio_track", {})  # Track 10
time.sleep(0.3)
run("set_track_name", {"track_index": 10, "name": "Bass"})

# Load bass clips into track 10
sections = ["Intro", "Build", "Drop", "Break", "Drop2", "Outro"]
print("\n=== Loading Bass clips ===")
for slot_idx, section in enumerate(sections):
    path = f"{samples}\\loop_{slot_idx:02d}_{section}_bass.wav"
    run("create_audio_clip", {"track_index": 10, "clip_index": slot_idx, "path": path})
    time.sleep(0.2)

# Verify session info
print("\n=== Session Info ===")
r = subprocess.run(["python", cmd, "get_session_info"], capture_output=True, text=True, timeout=30)
print(r.stdout.strip()[:1000])

print("\n=== TRACK BUILD DONE ===")
