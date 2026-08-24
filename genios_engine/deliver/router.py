from __future__ import annotations

from sqlalchemy import text

from genios_engine.executive.assignment import PgSeatDirectory, resolve_owner

# E3 · Delivery Router (§5.13) — now a THIN DELEGATION.
#
# The ownership rules used to live here, which made Layer 6 the authority on who owns a
# recommendation. That was the wrong home: Layer 6 answers *how intelligence travels*, and who
# holds a commitment is part of the commitment itself, not part of its transport. The rules moved
# down to executive/assignment.py (Layer 5) and this module now calls them.
#
# The direction is legal and deliberate: deliver (6) may import executive (5); executive may never
# import deliver. tests/test_layer_topology.py enforces it, and executive/validate.py already
# documents the same pattern for the render validators.
#
# Behaviour is unchanged — same three ordered rules, same reason codes:
#   rule 1  entity relationship/deal owner → that seat
#   rule 2  else the triggering commitment's actor, IFF internal AND an active seat
#   rule 3  else the admin queue, visible as 'unrouted' (never a silent drop)
#
# Budget (7/day) stays here. It is genuinely a distribution concern: it caps how many pushes one
# person receives in a day, which is a property of the channel's politeness, not of who owns what.


def resolve_assignee(store, org_id: str, node_facts: dict,
                     node_attrs: dict) -> tuple[str | None, str]:
    """Return (recipient seat | None, resolved_rule). None → genuinely nobody to show it to.

    Reads `assignment.recipient`, not `assignment.seat_id`. Ownership and recipiency are
    different questions: an unowned card still has to be SEEN by somebody, and answering None to
    both is why every live card carries `assignee = NULL` — invisible to the push condition, to
    the executive bridge's `assignee is not null` predicate, and to the per-recipient budget.
    `routed` is unchanged, so the escalation ladder still refuses to nudge an unowned commitment.

    Kept as a function rather than replaced at every call site so the Layer 6 pipeline reads the
    same as it did before. The tuple shape is what card_builder and the tests already expect.
    """
    with store.engine.connect() as c:
        assignment = resolve_owner(facts=node_facts, attrs=node_attrs,
                                   directory=PgSeatDirectory(conn=c, org_id=org_id))
    return assignment.recipient, assignment.reason_code


def budget_full(store, org_id: str, assignee: str | None, eval_time, budget_per_day: int) -> bool:
    """Per-assignee daily push budget. Unrouted cards are parked in the admin queue, not pushed,
    so they never consume budget — return False (they always land, just without a push)."""
    if assignee is None:
        return False
    with store.engine.connect() as c:
        n = c.execute(text(
            "select count(*) from cards where org_id=:o and assignee=:a "
            "and state in ('queued','surfaced','snoozed','claimed','acted') "
            "and created_at::date = :d"),
            {"o": org_id, "a": assignee, "d": eval_time.date()}).scalar()
    return int(n or 0) >= int(budget_per_day)
