"""P-09 / P-10 · someone is away and a deadline depends on them.

P-10 (deadline at risk, owner away): an OPEN commitment due within `DEADLINE_HORIZON_DAYS` whose
owner holds an absence window covering the due date → one team situation to the person it is owed
to (a seat), else the owner's manager, else the first admin — never the absent owner. The body
names the proposed cover (P-11) or says there is none.

P-09 (leave → the people it affects) is delivered THROUGH P-10: the affected people are the
beneficiaries of the away person's commitments inside the window, and `team_away` answers "who is
away" for the team view (`GET /v1/team/away`). A window with nothing depending on it tells nobody.

No leave reason ever leaves this module: windows are reported as who + when; the `sick` kind is
reported as `leave`.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.correlation_people import (CommitmentLink, load_directory,
                                                      org_visible_windows)
from genios_engine.reason.team.common import (DEADLINE_HORIZON_DAYS, Situation, TeamContext, day,
                                              digest, span, window_evidence)
from genios_engine.reason.team.cover import propose_cover
from genios_engine.reason.team.emit import clip

CAPABILITY = "team.deadline_at_risk"
#: Kinds a person may see about a colleague. `sick` is health information → reported as leave.
_PUBLIC_KIND = {"sick": "leave"}


def _recipient(conn, ctx: TeamContext, link: CommitmentLink) -> str | None:
    owner_seat = link.owner.seat_id if link.owner else None
    b = link.beneficiary
    if b is not None and b.seat_id and b.seat_id != owner_seat:
        return b.seat_id
    if owner_seat:
        manager = conn.execute(text(
            "select m.seat_id from org_seats s join org_seats m on m.org_id = s.org_id "
            "and m.seat_id = s.manager_seat_id and m.active "
            "where s.org_id = :o and s.seat_id = :s"),
            {"o": ctx.org_id, "s": owner_seat}).scalar()
        if manager and manager != owner_seat:
            return manager
        admin = conn.execute(text(
            "select seat_id from org_seats where org_id = :o and active and role = 'admin' "
            "and seat_id <> :s order by seat_id limit 1"),
            {"o": ctx.org_id, "s": owner_seat}).scalar()
        return admin
    return None


#: Node key prefixes of tracker connectors whose task an agent can reassign (`source:object_id`,
#: context/structured.py). An extracted commitment (`commitment:<sha>`) has no provider task.
_TRACKERS = frozenset({"linear", "jira", "asana", "github", "clickup", "trello"})
_MAIL = {"gmail": "gmail", "outlook": "outlook"}


def _task_ref(conn, org_id: str, node_id: str) -> dict | None:
    key = conn.execute(text(
        "select canonical_key from graph_nodes where org_id = :o and node_id = :n "
        "and valid_to is null"), {"o": org_id, "n": node_id}).scalar()
    source, _, obj = str(key or "").partition(":")
    return {"provider": source, "id": obj} if source in _TRACKERS and obj else None


def _open_thread(conn, org_id: str, person_node_id: str | None) -> dict | None:
    """The person's newest open request thread from an org-visible mail event."""
    if not person_node_id:
        return None
    r = conn.execute(text(
        "select ol.thread_id, se.source from open_loops ol join source_events se "
        "on se.org_id = ol.org_id and se.event_id = ol.opened_by_event "
        "where ol.org_id = :o and ol.subject_node_id = :n and ol.status = 'open' "
        "and ol.thread_id is not null and se.visibility_scope is distinct from 'private' "
        "order by ol.last_seen_at desc limit 1"), {"o": org_id, "n": person_node_id}).first()
    provider = _MAIL.get(str(r.source or "").lower()) if r is not None else None
    return {"provider": provider, "thread_id": r.thread_id} if provider else None


def _delegate_actions(conn, ctx: TeamContext, link: CommitmentLink, cover, window,
                      agents: dict[str, str]) -> list[dict]:
    """P6 §3.5 on a deadline-at-risk situation: `task.reassign` to the proposed cover when the
    commitment IS a tracker task, and `email.follow_up_draft` (never sent) to an external
    beneficiary on their open mail thread — each only when an active agent runs that play."""
    from genios_engine.contracts import plays as PL
    out: list[dict] = []
    owner = link.owner
    what = clip(link.text, 120)
    if cover.proposed and owner is not None and owner.email and PL.PLAY_REASSIGN in agents:
        ref = _task_ref(conn, ctx.org_id, link.node_id)
        to_email = conn.execute(text(
            "select email from org_seats where org_id = :o and seat_id = :s and active"),
            {"o": ctx.org_id, "s": cover.seat_id}).scalar() if ref else None
        action = PL.delegate_action(PL.PLAY_REASSIGN, {
            "task_ref": ref, "from_seat_email": owner.email, "to_seat_email": to_email,
            "note": f"{owner.label} is away {span(window)}; “{what}” is due {day(link.due)}."},
            agents[PL.PLAY_REASSIGN]) if ref and to_email else None
        if action:
            out.append(action)
    b = link.beneficiary
    if (PL.PLAY_FOLLOW_UP in agents and b is not None and not b.seat_id and b.email
            and owner is not None):
        thread = _open_thread(conn, ctx.org_id, b.node_id)
        first = (b.name or b.label).split()[0]
        plan = (f"{cover.name} is picking it up and will have it to you by {day(link.due)}."
                if cover.proposed else "We'll confirm the date with you shortly.")
        action = PL.delegate_action(PL.PLAY_FOLLOW_UP, {
            "thread_ref": thread, "to": [b.email], "subject": f"Re: {clip(link.text, 80)}",
            "body_draft": (f"Hi {first}, a quick update on “{what}”: {owner.label} is out "
                           f"{span(window)}. {plan}"),
            "send": False}, agents[PL.PLAY_FOLLOW_UP]) if thread else None
        if action:
            out.append(action)
    return out


def deadline_situations(conn, ctx: TeamContext) -> list[Situation]:
    from genios_engine.platform.agent_plays import agents_by_play
    out: list[Situation] = []
    horizon = ctx.today + timedelta(days=DEADLINE_HORIZON_DAYS)
    agents = agents_by_play(conn, ctx.org_id)       # one statement; {} → no delegate actions
    for link in ctx.links:
        if not link.open or link.due is None or link.owner is None:
            continue
        if not ctx.today <= link.due <= horizon:
            continue
        window = next((w for w in ctx.windows_of(link.owner) if w.covers(link.due)), None)
        if window is None:
            continue
        recipient = _recipient(conn, ctx, link)
        if recipient is None:
            continue
        owner = link.owner
        away_seats = {s for s in ctx.directory.seat_ids if ctx.seat_away(s, ctx.today, link.due)}
        cover = propose_cover(conn, ctx, link, away_seats=away_seats,
                              exclude={s for s in (owner.seat_id, recipient) if s})
        b = link.beneficiary
        owed = ("you" if b is not None and b.seat_id == recipient
                else (b.label if b is not None else (link.owed_to or "a counterparty")))
        what = clip(link.text, 60)
        headline = f"{owner.label} is away {span(window)} — “{what}” due {day(link.due)}"
        # THE COVER LEADS. The card keeps ≤ 140 characters of this body, and the headline already
        # says who is away and when; the one thing the reader can act on must survive the clip.
        body = (f"{cover.sentence()} {owner.label} owes {owed} “{what}” by {day(link.due)}, "
                f"away {span(window)}.")
        evidence = [window_evidence(owner, window),
                    {"kind": "commitment", "node_id": link.node_id, "text": link.text,
                     "due": link.due.isoformat(), "owed_to": owed if owed != "you" else None},
                    *cover.evidence]
        actions = ([{"id": "assign_cover", "label": f"Ask {cover.name}",
                     "payload": {"seat_id": cover.seat_id, "commitment_node_id": link.node_id}}]
                   if cover.proposed else [])
        if agents:
            actions += _delegate_actions(conn, ctx, link, cover, window, agents)
        out.append(Situation(
            key=f"deadline_at_risk:{link.node_id}:{recipient}", seat_id=recipient,
            capability_id=CAPABILITY,
            subject_node_ids=tuple(n for n in (link.node_id, owner.node_id) if n),
            headline=headline, body=body, actions=tuple(actions), evidence=tuple(evidence),
            digest=digest(link.node_id, link.text, link.due, window.start, window.effective_end,
                          recipient, cover.seat_id, cover.blocked),
            expires_at=datetime.combine(link.due + timedelta(days=1), time.min, timezone.utc)))
    return out


def team_away(conn, org_id: str, *, start: date, end: date) -> list[dict]:
    """`GET /v1/team/away`: seats with an absence overlapping [start, end] — who and when, never
    why. External people (no seat) are not listed."""
    directory = load_directory(conn, org_id)
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for w in org_visible_windows(conn, org_id, start, end):
        person = directory.for_node(w.person_node_id)
        if (person is None or not person.seat_id) and w.person_key and "@" in w.person_key:
            person = directory.for_email(w.person_key)
        if person is None or not person.seat_id or (person.seat_id, w.start.isoformat()) in seen:
            continue
        seen.add((person.seat_id, w.start.isoformat()))
        out.append({"seat_id": person.seat_id, "name": person.label,
                    "start": w.start.isoformat(), "end": w.effective_end.isoformat(),
                    "kind": _PUBLIC_KIND.get(w.kind, w.kind)})
    return sorted(out, key=lambda r: (r["start"], r["name"].casefold(), r["seat_id"]))


__all__ = ["CAPABILITY", "deadline_situations", "team_away"]
