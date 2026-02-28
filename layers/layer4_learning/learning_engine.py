"""
Layer 4 — Learning Engine

The main orchestrator for the Learning Layer.
Coordinates all sub-modules (L0-L4) and the Learning Assembler
to produce a complete LearningReport.

Reliability-preserving feedback system: strict, versioned, reviewable, reversible.
"""

import time

from core.contracts.decision_packet import DecisionPacket
from core.contracts.learning_report import LearningReport

# L0 — Learning Router
from layers.layer4_learning.l0_learning_router.learning_plan_builder import (
    build_learning_plan,
)

# L1 — Outcome Capture
from layers.layer4_learning.l1_outcomes.outcome_normalizer import normalize_outcome

# L2 — Memory Writeback
from layers.layer4_learning.l2_memory_writeback.candidate_generator import (
    generate_candidates,
)
from layers.layer4_learning.l2_memory_writeback.write_policy_gate import gate_updates

# L3 — Policy Suggestions
from layers.layer4_learning.l3_policy_suggestions.suggestion_generator import (
    generate_suggestions,
)

# L4 — Eval
from layers.layer4_learning.l4_eval.eval_aggregator import compute_eval_metrics

# Assembler
from layers.layer4_learning.learning_assembler.assembler import assemble_learning


class LearningEngine:

    def run(
        self,
        decision: DecisionPacket,
        execution_result: str,
        user_feedback: str = "",
        user_comment: str = "",
        tool_errors: list = None,
        latency_ms: float = 0.0,
    ) -> LearningReport:
        """
        Layer 4 — Full Learning Pipeline.

        Steps:
            L0: Build learning plan (which modules to run)
            L1: Normalize outcome (execution result + feedback + errors)
            L2: Generate + gate memory update candidates
            L3: Generate policy suggestions
            L4: Compute eval metrics
            Assemble: Combine into LearningReport

        Args:
            decision: DecisionPacket from Layer 3.
            execution_result: What happened (approved, rejected, etc).
            user_feedback: User action (approve, edit, reject, "").
            user_comment: Optional user comment.
            tool_errors: List of error dicts.
            latency_ms: End-to-end latency.

        Returns:
            Complete LearningReport.
        """
        start_time = time.time()

        # --- L0: Learning Plan ---
        plan = build_learning_plan(decision, execution_result, user_feedback)

        # --- L1: Outcome Capture ---
        outcome = normalize_outcome(
            decision=decision,
            execution_result=execution_result,
            user_feedback=user_feedback,
            user_comment=user_comment,
            tool_errors=tool_errors,
            latency_ms=latency_ms,
        )

        # --- L2: Memory Writeback ---
        memory_updates = []
        if "memory_writeback" in plan["modules"]:
            candidates = generate_candidates(decision, outcome)
            # Get risk level from decision trace if available
            risk_level = "low"  # default
            for reason in decision.reasons:
                if "high" in reason.lower() and "risk" in reason.lower():
                    risk_level = "high"
                    break
                elif "medium" in reason.lower() and "risk" in reason.lower():
                    risk_level = "medium"
            memory_updates = gate_updates(candidates, execution_result, risk_level)

        # --- L3: Policy Suggestions ---
        suggestions = []
        if "policy_suggestions" in plan["modules"]:
            suggestions = generate_suggestions(decision, outcome)

        # --- L4: Eval ---
        eval_metrics = compute_eval_metrics(decision, outcome, memory_updates)

        # --- Assemble ---
        elapsed_ms = (time.time() - start_time) * 1000

        report = assemble_learning(
            outcome_record=outcome,
            memory_updates=memory_updates,
            policy_suggestions=suggestions,
            eval_metrics=eval_metrics,
            learning_time_ms=elapsed_ms,
        )

        return report