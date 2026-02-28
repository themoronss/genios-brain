"""
R4.1 — Policy Loader

Load org policies and risk rules from PolicyStore.
"""

from core.stores.policy_store import PolicyStore
from core.contracts.query_plan import QueryPlan


class PolicyLoader:
    """Loads policies from store for a given workspace."""

    def __init__(self, policy_store: PolicyStore = None):
        self.store = policy_store or PolicyStore(use_db=False)

    def load(self, workspace_id: str, query_plan: QueryPlan) -> list[dict]:
        """
        Load all active policies for the workspace.

        Args:
            workspace_id: Workspace to load policies for.
            query_plan: For future budget enforcement.

        Returns:
            List of policy dicts.
        """
        return self.store.get_by_workspace(workspace_id)
