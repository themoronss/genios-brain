"""Intelligence routes — REST wrapper over the MCP intelligence.* tools.

POST /v1/intelligence/query        engine query → Envelope
GET  /v1/intelligence/decisions/{id}/explain   trace + narrator for decision
POST /v1/intelligence/feedback     thumbs/edit/snooze/never_show
POST /v1/intelligence/graph_view   read-only subgraph view

Why a thin wrapper, not a re-implementation of decide():
    The engine's decide() pipeline needs a Gateway, RuleSet, Scorer, etc. Those
    are constructed per-module per-request (Sales has its own ruleset; another
    module brings its own). The HTTP layer dispatches to a registered module
    handler (see register_query_handler).

If no handler is registered for a module, /query returns 503 with an explicit
"module not loaded" message rather than guessing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.api.deps import db_session, require_org
from core.artifacts.trace import build_trace
from core.decision_store import DecisionRow
from core.delivery.envelope import Envelope
from core.delivery.feedback_capture import FeedbackAction, capture_feedback
from core.foundations.telemetry import get_logger

router = APIRouter(prefix="/v1/intelligence", tags=["intelligence"])
log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Module handler registry — modules register their query/graph_view here
# ─────────────────────────────────────────────────────────────────────────────


QueryHandler = Callable[[Session, str, dict[str, Any], dict[str, Any], str | None], Envelope]
GraphViewHandler = Callable[[Session, str, list[str], int], dict[str, Any]]

_QUERY_HANDLERS: dict[str, QueryHandler] = {}
_GRAPH_VIEW_HANDLERS: dict[str, GraphViewHandler] = {}


def register_query_handler(module_id: str, handler: QueryHandler) -> None:
    """Modules call this at app startup to expose their decide() path via HTTP."""
    if module_id in _QUERY_HANDLERS:
        raise ValueError(f"Duplicate query handler for module: {module_id}")
    _QUERY_HANDLERS[module_id] = handler


def register_graph_view_handler(module_id: str, handler: GraphViewHandler) -> None:
    """Modules expose their read-only subgraph builder."""
    if module_id in _GRAPH_VIEW_HANDLERS:
        raise ValueError(f"Duplicate graph_view handler for module: {module_id}")
    _GRAPH_VIEW_HANDLERS[module_id] = handler


def clear_handlers() -> None:
    """Test-only: reset both registries."""
    _QUERY_HANDLERS.clear()
    _GRAPH_VIEW_HANDLERS.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    module_id: str = Field(..., min_length=1)
    query: dict[str, Any]
    facts: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None


class FeedbackRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    action: FeedbackAction
    decision_id: str | None = None
    insight_id: str | None = None
    edit_diff: dict[str, Any] | None = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    correction_id: str | None
    routed_to_g_i_3: bool


class GraphViewRequest(BaseModel):
    module_id: str = Field(..., min_length=1)
    center_node_ids: list[str] = Field(default_factory=list)
    hops: int = Field(default=1, ge=0, le=3)


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/query", response_model=Envelope)
def query(
    body: QueryRequest,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> Envelope:
    """Run the engine for a module + return the Envelope.

    The actual decide() call is dispatched to the module-registered handler so
    each module can wire its own Gateway/RuleSet without the HTTP layer
    knowing module internals.
    """
    handler = _QUERY_HANDLERS.get(body.module_id)
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"module '{body.module_id}' has no query handler registered",
        )
    envelope = handler(session, org_id, body.query, body.facts, body.user_id)
    log.info(
        "intelligence_query",
        org_id=org_id,
        module_id=body.module_id,
        decision_id=envelope.decision_id,
        route=envelope.route.value,
    )
    return envelope


@router.get("/decisions/{decision_id}/explain")
def explain(
    decision_id: str,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    """Fetch trace + narrator for a past decision.

    Trace contains: derivation chain, grounding refs, confidence breakdown,
    constraints checked, route + as_of pin. Cheap read.
    """
    decision = session.get(DecisionRow, decision_id)
    if decision is None or decision.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="decision not found"
        )
    # derivation_chain_jsonb is typed as dict in the model but persisted as a
    # JSON list by the engine; tolerate either shape on read.
    raw_chain: Any = decision.derivation_chain_jsonb
    chain_steps: list[dict[str, Any]] = raw_chain if isinstance(raw_chain, list) else []
    trace = build_trace(
        session,
        decision_id=decision.id,
        org_id=org_id,
        derivation_chain=chain_steps,
        grounding_ref_ids=decision.grounding_refs_jsonb or [],
        edge_path_ids=[],
        confidence_overall=decision.confidence_score,
        confidence_breakdown=decision.confidence_breakdown_jsonb,
        decision_path=decision.path,
        as_of_version=decision.as_of_version,
        as_of_timestamp=decision.created_at,
    )
    return trace.model_dump(mode="json")


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(
    body: FeedbackRequest,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> FeedbackResponse:
    """Capture user feedback. 👎/edit auto-creates a Correction routed to g-i-3."""
    if body.action in (FeedbackAction.THUMBS_DOWN, FeedbackAction.EDIT) and not body.decision_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{body.action.value} requires decision_id",
        )
    out = capture_feedback(
        session,
        org_id=org_id,
        user_id=body.user_id,
        decision_id=body.decision_id,
        insight_id=body.insight_id,
        action=body.action,
        edit_diff=body.edit_diff,
    )
    session.flush()
    return FeedbackResponse(
        feedback_id=out.feedback_id,
        correction_id=out.correction_id,
        routed_to_g_i_3=out.routed_to_g_i_3,
    )


@router.post("/graph_view")
def graph_view(
    body: GraphViewRequest,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    """Read-only subgraph rooted at center_node_ids, BFS up to `hops`."""
    handler = _GRAPH_VIEW_HANDLERS.get(body.module_id)
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"module '{body.module_id}' has no graph_view handler",
        )
    return handler(session, org_id, body.center_node_ids, body.hops)
