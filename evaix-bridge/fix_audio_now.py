import json, socket, subprocess, sys

HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=60.0):
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

def ok(r, label):
    print(label, r.get("status"), (r.get("result") or r.get("message") or "")[:200] if isinstance(r.get("result"), str) else r.get("result") is not None or r.get("message"))
    return r

info = send("get_session_info")
print("BEFORE", json.dumps(info.get("result") or info, indent=2)[:500])

# start playing
for cmd in ("start_playback", "start_playing", "continue_playing"):
    r = send(cmd)
    if r.get("status") == "success":
        print("started with", cmd)
        break
    print("try", cmd, r.get("message") or r)

snap = send("get_session_snapshot", {"include_devices": False})
res = snap.get("result") or {}
tracks = res.get("tracks") or []
print("tracks", len(tracks), "tempo", res.get("tempo") or (info.get("result") or {}).get("tempo"))

# unmute all, fire any clips on slot 0-5 that exist; prefer names with Drop/kick/acid
fired = []
for t in tracks:
    idx = t.get("index")
    name = t.get("name")
    # unmute
    send("set_track_mute", {"track_index": idx, "mute": False})
    send("set_track_solo", {"track_index": idx, "solo": False})
    for sl in (t.get("clip_slots") or []):
        if not sl.get("has_clip"):
            continue
        ci = sl.get("index")
        cname = (sl.get("clip_name") or sl.get("name") or "")
        # fire drop-ish or first few slots
        if ci <= 5 or "Drop" in cname or "drop" in cname or "kick" in cname.lower() or "acid" in cname.lower():
            r = send("fire_clip", {"track_index": idx, "clip_index": ci})
            if r.get("status") == "success":
                fired.append(f"{name}:{ci}:{cname}")

print("FIRED", len(fired))
for f in fired[:30]:
    print(" ", f)

# ensure tempo 162 for live set
send("set_tempo", {"tempo": 162.0})

# try start again
send("start_playback")
send("start_playing")

info2 = send("get_session_info")
print("AFTER", json.dumps(info2.get("result") or info2, indent=2)[:600])

# Windows: set Realtek as default via nircmd / SoundVolumeView if available
for tool in [
    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
]:
    pass

# List audio endpoints with powershell COM
ps = r'''
$enum = New-Object -ComObject MMDeviceEnumerator -ErrorAction SilentlyContinue
# fallback: use AudioSes via Get-Item
$code = @"
using System;
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
  int n1(); int n2(); int GetChannelCount(out uint c);
}
"@
Write-Host "Trying to list default via registry names..."
Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render" | ForEach-Object {
  $p = Join-Path $_.PSPath "Properties"
  try {
    $name = (Get-ItemProperty $p -ErrorAction Stop)."{a45c254e-df1c-4efd-8020-67d146a850e0},2"
    $state = (Get-ItemProperty $_.PSPath).DeviceState
    Write-Host "$state | $name | $($_.PSChildName)"
  } catch {}
}
'''
subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
