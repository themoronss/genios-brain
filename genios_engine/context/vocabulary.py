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
