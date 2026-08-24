"""g-i-4 Proactive Analysis — the push engine.

Per MD g-i-4 §0: "Value = FILTERING, not generation." 90% of insights are noise;
the prioritizer is the make-or-break component. One insight that matters beats
ten that don't.

Pipeline:
    scheduler(cron OR memory webhook)
        -> generate(g-i-2 over g-i-3.diff'd subgraph only)
        -> dedupe(signature + hysteresis + stale-retract)
        -> foresight(premortem + base-rate/qualitative)
        -> prioritize(multiplicative + KL-novelty + VoI + suppression)
        -> deliver(80/20 + channel discipline + per-user budget)

Public API:
    from core.proactive import (
        Insight, InsightSignature, InsightType, DeliveryRoute,
        generate_for_subgraph,
        dedupe_batch, DedupeResult,
        compute_premortem, ForesightMode, ForesightResult,
        prioritize_insight, PriorityScore,
        deliver_insight, ChannelDecision,
        check_workflow_drift, DriftReport,
        FeedbackStore,
    )
"""

from core.proactive.dedupe import DedupeResult, dedupe_batch
from core.proactive.deliver import ChannelDecision, deliver_insight
from core.proactive.drift import DriftReport, check_workflow_drift
from core.proactive.feedback_store import FeedbackStore
from core.proactive.foresight import ForesightMode, ForesightResult, compute_premortem
from core.proactive.generate import generate_for_subgraph
from core.proactive.prioritize import PriorityScore, prioritize_insight
from core.proactive.types import DeliveryRoute, Insight, InsightSignature, InsightType

__all__ = [
    "ChannelDecision",
    "DedupeResult",
    "DeliveryRoute",
    "DriftReport",
    "FeedbackStore",
    "ForesightMode",
    "ForesightResult",
    "Insight",
    "InsightSignature",
    "InsightType",
    "PriorityScore",
    "check_workflow_drift",
    "compute_premortem",
    "dedupe_batch",
    "deliver_insight",
    "generate_for_subgraph",
    "prioritize_insight",
]
