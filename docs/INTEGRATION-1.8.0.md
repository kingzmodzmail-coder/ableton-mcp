# Integrating the 1.8.0 protocol branch into main

Status: **not done.** Attempted 18 Sep 2026, backed out cleanly. This is the
map for whoever picks it up.

## The situation

Two lines of work diverged from `8731a47`:

* **`main`** (11 commits) — the mix ear, QC gate, reference profiles, pipeline
  stages, pre-flight, `save_set` (script 1.7.1), the dataset/telemetry privacy
  fixes and 242 passing tests.
* **`wip/protocol-framing-1.8.0`** (`c3c1171`, on top of `19fc6f1`) — newline-framed
  bridge protocol, handshake, `MCP_Server/doctor.py` (454 lines),
  `MCP_Server/protocol.py`, `MCP_Server/cli.py`, `scripts/sync_remote_script.py`,
  a CI workflow, and four new test modules.

Neither contains the other. `git diff main wip/protocol-framing-1.8.0` reads
`+2,196 / -71,149` — **merging that branch into main would delete the ear, the
pipeline, pre-flight and a dozen test files.** Never merge in that direction.

## What a cherry-pick of c3c1171 onto main actually hits

Nine content conflicts plus one modify/delete:

| File | Why it conflicts |
|---|---|
| `AbletonMCP_Remote_Script/__init__.py` | 1.8.0 reframes the socket protocol; main changed the same handlers for `save_set` and browser fixes |
| `MCP_Server/bundled_ableton_remote_script/AbletonMCP_init.py` | same change, second copy |
| `MCP_Server/server.py` | 1.8.0 routes through `protocol.py`; main exposes `save_set` |
| `MCP_Server/telemetry.py` | both branches fixed the log leak, differently |
| `MCP_Server/dataset/consent.py` | 1.8.0 adds the consent gate; main rewrote the same block |
| `MCP_Server/dataset/recorder.py` | both scrub paths, differently |
| `MCP_Server/remote_script_install.py` | one-line version bump on both sides |
| `pyproject.toml` | extras and version differ |
| `uv.lock` | regenerate, never hand-merge |
| `tests/test_remote_script_bridge.py` | modify/delete — main deleted it, 1.8.0 changed it |

The Remote Script conflicts are the dangerous ones: getting them wrong either
breaks the bridge (Live stops answering) or re-opens a privacy leak that main
already closed. They need someone with Live open to test against, not a blind
three-way merge.

## Recommended order

1. Branch from `main`, never from 1.8.0.
2. Take the **purely additive** files first, one commit, and run the suite after
   each: `MCP_Server/protocol.py`, `MCP_Server/doctor.py`, `MCP_Server/cli.py`,
   `scripts/sync_remote_script.py`, `docs/bridge-contracts.md`,
   `docs/release-readiness.md`, `MANIFEST.in`, `.github/workflows/tests.yml`.
   Expect `doctor.py` to need small edits where it assumes the 1.8.0 server.
3. Then the protocol reframing, **with Live running**: port 1.8.0's newline
   framing into main's Remote Script by hand, keeping main's `save_set` and
   browser handlers, and bump the script version once both copies match.
   `scripts/sync_remote_script.py` exists precisely so the two copies cannot
   drift again — wire it into the commit hook at the same time.
4. Re-generate `uv.lock` with `uv lock` rather than resolving it.
5. Port the four new test modules last; they encode the 1.8.0 contract, so they
   should fail until step 3 is genuinely finished. That is the signal, not noise.

## Do not

* Merge `wip/protocol-framing-1.8.0` into `main`.
* Resolve the Remote Script conflicts without a running Live to test against.
* Force-push either branch. `backup/pre-main-switch-20260918` and
  `backup/session-work-4a9f4e0` exist as safety nets; leave them alone.
