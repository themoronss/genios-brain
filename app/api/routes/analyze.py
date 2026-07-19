"""/v1/intelligence/analyze — deep, human-level analysis of ONE contact.

This is the 'true intelligence' layer. It reuses build_context_bundle (which
pulls the contact's graph facts PLUS live Gmail/Calendar) and hands that REAL
context to Sonnet acting as the founder's chief-of-staff — so the output is
specific, situation-aware advice ("they asked about pricing on Jun 10, you
haven't replied — send it today"), not a templated reminder.

Rationed by design: called on-demand for the contact the user is looking at
(the extension), and the answer is cached briefly. Signals decide WHO is worth
this call; this endpoint is the deep think.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.context.bundle_builder import build_context_bundle
from app.llm import llm_client
from app.llm_guard import call_with_timeout

logger = logging.getLogger(__name__)
router = APIRouter()

# Grounded in the sales module's proven plays (modules/sales — MEDDIC
# qualification, velocity, competition, pricing). This is the SAME expertise the
# rule engine encodes, applied by an LLM to REAL email context (which the rules
# can't see) — so the extension/agent get expert output on live data.
_SYSTEM = (
    "You are a world-class B2B sales advisor embedded in the founder's tools. "
    "You are given the REAL context (emails, calendar, history) for ONE "
    "contact/deal. Reason like a top rep using proven plays:\n"
    "- Late stage (proposal/negotiation) with no economic buyer engaged or no "
    "confirmed budget → qualification risk; get the economic buyer or confirm budget.\n"
    "- Single-threaded on a real deal → multi-thread before it slips.\n"
    "- No next step scheduled → book one now.\n"
    "- Stalled 21+ days in a late stage, or silent 7+ days after you sent something → "
    "it's stalling; switch channel (call, don't email) and give a concrete reason to move.\n"
    "- Went quiet right after pricing → buying-signal stall, not a loss; de-risk "
    "(pilot/proof), don't reflexively discount.\n"
    "- Competitor named with nothing reciprocal → you may be losing; differentiate on "
    "their stated pain.\n"
    "- Discount >=20% asked on a first deal → protect margin; trade for term/commitment.\n\n"
    "Reply in 2-4 short sentences: first the REAL situation (cite specifics from the "
    "context — what was said, who owes a reply, the stage), then ONE concrete next move "
    "naming the person/company and a specific action. If the user is reviewing a draft, "
    "say what's weak or missing and how to fix it. If it can be automated (reminder / "
    "follow-up), say so in a few words. No generic advice, no fluff, no preamble."
)


@router.get("/v1/intelligence/analyze")
def analyze_contact(
    contact: str = Query(..., min_length=1, description="Contact / company name"),
    situation: str | None = Query(None, description="Optional what-you're-doing hint"),
    deep: bool = Query(False, description="Use Sonnet (slower/costlier) vs Haiku default"),
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Analyse one contact from real (graph + live Gmail) context.

    Cost-first: Haiku by default (~10x cheaper); `deep=true` escalates to Sonnet
    only when the user asks for a deeper take. On-demand + client-cached.
    """
    try:
        bundle = build_context_bundle(db, org_id, contact, situation=situation or "")
    except Exception as e:  # noqa: BLE001 — context miss must not 500
        logger.warning("analyze_bundle_failed contact=%s err=%s", contact, e)
        bundle = None

    ctx = (bundle or {}).get("context_for_agent") or ""
    sit = (situation or "").strip()
    # With a draft/situation we can still help even if there's no cached context.
    if not ctx.strip() and not sit:
        return {
            "contact": contact,
            "suggestion": None,
            "note": "No context found for this contact yet.",
        }

    user_prompt = (
        f"Contact: {contact}\n\n"
        f"Context (from emails / calendar / history):\n{ctx[:6000] or '(no cached context)'}\n\n"
        + (f"What the user is doing right now: {sit[:2500]}\n\n" if sit else "")
        + "Give the real situation and the single best next move. If the user is "
        "reviewing a draft message, say what's weak or missing and how to fix it — "
        "specific to this context, not generic."
    )

    def _run() -> str:
        return llm_client.call(
            org_id=org_id,
            purpose="reason_sonnet" if deep else "reason_haiku",  # cheap by default
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=350,
        ).strip()

    try:
        suggestion = call_with_timeout(_run, fallback=None)
    except Exception as e:  # noqa: BLE001
        logger.warning("analyze_llm_failed contact=%s err=%s", contact, e)
        suggestion = None

    if not suggestion:
        raise HTTPException(status_code=503, detail="Analysis unavailable — try again.")

    return {"contact": contact, "suggestion": suggestion, "model": "sonnet" if deep else "haiku"}
