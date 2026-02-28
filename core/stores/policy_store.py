"""
Policy Store — Supabase-backed policy retrieval.

Maps to the `policies` table. Falls back to hardcoded defaults
if Supabase is not configured.
"""

from core.stores.database import get_supabase_client


# Hardcoded default policies (used when Supabase is unavailable)
DEFAULT_POLICIES = [
    {
        "id": "P_VIP_APPROVAL",
        "workspace_id": "w1",
        "policy_type": "org",
        "condition": {"recipient_tier": "VIP"},
        "effect": {"requires_approval": True},
        "priority": 10,
        "active": True,
    },
    {
        "id": "P_COLD_OUTREACH_REVIEW",
        "workspace_id": "w1",
        "policy_type": "risk",
        "condition": {"intent_type": "cold_outreach"},
        "effect": {"requires_approval": True, "risk_flag": "external_first_contact"},
        "priority": 8,
        "active": True,
    },
    {
        "id": "P_NO_WEEKENDS",
        "workspace_id": "w1",
        "policy_type": "org",
        "condition": {"day_of_week": ["saturday", "sunday"]},
        "effect": {"delay_until": "next_monday"},
        "priority": 5,
        "active": True,
    },
]


class PolicyStore:
    """Supabase-backed policy store with hardcoded fallback."""

    def __init__(self, use_db: bool = False):
        """
        Args:
            use_db: If True, try to fetch from Supabase.
                    If False, use hardcoded defaults.
        """
        self.use_db = use_db
        self._client = None

    @property
    def client(self):
        if self._client is None and self.use_db:
            self._client = get_supabase_client()
        return self._client

    def get_by_workspace(self, workspace_id: str) -> list[dict]:
        """Get all active policies for a workspace."""
        if not self.use_db:
            return [p for p in DEFAULT_POLICIES if p["workspace_id"] == workspace_id]

        result = (
            self.client
            .table("policies")
            .select("*")
            .eq("workspace_id", workspace_id)
            .eq("active", True)
            .order("priority", desc=True)
            .execute()
        )
        return result.data or []

    def get_by_type(self, workspace_id: str, policy_type: str) -> list[dict]:
        """Get policies of a specific type for a workspace."""
        all_policies = self.get_by_workspace(workspace_id)
        return [p for p in all_policies if p.get("policy_type") == policy_type]
