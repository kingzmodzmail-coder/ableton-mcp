"""EvAIx <-> AbletonMCP TCP bridge (localhost:9877).

Usage:
  python ableton_cmd.py get_session_info
  python ableton_cmd.py get_script_info
  python ableton_cmd.py set_tempo --params "{\"tempo\": 128}"
  python ableton_cmd.py create_midi_track --params "{\"index\": -1}"
"""
from __future__ import annotations

import argparse
import json
import socket
import sys

HOST = "127.0.0.1"
PORT = 9877


def recv_json(sock: socket.socket, timeout: float = 15.0) -> dict:
    sock.settimeout(timeout)
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            if not chunks:
                raise ConnectionError("Ableton closed the connection with no data")
            break
        chunks.append(chunk)
        raw = b"".join(chunks)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            continue
    raise ValueError("Incomplete JSON from Ableton: " + b"".join(chunks)[:200].decode("utf-8", "replace"))


def send_command(command_type: str, params: dict | None = None, timeout: float = 15.0) -> dict:
    payload = {"type": command_type, "params": params or {}}
    with socket.create_connection((HOST, PORT), timeout=5.0) as sock:
        sock.sendall(json.dumps(payload).encode("utf-8"))
        response = recv_json(sock, timeout=timeout)
    if response.get("status") == "error":
        raise RuntimeError(response.get("message", "Unknown Ableton error"))
    return response.get("result", response)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send one command to AbletonMCP")
    parser.add_argument("command", help="e.g. get_session_info, set_tempo, create_midi_track")
    parser.add_argument("--params", default="{}", help="JSON object of params")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()
    try:
        params = json.loads(args.params)
        if not isinstance(params, dict):
            raise ValueError("--params must be a JSON object")
        result = send_command(args.command, params, timeout=args.timeout)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
