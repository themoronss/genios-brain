"""Discrepancies a seat may see, and how a person settles one — SCREEN_INTEL_P4 §3.3.

WHO MAY SEE ONE. A discrepancy is two claims about one field. Either side can have come from a
seat's PRIVATE evidence: a work fact (`deal.status`) learned from seat 1's screen is written at
org level (`fact_visibility.is_work_fact`) and so CAN raise a discrepancy — whose challenger names
seat 1's private event. A viewer sees a discrepancy only when it may read BOTH sides:
`fact_visibility.viewer_may_read` on the challenger's source event and on the held fact version.
An API key (no seat) reads only discrepancies with no private side. Every surface that lists
discrepancies — `GET /v1/discrepancies`, `GET /context/discrepancies`, the verify post-pass's
recipient choice — goes through `visible()` here.

SETTLING ONE (`resolve`), in one transaction, audit-logged after commit:
  accept → the challenger value becomes a HUMAN-CONFIRMED fact (source `human_confirmed`, at the
           higher of the two ranks, now) — which supersedes the held version, and `write_fact`'s
           own supersede path closes the row; it is then stamped `resolution='accept'`;
  keep   → status `kept`; `GraphStore.write_discrepancy` will not raise the same challenger value
           (by digest) for 30 days;
  snooze → status `snoozed` until `snoozed_until`; the verify pass reopens it when it wakes.
PostgreSQL only (the columns are migration 0153's).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.fact_visibility import viewer_may_read
from genios_engine.reason.moments.common import iso, parse_ts, value_of

ACTIONS = ("accept", "keep", "snooze")
STATUSES = ("open", "snoozed", "kept", "resolved")
_OUT_STATUS = {"accept": "resolved", "keep": "kept", "snooze": "snoozed"}
HUMAN_SOURCE = "human_confirmed"
MAX_SNOOZE_DAYS = 90
#: The listing reads at most this many rows before the seat filter (open rows are one per field).
SCAN_CAP = 2000

#: One row per discrepancy with everything the seat filter and the public shape need.
_SELECT = (
    "select d.id, d.org_id, d.subject_node_id, d.field, d.held, d.challenger, d.status, "
    "d.created_at, d.updated_at, d.snoozed_until, d.resolution, d.challenger_digest, "
    "n.display_name, n.node_type, "
    "se.visibility_scope as ch_scope, se.visibility_principals as ch_principals, "
    "se.source as ch_event_source, "
    "hf.visibility_scope as h_scope, hf.visibility_principals as h_principals, "
    "hf.occurred_at as h_at, hf.value_type as h_value_type, hr.source as h_source "
    "from discrepancies d "
    "left join graph_nodes n on n.org_id = d.org_id and n.node_id = d.subject_node_id "
    " and n.valid_to is null "
    "left join source_events se on se.org_id = d.org_id and se.event_id = d.challenger->>'event_id' "
    "left join graph_facts hf on hf.org_id = d.org_id "
    " and hf.fact_version_id = d.held->>'fact_version_id' "
    "left join lateral (select r.source from graph_source_refs r "
    " where r.fact_version_id = hf.fact_version_id order by r.created_at limit 1) hr on true "
    "where d.org_id = :o ")

#: "Open" as a reader means it: an expired snooze is open again even before the pass reopens it.
OPEN_CLAUSE = ("(d.status = 'open' or (d.status = 'snoozed' and d.snoozed_until is not null "
               "and d.snoozed_until <= now()))")


def _j(v) -> dict:
    v = value_of(v)
    return v if isinstance(v, dict) else {}


def visible(row, viewer: str | None) -> bool:
    """May `viewer` (a seat's lower-cased email, or None for no seat) see this discrepancy?"""
    return (viewer_may_read(row.ch_scope, row.ch_principals, viewer)
            and viewer_may_read(row.h_scope, row.h_principals, viewer))


def private_principals(row) -> frozenset[str] | None:
    """The addresses allowed to see a discrepancy with a private side, or None when neither side
    is private (the whole org may)."""
    sets = [frozenset(str(p).strip().lower() for p in (pr or ()) if str(p or "").strip())
            for scope, pr in ((row.ch_scope, row.ch_principals), (row.h_scope, row.h_principals))
            if scope == "private"]
    if not sets:
        return None
    out = sets[0]
    for s in sets[1:]:
        out &= s
    return out


def rows(conn, *, org_id: str, status: str | None = "open", extra: str = "",
         params: dict | None = None, cap: int = SCAN_CAP) -> list:
    clause = ""
    if status == "open":
        clause = "and " + OPEN_CLAUSE + " "
    elif status == "snoozed":
        clause = "and d.status = 'snoozed' and (d.snoozed_until is null or d.snoozed_until > now()) "
    elif status in STATUSES:
        clause = "and d.status = :status "
    return conn.execute(text(
        _SELECT + clause + extra + " order by d.created_at desc, d.id desc limit :cap"),
        {"o": org_id, "status": status, "cap": cap, **(params or {})}).fetchall()


def list_for_viewer(conn, *, org_id: str, viewer: str | None, status: str = "open",
                    limit: int = 50) -> list:
    out = []
    for r in rows(conn, org_id=org_id, status=status):
        if visible(r, viewer):
            out.append(r)
            if len(out) >= limit:
                break
    return out


def get_for_viewer(conn, *, org_id: str, discrepancy_id: str, viewer: str | None):
    found = rows(conn, org_id=org_id, status=None, extra="and d.id = :id ",
                 params={"id": discrepancy_id}, cap=1)
    return found[0] if found and visible(found[0], viewer) else None


def _at(raw) -> str | None:
    return iso(parse_ts(raw)) if raw is not None else None


def public(r) -> dict:
    """§3.3: `{id, subject, field, held:{value,source,at}, challenger:{value,source,at},
    created_at}` — plus additive `subject_node_id`, `subject_type`, `status`, ranks."""
    held, ch = _j(r.held), _j(r.challenger)
    return {"id": r.id, "subject": r.display_name or r.subject_node_id,
            "subject_node_id": r.subject_node_id, "subject_type": r.node_type,
            "field": r.field, "status": r.status,
            "held": {"value": held.get("value"), "source": r.h_source or held.get("source"),
                     "at": iso(r.h_at) if r.h_at else _at(held.get("occurred_at")),
                     "rank": held.get("rank")},
            "challenger": {"value": ch.get("value"),
                           "source": ch.get("source") or r.ch_event_source,
                           "at": _at(ch.get("occurred_at")), "rank": ch.get("rank")},
            "created_at": iso(r.created_at)}


class ResolveError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def resolve(engine, graph_store, *, org_id: str, discrepancy_id: str, viewer: str | None,
            seat_id: str, action: str, snooze_days: int = 7,
            now: datetime | None = None) -> dict:
    """Settle one discrepancy the viewer may see. Raises ResolveError (404 not found / not
    visible, 409 already settled, 422 bad action)."""
    if action not in ACTIONS:
        raise ResolveError(422, "INVALID_ACTION", f"action must be one of {', '.join(ACTIONS)}")
    now = now or datetime.now(timezone.utc)
    days = max(1, min(int(snooze_days or 7), MAX_SNOOZE_DAYS))
    with engine.begin() as c:
        locked = c.execute(text("select status from discrepancies where org_id = :o and id = :id "
                                "for update"), {"o": org_id, "id": discrepancy_id}).first()
        r = get_for_viewer(c, org_id=org_id, discrepancy_id=discrepancy_id, viewer=viewer)
        if locked is None or r is None:
            raise ResolveError(404, "DISCREPANCY_NOT_FOUND", "No such discrepancy for this seat.")
        woke = r.status == "snoozed" and r.snoozed_until is not None and r.snoozed_until <= now
        if r.status != "open" and not woke and not (r.status == "snoozed" and action != "snooze"):
            raise ResolveError(409, "DISCREPANCY_SETTLED", f"This discrepancy is {r.status}.")
        held, ch = _j(r.held), _j(r.challenger)
        if action == "accept":
            rank = max(int(held.get("rank") or 0), int(ch.get("rank") or 0), 2)
            graph_store.write_fact(
                c, org_id=org_id, subject_node_id=r.subject_node_id, field=r.field,
                value=ch.get("value"), value_type=r.h_value_type or "string", confidence=1.0,
                occurred_at=now, event_id=f"human:{discrepancy_id}", source=HUMAN_SOURCE,
                authority_rank=rank,
                evidence={"human_confirmed": True, "discrepancy_id": discrepancy_id,
                          "confirmed_by": viewer or seat_id,
                          "challenger_event_id": ch.get("event_id")})
            graph_store.bump_version(c, org_id)
            c.execute(text(
                "update discrepancies set status = 'resolved', resolution = 'accept', "
                "resolved_at = :now, resolved_by = :by, updated_at = :now "
                "where org_id = :o and id = :id"),
                {"o": org_id, "id": discrepancy_id, "now": now, "by": seat_id})
        elif action == "keep":
            from genios_engine.context.graph_store import challenger_digest
            c.execute(text(
                "update discrepancies set status = 'kept', resolution = 'keep', "
                "resolved_at = :now, resolved_by = :by, updated_at = :now, "
                "challenger_digest = :d where org_id = :o and id = :id"),
                {"o": org_id, "id": discrepancy_id, "now": now, "by": seat_id,
                 "d": challenger_digest(ch.get("value"))})
        else:
            c.execute(text(
                "update discrepancies set status = 'snoozed', resolution = 'snooze', "
                "snoozed_until = :until, resolved_by = :by, updated_at = :now "
                "where org_id = :o and id = :id"),
                {"o": org_id, "id": discrepancy_id, "now": now, "by": seat_id,
                 "until": now + timedelta(days=days)})
    from genios_engine.platform import audit
    audit.record(org_id, "discrepancy_resolved", actor_type="user", actor_id=seat_id,
                 target_type="discrepancy", target_id=discrepancy_id,
                 metadata={"action": action, "field": r.field,
                           "subject_node_id": r.subject_node_id,
                           "snooze_days": days if action == "snooze" else None})
    out = {"id": discrepancy_id, "status": _OUT_STATUS[action]}
    if action == "snooze":
        out["snoozed_until"] = iso(now + timedelta(days=days))
    return out


def render_value(v) -> str:
    v = value_of(v)
    if isinstance(v, dict):
        if "minor_units" in v:
            try:
                return f"{v.get('currency') or ''} {int(v['minor_units']) / 100:,.2f}".strip()
            except (TypeError, ValueError):
                pass
        return json.dumps(v, default=str)[:80]
    return str(v)[:80] if v is not None else "—"


__all__ = ["ACTIONS", "HUMAN_SOURCE", "OPEN_CLAUSE", "ResolveError", "get_for_viewer",
           "list_for_viewer", "private_principals", "public", "render_value", "resolve", "rows",
           "visible"]
