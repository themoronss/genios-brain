"""Deriving the source ACL from a raw object — deterministic, per source shape.

Every rule here is answerable from the object itself: a recipient list, an attendee
list, a Drive permission array. **None of them requires knowing anything about the
company**, which is the test for whether a rule belongs in Layer 1 at all.

Where a source cannot tell us, the answer is `org` — not `public`, and not a guess at
something narrower. `org` is the tenant boundary that already exists, so defaulting to it
neither leaks beyond what the connection itself implies nor hides evidence from the people
who own it. A connector that CAN do better states it explicitly in `raw["acl"]`.
"""
from __future__ import annotations

from typing import Any

from genios_engine.capture.connectors.base import RawObject
from genios_engine.contracts.visibility import (ORG, PARTICIPANTS, PRIVATE, PUBLIC,
                                                SCOPES, Visibility)


def _emails(*values: Any) -> list[str]:
    """Flatten anything a connector might hand us into lowercased unique emails."""
    out: list[str] = []
    for v in values:
        if v is None:
            continue
        items = v if isinstance(v, (list, tuple, set)) else [v]
        for item in items:
            if isinstance(item, dict):                       # {"email": ...} / Drive permission
                item = item.get("email") or item.get("emailAddress")
            if isinstance(item, str) and "@" in item:
                e = item.strip().lower()
                if e not in out:
                    out.append(e)
    return out


def _explicit(raw: dict) -> Visibility | None:
    """A connector that knows the real ACL says so in raw['acl'] and wins outright."""
    acl = raw.get("acl")
    if not isinstance(acl, dict):
        return None
    scope = str(acl.get("scope") or ORG)
    if scope not in SCOPES:
        return None
    return Visibility(scope=scope, principals=_emails(acl.get("principals")),
                      derived_from=str(acl.get("derived_from") or "connector:explicit"))


def visibility_for(raw: RawObject) -> Visibility:
    """One raw object → the audience it arrived with.

    Mail and calendar are the two sources where a wrong default does real damage — both
    routinely carry material only two or three people have seen — so both resolve to the
    exact participant list. Everything else states its reasoning in `derived_from`.
    """
    r = raw.raw or {}
    explicit = _explicit(r)
    if explicit is not None:
        return explicit

    # Mail: sender + To + Cc. Bcc is invisible to us by definition; an attachment
    # inherits its parent message's audience (same dict keys, copied by the connector).
    if raw.object_type in ("email_message", "email_attachment"):
        people = _emails(raw.actor_email, r.get("to"), r.get("cc"))
        if people:
            return Visibility(scope=PARTICIPANTS, principals=people,
                              derived_from="mail:sender+to+cc")
        return Visibility(scope=PRIVATE, principals=_emails(raw.actor_email),
                          derived_from="mail:no-recipients")

    # Calendar: organiser + attendees. A solo event with no attendee list is the
    # owner's own calendar block, not something the whole org booked.
    if raw.object_type == "calendar_event":
        people = _emails(raw.actor_email, r.get("attendees"))
        if len(people) > 1:
            return Visibility(scope=PARTICIPANTS, principals=people,
                              derived_from="calendar:organizer+attendees")
        return Visibility(scope=PRIVATE, principals=people,
                          derived_from="calendar:solo-event")

    # Drive: the file's own permission array when the connector fetched it. `anyone`
    # (link sharing) is genuinely public; a named list is participants; an unshared file
    # belongs to its owner alone.
    if raw.source in ("gdrive", "drive", "google_drive"):
        perms = r.get("permissions")
        if isinstance(perms, list) and perms:
            if any(isinstance(p, dict) and p.get("type") == "anyone" for p in perms):
                return Visibility(scope=PUBLIC, derived_from="drive:anyone-with-link")
            if any(isinstance(p, dict) and p.get("type") == "domain" for p in perms):
                return Visibility(scope=ORG, derived_from="drive:domain-shared")
            people = _emails(perms, raw.actor_email)
            if people:
                return Visibility(scope=PARTICIPANTS, principals=people,
                                  derived_from="drive:permissions")
        if r.get("shared") is False:
            return Visibility(scope=PRIVATE, principals=_emails(raw.actor_email),
                              derived_from="drive:unshared")

    # Everything else — Notion workspace pages, client DB rows, uploads, typed canon,
    # agent outcomes — is org-wide by the nature of the door it came through.
    return Visibility(scope=ORG, derived_from=f"default:{raw.source}")
