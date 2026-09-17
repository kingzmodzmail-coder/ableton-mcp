"""Append feedback events to the project journal (idempotent by 'uniq' key)."""
import json, os, sys

PROJ = r"C:\Users\Gebruiker\ableton-mcp\.producer\projects\how-about-everyone-else"
JOURNAL = os.path.join(PROJ, "feedback-events.jsonl")

events = json.load(open(sys.argv[1], encoding="utf-8"))
existing = []
if os.path.exists(JOURNAL):
    with open(JOURNAL, encoding="utf-8") as f:
        existing = [json.loads(l) for l in f if l.strip()]
keys = {(e.get("event"), e.get("uniq")) for e in existing}
added = 0
with open(JOURNAL, "a", encoding="utf-8") as f:
    for ev in events:
        if (ev.get("event"), ev.get("uniq")) in keys:
            continue
        f.write(json.dumps(ev) + "\n")
        added += 1
print(f"added {added}, total events now {len(existing) + added}")
