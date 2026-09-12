"""Which cards a SEAT may read — one predicate for every surface a member uses.

A card reaches a seat two ways, both written by L5 and nothing else:

  * `cards.assignee` — the seat `deliver/router.resolve_assignee` routed it to;
  * `card_recipients` (0135) — a seat whose declared responsibility covers a slice the card names.

That is the whole of a member's reach. An UNASSIGNED card is not theirs: routing sends every card
it cannot place to the admin queue (0008: "everyone else falls through to the admin queue"), and a
member credential reading it would be reading the admin's queue. Owner and admin sessions, and an
org-level key, keep the org-wide read they always had; an agent-bound key keeps its own lane plus
the unclaimed loops (its existing rule, unchanged here).
"""
from __future__ import annotations

from sqlalchemy import text

#: The member reach, as SQL over a `cards k` alias with the seat bound as `:seat`.
SEAT_REACH_SQL = ("(k.assignee = :seat or exists (select 1 from card_recipients cr "
                  "where cr.org_id = k.org_id and cr.card_id = k.card_id and cr.seat_id = :seat))")


def card_reaches_seat(conn, org_id: str, card_id: str, seat_id: str | None) -> bool:
    """Is this card routed to this seat, by assignment or by declared responsibility?"""
    if not seat_id or not card_id:
        return False
    return conn.execute(text(
        "select 1 from cards k where k.org_id = :o and k.card_id = :c and " + SEAT_REACH_SQL),
        {"o": org_id, "c": card_id, "seat": seat_id}).first() is not None


def may_touch_card(conn, ctx, card_id: str, assignee: str | None) -> bool:
    """May this credential read or act on this card?

    Full-scope sessions (owner / tenant admin / legacy org key) read the org queue. A member reads
    its seat's reach. Any other scoped credential keeps the rule it always had: its own card or an
    unclaimed one.
    """
    if ctx.scopes is None:
        return True
    if getattr(ctx, "is_member", False):
        return card_reaches_seat(conn, ctx.org_id, card_id, ctx.seat_id)
    actor = ctx.actor_id or ctx.agent_id
    return assignee is None or assignee in {actor, ctx.agent_id}


__all__ = ["SEAT_REACH_SQL", "card_reaches_seat", "may_touch_card"]
