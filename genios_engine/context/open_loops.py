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
               thread_id: str | None, event_id: str, at: datetime) -> str:
    """An ask-class observation opens its loop — or bumps / reopens the existing one.

    A follow-up repeating the ask is the SAME loop (`ask_count` grows, `last_seen_at` moves); an
    ask arriving after we answered REOPENS it, because their asking again is direct evidence our
    answer did not resolve it.
    """
    loop = open_loop_id(org_id=org_id, subject_node_id=subject_node_id, kind=kind,
                        thread_id=thread_id)
    conn.execute(text(
        "insert into open_loops (org_id, loop_id, subject_node_id, kind, thread_id, "
        "status, opened_at, last_seen_at, opened_by_event) "
        "values (:o, :l, :s, :k, :t, 'open', :at, :at, :ev) "
        "on conflict (org_id, loop_id) do update set "
        "  ask_count = open_loops.ask_count + 1, "
        # CASE, not greatest(): same result, and it runs on the sqlite the tests use.
        "  last_seen_at = case when excluded.last_seen_at > open_loops.last_seen_at "
        "                 then excluded.last_seen_at else open_loops.last_seen_at end, "
        "  status = case when open_loops.status = 'closed' "
        "                 and excluded.last_seen_at > open_loops.closed_at "
        "                then 'open' else open_loops.status end"),
        {"o": org_id, "l": loop, "s": subject_node_id, "k": kind, "t": thread_id,
         "at": at, "ev": event_id})
    return loop


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
