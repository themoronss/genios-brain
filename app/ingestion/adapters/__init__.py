"""
Pull adapters — Genios actively fetches from external systems on a schedule.

Each adapter implements:
    fetch(credentials: dict, since_iso: str) -> list[dict]

Returned events follow the canonical /v1/ingest/{email,call,sms} payload
shape so the same insert helpers can be reused.
"""

from __future__ import annotations

from typing import Optional

# Lightweight registry — providers identified by metadata.provider value.
# Each entry is a dict of operation -> callable, e.g.
#   {"fetch_email": fn, "mark_read": fn, "fetch_call": fn, "fetch_sms": fn}
_REGISTRY: dict[str, dict] = {}


def register(provider: str, ops: dict) -> None:
    _REGISTRY[provider] = ops


def get(provider: str) -> Optional[dict]:
    return _REGISTRY.get(provider)


def known_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


# Eager-import the adapters so registration runs at import time.
# Keeping the imports here means callers just `from app.ingestion import adapters`
# and the registry is populated.
from . import inkbox as _inkbox  # noqa: E402,F401
from . import imap_pull as _imap  # noqa: E402,F401
from . import gmail as _gmail  # noqa: E402,F401
from . import calendar as _calendar  # noqa: E402,F401
