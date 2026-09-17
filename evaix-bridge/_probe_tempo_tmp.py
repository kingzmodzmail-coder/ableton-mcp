import json, socket
s = socket.create_connection(("127.0.0.1", 9877), 5)
s.sendall(b'{"type":"get_session_info","params":{}}')
s.settimeout(15)
d = b""
while True:
    c = s.recv(8192)
    if not c:
        break
    d += c
    try:
        r = json.loads(d)
        break
    except json.JSONDecodeError:
        pass
res = r.get("result", r)
print("tempo", res.get("tempo"), "playing", res.get("is_playing"))
