"""What came of each admitted situation candidate after admission — the store over `situation_outcomes`.

STEP-06 (`yc2_w27_s06 · M24.C2`), migration 0194. The admission gate records admit / hold / reject
(`situation_admission_decisions`) and the change gate every decided subject (`reasoning_fingerprints`);
this records what ended in between, one row per admitted candidate (its admission `decision_id`).

The row holds the candidate's CURRENT end. The same end again moves `last_seen_at` and `sweeps`; a
different end — `budget_exhausted` today, `decided` tomorrow — replaces the outcome and starts the count
again. One row per material change either way, never one per sweep.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import text

DECIDED = "decided"
NO_ROUTE = "no_route"
INCOMPLETE = "incomplete"
CONFLICT = "conflict"
REQUIRED_MISSING = "required_missing"
UNSUPPORTED = "unsupported"
NO_TENANT_PACK = "no_tenant_pack"
BUDGET_EXHAUSTED = "budget_exhausted"
ERROR = "error"

#: The schema's own closed vocabulary (`situation_outcomes_outcome_check`), so a typo fails here,
#: before the database refuses it in the middle of a pass's flush.
OUTCOMES: frozenset[str] = frozenset({DECIDED, NO_ROUTE, INCOMPLETE, CONFLICT, REQUIRED_MISSING,
                                      UNSUPPORTED, NO_TENANT_PACK, BUDGET_EXHAUSTED, ERROR})
#: Everything but a decision: the candidate stopped after it was admitted.
STOPS: frozenset[str] = OUTCOMES - {DECIDED}


_RECORD = text(
    "insert into situation_outcomes (org_id, decision_id, situation_id, outcome, reason, "
    "                                recorded_at, last_seen_at, sweeps) "
    "values (:o, :d, :s, :outcome, :reason, :at, :at, 1) "
    "on conflict (org_id, decision_id) do update set "
    "  recorded_at = case when situation_outcomes.outcome = excluded.outcome "
    "                      and situation_outcomes.reason is not distinct from excluded.reason "
    "                     then situation_outcomes.recorded_at else excluded.recorded_at end, "
    "  sweeps = case when situation_outcomes.outcome = excluded.outcome "
    "                 and situation_outcomes.reason is not distinct from excluded.reason "
    "                then situation_outcomes.sweeps + 1 else 1 end, "
    "  outcome = excluded.outcome, reason = excluded.reason, "
    "  last_seen_at = excluded.last_seen_at")

_SEEN = text(
    "insert into situation_outcomes (org_id, decision_id, situation_id, outcome, reason, "
    "                                recorded_at, last_seen_at, sweeps) "
    "values (:o, :d, :s, 'decided', 'unchanged', :at, :at, 1) "
    "on conflict (org_id, decision_id) do update set "
    "  last_seen_at = excluded.last_seen_at, sweeps = situation_outcomes.sweeps + 1")


def record(conn, *, org_id: str, decision_id: str, situation_id: str, outcome: str,
           reason: str | None, at: datetime) -> None:
    """Write `decision_id`'s current end; the same end again only moves its clock and count."""
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown situation outcome {outcome!r}")
    conn.execute(_RECORD, {"o": org_id, "d": decision_id, "s": situation_id, "outcome": outcome,
                           "reason": reason, "at": at})


def record_seen(conn, *, org_id: str, decision_id: str, situation_id: str, at: datetime) -> None:
    """The change gate skipped it: the end it was given stands, and only its clock and count move.

    A candidate decided before this table existed has no row yet; it gets `decided` / `unchanged`.
    """
    conn.execute(_SEEN, {"o": org_id, "d": decision_id, "s": situation_id, "at": at})
