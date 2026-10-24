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
    thread name (a thread is named by its subject);
  * THE WORK IN MOTION (GeniOS-011 S27.U1) — the founder's files touched in the window
    (`context/workstreams.files_for`: one counterparty's work, its role and kind of work when the brief
    gives one, its last touch, whose move it is, its open asks counted), the open situations on those
    files, and the brief's in-motion lines, accepted or proposed and waiting for the founder.

WHY THE WORK IN MOTION (GeniOS-011 S27.U1, audit `goals-antler-cannot-appear-today`). The drafter is the
only proposer of a goal, and it read the seven patterns above alone — never a file, a situation or an
in-motion line. An accelerator application the founder was pursuing, whose file and whose expert-proposed
in-motion line memory already held, could never become a goal: the drafter never saw it. Each piece of
work is now a pattern with its own memory ids (`file_id`, `situation_id`, `line_id`), so a goal cites
it and the founder sees what it rests on. A pending in-motion line is shown as `proposed`, never as the
brief in force: it is evidence that the work is moving, and what the drafter makes of it is itself only
a proposal. A rejected line, an ended situation and a file older than the window are not in motion.

`goal_work` lists the work a goal already rests on — pending, accepted, or rejected within
`company_brief_store.REJECTED_QUIET_DAYS` — and each file and in-motion item carries that goal's status
(`goal`), so the drafter proposes one goal per piece of work, however it words it (`work_of`).

Never a subject, never a body, and nothing private: mail captured privately (a seat's screen session, a
personal upload — `source_events.visibility_scope = 'private'`) is left out, and only facts every seat
may see (`graph_facts.visibility_scope = 'org'`) are read. A file is named by its counterparty — a
person or a company, never a thread — and is an org-level read (`context/workstreams`); a situation is
shown only on a listed file, and only when an event every seat may see is in it.

Every item carries an id (`p1`, `p2`, …): a proposed line must cite the ids it rests on, and an address
or domain it names must be one of these — the drafter cannot invent a sender. Deterministic: the same
memory gives the same patterns, in the same order.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping
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
#: GeniOS-011 S27.U1 · the work in motion, capped like every other pattern: the most recently touched
#: files, the most recently seen situations on them, and the brief's in-motion lines, accepted first.
MAX_FILES = 25
MAX_SITUATIONS = 25
MAX_IN_MOTION = 25
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

#: GeniOS-011 S27.U1 · the open situations on the listed files, seen in the window, each with at least one
#: member event every seat may see — a situation memory holds only from a private capture is not shown.
_SITUATIONS = text(
    "select s.situation_id, s.anchor_node_id, s.situation_type, s.domain, s.status, "
    "       s.first_seen_at, s.last_seen_at "
    "  from context_situations s "
    " where s.org_id = :o and s.status = any(:open) and s.anchor_node_id = any(:files) "
    "   and s.last_seen_at >= :since "
    "   and exists (select 1 from context_correlation_members m "
    "                 join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
    "                where m.org_id = s.org_id and m.correlation_id = s.correlation_id "
    "                  and se.visibility_scope is distinct from 'private') "
    " order by s.last_seen_at desc, s.situation_id limit :n")

#: GeniOS-011 S27.U1 · the brief's in-motion lines in force or waiting for the founder — accepted first.
_IN_MOTION = text(
    "select line_id, text, status, kind, address, domain, proposed_by from company_brief_lines "
    " where org_id = :o and section = 'in_motion' and status in ('accepted', 'proposed') "
    " order by status, proposed_at, line_id limit :n")

#: GeniOS-011 S27.U1 · the goals the brief holds, waits on, or was told no to — with what they rest on.
_GOALS = text(
    "select status, evidence, decided_at, text from company_brief_lines "
    " where org_id = :o and section = 'goals' and status in ('proposed', 'accepted', 'rejected') "
    " order by proposed_at, line_id")

#: A goal's status, strongest first — which one an item is marked with when several rest on it.
_GOAL_STRENGTH = ("accepted", "proposed", "rejected")


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


def work_of(item: Mapping[str, Any]) -> frozenset[str]:
    """The pieces of work in motion a pattern item stands for — its file (`file:<node>`), and an
    in-motion line by its id (`line:<id>`) — or none, for every other pattern. A goal's stored evidence
    is the item itself under its pattern id (`brief_drafter._evidence`), so it stands for the same work:
    that is how a goal reworded next week is still known to rest on work a goal already rests on."""
    out: set[str] = set()
    if item.get("file_id"):
        out.add(f"file:{item['file_id']}")
    if item.get("kind") == "in_motion" and item.get("line_id"):
        out.add(f"line:{item['line_id']}")
    return frozenset(out)


def _goal_work(conn, org_id: str, *, now: datetime, texts: list | None = None) -> dict[str, str]:
    """Each piece of work a goal rests on → that goal's status, the strongest when several do. A goal
    the founder rejected counts within `REJECTED_QUIET_DAYS`, as the store's own rule does
    (`company_brief_store._same_line`), so the weekly review cannot nag. G012 H-22 · each such goal's words are
    appended to `texts`, so a company goal is never proposed again in other words (`brief_drafter`)."""
    from genios_engine.platform.company_brief_store import REJECTED_QUIET_DAYS

    quiet = now - timedelta(days=REJECTED_QUIET_DAYS)
    out: dict[str, str] = {}
    for r in conn.execute(_GOALS, {"o": org_id}).fetchall():
        if r.status == "rejected" and (r.decided_at is None or r.decided_at < quiet):
            continue
        if texts is not None and r.text:
            texts.append(str(r.text))
        evidence = json.loads(r.evidence or "[]") if isinstance(r.evidence, str) else r.evidence
        for e in evidence or ():
            if not isinstance(e, Mapping):
                continue
            for work in work_of(e):
                out[work] = _strongest(out.get(work), r.status)
    return out


def _strongest(*statuses: str | None) -> str | None:
    """The strongest of some goals' statuses (`_GOAL_STRENGTH`), or None when there is none."""
    return next((s for s in _GOAL_STRENGTH if s in statuses), None)


def _counterparty(key: str | None, node_type: str | None) -> dict[str, str | None]:
    """A file's counterparty as a pattern names it — a person by their address, a company by its
    domain; anything else (a deal, a project) by neither, so it never widens what a proposal may name."""
    key = str(key or "").strip().lower()
    if "@" in key:
        return {"address": key, "domain": None}
    if node_type == "company" and "." in key and " " not in key:
        return {"address": None, "domain": key}
    return {"address": None, "domain": None}


def _names_file(address: str | None, domain: str | None, file: Mapping[str, Any]) -> bool:
    """Whether an in-motion line's counterparty is this file's, as `context/workstreams._work_kind`
    reads it: the person by their address; a file at the line's domain or under it (`lakshya.test`
    names `apply.lakshya.test`, never `notlakshya.test`); and a company's file by the domain of the
    address of someone at it."""
    if address and file.get("address") == address:
        return True
    at = file.get("domain") or _domain(file.get("address"))
    named = (domain, _domain(address) if file.get("domain") else None)
    return bool(at) and any(d and (at == d or at.endswith("." + d)) for d in named)


def _work_in_motion(conn, org_id: str, *, now: datetime, since: datetime,
                    add, held: dict[str, str]) -> None:
    """GeniOS-011 S27.U1 · the files touched in the window, the open situations on them, and the
    brief's in-motion lines — each added as a pattern with the memory ids it stands for."""
    from genios_engine.context.workstreams import OPEN_STATUSES
    from genios_engine.context.workstreams import files_for

    files: dict[str, dict[str, Any]] = {}
    for f in files_for(conn, org_id, now=now).files:
        if len(files) >= MAX_FILES:
            break
        if f.last_touch is None or f.last_touch < since:
            continue
        files[f.file_id] = add(
            "file", file_id=f.file_id, name=f.counterparty, type=f.counterparty_type,
            **_counterparty(f.counterparty_key, f.counterparty_type),
            role=f.kind, work_kind=f.work_kind, areas=list(f.domains), events=len(f.events),
            first=_day(f.first_touch), last=_day(f.last_touch), whose_move=f.whose_move,
            asks_ours=sum(1 for a in f.open_asks if a.owed_by == "us"),
            asks_theirs=sum(1 for a in f.open_asks if a.owed_by == "them"),
            goal=held.get(f"file:{f.file_id}"))
    if files:
        for r in conn.execute(_SITUATIONS, {"o": org_id, "open": sorted(OPEN_STATUSES),
                                            "files": sorted(files), "since": since,
                                            "n": MAX_SITUATIONS}).fetchall():
            on = files[r.anchor_node_id]
            add("situation", situation_id=r.situation_id, file=on["id"], file_id=r.anchor_node_id,
                name=on["name"], type=r.situation_type, area=r.domain, status=r.status,
                first=_day(r.first_seen_at), last=_day(r.last_seen_at))
    for r in conn.execute(_IN_MOTION, {"o": org_id, "n": MAX_IN_MOTION}).fetchall():
        on = next((f for f in files.values() if _names_file(r.address, r.domain, f)), None)
        item = add("in_motion", line_id=r.line_id, file=on["id"] if on else None,
                   file_id=on["file_id"] if on else None, text=_objective(r.text), status=r.status,
                   work_kind=r.kind, proposed_by=r.proposed_by, address=r.address, domain=r.domain)
        item["goal"] = _strongest(*(held.get(w) for w in work_of(item)))


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

    def add(kind: str, **fields: Any) -> dict[str, Any]:
        item = {"id": f"p{len(items) + 1}", "kind": kind, **fields}
        items.append(item)
        return item

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
    goal_texts: list[str] = []
    held = _goal_work(conn, org_id, now=now, texts=goal_texts)
    _work_in_motion(conn, org_id, now=now, since=since, add=add, held=held)
    return {"company": getattr(org, "company", None), "founder": getattr(org, "name", None),
            "us": sorted(us.addresses) + sorted(us.domains), "window_days": window_days,
            "items": items, "goal_work": sorted(held), "goal_texts": goal_texts}


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


__all__ = ["MAX_CORRESPONDENTS", "MAX_DEADLINE_DOMAINS", "MAX_DOMAINS", "MAX_FILES", "MAX_INTRODUCERS",
           "MAX_IN_MOTION", "MAX_SERIES", "MAX_SITUATIONS", "MAX_THREADS", "WAVE_DOMAINS", "WINDOW_DAYS",
           "addresses_in", "domains_in", "patterns_for", "work_of"]
