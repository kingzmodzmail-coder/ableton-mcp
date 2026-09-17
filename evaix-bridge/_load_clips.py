import subprocess, json, time

cmd = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\ableton_cmd.py"
samples = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\cue167_v41"

def run_ableton(action, params=None):
    args = ["python", cmd, action]
    if params:
        args += ["--params", json.dumps(params)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    out = r.stdout.strip()
    ok = r.returncode == 0 and '"error"' not in out.lower()
    if not ok:
        print(f"FAIL: {action} -> {out[:200]}")
    return ok

sections = ["Intro", "Build", "Drop", "Break", "Drop2", "Outro"]
stem_map = {0: "kick", 1: "snare", 2: "hats", 3: "perc", 4: "acid", 5: "mix"}

for slot_idx, section in enumerate(sections):
    print(f"\n=== Loading {section} (slot {slot_idx}) ===")
    for track_idx, stem in stem_map.items():
        path = f"{samples}\\loop_{slot_idx:02d}_{section}_{stem}.wav"
        ok = run_ableton("create_audio_clip", {
            "track_index": track_idx,
            "clip_index": slot_idx,
            "path": path
        })
        if ok:
            print(f"  {stem}: OK")
        time.sleep(0.3)

print("\n=== CLIPS LOADED ===")
