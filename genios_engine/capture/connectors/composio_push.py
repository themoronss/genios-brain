"""One Composio trigger delivery → whose it is, which source it belongs to, and its object.

Two envelopes reach `/webhooks/composio`:

* **V3** (Composio's current format): `{id, type: "composio.trigger.message", metadata: {user_id,
  connected_account_id, trigger_slug, …}, data: {…}}`. Identity lives in `metadata`, not at the top
  level, so the route's old top-level `user_id` read found no connection for any real delivery.
  Other `composio.*` types (an expired connection, …) are events, not objects to ingest.
* **Legacy**: `{user_id, data: {…}}` — what the parity tests and older projects send.

The source matters because `composio_user_id` is the ORG's label in Composio (every connection
of one org carries the same one), so matching on it alone could hand a Gmail push to that org's
Calendar connection. V3 names the trigger, and the trigger names the toolkit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

#: Composio toolkit (the trigger slug's prefix, lowercased) → our `source_type`. Only sources
#: with a webhook parser (`dispatch._PARSER_IMPORTS`) are listed; anything else is skipped rather
#: than guessed onto a connection it does not belong to.
TOOLKIT_SOURCE = {"gmail": "gmail", "googlecalendar": "gcal", "hubspot": "hubspot",
                  "notion": "notion", "googledrive": "gdrive"}


@dataclass(frozen=True)
class ComposioPush:
    user_id: str | None
    #: None when the envelope does not say (legacy) — the caller then matches on the label alone.
    source_type: str | None
    data: Any
    #: Set when the delivery is acknowledged but carries nothing to ingest.
    skip_reason: str | None = None


def parse_push(payload: Mapping[str, Any]) -> ComposioPush:
    kind = payload.get("type")
    if isinstance(kind, str) and kind.startswith("composio.") \
            and isinstance(payload.get("metadata"), Mapping):
        if kind != "composio.trigger.message":
            return ComposioPush(None, None, None, skip_reason=f"not a trigger event ({kind})")
        meta = payload["metadata"]
        slug = str(meta.get("trigger_slug") or "")
        toolkit = slug.split("_", 1)[0].lower() if "_" in slug else ""
        source = TOOLKIT_SOURCE.get(toolkit)
        if source is None:
            return ComposioPush(None, None, None,
                                skip_reason=f"no ingest lane for trigger {slug or '(none)'}")
        return ComposioPush(user_id=meta.get("user_id") or None, source_type=source,
                            data=payload.get("data") or {})
    data = payload.get("data") or payload.get("payload") or payload
    user_id = (payload.get("user_id")
               or (data.get("user_id") if isinstance(data, Mapping) else None)
               or payload.get("connected_account_id"))
    return ComposioPush(user_id=user_id, source_type=None, data=data)


def pick_connection(connections: Iterable, push: ComposioPush):
    """The active connection this push belongs to, or None.

    Both kinds of connection resolve by the same exact match. A workspace connection's Composio
    user id is the org id; a SEAT connection's is `{org_id}:{seat_id}` (migration 0138,
    `contracts.connection.composio_user_id_for`), so a push for one member's Gmail can never land
    on the org's connection or on another member's — the ids are distinct strings, compared whole.
    """
    mine = [c for c in connections if c.composio_user_id == push.user_id]
    if push.source_type is not None:
        mine = [c for c in mine if c.source_type == push.source_type]
    return mine[0] if mine else None
