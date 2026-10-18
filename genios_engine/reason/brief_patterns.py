"""The memory patterns the company-brief drafter may read — counts, names, domains, dates (STEP-07).

The drafter proposes the founder's company brief from what memory already holds, and the plan says how
much of it: PATTERNS, never a message (`speedrun008/YC-II W27/` STEP-07 §3.3, §8.3). So this module
reads the ledger and the graph and hands the drafter only:

  * correspondents — who wrote to us and whom we wrote to, how often, first and last;
  * domains — every sender domain with its volume, how much of it the gate archived, and whether it
    looks like a government portal or an academic program;
  * waves — days on which we wrote to five or more different domains (an investor wave looks like this);
  * introducers — senders whose mail to us copies people from other companies, and how many of those
    people we then wrote to (Boardy's introductions look like this, from the envelope alone), with
    how often memory already calls the sender an introducer (`party.role`);
  * meeting series — calendar titles that recur, with how often: a series is named by its title, the
    one title a pattern carries; a single meeting never is;
  * deadlines — which sender domains carried a dated commitment, how many, and the first and last date;
  * what threads are about — the one-line objective memory already extracted for a thread, with no
    thread name (a thread is named by its subject).

Never a subject, never a body, and nothing private: mail captured privately (a seat's screen session, a
personal upload — `source_events.visibility_scope = 'private'`) is left out, and only facts every seat
may see (`graph_facts.visibility_scope = 'org'`) are read.

Every item carries an id (`p1`, `p2`, …): a proposed line must cite the ids it rests on, and an address
or domain it names must be one of these — the drafter cannot invent a sender. Deterministic: the same
memory gives the same patterns, in the same order.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text

#: How far back the drafter looks. The first sync reaches 60 days; a re-sync more (STEP-08).
WINDOW_DAYS = 180
#: Caps, so the prompt stays one screen of evidence however large the mailbox.
MAX_CORRESPONDENTS = 40
MAX_DOMAINS = 40
MAX_INTRODUCERS = 15
MAX_SERIES = 15
MAX_DEADLINE_DOMAINS = 20
MAX_THREADS = 40
#: Outbound mail to at least this many domains on one day is a wave.
WAVE_DOMAINS = 5
#: An introduction copies one or two people; a message copying more is a broadcast, not an intro.
MAX_INTRODUCED_PER_MESSAGE = 3
#: A sender is an introducer once their mail has introduced at least this many different people.
MIN_INTRODUCED = 2

_GOV = (".gov", ".gov.in", ".nic.in", ".gov.uk", ".gov.test")
_ACADEMIC = (".ac.in", ".edu", ".edu.in", ".ac.uk")

#: Mail every seat may see. `visibility_scope` NULL is a row captured before the column existed.
_SHARED_MAIL = ("org_id = :o and object_type = 'email_message' and outcome <> 'superseded' "
                "and coalesce(visibility_scope, 'org') <> 'private' and occurred_at >= :since "
                "and coalesce(actor->>'email', '') like '%@%'")

_INBOUND = text(
    "select lower(actor->>'email') as email, max(actor->>'name') as name, count(*) as n, "
    "       min(occurred_at) as first, max(occurred_at) as last, "
    "       count(*) filter (where attention = 'archive') as archived "
    f" from source_events where {_SHARED_MAIL} group by 1 order by n desc, email")

_OUTBOUND = text(
    "select lower(r) as email, count(*) as n, min(occurred_at) as first, max(occurred_at) as last, "
    "       array_agg(distinct cast(occurred_at as date)) as days "
    "  from source_events, unnest(recipients) as r "
    f" where {_SHARED_MAIL} and lower(actor->>'email') = any(:ours) "
    "   and nullif(trim(r), '') is not null "
    " group by 1 order by n desc, email")

_COPIED = text(
    "select lower(actor->>'email') as sender, occurred_at, recipients from source_events "
    f" where {_SHARED_MAIL} and coalesce(array_length(recipients, 1), 0) >= 2 "
    " order by occurred_at, event_id")

_ROLE_INTRODUCER = text(
    "select lower(n.canonical_key) as address, count(*) as n "
    "  from graph_facts f join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id "
    "       and n.valid_to is null "
    " where f.org_id = :o and f.field = 'party.role' and f.status = 'active' and f.valid_to is null "
    "   and f.visibility_scope = 'org' and f.value = to_jsonb(cast('introducer' as text)) "
    "   and n.canonical_key like '%@%' "
    " group by 1")

_MEETINGS = text(
    "select n.node_id, n.display_name as title, n.valid_from, f.value as start_at "
    "  from graph_nodes n "
    "  left join graph_facts f on f.org_id = n.org_id and f.subject_node_id = n.node_id "
    "       and f.field = 'meeting.start_at' and f.status = 'active' and f.valid_to is null "
    "  left join source_events se on se.org_id = n.org_id and se.event_id = n.created_by_event_id "
    " where n.org_id = :o and n.node_type = 'meeting' and n.valid_to is null "
    "   and coalesce(n.display_name, '') <> '' "
    "   and coalesce(se.visibility_scope, 'org') <> 'private' "
    " order by n.node_id")

_DEADLINES = text(
    "select split_part(lower(se.actor->>'email'), '@', 2) as domain, f.value as due "
    "  from graph_facts f "
    "  join source_events se on se.org_id = f.org_id and se.event_id = f.created_by_event_id "
    " where f.org_id = :o and f.field = 'commitment.due_at' and f.status = 'active' "
    "   and f.valid_to is null and f.visibility_scope = 'org' and f.occurred_at >= :since "
    "   and coalesce(se.actor->>'email', '') like '%@%' "
    " order by 1, 2")

_THREADS = text(
    "select f.value as objective, max(f.occurred_at) as at "
    "  from graph_facts f "
    " where f.org_id = :o and f.field = 'thread.objective' and f.status = 'active' "
    "   and f.valid_to is null and f.visibility_scope = 'org' and f.occurred_at >= :since "
    " group by 1 order by at desc")


def _domain(address: str | None) -> str:
    return address.rsplit("@", 1)[1] if address and "@" in address else ""


def _looks(domain: str) -> str | None:
    if domain.endswith(_GOV):
        return "government"
    if domain.endswith(_ACADEMIC):
        return "academic"
    return None


def _day(value: Any) -> str | None:
    """An ISO day from a timestamp, a date or a JSON timestamp string; None for anything else."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return None
    return None


def _objective(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("value") or value.get("text")
    line = " ".join(str(value or "").split())
    return line[:160] or None


def patterns_for(conn, org_id: str, *, now: datetime, window_days: int = WINDOW_DAYS) -> dict[str, Any]:
    """The tenant's memory as the drafter may read it. Never a subject, never a body."""
    from genios_engine.platform.self_identity import identity_for

    since = now - timedelta(days=window_days)
    us = identity_for(conn, org_id)
    ours = sorted(us.addresses)
    org = conn.execute(text("select name, company from orgs where id = :o"), {"o": org_id}).first()
    window = {"o": org_id, "since": since}

    inbound = [r for r in conn.execute(_INBOUND, window).fetchall() if not us.is_us(r.email)]
    outbound = [r for r in conn.execute(_OUTBOUND, {**window, "ours": ours}).fetchall()
                if not us.is_us(r.email)] if ours else []

    people: dict[str, dict[str, Any]] = {}
    for r in inbound:
        people[r.email] = {"address": r.email, "name": r.name, "from_them": int(r.n), "to_them": 0,
                           "first": _day(r.first), "last": _day(r.last)}
    for r in outbound:
        row = people.setdefault(r.email, {"address": r.email, "name": None, "from_them": 0,
                                          "to_them": 0, "first": None, "last": None})
        row["to_them"] = int(r.n)
        row["first"] = min(filter(None, (row["first"], _day(r.first))), default=None)
        row["last"] = max(filter(None, (row["last"], _day(r.last))), default=None)
    ranked = sorted(people.values(),
                    key=lambda p: (-(p["from_them"] + p["to_them"]), p["address"]))[:MAX_CORRESPONDENTS]

    domains: dict[str, Counter] = defaultdict(Counter)
    for r in inbound:
        d = _domain(r.email)
        if d and not us.is_us_domain(d):
            domains[d]["mail"] += int(r.n)
            domains[d]["archived"] += int(r.archived or 0)
            domains[d]["senders"] += 1
    domain_rows = sorted(domains.items(), key=lambda kv: (-kv[1]["mail"], kv[0]))[:MAX_DOMAINS]

    by_day: dict[str, set[str]] = defaultdict(set)
    written_to: dict[str, str] = {}
    for r in outbound:
        written_to[r.email] = _day(r.last) or ""
        for day in r.days or ():
            by_day[_day(day) or str(day)].add(_domain(r.email))
    waves = sorted((day, sorted(ds)) for day, ds in by_day.items() if len(ds) >= WAVE_DOMAINS)

    introduced: dict[str, dict[str, Any]] = defaultdict(lambda: {"intros": 0, "people": set(),
                                                                 "followed_up": set()})
    for r in conn.execute(_COPIED, window).fetchall():
        sender = r.sender
        if us.is_us(sender) or not any(us.is_us(x) for x in r.recipients or ()):
            continue
        third = {x.lower() for x in r.recipients or () if x and "@" in x and not us.is_us(x)
                 and x.lower() != sender and _domain(x.lower()) != _domain(sender)}
        if not third or len(third) > MAX_INTRODUCED_PER_MESSAGE:
            continue
        row = introduced[sender]
        row["intros"] += 1
        row["people"] |= third
        day = _day(r.occurred_at) or ""
        row["followed_up"] |= {x for x in third if written_to.get(x, "") >= day and x in written_to}
    roles = {r.address: int(r.n) for r in conn.execute(_ROLE_INTRODUCER, {"o": org_id}).fetchall()}
    introducers = sorted(((s, v) for s, v in introduced.items()
                          if len(v["people"]) >= MIN_INTRODUCED or s in roles),
                         key=lambda kv: (-len(kv[1]["people"]), kv[0]))[:MAX_INTRODUCERS]

    series: dict[str, dict[str, Any]] = {}
    for r in conn.execute(_MEETINGS, {"o": org_id}).fetchall():
        title = " ".join(str(r.title).split())[:120]
        row = series.setdefault(title.lower(), {"title": title, "nodes": set(), "days": set()})
        row["nodes"].add(r.node_id)
        day = _day(r.start_at) or _day(r.valid_from)
        if day:
            row["days"].add(day)
    since_day = since.date().isoformat()
    meeting_series = sorted((s for s in series.values() if len(s["nodes"]) >= 2
                             and max(s["days"], default="") >= since_day),
                            key=lambda s: (-len(s["nodes"]), s["title"].lower()))[:MAX_SERIES]

    deadlines: dict[str, list[str]] = defaultdict(list)
    for r in conn.execute(_DEADLINES, window).fetchall():
        day = _day(r.due)
        if r.domain and day and not us.is_us_domain(r.domain):
            deadlines[r.domain].append(day)
    deadline_rows = sorted(deadlines.items(),
                           key=lambda kv: (-len(kv[1]), kv[0]))[:MAX_DEADLINE_DOMAINS]

    threads = conn.execute(_THREADS, window).fetchall()

    items: list[dict[str, Any]] = []

    def add(kind: str, **fields: Any) -> None:
        items.append({"id": f"p{len(items) + 1}", "kind": kind, **fields})

    for p in ranked:
        add("correspondent", **p)
    for d, c in domain_rows:
        add("domain", domain=d, mail=c["mail"], archived=c["archived"], senders=c["senders"],
            looks=_looks(d))
    for day, ds in waves:
        add("wave", day=day, domains=ds)
    for sender, v in introducers:
        add("introducer", address=sender, intros=v["intros"], people=len(v["people"]),
            followed_up=len(v["followed_up"]), called_introducer=roles.get(sender, 0))
    for s in meeting_series:
        add("meeting_series", title=s["title"], meetings=len(s["nodes"]),
            first=min(s["days"], default=None), last=max(s["days"], default=None))
    for d, days in deadline_rows:
        add("deadlines", domain=d, deadlines=len(days), first=min(days), last=max(days),
            looks=_looks(d))
    kept = 0
    for t in threads:
        about = _objective(t.objective)
        if about and kept < MAX_THREADS:
            add("thread", about=about, last=_day(t.at))
            kept += 1
    return {"company": getattr(org, "company", None), "founder": getattr(org, "name", None),
            "us": sorted(us.addresses) + sorted(us.domains), "window_days": window_days,
            "items": items}


def addresses_in(patterns: dict[str, Any]) -> frozenset[str]:
    """Every address the patterns name — the only addresses a proposal may carry."""
    return frozenset(i["address"] for i in patterns.get("items", ()) if i.get("address"))


def domains_in(patterns: dict[str, Any]) -> frozenset[str]:
    """Every domain the patterns name — the only domains a proposal may carry."""
    out = {i["domain"] for i in patterns.get("items", ()) if i.get("domain")}
    out |= {_domain(a) for a in addresses_in(patterns)}
    for i in patterns.get("items", ()):
        out.update(i.get("domains") or ())
    return frozenset(d for d in out if d)


__all__ = ["MAX_CORRESPONDENTS", "MAX_DEADLINE_DOMAINS", "MAX_DOMAINS", "MAX_INTRODUCERS",
           "MAX_SERIES", "MAX_THREADS", "WAVE_DOMAINS", "WINDOW_DAYS", "addresses_in", "domains_in",
           "patterns_for"]
