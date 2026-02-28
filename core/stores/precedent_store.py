"""
Precedent Store — retrieval of past decisions.

Maps to the `decision_logs` table. Falls back to hardcoded defaults
if Supabase is not configured.
"""

from core.stores.database import get_supabase_client


# Hardcoded demo precedents (used when Supabase is unavailable)
DEFAULT_PRECEDENTS = [
    {
        "id": "d1",
        "workspace_id": "w1",
        "actor_id": "u1",
        "intent_type": "follow_up",
        "decision_summary": "Drafted follow-up email using warm template, scheduled for 9am.",
        "outcome": "success",
        "outcome_score": 0.9,
        "context_hash": "abc123",
        "created_at": "2026-02-20T09:00:00Z",
    },
    {
        "id": "d2",
        "workspace_id": "w1",
        "actor_id": "u1",
        "intent_type": "follow_up",
        "decision_summary": "Sent aggressive follow-up. Investor responded negatively.",
        "outcome": "failure",
        "outcome_score": 0.2,
        "context_hash": "def456",
        "created_at": "2026-02-15T14:00:00Z",
    },
    {
        "id": "d3",
        "workspace_id": "w1",
        "actor_id": "u1",
        "intent_type": "schedule_meeting",
        "decision_summary": "Scheduled meeting at investor's preferred time slot.",
        "outcome": "success",
        "outcome_score": 0.95,
        "context_hash": "ghi789",
        "created_at": "2026-02-18T10:00:00Z",
    },
]


class PrecedentStore:
    """Store for past decisions with hardcoded fallback."""

    def __init__(self, use_db: bool = False):
        self.use_db = use_db
        self._client = None

    @property
    def client(self):
        if self._client is None and self.use_db:
            self._client = get_supabase_client()
        return self._client

    def get_by_intent(
        self, workspace_id: str, intent_type: str, limit: int = 5
    ) -> list[dict]:
        """
        Get past decisions matching workspace + intent type.

        Args:
            workspace_id: Workspace scope.
            intent_type: Filter by intent type.
            limit: Max results to return.

        Returns:
            List of decision log dicts, newest first.
        """
        if not self.use_db:
            results = [
                p for p in DEFAULT_PRECEDENTS
                if p["workspace_id"] == workspace_id
                and p["intent_type"] == intent_type
            ]
            return sorted(
                results, key=lambda x: x.get("created_at", ""), reverse=True
            )[:limit]

        result = (
            self.client
            .table("decision_logs")
            .select("*")
            .eq("workspace_id", workspace_id)
            .eq("intent_type", intent_type)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
