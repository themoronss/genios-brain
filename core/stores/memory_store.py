from core.stores.database import get_supabase_client


class MemoryStore:
    """
    Store for retrieving memory items from Supabase.
    Maps to the `memory_items` table.
    """

    def __init__(self):
        self.client = get_supabase_client()

    def get_by_actor(self, actor_id: str) -> list[dict]:
        """
        Retrieve all memory items for a given actor.
        Returns a list of dicts with keys: id, workspace_id, actor_id,
        memory_type, content, confidence.
        """
        result = (
            self.client
            .table("memory_items")
            .select("*")
            .eq("actor_id", actor_id)
            .execute()
        )
        return result.data or []

    def get_preferences(self, actor_id: str) -> dict:
        """
        Retrieve preference-type memories for an actor.
        Returns a merged dict of all preference content.
        """
        rows = (
            self.client
            .table("memory_items")
            .select("content")
            .eq("actor_id", actor_id)
            .eq("memory_type", "preference")
            .execute()
        )
        merged = {}
        for row in (rows.data or []):
            if isinstance(row.get("content"), dict):
                merged.update(row["content"])
        return merged

    def get_entity_data(self, actor_id: str) -> dict:
        """
        Retrieve entity-type memories for an actor.
        Returns a dict mapping entity names to their data.
        """
        rows = (
            self.client
            .table("memory_items")
            .select("content")
            .eq("actor_id", actor_id)
            .eq("memory_type", "entity")
            .execute()
        )
        merged = {}
        for row in (rows.data or []):
            if isinstance(row.get("content"), dict):
                merged.update(row["content"])
        return merged
