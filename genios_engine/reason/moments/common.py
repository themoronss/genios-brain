"""Shared pieces of the hot-lane reads: who may read what, and how graph values are parsed.

SEAT-VISIBLE ONLY (P2 §3.4, `context/fact_visibility`). Two things can be private to a seat:
  * a FACT — `graph_facts.visibility_scope='private'`, readable only by its principals;
  * the EVIDENCE of a touch — an observation whose source event is private (a teammate's screen
    session). "Last touch 2 d ago" learned only from someone else's screen is theirs, not ours.
The SQL fragments below are the one spelling of both rules for the slice and every moment unit.
The viewer is the seat's email, lower-cased (what `visibility_principals` holds).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

#: `graph_facts f` readable by `:viewer` (the asking seat's own overlay included).
VISIBLE_FACT_SQL = ("(f.visibility_scope is distinct from 'private' or cast(:viewer as text) = "
                    "any(coalesce(f.visibility_principals, cast('{}' as text[]))))")
#: `source_events se` (left-joined; NULL = no event, allowed) readable by `:viewer`.
VISIBLE_EVENT_SQL = ("(se.event_id is null or se.visibility_scope is distinct from 'private' "
                     "or cast(:viewer as text) = any(coalesce(se.visibility_principals, "
                     "cast('{}' as text[]))))")


def viewer_key(email: str | None) -> str | None:
    v = str(email or "").strip().lower()
    return v or None


def value_of(raw):
    """A `graph_facts.value` (jsonb) → a Python value; a JSON string that was double-encoded is
    decoded once more."""
    if isinstance(raw, str):
        s = raw.strip()
        if s[:1] in ('"', "{", "["):
            try:
                return json.loads(s)
            except ValueError:
                return raw
    return raw


def text_of(raw) -> str | None:
    v = value_of(raw)
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return None
    s = str(v).strip()
    return s or None


def parse_ts(raw) -> datetime | None:
    """ISO string / datetime / gcal `{"dateTime"|"date": …}` → aware UTC datetime, else None."""
    v = value_of(raw)
    if isinstance(v, dict):
        v = v.get("dateTime") or v.get("date_time") or v.get("date")
    if isinstance(v, datetime):
        dt = v
    elif isinstance(v, date):
        dt = datetime(v.year, v.month, v.day)
    elif isinstance(v, str) and v.strip():
        s = v.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            try:
                d = date.fromisoformat(s[:10])
            except ValueError:
                return None
            dt = datetime(d.year, d.month, d.day)
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def fact_rows_to_map(rows) -> dict[str, dict[str, tuple]]:
    """(subject_node_id, field, value, valid_from) rows, ordered overlay-first then newest-first →
    node → field → (value, valid_from). The first row per (node, field) wins."""
    out: dict[str, dict[str, tuple]] = {}
    for r in rows:
        out.setdefault(r.subject_node_id, {}).setdefault(r.field, (r.value, aware(r.valid_from)))
    return out


__all__ = ["VISIBLE_EVENT_SQL", "VISIBLE_FACT_SQL", "aware", "fact_rows_to_map", "iso",
           "parse_ts", "text_of", "value_of", "viewer_key"]
