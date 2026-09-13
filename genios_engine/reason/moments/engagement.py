"""Who else is talking to this company — P-13 duplicate outreach + the slice's `other_seats`
(SCREEN_INTEL_P4 §3.4).

A TOUCH is an ORG-VISIBLE source event attributed to a seat — its own connection
(`connections.seat_id`) or, on an org-wide connection, the seat whose address sent it — that wrote
an observation, fact or edge about a company or about a person who `works_at` one. Two things are
never a touch here, by construction of the one query below:
  * a screen event (`source='screen_session'`) — what a seat saw on its screen is its own;
  * any PRIVATE event (`visibility_scope='private'`) — a personal upload, a private connection.
So another seat's screen activity can never show up in `other_seats` nor fire P-13.
Our own company (a seat's email domain) is never a counterparty.

P-13: when a SECOND seat touches a company another seat touched within 7 days, the second seat
gets one server moment naming the first. Deterministic, no LLM, idempotent per episode (the moment
id is derived from seat + company + the others + the episode's first day). Never credit-charged.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.reason.moments.common import aware, iso

TOUCH_DAYS = 7
PASS_ID = "engagement"
CAPABILITY_ID = "moment.duplicate_outreach"
CAPABILITY_VERSION = "1"
TTL_SECONDS = 86400

_TOUCHES = text(
    "with seats as (select seat_id, lower(email) as email from org_seats where org_id = :o "
    " and active and email is not null), "
    "ev as (select se.event_id, se.occurred_at, coalesce(cs.seat_id, ss.seat_id) as seat_id "
    " from source_events se "
    " left join connections c on c.org_id = se.org_id and c.connection_id = se.connection_id "
    " left join seats cs on cs.seat_id = c.seat_id "
    " left join seats ss on ss.email = lower(se.actor->>'email') "
    " where se.org_id = :o and se.occurred_at > :since and se.occurred_at <= :now "
    " and se.source <> 'screen_session' and se.visibility_scope is distinct from 'private'), "
    "refs as (select ev.seat_id, ev.occurred_at, o.subject_node_id as n1, f.subject_node_id as n2, "
    " e.from_node_id as n3, e.to_node_id as n4 "
    " from ev join graph_source_refs r on r.org_id = :o and r.event_id = ev.event_id "
    " left join graph_observations o on o.observation_id = r.observation_id "
    " left join graph_facts f on f.fact_version_id = r.fact_version_id "
    " left join graph_edges e on e.edge_version_id = r.edge_version_id "
    " where ev.seat_id is not null), "
    "nodes as (select refs.seat_id, refs.occurred_at, x.nid from refs "
    " cross join lateral (values (refs.n1), (refs.n2), (refs.n3), (refs.n4)) as x(nid) "
    " where x.nid is not null), "
    "comp as (select n.seat_id, n.occurred_at, g.node_id as company from nodes n "
    " join graph_nodes g on g.org_id = :o and g.node_id = n.nid and g.valid_to is null "
    " and g.node_type = 'company' "
    " union all select n.seat_id, n.occurred_at, w.to_node_id from nodes n "
    " join graph_edges w on w.org_id = :o and w.from_node_id = n.nid "
    " and w.edge_type = 'works_at' and w.valid_to is null) "
    "select comp.company, cn.display_name, comp.seat_id, min(comp.occurred_at) as first_at, "
    " max(comp.occurred_at) as last_at "
    "from comp join graph_nodes cn on cn.org_id = :o and cn.node_id = comp.company "
    " and cn.valid_to is null and cn.node_type = 'company' "
    "where lower(coalesce(cn.canonical_key, '')) <> all(cast(:internal as text[])) "
    " and (cast(:ids as text[]) is null or comp.company = any(cast(:ids as text[]))) "
    "group by 1, 2, 3")


def internal_domains(conn, org_id: str) -> list[str]:
    """Our own company's domains: every seat's and the workspace owner's email domain."""
    return sorted({r.d for r in conn.execute(text(
        "select lower(split_part(email, '@', 2)) as d from org_seats where org_id = :o "
        "and email like '%@%' union select lower(split_part(email, '@', 2)) from orgs "
        "where id = :o and email like '%@%'"), {"o": org_id}) if r.d})


def touches(conn, org_id: str, *, now: datetime, company_ids=None,
            days: int = TOUCH_DAYS) -> dict[str, dict]:
    """company → {"name": display name, "seats": {seat_id: (first_at, last_at)}} for org-visible
    touches in the last `days`."""
    if company_ids is not None and not company_ids:
        return {}
    out: dict[str, dict] = {}
    for r in conn.execute(_TOUCHES, {"o": org_id, "now": now, "since": now - timedelta(days=days),
                                     "internal": internal_domains(conn, org_id),
                                     "ids": sorted(company_ids) if company_ids is not None
                                     else None}):
        entry = out.setdefault(r.company, {"name": r.display_name, "seats": {}})
        entry["seats"][r.seat_id] = (aware(r.first_at), aware(r.last_at))
    return out


def seat_names(conn, org_id: str) -> dict[str, str]:
    """seat_id → the person's name: an invited member's `org_members.name`; the workspace owner's
    name lives on `orgs.name` (account settings write it there); else the address's local part."""
    names: dict[str, str] = {}
    for r in conn.execute(text(
            "select s.seat_id, coalesce(nullif(m.name, ''), nullif(o.name, ''), "
            "split_part(s.email, '@', 1), s.seat_id) as name from org_seats s "
            "left join org_members m on m.org_id = s.org_id "
            "and (m.seat_id = s.seat_id or lower(m.email) = lower(s.email)) "
            "left join orgs o on o.id = s.org_id and lower(o.email) = lower(s.email) "
            "where s.org_id = :o order by s.seat_id, (m.seat_id = s.seat_id) desc nulls last"),
            {"o": org_id}):
        names.setdefault(r.seat_id, r.name)
    return names


def other_seats(conn, *, org_id: str, seat_id: str, company_ids, now: datetime
                ) -> dict[str, list[dict]]:
    """company → [{name, since, last_at}] of the OTHER seats that touched it in 7 d (the slice
    strips `last_at`, which it uses only to mark the company changed)."""
    t = touches(conn, org_id, now=now, company_ids=list(company_ids or ()))
    if not t:
        return {}
    names = seat_names(conn, org_id)
    out: dict[str, list[dict]] = {}
    for company, info in t.items():
        rows = [{"name": names.get(s, s), "since": iso(first), "last_at": last}
                for s, (first, last) in sorted(info["seats"].items(), key=lambda kv: kv[1][0])
                if s != seat_id]
        if rows:
            out[company] = rows
    return out


def _episode_id(seat_id: str, company: str, others: list[str], first: datetime) -> str:
    from genios_engine.reason.moments.store import server_moment_id
    blob = json.dumps([company, sorted(others), first.date().isoformat()], separators=(",", ":"))
    return server_moment_id(seat_id, "p13:" + hashlib.sha256(blob.encode()).hexdigest()[:24])


def compose(*, company_name: str | None, company: str, others: list[tuple[str, datetime]],
            now: datetime) -> dict:
    who = [n for n, _ in others]
    named = ", ".join(who[:2]) + (f" +{len(who) - 2}" if len(who) > 2 else "")
    label = company_name or "this company"
    first_name, first_at = others[0]
    days = max(0, (now - first_at).days)
    ago = "today" if days == 0 else ("yesterday" if days == 1 else f"{days} d ago")
    return {"kind": "advice", "priority": "normal", "capability_id": CAPABILITY_ID,
            "capability_version": CAPABILITY_VERSION, "ttl_seconds": TTL_SECONDS,
            "headline": f"{named} also contacted {label} this week"[:300],
            "body": f"{first_name} was in touch with {label} {ago}. Check with them before "
                    f"you reach out.",
            "actions": [],
            "evidence": [{"kind": "engagement", "node_id": company, "seat": n, "since": iso(at)}
                         for n, at in others[:5]]}


def emit_duplicate_outreach(engine, org_id: str, *, now: datetime | None = None) -> int:
    """P-13 for every seat that touched a company after another seat did, within 7 d. Returns
    the number of NEW moments. Skips entirely when no org-visible event arrived since the last
    run (0154 watermark)."""
    from genios_engine.reason.moments import store as M
    from genios_engine.reason.verify.passes import advance, watermark
    now = now or datetime.now(timezone.utc)
    with engine.connect() as c:
        wm = watermark(c, org_id, PASS_ID)
        fresh = c.execute(text(
            "select 1 from source_events where org_id = :o and captured_at > :wm "
            "and source <> 'screen_session' and visibility_scope is distinct from 'private' "
            "limit 1"), {"o": org_id, "wm": wm}).first()
        if fresh is None:
            return 0
        t = touches(c, org_id, now=now)
        names = seat_names(c, org_id)
    new = 0
    for company, info in sorted(t.items()):
        seats = info["seats"]
        if len(seats) < 2:
            continue
        order = sorted(seats.items(), key=lambda kv: (kv[1][0], kv[0]))
        for seat_id, (_first, last) in order[1:]:
            others = [(o, f) for o, (f, _l) in order if o != seat_id and f <= last]
            if not others:
                continue
            mid = _episode_id(seat_id, company, [o for o, _ in others], others[0][1])
            with engine.connect() as c:
                if c.execute(text("select 1 from moments where moment_id = :m"),
                             {"m": mid}).first() is not None:
                    continue
            moment = {"moment_id": mid, **compose(
                company_name=info["name"], company=company,
                others=[(names.get(o, o), f) for o, f in others], now=now)}
            try:
                M.persist(engine, org_id=org_id, seat_id=seat_id, device_id=None,
                          origin="server", moment=moment, subject_ids=[company], now=now)
                new += 1
            except M.MomentConflict:
                continue
    with engine.begin() as c:
        advance(c, org_id, PASS_ID, now)
    return new


__all__ = ["CAPABILITY_ID", "PASS_ID", "TOUCH_DAYS", "compose", "emit_duplicate_outreach",
           "internal_domains", "other_seats", "seat_names", "touches"]
