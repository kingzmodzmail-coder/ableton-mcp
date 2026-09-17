from pathlib import Path
p = Path(r'C:\Users\Gebruiker\Downloads\cue\src\lib\bridge.ts')
t = p.read_text(encoding='utf-8')
old = 'url: "ws://127.0.0.1:8741"'
new = 'url: "ws://127.0.0.1:7843"'
if old not in t:
    raise SystemExit('url not found: ' + repr(t[t.find('url'):t.find('url')+40] if 'url' in t else 'no url'))
p.write_text(t.replace(old, new, 1), encoding='utf-8')
print('cue MDBP -> 7843')
