from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import JudgementReport
from core.contracts.decision_packet import (
    DecisionPacket,
    ActionPlan,
    ActionStep
)


class DecisionEngine:

    def run(
        self,
        bundle: ContextBundle,
        judgement: JudgementReport
    ) -> DecisionPacket:

        intent_type = self._detect_intent(bundle)

        execution_mode = self._decide_execution_mode(judgement)

        plan = self._build_action_plan(intent_type)

        reasons = []
        reasons.extend(judgement.risk.reasons)
        reasons.extend(judgement.policy.reasons)

        return DecisionPacket(
            intent_type=intent_type,
            execution_mode=execution_mode,
            action_plan=plan,
            reasons=reasons
        )

    def _detect_intent(self, bundle: ContextBundle) -> str:
        # For now, simple rule-based intent detection
        return "follow_up"

    def _decide_execution_mode(self, judgement: JudgementReport) -> str:
        if judgement.needs_approval:
            return "needs_approval"
        if judgement.risk.level == "high":
            return "propose_only"
        return "auto_execute"

    def _build_action_plan(self, intent_type: str) -> ActionPlan:
        if intent_type == "follow_up":
            steps = [
                ActionStep(description="Draft follow-up email"),
                ActionStep(description="Schedule send time"),
            ]
        else:
            steps = [
                ActionStep(description="Generic action step")
            ]

        return ActionPlan(steps=steps)