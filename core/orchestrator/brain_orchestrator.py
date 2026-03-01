from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.judgement_engine import JudgementEngine
from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import JudgementReport
from layers.layer3_decision.decision_engine import DecisionEngine
from layers.layer4_learning.learning_engine import LearningEngine
from core.execution.executor import ExecutionAdapter
from core.config import Config


class BrainOrchestrator:

    def __init__(self, use_db: bool = None):
        """
        Args:
            use_db: If True, connect to Supabase for real data.
                    If None, use Config.USE_DB (from environment).
                    If False, use mock data.
        """
        # Use environment config if not explicitly set
        if use_db is None:
            use_db = Config.USE_DB

        memory_store = None
        vector_store = None

        if use_db:
            try:
                from core.stores.memory_store import MemoryStore
                from core.stores.vector_store import VectorStore
                from core.stores.embedding_service import EmbeddingService

                memory_store = MemoryStore()
                embedding_service = EmbeddingService()
                vector_store = VectorStore(embedding_service=embedding_service)
            except Exception as e:
                print(f"⚠ Could not connect to Supabase: {e}. Using mock data.")
                use_db = False

        self.retrieval_engine = RetrievalEngine(
            memory_store=memory_store,
            vector_store=vector_store,
            use_real_tools=use_db,
        )
        self.judgement_engine = JudgementEngine()
        self.decision_engine = DecisionEngine()
        self.learning_engine = LearningEngine(memory_store=memory_store)
        self.executor = ExecutionAdapter(use_real_tools=use_db)

    def run(self, intent: str, workspace_id: str, actor_id: str) -> dict:

        context_bundle = self.retrieval_engine.run(intent, workspace_id, actor_id)

        judgement_report = self.judgement_engine.run(context_bundle)

        decision_packet = self.decision_engine.run(context_bundle, judgement_report)

        # Execute tool calls via Execution Adapter
        exec_result = self.executor.execute(
            plan=decision_packet.action_plan,
            execution_mode=decision_packet.execution_mode,
        )

        # Determine execution result based on execution mode + adapter output
        if decision_packet.execution_mode == "needs_approval":
            execution_result = "pending_approval"
        elif decision_packet.execution_mode == "propose_only":
            execution_result = "proposed"
        elif exec_result.status == "success":
            execution_result = "auto_executed"
        else:
            execution_result = "failed"

        learning_report = self.learning_engine.run(
            decision=decision_packet,
            execution_result=execution_result,
            workspace_id=workspace_id,
            actor_id=actor_id,
        )

        return {
            "context": context_bundle,
            "judgement": judgement_report,
            "decision": decision_packet,
            "learning": learning_report,
        }
