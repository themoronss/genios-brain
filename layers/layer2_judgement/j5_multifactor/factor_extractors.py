"""
J5.1 — Factor Extractors

Extract factors from 5 dimensions:
  actor, org, situation, agent, tool

Each factor is a (name, category, weight, value, source_ref) tuple.
"""

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import RankedFactor


def extract_actor_factors(bundle: ContextBundle) -> list[RankedFactor]:
    """Extract factors from actor preferences and authority."""
    factors = []

    # Tone preference
    tone = bundle.memory.preferences.get("tone")
    if tone:
        factors.append(RankedFactor(
            name="preferred_tone",
            category="actor",
            weight=0.6,
            value=tone,
            source_ref="memory.preferences.tone",
        ))

    # Actor role
    role = bundle.scope.role
    if role:
        weight = 0.8 if role == "founder" else 0.5
        factors.append(RankedFactor(
            name="actor_authority",
            category="actor",
            weight=weight,
            value=role,
            source_ref="scope.role",
        ))

    return factors


def extract_org_factors(bundle: ContextBundle) -> list[RankedFactor]:
    """Extract factors from org stage and entity tiers."""
    factors = []

    # Entity tiers (VIP = high org importance)
    for entity_name, data in bundle.memory.entity_data.items():
        if isinstance(data, dict):
            tier = data.get("tier")
            if tier:
                weight = 0.9 if tier == "VIP" else 0.4
                factors.append(RankedFactor(
                    name=f"entity_tier_{entity_name}",
                    category="org",
                    weight=weight,
                    value=tier,
                    source_ref=f"memory.entity_data.{entity_name}.tier",
                ))

    return factors


def extract_situation_factors(
    bundle: ContextBundle, intent_type: str
) -> list[RankedFactor]:
    """Extract factors from current situation (urgency, channel, sentiment)."""
    factors = []

    # Last reply timing
    gmail = bundle.tools.snapshots.get("gmail", {})
    days_ago = gmail.get("last_reply_days_ago", 0)
    if days_ago > 0:
        urgency = min(1.0, days_ago / 14)  # normalize to 0-1 over 2 weeks
        factors.append(RankedFactor(
            name="time_since_last_reply",
            category="situation",
            weight=round(urgency, 2),
            value=f"{days_ago} days",
            source_ref="tools.snapshots.gmail.last_reply_days_ago",
        ))

    # Intent urgency
    intent_urgency = {"follow_up": 0.7, "reply_email": 0.8, "cold_outreach": 0.4}
    if intent_type in intent_urgency:
        factors.append(RankedFactor(
            name="intent_urgency",
            category="situation",
            weight=intent_urgency[intent_type],
            value=intent_type,
            source_ref="query_plan.intent_type",
        ))

    return factors


def extract_agent_factors(bundle: ContextBundle) -> list[RankedFactor]:
    """Extract factors about agent capability/confidence."""
    factors = []

    # Precedent success rate
    past = bundle.precedents.past_decisions
    if past:
        successes = sum(1 for p in past if p.get("outcome") == "success")
        rate = successes / len(past)
        factors.append(RankedFactor(
            name="precedent_success_rate",
            category="agent",
            weight=round(rate, 2),
            value=f"{successes}/{len(past)}",
            source_ref="precedents.past_decisions",
        ))

    return factors


def extract_tool_factors(bundle: ContextBundle) -> list[RankedFactor]:
    """Extract factors about tool availability and state."""
    factors = []

    # Tool availability
    for tool_name in bundle.tools.snapshots:
        is_stale = bundle.tools.stale_flags.get(tool_name, False)
        factors.append(RankedFactor(
            name=f"tool_{tool_name}_available",
            category="tool",
            weight=0.3 if is_stale else 0.7,
            value="stale" if is_stale else "fresh",
            source_ref=f"tools.snapshots.{tool_name}",
        ))

    return factors


def extract_all_factors(
    bundle: ContextBundle, intent_type: str
) -> list[RankedFactor]:
    """Run all factor extractors and return combined list."""
    factors = []
    factors.extend(extract_actor_factors(bundle))
    factors.extend(extract_org_factors(bundle))
    factors.extend(extract_situation_factors(bundle, intent_type))
    factors.extend(extract_agent_factors(bundle))
    factors.extend(extract_tool_factors(bundle))
    return factors
