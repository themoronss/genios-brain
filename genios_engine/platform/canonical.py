"""Strict canonical serialization for deterministic Layer 4 artifacts.

Semantic hashes are part of the reasoning contract.  They must not depend on dict insertion order,
locale, timezone, Python hash randomization, host formatting, or ``default=str`` fallbacks.  This
module therefore accepts only explicitly supported values and rejects floats entirely; probabilities,
scores, money and weights belong in integer basis/minor units.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Set
from dataclasses import fields, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

_RESERVED_TAG_KEYS = frozenset({"$decimal", "$datetime", "$date", "$uuid"})


class CanonicalizationError(ValueError):
    """A value cannot participate safely in a semantic hash."""


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CanonicalizationError("semantic datetimes must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonicalize(value: Any) -> Any:
    """Convert a supported value into unambiguous JSON primitives.

    Sets are sorted by their own canonical JSON representation. Lists/tuples preserve order because
    order is often semantic (reasoner plan, ranked candidates, play steps). Mapping keys must be
    strings; silently stringifying a key could create collisions.
    """
    semantic = getattr(value, "to_semantic_dict", None)
    if callable(semantic):
        return canonicalize(semantic())
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: canonicalize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return canonicalize(value.value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        raise CanonicalizationError(
            "floats are forbidden in semantic artifacts; use integer basis points or Decimal")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CanonicalizationError("Decimal values must be finite")
        return {"$decimal": format(value.normalize(), "f")}
    if isinstance(value, datetime):
        return {"$datetime": _utc(value)}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, UUID):
        return {"$uuid": str(value)}
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError("semantic mapping keys must be strings")
            if key in _RESERVED_TAG_KEYS:
                raise CanonicalizationError(
                    f"semantic mapping key {key!r} is reserved for canonical scalar encoding")
            out[key] = canonicalize(item)
        return out
    if isinstance(value, Set) and not isinstance(value, (str, bytes, bytearray)):
        items = [canonicalize(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(
            item, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    raise CanonicalizationError(f"unsupported semantic value: {type(value).__name__}")


def decanonicalize(value: Any) -> Any:
    """Reverse the scalar tagging of ``canonicalize`` so a stored artifact can be rehydrated.

    Only the four reserved tags are decoded, and only when they are the sole key of a mapping —
    the same shape ``canonicalize`` emits.  Everything else is returned as-is, so this is safe to
    run over arbitrary stored JSON.

    Deliberately not a full inverse: lists come back as lists, not tuples, and mappings as plain
    dicts.  The contract types re-impose their own shapes and validation in ``__post_init__``,
    which is the only place that should be deciding what a well-formed artifact looks like.
    """
    if isinstance(value, Mapping):
        if len(value) == 1:
            (key, item), = value.items()
            if key == "$datetime" and isinstance(item, str):
                return datetime.fromisoformat(item.replace("Z", "+00:00"))
            if key == "$date" and isinstance(item, str):
                return date.fromisoformat(item)
            if key == "$decimal" and isinstance(item, str):
                return Decimal(item)
            if key == "$uuid" and isinstance(item, str):
                return UUID(item)
        return {key: decanonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [decanonicalize(item) for item in value]
    return value


def canonical_dumps(value: Any) -> str:
    return json.dumps(canonicalize(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def semantic_hash(value: Any) -> str:
    return hashlib.sha256(canonical_dumps(value).encode("utf-8")).hexdigest()


def stable_id(prefix: str, value: Any) -> str:
    clean = str(prefix).strip().lower()
    if not clean or not clean.replace("_", "").isalnum():
        raise ValueError("stable id prefix must be alphanumeric/underscore")
    return f"{clean}_{semantic_hash(value)}"
