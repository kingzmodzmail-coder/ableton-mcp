import subprocess, json, time

cmd = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\ableton_cmd.py"

def fire(track, slot, label=""):
    r = subprocess.run(["python", cmd, "fire_clip", "--params", json.dumps({"track_index": track, "clip_index": slot})],
                       capture_output=True, text=True, timeout=15)
    out = r.stdout.strip() or r.stderr.strip()
    ok = '"error"' not in out.lower()
    print(f"  {label or f'T{track}S{slot}'}: {'OK' if ok else 'FAIL'}")
    return ok

# Tracks with clips: 2=Hats, 3=Perc, 6=Mix, 7=Kick, 8=Snare, 9=Acid, 10=Bass, 11=PercLoop
tracks = [2, 3, 6, 7, 8, 9, 10, 11]

# Let Intro play ~8 bars (about 12s at 162 BPM)
print("Intro playing... (8 bars)")
time.sleep(12)

# Section 1: Build (slot 1)
print("\n=== Build ===")
for t in tracks:
    fire(t, 1)
time.sleep(12)

# Section 2: Drop (slot 2) 
print("\n=== Drop ===")
for t in tracks:
    fire(t, 2)
time.sleep(16)

# Section 3: Break (slot 3)
print("\n=== Break ===")
for t in tracks:
    fire(t, 3)
time.sleep(12)

# Section 4: Drop2 (slot 4)
print("\n=== Drop2 ===")
for t in tracks:
    fire(t, 4)
time.sleep(16)

# Section 5: Outro (slot 5)
print("\n=== Outro ===")
for t in tracks:
    fire(t, 5)
time.sleep(8)

# Get final state
r = subprocess.run(["python", cmd, "get_session_info"], capture_output=True, text=True, timeout=15)
info = json.loads(r.stdout.strip())
print(f"\n=== Session: {info['tempo']} BPM | Playing: {info['is_playing']} | Time: {info['current_song_time']:.1f}s ===")

print("\n=== Full arrangement cycled ===")
