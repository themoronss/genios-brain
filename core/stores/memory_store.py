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
            self.client.table("memory_items")
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
            self.client.table("memory_items")
            .select("content")
            .eq("actor_id", actor_id)
            .eq("memory_type", "preference")
            .execute()
        )
        merged = {}
        for row in rows.data or []:
            if isinstance(row.get("content"), dict):
                merged.update(row["content"])
        return merged

    def get_entity_data(self, actor_id: str) -> dict:
        """
        Retrieve entity-type memories for an actor.
        Returns a dict mapping entity names to their data.
        """
        rows = (
            self.client.table("memory_items")
            .select("content")
            .eq("actor_id", actor_id)
            .eq("memory_type", "entity")
            .execute()
        )
        merged = {}
        for row in rows.data or []:
            if isinstance(row.get("content"), dict):
                merged.update(row["content"])
        return merged

    def write_update(
        self,
        actor_id: str,
        workspace_id: str,
        update: "MemoryUpdate",  # type: ignore
    ) -> dict:
        """
        Persist a memory update to Supabase.

        Args:
            actor_id: Actor identifier.
            workspace_id: Workspace identifier.
            update: MemoryUpdate object from Learning Layer.

        Returns:
            Inserted/updated row dict, or empty dict on error.
        """
        from datetime import datetime, timezone

        # Map operation type
        memory_type = "preference" if "preference" in update.field else "episodic"

        row = {
            "workspace_id": workspace_id,
            "actor_id": actor_id,
            "memory_type": memory_type,
            "field_key": update.field,
            "content": update.new_value,
            "confidence": update.confidence,
            "operation": update.operation,
            "evidence_refs": update.evidence_refs,
            "reason": update.reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            result = self.client.table("memory_items").insert(row).execute()
            return result.data[0] if result.data else {}
        except Exception as e:
            print(f"⚠ Memory write failed for {update.field}: {e}")
            return {}
