"""Shared validation vocabulary for cross-layer contract types.

``contracts/reasoning.py`` predates this module and carries private copies of the same
helpers.  It is deliberately left untouched: its bytes are covered by decision hashes that
already exist in audit rows, and a refactor that moved them would be a change with no
behavioural upside and a replay-shaped downside.  Every contract written after it imports
from here, so the vocabulary has exactly one public home going forward.

Every helper fails closed.  A value that cannot be proven well-formed raises rather than
being coerced, because a contract that quietly repairs its input is a contract that lets a
malformed execution reach a human — and by then the repair is invisible.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from genios_engine.platform.canonical import canonicalize, semantic_hash

#: Identifiers travel into SQL, URLs, log lines and content addresses.  The character class is
#: deliberately narrow so none of those four contexts ever needs to escape one.
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$")
HASH64 = re.compile(r"^[0-9a-f]{64}$")


def require_text(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def require_identifier(value: Any, label: str) -> str:
    result = require_text(value, label)
    if not IDENTIFIER.fullmatch(result):
        raise ValueError(f"{label} contains unsupported characters")
    return result


def require_aware(value: Any, label: str) -> datetime:
    """Timezone-aware, normalised to UTC.

    A naive datetime is rejected rather than assumed-UTC: the whole layer reasons about
    deadlines and escalation days, and a silent eight-hour offset would express itself as a
    reminder that fires on the wrong day rather than as an error anybody could see.
    """
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def require_bp(value: Any, label: str) -> int:
    """Integer basis points, 0..10000 — the only numeric currency in a semantic artifact."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be integer basis points")
    if not 0 <= value <= 10_000:
        raise ValueError(f"{label} must be between 0 and 10000")
    return value


def require_ordinal(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def require_non_negative(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def require_hash64(value: Any, label: str) -> str:
    result = require_text(value, label)
    if not HASH64.fullmatch(result):
        raise ValueError(f"{label} must be a lowercase SHA-256 hash")
    return result


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{label} must be boolean")
    return value


def freeze(value: Any) -> Any:
    """Deep-freeze a semantic value, validating it can be canonicalised at all.

    ``canonicalize`` runs first so unsupported input (a float, a non-string mapping key, an
    arbitrary object) is refused at construction time rather than at hashing time, when the
    artifact is already halfway into a database row.
    """
    canonicalize(value)
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((freeze(item) for item in value), key=semantic_hash))
    return value


def freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return freeze(value or {})


def require_strings(values: Any, label: str = "list value") -> tuple[str, ...]:
    return tuple(require_text(value, label) for value in (values or ()))


def require_sorted_unique(values: Any, label: str = "list value") -> tuple[str, ...]:
    return tuple(sorted(set(require_strings(values, label))))


def require_enum(value: Any, enum_cls: type, label: str):
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError as exc:                       # pragma: no cover - message clarity only
        raise ValueError(f"{label} is not a valid {enum_cls.__name__}: {value!r}") from exc


__all__ = ["HASH64", "IDENTIFIER", "freeze", "freeze_mapping", "require_aware", "require_bool",
           "require_bp", "require_enum", "require_hash64", "require_identifier",
           "require_non_negative", "require_ordinal", "require_sorted_unique", "require_strings",
           "require_text"]
