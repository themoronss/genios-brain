"""The company brief, for the founder to confirm — read it, add a line, accept, edit or reject a
proposal, remove a line (STEP-07, the confirm screen's backend).

The screen itself lives in the dashboard (`genios-dashboard`, a separate repository); these are the
routes it calls. Until it has the screen, `scripts/company_brief.py` makes the same decisions for an
operator acting on the founder's word.

WHO DECIDES. Reading is for anyone the dashboard already lets read the tenant (`get_current_org`).
Every change is the account OWNER's (`require_account_owner`, `06` D27): the brief steers every
judgment the engine makes, so a teammate may propose — through the drafter — but not decide.

ACCEPTING A NAMED SENDER PROMOTES ITS ARCHIVE. A connector, a key person or a watchlist domain the
founder accepts is a sender whose mail always matters, so whatever the gate archived from that domain
goes back to the ledger as kept and the next chain pass reads it (`capture/landing/promote`) — the
promotion `promote.py` was written to wait for. A public mail host is never promoted by domain.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform import company_brief_store as store
from genios_engine.platform.auth import AuthCtx, get_current_org, require_account_owner
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()

_CODE_STATUS = {"not_found": 404, "not_pending": 409, "not_accepted": 409}


class CompanyBriefLineIn(BaseModel):
    section: str
    text: str
    address: str | None = None
    domain: str | None = None


class CompanyBriefDecision(BaseModel):
    decision: str                    # "accept" | "reject"
    text: str | None = None          # accept in these words instead of the proposal's


def _engine():
    if _graph is None:
        raise HTTPException(503, "no database")
    return _graph.engine


def _lines(conn, org_id: str) -> list[dict]:
    rows = conn.execute(text(
        "select line_id, section, text, address, domain, proposed_by, proposed_text, accepted_at "
        "  from company_brief_lines where org_id = :o and status = 'accepted' "
        " order by accepted_at, line_id"), {"o": org_id}).fetchall()
    return [{"line_id": r.line_id, "section": r.section, "text": r.text, "address": r.address,
             "domain": r.domain, "proposed_by": r.proposed_by, "proposed_text": r.proposed_text,
             "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None} for r in rows]


def _promote_named(org_id: str, *, address: str | None, domain: str | None) -> int:
    """Promote what the gate archived from a sender the brief now names. Returns how many."""
    from genios_engine.capture.landing.promote import ARCHIVE_CODES, promote_archived
    from genios_engine.platform.self_identity import PUBLIC_MAIL_DOMAINS

    named = domain or (address.rsplit("@", 1)[1] if address and "@" in address else None)
    if not named or named in PUBLIC_MAIL_DOMAINS:
        return 0
    engine = _engine()
    return sum(promote_archived(engine, org_id, rule=rule, sender_domain=named, apply=True).promoted
               for rule in sorted(ARCHIVE_CODES))


def _refuse(exc: Exception):
    if isinstance(exc, store.CompanyBriefError):
        raise HTTPException(_CODE_STATUS.get(exc.code, 409),
                            {"error": exc.code, "message": str(exc)}) from exc
    raise HTTPException(422, {"error": "invalid_line", "message": str(exc)}) from exc


@router.get("/v1/company-brief")
def get_company_brief(org_id: str = Depends(get_current_org)) -> dict:
    """The brief as the models read it, the lines it is made of, and what waits for a decision."""
    from genios_engine.platform.company_brief import brief_for

    with _engine().connect() as c:
        brief = brief_for(c, org_id)
        return {"version": brief.version or None, "text": brief.prompt_block(),
                "truncated": list(brief.truncated), "lines": _lines(c, org_id),
                "proposals": store.pending(c, org_id)}


@router.post("/v1/company-brief/lines", status_code=201)
def add_company_brief_line(body: CompanyBriefLineIn,
                           ctx: AuthCtx = Depends(require_account_owner)) -> dict:
    """The founder's own line, in force at once."""
    now = datetime.now(timezone.utc)
    try:
        with _engine().begin() as c:
            line_id = store.add(c, org_id=ctx.org_id, section=body.section, words=body.text,
                                address=body.address, domain=body.domain,
                                decided_by=ctx.actor_id or ctx.org_id, at=now)
    except ValueError as exc:
        _refuse(exc)
    promoted = _promote_named(ctx.org_id, address=body.address, domain=body.domain) \
        if body.section in ("connectors", "people", "watchlist") else 0
    return {"line_id": line_id, "status": store.ACCEPTED, "promoted": promoted}


@router.post("/v1/company-brief/proposals/{line_id}/decide")
def decide_company_brief_proposal(line_id: str, body: CompanyBriefDecision,
                                  ctx: AuthCtx = Depends(require_account_owner)) -> dict:
    """Accept a proposal (as written, or in the founder's own words) or reject it."""
    if body.decision not in ("accept", "reject"):
        raise HTTPException(422, {"error": "invalid_decision",
                                  "message": "decision must be accept or reject"})
    now = datetime.now(timezone.utc)
    by = ctx.actor_id or ctx.org_id
    try:
        with _engine().begin() as c:
            if body.decision == "reject":
                store.reject(c, org_id=ctx.org_id, line_id=line_id, decided_by=by, at=now)
                return {"line_id": line_id, "status": store.REJECTED, "promoted": 0}
            line = store.accept(c, org_id=ctx.org_id, line_id=line_id, decided_by=by, at=now,
                                words=body.text)
    except ValueError as exc:
        _refuse(exc)
    promoted = _promote_named(ctx.org_id, address=line.address, domain=line.domain) \
        if line.section in ("connectors", "people", "watchlist") else 0
    return {"line_id": line_id, "status": store.ACCEPTED, "promoted": promoted}


@router.delete("/v1/company-brief/lines/{line_id}")
def remove_company_brief_line(line_id: str,
                              ctx: AuthCtx = Depends(require_account_owner)) -> dict:
    """Take an accepted line out of the brief. It is kept, as removed, with the instant it stopped."""
    try:
        with _engine().begin() as c:
            store.remove(c, org_id=ctx.org_id, line_id=line_id,
                         decided_by=ctx.actor_id or ctx.org_id, at=datetime.now(timezone.utc))
    except ValueError as exc:
        _refuse(exc)
    return {"line_id": line_id, "status": store.REMOVED}
