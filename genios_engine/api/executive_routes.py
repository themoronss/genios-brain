"""/v1/executive/* — the Layer 5 surface: briefs, summary ladder, memory, preventive
warnings, and why-not receipts. Read-only, org-scoped, fully deterministic (no LLM on
any path here). Additive module: no existing route is touched.

The boundary this surface keeps: it says WHAT/WHY/HOW-URGENT/ON-WHAT-EVIDENCE and
WHAT-IF-NOTHING. It never says who, when, or through which tool — that's deliver's."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from genios_engine.platform.auth import get_current_org
from genios_engine.platform.wiring import make_graph_store, make_pack_registry

router = APIRouter(prefix="/v1/executive", tags=["executive"])
_graph = make_graph_store()
_registry = make_pack_registry()


def _require_db():
    if _graph is None:
        raise HTTPException(400, "graph store not configured (needs DATABASE_URL)")


@router.get("/briefs")
def briefs(limit: int = 20, org_id: str = Depends(get_current_org)) -> dict:
    """Open signals as ranked Decision Briefs — the executive queue."""
    _require_db()
    from genios_engine.executive.brief import load_briefs
    return {"briefs": load_briefs(_graph, org_id, registry=_registry, limit=limit)}


@router.get("/summary")
def summary(horizon: str = "one_line", org_id: str = Depends(get_current_org)) -> dict:
    """The summary ladder: one_line | one_minute | five_minute. Counted, never estimated."""
    _require_db()
    if horizon not in ("one_line", "one_minute", "five_minute"):
        raise HTTPException(422, "horizon must be one_line | one_minute | five_minute")
    from genios_engine.executive.summary import build_summary
    return build_summary(_graph, org_id, horizon)


@router.get("/memory")
def memory(limit: int = 10, org_id: str = Depends(get_current_org)) -> dict:
    """Executive working context: recent decisions, open decisions, overdue items,
    where attention sits. So the next decision isn't amnesiac."""
    _require_db()
    from genios_engine.executive.memory import load_memory
    return load_memory(_graph, org_id, limit=limit)


@router.get("/preventive")
def preventive(limit: int = 25, org_id: str = Depends(get_current_org)) -> dict:
    """The fourth mode: rules about to trip, with exact time remaining — act BEFORE
    the miss. Pure arithmetic over the same rules/facts the reasoner uses."""
    _require_db()
    from genios_engine.executive.modes import load_preventive
    return {"preventive": load_preventive(_graph, org_id, registry=_registry, limit=limit)}


@router.get("/why-not")
def why_not_route(entity_id: str | None = None, rule_id: str | None = None,
                  days: int = 7, org_id: str = Depends(get_current_org)) -> dict:
    """'Why didn't you tell me about X?' — the stored suppression receipts, answered
    from signal_suppression_log (written since day one, read for the first time)."""
    _require_db()
    from genios_engine.executive.explain import why_not
    return why_not(_graph, org_id, entity_id=entity_id, rule_id=rule_id, days=days)
