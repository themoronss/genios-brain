"""
Phase 2: Intent + Emotion classifier.

One Haiku call per query (cached 5 min in Redis). Returns structured signal
that drives:
  - bundle_builder live-fetch decision
  - response_shaper tone selection
  - suggested_action urgency tagging

Fail-soft: any error → returns the neutral default (informational/casual/med).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from pydantic import BaseModel, Field, ValidationError, confloat

from app.brain.prompts.intent import INTENT_SYSTEM, INTENT_USER_TEMPLATE
from app.llm import llm_client
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 min — same query in quick succession reuses verdict
_CACHE_PREFIX = "intent:"

# Allowed enum values — pydantic Literal would be cleaner but enums.
_INTENTS = {
    "informational", "transactional", "action_request",
    "emotional", "troubleshooting",
}
_DOMAINS = {
    "billing", "meeting", "contact", "project",
    "document", "personal", "unknown",
}
_EMOTIONS = {
    "neutral", "frustrated", "urgent", "casual", "confused", "grateful",
}
_URGENCIES = {"low", "med", "high"}


class IntentSignal(BaseModel):
    intent: str = "informational"
    domain: str = "unknown"
    emotion: str = "neutral"
    urgency: str = "med"
    requires_live_fetch: bool = False
    confidence: confloat(ge=0.0, le=1.0) = 0.5

    @classmethod
    def neutral_default(cls) -> "IntentSignal":
        return cls()


def _normalize(data: dict) -> dict:
    """Coerce values into allowed enums; clamp confidence."""
    out = dict(data)
    if out.get("intent") not in _INTENTS:
        out["intent"] = "informational"
    if out.get("domain") not in _DOMAINS:
        out["domain"] = "unknown"
    if out.get("emotion") not in _EMOTIONS:
        out["emotion"] = "neutral"
    if out.get("urgency") not in _URGENCIES:
        out["urgency"] = "med"
    out["requires_live_fetch"] = bool(out.get("requires_live_fetch", False))
    try:
        c = float(out.get("confidence", 0.5))
        out["confidence"] = max(0.0, min(1.0, c))
    except (TypeError, ValueError):
        out["confidence"] = 0.5
    return out


def _cache_key(query: str, prior: str) -> str:
    h = hashlib.md5(f"{query}|{prior}".encode("utf-8")).hexdigest()
    return f"{_CACHE_PREFIX}{h}"


def _from_cache(key: str) -> Optional[IntentSignal]:
    try:
        raw = redis_client.get(key)
    except Exception:
        return None
    if not raw:
        return None
    try:
        return IntentSignal(**json.loads(raw))
    except (json.JSONDecodeError, ValidationError):
        return None


def _to_cache(key: str, sig: IntentSignal) -> None:
    try:
        redis_client.setex(key, _CACHE_TTL, sig.model_dump_json())
    except Exception:
        pass


def _parse_llm_json(raw: str) -> Optional[dict]:
    raw = (raw or "").strip()
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
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return None


def classify(
    query: str,
    *,
    org_id: Optional[str] = None,
    prior_context: str = "",
) -> IntentSignal:
    """
    Classify the user's query. Always returns a valid IntentSignal —
    falls back to neutral default on any failure.
    """
    if not query or not query.strip():
        return IntentSignal.neutral_default()

    query = query.strip()[:1000]
    prior = (prior_context or "(none)")[:500]

    key = _cache_key(query, prior)
    cached = _from_cache(key)
    if cached is not None:
        return cached

    try:
        raw = llm_client.call(
            org_id=org_id,
            purpose="classify_intent",
            messages=[
                {"role": "system", "content": INTENT_SYSTEM},
                {"role": "user", "content": INTENT_USER_TEMPLATE.format(
                    query=query, prior_context=prior,
                )},
            ],
            temperature=0.0,
            max_tokens=200,
        )
    except Exception as e:
        logger.debug(f"intent classify LLM error: {e}")
        sig = IntentSignal.neutral_default()
        _to_cache(key, sig)
        return sig

    data = _parse_llm_json(raw)
    if not data:
        sig = IntentSignal.neutral_default()
        _to_cache(key, sig)
        return sig

    try:
        sig = IntentSignal(**_normalize(data))
    except ValidationError:
        sig = IntentSignal.neutral_default()

    _to_cache(key, sig)
    return sig
