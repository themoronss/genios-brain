from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.reasoning import (Finding, ReasonerResult, ReasonerSpec,
                                               ReasoningRequest, ResultStatus)
from genios_engine.reason.engine import NodeContext, evaluate, score_rule
from genios_engine.reason.rules import rule_from_dict

from .common import active_spec, evidence_ids


class LegacyRuleReasoner:
    """Compatibility reasoner: exact legacy rule match/score behind the v2 protocol."""

    _descriptor = ReasonerSpec(reasoner_id="legacy.rule", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        del prior_results
        spec = active_spec(request, self.spec.reasoner_id)
        rule_data = dict(spec.config.get("rule") or {})
        scoring = dict(spec.config.get("scoring") or {})
        rule = rule_from_dict(rule_data)
        baselines = dict(request.context.metadata.get("baselines") or {})
        ctx = NodeContext(
            node_id=request.context.root_entity_id,
            node_type=request.context.root_entity_type,
            facts={key: dict(value) if isinstance(value, Mapping) else {"value": value}
                   for key, value in request.context.facts.items()},
            obs=[dict(item) for item in request.context.observations],
            baselines=baselines,
            edge_count=request.context.edge_count,
            neighbor_obs=set(request.context.neighbor_observations),
            neighbor_facts={key: (value.get("value") if isinstance(value, Mapping)
                                  and "value" in value else value)
                            for key, value in request.context.neighbor_facts.items()},
        )
        matched = evaluate(ctx, rule, request.evaluation_time)
        if not matched:
            return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                                  matched=False, reason_codes=("legacy_rule_not_matched",))
        score, inputs = score_rule(ctx, rule, request.evaluation_time, scoring)
        ev = evidence_ids(request, *rule.evidence_fields)
        metrics = {"legacy_score": score, "priority_bp": score * 100,
                   "confidence_bp": int(inputs["C"]) * 100,
                   "urgency_bp": int(inputs["U"]) * 100,
                   "impact_bp": int(inputs["I"]) * 100,
                   "recency_bp": int(inputs["R"]) * 100,
                   "legacy_terms_bp": int(inputs["terms_bp"])}
        finding = Finding(f"legacy.{rule.id}", "legacy_rule", matched=True, metrics=metrics,
                          evidence_ids=ev, reason_codes=(rule.reason_code,))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              matched=True, metrics=metrics, findings=(finding,), evidence_ids=ev,
                              reason_codes=(rule.reason_code,))
