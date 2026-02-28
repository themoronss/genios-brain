"""
R5.1 — Decision Log Retriever

Search past decisions by intent type.
Returns top-K precedents for the current context.
"""

from core.contracts.query_plan import QueryPlan
from core.stores.precedent_store import PrecedentStore


class DecisionLogRetriever:
    """Retrieve past decisions from the precedent store."""

    def __init__(self, precedent_store: PrecedentStore = None):
        self.store = precedent_store or PrecedentStore(use_db=False)

    def retrieve(self, workspace_id: str, query_plan: QueryPlan) -> list[dict]:
        """
        Fetch past decisions matching the current intent type.

        Args:
            workspace_id: Workspace scope.
            query_plan: For intent_type and budget.

        Returns:
            List of decision log dicts.
        """
        return self.store.get_by_intent(
            workspace_id=workspace_id,
            intent_type=query_plan.intent_type,
            limit=query_plan.budget.max_precedents,
        )
