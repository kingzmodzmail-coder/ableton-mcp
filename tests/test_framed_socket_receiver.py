"""Phase 0 / gate R0: TCP framing regression tests.

Covers the three stream conditions the bridge previously mishandled:
fragmentation, coalescing, and oversized/never-completed frames. The
FramedSocketReceiver is loaded straight out of the Remote Script file, because
that file is installed standalone into Live and imports nothing from the
package.
"""

import ast
import codecs
import json
import socket
import threading
import types
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[1]
          / "MCP_Server" / "bundled_ableton_remote_script" / "AbletonMCP_init.py")

# The Remote Script imports _Framework, which exists only inside Live, so the
# module cannot be imported here. Lift the real class source out of the shipped
# file instead — a copy in the test would stop testing what Live runs.
_WANTED_ASSIGNMENTS = {"MAX_REQUEST_BYTES", "PARTIAL_FRAME_TIMEOUT_SEC"}
_WANTED_CLASSES = {"FramedSocketReceiver"}


def _load_module():
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in _WANTED_ASSIGNMENTS
                for t in node.targets):
            wanted.append(node)
        elif isinstance(node, ast.ClassDef) and node.name in _WANTED_CLASSES:
            wanted.append(node)

    found = {getattr(n, "name", None) for n in wanted}
    assert _WANTED_CLASSES <= found, (
        "FramedSocketReceiver missing from %s" % SCRIPT)

    module = types.ModuleType("ableton_mcp_remote_script_subset")
    module.__dict__.update(json=json, codecs=codecs)
    exec(compile(ast.Module(body=wanted, type_ignores=[]), str(SCRIPT), "exec"),
         module.__dict__)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


@pytest.fixture
def receiver(mod):
    return mod.FramedSocketReceiver()


# --- framing semantics -----------------------------------------------------

def test_single_command(receiver):
    assert receiver.feed(b'{"type":"get_session_info"}') == [
        {"type": "get_session_info"}]


def test_fragmented_across_packets(receiver):
    """One command split over several recv() calls must not be lost."""
    raw = json.dumps({"type": "set_tempo", "params": {"tempo": 170}}).encode()
    for byte in raw[:-1]:
        assert receiver.feed(bytes([byte])) == []
    assert receiver.feed(raw[-1:]) == [
        {"type": "set_tempo", "params": {"tempo": 170}}]


def test_coalesced_commands_in_one_packet(receiver):
    """The regression that wedged the connection: two objects, one packet."""
    raw = (json.dumps({"type": "a"}) + json.dumps({"type": "b"})).encode()
    assert receiver.feed(raw) == [{"type": "a"}, {"type": "b"}]


def test_newline_delimited_commands(receiver):
    raw = (json.dumps({"type": "a"}) + "\n" + json.dumps({"type": "b"}) + "\n").encode()
    assert receiver.feed(raw) == [{"type": "a"}, {"type": "b"}]
    assert not receiver.has_pending()


def test_coalesced_plus_partial_tail(receiver):
    """A whole command followed by half of the next one."""
    whole = json.dumps({"type": "a"})
    partial = '{"type":"b"'
    assert receiver.feed((whole + partial).encode()) == [{"type": "a"}]
    assert receiver.has_pending()
    assert receiver.feed(b"}") == [{"type": "b"}]


def test_multibyte_character_split_across_packets(receiver):
    """An accented clip name must not raise when it straddles a boundary."""
    raw = json.dumps({"type": "set_clip_name", "name": "Café ✅"}).encode()
    split = raw.find("é".encode()) + 1  # mid-character
    assert receiver.feed(raw[:split]) == []
    assert receiver.feed(raw[split:]) == [
        {"type": "set_clip_name", "name": "Café ✅"}]


def test_oversized_frame_is_rejected(mod):
    small = mod.FramedSocketReceiver(max_pending=1024)
    with pytest.raises(ValueError, match="without a complete JSON command"):
        small.feed(b'{"type":"x","pad":"' + b"A" * 4096)


def test_reset_clears_partial_frame(receiver):
    receiver.feed(b'{"type":"a"')
    assert receiver.has_pending()
    receiver.reset()
    assert not receiver.has_pending()
    assert receiver.feed(b'{"type":"b"}') == [{"type": "b"}]


def test_whitespace_between_commands_ignored(receiver):
    assert receiver.feed(b'  {"type":"a"}\r\n\t {"type":"b"}  ') == [
        {"type": "a"}, {"type": "b"}]


# --- over a real loopback socket ------------------------------------------

def _serve_once(sock, received, done, mod):
    conn, _ = sock.accept()
    receiver = mod.FramedSocketReceiver()
    try:
        while not done.is_set():
            try:
                data = conn.recv(8192)
            except OSError:
                break  # client went away; not a failure of the receiver
            if not data:
                break
            for command in receiver.feed(data):
                received.append(command)
                conn.sendall((json.dumps({"status": "ok"}) + "\n").encode())
    finally:
        conn.close()


def test_real_loopback_coalesced_and_fragmented(mod):
    """End-to-end over 127.0.0.1: a burst then a deliberately split command."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    received, done = [], threading.Event()
    thread = threading.Thread(
        target=_serve_once, args=(server, received, done, mod), daemon=True)
    thread.start()

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    try:
        # three commands, one write — the coalescing case
        burst = "".join(json.dumps({"type": "burst", "i": i}) for i in range(3))
        client.sendall(burst.encode())
        # one command, two writes — the fragmentation case
        raw = json.dumps({"type": "split"}).encode()
        client.sendall(raw[:5])
        client.sendall(raw[5:])

        deadline = threading.Event()
        for _ in range(200):
            if len(received) >= 4:
                break
            deadline.wait(0.02)
    finally:
        done.set()
        client.close()
        server.close()

    assert [c["type"] for c in received] == ["burst", "burst", "burst", "split"]
    assert [c["i"] for c in received[:3]] == [0, 1, 2]
