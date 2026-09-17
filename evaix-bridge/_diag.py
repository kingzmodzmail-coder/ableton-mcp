import subprocess, json
cmd = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\ableton_cmd.py"

# Check if Kick files exist
import os
path = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\cue167_v41\loop_00_Intro_kick.wav"
print(f"Exists: {os.path.exists(path)}")

# Try to load Kick manually
args = ["python", cmd, "create_audio_clip", "--params", json.dumps({"track_index": 0, "clip_index": 0, "path": path})]
r = subprocess.run(args, capture_output=True, text=True, timeout=30)
print(f"stdout: {r.stdout.strip()}")
print(f"stderr: {r.stderr.strip()}")

# Try Acid
path2 = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\cue167_v41\loop_00_Intro_acid.wav"
print(f"Exists: {os.path.exists(path2)}")
args2 = ["python", cmd, "create_audio_clip", "--params", json.dumps({"track_index": 4, "clip_index": 0, "path": path2})]
r2 = subprocess.run(args2, capture_output=True, text=True, timeout=30)
print(f"stdout: {r2.stdout.strip()}")
print(f"stderr: {r2.stderr.strip()}")
