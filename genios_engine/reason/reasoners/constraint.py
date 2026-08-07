from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.reasoning import (CandidateCheck, CheckOutcome, ReasonerResult,
                                               ReasonerSpec, ReasoningRequest, ResultStatus)

from .common import active_spec, decimal, fact_value


def _compare(actual, operator: str, expected) -> bool:
    if operator in {"=", "==", "eq"}:
        return actual == expected
    if operator in {"!=", "ne"}:
        return actual != expected
    if operator == "in":
        return actual in expected if isinstance(expected, (tuple, list, set, frozenset)) else False
    if operator in {">", ">=", "<", "<="}:
        try:
            left, right = decimal(actual, "precondition actual"), decimal(expected, "precondition expected")
        except ValueError:
            return False
        return {">": left > right, ">=": left >= right,
                "<": left < right, "<=": left <= right}[operator]
    raise ValueError(f"unsupported precondition operator: {operator}")


class ConstraintReasoner:
    _descriptor = ReasonerSpec(reasoner_id="core.constraint", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        spec = active_spec(request, self.spec.reasoner_id)
        checks = []
        policies = set(request.capability.policies)
        context_evidence_ids = {item.evidence_id for item in request.context.evidence}
        used_evidence_ids = {
            evidence_id
            for result in prior_results.values()
            for evidence_id in (
                result.evidence_ids
                + tuple(evidence_id for finding in result.findings
                        for evidence_id in finding.evidence_ids)
                + tuple(evidence_id for adjustment in result.adjustments
                        for evidence_id in adjustment.evidence_ids)
            )
            if evidence_id in context_evidence_ids
        }
        for play in request.capability.plays:
            if "read_only" in policies:
                checks.append(CandidateCheck(
                    play.play_id, "policy",
                    CheckOutcome.PASS if play.read_only else CheckOutcome.ELIMINATE,
                    "read_only_policy_pass" if play.read_only else "read_only_policy",
                    self.spec.reasoner_id, self.spec.version,
                    detail={"required": True, "play_read_only": play.read_only}))

            if "human_approval_required" in policies:
                boundary = play.metadata.get("execution_boundary")
                approval_declared = (
                    boundary == "human_approval_required"
                    or "human_approval" in play.tags
                )
                checks.append(CandidateCheck(
                    play.play_id, "permission",
                    CheckOutcome.PASS if approval_declared else CheckOutcome.ELIMINATE,
                    ("human_approval_boundary_pass" if approval_declared
                     else "human_approval_boundary_missing"),
                    self.spec.reasoner_id, self.spec.version,
                    detail={"execution_boundary": boundary,
                            "human_approval_tag": "human_approval" in play.tags}))

            if "evidence_required" in policies:
                # Merely carrying an unrelated EvidenceRef is not grounding.  At least one
                # dependency must cite an evidence item that exists in this exact snapshot.
                evidence_present = bool(used_evidence_ids)
                checks.append(CandidateCheck(
                    play.play_id, "policy",
                    CheckOutcome.PASS if evidence_present else CheckOutcome.ELIMINATE,
                    "evidence_policy_pass" if evidence_present else "evidence_required",
                    self.spec.reasoner_id, self.spec.version,
                    detail={"context_evidence_count": len(request.context.evidence),
                            "used_evidence_count": len(used_evidence_ids)}))

            if "no_unverified_recipient" in policies:
                # Capability validation requires this typed effect declaration.  Indexing here
                # deliberately fails closed if a malformed object somehow crosses that boundary.
                recipient_required = play.metadata["external_recipient_required"]
                verification_guards = tuple(condition for condition in play.preconditions
                                            if str(condition.get("field") or "").endswith((
                                                ".verified_recipient",
                                                ".recipient_verified",
                                                ".stakeholder_verified",
                                                "_stakeholder_verified",
                                            ))
                                            and condition.get("value") is True
                                            and str(condition.get("op") or "") in
                                            {"=", "==", "eq"})
                guarded = not recipient_required or bool(verification_guards)
                checks.append(CandidateCheck(
                    play.play_id, "permission",
                    CheckOutcome.PASS if guarded else CheckOutcome.ELIMINATE,
                    ("verified_recipient_guard_pass" if guarded
                     else "verified_recipient_guard_missing"),
                    self.spec.reasoner_id, self.spec.version,
                    detail={"external_recipient_required": recipient_required,
                            "guard_count": len(verification_guards)}))
            for index, condition in enumerate(play.preconditions):
                field = str(condition.get("field") or "")
                neighbor = bool(condition.get("neighbor", False))
                exists = field in (request.context.neighbor_facts if neighbor else request.context.facts)
                operator = str(condition.get("op") or "exists")
                expected = condition.get("value")
                if operator == "exists":
                    passed = exists
                    actual = fact_value(request, field, neighbor=neighbor) if exists else None
                elif operator == "absent":
                    passed = not exists
                    actual = fact_value(request, field, neighbor=neighbor) if exists else None
                elif not exists:
                    passed, actual = False, None
                else:
                    actual = fact_value(request, field, neighbor=neighbor)
                    passed = _compare(actual, operator, expected)
                checks.append(CandidateCheck(
                    play.play_id, "precondition",
                    CheckOutcome.PASS if passed else CheckOutcome.ELIMINATE,
                    "precondition_pass" if passed else "precondition_failed",
                    self.spec.reasoner_id, self.spec.version,
                    detail={"index": index, "field": field, "neighbor": neighbor,
                            "operator": operator, "expected": expected, "actual": actual}))
        # Tenant policy inputs can hard-block a play by ID without changing authored expertise.
        for play_id in tuple(spec.config.get("blocked_play_ids") or ()):
            checks.append(CandidateCheck(str(play_id), "policy", CheckOutcome.ELIMINATE,
                                         "tenant_policy_block", self.spec.reasoner_id,
                                         self.spec.version))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              checks=tuple(checks), reason_codes=("constraints_evaluated",))
