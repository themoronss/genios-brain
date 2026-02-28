"""
Layer 3 — Decision Engine

The main orchestrator for the Decision Layer.
Coordinates all sub-modules (D0-D5) and the Decision Assembler
to produce a complete DecisionPacket.

No execution happens here. Only planning + instruction generation.
"""

import time

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import JudgementReport
from core.contracts.decision_packet import DecisionPacket

# D0 — Router
from layers.layer3_decision.d0_router.route_builder import resolve_route

# D1 — Intent Clarification
from layers.layer3_decision.d1_intent.intent_finalizer import finalize_intent

# D2 — Plan Generation
from layers.layer3_decision.d2_planning.step_builder import build_plan
from layers.layer3_decision.d2_planning.constraint_enforcer import enforce_constraints

# D3 — Execution Mode
from layers.layer3_decision.d3_execution_mode.mode_gate_engine import (
    determine_execution_mode,
)
from layers.layer3_decision.d3_execution_mode.approval_chain import (
    resolve_approval_chain,
)

# D4 — Trace
from layers.layer3_decision.d4_trace.reason_graph import build_reason_graph
from layers.layer3_decision.d4_trace.rejection_logger import log_rejections

# D5 — Packaging
from layers.layer3_decision.d5_packaging.brain_response_builder import (
    build_brain_response,
)
from layers.layer3_decision.d5_packaging.save_instruction_compiler import (
    compile_save_instructions,
)

# Assembler
from layers.layer3_decision.decision_assembler.assembler import assemble_decision


class DecisionEngine:

    def run(
        self,
        bundle: ContextBundle,
        judgement: JudgementReport,
    ) -> DecisionPacket:
        """
        Layer 3 — Full Decision Pipeline.

        Steps:
            D0: Route to correct decision template
            D1: Finalize intent + extract slots
            D2: Generate action plan from template + constraints
            D3: Determine execution mode (gate engine + approval chain)
            D4: Build decision trace (reasons, policies, rejections)
            D5: Package output (brain response + save instructions)
            Assemble: Combine into DecisionPacket

        Args:
            bundle: ContextBundle from Layer 1.
            judgement: JudgementReport from Layer 2.

        Returns:
            Complete DecisionPacket.
        """
        start_time = time.time()

        # --- D0: Route ---
        route = resolve_route(bundle, judgement)

        # --- D1: Intent Clarification ---
        intent_type, slots = finalize_intent(bundle, judgement, route)

        # --- D2: Plan Generation ---
        plan = build_plan(intent_type, slots)
        plan, constraints_applied = enforce_constraints(plan, judgement)

        # --- D3: Execution Mode ---
        execution = determine_execution_mode(
            judgement, route.get("overrides")
        )
        execution = resolve_approval_chain(execution, judgement)

        # --- D4: Trace ---
        trace = build_reason_graph(bundle, judgement, execution, intent_type, slots)
        rejections = log_rejections(intent_type, judgement)
        trace.rejected_options = rejections

        # --- D5: Packaging ---
        brain_response = build_brain_response(
            intent_type, slots, execution, plan, trace.why
        )
        save_instructions = compile_save_instructions(
            intent_type, execution.mode, slots
        )
        brain_response.save_instructions = save_instructions

        # --- Assemble ---
        elapsed_ms = (time.time() - start_time) * 1000

        packet = assemble_decision(
            intent_type=intent_type,
            intent_slots=slots,
            action_plan=plan,
            execution=execution,
            trace=trace,
            brain_response=brain_response,
            decision_time_ms=elapsed_ms,
            constraints_applied=constraints_applied,
        )

        return packet