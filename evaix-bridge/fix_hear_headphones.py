import json, socket, subprocess, os

HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=30.0):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall(payload)
        sock.settimeout(timeout)
        chunks = []
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue

snap = send("get_session_snapshot", {"include_devices": False})
tracks = (snap.get("result") or {}).get("tracks") or []
by = {t["name"]: t for t in tracks}

# STOP noisy beds; keep clean drums + acid
noisy = ["E-Mental", "E-Atm", "E-Syn", "E-Bass", "CRISP_e2e_kick"]
keep_fire = ["E-Kick", "E-Hats", "E-OHat", "E-Perc", "1-Drift", "Acid 303 Poly", "Tholin Bass"]

for name in noisy:
    t = by.get(name)
    if not t:
        continue
    send("set_track_mute", {"track_index": t["index"], "mute": True})
    for sl in (t.get("clip_slots") or []):
        if sl.get("has_clip") and sl.get("is_playing"):
            send("stop_clip", {"track_index": t["index"], "clip_index": sl["index"]})
    print("muted/stopped", name)

# unmute keep tracks and fire slot 4 (Drop) if has clip else first playing-capable
for name in keep_fire:
    t = by.get(name)
    if not t:
        # fuzzy
        for k,v in by.items():
            if name.lower() in k.lower() or k.lower() in name.lower():
                t = v; break
    if not t:
        print("missing", name); continue
    send("set_track_mute", {"track_index": t["index"], "mute": False})
    slots = t.get("clip_slots") or []
    # prefer index 4 Drop, else 2, else any
    preferred = [4, 2, 3, 1, 0, 5]
    fired = False
    for ci in preferred:
        for sl in slots:
            if sl.get("index") == ci and sl.get("has_clip"):
                r = send("fire_clip", {"track_index": t["index"], "clip_index": ci})
                print("fire", t["name"], ci, r.get("status"))
                fired = True
                break
        if fired:
            break

send("set_tempo", {"tempo": 162.0})
send("start_playback")
info = send("get_session_info")
print("PLAYING", (info.get("result") or {}).get("is_playing"), "tempo", (info.get("result") or {}).get("tempo"))

# Set Windows default to Realtek HD Audio 2nd output
guid = "{ece442eb-9611-4ef9-846e-5192a416cf98}"
ps = f'''
$ErrorActionPreference = "Continue"
# Try AudioDeviceCmdlets
if (-not (Get-Module -ListAvailable AudioDeviceCmdlets)) {{
  try {{ Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser -AllowClobber -ErrorAction Stop }} catch {{ Write-Host "Install AudioDeviceCmdlets failed:" $_.Exception.Message }}
}}
try {{
  Import-Module AudioDeviceCmdlets -ErrorAction Stop
  Get-AudioDevice -List | Format-Table Index,Default,Type,Name,ID -AutoSize
  $d = Get-AudioDevice -List | Where-Object {{ $_.Name -like "*2nd output*" -or $_.Name -like "*Realtek HD Audio 2nd*" }}
  if ($d) {{
    Set-AudioDevice -ID $d.ID
    Write-Host "SET DEFAULT:" $d.Name $d.ID
  }} else {{
    # try by guid
    Set-AudioDevice -ID "{guid}"
    Write-Host "SET DEFAULT BY GUID"
  }}
  Get-AudioDevice -Playback | Format-List
}} catch {{
  Write-Host "AudioDeviceCmdlets path failed:" $_.Exception.Message
}}
# Also try nircmd if present
$nircmd = @(
  "$env:USERPROFILE\\Downloads\\nircmd.exe",
  "C:\\Tools\\nircmd.exe",
  "C:\\Windows\\nircmd.exe"
) | Where-Object {{ Test-Path $_ }} | Select-Object -First 1
if ($nircmd) {{
  & $nircmd setdefaultsounddevice "Realtek HD Audio 2nd output" 1
  & $nircmd setdefaultsounddevice "Realtek HD Audio 2nd output" 2
  Write-Host "nircmd set default"
}} else {{ Write-Host "no nircmd" }}
'''
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], check=False)
