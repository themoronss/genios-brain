"""LLM reasoner.

Takes one candidate + supporting facts + precedents, calls
`llm_client.call(purpose="reason_haiku")`, returns a validated
ReasonResult. Respects GENIOS_REASONER_ENABLED — when off, returns
keep=False immediately (router still proceeds but skips LLM cost).
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError, confloat

from app import config
from app.brain.prompts.reason import REASON_SYSTEM, REASON_USER_TEMPLATE
from app.context.precedent_search import search_precedents, search_precedents_any
from app.llm import llm_client

logger = logging.getLogger(__name__)


class ReasonResult(BaseModel):
    keep: bool = False
    confidence: confloat(ge=0.0, le=1.0) = 0.0
    reason: str = ""
    action: str = ""
    subject_importance: confloat(ge=0.0, le=1.0) = 0.0
    time_urgency: confloat(ge=0.0, le=1.0) = 0.0
    novelty: confloat(ge=0.0, le=1.0) = 0.0


def _format_facts(facts: list[dict]) -> str:
    if not facts:
        return "(none)"
    lines = []
    for f in facts[:10]:
        ts = f.get("interaction_at") or f.get("ts") or ""
        desc = f.get("summary") or f.get("title") or ""
        lines.append(f"- {ts}: {desc}"[:240])
    return "\n".join(lines)


def _format_precedents(precedents: list[dict]) -> str:
    if not precedents:
        return "(none)"
    lines = []
    for p in precedents[:3]:
        lines.append(
            f"- success_rate={p.get('success_rate', 'n/a')} "
            f"action={(p.get('action_taken') or '')[:120]}"
        )
    return "\n".join(lines)


def _call_llm(candidate: dict, facts: list, precedents: list, attempt_temp: float) -> str:
    user_prompt = REASON_USER_TEMPLATE.format(
        candidate=json.dumps(candidate, default=str)[:2000],
        facts=_format_facts(facts),
        precedents=_format_precedents(precedents),
    )
    return llm_client.call(
        org_id=candidate.get("org_id"),
        purpose="reason_haiku",
        messages=[
            {"role": "system", "content": REASON_SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=attempt_temp,
        max_tokens=400,
    )


def _parse(raw: str) -> Optional[ReasonResult]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw.strip())
        return ReasonResult(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"reason parse failed: {e}")
        return None


def reason(db, candidate: dict, facts: list[dict] | None = None) -> ReasonResult:
    """Run reasoner on a candidate. Never raises; returns keep=False on failure."""
    if not config.GENIOS_REASONER_ENABLED:
        return ReasonResult(keep=False, reason="reasoner_disabled")

    facts = facts or []
    try:
        # Prefer v2 structured lookup (precedent_situations) when GENIOS_PRECEDENTS_V2
        # is on; falls back to v1 document-chunk search otherwise. See
        # `app/context/precedent_search.py::search_precedents_any`.
        meta = candidate.get("metadata") or {}
        precedents = search_precedents_any(
            db,
            candidate.get("org_id"),
            candidate.get("title") or "",
            stage=meta.get("stage") or (facts[0].get("stage") if facts else None),
            situation_category=candidate.get("insight_type"),
            entity_type=meta.get("entity_type"),
            sentiment_bucket=meta.get("sentiment_bucket"),
            limit=3,
        ) or []
    except Exception as e:
        logger.debug(f"precedent search failed: {e}")
        precedents = []

    first_pass: Optional[ReasonResult] = None
    for temp in (0.2, 0.0):  # retry once at temp=0 on parse fail
        try:
            raw = _call_llm(candidate, facts, precedents, temp)
        except Exception as e:
            logger.warning(f"reasoner LLM error: {e}")
            return ReasonResult(keep=False, reason="llm_error")
        first_pass = _parse(raw)
        if first_pass is not None:
            break

    if first_pass is None:
        return ReasonResult(keep=False, reason="parse_failed")

    # Phase 3.4 — Sonnet cascade (dormant until Anthropic routed + flag on).
    try:
        from app.brain import cascade as cascade_mod
        if cascade_mod.should_escalate(first_pass):
            sonnet_result = cascade_mod.escalate(candidate, first_pass, facts, precedents)
            if sonnet_result is not None:
                return sonnet_result
    except Exception as e:
        logger.debug(f"cascade skipped: {e}")

    return first_pass
