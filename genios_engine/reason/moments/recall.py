"""`moment.counterparty_recall` (P-02) — a known person or company is on screen: what do we know?

DETERMINISTIC, ONE HOP, NO LLM (P3 §2.2). Reuses the query assistant's one-hop read
(`reason/intelligence._neighborhood`, ≤ 40 edge neighbours) and its seat-visible fact rule
(`common.VISIBLE_FACT_SQL` — the same predicate `_retrieve` applies), plus the authoritative open
signals `_retrieve` grounds on.

Resolution order (G-15): email → LinkedIn profile url → a node id the device matched from its
slice → an exact observed name. Only person / company nodes are subjects, and never one of our
own seats (a teammate on screen is not a counterparty).

A subject whose every trace is private to ANOTHER seat reads as unknown (204): its facts and its
touches are filtered by the viewer, and nothing readable means nothing to say.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text

from genios_engine.platform.identity import norm_email, norm_linkedin_url, person_name_key
from genios_engine.reason.moments.common import (VISIBLE_EVENT_SQL, VISIBLE_FACT_SQL, aware,
                                                 fact_rows_to_map, iso, parse_ts, text_of)

CAPABILITY_ID = "moment.counterparty_recall"
CAPABILITY_VERSION = "1"
TTL_SECONDS = 900
SUBJECT_TYPES = ("person", "company")
TOUCH_WINDOW_DAYS = 365


@dataclass(frozen=True)
class Subject:
    node_id: str
    node_type: str
    name: str | None


@dataclass
class SubjectRead:
    subject: Subject
    nodes: dict[str, tuple[str, str | None]] = field(default_factory=dict)   # id → (type, name)
    facts: dict[str, dict[str, tuple]] = field(default_factory=dict)
    company: str | None = None
    seat_commitments: list[str] = field(default_factory=list)
    open_loops: int = 0
    last_touch_at: datetime | None = None
    signals: list[dict] = field(default_factory=list)
    internal: bool = False


def _keys(participants) -> list[tuple[str, str, int]]:
    out: list[tuple[str, str, int]] = []
    for p in participants or ():
        email = norm_email(getattr(p, "email", None))
        if email:
            out.append(("email", email, 0))
        li = norm_linkedin_url(getattr(p, "linkedin_url", None))
        if li:
            out.append(("linkedin_url", li, 1))
        name = person_name_key(getattr(p, "name", None))
        if name:
            out.append(("person_name", name, 3))
    return out


def resolve(conn, *, org_id: str, participants, entities, seat_email: str | None
            ) -> tuple[list[Subject], str | None]:
    """(subjects in resolution order, the seat's own person node or None). Two statements."""
    keys = _keys(participants)
    seat_key = norm_email(seat_email)
    lookup = list(keys) + ([("email", seat_key, -1)] if seat_key else [])
    hits: dict[tuple[str, str], str] = {}
    if lookup:
        for r in conn.execute(text(
                "select alias_type, alias_key, node_id from graph_aliases where org_id = :o "
                "and alias_key = any(:k) and alias_type = any(:t)"),
                {"o": org_id, "k": sorted({k for _, k, _ in lookup}),
                 "t": sorted({t for t, _, _ in lookup})}):
            hits[(r.alias_type, r.alias_key)] = r.node_id
    me = hits.get(("email", seat_key)) if seat_key else None
    ranked: list[tuple[int, int, str]] = []
    for i, (t, k, prio) in enumerate(keys):
        if (t, k) in hits:
            ranked.append((prio, i, hits[(t, k)]))
    for i, nid in enumerate(entities or ()):
        if isinstance(nid, str) and nid.strip():
            ranked.append((2, i, nid.strip()))
    ids = [nid for _, _, nid in sorted(ranked)]
    if not ids:
        return [], me
    live = {r.node_id: r for r in conn.execute(text(
        "select node_id, node_type, display_name from graph_nodes where org_id = :o "
        "and node_id = any(:ids) and valid_to is null"), {"o": org_id, "ids": sorted(set(ids))})}
    out, seen = [], set()
    for nid in ids:
        r = live.get(nid)
        if r is None or nid in seen or nid == me or r.node_type not in SUBJECT_TYPES:
            continue
        seen.add(nid)
        out.append(Subject(node_id=nid, node_type=r.node_type, name=r.display_name))
    return out, me


def subject_version(conn, *, org_id: str, node_ids) -> str:
    """The subject's own graph version (plan §6.2 cache key): its newest fact, edge, observation
    and open-loop change. One statement over indexed columns."""
    ids = sorted(set(node_ids))
    r = conn.execute(text(
        "select greatest("
        "(select max(valid_from) from graph_facts where org_id = :o and subject_node_id = any(:ids)), "
        "(select max(valid_from) from graph_edges where org_id = :o and from_node_id = any(:ids)), "
        "(select max(valid_from) from graph_edges where org_id = :o and to_node_id = any(:ids)), "
        "(select max(created_at) from graph_observations where org_id = :o "
        " and subject_node_id = any(:ids)), "
        "(select max(greatest(last_seen_at, coalesce(closed_at, last_seen_at))) from open_loops "
        " where org_id = :o and subject_node_id = any(:ids))) as v"),
        {"o": org_id, "ids": ids}).first()
    return iso(aware(r.v)) if r is not None and r.v is not None else "0"


def read(conn, *, org_id: str, subject: Subject, me: str | None, viewer: str | None,
         seat_emails: frozenset[str], now: datetime) -> SubjectRead:
    """The one-hop read for one subject (≈ 6 statements)."""
    from genios_engine.reason.authority import (AUTHORITATIVE_REASON_CODE_SQL,
                                                AUTHORITATIVE_SIGNAL_JOINS,
                                                AUTHORITATIVE_SIGNAL_PREDICATE, authority_time)
    from genios_engine.reason.intelligence import _neighborhood

    out = SubjectRead(subject=subject)
    hood = _neighborhood(conn, org_id, subject.node_id)
    # Our seat's promises: the commitments its person node owns (one of them may be owed to
    # this subject — matched below by the `commitment.owed_to` it names).
    mine: set[str] = set()
    if me:
        mine = {r.nid for r in conn.execute(text(
            "select to_node_id as nid from graph_edges where org_id = :o and from_node_id = :me "
            "and edge_type = 'owns' and valid_to is null limit 200"), {"o": org_id, "me": me})}
    rows = conn.execute(text(
        "select n.node_id, n.node_type, n.display_name, "
        "(select array_agg(a.alias_key) from graph_aliases a where a.org_id = n.org_id "
        " and a.node_id = n.node_id and a.alias_type = 'email') as emails "
        "from graph_nodes n where n.org_id = :o and n.node_id = any(:ids) and n.valid_to is null"),
        {"o": org_id, "ids": sorted(hood | mine)}).fetchall()
    for r in rows:
        out.nodes[r.node_id] = (r.node_type, r.display_name)
        if r.node_id == subject.node_id and seat_emails & {e.lower() for e in (r.emails or ())}:
            out.internal = True
    companies = [n for n in sorted(hood) if out.nodes.get(n, ("",))[0] == "company"
                 and n != subject.node_id]
    if subject.node_type == "person" and companies:
        out.company = companies[0]
        extra = _neighborhood(conn, org_id, companies[0]) - set(out.nodes)
        if extra:
            for r in conn.execute(text(
                    "select node_id, node_type, display_name from graph_nodes where org_id = :o "
                    "and node_id = any(:ids) and valid_to is null and node_type = 'deal'"),
                    {"o": org_id, "ids": sorted(extra)}):
                out.nodes[r.node_id] = (r.node_type, r.display_name)
    out.facts = fact_rows_to_map(conn.execute(text(
        "select f.subject_node_id, f.field, f.value, f.valid_from from graph_facts f "
        "where f.org_id = :o and f.subject_node_id = any(:ids) and f.valid_to is null "
        "and f.status = 'active' and " + VISIBLE_FACT_SQL + " "
        "order by f.subject_node_id, f.field, (f.visibility_scope = 'private') desc, "
        "f.occurred_at desc nulls last, f.fact_version_id"),
        {"o": org_id, "ids": sorted(out.nodes), "viewer": viewer}).fetchall())
    out.seat_commitments = sorted(mine & set(out.nodes))
    touch_ids = [subject.node_id] + ([out.company] if out.company else [])
    r = conn.execute(text(
        "select (select count(*) from open_loops where org_id = :o and subject_node_id = :n "
        " and status = 'open') as loops, "
        "(select max(o.occurred_at) from graph_observations o left join source_events se "
        " on se.org_id = o.org_id and se.event_id = o.created_by_event_id "
        " where o.org_id = :o and o.subject_node_id = any(:ids) and o.status = 'active' "
        " and o.occurred_at <= :now and o.occurred_at > :now - make_interval(days => :win) "
        " and " + VISIBLE_EVENT_SQL + ") as last_touch"),
        {"o": org_id, "n": subject.node_id, "ids": touch_ids, "now": now,
         "win": TOUCH_WINDOW_DAYS, "viewer": viewer}).first()
    out.open_loops = int(r.loops or 0)
    out.last_touch_at = aware(r.last_touch)
    out.signals = [dict(s._mapping) for s in conn.execute(text(
        "select rr.capability_id as rule_id, " + AUTHORITATIVE_REASON_CODE_SQL +
        " as reason_code, s.subject_node_id from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
        "where s.org_id = :o and s.status = 'open' and " + AUTHORITATIVE_SIGNAL_PREDICATE +
        " and s.subject_node_id = any(:ids) "
        "order by selected_rc.final_utility_bp desc, rr.capability_id, s.signal_id limit 15"),
        {"o": org_id, "ids": sorted(hood), "authority_time": authority_time(now)})]
    return out


def _fact(read_: SubjectRead, node: str | None, field_: str):
    if not node:
        return None
    hit = read_.facts.get(node, {}).get(field_)
    return hit[0] if hit else None


def _ago(then: datetime, now: datetime) -> str:
    days = (now.date() - then.astimezone(now.tzinfo).date()).days
    if days <= 0:
        return "last touch today"
    if days == 1:
        return "last touch yesterday"
    return f"last touch {days} d ago"


def _due(dt: datetime | None) -> str:
    return dt.strftime("%-d %b") if dt else ""


def _open(read_: SubjectRead, node: str) -> bool:
    status = (text_of(_fact(read_, node, "commitment.status")) or "open").lower()
    return status in ("open", "pending", "in_progress")


def compose(read_: SubjectRead, *, now: datetime) -> dict | None:
    """The moment content, or None when there is nothing worth a toast. Pure."""
    if read_.internal:
        return None
    s = read_.subject
    name = s.name or "This contact"
    role = text_of(_fact(read_, s.node_id, "person.title")) if s.node_type == "person" else None
    company_name = read_.nodes.get(read_.company, (None, None))[1] if read_.company else None
    evidence: list[dict] = []
    parts: list[str] = []
    priority = "low"
    name_key = person_name_key(s.name)
    # what WE owe them — a commitment our seat's node owns whose `owed_to` names this subject
    for c in read_.seat_commitments:
        owed = text_of(_fact(read_, c, "commitment.owed_to"))
        if not owed or not _open(read_, c) or not name_key or person_name_key(owed) != name_key:
            continue
        what = text_of(_fact(read_, c, "commitment.text")) or read_.nodes[c][1] or "a commitment"
        due = parse_ts(_fact(read_, c, "commitment.due_at"))
        if due is not None and due < now:
            parts.append(f"You owe: {what} (overdue since {_due(due)})")
            priority = "high"
        else:
            parts.append(f"You owe: {what}" + (f" (due {_due(due)})" if due else ""))
            priority = "normal" if priority == "low" else priority
        evidence.append({"node_id": c, "field": "commitment.text", "source": "graph"})
    # what THEY owe (commitments their node owns)
    for nid, (ntype, nname) in sorted(read_.nodes.items()):
        if ntype != "commitment" or nid in read_.seat_commitments or not _open(read_, nid):
            continue
        what = text_of(_fact(read_, nid, "commitment.text")) or nname
        if what:
            parts.append(f"They owe: {what}")
            priority = "normal" if priority == "low" else priority
            evidence.append({"node_id": nid, "field": "commitment.text", "source": "graph"})
    # the deal
    deals = [n for n, (t, _) in sorted(read_.nodes.items()) if t == "deal"]
    for d in deals:
        stage = text_of(_fact(read_, d, "deal.stage"))
        status = text_of(_fact(read_, d, "deal.status"))
        if stage or status:
            parts.append(f"Deal: {stage or status}")
            evidence.append({"node_id": d, "field": "deal.stage" if stage else "deal.status",
                             "source": "graph"})
            break
    if read_.open_loops:
        parts.append(f"{read_.open_loops} open loop" + ("s" if read_.open_loops != 1 else ""))
        priority = "normal" if priority == "low" else priority
    if read_.last_touch_at is None and not parts:
        return None
    headline = name + (f" ({role})" if role else "")
    if company_name and s.node_type == "person":
        headline += f" · {company_name}"
    if read_.last_touch_at is not None:
        headline += f" — {_ago(read_.last_touch_at, now)}"
        evidence.insert(0, {"node_id": s.node_id, "field": "last_touch_at", "source": "graph",
                            "at": iso(read_.last_touch_at)})
    if role:
        evidence.append({"node_id": s.node_id, "field": "person.title", "source": "graph"})
    for sig in read_.signals[:3]:
        evidence.append({"node_id": sig.get("subject_node_id"),
                         "field": f"signal:{sig.get('rule_id')}", "source": "reasoning",
                         "reason_code": sig.get("reason_code")})
    return {"kind": "advice", "priority": priority, "headline": headline[:300],
            "body": " · ".join(parts)[:2000] or None,
            "actions": [{"id": "open_in_genios", "label": "Open in GeniOS",
                         "payload": {"node_id": s.node_id}},
                        {"id": "dismiss", "label": "Dismiss"}],
            "evidence": evidence, "ttl_seconds": TTL_SECONDS,
            "capability_id": CAPABILITY_ID, "capability_version": CAPABILITY_VERSION}


__all__ = ["CAPABILITY_ID", "CAPABILITY_VERSION", "Subject", "SubjectRead", "compose", "read",
           "resolve", "subject_version"]
