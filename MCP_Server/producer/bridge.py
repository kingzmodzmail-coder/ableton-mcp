import json
import os
import socket


class Bridge:
    """One request per connection; never retry an ambiguous mutation."""
    def send_command(self, command, params=None):
        with socket.create_connection((os.getenv('ABLETON_HOST', '127.0.0.1'),
                                       int(os.getenv('ABLETON_PORT', '9877'))), timeout=5) as sock:
            sock.settimeout(45)
            sock.sendall(json.dumps({'type': command, 'params': params or {}}).encode())
            data = bytearray()
            while len(data) < 64 * 1024 * 1024:
                chunk = sock.recv(65536)
                if not chunk:
                    raise ConnectionError('Bridge closed before a complete response')
                data.extend(chunk)
                try:
                    reply = json.loads(data)
                except (ValueError, UnicodeDecodeError):
                    continue
                if reply.get('status') == 'error':
                    raise RuntimeError(reply.get('message', 'Ableton command failed'))
                return reply.get('result', reply)
        raise ValueError('Snapshot exceeds 64 MB')
