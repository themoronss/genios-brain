"""
J1.4 — Question Generator

Generate minimal clarifying questions from missing/stale fields.
Produces NeedMoreInfo output.
"""

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import NeedMoreInfo, ClarifyingQuestion
from layers.layer2_judgement.j1_sufficiency.required_fields import (
    validate_required_fields,
)
from layers.layer2_judgement.j1_sufficiency.staleness_detector import (
    detect_stale_data,
)


def check_sufficiency(
    bundle: ContextBundle, intent_type: str
) -> NeedMoreInfo:
    """
    Full J1 pipeline: check required fields + staleness → generate questions.

    Args:
        bundle: ContextBundle from Layer 1.
        intent_type: Canonical intent type.

    Returns:
        NeedMoreInfo with value=True if action is blocked.
    """
    questions = []

    # 1. Check required fields
    missing_fields = validate_required_fields(bundle, intent_type)
    for field in missing_fields:
        questions.append(ClarifyingQuestion(
            question=f"Missing required data: {field['label']}",
            reason=f"Field '{field['field']}' is empty or missing",
            blocking_field=field["field"],
        ))

    # 2. Check staleness
    stale_data = detect_stale_data(bundle)
    for stale in stale_data:
        questions.append(ClarifyingQuestion(
            question=f"Data from {stale['tool']} may be outdated. Refresh?",
            options=["Refresh data", "Proceed anyway"],
            reason=stale["reason"],
            blocking_field=f"tools.{stale['tool']}",
        ))

    return NeedMoreInfo(
        value=len(questions) > 0,
        questions=questions,
    )
