"""Layer 4 · Part 3 — the Decision Maker.

The orchestrator schedules; the reasoning units analyse; **only this module decides**.  It is the
single point of synthesis in GeniOS: every unit before it emits a typed observation about the
world, and none of them may name a winner.  Keeping that boundary physical — a separate module
with one entry point — is what stops a unit from quietly becoming a second decision authority.

Its shape follows the frozen architecture:

    Evidence Aggregator   → every citation the units stood behind, deduplicated
    Confidence Calculator → one authoritative confidence for the whole decision
    Decision Synthesizer  → declared plays become scored candidates
    Decision Evaluator    → hard checks eliminate candidates *before* anything is ranked
    Decision Ranker       → a total order over the survivors
    Decision Object Builder → one immutable, hashable ReasoningDecision

Two rules hold everywhere below. All arithmetic is integer basis points (0..10,000) with
half-up division, because a float would make the decision hash machine-dependent and destroy
replay.  And every ordering is total — never "whatever order the database returned" — because a
tie broken by iteration order is a decision that cannot be reproduced.

No language model participates here.  Under the confidence floor this module widens uncertainty
and lets the executive layer ask a human; it never invents the missing fact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from genios_engine.contracts.reasoning import (
    CandidateCheck,
    CandidateDisposition,
    CheckOutcome,
    DecisionCandidate,
    DecisionOutcome,
    ReasonerResult,
    ReasoningDecision,
    ResultStatus,
)
from genios_engine.platform.canonical import semantic_hash

from .protocols import OrchestrationError
from .reasoners.common import clamp_bp, divide_half_up

DECISION_MAKER_VERSION = "1.0.0"

#: Reasoner that owns the final word on each shared metric.  Several units legitimately observe
#: confidence and urgency along the way — a legacy rule, a gate, a temporal decay — but exactly one
#: gets to publish the value the decision is built on.  Without a named authority the winner would
#: be "whichever emitter happened to run last", so adding a unit could silently move every score in
#: the system.  Capabilities may name their own authority through the metadata keys below.
CONFIDENCE_AUTHORITY = "core.confidence"
PRIORITY_AUTHORITY = "core.priority"
CONFIDENCE_AUTHORITY_KEY = "confidence_authority"
PRIORITY_AUTHORITY_KEY = "priority_authority"


def _authority(request: Any, key: str, default: str) -> str:
    value = request.capability.metadata.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise OrchestrationError(f"capability metadata {key} must name a reasoner")
    return value.strip()


@dataclass(frozen=True, slots=True)
class DecisionSynthesis:
    """The complete output of Part 3: the candidate field and the decision drawn from it."""

    candidates: tuple[DecisionCandidate, ...]
    decision: ReasoningDecision


# ---------------------------------------------------------------------------------------------
# Evidence Aggregator
# ---------------------------------------------------------------------------------------------

def aggregate_evidence(results: Sequence[ReasonerResult]) -> tuple[str, ...]:
    """Union every evidence id the units cited, directly or through findings and adjustments.

    A candidate carries the whole evidential basis of the run rather than one unit's slice, so the
    explanation a human sees can never cite less than what actually moved the score.
    """
    return tuple(sorted(set(
        evidence_id
        for result in results
        for evidence_id in (
            result.evidence_ids
            + tuple(ev for finding in result.findings for ev in finding.evidence_ids)
            + tuple(ev for adjustment in result.adjustments for ev in adjustment.evidence_ids)
        )
    )))


# ---------------------------------------------------------------------------------------------
# Confidence Calculator
# ---------------------------------------------------------------------------------------------

def _metadata_bp(request: Any, key: str, default: int) -> int:
    value = request.capability.metadata.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise OrchestrationError(f"capability metadata {key} must be integer basis points")
    return value


def calculate_confidence(results: Sequence[ReasonerResult], request: Any, degraded: bool) -> int:
    """Resolve the one confidence that describes this decision.

    The capability's declared default holds until a unit publishes `confidence_bp`; the reasoner
    named by :data:`CONFIDENCE_AUTHORITY` has the last word and ends the scan.  A degraded run —
    one where an optional unit failed — is capped, because a decision reached with a blind spot
    must never present itself as well-evidenced as one reached with every input intact.
    """
    authority = _authority(request, CONFIDENCE_AUTHORITY_KEY, CONFIDENCE_AUTHORITY)
    value = _metadata_bp(request, "default_confidence_bp", 5_000)
    for result in results:
        if result.status == ResultStatus.COMPLETED and "confidence_bp" in result.metrics:
            raw = result.metrics["confidence_bp"]
            if isinstance(raw, bool) or not isinstance(raw, int):
                raise OrchestrationError("confidence_bp must be an integer")
            value = clamp_bp(raw)
        if result.reasoner_id == authority and result.status == ResultStatus.COMPLETED:
            break
    if degraded:
        value = min(value, _metadata_bp(request, "optional_failure_confidence_cap_bp", 5_000))
    return value


def priority_metrics(results: Sequence[ReasonerResult],
                     request: Any) -> tuple[int, int | None]:
    """Resolve shared urgency and any explicit priority override.

    An override replaces the weighted utility outright, so it is read only from the priority
    authority — a unit cannot seize ranking control by emitting the metric opportunistically.

    `request` is required rather than optional: an authority resolved from a default instead of
    from the capability would quietly answer a different question than the caller asked.
    """
    authority = _authority(request, PRIORITY_AUTHORITY_KEY, PRIORITY_AUTHORITY)
    urgency = 5_000
    override = None
    for result in results:
        if result.status != ResultStatus.COMPLETED:
            continue
        if "urgency_bp" in result.metrics:
            urgency = clamp_bp(int(result.metrics["urgency_bp"]))
        if result.reasoner_id == authority:
            if "priority_override_bp" in result.metrics:
                override = clamp_bp(int(result.metrics["priority_override_bp"]))
            break
    return urgency, override


# ---------------------------------------------------------------------------------------------
# Decision Evaluator
# ---------------------------------------------------------------------------------------------

def ordered_checks(checks: Sequence[CandidateCheck]) -> tuple[CandidateCheck, ...]:
    """Impose a total order on checks so an audit row is byte-stable across runs."""
    return tuple(sorted(checks, key=lambda item: (
        item.stage,
        item.evaluator_id,
        item.evaluator_version,
        item.reason_code,
        semantic_hash(item.detail),
    )))


# ---------------------------------------------------------------------------------------------
# Decision Synthesizer + Ranker + Object Builder
# ---------------------------------------------------------------------------------------------

def build_candidates(request: Any, results: Sequence[ReasonerResult],
                     degraded: bool) -> tuple[tuple[DecisionCandidate, ...], int]:
    """Turn declared plays plus unit effects into a ranked, fully-explained candidate field.

    Order of operations is load-bearing. Elimination happens *before* ranking, so a play blocked by
    policy can never win on score and be quietly demoted afterwards — it leaves the contest, and
    the check that removed it is preserved on the candidate as the reason.

    Also returns the decision-level confidence so callers cannot recompute it inconsistently.
    """
    confidence_bp = calculate_confidence(results, request, degraded)
    urgency_bp, priority_override = priority_metrics(results, request)
    adjustments = [item for result in results for item in result.adjustments]
    checks = [item for result in results for item in result.checks]
    evidence = aggregate_evidence(results)

    provisional: list[dict[str, Any]] = []
    for play in sorted(request.capability.plays, key=lambda item: item.play_id):
        components = {
            "impact": play.impact_bp,
            "success": play.success_probability_bp,
            "urgency": urgency_bp,
            "effort": play.effort_bp,
            "risk": play.risk_bp,
        }
        for adjustment in adjustments:
            if adjustment.play_id == play.play_id:
                components[adjustment.component] = clamp_bp(
                    components[adjustment.component] + adjustment.delta_bp)
        play_checks = ordered_checks([item for item in checks if item.play_id == play.play_id])
        eliminated = any(item.outcome == CheckOutcome.ELIMINATE for item in play_checks)
        if priority_override is None:
            weights = request.capability.ranking_weights
            # Effort and risk are costs: the candidate is rewarded for their absence.
            weighted = (
                components["impact"] * weights["impact"]
                + components["success"] * weights["success"]
                + components["urgency"] * weights["urgency"]
                + (10_000 - components["effort"]) * weights["effort"]
                + (10_000 - components["risk"]) * weights["risk"]
            )
            utility_bp = clamp_bp(divide_half_up(weighted, 100))
        else:
            utility_bp = priority_override
        provisional.append({
            "play": play,
            "components": components,
            "checks": play_checks,
            "disposition": (CandidateDisposition.ELIMINATED if eliminated
                            else CandidateDisposition.ELIGIBLE),
            "utility_bp": utility_bp,
        })

    eligible = sorted((item for item in provisional
                       if item["disposition"] == CandidateDisposition.ELIGIBLE),
                      key=lambda item: (-item["utility_bp"], item["play"].play_id))
    eliminated = sorted((item for item in provisional
                         if item["disposition"] == CandidateDisposition.ELIMINATED),
                        key=lambda item: item["play"].play_id)
    rank_by_play = {item["play"].play_id: rank
                    for rank, item in enumerate(eligible, start=1)}
    candidates = []
    for item in eligible + eliminated:
        play = item["play"]
        candidates.append(DecisionCandidate(
            play_id=play.play_id,
            play_version=play.version,
            disposition=item["disposition"],
            utility_bp=item["utility_bp"],
            confidence_bp=confidence_bp,
            score_components=item["components"],
            rank_position=rank_by_play.get(play.play_id),
            checks=item["checks"],
            evidence_ids=evidence,
            parameters={
                "label": play.label,
                "steps": play.steps,
                # `read_only` is the delivery authority bit: adapters refuse anything else.
                "read_only": play.read_only,
                "tags": play.tags,
                "metadata": play.metadata,
                "success_events": play.success_events,
                "window_days": play.window_days,
            },
        ))
    return tuple(candidates), confidence_bp


class DecisionMaker:
    """The sole synthesis authority of Layer 4."""

    def __init__(self, *, version: str = DECISION_MAKER_VERSION) -> None:
        self.version = str(version).strip()
        if not self.version:
            raise ValueError("decision maker version is required")

    def decide(self, request: Any, results: Sequence[ReasonerResult], *,
               terminal: DecisionOutcome | None, uncertainty: Sequence[str],
               degraded: bool) -> DecisionSynthesis:
        """Produce the decision for one execution.

        `terminal` is the orchestrator's report that execution itself ended the run — a required
        unit failed, context was insufficient, or a gate said this situation does not apply. Those
        are facts about execution, not judgements, which is why Part 1 determines them and Part 3
        merely records them.  A terminal run yields no candidates at all: publishing a ranked field
        no unit ever validated would be the exact fabrication this architecture exists to prevent.
        """
        if terminal is None:
            candidates, confidence_bp = build_candidates(request, results, degraded)
            outcome = (DecisionOutcome.DECISION if any(
                item.disposition == CandidateDisposition.ELIGIBLE for item in candidates)
                       else DecisionOutcome.BLOCKED)
        else:
            candidates = ()
            confidence_bp = calculate_confidence(results, request, degraded)
            outcome = terminal

        selected = next((item for item in candidates
                         if item.disposition == CandidateDisposition.ELIGIBLE), None)
        play_by_id = {play.play_id: play for play in request.capability.plays}
        decision = ReasoningDecision(
            outcome=outcome,
            capability_id=request.capability.capability_id,
            capability_version=request.capability.version,
            context_snapshot_id=request.context.context_snapshot_id,
            candidates=candidates,
            selected_candidate_id=(selected.candidate_id if outcome == DecisionOutcome.DECISION
                                   and selected is not None else None),
            confidence_bp=confidence_bp,
            uncertainty=tuple(uncertainty),
            do_nothing_consequence=request.capability.do_nothing_consequence,
            expires_at=request.evaluation_time + timedelta(
                hours=request.capability.expiry_hours),
            outcome_window_days=(play_by_id[selected.play_id].window_days
                                 if outcome == DecisionOutcome.DECISION
                                 and selected is not None else None),
        )
        return DecisionSynthesis(candidates=candidates, decision=decision)


__all__ = ["CONFIDENCE_AUTHORITY", "CONFIDENCE_AUTHORITY_KEY", "DECISION_MAKER_VERSION",
           "PRIORITY_AUTHORITY", "PRIORITY_AUTHORITY_KEY", "DecisionMaker", "DecisionSynthesis",
           "aggregate_evidence", "build_candidates", "calculate_confidence", "ordered_checks",
           "priority_metrics"]
