"""
J0.1 — Plan Builder

Build a JudgementPlan from ContextBundle:
  - which checks to run
  - which thresholds to use
  - what org_mode applies
"""

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_plan import JudgementPlan
from layers.layer2_judgement.j0_judgement_planner.thresholds import (
    RISK_AUTO_EXECUTE_MAX,
    RISK_HIGH_THRESHOLD,
    PRIORITY_MIN_SCORE,
    APPROVAL_REQUIRED_RISK_THRESHOLD,
)


# Intent types that always require all checks
_FULL_CHECK_INTENTS = {"follow_up", "cold_outreach", "reply_email", "send_email"}

# Intent types that can skip some checks
_LIGHT_CHECK_INTENTS = {"schedule_meeting", "general"}


def build_judgement_plan(bundle: ContextBundle) -> JudgementPlan:
    """
    Build a JudgementPlan from the ContextBundle.

    Determines which checks are mandatory and sets thresholds
    based on entity tiers and intent type.

    Args:
        bundle: Complete ContextBundle from Layer 1.

    Returns:
        JudgementPlan controlling which J-modules run.
    """
    # Detect intent type from the bundle's query_plan or scope
    intent_type = _detect_intent_type(bundle)

    # Determine org mode (MVP: always default)
    org_mode = "default"

    # Determine which checks to run
    required_checks = _determine_required_checks(intent_type, bundle)

    # Set thresholds
    thresholds = {
        "risk_auto_execute_max": RISK_AUTO_EXECUTE_MAX,
        "risk_high_threshold": RISK_HIGH_THRESHOLD,
        "priority_min_score": PRIORITY_MIN_SCORE,
        "approval_required_risk": APPROVAL_REQUIRED_RISK_THRESHOLD,
    }

    return JudgementPlan(
        intent_type=intent_type,
        required_checks=required_checks,
        thresholds=thresholds,
        org_mode=org_mode,
    )


def _detect_intent_type(bundle: ContextBundle) -> str:
    """Extract intent type from bundle. Uses query_plan_ref if available."""
    if bundle.query_plan_ref and bundle.query_plan_ref.get("intent_type"):
        return bundle.query_plan_ref["intent_type"]
    return "general"


def _determine_required_checks(intent_type: str, bundle: ContextBundle) -> list[str]:
    """Decide which J-module checks are mandatory."""
    # Always run these
    checks = ["sufficiency", "policy", "risk"]

    # Full-check intents also get priority + multifactor
    if intent_type in _FULL_CHECK_INTENTS:
        checks.extend(["priority", "multifactor"])
    elif intent_type in _LIGHT_CHECK_INTENTS:
        checks.append("priority")
    else:
        checks.extend(["priority", "multifactor"])

    return checks
