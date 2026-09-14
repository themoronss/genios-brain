"""The open-loop ledger's three verbs: ask opens, our reply closes, a repeat reopens.

`thread.ball_in_court` survives — it is real, useful thread state — but it stops being the
COMPLETION authority. One bit per person could never say WHICH request was answered, so
answering any of somebody's three questions read as answering all of them, and a card expiring
read as the request resolving. Each verb here touches exactly one loop row (identified by
`contracts/open_loop.open_loop_id`), which is the whole point: a match closes ONE request,
never a person.

Deterministic, no LLM, called from the same L2 transaction that writes the observation or the
outbound facts — the ledger can never disagree with the graph about what happened.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from genios_engine.contracts.open_loop import open_loop_id


def record_ask(conn, *, org_id: str, subject_node_id: str, kind: str,
               thread_id: str | None, event_id: str, at: datetime,
               awaited_from: str | None = None) -> str:
    """An ask-class observation opens its loop — or bumps / reopens the existing one.

    A follow-up repeating the ask is the SAME loop (`ask_count` grows, `last_seen_at` moves); an
    ask arriving after we answered REOPENS it, because their asking again is direct evidence our
    answer did not resolve it.

    ``awaited_from`` names WHO OWES THE ANSWER, which is not the subject: the subject is who
    ASKED. It is supplied for an ask WE send, where the answerer is the person we sent it to, and
    left null both for an ask they sent us — our own reply closes that one by subject — and for
    an ask with more than one external recipient, where no single node is the answerer. See
    `migrations/0159_open_loop_awaited_from.sql` for why a null is honest rather than a gap.
    """
    loop = open_loop_id(org_id=org_id, subject_node_id=subject_node_id, kind=kind,
                        thread_id=thread_id)
    conn.execute(text(
        "insert into open_loops (org_id, loop_id, subject_node_id, kind, thread_id, "
        "status, opened_at, last_seen_at, opened_by_event, awaited_from_node_id) "
        "values (:o, :l, :s, :k, :t, 'open', :at, :at, :ev, :aw) "
        "on conflict (org_id, loop_id) do update set "
        "  ask_count = open_loops.ask_count + 1, "
        # A follow-up that finally names one answerer fills the gap; one that names nobody must
        # not erase the answerer an earlier ask established.
        "  awaited_from_node_id = coalesce(excluded.awaited_from_node_id, "
        "                                  open_loops.awaited_from_node_id), "
        # CASE, not greatest(): same result, and it runs on the sqlite the tests use.
        "  last_seen_at = case when excluded.last_seen_at > open_loops.last_seen_at "
        "                 then excluded.last_seen_at else open_loops.last_seen_at end, "
        "  status = case when open_loops.status = 'closed' "
        "                 and excluded.last_seen_at > open_loops.closed_at "
        "                then 'open' else open_loops.status end"),
        {"o": org_id, "l": loop, "s": subject_node_id, "k": kind, "t": thread_id,
         "at": at, "ev": event_id, "aw": awaited_from})
    return loop


def close_loops_awaited_from(conn, *, org_id: str, node_id: str, thread_id: str | None,
                             event_id: str, at: datetime) -> int:
    """THEIR reply closes the asks WE were waiting on them for. The mirror of the verb above.

    `close_loops_for_reply` closes by SUBJECT, which answers "we replied, so their questions are
    handled". Nothing answered the other half — "they replied, so our questions are handled" —
    because a loop we opened is subjected on us and their inbound event never names us. This
    matches on the answerer instead, so an ask only ever closes on a message from the person it
    was actually waiting for.

    Same two rules as its mirror, for the same reasons: the reply closes loops on ITS OWN thread
    (answering one conversation must not mark every other one answered) plus loops with no thread
    identity at all, and only loops opened BEFORE the reply — a message cannot answer a question
    asked after it.
    """
    return conn.execute(text(
        "update open_loops set status='closed', closed_at=:at, closed_by_event=:ev "
        "where org_id=:o and awaited_from_node_id=:n and status='open' and opened_at <= :at "
        "and (thread_id = :t or thread_id is null)"),
        {"o": org_id, "n": node_id, "t": thread_id, "at": at, "ev": event_id}).rowcount


def close_loops_for_reply(conn, *, org_id: str, subject_node_id: str,
                          thread_id: str | None, event_id: str, at: datetime) -> int:
    """OUR outbound reply closes this person's open loops on ITS thread — and only its thread.

    Answering one conversation must not mark every other conversation answered (the same rule
    the ball_in_court thread mirror already follows). The one widening: a loop with NO thread
    identity (person-wide ask) is closed by any direct reply to that person, because a reply is
    the best completion evidence such a loop can ever have. Only loops opened BEFORE the reply
    close — a reply cannot answer a question that has not been asked yet.
    """
    result = conn.execute(text(
        "update open_loops set status='closed', closed_at=:at, closed_by_event=:ev "
        "where org_id=:o and subject_node_id=:s and status='open' and opened_at <= :at "
        "and (thread_id = :t or thread_id is null)"),
        {"o": org_id, "s": subject_node_id, "t": thread_id, "at": at, "ev": event_id})
    return result.rowcount


def open_loop_counts(conn, org_id: str) -> dict[str, int]:
    """Open loops per subject, one query — the reasoning sweep's bulk read."""
    return {r.subject_node_id: r.n for r in conn.execute(text(
        "select subject_node_id, count(*) as n from open_loops "
        "where org_id=:o and status='open' group by 1"), {"o": org_id})}


__all__ = ["close_loops_for_reply", "open_loop_counts", "record_ask"]
