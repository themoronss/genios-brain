"""
Phase 3: Tone-adaptive response shaper.

Rewrites bundle["context_for_agent"] and the action draft inside
bundle["suggested_action"] (when present) to match the user's emotional
state + urgency from Phase 2's IntentSignal.

Two paths:
  1. RULE-BASED FAST PATH — applies for casual/grateful/neutral or short
     payloads. No LLM call. Adds a tone wrapper / strips fluff.
  2. LLM PATH — only for frustrated / urgent / confused (where rewriting
     pays off). Single Haiku call, capped at 400 tokens.

Fail-soft: errors leave the bundle untouched.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.brain.prompts.shape import SHAPE_SYSTEM, SHAPE_USER_TEMPLATE
from app.llm import llm_client

logger = logging.getLogger(__name__)

_MAX_RESHAPE_CHARS = 4000  # don't burn tokens on giant payloads
_LLM_MODES = {"empathetic", "urgent", "supportive"}


def _emotion_to_mode(emotion: str, urgency: str) -> str:
    """Pick shaping mode from intent signal."""
    if urgency == "high":
        return "urgent"
    if emotion == "frustrated":
        return "empathetic"
    if emotion == "confused":
        return "supportive"
    if emotion == "grateful":
        return "celebratory"
    if emotion == "casual":
        return "casual"
    return "informational"


def _rule_shape(text: str, mode: str) -> str:
    """Cheap rewrites that don't need an LLM."""
    if not text:
        return text
    if mode == "casual":
        # Drop section headers, keep one-liners
        lines = [
            l for l in text.splitlines()
            if l.strip() and not l.strip().endswith(":")
        ]
        return " ".join(lines)[:1500]
    if mode == "celebratory":
        return f"Glad it helped. Quick recap:\n{text[:1500]}\n\nAnything else?"
    if mode == "informational":
        return text  # no-op — pass through
    return text


def _llm_shape(
    text: str,
    mode: str,
    emotion: str,
    urgency: str,
    org_id: Optional[str],
) -> str:
    """Single Haiku rewrite call."""
    text = (text or "").strip()
    if not text:
        return text
    if len(text) > _MAX_RESHAPE_CHARS:
        text = text[:_MAX_RESHAPE_CHARS]
    try:
        out = llm_client.call(
            org_id=org_id,
            purpose="shape_response",
            messages=[
                {"role": "system", "content": SHAPE_SYSTEM},
                {"role": "user", "content": SHAPE_USER_TEMPLATE.format(
                    emotion=emotion, urgency=urgency, mode=mode, text=text,
                )},
            ],
            temperature=0.2,
            max_tokens=600,
        )
    except Exception as e:
        logger.debug(f"shape_response LLM error: {e}")
        return text
    out = (out or "").strip()
    # Guard against the model returning an empty/junk reply
    if len(out) < min(20, len(text) // 4):
        return text
    return out


def shape_text(
    text: str,
    intent_signal,
    org_id: Optional[str] = None,
) -> str:
    """Shape a single text blob given an IntentSignal."""
    if not text or intent_signal is None:
        return text
    emotion = getattr(intent_signal, "emotion", "neutral")
    urgency = getattr(intent_signal, "urgency", "med")
    mode = _emotion_to_mode(emotion, urgency)

    if mode in _LLM_MODES:
        return _llm_shape(text, mode, emotion, urgency, org_id)
    return _rule_shape(text, mode)


def shape_bundle(bundle: dict, intent_signal) -> dict:
    """
    Apply tone shaping in-place on the bundle's user-facing fields:
      - context_for_agent
      - suggested_action.draft  (if present from payload_v2)
      - action_recommendation   (legacy field, sometimes present)
    Returns the same bundle dict.
    """
    if not bundle or intent_signal is None:
        return bundle
    org_id = bundle.get("org_id")  # may be None — shape_text tolerates that

    if bundle.get("context_for_agent"):
        bundle["context_for_agent"] = shape_text(
            bundle["context_for_agent"], intent_signal, org_id=org_id,
        )

    sa = bundle.get("suggested_action")
    if isinstance(sa, dict) and sa.get("draft"):
        sa["draft"] = shape_text(sa["draft"], intent_signal, org_id=org_id)
        bundle["suggested_action"] = sa

    if isinstance(bundle.get("action_recommendation"), str):
        bundle["action_recommendation"] = shape_text(
            bundle["action_recommendation"], intent_signal, org_id=org_id,
        )

    bundle["tone_applied"] = _emotion_to_mode(
        getattr(intent_signal, "emotion", "neutral"),
        getattr(intent_signal, "urgency", "med"),
    )
    return bundle
