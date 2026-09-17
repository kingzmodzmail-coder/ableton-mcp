import json, socket
HOST, PORT = "127.0.0.1", 9877

def send(cmd, params=None, timeout=30):
    payload = json.dumps({"type": cmd, "params": params or {}}).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.sendall(payload)
        s.settimeout(timeout)
        chunks = []
        while True:
            ch = s.recv(8192)
            if not ch:
                break
            chunks.append(ch)
            try:
                return json.loads(b"".join(chunks).decode())
            except json.JSONDecodeError:
                continue

r = send("get_script_info")
print(json.dumps(r, indent=2)[:4000])
print("---")
# try creating clip at slot 11
r2 = send("create_clip", {"track_index": 0, "clip_index": 11, "length": 4.0})
print("create slot11", r2)
r3 = send("create_clip", {"track_index": 0, "clip_index": 8, "length": 4.0})
print("create slot8", r3)
r4 = send("create_audio_clip", {"track_index": 2, "clip_index": 10, "path": r"C:\Users\Gebruiker\Downloads\ESXSD_Factory\wav\146_SinKick.wav"})
print("audio slot10", r4)
