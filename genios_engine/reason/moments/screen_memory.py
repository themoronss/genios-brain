"""Screen memory writer — design step S3 (docs/plans/SCREEN_INTEL_SYSTEM_DESIGN.html, phase 1).

The one judge (screen_insight v4) already read the screen and wrote its items — asks, promises,
deadlines, risks, next steps, each with who / due / a grounded quote — as `screen_followups` rows.
This module turns those rows into graph memory WITHOUT another AI read:

    when       the thread's screen content is promoted (screen_promoter, at most once an hour per
               thread); its seat-private source event is the observation's source, so the graph's
               visibility rules treat the item like any other private screen evidence;
    on whom    the person the item is about, ONLY when that person already exists in the graph
               (an email in `who` → its email alias; else the one person holding that exact name
               alias). A screen never CREATES a person: nodes are listed org-wide, and a private
               WhatsApp contact must not appear to the rest of the org. Unknown people stay in the
               seat's private follow-ups (and on the observation's evidence) with no subject; no
               one named → the manager's own node (their seat email's person);
    what       one observation per item, kind `screen.<item kind>`, evidence = the model's note,
               who, due and quote (never more screen text);
    once       `graph_written_at` marks the row, so a later promotion never writes it twice.

No AI call, no credit charge.
"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import text

from genios_engine.platform.logging import get_logger
from genios_engine.reason.moments.common import aware, iso

_log = get_logger("genios.moments.screen_memory")

KIND_PREFIX = "screen."
CONFIDENCE = 0.8
SOURCE = "screen_insight"
BATCH = 50
#: "Deepak (Rentomojo)", "Deepak, Rentomojo", "Deepak - Rentomojo", "Deepak from Rentomojo"
_COMPANY_SPLIT = re.compile(r"\s*(?:\(|,|\s-\s|\s–\s|\sfrom\s|\sat\s|@\s)", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def name_part(who: str | None) -> str | None:
    """The person's name out of the model's `who` ("Deepak (Rentomojo)" → "Deepak")."""
    s = " ".join((who or "").split())
    if not s:
        return None
    head = _COMPANY_SPLIT.split(s, maxsplit=1)[0].strip(" )")
    return head or None


def _person(conn, *, org_id: str, who: str) -> str | None:
    """The EXISTING person `who` names, or None (never creates one — see the module note)."""
    from genios_engine.context.identity import ALIAS_EMAIL, resolve_alias, resolve_person_name
    from genios_engine.platform.identity import norm_email
    m = _EMAIL.search(who)
    if m:
        email = norm_email(m.group(0))
        return (resolve_alias(conn, org_id=org_id, alias_type=ALIAS_EMAIL, alias_key=email)
                if email else None)
    return resolve_person_name(conn, org_id=org_id, name=name_part(who))


def write_items(engine, *, org_id: str, seat_id: str, seat_email: str | None,
                thread_key: str | None, event_id: str, now: datetime) -> int:
    """Write this thread's not-yet-written items as observations sourced by `event_id`.
    Returns how many were written. Never raises into the promoter: a failure is logged and the
    rows stay unwritten for the next promotion."""
    if not thread_key or not event_id:
        return 0
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.context.identity import ALIAS_EMAIL, resolve_alias
    from genios_engine.platform.identity import norm_email
    store = GraphStore(engine=engine)
    try:
        with engine.begin() as c:
            rows = c.execute(text(
                "select id, kind, text, who, due_at, quote, created_at from screen_followups "
                "where org_id = :o and seat_id = :s and thread_key = :t "
                "and graph_written_at is null order by created_at, id limit :n "
                "for update skip locked"),
                {"o": org_id, "s": seat_id, "t": thread_key, "n": BATCH}).fetchall()
            if not rows:
                return 0
            me_key = norm_email(seat_email)
            me = (resolve_alias(c, org_id=org_id, alias_type=ALIAS_EMAIL, alias_key=me_key)
                  if me_key else None)
            for r in rows:
                node = _person(c, org_id=org_id, who=r.who) if r.who else me
                store.write_observation(
                    c, org_id=org_id, subject_node_id=node, kind=KIND_PREFIX + r.kind,
                    confidence=CONFIDENCE, occurred_at=aware(r.created_at), event_id=event_id,
                    evidence={"followup_id": r.id, "text": r.text, "who": r.who,
                              "due_at": iso(aware(r.due_at)), "quote": r.quote},
                    source=SOURCE)
                c.execute(text(
                    "update screen_followups set graph_written_at = :now, subject_node_id = :n "
                    "where id = :i"), {"now": now, "n": node, "i": r.id})
            return len(rows)
    except Exception:      # noqa: BLE001 — memory is retried on the next promotion
        _log.exception("screen memory: items not written org=%s seat=%s", org_id, seat_id)
        return 0


__all__ = ["KIND_PREFIX", "name_part", "write_items"]
