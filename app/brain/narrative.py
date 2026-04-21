"""Narrative packer — called by the Pull API for medium/long packs.

Respects the remaining deadline budget: if less than 150ms remains of the
400ms pull window, skip the LLM call and return None. Caller strips the
narrative field on skip.

Result is cached in Redis 5min keyed on (org, entity, fact-fingerprint) to
deduplicate repeated pulls within the TTL window.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from app.brain.prompts.narrative import NARRATIVE_SYSTEM, NARRATIVE_USER_TEMPLATE
from app.llm import llm_client
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes
_NARRATIVE_MIN_BUDGET_MS = 150


def _cache_key(org_id: str, entity: str, facts: list[dict]) -> str:
    payload = json.dumps([f.get("id") or f.get("summary") for f in facts], default=str)
    h = hashlib.sha1(payload.encode()).hexdigest()[:16]
    return f"narrative:{org_id}:{entity}:{h}"


def _format_facts(facts: list[dict], limit: int) -> str:
    out = []
    for f in facts[:limit]:
        ts = f.get("interaction_at") or ""
        desc = (f.get("summary") or f.get("title") or "").strip()
        if not desc:
            continue
        out.append(f"- {ts}: {desc}"[:200])
    return "\n".join(out)


def build_narrative(
    *,
    org_id: str,
    entity: str,
    facts: list[dict],
    pack_size: str = "medium",
    remaining_ms: int = 10_000,
) -> Optional[str]:
    """Return a short briefing string, or None if budget/facts insufficient."""
    if remaining_ms < _NARRATIVE_MIN_BUDGET_MS:
        return None
    if not facts:
        return None

    limit = 40 if pack_size == "long" else 15
    sentences = "4-6" if pack_size == "long" else "2-3"

    key = _cache_key(org_id, entity, facts[:limit])
    try:
        cached = redis_client.get(key)
        if cached:
            return cached
    except Exception:
        pass

    user_prompt = NARRATIVE_USER_TEMPLATE.format(
        entity=entity,
        facts=_format_facts(facts, limit),
        sentences=sentences,
    )
    try:
        out = llm_client.call(
            org_id=org_id, purpose="narrative",
            messages=[
                {"role": "system", "content": NARRATIVE_SYSTEM},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.2, max_tokens=300,
        )
    except Exception as e:
        logger.warning(f"narrative build failed: {e}")
        return None

    out = (out or "").strip()
    if not out:
        return None

    try:
        redis_client.set(key, out, ex=_CACHE_TTL)
    except Exception:
        pass
    return out
