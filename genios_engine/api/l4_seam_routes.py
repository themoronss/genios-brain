"""Wave Z6 · the two OUTBOUND seams as request paths (doc 06 OUT-1 and OUT-2).

    POST /v1/intelligence/critique      an agent proposes; GeniOS scores, critiques, ADVISES
    GET  /v1/intelligence/brief         the book-level daily re-rank, with rank_components

A router of their own rather than two more handlers on `intelligence_routes`, for one reason that
matters more than tidiness: these two are the first surfaces in this product that are not read by a
human being. The critique endpoint is consumed by somebody ELSE'S agent under a grant an owner
issued (`intelligence.critique`, in `AGENT_API_SCOPES`), and a seam with that blast radius should be
findable in one file — its authorisation, its activation gate, its refusals and its receipt — rather
than at line 900 of a module about the Ask page.

BOTH ARE GATED PER TENANT. `l4_activation` carries five independently-flippable features and these
are the last two; an org that has not been switched on gets 404 rather than a verdict, because a
critique from a tenant whose formula has not been woken (`ranking_v2` is this feature's declared
precondition) would be scored on a model that cannot express an absent component. The gate reads
fail closed by construction, which for these two means "not activated" and therefore "not answered".

NOTHING HERE DECIDES. The critique route resolves a credential, builds the contract object, calls
`reason/critique.py`, and serialises. The brief route reads a clock — at the process boundary, which
is the only place this codebase reads one — and calls `reason/brief_ranking.py`. Every judgement in
both answers was made by a deterministic function in `reason/`, and every one of them is replayable
from the receipt this router returns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from genios_engine.contracts.reasoning import ExternalCandidate
from genios_engine.platform import audit, l4_activation
from genios_engine.platform.auth import AuthCtx, get_current_org, require_scope
from genios_engine.platform.canonical import stable_id
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import make_graph_store
from genios_engine.reason import brief_ranking as BRIEF
from genios_engine.reason import critique as CRITIQUE
from genios_engine.reason.store import ReasoningStore

router = APIRouter()
_log = get_logger("l4.seams")

#: The one grant this seam answers to. Owner sessions carry every scope; an agent key carries this
#: only if a tenant owner minted it with the grant (`/agents/register` validates against
#: `AGENT_API_SCOPES`, which is where this string is declared).
CRITIQUE_SCOPE = "intelligence.critique"

_graph = make_graph_store()


def _engine():
    """The tenant database, or a 503 that says so.

    `make_graph_store()` is module-level and returns a store even with no database configured; the
    503 belongs here rather than at import, because a process that cannot boot is worse than an
    endpoint that says the database is unavailable.
    """
    engine = getattr(_graph, "engine", None)
    if engine is None:
        raise HTTPException(503, "reasoning storage is not available")
    return engine


def _require_activated(org_id: str, feature: str) -> None:
    """The per-tenant gate. 404, not 403: an unactivated tenant has no such surface.

    403 would say "you may not use this", which invites a retry with a better credential and tells
    an agent something true about another tenant's configuration. 404 says what is actually the
    case — for this org, this seam does not exist yet.
    """
    if not l4_activation.is_l4_activated(_engine(), org_id, feature):
        raise HTTPException(404, f"the '{feature}' seam is not activated for this workspace")


# =================================================================================================
# E1 · POST /v1/intelligence/critique — evaluate without emitting (doc 06 OUT-1)
# =================================================================================================

class ProposedAction(BaseModel):
    """The agent's action, in doc 06's own shape: `{kind, draft, params}`."""

    kind: str
    draft: str
    params: dict[str, Any] = Field(default_factory=dict)


class CritiqueBody(BaseModel):
    """`{target_ref, proposed_action}` plus the two identities a receipt needs.

    `proposal_id` is the agent's own idempotency handle — it is echoed on the verdict, travels into
    the check that eliminated the proposal, and is what an agent correlates its record with ours by.
    Defaulted rather than required only because a first integration should not fail on a field it
    has not read about yet; when it is absent the agent id and target carry the identity.
    """

    target_ref: str
    proposed_action: ProposedAction
    proposal_id: str | None = None
    agent_id: str | None = None


@router.post("/v1/intelligence/critique")
def critique_proposed_action(body: CritiqueBody,
                             ctx: AuthCtx = Depends(require_scope(CRITIQUE_SCOPE))) -> dict:
    """Score an external agent's proposed action against this tenant's reasoning. **Advisory.**

    GeniOS scores; the agent executes. Nothing on this path writes to the graph, emits a signal,
    builds a card or touches the delivery outbox — the closed action space is untouched, because
    evaluating a proposal is not the same act as generating one. `advisory` is True on the way out
    and cannot be constructed False (Z0's `CritiqueVerdict`), so a client that ignored this
    docstring still cannot read a binding claim out of the payload.
    """
    org_id = ctx.org_id
    _require_activated(org_id, l4_activation.FEATURE_CRITIQUE)
    agent_id = body.agent_id or ctx.agent_id or ctx.actor_id or "external_agent"
    # DERIVED, never `hash()`: Python's string hash is salted per process, so an agent that
    # omitted `proposal_id` would receive a different identity for the same proposal on every
    # worker — and the identity is what its own record correlates against ours by.
    proposal_id = body.proposal_id or stable_id("proposal", {
        "agent_id": agent_id, "target_ref": body.target_ref,
        "kind": body.proposed_action.kind, "draft": body.proposed_action.draft})
    try:
        proposal = ExternalCandidate(
            proposal_id=proposal_id, agent_id=agent_id,
            kind=body.proposed_action.kind, draft=body.proposed_action.draft,
            params=body.proposed_action.params, target_ref=body.target_ref)
    except (TypeError, ValueError) as exc:
        # The contract refused the proposal itself — an unknown kind, a draft over the cap, a float
        # where basis points belong. 422 with the contract's own words: an agent author needs to
        # read what was wrong with the request, not a generic rejection.
        raise HTTPException(422, str(exc)) from None

    store = ReasoningStore(engine=_engine())
    try:
        outcome = CRITIQUE.critique_target(store=store, org_id=org_id, proposal=proposal)
    except CRITIQUE.CritiqueRefused as refusal:
        # 409, not 404 and not 500: the request is well-formed and the tenant is entitled to ask,
        # and the seam cannot answer YET — no run for this target, a swept context, a five-weight
        # capability. The reason code is the machine-readable half so an agent can branch on it.
        #
        # Logged as well as returned, because the distribution of these is the operational question
        # during a pilot: an agent integration that only ever receives
        # `no_reasoned_situation_for_target` is pointing at ids this tenant does not reason about,
        # and that is invisible from our side unless the refusals are counted somewhere.
        _log.info("critique refused org=%s agent=%s target=%s reason=%s",
                  org_id, agent_id, proposal.target_ref, refusal.reason)
        raise HTTPException(409, {"error": refusal.reason, "detail": refusal.detail,
                                  "target_ref": proposal.target_ref}) from None

    verdict = outcome.verdict
    if verdict.advisory is not True:                     # pragma: no cover — unconstructible
        # Unreachable through the constructor, and checked anyway. This is the last line before the
        # claim leaves the building; a future refactor reaching for `model_construct` would put a
        # binding verdict on the wire, and the cost of the check is one comparison.
        raise HTTPException(500, "a non-advisory verdict was produced and refused")

    audit.record(org_id, "intelligence.critique", actor_type="agent", actor_id=agent_id,
                 target_type="external_candidate", target_id=proposal.proposal_id,
                 metadata={"verdict": verdict.verdict, "failing_checks": list(verdict.failing_checks),
                           "run_id": (outcome.receipt.get("evidence") or {}).get("run_id"),
                           "kind": proposal.kind})
    return {
        "verdict": verdict.verdict,
        "advisory": verdict.advisory,
        "failing_checks": list(verdict.failing_checks),
        "winning_alternative": verdict.winning_alternative,
        "utility_bp": verdict.utility_bp,
        "confidence_bp": verdict.confidence_bp,
        "rationale": verdict.rationale,
        "proposal_id": proposal.proposal_id,
        "receipt": dict(outcome.receipt),
    }


# =================================================================================================
# E3 · GET /v1/intelligence/brief — the book-level daily re-rank (doc 06 OUT-2)
# =================================================================================================

@router.get("/v1/intelligence/brief")
def daily_brief(limit: int = Query(default=BRIEF.BRIEF_ENTRY_CAP, ge=1, le=BRIEF.BRIEF_ENTRY_CAP),
                org_id: str = Depends(get_current_org)) -> dict:
    """Today's decisions, ranked against EACH OTHER, with the components that ranked them.

    `limit` cuts the rendered list, never the stored ranking: the pass is over the whole open set
    and the artifact records all of it, so "why is this #4" stays answerable after the surface has
    shown three. The clock is read HERE and passed down — the ranking function takes an instant and
    reads no clock of its own, which is what makes today's brief reproducible tomorrow.
    """
    _require_activated(org_id, l4_activation.FEATURE_BRIEF)
    now = datetime.now(timezone.utc)
    ranking, changed = BRIEF.daily_brief_ranking(_engine(), org_id=org_id, eval_time=now)
    receipts = {receipt["decision_id"]: receipt for receipt in ranking.receipts}
    return {
        "org_id": ranking.ranking.org_id,
        "brief_date_key": ranking.ranking.brief_date_key,
        "model_version": ranking.version,
        "ranking_hash": ranking.ranking_hash,
        "changed": changed,
        "considered": len(ranking.ranking.entries) + len(ranking.dropped),
        "entries": [{
            "rank": entry.rank,
            "decision_id": entry.decision_id,
            "book_score_bp": entry.book_score_bp,
            # THE ANSWER TO "WHY #1 TODAY", AND IT IS DATA. Every term that moved this decision,
            # named and in basis points; a narrative that disagreed with these would be a bug.
            "rank_components": dict(entry.rank_components),
            **{key: receipts.get(entry.decision_id, {}).get(key)
               for key in ("card_id", "headline", "subject_node_id", "account_ref",
                           "surfaced_count", "absence_count", "run_id")},
        } for entry in ranking.ranking.entries[:limit]],
        "dropped": [dict(row) for row in ranking.dropped],
    }


@router.get("/v1/intelligence/brief/{date_key}")
def stored_brief(date_key: str, org_id: str = Depends(get_current_org)) -> dict:
    """A PAST day's brief, exactly as it was ranked — the question a live re-rank cannot answer.

    This is the half of the artifact that justifies the table: "what did you tell me on Tuesday, and
    why was that first" is unanswerable from a surface that recomputes, and it is the first question
    asked when a brief turns out to have been wrong.
    """
    _require_activated(org_id, l4_activation.FEATURE_BRIEF)
    row = BRIEF.stored_ranking(_engine(), org_id=org_id, date_key=date_key)
    if row is None:
        raise HTTPException(404, f"no brief was produced for {date_key}")
    return {**row, "computed_at": str(row["computed_at"])}


__all__ = ["CRITIQUE_SCOPE", "router"]
