import json
import socket

import pytest

from MCP_Server import server
from MCP_Server import script_handshake


class SocketStub:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.timeouts = []
        self.closed = False

    def settimeout(self, value):
        self.timeouts.append(value)

    def sendall(self, data):
        self.request = json.loads(data)

    def recv(self, size):
        value = next(self.chunks, b'')
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        self.closed = True


def test_import_timeout_and_split_utf8():
    raw = json.dumps({'status': 'success', 'result': {'name': 'café'}}, ensure_ascii=False).encode()
    split = raw.index(b'\xc3') + 1
    sock = SocketStub([raw[:split], raw[split:]])
    connection = server.AbletonConnection('localhost', 9877, sock)
    assert connection.send_command('create_audio_clip')['name'] == 'café'
    assert sock.timeouts == [65.0]
    assert not sock.closed


@pytest.mark.parametrize('chunks', [[socket.timeout()], [b'{', b''], [ConnectionResetError()]])
def test_failed_exchange_closes_socket(chunks):
    sock = SocketStub(chunks)
    connection = server.AbletonConnection('localhost', 9877, sock)
    with pytest.raises(Exception):
        connection.send_command('get_session_info')
    assert sock.closed
    assert connection.sock is None


def test_response_limit_disconnects(monkeypatch):
    monkeypatch.setattr(server, 'MAX_RESPONSE_BYTES', 16)
    sock = SocketStub([b' ' * 17])
    connection = server.AbletonConnection('localhost', 9877, sock)
    with pytest.raises(Exception, match='size limit'):
        connection.send_command('get_session_info')
    assert sock.closed


def test_alternative_bridge_is_identified_without_reinstall_advice(monkeypatch, caplog):
    monkeypatch.setattr(script_handshake, '_script_info', None)
    calls = []

    def send(command):
        calls.append(command)
        if command == 'get_script_info':
            raise RuntimeError('Unknown command: get_script_info')
        return {'bridge_version': '1.8.0'}

    result = script_handshake.handshake(send)
    assert result['implementation'] == 'alternative_bridge'
    assert result['bridge_version'] == '1.8.0'
    assert calls == ['get_script_info', 'get_session_info']
    assert 'restart' not in caplog.text.lower()
    assert 'outdated' not in caplog.text.lower()
