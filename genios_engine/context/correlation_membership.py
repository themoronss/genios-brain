"""Which events one reading's finding rests on, and writing that down as membership.

EXTRACTED SO BOTH READERS CAN USE IT WITHOUT A CYCLE. `outreach_situations` imports from
`support_situations`, so the writer cannot live in the first and be called from the second. It is
also a better home than either: this is one question — *what is this situation built from* — and
six modules write `context_situations`.

WHY IT EXISTS AT ALL. `gather_l1_signals` reaches Layer 1's qualified signals THROUGH
`context_correlation_members`, and a reading mints a synthetic correlation id that had no rows
there. Measured on the pilot 2026-09-15: 238 live qualified signals, all 99 correlation-member
events carrying one, and only 20 of 94 situations able to reach one — Layer 3 holding the other 73
at `QES_REQUIRED` before their content was ever examined. After wiring the first reader: 64 of 129.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text

def finding_events(conn, *, org_id: str, finding: Any) -> tuple[str, ...] | None:
    """The events one finding is actually built from. Ids, not receipts, and no writes.

    THE DERIVATION WAS ALWAYS HERE AND THE IDS WERE ALWAYS THROWN AWAY. `_finding_receipts` has
    computed this set on every finding of every sweep and immediately spent it on
    `load_event_receipts`. Nothing else could ask for it, so a reading's own provenance could not
    become its correlation membership.

    WHY THAT COST 73 CARDS. `gather_l1_signals` joins Layer 1's qualified signals THROUGH the
    correlation — *"the correlation already decided which events are one thing; the anchor is one
    node inside it"* — and a reading mints a synthetic correlation id (`outreach:{node}`,
    `stated:{hash}`, `analytic:{key}`) that has no rows in `context_correlation_members`. Measured
    on the pilot 2026-09-15: all 99 correlation-member events carry a qualified signal, and only
    20 of 94 situations can reach one. The other 74 fall back to a default importance and Layer 3
    holds them at `QES_REQUIRED` before their content is ever examined.

    THREE SOURCES, IN THIS ORDER, and the order is the point:

    * `finding.event_ids` — a group reading already KNOWS its exact scope. The seven campaign
      messages are the scope, not the two people chosen to display it, and re-deriving would
      silently enlarge it.
    * `inputs['events']` — the same answer, carried the long way by a reading that puts it there.
    * the facts themselves — every fact carries the event it was written from, so the walk is
      `graph_facts` -> `graph_source_refs`, which is how receipts have always been found.

    `()` AND `None` ARE DIFFERENT ANSWERS and the writer above depends on it: `()` is "this
    finding rests on no events", and `None` is "the graph could not be read". The first licenses
    writing no membership; the second must leave whatever membership exists alone rather than
    deleting it as absent — the same asymmetry this module's savepoint guards keep everywhere.

    Ordered and de-duplicated, because membership rows are written from it and two sweeps over an
    unchanged graph must produce the same set.
    """
    events = getattr(finding, "event_ids", None)
    if events is None:
        events = (getattr(finding, "inputs", None) or {}).get("events")
    if events is None:
        nodes = tuple(getattr(finding, "evidence_nodes", None)
                      or (getattr(finding, "concerns_node", None),))
        nodes = tuple(node for node in nodes if node)
        if not nodes:
            return ()
        try:
            with conn.begin_nested():
                events = conn.execute(text(
                    "select distinct r.event_id from graph_facts f join graph_source_refs r "
                    "on r.org_id=f.org_id and r.fact_version_id=f.fact_version_id "
                    "where f.org_id=:org and f.subject_node_id in :nodes "
                    "and f.status='active' and f.valid_to is null"
                ).bindparams(bindparam("nodes", expanding=True)),
                    {"org": org_id, "nodes": nodes}).scalars().all()
        except Exception:  # noqa: BLE001 — preserve the original writer on unavailable refinement
            return None
    return tuple(sorted({str(e) for e in (events or ()) if e}))


def declare_finding_events(conn, *, org_id: str, finding: Any,
                           correlation_id: str | None = None) -> int:
    """Write the membership a reading's own facts imply. Returns rows written.

    WHY THIS EXISTS. `gather_l1_signals` reaches Layer 1's qualified signals THROUGH
    `context_correlation_members` — its join is exactly `qualified_signals.event_id =
    context_correlation_members.event_id` — and a reading mints a synthetic correlation id
    (`outreach:{node}`, `stated:{hash}`, `analytic:trend:{node}`) that had no rows there. So the
    join matched nothing and the situation fell back to `DEFAULT_IMPORTANCE_BP`.

    MEASURED ON THE PILOT 2026-09-15, before this line existed: 238 live qualified signals, all 99
    correlation-member events carrying one, and only 20 of 94 situations able to reach one. Layer
    3 held 73 at `QES_REQUIRED` — a gate it is right to enforce — before their content was ever
    examined. Fourteen of the eighteen live situation types were in that state, which is 87% of
    the cards.

    A READING ONLY CLAIMS ITS OWN CORRELATION. A `context_correlations` row means the correlation
    ENGINE owns that id: it decided which events are one thing, and it maintains `event_count`
    beside the membership. Writing rows underneath it would enlarge somebody else's scope and
    desynchronise a counter from the rows it counts, so an owned id is skipped entirely. Real ids
    are `corr_<hex>` and readings' are colon-bearing, so the two namespaces cannot collide today
    — but the check is on OWNERSHIP rather than on the shape of the string, because a shape is a
    convention and ownership is a fact.

    AND NO COUNTER IS INVENTED. A reading's correlation has no parent row and does not gain one;
    minting one here would make a diagnostic the reason a row exists, which is the rule
    `conversion.record_conversion` states for the tenant node.

    `None` FROM THE DERIVATION WRITES NOTHING AND DELETES NOTHING. It means the graph could not be
    read, and reconciling on that would delete real membership because a query failed. Absence is
    never read as negative evidence here, the same as everywhere else in this layer.
    """
    correlation_id = str(
        correlation_id if correlation_id is not None
        else getattr(finding, "correlation_id", "") or "").strip()
    if not correlation_id:
        return 0
    events = finding_events(conn, org_id=org_id, finding=finding)
    if not events:                      # None (unreadable) and () (nothing) both write nothing
        return 0
    try:
        with conn.begin_nested():
            owned = conn.execute(text(
                "select 1 from context_correlations "
                "where org_id = :o and correlation_id = :c limit 1"),
                {"o": org_id, "c": correlation_id}).first()
            if owned:
                return 0
            written = 0
            for event_id in events:
                written += conn.execute(text(
                    "insert into context_correlation_members "
                    "(org_id, correlation_id, event_id, joined_via) "
                    "values (:o, :c, :e, 'reading') on conflict do nothing"),
                    {"o": org_id, "c": correlation_id, "e": event_id}).rowcount or 0
            return written
    except Exception:      # noqa: BLE001 — membership is a refinement, never the sweep
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").warning(
            "could not declare events for correlation=%s org=%s", correlation_id, org_id,
            exc_info=True)
        return 0


__all__ = ["declare_finding_events", "finding_events"]
