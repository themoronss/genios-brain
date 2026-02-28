"""
D1.4 — Intent Finalizer

Lock intent_type + slots using judgement signals.
If confidence is too low or info is missing, downgrade to ask_clarifying.
"""

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import JudgementReport
from layers.layer3_decision.d1_intent.slot_extractor import extract_slots


def finalize_intent(
    bundle: ContextBundle,
    judgement: JudgementReport,
    route: dict,
) -> tuple[str, dict[str, str]]:
    """
    Finalize the intent type and extract slots.

    If judgement says we need more info, the intent is kept but slots
    may be incomplete — the execution mode will handle this.

    Args:
        bundle: ContextBundle from Layer 1.
        judgement: JudgementReport from Layer 2.
        route: Route from D0.

    Returns:
        Tuple of (intent_type, slots_dict).
    """
    intent_type = route["intent_type"]

    # Extract slots
    slots = extract_slots(bundle, intent_type)

    # If judgement detected missing info, mark incomplete slots
    if judgement.need_more_info.value:
        for q in judgement.need_more_info.questions:
            field = q.blocking_field
            if field and field not in slots:
                slots[f"missing_{field}"] = q.question

    return intent_type, slots
