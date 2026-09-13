"""The meetings post-pass (registered in `reason/team/postpass.PASSES`) — SCREEN_INTEL_P5 §3.

    run(engine, card_store, org_id, *, now) -> int      (follow-up situations emitted)

  (a) PREP PRECOMPUTE — for every seat holding a live (unrevoked) device, each meeting it attends
      starting in the next 3 h gets its P-15 prep built into `moment_cache` (prep.precompute), so
      the desktop's evaluate is a cache read. Nothing is shown here; the evaluate shows it.
  (b) P-16 FOLLOW-UP — every `transcripts` row with `status='extracted'` → ONE
      `emit_situation(kind="team", capability_id="meeting.followup",
      key=f"followup:{transcript_id}:{seat}")` per seat that can see the transcript (its email is
      one of the transcript's principals — `context/fact_visibility.viewer_may_read`; a transcript
      is always PRIVATE to its principals, P5 §2.4). Body "You: … · Priya: … · Decided: …" from
      the commitments / decisions `raised_in` the meeting, each filtered for THAT seat (fact and
      edge-evidence visibility). A seat that can read none of them gets nothing. Re-emits only
      when the digest changes, so a rerun emits nothing.

The `transcripts` table is group A's (0155); until it exists (b) is skipped. The row is read
tolerantly — contract fields as columns, or inside a jsonb document column (`transcript` /
`doc` / `raw_extra.transcript`). Never credit-charged (D6). A failure in (a) never blocks (b).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

from sqlalchemy import text

from genios_engine.context.fact_visibility import viewer_may_read
from genios_engine.platform.logging import get_logger
from genios_engine.reason.meetings import prep as MP
from genios_engine.reason.moments.common import aware, parse_ts, text_of, value_of

_log = get_logger("genios.meetings")

PREP_HORIZON = timedelta(hours=3)
FOLLOWUP_CAPABILITY = "meeting.followup"
FOLLOWUP_TTL_SECONDS = 86400
OPEN_STATUSES = ("open", "pending", "in_progress")
ITEM_TYPES = ("commitment", "decision")
_DECISION_FIELDS = ("decision.text", "decision.summary")


# ── (a) prep precompute ─────────────────────────────────────────────────────────────────────
def device_meetings(conn, org_id: str, *, now: datetime,
                    horizon: timedelta = PREP_HORIZON) -> list[tuple[str, str, str]]:
    """[(seat_id, email, meeting node)] for seats with a live device and a meeting they attend
    starting in (now, now + horizon]. Two statements."""
    seats = {r.email: r.seat_id for r in conn.execute(text(
        "select distinct s.seat_id, lower(s.email) as email from org_seats s join devices d "
        "on d.org_id = s.org_id and d.seat_id = s.seat_id and d.revoked_at is null "
        "where s.org_id = :o and s.active and s.email is not null"), {"o": org_id})}
    if not seats:
        return []
    out = []
    for r in conn.execute(text(
            "select distinct a.alias_key as email, m.node_id, f.value from graph_aliases a "
            "join graph_edges e on e.org_id = a.org_id and e.edge_type = 'attended' "
            " and e.valid_to is null and (e.from_node_id = a.node_id or e.to_node_id = a.node_id) "
            "join graph_nodes m on m.org_id = a.org_id and m.valid_to is null "
            " and m.node_type = 'meeting' and m.node_id = case when e.from_node_id = a.node_id "
            " then e.to_node_id else e.from_node_id end "
            "join graph_facts f on f.org_id = a.org_id and f.subject_node_id = m.node_id "
            " and f.field = 'meeting.start_at' and f.valid_to is null and f.status = 'active' "
            "where a.org_id = :o and a.alias_type = 'email' and a.alias_key = any(:emails)"),
            {"o": org_id, "emails": sorted(seats)}):
        start = parse_ts(r.value)
        if start is not None and now < start <= now + horizon:
            out.append((seats[r.email], r.email, r.node_id))
    return sorted(set(out))


def precompute_preps(engine, org_id: str, *, now: datetime) -> int:
    with engine.connect() as c:
        todo = device_meetings(c, org_id, now=now)
    n = 0
    for seat_id, email, meeting in todo:
        try:
            n += int(MP.precompute(engine, org_id=org_id, seat_id=seat_id, email=email,
                                   meeting_node_id=meeting, now=now))
        except Exception:      # noqa: BLE001 — one prep never blocks the rest
            _log.exception("prep precompute failed org=%s seat=%s meeting=%s", org_id, seat_id,
                           meeting)
    return n


# ── (b) follow-ups ────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Transcript:
    transcript_id: str
    meeting_node_id: str | None
    title: str | None
    principals: tuple[str, ...]
    event_ids: tuple[str, ...]
    updated_at: datetime | None


def _doc(raw) -> dict:
    v = value_of(raw)
    return v if isinstance(v, dict) else {}


def transcript_of(row: Mapping) -> Transcript | None:
    """A `transcripts` row → Transcript. Contract fields are read from columns first, then from a
    jsonb document column holding the §3 transcript object."""
    doc = (_doc(row.get("transcript")) or _doc(row.get("doc")) or _doc(row.get("document"))
           or _doc(_doc(row.get("raw_extra")).get("transcript")))
    tid = row.get("transcript_id") or doc.get("transcript_id")
    if not tid:
        return None
    meeting = _doc(row.get("meeting")) or _doc(doc.get("meeting"))
    principals = row.get("principals") or doc.get("principals") or ()
    if isinstance(principals, str):
        principals = value_of(principals) if principals.strip().startswith("[") else [principals]
    events = [row.get(k) or doc.get(k) for k in ("event_id", "source_event_id")]
    return Transcript(
        transcript_id=str(tid),
        meeting_node_id=row.get("meeting_node_id") or meeting.get("meeting_node_id"),
        title=row.get("meeting_title") or row.get("title") or meeting.get("title"),
        principals=tuple(sorted({str(p).strip().lower() for p in principals or () if p})),
        event_ids=tuple(sorted({str(e) for e in events if e})),
        updated_at=aware(row.get("updated_at") or row.get("extracted_at")))


def _readable(scope, principals, viewer) -> bool:
    return viewer_may_read(scope, principals, viewer)


@dataclass
class Items:
    """Everything raised in one meeting, with the visibility of each piece so each seat's view is
    filtered in Python (one read serves every seat)."""
    nodes: dict            # node → (type, [(scope, principals)] of its raised_in evidence)
    facts: list            # (node, field, value, scope, principals), overlay-first, newest first
    owners: list           # (commitment, person, name, {emails}, scope, principals)


def load_items(conn, org_id: str, tx: Transcript) -> Items:
    if not tx.meeting_node_id and not tx.event_ids:
        return Items({}, [], [])
    nodes: dict[str, tuple[str, list]] = {}
    for r in conn.execute(text(
            "select e.from_node_id, n.node_type, se.event_id as ev, se.visibility_scope as sc, "
            "se.visibility_principals as who from graph_edges e "
            "join graph_nodes n on n.org_id = e.org_id and n.node_id = e.from_node_id "
            " and n.valid_to is null and n.node_type = any(:types) "
            "left join source_events se on se.org_id = e.org_id "
            " and se.event_id = e.created_by_event_id "
            "where e.org_id = :o and e.edge_type = 'raised_in' and e.valid_to is null "
            " and (e.to_node_id = cast(:m as text) "
            "  or e.created_by_event_id = any(cast(:evs as text[]))) order by e.from_node_id"),
            {"o": org_id, "types": list(ITEM_TYPES), "m": tx.meeting_node_id,
             "evs": list(tx.event_ids)}):
        entry = nodes.setdefault(r.from_node_id, (r.node_type, []))
        entry[1].append((r.sc if r.ev is not None else None, r.who))
    if not nodes:
        return Items({}, [], [])
    ids = sorted(nodes)
    facts = [(r.subject_node_id, r.field, r.value, r.visibility_scope, r.visibility_principals)
             for r in conn.execute(text(
                 "select subject_node_id, field, value, visibility_scope, visibility_principals "
                 "from graph_facts where org_id = :o and subject_node_id = any(:ids) "
                 "and valid_to is null and status = 'active' and field = any(:fields) "
                 "order by subject_node_id, field, (visibility_scope = 'private') desc, "
                 "occurred_at desc nulls last, fact_version_id"),
                 {"o": org_id, "ids": ids,
                  "fields": ["commitment.text", "commitment.status", "commitment.due_at",
                             *_DECISION_FIELDS]})]
    owners = [(r.to_node_id, r.from_node_id, r.display_name, set(r.emails or ()),
               r.sc if r.ev is not None else None, r.who)
              for r in conn.execute(text(
                  "select e.to_node_id, e.from_node_id, p.display_name, se.event_id as ev, "
                  "se.visibility_scope as sc, se.visibility_principals as who, "
                  "(select array_agg(lower(a.alias_key)) from graph_aliases a "
                  " where a.org_id = e.org_id and a.node_id = e.from_node_id "
                  " and a.alias_type = 'email') as emails from graph_edges e "
                  "join graph_nodes p on p.org_id = e.org_id and p.node_id = e.from_node_id "
                  " and p.valid_to is null and p.node_type = 'person' "
                  "left join source_events se on se.org_id = e.org_id "
                  " and se.event_id = e.created_by_event_id "
                  "where e.org_id = :o and e.edge_type = 'owns' and e.valid_to is null "
                  " and e.to_node_id = any(:ids) order by e.to_node_id, e.valid_from desc"),
                  {"o": org_id, "ids": ids})]
    return Items(nodes, facts, owners)


def _first(name: str | None) -> str:
    parts = (name or "").split()
    return parts[0] if parts else "Someone"


def _day(dt: datetime) -> str:
    return f"{dt.day} {dt.strftime('%b')}"


def compose_followup(items: Items, *, viewer: str, title: str | None,
                     meeting_node_id: str | None) -> dict | None:
    """One seat's follow-up (headline, body, subjects, evidence), or None when it can read
    nothing. Pure."""
    visible = {n: t for n, (t, ev) in items.nodes.items()
               if any(_readable(sc, who, viewer) for sc, who in ev)}
    if not visible:
        return None
    fv: dict[str, dict[str, object]] = {}
    for node, field_, value, sc, who in items.facts:
        if node in visible and _readable(sc, who, viewer):
            fv.setdefault(node, {}).setdefault(field_, value)
    owner: dict[str, tuple[str, str | None, set]] = {}
    for cm, person, name, emails, sc, who in items.owners:
        if cm in visible and cm not in owner and _readable(sc, who, viewer):
            owner[cm] = (person, name, emails)
    groups: dict[str, list[str]] = {}
    order: list[str] = []
    evidence: list[dict] = []
    decided: list[str] = []
    mine = 0
    for node in sorted(visible, key=lambda n: (text_of(fv.get(n, {}).get("commitment.due_at"))
                                               or "9999", n)):
        f = fv.get(node, {})
        if visible[node] == "decision":
            what = next((text_of(f.get(k)) for k in _DECISION_FIELDS if text_of(f.get(k))), None)
            if what:
                decided.append(what)
                evidence.append({"node_id": node, "field": "decision.text", "source": "graph"})
            continue
        what = text_of(f.get("commitment.text"))
        status = (text_of(f.get("commitment.status")) or "open").lower()
        if not what:
            continue                    # never a node's display name: it is the same text
        due = parse_ts(f.get("commitment.due_at"))
        item = what + (f" (due {_day(due)})" if due else "") + (
            "" if status in OPEN_STATUSES else " (done)")
        who_ = owner.get(node)
        if who_ is None:
            label = "No owner"
        elif viewer in who_[2]:
            label = "You"
            mine += 1
        else:
            label = _first(who_[1])
        if label not in groups:
            groups[label] = []
            order.append(label)
        groups[label].append(item)
        evidence.append({"node_id": node, "field": "commitment.text", "source": "graph"})
    order.sort(key=lambda lb: (lb != "You", lb == "No owner", lb))
    parts = [f"{lb}: " + "; ".join(groups[lb]) for lb in order]
    if decided:
        parts.append("Decided: " + "; ".join(decided))
    if not parts:
        return None
    label = title or "your meeting"
    tail = f" — {mine} for you" if mine else ""
    return {"headline": f"Follow-ups from {label}{tail}",
            "body": " · ".join(parts),
            "subjects": ([meeting_node_id] if meeting_node_id else []) + sorted(visible)[:19],
            "evidence": evidence[:19]}


def _active_seats(conn, org_id: str) -> dict[str, str]:
    return {r.e: r.seat_id for r in conn.execute(text(
        "select lower(email) as e, seat_id from org_seats where org_id = :o and active "
        "and email is not null order by created_at, seat_id"), {"o": org_id})}


def emit_followups(engine, card_store, org_id: str, *, now: datetime) -> int:
    from genios_engine.reason.team.common import digest
    from genios_engine.reason.team.emit import emit_situation
    with engine.connect() as c:
        if c.execute(text("select to_regclass('transcripts')")).scalar() is None:
            return 0
        rows = c.execute(text("select * from transcripts where org_id = :o "
                              "and status = 'extracted'"), {"o": org_id}).mappings().all()
        if not rows:
            return 0
        seats = _active_seats(c, org_id)
        held = {r.key: aware(r.last_at) for r in c.execute(text(
            "select key, last_at from team_situations where org_id = :o and kind = 'team' "
            "and key like 'followup:%'"), {"o": org_id})}
        plans = []
        for row in rows:
            tx = transcript_of(row)
            if tx is None:
                continue
            audience = [(s, e) for e, s in sorted(seats.items())
                        if viewer_may_read("private", tx.principals, e)]
            keys = [f"followup:{tx.transcript_id}:{s}" for s, _ in audience]
            if not audience or (tx.updated_at is not None and all(
                    held.get(k) is not None and held[k] >= tx.updated_at for k in keys)):
                continue
            title = tx.title
            if not title and tx.meeting_node_id:
                title = text_of(c.execute(text(
                    "select coalesce((select value #>> '{}' from graph_facts where org_id = :o "
                    " and subject_node_id = :m and field = 'meeting.title' and valid_to is null "
                    " and status = 'active' and visibility_scope is distinct from 'private' "
                    " limit 1), (select display_name from graph_nodes where org_id = :o "
                    " and node_id = :m and valid_to is null))"),
                    {"o": org_id, "m": tx.meeting_node_id}).scalar())
            plans.append((tx, title, audience, load_items(c, org_id, tx)))
    emitted = 0
    for tx, title, audience, items in plans:
        for seat_id, email in audience:
            out = compose_followup(items, viewer=email, title=title,
                                   meeting_node_id=tx.meeting_node_id)
            if out is None:
                continue
            actions = ([MP.open_meeting_action(tx.meeting_node_id)]
                       if tx.meeting_node_id else [])
            evidence = [{"kind": "transcript", "transcript_id": tx.transcript_id,
                         "source": "transcript"}, *out["evidence"]]
            try:
                if emit_situation(
                        engine, card_store, org_id, kind="team",
                        key=f"followup:{tx.transcript_id}:{seat_id}", seat_id=seat_id,
                        subject_node_ids=out["subjects"], headline=out["headline"],
                        body=out["body"], actions=actions, evidence=evidence,
                        priority="normal", ttl_seconds=FOLLOWUP_TTL_SECONDS,
                        digest=digest(out["headline"], out["body"], out["subjects"]),
                        capability_id=FOLLOWUP_CAPABILITY, now=now) is not None:
                    emitted += 1
            except Exception:      # noqa: BLE001 — one seat's follow-up never blocks the rest
                _log.exception("follow-up %s/%s failed org=%s", tx.transcript_id, seat_id, org_id)
    return emitted


def run(engine, card_store, org_id: str, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    try:
        n = precompute_preps(engine, org_id, now=now)
        if n:
            _log.info("meeting preps precomputed org=%s n=%d", org_id, n)
    except Exception:              # noqa: BLE001 — (a) never blocks (b)
        _log.exception("meeting prep precompute failed org=%s", org_id)
    return emit_followups(engine, card_store, org_id, now=now)


__all__ = ["FOLLOWUP_CAPABILITY", "Items", "PREP_HORIZON", "Transcript", "compose_followup",
           "device_meetings", "emit_followups", "load_items", "precompute_preps", "run",
           "transcript_of"]
