import subprocess, os

# Check for bass in other sample dirs
dirs = [
    r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\cue167_kit",
    r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\cue167_v3",
    r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples",
]

for d in dirs:
    if os.path.isdir(d):
        print(f"\n=== {d} ===")
        for f in sorted(os.listdir(d)):
            if 'bass' in f.lower():
                sz = os.path.getsize(os.path.join(d, f))
                print(f"  {f}: {sz}")
            elif f.endswith('.wav'):
                sz = os.path.getsize(os.path.join(d, f))
                print(f"  {f}: {sz}")
