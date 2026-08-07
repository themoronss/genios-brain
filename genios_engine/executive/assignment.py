"""Layer 5 · Unit — Owner resolution.  *Who* holds this commitment.

This is the canonical home for the question "who?".  It used to live in ``deliver/router.py``,
which made Layer 6 the authority on ownership — and Layer 6 is supposed to answer *how it
travels*, not *whose problem it is*.  Ownership is part of the commitment: an execution object
with no owner is not a plan, it is a wish.  So the authority moved down here and
``deliver/router.py`` now delegates upward-in-time, downward-in-layers, which is the direction
the topology ratchet allows (``tests/test_layer_topology.py``: 5 may not import 6; 6 may import
5, exactly as ``executive/validate.py`` already documents).

The rules are unchanged in behaviour, deliberately.  Moving code and changing it in the same
step is how a refactor turns into an outage:

  rule 1  the entity's declared owner (deal / relationship / node attribute) → that seat
  rule 2  otherwise the triggering commitment's actor, if it maps to an active seat
  rule 3  otherwise nobody — the admin queue, visible as ``unrouted``, never a silent drop

Rule 3 matters more than it looks.  An unroutable commitment still exists, is still tracked,
still escalates and still shows up in coverage reporting.  The alternative — dropping it — is
how a system quietly stops mentioning the accounts nobody owns, which are precisely the
accounts most likely to be lost.

**Pure core, injected directory.**  The resolution logic takes a ``SeatDirectory`` rather than a
database handle, so the whole of it is testable without Postgres (the CI suite has no service
containers).  ``PgSeatDirectory`` is the production implementation and the only part that
touches SQL.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from genios_engine.contracts.execution import AudienceClass

ASSIGNMENT_VERSION = "assign.v1"

#: Owner fields in priority order.  Deal ownership beats relationship ownership because a deal
#: is the narrower, more recently asserted claim; the generic node attribute is last because it
#: is the least likely to have been maintained.
OWNER_FIELDS: tuple[str, ...] = ("deal.owner", "relationship.owner")
ACTOR_FIELD = "commitment.actor"


@dataclass(frozen=True, slots=True)
class Assignment:
    """Who owns it, in what capacity, and by which rule.

    ``reason_code`` is not optional.  Ownership disputes are the most common support question a
    system like this generates, and "rule2_actor" answers it in one word where a bare seat id
    answers nothing at all.
    """

    seat_id: str | None
    audience: AudienceClass
    reason_code: str

    @property
    def routed(self) -> bool:
        return self.seat_id is not None


@runtime_checkable
class SeatDirectory(Protocol):
    """The org's people, as much of them as GeniOS actually knows.

    Kept to three questions on purpose.  A richer directory abstraction would invite ownership
    logic to grow features nobody asked for; these three are what the rules and the escalation
    ladder genuinely need.
    """

    def active_seat(self, seat_ref: str | None) -> str | None:
        """Resolve a seat id *or* an email to an active seat id, or None."""

    def manager_of(self, seat_id: str) -> str | None:
        """The seat one level up, or None when the org has published no reporting line."""

    def admins(self) -> tuple[str, ...]:
        """Active admin seats, in a stable order.  The escalation floor."""


@dataclass(frozen=True, slots=True)
class StaticSeatDirectory:
    """An in-memory directory — the whole point of the protocol.

    Used by the test suite and by ``why-not`` style explanations, where reconstructing a routing
    decision must not require the live org to still look the way it did that day.
    """

    seats: Mapping[str, Mapping[str, Any]]

    def active_seat(self, seat_ref: str | None) -> str | None:
        if not seat_ref:
            return None
        needle = str(seat_ref).strip().lower()
        for seat_id, row in self.seats.items():
            if not row.get("active", True):
                continue
            if seat_id.lower() == needle or str(row.get("email", "")).lower() == needle:
                return seat_id
        return None

    def manager_of(self, seat_id: str) -> str | None:
        row = self.seats.get(seat_id) or {}
        return self.active_seat(row.get("manager_seat_id"))

    def admins(self) -> tuple[str, ...]:
        return tuple(sorted(seat_id for seat_id, row in self.seats.items()
                            if row.get("active", True) and row.get("role") == "admin"))


def _fact_value(facts: Mapping[str, Any] | None, field: str) -> Any:
    """Read a typed L2 fact.

    Facts arrive as ``{field: {"value": …, "confidence": …}}`` from the graph and occasionally as
    plain scalars from projections and tests.  Accepting both here keeps every caller from
    reimplementing the same two-line unwrap slightly differently.
    """
    entry = (facts or {}).get(field)
    if isinstance(entry, Mapping):
        return entry.get("value")
    return entry


def resolve_owner(*, facts: Mapping[str, Any] | None, attrs: Mapping[str, Any] | None,
                  directory: SeatDirectory) -> Assignment:
    """The three ordered rules, and nothing else.

    Note what is *not* here: no load balancing, no round-robin, no "assign to whoever is least
    busy".  Those would make the same commitment land on different people on different days,
    and an owner who cannot predict what reaches them stops trusting the queue entirely.
    """
    for field in OWNER_FIELDS:
        seat = directory.active_seat(_fact_value(facts, field))
        if seat:
            return Assignment(seat, AudienceClass.OWNER, "rule1_owner")
    seat = directory.active_seat((attrs or {}).get("owner"))
    if seat:
        return Assignment(seat, AudienceClass.OWNER, "rule1_owner")

    # An owner recorded but off-seat (left the company, never onboarded) deliberately falls
    # through rather than being force-matched: pushing to a dead seat looks identical to
    # delivering successfully, which is the worst possible failure for a commitment.
    seat = directory.active_seat(_fact_value(facts, ACTOR_FIELD))
    if seat:
        return Assignment(seat, AudienceClass.OWNER, "rule2_actor")

    return Assignment(None, AudienceClass.ADMIN_QUEUE, "rule3_unrouted")


def resolve_escalation_target(*, audience: AudienceClass, owner_seat: str | None,
                              directory: SeatDirectory) -> Assignment:
    """Who a given rung of the ladder actually reaches, today.

    Resolved at fire time rather than at planning time, because the ladder is planned once and
    may fire two weeks later — by which point the manager may have changed.  The *rung* is
    frozen (see ``EscalationStep``); the *person* is not, and conflating the two would either
    freeze a stale name or make the ladder itself unreproducible.

    Degradation is explicit at every step.  No manager published → admins.  No admins → the
    owner, with a reason code that says so, because escalating to nobody is not escalating.
    """
    if audience is AudienceClass.OWNER:
        return Assignment(owner_seat, AudienceClass.OWNER,
                          "owner" if owner_seat else "owner_unrouted")

    if audience is AudienceClass.MANAGER and owner_seat:
        manager = directory.manager_of(owner_seat)
        if manager:
            return Assignment(manager, AudienceClass.MANAGER, "manager_of_owner")

    if audience in {AudienceClass.MANAGER, AudienceClass.EXECUTIVE, AudienceClass.TEAM}:
        admins = directory.admins()
        if admins:
            return Assignment(admins[0], audience, "admin_fallback")

    if owner_seat:
        return Assignment(owner_seat, AudienceClass.OWNER, "escalation_target_unavailable")
    return Assignment(None, AudienceClass.ADMIN_QUEUE, "rule3_unrouted")


@dataclass(frozen=True, slots=True)
class PgSeatDirectory:
    """The live directory.  The only part of ownership that touches SQL.

    Holds a connection rather than an engine so a caller resolving many commitments in one sweep
    pays for one connection, not one per commitment — and so ownership can be resolved inside
    the same transaction that writes the execution row.
    """

    conn: Any
    org_id: str

    def active_seat(self, seat_ref: str | None) -> str | None:
        if not seat_ref:
            return None
        from sqlalchemy import text
        row = self.conn.execute(text(
            "select seat_id from org_seats where org_id=:o and active "
            "and (seat_id=:s or lower(email)=lower(:s)) limit 1"),
            {"o": self.org_id, "s": str(seat_ref)}).first()
        return row.seat_id if row else None

    def manager_of(self, seat_id: str) -> str | None:
        from sqlalchemy import text
        row = self.conn.execute(text(
            "select m.seat_id from org_seats s join org_seats m "
            "on m.org_id=s.org_id and m.seat_id=s.manager_seat_id and m.active "
            "where s.org_id=:o and s.seat_id=:s limit 1"),
            {"o": self.org_id, "s": seat_id}).first()
        return row.seat_id if row else None

    def admins(self) -> tuple[str, ...]:
        from sqlalchemy import text
        rows = self.conn.execute(text(
            "select seat_id from org_seats where org_id=:o and active and role='admin' "
            "order by seat_id"), {"o": self.org_id}).fetchall()
        return tuple(row.seat_id for row in rows)


__all__ = ["ACTOR_FIELD", "ASSIGNMENT_VERSION", "OWNER_FIELDS", "Assignment", "PgSeatDirectory",
           "SeatDirectory", "StaticSeatDirectory", "resolve_escalation_target", "resolve_owner"]
