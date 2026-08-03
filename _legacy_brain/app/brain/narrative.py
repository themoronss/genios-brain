"""Narrative packer — used by /v1/context for medium/long packs.

As of Phase 4 cost optimization, the default path is *programmatic*:
we synthesize a 1-2 sentence headline from already-known contact metadata
(stage, last interaction, sentiment, open commitments) without an LLM
call. This is what dashboard humans actually need — a quick at-a-glance
summary — and it costs zero tokens.

The previous LLM-generated narrative is still available under the env
flag GENIOS_NARRATIVE_USE_LLM=true. It produced more polished prose but
was burning ~37K tokens/day for a single active org via the brain
router's automatic bundle refresh — the dollar/quality trade-off does
not work out on free Groq tiers.

Cache: results are stored in Redis under a date-stamped key
(narrative:v2:{org}:{entity}:{YYYYMMDD}) for a 1-hour TTL. Same entity
queried multiple times on the same day reuses the same headline.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Iterable

from app.redis_client import redis_client

logger = logging.getLogger(__name__)

_CACHE_TTL = 3600  # 1 hour
_NARRATIVE_MIN_BUDGET_MS = 50  # programmatic path is cheap
_USE_LLM = os.getenv("GENIOS_NARRATIVE_USE_LLM", "false").lower() in ("1", "true", "yes")


# ── Cache keys ────────────────────────────────────────────────────────────────

def _cache_key(org_id: str, entity: str) -> str:
    """Date-stamped key: same entity on same day reuses the same narrative.

    Falls back to a stable hash if the entity string contains odd chars.
    """
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    safe = (entity or "").lower().strip()
    if not safe.isascii() or len(safe) > 100:
        safe = hashlib.sha1(entity.encode()).hexdigest()[:16]
    return f"narrative:v2:{org_id}:{safe}:{today}"


# ── Programmatic narrative ────────────────────────────────────────────────────

def _sentiment_word(value) -> str:
    if value is None:
        return ""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if v >= 0.4:
        return "positive"
    if v <= -0.3:
        return "declining"
    if v <= -0.1:
        return "cooling"
    return "neutral"


def _days_ago(ts) -> Optional[int]:
    if not ts:
        return None
    try:
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        return max(0, delta.days)
    except Exception:
        return None


def _last_interaction(facts: Iterable[dict]) -> Optional[dict]:
    latest = None
    for f in facts or []:
        ts = f.get("interaction_at")
        if not ts:
            continue
        if latest is None or str(ts) > str(latest.get("interaction_at") or ""):
            latest = f
    return latest


def _build_programmatic(entity: str, facts: list[dict], meta: Optional[dict]) -> Optional[str]:
    """Compose a 1-2 sentence headline from known data — no LLM required."""
    if not entity and not facts and not meta:
        return None

    meta = meta or {}
    last = _last_interaction(facts)
    last_days = _days_ago(meta.get("last_interaction_at") or (last.get("interaction_at") if last else None))
    stage = (meta.get("stage") or meta.get("relationship_stage") or "").upper()
    sentiment = _sentiment_word(meta.get("sentiment_ewma") if meta.get("sentiment_ewma") is not None else meta.get("sentiment"))
    open_commitments = int(meta.get("open_commitments") or 0)
    last_subject = (meta.get("last_subject") or (last.get("title") if last else "") or (last.get("summary") if last else "") or "").strip()

    parts: list[str] = []

    # Sentence 1 — contact + stage + recency
    head = entity or "Contact"
    if stage:
        head_phrase = f"{head} — {stage}"
    else:
        head_phrase = head
    if last_days is not None:
        if last_days == 0:
            recency = "last contact today"
        elif last_days == 1:
            recency = "last contact yesterday"
        else:
            recency = f"last contact {last_days} days ago"
        head_phrase = f"{head_phrase}, {recency}"
    parts.append(head_phrase + ".")

    # Sentence 2 — subject + sentiment + commitments (whichever signals exist)
    tail_bits: list[str] = []
    if last_subject:
        tail_bits.append(f"latest topic: \"{last_subject[:80]}\"")
    if sentiment and sentiment != "neutral":
        tail_bits.append(f"sentiment {sentiment}")
    if open_commitments > 0:
        plural = "s" if open_commitments != 1 else ""
        tail_bits.append(f"{open_commitments} open commitment{plural}")
    if tail_bits:
        parts.append((" · ".join(tail_bits)).capitalize() + ".")

    if not parts:
        return None
    return " ".join(parts)


# ── LLM fallback (opt-in) ─────────────────────────────────────────────────────

def _build_llm(entity: str, facts: list[dict], pack_size: str) -> Optional[str]:
    from app.brain.prompts.narrative import NARRATIVE_SYSTEM, NARRATIVE_USER_TEMPLATE
    from app.llm import llm_client

    limit = 40 if pack_size == "long" else 15
    sentences = "4-6" if pack_size == "long" else "2-3"

    fact_lines = []
    for f in (facts or [])[:limit]:
        ts = f.get("interaction_at") or ""
        desc = (f.get("summary") or f.get("title") or "").strip()
        if desc:
            fact_lines.append(f"- {ts}: {desc}"[:200])
    formatted = "\n".join(fact_lines)

    user_prompt = NARRATIVE_USER_TEMPLATE.format(
        entity=entity, facts=formatted, sentences=sentences,
    )
    try:
        out = llm_client.call(
            org_id=None, purpose="narrative",
            messages=[
                {"role": "system", "content": NARRATIVE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2, max_tokens=300,
        )
    except Exception as e:
        logger.warning(f"narrative LLM build failed: {e}")
        return None
    return (out or "").strip() or None


# ── Public entry point ────────────────────────────────────────────────────────

def build_narrative(
    *,
    org_id: str,
    entity: str,
    facts: list[dict],
    contact_meta: Optional[dict] = None,
    pack_size: str = "medium",
    remaining_ms: int = 10_000,
) -> Optional[str]:
    """Return a short briefing string, or None if data is too thin.

    Default path is programmatic (zero LLM tokens). Set
    GENIOS_NARRATIVE_USE_LLM=true to restore the LLM-backed version.
    """
    if remaining_ms < _NARRATIVE_MIN_BUDGET_MS:
        return None

    # Cache lookup — same entity on the same day reuses the same narrative.
    key = _cache_key(org_id, entity)
    try:
        cached = redis_client.get(key)
        if cached:
            return cached if isinstance(cached, str) else cached.decode("utf-8", "ignore")
    except Exception:
        pass

    out: Optional[str]
    if _USE_LLM:
        out = _build_llm(entity, facts, pack_size)
        if not out:  # LLM failed — fall through to programmatic
            out = _build_programmatic(entity, facts, contact_meta)
    else:
        out = _build_programmatic(entity, facts, contact_meta)

    if not out:
        return None

    try:
        redis_client.set(key, out, ex=_CACHE_TTL)
    except Exception:
        pass
    return out
