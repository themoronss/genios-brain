"""The three counts that decide whether a tenant can be routed to — SQL only, no judgement.

⛔ WHY THIS LIVES IN `platform/` AND NOT IN `executive/`. Two callers need the same three queries: the
readiness verdict in `executive/readiness.py` (layer 5) and the health receipts in
`platform/receipts.py` (the floor). Duplicating them would let one drift from the other, and this
module's neighbour states the rule for itself: *"One list of claims, two surfaces, so the release gate
and the operator dashboard cannot drift apart about what 'ready' means."*

Putting them in `executive/` would have made the floor import a layer — `platform -> executive` — which
the topology test does not catch, because `platform` is cross-cutting and exempt. An unchecked upward
import is not a safe one; it is one nothing fails the build on. So the SQL sits at the bottom and both
callers reach DOWN for it.

⛔ NOTHING HERE DECIDES ANYTHING. Three strings and three names. The verdict — ready, missing, or the
third state `unknown` — belongs to `executive/readiness.py`, because "what does this count mean" is a
judgement and the floor holds no business meaning.
"""

from __future__ import annotations

from collections.abc import Mapping

SEATS = "seats"
REPORTING_LINE = "reporting_line"
CHANNELS = "channels"

#: Ordered by what a person should fix first: the seats, then the line between them, then how to reach
#: them. A reader who fixes channels before seats has fixed nothing.
REQUIREMENTS: tuple[str, ...] = (SEATS, REPORTING_LINE, CHANNELS)

#: Tenant-scoped, always. Every one of these is a question ABOUT A TENANT, so none may run unfiltered:
#: answering it fleet-wide would report one tenant's seats on another's readiness page — the exact
#: failure `Receipt.fleet_wide` was declared to prevent.
COUNT_SQL: Mapping[str, str] = {
    SEATS: "select count(*) from org_seats where org_id = :org and active",
    REPORTING_LINE: ("select count(*) from org_seats s join org_seats m "
                     "on m.org_id = s.org_id and m.seat_id = s.manager_seat_id and m.active "
                     "where s.org_id = :org and s.active"),
    # ⛔ ORG-LEVEL, NOT PER-SEAT — and the first version of this file got it wrong. `org_channels` is
    # keyed `(org_id, channel)`; `org_seats` has no `channel` column at all (see migration 0008, and
    # 0041 which added only `manager_seat_id`). A per-seat query here would have failed every time and
    # been reported as the third state, `unknown`, forever: a readiness check that can never measure
    # one of its three requirements is worse than one that admits it has two.
    CHANNELS: "select count(*) from org_channels where org_id = :org and active",
}

#: The same three questions with no tenant filter, for the fleet-wide readiness run. Separate constants
#: rather than string surgery on the ones above: a filter removed by `.replace()` is a filter nobody can
#: see was removed.
COUNT_SQL_FLEET: Mapping[str, str] = {
    SEATS: "select count(*) from org_seats where active",
    REPORTING_LINE: ("select count(*) from org_seats s join org_seats m "
                     "on m.org_id = s.org_id and m.seat_id = s.manager_seat_id and m.active "
                     "where s.active"),
    CHANNELS: "select count(*) from org_channels where active",
}

__all__ = ["CHANNELS", "COUNT_SQL", "COUNT_SQL_FLEET", "REPORTING_LINE", "REQUIREMENTS", "SEATS"]
