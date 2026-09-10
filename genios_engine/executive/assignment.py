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
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from genios_engine.contracts.execution import AudienceClass

ASSIGNMENT_VERSION = "assign.v1"

#: Owner fields in priority order.  Deal ownership beats relationship ownership because a deal
#: is the narrower, more recently asserted claim; the generic node attribute is last because it
#: is the least likely to have been maintained.
OWNER_FIELDS: tuple[str, ...] = ("deal.owner", "relationship.owner")
#: WHO MADE THE PROMISE. `commitment.actor` until now — a name that appears NOWHERE in the
#: corpus vocabulary and had no writer anywhere, so Rule 2 never fired. `commitment.owner` is
#: the name `Domain Expertise/_schema/vocabulary.yaml` has tracked as a declared-but-unwritten
#: ask, and `context/pipeline.py` now writes it beside the `owns` edge it was already writing.
#:
#: The old name is kept as a second candidate rather than deleted: it costs one dictionary
#: lookup, and a tenant whose pipeline predates the change has no `commitment.owner` on rows
#: already in the graph. Neither is invented — both are read, and absent stays absent.
ACTOR_FIELDS: tuple[str, ...] = ("commitment.owner", "commitment.actor")


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
    #: Who SEES this when nobody OWNS it.
    #:
    #: `seat_id` was answering two different questions at once — "who is accountable for this"
    #: and "who should it be shown to" — and answering `None` to both. Owning is what makes a
    #: nudge or an escalation legitimate, and forcing an owner onto an unowned commitment is the
    #: mistake this module deliberately refuses (see rule 2's comment). But BEING SHOWN it needs
    #: no such claim, and conflating the two is why all 43 live cards carry `assignee = NULL`:
    #: invisible, undeliverable, and excluded from every per-recipient budget.
    #:
    #: So an unowned card goes to the admin queue as a RECIPIENT while `routed` stays False and
    #: the escalation ladder stays silent. Tracked but never nudged — still true, and now also
    #: visible.
    queue_seat: str | None = None

    @property
    def routed(self) -> bool:
        """Does somebody OWN this? Deliberately not "can it be delivered" — see `queue_seat`."""
        return self.seat_id is not None

    @property
    def recipient(self) -> str | None:
        """Who the card is delivered to: its owner, or the queue that triages unowned work."""
        return self.seat_id or self.queue_seat


#: The one `scope_kind` the ENGINE gives meaning to. Every other kind is the tenant's own word
#: and this module has no opinion about it — a `region`, a `ward`, a `depot` mean whatever the
#: business means. `reports_to` is different because the escalation ladder climbs it, so it is
#: named here rather than left free text, and `scope_key` holds the manager's seat id or email.
REPORTS_TO = "reports_to"


@dataclass(frozen=True, slots=True)
class Responsibility:
    """One named slice of the business one person answers for, over one interval.

    WHAT IT IS NOT is the important half: this says a card is YOURS, never that you may SIGN
    it. `authority_rules` answers permission, is dated and source-ranked, and a second table
    that also implied it would be two answers to one question. A regional manager owns the
    region and cannot sign the contract.
    """

    seat_id: str
    scope_kind: str
    scope_key: str
    accountability: str = "owns"
    source: str = "admin_declared"
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @property
    def narrows(self) -> bool:
        """May this responsibility be used to HIDE a situation from somebody?

        Only a declared or discovered one. An INFERRED responsibility — "this person handles
        the West's mail, probably" — may widen a view and may never narrow it: hiding a real
        situation from somebody on the strength of a guess about their job is a silent false
        negative, and the one failure this whole concept could introduce.
        """
        return self.source in ("admin_declared", "discovered")

    def applies_at(self, moment: datetime) -> bool:
        """Half-open `[valid_from, valid_until)`, the same window `AuthorityRule` uses — so an
        acting term that ended yesterday stops applying today without anybody remembering to
        delete a row."""
        if self.valid_from is not None and moment < self.valid_from:
            return False
        return not (self.valid_until is not None and moment >= self.valid_until)


@runtime_checkable
class SeatDirectory(Protocol):
    """The org's people, as much of them as GeniOS actually knows.

    Kept to three questions on purpose.  A richer directory abstraction would invite ownership
    logic to grow features nobody asked for; these three are what the rules and the escalation
    ladder genuinely need.
    """

    def active_seat(self, seat_ref: str | None) -> str | None:
        """Resolve a seat id *or* an email to an active seat id, or None."""

    def seat_for_node(self, node_id: str | None) -> str | None:
        """A GRAPH NODE id to an active seat, or None.

        The fourth question, and the reason the other three were not enough.
        `authority_rules.approver_node_id` is a graph node — deliberately, so the Founder
        Bottleneck read is a group-by on a column rather than a string match on a name — and
        nothing in the engine could turn one back into a person the delivery layer can reach.
        So the tenant knew Arjun signs anything over ₹50L and could not tell him a decision was
        waiting: authority was a real, dated, source-ranked record joined to nothing that
        decides who receives a card.
        """

    def manager_of(self, seat_id: str, at: datetime | None = None) -> str | None:
        """The seat one level up AS AT `at`, or None when the org has published no line.

        `at` is optional and defaults to now, so every existing caller is unchanged. It exists
        because `org_seats.manager_seat_id` is a single mutable column: covering the North for
        June means overwriting it on 1 June and remembering to overwrite it back on 1 July.
        Nobody remembers, so July's escalations still climb to the acting manager — and the
        June state was DESTROYED by the July write, so nothing can even say her term was meant
        to end. A `reports_to` responsibility carries its own window and simply stops applying.
        """

    def responsibilities(self, seat_id: str,
                         at: datetime | None = None) -> tuple["Responsibility", ...]:
        """WHAT this person answers for, as at `at`. Empty when they have declared nothing.

        EMPTY IS NOT AN EMPTY SCOPE. A tenant with no declarations has said nothing about who
        answers for what, and every reader must treat that as "the tenant" — which is exactly
        today's behaviour. Reading empty as "this person owns nothing" would hide every card
        from everybody on the day the table shipped.
        """

    def seats_for_scope(self, scope_kind: str, scope_key: str,
                        at: datetime | None = None) -> tuple[str, ...]:
        """Who answers for this slice of the business, as at `at`. The inverse question, and
        the one that lets a card about the West find its regional manager rather than the
        first admin."""

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

    def responsibilities(self, seat_id: str,
                         at: datetime | None = None) -> tuple[Responsibility, ...]:
        """The twin reads a `responsibilities` list off the seat row."""
        moment = at or datetime.now(timezone.utc)
        rows = (self.seats.get(seat_id) or {}).get("responsibilities") or ()
        return tuple(r for r in rows if isinstance(r, Responsibility) and r.applies_at(moment))

    def seats_for_scope(self, scope_kind: str, scope_key: str,
                        at: datetime | None = None) -> tuple[str, ...]:
        moment = at or datetime.now(timezone.utc)
        wanted = (str(scope_kind).strip().lower(), str(scope_key).strip().lower())
        return tuple(sorted(
            seat_id for seat_id, row in self.seats.items()
            if row.get("active", True)
            for r in (row.get("responsibilities") or ())
            if isinstance(r, Responsibility)
            and (r.scope_kind.strip().lower(), r.scope_key.strip().lower()) == wanted
            and r.applies_at(moment)))

    def seat_for_node(self, node_id: str | None) -> str | None:
        """The in-memory twin resolves through a `node_id` key on the seat row — the tests own
        their own graph, so there is nothing to join against."""
        if not node_id:
            return None
        for seat_id, row in self.seats.items():
            if row.get("active", True) and row.get("node_id") == node_id:
                return seat_id
        return None

    def manager_of(self, seat_id: str, at: datetime | None = None) -> str | None:
        acting = self._acting_manager(seat_id, at)
        if acting:
            return acting
        row = self.seats.get(seat_id) or {}
        return self.active_seat(row.get("manager_seat_id"))

    def _acting_manager(self, seat_id: str, at: datetime | None) -> str | None:
        """A dated `reports_to` responsibility, if one is in force."""
        for r in self.responsibilities(seat_id, at):
            if r.scope_kind == REPORTS_TO and r.accountability == "covers":
                return self.active_seat(r.scope_key)
        return None

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
    for field in ACTOR_FIELDS:
        seat = directory.active_seat(_fact_value(facts, field))
        if seat:
            return Assignment(seat, AudienceClass.OWNER, "rule2_actor")

    # Rule 3 — the org's own admin. Every input above is structurally absent in production:
    # `deal.owner`/`relationship.owner` have no write_fact producer anywhere, `commitment.actor`
    # is never written as a fact, and `graph_nodes.attributes` is never populated at all. So this
    # returned `None` for every card ever built — all 43 carry `assignee = NULL`, `router.
    # budget_full` short-circuits to False for every one of them, and the executive bridge's
    # `assignee is not null` predicate matches zero rows.
    #
    # `ADMIN_QUEUE` was already the declared audience of this branch, and `admins()` already
    # existed to resolve it — it was simply only ever called from the ESCALATION path. A card
    # nobody is named on belongs to whoever runs the account, which for a single-founder tenant
    # is the founder. That is not load balancing (see above); it is the same deterministic seat
    # every time.
    admins = directory.admins()
    return Assignment(None, AudienceClass.ADMIN_QUEUE,
                      "rule3_unrouted" if not admins else "rule3_admin_queue",
                      queue_seat=admins[0] if admins else None)


def resolve_approver_seat(answer, *, directory: SeatDirectory) -> str | None:
    """The seat that must sign, from an `AuthorityAnswer`, or None.

    ONLY AN ENFORCEABLE ANSWER NAMES ANYBODY. `AuthorityView.resolve` returns three outcomes,
    not two, and the distinction is load-bearing: `suggested` means only OBSERVED BEHAVIOUR
    matched and a human must confirm before anybody signs, `no_authority_rule` means the org
    holds no rule — which is NOT "anyone may approve". Routing a card to a merely suggested
    approver would turn an unconfirmed observation into an instruction, which is the boundary
    `runtime_brains._validate_axis` raises to protect one layer down.

    None is a real answer and the caller must keep it. `requires_approval` stays TRUE when
    nobody can be named — a card that says "this needs sign-off" and cannot say whose is less
    useful than one that can, and far better than one that quietly drops the requirement.
    """
    # `enforced`, NOT `enforceable`. The property's own docstring says to read it and never
    # `rule is not None`: *"the two agree today because `__post_init__` makes them, and this one
    # says why."* Reading a name that does not exist would silently be False on every answer —
    # a guard that never fires and never says so, which is this branch's most-found defect.
    if answer is None or not getattr(answer, "enforced", False):
        return None
    # `approver_node_id` is ALREADY None on a SUGGESTED answer — *"a suggestion has a proposed
    # approver and no approver"* — so this is belt and braces rather than the only lock.
    return directory.seat_for_node(getattr(answer, "approver_node_id", None))


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

    #: `[valid_from, valid_until)` at one instant, as SQL. Written once because both reads
    #: below need exactly the same window and two spellings of a half-open interval is how one
    #: of them comes to include the day a term ended.
    _WINDOW = ("and r.valid_from <= :at "
               "and (r.valid_until is null or r.valid_until > :at) ")

    def responsibilities(self, seat_id: str,
                         at: datetime | None = None) -> tuple[Responsibility, ...]:
        """Everything this seat answers for, at this instant."""
        from sqlalchemy import text
        moment = at or datetime.now(timezone.utc)
        try:
            rows = self.conn.execute(text(
                "select scope_kind, scope_key, accountability, source, valid_from, valid_until "
                "from seat_responsibilities r "
                "where r.org_id=:o and r.seat_id=:s " + self._WINDOW +
                "order by scope_kind, scope_key, valid_from"),
                {"o": self.org_id, "s": seat_id, "at": moment}).mappings().all()
        except Exception:      # noqa: BLE001 — see the class note: an unreadable table means
            return ()          # "declared nothing", which is today's behaviour, not a narrower one
        return tuple(Responsibility(
            seat_id=seat_id, scope_kind=r["scope_kind"], scope_key=r["scope_key"],
            accountability=r["accountability"], source=r["source"],
            valid_from=r["valid_from"], valid_until=r["valid_until"]) for r in rows)

    def seats_for_scope(self, scope_kind: str, scope_key: str,
                        at: datetime | None = None) -> tuple[str, ...]:
        """Who answers for this slice — the read that lets a card about the West find its
        regional manager instead of the first admin."""
        from sqlalchemy import text
        moment = at or datetime.now(timezone.utc)
        try:
            rows = self.conn.execute(text(
                "select distinct r.seat_id from seat_responsibilities r "
                "join org_seats s on s.org_id=r.org_id and s.seat_id=r.seat_id and s.active "
                "where r.org_id=:o and lower(r.scope_kind)=lower(:k) "
                "and lower(r.scope_key)=lower(:v) " + self._WINDOW +
                "order by r.seat_id"),
                {"o": self.org_id, "k": scope_kind, "v": scope_key, "at": moment}).all()
        except Exception:      # noqa: BLE001 — same rule
            return ()
        return tuple(r.seat_id for r in rows)

    def seat_for_node(self, node_id: str | None) -> str | None:
        """Node -> its canonical address -> an active seat. ONE statement.

        `graph_nodes.canonical_key` holds the email for a person node — `context/pipeline.py`
        creates them with `canonical_key=email` — which is exactly what `active_seat` already
        matches on. So this is the join that was missing, not a new identity concept.

        A node that is not one of our seats returns None, which is the honest answer and the
        one the caller needs: an approver the org does not employ is not somebody a card can be
        routed to, whatever the policy document says.
        """
        if not node_id:
            return None
        from sqlalchemy import text
        row = self.conn.execute(text(
            "select s.seat_id from graph_nodes n join org_seats s "
            "on s.org_id = n.org_id and s.active "
            "and lower(s.email) = lower(n.canonical_key) "
            "where n.org_id = :o and n.node_id = :n and n.valid_to is null limit 1"),
            {"o": self.org_id, "n": str(node_id)}).first()
        return row.seat_id if row else None

    def manager_of(self, seat_id: str, at: datetime | None = None) -> str | None:
        # THE DATED LINE FIRST, THEN THE COLUMN. An acting term is a `reports_to`
        # responsibility with its own window, so it stops applying on its end date without
        # anybody remembering to undo a write — and the standing line underneath survives it,
        # which is what makes "who was her manager in June?" answerable in September.
        for r in self.responsibilities(seat_id, at):
            if r.scope_kind == REPORTS_TO and r.accountability == "covers":
                seat = self.active_seat(r.scope_key)
                if seat:
                    return seat
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
