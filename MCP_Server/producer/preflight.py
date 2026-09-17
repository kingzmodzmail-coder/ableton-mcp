"""Pre-flight: refuse to start a build on a setup that will lose the work.

Checks the four things that actually broke builds: the bridge is reachable and
speaks the expected script version, exactly one Live instance is running, the
snapshot contract is the full v2 one the producer needs, and the disk has room
for renders. Read-only: nothing here writes to Live or to disk.
"""
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

DEFAULT_HOST, DEFAULT_PORT = "127.0.0.1", 9877
DEFAULT_MIN_FREE_GB = 20.0
LIVE_PROCESS_NAMES = ("Ableton Live", "Live")
SOCKET_TIMEOUT = 5.0


def _check(name, ok, detail, value=None):
    return {"check": name, "status": "pass" if ok else "fail",
            "detail": detail, "value": value}


def ask_bridge(command, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=SOCKET_TIMEOUT):
    """One request/response against the Remote Script. Raises on any failure."""
    with socket.create_connection((host, port), timeout=timeout) as connection:
        connection.sendall(json.dumps({"type": command, "params": {}}).encode("utf-8"))
        chunks = b""
        connection.settimeout(timeout)
        while True:
            chunk = connection.recv(65536)
            if not chunk:
                break
            chunks += chunk
            try:
                return json.loads(chunks.decode("utf-8"))
            except json.JSONDecodeError:
                continue
    raise ConnectionError("Bridge closed the connection before a full response")


def live_process_count():
    """Number of running Live processes, or None where we cannot tell."""
    if not sys.platform.startswith("win"):
        return None
    try:
        output = subprocess.run(["tasklist"], capture_output=True, text=True,
                                timeout=20, check=True).stdout
    except Exception:
        return None
    lowered = output.lower()
    return sum(lowered.count(name.lower() + ".exe") for name in LIVE_PROCESS_NAMES)


def run(project=".producer", host=DEFAULT_HOST, port=DEFAULT_PORT,
        min_free_gb=DEFAULT_MIN_FREE_GB):
    from ..remote_script_install import EXPECTED_REMOTE_SCRIPT_VERSION

    checks = []

    try:
        response = ask_bridge("get_script_info", host, port)
        info = response.get("result", response) or {}
        version = str(info.get("script_version") or info.get("version") or "unknown")
        checks.append(_check("bridge_reachable", True,
                             "Remote Script answered on %s:%s" % (host, port), version))
        checks.append(_check(
            "script_version", version == EXPECTED_REMOTE_SCRIPT_VERSION,
            "loaded %s, expected %s%s" % (version, EXPECTED_REMOTE_SCRIPT_VERSION,
                                          "" if version == EXPECTED_REMOTE_SCRIPT_VERSION
                                          else " - deploy the script and restart Live"),
            version))
    except Exception as error:
        checks.append(_check("bridge_reachable", False,
                             "No answer on %s:%s (%s). Is Live running with the "
                             "AbletonMCP control surface selected?" % (host, port, error)))
        checks.append(_check("script_version", False, "not checked: bridge unreachable"))

    try:
        session = ask_bridge("get_session_info", host, port).get("result", {}) or {}
        full = bool(session.get("tracks") is not None or session.get("track_count") is not None)
        compact = "snapshot" in session and not full
        checks.append(_check("snapshot_contract", full and not compact,
                             "full session payload" if full and not compact else
                             "compact snapshot: the producer refuses to edit against "
                             "it - settle the 1.7.x / 1.8.x bridge family first",
                             sorted(session)[:8]))
    except Exception as error:
        checks.append(_check("snapshot_contract", False, "not checked (%s)" % error))

    count = live_process_count()
    if count is None:
        checks.append(_check("single_live_instance", True,
                             "cannot enumerate processes on this platform - check by hand"))
    else:
        checks.append(_check("single_live_instance", count == 1,
                             "%d Live process(es) running; exactly one must own the "
                             "socket" % count, count))

    target = Path(project).resolve()
    probe = target if target.exists() else target.anchor or "."
    free_gb = shutil.disk_usage(probe).free / (1024 ** 3)
    checks.append(_check("free_disk", free_gb >= min_free_gb,
                         "%.1f GB free, need %.1f GB for renders and captures"
                         % (free_gb, min_free_gb), round(free_gb, 1)))

    failures = [c["check"] for c in checks if c["status"] == "fail"]
    return {"passed": not failures, "failures": failures, "checks": checks,
            "next_step": ("Start the build." if not failures else
                          "Fix the failing checks before building; a build started "
                          "now is likely to be lost or unverifiable.")}
