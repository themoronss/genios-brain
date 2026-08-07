from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.reasoning import (Finding, ReasonerResult, ReasonerSpec,
                                               ReasoningRequest, ResultStatus)

from .common import active_spec, clamp_bp, integer


class PriorityReasoner:
    """Produces global priority inputs; the orchestrator's math stage ranks actual candidates."""

    _descriptor = ReasonerSpec(reasoner_id="core.priority", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        spec = active_spec(request, self.spec.reasoner_id)
        source = str(spec.config.get("source_reasoner") or "")
        if source and source in prior_results:
            metrics = prior_results[source].metrics
            override = metrics.get("priority_bp")
            urgency = metrics.get("urgency_bp", 5_000)
        else:
            override = None
            urgency = max((integer(result.metrics.get("urgency_bp", 0), "urgency_bp")
                           for result in prior_results.values()), default=5_000)
        output = {"urgency_bp": clamp_bp(integer(urgency, "urgency_bp"))}
        if override is not None:
            output["priority_override_bp"] = clamp_bp(integer(
                override, "priority_override_bp"))
        finding = Finding("priority.inputs", "priority", metrics=output,
                          reason_codes=("priority_inputs_ready",))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              metrics=output, findings=(finding,),
                              reason_codes=finding.reason_codes)
