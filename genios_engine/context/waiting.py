"""Derived WAITING state — the facts that only exist because nothing happened.

Every other L2 writer records something that occurred: a message arrived, a commitment was made,
a stage moved.  The intelligence a user actually asks for is the opposite shape — "they have not
replied", "no follow-up was sent", "we have not heard from them in three weeks".  No source system
emits that.  It has to be derived against a clock, from the gaps between the events we hold.

Without these five fields the whole stack could see WHO and WHAT but never HOW LONG or WHOSE TURN
FOR HOW LONG, so a card could say "a decision is sitting with them" and nothing more specific,
however good the authored expertise behind it was.

THE TIMELINE SOURCE IS `graph_source_refs`, NOT the facts themselves.  `thread.last_outbound` and
`thread.last_inbound` are single-valued: a second outbound overwrites the first, so the fact rows
hold the LATEST message, never the sequence.  But every write — including a corroborating no-op —
attaches a `graph_source_refs` row bound to the event that caused it, and the field name on that
row carries the direction.  Joining refs back to `source_events` therefore reconstructs the full
directed message timeline per counterparty, which is the only place a follow-up COUNT or a reply
CADENCE can come from.

Deterministic and LLM-free, like `derived.py`: these are arithmetic over timestamps already
committed, so the same graph yields the same numbers on every run.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import text

from genios_engine.context.derived import _write_fact

#: How far back the timeline is reconstructed.  A follow-up count is about the CURRENT exchange,
#: and `situations.DORMANT_AFTER_DAYS` already declares that a conversation older than 45 days has
#: ended and reopens as a new generation.  180 gives four of those generations of headroom while
#: keeping the join bounded on a founder inbox with years of mail in it.
_WINDOW_DAYS = 180

#: The two fields whose source refs ARE the message timeline, mapped to direction.
_DIRECTION_FIELD = {"thread.last_outbound": "out", "thread.last_inbound": "in"}

#: Observation kinds that mean WE PUT A QUESTION TO THEM — the difference between waiting for an
#: answer and merely not having written lately.  Without one of these, silence is not a failure to
#: respond, and a card that treats it as one is inventing an obligation nobody took on.
_ASK_KINDS: frozenset[str] = frozenset({
    "question", "meeting_request", "proposal_sent", "demo_requested",
    "contract_requested", "next_step_agreed",
    # The administrative and fundraising asks. Without these the whole set was sales-shaped, so
    # on an admin inbox `response_expected` would have been False on every row — every waiting
    # situation reading as "we just have not written lately" when in fact a signature, an
    # introduction or a document had been asked for and never came back.
    "approval_requested", "information_requested", "intro_requested", "investor_update_sent",
})

_TIMELINE = (
    "select f.subject_node_id as node_id, f.field as field, se.occurred_at as at "
    "from graph_source_refs r "
    "join graph_facts f on f.fact_version_id = r.fact_version_id and f.org_id = r.org_id "
    "join source_events se on se.event_id = r.event_id "
    "where r.org_id = :o and f.field in ('thread.last_outbound', 'thread.last_inbound') "
    "and se.occurred_at >= :since"
)

_ASKS = (
    "select distinct subject_node_id from graph_observations "
    "where org_id = :o and status = 'active' and kind = any(:kinds) "
    "and subject_node_id is not null"
)


def _days(later: datetime, earlier: datetime) -> int:
    return max(0, int((later - earlier).total_seconds() // 86400))


def _reply_gaps(timeline: list[tuple[str, datetime]]) -> list[float]:
    """Days between each outbound and the counterparty's NEXT inbound.

    Only the first reply after an outbound counts: a thread where they answered once and then sent
    four more messages describes one reply latency, not five.  Consecutive outbounds with no reply
    between them contribute nothing — an unanswered message has no latency yet, and scoring it as
    zero would make a silent counterparty look fast.
    """
    gaps: list[float] = []
    pending: datetime | None = None
    for direction, at in timeline:
        if direction == "out":
            if pending is None:
                pending = at
        elif pending is not None:
            gaps.append((at - pending).total_seconds() / 86400.0)
            pending = None
    return gaps


def _state(timeline: list[tuple[str, datetime]], now: datetime) -> dict:
    """One counterparty's waiting state from their directed message timeline."""
    outs = [at for direction, at in timeline if direction == "out"]
    ins = [at for direction, at in timeline if direction == "in"]
    last_out = max(outs) if outs else None
    last_in = max(ins) if ins else None

    state: dict[str, object] = {}
    if last_in is not None:
        state["thread.last_heard_days"] = _days(now, last_in)

    waiting = last_out is not None and (last_in is None or last_in < last_out)
    if waiting:
        state["thread.days_waiting"] = _days(now, last_out)
        # The first message is the ask; only what came AFTER it is a follow-up.  Counted against
        # the last inbound rather than against the whole history, so a thread that went quiet,
        # revived, and went quiet again reports the current streak instead of a lifetime total.
        since = [at for at in outs if last_in is None or at > last_in]
        state["thread.follow_up_count"] = max(0, len(since) - 1)

    gaps = _reply_gaps(sorted(timeline, key=lambda pair: pair[1]))
    # Two gaps is the minimum that describes a HABIT.  One reply is an anecdote, and a threshold
    # built on an anecdote is exactly the invented normal this field exists to replace.
    if len(gaps) >= 2:
        state["party.reply_cadence_days"] = round(median(gaps), 2)
    return state


def compute_waiting(store, org_id: str, *, now: datetime | None = None) -> int:
    """Write the waiting/absence facts for every counterparty in the org. Returns rows written."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=_WINDOW_DAYS)

    with store.engine.begin() as c:
        rows = c.execute(text(_TIMELINE), {"o": org_id, "since": since}).all()
        asked = {r[0] for r in c.execute(text(_ASKS),
                                         {"o": org_id, "kinds": list(_ASK_KINDS)}).all()}

        per_node: dict[str, list[tuple[str, datetime]]] = {}
        for node_id, field, at in rows:
            direction = _DIRECTION_FIELD.get(str(field))
            if direction is None or at is None:
                continue
            moment = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
            per_node.setdefault(str(node_id), []).append((direction, moment))

        written = 0
        for node_id, timeline in per_node.items():
            state = _state(timeline, now)
            if "thread.days_waiting" in state:
                # Written ONLY while waiting, and written as False rather than omitted when we
                # never asked: "we are waiting and put no question to them" is a real and
                # different situation from "we are waiting on an answer", and the two need
                # opposite advice.  Absent would collapse them into one.
                state["thread.response_expected"] = node_id in asked
            for field, value in state.items():
                if isinstance(value, bool):
                    _write_fact(c, org_id, node_id, field, "true" if value else "false",
                                "bool", now)
                else:
                    _write_fact(c, org_id, node_id, field, repr(value), "number", now)
                written += 1
    return written


__all__ = ["compute_waiting"]
