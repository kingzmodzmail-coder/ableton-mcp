"""Persistent consent state for dataset recording.

The env-var opt-in (``ABLETON_MCP_ENABLE_DATASET``) is invisible to anyone who
does not read the docs, so in practice nobody was ever asked. This module lets
the question be asked in the chat itself, once, and remembers the answer.

Three states, and the distinction matters:

    UNKNOWN  — never answered. Recording is OFF until an explicit grant.
    GRANTED  — the user said yes, in their own words. Recording is ON.
    DENIED   — the user said no. Recording is OFF, permanently, and the question
               is never asked again.

Missing, corrupt, dismissed or unknown consent never authorizes collection.
This grant concerns training contribution only, not telemetry, local project
memory or private audio processing.

``ABLETON_MCP_DISABLE_DATASET`` still overrides everything, and the env-var
opt-in still works for headless/CI use where no one can answer a chat prompt.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("ableton-mcp-dataset")

UNKNOWN = "unknown"
GRANTED = "granted"
DENIED = "denied"

# Consent is per-install, not per-project: the same person answering once should
# not be re-asked because they opened a different Live set.
_STATE_DIR = Path(
    os.environ.get("ABLETON_MCP_STATE_DIR", "")
    or (Path.home() / ".ableton-mcp")
)
_STATE_FILE = _STATE_DIR / "consent.json"

_lock = threading.Lock()
_persist_failed = False


def _read_state() -> dict[str, Any]:
    """Load persisted consent, tolerating a missing or corrupt file.

    Deliberately re-reads the file every time and keeps no cache: other MCP
    processes can revoke consent, and a process-lifetime cached grant must
    never decide whether queued data may leave the machine.
    """
    try:
        with open(_STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("consent state is not an object")
        return data
    except FileNotFoundError:
        return {}
    except Exception as e:
        # A damaged file must not wedge the server into a state where it can
        # neither record nor re-ask. Treat it as never-asked.
        logger.debug("Consent state unreadable (%s); treating as unasked", e)
        return {}


def _write_state(state: dict[str, Any]) -> None:
    global _persist_failed
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=_STATE_DIR, delete=False) as f:
            tmp = Path(f.name)
            json.dump(state, f, indent=2)
        os.replace(tmp, _STATE_FILE)
        _persist_failed = False
    except Exception as e:
        _persist_failed = True
        logger.warning("Could not persist dataset consent: %s", e)
        raise OSError('Consent could not be persisted; collection is disabled in this process') from e
    finally:
        if 'tmp' in locals():
            tmp.unlink(missing_ok=True)


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def consent_state() -> str:
    """Return UNKNOWN / GRANTED / DENIED, honouring env overrides.

    The kill switch wins outright. The env opt-in counts as a grant so headless
    and CI setups keep working without anyone to answer a prompt.

    UNKNOWN is reported as-is rather than collapsed into GRANTED: the prompting
    logic needs to tell "never answered" from "said yes" so it knows to still
    ask. Whether UNKNOWN records is a separate question, answered by
    ``recording_allowed``.
    """
    if _persist_failed or _env_flag("ABLETON_MCP_DISABLE_DATASET"):
        return DENIED
    with _lock:
        state = _read_state().get("state", UNKNOWN)
    # An explicit withdrawal overrides a stale headless opt-in.
    if state == DENIED:
        return DENIED
    if _env_flag("ABLETON_MCP_ENABLE_DATASET"):
        return GRANTED
    return state if isinstance(state, str) and state in {UNKNOWN, GRANTED, DENIED} else UNKNOWN


def recording_allowed() -> bool:
    """Only an explicit training contribution grant authorizes collection."""
    return consent_state() == GRANTED


def record_consent(granted: bool, quote: str | None = None) -> str:
    """Persist the user's answer. ``quote`` is what they actually said.

    Storing the raw phrasing matters: consent relayed through a model is only
    as good as the model's faithfulness, so keep the evidence for later audit.
    """
    if type(granted) is not bool:
        raise ValueError('Consent requires an explicit boolean')
    state = GRANTED if granted else DENIED
    with _lock:
        payload = dict(_read_state())
        payload.update({
            "state": state,
            "answered_at": time.time(),
            "user_said": (quote or "").strip()[:500] or None,
        })
        _write_state(payload)
    logger.info("Dataset consent recorded: %s", state)
    return state


def needs_prompt() -> bool:
    """True when the user has never been asked."""
    return consent_state() == UNKNOWN


def mark_prompted() -> None:
    """Note that the question has been surfaced, so it is asked once per session."""
    with _lock:
        payload = dict(_read_state())
        payload["last_prompted_at"] = time.time()
        _write_state(payload)


CONSENT_NOTICE = (
    "\n\n---\n"
    "[Ask the user this now, before continuing. Do not answer it yourself, and "
    "do not assume — relay their reply verbatim.]\n\n"
    "**Do you want to contribute this session to the open Ableton MCP training "
    "dataset?**\n\n"
    "Training collection is off until you agree. If you agree, your prompts, MIDI "
    "notes, track and clip names, and device settings are uploaded and may be "
    "published as part of an open dataset used to train music-production "
    "models. Email addresses and file paths are stripped first.\n\n"
    "Reply **no** to leave collection off, or **yes** to contribute. You will "
    "only be asked once; you can change your mind later by saying so.\n"
    "---"
)


ELICIT_MESSAGE = (
    "Contribute this session to the open Ableton MCP training dataset?\n\n"
    "Collection is off until you agree. If you agree, your prompts, MIDI "
    "notes, track and clip names, and device settings are uploaded and may be "
    "published as part of an open dataset used to train music-production "
    "models. Email addresses and file paths are stripped first.\n\n"
    "Decline to leave collection off. You are asked once, and can change your mind "
    "later."
)


async def try_elicit_consent(ctx: Any) -> str | None:
    """Ask for consent via a real client dialog. Returns a state, or None.

    Preferred over the text prompt because the *client* renders it and the user
    answers directly — the model cannot fabricate an answer it never received.

    Returns None when elicitation is unavailable (older mcp, or a client that
    does not implement it), which means the caller should fall back to
    appending the text notice. A user who cancels or declines the dialog is a
    real answer, not a fallback.
    """
    if ctx is None or not needs_prompt():
        return None
    try:
        from pydantic import BaseModel, Field

        class DatasetConsent(BaseModel):
            contribute: bool = Field(
                description=(
                    "Yes, contribute my sessions to the open dataset"
                ),
            )

        result = await ctx.elicit(message=ELICIT_MESSAGE, schema=DatasetConsent)
    except Exception as e:
        # Unsupported client, older mcp, or transport error — text fallback
        logger.debug("Elicitation unavailable (%s); falling back to text", e)
        return None

    action = getattr(result, "action", None)
    if action == "accept":
        data = getattr(result, "data", None)
        agreed = bool(getattr(data, "contribute", False))
        return record_consent(agreed, quote="(via client dialog)")
    if action == "decline":
        return record_consent(False, quote="(declined in client dialog)")
    # "cancel" — dismissed without answering. Left UNKNOWN so the question can
    # be asked again in a later session. Collection remains off.
    logger.debug("Consent dialog dismissed without an answer — collection remains off")
    mark_prompted()
    return UNKNOWN


def maybe_consent_notice() -> str:
    """Return the consent question to append to a tool result, or "".

    Empty once the user has answered, or if they were already asked this
    session — the prompt should read as a question, not a nag.
    """
    if not needs_prompt():
        return ""
    with _lock:
        last = _read_state().get("last_prompted_at") or 0
    # Re-ask on a later session if it went unanswered, but never twice in a row
    if time.time() - last < 3600:
        return ""
    mark_prompted()
    return CONSENT_NOTICE


def reset_for_tests() -> None:
    global _persist_failed
    with _lock:
        _persist_failed = False
