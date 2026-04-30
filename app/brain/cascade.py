"""Cascade: Haiku → Sonnet (dormant by default).

Phase 3 wires the infrastructure. It only runs when
GENIOS_CASCADE_ENABLED=true AND the purpose `reason_sonnet` is routed to
Anthropic. On Groq (today) there's no meaningful haiku/sonnet split, so
`should_escalate` stays False regardless of the flag.

When Phase 1.5 flips ROUTES to Anthropic and the flag goes true, cascade
activates automatically — no code change needed.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from pydantic import ValidationError

from app import config
from app.brain.prompts.reason_sonnet import SONNET_SYSTEM, SONNET_USER_TEMPLATE
from app.brain.reasoner import ReasonResult
from app.llm import llm_client
from app.llm.client import ROUTES

logger = logging.getLogger(__name__)

GREY_BAND = (0.45, 0.75)  # confidences where Sonnet adds signal


def should_escalate(result: ReasonResult) -> bool:
    """True when the flag is on AND Sonnet is actually on Anthropic."""
    if not config.GENIOS_CASCADE_ENABLED:
        return False
    provider, _ = ROUTES.get("reason_sonnet", ("groq", ""))
    if provider != "anthropic":
        return False
    return GREY_BAND[0] <= result.confidence <= GREY_BAND[1]


def escalate(
    candidate: dict,
    first_pass: ReasonResult,
    facts: list,
    precedents: list,
) -> Optional[ReasonResult]:
    """Run the Sonnet pass. Returns None if the call or parse fails."""
    try:
        raw = llm_client.call(
            org_id=candidate.get("org_id"),
            purpose="reason_sonnet",
            messages=[
                {"role": "system", "content": SONNET_SYSTEM},
                {"role": "user",   "content": SONNET_USER_TEMPLATE.format(
                    candidate=json.dumps(candidate, default=str)[:2000],
                    first_pass=first_pass.model_dump_json(),
                    facts="\n".join(str(f)[:200] for f in facts[:10]) or "(none)",
                    precedents="\n".join(str(p)[:200] for p in precedents[:3]) or "(none)",
                )},
            ],
            temperature=0.1, max_tokens=500,
        )
    except Exception as e:
        logger.warning(f"cascade sonnet call failed: {e}")
        return None

    raw = raw.strip()
    if "```" in raw:
        chunks = raw.split("```")
        raw = chunks[1] if len(chunks) >= 3 else chunks[-1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    if not raw.lstrip().startswith("{"):
        lo, hi = raw.find("{"), raw.rfind("}")
        if lo >= 0 and hi > lo:
            raw = raw[lo:hi + 1]
    try:
        data = json.loads(raw.strip())
        result = ReasonResult(**data)
        # Mark this result as having gone through the Sonnet escalation so
        # downstream observability and the learning loop can distinguish it.
        if result.escalation_reason is None:
            result.escalation_reason = "grey_band_confidence"
        return result
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"cascade sonnet parse failed: {e}")
        return None
