"""L2.5.5 / L-5 · the READ surface for typed absence and the coverage epoch.

Two questions this exists to answer, and neither could be asked before X6:

    what does this tenant NOT know, and which kind of not-knowing is each gap?
    what could we see when we said that, and can we still say it?

**Why a route and not only a table.** Doc 05's group gate is a MEASUREMENT — *"negative inferences
drawn from `UNKNOWABLE` facts: 0"* — and a gate stated as a count needs somewhere to read the
count from. `context_situations.missing` cannot answer it: it is a jsonb array of human phrases,
which cannot be grouped, cannot carry a coverage basis, and cannot record the epoch it was drawn
under. `GET .../absences` is that number, and `?type=` is the drill-down behind it.

**Read-only, and deliberately so.** Nothing here writes. An absence is a derived view of the
graph, recomputed by the drain (`situations.refresh_situations`), and a route that let a caller
edit one would be a route that let a caller grant themselves a negative inference — the exact
thing `licenses_negative_inference` is computed rather than supplied to prevent.

Single-tenant. `_org` refuses a mismatch between the path and the credential, exactly as the
cohort and correlation surfaces do.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from genios_engine.context.quality.epoch import (coverage_over, current_epochs, epoch_at,
                                                 epochs_over)
from genios_engine.context.quality.missing import (absence_counts, findings,
                                                   read_absences)
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


@router.get("/api/org/{org_id}/context/absences")
def list_absences(org_id: str, absence_type: str | None = Query(default=None, alias="type"),
                  situation_id: str | None = None, org: str = Depends(_org)) -> dict:
    """The typed absences, the counts by type, and how many still license an inference.

    `licensed` is NOT the same as the `genuinely_absent` count and the gap between them is the
    point of the epoch: a finding drawn under a coverage regime that has since been superseded is
    unverified, so it is reported, marked, and excluded from the licensed total rather than
    quietly dropped.
    """
    with _store().engine.connect() as conn:
        counts = absence_counts(conn, org)
        rows = read_absences(conn, org,
                             situation_ids=None if situation_id is None else [situation_id])
    if absence_type:
        rows = tuple(r for r in rows if r.fact.absence_type.value == absence_type)
    def _is_finding(row) -> bool:
        """OUTPUT rather than data quality, through the same function every other consumer uses
        so "is this a finding" has one answer. Stale coverage is checked FIRST: an absence drawn
        under a superseded regime is unverified, so it cannot be a finding whatever its
        expectation says."""
        return not row.stale_coverage and bool(findings((row.fact,)))

    return {
        "org_id": org,
        "counts": counts,
        # THE H6 ROW. Read straight off the rows rather than recomputed by the caller, so the
        # gate and the product read the same number.
        "licensed": sum(1 for r in rows if r.licenses_negative_inference),
        "stale_coverage": sum(1 for r in rows if r.stale_coverage),
        "absences": [{
            "situation_id": r.situation_id,
            "subject_node_id": r.fact.subject_node_id,
            "expected_fact": r.fact.expected_fact,
            "absence_type": r.fact.absence_type.value,
            # Serialized from the contract's COMPUTED field, so a client reads the licence
            # rather than re-deriving it from the type with its own idea of the rule.
            "licenses_negative_inference": r.licenses_negative_inference,
            "is_finding": _is_finding(r),
            "coverage_ready": r.fact.coverage_ready,
            "coverage_basis": list(r.fact.coverage_basis),
            "coverage_domain": r.coverage_domain,
            "coverage_epoch": r.coverage_epoch,
            "stale_coverage": r.stale_coverage,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
        } for r in rows],
    }


@router.get("/api/org/{org_id}/context/coverage-epochs")
def list_coverage_epochs(org_id: str, org: str = Depends(_org)) -> dict:
    """The coverage regime open for each domain, and since when.

    A different question from `GET /coverage/declared`, which reports the CURRENT row: this one
    reports the window that row has held over, which is what makes "was this true when we decided
    it" answerable at all.
    """
    with _store().engine.connect() as conn:
        epochs = current_epochs(conn, org)
    return {"org_id": org, "epochs": [{
        "domain": domain, "epoch": e.epoch, "coverage_ready": e.coverage_ready,
        "capabilities": list(e.capabilities),
        "opened_at": e.opened_at.isoformat() if e.opened_at else None,
    } for domain, e in sorted(epochs.items())]}


@router.get("/api/org/{org_id}/context/coverage-window")
def coverage_window(org_id: str, domain: str, since_days: int = Query(default=28, ge=1, le=730),
                    at: datetime | None = None, org: str = Depends(_org)) -> dict:
    """What coverage did across a PERIOD — the question a trend has to ask before it claims a
    decline.

    `crossed` is the answer that matters and the one no current-state row can give: a window with
    a connector change inside it is not wrong, but the step in the series is OURS, and *"engagement
    fell"* and *"we started being able to see engagement"* are the same numbers and two different
    sentences.

    The clock is read HERE, at the process boundary, and passed down — never inside the window
    arithmetic.
    """
    end = at or datetime.now(timezone.utc)
    if end.tzinfo is None:
        raise HTTPException(422, "at must carry a timezone")
    start = end - timedelta(days=since_days)
    with _store().engine.connect() as conn:
        found = epochs_over(conn, org, domain, start, end)
        at_end = epoch_at(conn, org, domain, end)
    window = coverage_over(domain, found, start=start, end=end)
    payload: dict[str, Any] = {
        "org_id": org, "domain": domain,
        "start": start.isoformat(), "end": end.isoformat(),
        "ready": window.ready, "crossed": window.crossed, "epochs": list(window.epochs),
        "licenses_negative_inference": window.licenses_negative_inference,
        "epoch_at_end": None if at_end is None else at_end.epoch,
    }
    return payload
