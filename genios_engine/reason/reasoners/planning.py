from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.reasoning import (CandidateCheck, CheckOutcome, Finding,
                                               ReasonerResult, ReasonerSpec, ReasoningRequest,
                                               ResultStatus)


class PlanningReasoner:
    _descriptor = ReasonerSpec(reasoner_id="core.planning", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        del prior_results
        checks = []
        for play in request.capability.plays:
            if play.success_events:
                checks.append(CandidateCheck(play.play_id, "safety", CheckOutcome.PASS,
                                             "outcome_observable", self.spec.reasoner_id,
                                             self.spec.version,
                                             detail={"window_days": play.window_days,
                                                     "success_events": play.success_events}))
            else:
                checks.append(CandidateCheck(play.play_id, "safety", CheckOutcome.WARN,
                                             "outcome_not_observable", self.spec.reasoner_id,
                                             self.spec.version))
        finding = Finding("planning.ready", "planning",
                          metrics={"play_count": len(request.capability.plays)},
                          reason_codes=("plans_validated",))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              findings=(finding,), checks=tuple(checks),
                              reason_codes=finding.reason_codes)
