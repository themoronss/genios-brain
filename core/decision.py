"""The engine pipeline — orchestration only. No reasoning logic here.

Per MD g-i-2 §1 the 11 steps:
    1. EXTRACT FACTS      caller supplies; we accept dict[str, Any]
    2. LOAD GRAPH         caller supplies graph version (defaults to current)
    3. SYMBOLIC PASS      ForwardChainer
    4. NEURAL PASS        Gateway (only on unresolved + gap-fill wiring)
    5. FUSION             fuse() — symbolic wins
    6. CONFIDENCE         ConfidenceScorer
    7. GUARDRAILS         check_hard_constraints + verify_grounding
    8. ROUTE 80/20        route_decision (persona redlines force flag)
    9. REFLECT            selective (stakes * (1-conf) > theta)
   10. EMIT               persist DecisionRow + return Decision pydantic
   11. CAPTURE            (separate API call when human overrides; see capture_correction)

Public API:
    from core.decision import decide, DecideRequest, DecideResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.decision_store import DecisionRow
from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.graph.store import current_version
from core.guardrails.constraints import check_hard_constraints
from core.guardrails.grounding import verify_grounding
from core.neural.confidence import ConfidenceScorer
from core.neural.fusion import fuse
from core.neural.gateway import Gateway, RoutingChoice
from core.reasoning.derivation import ProofTree
from core.reasoning.rule_engine import ChainResult, ForwardChainer
from core.reasoning.rule_loader import RuleSet
from core.reflection.human_flag import Route, RoutingDecision, route_decision
from core.reflection.trigger import should_reflect

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DecideRequest:
    """Inputs to one decide() call. Pure data; no I/O at construction."""

    org_id: str
    query: dict[str, Any]  # caller-defined shape (e.g. {"question": "...", "deal_id": "..."})
    facts: dict[str, Any]  # extracted facts the engine reasons over
    ruleset: RuleSet
    module_id: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    triggered_by: str = "query"  # query | proactive_scan | webhook
    # Optional neural-fallback wiring (per Gateway contract)
    gap_description: str | None = None
    gap_facts: dict[str, Any] | None = None
    neural_system_prompt: str | None = None
    neural_output_schema: type[BaseModel] | None = None
    # Routing context
    reversible: bool = True
    user_redlines_hit: list[str] = field(default_factory=list)
    irreversibility: float = 0.5  # used only in reflection trigger
    blast_radius: float = 0.5
    # Optional scope subgraph (g-i-4 incremental scoping) — placeholder for v1
    scope_filter: dict[str, Any] | None = None


@dataclass(frozen=True)
class DecideResult:
    """The emitted Decision + full audit trail."""

    decision_id: str
    conclusion: str
    path: str  # symbolic | neural | hybrid
    route: Route
    confidence: float
    confidence_breakdown: dict[str, Any]
    proof: ProofTree
    grounding_score: float
    grounding_refs: list[str]
    routing: RoutingDecision
    reflected: bool
    as_of_version: int
    halted_by_cost_guard: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# The pipeline
# ─────────────────────────────────────────────────────────────────────────────


def decide(
    session: Session,
    *,
    gateway: Gateway,
    request: DecideRequest,
    scorer: ConfidenceScorer | None = None,
) -> DecideResult:
    """Run the full 11-step engine pipeline. Persists the DecisionRow before returning."""
    scorer = scorer or ConfidenceScorer()

    # Steps 1-2 are caller-supplied (request.facts) + as_of pinning
    as_of_v = current_version(session, request.org_id)

    # Step 3: SYMBOLIC PASS
    symbolic: ChainResult = ForwardChainer(request.ruleset).run(request.facts)

    # Step 4: NEURAL PASS (only if symbolic unresolved + caller wired neural)
    gateway_result = gateway.route(
        org_id=request.org_id,
        symbolic_result=symbolic,
        gap_description=request.gap_description,
        gap_facts=request.gap_facts,
        system_prompt=request.neural_system_prompt,
        output_schema=request.neural_output_schema,
    )
    halted = gateway_result.route == RoutingChoice.HALTED
    neural_conclusion: str | None = None
    if (
        gateway_result.route == RoutingChoice.NEURAL_GAP_FILL
        and gateway_result.parsed_output is not None
    ):
        # Caller's schema is responsible for having a 'conclusion'-equivalent field;
        # we extract via duck-typing on common names.
        neural_conclusion = _extract_neural_conclusion(gateway_result.parsed_output)

    # Step 7-pre: GUARDRAILS (hard constraints) on candidate (neural or symbolic)
    candidate = (
        neural_conclusion if neural_conclusion is not None else symbolic.proof.final_conclusion
    )
    constraint_check = check_hard_constraints(
        org_id=request.org_id,
        ruleset=request.ruleset,
        facts=request.facts,
        candidate_conclusion=candidate or "",
    )
    neural_violates = neural_conclusion is not None and not constraint_check.ok

    # Step 5: FUSION
    fusion = fuse(
        symbolic=symbolic,
        neural_conclusion=neural_conclusion,
        neural_violates_hard=neural_violates,
    )
    final_conclusion = fusion.chosen_conclusion
    path = _path_from_fusion(symbolic, neural_conclusion, fusion.winner)

    # Step 7-post: GROUNDING (verify the chosen conclusion's claims map to facts)
    grounding = verify_grounding(
        session,
        org_id=request.org_id,
        claims=[final_conclusion] if final_conclusion else [],
    )
    grounding_refs = [
        c.supporting_fact_id for c in grounding.claims if c.supporting_fact_id is not None
    ]

    # Step 6: CONFIDENCE (external)
    breakdown = scorer.score(
        constraint_pass=constraint_check.ok,
        grounding_score=grounding.grounding_score,
        # consistency: only meaningful for neural-sampled outputs; pass 1.0 if no neural
        consistency_score=1.0 if neural_conclusion is None else 0.7,
        symbolic_support=symbolic.resolved,
    )

    # Step 8: ROUTE 80/20
    routing = route_decision(
        confidence=breakdown.overall,
        reversible=request.reversible,
        user_redlines_hit=request.user_redlines_hit,
    )

    # Step 9: REFLECT (selective; we record the trigger but don't auto-correct per MD)
    trigger = should_reflect(
        confidence=breakdown.overall,
        irreversibility=request.irreversibility,
        blast_radius=request.blast_radius,
    )
    reflected = trigger.fires
    if reflected and routing.route != Route.FLAG:
        # Per MD: prefer FLAG-to-human over silent auto-fix when reflection fires
        log.info(
            "reflection_fired_promote_to_flag",
            org_id=request.org_id,
            stakes=trigger.stakes,
            confidence=breakdown.overall,
        )
        routing = RoutingDecision(
            route=Route.FLAG,
            confidence=breakdown.overall,
            reason=f"reflection fired (stakes*(1-conf)={trigger.score:.3f}) — promoted to FLAG per MD policy",
            redline_triggered=routing.redline_triggered,
        )

    # Step 10: EMIT — persist + return
    row = DecisionRow(
        org_id=request.org_id,
        query_jsonb=dict(request.query),
        conclusion=final_conclusion,
        derivation_chain_jsonb=symbolic.proof.model_dump(),
        path=path,
        confidence_score=breakdown.overall,
        confidence_breakdown_jsonb={
            "overall": breakdown.overall,
            "constraint_pass": breakdown.constraint_pass,
            "grounding_score": breakdown.grounding_score,
            "consistency_score": breakdown.consistency_score,
            "symbolic_support": breakdown.symbolic_support,
            "weights": breakdown.weights,
        },
        grounding_refs_jsonb=grounding_refs,
        route=routing.route.value,
        as_of_version=as_of_v,
        triggered_by=request.triggered_by,
        module_id=request.module_id,
        user_id=request.user_id,
        agent_id=request.agent_id,
    )
    session.add(row)
    session.flush()

    audit.record(
        org_id=request.org_id,
        actor_type="system",
        actor_id="decision.decide",
        action="decision_made",
        target_type="decision",
        target_id=row.id,
        metadata={
            "conclusion": final_conclusion[:120],
            "path": path,
            "route": routing.route.value,
            "confidence": round(breakdown.overall, 3),
            "reflected": reflected,
            "halted_by_cost_guard": halted,
            "module_id": request.module_id,
            "triggered_by": request.triggered_by,
        },
    )

    return DecideResult(
        decision_id=row.id,
        conclusion=final_conclusion,
        path=path,
        route=routing.route,
        confidence=breakdown.overall,
        confidence_breakdown={
            "constraint_pass": breakdown.constraint_pass,
            "grounding_score": breakdown.grounding_score,
            "consistency_score": breakdown.consistency_score,
            "symbolic_support": breakdown.symbolic_support,
            "weights": breakdown.weights,
        },
        proof=symbolic.proof,
        grounding_score=grounding.grounding_score,
        grounding_refs=grounding_refs,
        routing=routing,
        reflected=reflected,
        as_of_version=as_of_v,
        halted_by_cost_guard=halted,
    )


# ─── helpers ────────────────────────────────────────────────────────────────


def _path_from_fusion(symbolic: ChainResult, neural_conclusion: str | None, winner: str) -> str:
    if winner == "symbolic" and neural_conclusion is None:
        return "symbolic"
    if winner == "neural":
        return "neural"
    if winner == "symbolic" and neural_conclusion is not None:
        return "hybrid"  # both attempted; symbolic won
    if not symbolic.resolved and neural_conclusion is None:
        return "symbolic"  # default — empty conclusion
    return "hybrid"


def _extract_neural_conclusion(parsed: BaseModel) -> str:
    """Pull a conclusion string from the LLM's parsed output via common field names."""
    data = parsed.model_dump()
    for key in ("conclusion", "decision", "recommendation", "answer"):
        if key in data:
            return str(data[key])
    return ""
