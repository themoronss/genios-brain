"""L1.1-U1 · the coverage DECLARATION — the group law, computed once per sweep, per org.

`coverage/model.py` has always computed the right answer. Nothing ever asked it. `coverage_fn`
appeared at five sites, all five inside `capture/pipeline.py`, and the three real capture entries
passed nothing — so `GatedEvent.coverage_ready` was `None` on 100% of events ever produced while
the model that could have said `True` sat one import away.

This module is the missing middle. It answers one question — *what can GeniOS see for this org,
right now* — ONCE, for every registered domain at the same time, and hands back a plain callable
`domain -> verdict` that the pipeline can invoke per event at the cost of a dict lookup. Computing
per event would put a `connections` query on the ingestion path of every message; computing per
sweep puts it on the path of every sweep, which is where a fact about the tenant's SOURCES belongs.

**What "coverage" licenses.** It is the difference between *"this customer has no support
tickets"* and *"we have no source that could carry a support ticket."* The first is a finding; the
second is a blind spot wearing a finding's clothes. Every negative inference downstream — "they
never replied", "no meeting was booked", "the invoice was never sent" — is only safe when a
declaration says the channel that would have carried the evidence is connected and flowing.

**Two functions moved here out of `api/routes.py`.** `_connected_capabilities` and
`_company_knowledge_count` were private helpers of the HTTP layer, which meant the only way to get
a coverage answer was to make a web request. A capture sweep cannot make a web request to itself,
so the capture path simply had no route to the answer. They are the same computation either way;
the API now calls this module rather than owning a second copy.

No clock is read here: `computed_at` is a parameter, so a declaration replays identically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping

from genios_engine.capture.coverage.model import (PACK_REQUIREMENTS, capability_of,
                                                  compute_coverage)
from genios_engine.contracts.connection import Connection

#: The three states a capability can be in for one org. `stale` is the honest middle: the tenant
#: HAS the source, and it is not currently flowing, which is neither "we can see this" nor "we
#: never could". `compute_coverage` treats anything but `fresh` as missing, so a paused mailbox
#: withdraws the licence to infer silence — which is exactly right, because a paused connector
#: produces the same empty result set as a connected one with nothing in it.
FRESH = "fresh"
STALE = "stale"
NOT_CONNECTED = "not_connected"

#: Connection status -> capability freshness. A status nobody has defined contributes nothing
#: rather than defaulting to `fresh`: an unknown state is not evidence that we can see.
_STATUS_FRESHNESS: Mapping[str, str] = {"connected": FRESH, "paused": STALE}


def connected_capabilities(connections: Iterable[Connection], *,
                           org_id: str) -> dict[str, str]:
    """Which CAPABILITIES this org's connections satisfy, and how fresh each one is.

    Absorbed from `api/routes.py:_connected_capabilities`, with two behaviours made explicit
    that were implicit there:

    * the org filter is a REQUIRED keyword rather than a caller's `if` inside a loop — this
      function is handed cross-tenant lists (`list_active()` returns every org's connections)
      and a forgotten filter would declare one tenant's coverage from another tenant's sources;
    * `fresh` wins over `stale` when two connections satisfy the same capability. A tenant with
      Gmail connected and a second, paused mailbox can still see communication; taking whichever
      row the iteration happened to reach last would make coverage depend on row order.

    Packs declare capabilities, never vendor names, so a tenant on HubSpot and a tenant on a
    client Postgres both satisfy `crm` without either name appearing in a requirement.
    """
    out: dict[str, str] = {}
    for connection in connections:
        if connection.org_id != org_id:
            continue
        capability = capability_of(connection.source_type)
        if capability is None:
            continue
        freshness = _STATUS_FRESHNESS.get(connection.status)
        if freshness is None:
            continue
        if out.get(capability) != FRESH:
            out[capability] = freshness
    return out


def company_knowledge_count(engine, org_id: str) -> int:
    """Distinct assertions this org has WRITTEN about itself — policies, pricing, SOPs.

    Absorbed from `api/routes.py:_company_knowledge_count`. NON-APP evidence: it never satisfies
    a live-signal capability (writing a refund policy yields no email data, so it cannot license
    "they never replied"), but it is real context and the dashboard used to report "not
    connected" no matter how much canon a tenant had written.

    `engine` may be None — a deployment with no database is a legitimate state, not an error —
    and a query failure returns 0 rather than raising: coverage is a hint on the capture path,
    and a hint that can abort an ingestion is worse than a hint that is conservative.
    """
    if engine is None:
        return 0
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return int(conn.execute(text(
                "select count(distinct source_object_id) from source_events "
                "where org_id=:o and source='internal'"), {"o": org_id}).scalar() or 0)
    except Exception:      # noqa: BLE001 — an unreadable count is 'none known', never a 500
        return 0


@dataclass(frozen=True)
class CoverageDeclaration:
    """One org's machine-readable statement of what GeniOS can and cannot see, at one instant.

    `domains` holds a verdict for EVERY registered domain, not just the one a caller asked
    about, because the expensive inputs (the connection set, the canon count) are shared and the
    per-domain arithmetic is free. That is what makes `for_domain` a lookup rather than a query,
    and it is why a sweep of ten thousand events costs one declaration.
    """

    org_id: str
    computed_at: datetime
    connected: Mapping[str, str]
    company_knowledge_count: int
    domains: Mapping[str, Mapping[str, Any]]

    def for_domain(self, domain: str) -> dict[str, Any]:
        """The verdict for one domain — the exact shape `coverage_fn` is expected to return.

        An UNREGISTERED domain is not a lookup miss to be papered over with a default: it is
        computed on the spot, and `compute_coverage` fails closed for it with
        `coverage_state='unknown_domain'` and every readiness predicate False. "We have never
        defined what a complete picture for this domain looks like" is a different sentence from
        "this domain is under-connected", and both are different from a KeyError.
        """
        held = self.domains.get(domain)
        if held is not None:
            return dict(held)
        return compute_coverage(domain, dict(self.connected),
                                company_knowledge_count=self.company_knowledge_count)

    def ready(self, domain: str) -> bool:
        """The one bit `GatedEvent.coverage_ready` carries."""
        return bool(self.for_domain(domain).get("coverage_ready"))


def declare_coverage(*, org_id: str, connections: Iterable[Connection],
                     computed_at: datetime,
                     company_knowledge_count: int = 0) -> CoverageDeclaration:
    """L1.1-U1 — one org's coverage across every registered domain, from its connection set.

    Pure: the connections and the canon count are arguments, and `computed_at` is a parameter
    rather than a clock read, so a declaration made during a replay of a March sweep is stamped
    March. A declaration that stamped itself `now()` would make every replay a different row in
    `source_coverage` and turn "what did we believe we could see when we decided this" into an
    unanswerable question.
    """
    connected = connected_capabilities(connections, org_id=org_id)
    domains = {
        domain: compute_coverage(domain, connected,
                                 company_knowledge_count=company_knowledge_count)
        for domain in PACK_REQUIREMENTS}
    return CoverageDeclaration(org_id=org_id, computed_at=computed_at, connected=connected,
                               company_knowledge_count=company_knowledge_count, domains=domains)


#: What the capture entries are injected with: `domain -> verdict`. Named so the four call sites
#: and the wiring factory all say the same word for the same thing.
CoverageFn = Callable[[str], Mapping[str, Any]]


__all__ = ["FRESH", "STALE", "NOT_CONNECTED", "CoverageDeclaration", "CoverageFn",
           "company_knowledge_count", "connected_capabilities", "declare_coverage"]
