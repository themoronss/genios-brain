from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import (
    JudgementReport,
    RiskReport,
    PolicyVerdict
)


class JudgementEngine:

    def run(self, bundle: ContextBundle) -> JudgementReport:
        """
        Layer 2 - Judgement
        Responsibilities:
        - Evaluate risk
        - Evaluate policy compliance
        - Decide approval requirement
        - Compute ok_to_act
        """

        risk = self._evaluate_risk(bundle)
        policy = self._evaluate_policy(bundle)

        needs_approval = policy.status == "needs_approval"
        ok_to_act = policy.status != "deny"

        return JudgementReport(
            risk=risk,
            policy=policy,
            ok_to_act=ok_to_act,
            needs_approval=needs_approval
        )

    def _evaluate_risk(self, bundle: ContextBundle) -> RiskReport:
        reasons = []
        score = 0.0

        entity_data = bundle.memory.entity_data.get("Investor X", {})
        if entity_data.get("tier") == "VIP":
            score += 0.6
            reasons.append("VIP recipient")

        gmail_data = bundle.tools.snapshots.get("gmail", {})
        if gmail_data.get("thread_exists"):
            score += 0.2
            reasons.append("Existing thread context")

        if score >= 0.7:
            level = "high"
        elif score >= 0.4:
            level = "medium"
        else:
            level = "low"

        return RiskReport(score=score, level=level, reasons=reasons)

    def _evaluate_policy(self, bundle: ContextBundle) -> PolicyVerdict:
        rules = bundle.policy.rules

        for rule in rules:
            if rule["condition"].get("recipient_tier") == "VIP":
                return PolicyVerdict(
                    status="needs_approval",
                    reasons=["VIP email requires approval"]
                )

        return PolicyVerdict(
            status="allow",
            reasons=[]
        )