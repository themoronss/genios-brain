from core.contracts.decision_packet import DecisionPacket
from core.contracts.learning_report import LearningReport, MemoryUpdate


class LearningEngine:

    def run(
        self,
        decision: DecisionPacket,
        execution_result: str
    ) -> LearningReport:

        memory_updates = []

        # Very simple MVP logic
        if execution_result == "approved":
            memory_updates.append(
                MemoryUpdate(
                    field="last_successful_intent",
                    new_value=decision.intent_type,
                    confidence=0.8
                )
            )

        return LearningReport(
            outcome=execution_result,
            memory_updates=memory_updates
        )