from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.judgement_engine import JudgementEngine
from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import JudgementReport
from layers.layer3_decision.decision_engine import DecisionEngine
from layers.layer4_learning.learning_engine import LearningEngine


class BrainOrchestrator:

    def __init__(self):
        self.retrieval_engine = RetrievalEngine()
        self.judgement_engine = JudgementEngine()
        self.decision_engine = DecisionEngine()
        self.learning_engine = LearningEngine()

    def run(self, intent: str, workspace_id: str, actor_id: str) -> dict:

        context_bundle = self.retrieval_engine.run(intent, workspace_id, actor_id)

        judgement_report = self.judgement_engine.run(context_bundle)

        decision_packet = self.decision_engine.run(context_bundle, judgement_report)

        # Simulate execution result (MVP)
        execution_result = (
            "approved"
            if decision_packet.execution_mode == "needs_approval"
            else "auto_executed"
        )

        learning_report = self.learning_engine.run(decision_packet, execution_result)

        return {
            "context": context_bundle,
            "judgement": judgement_report,
            "decision": decision_packet,
            "learning": learning_report,
        }
