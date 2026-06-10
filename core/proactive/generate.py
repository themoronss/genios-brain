"""Generate candidate insights by reusing g-i-2 engine over the affected subgraph.

Per MD g-i-4 §1.1.1: NO new reasoning code in g-i-4 — reuse g-i-2's ForwardChainer.
The proactive layer's job is FILTERING + DELIVERY, not generation.

This module:
1. Builds the fact dict from the affected subgraph (caller-provided extractor hook)
2. Runs ForwardChainer with the active module's rules
3. Each fired rule -> one candidate Insight (raw, before dedupe + prioritize)
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from core.foundations.telemetry import get_logger
from core.proactive.scheduler import AffectedSubgraph
from core.proactive.types import Insight, InsightType
from core.reasoning.rule_engine import ForwardChainer
from core.reasoning.rule_loader import RuleSet

log = get_logger(__name__)


# Caller-supplied: given a subgraph + session, returns the fact dict the engine reasons on.
# This lets the proactive layer stay generic — different modules extract different facts.
FactExtractor = Callable[[AffectedSubgraph], dict[str, Any]]


def generate_for_subgraph(
    *,
    org_id: str,
    subgraph: AffectedSubgraph,
    ruleset: RuleSet,
    fact_extractor: FactExtractor,
    insight_type_for_conclusion: Callable[[str], InsightType] | None = None,
) -> list[Insight]:
    """Run g-i-2 over the affected subgraph; produce raw candidate insights.

    Args:
        org_id: per-org scoping
        subgraph: AffectedSubgraph from scheduler.compute_affected_subgraph
        ruleset: the module's loaded rules
        fact_extractor: caller's mapper from subgraph -> fact dict
        insight_type_for_conclusion: optional classifier; default treats all as RISK

    Returns:
        list[Insight], possibly empty. NOT yet deduped, prioritized, or routed.
    """
    if subgraph.is_empty:
        return []

    classifier = insight_type_for_conclusion or _default_classify_type
    facts = fact_extractor(subgraph)
    if not facts:
        log.debug("proactive_generate_no_facts", org_id=org_id)
        return []

    result = ForwardChainer(ruleset).run(facts)
    if not result.resolved:
        return []

    insights: list[Insight] = []
    now = datetime.now(UTC)
    for step in result.proof.steps:
        primary = _primary_entity_from_step(step.matched_facts) or "unknown"
        ins = Insight(
            id=str(uuid.uuid4()),
            org_id=org_id,
            type=classifier(step.conclusion),
            primary_entity=primary,
            root_cause_edge="",  # filled later by g-i-3 graph lookup if available
            derivation_chain=[
                {
                    "rule_id": s.rule_id,
                    "rule_module": s.rule_module,
                    "rule_priority": s.rule_priority,
                    "conclusion": s.conclusion,
                    "matched_facts": s.matched_facts,
                    "reason": s.reason,
                    "hard": s.hard,
                }
                for s in result.proof.steps
            ],
            grounding_refs=[],
            created_at=now,
        )
        insights.append(ins)

    log.info(
        "proactive_generated_insights",
        org_id=org_id,
        n_insights=len(insights),
        n_rules_fired=len(result.proof.steps),
    )
    return insights


# ─── helpers ────────────────────────────────────────────────────────────────


def _default_classify_type(conclusion: str) -> InsightType:
    """Best-effort: 'block'/'risk' keywords -> RISK; 'opportunity' -> OPPORTUNITY; else MISALIGNMENT."""
    c = conclusion.lower()
    if any(k in c for k in ("risk", "stall", "block", "churn", "escalate", "overdue", "disengag")):
        return InsightType.RISK
    if any(k in c for k in ("opportunity", "approved", "upsell", "expand")):
        return InsightType.OPPORTUNITY
    return InsightType.MISALIGNMENT


def _primary_entity_from_step(matched_facts: dict[str, Any]) -> str:
    """Pick a primary entity reference from the matched facts (best-effort)."""
    for key in ("account_name", "deal_id", "contact_id", "primary_entity", "account_id"):
        if key in matched_facts:
            return str(matched_facts[key])
    return ""
