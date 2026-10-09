"""The founder's files — every piece of work in motion, read from what memory already holds (STEP-09).

A FILE IS ONE COUNTERPARTY'S CORRELATIONS. Correlation already groups the work by thread → person →
company (`context/correlation`), and STEP-09 made the founder's company brief take part in it: each
person a connector introduced is a correlation of their own, and so is each portal the brief watches.
A file is one anchor's correlations together — every domain the reading filed them under and every
generation of the 45-day window — because the founder asks "where are we with Kestrel", never "with
Kestrel in fundraising since 3 September". Nothing here is stored and nothing calls a model: the same
graph gives the same files, and `GET /v1/workstreams` and `scripts/pipeline_health.py` read this one
answer.

THE KIND IS THE BRIEF'S WORD, NEVER GUESSED FROM THE MAIL (`STEP-09` §8.3.4). The first that holds:
  `connector` — the anchor is a connector the brief names: its own asks (golden replay 02 m04);
  `watched`   — the anchor is a domain the brief watches: a portal's or a program's notices;
  `person`    — the anchor is someone the brief names;
  `intro`     — the anchor is someone a connector the brief names introduced (an `introduced` edge);
  none        — no line of the brief stands behind it: listed, with no kind.

THE KIND OF WORK IS THE BRIEF'S WORD TOO (STEP-11, `06` D31). The kind above is a ROLE, and no file
could say what kind of WORK it is — so none could pick its playbook (STEP-11 §8.3 N1). An in-motion line
names its kind of work (`contracts/company_brief.WORK_KINDS`) and its counterparty; a file takes that
line's kind as its `work_kind` when the line's address is one of the file's people's, or its domain is
the anchor's domain or a parent of it (`lakshya.test` names `apply.lakshya.test`, never
`notlakshya.test`). The roles stay beside it: an intro's file can be investor work. A line with a kind
and no counterparty names no file, and a file no line names has no kind of work.

WHOSE MOVE is read from the turn the pipeline writes on each of the file's people
(`thread.ball_in_court`): `ours` while anyone in the file waits on us — answering one partner at a
fund does not answer the other — `theirs` when every turn is with them, none when nobody's turn is
written. Per person, not per thread: one introduction of two people is one thread and two files, and
answering one of them must not make it the other's move. A connector's nudge and a portal's machine
address write no turn (STEP-09 C3), so neither ever makes a move ours.

THE OPEN ASKS are the open loops of the file's people: asked of us (`owed_by` us) or awaited from
them (`owed_by` them).

AN ORG-LEVEL READER, SO NOTHING PRIVATE (`context/fact_visibility`): an event a seat captured
privately is no file's evidence, a private overlay is never a turn, and a loop such an event opened
is not listed.

NAMED, AND WHETHER FILED. For every counterparty the brief names — a connector, a person, a watched
domain — how much of its mail memory read that can be a file (a mailing, spam and an auto-reply never
are), and how much of that is in one. A named counterparty with such mail and nothing filed is
`unfiled`; a connector whose introductions are filed under the CONNECTOR rather than under the
people introduced is `misfiled`. Either means its mail was read before the founder named it (or the
filing failed), and the health check names it
(`scripts/pipeline_health.check_every_named_counterparty_has_a_file`).

A CONNECTOR'S RATE (STEP-10, `yc2_w27_s10 · M29.C4.L-logic.V0.U02`). On the golden set Introly's rate
— 8 introductions, 5 contacts replied, 1 call booked — could be counted by SQL over the ledger and not
from memory (`STEP-10` §8.1). Its introductions are memory now (STEP-09's `introduced` edges), so a
connector's file carries three numbers, each a `Measured` at the connector (`contracts/measured`):
  `introductions` — the people its addresses introduced, each once;
  `replied`       — of them, the share who wrote to us THEMSELVES after their introduction: the
                    mail's actor, never the turn memory keeps on them, which since STEP-09 the
                    connector's own mail writes (`STEP-10` N3); a responder, a mailing or spam is
                    not them;
  `calls`         — of them, the share on a calendar meeting that starts after it: booked, not
                    necessarily held.
A connector that introduced no one has a count of none, and a rate of nobody is no rate — "not
measured", never 0%. Nothing a seat captured privately counts — not the introduction, the answer or
the meeting.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from genios_engine.context.introductions import connector_roles
from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine
from genios_engine.contracts.measured import Measured, count_of, rate_of
from genios_engine.platform.self_identity import identity_for

#: The brief's kinds of file, in the order that decides when several lines stand behind one.
KINDS: tuple[str, ...] = ("connector", "watched", "person", "intro")

#: How memory records mail that is never a file (`context/pipeline`'s noise record).
NEVER_A_FILE: tuple[str, ...] = ("email_noise:newsletter", "email_noise:spam",
                                 "email_noise:auto_reply")

#: STEP-10 · the level a connector's numbers are measured at (`contracts/measured`).
CONNECTOR_BASIS = "connector"



@dataclass(frozen=True, slots=True)
class Ask:
    """One open loop on a file: who asked, and who owes the answer."""
    loop_id: str
    kind: str
    asked_by: str
    owed_by: str                       # "us" — they wait on us · "them" — we wait on them
    thread_id: str | None
    opened_at: datetime | None


@dataclass(frozen=True, slots=True)
class WorkFile:
    """One piece of work: a counterparty's correlations, with what the brief says it is."""
    file_id: str                       # the anchor node
    kind: str | None
    line: str | None                   # the brief's words that stand behind the kind
    introduced_by: str | None          # the connector that introduced someone in it, whatever kind
    counterparty: str
    counterparty_key: str
    counterparty_type: str
    domains: tuple[str, ...]
    correlations: tuple[str, ...]
    events: tuple[str, ...]            # oldest first
    first_touch: datetime | None
    last_touch: datetime | None
    days_quiet: float | None
    whose_move: str | None             # "ours" | "theirs" | None — nobody's turn is written
    open_asks: tuple[Ask, ...]
    # STEP-10 · a connector's file only; None on every other kind.
    introductions: Measured | None = None   # the people it introduced, each once
    replied: Measured | None = None         # of them, the share who then wrote to us themselves
    calls: Measured | None = None           # of them, the share on a meeting that starts after it
    # STEP-10 · the file's people (node ids): the anchor when it is a person, everyone who works at
    # it when it is a company — whose numbers the file shows (`context/workstream_numbers`).
    people: tuple[str, ...] = ()
    # STEP-11 (`06` D31) · the kind of work (`contracts/company_brief.WORK_KINDS`) the in-motion line
    # naming this file's counterparty gives it, or None — beside the role in `kind`, never instead.
    work_kind: str | None = None


@dataclass(frozen=True, slots=True)
class Named:
    """A counterparty the brief names, and whether its mail is filed."""
    named: str                         # connector:<address> · person:<address> · watchlist:<domain>
    line: str
    mail: int                          # its mail memory read that can be a file
    filed: int                         # of which, in a file
    misfiled: int = 0                  # a connector's introductions filed under the connector


@dataclass(frozen=True, slots=True)
class Workstreams:
    files: tuple[WorkFile, ...]
    named: tuple[Named, ...]

    @property
    def unfiled(self) -> tuple[Named, ...]:
        """Named counterparties with mail and no file — what the health check names."""
        return tuple(n for n in self.named if n.mail and not n.filed)

    @property
    def misfiled(self) -> tuple[Named, ...]:
        """Connectors whose introductions are filed under them — what the health check names too."""
        return tuple(n for n in self.named if n.misfiled)


_MEMBERS = text(
    "select k.correlation_id, k.anchor_node_id, k.domain, m.event_id, se.occurred_at "
    "  from context_correlations k "
    "  join context_correlation_members m on m.org_id = k.org_id "
    "       and m.correlation_id = k.correlation_id "
    "  join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
    " where k.org_id = :o and se.visibility_scope is distinct from 'private'")

_NODES = text(
    "select node_id, node_type, canonical_key, display_name from graph_nodes "
    " where org_id = :o and node_id = any(:ids) and valid_to is null")

_WORKS_AT = text(
    "select from_node_id, to_node_id from graph_edges "
    " where org_id = :o and edge_type = 'works_at' and valid_to is null and to_node_id = any(:ids)")

_TURNS = text(
    "select subject_node_id, value from graph_facts "
    " where org_id = :o and field = 'thread.ball_in_court' and valid_to is null "
    "   and visibility_scope <> 'private' and subject_node_id = any(:ids)")

_ASKS = text(
    "select l.loop_id, l.subject_node_id, l.awaited_from_node_id, l.kind, l.thread_id, l.opened_at "
    "  from open_loops l "
    "  left join source_events se on se.org_id = l.org_id and se.event_id = l.opened_by_event "
    " where l.org_id = :o and l.status = 'open' "
    "   and (l.subject_node_id = any(:ids) or l.awaited_from_node_id = any(:ids)) "
    "   and se.visibility_scope is distinct from 'private' "
    " order by l.opened_at, l.loop_id")

_INTRODUCED = text(
    "select e.to_node_id, n.canonical_key from graph_edges e "
    "  join graph_nodes n on n.org_id = e.org_id and n.node_id = e.from_node_id "
    "       and n.valid_to is null "
    " where e.org_id = :o and e.edge_type = 'introduced' and e.valid_to is null "
    "   and e.from_node_id = any(:ids)")

#: STEP-10 · everyone a connector introduced — unless the introduction was captured privately —
#: and whether, after it, they wrote to us themselves and were on a calendar meeting. Who WROTE is
#: the ledger's actor; the edge keeps the introduction's time (`graph_store.write_edge`).
_CONNECTOR_RATE = text(
    "select e.from_node_id, e.to_node_id, "
    "       exists (select 1 from source_events m "
    "                where m.org_id = e.org_id and m.object_type = 'email_message' "
    "                  and lower(m.actor->>'email') = lower(p.canonical_key) "
    "                  and m.occurred_at > e.valid_from "
    "                  and m.visibility_scope is distinct from 'private' "
    "                  and not exists (select 1 from graph_observations ob "
    "                                   where ob.org_id = m.org_id "
    "                                     and ob.created_by_event_id = m.event_id "
    "                                     and ob.kind = any(:never))) as replied, "
    "       exists (select 1 from source_events c "
    "                where c.org_id = e.org_id and c.object_type = 'calendar_event' "
    "                  and c.occurred_at > e.valid_from "
    "                  and c.visibility_scope is distinct from 'private' "
    "                  and lower(p.canonical_key) = any(select lower(a) "
    "                                                     from unnest(c.recipients) a)) "
    "       as called "
    "  from graph_edges e "
    "  join graph_nodes p on p.org_id = e.org_id and p.node_id = e.to_node_id "
    "       and p.valid_to is null "
    "  left join source_events se on se.org_id = e.org_id "
    "       and se.event_id = e.created_by_event_id "
    " where e.org_id = :o and e.edge_type = 'introduced' and e.valid_to is null "
    "   and e.from_node_id = any(:ids) and se.visibility_scope is distinct from 'private'")

_NAMED_MAIL = text(
    "select lower(se.actor->>'email') as sender, "
    "       exists (select 1 from context_correlation_members m "
    "                where m.org_id = se.org_id and m.event_id = se.event_id) as filed "
    "  from source_events se "
    " where se.org_id = :o and se.outcome = 'emitted' "
    "   and se.visibility_scope is distinct from 'private' "
    "   and exists (select 1 from graph_observations ob where ob.org_id = se.org_id "
    "                 and ob.created_by_event_id = se.event_id "
    "                 and (ob.kind = 'email_relevance' or ob.kind like 'email_noise:%')) "
    "   and not exists (select 1 from graph_observations ob where ob.org_id = se.org_id "
    "                     and ob.created_by_event_id = se.event_id and ob.kind = any(:never)) "
    "   and (lower(se.actor->>'email') = any(:addresses) "
    "        or split_part(lower(se.actor->>'email'), '@', 2) = any(:domains) "
    "        or exists (select 1 from unnest(cast(:domains as text[])) d "
    "                    where split_part(lower(se.actor->>'email'), '@', 2) like '%.' || d))")


_UNDER_THE_CONNECTOR = text(
    "select lower(se.actor->>'email') as sender, se.recipients, "
    "       exists (select 1 from context_correlation_members m "
    "                 join context_correlations k on k.org_id = m.org_id "
    "                      and k.correlation_id = m.correlation_id "
    "                where m.org_id = se.org_id and m.event_id = se.event_id "
    "                  and (k.anchor_node_id = any(:nodes) "
    "                       or k.anchor_node_id in (select w.to_node_id from graph_edges w "
    "                            where w.org_id = se.org_id and w.edge_type = 'works_at' "
    "                              and w.valid_to is null and w.from_node_id = any(:nodes)))) "
    "       as under_connector "
    "  from source_events se "
    " where se.org_id = :o and se.outcome = 'emitted' "
    "   and se.visibility_scope is distinct from 'private' "
    "   and lower(se.actor->>'email') = any(:addresses)")


def _lines(brief: CompanyBrief | None) -> dict[str, str]:
    """`connector:<address>` / `person:<address>` / `watchlist:<domain>` → the founder's words."""
    out: dict[str, str] = {}
    for line in getattr(brief, "lines", None) or ():
        if line.section in ("connectors", "people") and line.address:
            out.setdefault(f"{'connector' if line.section == 'connectors' else 'person'}:"
                           f"{line.address}", line.text)
        elif line.section == "watchlist" and line.domain:
            out.setdefault(f"watchlist:{line.domain}", line.text)
    return out


def _named(brief: CompanyBrief | None, key: str | None) -> str | None:
    """What the brief names this node — by its address, or a company by its domain."""
    if brief is None or not key:
        return None
    return brief.named_sender(key if "@" in key else f"x@{key}")


def _work_lines(brief: CompanyBrief | None) -> list[CompanyBriefLine]:
    """The in-motion lines that name a kind of work and a counterparty, in the brief's order — the
    order the founder accepted them (`company_brief_store.accepted`; `compose` keeps it within a
    section)."""
    return [ln for ln in getattr(brief, "lines", None) or ()
            if ln.section == "in_motion" and ln.kind and (ln.address or ln.domain)]


def _anchor_domain(key: str | None) -> str | None:
    """The domain a file's anchor is at: a company's key is its domain, a person's is their address."""
    key = str(key or "").strip().lower()
    return (key.rsplit("@", 1)[1] if "@" in key else key) or None


def _work_kind(work: list[CompanyBriefLine], addresses: set[str], domain: str | None) -> str | None:
    """The kind of work of the in-motion line that names this file — one of its people by address,
    or its anchor's domain or a parent of that domain. ⛔ When two lines name one file (a partner's
    address and the fund's domain), the FIRST the founder accepted wins, whichever names it more
    exactly: `work` is in the order they were accepted."""
    for line in work:
        if line.address and line.address in addresses:
            return line.kind
        if line.domain and domain and (domain == line.domain
                                       or domain.endswith("." + line.domain)):
            return line.kind
    return None


def _accepted_brief(conn, org_id: str) -> CompanyBrief:
    from genios_engine.platform.company_brief import brief_for
    return brief_for(conn, org_id)


def files_for(conn, org_id: str, *, now: datetime,
              company_brief: CompanyBrief | None = None) -> Workstreams:
    """Every file of the tenant, most recently touched first, and the brief's named counterparties.
    `company_brief` defaults to the brief the founder has accepted, read on this connection."""
    brief = company_brief if company_brief is not None else _accepted_brief(conn, org_id)
    lines = _lines(brief)
    work = _work_lines(brief)

    grouped: dict[str, dict] = {}
    for r in conn.execute(_MEMBERS, {"o": org_id}):
        f = grouped.setdefault(r.anchor_node_id, {"correlations": set(), "domains": set(),
                                                  "events": {}})
        f["correlations"].add(r.correlation_id)
        f["domains"].add(r.domain)
        f["events"][r.event_id] = r.occurred_at
    anchors = sorted(grouped)

    # The file's people: the anchor when it is one, everyone who works at it when it is a company.
    people: dict[str, set[str]] = defaultdict(set)
    for r in conn.execute(_WORKS_AT, {"o": org_id, "ids": anchors}):
        people[r.to_node_id].add(r.from_node_id)
    nodes = {r.node_id: r for r in conn.execute(_NODES, {"o": org_id, "ids": anchors})}
    for a in anchors:
        if a in nodes and nodes[a].node_type != "company":
            people[a].add(a)
    everyone = sorted({p for ps in people.values() for p in ps})
    keys = {r.node_id: r.canonical_key
            for r in conn.execute(_NODES, {"o": org_id, "ids": everyone})}

    turns = {r.subject_node_id: r.value for r in conn.execute(_TURNS, {"o": org_id,
                                                                     "ids": everyone})}
    asks = list(conn.execute(_ASKS, {"o": org_id, "ids": everyone}))
    connectors = connector_roles(conn, org_id=org_id, company_brief=brief)
    introduced_by = {r.to_node_id: r.canonical_key
                     for r in conn.execute(_INTRODUCED, {"o": org_id, "ids": sorted(connectors)})}
    # STEP-10 · connector → person introduced → (wrote to us since, on a meeting since).
    since: dict[str, dict[str, tuple[bool, bool]]] = defaultdict(dict)
    for r in conn.execute(_CONNECTOR_RATE, {"o": org_id, "ids": sorted(connectors),
                                            "never": list(NEVER_A_FILE)}):
        since[r.from_node_id][r.to_node_id] = (bool(r.replied), bool(r.called))

    files: list[WorkFile] = []
    for a in anchors:
        node = nodes.get(a)
        if node is None:
            continue                    # merged away since: its correlations are re-derived later
        mine = people.get(a, set())
        kinds: dict[str, str | None] = {}         # kind → the brief's words behind it
        own = sorted(keys[p] for p in mine if p in connectors and p in keys)
        if own:
            kinds["connector"] = lines.get(f"connector:{own[0]}")
        named = _named(brief, node.canonical_key)
        if str(named or "").startswith("watchlist:"):
            kinds["watched"] = lines.get(named)
        by = None
        for p in sorted(mine):
            said = _named(brief, keys.get(p))
            if str(said or "").startswith("person:"):
                kinds.setdefault("person", lines.get(said))
            if p in introduced_by:
                by = by or introduced_by[p]
                kinds.setdefault("intro", lines.get(f"connector:{introduced_by[p]}"))
        kind = next((k for k in KINDS if k in kinds), None)
        moves = {turns[p] for p in mine if p in turns}
        rate = (_connector_rate(since, [p for p in mine if p in connectors])
                if kind == "connector" else (None, None, None))

        events = sorted(grouped[a]["events"].items(),
                        key=lambda e: (e[1] is not None, e[1] or now, e[0]))
        dated = [at for _e, at in events if at is not None]
        last = max(dated) if dated else None
        files.append(WorkFile(
            file_id=a, kind=kind, line=kinds.get(kind) if kind else None, introduced_by=by,
            counterparty=node.display_name or node.canonical_key,
            counterparty_key=node.canonical_key, counterparty_type=node.node_type,
            domains=tuple(sorted(grouped[a]["domains"])),
            correlations=tuple(sorted(grouped[a]["correlations"])),
            events=tuple(e for e, _at in events),
            first_touch=min(dated) if dated else None, last_touch=last,
            days_quiet=(round((now - last).total_seconds() / 86400, 1) if last else None),
            whose_move=("ours" if "us" in moves else "theirs" if "them" in moves else None),
            open_asks=tuple(
                Ask(loop_id=r.loop_id, kind=r.kind, asked_by=r.subject_node_id,
                    owed_by="them" if r.awaited_from_node_id in mine else "us",
                    thread_id=r.thread_id, opened_at=r.opened_at)
                for r in asks if r.subject_node_id in mine or r.awaited_from_node_id in mine),
            introductions=rate[0], replied=rate[1], calls=rate[2], people=tuple(sorted(mine)),
            work_kind=_work_kind(work, {str(keys[p]).strip().lower() for p in mine if p in keys},
                                 _anchor_domain(node.canonical_key))))
    files.sort(key=lambda f: (f.last_touch is None, -(f.last_touch.timestamp())
                              if f.last_touch else 0, f.file_id))
    return Workstreams(files=tuple(files),
                       named=_named_counterparties(conn, org_id, brief, lines, connectors))


def _connector_rate(since: dict[str, dict[str, tuple[bool, bool]]],
                    connector_nodes: list[str]) -> tuple[Measured, Measured, Measured]:
    """The people the file's connector addresses introduced, each once, and of them the share who
    then wrote to us and who met us. Introduced twice, a person answered or met us after either
    introduction — the earliest is theirs."""
    people: dict[str, tuple[bool, bool]] = {}
    for node in connector_nodes:
        for person, (replied, called) in since.get(node, {}).items():
            was = people.get(person, (False, False))
            people[person] = (was[0] or replied, was[1] or called)
    k = len(people)
    # A count is what it counts — zero included, "none" (`contracts/measured.count_of`).
    return (count_of(k, basis=CONNECTOR_BASIS),
            rate_of(sum(r for r, _c in people.values()), k, basis=CONNECTOR_BASIS),
            rate_of(sum(c for _r, c in people.values()), k, basis=CONNECTOR_BASIS))


def _named_counterparties(conn, org_id: str, brief: CompanyBrief | None, lines: dict[str, str],
                          connectors: dict[str, str]) -> tuple[Named, ...]:
    if not lines:
        return ()
    mail: dict[str, list[int]] = {named: [0, 0, 0] for named in lines}
    addresses = sorted(n.split(":", 1)[1] for n in lines if not n.startswith("watchlist:"))
    domains = sorted(n.split(":", 1)[1] for n in lines if n.startswith("watchlist:"))
    for r in conn.execute(_NAMED_MAIL, {"o": org_id, "never": list(NEVER_A_FILE),
                                        "addresses": addresses, "domains": domains}):
        named = brief.named_sender(r.sender) if brief is not None else None
        if named in mail:
            mail[named][0] += 1
            mail[named][1] += int(bool(r.filed))
    # A connector's INTRODUCTION — its mail to someone besides us and its fellow connectors — filed
    # under the connector or its company: read before the founder named it, never split (`03` F92).
    by_connector = sorted(n.split(":", 1)[1] for n in lines if n.startswith("connector:"))
    if by_connector and connectors:
        us = identity_for(conn, org_id)
        for r in conn.execute(_UNDER_THE_CONNECTOR, {"o": org_id, "nodes": sorted(connectors),
                                                     "addresses": by_connector}):
            introduced = {str(a).strip().lower() for a in (r.recipients or ())} - set(by_connector)
            if r.under_connector and any(not us.is_us(a) for a in introduced):
                mail[f"connector:{r.sender}"][2] += 1
    return tuple(Named(named=n, line=lines[n], mail=m, filed=f, misfiled=x)
                 for n, (m, f, x) in sorted(mail.items()) if m or x)


def file_as_dict(f: WorkFile) -> dict:
    """One file as JSON — an entry of `GET /v1/workstreams`, and the head of
    `GET /v1/workstreams/{file_id}`."""
    def iso(at):
        return at.isoformat() if at else None

    def said(measured):
        return measured.as_dict() if measured is not None else None
    return {
        "file_id": f.file_id, "kind": f.kind, "work_kind": f.work_kind, "line": f.line,
        "introduced_by": f.introduced_by,
        "counterparty": {"name": f.counterparty, "key": f.counterparty_key,
                         "type": f.counterparty_type},
        "domains": list(f.domains), "correlations": list(f.correlations),
        "events": list(f.events), "first_touch": iso(f.first_touch),
        "last_touch": iso(f.last_touch), "days_quiet": f.days_quiet,
        "whose_move": f.whose_move,
        "open_asks": [{"loop_id": a.loop_id, "kind": a.kind, "asked_by": a.asked_by,
                       "owed_by": a.owed_by, "thread_id": a.thread_id,
                       "opened_at": iso(a.opened_at)} for a in f.open_asks],
        "introductions": said(f.introductions), "replied": said(f.replied),
        "calls": said(f.calls),
    }


def as_dict(ws: Workstreams, *, now: datetime) -> dict:
    """The read model as JSON — what `GET /v1/workstreams` returns."""
    return {
        "as_of": now.isoformat(),
        "files": [file_as_dict(f) for f in ws.files],
        "named": [{"named": n.named, "line": n.line, "mail": n.mail, "filed": n.filed,
                   "misfiled": n.misfiled} for n in ws.named],
        "unfiled": [n.named for n in ws.unfiled],
        "misfiled": [n.named for n in ws.misfiled],
    }


__all__ = ["Ask", "KINDS", "NEVER_A_FILE", "Named", "WorkFile", "Workstreams", "as_dict",
           "file_as_dict", "files_for"]
