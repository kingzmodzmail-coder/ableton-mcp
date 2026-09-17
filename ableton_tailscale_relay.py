"""TCP relay: a chosen interface -> Ableton localhost:9877.

The Remote Script binds 127.0.0.1 on purpose: its command surface is
unauthenticated and includes importing arbitrary absolute paths, saving the
set and loading browser items. Anything that can reach the port owns the DAW.

So this relay does not widen that reach by default. Pass the address to listen
on explicitly — normally this machine's Tailscale IP, which keeps exposure
inside the tailnet:

    python ableton_tailscale_relay.py 100.x.y.z

Binding every interface is a separate, deliberate act:

    python ableton_tailscale_relay.py 0.0.0.0 19877 --allow-public
"""
import argparse
import socket
import threading

TARGET = ("127.0.0.1", 9877)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 19877

# Addresses that accept connections from anywhere the host is routable.
# "*" is deliberately absent: it is not a bindable address, so accepting it
# here would only trade a clear argument error for an OSError at bind.
_WILDCARD = {"0.0.0.0", "::"}


def listening_socket(host, port):
    """Bind host:port, letting the address choose the family.

    A Tailscale address can be either v4 (100.x.y.z) or v6 (fd7a:...), and "::"
    is a v6 wildcard — hardcoding AF_INET made those fail at bind.
    """
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM,
                               flags=socket.AI_PASSIVE)
    family, socktype, proto, _canon, address = infos[0]
    srv = socket.socket(family, socktype, proto)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(address)
    return srv


def pipe(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try: src.shutdown(socket.SHUT_RD)
        except Exception: pass
        try: dst.shutdown(socket.SHUT_WR)
        except Exception: pass

def handle(client):
    try:
        upstream = socket.create_connection(TARGET, timeout=5)
    except Exception as e:
        print(f"upstream_fail: {e}", flush=True)
        client.close()
        return
    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("host", nargs="?", default=DEFAULT_HOST,
                        help="address to listen on, e.g. this host's Tailscale IP "
                             "(default: %(default)s)")
    parser.add_argument("port", nargs="?", type=int, default=DEFAULT_PORT,
                        help="port to listen on (default: %(default)s)")
    parser.add_argument("--allow-public", action="store_true",
                        help="permit binding a wildcard address (0.0.0.0 / ::), "
                             "which exposes Ableton to every reachable network")
    args = parser.parse_args()

    if args.host in _WILDCARD and not args.allow_public:
        parser.error(
            f"refusing to bind {args.host}: that exposes Ableton's unauthenticated "
            "control socket to every reachable network. Pass this machine's "
            "Tailscale IP instead, or add --allow-public if you really mean it."
        )

    try:
        srv = listening_socket(args.host, args.port)
    except OSError as e:
        parser.error("cannot listen on %s:%s (%s)" % (args.host, args.port, e))
    srv.listen(32)
    print(f"relay {args.host}:{args.port} -> {TARGET[0]}:{TARGET[1]}", flush=True)
    if args.host in _WILDCARD:
        print("WARNING: listening on every interface; Ableton is reachable by "
              "anyone who can route to this host.", flush=True)
    while True:
        c, addr = srv.accept()
        print(f"accept {addr}", flush=True)
        threading.Thread(target=handle, args=(c,), daemon=True).start()

if __name__ == "__main__":
    main()
