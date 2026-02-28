"""
Layer 2 — Judgement Engine

The main orchestrator for the Judging Layer.
Coordinates all sub-modules (J0-J5) and the Judgement Assembler
to produce a complete JudgementReport.

Pure evaluation — no tool calls, no DB queries.
All data comes from the ContextBundle (Layer 1 output).
"""

import time

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import JudgementReport

# J0 — Judgement Planner
from layers.layer2_judgement.j0_judgement_planner.plan_builder import (
    build_judgement_plan,
)

# J1 — Sufficiency Check
from layers.layer2_judgement.j1_sufficiency.question_generator import (
    check_sufficiency,
)

# J2 — Policy Compliance
from layers.layer2_judgement.j2_policy.violation_engine import evaluate_policies

# J3 — Risk Assessment
from layers.layer2_judgement.j3_risk.risk_aggregator import assess_risk

# J4 — Priority Scoring
from layers.layer2_judgement.j4_priority.importance_scorer import score_priority

# J5 — Multi-Factor Evaluation
from layers.layer2_judgement.j5_multifactor.constraint_compiler import (
    evaluate_multifactor,
)

# Assembler
from layers.layer2_judgement.judgement_assembler.assembler import (
    assemble_judgement,
)


class JudgementEngine:

    def run(self, bundle: ContextBundle) -> JudgementReport:
        """
        Layer 2 — Full Judging Pipeline.

        Steps:
            J0: Build judgement plan (which checks to run, thresholds)
            J1: Sufficiency check (missing fields, stale data)
            J2: Policy compliance (violations, approvals, constraints)
            J3: Risk assessment (sensitive entities, reversibility, score)
            J4: Priority scoring (urgency, importance, distraction)
            J5: Multi-factor evaluation (factors, ranking, constraints)
            Assemble: Combine into JudgementReport with derived ok_to_act

        Args:
            bundle: ContextBundle from Layer 1.

        Returns:
            Complete JudgementReport.
        """
        start_time = time.time()

        # --- J0: Judgement Planner ---
        plan = build_judgement_plan(bundle)

        # --- J1: Sufficiency Check ---
        need_more_info = check_sufficiency(bundle, plan.intent_type)

        # --- J2: Policy Compliance ---
        policy = evaluate_policies(bundle)

        # --- J3: Risk Assessment ---
        risk = assess_risk(bundle, plan.intent_type)

        # --- J4: Priority Scoring ---
        priority = score_priority(bundle, plan.intent_type, plan.org_mode)

        # --- J5: Multi-Factor Evaluation ---
        multi_factor = evaluate_multifactor(
            bundle=bundle,
            intent_type=plan.intent_type,
            policy=policy,
            risk=risk,
        )

        # --- Assemble ---
        elapsed_ms = (time.time() - start_time) * 1000

        report = assemble_judgement(
            need_more_info=need_more_info,
            policy=policy,
            risk=risk,
            priority=priority,
            multi_factor=multi_factor,
            judging_time_ms=elapsed_ms,
            policies_evaluated=len(bundle.policy.rules),
        )

        return report