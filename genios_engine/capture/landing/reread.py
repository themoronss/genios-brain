"""A re-read of an already-landed Gmail message must not re-land its attachments.

Gmail hands out a fresh `attachmentId` on every read of a message, and an attachment's
`source_object_id` is `{message_id}::{attachmentId}` — `parked/refetch_policy.py` parses that id to
download the file again, so it cannot change. Every second read of the same message therefore
produced attachment events whose dedup keys had never been seen: one resumed sync on the design
partner's org re-landed 100 attachments, and another tenant holds 393 extra copies of 474.

The message itself is immutable and its own dedup key is stable, so it is what gets asked. When the
parent message has already landed, its attachments landed with it (a file we could not read landed
as a parked stub, which the refetch ladder owns), and this read's copies are dropped before capture.
A message landing for the first time has no row yet — the check runs before any object of the page
is captured — so its attachments always go through.

STEP-08 · A MESSAGE THE OLD GATE DELETED COMES BACK, AND ITS KEY IS FREE. The old gate deleted a junk
message while its readable attachment landed as an event of its own (`connectors/composio.
attachment_overrides_junk`); the re-sync frees the deleted message's key (`landing/resync`), and the
parent check alone would land that attachment a second time. So the ledger is asked one more thing —
has an attachment of this message landed KEPT? — and the copy is dropped when it has. It lands when the
earlier copy was deleted with its message, or never landed: that is the content the re-sync is for.
Known limit: the answer is per message. A message whose attachments the old gate SPLIT — one kept, one
deleted — gets none of the deleted ones back (`scripts/resync_deleted_mail.py` counts such messages).

THE LADDER'S OWN COPY IS NOT A RE-READ. The re-read ladder (`landing/unread`) rebuilds a KEPT row nothing
has read under its own key, set aside for the purpose, and marks it `rereading`. Dropped here because its
message had landed, it was restored, retried and given up — an attachment the ladder held was never read.
It always goes through.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from genios_engine.contracts.source_event import compute_dedup_key

_log = logging.getLogger(__name__)

#: A child object type and the parent type whose re-read carries it back in.
_PARENT_TYPE = {"email_attachment": "email_message"}


def drop_reread_attachments(objects: Sequence, *, org_id: str, repo) -> tuple[list, int]:
    """(objects still to capture, how many were dropped as re-reads). Never raises: a parent lookup
    that fails keeps the attachment, because a duplicate is recoverable and a lost file is not."""
    kept: list = []
    dropped = 0
    landed: dict[str, bool] = {}
    for raw in objects:
        parent_type = _PARENT_TYPE.get(getattr(raw, "object_type", "") or "")
        parent_id = getattr(raw, "parent_object_id", None)
        # A VERSIONED object is a new version, not a re-read: its own key already changes with the
        # content, and dropping it would hide the edit. Gmail attachments carry no version. A copy
        # the re-read ladder rebuilt (`rereading`) is that ladder reading what it holds.
        if (parent_type and parent_id and not getattr(raw, "content_version", None)
                and not getattr(raw, "rereading", None)):
            key = compute_dedup_key(raw.source, parent_type, parent_id)
            if key not in landed:
                try:
                    landed[key] = bool(repo.exists(org_id, key)) or bool(
                        repo.kept_child_exists(org_id, raw.source, raw.object_type, parent_id))
                except Exception:      # noqa: BLE001 — see the docstring
                    _log.warning("parent lookup failed org=%s parent=%s; keeping its attachment",
                                 org_id, parent_id, exc_info=True)
                    landed[key] = False
            if landed[key]:
                dropped += 1
                continue
        kept.append(raw)
    return kept, dropped
