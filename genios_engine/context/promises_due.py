"""Your promises due — every open promise of ours, overdue or due within a week, with the mail it was made in and
the person it is owed to (STEP-15, F30).

`speedrun008/YC-II W27/` STEP-15 §8.4 item 1, tree `yc2_w27_s15` M44.C2.L-data.V0.U05. A promise is a commitment
node of memory (`context/pipeline` writes one per promise the extraction kept: its words `commitment.text`, its
`commitment.due_at`, its `commitment.status`, an `owns` edge from whoever made it, and `commitment.owner` when the
maker's address is known). F30's — *"I'll send the pilot proposal by Friday"*, from the founder's own sent mail —
was in memory and in no brief: *"the pilot proposal to Gaurav, by Friday"*.

  OURS — by STEP-04's one identity (`platform/self_identity`): its `commitment.owner` is an address of ours; else
    the node that `owns` it is ours; else — no owner written at all — the mail it was made in was sent by us.
  DUE — open (`commitment.status` open or unwritten), and its due date overdue or within `DUE_WITHIN_DAYS` of the
    instant asked about. An undated promise has no due date to be due by: it is not listed here.
  OWED TO — the people the mail it was made in went to, when that mail was ours: by name, never an address
    (`platform/self_identity.spoken_name`), with the address kept apart so the brief can find their file.

Not a private fact, never one: an org-level reader. One connection, as of an instant; no model, nothing written.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.self_identity import identity_for, spoken_name

#: How far ahead a promise is due: a week.
DUE_WITHIN_DAYS = 7
#: The commitment statuses that are still open — `context/pipeline` writes `open`; an unwritten one is open.
OPEN_STATUSES = frozenset({"", "open", "pending", "in_progress"})

_PROMISES = text(
    "select t.subject_node_id as promise_id, t.value #>> '{}' as words, t.created_by_event_id as event_id, "
    "       d.value #>> '{}' as due_at, s.value #>> '{}' as status, w.value #>> '{}' as owner, "
    "       maker.node_type as maker_type, maker.canonical_key as maker_key, "
    "       lower(se.actor->>'email') as sender, se.recipients "
    "  from graph_facts t "
    "  join graph_facts d on d.org_id = t.org_id and d.subject_node_id = t.subject_node_id "
    "       and d.field = 'commitment.due_at' and d.valid_to is null and d.status = 'active' "
    "  left join graph_facts s on s.org_id = t.org_id and s.subject_node_id = t.subject_node_id "
    "       and s.field = 'commitment.status' and s.valid_to is null and s.status = 'active' "
    "  left join graph_facts w on w.org_id = t.org_id and w.subject_node_id = t.subject_node_id "
    "       and w.field = 'commitment.owner' and w.valid_to is null and w.status = 'active' "
    "  left join lateral (select n.node_type, n.canonical_key from graph_edges e "
    "       join graph_nodes n on n.org_id = e.org_id and n.node_id = e.from_node_id and n.valid_to is null "
    "       where e.org_id = t.org_id and e.edge_type = 'owns' and e.valid_to is null "
    "         and e.to_node_id = t.subject_node_id order by e.from_node_id limit 1) maker on true "
    "  left join source_events se on se.org_id = t.org_id and se.event_id = t.created_by_event_id "
    " where t.org_id = :o and t.field = 'commitment.text' and t.valid_to is null and t.status = 'active' "
    "   and t.visibility_scope is distinct from 'private' "
    " order by t.subject_node_id")

_PEOPLE = text(
    "select a.alias_key as email, n.node_id, n.display_name, n.canonical_key from graph_aliases a "
    "  join graph_nodes n on n.org_id = a.org_id and n.node_id = a.node_id and n.valid_to is null "
    " where a.org_id = :o and a.alias_type = 'email' and a.alias_key = any(:emails) "
    " order by a.alias_key, n.node_id")


@dataclass(frozen=True, slots=True)
class OwedTo:
    name: str | None                     # how the brief says who — never an address
    key: str                             # their address: what finds their file, never shown
    node_id: str | None


@dataclass(frozen=True, slots=True)
class PromiseDue:
    promise_id: str                      # the commitment node
    words: str
    due_at: datetime
    overdue: bool
    owed_to: tuple[OwedTo, ...]
    event_id: str | None                 # the mail it was made in


def _instant(value) -> datetime | None:
    """A due date as written — an instant; one written without its zone is read as UTC; unreadable is none."""
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
    except ValueError:
        return None
    return moment if moment is None or moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def promises_due(conn, org_id: str, *, now: datetime,
                 within_days: int = DUE_WITHIN_DAYS) -> tuple[PromiseDue, ...]:
    """Every open promise of ours due by `now` + `within_days` — the overdue first, then soonest due."""
    us = identity_for(conn, org_id)
    until = now + timedelta(days=within_days)
    found = []
    for r in conn.execute(_PROMISES, {"o": org_id}):
        due = _instant(r.due_at)
        if due is None or due > until or str(r.status or "").strip().lower() not in OPEN_STATUSES:
            continue
        if r.owner:
            ours = us.is_us(r.owner)
        elif r.maker_key:
            ours = us.is_us_node(r.maker_type, r.maker_key)
        else:
            ours = us.is_us(r.sender)
        if not ours:
            continue
        to = [str(x).lower() for x in (r.recipients or ()) if not us.is_us(x)] if us.is_us(r.sender) else []
        found.append((r, due, tuple(dict.fromkeys(to))))
    emails = sorted({e for _r, _d, to in found for e in to})
    nodes: dict[str, tuple] = {}
    if emails:
        for p in conn.execute(_PEOPLE, {"o": org_id, "emails": emails}):
            nodes.setdefault(p.email.lower(), (p.node_id, p.display_name, p.canonical_key))
    out = []
    for r, due, to in found:
        owed = tuple(OwedTo(name=spoken_name(nodes[e][1], nodes[e][2]) if e in nodes else spoken_name(None, e),
                            key=e, node_id=nodes[e][0] if e in nodes else None) for e in to)
        out.append(PromiseDue(promise_id=r.promise_id, words=" ".join(str(r.words or "").split()), due_at=due,
                              overdue=due < now, owed_to=owed, event_id=r.event_id))
    out.sort(key=lambda p: (p.due_at, p.promise_id))
    return tuple(out)


__all__ = ["DUE_WITHIN_DAYS", "OPEN_STATUSES", "OwedTo", "PromiseDue", "promises_due"]
