import subprocess, os

samples = r"C:\Users\Gebruiker\ableton-mcp\evaix-bridge\samples\cue167_v41"
files = sorted(os.listdir(samples))
for f in files:
    size = os.path.getsize(os.path.join(samples, f))
    print(f"{f:60s} {size:>8d}")
