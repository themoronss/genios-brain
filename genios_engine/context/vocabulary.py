"""Canonical observation-kind vocabulary + polarity — owned by CONTEXT (layer 2).

The L2 normalizer (context/pipeline.norm_obs_kind) emits these canonical kinds; the
polarity split lives beside the vocabulary it classifies. reason/ (layer 4) imports
this DOWNWARD for derived sentiment; context/attention reads it for the attention
score. (It used to live in reason/signals_derived — which forced context to either
import upward or duplicate the sets.)"""
from __future__ import annotations

OBS_POSITIVE: frozenset[str] = frozenset({
    "budget_approved", "buying_intent", "pricing_discussed", "positive_reply",
    "champion_engaged", "next_step_agreed", "verbal_yes", "contract_requested",
    "demo_requested", "stakeholder_added", "security_review_started",
})

OBS_NEGATIVE: frozenset[str] = frozenset({
    "objection", "objection_price", "objection_timing", "objection_security",
    "objection_authority", "objection_integration", "competitor", "going_dark",
    "churn_risk", "negative_reply", "price_pushback", "stakeholder_left",
    "discount_pressure", "budget_freeze", "champion_change", "timeline_slip",
    "closed_lost_mention",
})


#: The complete set the extractor may emit — polarity-bearing kinds plus the neutral ones the
#: prompt has always asked for. Named here rather than duplicated in the prompt so a kind cannot
#: be added to one and forgotten in the other, which is precisely how `verbal_yes` came to be
#: required by a rule and emitted by nothing.
OBS_NEUTRAL: frozenset[str] = frozenset({
    "meeting_request", "followup_sent", "introduction", "question", "proposal_sent",
    "legal_review",
})

CANONICAL_OBS_KINDS: frozenset[str] = OBS_POSITIVE | OBS_NEGATIVE | OBS_NEUTRAL
