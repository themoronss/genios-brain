from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    """Prefixed opaque id, e.g. evt_3f2a...  (24 hex chars)."""
    return f"{prefix}_{uuid.uuid4().hex[:24]}"
