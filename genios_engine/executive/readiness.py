"""M12.C1.U02 · why this tenant cannot be routed to — the diagnosis L4 has never been able to give.

⛔ WHAT WAS WRONG. `platform/receipts.py` carries 23 receipts across every layer and **not one is about
organisation data.** So a tenant with a compiled pack, a live activation row, a full graph and 23 green
receipts can still be completely unroutable, and nothing says so. That is the state the pilot is in, and
it is the whole reason `executive/` "examines nothing every tick".

`test_a_tenant_nobody_feeds_is_not_ready` made the identical argument one layer down, in its own words:

    "Every other receipt can pass while a tenant's feed is dead. ... seventeen receipts still say PASS.
     Nothing said the feed had stopped."

Organisation data is the same failure, one layer up.

⛔ THREE STATES, NOT TWO, AND THAT IS THE DESIGN.

    ready    present and usable
    missing  absent, and NAMED, with what to do about it
    unknown  the query could not run — NOT the same as missing

*"Nobody has filed a reporting line"* and *"we could not read the table"* call for opposite actions, and
this programme has been caught twice by exactly that conflation: `no_model_wired` in L1 (632 failures
that were one model-free lane) and the graph-revision guard in L3. The rule both produced:
**a count without its dimension is not a measurement.**

⛔ AND IT NAMES THE FIX, NOT ONLY THE GAP. *"seats: missing"* sends somebody hunting through five tables.
*"No active seat has a channel — without one, every plan L4 authors is written and never delivered"* is a
sentence an operator can act on. A readiness report nobody can act on is a status page.

PURE BY CONSTRUCTION. Counts come in, verdicts come out. A readiness check that could itself fail on the
network would be one more thing to diagnose at the moment somebody is already diagnosing something.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# The requirement names and their SQL live in the floor, because `platform/receipts.py` needs the same
# three queries and the floor may not import a layer. See `platform/org_readiness_sql.py` for why.
from genios_engine.platform.org_readiness_sql import (CHANNELS, COUNT_SQL, REPORTING_LINE,
                                                      REQUIREMENTS, SEATS)

READY = "ready"
MISSING = "missing"
UNKNOWN = "unknown"
STATES = (READY, MISSING, UNKNOWN)

#: ⛔ THE SENTENCE AN OPERATOR ACTS ON. Kept as data beside the requirement rather than formatted at the
#: call site, so the readiness page, the receipt's `detail` and the admin door cannot drift about what
#: the consequence is.
_CONSEQUENCE: Mapping[str, str] = {
    SEATS: ("no active seat exists, so there is nobody to assign an owner to and every execution plan "
            "is refused before it is written"),
    REPORTING_LINE: ("no seat has a manager, so rung 7 of the escalation ladder (escalate -> manager) "
                     "climbs into nothing and a stalled item is never escalated"),
    # ⛔ ORG-LEVEL. `org_channels` is keyed `(org_id, channel)` and there is no per-seat channel in the
    # schema, so this cannot say "seat X is unreachable" — only that the tenant has no way out at all.
    # Saying more than the data supports is the failure every other sentence in this file guards.
    CHANNELS: ("the tenant has no active channel, so every plan L4 authors is written and never "
               "delivered -- the work happens and nobody hears about it"),
}

_FIX: Mapping[str, str] = {
    SEATS: "load the org's seats (org_seats), marking the active ones",
    REPORTING_LINE: ("set org_seats.manager_seat_id for the standing line, or file a dated reports_to "
                     "responsibility for an acting term"),
    CHANNELS: "add an active row to org_channels so communication has somewhere to send",
}


@dataclass(frozen=True, slots=True)
class Requirement:
    """One thing L4 needs, its state, and — when it is missing — what that costs and how to fix it."""

    name: str
    state: str
    detail: str

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError(f"{self.state!r} is not a readiness state; the three are {list(STATES)}")
        if not self.detail.strip():
            # ⛔ A state with no sentence is a status page entry. The whole point of this module is that
            # a reader knows what to do next, and an empty detail silently removes that.
            raise ValueError(f"{self.name} has no detail; a readiness verdict must say something")

    @property
    def blocks_routing(self) -> bool:
        """⛔ Only `missing` blocks. `unknown` does NOT — we do not know that it is absent, and treating
        an unreadable table as an empty one is how a working tenant gets reported as unconfigured."""
        return self.state == MISSING


@dataclass(frozen=True, slots=True)
class Readiness:
    """The whole answer for one tenant."""

    org_id: str
    requirements: tuple[Requirement, ...]

    @property
    def routable(self) -> bool:
        """⛔ True only when nothing is MISSING. An `unknown` leaves this False as well, because we
        cannot claim a tenant is routable on evidence we could not read."""
        return all(r.state == READY for r in self.requirements)

    @property
    def blocked_by(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.requirements if r.blocks_routing)

    @property
    def unmeasured(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.requirements if r.state == UNKNOWN)

    def explain(self) -> str:
        """One line for an operator. Never empty, and never the same for two different verdicts."""
        if self.routable:
            return f"{self.org_id} is routable: seats, a reporting line and channels are all present"
        parts = []
        if self.blocked_by:
            parts.append("blocked by " + ", ".join(self.blocked_by))
        if self.unmeasured:
            # ⛔ Said separately. Folding it into "blocked" would claim we know something is absent.
            parts.append("could not measure " + ", ".join(self.unmeasured))
        return f"{self.org_id} is not routable: " + "; ".join(parts)


def _verdict(name: str, count: int | None) -> Requirement:
    """`None` means the query could not run. Zero means it ran and found nothing.

    ⛔ The difference between those two is the reason this module exists.
    """
    if count is None:
        return Requirement(name, UNKNOWN,
                           f"could not read {name} for this tenant; this is NOT the same as {name} "
                           f"being absent, and it must not be reported as such")
    if count > 0:
        return Requirement(name, READY, f"{count} {name} present")
    return Requirement(name, MISSING, f"{_CONSEQUENCE[name]}. Fix: {_FIX[name]}")


def assess(org_id: str, *, seats: int | None, reporting_line: int | None,
           channels: int | None) -> Readiness:
    """Judge one tenant from three counts. Pure — no database, no clock, no network.

    Each count is "how many rows satisfy this requirement", or `None` when the query could not run.
    """
    if not str(org_id).strip():
        raise ValueError("a readiness verdict belongs to a tenant; org_id is empty")
    return Readiness(org_id=str(org_id), requirements=(
        _verdict(SEATS, seats),
        _verdict(REPORTING_LINE, reporting_line),
        _verdict(CHANNELS, channels),
    ))


def read(conn, org_id: str) -> Readiness:
    """`assess` against a live connection. Every failed read becomes `unknown`, never `missing`.

    Each count is caught on its own, so one unreadable table does not turn the other two into
    `unknown` — a per-row seam, the same rule the rest of this codebase applies to a batch.
    """
    from sqlalchemy import text

    counts: dict[str, int | None] = {}
    for name, sql in COUNT_SQL.items():
        try:
            counts[name] = int(conn.execute(text(sql), {"org": org_id}).scalar() or 0)
        except Exception:      # noqa: BLE001 — an unreadable count is UNKNOWN, not zero
            counts[name] = None
    return assess(org_id, seats=counts[SEATS], reporting_line=counts[REPORTING_LINE],
                  channels=counts[CHANNELS])


__all__ = ["CHANNELS", "COUNT_SQL", "MISSING", "READY", "REPORTING_LINE", "REQUIREMENTS", "SEATS",
           "STATES", "UNKNOWN", "Readiness", "Requirement", "assess", "read"]
