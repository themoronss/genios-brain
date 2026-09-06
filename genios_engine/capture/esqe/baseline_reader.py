"""L1.6.7-U2's INPUT — the org's own priced history, read out of the database.

:func:`~genios_engine.capture.esqe.importance.compute_org_baseline` is a pure function over a
sequence of :class:`BaselineObservation`. It shipped with every one of its rungs tested and
**nothing on a production path able to build that sequence**, so `capture/pipeline.py` fell back
to `OrgBaseline.cold_start(...)` on every event of every sweep. The consequence is not a crash
and that is why it survived five reviews:

* ``monetary_exposure_bp`` — 30% of the formula — came off the ABSOLUTE ladder for every tenant,
  so "$84K" scored the same for a five-person startup and for a bank;
* ``entity_criticality_bp`` — another 20% — was pinned to ``FIRST_SEEN`` (2000) for every
  counterparty a tenant has ever had, because a cold-start baseline knows nobody;
* the RATIO ladder, the whole point of scoring against the org rather than against an absolute
  scale, never executed once outside its unit test;
* doc 06's own headline acceptance row — the $84K renewal, twelve days out, from the CFO, on a
  signed PDF — scored **5625** in production against a required 7500-8500.

This module is the missing half: where the history lives, and how it becomes observations.

WHERE THE HISTORY LIVES
-----------------------
`l1_extraction_results` (migration 0080). Every extraction L1 has ever produced for this tenant
is filed there as its `output` json — the mapping lane's and the model lane's alike — and its
`amounts` array is `Money` in **integer minor units with an ISO code**, already normalised by
ALG-10. That is the org's priced history, and it is the only store in this build that has one:
`graph_facts` holds no money field and no deal-value table exists. The event's WORLD time comes
from `source_events.occurred_at`, joined on `event_id`, because when we READ a message is not
when the contract was signed.

ONCE PER SWEEP, NEVER PER EVENT
-------------------------------
The shape is `capture/coverage/declaration.py`'s exactly: one impure reader beside a pure
computation, called once for an org by a wiring factory and handed to capture as a value. A p50
over a year moves by less than a rounding step when one deal lands; paying a table scan per
message would put a query on the ingestion path of every email for an answer that is the same
all sweep.

NEVER BLOCKS A SWEEP
--------------------
Every read here answers with what it could get. A database that is unreachable, a table that a
migration has not reached yet, a row whose json is not the shape this build knows: all of them
yield fewer observations, and no observations yields `OrgBaseline.cold_start` — the state every
tenant was already in. Doc 06 is explicit that a missing baseline must never block scoring, and
an exception raised here would do exactly that, for the whole tenant, on the ingestion path.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from genios_engine.capture.esqe.importance import (BASELINE_WINDOW_DAYS, BaselineObservation,
                                                   OrgBaseline, compute_org_baseline,
                                                   require_aware_instant)
from genios_engine.contracts.units import Money
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.baseline")

#: The extraction store (migration 0080) and the landing table its rows are dated by.
EXTRACTION_TABLE = "l1_extraction_results"
EVENT_TABLE = "source_events"

#: Term 4 rung 1's table (migration 0091) — the entities this tenant DECLARED mission-critical.
MISSION_CRITICAL_TABLE = "org_mission_critical_entities"

#: How many priced events one baseline may read. A tenant with a decade of mail must not turn a
#: once-per-sweep read into an unbounded scan, and a p50 taken over the most recent 5,000 priced
#: events in the window is the same number as one taken over 50,000 for every org this product
#: has: the cap is a ceiling on cost, not a sample. Ordered by `occurred_at desc` so the rows it
#: keeps are the recent ones, which is the half a baseline is a statement about.
MAX_OBSERVATIONS = 5000

#: An open deal makes its counterparty ACTIVE (term 4 rung 3). L2's own node type.
_OPEN_DEAL_SQL = (
    "select display_name, canonical_key from graph_nodes "
    "where org_id = :org and node_type = 'deal' and valid_to is null")

_HISTORY_SQL = (
    "select e.occurred_at as occurred_at, "
    "       x.output -> 'amounts' as amounts, "
    "       x.output -> 'entity_mentions' as entities "
    f"from {EXTRACTION_TABLE} x "
    f"join {EVENT_TABLE} e on e.event_id = x.event_id and e.org_id = x.org_id "
    "where x.org_id = :org and e.occurred_at >= :since and e.occurred_at <= :until "
    "  and jsonb_array_length(coalesce(x.output -> 'amounts', '[]'::jsonb)) > 0 "
    "order by e.occurred_at desc limit :cap")

#: `entity_type` values that name an ORGANISATION. Term 4 ranks counterparties, and a person
#: cc'd on a deal thread is a participant — the same rule `normalize._primary_entity` applies to
#: the signal, applied here to the history, so the two cannot disagree about who a deal was with.
_ORG_ENTITY_TYPES = frozenset({"organization", "organisation", "company", "org", "account",
                               "vendor", "customer", "counterparty"})


def _rows(engine, sql: str, params: dict) -> list[Any]:
    """One read, or an empty list and a warning. Never an exception into a sweep."""
    if engine is None:
        return []
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return list(conn.execute(text(sql), params))
    except Exception:      # noqa: BLE001 — an unreadable history is a cold start, never a 500
        _log.warning("could not read priced history for the org baseline", exc_info=True)
        return []


def _money_of(entry: Any) -> Money | None:
    """One stored `amounts` entry back into `Money`, or None when it is not that shape.

    Rebuilt through the CONTRACT rather than read as a bare integer: `Money`'s own validators
    are what refuse a float `minor_units` and a currency that is not an ISO code, and a baseline
    computed over amounts that skipped them would be a p50 of whatever a stored row happened to
    hold.
    """
    if not isinstance(entry, dict):
        return None
    try:
        return Money(minor_units=entry["minor_units"], currency=entry["currency"],
                     as_written=entry.get("as_written") or str(entry["minor_units"]))
    except (KeyError, TypeError, ValueError):
        return None


def _counterparty_of(entities: Any) -> str | None:
    """The ONE organisation this priced event was with, or None.

    Exactly one candidate must survive, on `normalize._primary_entity`'s rule and for its
    reason: two organisations named in one message is an introduction, and attributing the
    amount to either would put a counterparty in the top decile on the strength of somebody
    else's contract.
    """
    if not isinstance(entities, list):
        return None
    names = {name for entry in entities
             if isinstance(entry, dict)
             and str(entry.get("entity_type") or "").strip().lower() in _ORG_ENTITY_TYPES
             and (name := str(entry.get("surface_form") or "").strip())}
    return next(iter(names)) if len(names) == 1 else None


def priced_history(engine, org_id: str, *, eval_time: datetime,
                   window_days: int = BASELINE_WINDOW_DAYS,
                   cap: int = MAX_OBSERVATIONS) -> tuple[BaselineObservation, ...]:
    """Every amount this org's own extractions carry inside the window, as observations.

    One observation per AMOUNT and not per event: an invoice mail naming three line items is
    three priced facts, and collapsing them to one would let the shape of a tenant's mail decide
    its p50. The window is filtered in SQL rather than in Python so a tenant with ten years of
    history pays for one year of rows.
    """
    eval_time = require_aware_instant(eval_time)
    rows = _rows(engine, _HISTORY_SQL,
                 {"org": org_id, "since": eval_time - timedelta(days=window_days),
                  "until": eval_time, "cap": max(1, int(cap))})
    observations: list[BaselineObservation] = []
    for row in rows:
        counterparty = _counterparty_of(row.entities)
        for entry in (row.amounts if isinstance(row.amounts, list) else []):
            amount = _money_of(entry)
            if amount is None or amount.minor_units == 0:
                continue
            observations.append(BaselineObservation(amount=amount, occurred_at=row.occurred_at,
                                                    counterparty=counterparty))
    return tuple(observations)


def open_deal_counterparties(engine, org_id: str) -> tuple[str, ...]:
    """Who this org has a deal open with — term 4's ACTIVE rung, from L2's own deal nodes.

    Both keys are offered to the folder: `display_name` is what a human sees, and
    `canonical_key` is `deal:<company>` for the deals L2 lifts out of a company, which is the
    only place the counterparty's name survives when the node was never given a display name.
    """
    names: list[str] = []
    for row in _rows(engine, _OPEN_DEAL_SQL, {"org": org_id}):
        display = (row.display_name or "").strip()
        if display:
            names.append(display)
        key = (row.canonical_key or "").strip()
        if key.startswith("deal:") and key[5:].strip():
            names.append(key[5:].strip())
    return tuple(names)


def mission_critical_entities(engine, org_id: str) -> tuple[str, ...]:
    """Term 4 RUNG 1 — the entities this tenant declared mission-critical (migration 0091).

    This function is the half that used to be missing. `load_org_baseline` took
    ``mission_critical`` as a parameter with an empty default and nothing in the build ever
    passed one, so `EntityStanding.MISSION_CRITICAL` — the top rung of a term worth 2000 of
    ALG-17's 10000 basis points — was unreachable in production: a tenant's payroll provider
    could rank no higher than its largest customer by contract value, because the only rung the
    reader could reach on judgement rather than on money was TOP_DECILE.

    The keys come back CASEFOLDED because the column is (the migration's own check constraint),
    and because that is the form `OrgBaseline.__post_init__` folds every entity set into. Reading
    a display-cased name here would make `standing_of` compare a folded surface form against an
    unfolded tag and answer `first_seen` for a mission-critical vendor — a plausible number, and
    invisible.

    Answers with what it could get, like every read in this module: an unreachable database or a
    table a migration has not reached yet yields no tags, which is the state every tenant is in
    until somebody uses the route.
    """
    return tuple(str(row.entity_key) for row in _rows(
        engine, f"select entity_key from {MISSION_CRITICAL_TABLE} where org_id = :org "
                "order by entity_key", {"org": org_id}) if row.entity_key)


def load_org_baseline(engine, org_id: str, *, eval_time: datetime,
                      window_days: int = BASELINE_WINDOW_DAYS,
                      cap: int = MAX_OBSERVATIONS,
                      mission_critical: Iterable[str] | None = None) -> OrgBaseline:
    """L1.6.7-U2 for one tenant, from that tenant's own stored history. ONE call per sweep.

    All FIVE of term 4's rungs are reachable from here. Four are computed from history —
    top-decile and known by `compute_org_baseline` from the priced observations, active from the
    org's open deals — and rung 1, mission-critical, is read from the tenant's own declarations
    by `mission_critical_entities` above. `mission_critical=None` means "read it", which is what
    every production caller wants; an explicit sequence overrides the read for a caller that
    already holds the answer, and `()` is a caller stating that this tenant has no tags.

    A tenant with no priced history is not an error and gets `basis=ESTIMATED` with its entity
    sets still populated — `compute_org_baseline`'s own contract.
    """
    eval_time = require_aware_instant(eval_time)
    tagged = (mission_critical_entities(engine, org_id) if mission_critical is None
              else tuple(mission_critical))
    return compute_org_baseline(
        priced_history(engine, org_id, eval_time=eval_time, window_days=window_days, cap=cap),
        org_id=org_id, eval_time=eval_time, window_days=window_days,
        mission_critical=tagged,
        active_counterparties=open_deal_counterparties(engine, org_id))


__all__ = ["EVENT_TABLE", "EXTRACTION_TABLE", "MAX_OBSERVATIONS", "MISSION_CRITICAL_TABLE",
           "load_org_baseline", "mission_critical_entities", "open_deal_counterparties",
           "priced_history"]
