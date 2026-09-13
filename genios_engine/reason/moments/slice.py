"""The seat's graph slice — `GET /v1/seats/me/slice?since=<version>` (P3 §2.1, plan §6.3).

WHAT IS IN IT (seat-visible only). Starting from the seat's own person node (its email alias):
  * people   — its direct edge neighbours, plus the people on the threads and meetings it is on,
               with a readable touch (or a new edge) in the last 90 days;
  * companies— those people's employers (`works_at`) and companies it touches directly; deal
               status/stage from the company's deal node;
  * meetings — meetings it attends starting in the next 14 days (cancelled ones excluded);
  * busy     — those meetings as merged time blocks;
  * commitments — open ones its node owns (`owner: "seat"`) and open ones its people own
               (`owner: "counterparty"`, plus the additive `owner_node_id`).
Facts pass `common.VISIBLE_FACT_SQL` and touches `VISIBLE_EVENT_SQL`: another seat's private
fact or private touch never enters this seat's slice.

VERSION = epoch milliseconds, monotonic per seat (migration 0149). The bump
(`platform/realtime.bump_slice_versions`) runs inside every `GraphStore.bump_version` — the org's
graph-version bump that every L2 / structured / upload / knowledge write already performs in its
own transaction. It bumps the seats that hold a live device and announces `slice.delta`. That is
the cheapest CORRECT hook: no slice-affecting write is missed; the cost is over-notifying seats
whose slice did not change, whose delta is then empty. Documented trade-off, not a silent gap.

DELTA. `since` names an instant; people/companies whose own facts, aliases, touches, loops or
connecting edges changed after `since - DELTA_MARGIN` are sent (the margin absorbs a writer whose
transaction started before, and committed after, the bump the device last saw). Meetings, busy and
commitments are small and time-windowed, so every response carries their complete current set
(upsert them; a meeting entering the 14-day window needs no write). `removed` lists retired nodes
and meetings/commitments that closed or were cancelled since. An unknown, future, or > 7-day-old
`since`, or a seat with no version row yet, gets `full: true`.
"""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.identity import norm_email, person_name_key
from genios_engine.reason.moments.common import (VISIBLE_EVENT_SQL, VISIBLE_FACT_SQL, aware,
                                                 iso, parse_ts, text_of, viewer_key)

SCHEMA_VERSION = 1
TOUCH_DAYS = 90
MEETING_DAYS = 14
DELTA_MARGIN = timedelta(minutes=15)
MAX_DELTA_AGE = timedelta(days=7)
SIZE_CAP_GZ = 2 * 1024 * 1024
PEOPLE_MAX = 5000
HUB_TYPES = ("thread", "meeting")
_FIELDS = ("person.title", "company.name", "deal.status", "deal.stage", "commitment.text",
           "commitment.due_at", "commitment.status", "commitment.owed_to", "meeting.title",
           "meeting.start_at", "meeting.end_at", "meeting.status")


def version_instant(version: int) -> datetime:
    return datetime.fromtimestamp(int(version) / 1000.0, tz=timezone.utc)


_VERSION = text(
    "with ins as (insert into seat_slice_versions (org_id, seat_id, version, updated_at) "
    "values (:o, :s, cast(extract(epoch from clock_timestamp()) * 1000 as bigint), now()) "
    "on conflict (org_id, seat_id) do nothing returning version, true as created) "
    "select version, created from ins union all "
    "select version, false from seat_slice_versions where org_id = :o and seat_id = :s limit 1")

# "Touched by the seat" has TWO roots. (1) Edges of the seat's own person node. (2) The seat's OWN
# events — its screen sessions (`screen:<seat_id>`) and its own mailbox connections — and every
# node those events wrote an observation, fact or edge about (`graph_source_refs`, indexed by
# event). A screen thread links the counterparty to a THREAD, never to the seat's node, so without
# root (2) a person known only from the seat's screen was missing from its slice. Root (2) is
# per-seat by construction: another seat's events never seed this slice.
_GRAPH = text(
    "with me as (select node_id from graph_aliases where org_id = :o and alias_type = 'email' "
    " and alias_key = :email), "
    "ev as (select se.event_id from source_events se where se.org_id = :o "
    " and se.captured_at > :cut and (se.connection_id = :screen or se.connection_id in "
    " (select c.connection_id from connections c where c.org_id = :o and c.seat_id = :s))), "
    "refs as (select r.observation_id, r.fact_version_id, r.edge_version_id "
    " from graph_source_refs r join ev on r.org_id = :o and r.event_id = ev.event_id), "
    "own as (select distinct x.nid from ("
    " select o.subject_node_id as nid from refs join graph_observations o "
    " on o.observation_id = refs.observation_id "
    " union all select f.subject_node_id from refs join graph_facts f "
    " on f.fact_version_id = refs.fact_version_id "
    " union all select e.from_node_id from refs join graph_edges e "
    " on e.edge_version_id = refs.edge_version_id "
    " union all select e.to_node_id from refs join graph_edges e "
    " on e.edge_version_id = refs.edge_version_id) x where x.nid is not null), "
    "l1 as (select e.to_node_id as nid, e.edge_type, e.valid_from from graph_edges e "
    " join me on e.from_node_id = me.node_id where e.org_id = :o and e.valid_to is null "
    " union all select e.from_node_id, e.edge_type, e.valid_from from graph_edges e "
    " join me on e.to_node_id = me.node_id where e.org_id = :o and e.valid_to is null "
    " union all select own.nid, 'own_event', cast(null as timestamptz) from own), "
    "hubs as (select distinct l1.nid from l1 join graph_nodes n on n.org_id = :o "
    " and n.node_id = l1.nid and n.valid_to is null and n.node_type = any(:hubs)), "
    "l2 as (select e.to_node_id as nid, h.nid as via, e.edge_type, e.valid_from from graph_edges e "
    " join hubs h on e.from_node_id = h.nid where e.org_id = :o and e.valid_to is null "
    " union all select e.from_node_id, h.nid, e.edge_type, e.valid_from from graph_edges e "
    " join hubs h on e.to_node_id = h.nid where e.org_id = :o and e.valid_to is null) "
    "select x.nid as node_id, x.via, x.edge_type, x.valid_from, n.node_type, n.display_name "
    "from (select nid, cast(null as text) as via, edge_type, valid_from from l1 "
    " union all select nid, via, edge_type, valid_from from l2) x "
    "join graph_nodes n on n.org_id = :o and n.node_id = x.nid and n.valid_to is null "
    "where x.nid not in (select node_id from me) limit 50000")


def _out_edges(conn, org_id: str, people: list[str]):
    """works_at (employer) and owns (their commitments) from the slice's people."""
    if not people:
        return []
    return conn.execute(text(
        "select e.from_node_id, e.to_node_id, e.edge_type, e.valid_from, n.node_type, "
        "n.display_name from graph_edges e join graph_nodes n on n.org_id = e.org_id "
        "and n.node_id = e.to_node_id and n.valid_to is null "
        "where e.org_id = :o and e.from_node_id = any(:ids) "
        "and e.edge_type = any(array['works_at', 'owns']) and e.valid_to is null"),
        {"o": org_id, "ids": people}).fetchall()


def _deals(conn, org_id: str, companies: list[str]):
    if not companies:
        return []
    return conn.execute(text(
        "select x.company, x.deal, x.valid_from from ("
        " select e.to_node_id as company, e.from_node_id as deal, e.valid_from from graph_edges e "
        " where e.org_id = :o and e.to_node_id = any(:ids) and e.valid_to is null "
        " union all select e.from_node_id, e.to_node_id, e.valid_from from graph_edges e "
        " where e.org_id = :o and e.from_node_id = any(:ids) and e.valid_to is null) x "
        "join graph_nodes d on d.org_id = :o and d.node_id = x.deal and d.valid_to is null "
        "and d.node_type = 'deal'"), {"o": org_id, "ids": companies}).fetchall()


def _merge_busy(blocks: list[tuple[datetime, datetime]]) -> list[dict]:
    out: list[list[datetime]] = []
    for s, e in sorted(blocks):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [{"start_at": iso(s), "end_at": iso(e)} for s, e in out]


def _alias_out(alias_type: str, key: str) -> str:
    if alias_type == "linkedin_url":
        return "li:" + key
    return key


def ensure_version(conn, org_id: str, seat_id: str) -> tuple[int, bool]:
    r = conn.execute(_VERSION, {"o": org_id, "s": seat_id}).first()
    return int(r.version), bool(r.created)


def build(engine, *, org_id: str, seat_id: str, email: str | None, since: int | None = None,
          now: datetime | None = None) -> dict:
    """The slice document (§2.1). ~9 statements on one connection."""
    now = now or datetime.now(timezone.utc)
    viewer = viewer_key(email)
    with engine.connect() as c:
        version, created = ensure_version(c, org_id, seat_id)
        c.commit()
        full = (since is None or created or since <= 0 or since > version
                or version_instant(since) < now - MAX_DELTA_AGE)
        threshold = None if full else version_instant(since) - DELTA_MARGIN
        doc = _build(c, org_id=org_id, seat_id=seat_id, email=norm_email(email) or viewer,
                     viewer=viewer, now=now, threshold=threshold)
    doc.update({"schema_version": SCHEMA_VERSION, "version": version, "full": full,
                "generated_at": iso(now)})
    return _fit(doc)


def _build(c, *, org_id: str, seat_id: str, email: str | None, viewer: str | None,
           now: datetime, threshold: datetime | None) -> dict:
    empty = {"people": [], "companies": [], "meetings": [], "busy": [], "commitments": [],
             "removed": []}
    if not email:
        return empty
    from genios_engine.platform.capture_policy import screen_connection_id
    rows = c.execute(_GRAPH, {"o": org_id, "email": email, "hubs": list(HUB_TYPES),
                              "s": seat_id, "screen": screen_connection_id(seat_id),
                              "cut": now - timedelta(days=TOUCH_DAYS)}).fetchall()
    changed: dict[str, datetime] = {}

    def touch(nid: str, at) -> None:
        at = aware(at)
        if at is not None and (nid not in changed or at > changed[nid]):
            changed[nid] = at

    nodes: dict[str, tuple[str, str | None]] = {}
    people: set[str] = set()
    direct_edge_at: dict[str, datetime] = {}
    meetings: set[str] = set()
    my_commitments: set[str] = set()
    attendees: dict[str, set[str]] = {}
    for r in rows:
        nodes[r.node_id] = (r.node_type, r.display_name)
        touch(r.node_id, r.valid_from)
    # Second pass: a hub's type must be known before its members are classified, whatever order
    # the `union all` returned the rows in (attendees used to vanish when a meeting came later).
    for r in rows:
        if r.via is None:
            if r.node_type == "person":
                people.add(r.node_id)
                prev = direct_edge_at.get(r.node_id)
                va = aware(r.valid_from)
                if va is not None and (prev is None or va > prev):
                    direct_edge_at[r.node_id] = va
            elif r.node_type == "meeting":
                meetings.add(r.node_id)
            elif r.node_type == "commitment" and r.edge_type == "owns":
                my_commitments.add(r.node_id)
        elif r.node_type == "person":
            people.add(r.node_id)
            if nodes.get(r.via, ("",))[0] == "meeting":
                attendees.setdefault(r.via, set()).add(r.node_id)
    companies: set[str] = {n for n, (t, _) in nodes.items() if t == "company"}
    employer: dict[str, str] = {}
    their_commitments: dict[str, str] = {}
    for r in _out_edges(c, org_id, sorted(people)):
        nodes.setdefault(r.to_node_id, (r.node_type, r.display_name))
        touch(r.to_node_id, r.valid_from)
        if r.edge_type == "works_at" and r.node_type == "company":
            employer.setdefault(r.from_node_id, r.to_node_id)
            companies.add(r.to_node_id)
        elif r.edge_type == "owns" and r.node_type == "commitment":
            their_commitments.setdefault(r.to_node_id, r.from_node_id)
    company_deal: dict[str, str] = {}
    for r in _deals(c, org_id, sorted(companies)):
        company_deal.setdefault(r.company, r.deal)
        nodes.setdefault(r.deal, ("deal", None))
    fact_ids = sorted(people | companies | set(company_deal.values()) | meetings
                      | my_commitments | set(their_commitments))
    facts: dict[str, dict[str, object]] = {}
    for r in c.execute(text(
            "select f.subject_node_id, f.field, f.value, f.valid_from from graph_facts f "
            "where f.org_id = :o and f.subject_node_id = any(:ids) and f.field = any(:fields) "
            "and f.valid_to is null and f.status = 'active' and " + VISIBLE_FACT_SQL + " "
            "order by f.subject_node_id, f.field, (f.visibility_scope = 'private') desc, "
            "f.occurred_at desc nulls last, f.fact_version_id"),
            {"o": org_id, "ids": fact_ids, "fields": list(_FIELDS), "viewer": viewer}):
        facts.setdefault(r.subject_node_id, {}).setdefault(r.field, r.value)
        touch(r.subject_node_id, r.valid_from)
    entity_ids = sorted(people | companies)
    aliases: dict[str, list[str]] = {}
    for r in c.execute(text(
            "select node_id, alias_type, alias_key, created_at from graph_aliases "
            "where org_id = :o and node_id = any(:ids) and alias_type = any(:t) "
            "order by node_id, alias_type, alias_key"),
            {"o": org_id, "ids": entity_ids,
             "t": ["email", "linkedin_url", "domain", "company_name", "person_name"]}):
        aliases.setdefault(r.node_id, []).append(_alias_out(r.alias_type, r.alias_key))
        touch(r.node_id, r.created_at)
    loops: dict[str, int] = {}
    for r in c.execute(text(
            "select subject_node_id, count(*) filter (where status = 'open') as n, "
            "max(greatest(last_seen_at, coalesce(closed_at, last_seen_at))) as at "
            "from open_loops where org_id = :o and subject_node_id = any(:ids) group by 1"),
            {"o": org_id, "ids": sorted(people)}):
        loops[r.subject_node_id] = int(r.n or 0)
        touch(r.subject_node_id, r.at)
    last_touch: dict[str, datetime] = {}
    for r in c.execute(text(
            "select o.subject_node_id, max(o.occurred_at) as at, max(o.created_at) as changed "
            "from graph_observations o left join source_events se on se.org_id = o.org_id "
            "and se.event_id = o.created_by_event_id "
            "where o.org_id = :o and o.subject_node_id = any(:ids) and o.status = 'active' "
            "and o.occurred_at <= :now and o.occurred_at > :cut and " + VISIBLE_EVENT_SQL + " "
            "group by 1"),
            {"o": org_id, "ids": entity_ids, "now": now, "cut": now - timedelta(days=TOUCH_DAYS),
             "viewer": viewer}):
        last_touch[r.subject_node_id] = aware(r.at)
        touch(r.subject_node_id, r.changed)

    cut = now - timedelta(days=TOUCH_DAYS)
    live_people = sorted(
        (p for p in people
         if (last_touch.get(p) is not None) or (direct_edge_at.get(p) or now) >= cut),
        key=lambda p: last_touch.get(p) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True)[:PEOPLE_MAX]

    def is_open(cid: str) -> bool:
        return (text_of(facts.get(cid, {}).get("commitment.status")) or "open").lower() in (
            "open", "pending", "in_progress")

    name_to_person = {person_name_key(nodes[p][1]): p for p in live_people if nodes[p][1]}
    commitments, removed = [], []
    for cid in sorted(my_commitments | set(their_commitments)):
        f = facts.get(cid, {})
        if not is_open(cid):
            if threshold is not None and changed.get(cid) and changed[cid] >= threshold:
                removed.append(cid)
            continue
        if cid in my_commitments:
            owed = text_of(f.get("commitment.owed_to"))
            item = {"node_id": cid, "text": text_of(f.get("commitment.text")) or nodes[cid][1],
                    "due_at": iso(parse_ts(f.get("commitment.due_at"))), "owner": "seat",
                    "beneficiary": name_to_person.get(person_name_key(owed)) if owed else None}
        else:
            item = {"node_id": cid, "text": text_of(f.get("commitment.text")) or nodes[cid][1],
                    "due_at": iso(parse_ts(f.get("commitment.due_at"))),
                    "owner": "counterparty", "owner_node_id": their_commitments[cid],
                    "beneficiary": None}
        commitments.append(item)

    horizon = now + timedelta(days=MEETING_DAYS)
    meeting_out, busy = [], []
    for mid in sorted(meetings):
        f = facts.get(mid, {})
        start, end = parse_ts(f.get("meeting.start_at")), parse_ts(f.get("meeting.end_at"))
        status = (text_of(f.get("meeting.status")) or "").lower()
        if status == "cancelled":
            if threshold is not None and changed.get(mid) and changed[mid] >= threshold:
                removed.append(mid)
            continue
        if start is None:
            continue
        end = end or start + timedelta(minutes=30)
        if end <= now or start > horizon:
            continue
        meeting_out.append({"node_id": mid,
                            "title": text_of(f.get("meeting.title")) or nodes[mid][1],
                            "start_at": iso(start), "end_at": iso(end),
                            "attendees": sorted(attendees.get(mid, set()))})
        busy.append((start, end))
    meeting_out.sort(key=lambda m: m["start_at"])

    def person_summary(p: str) -> str | None:
        for cid, owner in their_commitments.items():
            if owner == p and is_open(cid):
                return (text_of(facts.get(cid, {}).get("commitment.text")) or "commitment") + \
                    " (theirs)"
        for item in commitments:
            if item["owner"] == "seat" and item.get("beneficiary") == p:
                return f"you owe: {item['text']}"
        if loops.get(p):
            return f"{loops[p]} open loop" + ("s" if loops[p] != 1 else "")
        comp = employer.get(p)
        deal = company_deal.get(comp) if comp else None
        if deal:
            stage = text_of(facts.get(deal, {}).get("deal.stage"))
            status = text_of(facts.get(deal, {}).get("deal.status"))
            if stage or status:
                return f"deal: {stage or status}"
        return None

    def fresh(*ids) -> bool:
        return threshold is None or any(changed.get(i) and changed[i] >= threshold
                                        for i in ids if i)

    people_out = []
    for p in live_people:
        comp = employer.get(p)
        if not fresh(p, comp, company_deal.get(comp) if comp else None,
                     *[cid for cid, o in their_commitments.items() if o == p]):
            continue
        people_out.append({"node_id": p, "name": nodes[p][1], "aliases": aliases.get(p, []),
                           "company": comp, "last_touch_at": iso(last_touch.get(p)),
                           "open_loops": loops.get(p, 0), "summary": person_summary(p),
                           "role": text_of(facts.get(p, {}).get("person.title"))})
    live_companies = {employer[p] for p in live_people if p in employer} | {
        n for n, (t, _) in nodes.items() if t == "company" and n in companies
        and n not in employer.values() and last_touch.get(n)}
    companies_out = []
    for comp in sorted(live_companies):
        deal = company_deal.get(comp)
        if not fresh(comp, deal):
            continue
        staff = [last_touch[p] for p in live_people if employer.get(p) == comp and p in last_touch]
        lt = max([t for t in [last_touch.get(comp), *staff] if t is not None], default=None)
        df = facts.get(deal, {}) if deal else {}
        companies_out.append({"node_id": comp,
                              "name": text_of(facts.get(comp, {}).get("company.name"))
                              or nodes[comp][1], "aliases": aliases.get(comp, []),
                              "deal_status": text_of(df.get("deal.status")),
                              "deal_stage": text_of(df.get("deal.stage")),
                              "last_touch_at": iso(lt)})
    if threshold is not None:
        removed.extend(r.node_id for r in c.execute(text(
            "select distinct g.node_id from graph_nodes g where g.org_id = :o "
            "and g.valid_to is not null and g.valid_to >= :t "
            "and g.node_type = any(array['person', 'company', 'meeting', 'commitment']) "
            "and not exists (select 1 from graph_nodes l where l.org_id = g.org_id "
            "and l.node_id = g.node_id and l.valid_to is null) limit 1000"),
            {"o": org_id, "t": threshold}))
    return {"people": people_out, "companies": companies_out, "meetings": meeting_out,
            "busy": _merge_busy(busy), "commitments": commitments,
            "removed": sorted(set(removed))}


def encode(doc: dict) -> bytes:
    return json.dumps(doc, separators=(",", ":"), default=str).encode()


def _fit(doc: dict) -> dict:
    """≤ 2 MB gzipped (§2.1): drop the least-recently-touched people until it fits."""
    while len(gzip.compress(encode(doc), 5)) > SIZE_CAP_GZ and doc["people"]:
        doc["people"] = doc["people"][: len(doc["people"]) // 2]
        doc["truncated"] = True
    return doc


__all__ = ["DELTA_MARGIN", "MAX_DELTA_AGE", "SCHEMA_VERSION", "build", "encode",
           "ensure_version", "version_instant"]
