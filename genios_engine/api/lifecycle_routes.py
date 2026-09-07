"""L2.7.7 · the resolution review queue — the surface below M-4's confidence floor.

Doc 12's seventh cross-cutting rule is one line: *"Confidence floor → human review queue, never
a card."* This is that queue. Everything in it is a sentence somebody wrote that DESCRIBED a
resolution and did not earn a close on its own — a vendor's *"all done on our side"*, an
owner's *"you should have everything you need now"*, a one-line *"sorted"* — kept with its quote,
its speaker and the arithmetic that held it back, so a person can settle it in a second.

WHY ACCEPTING AN ENTRY DOES NOT PROMOTE THE CLAIM. A human who agrees is making a HUMAN
resolution, and it is recorded as one (`resolve_situation`, the path that already existed and
already reopens on new evidence). The claim keeps saying what it always said — that the model
described a resolution and deterministic code would not act on it alone. Merging the two would
make the ledger unable to answer the only question it exists for: how often was M-4 right on its
own.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.context.lifecycle.store import decide_review, pending_reviews
from genios_engine.context.situations import resolve_situation
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.wiring import make_graph_store

#: NOT under `/situations/…`. `situation_routes` already owns
#: `/api/org/{org_id}/situations/{situation_id}` and it is included first, so a queue hanging off
#: that prefix would be swallowed by the wildcard and answer 404 "no such situation" — a route
#: that exists, resolves, and is unreachable.
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


class ReviewIn(BaseModel):
    accepted: bool
    reviewed_by: str | None = None


@router.get("/api/org/{org_id}/resolution-reviews")
def list_reviews(org_id: str, limit: int = 100, org: str = Depends(_org)) -> dict:
    """Stated resolutions held for a human, strongest first.

    Each entry carries the QUOTE and the reason it was held. A queue entry that said only "we
    think this might be resolved" would cost more attention than it saves; one that says who
    wrote what, and that a counterparty's claim is not by itself a fact, can be settled by
    reading two lines.
    """
    with _store().engine.connect() as conn:
        rows = pending_reviews(conn, org, limit=limit)
    return {"reviews": [
        {"claim_id": r["claim_id"], "situation_id": r["situation_id"],
         "about": r["about"], "type": r["situation_type"], "domain": r["domain"],
         "stated_at": r["stated_at"], "verdict": r["verdict"], "certainty": r["certainty"],
         "scope": r["scope"] or [], "said_by": r["speaker_email"],
         "speaker_role": r["speaker_role"], "quote": r["quote"], "held_because": r["reason"]}
        for r in rows], "count": len(rows)}


@router.post("/api/org/{org_id}/resolution-reviews/{claim_id}")
def settle_review(org_id: str, claim_id: str, body: ReviewIn,
                  org: str = Depends(_org)) -> dict:
    """Accept or dismiss one held resolution.

    The clock is read HERE, at the process boundary, because this is a request rather than a
    sweep — the same rule the drain follows, applied at the other kind of entry point.
    """
    now = datetime.now(timezone.utc)
    with _store().engine.begin() as conn:
        row = conn.execute(text(
            "select situation_id, quote from situation_resolution_claims "
            "where org_id = :o and claim_id = :cid"), {"o": org, "cid": claim_id}).first()
        if row is None:
            raise HTTPException(404, "no such resolution claim")
        if not decide_review(conn, org, claim_id=claim_id, accepted=body.accepted,
                             reviewed_by=body.reviewed_by, eval_time=now):
            raise HTTPException(409, "this claim is not waiting for review")
        resolved = False
        if body.accepted:
            resolved = resolve_situation(
                conn, org_id=org, situation_id=row.situation_id,
                note=f'accepted a stated resolution — "{row.quote}"')
    return {"claim_id": claim_id, "situation_id": row.situation_id,
            "review_state": "accepted" if body.accepted else "dismissed",
            "situation_resolved": resolved,
            "resolved_by": "human" if resolved else None}
