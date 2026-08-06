"""Deterministically compose several audited signals into one compound finding."""

from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.reasoning import (Finding, ReasonerResult, ReasonerSpec,
                                               ReasoningRequest, ResultStatus)

from .common import clamp_bp, evidence_ids, fact_value, integer


def _percent_to_bp(value, label: str) -> int:
    amount = integer(value, label)
    if not 0 <= amount <= 100:
        raise ValueError(f"{label} must be between 0 and 100")
    return amount * 100


class SignalCompositionReasoner:
    _descriptor = ReasonerSpec(reasoner_id="core.signal_composition", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        del prior_results
        members = fact_value(request, "signals.open")
        if not isinstance(members, (tuple, list)):
            return ReasonerResult(
                self.spec.reasoner_id, self.spec.version,
                ResultStatus.INSUFFICIENT_CONTEXT,
                missing_fields=("signals.open",),
                reason_codes=("signal_members_missing",),
            )
        normalized = []
        for member in members:
            if not isinstance(member, Mapping):
                raise ValueError("every signal member must be an object")
            signal_id = str(member.get("signal_id") or "")
            reason_code = str(member.get("reason_code") or "")
            parent_run = str(member.get("reasoning_run_id") or "")
            if not signal_id or not reason_code or not parent_run:
                raise ValueError("composite members require signal, reason, and reasoning run IDs")
            normalized.append(member)
        codes = tuple(sorted({str(item["reason_code"]) for item in normalized}))
        matched = len(normalized) >= 2 and len(codes) >= 2
        strongest = sorted(normalized, key=lambda item: (
            -integer(item.get("score", 0), "member score"),
            str(item.get("reason_code") or ""),
            str(item.get("subject_node_id") or ""),
            str(item.get("signal_id") or ""),
        ))[0] if normalized else {}
        score = integer(strongest.get("score", 0), "strongest score") if strongest else 0
        if not 0 <= score <= 100:
            raise ValueError("strongest score must be between 0 and 100")
        score_inputs = strongest.get("score_inputs") or {}
        if not isinstance(score_inputs, Mapping):
            raise ValueError("member score_inputs must be an object")
        confidence_bp = _percent_to_bp(score_inputs.get("C", 50), "member confidence")
        urgency_bp = _percent_to_bp(score_inputs.get("U", score), "member urgency")
        ev = evidence_ids(request, "signals.open")
        metrics = {
            "member_count": len(normalized),
            "distinct_reason_count": len(codes),
            "signal_score_bp": clamp_bp(score * 100),
            "confidence_bp": confidence_bp,
            "urgency_bp": urgency_bp,
        }
        finding = Finding(
            "signal.compound_condition",
            "signal_composition",
            matched=matched,
            metrics=metrics,
            evidence_ids=ev,
            reason_codes=(("compound_condition_present",) if matched
                          else ("compound_condition_absent",)),
        )
        return ReasonerResult(
            self.spec.reasoner_id,
            self.spec.version,
            ResultStatus.COMPLETED,
            matched=matched,
            metrics=metrics,
            findings=(finding,),
            evidence_ids=ev,
            reason_codes=finding.reason_codes,
        )


__all__ = ["SignalCompositionReasoner"]
