"""Regression tests for the Tailscale relay's listen address.

The relay forwards to Ableton's unauthenticated control socket, so which
address it binds is a security decision, not a convenience one.

Two defects this pins:

* the default was 0.0.0.0, exposing that socket to every network the host is
  routable from — undoing the loopback bind on the Live side.
* the socket was hardcoded AF_INET while the wildcard set accepted "::", so
  asking for IPv6 passed the guard and then raised OSError at bind. Tailscale
  hands out v6 addresses (fd7a:...), so this was a live failure, not just a
  cosmetic "::" case.

socket.getaddrinfo and socket.socket are stubbed, so nothing depends on
whether this host has IPv6 configured and nothing is actually bound.
"""
import socket

import pytest

import ableton_tailscale_relay as relay


class FakeSocket:
    """Records the family it was built with and what it was asked to bind."""

    def __init__(self, family, socktype, proto):
        self.family = family
        self.socktype = socktype
        self.proto = proto
        self.bound = None
        self.options = []
        self.backlog = None

    def setsockopt(self, level, option, value):
        self.options.append((level, option, value))

    def bind(self, address):
        self.bound = address

    def listen(self, backlog):
        self.backlog = backlog


@pytest.fixture
def fake_net(monkeypatch):
    """Stub resolution and socket creation; return the sockets that got built."""
    built = []

    def _install(family, address):
        def _getaddrinfo(host, port, **kwargs):
            assert kwargs.get("flags") == socket.AI_PASSIVE
            return [(family, socket.SOCK_STREAM, 6, "", address)]

        def _socket(fam, socktype, proto):
            sock = FakeSocket(fam, socktype, proto)
            built.append(sock)
            return sock

        monkeypatch.setattr(relay.socket, "getaddrinfo", _getaddrinfo)
        monkeypatch.setattr(relay.socket, "socket", _socket)
        return built
    return _install


# ---------------------------------------------------------------- defaults

def test_default_listen_address_is_loopback():
    """The whole point: a relay must not widen reach unless asked."""
    assert relay.DEFAULT_HOST == "127.0.0.1"


def test_target_is_ableton_on_loopback():
    assert relay.TARGET == ("127.0.0.1", 9877)


def test_wildcard_set_holds_only_bindable_addresses():
    """"*" is not an address; keeping it here traded a clear argument error
    for an OSError at bind."""
    assert relay._WILDCARD == {"0.0.0.0", "::"}


# ------------------------------------------------------- family selection

def test_ipv4_address_builds_an_ipv4_socket(fake_net):
    built = fake_net(socket.AF_INET, ("127.0.0.1", 19877))
    relay.listening_socket("127.0.0.1", 19877)
    assert built[0].family == socket.AF_INET
    assert built[0].bound == ("127.0.0.1", 19877)


def test_ipv6_address_builds_an_ipv6_socket(fake_net):
    """Regression: AF_INET was hardcoded, so this raised at bind."""
    built = fake_net(socket.AF_INET6, ("::", 19877, 0, 0))
    relay.listening_socket("::", 19877)
    assert built[0].family == socket.AF_INET6
    assert built[0].bound == ("::", 19877, 0, 0)


def test_tailscale_ipv6_address_builds_an_ipv6_socket(fake_net):
    """The address shape Tailscale actually hands out."""
    built = fake_net(socket.AF_INET6, ("fd7a:115c:a1e0::1", 19877, 0, 0))
    relay.listening_socket("fd7a:115c:a1e0::1", 19877)
    assert built[0].family == socket.AF_INET6


def test_address_reuse_is_set(fake_net):
    built = fake_net(socket.AF_INET, ("127.0.0.1", 19877))
    relay.listening_socket("127.0.0.1", 19877)
    assert (socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) in built[0].options


def test_unresolvable_address_raises_oserror_not_something_exotic():
    """main() catches OSError to turn this into a clean CLI error."""
    with pytest.raises(OSError):
        relay.listening_socket("*", 19877)


# --------------------------------------------------------- the CLI guard

def _run_cli(monkeypatch, argv):
    """Drive main() through argparse and return its exit code."""
    import sys as _sys
    monkeypatch.setattr(_sys, "argv", ["ableton_tailscale_relay.py"] + argv)
    with pytest.raises(SystemExit) as excinfo:
        relay.main()
    return excinfo.value.code


@pytest.mark.parametrize("host", ["0.0.0.0", "::"])
def test_wildcard_is_refused_without_the_explicit_flag(monkeypatch, capsys, host):
    assert _run_cli(monkeypatch, [host]) == 2
    assert "refusing to bind" in capsys.readouterr().err


def test_the_refusal_names_the_way_out(monkeypatch, capsys):
    _run_cli(monkeypatch, ["0.0.0.0"])
    stderr = capsys.readouterr().err
    assert "--allow-public" in stderr
    assert "Tailscale" in stderr


def test_unbindable_address_fails_cleanly_not_with_a_traceback(monkeypatch, capsys):
    """"*" passes the guard (it is not a wildcard we recognise) and must then
    surface as an argparse error, not an unhandled OSError."""
    assert _run_cli(monkeypatch, ["*", "19877", "--allow-public"]) == 2
    assert "cannot listen on" in capsys.readouterr().err


def test_allow_public_lets_a_wildcard_through(monkeypatch, capsys, fake_net):
    """The escape hatch has to actually work, and has to warn."""
    built = fake_net(socket.AF_INET, ("0.0.0.0", 19877))
    accepted = {}

    def _stop_after_bind(*args, **kwargs):
        accepted["reached"] = True
        raise KeyboardInterrupt

    monkeypatch.setattr(FakeSocket, "accept", _stop_after_bind, raising=False)
    import sys as _sys
    monkeypatch.setattr(_sys, "argv",
                        ["ableton_tailscale_relay.py", "0.0.0.0", "19877", "--allow-public"])

    with pytest.raises(KeyboardInterrupt):
        relay.main()

    assert built[0].bound == ("0.0.0.0", 19877)
    assert built[0].backlog == 32
    assert "WARNING" in capsys.readouterr().out
