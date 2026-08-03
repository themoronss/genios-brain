from __future__ import annotations

from datetime import timedelta

from sqlalchemy import text

# E3 · Delivery Router (§5.13). One card, one owner, one push — deterministic and ordered:
#   rule 1  entity relationship/deal owner → that seat
#   rule 2  else the triggering commitment's actor, IFF internal AND an active seat
#   rule 3  else the admin queue, visible as 'unrouted' (never a silent drop)
# Budget (7/day) is evaluated per assignee at delivery time; a reassigned card counts against the
# new owner only. 'unrouted' cards don't consume anyone's budget until an admin claims them.


def _active_seat(c, org_id, seat_ref) -> str | None:
    """seat_ref may be a seat_id or an email; return the seat_id iff it is an active seat."""
    if not seat_ref:
        return None
    r = c.execute(text(
        "select seat_id from org_seats where org_id=:o and active "
        "and (seat_id=:s or lower(email)=lower(:s)) limit 1"),
        {"o": org_id, "s": str(seat_ref)}).first()
    return r.seat_id if r else None


def resolve_assignee(store, org_id: str, node_facts: dict, node_attrs: dict) -> tuple[str | None, str]:
    """Return (seat_id | None, resolved_rule). None → admin queue / unrouted."""
    def fval(field):
        f = node_facts.get(field)
        return f.get("value") if isinstance(f, dict) else None

    with store.engine.connect() as c:
        # rule 1 — explicit deal/relationship owner (owner is authoritative even if off-seat,
        # but we only auto-push to an ACTIVE seat; an off-seat owner falls through to admin).
        owner = fval("deal.owner") or fval("relationship.owner") or (node_attrs or {}).get("owner")
        seat = _active_seat(c, org_id, owner)
        if seat:
            return seat, "rule1_owner"

        # rule 2 — commitment actor, only if internal AND an active seat (Finding C precision fix)
        actor = fval("commitment.actor")
        seat = _active_seat(c, org_id, actor)
        if seat:
            return seat, "rule2_actor"

    return None, "rule3_unrouted"


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
