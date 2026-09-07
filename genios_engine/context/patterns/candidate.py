"""L2.6.2-U1 · the Candidate Builder — a match, assembled into something a situation can be built
from, WITHOUT re-deriving a single thing the match already decided.

The one rule that makes this module worth having: **evidence is CARRIED, never recomputed.** The
temptation is to look the facts up again while assembling — the slice is right there — and the
consequence is that the candidate's explanation and the match that produced it can disagree while
neither looks wrong. A graph that moved between the match and the build would produce a card
citing facts the pattern never saw.

WHAT A CANDIDATE IS NOT. Not scored (`scorer.py`), not clustered (L2.7.3), not published
(L2.5.8 admits it, L2.7.8 publishes it), and above all not a situation: `provisional_type` is
provisional precisely because clustering may merge this candidate into another reality.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.context.patterns.matcher import ConditionEvidence, MatchResult
from genios_engine.context.patterns.slice import GraphSlice


class UnevidencedCondition(ValueError):
    """A match arrived carrying a condition with no evidence object.

    Raised rather than tolerated: `matcher` already treats an unevidenced satisfaction as a
    failure, so a match that reaches here with one has been constructed by hand or by a future
    caller that skipped the evaluator. Letting it through would undo the guarantee one layer
    later, which is worse than the original defect because the failure is now two modules from
    its cause.
    """


@dataclass(frozen=True, slots=True)
class SituationCandidate:
    """A provisional business reality: what fired, over what, and what proves it."""

    org_id: str
    pattern_id: str
    pattern_version: int
    #: Provisional — L2.7.3 clustering may merge this into a situation of another type.
    provisional_type: str
    anchor_node_id: str
    anchor_node_type: str
    matched_nodes: tuple[str, ...]
    matched_edges: tuple[str, ...]
    #: One per required condition, carried from the match unchanged.
    per_condition_evidence: tuple[ConditionEvidence, ...]
    optional_evidence: tuple[ConditionEvidence, ...]
    #: The evidence the SITUATION rests on, as ids — signals and events attached to the anchor.
    member_signal_ids: tuple[str, ...]
    member_event_ids: tuple[str, ...]
    match_strength_bp: int
    eval_time: datetime

    #: There is deliberately NO score field and NO importance field on this type. Scoring is
    #: `scorer.CandidateScore`'s and importance is BLG-18's, and a candidate carrying either
    #: would be a second ranking scale beside the one that already has stored components.

    @property
    def candidate_key(self) -> str:
        """A stable identity for this candidate — pattern, version and anchor.

        Derived rather than minted: two drains over an unchanged world must produce the same key,
        or the fire log double-counts and every fire rate in the report is wrong by however many
        times the drain ran.
        """
        return f"{self.pattern_id}@{self.pattern_version}:{self.anchor_node_id}"

    def as_record(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "pattern_id": self.pattern_id,
                "pattern_version": self.pattern_version, "provisional_type": self.provisional_type,
                "anchor_node_id": self.anchor_node_id, "anchor_node_type": self.anchor_node_type,
                "matched_nodes": list(self.matched_nodes),
                "matched_edges": list(self.matched_edges),
                "matched_conditions": [e.as_record() for e in self.per_condition_evidence],
                "optional_signals": [e.as_record() for e in self.optional_evidence],
                "member_signal_ids": list(self.member_signal_ids),
                "member_event_ids": list(self.member_event_ids),
                "match_strength_bp": self.match_strength_bp,
                "eval_time": self.eval_time.isoformat()}


def build_candidate(match_result: MatchResult, graph_slice: GraphSlice, *,
                    eval_time: datetime) -> SituationCandidate:
    """Assemble one match into a candidate. Carries; does not re-derive.

    `graph_slice` is taken for its MEMBERS only — the signal and event ids the situation will
    rest on. Every matched node, edge and piece of evidence comes from the `MatchResult`, which
    is why mutating the graph between the match and this call cannot change what the candidate
    says it saw.
    """
    for evidence in (*match_result.evidence, *match_result.optional_evidence):
        if not evidence.ref:
            raise UnevidencedCondition(
                f"condition {evidence.index} ({evidence.field_path}) carries no evidence object; "
                "it should have failed in the evaluator")
    return SituationCandidate(
        org_id=match_result.org_id, pattern_id=match_result.pattern_id,
        pattern_version=match_result.pattern_version,
        provisional_type=match_result.situation_type,
        anchor_node_id=match_result.anchor_node_id,
        anchor_node_type=match_result.anchor_node_type,
        matched_nodes=match_result.matched_nodes, matched_edges=match_result.matched_edges,
        per_condition_evidence=match_result.evidence,
        optional_evidence=match_result.optional_evidence,
        # Sorted and deduplicated: these reach a content-addressed object, and an iteration-order
        # difference over one unchanged situation mints a fresh package row per sweep — the
        # mechanism behind the 995 MB read-only incident.
        member_signal_ids=tuple(sorted(set(graph_slice.member_signal_ids))),
        member_event_ids=tuple(sorted(set(graph_slice.member_event_ids))),
        match_strength_bp=match_result.match_strength_bp, eval_time=eval_time)


__all__ = ["SituationCandidate", "UnevidencedCondition", "build_candidate"]
